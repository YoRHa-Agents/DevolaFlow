"""Wave-execution dispatch wrappers — extracted from ``feedback.py``.

v14.5.0 (ADR-006 / gap G-025 module split) — code extracted VERBATIM from
``feedback.py`` (``dispatch_wave_tasks``) per
``docs/cycle-archive/adr/v15-ADR-006-scorer-selector-module-split.md`` decision
item 3 ("``dispatch_wave_tasks`` move to a dispatch module").

Shim tracking table (per the ADR's "tracking table needed in the dispatch
module docstring" clause). v17.0.0 shim retirement (the ADR's "revisit at
v16.0.0+" clause discharged): every ADR-006 re-export shim EXCEPT the
S-10/schema-named row below was retired in v17.0.0 after all in-repo call
sites migrated to the owner modules (``devolaflow.gate.cascade`` /
``devolaflow.gate.ladder`` / ``devolaflow.gate.acceptance_v2`` /
``devolaflow.dispatch`` / ``devolaflow.agents_md_slice`` /
``devolaflow.selector_cli``):

    Old import path                                  Status
    ------------------------------------------------ ------------------------------
    devolaflow.feedback.populate_cascade_gate_fields PERMANENT — S-10 /
                                                     lean-dispatch.yaml name this
                                                     path verbatim; survives the
                                                     v17 shim retirement. Owner:
                                                     devolaflow.gate.cascade.
    (every other ADR-006 shim row)                   retired v17.0.0 after
                                                     call-site migration — import
                                                     from the owner modules above.

Pinned by ``tests/test_module_split_shims.py``.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# v9.7.0 (PV-03 — Performance Overhaul #2) — Auto-wire AsyncDispatchExecutor
# for L1-wave parallel L2 dispatches.
#
# The v9.3.0 PV-05 ``AsyncDispatchExecutor`` shipped library-only — the
# class machinery was complete but no production caller actually invoked
# it. v9.7.0 PV-03 closes the gap by wiring it into a public dispatch
# entry point at the L1-wave boundary.
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
# schedules the caller-provided callables. The actual L2 Task work
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


class _WaveTimeouts(dict[str, float]):
    """Timeout mapping carrying the explicit-stop contract for each task."""

    def __init__(self, values: dict[str, float], explicit_task_ids: set[str]) -> None:
        super().__init__(values)
        self.explicit_task_ids = frozenset(explicit_task_ids)


def _prepare_wave_tasks(
    wave_definition: dict[str, Any],
    dispatch_factory: Any,
    max_concurrency: int | None,
) -> tuple[str, int, list[tuple[str, Any]], dict[str, float]]:
    """Validate and prepare the common synchronous/async wave inputs."""
    from devolaflow.agent_workspace.dispatch_executor import (
        DEFAULT_MAX_CONCURRENCY,
        ExecutorError,
    )

    if not isinstance(wave_definition, dict):
        raise TypeError(f"wave_definition must be a dict, got {type(wave_definition).__name__}")
    if not callable(dispatch_factory):
        raise TypeError(f"dispatch_factory must be callable, got {type(dispatch_factory).__name__}")

    tasks_raw = wave_definition.get("tasks", [])
    if not isinstance(tasks_raw, list):
        raise TypeError(f"wave_definition['tasks'] must be a list, got {type(tasks_raw).__name__}")

    sync_barrier = wave_definition.get("sync_barrier") or {}
    if not isinstance(sync_barrier, dict):
        sync_barrier = {}
    mode = sync_barrier.get("mode", "all")

    if max_concurrency is None:
        configured = sync_barrier.get("max_parallelism")
        max_concurrency = DEFAULT_MAX_CONCURRENCY if configured is None else configured

    if max_concurrency < 1:
        raise ExecutorError(
            f"AsyncDispatchExecutor.max_concurrency must be >= 1, got {max_concurrency!r}"
        )
    if not tasks_raw:
        return mode, max_concurrency, [], {}

    callables: list[tuple[str, Any]] = []
    timeouts: dict[str, float] = {}
    explicit_timeout_ids: set[str] = set()
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
            if "timeout_seconds" in task:
                explicit_timeout_ids.add(task_id)

    return mode, max_concurrency, callables, _WaveTimeouts(timeouts, explicit_timeout_ids)


def dispatch_wave_tasks(
    wave_definition: dict[str, Any],
    dispatch_factory: Any,
    *,
    max_concurrency: int | None = None,
) -> list[Any]:
    """Dispatch an L1 wave's L2 tasks via :class:`AsyncDispatchExecutor`.

    Auto-wires v9.3.0 PV-05's library-only :class:`AsyncDispatchExecutor`
    into the L1-wave dispatch path per v9.7.0 PV-03. Inspects
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
    from devolaflow.agent_workspace.dispatch_executor import AsyncDispatchExecutor

    mode, resolved_concurrency, callables, timeouts = _prepare_wave_tasks(
        wave_definition, dispatch_factory, max_concurrency
    )
    if not callables:
        return []

    executor = AsyncDispatchExecutor(max_concurrency=resolved_concurrency)
    if mode == "parallel" and len(callables) > 1:
        return executor.dispatch_parallel(callables, timeouts=timeouts)
    return executor.dispatch_sequential(callables, timeouts=timeouts)


async def async_dispatch_wave_tasks(
    wave_definition: dict[str, Any],
    dispatch_factory: Any,
    *,
    max_concurrency: int | None = None,
) -> list[Any]:
    """Dispatch a wave from an active event loop.

    This is the async companion to :func:`dispatch_wave_tasks`.  Await it
    instead of calling the synchronous wrapper from an active event loop;
    it does not use nested :func:`asyncio.run` calls.  Validation,
    concurrency resolution, timeout handling, and ``TaskOutcome`` ordering
    match the synchronous wrapper.
    """
    from devolaflow.agent_workspace.dispatch_executor import AsyncDispatchExecutor

    mode, resolved_concurrency, callables, timeouts = _prepare_wave_tasks(
        wave_definition, dispatch_factory, max_concurrency
    )
    if not callables:
        return []

    executor = AsyncDispatchExecutor(max_concurrency=resolved_concurrency)
    if mode == "parallel" and len(callables) > 1:
        return await executor.dispatch_parallel_async(callables, timeouts=timeouts)
    return await executor.dispatch_sequential_async(callables, timeouts=timeouts)
