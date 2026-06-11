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

# SSOT-derived inventory counts (v14.2.1 G-028 — no hardcoded `== 24` /
# `== 4` pins that break on every legitimate addition):
# * references — the SF-4 canonical set pinned by the ghost audit;
# * examples  — the `examples/` entries of the mirror manifest.
from scripts.sync_cursor_skill import MIRRORED_FILES
from tests.ghost.test_registries import _SF4_REFERENCE_SET

_EXPECTED_REFERENCE_COUNT = len(_SF4_REFERENCE_SET)
_EXPECTED_EXAMPLE_COUNT = sum(1 for rel in MIRRORED_FILES if rel.startswith("examples/"))

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
    """All SF-4 canonical reference files must be copied into ``references/``.

    v8.0.0 P-08 grew this set 8 → 9 by appending ``behavioral-guidelines.md``
    (the L3 behavioral primitives reference wired through the new top-level
    ``behavioral_guidelines`` dispatch field at canonical_order position 14).

    v8.3.0 PV-09 grew this set 9 → 10 by appending ``agent-workspace.md``
    (the change-driven workspace reference covering ``.local/.agent/``,
    append-only handoff envelopes, source-of-truth specs, and per-artifact
    token budgets — pairs with the change-driven workflow template v8.2.6
    and the ``devolaflow.agent_workspace`` Python API v8.2.5+).

    v8.4.0 rollup grew this set 10 → 11 by appending ``shell-proxy.md``
    (the RTK + memory-router stack reference covering the runtime-plugins.yaml
    RTK row, the shell_proxy/ package, the pre_shell_call lifecycle hook,
    the memory_router/ planning fast-path, and the
    ``.local/memory/{cases,commands}/`` recipe layers — pairs with the
    v8.3.1..v8.3.4 PV-01..PV-04 surface area closing R-001+R-002+M-001+M-002).

    v9.0.0 PV-01 (v8.4.1) grew this set 11 → 12 by appending
    ``plan-mode-enforcement.md`` (the plan-mode L0 operating contract
    reference absorbing SKILL.md §"Mode Awareness" PLAN MODE detail +
    §"Reinforcement Rules" mechanism into a single Tier-2 reference,
    freeing ~57 lines of SKILL.md headroom and closing R7 carry-forward
    + B-01 SKILL.md ceiling crisis from v9.0.0 SI-1 gap analysis).

    v9.0.0 PV-05 (v8.5.0) grew this set 12 → 13 by appending
    ``env-flags.md`` (the canonical DEVOLAFLOW_* env-var inventory:
    8 active runtime flags + 6 forward-declared gate-primitive flags
    + 4 BG defaults + 3 test-fixture flags). Pairs with Workflow Rule
    W-20 (env-flag reuse vs new-flag policy).

    v9.0.0 PV-06 (v8.5.1) grew this set 13 → 14 by appending
    ``compression-pipeline.md`` (the CompressionStage protocol
    + CompressionPipeline orchestrator + 6-transform unification
    + multi-pass filter chain T3 #5 reference). Pairs with
    ``src/devolaflow/compression_pipeline.py`` and
    ``schemas/compression-pipeline.yaml``.

    v10.4.0 PV-05 grew this set 14 → 15 by appending
    ``troubleshooting.md`` (the operator troubleshooting handbook
    with quick lookup index + per-symptom diagnostic patterns +
    escalation patterns harvested from v8.0.0 → v10.3.0 cycle
    retrospectives). Pairs with v10.4.0 audit scripts (D-D-1, D-D-2)
    and scaffold CLIs (D-X-1, D-X-2).

    v10.7.0 D-O-1 grew this set 15 → 16 by appending
    ``evaluator-rosetta.md`` (the 6 × 9 cross-walk between SI-3
    dimensions + NineS hygiene axes / capability sub-bundles +
    Si-Chip iteration_delta scalar with per-cell verbatim source
    citations). Pairs with `scripts/auto_collect_si3_metrics.py`
    (D-O-2) and `scripts/generate_evaluator_rosetta.py` (D-O-1
    companion CSV emitter).

    v10.8.0 D-C-1 grew this set 16 → 17 by appending
    ``degraded-mode.md`` (the per-plugin upstream-unreachable fallback
    contract for NineS / Si-Chip / RTK / ui-pro — opens with the
    "Degraded ≠ Full" warning per D-C-1 §9 R1 mitigation). Pairs with
    `tests/test_degraded_mode.py` regression suite.

    v11.3.0 grew this set 17 → 19 by appending two NEW Tier-2 references
    in a single MINOR cycle: ``grill-mode.md`` (the grill-with-docs
    operating contract — one-question-at-a-time interview discipline,
    codebase-first exploration, fuzzy-term sharpening, scenario probing,
    ADR 3-condition gate; parallel-orthogonal to PLAN MODE) and
    ``domain-awareness.md`` (the CONTEXT.md authoring rules + ADR format
    + 3-condition ADR gate companion to grill-mode.md). Pairs with
    Workflow rules W-22 (Grill Mode Activation Contract) and W-23
    (Domain Glossary Maintenance).

    v11.4.0 grew this set 19 → 20 by appending one NEW Tier-2 reference:
    ``subagent-patterns.md`` (the philschmid 2026 4-pattern subagent
    taxonomy operating contract — Inline Tool / Fan-Out / Agent Pool /
    Teams selection decision tree, DevolaFlow current coverage matrix,
    Pattern 3 forward-compat plan, Pattern 4 P5-Forbidden rationale, and
    v12.0.0 NEST schema roadmap pre-staging). Pairs with Workflow rule
    W-24 (Subagent Pattern Selection).

    v12.5.0 PV-05 grew this set 21 → 22 by appending one NEW Tier-2
    reference: ``codegraph.md`` (the operating contract for the
    `colbymchenry/codegraph` integration — 9 MCP tools, CLI surface,
    workflow integration map, degraded-mode fallback, cache management;
    primary deliverable of the v12.5.0 EXPANSION MINOR cycle). Pairs
    with the new `code_intelligence` plugin role (5th of 5) and the
    Python wrapper at `src/devolaflow/codegraph/`."""
    _, out_dir = cursor_build
    refs_dir = out_dir / "references"
    assert refs_dir.is_dir(), "cursor adapter must emit references/ directory"

    source_refs = _find_project_root() / "workflow-system" / "agent" / "references"
    expected = {p.name for p in source_refs.glob("*.md")}
    actual = {p.name for p in refs_dir.glob("*.md")}
    assert expected == actual, (
        f"Cursor references mismatch — missing: {expected - actual}, extra: {actual - expected}"
    )
    # Derived from the SF-4 canonical set (tests.ghost.test_registries.
    # _SF4_REFERENCE_SET) instead of a hardcoded literal per G-028.
    assert len(actual) == _EXPECTED_REFERENCE_COUNT, (
        f"expected {_EXPECTED_REFERENCE_COUNT} reference files "
        f"(len(_SF4_REFERENCE_SET)), got {len(actual)}"
    )


def test_cursor_examples_golden(cursor_build):
    """All canonical example files are copied into ``examples/``."""
    _, out_dir = cursor_build
    examples_dir = out_dir / "examples"
    assert examples_dir.is_dir(), "cursor adapter must emit examples/ directory"

    source_examples = _find_project_root() / "workflow-system" / "agent" / "examples"
    expected = {p.name for p in source_examples.glob("*.md")}
    actual = {p.name for p in examples_dir.glob("*.md")}
    assert expected == actual, (
        f"Cursor examples mismatch — missing: {expected - actual}, extra: {actual - expected}"
    )
    # Derived from the `examples/` entries of scripts.sync_cursor_skill.
    # MIRRORED_FILES instead of a hardcoded literal per G-028.
    assert len(actual) == _EXPECTED_EXAMPLE_COUNT, (
        f"expected {_EXPECTED_EXAMPLE_COUNT} example files "
        f"(examples/ entries of MIRRORED_FILES), got {len(actual)}"
    )


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
