"""PV-1 black-box coverage for console and module entrypoints."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.functional.runner import (
    MAINTAINED_MODULE_ENTRYPOINTS,
    _entrypoint_cases,
    load_console_script_inventory,
    load_matrix,
    outcome_satisfies_row,
    run_entrypoint,
)

pytestmark = [pytest.mark.functional, pytest.mark.fast]


def _entrypoint_rows():
    root = Path(__file__).parents[2]
    return tuple(row for row in load_matrix(repo_root=root) if row.entrypoint)


def test_console_script_inventory_matches_pyproject_and_matrix() -> None:
    root = Path(__file__).parents[2]
    rows = {row.entrypoint for row in _entrypoint_rows() if row.surface == "console_script"}
    inventory = set(load_console_script_inventory(root))

    assert len(inventory) == 15
    assert rows == inventory


def test_maintained_module_inventory_matches_matrix() -> None:
    rows = {row.entrypoint for row in _entrypoint_rows() if row.surface == "python_module"}

    assert rows == set(MAINTAINED_MODULE_ENTRYPOINTS)


@pytest.mark.parametrize("row", _entrypoint_rows(), ids=lambda row: row.id)
def test_entrypoints_execute_behavioral_subprocess_contract(row) -> None:
    root = Path(__file__).parents[2]
    outcome = run_entrypoint(row, root)

    assert outcome_satisfies_row(row, outcome), outcome.to_json()


def _malformed_rows():
    return tuple(
        row
        for row in _entrypoint_rows()
        if _entrypoint_cases()[row.entrypoint].malformed_args is not None
    )


@pytest.mark.parametrize("row", _malformed_rows(), ids=lambda row: row.id)
def test_entrypoints_report_declared_malformed_input(row) -> None:
    root = Path(__file__).parents[2]
    outcome = run_entrypoint(row, root, malformed=True)

    assert outcome.status.value == "PASS", outcome.to_json()
