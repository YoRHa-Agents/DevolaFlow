"""Base adapter interface.

Design ref: design_delivery_architecture.md §4.3
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class AdapterResult:
    """Result of an adapter build."""

    tool: str
    output_dir: Path
    files_created: list[str]
    budget_ok: bool
    budget_details: str


class BaseAdapter(ABC):
    """Base class for tool-specific adapters."""

    @abstractmethod
    def build(self, source: dict, agent_dir: Path, output_dir: Path) -> AdapterResult:
        """Build tool-specific output from the canonical source."""
        ...


def _find_project_root() -> Path:
    """Walk up from this file to find the project root containing pyproject.toml."""
    p = Path(__file__).resolve()
    while p != p.parent:
        if (p / "pyproject.toml").exists():
            return p
        p = p.parent
    return Path.cwd()


def load_workflow_skill(path: Path | None = None) -> tuple[dict, Path]:
    """Load and parse ``workflow-skill.yaml`` and return ``(source, agent_dir)``.

    Parameters
    ----------
    path:
        Optional explicit path to a ``workflow-skill.yaml``. When omitted, the
        canonical location under ``workflow-system/agent/`` is used (discovered
        by walking up to the project root).
    """
    if path is None:
        root = _find_project_root()
        agent_dir = root / "workflow-system" / "agent"
        skill_yaml = agent_dir / "workflow-skill.yaml"
    else:
        skill_yaml = Path(path)
        agent_dir = skill_yaml.parent

    with open(skill_yaml) as f:
        source = yaml.safe_load(f) or {}
    return source, agent_dir
