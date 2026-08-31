"""Ghost audit for Phase C harness evidence semantics."""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator


def test_kimi_stream_replay_fixture_has_explicit_provenance_and_missing_usage(
    project_root: Path,
) -> None:
    schema = yaml.safe_load(
        (project_root / "schemas" / "kimi-stream-json-diagnostic.yaml").read_text(encoding="utf-8")
    )
    fixture = json.loads(
        (
            project_root / "tests" / "fixtures" / "harness" / "kimi_stream_json_missing_usage.json"
        ).read_text(encoding="utf-8")
    )
    assert list(Draft202012Validator(schema).iter_errors(fixture)) == []
    assert fixture["fixture_provenance"] == "replay"
    assert len(fixture["events"]) == 5
    forbidden = {"usage", "token_usage", "skill_loaded"}
    assert not any(
        forbidden.intersection(event) for event in fixture["events"] if isinstance(event, dict)
    )


def test_token_injection_schema_declares_fixture_provenance_types(project_root: Path) -> None:
    schema = yaml.safe_load(
        (project_root / "schemas" / "token-injection-measurement.yaml").read_text(encoding="utf-8")
    )
    provenance = schema["properties"]["provenance"]["properties"]
    assert provenance["fixture_type"]["enum"] == [
        "captured",
        "vendor-doc",
        "synthetic",
        "replay",
    ]
