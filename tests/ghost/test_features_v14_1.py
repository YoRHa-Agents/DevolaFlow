"""Ghost audit — per-cycle W-18 feature stanzas for the v14.1 cycle.

Split from ``tests/test_no_ghost_features.py`` per v15-ADR-001
(v14.3.0). New W-18 stanzas for a v14.1.x release append HERE; the
next MINOR cycle rotates to a fresh ``test_features_v<MAJ>_<MIN>.py``.
"""

from __future__ import annotations

from pathlib import Path


def test_v14_1_0_test_run_join_symbols(project_root: Path) -> None:
    """W-18 v14.1.0: every NEW §6c test-run-join + OUTPUT symbol has coverage.

    Discharges the W-18 precondition for the v14.1.0 CHANGELOG entry. The
    stanza asserts the load-bearing surfaces:

    (a) requirements_trace.py declares TestOutcome + parse_pytest_report and
        the criterion/cycle trace fields + the test_results join param.
    (b) reporter.py threads test_results + stagnation through the human
        renderers (the §4 OUTPUT conformance fixes).
    (c) human_report.md.j2 carries the 4-column Acceptance-criterion table.
    (d) the agent_workspace package re-exports TestOutcome + parse_pytest_report.
    (e) companion test coverage exists.

    Source: .local/research/v14.1.0_gap_analysis.md §(a) G-1..G-3 + §(d).
    """
    # --- (a) requirements_trace.py NEW §6c symbols -------------------
    trace_text = (project_root / "src/devolaflow/agent_workspace/requirements_trace.py").read_text(
        encoding="utf-8"
    )
    assert "class TestOutcome" in trace_text, (
        "W-18 v14.1.0 violation: requirements_trace.py missing TestOutcome."
    )
    assert "def parse_pytest_report(" in trace_text, (
        "W-18 v14.1.0 violation: requirements_trace.py missing parse_pytest_report()."
    )
    assert "test_results" in trace_text, (
        "W-18 v14.1.0 violation: trace_requirements missing the test_results join param."
    )
    for field in ("criterion", "cycle"):
        assert f"{field}: str" in trace_text, (
            f"W-18 v14.1.0 violation: RequirementTraceResult missing the {field!r} field."
        )

    # --- (b) reporter.py threads test_results + stagnation -----------
    reporter_text = (project_root / "src/devolaflow/agent_workspace/reporter.py").read_text(
        encoding="utf-8"
    )
    assert "test_results" in reporter_text, (
        "W-18 v14.1.0 violation: reporter.py does not thread test_results into the §6c join."
    )
    assert "stagnation" in reporter_text, (
        "W-18 v14.1.0 violation: reporter.py missing the stagnation→human_needed path."
    )

    # --- (c) 4-column convergence table ------------------------------
    tmpl_text = (
        project_root / "src/devolaflow/agent_workspace/templates/human_report.md.j2"
    ).read_text(encoding="utf-8")
    assert "| REQ-ID | Acceptance criterion | Result | Evidence |" in tmpl_text, (
        "W-18 v14.1.0 violation: human_report.md.j2 missing the 4-column §4a table."
    )

    # --- (d) package __all__ re-exports ------------------------------
    init_text = (project_root / "src/devolaflow/agent_workspace/__init__.py").read_text(
        encoding="utf-8"
    )
    for sym in ("TestOutcome", "parse_pytest_report"):
        assert f'"{sym}"' in init_text, (
            f"W-18 v14.1.0 violation: agent_workspace/__init__.py __all__ missing {sym!r}."
        )

    # --- (e) companion test coverage ---------------------------------
    trace_test = (project_root / "tests/test_requirements_trace.py").read_text(encoding="utf-8")
    assert "parse_pytest_report" in trace_test, (
        "W-18 v14.1.0 violation: tests/test_requirements_trace.py lacks "
        "parse_pytest_report coverage."
    )
    assert "test_join_failed_node_overrides_optimistic_matrix_to_unmet" in trace_test, (
        "W-18 v14.1.0 violation: missing the §6c join override regression test."
    )
