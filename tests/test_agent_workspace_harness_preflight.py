"""Focused tests for the OPTIONAL ``harness_preflight.md`` C-9 lint support.

Contract source: ``schemas/agent-workspace/harness-preflight.yaml`` (design
ref ``.local/tasks/add_harness_design/design.md`` §3.3). The artifact is
OPTIONAL — absence means the change is not harness-flagged and MUST produce
zero findings and zero budget violations.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from devolaflow.agent_workspace.lint import (
    CHECKLIST_ARTIFACT_BUDGETS,
    BudgetViolation,
    SemanticViolation,
    lint_change,
)
from devolaflow.agent_workspace.lint import main as lint_main
from devolaflow.skills.slash_commands import scaffold_change_folder

CHANGE_ID = "harness-preflight-lint"
ARTIFACT = "harness_preflight.md"
GAP_REPORT_JSON = '{"schema_version": 1, "auto_fill_rate": 0.62, "axes": []}\n'

_VALID_BODY = """\
# Harness Preflight

## 1. Target Observation Surface
- L0/L1/L2 dispatch telemetry completeness for the change-driven loop.

## 2. Capability Mapping
- telemetry: PARTIAL | aggregator: COVERED | evaluator: COVERED
- probe: GAP | proposal: COVERED | capacity: PARTIAL

## 3. Gap Inventory
- axes[probe].gaps[0].item: "probe fixtures x model table combinations uncovered"

## 4. Coverage Commitments
- probe: GAP -> COVERED (add frontier-tier fixture set)

## 5. Build Order
1. Observation points
2. Probe fixtures
3. Loop closure
"""


def _harness_text(
    *,
    gap_report: str = "evidence/harness_gap_before.json",
    axes_config: str = "null",
    schema_version: str = "1",
    body: str = _VALID_BODY,
    frontmatter: bool = True,
) -> str:
    if not frontmatter:
        return body
    return (
        "---\n"
        f"parent: {CHANGE_ID}\n"
        f"schema_version: {schema_version}\n"
        f"gap_report: {gap_report}\n"
        f"axes_config: {axes_config}\n"
        "---\n\n"
        f"{body}"
    )


def _scaffold(tmp_path: Path) -> Path:
    folder = scaffold_change_folder("Harness Preflight Lint", tmp_path, change_id=CHANGE_ID)
    (folder / "evidence" / "harness_gap_before.json").write_text(GAP_REPORT_JSON, encoding="utf-8")
    return folder


def _semantic_kinds(report) -> list[str]:
    return [
        violation.kind
        for violation in report.hard_failures
        if isinstance(violation, SemanticViolation)
    ]


@pytest.mark.parametrize("case", ["absent", "change-relative", "repo-relative-axes"])
def test_absent_and_valid_harness_preflight_pass(tmp_path: Path, case: str) -> None:
    """Absence is a clean no-op; a valid artifact resolves both path bases."""
    folder = _scaffold(tmp_path)

    if case == "change-relative":
        (folder / ARTIFACT).write_text(_harness_text(), encoding="utf-8")
    elif case == "repo-relative-axes":
        repo_gap = tmp_path / "telemetry" / "gap_before.json"
        repo_gap.parent.mkdir()
        repo_gap.write_text(GAP_REPORT_JSON, encoding="utf-8")
        (folder / "harness_axes.yaml").write_text("schema_version: 1\naxes: []\n", encoding="utf-8")
        (folder / ARTIFACT).write_text(
            _harness_text(
                gap_report="telemetry/gap_before.json",
                axes_config="harness_axes.yaml",
            ),
            encoding="utf-8",
        )

    report = lint_change(CHANGE_ID, repo_root=tmp_path)

    # The scaffold baseline may carry unrelated soft WARNs (e.g. the seeded
    # preflight.md); the harness artifact itself must contribute nothing.
    assert report.exit_code == 0
    assert not any(isinstance(v, SemanticViolation) for v in report.violations)
    assert not any(v.filename == ARTIFACT for v in report.violations)
    assert ARTIFACT in CHECKLIST_ARTIFACT_BUDGETS
    assert CHECKLIST_ARTIFACT_BUDGETS[ARTIFACT] == (800, 1600)


@pytest.mark.parametrize(
    ("case", "expected_kind"),
    [
        ("missing-frontmatter-key", "HPF_FRONTMATTER"),
        ("no-frontmatter", "HPF_FRONTMATTER"),
        ("wrong-schema-version", "HPF_SCHEMA_VERSION"),
        ("heading-order", "HPF_SECTION_ORDER"),
        ("missing-heading", "HPF_SECTION_ORDER"),
        ("missing-gap-report", "HPF_GAP_REPORT"),
        ("null-gap-report", "HPF_GAP_REPORT"),
        ("absolute-gap-report", "HPF_GAP_REPORT"),
        ("missing-axes-config", "HPF_AXES_CONFIG"),
    ],
)
def test_harness_preflight_finding_cases(tmp_path: Path, case: str, expected_kind: str) -> None:
    """Each contract breach emits its stable HPF_* finding and fails the lint."""
    folder = _scaffold(tmp_path)

    if case == "missing-frontmatter-key":
        text = _harness_text().replace("axes_config: null\n", "", 1)
    elif case == "no-frontmatter":
        text = _harness_text(frontmatter=False)
    elif case == "wrong-schema-version":
        text = _harness_text(schema_version="2")
    elif case == "heading-order":
        text = (
            _harness_text()
            .replace("## 2. Capability Mapping", "## SWAP", 1)
            .replace("## 3. Gap Inventory", "## 2. Capability Mapping", 1)
            .replace("## SWAP", "## 3. Gap Inventory", 1)
        )
    elif case == "missing-heading":
        text = _harness_text().replace("## 5. Build Order\n", "", 1)
    elif case == "missing-gap-report":
        (folder / "evidence" / "harness_gap_before.json").unlink()
        text = _harness_text()
    elif case == "null-gap-report":
        text = _harness_text(gap_report="null")
    elif case == "absolute-gap-report":
        # Built at runtime so no absolute path literal lands in this file.
        absolute_gap = tmp_path / "abs_gap.json"
        absolute_gap.write_text(GAP_REPORT_JSON, encoding="utf-8")
        text = _harness_text(gap_report=str(absolute_gap))
    else:  # missing-axes-config
        text = _harness_text(axes_config="harness_axes.yaml")

    (folder / ARTIFACT).write_text(text, encoding="utf-8")
    report = lint_change(CHANGE_ID, repo_root=tmp_path)

    assert report.exit_code == 1
    assert expected_kind in _semantic_kinds(report)
    assert all(
        violation.filename == ARTIFACT
        for violation in report.violations
        if isinstance(violation, SemanticViolation)
    )


@pytest.mark.parametrize(
    "case",
    ["cli-valid", "soft-budget-warn", "hard-budget-fail", "cli-semantic-fail"],
)
def test_harness_preflight_budget_tiers_and_cli(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    case: str,
) -> None:
    """C-9 soft/hard tiers apply to the artifact; the CLI surfaces HPF findings."""
    folder = _scaffold(tmp_path)

    if case == "soft-budget-warn":
        # > 800 * 4 chars but <= 1600 * 4 → WARN, exit 0.
        text = _harness_text(body=_VALID_BODY + "\n" + "x" * 3400)
    elif case == "hard-budget-fail":
        # > 1600 * 4 chars → FAIL, exit 1.
        text = _harness_text(body=_VALID_BODY + "\n" + "x" * 6600)
    elif case == "cli-semantic-fail":
        text = _harness_text(gap_report="evidence/missing.json")
    else:
        text = _harness_text()
    (folder / ARTIFACT).write_text(text, encoding="utf-8")

    rc = lint_main(["--repo-root", str(tmp_path), CHANGE_ID])
    stderr = capsys.readouterr().err
    report = lint_change(CHANGE_ID, repo_root=tmp_path)

    if case == "cli-valid":
        assert rc == 0
        assert not any(v.filename == ARTIFACT for v in report.violations)
        assert f"{CHANGE_ID}/{ARTIFACT}" in stderr
        assert " OK" in stderr
        return
    if case == "cli-semantic-fail":
        assert rc == 1
        assert "[HPF_GAP_REPORT]" in stderr
        return

    violation = next(v for v in report.violations if v.filename == ARTIFACT)
    assert isinstance(violation, BudgetViolation)
    assert (violation.soft_budget, violation.hard_budget) == (800, 1600)
    if case == "soft-budget-warn":
        assert rc == 0
        assert violation.severity == "WARN"
        assert "soft budget warning(s)" in stderr
    else:
        assert rc == 1
        assert violation.severity == "FAIL"
        assert "hard ceiling violation(s)" in stderr
