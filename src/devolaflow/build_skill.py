"""Build skill outputs via the adapter registry.

Design ref: design_delivery_architecture.md §§4.3-4.5

Without ``--tools``: builds every registered adapter (4 core + any YAML-driven
adapters discovered under ``adapter_configs/``).

With ``--tools cursor,kimicode``: builds only the named adapters.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path

from devolaflow.adapters.base import AdapterResult, _find_project_root, load_workflow_skill
from devolaflow.adapters.registry import AdapterRegistry, create_default_registry

__all__ = ["_find_project_root", "build_all"]


def _parse_tools_flag(args: Sequence[str]) -> list[str] | None:
    """Parse ``--tools cursor,codex`` from *args*.

    Returns ``None`` when the flag is absent so callers can distinguish
    "build everything" from "build an empty explicit list".
    """
    for i, a in enumerate(args):
        if a == "--tools" and i + 1 < len(args):
            return [n.strip() for n in args[i + 1].split(",") if n.strip()]
        if a.startswith("--tools="):
            return [n.strip() for n in a.split("=", 1)[1].split(",") if n.strip()]
    return None


def _load_with_extensions(registry: AdapterRegistry) -> AdapterRegistry:
    """Load YAML-configured adapters from ``adapter_configs/`` (D1)."""
    from devolaflow.adapters.data_driven import load_data_driven_adapters

    load_data_driven_adapters(registry)
    return registry


def _print_results(results: list[AdapterResult]) -> None:
    for r in results:
        status = "OK" if r.budget_ok else "WARN"
        print(f"[{status}] {r.tool}: {r.budget_details} ({len(r.files_created)} files)")
    passed = sum(1 for r in results if r.budget_ok)
    print(f"\n{passed} passed, {len(results) - passed} warned, {len(results)} total")


def build_all(
    args: Sequence[str] = (),
    registry: AdapterRegistry | None = None,
) -> list[AdapterResult]:
    """Build adapters from ``workflow-skill.yaml``.

    Parameters
    ----------
    args:
        CLI-style arguments. ``--tools a,b,c`` selects a subset.
    registry:
        Optional registry override (useful for tests). When omitted, a default
        registry is created and YAML extensions are loaded.
    """
    if registry is None:
        registry = _load_with_extensions(create_default_registry())

    try:
        source, agent_dir = load_workflow_skill()
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return []

    dist = Path("dist")
    dist.mkdir(exist_ok=True)

    selected = _parse_tools_flag(args)
    names = selected if selected is not None else registry.list_names()

    available = registry.list_names()
    unknown = [n for n in names if n not in available]
    if unknown:
        print(
            f"Unknown adapters: {unknown}. Available: {available}",
            file=sys.stderr,
        )
        sys.exit(2)

    results = registry.build_selected(names, source, agent_dir, dist)
    _print_results(results)
    return results


if __name__ == "__main__":
    build_all(sys.argv[1:])
