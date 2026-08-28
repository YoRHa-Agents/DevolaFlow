"""Focused Loop v3 state-safety regression tests."""

from __future__ import annotations

import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from devolaflow.agent_workspace.handoff import (
    EnvelopeImmutableError,
    HandoffStore,
    make_envelope,
)
from devolaflow.compression_pipeline import CompressionPipeline, CompressionStageError
from devolaflow.feedback import _filter_valid_proposals
from devolaflow.harness.evaluator import collect_signals, evaluate_harness
from devolaflow.lifecycle.dispatcher import (
    HookResult,
    HookViolation,
    clear_hooks,
    register_hook,
    run_hooks,
)


def _dispatch_envelope(seq: int, task_id: str):
    return make_envelope(
        seq=seq,
        from_layer="L0",
        to_layer="L2",
        change_id="loop3-race",
        envelope_kind="TaskDispatch",
        payload={
            "task_id": task_id,
            "type": "implement",
            "acceptance_criteria_ref": ".local/.agent/active/loop3-race/acceptance.md",
            "owned_files_ref": ".local/.agent/active/loop3-race/owned_files.txt",
        },
        created="2026-08-28T10:00:00Z",
    )


def _write_ledger(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "ts": "2026-08-28T00:00:00+00:00",
                "change_id": "loop3-evaluator",
                "round": 1,
                "layer": "L0",
                "dispatch_id": "dispatch-1",
                "tokens_injected_measured": 100,
                "tokens_budget": 1_000,
                "constraint_count": 10,
                "quantifiable_ratio": 0.8,
                "tier_breakdown": {"invariant": 4, "guard": 4, "advisory": 2},
                "advisory_folded": False,
                "model_hint": "quality",
            }
        )
        + "\n",
        encoding="utf-8",
    )


def test_handoff_same_sequence_race_has_one_winner_and_valid_bytes(tmp_path: Path) -> None:
    store = HandoffStore(repo_root=tmp_path)
    envelopes = (
        _dispatch_envelope(1, "winner-a"),
        _dispatch_envelope(1, "winner-b"),
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(store.write_envelope, envelope) for envelope in envelopes]
        successes = []
        collisions = []
        for future in futures:
            try:
                successes.append(future.result())
            except EnvelopeImmutableError as exc:
                collisions.append(exc)

    assert len(successes) == 1
    assert len(collisions) == 1
    assert [envelope.seq for envelope in store.read_envelopes("loop3-race")] == [1]


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        ("src/devolaflow/valid.py", True),
        ("workflow-system/agent/SKILL.md", True),
        ("schemas/valid.yaml", True),
        (".cursor/rules/valid.mdc", True),
        ("../src/devolaflow/escaped.py", False),
        ("src/devolaflow/../escaped.py", False),
        ("outside-repo/src/devolaflow/escaped.py", False),
    ],
)
def test_proposal_paths_require_canonical_repository_containment(
    tmp_path: Path,
    target: str,
    expected: bool,
) -> None:
    proposals = [{"target_file": target}]
    if expected:
        assert _filter_valid_proposals(proposals, repo_root=tmp_path) == proposals
    else:
        assert _filter_valid_proposals(proposals, repo_root=tmp_path) == []

    absolute = str(tmp_path / "src" / "devolaflow" / "absolute.py")
    assert _filter_valid_proposals([{"target_file": absolute}], repo_root=tmp_path) == []


def test_failed_w17_probe_is_unavailable_and_keeps_evaluation_insufficient(
    tmp_path: Path,
) -> None:
    def runner(
        argv: list[str],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        del kwargs
        if argv[0] == "git":
            return subprocess.CompletedProcess(
                argv,
                128,
                stdout="",
                stderr="fatal: bad revision 'missing-ref'",
            )
        stdout = "TOTAL 10 10 100%\n" if argv[0] == "ruff" or "pytest" in argv else ""
        return subprocess.CompletedProcess(argv, 0, stdout=stdout, stderr="")

    collected = collect_signals(tmp_path, base_ref="missing-ref", runner=runner)
    assert collected["w17_new_tests"].available is False
    assert "bad revision" in collected["w17_new_tests"].error
    assert collected["w17_new_tests"].value is None

    ledger = tmp_path / "harness.jsonl"
    _write_ledger(ledger)
    result = evaluate_harness(
        ledger,
        repo_root=tmp_path,
        base_ref="missing-ref",
        runner=runner,
    )
    assert result["verdict"] == "INSUFFICIENT"


def test_compression_protocol_requires_bypass_and_preserves_failure_modes() -> None:
    class MissingBypass:
        name = "missing-bypass"

        def transform(self, payload, _context):
            return payload

    with pytest.raises(TypeError, match="should_bypass"):
        CompressionPipeline(stages=(MissingBypass(),))

    class RaisingBypass:
        name = "raising-bypass"

        def should_bypass(self, _payload, _context):
            raise RuntimeError("bypass failure")

        def transform(self, payload, _context):
            return payload

    pipeline = CompressionPipeline(stages=(RaisingBypass(),))
    with pytest.raises(CompressionStageError, match="raising-bypass"):
        pipeline.run("payload")
    result = pipeline.run("payload", strict=False)
    assert result.payload == "payload"
    assert result.failed_stages == ("raising-bypass",)
    assert result.stage_results[0].error == "RuntimeError"


def test_run_hooks_isolates_handler_errors_without_mutating_payload(
    caplog: pytest.LogCaptureFixture,
) -> None:
    event = "loop3_state_safety"
    payload = {"nested": {"bytes": b"original"}}

    def broken_handler(received, *, strict: bool = False) -> HookResult:
        del strict
        received["nested"]["bytes"] = b"mutated"
        raise RuntimeError("handler broke")

    register_hook(event, broken_handler)
    try:
        with caplog.at_level("WARNING"):
            result = run_hooks(event, payload)
        assert result.passed is False
        assert result.metadata["handler_errors"][0]["exception"] == "RuntimeError"
        assert result.violations[0].code == "LIFECYCLE_HANDLER_EXCEPTION"
        assert payload == {"nested": {"bytes": b"original"}}
        assert any("isolating handler failure" in record.message for record in caplog.records)

        with pytest.raises(HookViolation, match="handler broke"):
            run_hooks(event, payload, strict=True)
        assert payload == {"nested": {"bytes": b"original"}}
    finally:
        clear_hooks(event)
