"""Ghost audit — per-cycle W-18 feature stanzas for the v10.4 cycle.

Split from ``tests/test_no_ghost_features.py`` per v15-ADR-001
(v14.3.0). New W-18 stanzas for a v10.4.x release append HERE; the
next MINOR cycle rotates to a fresh ``test_features_v<MAJ>_<MIN>.py``.
"""

from __future__ import annotations

from pathlib import Path

from tests.ghost._helpers import _w18_research_artifact_path

# =====================================================================
# v10.4.0 PV-05 — Developer Experience + Reference Audit Foundation
# =====================================================================
#
# v10.4.0 collapses 6 PDSs (D-X-1, D-X-2, D-X-3, D-X-5, D-D-1, D-D-2)
# into a single coherent MINOR cycle. PV-05 ships:
#  1. NEW scripts/scaffold_template.py (D-X-1 — workflow template CLI)
#  2. NEW scripts/scaffold_reference.py (D-X-2 — reference doc CLI)
#  3. NEW scripts/audit_reference_utilization.py (D-D-1 — selector audit)
#  4. NEW scripts/audit_long_reference_usage.py (D-D-2 — handoff audit)
#  5. NEW workflow-system/agent/references/troubleshooting.md (D-X-5;
#     15th SF-4 canonical)
#  6. Makefile precommit-fast / precommit-full / precommit (D-X-3
#     SI-10 fast-path)
#  7. CHANGELOG `## [10.4.0]` entry; canonical 7 sync 10.3.0 -> 10.4.0
#  8. .local/research/v10.4.{0,1,2}_*.md retrospective + audit outputs

_V10_4_0_SCAFFOLD_TEMPLATE_SCRIPT: Path = Path("scripts/scaffold_template.py")


_V10_4_0_SCAFFOLD_REFERENCE_SCRIPT: Path = Path("scripts/scaffold_reference.py")


_V10_4_0_AUDIT_UTILIZATION_SCRIPT: Path = Path("scripts/audit_reference_utilization.py")


_V10_4_0_AUDIT_LONG_REF_SCRIPT: Path = Path("scripts/audit_long_reference_usage.py")


_V10_4_0_TROUBLESHOOTING_REF: Path = Path("workflow-system/agent/references/troubleshooting.md")


_V10_4_0_RETROSPECTIVE_DOC: Path = Path(".local/research/v10.4.0_retrospective.md")


_V10_4_0_REF_UTILIZATION_DOC: Path = Path(".local/research/v10.4.1_reference_utilization.md")


_V10_4_0_LONG_REF_USAGE_DOC: Path = Path(".local/research/v10.4.2_long_reference_usage.md")


_V10_4_0_CHANGELOG_LITERAL: str = "## [10.4.0]"


_V10_4_0_MAKEFILE_PRECOMMIT_FAST_LITERAL: str = "precommit-fast:"


_V10_4_0_MAKEFILE_PRECOMMIT_FULL_LITERAL: str = "precommit-full:"


_V10_4_0_MAKEFILE_PRECOMMIT_LITERAL: str = "precommit: precommit-full"


def test_v10_4_0_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v10.4.0: every NEW v10.4.0 PV-05 surface has presence coverage.

    Discharges the W-18 precondition for the v10.4.0 MINOR cycle. The
    CHANGELOG entry mentions:

    * 4 NEW scripts (scaffold_template, scaffold_reference,
      audit_reference_utilization, audit_long_reference_usage);
    * 1 NEW reference (troubleshooting.md, the 15th SF-4 canonical);
    * 3 NEW Makefile targets (precommit-fast, precommit-full,
      precommit);
    * 2 NEW research artifacts (v10.4.1 reference utilization audit
      output + v10.4.2 long-reference usage audit output);
    * canonical 7 sync 10.3.0 -> 10.4.0 + CHANGELOG `## [10.4.0]`.

    Each pin protects the W-18 sequencing per
    `.local/research/v9.0.0_pv05_design.md` §3 + ADR-005 D2.
    """
    for script in (
        _V10_4_0_SCAFFOLD_TEMPLATE_SCRIPT,
        _V10_4_0_SCAFFOLD_REFERENCE_SCRIPT,
        _V10_4_0_AUDIT_UTILIZATION_SCRIPT,
        _V10_4_0_AUDIT_LONG_REF_SCRIPT,
    ):
        path = project_root / script
        assert path.is_file(), (
            f"W-18 v10.4.0 violation: NEW script missing at {script}. "
            f"v10.4.0 PV-05 ships this script as part of the D-X / D-D "
            f"slice. Author the file OR remove the CHANGELOG mention."
        )

    troubleshooting = project_root / _V10_4_0_TROUBLESHOOTING_REF
    assert troubleshooting.is_file(), (
        f"W-18 v10.4.0 violation: 15th SF-4 canonical reference missing "
        f"at {_V10_4_0_TROUBLESHOOTING_REF}. v10.4.0 PV-05 ships D-X-5."
    )

    skill_text = (project_root / "workflow-system/agent/SKILL.md").read_text(encoding="utf-8")
    assert "references/troubleshooting.md" in skill_text, (
        "W-18 v10.4.0 violation: SKILL.md must surface the new reference "
        "in the Reference Navigation Guide table."
    )

    makefile_text = (project_root / "Makefile").read_text(encoding="utf-8")
    for marker in (
        _V10_4_0_MAKEFILE_PRECOMMIT_FAST_LITERAL,
        _V10_4_0_MAKEFILE_PRECOMMIT_FULL_LITERAL,
        _V10_4_0_MAKEFILE_PRECOMMIT_LITERAL,
    ):
        assert marker in makefile_text, (
            f"W-18 v10.4.0 violation: Makefile missing literal {marker!r} "
            f"(D-X-3 SI-10 fast-path). Author the target OR remove the "
            f"CHANGELOG mention."
        )

    _w18_research_artifact_path(project_root, _V10_4_0_RETROSPECTIVE_DOC)

    _w18_research_artifact_path(project_root, _V10_4_0_REF_UTILIZATION_DOC)

    _w18_research_artifact_path(project_root, _V10_4_0_LONG_REF_USAGE_DOC)

    changelog = (project_root / "CHANGELOG.md").read_text(encoding="utf-8")
    assert _V10_4_0_CHANGELOG_LITERAL in changelog, (
        f"W-18 v10.4.0 violation: CHANGELOG entry "
        f"{_V10_4_0_CHANGELOG_LITERAL!r} missing; PV-05 ships this entry."
    )
