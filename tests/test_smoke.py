"""Smoke tests -- verify project structure and basic imports."""

from pathlib import Path


def test_import_devolaflow():
    import devolaflow

    assert devolaflow.__version__ == "8.4.4"


def test_directory_structure(project_root: Path):
    """Verify directory skeleton.

    Agent content dirs hold only .md/.yaml files that agents read.
    Code, schemas, and scripts live at project root or in src/.
    """
    agent_content_dirs = [
        "workflow-system/agent/references",
        "workflow-system/agent/templates/builtin",
        "workflow-system/agent/templates/custom",
        "workflow-system/agent/templates/derived",
        "workflow-system/agent/knowledge",
        "workflow-system/agent/examples",
    ]
    for d in agent_content_dirs:
        assert (project_root / d).is_dir(), f"Missing agent dir: {d}"

    human_dirs = [
        "workflow-system/human/en",
        "workflow-system/human/zh",
        "workflow-system/human/demo/workflow-visualizer",
        "workflow-system/human/demo/stage-explorer",
        "workflow-system/human/demo/design-architecture",
        "workflow-system/human/shared/images",
    ]
    for d in human_dirs:
        assert (project_root / d).is_dir(), f"Missing human dir: {d}"

    infra_dirs = [
        "src/devolaflow",
        "src/devolaflow/template_engine",
        "src/devolaflow/pre_decision",
        "src/devolaflow/gate",
        "src/devolaflow/adapters",
        "tests",
        "scripts",
        "schemas",
        "schemas/primitives",
    ]
    for d in infra_dirs:
        assert (project_root / d).is_dir(), f"Missing infra dir: {d}"


def test_pyproject_exists(project_root: Path):
    assert (project_root / "pyproject.toml").is_file()


def test_makefile_exists(project_root: Path):
    assert (project_root / "Makefile").is_file()
