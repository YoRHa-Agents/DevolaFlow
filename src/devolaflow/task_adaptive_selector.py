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

import sys
from pathlib import Path
from typing import Any

import yaml

PROFILES_PATH = Path(__file__).parents[2] / "workflow-system" / "agent" / "context_profiles.yaml"

PRIORITY_ORDER = ["critical", "important", "supplementary"]


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

            if used_tokens + tok <= budget:
                selected.append((section_name, text, tok))
                used_tokens += tok
            else:
                skipped.append(section_name)
                if verbose:
                    print(
                        f"  [SKIP] {section_name} ({tok} tok) — "
                        f"would exceed budget ({used_tokens}+{tok} > {budget})"
                    )

    result = {
        "profile_name": profile_name,
        "description": profile.get("description", ""),
        "selected_sections": [{"name": name, "tokens": tok} for name, _, tok in selected],
        "assembled_text": "\n\n".join(text for _, text, _ in selected),
        "total_tokens": used_tokens,
        "budget": budget,
        "utilization_pct": round(used_tokens / budget * 100, 1) if budget > 0 else 0,
        "skipped_sections": skipped,
        "extra_context": profile.get("extra_context", []),
        "rationale": profile.get("rationale", "").strip(),
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
    print(f"Token budget: {result['budget']}")
    print(f"Tokens used: {result['total_tokens']} ({result['utilization_pct']}%)")
    print()

    print("Selected sections:")
    for sec in result["selected_sections"]:
        print(f"  [{sec['tokens']:>4} tok] {sec['name']}")

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
