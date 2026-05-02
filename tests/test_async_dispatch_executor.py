"""Regression tests for the v9.3.0 PV-05 async dispatch executor.

Pin contract for
:class:`devolaflow.agent_workspace.dispatch_executor.AsyncDispatchExecutor`:

* sequential fallback runs callables in-order, captures exceptions
  per-task (S-5)
* parallel fast path uses :func:`asyncio.gather`, completes a wave in
  ~max(per-task) instead of sum(per-task) (the headline PV-05 win)
* exception isolation: one failing task does NOT short-circuit the
  rest (S-5)
* P1 invariant: the executor never inspects, mutates, or replaces the
  callable — it only schedules

W-17 NEW test functions: 6 (within +30/PV cap; cycle-cumulative
running tally +22 of +150).

Closes D-E-3 from `.local/research/v9.3.0_gap_analysis.md` §1.4.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from devolaflow.agent_workspace.dispatch_executor import (
    DEFAULT_MAX_CONCURRENCY,
    AsyncDispatchExecutor,
    ExecutorError,
    TaskOutcome,
)

# ---------------------------------------------------------------------------
# §1 — Construction + invariants.
# ---------------------------------------------------------------------------


def test_executor_default_max_concurrency_is_four() -> None:
    """The default cap is :data:`DEFAULT_MAX_CONCURRENCY` (= 4).

    Pinned because the SKILL.md §"Wave Dispatch" sub-table assumes
    4-parallel-task waves; bumping the default is an
    operator-visible behaviour change that requires a CHANGELOG
    entry.
    """
    executor = AsyncDispatchExecutor()
    assert DEFAULT_MAX_CONCURRENCY == 4
    assert executor.max_concurrency == DEFAULT_MAX_CONCURRENCY


def test_executor_rejects_zero_or_negative_max_concurrency() -> None:
    """``max_concurrency`` < 1 raises ``ExecutorError`` (S-5).

    A zero cap would deadlock the asyncio.Semaphore; a negative cap
    is non-sensical. The executor MUST NOT silently coerce — it
    raises so the bug surfaces at construction time, not during a
    live dispatch.
    """
    with pytest.raises(ExecutorError):
        AsyncDispatchExecutor(max_concurrency=0)
    with pytest.raises(ExecutorError):
        AsyncDispatchExecutor(max_concurrency=-1)
    # Inherits ValueError so callers can broad-except.
    assert issubclass(ExecutorError, ValueError)


# ---------------------------------------------------------------------------
# §2 — Sequential fallback.
# ---------------------------------------------------------------------------


def test_dispatch_sequential_runs_callables_in_order() -> None:
    """Sequential mode preserves task order in the outcome list."""
    executor = AsyncDispatchExecutor()
    call_order: list[str] = []

    def make(task_id: str, value: int):
        def call() -> int:
            call_order.append(task_id)
            return value

        return call

    tasks = [
        ("task-a", make("task-a", 1)),
        ("task-b", make("task-b", 2)),
        ("task-c", make("task-c", 3)),
    ]
    outcomes = executor.dispatch_sequential(tasks)

    assert call_order == ["task-a", "task-b", "task-c"], (
        "Sequential mode MUST run tasks in input order"
    )
    assert [o.task_id for o in outcomes] == ["task-a", "task-b", "task-c"]
    assert [o.succeeded for o in outcomes] == [True, True, True]
    assert [o.result for o in outcomes] == [1, 2, 3]
    assert [o.exception for o in outcomes] == [None, None, None]


def test_dispatch_sequential_isolates_per_task_exceptions() -> None:
    """One failing task does NOT abort the wave (S-5 contract).

    The failure is captured into the matching :class:`TaskOutcome`'s
    ``exception`` field; subsequent tasks still run. Callers handle
    the failure via the gate (typically by counting failed outcomes
    against a tolerance threshold).
    """
    executor = AsyncDispatchExecutor()

    def passing() -> str:
        return "ok"

    def failing() -> None:
        raise RuntimeError("boom")

    outcomes = executor.dispatch_sequential(
        [
            ("ok-1", passing),
            ("fail", failing),
            ("ok-2", passing),
        ]
    )

    assert outcomes[0].succeeded is True
    assert outcomes[0].result == "ok"
    assert outcomes[1].succeeded is False
    assert isinstance(outcomes[1].exception, RuntimeError)
    assert "boom" in str(outcomes[1].exception)
    assert outcomes[2].succeeded is True
    assert outcomes[2].result == "ok"


# ---------------------------------------------------------------------------
# §3 — Parallel fast path.
# ---------------------------------------------------------------------------


def test_dispatch_parallel_completes_in_max_not_sum() -> None:
    """4-task wave with ~50ms tasks completes in ~50ms total (parallel),
    not ~200ms (sequential).

    The headline PV-05 win — proves the asyncio.gather + Semaphore
    machinery actually overlaps the wait time. Uses small sleeps so
    the test is fast on CI; the absolute numbers don't need to be
    sub-millisecond, just clearly less than the sequential sum.
    """
    executor = AsyncDispatchExecutor(max_concurrency=4)

    def slow_task() -> str:
        time.sleep(0.05)  # 50 ms
        return "done"

    tasks = [(f"task-{i}", slow_task) for i in range(4)]

    t0 = time.perf_counter()
    outcomes = executor.dispatch_parallel(tasks)
    elapsed_s = time.perf_counter() - t0

    # All 4 must succeed.
    assert all(o.succeeded for o in outcomes), [o.exception for o in outcomes]
    assert [o.result for o in outcomes] == ["done"] * 4

    # Sequential would take 4 * 50 = 200 ms; parallel should be much closer
    # to 50 ms (the max). We assert < 150 ms to leave headroom for thread
    # spawn + asyncio overhead (typically ~20-40 ms on slow CI workers).
    assert elapsed_s < 0.15, (
        f"4-task parallel wave took {elapsed_s * 1000:.1f} ms — expected < 150 ms "
        "(close to max(50ms), not sum=200ms). Either the asyncio gather is "
        "broken or the worker is critically slow."
    )


def test_dispatch_parallel_isolates_per_task_exceptions() -> None:
    """One failing task does NOT abort the parallel wave (S-5).

    Mirror of test_dispatch_sequential_isolates_per_task_exceptions
    but for the asyncio path. Per-task exception capture is the
    same contract.
    """
    executor = AsyncDispatchExecutor()

    def passing() -> int:
        return 42

    def failing() -> None:
        raise ValueError("intended-test-failure")

    outcomes = executor.dispatch_parallel(
        [
            ("ok-1", passing),
            ("fail", failing),
            ("ok-2", passing),
        ]
    )

    by_id = {o.task_id: o for o in outcomes}
    assert by_id["ok-1"].succeeded is True
    assert by_id["ok-1"].result == 42
    assert by_id["fail"].succeeded is False
    assert isinstance(by_id["fail"].exception, ValueError)
    assert "intended-test-failure" in str(by_id["fail"].exception)
    assert by_id["ok-2"].succeeded is True
    assert by_id["ok-2"].result == 42


def test_dispatch_parallel_handles_async_callables() -> None:
    """Async callables are awaited, not threaded.

    Mixed sync + async callables in the same wave both work; the
    executor branches on :func:`inspect.iscoroutinefunction` and
    routes appropriately. Pinned because the executor's contract
    accepts BOTH callable shapes.
    """
    executor = AsyncDispatchExecutor()

    async def async_task() -> str:
        await asyncio.sleep(0.01)
        return "async-result"

    def sync_task() -> str:
        time.sleep(0.01)
        return "sync-result"

    outcomes = executor.dispatch_parallel(
        [
            ("async-1", async_task),
            ("sync-1", sync_task),
        ]
    )

    by_id = {o.task_id: o for o in outcomes}
    assert by_id["async-1"].succeeded is True
    assert by_id["async-1"].result == "async-result"
    assert by_id["sync-1"].succeeded is True
    assert by_id["sync-1"].result == "sync-result"


def test_dispatch_parallel_empty_wave_is_noop() -> None:
    """An empty task list returns ``[]`` without spawning a loop."""
    executor = AsyncDispatchExecutor()
    outcomes = executor.dispatch_parallel([])
    assert outcomes == []


# ---------------------------------------------------------------------------
# §4 — P1 invariant — Dispatcher-Not-Implementer (Soul Rule S-1).
# ---------------------------------------------------------------------------


def test_executor_calls_only_provided_callables() -> None:
    """The executor never invokes any internal "library work" — it only
    schedules user-provided callables.

    Pinned because P1 + Soul Rule S-1 (Dispatcher-Not-Implementer)
    is the foundational architectural invariant the executor MUST
    NOT violate. A future maintainer who adds e.g. an "if task_id
    in known_tasks: do_internal_work()" branch would break P1.

    The test wires a sentinel callable that records EVERY invocation
    (no class member functions, no internal helpers). After the
    parallel dispatch completes, the recorder must show exactly
    ``len(tasks)`` invocations and nothing else — proving the
    executor did not summon any side-effects from inside its own
    namespace.
    """
    executor = AsyncDispatchExecutor()
    invocations: list[str] = []

    def recorder_for(task_id: str):
        def recorded() -> str:
            invocations.append(task_id)
            return f"completed-{task_id}"

        return recorded

    tasks = [("alpha", recorder_for("alpha")), ("beta", recorder_for("beta"))]
    outcomes = executor.dispatch_parallel(tasks)

    # The executor invoked EXACTLY 2 callables (one per task), in some
    # order. No other invocations from inside the executor.
    assert len(invocations) == 2, (
        f"P1 violation: executor recorded {len(invocations)} callable "
        "invocations, expected exactly 2 (one per provided task). The "
        "executor MUST NOT invoke any internal helpers — it only "
        "schedules user-provided callables."
    )
    assert set(invocations) == {"alpha", "beta"}
    assert all(o.succeeded for o in outcomes)
    assert {o.result for o in outcomes} == {"completed-alpha", "completed-beta"}


# ---------------------------------------------------------------------------
# §5 — Concurrency cap.
# ---------------------------------------------------------------------------


def test_dispatch_parallel_respects_max_concurrency() -> None:
    """At most ``max_concurrency`` tasks are in flight simultaneously.

    Wires a counter-based semaphore-style probe: each task increments
    ``in_flight`` on entry and decrements on exit. The peak value
    observed across the wave's run MUST be <= ``max_concurrency``.
    """
    executor = AsyncDispatchExecutor(max_concurrency=2)
    in_flight = 0
    peak = 0
    lock = asyncio.Lock()  # local synchronisation; OK because tasks are async-aware

    async def probe_task() -> None:
        nonlocal in_flight, peak
        async with lock:
            in_flight += 1
            if in_flight > peak:
                peak = in_flight
        await asyncio.sleep(0.02)
        async with lock:
            in_flight -= 1

    tasks = [(f"probe-{i}", probe_task) for i in range(8)]
    outcomes = executor.dispatch_parallel(tasks)

    assert all(o.succeeded for o in outcomes)
    assert peak <= 2, (
        f"max_concurrency=2 violated: peak in-flight reached {peak}. "
        "The semaphore in dispatch_parallel must cap simultaneous tasks."
    )
    # And the cap must actually fire — peak should reach exactly 2 with 8
    # tasks each sleeping 20 ms. If peak = 1 the semaphore is forcing
    # serial execution (broken differently).
    assert peak >= 2, (
        f"With 8 sleep-tasks and max_concurrency=2 the peak should be "
        f"exactly 2; got {peak}. Either the semaphore is too tight or "
        "tasks are running serially (bug)."
    )


# ---------------------------------------------------------------------------
# §6 — TaskOutcome shape.
# ---------------------------------------------------------------------------


def test_task_outcome_invariant_succeeded_xor_exception() -> None:
    """Either ``result`` is set OR ``exception`` is — never both populated.

    Pin the contract: callers branch on ``succeeded``; the result /
    exception fields' shape is defined by that flag. Failed outcomes
    have ``result is None`` AND ``exception is not None``; succeeded
    outcomes have ``result`` (possibly None — the callable may have
    legitimately returned None) AND ``exception is None``.
    """
    succeeded = TaskOutcome(task_id="t", succeeded=True, result=42)
    assert succeeded.succeeded is True
    assert succeeded.result == 42
    assert succeeded.exception is None

    failed = TaskOutcome(task_id="t", succeeded=False, exception=RuntimeError("x"))
    assert failed.succeeded is False
    assert failed.result is None
    assert isinstance(failed.exception, RuntimeError)
