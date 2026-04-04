"""Template validation — schema conformance, reachability, cycle detection.

Design ref: design_meta_framework.md §8.4 (7 checks)

Checks:
 1. Schema conformance      — required fields present, types correct
 2. Stage reference integrity — every stage id in composition/loops/gates exists
 3. Loop termination        — every loop has both ``until`` and ``max_iterations``
 4. Gate completeness       — every gate has both ``on_pass`` and ``on_fail``
 5. Reachability            — every stage reachable from composition root
 6. No orphan stages        — no stage defined but never referenced
 7. Dependency lattice conformance (warning only)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from devolaflow.template_engine.composer import collect_stage_refs
from devolaflow.template_engine.models import (
    DEPENDENCY_LATTICE,
    VALID_PRIMITIVES,
    GateDef,
    LoopDef,
    WorkflowTemplate,
)

log = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return len(self.errors) == 0

    def merge(self, other: ValidationResult) -> None:
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)


# ── Individual checks ─────────────────────────────────────────────


def check_schema_conformance(template: WorkflowTemplate) -> ValidationResult:
    """Check 1: all required fields present, types correct."""
    r = ValidationResult()

    if not template.schema_version:
        r.errors.append("Missing schema_version")
    if not template.metadata.name:
        r.errors.append("Missing metadata.name")
    if not template.metadata.version:
        r.errors.append("Missing metadata.version")
    if not template.stages:
        r.errors.append("Template defines no stages")

    for stage in template.stages:
        if not stage.id:
            r.errors.append("Stage missing 'id'")
        if not stage.primitive:
            r.errors.append(f"Stage '{stage.id}' missing 'primitive'")
        elif stage.primitive not in VALID_PRIMITIVES:
            r.errors.append(
                f"Stage '{stage.id}' has invalid primitive '{stage.primitive}'. "
                f"Valid: {sorted(VALID_PRIMITIVES)}"
            )

    ids = [s.id for s in template.stages]
    dupes = {x for x in ids if ids.count(x) > 1}
    if dupes:
        r.errors.append(f"Duplicate stage ids: {sorted(dupes)}")

    return r


def check_stage_reference_integrity(template: WorkflowTemplate) -> ValidationResult:
    """Check 2: every stage id referenced in composition/loops/gates exists."""
    r = ValidationResult()
    defined = template.stage_ids()
    referenced = _all_referenced_stage_ids(template)

    for ref_id in sorted(referenced - defined):
        r.errors.append(f"Referenced stage '{ref_id}' not defined in stages list")

    return r


def check_loop_termination(template: WorkflowTemplate) -> ValidationResult:
    """Check 3: every loop has both ``until`` and ``max_iterations``."""
    r = ValidationResult()
    for loop in template.loops:
        if not loop.until:
            r.errors.append(f"Loop '{loop.name}' missing 'until' condition")
        if not loop.max_iterations or loop.max_iterations <= 0:
            r.errors.append(f"Loop '{loop.name}' missing or invalid 'max_iterations'")
    return r


def check_gate_completeness(template: WorkflowTemplate) -> ValidationResult:
    """Check 4: every gate has both ``on_pass`` and ``on_fail``."""
    r = ValidationResult()
    for gate in template.gates:
        if not gate.on_pass:
            r.errors.append(f"Gate '{gate.name}' missing 'on_pass'")
        if not gate.on_fail or not gate.on_fail.action:
            r.errors.append(f"Gate '{gate.name}' missing 'on_fail'")
    return r


def check_reachability(template: WorkflowTemplate) -> ValidationResult:
    """Check 5: every stage reachable from the composition root."""
    r = ValidationResult()
    reachable = _reachable_stage_ids(template)
    defined = template.stage_ids()
    unreachable = defined - reachable

    skip_ids = {s.id for s in template.stages if s.skip_condition}
    unreachable -= skip_ids

    for uid in sorted(unreachable):
        r.errors.append(f"Stage '{uid}' is defined but unreachable from composition root")
    return r


def check_no_orphan_stages(template: WorkflowTemplate) -> ValidationResult:
    """Check 6: no stage defined but never referenced."""
    r = ValidationResult()
    referenced = _all_referenced_stage_ids(template)
    defined = template.stage_ids()
    orphans = defined - referenced

    skip_ids = {s.id for s in template.stages if s.skip_condition}
    orphans -= skip_ids

    for oid in sorted(orphans):
        r.warnings.append(f"Stage '{oid}' is defined but never referenced (orphan)")
    return r


def check_dependency_lattice(template: WorkflowTemplate) -> ValidationResult:
    """Check 7 (warning only): flag transitions that violate the lattice."""
    r = ValidationResult()
    stage_map = {s.id: s.primitive for s in template.stages}

    for loop in template.loops:
        body = loop.body_stages
        for i in range(len(body) - 1):
            src_id, dst_id = body[i], body[i + 1]
            src_prim = stage_map.get(src_id)
            dst_prim = stage_map.get(dst_id)
            if not src_prim or not dst_prim:
                continue
            if src_prim == "gate" or dst_prim == "gate":
                continue
            allowed = DEPENDENCY_LATTICE.get(src_prim, set())
            if dst_prim not in allowed:
                r.warnings.append(
                    f"Transition '{src_id}'({src_prim}) -> '{dst_id}'({dst_prim}) "
                    f"violates dependency lattice"
                )

    return r


# ── Aggregate validation ──────────────────────────────────────────


def validate_template(template: WorkflowTemplate) -> ValidationResult:
    """Run all 7 validation checks and return combined result."""
    result = ValidationResult()
    result.merge(check_schema_conformance(template))
    result.merge(check_stage_reference_integrity(template))
    result.merge(check_loop_termination(template))
    result.merge(check_gate_completeness(template))
    result.merge(check_reachability(template))
    result.merge(check_no_orphan_stages(template))
    result.merge(check_dependency_lattice(template))
    return result


def validate_all_templates(
    all_flag: bool = False,
    templates_root: Path | None = None,
) -> bool:
    """Discover all .yaml template files and validate each.

    Returns True if all pass.
    """
    from devolaflow.template_engine.parser import parse_template

    if templates_root is None:
        project_root = _find_project_root()
        templates_root = project_root / "workflow-system" / "agent" / "templates" / "builtin"

    if not templates_root.exists():
        print(f"Templates directory not found: {templates_root}")
        log.warning("Templates directory not found: %s", templates_root)
        return False

    yaml_files = sorted(templates_root.glob("*.yaml"))
    if not yaml_files:
        print(f"No .yaml files found in {templates_root}")
        return False

    all_valid = True
    pass_count = 0
    fail_count = 0

    for yaml_path in yaml_files:
        try:
            tpl = parse_template(yaml_path)
            result = validate_template(tpl)
            if result.valid:
                print(f"  PASS: {yaml_path.name}")
                pass_count += 1
            else:
                print(f"  FAIL: {yaml_path.name}")
                for err in result.errors:
                    print(f"    ERROR: {err}")
                fail_count += 1
                all_valid = False
            for w in result.warnings:
                print(f"    WARNING: {w}")
                log.warning("Template %s: %s", yaml_path.name, w)
        except Exception as exc:
            print(f"  FAIL: {yaml_path.name} (parse error: {exc})")
            log.exception("Failed to parse template %s", yaml_path.name)
            fail_count += 1
            all_valid = False

    print(f"\n{pass_count} passed, {fail_count} failed, {len(yaml_files)} total")
    return all_valid


def _find_project_root() -> Path:
    """Find the project root by walking up from this file looking for pyproject.toml."""
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / "pyproject.toml").exists():
            return current
        current = current.parent
    return Path.cwd()


# ── Helpers ───────────────────────────────────────────────────────


def _all_referenced_stage_ids(template: WorkflowTemplate) -> set[str]:
    """Collect every stage id referenced anywhere in the template."""
    refs = collect_stage_refs(template.composition)

    for loop in template.loops:
        refs.update(loop.body_stages)
        if loop.escalation_target:
            refs.add(loop.escalation_target)

    for gate in template.gates:
        if gate.on_pass and gate.on_pass != "next":
            refs.add(gate.on_pass)
        if gate.on_fail and gate.on_fail.target:
            refs.add(gate.on_fail.target)

    return refs


def _reachable_stage_ids(template: WorkflowTemplate) -> set[str]:
    """Compute the set of stage ids reachable from the composition root."""
    comp_refs = collect_stage_refs(template.composition)

    loop_map: dict[str, LoopDef] = {lp.name: lp for lp in template.loops}
    gate_map: dict[str, GateDef] = {g.name: g for g in template.gates}

    reachable: set[str] = set(comp_refs)

    _expand_loops_gates(template.composition, loop_map, gate_map, reachable)

    return reachable


def _expand_loops_gates(
    node: Any,
    loop_map: dict[str, LoopDef],
    gate_map: dict[str, GateDef],
    reachable: set[str],
) -> None:
    """Walk the composition tree and expand loop/gate refs into reachable stages."""
    from devolaflow.template_engine.models import (
        Choice,
        GateRef,
        LoopRef,
        Parallel,
        Sequence,
        StageRef,
    )

    if isinstance(node, StageRef):
        reachable.add(node.stage)
    elif isinstance(node, (Sequence, Parallel)):
        for child in node.stages:
            _expand_loops_gates(child, loop_map, gate_map, reachable)
    elif isinstance(node, Choice):
        _expand_loops_gates(node.if_true, loop_map, gate_map, reachable)
        _expand_loops_gates(node.if_false, loop_map, gate_map, reachable)
    elif isinstance(node, LoopRef):
        loop_def = loop_map.get(node.ref)
        if loop_def:
            reachable.update(loop_def.body_stages)
            if loop_def.escalation_target:
                reachable.add(loop_def.escalation_target)
    elif isinstance(node, GateRef):
        gate_def = gate_map.get(node.ref)
        if gate_def:
            if gate_def.on_pass and gate_def.on_pass != "next":
                reachable.add(gate_def.on_pass)
            if gate_def.on_fail and gate_def.on_fail.target:
                reachable.add(gate_def.on_fail.target)
