"""Risk parking, judgment ledger, and event ledger (v24.0.0).

Design ref: `.local/research/v24.0.0_design_adr.md`.

This package is the single owner of three surfaces that live inside one task
or change folder:

* `parking/risks/RISK-NNN.md` — one file per risk, six-state lifecycle;
* `parking/judgments.yaml` — the append-only decision ledger, and the only
  place an operator decision is stored;
* `parking/events.yaml` — the append-only provenance record.

`parking/INDEX.md` and `parking/judge.md` are generated views rendered from
those ledgers. They carry surface markers and are drift-checked, so a hand
edit is reported rather than silently becoming a competing source of truth.
"""

from __future__ import annotations

from devolaflow.parking.adopt import AdoptionPlan, apply_adoption, plan_adoption
from devolaflow.parking.models import (
    JUDGE_VIEW_MARKER,
    LIVE_STATES,
    PARKING_ARTIFACT_BUDGETS,
    RISK_INDEX_MARKER,
    STATE_TRANSITIONS,
    Judgment,
    ParkingError,
    ParkingEvent,
    ParkingSnapshot,
    Risk,
    RiskState,
    Severity,
    validate_transition,
)
from devolaflow.parking.render import render_index, render_judge_view
from devolaflow.parking.store import (
    PARKING_DIRNAME,
    ParkingStore,
)

__all__ = [
    "JUDGE_VIEW_MARKER",
    "LIVE_STATES",
    "PARKING_ARTIFACT_BUDGETS",
    "PARKING_DIRNAME",
    "RISK_INDEX_MARKER",
    "STATE_TRANSITIONS",
    "AdoptionPlan",
    "Judgment",
    "ParkingError",
    "ParkingEvent",
    "ParkingSnapshot",
    "ParkingStore",
    "Risk",
    "RiskState",
    "Severity",
    "apply_adoption",
    "plan_adoption",
    "render_index",
    "render_judge_view",
    "validate_transition",
]
