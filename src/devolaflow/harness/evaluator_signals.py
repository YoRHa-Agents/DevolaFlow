"""Signal collection and normalization for the deterministic harness evaluator."""

from __future__ import annotations

import ast
import json
import math
import re
import subprocess
import sys
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from devolaflow.harness.evaluation_contract import EvaluationError
from devolaflow.harness.telemetry import (
    AGENTS_MD_TOKEN_FIELD,
    LEGACY_AGENTS_MD_TOKEN_FIELD,
    MetricObservationError,
    validate_metric_observation,
)
from devolaflow.task_adaptive_selector import estimate_tokens

MEASUREMENT_KEYS: Final[tuple[str, ...]] = (
    AGENTS_MD_TOKEN_FIELD,
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
_LEGACY_SIGNAL_ALIASES: Final[dict[str, str]] = {
    LEGACY_AGENTS_MD_TOKEN_FIELD: AGENTS_MD_TOKEN_FIELD,
}

Runner = Callable[..., subprocess.CompletedProcess[str]]


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


def _estimated_agents_md_tokens(repo_root: Path) -> SignalResult:
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
        AGENTS_MD_TOKEN_FIELD: _estimated_agents_md_tokens(root),
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
    normalized_input = dict(signals)
    for legacy, canonical in _LEGACY_SIGNAL_ALIASES.items():
        if canonical not in normalized_input and legacy in normalized_input:
            normalized_input[canonical] = normalized_input[legacy]
    normalized: dict[str, SignalResult] = {}
    for key in SIGNAL_KEYS:
        if key not in normalized_input:
            normalized[key] = _unavailable(f"missing injected signal: {key}")
            continue
        raw = normalized_input[key]
        provenance: Mapping[str, Any] | None = None
        if isinstance(raw, Mapping):
            if "observation" in raw:
                try:
                    observation = validate_metric_observation(raw["observation"])
                except MetricObservationError as exc:
                    raise EvaluationError(f"signal {key} observation is invalid: {exc}") from exc
                if (
                    observation["metric"] == LEGACY_AGENTS_MD_TOKEN_FIELD
                    and key == AGENTS_MD_TOKEN_FIELD
                ):
                    observation = {**observation, "metric": key}
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
