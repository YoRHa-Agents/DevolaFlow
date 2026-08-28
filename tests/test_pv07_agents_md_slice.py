"""v9.0.0 PV-07 (ADR-007 D3) — Per-task-type AGENTS.md slicing tests.

Pins the OPERATOR-VISIBLE breaking-change facet of v9.0.0 MAJOR semver +
the v9.1.5 PV-05 default-ON flip:

* **v9.1.5 PV-05 default-ON**: ``meta.agents_md_slice.enabled`` defaults
  to ``true`` in ``context_profiles.yaml``; L3 dispatches automatically
  receive the per-task-type slice. Pinned by
  :func:`test_agents_md_slice_default_on_in_v9_1_5`.
* **R5 strict env-flag opt-out**: ``DEVOLAFLOW_AGENTS_MD_SLICE=0``
  reverts to the v9.1.4 byte-identical full-AGENTS.md behaviour. Pinned
  by :func:`test_agents_md_slice_env_flag_0_opts_out`.
* **YAML opt-out path**: when ``meta.agents_md_slice.enabled`` is set
  to ``false`` (operator-authored override), the function returns full
  AGENTS.md byte-identical. Pinned by
  :func:`test_slice_yaml_disabled_returns_full_byte_identical`.
* **Per-profile slicing semantics**: when enabled, the slicer filters
  AGENTS.md by layer-prefix per the per-profile mapping in
  ``context_profiles.yaml#meta.agents_md_slice.profiles``.
* **Fallback semantics**: unmatched task types fall back to the full
  AGENTS.md (or a named profile if ``fallback`` points to one).
* **Layer dropping**: when a profile omits a layer key entirely, the
  layer header (``# Workflow Rules``) is dropped along with every rule
  in that layer.

The tests are intentionally lightweight — they exercise the Python
selector function directly rather than driving the full L0/L1/L2
dispatch chain (which is exercised by the EvoBench scenario suite).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
import yaml

# v14.5.0 (ADR-006 G-025): the slicing subsystem moved to
# devolaflow.agents_md_slice; v17.0.0 retired the task_adaptive_selector
# re-export shims, so public symbols now import from the owner module too.
from devolaflow.agents_md_slice import (
    _AGENTS_MD_SLICE_ENV_FLAG,
    _agents_md_slice_env_override,
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

    Pre-v9.1.5 the canonical YAML default was ``enabled: false`` and this
    fixture flipped it ON for the slicing-semantics tests. v9.1.5 PV-05
    flipped the canonical default to ``true``, so the fixture is now a
    no-op transformation — but it stays in place to keep the tests
    independent of any future YAML default change.
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


@pytest.fixture
def slice_yaml_disabled_profiles_path(project_root: Path) -> Path:
    """Return a temp profiles YAML with ``agents_md_slice.enabled: false``.

    v9.1.5 PV-05 flipped the canonical YAML default to ``true``. This
    fixture creates a temp YAML that opts out at the YAML layer (the
    operator-authored override path), so the byte-identical full-
    AGENTS.md test stays valid even after the canonical default flip.
    The temp file is cleaned up after the test.
    """
    base = yaml.safe_load(
        (project_root / "workflow-system/agent/context_profiles.yaml").read_text(encoding="utf-8")
    )
    base["meta"]["agents_md_slice"]["enabled"] = False
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as f:
        yaml.safe_dump(base, f)
        path = Path(f.name)
    yield path
    path.unlink(missing_ok=True)


def test_slice_yaml_disabled_returns_full_byte_identical(
    project_root: Path,
    slice_yaml_disabled_profiles_path: Path,
) -> None:
    """ADR-007 D3 + v9.1.5 PV-05: YAML opt-out (enabled: false) returns full text.

    With ``meta.agents_md_slice.enabled: false`` the selector returns
    full AGENTS.md byte-identical to the unsliced surface — preserving
    the v9.1.4 byte-stable behaviour for operators who explicitly set
    the YAML flag back to ``false``. Pre-v9.1.5 this test exercised the
    canonical YAML default; post-v9.1.5 the canonical default is
    ``true`` and the explicit YAML override is the byte-stable path.
    """
    full_text = _read_agents_md()
    assert full_text, "AGENTS.md must be present and non-empty"

    for task_type in ("hotfix", "feature", "research", "convergence", "unknown_task"):
        result = select_agents_md_slice(
            task_type,
            profiles_path=slice_yaml_disabled_profiles_path,
            env={},
        )
        assert result["slice_enabled"] is False, (
            f"slice should be OFF when YAML enabled=false for {task_type!r}"
        )
        assert result["sliced_text"] == full_text, (
            f"YAML opt-out must return full AGENTS.md byte-identical for {task_type!r}"
        )
        assert result["included_rules"] == "all"
        assert result["skipped_rules"] == []
        assert result["slice_savings_pct"] == 0.0


def test_agents_md_slice_default_on_in_v9_1_5(project_root: Path) -> None:
    """v9.1.5 PV-05 — canonical YAML default flipped to ``enabled: true``.

    Pins the operator-visible behaviour change of v9.1.5 PV-05: the
    canonical ``workflow-system/agent/context_profiles.yaml`` ships with
    ``meta.agents_md_slice.enabled: true``, so dispatchers on the
    default config receive sliced AGENTS.md content automatically.
    Operators who want the prior v9.1.4 byte-stable behaviour set
    ``DEVOLAFLOW_AGENTS_MD_SLICE=0`` (the W-20 reuse opt-out flag).
    """
    profiles_path = project_root / "workflow-system/agent/context_profiles.yaml"
    config = yaml.safe_load(profiles_path.read_text(encoding="utf-8"))
    slice_cfg = config.get("meta", {}).get("agents_md_slice", {})

    assert slice_cfg.get("enabled") is True, (
        "v9.1.5 PV-05 contract: canonical context_profiles.yaml MUST ship with "
        "agents_md_slice.enabled: true (the operator-visible default-ON flip). "
        f"Current YAML value: {slice_cfg.get('enabled')!r}"
    )


def test_agents_md_slice_env_flag_0_opts_out(project_root: Path) -> None:
    """v9.1.5 PV-05 — DEVOLAFLOW_AGENTS_MD_SLICE=0 forces byte-identical full AGENTS.md.

    R5 strict opt-out proof — with the env flag set to ``"0"`` the
    selector returns the unsliced AGENTS.md byte-identical to the
    v9.1.4 surface, regardless of the canonical YAML default
    (``enabled: true`` post-v9.1.5). The headline operator-visible
    behaviour change of v9.1.5 PV-05 is reversible via this env flag
    (W-20 reuse — no new env flag introduced).

    This test EXPLICITLY covers all 5 canonical task types in §"Quick
    Action Decision" plus an unknown-task fallback because the cache-
    prefix bytes are the contract — every dispatcher MUST see the same
    AGENTS.md byte-string when opted out.
    """
    full_text = _read_agents_md()
    assert full_text, "AGENTS.md must be present and non-empty"

    for task_type in ("hotfix", "feature", "research", "convergence", "unknown_task"):
        result = select_agents_md_slice(
            task_type,
            env={_AGENTS_MD_SLICE_ENV_FLAG: "0"},
        )
        assert result["slice_enabled"] is False, (
            f"DEVOLAFLOW_AGENTS_MD_SLICE=0 must force opt-out for {task_type!r} "
            f"(R5 strict — the headline v9.1.5 escape hatch); slice_enabled was "
            f"{result['slice_enabled']!r}"
        )
        assert result["sliced_text"] == full_text, (
            f"env-flag opt-out MUST return full AGENTS.md byte-identical for "
            f"{task_type!r} (the v9.1.4 byte-stable invariant; downstream tools "
            f"that audit the cache prefix MUST see the same bytes)"
        )
        assert result["included_rules"] == "all"
        assert result["skipped_rules"] == []
        assert result["slice_savings_pct"] == 0.0

    # R5 strict — env-flag override helper returns False ONLY for the
    # literal "0"; loose variants ("0.0", " 0 ", "false") fall through
    # to YAML default. The v9.1.5 PV-05 conjunction contract per
    # references/env-flags.md §6.
    assert _agents_md_slice_env_override({_AGENTS_MD_SLICE_ENV_FLAG: "0"}) is False
    assert _agents_md_slice_env_override({_AGENTS_MD_SLICE_ENV_FLAG: "1"}) is True
    for loose in ("0.0", " 0 ", "false", "0\n", "00", "1.0", "true", "yes", "on"):
        assert _agents_md_slice_env_override({_AGENTS_MD_SLICE_ENV_FLAG: loose}) is None, (
            f"R5 strict violation: env-flag value {loose!r} must fall through "
            f"to YAML default (return None), not be coerced to True/False"
        )
    assert _agents_md_slice_env_override({}) is None
    assert _agents_md_slice_env_override(None) is not False, (
        "env=None must defer to os.environ rather than returning False; "
        "the explicit empty-dict path is the safe test override"
    )


def test_slice_hotfix_includes_only_relevant_layers(
    slice_enabled_profiles_path: Path,
) -> None:
    """ADR-007 D3: hotfix slice keeps Soul + (A-1, A-2) + (C-1, C-2) + (W-4, W-9).

    Per `.local/research/v9.0.0_pv07_rule_audit.md` §2.2 hotfix row.
    Hotfix Task Agents skip the full Workflow layer (only W-9 SI-10 +
    the gate/benchmark guard apply to a 1-bug fix), most of Architecture
    (only A-1 hierarchy + A-2 cache invariants apply), and most of
    Conventions (only the pre-commit / lean-message / verbatim rules
    apply). C-8 (C++ braces) was a hotfix/review slice member until its
    v14.2.1 deletion per G-012 (dead rule — zero C++ files in repo);
    W-11 (gate suite) folded into W-4 at the v15.0.0 rule-diet
    (v15-ADR-004 / v15-ADR-008 §1), so the slice carries W-4 instead.
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
    assert conv_ids == {"C-1", "C-2"}, (
        f"hotfix Conventions should be C-1, C-2, got {sorted(conv_ids)}"
    )

    workflow_ids = {r for r in included if r.startswith("W-")}
    assert workflow_ids == {"W-4", "W-9"}, (
        f"hotfix Workflow should be W-4, W-9 only, got {sorted(workflow_ids)}"
    )

    style_ids = {r for r in included if r.startswith("ST-")}
    assert style_ids == set(), f"hotfix should drop all Style rules, got {sorted(style_ids)}"

    assert result["slice_savings_pct"] > 30.0, (
        f"hotfix slice should save > 30% tokens, got {result['slice_savings_pct']}%"
    )


def test_slice_research_minimal_corpus(slice_enabled_profiles_path: Path) -> None:
    """ADR-007 D3: research slice is the most aggressive — Soul + A-1 + (C-1, C-2) + (W-1, W-2).

    Research Task Agents are single-stage with minimal ceremony — no
    architecture cache invariants (A-2..A-5), no test/lint rules
    (C-4, C-6, C-7), no convergence-cycle Workflow rules (W-3..W-21). The
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
    assert conv_ids == {"C-1", "C-2"}, (
        f"research Conventions should be C-1, C-2, got {sorted(conv_ids)}"
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
    # v9.1.2 PV-02 (Architecture rule A-6 "Workspace Engagement Auto-Activation"
    # per `.rules/architecture.mdc` §A-6) bumped Architecture from 5 → 6 rules.
    # v11.0.5 PV-05 (Architecture rule A-7 "Cascade-Depth Invariant for Standard+
    # Dispatches" per `.rules/architecture.mdc` §A-7) bumped Architecture from
    # 6 → 7 rules. W-21 Soul-set freeze preserved at 10 entries; A-7 lands at
    # Architecture per ADR-007 §"Soul-vs-Architecture" decision-rule on
    # conditional + implementation-coupled invariants.
    assert arch_rules == [f"A-{i}" for i in range(1, 8)], (
        f"Architecture rule IDs drift: {arch_rules}"
    )

    workflow_rules = [rid for rid, _ in layers[3][2]]
    # v11.3.0 grew Workflow rules 21 → 23 by appending W-22 "Grill Mode
    # Activation Contract" + W-23 "Domain Glossary Maintenance" (the
    # grill-with-docs integration MINOR cycle). v11.4.0 grew Workflow
    # rules 23 → 24 by appending W-24 "Subagent Pattern Selection" (the
    # subagent-patterns-2026 prep cycle targeting v12.0.0 graduation).
    # v17.4.0 grows Workflow rules 24 → 25 by appending W-25 "Host Support
    # Contract Evidence and Revision"; v19.0.0 adds W-26..W-28 and folds
    # W-19 into W-7, leaving W-28 last and 21 live Workflow rules.
    # All three rules land at the Workflow layer (not Soul) per ADR-007
    # §"Soul-vs-Architecture" decision-rule on conditional + activation-
    # coupled invariants — mirrors the v11.0.5 PV-05 A-7 landing
    # rationale. W-21 Soul-set freeze preserved at 10 entries.
    assert workflow_rules[-1] == "W-28", (
        f"W-28 (Local-Archive Index-Generation Honesty) "
        f"should be last Workflow rule, got {workflow_rules[-1]}"
    )
    # v15.0.0 rule-diet (v15-ADR-004): W-10..W-15 folded into W-4/W-5/W-6/
    # C-6; v19.0.0 folds W-19 into W-7 and adds W-26..W-28. Retired ids
    # remain unused, so the layer carries 21 live rules.
    assert len(workflow_rules) == 21, (
        f"Workflow should have 21 rules after v19 consolidation, got {len(workflow_rules)}"
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


def test_cached_slice_summary_reads_once_and_invalidates_on_mtime(
    slice_enabled_profiles_path: Path,
    project_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """v17.0.0 R3 (D-R3-1/D-R3-2): the compact summary is served from the
    module-level (path, mtime_ns, task_type)-keyed cache — repeat calls
    never re-read AGENTS.md; an mtime bump invalidates; the projection
    matches select_agents_md_slice verbatim."""
    import os

    import devolaflow.agents_md_slice as agents_md_slice
    from devolaflow.agents_md_slice import cached_slice_summary

    agents_md_copy = tmp_path / "AGENTS-cache-test.md"
    agents_md_copy.write_text(
        (project_root / "AGENTS.md").read_text(encoding="utf-8"), encoding="utf-8"
    )

    reads: list[Path | None] = []
    real_read = agents_md_slice._read_agents_md

    def counting_read(agents_md_path: Path | None = None) -> str:
        reads.append(agents_md_path)
        return real_read(agents_md_path)

    monkeypatch.setattr(agents_md_slice, "_read_agents_md", counting_read)
    kwargs = {
        "profiles_path": slice_enabled_profiles_path,
        "agents_md_path": agents_md_copy,
        "env": {},
    }

    first = cached_slice_summary("hotfix", **kwargs)
    second = cached_slice_summary("hotfix", **kwargs)
    assert len(reads) == 1, "cache hit must not re-read AGENTS.md"
    assert first == second

    full = select_agents_md_slice("hotfix", **kwargs)
    assert first == {
        "profile_name": full["profile_name"],
        "slice_enabled": full["slice_enabled"],
        "total_tokens": full["total_tokens"],
        "full_tokens": full["full_tokens"],
        "slice_savings_pct": full["slice_savings_pct"],
        "included_rules_count": len(full["included_rules"]),
    }
    assert first["slice_enabled"] is True
    assert first["slice_savings_pct"] > 0

    stat = agents_md_copy.stat()
    os.utime(agents_md_copy, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))
    reads.clear()
    cached_slice_summary("hotfix", **kwargs)
    assert len(reads) >= 1, "mtime bump must invalidate the cache entry"
