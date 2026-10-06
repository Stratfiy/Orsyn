"""Format validators for Indian business identifiers (KYC plan section 1.3).

Pure functions. Invalid input never raises: every validator returns a
``ValidationResult``. These run before any paid provider call, so they only prove
that a value is well formed, never that it is real or active.

Aadhaar numbers are never accepted in any field (plan section 1.4): every validator
rejects Aadhaar-shaped input first, and ``contains_aadhaar_shaped`` scans free text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum


class IdError(StrEnum):
    EMPTY = "empty"
    BAD_FORMAT = "bad_format"
    BAD_CHECK_DIGIT = "bad_check_digit"
    BAD_STATE_CODE = "bad_state_code"
    BAD_ENTITY_TYPE = "bad_entity_type"
    AADHAAR_REJECTED = "aadhaar_rejected"
    NON_ASCII = "non_ascii"


@dataclass(frozen=True, slots=True)
class ValidationResult:
    valid: bool
    # Normalised (trimmed, upper-case) value when valid. Excluded from repr so an
    # identifier never lands in logs or tracebacks through the dataclass repr.
    value: str | None = field(default=None, repr=False)
    error: IdError | None = None


# Every pattern is compiled with re.ASCII so \d and character classes never match
# non-ASCII digits (e.g. Devanagari) that int() or downstream systems might accept.
_A = re.ASCII

# Longest accepted identifier after strip (CIN is 21, Udyam 19; 32 leaves headroom).
MAX_ID_LEN = 32

_AADHAAR_EXACT = re.compile(r"\d{4}[ \t-]?\d{4}[ \t-]?\d{4}", _A)
_AADHAAR_IN_TEXT = re.compile(r"(?<!\d)\d{4}[ \t-]?\d{4}[ \t-]?\d{4}(?!\d)", _A)


def is_aadhaar_shaped(value: str) -> bool:
    """True for exactly 12 digits, with or without spaces/hyphens in groups of four."""
    v = value.strip()
    return bool(_AADHAAR_EXACT.fullmatch(v)) or (len(v) == 12 and v.isascii() and v.isdigit())


def contains_aadhaar_shaped(text: str) -> bool:
    """True if free text contains an Aadhaar-shaped run of digits anywhere."""
    return bool(_AADHAAR_IN_TEXT.search(text))


def _prepare(raw: str) -> tuple[str, ValidationResult | None]:
    value = raw.strip()
    if len(value) > MAX_ID_LEN:  # before any other work, so huge input costs nothing
        return value, ValidationResult(False, error=IdError.BAD_FORMAT)
    if not value.isascii():  # checked before upper(), which can change non-ASCII length
        return value, ValidationResult(False, error=IdError.NON_ASCII)
    value = value.upper()
    if not value:
        return value, ValidationResult(False, error=IdError.EMPTY)
    if is_aadhaar_shaped(value):
        return value, ValidationResult(False, error=IdError.AADHAAR_REJECTED)
    return value, None


def _match(pattern: re.Pattern[str], raw: str) -> ValidationResult:
    value, early = _prepare(raw)
    if early is not None:
        return early
    if not pattern.fullmatch(value):
        return ValidationResult(False, error=IdError.BAD_FORMAT)
    return ValidationResult(True, value)


# --- GSTIN -------------------------------------------------------------------
# Layout: SS PPPPPPPPPP E Z C  (state code, PAN, entity number, 'Z', check digit).
_GSTIN_RE = re.compile(r"\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]", _A)
_GSTIN_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"

# State/UT codes in use: 01-38, plus 97 (other territory) and 99 (centre jurisdiction).
_VALID_STATE_CODES = frozenset({f"{n:02d}" for n in range(1, 39)} | {"97", "99"})


def gstin_check_digit(first14: str) -> str:
    """GSTN check character for the first 14 characters of a GSTIN.

    Algorithm reference: the GSTN mod-36 scheme (a Luhn-mod-N variant over the
    alphabet 0-9A-Z, code points 0..35), as in the GST Common Portal GSTIN
    validation logic. For each of the 14 characters from the left (index i from 0):
      factor = 1 if i is even else 2
      p      = code_point * factor
      term   = p // 36 + p % 36
    check = (36 - (sum of terms) % 36) % 36, mapped back to the alphabet.
    """
    total = 0
    for i, ch in enumerate(first14):
        p = _GSTIN_ALPHABET.index(ch) * (1 if i % 2 == 0 else 2)
        total += p // 36 + p % 36
    return _GSTIN_ALPHABET[(36 - total % 36) % 36]


def validate_gstin(raw: str) -> ValidationResult:
    value, early = _prepare(raw)
    if early is not None:
        return early
    if not _GSTIN_RE.fullmatch(value):
        return ValidationResult(False, error=IdError.BAD_FORMAT)
    if value[:2] not in _VALID_STATE_CODES:
        return ValidationResult(False, error=IdError.BAD_STATE_CODE)
    if gstin_check_digit(value[:14]) != value[14]:
        return ValidationResult(False, error=IdError.BAD_CHECK_DIGIT)
    return ValidationResult(True, value)


def gstin_state_code(gstin: str) -> str | None:
    """Characters 1-2 of a valid GSTIN, else None."""
    r = validate_gstin(gstin)
    return r.value[:2] if r.value else None


def gstin_pan(gstin: str) -> str | None:
    """Characters 3-12 of a valid GSTIN (the holder's PAN), else None."""
    r = validate_gstin(gstin)
    return r.value[2:12] if r.value else None


# --- PAN ---------------------------------------------------------------------
_PAN_RE = re.compile(r"[A-Z]{5}[0-9]{4}[A-Z]", _A)

PAN_ENTITY_TYPES: dict[str, str] = {
    "P": "individual",
    "C": "company",
    "H": "huf",
    "F": "firm",
    "A": "association_of_persons",
    "T": "trust",
    "B": "body_of_individuals",
    "L": "local_authority",
    "J": "artificial_juridical_person",
    "G": "government",
}


def validate_pan(raw: str) -> ValidationResult:
    r = _match(_PAN_RE, raw)
    if r.value is not None and r.value[3] not in PAN_ENTITY_TYPES:
        return ValidationResult(False, error=IdError.BAD_ENTITY_TYPE)
    return r


def pan_entity_type(pan: str) -> str | None:
    """Entity type from the 4th character of a valid PAN (e.g. 'company'), else None."""
    r = validate_pan(pan)
    return PAN_ENTITY_TYPES[r.value[3]] if r.value else None


# --- Other identifiers -------------------------------------------------------
_IFSC_RE = re.compile(r"[A-Z]{4}0[A-Z0-9]{6}", _A)
_UDYAM_RE = re.compile(r"UDYAM-[A-Z]{2}-\d{2}-\d{7}", _A)
_CIN_RE = re.compile(r"[LU]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6}", _A)
_LLPIN_RE = re.compile(r"[A-Z]{3}-\d{4}", _A)
_IEC_RE = re.compile(r"[A-Z0-9]{10}", _A)


def validate_ifsc(raw: str) -> ValidationResult:
    return _match(_IFSC_RE, raw)


def validate_udyam(raw: str) -> ValidationResult:
    return _match(_UDYAM_RE, raw)


def validate_cin(raw: str) -> ValidationResult:
    return _match(_CIN_RE, raw)


def validate_llpin(raw: str) -> ValidationResult:
    return _match(_LLPIN_RE, raw)


def validate_iec(raw: str) -> ValidationResult:
    return _match(_IEC_RE, raw)
