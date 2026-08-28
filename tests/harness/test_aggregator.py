"""Deterministic segmented-ledger aggregation tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from devolaflow.harness.aggregator import (
    AggregationError,
    aggregate_ledger,
    aggregate_metric_observations,
    load_ledger_records,
)
from devolaflow.harness.telemetry import (
    CONSOLIDATION_METRIC_NAMES,
    MetricObservationError,
    append_metric_observation,
    build_consolidation_metrics_record,
    build_metric_observation,
    build_metric_observation_record,
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


def _observation(*, value: int | float, metric: str = "agents_md_tokens") -> dict:
    return {
        "schema_version": 1,
        "cycle": "v19.0.0",
        "pv": "PV-2",
        "item_id": "O-3" if metric == "agents_md_tokens" else "O-5",
        "metric": metric,
        "statistic": "full_tokens" if metric == "agents_md_tokens" else "wall_seconds",
        "value": value,
        "unit": "tokens" if metric == "agents_md_tokens" else "seconds",
        "direction": "decrease",
        "sample_count": 1,
        "warmup_count": 0,
        "captured_at": "2026-08-28T00:00:00Z",
        "source_revision": "revision-a",
        "command": {
            "argv": ["python", "-c", "probe"],
            "cwd": ".",
            "timeout_seconds": 60,
        },
        "environment": {
            "os": "Darwin 25.6.0",
            "architecture": "arm64",
            "python": "3.11.0",
            "implementation": "CPython",
            "dependencies": "sha256:dependencies",
            "relevant_variables": {"GHOST_FULL": "1"},
            "config_files": [{"path": "AGENTS.md", "sha256": "a" * 64}],
        },
        "measurement": {
            "cache_state": "cold",
            "extraction_definition": "verbatim metric definition",
            "provenance": "tests/output.txt",
        },
    }


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


def test_optional_slice_metrics_are_none_when_absent_and_partial_mean_otherwise(
    tmp_path: Path,
) -> None:
    """v17.0.0 R3 (D-R3-2): ``host_rule_tokens`` / ``slice_savings_pct``
    stay OUT of the required field set — a pre-v17 ledger aggregates with
    both means emitted as ``None`` (mirroring the ``rounds.min/max``
    absent-metric style) — and a mixed ledger averages ONLY the records
    that carry the fields."""
    legacy = _record("legacy-record")
    _write_jsonl(tmp_path / "harness.jsonl", [legacy])

    legacy_summary = aggregate_ledger(tmp_path)
    assert "host_rule_tokens_mean" in legacy_summary["tokens"]
    assert "agents_md_tokens_mean" in legacy_summary["tokens"]
    assert "slice_savings_pct_mean" in legacy_summary["tokens"]
    assert legacy_summary["tokens"]["host_rule_tokens_mean"] is None
    assert legacy_summary["tokens"]["agents_md_tokens_mean"] is None
    assert legacy_summary["tokens"]["slice_savings_pct_mean"] is None

    carrying_a = _record("carrying-a")
    carrying_a["host_rule_tokens"] = 12_000
    carrying_a["agents_md_tokens"] = 12_000
    carrying_a["slice_savings_pct"] = 70.0
    carrying_b = _record("carrying-b")
    carrying_b["host_rule_tokens"] = 10_000
    carrying_b["agents_md_tokens"] = 10_000
    carrying_b["slice_savings_pct"] = 80.0
    _write_jsonl(tmp_path / "harness.jsonl", [legacy, carrying_a, carrying_b])

    mixed_summary = aggregate_ledger(tmp_path)
    assert mixed_summary["records"] == 3
    assert mixed_summary["tokens"]["host_rule_tokens_mean"] == pytest.approx(11_000)
    assert mixed_summary["tokens"]["agents_md_tokens_mean"] == pytest.approx(11_000)
    assert mixed_summary["tokens"]["slice_savings_pct_mean"] == pytest.approx(75.0)

    invalid = _record("invalid-savings")
    invalid["slice_savings_pct"] = 150.0
    _write_jsonl(tmp_path / "harness.jsonl", [invalid])
    with pytest.raises(AggregationError, match="slice_savings_pct"):
        aggregate_ledger(tmp_path)


def test_consolidation_metrics_are_aggregated_with_explicit_missing_values(
    tmp_path: Path,
) -> None:
    dispatch = _record("dispatch")
    dispatch["agents_md_tokens"] = 12_000
    event = build_consolidation_metrics_record(
        {
            "agents_md_tokens": 10_000,
            "suite_wall_seconds": 12.5,
            "cjk_violations": 2,
            "ghost_loc": 40,
        },
        timestamp="2026-08-28T00:00:00+00:00",
    )
    _write_jsonl(tmp_path / "harness.jsonl", [dispatch, event])

    summary = aggregate_ledger(tmp_path)

    assert list(summary["measurements"]) == list(CONSOLIDATION_METRIC_NAMES)
    assert summary["measurements"] == {
        "agents_md_tokens": {"mean": 10_000, "observed_records": 1, "status": "AVAILABLE"},
        "suite_wall_seconds": {"mean": 12.5, "observed_records": 1, "status": "AVAILABLE"},
        "cjk_violations": {"mean": 2.0, "observed_records": 1, "status": "AVAILABLE"},
        "ghost_loc": {"mean": 40.0, "observed_records": 1, "status": "AVAILABLE"},
    }


def test_historical_dispatch_without_consolidation_metrics_is_explicitly_insufficient(
    tmp_path: Path,
) -> None:
    _write_jsonl(tmp_path / "harness.jsonl", [_record("legacy")])

    summary = aggregate_ledger(tmp_path)

    for name in CONSOLIDATION_METRIC_NAMES:
        assert summary["measurements"][name] == {
            "mean": None,
            "observed_records": 0,
            "status": "INSUFFICIENT",
        }


def test_metric_observation_is_strict_and_aggregate_surfaces_provenance(
    tmp_path: Path,
) -> None:
    baseline = _observation(value=100)
    current = {**baseline, "source_revision": "revision-b", "value": 75}
    record = build_metric_observation_record(current)
    _write_jsonl(tmp_path / "harness.jsonl", [_record("legacy"), record])

    summary = aggregate_ledger(tmp_path)

    assert summary["metric_observations"] == [record]
    assert summary["measurements"]["agents_md_tokens"]["status"] == "AVAILABLE"
    assert summary["measurements"]["agents_md_tokens"]["provenance"][0]["source_revision"] == (
        "revision-b"
    )
    comparison = aggregate_metric_observations([baseline], [record])
    assert comparison["status"] == "AVAILABLE"
    assert comparison["comparisons"][0]["relative_improvement_pct"] == 25.0

    malformed = dict(baseline)
    del malformed["environment"]
    with pytest.raises(MetricObservationError, match="keys mismatch"):
        build_metric_observation(malformed)


def test_append_metric_observation_preserves_structured_record(tmp_path: Path) -> None:
    observation = _observation(value=100)
    ledger = tmp_path / "harness.jsonl"

    destination = append_metric_observation(ledger, observation)

    assert destination == ledger
    assert load_ledger_records(ledger) == [build_metric_observation_record(observation)]


def test_metric_observation_comparison_marks_absence_mismatch_and_zero_baseline_insufficient() -> (
    None
):
    baseline = _observation(value=100)
    current = {**baseline, "source_revision": "revision-b", "value": 80}
    assert (
        aggregate_metric_observations([baseline], [current])["comparisons"][0][
            "relative_improvement_pct"
        ]
        == 20.0
    )

    mismatched = {
        **current,
        "command": {**current["command"], "timeout_seconds": 30},
    }
    mismatch = aggregate_metric_observations([baseline], [mismatched])["comparisons"][0]
    assert mismatch["status"] == "INSUFFICIENT"
    assert "command" in mismatch["mismatched_fields"]
    assert "relative_improvement_pct" not in mismatch

    zero = aggregate_metric_observations([_observation(value=0)], [current])["comparisons"][0]
    assert zero["status"] == "INSUFFICIENT"
    assert "positive" in zero["reason"]

    absent = aggregate_metric_observations([baseline], [])["comparisons"][0]
    assert absent["status"] == "INSUFFICIENT"


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
