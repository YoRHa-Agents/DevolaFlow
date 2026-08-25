"""Contract tests for the ``repo-init`` checklist seed and owned-file manifest.

Registry v3 retires the executable ``repo-init.yaml`` while preserving its
historical stages as non-executable seed provenance. The eight-path dispatch
contract remains owned by ``WORKFLOW_MANIFESTS["repo-init"]`` and is named by
the seed's canonical-manifest assertion.

Closes AC-6 + AC-10 of v8.2.3.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from devolaflow.lifecycle.validate_owned_files import WORKFLOW_MANIFESTS
from devolaflow.template_engine.registry import TemplateRegistry
from devolaflow.template_engine.seeds import ChecklistSeed

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_ROOT = REPO_ROOT / "workflow-system/agent/templates"

# Order matches the YAML declaration:
#   * positions 1..5 — the pre-v8.2.3 paths (preserved per I-PV03-A, additive only)
#   * positions 6..8 — the v8.2.3 .agent/* substrate (new)
EXPECTED_PATHS: list[str] = [
    ".local/feedbacks/",
    ".local/tasks/",
    ".local/memory/",
    ".local/index.md",
    ".rules/compile-config.yaml",
    ".local/.agent/active/",
    ".local/.agent/handoff/",
    ".local/.agent/archive/",
]


@pytest.fixture()
def repo_init_data() -> ChecklistSeed:
    """Load and strictly validate the repo-init checklist seed."""
    seed = TemplateRegistry(TEMPLATES_ROOT).load_seed("repo-init")
    assert seed is not None
    return seed


def _scaffold_config(data: ChecklistSeed) -> dict:
    """Return the manifest plus the seed assertion that names its contract."""
    assertion = next(
        assertion
        for partition in data.partitions
        for assertion in partition.assertions
        if assertion.key == "canonical-manifest"
    )
    return {
        "canonical_manifest": list(WORKFLOW_MANIFESTS["repo-init"]),
        "statement_template": assertion.statement_template,
    }


# ── Manifest cardinality ────────────────────────────────────────────────


def test_canonical_manifest_has_exactly_eight_entries(repo_init_data: dict) -> None:
    manifest = _scaffold_config(repo_init_data)["canonical_manifest"]
    assert len(manifest) == 8, (
        f"Expected exactly 8 canonical paths post v8.2.3, got {len(manifest)}: {manifest}"
    )


# ── I-PV03-A: legacy 5 paths preserved (additive only) ──────────────────


def test_canonical_manifest_preserves_legacy_five_paths(repo_init_data: dict) -> None:
    """The 5 pre-v8.2.3 paths MUST still be present (I-PV03-A — additive only)."""
    manifest = _scaffold_config(repo_init_data)["canonical_manifest"]
    legacy_five = [
        ".local/feedbacks/",
        ".local/tasks/",
        ".local/memory/",
        ".local/index.md",
        ".rules/compile-config.yaml",
    ]
    for p in legacy_five:
        assert p in manifest, f"Legacy v8.2.2 manifest path '{p}' missing — I-PV03-A violation"


# ── A1: new .agent/* substrate ──────────────────────────────────────────


def test_canonical_manifest_contains_three_new_agent_paths(repo_init_data: dict) -> None:
    """v8.2.3 adds the 3 .agent/* dirs per .local/research/v8.3.0_design.md §1.1."""
    manifest = _scaffold_config(repo_init_data)["canonical_manifest"]
    new_three = [
        ".local/.agent/active/",
        ".local/.agent/handoff/",
        ".local/.agent/archive/",
    ]
    for p in new_three:
        assert p in manifest, f"v8.2.3 new path '{p}' missing"


# ── Exact ordered match ─────────────────────────────────────────────────


def test_canonical_manifest_exact_order(repo_init_data: dict) -> None:
    """Order matters — keeps pre-v8.2.3 prefix byte-stable for cache layout (P6 spirit)."""
    manifest = _scaffold_config(repo_init_data)["canonical_manifest"]
    assert manifest == EXPECTED_PATHS, (
        f"Manifest order/content mismatch.\n  Got     : {manifest}\n  Expected: {EXPECTED_PATHS}"
    )


# ── Path-shape conventions ──────────────────────────────────────────────


def test_directory_paths_end_with_slash(repo_init_data: dict) -> None:
    manifest = _scaffold_config(repo_init_data)["canonical_manifest"]
    expected_dirs = {
        ".local/feedbacks/",
        ".local/tasks/",
        ".local/memory/",
        ".local/.agent/active/",
        ".local/.agent/handoff/",
        ".local/.agent/archive/",
    }
    for p in manifest:
        if p in expected_dirs:
            assert p.endswith("/"), f"Directory path '{p}' must end with '/'"


def test_file_paths_do_not_end_with_slash(repo_init_data: dict) -> None:
    manifest = _scaffold_config(repo_init_data)["canonical_manifest"]
    expected_files = {".local/index.md", ".rules/compile-config.yaml"}
    for p in manifest:
        if p in expected_files:
            assert not p.endswith("/"), f"File path '{p}' must not end with '/'"


# ── S-2: relative paths only ────────────────────────────────────────────


def test_no_absolute_paths_in_manifest(repo_init_data: dict) -> None:
    """S-2 invariant: every path MUST be relative to the repo root."""
    manifest = _scaffold_config(repo_init_data)["canonical_manifest"]
    for p in manifest:
        assert not p.startswith("/"), f"Absolute path '{p}' violates S-2"
        assert not p.startswith("~"), f"Home-relative path '{p}' violates S-2"


# ── Description text reflects the new count ─────────────────────────────


def test_mode_parameter_description_mentions_eight_paths(repo_init_data: dict) -> None:
    """The seed assertion names the eight-path canonical contract."""
    statement = _scaffold_config(repo_init_data)["statement_template"]
    assert "eight canonical workspace paths" in statement.lower()


def test_scaffold_stage_description_mentions_agent_substrate(repo_init_data: dict) -> None:
    """The seed retains scaffold/compile provenance without executable semantics."""
    assert repo_init_data.source_stage_sequence() == [
        ("analyze", "analyze"),
        ("scaffold", "implement"),
        ("compile", "implement"),
        ("interview", "analyze"),
        ("verify", "verify"),
    ]
    assert not hasattr(repo_init_data, "composition")
