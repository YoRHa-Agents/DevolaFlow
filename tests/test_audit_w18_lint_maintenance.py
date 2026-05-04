"""Tests for the v10.5.0 PV-05 D-D-4 W-18 lint maintenance audit script.

Pins the public contract of ``scripts/audit_w18_lint_maintenance.py``
per `.local/research/v11.0.0_patches/D-D-4.md` §2:

1. :func:`extract_cycle_lints` parses every ``def
   test_v<M>_<m>_<p>_*(`` function signature + its line range.
2. :func:`count_stale_pins` counts path-literals whose target file
   no longer exists under the repo root.
3. :func:`compute_trajectory` aggregates cumulative LOC / lint
   counts per cycle version, sorted numerically.
4. :func:`render_markdown_report` carries Summary + Trajectory +
   Per-Lint sections.
5. :func:`run` exits 0 even on a fresh clone without the ghost-audit
   file.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import audit_w18_lint_maintenance as audit  # noqa: E402

# ── extract_cycle_lints ────────────────────────────────────────────────

_FIXTURE_TEXT = '''"""Ghost-audit module."""

def test_unrelated_helper() -> None:
    """This is not a cycle lint; doesn't match the regex."""
    assert True


def test_v9_1_0_new_symbols_have_coverage() -> None:
    """v9.1.0 W-18 lint."""
    paths = [
        "src/devolaflow/compressor/__init__.py",
        "tests/test_existing.py",
    ]
    for p in paths:
        assert p


def test_v10_0_0_new_symbols_have_coverage() -> None:
    """v10.0.0 W-18 lint — references a stale path too."""
    paths = [
        "src/devolaflow/compressor/__init__.py",
        "src/devolaflow/missing_module.py",
    ]
    for p in paths:
        assert p


def test_v10_3_0_new_symbols_have_coverage() -> None:
    """v10.3.0 latest W-18 lint."""
    paths = ["src/devolaflow/__init__.py"]
    for p in paths:
        assert p
'''


def test_extract_cycle_lints_returns_sorted_by_line() -> None:
    """Each ``def test_v{M}_{m}_{p}_*`` is captured with line + LOC."""
    lints = audit.extract_cycle_lints(_FIXTURE_TEXT)
    assert len(lints) == 3
    names = [l_["name"] for l_ in lints]
    assert names == [
        "test_v9_1_0_new_symbols_have_coverage",
        "test_v10_0_0_new_symbols_have_coverage",
        "test_v10_3_0_new_symbols_have_coverage",
    ]
    # LOC is (end - start + 1); must be positive.
    for lint in lints:
        assert lint["loc"] > 0
        assert lint["end_line"] >= lint["start_line"]


def test_extract_cycle_lints_captures_pinned_paths() -> None:
    """``pinned_paths`` extracts quoted .py literals inside each body."""
    lints = audit.extract_cycle_lints(_FIXTURE_TEXT)
    v9_1_0 = next(l_ for l_ in lints if l_["version"] == "9.1.0")
    assert "src/devolaflow/compressor/__init__.py" in v9_1_0["pinned_paths"]
    assert "tests/test_existing.py" in v9_1_0["pinned_paths"]


def test_extract_cycle_lints_empty_source() -> None:
    """Empty source → empty list (no error)."""
    assert audit.extract_cycle_lints("") == []


# ── count_stale_pins ───────────────────────────────────────────────────


def test_count_stale_pins_identifies_missing_files(tmp_path: Path) -> None:
    """A pin that doesn't resolve to a real file counts as stale."""
    # Create only one of the two pinned files.
    existing = tmp_path / "src" / "devolaflow" / "compressor"
    existing.mkdir(parents=True)
    (existing / "__init__.py").write_text("", encoding="utf-8")
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_existing.py").write_text("", encoding="utf-8")
    # `src/devolaflow/missing_module.py` + `src/devolaflow/__init__.py`
    # are NOT created — should be stale.
    lints = audit.extract_cycle_lints(_FIXTURE_TEXT)
    stale = audit.count_stale_pins(tmp_path, lints)
    # v10.0.0 block references `src/devolaflow/compressor/__init__.py` (exists)
    # + `src/devolaflow/missing_module.py` (MISSING) = 1 stale.
    # v10.3.0 block references `src/devolaflow/__init__.py` (MISSING) = 1 stale.
    # v9.1.0 block both paths exist = 0 stale.
    assert stale == 2


# ── compute_trajectory ─────────────────────────────────────────────────


def test_compute_trajectory_cumulative_counts() -> None:
    """Cumulative lint count + LOC ascend monotonically."""
    lints = audit.extract_cycle_lints(_FIXTURE_TEXT)
    trajectory = audit.compute_trajectory(lints)
    assert len(trajectory) == 3
    versions = [row["version"] for row in trajectory]
    assert versions == ["9.1.0", "10.0.0", "10.3.0"]
    # Cumulative values strictly non-decreasing.
    prev_lints = 0
    prev_loc = 0
    for row in trajectory:
        assert row["cumulative_lints"] >= prev_lints
        assert row["cumulative_loc"] >= prev_loc
        prev_lints = row["cumulative_lints"]
        prev_loc = row["cumulative_loc"]


# ── render_markdown_report ────────────────────────────────────────────


def test_render_markdown_report_has_required_sections() -> None:
    """Output carries Summary + Trajectory + Per-Lint headings."""
    lints = audit.extract_cycle_lints(_FIXTURE_TEXT)
    trajectory = audit.compute_trajectory(lints)
    md = audit.render_markdown_report(lints, trajectory, stale_count=2)
    assert "# v10.5.0 PV-05 D-D-4 W-18 Ghost-Audit Lint Maintenance Audit" in md
    assert "## Summary" in md
    assert "## Cycle-by-Cycle Trajectory" in md
    assert "## Per-Lint Detail" in md
    assert "## Projection" in md
    assert "**2**" in md  # stale count surfaces in summary


# ── run smoke ──────────────────────────────────────────────────────────


def test_run_emits_markdown_to_output(tmp_path: Path) -> None:
    """``run`` writes markdown even on a fresh tree."""
    out = tmp_path / "r.md"
    rc = audit.run(tmp_path, output=out)
    assert rc == 0
    assert "# v10.5.0 PV-05 D-D-4 W-18 Ghost-Audit Lint Maintenance Audit" in out.read_text(
        encoding="utf-8"
    )


def test_run_emits_json_when_requested(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """``--json`` produces parseable JSON with ``lints`` + ``trajectory``."""
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_no_ghost_features.py").write_text(_FIXTURE_TEXT, encoding="utf-8")
    rc = audit.run(tmp_path, json_out=True)
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert "lints" in payload
    assert "trajectory" in payload
    assert "stale_count" in payload
    assert len(payload["lints"]) == 3
