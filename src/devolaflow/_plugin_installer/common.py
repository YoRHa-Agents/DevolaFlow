"""Shared imports and constants for plugin installation."""

# ruff: noqa: F401, E402

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_REGISTRY_PATH = Path("workflow-system/agent/knowledge/runtime-plugins.yaml")

_VERSION_RX = re.compile(r"\d+\.\d+(?:\.\d+)?")

_SUPPORTED_BACKENDS: frozenset[str] = frozenset({"pip", "npm_then_init"})

_SUPPORTED_SCHEMA_VERSIONS: frozenset[int] = frozenset({1, 2, 3, 4})

_SUPPORTED_TIERS: frozenset[str] = frozenset({"require", "suggest"})

_DEFAULT_UPGRADE_CHECK_FREQUENCY_HOURS: int = 24

_LAST_CHECKED_SUCCESSFUL_EVENTS: frozenset[str] = frozenset(
    {"plugin_already_installed", "plugin_installed", "plugin_upgraded"}
)


def _load_dependencies() -> None:
    """Load public-package dependencies after the split is initialized."""
    from devolaflow.plugins.exceptions import (
        PluginBackendUnsupported,
        PluginInstallError,
        PluginNotFoundError,
        PluginVersionMismatch,
    )

    globals().update(
        {
            "PluginBackendUnsupported": PluginBackendUnsupported,
            "PluginInstallError": PluginInstallError,
            "PluginNotFoundError": PluginNotFoundError,
            "PluginVersionMismatch": PluginVersionMismatch,
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
