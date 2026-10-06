"""Provider interface, normalised results and the allow-list normaliser.

Rule 5 (CLAUDE.md): contact details never enter the platform through a check. Providers return
whatever they like; `allow_list` keeps only the fields named in `ALLOWED_FIELDS` (plan
section 2.2.1) and drops everything else, including phone, email, mobile, website and the
address of any individual. Adapters must pass raw payloads through `allow_list` before building
a result. No raw response is stored; only `provider_ref` and `response_sha256` are kept.
"""

import hashlib
import json
from collections.abc import Mapping
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from app.modules.verification.policy import CheckType

MatchLevel = Literal["high", "medium", "low"]

ALLOWED_FIELDS: dict[CheckType, frozenset[str]] = {
    CheckType.GSTIN: frozenset(
        {
            "gstin_status",
            "legal_name",
            "trade_name",
            "constitution",
            "taxpayer_type",
            "registration_date",
            "cancellation_date",
            "state_code",
            "nature_of_business",
            "pan_segment_matches",
        }
    ),
    CheckType.PAN: frozenset({"pan_status", "name_on_pan_normalised", "entity_type", "name_match"}),
    CheckType.NAME_MATCH: frozenset({"name_match", "name_match_score"}),
    CheckType.UDYAM: frozenset(
        {
            "udyam_status",
            "enterprise_name",
            "category",
            "category_year",
            "major_activity",
            "nic_codes",
        }
    ),
    CheckType.IEC: frozenset({"iec_status", "firm_name", "pan_matches", "last_updated_on"}),
    CheckType.CIN: frozenset(
        {"company_status", "name", "incorporation_date", "class", "directors_or_partners"}
    ),
}

# Keys that hold a list of mappings; each mapping is filtered to these scalar keys.
_NESTED_ALLOWED: dict[str, frozenset[str]] = {
    "directors_or_partners": frozenset({"name_normalised", "din_masked"}),
}

_Scalar = str | int | bool | None


def _is_scalar(value: object) -> bool:
    return value is None or isinstance(value, str | int | bool)


def allow_list(raw: Mapping[str, Any], check: CheckType) -> dict[str, Any]:
    """Return only the allow-listed fields of `raw`, failing closed on type at every level.

    A key survives only if it is allowed AND its value has the expected shape: a scalar
    (str, int, bool, None), a list of scalars, or (for nested keys) a list of mappings whose
    allowed keys hold scalars. Anything else, including dicts where a scalar is expected, is
    dropped. Contact fields are therefore dropped by name and cannot ride along in a nested shape.
    """
    allowed = ALLOWED_FIELDS[check]
    kept: dict[str, Any] = {}
    for key, value in raw.items():
        if key not in allowed:
            continue
        nested = _NESTED_ALLOWED.get(key)
        if nested is not None:
            if isinstance(value, list):
                kept[key] = [
                    {k: v for k, v in item.items() if k in nested and _is_scalar(v)}
                    for item in value
                    if isinstance(item, Mapping)
                ]
            continue
        if isinstance(value, list):
            if all(_is_scalar(v) for v in value):
                kept[key] = list(value)
        elif _is_scalar(value):
            kept[key] = value
    return kept


def sha256_of(raw_bytes: bytes) -> str:
    return hashlib.sha256(raw_bytes).hexdigest()


def sha256_of_json(payload: Mapping[str, Any]) -> str:
    return sha256_of(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())


class VerificationError(Exception):
    """Base for typed verification failures. Messages are fixed: no free text, no input."""


class ProviderUnavailable(VerificationError):  # noqa: N818 - name fixed by the plan
    """Timeout or provider down. `code` maps to kyc_checks.error_code."""

    def __init__(self, code: Literal["timeout", "provider_down", "rate_limited"] = "provider_down"):
        super().__init__(code)
        self.code = code


class InvalidInput(VerificationError):  # noqa: N818
    """Format validation failed. `reason` is an enum value (e.g. IdError), never the input."""

    def __init__(self, check: str, reason: str) -> None:
        super().__init__(f"invalid {check}: {reason}")
        self.check = check
        self.reason = reason


class NotFound(VerificationError):  # noqa: N818
    """The register has no record for this identifier."""

    def __init__(self) -> None:
        super().__init__("not_found")


class _Result(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, hide_input_in_errors=True)

    provider_ref: str
    response_sha256: str

    def normalised(self) -> dict[str, Any]:
        """The fields we keep, from the typed model (not raw provider output)."""
        return self.model_dump(exclude={"provider_ref", "response_sha256"})


class GstinResult(_Result):
    status: Literal["active", "inactive", "cancelled", "suspended"]
    legal_name: str | None = Field(default=None, repr=False)
    trade_name: str | None = Field(default=None, repr=False)
    constitution: str | None = None
    taxpayer_type: str | None = None
    registration_date: str | None = None
    cancellation_date: str | None = None
    state_code: str | None = None
    nature_of_business: list[str] = []
    pan_segment_matches: bool | None = None


class PanResult(_Result):
    status: Literal["valid", "invalid"]
    name_on_pan_normalised: str | None = Field(default=None, repr=False)
    entity_type: str | None = None
    name_match: MatchLevel | None = None


class NameMatchResult(_Result):
    status: Literal["checked"] = "checked"
    name_match: MatchLevel
    name_match_score: int  # 0..100


class UdyamResult(_Result):
    status: Literal["active", "inactive"]
    enterprise_name: str | None = Field(default=None, repr=False)
    category: str | None = None
    category_year: str | None = None
    major_activity: str | None = None
    nic_codes: list[str] = []


class IecResult(_Result):
    status: Literal["active", "inactive"]
    firm_name: str | None = Field(default=None, repr=False)
    pan_matches: bool | None = None
    last_updated_on: str | None = None


class DirectorOrPartner(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, hide_input_in_errors=True)

    name_normalised: str = Field(repr=False)
    din_masked: str | None = None


class CinResult(_Result):
    status: Literal["active", "inactive", "struck_off"]
    name: str | None = Field(default=None, repr=False)
    incorporation_date: str | None = None
    company_class: str | None = None
    directors_or_partners: list[DirectorOrPartner] = []


class VerificationProvider(Protocol):
    """One method per check type. Implementations raise only the typed errors in this module."""

    def gstin(self, gstin: str) -> GstinResult: ...

    def pan(self, pan: str, name: str | None = None) -> PanResult: ...

    def name_match(self, name_a: str, name_b: str) -> NameMatchResult: ...

    def udyam(self, udyam: str) -> UdyamResult: ...

    def iec(self, iec: str) -> IecResult: ...

    def cin(self, cin: str) -> CinResult: ...
