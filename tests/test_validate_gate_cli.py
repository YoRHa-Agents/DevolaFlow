"""Tests for the validate-gate CLI (closes G-B1 ghost; audit §3.B).

The v7.4.4 implementation was ``print("gate: pass (stub)")`` which silently
masked real failures (S-5 No-Silent-Failures violation per audit §3.B).
P-06 in v7.4.5 wires :func:`devolaflow.gate.scorer.run_gate_cli` into the
real :func:`devolaflow.gate.scorer.evaluate_gate` API with structured stdout
output (``decision`` / ``composite`` / ``findings`` / ``rationale``) and
exit codes 0 (PASS) / 1 (FAIL or ESCALATE) / 2 (usage / IO / parse error).

These tests cover every branch of ``run_gate_cli`` plus the YAML→GateInput
helpers, ensuring per-module coverage of ``gate/scorer.py`` stays ≥ 80%
per CP-2 / S-3.
"""

from __future__ import annotations

import sys
from pathlib import Path
from textwrap import dedent

import pytest

from devolaflow.gate.scorer import (
    _build_gate_input,
    _check_result_from_dict,
    _finding_from_dict,
    _format_findings,
    run_gate_cli,
)

# ── Reusable input fixtures (programmatic — no on-disk fixture files needed) ──

PASS_INPUT = dedent(
    """
    build_status:
      status: pass
      details:
        command: pytest
    test_results:
      status: pass
      details:
        coverage_pct: 92.0
        tests_passed: 100
        tests_total: 100
    lint_status:
      status: pass
      details: {}
    review_findings: []
    acceptance_criteria_results:
      status: pass
    """
).strip()

FAIL_BLOCKER_INPUT = dedent(
    """
    build_status:
      status: pass
      details: {}
    test_results:
      status: pass
      details:
        coverage_pct: 88.0
    lint_status:
      status: pass
      details: {}
    review_findings:
      - finding_id: F001
        severity: blocker
        category: security
        location: src/foo.py:1
        description: SQL injection vulnerability
        suggestion: Use parameterised queries
        rule_id: SEC001
      - finding_id: F002
        severity: minor
        category: style
        location: src/bar.py:42
        description: Long line
    """
).strip()

FAIL_BUILD_INPUT = dedent(
    """
    build_status:
      status: fail
      details:
        exit_code: 1
    test_results:
      status: pass
      details: {}
    lint_status:
      status: pass
      details: {}
    """
).strip()


def _write(tmp_path: Path, text: str, *, name: str = "input.yaml") -> Path:
    """Write *text* into ``tmp_path/name`` and return the path."""
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


# ────────────────────────────────────────────────────────────────────────────
# 1. Empty-args contract — print help, return None (no SystemExit)
# ────────────────────────────────────────────────────────────────────────────


def test_run_gate_cli_no_args_prints_help_and_returns(capsys: pytest.CaptureFixture) -> None:
    """Empty args MUST print usage and return without raising (smoke contract)."""
    result = run_gate_cli([])

    assert result is None
    out = capsys.readouterr().out
    assert "validate-gate" in out
    assert "--input" in out


# ────────────────────────────────────────────────────────────────────────────
# 2. --help — argparse exits 0 with usage text
# ────────────────────────────────────────────────────────────────────────────


def test_run_gate_cli_help_exits_zero(capsys: pytest.CaptureFixture) -> None:
    """``--help`` MUST exit 0 and emit usage info."""
    with pytest.raises(SystemExit) as exc:
        run_gate_cli(["--help"])

    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "validate-gate" in out
    assert "--input" in out
    assert "--profile" in out
    assert "--gate-type" in out


# ────────────────────────────────────────────────────────────────────────────
# 3. PASS scenario — gate input passes, exit 0, expected stdout
# ────────────────────────────────────────────────────────────────────────────


def test_run_gate_cli_pass_scenario_exits_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """A passing gate input MUST exit 0 and print ``decision: PASS``."""
    input_path = _write(tmp_path, PASS_INPUT)

    with pytest.raises(SystemExit) as exc:
        run_gate_cli(["--input", str(input_path)])

    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "decision: PASS" in out
    assert "findings: blocker=0 critical=0 major=0 minor=0 info=0" in out
    assert "profile: standard" in out
    assert "gate_type: standard" in out
    assert "rationale:" in out


# ────────────────────────────────────────────────────────────────────────────
# 4. FAIL scenarios — blocker findings + build failure, exit 1
# ────────────────────────────────────────────────────────────────────────────


def test_run_gate_cli_fail_blocker_exits_one(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """A blocker finding MUST exceed STANDARD.max_blocker=0 → FAIL exit 1."""
    input_path = _write(tmp_path, FAIL_BLOCKER_INPUT)

    with pytest.raises(SystemExit) as exc:
        run_gate_cli(["--input", str(input_path)])

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "decision: FAIL" in out
    assert "findings: blocker=1" in out
    assert "minor=1" in out


def test_run_gate_cli_fail_build_exits_one(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """A failing build status MUST yield decision FAIL → exit 1."""
    input_path = _write(tmp_path, FAIL_BUILD_INPUT)

    with pytest.raises(SystemExit) as exc:
        run_gate_cli(["--input", str(input_path)])

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "decision: FAIL" in out
    assert "build" in out


# ────────────────────────────────────────────────────────────────────────────
# 5. Error scenarios — missing file / malformed YAML / bad shape, exit 2
# ────────────────────────────────────────────────────────────────────────────


def test_run_gate_cli_missing_file_exits_usage(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """Missing input file MUST print stderr error and exit 2."""
    missing = tmp_path / "no-such-file.yaml"

    with pytest.raises(SystemExit) as exc:
        run_gate_cli(["--input", str(missing)])

    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "input file not found" in err
    assert str(missing) in err


def test_run_gate_cli_malformed_yaml_exits_usage(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """Unparseable YAML MUST print stderr error and exit 2."""
    bad = _write(tmp_path, "build_status: [unclosed\n  oops:\n", name="bad.yaml")

    with pytest.raises(SystemExit) as exc:
        run_gate_cli(["--input", str(bad)])

    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "malformed YAML" in err


def test_run_gate_cli_input_not_mapping_exits_usage(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """A YAML scalar at the top level MUST be rejected with exit 2."""
    scalar = _write(tmp_path, "just-a-string\n", name="scalar.yaml")

    with pytest.raises(SystemExit) as exc:
        run_gate_cli(["--input", str(scalar)])

    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "must be a YAML mapping" in err


def test_run_gate_cli_missing_required_keys_exits_usage(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """Missing one of build_status/test_results/lint_status MUST exit 2."""
    text = dedent(
        """
        build_status:
          status: pass
          details: {}
        # missing test_results + lint_status
        """
    ).strip()
    incomplete = _write(tmp_path, text, name="incomplete.yaml")

    with pytest.raises(SystemExit) as exc:
        run_gate_cli(["--input", str(incomplete)])

    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "invalid gate input" in err
    assert "missing required keys" in err


def test_run_gate_cli_no_input_flag_prints_help_exits_usage(
    capsys: pytest.CaptureFixture,
) -> None:
    """Calling with non-input flags but no --input MUST print help + exit 2."""
    with pytest.raises(SystemExit) as exc:
        run_gate_cli(["--profile", "strict"])

    assert exc.value.code == 2
    out = capsys.readouterr().out
    assert "validate-gate" in out


# ────────────────────────────────────────────────────────────────────────────
# 6. Profile / gate-type / round wiring — exercise the optional CLI flags
# ────────────────────────────────────────────────────────────────────────────


def test_run_gate_cli_strict_profile_threads_through(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """``--profile strict`` MUST select the STRICT profile."""
    input_path = _write(tmp_path, PASS_INPUT)

    with pytest.raises(SystemExit) as exc:
        run_gate_cli(["--input", str(input_path), "--profile", "strict"])

    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "profile: strict" in out


def test_run_gate_cli_passthrough_gate_type_threads_through(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """``--gate-type passthrough`` MUST always PASS regardless of input."""
    input_path = _write(tmp_path, FAIL_BLOCKER_INPUT)

    with pytest.raises(SystemExit) as exc:
        run_gate_cli(["--input", str(input_path), "--gate-type", "passthrough"])

    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "decision: PASS" in out
    assert "gate_type: passthrough" in out


def test_run_gate_cli_round_flag_accepted(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """``--round 3`` MUST be accepted and threaded into evaluate_gate."""
    input_path = _write(tmp_path, PASS_INPUT)

    with pytest.raises(SystemExit) as exc:
        run_gate_cli(["--input", str(input_path), "--round", "3"])

    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "decision: PASS" in out


def test_run_gate_cli_acceptance_readiness_prints_composite(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """``acceptance_readiness`` gate yields a composite score → ``composite:`` line."""
    text = dedent(
        """
        build_status: {status: pass}
        test_results: {status: pass}
        lint_status: {status: pass}
        acceptance_readiness_criteria:
          - criterion_id: AC-1
            text: "criterion 1"
            testability: 90
            completeness: 90
            measurability: 90
            independence: 90
            clarity: 90
        """
    ).strip()
    # acceptance_readiness_criteria isn't supported by _build_gate_input
    # (we wrap, don't modify evaluate_gate), so this exercises the
    # acceptance_readiness path returning composite=0 + decision FAIL on
    # missing criteria. Verifies the composite-score branch (line 767).
    input_path = _write(tmp_path, text)

    with pytest.raises(SystemExit) as exc:
        run_gate_cli(["--input", str(input_path), "--gate-type", "acceptance_readiness"])

    assert exc.value.code == 1  # FAIL — no criteria results provided
    out = capsys.readouterr().out
    assert "decision: FAIL" in out
    assert "composite: 0.00" in out


# ────────────────────────────────────────────────────────────────────────────
# 7. CLI wrapper — validate_gate_cmd through cli.py drives sys.argv
# ────────────────────────────────────────────────────────────────────────────


def test_validate_gate_cmd_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """``validate-gate --input <pass.yaml>`` exits 0 via the cli.py wrapper."""
    input_path = _write(tmp_path, PASS_INPUT)
    monkeypatch.setattr(sys, "argv", ["validate-gate", "--input", str(input_path)])
    from devolaflow.cli import validate_gate_cmd

    with pytest.raises(SystemExit) as exc:
        validate_gate_cmd()

    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "decision: PASS" in out


# ────────────────────────────────────────────────────────────────────────────
# 8. Helper unit tests — _check_result_from_dict / _finding_from_dict /
#    _build_gate_input / _format_findings (private API, exercised for coverage)
# ────────────────────────────────────────────────────────────────────────────


def test_check_result_from_dict_none_returns_none() -> None:
    assert _check_result_from_dict(None) is None


def test_check_result_from_dict_minimal() -> None:
    result = _check_result_from_dict({"status": "pass"})

    assert result is not None
    assert result.status == "pass"
    assert result.details == {}


def test_check_result_from_dict_with_details() -> None:
    result = _check_result_from_dict({"status": "fail", "details": {"x": 1}})

    assert result is not None
    assert result.status == "fail"
    assert result.details == {"x": 1}


def test_check_result_from_dict_invalid_status_raises() -> None:
    with pytest.raises(ValueError, match="status must be one of"):
        _check_result_from_dict({"status": "weird"})


def test_check_result_from_dict_non_mapping_raises() -> None:
    with pytest.raises(TypeError, match="must be a mapping"):
        _check_result_from_dict("not-a-dict")


def test_check_result_from_dict_non_mapping_details_raises() -> None:
    with pytest.raises(TypeError, match="details must be a mapping"):
        _check_result_from_dict({"status": "pass", "details": "nope"})


def test_finding_from_dict_minimal() -> None:
    finding = _finding_from_dict(
        {
            "finding_id": "F001",
            "severity": "minor",
            "category": "style",
            "location": "src/foo.py:1",
            "description": "x",
        }
    )

    assert finding.finding_id == "F001"
    assert finding.severity == "minor"
    assert finding.suggestion == ""
    assert finding.rule_id == ""


def test_finding_from_dict_invalid_severity_raises() -> None:
    with pytest.raises(ValueError, match="severity must be one of"):
        _finding_from_dict({"finding_id": "F001", "severity": "scary"})


def test_finding_from_dict_non_mapping_raises() -> None:
    with pytest.raises(TypeError, match="finding must be a mapping"):
        _finding_from_dict(["not", "a", "dict"])


def test_build_gate_input_findings_not_a_list_raises() -> None:
    raw = {
        "build_status": {"status": "pass"},
        "test_results": {"status": "pass"},
        "lint_status": {"status": "pass"},
        "review_findings": "not-a-list",
    }
    with pytest.raises(TypeError, match="review_findings must be a list"):
        _build_gate_input(raw)


def test_build_gate_input_required_status_null_raises() -> None:
    raw = {
        "build_status": None,
        "test_results": {"status": "pass"},
        "lint_status": {"status": "pass"},
    }
    with pytest.raises(ValueError, match="must not be null"):
        _build_gate_input(raw)


def test_build_gate_input_with_optional_user_facing_results() -> None:
    raw = {
        "build_status": {"status": "pass"},
        "test_results": {"status": "pass"},
        "lint_status": {"status": "pass"},
        "visual_test_results": {"status": "pass"},
        "interaction_test_results": {"status": "pass"},
        "accessibility_results": {"status": "pass"},
        "acceptance_verification_results": {"status": "pass"},
    }

    gate_input = _build_gate_input(raw)

    assert gate_input.visual_test_results is not None
    assert gate_input.interaction_test_results is not None
    assert gate_input.accessibility_results is not None
    assert gate_input.acceptance_verification_results is not None


def test_format_findings_empty_list() -> None:
    assert _format_findings([]) == "blocker=0 critical=0 major=0 minor=0 info=0"


def test_format_findings_mixed_severities() -> None:
    from devolaflow.gate.models import Finding

    severities = ["blocker", "blocker", "critical", "major", "minor", "minor", "info"]
    findings = [
        Finding(
            finding_id=f"F{i:03d}",
            severity=sev,  # type: ignore[arg-type]
            category="x",
            location="x",
            description="x",
        )
        for i, sev in enumerate(severities)
    ]
    assert _format_findings(findings) == "blocker=2 critical=1 major=1 minor=2 info=1"
