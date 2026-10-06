"""Routes a check to its provider, validates format first, logs one record per check.

The log record (logger "orsyn.kyc.check") carries check_type, provider, outcome, latency_ms and
provider_ref. It never carries the identifier or any name: only a masked form of the validated
value (last 3 chars for GSTIN, else 4).
"""

import logging
import time
from collections.abc import Callable, Mapping

from app.ai.tools.verification.base import (
    CinResult,
    GstinResult,
    IecResult,
    InvalidInput,
    NameMatchResult,
    NotFound,
    PanResult,
    ProviderUnavailable,
    UdyamResult,
    VerificationProvider,
)
from app.ai.tools.verification.fake import FakeVerificationProvider
from app.ai.tools.verification.routing import provider_name_for
from app.modules.verification.policy import CheckType
from app.modules.verification.validators import (
    ValidationResult,
    contains_aadhaar_shaped,
    validate_cin,
    validate_gstin,
    validate_iec,
    validate_pan,
    validate_udyam,
)
from app.settings import Settings, get_settings

check_logger = logging.getLogger("orsyn.kyc.check")

Validator = Callable[[str], ValidationResult]

_VALIDATORS: dict[CheckType, Validator] = {
    CheckType.GSTIN: validate_gstin,
    CheckType.PAN: validate_pan,
    CheckType.UDYAM: validate_udyam,
    CheckType.IEC: validate_iec,
    CheckType.CIN: validate_cin,
}


def mask_identifier(check: CheckType, value: str) -> str:
    """Mask a validated, normalised identifier. GSTIN keeps 3 chars (its 12th is the PAN's last),
    everything else keeps 4. Values too short to hide anything are fully masked."""
    keep = 3 if check is CheckType.GSTIN else 4
    return f"****{value[-keep:]}" if len(value) > 2 * keep else "****"


# Provider name to adapter CLASS. The factory constructs the adapter, so a caller cannot hand a
# real adapter in under the "fake" name.
_ADAPTERS: dict[str, Callable[[], VerificationProvider]] = {"fake": FakeVerificationProvider}


def build_verification_client(settings: Settings | None = None) -> "VerificationClient":
    settings = settings or get_settings()
    name = settings.verification_provider
    if settings.env == "prod" and name == "fake":
        raise RuntimeError("fake verification provider is not allowed in prod")
    return VerificationClient({name: _ADAPTERS[name]()})


class VerificationClient:
    def __init__(self, providers: Mapping[str, VerificationProvider]) -> None:
        self._providers = providers

    @staticmethod
    def _validate(check: CheckType, value: str) -> str:
        result = _VALIDATORS[check](value)
        if not result.valid or result.value is None:
            reason = result.error.value if result.error is not None else "invalid"
            raise InvalidInput(check.value, reason)
        return result.value

    def _run[R](
        self,
        check: CheckType,
        identifier: str | None,
        call: Callable[[VerificationProvider, str | None], R],
        free_text: tuple[str, ...] = (),
    ) -> R:
        provider_name = provider_name_for(check)
        started = time.monotonic()
        outcome = "ok"
        provider_ref: str | None = None
        masked: str | None = None
        try:
            for text in free_text:
                if contains_aadhaar_shaped(text):
                    raise InvalidInput("name", "aadhaar_rejected")
            clean = self._validate(check, identifier) if identifier is not None else None
            if clean is not None:
                masked = mask_identifier(check, clean)
            result = call(self._providers[provider_name], clean)
            provider_ref = getattr(result, "provider_ref", None)
            return result
        except InvalidInput:
            outcome = "invalid_input"
            raise
        except NotFound:
            outcome = "not_found"
            raise
        except ProviderUnavailable as exc:
            outcome = exc.code
            raise
        except Exception:
            outcome = "error"
            raise ProviderUnavailable("provider_down") from None
        finally:
            check_logger.info(
                "kyc_check",
                extra={
                    "check_type": check.value,
                    "provider": provider_name,
                    "outcome": outcome,
                    "latency_ms": int((time.monotonic() - started) * 1000),
                    "provider_ref": provider_ref,
                    "input_masked": masked,
                },
            )

    def gstin(self, gstin: str) -> GstinResult:
        return self._run(CheckType.GSTIN, gstin, lambda p, v: p.gstin(_req(v)))

    def pan(self, pan: str, name: str | None = None) -> PanResult:
        return self._run(
            CheckType.PAN, pan, lambda p, v: p.pan(_req(v), name), free_text=(name,) if name else ()
        )

    def name_match(self, name_a: str, name_b: str) -> NameMatchResult:
        return self._run(
            CheckType.NAME_MATCH,
            None,
            lambda p, _v: p.name_match(name_a, name_b),
            free_text=(name_a, name_b),
        )

    def udyam(self, udyam: str) -> UdyamResult:
        return self._run(CheckType.UDYAM, udyam, lambda p, v: p.udyam(_req(v)))

    def iec(self, iec: str) -> IecResult:
        return self._run(CheckType.IEC, iec, lambda p, v: p.iec(_req(v)))

    def cin(self, cin: str) -> CinResult:
        return self._run(CheckType.CIN, cin, lambda p, v: p.cin(_req(v)))


def _req(value: str | None) -> str:
    assert value is not None  # noqa: S101 - callers always pass an identifier
    return value
