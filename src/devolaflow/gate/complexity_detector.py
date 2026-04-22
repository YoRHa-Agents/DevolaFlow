"""Overcomplexity detector — wraps NineS subprocess with tier-aware verdicts.

v8.0.0 (P-09) — implements primitive 4.13 from
``.local/research/tweet_analysis_harness_engineering_v7.8.md`` §4.13 and
``.local/research/v8.0.0_patch_plan.md`` §3 P-09.

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
              complexity > 15, OR NineS surfaces an ERROR-severity
              finding. Decreases composite_score and flips the
              verdict to ITERATE per ``patch_plan §3 P-09``.
============  ===================================================

``wrap_nines_complexity(target_path)`` shells out to ``nines`` (see
https://github.com/YoRHa-Agents/NineS), parses the JSON report, and
returns the resulting :class:`ComplexitySignals`. When the binary is
unavailable the wrapper returns a conservative MOCK signal that
deliberately keeps the verdict at OK so the gate never silently fails
just because NineS is missing (S-5 — log + explicit fallback path,
never silent error).

Honors S-5 (No Silent Failures): every classifier branch returns one of
the three verdicts (never ``None``). The NineS subprocess wrapper logs
both success and fallback paths via :mod:`logging`.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from devolaflow.gate.models import (
    VALID_TASK_COMPLEXITY_TIERS,
    ComplexitySignals,
    ComplexityVerdict,
)

if TYPE_CHECKING:
    from devolaflow.gate.models import TaskComplexityTier

logger = logging.getLogger(__name__)

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
WARN_REASON_NINES_WARN: str = "nines_warn_findings"


# Critical reasons (non-tier-dependent — apply across all tiers).
CRITICAL_REASON_CC: str = "cyclomatic_complexity"
CRITICAL_REASON_NINES_ERROR: str = "nines_error_findings"


# ─────────────────────────────────────────────────────────────────────────────
# NineS subprocess wrapper
# ─────────────────────────────────────────────────────────────────────────────


# Default executable name. Resolved via :func:`shutil.which`; missing
# binary → MOCK fallback (logged at WARNING).
NINES_BINARY: str = "nines"

# Subprocess timeout in seconds. NineS deep analysis can be slow on
# large repos; 120s is conservative but bounded so a hung subprocess
# never blocks the gate forever (P4 bounded retry).
NINES_TIMEOUT_SECONDS: int = 120


def _conservative_mock_signals() -> ComplexitySignals:
    """Return a deliberately-low-complexity ``ComplexitySignals``.

    Used by :func:`wrap_nines_complexity` when ``nines`` is unavailable
    (binary missing, subprocess error, JSON parse failure). The fields
    sit comfortably inside the strictest tier budget (``trivial``) so
    :meth:`ComplexityDetector.evaluate` returns ``OK`` regardless of
    tier — the gate must never block solely because NineS is missing
    (S-5 — explicit conservative fallback, logged at WARNING).
    """
    return ComplexitySignals(
        lines_changed=0,
        files_touched=0,
        new_abstractions=0,
        nesting_depth_max=0,
        cyclomatic_complexity=0,
        ratio_to_minimal=0.0,
        nines_error_findings=0,
        nines_warn_findings=0,
    )


@dataclass(frozen=True)
class NinesWrapResult:
    """Bundle returned by :func:`wrap_nines_complexity`.

    Carries the parsed :class:`ComplexitySignals` AND a ``mode`` flag
    (``"live"`` / ``"mock"``) so callers can differentiate a real NineS
    run from a fallback. The ``rationale`` is human-readable and shows
    up in :class:`ComplexityDetector` audit logs.
    """

    signals: ComplexitySignals
    mode: str  # "live" | "mock"
    rationale: str
    raw_findings: tuple[dict[str, object], ...] = field(default_factory=tuple)

    @property
    def is_mock(self) -> bool:
        """``True`` iff the wrapper fell back to the conservative mock."""
        return self.mode == "mock"


def _resolve_nines_binary(binary: str | None) -> str | None:
    """Return the absolute path to ``binary`` or ``None`` if unavailable.

    Defaults to :data:`NINES_BINARY` when ``binary`` is ``None``. Uses
    :func:`shutil.which` so a binary on ``PATH`` resolves the same way
    as a manual shell invocation.
    """
    name = binary or NINES_BINARY
    return shutil.which(name)


def _parse_nines_payload(payload: dict[str, object]) -> ComplexitySignals:
    """Extract a :class:`ComplexitySignals` from a parsed NineS report.

    Accepts the canonical ``analyze`` shape:

    .. code-block:: json

        {
          "findings": [
            {"severity": "error", "metric": "cyclomatic", "value": 22, ...},
            {"severity": "warn",  "metric": "cyclomatic", "value": 15, ...}
          ],
          "summary": {"total_lines": 1234, "total_files": 5, ...}
        }

    Missing keys default to ``0`` / ``[]`` so a partial NineS payload
    still yields a valid :class:`ComplexitySignals`. Any negative
    integers in the payload are clamped to ``0`` (the dataclass will
    raise on construction otherwise — clamping keeps the wrapper
    forward-compatible with future NineS schema tweaks).
    """
    findings = payload.get("findings") or []
    if not isinstance(findings, list):
        findings = []
    summary = payload.get("summary") or {}
    if not isinstance(summary, dict):
        summary = {}

    error_count = 0
    warn_count = 0
    max_cc = 0
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        sev = str(finding.get("severity", "")).lower()
        if sev == "error":
            error_count += 1
        elif sev == "warn":
            warn_count += 1
        metric = str(finding.get("metric", "")).lower()
        if metric in {"cyclomatic", "cyclomatic_complexity", "cc"}:
            value = finding.get("value", 0)
            try:
                cc_value = int(value)
            except (TypeError, ValueError):
                cc_value = 0
            if cc_value > max_cc:
                max_cc = cc_value

    lines_changed = max(0, int(summary.get("total_lines", 0) or 0))
    files_touched = max(0, int(summary.get("total_files", 0) or 0))
    new_abstractions = max(0, int(summary.get("new_classes", 0) or 0))
    nesting_depth_max = max(0, int(summary.get("max_nesting_depth", 0) or 0))
    ratio_to_minimal = max(0.0, float(summary.get("ratio_to_minimal", 0.0) or 0.0))

    return ComplexitySignals(
        lines_changed=lines_changed,
        files_touched=files_touched,
        new_abstractions=new_abstractions,
        nesting_depth_max=nesting_depth_max,
        cyclomatic_complexity=max_cc,
        ratio_to_minimal=ratio_to_minimal,
        nines_error_findings=error_count,
        nines_warn_findings=warn_count,
    )


def wrap_nines_complexity(
    target_path: str | Path,
    *,
    binary: str | None = None,
    timeout: int = NINES_TIMEOUT_SECONDS,
    runner: object | None = None,
) -> NinesWrapResult:
    """Run NineS deep analysis on ``target_path`` and return signals.

    Shells out to ``nines analyze --target-path <target_path> --depth deep
    --keypoints -f json``. When the binary is not on ``PATH`` (or the
    subprocess fails for any reason — non-zero exit, JSON parse error,
    timeout), the wrapper falls back to :func:`_conservative_mock_signals`
    and logs at WARNING (S-5 — no silent failure).

    Parameters
    ----------
    target_path:
        Directory or file passed to ``nines analyze --target-path``.
    binary:
        Optional override for the ``nines`` executable name (defaults
        to :data:`NINES_BINARY`). Resolved via :func:`shutil.which`.
    timeout:
        Subprocess timeout in seconds (default
        :data:`NINES_TIMEOUT_SECONDS`).
    runner:
        Optional callable replacing :func:`subprocess.run`. Used by
        the test suite to inject deterministic mocks without monkey-
        patching :mod:`subprocess`. When provided, MUST return an
        object with ``returncode``, ``stdout`` and ``stderr``
        attributes (mirroring :class:`subprocess.CompletedProcess`).

    Returns
    -------
    NinesWrapResult
        Carries the parsed signals plus a ``mode`` flag (``"live"`` /
        ``"mock"``) and a human-readable rationale.
    """
    resolved = _resolve_nines_binary(binary)
    if resolved is None and runner is None:
        logger.warning(
            "NineS binary %r not on PATH; falling back to conservative MOCK signals "
            "(target_path=%s)",
            binary or NINES_BINARY,
            target_path,
        )
        return NinesWrapResult(
            signals=_conservative_mock_signals(),
            mode="mock",
            rationale=(
                f"NineS binary {(binary or NINES_BINARY)!r} not found on PATH; "
                "conservative MOCK signals returned (verdict will be OK)."
            ),
        )

    cmd = [
        resolved or (binary or NINES_BINARY),
        "-f",
        "json",
        "analyze",
        "--target-path",
        str(target_path),
        "--depth",
        "deep",
        "--keypoints",
    ]
    invoke = runner if runner is not None else subprocess.run
    try:
        result = invoke(  # type: ignore[operator]
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        logger.warning(
            "NineS subprocess raised FileNotFoundError (%s); MOCK fallback engaged.",
            exc,
        )
        return NinesWrapResult(
            signals=_conservative_mock_signals(),
            mode="mock",
            rationale=(f"NineS subprocess failed: {exc}; conservative MOCK signals returned."),
        )
    except subprocess.TimeoutExpired as exc:
        logger.warning(
            "NineS subprocess timed out after %ds (%s); MOCK fallback engaged.",
            timeout,
            exc,
        )
        return NinesWrapResult(
            signals=_conservative_mock_signals(),
            mode="mock",
            rationale=(f"NineS subprocess timed out: {exc}; conservative MOCK signals returned."),
        )
    except OSError as exc:
        logger.warning(
            "NineS subprocess raised OSError (%s); MOCK fallback engaged.",
            exc,
        )
        return NinesWrapResult(
            signals=_conservative_mock_signals(),
            mode="mock",
            rationale=(f"NineS subprocess error: {exc}; conservative MOCK signals returned."),
        )

    if getattr(result, "returncode", 1) != 0:
        logger.warning(
            "NineS subprocess returned non-zero exit %s; MOCK fallback engaged. stderr=%r",
            getattr(result, "returncode", "?"),
            getattr(result, "stderr", "")[:200],
        )
        return NinesWrapResult(
            signals=_conservative_mock_signals(),
            mode="mock",
            rationale=(
                f"NineS subprocess exited non-zero ({getattr(result, 'returncode', '?')}); "
                "conservative MOCK signals returned."
            ),
        )

    stdout = getattr(result, "stdout", "") or ""
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        logger.warning(
            "NineS stdout is not valid JSON (%s); MOCK fallback engaged. stdout=%r",
            exc,
            stdout[:200],
        )
        return NinesWrapResult(
            signals=_conservative_mock_signals(),
            mode="mock",
            rationale=(f"NineS JSON parse error: {exc}; conservative MOCK signals returned."),
        )

    if not isinstance(payload, dict):
        logger.warning(
            "NineS payload is not a dict (got %s); MOCK fallback engaged.",
            type(payload).__name__,
        )
        return NinesWrapResult(
            signals=_conservative_mock_signals(),
            mode="mock",
            rationale=(
                f"NineS payload type {type(payload).__name__}; conservative MOCK signals returned."
            ),
        )

    signals = _parse_nines_payload(payload)
    raw_findings = payload.get("findings") or []
    if not isinstance(raw_findings, list):
        raw_findings = []
    return NinesWrapResult(
        signals=signals,
        mode="live",
        rationale=(
            f"NineS deep analysis succeeded: max_cc={signals.cyclomatic_complexity}, "
            f"errors={signals.nines_error_findings}, warns={signals.nines_warn_findings}."
        ),
        raw_findings=tuple(f for f in raw_findings if isinstance(f, dict)),
    )


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
        """Convenience: wrap NineS on ``target_path`` then :meth:`evaluate`.

        Equivalent to ``self.evaluate(wrap_nines_complexity(target_path).signals,
        task_complexity)`` but keeps a single call-site for tests and
        downstream gate scorer integration. The MOCK fallback is
        transparent — the resulting :class:`ComplexityEvaluation` will
        return ``OK`` whenever NineS is unavailable (per S-5 fallback).
        """
        wrap = wrap_nines_complexity(target_path, binary=binary, timeout=timeout, runner=runner)
        return self.evaluate(wrap.signals, task_complexity)

    # ------------------------------------------------------------------
    # Internal helpers — kept tiny to honour C-1 / NineS cc ceilings.
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
        if signals.nines_error_findings > 0:
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
        if signals.nines_warn_findings > 0:
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
            parts.append(f"nines_errors={signals.nines_error_findings}")
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
            parts.append(f"nines_warns={signals.nines_warn_findings}")
        return f"WARNING (tier={tier!r}) — {', '.join(parts)}."


__all__ = [
    "CRITICAL_CC_THRESHOLD",
    "CRITICAL_REASON_CC",
    "CRITICAL_REASON_NINES_ERROR",
    "ComplexityDetector",
    "ComplexityEvaluation",
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
    "WARNING_CC_THRESHOLD",
    "wrap_nines_complexity",
]
