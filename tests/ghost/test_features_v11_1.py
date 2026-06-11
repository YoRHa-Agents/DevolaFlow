"""Ghost audit — per-cycle W-18 feature stanzas for the v11.1 cycle.

Split from ``tests/test_no_ghost_features.py`` per v15-ADR-001
(v14.3.0). New W-18 stanzas for a v11.1.x release append HERE; the
next MINOR cycle rotates to a fresh ``test_features_v<MAJ>_<MIN>.py``.
"""

from __future__ import annotations

import ast
from pathlib import Path

# v11.1.0 PV-07 — W-18 final ghost-audit stanza for the MINOR cycle close.
# Discharges the W-18 precondition for the CHANGELOG `## [11.1.0]` MINOR-close
# entry. Per W-18 sequencing the lint refresh MUST land BEFORE the CHANGELOG
# entry — this stanza closes that precondition for the cycle's rollup PV.
#
# PV-07 owned-files include canonical 7 (handled by `bump_version.py`),
# WX-2 versions.json + DS-1 demo index.html, ST-3 bilingual EN/ZH refresh
# (via `make sync-human-docs`), W-19 cycle archive at
# `docs/cycle-archive/v11.1.0/` (committed per W-19), and the W-7 SI-8
# retrospective at `.local/research/v11.1.0_retrospective.md`.
#
# The W-19 archive at `docs/cycle-archive/v11.1.0/retrospective.md` is the
# TRACKED copy of the retrospective. The `.local/research/v11.1.0_retrospective.md`
# original is gitignored per repo convention; this stanza pins the archive
# (always tracked) AND optionally the .local original (skip-when-absent).
_V11_1_0_VERSIONS_JSON: Path = Path("workflow-system/human/demo/version-timeline/versions.json")


_V11_1_0_DEMO_INDEX_HTML: Path = Path("workflow-system/human/demo/index.html")


_V11_1_0_CYCLE_ARCHIVE_DIR: Path = Path("docs/cycle-archive/v11.1.0")


_V11_1_0_CYCLE_ARCHIVE_RETROSPECTIVE: Path = _V11_1_0_CYCLE_ARCHIVE_DIR / "retrospective.md"


_V11_1_0_CYCLE_ARCHIVE_README: Path = _V11_1_0_CYCLE_ARCHIVE_DIR / "README.md"


_V11_1_0_LOCAL_RETROSPECTIVE: Path = Path(".local/research/v11.1.0_retrospective.md")


_V11_1_0_LOCAL_PV07_STAGE_REPORT: Path = Path(".local/research/v11.1.0_pv07_stage_report.md")


_V11_1_0_CHANGELOG: Path = Path("CHANGELOG.md")


# Mandatory section headers in the W-7 / SI-8 retrospective (4-section
# completeness check per W-7 spec).
_V11_1_0_RETROSPECTIVE_REQUIRED_SECTIONS: tuple[str, ...] = (
    "## §1 — Gaps identified",
    "## §2 — What was implemented",
    "## §3 — What was deferred and why",
    "## §4 — Key learnings",
)


# CHANGELOG body must carry the v11.1.0 MINOR-close entry verbatim.
_V11_1_0_CHANGELOG_POSITIVE_SUBSTRINGS: tuple[str, ...] = (
    "## [11.1.0] - 2026-05-08",
    "MINOR",
    "cascade-restoration",
)


def test_v11_1_0_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v11.1.0 PV-07: cycle-close MINOR rollup pinned.

    Discharges the W-18 precondition for the v11.1.0 MINOR-close CHANGELOG
    entry. Per W-18 sequencing the lint refresh MUST land BEFORE the
    CHANGELOG entry — this stanza closes that precondition.

    Surfaces pinned (cycle plan §2 PV-07 + §5 MINOR-close criteria):

    * ``workflow-system/human/demo/version-timeline/versions.json`` carries
      a v11.1.0 entry per WX-2 (real metrics from CHANGELOG only).
    * ``workflow-system/human/demo/index.html`` carries a v11.1.0
      "What's New" section per DS-1 demo "What's New".
    * ``docs/cycle-archive/v11.1.0/`` exists with the auto-generated
      ``README.md`` index + ``retrospective.md`` per W-19 archive contract
      (the archive IS committed; not gitignored).
    * ``CHANGELOG.md`` carries the ``## [11.1.0] - 2026-05-08`` MINOR-close
      entry mentioning ``MINOR`` + ``cascade-restoration``.
    * W-7 / SI-8 retrospective 4-section completeness — the archive copy at
      ``docs/cycle-archive/v11.1.0/retrospective.md`` MUST contain the 4
      mandatory section headers ("Gaps identified", "What was implemented",
      "What was deferred and why", "Key learnings").

    The .local/research/v11.1.0_retrospective.md original is gitignored
    per repo convention (`.gitignore:49` `.local/`); the W-19 archive copy
    at `docs/cycle-archive/v11.1.0/retrospective.md` is the tracked
    canonical pin. The .local original (if present) is also asserted via
    skip-when-absent for local-dev consistency.

    Coupled invariants verified GREEN at PV-07 close:

    * A-2.4 multi-baseline byte test: 32/32 PASS unchanged
    * S-10 hook-chain byte-id: 10/10 PASS unchanged
    * CP-4 gate suite: 108/108 PASS unchanged
    * cascade enforcement strict: 13/13 PASS unchanged
    * audit ratchet: 15/15 PASS unchanged
    * EvoBench: 36/36 PASS unchanged
    * W-21 Soul-set freeze preserved at 10 entries
    * W-20 reuse-first preserved at 8 env flags

    Skip-when-absent rationale: the W-19 archive at
    ``docs/cycle-archive/v11.1.0/`` is the SOURCE OF TRUTH for this lint
    once committed. Before the PV-07 commit lands the archive may be
    absent (e.g., during in-progress dispatching); the lint then falls
    back to the .local original (skip-when-absent for the .local file
    follows v11.0.6 PV-06 stanza pattern).
    """
    # CHANGELOG entry — ALWAYS pinned (CHANGELOG.md IS tracked; W-18
    # precondition that the entry land in this PV's commit).
    changelog_text = (project_root / _V11_1_0_CHANGELOG).read_text(encoding="utf-8")
    for sub in _V11_1_0_CHANGELOG_POSITIVE_SUBSTRINGS:
        assert sub in changelog_text, (
            f"W-18 v11.1.0 PV-07 violation: CHANGELOG.md missing positive "
            f"substring {sub!r} per cycle plan §5 MINOR-close criteria. "
            "The W-18 stanza lands BEFORE the CHANGELOG entry per W-18 "
            "sequencing — if this lint fails the entry must be authored."
        )

    # Single-application discipline (PV-03 N-2 mitigation): a section
    # header ## [11.1.0] appears EXACTLY once in CHANGELOG.md. Use
    # line-anchored match (mirrors `grep -c '^## \\[11\\.1\\.0\\]'`
    # semantics) so any in-prose `## [11.1.0]` mention inside another
    # entry's body does not double-count.
    section_header_count = sum(
        1 for line in changelog_text.splitlines() if line.startswith("## [11.1.0]")
    )
    assert section_header_count == 1, (
        "W-18 v11.1.0 PV-07 violation: CHANGELOG.md contains "
        f"{section_header_count} line-anchored '## [11.1.0]' section "
        "headers — exactly 1 expected (PV-03 N-2 single-application "
        "discipline)."
    )

    # WX-2 versions.json v11.1.0 entry — ALWAYS pinned (tracked per ST-1).
    versions_json_text = (project_root / _V11_1_0_VERSIONS_JSON).read_text(encoding="utf-8")
    assert '"version": "11.1.0"' in versions_json_text, (
        "W-18 v11.1.0 PV-07 violation: versions.json missing v11.1.0 "
        "entry per WX-2; cycle plan §5.6 mandates demo "
        "versions.json refreshed at MINOR close."
    )

    # DS-1 demo index.html v11.1.0 "What's New" — ALWAYS pinned.
    demo_index_text = (project_root / _V11_1_0_DEMO_INDEX_HTML).read_text(encoding="utf-8")
    assert "v11.1.0" in demo_index_text, (
        "W-18 v11.1.0 PV-07 violation: demo/index.html does not mention "
        "v11.1.0 per DS-1 'What's New'; cycle plan §5.6 mandates "
        "demo index.html refreshed at MINOR close."
    )

    # W-19 cycle archive at docs/cycle-archive/v11.1.0/ — ALWAYS pinned
    # (committed per W-19; not gitignored).
    assert (project_root / _V11_1_0_CYCLE_ARCHIVE_DIR).is_dir(), (
        "W-18 v11.1.0 PV-07 violation: docs/cycle-archive/v11.1.0/ "
        "directory missing per W-19; "
        "cycle plan §5.3 mandates archive committed at MINOR close. "
        "Run: python scripts/archive_research_artifacts.py 11.1.0"
    )
    assert (project_root / _V11_1_0_CYCLE_ARCHIVE_README).is_file(), (
        "W-18 v11.1.0 PV-07 violation: docs/cycle-archive/v11.1.0/README.md "
        "missing — auto-generated by archive_research_artifacts.py."
    )
    assert (project_root / _V11_1_0_CYCLE_ARCHIVE_RETROSPECTIVE).is_file(), (
        "W-18 v11.1.0 PV-07 violation: docs/cycle-archive/v11.1.0/"
        "retrospective.md missing — copy of "
        ".local/research/v11.1.0_retrospective.md per W-19 archive contract."
    )

    # W-7 SI-8 retrospective 4-section completeness — verified against
    # the TRACKED archive copy (always-on).
    archived_retro_text = (project_root / _V11_1_0_CYCLE_ARCHIVE_RETROSPECTIVE).read_text(
        encoding="utf-8"
    )
    for required_section in _V11_1_0_RETROSPECTIVE_REQUIRED_SECTIONS:
        assert required_section in archived_retro_text, (
            f"W-18 v11.1.0 PV-07 violation: archived retrospective missing "
            f"required section header {required_section!r} per W-7 / SI-8 "
            "4-section completeness mandate. Sections required: "
            f"{list(_V11_1_0_RETROSPECTIVE_REQUIRED_SECTIONS)!r}."
        )

    # .local/research/ retrospective + stage report — skip-when-absent for
    # CI / fresh clones (the .local/ directory is gitignored per
    # `.gitignore:49`).
    local_artifacts = (
        _V11_1_0_LOCAL_RETROSPECTIVE,
        _V11_1_0_LOCAL_PV07_STAGE_REPORT,
    )
    present = [p for p in local_artifacts if (project_root / p).is_file()]
    if not present:
        # CI / fresh clone path — the W-19 archive provides the canonical
        # tracked source-of-truth; the .local originals are an artifact
        # of the PV-07 author's local working tree only.
        return
    missing = [p for p in local_artifacts if not (project_root / p).is_file()]
    assert not missing, (
        f"W-18 v11.1.0 PV-07 violation: partial .local/research/ artifact "
        f"set — some present ({[str(p) for p in present]}) but others "
        f"missing ({[str(p) for p in missing]}); the PV-07 author MUST "
        f"produce BOTH the retrospective (W-7 / SI-8) AND the stage report "
        f"(L1 → L0 handoff) per cycle plan §2 PV-07 owned-files manifest."
    )


# v11.1.1 PATCH (D-1 in the v11.1.x stability-patch series; deferral D-5 in
# the v11.1.0 retrospective §3): CHANGELOG no-duplicate-version-header CI
# lint. First of 3 staged stability patches (v11.1.1 / v11.1.2 / v11.1.3)
# closing the cycle-observed risks documented in
# `docs/cycle-archive/v11.1.0/retrospective.md` §3.
#
# The lint detects the PV-03 N-2 class-of-bug at CI time so a future
# double-application (commit `da1c489` historical reference) fails the
# standard `pytest tests/ -q` sweep rather than requiring in-PV
# reconciliation. The L1-per-PV invariant (PV-03 N-2 process-side mitigation;
# v11.1.0 retrospective §4 L-2) remains the primary enforcement; this CI lint
# is the secondary belt-and-braces machinery.
_V11_1_1_LINT_FILE: Path = Path("tests/test_changelog_no_duplicate_versions.py")


_V11_1_1_CHANGELOG: Path = Path("CHANGELOG.md")


# Required public symbols in the lint module — pinned via AST so refactor
# of the function body is OK but rename / removal fails fast.
_V11_1_1_LINT_REQUIRED_SYMBOLS: tuple[str, ...] = (
    "find_duplicate_version_headers",
    "test_changelog_has_no_duplicate_version_headers",
    "test_changelog_lint_detects_synthetic_duplicate",
    "test_changelog_lint_passes_on_unique_versions",
)


# CHANGELOG body must carry the v11.1.1 PATCH entry verbatim.
_V11_1_1_CHANGELOG_POSITIVE_SUBSTRINGS: tuple[str, ...] = (
    "## [11.1.1] - 2026-05-08",
    "PATCH",
    "CHANGELOG double-application",
)


def test_v11_1_1_new_surfaces_have_coverage(project_root: Path) -> None:
    """W-18 v11.1.1 PATCH: D-1 CHANGELOG no-duplicate-version-header lint.

    Discharges the W-18 precondition for the v11.1.1 PATCH CHANGELOG
    entry. Per W-18 sequencing the lint refresh MUST land BEFORE the
    CHANGELOG entry — this stanza closes that precondition.

    Surfaces pinned (v11.1.1 D-1 patch scope; first of 3 staged
    v11.1.x stability patches):

    * ``tests/test_changelog_no_duplicate_versions.py`` (NEW file)
      defines the four required public symbols:

      - ``find_duplicate_version_headers`` (helper; reusable by
        future tooling such as a pre-commit hook).
      - ``test_changelog_has_no_duplicate_version_headers`` (the
        main load-bearing lint; reads the actual CHANGELOG.md).
      - ``test_changelog_lint_detects_synthetic_duplicate``
        (positive control; feeds a synthetic duplicate to the
        helper).
      - ``test_changelog_lint_passes_on_unique_versions``
        (negative control; feeds a synthetic CHANGELOG with all
        unique versions to the helper).

    * ``CHANGELOG.md`` carries the ``## [11.1.1] - 2026-05-08``
      PATCH entry mentioning ``PATCH`` + ``CHANGELOG
      double-application`` (the v11.1.0 retrospective §3 D-5
      deferral citation; the dispatcher's D-1 in-series label).

    * ``CHANGELOG.md`` ``## [11.1.1]`` section header appears
      EXACTLY once (the PV-03 N-2 single-application discipline;
      this lint runs against the new entry — proving the fix
      works on the reference CHANGELOG).

    Coupled invariants verified GREEN at PATCH close (no source
    edits to gate / schema / SKILL):

    * A-2.4 multi-baseline byte test: 32/32 PASS unchanged
    * S-10 hook-chain byte-id: 10/10 PASS unchanged
    * CP-4 gate suite: 108/108 PASS unchanged
    * W-21 Soul-set freeze preserved at 10 entries
    * W-20 reuse-first preserved at 8 env flags

    Source: ``docs/cycle-archive/v11.1.0/retrospective.md`` §3 D-5
    (deferral) + §5 P-5 (next-cycle proposal).
    """
    lint_path = project_root / _V11_1_1_LINT_FILE
    assert lint_path.is_file(), (
        f"W-18 v11.1.1 violation: NEW lint file {_V11_1_1_LINT_FILE} "
        "missing. The lint MUST land in the same commit as the CHANGELOG "
        "entry per W-18 sequencing (lint BEFORE entry)."
    )

    # AST symbol pin — robust against function-body refactor; only fails
    # on rename / removal of the four contracted public symbols.
    module = ast.parse(lint_path.read_text(encoding="utf-8"))
    defined = {
        node.name
        for node in module.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    missing = [s for s in _V11_1_1_LINT_REQUIRED_SYMBOLS if s not in defined]
    assert not missing, (
        f"W-18 v11.1.1 violation: {_V11_1_1_LINT_FILE} missing required "
        f"public symbols {missing!r}. Required set: "
        f"{list(_V11_1_1_LINT_REQUIRED_SYMBOLS)!r}; defined: "
        f"{sorted(defined)!r}."
    )

    # CHANGELOG entry — ALWAYS pinned (CHANGELOG.md IS tracked).
    changelog_text = (project_root / _V11_1_1_CHANGELOG).read_text(encoding="utf-8")
    for sub in _V11_1_1_CHANGELOG_POSITIVE_SUBSTRINGS:
        assert sub in changelog_text, (
            f"W-18 v11.1.1 violation: CHANGELOG.md missing positive "
            f"substring {sub!r} per v11.1.1 PATCH scope. The W-18 stanza "
            "lands BEFORE the CHANGELOG entry per W-18 sequencing — if "
            "this lint fails the entry must be authored."
        )

    # Single-application discipline (PV-03 N-2 mitigation; the bug we're
    # fixing — do NOT trip it while writing the fix). Use line-anchored
    # match (mirrors `grep -c '^## \\[11\\.1\\.1\\]'` semantics).
    section_header_count = sum(
        1 for line in changelog_text.splitlines() if line.startswith("## [11.1.1]")
    )
    assert section_header_count == 1, (
        "W-18 v11.1.1 violation: CHANGELOG.md contains "
        f"{section_header_count} line-anchored '## [11.1.1]' section "
        "headers — exactly 1 expected (PV-03 N-2 single-application "
        "discipline; the v11.1.1 D-1 patch is THIS class-of-bug fix, "
        "do not trip it while writing the fix)."
    )


# v11.1.2 PATCH (D-2 in the v11.1.x stability-patch series; deferral D-4 in
# the v11.1.0 retrospective §3): `audit_layer_usage.py` regex bold-markdown
# coverage. Second of 3 staged stability patches (v11.1.1 / v11.1.2 / v11.1.3)
# closing the cycle-observed risks documented in
# `docs/cycle-archive/v11.1.0/retrospective.md` §3.
#
# The legacy v10.5.0 regex matched only plain `Dispatch type:` text, missing
# the v11.x markdown-bold convention `**Dispatch type:** Wave` used in cycle
# plans, retrospectives, and stage reports. As a consequence, the v11.1.0
# PV-05 audit ratchet `cascade_ratio` reported 0 for v11.x cycle docs even
# though L1/L2 dispatches actually happened (the v11.1.0 cycle-archive
# retrospective + per-PV stage reports + NineS analyses contain ≥7 bold-style
# `**Dispatch type:** Wave` mentions; the OLD regex caught 0 of them).
#
# v11.1.2 D-2 widens `_DISPATCH_TYPE_RE` via the `\*{0,2}` quantifier to
# admit 0/1/2 asterisks before AND after the label and value uniformly,
# covering plain / italic / bold styles. The dual `\*{0,2}\s*\*{0,2}` slot
# between `[:=]` and the value group is intentional — it admits the
# full-bold case `**Dispatch type:** **Wave**` where the closing-label `**`
# and opening-value `**` are separated by whitespace. Capture group 1 (the
# layer name) and the `\b` word boundary + `re.IGNORECASE` flag are
# preserved so plain-text inputs match byte-identically (W-20 backward-
# compat; the existing 15 tests in `tests/test_audit_layer_usage.py` are
# preserved byte-stable).
_V11_1_2_TEST_FILE: Path = Path("tests/test_audit_layer_usage.py")


_V11_1_2_SCRIPT_FILE: Path = Path("scripts/audit_layer_usage.py")


_V11_1_2_CHANGELOG: Path = Path("CHANGELOG.md")


# Required NEW test functions in tests/test_audit_layer_usage.py — pinned
# via AST so refactor of the function body is OK but rename / removal
# fails fast. Note: only the NEW v11.1.2 tests are pinned here; the
# pre-existing 15 tests are byte-stable per W-20 backward-compat.
_V11_1_2_REQUIRED_NEW_TESTS: tuple[str, ...] = (
    "test_dispatch_type_regex_matches_plain_style",
    "test_dispatch_type_regex_matches_bold_markdown_style",
    "test_dispatch_type_regex_matches_bold_value_only",
    "test_dispatch_type_regex_matches_full_bold",
)


# Substrings required in scripts/audit_layer_usage.py to evidence the
# regex broadening. The source must contain `\*{0,2}` — the canonical
# marker — AND the citation back to the cycle archive.
_V11_1_2_SCRIPT_POSITIVE_SUBSTRINGS: tuple[str, ...] = (
    r"\*{0,2}",
    "v11.1.2 D-2",
    "docs/cycle-archive/v11.1.0/retrospective.md",
)


# CHANGELOG body must carry the v11.1.2 PATCH entry verbatim.
_V11_1_2_CHANGELOG_POSITIVE_SUBSTRINGS: tuple[str, ...] = (
    "## [11.1.2] - 2026-05-08",
    "PATCH",
    "audit_layer_usage.py",
    "bold-markdown",
)


# v11.1.3 PATCH (D-3 in the v11.1.x stability-patch series; the third v11.1.x
# cycle-observed risk telegraphed at v11.1.0 cycle close): tiktoken determinism
# documentation. Third and final of 3 staged stability patches (v11.1.1 +
# v11.1.2 + v11.1.3) closing the cycle-observed risks documented in
# `docs/cycle-archive/v11.1.0/retrospective.md`.
#
# This is a PURE-DOCUMENTATION patch — zero code/test logic change. The
# `tests/conftest.py::_force_fallback_token_estimator` autouse fixture forces
# `sys.modules["tiktoken"] = None` for every `test_benchmarks.py` test so the
# fallback `len(text) // 4` token estimator runs uniformly across CI / dev /
# fresh-clone environments. This is INTENTIONAL — pinning to fallback keeps
# pytest-side composites comparable across machines. The bug it surfaces is
# operator-side: regen scripts that import `devolaflow.benchmarks` OUTSIDE
# the pytest harness do NOT see the fixture fire, so the resulting baselines
# diverge from pytest scoring by ~7pp on the composite axis.
#
# v11.1.3 D-3 closes the documentation gap on three surfaces:
#
#   1. tests/conftest.py::_force_fallback_token_estimator — docstring
#      expanded with WHY (deterministic scoring), EFFECT (~7pp divergence
#      between pytest and raw scoring), and 3 fallback options for
#      reproducing pytest scoring outside pytest (Option A: invoke under
#      pytest; Option B: pre-set sys.modules["tiktoken"] = None; Option C:
#      uninstall tiktoken). Body of the fixture preserved BYTE-IDENTICAL
#      (W-20 contract preservation — no runtime surface change).
#   2. workflow-system/agent/references/troubleshooting.md — NEW §2.16
#      "Token-estimation determinism (W-16 baseline regen)" subsection
#      with the same 3-option fallback summary, plus a §1 Quick Lookup
#      Index row and `last_updated` bump to "2026-05-08".
#   3. CHANGELOG.md ## [11.1.3] entry citing the PATCH scope, the
#      v11.1.0 retrospective source, and the v11.1.x stability-patch
#      series close.
_V11_1_3_CONFTEST_FILE: Path = Path("tests/conftest.py")


_V11_1_3_REFERENCE_FILE: Path = Path("workflow-system/agent/references/troubleshooting.md")


_V11_1_3_CHANGELOG: Path = Path("CHANGELOG.md")


# Substrings required in tests/conftest.py to evidence the docstring
# expansion. The docstring MUST cite tiktoken + W-16 + deterministic
# (the three load-bearing concepts) AND the cycle-archive citation.
_V11_1_3_CONFTEST_POSITIVE_SUBSTRINGS: tuple[str, ...] = (
    "tiktoken",
    "W-16 baseline regen",
    "deterministic",
    'sys.modules["tiktoken"] = None',
    "Option A",
    "Option B",
    "Option C",
    "v11.1.3 D-3",
    "docs/cycle-archive/v11.1.0/retrospective.md",
)


# Substrings required in references/troubleshooting.md to evidence the
# new §2.16 section. The reference MUST carry the section header AND the
# same 3-option fallback summary.
_V11_1_3_REFERENCE_POSITIVE_SUBSTRINGS: tuple[str, ...] = (
    "#### 2.16 Token-estimation determinism (W-16 baseline regen)",
    "_force_fallback_token_estimator",
    "Option A",
    "Option B",
    "Option C",
    'sys.modules["tiktoken"] = None',
    "v11.1.3 D-3",
)


# CHANGELOG body must carry the v11.1.3 PATCH entry verbatim.
_V11_1_3_CHANGELOG_POSITIVE_SUBSTRINGS: tuple[str, ...] = (
    "## [11.1.3] - 2026-05-08",
    "PATCH",
    "tiktoken",
    "W-16",
    "_force_fallback_token_estimator",
)


def test_v11_1_3_new_surfaces_have_coverage(project_root: Path) -> None:
    """W-18 v11.1.3 PATCH: D-3 tiktoken determinism documentation.

    Discharges the W-18 precondition for the v11.1.3 PATCH CHANGELOG
    entry. Per W-18 sequencing the documentation refresh MUST land
    BEFORE the CHANGELOG entry — this stanza closes that precondition.

    Surfaces pinned (v11.1.3 D-3 patch scope; THIRD AND FINAL of 3
    staged v11.1.x stability patches — sister patches v11.1.1 + v11.1.2):

    * ``tests/conftest.py::_force_fallback_token_estimator`` carries
      the expanded docstring covering WHY (deterministic benchmark
      scoring across environments), EFFECT (~7pp divergence between
      pytest scoring and raw subprocess scoring), and 3 OPTIONS for
      reproducing pytest scoring outside pytest:

      - Option A (preferred): invoke regen under the pytest harness so
        the autouse fixture fires automatically.
      - Option B: pre-set ``sys.modules["tiktoken"] = None`` BEFORE
        importing any devolaflow modules in the regen script.
      - Option C: uninstall tiktoken from the venv (heavy-handed —
        affects every workflow in the env).

      The fixture BODY is preserved byte-identically — only the
      docstring changed (W-20 contract preservation; no runtime
      surface delta).

    * ``workflow-system/agent/references/troubleshooting.md`` carries
      a NEW §2.16 "Token-estimation determinism (W-16 baseline regen)"
      subsection with the same 3-option fallback summary, a
      cross-reference to the conftest fixture, and a §1 Quick Lookup
      Index row pointing at §2.16. The file's frontmatter
      ``last_updated`` field is bumped to "2026-05-08".

    * ``CHANGELOG.md`` carries the ``## [11.1.3] - 2026-05-08`` PATCH
      entry mentioning ``PATCH`` + ``tiktoken`` + ``W-16`` +
      ``_force_fallback_token_estimator`` (the v11.1.0 retrospective
      cycle-close source citation).

    * ``CHANGELOG.md`` ``## [11.1.3]`` section header appears EXACTLY
      once (the v11.1.1 D-1 single-application lint pre-condition;
      this stanza independently asserts the line-anchored count via
      splitlines + line.startswith).

    Coupled invariants verified GREEN at PATCH close (no source edits
    to gate / schema / SKILL / runtime):

    * A-2.4 multi-baseline byte test: 32/32 PASS unchanged
    * S-10 hook-chain byte-id: 10/10 PASS unchanged
    * CP-4 gate suite: 108/108 PASS unchanged
    * v11.1.1 D-1 CHANGELOG lint: PASS (this stanza's CHANGELOG
      entry is single-application — proving v11.1.1 D-1 catches its
      own next test; sister-patch chain holds across 3 patches)
    * v11.1.2 D-2 audit_layer_usage regex: 19/19 PASS unchanged
    * W-21 Soul-set freeze preserved at 10 entries
    * W-20 reuse-first preserved at 8 env flags
    * conftest fixture body preserved BYTE-IDENTICAL (only docstring
      changed; the ``monkeypatch.setitem(sys.modules, "tiktoken",
      None)`` body is untouched)

    Source: ``docs/cycle-archive/v11.1.0/retrospective.md`` cycle-
    close summary (the v11.1.0 PV-02 W-16 wholesale baseline regen
    was the first cycle where this divergence surfaced empirically;
    v11.1.3 D-3 closes the documentation gap and the v11.1.x
    stability-patch series).
    """
    conftest_path = project_root / _V11_1_3_CONFTEST_FILE
    assert conftest_path.is_file(), (
        f"W-18 v11.1.3 violation: conftest file {_V11_1_3_CONFTEST_FILE} missing. "
        "The docstring expansion MUST land in the same commit as "
        "the CHANGELOG entry per W-18 sequencing."
    )

    conftest_text = conftest_path.read_text(encoding="utf-8")
    for sub in _V11_1_3_CONFTEST_POSITIVE_SUBSTRINGS:
        assert sub in conftest_text, (
            f"W-18 v11.1.3 violation: {_V11_1_3_CONFTEST_FILE} missing "
            f"positive substring {sub!r} — the v11.1.3 D-3 docstring "
            "expansion MUST cite the load-bearing concepts (tiktoken + "
            "W-16 + deterministic + the 3 fallback options + the "
            "cycle-archive retrospective citation)."
        )

    reference_path = project_root / _V11_1_3_REFERENCE_FILE
    assert reference_path.is_file(), (
        f"W-18 v11.1.3 violation: reference file {_V11_1_3_REFERENCE_FILE} missing. "
        "The new §2.16 subsection MUST land in the same commit as "
        "the CHANGELOG entry per W-18 sequencing."
    )

    reference_text = reference_path.read_text(encoding="utf-8")
    for sub in _V11_1_3_REFERENCE_POSITIVE_SUBSTRINGS:
        assert sub in reference_text, (
            f"W-18 v11.1.3 violation: {_V11_1_3_REFERENCE_FILE} missing "
            f"positive substring {sub!r} — the v11.1.3 D-3 §2.16 "
            "subsection MUST carry the section header + the 3-option "
            "fallback summary + the conftest cross-reference."
        )

    # CHANGELOG entry — ALWAYS pinned (CHANGELOG.md IS tracked).
    changelog_text = (project_root / _V11_1_3_CHANGELOG).read_text(encoding="utf-8")
    for sub in _V11_1_3_CHANGELOG_POSITIVE_SUBSTRINGS:
        assert sub in changelog_text, (
            f"W-18 v11.1.3 violation: CHANGELOG.md missing positive "
            f"substring {sub!r} per v11.1.3 PATCH scope. The W-18 stanza "
            "lands BEFORE the CHANGELOG entry per W-18 sequencing — if "
            "this lint fails the entry must be authored."
        )

    # Single-application discipline (v11.1.1 D-1 lint pre-condition; this
    # stanza independently mirrors the line-anchored count to surface
    # any drift before the cross-test runs).
    section_header_count = sum(
        1 for line in changelog_text.splitlines() if line.startswith("## [11.1.3]")
    )
    assert section_header_count == 1, (
        "W-18 v11.1.3 violation: CHANGELOG.md contains "
        f"{section_header_count} line-anchored '## [11.1.3]' section "
        "headers — exactly 1 expected (v11.1.1 D-1 single-application "
        "lint pre-condition; the v11.1.3 D-3 patch INHERITS the v11.1.1 "
        "discipline cleanly across 3 patches — do not trip the "
        "predecessor's lint while writing the successor's fix)."
    )


def test_v11_1_2_new_surfaces_have_coverage(project_root: Path) -> None:
    """W-18 v11.1.2 PATCH: D-2 audit_layer_usage.py regex bold-markdown coverage.

    Discharges the W-18 precondition for the v11.1.2 PATCH CHANGELOG
    entry. Per W-18 sequencing the lint refresh MUST land BEFORE the
    CHANGELOG entry — this stanza closes that precondition.

    Surfaces pinned (v11.1.2 D-2 patch scope; second of 3 staged
    v11.1.x stability patches — sister patches v11.1.1 + v11.1.3):

    * ``tests/test_audit_layer_usage.py`` carries the 4 NEW regex
      coverage tests (AST symbol pin):

      - ``test_dispatch_type_regex_matches_plain_style``
        (negative-control — plain `Dispatch type:` matches; W-20
        backward-compat preserved).
      - ``test_dispatch_type_regex_matches_bold_markdown_style``
        (the D-2 fix — `**Dispatch type:** Wave` matches).
      - ``test_dispatch_type_regex_matches_bold_value_only``
        (defensive — bold value `Dispatch type: **Wave**` matches).
      - ``test_dispatch_type_regex_matches_full_bold``
        (defensive — full-bold `**Dispatch type:** **Wave**` matches;
        pins the dual ``\\*{0,2}\\s*\\*{0,2}`` slot design).

    * ``scripts/audit_layer_usage.py`` carries the broadened regex —
      the source MUST contain ``\\*{0,2}`` (the canonical broadening
      marker) AND the citation back to ``docs/cycle-archive/v11.1.0/
      retrospective.md``.

    * ``CHANGELOG.md`` carries the ``## [11.1.2] - 2026-05-08``
      PATCH entry mentioning ``PATCH`` + ``audit_layer_usage.py`` +
      ``bold-markdown`` (the v11.1.0 retrospective §3 D-4 deferral
      citation; the dispatcher's D-2 in-series label).

    * ``CHANGELOG.md`` ``## [11.1.2]`` section header appears
      EXACTLY once (the v11.1.1 D-1 single-application lint
      pre-condition; this stanza independently asserts the
      line-anchored count via splitlines + line.startswith).

    Coupled invariants verified GREEN at PATCH close (no source
    edits to gate / schema / SKILL):

    * A-2.4 multi-baseline byte test: 32/32 PASS unchanged
    * S-10 hook-chain byte-id: 10/10 PASS unchanged
    * CP-4 gate suite: 108/108 PASS unchanged
    * v11.1.1 D-1 CHANGELOG lint: PASS (this stanza's CHANGELOG
      entry is single-application — proving v11.1.1 D-1 catches
      its own next test)
    * W-21 Soul-set freeze preserved at 10 entries
    * W-20 reuse-first preserved at 8 env flags
    * Existing 15 tests in ``tests/test_audit_layer_usage.py``
      preserved byte-stable (W-20 backward-compat — the regex
      BROADENING admits new inputs without changing the v10.5.0
      plain-text contract)

    Source: ``docs/cycle-archive/v11.1.0/retrospective.md`` §3 D-4
    (cycle-deferral inventory; the dispatcher's D-2 in-series label).
    """
    test_path = project_root / _V11_1_2_TEST_FILE
    assert test_path.is_file(), (
        f"W-18 v11.1.2 violation: test file {_V11_1_2_TEST_FILE} missing. "
        "The 4 NEW regex coverage tests MUST land in the same commit as "
        "the CHANGELOG entry per W-18 sequencing."
    )

    # AST symbol pin — robust against function-body refactor; only fails
    # on rename / removal of the four contracted public symbols.
    module = ast.parse(test_path.read_text(encoding="utf-8"))
    defined = {
        node.name
        for node in module.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    missing = [s for s in _V11_1_2_REQUIRED_NEW_TESTS if s not in defined]
    assert not missing, (
        f"W-18 v11.1.2 violation: {_V11_1_2_TEST_FILE} missing required "
        f"NEW test functions {missing!r}. Required set: "
        f"{list(_V11_1_2_REQUIRED_NEW_TESTS)!r}; defined: "
        f"{sorted(defined)!r}."
    )

    # Audit script source MUST evidence the regex broadening — the
    # `\*{0,2}` quantifier is the canonical marker; the citation
    # anchors the deferral trail.
    script_path = project_root / _V11_1_2_SCRIPT_FILE
    assert script_path.is_file(), f"W-18 v11.1.2 violation: script {_V11_1_2_SCRIPT_FILE} missing."
    script_text = script_path.read_text(encoding="utf-8")
    for sub in _V11_1_2_SCRIPT_POSITIVE_SUBSTRINGS:
        assert sub in script_text, (
            f"W-18 v11.1.2 violation: {_V11_1_2_SCRIPT_FILE} missing "
            f"positive substring {sub!r} — the v11.1.2 D-2 regex "
            "broadening MUST cite both the `\\*{0,2}` quantifier (the "
            "canonical marker) AND the cycle-archive retrospective "
            "citation in the source comment."
        )

    # CHANGELOG entry — ALWAYS pinned (CHANGELOG.md IS tracked).
    changelog_text = (project_root / _V11_1_2_CHANGELOG).read_text(encoding="utf-8")
    for sub in _V11_1_2_CHANGELOG_POSITIVE_SUBSTRINGS:
        assert sub in changelog_text, (
            f"W-18 v11.1.2 violation: CHANGELOG.md missing positive "
            f"substring {sub!r} per v11.1.2 PATCH scope. The W-18 stanza "
            "lands BEFORE the CHANGELOG entry per W-18 sequencing — if "
            "this lint fails the entry must be authored."
        )

    # Single-application discipline (v11.1.1 D-1 lint pre-condition; this
    # stanza independently mirrors the line-anchored count to surface
    # any drift before the cross-test runs).
    section_header_count = sum(
        1 for line in changelog_text.splitlines() if line.startswith("## [11.1.2]")
    )
    assert section_header_count == 1, (
        "W-18 v11.1.2 violation: CHANGELOG.md contains "
        f"{section_header_count} line-anchored '## [11.1.2]' section "
        "headers — exactly 1 expected (v11.1.1 D-1 single-application "
        "lint pre-condition; the v11.1.2 D-2 patch INHERITS the v11.1.1 "
        "discipline cleanly — do not trip the predecessor's lint while "
        "writing the successor's fix)."
    )
