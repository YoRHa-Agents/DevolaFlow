"""Focused semantic tests for the optional Pathfinder report artifact."""

from __future__ import annotations

from pathlib import Path

import pytest

from devolaflow.agent_workspace.lint import (
    PATHFINDER_REPORT_FILENAME,
    SemanticViolation,
    lint_change,
)
from devolaflow.agent_workspace.lint import main as lint_main
from devolaflow.skills.slash_commands import scaffold_change_folder

CHANGE_ID = "pathfinder-report-lint"
GAP_REPORT = '{"schema_version": 1, "axes": []}\n'

_VALID_BODY = """\
# Pathfinder Report

## Scan Scope
- Horizon: next harness-evaluation wave
- Sources: `schemas/`, `tests/fixtures/`, `.local/telemetry/`

## Findings
- gap_id: PF001
  severity: RISK
  horizon: next harness-evaluation wave
  evidence: [`evidence/pathfinder_gap.json`]
  impact: "The next wave may lack a settled comparison fixture."
  suggested_owner: harness-build
  acceptance_signal: "Active cycle baseline exists."

## Handoff
- artifact_path: `.local/.agent/active/pathfinder-report-lint/pathfinder_report.md`
- status: DONE_WITH_CONCERNS
- next_owner: harness-build
"""


def _report_text(
    *,
    schema_version: str = "1",
    scan_mode: str = "initial",
    scan_round: str = "1",
    gap_report: str = "evidence/pathfinder_gap.json",
    body: str = _VALID_BODY,
    frontmatter: bool = True,
) -> str:
    if not frontmatter:
        return body
    return (
        "---\n"
        f"schema_version: {schema_version}\n"
        f"change_id: {CHANGE_ID}\n"
        f"scan_mode: {scan_mode}\n"
        f"scan_round: {scan_round}\n"
        "horizon: next harness-evaluation wave\n"
        f"gap_report: {gap_report}\n"
        "previous_report: null\n"
        "---\n\n"
        f"{body}"
    )


def _scaffold(tmp_path: Path) -> Path:
    folder = scaffold_change_folder("Pathfinder Report Lint", tmp_path, change_id=CHANGE_ID)
    (folder / "evidence" / "pathfinder_gap.json").write_text(GAP_REPORT, encoding="utf-8")
    return folder


def _semantic_kinds(report) -> list[str]:
    return [
        violation.kind
        for violation in report.hard_failures
        if isinstance(violation, SemanticViolation)
    ]


def test_pathfinder_report_absent_and_valid_pass(tmp_path: Path) -> None:
    """The optional artifact is a no-op when absent and validates when present."""
    folder = _scaffold(tmp_path)
    absent = lint_change(CHANGE_ID, repo_root=tmp_path)
    assert not any(v.filename == PATHFINDER_REPORT_FILENAME for v in absent.violations)

    (folder / PATHFINDER_REPORT_FILENAME).write_text(_report_text(), encoding="utf-8")
    report = lint_change(CHANGE_ID, repo_root=tmp_path)
    assert report.exit_code == 0
    assert not any(v.filename == PATHFINDER_REPORT_FILENAME for v in report.violations)


@pytest.mark.parametrize(
    ("case", "expected_kind"),
    [
        ("missing-frontmatter-key", "PFR_FRONTMATTER"),
        ("no-frontmatter", "PFR_FRONTMATTER"),
        ("wrong-schema-version", "PFR_SCHEMA_VERSION"),
        ("invalid-scan-mode", "PFR_FRONTMATTER"),
        ("section-order", "PFR_SECTION_ORDER"),
        ("missing-gap-report", "PFR_GAP_REPORT"),
        ("absolute-evidence", "PFR_ABSOLUTE_PATH"),
        ("blocker-signal", "PFR_BLOCKER_SIGNAL"),
    ],
)
def test_pathfinder_report_finding_cases(tmp_path: Path, case: str, expected_kind: str) -> None:
    """Every report contract breach emits a stable PFR finding."""
    folder = _scaffold(tmp_path)
    if case == "missing-frontmatter-key":
        text = _report_text().replace("horizon: next harness-evaluation wave\n", "", 1)
    elif case == "no-frontmatter":
        text = _report_text(frontmatter=False)
    elif case == "wrong-schema-version":
        text = _report_text(schema_version="2")
    elif case == "invalid-scan-mode":
        text = _report_text(scan_mode="continuous")
    elif case == "section-order":
        text = _report_text().replace("## Scan Scope", "## Temporary", 1)
        text = text.replace("## Findings", "## Scan Scope", 1)
        text = text.replace("## Temporary", "## Findings", 1)
    elif case == "missing-gap-report":
        (folder / "evidence" / "pathfinder_gap.json").unlink()
        text = _report_text()
    elif case == "absolute-evidence":
        absolute_body = _VALID_BODY.replace("evidence/pathfinder_gap.json", "/tmp/gap.json")
        text = _report_text(body=absolute_body)
    else:
        blocker = _VALID_BODY.replace("severity: RISK\n", "severity: BLOCKER\n", 1).replace(
            'acceptance_signal: "Active cycle baseline exists."\n',
            "acceptance_signal:\n",
            1,
        )
        text = _report_text(body=blocker)

    (folder / PATHFINDER_REPORT_FILENAME).write_text(text, encoding="utf-8")
    report = lint_change(CHANGE_ID, repo_root=tmp_path)
    assert report.exit_code == 1
    assert expected_kind in _semantic_kinds(report)


def test_pathfinder_report_rejects_missing_scan_round(tmp_path: Path) -> None:
    """Invalid scan-round values are part of the frontmatter contract."""
    folder = _scaffold(tmp_path)
    text = _report_text(scan_round="0")
    (folder / PATHFINDER_REPORT_FILENAME).write_text(text, encoding="utf-8")
    report = lint_change(CHANGE_ID, repo_root=tmp_path)
    assert "PFR_FRONTMATTER" in _semantic_kinds(report)


def test_pathfinder_report_cli_surfaces_semantic_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The normal linter CLI exposes PFR findings and returns failure."""
    folder = _scaffold(tmp_path)
    (folder / PATHFINDER_REPORT_FILENAME).write_text(
        _report_text(gap_report="evidence/missing.json"), encoding="utf-8"
    )
    assert lint_main(["--repo-root", str(tmp_path), CHANGE_ID]) == 1
    assert "[PFR_GAP_REPORT]" in capsys.readouterr().err
