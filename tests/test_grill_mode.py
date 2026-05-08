"""Tests for the v11.3.0 PV-01 grill-with-docs pure-function module.

Pins the public contract of :mod:`devolaflow.skills.grill_mode` per
the v11.3.0 gap-analysis §4 P1.3 (file-level scope of the new module)
and §4 P1.6 (the test suite this file implements).

The module integrates the upstream ``grill-with-docs`` skill
(``https://github.com/mattpocock/skills/tree/main/skills/engineering/grill-with-docs``)
into DevolaFlow as 5 pure-function entrypoints. This test file pins:

1. :func:`classify_grill_intent` — natural-language activation
   classifier; REQUESTED > SUGGESTED > NO_GRILL priority order.
2. :func:`qualifies_as_adr` — 3-condition ADR gate with verbatim
   condition names (``HARD_TO_REVERSE``,
   ``SURPRISING_WITHOUT_CONTEXT``, ``REAL_TRADE_OFF``).
3. :func:`propose_canonical_term` — fuzzy-term sharpening (primitive
   6); three-way verdict (already-canonical / alias-collision /
   no-match).
4. :func:`detect_fuzzy_terms` — plan-text scan for ``Avoid:`` alias
   collisions vs the glossary.
5. :func:`infer_context_layout` — filesystem layout probe with
   ``MULTI_CONTEXT`` precedence over ``SINGLE_CONTEXT``.
6. R5 strict: importing the module performs zero filesystem I/O.

The first 13 tests are O(1) pure-function tests with no filesystem
touches. The last four (``infer_context_layout`` + the import
zero-IO test) use ``tmp_path`` / monkeypatch and are still pure in
spirit — they isolate any disk activity to a per-test sandbox.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import get_args

import pytest

from devolaflow.skills.grill_mode import (
    AdrConditionName,
    CanonicalTermSuggestion,
    ContextLayout,
    DecisionDescriptor,
    FuzzyTerm,
    GrillVerdict,
    classify_grill_intent,
    detect_fuzzy_terms,
    infer_context_layout,
    propose_canonical_term,
    qualifies_as_adr,
)

# ── classify_grill_intent ──────────────────────────────────────────────


@pytest.mark.parametrize(
    "message",
    [
        "grill this plan",
        "Please interview me about this design",
        "Can you stress-test the proposal?",
        "stress test the architecture please",
        "Challenge my plan please",
        "Please challenge the plan",
        "Interrogate every assumption I've made",
        "Help me sharpen terminology",
        "Sharpen the domain language for this project",
    ],
)
def test_classify_grill_intent_grill_requested(message: str) -> None:
    """Explicit triggers map to ``"GRILL_REQUESTED"``.

    Every entry in the parametrize list is a verbatim REQUESTED
    trigger from the gap-analysis §4 P1.3 list (case-insensitive
    substring match). The verdict is the highest-priority signal —
    L0 SHOULD enter grill-mode without further prompting.
    """
    assert classify_grill_intent(message) == "GRILL_REQUESTED"


@pytest.mark.parametrize(
    "message",
    [
        "Should we add a domain glossary?",
        "I want to clarify terms before implementing",
        "There are ambiguous terms in the spec",
        "The plan has fuzzy language we should resolve",
        "I see fuzzy terms throughout this proposal",
        "Should the team commit a CONTEXT.md to the repo?",
        "Is this an ADR-worthy decision?",
        "Should we record this decision?",
        "This change feels hard to reverse later",
    ],
)
def test_classify_grill_intent_grill_suggested(message: str) -> None:
    """Softer triggers map to ``"GRILL_SUGGESTED"``.

    These are documentation- / domain-vocabulary-flavoured signals
    that L0 SHOULD propose grill-mode but not auto-enter — leaving
    the choice to the operator. The "is this an ADR-worthy decision?"
    case proves case-insensitive matching: lowercased it contains
    the substring ``"is this an adr"``.
    """
    assert classify_grill_intent(message) == "GRILL_SUGGESTED"


@pytest.mark.parametrize(
    "message",
    [
        "Add a function that does X",
        "Refactor this loop to use itertools",
        "Fix the typo in the README",
        "Bump the version to 11.3.0",
        "Run the test suite",
    ],
)
def test_classify_grill_intent_no_grill(message: str) -> None:
    """Typical implementation requests yield ``"NO_GRILL"``.

    R5 strict default-OFF: when no triggers fire, the verdict is
    NO_GRILL. This is the most common path (typical plan-mode
    delegation has no grill signal); preserves byte-identical legacy
    dispatch behaviour for operators who never mention grill mode.
    """
    assert classify_grill_intent(message) == "NO_GRILL"


def test_classify_grill_intent_priority_requested_over_suggested() -> None:
    """When BOTH REQUESTED and SUGGESTED triggers fire, REQUESTED wins.

    Pins the ordering rule from gap-analysis §4 P1.3: "Order matters:
    REQUESTED > SUGGESTED > NO_GRILL". A message like "grill me about
    the domain glossary" contains both ``"grill"`` (REQUESTED) and
    ``"domain glossary"`` (SUGGESTED) — the verdict MUST be
    REQUESTED, never SUGGESTED.
    """
    message = "Please grill me about the domain glossary and ADR choices"
    assert classify_grill_intent(message) == "GRILL_REQUESTED"


@pytest.mark.parametrize("message", ["", "   ", "\n\n", "\t"])
def test_classify_grill_intent_empty_message_returns_no_grill(message: str) -> None:
    """Empty / whitespace-only messages → ``"NO_GRILL"``.

    Pins the degenerate-input contract: a blank message can never
    activate grill mode. Mirrors the ``classify_complexity`` "no
    silent coercion" pattern (S-5) — though here the coercion target
    is the safe NO_GRILL default rather than a raised exception
    because an empty natural-language utterance is a normal session
    state (e.g. a freshly-opened chat), not an error.
    """
    assert classify_grill_intent(message) == "NO_GRILL"


# ── qualifies_as_adr ───────────────────────────────────────────────────


def test_qualifies_as_adr_all_three_conditions_pass() -> None:
    """All three conditions True → ``(True, [])``.

    Pins the upstream ``ADR-FORMAT.md`` "When to offer an ADR" gate:
    the ADR is qualified iff Hard-to-reverse, Surprising-without-
    context, and Real-trade-off are ALL true. The empty
    ``missing_conditions`` list is the explicit success signal.
    """
    decision = DecisionDescriptor(
        title="Use Postgres for the write model",
        hard_to_reverse=True,
        surprising_without_context=True,
        real_trade_off=True,
    )
    assert qualifies_as_adr(decision) == (True, [])


def test_qualifies_as_adr_returns_missing_when_one_fails() -> None:
    """Single missing condition surfaces in ``missing_conditions``.

    Pins the diagnostic contract: when only one of the three
    conditions fails, the returned list contains exactly that
    condition's canonical name. Callers can render the list verbatim
    to the operator to explain why the ADR was skipped.
    """
    decision = DecisionDescriptor(
        title="Switch to Redis cache",
        hard_to_reverse=True,
        surprising_without_context=False,
        real_trade_off=True,
    )
    qualifies, missing = qualifies_as_adr(decision)
    assert qualifies is False
    assert missing == ["SURPRISING_WITHOUT_CONTEXT"]


def test_qualifies_as_adr_returns_all_three_when_all_fail() -> None:
    """All three conditions False → all three names returned in canonical order.

    Pins the canonical ordering of :data:`AdrConditionName`:
    ``HARD_TO_REVERSE`` first, ``SURPRISING_WITHOUT_CONTEXT`` second,
    ``REAL_TRADE_OFF`` third. The order matches the verbatim source
    in ``ADR-FORMAT.md`` so callers can iterate the list in the same
    order the upstream skill enumerates the conditions.
    """
    decision = DecisionDescriptor(
        title="Add a debug log line",
        hard_to_reverse=False,
        surprising_without_context=False,
        real_trade_off=False,
    )
    qualifies, missing = qualifies_as_adr(decision)
    assert qualifies is False
    assert missing == [
        "HARD_TO_REVERSE",
        "SURPRISING_WITHOUT_CONTEXT",
        "REAL_TRADE_OFF",
    ]


# ── propose_canonical_term ─────────────────────────────────────────────


def test_propose_canonical_term_handles_alias_collision() -> None:
    """Candidate is in an "Avoid:" list → canonical surfaced + other aliases listed.

    Pins primitive 6 ("Sharpen fuzzy language") behaviour: when the
    operator types an alias that the glossary already flags as
    "to-avoid" under some canonical term, the function MUST surface
    both the canonical replacement AND the other aliases of the same
    canonical so the operator can avoid every synonym.
    """
    glossary = {
        "Customer": "A person or organization that places orders. _Avoid_: client, account, buyer",
    }
    suggestion = propose_canonical_term("client", glossary)
    assert suggestion.candidate == "client"
    assert suggestion.canonical == "Customer"
    assert set(suggestion.avoid_aliases) == {"account", "buyer"}
    assert "client" in suggestion.rationale
    assert "Customer" in suggestion.rationale


def test_propose_canonical_term_returns_none_for_canonical_input() -> None:
    """Candidate IS canonical → ``canonical=None`` + ``rationale="Already canonical."``.

    Pins the no-op verdict for an operator who already used the
    correct canonical term. The function returns the verbatim
    sentinel rationale string so callers can string-match against it
    if they want to short-circuit downstream UI.
    """
    glossary = {"Customer": "A person or organization that places orders."}
    suggestion = propose_canonical_term("Customer", glossary)
    assert suggestion.candidate == "Customer"
    assert suggestion.canonical is None
    assert suggestion.avoid_aliases == ()
    assert suggestion.rationale == "Already canonical."


def test_propose_canonical_term_returns_none_for_unknown_term() -> None:
    """Candidate matches NEITHER canonical nor alias → no-match rationale.

    Empty glossary ALWAYS yields the no-match outcome (per
    gap-analysis §4 P1.3 spec). The verbatim rationale advises the
    operator to add the term to ``CONTEXT.md`` — the lazy
    domain-glossary creation pattern from upstream §"Domain
    awareness".
    """
    suggestion = propose_canonical_term("widget", {})
    assert suggestion.candidate == "widget"
    assert suggestion.canonical is None
    assert suggestion.avoid_aliases == ()
    assert suggestion.rationale == ("No matching glossary term; consider adding to CONTEXT.md.")


def test_propose_canonical_term_canonical_match_is_case_insensitive() -> None:
    """Canonical-key lookup is case-insensitive.

    The glossary key is ``"Customer"`` but the operator types
    ``"customer"``. The function MUST recognise it as already
    canonical and return the no-op ``"Already canonical."`` rationale.
    Pins the case-insensitive contract documented in
    :func:`propose_canonical_term`'s docstring.
    """
    glossary = {"Customer": "A buyer."}
    suggestion = propose_canonical_term("customer", glossary)
    assert suggestion.canonical is None
    assert suggestion.rationale == "Already canonical."


# ── detect_fuzzy_terms ─────────────────────────────────────────────────


def test_detect_fuzzy_terms_finds_avoid_aliases() -> None:
    """Plan text uses an alias → :class:`FuzzyTerm` with correct position.

    Pins primitive 3 sub-pattern ("Challenge against the glossary"):
    when the plan body mentions ``"client"`` and the glossary defines
    ``Customer`` with ``_Avoid_: client``, the function returns a
    :class:`FuzzyTerm` whose ``term`` is the alias, ``plan_position``
    is the verbatim character offset, and ``candidates`` is the
    canonical term tuple.
    """
    glossary = {
        "Customer": "A person or organization. _Avoid_: client, buyer",
    }
    plan_text = "the new client onboarding flow"
    hits = detect_fuzzy_terms(plan_text, glossary)
    assert len(hits) == 1
    hit = hits[0]
    assert hit.term == "client"
    assert hit.plan_position == plan_text.find("client")
    assert hit.candidates == ("Customer",)


def test_detect_fuzzy_terms_handles_multiple_occurrences() -> None:
    """Multiple occurrences of the same alias yield multiple :class:`FuzzyTerm` entries.

    Pins the per-position emission rule from gap-analysis §4 P1.3:
    "Multiple plan-text occurrences of the same alias → multiple
    FuzzyTerm entries (one per position)". The plan_position values
    must be distinct and monotonically increasing so callers can
    underline every occurrence in the operator-facing UI.
    """
    glossary = {"Customer": "A buyer. _Avoid_: client"}
    plan_text = "client A and client B both signed up; the third client too"
    hits = detect_fuzzy_terms(plan_text, glossary)
    positions = [hit.plan_position for hit in hits]
    assert len(hits) == 3
    assert positions == sorted(positions)
    assert len(set(positions)) == 3
    assert all(hit.term == "client" for hit in hits)


def test_detect_fuzzy_terms_empty_glossary_returns_empty_list() -> None:
    """Empty glossary or empty plan text → ``[]``.

    Pins the degenerate-input contracts: when there's nothing to
    match against (no glossary) or nothing to scan (no plan text),
    the function returns an empty list rather than raising. This
    mirrors the :func:`classify_grill_intent` pattern of safe
    defaults for empty inputs.
    """
    assert detect_fuzzy_terms("the client signed up", {}) == []
    assert detect_fuzzy_terms("", {"Customer": "A buyer. _Avoid_: client"}) == []
    assert detect_fuzzy_terms("", {}) == []


# ── infer_context_layout ───────────────────────────────────────────────


def test_infer_context_layout_single_context(tmp_path: Path) -> None:
    """``CONTEXT.md`` only → ``"SINGLE_CONTEXT"``.

    Pins the upstream §"File structure" "Most repos have a single
    context" case: a single ``CONTEXT.md`` at the repo root signals
    the single-context layout regardless of nested per-context files
    elsewhere.
    """
    (tmp_path / "CONTEXT.md").write_text("# Single context\n")
    assert infer_context_layout(tmp_path) == "SINGLE_CONTEXT"


def test_infer_context_layout_multi_context(tmp_path: Path) -> None:
    """``CONTEXT-MAP.md`` present → ``"MULTI_CONTEXT"`` regardless of CONTEXT.md.

    Pins the precedence rule from gap-analysis §4 P1.3: when
    ``CONTEXT-MAP.md`` exists at the repo root, the layout is
    MULTI_CONTEXT even if a stray ``CONTEXT.md`` is also present
    (the map takes precedence — it points to per-context CONTEXT.md
    files inside src/ subdirectories per upstream §"File structure").
    """
    (tmp_path / "CONTEXT-MAP.md").write_text("# Context map\n")
    assert infer_context_layout(tmp_path) == "MULTI_CONTEXT"

    # Even with a stray CONTEXT.md present, MULTI_CONTEXT still wins.
    (tmp_path / "CONTEXT.md").write_text("# Stray single\n")
    assert infer_context_layout(tmp_path) == "MULTI_CONTEXT"


def test_infer_context_layout_no_context_yet(tmp_path: Path) -> None:
    """Empty repo root → ``"NO_CONTEXT_YET"`` (lazy-creation pre-condition).

    Pins the upstream §"Domain awareness" lazy-creation rule: the
    glossary is created LAZILY when the first term is resolved. Until
    then, the inference returns NO_CONTEXT_YET so callers know to
    create the glossary on the first resolution event.
    """
    assert infer_context_layout(tmp_path) == "NO_CONTEXT_YET"


def test_infer_context_layout_missing_repo_root_raises(tmp_path: Path) -> None:
    """Non-existent ``repo_root`` raises :class:`FileNotFoundError` (S-5).

    Pins the no-silent-failure contract: when the operator passes a
    path that doesn't exist, the function raises rather than
    returning a misleading ``NO_CONTEXT_YET`` (which would imply the
    repo is freshly-initialised but CONTEXT.md was just not created
    yet — different semantics from "the path doesn't exist").
    """
    bogus = tmp_path / "definitely_does_not_exist_xyz"
    with pytest.raises(FileNotFoundError, match="repo_root"):
        infer_context_layout(bogus)


# ── module-level / public-contract pins ────────────────────────────────


def test_grill_mode_module_zero_io_at_import(monkeypatch: pytest.MonkeyPatch) -> None:
    """R5 strict: importing :mod:`devolaflow.skills.grill_mode` performs no filesystem I/O.

    Companion test pattern per W-20 §"Authoring requirements": pin
    the zero-IO-at-import invariant explicitly so a future refactor
    that accidentally adds a top-level ``Path(...).exists()`` call
    (or any other filesystem read) fails this test before any
    operator notices the cache invalidation.

    Methodology: monkeypatch ``pathlib.Path.exists`` to record every
    invocation, pop the module from ``sys.modules``, then re-import.
    The import MUST NOT trigger any recorded calls — the only place
    in the module that probes the filesystem is
    :func:`infer_context_layout`, and that only runs when explicitly
    called.
    """
    import pathlib

    sentinel: list[str] = []
    original_exists = pathlib.Path.exists

    def recording_exists(self: pathlib.Path) -> bool:
        sentinel.append(str(self))
        return original_exists(self)

    monkeypatch.setattr(pathlib.Path, "exists", recording_exists)

    sys.modules.pop("devolaflow.skills.grill_mode", None)
    importlib.import_module("devolaflow.skills.grill_mode")

    assert sentinel == [], (
        f"R5 strict: import devolaflow.skills.grill_mode must not call "
        f"Path.exists; got calls: {sentinel}"
    )


def test_grill_mode_literal_string_values_are_stable() -> None:
    """Pin the three Literal string contracts — operators rely on these values.

    Per gap-analysis §4 P1.3 the three Literal types are the
    operator-quotable string contracts. Changing any literal value
    is a release blocker (it would break every downstream consumer
    that grep'd for the strings — and the Wave 2 SKILL.md edits will
    quote these strings verbatim). This test enumerates every
    literal value via :func:`typing.get_args` and asserts the
    expected sets exactly.
    """
    grill: set[GrillVerdict] = {"GRILL_REQUESTED", "GRILL_SUGGESTED", "NO_GRILL"}
    assert set(get_args(GrillVerdict)) == grill

    layout: set[ContextLayout] = {"SINGLE_CONTEXT", "MULTI_CONTEXT", "NO_CONTEXT_YET"}
    assert set(get_args(ContextLayout)) == layout

    adr: set[AdrConditionName] = {
        "HARD_TO_REVERSE",
        "SURPRISING_WITHOUT_CONTEXT",
        "REAL_TRADE_OFF",
    }
    assert set(get_args(AdrConditionName)) == adr


def test_grill_mode_dataclasses_are_frozen() -> None:
    """The three return-shape dataclasses are frozen (immutable).

    Pins the design-time invariant that
    :class:`FuzzyTerm` / :class:`CanonicalTermSuggestion` /
    :class:`DecisionDescriptor` cannot be mutated after construction
    — preserves equality semantics for callers that hash them or
    place them in sets, and matches the cache-stability discipline
    used by :class:`devolaflow.skills.change_activation`'s frozen
    types.
    """
    fuzzy = FuzzyTerm(term="x", plan_position=0, candidates=("Y",))
    suggestion = CanonicalTermSuggestion(
        candidate="x",
        canonical="Y",
        avoid_aliases=("z",),
        rationale="test",
    )
    decision = DecisionDescriptor(
        title="t",
        hard_to_reverse=True,
        surprising_without_context=True,
        real_trade_off=True,
    )

    with pytest.raises((AttributeError, TypeError)):
        fuzzy.term = "mutated"  # type: ignore[misc]
    with pytest.raises((AttributeError, TypeError)):
        suggestion.canonical = "mutated"  # type: ignore[misc]
    with pytest.raises((AttributeError, TypeError)):
        decision.title = "mutated"  # type: ignore[misc]
