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


def _set_default_hook(event: str, handler: HookHandler) -> None:
    """Register the canonical default handler for an event.

    Internal helper used by :mod:`devolaflow.lifecycle.__init__` to wire
    the three documented hooks. Not part of the public API; tests should
    use :func:`register_hook` for additional handlers.
    """
    _DEFAULT_HOOKS[event] = handler


def register_hook(event: str, handler: HookHandler) -> None:
    """Register an additional handler for *event*.

    Additional handlers run AFTER the default (if any) in insertion
    order. To replace the default, callers should also call
    :func:`clear_hooks` for the event first; default handlers are
    re-installable via :func:`reset_to_defaults` or by re-importing the
    package module.
    """
    _EXTRA_REGISTRY.setdefault(event, []).append(handler)


def clear_hooks(event: str | None = None) -> None:
    """Clear the extra-handler registry (default handlers untouched).

    Pass ``event=None`` to clear all events; pass an event name to
    clear only that event's extras. Default handlers installed via
    :func:`_set_default_hook` are NEVER cleared by this function.
    """
    if event is None:
        _EXTRA_REGISTRY.clear()
        return
    _EXTRA_REGISTRY.pop(event, None)


def list_handlers(event: str) -> tuple[HookHandler, ...]:
    """Return all handlers (default first, then extras) for *event*."""
    handlers: list[HookHandler] = []
    default = _DEFAULT_HOOKS.get(event)
    if default is not None:
        handlers.append(default)
    handlers.extend(_EXTRA_REGISTRY.get(event, []))
    return tuple(handlers)


def registered_events() -> tuple[str, ...]:
    """Return the union of events with at least one handler."""
    return tuple(sorted(set(_DEFAULT_HOOKS) | set(_EXTRA_REGISTRY)))


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
        # caller's `strict` flag and the merged violation set.
        result = handler(payload, strict=False)
        aggregate.violations.extend(result.violations)
        if not result.passed:
            aggregate.passed = False

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
]
