"""Contract checks for the combined local-archive artifact schema."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "local-archive.schema.yaml"


def _schema() -> dict:
    parsed = yaml.safe_load(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert isinstance(parsed, dict)
    return parsed


def test_local_archive_schema_is_valid_and_bounded() -> None:
    schema = _schema()

    assert schema["schema_name"] == "local-archive"
    assert schema["schema_version"] == 1
    assert schema["source_boundary"] == ".local/tasks"
    assert schema["instance_top_level_required"] == ["artifact_type", "schema_version"]
    assert schema["lifecycle"]["enum"] == ["active", "done", "stale", "unknown"]
    assert "protected" not in schema["lifecycle"]["enum"]
    assert "protection" in schema
    assert "protected" in schema["protection"]["enum"]


def test_schema_defines_separate_plan_index_mapping_contracts() -> None:
    contracts = _schema()["contracts"]

    assert set(contracts) == {"plan", "index", "mapping"}
    assert contracts["plan"]["artifact_type"] == "task-archive-plan"
    assert contracts["index"]["artifact_type"] == "task-archive-index"
    assert contracts["mapping"]["artifact_type"] == "task-archive-mapping"
    assert contracts["mapping"]["append_only"] is True
    assert contracts["mapping"]["no_clobber"] is True
    examples = _schema()["examples"]

    assert examples["plan"]["entries"][0]["action"] == "move"
    assert examples["index"]["generated"] is True
    assert examples["mapping"]["sequence"] == 1
    for path in (
        examples["plan"]["entries"][0]["source"],
        examples["plan"]["entries"][0]["destination"],
        examples["mapping"]["source"],
        examples["mapping"]["destination"],
    ):
        assert not Path(path).is_absolute()
        assert "\\" not in path


def test_schema_protected_surfaces_are_explicit() -> None:
    protected = _schema()["protected_prefixes"]

    for prefix in (".local/.agent/", ".local/memory/specs/", ".local/research/"):
        assert prefix in protected
    assert ".rules/" in protected
    assert "src/" in protected
