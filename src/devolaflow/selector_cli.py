"""Task-adaptive selector CLI — extracted from ``task_adaptive_selector.py``.

v14.5.0 (ADR-006 / gap G-025 module split) — code extracted VERBATIM from
``task_adaptive_selector.py`` (the ~190-line CLI block: ``main`` + the
``_print_cli_*`` / ``_parse_*`` helpers) per
``.local/research/adr/v15-ADR-006-scorer-selector-module-split.md`` decision
item 2. Mechanical import fix only: ``main`` imports ``select_context`` /
``select_agents_md_slice`` at function level to keep this module free of
module-level cycles.

``python -m devolaflow.task_adaptive_selector <task_type>`` keeps working
unchanged — the selector re-exports ``main`` and keeps its
``if __name__ == "__main__"`` guard. PERMANENT identity-preserving re-export
shims live at the old ``devolaflow.task_adaptive_selector`` path per the
ADR's shim clause. Pinned by ``tests/test_module_split_shims.py``.
"""

from __future__ import annotations

import contextlib
import sys
from typing import Any


def _print_cli_usage() -> None:
    """Print the CLI usage banner shown when no task_type is supplied."""
    print(
        "Usage: task_adaptive_selector.py <task_type> "
        "[--verbose] [--full] [--round N] [--plan-mode|--no-plan-mode] "
        "[--show-slice]"
    )
    print()
    print("Task types: hotfix, feature, research, refactor, review, design")
    print("Also matches goal hints: 'fix bug', 'implement feature', etc.")
    print()
    print("--show-slice: print the per-task-type AGENTS.md slice (PV-07 ADR-007 D3)")


def _parse_round_arg(argv: list[str]) -> int:
    """Return the ``--round N`` value from *argv*, defaulting to 1.

    Invalid integer values are silently coerced to 1 (matching the legacy
    behaviour preserved by ``test_main_round_flag_invalid_falls_back_to_one``).
    """
    round_num = 1
    for i, arg in enumerate(argv):
        if arg == "--round" and i + 1 < len(argv):
            with contextlib.suppress(ValueError):
                round_num = int(argv[i + 1])
    return round_num


def _parse_plan_mode_flag(argv: list[str]) -> bool | None:
    """Return ``True`` / ``False`` / ``None`` for ``--plan-mode`` / ``--no-plan-mode``."""
    if "--plan-mode" in argv:
        return True
    if "--no-plan-mode" in argv:
        return False
    return None


def _print_cli_summary(result: dict[str, Any], *, verbose: bool, round_num: int) -> None:
    """Print the per-profile summary block (lines 1–N of CLI output)."""
    print(f"Profile: {result['profile_name']}")
    print(f"Description: {result['description']}")
    print(f"Model hint: {result['model_hint']}")
    print(f"Token budget: {result['budget']}")
    print(f"Tokens used: {result['total_tokens']} ({result['utilization_pct']}%)")
    if verbose:
        print(f"Round: {round_num}")
        print(f"Plan mode: {result['plan_mode']}")
    print()


def _print_cli_sections(result: dict[str, Any]) -> None:
    """Print selected/skipped/extra-context lines for a CLI run."""
    print("Selected sections:")
    for sec in result["selected_sections"]:
        print(f"  [{sec['tokens']:>4} tok] {sec['name']}")

    if result.get("learnings_included"):
        print("  [learnings] operational learnings injected")

    print()
    print(f"Skipped sections: {', '.join(result['skipped_sections'])}")
    print()
    print(f"Extra context to load: {', '.join(result['extra_context'])}")


def _print_cli_assembled(result: dict[str, Any]) -> None:
    """Print the full assembled context block (only when ``--full`` was given)."""
    print()
    print("=" * 72)
    print("ASSEMBLED CONTEXT")
    print("=" * 72)
    print(result["assembled_text"])


def _print_cli_slice(slice_result: dict[str, Any]) -> None:
    """Print the per-task-type AGENTS.md slice summary (PV-07 ADR-007 D3)."""
    print()
    print("=" * 72)
    print("AGENTS.md SLICE")
    print("=" * 72)
    enabled = slice_result.get("slice_enabled", False)
    print(f"Slice enabled: {enabled}")
    print(f"Profile matched: {slice_result.get('profile_name', '') or '(none)'}")
    print(
        f"Tokens: {slice_result.get('total_tokens', 0)} / {slice_result.get('full_tokens', 0)} "
        f"(savings {slice_result.get('slice_savings_pct', 0.0)}%)"
    )
    included = slice_result.get("included_rules", "all")
    if included == "all":
        print("Included rules: ALL (slice OFF — byte-stable v8.5.1 fast path)")
    else:
        sample = ", ".join(included[:10])
        ellipsis = "..." if len(included) > 10 else ""
        print(f"Included rules: {len(included)} — {sample}{ellipsis}")
    skipped = slice_result.get("skipped_rules", [])
    if skipped:
        sample = ", ".join(skipped[:10])
        ellipsis = "..." if len(skipped) > 10 else ""
        print(f"Skipped rules ({len(skipped)}): {sample}{ellipsis}")


def main():
    """CLI entry point for the task-adaptive context selector."""
    from devolaflow.agents_md_slice import select_agents_md_slice
    from devolaflow.task_adaptive_selector import select_context

    if len(sys.argv) < 2:
        _print_cli_usage()
        sys.exit(1)

    task_type = sys.argv[1]
    verbose = "--verbose" in sys.argv
    show_full = "--full" in sys.argv
    show_slice = "--show-slice" in sys.argv
    round_num = _parse_round_arg(sys.argv)
    plan_mode_flag = _parse_plan_mode_flag(sys.argv)

    result = select_context(
        task_type,
        verbose=verbose,
        round_num=round_num,
        plan_mode=plan_mode_flag,
    )

    _print_cli_summary(result, verbose=verbose, round_num=round_num)
    _print_cli_sections(result)

    if show_full:
        _print_cli_assembled(result)

    if show_slice:
        slice_result = select_agents_md_slice(task_type)
        _print_cli_slice(slice_result)
