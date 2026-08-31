"""PV-04 offline token-injection ingestion and aggregation contracts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

from devolaflow.harness import (
    TOKEN_INJECTION_EVENT,
    TokenInjectionError,
    aggregate_ledger,
    append_token_injection_measurement,
    build_token_injection_measurement,
    ingest_cli_probe_artifact,
    ingest_measurement_artifact,
    validate_token_injection_measurement,
)
from devolaflow.harness.cursor_capture import (
    ingest_cursor_ide_capture,
    parse_cursor_ide_transcript,
)

FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "harness" / "token_injection_captured.jsonl"
)
SIX_HOST_FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "harness" / "token_injection_six_hosts.jsonl"
)


def test_captured_fixture_replay_is_append_only_and_aggregates_by_host_channel(
    tmp_path: Path,
) -> None:
    ledger = tmp_path / "harness.jsonl"
    artifact = tmp_path / "captured.jsonl"
    artifact.write_bytes(FIXTURE.read_bytes())

    records = ingest_measurement_artifact(
        artifact,
        ledger,
        source="captured",
        repo_root=tmp_path,
    )
    original = artifact.read_bytes()
    duplicate_records = ingest_measurement_artifact(
        artifact,
        ledger,
        source="captured",
        repo_root=tmp_path,
    )

    assert records == duplicate_records
    assert artifact.read_bytes() == original
    assert len(ledger.read_text(encoding="utf-8").splitlines()) == 2
    summary = aggregate_ledger(ledger)["token_injection"]
    assert summary["status"] == "AVAILABLE"
    assert set(summary["by_host_channel"]) == {"claude/claude", "cursor-ide/cursor"}
    cursor = summary["by_host_channel"]["cursor-ide/cursor"]
    assert cursor["components"]["context"] == {
        "mean": 240,
        "variance": 0,
        "interval": {"low": 240, "high": 240},
        "coverage": {
            "observed_records": 1,
            "total_records": 1,
            "ratio": 1.0,
            "status": "AVAILABLE",
        },
        "status": "AVAILABLE",
    }


def test_cli_probe_import_does_not_promote_total_usage_to_component_measurement(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "probe.json"
    artifact.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "event": "cli_probe",
                "channel": "claude",
                "metadata": {
                    "run_id": "probe-run",
                    "salt": "pv04",
                    "generated_at": "2026-08-30T00:00:00+00:00",
                },
                "token_usage": {
                    "input_tokens": 100,
                    "output_tokens": 20,
                    "total_tokens": 120,
                    "status": "AVAILABLE",
                },
            }
        ),
        encoding="utf-8",
    )
    record = ingest_cli_probe_artifact(
        artifact,
        tmp_path / "harness.jsonl",
        repo_root=tmp_path,
        layer="L2",
        profile="research",
    )

    assert record["event"] == TOKEN_INJECTION_EVENT
    assert record["source"] == "cli_probe"
    assert record["context_tokens"] is None
    assert record["context_status"] == "INSUFFICIENT"
    assert record["status"] == "INSUFFICIENT"


def test_missing_observation_and_reproducibility_metadata_are_explicitly_insufficient() -> None:
    record = validate_token_injection_measurement(
        {
            "schema_version": 1,
            "event": TOKEN_INJECTION_EVENT,
            "event_id": "event-1",
            "ts": "2026-08-30T00:00:00+00:00",
            "host": "cursor-ide",
            "channel": "cursor",
            "layer": "L0",
            "profile": "default",
            "run_id": None,
            "run_id_status": "INSUFFICIENT",
            "salt": None,
            "salt_status": "INSUFFICIENT",
            "repo_ref": None,
            "repo_ref_status": "INSUFFICIENT",
            "repo_sha": None,
            "repo_sha_status": "INSUFFICIENT",
            "source": "replay",
            "provenance": {
                "kind": "fixture-replay",
                "artifact_path": "fixture.jsonl",
                "artifact_sha256": "a" * 64,
            },
            "skill_tokens": None,
            "skill_status": "INSUFFICIENT",
            "rule_tokens": None,
            "rule_status": "INSUFFICIENT",
            "report_tokens": None,
            "report_status": "INSUFFICIENT",
            "context_tokens": None,
            "context_status": "INSUFFICIENT",
            "uncertainty": {
                "sample_count": None,
                "variance": None,
                "interval": None,
                "status": "INSUFFICIENT",
            },
            "status": "INSUFFICIENT",
        }
    )
    assert record["run_id"] is None
    assert record["skill_tokens"] is None


def test_event_id_collision_with_changed_record_is_rejected(tmp_path: Path) -> None:
    ledger = tmp_path / "harness.jsonl"
    source = {
        "host": "cursor-ide",
        "channel": "cursor",
        "layer": "L1",
        "profile": "default",
        "run_id": "run",
        "salt": "salt",
        "repo_ref": "main",
        "repo_sha": "a" * 40,
        "skill_tokens": 1,
        "rule_tokens": 1,
        "report_tokens": 1,
        "context_tokens": 3,
        "uncertainty": {"sample_count": 2, "variance": 1},
    }
    record = build_token_injection_measurement(
        source,
        source="captured",
        artifact_sha256="b" * 64,
        artifact_path="capture.json",
    )
    append_token_injection_measurement(ledger, record)
    changed = dict(record)
    changed["skill_tokens"] = 2
    with pytest.raises(TokenInjectionError, match="collision"):
        append_token_injection_measurement(ledger, changed)


def test_measurement_schema_accepts_fixture_output(tmp_path: Path) -> None:
    schema = yaml.safe_load(
        (
            Path(__file__).resolve().parents[2] / "schemas" / "token-injection-measurement.yaml"
        ).read_text(encoding="utf-8")
    )
    ledger = tmp_path / "harness.jsonl"
    artifact = tmp_path / "capture.jsonl"
    artifact.write_bytes(FIXTURE.read_bytes())
    ingest_measurement_artifact(artifact, ledger, source="captured", repo_root=tmp_path)
    validator = Draft202012Validator(schema)
    for line in ledger.read_text(encoding="utf-8").splitlines():
        assert list(validator.iter_errors(json.loads(line))) == []


def test_six_host_replay_fixture_is_schema_valid_and_deterministic(tmp_path: Path) -> None:
    artifact = tmp_path / "six-hosts.jsonl"
    artifact.write_bytes(SIX_HOST_FIXTURE.read_bytes())
    ledger = tmp_path / "harness.jsonl"

    first = ingest_measurement_artifact(
        artifact,
        ledger,
        source="replay",
        repo_root=tmp_path,
    )
    second = ingest_measurement_artifact(
        artifact,
        ledger,
        source="replay",
        repo_root=tmp_path,
    )

    assert first == second
    assert {record["host"] for record in first} == {
        "cursor",
        "claude",
        "codex",
        "kimicode",
        "dsh",
        "copilot",
    }
    assert all(record["status"] == "AVAILABLE" for record in first)
    assert all(record["provenance"]["kind"] == "fixture-replay" for record in first)
    assert len(ledger.read_text(encoding="utf-8").splitlines()) == 6


def test_cursor_ide_capture_parser_preserves_explicit_fields_and_missing_evidence(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "cursor-capture.jsonl"
    artifact.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "type": "session",
                        "run_id": "cursor-run",
                        "salt": "pv04",
                        "repo_ref": "main",
                        "repo_sha": "a" * 40,
                        "layer": "L1",
                        "profile": "manual",
                    }
                ),
                json.dumps(
                    {
                        "type": "measurement",
                        "skill_tokens": 120,
                        "captured_at": "2026-08-30T02:00:00+00:00",
                        "content": "token counts are not inferred from this text",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    parsed = parse_cursor_ide_transcript(artifact)
    assert parsed[0]["host"] == "cursor"
    assert parsed[0]["channel"] == "cursor-ide"
    assert parsed[0]["skill_tokens"] == 120
    assert parsed[0]["provenance"] == {"kind": "captured"}
    records = ingest_cursor_ide_capture(
        artifact,
        tmp_path / "harness.jsonl",
        repo_root=tmp_path,
    )
    assert records[0]["source"] == "captured"
    assert records[0]["provenance"]["kind"] == "captured"
    assert records[0]["skill_tokens"] == 120
    assert records[0]["rule_tokens"] is None
    assert records[0]["rule_status"] == "INSUFFICIENT"
    assert records[0]["status"] == "INSUFFICIENT"
