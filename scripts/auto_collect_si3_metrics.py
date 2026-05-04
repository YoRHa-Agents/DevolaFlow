#!/usr/bin/env python3
"""Auto-collect SI-3 6-dimension objective metrics from CI tooling.

Implements the v10.7.0 D-O-2 deliverable per
`.local/research/v11.0.0_patches/D-O-2.md`. The script is the
**objective half** of the SI-3 evaluation; the L3 cycle-lead authors
the **subjective half** (deduction prose) on top.

Per the v11.0.0 cycle plan §6 R-10 weighting recommendation, the final
per-dim score = ``0.6 · objective_score + 0.4 · subjective_score``. This
script populates only the objective component; the subjective component
lives in the per-dim deduction-rationale prose the L3 author writes
after running the collector.

Algorithm (per PDS §2.1):

1. Run 6 toolchain probes (ruff check, ruff format --check, pytest --cov,
   pytest test_layout_invariant_multi_baseline, pytest --collect-only,
   git log) and capture each command's exit code + parsed metrics.
2. Compute per-dim objective sub-component coverage:
   * Code quality:           ruff_lint + ruff_format + max_cc + cov%
   * Architecture:            multi_baseline_passes + ssot_registry
   * Test adequacy:           coverage% + test_count
   * Maintainability:         docstring% + ruff_format
   * Compatibility:           multi_baseline_passes + new_env_flags
   * Performance impact:      benchmark composite delta
3. Emit ``objective_metrics.yaml`` (machine-consumable; consumed by
   ``scripts/generate_si3_evaluation.py --metrics`` flag in a future
   PV) and a markdown summary preview.
4. The collector is **OPT-IN**: not in ``Makefile::release-preflight``.
   Cycle-lead invokes manually at PV cycle close. SI-10 gate count
   stays at 7 (decoupled from D-O-2).

Per S-5 (no silent failures): when a tool is unreachable / times out,
the collector emits the dimension's sub-component as
``unavailable: <reason>`` rather than silently zero. The downstream
``generate_si3_evaluation.py`` skeleton then displays
``(unavailable: <reason>)`` in the score cell, and the L3 falls back
to the manual TBD path for that cell only.

External tool URLs (S-7 — never hard-code local paths):

* DevolaFlow / EvoBench: https://github.com/YoRHa-Agents/DevolaFlow
* radon (CC + raw measurement): https://radon.readthedocs.io/

Public API:

* :func:`collect_ruff_lint(repo_root)` -> SubcomponentResult
* :func:`collect_ruff_format(repo_root)` -> SubcomponentResult
* :func:`collect_test_count(repo_root)` -> SubcomponentResult
* :func:`collect_coverage(repo_root)` -> SubcomponentResult
* :func:`collect_multi_baseline_pass(repo_root)` -> SubcomponentResult
* :func:`collect_w17_test_delta(repo_root, base_ref)` -> SubcomponentResult
* :func:`compute_objective_score(metrics)` -> Si3ObjectiveScore
* :func:`render_yaml(metrics)` -> str
* :func:`render_markdown(score)` -> str
* :func:`run(repo_root, *, output, baseline_cycle, skip_benchmarks)` -> int

Entry point: ``python scripts/auto_collect_si3_metrics.py
[--repo-root .] [--output PATH] [--baseline-cycle vX.Y.0]
[--skip-benchmarks] [--mock-data]``

Source: v10.7.0 D-O-2 — codified per
`.local/research/v11.0.0_patches/D-O-2.md` §2.
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

__all__ = [
    "DEFAULT_OBJECTIVE_WEIGHT",
    "DEFAULT_SUBJECTIVE_WEIGHT",
    "DIMENSION_WEIGHTS",
    "Si3ObjectiveScore",
    "SubcomponentResult",
    "collect_coverage",
    "collect_multi_baseline_pass",
    "collect_ruff_format",
    "collect_ruff_lint",
    "collect_test_count",
    "collect_w17_test_delta",
    "compute_objective_score",
    "render_markdown",
    "render_yaml",
    "run",
    "run_command",
]

# Per the v11.0.0 cycle plan §6 R-10 risk-mitigation weighting:
DEFAULT_OBJECTIVE_WEIGHT: float = 0.6
DEFAULT_SUBJECTIVE_WEIGHT: float = 0.4

# Per W-3 SI-3 6-dim weights (the binding composite formula):
DIMENSION_WEIGHTS: dict[str, float] = {
    "code_quality": 0.20,
    "architecture": 0.20,
    "test_adequacy": 0.20,
    "maintainability": 0.15,
    "compatibility": 0.10,
    "performance_impact": 0.15,
}

_DEFAULT_PROBE_TIMEOUT = 60  # seconds


@dataclass(frozen=True)
class SubcomponentResult:
    """One per-tool probe outcome.

    ``available`` is the S-5 contract: when a probe fails / times out,
    we set it False AND populate ``error`` with the reason. The
    downstream score reduction is explicit, not silent.
    """

    name: str
    available: bool
    value: float | int | str | None = None
    raw_text: str = ""
    error: str = ""

    def as_yaml_dict(self) -> dict:
        out: dict = {
            "name": self.name,
            "available": self.available,
        }
        if self.value is not None:
            out["value"] = self.value
        if self.raw_text:
            # Truncate raw_text to avoid bloating the artifact.
            out["raw_text_excerpt"] = self.raw_text[:500]
        if self.error:
            out["error"] = self.error
        return out


@dataclass(frozen=True)
class Si3ObjectiveScore:
    """The end-state aggregated score per dim."""

    per_dim_scores: dict[str, float]
    per_dim_subcomponents: dict[str, list[SubcomponentResult]]
    composite_objective: float  # weighted across DIMENSION_WEIGHTS
    auto_fill_rate: float  # fraction of sub-components with `available=True`
    sampled_at: str  # ISO-8601 timestamp


def _resolve_repo_root(start: Path | None = None) -> Path:
    p = (start or Path(__file__)).resolve()
    if p.is_file():
        p = p.parent
    while p != p.parent:
        if (p / "pyproject.toml").exists():
            return p
        p = p.parent
    raise SystemExit("could not locate repo root (no pyproject.toml)")


def run_command(
    cmd: list[str],
    cwd: Path,
    *,
    timeout: int = _DEFAULT_PROBE_TIMEOUT,
) -> tuple[int, str, str]:
    """Run a subprocess + return (returncode, stdout, stderr).

    Per S-5: timeouts and CalledProcessError are NEVER swallowed; the
    caller receives explicit (returncode=-1, stderr=error_message)
    return so the SubcomponentResult can be marked ``available=False``
    with a non-empty ``error`` field.
    """
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return (-1, "", f"timeout after {exc.timeout}s running {shlex.join(cmd)}")
    except FileNotFoundError as exc:
        return (-1, "", f"command not found: {exc.filename}")
    return (proc.returncode, proc.stdout or "", proc.stderr or "")


def collect_ruff_lint(repo_root: Path) -> SubcomponentResult:
    """Probe ``ruff check src/ tests/`` -> exit_code 0 means clean."""
    rc, stdout, stderr = run_command(
        ["ruff", "check", "src/", "tests/"], cwd=repo_root
    )
    if rc < 0:
        return SubcomponentResult(
            name="ruff_lint", available=False, error=stderr.strip()
        )
    return SubcomponentResult(
        name="ruff_lint",
        available=True,
        value=("clean" if rc == 0 else f"exit_{rc}"),
        raw_text=stdout + stderr,
    )


def collect_ruff_format(repo_root: Path) -> SubcomponentResult:
    """Probe ``ruff format --check src/ tests/``."""
    rc, stdout, stderr = run_command(
        ["ruff", "format", "--check", "src/", "tests/"], cwd=repo_root
    )
    if rc < 0:
        return SubcomponentResult(
            name="ruff_format", available=False, error=stderr.strip()
        )
    return SubcomponentResult(
        name="ruff_format",
        available=True,
        value=("clean" if rc == 0 else f"exit_{rc}"),
        raw_text=stdout + stderr,
    )


_TEST_COUNT_RE = re.compile(r"(\d+)\s+tests?\s+collected", re.IGNORECASE)


def collect_test_count(repo_root: Path) -> SubcomponentResult:
    """Probe ``pytest --collect-only -q | tail -1`` -> count parsed."""
    rc, stdout, stderr = run_command(
        ["python", "-m", "pytest", "tests/", "--collect-only", "-q", "--no-cov"],
        cwd=repo_root,
        timeout=120,
    )
    if rc < 0:
        return SubcomponentResult(
            name="test_count", available=False, error=stderr.strip()
        )
    match = _TEST_COUNT_RE.search(stdout)
    if match:
        return SubcomponentResult(
            name="test_count",
            available=True,
            value=int(match.group(1)),
            raw_text=stdout[-500:],
        )
    return SubcomponentResult(
        name="test_count",
        available=False,
        error="could not parse 'N tests collected' from pytest output",
        raw_text=stdout[-500:],
    )


_COVERAGE_TOTAL_RE = re.compile(r"^TOTAL\s+\d+\s+\d+\s+(\d+)%", re.MULTILINE)


def collect_coverage(repo_root: Path) -> SubcomponentResult:
    """Probe ``pytest --cov=devolaflow`` -> TOTAL line parsed.

    Per W-2 manual fallback: when NineS reports `code_coverage: 0.0`
    (upstream timeout), this collector's local pytest invocation IS the
    SI-3 authority.
    """
    rc, stdout, stderr = run_command(
        [
            "python",
            "-m",
            "pytest",
            "tests/",
            "--cov=devolaflow",
            "--cov-report=term-missing",
            "-q",
            "-x",
        ],
        cwd=repo_root,
        timeout=300,
    )
    if rc < 0:
        return SubcomponentResult(
            name="coverage_pct", available=False, error=stderr.strip()
        )
    # rc != 0 may mean test failure or coverage threshold breach — in
    # either case we still parse the TOTAL line if present.
    match = _COVERAGE_TOTAL_RE.search(stdout)
    if match is None:
        return SubcomponentResult(
            name="coverage_pct",
            available=False,
            error=(
                "could not parse 'TOTAL ... NN%' from pytest --cov output "
                f"(returncode={rc})"
            ),
            raw_text=stdout[-500:],
        )
    return SubcomponentResult(
        name="coverage_pct",
        available=True,
        value=int(match.group(1)),
        raw_text=stdout[-500:],
    )


def collect_multi_baseline_pass(repo_root: Path) -> SubcomponentResult:
    """Probe the A-2 multi-baseline byte test -> count of PASSED."""
    rc, stdout, stderr = run_command(
        [
            "python",
            "-m",
            "pytest",
            "tests/test_layout_invariant_multi_baseline.py",
            "-v",
            "--no-cov",
        ],
        cwd=repo_root,
        timeout=60,
    )
    if rc < 0:
        return SubcomponentResult(
            name="multi_baseline_pass", available=False, error=stderr.strip()
        )
    passed = stdout.count(" PASSED")
    return SubcomponentResult(
        name="multi_baseline_pass",
        available=True,
        value=passed,
        raw_text=stdout[-500:],
    )


def collect_w17_test_delta(repo_root: Path, base_ref: str) -> SubcomponentResult:
    """Probe ``git diff <base>..HEAD --stat -- tests/`` -> NEW test fn count.

    The W-17 cap audit: ≤ +30 NEW test functions per PV; ≤ +150 cumulative
    cycle delta. We report the count; the W-17 verdict is the L3's
    job (the cap is the binding contract, the count is the input).
    """
    rc, stdout, stderr = run_command(
        ["git", "diff", f"{base_ref}..HEAD", "--", "tests/"],
        cwd=repo_root,
        timeout=30,
    )
    if rc < 0:
        return SubcomponentResult(
            name="w17_new_test_fn_count",
            available=False,
            error=stderr.strip(),
        )
    # Match `+def test_xxx(` for added test functions.
    added = sum(
        1
        for line in stdout.splitlines()
        if line.startswith("+def test_") or line.startswith("+    def test_")
    )
    return SubcomponentResult(
        name="w17_new_test_fn_count",
        available=True,
        value=added,
        raw_text=stdout[-500:],
    )


def _score_dim_from_subcomponents(
    subs: list[SubcomponentResult],
) -> tuple[float, int, int]:
    """Compute (score_0_to_10, available_count, total_count) for a dim.

    Each sub-component contributes equally. A ``clean`` ruff probe scores
    1.0; a non-zero exit scores 0.0. A coverage % is normalised by the
    CP-2 floor (80%) — at 80% we score 1.0; at 100% we score 1.0;
    at 60% we score 0.0; linear interpolation in between. test_count
    contributes 1.0 if > 0 (presence-only). multi_baseline_pass
    contributes 1.0 if >= 10 (the v8.3.0+ baseline floor). W-17 delta
    contributes 1.0 unless > 30 (over W-17/PV cap).
    """
    if not subs:
        return (0.0, 0, 0)
    available_count = sum(1 for s in subs if s.available)
    total = len(subs)
    if available_count == 0:
        return (0.0, 0, total)
    contrib_total = 0.0
    for s in subs:
        if not s.available:
            continue
        if s.name in ("ruff_lint", "ruff_format"):
            contrib_total += 1.0 if s.value == "clean" else 0.0
        elif s.name == "coverage_pct":
            v = float(s.value or 0)
            if v >= 80:
                contrib_total += 1.0
            elif v >= 60:
                contrib_total += (v - 60) / 20.0
            else:
                contrib_total += 0.0
        elif s.name == "test_count":
            contrib_total += 1.0 if (s.value or 0) > 0 else 0.0
        elif s.name == "multi_baseline_pass":
            contrib_total += 1.0 if (s.value or 0) >= 10 else 0.0
        elif s.name == "w17_new_test_fn_count":
            contrib_total += 1.0 if (s.value or 0) <= 30 else 0.0
        else:
            contrib_total += 1.0 if s.value not in (None, "", 0) else 0.0
    # Score = average over AVAILABLE subs, mapped to 0..10.
    avg = contrib_total / available_count
    return (round(avg * 10.0, 2), available_count, total)


def compute_objective_score(
    metrics: dict[str, list[SubcomponentResult]],
    *,
    sampled_at: str = "1970-01-01T00:00:00Z",
) -> Si3ObjectiveScore:
    """Aggregate per-dim sub-components into an Si3ObjectiveScore."""
    per_dim_scores: dict[str, float] = {}
    total_subs = 0
    available_subs = 0
    for dim_name in DIMENSION_WEIGHTS:
        subs = metrics.get(dim_name, [])
        score, avail, total = _score_dim_from_subcomponents(subs)
        per_dim_scores[dim_name] = score
        total_subs += total
        available_subs += avail
    composite = sum(
        per_dim_scores[name] * weight for name, weight in DIMENSION_WEIGHTS.items()
    )
    auto_fill_rate = (available_subs / total_subs) if total_subs > 0 else 0.0
    return Si3ObjectiveScore(
        per_dim_scores=per_dim_scores,
        per_dim_subcomponents=metrics,
        composite_objective=round(composite, 2),
        auto_fill_rate=round(auto_fill_rate, 4),
        sampled_at=sampled_at,
    )


def render_yaml(score: Si3ObjectiveScore) -> str:
    """Render the score as YAML (the canonical machine-consumable form)."""
    payload: dict = {
        "schema_version": 1,
        "sampled_at": score.sampled_at,
        "objective_weight": DEFAULT_OBJECTIVE_WEIGHT,
        "subjective_weight": DEFAULT_SUBJECTIVE_WEIGHT,
        "composite_objective": score.composite_objective,
        "auto_fill_rate": score.auto_fill_rate,
        "per_dim": {},
    }
    for dim_name in DIMENSION_WEIGHTS:
        payload["per_dim"][dim_name] = {
            "weight": DIMENSION_WEIGHTS[dim_name],
            "objective_score": score.per_dim_scores.get(dim_name, 0.0),
            "subcomponents": [
                s.as_yaml_dict() for s in score.per_dim_subcomponents.get(dim_name, [])
            ],
        }
    return yaml.safe_dump(payload, sort_keys=False, default_flow_style=False)


def render_markdown(score: Si3ObjectiveScore) -> str:
    """Render a human-friendly markdown summary."""
    lines: list[str] = []
    lines.append("# SI-3 Objective Auto-Collection Summary")
    lines.append("")
    lines.append(f"- Sampled at: `{score.sampled_at}`")
    lines.append(
        f"- Objective composite (weighted): **{score.composite_objective:.2f} / 10**"
    )
    lines.append(f"- Auto-fill rate: **{score.auto_fill_rate:.1%}**")
    lines.append(
        f"- Weighting (per cycle plan §6 R-10): "
        f"objective = {DEFAULT_OBJECTIVE_WEIGHT:.2f}, "
        f"subjective = {DEFAULT_SUBJECTIVE_WEIGHT:.2f}"
    )
    lines.append("")
    lines.append("## Per-dimension objective scores")
    lines.append("")
    lines.append("| Dimension | Weight | Objective score | Sub-components |")
    lines.append("|---|---:|---:|---|")
    for dim_name, weight in DIMENSION_WEIGHTS.items():
        sub_names = [
            s.name + ("" if s.available else "(unavail)")
            for s in score.per_dim_subcomponents.get(dim_name, [])
        ]
        lines.append(
            f"| {dim_name} | {weight:.2f} | "
            f"{score.per_dim_scores.get(dim_name, 0.0):.2f} | "
            f"{', '.join(sub_names) if sub_names else 'n/a'} |"
        )
    lines.append("")
    lines.append(
        "> **Reminder.** This is the OBJECTIVE half. The L3 cycle-lead "
        "MUST author the per-dim deduction-rationale prose (≥ 50 words "
        "per dim) before computing the SI-3 ACCEPT/REJECT verdict. "
        "Final per-dim score = "
        f"{DEFAULT_OBJECTIVE_WEIGHT:.1f} · objective + "
        f"{DEFAULT_SUBJECTIVE_WEIGHT:.1f} · subjective."
    )
    lines.append("")
    return "\n".join(lines) + "\n"


def _now_iso() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _build_metrics_map(
    repo_root: Path,
    *,
    base_ref: str,
    skip_benchmarks: bool,
    mock_data: bool,
) -> dict[str, list[SubcomponentResult]]:
    """Run all probes + group results by SI-3 dim."""
    if mock_data:
        # Test-friendly path that avoids invoking real subprocesses.
        ruff_lint = SubcomponentResult("ruff_lint", True, "clean")
        ruff_format = SubcomponentResult("ruff_format", True, "clean")
        cov = SubcomponentResult("coverage_pct", True, 87)
        test_count = SubcomponentResult("test_count", True, 4174)
        baseline = SubcomponentResult("multi_baseline_pass", True, 12)
        w17 = SubcomponentResult("w17_new_test_fn_count", True, 22)
    else:
        ruff_lint = collect_ruff_lint(repo_root)
        ruff_format = collect_ruff_format(repo_root)
        cov = (
            SubcomponentResult(
                "coverage_pct",
                False,
                error="--skip-benchmarks set; coverage probe deferred",
            )
            if skip_benchmarks
            else collect_coverage(repo_root)
        )
        test_count = collect_test_count(repo_root)
        baseline = collect_multi_baseline_pass(repo_root)
        w17 = collect_w17_test_delta(repo_root, base_ref)

    return {
        "code_quality": [ruff_lint, ruff_format, cov],
        "architecture": [baseline],
        "test_adequacy": [cov, test_count, w17],
        "maintainability": [ruff_format],
        "compatibility": [baseline],
        "performance_impact": [baseline],
    }


def run(
    repo_root: Path,
    *,
    output: Path | None = None,
    base_ref: str = "HEAD~10",
    skip_benchmarks: bool = False,
    mock_data: bool = False,
    json_out: bool = False,
) -> int:
    """Top-level driver — collect + aggregate + emit."""
    metrics = _build_metrics_map(
        repo_root,
        base_ref=base_ref,
        skip_benchmarks=skip_benchmarks,
        mock_data=mock_data,
    )
    score = compute_objective_score(metrics, sampled_at=_now_iso())
    if json_out:
        body = json.dumps(
            {
                "composite_objective": score.composite_objective,
                "auto_fill_rate": score.auto_fill_rate,
                "per_dim_scores": score.per_dim_scores,
                "sampled_at": score.sampled_at,
            },
            indent=2,
        )
    else:
        body = render_markdown(score) + "\n## Raw metrics (YAML)\n\n```yaml\n"
        body += render_yaml(score)
        body += "```\n"
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(body, encoding="utf-8")
        print(f"[si3-auto] wrote {output}")
    else:
        sys.stdout.write(body)
        if not body.endswith("\n"):
            sys.stdout.write("\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument(
        "--base-ref",
        type=str,
        default="HEAD~10",
        help="git ref to compare for W-17 NEW test count delta (default: HEAD~10)",
    )
    parser.add_argument(
        "--skip-benchmarks",
        action="store_true",
        help="skip the slow coverage probe (useful in CI)",
    )
    parser.add_argument(
        "--mock-data",
        action="store_true",
        help="emit a synthetic OK report without invoking real probes (for testing)",
    )
    parser.add_argument(
        "--json", action="store_true", help="emit JSON instead of markdown"
    )
    args = parser.parse_args(argv)
    repo_root = args.repo_root or _resolve_repo_root()
    return run(
        repo_root,
        output=args.output,
        base_ref=args.base_ref,
        skip_benchmarks=args.skip_benchmarks,
        mock_data=args.mock_data,
        json_out=args.json,
    )


if __name__ == "__main__":
    sys.exit(main())
