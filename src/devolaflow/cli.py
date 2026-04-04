"""CLI entry points for DevolaFlow tools.

Design ref: design_meta_framework.md §5 (registry), design_decomposition_gate.md §5 (gate)
"""

import sys
from pathlib import Path


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
