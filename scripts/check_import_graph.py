#!/usr/bin/env python3
"""Reject cycles in the ``devolaflow`` source import graph.

The check is deliberately AST-based: it does not execute application code,
depends on no import order, and produces stable output for CI diagnostics.
Only module-initialization imports resolvable to another module under
``src/devolaflow`` are included in the graph. Function-local imports are
runtime edges rather than import-initialization edges and are intentionally
excluded; this makes the gate catch real module cycles without rejecting
deliberate lazy imports at call boundaries.
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path


def module_names(package_root: Path) -> set[str]:
    """Return the fully-qualified modules represented by ``package_root``."""
    package_root = package_root.resolve()
    package_name = package_root.name
    modules: set[str] = set()
    for path in sorted(package_root.rglob("*.py")):
        relative = path.relative_to(package_root)
        parts = list(relative.with_suffix("").parts)
        if parts[-1] == "__init__":
            parts.pop()
        modules.add(".".join((package_name, *parts)))
    return modules


def _resolve_from_import(current: str, node: ast.ImportFrom, modules: set[str]) -> set[str]:
    """Resolve one ``ImportFrom`` node to local module names."""
    if node.level:
        current_parts = current.split(".")
        anchor = current_parts[: -node.level]
        base = ".".join(anchor + ([node.module] if node.module else []))
    else:
        base = node.module or ""

    resolved: set[str] = set()
    for alias in node.names:
        if alias.name == "*":
            if base in modules:
                resolved.add(base)
            continue
        candidate = f"{base}.{alias.name}" if base else alias.name
        if candidate in modules:
            resolved.add(candidate)
        elif base in modules:
            resolved.add(base)
    return resolved


def _module_level_imports(tree: ast.Module) -> list[ast.Import | ast.ImportFrom]:
    """Return imports executed while a module is initialized."""
    imports: list[ast.Import | ast.ImportFrom] = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            imports.append(node)
        elif isinstance(node, ast.If):
            imports.extend(
                child for child in node.body if isinstance(child, (ast.Import, ast.ImportFrom))
            )
    return imports


def build_graph(package_root: Path) -> dict[str, tuple[str, ...]]:
    """Build a deterministic local-import adjacency map."""
    package_root = package_root.resolve()
    modules = module_names(package_root)
    graph: dict[str, tuple[str, ...]] = {}
    for path in sorted(package_root.rglob("*.py")):
        relative = path.relative_to(package_root)
        parts = list(relative.with_suffix("").parts)
        if parts[-1] == "__init__":
            parts.pop()
        current = ".".join((package_root.name, *parts))
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        dependencies: set[str] = set()
        for node in _module_level_imports(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    candidates = alias.name.split(".")
                    for end in range(len(candidates), 0, -1):
                        candidate = ".".join(candidates[:end])
                        if candidate in modules:
                            dependencies.add(candidate)
                            break
            elif isinstance(node, ast.ImportFrom):
                dependencies.update(_resolve_from_import(current, node, modules))
        dependencies.discard(current)
        graph[current] = tuple(sorted(dependencies))
    return dict(sorted(graph.items()))


def find_cycles(graph: dict[str, tuple[str, ...]]) -> list[tuple[str, ...]]:
    """Return every directed cycle, canonically rotated and sorted."""
    state: dict[str, int] = {}
    stack: list[str] = []
    cycles: set[tuple[str, ...]] = set()

    def visit(node: str) -> None:
        state[node] = 1
        stack.append(node)
        for dependency in graph.get(node, ()):
            if state.get(dependency, 0) == 0:
                visit(dependency)
            elif state.get(dependency) == 1:
                start = stack.index(dependency)
                cycle = stack[start:]
                rotations = [tuple(cycle[i:] + cycle[:i]) for i in range(len(cycle))]
                cycles.add(min(rotations))
        stack.pop()
        state[node] = 2

    for node in sorted(graph):
        if state.get(node, 0) == 0:
            visit(node)
    return sorted(cycles)


def main(argv: list[str] | None = None) -> int:
    """Run the import-cycle gate from a repository root."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--package-root",
        type=Path,
        default=Path("src/devolaflow"),
        help="directory containing the devolaflow package (default: src/devolaflow)",
    )
    args = parser.parse_args(argv)
    try:
        cycles = find_cycles(build_graph(args.package_root))
    except (OSError, SyntaxError, ValueError) as exc:
        print(f"ERROR: import-graph check failed: {exc}", file=sys.stderr)
        return 1
    if cycles:
        print("FAIL: devolaflow import cycles detected")
        for cycle in cycles:
            print(f"  {' -> '.join((*cycle, cycle[0]))}")
        return 1
    print("PASS: devolaflow import graph is acyclic")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
