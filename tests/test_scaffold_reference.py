"""Unit tests for `scripts/scaffold_reference.py` (D-X-2)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def scaffold_reference_module():
    repo_root = Path(__file__).resolve().parent.parent
    script_path = repo_root / "scripts" / "scaffold_reference.py"
    spec = importlib.util.spec_from_file_location("scaffold_reference", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["scaffold_reference"] = module
    spec.loader.exec_module(module)
    return module


def _seed_repo(root: Path) -> None:
    (root / "pyproject.toml").write_text("[tool.test]\n", encoding="utf-8")
    (root / "workflow-system/agent/references").mkdir(parents=True)
    (root / "workflow-system/agent/SKILL.md").write_text(
        "# DevolaFlow\n\n## Reference Navigation Guide\n\n"
        "**Tier 2 — Domain references**:\n\n"
        "| File | Load When |\n"
        "|---|---|\n"
        "| `references/agent-hierarchy.md` | Layer setup |\n"
        "| `references/meta-framework.md` | Workflow primitives |\n"
        "| `references/team-roles.md` | Task agent config |\n\n"
        "**Tier 3** — On-demand:\n",
        encoding="utf-8",
    )
    (root / "workflow-system/agent/manifest.yaml").write_text(
        'schema_version: "1.0"\n'
        "core:\n"
        "  - SKILL.md\n"
        "references:\n"
        "  - references/agent-hierarchy.md\n"
        "  - references/meta-framework.md\n"
        "  - references/team-roles.md\n"
        "examples:\n"
        "  - examples/full-pipeline-trace.md\n"
        "  - examples/hotfix-trace.md\n"
        "install_profiles:\n"
        "  cursor:   {kind: skill-dir, sets: [core, references, examples]}\n",
        encoding="utf-8",
    )


def test_render_reference_md_skeleton(scaffold_reference_module, tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    plan = scaffold_reference_module.build_plan(
        "troubleshooting",
        "large",
        "operator hits an opaque error",
        repo_root=tmp_path,
    )
    body = scaffold_reference_module.render_reference_md(plan)
    assert "# Troubleshooting" in body
    assert "## Purpose" in body
    assert "## When to Load" in body
    assert "## Body" in body
    assert "## Cross-References" in body
    assert "## History" in body
    assert "operator hits an opaque error" in body


def test_dry_run_does_not_mutate(scaffold_reference_module, tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = scaffold_reference_module.main(
        [
            "troubleshooting",
            "--tier",
            "large",
            "--load-when",
            "operator hits an error",
            "--dry-run",
            "--repo-root",
            str(tmp_path),
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "[dry-run]" in out
    ref_path = tmp_path / "workflow-system/agent/references/troubleshooting.md"
    assert not ref_path.exists()
    manifest = (tmp_path / "workflow-system/agent/manifest.yaml").read_text(encoding="utf-8")
    assert "troubleshooting" not in manifest, "dry-run must not edit the install manifest"


def test_happy_path_writes_three_surfaces(scaffold_reference_module, tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = scaffold_reference_module.main(
        [
            "troubleshooting",
            "--tier",
            "large",
            "--load-when",
            "operator hits an opaque error",
            "--repo-root",
            str(tmp_path),
        ]
    )
    assert rc == 0
    ref_path = tmp_path / "workflow-system/agent/references/troubleshooting.md"
    assert ref_path.is_file()
    skill = (tmp_path / "workflow-system/agent/SKILL.md").read_text(encoding="utf-8")
    assert "`references/troubleshooting.md`" in skill
    manifest = (tmp_path / "workflow-system/agent/manifest.yaml").read_text(encoding="utf-8")
    assert "  - references/troubleshooting.md" in manifest
    ref_lines = [ln for ln in manifest.splitlines() if ln.startswith("  - references/")]
    assert ref_lines == sorted(ref_lines), "manifest references list must stay alphabetical"


def test_skill_md_alphabetical_insertion(scaffold_reference_module, tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    scaffold_reference_module.main(
        [
            "troubleshooting",
            "--tier",
            "large",
            "--load-when",
            "trigger",
            "--repo-root",
            str(tmp_path),
        ]
    )
    skill_lines = (
        (tmp_path / "workflow-system/agent/SKILL.md").read_text(encoding="utf-8").splitlines()
    )
    ref_rows = [ln for ln in skill_lines if ln.startswith("| `references/")]
    sorted_rows = sorted(ref_rows, key=lambda ln: ln.lower())
    assert ref_rows == sorted_rows, "scaffold must keep SKILL.md rows alphabetical"


def test_collision_without_force_skips_write(scaffold_reference_module, tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    ref_path = tmp_path / "workflow-system/agent/references/troubleshooting.md"
    ref_path.write_text("# stale content\n", encoding="utf-8")
    rc = scaffold_reference_module.main(
        [
            "troubleshooting",
            "--tier",
            "large",
            "--load-when",
            "trigger",
            "--repo-root",
            str(tmp_path),
        ]
    )
    assert rc == 0
    assert ref_path.read_text(encoding="utf-8") == "# stale content\n"


def test_force_overwrites(scaffold_reference_module, tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    ref_path = tmp_path / "workflow-system/agent/references/troubleshooting.md"
    ref_path.write_text("# stale\n", encoding="utf-8")
    rc = scaffold_reference_module.main(
        [
            "troubleshooting",
            "--tier",
            "large",
            "--load-when",
            "trigger",
            "--force",
            "--repo-root",
            str(tmp_path),
        ]
    )
    assert rc == 0
    body = ref_path.read_text(encoding="utf-8")
    assert "# Troubleshooting" in body
    assert "stale" not in body


def test_invalid_tier_rejected(scaffold_reference_module, tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    with pytest.raises(SystemExit, match="invalid tier"):
        scaffold_reference_module.main(
            [
                "troubleshooting",
                "--tier",
                "huge",
                "--load-when",
                "trigger",
                "--repo-root",
                str(tmp_path),
            ]
        )
