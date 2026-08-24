"""Deterministic W-3 evaluator and module-CLI tests."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from devolaflow.harness.__main__ import main
from devolaflow.harness.evaluator import (
    DIMENSION_WEIGHTS,
    SIGNAL_KEYS,
    collect_signals,
    evaluate_harness,
    render_evaluation,
)


def _ledger_record(
    dispatch_id: str,
    *,
    measured: int,
    breakdown: tuple[int, int, int],
    folded: bool,
    timestamp: str,
) -> dict:
    invariant, guard, advisory = breakdown
    count = sum(breakdown)
    return {
        "ts": timestamp,
        "change_id": "eval-change",
        "round": 1,
        "layer": "L0",
        "dispatch_id": dispatch_id,
        "tokens_injected_measured": measured,
        "tokens_budget": 1_000,
        "constraint_count": count,
        "quantifiable_ratio": (invariant + guard) / count,
        "tier_breakdown": {
            "invariant": invariant,
            "guard": guard,
            "advisory": advisory,
        },
        "advisory_folded": folded,
        "model_hint": "quality",
    }


def _write_ledger(path: Path) -> None:
    records = [
        _ledger_record(
            "eval-1",
            measured=800,
            breakdown=(4, 4, 2),
            folded=False,
            timestamp="2026-08-25T00:00:00+00:00",
        ),
        _ledger_record(
            "eval-2",
            measured=1_100,
            breakdown=(5, 3, 2),
            folded=True,
            timestamp="2026-08-25T01:00:00+00:00",
        ),
    ]
    path.write_text(
        "".join(json.dumps(record, separators=(",", ":")) + "\n" for record in records),
        encoding="utf-8",
    )


def _signals(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "ruff_lint": True,
        "ruff_format": True,
        "test_suite": True,
        "coverage_pct": 70,
        "layout_invariant": True,
        "compatibility_suite": False,
        "w17_new_tests": 31,
        "docstring_coverage_pct": 50,
    }
    values.update(overrides)
    return values


def test_exact_six_dimension_rubric_and_composite(tmp_path: Path) -> None:
    ledger = tmp_path / "harness.jsonl"
    _write_ledger(ledger)

    results = [evaluate_harness(ledger, signals=_signals()) for _ in range(3)]
    rendered = [render_evaluation(result).encode() for result in results]
    result = results[0]

    assert rendered[0] == rendered[1] == rendered[2]
    assert result["sampled_at"] == "2026-08-25T01:00:00+00:00"
    assert [entry["id"] for entry in result["scores"]] == list(DIMENSION_WEIGHTS)
    assert [entry["weight"] for entry in result["scores"]] == list(DIMENSION_WEIGHTS.values())
    assert [entry["score"] for entry in result["scores"]] == [8.33, 9.0, 5.0, 7.5, 5.0, 5.0]
    assert result["composite"] == 6.84
    assert result["auto_fill_rate"] == 1.0
    assert result["verdict"] == "NOT_READY"
    assert result["scores"][0]["metadata"]["subcomponents"]["coverage"] == {
        "score": 5.0,
        "available": True,
        "value": 70,
    }
    assert result["scores"][-1]["metadata"]["subcomponents"]["p95_headroom"] == {
        "score": 5.0,
        "available": True,
        "value": 1.1,
    }
    assert [suggestion["dimension"] for suggestion in result["suggestions"]] == [
        "code_quality",
        "test_adequacy",
        "maintainability",
        "compatibility",
        "performance_impact",
    ]


def test_unavailable_or_timed_out_signal_is_insufficient(tmp_path: Path) -> None:
    source = tmp_path / "src" / "devolaflow"
    source.mkdir(parents=True)
    (source / "sample.py").write_text(
        '"""Documented module."""\n\ndef public():\n    """Documented function."""\n',
        encoding="utf-8",
    )
    calls: list[tuple[list[str], dict]] = []

    def timed_out(argv: list[str], **kwargs):
        calls.append((argv, kwargs))
        raise subprocess.TimeoutExpired(argv, kwargs["timeout"])

    collected = collect_signals(tmp_path, base_ref="v15.2.0", runner=timed_out)

    assert [kwargs["timeout"] for _, kwargs in calls] == [60, 60, 300, 60, 120, 30]
    assert all(kwargs["shell"] is False for _, kwargs in calls)
    assert all(isinstance(argv, list) for argv, _ in calls)
    assert all("nines" not in " ".join(argv).lower() for argv, _ in calls)
    assert collected["docstring_coverage_pct"].available is True
    for key in set(SIGNAL_KEYS) - {"docstring_coverage_pct"}:
        assert collected[key].available is False
        assert "timeout" in collected[key].error

    ledger = tmp_path / "harness.jsonl"
    _write_ledger(ledger)

    def subprocess_must_not_run(*_args, **_kwargs):
        raise AssertionError("injected signals must bypass subprocess")

    result = evaluate_harness(
        ledger,
        signals=_signals(
            coverage_pct={"available": False, "error": "coverage executable unavailable"},
            compatibility_suite=True,
            w17_new_tests=0,
            docstring_coverage_pct=100,
        ),
        runner=subprocess_must_not_run,
    )

    assert result["verdict"] == "INSUFFICIENT"
    assert result["auto_fill_rate"] == pytest.approx(12 / 14, abs=0.0001)
    assert [suggestion["dimension"] for suggestion in result["suggestions"][:2]] == [
        "code_quality",
        "test_adequacy",
    ]
    assert [item["reason"] for item in result["suggestions"][:2]] == [
        "unavailable inputs: coverage",
        "unavailable inputs: coverage",
    ]
    assert result["suggestions"][2]["dimension"] == "performance_impact"


def test_module_cli_pins_fixture_style_envelope_and_exit_codes(
    tmp_path: Path,
    capsys,
) -> None:
    ledger = tmp_path / "harness.jsonl"
    _write_ledger(ledger)
    signals_path = tmp_path / "signals.json"
    signals_path.write_text(
        json.dumps(
            _signals(
                coverage_pct=100,
                compatibility_suite=True,
                w17_new_tests=0,
                docstring_coverage_pct=100,
            )
        ),
        encoding="utf-8",
    )
    aggregate_output = tmp_path / "aggregate.json"
    aggregate_exit = main(
        [
            "aggregate",
            "--ledger",
            str(ledger),
            "--output",
            str(aggregate_output),
        ]
    )
    aggregate = json.loads(aggregate_output.read_text(encoding="utf-8"))
    assert aggregate_exit == 0
    assert list(aggregate) == [
        "schema_version",
        "records",
        "changes",
        "rounds",
        "tokens",
        "constraints",
        "models",
    ]
    assert aggregate["records"] == 2
    assert aggregate["tokens"]["total"] == 1_900

    ready_output = tmp_path / "ready.json"

    ready_exit = main(
        [
            "evaluate",
            "--ledger",
            str(ledger),
            "--signals",
            str(signals_path),
            "--output",
            str(ready_output),
        ]
    )
    ready = json.loads(ready_output.read_text(encoding="utf-8"))

    assert ready_exit == 0
    assert ready_output.read_text(encoding="utf-8") == render_evaluation(ready)
    assert list(ready) == [
        "schema_version",
        "sampled_at",
        "threshold",
        "scores",
        "composite",
        "auto_fill_rate",
        "verdict",
        "harness_summary",
        "suggestions",
    ]
    assert ready["verdict"] == "READY"
    assert len(ready["scores"]) == 6
    assert all(set(score) == {"id", "score", "weight", "metadata"} for score in ready["scores"])
    assert "scoring_accuracy" not in {score["id"] for score in ready["scores"]}

    not_ready_exit = main(
        [
            "evaluate",
            "--ledger",
            str(ledger),
            "--signals",
            str(signals_path),
            "--threshold",
            "10",
        ]
    )
    not_ready = json.loads(capsys.readouterr().out)
    assert not_ready_exit == 1
    assert not_ready["verdict"] == "NOT_READY"

    signals_path.write_text(
        json.dumps({"ruff_lint": {"available": False, "error": "ruff unavailable"}}),
        encoding="utf-8",
    )
    insufficient_exit = main(
        [
            "evaluate",
            "--ledger",
            str(ledger),
            "--signals",
            str(signals_path),
        ]
    )
    insufficient = json.loads(capsys.readouterr().out)
    assert insufficient_exit == 2
    assert insufficient["verdict"] == "INSUFFICIENT"

    empty = tmp_path / "empty.jsonl"
    empty.write_text("", encoding="utf-8")
    assert main(["evaluate", "--ledger", str(empty), "--signals", str(signals_path)]) == 2
    assert "ledger segment is empty" in capsys.readouterr().err
