"""Schema validation tests for the NineS golden test set (v6.1.1, N1).

Purpose
-------
The ``data/golden_test_set/`` directory contains TOML fixtures consumed by
NineS V1 scoring evaluators (``scoring_accuracy``, ``scoring_reliability``,
``scorer_agreement``, ``eval_coverage``). Before v6.1.1 these evaluators all
scored 0.0 because the directory did not exist; see
``.local/research/v6.0.0_improvement_advice.md`` for the gap analysis.

These tests guard the fixture set against silent breakage — missing files,
invalid TOML, missing required keys, duplicate IDs, or values outside the
NineS-accepted enum sets.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
GOLDEN_DIR = REPO_ROOT / "data" / "golden_test_set"

VALID_DIMENSIONS = {
    "code_quality",
    "analysis",
    "evaluation",
    "collection",
    "decomposition",
    "system",
}

VALID_SCORERS = {"exact", "fuzzy", "rubric"}


def _golden_files() -> list[Path]:
    return sorted(GOLDEN_DIR.glob("*.toml"))


def _load(path: Path) -> dict:
    with path.open("rb") as fh:
        return tomllib.load(fh)


def test_golden_dir_exists() -> None:
    assert GOLDEN_DIR.is_dir(), (
        f"{GOLDEN_DIR.relative_to(REPO_ROOT)} must exist for NineS V1 "
        "scoring evaluators (scoring_accuracy, scoring_reliability, "
        "scorer_agreement, eval_coverage)."
    )


def test_golden_dir_has_min_10_tomls() -> None:
    files = _golden_files()
    assert len(files) >= 10, (
        f"Expected at least 10 TOML fixtures in {GOLDEN_DIR.relative_to(REPO_ROOT)}, "
        f"found {len(files)}."
    )


@pytest.mark.parametrize("path", _golden_files(), ids=lambda p: p.name)
def test_every_golden_has_task_table(path: Path) -> None:
    data = _load(path)
    assert "task" in data, f"{path.name}: missing top-level [task] table"
    assert isinstance(data["task"], dict), f"{path.name}: [task] must be a table"


@pytest.mark.parametrize("path", _golden_files(), ids=lambda p: p.name)
def test_every_golden_has_required_task_fields(path: Path) -> None:
    data = _load(path)
    task = data.get("task", {})
    for required in ("id", "name", "dimension"):
        assert required in task, f"{path.name}: [task] missing required field '{required}'"
        assert isinstance(task[required], str) and task[required], (
            f"{path.name}: [task].{required} must be a non-empty string"
        )


@pytest.mark.parametrize("path", _golden_files(), ids=lambda p: p.name)
def test_every_golden_has_expected_score(path: Path) -> None:
    data = _load(path)
    golden = data.get("task", {}).get("golden", {})
    assert "expected_score" in golden, f"{path.name}: [task.golden] missing 'expected_score'"
    score = golden["expected_score"]
    assert isinstance(score, (int, float)), (
        f"{path.name}: expected_score must be numeric, got {type(score).__name__}"
    )
    assert 0.0 <= float(score) <= 1.0, f"{path.name}: expected_score must be in [0, 1], got {score}"


@pytest.mark.parametrize("path", _golden_files(), ids=lambda p: p.name)
def test_every_golden_scorer_valid(path: Path) -> None:
    data = _load(path)
    scorer = data.get("task", {}).get("golden", {}).get("scorer")
    assert scorer in VALID_SCORERS, f"{path.name}: scorer '{scorer}' not in {sorted(VALID_SCORERS)}"


@pytest.mark.parametrize("path", _golden_files(), ids=lambda p: p.name)
def test_every_golden_dimension_valid(path: Path) -> None:
    data = _load(path)
    dimension = data["task"]["dimension"]
    assert dimension in VALID_DIMENSIONS, (
        f"{path.name}: dimension '{dimension}' not in {sorted(VALID_DIMENSIONS)}"
    )


def test_every_golden_id_unique() -> None:
    ids: dict[str, str] = {}
    for path in _golden_files():
        data = _load(path)
        task_id = data["task"]["id"]
        assert task_id not in ids, (
            f"Duplicate task.id '{task_id}' — first seen in {ids[task_id]}, repeated in {path.name}"
        )
        ids[task_id] = path.name
