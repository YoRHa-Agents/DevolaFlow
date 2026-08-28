"""Tests for the deterministic source import-cycle gate."""

from __future__ import annotations

import ast
from pathlib import Path

from scripts.check_import_graph import build_graph, find_cycles, main


def test_repository_import_graph_is_acyclic() -> None:
    """The checked-in source graph has no module-initialization cycles."""
    graph = build_graph(Path("src/devolaflow"))
    assert graph == dict(sorted(graph.items()))
    assert find_cycles(graph) == []


def test_build_graph_collects_nested_module_initialization_imports(tmp_path: Path) -> None:
    """Compound module-level blocks contribute imports, but function locals do not."""
    package = tmp_path / "devolaflow"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    dependencies = {
        "try_body",
        "except_body",
        "try_else",
        "try_finally",
        "with_body",
        "for_body",
        "for_else",
        "while_body",
        "while_else",
        "nested_if",
    }
    try_star_source = ""
    if hasattr(ast, "TryStar"):
        dependencies.update({"try_star_body", "except_star"})
        try_star_source = """
try:
    from . import try_star_body
except* Exception:
    from . import except_star
"""
    source = (
        """
try:
    from . import try_body
    with object():
        from . import with_body
        for _ in ():
            from . import for_body
            while False:
                from . import while_body
                if False:
                    from . import nested_if
            else:
                from . import while_else
        else:
            from . import for_else
except Exception:
    from . import except_body
else:
    from . import try_else
finally:
    from . import try_finally

def lazy_import():
    from . import lazy
    try:
        from . import nested_lazy
    except Exception:
        from . import nested_lazy_handler
"""
        + try_star_source
    )
    (package / "a.py").write_text(source, encoding="utf-8")
    for module in (*dependencies, "lazy", "nested_lazy", "nested_lazy_handler"):
        (package / f"{module}.py").write_text("", encoding="utf-8")

    graph = build_graph(package)

    assert graph["devolaflow.a"] == tuple(sorted(f"devolaflow.{name}" for name in dependencies))


def test_find_cycles_returns_canonical_deterministic_cycle(tmp_path: Path) -> None:
    """Cycles are reported once, in stable lexical rotation."""
    package = tmp_path / "devolaflow"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "a.py").write_text("from . import b\n", encoding="utf-8")
    (package / "b.py").write_text("from . import a\n", encoding="utf-8")

    graph = build_graph(package)

    assert find_cycles(graph) == [("devolaflow.a", "devolaflow.b")]


def test_main_rejects_cycle_and_accepts_acyclic_graph(tmp_path: Path, capsys) -> None:
    """The CLI emits a deterministic failure and success status."""
    package = tmp_path / "devolaflow"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "a.py").write_text("from . import b\n", encoding="utf-8")
    (package / "b.py").write_text("from . import a\n", encoding="utf-8")

    assert main(["--package-root", str(package)]) == 1
    assert "devolaflow.a -> devolaflow.b -> devolaflow.a" in capsys.readouterr().out

    (package / "b.py").write_text("VALUE = 1\n", encoding="utf-8")
    assert main(["--package-root", str(package)]) == 0
    assert "acyclic" in capsys.readouterr().out
