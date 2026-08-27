"""Append-only per-dispatch telemetry for the built-in harness.

The post-dispatch lifecycle integration is deliberately observational:
payloads are rendered to stable YAML for measurement, never mutated, and any
attribution or persistence failure is reduced to a WARNING plus a clean
``HookResult``.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import yaml

from devolaflow.agent_workspace.layers import LAYER_ATTRIBUTION_ALIASES
from devolaflow.agents_md_slice import cached_slice_summary
from devolaflow.harness.capacity import CapacityProfile, capacity_profile
from devolaflow.harness.tiers import annotate_rule_surfaces, summarize_constraints
from devolaflow.task_adaptive_selector import estimate_tokens

if TYPE_CHECKING:
    from devolaflow.lifecycle.dispatcher import HookResult

EVENT: Final[str] = "post_dispatch"
HARNESS_SEGMENT_MAX_BYTES: Final[int] = 64 * 1024
MAX_HARNESS_SEGMENT_BYTES: Final[int] = HARNESS_SEGMENT_MAX_BYTES
LAYER_TOKEN_BUDGETS: Final[dict[str, int]] = {
    "L0": 5_000,
    "L1": 5_000,
    "L2": 8_000,
}

_ACTIVE_ROOT = Path(".local") / ".agent" / "active"
_BASE_LEDGER_NAME = "harness.jsonl"
_BEHAVIORAL_GUIDELINES_REF = "workflow-system/agent/references/behavioral-guidelines.md"
_SEGMENT_RE = re.compile(r"^harness\.(?P<index>[1-9]\d*)\.jsonl$")
# Alias table owned by agent_workspace.layers (A-5 single-owner; merged v17).
_LAYER_ALIASES: Final[dict[str, str]] = LAYER_ATTRIBUTION_ALIASES

logger = logging.getLogger(__name__)


class _AttributionError(ValueError):
    """Internal signal for a dispatch that cannot be attributed safely."""


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

    # An explicit destination is the strongest attribution signal.
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


def _capacity_view() -> CapacityProfile:
    """Resolve the capacity profile without ever blocking a dispatch.

    v17.0.0 R5 (D-R5-1): telemetry mirrors the configured round capacity
    (checklist-slice bound) and records the resolved profile in each ledger
    record. Any resolution failure — including a loudly-invalid
    ``meta.capacity`` block, which the DISPATCH path surfaces as a raise —
    degrades here to the hardcoded defaults with a WARNING per S-5, because
    telemetry is observational and must never block.
    """

    try:
        return capacity_profile()
    except Exception as exc:  # noqa: BLE001 - telemetry stays nonblocking
        logger.warning(
            "harness telemetry capacity profile resolution failed: %s; using hardcoded defaults",
            exc,
        )
        return CapacityProfile()


def _checklist_constraint_count(payload: dict[str, Any], *, round_capacity: int) -> int:
    change_context = _mapping(payload, "change_context")
    if change_context is None or "checklist_items" not in change_context:
        return 0
    checklist_items = change_context["checklist_items"]
    if not isinstance(checklist_items, list):
        raise _AttributionError("change_context.checklist_items must be a list")
    if not 1 <= len(checklist_items) <= round_capacity:
        raise _AttributionError(
            f"change_context.checklist_items must contain 1 through {round_capacity} items"
        )
    return len(checklist_items)


def _model_hint(payload: dict[str, Any]) -> str:
    hdr = _mapping(payload, "hdr")
    context = _mapping(payload, "context")
    candidates = (
        payload.get("model_hint"),
        hdr.get("model_hint") if hdr else None,
        context.get("model_hint") if context else None,
    )
    for candidate in candidates:
        if candidate is None:
            continue
        return _non_empty_string(candidate, field="model_hint")
    return "inherit"


def _dispatch_task_type(payload: dict[str, Any]) -> str:
    """Resolve the dispatch task type for AGENTS.md-slice accounting.

    Resolution order (first non-empty string wins):
      1. ``task.type`` — the canonical work-unit type of BOTH dispatch
         formats (lean ``task: { id, type, title }`` at canonical position
         2 and the verbose original format's ``task.type``; see
         ``schemas/lean-dispatch.yaml#lean_format_spec.task``).
      2. ``context.applicable_rules.task_type`` — the verbose format's
         rule-loading hint (``schemas/lean-dispatch.yaml`` original
         example; mirrored in ``task-dispatch.schema.yaml``).

    Returns ``""`` when unresolvable — the slice module's ``fallback:
    full`` semantics then yield ``slice_savings_pct == 0.0`` with
    ``host_rule_tokens`` still carrying the full AGENTS.md estimate.
    """

    task = _mapping(payload, "task")
    if task is not None:
        value = task.get("type")
        if isinstance(value, str) and value.strip():
            return value
    context = _mapping(payload, "context")
    if context is not None:
        applicable = context.get("applicable_rules")
        if isinstance(applicable, dict):
            value = applicable.get("task_type")
            if isinstance(value, str) and value.strip():
                return value
    return ""


def _slice_injection_metrics(payload: dict[str, Any]) -> tuple[int, float]:
    """Return ``(host_rule_tokens, slice_savings_pct)`` for one dispatch.

    v17.0.0 R3 (G17-B3 / D-R3-2) — host injection accounting:

      * ``host_rule_tokens`` is the FULL AGENTS.md corpus estimate
        (``full_tokens``), because hosts inject the unsliced corpus today;
        the slice is configured but unwired on the host side.
      * ``slice_savings_pct`` is the YAML-CONFIGURED slice's available
        saving for this dispatch's task type. The computation passes
        ``env={}`` so the R5 process-env opt-out
        (``DEVOLAFLOW_AGENTS_MD_SLICE=0``) does NOT zero the ledger — the
        account measures what the configuration offers, deterministically,
        which also keeps the owner module's mtime-keyed cache valid
        without an env component per record.

    The summary comes from the module-level cache in
    ``devolaflow.agents_md_slice`` (keyed on AGENTS.md path + mtime_ns +
    task_type), so appending records never re-reads AGENTS.md. Any
    failure degrades to ``(0, 0.0)`` with a WARNING per S-5 — telemetry
    must never block a dispatch.
    """

    try:
        summary = cached_slice_summary(_dispatch_task_type(payload), env={})
        return summary["full_tokens"], float(summary["slice_savings_pct"])
    except Exception as exc:  # noqa: BLE001 - telemetry stays nonblocking
        logger.warning(
            "harness telemetry AGENTS.md slice accounting failed: %s; "
            "host_rule_tokens/slice_savings_pct zeroed",
            exc,
        )
        return 0, 0.0


def _stable_yaml(payload: dict[str, Any]) -> str:
    """Render deterministic measurement input independent of mapping order."""

    return yaml.safe_dump(
        payload,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=True,
    )


# v17.0.0 R2 (G17-B2 / D-R2-5) — public alias so the pre_dispatch
# layer-budget assertion (`lifecycle.assert_layer_budget`) measures
# dispatch payloads with the EXACT serializer telemetry records with
# (A-5: one measurement pipeline, one owner).
stable_yaml = _stable_yaml


def _constraint_summary_view(payload: dict[str, Any]) -> dict[str, Any]:
    """Return an annotated copy without advisory-fold metadata."""

    view = dict(payload)
    behavioral = _mapping(payload, "behavioral_guidelines")
    if behavioral is not None and "advisory_folded" in behavioral:
        view["behavioral_guidelines"] = {
            name: value for name, value in behavioral.items() if name != "advisory_folded"
        }
    return annotate_rule_surfaces(view)


def _behavioral_advisory_count(summary_view: dict[str, Any]) -> int:
    """Count active advisory constraints from behavioral guidelines only."""

    behavioral = _mapping(summary_view, "behavioral_guidelines")
    if behavioral is None:
        return 0
    _, breakdown, _ = summarize_constraints({"behavioral_guidelines": behavioral})
    return breakdown["advisory"]


def build_dispatch_record(
    payload: dict[str, Any],
    *,
    change_id: str,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Build one exact-schema harness record from a dispatch payload.

    v17.0.0 R3 (G17-B3 / D-R3-2) appended two host-injection accounting
    fields: ``host_rule_tokens`` (full AGENTS.md corpus estimate — hosts
    inject the unsliced corpus) and ``slice_savings_pct`` (the configured
    slice's available saving for this dispatch's task type, resolved per
    :func:`_dispatch_task_type` / :func:`_slice_injection_metrics`).
    v17.0.0 R5 (G17-B6 / D-R5-1) appended ``capacity_profile`` — the
    resolved round capacity + executor concurrency with aggregate
    provenance (``"config"`` when any ``meta.capacity`` field is declared,
    else ``"default"``). All three are OPTIONAL for the aggregator — old
    ledgers keep aggregating.
    """

    if not isinstance(payload, dict):
        raise _AttributionError("payload must be a dict")
    attributed_change_id = _non_empty_string(change_id, field="change_id")
    if Path(attributed_change_id).name != attributed_change_id:
        raise _AttributionError("change_id must be one active-folder basename")

    capacity_view = _capacity_view()
    layer = _dispatch_layer(payload)
    _checklist_constraint_count(payload, round_capacity=capacity_view.round_capacity)
    summary_view = _constraint_summary_view(payload)
    constraint_count, tier_breakdown, quantifiable_ratio = summarize_constraints(summary_view)
    behavioral = _mapping(payload, "behavioral_guidelines")
    advisory_folded = behavioral is not None and behavioral.get("advisory_folded") is True
    model_hint = _model_hint(payload)
    measured = estimate_tokens(_stable_yaml(payload))
    host_rule_tokens, slice_savings_pct = _slice_injection_metrics(payload)
    record_timestamp = timestamp or datetime.now(UTC).isoformat()

    record = {
        "ts": record_timestamp,
        "change_id": attributed_change_id,
        "round": _round_number(payload),
        "layer": layer,
        "dispatch_id": _dispatch_id(payload),
        "tokens_injected_measured": measured,
        "tokens_budget": LAYER_TOKEN_BUDGETS[layer],
        "constraint_count": constraint_count,
        "quantifiable_ratio": quantifiable_ratio,
        "tier_breakdown": tier_breakdown,
        "advisory_folded": advisory_folded,
        "model_hint": model_hint,
        "host_rule_tokens": host_rule_tokens,
        "slice_savings_pct": slice_savings_pct,
        "capacity_profile": {
            "round_capacity": capacity_view.round_capacity,
            "max_concurrency": capacity_view.max_concurrency,
            "source": capacity_view.source,
        },
        # v18.0.0 — explicit full AGENTS.md token metric for rule-slimming
        # comparisons; retain host_rule_tokens for backward compatibility.
        "agents_md_tokens": host_rule_tokens,
    }
    if advisory_folded:
        record["fold_trace"] = {
            "folded_count": _behavioral_advisory_count(summary_view),
            "ref": _BEHAVIORAL_GUIDELINES_REF,
            "model_hint": model_hint,
        }
    return record


def _segment_index(path: Path) -> int | None:
    if path.name == _BASE_LEDGER_NAME:
        return 0
    match = _SEGMENT_RE.fullmatch(path.name)
    return int(match.group("index")) if match else None


def _segment_path(change_folder: Path, index: int) -> Path:
    if index == 0:
        return change_folder / _BASE_LEDGER_NAME
    return change_folder / f"harness.{index}.jsonl"


def append_harness_record(
    change_folder: str | Path,
    record: dict[str, Any],
    *,
    max_bytes: int = HARNESS_SEGMENT_MAX_BYTES,
) -> Path | None:
    """Append one compact JSONL record, rotating before the byte ceiling.

    Rotation is append-only: existing segments are never rewritten. The
    implementation uses directory metadata and ``stat`` only; it never reads
    an existing ledger into memory and deliberately performs no ``fsync``.
    """

    folder = Path(change_folder)
    try:
        if type(max_bytes) is not int or max_bytes <= 0:
            raise ValueError("max_bytes must be a positive integer")
        if not folder.is_dir():
            raise OSError(f"active change folder does not exist: {folder!s}")
        encoded = (json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n").encode(
            "utf-8"
        )
        if len(encoded) > max_bytes:
            logger.warning(
                "harness telemetry record is %d bytes, exceeding the %d-byte "
                "segment cap; record not written",
                len(encoded),
                max_bytes,
            )
            return None

        indexed_segments = [
            (index, child)
            for child in folder.iterdir()
            if child.is_file() and (index := _segment_index(child)) is not None
        ]
        if indexed_segments:
            index, target = max(indexed_segments, key=lambda item: item[0])
        else:
            index, target = 0, _segment_path(folder, 0)

        current_size = target.stat().st_size if target.exists() else 0
        if current_size + len(encoded) > max_bytes:
            target = _segment_path(folder, index + 1)

        with target.open("ab") as stream:
            stream.write(encoded)
        return target
    except (OSError, TypeError, ValueError) as exc:
        logger.warning(
            "harness telemetry append failed for %s: %s; dispatch continues",
            folder,
            exc,
        )
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
) -> Path | None:
    active_root = repo_root / _ACTIVE_ROOT
    explicit_change_id = _explicit_change_id(payload)
    if explicit_change_id is not None:
        explicit_folder = active_root / explicit_change_id
        if explicit_folder.is_dir():
            return explicit_folder
        logger.warning(
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
        logger.warning(
            "harness telemetry found %d active changes but no explicit change_id; "
            "record not written",
            len(active_folders),
        )
        return None
    return active_folders[0]


def record_dispatch_telemetry(
    payload: dict[str, Any],
    *,
    strict: bool = False,
    repo_root: str | Path | None = None,
) -> HookResult:
    """Nonblocking ``post_dispatch`` extra that records harness telemetry."""

    from devolaflow.lifecycle.dispatcher import HookResult

    del strict  # Telemetry is observational and never raises in strict mode.
    result = HookResult(event=EVENT)
    try:
        if not isinstance(payload, dict):
            raise _AttributionError("payload must be a dict")
        root = Path.cwd() if repo_root is None else Path(repo_root)
        change_folder = _resolve_active_change(payload, repo_root=root)
        if change_folder is None:
            result.metadata["reason"] = "no unambiguous active change"
            return result

        record = build_dispatch_record(
            payload,
            change_id=change_folder.name,
        )
        written_path = append_harness_record(change_folder, record)
        if written_path is None:
            result.metadata["reason"] = "telemetry record not written"
        else:
            result.metadata["path"] = str(written_path)
        return result
    except Exception as exc:  # noqa: BLE001 - hook boundary must remain nonblocking
        logger.warning(
            "harness telemetry attribution failed: %s; dispatch continues unchanged",
            exc,
        )
        result.metadata["reason"] = "telemetry attribution failed"
        return result


__all__ = [
    "HARNESS_SEGMENT_MAX_BYTES",
    "LAYER_TOKEN_BUDGETS",
    "MAX_HARNESS_SEGMENT_BYTES",
    "append_harness_record",
    "build_dispatch_record",
    "record_dispatch_telemetry",
    "stable_yaml",
]
