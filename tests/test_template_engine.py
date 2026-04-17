"""Comprehensive tests for the workflow template engine.

Covers:
  - Parsing the 3 example templates (research-only, hotfix, full-pipeline)
  - Each composition operator type
  - All 7 validation checks (positive + negative)
  - Registry discovery
  - Template inheritance
"""

from __future__ import annotations

from pathlib import Path

import pytest

from devolaflow.template_engine.composer import collect_stage_refs
from devolaflow.template_engine.inheritance import InheritanceError, resolve_inheritance
from devolaflow.template_engine.models import (
    VALID_PRIMITIVES,
    Break,
    Choice,
    GateRef,
    LoopRef,
    Parallel,
    Sequence,
    StageRef,
    WorkflowTemplate,
)
from devolaflow.template_engine.parser import (
    TemplateParseError,
    parse_composition,
    parse_template,
    parse_template_string,
)
from devolaflow.template_engine.registry import TemplateRegistry
from devolaflow.template_engine.validator import (
    check_dependency_lattice,
    check_gate_completeness,
    check_loop_termination,
    check_no_orphan_stages,
    check_reachability,
    check_schema_conformance,
    check_stage_reference_integrity,
    validate_template,
)

FIXTURES = Path(__file__).parent / "fixtures"


# ═══════════════════════════════════════════════════════════════════
# §1  Parsing — 3 example templates
# ═══════════════════════════════════════════════════════════════════


class TestParseResearchOnly:
    @pytest.fixture()
    def template(self) -> WorkflowTemplate:
        return parse_template(FIXTURES / "research_only.yaml")

    def test_metadata(self, template: WorkflowTemplate) -> None:
        assert template.metadata.name == "research-only"
        assert template.metadata.version == "1.0.0"
        assert template.metadata.category == "discover"
        assert "research" in template.metadata.tags

    def test_stages(self, template: WorkflowTemplate) -> None:
        ids = template.stage_ids()
        assert ids == {"research", "compare", "report"}

    def test_stage_primitives(self, template: WorkflowTemplate) -> None:
        stage_map = {s.id: s.primitive for s in template.stages}
        assert stage_map["research"] == "research"
        assert stage_map["compare"] == "analyze"
        assert stage_map["report"] == "validate"

    def test_alias(self, template: WorkflowTemplate) -> None:
        compare = template.stage_by_id("compare")
        assert compare is not None
        assert compare.alias == "compare"

    def test_composition_is_sequence(self, template: WorkflowTemplate) -> None:
        assert isinstance(template.composition, Sequence)

    def test_loop_definition(self, template: WorkflowTemplate) -> None:
        assert len(template.loops) == 1
        loop = template.loops[0]
        assert loop.name == "knowledge_loop"
        assert loop.body_stages == ["research", "compare"]
        assert loop.max_iterations == 3
        assert loop.on_exhaustion == "continue"

    def test_validates_clean(self, template: WorkflowTemplate) -> None:
        result = validate_template(template)
        assert result.valid, result.errors


class TestParseHotfix:
    @pytest.fixture()
    def template(self) -> WorkflowTemplate:
        return parse_template(FIXTURES / "hotfix.yaml")

    def test_metadata(self, template: WorkflowTemplate) -> None:
        assert template.metadata.name == "hotfix"
        assert template.metadata.category == "build"

    def test_stages(self, template: WorkflowTemplate) -> None:
        assert template.stage_ids() == {"bug_triage", "fix", "test", "release"}

    def test_gate_defined(self, template: WorkflowTemplate) -> None:
        assert len(template.gates) == 1
        assert template.gates[0].name == "severity_gate"
        assert len(template.gates[0].criteria) == 2

    def test_loop(self, template: WorkflowTemplate) -> None:
        assert len(template.loops) == 1
        assert template.loops[0].name == "test_fix_loop"

    def test_validates_clean(self, template: WorkflowTemplate) -> None:
        result = validate_template(template)
        assert result.valid, result.errors


class TestParseFullPipeline:
    @pytest.fixture()
    def template(self) -> WorkflowTemplate:
        return parse_template(FIXTURES / "full_pipeline.yaml")

    def test_metadata(self, template: WorkflowTemplate) -> None:
        assert template.metadata.name == "full-pipeline"
        assert template.metadata.category == "composite"

    def test_stages(self, template: WorkflowTemplate) -> None:
        expected = {"design", "plan", "impl", "review", "test", "refine", "testgate", "release"}
        assert template.stage_ids() == expected

    def test_multiple_loops(self, template: WorkflowTemplate) -> None:
        assert len(template.loops) == 3
        loop_names = {lp.name for lp in template.loops}
        assert loop_names == {"impl_cycle", "review_refine", "test_fix"}

    def test_multiple_gates(self, template: WorkflowTemplate) -> None:
        assert len(template.gates) == 2
        gate_names = {g.name for g in template.gates}
        assert gate_names == {"design_gate", "release_gate"}

    def test_gate_criteria(self, template: WorkflowTemplate) -> None:
        release_gate = next(g for g in template.gates if g.name == "release_gate")
        assert len(release_gate.criteria) == 3
        assert release_gate.require_human_override is True

    def test_validates_clean(self, template: WorkflowTemplate) -> None:
        result = validate_template(template)
        assert result.valid, result.errors


# ═══════════════════════════════════════════════════════════════════
# §2  Composition operator parsing
# ═══════════════════════════════════════════════════════════════════


class TestCompositionOperators:
    def test_stage_ref(self) -> None:
        node = parse_composition({"stage": "design"})
        assert isinstance(node, StageRef)
        assert node.stage == "design"

    def test_stage_ref_string(self) -> None:
        node = parse_composition("design")
        assert isinstance(node, StageRef)
        assert node.stage == "design"

    def test_sequence(self) -> None:
        node = parse_composition(
            {
                "compose": "sequence",
                "stages": [{"stage": "a"}, {"stage": "b"}, {"stage": "c"}],
            }
        )
        assert isinstance(node, Sequence)
        assert len(node.stages) == 3
        assert all(isinstance(s, StageRef) for s in node.stages)

    def test_parallel_all(self) -> None:
        node = parse_composition(
            {
                "compose": "parallel",
                "stages": [{"stage": "a"}, {"stage": "b"}],
                "join": "all",
            }
        )
        assert isinstance(node, Parallel)
        assert node.join == "all"

    def test_parallel_any(self) -> None:
        node = parse_composition(
            {
                "compose": "parallel",
                "stages": [{"stage": "a"}, {"stage": "b"}],
                "join": "any",
            }
        )
        assert isinstance(node, Parallel)
        assert node.join == "any"

    def test_parallel_n_of(self) -> None:
        node = parse_composition(
            {
                "compose": "parallel",
                "stages": [{"stage": "a"}, {"stage": "b"}, {"stage": "c"}],
                "join": "n_of(2)",
            }
        )
        assert isinstance(node, Parallel)
        assert node.join == "n_of"
        assert node.n_of_count == 2

    def test_choice(self) -> None:
        node = parse_composition(
            {
                "compose": "choice",
                "condition": "review.decision == 'pass'",
                "if_true": {"stage": "release"},
                "if_false": {"stage": "refine"},
            }
        )
        assert isinstance(node, Choice)
        assert node.condition == "review.decision == 'pass'"
        assert isinstance(node.if_true, StageRef)
        assert isinstance(node.if_false, StageRef)

    def test_loop_ref(self) -> None:
        node = parse_composition({"compose": "loop", "ref": "review_cycle"})
        assert isinstance(node, LoopRef)
        assert node.ref == "review_cycle"

    def test_gate_ref(self) -> None:
        node = parse_composition({"compose": "gate", "ref": "release_gate"})
        assert isinstance(node, GateRef)
        assert node.ref == "release_gate"

    def test_break(self) -> None:
        node = parse_composition({"break": True})
        assert isinstance(node, Break)

    def test_nested_composition(self) -> None:
        node = parse_composition(
            {
                "compose": "sequence",
                "stages": [
                    {"stage": "design"},
                    {
                        "compose": "parallel",
                        "stages": [{"stage": "test"}, {"stage": "review"}],
                        "join": "all",
                    },
                    {
                        "compose": "choice",
                        "condition": "test.pass",
                        "if_true": {"stage": "release"},
                        "if_false": {"stage": "refine"},
                    },
                ],
            }
        )
        assert isinstance(node, Sequence)
        assert isinstance(node.stages[0], StageRef)
        assert isinstance(node.stages[1], Parallel)
        assert isinstance(node.stages[2], Choice)

    def test_unknown_compose_raises(self) -> None:
        with pytest.raises(TemplateParseError, match="Unknown compose type"):
            parse_composition({"compose": "invalid_operator"})


# ═══════════════════════════════════════════════════════════════════
# §3  Collect stage refs
# ═══════════════════════════════════════════════════════════════════


class TestCollectStageRefs:
    def test_simple_sequence(self) -> None:
        node = Sequence(stages=[StageRef("a"), StageRef("b"), StageRef("c")])
        assert collect_stage_refs(node) == {"a", "b", "c"}

    def test_nested_choice(self) -> None:
        node = Choice(
            condition="x",
            if_true=StageRef("yes"),
            if_false=Sequence(stages=[StageRef("no1"), StageRef("no2")]),
        )
        assert collect_stage_refs(node) == {"yes", "no1", "no2"}

    def test_parallel(self) -> None:
        node = Parallel(stages=[StageRef("a"), StageRef("b")], join="all")
        assert collect_stage_refs(node) == {"a", "b"}


# ═══════════════════════════════════════════════════════════════════
# §4  Validation checks — positive and negative cases
# ═══════════════════════════════════════════════════════════════════


class TestValidationSchemaConformance:
    def test_valid_template(self) -> None:
        tpl = parse_template(FIXTURES / "research_only.yaml")
        r = check_schema_conformance(tpl)
        assert r.valid

    def test_missing_metadata_name(self) -> None:
        tpl = parse_template_string("""
schema_version: "1.0"
metadata:
  name: ""
  version: "1.0.0"
stages:
  - id: a
    primitive: design
composition:
  stage: a
""")
        r = check_schema_conformance(tpl)
        assert not r.valid
        assert any("metadata.name" in e for e in r.errors)

    def test_invalid_primitive(self) -> None:
        tpl = parse_template_string("""
schema_version: "1.0"
metadata:
  name: bad
  version: "1.0.0"
stages:
  - id: a
    primitive: explode
composition:
  stage: a
""")
        r = check_schema_conformance(tpl)
        assert not r.valid
        assert any("invalid primitive" in e for e in r.errors)

    def test_duplicate_stage_ids(self) -> None:
        tpl = parse_template_string("""
schema_version: "1.0"
metadata:
  name: dup
  version: "1.0.0"
stages:
  - id: a
    primitive: design
  - id: a
    primitive: plan
composition:
  compose: sequence
  stages:
    - stage: a
""")
        r = check_schema_conformance(tpl)
        assert not r.valid
        assert any("Duplicate" in e for e in r.errors)


class TestValidationStageRefIntegrity:
    def test_valid(self) -> None:
        tpl = parse_template(FIXTURES / "hotfix.yaml")
        r = check_stage_reference_integrity(tpl)
        assert r.valid

    def test_missing_ref(self) -> None:
        tpl = parse_template(FIXTURES / "invalid_missing_stage_ref.yaml")
        r = check_stage_reference_integrity(tpl)
        assert not r.valid
        assert any("nonexistent_stage" in e for e in r.errors)


class TestValidationLoopTermination:
    def test_valid_loops(self) -> None:
        tpl = parse_template(FIXTURES / "full_pipeline.yaml")
        r = check_loop_termination(tpl)
        assert r.valid

    def test_missing_max_iterations(self) -> None:
        tpl = parse_template(FIXTURES / "invalid_no_max_iterations.yaml")
        r = check_loop_termination(tpl)
        assert not r.valid
        assert any("max_iterations" in e for e in r.errors)

    def test_missing_until(self) -> None:
        tpl = parse_template_string("""
schema_version: "1.0"
metadata:
  name: bad-loop
  version: "1.0.0"
stages:
  - id: a
    primitive: implement
composition:
  compose: loop
  ref: loop1
loops:
  - name: loop1
    body_stages: [a]
    until: ""
    max_iterations: 5
    on_exhaustion: abort
""")
        r = check_loop_termination(tpl)
        assert not r.valid
        assert any("until" in e for e in r.errors)


class TestValidationGateCompleteness:
    def test_valid_gates(self) -> None:
        tpl = parse_template(FIXTURES / "full_pipeline.yaml")
        r = check_gate_completeness(tpl)
        assert r.valid

    def test_missing_on_fail(self) -> None:
        tpl = parse_template_string("""
schema_version: "1.0"
metadata:
  name: bad-gate
  version: "1.0.0"
stages:
  - id: a
    primitive: design
composition:
  stage: a
gates:
  - name: g1
    position: "after:a"
    criteria:
      - field: a.spec
        operator: "exists"
        value: true
    on_pass: "next"
    on_fail: {}
""")
        r = check_gate_completeness(tpl)
        assert not r.valid
        assert any("on_fail" in e for e in r.errors)


class TestValidationReachability:
    def test_all_reachable(self) -> None:
        tpl = parse_template(FIXTURES / "hotfix.yaml")
        r = check_reachability(tpl)
        assert r.valid

    def test_unreachable_stage(self) -> None:
        tpl = parse_template(FIXTURES / "invalid_orphan_stage.yaml")
        r = check_reachability(tpl)
        assert not r.valid
        assert any("orphan_review" in e for e in r.errors)


class TestValidationNoOrphans:
    def test_no_orphans(self) -> None:
        tpl = parse_template(FIXTURES / "research_only.yaml")
        r = check_no_orphan_stages(tpl)
        assert len(r.warnings) == 0

    def test_orphan_detected(self) -> None:
        tpl = parse_template(FIXTURES / "invalid_orphan_stage.yaml")
        r = check_no_orphan_stages(tpl)
        assert any("orphan_review" in w for w in r.warnings)


class TestValidationDependencyLattice:
    def test_lattice_warning(self) -> None:
        tpl = parse_template_string("""
schema_version: "1.0"
metadata:
  name: lattice-test
  version: "1.0.0"
stages:
  - id: a
    primitive: research
  - id: b
    primitive: release
composition:
  compose: sequence
  stages:
    - compose: loop
      ref: bad_loop

loops:
  - name: bad_loop
    body_stages: [a, b]
    until: "done"
    max_iterations: 3
    on_exhaustion: abort
""")
        r = check_dependency_lattice(tpl)
        assert len(r.warnings) > 0
        assert any("violates dependency lattice" in w for w in r.warnings)


class TestValidateTemplate:
    def test_full_validation_pass(self) -> None:
        tpl = parse_template(FIXTURES / "full_pipeline.yaml")
        r = validate_template(tpl)
        assert r.valid, r.errors

    def test_full_validation_catches_multiple_errors(self) -> None:
        tpl = parse_template(FIXTURES / "invalid_missing_stage_ref.yaml")
        r = validate_template(tpl)
        assert not r.valid


# ═══════════════════════════════════════════════════════════════════
# §5  Registry discovery
# ═══════════════════════════════════════════════════════════════════


class TestRegistry:
    @pytest.fixture()
    def registry_root(self, tmp_path: Path) -> Path:
        builtin = tmp_path / "builtin"
        builtin.mkdir()
        custom = tmp_path / "custom"
        custom.mkdir()
        derived = tmp_path / "derived"
        derived.mkdir()

        import shutil

        shutil.copy(FIXTURES / "research_only.yaml", builtin / "research-only.yaml")
        shutil.copy(FIXTURES / "hotfix.yaml", builtin / "hotfix.yaml")
        shutil.copy(FIXTURES / "full_pipeline.yaml", builtin / "full-pipeline.yaml")

        (custom / "research-only.yaml").write_text(
            (FIXTURES / "research_only.yaml")
            .read_text()
            .replace('version: "1.0.0"', 'version: "2.0.0"')
        )
        return tmp_path

    @pytest.fixture()
    def registry(self, registry_root: Path) -> TemplateRegistry:
        return TemplateRegistry(templates_root=registry_root)

    def test_discover_all(self, registry: TemplateRegistry) -> None:
        results = registry.discover()
        names = [m.name for m in results]
        assert "research-only" in names
        assert "hotfix" in names
        assert "full-pipeline" in names

    def test_discover_by_name(self, registry: TemplateRegistry) -> None:
        results = registry.discover(name="hotfix")
        assert len(results) == 1
        assert results[0].name == "hotfix"

    def test_discover_by_category(self, registry: TemplateRegistry) -> None:
        results = registry.discover(category="build")
        assert all(m.category == "build" for m in results)

    def test_discover_by_tags(self, registry: TemplateRegistry) -> None:
        results = registry.discover(tags=["research"])
        assert len(results) >= 1
        assert any(m.name == "research-only" for m in results)

    def test_custom_shadows_builtin(self, registry: TemplateRegistry) -> None:
        results = registry.discover(name="research-only")
        assert len(results) == 1
        tpl = registry.load_template("research-only")
        assert tpl is not None
        assert tpl.metadata.version == "2.0.0"

    def test_load_template(self, registry: TemplateRegistry) -> None:
        tpl = registry.load_template("full-pipeline")
        assert tpl is not None
        assert tpl.metadata.name == "full-pipeline"
        assert len(tpl.stages) == 8

    def test_load_nonexistent(self, registry: TemplateRegistry) -> None:
        assert registry.load_template("does-not-exist") is None

    def test_register_manual(self, registry: TemplateRegistry) -> None:
        meta = registry.register(FIXTURES / "hotfix.yaml", tier="custom")
        assert meta is not None
        assert meta.name == "hotfix"


# ═══════════════════════════════════════════════════════════════════
# §6  Inheritance
# ═══════════════════════════════════════════════════════════════════


class TestInheritance:
    @pytest.fixture()
    def registry(self, tmp_path: Path) -> TemplateRegistry:
        builtin = tmp_path / "builtin"
        builtin.mkdir()
        (tmp_path / "custom").mkdir()
        (tmp_path / "derived").mkdir()

        import shutil

        shutil.copy(FIXTURES / "full_pipeline.yaml", builtin / "full-pipeline.yaml")
        return TemplateRegistry(templates_root=tmp_path)

    def test_resolve_no_extends(self, registry: TemplateRegistry) -> None:
        tpl = parse_template(FIXTURES / "hotfix.yaml")
        resolved = resolve_inheritance(tpl, registry)
        assert resolved.metadata.name == "hotfix"

    def test_resolve_with_extends(self, registry: TemplateRegistry) -> None:
        child = parse_template(FIXTURES / "derived_template.yaml")
        resolved = resolve_inheritance(child, registry)
        assert resolved.extends is None
        assert resolved.metadata.name == "full-pipeline-local"
        impl = resolved.stage_by_id("impl")
        assert impl is not None
        assert impl.config["test_strategy"] == "test_after"

    def test_missing_base_raises(self, registry: TemplateRegistry) -> None:
        child = parse_template_string("""
schema_version: "1.0"
metadata:
  name: child
  version: "1.0.0"
extends: nonexistent-base
stages: []
composition:
  stage: dummy
""")
        with pytest.raises(InheritanceError, match="nonexistent-base"):
            resolve_inheritance(child, registry)


# ═══════════════════════════════════════════════════════════════════
# §7  Model invariants
# ═══════════════════════════════════════════════════════════════════


class TestModelInvariants:
    def test_valid_primitives_set(self) -> None:
        expected = {
            "research",
            "analyze",
            "design",
            "plan",
            "implement",
            "review",
            "test",
            "verify",
            "validate",
            "refine",
            "release",
            "deploy",
            "monitor",
            "gate",
        }
        assert expected == VALID_PRIMITIVES

    def test_stage_by_id(self) -> None:
        tpl = parse_template(FIXTURES / "hotfix.yaml")
        assert tpl.stage_by_id("fix") is not None
        assert tpl.stage_by_id("nonexistent") is None

    def test_parse_template_string(self) -> None:
        tpl = parse_template_string("""
schema_version: "1.0"
metadata:
  name: tiny
  version: "0.1.0"
stages:
  - id: a
    primitive: design
composition:
  stage: a
""")
        assert tpl.metadata.name == "tiny"
        assert len(tpl.stages) == 1
