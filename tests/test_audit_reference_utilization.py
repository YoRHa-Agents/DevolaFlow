"""Unit tests for `scripts/audit_reference_utilization.py` (D-D-1)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def audit_module():
    repo_root = Path(__file__).resolve().parent.parent
    script_path = repo_root / "scripts" / "audit_reference_utilization.py"
    spec = importlib.util.spec_from_file_location("audit_reference_utilization", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["audit_reference_utilization"] = module
    spec.loader.exec_module(module)
    return module


class _StubSelector:
    """Deterministic stub of `task_adaptive_selector.select_context`."""

    def __init__(self, mapping: dict[tuple[str, int], list[str]]) -> None:
        self._mapping = mapping

    def select_context(self, task_type: str, *, profiles_path, round_num: int = 1):
        return {
            "extra_context": list(self._mapping.get((task_type, round_num), [])),
        }


def _seed_profiles(path: Path) -> None:
    path.write_text(
        "profiles:\n"
        "  hotfix:\n"
        "    description: hot\n"
        "  feature:\n"
        "    description: feat\n"
        "  research:\n"
        "    description: res\n",
        encoding="utf-8",
    )


def _seed_references(repo_root: Path) -> None:
    refs_dir = repo_root / "workflow-system/agent/references"
    refs_dir.mkdir(parents=True)
    (refs_dir / "agent-hierarchy.md").write_text(
        "# Agent Hierarchy\nSee `references/meta-framework.md`.\n",
        encoding="utf-8",
    )
    (refs_dir / "meta-framework.md").write_text(
        "# Meta\nSee `references/agent-hierarchy.md` and `references/team-roles.md`.\n",
        encoding="utf-8",
    )
    (refs_dir / "team-roles.md").write_text(
        "# Team Roles\nNo cross-refs.\n",
        encoding="utf-8",
    )


def _seed_pyproject(repo_root: Path) -> None:
    (repo_root / "pyproject.toml").write_text("[tool.test]\n", encoding="utf-8")


def test_replay_matrix_aggregates_correctly(audit_module, tmp_path: Path) -> None:
    _seed_pyproject(tmp_path)
    _seed_references(tmp_path)
    profiles_path = tmp_path / "context_profiles.yaml"
    _seed_profiles(profiles_path)

    selector = _StubSelector(
        {
            ("hotfix", 1): ["references/agent-hierarchy.md"],
            ("hotfix", 2): ["references/agent-hierarchy.md"],
            ("hotfix", 3): ["references/agent-hierarchy.md"],
            ("hotfix", 4): ["references/agent-hierarchy.md"],
            ("hotfix", 5): ["references/agent-hierarchy.md"],
            ("feature", 1): [
                "references/agent-hierarchy.md",
                "references/meta-framework.md",
            ],
            ("feature", 2): [
                "references/agent-hierarchy.md",
                "references/meta-framework.md",
            ],
            ("feature", 3): [
                "references/agent-hierarchy.md",
                "references/meta-framework.md",
            ],
            ("feature", 4): [
                "references/agent-hierarchy.md",
                "references/meta-framework.md",
            ],
            ("feature", 5): [
                "references/agent-hierarchy.md",
                "references/meta-framework.md",
            ],
            ("research", 1): ["references/team-roles.md"],
            ("research", 2): ["references/team-roles.md"],
            ("research", 3): ["references/team-roles.md"],
            ("research", 4): ["references/team-roles.md"],
            ("research", 5): ["references/team-roles.md"],
        }
    )
    report = audit_module.build_report(
        repo_root=tmp_path, profiles_path=profiles_path, selector_module=selector
    )
    assert report.total_cells == 15
    assert report.cells_loaded["agent-hierarchy.md"] == 10
    assert report.cells_loaded["meta-framework.md"] == 5
    assert report.cells_loaded["team-roles.md"] == 5


def test_render_markdown_contains_table_rows(audit_module, tmp_path: Path) -> None:
    _seed_pyproject(tmp_path)
    _seed_references(tmp_path)
    profiles_path = tmp_path / "context_profiles.yaml"
    _seed_profiles(profiles_path)
    selector = _StubSelector({("hotfix", 1): ["references/meta-framework.md"]})
    report = audit_module.build_report(
        repo_root=tmp_path, profiles_path=profiles_path, selector_module=selector
    )
    md = audit_module.render_markdown(report)
    assert "# Reference Doc Utilization Audit" in md
    assert "| `references/meta-framework.md` |" in md
    assert "| # | Reference | Cells loaded" in md


def test_render_json_emits_valid_payload(audit_module, tmp_path: Path) -> None:
    _seed_pyproject(tmp_path)
    _seed_references(tmp_path)
    profiles_path = tmp_path / "context_profiles.yaml"
    _seed_profiles(profiles_path)
    selector = _StubSelector({("hotfix", 1): ["references/team-roles.md"]})
    report = audit_module.build_report(
        repo_root=tmp_path, profiles_path=profiles_path, selector_module=selector
    )
    out = audit_module.render_json(report)
    payload = json.loads(out)
    assert "cells_loaded" in payload
    assert "matrix" in payload
    assert payload["total_cells"] >= 1


def test_cross_ref_density_counts_inbound_links(audit_module, tmp_path: Path) -> None:
    _seed_pyproject(tmp_path)
    _seed_references(tmp_path)
    refs = tmp_path / "workflow-system/agent/references"
    counts = audit_module.measure_cross_refs(refs)
    assert counts.get("meta-framework.md", 0) == 1
    assert counts.get("agent-hierarchy.md", 0) == 1


def test_main_writes_to_output_path(audit_module, tmp_path: Path) -> None:
    _seed_pyproject(tmp_path)
    _seed_references(tmp_path)
    profiles_path = tmp_path / "context_profiles.yaml"
    _seed_profiles(profiles_path)

    real_import = audit_module._import_selector

    def fake_import(_):
        return _StubSelector(
            {(t, n): [] for t in ("hotfix", "feature", "research") for n in range(1, 6)}
        )

    audit_module._import_selector = fake_import
    try:
        out_path = tmp_path / "out.md"
        rc = audit_module.main(
            [
                "--profiles-path",
                str(profiles_path),
                "--repo-root",
                str(tmp_path),
                "--output",
                str(out_path),
            ]
        )
        assert rc == 0
        assert out_path.is_file()
        body = out_path.read_text(encoding="utf-8")
        assert "Reference Doc Utilization Audit" in body
    finally:
        audit_module._import_selector = real_import


def test_long_tail_threshold_uses_20pct(audit_module, tmp_path: Path) -> None:
    _seed_pyproject(tmp_path)
    _seed_references(tmp_path)
    profiles_path = tmp_path / "context_profiles.yaml"
    _seed_profiles(profiles_path)
    selector = _StubSelector(
        {("hotfix", n): ["references/agent-hierarchy.md"] for n in range(1, 6)}
        | {("feature", n): [] for n in range(1, 6)}
        | {("research", n): [] for n in range(1, 6)}
    )
    report = audit_module.build_report(
        repo_root=tmp_path, profiles_path=profiles_path, selector_module=selector
    )
    assert report.total_cells == 15
    assert "team-roles.md" in report.long_tail
    assert "meta-framework.md" in report.long_tail
