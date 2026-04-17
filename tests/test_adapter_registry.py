"""Tests for the AdapterRegistry and build_all --tools filtering (v6.0.4 R1)."""

from __future__ import annotations

from pathlib import Path

import pytest

from devolaflow.adapters.base import AdapterResult, BaseAdapter
from devolaflow.adapters.registry import AdapterRegistry, create_default_registry
from devolaflow.build_skill import _parse_tools_flag, build_all


class _StubAdapter(BaseAdapter):
    """Minimal adapter for registry unit tests."""

    def __init__(self, name: str = "stub") -> None:
        self.name = name

    def build(self, source: dict, agent_dir: Path, output_dir: Path) -> AdapterResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "marker.txt").write_text(self.name)
        return AdapterResult(
            tool=self.name,
            output_dir=output_dir,
            files_created=["marker.txt"],
            budget_ok=True,
            budget_details="stub: 0/0",
        )


def test_registry_register_and_get():
    reg = AdapterRegistry()
    adapter = _StubAdapter("alpha")
    reg.register("alpha", adapter, tier="core", description="alpha tool")
    assert reg.get("alpha") is adapter
    meta = reg.metadata("alpha")
    assert meta == {"tier": "core", "description": "alpha tool"}


def test_registry_list_names_returns_sorted():
    reg = AdapterRegistry()
    reg.register("zeta", _StubAdapter("zeta"))
    reg.register("alpha", _StubAdapter("alpha"))
    reg.register("mu", _StubAdapter("mu"))
    assert reg.list_names() == ["alpha", "mu", "zeta"]


def test_registry_list_by_tier():
    reg = AdapterRegistry()
    reg.register("c1", _StubAdapter("c1"), tier="core")
    reg.register("c2", _StubAdapter("c2"), tier="core")
    reg.register("hp", _StubAdapter("hp"), tier="high_priority")
    reg.register("t1", _StubAdapter("t1"), tier="tier_1")
    assert reg.list_by_tier("core") == ["c1", "c2"]
    assert reg.list_by_tier("high_priority") == ["hp"]
    assert reg.list_by_tier("tier_1") == ["t1"]
    assert reg.list_by_tier("nonexistent") == []


def test_registry_get_unknown_raises_key_error():
    reg = AdapterRegistry()
    reg.register("only", _StubAdapter("only"))
    with pytest.raises(KeyError) as exc:
        reg.get("missing")
    assert "missing" in str(exc.value)
    assert "only" in str(exc.value)


def test_registry_factory_lazy_resolution():
    created: list[_StubAdapter] = []

    def factory() -> _StubAdapter:
        inst = _StubAdapter("lazy")
        created.append(inst)
        return inst

    reg = AdapterRegistry()
    reg.register("lazy", factory)
    assert created == []
    first = reg.get("lazy")
    assert len(created) == 1
    second = reg.get("lazy")
    assert first is second
    assert len(created) == 1


def test_registry_build_selected(tmp_path: Path):
    reg = AdapterRegistry()
    reg.register("a", _StubAdapter("a"))
    reg.register("b", _StubAdapter("b"))
    reg.register("c", _StubAdapter("c"))
    dist = tmp_path / "dist"
    dist.mkdir()
    results = reg.build_selected(["a", "c"], {}, tmp_path, dist)
    assert [r.tool for r in results] == ["a", "c"]
    assert (dist / "a" / "marker.txt").exists()
    assert (dist / "c" / "marker.txt").exists()
    assert not (dist / "b").exists()


def test_create_default_registry_has_4_core():
    reg = create_default_registry()
    core = reg.list_by_tier("core")
    assert set(core) == {"cursor", "codex", "claude", "copilot"}
    assert reg.list_names() == sorted(core)


def test_parse_tools_flag_space_form():
    assert _parse_tools_flag(["--tools", "cursor,codex"]) == ["cursor", "codex"]


def test_parse_tools_flag_equals_form():
    assert _parse_tools_flag(["--tools=cursor,codex"]) == ["cursor", "codex"]


def test_parse_tools_flag_absent_returns_none():
    assert _parse_tools_flag([]) is None
    assert _parse_tools_flag(["--all"]) is None


def test_parse_tools_flag_strips_whitespace():
    assert _parse_tools_flag(["--tools", " cursor , codex "]) == ["cursor", "codex"]


def test_build_all_with_tools_flag_filters(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    results = build_all(["--tools", "cursor,claude"])
    tools = [r.tool for r in results]
    assert tools == ["cursor", "claude"] or sorted(tools) == ["claude", "cursor"]
    assert (tmp_path / "dist" / "cursor").exists()
    assert (tmp_path / "dist" / "claude").exists()
    assert not (tmp_path / "dist" / "codex").exists()
    assert not (tmp_path / "dist" / "copilot").exists()


def test_build_all_without_tools_builds_all(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    results = build_all([])
    tools = {r.tool for r in results}
    # The 4 core adapters must always be present.
    assert {"cursor", "codex", "claude", "copilot"}.issubset(tools)
    for t in tools:
        assert (tmp_path / "dist" / t).exists()


def test_build_all_unknown_tool_exits_nonzero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit) as exc:
        build_all(["--tools", "totally-unknown"])
    assert exc.value.code == 2


def test_build_all_accepts_injected_registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    reg = AdapterRegistry()
    reg.register("stub1", _StubAdapter("stub1"))
    reg.register("stub2", _StubAdapter("stub2"))
    results = build_all([], registry=reg)
    assert {r.tool for r in results} == {"stub1", "stub2"}
