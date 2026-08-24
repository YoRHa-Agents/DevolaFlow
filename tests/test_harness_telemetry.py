"""Focused tests for M2 post-dispatch harness telemetry."""

from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

import devolaflow.harness.telemetry as telemetry
from devolaflow.harness import (
    HARNESS_SEGMENT_MAX_BYTES,
    LAYER_TOKEN_BUDGETS,
    append_harness_record,
    build_dispatch_record,
    record_dispatch_telemetry,
)
from devolaflow.lifecycle import (
    POST_DISPATCH_EVENT,
    list_handlers,
    post_dispatch,
    register_hook,
)

EXPECTED_RECORD_KEYS = [
    "ts",
    "change_id",
    "round",
    "layer",
    "dispatch_id",
    "tokens_injected_measured",
    "tokens_budget",
    "constraint_count",
    "quantifiable_ratio",
    "tier_breakdown",
    "advisory_folded",
    "model_hint",
]


def _payload(
    *,
    change_id: str | None = None,
    layer: str = "L2",
    checklist_count: int = 2,
) -> dict:
    change_context = {
        "round_context": {"round_n": 3, "reverted_ids": []},
        "checklist_items": [
            {
                "id": f"C-G1.{index}",
                "assert": f"assertion {index}",
                "verify": f"pytest test_{index}",
                "priority": "P1",
            }
            for index in range(1, checklist_count + 1)
        ],
    }
    if change_id is not None:
        change_context["change_id"] = change_id
    return {
        "hdr": {"id": "dispatch-telemetry-001"},
        "task": {"id": "T1", "title": "Measure dispatch"},
        "change_context": change_context,
        "layer": layer,
        "model_hint": "quality",
    }


def _active_folder(root: Path, change_id: str) -> Path:
    folder = root / ".local" / ".agent" / "active" / change_id
    folder.mkdir(parents=True)
    return folder


def test_build_dispatch_record_uses_exact_schema_and_stable_yaml(monkeypatch) -> None:
    payload = _payload(change_id="measure-dispatch")
    rendered: list[str] = []

    def fake_estimate(text: str) -> int:
        rendered.append(text)
        return 321

    monkeypatch.setattr(telemetry, "estimate_tokens", fake_estimate)
    record = build_dispatch_record(
        payload,
        change_id="measure-dispatch",
        timestamp="2026-08-24T14:00:00+00:00",
    )

    assert list(record) == EXPECTED_RECORD_KEYS
    assert record == {
        "ts": "2026-08-24T14:00:00+00:00",
        "change_id": "measure-dispatch",
        "round": 3,
        "layer": "L2",
        "dispatch_id": "dispatch-telemetry-001",
        "tokens_injected_measured": 321,
        "tokens_budget": 8_000,
        "constraint_count": 2,
        "quantifiable_ratio": 1.0,
        "tier_breakdown": {"invariant": 0, "guard": 2, "advisory": 0},
        "advisory_folded": False,
        "model_hint": "quality",
    }
    assert rendered == [
        yaml.safe_dump(
            payload,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=True,
        )
    ]
    assert HARNESS_SEGMENT_MAX_BYTES == 64 * 1024
    assert LAYER_TOKEN_BUDGETS == {"L0": 5_000, "L1": 5_000, "L2": 8_000}


@pytest.mark.parametrize("bad_items", [[], [{}] * 6, "not-a-list"])
def test_build_dispatch_record_enforces_m2_checklist_count_guard(bad_items) -> None:
    payload = _payload(change_id="bad-checklist")
    payload["change_context"]["checklist_items"] = bad_items

    with pytest.raises(ValueError, match="checklist_items"):
        build_dispatch_record(payload, change_id="bad-checklist")


def test_append_harness_record_is_compact_and_rotates_without_rewrite(tmp_path: Path) -> None:
    folder = tmp_path / "change"
    folder.mkdir()
    record = {"ts": "now", "change_id": "change", "value": "x" * 20}
    encoded = (json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
    max_bytes = len(encoded) + 8
    original = b"p" * 9
    base = folder / "harness.jsonl"
    base.write_bytes(original)

    target = append_harness_record(folder, record, max_bytes=max_bytes)

    assert target == folder / "harness.1.jsonl"
    assert base.read_bytes() == original
    assert target.read_bytes() == encoded
    assert b'": "' not in encoded


def test_append_harness_record_warns_and_skips_oversize(
    tmp_path: Path,
    caplog,
) -> None:
    folder = tmp_path / "change"
    folder.mkdir()

    with caplog.at_level("WARNING", logger="devolaflow.harness.telemetry"):
        target = append_harness_record(folder, {"oversize": "x" * 100}, max_bytes=20)

    assert target is None
    assert not list(folder.glob("harness*.jsonl"))
    assert "exceeding" in caplog.text


def test_record_dispatch_telemetry_prefers_explicit_change_id(tmp_path: Path) -> None:
    alpha = _active_folder(tmp_path, "alpha")
    beta = _active_folder(tmp_path, "beta")
    payload = _payload(change_id="beta")
    before = copy.deepcopy(payload)

    result = record_dispatch_telemetry(payload, repo_root=tmp_path)

    assert result.passed is True
    assert payload == before
    assert not (alpha / "harness.jsonl").exists()
    records = [json.loads(line) for line in (beta / "harness.jsonl").read_text().splitlines()]
    assert [record["change_id"] for record in records] == ["beta"]


def test_record_dispatch_telemetry_resolves_only_one_implicit_active_change(
    tmp_path: Path,
    caplog,
) -> None:
    payload = _payload()
    none_result = record_dispatch_telemetry(payload, repo_root=tmp_path)
    assert none_result.metadata["reason"] == "no unambiguous active change"

    only = _active_folder(tmp_path, "only")
    one_result = record_dispatch_telemetry(payload, repo_root=tmp_path)
    assert one_result.passed is True
    assert (only / "harness.jsonl").is_file()

    second = _active_folder(tmp_path, "second")
    with caplog.at_level("WARNING", logger="devolaflow.harness.telemetry"):
        multiple_result = record_dispatch_telemetry(payload, repo_root=tmp_path)
    assert multiple_result.metadata["reason"] == "no unambiguous active change"
    assert not (second / "harness.jsonl").exists()
    assert "found 2 active changes" in caplog.text


def test_attribution_and_io_failures_warn_without_blocking(
    tmp_path: Path,
    caplog,
) -> None:
    folder = _active_folder(tmp_path, "failure-case")
    bad_payload = _payload(change_id="failure-case")
    del bad_payload["layer"]

    with caplog.at_level("WARNING", logger="devolaflow.harness.telemetry"):
        attribution_result = record_dispatch_telemetry(bad_payload, repo_root=tmp_path, strict=True)
        with patch.object(Path, "open", side_effect=OSError("disk unavailable")):
            io_result = record_dispatch_telemetry(
                _payload(change_id="failure-case"),
                repo_root=tmp_path,
            )

    assert attribution_result.passed is True
    assert io_result.passed is True
    assert not (folder / "harness.jsonl").exists()
    assert "attribution failed" in caplog.text
    assert "disk unavailable" in caplog.text


def test_post_dispatch_telemetry_registration_is_default_first_and_idempotent() -> None:
    for _ in range(2):
        if record_dispatch_telemetry not in list_handlers(POST_DISPATCH_EVENT):
            register_hook(POST_DISPATCH_EVENT, record_dispatch_telemetry)

    handlers = list_handlers(POST_DISPATCH_EVENT)
    assert handlers[0] is post_dispatch
    assert handlers.count(record_dispatch_telemetry) == 1


def test_warm_handler_mean_under_five_ms_and_payload_unchanged(tmp_path: Path) -> None:
    _active_folder(tmp_path, "warm-handler")
    payload = _payload(change_id="warm-handler")
    before = copy.deepcopy(payload)
    record_dispatch_telemetry(payload, repo_root=tmp_path)

    started = time.perf_counter()
    for _ in range(50):
        result = record_dispatch_telemetry(payload, repo_root=tmp_path)
        assert result.passed is True
    mean_ms = (time.perf_counter() - started) * 1_000 / 50

    assert mean_ms < 5.0
    assert payload == before
