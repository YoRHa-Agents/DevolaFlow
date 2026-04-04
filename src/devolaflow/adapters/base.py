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


def load_workflow_skill(path: Path) -> dict:
    """Load and parse workflow-skill.yaml."""
    with open(path) as f:
        return yaml.safe_load(f)
