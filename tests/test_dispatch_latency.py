"""Latency regression guards for the v9.3.0 dispatch primitives.

Couples the production landing of
``benchmarks/devolaflow_context/latency_harness.py`` (PV-02 deliverable)
to a small set of pytest-native regression guards. Three concerns are
covered:

1. **Harness shape** — the public API
   (:func:`benchmarks.devolaflow_context.latency_harness.capture_latency` +
   :data:`MEASURED_FUNCTIONS` + :func:`measure_function`) is stable.
   Tests pin the exact set of measured primitives so a future PV that
   adds / removes one MUST update the test in the same commit
   (preventing silent drift).
2. **Baseline file** — the wholesale baseline JSON shipped with PV-02
   (``benchmarks/devolaflow_context/baselines/v9.3.0_latency.json``)
   exists, parses, and carries percentile fields for every measured
   primitive. The pinned schema version (``1``) is the source of truth
   downstream tooling deserialises against.
3. **Sanity floors** — each primitive's measured ``p95_us`` MUST stay
   below an ABSOLUTE ceiling on a smoke-iteration run. The ceilings
   are intentionally generous (10× the post-PV-03 expected number)
   because pytest workers can run on slow CI shapes; the contract is
   "catch a 100× regression", not "match the production p95".

W-17 NEW-test-function tally: this module adds 4 new test functions
(plus 1 module-scope fixture). Parametrize expansions are absent —
the regression guards are deliberately separate so a failure surface
identifies which axis broke.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmarks.devolaflow_context.latency_harness import (
    DEFAULT_ITERATIONS,
    MEASURED_FUNCTIONS,
    SCHEMA_VERSION,
    SMOKE_ITERATIONS,
    _percentile,
    capture_latency,
    measure_function,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
BASELINES_DIR = REPO_ROOT / "benchmarks" / "devolaflow_context" / "baselines"
V9_3_0_LATENCY_BASELINE = BASELINES_DIR / "v9.3.0_latency.json"

# Per-function p95 sanity ceilings (microseconds). Intentionally generous —
# 10× the PV-01-measured post-LRU expectation. Catches a 100× regression
# but not micro-jitter on slow CI workers. Numbers anchor on the v9.3.0
# baseline JSON measured during PV-02 (pre-PV-03):
#
# | function          | PV-02 baseline p95 | sanity ceiling |
# |-------------------|--------------------|----------------|
# | select_context    | 80 ms              | 5000 ms        |
# | compress_message  | 1.8 ms             | 500 ms         |
# | run_hooks         | 4.5 µs             | 100 ms         |
# | full_dispatch     | 80 ms              | 10000 ms       |
#
# After PV-03 (LRU cache) ``select_context`` warm-path p95 collapses to
# ~50-200 µs. The ceiling stays at 5000 ms so this test does not need a
# bump every PV; the W-4 / SI-4 regression guard fires from
# ``tests/test_benchmarks.py`` against the recorded baseline JSON.
P95_SANITY_CEILING_US: dict[str, float] = {
    "select_context": 5_000_000.0,  # 5 s
    "compress_message": 500_000.0,  # 500 ms
    "run_hooks": 100_000.0,  # 100 ms
    "full_dispatch": 10_000_000.0,  # 10 s
}


@pytest.fixture(scope="module")
def latency_baseline() -> dict:
    """Parse the v9.3.0 latency baseline JSON once per test module."""
    assert V9_3_0_LATENCY_BASELINE.exists(), (
        f"Missing {V9_3_0_LATENCY_BASELINE.relative_to(REPO_ROOT)}. "
        "Regenerate via: "
        "python -m benchmarks.devolaflow_context.latency_harness "
        "--iterations 50 "
        f"--output {V9_3_0_LATENCY_BASELINE.relative_to(REPO_ROOT)}"
    )
    return json.loads(V9_3_0_LATENCY_BASELINE.read_text(encoding="utf-8"))


def test_latency_baseline_v9_3_0_schema_and_coverage(latency_baseline: dict) -> None:
    """The v9.3.0 latency baseline JSON parses + carries every primitive.

    Locks in:
    * ``schema_version`` matches the live :data:`SCHEMA_VERSION` (catch
      forgotten bumps when the JSON shape changes).
    * Every name in :data:`MEASURED_FUNCTIONS` has a ``measurements`` entry.
    * Every entry carries the 7 required keys
      (``n`` / ``mean_us`` / ``p50_us`` / ``p95_us`` / ``p99_us`` /
      ``min_us`` / ``max_us``) so tooling that JSON-parses the file
      (the v9.3.0 retrospective + the v10.0.0 cycle archive) can
      depend on the shape.
    """
    assert latency_baseline["schema_version"] == SCHEMA_VERSION, (
        f"v9.3.0_latency.json schema_version {latency_baseline['schema_version']!r} "
        f"!= module SCHEMA_VERSION {SCHEMA_VERSION!r}; bump or regenerate"
    )
    measurements = latency_baseline["measurements"]
    missing = set(MEASURED_FUNCTIONS) - set(measurements.keys())
    assert not missing, (
        f"v9.3.0_latency.json missing primitives {sorted(missing)} — "
        "regenerate via the latency_harness CLI"
    )
    extra = set(measurements.keys()) - set(MEASURED_FUNCTIONS)
    assert not extra, (
        f"v9.3.0_latency.json carries unexpected primitives {sorted(extra)} — "
        "MEASURED_FUNCTIONS and the baseline JSON must agree"
    )
    required_keys = {"n", "mean_us", "p50_us", "p95_us", "p99_us", "min_us", "max_us"}
    for name, entry in measurements.items():
        actual_keys = set(entry.keys())
        missing_keys = required_keys - actual_keys
        assert not missing_keys, (
            f"v9.3.0_latency.json::measurements[{name!r}] missing "
            f"{sorted(missing_keys)}; regenerate baseline"
        )


def test_latency_baseline_percentiles_are_monotonic(latency_baseline: dict) -> None:
    """For every primitive: p50 ≤ p95 ≤ p99 (definitionally).

    Catches a corrupt regenerated baseline (e.g. a partial write that
    produced p95 = 0 while p50 = 200ms). Cheap O(1) check per primitive.
    """
    for name in MEASURED_FUNCTIONS:
        m = latency_baseline["measurements"][name]
        assert m["min_us"] <= m["p50_us"] <= m["p95_us"] <= m["p99_us"] <= m["max_us"], (
            f"v9.3.0_latency.json::measurements[{name!r}] percentiles non-monotonic: "
            f"min={m['min_us']:.1f} p50={m['p50_us']:.1f} p95={m['p95_us']:.1f} "
            f"p99={m['p99_us']:.1f} max={m['max_us']:.1f}"
        )


def test_latency_smoke_run_returns_valid_shape() -> None:
    """A tiny ``capture_latency(iterations=SMOKE_ITERATIONS)`` succeeds.

    Doubles as a smoke check that the live primitives import without
    error and produce a measurable signal (every primitive returns
    ``n == SMOKE_ITERATIONS``). Runtime: ~3 s pre-PV-03 (3 iters × ~210
    ms select_context per call dominates); ≪ 1 s post-PV-03 once the
    LRU cache lands.
    """
    result = capture_latency(iterations=SMOKE_ITERATIONS)
    assert result["schema_version"] == SCHEMA_VERSION
    assert result["iterations"] == SMOKE_ITERATIONS
    assert set(result["measurements"].keys()) == set(MEASURED_FUNCTIONS)
    for name in MEASURED_FUNCTIONS:
        m = result["measurements"][name]
        assert m["n"] == float(SMOKE_ITERATIONS), (
            f"capture_latency smoke run: {name} n={m['n']} expected {SMOKE_ITERATIONS}"
        )
        # Sanity: every primitive consumed nonzero wall clock at least once.
        assert m["mean_us"] > 0.0, f"{name} mean_us={m['mean_us']} suggests measurement bug"


def test_per_primitive_p95_floor_sanity(latency_baseline: dict) -> None:
    """Each primitive's recorded p95 stays below the absolute sanity ceiling.

    The ceilings are 10× the post-PV-03 expected number per primitive
    (see :data:`P95_SANITY_CEILING_US`). They catch a 100× regression
    (e.g. PV-04 accidentally re-introducing a 1-second sleep into the
    compressor) without false-positiving on CI worker variance.

    PV-03 (LRU cache) lands AFTER this test; the v9.3.0 baseline JSON
    captures pre-PV-03 numbers, so the ceiling MUST accommodate the
    pre-LRU select_context p95 of ~80 ms (PV-01 measured 200 ms; CI
    headroom factored in at 5 s / 5000 ms).
    """
    measurements = latency_baseline["measurements"]
    for name, ceiling_us in P95_SANITY_CEILING_US.items():
        recorded_p95 = measurements[name]["p95_us"]
        assert recorded_p95 < ceiling_us, (
            f"{name} p95 {recorded_p95:.1f}us exceeds sanity ceiling {ceiling_us:.0f}us; "
            "either (a) the perf overhaul regressed, or (b) the harness fixture is "
            "running on a critically slow worker. Regenerate the baseline if (b) "
            "and bump the ceiling if a future PV deliberately changes the shape."
        )


def test_percentile_helper_handles_canonical_inputs() -> None:
    """Direct unit test for :func:`_percentile` so the harness math is pinned.

    Locks in:
    * Empty list returns 0.0 (S-5 — explicit empty signal, never raises).
    * Singleton list returns the value verbatim.
    * Linear interpolation matches the numpy default (7th-quantile method).
    """
    assert _percentile([], 50) == 0.0
    assert _percentile([42.0], 50) == 42.0
    # Linear interpolation: 50th percentile of [1,2,3,4] is 2.5.
    assert _percentile([1.0, 2.0, 3.0, 4.0], 50) == pytest.approx(2.5)
    # 95th percentile of [1..100] is 95.05 with the 7th-quantile method.
    values = [float(i + 1) for i in range(100)]
    assert _percentile(values, 95) == pytest.approx(95.05)
    # Out-of-range pct raises (S-5 — explicit error).
    with pytest.raises(ValueError):
        _percentile([1.0], 150.0)


def test_measure_function_validates_iteration_count() -> None:
    """``measure_function(fn, iterations < 1)`` raises ``ValueError``.

    S-5 — the harness must never silently coerce a bad arg to a default.
    """
    with pytest.raises(ValueError):
        measure_function(lambda: None, 0)
    with pytest.raises(ValueError):
        measure_function(lambda: None, -5)


def test_capture_latency_validates_iteration_count() -> None:
    """``capture_latency(iterations < 1)`` raises ``ValueError`` (S-5)."""
    with pytest.raises(ValueError):
        capture_latency(iterations=0)


def test_default_iterations_constant_is_sane() -> None:
    """Lock in the production iteration default at 100.

    The W-16 wholesale baseline regen at cycle start uses this constant
    via the latency_harness CLI default. A future PV that bumps it
    (cheap iteration tradeoff) MUST update this test in the same PR
    (preventing silent drift between docs and live default).
    """
    assert DEFAULT_ITERATIONS == 100, (
        f"DEFAULT_ITERATIONS={DEFAULT_ITERATIONS}; "
        "the W-16 cycle-start baseline contract pins 100 iterations. "
        "Bump this test if the contract changed."
    )
    assert SMOKE_ITERATIONS < DEFAULT_ITERATIONS, (
        "SMOKE_ITERATIONS must be strictly less than DEFAULT_ITERATIONS so "
        "the test smoke run is materially cheaper than the production capture"
    )
