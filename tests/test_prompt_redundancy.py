"""PV-4 prompt contract: shared hierarchy text has one normative owner."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
AGENT_ROOT = REPO_ROOT / "workflow-system" / "agent"


def _read(relative_path: str) -> str:
    return (AGENT_ROOT / relative_path).read_text(encoding="utf-8")


def test_hierarchy_pointer_structure_preserves_entry_contract() -> None:
    """SKILL and roles point to the canonical hierarchy without losing essentials."""
    skill = _read("SKILL.md")
    hierarchy = _read("references/agent-hierarchy.md")
    roles = _read("references/team-roles.md")

    assert "**Canonical contract owner:**" in hierarchy
    assert "Layer Contract Summary (canonical hierarchy contract)" in hierarchy
    assert "Context and Message Boundaries (canonical isolation contract)" in hierarchy
    for contract_fact in (
        "Context budget | ~5K tokens | ~5K tokens | ~8K tokens",
        "| Tasks per wave | 5 |",
        "## 7. Evidence Handshake",
    ):
        assert contract_fact in hierarchy

    assert "references/agent-hierarchy.md` §§2, 6–8" in skill
    assert "references/team-roles.md" in skill
    for entry_fact in (
        "| **L0 Project** | ~5K |",
        "| **L1 Wave** | ~5K |",
        "| **L2 Task** | ~8K |",
        "≤5 tasks and rounds ≤7 waves",
        "self-verify; report evidence",
    ):
        assert entry_fact in skill

    assert "Shared hierarchy contract:" in roles
    assert "references/agent-hierarchy.md` §§2, 6–8" in roles
    for role_fact in (
        "## 2. Role Selection",
        "| Research |",
        "| HarnessBuild |",
        "role-specific evidence contracts",
    ):
        assert role_fact in roles
