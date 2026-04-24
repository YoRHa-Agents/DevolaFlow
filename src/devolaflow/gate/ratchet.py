"""Monotonic Ratchet Guarantee — convergence-loop best-score guard.

v8.0.0 (P-07) — implements primitive 4.11 from
``.local/research/tweet_analysis_harness_engineering_v7.8.md`` §4.11 and
``.local/research/v8.0.0_patch_plan.md`` §3 P-07. Closes the largest
architectural gap (G13) — multi-round convergence loops could regress
silently from a previously-attained best score, wasting tokens and
masking real degradations.

The ratchet maintains an append-only log of per-round oracle scores and
emits one of 4 verdicts on every new round (per ``patch_plan §3 P-07
AC #1-#4``):

============  ===================================================
Verdict       When
============  ===================================================
``ADVANCE``   New score strictly above ``best_score``; new best.
``TOLERATE``  Score within ``regression_tolerance`` of best;
              best preserved, no escalation.
``ROLLBACK``  Score below best by more than the tolerance for
              ``max_regressions`` consecutive rounds; restore the
              saved :class:`ArtifactSnapshot`.
``ESCALATE``  A round AFTER a ROLLBACK still cannot exceed best;
              the loop is stuck and must escalate per P4 bounded
              retry.
============  ===================================================

The deterministic oracle subset (test + lint + build, review_findings
EXCLUDED) is computed by :func:`compute_deterministic_oracle_score` and
fed verbatim into :meth:`MonotonicRatchet.record_round`. Excluding
``review_findings`` enforces the Karpathy "non-gameable success
criteria" principle per upstream tweet analysis ``v7.8`` §4.11 — an
agent cannot lift its ratchet by silencing or fabricating review
findings (the S/O/R / Subjective Overrating Risk).

Honors S-5 (No Silent Failures): every invalid input raises
:class:`ValueError`; every recorded round returns a verdict (never
``None``).

v9.0.0 PV-06 (v8.5.1) — Theme T5 #3 default-on flip. STRICT and AUDIT
profiles default :pyattr:`GateProfile.ratchet_enabled` to ``True``.
Operators opt OUT via ``DEVOLAFLOW_GATE_RATCHET=0`` per env-flags.md
§2.8 (R5 strict). The :func:`is_gate_ratchet_active` helper combines
both signals so callers do not branch on the env-flag manually.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field

from devolaflow.gate.models import (
    ArtifactSnapshot,
    GateInput,
    GateProfile,
    RatchetAction,
)

# v9.0.0 PV-06 (v8.5.1) — Theme T5 #3 env-flag (R5 strict).
ENV_FLAG: str = "DEVOLAFLOW_GATE_RATCHET"
"""Env-flag controlling the v9.0.0 PV-06 default-on flip override.

R5 strict per ``workflow-system/agent/references/env-flags.md`` §2 parsing:

* env value EXACTLY ``"1"`` → force the ratchet active regardless of profile
* env value EXACTLY ``"0"`` → force the ratchet inactive regardless of profile
* env value unset / any other → respect ``profile.ratchet_enabled``
"""


def is_gate_ratchet_active(
    profile: GateProfile,
    env: dict[str, str] | None = None,
) -> bool:
    """Return True iff the monotonic ratchet should run for *profile*.

    Combines the v9.0.0 PV-06 default-on profile flag
    (:pyattr:`GateProfile.ratchet_enabled` — True for STRICT/AUDIT) with the
    :data:`ENV_FLAG` per-process override (R5 strict — EXACTLY ``"0"`` opts
    out, EXACTLY ``"1"`` forces on). Operators who want to disable the
    ratchet on a flipped profile set ``DEVOLAFLOW_GATE_RATCHET=0`` per
    env-flags.md §2.8.
    """
    source = env if env is not None else os.environ
    raw = source.get(ENV_FLAG, "")
    if raw == "0":
        return False
    if raw == "1":
        return True
    return bool(getattr(profile, "ratchet_enabled", False))


# ─────────────────────────────────────────────────────────────────────────────
# Tunable defaults — see ``patch_plan §3 P-07 AC #2/#3``.
# ─────────────────────────────────────────────────────────────────────────────

# Fraction of the 0-100 oracle scale treated as verifier-side jitter
# instead of real regression. ``0.02`` ≈ a ±2pp band — picked to align
# with the existing ``GateProfile.noise_tolerance_pct`` default the
# convergence-noise filter (P-01) and ratchet share.
DEFAULT_REGRESSION_TOLERANCE: float = 0.02

# Number of consecutive within/below-tolerance rounds before the ratchet
# emits ``ROLLBACK``. Two rounds matches the existing detect_stagnation
# semantic ("two consecutive non-improving rounds = stagnation") so the
# ratchet does not over-fire on a single jitter sample.
DEFAULT_MAX_REGRESSIONS: int = 2

# Oracle-subset weights — test passes the most signal because it is the
# direct correctness probe; lint and build are deterministic guard rails.
# Weights sum to 1.0; ``compute_deterministic_oracle_score`` uses them
# verbatim so the score lives in the canonical 0..100 range.
ORACLE_WEIGHT_TEST: float = 0.50
ORACLE_WEIGHT_LINT: float = 0.20
ORACLE_WEIGHT_BUILD: float = 0.30


# ─────────────────────────────────────────────────────────────────────────────
# Deterministic oracle score
#
# Pulled into a free function (instead of a method on MonotonicRatchet)
# so the scorer module can call it without importing the ratchet class
# (one-way dependency: scorer → ratchet, never the reverse). The oracle
# intentionally does NOT consult ``review_findings`` — see the module
# docstring for the S/O/R reasoning.
# ─────────────────────────────────────────────────────────────────────────────


# Counter key pairs consulted by :func:`_check_pct` when interpolating
# a partial-pass score from ``CheckResult.details``. The first match
# wins per pair — order is deterministic so the oracle is stable.
_CHECK_COUNTER_KEYS: tuple[tuple[str, str], ...] = (
    ("tests_passed", "tests_total"),
    ("checks_passed", "checks_total"),
    ("files_passed", "files_total"),
)


def _first_int(details: dict[str, object], keys: tuple[str, ...]) -> int:
    """Return the first integer value found under ``keys`` in ``details``.

    ``None`` and missing keys are skipped. Defaults to ``0`` when no
    matching key holds a value (matches the legacy ``next(..., 0)``
    semantics the oracle relies on for partial-pass interpolation).
    """
    for key in keys:
        value = details.get(key)
        if value is not None:
            return int(value)
    return 0


def _check_pct(check_status: str, details: dict[str, object]) -> float:
    """Return the 0..100 success ratio for a single :class:`CheckResult`.

    ``pass`` → 100, ``skip`` → 100 (skipped checks count as neutral
    rather than failures so the oracle stays within 0..100), ``fail`` →
    interpolate from ``passed/total`` when ``details`` carries the
    counters, otherwise 0.

    The interpolation lets a partial-pass test run (e.g. 95/100 unit
    tests) earn a partial oracle score, matching the existing semantics
    of :func:`devolaflow.gate.scorer.acceptance_verification_score`.
    """
    if check_status in ("pass", "skip"):
        return 100.0
    for passed_key, total_key in _CHECK_COUNTER_KEYS:
        total = _first_int(details, (total_key,))
        if total > 0:
            passed = _first_int(details, (passed_key,))
            return max(0.0, min(100.0, (passed / total) * 100.0))
    return 0.0


def compute_deterministic_oracle_score(state: GateInput) -> float:
    """Compute the deterministic oracle score for a :class:`GateInput`.

    The oracle is a weighted sum over EXACTLY three fields:

    - ``state.test_results`` → :data:`ORACLE_WEIGHT_TEST`
    - ``state.lint_status``  → :data:`ORACLE_WEIGHT_LINT`
    - ``state.build_status`` → :data:`ORACLE_WEIGHT_BUILD`

    ``state.review_findings`` and any other field on :class:`GateInput`
    are deliberately ignored (per ``patch_plan §3 P-07 AC #5`` — adding
    or removing review_findings MUST NOT change the oracle). This is the
    Karpathy "non-gameable success criteria" anchor: the agent cannot
    lift its ratchet score by silencing or fabricating review findings
    (the Subjective Overrating Risk / S/O/R).

    Returns
    -------
    float
        Score rounded to 4 decimal places, in ``[0.0, 100.0]``.
    """
    test_pct = _check_pct(state.test_results.status, dict(state.test_results.details or {}))
    lint_pct = _check_pct(state.lint_status.status, dict(state.lint_status.details or {}))
    build_pct = _check_pct(state.build_status.status, dict(state.build_status.details or {}))
    score = (
        test_pct * ORACLE_WEIGHT_TEST
        + lint_pct * ORACLE_WEIGHT_LINT
        + build_pct * ORACLE_WEIGHT_BUILD
    )
    return round(max(0.0, min(100.0, score)), 4)


def hash_payload(payload: dict[str, object]) -> str:
    """Return a stable SHA-256 hex digest for ``payload``.

    Used by :meth:`MonotonicRatchet.record_round` when the caller
    supplies a payload but no explicit hash. Uses ``json.dumps`` with
    ``sort_keys=True`` + ``default=str`` so non-string keys / values
    serialize deterministically.
    """
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


# ─────────────────────────────────────────────────────────────────────────────
# Per-round log entry (separate from ArtifactSnapshot so the log keeps
# every round, not just the bests). Frozen for the same hashing /
# defensive-copy reasons as the rest of gate.models.
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class RatchetLogEntry:
    """One row in :class:`MonotonicRatchet.history`.

    Records the verdict produced for the round AND the score that
    triggered it so downstream reporters / EvoBench scenarios can replay
    the trajectory verbatim. Best-score rotation is captured by
    :pyattr:`new_best`.
    """

    round_num: int
    score: float
    action: RatchetAction
    new_best: bool
    note: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# MonotonicRatchet — the public surface.
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class MonotonicRatchet:
    """Append-only ratchet for multi-round convergence loops.

    Construct once per task (or per orchestrator session), then call
    :meth:`record_round` after every round. The ratchet preserves the
    best :class:`ArtifactSnapshot` across rounds and guards against
    silent regression / S/O/R-driven gaming (see module docstring).

    Parameters
    ----------
    regression_tolerance:
        Fraction of the 0-100 oracle scale treated as jitter. Default
        :data:`DEFAULT_REGRESSION_TOLERANCE` (``0.02`` ≈ ±2pp).
    max_regressions:
        Number of consecutive within / below-tolerance rounds before the
        ratchet emits ``ROLLBACK``. Default :data:`DEFAULT_MAX_REGRESSIONS`
        (``2`` rounds, matches stagnation semantic).
    """

    regression_tolerance: float = DEFAULT_REGRESSION_TOLERANCE
    max_regressions: int = DEFAULT_MAX_REGRESSIONS

    best_score: float = 0.0
    best_round: int = 0
    best_artifact_snapshot: ArtifactSnapshot | None = None

    history: list[RatchetLogEntry] = field(default_factory=list)
    consecutive_regressions: int = 0
    last_action: RatchetAction | None = None

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------

    def record_round(
        self,
        round_num: int,
        score: float,
        artifact: dict[str, object] | None = None,
        artifact_hash: str | None = None,
    ) -> RatchetAction:
        """Record one convergence round and return the verdict.

        Parameters
        ----------
        round_num:
            1-based round ordinal. Strictly monotonic — supplying a
            ``round_num`` ≤ the most recent recorded round raises
            :class:`ValueError` (S-5 — never silently mis-order).
        score:
            Deterministic oracle score in ``[0.0, 100.0]``. Out-of-range
            values raise :class:`ValueError`.
        artifact:
            Optional state payload to snapshot if this round becomes the
            new best. Stored verbatim on
            :pyattr:`best_artifact_snapshot.payload` for caller-side
            rollback. ``None`` keeps the previous snapshot intact.
        artifact_hash:
            Optional explicit SHA-256 hex digest. When ``None`` (the
            default) and ``artifact`` is provided, the hash is computed
            via :func:`hash_payload`.

        Returns
        -------
        RatchetAction
            One of ``ADVANCE`` / ``TOLERATE`` / ``ROLLBACK`` /
            ``ESCALATE`` per the verdict matrix in the module docstring.
        """
        self._validate_inputs(round_num, score)
        action = self._classify(score)
        prior_best_score = self.best_score
        prior_best_round = self.best_round
        self._apply_action(action, round_num, score, artifact, artifact_hash)
        self.history.append(
            RatchetLogEntry(
                round_num=round_num,
                score=score,
                action=action,
                new_best=action is RatchetAction.ADVANCE,
                note=self._build_note(action, score, prior_best_score, prior_best_round),
            )
        )
        self.last_action = action
        return action

    def reset(self) -> None:
        """Clear every recorded round and best-state.

        Useful in tests and when an orchestrator restarts a task from
        scratch. Does NOT change ``regression_tolerance`` or
        ``max_regressions``.
        """
        self.best_score = 0.0
        self.best_round = 0
        self.best_artifact_snapshot = None
        self.history = []
        self.consecutive_regressions = 0
        self.last_action = None

    @property
    def tolerance_band(self) -> float:
        """Return the 0..100 absolute tolerance band derived from
        :pyattr:`regression_tolerance`.

        For example ``regression_tolerance=0.02`` → ``2.0``.
        """
        return round(self.regression_tolerance * 100.0, 4)

    # ---------------------------------------------------------------------
    # Internal helpers — kept tiny so each function's cyclomatic
    # complexity stays well under the C-1 / NineS ceiling.
    # ---------------------------------------------------------------------

    def _validate_inputs(self, round_num: int, score: float) -> None:
        """Raise if ``round_num`` / ``score`` violate the contract."""
        if not isinstance(round_num, int) or round_num < 1:
            raise ValueError(f"round_num must be a positive int (got {round_num!r})")
        if self.history and round_num <= self.history[-1].round_num:
            raise ValueError(
                f"round_num must be strictly greater than the last recorded round "
                f"({self.history[-1].round_num}); got {round_num}"
            )
        if not isinstance(score, int | float):
            raise ValueError(f"score must be numeric (got {type(score).__name__})")
        if score < 0.0 or score > 100.0:
            raise ValueError(f"score must be in [0.0, 100.0] (got {score})")

    def _classify(self, score: float) -> RatchetAction:
        """Choose the verdict for ``score`` against the current best.

        Decision matrix (per ``patch_plan §3 P-07 AC #1-#4``):

        - first round (no best) → ``ADVANCE``;
        - score strictly above best → ``ADVANCE``;
        - score within ±tolerance of best → ``TOLERATE``;
        - score below best by more than tolerance:
            - if previous verdict was ``ROLLBACK`` and we still cannot
              beat best → ``ESCALATE`` (loop is stuck);
            - else if this is the
              ``max_regressions``-th consecutive regression → ``ROLLBACK``;
            - else → ``TOLERATE`` (one-off jitter, keep iterating).
        """
        band = self.tolerance_band
        if self.best_round == 0:
            return RatchetAction.ADVANCE
        if score > self.best_score:
            return RatchetAction.ADVANCE
        if score >= self.best_score - band:
            return RatchetAction.TOLERATE
        if self.last_action is RatchetAction.ROLLBACK and score <= self.best_score:
            return RatchetAction.ESCALATE
        if self.consecutive_regressions + 1 >= self.max_regressions:
            return RatchetAction.ROLLBACK
        return RatchetAction.TOLERATE

    def _apply_action(
        self,
        action: RatchetAction,
        round_num: int,
        score: float,
        artifact: dict[str, object] | None,
        artifact_hash: str | None,
    ) -> None:
        """Mutate ratchet state to reflect ``action`` for ``round_num``."""
        if action is RatchetAction.ADVANCE:
            self._rotate_best(round_num, score, artifact, artifact_hash)
            self.consecutive_regressions = 0
            return
        if action is RatchetAction.TOLERATE:
            band = self.tolerance_band
            if score < self.best_score - band:
                self.consecutive_regressions += 1
            else:
                self.consecutive_regressions = 0
            return
        if action is RatchetAction.ROLLBACK:
            self.consecutive_regressions += 1
            return
        if action is RatchetAction.ESCALATE:
            self.consecutive_regressions += 1
            return

    def _rotate_best(
        self,
        round_num: int,
        score: float,
        artifact: dict[str, object] | None,
        artifact_hash: str | None,
    ) -> None:
        """Save ``round_num`` as the new best and snapshot the artifact."""
        self.best_score = score
        self.best_round = round_num
        if artifact is not None:
            payload = dict(artifact)
            digest = artifact_hash if artifact_hash is not None else hash_payload(payload)
            self.best_artifact_snapshot = ArtifactSnapshot(
                round_num=round_num,
                score=score,
                payload_hash=digest,
                payload=payload,
            )

    def _build_note(
        self,
        action: RatchetAction,
        score: float,
        prior_best_score: float,
        prior_best_round: int,
    ) -> str:
        """Render a short human-facing note for :class:`RatchetLogEntry`.

        ``prior_best_score`` / ``prior_best_round`` are passed in
        explicitly because :meth:`_apply_action` has already rotated the
        best by the time this note is built (when ``action`` is
        ``ADVANCE``). Threading the prior state through avoids reading
        post-mutation state and mis-classifying the first-round path.
        """
        if action is RatchetAction.ADVANCE:
            if prior_best_round == 0:
                return f"first round; baseline best={score:.2f}"
            delta = score - prior_best_score
            return f"new best (Δ={delta:+.2f} vs prior best={prior_best_score:.2f})"
        if action is RatchetAction.TOLERATE:
            return f"within ±{self.tolerance_band:.2f} of best={self.best_score:.2f}"
        if action is RatchetAction.ROLLBACK:
            return (
                f"regression > {self.tolerance_band:.2f} for "
                f"{self.consecutive_regressions} round(s); "
                f"restore snapshot from round {self.best_round}"
            )
        return (
            f"post-rollback round still cannot exceed best={self.best_score:.2f} "
            f"(score={score:.2f}); escalate per P4 bounded retry"
        )
