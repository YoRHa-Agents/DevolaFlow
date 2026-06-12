"""v15.0.0 Phase B collapse — composition manifest + alias-layer contract.

Pins the `v15-ADR-002` execution (template registry 23 → 7 survivors +
16 named compositions, registry schema v1.0 → v2.0):

1. The survivor set is EXACTLY the 7 yamls ratified by the ADR
   (decision 1, per product review §2.1).
2. registry.yaml carries schema v2.0 and a 16-entry `compositions:`
   manifest that cross-validates cleanly.
3. Every collapsed id resolves through the loader to a template
   synthesized from the manifest's C-3 VERBATIM stage sequence (the
   deleted yaml's `stages:` order, byte-equal ids + primitives).
4. Alias resolution emits a DeprecationWarning (ADR decision 3 — no
   silent rewrite; aliases guaranteed until at least v16.0.0); survivor
   loads stay warning-free.
5. `validate-template --all` walks templates + compositions with
   derived (floating) counts.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest
import yaml

from devolaflow.template_engine.compositions import (
    REGISTRY_SCHEMA_V2,
    load_composition_manifest,
    validate_composition_manifest,
)
from devolaflow.template_engine.registry import TemplateRegistry
from devolaflow.template_engine.validator import validate_all_templates

_REPO_ROOT = Path(__file__).resolve().parent.parent
_TEMPLATES_ROOT = _REPO_ROOT / "workflow-system" / "agent" / "templates"
_REGISTRY_YAML = _TEMPLATES_ROOT / "registry.yaml"

# v15-ADR-002 decision 1 — the ratified survivor set (product review §2.1).
_ADR_002_SURVIVORS: frozenset[str] = frozenset(
    {
        "change-driven",
        "repo-init",
        "self-update",
        "skill-optimization",
        "migration",
        "web-design",
        "nines-assisted",
    }
)

# C-3 verbatim witness: stage-id → primitive sequences extracted from the
# deleted yamls at the pre-collapse tree (v14.5.0). The registry manifest
# AND the loader-synthesized templates must reproduce these byte-equal.
_VERBATIM_STAGE_SEQUENCES: dict[str, list[tuple[str, str]]] = {
    "hotfix": [
        ("bug_triage", "analyze"),
        ("fix", "implement"),
        ("test", "test"),
        ("release", "release"),
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
    "documentation-only": [
        ("survey", "research"),
        ("author", "implement"),
        ("review", "review"),
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
    "research-design-review-refine": [
        ("research", "research"),
        ("design", "design"),
        ("review", "review"),
        ("refine", "refine"),
        ("knowledge_gap_research", "research"),
    ],
    "spike-poc": [
        ("research", "research"),
        ("prototype", "implement"),
        ("evaluate", "validate"),
    ],
    "security-audit": [
        ("threat_model", "research"),
        ("scan", "analyze"),
        ("analyze", "analyze"),
        ("remediate", "implement"),
        ("verify", "validate"),
    ],
    "demo-showcase": [
        ("research", "research"),
        ("design", "design"),
        ("build", "implement"),
        ("review", "review"),
        ("refine", "refine"),
        ("package", "release"),
    ],
    "performance-optimization": [
        ("profile", "analyze"),
        ("design", "design"),
        ("optimize", "implement"),
        ("benchmark", "test"),
        ("validate", "validate"),
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
}


def test_survivor_set_exact_match() -> None:
    """v15-ADR-002 decision 1: the survivor set is EXACTLY the 7 ratified yamls."""
    on_disk = {p.stem for p in (_TEMPLATES_ROOT / "builtin").glob("*.yaml")}
    assert on_disk == _ADR_002_SURVIVORS, (
        f"Survivor yamls on disk {sorted(on_disk)} != the v15-ADR-002 "
        f"ratified set {sorted(_ADR_002_SURVIVORS)} (product review §2.1)"
    )
    raw = yaml.safe_load(_REGISTRY_YAML.read_text(encoding="utf-8"))
    registry_templates = {e["name"] for e in raw["templates"]}
    assert registry_templates == _ADR_002_SURVIVORS, (
        f"registry.yaml templates {sorted(registry_templates)} != the "
        f"v15-ADR-002 ratified survivor set"
    )


def test_registry_schema_v2_validates() -> None:
    """Schema v2.0 manifest: 16 cross-valid compositions, disjoint from templates."""
    raw = yaml.safe_load(_REGISTRY_YAML.read_text(encoding="utf-8"))
    assert raw["schema_version"] == REGISTRY_SCHEMA_V2, (
        f"registry.yaml schema_version {raw['schema_version']!r} != "
        f"{REGISTRY_SCHEMA_V2!r} (v15-ADR-002 v1.0 → v2.0 bump)"
    )
    manifest = load_composition_manifest(_REGISTRY_YAML)
    assert set(manifest) == set(_VERBATIM_STAGE_SEQUENCES), (
        "compositions manifest must carry exactly the 16 collapsed names"
    )
    errors = validate_composition_manifest(manifest, _ADR_002_SURVIVORS)
    assert not errors, f"compositions manifest invalid: {errors}"


@pytest.mark.parametrize("name", sorted(_VERBATIM_STAGE_SEQUENCES))
def test_composition_resolution_preserves_verbatim_stage_sequence(name: str) -> None:
    """C-3: each collapsed id resolves to its VERBATIM stage sequence.

    The loader synthesizes the resolved template from the manifest's
    `stages:` block — the deleted yaml's stage-id → primitive order must
    survive byte-equal so legacy behavior stays reproducible.
    """
    registry = TemplateRegistry(_TEMPLATES_ROOT)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        tpl = registry.load_template(name)
    assert tpl is not None, f"composition {name!r} did not resolve"
    assert tpl.metadata.name == name
    assert [(s.id, s.primitive) for s in tpl.stages] == _VERBATIM_STAGE_SEQUENCES[name], (
        f"composition {name!r} lost its C-3 verbatim stage sequence"
    )
    record = tpl.parameters["composition"]
    assert record["alias_of"] in _ADR_002_SURVIVORS, (
        f"composition {name!r} primary base {record['alias_of']!r} is not a survivor"
    )


@pytest.mark.parametrize("name", sorted(_VERBATIM_STAGE_SEQUENCES))
def test_alias_resolution_emits_deprecation_warning(name: str) -> None:
    """v15-ADR-002 decision 3: alias resolution warns, never errors."""
    registry = TemplateRegistry(_TEMPLATES_ROOT)  # fresh instance — no cache
    with pytest.warns(DeprecationWarning, match="v15-ADR-002"):
        tpl = registry.load_template(name)
    assert tpl is not None


@pytest.mark.parametrize("name", sorted(_ADR_002_SURVIVORS))
def test_survivor_load_emits_no_deprecation_warning(name: str) -> None:
    """Survivor templates load silently — the alias layer is operator-invisible."""
    registry = TemplateRegistry(_TEMPLATES_ROOT)
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        tpl = registry.load_template(name)
    assert tpl is not None
    assert "composition" not in tpl.parameters


def test_validate_all_templates_walks_compositions(capsys: pytest.CaptureFixture[str]) -> None:
    """`validate-template --all` derives floating counts from disk + manifest."""
    assert validate_all_templates(True, templates_root=_TEMPLATES_ROOT / "builtin") is True
    out = capsys.readouterr().out
    n_disk = len(list((_TEMPLATES_ROOT / "builtin").glob("*.yaml")))
    n_comp = len(load_composition_manifest(_REGISTRY_YAML))
    assert f"{n_disk} templates + {n_comp} compositions" in out, (
        f"validator summary must derive counts from disk + manifest; got: {out.splitlines()[-1]}"
    )
    for name in _VERBATIM_STAGE_SEQUENCES:
        assert f"PASS: composition {name}" in out
