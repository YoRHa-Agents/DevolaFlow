"""Schema field parity tests (TD-4, v6.0.5).

Purpose
-------
Three schemas express overlapping concepts in different shapes:

* ``schemas/task-dispatch.schema.yaml``  — verbose dispatch envelope
* ``schemas/lean-dispatch.yaml``         — compact dispatch (abbreviated keys)
* ``schemas/gate-report.schema.yaml``    — gate output consumed downstream

Without a parity enforcer, a developer can add a field to one schema and forget
the equivalent in the other two. That silent drift is what these tests prevent.

How drift is caught
-------------------
Each test declares an explicit ``*_MAPPING`` (verbose → lean abbreviation) plus
an optional ``*_VERBOSE_ONLY`` set listing fields that intentionally exist on
the verbose side only (accepted compromises). The tests then:

1. Assert every mapping entry is present on **both** sides of the mapping —
   fails when one side is missing the equivalent key.
2. Assert there are no **orphan** fields in the verbose schema (any field not
   declared in the mapping or the ``VERBOSE_ONLY`` set fails loudly with a
   message that tells the developer exactly what to do).

To add a new field, update the mapping AND add the field to both schemas. If a
field legitimately cannot cross over (extreme compression, output-only, etc.),
add it to the relevant ``*_VERBOSE_ONLY`` / ``*_LEAN_ONLY`` set with a comment.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from devolaflow.compressor import DEFAULT_DISPATCH_LAYOUT, FROZEN_PREFIX_V7

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = REPO_ROOT / "schemas"

TASK_DISPATCH_PATH = SCHEMA_DIR / "task-dispatch.schema.yaml"
LEAN_DISPATCH_PATH = SCHEMA_DIR / "lean-dispatch.yaml"
GATE_REPORT_PATH = SCHEMA_DIR / "gate-report.schema.yaml"


# -----------------------------------------------------------------------------
# Fixtures — parse each YAML once per module.
# -----------------------------------------------------------------------------


@pytest.fixture(scope="module")
def verbose_doc() -> dict[str, Any]:
    return yaml.safe_load(TASK_DISPATCH_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def lean_doc() -> dict[str, Any]:
    return yaml.safe_load(LEAN_DISPATCH_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def gate_doc() -> dict[str, Any]:
    return yaml.safe_load(GATE_REPORT_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def lean_report_doc() -> dict[str, Any]:
    return yaml.safe_load((SCHEMA_DIR / "lean-report.yaml").read_text(encoding="utf-8"))


# -----------------------------------------------------------------------------
# Deep-search helpers — traverse a parsed YAML doc looking for a dict key.
# -----------------------------------------------------------------------------


def _field_in(doc: Any, key: str) -> bool:
    """Return True iff ``key`` appears as a dict key anywhere in ``doc``."""
    if isinstance(doc, dict):
        if key in doc:
            return True
        return any(_field_in(v, key) for v in doc.values())
    if isinstance(doc, list):
        return any(_field_in(item, key) for item in doc)
    return False


def field_in_verbose(doc: dict[str, Any], key: str) -> bool:
    """Check the verbose task-dispatch doc for a dict-key ``key`` anywhere."""
    return _field_in(doc, key)


def field_in_lean(doc: dict[str, Any], key: str) -> bool:
    """Check the lean-dispatch doc for a dict-key ``key`` anywhere."""
    return _field_in(doc, key)


# =============================================================================
# 1. Reinforcement field parity
# =============================================================================

# verbose applicable_rules.reinforcement → lean reinforce abbreviation
REINFORCEMENT_MAPPING: dict[str, str] = {
    "round": "round",
    "prior_score": "prior",
    "target_score": "target",
    "rules": "rules",
}

# Per-rule item fields (verbose rules[].X → lean rules[].Y).
REINFORCEMENT_RULE_ITEM_MAPPING: dict[str, str] = {
    "id": "id",
    "severity": "sev",
    "mandate": "mandate",
    "file": "file",
    "tier": "tier",
}

# Verbose-only fields: present in task-dispatch.schema.yaml with no lean
# equivalent. Extend only with an accompanying design discussion.
REINFORCEMENT_VERBOSE_ONLY: set[str] = {
    "severity_floor",
    "escalation_note",
}


def test_reinforcement_fields_parity(verbose_doc, lean_doc) -> None:
    """task-dispatch applicable_rules.reinforcement ↔ lean reinforce."""
    reinforcement_v = verbose_doc["fields"]["context"]["children"]["applicable_rules"]["children"][
        "reinforcement"
    ]
    verbose_keys = set(reinforcement_v["children"].keys())

    lean_example_reinforce = lean_doc["lean_example"]["reinforce"]
    lean_spec_reinforce = lean_doc["lean_format_spec"]["reinforce"]
    lean_keys = set(lean_example_reinforce.keys()) | set(lean_spec_reinforce["fields"].keys())

    for v_key, l_key in REINFORCEMENT_MAPPING.items():
        assert v_key in verbose_keys, (
            f"DRIFT: task-dispatch.schema.yaml "
            f"'applicable_rules.reinforcement' is missing '{v_key}' "
            f"(declared in REINFORCEMENT_MAPPING)."
        )
        assert l_key in lean_keys, (
            f"DRIFT: lean-dispatch.yaml is missing 'reinforce.{l_key}' "
            f"(expected as abbreviation for verbose "
            f"'applicable_rules.reinforcement.{v_key}'). "
            f"Add '{l_key}' to lean_example.reinforce AND "
            f"lean_format_spec.rules.reinforce.fields."
        )

    # Double-check via deep search that 'reinforce' block is reachable.
    assert field_in_lean(lean_doc, "reinforce"), (
        "DRIFT: lean-dispatch.yaml has no 'reinforce' block anywhere."
    )
    assert field_in_verbose(verbose_doc, "reinforcement"), (
        "DRIFT: task-dispatch.schema.yaml has no 'reinforcement' block anywhere."
    )

    # Orphan guard — any verbose field not in mapping or compromise set fails.
    expected_verbose = set(REINFORCEMENT_MAPPING.keys()) | REINFORCEMENT_VERBOSE_ONLY
    orphan_verbose = verbose_keys - expected_verbose
    assert not orphan_verbose, (
        f"DRIFT: task-dispatch.schema.yaml "
        f"'applicable_rules.reinforcement' has undeclared field(s) "
        f"{sorted(orphan_verbose)}. "
        f"Add each to REINFORCEMENT_MAPPING (with a lean equivalent) "
        f"or to REINFORCEMENT_VERBOSE_ONLY (accepted compromise)."
    )

    # Per-rule item-field parity.
    rule_item_v = reinforcement_v["children"]["rules"]["item_fields"]
    rule_v_keys = set(rule_item_v.keys())
    first_lean_rule = lean_example_reinforce["rules"][0]
    lean_rule_spec = lean_spec_reinforce["fields"]["rules"]["per_entry"]
    rule_l_keys = set(first_lean_rule.keys()) | set(lean_rule_spec.keys())

    for v_key, l_key in REINFORCEMENT_RULE_ITEM_MAPPING.items():
        assert v_key in rule_v_keys, (
            f"DRIFT: task-dispatch.schema.yaml "
            f"'reinforcement.rules.item_fields' is missing '{v_key}'."
        )
        assert l_key in rule_l_keys, (
            f"DRIFT: lean-dispatch.yaml "
            f"'lean_example.reinforce.rules[0]' is missing '{l_key}' "
            f"(expected as abbreviation for verbose rule field '{v_key}')."
        )

    # Orphan guard for per-rule items.
    orphan_rule_v = rule_v_keys - set(REINFORCEMENT_RULE_ITEM_MAPPING.keys())
    assert not orphan_rule_v, (
        f"DRIFT: task-dispatch.schema.yaml "
        f"'reinforcement.rules.item_fields' has undeclared field(s) "
        f"{sorted(orphan_rule_v)}. Add to REINFORCEMENT_RULE_ITEM_MAPPING."
    )


# =============================================================================
# 2. Verification field parity
# =============================================================================

# Verbose verification_config facet → lean verify_cfg abbreviation.
VERIFICATION_FACET_MAPPING: dict[str, str] = {
    "visual_testing": "visual",
    "acceptance_testing": "accept",
    "interaction_testing": "interact",
    "accessibility": "a11y",
}


def test_verification_fields_parity(verbose_doc, lean_doc) -> None:
    """task-dispatch verification_config ↔ lean verify_cfg cover the same facets."""
    vc_children = verbose_doc["fields"]["verification_config"]["children"]
    verbose_facets = set(vc_children.keys())

    verify_cfg = lean_doc["lean_format_spec"]["verify_cfg"]
    lean_facets = set(verify_cfg["fields"].keys())

    for v_facet, l_facet in VERIFICATION_FACET_MAPPING.items():
        assert v_facet in verbose_facets, (
            f"DRIFT: task-dispatch.schema.yaml 'verification_config' is missing "
            f"facet '{v_facet}' (declared in VERIFICATION_FACET_MAPPING)."
        )
        assert l_facet in lean_facets, (
            f"DRIFT: lean-dispatch.yaml 'verify_cfg.fields' is missing "
            f"'{l_facet}' (expected abbreviation for "
            f"verification_config.{v_facet})."
        )

    # Orphan guard on verbose facets.
    orphan_verbose = verbose_facets - set(VERIFICATION_FACET_MAPPING.keys())
    assert not orphan_verbose, (
        f"DRIFT: task-dispatch.schema.yaml 'verification_config' has new facet(s) "
        f"{sorted(orphan_verbose)}. Add to VERIFICATION_FACET_MAPPING AND to "
        f"lean verify_cfg.fields."
    )

    # Threshold is a shared concept — verbose nests it per-facet, lean has it once.
    assert "threshold" in lean_facets, (
        "DRIFT: lean-dispatch.yaml 'verify_cfg.fields' must include 'threshold'."
    )
    assert field_in_verbose(verbose_doc["fields"]["verification_config"], "threshold"), (
        "DRIFT: task-dispatch.schema.yaml 'verification_config' must include a "
        "'threshold' field under at least one facet's children."
    )


# =============================================================================
# 3. Gate-report verification coverage of dispatch verification_config
# =============================================================================

# Verbose verification_config facet → gate-report user_facing_verification field.
# Accessibility has no dedicated score field; it is covered via the
# user_facing_findings.dimension enum (asserted separately).
GATE_REPORT_FACET_MAPPING: dict[str, str] = {
    "visual_testing": "visual_fidelity_score",
    "interaction_testing": "interaction_quality_score",
    "acceptance_testing": "acceptance_verification_score",
}

# Fields under user_facing_verification that are output-only (not driven by
# dispatch config): extend when adding gate-only telemetry.
GATE_REPORT_OUTPUT_ONLY: set[str] = {
    "user_facing_findings",
}


def test_gate_report_verification_covers_dispatch_config(verbose_doc, gate_doc) -> None:
    """Every dispatch verification_config facet has a matching gate-report output."""
    vc_children = verbose_doc["fields"]["verification_config"]["children"]
    dispatch_facets = set(vc_children.keys())

    ufv_children = gate_doc["fields"]["user_facing_verification"]["children"]
    gate_keys = set(ufv_children.keys())

    for facet, gate_field in GATE_REPORT_FACET_MAPPING.items():
        assert facet in dispatch_facets, (
            f"DRIFT: task-dispatch.schema.yaml 'verification_config' is missing "
            f"facet '{facet}' (declared in GATE_REPORT_FACET_MAPPING)."
        )
        assert gate_field in gate_keys, (
            f"DRIFT: gate-report.schema.yaml 'user_facing_verification' is missing "
            f"'{gate_field}' (expected to mirror dispatch "
            f"verification_config.{facet})."
        )

    # Accessibility: covered via user_facing_findings.dimension enum, not a
    # dedicated score. Assert the enum description mentions 'accessibility'.
    findings_item = ufv_children["user_facing_findings"]["item_fields"]
    dimension_desc = findings_item["dimension"].get("description", "")
    assert "accessibility" in dimension_desc.lower(), (
        f"DRIFT: gate-report.schema.yaml "
        f"'user_facing_verification.user_facing_findings.item_fields."
        f"dimension' description must mention 'accessibility' "
        f"(mirrors dispatch verification_config.accessibility). "
        f"Current description: {dimension_desc!r}."
    )

    # Orphan guard: any gate field not in mapping or output-only set must be declared.
    expected_gate = set(GATE_REPORT_FACET_MAPPING.values()) | GATE_REPORT_OUTPUT_ONLY
    orphan_gate = gate_keys - expected_gate
    assert not orphan_gate, (
        f"DRIFT: gate-report.schema.yaml 'user_facing_verification' has new field(s) "
        f"{sorted(orphan_gate)}. Add to GATE_REPORT_FACET_MAPPING (if driven by "
        f"dispatch config) or GATE_REPORT_OUTPUT_ONLY (if gate-only telemetry)."
    )


# =============================================================================
# 4. Header field parity
# =============================================================================

# verbose header → lean hdr abbreviation
HEADER_MAPPING: dict[str, str] = {
    "dispatch_id": "id",
    "parent_id": "parent",
    "layer": "layer",
    "timeout_seconds": "timeout",
}

# Verbose-only header fields. These are intentional compression compromises:
#   * timestamp          — lean envelopes are short-lived; timing lives in
#                          surrounding dispatch metadata rather than `hdr`.
#   * model_hint         — adapter/host-IDE hint, added in v5.3.0; the lean
#                          format defers model selection to the runner.
#   * decomposition_mode — L3 execution hint; lean leaves this to the agent.
#   * compression_intensity — describes how the lean message itself was
#                          compressed; logically not repeatable inside it.
HEADER_VERBOSE_ONLY: set[str] = {
    "timestamp",
    "model_hint",
    "decomposition_mode",
    "compression_intensity",
}


def test_header_fields_parity(verbose_doc, lean_doc) -> None:
    """task-dispatch header ↔ lean hdr (documented abbreviation mapping)."""
    verbose_keys = set(verbose_doc["fields"]["header"]["children"].keys())
    lean_example_keys = set(lean_doc["lean_example"]["hdr"].keys())
    lean_spec_keys = set(lean_doc["lean_format_spec"]["hdr"]["fields"].keys())
    lean_keys = lean_example_keys | lean_spec_keys

    for v_key, l_key in HEADER_MAPPING.items():
        assert v_key in verbose_keys, (
            f"DRIFT: task-dispatch.schema.yaml 'header' is missing '{v_key}'."
        )
        assert l_key in lean_keys, (
            f"DRIFT: lean-dispatch.yaml 'hdr' is missing '{l_key}' "
            f"(expected as abbreviation for verbose 'header.{v_key}'). "
            f"Add it to BOTH lean_example.hdr and lean_format_spec.hdr.fields."
        )

    # Sanity: example and spec agree on their own abbreviation set.
    assert lean_example_keys == lean_spec_keys, (
        f"DRIFT: lean-dispatch.yaml 'lean_example.hdr' keys {sorted(lean_example_keys)} "
        f"disagree with 'lean_format_spec.hdr.fields' keys {sorted(lean_spec_keys)}. "
        f"Keep them in sync."
    )

    # Orphan guard.
    expected_verbose = set(HEADER_MAPPING.keys()) | HEADER_VERBOSE_ONLY
    orphan_verbose = verbose_keys - expected_verbose
    assert not orphan_verbose, (
        f"DRIFT: task-dispatch.schema.yaml 'header' has undeclared field(s) "
        f"{sorted(orphan_verbose)}. Add each to HEADER_MAPPING (with a lean "
        f"equivalent) or to HEADER_VERBOSE_ONLY (accepted compromise)."
    )


# =============================================================================
# 5. Acceptance field parity
# =============================================================================

# Top-level acceptance fields. `criteria` maps to lean `accept` (a top-level
# list in lean_example), `max_retry_rounds` maps to lean `gate.retries`.
# `quality_thresholds` is a nested object handled below.
ACCEPTANCE_TOP_MAPPING: dict[str, str] = {
    "criteria": "accept",
    "max_retry_rounds": "retries",
}

# Nested quality_thresholds fields → lean gate abbreviations.
ACCEPTANCE_THRESHOLD_MAPPING: dict[str, str] = {
    "coverage_pct": "coverage",
    "quality_score": "quality",
    "max_blocker_findings": "blockers",
}


def test_acceptance_fields_parity(verbose_doc, lean_doc) -> None:
    """task-dispatch acceptance.* ↔ lean accept (list) + gate (thresholds)."""
    verbose_accept = verbose_doc["fields"]["acceptance"]
    verbose_top_keys = set(verbose_accept["children"].keys())
    verbose_threshold_keys = set(
        verbose_accept["children"]["quality_thresholds"]["children"].keys()
    )

    lean_example = lean_doc["lean_example"]
    assert "accept" in lean_example, (
        "DRIFT: lean-dispatch.yaml 'lean_example' is missing the top-level 'accept' criteria list."
    )
    assert "gate" in lean_example, (
        "DRIFT: lean-dispatch.yaml 'lean_example' is missing the top-level 'gate' threshold block."
    )
    lean_gate_keys = set(lean_example["gate"].keys())

    for v_key, l_key in ACCEPTANCE_TOP_MAPPING.items():
        assert v_key in verbose_top_keys, (
            f"DRIFT: task-dispatch.schema.yaml 'acceptance' is missing '{v_key}'."
        )
        if l_key == "accept":
            assert "accept" in lean_example, (
                f"DRIFT: lean-dispatch.yaml 'lean_example' missing 'accept' "
                f"(expected for verbose 'acceptance.{v_key}')."
            )
        else:
            assert l_key in lean_gate_keys, (
                f"DRIFT: lean-dispatch.yaml 'lean_example.gate' is missing "
                f"'{l_key}' (expected as abbreviation for "
                f"'acceptance.{v_key}')."
            )

    for v_key, l_key in ACCEPTANCE_THRESHOLD_MAPPING.items():
        assert v_key in verbose_threshold_keys, (
            f"DRIFT: task-dispatch.schema.yaml "
            f"'acceptance.quality_thresholds' is missing '{v_key}'."
        )
        assert l_key in lean_gate_keys, (
            f"DRIFT: lean-dispatch.yaml 'lean_example.gate' is missing "
            f"'{l_key}' (expected as abbreviation for "
            f"'acceptance.quality_thresholds.{v_key}')."
        )

    # Orphan guard — verbose top-level.
    expected_top = set(ACCEPTANCE_TOP_MAPPING.keys()) | {"quality_thresholds"}
    orphan_top = verbose_top_keys - expected_top
    assert not orphan_top, (
        f"DRIFT: task-dispatch.schema.yaml 'acceptance' has undeclared field(s) "
        f"{sorted(orphan_top)}. Add to ACCEPTANCE_TOP_MAPPING (with a lean "
        f"equivalent) or to the expected_top set above."
    )

    # Orphan guard — nested thresholds.
    orphan_thresh = verbose_threshold_keys - set(ACCEPTANCE_THRESHOLD_MAPPING.keys())
    assert not orphan_thresh, (
        f"DRIFT: task-dispatch.schema.yaml "
        f"'acceptance.quality_thresholds' has undeclared field(s) "
        f"{sorted(orphan_thresh)}. Add to ACCEPTANCE_THRESHOLD_MAPPING."
    )

    # Orphan guard — lean gate should contain exactly the mapped keys.
    expected_lean_gate = set(ACCEPTANCE_THRESHOLD_MAPPING.values()) | {"retries"}
    orphan_gate = lean_gate_keys - expected_lean_gate
    assert not orphan_gate, (
        f"DRIFT: lean-dispatch.yaml 'lean_example.gate' has undeclared field(s) "
        f"{sorted(orphan_gate)}. Add the verbose equivalent to "
        f"ACCEPTANCE_THRESHOLD_MAPPING or ACCEPTANCE_TOP_MAPPING."
    )


# =============================================================================
# 6. Sanity — all three schemas parse without error.
# =============================================================================


def test_all_schemas_parse(verbose_doc, lean_doc, gate_doc) -> None:
    """All three schema YAMLs parse into non-empty dicts."""
    for name, doc in [
        ("task-dispatch.schema.yaml", verbose_doc),
        ("lean-dispatch.yaml", lean_doc),
        ("gate-report.schema.yaml", gate_doc),
    ]:
        assert isinstance(doc, dict), f"{name} did not parse to a dict (got {type(doc).__name__})."
        assert len(doc) > 0, f"{name} parsed but is empty."


# =============================================================================
# 7. Compression-rule owner / derived-view contract
# =============================================================================


def _normalized_common_compression_rules(
    schema: dict[str, Any], contract: dict[str, Any]
) -> dict[str, Any]:
    """Select only owner-declared common rules for cross-schema comparison."""
    rules = schema["compression_rules"]
    return {key: rules[key] for key in contract["common_keys"]}


def test_compression_rules_common_subtree_matches_owner(
    lean_doc: dict[str, Any], lean_report_doc: dict[str, Any]
) -> None:
    """The report view matches dispatch-owned common rules after normalization."""
    owner_contract = lean_doc["compression_rules_contract"]
    derived_contract = lean_report_doc["compression_rules_contract"]

    assert owner_contract["role"] == "owner"
    assert owner_contract["owner"] == "schemas/lean-dispatch.yaml#compression_rules"
    assert "schemas/lean-report.yaml#compression_rules" in owner_contract["derived_views"]
    assert derived_contract["role"] == "derived_view"
    assert derived_contract["owner"] == owner_contract["owner"]
    assert derived_contract["source_contract"] == (
        "schemas/lean-dispatch.yaml#compression_rules_contract"
    )
    assert derived_contract["common_keys"] == owner_contract["common_keys"]

    assert _normalized_common_compression_rules(lean_doc, owner_contract) == (
        _normalized_common_compression_rules(lean_report_doc, derived_contract)
    )

    # Preserve entries are intentionally message-specific, not part of the
    # normalized common subtree. The dispatch-only envelope policy is too.
    assert (
        lean_doc["compression_rules"]["preserve_list"]
        != (lean_report_doc["compression_rules"]["preserve_list"])
    )
    dispatch_preserve = set(lean_doc["compression_rules"]["preserve_list"])
    report_preserve = set(lean_report_doc["compression_rules"]["preserve_list"])
    assert dispatch_preserve - report_preserve == {"acceptance_criteria"}
    assert report_preserve - dispatch_preserve == {"finding_ids", "delta_descriptions"}
    assert owner_contract["preserve_list_differences"] == {
        "dispatch_only": ["acceptance_criteria"],
        "report_only": ["finding_ids", "delta_descriptions"],
    }
    assert "data_envelope_required" not in lean_report_doc["compression_rules"]
    assert set(owner_contract["message_specific_keys"]) == {
        "preserve_list",
        "data_envelope_required",
    }
    assert derived_contract["message_specific_keys"] == ["preserve_list"]


@pytest.mark.parametrize(
    "schema_name",
    ["lean-dispatch.yaml", "lean-report.yaml"],
)
def test_compression_schemas_parse_standalone(schema_name: str) -> None:
    """Each compression schema parses without an include or companion file."""
    path = SCHEMA_DIR / schema_name
    document = yaml.safe_load(path.read_text(encoding="utf-8"))

    assert isinstance(document, dict)
    assert isinstance(document["compression_rules"], dict)
    assert isinstance(document["compression_rules_contract"], dict)


def test_compression_contract_preserves_dispatch_layout_witness(
    lean_doc: dict[str, Any],
) -> None:
    """The metadata contract cannot add, reorder, or rename dispatch positions."""
    canonical = tuple(lean_doc["layout_invariant"]["canonical_order"])

    assert canonical == tuple(DEFAULT_DISPATCH_LAYOUT)
    assert len(canonical) == 17
    assert canonical[: len(FROZEN_PREFIX_V7)] == FROZEN_PREFIX_V7
    assert "compression_rules_contract" not in canonical
