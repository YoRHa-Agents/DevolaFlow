"""Focused implementation slice for the workspace-lint CLI."""

# ruff: noqa: F403, F405

from __future__ import annotations

from .common import *  # noqa: F403


def main(argv: list[str] | None = None) -> int:
    """CLI entry point — ``python -m devolaflow.agent_workspace.lint <id>``.

    Returns the exit code (``0`` / ``1`` / ``2``). All output is written
    to stderr so the call site can pipe stdout into another tool.
    """
    parser = argparse.ArgumentParser(
        prog="python -m devolaflow.agent_workspace.lint",
        description=(
            "Lint a .local/.agent/active/<change-id>/ folder against C-9 budgets, "
            "a direct .local/tasks/<task-name>/ folder with --task, or the "
            ".local/human/ surface with --human."
        ),
    )
    parser.add_argument(
        "change_id",
        nargs="?",
        default=None,
        help="lowercase-kebab-case change id (e.g. add-dark-mode, v8.3.0-pv05); "
        "omit when using --human",
    )
    parser.add_argument(
        "--human",
        action="store_true",
        help="lint the .local/human/ INPUT + OUTPUT zones instead of a change folder",
    )
    parser.add_argument(
        "--task",
        action="store_true",
        help="lint a direct .local/tasks/<task-name>/ folder",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="repo root directory (default: cwd)",
    )
    parser.add_argument(
        "--active-dir",
        type=Path,
        default=None,
        help="override active dir (default: .local/.agent/active)",
    )
    parser.add_argument(
        "--archive-dir",
        type=Path,
        default=None,
        help="override archive dir (default: .local/.agent/archive)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="suppress per-file PASS lines (still print WARN/FAIL)",
    )
    args = parser.parse_args(argv)

    if args.human and args.task:
        parser.error("--human and --task cannot be combined")

    if args.human:
        report = lint_human(repo_root=args.repo_root)
    else:
        if not args.change_id:
            parser.error("change_id is required unless --human is given")
        try:
            if args.task:
                report = lint_task(args.change_id, repo_root=args.repo_root)
            else:
                report = lint_change(
                    args.change_id,
                    repo_root=args.repo_root,
                    active_dir=args.active_dir,
                    archive_dir=args.archive_dir,
                )
        except (FileNotFoundError, LegacyChangeLayoutError, ValueError) as exc:
            print(f"lint: {exc}", file=sys.stderr)
            return 2

    if not args.quiet:
        # PASS rows for every checked file (so the operator sees coverage).
        for filename in report.checked_files:
            if any(v.filename == filename for v in report.violations):
                continue
            print(f"{report.change_id}/{filename:18s} OK", file=sys.stderr)
    for v in report.violations:
        print(v.render(report.change_id), file=sys.stderr)

    if report.hard_failures:
        failure_label = (
            "hard/semantic"
            if any(isinstance(v, SemanticViolation) for v in report.hard_failures)
            else "hard ceiling"
        )
        print(
            f"lint: FAIL — {len(report.hard_failures)} {failure_label} violation(s) in "
            f"{report.change_id!r}",
            file=sys.stderr,
        )
    elif report.soft_warnings:
        print(
            f"lint: WARN — {len(report.soft_warnings)} soft budget warning(s) in "
            f"{report.change_id!r} (no hard violations)",
            file=sys.stderr,
        )

    return report.exit_code


if __name__ == "__main__":  # pragma: no cover - CLI entry only
    raise SystemExit(main())

__all__ = [
    name
    for name in globals()
    if name not in {"__name__", "__package__", "__loader__", "__spec__", "__builtins__", "__all__"}
]
