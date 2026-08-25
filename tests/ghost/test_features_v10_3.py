"""Ghost audit — per-cycle W-18 feature stanzas for the v10.3 cycle.

Split from ``tests/test_no_ghost_features.py`` per v15-ADR-001
(v14.3.0). New W-18 stanzas for a v10.3.x release append HERE; the
next MINOR cycle rotates to a fresh ``test_features_v<MAJ>_<MIN>.py``.
"""

from __future__ import annotations

from pathlib import Path

from tests.ghost._helpers import _w18_research_artifact_path

# =====================================================================
# v10.3.0 PV-06 cycle-close W-18 ghost-audit refresh
# =====================================================================
#
# v10.3.0 is the MINOR cycle close of the v10.2.0 cycle (5 PATCH PVs +
# this MINOR cycle-close PV). PV-06 ships:
# 1. Canonical 7 sync locations bumped 10.2.4 → 10.3.0
# 2. versions.json v10.3.0 entry (63rd)
# 3. tracked cycle-archive README for v10.3.0
# 4. .local/research/v10.3.0_evaluation.md (W-3 SI-3 STRICT MINOR-cycle-close)
# 5. .local/research/v10.3.0_retrospective.md (W-7 SI-8; 4 mandatory sections)
# 6. .local/research/v10.3.0_nines.{json,md} (W-2 SI-2 cycle-close self-eval)
# 7. docs/cycle-archive/v10.3.0/ (W-19 cycle archive; ≥10 files)
# 8. CHANGELOG ## [10.3.0] header

# v10.3.0 PV-06 versions.json entry must contain the v10.3.0 version field.
# (Schema-checked via tests/test_doc_consistency.py; here we pin presence.)
_V10_3_0_VERSIONS_JSON_LITERAL: str = '"version": "10.3.0"'


# v10.3.0 PV-06 research artifacts (gitignored; path-presence is the
# operator-visible contract).
_V10_3_0_EVALUATION_DOC: Path = Path(".local/research/v10.3.0_evaluation.md")


_V10_3_0_RETROSPECTIVE_DOC: Path = Path(".local/research/v10.3.0_retrospective.md")


_V10_3_0_NINES_JSON: Path = Path(".local/research/v10.3.0_nines.json")


_V10_3_0_NINES_MD: Path = Path(".local/research/v10.3.0_nines.md")


# v10.3.0 PV-06 W-19 cycle archive directory (committed; presence-checked).
_V10_3_0_CYCLE_ARCHIVE_DIR: Path = Path("docs/cycle-archive/v10.3.0")


_V10_3_0_CYCLE_ARCHIVE_README: Path = _V10_3_0_CYCLE_ARCHIVE_DIR / "README.md"


# v10.3.0 PV-06 CHANGELOG header literal.
_V10_3_0_CHANGELOG_LITERAL: str = "## [10.3.0]"


# v10.3.0 W-3 SI-3 composite literal — the CHANGELOG entry must cite the
# composite to document the STRICT MINOR-cycle-close gate verdict.
_V10_3_0_CHANGELOG_SI3_LITERAL: str = "9.385"


def test_v10_3_0_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v10.3.0: every NEW v10.3.0 PV-06 surface has presence coverage.

    Discharges the W-18 precondition for the v10.3.0 PV-06 MINOR cycle
    close. The CHANGELOG entry mentions:

    * the v10.2.0 cycle's 6-PV ledger (PV-01 → PV-06);
    * canonical 7 sync to 10.3.0;
    * append-only versions.json history + tracked cycle-archive README;
    * .local/research/v10.3.0_{nines,evaluation,retrospective}.{json,md};
    * docs/cycle-archive/v10.3.0/ via the W-19 archive harness;
    * the W-3 SI-3 composite 9.385/10 verdict.

    Each needs a presence assertion here BEFORE the CHANGELOG mention is
    valid — per W-18 refresh-before-document sequencing.

    v10.3.0 PV-06 durable pins:

    1. versions.json contains a `"version": "10.3.0"` entry.
    2. `docs/cycle-archive/v10.3.0/README.md` identifies the v10.3.0 archive.
       Current Home and Harness pages do not carry retired release-specific
       cards or historical SAMPLE_DATA assumptions.
    3. `.local/research/v10.3.0_evaluation.md` exists (W-3 SI-3).
    4. `.local/research/v10.3.0_retrospective.md` exists (W-7 SI-8).
    5. `.local/research/v10.3.0_nines.json` exists (W-2 SI-2 raw).
    6. `.local/research/v10.3.0_nines.md` exists (W-2 SI-2 synthesis).
    7. `docs/cycle-archive/v10.3.0/` directory exists with ≥ 10 files
       (W-19 archive).
    8. CHANGELOG `## [10.3.0]` header is present AND cites the W-3
        SI-3 composite literal "9.385" so the STRICT MINOR-cycle-close
        gate verdict is discoverable to future cycle authors.
    """
    versions_json_path = (
        project_root / "workflow-system" / "human" / "demo" / "version-timeline" / "versions.json"
    )
    versions_json_text = versions_json_path.read_text(encoding="utf-8")
    assert _V10_3_0_VERSIONS_JSON_LITERAL in versions_json_text, (
        f"W-18 v10.3.0 violation: versions.json missing entry containing "
        f"{_V10_3_0_VERSIONS_JSON_LITERAL!r}; ST-7 requires a v10.3.0 "
        f"entry. Add the entry OR remove the CHANGELOG mention."
    )

    archive_readme = project_root / _V10_3_0_CYCLE_ARCHIVE_README
    assert archive_readme.is_file(), (
        f"W-18 v10.3.0 violation: tracked archive README missing at "
        f"{_V10_3_0_CYCLE_ARCHIVE_README}."
    )
    assert "# Cycle Archive — v10.3.0" in archive_readme.read_text(encoding="utf-8"), (
        "W-18 v10.3.0 violation: tracked archive README lost its v10.3.0 identity marker."
    )

    _w18_research_artifact_path(project_root, _V10_3_0_EVALUATION_DOC)

    _w18_research_artifact_path(project_root, _V10_3_0_RETROSPECTIVE_DOC)

    _w18_research_artifact_path(project_root, _V10_3_0_NINES_JSON)

    _w18_research_artifact_path(project_root, _V10_3_0_NINES_MD)

    archive_dir = project_root / _V10_3_0_CYCLE_ARCHIVE_DIR
    assert archive_dir.is_dir(), (
        f"W-18 v10.3.0 violation: W-19 cycle archive directory missing "
        f"at {_V10_3_0_CYCLE_ARCHIVE_DIR}. v10.3.0 PV-06 runs "
        f"`python scripts/archive_research_artifacts.py 10.3.0 "
        f"--extra-prefix v10.2.` to populate it. Re-run the harness."
    )
    archive_files = list(archive_dir.rglob("*"))
    archive_file_count = sum(1 for f in archive_files if f.is_file())
    assert archive_file_count >= 10, (
        f"W-18 v10.3.0 violation: W-19 cycle archive at "
        f"{_V10_3_0_CYCLE_ARCHIVE_DIR} contains only {archive_file_count} "
        f"file(s); the cycle archive should hold ≥ 10 files (per the "
        f"v10.0.0 archive precedent at docs/cycle-archive/v10.0.0/ which "
        f"holds 51 files). Re-run the W-19 harness with "
        f"`--extra-prefix v10.2.` to capture all PATCH-PV research."
    )

    changelog_path = project_root / "CHANGELOG.md"
    changelog_text = changelog_path.read_text(encoding="utf-8")
    assert _V10_3_0_CHANGELOG_LITERAL in changelog_text, (
        f"W-18 v10.3.0 violation: CHANGELOG entry "
        f"{_V10_3_0_CHANGELOG_LITERAL!r} missing; PV-06 ships this entry."
    )
    assert _V10_3_0_CHANGELOG_SI3_LITERAL in changelog_text, (
        f"W-18 v10.3.0 violation: CHANGELOG `## [10.3.0]` entry must "
        f"cite the W-3 SI-3 composite literal "
        f"{_V10_3_0_CHANGELOG_SI3_LITERAL!r} (the cycle's STRICT "
        f"MINOR-cycle-close gate verdict). Without the literal the "
        f"composite is not discoverable to future cycle authors. Update "
        f"CHANGELOG to cite the composite."
    )
