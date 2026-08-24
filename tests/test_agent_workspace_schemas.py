"""Schema validation tests for the agent-workspace YAML schema registry.

Covers the 13 files in `schemas/agent-workspace/` (1 index + 12 artifact
schemas). The v8.3.0 PV-04 contracts remain covered alongside the v16.0.0 M1
checklist/stage/preflight additions and the goal/status v2 contracts.

Test scope (per .local/research/v8.3.0_patch_plan.md §v8.2.4 AC-1..AC-10):

* AC-1: Every schema YAML safe-loads without error and exposes the canonical
        DevolaFlow declarative-schema convention (design_reference, schema_name,
        schema_version, governing_rules).
* AC-3: change-spec.yaml correctly enforces OpenSpec delta heading patterns
        (## ADDED / MODIFIED / REMOVED Requirements) — declared in the schema
        AND demonstrated against valid + invalid markdown fixtures.
* AC-4: handoff-envelope.yaml enforces append-only invariant (seq monotonic
        starting 1) and the discriminated `envelope_kind` union (TaskDispatch
        / StatusReport / EscalationEvent) — verified against three fixture
        envelopes plus a multi-block negative case.
* AC-5: change-status.yaml v2 enforces FSM state values, the three-layer owner
        enum, checklist-round fields, and read compatibility for v1 instances.
* AC-6: Token budgets are encoded per artifact (soft + hard) and the budget
        block exists for every per-artifact schema.

The tests deliberately avoid touching `.local/.agent/` runtime state — fixtures
are built in a tmp_path or expressed as inline strings.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = REPO_ROOT / "schemas" / "agent-workspace"

# The registry contains 13 files total (1 index + 12 artifact schemas). The
# schema ids match the basename minus `.yaml`.
EXPECTED_SCHEMA_FILES: list[Path] = [
    SCHEMA_DIR / "__init__.yaml",
    SCHEMA_DIR / "change-goal.yaml",
    SCHEMA_DIR / "change-acceptance.yaml",
    SCHEMA_DIR / "change-spec.yaml",
    SCHEMA_DIR / "change-tasks.yaml",
    SCHEMA_DIR / "change-checklist.yaml",
    SCHEMA_DIR / "change-stage.yaml",
    SCHEMA_DIR / "change-preflight.yaml",
    SCHEMA_DIR / "change-status.yaml",
    SCHEMA_DIR / "owned-files.yaml",
    SCHEMA_DIR / "handoff-envelope.yaml",
    SCHEMA_DIR / "agent-config.yaml",
    SCHEMA_DIR / "source-of-truth-spec.yaml",
]

# Schemas that govern an actual artifact (i.e. NOT the index). All of these
# carry token_budget + governing_rules + instance_path_template.
ARTIFACT_SCHEMA_FILES: list[Path] = [p for p in EXPECTED_SCHEMA_FILES if p.name != "__init__.yaml"]

EXPECTED_SCHEMA_VERSIONS: dict[str, int] = {
    path.stem: 2 if path.stem in {"change-goal", "change-status"} else 1
    for path in EXPECTED_SCHEMA_FILES
}

V16_ARTIFACT_SCHEMA_NAMES = {
    "change-goal",
    "change-checklist",
    "change-stage",
    "change-preflight",
    "change-status",
}

# Per Rule C-9 — verbatim soft / hard token budgets keyed by schema_name.
EXPECTED_TOKEN_BUDGETS: dict[str, tuple[int, int]] = {
    "change-goal": (200, 400),
    "change-acceptance": (400, 800),
    "change-spec": (1500, 3000),
    "change-tasks": (800, 1500),
    "change-checklist": (1200, 2400),
    "change-stage": (400, 800),
    "change-preflight": (600, 1200),
    "change-status": (150, 300),
    "owned-files": (50, 100),
    "handoff-envelope": (600, 1200),
    "agent-config": (400, 800),
    "source-of-truth-spec": (2000, 4000),
}

# Canonical FSM transition matrix — declared verbatim in change-status.yaml
# `state_transitions` (per design.md §1.3).
EXPECTED_FSM_STATES: list[str] = [
    "PROPOSED",
    "IN_PROGRESS",
    "VERIFYING",
    "ARCHIVED",
    "ESCALATED",
]

EXPECTED_FSM_TRANSITIONS: dict[str, list[str]] = {
    "PROPOSED": ["IN_PROGRESS"],
    "IN_PROGRESS": ["VERIFYING", "ESCALATED"],
    "VERIFYING": ["IN_PROGRESS", "ARCHIVED"],
    "ARCHIVED": [],
    "ESCALATED": [],
}

LEGACY_STATUS_REQUIRED_FIELDS = {
    "schema_version",
    "change_id",
    "state",
    "percent_complete",
    "owner_layer",
    "owner_session_id",
    "last_updated",
    "last_handoff_seq",
    "gate_score",
    "verify_pass",
}

# Three handoff envelope_kind discriminator values — must match
# handoff-envelope.yaml `discriminated_union.variants`.
EXPECTED_ENVELOPE_KINDS: list[str] = ["TaskDispatch", "StatusReport", "EscalationEvent"]
EXPECTED_VARIANT_BLOCK_MAPPING: dict[str, str] = {
    "TaskDispatch": "dispatch",
    "StatusReport": "report",
    "EscalationEvent": "escalation",
}


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------


def _load_yaml(path: Path) -> dict[str, Any]:
    """yaml.safe_load wrapper that tolerates `__init__.yaml` as a regular file."""
    raw = path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw)
    if data is None:
        raise AssertionError(f"{path.name} parsed to None (empty document)")
    if not isinstance(data, dict):
        raise AssertionError(f"{path.name} must parse to a mapping (got {type(data).__name__})")
    return data


def _parse_markdown_example(raw: str) -> tuple[dict[str, Any], str]:
    """Parse a schema's Markdown-with-YAML-frontmatter worked example."""
    parts = raw.strip().split("---", 2)
    if len(parts) != 3 or parts[0] != "":
        raise AssertionError("example must start with YAML frontmatter delimited by `---`")
    frontmatter = yaml.safe_load(parts[1])
    if not isinstance(frontmatter, dict):
        raise AssertionError("example frontmatter must parse to a mapping")
    return frontmatter, parts[2].strip()


@pytest.fixture(scope="module")
def schemas() -> dict[str, dict[str, Any]]:
    """All 13 schemas, keyed by schema_name."""
    out: dict[str, dict[str, Any]] = {}
    for path in EXPECTED_SCHEMA_FILES:
        doc = _load_yaml(path)
        out[doc["schema_name"]] = doc
    return out


@pytest.fixture(scope="module")
def index_schema(schemas: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return schemas["agent-workspace-index"]


# =============================================================================
# AC-1 — All 13 schemas exist + safe_load + canonical convention
# =============================================================================


@pytest.mark.parametrize("schema_path", EXPECTED_SCHEMA_FILES, ids=lambda p: p.name)
def test_schema_file_exists(schema_path: Path) -> None:
    """Every expected schema file is present on disk."""
    assert schema_path.is_file(), f"missing schema: {schema_path.relative_to(REPO_ROOT)}"


@pytest.mark.parametrize("schema_path", EXPECTED_SCHEMA_FILES, ids=lambda p: p.name)
def test_schema_yaml_safe_loads(schema_path: Path) -> None:
    """AC-1: every schema yaml.safe_loads to a non-empty mapping."""
    doc = _load_yaml(schema_path)
    assert len(doc) > 0, f"{schema_path.name} parsed to empty dict"


@pytest.mark.parametrize("schema_path", EXPECTED_SCHEMA_FILES, ids=lambda p: p.name)
def test_schema_carries_canonical_metadata(schema_path: Path) -> None:
    """Every schema carries the 4 mandatory metadata keys for the local convention."""
    doc = _load_yaml(schema_path)
    for required_key in ("design_reference", "schema_name", "schema_version", "last_updated"):
        assert required_key in doc, (
            f"{schema_path.name} missing canonical metadata key '{required_key}'"
        )


@pytest.mark.parametrize("schema_path", EXPECTED_SCHEMA_FILES, ids=lambda p: p.name)
def test_schema_versions_match_registry_generation(schema_path: Path) -> None:
    """Goal/status are v2; the index and all additive schemas remain v1."""
    doc = _load_yaml(schema_path)
    expected = EXPECTED_SCHEMA_VERSIONS[schema_path.stem]
    assert doc["schema_version"] == expected, (
        f"{schema_path.name} schema_version drift — expected {expected}, "
        f"got {doc['schema_version']}"
    )


def test_no_unexpected_files_in_schema_dir() -> None:
    """The schema directory contains exactly the 13 expected YAML files."""
    actual = sorted(p.name for p in SCHEMA_DIR.iterdir() if p.is_file())
    expected = sorted(p.name for p in EXPECTED_SCHEMA_FILES)
    assert actual == expected, f"schemas/agent-workspace/ drift — expected {expected}, got {actual}"


def test_schema_dir_has_no_subdirs() -> None:
    """The registry remains flat; subdirectories would be unindexed schemas."""
    subdirs = [p for p in SCHEMA_DIR.iterdir() if p.is_dir()]
    assert subdirs == [], f"schemas/agent-workspace/ has unexpected subdirs: {subdirs}"


# =============================================================================
# Index schema — declares the 12 artifact schemas
# =============================================================================


def test_index_lists_all_twelve_artifact_schemas(index_schema: dict[str, Any]) -> None:
    """__init__.yaml `schemas` list enumerates all 12 artifact schemas."""
    listed_ids = sorted(s["id"] for s in index_schema["schemas"])
    expected_ids = sorted(p.stem for p in ARTIFACT_SCHEMA_FILES)
    assert listed_ids == expected_ids, f"index drift — expected {expected_ids}, got {listed_ids}"


def test_index_files_resolve(index_schema: dict[str, Any]) -> None:
    """Every `file:` entry in the index points to a real file on disk."""
    for entry in index_schema["schemas"]:
        target = SCHEMA_DIR / entry["file"]
        assert target.is_file(), f"index entry id={entry['id']!r} references missing file {target}"


def test_index_token_budgets_match_per_schema_files(
    index_schema: dict[str, Any], schemas: dict[str, dict[str, Any]]
) -> None:
    """Token budgets in the index agree byte-for-byte with the per-schema files."""
    for entry in index_schema["schemas"]:
        per_schema = schemas[entry["id"]]
        per_budget = per_schema["token_budget"]
        idx_budget = entry["token_budget"]
        assert per_budget["soft"] == idx_budget["soft"], (
            f"{entry['id']} soft budget drift —"
            f" index={idx_budget['soft']} vs schema={per_budget['soft']}"
        )
        assert per_budget["hard"] == idx_budget["hard"], (
            f"{entry['id']} hard budget drift —"
            f" index={idx_budget['hard']} vs schema={per_budget['hard']}"
        )


def test_index_governing_rules_include_workspace_quartet(
    index_schema: dict[str, Any],
) -> None:
    """The 4 v8.2.2 rules (S-8, S-9, C-9, A-4) all appear in the index governing_rules."""
    declared = set(index_schema["governing_rules"])
    expected = {"S-8", "S-9", "C-9", "A-4"}
    assert expected <= declared, (
        f"index governing_rules missing v8.2.2 quartet — expected {expected}, got {declared}"
    )


def test_index_cross_references_external_openspec(index_schema: dict[str, Any]) -> None:
    """OpenSpec is the upstream source for the delta format — must be cited (S-7)."""
    external = index_schema["cross_references"]["external"]
    sources = {entry["source"] for entry in external}
    assert "openspec" in sources, "OpenSpec must be cited as the delta-format source"
    openspec_entry = next(e for e in external if e["source"] == "openspec")
    assert openspec_entry["url"].startswith("https://github.com/"), (
        "OpenSpec url must be a canonical GitHub URL (S-7 / SF-6)"
    )


# =============================================================================
# AC-6 — Token budgets per Rule C-9 (declared on every artifact schema)
# =============================================================================


@pytest.mark.parametrize(
    "schema_name,expected_soft,expected_hard",
    [(name, soft, hard) for name, (soft, hard) in EXPECTED_TOKEN_BUDGETS.items()],
)
def test_artifact_token_budget_matches_rule_c9(
    schemas: dict[str, dict[str, Any]],
    schema_name: str,
    expected_soft: int,
    expected_hard: int,
) -> None:
    """AC-6: token_budget.soft / .hard per artifact match the verbatim Rule C-9 table."""
    doc = schemas[schema_name]
    budget = doc["token_budget"]
    assert budget["soft"] == expected_soft, f"{schema_name} soft budget drift"
    assert budget["hard"] == expected_hard, f"{schema_name} hard budget drift"
    assert budget["units"] == "tokens", (
        f"{schema_name} token_budget.units must be 'tokens' (per C-9 vocabulary)"
    )
    assert budget["on_soft_breach"] == "warn", f"{schema_name} on_soft_breach must == 'warn'"
    assert budget["on_hard_breach"] == "fail_commit", (
        f"{schema_name} on_hard_breach must == 'fail_commit'"
    )


@pytest.mark.parametrize("schema_name", list(EXPECTED_TOKEN_BUDGETS.keys()), ids=lambda s: s)
def test_artifact_carries_lint_enforcement_command(
    schemas: dict[str, dict[str, Any]], schema_name: str
) -> None:
    """Each artifact schema documents the lint command that enforces token budget."""
    doc = schemas[schema_name]
    enforcement = doc["token_budget"]["enforcement"]
    assert isinstance(enforcement, list), f"{schema_name} enforcement must be a list"
    assert any("devolaflow.agent_workspace.lint" in str(item) for item in enforcement), (
        f"{schema_name} enforcement must reference `devolaflow.agent_workspace.lint`"
    )


# =============================================================================
# AC-5 — change-status FSM enum + transitions
# =============================================================================


def test_change_status_state_enum_matches_design(
    schemas: dict[str, dict[str, Any]],
) -> None:
    """change-status.yaml `state` enum matches the verbatim 5-state FSM from design.md §2.5."""
    state_field = schemas["change-status"]["fields"]["state"]
    assert state_field["type"] == "string"
    assert sorted(state_field["enum"]) == sorted(EXPECTED_FSM_STATES), (
        f"FSM enum drift — expected {EXPECTED_FSM_STATES}, got {state_field['enum']}"
    )


def test_change_status_state_transitions_match_design(
    schemas: dict[str, dict[str, Any]],
) -> None:
    """state_transitions matrix in change-status.yaml matches design.md §1.3 verbatim."""
    transitions = schemas["change-status"]["state_transitions"]
    for state, expected_next in EXPECTED_FSM_TRANSITIONS.items():
        assert state in transitions, f"FSM matrix missing state {state!r}"
        actual_next = transitions[state]["allowed_next"]
        assert sorted(actual_next) == sorted(expected_next), (
            f"FSM transition drift for state {state!r} —"
            f" expected {expected_next}, got {actual_next}"
        )


def test_change_status_required_fields_complete(
    schemas: dict[str, dict[str, Any]],
) -> None:
    """v2 requires the legacy fields plus four checklist-round progress fields."""
    doc = schemas["change-status"]
    required = set(doc["instance_top_level_required"])
    expected = LEGACY_STATUS_REQUIRED_FIELDS | {
        "checklist_checked",
        "checklist_total",
        "current_round",
        "next_blockers",
    }
    assert required == expected, f"change-status required fields drift — {required ^ expected}"
    assert doc["fields"]["schema_version"]["enum"] == [2]
    assert doc["fields"]["checklist_checked"]["minimum"] == 0
    assert doc["fields"]["checklist_total"]["minimum"] == 1
    assert doc["fields"]["current_round"]["minimum"] == 0
    assert doc["fields"]["next_blockers"]["max_items"] == 3


def test_change_status_owner_layer_enum() -> None:
    """v2 owner_layer is constrained to the three-layer L0..L2 model."""
    doc = _load_yaml(SCHEMA_DIR / "change-status.yaml")
    assert sorted(doc["fields"]["owner_layer"]["enum"]) == ["L0", "L1", "L2"]
    legacy = doc["compatibility"]["schema_version_1"]
    assert legacy["accepted"] is True
    assert legacy["owner_layer_mapping"] == {
        "L0": "L0",
        "L1": "L0",
        "L2": "L1",
        "L3": "L2",
    }
    assert legacy["history_rewrite"] == "forbidden"


def test_change_status_terminal_states_have_empty_allowed_next() -> None:
    """ARCHIVED and ESCALATED are terminal — no allowed_next."""
    doc = _load_yaml(SCHEMA_DIR / "change-status.yaml")
    transitions = doc["state_transitions"]
    assert transitions["ARCHIVED"]["allowed_next"] == []
    assert transitions["ESCALATED"]["allowed_next"] == []


def _validate_status_instance(instance: dict[str, Any]) -> list[str]:
    """Lightweight v2 validator with the declared v1 compatibility window."""
    schema = _load_yaml(SCHEMA_DIR / "change-status.yaml")
    errors: list[str] = []
    version = instance.get("schema_version")
    if version == 1:
        compatibility = schema["compatibility"]["schema_version_1"]
        if not compatibility["accepted"]:
            errors.append("schema_version 1 is not accepted")
        required = LEGACY_STATUS_REQUIRED_FIELDS
        owner_layers = set(compatibility["owner_layer_mapping"])
    elif version == schema["schema_version"]:
        required = set(schema["instance_top_level_required"])
        owner_layers = set(schema["fields"]["owner_layer"]["enum"])
    else:
        required = set(schema["instance_top_level_required"])
        owner_layers = set(schema["fields"]["owner_layer"]["enum"])
        errors.append(f"unsupported schema_version: {version!r}")
    for key in required:
        if key not in instance:
            errors.append(f"missing required field: {key}")
    state = instance.get("state")
    enum = schema["fields"]["state"]["enum"]
    if state is not None and state not in enum:
        errors.append(f"state value {state!r} not in enum {enum}")
    pct = instance.get("percent_complete")
    if pct is not None and not (0 <= pct <= 100):
        errors.append(f"percent_complete {pct} not in [0, 100]")
    layer = instance.get("owner_layer")
    if layer is not None and layer not in owner_layers:
        errors.append(f"owner_layer {layer!r} not in {sorted(owner_layers)}")
    if version == 2:
        checked = instance.get("checklist_checked")
        total = instance.get("checklist_total")
        if checked is not None and total is not None and not (0 <= checked <= total):
            errors.append(f"checklist_checked {checked} not in [0, {total}]")
        current_round = instance.get("current_round")
        if current_round is not None and current_round < 0:
            errors.append(f"current_round {current_round} must be >= 0")
        blockers = instance.get("next_blockers")
        if blockers is not None and (not isinstance(blockers, list) or len(blockers) > 3):
            errors.append("next_blockers must be a list with at most 3 entries")
    return errors


def test_status_fixture_valid_minimal_passes() -> None:
    """AC-5: a legacy v1 STATUS.yaml remains valid during the compatibility window."""
    instance = {
        "schema_version": 1,
        "change_id": "add-dark-mode",
        "state": "PROPOSED",
        "percent_complete": 0,
        "owner_layer": "L0",
        "owner_session_id": "550e8400-e29b-41d4-a716-446655440000",
        "last_updated": "2026-04-22T10:14:33Z",
        "last_handoff_seq": 0,
        "gate_score": None,
        "verify_pass": None,
    }
    errors = _validate_status_instance(instance)
    assert not errors, f"valid fixture rejected: {errors}"


def test_status_fixture_invalid_state_rejected() -> None:
    """AC-5: invalid state value (not in enum) is rejected."""
    instance = {
        "schema_version": 1,
        "change_id": "add-dark-mode",
        "state": "DRAFT",  # not a valid FSM state
        "percent_complete": 0,
        "owner_layer": "L0",
        "owner_session_id": "550e8400-e29b-41d4-a716-446655440000",
        "last_updated": "2026-04-22T10:14:33Z",
        "last_handoff_seq": 0,
        "gate_score": None,
        "verify_pass": None,
    }
    errors = _validate_status_instance(instance)
    assert any("state value" in e for e in errors), (
        f"invalid state should be rejected; got: {errors}"
    )


def test_status_fixture_missing_required_rejected() -> None:
    """AC-5: missing required field is rejected."""
    instance = {
        "schema_version": 1,
        "change_id": "add-dark-mode",
        "state": "PROPOSED",
        # missing percent_complete and others
    }
    errors = _validate_status_instance(instance)
    assert errors, "incomplete instance should produce errors"
    missing = [e for e in errors if "missing required" in e]
    assert len(missing) >= 6, f"expected ≥ 6 missing-field errors, got {len(missing)}: {missing}"


def test_status_fixture_invalid_owner_layer_rejected() -> None:
    """Legacy owner_layer accepts L0..L3 but still rejects L4."""
    instance = {
        "schema_version": 1,
        "change_id": "add-dark-mode",
        "state": "PROPOSED",
        "percent_complete": 0,
        "owner_layer": "L4",  # invalid
        "owner_session_id": "uuid",
        "last_updated": "2026-04-22T10:14:33Z",
        "last_handoff_seq": 0,
        "gate_score": None,
        "verify_pass": None,
    }
    errors = _validate_status_instance(instance)
    assert any("owner_layer" in e for e in errors)


# =============================================================================
# AC-3 — change-spec OpenSpec delta heading enforcement
# =============================================================================


def test_change_spec_delta_section_variants() -> None:
    """change-spec.yaml declares all three OpenSpec delta variants verbatim."""
    doc = _load_yaml(SCHEMA_DIR / "change-spec.yaml")
    variants = doc["body"]["delta_sections"]["variants"]
    ids = sorted(v["id"] for v in variants)
    assert ids == ["ADDED", "MODIFIED", "REMOVED"], (
        f"OpenSpec delta variants drift — expected [ADDED, MODIFIED, REMOVED], got {ids}"
    )


def test_change_spec_delta_headings_are_verbatim() -> None:
    """Each delta variant declares its EXACT verbatim heading string."""
    doc = _load_yaml(SCHEMA_DIR / "change-spec.yaml")
    variants = {v["id"]: v for v in doc["body"]["delta_sections"]["variants"]}
    assert variants["ADDED"]["heading"] == "## ADDED Requirements"
    assert variants["MODIFIED"]["heading"] == "## MODIFIED Requirements"
    assert variants["REMOVED"]["heading"] == "## REMOVED Requirements"


def test_change_spec_at_least_one_delta_required() -> None:
    """Schema declares 'at_least_one_required: true' for delta_sections."""
    doc = _load_yaml(SCHEMA_DIR / "change-spec.yaml")
    assert doc["body"]["delta_sections"]["at_least_one_required"] is True


def _validate_spec_markdown(md: str) -> list[str]:
    """Validator that enforces the change-spec body contract on a markdown string."""
    doc = _load_yaml(SCHEMA_DIR / "change-spec.yaml")
    errors: list[str] = []
    purpose_pattern = doc["body"]["required_sections"][1]["pattern"]
    if not re.search(purpose_pattern, md, re.MULTILINE):
        errors.append("missing required '## Purpose' section")
    delta_section_block = doc["body"]["delta_sections"]
    delta_patterns = [v["pattern"] for v in delta_section_block["variants"]]
    matches = [p for p in delta_patterns if re.search(p, md, re.MULTILINE)]
    if delta_section_block["at_least_one_required"] and not matches:
        errors.append("at least one delta section (ADDED/MODIFIED/REMOVED) required")
    if "## added requirements" in md.lower() and "## ADDED Requirements" not in md:
        errors.append("delta heading capitalization MUST match exactly: '## ADDED Requirements'")
    return errors


def test_spec_markdown_valid_with_added_section_passes() -> None:
    """AC-3: valid spec markdown with ADDED section passes validation."""
    md = """
# Operation Spec for add-dark-mode

## Purpose
Add user-toggleable dark mode to the demo dashboard.

## ADDED Requirements

### Requirement: Dark mode toggle is persistent across reloads
The system MUST persist the dark-mode preference in localStorage.

#### Scenario: User toggles dark mode and reloads
- GIVEN the user clicks the dark-mode toggle
- WHEN the page is reloaded
- THEN the dark-mode preference is restored from localStorage.
"""
    errors = _validate_spec_markdown(md)
    assert not errors, f"valid spec rejected: {errors}"


def test_spec_markdown_missing_delta_section_rejected() -> None:
    """AC-3: spec with NO delta section (ADDED/MODIFIED/REMOVED) is rejected."""
    md = """
# Operation Spec for add-dark-mode

## Purpose
Add dark mode but forget the delta sections.

## Notes
This is some other content but no delta heading.
"""
    errors = _validate_spec_markdown(md)
    assert any("delta section" in e for e in errors), (
        f"spec without delta sections should be rejected; got: {errors}"
    )


def test_spec_markdown_missing_purpose_rejected() -> None:
    """AC-3: spec missing the required ## Purpose section is rejected."""
    md = """
# Operation Spec for add-dark-mode

## ADDED Requirements

### Requirement: foo
The system MUST do something.
"""
    errors = _validate_spec_markdown(md)
    assert any("Purpose" in e for e in errors)


def test_spec_markdown_lowercase_added_rejected() -> None:
    """AC-3: lowercase '## added requirements' is rejected (capitalization MUST match)."""
    md = """
# Operation Spec for add-dark-mode

## Purpose
Test capitalization.

## added requirements

### Requirement: foo
The system MUST do something.
"""
    errors = _validate_spec_markdown(md)
    assert any("capitalization" in e or "delta section" in e for e in errors), (
        f"lowercase delta heading should be rejected; got: {errors}"
    )


def test_spec_markdown_modified_with_previously_passes() -> None:
    """change-spec MODIFIED Requirement template includes (Previously: ...) marker."""
    doc = _load_yaml(SCHEMA_DIR / "change-spec.yaml")
    modified = next(v for v in doc["body"]["delta_sections"]["variants"] if v["id"] == "MODIFIED")
    assert modified["previously_marker_required"] is True
    assert "(Previously:" in modified["body_template"]


def test_spec_markdown_removed_requires_reason() -> None:
    """change-spec REMOVED Requirement template requires a reason in parentheses."""
    doc = _load_yaml(SCHEMA_DIR / "change-spec.yaml")
    removed = next(v for v in doc["body"]["delta_sections"]["variants"] if v["id"] == "REMOVED")
    assert removed["reason_required"] is True


def test_change_spec_delta_kind_enum() -> None:
    """delta_kind frontmatter enum is exactly [lite, full]."""
    doc = _load_yaml(SCHEMA_DIR / "change-spec.yaml")
    enum = doc["frontmatter"]["fields"]["delta_kind"]["enum"]
    assert sorted(enum) == ["full", "lite"]


# =============================================================================
# AC-4 — handoff-envelope discriminated union + append-only
# =============================================================================


def test_handoff_envelope_kind_enum() -> None:
    """envelope_kind enum matches the 3 variants exactly."""
    doc = _load_yaml(SCHEMA_DIR / "handoff-envelope.yaml")
    enum = doc["fields"]["envelope_kind"]["enum"]
    assert sorted(enum) == sorted(EXPECTED_ENVELOPE_KINDS), (
        f"envelope_kind enum drift — expected {EXPECTED_ENVELOPE_KINDS}, got {enum}"
    )


def test_handoff_discriminator_block_present() -> None:
    """The schema declares a `discriminated_union` block with discriminator: envelope_kind."""
    doc = _load_yaml(SCHEMA_DIR / "handoff-envelope.yaml")
    assert "discriminated_union" in doc, "handoff-envelope must declare a discriminated_union"
    du = doc["discriminated_union"]
    assert du["discriminator"] == "envelope_kind"


def test_handoff_variant_block_mapping_complete() -> None:
    """The variant_block_mapping covers all 3 envelope kinds."""
    doc = _load_yaml(SCHEMA_DIR / "handoff-envelope.yaml")
    mapping = doc["discriminated_union"]["variant_block_mapping"]
    assert mapping == EXPECTED_VARIANT_BLOCK_MAPPING


def test_handoff_seq_monotonic_int_starting_one() -> None:
    """seq is declared as monotonic int starting at 1."""
    doc = _load_yaml(SCHEMA_DIR / "handoff-envelope.yaml")
    seq = doc["fields"]["seq"]
    assert seq["type"] == "int"
    assert seq["minimum"] == 1
    assert seq["monotonic"] is True


def test_handoff_filename_pattern_includes_seq() -> None:
    """Filename pattern enforces 4-digit zero-padded seq."""
    doc = _load_yaml(SCHEMA_DIR / "handoff-envelope.yaml")
    fc = doc["filename_contract"]
    assert fc["parts"]["seq"]["zero_padded_width"] == 4
    assert fc["parts"]["seq"]["monotonic"] is True
    # Spot-check the regex matches a representative filename.
    assert re.match(fc["pattern"], "L0__L2__add-dark-mode__0001.yaml")
    # And rejects non-zero-padded seq.
    assert not re.match(fc["pattern"], "L0__L2__add-dark-mode__1.yaml")


def test_handoff_append_only_invariant_documented() -> None:
    """The append-only invariant text must be present in the schema's invariants list."""
    doc = _load_yaml(SCHEMA_DIR / "handoff-envelope.yaml")
    invariants = " ".join(doc["invariants"])
    assert "append-only" in invariants.lower() or "IMMUTABLE" in invariants
    assert "S-9" in invariants
    assert "seq+1" in invariants


def test_handoff_to_layer_must_differ() -> None:
    """The schema documents that from_layer != to_layer (no self-handoff)."""
    doc = _load_yaml(SCHEMA_DIR / "handoff-envelope.yaml")
    invariants = " ".join(doc["invariants"])
    assert "no self-handoff" in invariants.lower() or "MUST NOT equal" in invariants


def _validate_envelope(env: dict[str, Any]) -> list[str]:
    """Validator that enforces the discriminator + presence rules of handoff-envelope."""
    doc = _load_yaml(SCHEMA_DIR / "handoff-envelope.yaml")
    errors: list[str] = []
    for key in doc["instance_top_level_required"]:
        if key not in env:
            errors.append(f"missing required field: {key}")
    if env.get("envelope_kind") not in doc["fields"]["envelope_kind"]["enum"]:
        errors.append(f"invalid envelope_kind: {env.get('envelope_kind')!r}")
    if env.get("from_layer") == env.get("to_layer") and env.get("from_layer") is not None:
        errors.append("from_layer MUST NOT equal to_layer (no self-handoff)")
    if env.get("seq") is not None and env["seq"] < 1:
        errors.append(f"seq must be >= 1, got {env['seq']}")
    mapping = doc["discriminated_union"]["variant_block_mapping"]
    expected_block = mapping.get(env.get("envelope_kind", ""))
    present_blocks = [b for b in mapping.values() if b in env]
    if expected_block and expected_block not in env:
        errors.append(
            f"envelope_kind={env['envelope_kind']!r} requires the {expected_block!r} block"
        )
    if len(present_blocks) > 1:
        errors.append(f"only ONE variant block may be present, got {present_blocks}")
    return errors


def test_envelope_task_dispatch_valid_passes() -> None:
    """AC-4: minimal valid TaskDispatch envelope passes validation."""
    env = {
        "schema_version": 1,
        "seq": 1,
        "from_layer": "L0",
        "to_layer": "L2",
        "change_id": "add-dark-mode",
        "created": "2026-04-22T10:14:33Z",
        "envelope_kind": "TaskDispatch",
        "dispatch": {
            "task_id": "T01",
            "type": "implement",
            "acceptance_criteria_ref": ".local/.agent/active/add-dark-mode/acceptance.md#ac-1",
            "owned_files_ref": ".local/.agent/active/add-dark-mode/owned_files.txt",
        },
    }
    errors = _validate_envelope(env)
    assert not errors, f"valid TaskDispatch rejected: {errors}"


def test_envelope_status_report_valid_passes() -> None:
    """AC-4: minimal valid StatusReport envelope passes validation."""
    env = {
        "schema_version": 1,
        "seq": 4,
        "from_layer": "L3",
        "to_layer": "L2",
        "change_id": "add-dark-mode",
        "created": "2026-04-22T11:02:18Z",
        "envelope_kind": "StatusReport",
        "report": {"task_id": "T02", "state": "completed"},
    }
    errors = _validate_envelope(env)
    assert not errors, f"valid StatusReport rejected: {errors}"


def test_envelope_escalation_event_valid_passes() -> None:
    """AC-4: minimal valid EscalationEvent envelope passes validation."""
    env = {
        "schema_version": 1,
        "seq": 7,
        "from_layer": "L3",
        "to_layer": "L0",
        "change_id": "add-dark-mode",
        "created": "2026-04-22T11:48:09Z",
        "envelope_kind": "EscalationEvent",
        "escalation": {
            "severity": "HUMAN_INTERVENE",
            "trigger": "P4 bounded retry exhausted (5/5)",
            "proposed_action": "Pause for human to install pixelmatch.",
        },
    }
    errors = _validate_envelope(env)
    assert not errors, f"valid EscalationEvent rejected: {errors}"


def test_envelope_invalid_kind_rejected() -> None:
    """AC-4: invalid envelope_kind is rejected."""
    env = {
        "schema_version": 1,
        "seq": 1,
        "from_layer": "L0",
        "to_layer": "L2",
        "change_id": "add-dark-mode",
        "created": "2026-04-22T10:14:33Z",
        "envelope_kind": "FooBar",  # not in enum
    }
    errors = _validate_envelope(env)
    assert any("invalid envelope_kind" in e for e in errors)


def test_envelope_missing_variant_block_rejected() -> None:
    """AC-4: TaskDispatch envelope without `dispatch:` block is rejected."""
    env = {
        "schema_version": 1,
        "seq": 1,
        "from_layer": "L0",
        "to_layer": "L2",
        "change_id": "add-dark-mode",
        "created": "2026-04-22T10:14:33Z",
        "envelope_kind": "TaskDispatch",
        # missing 'dispatch:' block
    }
    errors = _validate_envelope(env)
    assert any("requires the 'dispatch'" in e for e in errors)


def test_envelope_multiple_variant_blocks_rejected() -> None:
    """AC-4: envelope with TWO variant blocks (dispatch AND report) is rejected."""
    env = {
        "schema_version": 1,
        "seq": 1,
        "from_layer": "L0",
        "to_layer": "L2",
        "change_id": "add-dark-mode",
        "created": "2026-04-22T10:14:33Z",
        "envelope_kind": "TaskDispatch",
        "dispatch": {
            "task_id": "T01",
            "type": "implement",
            "acceptance_criteria_ref": ".local/.agent/active/add-dark-mode/acceptance.md",
            "owned_files_ref": ".local/.agent/active/add-dark-mode/owned_files.txt",
        },
        "report": {"task_id": "T01", "state": "completed"},  # spurious second block
    }
    errors = _validate_envelope(env)
    assert any("only ONE variant block" in e for e in errors)


def test_envelope_self_handoff_rejected() -> None:
    """AC-4: envelope with from_layer == to_layer is rejected."""
    env = {
        "schema_version": 1,
        "seq": 1,
        "from_layer": "L2",
        "to_layer": "L2",  # same layer — invalid
        "change_id": "add-dark-mode",
        "created": "2026-04-22T10:14:33Z",
        "envelope_kind": "TaskDispatch",
        "dispatch": {
            "task_id": "T01",
            "type": "implement",
            "acceptance_criteria_ref": ".local/.agent/active/add-dark-mode/acceptance.md",
            "owned_files_ref": ".local/.agent/active/add-dark-mode/owned_files.txt",
        },
    }
    errors = _validate_envelope(env)
    assert any("self-handoff" in e for e in errors)


def test_envelope_seq_zero_rejected() -> None:
    """AC-4: seq=0 is rejected (counter starts at 1)."""
    env = {
        "schema_version": 1,
        "seq": 0,  # invalid — must be >= 1
        "from_layer": "L0",
        "to_layer": "L2",
        "change_id": "add-dark-mode",
        "created": "2026-04-22T10:14:33Z",
        "envelope_kind": "TaskDispatch",
        "dispatch": {
            "task_id": "T01",
            "type": "implement",
            "acceptance_criteria_ref": ".local/.agent/active/add-dark-mode/acceptance.md",
            "owned_files_ref": ".local/.agent/active/add-dark-mode/owned_files.txt",
        },
    }
    errors = _validate_envelope(env)
    assert any(">= 1" in e for e in errors)


# =============================================================================
# Per-artifact frontmatter / format coverage
# =============================================================================


def test_change_goal_priority_enum() -> None:
    """change-goal priority enum is exactly P1..P4."""
    doc = _load_yaml(SCHEMA_DIR / "change-goal.yaml")
    enum = doc["frontmatter"]["fields"]["priority"]["enum"]
    assert sorted(enum) == ["P1", "P2", "P3", "P4"]


def test_change_goal_intent_class_enum_complete() -> None:
    """change-goal intent_class enum covers the 7 documented values."""
    doc = _load_yaml(SCHEMA_DIR / "change-goal.yaml")
    enum = doc["frontmatter"]["fields"]["intent_class"]["enum"]
    assert sorted(enum) == sorted(
        ["feature", "bugfix", "refactor", "migration", "spike", "docs", "ops"]
    )


def test_change_goal_v2_numbered_contract_and_legacy_compatibility() -> None:
    """Goal v2 links contiguous G<n> goals to matching checklist partitions."""
    doc = _load_yaml(SCHEMA_DIR / "change-goal.yaml")
    assert doc["schema_version"] == 2
    assert set(doc["frontmatter"]["required"]) == {
        "id",
        "created",
        "priority",
        "intent_class",
        "goals_count",
    }
    goals = doc["body"]["goal_entries"]
    assert goals["unique_ids"] is True
    assert goals["ordered_sequentially_from"] == 1
    assert goals["link_id_must_equal_entry_id"] is True
    assert goals["count_field"] == "goals_count"

    frontmatter, body = _parse_markdown_example(doc["example"])
    links = re.findall(r"^- G(\d+): .+ → checklist\.md ## G(\d+)$", body, re.MULTILINE)
    assert len(links) == frontmatter["goals_count"]
    assert all(goal_id == link_id for goal_id, link_id in links)

    legacy = doc["compatibility"]["schema_version_1"]
    assert "does not contain checklist.md" in legacy["detection"]
    assert "v1 contract" in legacy["behavior"]
    assert legacy["history_rewrite"] == "forbidden"


@pytest.mark.parametrize(
    ("schema_name", "required_frontmatter", "required_headings"),
    [
        (
            "change-checklist",
            {
                "parent",
                "schema_version",
                "total_items",
                "checked",
                "priority_dist",
                "reverted_open",
            },
            ["# Checklist"],
        ),
        (
            "change-stage",
            {"parent", "schema_version", "current_round", "max_rounds", "capacity_per_round"},
            [
                "# Stage — Round Control",
                "## Priority Settings",
                "## Round History",
                "## Next Round Plan",
            ],
        ),
        (
            "change-preflight",
            {
                "parent",
                "schema_version",
                "authorized_at",
                "snapshot_round",
                "config_inherited_from",
                "project_config_hash",
            },
            [
                "# Preflight",
                "## 0. Project Configuration",
                "## 1. Stop Cards",
                "## 2. Authorization Record",
                "## 3. Permitted Stops",
                "## 4. Progress Snapshot",
            ],
        ),
    ],
)
def test_v16_new_artifact_schema_contracts(
    schemas: dict[str, dict[str, Any]],
    schema_name: str,
    required_frontmatter: set[str],
    required_headings: list[str],
) -> None:
    """The three additive schemas encode their core checklist-round contracts."""
    doc = schemas[schema_name]
    assert doc["schema_version"] == 1
    assert set(doc["frontmatter"]["required"]) == required_frontmatter
    assert [section["heading"] for section in doc["body"]["required_sections"]] == required_headings

    if schema_name == "change-checklist":
        assert doc["frontmatter"]["fields"]["total_items"]["maximum"] == 60
        assert doc["body"]["item_metadata"]["verify"]["required"] is True
        assert doc["reversion_contract"]["allowed_actors"] == ["user"]
        assert doc["reversion_contract"]["forbidden_actors"] == ["L0", "L1", "L2"]
    elif schema_name == "change-stage":
        assert doc["frontmatter"]["fields"]["capacity_per_round"]["maximum"] == 5
        assert [item["criterion"] for item in doc["selection_algorithm"]["order"]] == [
            "reverted_open",
            "priority",
            "dependencies",
            "checklist_order",
        ]
        assert doc["bounded_execution"]["stagnation"]["window_rounds"] == 2
    else:
        assert len(doc["section_0_project_configuration"]["config_sections"]) == 8
        assert doc["authorization_coupling"]["signer"] == "user"
        assert doc["section_3_permitted_stops"]["exact_item_count"] == 4


@pytest.mark.parametrize(
    "schema_name",
    ["change-checklist", "change-stage", "change-preflight"],
)
def test_v16_new_schema_examples_match_declared_structure(
    schemas: dict[str, dict[str, Any]], schema_name: str
) -> None:
    """Each new worked example parses and includes its declared frontmatter/body."""
    doc = schemas[schema_name]
    frontmatter, body = _parse_markdown_example(doc["example"])
    assert set(doc["frontmatter"]["required"]) <= set(frontmatter)
    assert frontmatter["schema_version"] == doc["schema_version"]
    for section in doc["body"]["required_sections"]:
        assert re.search(section["pattern"], body, re.MULTILINE), (
            f"{schema_name} example missing {section['heading']!r}"
        )


@pytest.mark.parametrize("schema_name", ["change-acceptance", "change-tasks"])
def test_legacy_schema_deprecation_contract(
    index_schema: dict[str, Any],
    schemas: dict[str, dict[str, Any]],
    schema_name: str,
) -> None:
    """Legacy artifacts stay indexed for v16 read compatibility through v17."""
    doc = schemas[schema_name]
    entry = next(item for item in index_schema["schemas"] if item["id"] == schema_name)
    for metadata in (doc, entry):
        assert metadata["deprecated_since"] == "16.0.0"
        assert metadata["replacement"] == "change-checklist"
        assert metadata["removal_target"] == "17.0.0"
    assert "read-only validation" in doc["deprecation_summary"]


def test_change_acceptance_quality_section_mandates_ruff() -> None:
    """The Quality AC section MUST mandate ruff check + ruff format --check."""
    doc = _load_yaml(SCHEMA_DIR / "change-acceptance.yaml")
    quality = next(s for s in doc["body"]["required_sections"] if s["heading"] == "## Quality")
    mandatory = quality["mandatory_items_substr"]
    assert "ruff check" in mandatory
    assert "ruff format --check" in mandatory
    assert "tests pass" in mandatory


def test_owned_files_max_paths_six() -> None:
    """owned-files max_paths is 6 per Wave decomposition limit (design.md §2.6)."""
    doc = _load_yaml(SCHEMA_DIR / "owned-files.yaml")
    assert doc["limits"]["max_paths"] == 6
    assert doc["limits"]["min_paths"] == 1


def test_owned_files_format_strict_no_blank_lines() -> None:
    """owned-files format: no blank lines, no comments, LF newlines."""
    doc = _load_yaml(SCHEMA_DIR / "owned-files.yaml")
    fmt = doc["file_format"]
    assert fmt["empty_lines_allowed"] is False
    assert fmt["comment_lines_allowed"] is False
    assert fmt["trailing_newline_required"] is True


def test_owned_files_must_be_relative() -> None:
    """owned-files lines MUST be repo-relative (S-2)."""
    doc = _load_yaml(SCHEMA_DIR / "owned-files.yaml")
    line = doc["line"]
    assert line["must_be_relative"] is True
    assert line["must_not_contain_dotdot"] is True
    assert line["must_not_contain_glob"] is True


def test_change_tasks_total_tasks_max_fifty() -> None:
    """change-tasks total_tasks must be in [1, 50]."""
    doc = _load_yaml(SCHEMA_DIR / "change-tasks.yaml")
    field = doc["frontmatter"]["fields"]["total_tasks"]
    assert field["minimum"] == 1
    assert field["maximum"] == 50


def test_change_tasks_per_task_constraints() -> None:
    """Per-task constraints encode the Wave limits (≤ 30 min, ≤ 6 owned files)."""
    doc = _load_yaml(SCHEMA_DIR / "change-tasks.yaml")
    constraints = doc["body"]["per_task_constraints"]
    assert constraints["max_owned_files_per_task"] == 6
    assert constraints["max_minutes_per_task"] == 30


def test_agent_config_mode_enum() -> None:
    """agent-config mode is exactly [lite, full]."""
    doc = _load_yaml(SCHEMA_DIR / "agent-config.yaml")
    enum = doc["fields"]["mode"]["enum"]
    assert sorted(enum) == ["full", "lite"]


def test_agent_config_schema_default_change_driven() -> None:
    """agent-config defaults to schema=change-driven (the v8.3.0 workflow)."""
    doc = _load_yaml(SCHEMA_DIR / "agent-config.yaml")
    assert doc["fields"]["schema"]["default"] == "change-driven"
    assert "change-driven" in doc["fields"]["schema"]["enum"]


def test_source_of_truth_spec_mutation_writers() -> None:
    """Source-of-truth file mutation is restricted to ChangeArchive.propose_merge (per A-4)."""
    doc = _load_yaml(SCHEMA_DIR / "source-of-truth-spec.yaml")
    writers = doc["mutation_contract"]["legal_writers"]
    assert writers == ["ChangeArchive.propose_merge"]
    preconditions = " ".join(doc["mutation_contract"]["preconditions"])
    assert "VERIFYING" in preconditions
    assert "Gate composite" in preconditions


def test_source_of_truth_spec_no_delta_sections() -> None:
    """Source-of-truth specs MUST NOT contain ADDED/MODIFIED/REMOVED sections."""
    doc = _load_yaml(SCHEMA_DIR / "source-of-truth-spec.yaml")
    invariants = " ".join(doc["invariants"])
    assert "MUST NOT contain delta sections" in invariants


# =============================================================================
# Cross-cutting — relative paths, governing rules, design references
# =============================================================================


@pytest.mark.parametrize("schema_path", ARTIFACT_SCHEMA_FILES, ids=lambda p: p.name)
def test_artifact_schema_no_absolute_paths(schema_path: Path) -> None:
    """S-2 / SF-5: no schema file may carry an absolute filesystem path.

    Uses the same `ABS_PATH_PATTERN` shape as `tests/test_self_improve_rules.py`
    for cross-test consistency — anything rooted at /home, /Users, /tmp, /var,
    /opt, /usr, /etc, or /benchmarks is forbidden.
    """
    abs_path_pattern = re.compile(r"(?<!\w)(/(?:home|Users|tmp|var|opt|usr|etc|benchmarks)/\S+)")
    text = schema_path.read_text(encoding="utf-8")
    matches = abs_path_pattern.findall(text)
    assert not matches, (
        f"{schema_path.name} carries absolute filesystem paths "
        f"(use relative paths or canonical GitHub URLs): {matches}"
    )


@pytest.mark.parametrize("schema_path", ARTIFACT_SCHEMA_FILES, ids=lambda p: p.name)
def test_artifact_schema_design_reference_format(schema_path: Path) -> None:
    """design_reference points to the applicable legacy or v16 design artifact."""
    doc = _load_yaml(schema_path)
    ref = doc["design_reference"]
    expected = (
        ".local/tasks/plan_mode_full_update/design/checklist_iteration_design.md"
        if doc["schema_name"] in V16_ARTIFACT_SCHEMA_NAMES
        else ".local/research/v8.3.0_design.md"
    )
    assert ref.startswith(expected), (
        f"{schema_path.name} design_reference must point at {expected} (got {ref!r})"
    )


@pytest.mark.parametrize("schema_path", ARTIFACT_SCHEMA_FILES, ids=lambda p: p.name)
def test_artifact_schema_token_budget_present(schema_path: Path) -> None:
    """AC-6: every artifact schema declares a token_budget block."""
    doc = _load_yaml(schema_path)
    assert "token_budget" in doc, f"{schema_path.name} missing token_budget block"
    budget = doc["token_budget"]
    assert isinstance(budget["soft"], int) and budget["soft"] > 0
    assert isinstance(budget["hard"], int) and budget["hard"] > budget["soft"]


@pytest.mark.parametrize("schema_path", ARTIFACT_SCHEMA_FILES, ids=lambda p: p.name)
def test_artifact_schema_invariants_list_nonempty(schema_path: Path) -> None:
    """Every artifact schema documents lifecycle invariants."""
    doc = _load_yaml(schema_path)
    assert "invariants" in doc, f"{schema_path.name} missing invariants list"
    assert isinstance(doc["invariants"], list)
    assert len(doc["invariants"]) >= 3, (
        f"{schema_path.name} invariants list is too short (< 3 entries)"
    )


def test_workspace_quartet_rules_referenced_somewhere() -> None:
    """Each of S-8, S-9, C-9, A-4 is referenced by at least one schema (so the rules
    layer integration is wired)."""
    referencing: dict[str, set[str]] = {"S-8": set(), "S-9": set(), "C-9": set(), "A-4": set()}
    for path in ARTIFACT_SCHEMA_FILES:
        doc = _load_yaml(path)
        rules = doc.get("governing_rules", [])
        for rule in rules:
            if rule in referencing:
                referencing[rule].add(doc["schema_name"])
    for rule, schemas_with_rule in referencing.items():
        assert schemas_with_rule, f"rule {rule} not referenced by any artifact schema"


def test_change_id_pattern_consistency() -> None:
    """Every schema that references a change-id uses the SAME regex pattern."""
    expected_pattern = "^[a-z0-9][a-z0-9.-]*[a-z0-9]$"
    for path in ARTIFACT_SCHEMA_FILES:
        doc = _load_yaml(path)
        for raw in (doc.get("instance_path_template", ""),):
            if "<change-id>" in raw:
                # Find the change-id field constraint somewhere in the schema.
                for top_key in ("frontmatter", "fields"):
                    fields = doc.get(top_key, {}).get("fields", {})
                    for fname in ("id", "parent", "change_id"):
                        if fname in fields and "pattern" in fields[fname]:
                            actual = fields[fname]["pattern"]
                            assert actual == expected_pattern, (
                                f"{path.name}::{top_key}.fields.{fname} has"
                                f" divergent change-id pattern: {actual!r}"
                            )


def test_handoff_envelope_examples_parse_as_yaml() -> None:
    """Each of the 3 worked examples in handoff-envelope.yaml is itself valid YAML."""
    doc = _load_yaml(SCHEMA_DIR / "handoff-envelope.yaml")
    for kind, raw in doc["examples"].items():
        parsed = yaml.safe_load(raw)
        assert isinstance(parsed, dict), f"example {kind} did not parse to mapping"
        # Validate via our discriminator validator.
        errors = _validate_envelope(parsed)
        assert not errors, f"example {kind} is itself invalid: {errors}"


def test_change_status_example_parses_and_validates() -> None:
    """The worked example in change-status.yaml validates against its own schema."""
    doc = _load_yaml(SCHEMA_DIR / "change-status.yaml")
    parsed = yaml.safe_load(doc["example"])
    assert isinstance(parsed, dict)
    errors = _validate_status_instance(parsed)
    assert not errors, f"change-status example is itself invalid: {errors}"


# =============================================================================
# Final sanity — overall count + repo-state cleanliness
# =============================================================================


def _index_declared_schema_count() -> int:
    """Schema count declared by the owning SSOT — the index `schemas:` list.

    `schemas/agent-workspace/__init__.yaml` states "every schema listed here
    MUST exist as a file in this directory"; deriving the count from it (per
    v14.2.1 G-028) means a legitimate addition updates ONE registry instead
    of breaking stale hardcoded count pins.
    """
    index = _load_yaml(SCHEMA_DIR / "__init__.yaml")
    return len(index["schemas"])


def test_total_schema_count_matches_index() -> None:
    """On-disk file count == index-declared artifact count + 1 (the index)."""
    declared = _index_declared_schema_count()
    files = sorted(p for p in SCHEMA_DIR.iterdir() if p.is_file() and p.suffix == ".yaml")
    assert len(files) == declared + 1, (
        f"expected {declared + 1} schema files (index + {declared} declared "
        f"in __init__.yaml `schemas:`), got {len(files)}"
    )


def test_artifact_schema_count_matches_index() -> None:
    """On-disk artifact schemas (excluding the index) == index declaration."""
    declared = _index_declared_schema_count()
    artifact_count = sum(
        1
        for p in SCHEMA_DIR.iterdir()
        if p.is_file() and p.suffix == ".yaml" and p.name != "__init__.yaml"
    )
    assert artifact_count == declared, (
        f"expected {declared} artifact schemas (per __init__.yaml `schemas:`), got {artifact_count}"
    )


def test_all_schema_names_unique(schemas: dict[str, dict[str, Any]]) -> None:
    """No two schemas share a schema_name."""
    names = [s["schema_name"] for s in schemas.values()]
    assert len(names) == len(set(names)), f"duplicate schema_name detected: {names}"
