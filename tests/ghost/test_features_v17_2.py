"""Ghost audit — consolidated W-18 feature stanza for the v17.2.0 slice.

Pins the change-entrance onboarding-router surfaces (the 12th artifact
schema, the C-9 ``entrance.md | 400 | 800`` budget row, the scaffold
template, the ``ENTRANCE_*`` lint family, and the design D-5
no-dispatch-injection guarantee) BEFORE the cycle's CHANGELOG entry
lands, per W-18.

Design contract: ``.local/research/v17.2.0_change_entrance_design.md``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from devolaflow.agent_workspace import (
    Change,
    hydrate_change_context,
)
from devolaflow.agent_workspace.lint import (
    CHECKLIST_ARTIFACT_BUDGETS,
    SemanticViolation,
    lint_change,
)
from devolaflow.skills.slash_commands import _entrance_md, run_propose

_SCHEMA_PATH = Path("schemas/agent-workspace/change-entrance.yaml")
_INDEX_PATH = Path("schemas/agent-workspace/__init__.yaml")


def _entrance_findings(report) -> list[SemanticViolation]:
    return [
        violation
        for violation in report.violations
        if isinstance(violation, SemanticViolation) and violation.kind.startswith("ENTRANCE_")
    ]


def test_change_entrance_onboarding_router(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """v17.2.0 entrance.md: schema + budget + scaffold + lint + D-5 pins."""
    # Schema registry: change-entrance is the 12th artifact schema with the
    # C-9 400/800 budget, mirrored byte-for-byte by the index entry.
    schema = yaml.safe_load(_SCHEMA_PATH.read_text(encoding="utf-8"))
    assert schema["schema_name"] == "change-entrance"
    assert schema["schema_version"] == 1
    assert (schema["token_budget"]["soft"], schema["token_budget"]["hard"]) == (400, 800)
    index = yaml.safe_load(_INDEX_PATH.read_text(encoding="utf-8"))
    index_entry = next(e for e in index["schemas"] if e["id"] == "change-entrance")
    assert index_entry["file"] == "change-entrance.yaml"
    assert (index_entry["token_budget"]["soft"], index_entry["token_budget"]["hard"]) == (
        400,
        800,
    )
    assert CHECKLIST_ARTIFACT_BUDGETS["entrance.md"] == (400, 800)

    # Template parity: the schema's worked example IS the scaffold template
    # rendered for the demo slug (design D-8 — only Section 1 personalized).
    rendered = _entrance_md("add-dark-mode", "Complete add-dark-mode")
    assert schema["example"].rstrip("\n") == rendered.rstrip("\n")

    # Scaffold: every new change folder carries the router verbatim.
    monkeypatch.delenv("DEVOLAFLOW_AGENT_WORKSPACE", raising=False)
    scaffold = run_propose("V17.2 Ghost Audit", tmp_path)
    entrance_path = scaffold / "entrance.md"
    assert entrance_path.is_file()
    assert entrance_path.read_text(encoding="utf-8") == _entrance_md(
        scaffold.name, f"Complete {scaffold.name}"
    )

    # Lint: a fresh scaffold yields zero ENTRANCE_* findings; removing the
    # router downgrades to the ENTRANCE_MISSING WARN (exit code unchanged)
    # per the design D-4 backfill window.
    clean = lint_change(scaffold.name, repo_root=tmp_path)
    assert _entrance_findings(clean) == []
    entrance_path.unlink()
    missing = lint_change(scaffold.name, repo_root=tmp_path)
    assert missing.exit_code == 0
    kinds = [(v.kind, v.severity) for v in _entrance_findings(missing)]
    assert kinds == [("ENTRANCE_MISSING", "WARN")]

    # D-5: the router is never injected into dispatch payloads — the
    # hydrate_change_context key set stays the pinned v16 nine.
    hydrated = hydrate_change_context(scaffold.name, active_root=scaffold.parent)
    assert set(hydrated) == {
        "goal",
        "checklist",
        "stage",
        "preflight",
        "spec",
        "status",
        "owned_files",
        "learnings",
        "evidence",
    }

    # Round-trip guard: a pre-v17.2 folder (no entrance.md) does NOT gain
    # the file through a Change load/store cycle.
    loaded = Change.from_active_folder(scaffold)
    assert loaded.entrance_md == ""
    rewritten_target = tmp_path / "rewritten"
    loaded.to_active_folder(rewritten_target)
    assert not (rewritten_target / "entrance.md").exists()
