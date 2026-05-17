"""v12.2.0 PV-04 — AsyncDispatchExecutor per-task `asyncio.wait_for` timeout.

Closes the v12.0.0/v12.1.0 telegraph "AsyncDispatchExecutor per-task
timeout (`asyncio.wait_for`) — deferred to v12.2.0+" per
`.local/research/v12.2.0_gap_analysis.md` §2 D-4. The library-only
landing discipline (no env flag, no auto-wire) from v9.3.0 PV-05 is
preserved — callers opt in by passing the new ``timeouts=`` kwarg.

Test surface covers (per the v12.2.0 PV-04 dispatch AC):

1. Sequential mode honours the per-task timeout.
2. Parallel mode honours the per-task timeout.
3. Tasks WITHOUT a timeout (absent from the dict) run unbounded —
   preserves v9.3.0 byte-identical behaviour for every caller that
   does NOT pass the kwarg.
4. Timeout breach surfaces as ``TaskOutcome(succeeded=False,
   exception=TimeoutError)`` per S-5 (explicit error state).
5. Per-task isolation: a timeout on task A does NOT cancel task B in
   the same wave.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from devolaflow.agent_workspace.dispatch_executor import (
    AsyncDispatchExecutor,
    TaskOutcome,
)


def _sleep_fn(duration: float):
    """Return a sync callable that sleeps for ``duration`` seconds."""

    def _f() -> str:
        time.sleep(duration)
        return f"slept {duration}s"

    return _f


def _async_sleep_fn_factory(duration: float):
    """Return an async callable that sleeps for ``duration`` seconds.

    Returning the coroutine function directly (rather than a lambda that
    returns a coroutine) so ``inspect.iscoroutinefunction`` recognises
    it as a coroutine function and the executor routes it through the
    async branch of `_run_one_sync` / `_dispatch_parallel_async`.
    """

    async def _f() -> str:
        await asyncio.sleep(duration)
        return f"async slept {duration}s"

    return _f


def _instant_fn() -> str:
    return "instant"


# ---------------------------------------------------------------------------
# 1. Sequential mode — per-task timeout
# ---------------------------------------------------------------------------


def test_dispatch_sequential_honours_per_task_timeout() -> None:
    """A sync task that overruns its timeout MUST surface a TimeoutError."""
    executor = AsyncDispatchExecutor()
    outcomes = executor.dispatch_sequential(
        [("slow", _sleep_fn(0.30))],
        timeouts={"slow": 0.05},
    )
    assert len(outcomes) == 1
    assert outcomes[0].task_id == "slow"
    assert outcomes[0].succeeded is False, (
        "v12.2.0 PV-04 contract: a task whose execution exceeds the timeout "
        "MUST surface TaskOutcome(succeeded=False)"
    )
    assert isinstance(outcomes[0].exception, TimeoutError), (
        f"v12.2.0 PV-04 contract: timeout breach MUST surface TimeoutError; "
        f"got {type(outcomes[0].exception).__name__}"
    )


def test_dispatch_sequential_task_without_timeout_runs_unbounded() -> None:
    """A task absent from the timeouts map MUST run unbounded.

    Preserves v9.3.0 byte-identical behaviour for every caller that does
    NOT pass the kwarg — the v12.2.0 PV-04 contract is purely additive.
    """
    executor = AsyncDispatchExecutor()
    outcomes = executor.dispatch_sequential(
        [("slow", _sleep_fn(0.05))],
        timeouts={},
    )
    assert outcomes[0].succeeded is True
    assert outcomes[0].result == "slept 0.05s"


def test_dispatch_sequential_no_timeouts_kwarg_is_byte_identical() -> None:
    """Not passing the ``timeouts`` kwarg at all MUST match v9.3.0 behaviour."""
    executor = AsyncDispatchExecutor()
    outcomes = executor.dispatch_sequential([("fast", _instant_fn)])
    assert len(outcomes) == 1
    assert outcomes[0].succeeded is True
    assert outcomes[0].result == "instant"


# ---------------------------------------------------------------------------
# 2. Parallel mode — per-task timeout
# ---------------------------------------------------------------------------


def test_dispatch_parallel_honours_per_task_timeout() -> None:
    """A parallel sync task that overruns its timeout MUST surface TimeoutError."""
    executor = AsyncDispatchExecutor(max_concurrency=2)
    outcomes = executor.dispatch_parallel(
        [("slow", _sleep_fn(0.30)), ("fast", _instant_fn)],
        timeouts={"slow": 0.05},
    )
    by_id = {o.task_id: o for o in outcomes}
    assert by_id["slow"].succeeded is False
    assert isinstance(by_id["slow"].exception, TimeoutError)
    # Per-task isolation: fast task MUST succeed despite slow's timeout
    assert by_id["fast"].succeeded is True, (
        "v12.2.0 PV-04 contract: timeout on task A MUST NOT cancel task B"
    )
    assert by_id["fast"].result == "instant"


def test_dispatch_parallel_async_callable_honours_timeout() -> None:
    """Async coroutines wrapped in ``asyncio.wait_for`` also honour timeout."""
    executor = AsyncDispatchExecutor(max_concurrency=2)
    async_callable = _async_sleep_fn_factory(0.30)
    outcomes = executor.dispatch_parallel(
        [("async_slow", async_callable)],
        timeouts={"async_slow": 0.05},
    )
    assert outcomes[0].succeeded is False
    assert isinstance(outcomes[0].exception, TimeoutError)


def test_dispatch_parallel_no_timeouts_kwarg_is_byte_identical() -> None:
    """Not passing the ``timeouts`` kwarg matches v9.3.0 behaviour."""
    executor = AsyncDispatchExecutor(max_concurrency=2)
    outcomes = executor.dispatch_parallel([("a", _instant_fn), ("b", _instant_fn)])
    assert all(o.succeeded for o in outcomes)
    assert {o.task_id for o in outcomes} == {"a", "b"}


def test_dispatch_parallel_empty_tasks_no_op() -> None:
    """Empty tasks list returns [] regardless of timeouts."""
    executor = AsyncDispatchExecutor()
    assert executor.dispatch_parallel([], timeouts={"unused": 1.0}) == []


# ---------------------------------------------------------------------------
# 3. default_timeout_for helper (task_adaptive_selector surface)
# ---------------------------------------------------------------------------


def test_default_timeout_for_returns_known_task_type_value() -> None:
    """The v12.2.0 PV-04 per-task-type default MUST return the documented
    seconds value for each canonical task type."""
    from devolaflow.task_adaptive_selector import default_timeout_for

    # Source-of-truth values from SKILL.md §"Subagent Hang Prevention".
    assert default_timeout_for("research") == 2700
    assert default_timeout_for("impl") == 1800
    assert default_timeout_for("test") == 900
    assert default_timeout_for("review") == 1200
    assert default_timeout_for("hotfix") == 600


def test_default_timeout_for_unknown_task_type_returns_fallback() -> None:
    """Unrecognised task types fall back to the SKILL.md 7200s ceiling."""
    from devolaflow.task_adaptive_selector import (
        TASK_TYPE_TIMEOUT_FALLBACK,
        default_timeout_for,
    )

    assert default_timeout_for("unknown") == TASK_TYPE_TIMEOUT_FALLBACK
    assert default_timeout_for("") == TASK_TYPE_TIMEOUT_FALLBACK
    assert default_timeout_for("design") == TASK_TYPE_TIMEOUT_FALLBACK


def test_default_timeout_for_normalises_whitespace_and_case() -> None:
    """Lookup is case-insensitive and trims surrounding whitespace."""
    from devolaflow.task_adaptive_selector import default_timeout_for

    assert default_timeout_for(" Research ") == 2700
    assert default_timeout_for("IMPL") == 1800


def test_default_timeout_for_non_string_returns_fallback() -> None:
    """Defensive: non-string inputs return the fallback per S-5 explicit-error-state."""
    from devolaflow.task_adaptive_selector import (
        TASK_TYPE_TIMEOUT_FALLBACK,
        default_timeout_for,
    )

    assert default_timeout_for(None) == TASK_TYPE_TIMEOUT_FALLBACK  # type: ignore[arg-type]
    assert default_timeout_for(123) == TASK_TYPE_TIMEOUT_FALLBACK  # type: ignore[arg-type]


def test_task_type_timeout_defaults_membership_pinned() -> None:
    """The membership of TASK_TYPE_TIMEOUT_DEFAULTS is the contract surface.

    Pin the exact 5-entry set so future PVs cannot silently widen or
    narrow it without refreshing the W-18 ghost-audit stanza.
    """
    from devolaflow.task_adaptive_selector import TASK_TYPE_TIMEOUT_DEFAULTS

    assert set(TASK_TYPE_TIMEOUT_DEFAULTS.keys()) == {
        "research",
        "impl",
        "test",
        "review",
        "hotfix",
    }


# ---------------------------------------------------------------------------
# 4. TaskOutcome type sanity (defensive: ensure exception is propagated)
# ---------------------------------------------------------------------------


def test_task_outcome_carries_timeout_exception_instance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The captured TimeoutError instance is preserved end-to-end."""
    executor = AsyncDispatchExecutor()
    outcomes = executor.dispatch_sequential(
        [("slow", _sleep_fn(0.20))],
        timeouts={"slow": 0.02},
    )
    outcome = outcomes[0]
    assert isinstance(outcome, TaskOutcome)
    assert outcome.exception is not None
    # TimeoutError is the canonical asyncio.TimeoutError alias on 3.11+
    assert isinstance(outcome.exception, TimeoutError)
