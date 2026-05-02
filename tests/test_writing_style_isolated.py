"""Hot-path import-isolation test for ``devolaflow.writing_style``.

The v10.1.0 writing-style module MUST NOT be imported (directly or
transitively) by any of the following dispatch hot-path surfaces:

* ``src/devolaflow/task_adaptive_selector.py``
* any module under ``src/devolaflow/compressor/``
* any module under ``src/devolaflow/lifecycle/``
* ``src/devolaflow/feedback.py``
* ``src/devolaflow/agent_workspace/dispatch_executor.py``

This invariant closes gap G-B4 from the v10.1.0 gap analysis and is
the informal architecture rule referenced by the user mandate C-3
("performance non-pollution"). A violation means the humanizer
pipeline would run on every agent dispatch — catastrophically
polluting the cache-prefix budget.

The test walks each hot-path module's AST for ``import`` /
``importfrom`` statements, then recurses into first-party imports
within ``devolaflow.*``, building a transitive set. If
``devolaflow.writing_style`` (or any submodule) appears in the set,
the test fails with the specific violating module path.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "src" / "devolaflow"

HOT_PATH_SURFACES: tuple[Path, ...] = (
    SRC_ROOT / "task_adaptive_selector.py",
    SRC_ROOT / "compressor",
    SRC_ROOT / "lifecycle",
    SRC_ROOT / "feedback.py",
    SRC_ROOT / "agent_workspace" / "dispatch_executor.py",
)


def _collect_modules(surface: Path) -> list[Path]:
    if surface.is_file() and surface.suffix == ".py":
        return [surface]
    if surface.is_dir():
        return sorted(p for p in surface.rglob("*.py") if "__pycache__" not in p.parts)
    return []


def _imports_in(path: Path) -> set[str]:
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return set()
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module is None:
                continue
            if node.level and node.level > 0:
                continue
            out.add(node.module)
    return out


def _module_to_path(module: str) -> Path | None:
    if not module.startswith("devolaflow"):
        return None
    rel = module.replace(".", "/")
    candidate_file = SRC_ROOT.parent / (rel + ".py")
    candidate_pkg = SRC_ROOT.parent / rel / "__init__.py"
    if candidate_file.exists():
        return candidate_file
    if candidate_pkg.exists():
        return candidate_pkg
    return None


def _transitive_imports(start: Path) -> set[str]:
    visited: set[Path] = set()
    queue: list[Path] = [start]
    modules_seen: set[str] = set()
    while queue:
        current = queue.pop()
        if current in visited:
            continue
        visited.add(current)
        for mod in _imports_in(current):
            modules_seen.add(mod)
            target = _module_to_path(mod)
            if target and target not in visited:
                queue.append(target)
    return modules_seen


@pytest.mark.parametrize(
    "surface",
    HOT_PATH_SURFACES,
    ids=lambda p: str(p.relative_to(REPO_ROOT)),
)
def test_hot_path_does_not_import_writing_style(surface: Path) -> None:
    modules = _collect_modules(surface)
    assert modules, f"no python modules found under {surface}"
    for module in modules:
        seen = _transitive_imports(module)
        offenders = sorted(m for m in seen if m.startswith("devolaflow.writing_style"))
        assert not offenders, (
            f"hot-path module {module.relative_to(REPO_ROOT)} transitively "
            f"imports writing_style ({offenders!r}); "
            "see tests/test_writing_style_isolated.py docstring"
        )


def test_writing_style_does_not_reverse_import_hot_path() -> None:
    """The writing_style package must not pull in hot-path modules
    either. This is the dual of the previous test: it guards against
    someone wiring a dispatch callback INTO the humanizer.
    """
    ws_root = SRC_ROOT / "writing_style"
    forbidden_prefixes = (
        "devolaflow.task_adaptive_selector",
        "devolaflow.compressor",
        "devolaflow.lifecycle",
        "devolaflow.feedback",
        "devolaflow.agent_workspace.dispatch_executor",
    )
    for module in _collect_modules(ws_root):
        seen = _transitive_imports(module)
        offenders = sorted(
            m for m in seen if any(m == p or m.startswith(p + ".") for p in forbidden_prefixes)
        )
        assert not offenders, (
            f"writing_style module {module.relative_to(REPO_ROOT)} pulls in "
            f"hot-path surface(s) {offenders!r}"
        )
