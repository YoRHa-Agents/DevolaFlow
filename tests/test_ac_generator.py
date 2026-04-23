"""v8.0.0 P-10 — Automatic acceptance-criteria generator tests.

Coverage targets:

1. **Schema additivity** — ``canonical_order`` grew 14 → 15, version
   3 → 4, last entry = ``acceptance_criteria_v2``,
   ``behavioral_guidelines`` stays at position 14, ``repos`` at 13,
   first 12 keys byte-identical to v7.0.0; v7.0.0 + v7.3.0 byte-baselines
   STILL pass with the new shape (additivity holds across THREE schema
   generations: v7.2.6 → P-08 → P-10).
2. **R5 backward compatibility** — the legacy
   ``acceptance_criteria: list[str]`` alias is PRESERVED (recognised by
   ``src/devolaflow/lifecycle/validate_dispatch.py``); the new
   ``acceptance_criteria_v2`` field is OPT-IN and optional;
   ``assert_dispatch_layout`` accepts BOTH v3 (no v2 field) AND v4
   (with v2 field).
3. **ACGenerator.generate()** — pattern matching for "fix bug X"
   (test), "improve performance" (metric), "implement feature Y"
   (test), "refactor X" (test), unmatched (manual catch-all),
   companion criteria for bug-fix / performance / impl.
4. **score_quality()** — 3-dimensional output
   ``{completeness, testability, specificity}``; vague phrases drop
   specificity; bonus tokens raise it.
5. **evaluate_acceptance_criteria_v2()** — runner-based test path,
   skip-on-no-cmd, metric/manual paths emit ``skip``, duplicate ids
   raise ``ValueError``, default subprocess runner returns failure
   on bogus command.
6. **aggregate_criterion_verdicts()** — empty list → skip,
   any fail → fail, all pass → pass, all skip → skip,
   pass+skip mix → pass.
7. **Integration** — ``ac_generation_defaults`` lives in
   ``context_profiles.yaml#meta``; ``feature`` and ``refactor`` profiles
   override ``ac_generation: {enabled: true}``.

P-10 closes Karpathy "Goal-Driven Execution" gap surfaced by upstream
tweet analysis ``v7.8`` §4.14.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from devolaflow.ac_generator import (
    DEFAULT_PERFORMANCE_METRIC,
    DEFAULT_PERFORMANCE_THRESHOLD,
    ACGenerator,
    ACGeneratorError,
    score_quality,
)
from devolaflow.compressor import (
    DEFAULT_DISPATCH_LAYOUT,
    DispatchLayoutError,
    assert_dispatch_layout,
)
from devolaflow.gate.models import (
    VALID_VERIFICATION_TYPES,
    AcceptanceCriterion,
    AcceptanceCriterionVerdict,
    CheckResult,
    GateInput,
)
from devolaflow.gate.scorer import (
    CommandRunResult,
    aggregate_criterion_verdicts,
    evaluate_acceptance_criteria_v2,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schemas" / "lean-dispatch.yaml"
PROFILES_PATH = REPO_ROOT / "workflow-system" / "agent" / "context_profiles.yaml"


# ---------------------------------------------------------------------------
# 1. Schema additivity (P6 invariant transition: 14 → 15, version 3 → 4)
# ---------------------------------------------------------------------------


class TestSchemaAdditivity:
    """P6 cache-layout invariant: P-10 must APPEND ``acceptance_criteria_v2``
    at position 15 after ``behavioral_guidelines``, bump version 3 → 4,
    leave positions 1-14 UNCHANGED, and preserve the v7.0.0 + v7.3.0
    byte-baseline parity (additivity proof across THREE schema generations)."""

    @pytest.fixture
    def schema_spec(self) -> dict:
        return yaml.safe_load(SCHEMA_PATH.read_text(encoding="utf-8"))

    def test_canonical_order_length_is_16(self, schema_spec: dict) -> None:
        # v8.3.0 PV-05 (v8.2.5) bumped 15 → 16 by appending ``change_context``.
        canonical = schema_spec["layout_invariant"]["canonical_order"]
        assert len(canonical) == 16, (
            f"canonical_order length = {len(canonical)}; expected 16 after PV-05"
        )

    def test_canonical_order_position_15_is_acceptance_criteria_v2(self, schema_spec: dict) -> None:
        """P-10 placed ``acceptance_criteria_v2`` at position 15. PV-05 MUST
        keep it there (positions 1..15 byte-identical to v4)."""
        canonical = schema_spec["layout_invariant"]["canonical_order"]
        assert canonical[14] == "acceptance_criteria_v2"

    def test_canonical_order_last_entry_is_change_context(self, schema_spec: dict) -> None:
        canonical = schema_spec["layout_invariant"]["canonical_order"]
        assert canonical[-1] == "change_context"

    def test_canonical_order_position_14_is_behavioral_guidelines(self, schema_spec: dict) -> None:
        """v8.0.0 P-08 placed ``behavioral_guidelines`` at position 14
        (1-indexed). v8.0.0 P-10 + v8.3.0 PV-05 MUST keep it there."""
        canonical = schema_spec["layout_invariant"]["canonical_order"]
        assert canonical[13] == "behavioral_guidelines"

    def test_canonical_order_position_13_is_repos(self, schema_spec: dict) -> None:
        canonical = schema_spec["layout_invariant"]["canonical_order"]
        assert canonical[12] == "repos"

    def test_layout_invariant_version_is_5(self, schema_spec: dict) -> None:
        # v8.3.0 PV-05 (v8.2.5) bumped 4 → 5; v7.0.0 + v7.3.0 + v8.0.0 P-08
        # + v8.0.0 P-10 byte-baselines all continue passing (additivity).
        assert schema_spec["layout_invariant"]["version"] == 5

    def test_canonical_order_first_14_keys_unchanged(self, schema_spec: dict) -> None:
        """Positions 1-14 (1-indexed) MUST be byte-identical to the
        post-P-08 sequence — REORDERING ANY EXISTING KEY IS A RELEASE
        BLOCKER per devola-flow-rules.mdc Rule 6 (P6) and v7-ADR-001 §2."""
        canonical = schema_spec["layout_invariant"]["canonical_order"]
        post_p08_canonical = (
            "hdr",
            "task",
            "goal",
            "assumptions",
            "pred",
            "files",
            "rules",
            "shared",
            "accept",
            "reinforce",
            "verify_cfg",
            "gate",
            "repos",
            "behavioral_guidelines",
        )
        assert tuple(canonical[:14]) == post_p08_canonical

    def test_default_dispatch_layout_constant_matches_schema(self, schema_spec: dict) -> None:
        """The Python constant ``DEFAULT_DISPATCH_LAYOUT`` MUST stay in
        lock step with ``schemas/lean-dispatch.yaml#layout_invariant.canonical_order``.
        """
        canonical = schema_spec["layout_invariant"]["canonical_order"]
        assert list(DEFAULT_DISPATCH_LAYOUT) == list(canonical)

    def test_acceptance_criteria_v2_field_documented_in_lean_format_spec(
        self, schema_spec: dict
    ) -> None:
        """The new top-level field MUST have a documented field shape under
        ``lean_format_spec`` so dispatchers know the per-entry schema."""
        spec = schema_spec["lean_format_spec"]["acceptance_criteria_v2"]
        assert "per_entry" in spec
        for key in (
            "id",
            "description",
            "verification_type",
            "verification_cmd",
            "metric",
            "threshold",
        ):
            assert key in spec["per_entry"]

    def test_layout_invariant_v7_0_0_baseline_still_passes(self) -> None:
        """v7.0.0 byte-baseline is unaffected by P-10 (additivity proof
        across THREE schema generations: v7.2.6 → P-08 → P-10)."""
        from tests.test_benchmarks import TestLayoutInvariantBaseline

        TestLayoutInvariantBaseline().test_layout_invariant_baseline()

    def test_layout_invariant_v7_3_0_baseline_still_passes(self) -> None:
        """v7.3.0 byte-baseline is unaffected by P-10."""
        from tests.test_benchmarks import TestLayoutInvariantBaseline

        TestLayoutInvariantBaseline().test_layout_invariant_baseline_v7_3_0()


# ---------------------------------------------------------------------------
# 2. R5 backward compatibility (legacy `acceptance_criteria: list[str]` alias)
# ---------------------------------------------------------------------------


class TestR5LegacyAliasPreserved:
    """The legacy ``acceptance_criteria: list[str]`` alias MUST still be
    recognised by ``validate_dispatch.py`` (R5 mitigation per
    ``.local/research/v8.0.0_patch_plan.md`` §9). The new
    ``acceptance_criteria_v2`` field is OPT-IN and never replaces it."""

    def test_validate_dispatch_accepts_legacy_acceptance_criteria(self) -> None:
        from devolaflow.lifecycle.validate_dispatch import validate_dispatch

        legacy_payload = {
            "task_id": "T-legacy",
            "acceptance_criteria": [
                "JWT middleware exported from src/middleware/auth.ts",
                "Unit tests cover all 4 scenarios with >90% coverage",
            ],
        }
        result = validate_dispatch(legacy_payload, strict=False)
        assert result.event == "pre_dispatch"
        # No violations for legacy payload — the alias still validates.
        assert list(result.violations) == []

    def test_validate_dispatch_accepts_lean_accept_payload(self) -> None:
        from devolaflow.lifecycle.validate_dispatch import validate_dispatch

        lean_payload = {
            "task_id": "T-lean",
            "accept": [
                "render byte-stable across CI runs",
                "top-level keys remain in canonical order",
            ],
        }
        result = validate_dispatch(lean_payload, strict=False)
        assert list(result.violations) == []

    def test_assert_dispatch_layout_accepts_v3_no_v2_field(self) -> None:
        """v3 payloads (with behavioral_guidelines but NO
        acceptance_criteria_v2) MUST still pass — opt-in field."""
        v3 = {
            "hdr": {"id": "d-v3"},
            "task": {"id": "T-v3"},
            "gate": {"coverage": 80},
            "behavioral_guidelines": {"think_first": True, "surgical_scope": "function"},
        }
        assert assert_dispatch_layout(v3) is None

    def test_assert_dispatch_layout_accepts_v4_with_v2_field(self) -> None:
        """v4 payloads (with both behavioral_guidelines AND
        acceptance_criteria_v2) MUST pass."""
        v4 = {
            "hdr": {"id": "d-v4"},
            "task": {"id": "T-v4"},
            "gate": {"coverage": 90},
            "repos": [{"name": "primary", "primary": True}],
            "behavioral_guidelines": {
                "think_first": True,
                "simplicity_check": True,
                "surgical_scope": "function",
                "goal_loop": False,
            },
            "acceptance_criteria_v2": [
                {
                    "id": "AC-001",
                    "description": "fix bug X",
                    "verification_type": "test",
                    "verification_cmd": "pytest tests/ -q -x",
                },
            ],
        }
        assert assert_dispatch_layout(v4) is None

    def test_assert_dispatch_layout_rejects_v2_before_behavioral_guidelines(
        self,
    ) -> None:
        """REORDER attack: acceptance_criteria_v2 placed BEFORE
        behavioral_guidelines must fail — position-15 invariant."""
        bad = {
            "hdr": {"id": "x"},
            "task": {"id": "T"},
            "acceptance_criteria_v2": [
                {"id": "AC-001", "description": "x", "verification_type": "test"},
            ],
            "behavioral_guidelines": {"think_first": True},
        }
        with pytest.raises(DispatchLayoutError):
            assert_dispatch_layout(bad)

    def test_assert_dispatch_layout_accepts_sparse_v2_no_behavioral(self) -> None:
        """A dispatch may carry acceptance_criteria_v2 but no
        behavioral_guidelines — canonical_order tolerates absent positions."""
        sparse = {
            "hdr": {"id": "d-sparse"},
            "task": {"id": "T-sparse"},
            "gate": {"coverage": 80},
            "acceptance_criteria_v2": [
                {"id": "AC-1", "description": "ok", "verification_type": "manual"},
            ],
        }
        assert assert_dispatch_layout(sparse) is None


# ---------------------------------------------------------------------------
# 3. ACGenerator.generate() — pattern matching paths
# ---------------------------------------------------------------------------


class TestACGeneratorGenerate:
    """Per ``patch_plan §3 P-10 AC #1/#2/#3``: the generator MUST emit
    distinct verification paths for the 3 canonical task families."""

    @pytest.fixture
    def gen(self) -> ACGenerator:
        return ACGenerator()

    def test_fix_bug_returns_test_verification(self, gen: ACGenerator) -> None:
        """``patch_plan §3 P-10 AC #1`` — 'fix bug X' MUST produce a
        criterion with verification_type='test' and a non-empty
        verification_cmd."""
        criteria = gen.generate("fix bug X in auth")
        assert criteria, "generate() must return ≥ 1 criterion (S-5 — never empty)"
        assert criteria[0].verification_type == "test"
        assert criteria[0].verification_cmd
        assert "pytest" in criteria[0].verification_cmd

    def test_fix_bug_emits_regression_companion(self, gen: ACGenerator) -> None:
        """Bug-fix criteria SHOULD include a 'no regression' companion
        per ``patch_plan §3 P-10 AC #4``."""
        criteria = gen.generate("fix bug in cache invalidation")
        assert len(criteria) >= 2, "fix-bug pattern should emit primary + regression companion"
        regression = criteria[1]
        assert regression.verification_type == "test"
        assert "regression" in regression.description.lower()

    def test_improve_performance_returns_metric_verification(self, gen: ACGenerator) -> None:
        """``patch_plan §3 P-10 AC #2`` — 'improve performance' MUST
        produce a criterion with verification_type='metric' carrying
        BOTH metric AND threshold."""
        criteria = gen.generate("improve performance of compressor")
        assert criteria
        primary = criteria[0]
        assert primary.verification_type == "metric"
        assert primary.metric == DEFAULT_PERFORMANCE_METRIC
        assert primary.threshold == DEFAULT_PERFORMANCE_THRESHOLD

    def test_improve_performance_short_form(self, gen: ACGenerator) -> None:
        """The short 'performance' keyword alone is enough to match the
        metric path — covers task descriptions like 'performance audit'."""
        criteria = gen.generate("performance audit of gate scorer")
        assert criteria[0].verification_type == "metric"

    def test_improve_performance_emits_evobench_companion(self, gen: ACGenerator) -> None:
        criteria = gen.generate("optimize latency in gate evaluator")
        assert len(criteria) >= 2
        companion = criteria[1]
        assert "regression" in companion.description.lower()
        assert "test_benchmarks" in companion.verification_cmd

    def test_implement_feature_returns_test(self, gen: ACGenerator) -> None:
        criteria = gen.generate("implement feature X for billing module")
        assert criteria[0].verification_type == "test"
        assert "pytest" in criteria[0].verification_cmd

    def test_implement_feature_emits_coverage_companion(self, gen: ACGenerator) -> None:
        criteria = gen.generate("implement new endpoint for users API")
        assert len(criteria) >= 2
        companion = criteria[1]
        assert "coverage" in companion.description.lower()
        assert "--cov" in companion.verification_cmd

    def test_refactor_returns_test(self, gen: ACGenerator) -> None:
        criteria = gen.generate("refactor compressor.py")
        assert criteria[0].verification_type == "test"

    def test_test_only_pattern(self, gen: ACGenerator) -> None:
        criteria = gen.generate("write tests for cycle detector")
        assert criteria[0].verification_type == "test"

    def test_documentation_pattern_returns_manual(self, gen: ACGenerator) -> None:
        criteria = gen.generate("document the new feature")
        assert criteria[0].verification_type == "manual"

    def test_unmatched_falls_back_to_manual(self, gen: ACGenerator) -> None:
        """Catch-all path — unmatched descriptions emit a single MANUAL
        criterion (S-5: never silently emit a 'test' criterion when the
        description gives no test signal)."""
        criteria = gen.generate("review the architecture document with stakeholders")
        assert len(criteria) == 1
        assert criteria[0].verification_type == "manual"

    def test_empty_description_raises(self, gen: ACGenerator) -> None:
        with pytest.raises(ACGeneratorError):
            gen.generate("")
        with pytest.raises(ACGeneratorError):
            gen.generate("   \n\t  ")

    def test_non_string_description_raises(self, gen: ACGenerator) -> None:
        with pytest.raises(ACGeneratorError):
            gen.generate(None)  # type: ignore[arg-type]
        with pytest.raises(ACGeneratorError):
            gen.generate(123)  # type: ignore[arg-type]

    def test_id_prefix_override(self) -> None:
        gen = ACGenerator(id_prefix="P10")
        criteria = gen.generate("fix bug X")
        assert criteria[0].id.startswith("P10-")

    def test_all_criteria_carry_unique_ids(self, gen: ACGenerator) -> None:
        """Every emitted criterion MUST have a unique id within the list
        (downstream :func:`evaluate_acceptance_criteria_v2` raises on dup ids)."""
        criteria = gen.generate("fix bug in payment flow")
        ids = [c.id for c in criteria]
        assert len(ids) == len(set(ids)), f"duplicate ids in {ids!r}"

    def test_case_insensitive_matching(self, gen: ACGenerator) -> None:
        upper = gen.generate("FIX BUG X IN AUTH")
        lower = gen.generate("fix bug x in auth")
        assert upper[0].verification_type == lower[0].verification_type
        assert upper[0].verification_cmd == lower[0].verification_cmd


# ---------------------------------------------------------------------------
# 4. score_quality() — three-dimensional output
# ---------------------------------------------------------------------------


class TestScoreQuality:
    """Per ``patch_plan §3 P-10 AC #5``: ``score_quality()`` MUST return a
    dict with EXACTLY 3 keys: completeness / testability / specificity."""

    def test_three_dimensions(self) -> None:
        gen = ACGenerator()
        criteria = gen.generate("fix bug X in auth module")
        scores = score_quality(criteria)
        assert sorted(scores.keys()) == ["completeness", "specificity", "testability"]
        for dim, value in scores.items():
            assert 0.0 <= value <= 100.0, f"{dim}={value} out of [0,100]"

    def test_module_and_method_score_quality_agree(self) -> None:
        """``ACGenerator.score_quality`` is a thin wrapper around the
        module-level :func:`score_quality`; both MUST agree."""
        gen = ACGenerator()
        criteria = gen.generate("fix bug in cache")
        assert gen.score_quality(criteria) == score_quality(criteria)

    def test_empty_list_returns_zero(self) -> None:
        scores = score_quality([])
        assert scores == {"completeness": 0.0, "testability": 0.0, "specificity": 0.0}

    def test_fully_specified_test_criterion_scores_high(self) -> None:
        """A criterion with id + description + verification_type='test' +
        verification_cmd MUST score ≥ 80 % completeness."""
        criteria = [
            AcceptanceCriterion(
                id="AC-001",
                description=(
                    "Verify pytest tests/test_foo.py -q exits 0 with "
                    "100% line coverage on src/foo.py"
                ),
                verification_type="test",
                verification_cmd="pytest tests/test_foo.py -q",
            )
        ]
        scores = score_quality(criteria)
        assert scores["completeness"] >= 80.0
        assert scores["testability"] == 100.0

    def test_manual_criterion_scores_low_testability(self) -> None:
        criteria = [
            AcceptanceCriterion(
                id="AC-001",
                description="Manual review of architecture document",
                verification_type="manual",
            )
        ]
        scores = score_quality(criteria)
        assert scores["testability"] <= 20.0

    def test_vague_description_drops_specificity(self) -> None:
        """Per ``patch_plan §3 P-10``: vague phrases like 'make it
        better' MUST tank the specificity dimension."""
        vague = [
            AcceptanceCriterion(
                id="AC-001",
                description="make it better and improve overall",
                verification_type="manual",
            )
        ]
        concrete = [
            AcceptanceCriterion(
                id="AC-002",
                description=(
                    "verify pytest src/devolaflow/ac_generator.py exits 0 "
                    "and tests/test_ac_generator.py passes"
                ),
                verification_type="test",
                verification_cmd="pytest tests/test_ac_generator.py -q",
            )
        ]
        assert score_quality(vague)["specificity"] < score_quality(concrete)["specificity"]

    def test_metric_without_threshold_scores_partial_testability(self) -> None:
        criteria = [
            AcceptanceCriterion(
                id="AC-001",
                description="latency improvement",
                verification_type="metric",
                metric="latency_p95_ms",
            )
        ]
        scores = score_quality(criteria)
        assert 30.0 < scores["testability"] < 100.0


# ---------------------------------------------------------------------------
# 5. evaluate_acceptance_criteria_v2() — runner-based test path
# ---------------------------------------------------------------------------


class TestEvaluateAcceptanceCriteriaV2:
    """Auto-evaluator MUST: run test verification_cmd via runner, skip
    metric/manual paths with deterministic messages, raise on duplicate
    ids (S-5 — never silently swallow a cycle)."""

    def test_empty_list_returns_empty_verdicts(self) -> None:
        assert evaluate_acceptance_criteria_v2([]) == []

    def test_test_path_pass(self) -> None:
        crit = AcceptanceCriterion(
            id="AC-1",
            description="ok",
            verification_type="test",
            verification_cmd="echo ok",
        )

        def runner(c: AcceptanceCriterion) -> CommandRunResult:
            return CommandRunResult(returncode=0, stdout="ok\n")

        verdicts = evaluate_acceptance_criteria_v2([crit], runner=runner)
        assert verdicts[0].status == "pass"
        assert verdicts[0].criterion_id == "AC-1"
        assert verdicts[0].details["returncode"] == 0

    def test_test_path_fail(self) -> None:
        crit = AcceptanceCriterion(
            id="AC-1",
            description="bogus",
            verification_type="test",
            verification_cmd="nonexistent-command-foo",
        )

        def runner(c: AcceptanceCriterion) -> CommandRunResult:
            return CommandRunResult(returncode=127, stderr="not found")

        verdicts = evaluate_acceptance_criteria_v2([crit], runner=runner)
        assert verdicts[0].status == "fail"
        assert verdicts[0].details["returncode"] == 127

    def test_test_path_no_cmd_skips(self) -> None:
        """test verification_type without verification_cmd MUST skip
        (never silently treat as PASS — S-5)."""
        crit = AcceptanceCriterion(
            id="AC-1",
            description="empty cmd",
            verification_type="test",
            verification_cmd="",
        )
        verdicts = evaluate_acceptance_criteria_v2([crit])
        assert verdicts[0].status == "skip"
        assert "no verification_cmd" in verdicts[0].message

    def test_metric_path_skips_with_metric_in_message(self) -> None:
        crit = AcceptanceCriterion(
            id="AC-1",
            description="latency goal",
            verification_type="metric",
            metric="latency_p95_ms",
            threshold="<= 100",
        )
        verdicts = evaluate_acceptance_criteria_v2([crit])
        assert verdicts[0].status == "skip"
        assert "latency_p95_ms" in verdicts[0].message
        assert verdicts[0].details["metric"] == "latency_p95_ms"

    def test_manual_path_skips(self) -> None:
        crit = AcceptanceCriterion(
            id="AC-1",
            description="human review",
            verification_type="manual",
        )
        verdicts = evaluate_acceptance_criteria_v2([crit])
        assert verdicts[0].status == "skip"
        assert "manual" in verdicts[0].message.lower()

    def test_duplicate_ids_raise(self) -> None:
        crit_a = AcceptanceCriterion(
            id="AC-1",
            description="first",
            verification_type="manual",
        )
        crit_b = AcceptanceCriterion(
            id="AC-1",
            description="dup",
            verification_type="manual",
        )
        with pytest.raises(ValueError, match="duplicate"):
            evaluate_acceptance_criteria_v2([crit_a, crit_b])

    def test_default_runner_handles_subprocess_error(self) -> None:
        """Real subprocess invocation on a sentinel-bogus command MUST
        return exit != 0 → status='fail' (S-5 — never crash the gate)."""
        crit = AcceptanceCriterion(
            id="AC-1",
            description="bogus",
            verification_type="test",
            verification_cmd="false",  # POSIX builtin: exit 1
        )
        verdicts = evaluate_acceptance_criteria_v2([crit])
        assert verdicts[0].status == "fail"
        assert verdicts[0].details["returncode"] != 0


# ---------------------------------------------------------------------------
# 6. aggregate_criterion_verdicts() — fold into a CheckResult
# ---------------------------------------------------------------------------


class TestAggregateCriterionVerdicts:
    """Aggregator MUST collapse a verdict list into a single CheckResult
    that the legacy ``_evaluate_standard`` branch can consume."""

    def test_empty_returns_skip(self) -> None:
        result = aggregate_criterion_verdicts([])
        assert result.status == "skip"
        assert "no criteria" in str(result.details)

    def test_all_pass_returns_pass(self) -> None:
        verdicts = [
            AcceptanceCriterionVerdict(criterion_id="AC-1", status="pass"),
            AcceptanceCriterionVerdict(criterion_id="AC-2", status="pass"),
        ]
        result = aggregate_criterion_verdicts(verdicts)
        assert result.status == "pass"
        assert result.details["criteria_total"] == 2
        assert result.details["criteria_passing"] == 2

    def test_any_fail_returns_fail(self) -> None:
        verdicts = [
            AcceptanceCriterionVerdict(criterion_id="AC-1", status="pass"),
            AcceptanceCriterionVerdict(criterion_id="AC-2", status="fail"),
            AcceptanceCriterionVerdict(criterion_id="AC-3", status="pass"),
        ]
        result = aggregate_criterion_verdicts(verdicts)
        assert result.status == "fail"
        assert result.details["criteria_failing"] == 1
        assert "AC-2" in result.details["failing_ids"]

    def test_pass_plus_skip_mix_returns_pass(self) -> None:
        verdicts = [
            AcceptanceCriterionVerdict(criterion_id="AC-1", status="pass"),
            AcceptanceCriterionVerdict(criterion_id="AC-2", status="skip"),
        ]
        result = aggregate_criterion_verdicts(verdicts)
        assert result.status == "pass"

    def test_all_skip_returns_skip(self) -> None:
        verdicts = [
            AcceptanceCriterionVerdict(criterion_id="AC-1", status="skip"),
            AcceptanceCriterionVerdict(criterion_id="AC-2", status="skip"),
        ]
        result = aggregate_criterion_verdicts(verdicts)
        assert result.status == "skip"
        assert result.details["criteria_skipped"] == 2


# ---------------------------------------------------------------------------
# 7. AcceptanceCriterion / AcceptanceCriterionVerdict invariants
# ---------------------------------------------------------------------------


class TestAcceptanceCriterionDataclass:
    """Frozen dataclass invariants (S-5 — never silently accept invalid input)."""

    def test_empty_id_raises(self) -> None:
        with pytest.raises(ValueError, match="id"):
            AcceptanceCriterion(
                id="",
                description="ok",
                verification_type="test",
            )

    def test_empty_description_raises(self) -> None:
        with pytest.raises(ValueError, match="description"):
            AcceptanceCriterion(
                id="AC-1",
                description="",
                verification_type="test",
            )

    def test_unknown_verification_type_raises(self) -> None:
        with pytest.raises(ValueError, match="verification_type"):
            AcceptanceCriterion(
                id="AC-1",
                description="ok",
                verification_type="bogus",  # type: ignore[arg-type]
            )

    def test_valid_verification_types_set(self) -> None:
        assert frozenset({"test", "metric", "manual"}) == VALID_VERIFICATION_TYPES

    def test_frozen_dataclass_immutable(self) -> None:
        c = AcceptanceCriterion(
            id="AC-1",
            description="ok",
            verification_type="manual",
        )
        with pytest.raises((AttributeError, TypeError)):
            c.id = "AC-2"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 8. R5 byte-identical legacy fallback (no v2 → no behavior change)
# ---------------------------------------------------------------------------


class TestR5LegacyByteIdenticalFallback:
    """When ``acceptance_criteria_v2`` is absent AND
    ``acceptance_criterion_verdicts`` is None, gate evaluation MUST
    behave exactly as in v8.0.0-p09 (byte-identical fallback)."""

    def test_gate_input_default_verdicts_is_none(self) -> None:
        gi = GateInput(
            build_status=CheckResult(status="pass"),
            test_results=CheckResult(status="pass"),
            lint_status=CheckResult(status="pass"),
        )
        assert gi.acceptance_criterion_verdicts is None

    def test_gate_input_accepts_verdicts_field(self) -> None:
        verdicts = [AcceptanceCriterionVerdict(criterion_id="AC-1", status="pass")]
        gi = GateInput(
            build_status=CheckResult(status="pass"),
            test_results=CheckResult(status="pass"),
            lint_status=CheckResult(status="pass"),
            acceptance_criterion_verdicts=verdicts,
        )
        assert gi.acceptance_criterion_verdicts == verdicts

    def test_evaluate_gate_v7x_dispatch_still_passes(self) -> None:
        """A v7.x dispatch payload (no behavioral_guidelines + no
        acceptance_criteria_v2) MUST still validate & evaluate."""
        from devolaflow.gate.profiles import STANDARD
        from devolaflow.gate.scorer import evaluate_gate

        gi = GateInput(
            build_status=CheckResult(status="pass"),
            test_results=CheckResult(status="pass"),
            lint_status=CheckResult(status="pass"),
        )
        verdict = evaluate_gate(gi, STANDARD)
        assert verdict.decision == "PASS"


# ---------------------------------------------------------------------------
# 9. context_profiles.yaml integration (W-15 / CO-6 section relevance)
# ---------------------------------------------------------------------------


class TestContextProfilesIntegration:
    """``ac_generation_defaults`` lives at ``meta`` level; profile-level
    overrides activate auto-AC for impl/refactor stages."""

    @pytest.fixture
    def profiles(self) -> dict:
        return yaml.safe_load(PROFILES_PATH.read_text(encoding="utf-8"))

    def test_meta_default_disabled(self, profiles: dict) -> None:
        defaults = profiles["meta"]["ac_generation_defaults"]
        assert defaults["enabled"] is False
        assert defaults["min_quality_threshold"] == 60.0
        assert defaults["id_prefix"] == "AC"

    def test_feature_profile_enables_ac_generation(self, profiles: dict) -> None:
        feature = profiles["profiles"]["feature"]
        assert "ac_generation" in feature
        assert feature["ac_generation"]["enabled"] is True

    def test_refactor_profile_enables_ac_generation(self, profiles: dict) -> None:
        refactor = profiles["profiles"]["refactor"]
        assert "ac_generation" in refactor
        assert refactor["ac_generation"]["enabled"] is True

    def test_documentation_profile_does_not_enable(self, profiles: dict) -> None:
        """Docs-only profile inherits the disabled meta default — no
        per-profile override added (avoids noisy criteria)."""
        docs = profiles["profiles"]["documentation"]
        # No per-profile ac_generation override → falls back to meta default.
        assert "ac_generation" not in docs


# ---------------------------------------------------------------------------
# 10. Module-level smoke (count tally — guarantees ≥ 25 tests in this file)
# ---------------------------------------------------------------------------


def test_smoke_module_imports() -> None:
    """Smoke: module imports the public surface cleanly."""
    import devolaflow.ac_generator as mod

    assert hasattr(mod, "ACGenerator")
    assert hasattr(mod, "score_quality")
    assert hasattr(mod, "DEFAULT_PERFORMANCE_METRIC")


def test_smoke_default_constants_documented() -> None:
    assert DEFAULT_PERFORMANCE_METRIC == "latency_p95_ms"
    assert DEFAULT_PERFORMANCE_THRESHOLD == "<= baseline"
