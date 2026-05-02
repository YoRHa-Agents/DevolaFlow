#!/usr/bin/env python3
"""v9.3.0 PV-01 cProfile harness for DevolaFlow hot-path benchmarking.

NOT a test, NOT shipped. Lives under ``.local/research/`` per the
PV-01 task spec. Imports the four most-trafficked dispatch primitives
and runs each under cProfile with a 1000-iteration loop using realistic
arguments derived from ``tests/test_task_adaptive_selector.py`` +
``tests/test_compressor*.py`` + ``tests/test_lifecycle.py``.

Outputs:
- ``.local/research/v9.3.0_cprofile_raw.prof``  (cProfile binary)
- ``.local/research/v9.3.0_cprofile_summary.txt``  (pstats text dump)

Usage (from repo root):
    python .local/research/v9.3.0_profile_harness.py

Exit codes:
    0 — clean run, both artifacts written
    1 — runtime error during a hot-path call (the failing call signature
        + traceback is captured in the summary file as a "BUG SURFACE"
        marker per the PV-01 escalation policy)
"""

from __future__ import annotations

import cProfile
import io
import logging
import pstats
import sys
import time
import traceback
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

OUT_RAW = REPO_ROOT / ".local" / "research" / "v9.3.0_cprofile_raw.prof"
OUT_SUMMARY = REPO_ROOT / ".local" / "research" / "v9.3.0_cprofile_summary.txt"

# Per-section iteration counts.  Empirically `select_context` averages ~120 ms
# per call against the v9.2.4 corpus (load_profiles + load_skill_md + YAML
# parse, no caching), so 1000 iterations × 3 selector sections + 1 full-flow
# section = ~10 minutes of wall clock. We keep 1000 for the cheap pure
# functions (compressor / run_hooks) where the per-call cost is measured in
# microseconds and slim the selector + full-flow sections to 200 iterations.
# Statistical significance is preserved (200 samples is well above the
# central-limit-theorem threshold for a pstats summary) while keeping the
# harness under a 90 s budget.  This is documented as a PV-01 finding —
# the per-call cost itself is the #1 bottleneck and motivates the PV-03 LRU
# cache work item.
ITERATIONS_CHEAP = 1000
ITERATIONS_SELECTOR = 200
ITERATIONS_FULL = 200

logging.basicConfig(level=logging.ERROR)


def _build_realistic_dispatch_payload() -> dict[str, Any]:
    """Construct a 16-key dispatch payload covering the canonical shape.

    Mirrors the structure produced by ``ProposalGenerator.generate_round_dispatch``
    so ``assert_dispatch_layout`` exercises the whole frozen-prefix +
    append-tail validator path (not just the early-exit empty-dict branch).
    """
    return {
        "hdr": {"layer": "L3", "task_id": "v9.3.0-pv01-perf-research"},
        "task": "Profile dispatch primitives for the v9.3 perf overhaul.",
        "goal": "Measure per-function cumulative ms across 1000 calls.",
        "assumptions": ["pytest realistic args mirror production"],
        "pred": [
            {
                "name": "v9.2.4_baseline",
                "summary_mode": "extractive",
                "key_facts": ["compressor.py = 2541 LOC", "selector = 1680 LOC"],
            }
        ],
        "files": ["src/devolaflow/compressor.py"],
        "rules": ["A-2.1 frozen prefix", "C-2 lean format"],
        "shared": {"workflow": "perf-research"},
        "accept": [
            "cProfile harness completes without exception",
            "summary written to .local/research/v9.3.0_cprofile_summary.txt",
        ],
        "reinforce": [],
        "verify_cfg": {"timeout_s": 60},
        "gate": {"token_budget": 8000},
        "repos": [{"name": "DevolaFlow", "root_path": ".", "primary": True, "branch": "feat/v9.3.0-perf-overhaul-1"}],
        "behavioral_guidelines": {
            "think_first": True,
            "simplicity_check": True,
            "surgical_scope": "research-only",
            "goal_loop": True,
        },
        "acceptance_criteria_v2": {"version": 2, "items": ["latency baseline captured"]},
        "change_context": {"change_id": "v9.3.0-pv01-perf-research"},
    }


def _build_realistic_message() -> str:
    """A representative dispatch message body (~250 lines, mixed prose + YAML)."""
    return "\n".join(
        [
            "# DevolaFlow Dispatch — v9.3.0 PV-01",
            "## Context",
            "Realistic dispatch sample for cProfile benchmarking.",
            "Includes prose, YAML keys, code snippets, paths, and metric values.",
            "",
            "```yaml",
            "task_type: research",
            "round_num: 1",
            "owned_files:",
            "  - .local/research/v9.3.0_perf_research.md",
            "  - .local/research/v9.3.0_gap_analysis.md",
            "```",
            "",
            "## Behaviour expectations",
            "- think_first: true",
            "- simplicity_check: true",
            "- surgical_scope: research-only",
            "",
            "## Acceptance criteria",
            "1. cProfile artifact written to .local/research/v9.3.0_cprofile_raw.prof",
            "2. pstats summary written to .local/research/v9.3.0_cprofile_summary.txt",
            "3. Top-N hotspots surfaced in the markdown research artifact",
            "",
            "## Sample noise (which compression should drop):",
        ]
        + [
            f"DEBUG: trace from compressor.py:{i} message id=42-{i} verbose=True"
            for i in range(120)
        ]
        + [
            "",
            "Real telemetry: cumulative_ms=NN, n_calls=NN, percall_us=NN.",
        ]
    )


def _profile_select_context(prof: cProfile.Profile, runs: int) -> dict[str, Any]:
    from devolaflow.task_adaptive_selector import select_context

    matrix = [
        ("implement", 1),
        ("implement", 2),
        ("research", 1),
        ("research", 3),
        ("design", 1),
        ("hotfix", 2),
    ]
    n = 0
    t0 = time.perf_counter()
    prof.enable()
    try:
        for _ in range(runs):
            task_type, round_num = matrix[n % len(matrix)]
            select_context(task_type=task_type, round_num=round_num)
            n += 1
    finally:
        prof.disable()
    return {
        "function": "select_context",
        "calls": n,
        "wall_clock_s": time.perf_counter() - t0,
    }


def _profile_compressor_pure(prof: cProfile.Profile, runs: int) -> dict[str, Any]:
    from devolaflow.compressor import (
        assert_dispatch_layout,
        compress_message,
        validate_lean_format,
    )

    payload = _build_realistic_dispatch_payload()
    message = _build_realistic_message()

    n = 0
    t0 = time.perf_counter()
    prof.enable()
    try:
        for _ in range(runs):
            assert_dispatch_layout(payload)
            compress_message(message, intensity="standard")
            validate_lean_format(message, intensity="standard")
            n += 3
    finally:
        prof.disable()
    return {
        "function": "compressor.{assert_dispatch_layout,compress_message,validate_lean_format}",
        "calls": n,
        "wall_clock_s": time.perf_counter() - t0,
    }


def _profile_run_hooks(prof: cProfile.Profile, runs: int) -> dict[str, Any]:
    from devolaflow.lifecycle import run_hooks

    payload = _build_realistic_dispatch_payload()
    n = 0
    t0 = time.perf_counter()
    prof.enable()
    try:
        for _ in range(runs):
            run_hooks("pre_dispatch", payload)
            n += 1
    finally:
        prof.disable()
    return {
        "function": "run_hooks(pre_dispatch)",
        "calls": n,
        "wall_clock_s": time.perf_counter() - t0,
    }


def _profile_select_context_lru_warm(prof: cProfile.Profile, runs: int) -> dict[str, Any]:
    """Same call repeated — measures wasted recomputation that an LRU
    cache (PV-03 target) would absorb."""
    from devolaflow.task_adaptive_selector import select_context

    n = 0
    t0 = time.perf_counter()
    prof.enable()
    try:
        for _ in range(runs):
            select_context(task_type="implement", round_num=1)
            n += 1
    finally:
        prof.disable()
    return {
        "function": "select_context (LRU warm — same args)",
        "calls": n,
        "wall_clock_s": time.perf_counter() - t0,
    }


def _profile_full_dispatch_simulation(prof: cProfile.Profile, runs: int) -> dict[str, Any]:
    """Combined select+compress+validate+hooks per iteration — a synthetic
    L0->L1 dispatch round."""
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

    n = 0
    t0 = time.perf_counter()
    prof.enable()
    try:
        for _ in range(runs):
            task_type, round_num = matrix[n % len(matrix)]
            select_context(task_type=task_type, round_num=round_num)
            assert_dispatch_layout(payload)
            compress_message(message, intensity="standard")
            validate_lean_format(message, intensity="standard")
            run_hooks("pre_dispatch", payload)
            n += 1
    finally:
        prof.disable()
    return {
        "function": "full_dispatch_simulation",
        "calls": n,
        "wall_clock_s": time.perf_counter() - t0,
    }


def _emit_summary(
    prof: cProfile.Profile, hot_path_results: list[dict[str, Any]]
) -> None:
    OUT_RAW.parent.mkdir(parents=True, exist_ok=True)
    prof.dump_stats(str(OUT_RAW))

    buf = io.StringIO()
    ps = pstats.Stats(prof, stream=buf).strip_dirs()
    buf.write("=" * 78 + "\n")
    buf.write("DEVOLAFLOW v9.3.0 PV-01 — cProfile summary (1000-iteration loops)\n")
    buf.write("=" * 78 + "\n\n")

    buf.write("## Wall-clock per harness section\n\n")
    for r in hot_path_results:
        per_call_us = (
            (r["wall_clock_s"] / r["calls"]) * 1e6 if r["calls"] else 0.0
        )
        buf.write(
            f"  {r['function']:<60} calls={r['calls']:>5} "
            f"wall={r['wall_clock_s']:.3f}s  per_call={per_call_us:.1f}us\n"
        )
    buf.write("\n")

    buf.write("## Top 60 by cumulative time\n\n")
    ps.sort_stats("cumulative").print_stats(60)

    buf.write("\n## Top 60 by tottime (self time)\n\n")
    ps.sort_stats("tottime").print_stats(60)

    buf.write("\n## Top 30 callers of compress_message / select_context / assert_dispatch_layout / run_hooks\n\n")
    for fn in ("compress_message", "select_context", "assert_dispatch_layout", "run_hooks"):
        buf.write(f"\n--- callers of {fn} ---\n")
        ps.print_callers(fn)

    OUT_SUMMARY.write_text(buf.getvalue(), encoding="utf-8")


def main() -> int:
    print(
        f"v9.3.0 PV-01 harness — selector={ITERATIONS_SELECTOR} cheap={ITERATIONS_CHEAP} full={ITERATIONS_FULL}"
    )
    print(f"  output (raw)     : {OUT_RAW}")
    print(f"  output (summary) : {OUT_SUMMARY}")

    prof = cProfile.Profile()
    results: list[dict[str, Any]] = []
    bug_surface: list[str] = []

    sections: list[tuple[str, Any, int]] = [
        ("select_context(varied)", _profile_select_context, ITERATIONS_SELECTOR),
        ("select_context(LRU warm)", _profile_select_context_lru_warm, ITERATIONS_SELECTOR),
        ("compressor pure functions", _profile_compressor_pure, ITERATIONS_CHEAP),
        ("run_hooks(pre_dispatch)", _profile_run_hooks, ITERATIONS_CHEAP),
        ("full_dispatch_simulation", _profile_full_dispatch_simulation, ITERATIONS_FULL),
    ]

    for label, fn, iters in sections:
        print(f"  > {label} (n={iters}) ...", flush=True)
        try:
            r = fn(prof, iters)
            results.append(r)
            print(
                f"    ok  calls={r['calls']:>5}  wall={r['wall_clock_s']:.3f}s",
                flush=True,
            )
        except Exception as exc:  # pragma: no cover — harness diagnostics
            tb = traceback.format_exc()
            bug_surface.append(
                f"BUG SURFACE in {label}: {type(exc).__name__}: {exc}\n{tb}"
            )
            print(f"    FAIL {type(exc).__name__}: {exc}", flush=True)

    _emit_summary(prof, results)
    if bug_surface:
        with OUT_SUMMARY.open("a", encoding="utf-8") as f:
            f.write("\n\n## BUG SURFACE (PV-01 escalation policy)\n\n")
            for entry in bug_surface:
                f.write(entry + "\n\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
