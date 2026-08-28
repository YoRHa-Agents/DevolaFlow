"""Loop v3 domain-adapter and runner-policy checks."""

from __future__ import annotations

import json
import socket
from pathlib import Path

import pytest

from tests.functional.runner import (
    ADAPTERS,
    FunctionalOutcome,
    MatrixRow,
    NetworkAccessDenied,
    OutcomeStatus,
    load_matrix,
    run_matrix,
    run_row,
)

pytestmark = [pytest.mark.functional, pytest.mark.slow]


def test_full_matrix_writes_deterministic_result_artifact() -> None:
    root = Path(__file__).parents[2]
    first = run_matrix(repo_root=root)
    artifact_path = root / ".local" / "telemetry" / "functional-test-results.json"
    first_bytes = artifact_path.read_bytes()
    second = run_matrix(repo_root=root)
    second_bytes = artifact_path.read_bytes()

    assert len(first) == len(load_matrix(repo_root=root).rows)
    allowed = {OutcomeStatus.PASS, OutcomeStatus.SKIP_OPTIONAL}
    assert all(outcome.status in allowed for outcome in first)
    assert all(outcome.status in allowed for outcome in second)
    assert json.loads(first_bytes)["status"] == "PASS"
    assert first_bytes == second_bytes


def test_runner_denies_network_for_in_process_adapters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = MatrixRow(
        id="test.network-policy",
        domain="functional_infrastructure",
        surface="network_policy",
        call="test_network_policy_adapter",
        fixture="tests/functional/runner.py",
        tier="fast",
        required=True,
        expected="network requests are denied",
        design_source=("tests/functional/runner.py#run_row",),
    )

    def adapter(current: MatrixRow, _root: Path) -> FunctionalOutcome:
        try:
            socket.create_connection(("127.0.0.1", 9))
        except NetworkAccessDenied:
            return FunctionalOutcome(
                row_id=current.id,
                status=OutcomeStatus.PASS,
                message="network denied",
            )
        return FunctionalOutcome(
            row_id=current.id,
            status=OutcomeStatus.FAIL,
            message="network was reachable",
        )

    monkeypatch.setitem(ADAPTERS, row.call, adapter)
    outcome = run_row(row, Path(__file__).parents[2])

    assert outcome.status is OutcomeStatus.PASS
    assert outcome.details["network_policy"]["child_process"].startswith("child processes")
