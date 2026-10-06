"""Test badge computation from check records (plan section 1.2, 8.1)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.modules.verification.policy import (
    BADGE_TABLE,
    CLOCK_SKEW,
    RECHECK_INTERVALS,
    Badge,
    CheckOutcome,
    CheckRecord,
    CheckType,
    compute_badges,
    effective_expiry,
)


class TestBadgeComputationBasics:
    """Badge computation with the new CheckRecord API requiring org_id and provider."""

    @staticmethod
    def make_record(
        check_type: CheckType,
        outcome: CheckOutcome,
        checked_on: datetime,
        recheck_by: datetime | None = None,
        org_id: str = "test-org",
        provider: str = "fake",
    ) -> CheckRecord:
        """Helper to create a CheckRecord with required org_id and provider."""
        # Auto-provide recheck_by for interval types if not given and outcome is PASS
        if recheck_by is None and outcome is CheckOutcome.PASS and check_type in RECHECK_INTERVALS:
            recheck_by = checked_on + RECHECK_INTERVALS[check_type]
        return CheckRecord(
            check_id=f"chk-{check_type.value}",
            org_id=org_id,
            provider=provider,
            check_type=check_type,
            outcome=outcome,
            source="test_source",
            provider_ref=f"test-ref-{check_type.value}",
            checked_on=checked_on,
            recheck_by=recheck_by,
        )

    def test_all_required_checks_pass_yields_verified_supplier(self) -> None:
        """Done when: all five required checks pass → VERIFIED_SUPPLIER badge."""
        now = datetime.now(UTC)
        records = [
            self.make_record(CheckType.GSTIN, CheckOutcome.PASS, now),
            self.make_record(CheckType.LEGAL_NAME_CONFIRMED, CheckOutcome.PASS, now),
            self.make_record(CheckType.PAN, CheckOutcome.PASS, now),
            self.make_record(CheckType.SIGNATORY, CheckOutcome.PASS, now),
            self.make_record(CheckType.SANCTIONS, CheckOutcome.PASS, now),
        ]
        badges = compute_badges(records, now)
        assert Badge.VERIFIED_SUPPLIER in badges

    def test_gst_verified_badge(self) -> None:
        """Done when: GSTIN and LEGAL_NAME_CONFIRMED pass → GST_VERIFIED badge."""
        now = datetime.now(UTC)
        records = [
            self.make_record(CheckType.GSTIN, CheckOutcome.PASS, now),
            self.make_record(CheckType.LEGAL_NAME_CONFIRMED, CheckOutcome.PASS, now),
        ]
        badges = compute_badges(records, now)
        assert Badge.GST_VERIFIED in badges

    def test_signatory_confirmed_badge(self) -> None:
        """Done when: SIGNATORY pass → SIGNATORY_CONFIRMED (not buyer-visible)."""
        now = datetime.now(UTC)
        records = [self.make_record(CheckType.SIGNATORY, CheckOutcome.PASS, now)]
        badges = compute_badges(records, now)
        assert Badge.SIGNATORY_CONFIRMED in badges


class TestBadgeValidity:
    """Badge validity rules per new policy."""

    @staticmethod
    def make_record(
        check_type: CheckType,
        outcome: CheckOutcome,
        checked_on: datetime,
        recheck_by: datetime | None = None,
        org_id: str = "test-org",
    ) -> CheckRecord:
        """Helper to create CheckRecord."""
        if recheck_by is None and outcome is CheckOutcome.PASS and check_type in RECHECK_INTERVALS:
            recheck_by = checked_on + RECHECK_INTERVALS[check_type]
        return CheckRecord(
            check_id=f"chk-{check_type.value}",
            org_id=org_id,
            provider="fake",
            check_type=check_type,
            outcome=outcome,
            source="test",
            provider_ref="ref",
            checked_on=checked_on,
            recheck_by=recheck_by,
        )

    def test_interval_type_pass_without_recheck_by_invalid(self) -> None:
        """Done when: PASS on interval type without recheck_by is NOT valid."""
        now = datetime.now(UTC)
        # Manually override auto-recheck_by to test this rule
        record = CheckRecord(
            check_id="chk-gstin",
            org_id="test-org",
            provider="fake",
            check_type=CheckType.GSTIN,
            outcome=CheckOutcome.PASS,
            source="test",
            provider_ref="ref",
            checked_on=now,
            recheck_by=None,  # No recheck_by
        )
        legal = self.make_record(CheckType.LEGAL_NAME_CONFIRMED, CheckOutcome.PASS, now)
        badges = compute_badges([record, legal], now)
        assert Badge.GST_VERIFIED not in badges

    def test_non_interval_type_pass_without_recheck_by_valid(self) -> None:
        """Done when: PASS on non-interval type without recheck_by is valid."""
        now = datetime.now(UTC)
        records = [self.make_record(CheckType.SIGNATORY, CheckOutcome.PASS, now)]
        badges = compute_badges(records, now)
        assert Badge.SIGNATORY_CONFIRMED in badges

    def test_mixed_org_ids_raise_valueerror(self) -> None:
        """Done when: Records from different orgs raise ValueError."""
        now = datetime.now(UTC)
        records = [
            self.make_record(CheckType.GSTIN, CheckOutcome.PASS, now, org_id="org1"),
            self.make_record(CheckType.PAN, CheckOutcome.PASS, now, org_id="org2"),
        ]
        with pytest.raises(ValueError, match="span more than one org_id"):
            compute_badges(records, now)

    def test_future_record_ignored(self) -> None:
        """Done when: Records dated after now + CLOCK_SKEW are ignored."""
        now = datetime.now(UTC)
        future = now + CLOCK_SKEW + timedelta(seconds=1)
        records = [self.make_record(CheckType.GSTIN, CheckOutcome.PASS, future)]
        badges = compute_badges(records, now)
        assert Badge.GST_VERIFIED not in badges

    def test_fail_outcome_drops_badge(self) -> None:
        """Done when: FAIL outcome drops badge."""
        now = datetime.now(UTC)
        records = [self.make_record(CheckType.GSTIN, CheckOutcome.FAIL, now)]
        badges = compute_badges(records, now)
        assert Badge.GST_VERIFIED not in badges


class TestComputeBadgesRobustness:
    """Robustness tests."""

    def test_compute_with_naive_datetime_raises(self) -> None:
        """Done when: Naive datetime raises ValueError."""
        now = datetime(2025, 1, 15, 12, 0, 0)  # No timezone
        records = [
            CheckRecord(
                check_id="chk-gstin",
                org_id="test",
                provider="fake",
                check_type=CheckType.GSTIN,
                outcome=CheckOutcome.PASS,
                source="test",
                provider_ref="ref",
                checked_on=datetime(2025, 1, 10, 12, 0, 0, tzinfo=UTC),
                recheck_by=None,
            )
        ]
        with pytest.raises(ValueError, match="timezone-aware"):
            compute_badges(records, now)

    def test_compute_with_empty_records(self) -> None:
        """Done when: Empty records yields no badges."""
        now = datetime.now(UTC)
        badges = compute_badges([], now)
        assert badges == {}


T0 = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
FIVE = [
    CheckType.GSTIN,
    CheckType.LEGAL_NAME_CONFIRMED,
    CheckType.PAN,
    CheckType.SIGNATORY,
    CheckType.SANCTIONS,
]


def gst_pair(outcome: CheckOutcome = CheckOutcome.PASS) -> list[CheckRecord]:
    return [rec(CheckType.GSTIN, outcome), rec(CheckType.LEGAL_NAME_CONFIRMED)]


def rec(
    check_type: CheckType,
    outcome: CheckOutcome = CheckOutcome.PASS,
    checked_on: datetime = T0,
    recheck_by: datetime | None = None,
    ref: str | None = None,
    source: str = "src",
    check_id: str | None = None,
) -> CheckRecord:
    if recheck_by is None and outcome is CheckOutcome.PASS and check_type in RECHECK_INTERVALS:
        recheck_by = checked_on + RECHECK_INTERVALS[check_type]
    return CheckRecord(
        check_id=check_id or f"chk-{check_type.value}",
        org_id="org-a",
        provider="fake",
        check_type=check_type,
        outcome=outcome,
        source=source,
        provider_ref=ref or f"ref-{check_type.value}",
        checked_on=checked_on,
        recheck_by=recheck_by,
    )


LEGAL = rec(CheckType.LEGAL_NAME_CONFIRMED)


class TestVerifiedSupplier:
    @pytest.mark.parametrize("missing", FIVE)
    def test_requires_all_five(self, missing: CheckType) -> None:
        """Done when: VERIFIED_SUPPLIER needs all five (GSTIN, legal name, PAN, ...)."""
        records = [rec(t) for t in FIVE if t is not missing]
        assert Badge.VERIFIED_SUPPLIER not in compute_badges(records, T0)

    def test_potential_hit_on_sanctions_removes_it(self) -> None:
        records = [rec(t) for t in FIVE]
        records.append(
            rec(CheckType.SANCTIONS, CheckOutcome.POTENTIAL_HIT, T0 + timedelta(hours=1))
        )
        badges = compute_badges(records, T0 + timedelta(hours=2))
        assert Badge.VERIFIED_SUPPLIER not in badges
        assert Badge.SCREENING_CLEAR not in badges
        assert Badge.GST_VERIFIED in badges  # unrelated badges survive

    def test_earliest_expiry_is_grant_recheck_by(self) -> None:
        badges = compute_badges([rec(t) for t in FIVE], T0)
        grant = badges[Badge.VERIFIED_SUPPLIER]
        assert grant.recheck_by == T0 + RECHECK_INTERVALS[CheckType.SANCTIONS]  # 7 days, the min
        expiries = [e for r in grant.records if (e := effective_expiry(r)) is not None]
        assert grant.recheck_by == min(expiries)

    def test_records_carry_supporting_checks_with_ref_and_source(self) -> None:
        records = [rec(t, ref=f"vendor-ref-{i}", source=f"source-{i}") for i, t in enumerate(FIVE)]
        grant = compute_badges(records, T0)[Badge.VERIFIED_SUPPLIER]
        assert {r.check_type for r in grant.records} == set(FIVE)
        by_type = {r.check_type: r for r in grant.records}
        for i, t in enumerate(FIVE):
            assert by_type[t].provider_ref == f"vendor-ref-{i}"
            assert by_type[t].source == f"source-{i}"
        assert grant.last_checked == T0


class TestAudienceAndLabels:
    @pytest.mark.parametrize("badge", [Badge.SIGNATORY_CONFIRMED, Badge.SCREENING_CLEAR])
    def test_internal_badges_not_visible_to_buyers(self, badge: Badge) -> None:
        assert BADGE_TABLE[badge].audience == "internal"

    def test_business_verified_is_for_suppliers(self) -> None:
        assert BADGE_TABLE[Badge.BUSINESS_VERIFIED].audience == "suppliers"

    @pytest.mark.parametrize(
        "badge",
        [
            Badge.VERIFIED_SUPPLIER,
            Badge.GST_VERIFIED,
            Badge.PAN_VERIFIED,
            Badge.MSME_UDYAM,
            Badge.COMPANY_REGISTERED,
            Badge.EXPORT_READY_IEC,
            Badge.BANK_VERIFIED,
        ],
    )
    def test_buyer_facing_badges(self, badge: Badge) -> None:
        assert BADGE_TABLE[badge].audience == "buyers"

    def test_every_badge_has_an_audience(self) -> None:
        assert set(BADGE_TABLE) == set(Badge)
        assert {s.audience for s in BADGE_TABLE.values()} <= {"buyers", "suppliers", "internal"}

    def test_exact_labels(self) -> None:
        assert {b: s.label for b, s in BADGE_TABLE.items()} == {
            Badge.VERIFIED_SUPPLIER: "Verified supplier",
            Badge.GST_VERIFIED: "GST verified",
            Badge.PAN_VERIFIED: "PAN verified",
            Badge.MSME_UDYAM: "MSME registered",
            Badge.COMPANY_REGISTERED: "Company registered",
            Badge.EXPORT_READY_IEC: "Export-ready (IEC)",
            Badge.BANK_VERIFIED: "Bank verified",
            Badge.BUSINESS_VERIFIED: "Business verified",
            Badge.SIGNATORY_CONFIRMED: "Signatory confirmed",
            Badge.SCREENING_CLEAR: "Screening clear",
        }


class TestLegalNameConfirmed:
    def test_gstin_without_legal_name_gives_no_gst_verified_nor_verified_supplier(self) -> None:
        records = [rec(t) for t in FIVE if t is not CheckType.LEGAL_NAME_CONFIRMED]
        badges = compute_badges(records, T0)
        assert Badge.GST_VERIFIED not in badges
        assert Badge.VERIFIED_SUPPLIER not in badges
        assert Badge.PAN_VERIFIED in badges  # unrelated badges survive

    def test_legal_name_without_gstin_gives_no_gst_verified(self) -> None:
        badges = compute_badges([LEGAL], T0)
        assert Badge.GST_VERIFIED not in badges
        assert Badge.VERIFIED_SUPPLIER not in badges

    def test_failed_legal_name_drops_gst_verified(self) -> None:
        records = [
            *gst_pair(),
            rec(CheckType.LEGAL_NAME_CONFIRMED, CheckOutcome.FAIL, T0 + timedelta(days=1)),
        ]
        assert Badge.GST_VERIFIED not in compute_badges(records, T0 + timedelta(days=2))

    def test_legal_name_has_no_recheck_interval(self) -> None:
        assert CheckType.LEGAL_NAME_CONFIRMED not in RECHECK_INTERVALS
        assert effective_expiry(LEGAL) is None

    def test_legal_name_never_expires_on_its_own(self) -> None:
        later = T0 + timedelta(days=3650)
        gstin = rec(CheckType.GSTIN, checked_on=later - timedelta(days=1))
        assert Badge.GST_VERIFIED in compute_badges([gstin, LEGAL], later)

    def test_gst_verified_expires_with_gstin_not_legal_name(self) -> None:
        gstin = rec(CheckType.GSTIN)
        grant = compute_badges([gstin, LEGAL], T0)[Badge.GST_VERIFIED]
        assert grant.recheck_by == T0 + RECHECK_INTERVALS[CheckType.GSTIN]
        assert Badge.GST_VERIFIED not in compute_badges(
            [gstin, LEGAL], T0 + RECHECK_INTERVALS[CheckType.GSTIN]
        )


class TestRecordCheckIds:
    def test_grant_records_expose_their_check_ids(self) -> None:
        records = [rec(t, check_id=f"id-{i}") for i, t in enumerate(FIVE)]
        grant = compute_badges(records, T0)[Badge.VERIFIED_SUPPLIER]
        assert {r.check_id for r in grant.records} == {f"id-{i}" for i in range(len(FIVE))}

    def test_gst_grant_traces_to_both_checks(self) -> None:
        gstin = rec(CheckType.GSTIN, check_id="g-1")
        legal = rec(CheckType.LEGAL_NAME_CONFIRMED, check_id="l-1")
        grant = compute_badges([gstin, legal], T0)[Badge.GST_VERIFIED]
        assert [r.check_id for r in grant.records] == ["g-1", "l-1"]

    def test_grant_uses_latest_record_check_id(self) -> None:
        old = rec(CheckType.GSTIN, check_id="old")
        new = rec(CheckType.GSTIN, checked_on=T0 + timedelta(days=1), check_id="new")
        grant = compute_badges([old, new, LEGAL], T0 + timedelta(days=2))[Badge.GST_VERIFIED]
        assert "new" in {r.check_id for r in grant.records}
        assert "old" not in {r.check_id for r in grant.records}

    def test_check_id_is_required(self) -> None:
        with pytest.raises(ValueError):  # noqa: PT011
            CheckRecord(  # type: ignore[call-arg]
                org_id="o",
                provider="fake",
                check_type=CheckType.PAN,
                outcome=CheckOutcome.PASS,
                source="s",
                checked_on=T0,
            )


class TestLaterRecordsAndExpiry:
    @pytest.mark.parametrize(
        "outcome", [CheckOutcome.FAIL, CheckOutcome.MISMATCH, CheckOutcome.NOT_FOUND]
    )
    def test_later_verdict_after_pass_drops(self, outcome: CheckOutcome) -> None:
        records = [
            *gst_pair(),
            rec(CheckType.GSTIN, outcome, T0 + timedelta(days=1)),
        ]
        assert Badge.GST_VERIFIED not in compute_badges(records, T0 + timedelta(days=2))

    @pytest.mark.parametrize("outcome", [CheckOutcome.ERROR, CheckOutcome.PENDING])
    def test_non_verdict_after_pass_keeps_badge(self, outcome: CheckOutcome) -> None:
        records = [
            *gst_pair(),
            rec(CheckType.GSTIN, outcome, T0 + timedelta(days=1)),
        ]
        assert Badge.GST_VERIFIED in compute_badges(records, T0 + timedelta(days=2))

    def test_pass_after_fail_restores(self) -> None:
        records = [
            *gst_pair(CheckOutcome.FAIL),
            rec(CheckType.GSTIN, CheckOutcome.PASS, T0 + timedelta(days=1)),
        ]
        assert Badge.GST_VERIFIED in compute_badges(records, T0 + timedelta(days=2))

    def test_expiry_exactly_at_effective_expiry_drops(self) -> None:
        record = rec(CheckType.GSTIN)
        expiry = T0 + RECHECK_INTERVALS[CheckType.GSTIN]
        assert effective_expiry(record) == expiry
        assert Badge.GST_VERIFIED in compute_badges([record, LEGAL], expiry - timedelta(seconds=1))
        assert Badge.GST_VERIFIED not in compute_badges([record, LEGAL], expiry)

    def test_recheck_by_beyond_interval_is_capped(self) -> None:
        record = rec(CheckType.GSTIN, recheck_by=T0 + timedelta(days=365))
        cap = T0 + RECHECK_INTERVALS[CheckType.GSTIN]
        assert effective_expiry(record) == cap
        assert Badge.GST_VERIFIED in compute_badges([record, LEGAL], cap - timedelta(seconds=1))
        assert Badge.GST_VERIFIED not in compute_badges([record, LEGAL], cap)
        grant = compute_badges([record, LEGAL], T0)[Badge.GST_VERIFIED]
        assert grant.recheck_by == cap

    def test_earlier_own_recheck_by_wins_over_interval(self) -> None:
        early = T0 + timedelta(days=3)
        record = rec(CheckType.GSTIN, recheck_by=early)
        assert effective_expiry(record) == early
        assert Badge.GST_VERIFIED not in compute_badges([record, LEGAL], early)


class TestTieOnCheckedOn:
    @pytest.mark.parametrize("pass_first", [True, False])
    def test_non_pass_wins_regardless_of_order(self, pass_first: bool) -> None:
        p = rec(CheckType.GSTIN, CheckOutcome.PASS)
        f = rec(CheckType.GSTIN, CheckOutcome.FAIL)
        records = [p, f, LEGAL] if pass_first else [f, p, LEGAL]
        assert Badge.GST_VERIFIED not in compute_badges(records, T0 + timedelta(minutes=1))


class TestGrantContents:
    def test_single_badge_records_and_last_checked(self) -> None:
        checked = T0 - timedelta(days=2)
        record = rec(CheckType.GSTIN, checked_on=checked, ref="vendor-1", source="GSTN")
        legal = rec(CheckType.LEGAL_NAME_CONFIRMED, checked_on=checked)
        grant = compute_badges([record, legal], T0)[Badge.GST_VERIFIED]
        assert grant.records == (record, legal)
        assert grant.records[0].provider_ref == "vendor-1"
        assert grant.records[0].source == "GSTN"
        assert grant.last_checked == checked
        assert grant.recheck_by == checked + RECHECK_INTERVALS[CheckType.GSTIN]

    def test_non_interval_badge_has_no_recheck_by(self) -> None:
        grant = compute_badges([rec(CheckType.SIGNATORY)], T0)[Badge.SIGNATORY_CONFIRMED]
        assert grant.recheck_by is None
