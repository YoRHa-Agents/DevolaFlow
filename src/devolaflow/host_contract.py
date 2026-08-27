"""Loader and semantic validator for the Host Support Contract.

``workflow-system/agent/hosts.yaml`` owns host identity and capability
declarations.  This module deliberately derives views from that file rather
than maintaining a second host registry (Rule A-5).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

HOSTS_FILENAME = "hosts.yaml"
SCHEMA_FILENAME = "host-contract.yaml"
REQUIRED_EXTRA_AXES = (
    "boundary_bridge",
    "session_resume",
    "subagent_dispatch",
    "mcp",
    "tool_vocabulary",
)
IMPLEMENTED_PROVENANCE = frozenset({"captured", "vendor-doc"})
VALID_STATUSES = frozenset({"implemented", "designed", "broken", "undeclared", "native"})
VALID_PROVENANCE = frozenset({"captured", "vendor-doc", "synthetic", "TBD-audit"})


class HostContractError(ValueError):
    """Raised when the host contract is absent, malformed, or contradictory."""


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _error(source: Path | str, message: str) -> HostContractError:
    return HostContractError(f"{source}: {message}")


def _read_yaml(path: Path) -> object:
    if not path.is_file():
        raise _error(path, "host contract file is missing")
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise _error(path, f"YAML is not parseable: {exc}") from exc


def _schema_path(source_path: Path) -> Path:
    del source_path
    return _repository_root() / "schemas" / SCHEMA_FILENAME


def _validate_json_schema(data: object, source_path: Path) -> None:
    schema_path = _schema_path(source_path)
    schema = _read_yaml(schema_path)
    try:
        validator = Draft202012Validator(schema)
        errors = sorted(validator.iter_errors(data), key=lambda error: list(error.path))
    except SchemaError as exc:
        raise _error(schema_path, f"schema is invalid: {exc}") from exc
    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.path) or "<root>"
        raise _error(source_path, f"schema violation at {location}: {error.message}")


def _validate_aliases(hosts: dict[str, dict[str, Any]], source_path: Path) -> None:
    aliases: dict[str, str] = {}
    for name, entry in hosts.items():
        if name in aliases:
            raise _error(source_path, f"host id {name!r} is duplicated")
        for alias in entry.get("aliases", []):
            if alias in hosts:
                raise _error(source_path, f"alias {alias!r} collides with host id")
            owner = aliases.get(alias)
            if owner is not None:
                raise _error(source_path, f"alias {alias!r} belongs to both {owner!r} and {name!r}")
            aliases[alias] = name


def _validate_boundary_axis(host: str, axis: dict[str, Any], source_path: Path) -> None:
    status = axis["status"]
    provenance = axis.get("fixture_provenance")
    if provenance is not None and provenance not in VALID_PROVENANCE:
        raise _error(source_path, f"{host}.boundary_bridge has invalid fixture provenance")
    if status != "implemented":
        return
    if not axis.get("fixtures"):
        raise _error(source_path, f"{host}.boundary_bridge implemented without fixtures")
    if provenance not in IMPLEMENTED_PROVENANCE:
        raise _error(
            source_path,
            f"{host}.boundary_bridge implemented requires captured or vendor-doc provenance",
        )
    if provenance == "vendor-doc" and not axis.get("provenance_ref"):
        raise _error(
            source_path,
            f"{host}.boundary_bridge vendor-doc provenance requires provenance_ref",
        )


def _validate_semantics(data: dict[str, Any], source_path: Path) -> None:
    hosts = data["hosts"]
    if len(hosts) != 17:
        raise _error(source_path, f"contract must declare exactly 17 hosts, got {len(hosts)}")
    guaranteed = [name for name, entry in hosts.items() if entry["tier"] == "guaranteed"]
    if len(guaranteed) != 6:
        raise _error(
            source_path,
            f"contract must declare six guaranteed hosts, got {len(guaranteed)}",
        )

    _validate_aliases(hosts, source_path)
    for name, entry in hosts.items():
        floor = entry["floor"]
        if entry["tier"] == "guaranteed":
            required_floor = (
                "skill_delivery",
                "instruction_format",
                "install_channels",
                "doctor",
                "tests",
            )
            missing = [axis for axis in required_floor if not floor.get(axis)]
            if missing:
                raise _error(source_path, f"{name} guaranteed floor missing {missing}")
            if not floor["install_channels"]:
                raise _error(source_path, f"{name} guaranteed host has no install channel")
        extras = entry["extras"]
        if set(extras) != set(REQUIRED_EXTRA_AXES):
            raise _error(source_path, f"{name}.extras must declare exactly {REQUIRED_EXTRA_AXES}")
        for axis_name, axis in extras.items():
            status = axis.get("status")
            if status not in VALID_STATUSES:
                raise _error(source_path, f"{name}.{axis_name} has invalid status {status!r}")
            if axis_name == "boundary_bridge":
                _validate_boundary_axis(name, axis, source_path)
            elif (
                axis_name == "tool_vocabulary"
                and status == "implemented"
                and (not axis.get("write") or not axis.get("shell"))
            ):
                raise _error(
                    source_path,
                    f"{name}.tool_vocabulary implemented requires write and shell lists",
                )


def validate_host_contract(
    data: object, *, source_path: Path | str = HOSTS_FILENAME
) -> dict[str, Any]:
    """Validate and return a parsed HSC mapping.

    Validation is intentionally fail-loud: a malformed or over-claimed host
    entry cannot silently become a supported host.
    """
    source = Path(source_path)
    if not isinstance(data, dict):
        raise _error(source, "contract root must be a mapping")
    _validate_json_schema(data, source)
    _validate_semantics(data, source)
    for _name, entry in data["hosts"].items():
        for alias in entry.get("aliases", []):
            resolve_host(alias, data)
    return data


def load_host_contract(path: Path | str | None = None) -> dict[str, Any]:
    """Load and validate the repository's HSC or an explicit YAML path."""
    source = (
        Path(path)
        if path is not None
        else _repository_root() / "workflow-system/agent" / HOSTS_FILENAME
    )
    return validate_host_contract(_read_yaml(source), source_path=source)


def host_names(contract: dict[str, Any] | None = None) -> tuple[str, ...]:
    """Return canonical host ids in contract order."""
    contract = contract or load_host_contract()
    return tuple(contract["hosts"])


def resolve_host(name: str, contract: dict[str, Any] | None = None) -> str:
    """Resolve a canonical host id or alias to its canonical id."""
    contract = contract or load_host_contract()
    if name in contract["hosts"]:
        return name
    for canonical, entry in contract["hosts"].items():
        if name in entry.get("aliases", []):
            return canonical
    raise KeyError(f"unknown host {name!r}; available: {sorted(contract['hosts'])}")


def profile_projection(contract: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    """Return the manifest-shaped install view derived from HSC floor data."""
    contract = contract or load_host_contract()
    projection: dict[str, dict[str, Any]] = {}
    for name in host_names(contract):
        entry = contract["hosts"][name]
        if entry["floor"]["skill_delivery"]["sets"]:
            projection[name] = {
                "kind": entry["floor"]["skill_delivery"]["kind"],
                "sets": list(entry["floor"]["skill_delivery"]["sets"]),
            }
    return projection


__all__ = [
    "HOSTS_FILENAME",
    "IMPLEMENTED_PROVENANCE",
    "REQUIRED_EXTRA_AXES",
    "HostContractError",
    "host_names",
    "load_host_contract",
    "profile_projection",
    "resolve_host",
    "validate_host_contract",
]
