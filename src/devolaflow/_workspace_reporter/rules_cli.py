"""Focused implementation slice for report CLI operations."""

# ruff: noqa: F403, F405

from __future__ import annotations

from .common import *  # noqa: F403


def regenerate_all(
    repo_root: Path | None = None,
    *,
    now: datetime | None = None,
    archive_window_days: int = DEFAULT_ARCHIVE_WINDOW_DAYS,
    memory_window_days: int = DEFAULT_MEMORY_WINDOW_DAYS,
    human_version: str | None = None,
    human_requirements_path: Path | None = None,
    human_test_results: Mapping[str, object] | None = None,
    human_findings: Iterable[object] | None = None,
    human_stagnation: bool = False,
) -> dict[str, object]:
    """Regenerate the REPORT.md files at the canonical paths.

    Always regenerates the four agent-facing flavours (workspace / memory /
    rules / per-change). The FIFTH human flavour (design §4 / §6c) is opt-in:
    it renders ONLY when ``human_version`` is supplied, because the
    convergence report path is per-cycle (``<version>-convergence.md``) and
    the digest derives from the same cycle.

    Args:
      repo_root: repo root (default: ``Path.cwd()``).
      now: pinned clock — passed to every renderer so a fixed value yields
        byte-identical outputs across calls (AC-5 idempotency).
      archive_window_days: window for the workspace report's archived
        changes table (default 7 days per design.md §5.2).
      memory_window_days: window for the memory report's "Top 10
        high-confidence learnings" section (default 30 days per
        design.md §5.3).
      human_version: when supplied, also render + write the human
        convergence report (``output/convergence/<version>-convergence.md``)
        and refresh the digest (``output/DIGEST.md``).
      human_requirements_path: path to ``input/requirements.md`` for the
        per-REQ evidence rows (consumed via :func:`trace_requirements`).
      human_test_results: optional ``{node-id -> TestOutcome}`` map threaded
        into the §6c test-run join (typically :func:`parse_pytest_report`).
      human_findings: gate findings feeding the blocking/advisory split.
      human_stagnation: when ``True`` the human status is forced to
        ``human_needed`` (W-8/SI-9 escalation).

    Returns:
      Dict with keys ``"workspace"``, ``"memory"``, ``"rules"`` (each
      mapped to a single :class:`Path`) plus ``"changes"`` (list of
      :class:`Path` for every per-archive REPORT) and ``"human"`` (a
      ``{"convergence": Path, "digest": Path}`` mapping when
      ``human_version`` was supplied, else ``None``). The plural
      ``changes`` key was chosen over the singular ``change`` so callers can
      tell "one report for the change folder" from "many reports across all
      archives" at a glance.

    Idempotency: with a pinned ``now``, two successive invocations
    produce byte-identical files for every output path.

    Raises:
      HumanBudgetExceededError: when the rendered digest exceeds its C-9
        hard ceiling (REQ-OUT-01 — BLOCKING since v14.2.0); neither human
        OUTPUT artifact is written in that case.
    """
    root = _resolve_repo_root(repo_root)
    pinned_now = _normalise_now(now)

    workspace_text = render_workspace_report(
        repo_root=root,
        archive_window_days=archive_window_days,
        now=pinned_now,
    )
    memory_text = render_memory_report(
        repo_root=root,
        window_days=memory_window_days,
        now=pinned_now,
    )
    rules_text = render_rules_report(repo_root=root, now=pinned_now)

    workspace_path = _write_report(root / WORKSPACE_REPORT_PATH_DEFAULT, workspace_text)
    memory_path = _write_report(root / MEMORY_REPORT_PATH_DEFAULT, memory_text)
    rules_path = _write_report(root / RULES_REPORT_PATH_DEFAULT, rules_text)

    change_paths: list[Path] = []
    store = _make_store(root)
    for date_prefix, change_id in store.list_archive():
        archive_folder = store.archive_root / f"{date_prefix}-{change_id}"
        try:
            text = render_change_report(
                change_id,
                repo_root=root,
                now=pinned_now,
            )
        except (ChangeNotFoundError, DeltaSpecParseError) as exc:
            logger.warning(
                "regenerate_all: skipping %s (%s)",
                change_id,
                exc,
            )
            continue
        change_paths.append(_write_report(archive_folder / "REPORT.md", text))

    human_result: dict[str, Path] | None = None
    if human_version is not None:
        convergence_text = render_human_report(
            human_version,
            repo_root=root,
            requirements_path=human_requirements_path,
            test_results=human_test_results,
            findings=human_findings,
            stagnation=human_stagnation,
            now=pinned_now,
        )
        digest_text = render_human_digest(
            human_version,
            repo_root=root,
            requirements_path=human_requirements_path,
            test_results=human_test_results,
            findings=human_findings,
            stagnation=human_stagnation,
            now=pinned_now,
        )
        # REQ-OUT-01 (BLOCKING since v14.2.0): raises before either human
        # OUTPUT artifact is written, so a failed run leaves no partial pair.
        _check_digest_budget(digest_text)
        convergence_path = _write_report(
            root / _human_convergence_path(human_version), convergence_text
        )
        digest_path = _write_report(root / HUMAN_DIGEST_PATH_DEFAULT, digest_text)
        human_result = {"convergence": convergence_path, "digest": digest_path}

    return {
        "workspace": workspace_path,
        "memory": memory_path,
        "rules": rules_path,
        "changes": change_paths,
        "human": human_result,
    }


def _enumerate_rule_layers(rules_dir: Path) -> tuple[list[dict], int]:
    """Return ``(layer_rows, total_rules)`` for the rules report."""
    layers: list[dict] = []
    total = 0
    for label, filename in RULES_LAYERS:
        path = rules_dir / filename
        if not path.exists():
            layers.append(
                {
                    "label": label,
                    "file": filename,
                    "rule_count": 0,
                    "always_apply": "<missing>",
                    "token_est": 0,
                }
            )
            continue
        text = path.read_text(encoding="utf-8")
        rule_count = sum(1 for line in text.splitlines() if _RULE_HEADING_RE.match(line))
        total += rule_count
        fm = _parse_frontmatter(text)
        always = fm.get("alwaysApply")
        if always is True:
            always_str = "yes"
        elif always is False:
            always_str = "no"
        else:
            always_str = "<unknown>"
        token_est = len(text) // 4
        layers.append(
            {
                "label": label,
                "file": filename,
                "rule_count": rule_count,
                "always_apply": always_str,
                "token_est": token_est,
            }
        )
    return layers, total


def _enumerate_compile_targets(root: Path, rules_dir: Path) -> tuple[list[dict], str]:
    """Read ``.rules/.compile-hashes.json`` and the compile-config to build target rows.

    Returns ``(target_rows, drift_status)``. ``drift_status`` is ``"OK"``
    when the hash file exists with at least one target entry; ``"stale"``
    when the hash file is empty; ``"missing"`` when absent.
    """
    config_path = rules_dir / "compile-config.yaml"
    config: dict = {}
    if config_path.exists():
        try:
            parsed = yaml.safe_load(config_path.read_text(encoding="utf-8"))
            if isinstance(parsed, dict):
                config = parsed
        except yaml.YAMLError:
            config = {}

    hashes_path = rules_dir / ".compile-hashes.json"
    hashes: dict = {}
    if hashes_path.exists():
        try:
            hashes_data = json.loads(hashes_path.read_text(encoding="utf-8"))
            if isinstance(hashes_data, dict):
                hashes = hashes_data
        except json.JSONDecodeError:
            hashes = {}

    rows: list[dict] = []
    targets_section = config.get("targets") or {}
    if isinstance(targets_section, dict):
        for name, meta in sorted(targets_section.items()):
            if not isinstance(meta, dict):
                continue
            output = str(meta.get("output", "<unknown>"))
            output_path = root / output if not Path(output).is_absolute() else Path(output)
            status = _compile_target_status(name, hashes, output_path)
            rows.append({"name": name, "output": output, "status": status})

    if not hashes_path.exists():
        drift_status = "missing"
    elif not hashes:
        drift_status = "stale"
    else:
        drift_status = "OK"
    return rows, drift_status


def _compile_target_status(name: str, hashes: dict, output_path: Path) -> str:
    """Compute the per-target status string for the rules report table.

    The recorded hash (if any) is always surfaced verbatim; an absent
    output file is appended as a parenthetical so the audit trail keeps
    the hash visible even when the file got moved/cleaned externally.
    """
    recorded_hash = hashes.get(name)
    if not recorded_hash:
        return "no recorded hash"
    if not output_path.exists():
        return f"hash {recorded_hash} (output missing)"
    return f"hash {recorded_hash} on file"


def main(argv: list[str] | None = None) -> int:
    """CLI for ``python -m devolaflow.agent_workspace.reporter``.

    Flags:
      ``--all``          regenerate every report at the canonical paths.
      ``--workspace``    write only ``.local/.agent/REPORT.md``.
      ``--memory``       write only ``.local/memory/REPORT.md``.
      ``--rules``        write only ``.rules/REPORT.md``.
      ``--change <id>``  write only the per-change report (to the change's
                         archive folder, falling back to the active folder
                         when the change is not yet archived).
      ``--human <ver>``  write the human convergence report for ``<ver>`` and
                         refresh the digest (pair with ``--requirements``).
      ``--requirements`` path to ``requirements.md`` for ``--human``.
      ``--repo-root``    pin the repo root (default: cwd).
      ``--now <iso>``    pin the render clock (ISO-8601, e.g.
                         ``2026-08-28T00:00:00Z``); a fixed value yields
                         byte-identical output across invocations (AC-5).
      ``--print``        write to stdout instead of disk (only valid with
                         a single ``--workspace`` / ``--memory`` /
                         ``--rules`` / ``--change`` flag).

    Returns 0 on success, 2 on usage error, 1 on render failure.
    """
    parser = argparse.ArgumentParser(
        prog="python -m devolaflow.agent_workspace.reporter",
        description="Render REPORT.md files from the v8.2.5 agent workspace tree.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repo root (default: current working directory)",
    )
    parser.add_argument("--all", action="store_true", help="Regenerate every report.")
    parser.add_argument(
        "--workspace", action="store_true", help="Render only the workspace report."
    )
    parser.add_argument("--memory", action="store_true", help="Render only the memory report.")
    parser.add_argument("--rules", action="store_true", help="Render only the rules report.")
    parser.add_argument(
        "--change",
        type=str,
        default=None,
        help="Render only the per-change report for <change-id>.",
    )
    parser.add_argument(
        "--human",
        type=str,
        default=None,
        metavar="VERSION",
        help="Render the human convergence report for <version> + refresh the digest.",
    )
    parser.add_argument(
        "--requirements",
        type=Path,
        default=None,
        help="Path to requirements.md for --human (REQ-ID -> evidence trace).",
    )
    parser.add_argument(
        "--now",
        type=str,
        default=None,
        metavar="ISO_DATETIME",
        help="Pin the render clock to an ISO-8601 instant (e.g. "
        "2026-08-28T00:00:00Z) for byte-identical repeated output.",
    )
    parser.add_argument(
        "--print",
        action="store_true",
        dest="print_to_stdout",
        help="Print rendered text to stdout instead of writing to disk "
        "(only valid with a single non-`--all` flavour).",
    )
    parser.add_argument(
        "--archive-window-days",
        type=int,
        default=DEFAULT_ARCHIVE_WINDOW_DAYS,
        help=f"Archive lookback window for the workspace report "
        f"(default: {DEFAULT_ARCHIVE_WINDOW_DAYS} days).",
    )
    parser.add_argument(
        "--memory-window-days",
        type=int,
        default=DEFAULT_MEMORY_WINDOW_DAYS,
        help=f"Memory lookback window for the top-N section "
        f"(default: {DEFAULT_MEMORY_WINDOW_DAYS} days).",
    )
    args = parser.parse_args(argv)

    flavours = sum(
        1
        for flag in (
            args.all,
            args.workspace,
            args.memory,
            args.rules,
            bool(args.change),
            bool(args.human),
        )
        if flag
    )
    if flavours == 0:
        parser.error(
            "specify --all, --workspace, --memory, --rules, --change <id>, or --human <ver>"
        )
    if args.print_to_stdout and (args.all or flavours > 1):
        parser.error("--print is only valid with a single non-`--all` flavour")

    root = _resolve_repo_root(args.repo_root)
    pinned_now: datetime | None = None
    if args.now is not None:
        try:
            pinned_now = datetime.fromisoformat(args.now)
        except ValueError:
            parser.error(f"--now must be an ISO-8601 datetime, got: {args.now!r}")

    try:
        if args.all:
            results = regenerate_all(
                repo_root=root,
                now=pinned_now,
                archive_window_days=args.archive_window_days,
                memory_window_days=args.memory_window_days,
            )
            _print_results(results)
            return 0
        if args.workspace:
            return _emit_one(
                render_workspace_report(
                    repo_root=root,
                    archive_window_days=args.archive_window_days,
                    now=pinned_now,
                ),
                root / WORKSPACE_REPORT_PATH_DEFAULT,
                to_stdout=args.print_to_stdout,
            )
        if args.memory:
            return _emit_one(
                render_memory_report(
                    repo_root=root,
                    window_days=args.memory_window_days,
                    now=pinned_now,
                ),
                root / MEMORY_REPORT_PATH_DEFAULT,
                to_stdout=args.print_to_stdout,
            )
        if args.rules:
            return _emit_one(
                render_rules_report(repo_root=root, now=pinned_now),
                root / RULES_REPORT_PATH_DEFAULT,
                to_stdout=args.print_to_stdout,
            )
        if args.change:
            text = render_change_report(args.change, repo_root=root, now=pinned_now)
            target = _change_report_target(root, args.change)
            return _emit_one(text, target, to_stdout=args.print_to_stdout)
        if args.human:
            convergence_text = render_human_report(
                args.human,
                repo_root=root,
                requirements_path=args.requirements,
                now=pinned_now,
            )
            if args.print_to_stdout:
                return _emit_one(
                    convergence_text,
                    root / _human_convergence_path(args.human),
                    to_stdout=True,
                )
            digest_text = render_human_digest(
                args.human,
                repo_root=root,
                requirements_path=args.requirements,
                now=pinned_now,
            )
            # REQ-OUT-01 (BLOCKING since v14.2.0): checked before either
            # write so a failed run leaves no partial OUTPUT pair.
            _check_digest_budget(digest_text)
            convergence_path = _write_report(
                root / _human_convergence_path(args.human), convergence_text
            )
            digest_path = _write_report(root / HUMAN_DIGEST_PATH_DEFAULT, digest_text)
            print(f"wrote {convergence_path}", file=sys.stderr)
            print(f"wrote {digest_path}", file=sys.stderr)
            return 0
    except (ChangeNotFoundError, FileNotFoundError) as exc:
        print(f"reporter: {exc}", file=sys.stderr)
        return 2
    except HumanBudgetExceededError as exc:
        print(f"reporter: {exc}", file=sys.stderr)
        return 1
    except (DeltaSpecParseError, HandoffStoreError) as exc:
        print(f"reporter: render failed: {exc}", file=sys.stderr)
        return 1
    return 0


def _emit_one(text: str, target: Path, *, to_stdout: bool) -> int:
    if to_stdout:
        sys.stdout.write(text)
        if not text.endswith("\n"):
            sys.stdout.write("\n")
        return 0
    written = _write_report(target, text)
    print(f"wrote {written}", file=sys.stderr)
    return 0


def _change_report_target(root: Path, change_id: str) -> Path:
    """Resolve the on-disk REPORT.md path for ``change_id`` (archive then active)."""
    archive_dir = root / ARCHIVE_DIR_DEFAULT
    if archive_dir.is_dir():
        for child in sorted(archive_dir.iterdir()):
            if not child.is_dir():
                continue
            stripped = child.name
            m = _ARCHIVE_DATE_PREFIX_RE.match(child.name)
            if m:
                stripped = child.name[len(m.group(0)) :]
            if stripped == change_id:
                return child / "REPORT.md"
    return root / ACTIVE_DIR_DEFAULT / change_id / "REPORT.md"


def _print_results(results: dict[str, object]) -> None:
    for key in ("workspace", "memory", "rules"):
        path = results.get(key)
        if isinstance(path, Path):
            print(f"wrote {path}", file=sys.stderr)
    changes = results.get("changes") or []
    if isinstance(changes, list):
        for path in changes:
            if isinstance(path, Path):
                print(f"wrote {path}", file=sys.stderr)
    human = results.get("human")
    if isinstance(human, dict):
        for path in human.values():
            if isinstance(path, Path):
                print(f"wrote {path}", file=sys.stderr)


if __name__ == "__main__":  # pragma: no cover - CLI entry only
    raise SystemExit(main())

__all__ = [
    name
    for name in globals()
    if name not in {"__name__", "__package__", "__loader__", "__spec__", "__builtins__", "__all__"}
]
