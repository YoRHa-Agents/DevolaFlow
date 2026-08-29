"""v21.1.0 T7 ghost audit for skill residency contracts."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from devolaflow.host_contract import REQUIRED_EXTRA_AXES, load_host_contract


def test_skill_residency_axis_is_wired_across_ssot_and_schema(project_root: Path) -> None:
    contract = load_host_contract(project_root / "workflow-system/agent/hosts.yaml")
    schema = yaml.safe_load(
        (project_root / "schemas/host-contract.yaml").read_text(encoding="utf-8")
    )
    assert len(contract["hosts"]) == 17
    assert schema["$defs"]["extras"]["required"] == list(REQUIRED_EXTRA_AXES)
    assert "skill_residency" in schema["$defs"]["extras"]["properties"]
    assert all(
        set(entry["extras"]) == set(REQUIRED_EXTRA_AXES) for entry in contract["hosts"].values()
    )


def test_skill_residency_implemented_claims_have_allowed_evidence(project_root: Path) -> None:
    contract = load_host_contract(project_root / "workflow-system/agent/hosts.yaml")
    for name, entry in contract["hosts"].items():
        axis = entry["extras"]["skill_residency"]
        if axis["status"] == "implemented":
            assert axis["fixtures"], name
            assert axis["fixture_provenance"] in {"captured", "vendor-doc"}, name
            if axis["fixture_provenance"] == "vendor-doc":
                assert axis["provenance_ref"], name
    assert not any(
        entry["extras"]["skill_residency"]["status"] == "implemented"
        for entry in contract["hosts"].values()
    )


def test_skill_residency_design_records_fact_and_channel_limits(project_root: Path) -> None:
    design = (project_root / ".local/research/v21.1.0_skill_residency_design.md").read_text(
        encoding="utf-8"
    )
    for phrase in (
        "skill_delivery",
        "recorded runtime fact",
        "null",
        "INSUFFICIENT",
        "Claude, Codex, and KimiCode",
        "no real residency fixture",
    ):
        assert phrase in design


def test_v21_t4_calibration_and_baseline_keep_evidence_boundaries(project_root: Path) -> None:
    """T4 close evidence records unavailable ROI rather than inventing outcomes."""
    calibration = json.loads(
        (project_root / ".local/research/v21.1.0_calibration_roi.json").read_text(encoding="utf-8")
    )
    summary = calibration["summary"]
    assert calibration["matrix"]["planned_specs"] == 240
    assert summary["counts"] == {
        "planned": 240,
        "observed": 240,
        "completed": 0,
        "pass": 0,
        "fail": 0,
        "insufficient": 240,
        "unrecorded": 0,
    }
    assert summary["roi"]["status"] == "INSUFFICIENT"
    assert summary["roi"]["quality_causality"] == "NOT_ESTABLISHED"

    baseline = json.loads(
        (project_root / ".local/telemetry/baselines/harness_baseline_v21.1.0.json").read_text(
            encoding="utf-8"
        )
    )
    assert baseline["cycle"] == "v21.1.0"
    assert baseline["settlement"]["status"] == "SETTLED"
    assert baseline["settlement"]["historical_comparison"] == "INSUFFICIENT"
