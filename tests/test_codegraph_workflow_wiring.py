"""Tests for v12.5.0 PV-04 D-1.2 — codegraph workflow wiring.

Pins the codegraph integration surfaces in:

* registry-v3 checklist seeds — historical stage ids/primitives remain
  provenance only and materializable assertions retain codegraph intent;
* the codegraph reference — suggest-tier/background/marker behavior;
* ``workflow-system/agent/context_profiles.yaml`` — NEW
  ``meta.codegraph_integration`` block with 5 command recipes + 6 triggers.

Source: ``.local/research/v12.5.0_gap_analysis.md`` §2 D-1.2 +
``.local/research/v12.5.0_codegraph_benefit_analysis.md`` §3 surface 5
+ §6.2 PV-04 acceptance criteria; composition carry-over per
`docs/cycle-archive/adr/v15-ADR-002-template-phase-b-collapse.md`.

NO subprocess. NO network. Pure YAML structural assertions.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from devolaflow.template_engine.registry import TemplateRegistry

_REPO_ROOT: Path = Path(__file__).resolve().parent.parent
_TEMPLATES_DIR: Path = _REPO_ROOT / "workflow-system" / "agent" / "templates"
_CONTEXT_PROFILES_PATH: Path = _REPO_ROOT / "workflow-system" / "agent" / "context_profiles.yaml"
_CODEGRAPH_REFERENCE_PATH = _REPO_ROOT / "workflow-system/agent/references/codegraph.md"


def _load_yaml(path: Path) -> dict:
    """Load + parse a YAML file (cached per-call; cheap)."""
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _find_stage(template: dict, stage_id: str) -> dict:
    """Locate the stage with ``id == stage_id`` in a workflow template payload."""
    for stage in template.get("stages", []) or []:
        if isinstance(stage, dict) and stage.get("id") == stage_id:
            return stage
    raise LookupError(
        f"Stage {stage_id!r} not found in template; "
        f"available IDs: {[s.get('id') for s in template.get('stages', [])]}"
    )


# ---------------------------------------------------------------------------
# repo-init.yaml — analyze + scaffold + verify gain codegraph surfaces
# ---------------------------------------------------------------------------


class TestRepoInitCodegraphWiring:
    def test_analyze_stage_has_codegraph_commands(self) -> None:
        seed = TemplateRegistry(_TEMPLATES_DIR).load_seed("repo-init")
        assert seed is not None
        assert ("analyze", "analyze") in seed.source_stage_sequence()
        assert any(
            "codegraph availability" in assertion.statement_template
            for partition in seed.partitions
            for assertion in partition.assertions
        )

    def test_scaffold_stage_has_codegraph_init(self) -> None:
        seed = TemplateRegistry(_TEMPLATES_DIR).load_seed("repo-init")
        assert seed is not None
        assert ("scaffold", "implement") in seed.source_stage_sequence()
        reference = _CODEGRAPH_REFERENCE_PATH.read_text(encoding="utf-8")
        assert "suggest-tier, backgrounded" in reference
        assert ".codegraph/" in reference

    def test_scaffold_stage_has_no_mode_gate(self) -> None:
        """The seed carries no runtime gate or skip condition."""
        seed = TemplateRegistry(_TEMPLATES_DIR).load_seed("repo-init")
        assert seed is not None
        assert not hasattr(seed, "skip_condition")
        assert not hasattr(seed, "gates")

    def test_scaffold_codegraph_init_is_suggest_tier_background(self) -> None:
        """Track C-3 behavior remains explicit outside the non-executable seed."""
        reference = _CODEGRAPH_REFERENCE_PATH.read_text(encoding="utf-8")
        for literal in (
            "tier: suggest",
            "execution: background",
            "command -v codegraph",
            ".codegraph/.indexing",
            ".codegraph/.ready",
            ".codegraph/.failed",
        ):
            assert literal in reference

    def test_verify_stage_has_codegraph_smoke(self) -> None:
        seed = TemplateRegistry(_TEMPLATES_DIR).load_seed("repo-init")
        assert seed is not None
        assert ("verify", "verify") in seed.source_stage_sequence()
        statement = next(
            assertion.statement_template
            for partition in seed.partitions
            for assertion in partition.assertions
            if assertion.key == "initialization-verified"
        )
        assert "degraded optional tooling" in statement

    def test_verify_stage_skip_condition_unchanged(self) -> None:
        """No executable mode gate is inferred from verify provenance."""
        seed = TemplateRegistry(_TEMPLATES_DIR).load_seed("repo-init")
        assert seed is not None
        assert not hasattr(seed, "skip_condition")


# ---------------------------------------------------------------------------
# Sister seeds — codegraph intent plus source-stage provenance
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("composition_name", "expected_recipes"),
    [
        ("onboarding", {"analyze"}),
        ("security-audit", {"analyze"}),
        ("product-verification", {"analyze"}),
    ],
)
def test_sister_template_analyze_has_codegraph_commands(
    composition_name: str, expected_recipes: set[str]
) -> None:
    """Sister seeds keep codegraph intent without executable recipes."""
    seed = TemplateRegistry(_TEMPLATES_DIR).load_seed(composition_name)
    assert seed is not None
    provenance_ids = {stage_id for stage_id, _ in seed.source_stage_sequence()}
    assert expected_recipes <= provenance_ids
    assert any(
        "codegraph" in assertion.statement_template.lower()
        for partition in seed.partitions
        for assertion in partition.assertions
    )
    assert not hasattr(seed, "composition")


# ---------------------------------------------------------------------------
# context_profiles.yaml — meta.codegraph_integration block
# ---------------------------------------------------------------------------


class TestContextProfilesCodegraphIntegration:
    def test_codegraph_integration_block_present(self) -> None:
        payload = _load_yaml(_CONTEXT_PROFILES_PATH)
        meta = payload.get("meta") or {}
        block = meta.get("codegraph_integration")
        assert block is not None, (
            "v12.5.0 PV-04 D-1.2: context_profiles.yaml missing meta.codegraph_integration block."
        )
        assert block.get("auto_detect") is True
        assert "install_hint" in block
        assert "plugin_registry" in block

    def test_codegraph_integration_commands(self) -> None:
        payload = _load_yaml(_CONTEXT_PROFILES_PATH)
        block = payload["meta"]["codegraph_integration"]
        commands = block.get("commands") or {}
        for recipe_name in ("repo_init", "analyze", "research", "impact", "affected"):
            assert recipe_name in commands, (
                f"v12.5.0 PV-04 D-1.2: codegraph_integration.commands "
                f"missing recipe {recipe_name!r}; per the cycle plan §PV-04 "
                "the block MUST declare 5 recipes."
            )

    def test_codegraph_integration_triggers(self) -> None:
        payload = _load_yaml(_CONTEXT_PROFILES_PATH)
        block = payload["meta"]["codegraph_integration"]
        triggers = block.get("triggers") or []
        expected = {
            "smart_context_building",
            "full_text_search",
            "impact_analysis",
            "callers_callees_trace",
            "file_structure_lookup",
            "test_impact_selection",
        }
        missing = expected - set(triggers)
        assert not missing, (
            f"v12.5.0 PV-04 D-1.2: codegraph_integration.triggers missing "
            f"{sorted(missing)}; expected the 6 capability triggers from "
            "plugins.yaml::plugins.codegraph.capabilities."
        )
