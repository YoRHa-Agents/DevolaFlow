"""Convergence round rule reinforcement — dispatch-level findings injection.

Converts gate findings into reinforcement rules for the next convergence
round's dispatch, enabling L3 Task Agents to receive explicit mandates
about what MUST be fixed.  Zero file I/O, platform-agnostic (Approach B).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from devolaflow.gate.models import Finding, Severity

SEVERITY_ORDER: dict[str, int] = {
    "blocker": 0,
    "critical": 1,
    "major": 2,
    "minor": 3,
    "info": 4,
}

MAX_REINFORCEMENT_RULES = 5


@dataclass(frozen=True)
class ReinforcementRule:
    """A single mandate derived from a previous round's finding."""

    id: str
    severity: Severity
    mandate: str
    file: str = ""


@dataclass(frozen=True)
class ReinforcementBlock:
    """Reinforcement block to inject into dispatch ``applicable_rules``."""

    round: int
    prior_score: float
    target_score: float
    severity_floor: Severity
    rules: tuple[ReinforcementRule, ...] = ()
    escalation_note: str = ""


def findings_to_reinforcement(
    findings: list[Finding],
    round_num: int,
    prior_score: float,
    target_score: float,
    severity_floor: Severity = "major",
) -> ReinforcementBlock:
    """Convert gate findings into a dispatch reinforcement block.

    Filters by *severity_floor*, sorts by severity, caps at
    :data:`MAX_REINFORCEMENT_RULES`, and returns a :class:`ReinforcementBlock`.
    """
    floor_order = SEVERITY_ORDER.get(severity_floor, 2)
    eligible = [f for f in findings if SEVERITY_ORDER.get(f.severity, 4) <= floor_order]
    eligible.sort(key=lambda f: SEVERITY_ORDER.get(f.severity, 4))

    rules: list[ReinforcementRule] = []
    for f in eligible[:MAX_REINFORCEMENT_RULES]:
        mandate = f"MUST fix: {f.description}"
        if f.suggestion:
            mandate += f" — {f.suggestion}"
        rules.append(
            ReinforcementRule(
                id=f.finding_id,
                severity=f.severity,
                mandate=mandate,
                file=f.location,
            )
        )

    escalation = (
        f"Round {round_num - 1} score: {prior_score:.1f}/{target_score:.1f}. "
        f"{len(rules)} violation(s) from previous round MUST be addressed."
    )

    return ReinforcementBlock(
        round=round_num,
        prior_score=prior_score,
        target_score=target_score,
        severity_floor=severity_floor,
        rules=tuple(rules),
        escalation_note=escalation,
    )


def reinforcement_to_dict(block: ReinforcementBlock) -> dict[str, Any]:
    """Serialize a :class:`ReinforcementBlock` to a plain dict for YAML."""
    return {
        "round": block.round,
        "prior_score": block.prior_score,
        "target_score": block.target_score,
        "severity_floor": block.severity_floor,
        "rules": [
            {
                "id": r.id,
                "severity": r.severity,
                "mandate": r.mandate,
                **({"file": r.file} if r.file else {}),
            }
            for r in block.rules
        ],
        "escalation_note": block.escalation_note,
    }


def merge_reinforcement_into_dispatch(
    dispatch: dict[str, Any],
    reinforcement: ReinforcementBlock,
) -> dict[str, Any]:
    """Inject reinforcement into an existing dispatch's ``applicable_rules``.

    Mutates and returns *dispatch*.  Creates ``context`` /
    ``applicable_rules`` keys when absent.
    """
    context = dispatch.setdefault("context", {})
    rules = context.setdefault("applicable_rules", {})
    rules["reinforcement"] = reinforcement_to_dict(reinforcement)
    return dispatch
