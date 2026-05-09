"""Tests for the v11.4.0 PV-01 subagent-pattern selection module.

Pins the public contract of :mod:`devolaflow.skills.subagent_pattern`
per the v11.4.0 gap analysis §6 P1.2 (file-level scope of the new
module) and §6 P1.3 (the test suite this file implements).

The module codifies the upstream philschmid 4-pattern subagent
taxonomy (``https://www.philschmid.de/subagent-patterns-2026``) as
3 pure-function entrypoints + 2 public Literal type aliases. This
test file pins:

1. :func:`select_pattern` — operator-facing decision rule mapping
   ``(complexity, model_tier, task_count, parallel_independence,
   persistent_state_needed)`` to one of three verdicts (INLINE,
   FAN_OUT, AGENT_POOL_FORWARD); never returns TEAMS_FORBIDDEN.
2. :func:`validate_inputs` — S-5 explicit-error contract for invalid
   inputs (no silent coercion).
3. :func:`forbidden_pattern_rationale` — operator-education path that
   surfaces the P5 + Soul-level + W-21 reversal-pathway rationale for
   TEAMS_FORBIDDEN; ``None`` for the other three verdicts.
4. R5 strict: importing the module performs zero filesystem I/O.
5. The two Literal types are byte-stable public contracts whose
   string values operators rely on; reordering / renaming any value
   is a release blocker.

All ~15 tests are O(1) pure-function tests with no filesystem I/O.
The zero-IO-at-import test (mirror of
``tests/test_grill_mode.py::test_grill_mode_module_zero_io_at_import``)
is the only test that monkeypatches ``pathlib.Path.exists``; it does
so to PROVE the module never touches the filesystem at import time.
"""

from __future__ import annotations

import importlib
import sys
from typing import get_args

import pytest

from devolaflow.skills.subagent_pattern import (
    ModelTier,
    PatternVerdict,
    forbidden_pattern_rationale,
    select_pattern,
    validate_inputs,
)

# ── select_pattern — happy paths ───────────────────────────────────────


def test_select_pattern_inline_for_simple_single_task() -> None:
    """SIMPLE / 1 task / not persistent → INLINE.

    Pins gap-analysis §5.4 row "SIMPLE / 1 / n/a / any / False" →
    INLINE: a single-task simple change always falls through the
    decision tree to the final ``return "INLINE"`` (Pattern 1 — single
    L3 dispatch via the ``Task`` tool). This is the most common
    DevolaFlow path and the byte-stable legacy default.
    """
    assert select_pattern("SIMPLE", "balanced", 1, False) == "INLINE"
    assert select_pattern("SIMPLE", "small", 1, True) == "INLINE"
    assert select_pattern("TRIVIAL", "balanced", 1, False) == "INLINE"


def test_select_pattern_fan_out_for_parallel_independent_tasks() -> None:
    """STANDARD / >=2 tasks / parallel_independence=True → FAN_OUT.

    Pins gap-analysis §5.4 row "STANDARD / ≥ 2 / True / any / False"
    → FAN_OUT: an L2 wave dispatching N parallel L3 tasks (max 5 per
    wave per ``references/agent-hierarchy.md`` §5) — the canonical
    Pattern 2 use case. Verifies behaviour at task_count=2 (boundary)
    and task_count=3 (interior).
    """
    assert select_pattern("STANDARD", "balanced", 3, True) == "FAN_OUT"
    assert select_pattern("STANDARD", "balanced", 2, True) == "FAN_OUT"
    assert select_pattern("COMPLEX", "frontier", 5, True) == "FAN_OUT"


def test_select_pattern_agent_pool_forward_for_frontier_persistent() -> None:
    """STANDARD+ / frontier model / persistent_state_needed=True → AGENT_POOL_FORWARD.

    Pins gap-analysis §5.4 row "STANDARD or COMPLEX / any / any /
    frontier / True" → AGENT_POOL_FORWARD: the Pattern 3 forward-compat
    verdict (v11.4.0 reference-only; v12.0.0+ landing surface). The
    helper does NOT activate Pattern 3; it merely surfaces the verdict
    so operators can fall back to INLINE round-robin via
    ``change-driven`` workflow's ``apply ↔ verify`` convergence loop.
    """
    assert (
        select_pattern("STANDARD", "frontier", 2, False, persistent_state_needed=True)
        == "AGENT_POOL_FORWARD"
    )
    assert (
        select_pattern("COMPLEX", "frontier", 1, True, persistent_state_needed=True)
        == "AGENT_POOL_FORWARD"
    )


def test_select_pattern_downgrades_to_inline_when_under_resourced() -> None:
    """persistent_state_needed=True with small/balanced model → INLINE downgrade.

    Pins gap-analysis §5.4 row "any / any / any / small or balanced /
    True" → INLINE (downgrade — Pattern 3 needs frontier model). The
    decision rule's persistent-state branch is GUARDED on ``model_tier
    == "frontier"``; everything else falls through to ``return "INLINE"``
    inside the persistent branch (the under-resourced downgrade).
    Mirrors the article's "with a smaller or cheaper model, stay with
    Pattern 1 or 2" recommendation verbatim.
    """
    assert select_pattern("STANDARD", "small", 1, False, persistent_state_needed=True) == "INLINE"
    assert select_pattern("STANDARD", "balanced", 2, True, persistent_state_needed=True) == "INLINE"
    # Even with frontier model, SIMPLE/TRIVIAL complexity downgrades
    # because Pattern 3 is reserved for STANDARD/COMPLEX workflows.
    assert select_pattern("SIMPLE", "frontier", 1, False, persistent_state_needed=True) == "INLINE"


def test_select_pattern_inline_for_sequential_dependent_tasks() -> None:
    """STANDARD / >=2 tasks / parallel_independence=False → INLINE.

    Pins gap-analysis §5.4 row "STANDARD / ≥ 2 / False / any / False"
    → INLINE: sequential L3s (Pattern 2 needs independence). Without
    parallel-independence, the FAN_OUT branch is skipped and the
    decision falls through to ``return "INLINE"``. Operators dispatch
    these as sequential single-Task calls rather than a wave.
    """
    assert select_pattern("STANDARD", "balanced", 2, False) == "INLINE"
    assert select_pattern("COMPLEX", "frontier", 4, False) == "INLINE"


def test_select_pattern_never_returns_teams_forbidden() -> None:
    """Exhaustive sweep: select_pattern NEVER returns ``"TEAMS_FORBIDDEN"``.

    Pins the gap-analysis §5.2 invariant: TEAMS_FORBIDDEN is reserved
    for :func:`forbidden_pattern_rationale` (operator-education path),
    not for :func:`select_pattern`. This exhaustive sweep exercises
    every combination of the 5 input axes — 4 complexities × 3 model
    tiers × 3 task_counts × 2 parallel_independence × 2
    persistent_state_needed = 144 combinations — and asserts none
    returns TEAMS_FORBIDDEN. Cheap O(144) check on pure-function paths.
    """
    complexities = ("TRIVIAL", "SIMPLE", "STANDARD", "COMPLEX")
    model_tiers = ("small", "balanced", "frontier")
    task_counts = (1, 2, 5)
    bools = (False, True)

    seen: set[str] = set()
    for c in complexities:
        for m in model_tiers:
            for n in task_counts:
                for p in bools:
                    for s in bools:
                        verdict = select_pattern(c, m, n, p, persistent_state_needed=s)
                        assert verdict != "TEAMS_FORBIDDEN", (
                            f"select_pattern returned TEAMS_FORBIDDEN for "
                            f"(c={c!r}, m={m!r}, n={n!r}, p={p!r}, s={s!r})"
                        )
                        seen.add(verdict)

    # All three legitimate verdicts must be reachable through the sweep
    # (otherwise the decision rule has a dead branch).
    assert seen == {"INLINE", "FAN_OUT", "AGENT_POOL_FORWARD"}


# ── validate_inputs — S-5 explicit-error paths ─────────────────────────


def test_validate_inputs_raises_on_invalid_complexity() -> None:
    """Invalid complexity literal raises :class:`ValueError` (S-5).

    Pins the no-silent-coercion contract: passing a string outside the
    :data:`Complexity` literal set raises with a verbatim message
    naming the bad value. Mirrors
    :func:`devolaflow.skills.change_activation.classify_complexity`'s
    S-5 pattern.
    """
    with pytest.raises(ValueError, match="complexity 'BAD'"):
        validate_inputs("BAD", "balanced", 1)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="complexity"):
        validate_inputs("standard", "balanced", 1)  # type: ignore[arg-type]


def test_validate_inputs_raises_on_invalid_model_tier() -> None:
    """Invalid model_tier literal raises :class:`ValueError` (S-5).

    Pins the symmetric S-5 path for the second axis. The Literal type
    is the public contract — only the three lowercase strings ``"small"``,
    ``"balanced"``, ``"frontier"`` are valid; anything else raises.
    """
    with pytest.raises(ValueError, match="model_tier 'large'"):
        validate_inputs("STANDARD", "large", 1)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="model_tier"):
        validate_inputs("STANDARD", "Frontier", 1)  # type: ignore[arg-type]


def test_validate_inputs_raises_on_zero_or_negative_task_count() -> None:
    """task_count < 1 raises :class:`ValueError` (S-5).

    Pins the wave-decomposition invariant: every wave has at least one
    task. Zero or negative task_count is a caller bug (likely an
    off-by-one in the wave-decomposition step), not a runtime
    condition the helper should silently coerce.
    """
    with pytest.raises(ValueError, match="task_count must be >= 1"):
        validate_inputs("STANDARD", "balanced", 0)
    with pytest.raises(ValueError, match="task_count must be >= 1"):
        validate_inputs("STANDARD", "balanced", -3)


# ── forbidden_pattern_rationale — operator-education path ──────────────


def test_forbidden_pattern_rationale_explains_p5_for_teams() -> None:
    """``"TEAMS_FORBIDDEN"`` rationale cites P5 + shared state + Soul-level.

    Pins the v11.4.0 PV-01 design contract that the rationale string
    MUST mention "P5", "shared state", "cross-agent messaging",
    "Soul-level invariant", and the W-21 reversal pathway. These
    substrings are operator-quotable; downstream UI may render them
    verbatim in error toasts or in operator-facing rejection messages.
    """
    rationale = forbidden_pattern_rationale("TEAMS_FORBIDDEN")
    assert rationale is not None
    assert "P5" in rationale
    assert "shared state" in rationale
    assert "cross-agent messaging" in rationale
    assert "Soul-level" in rationale
    # W-21 reversal pathway substring per gap-analysis §6 P1.2.
    assert "SI-1" in rationale
    assert "ADR" in rationale
    assert "W-21" in rationale
    assert "9.5/10" in rationale


def test_forbidden_pattern_rationale_returns_none_for_inline() -> None:
    """``"INLINE"`` is ADOPT-already-native → rationale is ``None``.

    Pins the no-rationale verdict for Pattern 1: the helper signals
    "no rejection to explain" by returning ``None``. Callers that
    branch on ``rationale is None`` skip the operator-education UI
    cleanly without string-matching against an empty rationale.
    """
    assert forbidden_pattern_rationale("INLINE") is None


def test_forbidden_pattern_rationale_returns_none_for_fan_out() -> None:
    """``"FAN_OUT"`` is ADOPT-already-native → rationale is ``None``.

    Pins the no-rationale verdict for Pattern 2 (L2 wave dispatch).
    Symmetrical to the INLINE case.
    """
    assert forbidden_pattern_rationale("FAN_OUT") is None


def test_forbidden_pattern_rationale_returns_none_for_agent_pool_forward() -> None:
    """``"AGENT_POOL_FORWARD"`` is forward-compat → rationale is ``None``.

    Pins the no-rationale verdict for Pattern 3: forward-compat plans
    are NOT forbidden, so no rationale is emitted. Operators consuming
    this verdict are expected to fall back to INLINE round-robin via
    ``change-driven`` workflow's ``apply ↔ verify`` convergence loop
    (per gap-analysis §5.5 worked example).
    """
    assert forbidden_pattern_rationale("AGENT_POOL_FORWARD") is None


def test_forbidden_pattern_rationale_raises_on_invalid_pattern() -> None:
    """Invalid PatternVerdict literal raises :class:`ValueError` (S-5).

    Pins the symmetric S-5 path: the helper never silently returns
    ``None`` for an unrecognised verdict — that would mask caller
    bugs. Mirrors the validate_inputs S-5 pattern verbatim.
    """
    with pytest.raises(ValueError, match="pattern 'BOGUS'"):
        forbidden_pattern_rationale("BOGUS")  # type: ignore[arg-type]


# ── module-level / public-contract pins ────────────────────────────────


def test_subagent_pattern_module_zero_io_at_import(monkeypatch: pytest.MonkeyPatch) -> None:
    """R5 strict: importing :mod:`devolaflow.skills.subagent_pattern` performs no filesystem I/O.

    Companion test pattern per W-20 §"Authoring requirements": pin
    the zero-IO-at-import invariant explicitly so a future refactor
    that accidentally adds a top-level ``Path(...).exists()`` call
    (or any other filesystem read) fails this test before any
    operator notices the cache invalidation.

    Methodology mirrors
    :func:`tests.test_grill_mode.test_grill_mode_module_zero_io_at_import`:
    monkeypatch ``pathlib.Path.exists`` to record every invocation,
    pop the module from ``sys.modules``, then re-import. The import
    MUST NOT trigger any recorded calls — this module has NO
    filesystem-touching functions whatsoever (unlike grill_mode whose
    :func:`infer_context_layout` is called explicitly).
    """
    import pathlib

    sentinel: list[str] = []
    original_exists = pathlib.Path.exists

    def recording_exists(self: pathlib.Path) -> bool:
        sentinel.append(str(self))
        return original_exists(self)

    monkeypatch.setattr(pathlib.Path, "exists", recording_exists)

    sys.modules.pop("devolaflow.skills.subagent_pattern", None)
    importlib.import_module("devolaflow.skills.subagent_pattern")

    assert sentinel == [], (
        f"R5 strict: import devolaflow.skills.subagent_pattern must not call "
        f"Path.exists; got calls: {sentinel}"
    )


def test_subagent_pattern_literal_string_values_are_stable() -> None:
    """Pin the two Literal string contracts — operators rely on these values.

    Per gap-analysis §6 P1.2 the two Literal types
    (:data:`PatternVerdict` + :data:`ModelTier`) are the operator-
    quotable string contracts. Changing any literal value is a
    release blocker (it would break every downstream consumer that
    grep'd for the strings — and the v11.4.0 Wave 2 SKILL.md edits
    will quote these strings verbatim). This test enumerates every
    literal value via :func:`typing.get_args` and asserts the
    expected tuples exactly (preserving order so the runtime
    ``_VALID_*`` tuples are stable).
    """
    assert get_args(PatternVerdict) == (
        "INLINE",
        "FAN_OUT",
        "AGENT_POOL_FORWARD",
        "TEAMS_FORBIDDEN",
    )
    assert get_args(ModelTier) == ("small", "balanced", "frontier")
