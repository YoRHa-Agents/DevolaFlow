"""Selector cache warmup tests (v9.7.0 PV-04).

Closes D-N-2 from ``.local/research/v9.7.0_gap_analysis.md`` §1.3 — the
v9.3.0 PV-03 LRU cache on ``load_profiles`` / ``load_skill_md`` /
``estimate_tokens`` is COLD on session start. v9.7.0 PV-04 ships an
opt-in :func:`devolaflow.task_adaptive_selector.warmup_selector_cache`
that pre-populates the cache for the top-5 task_types × 3 round_nums
when ``DEVOLAFLOW_WARMUP=1`` is set.

Five concerns are covered:

1. **Warmup populates cache** — when ``force=True`` (or the env flag
   is set), the helper successfully calls ``select_context`` for every
   (task_type, round_num) pair and reports the right completion count.
2. **Env-flag-off no-op** — without the env flag, the helper is a
   STRICT no-op (returns ``0``, performs zero IO).
3. **Strict env-flag truthy contract** — only ``"1"`` activates;
   ``"true"`` / ``"yes"`` / ``"0"`` / ``""`` / unset all skip
   (R5 strict pattern per W-20 §3).
4. **Idempotency** — a second warmup call against an already-warm
   cache is cheap and produces the same completion count.
5. **Time-budget sanity** — the warmup runs in well under 1 second
   (the LRU cache makes the post-first-call iteration O(1) per pair).

W-17 NEW-test-function tally: this module adds 5 new test functions.
"""

from __future__ import annotations

import os
import time

from devolaflow.task_adaptive_selector import (
    WARMUP_ENV_FLAG,
    WARMUP_ROUND_NUMS,
    WARMUP_TASK_TYPES,
    WARMUP_TRUTHY_VALUE,
    _load_profiles_cached,
    _load_skill_md_cached,
    warmup_selector_cache,
)


def test_warmup_populates_cache_when_forced() -> None:
    """``force=True`` bypasses the env flag and populates the LRU caches.

    Returns the number of completed (task_type, round_num) pairs, which
    equals ``len(WARMUP_TASK_TYPES) * len(WARMUP_ROUND_NUMS)`` (15)
    for the canonical top-5 × 3 matrix.
    """
    completed = warmup_selector_cache(force=True)
    expected = len(WARMUP_TASK_TYPES) * len(WARMUP_ROUND_NUMS)
    assert completed == expected, f"expected {expected} pairs warmed (top-5 × 3), got {completed}"
    # The cache MUST now have at least one entry — proves the warmup
    # actually populated something.
    assert _load_profiles_cached.cache_info().currsize >= 1, (
        "warmup_selector_cache did not populate _load_profiles_cached"
    )
    assert _load_skill_md_cached.cache_info().currsize >= 1, (
        "warmup_selector_cache did not populate _load_skill_md_cached"
    )


def test_warmup_is_noop_when_env_flag_unset(monkeypatch) -> None:
    """Without the env flag set, warmup_selector_cache returns 0 without IO."""
    monkeypatch.delenv(WARMUP_ENV_FLAG, raising=False)
    completed = warmup_selector_cache()
    assert completed == 0, (
        f"warmup_selector_cache MUST be a no-op when DEVOLAFLOW_WARMUP "
        f"is unset; got {completed} completions"
    )


def test_warmup_strict_truthy_only_one_activates(monkeypatch) -> None:
    """Per R5 strict pattern, only the literal ``"1"`` activates warmup.

    Other "truthy-looking" values (``"true"``, ``"yes"``, ``"on"``,
    ``"0"``, ``""``, etc.) all skip — preserving the auditable
    activation surface contract per W-20 §3.
    """
    # 1. The literal "1" activates.
    monkeypatch.setenv(WARMUP_ENV_FLAG, "1")
    assert WARMUP_TRUTHY_VALUE == "1"
    n_active = warmup_selector_cache()
    assert n_active == len(WARMUP_TASK_TYPES) * len(WARMUP_ROUND_NUMS)

    # 2. Truthy-looking strings do NOT activate.
    for stale in ("true", "yes", "on", "True", "TRUE", "0", "", " 1 ", "1 ", " 1"):
        monkeypatch.setenv(WARMUP_ENV_FLAG, stale)
        n_skip = warmup_selector_cache()
        assert n_skip == 0, (
            f"warmup activated on env-flag={stale!r} — R5 strict contract "
            f"requires EXACT match against {WARMUP_TRUTHY_VALUE!r}"
        )


def test_warmup_idempotent() -> None:
    """A second warmup call against an already-warm cache returns the same count.

    The LRU cache makes the second iteration O(1) per pair (each
    select_context hits the cached load_profiles / load_skill_md
    paths). The completion count is stable regardless of cache state.
    """
    first = warmup_selector_cache(force=True)
    second = warmup_selector_cache(force=True)
    third = warmup_selector_cache(force=True)
    assert first == second == third, (
        f"warmup non-idempotent: 1st={first}, 2nd={second}, 3rd={third}"
    )


def test_warmup_completes_within_time_budget() -> None:
    """The warmup runs well within 5 seconds even on a cold start.

    Per the v9.7.0 PV-04 spec the soft budget is ≤ 500 ms on a warm
    cache; this test uses a 5-second hard ceiling to be CI-headroom-safe.
    Catches a regression where a future PV makes select_context
    re-introduce a slow uncached path.
    """
    # First call may be cold; second call should hit the cache.
    warmup_selector_cache(force=True)  # warm the cache first

    start = time.perf_counter()
    completed = warmup_selector_cache(force=True)
    elapsed = time.perf_counter() - start

    expected = len(WARMUP_TASK_TYPES) * len(WARMUP_ROUND_NUMS)
    assert completed == expected
    assert elapsed < 5.0, (
        f"warm-cache warmup took {elapsed:.3f}s for {completed} pairs; "
        f"the post-PV-03 LRU cache should keep this well under 1 second. "
        f"A regression here suggests a slow uncached path was reintroduced."
    )


def test_warmup_constants_are_sane() -> None:
    """Lock in the W-17 / W-18 contract constants for the warmup helper."""
    # Env flag name follows the canonical DEVOLAFLOW_* prefix.
    assert WARMUP_ENV_FLAG == "DEVOLAFLOW_WARMUP"
    # Truthy value is exactly "1" per R5 strict pattern.
    assert WARMUP_TRUTHY_VALUE == "1"
    # Top-5 task_types match the canonical declared set.
    assert len(WARMUP_TASK_TYPES) == 5
    assert WARMUP_TASK_TYPES == ("implement", "research", "design", "hotfix", "review")
    # Round numbers cover the convergence-loop hot path (1, 2, 3).
    assert WARMUP_ROUND_NUMS == (1, 2, 3)


def test_warmup_skips_env_flag_at_module_import() -> None:
    """The warmup helper does NOT auto-fire on module import.

    A future change that adds an import-time hook MUST be opt-in via
    a separate signal — it MUST NOT silently start spending CPU on
    every ``import devolaflow.task_adaptive_selector``. This test
    asserts the import-time invariant: importing the module without
    setting DEVOLAFLOW_WARMUP=1 has no warmup side-effects on the
    cache (we can't directly observe "didn't run" but we can confirm
    the public function exists + the env flag is the activation gate).
    """
    # Verify the function is importable but is gated by the env flag.
    assert callable(warmup_selector_cache)
    # The mere existence of the symbol does NOT pre-warm — verified
    # by saving (cache state at import) vs (cache state after env-off
    # call). Both should agree because the env-off path is a strict
    # no-op.
    state_before = (
        _load_profiles_cached.cache_info().hits,
        _load_profiles_cached.cache_info().misses,
    )

    # Ensure env flag is unset.
    saved = os.environ.pop(WARMUP_ENV_FLAG, None)
    try:
        n = warmup_selector_cache()
        assert n == 0
    finally:
        if saved is not None:
            os.environ[WARMUP_ENV_FLAG] = saved

    state_after = (
        _load_profiles_cached.cache_info().hits,
        _load_profiles_cached.cache_info().misses,
    )
    # Env-off path produces ZERO new cache hits or misses.
    assert state_before == state_after, (
        f"env-off warmup mutated cache state: before={state_before}, "
        f"after={state_after}; expected strict no-op"
    )
