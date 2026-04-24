"""v9.0.0 PV-07 (ADR-007 D3) — Per-task-type AGENTS.md slicing tests.

Pins the OPERATOR-VISIBLE breaking-change facet of v9.0.0 MAJOR semver:

* **R5 strict default-OFF**: when ``meta.agents_md_slice.enabled: false``
  (the v9.0.0 default), ``select_agents_md_slice(task_type)`` returns the
  full AGENTS.md byte-identical to the v8.5.1 surface.
* **Per-profile slicing semantics**: when enabled, the slicer filters
  AGENTS.md by layer-prefix per the per-profile mapping in
  ``context_profiles.yaml#meta.agents_md_slice.profiles``.
* **Fallback semantics**: unmatched task types fall back to the full
  AGENTS.md (or a named profile if ``fallback`` points to one).
* **Layer dropping**: when a profile omits a layer key entirely, the
  layer header (``# Workflow Rules``) is dropped along with every rule
  in that layer.

The tests are intentionally lightweight — they exercise the Python
selector function directly rather than driving the full L0/L1/L2/L3
dispatch chain (which is exercised by the EvoBench scenario suite).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
import yaml

from devolaflow.task_adaptive_selector import (
    _filter_agents_md_by_profile,
    _read_agents_md,
    _split_agents_md_into_layers,
    count_agents_md_rules,
    select_agents_md_slice,
)


@pytest.fixture(scope="module")
def project_root() -> Path:
    """Return the repository root."""
    return Path(__file__).resolve().parent.parent


@pytest.fixture
def slice_enabled_profiles_path(project_root: Path) -> Path:
    """Return a temp profiles YAML with `agents_md_slice.enabled: true`.

    Per ADR-007 D3, the slice defaults to OFF — operators opt in via
    config. The fixture writes a temp config that flips the slice ON,
    so the slicing semantics tests can exercise the actual filter.
    The temp file is cleaned up after the test.
    """
    base = yaml.safe_load(
        (project_root / "workflow-system/agent/context_profiles.yaml").read_text(encoding="utf-8")
    )
    base["meta"]["agents_md_slice"]["enabled"] = True
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as f:
        yaml.safe_dump(base, f)
        path = Path(f.name)
    yield path
    path.unlink(missing_ok=True)


def test_slice_disabled_returns_full_byte_identical(project_root: Path) -> None:
    """ADR-007 D3 R5 strict: default OFF returns full AGENTS.md byte-identical.

    Pins the v9.0.0 byte-stable invariant — operators on the default
    `meta.agents_md_slice.enabled: false` see the full AGENTS.md surface
    bit-for-bit identical to the v8.5.1 v9.0.0 PV-07 compile output.
    """
    full_text = _read_agents_md()
    assert full_text, "AGENTS.md must be present and non-empty"

    for task_type in ("hotfix", "feature", "research", "convergence", "unknown_task"):
        result = select_agents_md_slice(task_type)
        assert result["slice_enabled"] is False, (
            f"slice should be OFF by default for {task_type!r} (ADR-007 D3 R5 strict)"
        )
        assert result["sliced_text"] == full_text, (
            f"slice OFF must return full AGENTS.md byte-identical for {task_type!r}"
        )
        assert result["included_rules"] == "all"
        assert result["skipped_rules"] == []
        assert result["slice_savings_pct"] == 0.0


def test_slice_hotfix_includes_only_relevant_layers(
    slice_enabled_profiles_path: Path,
) -> None:
    """ADR-007 D3: hotfix slice keeps Soul + (A-1, A-2) + (C-1..C-3, C-8) + (W-9, W-11).

    Per `.local/research/v9.0.0_pv07_rule_audit.md` §2.2 hotfix row.
    Hotfix Task Agents skip the full Workflow layer (only W-9 SI-10 +
    W-11 gate apply to a 1-bug fix), most of Architecture (only A-1
    hierarchy + A-2 cache invariants apply), and most of Conventions
    (only the pre-commit / lean-message / verbatim / braces rules apply).
    """
    result = select_agents_md_slice("hotfix", profiles_path=slice_enabled_profiles_path)
    assert result["slice_enabled"] is True
    assert result["profile_name"] == "hotfix"

    included = result["included_rules"]
    assert isinstance(included, list)

    soul_ids = {r for r in included if r.startswith("S-")}
    assert soul_ids == {f"S-{i}" for i in range(1, 11)}, (
        f"hotfix should include all Soul (S-1..S-10), got {sorted(soul_ids)}"
    )

    arch_ids = {r for r in included if r.startswith("A-")}
    assert arch_ids == {"A-1", "A-2"}, (
        f"hotfix Architecture should be A-1, A-2 only, got {sorted(arch_ids)}"
    )

    conv_ids = {r for r in included if r.startswith("C-")}
    assert conv_ids == {"C-1", "C-2", "C-3", "C-8"}, (
        f"hotfix Conventions should be C-1, C-2, C-3, C-8, got {sorted(conv_ids)}"
    )

    workflow_ids = {r for r in included if r.startswith("W-")}
    assert workflow_ids == {"W-9", "W-11"}, (
        f"hotfix Workflow should be W-9, W-11 only, got {sorted(workflow_ids)}"
    )

    style_ids = {r for r in included if r.startswith("ST-")}
    assert style_ids == set(), f"hotfix should drop all Style rules, got {sorted(style_ids)}"

    assert result["slice_savings_pct"] > 30.0, (
        f"hotfix slice should save > 30% tokens, got {result['slice_savings_pct']}%"
    )


def test_slice_research_minimal_corpus(slice_enabled_profiles_path: Path) -> None:
    """ADR-007 D3: research slice is the most aggressive — Soul + A-1 + (C-1..C-3) + (W-1, W-2).

    Research Task Agents are single-stage with minimal ceremony — no
    architecture cache invariants (A-2..A-5), no test/lint rules
    (C-4..C-9), no convergence-cycle Workflow rules (W-3..W-21). The
    slice should achieve > 60% token savings.
    """
    result = select_agents_md_slice("research", profiles_path=slice_enabled_profiles_path)
    assert result["slice_enabled"] is True
    assert result["profile_name"] == "research"

    included = result["included_rules"]
    assert isinstance(included, list)

    arch_ids = {r for r in included if r.startswith("A-")}
    assert arch_ids == {"A-1"}, f"research Architecture should be A-1 only, got {sorted(arch_ids)}"

    conv_ids = {r for r in included if r.startswith("C-")}
    assert conv_ids == {"C-1", "C-2", "C-3"}, (
        f"research Conventions should be C-1, C-2, C-3, got {sorted(conv_ids)}"
    )

    workflow_ids = {r for r in included if r.startswith("W-")}
    assert workflow_ids == {"W-1", "W-2"}, (
        f"research Workflow should be W-1, W-2 only, got {sorted(workflow_ids)}"
    )

    assert result["slice_savings_pct"] > 60.0, (
        f"research slice should save > 60% tokens, got {result['slice_savings_pct']}%"
    )


def test_slice_convergence_full_corpus(slice_enabled_profiles_path: Path) -> None:
    """ADR-007 D3: convergence slice keeps the full canonical AGENTS.md (0% savings).

    Convergence and rdrr Task Agents need the full rule corpus because
    multi-round dispatch traverses every layer. The "full" mapping
    (every layer == "all") preserves byte-identical AGENTS.md.
    """
    result = select_agents_md_slice("convergence", profiles_path=slice_enabled_profiles_path)
    assert result["slice_enabled"] is True
    assert result["profile_name"] == "convergence"

    full_census = count_agents_md_rules()

    included = result["included_rules"]
    assert isinstance(included, list)

    assert len(included) == full_census["total"], (
        f"convergence slice should include every rule ({full_census['total']}), got {len(included)}"
    )

    assert result["slice_savings_pct"] == 0.0, (
        f"convergence slice should save 0% tokens, got {result['slice_savings_pct']}%"
    )


def test_slice_unmatched_falls_back_to_full(
    slice_enabled_profiles_path: Path,
) -> None:
    """ADR-007 D3: unmatched task type falls back to the full AGENTS.md (safe default).

    The `fallback: full` config key (ADR-007 D3 default) means any
    `task_type` that doesn't match a `profiles.<name>` key returns the
    full AGENTS.md surface unchanged — preserving R5 strict for
    operators with custom task types.
    """
    result = select_agents_md_slice(
        "totally_unknown_task_xyz", profiles_path=slice_enabled_profiles_path
    )
    full_text = _read_agents_md()

    assert result["sliced_text"] == full_text, "unmatched task should return full AGENTS.md"
    assert result["included_rules"] == "all"
    assert result["skipped_rules"] == []
    assert result["slice_savings_pct"] == 0.0


def test_slice_skipped_layer_drops_layer_header(project_root: Path) -> None:
    """ADR-007 D3: when a profile omits a layer key, the layer header is dropped too.

    The `_filter_agents_md_by_profile` helper drops both the rule body
    AND the layer header (`# Workflow Rules (P3) — ...`) when no rule in
    that layer survives. Pinned via direct helper call so the test
    works without flipping the YAML config.
    """
    full_text = _read_agents_md()

    profile_layers = {
        "soul": "all",
        "architecture": ["A-1"],
        "conventions": [],
    }

    sliced, included, skipped = _filter_agents_md_by_profile(full_text, profile_layers)

    assert "# Workflow Rules" not in sliced, "skipped layer header must be dropped"
    assert "# Style Rules" not in sliced, "skipped layer header must be dropped"
    assert "## W-1" not in sliced, "rules under skipped layer must be dropped"
    assert "## A-1" in sliced, "kept rule must be present"

    assert any(rid.startswith("W-") for rid in skipped), "Workflow rules should be in skipped"
    assert all(not rid.startswith("W-") for rid in included), "no Workflow rules in included"


def test_split_agents_md_into_layers_handles_canonical_structure(
    project_root: Path,
) -> None:
    """ADR-007 D3 helper: _split_agents_md_into_layers parses the canonical AGENTS.md."""
    text = _read_agents_md()
    layers = _split_agents_md_into_layers(text)

    layer_names = [name for name, _, _ in layers]
    assert layer_names == [
        "Soul Rules",
        "Architecture Rules",
        "Conventions Rules",
        "Workflow Rules",
    ], f"AGENTS.md layer order drift: {layer_names}"

    soul_rules = [rid for rid, _ in layers[0][2]]
    assert soul_rules == [f"S-{i}" for i in range(1, 11)], f"Soul rule IDs drift: {soul_rules}"

    arch_rules = [rid for rid, _ in layers[1][2]]
    assert arch_rules == [f"A-{i}" for i in range(1, 6)], (
        f"Architecture rule IDs drift: {arch_rules}"
    )

    workflow_rules = [rid for rid, _ in layers[3][2]]
    assert workflow_rules[-1] == "W-21", (
        f"W-21 (Soul-set freeze governance, ADR-007 D4) should be last Workflow rule, "
        f"got {workflow_rules[-1]}"
    )
    assert len(workflow_rules) == 21, (
        f"Workflow should have 21 rules (W-1..W-21), got {len(workflow_rules)}"
    )


def test_count_agents_md_rules_matches_layer_split(project_root: Path) -> None:
    """ADR-007 D5: count_agents_md_rules totals match _split_agents_md_into_layers."""
    text = _read_agents_md()
    layers = _split_agents_md_into_layers(text)
    expected_total = sum(len(rules) for _, _, rules in layers)

    census = count_agents_md_rules()

    assert census["total"] == expected_total, (
        f"count mismatch: census {census['total']} vs split-derived {expected_total}"
    )
    assert census["total"] <= 60, (
        f"AGENTS.md rule count {census['total']} exceeds the 60 HARD cap (ADR-007 D5)"
    )
