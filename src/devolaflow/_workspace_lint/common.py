"""Shared imports and constants for workspace linting."""

# ruff: noqa: F401, E402

from __future__ import annotations

import argparse
import hashlib
import logging
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

logger = logging.getLogger(__name__)

CHECKLIST_ARTIFACT_BUDGETS: Final[dict[str, tuple[int, int]]] = {
    "goal.md": (200, 400),
    "checklist.md": (1200, 2400),
    "stage.md": (400, 800),
    "preflight.md": (600, 1200),
    "spec.md": (1500, 3000),
    "STATUS.yaml": (150, 300),
    "owned_files.txt": (50, 100),
    # OPTIONAL harness pre-analysis artifact per the harness-construction
    # design (.local/tasks/add_harness_design/design.md §3.3): its presence
    # flags the change as harness-flagged; absence is a valid state that
    # yields zero findings and zero budget violations.
    "harness_preflight.md": (800, 1600),
    # Agent onboarding entry point (.local/research/v17.2.0_change_entrance_design.md
    # §4): scaffolded for every new change. Absence in a pre-v17.2 folder is a
    # WARN (ENTRANCE_MISSING) until backfilled on first resume — see
    # _check_entrance for the semantic checks.
    "entrance.md": (400, 800),
    # Optional read-only look-ahead artifact per the Pathfinder role contract.
    "pathfinder_report.md": (800, 1600),
}

LEARNINGS_JSONL_MAX_BYTES: Final[int] = 50 * 1024

EVIDENCE_FILE_MAX_BYTES: Final[int] = 10_240

EVIDENCE_DIRECTORY_MAX_BYTES: Final[int] = 51_200

_UTC_TIMESTAMP_RE: Final[re.Pattern[str]] = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

_SHA256_RE: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")

_GOAL_ENTRY_RE: Final[re.Pattern[str]] = re.compile(
    r"^- (G(?:[1-9]|10)): (.+) → checklist\.md ## (G(?:[1-9]|10))\s*$"
)

_CHECKLIST_GOAL_RE: Final[re.Pattern[str]] = re.compile(r"^## (G(?:[1-9]|1[0-5])): (.+)$")

_EVIDENCE_METADATA_RE: Final[re.Pattern[str]] = re.compile(
    r"^\s{6}evidence:\s*([^|\s]+)(?:\s*\|.*)?$"
)

HARNESS_PREFLIGHT_FILENAME: Final[str] = "harness_preflight.md"

_HARNESS_PREFLIGHT_REQUIRED_KEYS: Final[tuple[str, ...]] = (
    "parent",
    "schema_version",
    "gap_report",
    "axes_config",
)

_HARNESS_PREFLIGHT_HEADINGS: Final[tuple[str, ...]] = (
    "## 1. Target Observation Surface",
    "## 2. Capability Mapping",
    "## 3. Gap Inventory",
    "## 4. Coverage Commitments",
    "## 5. Build Order",
)

_HARNESS_NUMBERED_HEADING_RE: Final[re.Pattern[str]] = re.compile(r"^## \d+\. ")

PATHFINDER_REPORT_FILENAME: Final[str] = "pathfinder_report.md"

_PATHFINDER_REQUIRED_KEYS: Final[tuple[str, ...]] = (
    "schema_version",
    "change_id",
    "scan_mode",
    "scan_round",
    "horizon",
    "gap_report",
)

_PATHFINDER_SCAN_MODES: Final[frozenset[str]] = frozenset({"initial", "incremental"})

_PATHFINDER_HEADINGS: Final[tuple[str, ...]] = (
    "## Scan Scope",
    "## Findings",
    "## Handoff",
)

HUMAN_ARTIFACT_BUDGETS: Final[dict[str, tuple[int, int]]] = {
    "input/constitution.md": (800, 1500),
    "input/requirements.md": (1200, 2500),
    "input/requirements/<domain>.md": (1200, 2500),
    "input/amendments/<date>-<slug>.md": (400, 800),
    "output/DIGEST.md": (600, 1000),
    "output/convergence/<version>-convergence.md": (700, 1000),
}

HUMAN_DIR_DEFAULT: Final[Path] = Path(".local") / "human"

DIGEST_BUDGET_KEY: Final[str] = "output/DIGEST.md"

_PATHFINDER_ABSOLUTE_PATH_RE: Final[re.Pattern[str]] = re.compile(
    r"(?<![A-Za-z0-9:])/(?!/)[^\s`'\",)\]]*"
)

_PATHFINDER_FINDING_START_RE: Final[re.Pattern[str]] = re.compile(
    r"^\s*-\s+gap_id\s*:", re.MULTILINE
)

_PATHFINDER_SEVERITY_BLOCKER_RE: Final[re.Pattern[str]] = re.compile(
    r"^\s*severity\s*:\s*BLOCKER\s*$", re.MULTILINE
)

_PATHFINDER_ACCEPTANCE_SIGNAL_RE: Final[re.Pattern[str]] = re.compile(
    r"^[ \t]*acceptance_signal[ \t]*:[ \t]*([^\r\n]*)$", re.MULTILINE
)

_ENTRANCE_INVENTORY_ROW_RE: Final[re.Pattern[str]] = re.compile(r"^\|\s*`([^`]+)`\s*\|")

_ENTRANCE_INVENTORY_HEADING: Final[str] = "## 3. Artifact Inventory"

_ENTRANCE_REQUIRED_HEADINGS: Final[tuple[str, ...]] = (
    "## 1. What This Change Is",
    "## 2. Scenario Routing",
    _ENTRANCE_INVENTORY_HEADING,
    "## 4. Discipline Pointers",
)


def _load_dependencies() -> None:
    """Load public-package dependencies after the split is initialized."""
    from devolaflow.agent_workspace import progress as progress_header
    from devolaflow.agent_workspace import round_parser
    from devolaflow.agent_workspace.change import (
        ACTIVE_DIR_DEFAULT,
        ARCHIVE_DIR_DEFAULT,
        ChangeLayout,
        LegacyChangeLayoutError,
        detect_change_layout,
    )
    from devolaflow.agent_workspace.preflight import (
        PreflightAuthorizationError,
        _authorization_digest,
        _deterministic_mirror_bytes,
        _extract_preflight_sections,
        _frontmatter_shape,
        _parse_authorization_records,
        _parse_stop_cards,
        _validate_permitted_stops,
        _validate_section0,
        _validate_timestamp,
    )

    globals().update(
        {
            "progress_header": progress_header,
            "round_parser": round_parser,
            "ACTIVE_DIR_DEFAULT": ACTIVE_DIR_DEFAULT,
            "ARCHIVE_DIR_DEFAULT": ARCHIVE_DIR_DEFAULT,
            "ChangeLayout": ChangeLayout,
            "LegacyChangeLayoutError": LegacyChangeLayoutError,
            "detect_change_layout": detect_change_layout,
            "PreflightAuthorizationError": PreflightAuthorizationError,
            "_authorization_digest": _authorization_digest,
            "_deterministic_mirror_bytes": _deterministic_mirror_bytes,
            "_extract_preflight_sections": _extract_preflight_sections,
            "_frontmatter_shape": _frontmatter_shape,
            "_parse_authorization_records": _parse_authorization_records,
            "_parse_stop_cards": _parse_stop_cards,
            "_validate_permitted_stops": _validate_permitted_stops,
            "_validate_section0": _validate_section0,
            "_validate_timestamp": _validate_timestamp,
        }
    )


__all__ = [
    name
    for name in globals()
    if name
    not in {
        "__name__",
        "__package__",
        "__loader__",
        "__spec__",
        "__builtins__",
        "__all__",
        "_load_dependencies",
    }
]
