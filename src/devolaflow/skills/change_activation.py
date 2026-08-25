"""Change-driven workflow activation heuristic (v9.1.2 PV-02 + Rule A-6).

The two public functions in this module are the prompt-side enforcement
surface that Architecture rule **A-6** ("Workspace Engagement Auto-
Activation" — see ``.rules/architecture.mdc``) cites. L0 dispatchers
call :func:`classify_complexity` to derive a complexity tier from a
candidate task (file count + LOC estimate + cross-cutting flag), then
combine it with the env-flag state via :func:`activation_verdict` to
get a three-valued verdict the SKILL.md §"Quick Action Decision" sub-
table maps to a human-readable action.

Design constraints:

* **Pure functions, zero filesystem I/O.** :func:`classify_complexity`
  and :func:`activation_verdict` consume only their typed arguments
  and return a string literal. The single env-var read happens in
  :func:`from_env`, kept as a thin separate wrapper so unit tests can
  exercise the verdict logic without monkeypatching ``os.environ``.
* **R5 strict default-OFF** per W-20 reuse-first env-flag policy:
  ``DEVOLAFLOW_AGENT_WORKSPACE`` is REUSED (same activation surface
  as the v9.1.1 PV-01 SKILL.md "Workspace Engagement" guidance and
  the v9.1.3 PV-03 ``pre_handoff`` hook will use). Absent or any
  value other than the literal string ``"1"`` = default-OFF.
* **Three verdict values are the public contract.** Operators rely on
  the literal strings (``MUST_OPEN_CHANGE`` / ``SHOULD_OPEN_CHANGE``
  / ``NO_CHANGE``); changing any of them is a release blocker.
* **No silent failures (S-5).** Invalid complexity strings raise
  :class:`ValueError` with a verbatim message naming the bad value;
  the heuristic does NOT silently coerce unknown values to a default.

Public API:

* :data:`Complexity` — ``Literal["TRIVIAL", "SIMPLE", "STANDARD",
  "COMPLEX"]``.
* :data:`ActivationVerdict` — ``Literal["MUST_OPEN_CHANGE",
  "SHOULD_OPEN_CHANGE", "NO_CHANGE"]``.
* :data:`CascadeRequirement` — ``Literal["CASCADE_REQUIRED",
  "CASCADE_OPTIONAL"]``.
* :func:`cascade_requirement` — ``(complexity) -> CascadeRequirement``.
* :func:`classify_complexity` — ``(files_count, loc_estimate,
  is_cross_cutting=False) -> Complexity``.
* :func:`activation_verdict` — ``(complexity, env_agent_workspace,
  opt_out=False) -> ActivationVerdict``.
* :func:`from_env` — ``() -> bool``; the single env-var read site.
* :data:`ENV_FLAG_NAME` — the env-var name (``"DEVOLAFLOW_AGENT_WORKSPACE"``).
* :data:`ENV_FLAG_TRUTHY` — the only truthy value (``"1"``); R5 strict.

Source: v9.2.0 cycle plan §PV-02 — ``.cursor/plans/workspace-
capability-activation_ec560bc8.plan.md``; rule A-6 in
``.rules/architecture.mdc``.
"""

from __future__ import annotations

import os
from typing import Final, Literal, get_args

__all__ = [
    "ENV_FLAG_NAME",
    "ENV_FLAG_TRUTHY",
    "ActivationVerdict",
    "CascadeRequirement",
    "Complexity",
    "activation_verdict",
    "cascade_requirement",
    "classify_complexity",
    "from_env",
]


# ── Public type aliases ────────────────────────────────────────────────
# Literal types are the public contract; the runtime tuples below derive
# from them via typing.get_args so adding a new tier requires editing
# exactly one Literal alias (single-source-of-truth per A-5 spirit).
Complexity = Literal["TRIVIAL", "SIMPLE", "STANDARD", "COMPLEX"]
ActivationVerdict = Literal["MUST_OPEN_CHANGE", "SHOULD_OPEN_CHANGE", "NO_CHANGE"]
# v11.1.0 PV-02 — cascade-shape verdict (G-CLASSIFY-1 Candidate C); see
# ``.local/research/v11.1.0_pv02_decision.md`` §1.
CascadeRequirement = Literal["CASCADE_REQUIRED", "CASCADE_OPTIONAL"]

_VALID_COMPLEXITIES: Final[tuple[str, ...]] = get_args(Complexity)
_VALID_VERDICTS: Final[tuple[str, ...]] = get_args(ActivationVerdict)
_VALID_CASCADE_REQUIREMENTS: Final[tuple[str, ...]] = get_args(CascadeRequirement)


# ── Env-flag constants (W-20 reuse-first) ──────────────────────────────
# REUSED from the v9.1.1 PV-01 SKILL.md §"Workspace Engagement" surface;
# v9.1.3 PV-03 will REUSE the same flag for the pre_handoff hook so the
# activation contract stays single-surface (W-20 §1 reuse test passes:
# same activation surface as the existing flag).
ENV_FLAG_NAME: Final[str] = "DEVOLAFLOW_AGENT_WORKSPACE"
# R5 strict: the env-var value MUST be EXACTLY the literal string "1"
# to activate. Any other value (including "true", "yes", " 1", "1\n")
# is treated as default-OFF. This matches every other DevolaFlow
# DEVOLAFLOW_* opt-in flag's parsing per `references/env-flags.md` §1.
ENV_FLAG_TRUTHY: Final[str] = "1"


# ── Complexity classification thresholds ───────────────────────────────
# Mirror the SKILL.md §"Quick Action Decision" table verbatim:
#   * Trivial  — single file, < 20 lines, obvious fix
#   * Simple   — 1-3 files, clear scope, < 1 hour
#   * Standard — 3-10 files, needs design or review
#   * Complex  — 10+ files, cross-cutting, multi-day
#
# Thresholds picked to match the TABLE rows exactly so an operator can
# eyeball the SKILL.md table and predict the classifier output without
# re-reading source. The ``is_cross_cutting`` boolean is a forced
# upgrade lever — a single-file change that touches a cross-cutting
# concern (e.g. layout invariant, env-flag inventory) MUST be at least
# STANDARD per the cycle plan §PV-02 (the heuristic is conservative —
# better to scaffold a change folder for a cross-cutting trivial edit
# than to skip the audit trail).
_TRIVIAL_FILE_CEILING: Final[int] = 1
_TRIVIAL_LOC_CEILING: Final[int] = 20
_SIMPLE_FILE_CEILING: Final[int] = 3
_STANDARD_FILE_CEILING: Final[int] = 10


def classify_complexity(
    files_count: int,
    loc_estimate: int,
    is_cross_cutting: bool = False,
) -> Complexity:
    """Classify a candidate task into one of four complexity tiers.

    Args:
      files_count: Number of files the task is expected to touch
        (must be ``>= 0``).
      loc_estimate: Estimated lines-of-code change across all files
        (must be ``>= 0``). Used only for the TRIVIAL tier ceiling.
      is_cross_cutting: When ``True``, forces the verdict to at least
        STANDARD regardless of file count / LOC. Use for changes that
        touch the layout invariant, the env-flag inventory, the rule
        corpus, or any other cross-cutting concern.

    Returns:
      A :data:`Complexity` literal — one of ``"TRIVIAL"``,
      ``"SIMPLE"``, ``"STANDARD"``, ``"COMPLEX"``.

    Raises:
      ValueError: when ``files_count`` or ``loc_estimate`` is negative
        (S-5 — explicit error rather than silent ``abs()`` coercion).

    Mapping (mirrors SKILL.md §"Quick Action Decision" rows verbatim):

      * ``files_count == 1`` AND ``loc_estimate < 20`` AND NOT
        ``is_cross_cutting`` → TRIVIAL
      * ``files_count <= 3`` AND NOT ``is_cross_cutting`` → SIMPLE
      * ``files_count <= 10`` OR ``is_cross_cutting`` → STANDARD
      * ``files_count > 10`` → COMPLEX
    """
    if files_count < 0:
        raise ValueError(f"classify_complexity: files_count must be >= 0, got {files_count!r}")
    if loc_estimate < 0:
        raise ValueError(f"classify_complexity: loc_estimate must be >= 0, got {loc_estimate!r}")

    # Cross-cutting forces STANDARD floor regardless of size.
    if is_cross_cutting:
        if files_count > _STANDARD_FILE_CEILING:
            return "COMPLEX"
        return "STANDARD"

    if files_count <= _TRIVIAL_FILE_CEILING and loc_estimate < _TRIVIAL_LOC_CEILING:
        return "TRIVIAL"
    if files_count <= _SIMPLE_FILE_CEILING:
        return "SIMPLE"
    if files_count <= _STANDARD_FILE_CEILING:
        return "STANDARD"
    return "COMPLEX"


def activation_verdict(
    complexity: Complexity,
    env_agent_workspace: bool,
    opt_out: bool = False,
    force_no_change: bool = False,
) -> ActivationVerdict:
    """Combine complexity + env-flag + opt-out + force into a three-valued verdict.

    Args:
      complexity: The :data:`Complexity` tier from
        :func:`classify_complexity` (or a verbatim literal).
      env_agent_workspace: ``True`` iff
        ``DEVOLAFLOW_AGENT_WORKSPACE=1`` is set (use :func:`from_env`
        for the canonical read site).
      opt_out: ``True`` iff the operator passed ``--no-change`` on
        ``/devola:propose`` (per A-6.3 the only slash-command opt-out).
      force_no_change: ``True`` iff the dispatcher explicitly forces
        the verdict to ``NO_CHANGE`` regardless of complexity / env /
        opt-out. v10.5.0 PV-03 D-A-4 dispatch-level override —
        orthogonal to ``opt_out`` (per the PDS §2 nest-vs-append
        decision rule the new flag NESTS into the existing argument
        list as a fourth axis rather than introducing a new env flag,
        respecting W-20 reuse-first). Default ``False`` preserves
        byte-identical v10.4.x behaviour for every existing call site.

    Returns:
      A :data:`ActivationVerdict` literal — one of
      ``"MUST_OPEN_CHANGE"``, ``"SHOULD_OPEN_CHANGE"``, ``"NO_CHANGE"``.

    Raises:
      ValueError: when ``complexity`` is not a recognised
        :data:`Complexity` literal (S-5 — never silently coerce).

    Verdict matrix (per A-6 + cycle plan §PV-02 + v10.5.0 PV-03):

      * force_no_change=True → NO_CHANGE (operator override wins;
        evaluated FIRST per A-6.3.1 sub-rule)
      * COMPLEX + env=True + opt_out=False → MUST_OPEN_CHANGE
      * STANDARD + env=True + opt_out=False → SHOULD_OPEN_CHANGE
      * SIMPLE / TRIVIAL → NO_CHANGE (regardless of env / opt_out)
      * env=False → NO_CHANGE (R5 strict default-OFF)
      * opt_out=True → NO_CHANGE (escape hatch wins)
    """
    if complexity not in _VALID_COMPLEXITIES:
        raise ValueError(
            f"activation_verdict: complexity {complexity!r} is not one of {_VALID_COMPLEXITIES}"
        )

    # v10.5.0 PV-03 D-A-4: explicit operator override evaluated BEFORE
    # complexity / env / opt-out so the "I know what I'm doing,
    # bypass scaffold for this dispatch only" path is unconditional.
    # Use case: ad-hoc exploratory analysis where the operator
    # deliberately skips the workspace audit trail (and accepts the
    # S-8 file-ownership consequence — see references/agent-workspace.md
    # §3.6 cross-references).
    if force_no_change:
        return "NO_CHANGE"

    if not env_agent_workspace:
        return "NO_CHANGE"
    if opt_out:
        return "NO_CHANGE"
    if complexity == "COMPLEX":
        return "MUST_OPEN_CHANGE"
    if complexity == "STANDARD":
        return "SHOULD_OPEN_CHANGE"
    return "NO_CHANGE"


def from_env(env: dict[str, str] | None = None) -> bool:
    """Single env-var read site for ``DEVOLAFLOW_AGENT_WORKSPACE``.

    Args:
      env: Optional environment mapping (defaults to :data:`os.environ`).
        Provided as a parameter so unit tests can pass a dict instead
        of monkeypatching the live process environment.

    Returns:
      ``True`` iff ``env[ENV_FLAG_NAME] == ENV_FLAG_TRUTHY`` exactly.
      Any other value (including the env-var being absent) returns
      ``False`` — R5 strict default-OFF.
    """
    source = env if env is not None else os.environ
    return source.get(ENV_FLAG_NAME) == ENV_FLAG_TRUTHY


def cascade_requirement(complexity: Complexity) -> CascadeRequirement:
    """STANDARD complexity or higher → cascade required (L0→L1 Wave→L2 Task); SIMPLE / TRIVIAL → cascade optional."""  # noqa: E501
    # v11.1.0 PV-02 (G-CLASSIFY-1 Candidate C — "Rule-based 4-tier collapse
    # with new sibling pure function"). Pure function of ``complexity`` —
    # no env-flag, no dispatcher state, no parameter beyond complexity.
    # Composes orthogonally with :func:`activation_verdict` (workspace
    # activation axis). Operators bypass cascade not via a flag here but
    # via the existing ``force_no_change`` parameter on
    # :func:`activation_verdict` (workspace-activation axis). Raises
    # ValueError on invalid complexity per S-5 (no silent coercion).
    # Verdict matrix:
    #   * COMPLEX  → CASCADE_REQUIRED
    #   * STANDARD → CASCADE_REQUIRED
    #   * SIMPLE   → CASCADE_OPTIONAL
    #   * TRIVIAL  → CASCADE_OPTIONAL
    # Source: ``.local/research/v11.1.0_pv02_decision.md`` §1.
    if complexity not in _VALID_COMPLEXITIES:
        raise ValueError(
            f"cascade_requirement: complexity {complexity!r} is not one of {_VALID_COMPLEXITIES}"
        )
    if complexity in ("STANDARD", "COMPLEX"):
        return "CASCADE_REQUIRED"
    return "CASCADE_OPTIONAL"


# v11.1.0 PV-05 — Architecture rule A-7 ("Cascade-Depth Invariant for
# Standard+ Dispatches") establishes ``cascade_requirement`` as the
# canonical complexity-to-cascade verdict surface. The function is now
# wired via the production call site in
# ``src/devolaflow/feedback.py::populate_cascade_gate_fields`` (line 564
# call ``cascade_requirement(complexity)``) so the dead-API detector sees
# a real ``ast.Call`` reference outside of any Import statement. The
# v11.1.0 PV-02 placeholder pin tuple
# ``_cascade_requirement_dead_api_pins`` was REMOVED in v11.0.5 PV-05
# per cycle plan §3 PV-05 W03 ("dead-API pin cleanup now that A-7 wires
# the symbols"). Source: ``.rules/architecture.mdc`` §A-7.
#
# v12.0.0 PV-03 D-2 — the v9.3.0 PV-06 ``SHORTCUT_SIMPLE`` /
# ``shortcut_verdict`` / ``shortcut_from_env`` / ``SHORTCUT_FLAG_NAME``
# / ``SHORTCUT_FLAG_TRUTHY`` / ``ShortcutVerdict`` surfaces were RETIRED
# entirely. The companion ``DEVOLAFLOW_SIMPLE_SHORTCUT`` env flag was
# removed from the inventory (env-flag count: 8 → 7; W-20 reuse-first
# preserved — no new flag introduced). Operators who relied on the
# v11.x shortcut path migrate to ``activation_verdict(...,
# force_no_change=True)`` per the v12.0.0 PV-03 retirement migration
# table. Source: ``.local/research/v12.0.0_gap_analysis.md`` §4 D-2 +
# ``docs/cycle-archive/v11.1.0/retrospective.md`` §3 D-2 telegraph.
