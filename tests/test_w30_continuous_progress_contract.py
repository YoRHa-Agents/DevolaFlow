"""PV-02 contract checks for Workflow Rule W-30."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / ".rules" / "workflow.mdc"
COMPILED = (
    ROOT / "AGENTS.md",
    ROOT / ".cursor" / "rules" / "repo-governance.mdc",
)
REFERENCE_FILES = (
    ROOT / "workflow-system" / "agent" / "SKILL.md",
    ROOT / "workflow-system" / "agent" / "references" / "execution-protocol.md",
    ROOT / "workflow-system" / "agent" / "references" / "decomposition-gate.md",
    ROOT / "workflow-system" / "agent" / "references" / "wave-dispatch.md",
    ROOT / "workflow-system" / "agent" / "references" / "agent-hierarchy.md",
    ROOT / "workflow-system" / "agent" / "references" / "troubleshooting.md",
    ROOT / "workflow-system" / "agent" / "references" / "plan-mode-enforcement.md",
    ROOT / "workflow-system" / "agent" / "references" / "meta-framework.md",
)


def test_w30_source_has_both_contracts_and_no_new_flag() -> None:
    """W-30 source rule contains the two normative sub-items."""
    source = SOURCE.read_text(encoding="utf-8")
    normalized = " ".join(source.split())
    w30 = source.split("## W-30 —", 1)[1]

    assert "## W-30 — Continuous Progress Contract" in source
    assert "### W-30(a) — Bounded Wait and Ready-Work Progress" in source
    assert "### W-30(b) — Selective Blocker Isolation" in source
    assert "meaninglessly poll" in source
    assert "Independent, unaffected siblings MUST continue" in normalized
    assert "dependency-blocked" in source
    assert "finding-blocked" in source
    assert "wave conflict" in source
    assert "HARD breakpoint" in normalized
    assert "FULL_ROLLBACK" in source
    assert "DEVOLAFLOW_" not in w30


def test_w30_is_present_in_both_compiled_surfaces() -> None:
    """Rule compilation keeps W-30 in AGENTS.md and the Cursor corpus."""
    source = SOURCE.read_text(encoding="utf-8")
    source_body = source.split("## W-30 —", 1)[1]

    for path in COMPILED:
        text = path.read_text(encoding="utf-8")
        assert "## W-30 — Continuous Progress Contract" in text
        assert "### W-30(a) — Bounded Wait and Ready-Work Progress" in text
        assert "### W-30(b) — Selective Blocker Isolation" in text
        assert source_body in text


def test_w30_agent_facing_references_cover_progress_and_isolation() -> None:
    """Each selected agent-facing surface exposes the operational contract."""
    for path in REFERENCE_FILES:
        text = path.read_text(encoding="utf-8")
        assert "W-30" in text, f"{path.relative_to(ROOT)} does not cite W-30"
        assert "unaffected" in text.lower(), f"{path.relative_to(ROOT)} omits sibling isolation"
        assert "dependency-blocked" in text, f"{path.relative_to(ROOT)} omits dependency state"
        assert "finding-blocked" in text, f"{path.relative_to(ROOT)} omits finding state"
        assert "wave conflict" in text, f"{path.relative_to(ROOT)} omits wave conflict"


def test_w30_replaces_ordinary_blocker_wide_stop_language() -> None:
    """Ordinary blockers are local; only explicit hard conditions stop globally."""
    forbidden = (
        "Stop affected checklist item/round",
        "Stop the affected wave/round",
        "ownership conflict, contradictory evidence | stop wave, report to Project",
    )
    for path in (SOURCE, *REFERENCE_FILES):
        text = path.read_text(encoding="utf-8")
        assert not any(phrase in text for phrase in forbidden), (
            f"{path.relative_to(ROOT)} retains ambiguous whole-scope stop language"
        )

    execution = (ROOT / "workflow-system/agent/references/execution-protocol.md").read_text(
        encoding="utf-8"
    )
    assert "preflight STOP card" in execution
    assert "destructive-policy violation" in execution
