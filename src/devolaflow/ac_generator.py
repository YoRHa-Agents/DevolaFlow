"""Automatic acceptance-criteria generator (v8.0.0 P-10).

Closes the Karpathy "Goal-Driven Execution" gap surfaced by upstream
tweet analysis ``v7.8`` §4.14: agents need *structured*, machine-checkable
acceptance criteria attached to every dispatch so ``ACGenerator.generate``
can be replayed deterministically and ``evaluate_acceptance_criteria_v2``
can ratify completion without LLM judgement.

This module is deliberately small and dependency-free:

* :class:`ACGenerator` runs pure-Python pattern matching against the
  task description (no LLM, no subprocess) and emits a list of
  :class:`devolaflow.gate.models.AcceptanceCriterion` records.
* :meth:`ACGenerator.score_quality` reports a 3-dimensional quality
  vector (``completeness`` / ``testability`` / ``specificity``) so
  L2/L3 agents can refuse low-quality criteria upstream of the gate.

Per ``patch_plan §3 P-10`` the legacy ``acceptance_criteria: list[str]``
alias remains the contract for v7.x dispatchers; this module supplies
the structured ``acceptance_criteria_v2`` (canonical_order position 15,
schema version 4) for v8.x consumers without breaking the old shape (R5
mitigation per ``.local/research/v8.0.0_patch_plan.md`` §9).

v9.0.0 PV-06 (v8.5.1) — Theme T5 #5 default-on flip. STRICT and AUDIT
profiles default :pyattr:`GateProfile.ac_generator_enabled` to ``True``.
Operators opt OUT via ``DEVOLAFLOW_AC_GEN=0`` per env-flags.md §2.10
(R5 strict). The :func:`is_ac_generator_active` helper combines both
signals so callers do not branch on the env-flag manually. The legacy
``acceptance_criteria: list[str]`` alias remains the contract per the
v8.0.0 P-10 R5 mitigation — opt-out preserves the exact pre-flip
dispatch shape.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

from devolaflow.gate.models import (
    AcceptanceCriterion,
    GateProfile,
    VerificationType,
)

__all__ = [
    "ACGenerator",
    "ACGeneratorError",
    "DEFAULT_PERFORMANCE_METRIC",
    "DEFAULT_PERFORMANCE_THRESHOLD",
    "DEFAULT_TEST_COMMAND",
    "ENV_FLAG",
    "is_ac_generator_active",
    "score_quality",
]


ENV_FLAG: str = "DEVOLAFLOW_AC_GEN"
"""v9.0.0 PV-06 (v8.5.1) — Theme T5 #5 env-flag (R5 strict).

Per ``workflow-system/agent/references/env-flags.md`` §2 parsing:

* env value EXACTLY ``"1"`` → force ACGenerator active regardless of profile
* env value EXACTLY ``"0"`` → force ACGenerator inactive regardless of profile
* env value unset / any other → respect ``profile.ac_generator_enabled``
"""


def is_ac_generator_active(
    profile: GateProfile,
    env: dict[str, str] | None = None,
) -> bool:
    """Return True iff the ACGenerator should run for *profile*.

    Combines the v9.0.0 PV-06 default-on profile flag
    (:pyattr:`GateProfile.ac_generator_enabled` — True for STRICT/AUDIT)
    with the :data:`ENV_FLAG` per-process override (R5 strict). Operators
    who want to disable the generator on a flipped profile set
    ``DEVOLAFLOW_AC_GEN=0`` per env-flags.md §2.10. The legacy
    ``acceptance_criteria: list[str]`` alias remains the contract path
    when the generator is opted out — preserving the v8.0.0 P-10 R5
    backward-compat shape.
    """
    source = env if env is not None else os.environ
    raw = source.get(ENV_FLAG, "")
    if raw == "0":
        return False
    if raw == "1":
        return True
    return bool(getattr(profile, "ac_generator_enabled", False))


# ─────────────────────────────────────────────────────────────────────────────
# Pattern catalogue
#
# Each entry maps a regex (case-insensitive) to a generator that returns
# (verification_type, verification_cmd, metric, threshold, description_suffix).
# Order matters — the FIRST matching pattern wins (more specific patterns
# come first). Patterns are intentionally small and explicit so the agent
# can predict the output without reading source.
# ─────────────────────────────────────────────────────────────────────────────


DEFAULT_TEST_COMMAND: str = "pytest tests/ -q"
DEFAULT_PERFORMANCE_METRIC: str = "latency_p95_ms"
DEFAULT_PERFORMANCE_THRESHOLD: str = "<= baseline"
DEFAULT_BUILD_COMMAND: str = "make build"
DEFAULT_LINT_COMMAND: str = "ruff check src/ tests/"


# Regex catalogue — keys are short labels surfaced in details for debugging.
# ``re.IGNORECASE`` is applied uniformly via :class:`ACGenerator`.
_PATTERN_FIX_BUG: re.Pattern[str] = re.compile(
    r"\b(fix|patch|repair|resolve)\b.*\b(bug|issue|defect|error|crash|regression)\b",
)
_PATTERN_FIX_ONLY: re.Pattern[str] = re.compile(
    r"\bfix\b",
)
_PATTERN_PERFORMANCE: re.Pattern[str] = re.compile(
    r"\b(improve|optimi[sz]e|reduce|speed\s?up|accelerate)\b.*"
    r"\b(performance|latency|throughput|speed|memory|cpu|footprint)\b"
    r"|\b(performance|latency|throughput)\b.*\b(improve|optimi[sz]e|reduce)\b",
)
_PATTERN_PERFORMANCE_SHORT: re.Pattern[str] = re.compile(
    r"\b(performance|latency|throughput|speedup)\b",
)
_PATTERN_IMPLEMENT: re.Pattern[str] = re.compile(
    r"\b(implement|build|add|introduce|create)\b.*\b(feature|module|class|function|api|endpoint)\b",
)
_PATTERN_IMPLEMENT_SHORT: re.Pattern[str] = re.compile(
    r"\b(implement|build|add|introduce|create|develop)\b",
)
_PATTERN_REFACTOR: re.Pattern[str] = re.compile(
    r"\b(refactor|cleanup|tidy|reorgani[sz]e|restructure|simplify)\b",
)
_PATTERN_TEST: re.Pattern[str] = re.compile(
    r"\b(write|add|extend|cover|backfill)\b.*\b(test|tests|coverage|spec|specs)\b"
    r"|\bcoverage\b",
)
_PATTERN_DOC: re.Pattern[str] = re.compile(
    r"\b(document|docs|documentation|readme|changelog|guide|tutorial)\b",
)
_PATTERN_BUILD: re.Pattern[str] = re.compile(
    r"\b(compile|build|bundle|package)\b",
)
_PATTERN_LINT: re.Pattern[str] = re.compile(
    r"\b(lint|format|style|ruff|flake8|black)\b",
)
# v14.4.0 (G-006) — per-type minimal templates for the newly AC-enabled
# impl-class profiles (migration / dependency-setup / repo-init / design).
# Appended AFTER every pre-v14.4.0 pattern in :func:`_match_patterns` so
# they only claim descriptions that previously fell through to the manual
# catch-all (strictly additive on the None-space; existing verdicts are
# byte-identical per the R5 backward-compat discipline).
_PATTERN_MIGRATION: re.Pattern[str] = re.compile(
    r"\b(migrate|migration|upgrade|port|convert)\b",
)
_PATTERN_SETUP: re.Pattern[str] = re.compile(
    r"\b(install|configure|setup|set\s+up|scaffold|bootstrap|provision|initiali[sz]e)\b",
)
_PATTERN_DESIGN: re.Pattern[str] = re.compile(
    r"\b(design|architect|blueprint)\b",
)


# Keywords that boost the specificity score (concrete proper nouns / metrics
# / file extensions). Lowercased; each unique hit adds a small bonus.
_SPECIFICITY_BONUS_TOKENS: frozenset[str] = frozenset(
    {
        "ms",
        "%",
        "s",
        "mb",
        "gb",
        "p50",
        "p95",
        "p99",
        ".py",
        ".ts",
        ".tsx",
        ".js",
        ".go",
        ".rs",
        ".cpp",
        "src/",
        "tests/",
        "schemas/",
        "workflow-system/",
        "subprocess",
        "pytest",
        "ruff",
        "make",
        "exit",
    }
)


# Vague phrases that depress the specificity score. Lower-cased, substring
# matched against the description so "make it better" or "improve overall"
# both score low even when surrounded by other words.
_VAGUE_PHRASES: tuple[str, ...] = (
    "make it better",
    "make it work",
    "make better",
    "look nice",
    "looks nice",
    "user friendly",
    "user-friendly",
    "more robust",
    "improve overall",
    "general improvements",
    "various improvements",
    "as needed",
    "if possible",
    "where appropriate",
    "best practices",
)


class ACGeneratorError(ValueError):
    """Raised when the generator cannot synthesize a valid criterion."""


@dataclass(frozen=True)
class _PatternHit:
    """Internal record of which pattern matched the task description."""

    label: str
    verification_type: VerificationType
    verification_cmd: str = ""
    metric: str = ""
    threshold: str = ""


def _match_patterns(description: str) -> _PatternHit | None:
    """Return the first matching :class:`_PatternHit` or ``None``.

    Order matters — more specific patterns come first. Returning
    ``None`` lets the caller fall back to the catch-all ``manual``
    criterion (S-5 — never silently emit a "test" criterion when the
    description gives no test signal).
    """
    if _PATTERN_FIX_BUG.search(description):
        return _PatternHit(
            label="fix_bug",
            verification_type="test",
            verification_cmd="pytest tests/ -q -x",
        )
    if _PATTERN_PERFORMANCE.search(description) or _PATTERN_PERFORMANCE_SHORT.search(description):
        return _PatternHit(
            label="performance",
            verification_type="metric",
            metric=DEFAULT_PERFORMANCE_METRIC,
            threshold=DEFAULT_PERFORMANCE_THRESHOLD,
        )
    if _PATTERN_IMPLEMENT.search(description):
        return _PatternHit(
            label="implement_feature",
            verification_type="test",
            verification_cmd=DEFAULT_TEST_COMMAND,
        )
    if _PATTERN_TEST.search(description):
        return _PatternHit(
            label="test_only",
            verification_type="test",
            verification_cmd=DEFAULT_TEST_COMMAND,
        )
    if _PATTERN_REFACTOR.search(description):
        return _PatternHit(
            label="refactor",
            verification_type="test",
            verification_cmd=DEFAULT_TEST_COMMAND,
        )
    if _PATTERN_BUILD.search(description):
        return _PatternHit(
            label="build",
            verification_type="test",
            verification_cmd=DEFAULT_BUILD_COMMAND,
        )
    if _PATTERN_LINT.search(description):
        return _PatternHit(
            label="lint",
            verification_type="test",
            verification_cmd=DEFAULT_LINT_COMMAND,
        )
    if _PATTERN_FIX_ONLY.search(description):
        return _PatternHit(
            label="fix_generic",
            verification_type="test",
            verification_cmd=DEFAULT_TEST_COMMAND,
        )
    if _PATTERN_IMPLEMENT_SHORT.search(description):
        return _PatternHit(
            label="implement_generic",
            verification_type="test",
            verification_cmd=DEFAULT_TEST_COMMAND,
        )
    if _PATTERN_DOC.search(description):
        return _PatternHit(
            label="documentation",
            verification_type="manual",
        )
    # v14.4.0 (G-006) — appended AFTER all pre-v14.4.0 patterns so the
    # new templates only claim previously-unmatched (manual catch-all)
    # descriptions. Order within the group: migration > setup > design
    # (a "design the migration plan" description is migration-shaped).
    if _PATTERN_MIGRATION.search(description):
        return _PatternHit(
            label="migration",
            verification_type="test",
            verification_cmd=DEFAULT_TEST_COMMAND,
        )
    if _PATTERN_SETUP.search(description):
        return _PatternHit(
            label="setup_environment",
            verification_type="test",
            verification_cmd=DEFAULT_TEST_COMMAND,
        )
    if _PATTERN_DESIGN.search(description):
        return _PatternHit(
            label="design",
            verification_type="manual",
        )
    return None


def _completeness_score(criterion: AcceptanceCriterion) -> float:
    """Score completeness (0-100) of a single criterion.

    Required: ``id`` and ``description`` are always present (the
    dataclass enforces this in ``__post_init__``). Type-specific fields
    (``verification_cmd`` for ``test``, ``metric`` + ``threshold`` for
    ``metric``) earn additional credit. ``manual`` criteria earn full
    credit when description is non-trivial because manual checks have no
    type-specific payload.
    """
    base = 60.0  # id + description always present (frozen dataclass invariant)
    if criterion.verification_type == "test":
        if criterion.verification_cmd:
            base += 40.0
    elif criterion.verification_type == "metric":
        if criterion.metric:
            base += 25.0
        if criterion.threshold:
            base += 15.0
    else:  # manual
        if len(criterion.description) >= 20:
            base += 40.0
        else:
            base += 20.0
    return min(100.0, base)


def _testability_score(criterion: AcceptanceCriterion) -> float:
    """Score testability (0-100) of a single criterion.

    ``test`` criteria with a non-empty ``verification_cmd`` are fully
    testable (100). ``metric`` criteria with both ``metric`` AND
    ``threshold`` are fully testable. ``manual`` criteria are explicitly
    NOT auto-testable (20 — capped low so the dimension reflects the
    cost of human review).
    """
    if criterion.verification_type == "test":
        return 100.0 if criterion.verification_cmd else 40.0
    if criterion.verification_type == "metric":
        if criterion.metric and criterion.threshold:
            return 100.0
        if criterion.metric or criterion.threshold:
            return 60.0
        return 30.0
    return 20.0  # manual


def _specificity_score(criterion: AcceptanceCriterion) -> float:
    """Score specificity (0-100) of a single criterion.

    Heuristics:
    * Description length 30-200 chars → +30 (sweet spot)
    * 10-29 chars → +15 (terse but acceptable)
    * < 10 chars → +0
    * > 200 chars → +20 (verbose; clarity penalty)
    * Each unique :data:`_SPECIFICITY_BONUS_TOKENS` hit → +6 (max +30)
    * verification_cmd / metric / threshold present → +20
    * Each :data:`_VAGUE_PHRASES` hit → -25 (capped)
    """
    desc = criterion.description.lower()
    length = len(desc)
    if 30 <= length <= 200:
        score = 30.0
    elif 10 <= length < 30:
        score = 15.0
    elif length > 200:
        score = 20.0
    else:
        score = 0.0

    bonus_tokens = sum(1 for tok in _SPECIFICITY_BONUS_TOKENS if tok in desc)
    score += min(30.0, bonus_tokens * 6.0)

    if criterion.verification_cmd or criterion.metric or criterion.threshold:
        score += 20.0

    vague_hits = sum(1 for phrase in _VAGUE_PHRASES if phrase in desc)
    score -= min(50.0, vague_hits * 25.0)

    # Verification-type baseline credit: structured types earn a small
    # baseline (10) on top so a fully-specified test criterion beats a
    # bare manual one in the "specificity" dimension.
    if criterion.verification_type in ("test", "metric"):
        score += 10.0

    return max(0.0, min(100.0, score))


def score_quality(criteria: list[AcceptanceCriterion]) -> dict[str, float]:
    """Score a criteria list across 3 dimensions (0-100 per dimension).

    Returns a dict with keys ``completeness`` / ``testability`` /
    ``specificity``. An empty list returns ``{dim: 0.0 for dim in keys}``
    — never raises (S-5 — let callers act on the zero verdict).

    Each dimension is the arithmetic mean across criteria, then rounded
    to 2 decimals. Per ``patch_plan §3 P-10 AC #5``: the
    ``score_quality`` result MUST carry the 3 keys exactly so dispatch
    consumers can index them deterministically.
    """
    if not criteria:
        return {"completeness": 0.0, "testability": 0.0, "specificity": 0.0}

    n = float(len(criteria))
    completeness = sum(_completeness_score(c) for c in criteria) / n
    testability = sum(_testability_score(c) for c in criteria) / n
    specificity = sum(_specificity_score(c) for c in criteria) / n
    return {
        "completeness": round(completeness, 2),
        "testability": round(testability, 2),
        "specificity": round(specificity, 2),
    }


class ACGenerator:
    """Generate structured acceptance criteria from a task description.

    Pure-Python pattern matching — no LLM, no subprocess. Stateless;
    instances may be reused across dispatches.

    Per ``patch_plan §3 P-10 AC #1/#2/#3``:

    - ``generate("fix bug X")`` returns ≥ 1 criterion with
      ``verification_type='test'`` and a non-empty ``verification_cmd``.
    - ``generate("improve performance")`` returns ≥ 1 criterion with
      ``verification_type='metric'`` carrying both ``metric`` AND
      ``threshold``.
    - ``score_quality(criteria)`` returns a 3-key dict
      ``{completeness, testability, specificity}``.

    Examples
    --------
    >>> gen = ACGenerator()
    >>> [c.verification_type for c in gen.generate("fix bug in auth")]
    ['test']
    >>> sorted(gen.score_quality(gen.generate("fix bug in auth")))
    ['completeness', 'specificity', 'testability']
    """

    def __init__(
        self,
        *,
        default_test_command: str = DEFAULT_TEST_COMMAND,
        default_metric: str = DEFAULT_PERFORMANCE_METRIC,
        default_threshold: str = DEFAULT_PERFORMANCE_THRESHOLD,
        id_prefix: str = "AC",
    ) -> None:
        self.default_test_command = default_test_command
        self.default_metric = default_metric
        self.default_threshold = default_threshold
        self.id_prefix = id_prefix

    def _next_id(self, sequence: int) -> str:
        return f"{self.id_prefix}-{sequence:03d}"

    def generate(self, task_description: str) -> list[AcceptanceCriterion]:
        """Return a list of structured criteria for *task_description*.

        Always returns at least 1 criterion (S-5 — never an empty list,
        which would silently disable downstream auto-evaluation). Empty
        / whitespace-only input raises :class:`ACGeneratorError` so the
        caller cannot accidentally ship a zero-criterion dispatch.

        Parameters
        ----------
        task_description:
            Free-form description of the work item. Case-insensitive
            pattern matching picks the dominant verification type.

        Returns
        -------
        list[AcceptanceCriterion]
            Length ≥ 1. The first criterion reflects the dominant
            pattern; subsequent criteria carry secondary asserts (e.g.
            "fix bug" criteria gain a "no regression" companion).
        """
        if not isinstance(task_description, str):
            raise ACGeneratorError(
                f"task_description must be a string (got {type(task_description).__name__})"
            )
        cleaned = task_description.strip()
        if not cleaned:
            raise ACGeneratorError("task_description must be non-empty")

        # Apply case-insensitive matching by lower-casing for the regex
        # search; preserve the original spelling in the description.
        lowered = cleaned.lower()
        hit = _match_patterns(lowered)

        criteria: list[AcceptanceCriterion] = []
        sequence = 1

        if hit is None:
            # Catch-all: emit a single MANUAL criterion. The agent can
            # refine this later via score_quality + iteration.
            criteria.append(
                AcceptanceCriterion(
                    id=self._next_id(sequence),
                    description=f"Manual review: {cleaned}",
                    verification_type="manual",
                )
            )
            return criteria

        primary_description = self._describe_primary(hit, cleaned)
        criteria.append(
            AcceptanceCriterion(
                id=self._next_id(sequence),
                description=primary_description,
                verification_type=hit.verification_type,
                verification_cmd=hit.verification_cmd,
                metric=hit.metric,
                threshold=hit.threshold,
            )
        )
        sequence += 1

        for companion in self._companions(hit, cleaned):
            criteria.append(companion._replace_id(self._next_id(sequence)))
            sequence += 1

        return criteria

    @staticmethod
    def _describe_primary(hit: _PatternHit, original: str) -> str:
        """Build a human-readable description for the primary criterion."""
        if hit.verification_type == "test":
            return (
                f"Verify '{original}' via `{hit.verification_cmd}` exits 0 "
                f"(no failing tests, label={hit.label})"
            )
        if hit.verification_type == "metric":
            return (
                f"Measure '{hit.metric}' for '{original}' satisfies "
                f"threshold `{hit.threshold}` (label={hit.label})"
            )
        return f"Manual review of '{original}' (label={hit.label})"

    @staticmethod
    def _companions(hit: _PatternHit, original: str) -> list[_CompanionTemplate]:
        """Return secondary criteria templates (each ≤ 1 per primary).

        Per ``patch_plan §3 P-10 AC #4``: each generated criterion list
        SHOULD include a "no regression" companion when the primary is a
        bug-fix or performance optimization, so downstream gates catch
        side-effects automatically.
        """
        if hit.label in {"fix_bug", "fix_generic"}:
            return [
                _CompanionTemplate(
                    description=(
                        f"Regression guard for '{original}': "
                        f"`{DEFAULT_TEST_COMMAND}` exits 0 (no NEW failures vs main)"
                    ),
                    verification_type="test",
                    verification_cmd=DEFAULT_TEST_COMMAND,
                )
            ]
        if hit.label == "performance":
            return [
                _CompanionTemplate(
                    description=(
                        f"Regression guard for '{original}': existing "
                        f"`pytest tests/test_benchmarks.py -v` shows 0 scenarios "
                        f"regressed > 5pp"
                    ),
                    verification_type="test",
                    verification_cmd="pytest tests/test_benchmarks.py -v",
                )
            ]
        if hit.label == "migration":
            # v14.4.0 (G-006) — migrations get the same regression-guard
            # companion shape as bug fixes: the migrated surface MUST NOT
            # introduce NEW failures vs the pre-migration baseline.
            return [
                _CompanionTemplate(
                    description=(
                        f"Compatibility guard for '{original}': "
                        f"`{DEFAULT_TEST_COMMAND}` exits 0 (no NEW failures "
                        f"vs the pre-migration baseline)"
                    ),
                    verification_type="test",
                    verification_cmd=DEFAULT_TEST_COMMAND,
                )
            ]
        if hit.label in {"implement_feature", "implement_generic"}:
            return [
                _CompanionTemplate(
                    description=(
                        f"Coverage gate for '{original}': "
                        f"`pytest tests/ --cov=devolaflow --cov-report=term-missing` "
                        f"reports >= 80 % per CP-2"
                    ),
                    verification_type="test",
                    verification_cmd=("pytest tests/ --cov=devolaflow --cov-report=term-missing"),
                )
            ]
        return []

    def score_quality(
        self,
        criteria: list[AcceptanceCriterion],
    ) -> dict[str, float]:
        """Delegate to the module-level :func:`score_quality` for ergonomic
        access on the generator instance."""
        return score_quality(criteria)


@dataclass(frozen=True)
class _CompanionTemplate:
    """Internal template for secondary criteria — gains an id when committed."""

    description: str
    verification_type: VerificationType
    verification_cmd: str = ""
    metric: str = ""
    threshold: str = ""

    def _replace_id(self, new_id: str) -> AcceptanceCriterion:
        return AcceptanceCriterion(
            id=new_id,
            description=self.description,
            verification_type=self.verification_type,
            verification_cmd=self.verification_cmd,
            metric=self.metric,
            threshold=self.threshold,
        )


# Re-export the structured criterion type so callers can build
# :class:`AcceptanceCriterion` instances by hand without importing from
# :mod:`devolaflow.gate.models`. ``VerificationType`` is the typing
# alias surfaced through the same import.
__all__.extend(["AcceptanceCriterion", "VerificationType"])
