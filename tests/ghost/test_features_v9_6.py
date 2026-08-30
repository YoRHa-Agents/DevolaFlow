"""Ghost audit — per-cycle W-18 feature stanzas for the v9.6 cycle.

Split from ``tests/test_no_ghost_features.py`` per v15-ADR-001
(v14.3.0). New W-18 stanzas for a v9.6.x release append HERE; the
next MINOR cycle rotates to a fresh ``test_features_v<MAJ>_<MIN>.py``.
"""

from __future__ import annotations

from pathlib import Path

# ============================================================================
# v9.6.0 — Reference Library Refresh (PV-01..PV-05).
# ============================================================================

# v9.6.0 PV-04 yaml entry-count contract: 11 active + 10 periodic = 21 total.
# Header comment was stale "10 + 9 = 19" pre-PV-04; corrected per D-R-7.
# v12.5.0 grew active_tracking by appending codegraph, and v13.0.0
# appended impeccable; header comment refreshed to "13 + 10 = 23 total".
_V9_6_0_TOTAL_REFS: int = 23


_V9_6_0_ACTIVE_REFS: int = 13


_V9_6_0_PERIODIC_REFS: int = 10


# v9.6.0 PV-02 reference-doc anchor contract — the 4 NEW subsections wired
# into the agent-facing reference docs by the high-relevance integration.
# Each anchor is the literal heading line (must appear verbatim).
_V9_6_0_REFERENCE_DOC_ANCHORS: tuple[tuple[str, str], ...] = (
    (
        "workflow-system/agent/references/decomposition-gate.md",
        "### 6.0 Stagnation detection (v9.6.0)",
    ),
    (
        "workflow-system/agent/references/team-roles.md",
        "### Two-stage review pattern (v9.6.0 — superpowers integration)",
    ),
    (
        "workflow-system/agent/references/execution-protocol.md",
        "### 1b.1 Pre-handoff verification gate (v9.6.0 — superpowers integration)",
    ),
    (
        "workflow-system/agent/references/meta-framework.md",
        "#### 2.2.1 Multi-team codebase analysis pattern "
        "(v9.6.0 — understand-anything integration)",
    ),
)


def test_v9_6_0_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v9.6.0: every NEW v9.6.0 surface has presence + structural coverage.

    Discharges the W-18 precondition for the v9.6.0 cycle-close MINOR —
    every CHANGELOG entry mentioning a v9.6.0 feature MUST have a
    backing ghost-audit lint in THIS file BEFORE the CHANGELOG entry
    is authored.

    v9.6.0 PV-05 cycle close pins:

    1. **Reference inventory shape (D-R-7 closure)** — yaml carries
       exactly 11 active + 10 periodic = 21 entries; header comment
       reflects the 21-entry count (not the legacy "10 + 9 = 19").
    2. **Bulk freshness (D-R-5 closure)** — every yaml entry has
       last_checked == "2026-05-02" after PV-04.
    3. **primelocus-hydra graduation (D-R-9 closure)** — entry carries
       tracking_status: "frozen_reference" + graduated_to_frozen_at
       audit field.
    4. **Reference-doc anchors (PV-02 deliverable)** — the 4 NEW
       subsection headings appear verbatim in their owning files.
    Failure modes:
      * "yaml ref count drift" → either an entry was added/removed
        outside the v9.6.0 PV chain OR yaml header comment regressed;
        re-check D-R-7 closure.
      * "stale last_checked" → PV-04 freshness sweep regressed; re-run
        the bulk update.
      * "primelocus-hydra not frozen" → PV-04 graduation regressed;
        re-apply the tracking_status flip.
      * "missing reference-doc anchor" → PV-02 reference doc edit was
        reverted; re-author the §X subsection per gap_analysis §3.1.
    """
    import yaml as yaml_lib

    yaml_path = (
        project_root / "workflow-system" / "agent" / "knowledge" / "reference-dependencies.yaml"
    )

    # §1 — Reference inventory shape.
    data = yaml_lib.safe_load(yaml_path.read_text(encoding="utf-8"))
    active = data.get("active_tracking", []) or []
    periodic = data.get("periodic_monitoring", []) or []
    assert len(active) == _V9_6_0_ACTIVE_REFS, (
        f"W-18 v9.6.0 violation: active_tracking count is {len(active)}, "
        f"expected {_V9_6_0_ACTIVE_REFS} (D-R-7 closure)"
    )
    assert len(periodic) == _V9_6_0_PERIODIC_REFS, (
        f"W-18 v9.6.0 violation: periodic_monitoring count is "
        f"{len(periodic)}, expected {_V9_6_0_PERIODIC_REFS} (D-R-7)"
    )
    raw = yaml_path.read_text(encoding="utf-8")
    assert (
        f"{_V9_6_0_ACTIVE_REFS} active_tracking + "
        f"{_V9_6_0_PERIODIC_REFS} periodic_monitoring = "
        f"{_V9_6_0_TOTAL_REFS} total"
    ) in raw, (
        f"W-18 v9.6.0 violation: yaml header comment must reflect the "
        f"{_V9_6_0_ACTIVE_REFS} + {_V9_6_0_PERIODIC_REFS} = "
        f"{_V9_6_0_TOTAL_REFS} count per D-R-7"
    )

    # §2 — Bulk freshness. v9.6.0 PV-04 D-R-5 closure pinned all 21 entries
    # at 2026-05-02. v12.5.0 added codegraph at 2026-05-23; newer entries
    # are explicitly permitted per D-R-5,
    # which requires entries to be ≥ 2026-05-02 (the floor; not equality).
    # The carve-out preserves the no-stale-entries invariant while allowing
    # legitimately fresher additions to land per cycle.
    all_refs = active + periodic
    stale = [r["id"] for r in all_refs if (r.get("last_checked") or "") < "2026-05-02"]
    assert not stale, (
        f"W-18 v9.6.0 violation: yaml entries with stale last_checked "
        f"(< 2026-05-02 floor): {stale} (D-R-5 closure requires ALL "
        f"entries at 2026-05-02 or later)"
    )

    # §3 — primelocus-hydra graduation.
    ph = next((r for r in periodic if r["id"] == "primelocus-hydra"), None)
    assert ph is not None, (
        "W-18 v9.6.0 violation: primelocus-hydra missing from periodic_monitoring"
    )
    assert ph.get("tracking_status") == "frozen_reference", (
        f"W-18 v9.6.0 violation: primelocus-hydra tracking_status is "
        f"{ph.get('tracking_status')!r}, expected 'frozen_reference' "
        f"(D-R-9 closure)"
    )
    assert ph.get("graduated_to_frozen_at", "").startswith("v9.6.0 PV-04")

    # §4 — Reference-doc anchors.
    for rel_path, anchor in _V9_6_0_REFERENCE_DOC_ANCHORS:
        ref_file = project_root / rel_path
        assert ref_file.is_file(), f"W-18 v9.6.0 violation: reference doc {rel_path} missing"
        text = ref_file.read_text(encoding="utf-8")
        assert anchor in text, (
            f"W-18 v9.6.0 violation: {rel_path} missing v9.6.0 anchor "
            f"{anchor!r}; PV-02 integration regressed"
        )
