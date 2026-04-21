#!/usr/bin/env python3
"""Task-Adaptive Context Selector for DevolaFlow.

Given a task_type (from TaskDispatch), selects and assembles the relevant
SKILL.md sections according to the matching context profile. Uses priority-based
budget allocation: critical sections first, then important, then supplementary,
until the token budget is exhausted.

Based on: WP-4 Rank 4 (Task-Adaptive Context Selection via Goal-Hint Routing),
          SWE-Pruner goal hints, ATACompressor variable-rate allocation.
"""

from __future__ import annotations

import contextlib
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any

import yaml

from devolaflow.learnings import (
    format_learnings_section,
    load_relevant_learnings,
    resolve_learnings_path,
)

logger = logging.getLogger(__name__)

PROFILES_PATH = Path(__file__).parents[2] / "workflow-system" / "agent" / "context_profiles.yaml"

PRIORITY_ORDER = ["critical", "important", "supplementary"]

VALID_MODEL_HINTS = {"quality", "balanced", "budget", "inherit"}

VALID_COMPRESSION_INTENSITIES = {"minimal", "standard", "aggressive"}

_PLAN_MODE_ENV = "DEVOLAFLOW_PLAN_MODE"
_PLAN_MODE_MARKER = ".devolaflow_plan_mode"


def _detect_plan_mode() -> bool:
    """Detect plan-mode from environment or filesystem markers.

    Detection signals (in priority order):
      1. Env var ``DEVOLAFLOW_PLAN_MODE`` in {"1", "true", "yes", "on"}
      2. File ``.devolaflow_plan_mode`` exists in cwd

    Returns False on any other state (including unset, empty, or unknown
    string values like ``"garbage"``).
    """
    val = os.environ.get(_PLAN_MODE_ENV, "").strip().lower()
    if val in {"1", "true", "yes", "on"}:
        return True
    return (Path.cwd() / _PLAN_MODE_MARKER).exists()


_PLAN_MODE_OVERRIDES: dict[str, Any] = {
    "section_priority_overrides": {
        "agent_hierarchy": "critical",
        "decomposition_gate": "critical",
        "rationalization_prevention": "critical",
        "convergence_loop": "important",
        "execution_protocol": "supplementary",
    },
    "compression_intensity": "minimal",
    "model_hint_override": "quality",
}


def apply_plan_mode_overrides(profile: dict[str, Any]) -> dict[str, Any]:
    """Return a profile copy with plan-mode priority/model overrides applied.

    When plan-mode is active, the L0 Project Agent is designing an execution
    plan rather than executing. The assembled context therefore needs to
    emphasise the primitives that shape good plans (agent hierarchy,
    decomposition gate, rationalization prevention) and de-emphasise the
    runtime execution protocol.

    Does not mutate *profile*. Composes with :func:`apply_round_escalation`:
    plan-mode applies first, round-escalation may then override individual
    sections (e.g. round-3 lifts ``convergence_loop`` back to critical).
    """
    result = {**profile}

    prio_overrides = _PLAN_MODE_OVERRIDES["section_priority_overrides"]
    existing = dict(result.get("section_priorities", {}))
    existing.update(prio_overrides)
    result["section_priorities"] = existing

    result["model_hint"] = _PLAN_MODE_OVERRIDES["model_hint_override"]
    result["compression_intensity"] = _PLAN_MODE_OVERRIDES["compression_intensity"]
    return result


def resolve_decomposition_config(profile_config: dict[str, Any]) -> dict[str, Any]:
    """Resolve decomposition configuration from profile.

    Returns a dict with enabled, max_sub_agents, sub_agent_model_hint, etc.
    Defaults to disabled if not configured.
    """
    decomp = profile_config.get("decomposition", {})
    return {
        "enabled": decomp.get("enabled", False),
        "max_sub_agents": decomp.get("max_sub_agents", 4),
        "max_nesting_depth": decomp.get("max_nesting_depth", 1),
        "sub_agent_model_hint": decomp.get("sub_agent_model_hint", "budget"),
        "sub_agent_context_budget": decomp.get("sub_agent_context_budget", 3000),
        "coordinator_retains_advisor": decomp.get("coordinator_retains_advisor", True),
        "gen_verify_mode": decomp.get("gen_verify_mode", False),
        "gen_verify_max_rounds": decomp.get("gen_verify_max_rounds", 3),
    }


def resolve_compression_intensity(boundary: str, profiles_config: dict[str, Any]) -> str:
    """Resolve compression intensity for a given layer boundary.

    boundary: one of l0_to_l1, l1_to_l2, l2_to_l3, l3_to_l2, l2_to_l1, l1_to_l0
    """
    defaults = profiles_config.get("meta", {}).get("compression_defaults", {})
    intensity = defaults.get(boundary, "standard")
    return intensity if intensity in VALID_COMPRESSION_INTENSITIES else "standard"


def resolve_model_hint(
    task_type: str,
    profile_config: dict[str, Any],
    complexity_tier: str | None = None,
) -> str:
    """Resolve the model_hint for a given task type from the profile config.

    Lookup priority (v7.2.1+ P-04):
      1. ``complexity_routing[complexity_tier]`` — when *complexity_tier* is
         provided AND a mapping exists in
         ``profile_config["complexity_routing"]`` AND the resolved tier is in
         :data:`VALID_MODEL_HINTS`. The complexity-tier lookup table lives
         under top-level ``meta.complexity_routing`` in
         ``context_profiles.yaml``; :func:`select_context` injects it into the
         per-profile dict via copy-on-write before calling this function.
      2. ``model_hints.overrides[task_type]`` — per-task override.
      3. ``model_hints.default_tier`` — profile default.
      4. ``"inherit"`` — terminal fallback.

    Default ``complexity_tier=None`` preserves the v7.1.0 lookup priority
    bytewise (the new branch is skipped entirely), so the 2-arg signature
    ``resolve_model_hint(task_type, profile_config)`` remains valid for
    every existing caller and test.
    """
    if complexity_tier is not None:
        complexity_routing = profile_config.get("complexity_routing", {})
        if complexity_tier in complexity_routing:
            tier_hint = complexity_routing[complexity_tier]
            if tier_hint in VALID_MODEL_HINTS:
                return tier_hint

    model_hints = profile_config.get("model_hints", {})
    overrides = model_hints.get("overrides", {})

    if task_type in overrides:
        hint = overrides[task_type]
        if hint in VALID_MODEL_HINTS:
            return hint

    default = model_hints.get("default_tier", "inherit")
    return default if default in VALID_MODEL_HINTS else "inherit"


def load_profiles(path: Path | None = None) -> dict[str, Any]:
    """Load context profiles from a YAML configuration file."""
    p = path or PROFILES_PATH
    with open(p) as f:
        return yaml.safe_load(f)


def load_skill_md(config: dict[str, Any]) -> str:
    """Load the SKILL.md file contents as a string."""
    skill_path = Path(__file__).parents[2] / "workflow-system" / "agent" / "SKILL.md"
    if not skill_path.exists():
        repo_root = Path(__file__).parents[2]
        candidates = list(repo_root.rglob("SKILL.md"))
        if candidates:
            skill_path = candidates[0]
        else:
            raise FileNotFoundError(f"SKILL.md not found relative to {repo_root}")
    return skill_path.read_text()


_LINE_RANGE_RE = re.compile(r"^\d+-\d+$")


def extract_section(full_text: str, line_range: str) -> str:
    """Extract lines from full_text given a range like '57-68'."""
    if not line_range or not _LINE_RANGE_RE.match(line_range):
        return ""
    lines = full_text.splitlines()
    start, end = map(int, line_range.split("-"))
    return "\n".join(lines[start - 1 : end])


def estimate_tokens(text: str) -> int:
    """Estimate token count. Uses tiktoken if available, otherwise ~4 chars/token."""
    try:
        import tiktoken

        enc = tiktoken.encoding_for_model("gpt-4o")
        return len(enc.encode(text))
    except (ImportError, Exception):
        return max(1, len(text) // 4)


def match_profile(task_type: str, profiles_config: dict[str, Any]) -> str:
    """Match a task_type string to the best profile name.

    Ranking: exact key match > exact hint match > best substring match
    (longest overlap wins to avoid short hints stealing specific tasks).
    """
    profiles = profiles_config.get("profiles", {})

    if task_type in profiles:
        return task_type

    task_lower = task_type.lower()

    best_match: str | None = None
    best_score = 0

    for profile_name, profile in profiles.items():
        hints = profile.get("goal_hints", [])
        for hint in hints:
            hint_lower = hint.lower()
            if hint_lower == task_lower:
                return profile_name
            if hint_lower in task_lower:
                score = len(hint_lower)
                if score > best_score:
                    best_score = score
                    best_match = profile_name
            elif task_lower in hint_lower:
                score = len(task_lower)
                if score > best_score:
                    best_score = score
                    best_match = profile_name

    return best_match or profiles_config.get("meta", {}).get("default_profile", "feature")


def _resolve_advisor_text(profile: dict[str, Any]) -> tuple[bool, str, int]:
    """Build advisor section text and compute its token reserve.

    v7.2.0 PR-D note: dispatch and candidate-list refer to this helper as
    `_build_advisor_section`; the actual symbol is `_resolve_advisor_text`.
    The helper is the single emitter for the "## Advisor Tool" block consumed
    by all 4 advisor-enabled profiles (feature, refactor, migration,
    security-audit). One change here covers all 4.
    """
    advisor_config = profile.get("advisor", {})
    if not advisor_config.get("enabled", False):
        return False, "", 0

    max_uses = advisor_config.get("max_uses", 3)
    cost_ceiling = advisor_config.get("cost_ceiling_usd", 0.30)
    triggers = advisor_config.get("trigger_conditions", [])
    triggers_str = ", ".join(triggers) if triggers else "none"
    parts = [
        "## Advisor Tool",
        f"Advisor enabled (max {max_uses} uses, budget ${cost_ceiling}).",
        f"Invoke for: {triggers_str}.",
    ]
    if advisor_config.get("conciseness_instruction", True):
        parts.append(
            'When invoking advisor, append: "Reply in under 100 words and use '
            'enumerated steps, not explanations."'
        )
    if advisor_config.get("timing_block", True):
        parts.append(
            "Timing: Call advisor BEFORE substantive work. On tasks longer than "
            "a few steps, call advisor at least once before committing to an "
            "approach and once before declaring done."
        )
    if advisor_config.get("reconcile_block", True):
        parts.append(
            "On conflict: If you've already retrieved data pointing one way and "
            "the advisor points another, do not silently switch. Surface the "
            'conflict in one more advisor call: "I found X, you suggest Y, '
            'which constraint breaks the tie?".'
        )
    text = "\n".join(parts)
    return True, text, estimate_tokens(text)


def _compute_learnings_reserve(
    learnings_config: dict[str, Any],
    profiles_path: Path | None,
    budget: int,
) -> int:
    """Compute the token reservation for operational learnings."""
    if not learnings_config.get("enabled", False):
        return 0
    learnings_path = resolve_learnings_path()
    if not learnings_path.exists() or learnings_path.stat().st_size == 0:
        return 0
    budget_max_tokens = learnings_config.get("budget_max_tokens", 500)
    budget_pct = learnings_config.get("budget_pct", 10)
    return min(budget_max_tokens, int(budget * budget_pct / 100))


def _build_priority_buckets(
    section_priorities: dict[str, str],
) -> tuple[dict[str, list[str]], list[str]]:
    """Sort section names into priority buckets and a skip list."""
    buckets: dict[str, list[str]] = {p: [] for p in PRIORITY_ORDER}
    skipped: list[str] = []
    for section_name, priority in section_priorities.items():
        if priority == "skip":
            skipped.append(section_name)
        elif priority in buckets:
            buckets[priority].append(section_name)
    return buckets, skipped


def _select_sections_within_budget(
    priority_buckets: dict[str, list[str]],
    sections_registry: dict[str, Any],
    skill_text: str,
    section_budget: int,
    verbose: bool,
) -> tuple[list[tuple[str, str, int]], list[str], int]:
    """Pick sections in priority order until the token budget is exhausted."""
    selected: list[tuple[str, str, int]] = []
    overflow: list[str] = []
    used_tokens = 0

    for priority in PRIORITY_ORDER:
        for section_name in priority_buckets[priority]:
            if section_name not in sections_registry:
                continue
            sec_info = sections_registry[section_name]
            line_range = sec_info.get("lines", "")
            if not line_range or not _LINE_RANGE_RE.match(line_range):
                continue

            text = extract_section(skill_text, line_range)
            tok = estimate_tokens(text)

            if used_tokens + tok <= section_budget:
                selected.append((section_name, text, tok))
                used_tokens += tok
            else:
                overflow.append(section_name)
                if verbose:
                    print(
                        f"  [SKIP] {section_name} ({tok} tok) — "
                        f"would exceed budget ({used_tokens}+{tok} > {section_budget})"
                    )

    return selected, overflow, used_tokens


def _integrate_learnings(
    learnings_config: dict[str, Any],
    profile_name: str,
    profiles_path: Path | None,
    learnings_reserve: int,
) -> str:
    """Load and format operational learnings, returning the text (or empty)."""
    if not learnings_config.get("enabled", False):
        return ""
    learnings_path = resolve_learnings_path()
    if not learnings_path.exists():
        return ""

    max_entries = learnings_config.get("max_entries", 5)
    min_confidence = learnings_config.get("min_confidence", 0.5)
    try:
        relevant = load_relevant_learnings(
            task_type=profile_name,
            jsonl_path=learnings_path,
            min_confidence=min_confidence,
            max_entries=max_entries,
        )
        if not relevant:
            return ""
        return format_learnings_section(relevant, max_tokens=learnings_reserve)
    except Exception:
        logger.debug("Learnings integration skipped due to error", exc_info=True)
        return ""


def select_context(
    task_type: str,
    profiles_path: Path | None = None,
    verbose: bool = False,
    round_num: int = 1,
    escalation_config: dict[int, dict[str, Any]] | None = None,
    plan_mode: bool | None = None,
    complexity_tier: str | None = None,
) -> dict[str, Any]:
    """Select context sections for a given task type.

    Returns a dict with:
      - profile_name: matched profile
      - selected_sections: ordered list of (section_name, text, tokens)
      - total_tokens: sum of selected section tokens
      - budget: token budget for this profile
      - skipped_sections: sections that didn't fit or were deprioritized
      - extra_context: additional reference files to load
      - round_num: convergence round number (1 = initial, 2+ = escalated)
      - escalation_applied: whether round-based escalation was applied
      - plan_mode: whether plan-mode is active (resolved from param or
        :func:`_detect_plan_mode` when *plan_mode* is ``None``)
      - plan_mode_applied: alias of ``plan_mode`` for explicit downstream
        checks; True when :func:`apply_plan_mode_overrides` was applied

    When ``round_num > 1`` the resolved profile is routed through
    :func:`apply_round_escalation` so convergence rounds receive stricter
    section priorities and larger token budgets.  Pass ``escalation_config``
    to override the defaults defined in ``_ROUND_ESCALATION_DEFAULTS``.

    When *plan_mode* is True (or auto-detected via env var/marker file when
    ``plan_mode is None``) :func:`apply_plan_mode_overrides` runs *before*
    round-based escalation so plan-relevant primitives are escalated first
    and round overrides may then layer on top (e.g. round-3 still lifts
    ``convergence_loop`` to critical and bumps the budget by 20%).
    Pass ``plan_mode=False`` to disable detection entirely.

    When *complexity_tier* is provided (one of the keys in
    ``meta.complexity_routing`` — typically ``"simple" | "medium" | "complex"
    | "very_complex"``) the corresponding model hint takes priority over
    the per-profile ``model_hints.overrides`` and ``default_tier``. Default
    ``complexity_tier=None`` preserves the v7.1.0 routing priority bytewise.
    See :func:`resolve_model_hint` for the full lookup priority.
    """
    config = load_profiles(profiles_path)
    skill_text = load_skill_md(config)
    sections_registry = config.get("sections", {})

    profile_name = match_profile(task_type, config)
    profile = config["profiles"][profile_name]

    active_plan_mode = plan_mode if plan_mode is not None else _detect_plan_mode()
    if active_plan_mode:
        profile = apply_plan_mode_overrides(profile)

    if round_num > 1:
        profile = apply_round_escalation(profile, round_num, escalation_config)

    meta_complexity_routing = config.get("meta", {}).get("complexity_routing", {})
    if meta_complexity_routing:
        profile = {**profile, "complexity_routing": meta_complexity_routing}
    budget = profile.get("token_budget", 6000)

    advisor_enabled, advisor_text, advisor_reserve = _resolve_advisor_text(profile)
    learnings_config = profile.get("learnings", {})
    learnings_reserve = _compute_learnings_reserve(learnings_config, profiles_path, budget)
    section_budget = budget - advisor_reserve - learnings_reserve

    priority_buckets, skipped = _build_priority_buckets(profile.get("section_priorities", {}))
    selected, overflow_skipped, used_tokens = _select_sections_within_budget(
        priority_buckets,
        sections_registry,
        skill_text,
        section_budget,
        verbose,
    )
    skipped.extend(overflow_skipped)

    assembled_text = "\n\n".join(text for _, text, _ in selected)

    learnings_text = _integrate_learnings(
        learnings_config,
        profile_name,
        profiles_path,
        learnings_reserve,
    )
    if learnings_text:
        assembled_text = assembled_text + "\n\n" + learnings_text
        used_tokens += estimate_tokens(learnings_text)

    if advisor_text:
        assembled_text = assembled_text + "\n\n" + advisor_text
        used_tokens += advisor_reserve

    escalation_applied = round_num > 1
    profile_overrides_applied = escalation_applied or active_plan_mode
    model_hint: str | None = None
    if profile_overrides_applied and "model_hint" in profile:
        model_hint = profile["model_hint"]
    if not model_hint:
        model_hint = resolve_model_hint(task_type, profile, complexity_tier)

    compression_intensity = (
        profile.get("compression_intensity")
        if profile_overrides_applied and "compression_intensity" in profile
        else resolve_compression_intensity("l2_to_l3", config)
    )

    return {
        "profile_name": profile_name,
        "description": profile.get("description", ""),
        "selected_sections": [{"name": name, "tokens": tok} for name, _, tok in selected],
        "assembled_text": assembled_text,
        "total_tokens": used_tokens,
        "budget": budget,
        "utilization_pct": round(used_tokens / budget * 100, 1) if budget > 0 else 0,
        "skipped_sections": skipped,
        "extra_context": profile.get("extra_context", []),
        "rationale": profile.get("rationale", "").strip(),
        "learnings_included": bool(learnings_text),
        "model_hint": model_hint,
        "advisor_enabled": advisor_enabled,
        "decomposition": resolve_decomposition_config(profile),
        "compression_intensity": compression_intensity,
        "round_num": round_num,
        "escalation_applied": escalation_applied,
        "plan_mode": active_plan_mode,
        "plan_mode_applied": active_plan_mode,
    }


_ROUND_ESCALATION_DEFAULTS: dict[int, dict[str, Any]] = {
    2: {
        "section_priority_overrides": {
            "rationalization_prevention": "critical",
            "convergence_loop": "critical",
        },
        "compression_intensity": "minimal",
    },
    3: {
        "section_priority_overrides": {
            "rationalization_prevention": "critical",
            "convergence_loop": "critical",
            "gate_mechanism": "critical",
        },
        "model_hint_override": "quality",
        "token_budget_increase_pct": 20,
    },
}


def apply_round_escalation(
    profile: dict[str, Any],
    round_num: int,
    escalation_config: dict[int, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return a profile copy with round-based escalation overrides applied.

    Higher convergence rounds get stricter section priorities, better
    model hints, and increased token budgets.  Does not mutate *profile*.
    """
    overrides = (escalation_config or _ROUND_ESCALATION_DEFAULTS).get(round_num)
    if overrides is None:
        if round_num > max((escalation_config or _ROUND_ESCALATION_DEFAULTS), default=0):
            overrides = max(
                (escalation_config or _ROUND_ESCALATION_DEFAULTS).values(),
                key=lambda v: v.get("token_budget_increase_pct", 0),
                default={},
            )
        else:
            return profile

    result = {**profile}

    prio_overrides = overrides.get("section_priority_overrides", {})
    if prio_overrides:
        existing = dict(result.get("section_priorities", {}))
        existing.update(prio_overrides)
        result["section_priorities"] = existing

    if "model_hint_override" in overrides:
        result["model_hint"] = overrides["model_hint_override"]

    if "compression_intensity" in overrides:
        result["compression_intensity"] = overrides["compression_intensity"]

    increase_pct = overrides.get("token_budget_increase_pct", 0)
    if increase_pct and "token_budget" in result:
        result["token_budget"] = int(result["token_budget"] * (1 + increase_pct / 100))

    return result


def main():
    """CLI entry point for the task-adaptive context selector."""
    if len(sys.argv) < 2:
        print(
            "Usage: task_adaptive_selector.py <task_type> "
            "[--verbose] [--full] [--round N] [--plan-mode|--no-plan-mode]"
        )
        print()
        print("Task types: hotfix, feature, research, refactor, review, design")
        print("Also matches goal hints: 'fix bug', 'implement feature', etc.")
        sys.exit(1)

    task_type = sys.argv[1]
    verbose = "--verbose" in sys.argv
    show_full = "--full" in sys.argv

    round_num = 1
    for i, arg in enumerate(sys.argv):
        if arg == "--round" and i + 1 < len(sys.argv):
            with contextlib.suppress(ValueError):
                round_num = int(sys.argv[i + 1])

    plan_mode_flag: bool | None = None
    if "--plan-mode" in sys.argv:
        plan_mode_flag = True
    elif "--no-plan-mode" in sys.argv:
        plan_mode_flag = False

    result = select_context(
        task_type,
        verbose=verbose,
        round_num=round_num,
        plan_mode=plan_mode_flag,
    )

    print(f"Profile: {result['profile_name']}")
    print(f"Description: {result['description']}")
    print(f"Model hint: {result['model_hint']}")
    print(f"Token budget: {result['budget']}")
    print(f"Tokens used: {result['total_tokens']} ({result['utilization_pct']}%)")
    if verbose:
        print(f"Round: {round_num}")
        print(f"Plan mode: {result['plan_mode']}")
    print()

    print("Selected sections:")
    for sec in result["selected_sections"]:
        print(f"  [{sec['tokens']:>4} tok] {sec['name']}")

    if result.get("learnings_included"):
        print("  [learnings] operational learnings injected")

    print()
    print(f"Skipped sections: {', '.join(result['skipped_sections'])}")
    print()
    print(f"Extra context to load: {', '.join(result['extra_context'])}")

    if show_full:
        print()
        print("=" * 72)
        print("ASSEMBLED CONTEXT")
        print("=" * 72)
        print(result["assembled_text"])


if __name__ == "__main__":
    main()
