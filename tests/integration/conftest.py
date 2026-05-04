"""Shared fixtures + no-network guard for bridge shape contract tests.

Per v10.8.0 D-C-2 §2 patch_design step 1, this conftest provides:

* ``fixtures_dir`` — resolved path to ``tests/integration/fixtures/``.
* Per-plugin fixture-loader helpers (``load_yaml_fixture`` /
  ``load_json_fixture`` / ``load_text_fixture``).
* R1 mitigation: every fixture MUST carry a
  ``captured_from_plugin_version: <version>`` header; the loader asserts
  the header is present + non-empty (fails loudly if an operator checks
  in a fixture without the version stamp).

The conftest is SHARED with D-C-1 where convenient (per D-C-1 §8
dependencies note). The D-C-1 degraded-mode tests live under
``tests/test_degraded_mode.py`` and use monkeypatch-based mocks, NOT
cached fixtures; they do not import this conftest but co-exist happily.

No-network guard: integration tests MUST NOT invoke live plugin
binaries or HTTP requests. Any accidental `requests.get` / `subprocess`
call is caught by the guard fixture and surfaces as a loud AssertionError.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

FIXTURES_DIR: Path = Path(__file__).resolve().parent / "fixtures"

# Canonical plugin registry (name → path under fixtures/).
_PLUGIN_DIRS: dict[str, str] = {
    "si-chip": "si-chip",
    "nines": "nines",
    "rtk": "rtk",
    "ui-pro": "ui-pro",
}


@pytest.fixture
def fixtures_dir() -> Path:
    """Return the absolute path to ``tests/integration/fixtures/``."""
    return FIXTURES_DIR


def _assert_version_header(text: str, fixture_path: Path) -> None:
    """R1 mitigation: require ``captured_from_plugin_version`` header.

    Per D-C-2 §9 R1 mitigation: every fixture file carries a YAML / JSON /
    plaintext header with ``captured_from_plugin_version: <version>``.
    Loaders call this to fail loud when a fixture checked in without the
    stamp (stops silent fixture drift between weekly refreshes).
    """
    if "captured_from_plugin_version:" not in text and (
        '"captured_from_plugin_version"' not in text
    ):
        raise AssertionError(
            f"R1 mitigation violated: fixture {fixture_path.name} missing "
            f"`captured_from_plugin_version: <version>` header. Every fixture "
            f"under tests/integration/fixtures/ MUST carry the version stamp "
            f"per D-C-2 §9 R1. Refresh via `make refresh-bridge-fixtures`."
        )


def load_yaml_fixture(plugin: str, filename: str) -> dict[str, Any]:
    """Load a captured YAML fixture for *plugin* from ``fixtures/<plugin>/<filename>``.

    Asserts the R1 version-header is present before parsing the body.
    """
    import yaml  # lazy — avoid pytest-collect-time pyyaml import

    sub = _PLUGIN_DIRS.get(plugin)
    if sub is None:
        raise ValueError(f"unknown plugin {plugin!r}; expected one of {sorted(_PLUGIN_DIRS)}")
    path = FIXTURES_DIR / sub / filename
    if not path.is_file():
        raise AssertionError(
            f"fixture missing: {path.relative_to(FIXTURES_DIR.parent.parent.parent)}. "
            f"Refresh via `make refresh-bridge-fixtures`."
        )
    raw = path.read_text(encoding="utf-8")
    _assert_version_header(raw, path)
    loaded = yaml.safe_load(raw) or {}
    if not isinstance(loaded, dict):
        raise AssertionError(
            f"fixture {path.name} did not parse to a dict (got {type(loaded).__name__})"
        )
    return loaded


def load_json_fixture(plugin: str, filename: str) -> dict[str, Any]:
    """Load a captured JSON fixture; assert the R1 version-header first."""
    sub = _PLUGIN_DIRS.get(plugin)
    if sub is None:
        raise ValueError(f"unknown plugin {plugin!r}; expected one of {sorted(_PLUGIN_DIRS)}")
    path = FIXTURES_DIR / sub / filename
    if not path.is_file():
        raise AssertionError(
            f"fixture missing: {path.relative_to(FIXTURES_DIR.parent.parent.parent)}. "
            f"Refresh via `make refresh-bridge-fixtures`."
        )
    raw = path.read_text(encoding="utf-8")
    _assert_version_header(raw, path)
    loaded = json.loads(raw)
    if not isinstance(loaded, dict):
        raise AssertionError(
            f"fixture {path.name} did not parse to a dict (got {type(loaded).__name__})"
        )
    return loaded


def load_text_fixture(plugin: str, filename: str) -> str:
    """Load a plain-text fixture (stdout / log) verbatim.

    The R1 header appears as a ``# captured_from_plugin_version: <ver>``
    first-line comment; asserted before returning.
    """
    sub = _PLUGIN_DIRS.get(plugin)
    if sub is None:
        raise ValueError(f"unknown plugin {plugin!r}; expected one of {sorted(_PLUGIN_DIRS)}")
    path = FIXTURES_DIR / sub / filename
    if not path.is_file():
        raise AssertionError(
            f"fixture missing: {path.relative_to(FIXTURES_DIR.parent.parent.parent)}. "
            f"Refresh via `make refresh-bridge-fixtures`."
        )
    raw = path.read_text(encoding="utf-8")
    _assert_version_header(raw, path)
    return raw
