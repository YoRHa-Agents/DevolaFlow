"""Current-cycle ghost audit for v19.0.0 review-loop contracts."""

from __future__ import annotations

import importlib
import inspect
import json
from pathlib import Path

from devolaflow._workspace_reporter.renderers import render_workspace_report
from devolaflow.harness import CONSOLIDATION_METRIC_NAMES, MEASUREMENT_KEYS
from scripts.check_module_coverage import main as check_module_coverage
from scripts.check_template_metadata_parity import check_template_metadata_parity

_DIRECT_FACADES = (
    "devolaflow._compressor_transforms",
    "devolaflow._plugin_installer",
    "devolaflow._workspace_lint",
    "devolaflow._workspace_reporter",
)
_CLEANED_FACADES = (
    "_compressor_transforms",
    "_workspace_lint",
    "_workspace_reporter",
)
_PUBLIC_FACADES = (
    "src/devolaflow/compressor/transforms.py",
    "src/devolaflow/agent_workspace/lint.py",
)


def test_v19_release_review_contracts_are_present(
    project_root: Path, tmp_path: Path, capsys
) -> None:
    """Parity, coverage, and settled evaluator contracts remain executable."""
    parity = check_template_metadata_parity(project_root)
    assert parity.passed, parity.issues
    # This checks the live parity surfaces; v20.1 adds one registered seed.
    assert (parity.registry_count, parity.workflow_count, parity.seed_count) == (28, 28, 28)

    makefile = (project_root / "Makefile").read_text(encoding="utf-8")
    assert "check-template-metadata-parity:" in makefile
    assert "python scripts/check_template_metadata_parity.py" in makefile
    release_preflight = next(
        line for line in makefile.splitlines() if line.startswith("release-preflight:")
    )
    assert "check-template-metadata-parity" in release_preflight

    evaluation = json.loads(
        (
            project_root / "docs/cycle-archive/v19.0.0/harness/v19.0.0_harness_evaluation.json"
        ).read_text(encoding="utf-8")
    )
    assert set(MEASUREMENT_KEYS) == set(CONSOLIDATION_METRIC_NAMES)
    historical_measurements = {
        "estimated_agents_md_tokens" if name == "agents_md_tokens" else name
        for name in evaluation["measurements"]
    }
    assert historical_measurements == set(MEASUREMENT_KEYS)
    assert all(
        evaluation["measurements"][
            "agents_md_tokens" if name == "estimated_agents_md_tokens" else name
        ]["status"]
        == "AVAILABLE"
        for name in MEASUREMENT_KEYS
    )
    assert evaluation["verdict"] == "READY"
    assert evaluation["composite"] == 9.17
    baseline = json.loads(
        (
            project_root / "docs/cycle-archive/v19.0.0/harness/v19.0.0_harness_baseline.json"
        ).read_text(encoding="utf-8")
    )
    settlement = baseline["settlement"]
    assert settlement["status"] == "SETTLED"
    assert settlement["source_evaluator"] == ".local/research/v19.0.0_harness_evaluation.json"
    assert settlement["source_ledger"] == ".local/telemetry/harness.jsonl"
    assert settlement["major_release_threshold"] == 9.0
    assert settlement["historical_comparison"] == "INSUFFICIENT"

    report = tmp_path / "coverage.json"
    report.write_text(
        json.dumps(
            {"files": {"src/example.py": {"summary": {"num_statements": 1, "percent_covered": 75}}}}
        ),
        encoding="utf-8",
    )
    assert check_module_coverage([str(report)]) == 0
    assert "meet 75.0% coverage" in capsys.readouterr().out


def test_v19_facade_import_and_compatibility_boundaries_are_retained(
    project_root: Path,
) -> None:
    """Clean facades have no dead markers while compatibility stays callable."""
    for module_name in _DIRECT_FACADES:
        module = importlib.import_module(module_name)
        assert module.__all__, f"{module_name} has no direct-import exports"

    for module_name in _CLEANED_FACADES:
        source = (
            project_root / "src" / "devolaflow" / Path(*module_name.split("/")) / "__init__.py"
        ).read_text(encoding="utf-8")
        assert "class _CompatModule" not in source
        assert "Forward legacy monkeypatches" not in source

    for relative_path in _PUBLIC_FACADES:
        source = (project_root / relative_path).read_text(encoding="utf-8")
        assert "if False:" not in source
        assert "PFR_BLOCKER_SIGNAL" not in source

    parameter = inspect.signature(render_workspace_report).parameters["workspace_root"]
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
    assert parameter.default is None
