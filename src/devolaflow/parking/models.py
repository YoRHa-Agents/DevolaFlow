"""Frozen record types and the risk lifecycle FSM (v24.0.0).

Design ref: `.local/research/v24.0.0_design_adr.md` §4.

The lifecycle deliberately separates two things the pre-v24 practice mixed:
a risk's own state (does it still threaten the work?) and whether a human
decision is outstanding. "Needs a decision" is a *reference* into the
judgment ledger, never a risk state, so a risk can keep being worked while
one of its open questions waits for the operator.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Final


class RiskState(StrEnum):
    """The six states a parked risk may occupy."""

    OPEN = "open"
    PARKED = "parked"
    ACTIVE = "active"
    MITIGATING = "mitigating"
    CLOSED = "closed"
    ARCHIVED = "archived"


class Severity(StrEnum):
    """Severity vocabulary shared with the repository's finding grades."""

    BLOCKER = "blocker"
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"


#: Legal transitions. ``closed`` may reopen because a risk can recur;
#: ``archived`` is terminal because the file has been relocated by compact
#: and reopening it would leave the mapping ledger describing a moved file
#: that came back.
STATE_TRANSITIONS: Final[dict[RiskState, frozenset[RiskState]]] = {
    RiskState.OPEN: frozenset(
        {RiskState.PARKED, RiskState.ACTIVE, RiskState.MITIGATING, RiskState.CLOSED}
    ),
    RiskState.PARKED: frozenset({RiskState.ACTIVE, RiskState.MITIGATING, RiskState.CLOSED}),
    RiskState.ACTIVE: frozenset({RiskState.PARKED, RiskState.MITIGATING, RiskState.CLOSED}),
    RiskState.MITIGATING: frozenset({RiskState.ACTIVE, RiskState.CLOSED}),
    RiskState.CLOSED: frozenset({RiskState.ARCHIVED, RiskState.ACTIVE}),
    RiskState.ARCHIVED: frozenset(),
}

#: States whose risks still demand attention in the generated index.
LIVE_STATES: Final[frozenset[RiskState]] = frozenset(
    {RiskState.OPEN, RiskState.PARKED, RiskState.ACTIVE, RiskState.MITIGATING}
)

RISK_ID_RE: Final[re.Pattern[str]] = re.compile(r"^RISK-\d{3,}$")
JUDGMENT_ID_RE: Final[re.Pattern[str]] = re.compile(r"^J-\d{3,}$")

RISK_INDEX_MARKER: Final[str] = "<!-- devolaflow: generated risk parking index -->"
JUDGE_VIEW_MARKER: Final[str] = "<!-- devolaflow: generated judgment view -->"

#: Soft/hard token budgets for the parking surface, mirroring the C-9 table.
#: Splitting one bloated ledger into many files only helps if each file is
#: itself bounded; otherwise the bloat simply relocates.
PARKING_ARTIFACT_BUDGETS: Final[dict[str, tuple[int, int]]] = {
    "risk": (500, 1000),
    "INDEX.md": (600, 1200),
    "judge.md": (800, 1600),
}


class ParkingError(RuntimeError):
    """Raised for invalid parking input or an illegal lifecycle transition."""


@dataclass(frozen=True)
class Risk:
    """One parked risk: structured header plus free-form Markdown body."""

    id: str
    title: str
    state: RiskState
    severity: Severity
    trigger: str
    disposition: str
    opened_at: str
    updated_at: str
    judgment_refs: tuple[str, ...] = ()
    legacy_id: str | None = None
    body: str = ""

    @property
    def live(self) -> bool:
        """Return whether this risk still belongs in the active index."""

        return self.state in LIVE_STATES

    def frontmatter(self) -> dict[str, Any]:
        """Return the ordered mapping persisted as the file's frontmatter."""

        data: dict[str, Any] = {
            "id": self.id,
            "title": self.title,
            "state": self.state.value,
            "severity": self.severity.value,
            "trigger": self.trigger,
            "disposition": self.disposition,
            "opened_at": self.opened_at,
            "updated_at": self.updated_at,
            "judgment_refs": list(self.judgment_refs),
        }
        if self.legacy_id is not None:
            data["legacy_id"] = self.legacy_id
        return data


@dataclass(frozen=True)
class Judgment:
    """One row of the append-only judgment ledger.

    A row with ``decision is None`` is a pending question. Answering it does
    not edit the row: a new row is appended whose ``supersedes`` cites the
    question. The ledger is therefore a complete decision history that can be
    replayed, and it is never compacted.
    """

    sequence: int
    id: str
    question: str
    subject: str
    raised_at: str
    decision: str | None = None
    decided_at: str | None = None
    supersedes: str | None = None

    @property
    def settled(self) -> bool:
        """Return whether this row carries an actual decision."""

        return self.decision is not None


@dataclass(frozen=True)
class ParkingEvent:
    """One row of the append-only event ledger."""

    sequence: int
    event: str
    subject: str
    detail: str
    timestamp: str


EVENT_RISK_OPENED: Final[str] = "risk_opened"
EVENT_RISK_STATE_CHANGED: Final[str] = "risk_state_changed"
EVENT_RISK_UPDATED: Final[str] = "risk_updated"
EVENT_QUESTION_RAISED: Final[str] = "question_raised"
EVENT_JUDGMENT_RECORDED: Final[str] = "judgment_recorded"
EVENT_RISK_ARCHIVED: Final[str] = "risk_archived"
EVENT_COMPACT_APPLIED: Final[str] = "compact_applied"

EVENT_NAMES: Final[frozenset[str]] = frozenset(
    {
        EVENT_RISK_OPENED,
        EVENT_RISK_STATE_CHANGED,
        EVENT_RISK_UPDATED,
        EVENT_QUESTION_RAISED,
        EVENT_JUDGMENT_RECORDED,
        EVENT_RISK_ARCHIVED,
        EVENT_COMPACT_APPLIED,
    }
)


@dataclass(frozen=True)
class ParkingSnapshot:
    """A consistent read of every parking surface at one point in time."""

    risks: tuple[Risk, ...] = ()
    judgments: tuple[Judgment, ...] = ()
    events: tuple[ParkingEvent, ...] = field(default=())

    @property
    def pending(self) -> tuple[Judgment, ...]:
        """Return questions that no later row has answered."""

        answered = {row.supersedes for row in self.judgments if row.settled and row.supersedes}
        return tuple(row for row in self.judgments if not row.settled and row.id not in answered)

    @property
    def settled(self) -> tuple[Judgment, ...]:
        """Return decisions in ledger order."""

        return tuple(row for row in self.judgments if row.settled)


def validate_transition(current: RiskState, target: RiskState) -> None:
    """Raise :class:`ParkingError` unless the transition is in the FSM."""

    if target not in STATE_TRANSITIONS[current]:
        allowed = ", ".join(sorted(state.value for state in STATE_TRANSITIONS[current])) or "none"
        raise ParkingError(
            f"illegal risk transition {current.value} -> {target.value}; allowed: {allowed}"
        )


__all__ = [
    "EVENT_COMPACT_APPLIED",
    "EVENT_JUDGMENT_RECORDED",
    "EVENT_NAMES",
    "EVENT_QUESTION_RAISED",
    "EVENT_RISK_ARCHIVED",
    "EVENT_RISK_OPENED",
    "EVENT_RISK_STATE_CHANGED",
    "EVENT_RISK_UPDATED",
    "JUDGE_VIEW_MARKER",
    "JUDGMENT_ID_RE",
    "LIVE_STATES",
    "PARKING_ARTIFACT_BUDGETS",
    "RISK_ID_RE",
    "RISK_INDEX_MARKER",
    "STATE_TRANSITIONS",
    "Judgment",
    "ParkingError",
    "ParkingEvent",
    "ParkingSnapshot",
    "Risk",
    "RiskState",
    "Severity",
    "validate_transition",
]
