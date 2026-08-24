"""Convergence round rule reinforcement — dispatch-level findings injection.

Converts gate findings into reinforcement rules for the next convergence
round's dispatch, enabling L3 Task Agents to receive explicit mandates
about what MUST be fixed.  Zero file I/O, platform-agnostic (Approach B).

v8.0.0 (P-04) — adds deterministic fence expansion via
:func:`fence_to_instruction`, mapping a single fence-check failure
(``lint``/``format``/``typecheck``/``test``/``build``) to a
:class:`ReinforcementRule` whose ``id`` is deterministic given a
``(fence_type, sequence)`` pair (e.g. ``F-lint-001``). See
``.local/research/v8.0.0_patch_plan.md §3 P-04``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from devolaflow.gate.models import CYCLE_DEFAULT_SEVERITY, CycleReport, Finding, Severity

SEVERITY_ORDER: dict[str, int] = {
    "blocker": 0,
    "critical": 1,
    "major": 2,
    "minor": 3,
    "info": 4,
}

MAX_REINFORCEMENT_RULES = 5

# v8.0.0 (P-04) — deterministic fence-to-instruction expansion.
#
# Supported fence types and their default severities. Lint / format are
# styled as ``major``; build / test / typecheck escalate to ``critical``
# because a broken build, failing test, or type error blocks downstream
# work entirely (Karpathy "strong success criteria" — verbatim oracle
# signals get higher severity than style nitpicks).
FENCE_DEFAULT_SEVERITY: dict[str, Severity] = {
    "lint": "major",
    "format": "major",
    "typecheck": "critical",
    "test": "critical",
    "build": "critical",
}

# Approximate chars-per-token used to honour ``fence_to_instruction``'s
# ``max_tokens`` budget without pulling in a tokenizer dependency. The
# 4 chars/token heuristic is the cl100k-base ballpark and is the same
# approximation used by ``schemas/lean-dispatch.yaml`` budget docs.
_CHARS_PER_TOKEN: int = 4

# The fence-derived rule id format. Stable across calls so the same
# ``(fence_type, sequence)`` pair always renders the same id (see
# ``patch_plan §3 P-04 AC #1``).
_FENCE_RULE_ID_FORMAT: str = "F-{fence_type}-{sequence:03d}"
_REVERT_RULE_ID_FORMAT: str = "R-{item_id}-{round_num:03d}"


@dataclass(frozen=True)
class ReinforcementRule:
    """A single mandate derived from a previous round's finding."""

    id: str
    severity: Severity
    mandate: str
    file: str = ""


@dataclass(frozen=True)
class ReinforcementBlock:
    """Reinforcement block to inject into dispatch ``applicable_rules``."""

    round: int
    prior_score: float
    target_score: float
    severity_floor: Severity
    rules: tuple[ReinforcementRule, ...] = ()
    escalation_note: str = ""


def findings_to_reinforcement(
    findings: list[Finding],
    round_num: int,
    prior_score: float,
    target_score: float,
    severity_floor: Severity = "major",
) -> ReinforcementBlock:
    """Convert gate findings into a dispatch reinforcement block.

    Filters by *severity_floor*, sorts by severity, caps at
    :data:`MAX_REINFORCEMENT_RULES`, and returns a :class:`ReinforcementBlock`.
    """
    floor_order = SEVERITY_ORDER.get(severity_floor, 2)
    eligible = [f for f in findings if SEVERITY_ORDER.get(f.severity, 4) <= floor_order]
    eligible.sort(key=lambda f: SEVERITY_ORDER.get(f.severity, 4))

    rules: list[ReinforcementRule] = []
    for f in eligible[:MAX_REINFORCEMENT_RULES]:
        mandate = f"MUST fix: {f.description}"
        if f.suggestion:
            mandate += f" — {f.suggestion}"
        rules.append(
            ReinforcementRule(
                id=f.finding_id,
                severity=f.severity,
                mandate=mandate,
                file=f.location,
            )
        )

    escalation = (
        f"Round {round_num - 1} score: {prior_score:.1f}/{target_score:.1f}. "
        f"{len(rules)} violation(s) from previous round MUST be addressed."
    )

    return ReinforcementBlock(
        round=round_num,
        prior_score=prior_score,
        target_score=target_score,
        severity_floor=severity_floor,
        rules=tuple(rules),
        escalation_note=escalation,
    )


def reverted_items_to_reinforcement(
    reverted_items: Sequence[Any],
    round_num: int,
    prior_score: float = 0.0,
    target_score: float = 0.0,
) -> ReinforcementBlock:
    """Convert open parser checklist reverts into blocker reinforcement.

    Reasons are copied verbatim into mandates per C-3. Source order is stable,
    ids include the checklist id and target round, and the existing top-five
    reinforcement cap applies unchanged.
    """

    if type(round_num) is not int or round_num < 1:
        raise ValueError(f"round_num must be a positive integer (got {round_num!r})")

    rules: list[ReinforcementRule] = []
    for item in reverted_items:
        reason = getattr(item, "reverted_reason", None)
        if getattr(item, "checked", False) or reason is None:
            continue
        item_id = getattr(item, "item_id", None)
        if not isinstance(item_id, str) or not item_id:
            raise TypeError("reverted checklist items must expose a non-empty item_id")
        if not isinstance(reason, str) or not reason:
            raise TypeError(
                f"reverted checklist item {item_id!r} must expose a non-empty reverted_reason"
            )
        rules.append(
            ReinforcementRule(
                id=_REVERT_RULE_ID_FORMAT.format(
                    item_id=item_id,
                    round_num=round_num,
                ),
                severity="blocker",
                mandate=reason,
            )
        )
        if len(rules) == MAX_REINFORCEMENT_RULES:
            break

    return ReinforcementBlock(
        round=round_num,
        prior_score=prior_score,
        target_score=target_score,
        severity_floor="blocker",
        rules=tuple(rules),
        escalation_note=(
            f"Round {round_num}: {len(rules)} user-reverted checklist item(s) "
            "MUST close blocker reinforcement before recheck."
        ),
    )


# Explicit public API pin until dispatch callers opt into round control.
_reverted_items_dead_api_pin = (reverted_items_to_reinforcement,)


def reinforcement_to_dict(block: ReinforcementBlock) -> dict[str, Any]:
    """Serialize a :class:`ReinforcementBlock` to a plain dict for YAML."""
    return {
        "round": block.round,
        "prior_score": block.prior_score,
        "target_score": block.target_score,
        "severity_floor": block.severity_floor,
        "rules": [
            {
                "id": r.id,
                "severity": r.severity,
                "mandate": r.mandate,
                **({"file": r.file} if r.file else {}),
            }
            for r in block.rules
        ],
        "escalation_note": block.escalation_note,
    }


def merge_reinforcement_into_dispatch(
    dispatch: dict[str, Any],
    reinforcement: ReinforcementBlock,
) -> dict[str, Any]:
    """Inject reinforcement into an existing dispatch's ``applicable_rules``.

    Mutates and returns *dispatch*.  Creates ``context`` /
    ``applicable_rules`` keys when absent.
    """
    context = dispatch.setdefault("context", {})
    rules = context.setdefault("applicable_rules", {})
    rules["reinforcement"] = reinforcement_to_dict(reinforcement)
    return dispatch


# ─────────────────────────────────────────────────────────────────────────────
# v8.0.0 (P-04) — Deterministic Fence Expansion
# ─────────────────────────────────────────────────────────────────────────────


def _truncate_to_token_budget(text: str, max_tokens: int) -> str:
    """Truncate ``text`` to roughly ``max_tokens`` tokens.

    Uses a 4-chars-per-token approximation to avoid a tokenizer dependency.
    When truncation is necessary, an ellipsis (``…``) replaces the trailing
    character so callers can detect the cut without a separate flag.
    Returns ``text`` unchanged when ``max_tokens <= 0`` (treat as unlimited)
    or when the budget is already met.
    """
    if max_tokens <= 0:
        return text
    char_budget = max_tokens * _CHARS_PER_TOKEN
    if len(text) <= char_budget:
        return text
    return text[: char_budget - 1] + "…"


def _coerce_fence_payload(fence_payload: object) -> dict[str, str]:
    """Normalise a fence payload into a flat ``{file, line, msg}`` mapping.

    Accepts either a plain string (treated as the ``msg`` field with no
    ``file``/``line``) or a mapping. Other types raise ``TypeError`` per
    S-5 (No Silent Failures). Missing keys default to empty strings so
    downstream rendering never crashes on partial payloads.
    """
    if isinstance(fence_payload, str):
        return {"file": "", "line": "", "msg": fence_payload}
    if isinstance(fence_payload, dict):
        return {
            "file": str(fence_payload.get("file", "")),
            "line": str(fence_payload.get("line", "")),
            "msg": str(fence_payload.get("msg", "")),
        }
    raise TypeError(
        f"fence_payload must be a str or dict (got {type(fence_payload).__name__}); "
        "expected keys: file, line, msg"
    )


def _format_fence_mandate(fence_type: str, payload: dict[str, str]) -> str:
    """Render the MUST-fix mandate string for a fence finding.

    Format mirrors ``patch_plan §3 P-04 AC #1`` — e.g.
    ``MUST fix lint error at src/foo.py:42: E501 line too long (123 > 79)``.
    Empty ``file``/``line`` segments are skipped so the mandate stays
    readable for fence types that lack location info (e.g. a global
    typecheck failure).
    """
    file_part = payload.get("file", "")
    line_part = payload.get("line", "")
    msg_part = payload.get("msg", "") or "(no details provided)"

    if file_part and line_part:
        location = f" at {file_part}:{line_part}"
    elif file_part:
        location = f" at {file_part}"
    else:
        location = ""

    return f"MUST fix {fence_type} error{location}: {msg_part}"


def fence_to_instruction(
    fence_type: str,
    fence_payload: object,
    *,
    sequence: int = 1,
    max_tokens: int = 200,
    severity: Severity | None = None,
) -> ReinforcementRule:
    """Map a single fence-check failure into a deterministic reinforcement rule.

    Parameters
    ----------
    fence_type:
        One of ``"lint"``, ``"format"``, ``"typecheck"``, ``"test"``,
        ``"build"``. Other values are accepted (returned verbatim in the
        rule id) but get a default ``"major"`` severity.
    fence_payload:
        Either a plain string (treated as ``msg``) or a mapping with
        ``file`` / ``line`` / ``msg`` keys. Anything else raises
        :class:`TypeError` per S-5.
    sequence:
        1-based ordinal that disambiguates multiple fences of the same
        type within a single round. Drives the deterministic id format
        ``F-{fence_type}-{sequence:03d}``.
    max_tokens:
        Soft ceiling on the rendered mandate string. Honoured via a
        4-chars-per-token approximation so this function stays
        tokenizer-free. Defaults to 200 (≈ 800 chars), matching the
        ``patch_plan §3 P-04`` budget recommendation.
    severity:
        Override for the fence's default severity. Defaults to
        :data:`FENCE_DEFAULT_SEVERITY` (or ``"major"`` for unknown types).

    Returns
    -------
    ReinforcementRule
        Carries the deterministic id, severity, MUST-fix mandate, and
        the originating ``file`` (when known). Pure function: same input
        ⇒ identical output.

    Raises
    ------
    ValueError
        If ``fence_type`` is empty or ``sequence`` is non-positive.
    TypeError
        If ``fence_payload`` is neither a string nor a mapping.
    """
    if not fence_type:
        raise ValueError("fence_type must be a non-empty string")
    if sequence < 1:
        raise ValueError(f"sequence must be >= 1 (got {sequence})")

    payload = _coerce_fence_payload(fence_payload)
    mandate = _truncate_to_token_budget(
        _format_fence_mandate(fence_type, payload),
        max_tokens=max_tokens,
    )
    resolved_severity: Severity = severity or FENCE_DEFAULT_SEVERITY.get(fence_type, "major")

    return ReinforcementRule(
        id=_FENCE_RULE_ID_FORMAT.format(fence_type=fence_type, sequence=sequence),
        severity=resolved_severity,
        mandate=mandate,
        file=payload.get("file", ""),
    )


# ─────────────────────────────────────────────────────────────────────────────
# v8.0.0 (P-06) — Cycle-to-instruction expansion
#
# Converts a :class:`devolaflow.gate.models.CycleReport` produced by
# :class:`devolaflow.gate.cycle_detector.CycleDetector` into a
# :class:`ReinforcementRule` whose ``mandate`` starts with the literal
# token ``MUST NOT repeat`` so L3 Task Agents recognise it as a hard
# prohibition for the next round (per ``patch_plan §3 P-06 AC #4``).
# ─────────────────────────────────────────────────────────────────────────────


# Deterministic id format for cycle-derived rules. Stable across calls so
# the same ``(cycle_type, sequence)`` pair always renders the same id —
# mirrors the ``F-{fence_type}-{sequence:03d}`` convention from P-04 to
# keep dispatch payloads diffable across rounds.
_CYCLE_RULE_ID_FORMAT: str = "C-{cycle_type}-{sequence:03d}"

# Maximum length of the file-list segment in the rendered mandate. Keeps
# the mandate readable when the cycle touches many files; longer lists
# get an ellipsis suffix so callers can detect truncation without a
# separate flag (mirrors :func:`_truncate_to_token_budget`).
_CYCLE_FILES_INLINE_LIMIT: int = 3


def _format_cycle_files(files: tuple[str, ...]) -> str:
    """Render the ``files`` tuple inline, truncating long lists with ``…``."""
    if not files:
        return ""
    visible = list(files[:_CYCLE_FILES_INLINE_LIMIT])
    if len(files) > _CYCLE_FILES_INLINE_LIMIT:
        visible.append(f"… (+{len(files) - _CYCLE_FILES_INLINE_LIMIT} more)")
    return ", ".join(visible)


def _format_cycle_mandate(report: CycleReport) -> str:
    """Render the ``MUST NOT repeat`` mandate string for a cycle finding.

    Format mirrors ``patch_plan §3 P-06 AC #4`` — e.g.::

        MUST NOT repeat exact_match cycle: signature='edit:a.py:add print'
        observed in rounds [3, 4]; vary the approach (different tool, file,
        or argument structure) before the next attempt.

    Empty / unknown segments are omitted so the mandate stays readable
    for cycle reports without file or rounds metadata (S-5 — never emit
    an empty mandate).
    """
    cycle_type = report.cycle_type
    repeated = (
        report.repeated_signatures[0] if report.repeated_signatures else "(no signature recorded)"
    )
    rounds_part = f" in rounds {list(report.rounds)}" if report.rounds else ""
    files_part = ""
    if report.files:
        files_part = f" touching {_format_cycle_files(report.files)}"
    similarity_part = ""
    if cycle_type == "fuzzy_match" and report.similarity:
        similarity_part = f" (Jaccard ≈ {report.similarity:.2f})"

    guidance = {
        "exact_match": (
            "vary the approach (different tool, file, or argument structure) "
            "before the next attempt"
        ),
        "fuzzy_match": (
            "stop iterating on near-duplicate edits; produce a structurally "
            "different change before the next attempt"
        ),
        "edit_oscillation": (
            "stop reverting between two states on the shared file(s); commit "
            "to a single direction backed by tests before the next attempt"
        ),
        "none": "no cycle observed (defensive mandate — caller error)",
    }.get(cycle_type, "vary the approach before the next attempt")

    return (
        f"MUST NOT repeat {cycle_type} cycle: signature={repeated!r}"
        f"{rounds_part}{files_part}{similarity_part}; {guidance}."
    )


def cycle_to_instruction(
    report: CycleReport,
    *,
    sequence: int = 1,
    max_tokens: int = 200,
    severity: Severity | None = None,
) -> ReinforcementRule:
    """Map a :class:`CycleReport` into a deterministic ``MUST NOT`` rule.

    Parameters
    ----------
    report:
        A :class:`CycleReport` produced by
        :meth:`devolaflow.gate.cycle_detector.CycleDetector.detect`.
        ``report.detected`` MUST be ``True`` — passing a no-cycle report
        raises :class:`ValueError` per S-5 (never silently emit a hard
        ``MUST NOT`` mandate without evidence).
    sequence:
        1-based ordinal that disambiguates multiple cycle rules within a
        single round. Drives the deterministic id format
        ``C-{cycle_type}-{sequence:03d}``.
    max_tokens:
        Soft ceiling on the rendered mandate string. Honoured via the
        same 4-chars-per-token approximation used by
        :func:`fence_to_instruction`. Defaults to 200 (≈ 800 chars).
    severity:
        Override for the cycle's default severity. Defaults to
        :data:`devolaflow.gate.models.CYCLE_DEFAULT_SEVERITY` when the
        report's severity is ``info`` (the no-cycle path); otherwise the
        report's own severity wins so detector-side escalations
        (e.g. ≥ 4 consecutive identical signatures → ``critical``)
        propagate verbatim.

    Returns
    -------
    ReinforcementRule
        Carries the deterministic id, severity ≥ ``major``, MUST-NOT
        mandate, and the first file path from the report (when known).
        Pure function: same input ⇒ identical output.

    Raises
    ------
    ValueError
        If ``report.detected`` is ``False`` or ``sequence`` is non-positive.
    TypeError
        If ``report`` is not a :class:`CycleReport`.
    """
    if not isinstance(report, CycleReport):
        raise TypeError(f"report must be a CycleReport (got {type(report).__name__})")
    if not report.detected:
        raise ValueError(
            "cycle_to_instruction requires a detected cycle "
            "(report.detected=False; nothing to forbid)"
        )
    if sequence < 1:
        raise ValueError(f"sequence must be >= 1 (got {sequence})")

    if severity is not None:
        resolved_severity: Severity = severity
    elif report.severity == CYCLE_DEFAULT_SEVERITY["none"]:
        resolved_severity = CYCLE_DEFAULT_SEVERITY.get(report.cycle_type, "major")
    else:
        resolved_severity = report.severity

    mandate = _truncate_to_token_budget(
        _format_cycle_mandate(report),
        max_tokens=max_tokens,
    )
    file_value = report.files[0] if report.files else ""

    return ReinforcementRule(
        id=_CYCLE_RULE_ID_FORMAT.format(
            cycle_type=report.cycle_type,
            sequence=sequence,
        ),
        severity=resolved_severity,
        mandate=mandate,
        file=file_value,
    )
