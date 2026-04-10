"""EvoBench evaluator — scores context selection quality.

Dimensions:
  - information_density: quality-weighted tokens (relevant tokens / total tokens)
  - section_relevance: fraction of selected sections that match expected sections
  - budget_utilization: how much of the token budget is used (higher = more efficient)
  - noise_ratio: fraction of selected sections that are NOT in expected sections (lower = better)
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class BenchmarkScore:
    """Scores for a single benchmark scenario."""

    scenario_name: str
    profile_name: str
    information_density: float
    section_relevance: float
    budget_utilization: float
    noise_ratio: float
    total_tokens: int
    budget: int
    selected_count: int
    expected_count: int
    matched_count: int

    @property
    def composite(self) -> float:
        """Weighted composite score (0-100)."""
        return round(
            self.section_relevance * 40
            + self.information_density * 30
            + (1.0 - self.noise_ratio) * 20
            + self.budget_utilization * 10,
            2,
        )

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["composite"] = self.composite
        return d


def evaluate_scenario(
    scenario_name: str,
    selector_result: dict[str, Any],
    expected_sections: list[str],
    unwanted_sections: list[str] | None = None,
) -> BenchmarkScore:
    """Evaluate a single benchmark scenario.

    Parameters
    ----------
    scenario_name:
        Human-readable name for this scenario.
    selector_result:
        Output of ``select_context()`` from task_adaptive_selector.
    expected_sections:
        Section names that SHOULD be selected for this task type.
    unwanted_sections:
        Section names that SHOULD NOT be selected (noise). If None,
        any section not in expected is considered unwanted.
    """
    selected_names = {s["name"] for s in selector_result["selected_sections"]}
    expected_set = set(expected_sections)
    unwanted_set = set(unwanted_sections) if unwanted_sections else set()

    matched = selected_names & expected_set
    noise = selected_names & unwanted_set if unwanted_set else selected_names - expected_set

    total_tokens = selector_result["total_tokens"]
    budget = selector_result["budget"]
    selected_count = len(selected_names)

    section_relevance = len(matched) / len(expected_set) if expected_set else 0.0
    noise_ratio = len(noise) / selected_count if selected_count else 0.0
    budget_utilization = total_tokens / budget if budget > 0 else 0.0
    information_density = section_relevance * budget_utilization

    return BenchmarkScore(
        scenario_name=scenario_name,
        profile_name=selector_result["profile_name"],
        information_density=round(information_density, 4),
        section_relevance=round(section_relevance, 4),
        budget_utilization=round(budget_utilization, 4),
        noise_ratio=round(noise_ratio, 4),
        total_tokens=total_tokens,
        budget=budget,
        selected_count=selected_count,
        expected_count=len(expected_set),
        matched_count=len(matched),
    )


def compare_to_baseline(
    current: BenchmarkScore,
    baseline: dict[str, Any],
    regression_threshold: float = 0.05,
) -> dict[str, Any]:
    """Compare current score against baseline and detect regressions.

    Returns a dict with per-dimension deltas and a pass/fail verdict.
    A regression is flagged when the current composite score drops more
    than ``regression_threshold`` (as a fraction) below the baseline.
    """
    baseline_composite = baseline.get("composite", 0.0)
    current_composite = current.composite

    delta = current_composite - baseline_composite
    pct_change = delta / baseline_composite if baseline_composite > 0 else 0.0

    regressed = pct_change < -regression_threshold

    return {
        "scenario": current.scenario_name,
        "baseline_composite": baseline_composite,
        "current_composite": current_composite,
        "delta": round(delta, 2),
        "pct_change": round(pct_change * 100, 2),
        "regressed": regressed,
        "verdict": "REGRESSION" if regressed else "PASS",
    }
