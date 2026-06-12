"""Template registry — discovery, loading, and caching.

Design ref: design_meta_framework.md §5.1-§5.3

Discovery priority:  custom > derived > builtin  (§5.3)

v15.0.0 (v15-ADR-002 Phase B): names absent from disk additionally
resolve through the ``compositions:`` manifest of ``registry.yaml``
(schema v2.0) — the alias layer for the 16 collapsed legacy templates.
"""

from __future__ import annotations

import logging
import warnings
from pathlib import Path

from devolaflow.template_engine.compositions import (
    CompositionEntry,
    CompositionManifestError,
    composition_to_template,
    load_composition_manifest,
)
from devolaflow.template_engine.models import TemplateMetadata, WorkflowTemplate
from devolaflow.template_engine.parser import TemplateParseError, parse_template

log = logging.getLogger(__name__)

_TIER_PRIORITY = {"custom": 0, "derived": 1, "builtin": 2}


class TemplateRegistry:
    """Central store for discovering and loading workflow templates.

    Default layout::

        <root>/
            builtin/   — shipped with framework (read-only)
            custom/    — user-defined
            derived/   — templates derived via inheritance
    """

    def __init__(self, templates_root: Path | None = None) -> None:
        """Initialize the registry with a root directory for template discovery."""
        if templates_root is None:
            templates_root = Path("workflow-system/agent/templates")
        self._root = templates_root
        self._cache: dict[str, WorkflowTemplate] = {}
        self._index: list[_IndexEntry] = []
        self._indexed = False
        self._compositions: dict[str, CompositionEntry] | None = None

    # ── public API ────────────────────────────────────────────────

    def discover(
        self,
        name: str | None = None,
        tags: list[str] | None = None,
        category: str | None = None,
    ) -> list[TemplateMetadata]:
        """Find templates matching the given filters.

        Returns metadata entries sorted by discovery priority
        (custom > derived > builtin).
        """
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

        results.sort(key=lambda e: _TIER_PRIORITY.get(e.tier, 99))

        seen: set[str] = set()
        deduped: list[TemplateMetadata] = []
        for entry in results:
            if entry.meta.name not in seen:
                seen.add(entry.meta.name)
                deduped.append(entry.meta)

        return deduped

    def load_template(self, name: str) -> WorkflowTemplate | None:
        """Load a template by name, checking cache first.

        Resolution order: cache → on-disk yaml (custom > derived >
        builtin) → compositions manifest (the v15-ADR-002 alias layer for
        collapsed legacy names). Unknown names return ``None`` (the
        registry's explicit-miss contract); malformed manifests raise
        :class:`CompositionManifestError` (S-5: fail loudly).
        """
        if name in self._cache:
            return self._cache[name]

        tpl = self._load_concrete(name)
        if tpl is not None:
            return tpl

        return self._resolve_composition(name)

    def compositions(self) -> dict[str, CompositionEntry]:
        """Return the compositions manifest (empty for pre-v2.0 layouts)."""
        if self._compositions is None:
            self._compositions = load_composition_manifest(self._root / "registry.yaml")
        return self._compositions

    def register(self, path: Path, tier: str = "custom") -> TemplateMetadata | None:
        """Manually register a template file."""
        try:
            tpl = parse_template(path)
        except TemplateParseError:
            log.exception("Failed to parse template at %s", path)
            return None

        entry = _IndexEntry(meta=tpl.metadata, path=path, tier=tier)
        self._index.append(entry)
        self._cache[tpl.metadata.name] = tpl
        return tpl.metadata

    # ── private ───────────────────────────────────────────────────

    def _load_concrete(self, name: str) -> WorkflowTemplate | None:
        """Load an on-disk template by name (no composition fallback)."""
        self._ensure_indexed()

        for entry in sorted(self._index, key=lambda e: _TIER_PRIORITY.get(e.tier, 99)):
            if entry.meta.name == name:
                try:
                    tpl = parse_template(entry.path)
                    self._cache[name] = tpl
                    return tpl
                except TemplateParseError:
                    log.exception("Failed to load template '%s'", name)
                    return None

        return None

    def _resolve_composition(self, name: str) -> WorkflowTemplate | None:
        """Resolve a collapsed legacy name via the compositions manifest.

        Synthesizes the template from the entry's C-3 verbatim stage
        sequence (see :func:`composition_to_template`) after confirming
        the primary base resolves to an on-disk survivor. Emits a
        :class:`DeprecationWarning` + WARNING log on first resolution
        (v15-ADR-002 decision 3 — no silent rewrite). ``None`` when the
        name is not a composition either.
        """
        entry = self.compositions().get(name)
        if entry is None:
            return None

        # Fail loudly (S-5) if the declared base chain is broken.
        self._resolve_base(entry.primary_base, visited=(name,))

        resolved = composition_to_template(entry)
        warnings.warn(entry.deprecation_note(), DeprecationWarning, stacklevel=3)
        log.warning(
            "Template '%s' is a deprecated composition alias — resolved via "
            "base '%s' (v15-ADR-002; alias guaranteed until at least v16.0.0)",
            name,
            entry.primary_base,
        )
        self._cache[name] = resolved
        return resolved

    def _resolve_base(self, base: str, visited: tuple[str, ...]) -> WorkflowTemplate:
        """Resolve a composition base to a concrete template, loudly.

        A base may itself be another composition (e.g. ``onboarding`` →
        ``documentation-only`` → ``change-driven``); cycles and unknown
        bases raise :class:`CompositionManifestError` per S-5.
        """
        tpl = self._load_concrete(base)
        if tpl is not None:
            return tpl

        if base in visited:
            chain = " -> ".join((*visited, base))
            raise CompositionManifestError(f"composition base cycle: {chain}")

        entry = self.compositions().get(base)
        if entry is None:
            chain = " -> ".join(visited)
            raise CompositionManifestError(
                f"composition '{chain}' references unknown base '{base}' "
                f"(neither an on-disk template nor a composition)"
            )
        return self._resolve_base(entry.primary_base, visited=(*visited, base))

    def _ensure_indexed(self) -> None:
        """Trigger directory scanning if not already indexed."""
        if self._indexed:
            return
        self._indexed = True
        self._scan_directory()

    def _scan_directory(self) -> None:
        """Walk builtin/custom/derived tiers and index all parseable YAML templates."""
        for tier in ("builtin", "custom", "derived"):
            tier_dir = self._root / tier
            if not tier_dir.is_dir():
                continue
            for yaml_path in sorted(tier_dir.glob("*.yaml")):
                try:
                    tpl = parse_template(yaml_path)
                    self._index.append(_IndexEntry(meta=tpl.metadata, path=yaml_path, tier=tier))
                except Exception:
                    log.warning("Skipping unparseable template: %s", yaml_path)


class _IndexEntry:
    """Store metadata, file path, and tier for a discovered template."""

    __slots__ = ("meta", "path", "tier")

    def __init__(self, meta: TemplateMetadata, path: Path, tier: str) -> None:
        """Initialize an index entry with metadata, path, and tier."""
        self.meta = meta
        self.path = path
        self.tier = tier
