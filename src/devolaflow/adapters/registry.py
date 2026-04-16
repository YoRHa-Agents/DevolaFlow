"""Adapter registry — discoverable, extensible adapter collection."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path

from devolaflow.adapters.base import AdapterResult, BaseAdapter


class AdapterRegistry:
    """Central registry for all platform adapters.

    Adapters are registered by name (e.g. ``"cursor"``, ``"kimicode"``). The
    registry supports selective builds via :meth:`build_selected` and
    auto-discovery via :func:`create_default_registry`.
    """

    def __init__(self) -> None:
        self._adapters: dict[str, BaseAdapter | Callable[[], BaseAdapter]] = {}
        self._metadata: dict[str, dict] = {}

    def register(
        self,
        name: str,
        adapter: BaseAdapter | Callable[[], BaseAdapter],
        *,
        tier: str = "core",
        description: str = "",
    ) -> None:
        """Register an adapter instance or factory under *name*."""
        self._adapters[name] = adapter
        self._metadata[name] = {"tier": tier, "description": description}

    def get(self, name: str) -> BaseAdapter:
        """Return the adapter instance for *name*.

        Raises :class:`KeyError` when *name* is not registered. Callable
        factories are resolved lazily on first access.
        """
        if name not in self._adapters:
            raise KeyError(f"Unknown adapter: {name!r}. Available: {sorted(self._adapters)}")
        entry = self._adapters[name]
        if isinstance(entry, BaseAdapter):
            return entry
        if callable(entry):
            resolved = entry()
            self._adapters[name] = resolved
            return resolved
        return entry

    def list_names(self) -> list[str]:
        """Return all registered adapter names, sorted alphabetically."""
        return sorted(self._adapters)

    def list_by_tier(self, tier: str) -> list[str]:
        """Return adapter names whose metadata tier matches *tier*."""
        return sorted(n for n, m in self._metadata.items() if m.get("tier") == tier)

    def metadata(self, name: str) -> dict:
        """Return a copy of the metadata dict registered for *name*."""
        return dict(self._metadata.get(name, {}))

    def build_selected(
        self,
        names: Iterable[str],
        source: dict,
        agent_dir: Path,
        dist: Path,
    ) -> list[AdapterResult]:
        """Build the specified adapters; each writes into ``dist/<name>/``."""
        results: list[AdapterResult] = []
        for n in names:
            adapter = self.get(n)
            out_dir = dist / n
            result = adapter.build(source, agent_dir, out_dir)
            results.append(result)
        return results


def create_default_registry() -> AdapterRegistry:
    """Return a registry pre-populated with all built-in core adapters."""
    from devolaflow.adapters.claude_adapter import ClaudeAdapter
    from devolaflow.adapters.codex_adapter import CodexAdapter
    from devolaflow.adapters.copilot_adapter import CopilotAdapter
    from devolaflow.adapters.cursor_adapter import CursorAdapter

    reg = AdapterRegistry()
    reg.register("cursor", CursorAdapter(), tier="core", description="Cursor IDE")
    reg.register("codex", CodexAdapter(), tier="core", description="OpenAI Codex")
    reg.register("claude", ClaudeAdapter(), tier="core", description="Claude Code")
    reg.register("copilot", CopilotAdapter(), tier="core", description="GitHub Copilot")
    return reg
