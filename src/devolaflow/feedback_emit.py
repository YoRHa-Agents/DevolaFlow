"""Lifecycle hook emission for ``ProposalGenerator`` dispatches.

Extracted from
:meth:`devolaflow.feedback.ProposalGenerator._emit_dispatch` in v10.6.0
PV-02 (D-Q-2 god-function refactor) per
``.local/research/v11.0.0_patches/D-Q-2.md``. The original method had
grown to carry **6 distinct responsibilities** in one cohesive but
architecturally-mixed surface; the v8.4.4 PV-04 + v9.1.3 PV-03 + v9.4.0
PV-03 chain growth had progressively bloated ``_emit_dispatch`` to
80 LOC + 4 in-loop event constants + 5 separate docstring sections.

This module owns the **dispatch-emission** subset of the original
responsibilities (#1, #3, #4, #5 from D-Q-2 §1):

1. Dispatch construction — :meth:`ProposalEmitter.emit` deep-copies
   ``base_dispatch`` then conditionally merges reinforcement.
3. Lifecycle hook chain firing — :meth:`ProposalEmitter._fire_hook_chain`
   runs the 4-event chain (``pre_dispatch`` → ``post_dispatch`` →
   ``pre_handoff`` → ``pre_plugin_invocation``) per Soul Rule S-10
   ("Prompt-Side Governance Contract Embedding"; see
   ``.cursor/rules/repo-governance.mdc`` S-10 + the v9.0.0 PV-04 +
   v9-ADR-004-lifecycle-wiring-and-s10.md ADR).
4. Per-event exception isolation — each hook is wrapped in its own
   try/except so a buggy custom handler does NOT crash dispatch
   (S-5 no-silent-failures pattern).
5. Lazy lifecycle module import — defensive
   ``try: from devolaflow import lifecycle`` so a missing lifecycle
   install path doesn't crash the round-N+1 emission.

Responsibility #2 (verdict→reinforcement extraction) stays on
:meth:`devolaflow.feedback.ProposalGenerator.generate_reinforcement`
and is passed in to :meth:`ProposalEmitter.emit` as a callable factory
(preserves the v6-01 reinforcement-wiring contract). Responsibility
#6 (`generate_proposals` flow) stays on ``ProposalGenerator`` —
unrelated to dispatch emission.

R5 strict byte-identical invariant (v8.4.0 retro §4.1 #4): when no
extra handlers are registered for any event, the dispatch returned by
:meth:`ProposalEmitter.emit` is byte-identical to the pre-PV-04
behaviour AND to the v10.5.x ``ProposalGenerator._emit_dispatch``
output. The 11 (10 currently shipped) regression tests in
``tests/test_dispatch_emission_runs_hooks.py`` are the release-blocker
contract — every refactor MUST keep them green.

v15.0.0 strict graduation (G-038 + G-001-strict cluster): the
``pre_dispatch`` event of the chain now runs STRICT by default — a
violation reported by ``validate_dispatch`` (incl. the VD005-VD008
AC-v2 structural checks), ``validate_owned_files``,
``reject_subagent_quality_score``, or
``reject_subagent_banner_emission`` raises :class:`HookViolation` and
BLOCKS the dispatch instead of warn-and-continue. Documented permissive
escape: construct ``ProposalEmitter(pre_dispatch_strict=False)`` (or
``ProposalGenerator(pre_dispatch_strict=False)``) to restore the
pre-v15.0.0 warn-only behaviour. The S-10 byte-identity contract is
UNCHANGED for clean payloads: strictness never mutates the payload —
it only decides whether a violating dispatch is released.

Source: v10.6.0 PV-02 — codified per D-Q-2 §2 patch_design; strict
graduation per `.local/research/v14.2.0_gap_analysis.md` §2.7 G-038.
"""

from __future__ import annotations

import copy
import logging
from collections.abc import Callable
from dataclasses import replace
from typing import Any

from devolaflow.gate.models import GateVerdict, Severity
from devolaflow.gate.reinforcement import (
    MAX_REINFORCEMENT_RULES,
    ReinforcementBlock,
    merge_reinforcement_into_dispatch,
)

logger = logging.getLogger(__name__)


# v8.4.4 PV-04 / v9.1.3 PV-03 / v9.4.0 PV-03 — S-10 hook-chain event constants.
#
# The chain order is the canonical S-10 governance tail (frozen by
# ``tests/test_dispatch_emission_runs_hooks.py::TestHookInvocation``):
#
# * ``pre_dispatch`` — validates dispatch CONTENT (acceptance
#   criteria, owned files, schema compliance). The default handler
#   chain includes :func:`devolaflow.lifecycle.validate_dispatch`
#   plus the registered :func:`validate_owned_files` extra.
# * ``post_dispatch`` — future-extensibility slot for governance
#   contracts (Soul-set version embedding, rule-manifest URL,
#   reinforcement state). v8.4.4 ships a permissive no-op default
#   to preserve cache bytes (R5 strict byte-identical).
# * ``pre_handoff`` — materialises a handoff envelope under
#   ``.local/.agent/handoff/`` when ``DEVOLAFLOW_AGENT_WORKSPACE=1``;
#   default is no-op when the env-flag is off (closes G-005 from
#   v9.1.0 by giving ``HandoffStore.write_envelope`` its FIRST
#   production caller).
# * ``pre_plugin_invocation`` — auto-installs plugins cited in the
#   dispatch's ``workflow`` / ``plugin_id`` / ``plugin_ids`` fields
#   when ``DEVOLAFLOW_AUTO_INSTALL_PLUGINS=1``; default is no-op
#   when the env-flag is off (closes the PV-01 dead-wire ghost
#   D-P-2 from ``.local/research/v9.4.0_gap_analysis.md`` §3.1).
#
# Reordering, renaming, or removing ANY of these 4 names is a
# release blocker per the S-10 ADR (v9-ADR-004) and ``test_pre_handoff
# _invoked_after_post_dispatch`` / ``test_pre_plugin_invocation_invoked
# _after_pre_handoff`` chain-order pins.
_HOOK_PRE_DISPATCH = "pre_dispatch"
_HOOK_POST_DISPATCH = "post_dispatch"
_HOOK_PRE_HANDOFF = "pre_handoff"
_HOOK_PRE_PLUGIN_INVOCATION = "pre_plugin_invocation"

# Single-source-of-truth for the firing order (consumed by
# :meth:`ProposalEmitter._fire_hook_chain`). Tuple is immutable so a
# downstream consumer cannot accidentally re-order in-place.
_HOOK_CHAIN: tuple[str, ...] = (
    _HOOK_PRE_DISPATCH,
    _HOOK_POST_DISPATCH,
    _HOOK_PRE_HANDOFF,
    _HOOK_PRE_PLUGIN_INVOCATION,
)


# Type alias for the reinforcement factory passed in by the parent
# (typically ``ProposalGenerator.generate_reinforcement``). Returning
# ``None`` signals "no actionable findings — pass-through dispatch".
ReinforcementFactory = Callable[..., ReinforcementBlock | None]


def _compose_reinforcement(
    supplemental: ReinforcementBlock | None,
    gate: ReinforcementBlock | None,
) -> ReinforcementBlock | None:
    """Prepend supplemental rules to gate rules with one stable global cap."""

    if supplemental is None:
        return gate

    rules = []
    seen_ids: set[str] = set()
    for block in (supplemental, gate):
        if block is None:
            continue
        for rule in block.rules:
            if rule.id in seen_ids:
                continue
            seen_ids.add(rule.id)
            rules.append(rule)
            if len(rules) == MAX_REINFORCEMENT_RULES:
                break
        if len(rules) == MAX_REINFORCEMENT_RULES:
            break

    metadata_source = gate or supplemental
    merged_rules = tuple(rules)
    if metadata_source is supplemental and merged_rules == supplemental.rules:
        return supplemental
    return replace(metadata_source, rules=merged_rules)


class ProposalEmitter:
    """Emit dispatch payloads through the S-10 lifecycle hook chain.

    Single-responsibility extraction of the v10.5.x
    ``ProposalGenerator._emit_dispatch`` body plus the round-N+1
    deep-copy + reinforcement-merge orchestration. The caller (typically
    :class:`devolaflow.feedback.ProposalGenerator`) injects its own
    :meth:`generate_reinforcement` as the factory so the emitter does
    NOT own the verdict-to-block conversion logic.

    Stateless by design: every call to :meth:`emit` is independent;
    no instance state accumulates across calls. The class wrapper
    exists to support future composition patterns (e.g. an alternate
    emitter that targets a different hook chain for testing) without
    breaking the v10.6.0 PV-02 refactor surface.

    Composition-over-inheritance: ``ProposalGenerator`` holds an
    instance of this class as ``self._emitter`` rather than inheriting
    from it. This keeps the S-10 contract surface narrow (one method
    + one helper) and prevents the v8.4.4 → v10.5.x god-class drift
    pattern from re-emerging.
    """

    def __init__(self, *, pre_dispatch_strict: bool = True) -> None:
        """Construct an emitter with the v15.0.0 strict-graduation knob.

        Args:
          pre_dispatch_strict: When ``True`` (the v15.0.0 default per
            G-038), the ``pre_dispatch`` event of the S-10 chain runs
            with ``strict=True`` — a hook violation raises
            :class:`devolaflow.lifecycle.HookViolation` out of
            :meth:`emit` and BLOCKS the dispatch. Pass ``False`` for
            the documented permissive escape (pre-v15.0.0 warn-only
            behaviour). The remaining chain events (``post_dispatch``
            / ``pre_handoff`` / ``pre_plugin_invocation``) always run
            permissively — they are side-effect adapters, not content
            validators.
        """
        self._pre_dispatch_strict = pre_dispatch_strict

    def emit(
        self,
        *,
        base_dispatch: dict[str, Any],
        verdict: GateVerdict | None,
        round_num: int,
        target_score: float = 85.0,
        severity_floor: Severity = "major",
        reinforcement_factory: ReinforcementFactory,
        supplemental_reinforcement: ReinforcementBlock | None = None,
    ) -> dict[str, Any]:
        """Produce a dispatch for convergence round ``round_num``.

        V6-01 wiring (preserved verbatim from the v10.5.x
        ``ProposalGenerator.generate_round_dispatch`` body): stitches
        the caller's reinforcement factory into the dispatch lifecycle
        so L3 Task Agents receive the reinforcement block under
        ``context.applicable_rules.reinforcement`` on rounds ≥ 2.
        Round 1 is a pure pass-through — the first attempt has no
        prior round to learn from.

        v8.4.4 PV-04 wiring: the FINAL dispatch payload of every
        return path is run through the S-10 lifecycle hook chain via
        :meth:`_fire_hook_chain` (permissive mode; see that method's
        docstring for the R5 strict byte-identical contract).

        The input ``base_dispatch`` is never mutated; a deep copy is
        returned in all cases (v8.4.0 retro §4.1 #4 R5 strict
        invariant — verified by
        ``tests/test_dispatch_emission_runs_hooks.py::TestR5ByteIdentical``).

        Parameters
        ----------
        base_dispatch:
            The v6-01 base dispatch payload to emit. NEVER mutated in
            place — the method always returns a fresh deep copy.
        verdict:
            The most recent gate verdict (``None`` for round 1 / no
            prior gate run).
        round_num:
            Convergence round number (1-indexed). ``round_num <= 1``
            short-circuits to the pure pass-through path even when a
            verdict is supplied — the first round has nothing to
            reinforce against.
        target_score, severity_floor:
            Forwarded to ``reinforcement_factory`` when called.
        reinforcement_factory:
            Callable owned by the caller (typically
            :meth:`ProposalGenerator.generate_reinforcement`) that
            converts a ``GateVerdict`` into a
            :class:`ReinforcementBlock` or ``None``. Composition over
            inheritance: ``ProposalEmitter`` does NOT own the
            verdict-to-block conversion — that lives on the
            ``ProposalGenerator`` per D-Q-2 §2 patch_design.
        supplemental_reinforcement:
            Optional caller-built rules that precede gate-derived findings.
            Stable id de-duplication and one global top-five cap apply only
            when this opt-in block is present; omitting it preserves legacy
            gate-only serialization byte-for-byte.

        Returns
        -------
        dict[str, Any]
            A fresh deep copy of ``base_dispatch`` (with the
            reinforcement block merged in for round ≥ 2 + non-empty
            findings); identical bytes to the v10.5.x
            ``ProposalGenerator.generate_round_dispatch`` output for
            every input the regression-suite covers.
        """
        dispatch = copy.deepcopy(base_dispatch)

        gate_block = None
        if round_num > 1 and verdict is not None:
            gate_block = reinforcement_factory(
                verdict,
                round_num=round_num,
                target_score=target_score,
                severity_floor=severity_floor,
            )

        block = _compose_reinforcement(supplemental_reinforcement, gate_block)
        if block is None:
            return self._fire_hook_chain(dispatch)

        return self._fire_hook_chain(merge_reinforcement_into_dispatch(dispatch, block))

    def _fire_hook_chain(self, dispatch: dict[str, Any]) -> dict[str, Any]:
        """Run the S-10 lifecycle hook chain on ``dispatch`` and return it unchanged.

        Verbatim move of the v10.5.x ``ProposalGenerator._emit_dispatch``
        body per D-Q-2 §2 patch_design + §9 risk register row #1.
        Fires the 4-event chain
        ``pre_dispatch`` → ``post_dispatch`` → ``pre_handoff`` →
        ``pre_plugin_invocation`` against ``dispatch`` via
        :func:`devolaflow.lifecycle.run_hooks`.

        v15.0.0 strict graduation (G-038): ``pre_dispatch`` runs with
        ``strict=self._pre_dispatch_strict`` (default ``True``) — a
        content violation raises the top-severity
        :class:`devolaflow.lifecycle.HookViolation` and BLOCKS the
        dispatch. The permissive escape is
        ``ProposalEmitter(pre_dispatch_strict=False)``. The other 3
        events always run in permissive mode (``strict=False``) so a
        violation there only emits a WARNING via the lifecycle logger
        and never raises out of the dispatch path.

        v9.1.3 PV-03 — ``pre_handoff`` lands AFTER the governance
        tail (Soul Rule S-10) so the payload is fully-formed +
        lint-validated before the handoff-write decision runs. The
        default ``auto_write_handoff`` handler is a no-op when
        ``DEVOLAFLOW_AGENT_WORKSPACE`` is unset (R5 strict
        byte-identical), so adding the third event preserves the
        byte-output guarantee for operators who haven't opted into
        the agent-workspace activation surface.

        v9.4.0 PV-03 — ``pre_plugin_invocation`` lands AFTER
        ``pre_handoff`` so the dispatch's plugin candidates can be
        auto-installed BEFORE the L3 Task Agent attempts to call the
        plugin's binary. The default ``pre_plugin_invocation``
        handler is a no-op when ``DEVOLAFLOW_AUTO_INSTALL_PLUGINS``
        is unset (R5 strict byte-identical), so adding the fourth
        event preserves the byte-output guarantee for operators who
        have not opted into the dispatcher pre-flight surface.

        R5 strict-byte-identical invariant (v8.4.0 retro §4.1 #4):
        when no extra handlers are registered for any event, the
        returned ``dispatch`` is byte-identical to the pre-PV-04
        behaviour. The permissive default handlers either return
        cleanly (``post_dispatch`` is a no-op; ``pre_handoff`` is a
        no-op when the env-flag is OFF; ``pre_plugin_invocation`` is
        a no-op when the env-flag is OFF) or emit a WARNING log
        without mutating the payload (``pre_dispatch`` /
        ``validate_dispatch``).

        S-5 (no silent failures): a buggy custom handler that raises
        from inside the dispatch path is caught here, logged at
        WARNING level via ``logger.warning``, and the dispatch is
        returned unchanged — the round-N+1 emission MUST NOT crash
        on a third-party hook bug. Each event is wrapped in its own
        try/except so a failure on one does NOT short-circuit the
        others (the hook chain is collectively a contract; per-event
        independence is intentional, codified by
        ``tests/test_dispatch_emission_runs_hooks.py::
        TestHandlerExceptionsAreSwallowed``). The ONLY exception type
        that propagates is the strict-mode governance raise: a
        :class:`HookViolation` escaping the ``pre_dispatch`` event
        while ``pre_dispatch_strict`` is engaged (v15.0.0 graduation —
        block, not warn).
        """
        try:
            from devolaflow import lifecycle
        except ImportError as exc:  # pragma: no cover - defensive
            logger.warning(
                "ProposalEmitter._fire_hook_chain: lifecycle module unavailable "
                "(%s); skipping pre_dispatch / post_dispatch / pre_handoff / "
                "pre_plugin_invocation hooks",
                exc,
            )
            return dispatch

        for event in _HOOK_CHAIN:
            # v15.0.0 strict graduation (G-038): only pre_dispatch is
            # content-validating; it alone carries the strict default.
            event_strict = self._pre_dispatch_strict and event == _HOOK_PRE_DISPATCH
            try:
                lifecycle.run_hooks(event, dispatch, strict=event_strict)
            except Exception as exc:  # noqa: BLE001
                if event_strict and isinstance(exc, lifecycle.HookViolation):
                    # Governance raise — BLOCK the dispatch (block, not
                    # warn). Permissive escape: pre_dispatch_strict=False.
                    raise
                logger.warning(
                    "ProposalEmitter._fire_hook_chain: %s hook raised %s; "
                    "dispatch returned unchanged",
                    event,
                    exc,
                )
        return dispatch


__all__ = [
    "ProposalEmitter",
    "ReinforcementFactory",
]
