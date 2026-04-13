"""NineS low-level CLI wrappers for eval and analyze commands.

Higher-level research and skill-iteration utilities live in
``devolaflow.nines.researcher``.  Gate scoring should use the standard
gate mechanism (``devolaflow.gate.scorer.evaluate_gate``), not NineS.
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

FALLBACK_SCORE = 100.0
DIMENSION_KEYS = ("test_quality", "code_review", "architecture", "benchmark")


@dataclass
class NinesScorerConfig:
    """Maps NineS commands to gate dimensions (``None`` → fallback)."""

    test_suite: str | None = None
    review_path: str | None = None
    architecture_path: str | None = None
    benchmark_suite: str | None = None
    timeout: int = 120
    extra_eval_args: list[str] = field(default_factory=list)
    extra_analyze_args: list[str] = field(default_factory=list)


def _run_cli(cmd: list[str], timeout: int) -> dict:
    """Run a CLI command and return parsed JSON, or ``{}`` on failure."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        logger.warning("NineS command timed out after %ds: %s", timeout, cmd)
        return {}
    except OSError as exc:
        logger.warning("NineS command failed to start: %s — %s", cmd, exc)
        return {}

    if result.returncode != 0:
        logger.warning(
            "NineS exited %d: %s stderr=%s",
            result.returncode,
            cmd,
            result.stderr.strip(),
        )
        return {}

    try:
        return json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("Failed to parse NineS JSON: %s — %s", exc, cmd)
        return {}


def run_nines_eval(
    artifact_path: str,
    scorer: str = "composite",
    extra_args: list[str] | None = None,
    timeout: int = 120,
) -> dict:
    """Run ``nines eval <artifact_path>`` and return parsed JSON."""
    cmd = ["nines", "eval", artifact_path, "--scorer", scorer, "--format", "json"]
    if extra_args:
        cmd.extend(extra_args)
    return _run_cli(cmd, timeout)


def run_nines_analyze(
    target_path: str,
    depth: str = "deep",
    extra_args: list[str] | None = None,
    timeout: int = 120,
) -> dict:
    """Run ``nines analyze <target_path>`` and return parsed JSON."""
    cmd = ["nines", "analyze", target_path, "--depth", depth, "--format", "json"]
    if extra_args:
        cmd.extend(extra_args)
    return _run_cli(cmd, timeout)


def _score_or_fallback(data: dict, key: str = "score") -> float:
    """Extract a numeric score from NineS JSON, falling back on miss."""
    val = data.get(key)
    if val is None:
        return FALLBACK_SCORE
    try:
        return float(val)
    except (TypeError, ValueError):
        return FALLBACK_SCORE


def nines_dimension_scores(
    config: NinesScorerConfig,
    artifact_path: str,
) -> dict[str, float]:
    """Return gate-dimension scores via NineS CLI (fallback on failure)."""
    scores: dict[str, float] = {}
    t = config.timeout

    if config.test_suite:
        data = run_nines_eval(
            config.test_suite,
            scorer="composite",
            extra_args=config.extra_eval_args or None,
            timeout=t,
        )
        scores["test_quality"] = _score_or_fallback(data)
    else:
        scores["test_quality"] = FALLBACK_SCORE

    if config.review_path:
        data = run_nines_analyze(
            config.review_path,
            depth="deep",
            extra_args=config.extra_analyze_args or None,
            timeout=t,
        )
        scores["code_review"] = _score_or_fallback(data)
    else:
        scores["code_review"] = FALLBACK_SCORE

    if config.architecture_path:
        data = run_nines_analyze(
            config.architecture_path,
            depth="deep",
            extra_args=["--agent-impact", *(config.extra_analyze_args or [])],
            timeout=t,
        )
        scores["architecture"] = _score_or_fallback(data)
    else:
        scores["architecture"] = FALLBACK_SCORE

    if config.benchmark_suite:
        data = run_nines_eval(
            config.benchmark_suite,
            scorer="composite",
            extra_args=["--parallel", "4", "--report", *(config.extra_eval_args or [])],
            timeout=t,
        )
        scores["benchmark"] = _score_or_fallback(data)
    else:
        scores["benchmark"] = FALLBACK_SCORE

    return scores
