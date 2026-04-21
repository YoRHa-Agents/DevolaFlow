"""CLI entry points for DevolaFlow tools.

Design ref: design_meta_framework.md §5 (registry), design_decomposition_gate.md §5 (gate)
"""

import sys
from pathlib import Path


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
    from devolaflow.local.workspace import scaffold_local

    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    dirs = args if args else None
    scaffold_local(Path.cwd(), dirs=dirs)
    print("  .local/ workspace initialized.")


def doctor_cmd() -> None:
    """Check repo-init canonical manifest health.

    Scans the current working directory against the canonical manifest
    for repo-init and reports missing paths. Exit 0 if healthy, 1 if not.
    """
    from devolaflow.lifecycle.validate_owned_files import check_init_health

    report = check_init_health(Path.cwd())
    icons = {True: "✅", False: "❌"}
    for f in report.findings:
        print(f"  {icons[f.ok]} {f.path} — {f.detail}")
    print()
    if report.healthy:
        print("  All canonical paths present. Workspace is healthy.")
    else:
        print(f"  {len(report.missing)} missing path(s): {report.missing}")
        print("  Run 'devola-init local' to fix.")
    sys.exit(0 if report.healthy else 1)
