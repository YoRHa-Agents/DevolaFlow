"""Ghost audit — per-cycle W-18 feature stanzas for the v10.0 cycle.

Split from ``tests/test_no_ghost_features.py`` per v15-ADR-001
(v14.3.0). New W-18 stanzas for a v10.0.x release append HERE; the
next MINOR cycle rotates to a fresh ``test_features_v<MAJ>_<MIN>.py``.
"""

from __future__ import annotations

import ast
from pathlib import Path

# ---------------------------------------------------------------------------
# W-18 v10.0.0 ghost-audit refresh — MAJOR rollup cycle close.
# ---------------------------------------------------------------------------


# v10.0.0 NEW symbol: the feedback-AC audit script's public surface.
# Every other "new" surface in v10.0.0 comes from a v9.X MINOR that already
# has its own W-18 lint above; the MAJOR rollup itself adds only the audit
# script + the W-19 archive output + the human-docs refresh (none of which
# expose Python symbols).
_V10_0_0_AUDIT_SCRIPT_PATH: Path = Path("scripts/audit_feedback_ac.py")


_V10_0_0_AUDIT_SCRIPT_PUBLIC_SYMBOLS: tuple[str, ...] = (
    "FeedbackAudit",
    "audit_feedback",
    "_extract_artifacts",
    "_count_ac_items",
    "_classify",
    "_check_path",
    "_grep_symbol",
    "_later_changelog_entries",
    "_format_markdown_report",
    "main",
)


# v10.0.0 PV-03 historical human-doc surfaces. Timeline is append-only, and
# the tracked cycle-archive README preserves the release contract without
# requiring a retired release card on the current Home page.
_V10_0_0_HUMAN_DOC_LITERALS: tuple[tuple[str, str], ...] = (
    ("workflow-system/human/demo/version-timeline/versions.json", '"version": "10.0.0"'),
    ("docs/cycle-archive/v10.0.0/README.md", "# Cycle Archive — v10.0.0"),
)


# v10.0.0 PV-04 W-19 cycle archive surfaces.
_V10_0_0_CYCLE_ARCHIVE_REQUIRED_FILES: tuple[Path, ...] = (
    Path("docs/cycle-archive/v10.0.0/README.md"),
    Path("docs/cycle-archive/v10.0.0/v10.0.0_retrospective.md"),
    Path("docs/cycle-archive/v10.0.0/v9.3.0_retrospective.md"),
    Path("docs/cycle-archive/v10.0.0/v9.7.0_retrospective.md"),
    Path("docs/cycle-archive/v10.0.0/evaluation/v10.0.0_evaluation.md"),
    Path("docs/cycle-archive/v10.0.0/nines/v10.0.0_nines.json"),
    Path("docs/cycle-archive/v10.0.0/nines/v10.0.0_nines.md"),
    Path("docs/cycle-archive/v10.0.0/other/v10.0.0_cycle_plan.md"),
    Path("docs/cycle-archive/v10.0.0/other/v10.0.0_feedback_ac_audit.md"),
)


def test_v10_0_0_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v10.0.0: every NEW v10.0.0 surface has presence + structural coverage.

    Discharges the W-18 precondition for the v10.0.0 cycle-close MAJOR —
    every CHANGELOG entry mentioning a v10.0.0 feature MUST have a backing
    ghost-audit lint in THIS file BEFORE the CHANGELOG entry is authored.

    v10.0.0 PV-05 cycle close pins:

    1. **PV-02 audit script public surface** — `scripts/audit_feedback_ac.py`
       exists AND every named public symbol is present at module level. The
       MAJOR rollup CHANGELOG entry cites the audit's "57 files / 0 FAILs"
       headline number; missing script = unprovable claim.
    2. **PV-03 historical-doc contract** — the append-only `versions.json`
       v10.0.0 entry and tracked cycle-archive README remain present. Current
       Home and Harness pages do not carry retired release-specific cards.
    3. **PV-04 W-19 cycle archive surface** — the
       `docs/cycle-archive/v10.0.0/` tree exists with the README + the
       v10.0.0 retrospective + the v9.3 / v9.7 retrospectives (sample of
       the per-MINOR coverage) + the v10.0.0 evaluation + the v10.0.0 nines
       JSON+MD + the cycle plan + the feedback audit. These are the W-19
       surfaces the CHANGELOG cites.

    Failure modes:
      * "audit script missing public symbol" → PV-02 surface decayed; restore
        the symbol OR remove the CHANGELOG mention.
      * "historical-doc literal missing" → Timeline or tracked archive
        evidence decayed; restore the durable historical contract.
      * "cycle archive file missing" → PV-04 W-19 archive run failed; re-run
        `python scripts/archive_research_artifacts.py 10.0.0 --extra-prefix
        v9.3. --extra-prefix v9.4. --extra-prefix v9.5. --extra-prefix v9.6.
        --extra-prefix v9.7. --extra-prefix v10.0.`
    """

    # §1 — Audit script symbol surface.
    audit_path = project_root / _V10_0_0_AUDIT_SCRIPT_PATH
    assert audit_path.is_file(), (
        f"W-18 v10.0.0 violation: audit script {_V10_0_0_AUDIT_SCRIPT_PATH} "
        f"missing. PV-02 ships this script; either restore it OR remove "
        f"the CHANGELOG mention of the 57-feedback audit."
    )
    audit_source = audit_path.read_text(encoding="utf-8")
    audit_module = ast.parse(audit_source)
    defined_names = {
        node.name
        for node in ast.walk(audit_module)
        if isinstance(node, ast.FunctionDef | ast.ClassDef)
    }
    for sym in _V10_0_0_AUDIT_SCRIPT_PUBLIC_SYMBOLS:
        assert sym in defined_names, (
            f"W-18 v10.0.0 violation: audit script "
            f"{_V10_0_0_AUDIT_SCRIPT_PATH} missing public symbol {sym!r}. "
            f"PV-02 cites this symbol in tests/test_audit_feedback_ac.py; "
            f"either restore the symbol OR adjust both the CHANGELOG and "
            f"the test."
        )

    # §2 — Human-doc literal contract.
    for rel_path, literal in _V10_0_0_HUMAN_DOC_LITERALS:
        doc_path = project_root / rel_path
        assert doc_path.is_file(), f"W-18 v10.0.0 violation: human-doc {rel_path} missing"
        doc_text = doc_path.read_text(encoding="utf-8")
        assert literal in doc_text, (
            f"W-18 v10.0.0 violation: literal {literal!r} missing from "
            f"{rel_path}. PV-03 history must remain discoverable through "
            f"Timeline and the tracked cycle archive."
        )

    # §3 — W-19 cycle archive surface.
    for archive_rel in _V10_0_0_CYCLE_ARCHIVE_REQUIRED_FILES:
        archive_path = project_root / archive_rel
        assert archive_path.is_file(), (
            f"W-18 v10.0.0 violation: cycle-archive file {archive_rel} "
            f"missing. PV-04 ships this file; re-run "
            f"`python scripts/archive_research_artifacts.py 10.0.0 "
            f"--extra-prefix v9.3. --extra-prefix v9.4. --extra-prefix "
            f"v9.5. --extra-prefix v9.6. --extra-prefix v9.7. "
            f"--extra-prefix v10.0.` to regenerate."
        )
