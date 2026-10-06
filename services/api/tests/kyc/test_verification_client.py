"""VerificationClient, fake provider and allow-list (KYC plan section 2). Synthetic ids only."""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from typing import Any

import pytest
from pydantic import ValidationError

from app.ai.tools.verification.base import (
    CinResult,
    DirectorOrPartner,
    GstinResult,
    InvalidInput,
    NotFound,
    PanResult,
    ProviderUnavailable,
    allow_list,
)
from app.ai.tools.verification.client import (
    VerificationClient,
    build_verification_client,
    mask_identifier,
)
from app.ai.tools.verification.fake import FakeVerificationProvider
from app.modules.verification.policy import CheckType
from app.modules.verification.validators import (
    gstin_check_digit,
    validate_cin,
    validate_gstin,
    validate_iec,
    validate_pan,
    validate_udyam,
)
from app.settings import Settings

GSTIN = "27AAAPL1234C1ZE"
PAN = "AAAPL1234C"
IEC = "ABCDE12345"
CIN = "U12345MH2020PTC123456"
UDYAM = "UDYAM-MH-01-1234567"
AADHAAR_NAME = "1234 5678 9012"

CONTACT_WORDS = ("phone", "email", "mobile", "website", "address")


class Spy:
    """Wraps a provider and counts calls without changing behaviour."""

    def __init__(self, inner: Any) -> None:
        self.inner = inner
        self.calls: list[str] = []

    def __getattr__(self, name: str) -> Any:
        target = getattr(self.inner, name)

        def call(*a: Any, **kw: Any) -> Any:
            self.calls.append(name)
            return target(*a, **kw)

        return call


class Exploding:
    """Provider whose every method raises a generic error carrying the input."""

    def __getattr__(self, name: str) -> Any:
        def call(*a: Any, **kw: Any) -> Any:
            raise RuntimeError(f"boom {a!r}")

        return call


def client_for(provider: Any) -> VerificationClient:
    return VerificationClient({"fake": provider})


def gstin_with_last(digit: str) -> str:
    """A format- and checksum-valid synthetic GSTIN whose check character is `digit`."""
    for entity in "123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        first14 = f"27AAAPL1234C{entity}Z"
        if gstin_check_digit(first14) == digit:
            gstin = first14 + digit
            assert validate_gstin(gstin).valid
            return gstin
    raise AssertionError("no synthetic GSTIN found")


def walk(obj: Any) -> Iterator[tuple[str | None, Any]]:
    """Yield (key, value) pairs for every node of a nested dict/list."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k, v
            yield from walk(v)
    elif isinstance(obj, list | tuple):
        for v in obj:
            yield None, v
            yield from walk(v)


def check_records(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == "orsyn.kyc.check"]


def test_synthetic_identifiers_are_format_valid() -> None:
    assert validate_gstin(GSTIN).valid
    assert validate_pan(PAN).valid
    assert validate_iec(IEC).valid
    assert validate_cin(CIN).valid
    assert validate_udyam(UDYAM).valid


# --- happy path --------------------------------------------------------------


def test_valid_gstin_active_with_provider_ref_and_hash() -> None:
    result = client_for(FakeVerificationProvider()).gstin(GSTIN)
    assert result.status == "active"
    assert re.fullmatch(r"fake-[0-9a-f]{12}", result.provider_ref)
    assert re.fullmatch(r"[0-9a-f]{64}", result.response_sha256)
    assert result.state_code == "27"


def test_gstin_input_is_normalised_before_provider() -> None:
    result = client_for(FakeVerificationProvider()).gstin(f"  {GSTIN.lower()} ")
    assert result.status == "active"


# --- invalid input -----------------------------------------------------------


def test_invalid_format_raises_without_calling_provider() -> None:
    spy = Spy(FakeVerificationProvider())
    bad = "SECRETBAD123"
    with pytest.raises(InvalidInput) as ei:
        client_for(spy).gstin(bad)
    assert ei.value.check == "gstin"
    assert ei.value.reason == "bad_format"
    assert spy.calls == []
    assert bad not in str(ei.value)
    assert bad not in repr(ei.value)


def test_bad_check_digit_is_invalid_input() -> None:
    wrong = GSTIN[:-1] + ("F" if GSTIN[-1] != "F" else "G")
    spy = Spy(FakeVerificationProvider())
    with pytest.raises(InvalidInput) as ei:
        client_for(spy).gstin(wrong)
    assert ei.value.reason == "bad_check_digit"
    assert spy.calls == []


# --- contacts (rule 5) -------------------------------------------------------


def _all_results(client: VerificationClient) -> list[Any]:
    return [
        client.gstin(GSTIN),
        client.pan(PAN, name="Testco"),
        client.name_match("Testco One", "Testco One Pvt Ltd"),
        client.udyam(UDYAM),
        client.iec(IEC),
        client.cin(CIN),
    ]


def test_contact_fields_dropped_from_every_result() -> None:
    client = client_for(FakeVerificationProvider(include_contact_fields=True))
    for result in _all_results(client):
        dumped = result.model_dump()
        for key, value in walk(dumped):
            if key is not None:
                assert not any(w in key.lower() for w in CONTACT_WORDS), key
            if isinstance(value, str):
                assert "example.invalid" not in value
                assert "nobody@" not in value
        assert "example.invalid" not in repr(result)


# --- allow_list fails closed -------------------------------------------------


def test_allow_list_drops_dict_where_scalar_expected() -> None:
    kept = allow_list(
        {"legal_name": {"email": "a@b.invalid"}, "constitution": "X"}, CheckType.GSTIN
    )
    assert kept == {"constitution": "X"}


def test_allow_list_drops_dict_inside_plain_list() -> None:
    raw = {"nature_of_business": [{"phone": "1"}], "taxpayer_type": "Regular"}
    kept = allow_list(raw, CheckType.GSTIN)
    assert "nature_of_business" not in kept
    assert kept == {"taxpayer_type": "Regular"}


def test_allow_list_keeps_plain_list_of_scalars() -> None:
    kept = allow_list({"nature_of_business": ["a", "b"]}, CheckType.GSTIN)
    assert kept == {"nature_of_business": ["a", "b"]}


def test_allow_list_drops_dict_instead_of_directors_list() -> None:
    raw = {"directors_or_partners": {"name_normalised": "x", "email": "a@b.invalid"}}
    assert allow_list(raw, CheckType.CIN) == {}


def test_allow_list_drops_email_key_inside_director_item() -> None:
    raw = {
        "directors_or_partners": [
            {"name_normalised": "test director", "din_masked": "0000****", "email": "a@b.invalid"}
        ]
    }
    kept = allow_list(raw, CheckType.CIN)
    assert kept == {
        "directors_or_partners": [{"name_normalised": "test director", "din_masked": "0000****"}]
    }


def test_allow_list_drops_non_scalar_inside_director_item_and_non_mapping_items() -> None:
    raw = {"directors_or_partners": [{"name_normalised": {"phone": "1"}}, "stray", 5]}
    assert allow_list(raw, CheckType.CIN) == {"directors_or_partners": [{}]}


def test_allow_list_drops_unlisted_top_level_contact_keys() -> None:
    raw = {
        "email": "a",
        "phone": "b",
        "mobile": "c",
        "website": "d",
        "address": "e",
        "state_code": "27",
    }
    assert allow_list(raw, CheckType.GSTIN) == {"state_code": "27"}


# --- logging -----------------------------------------------------------------


def _flat(record: logging.LogRecord) -> list[str]:
    return [record.getMessage(), *(str(v) for v in record.__dict__.values())]


def _assert_absent(record: logging.LogRecord, *secrets: str) -> None:
    for text in _flat(record):
        for secret in secrets:
            assert secret not in text


def test_log_one_record_ok(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="orsyn.kyc.check")
    result = client_for(FakeVerificationProvider()).gstin(GSTIN)
    recs = check_records(caplog)
    assert len(recs) == 1
    r = recs[0]
    assert r.outcome == "ok"  # type: ignore[attr-defined]
    assert r.check_type == "gstin"  # type: ignore[attr-defined]
    assert r.provider == "fake"  # type: ignore[attr-defined]
    assert r.provider_ref == result.provider_ref  # type: ignore[attr-defined]
    assert r.input_masked == mask_identifier(CheckType.GSTIN, GSTIN)  # type: ignore[attr-defined]
    _assert_absent(r, GSTIN, GSTIN[:12])


def test_log_masks_gstin_to_last_three_and_pan_to_last_four(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="orsyn.kyc.check")
    c = client_for(FakeVerificationProvider())
    c.gstin(GSTIN)
    c.pan(PAN)
    g, p = check_records(caplog)
    assert g.input_masked == "****" + GSTIN[-3:]  # type: ignore[attr-defined]
    assert p.input_masked == "****" + PAN[-4:]  # type: ignore[attr-defined]
    assert mask_identifier(CheckType.GSTIN, GSTIN) == "****" + GSTIN[-3:]
    assert mask_identifier(CheckType.PAN, PAN) == "****" + PAN[-4:]
    _assert_absent(p, PAN)


def test_log_invalid_input(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="orsyn.kyc.check")
    spy = Spy(FakeVerificationProvider())
    bad = "SECRETBAD123"
    with pytest.raises(InvalidInput):
        client_for(spy).gstin(bad)
    (r,) = check_records(caplog)
    assert r.outcome == "invalid_input"  # type: ignore[attr-defined]
    assert r.input_masked is None  # type: ignore[attr-defined]
    _assert_absent(r, bad)


def test_log_not_found(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="orsyn.kyc.check")
    gstin = gstin_with_last("9")
    with pytest.raises(NotFound):
        client_for(FakeVerificationProvider()).gstin(gstin)
    (r,) = check_records(caplog)
    assert r.outcome == "not_found"  # type: ignore[attr-defined]
    _assert_absent(r, gstin)


@pytest.mark.parametrize(
    ("flags", "code"),
    [({"timeout": True}, "timeout"), ({"unavailable": True}, "provider_down")],
)
def test_unavailable_flags_raise_and_log(
    caplog: pytest.LogCaptureFixture, flags: dict[str, bool], code: str
) -> None:
    caplog.set_level(logging.INFO, logger="orsyn.kyc.check")
    with pytest.raises(ProviderUnavailable) as ei:
        client_for(FakeVerificationProvider(**flags)).gstin(GSTIN)
    assert ei.value.code == code
    (r,) = check_records(caplog)
    assert r.outcome == code  # type: ignore[attr-defined]
    _assert_absent(r, GSTIN)


@pytest.mark.parametrize(
    ("flags", "code"),
    [({"timeout": True}, "timeout"), ({"unavailable": True}, "provider_down")],
)
def test_unavailable_flags_apply_to_name_match(flags: dict[str, bool], code: str) -> None:
    with pytest.raises(ProviderUnavailable) as ei:
        client_for(FakeVerificationProvider(**flags)).name_match("a corp", "b corp")
    assert ei.value.code == code


def test_generic_error_becomes_provider_down_without_cause(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="orsyn.kyc.check")
    with pytest.raises(ProviderUnavailable) as ei:
        client_for(Exploding()).gstin(GSTIN)
    exc = ei.value
    assert exc.code == "provider_down"
    assert exc.__cause__ is None
    assert exc.__suppress_context__ is True
    assert GSTIN not in str(exc)
    (r,) = check_records(caplog)
    assert r.outcome == "error"  # type: ignore[attr-defined]
    _assert_absent(r, GSTIN, "boom")


# --- Aadhaar in free text ----------------------------------------------------


def test_aadhaar_shaped_name_rejected_for_pan(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="orsyn.kyc.check")
    spy = Spy(FakeVerificationProvider())
    with pytest.raises(InvalidInput) as ei:
        client_for(spy).pan(PAN, name=AADHAAR_NAME)
    assert ei.value.reason == "aadhaar_rejected"
    assert spy.calls == []
    (r,) = check_records(caplog)
    assert r.outcome == "invalid_input"  # type: ignore[attr-defined]
    _assert_absent(r, "1234", "5678", "9012")
    assert "1234" not in str(ei.value)


@pytest.mark.parametrize("which", [0, 1])
def test_aadhaar_shaped_name_rejected_for_name_match(
    caplog: pytest.LogCaptureFixture, which: int
) -> None:
    caplog.set_level(logging.INFO, logger="orsyn.kyc.check")
    spy = Spy(FakeVerificationProvider())
    names = ["Testco One", "Testco One"]
    names[which] = AADHAAR_NAME
    with pytest.raises(InvalidInput) as ei:
        client_for(spy).name_match(names[0], names[1])
    assert ei.value.reason == "aadhaar_rejected"
    assert spy.calls == []
    (r,) = check_records(caplog)
    _assert_absent(r, "1234", "5678", "9012")


# --- factory -----------------------------------------------------------------


def test_factory_builds_fake_client_in_local() -> None:
    client = build_verification_client(Settings(_env_file=None, env="local"))  # type: ignore[call-arg]
    assert isinstance(client, VerificationClient)
    assert client.gstin(GSTIN).status == "active"


def test_factory_refuses_fake_in_prod() -> None:
    # model_construct bypasses the Settings validator so the factory's own guard is exercised.
    prod = Settings.model_construct(
        env="prod",
        log_level="INFO",
        git_sha="abc",
        ai_provider="fake",
        verification_provider="fake",
    )
    with pytest.raises(RuntimeError, match="not allowed in prod"):
        build_verification_client(prod)


# --- no input echo from result models ---------------------------------------


def test_repr_of_results_hides_names() -> None:
    planted = "PLANTED NAME ZZ"
    g = GstinResult(
        status="active",
        provider_ref="fake-x",
        response_sha256="0" * 64,
        legal_name=planted,
        trade_name=planted,
    )
    p = PanResult(
        status="valid",
        provider_ref="fake-x",
        response_sha256="0" * 64,
        name_on_pan_normalised=planted,
    )
    c = CinResult(
        status="active",
        provider_ref="fake-x",
        response_sha256="0" * 64,
        name=planted,
        directors_or_partners=[DirectorOrPartner(name_normalised=planted)],
    )
    for obj in (g, p, c):
        assert planted not in repr(obj)
        assert planted.lower() not in repr(obj).lower()


def test_validation_error_text_hides_input() -> None:
    planted_name = "PLANTED NAME ZZ"
    planted_pan = "ZZZZZ9999Z"
    with pytest.raises(ValidationError) as ei:
        PanResult(
            status=planted_name,  # type: ignore[arg-type]
            provider_ref="r",
            response_sha256="h",
            name_on_pan_normalised=12345,  # type: ignore[arg-type]
            pan=planted_pan,  # type: ignore[call-arg]
        )
    text = str(ei.value)
    assert planted_name not in text
    assert planted_pan not in text
    with pytest.raises(ValidationError) as ei2:
        DirectorOrPartner(name_normalised=planted_name, extra_pan=planted_pan)  # type: ignore[call-arg]
    assert planted_name not in str(ei2.value)
    assert planted_pan not in str(ei2.value)


# --- fake suffix rules -------------------------------------------------------


def test_gstin_ending_zero_is_cancelled() -> None:
    gstin = gstin_with_last("0")
    result = client_for(FakeVerificationProvider()).gstin(gstin)
    assert result.status == "cancelled"
    assert result.cancellation_date is not None


def test_gstin_ending_nine_is_not_found() -> None:
    with pytest.raises(NotFound):
        client_for(FakeVerificationProvider()).gstin(gstin_with_last("9"))


def test_iec_suffix_rules() -> None:
    c = client_for(FakeVerificationProvider())
    assert c.iec("ABCDE12340").status == "inactive"
    with pytest.raises(NotFound):
        c.iec("ABCDE12349")


def test_cin_suffix_rules() -> None:
    c = client_for(FakeVerificationProvider())
    assert c.cin("U12345MH2020PTC123450").status == "inactive"
    with pytest.raises(NotFound):
        c.cin("U12345MH2020PTC123459")


def test_udyam_suffix_rules() -> None:
    c = client_for(FakeVerificationProvider())
    assert c.udyam("UDYAM-MH-01-1234560").status == "inactive"
    with pytest.raises(NotFound):
        c.udyam("UDYAM-MH-01-1234569")


def test_pan_format_makes_fake_suffix_rules_unreachable_through_client() -> None:
    """A format-valid PAN always ends in a letter, so the fake's 0/9 PAN rules cannot trigger."""
    assert not validate_pan("AAAPL12340").valid
    assert not validate_pan("AAAPL12349").valid
    with pytest.raises(InvalidInput):
        client_for(FakeVerificationProvider()).pan("AAAPL12349")


def test_pan_company_entity_type_and_name_match_level() -> None:
    c = client_for(FakeVerificationProvider())
    assert c.pan("AAACL1234C").entity_type == "company"
    assert c.pan(PAN).entity_type == "other"  # fake: only a 4th letter C maps to company
    assert c.pan(PAN, name="Totally Different Name").name_match == "low"
