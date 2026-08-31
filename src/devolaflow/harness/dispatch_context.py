"""Dispatch-only context and attribution helpers for harness emission."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any

from devolaflow.agent_workspace.layers import LAYER_ATTRIBUTION_ALIASES

_ACTIVE_ROOT = Path(".local") / ".agent" / "active"
_LAYER_ALIASES = LAYER_ATTRIBUTION_ALIASES
_ACTIVE_DISPATCH_CONTEXT: ContextVar[dict[str, Any] | None] = ContextVar(
    "devolaflow_active_dispatch_context",
    default=None,
)
logger = logging.getLogger(__name__)


class _AttributionError(ValueError):
    """Internal signal for a dispatch that cannot be attributed safely."""


@contextmanager
def dispatch_context(
    *,
    context_tokens: Mapping[str, object] | None = None,
    skill_text: str | None = None,
    rule_text: str | None = None,
    report_envelope: Mapping[str, Any] | str | None = None,
    profile: str | None = None,
    metadata: Mapping[str, Any] | None = None,
    accounting_requested: bool = False,
):
    """Expose emission-only context to observational lifecycle handlers."""
    if (
        all(
            value is None
            for value in (
                context_tokens,
                skill_text,
                rule_text,
                report_envelope,
                profile,
                metadata,
            )
        )
        and not accounting_requested
    ):
        yield
        return
    token = _ACTIVE_DISPATCH_CONTEXT.set(
        {
            "context_tokens": context_tokens,
            "skill_text": skill_text,
            "rule_text": rule_text,
            "report_envelope": report_envelope,
            "profile": profile,
            "metadata": metadata,
            "requested": accounting_requested,
        }
    )
    try:
        yield
    finally:
        _ACTIVE_DISPATCH_CONTEXT.reset(token)


def current_dispatch_context() -> Mapping[str, Any] | None:
    """Return the current emission context without performing any IO."""
    value = _ACTIVE_DISPATCH_CONTEXT.get()
    return dict(value) if value is not None else None


def _mapping(payload: dict[str, Any], key: str) -> dict[str, Any] | None:
    value = payload.get(key)
    return value if isinstance(value, dict) else None


def _non_empty_string(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _AttributionError(f"{field} must be a non-empty string")
    return value


def _dispatch_id(payload: dict[str, Any]) -> str:
    hdr = _mapping(payload, "hdr")
    header = _mapping(payload, "header")
    candidates = (
        hdr.get("id") if hdr else None,
        hdr.get("dispatch_id") if hdr else None,
        header.get("id") if header else None,
        header.get("dispatch_id") if header else None,
        payload.get("dispatch_id"),
        payload.get("task_id"),
    )
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate
    raise _AttributionError("dispatch_id is absent from hdr/header/top-level dispatch fields")


def _normalize_layer(value: object, *, field: str) -> str:
    token = _non_empty_string(value, field=field)
    normalized = _LAYER_ALIASES.get(token)
    if normalized is None:
        raise _AttributionError(
            f"{field} has unsupported layer {token!r}; expected L0/L1/L2 or project/wave/task"
        )
    return normalized


def _dispatch_layer(payload: dict[str, Any]) -> str:
    """Resolve current layer attribution without modifying legacy payloads."""
    change_context = _mapping(payload, "change_context")
    hdr = _mapping(payload, "hdr")
    header = _mapping(payload, "header")
    sources = (
        ("change_context", change_context),
        ("hdr", hdr),
        ("header", header),
    )
    for source_name, source in sources:
        if source is not None and "to_layer" in source:
            return _normalize_layer(source["to_layer"], field=f"{source_name}.to_layer")
    if "to_layer" in payload:
        return _normalize_layer(payload["to_layer"], field="to_layer")
    if "layer" in payload:
        return _normalize_layer(payload["layer"], field="layer")
    for source_name, source in sources:
        if source is not None and "layer" in source:
            return _normalize_layer(source["layer"], field=f"{source_name}.layer")
    raise _AttributionError("layer is absent from dispatch attribution fields")


def _round_number(payload: dict[str, Any]) -> int:
    change_context = _mapping(payload, "change_context")
    round_context = change_context.get("round_context") if change_context is not None else None
    if round_context is not None:
        if not isinstance(round_context, dict):
            raise _AttributionError("change_context.round_context must be a mapping")
        value = round_context.get("round_n")
        if type(value) is not int or value < 1:
            raise _AttributionError("change_context.round_context.round_n must be an integer >= 1")
        return value
    for field in ("round", "round_num"):
        if field in payload:
            value = payload[field]
            if type(value) is not int or value < 1:
                raise _AttributionError(f"{field} must be an integer >= 1")
            return value
    return 1


def _dispatch_profile(payload: dict[str, Any]) -> str | None:
    """Resolve an explicitly supplied selector profile, if present."""
    containers: list[Mapping[str, Any]] = [payload]
    for parent_key in ("context", "telemetry"):
        parent = _mapping(payload, parent_key)
        if parent is not None:
            containers.append(parent)
    for container in containers:
        for key in ("profile", "profile_name"):
            value = container.get(key)
            if isinstance(value, str) and value.strip():
                return value
    return None


def _explicit_change_id(payload: dict[str, Any]) -> str | None:
    change_context = _mapping(payload, "change_context")
    if change_context is None or "change_id" not in change_context:
        return None
    change_id = _non_empty_string(
        change_context["change_id"],
        field="change_context.change_id",
    )
    if Path(change_id).name != change_id:
        raise _AttributionError("change_context.change_id must be one active-folder basename")
    return change_id


def _resolve_active_change(
    payload: dict[str, Any],
    *,
    repo_root: Path,
    log: logging.Logger | None = None,
) -> Path | None:
    active_root = repo_root / _ACTIVE_ROOT
    explicit_change_id = _explicit_change_id(payload)
    if explicit_change_id is not None:
        explicit_folder = active_root / explicit_change_id
        if explicit_folder.is_dir():
            return explicit_folder
        (log or logger).warning(
            "harness telemetry cannot attribute explicit change_id %r: "
            "active folder %s is absent; record not written",
            explicit_change_id,
            explicit_folder,
        )
        return None
    if not active_root.is_dir():
        return None
    active_folders = sorted(
        (path for path in active_root.iterdir() if path.is_dir()),
        key=lambda path: path.name,
    )
    if not active_folders:
        return None
    if len(active_folders) > 1:
        (log or logger).warning(
            "harness telemetry found %d active changes but no explicit change_id; "
            "record not written",
            len(active_folders),
        )
        return None
    return active_folders[0]
