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

from devolaflow.feedback_emit import ProposalEmitter
from devolaflow.gate.models import Finding, GateVerdict, Severity
from devolaflow.gate.reinforcement import (
    ReinforcementBlock,
    findings_to_reinforcement,
)
from devolaflow.learnings import _now_iso, _read_lines

logger = logging.getLogger(__name__)

# v10.6.0 PV-02 — the S-10 4-event lifecycle hook chain firing
# (``pre_dispatch`` → ``post_dispatch`` → ``pre_handoff`` →
# ``pre_plugin_invocation``) was extracted from this module into
# :class:`devolaflow.feedback_emit.ProposalEmitter`. The 4 hook event
# constants (``_HOOK_PRE_DISPATCH``, etc.) and the lazy lifecycle
# import live there now. Behaviour is byte-identical to v10.5.x
# baseline — pinned by ``tests/test_dispatch_emission_runs_hooks.py``
# (10 release-blocker tests) AND by the new
# ``tests/test_feedback_emit.py`` (8 unit tests on ``ProposalEmitter``
# in isolation). See PDS ``v11.0.0_patches/D-Q-2.md`` for the full
# rationale.

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
        """Initialize the proposal generator with empty internal state.

        v10.6.0 PV-02 (D-Q-2 god-function refactor) — composes a
        :class:`devolaflow.feedback_emit.ProposalEmitter` for round-N+1
        dispatch emission. The emitter owns the S-10 4-event lifecycle
        hook chain firing AND the deep-copy + reinforcement merge
        pipeline; this class delegates to it via the
        :meth:`generate_round_dispatch` façade.
        """
        self._state = _ProposalState()
        self._emitter = ProposalEmitter()

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

        Thin façade — delegates to
        :meth:`devolaflow.feedback_emit.ProposalEmitter.emit`.

        V6-01 wiring: stitches :meth:`generate_reinforcement` into the
        dispatch lifecycle so L3 Task Agents receive the reinforcement
        block under ``context.applicable_rules.reinforcement`` on rounds
        ≥ 2. Round 1 is a pure pass-through — the first attempt has no
        prior round to learn from.

        v8.4.4 PV-04 / v9.1.3 PV-03 / v9.4.0 PV-03 wiring: the FINAL
        dispatch payload of every return path is run through the
        lifecycle hook chain (``pre_dispatch`` → ``post_dispatch`` →
        ``pre_handoff`` → ``pre_plugin_invocation``) per Soul Rule S-10.
        Hooks run in permissive mode — see
        :func:`devolaflow.feedback_emit._fire_hook_chain` for the R5
        strict-byte-identical contract.

        v10.6.0 PV-02 (D-Q-2): the deep-copy + reinforcement merge +
        hook chain pipeline now lives on
        :class:`devolaflow.feedback_emit.ProposalEmitter`. This class
        retains :meth:`generate_reinforcement` (which extracts
        :class:`ReinforcementBlock` from a :class:`GateVerdict`) and
        passes it as the ``reinforcement_factory`` callable so the
        v6-01 wiring contract is preserved verbatim.

        The input ``base_dispatch`` is never mutated; a deep copy is
        returned in all cases.
        """
        return self._emitter.emit(
            base_dispatch=base_dispatch,
            verdict=verdict,
            round_num=round_num,
            target_score=target_score,
            severity_floor=severity_floor,
            reinforcement_factory=self.generate_reinforcement,
        )


# ---------------------------------------------------------------------------
# v11.1.0 (PV-04 / W02) — Cascade-gate field population helper
#
# Module-level helper that L0/L1/L2 dispatchers may call BEFORE handing
# a base dispatch to ``ProposalGenerator.generate_round_dispatch``. The
# helper conditionally populates the v11.1.0 PV-04 W01 NEST sub-fields
# under the existing ``gate`` block (per the schema-side wiring in
# ``schemas/lean-dispatch.yaml`` lines 177-210):
#
# * ``gate.cascade_required: bool`` — true when complexity is
#   STANDARD/COMPLEX per ``cascade_requirement(complexity)``;
# * ``gate.cascade_min_layers: int`` — defaults to 4 (the canonical
#   L0 → L1 → L2 → L3 minimum) when cascade is required.
#
# Per Soul Rule S-10: this helper is OPT-IN. Callers that do NOT pass
# the base dispatch through this helper produce dispatches byte-identical
# to the v11.0.3 control — the existing
# ``tests/test_dispatch_emission_runs_hooks.py`` 10/10 R5 strict
# byte-identical contract is preserved BY CONSTRUCTION (the helper
# operates on the BASE dispatch BEFORE ``generate_round_dispatch`` runs;
# the round-N+1 emission path is unchanged).
#
# Per A-2.3 (NEST contract): SIMPLE/TRIVIAL complexity returns the deep
# copy AS-IS — canonical absence-as-default preserves the v9.7.0 layout
# byte-baseline + the 10 historical multi-baseline byte-tests in
# ``tests/test_layout_invariant_multi_baseline.py``.
#
# Source: v11.1.0 PV-04 spec — closes the W02 owned-files manifest;
# pairs with W03 (`gate/scorer.py::validate_cascade_gate_fields` soft
# validator). Strict A-7 enforcement lands at PV-05.
# ---------------------------------------------------------------------------


def populate_cascade_gate_fields(
    base_dispatch: dict[str, Any],
    complexity: str,
) -> dict[str, Any]:
    """Conditionally populate gate.cascade_required + gate.cascade_min_layers.

    v11.1.0 PV-04 — opt-in helper for L0/L1/L2 dispatchers building a
    dispatch payload with explicit complexity. Returns a new dict
    (deep copy of *base_dispatch*) with the cascade sub-fields populated
    under the existing ``gate`` block when complexity is STANDARD/COMPLEX
    (per :func:`devolaflow.skills.change_activation.cascade_requirement`).
    For SIMPLE/TRIVIAL the sub-fields are OMITTED (canonical absence-as-
    default per A-2.3 NEST contract); the returned dict is byte-identical
    to a deepcopy of *base_dispatch*.

    Per S-10: this helper is OPT-IN.
    :meth:`ProposalGenerator.generate_round_dispatch` callers that do
    NOT pass through this helper produce dispatches byte-identical to
    the v11.0.3 control (the existing
    ``tests/test_dispatch_emission_runs_hooks.py`` 10/10 R5 strict
    byte-identical contract is preserved BY CONSTRUCTION — the helper
    operates on the BASE dispatch BEFORE the round-N+1 emission path).

    Args:
      base_dispatch: dispatch payload dict; never mutated.
      complexity: one of TRIVIAL/SIMPLE/STANDARD/COMPLEX.

    Returns:
      Deep copy of *base_dispatch* with ``gate.cascade_required`` and
      ``gate.cascade_min_layers`` populated when cascade is required.
      When the input has no ``gate`` block AND cascade is required, an
      empty ``gate: {}`` dict is created and the cascade sub-fields are
      added to it (mirrors the gate block creation pattern elsewhere in
      feedback flows).

    Raises:
      ValueError: when ``complexity`` is not a recognised
        :data:`devolaflow.skills.change_activation.Complexity` literal —
        re-raised verbatim from :func:`cascade_requirement` per S-5
        (no silent coercion of unknown complexity tiers).
    """
    from devolaflow.skills.change_activation import cascade_requirement

    dispatch = copy.deepcopy(base_dispatch)

    if cascade_requirement(complexity) == "CASCADE_OPTIONAL":
        return dispatch

    gate_block = dispatch.get("gate")
    if not isinstance(gate_block, dict):
        dispatch["gate"] = {}
    dispatch["gate"]["cascade_required"] = True
    dispatch["gate"]["cascade_min_layers"] = 4
    return dispatch


# v11.1.0 PV-05 — Architecture rule A-7 ("Cascade-Depth Invariant for
# Standard+ Dispatches") establishes ``populate_cascade_gate_fields`` as
# the canonical OPT-IN dispatch-payload populator for the cascade NEST
# sub-fields. The v11.1.0 PV-04 placeholder pin tuple
# ``_populate_cascade_gate_fields_dead_api_pins`` was REMOVED in v11.0.5
# PV-05 per cycle plan §3 PV-05 W03 ("dead-API pin cleanup now that A-7
# wires the symbols"); the dead-API detector tracks this helper via the
# explicit allowlist entry
# ``"devolaflow.feedback:populate_cascade_gate_fields"`` in
# ``scripts/detect_dead_apis.py::DEFAULT_ALLOWLIST`` (with the v12.0.0
# STRICT-promotion deferral comment per cycle plan §6). The full
# production wiring lands at v12.0.0 STRICT promotion alongside
# ``validate_cascade_gate_fields`` per W-21 2-cycle deliberation cadence.
# Source: ``.rules/architecture.mdc`` §A-7 + cycle plan §6.


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


# ---------------------------------------------------------------------------
# v10.2.1 (PV-02 — Formal Si-Chip integration) — Dogfood-cycle dispatch wrapper
#
# Closes D-S-2 from `.local/research/v10.2.0_gap_analysis.md` §3.2: prior to
# v10.2.1 the persistent BasicAbility optimisation factory in
# :mod:`devolaflow.si_chip_bridge.runner` (``run_dogfood_cycle``) was reachable
# ONLY via the v9.5.0 PV-04 ``post_skill_edit`` lifecycle hook, gated on
# ``DEVOLAFLOW_SI_CHIP_DEEP=1``. L0/L1 dispatchers had no programmatic entry
# point even though ``skill-optimization`` / ``self-update`` /
# ``nines-assisted`` workflow templates declare ``si-chip`` in
# ``invoked_by_workflows``. This wrapper closes that integration gap.
#
# P1 dispatcher-not-implementer (Soul Rule S-1): the wrapper is a thin
# delegation layer. It does NOT mutate any skill file directly. It invokes
# :func:`devolaflow.si_chip_bridge.runner.run_dogfood_cycle` which orchestrates
# profile + count_tokens + (optional) evaluate. The verdict (APPLY / DEFER) is
# returned to the caller; the caller is responsible for any downstream skill
# edit decision (typically delegated to an L3 Task Agent).
#
# Activation gate: this is a Python API entry point — the workflow stage
# itself opts in by calling the wrapper. The post_skill_edit lifecycle hook
# remains separately gated on ``DEVOLAFLOW_SI_CHIP_DEEP=1`` per the v9.5.0
# DEEP integration contract; the wrapper bypasses that env-flag because
# direct callers are explicit opt-ins by virtue of importing + invoking.
#
# Source: v10.2.0 cycle plan §3 PV-02 owned-files manifest (D-S-2 closure).
# External tool reference: https://github.com/YoRHa-Agents/Si-Chip
# ---------------------------------------------------------------------------


def dispatch_dogfood_cycle(
    workflow_name: str,
    *,
    skill_files: list[str | Path] | None = None,
    runs_dir: Path | str | None = None,
    baseline_dir: Path | str | None = None,
    threshold: float = 0.10,
    work_dir: Path | str | None = None,
) -> Any:
    """Dispatch a Si-Chip dogfood cycle from the L0/L1 workflow surface.

    Bridges the gap between the workflow-stage layer (``skill-optimization``,
    ``self-update``, ``nines-assisted`` templates that declare ``si-chip`` in
    ``invoked_by_workflows``) and the persistent BasicAbility optimisation
    factory implemented in :mod:`devolaflow.si_chip_bridge`. Closes D-S-2 from
    ``.local/research/v10.2.0_gap_analysis.md`` §3.2.

    P1 dispatcher-not-implementer is preserved: this wrapper does NOT
    perform skill edits itself. It invokes
    :func:`devolaflow.si_chip_bridge.runner.run_dogfood_cycle` which
    orchestrates the static profile + token audit + iteration_delta evaluation
    pipeline. APPLY / DEFER verdicts are returned to the caller; downstream
    L3 Task Agents are responsible for any actual skill-file mutation.

    Activation gate (R5 strict):
    - Always available as a Python API.
    - When called from inside the ``post_skill_edit`` lifecycle hook,
      the env flag ``DEVOLAFLOW_SI_CHIP_DEEP=1`` gates auto-invocation.
      Direct callers (this wrapper) bypass the env gate — the workflow
      itself opts in by declaring the dogfood stage.

    Workflow → ability mapping: the ``workflow_name`` argument is passed
    through as the underlying ``ability_name`` for the Si-Chip
    ``profile_static.py`` invocation. DevolaFlow's canonical dogfood
    workflow names (``skill-optimization``, ``self-update``,
    ``nines-assisted``) all map to the same ``"devola-flow"`` ability for
    profiling purposes; this wrapper preserves the verbatim
    ``workflow_name`` so callers retain provenance in the returned
    :class:`SiChipResult.notes` list.

    Multi-file ``skill_files``: when the caller supplies multiple files, only
    the FIRST entry is forwarded as ``skill_md`` to the underlying
    ``run_dogfood_cycle`` call. Multi-file batch dogfooding is on the
    v10.4.0+ roadmap (per gap analysis §5); v10.2.1 ships the integration
    surface, not the batch loop.

    Parameters
    ----------
    workflow_name : str
        Name of the workflow stage requesting the dogfood cycle. Pass-through
        as ``ability_name`` to ``run_dogfood_cycle``. Examples:
        ``"skill-optimization"`` / ``"self-update"`` / ``"nines-assisted"``.
    skill_files : list[str | Path] | None, keyword-only
        Skill files to evaluate. Only the first entry is consumed in v10.2.1;
        when ``None`` or empty, defaults to ``"workflow-system/agent/SKILL.md"``
        (the canonical entry point per the v9.5.0 PV-04 lifecycle precedent).
    runs_dir, baseline_dir : Path | str | None, keyword-only
        Eval directories for the ``aggregate_eval.py`` pass. When either is
        ``None``, ``run_dogfood_cycle`` returns a DEFER verdict with
        ``"evaluate: skipped"`` notes (the expected v10.2.1 PV-02 dogfood
        pass #1 outcome — D-N-1 PV-03 supplies eval data via the NineS
        adapter).
    threshold : float, keyword-only
        Apply/defer threshold; default 0.10 per Si-Chip spec §23.
    work_dir : Path | str | None, keyword-only
        Where intermediate Si-Chip YAML files land. Defaults to
        ``Path.cwd() / ".local" / "dogfood" / __version__`` (v10.2.1 D-S-6
        version-tracking default; supersedes the v9.5.0 hardcoded ``"v9.5.0"``
        literal).

    Returns
    -------
    SiChipResult
        The orchestrated profile + audit + evaluate envelope. Verdict
        accessible via ``result.verdict`` (``ApplyVerdict.APPLY`` /
        ``ApplyVerdict.DEFER``).

    Raises
    ------
    SiChipUnavailable
        Si-Chip not installed (resolver returned None). Callers can
        downgrade to "skip" semantics on this exception per the v9.5.0
        PV-04 lifecycle hook precedent.
    SiChipError
        Si-Chip subprocess failure on a stage that should have succeeded.
    """
    from devolaflow.si_chip_bridge.runner import run_dogfood_cycle

    if work_dir is None:
        from devolaflow import __version__

        work_dir = Path.cwd() / ".local" / "dogfood" / __version__
    elif not isinstance(work_dir, Path):
        work_dir = Path(work_dir)

    files = skill_files or ["workflow-system/agent/SKILL.md"]
    primary_skill = Path(files[0])

    runs_dir_resolved = Path(runs_dir) if isinstance(runs_dir, str) else runs_dir
    baseline_dir_resolved = Path(baseline_dir) if isinstance(baseline_dir, str) else baseline_dir

    return run_dogfood_cycle(
        ability_name=workflow_name,
        skill_md=primary_skill,
        runs_dir=runs_dir_resolved,
        baseline_dir=baseline_dir_resolved,
        threshold=threshold,
        work_dir=work_dir,
    )
