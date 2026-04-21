"""Cross-file parity tests for the repo-init canonical manifest.

Regression guard for the v7.4.1 / v7.5.0 / v7.7.0 three-time recurring issue
where prompt-only L0 created wrong files because the canonical manifest was
only defined in Python code and template YAML — not in SKILL.md.

These tests ensure that ALL three sources of truth agree:
  1. WORKFLOW_MANIFESTS["repo-init"] in validate_owned_files.py
  2. scaffold.config.canonical_manifest in repo-init.yaml
  3. §Repo-Init Pre-Dispatch Contract table in SKILL.md

If any of these drift, the regression WILL recur.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from devolaflow.lifecycle.validate_owned_files import (
    WORKFLOW_MANIFESTS,
    get_canonical_manifest,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_repo_init_yaml() -> dict:
    path = REPO_ROOT / "workflow-system/agent/templates/builtin/repo-init.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _load_skill_md() -> str:
    path = REPO_ROOT / "workflow-system/agent/SKILL.md"
    return path.read_text(encoding="utf-8")


def _extract_canonical_table_rows(skill_text: str) -> list[str]:
    """Extract path cells from the canonical manifest table in SKILL.md."""
    start = skill_text.find("Canonical manifest")
    assert start != -1, "Could not find 'Canonical manifest' heading in SKILL.md"
    end = skill_text.find("Mode selects", start)
    assert end != -1, "Could not find 'Mode selects' after canonical manifest table"
    table_section = skill_text[start:end]

    paths: list[str] = []
    for line in table_section.splitlines():
        match = re.match(r"\|\s*\d+\s*\|\s*`([^`]+)`", line)
        if match:
            paths.append(match.group(1))
    return paths


# ── Tests ────────────────────────────────────────────────────────────────


def test_python_manifest_matches_template_yaml():
    data = _load_repo_init_yaml()
    scaffold_stage = next(s for s in data["stages"] if s["id"] == "scaffold")
    yaml_manifest = scaffold_stage["config"]["canonical_manifest"]
    assert yaml_manifest == WORKFLOW_MANIFESTS["repo-init"], (
        f"Template YAML manifest {yaml_manifest} != "
        f"Python WORKFLOW_MANIFESTS {WORKFLOW_MANIFESTS['repo-init']}"
    )


def test_skill_md_contains_all_canonical_paths():
    skill_text = _load_skill_md()

    assert "Repo-Init Pre-Dispatch Contract" in skill_text, (
        "SKILL.md missing §Repo-Init Pre-Dispatch Contract section header"
    )

    for path in WORKFLOW_MANIFESTS["repo-init"]:
        assert path in skill_text, (
            f"Canonical path '{path}' not found in SKILL.md — "
            "all 3 sources of truth must list every manifest entry"
        )


def test_skill_md_canonical_table_has_five_rows():
    skill_text = _load_skill_md()
    rows = _extract_canonical_table_rows(skill_text)
    assert len(rows) == 5, f"Expected 5 canonical-manifest table rows, got {len(rows)}: {rows}"


def test_skill_md_canonical_table_matches_python():
    """The SKILL.md table paths must match WORKFLOW_MANIFESTS exactly."""
    skill_text = _load_skill_md()
    table_paths = _extract_canonical_table_rows(skill_text)
    assert table_paths == WORKFLOW_MANIFESTS["repo-init"], (
        f"SKILL.md table paths {table_paths} != "
        f"Python WORKFLOW_MANIFESTS {WORKFLOW_MANIFESTS['repo-init']}"
    )


def test_skill_md_mentions_vof001_blocker():
    skill_text = _load_skill_md()
    assert "VOF001" in skill_text, "SKILL.md must reference violation code VOF001"

    contract_start = skill_text.find("Repo-Init Pre-Dispatch Contract")
    assert contract_start != -1
    section = skill_text[contract_start : contract_start + 2000]
    assert "blocker" in section.lower(), (
        "SKILL.md §Repo-Init Pre-Dispatch Contract must mention 'blocker' severity"
    )


def test_skill_md_mentions_doctor_command():
    skill_text = _load_skill_md()
    assert "devola-init doctor" in skill_text, (
        "SKILL.md must reference 'devola-init doctor' post-init verification command"
    )


def test_repo_init_yaml_mode_description_mentions_canonical():
    data = _load_repo_init_yaml()
    mode_desc = data["parameters"]["mode"]["description"]
    assert "canonical" in mode_desc.lower(), (
        "repo-init.yaml mode parameter description must mention 'canonical_manifest' or 'canonical'"
    )


def test_manifest_paths_are_consistent_types():
    manifest = WORKFLOW_MANIFESTS["repo-init"]

    expected_dirs = {".local/feedbacks/", ".local/tasks/", ".local/memory/"}
    expected_files = {".local/index.md", ".rules/compile-config.yaml"}

    for path in manifest:
        if path in expected_dirs:
            assert path.endswith("/"), f"Directory path '{path}' must end with '/'"
        elif path in expected_files:
            assert not path.endswith("/"), f"File path '{path}' must not end with '/'"
        else:
            raise AssertionError(f"Unexpected manifest path '{path}' — update this test")


def test_canonical_count_is_five():
    assert len(WORKFLOW_MANIFESTS["repo-init"]) == 5, (
        f"Expected exactly 5 canonical paths, got {len(WORKFLOW_MANIFESTS['repo-init'])}. "
        "Adding or removing paths requires updating all 3 locations: "
        "validate_owned_files.py, repo-init.yaml, and SKILL.md"
    )


def test_get_canonical_manifest_returns_copy():
    """get_canonical_manifest() must return a copy, not the original list."""
    result = get_canonical_manifest("repo-init")
    assert result == WORKFLOW_MANIFESTS["repo-init"]
    assert result is not WORKFLOW_MANIFESTS["repo-init"]
