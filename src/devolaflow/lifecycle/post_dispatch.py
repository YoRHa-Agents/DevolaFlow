"""Post-dispatch lifecycle hook — ``post_dispatch``.

Symmetric tail event to :mod:`devolaflow.lifecycle.validate_dispatch` (the
``pre_dispatch`` event handler). Bound to the ``post_dispatch`` event by
:mod:`devolaflow.lifecycle.__init__` so callers can register
governance-contract validators (Soul Rule S-10), observability
collectors, or other prompt-side enforcement extensions WITHOUT touching
the canonical dispatch path.

Contract: this default handler is intentionally a **permissive no-op**.
Per the v8.4.4 PV-04 R5 strict-byte-identical invariant
(`.local/research/adr/v9-ADR-004-lifecycle-wiring-and-s10.md` §3),
adding ``post_dispatch`` to ``DEFAULT_EVENTS`` MUST NOT change the
returned dispatch payload when no extra handlers are registered. The
no-op default returns a clean :class:`HookResult` with metadata
``{"reason": "default no-op; await PV-07 governance contract handler"}``
so callers that introspect ``HookResult.metadata`` can distinguish a
genuine no-violation result from "no handlers registered" (the
dispatcher-level no-op marker).

The actual governance-contract handler (Soul-set version embedding,
rule-manifest URL embedding, reinforcement state surfacing) lands in
PV-07 with the rule-corpus selectivity slice per V-PV07-A. v8.4.4 ships
the empty slot so downstream PVs can register without re-touching the
``DEFAULT_EVENTS`` tuple.

Permissive default — never raises, never logs at WARNING level (since
there are no violations to surface). Strict mode (``strict=True``)
likewise never raises — the handler is a no-op by design.
"""

from __future__ import annotations

from typing import Any

from devolaflow.lifecycle.dispatcher import HookResult, finalize

EVENT = "post_dispatch"

_NO_OP_REASON = "default no-op; await PV-07 governance contract handler"


def post_dispatch(payload: dict[str, Any], *, strict: bool = False) -> HookResult:
    """Permissive no-op default for the ``post_dispatch`` event.

    Returns a clean :class:`HookResult` with no violations. The
    ``metadata`` dict carries the ``reason`` string so callers can
    distinguish "default ran cleanly" from "no handlers registered"
    (the dispatcher-level no-op marker).

    Per Soul Rule S-10 (v8.4.4), this slot is reserved for governance-
    contract validators. The actual implementation lands in PV-07; this
    default exists so adding the event to ``DEFAULT_EVENTS`` preserves
    the R5 byte-identical invariant (zero behaviour change without
    extras).
    """
    del payload  # accepted for handler-signature symmetry; no inspection needed.
    result = finalize(EVENT, [], strict=strict)
    result.metadata["reason"] = _NO_OP_REASON
    return result


__all__ = ["EVENT", "post_dispatch"]
