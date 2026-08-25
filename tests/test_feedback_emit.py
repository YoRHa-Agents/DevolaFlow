"""Unit tests for the v10.6.0 PV-02 ``ProposalEmitter`` extraction.

Complements the integration regression suite in
``tests/test_dispatch_emission_runs_hooks.py`` (the release-blocker
S-10 contract) by exercising :class:`devolaflow.feedback_emit.ProposalEmitter`
in isolation. The integration tests pin the chain via
:meth:`devolaflow.feedback.ProposalGenerator.generate_round_dispatch`
(the public façade); these unit tests pin the same behaviour against
the extracted emitter directly so a future refactor of the façade
cannot accidentally weaken the contract.

The 8 unit tests cover the surface called out in PDS
``.local/research/v11.0.0_patches/D-Q-2.md`` §7 effort_estimate:

(a) ``emit`` round-1 pass-through (no reinforcement_factory call)
(b) ``emit`` round ≥ 2 with empty findings (factory returns ``None``)
(c) ``emit`` round ≥ 2 with findings (reinforcement merged into dispatch)
(d) ``_fire_hook_chain`` invokes the 4 events in the canonical order
(e) ``_fire_hook_chain`` per-event try/except isolation (one bad
    handler does NOT short-circuit the others)
(f) ``_fire_hook_chain`` lazy-import fallback when the lifecycle module
    is unavailable (no crash; warning logged)
(g) ``strict=False`` invariant on every hook invocation
(h) deep-copy contract (the input ``base_dispatch`` is never mutated)

Source: v10.6.0 PV-02 — codified per D-Q-2 §2 patch_design + §7 effort.
"""

from __future__ import annotations

import builtins
import copy
from typing import Any
from unittest.mock import patch

import pytest

from devolaflow.feedback import ProposalGenerator
from devolaflow.feedback_emit import ProposalEmitter
from devolaflow.gate.models import Finding, GateVerdict
from devolaflow.gate.reinforcement import ReinforcementBlock, ReinforcementRule
from devolaflow.lifecycle import (
    POST_DISPATCH_EVENT,
    PRE_DISPATCH_EVENT,
    PRE_HANDOFF_EVENT,
    PRE_PLUGIN_INVOCATION_EVENT,
    HookResult,
    clear_hooks,
)


@pytest.fixture(autouse=True)
def _clear_extra_hooks():
    """Match the canonical fixture from ``test_dispatch_emission_runs_hooks.py``.

    Ensures each unit test starts/ends with NO extra hook handlers
    registered. The lifecycle module installs canonical defaults at
    import time (``validate_dispatch`` for ``pre_dispatch``, etc.);
    this fixture only clears extras THIS test added.
    """
    yield
    clear_hooks()


def _base_dispatch() -> dict[str, Any]:
    """Minimal dispatch shape compatible with the ``validate_dispatch`` hook."""
    return {
        "task_id": "T-DQ2",
        "task_type": "refactor",
        "accept": ["the dispatch payload runs through the hook chain"],
        "context": {
            "applicable_rules": {"loading_strategy": "standard"},
            "target_files": ["src/foo.py"],
        },
    }


def _verdict_with_findings(findings: list, score: float = 65.0) -> GateVerdict:
    return GateVerdict(
        decision="FAIL",
        rationale="test",
        composite_score=score,
        details={"findings": findings},
    )


def _blocker_finding() -> Finding:
    return Finding(
        finding_id="F-DQ2-1",
        severity="blocker",
        category="security",
        location="src/foo.py",
        description="extracted-emitter unit-test fixture",
        suggestion="run lifecycle.run_hooks on every emitter path",
    )


def _make_call_recorder() -> tuple[list[tuple], Any]:
    """Build a fake ``run_hooks`` that records (event, payload, strict)."""
    calls: list[tuple] = []

    def fake_run_hooks(event, payload, *, strict=False):
        calls.append((event, copy.deepcopy(payload), strict))
        return HookResult(event=event, passed=True)

    return calls, fake_run_hooks


# ---------------------------------------------------------------------------
# Test (a): round-1 pass-through doesn't invoke the reinforcement factory
# ---------------------------------------------------------------------------


def test_emit_round1_passthrough_skips_reinforcement_factory() -> None:
    """``emit`` with ``round_num=1`` MUST NOT call the reinforcement factory.

    Round 1 is a pure pass-through — there is no prior round to learn
    from, so the verdict (even when supplied) is ignored and the
    factory is never invoked. Pins the v6-01 wiring contract.
    """
    emitter = ProposalEmitter()
    factory_calls: list[tuple] = []

    def factory(verdict, **kwargs):
        factory_calls.append((verdict, kwargs))
        return None

    calls, fake = _make_call_recorder()
    with patch("devolaflow.lifecycle.run_hooks", side_effect=fake):
        result = emitter.emit(
            base_dispatch=_base_dispatch(),
            verdict=_verdict_with_findings([_blocker_finding()]),
            round_num=1,
            reinforcement_factory=factory,
        )

    assert factory_calls == [], (
        "round-1 pass-through must skip the reinforcement factory entirely "
        f"(factory was called {len(factory_calls)} times)"
    )
    assert result["task_id"] == "T-DQ2"
    events = [c[0] for c in calls]
    assert events == [
        PRE_DISPATCH_EVENT,
        POST_DISPATCH_EVENT,
        PRE_HANDOFF_EVENT,
        PRE_PLUGIN_INVOCATION_EVENT,
    ], "round-1 still fires the full S-10 hook chain"


# ---------------------------------------------------------------------------
# Test (b): factory returns None → emit pass-through (no merge)
# ---------------------------------------------------------------------------


def test_emit_no_findings_path_skips_merge_but_fires_chain() -> None:
    """``emit`` round ≥ 2 with factory returning ``None`` must NOT merge.

    Pins the contract: the emitter delegates verdict-to-block
    conversion to the factory; when the factory yields ``None``
    (no actionable findings), the dispatch pass-through path runs.
    The hook chain still fires (S-10 invariant).
    """
    emitter = ProposalEmitter()
    factory_calls: list[tuple] = []

    def factory(verdict, **kwargs) -> ReinforcementBlock | None:
        factory_calls.append((verdict, kwargs))
        return None

    base = _base_dispatch()
    control = copy.deepcopy(base)
    calls, fake = _make_call_recorder()
    with patch("devolaflow.lifecycle.run_hooks", side_effect=fake):
        result = emitter.emit(
            base_dispatch=base,
            verdict=_verdict_with_findings([]),
            round_num=2,
            reinforcement_factory=factory,
        )

    assert len(factory_calls) == 1, (
        "factory must be called exactly once on round ≥ 2 even when it returns None"
    )
    assert result == control, "no-findings path must return byte-identical deep copy"
    events = [c[0] for c in calls]
    assert events == [
        PRE_DISPATCH_EVENT,
        POST_DISPATCH_EVENT,
        PRE_HANDOFF_EVENT,
        PRE_PLUGIN_INVOCATION_EVENT,
    ], "no-findings path still fires the full S-10 hook chain"


# ---------------------------------------------------------------------------
# Test (c): factory returns block → merge into dispatch + hook chain
# ---------------------------------------------------------------------------


def test_emit_reinforcement_applied_merges_block_and_fires_chain() -> None:
    """``emit`` round ≥ 2 with factory returning a block MUST merge.

    Pins the contract: the emitter passes the merged dispatch (NOT
    the deep-copy alone) to the hook chain. The merged dispatch
    carries the reinforcement block under
    ``context.applicable_rules.reinforcement`` per the v6-01 contract.
    """
    emitter = ProposalEmitter()
    # Use the real ProposalGenerator factory to get a realistic block;
    # this complements the per-emitter unit isolation by exercising the
    # façade path in a single test.
    parent = ProposalGenerator()

    base = _base_dispatch()
    verdict = _verdict_with_findings([_blocker_finding()])
    calls, fake = _make_call_recorder()
    with patch("devolaflow.lifecycle.run_hooks", side_effect=fake):
        result = emitter.emit(
            base_dispatch=base,
            verdict=verdict,
            round_num=2,
            reinforcement_factory=parent.generate_reinforcement,
        )

    # Reinforcement block was merged into the result.
    applicable_rules = result.get("context", {}).get("applicable_rules", {})
    assert "reinforcement" in applicable_rules, (
        "reinforcement block MUST be merged into context.applicable_rules.reinforcement "
        f"(got applicable_rules={applicable_rules!r})"
    )
    events = [c[0] for c in calls]
    assert events == [
        PRE_DISPATCH_EVENT,
        POST_DISPATCH_EVENT,
        PRE_HANDOFF_EVENT,
        PRE_PLUGIN_INVOCATION_EVENT,
    ], "reinforcement-applied path still fires the full S-10 hook chain"


def test_emit_accepts_supplemental_reinforcement_without_gate_findings() -> None:
    """Supplemental blockers are emitted even when the legacy gate path is idle."""
    emitter = ProposalEmitter()
    supplemental = ReinforcementBlock(
        round=1,
        prior_score=0.0,
        target_score=0.0,
        severity_floor="blocker",
        rules=(
            ReinforcementRule(
                id="R-C-G1.1-001",
                severity="blocker",
                mandate="verbatim user revert reason",
            ),
        ),
        escalation_note="selected revert",
    )

    with patch("devolaflow.lifecycle.run_hooks", return_value=None):
        result = emitter.emit(
            base_dispatch=_base_dispatch(),
            verdict=None,
            round_num=1,
            reinforcement_factory=lambda *_args, **_kwargs: None,
            supplemental_reinforcement=supplemental,
        )

    reinforcement = result["context"]["applicable_rules"]["reinforcement"]
    assert reinforcement["rules"] == [
        {
            "id": "R-C-G1.1-001",
            "severity": "blocker",
            "mandate": "verbatim user revert reason",
            "tier": "guard",
        }
    ]


# ---------------------------------------------------------------------------
# Test (d): _fire_hook_chain invokes the 4 events in canonical order
# ---------------------------------------------------------------------------


def test_fire_hook_chain_invokes_four_events_in_canonical_order() -> None:
    """Direct unit test on ``_fire_hook_chain`` chain order.

    The integration test in ``test_dispatch_emission_runs_hooks.py``
    pins this via the public façade; this test pins it on the
    extracted helper directly so the chain order can't drift even
    if the façade is rewritten.
    """
    emitter = ProposalEmitter()
    calls, fake = _make_call_recorder()
    with patch("devolaflow.lifecycle.run_hooks", side_effect=fake):
        result = emitter._fire_hook_chain(_base_dispatch())

    events = [c[0] for c in calls]
    assert events == [
        PRE_DISPATCH_EVENT,
        POST_DISPATCH_EVENT,
        PRE_HANDOFF_EVENT,
        PRE_PLUGIN_INVOCATION_EVENT,
    ], "_fire_hook_chain must invoke the canonical 4-event order"
    assert result["task_id"] == "T-DQ2", "_fire_hook_chain returns the dispatch unchanged"


# ---------------------------------------------------------------------------
# Test (e): per-event try/except isolation — one bad hook doesn't break others
# ---------------------------------------------------------------------------


def test_fire_hook_chain_per_event_isolation_runs_remaining_hooks(caplog) -> None:
    """A buggy handler on event #2 MUST NOT short-circuit events #3 and #4.

    Pins the per-event try/except scope per the original ``_emit_dispatch``
    docstring "the hook chain is collectively a contract; per-event
    independence is intentional".
    """
    emitter = ProposalEmitter()
    calls: list[tuple] = []

    def selectively_bad_run_hooks(event, payload, *, strict=False):
        calls.append((event, strict))
        if event == POST_DISPATCH_EVENT:
            raise RuntimeError(f"{event} handler exploded")
        return HookResult(event=event, passed=True)

    with (
        patch("devolaflow.lifecycle.run_hooks", side_effect=selectively_bad_run_hooks),
        caplog.at_level("WARNING", logger="devolaflow.feedback_emit"),
    ):
        result = emitter._fire_hook_chain(_base_dispatch())

    events_invoked = [c[0] for c in calls]
    # All 4 events were ATTEMPTED — the failed event #2 didn't abort the others.
    assert events_invoked == [
        PRE_DISPATCH_EVENT,
        POST_DISPATCH_EVENT,
        PRE_HANDOFF_EVENT,
        PRE_PLUGIN_INVOCATION_EVENT,
    ], (
        "per-event try/except scope must allow events 3+4 to run after event 2 raised "
        f"(actual chain={events_invoked!r})"
    )
    assert result["task_id"] == "T-DQ2", "dispatch returned unchanged"
    # The S-5 warning was logged for the failed event.
    warnings = [rec for rec in caplog.records if rec.levelname == "WARNING"]
    assert any("hook raised" in rec.message for rec in warnings), (
        f"S-5 violation: handler raise must be logged at WARNING level via logger.warning "
        f"(WARNING records: {[r.message for r in warnings]!r})"
    )


# ---------------------------------------------------------------------------
# Test (f): lazy-import fallback when lifecycle is unavailable
# ---------------------------------------------------------------------------


def test_fire_hook_chain_lazy_import_fallback_when_lifecycle_missing(caplog) -> None:
    """When ``from devolaflow import lifecycle`` raises, the helper logs + returns.

    Pins the defensive ImportError fallback that protects round-N+1
    dispatch from a bad lifecycle install. The dispatch is returned
    unchanged; no exception propagates.

    Implementation note: patching ``builtins.__import__`` is the
    canonical way to simulate an ImportError on a ``from X import Y``
    statement. ``sys.modules`` poisoning is unreliable here because
    the parent ``devolaflow`` package already carries ``lifecycle``
    as an attribute from the test-module's own imports — the
    ``from`` statement would resolve via attribute lookup and bypass
    the sentinel.
    """
    emitter = ProposalEmitter()
    base = _base_dispatch()

    real_import = builtins.__import__

    def fake_import(
        name: str,
        globals_arg: Any = None,
        locals_arg: Any = None,
        fromlist: tuple = (),
        level: int = 0,
    ):
        if name == "devolaflow" and fromlist and "lifecycle" in fromlist:
            raise ImportError("simulated missing lifecycle module for v10.6.0 PV-02 unit test")
        return real_import(name, globals_arg, locals_arg, fromlist, level)

    with (
        patch("builtins.__import__", side_effect=fake_import),
        caplog.at_level("WARNING", logger="devolaflow.feedback_emit"),
    ):
        result = emitter._fire_hook_chain(base)

    assert result["task_id"] == "T-DQ2", (
        "dispatch must be returned unchanged when lifecycle is unavailable"
    )
    warnings = [rec for rec in caplog.records if rec.levelname == "WARNING"]
    assert any("lifecycle module unavailable" in rec.message for rec in warnings), (
        f"defensive ImportError fallback must log a WARNING citing the missing module "
        f"(WARNING records: {[r.message for r in warnings]!r})"
    )


# ---------------------------------------------------------------------------
# Test (g): per-event strictness — pre_dispatch strict, the rest permissive
# ---------------------------------------------------------------------------


def test_fire_hook_chain_uses_permissive_mode_on_every_event() -> None:
    """pre_dispatch fires strict; the 3 side-effect events stay permissive.

    # v15.0.0 strict graduation (G-038): the default
    # ``ProposalEmitter()`` runs ``pre_dispatch`` with ``strict=True``
    # (content violations BLOCK the dispatch); ``post_dispatch`` /
    # ``pre_handoff`` / ``pre_plugin_invocation`` keep the v8.4.0 retro
    # §4.1 #4 permissive contract. The documented escape —
    # ``ProposalEmitter(pre_dispatch_strict=False)`` — restores the
    # all-permissive chain and is pinned in the second half below.
    """
    emitter = ProposalEmitter()
    calls, fake = _make_call_recorder()
    with patch("devolaflow.lifecycle.run_hooks", side_effect=fake):
        emitter._fire_hook_chain(_base_dispatch())

    for event, _payload, strict in calls:
        expected = event == PRE_DISPATCH_EVENT
        assert strict is expected, (
            f"event {event!r} was invoked with strict={strict!r} — "
            f"expected strict={expected!r} (v15.0.0 pre_dispatch strict default)"
        )

    # Permissive escape: every event back to strict=False.
    emitter_permissive = ProposalEmitter(pre_dispatch_strict=False)
    calls_p, fake_p = _make_call_recorder()
    with patch("devolaflow.lifecycle.run_hooks", side_effect=fake_p):
        emitter_permissive._fire_hook_chain(_base_dispatch())
    assert all(strict is False for _, _, strict in calls_p), (
        "ProposalEmitter(pre_dispatch_strict=False) must restore the "
        "pre-v15.0.0 all-permissive chain"
    )


# ---------------------------------------------------------------------------
# Test (h): emit never mutates the input base_dispatch (deep-copy contract)
# ---------------------------------------------------------------------------


def test_emit_does_not_mutate_input_base_dispatch() -> None:
    """``emit`` returns a fresh deep copy; the input is byte-identical.

    Pins the v8.4.0 retro §4.1 #4 R5 strict invariant — the input
    ``base_dispatch`` is NEVER mutated, even on the
    reinforcement-applied path (which merges a block into the
    deep-copy, NOT into the original).
    """
    emitter = ProposalEmitter()
    parent = ProposalGenerator()

    base = _base_dispatch()
    snapshot = copy.deepcopy(base)

    # Round 1 path
    with patch("devolaflow.lifecycle.run_hooks", return_value=None):
        emitter.emit(
            base_dispatch=base,
            verdict=_verdict_with_findings([_blocker_finding()]),
            round_num=1,
            reinforcement_factory=parent.generate_reinforcement,
        )
    assert base == snapshot, (
        "round-1 emit() must NOT mutate base_dispatch (R5 strict byte-identical)"
    )

    # Reinforcement-applied path
    with patch("devolaflow.lifecycle.run_hooks", return_value=None):
        emitter.emit(
            base_dispatch=base,
            verdict=_verdict_with_findings([_blocker_finding()]),
            round_num=2,
            reinforcement_factory=parent.generate_reinforcement,
        )
    assert base == snapshot, (
        "reinforcement-applied emit() must NOT mutate base_dispatch — "
        "the merge runs against the deep-copy, not the input"
    )
