"""Async dispatch executor for L1-wave parallel L2 task dispatch.

v9.3.0 PV-05 — RE-TARGETED per `.local/research/v9.3.0_perf_research.md`
§4.3 (echoed in the v9.3.0 gap analysis §3.4). The original cycle-plan
PV-05 spec proposed a `ThreadPoolExecutor` for `run_hooks` parallelism;
the PV-01 cProfile harness measured `run_hooks(pre_dispatch)` at 9.2 µs
per call — *microseconds* — which is 5-10× SMALLER than the
`ThreadPoolExecutor.submit` overhead. The fix is empirically
anti-improvement at the per-dispatch level.

The high-leverage parallelism opportunity surfaced by the same profile
data is the L1-wave fan-out: when a wave declares 4 parallel tasks,
the current synchronous dispatcher pays
``sum(per-task-dispatch-prep)`` of latency where parallel asyncio
would pay only ``max(per-task-dispatch-prep)``. With each L2 task's
``select_context`` averaging 200 ms pre-PV-03 (now ~2 ms post-PV-03 —
see the archived v9.3.0 latency evidence under
``docs/cycle-archive/v15.2.0/``), the L1-wave saving compounds with
PV-03's LRU cache: a 4-task wave
dispatch that pre-PV-03 paid 4 × 200 ms = 800 ms in serial dispatch
prep now pays 4 × 2 ms = 8 ms in serial OR ``max(2 ms) = 2 ms`` in
parallel. The post-PV-03 absolute saving per wave is small (6 ms),
but the architectural pattern unlocks future ``asyncio.gather``
opportunities at every layer of the dispatcher (e.g., v9.7.0 PV-03
will wire the executor into the L0→L1 boundary where each L1 stage
performs its own `select_context` + advisor + memory_router probe).

P1 invariant — Dispatcher-Not-Implementer (Soul Rule S-1):
:class:`AsyncDispatchExecutor` MUST NOT itself perform any work. It
only schedules CALLABLES provided by the caller; the actual L2 Task
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

Source: v9.3.0 PV-05 spec — closes D-E-3 (4-parallel-task L1 wave
currently pays ``4 × 220 ms = 880 ms`` of dispatch prep) from the
PV-01 gap analysis §1.4.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import multiprocessing
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
"""Default upper bound on simultaneous in-flight L2 tasks.

Picked to match the canonical 4-parallel-task wave shape documented in
``workflow-system/agent/SKILL.md`` §"Wave Dispatch". v17.0.0 R5
(D-R5-1): construction with ``max_concurrency=None`` now resolves the
default through ``devolaflow.harness.capacity.capacity_profile()``
(``context_profiles.yaml#meta.capacity.max_concurrency``, valid 1..8).
This constant stays the pinned FALLBACK default — byte-equal to the
dark-config value, asserted by
``tests/test_async_dispatch_executor.py::test_executor_default_max_concurrency_is_four``
— and MUST remain equal to the ``CapacityProfile.max_concurrency``
dataclass default (the A-5 owner of the configurable value)."""


# Type alias for the per-task callable. Accepts either a sync callable
# returning a value OR an async callable returning an awaitable. The
# executor handles both branches in :meth:`dispatch_parallel` via
# :func:`asyncio.iscoroutinefunction` + :func:`asyncio.to_thread`.
TaskCallable = Callable[[], Any] | Callable[[], Awaitable[Any]]

_PROCESS_CLEANUP_TIMEOUT_SECONDS = 1.0
_PROCESS_RESULT_POLL_SECONDS = 0.1


def _process_task_callable(fn: TaskCallable, connection: Any) -> None:
    """Run a fork-isolated sync callable and send its explicit outcome."""
    try:
        result = fn()  # type: ignore[misc]
        message = ("result", result)
    except BaseException as exc:  # noqa: BLE001
        message = ("exception", exc)

    try:
        connection.send(message)
    except BaseException as transport_error:  # noqa: BLE001
        # A result or exception that cannot cross the process boundary is
        # still reported explicitly rather than becoming a silent child crash.
        try:
            connection.send(
                (
                    "exception",
                    RuntimeError(
                        f"timed sync callable produced an unserializable outcome: {transport_error}"
                    ),
                )
            )
        except BaseException:
            raise
    finally:
        connection.close()


def _run_sync_in_process(fn: TaskCallable, timeout: float) -> Any:
    """Run a timed sync callable in a child process and stop it on timeout."""
    if "fork" not in multiprocessing.get_all_start_methods():
        raise ExecutorError(
            "timeout-sensitive synchronous dispatch requires a fork-capable platform; "
            "a non-stopping thread fallback is not supported"
        )

    context = multiprocessing.get_context("fork")
    parent_connection, child_connection = context.Pipe(duplex=False)
    process = context.Process(target=_process_task_callable, args=(fn, child_connection))
    process.daemon = True
    try:
        process.start()
    except (OSError, RuntimeError) as exc:
        child_connection.close()
        parent_connection.close()
        raise ExecutorError(f"could not start isolated timed task process: {exc}") from exc
    child_connection.close()

    try:
        process.join(timeout)
        if process.is_alive():
            process.terminate()
            process.join(_PROCESS_CLEANUP_TIMEOUT_SECONDS)
            if process.is_alive() and hasattr(process, "kill"):
                process.kill()
                process.join(_PROCESS_CLEANUP_TIMEOUT_SECONDS)
            raise TimeoutError(f"task exceeded timeout of {timeout:.3f}s")

        if not parent_connection.poll(_PROCESS_RESULT_POLL_SECONDS):
            raise ExecutorError(
                "isolated timed task exited without returning an outcome "
                f"(exit code {process.exitcode!r})"
            )
        try:
            status, payload = parent_connection.recv()
        except (EOFError, OSError) as exc:
            raise ExecutorError("isolated timed task outcome could not be read") from exc
        if status == "result":
            return payload
        if status == "exception":
            if isinstance(payload, Exception):
                raise payload
            raise RuntimeError(f"isolated timed task raised {payload!r}")
        raise ExecutorError(f"isolated timed task returned unknown outcome {status!r}")
    finally:
        parent_connection.close()
        if process.is_alive():
            process.terminate()
            process.join(_PROCESS_CLEANUP_TIMEOUT_SECONDS)
        if not process.is_alive():
            process.close()


def _should_isolate_sync_task(timeouts: dict[str, float] | None, task_id: str) -> bool:
    """Resolve whether a wave marks this task's timeout as stop-sensitive."""
    explicit_task_ids = getattr(timeouts, "explicit_task_ids", None)
    return explicit_task_ids is None or task_id in explicit_task_ids


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
    """Orchestrate parallel L2 Task dispatches via :func:`asyncio.gather`.

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
            in :meth:`dispatch_parallel`. ``None`` resolves through
            ``meta.capacity.max_concurrency`` (D-R5-1), which is
            :data:`DEFAULT_MAX_CONCURRENCY` (4) when the config key is
            absent — the shipped dark default. Must be >= 1 — a
            value of 0 or negative raises :class:`ExecutorError`
            because it would deadlock the semaphore.

        Raises:
          ExecutorError: when ``max_concurrency`` < 1.
        """
        if max_concurrency is None:
            # Import at call boundary: harness.telemetry imports
            # agent_workspace.layers, so a module-level import here would
            # create an agent_workspace ↔ harness init cycle.
            from devolaflow.harness.capacity import capacity_profile

            max_concurrency = capacity_profile().max_concurrency
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
        *,
        timeouts: dict[str, float] | None = None,
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

        v12.2.0 PV-04 — per-task ``timeouts`` map. Optional dict mapping
        ``task_id -> seconds``; tasks whose execution exceeds the budget
        are cancelled and surface ``TaskOutcome(succeeded=False,
        exception=asyncio.TimeoutError)``. Tasks absent from the map
        run without a timeout (preserves v9.3.0 byte-identical behaviour
        for every caller that does NOT pass the kwarg — the runtime
        contract per CHANGELOG.md §v12.1.0 telegraph "deferred to v12.2.0+"
        closure). Async callables route through :func:`asyncio.wait_for`;
        timed sync callables run in a child process terminated on timeout.
        The library remains opt-in: no env flag, no auto-wire (per the
        v9.3.0 PV-05 "library-only landing" discipline).
        """
        outcomes: list[TaskOutcome] = []
        for task_id, fn in tasks:
            timeout = (timeouts or {}).get(task_id)
            outcomes.append(
                self._run_one_sync(
                    task_id,
                    fn,
                    timeout=timeout,
                    isolate_sync=_should_isolate_sync_task(timeouts, task_id),
                )
            )
        return outcomes

    @staticmethod
    def _run_one_sync(
        task_id: str,
        fn: TaskCallable,
        *,
        timeout: float | None = None,
        isolate_sync: bool = True,
    ) -> TaskOutcome:
        """Internal: run a single task synchronously, capture exception."""
        try:
            if timeout is not None:
                # v12.2.0 PV-04 — async callables use `wait_for`; sync
                # callables use a process so timeout stops underlying work.
                if inspect.iscoroutinefunction(fn):
                    result = asyncio.run(asyncio.wait_for(fn(), timeout=timeout))  # type: ignore[arg-type]
                elif isolate_sync:
                    result = _run_sync_in_process(fn, timeout)
                else:
                    result = asyncio.run(
                        asyncio.wait_for(asyncio.to_thread(fn), timeout=timeout)  # type: ignore[arg-type]
                    )
            elif inspect.iscoroutinefunction(fn):  # noqa: SIM108  (comment-bearing branch)
                # Async callable invoked from sync context — pay the
                # loop-init cost per call. Callers with many async
                # callables should use dispatch_parallel instead.
                result = asyncio.run(fn())  # type: ignore[arg-type]
            else:
                result = fn()
            return TaskOutcome(task_id=task_id, succeeded=True, result=result)
        except TimeoutError as exc:
            # asyncio.TimeoutError is an alias for builtin TimeoutError on
            # 3.11+; capture explicitly so the WARNING log distinguishes
            # the timeout breach from a generic exception (S-5 explicit
            # error-state).
            logger.warning(
                "AsyncDispatchExecutor: task %r exceeded timeout %.3fs; captured into TaskOutcome",
                task_id,
                timeout if timeout is not None else -1.0,
            )
            return TaskOutcome(task_id=task_id, succeeded=False, exception=exc)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "AsyncDispatchExecutor: task %r raised %s; captured into TaskOutcome",
                task_id,
                exc,
            )
            return TaskOutcome(task_id=task_id, succeeded=False, exception=exc)

    async def dispatch_sequential_async(
        self,
        tasks: list[tuple[str, TaskCallable]],
        *,
        timeouts: dict[str, float] | None = None,
    ) -> list[TaskOutcome]:
        """Run tasks in order without creating a nested event loop."""
        outcomes: list[TaskOutcome] = []
        explicit_task_ids = getattr(timeouts, "explicit_task_ids", None)
        for task_id, fn in tasks:
            outcomes.append(
                await self._run_one_async(
                    task_id,
                    fn,
                    (timeouts or {}).get(task_id),
                    isolate_sync=(explicit_task_ids is None or task_id in explicit_task_ids),
                )
            )
        return outcomes

    @staticmethod
    async def _run_one_async(
        task_id: str,
        fn: TaskCallable,
        timeout: float | None,
        *,
        isolate_sync: bool = True,
    ) -> TaskOutcome:
        """Run one task from an already-running event loop."""
        try:
            if inspect.iscoroutinefunction(fn):
                coro = fn()  # type: ignore[misc]
                result = (
                    await asyncio.wait_for(coro, timeout=timeout)
                    if timeout is not None
                    else await coro
                )
            elif timeout is not None and isolate_sync:
                result = await asyncio.to_thread(_run_sync_in_process, fn, timeout)
            elif timeout is not None:
                result = await asyncio.wait_for(asyncio.to_thread(fn), timeout=timeout)
            else:
                result = await asyncio.to_thread(fn)
            return TaskOutcome(task_id=task_id, succeeded=True, result=result)
        except TimeoutError as exc:
            logger.warning(
                "AsyncDispatchExecutor: task %r exceeded timeout %.3fs; captured into TaskOutcome",
                task_id,
                timeout if timeout is not None else -1.0,
            )
            return TaskOutcome(task_id=task_id, succeeded=False, exception=exc)
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
        *,
        timeouts: dict[str, float] | None = None,
    ) -> list[TaskOutcome]:
        """Run tasks via :func:`asyncio.gather`, bounded by ``max_concurrency``.

        Returns a list of :class:`TaskOutcome` matching the input order
        — ``outcomes[i]`` corresponds to ``tasks[i]``. Failed tasks
        carry their exception in ``outcome.exception`` and never raise
        out of this method (S-5 — the executor never silently swallows
        but also never short-circuits the wave on first failure).

        Empty ``tasks`` is a valid no-op; returns ``[]`` immediately
        without spawning a loop.

        v12.2.0 PV-04 — per-task ``timeouts`` map. Optional dict mapping
        ``task_id -> seconds``; tasks whose execution exceeds the budget
        are cancelled and surface ``TaskOutcome(succeeded=False,
        exception=asyncio.TimeoutError)``. Tasks absent from the map
        run without a timeout (preserves v9.3.0 byte-identical behaviour
        for every caller that does NOT pass the kwarg — see the
        :meth:`dispatch_sequential` docstring for the rollout discipline).
        """
        if not tasks:
            return []
        return asyncio.run(self.dispatch_parallel_async(tasks, timeouts=timeouts))

    async def dispatch_parallel_async(
        self,
        tasks: list[tuple[str, TaskCallable]],
        *,
        timeouts: dict[str, float] | None = None,
    ) -> list[TaskOutcome]:
        """Run parallel tasks from an already-running event loop."""
        if not tasks:
            return []
        return await self._dispatch_parallel_async(tasks, timeouts or {})

    async def _dispatch_parallel_async(
        self,
        tasks: list[tuple[str, TaskCallable]],
        timeouts: dict[str, float],
    ) -> list[TaskOutcome]:
        """Internal coroutine: gather + semaphore + optional per-task timeout.

        Each task runs inside a context-managed semaphore acquire so
        no more than ``max_concurrency`` tasks are in flight at once.
        Sync callables without a timeout go through
        :func:`asyncio.to_thread` so the event loop is not blocked. Timed
        sync callables run in a child process whose bounded join is performed
        in a worker thread, allowing the child to be terminated on breach.
        Async callables use :func:`asyncio.wait_for`.
        """
        sem = asyncio.Semaphore(self._max_concurrency)
        explicit_task_ids = getattr(timeouts, "explicit_task_ids", None)

        async def run_one(task_id: str, fn: TaskCallable) -> TaskOutcome:
            timeout = timeouts.get(task_id)
            async with sem:
                return await self._run_one_async(
                    task_id,
                    fn,
                    timeout,
                    isolate_sync=explicit_task_ids is None or task_id in explicit_task_ids,
                )

        return await asyncio.gather(*(run_one(tid, fn) for tid, fn in tasks))
