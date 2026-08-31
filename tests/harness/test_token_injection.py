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
        source="replay",
        repo_root=tmp_path,
    )
    original = artifact.read_bytes()
    original_ledger = ledger.read_bytes()
    duplicate_records = ingest_measurement_artifact(
        artifact,
        ledger,
        source="replay",
        repo_root=tmp_path,
    )

    assert records == duplicate_records
    assert artifact.read_bytes() == original
    assert ledger.read_bytes() == original_ledger
    assert len(ledger.read_text(encoding="utf-8").splitlines()) == 2
    assert {record["provenance"]["fixture_type"] for record in records} == {"synthetic"}
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
    assert cursor["provider_usage"]["total"]["status"] == "INSUFFICIENT"


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
                    "cache_usage": {
                        "cache_read": {
                            "tokens": 30,
                            "status": "AVAILABLE",
                            "source_path": "response.usage.cache_read_input_tokens",
                        },
                        "cache_creation": {
                            "tokens": 4,
                            "status": "AVAILABLE",
                            "source_path": "response.usage.cache_creation_input_tokens",
                        },
                        "cache_write": {
                            "tokens": None,
                            "status": "INSUFFICIENT",
                            "source_path": None,
                        },
                        "uncached_input": {
                            "tokens": 70,
                            "status": "AVAILABLE",
                            "source_path": "response.usage.input_tokens",
                        },
                    },
                    "status": "AVAILABLE",
                    "usage_observation": {
                        "status": "AVAILABLE",
                        "reason": "usage_observed",
                        "source_path": "response.usage",
                    },
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
    assert record["cache_read_tokens"] == 30
    assert record["cache_read_status"] == "AVAILABLE"
    assert record["cache_read_source_path"] == "response.usage.cache_read_input_tokens"
    assert record["cache_creation_tokens"] == 4
    assert record["cache_write_tokens"] is None
    assert record["cache_write_status"] == "INSUFFICIENT"
    assert record["uncached_input_tokens"] == 70
    assert record["uncached_input_source_path"] == "response.usage.input_tokens"
    assert record["provider_input_tokens"] == 100
    assert record["provider_input_status"] == "AVAILABLE"
    assert record["provider_input_source_path"] == "response.usage.input_tokens"
    assert record["provider_output_tokens"] == 20
    assert record["provider_total_tokens"] == 120
    assert record["provider_usage_status"] == "AVAILABLE"
    assert record["provider_usage_source_path"] == "response.usage"
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
            "cache_read_tokens": None,
            "cache_read_status": "INSUFFICIENT",
            "cache_read_source_path": None,
            "cache_creation_tokens": None,
            "cache_creation_status": "INSUFFICIENT",
            "cache_creation_source_path": None,
            "cache_write_tokens": None,
            "cache_write_status": "INSUFFICIENT",
            "cache_write_source_path": None,
            "uncached_input_tokens": None,
            "uncached_input_status": "INSUFFICIENT",
            "uncached_input_source_path": None,
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
    changed["provenance"] = {
        **record["provenance"],
        "artifact_sha256": "c" * 64,
    }
    original_ledger = ledger.read_bytes()
    with pytest.raises(TokenInjectionError, match="collision"):
        append_token_injection_measurement(ledger, changed)
    assert ledger.read_bytes() == original_ledger


def test_same_measurement_deduplicates_when_artifact_sha_changes(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    artifact = tmp_path / "capture.json"
    ledger = tmp_path / "harness.jsonl"
    measurement = {
        "host": "cursor-ide",
        "channel": "cursor",
        "layer": "L1",
        "profile": "research",
        "run_id": "run",
        "salt": "salt",
        "repo_ref": "main",
        "repo_sha": "a" * 40,
        "skill_tokens": 1,
        "rule_tokens": 2,
        "report_tokens": 3,
        "context_tokens": 6,
        "uncertainty": {"sample_count": 1, "variance": 0},
        "captured_at": "2026-08-30T00:00:00+00:00",
        "item_id": "item",
    }
    artifact.write_text(json.dumps(measurement, separators=(",", ":")), encoding="utf-8")

    caplog.set_level("INFO", logger="devolaflow.harness.token_injection")
    first = ingest_measurement_artifact(
        artifact,
        ledger,
        source="captured",
        repo_root=tmp_path,
    )
    original_ledger = ledger.read_bytes()
    first_sha = first[0]["provenance"]["artifact_sha256"]

    artifact.write_text(json.dumps(measurement, indent=2) + "\n", encoding="utf-8")
    second = ingest_measurement_artifact(
        artifact,
        ledger,
        source="captured",
        repo_root=tmp_path,
    )

    assert first[0]["event_id"] == second[0]["event_id"]
    assert first_sha != second[0]["provenance"]["artifact_sha256"]
    assert ledger.read_bytes() == original_ledger
    assert len(ledger.read_text(encoding="utf-8").splitlines()) == 1
    assert "reason=measurement_content_match" in caplog.text
    assert "transport_artifact_sha_changed=True" in caplog.text


def test_same_measurement_deduplicates_against_legacy_artifact_bound_event_id(
    tmp_path: Path,
) -> None:
    ledger = tmp_path / "harness.jsonl"
    source = {
        "host": "cursor-ide",
        "channel": "cursor",
        "layer": "L1",
        "profile": "research",
        "run_id": "run",
        "salt": "salt",
        "repo_ref": "main",
        "repo_sha": "a" * 40,
        "skill_tokens": 1,
        "rule_tokens": 2,
        "report_tokens": 3,
        "context_tokens": 6,
        "uncertainty": {"sample_count": 1, "variance": 0},
        "captured_at": "2026-08-30T00:00:00+00:00",
        "item_id": "item",
    }
    legacy = build_token_injection_measurement(
        source,
        source="captured",
        artifact_sha256="b" * 64,
        artifact_path="capture.json",
    )
    legacy["event_id"] = "token_injection_measurement:legacy-artifact-bound-id"
    current = build_token_injection_measurement(
        source,
        source="captured",
        artifact_sha256="c" * 64,
        artifact_path="capture.json",
    )
    append_token_injection_measurement(ledger, legacy)
    original_ledger = ledger.read_bytes()

    append_token_injection_measurement(ledger, current)

    assert ledger.read_bytes() == original_ledger
    assert len(ledger.read_text(encoding="utf-8").splitlines()) == 1


def test_same_identity_with_changed_measurement_is_rejected(tmp_path: Path) -> None:
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
        "uncertainty": {"sample_count": 1, "variance": 0},
        "item_id": "item",
    }
    original = build_token_injection_measurement(
        source,
        source="captured",
        artifact_sha256="b" * 64,
        artifact_path="capture.json",
    )
    changed_source = {**source, "skill_tokens": 2}
    changed = build_token_injection_measurement(
        changed_source,
        source="captured",
        artifact_sha256="c" * 64,
        artifact_path="capture.json",
    )
    append_token_injection_measurement(ledger, original)
    original_ledger = ledger.read_bytes()

    with pytest.raises(TokenInjectionError, match="different measurement") as error:
        append_token_injection_measurement(ledger, changed)

    assert "skill_tokens" in str(error.value)
    assert ledger.read_bytes() == original_ledger


def test_append_dedup_ignores_invalid_unrelated_ledger_history(tmp_path: Path) -> None:
    ledger = tmp_path / "harness.jsonl"
    ledger.write_text(
        json.dumps({"event": "si10_gate", "gate": "legacy-invalid"}) + "\n",
        encoding="utf-8",
    )
    source = {
        "host": "kimi",
        "channel": "kimi",
        "layer": "L2",
        "profile": "cli-probe",
        "run_id": "probe-run",
        "salt": "salt",
        "context_tokens": None,
        "token_usage": {
            "usage_observation": {
                "status": "INSUFFICIENT",
                "reason": "missing_usage",
                "source_path": "$",
            }
        },
    }
    record = build_token_injection_measurement(
        source,
        source="cli_probe",
        artifact_sha256="c" * 64,
        artifact_path="probe.json",
    )

    first = append_token_injection_measurement(ledger, record)
    second = append_token_injection_measurement(ledger, record)

    assert first == second == ledger
    assert len(ledger.read_text(encoding="utf-8").splitlines()) == 2


def test_replay_cannot_claim_captured_or_vendor_doc_provenance() -> None:
    source = {
        "host": "cursor-ide",
        "channel": "cursor",
        "layer": "L1",
        "profile": "replay",
        "run_id": "replay-run",
        "salt": "salt",
        "repo_ref": "main",
        "repo_sha": "a" * 40,
        "context_tokens": 1,
        "uncertainty": {"sample_count": 1, "variance": 0},
        "provenance": {"fixture_type": "captured"},
    }
    with pytest.raises(TokenInjectionError, match="cannot be labeled"):
        build_token_injection_measurement(
            source,
            source="replay",
            artifact_sha256="b" * 64,
            artifact_path="fixture.json",
        )


def test_measurement_schema_accepts_fixture_output(tmp_path: Path) -> None:
    schema = yaml.safe_load(
        (
            Path(__file__).resolve().parents[2] / "schemas" / "token-injection-measurement.yaml"
        ).read_text(encoding="utf-8")
    )
    ledger = tmp_path / "harness.jsonl"
    artifact = tmp_path / "capture.jsonl"
    artifact.write_bytes(FIXTURE.read_bytes())
    ingest_measurement_artifact(artifact, ledger, source="replay", repo_root=tmp_path)
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
