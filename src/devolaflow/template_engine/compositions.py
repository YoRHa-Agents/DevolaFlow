"""Retired executable-composition compatibility surface.

Registry schema v3 stores declarative checklist seeds.  The historical
dataclasses remain importable for name resolution and legacy diagnostics so
callers receive a classified error instead of an import failure, but no
helper synthesizes or validates executable DAGs (the v16 always-raise stubs
were removed in v17.0.0).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, NoReturn

import yaml

REGISTRY_SCHEMA_V2 = "2.0"
REGISTRY_SCHEMA_V3 = "3.0"

_RETIREMENT_MESSAGE = (
    "executable composition synthesis is retired in registry schema 3.0; "
    "use TemplateRegistry.load_seed() or load_template('change-driven')"
)


class CompositionManifestError(Exception):
    """Raised when retired executable-composition behavior is requested."""


@dataclass(frozen=True)
class CompositionStep:
    """Legacy import-only representation of one composition step."""

    base: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CompositionStage:
    """Legacy import-only representation of one composition stage."""

    id: str
    primitive: str
    config: dict[str, Any] = field(default_factory=dict)
    skip_condition: str | None = None


@dataclass(frozen=True)
class CompositionEntry:
    """Legacy import-only representation of a schema-v2 composition."""

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
        """Return the legacy first base for diagnostics only."""
        if not self.steps:
            raise CompositionManifestError("legacy composition declares no steps")
        return self.steps[0].base

    def stage_sequence(self) -> list[tuple[str, str]]:
        """Return legacy stage provenance without synthesizing a workflow."""
        return [(stage.id, stage.primitive) for stage in self.stages]

    def deprecation_note(self) -> str:
        """Return an explicit retirement note for old diagnostics."""
        return _RETIREMENT_MESSAGE


def _retired() -> NoReturn:
    raise CompositionManifestError(_RETIREMENT_MESSAGE)


def load_composition_manifest(registry_yaml: Path) -> dict[str, CompositionEntry]:
    """Reject schema-v3 registries; absent/pre-v2 manifests remain empty."""
    if not registry_yaml.is_file():
        return {}
    try:
        raw = yaml.safe_load(registry_yaml.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise CompositionManifestError(
            f"failed to read legacy composition manifest {registry_yaml}: {exc}"
        ) from exc
    if not isinstance(raw, dict):
        raise CompositionManifestError("legacy composition registry root must be a mapping")
    if raw.get("schema_version") == REGISTRY_SCHEMA_V3:
        _retired()
    if raw.get("schema_version") == REGISTRY_SCHEMA_V2 and raw.get("compositions"):
        _retired()
    return {}
