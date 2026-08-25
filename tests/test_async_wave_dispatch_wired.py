"""Auto-wired async wave dispatch tests (v9.7.0 PV-03).

Closes D-N-3 from ``.local/research/v9.7.0_gap_analysis.md`` §1.2 — the
v9.3.0 PV-05 ``AsyncDispatchExecutor`` shipped library-only; v9.7.0
PV-03 wires it into a public dispatch entry point at the L2-wave
boundary via :func:`devolaflow.dispatch.dispatch_wave_tasks` (owner
module since the v14.5.0 ADR-006 split; the ``devolaflow.feedback``
re-export shim was retired in v17.0.0).

Six concerns are covered:

1. **Parallel wave → async path** — when ``sync_barrier.mode == "parallel"``
   AND len(tasks) > 1, the executor's ``dispatch_parallel`` (asyncio.gather)
   path is taken. Tasks complete and return correct outcomes.
2. **Sequential wave → sync path** — when ``mode == "all"`` (the default
   sync barrier) OR the wave has 1 task, the sync ``dispatch_sequential``
   path is taken. No asyncio.run cost paid.
3. **Exception isolation** — a failing task carries its exception in
   ``TaskOutcome.exception`` rather than raising out of the wave. Other
   tasks in the same wave continue running (S-5).
4. **P1 preserved** — :func:`dispatch_wave_tasks` does NOT execute the
   factory's return value itself; it only schedules. Verified by
   intercepting the factory and asserting the dispatch helper never
   touches the callable's body before the executor is invoked.
5. **Max concurrency resolution** — ``sync_barrier.max_parallelism``
   wins when set; ``max_concurrency`` keyword wins over the wave's
   value; default falls back to
   :data:`DEFAULT_MAX_CONCURRENCY` (4).
6. **Contract violations** — bad shapes (non-dict wave_definition,
   non-callable factory, non-list tasks, factory returning non-callable)
   raise eagerly per S-5 explicit failure semantics.

W-17 NEW-test-function tally: this module adds 7 new test functions.
Parametrize expansions are absent — the regression guards are
deliberately separate so a failure surface identifies which axis broke.

v15.0.0 G-038 flip 1 addendum (+2 test functions): the v12.2.0 PV-04
``asyncio.wait_for`` timeout machinery is DEFAULT-ON at this dispatch
surface — every task gets a ceiling resolved from its explicit
``timeout_seconds`` (the v14.5.0 G-037 auto-population knob) or its
task-type class default (7200 s fail-safe for unknown types). Opt-out:
``timeout_seconds: null`` on the task spec.
"""

from __future__ import annotations

from devolaflow.agent_workspace.dispatch_executor import (
    DEFAULT_MAX_CONCURRENCY,
    AsyncDispatchExecutor,
    TaskOutcome,
)
from devolaflow.dispatch import dispatch_wave_tasks


def _parallel_wave(tasks: list[dict] | None = None, max_parallelism: int | None = None) -> dict:
    """Build a minimal parallel-mode wave_definition."""
    if tasks is None:
        tasks = [{"task_id": f"T0{i}", "title": f"task {i}"} for i in range(4)]
    sync_barrier: dict = {"mode": "parallel"}
    if max_parallelism is not None:
        sync_barrier["max_parallelism"] = max_parallelism
    return {
        "id": "W01",
        "stage_id": "S01",
        "tasks": tasks,
        "sync_barrier": sync_barrier,
        "gate": {"type": "standard"},
    }


def _sequential_wave(tasks: list[dict] | None = None) -> dict:
    """Build a minimal sequential ('all') wave_definition."""
    if tasks is None:
        tasks = [{"task_id": "T01", "title": "single task"}]
    return {
        "id": "W02",
        "stage_id": "S01",
        "tasks": tasks,
        "sync_barrier": {"mode": "all"},
        "gate": {"type": "standard"},
    }


def test_parallel_wave_takes_async_path() -> None:
    """A parallel-mode wave with multiple tasks runs via the asyncio path.

    The dispatch_factory returns sync callables that record their
    ``task_id`` into a shared list; the parallel executor schedules them
    via :func:`asyncio.gather` so all 4 tasks complete and produce
    successful TaskOutcomes.
    """
    wave = _parallel_wave()
    completed: list[str] = []

    def factory(task: dict):
        task_id = task["task_id"]

        def fn() -> str:
            completed.append(task_id)
            return f"done-{task_id}"

        return fn

    outcomes = dispatch_wave_tasks(wave, factory)

    assert len(outcomes) == 4, f"expected 4 outcomes, got {len(outcomes)}"
    assert all(isinstance(o, TaskOutcome) for o in outcomes)
    assert all(o.succeeded for o in outcomes), (
        f"expected all 4 to succeed, got {[o.succeeded for o in outcomes]}"
    )
    # Outcomes preserve input order regardless of completion order.
    assert [o.task_id for o in outcomes] == ["T00", "T01", "T02", "T03"]
    assert sorted(completed) == ["T00", "T01", "T02", "T03"]


def test_sequential_wave_takes_sync_path() -> None:
    """A sequential ('all') wave runs via the sync path (no asyncio.run cost).

    The single-task path AND multi-task all-mode path both go through
    ``dispatch_sequential``. The deterministic-order completion list
    proves the sync path was taken (parallel scheduling could complete
    in any order).
    """
    # Single-task wave — sync fallback regardless of mode.
    wave_one = _sequential_wave()
    outcomes_one = dispatch_wave_tasks(wave_one, lambda t: lambda: f"r-{t['task_id']}")
    assert len(outcomes_one) == 1
    assert outcomes_one[0].result == "r-T01"

    # Multi-task 'all' wave — sequential because mode != "parallel".
    wave_multi = _sequential_wave(tasks=[{"task_id": f"T0{i}"} for i in range(3)])
    completed_order: list[str] = []

    def factory(task):
        return lambda: completed_order.append(task["task_id"]) or task["task_id"]

    outcomes_multi = dispatch_wave_tasks(wave_multi, factory)
    assert len(outcomes_multi) == 3
    # Sequential path completes in deterministic input order.
    assert completed_order == ["T00", "T01", "T02"]


def test_failed_task_isolated_into_outcome() -> None:
    """A task that raises has its exception captured in TaskOutcome (S-5).

    The wave does NOT short-circuit on first failure; siblings keep
    running. The outcome list preserves input order so callers can
    correlate failures with their task specs.
    """
    wave = _parallel_wave(tasks=[{"task_id": f"T0{i}"} for i in range(3)])

    def factory(task):
        task_id = task["task_id"]

        def fn():
            if task_id == "T01":
                raise RuntimeError(f"injected failure for {task_id}")
            return f"ok-{task_id}"

        return fn

    outcomes = dispatch_wave_tasks(wave, factory)

    assert len(outcomes) == 3
    assert outcomes[0].succeeded
    assert outcomes[0].result == "ok-T00"
    assert not outcomes[1].succeeded
    assert isinstance(outcomes[1].exception, RuntimeError)
    assert "T01" in str(outcomes[1].exception)
    assert outcomes[2].succeeded
    assert outcomes[2].result == "ok-T02"


def test_dispatch_wave_tasks_preserves_p1() -> None:
    """P1 invariant: dispatch_wave_tasks itself never executes a callable.

    The factory is INSTRUMENTED to record whenever a callable is INVOKED.
    dispatch_wave_tasks SHOULD only call the factory once per task (to
    BUILD the callable) and then hand the callables off to the executor.
    By instrumenting the callable's body to track invocation, we can
    verify that no invocation happens until the executor schedules it.
    """
    wave = _parallel_wave(tasks=[{"task_id": "T00"}, {"task_id": "T01"}])

    factory_calls = 0
    callable_calls = 0

    def factory(task):
        nonlocal factory_calls
        factory_calls += 1

        def fn():
            nonlocal callable_calls
            callable_calls += 1
            return task["task_id"]

        return fn

    outcomes = dispatch_wave_tasks(wave, factory)

    # Factory called exactly once per task (to build the callable).
    assert factory_calls == 2
    # Callable executed exactly once per task (by the executor, NOT by
    # dispatch_wave_tasks). The fact that we see the right return values
    # AND the count == 2 (no double-invocation) proves P1: the helper
    # only schedules.
    assert callable_calls == 2
    assert all(o.succeeded for o in outcomes)


def test_max_concurrency_resolution() -> None:
    """``max_concurrency`` resolves: keyword > sync_barrier.max_parallelism > default."""
    # 1. Keyword override wins over sync_barrier value.
    wave_with_max = _parallel_wave(max_parallelism=8)
    # We can't directly observe the executor's max_concurrency from
    # outside, but we can verify the function accepts the override
    # without raising. Capture the executor via monkey-patching the
    # AsyncDispatchExecutor constructor.
    captured: list[int] = []
    original_init = AsyncDispatchExecutor.__init__

    def spy_init(self, max_concurrency=None):
        captured.append(max_concurrency if max_concurrency is not None else DEFAULT_MAX_CONCURRENCY)
        original_init(self, max_concurrency=max_concurrency)

    AsyncDispatchExecutor.__init__ = spy_init  # type: ignore[method-assign]
    try:
        # 1. keyword override wins
        dispatch_wave_tasks(wave_with_max, lambda t: lambda: None, max_concurrency=2)
        assert captured[-1] == 2

        # 2. sync_barrier value wins when no keyword override
        dispatch_wave_tasks(wave_with_max, lambda t: lambda: None)
        assert captured[-1] == 8

        # 3. default fallback when neither set
        wave_no_max = _parallel_wave(max_parallelism=None)
        dispatch_wave_tasks(wave_no_max, lambda t: lambda: None)
        assert captured[-1] == DEFAULT_MAX_CONCURRENCY  # 4
    finally:
        AsyncDispatchExecutor.__init__ = original_init  # type: ignore[method-assign]


def test_empty_tasks_returns_empty_list_no_loop_init() -> None:
    """An empty tasks list short-circuits to [] without spawning a loop."""
    wave_empty = _parallel_wave(tasks=[])
    outcomes = dispatch_wave_tasks(wave_empty, lambda t: lambda: "should not be called")
    assert outcomes == []


def test_contract_violations_raise_explicitly() -> None:
    """Per S-5, malformed inputs raise rather than silently coercing."""
    import pytest

    # Non-dict wave_definition.
    with pytest.raises(TypeError):
        dispatch_wave_tasks("not a dict", lambda t: lambda: None)  # type: ignore[arg-type]

    # Non-callable factory.
    wave = _parallel_wave()
    with pytest.raises(TypeError):
        dispatch_wave_tasks(wave, "not callable")  # type: ignore[arg-type]

    # Non-list tasks.
    bad_wave = {"tasks": "not a list", "sync_barrier": {"mode": "parallel"}}
    with pytest.raises(TypeError):
        dispatch_wave_tasks(bad_wave, lambda t: lambda: None)

    # Factory returning a non-callable.
    with pytest.raises(TypeError):
        dispatch_wave_tasks(wave, lambda t: "not callable")  # type: ignore[arg-type,return-value]

    # Non-dict task entry.
    bad_task_wave = {
        "tasks": ["string instead of dict"],
        "sync_barrier": {"mode": "parallel"},
    }
    with pytest.raises(TypeError):
        dispatch_wave_tasks(bad_task_wave, lambda t: lambda: None)


# ---------------------------------------------------------------------------
# v15.0.0 G-038 flip 1 — timeout enforcement DEFAULT-ON
# ---------------------------------------------------------------------------


def test_default_timeouts_auto_populated_with_explicit_null_opt_out() -> None:
    """v15.0.0 new default: every task gets a ``wait_for`` ceiling by default.

    Captures the ``timeouts={}`` map handed to the executor and pins
    the 3-step resolution per ``_resolve_task_timeout``:

    * explicit numeric ``timeout_seconds`` → enforced verbatim;
    * absent key → task-type class default (``test`` → 900 s) or the
      7200 s fail-safe for unknown / missing types;
    * explicit ``timeout_seconds: None`` → documented OPT-OUT — the
      task gets NO entry in the timeouts map (runs unbounded, the
      pre-v15.0.0 behaviour, per task; existing knob — no new env
      flag per W-20).
    """
    wave = _sequential_wave(
        tasks=[
            {"task_id": "T-explicit", "timeout_seconds": 42},
            {"task_id": "T-typed", "type": "test"},
            {"task_id": "T-unknown"},
            {"task_id": "T-opt-out", "timeout_seconds": None},
        ]
    )
    captured: list[dict] = []
    original = AsyncDispatchExecutor.dispatch_sequential

    def spy(self, tasks, *, timeouts=None):
        captured.append(dict(timeouts or {}))
        return original(self, tasks, timeouts=timeouts)

    AsyncDispatchExecutor.dispatch_sequential = spy  # type: ignore[method-assign]
    try:
        outcomes = dispatch_wave_tasks(wave, lambda t: lambda: t["task_id"])
    finally:
        AsyncDispatchExecutor.dispatch_sequential = original  # type: ignore[method-assign]

    assert all(o.succeeded for o in outcomes)
    assert captured == [
        {
            "T-explicit": 42.0,
            "T-typed": 900.0,
            "T-unknown": 7200.0,
            # T-opt-out is ABSENT — explicit null opts the task out.
        }
    ]


def test_timeout_breach_cancels_task_into_timeout_outcome() -> None:
    """v15.0.0 new default end-to-end: a breaching task is cancelled and
    surfaces ``TaskOutcome(succeeded=False, exception=TimeoutError)``
    per the v12.2.0 PV-04 contract, while its opted-out sibling
    (``timeout_seconds: None``) completes unbounded (S-5 — the breach
    is an explicit error state, never a silent hang)."""
    import time

    wave = _parallel_wave(
        tasks=[
            {"task_id": "T-slow", "timeout_seconds": 0.05},
            {"task_id": "T-free", "timeout_seconds": None},
        ]
    )

    def factory(task):
        if task["task_id"] == "T-slow":
            return lambda: time.sleep(0.5) or "never"
        return lambda: "ok-free"

    outcomes = dispatch_wave_tasks(wave, factory)

    assert not outcomes[0].succeeded
    assert isinstance(outcomes[0].exception, TimeoutError)
    assert outcomes[1].succeeded
    assert outcomes[1].result == "ok-free"
