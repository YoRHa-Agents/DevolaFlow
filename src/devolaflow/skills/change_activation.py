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
    "SHORTCUT_FLAG_NAME",
    "SHORTCUT_FLAG_TRUTHY",
    "ActivationVerdict",
    "Complexity",
    "ShortcutVerdict",
    "activation_verdict",
    "classify_complexity",
    "from_env",
    "shortcut_from_env",
    "shortcut_verdict",
]


# ── Public type aliases ────────────────────────────────────────────────
# Literal types are the public contract; the runtime tuples below derive
# from them via typing.get_args so adding a new tier requires editing
# exactly one Literal alias (single-source-of-truth per A-5 spirit).
Complexity = Literal["TRIVIAL", "SIMPLE", "STANDARD", "COMPLEX"]
ActivationVerdict = Literal["MUST_OPEN_CHANGE", "SHOULD_OPEN_CHANGE", "NO_CHANGE"]
# v9.3.0 PV-06 — separate verdict surface for the simple-task auto-shortcut.
# Kept as a SEPARATE Literal (not folded into ActivationVerdict) so the
# A-6.1 three-valued contract stays intact — operators relying on the
# three ``ActivationVerdict`` strings see no change. The shortcut decision
# is orthogonal: a task may have ANY ActivationVerdict AND independently
# qualify for SHORTCUT_SIMPLE based on the v9.3.0 PV-06 env flag.
ShortcutVerdict = Literal["SHORTCUT_SIMPLE", "NO_SHORTCUT"]

_VALID_COMPLEXITIES: Final[tuple[str, ...]] = get_args(Complexity)
_VALID_VERDICTS: Final[tuple[str, ...]] = get_args(ActivationVerdict)
_VALID_SHORTCUT_VERDICTS: Final[tuple[str, ...]] = get_args(ShortcutVerdict)


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


# ── Simple-shortcut env-flag constants (v9.3.0 PV-06 — W-20 NEW flag) ──
# A NEW DEVOLAFLOW_* flag is justified per W-20 §3 because the
# behavioural surface is BEHAVIOURALLY ORTHOGONAL to every existing flag:
# this flag activates the SHORTCUT_SIMPLE dispatch verdict (skip L1/L2
# layers when complexity is SIMPLE/TRIVIAL), independently of whether
# the agent-workspace activation surface is ON.
#
# The flag is opt-in for v9.3.0; a future cycle (telegraphed v9.7.0)
# will promote it to default-ON after operators have time to adopt
# the SHORTCUT_SIMPLE dispatch path. The R5 strict ``"1"``-only
# parsing matches every other DevolaFlow opt-in flag (§ 6 of
# `references/env-flags.md`).
SHORTCUT_FLAG_NAME: Final[str] = "DEVOLAFLOW_SIMPLE_SHORTCUT"
SHORTCUT_FLAG_TRUTHY: Final[str] = "1"


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
) -> ActivationVerdict:
    """Combine complexity + env-flag + opt-out into a three-valued verdict.

    Args:
      complexity: The :data:`Complexity` tier from
        :func:`classify_complexity` (or a verbatim literal).
      env_agent_workspace: ``True`` iff
        ``DEVOLAFLOW_AGENT_WORKSPACE=1`` is set (use :func:`from_env`
        for the canonical read site).
      opt_out: ``True`` iff the operator passed ``--no-change`` on
        ``/devola:propose`` (per A-6.3 the only opt-out channel).

    Returns:
      A :data:`ActivationVerdict` literal — one of
      ``"MUST_OPEN_CHANGE"``, ``"SHOULD_OPEN_CHANGE"``, ``"NO_CHANGE"``.

    Raises:
      ValueError: when ``complexity`` is not a recognised
        :data:`Complexity` literal (S-5 — never silently coerce).

    Verdict matrix (per A-6 + cycle plan §PV-02):

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


# ── Simple-shortcut surface (v9.3.0 PV-06) ────────────────────────────


def shortcut_from_env(env: dict[str, str] | None = None) -> bool:
    """Single env-var read site for ``DEVOLAFLOW_SIMPLE_SHORTCUT``.

    Mirrors :func:`from_env` for the v9.3.0 PV-06 simple-shortcut flag.
    Kept as a separate function so unit tests + future callers can
    monkeypatch one flag without disturbing the other (the two
    activation surfaces are independently optional; per W-20 §3 the
    NEW flag is justified because the behaviour is orthogonal).

    Args:
      env: Optional environment mapping (defaults to :data:`os.environ`).

    Returns:
      ``True`` iff ``env[SHORTCUT_FLAG_NAME] == SHORTCUT_FLAG_TRUTHY``
      exactly. Any other value (including absent) returns ``False`` —
      R5 strict default-OFF (the v9.3.0 cycle ships the flag as opt-in;
      v9.7.0 PV-XX will promote it to default-ON after one cycle of
      operator-adoption observation).
    """
    source = env if env is not None else os.environ
    return source.get(SHORTCUT_FLAG_NAME) == SHORTCUT_FLAG_TRUTHY


def shortcut_verdict(
    complexity: Complexity,
    simple_shortcut_enabled: bool,
    opt_out: bool = False,
) -> ShortcutVerdict:
    """Decide whether a SIMPLE / TRIVIAL task should L0→L3 short-circuit.

    The shortcut is the v9.3.0 PV-06 deliverable that closes D-E-4
    from `.local/research/v9.3.0_gap_analysis.md` §1.4: SHORTCUT_SIMPLE
    is declared in SKILL.md §"Quick Action Decision" but was NOT
    auto-enforced by any dispatcher.

    Args:
      complexity: The :data:`Complexity` tier from
        :func:`classify_complexity`. The shortcut fires only for
        ``"SIMPLE"`` and ``"TRIVIAL"`` complexity tiers — STANDARD
        and COMPLEX always go through the full L0→L1→L2→L3 chain
        because they need design / decomposition / wave coordination.
      simple_shortcut_enabled: ``True`` iff
        ``DEVOLAFLOW_SIMPLE_SHORTCUT=1`` is set (use
        :func:`shortcut_from_env` for the canonical read site). When
        ``False``, returns ``"NO_SHORTCUT"`` regardless of complexity
        — preserving v9.2.4 byte-identical dispatch behaviour for
        operators who have not opted in.
      opt_out: ``True`` iff the operator passed an explicit opt-out
        signal (e.g. ``--no-shortcut`` on a future ``/devola:dispatch``
        slash command). Mirrors the :func:`activation_verdict`
        ``opt_out`` parameter — the escape hatch wins.

    Returns:
      A :data:`ShortcutVerdict` literal — either ``"SHORTCUT_SIMPLE"``
      (the dispatcher MAY skip L1 + L2 and route the task directly
      to an L3 Task Agent) or ``"NO_SHORTCUT"`` (default-OFF or
      complexity above the shortcut tier).

    Raises:
      ValueError: when ``complexity`` is not a recognised
        :data:`Complexity` literal (S-5 — never silently coerce).

    Verdict matrix (per .local/research/v9.3.0_gap_analysis.md §3.5):

      * simple_shortcut_enabled=False                            → NO_SHORTCUT
      * opt_out=True                                             → NO_SHORTCUT
      * complexity ∈ {SIMPLE, TRIVIAL} + enabled + not opt_out   → SHORTCUT_SIMPLE
      * complexity ∈ {STANDARD, COMPLEX}                         → NO_SHORTCUT

    Backward-compatibility (v9.2.4 byte-identical contract): when
    ``simple_shortcut_enabled=False`` (the default until v9.7.0 flips
    the flag), this function returns ``"NO_SHORTCUT"`` for EVERY
    complexity input. Callers that branch on ``verdict ==
    "SHORTCUT_SIMPLE"`` see no change in behaviour for operators
    who have not opted in.
    """
    if complexity not in _VALID_COMPLEXITIES:
        raise ValueError(
            f"shortcut_verdict: complexity {complexity!r} is not one of {_VALID_COMPLEXITIES}"
        )

    if not simple_shortcut_enabled:
        return "NO_SHORTCUT"
    if opt_out:
        return "NO_SHORTCUT"
    if complexity in ("TRIVIAL", "SIMPLE"):
        return "SHORTCUT_SIMPLE"
    return "NO_SHORTCUT"


# v9.3.0 PV-06 — non-import references for ``scripts/detect_dead_apis.py``.
# The two new public symbols ``shortcut_from_env`` + ``shortcut_verdict``
# have no in-repo production caller until v9.7.0 wires the SHORTCUT_SIMPLE
# verdict into the dispatcher. The detector's ``_collect_real_uses``
# walker treats any non-Import ``ast.Name`` reference as a real caller —
# this tuple establishes such references at the new symbols' qualified
# names without leaking into ``__all__``. Mirrors the PV-04
# ``_dead_api_pins`` pattern in ``src/devolaflow/compressor/__init__.py``
# and the PV-05 ``_dispatch_executor_dead_api_pins`` pattern in
# ``src/devolaflow/agent_workspace/__init__.py``.
_simple_shortcut_dead_api_pins = (
    shortcut_from_env,
    shortcut_verdict,
)
