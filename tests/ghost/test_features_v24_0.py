"""Ghost audit for v24.0.0 workspace compaction and risk parking (W-18).

Every symbol named in the v24.0.0 CHANGELOG entry must resolve to real,
reachable code here before that entry may land (S-4, sharpened by W-18 into a
sequencing requirement). These are existence-and-contract checks, not behaviour
tests: the behaviour lives in `tests/test_parking.py`,
`tests/test_workspace_compact.py`, and `tests/test_workspace_compact_telemetry.py`.
"""

from __future__ import annotations

import tomllib
from pathlib import Path


def test_parking_domain_exposes_its_public_surface() -> None:
    from devolaflow import parking

    for symbol in (
        "ParkingStore",
        "Risk",
        "RiskState",
        "Judgment",
        "Severity",
        "render_index",
        "render_judge_view",
        "plan_adoption",
        "apply_adoption",
    ):
        assert hasattr(parking, symbol), f"parking.{symbol} is missing"


def test_workspace_compact_domain_exposes_its_public_surface() -> None:
    from devolaflow import workspace_compact

    for symbol in (
        "build_plan",
        "apply_plan",
        "locate",
        "restore",
        "verify_integrity",
        "CompactPlan",
        "CompactResult",
        "scan_bloat",
    ):
        assert hasattr(workspace_compact, symbol), f"workspace_compact.{symbol} is missing"


def test_shared_ledger_primitives_are_importable() -> None:
    from devolaflow.workspace_ledger import (
        append_ledger_row,
        detect_view_drift,
        load_ledger_rows,
        write_generated_view,
    )

    assert callable(append_ledger_row)
    assert callable(load_ledger_rows)
    assert callable(write_generated_view)
    assert callable(detect_view_drift)


def test_both_console_scripts_are_registered(project_root: Path) -> None:
    """The tools are the only supported write path, so they must be installed."""

    data = tomllib.loads((project_root / "pyproject.toml").read_text(encoding="utf-8"))
    scripts = data["project"]["scripts"]
    assert scripts["devola-parking"] == "devolaflow.parking.console:parking_cmd"
    assert scripts["devola-compact"] == "devolaflow.workspace_compact.console:compact_cmd"


def test_risk_lifecycle_treats_archived_as_terminal() -> None:
    """A relocated file must not come back and contradict the mapping ledger."""

    from devolaflow.parking.models import STATE_TRANSITIONS, RiskState

    assert STATE_TRANSITIONS[RiskState.ARCHIVED] == frozenset()
    assert RiskState.ARCHIVED in STATE_TRANSITIONS[RiskState.CLOSED]


def test_judgment_ledger_is_never_a_compaction_candidate() -> None:
    """The decision record is the expensive thing to reconstruct; it stays."""

    from devolaflow.workspace_compact.models import PROTECTED_NAMES

    assert {"judgments.yaml", "events.yaml", "judge.md"} <= PROTECTED_NAMES


def test_parking_write_hook_is_registered_on_file_write() -> None:
    from devolaflow.lifecycle import list_handlers
    from devolaflow.lifecycle.check_parking_write import check_parking_write

    assert check_parking_write in list_handlers("file_write")


def test_compact_telemetry_records_three_distinguishable_outcomes() -> None:
    from devolaflow.workspace_compact.telemetry import (
        OUTCOME_APPLIED,
        OUTCOME_BYPASSED,
        OUTCOME_PLANNED,
        OUTCOMES,
    )

    assert {OUTCOME_APPLIED, OUTCOME_PLANNED, OUTCOME_BYPASSED} == OUTCOMES


def test_retired_si10_gate_names_keep_the_ledger_readable() -> None:
    """F-00: one retired gate name must not cost every downstream reading."""

    from devolaflow.harness.telemetry import RETIRED_SI10_GATE_NAMES, SI10_GATE_NAMES

    assert "iteration-delta-gate" in RETIRED_SI10_GATE_NAMES
    assert not RETIRED_SI10_GATE_NAMES & set(SI10_GATE_NAMES)


def test_both_references_are_installed_and_cited(project_root: Path) -> None:
    agent = project_root / "workflow-system" / "agent"
    skill = (agent / "SKILL.md").read_text(encoding="utf-8")
    manifest = (agent / "manifest.yaml").read_text(encoding="utf-8")
    for name in ("risk-parking.md", "workspace-compact.md"):
        assert (agent / "references" / name).is_file()
        assert f"references/{name}" in skill
        assert name in manifest
