"""Deterministic segmented-ledger aggregation tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from devolaflow.harness.aggregator import (
    AggregationError,
    aggregate_ledger,
    load_ledger_records,
)


def _record(
    dispatch_id: str,
    *,
    change_id: str = "change-a",
    round_number: int = 1,
    layer: str = "L0",
    measured: int = 50,
    budget: int = 100,
    breakdown: tuple[int, int, int] = (1, 0, 0),
    folded: bool = False,
    model: str = "inherit",
    timestamp: str = "2026-08-25T00:00:00+00:00",
) -> dict:
    invariant, guard, advisory = breakdown
    count = sum(breakdown)
    return {
        "ts": timestamp,
        "change_id": change_id,
        "round": round_number,
        "layer": layer,
        "dispatch_id": dispatch_id,
        "tokens_injected_measured": measured,
        "tokens_budget": budget,
        "constraint_count": count,
        "quantifiable_ratio": (invariant + guard) / count if count else 0.0,
        "tier_breakdown": {
            "invariant": invariant,
            "guard": guard,
            "advisory": advisory,
        },
        "advisory_folded": folded,
        "model_hint": model,
    }


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(record, separators=(",", ":")) + "\n" for record in records),
        encoding="utf-8",
    )


def test_segmented_ledger_exact_rollup(tmp_path: Path) -> None:
    base_record = _record(
        "base-first",
        change_id="beta",
        round_number=2,
        layer="L2",
        measured=90,
        breakdown=(0, 1, 1),
        folded=True,
        model="quality",
    )
    segment_records = [
        _record(
            "segment-l0",
            change_id="alpha",
            layer="L0",
            measured=50,
            model="inherit",
        ),
        _record(
            "segment-l1",
            change_id="beta",
            round_number=2,
            layer="L1",
            measured=150,
            breakdown=(0, 0, 0),
            model="budget",
        ),
    ]
    event = {
        "schema_version": 1,
        "event": "proposal_applied",
        "event_id": f"proposal_applied:{'a' * 64}",
        "ts": "2026-08-25T00:00:01+00:00",
        "proposal_id": "a" * 64,
        "proposal_ref": ".local/research/proposal.yaml",
        "approval_ref": ".local/research/proposal.approval.yaml",
        "proposal_sha256": "b" * 64,
        "target_digest": "c" * 64,
    }
    _write_jsonl(tmp_path / "harness.jsonl", [base_record, event])
    _write_jsonl(tmp_path / "harness.1.jsonl", segment_records)

    loaded = load_ledger_records(tmp_path)
    assert [record["dispatch_id"] for record in loaded if "dispatch_id" in record] == [
        "base-first",
        "segment-l0",
        "segment-l1",
    ]
    assert loaded[1] == event
    summary = aggregate_ledger(tmp_path)

    assert summary["schema_version"] == 1
    assert summary["records"] == 3
    assert summary["events"] == [event]
    assert summary["changes"] == ["alpha", "beta"]
    assert summary["rounds"] == {"min": 1, "max": 2, "distinct": 2}
    assert summary["tokens"]["total"] == 290
    assert summary["tokens"]["mean"] == pytest.approx(290 / 3)
    assert summary["tokens"]["p50"] == 90
    assert summary["tokens"]["p95"] == 150
    assert summary["tokens"]["budget_compliance_ratio"] == pytest.approx(2 / 3)
    assert summary["tokens"]["p95_budget_utilization"] == 1.5
    assert list(summary["tokens"]["by_layer"]) == ["L0", "L1", "L2"]
    assert summary["constraints"] == {
        "count": 3,
        "tier_breakdown": {"invariant": 1, "guard": 1, "advisory": 1},
        "quantifiable_ratio": pytest.approx(2 / 3),
        "advisory_folded_ratio": pytest.approx(1 / 3),
    }
    assert summary["models"] == {"budget": 1, "inherit": 1, "quality": 1}


@pytest.mark.parametrize(
    "case",
    [
        "empty",
        "json",
        "missing",
        "ratio",
        "tier-sum",
        "segment-gap",
        "segment-name",
        "event",
    ],
)
def test_empty_or_malformed_ledger_fails_explicitly(tmp_path: Path, case: str) -> None:
    base = tmp_path / "harness.jsonl"
    record = _record("bad-record")
    if case == "empty":
        base.write_text("", encoding="utf-8")
    elif case == "json":
        base.write_text("{bad json}\n", encoding="utf-8")
    elif case == "missing":
        del record["layer"]
        _write_jsonl(base, [record])
    elif case == "ratio":
        record["quantifiable_ratio"] = 1.5
        _write_jsonl(base, [record])
    elif case == "tier-sum":
        record["tier_breakdown"]["guard"] = 1
        _write_jsonl(base, [record])
    elif case == "segment-gap":
        _write_jsonl(base, [record])
        _write_jsonl(tmp_path / "harness.2.jsonl", [record])
    elif case == "segment-name":
        _write_jsonl(base, [record])
        _write_jsonl(tmp_path / "harness.01.jsonl", [record])
    else:
        _write_jsonl(
            base,
            [
                {
                    "schema_version": 1,
                    "event": "proposal_applied",
                    "event_id": "proposal_applied:not-a-hash",
                    "ts": "2026-08-25T00:00:00+00:00",
                    "proposal_id": "not-a-hash",
                    "proposal_ref": "../proposal.yaml",
                    "approval_ref": "approval.yaml",
                    "proposal_sha256": "b" * 64,
                    "target_digest": "c" * 64,
                }
            ],
        )

    with pytest.raises(AggregationError) as caught:
        aggregate_ledger(tmp_path)

    assert str(tmp_path) in str(caught.value)
    if case not in {"empty", "segment-gap", "segment-name"}:
        assert ":1:" in str(caught.value)


def test_aggregation_is_identical_across_three_runs(tmp_path: Path) -> None:
    _write_jsonl(
        tmp_path / "harness.jsonl",
        [
            _record("d-2", layer="L2", model="quality"),
            _record("d-1", layer="L0", model="budget"),
        ],
    )

    rendered = [
        json.dumps(aggregate_ledger(tmp_path), ensure_ascii=False, separators=(",", ":"))
        for _ in range(3)
    ]

    assert rendered[0].encode() == rendered[1].encode() == rendered[2].encode()
