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

import logging
import sys
from pathlib import Path
from typing import Any

import yaml

from devolaflow.learnings import format_learnings_section, load_relevant_learnings

logger = logging.getLogger(__name__)

PROFILES_PATH = Path(__file__).parents[2] / "workflow-system" / "agent" / "context_profiles.yaml"

PRIORITY_ORDER = ["critical", "important", "supplementary"]

VALID_MODEL_HINTS = {"quality", "balanced", "budget", "inherit"}


def resolve_model_hint(task_type: str, profile_config: dict[str, Any]) -> str:
    """Resolve the model_hint for a given task type from the profile config.

    Checks profile-level model_hints.overrides first, then falls back to
    model_hints.default_tier, then to "inherit".
    """
    model_hints = profile_config.get("model_hints", {})
    overrides = model_hints.get("overrides", {})

    if task_type in overrides:
        hint = overrides[task_type]
        if hint in VALID_MODEL_HINTS:
            return hint

    default = model_hints.get("default_tier", "inherit")
    return default if default in VALID_MODEL_HINTS else "inherit"


def load_profiles(path: Path | None = None) -> dict[str, Any]:
    p = path or PROFILES_PATH
    with open(p) as f:
        return yaml.safe_load(f)


def load_skill_md(config: dict[str, Any]) -> str:
    skill_path = Path(__file__).parents[2] / "workflow-system" / "agent" / "SKILL.md"
    if not skill_path.exists():
        repo_root = Path(__file__).parents[2]
        candidates = list(repo_root.rglob("SKILL.md"))
        if candidates:
            skill_path = candidates[0]
        else:
            raise FileNotFoundError(f"SKILL.md not found relative to {repo_root}")
    return skill_path.read_text()


def extract_section(full_text: str, line_range: str) -> str:
    """Extract lines from full_text given a range like '57-68'."""
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


def select_context(
    task_type: str,
    profiles_path: Path | None = None,
    verbose: bool = False,
) -> dict[str, Any]:
    """Select context sections for a given task type.

    Returns a dict with:
      - profile_name: matched profile
      - selected_sections: ordered list of (section_name, text, tokens)
      - total_tokens: sum of selected section tokens
      - budget: token budget for this profile
      - skipped_sections: sections that didn't fit or were deprioritized
      - extra_context: additional reference files to load
    """
    config = load_profiles(profiles_path)
    skill_text = load_skill_md(config)
    sections_registry = config.get("sections", {})

    profile_name = match_profile(task_type, config)
    profile = config["profiles"][profile_name]
    budget = profile.get("token_budget", 6000)
    section_priorities = profile.get("section_priorities", {})

    advisor_config = profile.get("advisor", {})
    advisor_enabled = advisor_config.get("enabled", False)
    advisor_text = ""
    advisor_reserve = 0
    if advisor_enabled:
        max_uses = advisor_config.get("max_uses", 3)
        cost_ceiling = advisor_config.get("cost_ceiling_usd", 0.30)
        triggers = advisor_config.get("trigger_conditions", [])
        triggers_str = ", ".join(triggers) if triggers else "none"
        advisor_text = (
            f"## Advisor Tool\n"
            f"Advisor enabled (max {max_uses} uses, budget ${cost_ceiling}).\n"
            f"Invoke for: {triggers_str}."
        )
        advisor_reserve = estimate_tokens(advisor_text)

    learnings_config = profile.get("learnings", {})
    learnings_reserve = 0
    if learnings_config.get("enabled", False):
        p = profiles_path or PROFILES_PATH
        learnings_path = p.parent / "knowledge" / "learnings" / "operational.jsonl"
        if learnings_path.exists() and learnings_path.stat().st_size > 0:
            budget_max_tokens = learnings_config.get("budget_max_tokens", 500)
            budget_pct = learnings_config.get("budget_pct", 10)
            learnings_reserve = min(budget_max_tokens, int(budget * budget_pct / 100))

    section_budget = budget - advisor_reserve - learnings_reserve

    priority_buckets: dict[str, list[str]] = {p: [] for p in PRIORITY_ORDER}
    skipped = []

    for section_name, priority in section_priorities.items():
        if priority == "skip":
            skipped.append(section_name)
        elif priority in priority_buckets:
            priority_buckets[priority].append(section_name)

    selected: list[tuple[str, str, int]] = []
    used_tokens = 0

    for priority in PRIORITY_ORDER:
        for section_name in priority_buckets[priority]:
            if section_name not in sections_registry:
                continue

            sec_info = sections_registry[section_name]
            line_range = sec_info.get("lines", "")
            if not line_range:
                continue

            text = extract_section(skill_text, line_range)
            tok = estimate_tokens(text)

            if used_tokens + tok <= section_budget:
                selected.append((section_name, text, tok))
                used_tokens += tok
            else:
                skipped.append(section_name)
                if verbose:
                    print(
                        f"  [SKIP] {section_name} ({tok} tok) — "
                        f"would exceed budget ({used_tokens}+{tok} > {section_budget})"
                    )

    assembled_text = "\n\n".join(text for _, text, _ in selected)

    learnings_text = ""
    if learnings_config.get("enabled", False):
        p = profiles_path or PROFILES_PATH
        learnings_path = p.parent / "knowledge" / "learnings" / "operational.jsonl"
        if learnings_path.exists():
            max_entries = learnings_config.get("max_entries", 5)
            min_confidence = learnings_config.get("min_confidence", 0.5)
            learnings_token_cap = learnings_reserve

            try:
                relevant = load_relevant_learnings(
                    task_type=profile_name,
                    jsonl_path=learnings_path,
                    min_confidence=min_confidence,
                    max_entries=max_entries,
                )
                if relevant:
                    learnings_text = format_learnings_section(
                        relevant, max_tokens=learnings_token_cap
                    )
                    learnings_tokens = estimate_tokens(learnings_text)
                    used_tokens += learnings_tokens
            except Exception:
                logger.debug("Learnings integration skipped due to error", exc_info=True)

    if learnings_text:
        assembled_text = assembled_text + "\n\n" + learnings_text

    if advisor_text:
        assembled_text = assembled_text + "\n\n" + advisor_text
        used_tokens += advisor_reserve

    model_hint = resolve_model_hint(task_type, profile)

    result = {
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
    }

    return result


def main():
    if len(sys.argv) < 2:
        print("Usage: task_adaptive_selector.py <task_type> [--verbose] [--full]")
        print()
        print("Task types: hotfix, feature, research, refactor, review, design")
        print("Also matches goal hints: 'fix bug', 'implement feature', etc.")
        sys.exit(1)

    task_type = sys.argv[1]
    verbose = "--verbose" in sys.argv
    show_full = "--full" in sys.argv

    result = select_context(task_type, verbose=verbose)

    print(f"Profile: {result['profile_name']}")
    print(f"Description: {result['description']}")
    print(f"Model hint: {result['model_hint']}")
    print(f"Token budget: {result['budget']}")
    print(f"Tokens used: {result['total_tokens']} ({result['utilization_pct']}%)")
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
