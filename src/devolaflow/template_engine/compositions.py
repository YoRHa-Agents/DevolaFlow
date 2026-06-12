"""Composition manifest — the v15.0.0 Phase B alias layer.

Per `v15-ADR-002` (template registry Phase B collapse), the 16 former
legacy builtin yamls are re-expressed as named entries in the
``compositions:`` block of ``templates/registry.yaml`` (schema v2.0).
Each entry is ``base`` (a survivor template) + parameter overrides, or a
``compose: sequence`` of such steps, PLUS the C-3 verbatim ``stages:``
sequence extracted from the deleted yaml — the resolved template is
synthesized from that sequence so legacy behavior stays reproducible.

Alias guarantee (ADR decision 3): every composition name keeps resolving
through :meth:`TemplateRegistry.load_template` for >= 1 MAJOR; resolution
emits a :class:`DeprecationWarning` (S-5: no silent rewrite). Unknown
names and malformed manifests fail loudly via
:class:`CompositionManifestError`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from devolaflow.template_engine.models import (
    VALID_PRIMITIVES,
    Sequence,
    StageDefinition,
    StageRef,
    TemplateMetadata,
    WorkflowTemplate,
)

log = logging.getLogger(__name__)

#: Schema version of the registry file that carries a compositions block.
REGISTRY_SCHEMA_V2 = "2.0"

#: Gate types a composition may declare (mirrors the survivor gate types).
VALID_GATE_TYPES = frozenset({"standard", "convergence"})

#: Deprecation note template embedded in resolved aliases (ADR decision 3).
DEPRECATION_NOTE = (
    "'{name}' was collapsed into a named composition at v15.0.0 per "
    "v15-ADR-002; it resolves via base '{base}'. Alias resolution is "
    "guaranteed until at least v16.0.0 — migrate workflow_type references "
    "to the composition expression."
)


class CompositionManifestError(Exception):
    """Raised when the compositions manifest is malformed or unresolvable."""


@dataclass(frozen=True)
class CompositionStep:
    """One step of a composition: a base template name + parameter overrides."""

    base: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CompositionStage:
    """One C-3 verbatim stage carried over from the deleted legacy yaml."""

    id: str
    primitive: str
    config: dict[str, Any] = field(default_factory=dict)
    skip_condition: str | None = None


@dataclass(frozen=True)
class CompositionEntry:
    """A named composition replacing one former legacy template yaml."""

    name: str
    steps: tuple[CompositionStep, ...]
    stages: tuple[CompositionStage, ...] = ()
    gate: str = "standard"
    params: dict[str, Any] = field(default_factory=dict)
    expression: str = ""
    category: str = ""
    tags: tuple[str, ...] = ()
    description: str = ""
    deprecated_since: str = ""
    collapsed_in: str = ""

    @property
    def primary_base(self) -> str:
        """Return the base template name the alias resolves to (first step)."""
        return self.steps[0].base

    def stage_sequence(self) -> list[tuple[str, str]]:
        """Return the verbatim ``(stage_id, primitive)`` sequence."""
        return [(s.id, s.primitive) for s in self.stages]

    def deprecation_note(self) -> str:
        """Render the operator-facing deprecation note for this alias."""
        return DEPRECATION_NOTE.format(name=self.name, base=self.primary_base)


def _parse_stage(name: str, raw: Any) -> CompositionStage:
    """Build a :class:`CompositionStage` from one raw stage mapping."""
    if not isinstance(raw, dict) or not raw.get("id") or not raw.get("primitive"):
        raise CompositionManifestError(
            f"composition '{name}' has a stage without 'id'/'primitive': {raw!r}"
        )
    return CompositionStage(
        id=str(raw["id"]),
        primitive=str(raw["primitive"]),
        config=dict(raw.get("config") or {}),
        skip_condition=raw.get("skip_condition"),
    )


def _parse_entry(raw: dict[str, Any]) -> CompositionEntry:
    """Build a :class:`CompositionEntry` from one raw manifest mapping."""
    name = raw.get("name")
    if not name or not isinstance(name, str):
        raise CompositionManifestError(f"composition entry missing 'name': {raw!r}")

    raw_steps = raw.get("steps")
    base = raw.get("base")
    if raw_steps is not None:
        if base is not None:
            raise CompositionManifestError(
                f"composition '{name}' declares BOTH 'base' and 'steps' — pick one"
            )
        steps: list[CompositionStep] = []
        for raw_step in raw_steps:
            step_base = raw_step.get("base") if isinstance(raw_step, dict) else None
            if not step_base:
                raise CompositionManifestError(
                    f"composition '{name}' has a step without 'base': {raw_step!r}"
                )
            steps.append(CompositionStep(base=step_base, params=dict(raw_step.get("params") or {})))
        if not steps:
            raise CompositionManifestError(f"composition '{name}' declares empty 'steps'")
    elif base:
        steps = [CompositionStep(base=base, params={})]
    else:
        raise CompositionManifestError(f"composition '{name}' declares neither 'base' nor 'steps'")

    raw_stages = raw.get("stages") or []
    stages = tuple(_parse_stage(name, raw_stage) for raw_stage in raw_stages)
    if not stages:
        raise CompositionManifestError(
            f"composition '{name}' declares no 'stages' — the C-3 verbatim "
            f"stage sequence from the deleted yaml is REQUIRED in schema v2.0"
        )

    return CompositionEntry(
        name=name,
        steps=tuple(steps),
        stages=stages,
        gate=str(raw.get("gate") or "standard"),
        params=dict(raw.get("params") or {}),
        expression=str(raw.get("expression") or ""),
        category=str(raw.get("category") or ""),
        tags=tuple(raw.get("tags") or ()),
        description=str(raw.get("description") or ""),
        deprecated_since=str(raw.get("deprecated_since") or ""),
        collapsed_in=str(raw.get("collapsed_in") or ""),
    )


def load_composition_manifest(registry_yaml: Path) -> dict[str, CompositionEntry]:
    """Parse the ``compositions:`` block of a v2.0 registry file.

    Returns an empty mapping when the file is absent or carries no
    compositions block (pre-v2.0 layouts, tmp-dir test registries).
    Malformed entries raise :class:`CompositionManifestError` (S-5).
    """
    if not registry_yaml.is_file():
        return {}

    import yaml

    raw = yaml.safe_load(registry_yaml.read_text(encoding="utf-8")) or {}
    raw_compositions = raw.get("compositions") or []
    manifest: dict[str, CompositionEntry] = {}
    for raw_entry in raw_compositions:
        entry = _parse_entry(raw_entry)
        if entry.name in manifest:
            raise CompositionManifestError(f"duplicate composition name '{entry.name}'")
        manifest[entry.name] = entry
    return manifest


def composition_to_template(entry: CompositionEntry) -> WorkflowTemplate:
    """Synthesize a :class:`WorkflowTemplate` from a composition entry.

    The synthesized template carries the C-3 verbatim stage sequence as
    its ``stages`` list, composed as a plain ``sequence`` — the same
    shape the deleted yaml's main path declared. The full resolution
    record (base, params, expression, deprecation note) is embedded
    under ``parameters["composition"]`` so dispatchers see the alias
    provenance (no silent rewrite).
    """
    stages = [
        StageDefinition(
            id=s.id,
            primitive=s.primitive,
            config=dict(s.config),
            skip_condition=s.skip_condition,
        )
        for s in entry.stages
    ]
    return WorkflowTemplate(
        schema_version=REGISTRY_SCHEMA_V2,
        metadata=TemplateMetadata(
            name=entry.name,
            version="1.0.0",
            description=entry.description,
            category=entry.category,
            tags=list(entry.tags),
        ),
        stages=stages,
        composition=Sequence(stages=[StageRef(stage=s.id) for s in stages]),
        parameters={
            "composition": {
                "name": entry.name,
                "alias_of": entry.primary_base,
                "expression": entry.expression,
                "gate": entry.gate,
                "params": dict(entry.params),
                "steps": [{"base": s.base, "params": dict(s.params)} for s in entry.steps],
                "deprecated_since": entry.deprecated_since,
                "deprecation": entry.deprecation_note(),
            }
        },
    )


def validate_composition_manifest(
    manifest: dict[str, CompositionEntry],
    template_names: set[str],
) -> list[str]:
    """Cross-check the manifest against concrete template names.

    Returns a list of error strings (empty == valid). Checks:

    1. No composition shadows a concrete template name.
    2. Every step base resolves to a concrete template OR another
       composition (transitively, without cycles).
    3. Every verbatim stage uses a valid primitive; stage ids are
       unique within an entry; the gate type is known.
    """
    errors: list[str] = []

    for name in sorted(manifest):
        if name in template_names:
            errors.append(f"composition '{name}' shadows a concrete template of the same name")

    def _check_base(origin: str, base: str, visited: tuple[str, ...]) -> None:
        if base in template_names:
            return
        if base in visited:
            errors.append(f"composition '{origin}' has a base cycle through '{base}'")
            return
        entry = manifest.get(base)
        if entry is None:
            errors.append(
                f"composition '{origin}' references unknown base '{base}' "
                f"(neither a template nor a composition)"
            )
            return
        for step in entry.steps:
            _check_base(origin, step.base, (*visited, base))

    for name, entry in sorted(manifest.items()):
        for step in entry.steps:
            _check_base(name, step.base, (name,))
        if entry.gate not in VALID_GATE_TYPES:
            errors.append(
                f"composition '{name}' declares unknown gate type '{entry.gate}' "
                f"(valid: {sorted(VALID_GATE_TYPES)})"
            )
        seen_ids: set[str] = set()
        for stage in entry.stages:
            if stage.primitive not in VALID_PRIMITIVES:
                errors.append(
                    f"composition '{name}' stage '{stage.id}' has invalid "
                    f"primitive '{stage.primitive}'"
                )
            if stage.id in seen_ids:
                errors.append(f"composition '{name}' has duplicate stage id '{stage.id}'")
            seen_ids.add(stage.id)

    return errors
