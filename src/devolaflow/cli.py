"""CLI entry points for DevolaFlow tools.

Design ref: design_meta_framework.md §5 (registry), design_decomposition_gate.md §5 (gate)
"""

import argparse
import sys
from pathlib import Path

# Stdlib-only at module level (the codec's devolaflow imports stay lazy), so
# the CLI keeps its cheap-import property.
from devolaflow.local.archive_payloads import (
    _LOCAL_ARCHIVE_INDEX_LINE,
    _LOCAL_ARCHIVE_SCHEMA_VERSION,
    _local_archive_finding,
    _local_archive_json,
    _local_archive_load_plan,
    _local_archive_plan_payload,
    _local_archive_result_payload,
    _LocalArchiveInputError,
)


def version_cmd() -> None:
    """Print the current DevolaFlow version."""
    from devolaflow import __version__

    print(f"DevolaFlow v{__version__}")


def validate_template_cmd() -> None:
    """Validate workflow template YAML files.

    Usage:
      validate-template --all          Validate all builtin templates.
      validate-template <path>         Validate a single template file.
    """
    if "--all" in sys.argv:
        from devolaflow.template_engine.validator import validate_all_templates

        success = validate_all_templates(all_flag=True)
        sys.exit(0 if success else 1)

    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not args:
        print("Usage: validate-template --all | validate-template <path>")
        sys.exit(1)

    from devolaflow.template_engine.parser import parse_template
    from devolaflow.template_engine.validator import validate_template

    path = Path(args[0])
    if not path.exists():
        print(f"FAIL: {path} (file not found)")
        sys.exit(1)

    try:
        tpl = parse_template(path)
    except Exception as exc:
        print(f"FAIL: {path} (parse error: {exc})")
        sys.exit(1)

    result = validate_template(tpl)
    if result.valid:
        print(f"PASS: {path}")
    else:
        print(f"FAIL: {path}")
        for err in result.errors:
            print(f"  ERROR: {err}")
    for warn in result.warnings:
        print(f"  WARNING: {warn}")
    sys.exit(0 if result.valid else 1)


def validate_gate_cmd() -> None:
    """Evaluate a gate quality checkpoint."""
    from devolaflow.gate.scorer import run_gate_cli

    run_gate_cli(sys.argv[1:])


def build_skill_cmd() -> None:
    """Build skill outputs for all target tools."""
    from devolaflow.build_skill import build_all

    build_all(sys.argv[1:])


def check_drift_cmd() -> None:
    """Check human docs for drift against agent source."""
    from devolaflow.check_drift import check_drift

    has_drift = check_drift()
    sys.exit(1 if has_drift else 0)


def detect_repo_mode_cmd() -> None:
    """Detect repository mode from git remote."""
    from devolaflow.pre_decision.detect import detect_and_print

    detect_and_print()


def sync_rules_cmd() -> None:
    """Compile .rules/ governance rules to all AI tool formats."""
    from devolaflow.local.compiler import RuleCompiler

    config_path = Path.cwd() / ".rules" / "compile-config.yaml"
    if not config_path.exists():
        print("No .rules/compile-config.yaml found. Run 'devola-init' first.")
        sys.exit(1)

    compiler = RuleCompiler(config_path)
    results = compiler.compile_all()
    for r in results:
        print(
            f"  {r.target}: {r.tokens_used}/{r.tokens_budget} tokens, layers: {r.layers_included}"
        )
    print(f"\n  {len(results)} target(s) compiled.")


def check_rules_drift_cmd() -> None:
    """Check compiled rules for drift against .rules/ source."""
    from devolaflow.local.drift import check_rules_drift

    rules_dir = Path.cwd() / ".rules"
    if not rules_dir.is_dir():
        print("No .rules/ directory found.")
        sys.exit(1)

    results = check_rules_drift(rules_dir)
    any_drift = False
    for r in results:
        status_icon = {"in_sync": "✅", "drifted": "⚠️", "missing": "❌"}.get(r.status, "?")
        print(f"  {status_icon} {r.target} — {r.status}")
        if r.status != "in_sync":
            any_drift = True
    sys.exit(1 if any_drift else 0)


def scaffold_local_cmd() -> None:
    """Initialize .local/ workspace structure."""
    from devolaflow.local.workspace import (
        ScaffoldStructureError,
        ScaffoldVerificationError,
        scaffold_local,
    )

    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    dirs = args if args else None
    try:
        scaffold_local(Path.cwd(), dirs=dirs)
    except (ScaffoldVerificationError, ScaffoldStructureError) as exc:
        print(f"  FAIL {exc}")
        sys.exit(1)
    print("  .local/ workspace initialized.")


def doctor_cmd() -> None:
    """Check repo-init canonical manifest health (default) or skill installs.

    Default mode scans the current working directory against the canonical
    manifest for repo-init and reports missing paths. Exit 0 if healthy,
    1 if not.

    ``--skills`` mode (full_review_and_improve Track B-2) scans the known
    DevolaFlow skill install locations (project + user-global, mirroring
    the ``scripts/install.sh`` detection matrix) and reports each install's
    stamped version against the running package ``__version__``. Exit 0
    when every found install is current (or none found), 1 when any is
    stale or carries an unknown version.
    """
    if "--skills" in sys.argv:
        _doctor_skills()
        return

    from devolaflow.init_probe import format_capability_table, probe_capabilities
    from devolaflow.lifecycle.validate_owned_files import check_init_health

    # Track C-4 (R5 F4): the doctor surfaces the same init-chain
    # capability table as `devola-init local` (A-5 — one dependency tier
    # table, two readers) so existing repos can audit their environment
    # after the fact. Informational here — doctor exit code stays keyed
    # to the structure contract only.
    print(format_capability_table(probe_capabilities()))
    print()

    report = check_init_health(Path.cwd())
    for f in report.findings:
        icon = "⚠️" if (f.advisory and not f.ok) else ("✅" if f.ok else "❌")
        print(f"  {icon} {f.path} — {f.detail}")
    print()
    if report.healthy:
        print("  All canonical paths present. Workspace is healthy.")
        if report.advisories:
            print(f"  {len(report.advisories)} advisory finding(s) (non-blocking).")
    else:
        print(f"  {len(report.missing)} missing path(s): {report.missing}")
        print("  Run 'devola-init local' to fix.")
    sys.exit(0 if report.healthy else 1)


def _doctor_skills() -> None:
    """`devola-init-doctor --skills` — skill-install version scan."""
    from devolaflow import __version__
    from devolaflow.skills_doctor import scan_installed_skills

    installs = scan_installed_skills()
    if not installs:
        print("  No DevolaFlow skill installs found (project or user-global).")
        print("  Install one: bash scripts/install.sh <tool>  (or devola-init <tool>)")
        sys.exit(0)

    icons = {"current": "✅", "stale": "⚠️", "unknown-version": "❓"}
    for inst in installs:
        version = inst.installed_version or "(no stamp)"
        print(f"  {icons[inst.status]} {inst.tool:<9} {inst.scope:<8} {version:<12} {inst.path}")
    print()
    not_current = [i for i in installs if i.status != "current"]
    if not_current:
        print(f"  {len(not_current)}/{len(installs)} install(s) not at v{__version__}.")
        print("  Refresh: bash scripts/install.sh update  (or devola-init <tool>)")
        sys.exit(1)
    print(f"  All {len(installs)} install(s) current (v{__version__}).")
    sys.exit(0)


# ---------------------------------------------------------------------------
# v9.4.0 PV-04 — `devolaflow plugins` CLI subcommand group
# ---------------------------------------------------------------------------
#
# Closes D-P-4 (MAJOR — daily-upgrade surface) + D-P-8 (MINOR — registry
# refresh UX) from `.local/research/v9.4.0_gap_analysis.md` §3.2.
#
# Subcommands:
#   plugins list                     show all plugins + install state + last_checked
#   plugins status                   alias of `plugins list` (more discoverable name)
#   plugins refresh [--force]        upgrade stale plugins
#                   [--plugin <id>]  restrict to a single plugin
#
# Exit codes (stable contract):
#   0  — happy path
#   1  — runtime failure (registry unreadable / one or more upgrades failed)
#   2  — invocation error (unknown subcommand / bad flags)


def plugins_cmd() -> None:
    """`devolaflow plugins {list,status,refresh}` — registry inspection + upgrade CLI.

    PV-04 contract per gap analysis §6 AC-4 + AC-5 + AC-7:
    * `plugins list` / `plugins status` — pure inspection (no installs)
    * `plugins refresh` — daily-upgrade entry point; iterates registry,
      upgrades stale plugins, reports per-plugin outcome
    * `plugins refresh --force` — upgrade ALL plugins regardless of staleness
    * `plugins refresh --plugin <id>` — restrict to a single plugin
    * Network failures are reported as WARN per outcome row, NOT crashes
      (exit 1 only if AT LEAST ONE upgrade failed)
    """
    import argparse
    import json as _json

    from devolaflow.plugins.installer import list_plugins, refresh_all

    parser = argparse.ArgumentParser(
        prog="devolaflow plugins",
        description="DevolaFlow runtime plugin registry inspection + daily upgrade",
    )
    sub = parser.add_subparsers(dest="subcmd", required=True)

    list_parser = sub.add_parser("list", help="show all plugins + install state + last_checked")
    list_parser.add_argument(
        "--json",
        action="store_true",
        help="emit machine-readable JSON instead of the human-readable table",
    )

    status_parser = sub.add_parser(
        "status", help="alias of `plugins list` (more discoverable name)"
    )
    status_parser.add_argument(
        "--json",
        action="store_true",
        help="emit machine-readable JSON instead of the human-readable table",
    )

    refresh_parser = sub.add_parser(
        "refresh", help="upgrade stale plugins (default: stale = > 24h since last check)"
    )
    refresh_parser.add_argument(
        "--force",
        action="store_true",
        help="upgrade EVERY plugin regardless of staleness",
    )
    refresh_parser.add_argument(
        "--plugin",
        action="append",
        dest="plugins",
        metavar="ID",
        help="restrict refresh to this plugin (repeatable)",
    )
    refresh_parser.add_argument(
        "--json",
        action="store_true",
        help="emit machine-readable JSON instead of the human-readable table",
    )

    args = parser.parse_args(sys.argv[1:])

    if args.subcmd in ("list", "status"):
        try:
            rows = list_plugins()
        except FileNotFoundError as exc:
            print(f"FAIL: {exc}", file=sys.stderr)
            sys.exit(1)
        if args.json:
            print(_json.dumps(rows, indent=2, sort_keys=True))
            sys.exit(0)
        if not rows:
            print("No plugins registered.")
            sys.exit(0)
        # Human-readable table.
        print(f"{'ID':<14} {'BACKEND':<22} {'INSTALLED':<14} {'LAST CHECKED':<28} WORKFLOWS")
        print("-" * 100)
        for row in rows:
            installed = row["installed_version"] or "(missing)"
            last = row["last_checked"] or "(never)"
            workflows = ",".join(row["invoked_by_workflows"]) or "—"
            print(f"{row['id']:<14} {row['backend']:<22} {installed:<14} {last:<28} {workflows}")
        sys.exit(0)

    if args.subcmd == "refresh":
        try:
            outcomes = refresh_all(force=args.force, only=args.plugins)
        except FileNotFoundError as exc:
            print(f"FAIL: {exc}", file=sys.stderr)
            sys.exit(1)
        if args.json:
            print(
                _json.dumps(
                    [
                        {
                            "plugin_id": o.plugin_id,
                            "action": o.action,
                            "version": o.version,
                            "reason": o.reason,
                            "error": o.error,
                        }
                        for o in outcomes
                    ],
                    indent=2,
                    sort_keys=True,
                )
            )
        else:
            if not outcomes:
                print("No plugins matched the refresh filter.")
            for o in outcomes:
                if o.action == "upgraded":
                    print(f"  ✓ {o.plugin_id} → {o.version} (upgraded)")
                elif o.action == "skipped_fresh":
                    print(f"  · {o.plugin_id} — skipped ({o.reason})")
                elif o.action == "failed":
                    print(f"  ✗ {o.plugin_id} — FAILED: {o.error}", file=sys.stderr)
                else:
                    print(f"  ? {o.plugin_id} — {o.action}: {o.reason or o.error or ''}")
        # Exit non-zero if ANY upgrade failed (per gap analysis §6 AC-7).
        any_failure = any(o.action == "failed" for o in outcomes)
        sys.exit(1 if any_failure else 0)

    parser.print_help(sys.stderr)
    sys.exit(2)


# ---------------------------------------------------------------------------
# Explicit local-task archive command
# ---------------------------------------------------------------------------

LOCAL_ARCHIVE_REPORT = 0
LOCAL_ARCHIVE_MALFORMED = 2
LOCAL_ARCHIVE_SAFETY_REFUSAL = 3
LOCAL_ARCHIVE_APPROVAL_MISMATCH = 4
LOCAL_ARCHIVE_MAPPING_CONFLICT = 5


def _local_archive_exit_code(
    findings: tuple[object, ...] | list[object], *, success: bool = True, refused: bool = False
) -> int:
    codes = {finding.code for finding in findings}
    if codes & {"APPROVAL_MISMATCH", "PLAN_CHANGED", "APPROVAL_REQUIRED", "EMPTY_APPROVAL"}:
        return LOCAL_ARCHIVE_APPROVAL_MISMATCH
    if codes & {
        "MAPPING_DUPLICATE",
        "MALFORMED_MAPPING",
        "MAPPING_CONFLICT",
        "MAPPING_DRIFT",
        "MAPPING_SEQUENCE",
        "DUPLICATE_DESTINATION",
    }:
        return LOCAL_ARCHIVE_MAPPING_CONFLICT
    if codes & {
        "PROTECTED_PATH",
        "SYMLINK_PATH",
        "DIRTY_TREE",
        "STAGED_DIFF",
        "UNSTAGED_DIFF",
        "UNTRACKED_REVIEW_NOTE",
        "NESTED_REPOSITORY",
        "WORKTREE_REGISTRY",
        "REPOSITORY_BOUNDARY",
        "MISSING_SOURCE",
        "DESTINATION_EXISTS",
        "UNREADABLE_SOURCE",
        "GIT_INSPECTION_ERROR",
        "CROSS_DEVICE",
        "HUMAN_INDEX",
        "INDEX_DRIFT",
        "INDEX_MISSING",
        "MAPPING_DESTINATION_MISSING",
        "MAPPING_SOURCE_PRESENT",
        "PARTIAL_APPLY",
    }:
        return LOCAL_ARCHIVE_SAFETY_REFUSAL
    if findings or not success or refused:
        return LOCAL_ARCHIVE_SAFETY_REFUSAL
    return LOCAL_ARCHIVE_REPORT


def _local_archive_doctor_findings(root: Path, plan: object) -> tuple[object, ...]:
    from devolaflow.local import archive as archive_module

    adapter = archive_module.get_archive_adapter(getattr(plan, "surface", "tasks"))

    findings = list(plan.findings)
    destinations = {entry.destination for entry in plan.entries}
    for destination in sorted(
        destination
        for destination in destinations
        if sum(entry.destination == destination for entry in plan.entries) > 1
    ):
        findings.append(
            archive_module.Finding(
                "DUPLICATE_DESTINATION",
                f"multiple entries target {destination}",
            )
        )
    for entry in plan.entries:
        findings.extend(entry.findings)
        if entry.protection.value != "allowed":
            findings.append(
                archive_module.Finding(
                    "PROTECTED_PATH",
                    f"entry is not eligible: {entry.source} ({entry.protection.value})",
                )
            )

    index_path = root / adapter.index_path
    if index_path.is_symlink():
        findings.append(archive_module.Finding("SYMLINK_INDEX", "index target is a symlink"))
        index_pairs: set[tuple[str, str]] = set()
    elif not index_path.exists():
        findings.append(archive_module.Finding("INDEX_MISSING", adapter.index_path))
        index_pairs: set[tuple[str, str]] = set()
    else:
        try:
            index_text = index_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            findings.append(archive_module.Finding("UNREADABLE_INDEX", str(exc)))
            index_pairs = set()
        else:
            if not index_text.startswith(adapter.index_marker):
                findings.append(
                    archive_module.Finding(
                        "HUMAN_INDEX", "refusing to treat a human index as generated"
                    )
                )
            index_pairs = {
                (destination, source)
                for destination, source in _LOCAL_ARCHIVE_INDEX_LINE.findall(index_text)
            }

    mapping_path = root / adapter.mapping_path
    if mapping_path.is_symlink():
        findings.append(archive_module.Finding("MAPPING_CONFLICT", "mapping path is a symlink"))
        mappings = ()
    else:
        try:
            mappings = archive_module._load_mapping_records(mapping_path)
        except archive_module.ArchiveError as exc:
            findings.append(archive_module.Finding("MALFORMED_MAPPING", str(exc)))
            mappings = ()

    sequences = [mapping.sequence for mapping in mappings]
    if sequences != sorted(sequences) or len(set(sequences)) != len(sequences):
        findings.append(
            archive_module.Finding(
                "MAPPING_SEQUENCE", "mapping sequences must be strictly increasing"
            )
        )
    expected_pairs: set[tuple[str, str]] = set()
    for mapping in mappings:
        pair = (mapping.destination, mapping.source)
        expected_pairs.add(pair)
        destination_path = root / mapping.destination
        source_path = root / mapping.source
        destination_exists = (
            destination_path.is_dir() if adapter.requires_directory else destination_path.is_file()
        )
        if not destination_exists:
            findings.append(
                archive_module.Finding(
                    "MAPPING_DESTINATION_MISSING",
                    f"mapped destination is missing: {mapping.destination}",
                )
            )
        if source_path.exists():
            findings.append(
                archive_module.Finding(
                    "MAPPING_SOURCE_PRESENT",
                    f"mapped source still exists: {mapping.source}",
                )
            )
        if pair not in index_pairs:
            findings.append(
                archive_module.Finding(
                    "MAPPING_DRIFT",
                    f"mapping is absent from generated index: {mapping.source}",
                )
            )

    if index_path.exists() and not index_path.is_symlink() and index_pairs != expected_pairs:
        findings.append(
            archive_module.Finding(
                "INDEX_DRIFT",
                "generated index entries do not match authoritative mapping records",
            )
        )

    for entry in plan.entries:
        if entry.action != "move":
            continue
        inspection = archive_module.inspect_safety(
            root,
            entry.source,
            entry.destination,
            source_boundary=adapter.source_root,
            destination_boundary=adapter.archive_root,
            requires_directory=adapter.requires_directory,
        )
        findings.extend(inspection.findings)
    return tuple(findings)


def _local_archive_doctor(
    root: Path, plan_path: Path | None, surface: str = "tasks"
) -> tuple[dict[str, object], int]:
    from devolaflow.local.archive import ArchiveApproval, build_archive_plan

    try:
        plan = (
            _local_archive_load_plan(plan_path)
            if plan_path is not None
            else build_archive_plan(root, surface=surface)
        )
        if isinstance(plan, ArchiveApproval):
            raise _LocalArchiveInputError("doctor requires an archive-plan artifact")
    except _LocalArchiveInputError as exc:
        payload = {
            "artifact_type": f"{surface}-archive-doctor",
            "schema_version": _LOCAL_ARCHIVE_SCHEMA_VERSION,
            "findings": [{"code": "MALFORMED_PLAN", "message": str(exc)}],
            "healthy": False,
        }
        return payload, LOCAL_ARCHIVE_MALFORMED
    findings = _local_archive_doctor_findings(root, plan)
    payload = {
        "artifact_type": f"{getattr(plan, 'surface', surface)}-archive-doctor",
        "schema_version": _LOCAL_ARCHIVE_SCHEMA_VERSION,
        "plan_fingerprint": plan.fingerprint,
        "findings": [_local_archive_finding(finding) for finding in findings],
        "healthy": not findings,
    }
    return payload, _local_archive_exit_code(findings)


def local_archive_cmd() -> None:
    """Report or explicitly apply a reviewed local archive plan."""
    parser = argparse.ArgumentParser(
        prog="devola-local-archive",
        description=("Report-only local archive planning; apply requires an approved plan file."),
    )
    parser.add_argument(
        "mode",
        nargs="?",
        choices=("doctor",),
        help="validate plan, index, mapping, safety, and no-clobber contracts",
    )
    parser.add_argument("--repo-root", type=Path, default=Path.cwd(), help=argparse.SUPPRESS)
    parser.add_argument(
        "--surface",
        choices=("tasks", "feedbacks", "research"),
        default="tasks",
        help="registered local surface to inventory",
    )
    parser.add_argument("--plan", type=Path, help="plan artifact to validate or use as approval")
    parser.add_argument(
        "--apply", metavar="PLAN", type=Path, help="apply the approved PLAN artifact"
    )
    parser.add_argument("--doctor", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(sys.argv[1:])
    root = args.repo_root

    if args.mode == "doctor" or args.doctor:
        if args.apply is not None:
            parser.error("doctor cannot be combined with --apply")
        payload, exit_code = _local_archive_doctor(root, args.plan, args.surface)
        print(_local_archive_json(payload), end="")
        sys.exit(exit_code)

    if args.apply is None:
        from devolaflow.local.archive import build_archive_plan

        plan = build_archive_plan(root, surface=args.surface)
        print(_local_archive_json(_local_archive_plan_payload(plan)), end="")
        sys.exit(LOCAL_ARCHIVE_REPORT)

    if args.plan is not None:
        parser.error("--plan is only used with doctor; --apply names the approved plan")
    try:
        plan = _local_archive_load_plan(args.apply)
    except _LocalArchiveInputError as exc:
        payload = {
            "artifact_type": "task-archive-result",
            "schema_version": _LOCAL_ARCHIVE_SCHEMA_VERSION,
            "findings": [{"code": "MALFORMED_PLAN", "message": str(exc)}],
            "refused": True,
            "success": False,
        }
        print(_local_archive_json(payload), end="")
        sys.exit(LOCAL_ARCHIVE_MALFORMED)

    from devolaflow.local.archive import (
        ArchiveApproval,
        ArchiveError,
        apply_archive_plan,
        build_archive_plan,
    )

    approved = (
        plan
        if isinstance(plan, ArchiveApproval)
        else tuple(entry for entry in plan.entries if entry.action == "move")
    )
    try:
        if isinstance(plan, ArchiveApproval):
            current_plan = build_archive_plan(root)
            result = apply_archive_plan(root, current_plan, approved)
        else:
            result = apply_archive_plan(root, plan, approved)
    except ArchiveError as exc:
        payload = {
            "artifact_type": "task-archive-result",
            "schema_version": _LOCAL_ARCHIVE_SCHEMA_VERSION,
            "findings": [{"code": "MALFORMED_APPROVAL", "message": str(exc)}],
            "refused": True,
            "success": False,
        }
        print(_local_archive_json(payload), end="")
        sys.exit(LOCAL_ARCHIVE_MALFORMED)
    print(_local_archive_json(_local_archive_result_payload(result)), end="")
    sys.exit(
        _local_archive_exit_code(
            result.findings,
            success=result.success,
            refused=result.refused,
        )
    )
