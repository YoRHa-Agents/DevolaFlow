"""Lifecycle hooks package — deterministic enforcement layer (P-05).

Closes the **BLOCKER** ghost G-C1 documented in
``.local/research/v7.5.0_ghost_audit.md`` §3.C: ``workflow-system/agent/SKILL.md``
§"Lifecycle Hooks" promised three hooks (``validate_dispatch``,
``check_file_ownership``, ``test_on_complete``) with "100% compliance"
enforcement, but until v7.4.8 no implementation existed.

This package lands the missing implementations as three small modules
plus a central :func:`run_hooks` orchestrator. The hooks ship two
enforcement modes:

* **Permissive** (default): violations are collected on the returned
  :class:`HookResult` and logged at WARNING level via Python's standard
  :mod:`logging` module. No exception is raised. Suitable for advisory
  / observability use cases where the surrounding orchestrator decides
  what to do with the violations.

* **Strict** (opt-in via ``strict=True``): after all handlers run and
  violations are aggregated, the top-severity :class:`HookViolation`
  (``blocker > error > warning``) is re-raised so the caller can
  block / reject / escalate per the SKILL.md "On Violation" column.

Hooks are intentionally NOT wired into existing dispatch / write /
status-report flows by P-05 — that integration is deferred to a future
patch (likely v7.6.x) and lives outside this module's scope. P-05's
risk profile stays LOW because this package is purely additive.

Public API
----------
* :func:`run_hooks` — dispatch by event name (``pre_dispatch``,
  ``file_write``, ``task_stop``, ``format_on_edit``).
* :func:`register_hook` — add an extra handler for an event (defaults
  remain installed).
* :func:`clear_hooks` — clear extras only; defaults are immutable.
* :class:`HookResult` / :class:`HookViolation` — result/error envelopes.
* The default hooks are re-exported so callers can invoke them directly
  with the same ``(payload, *, strict=False)`` signature without going
  through :func:`run_hooks`.
"""

from __future__ import annotations

from devolaflow.lifecycle.check_envelope_append_only import (
    EVENT as _ENVELOPE_WRITE_EVENT,
)
from devolaflow.lifecycle.check_envelope_append_only import (
    check_envelope_append_only,
)
from devolaflow.lifecycle.check_file_ownership import (
    EVENT as _FILE_WRITE_EVENT,
)
from devolaflow.lifecycle.check_file_ownership import (
    check_file_ownership,
)
from devolaflow.lifecycle.dispatcher import (
    HookHandler,
    HookResult,
    HookViolation,
    Severity,
    _set_default_hook,
    clear_hooks,
    emit_violations,
    finalize,
    list_handlers,
    register_hook,
    registered_events,
    run_hooks,
)
from devolaflow.lifecycle.format_on_edit import (
    EVENT as _FORMAT_ON_EDIT_EVENT,
)
from devolaflow.lifecycle.format_on_edit import (
    format_on_edit,
)
from devolaflow.lifecycle.post_dispatch import (
    EVENT as _POST_DISPATCH_EVENT,
)
from devolaflow.lifecycle.post_dispatch import (
    post_dispatch,
)
from devolaflow.lifecycle.pre_shell_call import (
    EVENT as _PRE_SHELL_CALL_EVENT,
)
from devolaflow.lifecycle.pre_shell_call import (
    pre_shell_call,
)
from devolaflow.lifecycle.test_on_complete import (
    EVENT as _TASK_STOP_EVENT,
)
from devolaflow.lifecycle.test_on_complete import (
    test_on_complete,
)
from devolaflow.lifecycle.validate_dispatch import (
    EVENT as _PRE_DISPATCH_EVENT,
)
from devolaflow.lifecycle.validate_dispatch import (
    validate_dispatch,
)
from devolaflow.lifecycle.validate_owned_files import (
    DoctorFinding,
    DoctorReport,
    check_init_health,
    get_canonical_manifest,
    validate_owned_files,
)

# Wire the canonical defaults.
_set_default_hook(_PRE_DISPATCH_EVENT, validate_dispatch)
_set_default_hook(_POST_DISPATCH_EVENT, post_dispatch)
_set_default_hook(_FILE_WRITE_EVENT, check_file_ownership)
_set_default_hook(_TASK_STOP_EVENT, test_on_complete)
_set_default_hook(_FORMAT_ON_EDIT_EVENT, format_on_edit)
_set_default_hook(_PRE_SHELL_CALL_EVENT, pre_shell_call)
_set_default_hook(_ENVELOPE_WRITE_EVENT, check_envelope_append_only)

# Register validate_owned_files as an extra on pre_dispatch (runs after default).
register_hook(_PRE_DISPATCH_EVENT, validate_owned_files)

PRE_DISPATCH_EVENT: str = _PRE_DISPATCH_EVENT
POST_DISPATCH_EVENT: str = _POST_DISPATCH_EVENT
FILE_WRITE_EVENT: str = _FILE_WRITE_EVENT
TASK_STOP_EVENT: str = _TASK_STOP_EVENT
FORMAT_ON_EDIT_EVENT: str = _FORMAT_ON_EDIT_EVENT
PRE_SHELL_CALL_EVENT: str = _PRE_SHELL_CALL_EVENT
ENVELOPE_WRITE_EVENT: str = _ENVELOPE_WRITE_EVENT

# v8.4.4 PV-04: bumped 5 → 6 with the addition of `post_dispatch` (the
# symmetric tail event to `pre_dispatch`). The new slot is wired to a
# permissive no-op default in `post_dispatch.py`; the actual governance-
# contract handler (Soul Rule S-10) lands in PV-07 with the rule-corpus
# selectivity slice. R5 strict byte-identical: zero behaviour change with
# no extras registered (verified by
# `tests/test_dispatch_emission_runs_hooks.py`).
#
# v9.1.0 W1-02: bumped 6 → 7 with the addition of `envelope_write` per
# Soul Rule S-9 closure (handoff envelopes are append-only). The new
# slot is wired to `check_envelope_append_only.py` which blocks
# overwrites of existing handoff envelopes in STRICT mode. The new
# event is APPENDED at the END of the tuple to preserve A-2.4 /
# cache-prefix invariants — existing event positions 1-6 remain
# byte-stable.
DEFAULT_EVENTS: tuple[str, ...] = (
    PRE_DISPATCH_EVENT,
    POST_DISPATCH_EVENT,
    FILE_WRITE_EVENT,
    TASK_STOP_EVENT,
    FORMAT_ON_EDIT_EVENT,
    PRE_SHELL_CALL_EVENT,
    ENVELOPE_WRITE_EVENT,
)

__all__ = [
    "DEFAULT_EVENTS",
    "DoctorFinding",
    "DoctorReport",
    "ENVELOPE_WRITE_EVENT",
    "FILE_WRITE_EVENT",
    "FORMAT_ON_EDIT_EVENT",
    "HookHandler",
    "HookResult",
    "HookViolation",
    "POST_DISPATCH_EVENT",
    "PRE_DISPATCH_EVENT",
    "PRE_SHELL_CALL_EVENT",
    "Severity",
    "TASK_STOP_EVENT",
    "check_envelope_append_only",
    "check_file_ownership",
    "check_init_health",
    "clear_hooks",
    "emit_violations",
    "finalize",
    "format_on_edit",
    "get_canonical_manifest",
    "list_handlers",
    "post_dispatch",
    "pre_shell_call",
    "register_hook",
    "registered_events",
    "run_hooks",
    "test_on_complete",
    "validate_dispatch",
    "validate_owned_files",
]
