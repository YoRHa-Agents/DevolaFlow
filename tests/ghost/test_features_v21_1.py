"""v21.1.0 T7 ghost audit for skill residency contracts."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from devolaflow.host_contract import REQUIRED_EXTRA_AXES, load_host_contract

_V21_1_ARTIFACT_PATHS: dict[str, tuple[Path, Path]] = {
    "skill_residency_design": (
        Path(".local/research/v21.1.0_skill_residency_design.md"),
        Path("docs/cycle-archive/v21.1.0/design/v21.1.0_skill_residency_design.md"),
    ),
    "calibration_roi": (
        Path(".local/research/v21.1.0_calibration_roi.json"),
        Path("docs/cycle-archive/v21.1.0/other/v21.1.0_calibration_roi.json"),
    ),
    "harness_baseline": (
        Path(".local/telemetry/baselines/harness_baseline_v21.1.0.json"),
        Path("docs/cycle-archive/v21.1.0/harness/v21.1.0_harness_baseline.json"),
    ),
}


def _resolve_v21_1_artifact(project_root: Path, artifact_name: str) -> Path:
    """Prefer local v21.1.0 artifacts, falling back to tracked archive copies."""
    local_path, archive_path = _V21_1_ARTIFACT_PATHS[artifact_name]
    for relative_path in (local_path, archive_path):
        candidate = project_root / relative_path
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        f"v21.1.0 artifact {artifact_name!r} is missing at {local_path} and {archive_path}"
    )


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
    design = _resolve_v21_1_artifact(project_root, "skill_residency_design").read_text(
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
        _resolve_v21_1_artifact(project_root, "calibration_roi").read_text(encoding="utf-8")
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
        _resolve_v21_1_artifact(project_root, "harness_baseline").read_text(encoding="utf-8")
    )
    assert baseline["cycle"] == "v21.1.0"
    assert baseline["settlement"]["status"] == "SETTLED"
    assert baseline["settlement"]["historical_comparison"] == "INSUFFICIENT"


def test_optional_plugins_are_explicit_only_not_default_dependencies(project_root: Path) -> None:
    """Patch contract: optional plugins remain registered but are not bundled."""
    from devolaflow.plugins.installer import available_plugin_profiles, select_plugin_profile

    registry_path = project_root / "workflow-system/agent/knowledge/runtime-plugins.yaml"
    registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    optional_ids = {"rtk", "ui-pro", "si-chip"}
    for plugin_id in optional_ids:
        entry = next(entry for entry in registry["plugins"] if entry["id"] == plugin_id)
        assert entry["tier"] == "suggest"
        assert entry["default_install"] is False

    profiles = available_plugin_profiles(registry_path=registry_path)
    for plugin_id in optional_ids:
        assert plugin_id not in profiles["all"]
        assert plugin_id not in profiles["global"]
        assert select_plugin_profile(plugin_id, registry_path=registry_path) == [plugin_id]
