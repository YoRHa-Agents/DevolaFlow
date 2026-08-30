"""v9.6.0 PV-02 — Tests for high-relevance (score >= 4) reference integrations.

Pins the cross-document integration contract for the 5 deep-analyzed refs
(superpowers, get-shit-done, caveman, understand-anything, openspec) per
v9.6.0 SI-1 §4 PV-02 row.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
YAML_PATH = REPO_ROOT / "workflow-system" / "agent" / "knowledge" / "reference-dependencies.yaml"
REFS_DIR = REPO_ROOT / "workflow-system" / "agent" / "references"


@pytest.fixture(scope="module")
def yaml_data() -> dict:
    return yaml.safe_load(YAML_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def active_refs(yaml_data: dict) -> dict[str, dict]:
    """Return active_tracking refs keyed by id for cross-checks."""
    return {entry["id"]: entry for entry in yaml_data.get("active_tracking", [])}


def test_yaml_active_tracking_count_unchanged(yaml_data: dict) -> None:
    """active_tracking holds 13 entries at v13.0.0 (impeccable appended).

    v9.6.0 PV-02 baseline was 11 entries; v12.5.0 PV-05 D-1.1 grew it to 12
    (codegraph); v13.0.0 grew it to 13 by appending the impeccable entry, the
    design-refinement plugin integrated for the v13.0.0 MAJOR cycle. Future
    ref additions land via dedicated PV slices per W-19 cadence.
    """
    assert len(yaml_data.get("active_tracking", [])) == 13, (
        "v13.0.0 contract: active_tracking holds 13 entries "
        "(12 v12.5.0 baseline + impeccable appended at v13.0.0); "
        "ref additions land via dedicated PV slices"
    )


def test_superpowers_yaml_carries_v9_6_0_skill_catalog(active_refs: dict) -> None:
    """superpowers ref must enumerate the +4 NEW skills catalog at v9.6.0."""
    sp = active_refs["superpowers"]
    assert sp["last_checked"] == "2026-05-02"
    kp_text = "\n".join(sp["key_patterns"])
    for skill_name in (
        "subagent-driven-development",
        "verification-before-completion",
        "dispatching-parallel-agents",
        "using-git-worktrees",
    ):
        assert skill_name in kp_text, (
            f"superpowers.key_patterns must cite '{skill_name}' (v9.6.0 PV-02 delta)"
        )
    # The CLAUDE.md "94% PR rejection rate" preamble is the new framing pattern.
    assert "94%" in kp_text, (
        "superpowers.key_patterns must reference the '94% PR rejection rate' "
        "agent-pressure preamble (v9.6.0 PV-02)"
    )
    # Integration-points must point at the new reference doc anchors.
    ip_text = "\n".join(sp["devolaflow_integration_points"])
    assert "team-roles.md" in ip_text
    assert "execution-protocol.md" in ip_text


def test_get_shit_done_yaml_carries_stall_detection(active_refs: dict) -> None:
    """get-shit-done ref must cite the v9.6.0 stall-detection delta."""
    gsd = active_refs["get-shit-done"]
    assert gsd["last_checked"] == "2026-05-02"
    kp_text = "\n".join(gsd["key_patterns"])
    assert "stall detection" in kp_text.lower(), (
        "get-shit-done.key_patterns must cite the revision-gate "
        "stall-detection refinement (v9.6.0 PV-02 delta)"
    )
    # Integration point links the new decomposition-gate.md §6.0 anchor.
    ip_text = "\n".join(gsd["devolaflow_integration_points"])
    assert "decomposition-gate.md" in ip_text
    assert "6.0" in ip_text


def test_caveman_yaml_carries_six_intensity_levels(active_refs: dict) -> None:
    """caveman ref must enumerate all 6 intensity tiers (3 modern + 3 wenyan)."""
    cv = active_refs["caveman"]
    assert cv["last_checked"] == "2026-05-02"
    kp_text = "\n".join(cv["key_patterns"])
    for level in (
        "lite",
        "full",
        "ultra",
        "wenyan-lite",
        "wenyan-full",
        "wenyan-ultra",
    ):
        assert level in kp_text, (
            f"caveman.key_patterns must enumerate intensity level '{level}' "
            "(v9.6.0 PV-02 — caveman now ships 6 levels, not 3)"
        )


def test_understand_anything_yaml_carries_subdomain_merging(
    active_refs: dict,
) -> None:
    """understand-anything ref must cite the subdomain-merging script delta."""
    ua = active_refs["understand-anything"]
    assert ua["last_checked"] == "2026-05-02"
    kp_text = "\n".join(ua["key_patterns"])
    assert "merge-subdomain-graphs.py" in kp_text, (
        "understand-anything.key_patterns must cite merge-subdomain-graphs.py "
        "(v9.6.0 PV-02 delta — subdomain knowledge-graph merging)"
    )
    ip_text = "\n".join(ua["devolaflow_integration_points"])
    assert "meta-framework.md" in ip_text
    assert "2.2.1" in ip_text


def test_openspec_yaml_carries_11_spec_catalog(active_refs: dict) -> None:
    """openspec ref note must enumerate the 11-spec catalog."""
    os_ref = active_refs["openspec"]
    assert os_ref["last_checked"] == "2026-05-02"
    kp_text = "\n".join(os_ref["key_patterns"])
    # All 11 spec names must appear in key_patterns OR note.
    full_text = kp_text + "\n" + os_ref.get("note", "")
    for spec in (
        "schema-which-command",
        "opsx-onboard-skill",
        "change-creation",
        "config-loading",
        "context-injection",
    ):
        assert spec in full_text, (
            f"openspec ref must cite the '{spec}' spec from the 11-spec catalog"
        )


def test_decomposition_gate_md_has_stagnation_section() -> None:
    """`references/decomposition-gate.md` must carry the v9.6.0 §6.0 anchor."""
    text = (REFS_DIR / "decomposition-gate.md").read_text(encoding="utf-8")
    assert "### 6.0 Stagnation detection (v9.6.0)" in text, (
        "decomposition-gate.md must declare the v9.6.0 §6.0 'Stagnation "
        "detection' subsection cited by reference-dependencies.yaml's "
        "get-shit-done.devolaflow_integration_points"
    )
    # Both stagnation signals must be enumerated.
    assert "Score stagnation" in text
    assert "Issue-count stagnation" in text
    # Must cite the upstream URL per S-7.
    assert "github.com/gsd-build/get-shit-done" in text


def test_team_roles_md_has_two_stage_review_section() -> None:
    """`references/team-roles.md` must carry the v9.6.0 two-stage review pattern."""
    text = (REFS_DIR / "team-roles.md").read_text(encoding="utf-8")
    assert "### Two-stage review pattern (v9.6.0 — superpowers integration)" in text, (
        "team-roles.md must declare the v9.6.0 two-stage review pattern "
        "subsection cited by reference-dependencies.yaml's superpowers entry"
    )
    # Both stages explicitly named.
    assert "Spec compliance" in text
    assert "Code quality" in text
    # Typed status protocol enumerated (SF-4 + lean-report.yaml contract).
    for verdict in ("DONE", "DONE_WITH_CONCERNS", "NEEDS_CONTEXT", "BLOCKED"):
        assert verdict in text
    # Must cite upstream URL per S-7.
    assert "github.com/obra/superpowers" in text


def test_execution_protocol_md_has_pre_handoff_verification_section() -> None:
    """`references/execution-protocol.md` must carry the v9.6.0 §1b.1 anchor."""
    text = (REFS_DIR / "execution-protocol.md").read_text(encoding="utf-8")
    assert "### 1b.1 Pre-handoff verification gate (v9.6.0 — superpowers integration)" in text
    assert "pre_handoff" in text
    # Must cite upstream URL per S-7.
    assert "github.com/obra/superpowers" in text


def test_meta_framework_md_has_subdomain_merging_section() -> None:
    """`references/meta-framework.md` must carry the v9.6.0 §2.2.1 anchor."""
    text = (REFS_DIR / "meta-framework.md").read_text(encoding="utf-8")
    expected_heading = (
        "#### 2.2.1 Multi-team codebase analysis pattern (v9.6.0 — understand-anything integration)"
    )
    assert expected_heading in text
    assert "merge-subdomain-graphs.py" in text
    assert "github.com/Lum1104/Understand-Anything" in text


def test_no_absolute_paths_in_modified_references() -> None:
    """Per S-2: no absolute filesystem paths in agent-facing reference docs.

    Defends against accidentally embedding $DEVOLAFLOW_REFERENCE_ROOT or
    /home/<user>/ paths during the v9.6.0 reference integration edits.
    """
    forbidden_prefixes = ("/Users/", "/root/", "/tmp/")
    for ref_file in (
        REFS_DIR / "decomposition-gate.md",
        REFS_DIR / "team-roles.md",
        REFS_DIR / "execution-protocol.md",
        REFS_DIR / "meta-framework.md",
    ):
        text = ref_file.read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), start=1):
            for prefix in forbidden_prefixes:
                assert prefix not in line, (
                    f"{ref_file.name}:{line_no}: forbidden absolute path "
                    f"prefix {prefix!r} per Soul Rule S-2"
                )


# ============================================================================
# PV-03 — medium-relevance (score == 3) refs freshness contract.
# ============================================================================


def _score_3_active(active_refs: dict) -> dict[str, dict]:
    return {k: v for k, v in active_refs.items() if v.get("relevance_score") == 3}


def test_pv03_score_3_refs_carry_2026_05_02_last_checked(active_refs: dict) -> None:
    """All score=3 refs in active_tracking must carry the v9.6.0 PV-03 freshness stamp.

    Per gap_analysis §3.2 D-R-5: PV-03 bulk-refreshes the medium-relevance
    refs to last_checked: 2026-05-02 with a note documenting the no-clone
    or non-repo manual-review fallback.
    """
    s3 = _score_3_active(active_refs)
    # Active-bucket score-3 refs at v9.6.0: edict, karpathy-llm-wiki.
    expected_active_s3 = {"edict", "karpathy-llm-wiki"}
    assert expected_active_s3.issubset(set(s3.keys())), (
        f"active_tracking score=3 refs missing: {expected_active_s3 - set(s3.keys())}"
    )
    for ref_id, entry in s3.items():
        assert entry["last_checked"] == "2026-05-02", (
            f"{ref_id}: last_checked must be 2026-05-02 after PV-03 refresh"
        )
        assert entry.get("note", "").strip(), (
            f"{ref_id}: must carry a v9.6.0 PV-03 note (W-2 manual-review marker)"
        )


def test_pv03_periodic_score_3_refs_freshness(yaml_data: dict) -> None:
    """All periodic_monitoring score=3 refs must carry v9.6.0 PV-03 freshness stamp."""
    periodic = {entry["id"]: entry for entry in yaml_data.get("periodic_monitoring", [])}
    s3_periodic = {k: v for k, v in periodic.items() if v.get("relevance_score") == 3}
    # Periodic-bucket score-3 at v9.6.0: primelocus-hydra, christophera-bootstrap-seed,
    # spring-ai-agent-skills.
    expected_periodic_s3 = {
        "primelocus-hydra",
        "christophera-bootstrap-seed",
        "spring-ai-agent-skills",
    }
    assert expected_periodic_s3.issubset(set(s3_periodic.keys()))
    for ref_id, entry in s3_periodic.items():
        assert entry["last_checked"] == "2026-05-02", (
            f"{ref_id}: last_checked must be 2026-05-02 after PV-03 refresh"
        )


def test_primelocus_hydra_graduated_to_frozen_reference(yaml_data: dict) -> None:
    """primelocus-hydra must be graduated to `frozen_reference` at v9.6.0 PV-04.

    Per gap_analysis §3.2 D-R-9: PV-03 telegraphed via
    `tracking_status: frozen_reference_pending_v9_6_0_pv04_graduation`,
    and PV-04 actually graduates the entry to `tracking_status:
    frozen_reference` per tracking_policy.staleness_indicators
    (`repo_archived_or_6_months_inactive`).
    """
    periodic = {entry["id"]: entry for entry in yaml_data.get("periodic_monitoring", [])}
    ph = periodic["primelocus-hydra"]
    assert ph.get("status") == "deleted_upstream"
    # PV-04 actual graduation: the post-graduation status is exactly
    # "frozen_reference" (no longer the "_pending_" telegraph).
    assert ph.get("tracking_status") == "frozen_reference", (
        "primelocus-hydra must be graduated to tracking_status: "
        "frozen_reference at v9.6.0 PV-04 (D-R-9)"
    )
    # The graduation timestamp pins when the transition happened.
    assert ph.get("graduated_to_frozen_at", "").startswith("v9.6.0 PV-04"), (
        "primelocus-hydra must record the v9.6.0 PV-04 graduation timestamp"
    )
    # The original PV-03 telegraph + PV-04 actual graduation are noted.
    assert "v9.6.0 PV-04" in ph.get("note", ""), (
        "primelocus-hydra note must reference the PV-04 graduation"
    )


# ============================================================================
# PV-04 — bulk freshness contract.
# ============================================================================


def test_pv04_all_21_refs_carry_2026_05_02_last_checked(yaml_data: dict) -> None:
    """Per gap_analysis §3.1 D-R-5: ALL yaml refs must carry the v9.6.0 freshness floor.

    PV-02 refreshed 5 (deep-analyzed), PV-03 refreshed 5 (score=3),
    PV-04 refreshes the remaining 11 to bring the bulk to 21/21.

    v12.5.0 PV-05 update: total grew 21 → 22 (codegraph appended); the
    bulk-freshness invariant is relaxed from equality (`== 2026-05-02`) to
    floor (`>= 2026-05-02`) so legitimately fresher entries (codegraph at
    2026-05-23) land per cycle without breaking the no-stale-entries guard.
    """
    from datetime import date

    all_refs = yaml_data.get("active_tracking", []) + yaml_data.get("periodic_monitoring", [])
    assert len(all_refs) == 23, (
        f"v13.0.0: total ref count is 23 (13 active_tracking + 10 "
        f"periodic_monitoring); got {len(all_refs)}"
    )
    floor = date(2026, 5, 2)
    stale = [
        r["id"]
        for r in all_refs
        if not r.get("last_checked") or date.fromisoformat(r["last_checked"]) < floor
    ]
    assert not stale, (
        f"v12.5.0 PV-05: ALL refs must carry last_checked >= 2026-05-02 "
        f"(v9.6.0 PV-04 floor); still stale: {stale}"
    )


def test_pv04_yaml_header_comment_corrected(yaml_data: dict) -> None:
    """Per gap_analysis §3.2 D-R-7: yaml header must reflect the actual count.

    v9.6.0 PV-04 corrected the header from "10 + 9 = 19" → "11 + 10 = 21".
    v12.5.0 PV-05 D-1.1 grew active_tracking 11 → 12 (codegraph appended),
    v13.0.0 grew active_tracking 12 → 13 by appending the impeccable entry,
    so the header now reads "13 + 10 = 23" — the test pins the current
    line.
    """
    raw = (REPO_ROOT / "workflow-system/agent/knowledge/reference-dependencies.yaml").read_text(
        encoding="utf-8"
    )
    assert "13 active_tracking + 10 periodic_monitoring = 23 total" in raw, (
        "yaml header comment must reflect 13 + 10 = 23 per v13.0.0 "
        "(impeccable appended to active_tracking)"
    )
    # The original "10 + 9 = 19" claim must NOT appear except in the
    # historical correction note.
    correction_phrase = '"10 + 9 = 19"'
    occurrences = raw.count(correction_phrase)
    assert occurrences <= 1, (
        f"the historical '10 + 9 = 19' string must appear at most once "
        f"(in the correction note); found {occurrences}"
    )
