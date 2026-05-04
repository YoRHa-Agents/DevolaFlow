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
    """Sanity: shape matches the SF-3 contract (15-refs / 4-examples since v10.5.0 PV-01).

    v8.0.0 P-08 grew the reference set 8 → 9 by appending
    ``references/behavioral-guidelines.md`` (the L3 behavioral primitives reference
    wired through the new top-level ``behavioral_guidelines`` dispatch field at
    ``schemas/lean-dispatch.yaml#layout_invariant.canonical_order`` position 14,
    schema version 3). Per Rule 6 (P6 Preserve Cached Prefix), positions 1–13
    remained byte-identical; the new field is appended at position 14.

    v8.3.0 PV-09 grew the reference set 9 → 10 by appending
    ``references/agent-workspace.md`` (the change-driven workspace reference
    covering ``.local/.agent/``, append-only handoff envelopes, source-of-truth
    specs, and per-artifact token budgets). Pairs with the change-driven workflow
    template (v8.2.6) and the ``devolaflow.agent_workspace`` Python API (v8.2.5+).

    v8.4.0 rollup grew the reference set 10 → 11 by appending
    ``references/shell-proxy.md`` (the RTK + memory-router stack reference
    covering the runtime-plugins.yaml RTK row, the shell_proxy/ package, the
    pre_shell_call lifecycle hook, the memory_router/ planning fast-path, and
    the ``.local/memory/{cases,commands}/`` recipe layers). Pairs with the
    v8.3.1..v8.3.4 PV-01..PV-04 surface area closing R-001+R-002+M-001+M-002.

    v9.0.0 PV-01 (v8.4.1) grew the reference set 11 → 12 by appending
    ``references/plan-mode-enforcement.md`` (the plan-mode L0 operating
    contract reference absorbing SKILL.md §"Mode Awareness" PLAN MODE detail
    + §"Reinforcement Rules" mechanism, freeing ~57 lines of SKILL.md
    headroom and closing R7 carry-forward + B-01 SKILL.md ceiling crisis
    from .local/research/v9.0.0_gap_analysis.md §3.1).

    v9.0.0 PV-05 (v8.5.0) grew the reference set 12 → 13 by appending
    ``references/env-flags.md`` (the canonical DEVOLAFLOW_* env-var
    inventory: 8 active runtime flags + 6 forward-declared gate-primitive
    flags + 4 BG default-on primitives + 3 test-fixture flags). Pairs with
    Workflow Rule W-20 (env-flag reuse vs new-flag policy) so the rule has
    a single source of truth to enforce against.

    v9.0.0 PV-06 (v8.5.1) grew the reference set 13 → 14 by appending
    ``references/compression-pipeline.md`` (the CompressionStage protocol
    + CompressionPipeline orchestrator + 6-transform unification +
    multi-pass filter chain T3 #5 reference — ~408 lines, within Large
    tier 1000 ceiling per SF-1). Pairs with
    ``src/devolaflow/compression_pipeline.py`` and
    ``schemas/compression-pipeline.yaml``.

    v10.4.0 PV-05 grew the reference set 14 → 15 by appending
    ``references/troubleshooting.md`` (the operator troubleshooting
    handbook with quick lookup index + per-symptom diagnostic patterns +
    escalation patterns harvested from v8.0.0 → v10.3.0 retros — ~424
    lines, well within Large tier 1000 ceiling per SF-1). Pairs with
    the v10.4.0 audit scripts (``audit_reference_utilization.py`` /
    ``audit_long_reference_usage.py``) and the scaffold CLIs
    (``scaffold_template.py`` / ``scaffold_reference.py``).

    v10.5.0 PV-01 grew the example set 3 → 4 by appending
    ``examples/multi-stage-trace.md`` (the multi-team analyze + cross-
    stage merge counter-example referenced by the SKILL.md §"Quick
    Action Decision" advisory annotation that v10.5.0 D-A-1 ships).
    The audit `scripts/audit_layer_usage.py` documents WHEN the L1 +
    L2 layers genuinely earn their cost; this example walks one such
    scenario verbatim. Stays well within XL tier 1600-line ceiling
    per SF-1.
    """
    assert len(_REF_FILES) == 15, f"expected 15 references, got {len(_REF_FILES)}: {_REF_FILES}"
    assert len(_EXAMPLE_FILES) == 4, (
        f"expected 4 examples, got {len(_EXAMPLE_FILES)}: {_EXAMPLE_FILES}"
    )
