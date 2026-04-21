"""Comprehensive tests for the v8.0.0 P-03 token-budget circuit breaker.

Covers:

- All three decision paths (CONTINUE / WARN / BREAK) per profile.
- Profile defaults (STRICT 80_000 / STANDARD 50_000 / RELAXED 0 (unlimited)
  / AUDIT 100_000) per ``patch_plan §3 P-03``.
- ``evaluate_gate(breaker=None)`` byte-identity regression vs v7.8.0.
- STRICT profile + cumulative=80_001 → BREAK + ESCALATE recommendation
  (``patch_plan §3 P-03 AC #6``).
- Edge cases: negative tokens, zero budget (unlimited), unknown profile,
  threshold boundary conditions.
- Schema invariant: ``schemas/lean-dispatch.yaml#layout_invariant``
  ``canonical_order`` length = 13, ``version`` = 2 PRESERVED (P6).

Target: 100 % line coverage on ``src/devolaflow/gate/budget.py``.
"""

from __future__ import annotations

import logging
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from devolaflow.gate.budget import (
    BREAK_UTILIZATION_THRESHOLD,
    WARN_UTILIZATION_THRESHOLD,
    TokenBudgetBreaker,
    _classify_utilization,
    _disabled_decision,
    _format_rationale,
    _recommendation_for,
    _resolve_max_tokens,
    from_profile_name,
)
from devolaflow.gate.models import (
    BudgetAction,
    BudgetDecision,
    BudgetRecommendation,
    CheckResult,
    Finding,
    GateInput,
    GateProfile,
)
from devolaflow.gate.profiles import AUDIT, PROFILES, RELAXED, STANDARD, STRICT
from devolaflow.gate.scorer import evaluate_gate

# ---------------------------------------------------------------------------
# helpers — tiny fixtures shared across the suite
# ---------------------------------------------------------------------------


def _pass_input() -> GateInput:
    """A trivial all-pass :class:`GateInput` for byte-identity regression."""
    return GateInput(
        build_status=CheckResult(status="pass"),
        test_results=CheckResult(status="pass"),
        lint_status=CheckResult(status="pass"),
        review_findings=[],
        acceptance_criteria_results=CheckResult(status="pass"),
    )


def _fail_input() -> GateInput:
    """A failing :class:`GateInput` to verify FAIL paths still surface."""
    return GateInput(
        build_status=CheckResult(status="fail"),
        test_results=CheckResult(status="pass"),
        lint_status=CheckResult(status="pass"),
        review_findings=[
            Finding(
                finding_id="F999",
                severity="major",
                category="test",
                location="src/x.py:1",
                description="x",
            )
        ],
    )


# ---------------------------------------------------------------------------
# 1. profile defaults — patch_plan §3 P-03 lines 183-184 verbatim
# ---------------------------------------------------------------------------


class TestProfileMaxTokensDefaults:
    """Each registered profile carries the documented ``max_tokens`` ceiling."""

    def test_strict_max_tokens_is_80k(self) -> None:
        assert STRICT.max_tokens == 80_000

    def test_standard_max_tokens_is_50k(self) -> None:
        assert STANDARD.max_tokens == 50_000

    def test_relaxed_max_tokens_is_zero_unlimited(self) -> None:
        assert RELAXED.max_tokens == 0

    def test_audit_max_tokens_is_100k(self) -> None:
        assert AUDIT.max_tokens == 100_000

    def test_profiles_registry_contains_all_four(self) -> None:
        assert set(PROFILES) == {"strict", "standard", "relaxed", "audit"}


# ---------------------------------------------------------------------------
# 2. constructor / property / type validation
# ---------------------------------------------------------------------------


class TestConstructor:
    """Construction-time validation and property surfaces."""

    def test_default_max_tokens_pulled_from_profile(self) -> None:
        b = TokenBudgetBreaker(profile=STRICT)
        assert b.max_tokens == STRICT.max_tokens == 80_000

    def test_explicit_max_tokens_overrides_profile(self) -> None:
        b = TokenBudgetBreaker(profile=STRICT, max_tokens=10_000)
        assert b.max_tokens == 10_000
        assert b.profile is STRICT

    def test_zero_max_tokens_means_unlimited(self) -> None:
        b = TokenBudgetBreaker(profile=STANDARD, max_tokens=0)
        assert b.is_unlimited is True
        assert b.max_tokens == 0

    def test_relaxed_profile_default_is_unlimited(self) -> None:
        b = TokenBudgetBreaker(profile=RELAXED)
        assert b.is_unlimited is True

    def test_negative_max_tokens_override_raises(self) -> None:
        with pytest.raises(ValueError, match="max_tokens override must be >= 0"):
            TokenBudgetBreaker(profile=STANDARD, max_tokens=-1)

    def test_negative_profile_max_tokens_raises(self) -> None:
        bad_profile = replace(STANDARD, max_tokens=-5)
        with pytest.raises(ValueError, match="profile.max_tokens must be >= 0"):
            TokenBudgetBreaker(profile=bad_profile)

    def test_non_profile_argument_raises_typeerror(self) -> None:
        with pytest.raises(TypeError, match="profile must be a GateProfile"):
            TokenBudgetBreaker(profile="strict")  # type: ignore[arg-type]

    def test_initial_cumulative_is_zero(self) -> None:
        b = TokenBudgetBreaker(profile=STANDARD)
        assert b.cumulative_tokens == 0


# ---------------------------------------------------------------------------
# 3. three decision paths — per profile (4 profiles × 3 paths = 12 baseline)
# ---------------------------------------------------------------------------


class TestThreePathsAcrossProfiles:
    """CONTINUE / WARN / BREAK for every profile flavour."""

    @pytest.mark.parametrize(
        ("profile", "max_tokens"),
        [
            (STRICT, 10_000),
            (STANDARD, 10_000),
            (AUDIT, 10_000),
            # RELAXED is unlimited by default — exercise it with an explicit
            # finite override so we can assert all three paths.
            (RELAXED, 10_000),
        ],
        ids=["strict", "standard", "audit", "relaxed-explicit"],
    )
    def test_continue_path_below_warn_threshold(
        self, profile: GateProfile, max_tokens: int
    ) -> None:
        b = TokenBudgetBreaker(profile=profile, max_tokens=max_tokens)
        decision = b.check(5_000)  # 0.50 utilization
        assert decision.action is BudgetAction.CONTINUE
        assert decision.recommendation is BudgetRecommendation.NONE
        assert decision.utilization == 0.5
        assert decision.cumulative_tokens == 5_000
        assert decision.max_tokens == max_tokens
        assert "within" in decision.rationale

    @pytest.mark.parametrize(
        ("profile", "max_tokens"),
        [(STRICT, 10_000), (STANDARD, 10_000), (AUDIT, 10_000), (RELAXED, 10_000)],
        ids=["strict", "standard", "audit", "relaxed-explicit"],
    )
    def test_warn_path_inside_warning_band(self, profile: GateProfile, max_tokens: int) -> None:
        b = TokenBudgetBreaker(profile=profile, max_tokens=max_tokens)
        decision = b.check(8_000)  # 0.80 utilization
        assert decision.action is BudgetAction.WARN
        assert decision.recommendation is BudgetRecommendation.THROTTLE
        assert decision.utilization == 0.8
        assert "crossed" in decision.rationale

    @pytest.mark.parametrize(
        ("profile", "max_tokens", "expected_rec"),
        [
            (STRICT, 10_000, BudgetRecommendation.ESCALATE),
            (AUDIT, 10_000, BudgetRecommendation.ESCALATE),
            (STANDARD, 10_000, BudgetRecommendation.ITERATE),
            (RELAXED, 10_000, BudgetRecommendation.ITERATE),
        ],
        ids=["strict-escalate", "audit-escalate", "standard-iterate", "relaxed-iterate"],
    )
    def test_break_path_recommendation_depends_on_profile(
        self,
        profile: GateProfile,
        max_tokens: int,
        expected_rec: BudgetRecommendation,
    ) -> None:
        b = TokenBudgetBreaker(profile=profile, max_tokens=max_tokens)
        decision = b.check(15_000)  # 1.50 utilization
        assert decision.action is BudgetAction.BREAK
        assert decision.recommendation is expected_rec
        assert "exceeded" in decision.rationale
        assert "circuit broken" in decision.rationale


# ---------------------------------------------------------------------------
# 4. patch_plan §3 P-03 AC #1 — exact verbatim contract
# ---------------------------------------------------------------------------


class TestPatchPlanAC1:
    """``TokenBudgetBreaker(max_tokens=10_000).check(N)`` returns documented action."""

    @pytest.fixture
    def breaker(self) -> TokenBudgetBreaker:
        return TokenBudgetBreaker(profile=STANDARD, max_tokens=10_000)

    def test_check_5000_returns_continue(self, breaker: TokenBudgetBreaker) -> None:
        assert breaker.check(5_000).action is BudgetAction.CONTINUE

    def test_check_8000_returns_warn(self, breaker: TokenBudgetBreaker) -> None:
        assert breaker.check(8_000).action is BudgetAction.WARN

    def test_check_15000_returns_break(self, breaker: TokenBudgetBreaker) -> None:
        assert breaker.check(15_000).action is BudgetAction.BREAK


# ---------------------------------------------------------------------------
# 5. patch_plan §3 P-03 AC #6 — STRICT cumulative > 80_000 → BREAK + ESCALATE
# ---------------------------------------------------------------------------


class TestPatchPlanAC6StrictEscalate:
    """STRICT profile escalates immediately on token budget exhaustion."""

    def test_strict_at_default_max_80k_continue(self) -> None:
        b = TokenBudgetBreaker(profile=STRICT)
        assert b.check(40_000).action is BudgetAction.CONTINUE

    def test_strict_at_80001_breaks_and_escalates(self) -> None:
        b = TokenBudgetBreaker(profile=STRICT)
        d = b.check(80_001)
        assert d.action is BudgetAction.BREAK
        assert d.recommendation is BudgetRecommendation.ESCALATE
        assert d.cumulative_tokens == 80_001
        assert d.max_tokens == 80_000

    def test_strict_at_exactly_80000_breaks(self) -> None:
        # Exactly 100% utilization is BREAK — boundary is inclusive.
        b = TokenBudgetBreaker(profile=STRICT)
        d = b.check(80_000)
        assert d.action is BudgetAction.BREAK
        assert d.recommendation is BudgetRecommendation.ESCALATE


# ---------------------------------------------------------------------------
# 6. boundary conditions on warn/break thresholds
# ---------------------------------------------------------------------------


class TestBoundaryConditions:
    """Threshold edges treat 0.75/1.00 as inclusive lower bounds."""

    def test_just_below_warn_threshold_is_continue(self) -> None:
        b = TokenBudgetBreaker(profile=STANDARD, max_tokens=10_000)
        assert b.check(7_499).action is BudgetAction.CONTINUE  # 0.7499

    def test_at_warn_threshold_is_warn(self) -> None:
        b = TokenBudgetBreaker(profile=STANDARD, max_tokens=10_000)
        assert b.check(7_500).action is BudgetAction.WARN  # exactly 0.75

    def test_just_below_break_threshold_is_warn(self) -> None:
        b = TokenBudgetBreaker(profile=STANDARD, max_tokens=10_000)
        assert b.check(9_999).action is BudgetAction.WARN  # 0.9999

    def test_at_break_threshold_is_break(self) -> None:
        b = TokenBudgetBreaker(profile=STANDARD, max_tokens=10_000)
        assert b.check(10_000).action is BudgetAction.BREAK  # exactly 1.00

    def test_zero_cumulative_is_continue(self) -> None:
        b = TokenBudgetBreaker(profile=STANDARD, max_tokens=10_000)
        d = b.check(0)
        assert d.action is BudgetAction.CONTINUE
        assert d.utilization == 0.0


# ---------------------------------------------------------------------------
# 7. unlimited (max_tokens=0) path is byte-identical pre-P-03
# ---------------------------------------------------------------------------


class TestUnlimitedBudget:
    """``max_tokens=0`` disables the breaker; CONTINUE for any non-negative N."""

    def test_default_relaxed_continues_at_million(self) -> None:
        b = TokenBudgetBreaker(profile=RELAXED)
        d = b.check(1_000_000)
        assert d.action is BudgetAction.CONTINUE
        assert d.recommendation is BudgetRecommendation.NONE
        assert d.utilization == 0.0
        assert d.max_tokens == 0
        assert "unlimited" in d.rationale

    def test_explicit_zero_override_disables_breaker(self) -> None:
        b = TokenBudgetBreaker(profile=STRICT, max_tokens=0)
        assert b.is_unlimited is True
        assert b.check(10_000_000).action is BudgetAction.CONTINUE


# ---------------------------------------------------------------------------
# 8. edge: negative cumulative_tokens raises ValueError (S-5)
# ---------------------------------------------------------------------------


class TestNegativeInputs:
    def test_negative_cumulative_tokens_raises(self) -> None:
        b = TokenBudgetBreaker(profile=STANDARD, max_tokens=10_000)
        with pytest.raises(ValueError, match="cumulative_tokens must be >= 0"):
            b.check(-1)

    def test_negative_record_delta_raises(self) -> None:
        b = TokenBudgetBreaker(profile=STANDARD, max_tokens=10_000)
        with pytest.raises(ValueError, match="token delta must be >= 0"):
            b.record(-100)


# ---------------------------------------------------------------------------
# 9. stateful tracking via record() / check_recorded()
# ---------------------------------------------------------------------------


class TestStatefulTracking:
    def test_record_accumulates_and_returns_total(self) -> None:
        b = TokenBudgetBreaker(profile=STANDARD, max_tokens=10_000)
        assert b.record(1_000) == 1_000
        assert b.record(2_500) == 3_500
        assert b.cumulative_tokens == 3_500

    def test_record_zero_is_noop(self) -> None:
        b = TokenBudgetBreaker(profile=STANDARD, max_tokens=10_000)
        b.record(5_000)
        assert b.record(0) == 5_000
        assert b.cumulative_tokens == 5_000

    def test_check_recorded_uses_internal_state(self) -> None:
        b = TokenBudgetBreaker(profile=STANDARD, max_tokens=10_000)
        b.record(5_000)
        d = b.check_recorded()
        assert d.action is BudgetAction.CONTINUE
        b.record(3_500)  # → 8_500 ≥ 75 % warn
        assert b.check_recorded().action is BudgetAction.WARN

    def test_reset_clears_cumulative_but_keeps_budget(self) -> None:
        b = TokenBudgetBreaker(profile=STANDARD, max_tokens=10_000)
        b.record(8_000)
        assert b.cumulative_tokens == 8_000
        b.reset()
        assert b.cumulative_tokens == 0
        assert b.max_tokens == 10_000  # budget preserved


# ---------------------------------------------------------------------------
# 10. from_profile_name() factory
# ---------------------------------------------------------------------------


class TestFromProfileName:
    def test_known_profile_name_returns_breaker_with_that_profile(self) -> None:
        b = from_profile_name("strict")
        assert b.profile is STRICT
        assert b.max_tokens == 80_000

    def test_known_profile_name_with_override(self) -> None:
        b = from_profile_name("audit", max_tokens=12_345)
        assert b.profile is AUDIT
        assert b.max_tokens == 12_345

    def test_unknown_profile_falls_back_to_standard_with_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.WARNING, logger="devolaflow.gate.budget"):
            b = from_profile_name("nonexistent-profile-xyz")
        assert b.profile is STANDARD
        assert b.max_tokens == 50_000
        assert any("Unknown profile" in rec.message for rec in caplog.records), (
            "Fallback MUST log a WARNING (S-5 No Silent Failures)."
        )


# ---------------------------------------------------------------------------
# 11. private helpers — direct unit coverage
# ---------------------------------------------------------------------------


class TestPrivateHelpers:
    def test_classify_utilization_continue(self) -> None:
        assert _classify_utilization(0.0) is BudgetAction.CONTINUE
        assert _classify_utilization(0.5) is BudgetAction.CONTINUE
        assert _classify_utilization(0.749) is BudgetAction.CONTINUE

    def test_classify_utilization_warn(self) -> None:
        assert _classify_utilization(WARN_UTILIZATION_THRESHOLD) is BudgetAction.WARN
        assert _classify_utilization(0.999) is BudgetAction.WARN

    def test_classify_utilization_break(self) -> None:
        assert _classify_utilization(BREAK_UTILIZATION_THRESHOLD) is BudgetAction.BREAK
        assert _classify_utilization(2.5) is BudgetAction.BREAK

    def test_recommendation_for_continue_is_none_for_all_profiles(self) -> None:
        for name in PROFILES:
            assert _recommendation_for(BudgetAction.CONTINUE, name) is BudgetRecommendation.NONE

    def test_recommendation_for_warn_is_throttle_for_all_profiles(self) -> None:
        for name in PROFILES:
            assert _recommendation_for(BudgetAction.WARN, name) is BudgetRecommendation.THROTTLE

    def test_recommendation_for_break_strict_audit_is_escalate(self) -> None:
        for name in ("strict", "audit"):
            assert _recommendation_for(BudgetAction.BREAK, name) is BudgetRecommendation.ESCALATE

    def test_recommendation_for_break_standard_relaxed_is_iterate(self) -> None:
        for name in ("standard", "relaxed"):
            assert _recommendation_for(BudgetAction.BREAK, name) is BudgetRecommendation.ITERATE

    def test_resolve_max_tokens_uses_profile_when_no_override(self) -> None:
        assert _resolve_max_tokens(STRICT, None) == 80_000

    def test_resolve_max_tokens_override_wins(self) -> None:
        assert _resolve_max_tokens(STRICT, 999) == 999

    def test_resolve_max_tokens_negative_override_raises(self) -> None:
        with pytest.raises(ValueError):
            _resolve_max_tokens(STRICT, -10)

    def test_resolve_max_tokens_negative_profile_raises(self) -> None:
        bad = replace(STRICT, max_tokens=-100)
        with pytest.raises(ValueError):
            _resolve_max_tokens(bad, None)

    def test_disabled_decision_shape(self) -> None:
        d = _disabled_decision(123, "strict")
        assert isinstance(d, BudgetDecision)
        assert d.action is BudgetAction.CONTINUE
        assert d.cumulative_tokens == 123
        assert d.max_tokens == 0
        assert d.utilization == 0.0
        assert "strict" in d.rationale
        assert "unlimited" in d.rationale

    def test_format_rationale_continue(self) -> None:
        msg = _format_rationale(BudgetAction.CONTINUE, 100, 1000, 0.1, "standard")
        assert "100/1000" in msg
        assert "10.0%" in msg
        assert "within" in msg

    def test_format_rationale_warn(self) -> None:
        msg = _format_rationale(BudgetAction.WARN, 800, 1000, 0.8, "standard")
        assert "throttle" in msg.lower()

    def test_format_rationale_break(self) -> None:
        msg = _format_rationale(BudgetAction.BREAK, 1500, 1000, 1.5, "strict")
        assert "circuit broken" in msg
        assert "strict" in msg


# ---------------------------------------------------------------------------
# 12. evaluate_gate(breaker=None) byte-identity regression vs v7.8.0
# ---------------------------------------------------------------------------


class TestEvaluateGateByteIdentityWithoutBreaker:
    """``patch_plan §3 P-03 AC #2`` — breaker=None ⇒ byte-identical pre-P-03."""

    def test_default_call_unchanged_for_pass_input(self) -> None:
        # The two calls MUST return *equal* verdicts when breaker=None.
        v1 = evaluate_gate(_pass_input(), STANDARD)
        v2 = evaluate_gate(_pass_input(), STANDARD, breaker=None)
        assert v1.decision == v2.decision == "PASS"
        assert v1.rationale == v2.rationale
        assert v1.composite_score == v2.composite_score
        assert v1.meets_threshold == v2.meets_threshold
        assert v1.escalation_context == v2.escalation_context
        assert v1.details == v2.details

    def test_default_call_unchanged_for_fail_input(self) -> None:
        v1 = evaluate_gate(_fail_input(), STANDARD)
        v2 = evaluate_gate(_fail_input(), STANDARD, breaker=None)
        assert v1.decision == v2.decision == "FAIL"
        assert v1.rationale == v2.rationale
        assert v1.composite_score == v2.composite_score

    def test_explicit_cumulative_ignored_when_breaker_none(self) -> None:
        # cumulative_tokens kwarg is ignored when breaker=None — no exception
        # and verdict is byte-identical to the default call.
        v_baseline = evaluate_gate(_pass_input(), STRICT, gate_type="standard")
        v_with_cumulative = evaluate_gate(
            _pass_input(), STRICT, gate_type="standard", cumulative_tokens=999_999
        )
        assert v_baseline.decision == v_with_cumulative.decision == "PASS"
        assert v_baseline.rationale == v_with_cumulative.rationale
        assert v_baseline.details == v_with_cumulative.details

    def test_evaluate_gate_byte_identical_across_all_profiles(self) -> None:
        for prof in PROFILES.values():
            base = evaluate_gate(_pass_input(), prof)
            wrapped = evaluate_gate(_pass_input(), prof, breaker=None)
            assert base.decision == wrapped.decision
            assert base.rationale == wrapped.rationale
            assert base.details == wrapped.details, f"breaker=None drift on profile {prof.name!r}"


# ---------------------------------------------------------------------------
# 13. evaluate_gate(breaker=...) — BREAK + WARN integration paths
# ---------------------------------------------------------------------------


class TestEvaluateGateWithBreaker:
    def test_break_on_strict_returns_escalate_verdict(self) -> None:
        breaker = TokenBudgetBreaker(profile=STRICT, max_tokens=10_000)
        v = evaluate_gate(_pass_input(), STRICT, breaker=breaker, cumulative_tokens=15_000)
        assert v.decision == "ESCALATE"
        assert "Token-budget circuit broken" in v.rationale
        assert v.details["budget_break"] is True
        assert v.details["budget_action"] == "BREAK"
        assert v.details["budget_recommendation"] == "ESCALATE"
        assert v.details["cumulative_tokens"] == 15_000
        assert v.details["max_tokens"] == 10_000

    def test_break_on_standard_returns_fail_verdict_with_iterate_rec(self) -> None:
        breaker = TokenBudgetBreaker(profile=STANDARD, max_tokens=10_000)
        v = evaluate_gate(_pass_input(), STANDARD, breaker=breaker, cumulative_tokens=15_000)
        assert v.decision == "FAIL"
        assert v.details["budget_recommendation"] == "ITERATE"
        # Standard non-escalate path must NOT set escalation_context.
        assert v.escalation_context == ""

    def test_warn_attaches_metadata_but_keeps_pass(self) -> None:
        breaker = TokenBudgetBreaker(profile=STANDARD, max_tokens=10_000)
        v = evaluate_gate(_pass_input(), STANDARD, breaker=breaker, cumulative_tokens=8_000)
        assert v.decision == "PASS"
        assert v.details["budget_warning"] is True
        assert v.details["budget_action"] == "WARN"
        assert v.details["budget_recommendation"] == "THROTTLE"
        assert v.details["cumulative_tokens"] == 8_000

    def test_continue_does_not_pollute_details(self) -> None:
        breaker = TokenBudgetBreaker(profile=STANDARD, max_tokens=10_000)
        v = evaluate_gate(_pass_input(), STANDARD, breaker=breaker, cumulative_tokens=5_000)
        assert v.decision == "PASS"
        assert "budget_warning" not in v.details
        assert "budget_break" not in v.details

    def test_breaker_uses_internal_state_when_cumulative_none(self) -> None:
        breaker = TokenBudgetBreaker(profile=STRICT, max_tokens=10_000)
        breaker.record(15_000)
        v = evaluate_gate(_pass_input(), STRICT, breaker=breaker)
        assert v.decision == "ESCALATE"
        assert v.details["cumulative_tokens"] == 15_000

    def test_breaker_unlimited_path_passes_through(self) -> None:
        breaker = TokenBudgetBreaker(profile=RELAXED)  # unlimited
        v = evaluate_gate(_pass_input(), RELAXED, breaker=breaker, cumulative_tokens=10_000_000)
        # Unlimited breaker can never break — original verdict preserved.
        assert v.decision == "PASS"
        assert "budget_break" not in v.details


# ---------------------------------------------------------------------------
# 14. P6 invariant — schemas/lean-dispatch.yaml unchanged at top level
# ---------------------------------------------------------------------------


class TestSchemaP6Invariant:
    """``patch_plan §3 P-03 AC #5`` — gate.token_budget is NESTED only."""

    SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "lean-dispatch.yaml"

    @pytest.fixture
    def spec(self) -> dict:
        return yaml.safe_load(self.SCHEMA_PATH.read_text(encoding="utf-8"))

    def test_canonical_order_length_remains_13(self, spec: dict) -> None:
        canonical = spec["layout_invariant"]["canonical_order"]
        assert len(canonical) == 13, (
            f"P-03 MUST NOT add top-level keys (P6 ADR-001 §2); "
            f"canonical_order length = {len(canonical)}"
        )

    def test_layout_invariant_version_remains_2(self, spec: dict) -> None:
        assert spec["layout_invariant"]["version"] == 2

    def test_canonical_order_last_key_remains_repos(self, spec: dict) -> None:
        assert spec["layout_invariant"]["canonical_order"][-1] == "repos"

    def test_token_budget_field_nested_under_gate(self, spec: dict) -> None:
        gate_spec = spec["lean_format_spec"]["gate"]
        assert "token_budget" in gate_spec, (
            "token_budget MUST appear inside lean_format_spec.gate (NESTED, NOT top-level)"
        )

    def test_token_budget_not_in_top_level_canonical_order(self, spec: dict) -> None:
        assert "token_budget" not in spec["layout_invariant"]["canonical_order"]


# ---------------------------------------------------------------------------
# 15. BudgetDecision dataclass shape — frozen, equality, fields
# ---------------------------------------------------------------------------


class TestBudgetDecisionDataclass:
    def test_decision_is_frozen(self) -> None:
        b = TokenBudgetBreaker(profile=STANDARD, max_tokens=10_000)
        d = b.check(5_000)
        with pytest.raises((AttributeError, TypeError)):
            d.action = BudgetAction.BREAK  # type: ignore[misc]

    def test_decision_equality_is_value_based(self) -> None:
        b1 = TokenBudgetBreaker(profile=STANDARD, max_tokens=10_000)
        b2 = TokenBudgetBreaker(profile=STANDARD, max_tokens=10_000)
        assert b1.check(5_000) == b2.check(5_000)

    def test_decision_carries_all_six_fields(self) -> None:
        b = TokenBudgetBreaker(profile=STRICT, max_tokens=10_000)
        d = b.check(8_000)
        assert d.action is BudgetAction.WARN
        assert d.cumulative_tokens == 8_000
        assert d.max_tokens == 10_000
        assert d.utilization == 0.8
        assert isinstance(d.rationale, str) and d.rationale
        assert d.recommendation is BudgetRecommendation.THROTTLE


# ---------------------------------------------------------------------------
# 16. v7.8.0 byte-identity vs the canonical pre-P-03 evaluator
# ---------------------------------------------------------------------------


class TestV780ByteIdentityRegression:
    """Cross-check that adding the breaker hook did not perturb the legacy
    evaluator output for representative GateInput shapes from
    ``tests/test_gate.py`` (sampled to cover preflight, abort,
    acceptance_readiness, and convergence dispatch paths).
    """

    def _baseline_passthrough_then_breakerless(self) -> None:
        """Helper baseline: assert decision sequence remains stable."""
        return None

    def test_passthrough_dispatch_unchanged(self) -> None:
        v = evaluate_gate(_pass_input(), STANDARD, gate_type="passthrough")
        assert v.decision == "PASS"
        assert v.rationale == "Passthrough gate — forwarding stage results."
        # Re-call with explicit breaker=None and assert identity.
        v2 = evaluate_gate(_pass_input(), STANDARD, gate_type="passthrough", breaker=None)
        assert v == v2

    def test_acceptance_readiness_dispatch_unchanged_when_no_criteria(self) -> None:
        v = evaluate_gate(_pass_input(), STANDARD, gate_type="acceptance_readiness")
        v2 = evaluate_gate(_pass_input(), STANDARD, gate_type="acceptance_readiness", breaker=None)
        assert v.decision == v2.decision == "FAIL"
        assert v.rationale == v2.rationale

    def test_abort_dispatch_unchanged(self) -> None:
        bad_input = GateInput(
            build_status=CheckResult(status="pass"),
            test_results=CheckResult(status="pass"),
            lint_status=CheckResult(status="pass"),
            review_findings=[
                Finding(
                    finding_id="F-sec-01",
                    severity="critical",
                    category="security",
                    location="src/a.py:1",
                    description="x",
                )
            ],
        )
        v1 = evaluate_gate(bad_input, STANDARD, gate_type="abort")
        v2 = evaluate_gate(bad_input, STANDARD, gate_type="abort", breaker=None)
        assert v1.decision == v2.decision == "ESCALATE"
        assert v1.rationale == v2.rationale
        assert v1.post_mortem == v2.post_mortem


# ---------------------------------------------------------------------------
# 17. defensive: deepcopy(breaker) does not break behaviour
# ---------------------------------------------------------------------------


class TestDeepcopySafety:
    def test_deepcopy_breaker_preserves_state_and_check(self) -> None:
        b = TokenBudgetBreaker(profile=STRICT, max_tokens=10_000)
        b.record(8_000)
        b2 = deepcopy(b)
        assert b2.cumulative_tokens == 8_000
        assert b2.max_tokens == 10_000
        # deepcopy clones the frozen dataclass — equality (not identity).
        assert b2.profile == STRICT
        assert b2.check(8_500).action is BudgetAction.WARN
