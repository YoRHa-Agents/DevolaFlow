"""Dispatch-only context and attribution helpers for harness emission."""

from __future__ import annotations

import copy
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


_AUTO_INJECTED_CHANNELS = frozenset({"cursor", "cursor-ide"})
_CONTEXT_SELECTIONS = frozenset({"slice", "full"})


def _probe_host(channel: str) -> str | None:
    """Resolve a known subprocess channel through the existing probe registry."""

    from devolaflow.harness.cli_probe import PROBE_HOSTS

    return PROBE_HOSTS.get(channel)


def _selection_inputs(
    selection: Mapping[str, Any] | None,
) -> tuple[str | None, str | None, str | None]:
    """Return ``(source, selection, candidate_text)`` without guessing."""

    if selection is None:
        return None, None, None
    if not isinstance(selection, Mapping):
        raise TypeError("selection must be a mapping or None")

    source = selection.get("source")
    source_value = source.strip() if isinstance(source, str) and source.strip() else None
    account = selection.get("agents_md_slice")
    account = account if isinstance(account, Mapping) else {}

    requested = selection.get("selection") or selection.get("mode")
    if requested not in _CONTEXT_SELECTIONS:
        enabled = account.get("slice_enabled", selection.get("slice_enabled"))
        requested = "slice" if enabled is True else "full" if enabled is False else None
    if requested not in _CONTEXT_SELECTIONS:
        requested = None

    if requested == "slice":
        candidate_keys = ("slice_text", "sliced_text", "rule_text", "text")
    elif requested == "full":
        candidate_keys = ("full_text", "full_rule_text", "rule_text", "text")
    else:
        candidate_keys = ()
    candidate = next(
        (selection.get(key) for key in candidate_keys if isinstance(selection.get(key), str)),
        None,
    )
    return source_value, requested, candidate


def _route_identity(
    *,
    host: str | None,
    channel: str | None,
) -> tuple[str | None, str | None, str | None]:
    """Resolve an HSC host and existing channel into a delivery mode."""

    from devolaflow.host_contract import load_host_contract, resolve_host

    contract = load_host_contract()
    canonical_host: str | None = None
    if host is not None:
        if not isinstance(host, str) or not host.strip():
            return None, None, "unknown-host"
        try:
            canonical_host = resolve_host(host.strip(), contract)
        except KeyError:
            return host.strip(), None, "unknown-host"

    if channel is None:
        if canonical_host == "cursor":
            return canonical_host, "host", None
        return canonical_host, None, "INSUFFICIENT"
    if not isinstance(channel, str) or not channel.strip():
        return canonical_host, None, "unknown-channel"

    channel_value = channel.strip()
    mapped_host = _probe_host(channel_value)
    if mapped_host is not None:
        if canonical_host is not None and canonical_host != mapped_host:
            return canonical_host, "subprocess", "host-channel-mismatch"
        return canonical_host or mapped_host, "subprocess", None
    if channel_value in _AUTO_INJECTED_CHANNELS:
        if canonical_host is not None and canonical_host != "cursor":
            return canonical_host, "host", "host-channel-mismatch"
        return "cursor", "host", None
    return canonical_host, None, "unknown-channel"


def route_context_injection(
    selection: Mapping[str, Any] | None = None,
    *,
    host: str | None = None,
    channel: str | None = None,
) -> dict[str, Any]:
    """Route full/sliced context according to the existing HSC/channel split.

    Declared subprocess channels may carry selected text in a dispatch.
    Cursor IDE host injection must not carry the same text in the dispatch:
    it returns ``host-injected-unsliceable`` with an ``INSUFFICIENT`` evidence
    status because host-consumed context is not observable here. Unknown
    hosts, channels, and mismatches are explicit insufficient states.
    """

    source, selected, candidate = _selection_inputs(selection)
    resolved_host, mode, identity_status = _route_identity(host=host, channel=channel)
    result: dict[str, Any] = {
        "source": source,
        "selection": selected,
        "host": resolved_host,
        "channel": channel,
        "channel_mode": mode,
        "status": "INSUFFICIENT",
        "evidence_status": "INSUFFICIENT",
        "embedded": False,
        "embedded_text": None,
        "candidate_text": candidate,
        "reason": None,
    }

    if identity_status is not None:
        result["status"] = identity_status
        result["reason"] = {
            "unknown-host": "host is absent from the HSC",
            "unknown-channel": "channel is not a declared subprocess or host channel",
            "host-channel-mismatch": "host and channel resolve to different HSC hosts",
            "INSUFFICIENT": "a host/channel delivery boundary was not supplied",
        }.get(identity_status, "host/channel delivery is not attributable")
        return result

    if selected is None:
        result["reason"] = "full/slice selection is absent or contradictory"
        return result
    if candidate is None:
        result["reason"] = f"{selected} context text was not supplied"
        return result

    if mode == "subprocess":
        result["status"] = f"{selected}-embedded"
        result["evidence_status"] = "AVAILABLE"
        result["embedded"] = True
        result["embedded_text"] = candidate
        return result

    if mode == "host":
        result["status"] = "host-injected-unsliceable"
        result["reason"] = (
            "host injects context outside the dispatch; host-consumed slice "
            "is not observable and must not be duplicated"
        )
        return result

    result["reason"] = "delivery mode is not attributable"
    return result


def _with_rules(dispatch: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Copy a dispatch and return its mutable existing/new rules block."""

    result = copy.deepcopy(dict(dispatch))
    rules = result.get("rules")
    if isinstance(rules, dict):
        return result, copy.deepcopy(rules)
    rules = {}
    items = list(result.items())
    result = {}
    inserted = False
    for key, value in items:
        if not inserted and key == "shared":
            result["rules"] = rules
            inserted = True
        result[key] = value
    if not inserted:
        result["rules"] = rules
    return result, rules


def prepare_dispatch_context(
    dispatch: Mapping[str, Any],
    selection: Mapping[str, Any] | None = None,
    *,
    host: str | None = None,
    channel: str | None = None,
) -> dict[str, Any]:
    """Prepare a dispatch and return its auditable routing decision.

    For an auto-injected host, an existing text block is removed only when it
    is byte-identical to the selected candidate. Unrelated caller-owned rules
    remain untouched.
    """

    if not isinstance(dispatch, Mapping):
        raise TypeError("dispatch must be a mapping")
    routing = route_context_injection(selection, host=host, channel=channel)
    if routing["channel_mode"] not in {"subprocess", "host"} or (
        routing["channel_mode"] == "subprocess" and not routing["embedded"]
    ):
        return {"dispatch": copy.deepcopy(dict(dispatch)), "routing": routing}
    if routing["channel_mode"] == "host" and not isinstance(dispatch.get("rules"), dict):
        routing["duplicate_prevented"] = False
        return {"dispatch": copy.deepcopy(dict(dispatch)), "routing": routing}
    result, rules = _with_rules(dispatch)

    if routing["channel_mode"] == "subprocess" and routing["embedded"]:
        rules["text"] = routing["embedded_text"]
    elif routing["channel_mode"] == "host":
        if (
            isinstance(routing["candidate_text"], str)
            and rules.get("text") == routing["candidate_text"]
        ):
            del rules["text"]
            routing["duplicate_prevented"] = True
        else:
            routing["duplicate_prevented"] = False
    result["rules"] = rules
    return {"dispatch": result, "routing": routing}


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
    host: str | None = None,
    channel: str | None = None,
    context_selection: Mapping[str, Any] | None = None,
):
    """Expose emission-only context to observational lifecycle handlers."""
    routing_host = host
    routing_channel = channel
    routing_selection = context_selection
    if isinstance(metadata, Mapping):
        if routing_host is None:
            candidate_host = metadata.get("host")
            routing_host = candidate_host if isinstance(candidate_host, str) else None
        if routing_channel is None:
            candidate_channel = metadata.get("channel")
            routing_channel = candidate_channel if isinstance(candidate_channel, str) else None
        if routing_selection is None:
            candidate_selection = metadata.get("context_selection")
            if isinstance(candidate_selection, Mapping):
                routing_selection = candidate_selection
    context_routing = None
    if routing_host is not None or routing_channel is not None or routing_selection is not None:
        context_routing = route_context_injection(
            routing_selection,
            host=routing_host,
            channel=routing_channel,
        )
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
        and context_routing is None
        and not accounting_requested
    ):
        yield
        return
    context: dict[str, Any] = {
        "context_tokens": context_tokens,
        "skill_text": skill_text,
        "rule_text": rule_text,
        "report_envelope": report_envelope,
        "profile": profile,
        "metadata": metadata,
        "requested": accounting_requested,
    }
    if context_routing is not None:
        context["context_routing"] = context_routing
    token = _ACTIVE_DISPATCH_CONTEXT.set(context)
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
