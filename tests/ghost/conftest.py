"""Package-level fixtures for the ``tests/ghost/`` audit package.

Moved verbatim from ``tests/test_no_ghost_features.py`` per
v15-ADR-001 (v14.3.0 split).
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def project_root() -> Path:
    """Return the repository root (parent of the ``tests/`` directory)."""
    return Path(__file__).resolve().parent.parent.parent
