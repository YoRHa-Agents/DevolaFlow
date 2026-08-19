"""Tests for v12.5.0 PV-04 D-1.2 — codegraph workflow wiring.

Pins the codegraph integration surfaces in:

* ``workflow-system/agent/templates/builtin/repo-init.yaml`` — analyze
  stage gains ``codegraph_commands`` hint; scaffold stage gains
  ``codegraph_init`` sub-step (runs in ALL modes per locked operator
  decision); verify stage gains ``codegraph_smoke`` presence check.
* the 3 sister templates (onboarding / security-audit /
  product-verification) — analyze-stage ``codegraph_commands`` recipes.
  v15.0.0 update (v15-ADR-002 Phase B): the sister yamls were deleted;
  the recipes are carried over verbatim as ``params.codegraph_commands``
  on the corresponding composition entries in
  ``workflow-system/agent/templates/registry.yaml#compositions``.
* ``workflow-system/agent/context_profiles.yaml`` — NEW
  ``meta.codegraph_integration`` block parallel to ``nines_integration``
  with 5 commands recipes + 6 triggers.

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

_REPO_ROOT: Path = Path(__file__).resolve().parent.parent
_TEMPLATES_DIR: Path = _REPO_ROOT / "workflow-system" / "agent" / "templates" / "builtin"
_REPO_INIT_PATH: Path = _TEMPLATES_DIR / "repo-init.yaml"
_REGISTRY_PATH: Path = _REPO_ROOT / "workflow-system" / "agent" / "templates" / "registry.yaml"
_CONTEXT_PROFILES_PATH: Path = _REPO_ROOT / "workflow-system" / "agent" / "context_profiles.yaml"


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
        template = _load_yaml(_REPO_INIT_PATH)
        analyze = _find_stage(template, "analyze")
        cfg = analyze.get("config") or {}
        codegraph_commands = cfg.get("codegraph_commands") or {}
        assert "status" in codegraph_commands, (
            "v12.5.0 PV-04 D-1.2: repo-init.analyze.config.codegraph_commands "
            "missing the `status` recipe."
        )
        assert "files" in codegraph_commands

    def test_scaffold_stage_has_codegraph_init(self) -> None:
        template = _load_yaml(_REPO_INIT_PATH)
        scaffold = _find_stage(template, "scaffold")
        cfg = scaffold.get("config") or {}
        codegraph_init = cfg.get("codegraph_init") or {}
        assert codegraph_init.get("cmd") == "codegraph init {project_root}"
        assert codegraph_init.get("on_failure") == "warn", (
            "v12.5.0 PV-04 D-1.2: codegraph_init.on_failure must be "
            "'warn' per S-5 explicit warn + continue (NEVER block scaffold)."
        )
        gitignore_targets = codegraph_init.get("add_to_gitignore") or []
        assert ".codegraph/" in gitignore_targets, (
            "v12.5.0 PV-04 D-1.2: codegraph_init.add_to_gitignore must "
            "include '.codegraph/' so the project-local index does not "
            "leak into git."
        )

    def test_scaffold_codegraph_init_runs_in_all_modes(self) -> None:
        """Per locked operator decision 2026-05-23: codegraph_init has NO mode gate.

        The scaffold stage has no skip_condition (runs in all modes), and
        the codegraph_init sub-step inherits that — codegraph footprint
        is small enough that even mode=core users get the index for the
        downstream analyze workflows' efficiency gains.
        """
        template = _load_yaml(_REPO_INIT_PATH)
        scaffold = _find_stage(template, "scaffold")
        # Scaffold itself MUST not have a skip_condition that gates by mode.
        assert "skip_condition" not in scaffold, (
            "v12.5.0 PV-04 D-1.2: repo-init.scaffold MUST NOT carry a "
            "skip_condition (the codegraph_init sub-step runs in all modes)."
        )

    def test_verify_stage_has_codegraph_smoke(self) -> None:
        template = _load_yaml(_REPO_INIT_PATH)
        verify = _find_stage(template, "verify")
        cfg = verify.get("config") or {}
        codegraph_smoke = cfg.get("codegraph_smoke") or {}
        assert codegraph_smoke.get("path") == ".codegraph/codegraph.db"
        assert codegraph_smoke.get("on_missing") == "warn", (
            "v12.5.0 PV-04 D-1.2: codegraph_smoke.on_missing must be "
            "'warn' (NOT 'fail') so codegraph install / network failures "
            "do not break repo-init verification altogether."
        )

    def test_verify_stage_skip_condition_unchanged(self) -> None:
        """The verify stage's mode=full gate is preserved verbatim."""
        template = _load_yaml(_REPO_INIT_PATH)
        verify = _find_stage(template, "verify")
        assert verify.get("skip_condition") == "mode != 'full'"


# ---------------------------------------------------------------------------
# Sister compositions — params carry codegraph_commands (v15-ADR-002)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("composition_name", "expected_recipes"),
    [
        ("onboarding", {"entry_points", "files"}),
        ("security-audit", {"callers", "impact"}),
        ("product-verification", {"explore", "impact"}),
    ],
)
def test_sister_template_analyze_has_codegraph_commands(
    composition_name: str, expected_recipes: set[str]
) -> None:
    """The 3 sister names (onboarding/security-audit/product-verification) keep codegraph wiring.

    Their yamls were deleted at v15.0.0 (v15-ADR-002 Phase B); the
    v12.5.0 PV-04 D-1.2 recipes are carried over verbatim as
    ``params.codegraph_commands`` on the composition entries.
    """
    registry = _load_yaml(_REGISTRY_PATH)
    entry = next(c for c in registry["compositions"] if c["name"] == composition_name)
    codegraph_commands = (entry.get("params") or {}).get("codegraph_commands") or {}
    missing = expected_recipes - set(codegraph_commands.keys())
    assert not missing, (
        f"v12.5.0 PV-04 D-1.2 (carried per v15-ADR-002): composition "
        f"{composition_name!r} missing codegraph recipes {sorted(missing)}; "
        f"got {sorted(codegraph_commands.keys())}"
    )


# ---------------------------------------------------------------------------
# context_profiles.yaml — meta.codegraph_integration block
# ---------------------------------------------------------------------------


class TestContextProfilesCodegraphIntegration:
    def test_codegraph_integration_block_present(self) -> None:
        payload = _load_yaml(_CONTEXT_PROFILES_PATH)
        meta = payload.get("meta") or {}
        block = meta.get("codegraph_integration")
        assert block is not None, (
            "v12.5.0 PV-04 D-1.2: context_profiles.yaml missing "
            "meta.codegraph_integration block (parallel to nines_integration)."
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

    def test_nines_integration_block_unchanged(self) -> None:
        """Sibling block byte-stable — codegraph wiring is purely additive."""
        payload = _load_yaml(_CONTEXT_PROFILES_PATH)
        meta = payload.get("meta") or {}
        nines = meta.get("nines_integration")
        assert nines is not None
        assert nines.get("auto_detect") is True
        # Spot-check a known recipe to ensure the codegraph addition did
        # not perturb the nines block.
        commands = nines.get("commands") or {}
        assert "self_eval" in commands
