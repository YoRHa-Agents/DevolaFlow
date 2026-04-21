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
    validate_owned_files,
)

# Wire the canonical defaults.
_set_default_hook(_PRE_DISPATCH_EVENT, validate_dispatch)
_set_default_hook(_FILE_WRITE_EVENT, check_file_ownership)
_set_default_hook(_TASK_STOP_EVENT, test_on_complete)
_set_default_hook(_FORMAT_ON_EDIT_EVENT, format_on_edit)

# Register validate_owned_files as an extra on pre_dispatch (runs after default).
register_hook(_PRE_DISPATCH_EVENT, validate_owned_files)

PRE_DISPATCH_EVENT: str = _PRE_DISPATCH_EVENT
FILE_WRITE_EVENT: str = _FILE_WRITE_EVENT
TASK_STOP_EVENT: str = _TASK_STOP_EVENT
FORMAT_ON_EDIT_EVENT: str = _FORMAT_ON_EDIT_EVENT

DEFAULT_EVENTS: tuple[str, ...] = (
    PRE_DISPATCH_EVENT,
    FILE_WRITE_EVENT,
    TASK_STOP_EVENT,
    FORMAT_ON_EDIT_EVENT,
)

__all__ = [
    "DEFAULT_EVENTS",
    "FILE_WRITE_EVENT",
    "FORMAT_ON_EDIT_EVENT",
    "HookHandler",
    "HookResult",
    "HookViolation",
    "PRE_DISPATCH_EVENT",
    "Severity",
    "TASK_STOP_EVENT",
    "check_file_ownership",
    "clear_hooks",
    "emit_violations",
    "finalize",
    "format_on_edit",
    "list_handlers",
    "register_hook",
    "registered_events",
    "run_hooks",
    "test_on_complete",
    "validate_dispatch",
    "validate_owned_files",
]
