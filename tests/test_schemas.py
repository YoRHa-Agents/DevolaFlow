"""Validate YAML schema docs and example fixtures (structural key presence)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = REPO_ROOT / "schemas"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

EXPECTED_SCHEMA_FILES = [
    SCHEMA_DIR / "workflow-template.schema.yaml",
    SCHEMA_DIR / "task-dispatch.schema.yaml",
    SCHEMA_DIR / "status-report.schema.yaml",
    SCHEMA_DIR / "gate-report.schema.yaml",
    SCHEMA_DIR / "pre-decision-checklist.schema.yaml",
    SCHEMA_DIR / "checkpoint.schema.yaml",
    SCHEMA_DIR / "exception-escalation.schema.yaml",
]

SCHEMA_TO_FIXTURE: list[tuple[Path, Path]] = [
    (SCHEMA_DIR / "workflow-template.schema.yaml", FIXTURES_DIR / "example_template.yaml"),
    (SCHEMA_DIR / "task-dispatch.schema.yaml", FIXTURES_DIR / "example_dispatch.yaml"),
    (SCHEMA_DIR / "status-report.schema.yaml", FIXTURES_DIR / "example_report.yaml"),
    (SCHEMA_DIR / "gate-report.schema.yaml", FIXTURES_DIR / "example_gate_report.yaml"),
    (SCHEMA_DIR / "pre-decision-checklist.schema.yaml", FIXTURES_DIR / "example_checklist.yaml"),
    (SCHEMA_DIR / "checkpoint.schema.yaml", FIXTURES_DIR / "example_checkpoint.yaml"),
    (SCHEMA_DIR / "exception-escalation.schema.yaml", FIXTURES_DIR / "example_escalation.yaml"),
]


def _load_yaml(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    return yaml.safe_load(text)


@pytest.mark.parametrize("schema_path", EXPECTED_SCHEMA_FILES, ids=lambda p: p.name)
def test_schema_files_exist(schema_path: Path):
    assert schema_path.is_file(), f"Missing schema: {schema_path.relative_to(REPO_ROOT)}"


@pytest.mark.parametrize("schema_path", EXPECTED_SCHEMA_FILES, ids=lambda p: p.name)
def test_schema_files_are_valid_yaml(schema_path: Path):
    data = _load_yaml(schema_path)
    assert isinstance(data, dict), f"{schema_path.name} must parse to a mapping"
    assert "design_reference" in data
    assert "instance_top_level_required" in data
    assert isinstance(data["instance_top_level_required"], list)


@pytest.mark.parametrize(
    "fixture_path", [pair[1] for pair in SCHEMA_TO_FIXTURE], ids=lambda p: p.name
)
def test_fixture_files_are_valid_yaml(fixture_path: Path):
    assert fixture_path.is_file(), f"Missing fixture: {fixture_path}"
    data = _load_yaml(fixture_path)
    assert isinstance(data, dict), f"{fixture_path.name} must parse to a mapping"


@pytest.mark.parametrize(
    "schema_path,fixture_path",
    SCHEMA_TO_FIXTURE,
    ids=[pair[1].name for pair in SCHEMA_TO_FIXTURE],
)
def test_fixtures_have_required_top_level_keys(schema_path: Path, fixture_path: Path):
    schema_doc = _load_yaml(schema_path)
    required = schema_doc["instance_top_level_required"]
    instance = _load_yaml(fixture_path)
    missing = [k for k in required if k not in instance]
    assert not missing, f"{fixture_path.name} missing keys {missing} (schema {schema_path.name})"


def test_all_expected_schema_paths_under_schemas_dir():
    for path in EXPECTED_SCHEMA_FILES:
        assert path.parent == SCHEMA_DIR
