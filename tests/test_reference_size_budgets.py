"""Tier-budget enforcement for workflow-system/agent reference + example files.

C-006 (v7.2.0). Source rationale: gsd v1.37.0 release notes (issue #2361):
    "Agent size-budget enforcement — Tiered line-count limits
     (XL: 1 600, Large: 1 000, Default: 500) keep agent prompts lean;
     violations surface in CI"

Tier mapping for DevolaFlow:
    * Default tier (< 500 lines)   — workflow-system/agent/SKILL.md
                                       (covered by
                                       tests/test_integration.py::test_skill_md_under_500_lines)
    * Large   tier (<= 1000 lines) — workflow-system/agent/references/*.md
    * XL      tier (<= 1600 lines) — workflow-system/agent/examples/*.md

The reference + example file lists are loaded from
``scripts/sync_cursor_skill.py::MIRRORED_FILES`` so the test stays in lockstep
with the canonical set Cursor / Claude users actually receive (single source of
truth, matching SF-3 mirror semantics).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

TIER_DEFAULT = 500  # SKILL.md (covered by existing integration test)
TIER_LARGE = 1000  # references/*.md
TIER_XL = 1600  # examples/*.md


def _load_mirror_lists(project_root: Path) -> tuple[list[str], list[str]]:
    """Import scripts/sync_cursor_skill.py and split MIRRORED_FILES by subdir."""
    sync_path = project_root / "scripts" / "sync_cursor_skill.py"
    if not sync_path.is_file():
        raise RuntimeError(f"missing canonical sync script: {sync_path}")
    spec = importlib.util.spec_from_file_location("sync_cursor_skill_size_budget_probe", sync_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    refs = [rel for rel in module.MIRRORED_FILES if rel.startswith("references/")]
    examples = [rel for rel in module.MIRRORED_FILES if rel.startswith("examples/")]
    return refs, examples


def _line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


_REPO_ROOT_FOR_COLLECTION = Path(__file__).resolve().parent.parent
_REF_FILES, _EXAMPLE_FILES = _load_mirror_lists(_REPO_ROOT_FOR_COLLECTION)


@pytest.mark.parametrize("rel_path", _REF_FILES)
def test_reference_within_large_tier(project_root: Path, rel_path: str) -> None:
    """Each ``references/*.md`` must stay within the Large tier ceiling."""
    target = project_root / "workflow-system" / "agent" / rel_path
    assert target.is_file(), f"missing canonical reference: {target}"
    lines = _line_count(target)
    assert lines <= TIER_LARGE, f"{rel_path} has {lines} lines (Large tier ceiling: {TIER_LARGE})"


@pytest.mark.parametrize("rel_path", _EXAMPLE_FILES)
def test_example_within_xl_tier(project_root: Path, rel_path: str) -> None:
    """Each ``examples/*.md`` must stay within the XL tier ceiling."""
    target = project_root / "workflow-system" / "agent" / rel_path
    assert target.is_file(), f"missing canonical example: {target}"
    lines = _line_count(target)
    assert lines <= TIER_XL, f"{rel_path} has {lines} lines (XL tier ceiling: {TIER_XL})"


def test_canonical_lists_match_sf3_contract() -> None:
    """Sanity: shape matches the long-standing 8-refs / 3-examples SF-3 contract."""
    assert len(_REF_FILES) == 8, f"expected 8 references, got {len(_REF_FILES)}: {_REF_FILES}"
    assert len(_EXAMPLE_FILES) == 3, (
        f"expected 3 examples, got {len(_EXAMPLE_FILES)}: {_EXAMPLE_FILES}"
    )
