"""Current-cycle ghost audit for v20.0.0 functional-test-system contracts."""

from __future__ import annotations

import inspect
import json
import subprocess
import sys
from pathlib import Path

import pytest


def test_v20_functional_matrix_system_is_live(project_root: Path) -> None:
    """The Loop v3 matrix SSOT, runner, hard gate, and release wiring exist."""
    matrix_path = project_root / "tests" / "functional" / "matrix.yaml"
    gate_script = project_root / "scripts" / "check_functional_matrix.py"
    assert matrix_path.is_file()
    assert gate_script.is_file()

    from scripts.check_functional_matrix import check_functional_matrix
    from tests.functional.runner import (
        ADAPTERS,
        MAINTAINED_MODULE_ENTRYPOINTS,
        OutcomeStatus,
        load_console_script_inventory,
        load_matrix,
    )

    diagnostics = check_functional_matrix(matrix_path, project_root)
    assert diagnostics == (), [str(item) for item in diagnostics]

    document = load_matrix(matrix_path, project_root)
    assert len(document.rows) >= 40
    assert {row.call for row in document.rows} <= set(ADAPTERS)
    console_rows = {row.entrypoint for row in document.rows if row.surface == "console_script"}
    assert console_rows == set(load_console_script_inventory(project_root))
    module_rows = {row.entrypoint for row in document.rows if row.surface == "python_module"}
    assert module_rows == set(MAINTAINED_MODULE_ENTRYPOINTS)
    assert {status.value for status in OutcomeStatus} == {
        "PASS",
        "FAIL",
        "SKIP_OPTIONAL",
        "INSUFFICIENT",
    }

    makefile = (project_root / "Makefile").read_text(encoding="utf-8")
    assert "check-functional-matrix:" in makefile
    release_preflight = next(
        line for line in makefile.splitlines() if line.startswith("release-preflight:")
    )
    assert "check-functional-matrix" in release_preflight
    assert "test-functional:" in makefile


def test_v20_behavioral_safety_contracts_are_live(project_root: Path, tmp_path: Path) -> None:
    """The adjudicated B4 closures remain wired to their public surfaces."""
    from devolaflow.agent_workspace.handoff import EnvelopeImmutableError, HandoffStore
    from devolaflow.compression_pipeline import CompressionPipeline
    from devolaflow.dispatch import async_dispatch_wave_tasks, dispatch_wave_tasks
    from devolaflow.feedback import _filter_valid_proposals
    from devolaflow.gate.models import CheckResult, GateInput
    from devolaflow.gate.profiles import STANDARD
    from devolaflow.gate.scorer import evaluate_gate
    from devolaflow.lifecycle.dispatcher import run_hooks
    from devolaflow.local.archive import ArchiveApproval, apply_archive_plan
    from devolaflow.plugins.installer import (
        available_plugin_profiles,
        select_plugin_profile,
    )

    # B4-GATE-001 — a skipped required check cannot become a standard PASS.
    verdict = evaluate_gate(
        GateInput(
            build_status=CheckResult(status="skip"),
            test_results=CheckResult(status="pass"),
            lint_status=CheckResult(status="pass"),
            acceptance_criteria_results=CheckResult(status="pass"),
        ),
        STANDARD,
    )
    assert verdict.decision == "FAIL"

    # B4-DISP-001/003 — explicit zero is rejected; the async companion exists.
    from devolaflow.agent_workspace.dispatch_executor import ExecutorError

    with pytest.raises(ExecutorError):
        dispatch_wave_tasks(
            {
                "tasks": [{"task_id": "one"}, {"task_id": "two"}],
                "sync_barrier": {"mode": "parallel", "max_parallelism": 0},
            },
            lambda task: lambda: task["task_id"],
        )
    assert inspect.iscoroutinefunction(async_dispatch_wave_tasks)

    # B4-HANDOFF-001 — exclusive-create semantics are public API.
    assert issubclass(EnvelopeImmutableError, Exception)
    assert callable(HandoffStore.write_envelope)

    # B4-FB-001 — traversal and absolute proposal targets are rejected.
    accepted = _filter_valid_proposals(
        [
            {"target_file": "src/devolaflow/dispatch.py"},
            {"target_file": "../outside.py"},
            {"target_file": str(project_root / "src" / "devolaflow" / "abs.py")},
        ],
        repo_root=project_root,
    )
    assert accepted == [{"target_file": "src/devolaflow/dispatch.py"}]

    # B4-COMP-001 — third-party stages must implement should_bypass.
    class _NoBypass:
        name = "no-bypass"

        def transform(self, payload: str, _context: dict) -> str:
            return payload

    with pytest.raises(TypeError):
        CompressionPipeline(stages=(_NoBypass(),))

    # B4-LIFE-001 — permissive run_hooks isolates handler failures.
    assert "strict" in inspect.signature(run_hooks).parameters

    # B4-LA-001..003 — archive apply takes an explicit approval artifact.
    assert "approved" in inspect.signature(apply_archive_plan).parameters
    assert ArchiveApproval.__dataclass_fields__.keys() >= {
        "plan_fingerprint",
        "entries",
    }

    # O-13 — plugin SSOT keeps five suggest rows with optional profiles.
    registry_path = (
        project_root / "workflow-system" / "agent" / "knowledge" / "runtime-plugins.yaml"
    )
    profiles = available_plugin_profiles(registry_path=registry_path)
    assert profiles["all"] == ["ui-pro", "rtk", "si-chip", "codegraph", "impeccable"]
    assert select_plugin_profile("codegraph", registry_path=registry_path) == ["codegraph"]

    # Reporter --now pinned clock (deterministic artifact repair).
    help_run = subprocess.run(
        [sys.executable, "-m", "devolaflow.agent_workspace.reporter", "--help"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        cwd=tmp_path,
    )
    assert help_run.returncode == 0
    assert "--now" in help_run.stdout

    # S-3 settled coverage policy is compiled into the rule corpus.
    agents_md = (project_root / "AGENTS.md").read_text(encoding="utf-8")
    assert "at least 90%" in agents_md
    assert "75% test coverage" in agents_md

    # Functional telemetry artifact stays deterministic JSON evidence.
    results_path = project_root / ".local" / "telemetry" / "functional-test-results.json"
    if results_path.is_file():
        artifact = json.loads(results_path.read_text(encoding="utf-8"))
        assert artifact["mode"] == "offline"
        assert set(artifact["status_counts"]) == {
            "PASS",
            "FAIL",
            "SKIP_OPTIONAL",
            "INSUFFICIENT",
        }


def test_v20_entrance_router_always_written_with_planning_artifacts(tmp_path: Path) -> None:
    """entrance.md is backfilled by the canonical store write (design D-4 owner).

    ``Change.to_active_folder`` MUST materialise the onboarding router
    alongside goal/checklist/stage/preflight whenever the in-memory change
    lacks one, deriving Section 1 from the ``# Goal:`` heading; a loaded
    entrance still round-trips verbatim.
    """
    from devolaflow.agent_workspace import Change
    from devolaflow.agent_workspace.entrance import derive_goal_title, render_entrance_md

    # Title derivation: canonical heading wins; absent heading falls back.
    assert derive_goal_title("# Goal: Ship dark mode\n", "ship-dark-mode") == "Ship dark mode"
    assert derive_goal_title("", "ship-dark-mode") == "Complete ship-dark-mode"

    change = Change(
        change_id="entrance-backfill",
        goal_md="# Goal: Ship dark mode\n\n## Goals\n- G1: Ship dark mode\n",
        status={"state": "PROPOSED"},
    )
    target = tmp_path / "entrance-backfill"
    change.to_active_folder(target)
    written = (target / "entrance.md").read_text(encoding="utf-8")
    assert written == render_entrance_md("entrance-backfill", "Ship dark mode")

    # A populated entrance is never regenerated — verbatim round-trip.
    custom = written.replace("Ship dark mode —", "Custom router —")
    (target / "entrance.md").write_text(custom, encoding="utf-8")
    reloaded = Change.from_active_folder(target)
    rewritten = tmp_path / "entrance-rewrite"
    reloaded.to_active_folder(rewritten)
    assert (rewritten / "entrance.md").read_text(encoding="utf-8") == custom
