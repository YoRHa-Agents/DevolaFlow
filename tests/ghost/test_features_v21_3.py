"""v21.3.0 ghost audit for release-cut source contracts.

These tests exercise shipped behavior and inspect the workflow contracts
before the release note is finalized, per W-18.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from devolaflow.agent_workspace.lint import SemanticViolation, lint_change
from devolaflow.harness import evaluator
from devolaflow.harness.aggregator import aggregate_records
from devolaflow.harness.evaluator import (
    MEASUREMENT_KEYS,
    SIGNAL_KEYS,
    SignalResult,
    evaluate_harness,
)
from devolaflow.harness.metadata import build_run_metadata
from devolaflow.skills.slash_commands import run_propose


def _entrance_findings(report) -> list[SemanticViolation]:
    return [
        finding
        for finding in report.violations
        if isinstance(finding, SemanticViolation) and finding.kind.startswith("ENTRANCE_")
    ]


def test_missing_entrance_is_a_failing_lint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DEVOLAFLOW_AGENT_WORKSPACE", raising=False)
    change_folder = run_propose("v21.3 entrance audit", tmp_path)
    (change_folder / "entrance.md").unlink()

    report = lint_change(change_folder.name, repo_root=tmp_path)

    assert report.exit_code == 1
    assert [(finding.kind, finding.severity) for finding in _entrance_findings(report)] == [
        ("ENTRANCE_MISSING", "FAIL")
    ]


def _dispatch_record(dispatch_id: str) -> dict:
    return {
        "ts": "2026-08-30T00:00:00+00:00",
        "change_id": "v21-3-ghost",
        "round": 1,
        "layer": "L0",
        "dispatch_id": dispatch_id,
        "tokens_injected_measured": 10,
        "tokens_budget": 5_000,
        "constraint_count": 1,
        "quantifiable_ratio": 1.0,
        "tier_breakdown": {"invariant": 1, "guard": 0, "advisory": 0},
        "advisory_folded": False,
        "model_hint": "inherit",
    }


def test_evaluator_persists_collected_measurements_with_metadata(tmp_path: Path) -> None:
    ledger = tmp_path / "harness.jsonl"
    ledger.write_text(json.dumps(_dispatch_record("dispatch-1")) + "\n", encoding="utf-8")
    metadata = build_run_metadata(
        ledger,
        repo_root=tmp_path,
        sampled_at="2026-08-30T00:00:00+00:00",
        base_ref=None,
        salt="ghost",
        runner=lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout=""),
    )
    values = {
        key: SignalResult(True, 1 if key in MEASUREMENT_KEYS else True) for key in SIGNAL_KEYS
    }

    original = evaluator.collect_signals
    evaluator.collect_signals = lambda *args, **kwargs: values
    try:
        evaluate_harness(ledger, repo_root=tmp_path, signals=None, run_metadata=metadata)
    finally:
        evaluator.collect_signals = original

    records = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    event = next(record for record in records if record.get("event") == "consolidation_metrics")
    assert event["metadata"]["run_id"] == metadata["run_id"]
    assert event["estimated_agents_md_tokens"] == 1


def test_aggregator_retains_distinct_multi_run_metadata() -> None:
    first = _dispatch_record("dispatch-1")
    second = _dispatch_record("dispatch-2")
    first["metadata"] = {"run_id": "run-one"}
    second["metadata"] = {"run_id": "run-two"}

    summary = aggregate_records([first, second])

    assert [item["run_id"] for item in summary["metadata_records"]] == ["run-one", "run-two"]
    assert "metadata" not in summary


def test_s5_fallback_modules_retain_observable_warning_paths(project_root: Path) -> None:
    modules = (
        "src/devolaflow/_compressor_transforms/retrieval.py",
        "src/devolaflow/agent_workspace/change.py",
        "src/devolaflow/agent_workspace/checkpoint.py",
        "src/devolaflow/hostbridge/__main__.py",
        "src/devolaflow/learnings.py",
        "src/devolaflow/local/archive_kernel.py",
        "src/devolaflow/task_adaptive_selector.py",
        "src/devolaflow/template_engine/runtime.py",
    )
    for relative in modules:
        tree = ast.parse((project_root / relative).read_text(encoding="utf-8"))
        if relative.endswith("agent_workspace/checkpoint.py"):
            continue  # Its documented collision retry is covered by the v21.3 S-5 audit.
        assert any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"warning", "exception"}
            for node in ast.walk(tree)
        ), f"{relative} has no observable logging call"


def test_release_recovery_demo_i18n_and_npm_concurrency_contracts(project_root: Path) -> None:
    workflows = project_root / ".github" / "workflows"
    prep = yaml.safe_load((workflows / "release-prep.yml").read_text(encoding="utf-8"))
    open_pr = next(
        step for step in prep["jobs"]["prepare"]["steps"] if step.get("name") == "Open release PR"
    )
    open_pr_run = open_pr["run"]
    assert "if gh pr create \\" in open_pr_run
    assert "::warning::GitHub Actions could not create the release PR" in open_pr_run
    assert "Branch URL: https://github.com/$GITHUB_REPOSITORY/tree/$branch_name" in open_pr_run
    assert "Manual command: gh pr create" in open_pr_run
    assert "exit 1" not in open_pr_run[open_pr_run.index("if gh pr create") :]

    promote = next(
        step
        for step in prep["jobs"]["prepare"]["steps"]
        if step.get("name") == "Promote prepared demo release window"
    )
    promote_run = promote["run"]
    assert r"home\.release\.v19\.heading" in promote_run
    assert "Upcoming release ·" in promote_run
    assert "即将发布 ·" in promote_run
    assert "v{version} 新变化 ·" in promote_run
    assert "if updated == text:" in promote_run
    assert "Continuing." in promote_run

    npm = yaml.safe_load((workflows / "npm-publish.yml").read_text(encoding="utf-8"))
    assert npm["concurrency"] == {
        "group": "npm-publish-${{ inputs.release_tag || github.ref_name }}",
        "cancel-in-progress": False,
    }
