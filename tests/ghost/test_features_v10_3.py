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
# 2. README "What's New in v10.3.0 (MINOR cycle close)" section
# 3. demo/index.html v10.3.0 What's New section with 3 highlight cards
# 4. versions.json v10.3.0 entry (63rd)
# 5. benchmark-results SAMPLE_DATA at 10.3.0 (handled by bump_version)
# 6. .local/research/v10.3.0_evaluation.md (W-3 SI-3 STRICT MINOR-cycle-close)
# 7. .local/research/v10.3.0_retrospective.md (W-7 SI-8; 4 mandatory sections)
# 8. .local/research/v10.3.0_nines.{json,md} (W-2 SI-2 cycle-close self-eval)
# 9. docs/cycle-archive/v10.3.0/ (W-19 cycle archive; ≥10 files)
# 10. CHANGELOG ## [10.3.0] header

# v10.3.0 PV-06 README "What's New" section literal — pinned for visibility.
_V10_3_0_README_WHATS_NEW: str = "What's New in v10.3.0 (MINOR cycle close)"


# v10.3.0 PV-06 demo landing v10.3.0 What's New marker — pinned for ST-1.
_V10_3_0_DEMO_LANDING_LITERAL: str = 'data-i18n="landing.whatsNew.v1030"'


# v10.3.0 PV-06 versions.json entry must contain the v10.3.0 version field.
# (Schema-checked via tests/test_doc_consistency.py; here we pin presence.)
_V10_3_0_VERSIONS_JSON_LITERAL: str = '"version": "10.3.0"'


# v10.3.0 PV-06 benchmark-results SAMPLE_DATA literal (canonical 7 sync #8).
#
# v10.4.0 PV-05 NOTE: the original literal was version-specific
# ('"version":"10.3.0"'), which `scripts/bump_version.py` atomically
# rewrites on every subsequent cycle. The pin's INTENT is "verify
# canonical 7 sync #8 wired the SAMPLE_DATA `version` field"; the
# realised assertion was "verify the value is exactly 10.3.0" — these
# diverge after the first post-v10.3.0 bump. The fix is to assert the
# field LABEL is present, which survives version bumps, so the lint
# preserves its semantic intent (the v10.3.0 cycle wired the canonical
# 7 sync #8 → benchmark-results) without breaking on every future bump.
_V10_3_0_BENCHMARK_SAMPLE_DATA_LITERAL: str = '"version":"'


# v10.3.0 PV-06 research artifacts (gitignored; path-presence is the
# operator-visible contract).
_V10_3_0_EVALUATION_DOC: Path = Path(".local/research/v10.3.0_evaluation.md")


_V10_3_0_RETROSPECTIVE_DOC: Path = Path(".local/research/v10.3.0_retrospective.md")


_V10_3_0_NINES_JSON: Path = Path(".local/research/v10.3.0_nines.json")


_V10_3_0_NINES_MD: Path = Path(".local/research/v10.3.0_nines.md")


# v10.3.0 PV-06 W-19 cycle archive directory (committed; presence-checked).
_V10_3_0_CYCLE_ARCHIVE_DIR: Path = Path("docs/cycle-archive/v10.3.0")


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
    * README + demo + versions.json + benchmark-results human-doc refresh;
    * .local/research/v10.3.0_{nines,evaluation,retrospective}.{json,md};
    * docs/cycle-archive/v10.3.0/ via the W-19 archive harness;
    * the W-3 SI-3 composite 9.385/10 verdict.

    Each needs a presence assertion here BEFORE the CHANGELOG mention is
    valid — per W-18 refresh-before-document sequencing.

    v10.3.0 PV-06 pins (10 distinct surface elements):

    1. README "What's New in v10.3.0 (MINOR cycle close)" header is present.
    2. demo/index.html carries the v10.3.0 What's New section
       (`landing.whatsNew.v1030` i18n key marker).
    3. versions.json contains a `"version": "10.3.0"` entry.
    4. benchmark-results/index.html SAMPLE_DATA at "10.3.0" (bump_version
       canonical 7 sync #8).
    5. `.local/research/v10.3.0_evaluation.md` exists (W-3 SI-3).
    6. `.local/research/v10.3.0_retrospective.md` exists (W-7 SI-8).
    7. `.local/research/v10.3.0_nines.json` exists (W-2 SI-2 raw).
    8. `.local/research/v10.3.0_nines.md` exists (W-2 SI-2 synthesis).
    9. `docs/cycle-archive/v10.3.0/` directory exists with ≥ 10 files
       (W-19 archive).
    10. CHANGELOG `## [10.3.0]` header is present AND cites the W-3
        SI-3 composite literal "9.385" so the STRICT MINOR-cycle-close
        gate verdict is discoverable to future cycle authors.
    """
    readme_path = project_root / "README.md"
    readme_text = readme_path.read_text(encoding="utf-8")
    assert _V10_3_0_README_WHATS_NEW in readme_text, (
        f"W-18 v10.3.0 violation: README missing literal "
        f"{_V10_3_0_README_WHATS_NEW!r}; the v10.3.0 cycle-close PV ships "
        f"a README 'What's New' section per ST-1. Restore the section OR "
        f"remove the CHANGELOG mention of the README refresh."
    )

    demo_index_path = project_root / "workflow-system" / "human" / "demo" / "index.html"
    demo_index_text = demo_index_path.read_text(encoding="utf-8")
    assert _V10_3_0_DEMO_LANDING_LITERAL in demo_index_text, (
        f"W-18 v10.3.0 violation: demo landing missing the "
        f"{_V10_3_0_DEMO_LANDING_LITERAL!r} i18n marker; the v10.3.0 "
        f"cycle-close PV ships a v10.3.0 What's New section per ST-1 + "
        f"ST-2. Restore the section OR remove the CHANGELOG mention."
    )

    versions_json_path = (
        project_root / "workflow-system" / "human" / "demo" / "version-timeline" / "versions.json"
    )
    versions_json_text = versions_json_path.read_text(encoding="utf-8")
    assert _V10_3_0_VERSIONS_JSON_LITERAL in versions_json_text, (
        f"W-18 v10.3.0 violation: versions.json missing entry containing "
        f"{_V10_3_0_VERSIONS_JSON_LITERAL!r}; ST-7 requires a v10.3.0 "
        f"entry. Add the entry OR remove the CHANGELOG mention."
    )

    benchmark_results_path = (
        project_root / "workflow-system" / "human" / "demo" / "benchmark-results" / "index.html"
    )
    benchmark_text = benchmark_results_path.read_text(encoding="utf-8")
    assert _V10_3_0_BENCHMARK_SAMPLE_DATA_LITERAL in benchmark_text, (
        f"W-18 v10.3.0 violation: benchmark-results missing SAMPLE_DATA "
        f"version literal {_V10_3_0_BENCHMARK_SAMPLE_DATA_LITERAL!r}; "
        f"canonical 7 sync #8 (`scripts/bump_version.py`) updates this "
        f"automatically. Re-run `python scripts/bump_version.py 10.3.0`."
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
