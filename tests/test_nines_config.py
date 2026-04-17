"""Schema & path-binding tests for repo-root ``nines.toml`` (v6.1.1, N1).

Purpose
-------
``nines.toml`` at the repo root is the canonical NineS configuration for the
DevolaFlow project. ``nines -c nines.toml self-eval ...`` picks up its
``[self_eval.paths]`` bindings (``golden_dir``, ``samples_dir``, ``src_dir``,
``test_dir``, ``project_root``), so drift between that file and the actual
repo layout silently breaks self-eval.

These tests enforce:

1. The file exists and parses as TOML.
2. The ``[project]`` identity table is present.
3. ``[self_eval.paths]`` binds every required directory.
4. Every bound path is relative (no absolute filesystem paths — per SF-5).
5. Every bound path actually exists on disk, relative to the repo root.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
NINES_TOML = REPO_ROOT / "nines.toml"

REQUIRED_PATH_KEYS = (
    "golden_dir",
    "samples_dir",
    "src_dir",
    "test_dir",
    "project_root",
)


@pytest.fixture(scope="module")
def nines_config() -> dict:
    with NINES_TOML.open("rb") as fh:
        return tomllib.load(fh)


def test_nines_toml_exists() -> None:
    assert NINES_TOML.is_file(), (
        "nines.toml must exist at repo root for `nines -c nines.toml self-eval` "
        "to pick up canonical project defaults."
    )


def test_nines_toml_parses(nines_config: dict) -> None:
    assert isinstance(nines_config, dict) and nines_config, (
        "nines.toml parsed to an empty or non-dict structure"
    )


def test_nines_toml_has_project_section(nines_config: dict) -> None:
    assert "project" in nines_config, "nines.toml missing [project] section"
    project = nines_config["project"]
    assert project.get("name") == "devolaflow", (
        f"[project].name must be 'devolaflow', got {project.get('name')!r}"
    )
    assert isinstance(project.get("description"), str) and project["description"], (
        "[project].description must be a non-empty string"
    )


def test_nines_toml_has_self_eval_paths(nines_config: dict) -> None:
    paths = nines_config.get("self_eval", {}).get("paths", {})
    for key in REQUIRED_PATH_KEYS:
        assert key in paths, (
            f"[self_eval.paths] missing required key '{key}' — required by "
            "`nines self-eval` for V1 / V2 / V3 evaluator wiring."
        )
        value = paths[key]
        assert isinstance(value, str) and value, (
            f"[self_eval.paths].{key} must be a non-empty string, got {value!r}"
        )
        # SF-5: all agent-facing paths are relative to repo root.
        assert not Path(value).is_absolute(), (
            f"[self_eval.paths].{key}={value!r} is absolute; per rule SF-5 all "
            "paths must be relative to the repo root."
        )


def test_nines_toml_paths_exist(nines_config: dict) -> None:
    paths = nines_config["self_eval"]["paths"]
    for key in REQUIRED_PATH_KEYS:
        rel = paths[key]
        resolved = (REPO_ROOT / rel).resolve()
        assert resolved.exists(), (
            f"[self_eval.paths].{key}={rel!r} resolves to {resolved}, which does not exist on disk."
        )
