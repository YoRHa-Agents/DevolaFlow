"""Tests for the deterministic source import-cycle gate."""

from __future__ import annotations

from pathlib import Path

from scripts.check_import_graph import build_graph, find_cycles, main


def test_repository_import_graph_is_acyclic() -> None:
    """The checked-in source graph has no module-initialization cycles."""
    graph = build_graph(Path("src/devolaflow"))
    assert graph == dict(sorted(graph.items()))
    assert find_cycles(graph) == []


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
