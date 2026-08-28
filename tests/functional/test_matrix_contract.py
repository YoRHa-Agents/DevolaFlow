"""Focused PV-0 tests for the functional matrix contract."""

from __future__ import annotations

import copy
import json
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from tests.functional.runner import (
    FunctionalOutcome,
    MatrixValidationError,
    OutcomeStatus,
    load_matrix,
    outcome_satisfies_row,
    run_row,
    serialize_outcomes,
    validate_matrix_payload,
)

pytestmark = [pytest.mark.functional, pytest.mark.fast]


def _valid_payload(fixture_name: str = "fixture.txt") -> dict:
    return {
        "schema_version": 1,
        "mode": "offline",
        "defaults": {
            "timeout_seconds": 30,
            "network": "forbidden",
            "unclassified_outcome": "fail",
            "required_skip": "fail",
        },
        "rows": [
            {
                "id": "test.valid",
                "domain": "functional_infrastructure",
                "surface": "matrix_loader",
                "call": "validate_matrix_contract",
                "fixture": fixture_name,
                "tier": "fast",
                "required": True,
                "expected": "fixture is available",
                "design_source": ["source.md#contract"],
            }
        ],
    }


def _matrix_rows():
    root = Path(__file__).parents[2]
    return load_matrix(repo_root=root).rows


@pytest.mark.parametrize("row", _matrix_rows(), ids=lambda row: row.id)
def test_matrix_rows_validate_and_execute_with_typed_outcomes(row) -> None:
    root = Path(__file__).parents[2]
    outcome = run_row(row, root)

    assert outcome.status in {
        OutcomeStatus.PASS,
        OutcomeStatus.SKIP_OPTIONAL,
    }
    assert outcome_satisfies_row(row, outcome)

    if row.expected_status is not OutcomeStatus.SKIP_OPTIONAL:
        return
    required_skip = replace(row, required=True)
    rejected = run_row(required_skip, root)
    assert rejected.status is OutcomeStatus.FAIL
    assert not outcome_satisfies_row(required_skip, rejected)


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("duplicate", "duplicate_id"),
        ("missing_adapter", "missing_adapter"),
        ("required_gap", "required_gap"),
    ],
)
def test_matrix_validation_rejects_duplicate_adapter_and_required_gap(
    tmp_path: Path, mutation: str, expected_code: str
) -> None:
    fixture = tmp_path / "fixture.txt"
    source = tmp_path / "source.md"
    fixture.write_text("fixture\n", encoding="utf-8")
    source.write_text("contract\n", encoding="utf-8")
    payload = _valid_payload()
    payload["rows"][0]["fixture"] = fixture.name
    payload["rows"][0]["design_source"] = [f"{source.name}#contract"]

    if mutation == "duplicate":
        payload["rows"].append(copy.deepcopy(payload["rows"][0]))
    elif mutation == "missing_adapter":
        payload["rows"][0]["call"] = "not_registered"
    else:
        payload["rows"][0]["expected_status"] = "INSUFFICIENT"

    diagnostics = validate_matrix_payload(payload, tmp_path)
    assert expected_code in {diagnostic.code for diagnostic in diagnostics}


def test_optional_skip_requires_and_preserves_explicit_reason(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture.txt"
    source = tmp_path / "source.md"
    fixture.write_text("fixture\n", encoding="utf-8")
    source.write_text("contract\n", encoding="utf-8")
    payload = _valid_payload(fixture.name)
    row = payload["rows"][0]
    row.update(
        {
            "required": False,
            "surface": "optional_prerequisite",
            "call": "optional_prerequisite_skip",
            "prerequisite": "optional local prerequisite is unavailable",
            "expected_status": "SKIP_OPTIONAL",
            "design_source": [f"{source.name}#contract"],
        }
    )
    document = load_matrix_from_payload_for_test(payload, tmp_path)
    outcome = run_row(document.rows[0], tmp_path)

    assert outcome.status is OutcomeStatus.SKIP_OPTIONAL
    assert outcome.prerequisite == row["prerequisite"]
    assert outcome.message == row["prerequisite"]


def test_result_serialization_uses_exact_status_values() -> None:
    outcome = FunctionalOutcome(
        row_id="test.serialization",
        status=OutcomeStatus.INSUFFICIENT,
        message="evidence is unavailable",
        details={"source": "fixture"},
        prerequisite=None,
    )

    serialized = outcome.to_dict()
    assert serialized["status"] == "INSUFFICIENT"
    assert json.loads(outcome.to_json()) == serialized
    assert json.loads(serialize_outcomes([outcome])) == [serialized]


def load_matrix_from_payload_for_test(payload: dict, root: Path):
    """Load a temporary payload through the same strict normalization path."""
    matrix_path = root / "matrix.yaml"
    matrix_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    try:
        return load_matrix(matrix_path, root)
    except MatrixValidationError as exc:
        pytest.fail(str(exc))
