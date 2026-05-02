"""Async dispatch executor for L2-wave parallel L3 task dispatch.

v9.3.0 PV-05 — RE-TARGETED per `.local/research/v9.3.0_perf_research.md`
§4.3 (echoed in the v9.3.0 gap analysis §3.4). The original cycle-plan
PV-05 spec proposed a `ThreadPoolExecutor` for `run_hooks` parallelism;
the PV-01 cProfile harness measured `run_hooks(pre_dispatch)` at 9.2 µs
per call — *microseconds* — which is 5-10× SMALLER than the
`ThreadPoolExecutor.submit` overhead. The fix is empirically
anti-improvement at the per-dispatch level.

The high-leverage parallelism opportunity surfaced by the same profile
data is the L2-wave fan-out: when a wave declares 4 parallel tasks,
the current synchronous dispatcher pays
``sum(per-task-dispatch-prep)`` of latency where parallel asyncio
would pay only ``max(per-task-dispatch-prep)``. With each L3 task's
``select_context`` averaging 200 ms pre-PV-03 (now ~2 ms post-PV-03 —
see ``benchmarks/devolaflow_context/baselines/v9.3.0_latency.json``),
the L2-wave saving compounds with PV-03's LRU cache: a 4-task wave
dispatch that pre-PV-03 paid 4 × 200 ms = 800 ms in serial dispatch
prep now pays 4 × 2 ms = 8 ms in serial OR ``max(2 ms) = 2 ms`` in
parallel. The post-PV-03 absolute saving per wave is small (6 ms),
but the architectural pattern unlocks future ``asyncio.gather``
opportunities at every layer of the dispatcher (e.g., v9.7.0 PV-03
will wire the executor into the L0→L1 boundary where each L1 stage
performs its own `select_context` + advisor + memory_router probe).

P1 invariant — Dispatcher-Not-Implementer (Soul Rule S-1):
:class:`AsyncDispatchExecutor` MUST NOT itself perform any work. It
only schedules CALLABLES provided by the caller; the actual L3 Task
work happens inside each callable's own context (typically a
``Task`` tool invocation or a cached `select_context` call). The
executor is a pure orchestration layer — it has zero domain
knowledge of compression, dispatch payload validation, gate scoring,
or any other DevolaFlow primitive. This is verified at test time by
:func:`tests.test_async_dispatch_executor.test_executor_calls_only_provided_callables`.

Library-only landing (no env flag, no auto-wire):
v9.3.0 PV-05 ships the executor as a pure library — no dispatcher
auto-wires it. Future PVs (v9.7.0 PV-03 telegraphed) will wire the
executor into the L0/L1 dispatch loop. Until then, callers explicitly
opt in by instantiating ``AsyncDispatchExecutor()`` and calling
:meth:`AsyncDispatchExecutor.dispatch_parallel`. The opt-in IS the
act of calling — there is no env flag to set, no monkey-patch
hazard, no R5 strict opt-out path to author. Per W-20 §3, no NEW
env flag is justified at this PV's scope.

Public API:

* :class:`AsyncDispatchExecutor` — orchestrator with two execution
  modes (sequential fallback + asyncio.gather parallel).
* :class:`TaskOutcome` — typed result envelope per dispatched task.
* :class:`ExecutorError` — raised for invalid construction args.

Source: v9.3.0 PV-05 spec — closes D-E-3 (4-parallel-task L2 wave
currently pays ``4 × 220 ms = 880 ms`` of dispatch prep) from the
PV-01 gap analysis §1.4.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

__all__ = [
    "AsyncDispatchExecutor",
    "DEFAULT_MAX_CONCURRENCY",
    "ExecutorError",
    "TaskCallable",
    "TaskOutcome",
]


DEFAULT_MAX_CONCURRENCY: int = 4
"""Default upper bound on simultaneous in-flight L3 tasks.

Picked to match the canonical 4-parallel-task wave shape documented in
``workflow-system/agent/SKILL.md`` §"Wave Dispatch". A future PV that
wires the executor into a dispatcher MAY override via the
``max_concurrency`` constructor arg or via a future env flag; until
that landing the constant IS the contract."""


# Type alias for the per-task callable. Accepts either a sync callable
# returning a value OR an async callable returning an awaitable. The
# executor handles both branches in :meth:`dispatch_parallel` via
# :func:`asyncio.iscoroutinefunction` + :func:`asyncio.to_thread`.
TaskCallable = Callable[[], Any] | Callable[[], Awaitable[Any]]


class ExecutorError(ValueError):
    """Raised on invalid :class:`AsyncDispatchExecutor` construction.

    Inherits :class:`ValueError` (rather than a fresh base) so callers
    can ``except ValueError`` and catch both this and the underlying
    ``int(s)`` raises. S-5 — the executor never silently coerces a bad
    ``max_concurrency`` value to a default.
    """


@dataclass
class TaskOutcome:
    """Result envelope for a single dispatched task.

    Either ``result`` is set (and ``exception`` is ``None``), or
    ``exception`` is set (and ``result`` is ``None``). The
    ``succeeded`` boolean is the canonical predicate — callers should
    branch on it rather than testing ``exception is not None`` so the
    contract stays stable if a future PV adds further failure-mode
    enums.

    Per S-5 (no silent failures), :meth:`AsyncDispatchExecutor.dispatch_parallel`
    captures every task's exception into the outcome and continues the
    other tasks; the caller decides whether to escalate per P4 (Bounded
    Retry — escalate up the layer hierarchy on any blocker-level
    failure).
    """

    task_id: str
    succeeded: bool
    result: Any = None
    exception: BaseException | None = None


class AsyncDispatchExecutor:
    """Orchestrate parallel L3 Task dispatches via :func:`asyncio.gather`.

    Two execution modes:

    * :meth:`dispatch_sequential` — sync fallback path. Runs each
      task callable in order, captures per-task exceptions, returns
      a :class:`TaskOutcome` per task. Use when async dispatch is
      unavailable (e.g., the caller is itself running inside an
      asyncio loop and cannot `asyncio.run` recursively) or when the
      wave is so small that parallelism wouldn't pay for the loop
      setup.

    * :meth:`dispatch_parallel` — asyncio fast path. Wraps every
      task in a :class:`asyncio.Semaphore`-bounded coroutine and
      gathers them via :func:`asyncio.gather`. The semaphore caps
      concurrency at ``max_concurrency``; sync callables run via
      :func:`asyncio.to_thread` so a slow sync call doesn't block
      the event loop.

    P1 invariant: the executor schedules callables. It does NOT
    inspect them, mutate them, or replace them with a "library
    implementation". This invariant is the entire reason
    :class:`TaskOutcome.result` is typed ``Any`` — the executor
    cannot peek at what the callable returned.
    """

    def __init__(self, max_concurrency: int | None = None) -> None:
        """Construct an executor.

        Args:
          max_concurrency: Upper bound on simultaneous in-flight tasks
            in :meth:`dispatch_parallel`. Defaults to
            :data:`DEFAULT_MAX_CONCURRENCY` (4). Must be >= 1 — a
            value of 0 or negative raises :class:`ExecutorError`
            because it would deadlock the semaphore.

        Raises:
          ExecutorError: when ``max_concurrency`` < 1.
        """
        if max_concurrency is None:
            max_concurrency = DEFAULT_MAX_CONCURRENCY
        if max_concurrency < 1:
            raise ExecutorError(
                f"AsyncDispatchExecutor.max_concurrency must be >= 1, got {max_concurrency!r}"
            )
        self._max_concurrency = max_concurrency

    @property
    def max_concurrency(self) -> int:
        """Read-only accessor for the configured concurrency cap."""
        return self._max_concurrency

    # ------------------------------------------------------------------
    # Sequential mode — sync fallback.
    # ------------------------------------------------------------------

    def dispatch_sequential(
        self,
        tasks: list[tuple[str, TaskCallable]],
    ) -> list[TaskOutcome]:
        """Run each ``(task_id, callable)`` tuple synchronously, in order.

        Per S-5, exceptions are captured into the per-task outcome
        rather than aborting the wave. The next task runs on the next
        loop iteration regardless of the previous task's failure. The
        caller is responsible for surfacing failures via the per-PV
        gate (typically by inspecting ``[t for t in outcomes if not
        t.succeeded]``).

        For async callables the sequential path runs them via
        :func:`asyncio.run` per task — which has loop-init cost but
        keeps the contract uniform regardless of callable shape. Use
        :meth:`dispatch_parallel` when you have multiple async
        callables to amortise the loop cost.
        """
        outcomes: list[TaskOutcome] = []
        for task_id, fn in tasks:
            outcomes.append(self._run_one_sync(task_id, fn))
        return outcomes

    @staticmethod
    def _run_one_sync(task_id: str, fn: TaskCallable) -> TaskOutcome:
        """Internal: run a single task synchronously, capture exception."""
        try:
            if inspect.iscoroutinefunction(fn):  # noqa: SIM108  (comment-bearing branch)
                # Async callable invoked from sync context — pay the
                # loop-init cost per call. Callers with many async
                # callables should use dispatch_parallel instead.
                result = asyncio.run(fn())  # type: ignore[arg-type]
            else:
                result = fn()
            return TaskOutcome(task_id=task_id, succeeded=True, result=result)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "AsyncDispatchExecutor: task %r raised %s; captured into TaskOutcome",
                task_id,
                exc,
            )
            return TaskOutcome(task_id=task_id, succeeded=False, exception=exc)

    # ------------------------------------------------------------------
    # Parallel mode — asyncio.gather fast path.
    # ------------------------------------------------------------------

    def dispatch_parallel(
        self,
        tasks: list[tuple[str, TaskCallable]],
    ) -> list[TaskOutcome]:
        """Run tasks via :func:`asyncio.gather`, bounded by ``max_concurrency``.

        Returns a list of :class:`TaskOutcome` matching the input order
        — ``outcomes[i]`` corresponds to ``tasks[i]``. Failed tasks
        carry their exception in ``outcome.exception`` and never raise
        out of this method (S-5 — the executor never silently swallows
        but also never short-circuits the wave on first failure).

        Empty ``tasks`` is a valid no-op; returns ``[]`` immediately
        without spawning a loop.
        """
        if not tasks:
            return []
        return asyncio.run(self._dispatch_parallel_async(tasks))

    async def _dispatch_parallel_async(
        self,
        tasks: list[tuple[str, TaskCallable]],
    ) -> list[TaskOutcome]:
        """Internal coroutine: gather + semaphore.

        Each task runs inside a context-managed semaphore acquire so
        no more than ``max_concurrency`` tasks are in flight at once.
        Sync callables go through :func:`asyncio.to_thread` so the
        event loop is not blocked.
        """
        sem = asyncio.Semaphore(self._max_concurrency)

        async def run_one(task_id: str, fn: TaskCallable) -> TaskOutcome:
            async with sem:
                try:
                    if inspect.iscoroutinefunction(fn):
                        result = await fn()  # type: ignore[misc]
                    else:
                        result = await asyncio.to_thread(fn)  # type: ignore[arg-type]
                    return TaskOutcome(task_id=task_id, succeeded=True, result=result)
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "AsyncDispatchExecutor: parallel task %r raised %s; captured",
                        task_id,
                        exc,
                    )
                    return TaskOutcome(task_id=task_id, succeeded=False, exception=exc)

        return await asyncio.gather(*(run_one(tid, fn) for tid, fn in tasks))
