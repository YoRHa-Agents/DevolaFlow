"""Central orchestrator for lifecycle hooks.

Provides the public ``run_hooks`` entrypoint, the ``HookResult`` /
``HookViolation`` envelopes, and a thin extra-handler registry layer.

Design contract (P-05 in the v7.5.0 cycle, audit §3.C G-C1 closure):

* Each canonical event maps to exactly **one default handler** baked into
  ``_DEFAULT_HOOKS``. Defaults are immutable from the dispatcher's POV.
* Additional handlers can be registered via :func:`register_hook` and live
  in :data:`_EXTRA_REGISTRY`. They are invoked AFTER the default for the
  same event (insertion order preserved).
* Default mode is **permissive** — every violation is logged at WARNING
  level via the standard ``logging`` module (NOT ``print``) and collected
  into ``HookResult.violations``; no exception is raised.
* Strict mode (``strict=True``) re-raises the highest-severity collected
  violation (``blocker > error > warning``) AFTER all handlers complete,
  so callers see the full violation set on the result envelope before
  the raise propagates out of ``run_hooks``.

This keeps each hook module's signature uniform — ``hook(payload, *,
strict=False) -> HookResult`` — so they can be invoked directly OR
through ``run_hooks``. When invoked through ``run_hooks`` the dispatcher
threads ``strict=False`` to every handler regardless and applies the
strict-raise policy ONCE at aggregate time, ensuring per-handler logs
are emitted exactly once and the strict raise carries the across-handler
top-severity violation rather than just the first handler's top.
"""

from __future__ import annotations

import copy
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

logger = logging.getLogger(__name__)

Severity = Literal["warning", "error", "blocker"]
"""Hook violation severity. Ordering: ``blocker`` > ``error`` > ``warning``."""

_SEVERITY_ORDER: dict[str, int] = {"warning": 0, "error": 1, "blocker": 2}


# Class name is intentionally `HookViolation` (not `HookViolationError`) per
# the v7.5.0 P-05 task spec / SKILL.md §"Lifecycle Hooks" public-API contract.
# The N818 ruff rule's "Error suffix" recommendation is silenced here.
class HookViolation(Exception):  # noqa: N818
    """A single lifecycle-hook constraint violation.

    Carries a stable machine-readable ``code``, a human-readable
    ``message``, a ``severity`` tag, and an optional ``context`` dict
    with structured details (file path, expected/actual values, etc.).

    Subclassing :class:`Exception` lets callers ``raise`` the violation
    directly under strict mode while still allowing it to be aggregated
    into a :class:`HookResult` under permissive mode.
    """

    __slots__ = ("code", "message", "severity", "context")

    def __init__(
        self,
        code: str,
        message: str,
        severity: Severity = "error",
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.severity: Severity = severity
        self.context: dict[str, Any] = dict(context) if context else {}

    def __str__(self) -> str:
        return f"[{self.severity}] {self.code}: {self.message}"

    def __repr__(self) -> str:
        return (
            f"HookViolation(code={self.code!r}, message={self.message!r}, "
            f"severity={self.severity!r}, context={self.context!r})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, HookViolation):
            return NotImplemented
        return (
            self.code == other.code
            and self.message == other.message
            and self.severity == other.severity
            and self.context == other.context
        )

    def __hash__(self) -> int:
        return hash((self.code, self.message, self.severity))


@dataclass
class HookResult:
    """Aggregate outcome of running all handlers for a single event.

    ``passed`` is ``True`` iff zero violations were collected. ``severity``
    returns the highest severity in the violation list (or ``None`` when
    the result is clean). ``metadata`` is a free-form dict the dispatcher
    uses for diagnostic notes (e.g. ``{"reason": "no handlers registered"}``).
    """

    event: str
    passed: bool = True
    violations: list[HookViolation] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def severity(self) -> Severity | None:
        """Highest severity across :attr:`violations`, or ``None`` if clean."""
        if not self.violations:
            return None
        return max(
            (v.severity for v in self.violations),
            key=lambda s: _SEVERITY_ORDER[s],
        )

    def top_violation(self) -> HookViolation | None:
        """Return the highest-severity violation, or ``None`` if clean."""
        if not self.violations:
            return None
        return max(self.violations, key=lambda v: _SEVERITY_ORDER[v.severity])


HookHandler = Callable[..., HookResult]
"""Hook handler signature: ``handler(payload, *, strict=False) -> HookResult``."""


# Default event → handler map populated by ``__init__`` after the three
# hook modules import. This avoids circular imports while keeping a
# single canonical source of event names.
_DEFAULT_HOOKS: dict[str, HookHandler] = {}

# Mutable extra-handler registry — for plugin-style additions on top of
# the defaults. Tests use :func:`clear_hooks` to reset this layer without
# disturbing :data:`_DEFAULT_HOOKS`.
_EXTRA_REGISTRY: dict[str, list[HookHandler]] = {}

# v11.0.0 PV-02 D-Q-3: event-name alias map. Each entry maps an OLD
# (legacy) event name → its NEW canonical name. PURE-ALIAS — both names
# accept ``register_hook`` / ``clear_hooks`` / ``list_handlers`` /
# ``run_hooks`` calls, and both route to the SAME underlying handler
# list (single source of truth in ``_DEFAULT_HOOKS`` /
# ``_EXTRA_REGISTRY`` keyed by the canonical name). This preserves
# byte-identical observable behaviour for callers that hard-coded the
# OLD string while admitting the NEW canonical taxonomy
# (``pre_*`` / ``post_*`` / ``check_*``) per D-Q-3 §2.
#
# 1-cycle alias schedule (per `references/env-flags.md` lifecycle event
# taxonomy section + the v11.0.0 retrospective §3 deferred-items
# telegraph): OLD names removed at v12.0.0+ once operators have had 1
# full cycle of migration runway. The keys here are the OLD names that
# stay PURE-ALIAS for v11.x; v12.0.0 cycle plan SI-1 evaluates removal.
_EVENT_ALIASES: dict[str, str] = {}


def _canonical(event: str) -> str:
    """Resolve an event name through the alias map.

    Returns the canonical name when *event* is an alias, otherwise
    returns *event* unchanged. The alias resolution is single-step (an
    alias does not chain through multiple aliases) — callers that want
    multi-hop alias chains must register intermediate canonical names
    explicitly.
    """
    return _EVENT_ALIASES.get(event, event)


def _alias_event(old: str, new: str) -> None:
    """Register *old* as a PURE-ALIAS for *new* (v11.0.0 PV-02 D-Q-3).

    Internal helper used by :mod:`devolaflow.lifecycle.__init__` to wire
    the v11.0.0 PV-02 lifecycle-event taxonomy rename. After the alias
    is registered, every ``register_hook(old, ...)`` /
    ``register_hook(new, ...)`` call appends to the SAME handler list
    (canonical-keyed), and every ``run_hooks(old, ...)`` /
    ``run_hooks(new, ...)`` call dispatches the SAME list. This makes
    the rename a PURE-ALIAS with byte-identical observable behaviour
    for both names.

    Idempotent: re-registering the same (old, new) pair is a no-op.
    Re-pointing an existing alias to a different canonical name raises
    ``ValueError`` because that would silently break callers depending
    on the original alias resolution.
    """
    if old == new:
        # Self-alias is a no-op (the event would already canonicalise to
        # itself); avoid polluting the alias map.
        return
    existing = _EVENT_ALIASES.get(old)
    if existing is not None and existing != new:
        raise ValueError(
            f"event alias conflict: {old!r} already aliases to "
            f"{existing!r}; refusing to silently re-point to {new!r}"
        )
    _EVENT_ALIASES[old] = new


def _set_default_hook(event: str, handler: HookHandler) -> None:
    """Register the canonical default handler for an event.

    Internal helper used by :mod:`devolaflow.lifecycle.__init__` to wire
    the three documented hooks. Not part of the public API; tests should
    use :func:`register_hook` for additional handlers.

    The *event* name is resolved through the alias map per
    :func:`_canonical` so registering against an alias name correctly
    populates the canonical slot.
    """
    _DEFAULT_HOOKS[_canonical(event)] = handler


def register_hook(event: str, handler: HookHandler) -> None:
    """Register an additional handler for *event*.

    Additional handlers run AFTER the default (if any) in insertion
    order. To replace the default, callers should also call
    :func:`clear_hooks` for the event first; default handlers are
    re-installable via :func:`reset_to_defaults` or by re-importing the
    package module.

    The *event* name is resolved through the alias map per
    :func:`_canonical`. Registering against ``"file_write"`` (OLD) and
    against ``"check_file_write"`` (NEW canonical) appends to the SAME
    underlying handler list — both names dispatch identically.
    """
    _EXTRA_REGISTRY.setdefault(_canonical(event), []).append(handler)


def unregister_hook(event: str, handler: HookHandler) -> bool:
    """Remove every occurrence of *handler* from *event*'s extras list.

    v15.0.0 (G-038 flip 3) — the per-handler opt-out surface for
    default-wired extras (e.g. ``reject_subagent_banner_emission``,
    auto-wired since v15.0.0). Unlike :func:`clear_hooks` (which strips
    ALL extras for an event), this removes ONLY the given handler so
    sibling extras (``validate_owned_files``,
    ``reject_subagent_quality_score``) stay registered.

    Default handlers installed via :func:`_set_default_hook` are NEVER
    removed by this function. The *event* name is resolved through the
    alias map per :func:`_canonical`.

    Returns ``True`` when at least one registration was removed,
    ``False`` when the handler was not registered (no-op — callers may
    treat a ``False`` return as "already opted out").
    """
    extras = _EXTRA_REGISTRY.get(_canonical(event))
    if not extras or handler not in extras:
        return False
    extras[:] = [h for h in extras if h is not handler]
    return True


def clear_hooks(event: str | None = None) -> None:
    """Clear the extra-handler registry (default handlers untouched).

    Pass ``event=None`` to clear all events; pass an event name to
    clear only that event's extras. Default handlers installed via
    :func:`_set_default_hook` are NEVER cleared by this function.

    The *event* name is resolved through the alias map per
    :func:`_canonical`.
    """
    if event is None:
        _EXTRA_REGISTRY.clear()
        return
    _EXTRA_REGISTRY.pop(_canonical(event), None)


def list_handlers(event: str) -> tuple[HookHandler, ...]:
    """Return all handlers (default first, then extras) for *event*.

    The *event* name is resolved through the alias map per
    :func:`_canonical` so OLD aliases see the same handler list as
    NEW canonical names.
    """
    canonical_event = _canonical(event)
    handlers: list[HookHandler] = []
    default = _DEFAULT_HOOKS.get(canonical_event)
    if default is not None:
        handlers.append(default)
    handlers.extend(_EXTRA_REGISTRY.get(canonical_event, []))
    return tuple(handlers)


def registered_events() -> tuple[str, ...]:
    """Return the union of events with at least one handler.

    Includes BOTH the canonical event names (the ``_DEFAULT_HOOKS`` /
    ``_EXTRA_REGISTRY`` keys) AND the alias names registered via
    :func:`_alias_event`. Both surfaces appear in the introspection
    output because callers may hold references to either name and
    expect to see "their" event in the registered list.
    """
    canonical = set(_DEFAULT_HOOKS) | set(_EXTRA_REGISTRY)
    aliased = {alias for alias, target in _EVENT_ALIASES.items() if target in canonical}
    return tuple(sorted(canonical | aliased))


def run_hooks(
    event: str,
    payload: dict[str, Any],
    *,
    strict: bool = False,
) -> HookResult:
    """Dispatch *event* with *payload* through every registered handler.

    Handlers are invoked in deterministic order: the default handler for
    *event* (if registered) runs first, followed by extras in insertion
    order. Each handler is invoked with ``strict=False`` regardless of
    the caller's request — the strict-raise decision is centralised here
    so handlers don't double-log and the raise carries the cross-handler
    top-severity violation.

    The *event* name is resolved through :func:`_canonical` (via
    :func:`list_handlers`) so OLD alias names dispatch through the SAME
    handler list as NEW canonical names per the v11.0.0 PV-02 D-Q-3
    alias schedule. The aggregate ``HookResult.event`` field carries
    the alias name as supplied by the caller (NOT the canonical) so
    existing log lines and test assertions that pin the event-name
    string continue to match byte-identically.

    Returns
    -------
    HookResult
        Aggregate result with ``passed=False`` and a populated
        ``violations`` list when any handler reported a violation.
        When no handlers are registered for *event*, returns a clean
        result with ``metadata["reason"] == "no handlers registered"``.

    Raises
    ------
    HookViolation
        Only when ``strict=True`` AND at least one violation was
        collected. The raised violation is the highest severity across
        all handlers (``blocker`` > ``error`` > ``warning``); the
        full ``violations`` list is also accessible via the in-progress
        ``HookResult`` if needed by callers wrapping the raise.
    """
    handlers = list_handlers(event)
    aggregate = HookResult(event=event)

    if not handlers:
        aggregate.metadata["reason"] = "no handlers registered"
        return aggregate

    for handler in handlers:
        # Always invoke handlers in permissive mode — the aggregator
        # below decides whether to escalate to a raise based on the
        # caller's `strict` flag and the merged violation set. Each handler
        # receives an isolated copy so lifecycle hooks cannot mutate the
        # dispatch payload bytes.
        handler_name = getattr(
            handler,
            "__qualname__",
            getattr(handler, "__name__", type(handler).__name__),
        )
        try:
            result = handler(copy.deepcopy(payload), strict=False)
            if not isinstance(result, HookResult):
                raise TypeError(f"handler returned {type(result).__name__}, expected HookResult")
            aggregate.violations.extend(result.violations)
            for key, value in result.metadata.items():
                aggregate.metadata.setdefault(key, copy.deepcopy(value))
            if not result.passed:
                aggregate.passed = False
        except Exception as exc:  # noqa: BLE001 - isolate buggy extensions
            message = f"hook handler {handler_name!r} raised {type(exc).__name__}: {exc}"
            violation = HookViolation(
                "LIFECYCLE_HANDLER_EXCEPTION",
                message,
                severity="error",
                context={"handler": handler_name, "exception": type(exc).__name__},
            )
            logger.warning("[hook=%s] isolating handler failure: %s", event, message)
            aggregate.violations.append(violation)
            aggregate.passed = False
            aggregate.metadata.setdefault("handler_errors", []).append(
                {
                    "handler": handler_name,
                    "exception": type(exc).__name__,
                    "message": str(exc),
                }
            )

    if not aggregate.passed and strict:
        top = aggregate.top_violation()
        # ``top`` is guaranteed non-None here (passed is False ⇒ at least
        # one violation was collected) but keep the guard for type-checker
        # peace of mind.
        if top is not None:
            logger.error(
                "[hook=%s] strict mode raising top violation: %s",
                event,
                top,
            )
            raise top

    return aggregate


def emit_violations(event: str, violations: list[HookViolation]) -> None:
    """Log each violation at WARNING level under the lifecycle logger.

    Hook modules call this once per invocation to surface violations
    before returning their :class:`HookResult`. Centralising the log
    format here keeps log output consistent across the three default
    hooks and any future extras.
    """
    for v in violations:
        logger.warning("[hook=%s] %s", event, v)


def finalize(
    event: str,
    violations: list[HookViolation],
    *,
    strict: bool,
) -> HookResult:
    """Build a :class:`HookResult`, log violations, and optionally raise.

    Used by the three canonical hook modules so that calling them
    directly (not through :func:`run_hooks`) still respects the
    permissive-default + strict-opt-in contract.
    """
    result = HookResult(event=event, violations=list(violations), passed=not violations)
    if violations:
        emit_violations(event, violations)
        if strict:
            top = result.top_violation()
            if top is not None:
                logger.error(
                    "[hook=%s] strict mode raising top violation: %s",
                    event,
                    top,
                )
                raise top
    return result


__all__ = [
    "HookHandler",
    "HookResult",
    "HookViolation",
    "Severity",
    "clear_hooks",
    "emit_violations",
    "finalize",
    "list_handlers",
    "register_hook",
    "registered_events",
    "run_hooks",
    "unregister_hook",
]
