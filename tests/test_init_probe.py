"""Tests for Track C-4 — init-chain dependency tiering + unified probe.

Pins ``devolaflow.init_probe``: the single-owner dependency tier table
(R5 F4 — "环境依赖缺失导致固定脚本无法生成") and the pre-flight
capability probe wired into ``devola-init local`` + the doctor.

NO subprocess. NO network. shutil.which is monkeypatched.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

from devolaflow import init_probe
from devolaflow.init_probe import (
    INIT_DEPENDENCIES,
    MissingRequiredDependencyError,
    assert_required_present,
    format_capability_table,
    missing_required,
    probe_capabilities,
)

_REPO_ROOT: Path = Path(__file__).resolve().parent.parent


def _probe_with(monkeypatch: pytest.MonkeyPatch, present: set[str]) -> list:
    """Probe with shutil.which faked to report only *present* binaries."""
    monkeypatch.setattr(
        init_probe.shutil,
        "which",
        lambda name: f"/fake/bin/{name}" if name in present else None,
    )
    return probe_capabilities()


class TestDependencyTierTable:
    def test_git_is_the_only_required_dependency(self) -> None:
        """Per 05-init-quality-fixes §5.1: required = git; everything else degrades."""
        required = [d.name for d in INIT_DEPENDENCIES if d.tier == "required"]
        assert required == ["git"]

    def test_optional_tier_covers_the_r5_f4_inventory(self) -> None:
        optional = {d.name for d in INIT_DEPENDENCIES if d.tier == "optional"}
        assert optional == {"node", "npm", "codegraph", "nines"}
        situational = {d.name for d in INIT_DEPENDENCIES if d.tier == "situational"}
        assert situational == {"curl"}

    def test_every_dependency_carries_a_single_line_hint(self) -> None:
        """Acceptance: one clear hint per missing dep, never a stack trace."""
        for dep in INIT_DEPENDENCIES:
            assert dep.absent_hint.strip(), f"{dep.name} missing absent_hint"
            assert "\n" not in dep.absent_hint, f"{dep.name} hint must be ONE line"


class TestProbeAndGate:
    def test_missing_required_git_raises_with_hint(self, monkeypatch: pytest.MonkeyPatch) -> None:
        findings = _probe_with(monkeypatch, present={"node", "npm"})
        assert [f.spec.name for f in missing_required(findings)] == ["git"]
        with pytest.raises(MissingRequiredDependencyError) as excinfo:
            assert_required_present(findings)
        message = str(excinfo.value)
        assert "git" in message
        assert "Nothing was scaffolded" in message

    def test_all_present_passes_gate_silently(self, monkeypatch: pytest.MonkeyPatch) -> None:
        findings = _probe_with(monkeypatch, present={d.name for d in INIT_DEPENDENCIES})
        assert missing_required(findings) == []
        assert_required_present(findings)  # must not raise

    def test_capability_table_prints_one_hint_per_gap(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        findings = _probe_with(monkeypatch, present={"git"})
        table = format_capability_table(findings)
        assert "ok (/fake/bin/git)" in table
        # Each missing optional dep surfaces its verbatim hint exactly once.
        for dep in INIT_DEPENDENCIES:
            if dep.name == "git":
                continue
            assert table.count(dep.absent_hint) == 1, (
                f"{dep.name} hint must appear exactly once in the table"
            )


def test_init_chain_modules_are_stdlib_only() -> None:
    """Track C-4 脚本标准库化: the deterministic init chain imports stdlib only.

    Walks the top-level imports of the init-chain modules (scaffold,
    markers, probe) and asserts every imported root package is either
    stdlib or devolaflow itself — a third-party import here would
    reintroduce the exact F4 failure class (init breaks when an external
    package is missing).
    """
    init_chain = [
        _REPO_ROOT / "src/devolaflow/local/workspace.py",
        _REPO_ROOT / "src/devolaflow/codegraph/markers.py",
        _REPO_ROOT / "src/devolaflow/init_probe.py",
    ]
    allowed_roots = set(sys.stdlib_module_names) | {"devolaflow", "__future__"}
    for module_path in init_chain:
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            roots: list[str] = []
            if isinstance(node, ast.Import):
                roots = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                roots = [node.module.split(".")[0]]
            for root in roots:
                assert root in allowed_roots, (
                    f"{module_path.name} imports third-party package {root!r} — "
                    "the init chain must stay stdlib-only (Track C-4)."
                )
