"""Template registry — discovery, loading, and caching.

Design ref: design_meta_framework.md §5.1-§5.3

Discovery priority:  custom > derived > builtin  (§5.3)
"""

from __future__ import annotations

import logging
from pathlib import Path

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
        if templates_root is None:
            templates_root = Path("workflow-system/agent/templates")
        self._root = templates_root
        self._cache: dict[str, WorkflowTemplate] = {}
        self._index: list[_IndexEntry] = []
        self._indexed = False

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
        """Load a template by name, checking cache first."""
        if name in self._cache:
            return self._cache[name]

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

    def _ensure_indexed(self) -> None:
        if self._indexed:
            return
        self._indexed = True
        self._scan_directory()

    def _scan_directory(self) -> None:
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
    __slots__ = ("meta", "path", "tier")

    def __init__(self, meta: TemplateMetadata, path: Path, tier: str) -> None:
        self.meta = meta
        self.path = path
        self.tier = tier
