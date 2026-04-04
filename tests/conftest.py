"""Shared test fixtures for DevolaFlow."""

from pathlib import Path

import pytest


@pytest.fixture
def project_root() -> Path:
    """Return the project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture
def design_docs_dir(project_root: Path) -> Path:
    """Return the design docs directory."""
    return project_root / "doc" / "designs"


@pytest.fixture
def templates_dir(project_root: Path) -> Path:
    """Return the built-in templates directory."""
    return project_root / "workflow-system" / "agent" / "templates" / "builtin"


@pytest.fixture
def schemas_dir(project_root: Path) -> Path:
    """Return the schemas directory."""
    return project_root / "schemas"
