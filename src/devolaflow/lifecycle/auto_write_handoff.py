"""Auto-write handoff envelope hook — ``auto_write_handoff``.

Closes G-005 deferred from v9.1.0 by creating the FIRST production caller
of :meth:`devolaflow.agent_workspace.handoff.HandoffStore.write_envelope`
outside the module itself. This bridges the v9.1.0 W1-02 envelope-writer
+ S-9 enforcement work to a runtime auto-write surface fired at every
dispatch emission (cycle plan
`.cursor/plans/workspace-capability-activation_ec560bc8.plan.md` §PV-03).

Bound to the ``pre_handoff`` event by :mod:`devolaflow.lifecycle.__init__`,
and dispatched from
:meth:`devolaflow.feedback.ProposalGenerator._emit_dispatch` AFTER the
``pre_dispatch`` and ``post_dispatch`` events (Soul Rule S-10 governance
tail). At this point the dispatch payload is fully-formed +
lint-validated, making it the correct moment to consider materialising a
handoff envelope under ``.local/.agent/handoff/``.

Behaviour contract (R5 strict):

1. **Gate 1 (env-flag OFF)** — if ``DEVOLAFLOW_AGENT_WORKSPACE`` is unset
   or anything other than the literal string ``"1"``, the handler returns
   an empty :class:`HookResult` with zero filesystem I/O. This is the
   byte-identical no-op invariant: every dispatch path that does NOT
   opt-in MUST produce identical bytes to v9.1.2 behaviour.

   Per Workflow Rule W-20 (env-flag reuse-first), the flag REUSES the
   v9.1.1 PV-01 activation surface (SKILL.md §"Workspace Engagement
   (Read at Session Start)") and the v9.1.2 PV-02 activation surface
   (Architecture rule A-6 §A-6.2) — no new flag is authored.

2. **Gate 2 (no change_context)** — if ``payload["change_context"]`` is
   empty / missing, the handler returns an empty :class:`HookResult`.
   A dispatch without a ``change_context`` block has nothing to bind a
   handoff envelope to; silent no-op is the correct behaviour (NOT an
   error — many free-floating-workflow dispatches legitimately lack the
   block, and the v8.3.0 PV-05 schema explicitly documents
   ``change_context`` as OPTIONAL).

3. **Action (both gates open)** — extract ``change_id`` / ``from_layer``
   / ``to_layer`` from the payload (defensive lookup — see
   :func:`_extract_layers`), compute the next seq via
   :meth:`HandoffStore.next_seq`, build a ``TaskDispatch`` envelope, and
   call :meth:`HandoffStore.write_envelope`. The append-only ledger
   invariant (Rule S-9) is honoured — the handler never overwrites an
   existing seq.

S-5 compliance (no silent failures): every error mode is surfaced
through a typed :class:`HookViolation`:

* ``AWH001`` (severity ``error``) — payload missing required fields
  (``change_id`` / ``from_layer`` / ``to_layer``) OR
  :class:`HandoffStoreError` from the writer (schema violation).
* ``AWH002`` (severity ``warning``) — :class:`EnvelopeImmutableError`
  surfaced as a warning so the dispatch path does not abort. In strict
  mode the original :class:`EnvelopeImmutableError` is re-raised so the
  caller can decide how to recover (Rule S-9 — author seq+1).

Anything genuinely unexpected (e.g. ``OSError`` on disk full, generic
``RuntimeError``) is logged at WARNING via the lifecycle logger AND
re-raised — the handler never silently swallows.

Lazy imports of :mod:`devolaflow.agent_workspace.handoff` keep the
lifecycle package import-light and avoid a top-level circular import
(future agent_workspace observers may pull in the lifecycle package via
reporter / archive paths).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

from devolaflow.lifecycle.dispatcher import HookResult, HookViolation, finalize

EVENT: str = "pre_handoff"
ENV_FLAG: str = "DEVOLAFLOW_AGENT_WORKSPACE"
ENV_FLAG_TRUTHY: str = "1"

logger = logging.getLogger(__name__)


def _layer_lookup_table(payload: dict[str, Any]) -> list[tuple[Any, Any]]:
    """Return ordered candidate ``(from_layer, to_layer)`` pairs.

    Extracted from :func:`_extract_layers` in v10.6.0 PV-01 (D-Q-1
    row #2). Collapses the 4 distinct if/return blocks of the previous
    implementation into a single ordered list of candidate pairs from
    the 4 known sources, in priority order:

    1. ``payload["change_context"]`` — canonical layer-metadata source.
    2. ``payload["hdr"]`` — lean header.
    3. ``payload["header"]`` — verbose header.
    4. top-level ``payload["from_layer"] + ["to_layer"]``.

    Returned candidates are NOT validated — the caller filters for
    ``isinstance(..., str)`` and non-empty values. This keeps the
    helper simple (single responsibility: enumerate candidates) and
    leaves the validation policy on the orchestrator.
    """
    candidates: list[tuple[Any, Any]] = []
    for source_key in ("change_context", "hdr", "header"):
        sub = payload.get(source_key)
        if isinstance(sub, dict):
            candidates.append((sub.get("from_layer"), sub.get("to_layer")))
    candidates.append((payload.get("from_layer"), payload.get("to_layer")))
    return candidates


def _extract_layers(payload: dict[str, Any]) -> tuple[str, str]:
    """Return ``(from_layer, to_layer)`` extracted defensively from *payload*.

    Lookup order (first non-empty pair wins):

    1. ``payload["change_context"]["from_layer"]`` + ``["to_layer"]`` —
       the canonical placement when a dispatcher attaches layer metadata
       to the change-binding block.
    2. ``payload["hdr"]["from_layer"]`` + ``["to_layer"]`` — lean header.
    3. ``payload["header"]["from_layer"]`` + ``["to_layer"]`` — verbose
       header.
    4. ``payload["from_layer"]`` + ``payload["to_layer"]`` — top-level.

    Returns ``("", "")`` when no layer pair is found; the caller is
    responsible for surfacing the empty values as an AWH001 violation.

    Implementation note: per the v10.6.0 PV-01 cyclomatic-complexity
    reduction (historical analysis row #3), the candidate
    enumeration body lives in :func:`_layer_lookup_table`. Behaviour
    is byte-identical to v10.5.x baseline.
    """
    for cand_from, cand_to in _layer_lookup_table(payload):
        if isinstance(cand_from, str) and isinstance(cand_to, str) and cand_from and cand_to:
            return cand_from, cand_to
    return "", ""


def _extract_change_id(payload: dict[str, Any]) -> str:
    """Return ``payload["change_context"]["change_id"]`` or empty string."""
    cc = payload.get("change_context")
    if isinstance(cc, dict):
        change_id = cc.get("change_id")
        if isinstance(change_id, str) and change_id:
            return change_id
    return ""


def _build_dispatch_block(
    payload: dict[str, Any],
    change_context: dict[str, Any],
) -> dict[str, Any]:
    """Build the envelope's ``dispatch`` variant block from the dispatch payload.

    Honours the v8.2.4 ``schemas/agent-workspace/handoff-envelope.yaml``
    discriminated-union contract for ``TaskDispatch``: required fields
    are ``task_id`` / ``type`` / ``acceptance_criteria_ref`` /
    ``owned_files_ref``. Pulls the references from ``change_context``
    (which carries the canonical paths per the v8.3.0 PV-05 schema) and
    falls back through the lean and verbose header shapes for
    ``task_id`` / ``type``.

    The full payload is NOT embedded — that would routinely blow the
    C-9 hard-ceiling (1200 tokens per envelope) on real dispatches. The
    block is the minimal envelope contract; the L3 receiver follows the
    refs back to the canonical artefacts under ``.local/.agent/active/``.
    """
    task = payload.get("task")
    if isinstance(task, dict):
        task_id = task.get("id") or task.get("task_id") or ""
        task_type = task.get("type") or "implement"
    else:
        task_id = payload.get("task_id") or ""
        task_type = payload.get("task_type") or "implement"

    acceptance_ref = change_context.get("acceptance_ref") or ""
    owned_files_ref = change_context.get("owned_files_ref") or ""

    return {
        "task_id": str(task_id),
        "type": str(task_type),
        "acceptance_criteria_ref": str(acceptance_ref),
        "owned_files_ref": str(owned_files_ref),
    }


@dataclass(frozen=True)
class _ResolvedEnvelopeInputs:
    """Validated inputs for materialising a handoff envelope.

    Result type for :func:`_resolve_envelope_inputs` — only constructed
    when every required field (``change_id``, ``from_layer``,
    ``to_layer``) is present and non-empty AND the gates are open.
    """

    change_id: str
    from_layer: str
    to_layer: str
    change_context: dict[str, Any]


def _resolve_envelope_inputs(
    payload: dict[str, Any],
) -> tuple[_ResolvedEnvelopeInputs | None, list[HookViolation]]:
    """Validate gates + extract every input needed by :func:`_write_envelope_or_violation`.

    Extracted from :func:`auto_write_handoff` in v10.6.0 PV-01 (D-Q-1
    row #3, env-flag + payload-shape gate shard). Returns a 2-tuple:

    * ``(None, [])`` — gates closed (env-flag off, payload not a dict,
      or no ``change_context`` block). Caller routes through a clean
      :func:`finalize` with no violations.
    * ``(None, [violation])`` — gates open but a required field is
      missing. Caller routes through :func:`finalize` with the AWH001
      violation surfaced here.
    * ``(_ResolvedEnvelopeInputs, [])`` — every gate passed and every
      required field is non-empty. Caller proceeds to
      :func:`_write_envelope_or_violation`.

    R5 byte-identical: the gates + extraction sequence is verbatim
    from the pre-extraction inline body. Callers that opted-out of
    the workspace activation surface still see zero filesystem I/O
    when ``DEVOLAFLOW_AGENT_WORKSPACE`` is unset.
    """
    if os.environ.get(ENV_FLAG, "") != ENV_FLAG_TRUTHY:
        return None, []

    if not isinstance(payload, dict):
        return None, []

    change_context = payload.get("change_context")
    if not change_context or not isinstance(change_context, dict):
        return None, []

    change_id = _extract_change_id(payload)
    from_layer, to_layer = _extract_layers(payload)

    if not change_id or not from_layer or not to_layer:
        violation = HookViolation(
            code="AWH001",
            message=(
                "auto_write_handoff: payload missing required fields — "
                f"change_id={change_id!r}, from_layer={from_layer!r}, "
                f"to_layer={to_layer!r}"
            ),
            severity="error",
            context={
                "change_id": change_id,
                "from_layer": from_layer,
                "to_layer": to_layer,
            },
        )
        return None, [violation]

    return (
        _ResolvedEnvelopeInputs(
            change_id=change_id,
            from_layer=from_layer,
            to_layer=to_layer,
            change_context=change_context,
        ),
        [],
    )


def _write_envelope_or_violation(
    inputs: _ResolvedEnvelopeInputs,
    payload: dict[str, Any],
    *,
    strict: bool,
) -> list[HookViolation]:
    """Build + write a handoff envelope; return any caught domain violations.

    Extracted from :func:`auto_write_handoff` in v10.6.0 PV-01 (D-Q-1
    row #3, try/except shard). Returns:

    * ``[]`` on success (envelope materialised under
      ``.local/.agent/handoff/``).
    * ``[AWH002 warning]`` when :class:`EnvelopeImmutableError` is
      caught in permissive mode (S-9 append-only breach surfaced as a
      warning so the dispatch path does not abort).
    * ``[AWH001 error]`` when :class:`HandoffStoreError` is caught
      (schema violation from the writer).

    Raises:

    * :class:`EnvelopeImmutableError` when ``strict=True`` (S-9
      re-raise contract — the caller can decide how to recover).
    * Any other unexpected exception is logged at WARNING and
      re-raised (S-5 no-silent-failure).

    The lazy import of
    :mod:`devolaflow.agent_workspace.handoff` lives here so the
    parent function's hot path stays import-light when the gates
    are closed.
    """
    from devolaflow.agent_workspace.handoff import (
        EnvelopeImmutableError,
        HandoffStore,
        HandoffStoreError,
        make_envelope,
    )

    store = HandoffStore()

    try:
        seq = store.next_seq(inputs.change_id)
        envelope = make_envelope(
            seq=seq,
            from_layer=inputs.from_layer,
            to_layer=inputs.to_layer,
            change_id=inputs.change_id,
            envelope_kind="TaskDispatch",
            payload=_build_dispatch_block(payload, inputs.change_context),
        )
        store.write_envelope(envelope)
    except EnvelopeImmutableError as exc:
        if strict:
            raise
        return [
            HookViolation(
                code="AWH002",
                message=(
                    f"auto_write_handoff: append-only breach for change_id="
                    f"{inputs.change_id!r} — {exc}"
                ),
                severity="warning",
                context={
                    "change_id": inputs.change_id,
                    "from_layer": inputs.from_layer,
                    "to_layer": inputs.to_layer,
                },
            )
        ]
    except HandoffStoreError as exc:
        return [
            HookViolation(
                code="AWH001",
                message=(
                    f"auto_write_handoff: HandoffStoreError while writing envelope "
                    f"for change_id={inputs.change_id!r}: {exc}"
                ),
                severity="error",
                context={
                    "change_id": inputs.change_id,
                    "from_layer": inputs.from_layer,
                    "to_layer": inputs.to_layer,
                },
            )
        ]
    except Exception:
        logger.warning(
            "auto_write_handoff: unexpected exception while writing envelope "
            "for change_id=%r (re-raising per S-5 no-silent-failure)",
            inputs.change_id,
            exc_info=True,
        )
        raise

    return []


def auto_write_handoff(
    payload: dict[str, Any],
    *,
    strict: bool = False,
) -> HookResult:
    """Materialise a handoff envelope under ``.local/.agent/handoff/``.

    See module docstring for the full contract. Returns a
    :class:`HookResult` in both modes; raises only when ``strict=True``
    AND a hard failure occurred (AWH001 → finalize re-raise) OR
    :class:`EnvelopeImmutableError` was caught (re-raised verbatim so
    the original Rule S-9 recovery hint reaches the caller).

    Implementation note: per the v10.6.0 PV-01 cyclomatic-complexity
    reduction (historical analysis row #4), the env-flag /
    payload-shape gate body lives in :func:`_resolve_envelope_inputs`
    and the envelope-write try/except shard lives in
    :func:`_write_envelope_or_violation`. Behaviour is byte-identical
    to v10.5.x baseline.
    """
    inputs, gate_violations = _resolve_envelope_inputs(payload)
    if inputs is None:
        return finalize(EVENT, gate_violations, strict=strict)

    write_violations = _write_envelope_or_violation(inputs, payload, strict=strict)
    return finalize(EVENT, write_violations, strict=strict)


__all__ = ["ENV_FLAG", "ENV_FLAG_TRUTHY", "EVENT", "auto_write_handoff"]
