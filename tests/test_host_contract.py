"""Contract and provenance tests for the Host Support Contract."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from devolaflow.host_contract import (
    HostContractError,
    host_names,
    load_host_contract,
    normalize_skill_observation,
    profile_projection,
    resolve_host,
    validate_host_contract,
)

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "host-contract.yaml"


def test_repository_contract_has_expected_shape() -> None:
    contract = load_host_contract()
    assert len(host_names(contract)) == 17
    assert sum(entry["tier"] == "guaranteed" for entry in contract["hosts"].values()) == 6
    assert set(profile_projection(contract)) == set(contract["hosts"])


def test_repository_contract_resolves_kimi_alias() -> None:
    contract = load_host_contract()
    assert resolve_host("kimi", contract) == "kimicode"
    assert resolve_host("cursor", contract) == "cursor"
    with pytest.raises(KeyError, match="unknown host"):
        resolve_host("not-a-host", contract)


def test_schema_is_yaml_and_declares_closed_enums() -> None:
    schema = yaml.safe_load(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert schema["$defs"]["status"]["enum"] == [
        "implemented",
        "designed",
        "broken",
        "undeclared",
        "native",
    ]
    assert schema["$defs"]["provenance"]["enum"] == [
        "captured",
        "vendor-doc",
        "synthetic",
        "TBD-audit",
    ]
    assert schema["$defs"]["skillResidency"]["required"] == [
        "status",
        "scope",
        "observation_method",
        "fixtures",
        "fixture_provenance",
        "reason",
    ]


def test_invalid_root_and_host_count_fail_loudly() -> None:
    with pytest.raises(HostContractError, match="root must be a mapping"):
        validate_host_contract([])
    contract = deepcopy(load_host_contract())
    contract["hosts"].pop("trae")
    with pytest.raises(HostContractError, match="exactly 17 hosts"):
        validate_host_contract(contract)


def test_implemented_bridge_rejects_unverified_provenance() -> None:
    contract = deepcopy(load_host_contract())
    bridge = contract["hosts"]["cursor"]["extras"]["boundary_bridge"]
    bridge["status"] = "implemented"
    with pytest.raises(HostContractError, match="captured or vendor-doc"):
        validate_host_contract(contract)


def test_vendor_doc_implemented_bridge_requires_reference() -> None:
    contract = deepcopy(load_host_contract())
    bridge = contract["hosts"]["copilot"]["extras"]["boundary_bridge"]
    bridge["status"] = "implemented"
    bridge["provenance_ref"] = None
    with pytest.raises(HostContractError, match="requires provenance_ref"):
        validate_host_contract(contract)


def test_implemented_vocabulary_requires_both_tool_families() -> None:
    contract = deepcopy(load_host_contract())
    vocabulary = contract["hosts"]["kimicode"]["extras"]["tool_vocabulary"]
    vocabulary["write"] = []
    with pytest.raises(HostContractError, match="requires write and shell"):
        validate_host_contract(contract)


def test_implemented_skill_residency_requires_evidence() -> None:
    contract = deepcopy(load_host_contract())
    residency = contract["hosts"]["claude"]["extras"]["skill_residency"]
    residency["status"] = "implemented"
    with pytest.raises(HostContractError, match="skill_residency implemented without fixtures"):
        validate_host_contract(contract)


def test_skill_observation_keeps_runtime_fact_separate_from_hsc_claim() -> None:
    observation = normalize_skill_observation("claude", True)
    assert observation["value"] is True
    assert observation["observed"] is True
    assert observation["status"] == "AVAILABLE"
    assert observation["provenance"] == "probe-runtime"
    assert observation["contract_status"] == "designed"
    assert observation["hsc_validation"]["status"] == "INSUFFICIENT"

    missing = normalize_skill_observation("kimi", None)
    assert missing["host"] == "kimicode"
    assert missing["value"] is None
    assert missing["status"] == "INSUFFICIENT"
    assert missing["hsc_validation"]["status"] == "INSUFFICIENT"
    assert "not observable" in missing["hsc_validation"]["reason"]


def test_duplicate_alias_and_alias_collision_fail() -> None:
    contract = deepcopy(load_host_contract())
    contract["hosts"]["cursor"]["aliases"] = ["shared"]
    contract["hosts"]["claude"]["aliases"] = ["shared"]
    with pytest.raises(HostContractError, match="belongs to both"):
        validate_host_contract(contract)

    contract = deepcopy(load_host_contract())
    contract["hosts"]["cursor"]["aliases"] = ["claude"]
    with pytest.raises(HostContractError, match="collides with host id"):
        validate_host_contract(contract)
