"""NineS research and skill-iteration utilities.

Provides structured access to NineS collection, analysis, and
self-iteration capabilities for research-only and skill-optimization
workflows.  NOT for gate scoring — use the standard gate mechanism
(``devolaflow.gate.scorer.evaluate_gate``) for quality gates.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

from devolaflow.nines._cli import run_nines_cli as _run_cli

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
        "-f",
        "json",
        "collect",
        "--source",
        source,
        "--query",
        query,
        "--max-results",
        str(limit),
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
        If *True*, enable ``--agent-impact`` and ``--keypoints`` (v2 replacements
        for the removed ``--decompose --index`` flags).
    timeout:
        CLI timeout in seconds.
    """
    cmd = [
        "nines",
        "-f",
        "json",
        "analyze",
        "--target-path",
        target,
        "--depth",
        depth,
    ]
    if decompose:
        cmd.extend(["--agent-impact", "--keypoints"])
    return _run_cli(cmd, timeout)


def run_self_evaluation(
    *,
    project_root: str | None = None,
    src_dir: str | None = None,
    test_dir: str | None = None,
    capability_only: bool = False,
    baseline_version: str | None = None,
    timeout: int = 120,
    dimensions: str | None = None,
) -> dict:
    """Run ``nines self-eval`` for agent self-assessment.

    Parameters
    ----------
    project_root:
        Project root directory for coverage measurement.
    src_dir:
        Source directory for module/docstring/lint analysis.
    test_dir:
        Test directory for test discovery.
    capability_only:
        Run only capability evaluators, skip hygiene.
    baseline_version:
        Version tag for baseline comparison.
    timeout:
        CLI timeout in seconds.
    dimensions:
        Ignored (v1 compat). The ``--dimensions`` flag was removed in v2.
    """
    cmd = ["nines", "-f", "json", "self-eval"]
    if project_root:
        cmd.extend(["--project-root", project_root])
    if src_dir:
        cmd.extend(["--src-dir", src_dir])
    if test_dir:
        cmd.extend(["--test-dir", test_dir])
    if capability_only:
        cmd.append("--capability-only")
    if baseline_version:
        cmd.extend(["--baseline-version", baseline_version])
    return _run_cli(cmd, timeout)


def run_skill_iteration(
    max_rounds: int = 5,
    convergence_threshold: float = 0.02,
    timeout: int = 300,
    *,
    project_root: str | None = None,
    src_dir: str | None = None,
    test_dir: str | None = None,
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
    project_root:
        Project root directory.
    src_dir:
        Source directory for analysis.
    test_dir:
        Test directory.
    """
    cmd = [
        "nines",
        "-f",
        "json",
        "iterate",
        "--max-rounds",
        str(max_rounds),
        "--threshold",
        str(convergence_threshold),
    ]
    if project_root:
        cmd.extend(["--project-root", project_root])
    if src_dir:
        cmd.extend(["--src-dir", src_dir])
    if test_dir:
        cmd.extend(["--test-dir", test_dir])
    return _run_cli(cmd, timeout)


def run_nines_benchmark(
    target_path: str,
    *,
    rounds: int | None = None,
    convergence_threshold: float | None = None,
    output_dir: str | None = None,
    suite_id: str | None = None,
    tasks_path: str | None = None,
    timeout: int = 300,
) -> dict:
    """Run ``nines benchmark`` — full analysis/benchmark/evaluate pipeline.

    Parameters
    ----------
    target_path:
        Path to the repository to analyze.
    rounds:
        Number of evaluation rounds.
    convergence_threshold:
        Score convergence threshold.
    output_dir:
        Directory for output artifacts.
    suite_id:
        Benchmark suite identifier.
    tasks_path:
        Path to custom TOML task definitions.
    timeout:
        CLI timeout in seconds.
    """
    cmd = ["nines", "-f", "json", "benchmark", "--target-path", target_path]
    if rounds is not None:
        cmd.extend(["--rounds", str(rounds)])
    if convergence_threshold is not None:
        cmd.extend(["--convergence-threshold", str(convergence_threshold)])
    if output_dir:
        cmd.extend(["--output-dir", output_dir])
    if suite_id:
        cmd.extend(["--suite-id", suite_id])
    if tasks_path:
        cmd.extend(["--tasks-path", tasks_path])
    return _run_cli(cmd, timeout)


def run_nines_update(
    *,
    check_only: bool = False,
    skip_skills: bool = False,
    target: str | None = None,
    is_global: bool = False,
    timeout: int = 120,
) -> dict:
    """Run ``nines update`` — check for and install NineS updates.

    Parameters
    ----------
    check_only:
        Only check if an update is available, don't install.
    skip_skills:
        Skip skill file refresh after update.
    target:
        Which skill targets to refresh (cursor/claude/codex/copilot/all).
    is_global:
        Refresh skill files in user home directory instead of current project.
    timeout:
        CLI timeout in seconds.
    """
    cmd = ["nines", "-f", "json", "update"]
    if check_only:
        cmd.append("--check")
    if skip_skills:
        cmd.append("--skip-skills")
    if target:
        cmd.extend(["--target", target])
    if is_global:
        cmd.append("--global")
    return _run_cli(cmd, timeout)


# ---------------------------------------------------------------------------
# v2 self-improvement loop (C1)
# ---------------------------------------------------------------------------


@dataclass
class SelfImproveResult:
    """Result of a single self-improvement loop invocation."""

    rounds_executed: int = 0
    initial_score: float = 0.0
    final_score: float = 0.0
    converged: bool = False
    benchmark_output: dict = field(default_factory=dict)
    error: str = ""


def _run_v2_self_eval(
    project_root: str,
    src_dir: str,
    test_dir: str,
    timeout: int = 120,
) -> dict:
    """Run NineS v2 ``self-eval`` with project-scoped flags."""
    cmd = [
        "nines",
        "-f",
        "json",
        "self-eval",
        "--project-root",
        project_root,
        "--src-dir",
        src_dir,
        "--test-dir",
        test_dir,
    ]
    return _run_cli(cmd, timeout)


def _run_v2_iterate(
    project_root: str,
    src_dir: str,
    test_dir: str,
    max_rounds: int = 3,
    threshold: float = 0.05,
    timeout: int = 300,
) -> dict:
    """Run NineS v2 ``iterate`` with project-scoped flags."""
    cmd = [
        "nines",
        "-f",
        "json",
        "iterate",
        "--project-root",
        project_root,
        "--src-dir",
        src_dir,
        "--test-dir",
        test_dir,
        "--max-rounds",
        str(max_rounds),
        "--threshold",
        str(threshold),
    ]
    return _run_cli(cmd, timeout)


def _run_v2_benchmark(
    target_path: str,
    output_dir: str,
    timeout: int = 120,
) -> dict:
    """Run NineS v2 ``benchmark`` with target path and output directory."""
    cmd = [
        "nines",
        "-f",
        "json",
        "benchmark",
        "--target-path",
        target_path,
        "--output-dir",
        output_dir,
    ]
    return _run_cli(cmd, timeout)


def run_self_improve_loop(
    project_root: str,
    src_dir: str,
    test_dir: str,
    max_rounds: int = 3,
    threshold: float = 0.05,
    benchmark_output_dir: str | None = None,
    timeout: int = 300,
) -> SelfImproveResult:
    """Orchestrate the NineS v2 self-eval -> iterate -> benchmark loop.

    Parameters
    ----------
    project_root:
        Absolute path to the project root directory.
    src_dir:
        Relative (to *project_root*) or absolute path to the source directory.
    test_dir:
        Relative (to *project_root*) or absolute path to the test directory.
    max_rounds:
        Maximum improvement iterations passed to ``nines iterate``.
    threshold:
        Convergence threshold — stop when score delta drops below this.
    benchmark_output_dir:
        Directory for benchmark artifacts.  When *None*, benchmarking is skipped.
    timeout:
        CLI timeout in seconds for each sub-command.
    """
    result = SelfImproveResult()

    eval_out = _run_v2_self_eval(project_root, src_dir, test_dir, timeout=timeout)
    if not eval_out:
        result.error = "self-eval returned empty result"
        logger.warning("Self-improve loop: %s", result.error)
        return result

    result.initial_score = float(eval_out.get("score", eval_out.get("overall_score", 0)))

    iterate_out = _run_v2_iterate(
        project_root,
        src_dir,
        test_dir,
        max_rounds=max_rounds,
        threshold=threshold,
        timeout=timeout,
    )
    if not iterate_out:
        result.error = "iterate returned empty result"
        logger.warning("Self-improve loop: %s", result.error)
        return result

    result.rounds_executed = int(iterate_out.get("rounds", iterate_out.get("rounds_executed", 0)))
    result.final_score = float(iterate_out.get("final_score", iterate_out.get("score", 0)))
    result.converged = bool(iterate_out.get("converged", False))

    if benchmark_output_dir:
        bench_out = _run_v2_benchmark(
            target_path=project_root,
            output_dir=benchmark_output_dir,
            timeout=timeout,
        )
        result.benchmark_output = bench_out

    return result


# ---------------------------------------------------------------------------
# Reference-dependency refresh (C3)
# ---------------------------------------------------------------------------


def _load_reference_deps(deps_path: str) -> dict | None:
    """Load and parse a reference-dependencies YAML file.

    Returns ``None`` (and logs a WARNING) when PyYAML is missing, when the
    file is absent, or when the file is empty/parses to a falsy value.
    """
    from pathlib import Path

    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        logger.warning("PyYAML not installed — cannot refresh reference dependency")
        return None

    path = Path(deps_path)
    if not path.exists():
        logger.warning("reference-dependencies.yaml not found at %s", deps_path)
        return None

    data = yaml.safe_load(path.read_text())
    if not data:
        return None
    return data


def _apply_dep_updates(
    entry: dict,
    new_version: str | None,
    new_patterns: list[str] | None,
) -> None:
    """Mutate *entry* in place with the supplied version / patterns / timestamp.

    ``new_version`` overwrites ``last_known_version`` when not None.
    ``new_patterns`` extends (does not replace) ``key_patterns``, skipping
    duplicates. ``last_checked`` is always refreshed to today's UTC date.
    """
    if new_version is not None:
        entry["last_known_version"] = new_version
    if new_patterns:
        existing = entry.get("key_patterns", [])
        for pat in new_patterns:
            if pat not in existing:
                existing.append(pat)
        entry["key_patterns"] = existing
    entry["last_checked"] = datetime.now(UTC).strftime("%Y-%m-%d")


def _persist_reference_deps(deps_path: str, data: dict) -> None:
    """Serialise *data* back to *deps_path* using the canonical YAML style."""
    from pathlib import Path

    import yaml  # type: ignore[import-untyped]

    yaml_text = yaml.dump(
        data,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
    )
    Path(deps_path).write_text(yaml_text)


def refresh_reference_dependency(
    dep_id: str,
    deps_path: str,
    new_version: str | None = None,
    new_patterns: list[str] | None = None,
) -> bool:
    """Update a tracked dependency entry in *reference-dependencies.yaml*.

    Reads the YAML file, finds the entry matching *dep_id* in either
    ``active_tracking`` or ``periodic_monitoring``, applies updates, and
    writes the file back.  Returns *True* if the entry was found and updated.

    Parameters
    ----------
    dep_id:
        The ``id`` field of the dependency to update.
    deps_path:
        Filesystem path to ``reference-dependencies.yaml``.
    new_version:
        If given, updates ``last_known_version``.
    new_patterns:
        If given, **extends** (not replaces) the ``key_patterns`` list.
    """
    data = _load_reference_deps(deps_path)
    if data is None:
        return False

    for section_key in ("active_tracking", "periodic_monitoring"):
        entries = data.get(section_key) or []
        for entry in entries:
            if entry.get("id") != dep_id:
                continue
            _apply_dep_updates(entry, new_version, new_patterns)
            _persist_reference_deps(deps_path, data)
            logger.info("Updated reference dependency: %s", dep_id)
            return True

    logger.warning("Dependency %s not found in %s", dep_id, deps_path)
    return False
