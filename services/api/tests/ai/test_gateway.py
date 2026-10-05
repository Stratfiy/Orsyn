"""Test Gateway, cost computation, and logging."""

import logging
from decimal import Decimal

import pytest

from app.ai.fake_provider import FakeProvider
from app.ai.gateway import (
    Gateway,
    GatewayError,
    GatewayTimeoutError,
    Message,
    ModelRequest,
    UnknownModelError,
    compute_cost,
    get_gateway,
)
from app.settings import Settings


def test_gateway_complete_success() -> None:
    """Done when: gateway.complete returns tokens and cost_usd as Decimal."""
    gateway = Gateway(FakeProvider())
    req = ModelRequest(
        org_id="test-org",
        feature="test_feature",
        model="fake-echo",
        prompt_id="prompt-1",
        prompt_version="1",
        messages=[Message(role="user", content="hello world")],
    )
    resp = gateway.complete(req)
    assert resp.text == "hello world"
    assert resp.model == "fake-echo"
    assert isinstance(resp.cost_usd, Decimal)
    assert resp.cost_usd == Decimal(0)
    assert resp.input_tokens == 2
    assert resp.output_tokens == 2


def test_gateway_cost_computation_prices(monkeypatch: pytest.MonkeyPatch) -> None:
    """Done when: cost is computed in code from PRICES table."""
    from app.ai import gateway

    monkeypatch.setitem(gateway.PRICES, "test-model", (Decimal(3), Decimal(15)))

    cost = compute_cost("test-model", 1_000_000, 1_000_000)
    assert cost == Decimal(18)  # (3 + 15) = 18


def test_gateway_cost_logging_fields_success(caplog: pytest.LogCaptureFixture) -> None:
    """Done when: one log record per call with all fields but no message text in success path."""
    caplog.set_level(logging.INFO, logger="orsyn.ai.cost")

    sentinel = "SENTINEL-7f3a9c"
    gateway = Gateway(FakeProvider())
    req = ModelRequest(
        org_id="org-123",
        feature="test_feature",
        model="fake-echo",
        prompt_id="prompt-abc",
        prompt_version="v2",
        messages=[Message(role="user", content=sentinel)],
    )

    gateway.complete(req)

    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.name == "orsyn.ai.cost"
    assert record.msg == "ai_call"

    extra = record.__dict__
    assert extra["org_id"] == "org-123"
    assert extra["feature"] == "test_feature"
    assert extra["model"] == "fake-echo"
    assert extra["prompt_id"] == "prompt-abc"
    assert extra["prompt_version"] == "v2"
    assert "input_tokens" in extra
    assert "output_tokens" in extra
    assert extra["cost_usd"] == "0"
    assert "latency_ms" in extra
    assert extra["outcome"] == "ok"

    # Ensure sentinel never appears in the log record
    assert sentinel not in str(record.__dict__)
    assert sentinel not in record.getMessage()


def test_gateway_cost_logging_no_message_text_error_path(caplog: pytest.LogCaptureFixture) -> None:
    """Done when: no message text logged on provider error path."""
    caplog.set_level(logging.INFO, logger="orsyn.ai.cost")

    sentinel = "SENTINEL-7f3a9c"
    provider = FakeProvider(fail_times=2)
    gateway = Gateway(provider)
    req = ModelRequest(
        org_id="test",
        feature="test",
        model="fake-echo",
        prompt_id="p",
        prompt_version="1",
        messages=[Message(role="user", content=sentinel)],
    )

    with pytest.raises(GatewayError):
        gateway.complete(req)

    # Check the error log record
    assert len(caplog.records) >= 1
    record = caplog.records[-1]
    assert record.__dict__["outcome"] == "error"
    assert sentinel not in str(record.__dict__)
    assert sentinel not in record.getMessage()


def test_gateway_cost_logging_no_message_text_timeout_path(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Done when: no message text logged on timeout path."""
    caplog.set_level(logging.INFO, logger="orsyn.ai.cost")

    sentinel = "SENTINEL-7f3a9c"
    provider = FakeProvider(delay_s=0.3)
    gateway = Gateway(provider)
    req = ModelRequest(
        org_id="test",
        feature="test",
        model="fake-echo",
        prompt_id="p",
        prompt_version="1",
        messages=[Message(role="user", content=sentinel)],
        timeout_s=0.05,
    )

    with pytest.raises(GatewayTimeoutError):
        gateway.complete(req)

    # Check the timeout log record
    assert len(caplog.records) >= 1
    record = caplog.records[-1]
    assert record.__dict__["outcome"] == "timeout"
    assert sentinel not in str(record.__dict__)
    assert sentinel not in record.getMessage()


def test_gateway_retry_success_on_second_attempt() -> None:
    """Done when: retry succeeds after first ProviderError, calls == 2."""
    provider = FakeProvider(fail_times=1)
    gateway = Gateway(provider)
    req = ModelRequest(
        org_id="test",
        feature="test",
        model="fake-echo",
        prompt_id="p",
        prompt_version="1",
        messages=[Message(role="user", content="hello")],
    )

    resp = gateway.complete(req)
    assert resp.text == "hello"
    assert provider.calls == 2


def test_gateway_retry_exhausts_and_fails(caplog: pytest.LogCaptureFixture) -> None:
    """Done when: retry exhausted raises GatewayError with calls == 2 and outcome logged."""
    caplog.set_level(logging.INFO, logger="orsyn.ai.cost")

    provider = FakeProvider(fail_times=2)
    gateway = Gateway(provider)
    req = ModelRequest(
        org_id="test",
        feature="test",
        model="fake-echo",
        prompt_id="p",
        prompt_version="1",
        messages=[Message(role="user", content="hello")],
    )

    with pytest.raises(GatewayError):
        gateway.complete(req)

    assert provider.calls == 2
    # Last log record should have outcome "error"
    assert caplog.records[-1].__dict__["outcome"] == "error"


def test_gateway_timeout_error(caplog: pytest.LogCaptureFixture) -> None:
    """Done when: timeout raises GatewayTimeoutError with calls == 2, outcome logged."""
    caplog.set_level(logging.INFO, logger="orsyn.ai.cost")

    provider = FakeProvider(delay_s=0.3)
    gateway = Gateway(provider)
    req = ModelRequest(
        org_id="test",
        feature="test",
        model="fake-echo",
        prompt_id="p",
        prompt_version="1",
        messages=[Message(role="user", content="hello")],
        timeout_s=0.05,
    )

    with pytest.raises(GatewayTimeoutError):
        gateway.complete(req)

    assert provider.calls == 2
    # Last log record should have outcome "timeout"
    assert caplog.records[-1].__dict__["outcome"] == "timeout"


def test_gateway_unpriced_model_early_failure() -> None:
    """Done when: unpriced model raises UnknownModelError, provider calls == 0."""
    provider = FakeProvider()
    gateway = Gateway(provider)
    req = ModelRequest(
        org_id="test",
        feature="test",
        model="unknown-model",
        prompt_id="p",
        prompt_version="1",
        messages=[Message(role="user", content="hello")],
    )

    with pytest.raises(UnknownModelError):
        gateway.complete(req)

    assert provider.calls == 0


def test_get_gateway_with_fake_provider() -> None:
    """Done when: get_gateway() with fake provider returns a Gateway."""
    settings = Settings(_env_file=None, ai_provider="fake")  # type: ignore[call-arg]
    gateway = get_gateway(settings)
    assert isinstance(gateway, Gateway)


def test_get_gateway_invalid_provider() -> None:
    """Done when: get_gateway() with unsupported provider raises GatewayError."""
    settings = Settings.model_construct(ai_provider="openai")
    with pytest.raises(GatewayError) as exc_info:
        get_gateway(settings)
    assert "unsupported ai_provider" in str(exc_info.value)
