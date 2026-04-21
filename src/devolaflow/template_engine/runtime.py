"""Mode-aware runtime stage selector for workflow templates.

Design ref: ``.local/research/v7.5.0_ghost_audit.md`` §3.G + §3.I + §5 P-04 row.

Closes the v7.4.2 internal follow-up flagged by T-W1-1 fix-wave: composer
walks the composition tree but never consults ``WorkflowTemplate.parameters``
or ``StageDefinition.skip_condition``. This module is a thin runtime shim
sitting ON TOP of :mod:`devolaflow.template_engine.composer` (whose public
API stays bytewise-compatible) that produces a filtered, ordered list of
:class:`~devolaflow.template_engine.models.StageRef` objects honouring:

1. ``WorkflowTemplate.parameters.mode.default`` when the caller does not
   pass an explicit ``mode`` argument.
2. ``StageDefinition.skip_condition`` evaluated against the runtime context.
3. ``WorkflowTemplate.environment_modes[<env>].skip_stages`` (filter out)
   and ``.extra_stages`` (append at end).

The expression evaluator is intentionally minimal — supports ``==`` and
``!=`` comparisons between an identifier (looked up in context) and either
a quoted string literal, a bare numeric literal, or another identifier.
**Python ``eval()`` / ``exec()`` are never used** (security + sandbox
discipline per CO-4 / SF-5 spirit and audit §5 P-04 risk row).

Malformed expressions log a WARNING via :mod:`logging` and default to NOT
skipping (safe default — better to over-execute than to silently elide a
stage based on a typo).
"""

from __future__ import annotations

import logging
import re
from typing import Any

from devolaflow.template_engine.models import (
    Break,
    Choice,
    CompositionNode,
    GateRef,
    LoopRef,
    Parallel,
    Sequence,
    StageRef,
    WorkflowTemplate,
)

log = logging.getLogger(__name__)

DEFAULT_MODE = "standard"
DEFAULT_ENVIRONMENT = "local"

_EXPR_RE = re.compile(
    r"""^\s*
        (?P<lhs>[A-Za-z_][A-Za-z0-9_]*)        # identifier
        \s*
        (?P<op>==|!=)                          # operator
        \s*
        (?:                                    # rhs alternatives:
            '(?P<sq>[^']*)'                    #   single-quoted literal
          | "(?P<dq>[^"]*)"                    #   double-quoted literal
          | (?P<bare>[A-Za-z0-9_.\-]+)         #   bare identifier or numeric
        )
        \s*$
    """,
    re.VERBOSE,
)


def evaluate_skip_condition(expression: str | None, context: dict[str, Any]) -> bool:
    """Return True if a stage carrying *expression* should be SKIPPED.

    Grammar (intentionally minimal — ``eval()`` is NEVER used):

        <expr>    := <ident> <op> <rhs>
        <op>      := "==" | "!="
        <rhs>     := <quoted-string> | <number> | <ident>
        <ident>   := /[A-Za-z_][A-Za-z0-9_]*/

    *expression* of ``None`` or empty/whitespace-only is treated as
    "no skip condition" and returns False. Malformed expressions log a
    WARNING and return False (safe default — execute the stage rather
    than silently elide it on a typo).
    """
    if expression is None:
        return False
    text = expression.strip()
    if not text:
        return False

    match = _EXPR_RE.match(text)
    if not match:
        log.warning(
            "Malformed skip_condition expression %r — defaulting to NOT skip "
            "(supported grammar: <ident> ('==' | '!=') (<quoted-string> | <number> | <ident>))",
            expression,
        )
        return False

    lhs_name = match.group("lhs")
    op = match.group("op")
    sq, dq, bare = match.group("sq"), match.group("dq"), match.group("bare")

    lhs_value = context.get(lhs_name)

    if sq is not None:
        rhs_value: Any = sq
    elif dq is not None:
        rhs_value = dq
    else:
        assert bare is not None
        rhs_value = _coerce_bare_rhs(bare, context)

    if op == "==":
        return lhs_value == rhs_value
    return lhs_value != rhs_value


def _coerce_bare_rhs(bare: str, context: dict[str, Any]) -> Any:
    """Resolve a bare RHS token: identifier-in-context, int, float, or string."""
    if bare in context:
        return context[bare]
    try:
        return int(bare)
    except ValueError:
        pass
    try:
        return float(bare)
    except ValueError:
        pass
    return bare


def _flatten_composition(node: CompositionNode, ordered: list[StageRef]) -> None:
    """Walk the composition tree and append :class:`StageRef`s in execution order.

    Choice branches are walked in declaration order (if_true → if_false) — we
    cannot evaluate the choice predicate at runtime-filter time, so both
    branches contribute their stages. Loops and gates contribute nothing
    here (stage refs inside loops are reached via ``LoopDef.body_stages``
    in the dispatch layer, not via this composition flattener).
    """
    if isinstance(node, StageRef):
        ordered.append(node)
        return
    if isinstance(node, (Sequence, Parallel)):
        for child in node.stages:
            _flatten_composition(child, ordered)
        return
    if isinstance(node, Choice):
        _flatten_composition(node.if_true, ordered)
        _flatten_composition(node.if_false, ordered)
        return
    if isinstance(node, (LoopRef, GateRef, Break)):
        return


def _resolve_mode_default(template: WorkflowTemplate) -> str:
    """Return ``parameters.mode.default`` when present, else ``DEFAULT_MODE``."""
    params_mode = template.parameters.get("mode") if template.parameters else None
    if isinstance(params_mode, dict):
        default = params_mode.get("default")
        if isinstance(default, str) and default:
            return default
    return DEFAULT_MODE


def _resolve_runtime_context(
    template: WorkflowTemplate,
    mode: str | None,
    environment: str,
    extra_context: dict[str, Any] | None,
) -> tuple[str, dict[str, Any]]:
    """Resolve the effective mode and the skip-condition evaluation context.

    Explicit *mode* wins; otherwise falls back to
    ``template.parameters.mode.default`` and finally :data:`DEFAULT_MODE`.
    The returned context is seeded with ``mode`` and ``environment`` and
    then overlaid with *extra_context* when provided.
    """
    effective_mode = mode if mode is not None else _resolve_mode_default(template)
    context: dict[str, Any] = {
        "mode": effective_mode,
        "environment": environment,
    }
    if extra_context:
        context.update(extra_context)
    return effective_mode, context


def _filter_by_skip_predicates(
    ordered: list[StageRef],
    stage_def_map: dict[str, Any],
    context: dict[str, Any],
) -> list[StageRef]:
    """Drop any :class:`StageRef` whose stage definition's ``skip_condition`` is True.

    Stage refs without a matching definition (or without a skip condition)
    pass through unchanged. Elided stages are logged at DEBUG with the
    triggering expression and context.
    """
    filtered: list[StageRef] = []
    for ref in ordered:
        stage_def = stage_def_map.get(ref.stage)
        if stage_def is None or not stage_def.skip_condition:
            filtered.append(ref)
            continue
        if evaluate_skip_condition(stage_def.skip_condition, context):
            log.debug(
                "Stage %r elided: skip_condition %r evaluated True under context %r",
                ref.stage,
                stage_def.skip_condition,
                context,
            )
            continue
        filtered.append(ref)
    return filtered


def _apply_environment_overlay(
    filtered: list[StageRef],
    env_cfg: dict[str, Any] | None,
    environment: str,
    stage_def_map: dict[str, Any],
) -> list[StageRef]:
    """Apply ``environment_modes`` skip/extra stages overlay to *filtered*.

    ``skip_stages`` removes refs by stage id; ``extra_stages`` appends
    a fresh :class:`StageRef` for each id that resolves to a defined
    stage. Unknown ids are logged at WARNING and skipped.
    """
    if not isinstance(env_cfg, dict):
        return filtered
    skip_set = set(env_cfg.get("skip_stages") or [])
    if skip_set:
        filtered = [r for r in filtered if r.stage not in skip_set]
    for extra_id in env_cfg.get("extra_stages") or []:
        if not isinstance(extra_id, str):
            continue
        if extra_id in stage_def_map:
            filtered.append(StageRef(stage=extra_id))
        else:
            log.warning(
                "environment_modes[%r].extra_stages references unknown stage id %r — skipping",
                environment,
                extra_id,
            )
    return filtered


def select_stages_for_runtime(
    template: WorkflowTemplate,
    *,
    mode: str | None = None,
    environment: str = DEFAULT_ENVIRONMENT,
    extra_context: dict[str, Any] | None = None,
) -> list[StageRef]:
    """Return the ordered :class:`StageRef` list to execute under *mode* / *environment*.

    Pipeline:

    1. Resolve effective ``mode`` — explicit *mode* argument wins; otherwise
       fall back to ``template.parameters.mode.default`` (per the YAML
       declaration); otherwise the module-level :data:`DEFAULT_MODE`.
    2. Walk ``template.composition`` to a flat ordered list of
       :class:`StageRef`. Loops and gates are intentionally skipped here
       (they are dispatch-layer concerns).
    3. For each :class:`StageRef`, look up its :class:`StageDefinition`
       and evaluate ``skip_condition`` against the runtime context
       ``{"mode": <mode>, "environment": <environment>, **extra_context}``.
       Drop the ref when the expression evaluates True.
    4. Apply ``template.environment_modes[<environment>]``:

       - ``skip_stages`` — drop any ref whose stage id is in this list
         (applied AFTER skip_condition filtering).
       - ``extra_stages`` — append a :class:`StageRef` for each id in the
         list (only if the id resolves to a defined stage; unknown ids are
         logged at WARNING level and skipped).

    The composer API at :mod:`devolaflow.template_engine.composer` is
    UNCHANGED. This function is a pure additive runtime layer.

    Args:
        template: The fully-parsed (and inheritance-resolved, if any)
            workflow template.
        mode: Optional override for ``parameters.mode.default``.
        environment: Environment key for ``environment_modes`` lookup
            (canonical: ``"local"`` or ``"github"``); defaults to
            :data:`DEFAULT_ENVIRONMENT`.
        extra_context: Optional additional bindings for skip_condition
            evaluation (merged after ``mode`` / ``environment``).

    Returns:
        A list of :class:`StageRef` in execution order, with skip-conditions
        and environment overlays applied. May be empty if every stage is
        elided.
    """
    _, context = _resolve_runtime_context(template, mode, environment, extra_context)
    stage_def_map = {s.id: s for s in template.stages}

    ordered: list[StageRef] = []
    _flatten_composition(template.composition, ordered)

    filtered = _filter_by_skip_predicates(ordered, stage_def_map, context)

    env_cfg = template.environment_modes.get(environment) if template.environment_modes else None
    return _apply_environment_overlay(filtered, env_cfg, environment, stage_def_map)


__all__ = [
    "DEFAULT_ENVIRONMENT",
    "DEFAULT_MODE",
    "evaluate_skip_condition",
    "select_stages_for_runtime",
]
