"""Comprehensive tests for the v8.0.0 P-06 cycle-detection middleware.

Covers:

- All three detection paths (``exact_match`` / ``fuzzy_match`` /
  ``edit_oscillation``) per ``patch_plan §3 P-06 AC #1/#2/#3``.
- ``cycle_to_instruction`` MUST-NOT mandate formatting + deterministic id
  (``patch_plan §3 P-06 AC #4``).
- ``cycle_detector=None`` ⇒ ``evaluate_gate`` byte-identical to v7.8.0
  (``patch_plan §3 P-06 AC #6``).
- Integration with the scorer (``cycle_detected`` / ``cycle_details``
  attached to ``GateVerdict.details`` only when supplied + detected).
- Edge cases: empty history, single snapshot, duplicate signatures
  without files, invalid constructor args, wrong-typed inputs.
- Schema invariant: ``schemas/lean-dispatch.yaml#layout_invariant``
  ``canonical_order`` length = 14, ``version`` = 3 PRESERVED (P6).

Target: ≥ 95 % line coverage on ``src/devolaflow/gate/cycle_detector.py``
and on the new code paths in ``reinforcement.py`` / ``scorer.py``.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from devolaflow.gate.budget import TokenBudgetBreaker
from devolaflow.gate.cycle_detector import (
    EDIT_OSCILLATION_MIN_LEN,
    EXACT_MATCH_CRITICAL_RUN,
    EXACT_MATCH_MIN_RUN,
    FUZZY_MATCH_MIN_WINDOW,
    MIN_HISTORY_FOR_DETECTION,
    CycleDetector,
    _detect_edit_oscillation,
    _detect_exact_match,
    _detect_fuzzy_match,
    _jaccard,
    _make_snapshot,
    _no_cycle,
    _stringify,
)
from devolaflow.gate.models import (
    CYCLE_DEFAULT_SEVERITY,
    CheckResult,
    CycleReport,
    Finding,
    GateInput,
    StateSnapshot,
)
from devolaflow.gate.profiles import AUDIT, RELAXED, STANDARD, STRICT
from devolaflow.gate.reinforcement import (
    _CYCLE_FILES_INLINE_LIMIT,
    _format_cycle_files,
    _format_cycle_mandate,
    cycle_to_instruction,
)
from devolaflow.gate.scorer import _attach_cycle_report, evaluate_gate, evaluate_ladder

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


def _snap(
    round_num: int,
    signature: str,
    *,
    tokens: tuple[str, ...] = (),
    files: tuple[str, ...] = (),
) -> StateSnapshot:
    """Compact constructor for :class:`StateSnapshot` test data."""
    return StateSnapshot(
        round_num=round_num,
        signature=signature,
        tokens=tokens,
        files=files,
    )


def _pump(detector: CycleDetector, snapshots: list[StateSnapshot]) -> None:
    """Bulk-record ``snapshots`` into ``detector``."""
    for s in snapshots:
        detector.record(s)


# ---------------------------------------------------------------------------
# 1. Constructor / parameter validation
# ---------------------------------------------------------------------------


class TestConstructor:
    """``CycleDetector(window_size, similarity_threshold)`` validation."""

    def test_defaults(self) -> None:
        d = CycleDetector()
        assert d.window_size == 3
        assert d.similarity_threshold == 0.8
        assert d.history == []

    def test_custom_window(self) -> None:
        d = CycleDetector(window_size=5, similarity_threshold=0.9)
        assert d.window_size == 5
        assert d.similarity_threshold == 0.9

    def test_window_below_minimum_rejects(self) -> None:
        with pytest.raises(ValueError, match="window_size must be >= 3"):
            CycleDetector(window_size=2)

    def test_window_zero_rejects(self) -> None:
        with pytest.raises(ValueError, match="window_size must be >= 3"):
            CycleDetector(window_size=0)

    def test_threshold_above_one_rejects(self) -> None:
        with pytest.raises(ValueError, match=r"\[0\.0, 1\.0\]"):
            CycleDetector(similarity_threshold=1.5)

    def test_threshold_negative_rejects(self) -> None:
        with pytest.raises(ValueError, match=r"\[0\.0, 1\.0\]"):
            CycleDetector(similarity_threshold=-0.1)

    def test_threshold_zero_allowed(self) -> None:
        d = CycleDetector(similarity_threshold=0.0)
        assert d.similarity_threshold == 0.0

    def test_threshold_one_allowed(self) -> None:
        d = CycleDetector(similarity_threshold=1.0)
        assert d.similarity_threshold == 1.0


# ---------------------------------------------------------------------------
# 2. record / reset / detect_cycle on internal state
# ---------------------------------------------------------------------------


class TestRecordResetAndStatefulDetect:
    """The stateful API mirrors ``patch_plan §3 P-06`` ``record(sig)``."""

    def test_record_appends_and_detect_cycle_uses_history(self) -> None:
        d = CycleDetector()
        _pump(d, [_snap(1, "sig"), _snap(2, "sig")])
        report = d.detect_cycle()
        assert report.detected is True
        assert report.cycle_type == "exact_match"
        assert len(d.history) == 2

    def test_reset_clears_history(self) -> None:
        d = CycleDetector()
        _pump(d, [_snap(1, "sig"), _snap(2, "sig")])
        assert d.detect_cycle().detected is True
        d.reset()
        assert d.history == []
        assert d.detect_cycle().detected is False

    def test_record_rejects_non_state_snapshot(self) -> None:
        d = CycleDetector()
        with pytest.raises(TypeError, match="snapshot must be a StateSnapshot"):
            d.record("not a snapshot")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# 3. detect() — empty / single-snapshot history
# ---------------------------------------------------------------------------


class TestEmptyAndShortHistory:
    """Per ``patch_plan §3 P-06`` ``CycleReport(detected=False)`` for short."""

    def test_empty_history_returns_no_cycle(self) -> None:
        d = CycleDetector()
        report = d.detect([])
        assert report.detected is False
        assert report.cycle_type == "none"
        assert "insufficient history" in report.rationale
        assert report.severity == "info"

    def test_single_snapshot_returns_no_cycle(self) -> None:
        d = CycleDetector()
        report = d.detect([_snap(1, "only")])
        assert report.detected is False
        assert report.cycle_type == "none"
        assert "insufficient history" in report.rationale

    def test_no_cycle_carries_window_and_threshold(self) -> None:
        d = CycleDetector(window_size=4, similarity_threshold=0.9)
        report = d.detect([])
        assert report.window_size == 4
        assert report.threshold == 0.9


# ---------------------------------------------------------------------------
# 4. detect() — input validation
# ---------------------------------------------------------------------------


class TestDetectInputValidation:
    def test_detect_rejects_non_list(self) -> None:
        d = CycleDetector()
        # ``list("…")`` turns the string into per-character entries, so the
        # per-element type check fires first — both messages are surfaced
        # via TypeError per S-5 (no silent coercion of an unintended input).
        with pytest.raises(TypeError, match="must be a StateSnapshot"):
            d.detect("not a list")  # type: ignore[arg-type]

    def test_detect_rejects_dict(self) -> None:
        d = CycleDetector()
        with pytest.raises(TypeError):
            d.detect({"a": 1})  # type: ignore[arg-type]

    def test_detect_rejects_non_snapshot_element(self) -> None:
        d = CycleDetector()
        with pytest.raises(TypeError, match=r"round_history\[1\] must be a StateSnapshot"):
            d.detect([_snap(1, "ok"), "bad"])  # type: ignore[list-item]

    def test_detect_none_uses_internal_history(self) -> None:
        d = CycleDetector()
        d.record(_snap(1, "x"))
        d.record(_snap(2, "x"))
        # detect() with no arg → uses self.history
        report = d.detect()
        assert report.detected is True
        assert report.cycle_type == "exact_match"


# ---------------------------------------------------------------------------
# 5. exact_match — AC #1
# ---------------------------------------------------------------------------


class TestExactMatch:
    """``patch_plan §3 P-06 AC #1`` — 2 consecutive identical → exact_match."""

    def test_two_identical_signatures_fires_exact_match(self) -> None:
        d = CycleDetector()
        report = d.detect([_snap(1, "edit:a.py"), _snap(2, "edit:a.py")])
        assert report.detected is True
        assert report.cycle_type == "exact_match"
        assert report.severity == CYCLE_DEFAULT_SEVERITY["exact_match"]
        assert report.severity == "major"
        assert report.repeated_signatures == ("edit:a.py",)
        assert report.similarity == 1.0
        assert report.rounds == (1, 2)

    def test_three_identical_signatures_still_major(self) -> None:
        d = CycleDetector()
        report = d.detect(
            [_snap(1, "X"), _snap(2, "X"), _snap(3, "X")],
        )
        assert report.detected is True
        assert report.cycle_type == "exact_match"
        # 3 < EXACT_MATCH_CRITICAL_RUN (4) → severity stays major
        assert report.severity == "major"
        assert report.rounds == (1, 2, 3)

    def test_four_identical_escalates_to_critical(self) -> None:
        d = CycleDetector()
        history = [_snap(i, "Y") for i in range(1, EXACT_MATCH_CRITICAL_RUN + 1)]
        report = d.detect(history)
        assert report.detected is True
        assert report.cycle_type == "exact_match"
        assert report.severity == "critical"

    def test_exact_match_evidence_is_verbatim(self) -> None:
        d = CycleDetector()
        report = d.detect([_snap(7, "S"), _snap(8, "S")])
        assert any("round 7" in e for e in report.evidence)
        assert any("round 8" in e for e in report.evidence)
        assert any("'S'" in e for e in report.evidence)

    def test_exact_match_only_runs_at_tail(self) -> None:
        # A→A→B→B → only the trailing B-run counts.
        d = CycleDetector()
        report = d.detect(
            [_snap(1, "A"), _snap(2, "A"), _snap(3, "B"), _snap(4, "B")],
        )
        assert report.detected is True
        assert report.cycle_type == "exact_match"
        assert report.repeated_signatures == ("B",)
        assert report.rounds == (3, 4)

    def test_exact_match_includes_files_union(self) -> None:
        d = CycleDetector()
        report = d.detect(
            [
                _snap(1, "S", files=("a.py",)),
                _snap(2, "S", files=("a.py", "b.py")),
            ]
        )
        assert report.files == ("a.py", "b.py")

    def test_distinct_trailing_signatures_no_exact_match(self) -> None:
        report = _detect_exact_match([_snap(1, "X"), _snap(2, "Y")], 3, 0.8)
        assert report is None


# ---------------------------------------------------------------------------
# 6. fuzzy_match — AC #2
# ---------------------------------------------------------------------------


class TestFuzzyMatch:
    """``patch_plan §3 P-06 AC #2`` — ≥ window with pairwise Jaccard ≥ 0.8."""

    def _high_sim_snapshots(self) -> list[StateSnapshot]:
        # 9-token base; swap the last token each round → 8/10 = 0.8 Jaccard.
        base = ("a", "b", "c", "d", "e", "f", "g", "h")
        return [
            _snap(1, "s1", tokens=(*base, "i")),
            _snap(2, "s2", tokens=(*base, "j")),
            _snap(3, "s3", tokens=(*base, "k")),
        ]

    def test_three_high_similarity_rounds_fire_fuzzy(self) -> None:
        d = CycleDetector(window_size=3, similarity_threshold=0.8)
        report = d.detect(self._high_sim_snapshots())
        assert report.detected is True
        assert report.cycle_type == "fuzzy_match"
        assert report.similarity >= 0.8
        assert report.severity == "major"

    def test_low_similarity_does_not_fire(self) -> None:
        d = CycleDetector(window_size=3, similarity_threshold=0.9)
        report = d.detect(
            [
                _snap(1, "s1", tokens=("a", "b")),
                _snap(2, "s2", tokens=("c", "d")),
                _snap(3, "s3", tokens=("e", "f")),
            ]
        )
        assert report.detected is False

    def test_fuzzy_match_skipped_when_history_below_window(self) -> None:
        report = _detect_fuzzy_match(
            [_snap(1, "s1", tokens=("a", "b")), _snap(2, "s2", tokens=("a", "b"))],
            3,
            0.8,
        )
        assert report is None

    def test_fuzzy_match_skipped_when_tokens_empty(self) -> None:
        # No tokens → Jaccard collapses to 0.0 → run breaks.
        d = CycleDetector(window_size=3, similarity_threshold=0.8)
        report = d.detect(
            [
                _snap(1, "s1"),
                _snap(2, "s2"),
                _snap(3, "s3"),
            ]
        )
        assert report.detected is False
        assert report.cycle_type == "none"

    def test_fuzzy_match_avg_similarity_reported(self) -> None:
        d = CycleDetector(window_size=3, similarity_threshold=0.8)
        report = d.detect(self._high_sim_snapshots())
        assert report.similarity == pytest.approx(0.8, rel=0.05)

    def test_fuzzy_match_evidence_includes_tokens(self) -> None:
        d = CycleDetector(window_size=3, similarity_threshold=0.8)
        report = d.detect(self._high_sim_snapshots())
        assert any("tokens=" in e for e in report.evidence)

    def test_fuzzy_match_window_min_three_enforced_by_constant(self) -> None:
        # Even when caller passes window_size=3, the inner FUZZY_MATCH_MIN_WINDOW
        # constant guarantees ≥ 3 snapshots are inspected.
        assert FUZZY_MATCH_MIN_WINDOW == 3


# ---------------------------------------------------------------------------
# 7. edit_oscillation — AC #3
# ---------------------------------------------------------------------------


class TestEditOscillation:
    """``patch_plan §3 P-06 AC #3`` — A→B→A on a shared file = oscillation."""

    def test_basic_a_b_a_pattern(self) -> None:
        d = CycleDetector()
        report = d.detect(
            [
                _snap(1, "A", files=("x.py",)),
                _snap(2, "B", files=("x.py",)),
                _snap(3, "A", files=("x.py",)),
            ]
        )
        assert report.detected is True
        assert report.cycle_type == "edit_oscillation"
        assert report.severity == "major"
        assert report.repeated_signatures == ("A", "B")
        assert report.rounds == (1, 2, 3)
        assert report.files == ("x.py",)

    def test_a_b_a_b_at_tail_still_fires_oscillation(self) -> None:
        d = CycleDetector()
        report = d.detect(
            [
                _snap(1, "A", files=("x.py",)),
                _snap(2, "B", files=("x.py",)),
                _snap(3, "A", files=("x.py",)),
                _snap(4, "B", files=("x.py",)),
            ]
        )
        # Trailing window prev2=A, prev1=B, current=B → no exact_match, no
        # oscillation match (current != prev2). Wait: A,B,B at tail. prev2=B,
        # prev1=B, current=B is exact_match.
        # Actually history[-3:] = [snap(2,B), snap(3,A), snap(4,B)]
        # → prev2=B, prev1=A, current=B → matches A→B→A pattern? No, B→A→B.
        # That's still oscillation (just B-side instead of A-side).
        assert report.detected is True
        assert report.cycle_type == "edit_oscillation"
        assert report.repeated_signatures == ("B", "A")

    def test_no_shared_file_does_not_fire(self) -> None:
        d = CycleDetector()
        report = d.detect(
            [
                _snap(1, "A", files=("x.py",)),
                _snap(2, "B", files=("y.py",)),
                _snap(3, "A", files=("z.py",)),
            ]
        )
        # exact_match doesn't fire (only 1 trailing A). fuzzy_match needs
        # tokens. edit_oscillation needs shared files → no overlap → none.
        assert report.detected is False
        assert report.cycle_type == "none"

    def test_three_identical_does_not_fire_oscillation(self) -> None:
        # Three identical signatures → exact_match path (handled earlier).
        d = CycleDetector()
        report = d.detect(
            [
                _snap(1, "A", files=("x.py",)),
                _snap(2, "A", files=("x.py",)),
                _snap(3, "A", files=("x.py",)),
            ]
        )
        assert report.detected is True
        assert report.cycle_type == "exact_match"

    def test_internal_helper_returns_none_on_short_history(self) -> None:
        report = _detect_edit_oscillation(
            [_snap(1, "A"), _snap(2, "B")],
            3,
            0.8,
        )
        assert report is None

    def test_oscillation_evidence_marks_alternate_and_returned(self) -> None:
        d = CycleDetector()
        report = d.detect(
            [
                _snap(1, "A", files=("x.py",)),
                _snap(2, "B", files=("x.py",)),
                _snap(3, "A", files=("x.py",)),
            ]
        )
        assert any("alternate" in e for e in report.evidence)
        assert any("returned" in e for e in report.evidence)


# ---------------------------------------------------------------------------
# 8. detection ordering — exact_match wins over the others
# ---------------------------------------------------------------------------


class TestDetectionOrdering:
    def test_exact_match_wins_over_fuzzy(self) -> None:
        # All three trailing snapshots identical & high-Jaccard token overlap.
        d = CycleDetector(window_size=3, similarity_threshold=0.5)
        history = [
            _snap(1, "S", tokens=("a", "b", "c")),
            _snap(2, "S", tokens=("a", "b", "c")),
            _snap(3, "S", tokens=("a", "b", "c")),
        ]
        report = d.detect(history)
        assert report.cycle_type == "exact_match"

    def test_exact_match_wins_over_oscillation(self) -> None:
        d = CycleDetector()
        # If we pass [A, A, A] with shared files, oscillation pattern doesn't
        # apply (current == prev1) but exact_match does fire.
        history = [
            _snap(1, "A", files=("x.py",)),
            _snap(2, "A", files=("x.py",)),
            _snap(3, "A", files=("x.py",)),
        ]
        report = d.detect(history)
        assert report.cycle_type == "exact_match"


# ---------------------------------------------------------------------------
# 9. helpers — _jaccard / _stringify / _no_cycle / make_snapshot
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_jaccard_empty_pair_zero(self) -> None:
        assert _jaccard((), ()) == 0.0

    def test_jaccard_one_empty_zero(self) -> None:
        assert _jaccard(("a",), ()) == 0.0

    def test_jaccard_full_overlap_one(self) -> None:
        assert _jaccard(("a", "b"), ("a", "b")) == 1.0

    def test_jaccard_partial(self) -> None:
        assert _jaccard(("a", "b"), ("a", "c")) == pytest.approx(1 / 3)

    def test_stringify_none(self) -> None:
        assert _stringify(None) == ""

    def test_stringify_str(self) -> None:
        assert _stringify("abc") == "abc"

    def test_stringify_list(self) -> None:
        assert _stringify(["a", "b"]) == "a,b"

    def test_stringify_dict_sorted(self) -> None:
        # dict keys sorted for determinism
        assert _stringify({"b": 2, "a": 1}) == "a=1,b=2"

    def test_stringify_int(self) -> None:
        assert _stringify(42) == "42"

    def test_no_cycle_helper(self) -> None:
        report = _no_cycle("explicit reason", window_size=3, threshold=0.8)
        assert report.detected is False
        assert report.cycle_type == "none"
        assert report.rationale == "explicit reason"
        assert report.window_size == 3
        assert report.threshold == 0.8

    def test_make_snapshot_basic(self) -> None:
        s = _make_snapshot(1, tool="edit", payload={"file": "a.py"})
        assert s.round_num == 1
        assert s.signature.startswith("edit:")
        assert "a.py" in s.signature

    def test_make_snapshot_round_zero_rejects(self) -> None:
        with pytest.raises(ValueError, match="round_num must be >= 1"):
            _make_snapshot(0, tool="edit", payload="x")

    def test_make_snapshot_empty_tool_rejects(self) -> None:
        with pytest.raises(ValueError, match="tool must be a non-empty string"):
            _make_snapshot(1, tool="", payload="x")

    def test_make_snapshot_with_files_and_metadata(self) -> None:
        s = _make_snapshot(
            2,
            tool="write",
            payload={"path": "b.py", "size": 100},
            files=["b.py"],
            metadata={"task_id": "T01"},
        )
        assert s.files == ("b.py",)
        assert ("task_id", "T01") in s.metadata

    def test_record_tool_call_appends_and_returns_snapshot(self) -> None:
        d = CycleDetector()
        snap = d.record_tool_call(1, tool="edit", payload={"file": "x.py"})
        assert isinstance(snap, StateSnapshot)
        assert d.history == [snap]
        assert snap.signature.startswith("edit:")

    def test_record_tool_call_two_identical_fires_exact_match(self) -> None:
        d = CycleDetector()
        d.record_tool_call(1, tool="edit", payload={"file": "x.py"})
        d.record_tool_call(2, tool="edit", payload={"file": "x.py"})
        report = d.detect_cycle()
        assert report.detected is True
        assert report.cycle_type == "exact_match"


# ---------------------------------------------------------------------------
# 10. cycle_to_instruction — AC #4 (MUST NOT mandate)
# ---------------------------------------------------------------------------


class TestCycleToInstruction:
    """``patch_plan §3 P-06 AC #4`` — returns ``MUST NOT repeat`` rule."""

    def _exact_match_report(self) -> CycleReport:
        d = CycleDetector()
        return d.detect([_snap(1, "S"), _snap(2, "S")])

    def _fuzzy_match_report(self) -> CycleReport:
        base = ("a", "b", "c", "d", "e", "f", "g", "h")
        d = CycleDetector(window_size=3, similarity_threshold=0.7)
        return d.detect(
            [
                _snap(1, "s1", tokens=(*base, "i")),
                _snap(2, "s2", tokens=(*base, "j")),
                _snap(3, "s3", tokens=(*base, "k")),
            ]
        )

    def _oscillation_report(self) -> CycleReport:
        d = CycleDetector()
        return d.detect(
            [
                _snap(1, "A", files=("x.py",)),
                _snap(2, "B", files=("x.py",)),
                _snap(3, "A", files=("x.py",)),
            ]
        )

    def test_exact_match_rule_must_not_format(self) -> None:
        rule = cycle_to_instruction(self._exact_match_report())
        assert rule.mandate.startswith("MUST NOT repeat exact_match cycle")
        assert "signature=" in rule.mandate
        assert rule.severity in {"major", "critical"}
        assert rule.id == "C-exact_match-001"

    def test_fuzzy_match_rule_must_not_format(self) -> None:
        rule = cycle_to_instruction(self._fuzzy_match_report())
        assert "MUST NOT repeat fuzzy_match" in rule.mandate
        assert "Jaccard" in rule.mandate
        assert rule.id == "C-fuzzy_match-001"

    def test_oscillation_rule_must_not_format(self) -> None:
        rule = cycle_to_instruction(self._oscillation_report())
        assert "MUST NOT repeat edit_oscillation" in rule.mandate
        assert "shared file" in rule.mandate or "touching" in rule.mandate
        assert rule.id == "C-edit_oscillation-001"
        assert rule.file == "x.py"

    def test_severity_major_or_higher(self) -> None:
        # AC: severity ≥ major for any detected cycle.
        for report in (
            self._exact_match_report(),
            self._fuzzy_match_report(),
            self._oscillation_report(),
        ):
            rule = cycle_to_instruction(report)
            assert rule.severity in {"major", "critical", "blocker"}

    def test_sequence_drives_id(self) -> None:
        report = self._exact_match_report()
        assert cycle_to_instruction(report, sequence=2).id == "C-exact_match-002"
        assert cycle_to_instruction(report, sequence=42).id == "C-exact_match-042"

    def test_sequence_zero_rejects(self) -> None:
        with pytest.raises(ValueError, match="sequence must be >= 1"):
            cycle_to_instruction(self._exact_match_report(), sequence=0)

    def test_undetected_report_rejects(self) -> None:
        d = CycleDetector()
        report = d.detect([])
        with pytest.raises(ValueError, match="report.detected=False"):
            cycle_to_instruction(report)

    def test_non_report_rejects(self) -> None:
        with pytest.raises(TypeError, match="report must be a CycleReport"):
            cycle_to_instruction("not a report")  # type: ignore[arg-type]

    def test_severity_override(self) -> None:
        rule = cycle_to_instruction(self._fuzzy_match_report(), severity="critical")
        assert rule.severity == "critical"

    def test_mandate_truncates_under_token_budget(self) -> None:
        report = self._exact_match_report()
        rule = cycle_to_instruction(report, max_tokens=5)
        # 5 tokens × 4 chars = 20 chars; mandate should be truncated.
        assert rule.mandate.endswith("…")
        assert len(rule.mandate) <= 20

    def test_format_cycle_files_truncates_long_lists(self) -> None:
        rendered = _format_cycle_files(("a.py", "b.py", "c.py", "d.py", "e.py"))
        assert "more" in rendered
        assert _CYCLE_FILES_INLINE_LIMIT == 3

    def test_format_cycle_files_empty(self) -> None:
        assert _format_cycle_files(()) == ""

    def test_format_cycle_mandate_unknown_type_falls_back(self) -> None:
        # Build a synthetic report with an unknown cycle_type so the
        # mandate generator falls back to the generic guidance.
        report = CycleReport(
            detected=True,
            cycle_type="unknown_kind",  # type: ignore[arg-type]
            severity="major",
            evidence=("e",),
            repeated_signatures=("sig",),
            rationale="r",
        )
        text = _format_cycle_mandate(report)
        assert "vary the approach" in text
        assert "unknown_kind" in text


# ---------------------------------------------------------------------------
# 11. Scorer integration — cycle_detector=None byte-identical (AC #6)
# ---------------------------------------------------------------------------


class TestScorerByteIdenticalDefault:
    """``patch_plan §3 P-06 AC #6`` — None default = pre-P-06 byte-identical."""

    def test_evaluate_gate_default_arg_byte_identical(self) -> None:
        gi = _pass_input()
        v_default = evaluate_gate(gi, STANDARD)
        v_explicit_none = evaluate_gate(gi, STANDARD, cycle_detector=None)
        assert v_default.decision == v_explicit_none.decision
        assert v_default.rationale == v_explicit_none.rationale
        assert v_default.composite_score == v_explicit_none.composite_score
        assert v_default.meets_threshold == v_explicit_none.meets_threshold
        assert v_default.details == v_explicit_none.details
        assert v_default.escalation_context == v_explicit_none.escalation_context

    def test_evaluate_gate_supplied_detector_no_cycle_no_mutation(self) -> None:
        # Single snapshot → no cycle → details unchanged vs None.
        gi = _pass_input()
        d = CycleDetector()
        d.record(_snap(1, "unique"))
        v_with = evaluate_gate(gi, STANDARD, cycle_detector=d)
        v_without = evaluate_gate(gi, STANDARD, cycle_detector=None)
        assert v_with.decision == v_without.decision
        assert v_with.details == v_without.details
        assert "cycle_detected" not in v_with.details

    def test_evaluate_gate_with_cycle_attaches_details(self) -> None:
        gi = _pass_input()
        d = CycleDetector()
        _pump(d, [_snap(1, "S"), _snap(2, "S")])
        verdict = evaluate_gate(gi, STANDARD, cycle_detector=d)
        # Decision NOT mutated (S-5 — explicit signal, not silent escalate).
        assert verdict.decision == "PASS"
        # Cycle metadata appended.
        assert verdict.details["cycle_detected"] is True
        cd = verdict.details["cycle_details"]
        assert cd["cycle_type"] == "exact_match"
        assert cd["severity"] == "major"
        assert cd["rounds"] == [1, 2]

    def test_evaluate_gate_byte_identical_under_failing_input(self) -> None:
        # FAIL-side byte-identity: cycle_detector=None must not change FAIL.
        gi = _pass_input()
        gi.review_findings = [
            Finding(
                finding_id="F1",
                severity="blocker",
                category="test",
                location="x.py",
                description="d",
            )
        ]
        v_default = evaluate_gate(gi, STANDARD, gate_type="standard")
        v_explicit_none = evaluate_gate(gi, STANDARD, gate_type="standard", cycle_detector=None)
        assert v_default.decision == v_explicit_none.decision == "FAIL"
        assert v_default.details == v_explicit_none.details

    def test_evaluate_gate_with_cycle_and_breaker_break(self) -> None:
        # Even when the breaker fires BREAK first, the cycle metadata is
        # still appended so the orchestrator sees both signals.
        gi = _pass_input()
        breaker = TokenBudgetBreaker(profile=STANDARD, max_tokens=10_000)
        d = CycleDetector()
        _pump(d, [_snap(1, "S"), _snap(2, "S")])
        verdict = evaluate_gate(
            gi,
            STANDARD,
            breaker=breaker,
            cumulative_tokens=15_000,
            cycle_detector=d,
        )
        assert verdict.decision == "FAIL"  # BREAK on STANDARD
        assert verdict.details["budget_break"] is True
        assert verdict.details["cycle_detected"] is True


# ---------------------------------------------------------------------------
# 12. Ladder integration — cycle_detector forwarded
# ---------------------------------------------------------------------------


class TestLadderIntegration:
    def test_ladder_disabled_passes_cycle_through_to_evaluate_gate(self) -> None:
        gi = _pass_input()
        d = CycleDetector()
        _pump(d, [_snap(1, "S"), _snap(2, "S")])
        verdict = evaluate_ladder(gi, STANDARD, cycle_detector=d)
        # STANDARD has ladder_enabled=False → delegates to evaluate_gate
        # which attaches the cycle.
        assert verdict.details["cycle_detected"] is True
        assert verdict.details["cycle_details"]["cycle_type"] == "exact_match"

    def test_ladder_enabled_attaches_cycle_after_aggregation(self) -> None:
        gi = _pass_input()
        d = CycleDetector()
        _pump(d, [_snap(1, "S"), _snap(2, "S")])
        verdict = evaluate_ladder(gi, STRICT, cycle_detector=d)
        # STRICT has ladder_enabled=True; cycle is appended after the
        # ladder verdict is built.
        assert verdict.details["cycle_detected"] is True
        assert "ladder" in verdict.details

    def test_ladder_no_detector_byte_identical(self) -> None:
        gi = _pass_input()
        v_no_arg = evaluate_ladder(gi, STRICT)
        v_explicit = evaluate_ladder(gi, STRICT, cycle_detector=None)
        assert v_no_arg.details == v_explicit.details


# ---------------------------------------------------------------------------
# 13. attach helper
# ---------------------------------------------------------------------------


class TestAttachCycleReport:
    def test_attach_idempotent(self) -> None:
        # Second call should not overwrite an already-set value
        # (the helper uses setdefault per the byte-identity contract).
        from devolaflow.gate.models import GateVerdict

        verdict = GateVerdict(decision="PASS", rationale="r")
        report = CycleDetector().detect([_snap(1, "X"), _snap(2, "X")])
        _attach_cycle_report(verdict, report)
        first = deepcopy(verdict.details)
        _attach_cycle_report(verdict, report)
        assert verdict.details == first


# ---------------------------------------------------------------------------
# 14. Schema invariants — lean-dispatch P6, lean-report opt-in fields
# ---------------------------------------------------------------------------


class TestSchemaInvariants:
    """Verify P6 cache-layout invariant on lean-dispatch is preserved.

    P-06 only touches lean-report.yaml (no P6 invariant); lean-dispatch.yaml
    is set by the latest P6 transition. P-08 raised it to length 14 /
    version 3; P-10 raised it to length 15 / version 4 by APPENDING
    ``acceptance_criteria_v2`` after ``behavioral_guidelines``. The
    v7.0.0 + v7.3.0 byte-baselines in
    ``tests/test_layout_invariant_multi_baseline.py::TestMultiBaselineByteStability`` prove
    additivity across all three generations.
    """

    @staticmethod
    def _lean_dispatch_layout() -> dict[str, object]:
        path = Path(__file__).resolve().parent.parent / "schemas" / "lean-dispatch.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return data["layout_invariant"]

    def test_canonical_order_length_unchanged(self) -> None:
        # v9.7.0 PV-02 bumped 16 → 17 by appending ``predecessor_dedup_ledger``.
        layout = self._lean_dispatch_layout()
        assert len(layout["canonical_order"]) == 17

    def test_canonical_order_version_unchanged(self) -> None:
        # v9.7.0 PV-02 bumped version 5 → 6; positions 1..16 byte-identical.
        layout = self._lean_dispatch_layout()
        assert layout["version"] == 6

    def test_lean_report_carries_cycle_fields(self) -> None:
        path = Path(__file__).resolve().parent.parent / "schemas" / "lean-report.yaml"
        text = path.read_text(encoding="utf-8")
        assert "cycle_detected:" in text
        assert "cycle_details:" in text
        assert "cycle_type" in text


# ---------------------------------------------------------------------------
# 15. Profile-aware sanity — every registered profile accepts a detector
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("profile", [STRICT, STANDARD, RELAXED, AUDIT])
def test_every_profile_accepts_cycle_detector(profile) -> None:
    gi = _pass_input()
    d = CycleDetector()
    _pump(d, [_snap(1, "X"), _snap(2, "X")])
    verdict = evaluate_gate(gi, profile, cycle_detector=d)
    assert verdict.details["cycle_detected"] is True


@pytest.mark.parametrize("profile", [STRICT, STANDARD, RELAXED, AUDIT])
def test_every_profile_byte_identical_when_detector_none(profile) -> None:
    gi = _pass_input()
    v_default = evaluate_gate(gi, profile)
    v_none = evaluate_gate(gi, profile, cycle_detector=None)
    assert v_default.details == v_none.details


# ---------------------------------------------------------------------------
# 16. Constants sanity — keep documented thresholds verifiable
# ---------------------------------------------------------------------------


class TestConstants:
    def test_exact_match_min_run(self) -> None:
        assert EXACT_MATCH_MIN_RUN == 2

    def test_fuzzy_match_min_window(self) -> None:
        assert FUZZY_MATCH_MIN_WINDOW == 3

    def test_edit_oscillation_min_len(self) -> None:
        assert EDIT_OSCILLATION_MIN_LEN == 3

    def test_critical_run_threshold(self) -> None:
        assert EXACT_MATCH_CRITICAL_RUN == 4

    def test_min_history_for_detection(self) -> None:
        assert MIN_HISTORY_FOR_DETECTION == 2

    def test_default_severity_table(self) -> None:
        assert CYCLE_DEFAULT_SEVERITY["exact_match"] == "major"
        assert CYCLE_DEFAULT_SEVERITY["fuzzy_match"] == "major"
        assert CYCLE_DEFAULT_SEVERITY["edit_oscillation"] == "major"
        assert CYCLE_DEFAULT_SEVERITY["none"] == "info"


# ---------------------------------------------------------------------------
# 17. CycleReport.detection_type alias
# ---------------------------------------------------------------------------


class TestDetectionTypeAlias:
    def test_alias_returns_cycle_type(self) -> None:
        d = CycleDetector()
        report = d.detect([_snap(1, "S"), _snap(2, "S")])
        assert report.detection_type == report.cycle_type == "exact_match"

    def test_alias_for_no_cycle(self) -> None:
        report = _no_cycle("none here", 3, 0.8)
        assert report.detection_type == "none"


# ---------------------------------------------------------------------------
# 18. Replace-style overrides — ensure dataclasses are immutable
# ---------------------------------------------------------------------------


class TestImmutability:
    def test_state_snapshot_is_frozen(self) -> None:
        s = _snap(1, "X")
        with pytest.raises((AttributeError, Exception)):
            s.signature = "Y"  # type: ignore[misc]

    def test_cycle_report_is_frozen(self) -> None:
        report = CycleDetector().detect([_snap(1, "X"), _snap(2, "X")])
        with pytest.raises((AttributeError, Exception)):
            report.detected = False  # type: ignore[misc]

    def test_replace_yields_distinct_snapshot(self) -> None:
        s = _snap(1, "X")
        s2 = replace(s, round_num=2)
        assert s.round_num == 1
        assert s2.round_num == 2
        assert s.signature == s2.signature
