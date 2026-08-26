"""Registry-v3 checklist seed corpus and compatibility alias contracts."""

from __future__ import annotations

import copy
import logging
import warnings
from pathlib import Path

import pytest
import yaml

from devolaflow.template_engine.compositions import (
    CompositionEntry,
    CompositionManifestError,
    CompositionStep,
    load_composition_manifest,
)
from devolaflow.template_engine.registry import (
    ChecklistSeedAliasWarning,
    TemplateRegistry,
)
from devolaflow.template_engine.seeds import (
    REGISTRY_SCHEMA_V3,
    ChecklistSeedError,
    load_checklist_seed,
    load_seed_registry,
)
from devolaflow.template_engine.validator import validate_all_templates

_REPO_ROOT = Path(__file__).resolve().parent.parent
_TEMPLATES_ROOT = _REPO_ROOT / "workflow-system" / "agent" / "templates"
_REGISTRY_YAML = _TEMPLATES_ROOT / "registry.yaml"

_SOURCE_STAGE_SEQUENCES: dict[str, list[tuple[str, str]]] = {
    "change-driven": [
        ("propose", "design"),
        ("apply", "implement"),
        ("verify", "verify"),
        ("archive", "deploy"),
    ],
    "migration": [
        ("assessment", "analyze"),
        ("plan", "plan"),
        ("implement", "implement"),
        ("validate", "validate"),
        ("cutover", "deploy"),
    ],
    "nines-assisted": [
        ("precondition", "implement"),
        ("research", "research"),
        ("design", "design"),
        ("plan", "plan"),
        ("impl", "implement"),
        ("review", "review"),
        ("test", "test"),
        ("refine", "refine"),
        ("validate", "validate"),
        ("release", "release"),
    ],
    "repo-init": [
        ("analyze", "analyze"),
        ("scaffold", "implement"),
        ("compile", "implement"),
        ("interview", "analyze"),
        ("verify", "verify"),
    ],
    "self-update": [
        ("check-refs", "analyze"),
        ("research-updates", "research"),
        ("decompose", "design"),
        ("integrate", "implement"),
        ("si_chip_gate", "validate"),
        ("test", "test"),
        ("self-improve", "validate"),
        ("evaluate", "validate"),
    ],
    "skill-optimization": [
        ("survey", "research"),
        ("profile", "analyze"),
        ("optimize", "implement"),
        ("si_chip_dogfood", "validate"),
        ("benchmark", "test"),
        ("document", "release"),
    ],
    "web-design": [
        ("design", "design"),
        ("implement", "implement"),
        ("refine", "refine"),
        ("verify", "verify"),
    ],
    "hotfix": [
        ("bug_triage", "analyze"),
        ("fix", "implement"),
        ("test", "test"),
        ("release", "release"),
    ],
    "research-only": [
        ("research", "research"),
        ("compare", "analyze"),
        ("report", "validate"),
    ],
    "design-only": [
        ("research", "research"),
        ("design", "design"),
        ("review", "review"),
    ],
    "documentation-only": [
        ("survey", "research"),
        ("author", "implement"),
        ("review", "review"),
    ],
    "spike-poc": [
        ("research", "research"),
        ("prototype", "implement"),
        ("evaluate", "validate"),
    ],
    "refactoring": [
        ("scope_analysis", "analyze"),
        ("plan", "plan"),
        ("implement", "implement"),
        ("test", "test"),
        ("review", "review"),
    ],
    "feature-enhancement": [
        ("scope", "analyze"),
        ("design", "design"),
        ("plan", "plan"),
        ("implement", "implement"),
        ("review", "review"),
        ("test", "test"),
        ("release", "release"),
    ],
    "full-pipeline": [
        ("design", "design"),
        ("plan", "plan"),
        ("impl", "implement"),
        ("review", "review"),
        ("test", "test"),
        ("verify", "verify"),
        ("refine", "refine"),
        ("testgate", "validate"),
        ("release", "release"),
    ],
    "performance-optimization": [
        ("profile", "analyze"),
        ("design", "design"),
        ("optimize", "implement"),
        ("benchmark", "test"),
        ("validate", "validate"),
    ],
    "security-audit": [
        ("threat_model", "research"),
        ("scan", "analyze"),
        ("analyze", "analyze"),
        ("remediate", "implement"),
        ("verify", "validate"),
    ],
    "research-design-review-refine": [
        ("research", "research"),
        ("design", "design"),
        ("review", "review"),
        ("refine", "refine"),
        ("knowledge_gap_research", "research"),
    ],
    "dependency-setup": [
        ("research", "research"),
        ("plan", "plan"),
        ("configure", "implement"),
        ("verify", "test"),
    ],
    "onboarding": [
        ("analyze", "analyze"),
        ("document", "implement"),
        ("setup", "implement"),
        ("verify", "test"),
    ],
    "demo-showcase": [
        ("research", "research"),
        ("design", "design"),
        ("build", "implement"),
        ("review", "review"),
        ("refine", "refine"),
        ("package", "release"),
    ],
    "product-verification": [
        ("precondition", "implement"),
        ("analyze", "analyze"),
        ("design_tests", "design"),
        ("implement_tests", "implement"),
        ("execute_dev_tests", "test"),
        ("execute_verification", "verify"),
        ("review_results", "review"),
        ("refine", "refine"),
        ("validate", "validate"),
    ],
    "entropy-cleanup": [
        ("scan", "analyze"),
        ("propose", "design"),
        ("review", "review"),
        ("apply", "implement"),
    ],
    "harness-construction": [
        ("survey", "research"),
        ("capability_map", "analyze"),
        ("gap_analysis", "analyze"),
        ("build_infra", "implement"),
        ("refine_infra", "refine"),
        ("capability_review", "validate"),
        ("verify_delta", "verify"),
    ],
}

_ALIASES = sorted(set(_SOURCE_STAGE_SEQUENCES) - {"change-driven"})


@pytest.mark.parametrize("name", sorted(_SOURCE_STAGE_SEQUENCES))
def test_registry_schema_v3_and_seed_stage_provenance(name: str) -> None:
    raw = yaml.safe_load(_REGISTRY_YAML.read_text(encoding="utf-8"))
    assert raw["schema_version"] == REGISTRY_SCHEMA_V3
    assert list(raw)[-1] == "templates"
    assert len(raw["compositions"]) == 17
    assert len(raw["templates"]) == 7
    assert all(
        set(entry) == {"name", "seed", "category", "tags", "description"}
        for entry in raw["compositions"]
    )
    assert sum("path" in entry for entry in raw["templates"]) == 1
    assert next(entry for entry in raw["templates"] if "path" in entry)["name"] == "change-driven"

    manifest = load_seed_registry(_REGISTRY_YAML)
    assert set(manifest) == set(_SOURCE_STAGE_SEQUENCES)
    registry = TemplateRegistry(_TEMPLATES_ROOT)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        seed = registry.load_seed(name)
    assert seed is not None
    assert seed.metadata.name == name
    assert seed.source_stage_sequence() == _SOURCE_STAGE_SEQUENCES[name]


@pytest.mark.parametrize("name", _ALIASES)
def test_seed_alias_resolution_warns_once_and_clones_runtime(
    name: str, caplog: pytest.LogCaptureFixture
) -> None:
    registry = TemplateRegistry(_TEMPLATES_ROOT)
    expected = (
        f"TemplateRegistry.load_template('{name}') is deprecated for checklist "
        f"seed '{name}' since v16.0.0; returning the 'change-driven' "
        "checklist-round runtime with seed metadata attached. Use "
        f"load_seed('{name}') and load_template('change-driven'); this "
        "compatibility alias is scheduled for removal in v17.0.0."
    )
    caplog.set_level(logging.WARNING)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        first = registry.load_template(name)
        second = registry.load_template(name)
    assert first is second
    assert first is not None
    assert [warning.category for warning in caught] == [ChecklistSeedAliasWarning]
    assert str(caught[0].message) == expected
    assert [record.message for record in caplog.records if record.message == expected] == [expected]
    assert first.metadata.name == name
    assert [stage.id for stage in first.stages] == ["propose", "preflight", "round", "archive"]
    assert "composition" not in first.parameters
    assert first.parameters["checklist_seed"] == {
        "name": name,
        "path": f"seeds/{name}.yaml",
        "runtime": "change-driven",
        "compatibility_alias": True,
    }


def test_runtime_discovery_validator_and_legacy_failure(
    capsys: pytest.CaptureFixture[str],
) -> None:
    registry = TemplateRegistry(_TEMPLATES_ROOT)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        runtime = registry.load_template("change-driven")
        assert registry.load_template("unknown-mode") is None
        assert registry.load_seed("unknown-mode") is None
        discovered = registry.discover()
    assert runtime is not None
    assert runtime.metadata.name == "change-driven"
    assert "checklist_seed" not in runtime.parameters
    assert {metadata.name for metadata in discovered} == set(_SOURCE_STAGE_SEQUENCES)
    with pytest.raises(CompositionManifestError, match="synthesis is retired"):
        load_composition_manifest(_REGISTRY_YAML)
    with pytest.raises(CompositionManifestError, match="synthesis is retired"):
        registry.compositions()
    legacy = CompositionEntry(name="legacy", steps=(CompositionStep(base="change-driven"),))
    assert legacy.primary_base == "change-driven"
    assert legacy.stage_sequence() == []
    assert "synthesis is retired" in legacy.deprecation_note()
    assert validate_all_templates(True, _TEMPLATES_ROOT / "builtin")
    assert "1 template + 24 seeds" in capsys.readouterr().out


def test_malformed_seed_and_registry_fail_loudly(tmp_path: Path) -> None:
    valid = yaml.safe_load(
        (_TEMPLATES_ROOT / "seeds" / "change-driven.yaml").read_text(encoding="utf-8")
    )
    mutations = [
        lambda raw: raw.update(schema_version="2.0"),
        lambda raw: raw.update(kind="workflow"),
        lambda raw: raw.update(stages=[]),
        lambda raw: raw["metadata"].update(name="Bad Name"),
        lambda raw: raw["metadata"].update(version="1"),
        lambda raw: raw["metadata"].update(category="unknown"),
        lambda raw: raw["metadata"].update(intent_keywords=[]),
        lambda raw: raw["metadata"].update(intent_keywords=["x", "x"]),
        lambda raw: raw["metadata"]["source"].update(kind="runtime"),
        lambda raw: raw["metadata"]["source"].update(name="other"),
        lambda raw: raw["metadata"]["source"].update(path="/absolute"),
        lambda raw: raw.update(placeholders={"Bad-Key": {"description": "x", "required": True}}),
        lambda raw: raw.update(placeholders={"x": {"description": "x", "required": "yes"}}),
        lambda raw: raw.update(partitions=[]),
        lambda raw: raw["partitions"][0].update(key="Bad Key"),
        lambda raw: raw["partitions"][0].update(source_stages=[]),
        lambda raw: raw["partitions"][0]["source_stages"][0].update(primitive="execute"),
        lambda raw: raw["partitions"][0].update(assertions=[]),
        lambda raw: raw["partitions"][0]["assertions"][0].update(suggested_priority="P3"),
        lambda raw: raw["partitions"][0]["assertions"][0].update(verify={"mode": "command"}),
        lambda raw: raw["partitions"][0]["assertions"][0].update(
            statement_template="{{ missing }}"
        ),
    ]
    for mutate in mutations:
        malformed = copy.deepcopy(valid)
        mutate(malformed)
        path = tmp_path / "change-driven.yaml"
        path.write_text(yaml.safe_dump(malformed), encoding="utf-8")
        with pytest.raises(ChecklistSeedError):
            load_checklist_seed(path)

    with pytest.raises(ChecklistSeedError, match="not found"):
        load_checklist_seed(tmp_path / "missing.yaml")
    bad_registry = tmp_path / "registry.yaml"
    bad_registry.write_text('schema_version: "2.0"\n', encoding="utf-8")
    with pytest.raises(ChecklistSeedError, match="requires schema_version"):
        load_seed_registry(bad_registry)
    assert load_composition_manifest(tmp_path / "missing-registry.yaml") == {}
    bad_registry.write_text("- not-a-mapping\n", encoding="utf-8")
    with pytest.raises(CompositionManifestError, match="root must be a mapping"):
        load_composition_manifest(bad_registry)
    with pytest.raises(CompositionManifestError, match="no steps"):
        _ = CompositionEntry(name="empty", steps=()).primary_base
    bad_registry.write_text(
        'schema_version: "2.0"\ncompositions:\n  - name: old\n',
        encoding="utf-8",
    )
    with pytest.raises(CompositionManifestError, match="synthesis is retired"):
        load_composition_manifest(bad_registry)
