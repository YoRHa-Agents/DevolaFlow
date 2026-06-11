"""Unit tests for `scripts/scaffold_template.py` (D-X-1)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def scaffold_template_module():
    repo_root = Path(__file__).resolve().parent.parent
    script_path = repo_root / "scripts" / "scaffold_template.py"
    spec = importlib.util.spec_from_file_location("scaffold_template", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["scaffold_template"] = module
    spec.loader.exec_module(module)
    return module


def _seed_repo(root: Path) -> None:
    """Build a minimal in-tmp DevolaFlow tree the scaffolder can mutate."""
    (root / "pyproject.toml").write_text("[tool.test]\n", encoding="utf-8")
    (root / "workflow-system/agent/templates/builtin").mkdir(parents=True)
    (root / "workflow-system/agent/references").mkdir(parents=True)
    (root / "tests").mkdir(parents=True)
    (root / "workflow-system/agent/templates/registry.yaml").write_text(
        'schema_version: "1.0"\n\ntemplates:\n  - name: hotfix\n    path: builtin/hotfix.yaml\n',
        encoding="utf-8",
    )
    (root / "workflow-system/agent/references/meta-framework.md").write_text(
        "## 4. Alias Mapping Table\n\n| Alias | Maps To | Workflow |\n|---|---|---|\n"
        "| fix | implement | hotfix |\n\n"
        "**Composition operators**: sequence, parallel.\n\n"
        "### Template Quick-Reference — Gate Types\n\n"
        "| Template | Gate Type |\n"
        "|----------|-----------|\n"
        "| hotfix | standard |\n\n"
        "## 5. Next section\n",
        encoding="utf-8",
    )
    (root / "workflow-system/agent/references/team-roles.md").write_text(
        "## 7. Team Participation Matrix\n\n"
        "| Workflow Type | Research | Design | Implement | Test | Review |\n"
        "|---|---|---|---|---|---|\n"
        "| hotfix | — | — | **Primary** | Active | Minimal |\n\n"
        "**Primary** = drives the stage. — = not involved.\n",
        encoding="utf-8",
    )


def test_render_builtin_yaml_includes_primitives(scaffold_template_module, tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    plan = scaffold_template_module.build_plan(
        "demo-flow",
        ["analyze", "implement", "test"],
        "build",
        ["demo", "scaffold"],
        repo_root=tmp_path,
    )
    yaml_text = scaffold_template_module.render_builtin_yaml(plan)
    assert "name: demo-flow" in yaml_text
    assert "primitive: analyze" in yaml_text
    assert "primitive: implement" in yaml_text
    assert "primitive: test" in yaml_text
    assert "compose: sequence" in yaml_text


def test_dry_run_produces_no_writes(scaffold_template_module, tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = scaffold_template_module.main(
        [
            "demo-flow",
            "--primitives",
            "analyze,implement",
            "--category",
            "build",
            "--repo-root",
            str(tmp_path),
            "--dry-run",
        ]
    )
    assert rc == 0
    captured = capsys.readouterr().out
    assert "[dry-run]" in captured
    assert "primitive: analyze" in captured
    yaml_path = tmp_path / "workflow-system/agent/templates/builtin/demo-flow.yaml"
    assert not yaml_path.exists(), "dry-run must not write the builtin yaml"
    test_path = tmp_path / "tests/test_demo_flow_template.py"
    assert not test_path.exists(), "dry-run must not write the test skeleton"


def test_happy_path_creates_all_surfaces(scaffold_template_module, tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = scaffold_template_module.main(
        [
            "demo-flow",
            "--primitives",
            "analyze,implement,test",
            "--category",
            "build",
            "--tags",
            "demo,scaffold",
            "--repo-root",
            str(tmp_path),
        ]
    )
    assert rc == 0
    yaml_path = tmp_path / "workflow-system/agent/templates/builtin/demo-flow.yaml"
    assert yaml_path.is_file()
    text = yaml_path.read_text(encoding="utf-8")
    assert "name: demo-flow" in text
    registry = (tmp_path / "workflow-system/agent/templates/registry.yaml").read_text(
        encoding="utf-8"
    )
    assert "name: demo-flow" in registry
    meta_framework = (tmp_path / "workflow-system/agent/references/meta-framework.md").read_text(
        encoding="utf-8"
    )
    assert "| analyze | analyze | demo-flow |" in meta_framework, (
        "scaffolder must insert the §4 alias-mapping rows"
    )
    quick_ref_section = meta_framework.split("### Template Quick-Reference — Gate Types", 1)[1]
    quick_ref_table = quick_ref_section.split("## 5.", 1)[0]
    assert "| demo-flow | standard |" in quick_ref_table, (
        "scaffolder must insert the gate-type row into the meta-framework.md §4 "
        "quick-reference table (retargeted from SKILL.md at v14.5.0 G-019)"
    )
    team_roles = (tmp_path / "workflow-system/agent/references/team-roles.md").read_text(
        encoding="utf-8"
    )
    assert "| demo-flow |" in team_roles
    test_file = tmp_path / "tests/test_demo_flow_template.py"
    assert test_file.is_file()
    test_content = test_file.read_text(encoding="utf-8")
    assert 'metadata"]["name"] == "demo-flow"' in test_content


def test_collision_detection_without_force(scaffold_template_module, tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    yaml_path = tmp_path / "workflow-system/agent/templates/builtin/hotfix.yaml"
    yaml_path.write_text("# already exists\n", encoding="utf-8")
    rc = scaffold_template_module.main(
        [
            "hotfix",
            "--primitives",
            "analyze,implement",
            "--category",
            "build",
            "--repo-root",
            str(tmp_path),
        ]
    )
    assert rc == 0
    assert yaml_path.read_text(encoding="utf-8") == "# already exists\n", (
        "without --force, scaffolder must NOT overwrite the existing yaml"
    )


def test_force_flag_overwrites_existing_yaml(scaffold_template_module, tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    yaml_path = tmp_path / "workflow-system/agent/templates/builtin/hotfix.yaml"
    yaml_path.write_text("# stale\n", encoding="utf-8")
    rc = scaffold_template_module.main(
        [
            "hotfix",
            "--primitives",
            "analyze,implement",
            "--category",
            "build",
            "--force",
            "--repo-root",
            str(tmp_path),
        ]
    )
    assert rc == 0
    new_text = yaml_path.read_text(encoding="utf-8")
    assert "name: hotfix" in new_text
    assert "stale" not in new_text


def test_invalid_primitive_rejected(scaffold_template_module, tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    with pytest.raises(SystemExit, match="unknown primitive"):
        scaffold_template_module.main(
            [
                "demo-flow",
                "--primitives",
                "analyze,bogus",
                "--category",
                "build",
                "--repo-root",
                str(tmp_path),
            ]
        )


def test_invalid_name_rejected(scaffold_template_module, tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    with pytest.raises(SystemExit, match="invalid template name"):
        scaffold_template_module.main(
            [
                "Demo_Flow",
                "--primitives",
                "analyze",
                "--category",
                "build",
                "--repo-root",
                str(tmp_path),
            ]
        )


def test_w18_stanza_includes_template_name(scaffold_template_module, tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    plan = scaffold_template_module.build_plan(
        "demo-flow",
        ["analyze", "implement"],
        "build",
        [],
        repo_root=tmp_path,
    )
    stanza = scaffold_template_module.render_w18_stanza(plan)
    assert "test_template_demo_flow_present" in stanza
    assert "name: demo-flow" in stanza
