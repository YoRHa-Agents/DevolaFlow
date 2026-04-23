"""Golden-snapshot tests for adapter outputs (v6.1.0 C3).

These tests lock down structural invariants of the Cursor adapter output so
regressions — missing sections, stray legacy symbols, budget overruns — are
caught deterministically. The fixture is intentionally *metadata-based*
(not byte-exact) because SKILL.md contains version strings and dates that
legitimately change every release.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from devolaflow.adapters.base import _find_project_root, load_workflow_skill
from devolaflow.adapters.cursor_adapter import CursorAdapter

GOLDEN_DIR = Path(__file__).parent / "fixtures" / "golden" / "cursor"
GOLDEN_META = GOLDEN_DIR / "SKILL.md.expected.meta.json"


@pytest.fixture(scope="module")
def golden_meta() -> dict:
    return json.loads(GOLDEN_META.read_text())


@pytest.fixture
def cursor_build(tmp_path: Path):
    """Build the Cursor adapter into a temp dir and return (result, out_dir)."""
    source, agent_dir = load_workflow_skill()
    adapter = CursorAdapter()
    out_dir = tmp_path / "cursor"
    result = adapter.build(source, agent_dir, out_dir)
    return result, out_dir


def _extract_frontmatter(text: str) -> dict[str, str]:
    """Return a shallow key->value dict from a YAML-ish frontmatter block.

    We avoid importing yaml here to keep the check simple and independent of
    multi-line parsing quirks; only top-level ``key: value`` lines are
    extracted (enough for membership checks on ``must_have_frontmatter_keys``).
    """
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    block = parts[1]
    out: dict[str, str] = {}
    for line in block.splitlines():
        line = line.rstrip()
        if not line or line.startswith(" ") or line.startswith("#") or line.startswith("-"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        out[key.strip()] = value.strip()
    return out


def test_cursor_skill_golden_metadata(cursor_build, golden_meta):
    """Generated SKILL.md satisfies every property in the golden meta file."""
    _, out_dir = cursor_build
    skill = out_dir / "SKILL.md"
    assert skill.exists(), "cursor adapter must emit SKILL.md"
    text = skill.read_text()

    # 1) required_sections — every heading must appear verbatim
    for section in golden_meta["required_sections"]:
        assert section in text, f"required section missing from Cursor SKILL.md: {section!r}"

    # 2) line_count_range — generated SKILL must fit the documented band
    lo, hi = golden_meta["line_count_range"]
    actual = len(text.splitlines())
    assert lo <= actual <= hi, (
        f"Cursor SKILL.md line count {actual} outside golden range [{lo}, {hi}]"
    )

    # 3) must_have_frontmatter_keys — every frontmatter key present
    fm = _extract_frontmatter(text)
    for key in golden_meta["must_have_frontmatter_keys"]:
        assert key in fm, f"Cursor SKILL.md frontmatter missing key: {key!r}"

    # 4) must_not_contain — no legacy/removed symbols leak through
    for forbidden in golden_meta["must_not_contain"]:
        assert forbidden not in text, (
            f"Cursor SKILL.md contains forbidden legacy symbol: {forbidden!r}"
        )


def test_cursor_references_golden(cursor_build):
    """All 10 canonical reference files must be copied into ``references/``.

    v8.0.0 P-08 grew this set 8 → 9 by appending ``behavioral-guidelines.md``
    (the L3 behavioral primitives reference wired through the new top-level
    ``behavioral_guidelines`` dispatch field at canonical_order position 14).

    v8.3.0 PV-09 grew this set 9 → 10 by appending ``agent-workspace.md``
    (the change-driven workspace reference covering ``.local/.agent/``,
    append-only handoff envelopes, source-of-truth specs, and per-artifact
    token budgets — pairs with the change-driven workflow template v8.2.6
    and the ``devolaflow.agent_workspace`` Python API v8.2.5+)."""
    _, out_dir = cursor_build
    refs_dir = out_dir / "references"
    assert refs_dir.is_dir(), "cursor adapter must emit references/ directory"

    source_refs = _find_project_root() / "workflow-system" / "agent" / "references"
    expected = {p.name for p in source_refs.glob("*.md")}
    actual = {p.name for p in refs_dir.glob("*.md")}
    assert expected == actual, (
        f"Cursor references mismatch — missing: {expected - actual}, extra: {actual - expected}"
    )
    assert len(actual) == 10, f"expected 10 reference files, got {len(actual)}"


def test_cursor_examples_golden(cursor_build):
    """All 3 example files are copied into ``examples/``."""
    _, out_dir = cursor_build
    examples_dir = out_dir / "examples"
    assert examples_dir.is_dir(), "cursor adapter must emit examples/ directory"

    source_examples = _find_project_root() / "workflow-system" / "agent" / "examples"
    expected = {p.name for p in source_examples.glob("*.md")}
    actual = {p.name for p in examples_dir.glob("*.md")}
    assert expected == actual, (
        f"Cursor examples mismatch — missing: {expected - actual}, extra: {actual - expected}"
    )
    assert len(actual) == 3, f"expected 3 example files, got {len(actual)}"


def test_cursor_rules_mdc_created(cursor_build):
    """The ``rules/workflow-hard-rules.mdc`` file is created and non-empty."""
    _, out_dir = cursor_build
    mdc = out_dir / "rules" / "workflow-hard-rules.mdc"
    assert mdc.exists(), "cursor adapter must emit rules/workflow-hard-rules.mdc"
    text = mdc.read_text()
    assert text.strip(), "workflow-hard-rules.mdc must not be empty"
    # Must contain Cursor rule frontmatter (alwaysApply), not DevolaFlow SKILL frontmatter
    assert "alwaysApply" in text, (
        "workflow-hard-rules.mdc should contain Cursor alwaysApply frontmatter"
    )
