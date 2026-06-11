"""Ghost audit — per-cycle W-18 feature stanzas for the v14.0 cycle.

Split from ``tests/test_no_ghost_features.py`` per v15-ADR-001
(v14.3.0). New W-18 stanzas for a v14.0.x release append HERE; the
next MINOR cycle rotates to a fresh ``test_features_v<MAJ>_<MIN>.py``.
"""

from __future__ import annotations

from pathlib import Path

from tests.ghost.test_registries import _SF4_REFERENCE_SET

# ---------------------------------------------------------------------------
# W-18 stanza for v14.0.0 — `.local/human/` human-facing interaction surface
# ---------------------------------------------------------------------------
#
# Per W-18 sequencing the ghost-audit refresh MUST land BEFORE the v14.0.0
# CHANGELOG entry mentioning the human surface. This stanza pins the
# v14.0.0 implementation surface (design `.local/research/v14.0.0_design.md`
# §3-§6):
#
# * src/devolaflow/agent_workspace/requirements_trace.py declares
#   trace_requirements + RequirementTraceResult (the REQ-ID → evidence
#   producer; design §6c / finding F-2).
# * src/devolaflow/lifecycle/check_human_input_append_only.py declares the
#   immutability hook (design §3c; keyed on Lifecycle, NOT Status / F-1).
# * src/devolaflow/agent_workspace/reporter.py declares the FIFTH flavour
#   render_human_report (+ render_human_digest; design §4).
# * src/devolaflow/agent_workspace/lint.py declares lint_human +
#   HUMAN_ARTIFACT_BUDGETS (the C-9 human rows; design §4c).
# * src/devolaflow/workspace_context.py declares the 4 additive
#   WorkspaceContext fields has_human_dir / human_constitution /
#   human_requirements / human_digest (design §6a).
# * The agent_workspace package re-exports the new public symbols in __all__.
# * workflow-system/agent/references/human-surface.md exists (24th SF-4
#   reference) and is pinned in _SF4_REFERENCE_SET above.
# * Companion test files exist.
#
# Source: .local/research/v14.0.0_design.md §3-§6.
# ---------------------------------------------------------------------------


def test_v14_0_0_human_surface_symbols(project_root: Path) -> None:
    """W-18 v14.0.0: every NEW `.local/human/` surface symbol has coverage.

    Discharges the W-18 precondition for the v14.0.0 CHANGELOG entry
    mentioning the human surface. The stanza asserts the load-bearing
    surfaces across src/ + docs/ + tests/:

    (a) requirements_trace.py declares trace_requirements +
        RequirementTraceResult.
    (b) check_human_input_append_only.py declares the immutability hook.
    (c) reporter.py declares render_human_report + render_human_digest.
    (d) lint.py declares lint_human + HUMAN_ARTIFACT_BUDGETS (6 rows).
    (e) workspace_context.py declares the 4 additive scan fields.
    (f) the agent_workspace package re-exports the new public symbols.
    (g) references/human-surface.md exists + is in _SF4_REFERENCE_SET.
    (h) companion test files exist.

    Source: .local/research/v14.0.0_design.md §3-§6.
    """
    # --- (a) requirements_trace.py -----------------------------------
    trace_path = project_root / "src/devolaflow/agent_workspace/requirements_trace.py"
    assert trace_path.is_file(), (
        "W-18 v14.0.0 violation: requirements_trace.py missing — release blocker."
    )
    trace_text = trace_path.read_text(encoding="utf-8")
    assert "def trace_requirements(" in trace_text, (
        "W-18 v14.0.0 violation: requirements_trace.py missing trace_requirements()."
    )
    assert "class RequirementTraceResult" in trace_text, (
        "W-18 v14.0.0 violation: requirements_trace.py missing RequirementTraceResult."
    )

    # --- (b) check_human_input_append_only.py ------------------------
    hook_path = project_root / "src/devolaflow/lifecycle/check_human_input_append_only.py"
    assert hook_path.is_file(), (
        "W-18 v14.0.0 violation: check_human_input_append_only.py missing — release blocker."
    )
    hook_text = hook_path.read_text(encoding="utf-8")
    assert "def check_human_input_append_only(" in hook_text, (
        "W-18 v14.0.0 violation: check_human_input_append_only.py missing the hook function."
    )

    # --- (c) reporter.py FIFTH flavour -------------------------------
    reporter_text = (project_root / "src/devolaflow/agent_workspace/reporter.py").read_text(
        encoding="utf-8"
    )
    assert "def render_human_report(" in reporter_text, (
        "W-18 v14.0.0 violation: reporter.py missing render_human_report (5th flavour)."
    )
    assert "def render_human_digest(" in reporter_text, (
        "W-18 v14.0.0 violation: reporter.py missing render_human_digest."
    )

    # --- (d) lint.py human rows --------------------------------------
    lint_text = (project_root / "src/devolaflow/agent_workspace/lint.py").read_text(
        encoding="utf-8"
    )
    assert "def lint_human(" in lint_text, "W-18 v14.0.0 violation: lint.py missing lint_human()."
    assert "HUMAN_ARTIFACT_BUDGETS" in lint_text, (
        "W-18 v14.0.0 violation: lint.py missing HUMAN_ARTIFACT_BUDGETS."
    )
    for budget_key in (
        "input/constitution.md",
        "input/requirements.md",
        "input/requirements/<domain>.md",
        "input/amendments/<date>-<slug>.md",
        "output/DIGEST.md",
        "output/convergence/<version>-convergence.md",
    ):
        assert budget_key in lint_text, (
            f"W-18 v14.0.0 violation: HUMAN_ARTIFACT_BUDGETS missing the "
            f"{budget_key!r} row (design §4c)."
        )

    # --- (e) workspace_context.py 4 scan fields ----------------------
    ws_text = (project_root / "src/devolaflow/workspace_context.py").read_text(encoding="utf-8")
    for field in (
        "has_human_dir",
        "human_constitution",
        "human_requirements",
        "human_digest",
    ):
        assert field in ws_text, (
            f"W-18 v14.0.0 violation: workspace_context.py missing the "
            f"{field!r} scan field (design §6a)."
        )

    # --- (f) package __all__ re-exports ------------------------------
    init_text = (project_root / "src/devolaflow/agent_workspace/__init__.py").read_text(
        encoding="utf-8"
    )
    for sym in (
        "trace_requirements",
        "RequirementTraceResult",
        "render_human_report",
        "render_human_digest",
        "lint_human",
        "HUMAN_ARTIFACT_BUDGETS",
    ):
        assert f'"{sym}"' in init_text, (
            f"W-18 v14.0.0 violation: agent_workspace/__init__.py __all__ missing {sym!r}."
        )

    # --- (g) reference doc + SF-4 set --------------------------------
    assert (project_root / "workflow-system/agent/references/human-surface.md").is_file(), (
        "W-18 v14.0.0 violation: references/human-surface.md missing — release blocker."
    )
    assert "human-surface.md" in set(_SF4_REFERENCE_SET), (
        "W-18 v14.0.0 violation: _SF4_REFERENCE_SET must include human-surface.md (24th entry)."
    )

    # --- (h) companion test files ------------------------------------
    for companion in (
        "tests/test_requirements_trace.py",
        "tests/test_human_input_immutability.py",
        "tests/test_lint_human.py",
        "tests/test_workspace_context_scan.py",
    ):
        assert (project_root / companion).is_file(), (
            f"W-18 v14.0.0 violation: {companion} missing — release blocker."
        )
