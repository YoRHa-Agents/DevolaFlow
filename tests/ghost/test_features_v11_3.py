"""Ghost audit — per-cycle W-18 feature stanzas for the v11.3 cycle.

Split from ``tests/test_no_ghost_features.py`` per v15-ADR-001
(v14.3.0). New W-18 stanzas for a v11.3.x release append HERE; the
next MINOR cycle rotates to a fresh ``test_features_v<MAJ>_<MIN>.py``.
"""

from __future__ import annotations

import ast
from pathlib import Path

# ---------------------------------------------------------------------------
# v11.3.0 W-18 ghost-audit pinning surface (grill-with-docs integration MINOR)
# ---------------------------------------------------------------------------
# Per W-18 sequencing the lint refresh MUST land BEFORE the v11.3.0 CHANGELOG
# entry — see ``test_v11_3_0_new_surfaces_have_coverage`` below for the full
# rationale. Constants are clustered alongside the existing v11.1.x cluster
# so future cycle-N+1 contributors find them in one place.
_V11_3_0_GRILL_MODULE_FILE: Path = Path("src/devolaflow/skills/grill_mode.py")


_V11_3_0_GRILL_TEST_FILE: Path = Path("tests/test_grill_mode.py")


_V11_3_0_DOMAIN_TEST_FILE: Path = Path("tests/test_domain_awareness.py")


_V11_3_0_GRILL_REF_FILE: Path = Path("workflow-system/agent/references/grill-mode.md")


_V11_3_0_DOMAIN_REF_FILE: Path = Path("workflow-system/agent/references/domain-awareness.md")


_V11_3_0_CHANGELOG: Path = Path("CHANGELOG.md")


# 5 public pure-function APIs on grill_mode (AST FunctionDef pin — robust
# against function-body refactor; only fails on rename / removal of the
# five contracted public symbols enumerated in gap analysis §4 P1.3).
_V11_3_0_GRILL_REQUIRED_FUNCTIONS: tuple[str, ...] = (
    "classify_grill_intent",
    "detect_fuzzy_terms",
    "qualifies_as_adr",
    "propose_canonical_term",
    "infer_context_layout",
)


# 3 public Literal type aliases on grill_mode (AST AnnAssign pin — the
# Literal verdict strings ARE the public contract per W-22 / W-23).
_V11_3_0_GRILL_REQUIRED_ALIASES: tuple[str, ...] = (
    "GrillVerdict",
    "ContextLayout",
    "AdrConditionName",
)


# 3 public frozen dataclasses on grill_mode (AST ClassDef pin — frozen
# instances flow across L0 → L3 boundaries per W-22.3 / W-23.4).
_V11_3_0_GRILL_REQUIRED_DATACLASSES: tuple[str, ...] = (
    "FuzzyTerm",
    "CanonicalTermSuggestion",
    "DecisionDescriptor",
)


# Required NEW test functions in tests/test_grill_mode.py — the canonical
# 9-name subset that the gap analysis §4 P1.6 enumerates. The L3 author
# may have authored additional tests beyond this set; we DO NOT pin those
# so the audit remains robust against later test-suite refactors that
# consolidate or expand coverage without touching the contract surface
# (over-pinning would make the audit brittle per the v11.1.2 pattern).
_V11_3_0_GRILL_REQUIRED_NEW_TESTS: tuple[str, ...] = (
    "test_classify_grill_intent_grill_requested",
    "test_classify_grill_intent_grill_suggested",
    "test_classify_grill_intent_no_grill",
    "test_qualifies_as_adr_all_three_conditions_pass",
    "test_qualifies_as_adr_returns_missing_when_one_fails",
    "test_propose_canonical_term_returns_none_for_canonical_input",
    "test_infer_context_layout_single_context",
    "test_infer_context_layout_multi_context",
    "test_infer_context_layout_no_context_yet",
)


# Required NEW test functions in tests/test_domain_awareness.py — the
# canonical 6-name subset enumerated in gap analysis §4 P1.6.
_V11_3_0_DOMAIN_REQUIRED_NEW_TESTS: tuple[str, ...] = (
    "test_context_md_required_sections_documented",
    "test_context_md_be_opinionated_rule_documented",
    "test_context_md_only_project_specific_rule_documented",
    "test_adr_format_3_condition_gate_documented",
    "test_adr_format_sequential_numbering_documented",
    "test_adr_format_minimum_body_documented",
)


# Positive substrings for grill-mode.md — the load-bearing concepts from
# the upstream grill-with-docs SKILL (one-question-at-a-time / explore
# codebase / stress-test scenarios / 3-condition gate verbatim), the 5
# public function citations, and the explicit R-11 distinction from
# interview-protocol.md (gap analysis §5 R-11 mitigation).
_V11_3_0_GRILL_REF_POSITIVE_SUBSTRINGS: tuple[str, ...] = (
    "id: grill-mode",
    "tier: 2",
    "# Grill Mode",
    "Ask the questions one at a time",
    "explore the codebase instead",
    "stress-test them with specific scenarios",
    "Hard to reverse",
    "Surprising without context",
    "real trade-off",
    "classify_grill_intent",
    "qualifies_as_adr",
    "propose_canonical_term",
    "infer_context_layout",
    "detect_fuzzy_terms",
    "interview-protocol.md",
)


# Positive substrings for domain-awareness.md — the CONTEXT.md authoring
# rules, the ADR format, the historical .local/research/adr/ distinction,
# and the A-4 source-of-truth spec cross-reference.
_V11_3_0_DOMAIN_REF_POSITIVE_SUBSTRINGS: tuple[str, ...] = (
    "id: domain-awareness",
    "tier: 2",
    "# Domain Awareness",
    "## Language",
    "## Relationships",
    "## Example dialogue",
    "## Flagged ambiguities",
    "When multiple words exist for the same concept",
    "list the others as aliases to avoid",
    "General programming concepts",
    "0001-slug.md",
    "An ADR can be a single paragraph",
    "Hard to reverse",
    "Surprising without context",
    ".local/research/adr/",
    "A-4",
)


# CHANGELOG.md entry positive substrings — cited but the lint allows this
# stanza to FAIL until Stage 3 authors the entry (see test docstring for
# the W-18 sequencing detail). The 6 substrings pin: the section header,
# the load-bearing scope name (grill-with-docs), the new module file, the
# two new workflow rules (W-22 + W-23), and the predecessor version
# citation (11.1.3 → 11.3.0 minor jump).
_V11_3_0_CHANGELOG_POSITIVE_SUBSTRINGS: tuple[str, ...] = (
    "## [11.3.0]",
    "grill-with-docs",
    "grill_mode.py",
    "W-22",
    "W-23",
    "11.1.3",
)


def test_v11_3_0_new_surfaces_have_coverage(project_root: Path) -> None:
    """W-18 v11.3.0 MINOR: grill-with-docs integration cycle.

    Discharges the W-18 precondition for the v11.3.0 MINOR CHANGELOG
    entry. Per W-18 sequencing the lint refresh MUST land BEFORE the
    CHANGELOG entry — this stanza closes that precondition. Until
    Stage 3 lands the entry the CHANGELOG portion of this test FAILS
    intentionally; that failure IS the W-18 lint gate working as
    designed and is the signal Stage 3 needs to author the entry.

    Surfaces pinned (v11.3.0 grill-with-docs integration cycle):

    * ``src/devolaflow/skills/grill_mode.py`` carries 5 public
      pure-function APIs (AST symbol pin):

      - ``classify_grill_intent`` — natural-language activation
        classifier returning
        ``Literal["GRILL_REQUESTED", "GRILL_SUGGESTED", "NO_GRILL"]``.
      - ``detect_fuzzy_terms`` — scans a plan text against a
        CONTEXT.md glossary, returning ``FuzzyTerm`` entries for each
        ``Avoid:`` alias match.
      - ``qualifies_as_adr`` — applies the 3-condition ADR gate
        (Hard to reverse + Surprising without context + Real
        trade-off); returns ``(qualifies, missing_conditions)``.
      - ``propose_canonical_term`` — suggests the canonical
        replacement for a fuzzy candidate term.
      - ``infer_context_layout`` — filesystem probe returning
        ``Literal["SINGLE_CONTEXT", "MULTI_CONTEXT", "NO_CONTEXT_YET"]``.

      3 public ``Literal`` type aliases (AST AnnAssign pin):
      ``GrillVerdict``, ``ContextLayout``, ``AdrConditionName``.

      3 public frozen dataclasses (AST ClassDef pin):
      ``FuzzyTerm``, ``CanonicalTermSuggestion``, ``DecisionDescriptor``.

    * ``tests/test_grill_mode.py`` carries the 9 canonical NEW test
      functions enumerated in ``.local/research/v11.3.0_gap_analysis.md``
      §4 P1.6. The L3 author may have added tests beyond this set —
      we pin only the canonical 9 so the audit remains robust against
      test-suite expansion (over-pinning would make the audit brittle).

    * ``tests/test_domain_awareness.py`` carries the 6 canonical NEW
      test functions enumerated in §4 P1.6.

    * ``workflow-system/agent/references/grill-mode.md`` (Tier-2
      reference, ≤ 1000 lines per C-4 Large tier) carries the
      operating contract — frontmatter (``id: grill-mode`` /
      ``tier: 2``), the load-bearing verbatim quotes from upstream
      SKILL.md (one-question-at-a-time / explore codebase /
      stress-test scenarios / 3-condition gate), all 5 public
      function citations, and the explicit R-11 distinction from
      ``interview-protocol.md`` (gap analysis §5 risk R-11).

    * ``workflow-system/agent/references/domain-awareness.md``
      (Tier-2, ≤ 1000 lines) carries the CONTEXT.md authoring rules
      (Language / Relationships / Example dialogue / Flagged
      ambiguities sections) + ADR format (``0001-slug.md`` numbering,
      single-paragraph minimum body) + the historical
      ``.local/research/adr/`` distinction + the A-4 source-of-truth
      spec cross-reference.

    * ``CHANGELOG.md`` carries the ``## [11.3.0]`` MINOR entry
      mentioning ``grill-with-docs`` + ``grill_mode.py`` + ``W-22`` +
      ``W-23`` + ``11.1.3`` (predecessor version citation). NOTE:
      per W-18 sequencing this stanza is authored BEFORE the
      CHANGELOG entry; until Stage 3 lands the entry, this portion
      of the test FAILS — that is INTENTIONAL and is the W-18 lint
      gate working as designed.

    * ``CHANGELOG.md`` ``## [11.3.0]`` section header appears EXACTLY
      once (v11.1.1 D-1 single-application lint inheritance — this
      stanza preserves the line-anchored count discipline across the
      v11.1.x → v11.3.0 MINOR boundary).

    Coupled invariants verified GREEN at MINOR close (no source edits
    to gate / schema / S-10 hooks):

    * A-2.4 multi-baseline byte test: 32/32 PASS unchanged
      (canonical_order stays at 17; no new dispatch keys per gap
      analysis §5 risk R-5).
    * S-10 hook-chain byte-id: 10/10 PASS unchanged.
    * CP-4 gate suite: 108/108 PASS unchanged (no
      ``src/devolaflow/gate/`` edits).
    * v11.1.1 D-1 CHANGELOG lint: PASS (this stanza's CHANGELOG
      entry is single-application — proving v11.1.1 D-1 catches its
      own next test; sister-patch-pattern inheritance preserved
      across the v11.1.x → v11.3.0 MINOR boundary).
    * v11.1.2 D-2 audit_layer_usage regex: 19/19 PASS unchanged.
    * v11.1.3 D-3 conftest fixture: byte-stable; the W-16 baseline
      regen for v11.3.0 cycle start MUST run under the pytest
      harness for tiktoken determinism.
    * W-21 Soul-set freeze preserved at 10 entries (no S-11
      proposed; W-22 + W-23 land at Workflow layer, architecturally
      correct per ADR-007 §"Soul-vs-Architecture decision-rule").
    * W-20 reuse-first preserved at 8 env flags (NO new
      ``DEVOLAFLOW_*`` env flag introduced; grill-mode activation is
      natural-language-only per W-22.4).

    Source: ``.local/research/v11.3.0_gap_analysis.md`` §4 P1.7
    (W-18 ghost-audit refresh BEFORE CHANGELOG entry sequencing).
    """
    # ----- 1. grill_mode.py public API surface (AST pin) -----
    grill_module_path = project_root / _V11_3_0_GRILL_MODULE_FILE
    assert grill_module_path.is_file(), (
        f"W-18 v11.3.0 violation: {_V11_3_0_GRILL_MODULE_FILE} missing. "
        "The grill_mode module MUST land in the same MINOR cycle as the "
        "CHANGELOG entry per W-18 sequencing."
    )
    grill_module = ast.parse(grill_module_path.read_text(encoding="utf-8"))

    defined_funcs = {
        node.name
        for node in grill_module.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    missing_funcs = [f for f in _V11_3_0_GRILL_REQUIRED_FUNCTIONS if f not in defined_funcs]
    assert not missing_funcs, (
        f"W-18 v11.3.0 violation: {_V11_3_0_GRILL_MODULE_FILE} missing "
        f"required public functions {missing_funcs!r}. Required set: "
        f"{list(_V11_3_0_GRILL_REQUIRED_FUNCTIONS)!r}; "
        f"defined: {sorted(defined_funcs)!r}."
    )

    # Literal type aliases in grill_mode.py use plain Assign (e.g.,
    # ``GrillVerdict = Literal[...]``) per the existing v11.3.0 module
    # style; private constants (``_REQUESTED_TRIGGERS: Final = ...``)
    # use AnnAssign. Both node forms are walked so the public Literal
    # aliases surface regardless of which annotation style the L3 author
    # picked. Extras in ``defined_aliases`` are harmless — the missing
    # check only fails if a REQUIRED name is absent.
    defined_aliases: set[str] = set()
    for node in grill_module.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    defined_aliases.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            defined_aliases.add(node.target.id)
    missing_aliases = [a for a in _V11_3_0_GRILL_REQUIRED_ALIASES if a not in defined_aliases]
    assert not missing_aliases, (
        f"W-18 v11.3.0 violation: {_V11_3_0_GRILL_MODULE_FILE} missing "
        f"required Literal aliases {missing_aliases!r}. Required set: "
        f"{list(_V11_3_0_GRILL_REQUIRED_ALIASES)!r}; "
        f"defined: {sorted(defined_aliases)!r}."
    )

    defined_classes = {node.name for node in grill_module.body if isinstance(node, ast.ClassDef)}
    missing_classes = [c for c in _V11_3_0_GRILL_REQUIRED_DATACLASSES if c not in defined_classes]
    assert not missing_classes, (
        f"W-18 v11.3.0 violation: {_V11_3_0_GRILL_MODULE_FILE} missing "
        f"required frozen dataclasses {missing_classes!r}. Required set: "
        f"{list(_V11_3_0_GRILL_REQUIRED_DATACLASSES)!r}; "
        f"defined: {sorted(defined_classes)!r}."
    )

    # ----- 2. test_grill_mode.py NEW test surface (AST pin; canonical subset) -----
    grill_test_path = project_root / _V11_3_0_GRILL_TEST_FILE
    assert grill_test_path.is_file(), (
        f"W-18 v11.3.0 violation: {_V11_3_0_GRILL_TEST_FILE} missing. "
        "The grill_mode test surface MUST land in the same MINOR cycle "
        "as the CHANGELOG entry per W-18 sequencing."
    )
    grill_test_module = ast.parse(grill_test_path.read_text(encoding="utf-8"))
    grill_defined_tests = {
        node.name
        for node in grill_test_module.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    missing_grill_tests = [
        t for t in _V11_3_0_GRILL_REQUIRED_NEW_TESTS if t not in grill_defined_tests
    ]
    assert not missing_grill_tests, (
        f"W-18 v11.3.0 violation: {_V11_3_0_GRILL_TEST_FILE} missing "
        f"required NEW test functions {missing_grill_tests!r}. Required "
        f"canonical subset (gap analysis §4 P1.6): "
        f"{list(_V11_3_0_GRILL_REQUIRED_NEW_TESTS)!r}."
    )

    # ----- 3. test_domain_awareness.py NEW test surface (AST pin) -----
    domain_test_path = project_root / _V11_3_0_DOMAIN_TEST_FILE
    assert domain_test_path.is_file(), (
        f"W-18 v11.3.0 violation: {_V11_3_0_DOMAIN_TEST_FILE} missing. "
        "The domain_awareness test surface MUST land in the same MINOR "
        "cycle as the CHANGELOG entry per W-18 sequencing."
    )
    domain_test_module = ast.parse(domain_test_path.read_text(encoding="utf-8"))
    domain_defined_tests = {
        node.name
        for node in domain_test_module.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    missing_domain_tests = [
        t for t in _V11_3_0_DOMAIN_REQUIRED_NEW_TESTS if t not in domain_defined_tests
    ]
    assert not missing_domain_tests, (
        f"W-18 v11.3.0 violation: {_V11_3_0_DOMAIN_TEST_FILE} missing "
        f"required NEW test functions {missing_domain_tests!r}. Required "
        f"canonical subset (gap analysis §4 P1.6): "
        f"{list(_V11_3_0_DOMAIN_REQUIRED_NEW_TESTS)!r}."
    )

    # ----- 4. grill-mode.md content surface (positive-substring pin) -----
    grill_ref_path = project_root / _V11_3_0_GRILL_REF_FILE
    assert grill_ref_path.is_file(), (
        f"W-18 v11.3.0 violation: {_V11_3_0_GRILL_REF_FILE} missing. "
        "The grill-mode operating-contract reference MUST land in the "
        "same MINOR cycle as the CHANGELOG entry per W-18 sequencing."
    )
    grill_ref_text = grill_ref_path.read_text(encoding="utf-8")
    for sub in _V11_3_0_GRILL_REF_POSITIVE_SUBSTRINGS:
        assert sub in grill_ref_text, (
            f"W-18 v11.3.0 violation: {_V11_3_0_GRILL_REF_FILE} missing "
            f"positive substring {sub!r} — the grill-mode reference MUST "
            "carry the load-bearing verbatim quotes (one-question-at-a-time "
            "/ explore codebase / stress-test scenarios / 3-condition gate), "
            "all 5 public function citations, and the explicit R-11 "
            "distinction from interview-protocol.md."
        )

    # ----- 5. domain-awareness.md content surface (positive-substring pin) -----
    domain_ref_path = project_root / _V11_3_0_DOMAIN_REF_FILE
    assert domain_ref_path.is_file(), (
        f"W-18 v11.3.0 violation: {_V11_3_0_DOMAIN_REF_FILE} missing. "
        "The domain-awareness reference MUST land in the same MINOR "
        "cycle as the CHANGELOG entry per W-18 sequencing."
    )
    domain_ref_text = domain_ref_path.read_text(encoding="utf-8")
    for sub in _V11_3_0_DOMAIN_REF_POSITIVE_SUBSTRINGS:
        assert sub in domain_ref_text, (
            f"W-18 v11.3.0 violation: {_V11_3_0_DOMAIN_REF_FILE} missing "
            f"positive substring {sub!r} — the domain-awareness reference "
            "MUST carry the CONTEXT.md authoring rules + ADR format + the "
            "historical .local/research/adr/ distinction + the A-4 "
            "source-of-truth spec cross-reference."
        )

    # ----- 6. CHANGELOG.md entry (positive-substring + line-anchored count) -----
    # Per W-18 sequencing this stanza is authored BEFORE the CHANGELOG entry;
    # until Stage 3 lands the entry, the assertions below FAIL — that is the
    # W-18 lint gate working as designed (the failure IS the signal).
    changelog_path = project_root / _V11_3_0_CHANGELOG
    assert changelog_path.is_file(), (
        "W-18 v11.3.0 violation: CHANGELOG.md missing — release-blocker."
    )
    changelog_text = changelog_path.read_text(encoding="utf-8")
    for sub in _V11_3_0_CHANGELOG_POSITIVE_SUBSTRINGS:
        assert sub in changelog_text, (
            f"W-18 v11.3.0 violation: CHANGELOG.md missing positive "
            f"substring {sub!r} per v11.3.0 MINOR scope. The W-18 stanza "
            "lands BEFORE the CHANGELOG entry per W-18 sequencing — if "
            "this lint fails the entry must be authored mentioning the "
            "load-bearing concepts (grill-with-docs + grill_mode.py + "
            "W-22 + W-23 + 11.1.3 predecessor)."
        )

    # Single-application discipline (v11.1.1 D-1 lint pre-condition; this
    # stanza independently mirrors the line-anchored count to surface any
    # drift before the cross-test runs across the MINOR boundary).
    section_header_count = sum(
        1 for line in changelog_text.splitlines() if line.startswith("## [11.3.0]")
    )
    assert section_header_count == 1, (
        "W-18 v11.3.0 violation: CHANGELOG.md contains "
        f"{section_header_count} line-anchored '## [11.3.0]' section "
        "headers — exactly 1 expected (v11.1.1 D-1 single-application "
        "lint pre-condition; the v11.3.0 MINOR INHERITS the v11.1.x "
        "discipline cleanly across the MINOR boundary — do not trip the "
        "predecessor's lint while writing the successor's entry)."
    )
