"""Unified session state package (v8.2.0 PV-03).

Re-exports the public surface of :mod:`devolaflow.session.state` so callers
can ``from devolaflow.session import SessionState, SessionStore`` without
reaching into the submodule.

PV-03 closes the ``v8.0.0_patch_plan §1 row 8`` deferral of the "Unified
session state model" / Karpathy 4.8. The state model is **additive** — every
existing public API in :mod:`devolaflow.learnings` and
:mod:`devolaflow.lifecycle` keeps its byte-stable behaviour (R5 backward
compatibility), and adoption is opt-in via the ``session_state_enabled``
toggle in ``workflow-system/agent/context_profiles.yaml`` (default
``false`` for STANDARD/RELAXED, ``true`` for STRICT/AUDIT).

See ``src/devolaflow/session/state.py`` module docstring for design
notes, acceptance criteria, and the JSON schema layout.
"""

from devolaflow.session.state import (
    DEFAULT_SESSION_STATE_PATH,
    SCHEMA_VERSION,
    LegibilitySnapshot,
    LifecycleEvent,
    SessionState,
    SessionStateError,
    SessionStore,
    default_session_state_path,
)

__all__ = [
    "DEFAULT_SESSION_STATE_PATH",
    "LegibilitySnapshot",
    "LifecycleEvent",
    "SCHEMA_VERSION",
    "SessionState",
    "SessionStateError",
    "SessionStore",
    "default_session_state_path",
]
