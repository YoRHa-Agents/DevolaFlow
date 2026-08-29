"""Pre-dispatch lifecycle hook — ``assert_layer_token_budget``.

v17.0.0 R2 (G17-B2 closure per ``.local/research/v17.0.0_r2_design.md``
§D-R2-5): ``meta.layer_token_budgets`` (A-3 context token budgets) had
no dispatch-time consumer — ``harness.telemetry.build_dispatch_record``
records overruns in the harness ledger but never raises, so an
over-budget dispatch sailed through the S-10 hook chain unchallenged.
This hook closes the gap: it estimates the dispatch payload's token
size with the EXACT measurement pipeline telemetry uses
(``estimate_tokens(stable_yaml(payload))``) and surfaces an ``ALB001``
violation when the estimate exceeds the target layer's budget from
``harness.telemetry.LAYER_TOKEN_BUDGETS`` (A-5 single owner; parity
with ``context_profiles.yaml#meta.layer_token_budgets`` is pinned by
``tests/test_layer_budget_assertion.py``).

Behaviour contract:

* **Non-mutating** — the payload is only read and serialized; the S-10
  byte-identity contract (``tests/test_dispatch_emission_runs_hooks.py``)
  is preserved.
* **Layer resolution mirrors telemetry** — the attribution order is a
  verbatim mirror of ``build_dispatch_record``'s ``_dispatch_layer``
  (explicit ``to_layer`` in ``change_context``/``hdr``/``header``, then
  top-level ``to_layer``, then top-level ``layer``, then source
  ``layer``), normalized through
  :data:`devolaflow.agent_workspace.layers.LAYER_ATTRIBUTION_ALIASES`.
  Where telemetry fails attribution (missing OR malformed layer token),
  this hook PASSES — legacy dispatches without layer info are never
  blocked (backward compatible).
* **Strict blocks, lite warns** — under the strict ``pre_dispatch``
  default at dispatch emission (v15.0.0 G-038 graduation via
  ``feedback_emit.ProposalEmitter._fire_hook_chain``), an ``ALB001``
  error violation BLOCKS the dispatch; with ``strict=False`` (lite) it
  is logged at WARNING and attached to the returned
  :class:`HookResult` (S-5 explicit error state).

Registered as an **extra** handler on the ``pre_dispatch`` event by
:mod:`devolaflow.lifecycle.__init__`, AFTER the existing extras
(``validate_owned_files`` → ``reject_subagent_quality_score`` →
``reject_subagent_banner_emission``) so content validators run first.

Source: ``.local/research/v17.0.0_gap_analysis.md`` G17-B2 +
``.local/research/v17.0.0_r2_design.md`` §D-R2-5.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any, Final

from devolaflow.agent_workspace.layers import LAYER_ATTRIBUTION_ALIASES
from devolaflow.gate.budget import check_ceremony_share
from devolaflow.harness.telemetry import (
    CONTEXT_TOKEN_FIELDS,
    LAYER_TOKEN_BUDGETS,
    measure_context_tokens,
    stable_yaml,
)
from devolaflow.lifecycle.dispatcher import HookResult, HookViolation, finalize
from devolaflow.task_adaptive_selector import estimate_tokens

EVENT = "pre_dispatch"

_VIOLATION_CODE: Final[str] = "ALB001"
_CEREMONY_VIOLATION_CODE: Final[str] = "ALB002"
CEREMONY_SHARE_WARN_THRESHOLD: Final[float] = 0.5

_VIOLATION_MESSAGE_TEMPLATE = (
    "layer_token_budget_exceeded: dispatch payload measures {measured} "
    "tokens (stable-YAML estimate, the harness telemetry pipeline) but "
    "the {layer!r} layer budget is {budget} tokens per "
    "harness.telemetry.LAYER_TOKEN_BUDGETS / "
    "context_profiles.yaml#meta.layer_token_budgets (A-3). Blocked under "
    "the strict pre_dispatch default at dispatch emission; logged as a "
    "warning in lite mode (strict=False). Trim the dispatch context per "
    "P2 Minimal Context or split the task."
)
_CEREMONY_MESSAGE_TEMPLATE = (
    "ceremony_token_share_exceeded: fixed ceremony measures {ceremony_tokens} "
    "tokens ({share:.1%}) against the {layer!r} layer budget of {budget} "
    "tokens; threshold is {threshold:.1%}. Skill, rule, and report envelope "
    "components are accounted separately. AGENTS.md corpus totals are not "
    "used as ceremony tokens."
)

logger = logging.getLogger(__name__)


def _mapping(payload: dict[str, Any], key: str) -> dict[str, Any] | None:
    value = payload.get(key)
    return value if isinstance(value, dict) else None


def _normalize_layer(value: object) -> str | None:
    """Normalize one attribution token; ``None`` when unresolvable.

    Telemetry's ``_normalize_layer`` raises on non-string / empty /
    unknown tokens (failing attribution → record not written). The
    budget assertion maps that same outcome to ``None`` → PASS, per
    the backward-compatibility contract.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    return LAYER_ATTRIBUTION_ALIASES.get(value)


def _resolve_layer(payload: dict[str, Any]) -> str | None:
    """Mirror ``harness.telemetry`` ``_dispatch_layer`` attribution order.

    First-found-wins is part of the mirror: when the highest-priority
    attribution field is present but malformed, telemetry fails
    attribution WITHOUT falling through to lower-priority fields — this
    resolver returns ``None`` (PASS) in exactly those cases.
    """
    sources = (
        _mapping(payload, "change_context"),
        _mapping(payload, "hdr"),
        _mapping(payload, "header"),
    )

    for source in sources:
        if source is not None and "to_layer" in source:
            return _normalize_layer(source["to_layer"])
    if "to_layer" in payload:
        return _normalize_layer(payload["to_layer"])

    if "layer" in payload:
        return _normalize_layer(payload["layer"])
    for source in sources:
        if source is not None and "layer" in source:
            return _normalize_layer(source["layer"])
    return None


def _payload_context_tokens(payload: dict[str, Any]) -> Mapping[str, object] | None:
    """Read explicit nested context accounting without filesystem access."""
    direct = payload.get("context_tokens")
    if isinstance(direct, Mapping):
        return direct
    for parent_key in ("context", "telemetry"):
        parent = _mapping(payload, parent_key)
        if parent is None:
            continue
        candidate = parent.get("context_tokens") or parent.get("token_accounting")
        if isinstance(candidate, Mapping):
            return candidate
    return None


def _sum_context_tokens(accounting: Mapping[str, object]) -> int | None:
    """Sum only complete accounting; missing components remain unknown."""
    if not isinstance(accounting, Mapping):
        raise ValueError("context_tokens must be a mapping")
    unknown = sorted(set(accounting) - set(CONTEXT_TOKEN_FIELDS))
    if unknown:
        raise ValueError(f"unsupported context token field(s): {', '.join(unknown)}")
    values = [accounting.get(field) for field in CONTEXT_TOKEN_FIELDS]
    if any(value is None for value in values):
        return None
    if any(type(value) is not int or value < 0 for value in values):
        raise ValueError("context token fields must be non-negative integers or null")
    return sum(values)


def _resolve_ceremony_tokens(
    payload: dict[str, Any],
    *,
    ceremony_tokens: int | None,
    context_tokens: Mapping[str, object] | None,
    skill_text: str | None,
    rule_text: str | None,
    report_envelope: Mapping[str, Any] | str | None,
) -> tuple[int | None, str]:
    text_supplied = any(value is not None for value in (skill_text, rule_text, report_envelope))
    if ceremony_tokens is not None:
        if isinstance(ceremony_tokens, bool) or not isinstance(ceremony_tokens, int):
            raise ValueError("ceremony_tokens must be a non-negative integer or null")
        if ceremony_tokens < 0:
            raise ValueError("ceremony_tokens must be a non-negative integer or null")
        return ceremony_tokens, "explicit"
    if context_tokens is not None and text_supplied:
        raise ValueError("provide context_tokens or source text, not both")
    if context_tokens is None and text_supplied:
        context_tokens = measure_context_tokens(
            skill_text=skill_text,
            rule_text=rule_text,
            report_envelope=report_envelope,
        )
    if context_tokens is None:
        context_tokens = _payload_context_tokens(payload)
    if context_tokens is None:
        return None, "missing"
    return _sum_context_tokens(context_tokens), "context_tokens"


def assert_layer_token_budget(
    payload: dict[str, Any],
    *,
    strict: bool = False,
    ceremony_tokens: int | None = None,
    context_tokens: Mapping[str, object] | None = None,
    skill_text: str | None = None,
    rule_text: str | None = None,
    report_envelope: Mapping[str, Any] | str | None = None,
    ceremony_share_threshold: float = CEREMONY_SHARE_WARN_THRESHOLD,
) -> HookResult:
    """Assert the dispatch payload fits the target layer's token budget.

    Args:
      payload: Dispatch payload (lean format per
        ``schemas/lean-dispatch.yaml``).
      strict: When ``True``, an over-budget payload raises the
        :class:`HookViolation` (block). Default ``False`` returns the
        violation attached to the :class:`HookResult` (lite — warn +
        log). The ``run_hooks`` chain always invokes handlers
        permissively and centralises the strict-raise at aggregate
        time, so the emission-site strictness
        (``ProposalEmitter(pre_dispatch_strict=True)``) governs whether
        an overrun blocks the dispatch.

    Returns:
      HookResult with an ``ALB001`` (severity ``error``) violation when
      the stable-YAML token estimate exceeds the resolved layer's
      budget; a clean result otherwise. Payloads that are not dicts,
      have no telemetry-resolvable layer attribution, or cannot be
      serialized for measurement PASS with a ``metadata["reason"]``
      note (never blocked; measurement failure is logged per S-5).
    """
    violations: list[HookViolation] = []
    if not isinstance(payload, dict):
        result = finalize(EVENT, violations, strict=strict)
        result.metadata["reason"] = "payload is not a dict"
        return result

    layer = _resolve_layer(payload)
    if layer is None:
        result = finalize(EVENT, violations, strict=strict)
        result.metadata["reason"] = "no telemetry-resolvable layer attribution"
        return result

    budget = LAYER_TOKEN_BUDGETS[layer]
    try:
        measured = estimate_tokens(stable_yaml(payload))
    except Exception as exc:  # noqa: BLE001 - measurement must never block dispatch
        logger.warning(
            "layer-budget assertion could not measure dispatch payload "
            "for layer %s: %s; dispatch continues unchecked",
            layer,
            exc,
        )
        result = finalize(EVENT, violations, strict=strict)
        result.metadata["reason"] = "token measurement failed"
        return result

    if measured > budget:
        violations.append(
            HookViolation(
                code=_VIOLATION_CODE,
                message=_VIOLATION_MESSAGE_TEMPLATE.format(
                    measured=measured,
                    layer=layer,
                    budget=budget,
                ),
                severity="error",
                context={
                    "layer": layer,
                    "measured_tokens": measured,
                    "budget_tokens": budget,
                    "rule": "v17.0.0 R2 G17-B2 / D-R2-5 (A-3 layer token budgets)",
                },
            )
        )

    try:
        ceremony_total, ceremony_source = _resolve_ceremony_tokens(
            payload,
            ceremony_tokens=ceremony_tokens,
            context_tokens=context_tokens,
            skill_text=skill_text,
            rule_text=rule_text,
            report_envelope=report_envelope,
        )
        ceremony_decision = (
            check_ceremony_share(
                ceremony_total,
                budget,
                warn_at=ceremony_share_threshold,
            )
            if ceremony_total is not None
            else None
        )
    except (TypeError, ValueError) as exc:
        logger.warning(
            "layer-budget assertion could not measure ceremony tokens for layer %s: %s",
            layer,
            exc,
        )
        ceremony_total = None
        ceremony_source = "invalid"
        ceremony_decision = None
        result = finalize(EVENT, violations, strict=strict)
        result.metadata["reason"] = "ceremony token measurement failed"
        result.metadata["layer"] = layer
        result.metadata["measured_tokens"] = measured
        result.metadata["budget_tokens"] = budget
        return result

    if ceremony_total is None:
        ceremony_source = f"{ceremony_source}:INSUFFICIENT"
    elif ceremony_decision is not None and ceremony_decision.action.value != "CONTINUE":
        violations.append(
            HookViolation(
                code=_CEREMONY_VIOLATION_CODE,
                message=_CEREMONY_MESSAGE_TEMPLATE.format(
                    ceremony_tokens=ceremony_total,
                    share=ceremony_decision.utilization,
                    layer=layer,
                    budget=budget,
                    threshold=ceremony_share_threshold,
                ),
                severity="blocker",
                context={
                    "layer": layer,
                    "ceremony_tokens": ceremony_total,
                    "ceremony_share": ceremony_decision.utilization,
                    "budget_tokens": budget,
                    "threshold": ceremony_share_threshold,
                    "source": ceremony_source,
                    "rule": "v21.0.0 PV-03 ceremony share warning",
                },
            )
        )

    result = finalize(EVENT, violations, strict=strict)
    result.metadata["layer"] = layer
    result.metadata["measured_tokens"] = measured
    result.metadata["budget_tokens"] = budget
    result.metadata["ceremony_tokens"] = ceremony_total
    result.metadata["ceremony_source"] = ceremony_source
    if ceremony_decision is not None:
        result.metadata["ceremony_share"] = ceremony_decision.utilization
    return result


__all__ = ["CEREMONY_SHARE_WARN_THRESHOLD", "EVENT", "assert_layer_token_budget"]
