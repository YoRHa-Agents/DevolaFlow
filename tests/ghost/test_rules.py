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
# Two new lints enforce the PV-07 governance contract:
#
#   * test_rule_count_under_cap — total compiled-AGENTS.md rule count ≤ 60
#     (HARD per ADR-007 D5). Rule count = sum of `^## ([SACW]|ST)-\d+`
#     headings in AGENTS.md (the operator-facing canonical compile output).
#   * test_rule_surfaces_compile_only — `.cursor/rules/repo-governance.mdc`
#     SHA-256 matches the value stored in `.rules/.compile-hashes.json`
#     (drift detection); every deprecated stub registered in
#     `devolaflow.local.drift::DEPRECATED_STUB_FILES` (6 as of v14.2.1 G-008)
#     matches its expected stub-template fingerprint (preventing
#     hand-edits). Failure means the canonical-vs-compiled invariant is broken
#     OR a stub was hand-edited to drift from the deprecation scaffold.

# v9.0.0 PV-07 (ADR-007 D5) — HARD cap on the total rule count surfaced by
# the compiled AGENTS.md. The 60 cap derives from improvements_zh.md
# §"Rule cap" + the cumulative additions across the v9.0.0 cycle (PV-03
# A-5 + PV-04 S-10 + PV-05 W-16..W-20 + PV-07 W-21 = 7 net additions on top
# of the v8.4.0 baseline of 50). Post-PV-07 rule census: Soul 10 + Arch 5 +
# Conv 9 + Workflow 21 = 45 rules in AGENTS.md (Style is excluded from
# AGENTS.md per `compile-config.yaml#agents_md.include_layers`); the
# repo-governance.mdc target additionally surfaces Style 13 → 58 total
# in the cursor target. The cap is enforced on the AGENTS.md surface (the
# operator-facing canonical compile output).
_RULE_COUNT_CAP_HARD: int = 60


_SOUL_FREEZE_COUNT: int = 10  # post-W-21 Soul-set freeze (ADR-007 D4)


def test_rule_count_under_cap(project_root: Path) -> None:
    """ADR-007 D5: AGENTS.md compiled rule count ≤ 60 HARD.

    Counts every ``^## ([SACW]|ST)-\\d+`` heading in the compiled AGENTS.md
    file and asserts the total stays at or below the 60-rule HARD cap from
    `improvements_zh.md` §"Rule cap" + ADR-007 D5. Also pins:

    1. The Soul-set count at exactly 10 (S-1..S-10, frozen by W-21 Soul-set
       freeze governance per ADR-007 D4).
    2. The total stays ≤ 60.
    3. **G-034 parity (v14.2.1)**: the per-layer "Rule count" figures
       declared in the `.rules/index.md` layer table match the rule-id
       headings actually present in the on-disk `.rules/*.mdc` sources,
       and the "Total rules" header figure equals their sum. Closes the
       v14.2.0 gap-register row G-034 (index.md said "5 (A-1..A-5)"
       while architecture.mdc carried A-1..A-7).

    Future cycles proposing a new rule MUST first confirm `total + 1 ≤ 60`
    before authoring; if the projection exceeds 60, the proposing PV must
    either (a) defer an existing rule, OR (b) explicitly raise the cap via
    a new ADR. Soul additions further require the W-21 2-cycle telegraph
    protocol (deferral note in cycle N retrospective → SI-1 in cycle N+2 →
    SI-3 §3.2 ≥ 9.5/10 in cycle N+2) before bumping past 10.
    """
    from devolaflow.task_adaptive_selector import count_agents_md_rules

    agents_md = project_root / "AGENTS.md"
    assert agents_md.is_file(), (
        f"AGENTS.md missing at {agents_md.relative_to(project_root)} — "
        f"run `python -c 'from devolaflow.local.compiler import RuleCompiler; "
        f'RuleCompiler(".rules/compile-config.yaml").compile_all()\'` to regenerate'
    )

    census = count_agents_md_rules(agents_md_path=agents_md)
    total = census["total"]
    by_layer = census["by_layer"]

    assert total <= _RULE_COUNT_CAP_HARD, (
        f"ADR-007 D5 violation: AGENTS.md rule count {total} exceeds "
        f"the 60 HARD cap. Per-layer breakdown: {by_layer}. "
        f"Future PVs adding rules MUST either defer an existing rule OR "
        f"explicitly raise the cap via a new ADR."
    )

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


def test_rule_surfaces_compile_only(project_root: Path) -> None:
    """ADR-007 D2 + D5: `.cursor/rules/*.mdc` files must be compile-only.

    Two-part invariant per ADR-007:

    1. **D5** — `.cursor/rules/repo-governance.mdc` (the compiled full corpus)
       SHA-256 matches the `cursor` entry in `.rules/.compile-hashes.json`.
       A hand-edit to the compiled file shifts the SHA-256 and fails this
       assertion — operators MUST regenerate via
       `RuleCompiler('.rules/compile-config.yaml').compile_all()` instead
       of editing the compiled output directly.

    2. **D2** — every deprecated stub registered in
       `devolaflow.local.drift::DEPRECATED_STUB_FILES` (2 at v9.0.0 PV-07
       per ADR-007 D2; +4 at v14.2.1 per G-008 — `change-process` /
       `context-optimization` / `self-improve-iteration` / `skill-format`)
       must match the stub-template fingerprint stored under its
       `stub_<name>` key in `.rules/.compile-hashes.json`. The stubs are
       pinned cross-reference scaffolds — a hand-edit either drifts the
       SHA-256 OR grows the stub past the ≤ 50-line ceiling enforced by
       the inline length check below.

    Failure modes:
      * "compiled file SHA-256 mismatch" → operator hand-edited
        `repo-governance.mdc`; re-run `RuleCompiler.compile_all()`.
      * "stub SHA-256 mismatch" → operator hand-edited a deprecated stub;
        the stubs are intentionally frozen as cross-reference scaffolds.
      * "stub line count > 50" → a stub grew past the deprecation ceiling;
        either compress back or re-evaluate the deprecation decision.
      * "compile-hashes.json missing key" → drift store wasn't regenerated
        with the v9.0.0 PV-07 stub fingerprints; re-run
        `RuleCompiler.compile_all()` after the v9.0.0 update.
    """
    from devolaflow.local.drift import (
        DEPRECATED_STUB_FILES,
        check_rules_drift,
        check_stub_drift,
    )

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

    stub_results = check_stub_drift(repo_root=project_root, hash_file=hash_file)
    drifted_stubs = [r for r in stub_results if r.status == "drifted"]
    assert not drifted_stubs, (
        f"ADR-007 D2 violation: deprecated stub fingerprints drifted from "
        f".rules/.compile-hashes.json: "
        f"{[(r.target, r.expected_hash, r.actual_hash) for r in drifted_stubs]}. "
        f"The stubs registered in drift.DEPRECATED_STUB_FILES are PINNED "
        f"cross-reference scaffolds — re-run "
        f"RuleCompiler.compile_all() after re-applying the canonical stub "
        f"template, OR investigate why the stubs were hand-edited."
    )

    missing_stubs = [r for r in stub_results if r.status == "missing"]
    assert not missing_stubs, (
        f"ADR-007 D2 violation: deprecated stub or fingerprint missing: "
        f"{[r.target for r in missing_stubs]}. Re-run RuleCompiler.compile_all() "
        f"after restoring the deprecated stub files."
    )

    for _key, relpath in DEPRECATED_STUB_FILES:
        stub_path = project_root / relpath
        assert stub_path.is_file(), f"Deprecated stub missing: {relpath}"
        line_count = stub_path.read_text(encoding="utf-8").count("\n") + 1
        assert line_count <= 50, (
            f"ADR-007 D2 violation: deprecated stub {relpath} has {line_count} "
            f"lines — must be ≤ 50 (cross-reference scaffold ceiling). The stub "
            f"is intentionally minimal; expand canonical content under .rules/ "
            f"instead and let the compiler re-emit the full corpus."
        )
