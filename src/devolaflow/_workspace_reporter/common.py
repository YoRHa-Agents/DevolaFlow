"""Shared imports and constants for the legacy compatibility split."""

# ruff: noqa: F401, E402

from __future__ import annotations

import argparse
import contextlib
import json
import logging
import re
import sys
from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Final

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from devolaflow.agent_workspace.change import (
    ACTIVE_DIR_DEFAULT,
    ARCHIVE_DIR_DEFAULT,
    Change,
    ChangeNotFoundError,
    ChangeStore,
)
from devolaflow.agent_workspace.delta_parser import (
    DELTA_SECTION_KINDS,
    DeltaSpecParseError,
    parse_delta_spec,
)
from devolaflow.agent_workspace.handoff import (
    HANDOFF_DIR_DEFAULT,
    HandoffEnvelope,
    HandoffStore,
    HandoffStoreError,
)
from devolaflow.agent_workspace.lint import (
    HumanBudgetExceededError,
    enforce_digest_budget,
)
from devolaflow.agent_workspace.requirements_trace import (
    RequirementTraceResult,
    trace_requirements,
)

logger = logging.getLogger(__name__)

WORKSPACE_REPORT_PATH_DEFAULT: Final[Path] = Path(".local") / ".agent" / "REPORT.md"

MEMORY_REPORT_PATH_DEFAULT: Final[Path] = Path(".local") / "memory" / "REPORT.md"

RULES_REPORT_PATH_DEFAULT: Final[Path] = Path(".rules") / "REPORT.md"

HUMAN_OUTPUT_DIR_DEFAULT: Final[Path] = Path(".local") / "human" / "output"

HUMAN_DIGEST_PATH_DEFAULT: Final[Path] = HUMAN_OUTPUT_DIR_DEFAULT / "DIGEST.md"

HUMAN_STATUS_PASSED: Final[str] = "passed"

HUMAN_STATUS_GAPS_FOUND: Final[str] = "gaps_found"

HUMAN_STATUS_HUMAN_NEEDED: Final[str] = "human_needed"

_BLOCKING_SEVERITIES: Final[frozenset[str]] = frozenset({"blocker", "critical"})

_ADVISORY_SEVERITIES: Final[frozenset[str]] = frozenset({"major", "minor", "info"})

DEFAULT_ARCHIVE_WINDOW_DAYS: Final[int] = 7

DEFAULT_MEMORY_WINDOW_DAYS: Final[int] = 30

DEFAULT_TOP_LEARNINGS: Final[int] = 10

RULES_LAYERS: Final[tuple[tuple[str, str], ...]] = (
    ("Soul (P0)", "soul.mdc"),
    ("Architecture (P1)", "architecture.mdc"),
    ("Conventions (P2)", "conventions.mdc"),
    ("Workflow (P3)", "workflow.mdc"),
    ("Style (P4)", "style.mdc"),
)

_RULE_HEADING_RE: Final[re.Pattern[str]] = re.compile(r"^#+ [A-Z]{1,3}-\d+\b")

_WHY_HEADING_RE: Final[re.Pattern[str]] = re.compile(r"^##\s+Why\s*$")

_TASK_GROUP_RE: Final[re.Pattern[str]] = re.compile(r"^##\s+(G\d+:\s+.+)$")

_ARCHIVE_DATE_PREFIX_RE: Final[re.Pattern[str]] = re.compile(r"^(\d{4}-\d{2}-\d{2})-")

__all__ = [
    name
    for name in globals()
    if name not in {"__name__", "__package__", "__loader__", "__spec__", "__builtins__", "__all__"}
]
