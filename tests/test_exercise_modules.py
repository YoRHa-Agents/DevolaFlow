"""Exercise stub modules and CLI entrypoints for coverage (pyproject fail_under)."""

import io
import sys
from contextlib import redirect_stdout

import pytest


def test_stub_helpers():
    from devolaflow.build_skill import build_all
    from devolaflow.check_drift import check_drift
    from devolaflow.gate.scorer import run_gate_cli
    from devolaflow.pre_decision.detect import detect_and_print
    from devolaflow.template_engine.validator import validate_all_templates

    assert check_drift() is False
    assert validate_all_templates(False) is True
    assert validate_all_templates(True) is True

    buf = io.StringIO()
    with redirect_stdout(buf):
        detect_and_print()
    assert buf.getvalue().strip() == "local"

    buf2 = io.StringIO()
    with redirect_stdout(buf2):
        build_all([])
        run_gate_cli([])
    out = buf2.getvalue()
    assert "no-op" in out
    assert "pass" in out


def test_validate_template_cmd(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["validate-template", "--all"])
    from devolaflow.cli import validate_template_cmd

    with pytest.raises(SystemExit) as exc:
        validate_template_cmd()
    assert exc.value.code == 0


def test_validate_gate_cmd(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["validate-gate", "x"])
    from devolaflow.cli import validate_gate_cmd

    validate_gate_cmd()


def test_build_skill_cmd(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["build-skill"])
    from devolaflow.cli import build_skill_cmd

    build_skill_cmd()


def test_check_drift_cmd(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["check-drift"])
    from devolaflow.cli import check_drift_cmd

    with pytest.raises(SystemExit) as exc:
        check_drift_cmd()
    assert exc.value.code == 0


def test_detect_repo_mode_cmd(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["detect-repo-mode"])
    from devolaflow.cli import detect_repo_mode_cmd

    buf = io.StringIO()
    with redirect_stdout(buf):
        detect_repo_mode_cmd()
    assert buf.getvalue().strip() == "local"
