"""Deterministic provider for dev and CI. No network, no secrets, no real-looking personal data.

Rules, all derived from the input:
- GSTIN / Udyam / IEC / CIN ending in "0": inactive state (GSTIN: Cancelled).
- Any identifier ending in "9": NotFound.
- Everything else: active, with a synthetic name like "TESTCO KQXM ENTERPRISES".
- PAN is valid unless it ends in "9" (NotFound) or "0" (invalid).
- name_match uses app.modules.verification.names.match_names (score 0-1 stored as 0-100).
Flags: `unavailable` raises ProviderUnavailable("provider_down"), `timeout` raises
("timeout"), `include_contact_fields` makes the raw payload carry synthetic contact fields so
tests can prove the normaliser drops them.
"""

import hashlib
import hmac
import json
from typing import Any

from app.ai.tools.verification.base import (
    CinResult,
    DirectorOrPartner,
    GstinResult,
    IecResult,
    NameMatchResult,
    NotFound,
    PanResult,
    ProviderUnavailable,
    UdyamResult,
    allow_list,
)
from app.modules.verification.names import match_names
from app.modules.verification.policy import CheckType

_FAKE_KEY = b"orsyn-fake-verification-test-key"  # constant, test-only

_CONTACTS: dict[str, Any] = {
    "email": "nobody@example.invalid",
    "mobile": "0000000000",
    "phone": "0000000000",
    "website": "https://example.invalid",
    "address_of_individual": "synthetic",
}


def _fake_name(value: str) -> str:
    digest = hashlib.sha256(value.encode()).digest()
    letters = "".join(chr(ord("A") + b % 26) for b in digest[:4])
    return f"TESTCO {letters} ENTERPRISES"


class FakeVerificationProvider:
    name = "fake"

    def __init__(
        self,
        *,
        unavailable: bool = False,
        timeout: bool = False,
        include_contact_fields: bool = False,
    ) -> None:
        self._unavailable = unavailable
        self._timeout = timeout
        self._contacts = include_contact_fields

    def _gate(self, value: str) -> None:
        if self._timeout:
            raise ProviderUnavailable("timeout")
        if self._unavailable:
            raise ProviderUnavailable("provider_down")
        if value.endswith("9"):
            raise NotFound()

    def _raw(
        self, check: str, value: str, fields: dict[str, Any]
    ) -> tuple[dict[str, Any], str, str]:
        raw = {**fields, **(_CONTACTS if self._contacts else {})}
        # Test-only: an input-derived HMAC under a constant key. Real adapters must use the vendor's
        # own reference id for provider_ref and the hash of the raw response bytes, never a hash
        # of the input (a hash of an identifier is itself an identifier).
        payload = json.dumps({"c": check, "i": value, "r": raw}, sort_keys=True).encode()
        digest = hmac.new(_FAKE_KEY, payload, hashlib.sha256).hexdigest()
        return raw, f"fake-{digest[:12]}", digest

    def gstin(self, gstin: str) -> GstinResult:
        self._gate(gstin)
        cancelled = gstin.endswith("0")
        name = _fake_name(gstin)
        raw, ref, digest = self._raw(
            "gstin",
            gstin,
            {
                "gstin_status": "cancelled" if cancelled else "active",
                "legal_name": name,
                "trade_name": name,
                "constitution": "Private Limited Company",
                "taxpayer_type": "Regular",
                "registration_date": "2020-01-01",
                "cancellation_date": "2024-01-01" if cancelled else None,
                "state_code": gstin[:2],
                "nature_of_business": ["Factory / Manufacturing"],
                "pan_segment_matches": True,
            },
        )
        return GstinResult(
            status=raw["gstin_status"],
            provider_ref=ref,
            response_sha256=digest,
            **_without(allow_list(raw, CheckType.GSTIN), "gstin_status"),
        )

    def pan(self, pan: str, name: str | None = None) -> PanResult:
        self._gate(pan)
        valid = not pan.endswith("0")
        synthetic = _fake_name(pan)
        level = None
        if name is not None:
            level = match_names(name, synthetic).level.value
        raw, ref, digest = self._raw(
            "pan",
            pan,
            {
                "pan_status": "valid" if valid else "invalid",
                "name_on_pan_normalised": synthetic.lower() if valid else None,
                "entity_type": "company" if pan[3:4] == "C" else "other",
                "name_match": level,
            },
        )
        return PanResult(
            status=raw["pan_status"],
            provider_ref=ref,
            response_sha256=digest,
            **_without(allow_list(raw, CheckType.PAN), "pan_status"),
        )

    def name_match(self, name_a: str, name_b: str) -> NameMatchResult:
        if self._timeout:
            raise ProviderUnavailable("timeout")
        if self._unavailable:
            raise ProviderUnavailable("provider_down")
        match = match_names(name_a, name_b)
        raw, ref, digest = self._raw(
            "name_match",
            "|".join(sorted([name_a, name_b])),
            {"name_match": match.level.value, "name_match_score": round(match.score * 100)},
        )
        return NameMatchResult(
            provider_ref=ref, response_sha256=digest, **allow_list(raw, CheckType.NAME_MATCH)
        )

    def udyam(self, udyam: str) -> UdyamResult:
        self._gate(udyam)
        raw, ref, digest = self._raw(
            "udyam",
            udyam,
            {
                "udyam_status": "inactive" if udyam.endswith("0") else "active",
                "enterprise_name": _fake_name(udyam),
                "category": "Small",
                "category_year": "2024-25",
                "major_activity": "Manufacturing",
                "nic_codes": ["25910"],
            },
        )
        return UdyamResult(
            status=raw["udyam_status"],
            provider_ref=ref,
            response_sha256=digest,
            **_without(allow_list(raw, CheckType.UDYAM), "udyam_status"),
        )

    def iec(self, iec: str) -> IecResult:
        self._gate(iec)
        raw, ref, digest = self._raw(
            "iec",
            iec,
            {
                "iec_status": "inactive" if iec.endswith("0") else "active",
                "firm_name": _fake_name(iec),
                "pan_matches": True,
                "last_updated_on": "2025-06-01",
            },
        )
        return IecResult(
            status=raw["iec_status"],
            provider_ref=ref,
            response_sha256=digest,
            **_without(allow_list(raw, CheckType.IEC), "iec_status"),
        )

    def cin(self, cin: str) -> CinResult:
        self._gate(cin)
        raw, ref, digest = self._raw(
            "cin",
            cin,
            {
                "company_status": "inactive" if cin.endswith("0") else "active",
                "name": _fake_name(cin),
                "incorporation_date": "2015-04-01",
                "class": "Private",
                "directors_or_partners": [
                    {"name_normalised": "test director one", "din_masked": "0000****"}
                ],
            },
        )
        kept = allow_list(raw, CheckType.CIN)
        return CinResult(
            status=kept["company_status"],
            name=kept.get("name"),
            incorporation_date=kept.get("incorporation_date"),
            company_class=kept.get("class"),
            directors_or_partners=[DirectorOrPartner(**d) for d in kept["directors_or_partners"]],
            provider_ref=ref,
            response_sha256=digest,
        )


def _without(d: dict[str, Any], *keys: str) -> dict[str, Any]:
    return {k: v for k, v in d.items() if k not in keys}
