"""End-to-end convergence integration test (v6.0.3).

Validates Wave 3 wiring: select_context + apply_round_escalation +
ProposalGenerator.generate_round_dispatch + merge_reinforcement_into_dispatch
compose correctly for a realistic 3-round convergence.

These tests intentionally avoid mocking the wiring layer: we exercise the
full path from `select_context(round_num=N)` through
`ProposalGenerator.generate_round_dispatch` so that any regression in the
Task A or Task B wires surfaces here.
"""

from __future__ import annotations

from pathlib import Path

from devolaflow.feedback import ProposalGenerator
from devolaflow.gate.models import Finding, GateVerdict
from devolaflow.gate.reinforcement import MAX_REINFORCEMENT_RULES
from devolaflow.task_adaptive_selector import select_context

REPO_ROOT = Path(__file__).resolve().parent.parent
PROFILES_YAML = REPO_ROOT / "workflow-system" / "agent" / "context_profiles.yaml"


def _finding(
    fid: str,
    severity: str,
    description: str = "issue",
    location: str = "src/foo.py",
    suggestion: str = "",
) -> Finding:
    return Finding(
        finding_id=fid,
        severity=severity,  # type: ignore[arg-type]
        category="quality",
        location=location,
        description=description,
        suggestion=suggestion,
    )


def _verdict(findings: list[Finding], score: float) -> GateVerdict:
    return GateVerdict(
        decision="FAIL",
        rationale="convergence-test",
        composite_score=score,
        details={"findings": findings},
    )


def _base_dispatch(task_type: str = "refactor") -> dict:
    return {
        "task_id": "T-CV-001",
        "task_type": task_type,
        "context": {
            "applicable_rules": {"loading_strategy": "standard"},
            "target_files": ["src/foo.py", "src/bar.py"],
        },
    }


class TestE2EConvergenceWiring:
    """Integration tests for the full 3-round convergence loop."""

    def test_e2e_round1_baseline(self) -> None:
        """Round 1: selector returns baseline profile, dispatch untouched."""
        gen = ProposalGenerator()
        base = _base_dispatch()

        ctx = select_context("refactor", profiles_path=PROFILES_YAML, round_num=1)
        dispatch = gen.generate_round_dispatch(base, None, round_num=1)

        assert ctx["round_num"] == 1
        assert ctx["escalation_applied"] is False
        assert "reinforcement" not in dispatch["context"]["applicable_rules"]
        assert dispatch["context"]["applicable_rules"]["loading_strategy"] == "standard"
        assert dispatch["task_id"] == "T-CV-001"

    def test_e2e_round2_escalation_and_reinforcement(self) -> None:
        """Round 2: budget/section escalation + reinforcement from round-1 findings."""
        gen = ProposalGenerator()
        base = _base_dispatch()

        ctx1 = select_context("refactor", profiles_path=PROFILES_YAML, round_num=1)
        ctx2 = select_context("refactor", profiles_path=PROFILES_YAML, round_num=2)

        findings = [
            _finding("F-1", "blocker", "SQL injection", "src/db.py"),
            _finding("F-2", "critical", "missing auth check", "src/auth.py"),
            _finding("F-3", "major", "low coverage", "src/util.py"),
        ]
        verdict = _verdict(findings, score=70.0)
        dispatch = gen.generate_round_dispatch(base, verdict, round_num=2, target_score=85.0)

        assert ctx2["round_num"] == 2
        assert ctx2["escalation_applied"] is True
        # Round 2 defaults don't bump budget but DO force the two critical sections
        assert ctx2["budget"] == ctx1["budget"]
        assert "rationalization_prevention" not in ctx2["skipped_sections"]
        assert "convergence_loop" not in ctx2["skipped_sections"]

        reinforcement = dispatch["context"]["applicable_rules"]["reinforcement"]
        assert reinforcement["round"] == 2
        assert reinforcement["prior_score"] == 70.0
        assert reinforcement["target_score"] == 85.0
        assert len(reinforcement["rules"]) == 3
        rule_ids = [r["id"] for r in reinforcement["rules"]]
        assert set(rule_ids) == {"F-1", "F-2", "F-3"}
        # Severity sort: blocker first, then critical, then major
        assert [r["severity"] for r in reinforcement["rules"]] == [
            "blocker",
            "critical",
            "major",
        ]

    def test_e2e_round3_full_escalation(self) -> None:
        """Round 3: +20% budget, model_hint=quality, reinforcement carries round-3 metadata."""
        gen = ProposalGenerator()
        base = _base_dispatch()

        ctx1 = select_context("refactor", profiles_path=PROFILES_YAML, round_num=1)
        ctx3 = select_context("refactor", profiles_path=PROFILES_YAML, round_num=3)

        persistent = [
            _finding("F-P1", "critical", "still failing", "src/foo.py"),
            _finding("F-P2", "major", "coverage < 80%", "src/bar.py"),
        ]
        verdict = _verdict(persistent, score=78.5)
        dispatch = gen.generate_round_dispatch(base, verdict, round_num=3, target_score=85.0)

        assert ctx3["round_num"] == 3
        assert ctx3["escalation_applied"] is True
        assert ctx3["budget"] == int(ctx1["budget"] * 1.2)
        assert ctx3["model_hint"] == "quality"
        assert "gate_mechanism" not in ctx3["skipped_sections"]

        reinforcement = dispatch["context"]["applicable_rules"]["reinforcement"]
        assert reinforcement["round"] == 3
        assert reinforcement["prior_score"] == 78.5
        assert reinforcement["target_score"] == 85.0
        assert "Round 2 score: 78.5/85.0" in reinforcement["escalation_note"]
        assert "MUST be addressed" in reinforcement["escalation_note"]

    def test_e2e_convergence_rules_capped_at_max(self) -> None:
        """10 findings → only MAX_REINFORCEMENT_RULES end up in dispatch."""
        gen = ProposalGenerator()
        base = _base_dispatch()

        findings = [_finding(f"F-{i:02d}", "critical", f"issue {i}") for i in range(10)]
        verdict = _verdict(findings, score=55.0)
        dispatch = gen.generate_round_dispatch(base, verdict, round_num=2)

        reinforcement = dispatch["context"]["applicable_rules"]["reinforcement"]
        assert len(reinforcement["rules"]) == MAX_REINFORCEMENT_RULES
        assert MAX_REINFORCEMENT_RULES == 5

    def test_e2e_convergence_severity_filter(self) -> None:
        """Severity floor = major → blocker/critical/major kept, minor dropped."""
        gen = ProposalGenerator()
        base = _base_dispatch()

        findings = [
            _finding("F-BL", "blocker", "bl"),
            _finding("F-CR", "critical", "cr"),
            _finding("F-MA", "major", "ma"),
            _finding("F-MI", "minor", "mi"),
        ]
        verdict = _verdict(findings, score=60.0)
        dispatch = gen.generate_round_dispatch(base, verdict, round_num=2, severity_floor="major")

        reinforcement = dispatch["context"]["applicable_rules"]["reinforcement"]
        ids = [r["id"] for r in reinforcement["rules"]]
        severities = [r["severity"] for r in reinforcement["rules"]]

        assert set(ids) == {"F-BL", "F-CR", "F-MA"}
        assert "F-MI" not in ids
        assert severities == ["blocker", "critical", "major"]
        assert reinforcement["severity_floor"] == "major"

    def test_e2e_round_num_in_selector_output(self) -> None:
        """Selector result dict must expose round_num for observability."""
        for rn in (1, 2, 3, 4):
            ctx = select_context("refactor", profiles_path=PROFILES_YAML, round_num=rn)
            assert "round_num" in ctx
            assert ctx["round_num"] == rn
            assert "escalation_applied" in ctx
            assert ctx["escalation_applied"] is (rn > 1)

    def test_e2e_full_3_round_loop_composes(self) -> None:
        """Sanity check: 3 sequential rounds compose without side-effects."""
        gen = ProposalGenerator()
        base = _base_dispatch()
        base_snapshot_keys = list(base["context"]["applicable_rules"].keys())

        ctx_r1 = select_context("refactor", profiles_path=PROFILES_YAML, round_num=1)
        d_r1 = gen.generate_round_dispatch(base, None, round_num=1)

        findings_r1 = [_finding("F-1", "critical", "x")]
        d_r2 = gen.generate_round_dispatch(base, _verdict(findings_r1, 70.0), round_num=2)

        ctx_r3 = select_context("refactor", profiles_path=PROFILES_YAML, round_num=3)
        findings_r2 = [_finding("F-2", "critical", "y")]
        d_r3 = gen.generate_round_dispatch(base, _verdict(findings_r2, 80.0), round_num=3)

        # base dispatch is NEVER mutated by any round
        assert list(base["context"]["applicable_rules"].keys()) == base_snapshot_keys

        assert ctx_r1["budget"] < ctx_r3["budget"]
        assert ctx_r1["model_hint"] != "quality"
        assert ctx_r3["model_hint"] == "quality"

        assert "reinforcement" not in d_r1["context"]["applicable_rules"]
        assert d_r2["context"]["applicable_rules"]["reinforcement"]["round"] == 2
        assert d_r3["context"]["applicable_rules"]["reinforcement"]["round"] == 3
