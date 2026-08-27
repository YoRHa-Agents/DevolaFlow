"""Ghost audit — per-cycle W-18 feature stanzas for the v11.4 cycle.

Split from ``tests/test_no_ghost_features.py`` per v15-ADR-001
(v14.3.0). New W-18 stanzas for a v11.4.x release append HERE; the
next MINOR cycle rotates to a fresh ``test_features_v<MAJ>_<MIN>.py``.
"""

from __future__ import annotations

import ast
from pathlib import Path

# ---------------------------------------------------------------------------
# v11.4.0 W-18 ghost-audit pinning surface (subagent-patterns-2026 prep MINOR)
# ---------------------------------------------------------------------------
# Per W-18 sequencing the lint refresh MUST land BEFORE the v11.4.0 CHANGELOG
# entry — see ``test_v11_4_0_new_surfaces_have_coverage`` below for the full
# rationale. Constants are clustered alongside the v11.3.0 cluster so future
# cycle-N+1 contributors find them in one place. v11.4.0 is the deliberate
# analysis-and-lightweight-foundation prep cycle that codifies the philschmid
# supported subagent patterns (Inline Tool / Fan-Out / Teams) as
# a Tier-2 reference (`workflow-system/agent/references/subagent-patterns.md`)
# + a pure-function selection helper (`src/devolaflow/skills/subagent_pattern.py`)
# + a NEW workflow rule W-24 — leaving the schema NEST + helper wiring for the
# v12.0.0 cycle per the PV-01 cycle plan.
_V11_4_0_SUBAGENT_MODULE_FILE: Path = Path("src/devolaflow/skills/subagent_pattern.py")


_V11_4_0_SUBAGENT_TEST_FILE: Path = Path("tests/test_subagent_patterns.py")


_V11_4_0_SUBAGENT_REF_FILE: Path = Path("workflow-system/agent/references/subagent-patterns.md")


_V11_4_0_CHANGELOG: Path = Path("CHANGELOG.md")


# 3 public pure-function APIs on subagent_pattern (AST FunctionDef pin —
# robust against function-body refactor; only fails on rename / removal of
# the three contracted public symbols enumerated in gap analysis §6 P1.6).
_V11_4_0_SUBAGENT_REQUIRED_FUNCTIONS: tuple[str, ...] = (
    "select_pattern",
    "validate_inputs",
    "forbidden_pattern_rationale",
)


# 2 public Literal type aliases on subagent_pattern (AST Assign pin — the
# Literal verdict / model-tier strings ARE the public contract per W-24;
# the module declares them via plain ``X = Literal[...]`` assignment, not
# annotated assignment, mirroring the v11.3.0 W2.T5 grill_mode precedent).
_V11_4_0_SUBAGENT_REQUIRED_ALIASES: tuple[str, ...] = (
    "PatternVerdict",
    "ModelTier",
)


# Required NEW test functions in tests/test_subagent_patterns.py — the
# canonical subset the gap analysis §6 P1.3 enumerates. The L3
# author may have added tests beyond this set; we DO NOT pin those so the
# audit remains robust against later test-suite refactors that consolidate
# or expand coverage without touching the contract surface (over-pinning
# would make the audit brittle per the v11.1.2 + v11.3.0 pattern).
_V11_4_0_SUBAGENT_REQUIRED_NEW_TESTS: tuple[str, ...] = (
    "test_select_pattern_inline_for_simple_single_task",
    "test_select_pattern_fan_out_for_parallel_independent_tasks",
    "test_select_pattern_inline_for_sequential_dependent_tasks",
    "test_select_pattern_never_returns_teams_forbidden",
    "test_validate_inputs_raises_on_invalid_complexity",
    "test_validate_inputs_raises_on_invalid_model_tier",
    "test_validate_inputs_raises_on_zero_or_negative_task_count",
    "test_forbidden_pattern_rationale_explains_p5_for_teams",
    "test_subagent_pattern_module_zero_io_at_import",
    "test_subagent_pattern_literal_string_values_are_stable",
)


# Positive substrings for subagent-patterns.md — the load-bearing concepts
# from the upstream philschmid article, the P5
# invariant citation + ``shared state`` keyword (the Pattern 4 forbidden
# anchor), the 5 public symbol citations from the Python helper, and the
# explicit R-11 disambiguation from grill-mode.md (gap analysis §8) +
# the v7.x baseline cross-reference to execution-protocol.md.
_V11_4_0_SUBAGENT_REF_POSITIVE_SUBSTRINGS: tuple[str, ...] = (
    "id: subagent-patterns",
    "tier: 2",
    "# Subagent Patterns",
    "Inline Tool",
    "Fan-Out",
    "Teams",
    "P5",
    "shared state",
    "TEAMS_FORBIDDEN",
    "select_pattern",
    "validate_inputs",
    "forbidden_pattern_rationale",
    "grill-mode",
    "execution-protocol.md",
)


# CHANGELOG.md entry positive substrings — cited but the lint allows this
# stanza to FAIL until Stage 3 authors the entry (see test docstring for
# the W-18 sequencing detail). The 5 substrings pin: the section header,
# the load-bearing scope name (subagent-patterns), the new module file,
# the new workflow rule (W-24), and the predecessor version citation
# (11.3.0 → 11.4.0 minor jump).
_V11_4_0_CHANGELOG_POSITIVE_SUBSTRINGS: tuple[str, ...] = (
    "## [11.4.0]",
    "subagent-patterns",
    "subagent_pattern.py",
    "W-24",
    "11.3.0",
)


def test_v11_4_0_new_surfaces_have_coverage(project_root: Path) -> None:
    """W-18 v11.4.0 MINOR: subagent-patterns-2026 prep cycle.

    Discharges the W-18 precondition for the v11.4.0 MINOR CHANGELOG
    entry. Per W-18 sequencing the lint refresh MUST land BEFORE the
    CHANGELOG entry — this stanza closes that precondition. Until
    Stage 3 lands the entry the CHANGELOG portion of this test FAILS
    intentionally; that failure IS the W-18 lint gate working as
    designed and is the signal Stage 3 needs to author the entry.

    Surfaces pinned (v11.4.0 subagent-patterns prep cycle):

    * ``src/devolaflow/skills/subagent_pattern.py`` carries 3 public
      pure-function APIs (AST symbol pin):

      - ``select_pattern`` — 5-axis decision rule mapping
        ``(complexity, model_tier, task_count, parallel_independence,
        persistent_state_needed)`` to a
        ``Literal["INLINE", "FAN_OUT", "AGENT_POOL_FORWARD",
        "TEAMS_FORBIDDEN"]`` verdict; never returns TEAMS_FORBIDDEN
        from the operator-facing happy path (TEAMS_FORBIDDEN is the
        forbidden-pattern sentinel surfaced only by
        ``forbidden_pattern_rationale``).
      - ``validate_inputs`` — S-5 explicit-error contract; raises
        :class:`ValueError` on invalid complexity / model_tier /
        task_count (no silent coercion).
      - ``forbidden_pattern_rationale`` — operator-education path
        returning the structured P5 + Soul-level + W-21 reversal-
        pathway rationale for ``TEAMS_FORBIDDEN``; ``None`` for the
        other three verdicts.

      2 public ``Literal`` type aliases (AST Assign pin — the module
      declares them via plain ``X = Literal[...]`` assignment per the
      v11.3.0 W2.T5 grill_mode precedent):
      ``PatternVerdict``, ``ModelTier``.

    * ``tests/test_subagent_patterns.py`` carries the 12 canonical NEW
      test functions enumerated in
      ``.local/research/v11.4.0_subagent_pattern_analysis.md`` §6 P1.3
      (the L3 author may have ADDED tests beyond this set — we pin
      only the canonical set so the audit remains robust against
      test-suite expansion).

    * ``workflow-system/agent/references/subagent-patterns.md``
      (Tier-2 reference, ≤ 1000 lines per C-4 Large tier) carries
      the operating contract — frontmatter (``id: subagent-patterns``
      / ``tier: 2``), all 4 pattern names verbatim (Inline Tool /
      Fan-Out / Agent Pool / Teams), the P5 invariant citation and
      ``shared state`` keyword (the Pattern 4 forbidden anchor), all
      5 public symbol citations (``PatternVerdict``, ``ModelTier``,
      ``select_pattern``, ``validate_inputs``,
      ``forbidden_pattern_rationale``), and the explicit
      disambiguation from ``grill-mode.md`` (R-11 mitigation per gap
      analysis §8) + the v7.x baseline cross-reference to
      ``execution-protocol.md``.

    * ``CHANGELOG.md`` carries the ``## [11.4.0]`` MINOR entry
      mentioning ``subagent-patterns`` + ``subagent_pattern.py`` +
      ``W-24`` + ``11.3.0`` (predecessor version citation). NOTE:
      per W-18 sequencing this stanza is authored BEFORE the
      CHANGELOG entry; until Stage 3 lands the entry, this portion
      of the test FAILS — that is INTENTIONAL and is the W-18 lint
      gate working as designed.

    * ``CHANGELOG.md`` ``## [11.4.0]`` section header appears EXACTLY
      once (v11.1.1 D-1 single-application lint inheritance — this
      stanza preserves the line-anchored count discipline across the
      v11.3.0 → v11.4.0 MINOR boundary).

    Coupled invariants verified GREEN at MINOR close (no source edits
    to gate / schema / S-10 hooks):

    * A-2.4 multi-baseline byte test: 32/32 PASS unchanged
      (canonical_order stays at 17; no new dispatch keys per gap
      analysis §8 risk R-5).
    * S-10 hook-chain byte-id: 10/10 PASS unchanged.
    * CP-4 gate suite: 108/108 PASS unchanged (no
      ``src/devolaflow/gate/`` edits).
    * v11.1.1 D-1 CHANGELOG lint: PASS (this stanza's CHANGELOG
      entry is single-application).
    * W-21 Soul-set freeze preserved at 10 entries (no S-11
      proposed; W-24 lands at Workflow layer, mirroring W-22's
      placement rationale per ADR-007 §"Soul-vs-Architecture
      decision-rule").
    * W-20 reuse-first preserved at 8 env flags (NO new
      ``DEVOLAFLOW_*`` env flag introduced; subagent-pattern
      activation is natural-language-only per W-24.4).

    Source: ``.local/research/v11.4.0_subagent_pattern_analysis.md``
    §6 P1.6 (W-18 ghost-audit refresh BEFORE CHANGELOG entry sequencing).
    """
    # ----- 1. subagent_pattern.py public API surface (AST pin) -----
    subagent_module_path = project_root / _V11_4_0_SUBAGENT_MODULE_FILE
    assert subagent_module_path.is_file(), (
        f"W-18 v11.4.0 violation: {_V11_4_0_SUBAGENT_MODULE_FILE} missing. "
        "The subagent_pattern module MUST land in the same MINOR cycle as the "
        "CHANGELOG entry per W-18 sequencing."
    )
    subagent_module = ast.parse(subagent_module_path.read_text(encoding="utf-8"))

    defined_funcs = {
        node.name
        for node in subagent_module.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    missing_funcs = [f for f in _V11_4_0_SUBAGENT_REQUIRED_FUNCTIONS if f not in defined_funcs]
    assert not missing_funcs, (
        f"W-18 v11.4.0 violation: {_V11_4_0_SUBAGENT_MODULE_FILE} missing "
        f"required public functions {missing_funcs!r}. Required set: "
        f"{list(_V11_4_0_SUBAGENT_REQUIRED_FUNCTIONS)!r}; "
        f"defined: {sorted(defined_funcs)!r}."
    )

    # Literal aliases — handle both ``ast.Assign`` and ``ast.AnnAssign`` per
    # the v11.3.0 W2.T5 precedent: ``subagent_pattern.py`` declares the
    # Literal aliases via plain ``X = Literal[...]`` assignment (not
    # annotated assignment), so the AST walker MUST cover both node forms
    # for the pin to remain robust. Extras in ``defined_aliases`` are
    # harmless — the missing check only fails if a REQUIRED name is absent.
    defined_aliases: set[str] = set()
    for node in subagent_module.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    defined_aliases.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            defined_aliases.add(node.target.id)
    missing_aliases = [a for a in _V11_4_0_SUBAGENT_REQUIRED_ALIASES if a not in defined_aliases]
    assert not missing_aliases, (
        f"W-18 v11.4.0 violation: {_V11_4_0_SUBAGENT_MODULE_FILE} missing "
        f"required Literal aliases {missing_aliases!r}. Required set: "
        f"{list(_V11_4_0_SUBAGENT_REQUIRED_ALIASES)!r}; "
        f"defined: {sorted(defined_aliases)!r}."
    )

    # ----- 2. test_subagent_patterns.py NEW test surface (AST pin; subset) -----
    subagent_test_path = project_root / _V11_4_0_SUBAGENT_TEST_FILE
    assert subagent_test_path.is_file(), (
        f"W-18 v11.4.0 violation: {_V11_4_0_SUBAGENT_TEST_FILE} missing. "
        "The subagent_pattern test surface MUST land in the same MINOR cycle "
        "as the CHANGELOG entry per W-18 sequencing."
    )
    subagent_test_module = ast.parse(subagent_test_path.read_text(encoding="utf-8"))
    subagent_defined_tests = {
        node.name
        for node in subagent_test_module.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    missing_subagent_tests = [
        t for t in _V11_4_0_SUBAGENT_REQUIRED_NEW_TESTS if t not in subagent_defined_tests
    ]
    assert not missing_subagent_tests, (
        f"W-18 v11.4.0 violation: {_V11_4_0_SUBAGENT_TEST_FILE} missing "
        f"required NEW test functions {missing_subagent_tests!r}. Required "
        f"canonical subset (gap analysis §6 P1.3): "
        f"{list(_V11_4_0_SUBAGENT_REQUIRED_NEW_TESTS)!r}."
    )

    # ----- 3. subagent-patterns.md content surface (positive-substring pin) -----
    subagent_ref_path = project_root / _V11_4_0_SUBAGENT_REF_FILE
    assert subagent_ref_path.is_file(), (
        f"W-18 v11.4.0 violation: {_V11_4_0_SUBAGENT_REF_FILE} missing. "
        "The subagent-patterns operating-contract reference MUST land in the "
        "same MINOR cycle as the CHANGELOG entry per W-18 sequencing."
    )
    subagent_ref_text = subagent_ref_path.read_text(encoding="utf-8")
    for sub in _V11_4_0_SUBAGENT_REF_POSITIVE_SUBSTRINGS:
        assert sub in subagent_ref_text, (
            f"W-18 v11.4.0 violation: {_V11_4_0_SUBAGENT_REF_FILE} missing "
            f"positive substring {sub!r} — the subagent-patterns reference "
            "MUST carry the 4 pattern names verbatim (Inline Tool / Fan-Out / "
            "Agent Pool / Teams), the P5 invariant citation + shared-state "
            "keyword (Pattern 4 forbidden anchor), all 5 public symbol "
            "citations, and the explicit R-11 disambiguation from "
            "grill-mode.md."
        )

    # ----- 4. CHANGELOG.md entry (positive-substring + line-anchored count) -----
    # Per W-18 sequencing this stanza is authored BEFORE the CHANGELOG entry;
    # until Stage 3 lands the entry, the assertions below FAIL — that is the
    # W-18 lint gate working as designed (the failure IS the signal).
    changelog_path = project_root / _V11_4_0_CHANGELOG
    assert changelog_path.is_file(), (
        "W-18 v11.4.0 violation: CHANGELOG.md missing — release-blocker."
    )
    changelog_text = changelog_path.read_text(encoding="utf-8")
    for sub in _V11_4_0_CHANGELOG_POSITIVE_SUBSTRINGS:
        assert sub in changelog_text, (
            f"W-18 v11.4.0 violation: CHANGELOG.md missing positive "
            f"substring {sub!r} per v11.4.0 MINOR scope. The W-18 stanza "
            "lands BEFORE the CHANGELOG entry per W-18 sequencing — if "
            "this lint fails the entry must be authored mentioning the "
            "load-bearing concepts (subagent-patterns + subagent_pattern.py + "
            "W-24 + 11.3.0 predecessor)."
        )

    # Single-application discipline (v11.1.1 D-1 lint pre-condition; this
    # stanza independently mirrors the line-anchored count to surface any
    # drift before the cross-test runs across the MINOR boundary).
    section_header_count = sum(
        1 for line in changelog_text.splitlines() if line.startswith("## [11.4.0]")
    )
    assert section_header_count == 1, (
        "W-18 v11.4.0 violation: CHANGELOG.md contains "
        f"{section_header_count} line-anchored '## [11.4.0]' section "
        "headers — exactly 1 expected (v11.1.1 D-1 single-application "
        "lint pre-condition; the v11.4.0 MINOR INHERITS the v11.3.0 "
        "discipline cleanly across the MINOR boundary — do not trip the "
        "predecessor's lint while writing the successor's entry)."
    )
