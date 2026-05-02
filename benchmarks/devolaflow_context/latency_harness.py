#!/usr/bin/env python3
"""Latency harness for DevolaFlow dispatch primitives.

Production landing of the v9.3.0 PV-01 cProfile harness
(``.local/research/v9.3.0_profile_harness.py``). Provides:

* A pure measurement API (:func:`measure_function`,
  :func:`capture_latency`) consumed by ``tests/test_dispatch_latency.py``
  for regression guards (W-4 / SI-4 + the v9.3.0 cycle-start latency
  contract).
* A CLI entry point (``python -m benchmarks.devolaflow_context.latency_harness``)
  for capturing fresh percentile baselines into JSON files under
  ``benchmarks/devolaflow_context/baselines/v<version>_latency.json``.

Measured primitives (4):

1. ``select_context`` — ``task_adaptive_selector.select_context`` over a
   varied (task_type, round_num) matrix. Pre-PV-03 the p50 is ~210 ms
   per call (proven by ``v9.3.0_cprofile_summary.txt``); post-PV-03 the
   warm path is ~50-200 µs.
2. ``compress_message`` — ``compressor.compress_message`` over a
   representative dispatch message body (~150 lines, mixed prose +
   YAML + debug noise).
3. ``run_hooks`` — ``lifecycle.run_hooks('pre_dispatch', payload)`` over
   the canonical 16-key dispatch payload. Per the PV-01 finding this is
   ~9 µs per call — calibration anchor that proves the harness is
   working when the absolute number lands < 1 ms.
4. ``full_dispatch`` — composite of the four steps above
   (``select_context`` + ``assert_dispatch_layout`` +
   ``compress_message`` + ``validate_lean_format`` +
   ``run_hooks``) in one round, mirroring the L0→L1 dispatch shape.

Output JSON shape (versioned by :data:`SCHEMA_VERSION` = ``1``):

.. code-block:: json

    {
      "schema_version": 1,
      "version": "9.3.0",
      "iterations": 100,
      "captured_at": "2026-05-02T07:00:00+00:00",
      "measurements": {
        "select_context": {
          "n": 100,
          "mean_us": 210000.0,
          "p50_us": 210000.0,
          "p95_us": 230000.0,
          "p99_us": 240000.0,
          "min_us": 200000.0,
          "max_us": 250000.0
        },
        ...
      }
    }

Repository: https://github.com/YoRHa-Agents/DevolaFlow
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# When invoked as a script (``python benchmarks/.../latency_harness.py``),
# __package__ is empty and the sibling import below would fail. Mirror the
# generate_baseline.py guard so both invocations work.
if __package__ in (None, ""):
    _repo_root = Path(__file__).resolve().parents[2]
    if str(_repo_root) not in sys.path:
        sys.path.insert(0, str(_repo_root))
    if str(_repo_root / "src") not in sys.path:
        sys.path.insert(0, str(_repo_root / "src"))


SCHEMA_VERSION: int = 1
"""Schema version for the latency JSON file. Bump when the shape changes."""

REPO_ROOT: Path = Path(__file__).resolve().parents[2]
BASELINES_DIR: Path = REPO_ROOT / "benchmarks" / "devolaflow_context" / "baselines"

DEFAULT_ITERATIONS: int = 100
"""Default iteration count for production baseline captures."""

SMOKE_ITERATIONS: int = 3
"""Tiny iteration count tests use to verify the harness shape without
spending the full ~120 s a 100-iter capture takes pre-PV-03."""

# The 4 measured primitive names — kept as a module-level tuple so tests
# can assert exact coverage without depending on dict iteration order.
MEASURED_FUNCTIONS: tuple[str, ...] = (
    "select_context",
    "compress_message",
    "run_hooks",
    "full_dispatch",
)


# ---------------------------------------------------------------------------
# Pure utility — percentile computation. Linear interpolation; matches the
# numpy.percentile default behaviour for the percentiles we care about
# (50, 95, 99). Implementing in pure Python avoids a numpy import at hot
# path and keeps the harness dependency-free.
# ---------------------------------------------------------------------------


def _percentile(values: list[float], pct: float) -> float:
    """Compute *pct* percentile (0-100) of *values* via linear interpolation.

    Matches the default ``numpy.percentile`` formula (linear / 7th-quantile
    method). Returns ``0.0`` for an empty list (S-5 — explicit empty signal
    so callers can branch instead of raising).
    """
    if not values:
        return 0.0
    if not 0.0 <= pct <= 100.0:
        raise ValueError(f"_percentile: pct {pct!r} must be in [0, 100]")
    sorted_values = sorted(values)
    if len(sorted_values) == 1:
        return sorted_values[0]
    k = (len(sorted_values) - 1) * pct / 100.0
    f = int(k)
    c = min(f + 1, len(sorted_values) - 1)
    if f == c:
        return sorted_values[f]
    return sorted_values[f] * (c - k) + sorted_values[c] * (k - f)


def measure_function(fn: Callable[[], Any], iterations: int) -> dict[str, float]:
    """Run ``fn()`` *iterations* times and return percentile stats in microseconds.

    Returns a dict with keys ``n`` / ``mean_us`` / ``p50_us`` / ``p95_us`` /
    ``p99_us`` / ``min_us`` / ``max_us``. The harness is intentionally
    minimal — no warmup pass, no GC disable, no timer-resolution
    fallback — because the regression guard cares about the relative
    delta after PV-03, not absolute precision at the < 1 µs floor.

    Raises ``ValueError`` when *iterations* < 1 (S-5).
    """
    if iterations < 1:
        raise ValueError(f"measure_function: iterations must be >= 1, got {iterations!r}")

    durations_us: list[float] = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        fn()
        durations_us.append((time.perf_counter() - t0) * 1e6)

    return {
        "n": float(len(durations_us)),
        "mean_us": sum(durations_us) / len(durations_us),
        "p50_us": _percentile(durations_us, 50),
        "p95_us": _percentile(durations_us, 95),
        "p99_us": _percentile(durations_us, 99),
        "min_us": min(durations_us),
        "max_us": max(durations_us),
    }


# ---------------------------------------------------------------------------
# Realistic argument fixtures — verbatim from the v9.3.0 PV-01 harness so
# the production module measures the SAME shape. Centralising them here
# keeps test arguments and CLI arguments in lockstep (no per-call drift).
# ---------------------------------------------------------------------------


def _build_realistic_dispatch_payload() -> dict[str, Any]:
    """Construct a 16-key dispatch payload covering the canonical layout."""
    return {
        "hdr": {"layer": "L3", "task_id": "v9.3.0-pv02-latency-harness"},
        "task": "Measure dispatch primitive latency for the v9.3 perf overhaul.",
        "goal": "Capture per-function p50/p95/p99 across 100 iterations.",
        "assumptions": ["fixture mirrors production payload shape"],
        "pred": [
            {
                "name": "v9.2.4_baseline",
                "summary_mode": "extractive",
                "key_facts": ["compressor.py = 2541 LOC", "selector = 1680 LOC"],
            }
        ],
        "files": ["src/devolaflow/compressor.py"],
        "rules": ["A-2.1 frozen prefix", "C-2 lean format"],
        "shared": {"workflow": "perf-overhaul-1"},
        "accept": [
            "harness completes without exception",
            "baseline JSON written to baselines/v9.3.0_latency.json",
        ],
        "reinforce": [],
        "verify_cfg": {"timeout_s": 60},
        "gate": {"token_budget": 8000},
        "repos": [
            {
                "name": "DevolaFlow",
                "root_path": ".",
                "primary": True,
                "branch": "feat/v9.3.0-perf-overhaul-1",
            }
        ],
        "behavioral_guidelines": {
            "think_first": True,
            "simplicity_check": True,
            "surgical_scope": "module",
            "goal_loop": True,
        },
        "acceptance_criteria_v2": {
            "version": 2,
            "items": ["latency baseline captured", "regression guard wired"],
        },
        "change_context": {"change_id": "v9.3.0-pv02-latency-harness"},
    }


def _build_realistic_message() -> str:
    """A representative dispatch message body (~150 lines, mixed)."""
    return "\n".join(
        [
            "# DevolaFlow Dispatch — v9.3.0 PV-02",
            "## Context",
            "Realistic dispatch sample for latency benchmarking.",
            "Includes prose, YAML keys, code snippets, paths, and metric values.",
            "",
            "```yaml",
            "task_type: implement",
            "round_num: 1",
            "owned_files:",
            "  - benchmarks/devolaflow_context/latency_harness.py",
            "  - tests/test_dispatch_latency.py",
            "```",
            "",
            "## Behaviour expectations",
            "- think_first: true",
            "- simplicity_check: true",
            "- surgical_scope: module",
            "",
            "## Acceptance criteria",
            "1. latency baseline captured with p50/p95/p99 percentiles",
            "2. regression guards pass for all 4 measured primitives",
            "3. `python -m benchmarks.devolaflow_context.latency_harness --iterations 100`",
            "   produces a fresh baseline JSON file",
            "",
            "## Sample noise (which compression should drop):",
        ]
        + [f"DEBUG: trace from compressor.py:{i} message id=42-{i} verbose=True" for i in range(80)]
        + ["", "Real telemetry: cumulative_ms=NN, n_calls=NN, percall_us=NN."]
    )


# ---------------------------------------------------------------------------
# Per-primitive callable builders. Each returns a zero-arg ``Callable``
# that ``measure_function`` invokes in a tight loop.
# ---------------------------------------------------------------------------


def _build_select_context_call() -> Callable[[], Any]:
    """Build a varied-args callable for ``select_context``.

    Cycles through 5 (task_type, round_num) tuples so the LRU cache
    landing in PV-03 has multiple distinct keys to remember (proves the
    cache works for the production access pattern, not just a single
    hot key).
    """
    from devolaflow.task_adaptive_selector import select_context

    matrix = [
        ("implement", 1),
        ("research", 1),
        ("design", 1),
        ("hotfix", 2),
        ("review", 1),
    ]
    state = {"i": 0}

    def call() -> None:
        task_type, round_num = matrix[state["i"] % len(matrix)]
        state["i"] += 1
        select_context(task_type=task_type, round_num=round_num)

    return call


def _build_compress_message_call() -> Callable[[], Any]:
    """Build a callable for ``compress_message`` over a fixed message."""
    from devolaflow.compressor import compress_message

    message = _build_realistic_message()

    def call() -> None:
        compress_message(message, intensity="standard")

    return call


def _build_run_hooks_call() -> Callable[[], Any]:
    """Build a callable for ``run_hooks('pre_dispatch', payload)``.

    Calibration anchor: should land < 100 µs / call even on slow CI; the
    PV-01 cProfile run measured 9.2 µs / call on a beefy dev box.
    """
    from devolaflow.lifecycle import run_hooks

    payload = _build_realistic_dispatch_payload()

    def call() -> None:
        run_hooks("pre_dispatch", payload)

    return call


def _build_full_dispatch_call() -> Callable[[], Any]:
    """Build a callable for the composite L0→L1 dispatch shape.

    Mirrors :func:`_profile_full_dispatch_simulation` in the PV-01
    harness but as a reusable module-level function.
    """
    from devolaflow.compressor import (
        assert_dispatch_layout,
        compress_message,
        validate_lean_format,
    )
    from devolaflow.lifecycle import run_hooks
    from devolaflow.task_adaptive_selector import select_context

    payload = _build_realistic_dispatch_payload()
    message = _build_realistic_message()
    matrix = [
        ("implement", 1),
        ("research", 1),
        ("design", 1),
        ("hotfix", 2),
        ("review", 1),
    ]
    state = {"i": 0}

    def call() -> None:
        task_type, round_num = matrix[state["i"] % len(matrix)]
        state["i"] += 1
        select_context(task_type=task_type, round_num=round_num)
        assert_dispatch_layout(payload)
        compress_message(message, intensity="standard")
        validate_lean_format(message, intensity="standard")
        run_hooks("pre_dispatch", payload)

    return call


CALL_BUILDERS: dict[str, Callable[[], Callable[[], Any]]] = {
    "select_context": _build_select_context_call,
    "compress_message": _build_compress_message_call,
    "run_hooks": _build_run_hooks_call,
    "full_dispatch": _build_full_dispatch_call,
}


# ---------------------------------------------------------------------------
# Top-level capture orchestrator.
# ---------------------------------------------------------------------------


def _read_devolaflow_version() -> str:
    """Resolve ``devolaflow.__version__`` (falls back to ``"unknown"``)."""
    try:
        from devolaflow import __version__

        return __version__
    except ImportError:  # pragma: no cover — defensive
        return "unknown"


def capture_latency(iterations: int = DEFAULT_ITERATIONS) -> dict[str, Any]:
    """Run all 4 primitives *iterations* times and return the result dict.

    The returned shape mirrors the on-disk JSON file (see module
    docstring). ``schema_version`` is always
    :data:`SCHEMA_VERSION`. ``captured_at`` is an ISO-8601 UTC timestamp.

    Raises ``ValueError`` when *iterations* < 1 (S-5).
    """
    if iterations < 1:
        raise ValueError(f"capture_latency: iterations must be >= 1, got {iterations!r}")

    measurements: dict[str, dict[str, float]] = {}
    for name in MEASURED_FUNCTIONS:
        builder = CALL_BUILDERS[name]
        call = builder()
        measurements[name] = measure_function(call, iterations)

    return {
        "schema_version": SCHEMA_VERSION,
        "version": _read_devolaflow_version(),
        "iterations": iterations,
        "captured_at": datetime.now(UTC).isoformat(),
        "measurements": measurements,
    }


def write_latency_baseline(
    iterations: int = DEFAULT_ITERATIONS,
    output_path: Path | None = None,
) -> Path:
    """Capture latency and write the JSON baseline to disk.

    Parameters
    ----------
    iterations:
        Iteration count per measured primitive. Default
        :data:`DEFAULT_ITERATIONS` (100).
    output_path:
        Destination JSON path. Defaults to
        ``baselines/v<devolaflow.__version__>_latency.json``.

    Returns the resolved path.
    """
    if output_path is None:
        version = _read_devolaflow_version()
        output_path = BASELINES_DIR / f"v{version}_latency.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result = capture_latency(iterations)
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return output_path


# ---------------------------------------------------------------------------
# CLI.
# ---------------------------------------------------------------------------


def _summarise_to_stdout(result: dict[str, Any]) -> None:
    print(f"DevolaFlow latency baseline — version {result['version']}")
    print(f"  iterations    : {result['iterations']}")
    print(f"  captured_at   : {result['captured_at']}")
    print(f"  schema        : {result['schema_version']}")
    for name in MEASURED_FUNCTIONS:
        m = result["measurements"][name]
        print(
            f"  {name:<18} n={int(m['n']):>4}  "
            f"p50={m['p50_us']:>10.1f}us  "
            f"p95={m['p95_us']:>10.1f}us  "
            f"p99={m['p99_us']:>10.1f}us  "
            f"max={m['max_us']:>10.1f}us"
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Capture DevolaFlow dispatch-primitive latency percentiles. "
            "Writes JSON baseline to baselines/v<version>_latency.json by default."
        )
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=DEFAULT_ITERATIONS,
        help=f"Iterations per measured primitive (default: {DEFAULT_ITERATIONS})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output JSON path (default: baselines/v<devolaflow.__version__>_latency.json)",
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Run measurement but only print to stdout; do not touch disk",
    )
    args = parser.parse_args()

    print(f"Capturing latency with {args.iterations} iterations per primitive...")
    if args.no_write:
        result = capture_latency(args.iterations)
    else:
        out_path = (
            args.output
            if args.output is not None
            else BASELINES_DIR / f"v{_read_devolaflow_version()}_latency.json"
        )
        out_path = out_path.resolve()
        write_latency_baseline(iterations=args.iterations, output_path=out_path)
        result = json.loads(out_path.read_text(encoding="utf-8"))
        try:
            display_path: str = str(out_path.relative_to(REPO_ROOT))
        except ValueError:
            display_path = str(out_path)
        print(f"  wrote         : {display_path}")
    _summarise_to_stdout(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
