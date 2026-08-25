"""Regression test: feedback.py wires lifecycle hooks on every dispatch return path.

v8.4.4 PV-04 — Soul Rule S-10 enforcement.
v9.1.3 PV-03 — extends the chain to include ``pre_handoff`` (G-005 closure).
v9.4.0 PV-03 — extends the chain to include ``pre_plugin_invocation``
(D-P-2 closure: closes the ``ensure_plugin()`` dead-wire ghost).

Pins the dead-wire fix that closes C-03 from
``.local/research/v9.0.0_gap_analysis.md`` §3.1: prior to v8.4.4,
``src/devolaflow/feedback.py::ProposalGenerator.generate_round_dispatch``
constructed dispatch payloads but never invoked
``lifecycle.run_hooks("pre_dispatch", ...)`` even though
``src/devolaflow/lifecycle/__init__.py`` had registered ``pre_dispatch``
+ ``validate_dispatch`` + ``validate_owned_files`` for years. This test
asserts the wiring is now active and remains active across all 3 return
paths of ``generate_round_dispatch``:

1. Round 1 / no verdict — pure pass-through.
2. No reinforcement findings (verdict.details["findings"] empty).
3. Reinforcement applied (round ≥ 2 + non-empty findings).

All three paths MUST invoke the FOUR-event hook chain in this exact
order, exactly once each, in PERMISSIVE mode (``strict=False``):

  ``pre_dispatch`` → ``post_dispatch`` → ``pre_handoff`` → ``pre_plugin_invocation``

The v9.1.3 PV-03 ``pre_handoff`` slot lands AFTER the governance tail
because the dispatch payload is fully-formed + lint-validated at that
point. The v9.4.0 PV-03 ``pre_plugin_invocation`` slot lands AFTER
``pre_handoff`` because the dispatch payload's plugin candidates are
typically resolved against the ``runtime-plugins.yaml`` registry AFTER
the handoff envelope has been written (so the L3 receiver sees the
authoritative payload before the auto-install fires).

Tests also assert R5 strict byte-identical: when no extra handlers are
registered, the returned dispatch payload is byte-identical to the
pre-PV-04 control (golden snapshot built from pure deepcopy +
``merge_reinforcement_into_dispatch``). This protects callers that have
not yet adopted the v8.4.4 schema from any silent mutation through the
hook chain. The v9.1.3 PV-03 ``auto_write_handoff`` default is also
byte-stable when ``DEVOLAFLOW_AGENT_WORKSPACE`` is unset; the v9.4.0
PV-03 ``pre_plugin_invocation`` default is also byte-stable when
``DEVOLAFLOW_AUTO_INSTALL_PLUGINS`` is unset.
"""

from __future__ import annotations

import copy
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from devolaflow.feedback import ProposalGenerator
from devolaflow.gate.models import Finding, GateVerdict
from devolaflow.gate.reinforcement import merge_reinforcement_into_dispatch
from devolaflow.harness import record_dispatch_telemetry
from devolaflow.lifecycle import (
    POST_DISPATCH_EVENT,
    PRE_DISPATCH_EVENT,
    PRE_HANDOFF_EVENT,
    PRE_PLUGIN_INVOCATION_EVENT,
    HookResult,
    clear_hooks,
    list_handlers,
    register_hook,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_extra_hooks():
    """Ensure each test starts/ends with NO extra hook handlers registered.

    The lifecycle module installs canonical defaults at import time
    (``validate_dispatch`` for ``pre_dispatch``, ``post_dispatch`` no-op
    for ``post_dispatch``, etc.) and pins ``validate_owned_files`` as
    an extra on ``pre_dispatch``. We do NOT clear those — the test
    fixtures only clear extras THIS test added.
    """
    yield
    clear_hooks()


def _base_dispatch() -> dict:
    """Minimal dispatch shape that satisfies the existing ``validate_dispatch`` hook."""
    return {
        "task_id": "T-PV04",
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
        finding_id="F-PV04-1",
        severity="blocker",
        category="security",
        location="src/foo.py",
        description="dead-wire regression",
        suggestion="run lifecycle.run_hooks on every dispatch path",
    )


# ---------------------------------------------------------------------------
# Hook-invocation regression — the dead-wire fix
# ---------------------------------------------------------------------------


class TestHookInvocation:
    """Assert ``lifecycle.run_hooks`` fires on every dispatch return path."""

    def _make_call_recorder(self) -> tuple[list[tuple], callable]:
        calls: list[tuple] = []

        def fake_run_hooks(event, payload, *, strict=False):
            calls.append((event, copy.deepcopy(payload), strict))
            return HookResult(event=event, passed=True)

        return calls, fake_run_hooks

    def test_round1_passthrough_invokes_all_hooks(self) -> None:
        gen = ProposalGenerator()
        calls, fake = self._make_call_recorder()
        with patch("devolaflow.lifecycle.run_hooks", side_effect=fake):
            gen.generate_round_dispatch(
                _base_dispatch(),
                _verdict_with_findings([_blocker_finding()]),
                round_num=1,
            )
        events = [c[0] for c in calls]
        assert events == [
            PRE_DISPATCH_EVENT,
            POST_DISPATCH_EVENT,
            PRE_HANDOFF_EVENT,
            PRE_PLUGIN_INVOCATION_EVENT,
        ], (
            "round-1 pass-through must invoke pre_dispatch, post_dispatch, "
            "pre_handoff, then pre_plugin_invocation exactly once each "
            "(v9.4.0 PV-03 chain)"
        )

    def test_no_findings_path_invokes_all_hooks(self) -> None:
        gen = ProposalGenerator()
        calls, fake = self._make_call_recorder()
        with patch("devolaflow.lifecycle.run_hooks", side_effect=fake):
            gen.generate_round_dispatch(
                _base_dispatch(),
                _verdict_with_findings([]),
                round_num=2,
            )
        events = [c[0] for c in calls]
        assert events == [
            PRE_DISPATCH_EVENT,
            POST_DISPATCH_EVENT,
            PRE_HANDOFF_EVENT,
            PRE_PLUGIN_INVOCATION_EVENT,
        ], (
            "empty-findings path must still invoke the full hook chain "
            "(pre_dispatch → post_dispatch → pre_handoff → "
            "pre_plugin_invocation)"
        )

    def test_reinforcement_applied_path_invokes_all_hooks(self) -> None:
        gen = ProposalGenerator()
        calls, fake = self._make_call_recorder()
        with patch("devolaflow.lifecycle.run_hooks", side_effect=fake):
            gen.generate_round_dispatch(
                _base_dispatch(),
                _verdict_with_findings([_blocker_finding()]),
                round_num=2,
            )
        events = [c[0] for c in calls]
        assert events == [
            PRE_DISPATCH_EVENT,
            POST_DISPATCH_EVENT,
            PRE_HANDOFF_EVENT,
            PRE_PLUGIN_INVOCATION_EVENT,
        ], (
            "reinforcement-applied path must invoke the full hook chain "
            "(pre_dispatch → post_dispatch → pre_handoff → "
            "pre_plugin_invocation) exactly once"
        )

    def test_pre_handoff_invoked_after_post_dispatch(self) -> None:
        """v9.1.3 PV-03: ``pre_handoff`` MUST fire AFTER the governance tail.

        At this point the dispatch payload is fully-formed and
        lint-validated, making it the correct moment to consider
        materialising a handoff envelope. Pinning the order prevents a
        future refactor from re-ordering the chain and breaking the
        S-10 governance contract.
        """
        gen = ProposalGenerator()
        calls, fake = self._make_call_recorder()
        with patch("devolaflow.lifecycle.run_hooks", side_effect=fake):
            gen.generate_round_dispatch(
                _base_dispatch(),
                _verdict_with_findings([_blocker_finding()]),
                round_num=2,
            )
        events = [c[0] for c in calls]
        post_idx = events.index(POST_DISPATCH_EVENT)
        handoff_idx = events.index(PRE_HANDOFF_EVENT)
        assert handoff_idx == post_idx + 1, (
            f"pre_handoff (idx {handoff_idx}) must immediately follow "
            f"post_dispatch (idx {post_idx}); chain={events!r}"
        )

    def test_pre_plugin_invocation_invoked_after_pre_handoff(self) -> None:
        """v9.4.0 PV-03: ``pre_plugin_invocation`` MUST fire AFTER ``pre_handoff``.

        At this point the dispatch payload is fully-formed and the
        handoff envelope has been written (in workspace-engaged
        operation), making it the correct moment to auto-install
        plugins cited by the dispatch's workflow. Pinning the order
        prevents a future refactor from re-ordering the chain and
        breaking the v9.4.0 PV-03 dispatch-wiring contract.
        """
        gen = ProposalGenerator()
        calls, fake = self._make_call_recorder()
        with patch("devolaflow.lifecycle.run_hooks", side_effect=fake):
            gen.generate_round_dispatch(
                _base_dispatch(),
                _verdict_with_findings([_blocker_finding()]),
                round_num=2,
            )
        events = [c[0] for c in calls]
        handoff_idx = events.index(PRE_HANDOFF_EVENT)
        plugin_idx = events.index(PRE_PLUGIN_INVOCATION_EVENT)
        assert plugin_idx == handoff_idx + 1, (
            f"pre_plugin_invocation (idx {plugin_idx}) must immediately "
            f"follow pre_handoff (idx {handoff_idx}); chain={events!r}"
        )

    def test_hook_invoked_in_permissive_mode(self) -> None:
        """Per-event strictness: pre_dispatch strict, the rest permissive.

        # v15.0.0 strict graduation (G-038): the ``pre_dispatch`` event
        # now fires with ``strict=True`` by default (violations BLOCK
        # the dispatch); the remaining 3 chain events stay permissive
        # (they are side-effect adapters, not content validators). The
        # permissive escape is ``ProposalGenerator(pre_dispatch_strict=
        # False)`` — pinned by ``TestV15StrictGraduation`` below.
        """
        gen = ProposalGenerator()
        calls, fake = self._make_call_recorder()
        with patch("devolaflow.lifecycle.run_hooks", side_effect=fake):
            gen.generate_round_dispatch(
                _base_dispatch(),
                _verdict_with_findings([_blocker_finding()]),
                round_num=2,
            )
        for event, _payload, strict in calls:
            expected = event == PRE_DISPATCH_EVENT
            assert strict is expected, (
                f"event {event!r} was invoked with strict={strict!r} — "
                f"expected strict={expected!r} (v15.0.0: pre_dispatch strict "
                f"by default, all other chain events permissive)"
            )

    def test_complete_round_payload_reaches_each_hook_exactly_once(self) -> None:
        gen = ProposalGenerator()
        base = _base_dispatch()
        base["change_context"] = {"change_id": "s10-round"}
        checklist = SimpleNamespace(
            items=(
                SimpleNamespace(
                    item_id="C-G1.1",
                    assertion="round assertion",
                    verify="pytest round",
                    checked=False,
                    reverted_reason="user reason verbatim",
                ),
            )
        )
        selection = SimpleNamespace(
            selected=(SimpleNamespace(item_id="C-G1.1", priority="P0", reverted=True),)
        )
        calls, fake = self._make_call_recorder()

        with patch("devolaflow.lifecycle.run_hooks", side_effect=fake):
            result = gen.generate_round_dispatch(
                base,
                _verdict_with_findings([_blocker_finding()]),
                round_num=2,
                checklist=checklist,
                selection=selection,
                round_n=2,
            )

        events = [call[0] for call in calls]
        assert events == [
            PRE_DISPATCH_EVENT,
            POST_DISPATCH_EVENT,
            PRE_HANDOFF_EVENT,
            PRE_PLUGIN_INVOCATION_EVENT,
        ]
        assert events.count(PRE_DISPATCH_EVENT) == 1
        assert events.count(POST_DISPATCH_EVENT) == 1
        assert all(call[1] == result for call in calls)
        rules = result["context"]["applicable_rules"]["reinforcement"]["rules"]
        assert [rule["id"] for rule in rules] == [
            "R-C-G1.1-002",
            "F-PV04-1",
        ]
        assert result["change_context"]["round_context"]["reverted_ids"] == ["C-G1.1"]

    def test_partial_round_inputs_raise_before_any_hook(self) -> None:
        gen = ProposalGenerator()
        with (
            patch("devolaflow.lifecycle.run_hooks") as run_hooks,
            pytest.raises(ValueError, match="must be provided together"),
        ):
            gen.generate_round_dispatch(
                _base_dispatch(),
                None,
                round_num=2,
                checklist=SimpleNamespace(items=()),
            )
        run_hooks.assert_not_called()


# ---------------------------------------------------------------------------
# R5 strict byte-identical: dispatch payload unchanged when no extras register
# ---------------------------------------------------------------------------


class TestR5ByteIdentical:
    """Pre-PV-04 control bytes must equal post-PV-04 bytes when no extras register.

    Per the v8.4.0 retro §4.1 #4 R5 strict pattern, adding the hook
    chain MUST NOT mutate the dispatch payload. The default handlers
    (``validate_dispatch`` + ``post_dispatch`` no-op +
    ``validate_owned_files``) only inspect the payload; they never
    write to it.
    """

    def test_round1_payload_unchanged(self, tmp_path, monkeypatch, caplog) -> None:
        gen = ProposalGenerator()
        base = _base_dispatch()
        base["hdr"] = {"id": "dispatch-byte-identity", "layer": "wave"}
        base["change_context"] = {"change_id": "byte-identity"}
        base["layer"] = "L2"
        control = copy.deepcopy(base)
        monkeypatch.chdir(tmp_path)
        if record_dispatch_telemetry not in list_handlers(POST_DISPATCH_EVENT):
            register_hook(POST_DISPATCH_EVENT, record_dispatch_telemetry)

        inactive = gen.generate_round_dispatch(
            base,
            _verdict_with_findings([_blocker_finding()]),
            round_num=1,
        )
        assert inactive == control, (
            "round-1 pass-through must return a deep copy of base, byte-identical"
        )
        assert inactive is not base, "result must be a new object (deepcopy contract)"

        active = tmp_path / ".local" / ".agent" / "active" / "byte-identity"
        active.mkdir(parents=True)
        measured = gen.generate_round_dispatch(
            base,
            _verdict_with_findings([_blocker_finding()]),
            round_num=1,
        )
        assert measured == control
        assert (active / "harness.jsonl").is_file()

        with (
            patch(
                "devolaflow.harness.telemetry.append_harness_record",
                side_effect=OSError("telemetry disk failure"),
            ),
            caplog.at_level("WARNING", logger="devolaflow.harness.telemetry"),
        ):
            failed = gen.generate_round_dispatch(
                base,
                _verdict_with_findings([_blocker_finding()]),
                round_num=1,
            )
        assert failed == control
        assert "telemetry disk failure" in caplog.text

    def test_no_findings_payload_unchanged(self) -> None:
        gen = ProposalGenerator()
        base = _base_dispatch()
        control = copy.deepcopy(base)
        actual = gen.generate_round_dispatch(
            base,
            _verdict_with_findings([]),
            round_num=2,
        )
        assert actual == control, (
            "empty-findings path must return a byte-identical deep copy of base"
        )

    def test_reinforcement_payload_matches_control(self) -> None:
        gen = ProposalGenerator()
        base = _base_dispatch()
        verdict = _verdict_with_findings([_blocker_finding()])

        # Build the control: same logic as feedback.py minus the hook chain.
        control_dispatch = copy.deepcopy(base)
        block = gen.generate_reinforcement(verdict, round_num=2)
        assert block is not None
        control_dispatch = merge_reinforcement_into_dispatch(control_dispatch, block)

        actual = gen.generate_round_dispatch(base, verdict, round_num=2)
        assert actual == control_dispatch, (
            "reinforcement-applied path must produce a byte-identical payload "
            "to the pre-PV-04 control (no hook side-effects in the payload)"
        )


# ---------------------------------------------------------------------------
# Defensive: a buggy custom handler must not crash dispatch emission (S-5)
# ---------------------------------------------------------------------------


class TestHandlerExceptionsAreSwallowed:
    """A buggy custom handler raising mid-call MUST NOT bring down dispatch.

    Per the design doc §1.3 and Soul Rule S-5 (no silent failures), a
    custom hook handler that raises is caught, logged at WARNING, and
    the dispatch is returned unchanged. This protects the round-N+1
    emission path from third-party hook bugs.
    """

    def test_handler_raise_is_logged_and_swallowed(self, caplog) -> None:
        gen = ProposalGenerator()

        def boom(event, payload, *, strict=False):
            del payload, strict
            raise RuntimeError(f"{event} handler exploded")

        with (
            patch("devolaflow.lifecycle.run_hooks", side_effect=boom),
            caplog.at_level("WARNING", logger="devolaflow.feedback"),
        ):
            result = gen.generate_round_dispatch(
                _base_dispatch(),
                _verdict_with_findings([_blocker_finding()]),
                round_num=2,
            )
        # Dispatch is still returned (S-5 — no silent failures, but no propagation).
        assert "task_id" in result
        # And we logged the failure at WARNING level (S-5).
        warnings = [rec for rec in caplog.records if rec.levelname == "WARNING"]
        assert any("hook raised" in rec.message for rec in warnings), (
            "handler raise must be logged at WARNING level via logger.warning"
        )


# ---------------------------------------------------------------------------
# v15.0.0 strict graduation (G-038 flips 2/3/7) — pre_dispatch BLOCKS dispatch
# ---------------------------------------------------------------------------


class TestV15StrictGraduation:
    """Pre-dispatch content violations BLOCK the dispatch since v15.0.0.

    The ``pre_dispatch`` chain (``validate_dispatch`` default incl. the
    base AC checks VD001-VD004 + AC-v2 structural checks VD005-VD008,
    plus the ``validate_owned_files`` / ``reject_subagent_quality_score``
    / ``reject_subagent_banner_emission`` extras) runs STRICT by default
    at the emission call site — block, not warn. The documented
    permissive escape is ``ProposalGenerator(pre_dispatch_strict=False)``
    (threaded to ``ProposalEmitter(pre_dispatch_strict=False)``).
    """

    def test_pre_dispatch_violation_blocks_dispatch_by_default(self) -> None:
        """A payload with no testable AC raises VD002 out of the dispatch path."""
        from devolaflow.lifecycle import HookViolation

        gen = ProposalGenerator()
        bad = _base_dispatch()
        del bad["accept"]  # no acceptance criteria → VD002 blocker
        with pytest.raises(HookViolation) as exc_info:
            gen.generate_round_dispatch(
                bad,
                _verdict_with_findings([_blocker_finding()]),
                round_num=1,
            )
        assert exc_info.value.code == "VD002"
        assert exc_info.value.severity == "blocker"

    def test_pre_dispatch_permissive_escape_warns_and_returns(self, caplog) -> None:
        """``pre_dispatch_strict=False`` restores the pre-v15.0.0 warn-only path.

        The violating dispatch is still RETURNED (byte-identical deep copy
        of the base — strictness never mutates the payload) and the
        violation is logged at WARNING via the lifecycle logger (S-5).
        """
        gen = ProposalGenerator(pre_dispatch_strict=False)
        bad = _base_dispatch()
        del bad["accept"]
        control = copy.deepcopy(bad)
        with caplog.at_level("WARNING", logger="devolaflow.lifecycle.dispatcher"):
            result = gen.generate_round_dispatch(
                bad,
                _verdict_with_findings([_blocker_finding()]),
                round_num=1,
            )
        assert result == control, "permissive escape must return the dispatch unchanged"
        assert any("VD002" in rec.message for rec in caplog.records), (
            "S-5: the permissive escape must still WARN via the lifecycle logger"
        )
