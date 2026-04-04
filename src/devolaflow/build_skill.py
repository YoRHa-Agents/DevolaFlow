"""Build skill outputs for all target tools (Cursor, Codex, Claude, Copilot).

Design ref: design_delivery_architecture.md sections 4.3-4.5
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from devolaflow.adapters.base import AdapterResult, load_workflow_skill
from devolaflow.adapters.claude_adapter import ClaudeAdapter
from devolaflow.adapters.codex_adapter import CodexAdapter
from devolaflow.adapters.copilot_adapter import CopilotAdapter
from devolaflow.adapters.cursor_adapter import CursorAdapter


def _find_project_root() -> Path:
    p = Path(__file__).resolve()
    while p != p.parent:
        if (p / "pyproject.toml").exists():
            return p
        p = p.parent
    return Path.cwd()


def build_all(args: Sequence[str]) -> list[AdapterResult]:
    """Build all adapter outputs from workflow-skill.yaml."""
    root = _find_project_root()
    agent_dir = root / "workflow-system" / "agent"
    skill_yaml = agent_dir / "workflow-skill.yaml"

    if not skill_yaml.exists():
        print(f"ERROR: {skill_yaml} not found")
        return []

    source = load_workflow_skill(skill_yaml)
    dist = root / "dist"
    dist.mkdir(exist_ok=True)

    adapters = [
        ("cursor", CursorAdapter()),
        ("codex", CodexAdapter()),
        ("claude", ClaudeAdapter()),
        ("copilot", CopilotAdapter()),
    ]

    results: list[AdapterResult] = []
    for name, adapter in adapters:
        out_dir = dist / name
        result = adapter.build(source, agent_dir, out_dir)
        status = "PASS" if result.budget_ok else "FAIL (over budget)"
        print(f"  {status}: {name} - {result.budget_details}")
        results.append(result)

    passed = sum(1 for r in results if r.budget_ok)
    print(f"\n{passed} passed, {len(results) - passed} failed, {len(results)} total")
    return results
