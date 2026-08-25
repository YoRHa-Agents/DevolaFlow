"""Cross-file parity tests for the repo-init canonical manifest.

Regression guard for the v7.4.1 / v7.5.0 / v7.7.0 three-time recurring issue
where prompt-only L0 created wrong files because the canonical manifest was
only defined in Python code and template YAML — not in SKILL.md.

These tests ensure that the current registry-v3 surfaces agree:
  1. WORKFLOW_MANIFESTS["repo-init"] in validate_owned_files.py
  2. the repo-init checklist seed's canonical-manifest assertion
  3. §Repo-Init Pre-Dispatch Contract table in SKILL.md

If any of these drift, the regression WILL recur.
"""

from __future__ import annotations

import re
from pathlib import Path

from devolaflow.lifecycle.validate_owned_files import (
    WORKFLOW_MANIFESTS,
    get_canonical_manifest,
    validate_owned_files,
)
from devolaflow.template_engine.registry import TemplateRegistry
from devolaflow.template_engine.seeds import ChecklistSeed

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_repo_init_yaml() -> ChecklistSeed:
    registry = TemplateRegistry(REPO_ROOT / "workflow-system/agent/templates")
    seed = registry.load_seed("repo-init")
    assert seed is not None
    return seed


def _load_skill_md() -> str:
    path = REPO_ROOT / "workflow-system/agent/SKILL.md"
    return path.read_text(encoding="utf-8")


def _load_execution_protocol() -> str:
    path = REPO_ROOT / "workflow-system/agent/references/execution-protocol.md"
    return path.read_text(encoding="utf-8")


def _extract_canonical_table_rows(skill_text: str) -> list[str]:
    """Extract path cells from the canonical manifest table in SKILL.md."""
    start = skill_text.find("Repo-Init Pre-Dispatch Contract")
    assert start != -1, "Could not find repo-init contract heading in SKILL.md"
    end = skill_text.find("## 3-Layer Agent Hierarchy", start)
    assert end != -1, "Could not find the section after the repo-init table"
    table_section = skill_text[start:end]

    paths: list[str] = []
    for line in table_section.splitlines():
        match = re.match(r"\|\s*\d+\s*\|\s*`([^`]+)`", line)
        if match:
            paths.append(match.group(1))
    return paths


# ── Tests ────────────────────────────────────────────────────────────────


def test_python_manifest_matches_template_yaml():
    seed = _load_repo_init_yaml()
    canonical = next(
        assertion
        for partition in seed.partitions
        for assertion in partition.assertions
        if assertion.key == "canonical-manifest"
    )
    assert "eight canonical workspace paths" in canonical.statement_template.lower()
    assert seed.source_stage_sequence() == [
        ("analyze", "analyze"),
        ("scaffold", "implement"),
        ("compile", "implement"),
        ("interview", "analyze"),
        ("verify", "verify"),
    ]


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


def test_skill_md_canonical_table_has_eight_rows():
    skill_text = _load_skill_md()
    rows = _extract_canonical_table_rows(skill_text)
    assert len(rows) == 8, f"Expected 8 canonical-manifest table rows, got {len(rows)}: {rows}"


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
    contract_start = skill_text.find("Repo-Init Pre-Dispatch Contract")
    assert contract_start != -1
    section = skill_text[contract_start : contract_start + 2000]
    assert "owns all eight paths" in section.lower()

    result = validate_owned_files({"workflow": "repo-init", "owned_files": []})
    assert not result.passed
    assert [(v.code, v.severity) for v in result.violations] == [("VOF001", "blocker")]


def test_skill_md_mentions_valid_operator_commands():
    skill_text = _load_skill_md()
    init_source = (REPO_ROOT / "src/devolaflow/init_project.py").read_text(encoding="utf-8")

    for command in (
        "devola-init-doctor",
        "devola-init-doctor --skills",
        "npx @yorha-agents/devola-flow doctor",
        "npx @yorha-agents/devola-flow update <cursor|claude|all>",
        "scripts/install.sh | bash -s update",
        "pip install --upgrade",
        "sync-rules",
        "make compile-rules",
    ):
        assert command in skill_text
    assert "copied skills" in skill_text
    for invalid in ("devola-init doctor", "devola-init sync-rules"):
        assert invalid not in skill_text
        assert invalid not in init_source


def test_execution_protocol_uses_three_layer_normative_vocabulary():
    protocol = _load_execution_protocol()

    for current_contract in (
        "L0 Project → L1 Wave → L2 Task",
        "Task → Wave → Project → Human",
        "Project and Wave are dispatchers",
        "only implementation layer",
    ):
        assert current_contract in protocol
    for stale_pattern in (
        r"L3 Task",
        r"L1 Stage",
        r"L2 Wave",
        r"L0.?L1.?L2.?L3",
        r"Wave → Stage",
        r"Stage → Project",
    ):
        assert re.search(stale_pattern, protocol) is None
    assert "source_stages" in protocol
    assert "contribute no progress weight" in protocol


def test_repo_init_yaml_mode_description_mentions_canonical():
    seed = _load_repo_init_yaml()
    statements = [
        assertion.statement_template
        for partition in seed.partitions
        for assertion in partition.assertions
    ]
    assert any("canonical" in statement.lower() for statement in statements)
    assert not hasattr(seed, "stages")


def test_manifest_paths_are_consistent_types():
    manifest = WORKFLOW_MANIFESTS["repo-init"]

    expected_dirs = {
        ".local/feedbacks/",
        ".local/tasks/",
        ".local/memory/",
        # v8.2.3 — A1 .agent/* substrate per .local/research/v8.3.0_design.md §1.1
        ".local/.agent/active/",
        ".local/.agent/handoff/",
        ".local/.agent/archive/",
    }
    expected_files = {".local/index.md", ".rules/compile-config.yaml"}

    for path in manifest:
        if path in expected_dirs:
            assert path.endswith("/"), f"Directory path '{path}' must end with '/'"
        elif path in expected_files:
            assert not path.endswith("/"), f"File path '{path}' must not end with '/'"
        else:
            raise AssertionError(f"Unexpected manifest path '{path}' — update this test")


def test_canonical_count_is_eight():
    assert len(WORKFLOW_MANIFESTS["repo-init"]) == 8, (
        f"Expected exactly 8 canonical paths, got {len(WORKFLOW_MANIFESTS['repo-init'])}. "
        "Adding or removing paths requires updating all 3 locations: "
        "validate_owned_files.py, repo-init.yaml, and SKILL.md"
    )


def test_get_canonical_manifest_returns_copy():
    """get_canonical_manifest() must return a copy, not the original list."""
    result = get_canonical_manifest("repo-init")
    assert result == WORKFLOW_MANIFESTS["repo-init"]
    assert result is not WORKFLOW_MANIFESTS["repo-init"]
