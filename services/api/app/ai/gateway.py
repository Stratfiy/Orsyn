"""The only path to a model.

Providers (fake now; Bedrock and Sarvam later) implement `ModelProvider`. The gateway adds a
timeout, exactly one retry on `ProviderError`, cost computed in code, and one structured log
record per call on logger `orsyn.ai.cost`. The record never contains message text.
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from decimal import Decimal
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from app.settings import Settings, get_settings

cost_logger = logging.getLogger("orsyn.ai.cost")

_PER_MILLION = Decimal(1_000_000)

# (input, output) USD per 1M tokens. Real models are added with their provider.
PRICES: dict[str, tuple[Decimal, Decimal]] = {
    "fake-echo": (Decimal(0), Decimal(0)),
}


class GatewayError(Exception):
    """Typed failure returned by the gateway after retries."""


class UnknownModelError(GatewayError):
    """The model has no entry in PRICES, so its cost cannot be computed."""


class GatewayTimeoutError(GatewayError):
    """The provider did not answer within `timeout_s` on both attempts."""


class ProviderError(Exception):
    """Raised by a provider for a retryable failure."""


class Message(BaseModel):
    model_config = ConfigDict(frozen=True)

    role: Literal["system", "user", "assistant"]
    content: str


class ModelRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    org_id: str
    feature: str
    model: str
    prompt_id: str
    prompt_version: str
    messages: list[Message]
    max_tokens: int = Field(default=1024, gt=0)
    timeout_s: float = Field(default=30.0, gt=0)


class ProviderResult(BaseModel):
    text: str
    model: str
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)


class ModelResponse(BaseModel):
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal
    latency_ms: int


class ModelProvider(Protocol):
    def complete(self, req: ModelRequest) -> ProviderResult: ...


def compute_cost(model: str, input_tokens: int, output_tokens: int) -> Decimal:
    try:
        price_in, price_out = PRICES[model]
    except KeyError:
        raise UnknownModelError(f"no price for model {model!r}") from None
    return (price_in * input_tokens + price_out * output_tokens) / _PER_MILLION


class Gateway:
    def __init__(self, provider: ModelProvider) -> None:
        self._provider = provider

    def complete(self, req: ModelRequest) -> ModelResponse:
        started = time.monotonic()
        try:
            compute_cost(req.model, 0, 0)  # fail early on an unpriced model
            result = self._call_with_retry(req)
            cost = compute_cost(req.model, result.input_tokens, result.output_tokens)
        except GatewayTimeoutError:
            self._log(req, "timeout", 0, 0, Decimal(0), started)
            raise
        except GatewayError:
            self._log(req, "error", 0, 0, Decimal(0), started)
            raise
        latency_ms = self._log(req, "ok", result.input_tokens, result.output_tokens, cost, started)
        return ModelResponse(
            text=result.text,
            model=req.model,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            cost_usd=cost,
            latency_ms=latency_ms,
        )

    def _call_with_retry(self, req: ModelRequest) -> ProviderResult:
        last: ProviderError | None = None
        timed_out = False
        for _attempt in range(2):
            try:
                return self._call_once(req)
            except FutureTimeout:
                timed_out = True
                last = None
            except ProviderError as exc:
                timed_out = False
                last = exc
        if timed_out:
            raise GatewayTimeoutError(f"no answer within {req.timeout_s}s") from None
        raise GatewayError("provider failed after retry") from last

    def _call_once(self, req: ModelRequest) -> ProviderResult:
        pool = ThreadPoolExecutor(max_workers=1)
        try:
            return pool.submit(self._provider.complete, req).result(timeout=req.timeout_s)
        finally:
            pool.shutdown(wait=False, cancel_futures=True)

    @staticmethod
    def _log(
        req: ModelRequest,
        outcome: str,
        input_tokens: int,
        output_tokens: int,
        cost: Decimal,
        started: float,
    ) -> int:
        latency_ms = int((time.monotonic() - started) * 1000)
        cost_logger.info(
            "ai_call",
            extra={
                "org_id": req.org_id,
                "feature": req.feature,
                "model": req.model,
                "prompt_id": req.prompt_id,
                "prompt_version": req.prompt_version,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_usd": str(cost),
                "latency_ms": latency_ms,
                "outcome": outcome,
            },
        )
        return latency_ms


def get_gateway(settings: Settings | None = None) -> Gateway:
    settings = settings or get_settings()
    if settings.ai_provider == "fake":
        from app.ai.fake_provider import FakeProvider

        return Gateway(FakeProvider())
    raise GatewayError(f"unsupported ai_provider {settings.ai_provider!r}")
