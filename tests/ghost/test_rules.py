"""Ghost audit — rule-cap, compile-drift, and rule-surface lints.

Split from ``tests/test_no_ghost_features.py`` per v15-ADR-001
(v14.3.0). Owns the W-21/ADR-007 cap pins (``_RULE_COUNT_CAP_HARD``,
``_SOUL_FREEZE_COUNT``) re-exported by the deprecation aggregator.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests.ghost._helpers import _read


def test_ghost_audit_refresh_present(project_root: Path) -> None:
    """v9.0.0 PV-05 NEW (Workflow Rule W-18 enforcement).

    Asserts that the latest CHANGELOG `## [vX.Y.Z]` entry references at
    least one identifier that surfaces in this ghost-audit module — the
    W-18 contract: every CHANGELOG entry mentioning a feature MUST have
    a corresponding ghost-audit lint somewhere in this file (per S-4
    "no ghost features" + the W-18 sharpening that adds the SEQUENCING
    requirement: refresh the audit BEFORE landing the CHANGELOG entry).

    Mechanism (intentionally lightweight to avoid regex / NLP coupling):

    1. Read the current `__version__` from ``src/devolaflow/__init__.py``.
    2. Find the corresponding ``## [<version>]`` block in CHANGELOG.md
       (or fall back to the most recent ``## [vX.Y.Z]`` block if the
       block for the current version has not yet been authored).
    3. Confirm the block is NON-EMPTY and has at least one bullet that
       cites a feature (rough heuristic: at least one bullet contains a
       backticked code identifier or a CamelCase symbol).
    4. Confirm the ghost-audit package (tests/ghost/) is non-empty —
       the existence + structure of the package is the W-18 audit
       artifact (the audit lived in tests/test_no_ghost_features.py
       until the v14.3.0 v15-ADR-001 split).

    The test is intentionally LENIENT — its purpose is to catch the
    case where a future PV silently empties the audit module or skips
    the CHANGELOG entry entirely. It is NOT a substitute for the per-
    feature lint tests above; those carry the strict pass/fail
    semantics. This test is the meta-guarantee that the audit-as-a-set
    stays alive at every PV.
    """
    init_text = _read(project_root / "src/devolaflow/__init__.py")
    version_match = re.search(r'__version__\s*=\s*"([^"]+)"', init_text)
    assert version_match, "Cannot find __version__ in src/devolaflow/__init__.py"
    current_version = version_match.group(1)

    changelog = _read(project_root / "CHANGELOG.md")
    block_re = re.compile(rf"## \[{re.escape(current_version)}\](.*?)(?=\n## \[|\Z)", re.DOTALL)
    m = block_re.search(changelog)
    if m is None:
        any_block_re = re.compile(r"## \[\d+\.\d+\.\d+[^\]]*\](.*?)(?=\n## \[|\Z)", re.DOTALL)
        m = any_block_re.search(changelog)
    assert m is not None, "CHANGELOG.md has no ## [vX.Y.Z] block at all"

    block = m.group(1)
    has_feature_citation = bool(
        re.search(r"`[A-Za-z_][A-Za-z0-9_./-]+`", block)
        or re.search(r"\b[A-Z][a-zA-Z0-9]+[A-Z][a-zA-Z0-9]+\b", block)
    )
    assert has_feature_citation, (
        f"CHANGELOG block for {current_version!r} (or most-recent fallback) "
        f"has no feature citation (backticked identifier or CamelCase symbol). "
        f"W-18: every CHANGELOG entry mentioning a feature MUST have a "
        f"ghost-audit lint backing it."
    )

    audit_dir = Path(__file__).resolve().parent
    audit_text = "".join(p.read_text(encoding="utf-8") for p in sorted(audit_dir.glob("*.py")))
    assert len(audit_text) > 0, "ghost-audit package is empty — W-18 violation"
    assert "_SF4_REFERENCE_SET" in audit_text, (
        "ghost-audit package is missing the _SF4_REFERENCE_SET pin — W-18 violation"
    )


def test_rules_source_directory_exists(project_root: Path) -> None:
    """G-J2 sanity: .rules/ source directory must be present and tracked.

    Audit flagged this as conditional ("if absent, the auto-gen chain is
    broken"). Verified PRESENT in this working tree at v7.4.3 — pin closure.
    """
    rules_dir = project_root / ".rules"
    assert rules_dir.is_dir(), ".rules/ source rule directory must exist"
    assert sorted(rules_dir.glob("*.mdc")), (
        f"{rules_dir} must contain at least one *.mdc source rule file"
    )


# ── v9.0.0 PV-07 — Rule Taxonomy Rebalancing (ADR-007) ─────────────────
# Two lints enforce the governance contract:
#
#   * test_rule_count_under_cap — total rule count ≤ 60 HARD. As of the
#     v15.0.0 rule-diet (v15-ADR-004, amending ADR-007 D5) the cap
#     denominator is the FULL on-disk `.rules/` source corpus — all 5
#     layers INCLUDING Style. Rule count = sum of `^#{2,3} (S|A|C|W|ST)-N — `
#     rule-id headings across `.rules/*.mdc`.
#   * test_rule_surfaces_compile_only — `.cursor/rules/repo-governance.mdc`
#     SHA-256 matches the value stored in `.rules/.compile-hashes.json`
#     (drift detection); the 6 deprecated pointer stubs RETIRED at
#     v15.0.0 (clean_repo C1-2, decision D1) must NOT resurrect under
#     `.cursor/rules/`, and `src/devolaflow/local/drift.py` must not
#     re-grow the stub-registry machinery. Failure means the
#     canonical-vs-compiled invariant is broken OR a retired stub (or its
#     drift machinery) was resurrected.

# 60 HARD cap (ADR-007 D5, denominator re-based by v15-ADR-004 D1/D2 to the
# full `.rules/` source corpus). The pre-v19 baseline census was Soul 10 +
# Arch 7 + Conv 8 + Workflow 19 + Style 13 = 57; PV-0 lands three accepted
# Workflow rules before the approved consolidations settle the corpus at 50.
# The cap is the forcing function — a future PV adding a rule MUST first confirm
# `full-corpus total + 1 ≤ 60`; raising the cap requires a new ADR.
_RULE_COUNT_CAP_HARD: int = 60


_SOUL_FREEZE_COUNT: int = 10  # post-W-21 Soul-set freeze (ADR-007 D4)


def test_rule_count_under_cap(project_root: Path) -> None:
    """ADR-007 D5 (re-based by v15-ADR-004): full-corpus rule count ≤ 60 HARD.

    The cap denominator is the FULL on-disk `.rules/` source corpus — all
    5 layers including Style (v15-ADR-004 D1; the pre-v15.0.0 compiled-
    AGENTS.md denominator let Style escape governance). Pins:

    1. The Soul-set count at exactly 10 (S-1..S-10, frozen by W-21 Soul-set
       freeze governance per ADR-007 D4).
    2. **G-034 parity (v14.2.1)**: the per-layer "Rule count" figures
       declared in the `.rules/index.md` layer table match the rule-id
       headings actually present in the on-disk `.rules/*.mdc` sources,
       and the "Total rules" header figure equals their sum.
    3. The full-corpus on-disk total stays ≤ 60 HARD (strict — the G-009
       interim AGENTS.md-denominator pin retired with the v15.0.0
       rule-diet; the pre-v19 baseline census was 57).

    Future cycles proposing a new rule MUST first confirm `total + 1 ≤ 60`
    before authoring; if the projection exceeds 60, the proposing PV must
    either (a) defer an existing rule, OR (b) explicitly raise the cap via
    a new ADR. Soul additions further require the W-21 2-cycle telegraph
    protocol (deferral note in cycle N retrospective → SI-1 in cycle N+2 →
    SI-3 §3.2 ≥ 9.5/10 in cycle N+2) before bumping past 10.
    """
    from devolaflow.agents_md_slice import count_agents_md_rules

    agents_md = project_root / "AGENTS.md"
    assert agents_md.is_file(), (
        f"AGENTS.md missing at {agents_md.relative_to(project_root)} — "
        f"run `python -c 'from devolaflow.local.compiler import RuleCompiler; "
        f'RuleCompiler(".rules/compile-config.yaml").compile_all()\'` to regenerate'
    )

    census = count_agents_md_rules(agents_md_path=agents_md)
    by_layer = census["by_layer"]

    soul_count = by_layer.get("soul", 0)
    assert soul_count == _SOUL_FREEZE_COUNT, (
        f"ADR-007 D4 violation: Soul-set count {soul_count} != frozen count "
        f"{_SOUL_FREEZE_COUNT} (S-1..S-10). Soul additions require the W-21 "
        f"2-cycle telegraph protocol (cycle N retrospective deferral → cycle "
        f"N+2 SI-1 gap analysis → cycle N+2 SI-3 §3.2 ≥ 9.5/10) before landing."
    )

    # ----- G-034 (v14.2.1): index.md per-layer counts ↔ on-disk parity -----
    # The `.rules/index.md` layer table declares a "Rule count" per layer
    # (e.g. "10 (S-1..S-10)"). Each declared count must equal the number of
    # rule-id headings actually present in that layer's `.rules/<file>.mdc`
    # source. Rule-id headings live at H2 (soul / architecture / conventions
    # / workflow) or H3 (style nests ST-* under DS-*/WX-* grouping H2s); the
    # " — " separator excludes sub-section headings like `### A-2.1 — …`.
    index_text = (project_root / ".rules" / "index.md").read_text(encoding="utf-8")
    layer_row_re = re.compile(
        r"^\|[^|]+\|\s*`(?P<file>[a-z]+\.mdc)`\s*\|[^|]*\|[^|]*\|\s*(?P<count>\d+)\s*\(",
        re.MULTILINE,
    )
    declared_counts = {m["file"]: int(m["count"]) for m in layer_row_re.finditer(index_text)}
    assert len(declared_counts) == 5, (
        f"G-034: expected 5 layer rows with a 'Rule count' cell in "
        f".rules/index.md, parsed {sorted(declared_counts)} — the layer table "
        f"format changed; update the parity regex in this test."
    )

    rule_id_heading_re = re.compile(r"^#{2,3} (?:S|A|C|W|ST)-\d+ — ", re.MULTILINE)
    on_disk_total = 0
    for layer_file, declared in declared_counts.items():
        layer_body = (project_root / ".rules" / layer_file).read_text(encoding="utf-8")
        actual = len(rule_id_heading_re.findall(layer_body))
        on_disk_total += actual
        assert actual == declared, (
            f"G-034 violation: .rules/index.md declares {declared} rules for "
            f"`{layer_file}` but the on-disk source carries {actual} rule-id "
            f"headings. Update the index.md layer-table row (or the layer "
            f"source) so the declared count matches reality."
        )

    total_match = re.search(r"Total rules: \*\*(\d+)\*\*", index_text)
    assert total_match is not None, (
        "G-034: .rules/index.md is missing the 'Total rules: **N**' header line."
    )
    assert int(total_match.group(1)) == on_disk_total, (
        f"G-034 violation: .rules/index.md header declares "
        f"'Total rules: **{total_match.group(1)}**' but the on-disk .rules/*.mdc "
        f"sources carry {on_disk_total} rule-id headings in total."
    )

    # ----- v15-ADR-004 strict full-corpus cap (v15.0.0 rule-diet re-pin) ----
    # Denominator = the FULL on-disk `.rules/` corpus, all 5 layers including
    # Style (the `ST` regex branch above finally matches something, per
    # v15-ADR-004 D4). The G-009 interim exact-count pin (62) retired with
    # the diet; the strict ≤ 60 HARD cap is the live forcing function.
    assert on_disk_total <= _RULE_COUNT_CAP_HARD, (
        f"v15-ADR-004 violation: the on-disk .rules/ corpus carries "
        f"{on_disk_total} rule-id headings, exceeding the 60 HARD cap "
        f"(denominator = full corpus, all 5 layers including Style). "
        f"Future PVs adding rules MUST either defer/fold an existing rule "
        f"OR explicitly raise the cap via a new ADR."
    )


def test_v19_rule_refactor_contracts_are_present(project_root: Path) -> None:
    """Pin the approved v19 additions, merges, and retained rule owners."""
    rules_dir = project_root / ".rules"
    workflow = (rules_dir / "workflow.mdc").read_text(encoding="utf-8")
    conventions = (rules_dir / "conventions.mdc").read_text(encoding="utf-8")
    style = (rules_dir / "style.mdc").read_text(encoding="utf-8")
    architecture = (rules_dir / "architecture.mdc").read_text(encoding="utf-8")

    for rule_id in ("W-26", "W-27", "W-28"):
        assert f"## {rule_id} —" in workflow
    assert "automatic deletion API" in workflow
    assert ".local/tasks/archive-mappings.yaml" in workflow
    assert "generated task archive index" in workflow

    assert "## C-2 — Lean Message Format" in conventions
    assert "### Required SKILL.md Frontmatter Keys" in conventions
    assert "### Lightweight Agent Workspace Artifacts" in conventions
    assert "## C-3 —" not in conventions
    assert "## C-5 —" not in conventions
    assert "## C-9 —" not in conventions
    assert "## W-19 —" not in workflow

    for rule_id in ("ST-1", "ST-3", "ST-4", "ST-6", "ST-8", "ST-11"):
        assert f"### {rule_id} —" in style
    for rule_id in ("ST-5", "ST-7", "ST-9", "ST-10", "ST-12", "ST-13"):
        assert f"### {rule_id} —" not in style

    assert "defined by S-1" in architecture
    assert "position 17 in the live schema" in architecture


# The 6 deprecated `.cursor/rules/` pointer stubs RETIRED at v15.0.0
# (clean_repo C1-2, decision D1 — dated retirement record in the
# CHANGELOG `## [Unreleased]` PR-8 entry). Content is fully preserved in
# the compiled `repo-governance.mdc` corpus + git history. The reverse
# lint below replaces the retired ADR-007 D2 stub-fingerprint check,
# maintaining S-4 continuity: a resurrected stub file (or re-grown
# stub-registry machinery in drift.py) fails CI.
_RETIRED_STUB_FILENAMES: tuple[str, ...] = (
    "change-process-rules.mdc",
    "context-optimization-rules.mdc",
    "devola-flow-rules.mdc",
    "self-improve-iteration-rules.mdc",
    "skill-format-rules.mdc",
    "workflow-rules.mdc",
)


def test_rule_surfaces_compile_only(project_root: Path) -> None:
    """ADR-007 D5 + the v15.0.0 D1 stub retirement reverse lint.

    Two-part invariant:

    1. **ADR-007 D5** — `.cursor/rules/repo-governance.mdc` (the compiled
       full corpus) SHA-256 matches the `cursor` entry in
       `.rules/.compile-hashes.json`. A hand-edit to the compiled file
       shifts the SHA-256 and fails this assertion — operators MUST
       regenerate via `RuleCompiler('.rules/compile-config.yaml').compile_all()`
       instead of editing the compiled output directly.

    2. **Reverse lint (v15.0.0 clean_repo C1-2, decision D1)** — the 6
       deprecated pointer stubs (2 demoted at v9.0.0 PV-07 per ADR-007
       D2; +4 at v14.2.1 per G-008) were RETIRED wholesale: `git rm` ×6
       plus retirement of the stub-drift machinery that pinned them
       (the deprecated-stub registry + fingerprint helpers formerly in
       `devolaflow.local.drift`, their `stub_*` hash-store keys, and the
       `DEFAULT_ALLOWLIST` entries). This part asserts the stubs must
       NOT exist under `.cursor/rules/` and the drift module must not
       re-grow the stub registry — preventing resurrection.

    Failure modes:
      * "compiled file SHA-256 mismatch" → operator hand-edited
        `repo-governance.mdc`; re-run `RuleCompiler.compile_all()`.
      * "retired stub resurrected" → a deleted pointer stub reappeared
        under `.cursor/rules/`; the canonical content lives in `.rules/`
        + the compiled corpus — delete the resurrected file (restore
        decisions go through the CHANGELOG EXTEND clause, not silent
        re-adds).
      * "stub-registry machinery re-grown" → `drift.py` re-declares the
        retired deprecated-stub registry; new drift surfaces must cover
        compile TARGETS only.
    """
    from devolaflow.local.drift import check_rules_drift

    rules_dir = project_root / ".rules"
    hash_file = rules_dir / ".compile-hashes.json"
    assert hash_file.is_file(), (
        f"compile hash store missing at {hash_file.relative_to(project_root)} — "
        f"run RuleCompiler('.rules/compile-config.yaml').compile_all() to populate it"
    )

    compiled_results = check_rules_drift(rules_dir=rules_dir)
    drifted = [r for r in compiled_results if r.status == "drifted"]
    assert not drifted, (
        f"ADR-007 D5 violation: compiled .cursor/rules/* targets drifted from "
        f"the .rules/ source: {[(r.target, r.expected_hash, r.actual_hash) for r in drifted]}. "
        f"Re-run RuleCompiler.compile_all() to regenerate."
    )

    missing_compiled = [r for r in compiled_results if r.status == "missing"]
    assert not missing_compiled, (
        f"ADR-007 D5 violation: compiled .cursor/rules/* targets missing on "
        f"disk: {[r.target for r in missing_compiled]}. Re-run "
        f"RuleCompiler.compile_all() to regenerate."
    )

    # ----- v15.0.0 D1 reverse lint: retired stubs must NOT resurrect -----
    resurrected = [
        filename
        for filename in _RETIRED_STUB_FILENAMES
        if (project_root / ".cursor" / "rules" / filename).exists()
    ]
    assert not resurrected, (
        f"clean_repo C1-2 (decision D1) violation: retired deprecated "
        f"pointer stub(s) resurrected under .cursor/rules/: {resurrected}. "
        f"The 6 stubs were retired at v15.0.0 — canonical content lives in "
        f".rules/ + the compiled repo-governance.mdc corpus (zero loss); "
        f"history is in git. To un-retire, follow the EXTEND fallback "
        f"clause in the CHANGELOG retirement record instead of silently "
        f"re-adding files."
    )

    drift_source = (project_root / "src/devolaflow/local/drift.py").read_text(encoding="utf-8")
    assert "DEPRECATED_STUB_FILES" not in drift_source, (
        "clean_repo C1-2 (decision D1) violation: the stub-drift registry "
        "machinery was retired from src/devolaflow/local/drift.py together "
        "with the 6 pointer stubs (an empty registry would be a ghost "
        "surface per S-4). New drift surfaces must cover compile TARGETS "
        "declared in .rules/compile-config.yaml, not resurrected stubs."
    )
