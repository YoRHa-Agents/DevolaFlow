"""Wave-execution + dogfood-cycle dispatch wrappers — extracted from ``feedback.py``.

v14.5.0 (ADR-006 / gap G-025 module split) — code extracted VERBATIM from
``feedback.py`` (``dispatch_wave_tasks`` + ``dispatch_dogfood_cycle``) per
``.local/research/adr/v15-ADR-006-scorer-selector-module-split.md`` decision
item 3 ("``dispatch_wave_tasks`` / ``dispatch_dogfood_cycle`` move to a
dispatch module").

Shim tracking table (per the ADR's "tracking table needed in the dispatch
module docstring" clause). Every OLD path below keeps working PERMANENTLY
(lifetime >= v16.0.0, revisit then) via identity-preserving module-level
re-exports; S-10-named paths never expire:

    Old import path                                         New owner module
    ------------------------------------------------------- -------------------------------
    devolaflow.feedback.dispatch_wave_tasks                  devolaflow.dispatch
    devolaflow.feedback.dispatch_dogfood_cycle               devolaflow.dispatch
    devolaflow.feedback.populate_cascade_gate_fields         devolaflow.gate.cascade
                                                             (S-10 / lean-dispatch.yaml-named
                                                             — shim permanent)
    devolaflow.feedback.populate_intra_task_convergence      devolaflow.gate.cascade
    devolaflow.feedback.INTRA_TASK_CONVERGENCE_TASK_TYPES    devolaflow.gate.cascade
    devolaflow.feedback.INTRA_TASK_MAX_ROUNDS_DEFAULT        devolaflow.gate.cascade
    devolaflow.gate.scorer.CascadeViolationError             devolaflow.gate.cascade
    devolaflow.gate.scorer.validate_cascade_gate_fields      devolaflow.gate.cascade
    devolaflow.gate.scorer.IntraTaskConvergenceViolationError devolaflow.gate.cascade
    devolaflow.gate.scorer.validate_intra_task_convergence_fields devolaflow.gate.cascade
    devolaflow.gate.scorer.evaluate_ladder                   devolaflow.gate.ladder
    devolaflow.gate.scorer.is_verification_ladder_active     devolaflow.gate.ladder
    devolaflow.gate.scorer.VERIFICATION_LADDER_ENV_FLAG      devolaflow.gate.ladder
    devolaflow.gate.scorer.RungChecker                       devolaflow.gate.ladder
    devolaflow.gate.scorer.evaluate_acceptance_criteria_v2   devolaflow.gate.acceptance_v2
    devolaflow.gate.scorer.aggregate_criterion_verdicts      devolaflow.gate.acceptance_v2
    devolaflow.gate.scorer.CommandRunner / CommandRunResult  devolaflow.gate.acceptance_v2
    devolaflow.gate.scorer.METRIC_KIND_{COVERAGE,LINT,NUMBER} devolaflow.gate.acceptance_v2
    devolaflow.task_adaptive_selector.select_agents_md_slice devolaflow.agents_md_slice
    devolaflow.task_adaptive_selector.count_agents_md_rules  devolaflow.agents_md_slice
    devolaflow.task_adaptive_selector.main                   devolaflow.selector_cli

Pinned by ``tests/test_module_split_shims.py``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

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


def _resolve_task_timeout(task: dict[str, Any]) -> float | None:
    """Resolve the enforced ``timeout_seconds`` ceiling for one task spec.

    v15.0.0 (G-038 flip 1) — the v12.2.0 PV-04 ``asyncio.wait_for``
    timeout machinery graduates from opt-in to DEFAULT-ON at the wave
    dispatch surface, fed by the v14.5.0 G-037 ``timeout_seconds``
    auto-population:

    1. Task spec carries an explicit ``timeout_seconds`` key:
       * ``None`` → documented OPT-OUT — the task runs with NO timeout
         (the pre-v15.0.0 behaviour, per task).
       * numeric → enforced verbatim (the v14.5.0
         ``select_context``-populated value or an operator override).
    2. Key absent → :func:`devolaflow.task_adaptive_selector.
       default_timeout_for` on the task's ``type`` / ``task_type``
       field (SKILL.md §"Subagent Hang Prevention" per-class budgets;
       unknown / missing types resolve to the 7200 s fail-safe
       ceiling).

    No env flag in either direction (W-20 — the opt-out REUSES the
    existing ``timeout_seconds`` config surface).
    """
    from devolaflow.task_adaptive_selector import default_timeout_for

    if "timeout_seconds" in task:
        explicit = task["timeout_seconds"]
        if explicit is None:
            return None
        return float(explicit)
    task_type = task.get("type") or task.get("task_type") or ""
    return float(default_timeout_for(task_type))


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

    Timeout enforcement — DEFAULT-ON since v15.0.0 (G-038 flip 1):
    every task gets an ``asyncio.wait_for`` ceiling resolved by
    :func:`_resolve_task_timeout` (explicit per-task ``timeout_seconds``
    → its task-type class default → the 7200 s fail-safe). A breach
    cancels the task and surfaces ``TaskOutcome(succeeded=False,
    exception=TimeoutError)`` per the v12.2.0 PV-04 contract. Opt-out:
    set ``timeout_seconds: null`` explicitly on the task spec (the
    existing v14.5.0 config knob — no new env flag per W-20).

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
    timeouts: dict[str, float] = {}
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
        timeout = _resolve_task_timeout(task)
        if timeout is not None:
            timeouts[task_id] = timeout

    executor = AsyncDispatchExecutor(max_concurrency=max_concurrency)
    if mode == "parallel" and len(callables) > 1:
        return executor.dispatch_parallel(callables, timeouts=timeouts)
    return executor.dispatch_sequential(callables, timeouts=timeouts)


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
