"""Subagent-pattern selection heuristic (v11.4.0 cycle, prep for v12.0.0).

Codifies the philschmid 4-pattern subagent taxonomy — **Inline Tool**,
**Fan-Out**, **Agent Pool**, **Teams** — as pure-function selection
heuristics for L0 / L1 / L2 dispatchers. Reframes (subagent-lifecycle
lens) the same architectural axis DevolaFlow already maps via the v7.x
anthropic-coordination-blog mapping in
``workflow-system/agent/references/execution-protocol.md`` §7.3. Cited
(forward-defined) by workflow rule **W-24** ("Subagent Pattern
Selection") authored in v11.4.0 Wave 2 alongside the new Tier-2
reference ``workflow-system/agent/references/subagent-patterns.md``.

Design (mirrors :mod:`devolaflow.skills.change_activation` and
:mod:`devolaflow.skills.grill_mode`): pure functions, zero filesystem
I/O at import time; **R5 strict default-OFF** natural-language
activation per W-20 reuse-first env-flag policy (NO new
``DEVOLAFLOW_*`` flag — env-flag count stays at 8 per v11.3.0
baseline); composes with — but does NOT import — :mod:`grill_mode`
(orthogonal axes per W-20: pattern selection is the AGENT-to-AGENT
dispatch shape; grill mode is the HUMAN-facing interview pattern);
REUSES :data:`Complexity` from :mod:`change_activation` (single
source of truth per A-5 SSOT); literal verdicts are the public
contract (changing any value is a release blocker); invalid inputs
raise :class:`ValueError` with verbatim messages per S-5 (no silent
coercion).

Source: ``.local/research/v11.4.0_subagent_pattern_analysis.md`` §6
P1.2 + §5. Upstream taxonomy: ``https://www.philschmid.de/subagent-patterns-2026``.
"""

from __future__ import annotations

from typing import Final, Literal, get_args

from devolaflow.skills.change_activation import Complexity

__all__ = [
    "ModelTier",
    "PatternVerdict",
    "forbidden_pattern_rationale",
    "select_pattern",
    "validate_inputs",
]


# Literal types are the public contract; the runtime tuples below derive
# from them via :func:`typing.get_args` so adding a new verdict / tier
# requires editing exactly one Literal alias (single-source-of-truth per
# A-5 spirit; mirrors change_activation.py lines 80-96).
PatternVerdict = Literal["INLINE", "FAN_OUT", "AGENT_POOL_FORWARD", "TEAMS_FORBIDDEN"]
ModelTier = Literal["small", "balanced", "frontier"]


_VALID_PATTERN_VERDICTS: Final[tuple[str, ...]] = get_args(PatternVerdict)
_VALID_MODEL_TIERS: Final[tuple[str, ...]] = get_args(ModelTier)
# REUSE the change_activation Complexity tuple via :func:`get_args` so the
# two modules stay structurally synchronised — a future addition of a 5th
# complexity tier in change_activation.py automatically propagates here.
_VALID_COMPLEXITIES: Final[tuple[str, ...]] = get_args(Complexity)


# Single canonical string for the Pattern 4 (Teams) rejection so any
# future edit to the wording happens in exactly one place. Mentions:
# "P5", "shared state", "cross-agent messaging", "Soul-level invariant",
# and the W-21 reversal pathway, per the v11.4.0 PV-01 design contract.
_TEAMS_FORBIDDEN_RATIONALE: Final[str] = (
    "Pattern 4 (Teams) is permanently NOT SUPPORTED in DevolaFlow. The "
    "Soul-level invariant P5 ('Artifacts as Contracts') explicitly forbids "
    "cross-agent messaging and shared state between subagents. Per "
    "repo-governance.mdc §A-1 P5: 'Layers communicate through artifact "
    "files, not shared memory or conversation history. ... No bidirectional "
    "shared state.' This is a permanent architectural commitment; future "
    "overturn requires SI-1 + ADR + W-21 cadence + SI-3 §3.2 ≥ 9.5/10."
)


def validate_inputs(
    complexity: Complexity,
    model_tier: ModelTier,
    task_count: int,
) -> None:
    """Raise :class:`ValueError` on invalid inputs (S-5 — no silent coercion).

    >>> validate_inputs("STANDARD", "balanced", 3) is None
    True
    """
    if complexity not in _VALID_COMPLEXITIES:
        raise ValueError(
            f"validate_inputs: complexity {complexity!r} is not one of {_VALID_COMPLEXITIES}"
        )
    if model_tier not in _VALID_MODEL_TIERS:
        raise ValueError(
            f"validate_inputs: model_tier {model_tier!r} is not one of {_VALID_MODEL_TIERS}"
        )
    if task_count < 1:
        raise ValueError(f"validate_inputs: task_count must be >= 1, got {task_count!r}")


def select_pattern(
    complexity: Complexity,
    model_tier: ModelTier,
    task_count: int,
    parallel_independence: bool,
    persistent_state_needed: bool = False,
) -> PatternVerdict:
    """Select the philschmid pattern that best fits the wave shape.

    Decision rule (verbatim from gap analysis §5.2):

    * ``persistent_state_needed`` AND ``model_tier == "frontier"`` AND
      ``complexity in {"STANDARD", "COMPLEX"}`` → ``AGENT_POOL_FORWARD``
      (Pattern 3 forward-compat; v11.4.0 reference-only).
    * ``persistent_state_needed`` else → ``INLINE`` (under-resourced
      downgrade to Pattern 1).
    * ``task_count >= 2`` AND ``parallel_independence`` → ``FAN_OUT``
      (Pattern 2 — L2 wave dispatch with disjoint owned files).
    * else → ``INLINE`` (Pattern 1 — single L3 dispatch via ``Task``).

    **Never returns** ``"TEAMS_FORBIDDEN"`` — that verdict is reserved
    for :func:`forbidden_pattern_rationale` (operator-education path).
    Raises :class:`ValueError` per :func:`validate_inputs`.

    >>> select_pattern("SIMPLE", "balanced", 1, False)
    'INLINE'
    >>> select_pattern("STANDARD", "balanced", 3, True)
    'FAN_OUT'
    >>> select_pattern("STANDARD", "frontier", 2, False, persistent_state_needed=True)
    'AGENT_POOL_FORWARD'
    """
    validate_inputs(complexity, model_tier, task_count)

    if persistent_state_needed:
        if model_tier == "frontier" and complexity in ("STANDARD", "COMPLEX"):
            return "AGENT_POOL_FORWARD"
        return "INLINE"

    if task_count >= 2 and parallel_independence:
        return "FAN_OUT"

    return "INLINE"


def forbidden_pattern_rationale(pattern: PatternVerdict) -> str | None:
    """Return rationale string for ``"TEAMS_FORBIDDEN"``; ``None`` for other verdicts.

    Operator-education path: only Pattern 4 (``"TEAMS_FORBIDDEN"``)
    yields a non-None rationale — Patterns 1 and 2 are ADOPT-already-
    native and Pattern 3 is forward-compat. Raises :class:`ValueError`
    on unrecognised :data:`PatternVerdict` literal (S-5).

    >>> rationale = forbidden_pattern_rationale("TEAMS_FORBIDDEN")
    >>> "P5" in rationale and "shared state" in rationale
    True
    >>> forbidden_pattern_rationale("INLINE") is None
    True
    """
    if pattern not in _VALID_PATTERN_VERDICTS:
        raise ValueError(
            f"forbidden_pattern_rationale: pattern {pattern!r} is not one of "
            f"{_VALID_PATTERN_VERDICTS}"
        )
    if pattern == "TEAMS_FORBIDDEN":
        return _TEAMS_FORBIDDEN_RATIONALE
    return None


# v11.4.0 PV-01 — non-import references for ``scripts/detect_dead_apis.py``.
# The three new public functions have no in-repo production caller until
# v12.0.0 wires them into the dispatcher pre-flight (per the gap-analysis
# §7 NEST-vs-APPEND pre-staging recommendation). Mirrors the v11.3.0 PV-01
# ``_grill_mode_dead_api_pins`` pattern in
# ``src/devolaflow/skills/grill_mode.py`` lines 274-280.
_subagent_pattern_dead_api_pins = (
    select_pattern,
    validate_inputs,
    forbidden_pattern_rationale,
)
