"""NineS research and skill-iteration utilities.

Provides structured access to NineS collection, analysis, and
self-iteration capabilities for research-only and skill-optimization
workflows.  NOT for gate scoring — use the standard gate mechanism
(``devolaflow.gate.scorer.evaluate_gate``) for quality gates.
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class NinesResearchConfig:
    """Configuration for NineS research operations."""

    search_queries: list[str] = field(default_factory=list)
    analysis_targets: list[str] = field(default_factory=list)
    eval_suite: str | None = None
    iteration_max_rounds: int = 5
    convergence_threshold: float = 0.02
    timeout: int = 120


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


def collect_research(
    query: str,
    limit: int = 20,
    source: str = "github",
    timeout: int = 120,
) -> dict:
    """Run ``nines collect`` for research gathering.

    Parameters
    ----------
    query:
        Search query string passed to ``nines collect``.
    limit:
        Maximum number of results to collect.
    source:
        Collection source (e.g. ``"github"``, ``"arxiv"``).
    timeout:
        CLI timeout in seconds.
    """
    cmd = [
        "nines",
        "collect",
        source,
        query,
        "--limit",
        str(limit),
        "--format",
        "json",
    ]
    return _run_cli(cmd, timeout)


def analyze_target(
    target: str,
    depth: str = "deep",
    decompose: bool = True,
    timeout: int = 120,
) -> dict:
    """Run ``nines analyze`` for deep codebase/artifact understanding.

    Parameters
    ----------
    target:
        File or directory path to analyze.
    depth:
        Analysis depth (``"shallow"`` or ``"deep"``).
    decompose:
        If *True*, add ``--decompose --index`` flags.
    timeout:
        CLI timeout in seconds.
    """
    cmd = ["nines", "analyze", target, "--depth", depth, "--format", "json"]
    if decompose:
        cmd.extend(["--decompose", "--index"])
    return _run_cli(cmd, timeout)


def run_self_evaluation(
    dimensions: str = "all",
    timeout: int = 120,
) -> dict:
    """Run ``nines self-eval`` for agent self-assessment.

    Parameters
    ----------
    dimensions:
        Comma-separated dimension list or ``"all"``.
    timeout:
        CLI timeout in seconds.
    """
    cmd = ["nines", "self-eval", "--dimensions", dimensions, "--format", "json"]
    return _run_cli(cmd, timeout)


def run_skill_iteration(
    max_rounds: int = 5,
    convergence_threshold: float = 0.02,
    timeout: int = 300,
) -> dict:
    """Run ``nines iterate`` for MAPIM self-improvement cycle.

    Parameters
    ----------
    max_rounds:
        Maximum number of improvement iterations.
    convergence_threshold:
        Stop when score delta drops below this value.
    timeout:
        CLI timeout in seconds.
    """
    cmd = [
        "nines",
        "iterate",
        "--max-rounds",
        str(max_rounds),
        "--convergence-threshold",
        str(convergence_threshold),
        "--format",
        "json",
    ]
    return _run_cli(cmd, timeout)
