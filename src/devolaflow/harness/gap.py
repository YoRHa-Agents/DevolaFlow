"""Harness gap/coverage inventory across six built-in and custom axes.

The ``gap`` subcommand is the evaluator's inventory mode: it reuses the
``INSUFFICIENT`` machinery in reverse to report WHERE harness coverage is
missing instead of refusing to score. An absent ledger (or baselines
directory) is treated as evidence — the affected axes report ``GAP`` with an
explicit reason — while malformed inputs (unreadable axes-config, invalid
ledger records) fail loudly per S-5 and map to CLI exit code 2.

Custom change-level axes are declared in an ``--axes-config`` YAML document
(design §3.2); every custom axis MUST carry a machine probe (``file_exists``,
``command``, or ``ledger_query``) so no unverifiable "vibes" axis can enter
the report. Reports are loaded back via :func:`load_gap_report` so the
``--compare`` capability-review mode can diff two frozen snapshots through
:func:`compare_gap_reports` and render the archive artifact through
:func:`render_capability_review`. All comparison deltas are TREND-ONLY per
design decision 5 — they are recorded for review and never gate anything.
"""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

import yaml

from devolaflow.harness.aggregator import load_ledger_records
from devolaflow.harness.evaluator import (
    SIGNAL_KEYS,
    EvaluationError,
    SignalResult,
    collect_signals,
    evaluate_harness,
)
from devolaflow.harness.probe import load_probe_model_table

BUILTIN_GAP_AXES: Final[tuple[str, ...]] = (
    "observation",
    "evaluation",
    "probe",
    "baseline",
    "signal",
    "loop-closure",
)
COMMAND_TIMEOUT_CAP_SECONDS: Final[int] = 120

_LAYER_ORDER: Final[tuple[str, ...]] = ("L0", "L1", "L2")
_PROBE_KINDS: Final[tuple[str, ...]] = ("file_exists", "command", "ledger_query")
_AXIS_REQUIRED_KEYS: Final[frozenset[str]] = frozenset({"id", "probe"})
_AXIS_ALLOWED_KEYS: Final[frozenset[str]] = frozenset({"id", "title", "probe", "rationale"})
_SLUG_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_STDERR_TAIL_CHARS: Final[int] = 400
_FIXTURES_DIR: Final[Path] = Path("tests/fixtures/harness")
_BASELINES_DIR: Final[Path] = Path(".local/telemetry/baselines")
_BASELINE_GLOB: Final[str] = "harness_baseline_*.json"
_PROFILES_PATH: Final[Path] = Path("workflow-system/agent/context_profiles.yaml")
_LEDGER_ABSENT: Final[str] = "ledger absent"
_REPORT_KEYS: Final[tuple[str, ...]] = (
    "schema_version",
    "sampled_at",
    "axes",
    "auto_fill_rate",
    "insufficient_slots",
    "summary",
)
_STATUS_VALUES: Final[frozenset[str]] = frozenset({"COVERED", "PARTIAL", "GAP"})
_STATUS_RANK: Final[dict[str, int]] = {"GAP": 0, "PARTIAL": 1, "COVERED": 2}
_REVIEW_TREND_NOTE: Final[str] = (
    "Trend-only record (design decision 5): regressions are recorded for review, "
    "never gated — the gap exit code reflects current gaps only."
)

Runner = Callable[..., subprocess.CompletedProcess[str]]


class GapConfigError(ValueError):
    """A gap axes-config or gap-report document violates its explicit contract."""


def _config_error(path: Path | str, message: str) -> GapConfigError:
    return GapConfigError(f"{path}: {message}")


def _axis_entry(
    axis_id: str,
    *,
    builtin: bool,
    status: str,
    evidence: dict[str, Any],
    gaps: list[dict[str, str]],
    title: str | None = None,
    rationale: str | None = None,
) -> dict[str, Any]:
    entry: dict[str, Any] = {"id": axis_id}
    if title is not None:
        entry["title"] = title
    if rationale is not None:
        entry["rationale"] = rationale
    entry["builtin"] = builtin
    entry["status"] = status
    entry["evidence"] = evidence
    entry["gaps"] = gaps
    return entry


def _tri_status(full: bool, partial: bool) -> str:
    if full:
        return "COVERED"
    return "PARTIAL" if partial else "GAP"


def _status_counts(axes: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"covered": 0, "partial": 0, "gap": 0}
    for axis in axes:
        counts[axis["status"].lower()] += 1
    return counts


def _observation_axis(records: list[dict[str, Any]] | None) -> dict[str, Any]:
    if records is None:
        return _axis_entry(
            "observation",
            builtin=True,
            status="GAP",
            evidence={"ledger": "absent", "layers_present": [], "dispatch_records": 0},
            gaps=[{"item": "ledger", "reason": _LEDGER_ABSENT}],
        )
    layers = {record["layer"] for record in records if "event" not in record}
    present = [layer for layer in _LAYER_ORDER if layer in layers]
    missing = [layer for layer in _LAYER_ORDER if layer not in layers]
    return _axis_entry(
        "observation",
        builtin=True,
        status=_tri_status(not missing, bool(present)),
        evidence={
            "layers_present": present,
            "layers_missing": missing,
            "dispatch_records": sum("event" not in record for record in records),
        },
        gaps=[
            {"item": layer, "reason": f"no dispatch telemetry recorded for layer {layer}"}
            for layer in missing
        ],
    )


def _evaluation_axis(
    ledger: Path,
    records: list[dict[str, Any]] | None,
    signals: Mapping[str, SignalResult],
    *,
    repo_root: Path,
    base_ref: str,
) -> tuple[dict[str, Any], float, list[str]]:
    """Return the evaluation axis plus the top-level auto-fill facts it owns."""

    if records is None:
        axis = _axis_entry(
            "evaluation",
            builtin=True,
            status="GAP",
            evidence={"ledger": "absent"},
            gaps=[{"item": "evaluate_harness", "reason": _LEDGER_ABSENT}],
        )
        return axis, 0.0, []

    result = evaluate_harness(ledger, signals=signals, repo_root=repo_root, base_ref=base_ref)
    available_slots = 0
    total_slots = 0
    insufficient_slots: list[str] = []
    gaps: list[dict[str, str]] = []
    for entry in result["scores"]:
        for name, component in entry["metadata"]["subcomponents"].items():
            total_slots += 1
            if component["available"] is True:
                available_slots += 1
                continue
            slot = f"{entry['id']}.{name}"
            insufficient_slots.append(slot)
            gaps.append({"item": slot, "reason": component.get("error", "slot unavailable")})
    auto_fill_rate = float(result["auto_fill_rate"])
    axis = _axis_entry(
        "evaluation",
        builtin=True,
        status=_tri_status(auto_fill_rate == 1.0, auto_fill_rate > 0.0),
        evidence={
            "available_slots": available_slots,
            "total_slots": total_slots,
            "auto_fill_rate": auto_fill_rate,
            "verdict": result["verdict"],
        },
        gaps=gaps,
    )
    return axis, auto_fill_rate, insufficient_slots


def _probe_axis(repo_root: Path) -> dict[str, Any]:
    fixtures_dir = repo_root / _FIXTURES_DIR
    fixture_count = 0
    if fixtures_dir.is_dir():
        fixture_count = sum(
            1
            for path in fixtures_dir.iterdir()
            if path.is_file() and path.suffix.lower() in {".yaml", ".yml"}
        )
    table = load_probe_model_table(repo_root / _PROFILES_PATH)
    probe_models = [f"{entry.provider}:{entry.model}" for entry in table]
    gaps: list[dict[str, str]] = []
    if fixture_count == 0:
        gaps.append(
            {
                "item": "fixtures",
                "reason": f"no YAML probe fixtures under {_FIXTURES_DIR.as_posix()}",
            }
        )
    if not probe_models:
        gaps.append(
            {
                "item": "probe_models",
                "reason": f"meta.probe_models is not configured in {_PROFILES_PATH.as_posix()}",
            }
        )
    return _axis_entry(
        "probe",
        builtin=True,
        status=_tri_status(not gaps, fixture_count > 0 or bool(probe_models)),
        evidence={
            "fixtures_dir": _FIXTURES_DIR.as_posix(),
            "fixture_count": fixture_count,
            "probe_models": probe_models,
        },
        gaps=gaps,
    )


def _baseline_axis(repo_root: Path) -> dict[str, Any]:
    baselines_dir = repo_root / _BASELINES_DIR
    if baselines_dir.is_dir():
        baselines = sorted(
            path.name for path in baselines_dir.glob(_BASELINE_GLOB) if path.is_file()
        )
        reason = f"no settled {_BASELINE_GLOB} artifact in {_BASELINES_DIR.as_posix()}"
    else:
        baselines = []
        reason = f"baselines directory absent: {_BASELINES_DIR.as_posix()}"
    return _axis_entry(
        "baseline",
        builtin=True,
        status="COVERED" if baselines else "GAP",
        evidence={"baselines_dir": _BASELINES_DIR.as_posix(), "baselines": baselines},
        gaps=[] if baselines else [{"item": _BASELINE_GLOB, "reason": reason}],
    )


def _signal_axis(signals: Mapping[str, SignalResult]) -> dict[str, Any]:
    available = [key for key in SIGNAL_KEYS if signals[key].available]
    unavailable = [key for key in SIGNAL_KEYS if not signals[key].available]
    return _axis_entry(
        "signal",
        builtin=True,
        status=_tri_status(not unavailable, bool(available)),
        evidence={"available": available, "unavailable": unavailable},
        gaps=[
            {"item": key, "reason": signals[key].error or "signal unavailable"}
            for key in unavailable
        ],
    )


def _loop_closure_axis(records: list[dict[str, Any]] | None) -> dict[str, Any]:
    if records is None:
        return _axis_entry(
            "loop-closure",
            builtin=True,
            status="GAP",
            evidence={"ledger": "absent", "proposal_applied_events": 0},
            gaps=[{"item": "proposal_applied", "reason": _LEDGER_ABSENT}],
        )
    count = sum(record.get("event") == "proposal_applied" for record in records)
    return _axis_entry(
        "loop-closure",
        builtin=True,
        status="COVERED" if count else "GAP",
        evidence={"proposal_applied_events": count},
        gaps=(
            []
            if count
            else [
                {
                    "item": "proposal_applied",
                    "reason": "no proposal_applied event recorded in ledger",
                }
            ]
        ),
    )


def _validate_file_exists_spec(spec: dict[str, Any], *, path: Path, field: str) -> None:
    if set(spec) != {"path"}:
        raise _config_error(path, f"{field}.spec must contain exactly 'path'")
    value = spec["path"]
    if not isinstance(value, str) or not value.strip():
        raise _config_error(path, f"{field}.spec.path must be a non-empty string")
    candidate = Path(value)
    if candidate.is_absolute() or value.startswith("~") or ".." in candidate.parts:
        raise _config_error(path, f"{field}.spec.path must be repository-relative, got {value!r}")


def _validate_command_spec(spec: dict[str, Any], *, path: Path, field: str) -> None:
    if set(spec) != {"argv", "timeout_seconds"}:
        raise _config_error(
            path,
            f"{field}.spec must contain exactly 'argv' and 'timeout_seconds'",
        )
    argv = spec["argv"]
    if (
        not isinstance(argv, list)
        or not argv
        or any(not isinstance(item, str) or not item.strip() for item in argv)
    ):
        raise _config_error(
            path,
            f"{field}.spec.argv must be a non-empty list of non-empty strings",
        )
    timeout = spec["timeout_seconds"]
    if type(timeout) is not int or not 1 <= timeout <= COMMAND_TIMEOUT_CAP_SECONDS:
        raise _config_error(
            path,
            f"{field}.spec.timeout_seconds must be an integer in "
            f"[1, {COMMAND_TIMEOUT_CAP_SECONDS}]",
        )


def _validate_ledger_query_spec(spec: dict[str, Any], *, path: Path, field: str) -> None:
    extra = sorted(spec.keys() - {"event", "min_count"})
    if "event" not in spec or extra:
        raise _config_error(
            path,
            f"{field}.spec must contain 'event' and optionally 'min_count'; extra={extra}",
        )
    event = spec["event"]
    if not isinstance(event, str) or not event.strip():
        raise _config_error(path, f"{field}.spec.event must be a non-empty string")
    minimum = spec.get("min_count", 1)
    if type(minimum) is not int or minimum < 1:
        raise _config_error(path, f"{field}.spec.min_count must be an integer >= 1")


_SPEC_VALIDATORS: Final[dict[str, Callable[..., None]]] = {
    "file_exists": _validate_file_exists_spec,
    "command": _validate_command_spec,
    "ledger_query": _validate_ledger_query_spec,
}


def _validate_axis(
    axis: object,
    *,
    index: int,
    path: Path,
    seen: set[str],
) -> dict[str, Any]:
    field = f"axes[{index}]"
    if not isinstance(axis, dict):
        raise _config_error(path, f"{field} must be a mapping")
    missing = sorted(_AXIS_REQUIRED_KEYS - axis.keys())
    extra = sorted(axis.keys() - _AXIS_ALLOWED_KEYS)
    if missing or extra:
        raise _config_error(path, f"{field} keys mismatch; missing={missing}, extra={extra}")
    axis_id = axis["id"]
    if not isinstance(axis_id, str) or _SLUG_RE.fullmatch(axis_id) is None:
        raise _config_error(path, f"{field}.id must be a lowercase hyphenated slug")
    if axis_id in seen:
        raise _config_error(
            path,
            f"{field}.id {axis_id!r} collides with a built-in or already-declared axis",
        )
    seen.add(axis_id)
    for key in ("title", "rationale"):
        if key in axis and (not isinstance(axis[key], str) or not axis[key].strip()):
            raise _config_error(path, f"{field}.{key} must be a non-empty string when present")
    probe = axis["probe"]
    if not isinstance(probe, dict):
        raise _config_error(path, f"{field}.probe must be a mapping")
    probe_missing = sorted({"kind", "spec"} - probe.keys())
    probe_extra = sorted(probe.keys() - {"kind", "spec"})
    if probe_missing or probe_extra:
        raise _config_error(
            path,
            f"{field}.probe keys mismatch; missing={probe_missing}, extra={probe_extra}",
        )
    kind = probe["kind"]
    if kind not in _PROBE_KINDS:
        raise _config_error(
            path,
            f"{field}.probe.kind must be one of {list(_PROBE_KINDS)}; got {kind!r}",
        )
    spec = probe["spec"]
    if not isinstance(spec, dict):
        raise _config_error(path, f"{field}.probe.spec must be a mapping")
    _SPEC_VALIDATORS[kind](spec, path=path, field=f"{field}.probe")
    return axis


def _load_axes_config(source: str | Path) -> list[dict[str, Any]]:
    path = Path(source)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise _config_error(path, f"cannot read axes config: {exc}") from exc
    try:
        payload = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise _config_error(path, f"invalid axes config YAML: {exc}") from exc
    if not isinstance(payload, dict):
        raise _config_error(path, "axes config root must be a mapping")
    missing = sorted({"schema_version", "axes"} - payload.keys())
    extra = sorted(payload.keys() - {"schema_version", "axes"})
    if missing or extra:
        raise _config_error(path, f"axes config keys mismatch; missing={missing}, extra={extra}")
    if type(payload["schema_version"]) is not int or payload["schema_version"] != 1:
        raise _config_error(path, "schema_version must equal 1")
    axes = payload["axes"]
    if not isinstance(axes, list) or not axes:
        raise _config_error(path, "axes must be a non-empty list")
    seen = set(BUILTIN_GAP_AXES)
    return [
        _validate_axis(axis, index=index, path=path, seen=seen) for index, axis in enumerate(axes)
    ]


def _file_exists_probe(spec: dict[str, Any], *, repo_root: Path) -> tuple[str, dict, list]:
    exists = (repo_root / spec["path"]).exists()
    evidence = {"kind": "file_exists", "path": spec["path"], "exists": exists}
    if exists:
        return "COVERED", evidence, []
    return "GAP", evidence, [{"item": spec["path"], "reason": "path does not exist"}]


def _command_probe(
    spec: dict[str, Any],
    *,
    repo_root: Path,
    runner: Runner,
) -> tuple[str, dict, list]:
    argv = list(spec["argv"])
    timeout = spec["timeout_seconds"]
    evidence: dict[str, Any] = {"kind": "command", "argv": argv, "timeout_seconds": timeout}
    try:
        completed = runner(
            argv,
            cwd=str(repo_root),
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        reason = f"timeout after {timeout}s: {' '.join(argv)}"
        evidence["error"] = reason
        return "GAP", evidence, [{"item": argv[0], "reason": reason}]
    except OSError as exc:
        reason = f"unavailable executable for {argv[0]}: {exc}"
        evidence["error"] = reason
        return "GAP", evidence, [{"item": argv[0], "reason": reason}]
    evidence["returncode"] = completed.returncode
    if completed.returncode == 0:
        return "COVERED", evidence, []
    evidence["stderr_tail"] = (completed.stderr or "")[-_STDERR_TAIL_CHARS:]
    reason = f"command exited {completed.returncode}"
    return "GAP", evidence, [{"item": argv[0], "reason": reason}]


def _ledger_query_probe(
    spec: dict[str, Any],
    *,
    records: list[dict[str, Any]] | None,
) -> tuple[str, dict, list]:
    event = spec["event"]
    minimum = spec.get("min_count", 1)
    count = 0 if records is None else sum(record.get("event") == event for record in records)
    evidence: dict[str, Any] = {
        "kind": "ledger_query",
        "event": event,
        "min_count": minimum,
        "count": count,
    }
    if records is None:
        evidence["ledger"] = "absent"
        return "GAP", evidence, [{"item": event, "reason": _LEDGER_ABSENT}]
    if count >= minimum:
        return "COVERED", evidence, []
    reason = f"ledger has {count} {event!r} event(s); need >= {minimum}"
    return "GAP", evidence, [{"item": event, "reason": reason}]


def _custom_axis(
    axis: dict[str, Any],
    *,
    repo_root: Path,
    records: list[dict[str, Any]] | None,
    runner: Runner,
) -> dict[str, Any]:
    kind = axis["probe"]["kind"]
    spec = axis["probe"]["spec"]
    if kind == "file_exists":
        status, evidence, gaps = _file_exists_probe(spec, repo_root=repo_root)
    elif kind == "command":
        status, evidence, gaps = _command_probe(spec, repo_root=repo_root, runner=runner)
    else:
        status, evidence, gaps = _ledger_query_probe(spec, records=records)
    return _axis_entry(
        axis["id"],
        builtin=False,
        status=status,
        evidence=evidence,
        gaps=gaps,
        title=axis.get("title"),
        rationale=axis.get("rationale"),
    )


def _resolve_signals(
    signals: Mapping[str, SignalResult] | None,
    *,
    repo_root: Path,
    base_ref: str,
    runner: Runner | None,
) -> dict[str, SignalResult]:
    if signals is None:
        return collect_signals(repo_root, base_ref=base_ref, runner=runner)
    resolved: dict[str, SignalResult] = {}
    for key in SIGNAL_KEYS:
        value = signals.get(key)
        if value is None:
            resolved[key] = SignalResult(available=False, error=f"missing injected signal: {key}")
        elif isinstance(value, SignalResult):
            resolved[key] = value
        else:
            raise EvaluationError(f"injected gap signal {key} must be a SignalResult")
    return resolved


def build_gap_report(
    ledger: str | Path,
    *,
    repo_root: str | Path = ".",
    axes_config: str | Path | None = None,
    signals: Mapping[str, SignalResult] | None = None,
    base_ref: str = "HEAD~1",
    sampled_at: str | None = None,
    runner: Runner | None = None,
) -> dict[str, Any]:
    """Inventory harness coverage across the six built-in axes plus custom axes.

    An absent ledger is evidence, not an error: ledger-dependent axes report
    ``GAP`` with the reason ``"ledger absent"``. Malformed inputs fail loudly
    per S-5 — an invalid ledger record raises ``AggregationError`` and an
    invalid axes-config raises :class:`GapConfigError`. The returned mapping
    is deterministic and byte-stable across runs except for ``sampled_at``
    (injectable for frozen snapshots).
    """

    root = Path(repo_root)
    if not root.is_dir():
        raise EvaluationError(f"repo root does not exist or is not a directory: {root}")
    custom_axes = _load_axes_config(axes_config) if axes_config is not None else []
    ledger_path = Path(ledger)
    records = load_ledger_records(ledger_path) if ledger_path.exists() else None
    resolved_signals = _resolve_signals(signals, repo_root=root, base_ref=base_ref, runner=runner)

    evaluation_axis, auto_fill_rate, insufficient_slots = _evaluation_axis(
        ledger_path,
        records,
        resolved_signals,
        repo_root=root,
        base_ref=base_ref,
    )
    axes = [
        _observation_axis(records),
        evaluation_axis,
        _probe_axis(root),
        _baseline_axis(root),
        _signal_axis(resolved_signals),
        _loop_closure_axis(records),
    ]
    invoke = runner or subprocess.run
    axes.extend(
        _custom_axis(axis, repo_root=root, records=records, runner=invoke) for axis in custom_axes
    )
    return {
        "schema_version": 1,
        "sampled_at": sampled_at or datetime.now(UTC).isoformat(),
        "axes": axes,
        "auto_fill_rate": auto_fill_rate,
        "insufficient_slots": insufficient_slots,
        "summary": _status_counts(axes),
    }


def load_gap_report(source: str | Path) -> dict[str, Any]:
    """Load and validate one frozen gap report for comparison consumers.

    The ``--compare`` mode diffs two reports loaded through this path;
    validation pins the envelope keys, the schema version, and the
    per-axis ``id``/``status`` contract so a diff never runs on garbage.
    """

    path = Path(source)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise _config_error(path, f"cannot read gap report: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise _config_error(path, f"invalid gap report JSON: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise _config_error(path, "gap report root must be a mapping")
    missing = sorted(set(_REPORT_KEYS) - payload.keys())
    if missing:
        raise _config_error(path, f"gap report is missing key(s): {', '.join(missing)}")
    if payload["schema_version"] != 1:
        raise _config_error(path, "gap report schema_version must equal 1")
    axes = payload["axes"]
    if not isinstance(axes, list):
        raise _config_error(path, "gap report axes must be a list")
    for index, axis in enumerate(axes):
        if (
            not isinstance(axis, dict)
            or not isinstance(axis.get("id"), str)
            or axis.get("status") not in _STATUS_VALUES
        ):
            raise _config_error(
                path,
                f"gap report axes[{index}] must carry a string id and a COVERED/PARTIAL/GAP status",
            )
    return payload


def compare_gap_reports(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """Diff two validated gap-report envelopes into one capability delta.

    Both inputs MUST be validated gap-report envelopes — file loading goes
    through :func:`load_gap_report`. Every delta value is TREND-ONLY per
    design decision 5: the comparison never gates, and CLI exit codes keep
    reflecting the CURRENT report's gaps.

    Axes are matched by ``id``. An axis present only in ``after`` is newly
    tracked (``from`` is None); an axis present only in ``before`` is no
    longer tracked (``to`` is None) and listed under ``regressions``
    alongside status downgrades. Gap items are matched by their ``item``
    field and reproduced verbatim (C-3): items in ``before`` but not
    ``after`` are ``resolved_gaps`` (both-present axes only — a dropped
    axis is a regression, not a resolution), items in ``after`` but not
    ``before`` are ``new_gaps``. Summary deltas are recomputed from the
    validated per-axis statuses instead of trusting either report's
    ``summary`` block; an axis without a ``gaps`` list is treated as
    gap-free. Ordering is deterministic: before-report axis order first,
    then after-only axes in after-report order.
    """

    before_by_id = {axis["id"]: axis for axis in before["axes"]}
    after_by_id = {axis["id"]: axis for axis in after["axes"]}
    ordered_ids = [axis["id"] for axis in before["axes"]]
    ordered_ids += [axis["id"] for axis in after["axes"] if axis["id"] not in before_by_id]

    transitions: list[dict[str, Any]] = []
    regressions: list[dict[str, Any]] = []
    resolved_gaps: list[dict[str, str]] = []
    new_gaps: list[dict[str, str]] = []
    for axis_id in ordered_ids:
        source = before_by_id.get(axis_id)
        target = after_by_id.get(axis_id)
        from_status = None if source is None else source["status"]
        to_status = None if target is None else target["status"]
        transitions.append({"axis": axis_id, "from": from_status, "to": to_status})
        downgraded = (
            source is not None
            and target is not None
            and _STATUS_RANK[to_status] < _STATUS_RANK[from_status]
        )
        if (source is not None and target is None) or downgraded:
            regressions.append({"axis": axis_id, "from": from_status, "to": to_status})
        before_gaps = [] if source is None else source.get("gaps", [])
        after_gaps = [] if target is None else target.get("gaps", [])
        before_items = {gap["item"] for gap in before_gaps}
        after_items = {gap["item"] for gap in after_gaps}
        if source is not None and target is not None:
            resolved_gaps.extend(
                {"axis": axis_id, "item": gap["item"], "reason": gap["reason"]}
                for gap in before_gaps
                if gap["item"] not in after_items
            )
        new_gaps.extend(
            {"axis": axis_id, "item": gap["item"], "reason": gap["reason"]}
            for gap in after_gaps
            if gap["item"] not in before_items
        )

    before_counts = _status_counts(before["axes"])
    after_counts = _status_counts(after["axes"])
    return {
        "schema_version": 1,
        "sampled_at": {"before": before["sampled_at"], "after": after["sampled_at"]},
        "axis_transitions": transitions,
        "auto_fill_rate_delta": round(
            float(after["auto_fill_rate"]) - float(before["auto_fill_rate"]), 4
        ),
        "resolved_gaps": resolved_gaps,
        "new_gaps": new_gaps,
        "regressions": regressions,
        "summary_delta": {
            key: after_counts[key] - before_counts[key] for key in ("covered", "partial", "gap")
        },
    }


def render_capability_review(
    delta: Mapping[str, Any],
    *,
    before_ref: str,
    after_ref: str,
) -> str:
    """Render one capability-review markdown artifact for the archive.

    Byte-stable for a given delta: the only timestamps cited are the
    compared reports' own ``sampled_at`` values — no new timestamp is
    generated. The output stays lean by construction so the C-9 evidence
    ceiling (10 KB/file) holds for realistic axis counts. Regressions are
    explicitly labelled trend-only per design decision 5.
    """

    sampled_at = delta["sampled_at"]
    lines = [
        "# Harness Capability Review",
        "",
        "## Sources",
        "",
        f"- before: `{before_ref}` (sampled_at {sampled_at['before']})",
        f"- after: `{after_ref}` (sampled_at {sampled_at['after']})",
        "",
        "## Axis Transitions",
        "",
        "| Axis | From | To |",
        "| --- | --- | --- |",
    ]
    for transition in delta["axis_transitions"]:
        from_cell = transition["from"] or "(untracked)"
        to_cell = transition["to"] or "(untracked)"
        lines.append(f"| {transition['axis']} | {from_cell} | {to_cell} |")
    lines += [
        "",
        "## Auto-fill Delta",
        "",
        f"- auto_fill_rate delta: {delta['auto_fill_rate_delta']:+.4f}",
        "",
        "## Resolved Gaps",
        "",
    ]
    lines += [
        f"- `{gap['axis']}` / `{gap['item']}`: {gap['reason']}" for gap in delta["resolved_gaps"]
    ] or ["- none"]
    lines += [
        "",
        "## Regressions",
        "",
        _REVIEW_TREND_NOTE,
        "",
    ]
    regression_lines = [
        (
            f"- status downgrade `{entry['axis']}`: {entry['from']} -> {entry['to']}"
            if entry["to"] is not None
            else f"- no longer tracked `{entry['axis']}` (was {entry['from']})"
        )
        for entry in delta["regressions"]
    ]
    regression_lines += [
        f"- new gap `{gap['axis']}` / `{gap['item']}`: {gap['reason']}" for gap in delta["new_gaps"]
    ]
    lines += regression_lines or ["- none"]
    summary_delta = delta["summary_delta"]
    lines += [
        "",
        "## Summary",
        "",
        f"- covered: {summary_delta['covered']:+d}",
        f"- partial: {summary_delta['partial']:+d}",
        f"- gap: {summary_delta['gap']:+d}",
        "",
    ]
    return "\n".join(lines)


__all__ = [
    "BUILTIN_GAP_AXES",
    "COMMAND_TIMEOUT_CAP_SECONDS",
    "GapConfigError",
    "build_gap_report",
    "compare_gap_reports",
    "load_gap_report",
    "render_capability_review",
]
