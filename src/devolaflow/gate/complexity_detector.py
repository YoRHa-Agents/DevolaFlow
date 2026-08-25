"""Deterministic local complexity inspection with tier-aware verdicts.

v8.0.0 (P-09) — implements primitive 4.13 from
``.local/research/tweet_analysis_harness_engineering_v7.8.md`` §4.13 and
``.local/research/v8.0.0_patch_plan.md`` §3 P-09.

v9.0.0 PV-06 (v8.5.1) — Theme T5 #4 default-on flip. STRICT and AUDIT
profiles default :pyattr:`GateProfile.complexity_detector_enabled` to
``True`` (paired with the existing ``complexity_weight=0.10``).
Operators opt OUT via ``DEVOLAFLOW_COMPLEXITY_DETECTOR=0`` per
env-flags.md §2.9 (R5 strict). The :func:`is_complexity_detector_active`
helper combines both signals so callers do not branch on the env-flag
manually.

The detector reads :class:`devolaflow.gate.models.ComplexitySignals` and
returns one of three :class:`devolaflow.gate.models.ComplexityVerdict`
values:

============  ===================================================
Verdict       When
============  ===================================================
``OK``        every signal sits inside the tier's headroom; ratify.
``WARNING``   at least one *soft* ceiling crossed (lines_changed,
              ratio_to_minimal, files_touched, nesting_depth,
              new_abstractions, OR cyclomatic_complexity > 10).
              Inject a "may be overcomplicated" reinforcement rule
              but do NOT block.
``CRITICAL``  at least one *hard* invariant broken: cyclomatic
              complexity > 15, OR an injected ERROR-severity finding.
              Decreases composite_score and flips the
              verdict to ITERATE per ``patch_plan §3 P-09``.
============  ===================================================

``inspect_complexity_path(target_path)`` walks Python files in stable
lexicographic order and derives LOC, file, class, block-nesting, and
cyclomatic-complexity measurements with the standard-library AST parser.
The ratio to a hypothetical minimal implementation is not measurable from
path inspection, so it is always the explicit sentinel ``0.0``.

Honors S-5 (No Silent Failures): every classifier branch returns one of
the three verdicts (never ``None``). Missing, unreadable, or unparsable
paths return a logged result with ``mode="degraded"`` rather than failing
silently.

The historical ``NinesWrapResult``, ``wrap_nines_complexity``,
``NINES_*``, and ``nines_*`` surfaces remain deprecated compatibility
aliases. They never resolve or execute an external binary.
"""

from __future__ import annotations

import ast
import logging
import os
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from devolaflow.gate.models import (
    VALID_TASK_COMPLEXITY_TIERS,
    ComplexitySignals,
    ComplexityVerdict,
    GateProfile,
)

if TYPE_CHECKING:
    from devolaflow.gate.models import TaskComplexityTier

logger = logging.getLogger(__name__)

# v9.0.0 PV-06 (v8.5.1) — Theme T5 #4 env-flag (R5 strict).
ENV_FLAG: str = "DEVOLAFLOW_COMPLEXITY_DETECTOR"
"""Env-flag controlling the v9.0.0 PV-06 default-on flip override.

R5 strict per ``workflow-system/agent/references/env-flags.md`` §2 parsing:

* env value EXACTLY ``"1"`` → force the detector active regardless of profile
* env value EXACTLY ``"0"`` → force the detector inactive regardless of profile
* env value unset / any other → respect ``profile.complexity_detector_enabled``
"""


def is_complexity_detector_active(
    profile: GateProfile,
    env: dict[str, str] | None = None,
) -> bool:
    """Return True iff the overcomplexity detector should run for *profile*.

    Combines the v9.0.0 PV-06 default-on profile flag
    (:pyattr:`GateProfile.complexity_detector_enabled` — True for STRICT/AUDIT)
    with the :data:`ENV_FLAG` per-process override (R5 strict). Operators
    who want to disable the detector on a flipped profile set
    ``DEVOLAFLOW_COMPLEXITY_DETECTOR=0`` per env-flags.md §2.9.
    """
    source = env if env is not None else os.environ
    raw = source.get(ENV_FLAG, "")
    if raw == "0":
        return False
    if raw == "1":
        return True
    return bool(getattr(profile, "complexity_detector_enabled", False))


# ─────────────────────────────────────────────────────────────────────────────
# Verdict thresholds — see ``patch_plan §3 P-09 AC #1-#3``.
# ─────────────────────────────────────────────────────────────────────────────

# Cyclomatic complexity ceiling for the WARNING path (per L3 dispatch
# work scope: "WARNING (cc>10 in any new module)"). Functions whose
# maximum cc strictly exceeds this trigger WARNING.
WARNING_CC_THRESHOLD: int = 10

# Cyclomatic complexity ceiling for the CRITICAL path (per L3 dispatch
# work scope: "CRITICAL (cc>15 OR ERROR finding)"). Functions whose
# maximum cc strictly exceeds this trigger CRITICAL — overrides any
# WARNING the same signal bundle would otherwise produce.
CRITICAL_CC_THRESHOLD: int = 15


# Per-tier soft ceilings driving WARNING. Picked so:
# - trivial    + lines_changed=50  + cc=5           → OK    (AC #1)
# - trivial    + lines_changed=100                  → WARN  (AC #2)
# - complex    + ratio_to_minimal=6.0               → WARN  (AC #3)
# Each tier carries explicit budgets for every dimension so the matrix
# stays exhaustive (S-5 — no silent default fall-through).
@dataclass(frozen=True)
class TierBudgets:
    """Per-tier WARNING ceilings consumed by :class:`ComplexityDetector`.

    Frozen so the budget table can be hashed / compared in tests.
    Threshold semantics: a signal value strictly greater than the
    corresponding budget triggers WARNING. A budget of ``0`` for a
    discrete dimension (e.g. ``new_abstractions_budget=0`` on trivial)
    means "no headroom" — any non-zero introduction warns.
    """

    line_budget: int
    files_budget: int
    new_abstractions_budget: int
    nesting_depth_budget: int
    ratio_threshold: float


TIER_BUDGETS: dict[str, TierBudgets] = {
    "trivial": TierBudgets(
        line_budget=99,
        files_budget=1,
        new_abstractions_budget=0,
        nesting_depth_budget=2,
        ratio_threshold=2.0,
    ),
    "simple": TierBudgets(
        line_budget=199,
        files_budget=2,
        new_abstractions_budget=2,
        nesting_depth_budget=3,
        ratio_threshold=3.0,
    ),
    "standard": TierBudgets(
        line_budget=499,
        files_budget=5,
        new_abstractions_budget=5,
        nesting_depth_budget=4,
        ratio_threshold=4.0,
    ),
    "complex": TierBudgets(
        line_budget=999,
        files_budget=10,
        new_abstractions_budget=10,
        nesting_depth_budget=5,
        ratio_threshold=5.0,
    ),
}


# Signal values flagged by :meth:`_collect_warnings` use these labels in
# the ``rationale`` string so consumers can grep specific dimensions
# without re-parsing the verdict.
WARN_REASON_LINES: str = "lines_changed"
WARN_REASON_FILES: str = "files_touched"
WARN_REASON_ABSTRACTIONS: str = "new_abstractions"
WARN_REASON_NESTING: str = "nesting_depth_max"
WARN_REASON_RATIO: str = "ratio_to_minimal"
WARN_REASON_CC: str = "cyclomatic_complexity"
WARN_REASON_WARNING_FINDINGS: str = "warning_findings"
# Deprecated compatibility alias.
WARN_REASON_NINES_WARN: str = WARN_REASON_WARNING_FINDINGS


# Critical reasons (non-tier-dependent — apply across all tiers).
CRITICAL_REASON_CC: str = "cyclomatic_complexity"
CRITICAL_REASON_ERROR_FINDINGS: str = "error_findings"
# Deprecated compatibility alias.
CRITICAL_REASON_NINES_ERROR: str = CRITICAL_REASON_ERROR_FINDINGS


# ─────────────────────────────────────────────────────────────────────────────
# Deterministic local path inspection
# ─────────────────────────────────────────────────────────────────────────────


# Deprecated compatibility constant. Local inspection never resolves or
# executes this value.
NINES_BINARY: str = "nines"

# The local inspection is synchronous and performs no subprocess call. This
# neutral name is canonical; the historical NineS name remains an alias so
# existing call signatures and imports continue to work.
COMPLEXITY_INSPECTION_TIMEOUT_SECONDS: int = 120
NINES_TIMEOUT_SECONDS: int = COMPLEXITY_INSPECTION_TIMEOUT_SECONDS


def _zero_complexity_signals() -> ComplexitySignals:
    """Return explicit zero measurements for a degraded inspection.

    The ratio remains ``0.0`` because a minimal viable implementation cannot
    be inferred from a filesystem path. Inspection failures are represented
    on :class:`ComplexityProbeResult`, not fabricated as code findings.
    """
    return ComplexitySignals(
        lines_changed=0,
        files_touched=0,
        new_abstractions=0,
        nesting_depth_max=0,
        cyclomatic_complexity=0,
        ratio_to_minimal=0.0,
        error_findings=0,
        warning_findings=0,
    )


@dataclass(frozen=True)
class ComplexityProbeResult:
    """Bundle returned by :func:`inspect_complexity_path`.

    ``mode`` is ``"local"`` when every discovered Python file was measured
    and ``"degraded"`` when path discovery, reading, or parsing failed.
    ``errors`` keeps every failure explicit while ``inspected_files`` exposes
    the stable processing order.
    """

    signals: ComplexitySignals
    mode: str  # "local" | "degraded"
    rationale: str
    raw_findings: tuple[dict[str, object], ...] = field(default_factory=tuple)
    inspected_files: tuple[str, ...] = field(default_factory=tuple)
    errors: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_degraded(self) -> bool:
        """Return whether any requested measurement was unavailable."""
        return self.mode in {"degraded", "mock"}

    @property
    def is_mock(self) -> bool:
        """Deprecated alias for :attr:`is_degraded`."""
        return self.is_degraded


# Deprecated class alias. Identity is intentional for compatibility.
NinesWrapResult = ComplexityProbeResult


_FUNCTION_NODES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)
_NESTING_NODES = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.With,
    ast.AsyncWith,
    ast.Try,
    ast.TryStar,
    ast.Match,
)


def _owned_ast_nodes(root: ast.AST) -> Iterator[ast.AST]:
    """Yield descendants of ``root`` without entering nested functions."""
    stack = list(reversed(list(ast.iter_child_nodes(root))))
    while stack:
        node = stack.pop()
        if isinstance(node, _FUNCTION_NODES):
            continue
        yield node
        stack.extend(reversed(list(ast.iter_child_nodes(node))))


def _function_cyclomatic_complexity(function: ast.AST) -> int:
    """Compute deterministic McCabe-style complexity for one function."""
    complexity = 1
    for node in _owned_ast_nodes(function):
        if isinstance(
            node,
            (
                ast.If,
                ast.While,
                ast.For,
                ast.AsyncFor,
                ast.ExceptHandler,
                ast.IfExp,
                ast.Assert,
            ),
        ):
            complexity += 1
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            complexity += len(node.items)
        elif isinstance(node, ast.BoolOp):
            complexity += max(0, len(node.values) - 1)
        elif isinstance(node, ast.comprehension):
            complexity += len(node.ifs)
        elif isinstance(node, ast.Match):
            complexity += max(0, len(node.cases) - 1)
    return complexity


def _function_nesting_depth(function: ast.AST) -> int:
    """Return maximum control-flow nesting below one function."""

    def visit(node: ast.AST, depth: int) -> int:
        if node is not function and isinstance(node, _FUNCTION_NODES):
            return depth
        child_depth = depth + 1 if isinstance(node, _NESTING_NODES) else depth
        return max(
            [child_depth, *(visit(child, child_depth) for child in ast.iter_child_nodes(node))]
        )

    return visit(function, 0)


def _discover_python_files(target: Path) -> tuple[list[Path], list[str]]:
    """Return sorted Python files and explicit path-discovery errors."""
    try:
        if not target.exists():
            return [], [f"path does not exist: {target}"]
        if target.is_file():
            if target.suffix != ".py":
                return [], [f"path is not a Python file: {target}"]
            return [target], []
        if not target.is_dir():
            return [], [f"path is neither a file nor directory: {target}"]
    except OSError as exc:
        return [], [f"cannot inspect path {target}: {type(exc).__name__}: {exc}"]

    files: list[Path] = []
    errors: list[str] = []

    def onerror(exc: OSError) -> None:
        errors.append(f"cannot traverse {exc.filename or target}: {type(exc).__name__}: {exc}")

    for root, directories, filenames in os.walk(target, topdown=True, onerror=onerror):
        directories.sort()
        for filename in sorted(filenames):
            if filename.endswith(".py"):
                files.append(Path(root) / filename)
    return sorted(files, key=lambda path: path.as_posix()), errors


def _measure_python_file(path: Path) -> tuple[int, int, int, int]:
    """Return ``(loc, class_count, max_nesting, max_cc)`` for ``path``."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    functions = [node for node in ast.walk(tree) if isinstance(node, _FUNCTION_NODES)]
    return (
        len(source.splitlines()),
        sum(1 for node in ast.walk(tree) if isinstance(node, ast.ClassDef)),
        max((_function_nesting_depth(function) for function in functions), default=0),
        max((_function_cyclomatic_complexity(function) for function in functions), default=0),
    )


def inspect_complexity_path(
    target_path: str | Path,
    *,
    binary: str | None = None,
    timeout: int = NINES_TIMEOUT_SECONDS,
    runner: object | None = None,
) -> ComplexityProbeResult:
    """Inspect Python sources under ``target_path`` without external tools.

    Parameters
    ----------
    target_path:
        Python file or directory inspected recursively in sorted path order.
    binary:
        Deprecated compatibility argument. Ignored; no binary is resolved.
    timeout:
        Deprecated compatibility argument. Ignored; no subprocess runs.
    runner:
        Deprecated compatibility argument. Never invoked.

    Returns
    -------
    ComplexityProbeResult
        Local measurements, stable file order, and explicit degraded errors.
    """
    if binary is not None or timeout != NINES_TIMEOUT_SECONDS or runner is not None:
        logger.debug(
            "Deprecated external-probe arguments ignored: binary=%r timeout=%r runner=%s",
            binary,
            timeout,
            type(runner).__name__ if runner is not None else None,
        )

    target = Path(target_path)
    files, errors = _discover_python_files(target)
    total_loc = 0
    total_classes = 0
    max_nesting = 0
    max_cc = 0

    for path in files:
        try:
            loc, class_count, nesting, cc = _measure_python_file(path)
        except (OSError, UnicodeError, SyntaxError) as exc:
            error = f"cannot measure {path}: {type(exc).__name__}: {exc}"
            errors.append(error)
            logger.warning("Complexity path inspection degraded: %s", error)
            continue
        total_loc += loc
        total_classes += class_count
        max_nesting = max(max_nesting, nesting)
        max_cc = max(max_cc, cc)

    if errors:
        for error in errors:
            if not error.startswith("cannot measure "):
                logger.warning("Complexity path inspection degraded: %s", error)

    signals = ComplexitySignals(
        lines_changed=total_loc,
        files_touched=len(files),
        new_abstractions=total_classes,
        nesting_depth_max=max_nesting,
        cyclomatic_complexity=max_cc,
        ratio_to_minimal=0.0,
        error_findings=0,
        warning_findings=0,
    )
    mode = "degraded" if errors else "local"
    rationale = (
        f"Local Python inspection {mode}: files={signals.files_touched}, "
        f"loc={signals.lines_changed}, classes={signals.new_abstractions}, "
        f"max_nesting={signals.nesting_depth_max}, "
        f"max_cc={signals.cyclomatic_complexity}, "
        "ratio_to_minimal=0.0 (unmeasurable)"
    )
    if errors:
        rationale += f", errors={len(errors)}."
    else:
        rationale += "."
    return ComplexityProbeResult(
        signals=signals,
        mode=mode,
        rationale=rationale,
        inspected_files=tuple(path.as_posix() for path in files),
        errors=tuple(errors),
    )


# Deprecated function alias. It intentionally resolves to the local inspector
# and therefore can never execute a binary.
wrap_nines_complexity = inspect_complexity_path

# Private legacy helper retained for source-compatible tests and callers.
_conservative_mock_signals = _zero_complexity_signals


# ─────────────────────────────────────────────────────────────────────────────
# ComplexityDetector — pure verdict matrix on top of ComplexitySignals
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ComplexityEvaluation:
    """Outcome of :meth:`ComplexityDetector.evaluate`.

    Carries the verdict alongside the matched ``reasons`` list so
    downstream :class:`devolaflow.gate.reinforcement.ReinforcementBlock`
    rendering can quote the exact dimension that crossed the ceiling.
    """

    verdict: ComplexityVerdict
    task_complexity: str
    reasons: tuple[str, ...]
    rationale: str
    signals: ComplexitySignals

    @property
    def is_ok(self) -> bool:
        """``True`` iff the verdict is :data:`ComplexityVerdict.OK`."""
        return self.verdict is ComplexityVerdict.OK


@dataclass
class ComplexityDetector:
    """Pure verdict matrix on top of :class:`ComplexitySignals`.

    Construct once per gate evaluation (or per task) then call
    :meth:`evaluate` to translate signal bundles into a
    :class:`ComplexityVerdict`. The detector never raises on missing
    fields — invalid signal values are caught at
    :class:`ComplexitySignals` construction time (S-5).

    Parameters
    ----------
    warning_cc_threshold:
        Cyclomatic-complexity ceiling above which the WARNING path
        fires. Default :data:`WARNING_CC_THRESHOLD` (``10``).
    critical_cc_threshold:
        Cyclomatic-complexity ceiling above which the CRITICAL path
        fires. Default :data:`CRITICAL_CC_THRESHOLD` (``15``). MUST be
        strictly greater than :pyattr:`warning_cc_threshold`.
    tier_budgets:
        Optional per-tier soft-budget overrides. Defaults to the
        :data:`TIER_BUDGETS` global; supplied values are merged on top
        of the default table so the caller can override one or two
        tiers without restating the others.
    """

    warning_cc_threshold: int = WARNING_CC_THRESHOLD
    critical_cc_threshold: int = CRITICAL_CC_THRESHOLD
    tier_budgets: dict[str, TierBudgets] = field(default_factory=lambda: dict(TIER_BUDGETS))

    def __post_init__(self) -> None:
        if self.warning_cc_threshold < 0:
            raise ValueError(f"warning_cc_threshold must be >= 0 (got {self.warning_cc_threshold})")
        if self.critical_cc_threshold <= self.warning_cc_threshold:
            raise ValueError(
                f"critical_cc_threshold ({self.critical_cc_threshold}) must be strictly "
                f"greater than warning_cc_threshold ({self.warning_cc_threshold})"
            )
        merged = dict(TIER_BUDGETS)
        merged.update(self.tier_budgets)
        self.tier_budgets = merged

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(
        self,
        signals: ComplexitySignals,
        task_complexity: TaskComplexityTier | str,
    ) -> ComplexityEvaluation:
        """Classify ``signals`` for the supplied ``task_complexity`` tier.

        Returns
        -------
        ComplexityEvaluation
            Carries verdict (``OK`` / ``WARNING`` / ``CRITICAL``),
            the matched dimension reasons, a human-readable rationale,
            and the original signals (for audit logs).
        """
        tier = self._resolve_tier(task_complexity)
        budgets = self.tier_budgets[tier]

        critical_reasons = self._collect_critical_reasons(signals)
        if critical_reasons:
            rationale = self._format_critical_rationale(signals, critical_reasons)
            return ComplexityEvaluation(
                verdict=ComplexityVerdict.CRITICAL,
                task_complexity=tier,
                reasons=tuple(critical_reasons),
                rationale=rationale,
                signals=signals,
            )

        warning_reasons = self._collect_warning_reasons(signals, budgets)
        if warning_reasons:
            rationale = self._format_warning_rationale(signals, tier, budgets, warning_reasons)
            return ComplexityEvaluation(
                verdict=ComplexityVerdict.WARNING,
                task_complexity=tier,
                reasons=tuple(warning_reasons),
                rationale=rationale,
                signals=signals,
            )

        rationale = (
            f"All signals within {tier!r} tier budgets "
            f"(lines_changed={signals.lines_changed}/{budgets.line_budget}, "
            f"cc={signals.cyclomatic_complexity}/{self.warning_cc_threshold}, "
            f"ratio={signals.ratio_to_minimal:.2f}/{budgets.ratio_threshold:.2f})."
        )
        return ComplexityEvaluation(
            verdict=ComplexityVerdict.OK,
            task_complexity=tier,
            reasons=(),
            rationale=rationale,
            signals=signals,
        )

    def evaluate_path(
        self,
        target_path: str | Path,
        task_complexity: TaskComplexityTier | str,
        *,
        binary: str | None = None,
        timeout: int = NINES_TIMEOUT_SECONDS,
        runner: object | None = None,
    ) -> ComplexityEvaluation:
        """Convenience: inspect ``target_path`` locally then :meth:`evaluate`.

        Equivalent to ``self.evaluate(inspect_complexity_path(target_path).signals,
        task_complexity)`` but keeps a single call-site for tests and
        downstream gate scorer integration. Deprecated external-probe
        arguments are accepted but ignored.
        """
        probe = inspect_complexity_path(
            target_path,
            binary=binary,
            timeout=timeout,
            runner=runner,
        )
        return self.evaluate(probe.signals, task_complexity)

    # ------------------------------------------------------------------
    # Internal helpers — kept tiny to honour C-1 complexity ceilings.
    # ------------------------------------------------------------------

    def _resolve_tier(self, task_complexity: TaskComplexityTier | str) -> str:
        """Validate and normalise ``task_complexity`` into a tier name."""
        if not isinstance(task_complexity, str):
            raise TypeError(
                f"task_complexity must be a string (got {type(task_complexity).__name__})"
            )
        tier = task_complexity.lower()
        if tier not in VALID_TASK_COMPLEXITY_TIERS:
            raise ValueError(
                f"task_complexity must be one of {sorted(VALID_TASK_COMPLEXITY_TIERS)} "
                f"(got {task_complexity!r})"
            )
        if tier not in self.tier_budgets:
            raise ValueError(
                f"No tier budget configured for {tier!r}; configured tiers: "
                f"{sorted(self.tier_budgets)}"
            )
        return tier

    def _collect_critical_reasons(self, signals: ComplexitySignals) -> list[str]:
        """Return non-empty list iff a hard invariant is broken."""
        reasons: list[str] = []
        if signals.cyclomatic_complexity > self.critical_cc_threshold:
            reasons.append(CRITICAL_REASON_CC)
        if signals.error_findings > 0:
            reasons.append(CRITICAL_REASON_NINES_ERROR)
        return reasons

    def _collect_warning_reasons(
        self,
        signals: ComplexitySignals,
        budgets: TierBudgets,
    ) -> list[str]:
        """Return non-empty list iff at least one soft ceiling is crossed."""
        reasons: list[str] = []
        if signals.lines_changed > budgets.line_budget:
            reasons.append(WARN_REASON_LINES)
        if signals.files_touched > budgets.files_budget:
            reasons.append(WARN_REASON_FILES)
        if signals.new_abstractions > budgets.new_abstractions_budget:
            reasons.append(WARN_REASON_ABSTRACTIONS)
        if signals.nesting_depth_max > budgets.nesting_depth_budget:
            reasons.append(WARN_REASON_NESTING)
        if signals.ratio_to_minimal > 0.0 and signals.ratio_to_minimal >= budgets.ratio_threshold:
            reasons.append(WARN_REASON_RATIO)
        if signals.cyclomatic_complexity > self.warning_cc_threshold:
            reasons.append(WARN_REASON_CC)
        if signals.warning_findings > 0:
            reasons.append(WARN_REASON_NINES_WARN)
        return reasons

    def _format_critical_rationale(
        self,
        signals: ComplexitySignals,
        reasons: list[str],
    ) -> str:
        """Render a single-line CRITICAL rationale string."""
        parts: list[str] = []
        if CRITICAL_REASON_CC in reasons:
            parts.append(f"cc={signals.cyclomatic_complexity} > {self.critical_cc_threshold}")
        if CRITICAL_REASON_NINES_ERROR in reasons:
            parts.append(f"errors={signals.error_findings}")
        return f"CRITICAL — {', '.join(parts)} (reasons={reasons})."

    def _format_warning_rationale(
        self,
        signals: ComplexitySignals,
        tier: str,
        budgets: TierBudgets,
        reasons: list[str],
    ) -> str:
        """Render a single-line WARNING rationale string."""
        parts: list[str] = []
        if WARN_REASON_LINES in reasons:
            parts.append(f"lines={signals.lines_changed} > {budgets.line_budget}")
        if WARN_REASON_FILES in reasons:
            parts.append(f"files={signals.files_touched} > {budgets.files_budget}")
        if WARN_REASON_ABSTRACTIONS in reasons:
            parts.append(
                f"new_abstractions={signals.new_abstractions} > {budgets.new_abstractions_budget}"
            )
        if WARN_REASON_NESTING in reasons:
            parts.append(f"nesting={signals.nesting_depth_max} > {budgets.nesting_depth_budget}")
        if WARN_REASON_RATIO in reasons:
            parts.append(f"ratio={signals.ratio_to_minimal:.2f} >= {budgets.ratio_threshold:.2f}")
        if WARN_REASON_CC in reasons:
            parts.append(f"cc={signals.cyclomatic_complexity} > {self.warning_cc_threshold}")
        if WARN_REASON_NINES_WARN in reasons:
            parts.append(f"warnings={signals.warning_findings}")
        return f"WARNING (tier={tier!r}) — {', '.join(parts)}."


__all__ = [
    "CRITICAL_CC_THRESHOLD",
    "CRITICAL_REASON_ERROR_FINDINGS",
    "CRITICAL_REASON_CC",
    "CRITICAL_REASON_NINES_ERROR",
    "COMPLEXITY_INSPECTION_TIMEOUT_SECONDS",
    "ComplexityDetector",
    "ComplexityEvaluation",
    "ComplexityProbeResult",
    "NINES_BINARY",
    "NINES_TIMEOUT_SECONDS",
    "NinesWrapResult",
    "TIER_BUDGETS",
    "TierBudgets",
    "WARN_REASON_ABSTRACTIONS",
    "WARN_REASON_CC",
    "WARN_REASON_FILES",
    "WARN_REASON_LINES",
    "WARN_REASON_NESTING",
    "WARN_REASON_NINES_WARN",
    "WARN_REASON_RATIO",
    "WARN_REASON_WARNING_FINDINGS",
    "WARNING_CC_THRESHOLD",
    "inspect_complexity_path",
    "wrap_nines_complexity",
]
