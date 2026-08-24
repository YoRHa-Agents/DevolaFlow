"""Template and checklist-seed registry discovery, loading, and caching."""

from __future__ import annotations

import copy
import logging
import warnings
from dataclasses import replace
from pathlib import Path

from devolaflow.template_engine.compositions import (
    CompositionEntry,
    load_composition_manifest,
)
from devolaflow.template_engine.models import TemplateMetadata, WorkflowTemplate
from devolaflow.template_engine.parser import TemplateParseError, parse_template
from devolaflow.template_engine.seeds import (
    ChecklistSeed,
    ChecklistSeedError,
    RegistrySeedEntry,
    load_checklist_seed,
    load_seed_registry,
)

log = logging.getLogger(__name__)

_TIER_PRIORITY = {"custom": 0, "derived": 1, "builtin": 2}
_ALIAS_WARNING = (
    "TemplateRegistry.load_template('{name}') is deprecated for checklist "
    "seed '{name}' since v16.0.0; returning the 'change-driven' "
    "checklist-round runtime with seed metadata attached. Use "
    "load_seed('{name}') and load_template('change-driven'); this "
    "compatibility alias is scheduled for removal in v17.0.0."
)


class ChecklistSeedAliasWarning(DeprecationWarning):
    """Warn that a historical workflow name now selects a checklist seed."""


class TemplateRegistry:
    """Central store for executable templates and declarative checklist seeds."""

    def __init__(self, templates_root: Path | None = None) -> None:
        """Initialize the registry with a root directory for discovery."""
        self._root = templates_root or Path("workflow-system/agent/templates")
        self._cache: dict[str, WorkflowTemplate] = {}
        self._seed_cache: dict[str, ChecklistSeed] = {}
        self._index: list[_IndexEntry] = []
        self._indexed = False
        self._seed_entries: dict[str, RegistrySeedEntry] | None = None
        self._compositions: dict[str, CompositionEntry] | None = None
        self._alias_warnings_emitted: set[str] = set()

    def discover(
        self,
        name: str | None = None,
        tags: list[str] | None = None,
        category: str | None = None,
    ) -> list[TemplateMetadata]:
        """Find executable templates and seed modes without emitting warnings."""
        self._ensure_indexed()
        results: list[_IndexEntry] = []
        for entry in self._index:
            if name and entry.meta.name != name:
                continue
            if category and entry.meta.category != category:
                continue
            if tags and not set(tags) & set(entry.meta.tags):
                continue
            results.append(entry)
        results.sort(key=lambda entry: _TIER_PRIORITY.get(entry.tier, 99))

        seen: set[str] = set()
        deduped: list[TemplateMetadata] = []
        for entry in results:
            if entry.meta.name not in seen:
                seen.add(entry.meta.name)
                deduped.append(entry.meta)
        return deduped

    def load_seed(self, name: str) -> ChecklistSeed | None:
        """Load a registered checklist seed; unknown names return ``None``."""
        if name in self._seed_cache:
            return self._seed_cache[name]
        entry = self._seed_manifest().get(name)
        if entry is None:
            return None
        seed_path = self._root / entry.seed
        seed = load_checklist_seed(seed_path)
        if seed.metadata.name != entry.name:
            raise ChecklistSeedError(
                f"{seed_path}: metadata.name {seed.metadata.name!r} does not match "
                f"registry name {entry.name!r}"
            )
        if seed.metadata.category != entry.category:
            raise ChecklistSeedError(
                f"{seed_path}: metadata.category {seed.metadata.category!r} does not "
                f"match registry category {entry.category!r}"
            )
        self._seed_cache[name] = seed
        return seed

    def load_template(self, name: str) -> WorkflowTemplate | None:
        """Load the canonical runtime or a v16 checklist-seed compatibility alias."""
        if name in self._cache:
            return self._cache[name]

        concrete = self._load_concrete(name)
        if concrete is not None:
            return concrete

        seed = self.load_seed(name)
        if seed is None or name == "change-driven":
            return None
        runtime = self._load_concrete("change-driven")
        if runtime is None:
            raise ChecklistSeedError(
                "Checklist seed compatibility aliases require executable template "
                "'change-driven', but it could not be loaded"
            )

        resolved = copy.deepcopy(runtime)
        resolved.metadata = replace(
            resolved.metadata,
            name=name,
            description=seed.metadata.description,
            category=seed.metadata.category,
            applicable_scenarios=list(seed.metadata.applicable_scenarios),
            tags=list(seed.metadata.intent_keywords),
        )
        resolved.parameters = copy.deepcopy(runtime.parameters)
        seed_entry = self._seed_manifest()[name]
        resolved.parameters["checklist_seed"] = {
            "name": name,
            "path": seed_entry.seed,
            "runtime": "change-driven",
            "compatibility_alias": True,
        }
        self._emit_alias_warning(name)
        self._cache[name] = resolved
        return resolved

    def compositions(self) -> dict[str, CompositionEntry]:
        """Expose only legacy v2 manifests; registry v3 fails explicitly."""
        if self._compositions is None:
            self._compositions = load_composition_manifest(self._root / "registry.yaml")
        return self._compositions

    def register(self, path: Path, tier: str = "custom") -> TemplateMetadata | None:
        """Manually register one executable workflow template file."""
        try:
            template = parse_template(path)
        except TemplateParseError:
            log.exception("Failed to parse template at %s", path)
            return None
        entry = _IndexEntry(meta=template.metadata, path=path, tier=tier, executable=True)
        self._index.append(entry)
        self._cache[template.metadata.name] = template
        return template.metadata

    def _seed_manifest(self) -> dict[str, RegistrySeedEntry]:
        if self._seed_entries is None:
            self._seed_entries = load_seed_registry(self._root / "registry.yaml")
        return self._seed_entries

    def _emit_alias_warning(self, name: str) -> None:
        if name in self._alias_warnings_emitted:
            return
        message = _ALIAS_WARNING.format(name=name)
        warnings.warn(message, ChecklistSeedAliasWarning, stacklevel=3)
        log.warning(message)
        self._alias_warnings_emitted.add(name)

    def _load_concrete(self, name: str) -> WorkflowTemplate | None:
        self._ensure_indexed()
        for entry in sorted(
            self._index, key=lambda candidate: _TIER_PRIORITY.get(candidate.tier, 99)
        ):
            if entry.meta.name != name or not entry.executable or entry.path is None:
                continue
            try:
                template = parse_template(entry.path)
            except TemplateParseError:
                log.exception("Failed to load template '%s'", name)
                return None
            self._cache[name] = template
            return template
        return None

    def _ensure_indexed(self) -> None:
        if self._indexed:
            return
        self._indexed = True
        self._scan_directory()
        self._index_registry_seeds()

    def _scan_directory(self) -> None:
        for tier in ("builtin", "custom", "derived"):
            tier_dir = self._root / tier
            if not tier_dir.is_dir():
                continue
            for yaml_path in sorted(tier_dir.glob("*.yaml")):
                try:
                    template = parse_template(yaml_path)
                except Exception:
                    log.warning("Skipping unparseable template: %s", yaml_path)
                    continue
                self._index.append(
                    _IndexEntry(
                        meta=template.metadata,
                        path=yaml_path,
                        tier=tier,
                        executable=True,
                    )
                )

    def _index_registry_seeds(self) -> None:
        for entry in self._seed_manifest().values():
            self._index.append(
                _IndexEntry(
                    meta=TemplateMetadata(
                        name=entry.name,
                        version="1.0.0",
                        description=entry.description,
                        category=entry.category,
                        tags=list(entry.tags),
                    ),
                    path=self._root / entry.seed,
                    tier="builtin",
                    executable=False,
                )
            )


class _IndexEntry:
    """Store discovery metadata and whether a path is executable."""

    __slots__ = ("meta", "path", "tier", "executable")

    def __init__(
        self,
        meta: TemplateMetadata,
        path: Path | None,
        tier: str,
        executable: bool,
    ) -> None:
        self.meta = meta
        self.path = path
        self.tier = tier
        self.executable = executable
