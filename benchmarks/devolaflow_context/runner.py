#!/usr/bin/env python3
"""EvoBench runner — orchestrates benchmark scenarios and reports results.

Usage:
    python -m benchmarks.devolaflow_context.runner --scenario all
    python -m benchmarks.devolaflow_context.runner --scenario hotfix_jwt
    python -m benchmarks.devolaflow_context.runner --scenario all --compare-baseline
    python -m benchmarks.devolaflow_context.runner --generate-baseline

Repository: https://github.com/YoRHa-Agents/DevolaFlow
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from benchmarks.devolaflow_context.evaluator import (
    BenchmarkScore,
    compare_to_baseline,
    evaluate_scenario,
)

SCENARIOS_DIR = Path(__file__).parent / "scenarios"
BASELINES_DIR = Path(__file__).parent / "baselines"

_selector_module = None


def _get_selector():
    global _selector_module
    if _selector_module is None:
        from devolaflow import task_adaptive_selector

        _selector_module = task_adaptive_selector
    return _selector_module


def load_scenario(path: Path) -> dict[str, Any]:
    with open(path) as f:
        return yaml.safe_load(f)


def discover_scenarios(name_filter: str = "all") -> list[Path]:
    if not SCENARIOS_DIR.is_dir():
        return []
    scenarios = sorted(SCENARIOS_DIR.glob("*.yaml"))
    if name_filter == "all":
        return scenarios
    return [s for s in scenarios if s.stem == name_filter]


def run_scenario(scenario_data: dict[str, Any]) -> BenchmarkScore:
    selector = _get_selector()
    task_type = scenario_data["task_type"]
    expected = scenario_data.get("expected_sections", [])
    unwanted = scenario_data.get("unwanted_sections", [])

    profiles_path = (
        Path(__file__).parents[2] / "workflow-system" / "agent" / "context_profiles.yaml"
    )
    result = selector.select_context(task_type, profiles_path=profiles_path)

    return evaluate_scenario(
        scenario_name=scenario_data.get("name", task_type),
        selector_result=result,
        expected_sections=expected,
        unwanted_sections=unwanted or None,
    )


def load_baseline(scenario_name: str) -> dict[str, Any] | None:
    baseline_path = BASELINES_DIR / "v2.1.0_baseline.json"
    if not baseline_path.exists():
        return None
    with open(baseline_path) as f:
        baselines = json.load(f)
    return baselines.get(scenario_name)


def run_all(
    name_filter: str = "all",
    compare_baseline: bool = False,
) -> dict[str, Any]:
    scenario_paths = discover_scenarios(name_filter)
    if not scenario_paths:
        return {"error": f"No scenarios found matching '{name_filter}'", "results": []}

    results: list[dict[str, Any]] = []
    comparisons: list[dict[str, Any]] = []
    all_pass = True

    for path in scenario_paths:
        scenario_data = load_scenario(path)
        score = run_scenario(scenario_data)
        results.append(score.to_dict())

        if compare_baseline:
            baseline = load_baseline(score.scenario_name)
            if baseline:
                cmp = compare_to_baseline(score, baseline)
                comparisons.append(cmp)
                if cmp["regressed"]:
                    all_pass = False

    report = {
        "results": results,
        "scenario_count": len(results),
        "overall_verdict": "PASS" if all_pass else "REGRESSION",
    }
    if comparisons:
        report["baseline_comparisons"] = comparisons

    return report


def generate_baseline(name_filter: str = "all") -> Path:
    """Run all scenarios and write results as the baseline file."""
    scenario_paths = discover_scenarios(name_filter)
    baselines: dict[str, dict[str, Any]] = {}

    for path in scenario_paths:
        scenario_data = load_scenario(path)
        score = run_scenario(scenario_data)
        baselines[score.scenario_name] = score.to_dict()

    BASELINES_DIR.mkdir(parents=True, exist_ok=True)
    out = BASELINES_DIR / "v2.1.0_baseline.json"
    with open(out, "w") as f:
        json.dump(baselines, f, indent=2)
    return out


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="EvoBench context density benchmark runner")
    parser.add_argument(
        "--scenario",
        default="all",
        help="Scenario name or 'all' (default: all)",
    )
    parser.add_argument(
        "--compare-baseline",
        action="store_true",
        help="Compare against stored baseline",
    )
    parser.add_argument(
        "--generate-baseline",
        action="store_true",
        help="Generate baseline from current results",
    )
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    if args.generate_baseline:
        out = generate_baseline(args.scenario)
        print(f"Baseline written to {out}")
        return

    report = run_all(args.scenario, args.compare_baseline)

    if args.json:
        print(json.dumps(report, indent=2))
        return

    print(f"EvoBench Results — {report['scenario_count']} scenarios")
    print(f"Overall: {report['overall_verdict']}")
    print()

    for r in report["results"]:
        print(f"  {r['scenario_name']} ({r['profile_name']})")
        print(f"    Composite: {r['composite']:.1f}/100")
        print(f"    Relevance: {r['section_relevance']:.1%}")
        print(f"    Density:   {r['information_density']:.4f}")
        print(f"    Noise:     {r['noise_ratio']:.1%}")
        print(f"    Budget:    {r['total_tokens']}/{r['budget']} ({r['budget_utilization']:.1%})")
        print()

    if "baseline_comparisons" in report:
        print("Baseline Comparisons:")
        for c in report["baseline_comparisons"]:
            status = "REGRESSION" if c["regressed"] else "OK"
            print(f"  [{status}] {c['scenario']}: {c['delta']:+.1f} ({c['pct_change']:+.1f}%)")


if __name__ == "__main__":
    main()
