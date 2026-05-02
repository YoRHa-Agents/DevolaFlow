"""Self-Improving Feedback Loop Module for DevolaFlow.

Collects execution metrics from gate verdicts and status reports, analyzes
patterns (recurring violations, convergence stagnation, profile mismatches),
and generates structured improvement proposals with safeguards against
runaway self-modification.

Design ref: S02-T08-engine-infra.md §5 (Integration Point 5)
"""

from __future__ import annotations

import copy
import logging
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from devolaflow.gate.models import Finding, GateVerdict, Severity
from devolaflow.gate.reinforcement import (
    ReinforcementBlock,
    findings_to_reinforcement,
    merge_reinforcement_into_dispatch,
)
from devolaflow.learnings import _now_iso, _read_lines

logger = logging.getLogger(__name__)

# v8.4.4 PV-04 — Soul Rule S-10 enforcement: every dispatch payload returned
# by ``generate_round_dispatch`` is run through the lifecycle hook chain
# (`pre_dispatch` → `post_dispatch`) so prompt-side governance contracts can
# observe / validate / annotate the payload without coupling
# ``feedback.py`` to specific handlers. The hook is invoked in PERMISSIVE
# mode (``strict=False``) per the v8.4.0 retro §4.1 #4 R5 strict pattern —
# byte-output is identical when no extras are registered, and a buggy
# custom handler MUST NOT bring down the round-N+1 dispatch emission.
#
# Closes the dead-wire identified in v6.0.3 retro precedent + C-03 from
# `.local/research/v9.0.0_gap_analysis.md` §3.1.
#
# v9.1.3 PV-03 — extends the chain to include `pre_handoff` AFTER the
# governance tail. At this point the dispatch payload is fully-formed +
# lint-validated, making it the correct moment to consider materialising
# a handoff envelope under `.local/.agent/handoff/`. The default
# handler (`auto_write_handoff`) is a no-op when
# `DEVOLAFLOW_AGENT_WORKSPACE` is unset (R5 strict byte-identical), so
# adding the third event preserves the byte-output guarantee for
# operators who haven't opted into the agent-workspace activation
# surface. Closes G-005 deferred from v9.1.0 by giving
# `HandoffStore.write_envelope` its FIRST production caller.
_HOOK_PRE_DISPATCH = "pre_dispatch"
_HOOK_POST_DISPATCH = "post_dispatch"
_HOOK_PRE_HANDOFF = "pre_handoff"
# v9.4.0 PV-03 — extends the chain to include `pre_plugin_invocation`
# AFTER the v9.1.3 PV-03 `pre_handoff` slot. At this point the dispatch
# payload is fully-formed + lint-validated + handoff-resolved, making
# it the correct moment to consider auto-installing plugins cited in
# the dispatch's `workflow` / `plugin_id` / `plugin_ids` fields. The
# default handler is a no-op when `DEVOLAFLOW_AUTO_INSTALL_PLUGINS` is
# unset (R5 strict byte-identical), so adding the fourth event
# preserves the byte-output guarantee for operators who have not opted
# into the dispatcher pre-flight plugin install surface. Closes the
# PV-01 dead-wire ghost (D-P-2 from
# `.local/research/v9.4.0_gap_analysis.md` §3.1) by giving the
# `ensure_plugin()` chain its first dispatcher caller.
_HOOK_PRE_PLUGIN_INVOCATION = "pre_plugin_invocation"

LOCKED_FILES = frozenset(
    {
        "__init__.py",
        "pyproject.toml",
        "feedback.py",
    }
)

MAX_PROPOSALS_PER_WORKFLOW = 3
CONFIDENCE_FLOOR = 0.7


@dataclass
class Proposal:
    """A structured improvement proposal."""

    id: str
    type: str
    description: str
    confidence: float
    target_file: str
    suggested_change: str


def _is_locked(target_file: str) -> bool:
    """Return True if *target_file* is in the scope-lock set."""
    basename = Path(target_file).name
    if basename in LOCKED_FILES:
        return True
    return basename.startswith("test_")


def _inside_devolaflow(target_file: str) -> bool:
    """Return True if *target_file* lives within the DevolaFlow tree.

    Accepts relative paths (rooted at repo), or paths containing
    'devolaflow', 'workflow-system', 'schemas', or '.cursor/rules'.
    """
    allowed_prefixes = (
        "src/devolaflow/",
        "workflow-system/",
        "schemas/",
        ".cursor/rules/",
    )
    return any(target_file.startswith(p) or f"/{p}" in target_file for p in allowed_prefixes)


class FeedbackCollector:
    """Extracts structured metrics from gate verdicts and status reports."""

    def collect_from_gate(self, verdict: GateVerdict) -> dict:
        """Extract composite_score, decision, and findings_count from a GateVerdict."""
        findings_count = 0
        if "findings" in verdict.details:
            raw = verdict.details["findings"]
            findings_count = len(raw) if isinstance(raw, list) else int(raw)

        return {
            "composite_score": verdict.composite_score,
            "decision": verdict.decision,
            "findings_count": findings_count,
        }

    def collect_from_report(self, report_data: dict) -> dict:
        """Extract metrics, issues, and elapsed time from a status report dict."""
        return {
            "metrics": report_data.get("metrics", {}),
            "issues": report_data.get("issues", []),
            "elapsed_seconds": report_data.get("elapsed_seconds", 0),
        }

    def collect_workflow_metrics(self, stages: list[dict]) -> dict:
        """Aggregate workflow-level metrics across all stages.

        Each stage dict is expected to have keys: rounds, composite_score, name.
        """
        if not stages:
            return {
                "total_rounds": 0,
                "avg_composite": 0.0,
                "bottleneck_stage": "",
            }

        total_rounds = sum(s.get("rounds", 0) for s in stages)
        scores = [s.get("composite_score", 0.0) for s in stages]
        avg_composite = sum(scores) / len(scores) if scores else 0.0

        bottleneck = max(stages, key=lambda s: s.get("rounds", 0))

        return {
            "total_rounds": total_rounds,
            "avg_composite": round(avg_composite, 2),
            "bottleneck_stage": bottleneck.get("name", ""),
        }


class FeedbackAnalyzer:
    """Detects patterns in execution history that suggest improvements."""

    def detect_recurring_violations(
        self,
        learnings_path: Path,
        min_occurrences: int = 3,
    ) -> list[dict]:
        """Find rule_ids that appear >= *min_occurrences* times in learnings."""
        entries = _read_lines(learnings_path)
        rule_counts: Counter[str] = Counter()
        rule_examples: dict[str, list[str]] = {}

        for entry in entries:
            rid = entry.get("rule_id", "")
            if not rid:
                continue
            rule_counts[rid] += 1
            rule_examples.setdefault(rid, []).append(entry.get("insight", ""))

        return [
            {
                "rule_id": rid,
                "count": count,
                "examples": rule_examples.get(rid, [])[:3],
            }
            for rid, count in rule_counts.items()
            if count >= min_occurrences
        ]

    def detect_convergence_stagnation(
        self,
        rounds: list[dict],
        threshold: float = 2.0,
    ) -> bool:
        """Return True if score improvement < *threshold* for 2+ consecutive rounds.

        Each round dict must have a ``composite_score`` key.
        """
        if len(rounds) < 3:
            return False

        consecutive_stagnant = 0
        for i in range(1, len(rounds)):
            prev = rounds[i - 1].get("composite_score", 0.0)
            curr = rounds[i].get("composite_score", 0.0)
            improvement = curr - prev
            if improvement < threshold:
                consecutive_stagnant += 1
                if consecutive_stagnant >= 2:
                    return True
            else:
                consecutive_stagnant = 0

        return False

    def detect_profile_mismatch(
        self,
        task_type: str,
        actual_metrics: dict,
        expected_thresholds: dict,
    ) -> list[str]:
        """Compare actual metrics against expected thresholds.

        Returns a list of human-readable mismatch descriptions.
        """
        mismatches: list[str] = []
        for metric_name, expected_value in expected_thresholds.items():
            actual_value = actual_metrics.get(metric_name)
            if actual_value is None:
                mismatches.append(
                    f"{task_type}: metric '{metric_name}' missing from actual metrics"
                )
                continue
            if (
                isinstance(expected_value, (int, float))
                and isinstance(actual_value, (int, float))
                and actual_value < expected_value
            ):
                mismatches.append(
                    f"{task_type}: '{metric_name}' is {actual_value}, expected >= {expected_value}"
                )
        return mismatches


@dataclass
class _ProposalState:
    """Internal bookkeeping for proposal generation safeguards."""

    recent_rule_ids: dict[str, str] = field(default_factory=dict)


def _make_proposal(
    index: int,
    ptype: str,
    description: str,
    confidence: float,
    target_file: str,
    suggested_change: str,
) -> dict:
    return {
        "id": f"prop-{_now_iso()[:10]}-{index + 1:03d}",
        "type": ptype,
        "description": description,
        "confidence": confidence,
        "target_file": target_file,
        "suggested_change": suggested_change,
    }


def _filter_valid_proposals(proposals: list[dict]) -> list[dict]:
    valid: list[dict] = []
    for p in proposals:
        tf = p.get("target_file", "")
        if _is_locked(tf):
            logger.info("Rejecting proposal for locked file: %s", tf)
            continue
        if not _inside_devolaflow(tf):
            logger.info("Rejecting proposal for out-of-scope file: %s", tf)
            continue
        valid.append(p)
    return valid[:MAX_PROPOSALS_PER_WORKFLOW]


class ProposalGenerator:
    """Creates structured improvement proposals from analysis results.

    Safeguards enforced:
    - Max ``MAX_PROPOSALS_PER_WORKFLOW`` (3) proposals per invocation
    - Confidence floor ``CONFIDENCE_FLOOR`` (0.7) on source evidence
    - Scope-lock: proposals targeting locked files are rejected
    - DevolaFlow scope: proposals for files outside the repo are rejected
    """

    def __init__(self) -> None:
        """Initialize the proposal generator with empty internal state."""
        self._state = _ProposalState()

    def generate_proposals(self, analysis: dict) -> list[dict]:
        """Generate improvement proposals from an analysis dict.

        *analysis* should contain optional keys:
        - ``recurring_violations``: list[dict] from FeedbackAnalyzer
        - ``stagnation_detected``: bool
        - ``profile_mismatches``: list[str]
        - ``confidence``: float — overall analysis confidence

        Returns a list of proposal dicts, each with keys:
        id, type, description, confidence, target_file, suggested_change.
        """
        confidence = float(analysis.get("confidence", 0.0))
        if confidence < CONFIDENCE_FLOOR:
            logger.info(
                "Analysis confidence %.2f below floor %.2f — no proposals",
                confidence,
                CONFIDENCE_FLOOR,
            )
            return []

        proposals: list[dict] = []
        self._add_violation_proposals(analysis, confidence, proposals)
        self._add_stagnation_proposal(analysis, confidence, proposals)
        self._add_mismatch_proposals(analysis, confidence, proposals)
        return _filter_valid_proposals(proposals)

    def _add_violation_proposals(
        self,
        analysis: dict,
        confidence: float,
        proposals: list[dict],
    ) -> None:
        for violation in analysis.get("recurring_violations", []):
            if len(proposals) >= MAX_PROPOSALS_PER_WORKFLOW:
                return
            rule_id = violation.get("rule_id", "")
            if not rule_id:
                continue
            target = f".cursor/rules/{rule_id.lower().replace('-', '_')}.mdc"
            if _is_locked(target):
                logger.info("Skipping locked target: %s", target)
                continue
            proposals.append(
                _make_proposal(
                    index=len(proposals),
                    ptype="rule_update",
                    description=(
                        f"Rule {rule_id} violated {violation.get('count', 0)} times — "
                        "consider clarification or threshold adjustment"
                    ),
                    confidence=confidence,
                    target_file=target,
                    suggested_change=f"Review rule {rule_id} for clarity",
                )
            )

    def _add_stagnation_proposal(
        self,
        analysis: dict,
        confidence: float,
        proposals: list[dict],
    ) -> None:
        if not analysis.get("stagnation_detected"):
            return
        if len(proposals) >= MAX_PROPOSALS_PER_WORKFLOW:
            return
        target = "workflow-system/agent/context_profiles.yaml"
        if _is_locked(target):
            return
        proposals.append(
            _make_proposal(
                index=len(proposals),
                ptype="profile_tune",
                description=(
                    "Convergence stagnation detected — "
                    "consider adjusting gate thresholds or max_rounds"
                ),
                confidence=confidence,
                target_file=target,
                suggested_change="Lower composite_threshold or increase max_rounds",
            )
        )

    def _add_mismatch_proposals(
        self,
        analysis: dict,
        confidence: float,
        proposals: list[dict],
    ) -> None:
        target = "workflow-system/agent/context_profiles.yaml"
        for mismatch in analysis.get("profile_mismatches", []):
            if len(proposals) >= MAX_PROPOSALS_PER_WORKFLOW:
                return
            if _is_locked(target):
                continue
            proposals.append(
                _make_proposal(
                    index=len(proposals),
                    ptype="profile_tune",
                    description=f"Profile mismatch: {mismatch}",
                    confidence=confidence,
                    target_file=target,
                    suggested_change="Adjust section_priorities or token budget",
                )
            )

    def generate_reinforcement(
        self,
        verdict: GateVerdict,
        round_num: int,
        target_score: float = 85.0,
        severity_floor: Severity = "major",
    ) -> ReinforcementBlock | None:
        """Generate a :class:`ReinforcementBlock` from a gate verdict.

        Bridges feedback analysis (Approach E) with the dispatch-level
        reinforcement mechanism (Approach B).  Returns ``None`` when the
        verdict has no actionable findings.
        """
        findings_raw = verdict.details.get("findings", [])
        if not findings_raw:
            return None

        findings: list[Finding] = []
        for i, raw in enumerate(findings_raw):
            if isinstance(raw, Finding):
                findings.append(raw)
            elif isinstance(raw, dict):
                findings.append(
                    Finding(
                        finding_id=raw.get("finding_id", f"F-{i:03d}"),
                        severity=raw.get("severity", "major"),
                        category=raw.get("category", "general"),
                        location=raw.get("location", ""),
                        description=raw.get("description", ""),
                        suggestion=raw.get("suggestion", ""),
                        rule_id=raw.get("rule_id", ""),
                    )
                )

        if not findings:
            return None

        prior_score = verdict.composite_score or 0.0
        return findings_to_reinforcement(
            findings=findings,
            round_num=round_num,
            prior_score=prior_score,
            target_score=target_score,
            severity_floor=severity_floor,
        )

    def generate_round_dispatch(
        self,
        base_dispatch: dict[str, Any],
        verdict: GateVerdict | None,
        round_num: int,
        target_score: float = 85.0,
        severity_floor: Severity = "major",
    ) -> dict[str, Any]:
        """Produce a dispatch for convergence round ``round_num``.

        V6-01 wiring: stitches :meth:`generate_reinforcement` into the
        dispatch lifecycle so L3 Task Agents receive the reinforcement
        block under ``context.applicable_rules.reinforcement`` on rounds
        ≥ 2.  Round 1 is a pure pass-through — the first attempt has no
        prior round to learn from.

        v8.4.4 PV-04 wiring: the FINAL dispatch payload of every return
        path is run through the lifecycle hook chain
        (``pre_dispatch`` → ``post_dispatch``) per Soul Rule S-10
        ("Prompt-Side Governance Contract Embedding"). Hooks run in
        permissive mode — see ``_emit_dispatch`` docstring for R5
        strict-byte-identical contract.

        The input ``base_dispatch`` is never mutated; a deep copy is
        returned in all cases.
        """
        dispatch = copy.deepcopy(base_dispatch)

        if round_num <= 1 or verdict is None:
            return self._emit_dispatch(dispatch)

        block = self.generate_reinforcement(
            verdict,
            round_num=round_num,
            target_score=target_score,
            severity_floor=severity_floor,
        )
        if block is None:
            return self._emit_dispatch(dispatch)

        return self._emit_dispatch(merge_reinforcement_into_dispatch(dispatch, block))

    def _emit_dispatch(self, dispatch: dict[str, Any]) -> dict[str, Any]:
        """Run the lifecycle hook chain on ``dispatch`` and return it unchanged.

        v8.4.4 PV-04 — Soul Rule S-10 enforcement point. Fires
        ``pre_dispatch`` → ``post_dispatch`` → ``pre_handoff`` against
        the dispatch payload via :func:`devolaflow.lifecycle.run_hooks`;
        all three calls run in permissive mode (``strict=False``) so a
        violation only emits a WARNING via the lifecycle logger and
        never raises out of the dispatch path.

        v9.1.3 PV-03 — added ``pre_handoff`` AFTER the governance tail
        (Soul Rule S-10) so the payload is fully-formed + lint-validated
        before the handoff-write decision runs. The default
        ``auto_write_handoff`` handler is a no-op when
        ``DEVOLAFLOW_AGENT_WORKSPACE`` is unset (R5 strict
        byte-identical), so adding the third event preserves the
        byte-output guarantee for operators who haven't opted into the
        agent-workspace activation surface. Closes G-005 from v9.1.0
        by giving ``HandoffStore.write_envelope`` its FIRST production
        caller.

        v9.4.0 PV-03 — added ``pre_plugin_invocation`` AFTER
        ``pre_handoff`` so the dispatch's plugin candidates can be
        auto-installed BEFORE the L3 Task Agent attempts to call the
        plugin's binary. The default ``pre_plugin_invocation`` handler
        is a no-op when ``DEVOLAFLOW_AUTO_INSTALL_PLUGINS`` is unset
        (R5 strict byte-identical), so adding the fourth event
        preserves the byte-output guarantee for operators who have not
        opted into the dispatcher pre-flight surface. Closes the
        PV-01 dead-wire ghost (D-P-2 from
        ``.local/research/v9.4.0_gap_analysis.md`` §3.1) by giving
        the ``ensure_plugin()`` chain its FIRST dispatcher caller.
        The hook resolves plugin candidates from the dispatch's
        ``workflow`` / ``plugin_id`` / ``plugin_ids`` fields via the
        ``runtime-plugins.yaml#plugins[*].invoked_by_workflows``
        registry mapping (see :func:`devolaflow.plugins.installer.plugins_for_workflow`).

        R5 strict-byte-identical invariant (v8.4.0 retro §4.1 #4): when
        no extra handlers are registered for either event, the returned
        ``dispatch`` is byte-identical to the pre-PV-04 behaviour. The
        permissive default handlers either return cleanly
        (``post_dispatch`` is a no-op; ``pre_handoff`` is a no-op when
        the env-flag is OFF; ``pre_plugin_invocation`` is a no-op when
        the env-flag is OFF) or emit a WARNING log without mutating
        the payload (``pre_dispatch`` / ``validate_dispatch``).

        S-5 (no silent failures): a buggy custom handler that raises
        from inside the dispatch path is caught here, logged at
        WARNING level via ``logger.warning``, and the dispatch is
        returned unchanged — the round-N+1 emission MUST NOT crash on a
        third-party hook bug. Each event is wrapped in its own
        try/except so a failure on one does NOT short-circuit the
        others (the hook chain is collectively a contract; per-event
        independence is intentional).
        """
        try:
            from devolaflow import lifecycle
        except ImportError as exc:  # pragma: no cover - defensive
            logger.warning(
                "feedback._emit_dispatch: lifecycle module unavailable (%s); "
                "skipping pre_dispatch / post_dispatch / pre_handoff / "
                "pre_plugin_invocation hooks",
                exc,
            )
            return dispatch

        for event in (
            _HOOK_PRE_DISPATCH,
            _HOOK_POST_DISPATCH,
            _HOOK_PRE_HANDOFF,
            _HOOK_PRE_PLUGIN_INVOCATION,
        ):
            try:
                lifecycle.run_hooks(event, dispatch, strict=False)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "feedback._emit_dispatch: %s hook raised %s; dispatch returned unchanged",
                    event,
                    exc,
                )
        return dispatch


# ---------------------------------------------------------------------------
# v9.7.0 (PV-03 — Performance Overhaul #2) — Auto-wire AsyncDispatchExecutor
# for L2-wave parallel L3 dispatches.
#
# The v9.3.0 PV-05 ``AsyncDispatchExecutor`` shipped library-only — the
# class machinery was complete but no production caller actually invoked
# it. v9.7.0 PV-03 closes the gap by wiring it into a public dispatch
# entry point at the L2-wave boundary.
#
# ``dispatch_wave_tasks(wave_definition, dispatch_factory)`` is the
# canonical caller: pass a parsed wave-definition dict (the YAML loaded
# from ``schemas/wave-definition.schema.yaml``) plus a factory that
# accepts a per-task spec dict and returns a zero-arg callable to run
# that task. The function inspects ``sync_barrier.mode``:
#
# * ``"parallel"`` with ≥ 2 tasks → :meth:`AsyncDispatchExecutor.dispatch_parallel`
#   under :func:`asyncio.run`. Concurrency is capped at
#   ``sync_barrier.max_parallelism`` when set, else
#   :data:`DEFAULT_MAX_CONCURRENCY`. The executor schedules the
#   callables via :func:`asyncio.gather` + a bounded
#   :class:`asyncio.Semaphore`; sync callables go through
#   :func:`asyncio.to_thread` so a slow sync call does not block the
#   loop.
# * ``"all"`` (the default sync barrier — wait for every branch) /
#   single-task waves / non-parallel modes → :meth:`AsyncDispatchExecutor.dispatch_sequential`.
#   Same TaskOutcome capture contract; no asyncio loop init cost.
#
# P1 invariant — Dispatcher-Not-Implementer (Soul Rule S-1):
# :func:`dispatch_wave_tasks` does NOT perform any work itself. It only
# schedules the caller-provided callables. The actual L3 Task work
# happens inside each callable (typically a ``Task`` tool invocation
# or a cached :func:`select_context` call). The executor is a pure
# orchestration layer with zero domain knowledge of compression,
# dispatch payload validation, gate scoring, etc. Verified at test
# time by
# :func:`tests.test_async_wave_dispatch_wired.test_dispatch_wave_tasks_preserves_p1`.
#
# Exception isolation: per S-5 (no silent failures), failed tasks
# carry their exception inside :class:`TaskOutcome` rather than
# raising out of the wave. The caller decides whether to escalate
# per P4 (Bounded Retry — escalate up the layer hierarchy on any
# blocker-level failure). The wave-level dispatch itself never raises
# on individual task failure; only callable-shape errors (non-callable
# factory output, malformed wave_definition) raise eagerly so the
# caller can fail fast on contract violations.
#
# Source: v9.7.0 PV-03 spec — closes D-N-3 (AsyncDispatchExecutor
# library-only carry-forward) from
# ``.local/research/v9.7.0_gap_analysis.md`` §1.2.
# ---------------------------------------------------------------------------


def dispatch_wave_tasks(
    wave_definition: dict[str, Any],
    dispatch_factory: Any,
    *,
    max_concurrency: int | None = None,
) -> list[Any]:
    """Dispatch an L2 wave's L3 tasks via :class:`AsyncDispatchExecutor`.

    Auto-wires v9.3.0 PV-05's library-only :class:`AsyncDispatchExecutor`
    into the L2-wave dispatch path per v9.7.0 PV-03. Inspects
    ``wave_definition['sync_barrier']['mode']``:

    * ``"parallel"`` with ≥ 2 tasks →
      :meth:`AsyncDispatchExecutor.dispatch_parallel` (asyncio.gather +
      bounded semaphore). Concurrency is capped at
      ``sync_barrier.max_parallelism`` when set; falls back to
      :data:`DEFAULT_MAX_CONCURRENCY` (4) otherwise. The
      ``max_concurrency`` keyword overrides both.
    * ``"all"`` / single-task waves / unrecognised modes →
      :meth:`AsyncDispatchExecutor.dispatch_sequential` (sync fallback
      path; identical TaskOutcome capture).

    Args:
      wave_definition: Parsed wave-definition dict (loaded from a YAML
        instance of ``schemas/wave-definition.schema.yaml``). MUST
        carry ``tasks: list[dict]`` and SHOULD carry ``sync_barrier``
        with ``mode`` and optionally ``max_parallelism``.
      dispatch_factory: Callable that accepts a task spec dict (one
        element of ``wave_definition['tasks']``) and returns a zero-arg
        callable executing that task. The factory's return value is
        the unit of work scheduled by the executor. P1 preserved —
        ``dispatch_wave_tasks`` itself does NOT execute the returned
        callable; it only schedules.
      max_concurrency: Optional override for the parallel-mode
        concurrency cap. When ``None`` (default), reads
        ``sync_barrier.max_parallelism`` then falls back to
        :data:`DEFAULT_MAX_CONCURRENCY`. Must be ≥ 1.

    Returns:
      ``list[TaskOutcome]`` — one per task in input order. Failed tasks
      carry their exception in ``outcome.exception`` and never raise
      out of this function (S-5). Empty ``tasks`` returns ``[]``
      immediately without spawning a loop.

    Raises:
      TypeError: when ``wave_definition`` is not a dict, ``tasks`` is
        not a list, or ``dispatch_factory`` is not callable. S-5 —
        contract violations are explicit, never silent.
      ExecutorError: when the resolved ``max_concurrency`` is < 1.
    """
    from devolaflow.agent_workspace.dispatch_executor import (
        DEFAULT_MAX_CONCURRENCY,
        AsyncDispatchExecutor,
    )

    if not isinstance(wave_definition, dict):
        raise TypeError(f"wave_definition must be a dict, got {type(wave_definition).__name__}")
    if not callable(dispatch_factory):
        raise TypeError(f"dispatch_factory must be callable, got {type(dispatch_factory).__name__}")

    tasks_raw = wave_definition.get("tasks", [])
    if not isinstance(tasks_raw, list):
        raise TypeError(f"wave_definition['tasks'] must be a list, got {type(tasks_raw).__name__}")
    if not tasks_raw:
        return []

    sync_barrier = wave_definition.get("sync_barrier") or {}
    if not isinstance(sync_barrier, dict):
        sync_barrier = {}
    mode = sync_barrier.get("mode", "all")

    if max_concurrency is None:
        max_concurrency = sync_barrier.get("max_parallelism") or DEFAULT_MAX_CONCURRENCY

    callables: list[tuple[str, Any]] = []
    for idx, task in enumerate(tasks_raw):
        if not isinstance(task, dict):
            raise TypeError(
                f"wave_definition['tasks'][{idx}] must be a dict, got {type(task).__name__}"
            )
        task_id = str(task.get("task_id") or task.get("id") or f"wave-task-{idx}")
        fn = dispatch_factory(task)
        if not callable(fn):
            raise TypeError(
                f"dispatch_factory(task[{idx}]) must return a callable, got {type(fn).__name__}"
            )
        callables.append((task_id, fn))

    executor = AsyncDispatchExecutor(max_concurrency=max_concurrency)
    if mode == "parallel" and len(callables) > 1:
        return executor.dispatch_parallel(callables)
    return executor.dispatch_sequential(callables)
