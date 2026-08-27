"""Package-level fixtures for the ``tests/ghost/`` audit package.

Moved verbatim from ``tests/test_no_ghost_features.py`` per
v15-ADR-001 (v14.3.0 split).
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

_LEGACY_FEATURE_RE = re.compile(r"test_features_v(?P<major>\d+)_")


def full_ghost_enabled(environ: dict[str, str] | None = None) -> bool:
    """Return whether the operator explicitly requests the full ghost suite."""
    return (environ if environ is not None else os.environ).get("GHOST_FULL") == "1"


def is_legacy_feature_module(path: Path) -> bool:
    """Return whether *path* is a pre-v16 cycle feature module."""
    if path.name == "test_features_legacy.py":
        return True
    match = _LEGACY_FEATURE_RE.match(path.name)
    return bool(match and int(match.group("major")) < 16)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip immutable pre-v16 feature audits unless GHOST_FULL=1 is set."""
    del config
    if full_ghost_enabled():
        return
    skip = pytest.mark.skip(reason="pre-v16 ghost audit; set GHOST_FULL=1 to run")
    for item in items:
        if is_legacy_feature_module(Path(str(item.path))):
            item.add_marker(skip)


@pytest.fixture(scope="module")
def project_root() -> Path:
    """Return the repository root (parent of the ``tests/`` directory)."""
    return Path(__file__).resolve().parent.parent.parent
