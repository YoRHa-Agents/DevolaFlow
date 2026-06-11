"""Ghost audit — per-cycle W-18 feature stanzas for the v10.7 cycle.

Split from ``tests/test_no_ghost_features.py`` per v15-ADR-001
(v14.3.0). New W-18 stanzas for a v10.7.x release append HERE; the
next MINOR cycle rotates to a fresh ``test_features_v<MAJ>_<MIN>.py``.
"""

from __future__ import annotations

from pathlib import Path

from tests.ghost._helpers import _w18_research_artifact_path

# =====================================================================
# v10.7.0 PV-01..PV-05 — Protocol Audit + Observability
# =====================================================================
#
# v10.7.0 collapses 5 v11.0.0-cycle PDSs (D-P-1, D-P-3, D-O-1, D-O-2,
# D-O-3) into a single coherent MINOR cycle per
# `.local/research/v11.0.0_patches/`. The cycle ships:
#  1. D-P-1 — `scripts/audit_canonical_order_emptiness.py` audit-only
#     script + tests + first audit output. Reports per-position non-
#     empty rate across the 17-element canonical_order; G-6 frozen-
#     prefix gate preserved (positions 1-12 informational only).
#  2. D-P-3 — STATUS.yaml NEST extensibility demo: NEW OPTIONAL
#     `last_handoff_summary` dict field at top-level (NEST: groups
#     four sub-attributes in ONE dict-shaped key vs APPEND × 4 sibling
#     scalars). Schema_version stays at 1 (additive only).
#  3. D-O-1 — `references/evaluator-rosetta.md` 16th SF-4 canonical
#     reference (~505 lines, Large tier <1000) + companion
#     `scripts/generate_evaluator_rosetta.py` + tests + first audit.
#  4. D-O-2 — `scripts/auto_collect_si3_metrics.py` 6-dim objective
#     metric auto-collector + tests + first run output. 0% → 87% sub-
#     component auto-fill (mock-data preview).
#  5. D-O-3 — `scripts/index_mid_cycle_research.py` mid-cycle research
#     artifact navigator + tests + first index output. Workspace-local
#     ephemeral; complementary to the W-19 cycle-end committed archive.
#  6. CHANGELOG `## [10.7.0]` entry; canonical 7 sync 10.6.0 -> 10.7.0
#  7. .local/research/v10.7.0_retrospective.md (W-7 / SI-8)

# 4 NEW scripts authored by v10.7.0.
_V10_7_0_AUDIT_CANONICAL_SCRIPT: Path = Path("scripts/audit_canonical_order_emptiness.py")


_V10_7_0_GEN_ROSETTA_SCRIPT: Path = Path("scripts/generate_evaluator_rosetta.py")


_V10_7_0_AUTO_SI3_SCRIPT: Path = Path("scripts/auto_collect_si3_metrics.py")


_V10_7_0_INDEX_RESEARCH_SCRIPT: Path = Path("scripts/index_mid_cycle_research.py")


# 4 matching test files.
_V10_7_0_AUDIT_CANONICAL_TESTS: Path = Path("tests/test_audit_canonical_order_emptiness.py")


_V10_7_0_GEN_ROSETTA_TESTS: Path = Path("tests/test_generate_evaluator_rosetta.py")


_V10_7_0_AUTO_SI3_TESTS: Path = Path("tests/test_auto_collect_si3_metrics.py")


_V10_7_0_INDEX_RESEARCH_TESTS: Path = Path("tests/test_index_mid_cycle_research.py")


# 16th SF-4 reference + the agent_workspace.md NEST doc literal.
_V10_7_0_EVALUATOR_ROSETTA_REF: Path = Path("workflow-system/agent/references/evaluator-rosetta.md")


_V10_7_0_AGENT_WORKSPACE_NEST_LITERAL: str = "v10.7.0 D-P-3"


# 4 audit / index / collector first-run outputs (W-18 PRECONDITION
# pin per cycle plan).
_V10_7_0_AUDIT_DOCS: tuple[Path, ...] = (
    Path(".local/research/v10.7.1_canonical_order_emptiness.md"),
    Path(".local/research/v10.7.2_evaluator_rosetta.md"),
    Path(".local/research/v10.7.3_si3_auto_collection.md"),
    Path(".local/research/v10.7.4_research_index.md"),
)


_V10_7_0_RETROSPECTIVE_DOC: Path = Path(".local/research/v10.7.0_retrospective.md")


_V10_7_0_CHANGELOG_LITERAL: str = "## [10.7.0]"


# 4 Makefile target literals.
_V10_7_0_MAKEFILE_TARGETS: tuple[str, ...] = (
    "audit-canonical-emptiness:",
    "gen-evaluator-rosetta:",
    "auto-collect-si3:",
    "index-research:",
)


# D-P-3 STATUS.yaml schema field name (the NEST demo).
_V10_7_0_STATUS_NEST_FIELD: str = "last_handoff_summary"


def test_v10_7_0_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v10.7.0: every NEW v10.7.0 PV-01..PV-05 surface has presence coverage.

    Discharges the W-18 precondition for the v10.7.0 MINOR cycle. The
    CHANGELOG entry mentions:

    * 4 NEW audit / observability scripts (D-P-1, D-O-1 companion,
      D-O-2, D-O-3) + matching test files.
    * NEW `workflow-system/agent/references/evaluator-rosetta.md` (16th
      SF-4 canonical reference; ~505 lines, Large tier).
    * NEW OPTIONAL `last_handoff_summary` field on
      `schemas/agent-workspace/change-status.yaml` (D-P-3 NEST demo)
      + matching `Change.last_handoff_summary` accessor.
    * 4 audit / index / collector first-run outputs in
      `.local/research/v10.7.{1,2,3,4}_*.md`.
    * 4 NEW Makefile targets (audit-canonical-emptiness,
      gen-evaluator-rosetta, auto-collect-si3, index-research).
    * Canonical 7 sync 10.6.0 -> 10.7.0 + CHANGELOG `## [10.7.0]`.

    Each pin protects the W-18 sequencing per
    `.local/research/v9.0.0_pv05_design.md` §3 + ADR-005 D2.
    """
    # 4 NEW scripts.
    for script in (
        _V10_7_0_AUDIT_CANONICAL_SCRIPT,
        _V10_7_0_GEN_ROSETTA_SCRIPT,
        _V10_7_0_AUTO_SI3_SCRIPT,
        _V10_7_0_INDEX_RESEARCH_SCRIPT,
    ):
        assert (project_root / script).is_file(), (
            f"W-18 v10.7.0 violation: NEW audit/collector script missing at "
            f"{script}. v10.7.0 ships this script as part of the D-P / D-O "
            f"slice. Author the script OR remove the CHANGELOG mention."
        )

    # 4 matching test files.
    for test_file in (
        _V10_7_0_AUDIT_CANONICAL_TESTS,
        _V10_7_0_GEN_ROSETTA_TESTS,
        _V10_7_0_AUTO_SI3_TESTS,
        _V10_7_0_INDEX_RESEARCH_TESTS,
    ):
        assert (project_root / test_file).is_file(), (
            f"W-18 v10.7.0 violation: NEW test file missing at {test_file}. "
            f"v10.7.0 ships unit tests for every new audit/collector script."
        )

    # 16th SF-4 canonical reference.
    rosetta_ref = project_root / _V10_7_0_EVALUATOR_ROSETTA_REF
    assert rosetta_ref.is_file(), (
        f"W-18 v10.7.0 violation: NEW SF-4 canonical reference missing at "
        f"{_V10_7_0_EVALUATOR_ROSETTA_REF}. v10.7.0 D-O-1 ships the "
        f"three-evaluator rosetta as the 16th canonical reference."
    )
    rosetta_text = rosetta_ref.read_text(encoding="utf-8")
    assert "6 × 9" in rosetta_text or "6 \\times 9" in rosetta_text or "6×9" in rosetta_text, (
        "W-18 v10.7.0 violation: evaluator-rosetta.md must contain the "
        "'6 × 9' (or 6×9) cell-table identifier per D-O-1 §2.3."
    )

    # D-P-3 NEST field present in change-status.yaml schema + Change accessor.
    schema_path = project_root / "schemas" / "agent-workspace" / "change-status.yaml"
    schema_text = schema_path.read_text(encoding="utf-8")
    assert _V10_7_0_STATUS_NEST_FIELD in schema_text, (
        f"W-18 v10.7.0 violation: STATUS.yaml schema missing NEW field "
        f"`{_V10_7_0_STATUS_NEST_FIELD}` (D-P-3 NEST demo)."
    )
    change_text = (project_root / "src/devolaflow/agent_workspace/change.py").read_text(
        encoding="utf-8"
    )
    assert "def last_handoff_summary" in change_text, (
        "W-18 v10.7.0 violation: Change dataclass missing "
        "`last_handoff_summary` property accessor (D-P-3)."
    )

    # agent-workspace.md reference doc must mention the D-P-3 demo.
    agent_workspace_text = (
        project_root / "workflow-system/agent/references/agent-workspace.md"
    ).read_text(encoding="utf-8")
    assert _V10_7_0_AGENT_WORKSPACE_NEST_LITERAL in agent_workspace_text, (
        f"W-18 v10.7.0 violation: agent-workspace.md must cite the "
        f"{_V10_7_0_AGENT_WORKSPACE_NEST_LITERAL!r} D-P-3 NEST demo "
        f"in the STATUS.yaml schema section."
    )

    # 4 Makefile targets present (literals exact-match).
    makefile_text = (project_root / "Makefile").read_text(encoding="utf-8")
    for target in _V10_7_0_MAKEFILE_TARGETS:
        assert target in makefile_text, (
            f"W-18 v10.7.0 violation: Makefile missing literal {target!r} "
            f"(D-P-1 / D-O-1 / D-O-2 / D-O-3 audit targets)."
        )

    # 4 audit / index / collector first-run outputs.
    for audit_doc in _V10_7_0_AUDIT_DOCS:
        _w18_research_artifact_path(project_root, audit_doc)

    # Retrospective + CHANGELOG.
    _w18_research_artifact_path(project_root, _V10_7_0_RETROSPECTIVE_DOC)

    changelog = (project_root / "CHANGELOG.md").read_text(encoding="utf-8")
    assert _V10_7_0_CHANGELOG_LITERAL in changelog, (
        f"W-18 v10.7.0 violation: CHANGELOG entry "
        f"{_V10_7_0_CHANGELOG_LITERAL!r} missing; v10.7.0 ships this entry."
    )
