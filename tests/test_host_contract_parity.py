"""Parity checks for HSC-derived install and support declarations."""

from __future__ import annotations

from pathlib import Path

from devolaflow.host_contract import REQUIRED_EXTRA_AXES, load_host_contract, profile_projection
from devolaflow.install_manifest import load_manifest

ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / "workflow-system" / "agent"


def test_manifest_profiles_match_host_contract_projection() -> None:
    manifest = load_manifest(AGENT_DIR)
    projection = profile_projection(load_host_contract())
    for name, profile in manifest["install_profiles"].items():
        assert name in projection, f"manifest profile {name!r} is absent from hosts.yaml"
        assert profile == projection[name], (
            f"manifest profile {name!r} drifted from hosts.yaml: "
            f"manifest={profile!r}, contract={projection[name]!r}"
        )


def test_guaranteed_hosts_declare_complete_floor_and_extras() -> None:
    contract = load_host_contract()
    required_floor = {"skill_delivery", "instruction_format", "install_channels", "doctor", "tests"}
    required_extras = set(REQUIRED_EXTRA_AXES)
    guaranteed = [
        (name, entry) for name, entry in contract["hosts"].items() if entry["tier"] == "guaranteed"
    ]
    assert len(guaranteed) == 6
    for name, entry in guaranteed:
        assert set(entry["floor"]) == required_floor, name
        assert set(entry["extras"]) == required_extras, name
        assert entry["floor"]["install_channels"], name


def test_skill_residency_declarations_have_observation_contract() -> None:
    contract = load_host_contract()
    for name, entry in contract["hosts"].items():
        residency = entry["extras"]["skill_residency"]
        assert residency["status"]
        assert residency["scope"]
        assert residency["observation_method"]
        assert "fixtures" in residency
        assert residency["fixture_provenance"]
        assert residency["reason"], name


def test_manifest_includes_dsh_after_delivery_phase() -> None:
    manifest = load_manifest(AGENT_DIR)
    contract = load_host_contract()
    assert "dsh" in contract["hosts"]
    assert manifest["install_profiles"]["dsh"] == profile_projection(contract)["dsh"]


def test_claims_match_contract_tiers(project_root: Path) -> None:
    contract = load_host_contract()
    readme = (project_root / "README.md").read_text(encoding="utf-8")
    english = (project_root / "workflow-system/human/en/integration-guide.md").read_text(
        encoding="utf-8"
    )
    chinese = (project_root / "workflow-system/human/zh/integration-guide.md").read_text(
        encoding="utf-8"
    )
    for name, entry in contract["hosts"].items():
        assert f"`{name}`" in english or name.replace("_", " ").title() in english
        assert f"`{name}`" in chinese or name.replace("_", " ").title() in chinese
        if entry["tier"] == "guaranteed":
            assert (
                name.lower() in readme.lower()
                or entry.get("display_name", "").lower() in readme.lower()
            )
