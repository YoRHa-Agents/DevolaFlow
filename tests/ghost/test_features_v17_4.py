"""Ghost audit for the Host Support Contract surfaces."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from devolaflow.host_contract import load_host_contract, profile_projection


def test_host_contract_surfaces_are_wired(project_root: Path) -> None:
    """W-18: HSC SSOT, schema, loader, and manifest mirror agree."""
    hosts_path = project_root / "workflow-system/agent/hosts.yaml"
    schema_path = project_root / "schemas/host-contract.yaml"
    manifest_path = project_root / "workflow-system/agent/manifest.yaml"
    assert hosts_path.is_file()
    assert schema_path.is_file()
    contract = load_host_contract(hosts_path)
    schema = yaml.safe_load(schema_path.read_text(encoding="utf-8"))
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    assert schema["title"] == "DevolaFlow Host Support Contract"
    assert schema["$defs"]["provenance"]["enum"] == [
        "captured",
        "vendor-doc",
        "synthetic",
        "TBD-audit",
    ]
    assert "reason" in schema["$defs"]["statusAxis"]["properties"]
    projection = profile_projection(contract)
    assert projection["cursor"] == manifest["install_profiles"]["cursor"]
    assert len(contract["hosts"]) == 17
    guaranteed = {
        name for name, entry in contract["hosts"].items() if entry["tier"] == "guaranteed"
    }
    assert guaranteed == {
        "cursor",
        "claude",
        "codex",
        "copilot",
        "kimicode",
        "dsh",
    }
    assert contract["hosts"]["dsh"]["extras"]["subagent_dispatch"]["primitive"] == "subagent"
    assert contract["hosts"]["copilot"]["extras"]["subagent_dispatch"]["status"] == "undeclared"
    for host in ("codex", "kimicode", "dsh"):
        assert contract["hosts"][host]["extras"]["session_resume"]["reason"]
    dsh_package = json.loads(
        (project_root / "packages/dsh-plugin/package.json").read_text(encoding="utf-8")
    )
    assert dsh_package["dsh"]["bundle"]["patch"] == "./cordis.patch.yml"
    dsh_plugin = (project_root / "packages/dsh-plugin/index.mjs").read_text(encoding="utf-8")
    assert "exec?.arguments" in dsh_plugin
    assert "str_replace_editor" in dsh_plugin
