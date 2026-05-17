#!/usr/bin/env python3
"""Generate a full-coverage EvoBench baseline (all scenarios).

Reads every YAML under ``scenarios/``, runs the context selector + evaluator,
and writes a baseline JSON keyed by scenario name.

Closes C1 from the v6.0.0 improvement advice doc: v2.1.0_baseline.json covered
only 3 of 29 scenarios, so 26 scenarios had no regression guard.

Determinism note (v12.4.0 PV-02 — closes v12.3.0 retro §4.2 learning):
    The pytest harness pins ``sys.modules["tiktoken"] = None`` via the
    autouse ``_force_fallback_token_estimator`` fixture in
    ``tests/conftest.py`` so benchmark scoring uses the deterministic
    ``len(text) // 4`` fallback path regardless of whether ``tiktoken``
    is installed in the runner's venv. Standalone regen scripts that do
    NOT load conftest would otherwise produce a different composite
    score from pytest (~7pp drift on the composite axis). v12.3.0 PV-04
    hit this with a 3-attempt trial-and-error baseline regen.
    v12.4.0 PV-02 applies "Option B" from the conftest docstring —
    set ``sys.modules["tiktoken"] = None`` at module-import time, BEFORE
    any ``devolaflow`` module gets a chance to import tiktoken — so
    standalone regens automatically match pytest scoring.

Usage
-----

    # default: writes baselines/v<CURRENT_VERSION>_baseline.json
    python benchmarks/devolaflow_context/generate_baseline.py

    # custom output path
    python benchmarks/devolaflow_context/generate_baseline.py \
        --output benchmarks/devolaflow_context/baselines/v6.0.5_baseline.json

Repository: https://github.com/YoRHa-Agents/DevolaFlow
"""

from __future__ import annotations

import sys

# v12.4.0 PV-02 — pin tiktoken=None at module import (Option B from
# ``tests/conftest.py::_force_fallback_token_estimator`` docstring).
# MUST execute BEFORE any ``devolaflow`` / ``benchmarks`` import below
# so the fallback token estimator is selected at first import. Do NOT
# move this assignment; ordering is load-bearing per the conftest
# docstring (the assignment hides any installed tiktoken from later
# ``import tiktoken`` calls anywhere in the import graph).
sys.modules["tiktoken"] = None  # noqa: E402  # load-bearing — see module docstring

import argparse  # noqa: E402
import json  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any  # noqa: E402

# Support `python benchmarks/devolaflow_context/generate_baseline.py` from the
# repo root in addition to `python -m benchmarks.devolaflow_context.generate_baseline`.
# When invoked as a script, __package__ is empty and sibling imports fail.
if __package__ in (None, ""):
    _repo_root = Path(__file__).resolve().parents[2]
    if str(_repo_root) not in sys.path:
        sys.path.insert(0, str(_repo_root))
    if str(_repo_root / "src") not in sys.path:
        sys.path.insert(0, str(_repo_root / "src"))

from benchmarks.devolaflow_context.runner import (  # noqa: E402
    BASELINES_DIR,
    discover_scenarios,
    load_scenario,
    run_scenario,
)

# Fields to persist per scenario. Keep in lockstep with
# ``BenchmarkScore.to_dict`` output; downstream tests assert these keys exist.
BASELINE_FIELDS: tuple[str, ...] = (
    "composite",
    "information_density",
    "section_relevance",
    "budget_utilization",
    "noise_ratio",
    "total_tokens",
    "budget",
    "selected_count",
)


def _default_output_path() -> Path:
    """Return ``baselines/v<devolaflow.__version__>_baseline.json``."""
    try:
        from devolaflow import __version__
    except ImportError:
        __version__ = "unknown"
    return BASELINES_DIR / f"v{__version__}_baseline.json"


def generate_full_baseline(output_path: Path | None = None) -> Path:
    """Run every scenario and write a baseline JSON keyed by scenario name.

    Parameters
    ----------
    output_path:
        File path to write. Defaults to ``baselines/v<version>_baseline.json``.

    Returns
    -------
    The path written.
    """
    if output_path is None:
        output_path = _default_output_path()

    scenario_paths = discover_scenarios("all")
    if not scenario_paths:
        raise RuntimeError(
            "No scenarios discovered under "
            f"{Path(__file__).parent / 'scenarios'}. "
            "Cannot generate an empty baseline."
        )

    baselines: dict[str, dict[str, Any]] = {}
    for path in scenario_paths:
        scenario_data = load_scenario(path)
        score = run_scenario(scenario_data)
        score_dict = score.to_dict()
        entry: dict[str, Any] = {"scenario_name": score.scenario_name}
        entry["profile_name"] = score.profile_name
        for key in BASELINE_FIELDS:
            entry[key] = score_dict[key]
        baselines[score.scenario_name] = entry

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(baselines, f, indent=2, sort_keys=True)
    return output_path


def _main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a full EvoBench baseline covering every scenario under "
            "benchmarks/devolaflow_context/scenarios/."
        )
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=("Output JSON path. Default: baselines/v<devolaflow.__version__>_baseline.json"),
    )
    args = parser.parse_args()

    out = generate_full_baseline(output_path=args.output)
    print(f"Baseline written: {out}")
    with open(out) as f:
        data = json.load(f)
    print(f"Scenarios covered: {len(data)}")


if __name__ == "__main__":
    _main()
