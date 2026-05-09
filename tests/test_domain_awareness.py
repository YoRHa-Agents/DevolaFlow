"""Pin domain-awareness.md content to v11.3.0 spec (W-18 ghost-audit precedent).

These are positive-substring assertions per the v11.1.3 D-3 pattern in
``tests/test_no_ghost_features.py::test_v11_1_3_new_surfaces_have_coverage``.
The W-18 ghost-audit refresh in Wave 2 also pins these strings; this file
is the focused per-feature test owned by W1.T3.

Each test is R5-strict zero-IO:
* No subprocess invocation, no network access, no LLM call.
* Reads exactly one file (`domain-awareness.md`) via a module-scoped
  fixture so the file is read once and shared across tests.
* Asserts only that specific substrings appear in the text — no
  semantic interpretation, no parsing beyond ``str in str``.

The verbatim phrases pinned here come from the v11.3.0 cycle's
canonical sources:

* `CONTEXT-FORMAT.md` (4 mandatory sections, "Be opinionated" rule,
  "Only project-specific" rule)
* `ADR-FORMAT.md` (3-condition ADR gate, sequential numbering rule,
  1-3 sentences body rule)

The file under test is `workflow-system/agent/references/domain-awareness.md`
(authored by W1.T3 of the v11.3.0 cycle; gap-analysis source =
`.local/research/v11.3.0_gap_analysis.md` §4 P1.2).
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DOMAIN_AWARENESS_PATH = (
    REPO_ROOT / "workflow-system" / "agent" / "references" / "domain-awareness.md"
)


@pytest.fixture(scope="module")
def domain_awareness_content() -> str:
    """Read `domain-awareness.md` once per module — shared across tests."""
    assert DOMAIN_AWARENESS_PATH.is_file(), (
        f"domain-awareness.md missing at {DOMAIN_AWARENESS_PATH}; "
        "v11.3.0 W1.T3 must author this file before this test file lands."
    )
    return DOMAIN_AWARENESS_PATH.read_text(encoding="utf-8")


def test_context_md_required_sections_documented(
    domain_awareness_content: str,
) -> None:
    """§3 must document the 4 mandatory CONTEXT.md sections (F-1 / verbatim).

    The upstream `CONTEXT-FORMAT.md` mandates exactly 4 section headers
    in every CONTEXT.md (lines 10, 24, 29, 34 of the upstream file).
    domain-awareness.md §3 reproduces this verbatim by including the
    upstream sample inside a fenced markdown code block.
    """
    for required_header in (
        "## Language",
        "## Relationships",
        "## Example dialogue",
        "## Flagged ambiguities",
    ):
        assert required_header in domain_awareness_content, (
            f"domain-awareness.md missing F-1 section header {required_header!r} — "
            "the §3 verbatim block from CONTEXT-FORMAT.md MUST reproduce all 4 "
            "mandatory section headers (Language / Relationships / Example "
            "dialogue / Flagged ambiguities)."
        )


def test_context_md_be_opinionated_rule_documented(
    domain_awareness_content: str,
) -> None:
    """§4 must reproduce the "Be opinionated" rule verbatim (F-2).

    Verbatim quote source: `CONTEXT-FORMAT.md` line 41 (first bullet of
    the upstream "## Rules" section). The two pinned substrings are the
    cause-clause and the resolution-clause of the rule; both must
    appear in the file body.
    """
    assert "When multiple words exist for the same concept" in domain_awareness_content, (
        "domain-awareness.md §4 missing F-2 cause clause — the verbatim "
        "phrase 'When multiple words exist for the same concept' from "
        "CONTEXT-FORMAT.md line 41 MUST appear in §4."
    )
    assert "list the others as aliases to avoid" in domain_awareness_content, (
        "domain-awareness.md §4 missing F-2 resolution clause — the verbatim "
        "phrase 'list the others as aliases to avoid' from CONTEXT-FORMAT.md "
        "line 41 MUST appear in §4."
    )


def test_context_md_only_project_specific_rule_documented(
    domain_awareness_content: str,
) -> None:
    """§5 must reproduce the "Only project-specific" rule verbatim (F-3).

    Verbatim quote source: `CONTEXT-FORMAT.md` line 45 (the fifth bullet
    of the upstream "## Rules" section). The two pinned substrings are
    the subject-clause and the predicate-clause of the rule; both must
    appear in the file body.
    """
    assert "General programming concepts" in domain_awareness_content, (
        "domain-awareness.md §5 missing F-3 subject clause — the verbatim "
        "phrase 'General programming concepts' from CONTEXT-FORMAT.md "
        "line 45 MUST appear in §5."
    )
    assert "don't belong even if the project uses them extensively" in domain_awareness_content, (
        "domain-awareness.md §5 missing F-3 predicate clause — the verbatim "
        "phrase 'don't belong even if the project uses them extensively' "
        "from CONTEXT-FORMAT.md line 45 MUST appear in §5."
    )


def test_adr_format_3_condition_gate_documented(
    domain_awareness_content: str,
) -> None:
    """§8.5 must document all 3 ADR gate conditions verbatim (F-7).

    Verbatim quote source: `ADR-FORMAT.md` lines 33-35 (the numbered
    list under "## When to offer an ADR"). The 3 condition strings
    are the canonical labels every downstream caller pins on; each
    one MUST appear verbatim in the §8.5 body.
    """
    for condition in (
        "Hard to reverse",
        "Surprising without context",
        "real trade-off",
    ):
        assert condition in domain_awareness_content, (
            f"domain-awareness.md §8.5 missing ADR gate condition {condition!r} — "
            "the verbatim 3-condition list from ADR-FORMAT.md lines 33-35 MUST "
            "appear in §8.5 (Hard to reverse / Surprising without context / "
            "real trade-off)."
        )


def test_adr_format_sequential_numbering_documented(
    domain_awareness_content: str,
) -> None:
    """§8.1 must document the ADR sequential numbering scheme (F-5).

    Verbatim quote source: `ADR-FORMAT.md` lines 3-5. Pins the literal
    `0001-slug.md` numbering scheme, the lazy-creation phrase
    'lazily', and the trigger phrase 'first ADR is needed' so the §8.1
    body cannot drift from the upstream contract.
    """
    assert "0001-slug.md" in domain_awareness_content, (
        "domain-awareness.md §8.1 missing F-5 numbering literal — the "
        "verbatim phrase '0001-slug.md' from ADR-FORMAT.md line 3 MUST "
        "appear in §8.1 (the canonical 4-digit zero-padded scheme)."
    )
    assert "lazily" in domain_awareness_content, (
        "domain-awareness.md §8.1 missing F-5 lazy-creation phrase — the "
        "verbatim word 'lazily' from ADR-FORMAT.md line 5 MUST appear in "
        "§8.1 to telegraph the 'first ADR needed' trigger condition."
    )
    assert "first ADR is needed" in domain_awareness_content, (
        "domain-awareness.md §8.1 missing F-5 trigger phrase — the verbatim "
        "phrase 'first ADR is needed' from ADR-FORMAT.md line 5 MUST appear "
        "in §8.1 to bind the lazy-creation rule to its trigger."
    )


def test_adr_format_minimum_body_documented(
    domain_awareness_content: str,
) -> None:
    """§8.2 must document the 1-3 sentences ADR body rule (F-6).

    Verbatim quote source: `ADR-FORMAT.md` line 15. Pins the canonical
    minimum-body phrase 'An ADR can be a single paragraph' AND the
    value-statement 'The value is in recording *that* a decision was
    made' so the §8.2 body cannot drift toward longer / more
    structured templates.
    """
    assert "An ADR can be a single paragraph" in domain_awareness_content, (
        "domain-awareness.md §8.2 missing F-6 minimum-body phrase — the "
        "verbatim phrase 'An ADR can be a single paragraph' from "
        "ADR-FORMAT.md line 15 MUST appear in §8.2."
    )
    assert "The value is in recording *that* a decision was made" in domain_awareness_content, (
        "domain-awareness.md §8.2 missing F-6 value-statement — the verbatim "
        "phrase 'The value is in recording *that* a decision was made' from "
        "ADR-FORMAT.md line 15 MUST appear in §8.2 to bind the minimum-body "
        "rule to its rationale."
    )


def test_a4_distinction_and_historical_adr_distinction_documented(
    domain_awareness_content: str,
) -> None:
    """§2.2 must cite A-4 by name AND §9 must distinguish historical ADRs.

    Two acceptance criteria from the W1.T3 task brief composed into one
    test (both relate to "the spec.md vs CONTEXT.md vs historical-ADR
    boundary"):

    * §2.2 spec.md vs CONTEXT.md distinction MUST cite A-4 by name and
      link to `references/agent-workspace.md` (per gap analysis §4 P1.2
      AC-7 and the v11.3.0 task brief acceptance criterion #7).
    * §9 historical `.local/research/adr/` distinction MUST be present
      (per gap analysis §3.3 mitigation and the v11.3.0 task brief
      acceptance criterion #8).
    """
    assert "A-4" in domain_awareness_content, (
        "domain-awareness.md §2.2 missing A-4 citation — the spec.md vs "
        "CONTEXT.md distinction MUST cite Architecture rule A-4 (Source-of-"
        "Truth Spec Location) by name per the v11.3.0 task brief AC-7."
    )
    assert "references/agent-workspace.md" in domain_awareness_content, (
        "domain-awareness.md §2.2 missing agent-workspace cross-reference — "
        "the spec.md vs CONTEXT.md distinction MUST link to "
        "`references/agent-workspace.md` (the file that documents A-4 in "
        "full) per the v11.3.0 task brief AC-7."
    )
    assert ".local/research/adr/" in domain_awareness_content, (
        "domain-awareness.md §9 missing historical-ADR-directory citation — "
        "the v11.3.0+ ADR format applies to NEW ADRs only; historical ADRs "
        "in `.local/research/adr/` are NOT retrofitted (per gap analysis "
        "§3.3 mitigation and the v11.3.0 task brief AC-8)."
    )
