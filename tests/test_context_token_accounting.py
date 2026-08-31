"""PV-03 tests for component token accounting and ceremony-share checks."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import devolaflow.harness.context_tokens as context_tokens
import devolaflow.harness.telemetry as telemetry
from devolaflow.gate.budget import (
    CEREMONY_SHARE_WARN_THRESHOLD,
    TokenBudgetBreaker,
    check_ceremony_share,
)
from devolaflow.gate.profiles import STANDARD
from devolaflow.harness.aggregator import aggregate_ledger
from devolaflow.harness.telemetry import (
    CONTEXT_TOKEN_EVENT,
    append_context_token_record,
    build_dispatch_record,
    build_report_telemetry_record,
    measure_context_tokens,
)
from devolaflow.lifecycle.assert_layer_budget import assert_layer_token_budget
from devolaflow.lifecycle.dispatcher import HookViolation


def test_component_measurement_distinguishes_missing_and_empty(monkeypatch) -> None:
    monkeypatch.setattr(context_tokens, "estimate_tokens", lambda text: len(text) // 2)

    assert measure_context_tokens(skill_text=None, rule_text="", report_envelope={}) == {
        "skill_tokens": None,
        "rule_tokens": 0,
        "report_tokens": 0,
    }
    assert "not observe provider usage" in context_tokens.estimate_text_tokens.__doc__


def test_report_mapping_measurement_is_stable_and_reproducible(monkeypatch) -> None:
    monkeypatch.setattr(context_tokens, "estimate_tokens", lambda text: len(text))
    report = {"state": "completed", "task_id": "T2"}

    first = build_report_telemetry_record(
        report,
        skill_text="skill",
        rule_text="rules",
        timestamp="2026-08-29T00:00:00+00:00",
    )
    second = build_report_telemetry_record(
        {"task_id": "T2", "state": "completed"},
        skill_text="skill",
        rule_text="rules",
        timestamp="2026-08-29T00:00:00+00:00",
    )

    assert first == second
    assert first["context_tokens"]["report_tokens"] == len("state: completed\ntask_id: T2\n")


def test_dispatch_record_nests_explicit_context_tokens_without_legacy_shape_drift(
    monkeypatch,
) -> None:
    monkeypatch.setattr(telemetry, "_slice_injection_metrics", lambda payload: (0, 0.0))
    payload = {
        "hdr": {"id": "dispatch-1"},
        "task": {"id": "T2"},
        "change_context": {
            "round_context": {"round_n": 1},
            "checklist_items": [{"id": "AC-1"}],
        },
        "layer": "L2",
    }

    legacy = build_dispatch_record(payload, change_id="t2")
    measured = build_dispatch_record(
        payload,
        change_id="t2",
        context_tokens={"skill_tokens": 12, "rule_tokens": 34, "report_tokens": None},
    )

    assert "context_tokens" not in legacy
    assert measured["context_tokens"] == {
        "skill_tokens": 12,
        "rule_tokens": 34,
        "report_tokens": None,
    }


def test_report_record_and_ledger_aggregation_preserve_nulls(tmp_path: Path) -> None:
    ledger = tmp_path / "harness.jsonl"
    append_context_token_record(
        ledger,
        None,
        context_tokens={"skill_tokens": None, "rule_tokens": 20, "report_tokens": 0},
        timestamp="2026-08-29T00:00:00+00:00",
    )

    record = json.loads(ledger.read_text().strip())
    assert record["event"] == CONTEXT_TOKEN_EVENT
    assert record["context_tokens"]["skill_tokens"] is None
    summary = aggregate_ledger(ledger)
    assert summary["tokens"]["context_tokens"]["skill_tokens"]["status"] == "INSUFFICIENT"
    assert summary["tokens"]["context_tokens"]["rule_tokens"]["mean"] == 20
    assert summary["tokens"]["context_tokens"]["report_tokens"]["mean"] == 0


def test_ceremony_share_boundary_is_strictly_greater_than_half() -> None:
    exact = check_ceremony_share(50, 100)
    over = check_ceremony_share(51, 100)

    assert exact.action.value == "CONTINUE"
    assert over.action.value == "WARN"
    assert CEREMONY_SHARE_WARN_THRESHOLD == 0.5


def test_pre_dispatch_missing_and_empty_accounting_are_explicit_noops() -> None:
    payload = {"task_id": "T2", "layer": "L2"}

    missing = assert_layer_token_budget(payload)
    empty = assert_layer_token_budget(
        payload,
        context_tokens={"skill_tokens": 0, "rule_tokens": 0, "report_tokens": 0},
    )

    assert missing.passed is True
    assert missing.metadata["ceremony_source"] == "missing:INSUFFICIENT"
    assert empty.passed is True
    assert empty.metadata["ceremony_tokens"] == 0
    assert empty.metadata["ceremony_share"] == 0.0


def test_pre_dispatch_ceremony_warning_is_lite_and_blocker_in_strict(monkeypatch) -> None:
    monkeypatch.setattr(
        "devolaflow.lifecycle.assert_layer_budget.estimate_tokens",
        lambda text: 100,
    )
    payload = {
        "task_id": "T2",
        "layer": "L2",
    }
    accounting = {"skill_tokens": 2_001, "rule_tokens": 2_000, "report_tokens": None}

    lite = assert_layer_token_budget(
        payload,
        context_tokens={**accounting, "report_tokens": 1_000},
    )
    assert lite.passed is False
    assert lite.violations[0].code == "ALB002"
    assert lite.violations[0].severity == "blocker"
    assert lite.violations[0].context["ceremony_tokens"] == 5_001

    with pytest.raises(HookViolation) as excinfo:
        assert_layer_token_budget(
            payload,
            strict=True,
            context_tokens={**accounting, "report_tokens": 1_000},
        )
    assert excinfo.value.code == "ALB002"


def test_pre_dispatch_can_measure_explicit_text_without_agents_corpus() -> None:
    result = assert_layer_token_budget(
        {"task_id": "T2", "layer": "L1"},
        skill_text="skill",
        rule_text="rules",
        report_envelope={"state": "completed"},
    )

    assert result.metadata["ceremony_tokens"] is not None
    assert result.metadata["ceremony_source"] == "context_tokens"
    assert not any(v.code == "ALB002" for v in result.violations)


def test_breaker_exposes_ceremony_warn_and_break_paths() -> None:
    breaker = TokenBudgetBreaker(profile=STANDARD, max_tokens=100)

    assert breaker.check_ceremony_share(50).action.value == "CONTINUE"
    assert breaker.check_ceremony_share(51).action.value == "WARN"
    assert breaker.check_ceremony_share(100).action.value == "BREAK"
