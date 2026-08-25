"""M5-a constraint-tier SSOT, annotation, and summary tests."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import get_args

import pytest
import yaml

from devolaflow.harness.tiers import (
    BEHAVIORAL_FIELD_TIERS,
    SOURCE_TIERS,
    ConstraintTier,
    annotate_behavioral_guidelines,
    annotate_rule_surfaces,
    should_fold_advisory,
    summarize_constraints,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_exact_ssot_mappings() -> None:
    assert set(get_args(ConstraintTier)) == {"invariant", "guard", "advisory"}
    assert BEHAVIORAL_FIELD_TIERS == {
        "think_first": "advisory",
        "simplicity_check": "advisory",
        "surgical_scope": "guard",
        "goal_loop": "advisory",
        "no_llm_for_deterministic": "advisory",
        "surface_conflicts": "advisory",
        "convention_first": "advisory",
        "line_level_criteria": "guard",
    }
    assert SOURCE_TIERS == {
        "gate_scalar_leaf": "invariant",
        "checklist_item": "guard",
        "machine_acceptance_v2": "guard",
        "manual_or_legacy_acceptance": "advisory",
        "rules_focus": "advisory",
        "quality_focus": "advisory",
        "reinforcement_rule": "guard",
    }


def test_behavioral_annotation_idempotence_and_absence() -> None:
    empty: dict = {}
    assert annotate_behavioral_guidelines(None) is None
    assert annotate_behavioral_guidelines(empty) == {}
    assert annotate_behavioral_guidelines(empty) is not empty

    source = {
        "think_first": True,
        "surgical_scope": "function",
        "future_guideline": {"enabled": True},
        "constraint_tiers": {"think_first": "invariant", "stale_field": "guard"},
    }
    before = deepcopy(source)
    annotated = annotate_behavioral_guidelines(source)

    assert source == before
    assert annotated is not source
    assert annotated == {
        "think_first": True,
        "surgical_scope": "function",
        "future_guideline": {"enabled": True},
        "constraint_tiers": {
            "think_first": "advisory",
            "surgical_scope": "guard",
            "future_guideline": "advisory",
        },
    }
    assert annotate_behavioral_guidelines(annotated) == annotated


def test_lean_and_full_rule_shape_annotation() -> None:
    payload = {
        "rules": {
            "strategy": "standard",
            "lang": "python",
            "focus": ["security"],
            "future_rule": "preserve me",
            "constraint_tiers": {"focus": "invariant"},
        },
        "reinforce": {"rules": [{"id": "F-1", "mandate": "MUST fix"}]},
        "context": {
            "applicable_rules": {
                "loading_strategy": "full",
                "quality_focus": ["maintainability"],
                "reinforcement": {
                    "rules": [{"id": "F-2", "mandate": "MUST test"}],
                },
            }
        },
    }
    before = deepcopy(payload)
    annotated = annotate_rule_surfaces(payload)

    assert payload == before
    assert annotated["rules"]["constraint_tiers"] == {
        "focus": "advisory",
        "future_rule": "advisory",
    }
    full = annotated["context"]["applicable_rules"]
    assert full["constraint_tiers"] == {"quality_focus": "advisory"}
    assert annotated["reinforce"]["rules"][0]["tier"] == "guard"
    assert full["reinforcement"]["rules"][0]["tier"] == "guard"
    assert annotate_rule_surfaces(annotated) == annotated
    assert annotate_rule_surfaces({}) == {}


def test_mixed_payload_count_ratio_and_reinforcement_deduplication() -> None:
    payload = annotate_rule_surfaces(
        {
            "gate": {"coverage": 80, "token_budget": {"max_tokens": 5000, "warn_at": 0.8}},
            "change_context": {"checklist_items": [{"id": "C-1"}, {"id": "C-2"}]},
            "acceptance_criteria_v2": [
                {
                    "id": "AC-1",
                    "verification_type": "test",
                    "verification_cmd": "pytest -q",
                },
                {"id": "AC-2", "verification_type": "metric", "metric": "coverage"},
                {"id": "AC-3", "verification_type": "manual"},
            ],
            "accept": ["legacy lean AC"],
            "acceptance_criteria": ["legacy alias AC"],
            "acceptance": {"criteria": ["legacy full AC 1", "legacy full AC 2"]},
            "behavioral_guidelines": annotate_behavioral_guidelines(
                {
                    "think_first": True,
                    "simplicity_check": False,
                    "surgical_scope": "function",
                    "line_level_criteria": ["LL-1", "LL-2"],
                    "future_guideline": True,
                }
            ),
            "rules": {"focus": ["security", "maintainability"]},
            "reinforce": {
                "rules": [
                    {"id": "F-1", "mandate": "MUST fix"},
                    {"id": "F-2", "mandate": "MUST test"},
                ]
            },
            "context": {
                "applicable_rules": {
                    "quality_focus": ["compatibility"],
                    "reinforcement": {
                        "rules": [{"id": "F-1", "mandate": "MUST fix"}],
                    },
                }
            },
        }
    )

    count, breakdown, ratio = summarize_constraints(payload)

    assert count == 22
    assert breakdown == {"invariant": 3, "guard": 8, "advisory": 11}
    assert ratio == pytest.approx(11 / 22)
    assert summarize_constraints({}) == (
        0,
        {"invariant": 0, "guard": 0, "advisory": 0},
        0.0,
    )

    mirrored_payload = {
        "acceptance_criteria_v2": [
            {
                "id": "AC-MACHINE",
                "description": "Machine mirror",
                "verification_type": "test",
                "verification_cmd": "pytest -q",
            },
            {
                "id": "AC-MANUAL",
                "description": "Manual mirror",
                "verification_type": "manual",
            },
            {
                "id": "AC-NONSTRING-DESCRIPTION",
                "description": 17,
                "verification_type": "test",
                "verification_cmd": "pytest -q",
            },
            "malformed structured criterion",
        ],
        "accept": [" Machine mirror ", "distinct lean criterion", 17, ""],
        "acceptance_criteria": ["Manual mirror", "machine mirror", None],
        "acceptance": {"criteria": ["nested legacy criterion"]},
    }
    mirrored_summary = summarize_constraints(mirrored_payload)
    assert mirrored_summary == (
        10,
        {"invariant": 0, "guard": 2, "advisory": 8},
        pytest.approx(2 / 10),
    )
    assert summarize_constraints(deepcopy(mirrored_payload)) == mirrored_summary


def test_invalid_unknown_and_fold_trigger_semantics() -> None:
    annotated = annotate_behavioral_guidelines({"tier": "standard", "unknown_future_rule": True})
    assert annotated == {
        "tier": "standard",
        "unknown_future_rule": True,
        "constraint_tiers": {"tier": "advisory", "unknown_future_rule": "advisory"},
    }
    unknown_rules = annotate_rule_surfaces({"rules": {"future_rule": True}})
    assert unknown_rules["rules"]["future_rule"] is True
    assert unknown_rules["rules"]["constraint_tiers"] == {"future_rule": "advisory"}
    assert summarize_constraints(unknown_rules) == (
        1,
        {"invariant": 0, "guard": 0, "advisory": 1},
        0.0,
    )

    with pytest.raises(ValueError, match="invalid explicit tier"):
        annotate_behavioral_guidelines(
            {"think_first": True, "constraint_tiers": {"think_first": "optional"}}
        )
    with pytest.raises(ValueError, match="invalid explicit tier"):
        annotate_rule_surfaces(
            {"reinforce": {"rules": [{"id": "F-1", "mandate": "fix", "tier": "high"}]}}
        )
    with pytest.raises(ValueError, match="invalid explicit tier"):
        summarize_constraints(
            {
                "behavioral_guidelines": {
                    "think_first": True,
                    "constraint_tiers": {"think_first": "invalid"},
                }
            }
        )

    assert should_fold_advisory("quality") is True
    assert should_fold_advisory("frontier") is True
    for model_hint in ("balanced", "budget", "inherit", "QUALITY", None, ""):
        assert should_fold_advisory(model_hint) is False


def test_advisory_fold_tiers_are_config_driven_with_exact_match(tmp_path: Path) -> None:
    """v17.0.0 R3 (D-R3-3 / G-TOK-3 minimal): ``meta.advisory_fold.model_tiers``
    replaces the fold tier set when declared; exact-match stays
    case-sensitive; a malformed value falls back to the default set with a
    WARNING (S-5). Config-ABSENT behaviour (the shipped default — the
    canonical YAML declares no ``advisory_fold``) is pinned byte-identical
    by the assertions in the test above and the fold matrix in
    ``tests/test_behavioral_guidelines.py``."""
    configured = tmp_path / "profiles-advisory-fold.yaml"
    configured.write_text(
        yaml.safe_dump({"meta": {"advisory_fold": {"model_tiers": ["balanced"]}}}),
        encoding="utf-8",
    )
    assert should_fold_advisory("balanced", configured) is True
    assert should_fold_advisory("BALANCED", configured) is False
    assert should_fold_advisory("quality", configured) is False
    assert should_fold_advisory("frontier", configured) is False

    absent = tmp_path / "profiles-no-advisory-fold.yaml"
    absent.write_text(yaml.safe_dump({"meta": {}}), encoding="utf-8")
    assert should_fold_advisory("quality", absent) is True
    assert should_fold_advisory("frontier", absent) is True
    assert should_fold_advisory("balanced", absent) is False

    malformed = tmp_path / "profiles-malformed-advisory-fold.yaml"
    malformed.write_text(
        yaml.safe_dump({"meta": {"advisory_fold": {"model_tiers": "quality"}}}),
        encoding="utf-8",
    )
    assert should_fold_advisory("quality", malformed) is True
    assert should_fold_advisory("balanced", malformed) is False


def test_schema_nests_and_layout_remain_version_6_length_17() -> None:
    lean = yaml.safe_load((REPO_ROOT / "schemas" / "lean-dispatch.yaml").read_text())
    full = yaml.safe_load((REPO_ROOT / "schemas" / "task-dispatch.schema.yaml").read_text())

    layout = lean["layout_invariant"]
    assert layout["version"] == 6
    assert len(layout["canonical_order"]) == 17
    assert layout["canonical_order"][13] == "behavioral_guidelines"
    assert lean["lean_format_spec"]["behavioral_guidelines"]["fields"]["constraint_tiers"][
        "optional"
    ]
    assert lean["lean_format_spec"]["rules"]["fields"]["constraint_tiers"]["optional"]
    assert "reinforce" not in lean["lean_format_spec"]["rules"]
    assert lean["lean_format_spec"]["reinforce"]["fields"]["rules"]["per_entry"]["tier"]["optional"]

    applicable = full["fields"]["context"]["children"]["applicable_rules"]["children"]
    assert applicable["constraint_tiers"]["optional"]
    assert applicable["reinforcement"]["children"]["rules"]["item_fields"]["tier"]["optional"]
