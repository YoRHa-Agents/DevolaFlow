"""Deterministic W-3 six-dimension evaluation over harness telemetry."""

from __future__ import annotations

import ast
import json
import math
import re
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Final

from devolaflow.harness.aggregator import (
    aggregate_metric_observations,
    aggregate_records,
    load_ledger_records,
)
from devolaflow.harness.telemetry import MetricObservationError, validate_metric_observation
from devolaflow.task_adaptive_selector import estimate_tokens

DIMENSION_WEIGHTS: Final[dict[str, float]] = {
    "code_quality": 0.20,
    "architecture_rationality": 0.20,
    "test_adequacy": 0.20,
    "maintainability": 0.15,
    "compatibility": 0.10,
    "performance_impact": 0.15,
}
MEASUREMENT_KEYS: Final[tuple[str, ...]] = (
    "agents_md_tokens",
    "suite_wall_seconds",
    "cjk_violations",
    "ghost_loc",
)
SIGNAL_KEYS: Final[tuple[str, ...]] = (
    "ruff_lint",
    "ruff_format",
    "test_suite",
    "coverage_pct",
    "layout_invariant",
    "compatibility_suite",
    "w17_new_tests",
    "docstring_coverage_pct",
    *MEASUREMENT_KEYS,
)
DEFAULT_THRESHOLD: Final[float] = 8.5
DEFAULT_CROSS_VALIDATION_DELTA: Final[float] = 1.0
HISTORICAL_COMPANION_METHOD: Final[str] = "historical_w3_hybrid_companion_v15_final"

_COVERAGE_RE: Final[re.Pattern[str]] = re.compile(
    r"^TOTAL\s+\d+\s+\d+\s+(\d+(?:\.\d+)?)%",
    re.MULTILINE,
)
_ADDED_TEST_RE: Final[re.Pattern[str]] = re.compile(
    r"^\+\s*(?:async\s+)?def\s+test_[A-Za-z0-9_]*\s*\(",
    re.MULTILINE,
)
_BINARY_SIGNALS: Final[frozenset[str]] = frozenset(
    {
        "ruff_lint",
        "ruff_format",
        "test_suite",
        "layout_invariant",
        "compatibility_suite",
    }
)
_CJK_RE: Final[re.Pattern[str]] = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
_AGENT_TEXT_PATHS: Final[tuple[Path, ...]] = (
    Path("AGENTS.md"),
    Path("workflow-system/agent/SKILL.md"),
)

Runner = Callable[..., subprocess.CompletedProcess[str]]


class EvaluationError(ValueError):
    """Evaluation inputs or signal values violate the evaluator contract."""


@dataclass(frozen=True)
class SignalResult:
    """One explicit, typed evaluator signal."""

    available: bool
    value: bool | float | int | None = None
    error: str = ""
    provenance: Mapping[str, Any] | None = None

    def as_subcomponent(self, score: float) -> dict[str, Any]:
        """Render the fixture-compatible subcomponent envelope."""

        rendered: dict[str, Any] = {
            "score": round(score, 2),
            "available": self.available,
        }
        if self.value is not None:
            rendered["value"] = self.value
        if self.error:
            rendered["error"] = self.error
        return rendered


def _unavailable(error: str) -> SignalResult:
    return SignalResult(available=False, error=error)


def _run_probe(
    argv: list[str],
    *,
    repo_root: Path,
    timeout: int,
    runner: Runner,
) -> tuple[subprocess.CompletedProcess[str] | None, str]:
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
    except subprocess.TimeoutExpired as exc:
        return None, f"timeout after {exc.timeout}s: {' '.join(argv)}"
    except OSError as exc:
        return None, f"unavailable executable for {argv[0]}: {exc}"
    return completed, ""


def _binary_probe(
    argv: list[str],
    *,
    repo_root: Path,
    timeout: int,
    runner: Runner,
) -> SignalResult:
    completed, error = _run_probe(
        argv,
        repo_root=repo_root,
        timeout=timeout,
        runner=runner,
    )
    if completed is None:
        return _unavailable(error)
    return SignalResult(available=True, value=completed.returncode == 0)


def _docstring_coverage(repo_root: Path) -> SignalResult:
    source_root = repo_root / "src" / "devolaflow"
    if not source_root.is_dir():
        return _unavailable(f"source directory unavailable: {source_root}")
    documented = 0
    total = 0
    try:
        for path in sorted(source_root.rglob("*.py")):
            module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            total += 1
            documented += int(ast.get_docstring(module) is not None)
            for node in ast.walk(module):
                if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name.startswith("_"):
                        continue
                    total += 1
                    documented += int(ast.get_docstring(node) is not None)
    except (OSError, SyntaxError, UnicodeError) as exc:
        return _unavailable(f"docstring scan failed: {exc}")
    value = 100.0 * documented / total if total else 0.0
    return SignalResult(available=True, value=value)


def _agents_md_tokens(repo_root: Path) -> SignalResult:
    path = repo_root / "AGENTS.md"
    try:
        return SignalResult(available=True, value=estimate_tokens(path.read_text(encoding="utf-8")))
    except (OSError, UnicodeError) as exc:
        return _unavailable(f"AGENTS.md token scan failed: {exc}")


def _cjk_violations(repo_root: Path) -> SignalResult:
    paths = [path for path in _AGENT_TEXT_PATHS if (repo_root / path).is_file()]
    reference_root = repo_root / "workflow-system" / "agent" / "references"
    if reference_root.is_dir():
        paths.extend(sorted(reference_root.glob("*.md")))
    if not paths:
        return _unavailable("agent-facing text surfaces unavailable")
    try:
        count = sum(
            len(_CJK_RE.findall((repo_root / path).read_text(encoding="utf-8"))) for path in paths
        )
    except (OSError, UnicodeError) as exc:
        return _unavailable(f"CJK scan failed: {exc}")
    return SignalResult(available=True, value=count)


def _ghost_loc(repo_root: Path) -> SignalResult:
    ghost_root = repo_root / "tests" / "ghost"
    if not ghost_root.is_dir():
        return _unavailable(f"ghost test directory unavailable: {ghost_root}")
    paths = sorted(ghost_root.rglob("*.py"))
    if not paths:
        return _unavailable("ghost test directory contains no Python files")
    try:
        loc = sum(
            1
            for path in paths
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        )
    except (OSError, UnicodeError) as exc:
        return _unavailable(f"ghost LOC scan failed: {exc}")
    return SignalResult(available=True, value=loc)


def collect_signals(
    repo_root: str | Path,
    *,
    base_ref: str,
    runner: Runner | None = None,
) -> dict[str, SignalResult]:
    """Collect all evaluator signals through fixed, bounded argv probes."""

    root = Path(repo_root)
    if not root.is_dir():
        raise EvaluationError(f"repo root does not exist or is not a directory: {root}")
    if not isinstance(base_ref, str) or not base_ref.strip():
        raise EvaluationError("base_ref must be a non-empty string")
    invoke = runner or subprocess.run

    ruff_lint = _binary_probe(
        ["ruff", "check", "src/", "tests/"],
        repo_root=root,
        timeout=60,
        runner=invoke,
    )
    ruff_format = _binary_probe(
        ["ruff", "format", "--check", "src/", "tests/"],
        repo_root=root,
        timeout=60,
        runner=invoke,
    )
    suite_started = time.perf_counter()
    coverage_run, coverage_error = _run_probe(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/",
            "-q",
            "--cov=devolaflow",
            "--cov-report=term",
        ],
        repo_root=root,
        timeout=300,
        runner=invoke,
    )
    suite_elapsed = time.perf_counter() - suite_started
    if coverage_run is None:
        test_suite = _unavailable(coverage_error)
        coverage = _unavailable(coverage_error)
    else:
        test_suite = SignalResult(available=True, value=coverage_run.returncode == 0)
        coverage_match = _COVERAGE_RE.search(
            (coverage_run.stdout or "") + "\n" + (coverage_run.stderr or "")
        )
        coverage = (
            SignalResult(available=True, value=float(coverage_match.group(1)))
            if coverage_match
            else _unavailable(
                "coverage parse failed: expected a 'TOTAL ... NN%' line "
                f"(returncode={coverage_run.returncode})"
            )
        )

    layout = _binary_probe(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_layout_invariant_multi_baseline.py",
            "-q",
            "--no-cov",
        ],
        repo_root=root,
        timeout=60,
        runner=invoke,
    )
    compatibility = _binary_probe(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_version.py",
            "-q",
            "--no-cov",
        ],
        repo_root=root,
        timeout=120,
        runner=invoke,
    )
    w17_run, w17_error = _run_probe(
        ["git", "diff", base_ref, "--", "tests/"],
        repo_root=root,
        timeout=30,
        runner=invoke,
    )
    if w17_run is None:
        w17 = _unavailable(w17_error)
    elif w17_run.returncode != 0:
        w17 = _unavailable(
            f"W-17 probe failed (returncode={w17_run.returncode}, "
            f"command={' '.join(['git', 'diff', base_ref, '--', 'tests/'])!r}): "
            f"{(w17_run.stderr or w17_run.stdout or '').strip() or 'no diagnostic output'}"
        )
    else:
        w17 = SignalResult(available=True, value=len(_ADDED_TEST_RE.findall(w17_run.stdout or "")))
    measurements: dict[str, SignalResult] = {
        "agents_md_tokens": _agents_md_tokens(root),
        "suite_wall_seconds": (
            SignalResult(available=True, value=suite_elapsed)
            if coverage_run is not None
            else _unavailable(coverage_error)
        ),
        "cjk_violations": _cjk_violations(root),
        "ghost_loc": _ghost_loc(root),
    }
    return {
        "ruff_lint": ruff_lint,
        "ruff_format": ruff_format,
        "test_suite": test_suite,
        "coverage_pct": coverage,
        "layout_invariant": layout,
        "compatibility_suite": compatibility,
        "w17_new_tests": w17,
        "docstring_coverage_pct": _docstring_coverage(root),
        **measurements,
    }


def _coerce_binary(value: object, *, key: str) -> bool:
    if type(value) is bool:
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"pass", "passed", "clean", "true"}:
            return True
        if normalized in {"fail", "failed", "dirty", "false"}:
            return False
    raise EvaluationError(f"signal {key} must contain a boolean/pass/fail value")


def _coerce_number(value: object, *, key: str) -> float | int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EvaluationError(f"signal {key} must contain a numeric value")
    if not math.isfinite(float(value)):
        raise EvaluationError(f"signal {key} must contain a finite numeric value")
    return value


def normalize_signals(signals: Mapping[str, object]) -> dict[str, SignalResult]:
    """Normalize injected JSON signals; absent entries become explicit unavailable states."""

    if not isinstance(signals, Mapping):
        raise EvaluationError("signals must be a JSON object")
    normalized: dict[str, SignalResult] = {}
    for key in SIGNAL_KEYS:
        if key not in signals:
            normalized[key] = _unavailable(f"missing injected signal: {key}")
            continue
        raw = signals[key]
        provenance: Mapping[str, Any] | None = None
        if isinstance(raw, Mapping):
            if "observation" in raw:
                try:
                    observation = validate_metric_observation(raw["observation"])
                except MetricObservationError as exc:
                    raise EvaluationError(f"signal {key} observation is invalid: {exc}") from exc
                if observation["metric"] != key:
                    raise EvaluationError(f"signal {key} observation metric must equal {key!r}")
                provenance = observation
                raw = observation["value"]
            else:
                available = raw.get("available")
                if type(available) is not bool:
                    raise EvaluationError(f"signal {key}.available must be a boolean")
                if not available:
                    error = raw.get("error")
                    if not isinstance(error, str) or not error.strip():
                        raise EvaluationError(
                            f"unavailable signal {key} must include a non-empty error"
                        )
                    normalized[key] = _unavailable(error)
                    continue
                if "value" not in raw:
                    raise EvaluationError(f"available signal {key} must include value")
                raw = raw["value"]

        value: bool | float | int
        if key in _BINARY_SIGNALS:
            value = _coerce_binary(raw, key=key)
        else:
            value = _coerce_number(raw, key=key)
        normalized[key] = SignalResult(available=True, value=value, provenance=provenance)
    return normalized


def load_signals(source: str | Path) -> dict[str, SignalResult]:
    """Read and normalize one injected JSON signal document."""

    path = Path(source)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise EvaluationError(f"cannot read signals file {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise EvaluationError(f"{path}: invalid signals JSON: {exc.msg}") from exc
    if isinstance(payload, dict) and set(payload) == {"signals"}:
        payload = payload["signals"]
    return normalize_signals(payload)


def _clamp(value: float) -> float:
    return min(1.0, max(0.0, value))


def _binary_score(signal: SignalResult) -> float:
    return 10.0 if signal.available and signal.value is True else 0.0


def _coverage_score(signal: SignalResult) -> float:
    if not signal.available:
        return 0.0
    return 10.0 * _clamp((float(signal.value) - 60.0) / 20.0)


def _docstrings_score(signal: SignalResult) -> float:
    if not signal.available:
        return 0.0
    return 10.0 * _clamp(float(signal.value) / 100.0)


def _ratio_score(value: float) -> float:
    return 10.0 * _clamp(value)


def _w17_score(signal: SignalResult) -> float:
    return 10.0 if signal.available and float(signal.value) <= 30.0 else 0.0


def _p95_headroom_score(utilization: float) -> float:
    if utilization <= 1.0:
        return 10.0
    if utilization >= 1.2:
        return 0.0
    return 10.0 * (1.2 - utilization) / 0.2


def _latest_timestamp(records: list[dict[str, Any]]) -> str:
    def parsed(record: dict[str, Any]) -> tuple[datetime, str]:
        value = record.get("ts") or record.get("captured_at")
        if not isinstance(value, str):
            raise EvaluationError("record has no evaluation timestamp")
        return datetime.fromisoformat(value.replace("Z", "+00:00")), value

    latest = max(records, key=parsed)
    return latest.get("ts") or latest["captured_at"]


def _signal_component(signal: SignalResult, score: float) -> dict[str, Any]:
    return signal.as_subcomponent(score)


def _metric_component(value: float, score: float) -> dict[str, Any]:
    return {
        "score": round(score, 2),
        "available": True,
        "value": value,
    }


def _coerce_measurement(value: object, *, key: str) -> float | int:
    if isinstance(value, SignalResult):
        if not value.available:
            raise EvaluationError(value.error or f"measurement {key} unavailable")
        value = value.value
    coerced = _coerce_number(value, key=key)
    if float(coerced) < 0:
        raise EvaluationError(f"measurement {key} must be non-negative")
    return coerced


def _telemetry_measurements(summary: Mapping[str, Any]) -> dict[str, SignalResult]:
    raw_measurements = summary.get("measurements")
    if not isinstance(raw_measurements, Mapping):
        return {
            key: _unavailable(f"historical telemetry missing measurement: {key}")
            for key in MEASUREMENT_KEYS
        }
    resolved: dict[str, SignalResult] = {}
    for key in MEASUREMENT_KEYS:
        entry = raw_measurements.get(key)
        if not isinstance(entry, Mapping) or entry.get("mean") is None:
            resolved[key] = _unavailable(f"historical telemetry missing measurement: {key}")
        else:
            resolved[key] = SignalResult(
                available=True,
                value=_coerce_measurement(entry["mean"], key=key),
                provenance=(
                    entry.get("provenance")
                    if isinstance(entry.get("provenance"), Mapping)
                    else None
                ),
            )
    return resolved


def _resolve_measurements(
    summary: Mapping[str, Any],
    *,
    injected: Mapping[str, object] | None,
    collected: Mapping[str, SignalResult] | None,
) -> tuple[dict[str, SignalResult], dict[str, str]]:
    telemetry = _telemetry_measurements(summary)
    resolved: dict[str, SignalResult] = {}
    sources: dict[str, str] = {}
    for key in MEASUREMENT_KEYS:
        if telemetry[key].available:
            resolved[key] = telemetry[key]
            sources[key] = "telemetry"
            continue
        if injected is not None and key in injected:
            raw = injected[key]
            if isinstance(raw, SignalResult):
                resolved[key] = raw
                sources[key] = "injected"
                continue
            if isinstance(raw, Mapping):
                if "observation" in raw:
                    try:
                        observation = validate_metric_observation(raw["observation"])
                    except MetricObservationError as exc:
                        raise EvaluationError(
                            f"measurement {key} observation is invalid: {exc}"
                        ) from exc
                    if observation["metric"] != key:
                        raise EvaluationError(
                            f"measurement {key} observation metric must equal {key!r}"
                        )
                    resolved[key] = SignalResult(
                        available=True,
                        value=observation["value"],
                        provenance=observation,
                    )
                    sources[key] = "injected"
                    continue
                available = raw.get("available")
                if type(available) is not bool:
                    raise EvaluationError(f"measurement {key}.available must be a boolean")
                if not available:
                    error = raw.get("error")
                    if not isinstance(error, str) or not error.strip():
                        raise EvaluationError(
                            f"unavailable measurement {key} must include a non-empty error"
                        )
                    resolved[key] = _unavailable(error)
                else:
                    if "value" not in raw:
                        raise EvaluationError(f"available measurement {key} must include value")
                    resolved[key] = SignalResult(
                        available=True,
                        value=_coerce_measurement(raw["value"], key=key),
                    )
            else:
                resolved[key] = SignalResult(
                    available=True,
                    value=_coerce_measurement(raw, key=key),
                )
            sources[key] = "injected"
            continue
        if collected is not None and key in collected:
            resolved[key] = collected[key]
            sources[key] = "evaluator" if collected[key].available else "unavailable"
            continue
        resolved[key] = telemetry[key]
        sources[key] = "unavailable"
    return resolved, sources


def _render_measurements(
    measurements: Mapping[str, SignalResult],
    sources: Mapping[str, str],
    summary: Mapping[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    rendered: dict[str, dict[str, Any]] = {}
    for key in MEASUREMENT_KEYS:
        signal = measurements[key]
        entry: dict[str, Any] = {
            "available": signal.available,
            "value": signal.value if signal.available else None,
            "status": "AVAILABLE" if signal.available else "INSUFFICIENT",
            "source": sources[key],
        }
        if signal.error:
            entry["error"] = signal.error
        provenance = signal.provenance
        if provenance is None and isinstance(summary, Mapping):
            raw_entry = summary.get(key)
            if isinstance(raw_entry, Mapping) and isinstance(raw_entry.get("provenance"), list):
                provenance = {"observations": raw_entry["provenance"]}
        if provenance is not None:
            entry["provenance"] = provenance
        rendered[key] = entry
    return rendered


def _mean_available(subcomponents: Mapping[str, Mapping[str, Any]]) -> float:
    scores = [
        float(component["score"])
        for component in subcomponents.values()
        if component["available"] is True
    ]
    return sum(scores) / len(scores) if scores else 0.0


def evaluate_harness(
    ledger: str | Path,
    *,
    signals: Mapping[str, object] | Mapping[str, SignalResult] | None = None,
    repo_root: str | Path = ".",
    base_ref: str = "HEAD~1",
    threshold: float = DEFAULT_THRESHOLD,
    sampled_at: str | None = None,
    runner: Runner | None = None,
    baseline: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Aggregate a ledger and evaluate the exact deterministic W-3 rubric."""

    if (
        isinstance(threshold, bool)
        or not isinstance(threshold, (int, float))
        or not math.isfinite(float(threshold))
        or not 0.0 <= float(threshold) <= 10.0
    ):
        raise EvaluationError("threshold must be a finite number in [0, 10]")

    records = load_ledger_records(ledger)
    summary = aggregate_records(records)
    collected_signals: dict[str, SignalResult] | None = None
    if signals is None:
        collected_signals = collect_signals(repo_root, base_ref=base_ref, runner=runner)
        resolved_signals = {key: collected_signals[key] for key in SIGNAL_KEYS}
    elif all(isinstance(value, SignalResult) for value in signals.values()):
        resolved_signals = {
            key: (
                signals[key] if key in signals else _unavailable(f"missing injected signal: {key}")
            )
            for key in SIGNAL_KEYS
        }
    else:
        resolved_signals = normalize_signals(signals)
    measurement_signals, measurement_sources = _resolve_measurements(
        summary,
        injected=signals,
        collected=collected_signals,
    )

    quantifiable_ratio = float(summary["constraints"]["quantifiable_ratio"])
    budget_compliance = float(summary["tokens"]["budget_compliance_ratio"])
    p95_utilization = float(summary["tokens"]["p95_budget_utilization"])
    components: dict[str, dict[str, dict[str, Any]]] = {
        "code_quality": {
            "ruff_lint": _signal_component(
                resolved_signals["ruff_lint"],
                _binary_score(resolved_signals["ruff_lint"]),
            ),
            "ruff_format": _signal_component(
                resolved_signals["ruff_format"],
                _binary_score(resolved_signals["ruff_format"]),
            ),
            "coverage": _signal_component(
                resolved_signals["coverage_pct"],
                _coverage_score(resolved_signals["coverage_pct"]),
            ),
        },
        "architecture_rationality": {
            "layout_invariant": _signal_component(
                resolved_signals["layout_invariant"],
                _binary_score(resolved_signals["layout_invariant"]),
            ),
            "quantifiable_ratio": _metric_component(
                quantifiable_ratio,
                _ratio_score(quantifiable_ratio),
            ),
        },
        "test_adequacy": {
            "test_suite": _signal_component(
                resolved_signals["test_suite"],
                _binary_score(resolved_signals["test_suite"]),
            ),
            "coverage": _signal_component(
                resolved_signals["coverage_pct"],
                _coverage_score(resolved_signals["coverage_pct"]),
            ),
            "w17": _signal_component(
                resolved_signals["w17_new_tests"],
                _w17_score(resolved_signals["w17_new_tests"]),
            ),
        },
        "maintainability": {
            "ruff_format": _signal_component(
                resolved_signals["ruff_format"],
                _binary_score(resolved_signals["ruff_format"]),
            ),
            "docstrings": _signal_component(
                resolved_signals["docstring_coverage_pct"],
                _docstrings_score(resolved_signals["docstring_coverage_pct"]),
            ),
        },
        "compatibility": {
            "layout_invariant": _signal_component(
                resolved_signals["layout_invariant"],
                _binary_score(resolved_signals["layout_invariant"]),
            ),
            "compatibility_suite": _signal_component(
                resolved_signals["compatibility_suite"],
                _binary_score(resolved_signals["compatibility_suite"]),
            ),
        },
        "performance_impact": {
            "budget_compliance_ratio": _metric_component(
                budget_compliance,
                _ratio_score(budget_compliance),
            ),
            "p95_headroom": _metric_component(
                p95_utilization,
                _p95_headroom_score(p95_utilization),
            ),
        },
    }

    scores: list[dict[str, Any]] = []
    available_slots = 0
    total_slots = 0
    for dimension, weight in DIMENSION_WEIGHTS.items():
        subcomponents = components[dimension]
        available_slots += sum(
            component["available"] is True for component in subcomponents.values()
        )
        total_slots += len(subcomponents)
        scores.append(
            {
                "id": dimension,
                "score": round(_mean_available(subcomponents), 2),
                "weight": weight,
                "metadata": {"subcomponents": subcomponents},
            }
        )

    composite = round(sum(item["score"] * item["weight"] for item in scores), 2)
    complete = available_slots == total_slots
    verdict = (
        "INSUFFICIENT"
        if not complete
        else "READY"
        if composite >= float(threshold)
        else "NOT_READY"
    )
    suggestions: list[dict[str, str]] = []
    for item in scores:
        unavailable = [
            name
            for name, component in item["metadata"]["subcomponents"].items()
            if component["available"] is False
        ]
        if unavailable:
            reason = f"unavailable inputs: {', '.join(unavailable)}"
        elif item["score"] < float(threshold):
            reason = f"score {item['score']:.2f} below threshold {float(threshold):.2f}"
        else:
            continue
        suggestions.append({"dimension": item["id"], "reason": reason})

    result = {
        "schema_version": 1,
        "sampled_at": sampled_at or _latest_timestamp(records),
        "threshold": float(threshold),
        "scores": scores,
        "composite": composite,
        "auto_fill_rate": round(available_slots / total_slots, 4),
        "verdict": verdict,
        "harness_summary": summary,
        "measurements": _render_measurements(
            measurement_signals,
            measurement_sources,
            summary["measurements"],
        ),
        "suggestions": suggestions,
    }
    if baseline is not None:
        if isinstance(baseline, (str, bytes)) or not isinstance(baseline, Sequence):
            raise EvaluationError("baseline must be a sequence of metric observations")
        current = summary.get("metric_observations", [])
        if not isinstance(current, list):
            current = []
        result["metric_comparison"] = aggregate_metric_observations(list(baseline), current)
    return result


def _score_vector(payload: Mapping[str, Any], *, label: str) -> dict[str, float]:
    raw_scores = payload.get("scores")
    if not isinstance(raw_scores, list):
        raise EvaluationError(f"{label}.scores must be a list")

    scores: dict[str, float] = {}
    for index, entry in enumerate(raw_scores):
        if not isinstance(entry, Mapping):
            raise EvaluationError(f"{label}.scores[{index}] must be an object")
        dimension = entry.get("id")
        if not isinstance(dimension, str) or not dimension:
            raise EvaluationError(f"{label}.scores[{index}].id must be a non-empty string")
        if dimension in scores:
            raise EvaluationError(f"{label}.scores contains duplicate id {dimension!r}")
        raw_score = entry.get("score")
        if (
            isinstance(raw_score, bool)
            or not isinstance(raw_score, (int, float))
            or not math.isfinite(float(raw_score))
            or not 0.0 <= float(raw_score) <= 10.0
        ):
            raise EvaluationError(
                f"{label}.scores[{index}].score must be a finite number in [0, 10]"
            )
        scores[dimension] = float(raw_score)

    expected = set(DIMENSION_WEIGHTS)
    actual = set(scores)
    if actual != expected:
        raise EvaluationError(
            f"{label}.scores ids must exactly match {list(DIMENSION_WEIGHTS)}; "
            f"missing={sorted(expected - actual)}, extra={sorted(actual - expected)}"
        )
    return scores


def _historical_provenance(companion: Mapping[str, Any]) -> dict[str, Any]:
    sampled_at = companion.get("sampled_at")
    if not isinstance(sampled_at, str) or not sampled_at.strip():
        raise EvaluationError("historical companion sampled_at must be a non-empty string")
    if companion.get("metric_count") != len(DIMENSION_WEIGHTS):
        raise EvaluationError(
            f"historical companion metric_count must equal {len(DIMENSION_WEIGHTS)}"
        )
    methodology = companion.get("methodology")
    if not isinstance(methodology, str) or not methodology.strip():
        raise EvaluationError("historical companion methodology must be a non-empty string")
    limitation = companion.get("limitation")
    if (
        not isinstance(limitation, str)
        or "not a raw NineS six-dimensional output" not in limitation
    ):
        raise EvaluationError(
            "historical companion limitation must state that it is "
            "not a raw NineS six-dimensional output"
        )

    raw_sources = companion.get("sources")
    if not isinstance(raw_sources, list) or not raw_sources:
        raise EvaluationError("historical companion sources must be a non-empty list")
    sources: list[dict[str, str]] = []
    for index, source in enumerate(raw_sources):
        if not isinstance(source, Mapping):
            raise EvaluationError(f"historical companion sources[{index}] must be an object")
        path = source.get("path")
        digest = source.get("sha256")
        if (
            not isinstance(path, str)
            or not path
            or Path(path).is_absolute()
            or path.startswith("~")
        ):
            raise EvaluationError(
                f"historical companion sources[{index}].path must be repository-relative"
            )
        if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise EvaluationError(
                f"historical companion sources[{index}].sha256 must be lowercase SHA-256"
            )
        sources.append({"path": path, "sha256": digest})

    source_context = companion.get("source_context")
    if source_context is not None and not isinstance(source_context, Mapping):
        raise EvaluationError("historical companion source_context must be an object")
    return {
        "sampled_at": sampled_at,
        "metric_count": len(DIMENSION_WEIGHTS),
        "methodology": methodology,
        "limitation": limitation,
        "sources": sources,
        "source_context": dict(source_context or {}),
    }


def compare_historical_companion(
    current: Mapping[str, Any],
    historical: Mapping[str, Any],
    *,
    max_abs_delta: float = DEFAULT_CROSS_VALIDATION_DELTA,
) -> dict[str, Any]:
    """Compare a complete current W-3 result with an explicit historical companion."""

    if not isinstance(current, Mapping):
        raise EvaluationError("current evaluation must be an object")
    if not isinstance(historical, Mapping):
        raise EvaluationError("historical companion must be an object")
    if (
        isinstance(max_abs_delta, bool)
        or not isinstance(max_abs_delta, (int, float))
        or not math.isfinite(float(max_abs_delta))
        or not 0.0 <= float(max_abs_delta) <= 10.0
    ):
        raise EvaluationError("max_abs_delta must be a finite number in [0, 10]")
    auto_fill_rate = current.get("auto_fill_rate")
    if (
        isinstance(auto_fill_rate, bool)
        or not isinstance(auto_fill_rate, (int, float))
        or float(auto_fill_rate) != 1.0
    ):
        raise EvaluationError("current evaluation auto_fill_rate must equal 1.0")
    if current.get("verdict") not in {"READY", "NOT_READY"}:
        raise EvaluationError("current evaluation verdict must be READY or NOT_READY")
    if historical.get("method") != HISTORICAL_COMPANION_METHOD:
        raise EvaluationError(
            f"historical companion method must equal {HISTORICAL_COMPANION_METHOD!r}"
        )

    current_scores = _score_vector(current, label="current evaluation")
    historical_scores = _score_vector(historical, label="historical companion")
    historical_provenance = _historical_provenance(historical)
    limit = float(max_abs_delta)
    comparisons: list[dict[str, Any]] = []
    for dimension in DIMENSION_WEIGHTS:
        current_score = current_scores[dimension]
        historical_score = historical_scores[dimension]
        delta = abs(current_score - historical_score)
        comparisons.append(
            {
                "id": dimension,
                "current_score": current_score,
                "historical_score": historical_score,
                "abs_delta": round(delta, 2),
                "within_limit": delta <= limit,
            }
        )

    current_provenance = current.get("provenance")
    if current_provenance is not None and not isinstance(current_provenance, Mapping):
        raise EvaluationError("current evaluation provenance must be an object when present")
    verdict = "PASS" if all(comparison["within_limit"] for comparison in comparisons) else "FAIL"
    return {
        "schema_version": 1,
        "method": "historical_w3_hybrid_cross_validation",
        "criterion": {"max_abs_delta_per_dimension": limit},
        "current": {
            "sampled_at": current.get("sampled_at"),
            "auto_fill_rate": 1.0,
            "verdict": current["verdict"],
            "provenance": dict(current_provenance or {}),
        },
        "historical": {
            "method": HISTORICAL_COMPANION_METHOD,
            **historical_provenance,
        },
        "comparisons": comparisons,
        "max_abs_delta": max(comparison["abs_delta"] for comparison in comparisons),
        "verdict": verdict,
    }


def render_evaluation(result: Mapping[str, Any]) -> str:
    """Render stable, byte-identical JSON for a deterministic result."""

    return json.dumps(result, ensure_ascii=False, indent=2, separators=(",", ": ")) + "\n"


__all__ = [
    "DEFAULT_CROSS_VALIDATION_DELTA",
    "DEFAULT_THRESHOLD",
    "DIMENSION_WEIGHTS",
    "HISTORICAL_COMPANION_METHOD",
    "MEASUREMENT_KEYS",
    "SIGNAL_KEYS",
    "EvaluationError",
    "SignalResult",
    "collect_signals",
    "compare_historical_companion",
    "evaluate_harness",
    "load_signals",
    "normalize_signals",
    "render_evaluation",
]
