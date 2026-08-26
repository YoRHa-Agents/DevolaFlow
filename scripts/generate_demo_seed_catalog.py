#!/usr/bin/env python3
"""Generate the file://-safe browser catalog for registry-v3 checklist seeds."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "workflow-system/agent/templates/registry.yaml"
OUTPUT_PATH = ROOT / "workflow-system/human/demo/shared/seed-catalog.js"
EXPECTED_SEED_COUNT = 24


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path.relative_to(ROOT)} must contain a YAML mapping")
    return payload


def _require_mapping(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be a mapping")
    return value


def _require_list(value: Any, context: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{context} must be a list")
    return value


def _seed_record(entry: dict[str, Any], registry_schema: str) -> dict[str, Any]:
    name = entry.get("name")
    seed_relative = entry.get("seed")
    if not isinstance(name, str) or not isinstance(seed_relative, str):
        raise ValueError("every registry entry must declare string name and seed fields")
    if seed_relative != f"seeds/{name}.yaml":
        raise ValueError(f"registry seed path for {name!r} is not canonical")

    seed_path = REGISTRY_PATH.parent / seed_relative
    seed = _load_yaml(seed_path)
    metadata = _require_mapping(seed.get("metadata"), f"{seed_relative}.metadata")
    if seed.get("kind") != "checklist-seed":
        raise ValueError(f"{seed_relative} must be a checklist-seed")
    if metadata.get("name") != name or metadata.get("category") != entry.get("category"):
        raise ValueError(f"{seed_relative} metadata does not match registry entry {name!r}")

    partitions: list[dict[str, Any]] = []
    for partition_index, raw_partition in enumerate(
        _require_list(seed.get("partitions"), f"{seed_relative}.partitions")
    ):
        partition = _require_mapping(
            raw_partition, f"{seed_relative}.partitions[{partition_index}]"
        )
        source_stages: list[dict[str, str]] = []
        for source_index, raw_source in enumerate(
            _require_list(
                partition.get("source_stages"),
                f"{seed_relative}.partitions[{partition_index}].source_stages",
            )
        ):
            source = _require_mapping(
                raw_source,
                f"{seed_relative}.partitions[{partition_index}].source_stages[{source_index}]",
            )
            source_id = source.get("id")
            primitive = source.get("primitive")
            if not isinstance(source_id, str) or not isinstance(primitive, str):
                raise ValueError(f"{name} source_stages entries require string id and primitive")
            source_stages.append({"id": source_id, "primitive": primitive})

        assertions: list[dict[str, Any]] = []
        for assertion_index, raw_assertion in enumerate(
            _require_list(
                partition.get("assertions"),
                f"{seed_relative}.partitions[{partition_index}].assertions",
            )
        ):
            assertion = _require_mapping(
                raw_assertion,
                f"{seed_relative}.partitions[{partition_index}].assertions[{assertion_index}]",
            )
            verify = _require_mapping(
                assertion.get("verify"),
                f"{seed_relative}.partitions[{partition_index}].assertions"
                f"[{assertion_index}].verify",
            )
            assertions.append(
                {
                    "key": assertion["key"],
                    "statement": assertion["statement_template"],
                    "suggested_priority": assertion["suggested_priority"],
                    "verify": verify,
                }
            )

        partitions.append(
            {
                "key": partition["key"],
                "title": partition["title_template"],
                "source_stages": source_stages,
                "assertions": assertions,
            }
        )

    record: dict[str, Any] = {
        "registry_schema_version": registry_schema,
        "seed_schema_version": seed["schema_version"],
        "source": _require_mapping(metadata.get("source"), f"{seed_relative}.metadata.source"),
        "name": name,
        "category": entry["category"],
        "tags": _require_list(entry.get("tags"), f"registry entry {name}.tags"),
        "description": entry["description"],
        "seed_path": f"workflow-system/agent/templates/{seed_relative}",
        "partitions": partitions,
    }
    runtime_path = entry.get("path")
    if runtime_path is not None:
        if not isinstance(runtime_path, str):
            raise ValueError(f"registry runtime path for {name!r} must be a string")
        record["runtime_path"] = f"workflow-system/agent/templates/{runtime_path}"
    return record


def build_catalog() -> dict[str, Any]:
    registry = _load_yaml(REGISTRY_PATH)
    registry_schema = registry.get("schema_version")
    if registry_schema != "3.0":
        raise ValueError(f"expected registry schema 3.0, got {registry_schema!r}")

    entries = [
        *_require_list(registry.get("compositions"), "registry.compositions"),
        *_require_list(registry.get("templates"), "registry.templates"),
    ]
    if len(entries) != EXPECTED_SEED_COUNT:
        raise ValueError(
            f"registry must contain exactly {EXPECTED_SEED_COUNT} seeds, got {len(entries)}"
        )
    records = [
        _seed_record(_require_mapping(entry, f"registry entry {index}"), registry_schema)
        for index, entry in enumerate(entries)
    ]
    names = [record["name"] for record in records]
    if len(set(names)) != EXPECTED_SEED_COUNT:
        raise ValueError("registry seed names must be unique")

    return {
        "schema_version": "1.0",
        "registry": {
            "schema_version": registry_schema,
            "source_path": "workflow-system/agent/templates/registry.yaml",
        },
        "record_count": len(records),
        "seeds": records,
    }


def render_catalog() -> str:
    payload = json.dumps(build_catalog(), ensure_ascii=False, indent=2)
    return (
        "// AUTO-GENERATED by scripts/generate_demo_seed_catalog.py. DO NOT EDIT.\n"
        "window.DEVOLAFLOW_SEED_CATALOG = Object.freeze(\n"
        f"{payload}\n"
        ");\n"
    )


def render_catalog_bytes() -> bytes:
    """Render deterministic UTF-8 bytes with explicit LF line endings."""
    rendered = render_catalog()
    if "\r" in rendered:
        raise ValueError("generated seed catalog must use LF line endings")
    return rendered.encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail when the generated browser catalog is missing or stale",
    )
    args = parser.parse_args()

    expected = render_catalog_bytes()
    if args.check:
        current = OUTPUT_PATH.read_bytes() if OUTPUT_PATH.exists() else None
        if current != expected:
            display_path = (
                OUTPUT_PATH.relative_to(ROOT) if OUTPUT_PATH.is_relative_to(ROOT) else OUTPUT_PATH
            )
            print(
                f"{display_path} is stale; run scripts/generate_demo_seed_catalog.py",
                file=sys.stderr,
            )
            return 1
        return 0

    OUTPUT_PATH.write_bytes(expected)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
