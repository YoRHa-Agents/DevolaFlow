"""Tests for deterministic local compressor health measurements."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

# The script lives outside ``src/`` so import via the file path.
_SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "snapshot_compressor_health.py"


@pytest.fixture(scope="module")
def snapshot_module():
    """Import the snapshot script as a module (it isn't a package member)."""
    spec = importlib.util.spec_from_file_location("snapshot_compressor_health", _SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["snapshot_compressor_health"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def repo_root() -> Path:
    """Return the repository root."""
    return Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Test 1: scan finds the 4 compressor module files
# ---------------------------------------------------------------------------


def test_scan_compressor_files_returns_four_modules(snapshot_module, repo_root) -> None:
    """``scan_compressor_files`` returns the 4 known compressor modules.

    Pins the v9.3.0 PV-04 4-way split: ``__init__.py`` + ``layout.py``
    + ``patterns.py`` + ``transforms.py``. If a future cycle adds a 5th
    module or removes one, this test fails so the snapshot script's
    schema stays in sync.
    """
    files = snapshot_module.scan_compressor_files(repo_root)
    names = sorted(f.name for f in files)
    assert names == [
        "__init__.py",
        "layout.py",
        "patterns.py",
        "transforms.py",
    ], f"compressor package shape changed: got {names!r}"


# ---------------------------------------------------------------------------
# Test 2: parse_radon_cc extracts function metrics from a synthetic input
# ---------------------------------------------------------------------------


def test_parse_radon_cc_extracts_function_metrics(snapshot_module) -> None:
    """``parse_radon_cc`` correctly groups per-file metrics + parses ranks.

    Uses a synthetic radon output (matching the documented format
    ``F <line>:<col> <name> - <rank>``) so the test does NOT depend
    on the actual radon binary or the actual compressor source — pure
    parser unit test.
    """
    raw = (
        "src/devolaflow/compressor/transforms.py\n"
        "    F 10:0 helper_a - A\n"
        "    F 50:4 helper_b - B\n"
        "    F 100:0 god_function - C\n"
        "    F 500:4 worse_function - D\n"
        "src/devolaflow/compressor/layout.py\n"
        "    F 5:0 simple - A\n"
    )
    parsed = snapshot_module.parse_radon_cc(raw)

    assert "src/devolaflow/compressor/transforms.py" in parsed
    assert "src/devolaflow/compressor/layout.py" in parsed
    transforms_metrics = parsed["src/devolaflow/compressor/transforms.py"]
    assert len(transforms_metrics) == 4
    ranks = [m.rank for m in transforms_metrics]
    assert ranks == ["A", "B", "C", "D"]

    layout_metrics = parsed["src/devolaflow/compressor/layout.py"]
    assert len(layout_metrics) == 1
    assert layout_metrics[0].name == "simple"
    assert layout_metrics[0].rank == "A"
    assert layout_metrics[0].line == 5


# ---------------------------------------------------------------------------
# Test 3: compute_health_summary aggregates per-file metrics correctly
# ---------------------------------------------------------------------------


def test_compute_health_summary_aggregates_correctly(snapshot_module, tmp_path) -> None:
    """``compute_health_summary`` produces correct per-package totals.

    Builds a tiny synthetic 2-file package + radon output and confirms
    the aggregate matches expectation (file count, function count,
    warning count, rank histogram).
    """
    # Synthetic 2-file package under tmp_path.
    pkg = tmp_path / "src" / "devolaflow" / "compressor"
    pkg.mkdir(parents=True)
    (pkg / "good.py").write_text("def a():\n    return 1\n")
    (pkg / "bad.py").write_text(
        "def a():\n    return 1\n\ndef god_func():\n    " + "    if True:\n        pass\n" * 12
    )
    files = sorted(pkg.glob("*.py"))

    # Synthetic radon output for these 2 files.
    raw = (
        f"{files[0].relative_to(tmp_path)}\n"
        "    F 1:0 a - A\n"
        f"{files[1].relative_to(tmp_path)}\n"
        "    F 1:0 a - A\n"
        "    F 4:0 god_func - C\n"
    )
    per_file = snapshot_module.parse_radon_cc(raw)
    health = snapshot_module.compute_health_summary(
        files,
        per_file,
        used_radon=True,
        repo_root=tmp_path,
    )

    assert health.file_count == 2
    assert health.warning_count == 1, "exactly 1 rank-C warning expected"
    assert health.rank_histogram["A"] == 2
    assert health.rank_histogram["C"] == 1
    assert health.used_radon is True
    assert health.total_function_count == 3


# ---------------------------------------------------------------------------
# Test 4: render_markdown_report emits all 6 required sections
# ---------------------------------------------------------------------------


def test_render_markdown_report_emits_required_sections(snapshot_module) -> None:
    """The stable report carries all six local-measurement sections."""
    # Build a minimal CompressorHealth via compute_health_summary on
    # an empty package (the renderer is the unit under test, not the
    # aggregator).
    health = snapshot_module.CompressorHealth(
        file_count=4,
        total_loc=3085,
        total_function_count=40,
        rank_histogram={"A": 35, "B": 4, "C": 1, "D": 0, "E": 0, "F": 0},
        warning_count=1,
        avg_complexity_estimate=4.5,
        per_file_loc={
            "src/devolaflow/compressor/__init__.py": 339,
            "src/devolaflow/compressor/layout.py": 327,
            "src/devolaflow/compressor/patterns.py": 221,
            "src/devolaflow/compressor/transforms.py": 2198,
        },
        per_file_function_count={
            "src/devolaflow/compressor/__init__.py": 0,
            "src/devolaflow/compressor/layout.py": 5,
            "src/devolaflow/compressor/patterns.py": 0,
            "src/devolaflow/compressor/transforms.py": 35,
        },
        per_file_warning_findings={
            "src/devolaflow/compressor/__init__.py": [],
            "src/devolaflow/compressor/layout.py": [],
            "src/devolaflow/compressor/patterns.py": [],
            "src/devolaflow/compressor/transforms.py": [
                snapshot_module.FunctionMetric(
                    file="src/devolaflow/compressor/transforms.py",
                    line=1234,
                    name="some_god_function",
                    rank="C",
                    sigil="F",
                )
            ],
        },
        used_radon=True,
    )
    report = snapshot_module.render_markdown_report(health)

    # All 6 sections present.
    for section in (
        "## §1 — Per-package summary",
        "## §2 — Top findings",
        "## §3 — Keypoints (per-file)",
        "## §4 — Deterministic health summary",
        "## §5 — Findings flagged for follow-up",
        "## §6 — References",
    ):
        assert section in report, f"missing required section: {section!r}"

    # Baseline comparison stanza present.
    assert "v9.3.0" in report
    assert "Legacy comparison vs v9.3.0 PV-04 pre-split baseline" in report
    # The 1 warning surfaces in §2 (a table row containing "some_god_function").
    assert "some_god_function" in report


# ---------------------------------------------------------------------------
# Test 5: run() smoke-test — end-to-end against the real compressor package
# ---------------------------------------------------------------------------


def test_run_writes_output_file(snapshot_module, repo_root, tmp_path) -> None:
    """End-to-end smoke test: ``run()`` writes the markdown report to a file.

    Exercises the full pipeline against the real compressor package
    (4 files). Asserts the output file exists, contains the §1
    package-summary header, and reports exactly 4 files.
    """
    output_path = tmp_path / "v10.6.X_compressor_health.md"
    rc = snapshot_module.run(repo_root, output=output_path)
    assert rc == 0
    assert output_path.is_file()
    text = output_path.read_text(encoding="utf-8")
    assert "# Compressor Health Snapshot" in text
    assert "## §1 — Per-package summary" in text
    # Per-package row reports 4 files.
    assert "| 4 |" in text, "§1 row must report 4 files in the compressor package"
