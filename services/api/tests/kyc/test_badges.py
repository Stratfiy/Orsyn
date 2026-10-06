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
        """Done when: GSTIN, PAN, SIGNATORY, SANCTIONS all pass → VERIFIED_SUPPLIER badge."""
        now = datetime.now(UTC)
        records = [
            self.make_record(CheckType.GSTIN, CheckOutcome.PASS, now),
            self.make_record(CheckType.PAN, CheckOutcome.PASS, now),
            self.make_record(CheckType.SIGNATORY, CheckOutcome.PASS, now),
            self.make_record(CheckType.SANCTIONS, CheckOutcome.PASS, now),
        ]
        badges = compute_badges(records, now)
        assert Badge.VERIFIED_SUPPLIER in badges

    def test_gst_verified_badge(self) -> None:
        """Done when: GSTIN check pass → GST_VERIFIED badge."""
        now = datetime.now(UTC)
        records = [self.make_record(CheckType.GSTIN, CheckOutcome.PASS, now)]
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
            org_id="test",
            provider="fake",
            check_type=CheckType.GSTIN,
            outcome=CheckOutcome.PASS,
            source="test",
            provider_ref="ref",
            checked_on=now,
            recheck_by=None,  # No recheck_by
        )
        badges = compute_badges([record], now)
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
FOUR = [CheckType.GSTIN, CheckType.PAN, CheckType.SIGNATORY, CheckType.SANCTIONS]


def rec(
    check_type: CheckType,
    outcome: CheckOutcome = CheckOutcome.PASS,
    checked_on: datetime = T0,
    recheck_by: datetime | None = None,
    ref: str | None = None,
    source: str = "src",
) -> CheckRecord:
    if recheck_by is None and outcome is CheckOutcome.PASS and check_type in RECHECK_INTERVALS:
        recheck_by = checked_on + RECHECK_INTERVALS[check_type]
    return CheckRecord(
        org_id="org-a",
        provider="fake",
        check_type=check_type,
        outcome=outcome,
        source=source,
        provider_ref=ref or f"ref-{check_type.value}",
        checked_on=checked_on,
        recheck_by=recheck_by,
    )


class TestVerifiedSupplier:
    @pytest.mark.parametrize("missing", FOUR)
    def test_requires_all_four(self, missing: CheckType) -> None:
        """Done when: VERIFIED_SUPPLIER needs GSTIN, PAN, SIGNATORY and SANCTIONS."""
        records = [rec(t) for t in FOUR if t is not missing]
        assert Badge.VERIFIED_SUPPLIER not in compute_badges(records, T0)

    def test_potential_hit_on_sanctions_removes_it(self) -> None:
        records = [rec(t) for t in FOUR]
        records.append(
            rec(CheckType.SANCTIONS, CheckOutcome.POTENTIAL_HIT, T0 + timedelta(hours=1))
        )
        badges = compute_badges(records, T0 + timedelta(hours=2))
        assert Badge.VERIFIED_SUPPLIER not in badges
        assert Badge.SCREENING_CLEAR not in badges
        assert Badge.GST_VERIFIED in badges  # unrelated badges survive

    def test_earliest_expiry_is_grant_recheck_by(self) -> None:
        badges = compute_badges([rec(t) for t in FOUR], T0)
        grant = badges[Badge.VERIFIED_SUPPLIER]
        assert grant.recheck_by == T0 + RECHECK_INTERVALS[CheckType.SANCTIONS]  # 7 days, the min
        expiries = [e for r in grant.records if (e := effective_expiry(r)) is not None]
        assert grant.recheck_by == min(expiries)

    def test_records_carry_supporting_checks_with_ref_and_source(self) -> None:
        records = [rec(t, ref=f"vendor-ref-{i}", source=f"source-{i}") for i, t in enumerate(FOUR)]
        grant = compute_badges(records, T0)[Badge.VERIFIED_SUPPLIER]
        assert {r.check_type for r in grant.records} == set(FOUR)
        by_type = {r.check_type: r for r in grant.records}
        for i, t in enumerate(FOUR):
            assert by_type[t].provider_ref == f"vendor-ref-{i}"
            assert by_type[t].source == f"source-{i}"
        assert grant.since == T0


class TestInternalBadges:
    @pytest.mark.parametrize("badge", [Badge.SIGNATORY_CONFIRMED, Badge.SCREENING_CLEAR])
    def test_not_buyer_visible(self, badge: Badge) -> None:
        assert BADGE_TABLE[badge].buyer_visible is False

    def test_buyer_facing_badges_are_visible(self) -> None:
        assert BADGE_TABLE[Badge.VERIFIED_SUPPLIER].buyer_visible is True
        assert BADGE_TABLE[Badge.GST_VERIFIED].buyer_visible is True


class TestLaterRecordsAndExpiry:
    @pytest.mark.parametrize(
        "outcome", [CheckOutcome.FAIL, CheckOutcome.MISMATCH, CheckOutcome.NOT_FOUND]
    )
    def test_later_verdict_after_pass_drops(self, outcome: CheckOutcome) -> None:
        records = [
            rec(CheckType.GSTIN),
            rec(CheckType.GSTIN, outcome, T0 + timedelta(days=1)),
        ]
        assert Badge.GST_VERIFIED not in compute_badges(records, T0 + timedelta(days=2))

    @pytest.mark.parametrize("outcome", [CheckOutcome.ERROR, CheckOutcome.PENDING])
    def test_non_verdict_after_pass_keeps_badge(self, outcome: CheckOutcome) -> None:
        records = [
            rec(CheckType.GSTIN),
            rec(CheckType.GSTIN, outcome, T0 + timedelta(days=1)),
        ]
        assert Badge.GST_VERIFIED in compute_badges(records, T0 + timedelta(days=2))

    def test_pass_after_fail_restores(self) -> None:
        records = [
            rec(CheckType.GSTIN, CheckOutcome.FAIL),
            rec(CheckType.GSTIN, CheckOutcome.PASS, T0 + timedelta(days=1)),
        ]
        assert Badge.GST_VERIFIED in compute_badges(records, T0 + timedelta(days=2))

    def test_expiry_exactly_at_effective_expiry_drops(self) -> None:
        record = rec(CheckType.GSTIN)
        expiry = T0 + RECHECK_INTERVALS[CheckType.GSTIN]
        assert effective_expiry(record) == expiry
        assert Badge.GST_VERIFIED in compute_badges([record], expiry - timedelta(seconds=1))
        assert Badge.GST_VERIFIED not in compute_badges([record], expiry)

    def test_recheck_by_beyond_interval_is_capped(self) -> None:
        record = rec(CheckType.GSTIN, recheck_by=T0 + timedelta(days=365))
        cap = T0 + RECHECK_INTERVALS[CheckType.GSTIN]
        assert effective_expiry(record) == cap
        assert Badge.GST_VERIFIED in compute_badges([record], cap - timedelta(seconds=1))
        assert Badge.GST_VERIFIED not in compute_badges([record], cap)
        grant = compute_badges([record], T0)[Badge.GST_VERIFIED]
        assert grant.recheck_by == cap

    def test_earlier_own_recheck_by_wins_over_interval(self) -> None:
        early = T0 + timedelta(days=3)
        record = rec(CheckType.GSTIN, recheck_by=early)
        assert effective_expiry(record) == early
        assert Badge.GST_VERIFIED not in compute_badges([record], early)


class TestTieOnCheckedOn:
    @pytest.mark.parametrize("pass_first", [True, False])
    def test_non_pass_wins_regardless_of_order(self, pass_first: bool) -> None:
        p = rec(CheckType.GSTIN, CheckOutcome.PASS)
        f = rec(CheckType.GSTIN, CheckOutcome.FAIL)
        records = [p, f] if pass_first else [f, p]
        assert Badge.GST_VERIFIED not in compute_badges(records, T0 + timedelta(minutes=1))


class TestGrantContents:
    def test_single_badge_records_and_since(self) -> None:
        checked = T0 - timedelta(days=2)
        record = rec(CheckType.GSTIN, checked_on=checked, ref="vendor-1", source="GSTN")
        grant = compute_badges([record], T0)[Badge.GST_VERIFIED]
        assert grant.records == (record,)
        assert grant.records[0].provider_ref == "vendor-1"
        assert grant.records[0].source == "GSTN"
        assert grant.since == checked
        assert grant.recheck_by == checked + RECHECK_INTERVALS[CheckType.GSTIN]

    def test_non_interval_badge_has_no_recheck_by(self) -> None:
        grant = compute_badges([rec(CheckType.SIGNATORY)], T0)[Badge.SIGNATORY_CONFIRMED]
        assert grant.recheck_by is None
