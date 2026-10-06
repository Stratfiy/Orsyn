"""Badge policy (KYC plan section 1.2) as typed data, and badge computation.

Badges are computed on read from the latest decisive check per type; nothing is
stored. A badge disappears when a required check fails, expires or is missing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict


class CheckType(StrEnum):
    # GSTIN "pass" means the GSTN status is Active and the PAN segment of the GSTIN is
    # consistent with the PAN on file (adapter responsibility).
    GSTIN = "gstin"
    # The supplier's own confirmation of the legal name shown from GSTN (in-house action).
    LEGAL_NAME_CONFIRMED = "legal_name_confirmed"
    GST_FILING = "gst_filing"
    PAN = "pan"
    UDYAM = "udyam"
    IEC = "iec"
    CIN = "cin"
    LLPIN = "llpin"
    BANK_PENNY_DROP = "bank_penny_drop"
    BANK_REVERSE_PENNY_DROP = "bank_reverse_penny_drop"
    NAME_MATCH = "name_match"
    SIGNATORY = "signatory"
    SANCTIONS = "sanctions"
    DOMAIN = "domain"
    REGISTRY_DOC = "registry_doc"
    DUPLICATE = "duplicate"


class CheckOutcome(StrEnum):
    PASS = "pass"  # noqa: S105
    FAIL = "fail"
    MISMATCH = "mismatch"
    POTENTIAL_HIT = "potential_hit"
    NOT_FOUND = "not_found"
    ERROR = "error"
    PENDING = "pending"


# ERROR and PENDING are not verdicts: they never override an earlier verdict, so a
# provider outage on a re-check does not drop a badge before its own expiry.
_DECISIVE = frozenset(
    {
        CheckOutcome.PASS,
        CheckOutcome.FAIL,
        CheckOutcome.MISMATCH,
        CheckOutcome.POTENTIAL_HIT,
        CheckOutcome.NOT_FOUND,
    }
)

# Re-check intervals: plan section 12 Q2 proposal. PENDING FOUNDER CONFIRMATION.
RECHECK_GSTIN = timedelta(days=30)  # monthly; pending founder confirmation
RECHECK_PAN = timedelta(days=365)  # yearly; pending founder confirmation
RECHECK_IEC = timedelta(days=365)  # yearly; pending founder confirmation
RECHECK_UDYAM = timedelta(days=365)  # yearly; pending founder confirmation
RECHECK_CIN = timedelta(days=183)  # six-monthly; pending founder confirmation
# Weekly; pending founder confirmation. RISK: a missed weekly re-screen would lapse every
# supplier's Verified badge at once. The scheduler must alert before expiry.
RECHECK_SANCTIONS = timedelta(days=7)

# Records dated further ahead than this are ignored (a skewed or forged clock must not
# let a future-dated record win "latest" and pin a badge).
CLOCK_SKEW = timedelta(minutes=5)

# Types not listed have no scheduled re-check (None).
RECHECK_INTERVALS: dict[CheckType, timedelta] = {
    CheckType.GSTIN: RECHECK_GSTIN,
    CheckType.PAN: RECHECK_PAN,
    CheckType.IEC: RECHECK_IEC,
    CheckType.UDYAM: RECHECK_UDYAM,
    CheckType.CIN: RECHECK_CIN,
    CheckType.LLPIN: RECHECK_CIN,
    CheckType.SANCTIONS: RECHECK_SANCTIONS,
}


class Badge(StrEnum):
    VERIFIED_SUPPLIER = "verified_supplier"
    GST_VERIFIED = "gst_verified"
    PAN_VERIFIED = "pan_verified"
    MSME_UDYAM = "msme_udyam"
    COMPANY_REGISTERED = "company_registered"
    EXPORT_READY_IEC = "export_ready_iec"
    BANK_VERIFIED = "bank_verified"
    BUSINESS_VERIFIED = "business_verified"  # foreign buyer
    SIGNATORY_CONFIRMED = "signatory_confirmed"  # internal
    SCREENING_CLEAR = "screening_clear"  # internal


@dataclass(frozen=True, slots=True)
class BadgeSpec:
    badge: Badge
    label: str
    # All groups must be satisfied; a group is satisfied by any one of its check types.
    requires: tuple[frozenset[CheckType], ...]
    audience: Literal["buyers", "suppliers", "internal"]


def _all(*types: CheckType) -> tuple[frozenset[CheckType], ...]:
    return tuple(frozenset({t}) for t in types)


C = CheckType
BADGE_TABLE: dict[Badge, BadgeSpec] = {
    s.badge: s
    for s in (
        BadgeSpec(
            Badge.VERIFIED_SUPPLIER,
            "Verified supplier",
            _all(C.GSTIN, C.LEGAL_NAME_CONFIRMED, C.PAN, C.SIGNATORY, C.SANCTIONS),
            "buyers",
        ),
        # GSTIN pass = status Active and PAN segment consistent (adapter responsibility);
        # the legal-name confirmation is the supplier's own action.
        BadgeSpec(
            Badge.GST_VERIFIED, "GST verified", _all(C.GSTIN, C.LEGAL_NAME_CONFIRMED), "buyers"
        ),
        # PAN check passes only if the name on PAN matches the GST legal name.
        BadgeSpec(Badge.PAN_VERIFIED, "PAN verified", _all(C.PAN), "buyers"),
        BadgeSpec(Badge.MSME_UDYAM, "MSME registered", _all(C.UDYAM), "buyers"),
        BadgeSpec(
            Badge.COMPANY_REGISTERED,
            "Company registered",
            (frozenset({C.CIN, C.LLPIN}),),
            "buyers",
        ),
        BadgeSpec(Badge.EXPORT_READY_IEC, "Export-ready (IEC)", _all(C.IEC), "buyers"),
        # A staff-approved mismatch is recorded as a passing inhouse check by the review flow.
        BadgeSpec(
            Badge.BANK_VERIFIED,
            "Bank verified",
            (frozenset({C.BANK_PENNY_DROP, C.BANK_REVERSE_PENNY_DROP}),),
            "buyers",
        ),
        BadgeSpec(
            Badge.BUSINESS_VERIFIED,
            "Business verified",
            _all(C.REGISTRY_DOC, C.DOMAIN, C.SANCTIONS),
            "suppliers",
        ),
        BadgeSpec(Badge.SIGNATORY_CONFIRMED, "Signatory confirmed", _all(C.SIGNATORY), "internal"),
        BadgeSpec(Badge.SCREENING_CLEAR, "Screening clear", _all(C.SANCTIONS), "internal"),
    )
}


def recheck_interval(badge: Badge) -> timedelta | None:
    """Shortest re-check interval among the badge's required check types, if any."""
    intervals = [
        RECHECK_INTERVALS[t]
        for group in BADGE_TABLE[badge].requires
        for t in group
        if t in RECHECK_INTERVALS
    ]
    return min(intervals) if intervals else None


class CheckRecord(BaseModel):
    model_config = ConfigDict(frozen=True, hide_input_in_errors=True)

    check_id: str  # id of the stored check; every badge traces to these (rule 3)
    org_id: str
    provider: str  # which adapter produced the record, e.g. "fake"
    check_type: CheckType
    outcome: CheckOutcome
    source: str  # upstream source, e.g. "GSTN"
    provider_ref: str | None = None
    checked_on: AwareDatetime
    recheck_by: AwareDatetime | None = None  # the check is expired from this instant


class BadgeGrant(BaseModel):
    model_config = ConfigDict(frozen=True, hide_input_in_errors=True)

    badge: Badge
    records: tuple[CheckRecord, ...]  # the checks behind the badge (rule 3)
    # Latest supporting check time. TODO: "verified since" needs the event log (no
    # continuous-pass history yet).
    last_checked: AwareDatetime
    recheck_by: AwareDatetime | None  # earliest expiry among supporting checks


def effective_expiry(rec: CheckRecord) -> datetime | None:
    """Earlier of the record's own recheck_by and checked_on + the type's interval."""
    interval = RECHECK_INTERVALS.get(rec.check_type)
    candidates: list[datetime] = []
    if rec.recheck_by is not None:
        candidates.append(rec.recheck_by)
    if interval is not None:
        candidates.append(rec.checked_on + interval)
    return min(candidates) if candidates else None


def _is_valid(rec: CheckRecord, now: datetime) -> bool:
    if rec.outcome is not CheckOutcome.PASS:
        return False
    if rec.check_type in RECHECK_INTERVALS and rec.recheck_by is None:
        return False  # no permanent badges on types that must be re-checked
    expiry = effective_expiry(rec)
    return expiry is None or expiry > now


def compute_badges(records: list[CheckRecord], now: datetime) -> dict[Badge, BadgeGrant]:
    """Badges held at ``now``, from the latest decisive check of each type.

    ``records`` must all belong to one org (ValueError otherwise). ``now`` must be
    timezone-aware (UTC). Records dated after ``now + CLOCK_SKEW`` are ignored; on equal
    ``checked_on`` within a type the non-PASS record wins.
    """
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    if len({r.org_id for r in records}) > 1:
        raise ValueError("records span more than one org_id")
    latest: dict[CheckType, CheckRecord] = {}
    for rec in records:
        if rec.outcome not in _DECISIVE or rec.checked_on > now + CLOCK_SKEW:
            continue
        cur = latest.get(rec.check_type)
        if (
            cur is None
            or rec.checked_on > cur.checked_on
            or (
                rec.checked_on == cur.checked_on
                and cur.outcome is CheckOutcome.PASS
                and rec.outcome is not CheckOutcome.PASS
            )
        ):
            latest[rec.check_type] = rec
    valid = {t: r for t, r in latest.items() if _is_valid(r, now)}

    granted: dict[Badge, BadgeGrant] = {}
    for badge, spec in BADGE_TABLE.items():
        support: list[CheckRecord] = []
        for group in spec.requires:
            hits = sorted(
                (valid[t] for t in group if t in valid), key=lambda r: r.checked_on, reverse=True
            )
            if not hits:
                break
            support.append(hits[0])
        else:
            expiries = [e for r in support if (e := effective_expiry(r)) is not None]
            granted[badge] = BadgeGrant(
                badge=badge,
                records=tuple(support),
                last_checked=max(r.checked_on for r in support),
                recheck_by=min(expiries) if expiries else None,
            )
    return granted
