"""Deterministic shared harness fixture contract tests."""

from __future__ import annotations

import re
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
import yaml

from devolaflow.compressor import assert_dispatch_layout
from devolaflow.harness.fixtures import (
    MAX_PROBE_FIXTURES,
    HarnessFixtureError,
    compute_probe_set_hash,
    load_harness_fixture,
    load_harness_fixtures,
)
from devolaflow.harness.telemetry import build_dispatch_record
from devolaflow.lifecycle.validate_dispatch import validate_dispatch

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "harness"
REPORT_KEYS = ["hdr", "state", "artifacts", "ac_results", "diff_stats"]
MANIFEST = {
    "acceptance_product_verification": {
        "provenance": [
            "legacy-evobench:acceptance_verification_feature",
            "legacy-evobench:product_verification_pipeline",
            "legacy-evobench:visual_regression_webapp",
            "legacy-evobench:interaction_accessibility_test",
            "legacy-evobench:verification_ladder_disabled",
        ],
        "feature_tags": [
            "acceptance_v2",
            "visual",
            "interaction",
            "accessibility",
            "default_safe_fallback",
        ],
    },
    "adversarial_envelope": {
        "provenance": ["legacy-evobench:adversarial_data_instruction"],
        "feature_tags": ["data_envelope", "prompt_injection", "security"],
    },
    "compression_layered": {
        "provenance": [
            "legacy-evobench:compression_retention_easy",
            "legacy-evobench:compression_retention_medium",
            "legacy-evobench:compression_retention_hard",
            "legacy-evobench:directed_compaction_focused",
            "legacy-evobench:layered_recency_decay",
            "legacy-evobench:abstractive_llm",
        ],
        "feature_tags": [
            "verbatim_retention",
            "compact_directive",
            "recency_decay",
            "abstractive_fallback",
        ],
    },
    "convergence_feedback": {
        "provenance": ["legacy-evobench:convergence_noise_filter"],
        "feature_tags": ["reinforcement", "bounded_retry", "noise_tolerance"],
    },
    "hierarchy_complex_cascade": {
        "provenance": [
            "legacy-evobench:cascade_l0_l1_l2_l3_standard",
            "legacy-evobench:cascade_l0_l1_l2_l3_complex",
        ],
        "feature_tags": [
            "cascade_required",
            "cascade_min_layers",
            "fan_out",
            "complex_dispatch",
        ],
    },
    "hierarchy_trivial_collapse": {
        "provenance": [
            "legacy-evobench:collapse_l0_l3_simple",
            "legacy-evobench:collapse_l0_l3_trivial",
        ],
        "feature_tags": ["inline_dispatch", "trivial_waiver", "absence_canonical"],
    },
    "long_context_retrieval": {
        "provenance": ["legacy-evobench:long_context_repo_qa"],
        "feature_tags": ["retrieval_priority", "long_context"],
    },
    "model_tier_advisory_fold": {
        "provenance": [
            "legacy-evobench:complexity_tier_routing",
            "legacy-evobench:model_routing_feature",
            "legacy-evobench:simple_impl_budget",
        ],
        "feature_tags": [
            "model_hint",
            "complexity_routing",
            "constraint_tiers",
            "advisory_fold",
        ],
    },
    "multi_repo_migration": {
        "provenance": ["legacy-evobench:multi_repo_dispatch"],
        "feature_tags": ["repos", "primary_dependent_coordination", "cached_prefix"],
    },
    "workspace_handoff_memory": {
        "provenance": [
            "legacy-evobench:agent_workspace_active",
            "legacy-evobench:handoff_envelope_density",
            "legacy-evobench:reflective_reflex_capture",
        ],
        "feature_tags": [
            "change_context",
            "owned_files",
            "append_only_handoff",
            "operational_memory",
        ],
    },
}


def _reverse_mapping_order(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _reverse_mapping_order(child) for key, child in reversed(tuple(value.items()))}
    if isinstance(value, list):
        return [_reverse_mapping_order(child) for child in value]
    return value


def _write_fixture(path: Path, fixture: dict[str, Any]) -> None:
    path.write_text(yaml.safe_dump(fixture, sort_keys=False), encoding="utf-8")


def _path_values(dispatch: dict[str, Any]) -> list[str]:
    values = list(dispatch["files"])
    values.extend(item["ref"] for item in dispatch.get("pred", []))
    values.extend(item["root_path"] for item in dispatch.get("repos", []))
    reinforcement = dispatch.get("reinforce")
    if isinstance(reinforcement, dict):
        values.extend(rule["file"] for rule in reinforcement.get("rules", []) if "file" in rule)
    change_context = dispatch.get("change_context")
    if isinstance(change_context, dict):
        values.extend(
            change_context[field]
            for field in ("active_folder", "owned_files_ref", "acceptance_ref")
        )
    return values


def _assert_error_path(call, path: Path, phrase: str) -> None:
    with pytest.raises(
        HarnessFixtureError,
        match=rf"{re.escape(str(path))}:.*{re.escape(phrase)}",
    ):
        call()


def test_dispatch_layout_acceptance_paths_and_report_contract() -> None:
    runs = [load_harness_fixtures(FIXTURE_DIR) for _ in range(3)]
    fixtures = runs[0]
    ids = tuple(fixture["id"] for fixture in fixtures)
    mirror_ids: set[str] = set()
    mirror_commands: list[str] = []

    assert MAX_PROBE_FIXTURES == 10
    assert len(fixtures) == MAX_PROBE_FIXTURES
    assert ids == tuple(sorted(MANIFEST))
    assert tuple(path.stem for path in sorted(FIXTURE_DIR.glob("*.yaml"))) == ids
    for fixture in fixtures:
        expected = MANIFEST[fixture["id"]]
        assert fixture["provenance"] == expected["provenance"]
        assert fixture["feature_tags"] == expected["feature_tags"]
        assert load_harness_fixture(FIXTURE_DIR / f"{fixture['id']}.yaml") == fixture

    hashes = [compute_probe_set_hash(run) for run in runs]
    reordered = tuple(_reverse_mapping_order(fixture) for fixture in reversed(fixtures))
    assert hashes[0] == hashes[1] == hashes[2] == compute_probe_set_hash(reordered)
    assert re.fullmatch(r"[0-9a-f]{64}", hashes[0])

    all_features = {tag for fixture in fixtures for tag in fixture["feature_tags"]}
    assert {
        "cascade_required",
        "inline_dispatch",
        "compact_directive",
        "long_context",
        "data_envelope",
        "change_context",
        "repos",
        "reinforcement",
        "acceptance_v2",
        "advisory_fold",
    } <= all_features

    for fixture in fixtures:
        dispatch = fixture["dispatch"]
        expected = fixture["expected"]
        assert_dispatch_layout(dispatch)
        assert validate_dispatch(dispatch).passed
        assert expected["report_required_keys"] == REPORT_KEYS
        assert expected["report_forbidden_keys"] == ["quality_score"]
        assert type(expected["fold_sensitive"]) is bool
        assert expected["required_literals"]
        assert all(
            not Path(value).is_absolute() and not value.startswith("~")
            for value in _path_values(dispatch)
        )

        criteria = dispatch["acceptance_criteria_v2"]
        machine_ids = {
            criterion["id"]
            for criterion in criteria
            if criterion["verification_type"] in {"test", "metric"}
        }
        assert machine_ids == set(expected["guard_ids"])
        assert all(criterion["description"].strip() for criterion in criteria)
        assert all(
            criterion["verification_type"] == "manual" or criterion["verification_cmd"].strip()
            for criterion in criteria
        )
        lean_acceptance = dispatch["accept"]
        assert len(lean_acceptance) == 2
        for legacy in lean_acceptance:
            mirrors = [
                criterion
                for criterion in criteria
                if criterion["verification_type"] in {"test", "metric"}
                and criterion["description"].strip() == legacy.strip()
            ]
            assert len(mirrors) == 1
            mirror = mirrors[0]
            assert mirror["id"] in expected["guard_ids"]
            assert mirror["id"] not in mirror_ids
            mirror_ids.add(mirror["id"])
            mirror_commands.append(mirror["verification_cmd"])
        serialized = yaml.safe_dump(fixture, sort_keys=False)
        assert all(
            legacy not in serialized
            for legacy in ("expected_sections", "unwanted_sections", "quality_thresholds")
        )

    assert len(mirror_ids) == len(mirror_commands) == len(fixtures) * 2 == 20
    assert len(set(mirror_commands)) == 20
    records = [
        build_dispatch_record(
            fixture["dispatch"],
            change_id="canonical-fixture-contract",
            timestamp=f"2026-08-25T00:{index:02d}:00+00:00",
        )
        for index, fixture in enumerate(fixtures)
    ]
    aggregate_breakdown = {
        tier: sum(record["tier_breakdown"][tier] for record in records)
        for tier in ("invariant", "guard", "advisory")
    }
    aggregate_count = sum(record["constraint_count"] for record in records)
    assert aggregate_breakdown == {"invariant": 35, "guard": 33, "advisory": 27}
    assert aggregate_count == sum(aggregate_breakdown.values()) == 95
    assert (aggregate_breakdown["invariant"] + aggregate_breakdown["guard"]) / aggregate_count == (
        pytest.approx(68 / 95)
    )

    trivial_gate = fixtures[5]["dispatch"]["gate"]
    assert "cascade_required" not in trivial_gate
    assert "cascade_min_layers" not in trivial_gate
    repos = fixtures[8]["dispatch"]["repos"]
    assert sum(repo["primary"] is True for repo in repos) == 1


def test_explicit_loader_and_hash_failures_include_source(tmp_path: Path) -> None:
    valid = load_harness_fixture(FIXTURE_DIR / "hierarchy_trivial_collapse.yaml")

    missing = tmp_path / "missing.yaml"
    _assert_error_path(lambda: load_harness_fixture(missing), missing, "cannot read fixture")

    malformed = tmp_path / "malformed.yaml"
    malformed.write_text("dispatch: [\n", encoding="utf-8")
    _assert_error_path(lambda: load_harness_fixture(malformed), malformed, "invalid fixture YAML")

    empty = tmp_path / "empty.yaml"
    empty.write_text("{}\n", encoding="utf-8")
    _assert_error_path(lambda: load_harness_fixture(empty), empty, "non-empty mapping")

    mismatched = tmp_path / "mismatched.yaml"
    _write_fixture(mismatched, valid)
    _assert_error_path(
        lambda: load_harness_fixture(mismatched),
        mismatched,
        "must match filename stem",
    )

    invalid_layout = deepcopy(valid)
    invalid_layout["id"] = "invalid_layout"
    dispatch = invalid_layout["dispatch"]
    invalid_layout["dispatch"] = {
        "task": dispatch["task"],
        "hdr": dispatch["hdr"],
        **{key: value for key, value in dispatch.items() if key not in {"hdr", "task"}},
    }
    invalid_layout_path = tmp_path / "invalid_layout.yaml"
    _write_fixture(invalid_layout_path, invalid_layout)
    _assert_error_path(
        lambda: load_harness_fixture(invalid_layout_path),
        invalid_layout_path,
        "dispatch layout is invalid",
    )

    empty_dir = tmp_path / "empty-dir"
    empty_dir.mkdir()
    _assert_error_path(
        lambda: load_harness_fixtures(empty_dir),
        empty_dir,
        "contains no YAML fixtures",
    )

    duplicate_dir = tmp_path / "duplicate-dir"
    duplicate_dir.mkdir()
    duplicate = deepcopy(valid)
    duplicate["id"] = "duplicate"
    _write_fixture(duplicate_dir / "first.yaml", duplicate)
    _write_fixture(duplicate_dir / "second.yaml", duplicate)
    _assert_error_path(
        lambda: load_harness_fixtures(duplicate_dir),
        duplicate_dir / "second.yaml",
        "duplicate fixture id",
    )

    oversized_dir = tmp_path / "oversized-dir"
    oversized_dir.mkdir()
    for index in range(MAX_PROBE_FIXTURES + 1):
        (oversized_dir / f"{index:02}.yaml").write_text("{}\n", encoding="utf-8")
    _assert_error_path(
        lambda: load_harness_fixtures(oversized_dir),
        oversized_dir,
        "exceeds MAX_PROBE_FIXTURES",
    )

    with pytest.raises(HarnessFixtureError, match="<fixtures>: fixture set must not be empty"):
        compute_probe_set_hash([])
    with pytest.raises(HarnessFixtureError, match="<fixtures>: duplicate fixture id"):
        compute_probe_set_hash([valid, valid])
    with pytest.raises(
        HarnessFixtureError,
        match="<fixtures>: fixture at index 0 must be a mapping",
    ):
        compute_probe_set_hash(["not-a-mapping"])
