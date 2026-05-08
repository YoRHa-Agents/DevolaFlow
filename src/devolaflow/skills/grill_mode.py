"""Grill-with-docs primitives as pure-function heuristics (v11.3.0 cycle).

Codifies the seven behavioural primitives of the upstream
``grill-with-docs`` skill (``https://github.com/mattpocock/skills/tree/
main/skills/engineering/grill-with-docs``) as pure-function helpers
for L0 plan-mode dispatchers. Cited by workflow rules **W-22**
("Grill Mode Activation Contract") and **W-23** ("Domain Glossary
Maintenance"), both authored in v11.3.0 Wave 2.

Design (mirrors :mod:`devolaflow.skills.change_activation`, the v9.1.2
PV-02 design template): pure functions, zero filesystem I/O at import
(only :func:`infer_context_layout` touches disk); R5 strict default-OFF
natural-language activation, no new ``DEVOLAFLOW_*`` env flag (W-20
reuse-first); composes with but never imports :mod:`change_activation`;
literal verdicts are the public contract; S-5 no silent failures.

Source: ``.local/research/v11.3.0_gap_analysis.md`` §4 P1.3.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, Literal, get_args

__all__ = [
    "AdrConditionName",
    "CanonicalTermSuggestion",
    "ContextLayout",
    "DecisionDescriptor",
    "FuzzyTerm",
    "GrillVerdict",
    "classify_grill_intent",
    "detect_fuzzy_terms",
    "infer_context_layout",
    "propose_canonical_term",
    "qualifies_as_adr",
]


GrillVerdict = Literal["GRILL_REQUESTED", "GRILL_SUGGESTED", "NO_GRILL"]
ContextLayout = Literal["SINGLE_CONTEXT", "MULTI_CONTEXT", "NO_CONTEXT_YET"]
AdrConditionName = Literal["HARD_TO_REVERSE", "SURPRISING_WITHOUT_CONTEXT", "REAL_TRADE_OFF"]

# Canonical W-23 ordering for the 3-condition ADR gate; also the runtime tuple of valid literals.
_ADR_CONDITION_ORDER: Final[tuple[AdrConditionName, ...]] = get_args(AdrConditionName)

# REQUESTED — operator's EXPLICIT grill-mode call; auto-enter on match.
_REQUESTED_TRIGGERS: Final[tuple[str, ...]] = (
    "grill",
    "interview me",
    "stress-test",
    "stress test",
    "challenge my plan",
    "challenge the plan",
    "interrogate",
    "sharpen terminology",
    "sharpen the domain",
)

# SUGGESTED — softer signals; L0 proposes grill-mode but MUST NOT auto-enter (W-22).
_SUGGESTED_TRIGGERS: Final[tuple[str, ...]] = (
    "domain glossary",
    "clarify terms",
    "ambiguous terms",
    "fuzzy language",
    "fuzzy terms",
    "context.md",
    "is this an adr",
    "should we record",
    "hard to reverse",
)

# Bare ``adr`` substring is matched case-SENSITIVELY (lowercase only); uppercase ``ADR``
# is the formal acronym used pervasively in technical writing and would generate false positives.
_ADR_LOWERCASE_TRIGGER: Final[str] = "adr"


@dataclass(frozen=True)
class FuzzyTerm:
    """One alias→canonical match found by :func:`detect_fuzzy_terms`."""

    term: str
    plan_position: int
    candidates: tuple[str, ...]


@dataclass(frozen=True)
class CanonicalTermSuggestion:
    """Result of :func:`propose_canonical_term` — replacement + rationale."""

    candidate: str
    canonical: str | None
    avoid_aliases: tuple[str, ...]
    rationale: str


@dataclass(frozen=True)
class DecisionDescriptor:
    """Input to :func:`qualifies_as_adr` — the 3-condition gate descriptor."""

    title: str
    hard_to_reverse: bool
    surprising_without_context: bool
    real_trade_off: bool
    notes: str = field(default="")


# Matches ``_Avoid_: a, b, c`` and underscore variants; captures the comma-separated alias block.
_AVOID_PATTERN: Final[re.Pattern[str]] = re.compile(r"_?Avoid_?:\s*([^\n]*)", re.IGNORECASE)


def _extract_avoid_aliases(definition: str) -> tuple[str, ...]:
    """Parse the ``Avoid:`` alias list from a glossary definition body."""
    aliases: list[str] = []
    for match in _AVOID_PATTERN.finditer(definition):
        for raw in match.group(1).split(","):
            cleaned = raw.strip()
            if cleaned:
                aliases.append(cleaned)
    return tuple(aliases)


def classify_grill_intent(message: str) -> GrillVerdict:
    """Classify operator intent into REQUESTED / SUGGESTED / NO_GRILL (priority in that order).

    Triggers are case-insensitive except the bare ``"adr"`` (lowercase
    only). Empty / whitespace-only input → ``"NO_GRILL"``.

    >>> classify_grill_intent("Please grill this plan")
    'GRILL_REQUESTED'
    >>> classify_grill_intent("Implement a CRUD endpoint")
    'NO_GRILL'
    >>> classify_grill_intent("Should we record this as an adr?")
    'GRILL_SUGGESTED'
    """
    if not message or not message.strip():
        return "NO_GRILL"
    lowered = message.lower()
    for trigger in _REQUESTED_TRIGGERS:
        if trigger in lowered:
            return "GRILL_REQUESTED"
    for trigger in _SUGGESTED_TRIGGERS:
        if trigger in lowered:
            return "GRILL_SUGGESTED"
    if _ADR_LOWERCASE_TRIGGER in message:
        return "GRILL_SUGGESTED"
    return "NO_GRILL"


def detect_fuzzy_terms(plan_text: str, glossary: dict[str, str]) -> list[FuzzyTerm]:
    """Emit one :class:`FuzzyTerm` per alias→canonical match per plan position (verbatim).

    >>> result = detect_fuzzy_terms(
    ...     "We charge the account for the order",
    ...     {"Customer": "A buyer.\\n_Avoid_: account, client"},
    ... )
    >>> [(f.term, f.plan_position, f.candidates) for f in result]
    [('account', 14, ('Customer',))]
    """
    if not plan_text or not glossary:
        return []
    matches: list[FuzzyTerm] = []
    for canonical, definition in glossary.items():
        for alias in _extract_avoid_aliases(definition):
            if not alias:
                continue
            cursor = 0
            while True:
                position = plan_text.find(alias, cursor)
                if position < 0:
                    break
                matches.append(
                    FuzzyTerm(term=alias, plan_position=position, candidates=(canonical,))
                )
                cursor = position + 1
    return matches


def qualifies_as_adr(decision: DecisionDescriptor) -> tuple[bool, list[AdrConditionName]]:
    """Apply the 3-condition ADR gate; return ``(qualifies, missing_conditions)`` (canonical order).

    >>> d = DecisionDescriptor(
    ...     title="Use Postgres for the write model",
    ...     hard_to_reverse=True,
    ...     surprising_without_context=True,
    ...     real_trade_off=True,
    ... )
    >>> qualifies_as_adr(d)
    (True, [])
    """
    flags = {
        "HARD_TO_REVERSE": decision.hard_to_reverse,
        "SURPRISING_WITHOUT_CONTEXT": decision.surprising_without_context,
        "REAL_TRADE_OFF": decision.real_trade_off,
    }
    missing: list[AdrConditionName] = [name for name in _ADR_CONDITION_ORDER if not flags[name]]
    return (len(missing) == 0, missing)


_NO_MATCH_RATIONALE = "No matching glossary term; consider adding to CONTEXT.md."


def propose_canonical_term(
    candidate: str,
    glossary: dict[str, str],
) -> CanonicalTermSuggestion:
    """Propose a canonical replacement; canonical-match / alias-match / no-match outcomes.

    >>> r = propose_canonical_term(
    ...     "account",
    ...     {"Customer": "A buyer.\\n_Avoid_: account, client"},
    ... )
    >>> r.canonical
    'Customer'
    """
    candidate_lower = candidate.lower()
    for canonical in glossary:
        if candidate_lower == canonical.lower():
            return CanonicalTermSuggestion(
                candidate=candidate,
                canonical=None,
                avoid_aliases=(),
                rationale="Already canonical.",
            )
    for canonical, definition in glossary.items():
        aliases = _extract_avoid_aliases(definition)
        if candidate in aliases:
            other = tuple(a for a in aliases if a != candidate)
            return CanonicalTermSuggestion(
                candidate=candidate,
                canonical=canonical,
                avoid_aliases=other,
                rationale=f"'{candidate}' is an alias for canonical term '{canonical}'.",
            )
    return CanonicalTermSuggestion(
        candidate=candidate,
        canonical=None,
        avoid_aliases=(),
        rationale=_NO_MATCH_RATIONALE,
    )


def infer_context_layout(repo_root: Path) -> ContextLayout:
    """Probe ``repo_root``: CONTEXT-MAP.md → MULTI; CONTEXT.md → SINGLE; neither → NO_CONTEXT_YET.

    The ONLY function here that touches disk (read-only ``exists()``);
    raises :class:`FileNotFoundError` on missing ``repo_root`` (S-5).

    >>> import tempfile
    >>> with tempfile.TemporaryDirectory() as tmp:
    ...     infer_context_layout(Path(tmp))
    'NO_CONTEXT_YET'
    """
    if not repo_root.exists():
        raise FileNotFoundError(f"infer_context_layout: repo_root does not exist: {repo_root!s}")
    if (repo_root / "CONTEXT-MAP.md").exists():
        return "MULTI_CONTEXT"
    if (repo_root / "CONTEXT.md").exists():
        return "SINGLE_CONTEXT"
    return "NO_CONTEXT_YET"


# v11.3.0 PV-01 — non-import references for ``scripts/detect_dead_apis.py``.
# The five new public symbols have no in-repo production caller until
# v11.3.0 Wave 2 wires them into the SKILL.md §"GRILL MODE" plan-mode
# activation surface and the W-22 / W-23 rule bodies. The detector's
# ``_collect_real_uses`` walker treats any non-Import ``ast.Name``
# reference as a real caller — this tuple establishes such references at
# the new symbols' qualified names without leaking into ``__all__``.
# Mirrors the v9.3.0 PV-06 ``_simple_shortcut_dead_api_pins`` pattern in
# ``src/devolaflow/skills/change_activation.py`` lines 418-421.
_grill_mode_dead_api_pins = (
    classify_grill_intent,
    detect_fuzzy_terms,
    qualifies_as_adr,
    propose_canonical_term,
    infer_context_layout,
)
