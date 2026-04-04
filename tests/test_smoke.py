"""Smoke tests — verify project structure and basic imports."""

from pathlib import Path


def test_import_devolaflow():
    import devolaflow

    assert devolaflow.__version__ == "0.1.0"


def test_directory_structure(project_root: Path):
    """Verify directory skeleton matches design_dual_system.md §2.1."""
    agent_dirs = [
        "workflow-system/agent/references",
        "workflow-system/agent/templates/builtin",
        "workflow-system/agent/templates/custom",
        "workflow-system/agent/templates/derived",
        "workflow-system/agent/rules",
        "workflow-system/agent/knowledge",
        "workflow-system/agent/examples",
        "workflow-system/agent/schemas",
        "workflow-system/agent/scripts",
        "workflow-system/agent/adapters",
    ]
    for d in agent_dirs:
        assert (project_root / d).is_dir(), f"Missing agent dir: {d}"

    human_dirs = [
        "workflow-system/human/en",
        "workflow-system/human/zh",
        "workflow-system/human/demo/workflow-visualizer",
        "workflow-system/human/demo/stage-explorer",
        "workflow-system/human/shared/images",
        "workflow-system/human/shared/schema",
    ]
    for d in human_dirs:
        assert (project_root / d).is_dir(), f"Missing human dir: {d}"

    infra_dirs = ["src/devolaflow", "tests", "scripts", "schemas", "primitives/schemas"]
    for d in infra_dirs:
        assert (project_root / d).is_dir(), f"Missing infra dir: {d}"


def test_pyproject_exists(project_root: Path):
    assert (project_root / "pyproject.toml").is_file()


def test_makefile_exists(project_root: Path):
    assert (project_root / "Makefile").is_file()
