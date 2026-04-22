#!/usr/bin/env python3
"""Task-Adaptive Context Selector for DevolaFlow.

Given a task_type (from TaskDispatch), selects and assembles the relevant
SKILL.md sections according to the matching context profile. Uses priority-based
budget allocation: critical sections first, then important, then supplementary,
until the token budget is exhausted.

Based on: WP-4 Rank 4 (Task-Adaptive Context Selection via Goal-Hint Routing),
          SWE-Pruner goal hints, ATACompressor variable-rate allocation.
"""

from __future__ import annotations

import contextlib
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any

import yaml

from devolaflow.learnings import (
    format_learnings_section,
    load_relevant_learnings,
    resolve_learnings_path,
)

logger = logging.getLogger(__name__)

PROFILES_PATH = Path(__file__).parents[2] / "workflow-system" / "agent" / "context_profiles.yaml"

PRIORITY_ORDER = ["critical", "important", "supplementary"]

VALID_MODEL_HINTS = {"quality", "balanced", "budget", "inherit"}

VALID_COMPRESSION_INTENSITIES = {"minimal", "standard", "aggressive"}

_PLAN_MODE_ENV = "DEVOLAFLOW_PLAN_MODE"
_PLAN_MODE_MARKER = ".devolaflow_plan_mode"


def _detect_plan_mode() -> bool:
    """Detect plan-mode from environment or filesystem markers.

    Detection signals (in priority order):
      1. Env var ``DEVOLAFLOW_PLAN_MODE`` in {"1", "true", "yes", "on"}
      2. File ``.devolaflow_plan_mode`` exists in cwd

    Returns False on any other state (including unset, empty, or unknown
    string values like ``"garbage"``).
    """
    val = os.environ.get(_PLAN_MODE_ENV, "").strip().lower()
    if val in {"1", "true", "yes", "on"}:
        return True
    return (Path.cwd() / _PLAN_MODE_MARKER).exists()


_PLAN_MODE_OVERRIDES: dict[str, Any] = {
    "section_priority_overrides": {
        "agent_hierarchy": "critical",
        "decomposition_gate": "critical",
        "rationalization_prevention": "critical",
        "convergence_loop": "important",
        "execution_protocol": "supplementary",
    },
    "compression_intensity": "minimal",
    "model_hint_override": "quality",
}


def apply_plan_mode_overrides(profile: dict[str, Any]) -> dict[str, Any]:
    """Return a profile copy with plan-mode priority/model overrides applied.

    When plan-mode is active, the L0 Project Agent is designing an execution
    plan rather than executing. The assembled context therefore needs to
    emphasise the primitives that shape good plans (agent hierarchy,
    decomposition gate, rationalization prevention) and de-emphasise the
    runtime execution protocol.

    Does not mutate *profile*. Composes with :func:`apply_round_escalation`:
    plan-mode applies first, round-escalation may then override individual
    sections (e.g. round-3 lifts ``convergence_loop`` back to critical).
    """
    result = {**profile}

    prio_overrides = _PLAN_MODE_OVERRIDES["section_priority_overrides"]
    existing = dict(result.get("section_priorities", {}))
    existing.update(prio_overrides)
    result["section_priorities"] = existing

    result["model_hint"] = _PLAN_MODE_OVERRIDES["model_hint_override"]
    result["compression_intensity"] = _PLAN_MODE_OVERRIDES["compression_intensity"]
    return result


def resolve_decomposition_config(profile_config: dict[str, Any]) -> dict[str, Any]:
    """Resolve decomposition configuration from profile.

    Returns a dict with enabled, max_sub_agents, sub_agent_model_hint, etc.
    Defaults to disabled if not configured.
    """
    decomp = profile_config.get("decomposition", {})
    return {
        "enabled": decomp.get("enabled", False),
        "max_sub_agents": decomp.get("max_sub_agents", 4),
        "max_nesting_depth": decomp.get("max_nesting_depth", 1),
        "sub_agent_model_hint": decomp.get("sub_agent_model_hint", "budget"),
        "sub_agent_context_budget": decomp.get("sub_agent_context_budget", 3000),
        "coordinator_retains_advisor": decomp.get("coordinator_retains_advisor", True),
        "gen_verify_mode": decomp.get("gen_verify_mode", False),
        "gen_verify_max_rounds": decomp.get("gen_verify_max_rounds", 3),
    }


def resolve_compression_intensity(boundary: str, profiles_config: dict[str, Any]) -> str:
    """Resolve compression intensity for a given layer boundary.

    boundary: one of l0_to_l1, l1_to_l2, l2_to_l3, l3_to_l2, l2_to_l1, l1_to_l0
    """
    defaults = profiles_config.get("meta", {}).get("compression_defaults", {})
    intensity = defaults.get(boundary, "standard")
    return intensity if intensity in VALID_COMPRESSION_INTENSITIES else "standard"


def resolve_model_hint(
    task_type: str,
    profile_config: dict[str, Any],
    complexity_tier: str | None = None,
) -> str:
    """Resolve the model_hint for a given task type from the profile config.

    Lookup priority (v7.2.1+ P-04):
      1. ``complexity_routing[complexity_tier]`` — when *complexity_tier* is
         provided AND a mapping exists in
         ``profile_config["complexity_routing"]`` AND the resolved tier is in
         :data:`VALID_MODEL_HINTS`. The complexity-tier lookup table lives
         under top-level ``meta.complexity_routing`` in
         ``context_profiles.yaml``; :func:`select_context` injects it into the
         per-profile dict via copy-on-write before calling this function.
      2. ``model_hints.overrides[task_type]`` — per-task override.
      3. ``model_hints.default_tier`` — profile default.
      4. ``"inherit"`` — terminal fallback.

    Default ``complexity_tier=None`` preserves the v7.1.0 lookup priority
    bytewise (the new branch is skipped entirely), so the 2-arg signature
    ``resolve_model_hint(task_type, profile_config)`` remains valid for
    every existing caller and test.
    """
    if complexity_tier is not None:
        complexity_routing = profile_config.get("complexity_routing", {})
        if complexity_tier in complexity_routing:
            tier_hint = complexity_routing[complexity_tier]
            if tier_hint in VALID_MODEL_HINTS:
                return tier_hint

    model_hints = profile_config.get("model_hints", {})
    overrides = model_hints.get("overrides", {})

    if task_type in overrides:
        hint = overrides[task_type]
        if hint in VALID_MODEL_HINTS:
            return hint

    default = model_hints.get("default_tier", "inherit")
    return default if default in VALID_MODEL_HINTS else "inherit"


def load_profiles(path: Path | None = None) -> dict[str, Any]:
    """Load context profiles from a YAML configuration file."""
    p = path or PROFILES_PATH
    with open(p) as f:
        return yaml.safe_load(f)


def load_skill_md(config: dict[str, Any]) -> str:
    """Load the SKILL.md file contents as a string."""
    skill_path = Path(__file__).parents[2] / "workflow-system" / "agent" / "SKILL.md"
    if not skill_path.exists():
        repo_root = Path(__file__).parents[2]
        candidates = list(repo_root.rglob("SKILL.md"))
        if candidates:
            skill_path = candidates[0]
        else:
            raise FileNotFoundError(f"SKILL.md not found relative to {repo_root}")
    return skill_path.read_text()


_LINE_RANGE_RE = re.compile(r"^\d+-\d+$")


def extract_section(full_text: str, line_range: str) -> str:
    """Extract lines from full_text given a range like '57-68'."""
    if not line_range or not _LINE_RANGE_RE.match(line_range):
        return ""
    lines = full_text.splitlines()
    start, end = map(int, line_range.split("-"))
    return "\n".join(lines[start - 1 : end])


def estimate_tokens(text: str) -> int:
    """Estimate token count. Uses tiktoken if available, otherwise ~4 chars/token."""
    try:
        import tiktoken

        enc = tiktoken.encoding_for_model("gpt-4o")
        return len(enc.encode(text))
    except (ImportError, Exception):
        return max(1, len(text) // 4)


def match_profile(task_type: str, profiles_config: dict[str, Any]) -> str:
    """Match a task_type string to the best profile name.

    Ranking: exact key match > exact hint match > best substring match
    (longest overlap wins to avoid short hints stealing specific tasks).
    """
    profiles = profiles_config.get("profiles", {})

    if task_type in profiles:
        return task_type

    task_lower = task_type.lower()

    best_match: str | None = None
    best_score = 0

    for profile_name, profile in profiles.items():
        hints = profile.get("goal_hints", [])
        for hint in hints:
            hint_lower = hint.lower()
            if hint_lower == task_lower:
                return profile_name
            if hint_lower in task_lower:
                score = len(hint_lower)
                if score > best_score:
                    best_score = score
                    best_match = profile_name
            elif task_lower in hint_lower:
                score = len(task_lower)
                if score > best_score:
                    best_score = score
                    best_match = profile_name

    return best_match or profiles_config.get("meta", {}).get("default_profile", "feature")


def _resolve_advisor_text(profile: dict[str, Any]) -> tuple[bool, str, int]:
    """Build advisor section text and compute its token reserve.

    v7.2.0 PR-D note: dispatch and candidate-list refer to this helper as
    `_build_advisor_section`; the actual symbol is `_resolve_advisor_text`.
    The helper is the single emitter for the "## Advisor Tool" block consumed
    by all 4 advisor-enabled profiles (feature, refactor, migration,
    security-audit). One change here covers all 4.
    """
    advisor_config = profile.get("advisor", {})
    if not advisor_config.get("enabled", False):
        return False, "", 0

    max_uses = advisor_config.get("max_uses", 3)
    cost_ceiling = advisor_config.get("cost_ceiling_usd", 0.30)
    triggers = advisor_config.get("trigger_conditions", [])
    triggers_str = ", ".join(triggers) if triggers else "none"
    parts = [
        "## Advisor Tool",
        f"Advisor enabled (max {max_uses} uses, budget ${cost_ceiling}).",
        f"Invoke for: {triggers_str}.",
    ]
    if advisor_config.get("conciseness_instruction", True):
        parts.append(
            'When invoking advisor, append: "Reply in under 100 words and use '
            'enumerated steps, not explanations."'
        )
    if advisor_config.get("timing_block", True):
        parts.append(
            "Timing: Call advisor BEFORE substantive work. On tasks longer than "
            "a few steps, call advisor at least once before committing to an "
            "approach and once before declaring done."
        )
    if advisor_config.get("reconcile_block", True):
        parts.append(
            "On conflict: If you've already retrieved data pointing one way and "
            "the advisor points another, do not silently switch. Surface the "
            'conflict in one more advisor call: "I found X, you suggest Y, '
            'which constraint breaks the tie?".'
        )
    text = "\n".join(parts)
    return True, text, estimate_tokens(text)


def _compute_learnings_reserve(
    learnings_config: dict[str, Any],
    profiles_path: Path | None,
    budget: int,
) -> int:
    """Compute the token reservation for operational learnings."""
    if not learnings_config.get("enabled", False):
        return 0
    learnings_path = resolve_learnings_path()
    if not learnings_path.exists() or learnings_path.stat().st_size == 0:
        return 0
    budget_max_tokens = learnings_config.get("budget_max_tokens", 500)
    budget_pct = learnings_config.get("budget_pct", 10)
    return min(budget_max_tokens, int(budget * budget_pct / 100))


def _build_priority_buckets(
    section_priorities: dict[str, str],
) -> tuple[dict[str, list[str]], list[str]]:
    """Sort section names into priority buckets and a skip list."""
    buckets: dict[str, list[str]] = {p: [] for p in PRIORITY_ORDER}
    skipped: list[str] = []
    for section_name, priority in section_priorities.items():
        if priority == "skip":
            skipped.append(section_name)
        elif priority in buckets:
            buckets[priority].append(section_name)
    return buckets, skipped


def _select_sections_by_priority(
    priority_buckets: dict[str, list[str]],
    directive: dict | None = None,
) -> list[str]:
    """Flatten ``priority_buckets`` into a single ordered list of section names.

    Walks the canonical :data:`PRIORITY_ORDER` (``critical → important →
    supplementary``) and emits each bucket's contents in the order recorded
    by :func:`_build_priority_buckets`. When ``directive`` is provided AND
    its ``focus_section_names`` set is non-empty, sections in that set are
    promoted to the front of their priority tier (preserving the cross-tier
    ranking — focused critical still beats focused important). Default
    ``directive=None`` preserves byte-stable v7.x ordering.

    v8.0.0 (P-02) — companion to the ``compressor._select_sections_by_priority``
    section-text overlay: this helper performs the SAME directed-compaction
    promotion at the SKILL-section-name layer so both Layer-2 (section
    ranker) and Layer-3 (text compactor) honour the same directive shape.
    The helper is intentionally additive — :func:`_select_sections_within_budget`
    accepts ``directive=None`` by default so every existing caller is
    untouched.
    """
    focus = set((directive or {}).get("focus_section_names", []) or [])
    ordered: list[str] = []
    for priority in PRIORITY_ORDER:
        bucket = priority_buckets.get(priority, [])
        if focus:
            focused_in_bucket = [s for s in bucket if s in focus]
            other_in_bucket = [s for s in bucket if s not in focus]
            ordered.extend(focused_in_bucket)
            ordered.extend(other_in_bucket)
        else:
            ordered.extend(bucket)
    return ordered


def _select_sections_within_budget(
    priority_buckets: dict[str, list[str]],
    sections_registry: dict[str, Any],
    skill_text: str,
    section_budget: int,
    verbose: bool,
    directive: dict | None = None,
) -> tuple[list[tuple[str, str, int]], list[str], int]:
    """Pick sections in priority order until the token budget is exhausted.

    v8.0.0 (P-02) — accepts an optional ``directive`` dict that is forwarded
    to :func:`_select_sections_by_priority` so directed-compaction overlays
    can promote focus sections within each priority tier. Default
    ``directive=None`` preserves byte-stable v7.x behaviour for every
    existing caller (verified by :class:`tests.test_compressor.
    TestSelectorDirectiveBackwardCompat`).
    """
    selected: list[tuple[str, str, int]] = []
    overflow: list[str] = []
    used_tokens = 0

    for section_name in _select_sections_by_priority(priority_buckets, directive):
        if section_name not in sections_registry:
            continue
        sec_info = sections_registry[section_name]
        line_range = sec_info.get("lines", "")
        if not line_range or not _LINE_RANGE_RE.match(line_range):
            continue

        text = extract_section(skill_text, line_range)
        tok = estimate_tokens(text)

        if used_tokens + tok <= section_budget:
            selected.append((section_name, text, tok))
            used_tokens += tok
        else:
            overflow.append(section_name)
            if verbose:
                print(
                    f"  [SKIP] {section_name} ({tok} tok) — "
                    f"would exceed budget ({used_tokens}+{tok} > {section_budget})"
                )

    return selected, overflow, used_tokens


def _integrate_learnings(
    learnings_config: dict[str, Any],
    profile_name: str,
    profiles_path: Path | None,
    learnings_reserve: int,
) -> str:
    """Load and format operational learnings, returning the text (or empty)."""
    if not learnings_config.get("enabled", False):
        return ""
    learnings_path = resolve_learnings_path()
    if not learnings_path.exists():
        return ""

    max_entries = learnings_config.get("max_entries", 5)
    min_confidence = learnings_config.get("min_confidence", 0.5)
    try:
        relevant = load_relevant_learnings(
            task_type=profile_name,
            jsonl_path=learnings_path,
            min_confidence=min_confidence,
            max_entries=max_entries,
        )
        if not relevant:
            return ""
        return format_learnings_section(relevant, max_tokens=learnings_reserve)
    except Exception:
        logger.debug("Learnings integration skipped due to error", exc_info=True)
        return ""


# ---------------------------------------------------------------------------
# v8.0.0 (P-08) — L3 behavioral guideline injection.
#
# Behavioral guidelines are 4 Karpathy-derived primitives (think_first,
# simplicity_check, surgical_scope, goal_loop) documented in
# ``workflow-system/agent/references/behavioral-guidelines.md`` and
# expressed in the dispatch payload via the top-level
# ``behavioral_guidelines`` field (canonical_order position 14, schema
# version 3 — added by P-08, P6 additive). The two helpers below resolve
# per-profile defaults and render the injectable text block. They are
# extracted from ``select_context`` so the parent function's cyclomatic
# complexity stays ≤ 8 (NineS finding ``[CC-448821-0000]`` closure).
#
# Backward compatibility: when a profile omits ``behavioral_guidelines``
# AND ``meta.behavioral_guidelines_defaults`` is unset, both helpers
# short-circuit to None / "" so the dispatch payload remains
# byte-identical to the v7.x output (preserves the v7.0.0 layout
# baseline byte-comparison; verified by
# ``tests/test_behavioral_guidelines.py::TestBackwardCompat``).
#
# v8.2.0 (PV-04) — surgical_scope='line' completion. Closes the deferred
# AC #2 from v8.0.0 P-08 (line-tier verification). When the resolved
# behavioral block carries ``surgical_scope='line'``,
# :func:`_load_line_level_criteria` extracts the line-diff validation
# rules from ``references/behavioral-guidelines.md#line-level-behavioral-criteria``
# verbatim (per CO-2 / C-3) and the helper appends them under
# ``line_level_criteria`` in the returned dict.
# ``surgical_scope='function'`` and ``surgical_scope='module'`` paths
# remain byte-identical to v8.0.0-p08 (R5 backward-compat discipline,
# verified by ``tests/test_behavioral_guidelines.py
# ::TestSurgicalScopeLine::test_function_scope_byte_identical_to_p08``).
# ---------------------------------------------------------------------------


_BEHAVIORAL_REF_PATH: Path = (
    Path(__file__).parents[2]
    / "workflow-system"
    / "agent"
    / "references"
    / "behavioral-guidelines.md"
)
_LINE_LEVEL_HEADING = "## Line-Level Behavioral Criteria"
_LINE_LEVEL_BULLET_RE = re.compile(r"^[-*]\s+(.*\S)\s*$")


def _load_line_level_criteria(ref_path: Path | None = None) -> list[str]:
    """Extract line-level behavioural criteria verbatim from the reference doc.

    Walks ``references/behavioral-guidelines.md`` for the canonical
    ``## Line-Level Behavioral Criteria`` heading (added in v8.2.0 PV-04)
    and returns each ``- ...`` bullet from that section as a list of
    strings. Returns ``[]`` when:
      * ``ref_path`` does not exist (S-5 — explicit empty signal, never
        a silent exception),
      * the heading is absent (older reference docs predating PV-04),
      * the section is empty.

    Per CO-2 / C-3 (verbatim extraction), each bullet's text is preserved
    as-written in the markdown — no paraphrasing, normalisation, or
    re-ordering. Continuation lines (indented under a bullet, common for
    line-wrapped markdown) are joined into the parent bullet with a
    single space so the returned list carries each criterion's full
    prose. Nested bullets (lines that themselves start with ``- ``
    after indentation) terminate the parent bullet and start a fresh
    entry — matches Markdown rendering semantics.

    The default ``ref_path=None`` resolves the path relative to the
    DevolaFlow checkout root so callers in tests / scripts inherit the
    canonical reference doc without wiring boilerplate.
    """
    path = ref_path if ref_path is not None else _BEHAVIORAL_REF_PATH
    if not path.exists():
        return []

    text = path.read_text(encoding="utf-8")
    if _LINE_LEVEL_HEADING not in text:
        return []

    after = text.split(_LINE_LEVEL_HEADING, 1)[1]
    next_heading_match = re.search(r"^## ", after, flags=re.MULTILINE)
    section_body = after[: next_heading_match.start()] if next_heading_match else after

    criteria: list[str] = []
    current: list[str] | None = None
    for raw in section_body.splitlines():
        stripped = raw.strip()
        if not stripped:
            if current is not None:
                criteria.append(" ".join(current))
                current = None
            continue
        match = _LINE_LEVEL_BULLET_RE.match(raw)
        if match and not raw.startswith((" ", "\t")):
            if current is not None:
                criteria.append(" ".join(current))
            current = [match.group(1)]
        elif current is not None and raw.startswith((" ", "\t")):
            continuation = stripped
            if continuation.startswith(("- ", "* ")):
                continuation = continuation[2:]
            current.append(continuation)
        else:
            if current is not None:
                criteria.append(" ".join(current))
                current = None
    if current is not None:
        criteria.append(" ".join(current))
    return criteria


def _select_behavioral_sections(
    profile: dict[str, Any],
    profiles_config: dict[str, Any],
) -> dict[str, Any] | None:
    """Resolve the L3 behavioral_guidelines for ``profile``.

    Lookup order:
      1. ``profile["behavioral_guidelines"]`` — explicit per-profile block.
      2. ``meta.behavioral_guidelines_defaults[profile_block.tier]`` —
         tier-default fallback when the per-profile block sets ``tier``.
      3. Per-profile explicit keys (think_first, simplicity_check,
         surgical_scope, goal_loop) override tier defaults on a per-key
         basis (so a profile MAY inherit standard tier yet override
         ``goal_loop=true`` for one specific profile).

    Returns the merged 4-key dict, or ``None`` when the profile omits
    the block AND no tier fallback is available — preserves v7.x
    byte-identical dispatch shape for backward compatibility.

    v8.2.0 (PV-04): when the resolved block sets ``surgical_scope='line'``,
    augments the returned dict with ``line_level_criteria`` (a list of
    strings extracted verbatim from
    ``references/behavioral-guidelines.md#line-level-behavioral-criteria``).
    Other ``surgical_scope`` values produce output byte-identical to
    v8.0.0-p08 (R5 discipline) so existing function/module dispatchers
    are unaffected.
    """
    profile_block = profile.get("behavioral_guidelines")
    if profile_block is None:
        return None
    if not isinstance(profile_block, dict):
        return None

    defaults = profiles_config.get("meta", {}).get("behavioral_guidelines_defaults", {})
    tier = profile_block.get("tier")
    base: dict[str, Any] = dict(defaults.get(tier, {})) if tier else {}
    base.update({k: v for k, v in profile_block.items() if k != "tier"})
    if not base:
        return None

    if base.get("surgical_scope") == "line":
        criteria = _load_line_level_criteria()
        if criteria:
            base["line_level_criteria"] = criteria

    return base


def _compose_behavioral_block(behavioral_guidelines: dict[str, Any] | None) -> str:
    """Render the active behavioral guidelines into an injectable text block.

    The block is a compact ``## Behavioral Guidelines (L3 active)`` markdown
    section with one bullet per active rule. Inactive rules (those with a
    falsy flag) are NOT rendered so the token cost scales with the number
    of active rules. ``surgical_scope`` is always rendered (str field with
    no opt-out) when the block is non-None.

    The full rule prose lives in
    ``workflow-system/agent/references/behavioral-guidelines.md`` (Tier 3
    on-demand reference, loaded only when this block surfaces). This helper
    emits a 5-line summary block (~ 30-100 tokens depending on active
    rules) intended for verbatim injection into the L3 dispatch context.

    v8.2.0 (PV-04): when ``surgical_scope='line'`` AND
    ``line_level_criteria`` is present, each criterion is rendered as an
    indented sub-bullet under BG-003 so the L3 task agent sees the
    line-diff validation rules verbatim. ``surgical_scope='function'`` /
    ``'module'`` paths emit output byte-identical to v8.0.0-p08
    (R5 backward-compat discipline).

    Returns "" when ``behavioral_guidelines`` is None or empty so callers
    can ``if block:`` without a None-check.
    """
    if not behavioral_guidelines:
        return ""

    lines = ["## Behavioral Guidelines (L3 active)"]
    if behavioral_guidelines.get("think_first"):
        lines.append("- BG-001 think_first ENABLED — emit numbered plan before any source edit.")
    if behavioral_guidelines.get("simplicity_check"):
        lines.append(
            "- BG-002 simplicity_check ENABLED — audit 3 over-engineering smells before commit."
        )
    scope = behavioral_guidelines.get("surgical_scope", "function")
    lines.append(f"- BG-003 surgical_scope = {scope!r} — diff hunks MUST stay within this tier.")
    if scope == "line":
        for criterion in behavioral_guidelines.get("line_level_criteria") or []:
            lines.append(f"  - {criterion}")
    if behavioral_guidelines.get("goal_loop"):
        lines.append("- BG-004 goal_loop ENABLED — restate user goal verbatim at round start.")
    return "\n".join(lines)


def _resolve_active_profile(
    config: dict[str, Any],
    task_type: str,
    plan_mode: bool | None,
    round_num: int,
    escalation_config: dict[int, dict[str, Any]] | None,
) -> tuple[str, dict[str, Any], bool]:
    """Match ``task_type`` to a profile and apply plan-mode + round overrides.

    Extracted from the legacy ``select_context`` body in v8.0.0 (P-08) to
    bring the parent function's cyclomatic complexity from 16 down to ≤ 8
    (NineS finding ``[CC-448821-0000]``). Returns
    ``(profile_name, resolved_profile, active_plan_mode)``.

    Plan-mode is auto-detected via :func:`_detect_plan_mode` when *plan_mode*
    is ``None``; pass ``plan_mode=False`` to disable detection. Round-based
    escalation runs AFTER plan-mode overrides so round overrides may layer
    on top (matches the v7.x ordering preserved across the refactor).
    """
    profile_name = match_profile(task_type, config)
    profile = config["profiles"][profile_name]

    active_plan_mode = plan_mode if plan_mode is not None else _detect_plan_mode()
    if active_plan_mode:
        profile = apply_plan_mode_overrides(profile)

    if round_num > 1:
        profile = apply_round_escalation(profile, round_num, escalation_config)

    meta_complexity_routing = config.get("meta", {}).get("complexity_routing", {})
    if meta_complexity_routing:
        profile = {**profile, "complexity_routing": meta_complexity_routing}

    return profile_name, profile, active_plan_mode


def _resolve_dispatch_overrides(
    profile: dict[str, Any],
    task_type: str,
    complexity_tier: str | None,
    config: dict[str, Any],
    profile_overrides_applied: bool,
) -> tuple[str, str]:
    """Compute ``(model_hint, compression_intensity)`` honouring overrides.

    Extracted from the legacy ``select_context`` body in v8.0.0 (P-08).
    When *profile_overrides_applied* is True (plan-mode active OR round
    escalation applied) and the profile carries explicit ``model_hint`` /
    ``compression_intensity`` keys, those keys win. Otherwise the helpers
    :func:`resolve_model_hint` and :func:`resolve_compression_intensity`
    apply the per-task / per-boundary defaults.

    Behaviour is byte-identical to the inlined v7.x logic (verified by
    ``tests.test_task_adaptive_selector.TestSelectContext::test_result_structure``).
    """
    model_hint: str | None = None
    if profile_overrides_applied and "model_hint" in profile:
        model_hint = profile["model_hint"]
    if not model_hint:
        model_hint = resolve_model_hint(task_type, profile, complexity_tier)

    if profile_overrides_applied and "compression_intensity" in profile:
        compression_intensity = profile["compression_intensity"]
    else:
        compression_intensity = resolve_compression_intensity("l2_to_l3", config)

    return model_hint, compression_intensity


def _append_optional_blocks(
    base_text: str,
    base_tokens: int,
    blocks: list[tuple[str, int]],
) -> tuple[str, int]:
    """Append non-empty blocks to ``base_text`` and accumulate token costs.

    Each block is a ``(text, token_cost)`` tuple. Empty / falsy text
    blocks are skipped (their token cost is NOT added). Non-empty blocks
    are concatenated with a ``\\n\\n`` separator and their costs are
    summed into ``base_tokens``. Returns ``(merged_text, total_tokens)``.

    Extracted from the legacy ``select_context`` body in v8.0.0 (P-08) so
    the parent's cc stays ≤ 8 even after the new behavioral_guidelines
    block is added. The ordering of *blocks* is preserved verbatim so
    callers control concatenation order (matches v7.x: learnings then
    advisor; v8.0.0 appends behavioral_guidelines as the final block).
    """
    text = base_text
    tokens = base_tokens
    for block_text, block_cost in blocks:
        if not block_text:
            continue
        text = (text + "\n\n" + block_text) if text else block_text
        tokens += block_cost
    return text, tokens


def select_context(
    task_type: str,
    profiles_path: Path | None = None,
    verbose: bool = False,
    round_num: int = 1,
    escalation_config: dict[int, dict[str, Any]] | None = None,
    plan_mode: bool | None = None,
    complexity_tier: str | None = None,
) -> dict[str, Any]:
    """Select context sections for a given task type.

    Returns a dict with:
      - profile_name: matched profile
      - selected_sections: ordered list of (section_name, text, tokens)
      - total_tokens: sum of selected section tokens
      - budget: token budget for this profile
      - skipped_sections: sections that didn't fit or were deprioritized
      - extra_context: additional reference files to load
      - round_num: convergence round number (1 = initial, 2+ = escalated)
      - escalation_applied: whether round-based escalation was applied
      - plan_mode: whether plan-mode is active (resolved from param or
        :func:`_detect_plan_mode` when *plan_mode* is ``None``)
      - plan_mode_applied: alias of ``plan_mode`` for explicit downstream
        checks; True when :func:`apply_plan_mode_overrides` was applied
      - behavioral_guidelines (v8.0.0 P-08): resolved 4-key dict (think_first,
        simplicity_check, surgical_scope, goal_loop) when the profile
        carries the block, otherwise ``None`` (preserves v7.x byte-stable
        dispatch shape for backward compatibility)

    When ``round_num > 1`` the resolved profile is routed through
    :func:`apply_round_escalation` so convergence rounds receive stricter
    section priorities and larger token budgets.  Pass ``escalation_config``
    to override the defaults defined in ``_ROUND_ESCALATION_DEFAULTS``.

    When *plan_mode* is True (or auto-detected via env var/marker file when
    ``plan_mode is None``) :func:`apply_plan_mode_overrides` runs *before*
    round-based escalation so plan-relevant primitives are escalated first
    and round overrides may then layer on top (e.g. round-3 still lifts
    ``convergence_loop`` to critical and bumps the budget by 20%).
    Pass ``plan_mode=False`` to disable detection entirely.

    When *complexity_tier* is provided (one of the keys in
    ``meta.complexity_routing`` — typically ``"simple" | "medium" | "complex"
    | "very_complex"``) the corresponding model hint takes priority over
    the per-profile ``model_hints.overrides`` and ``default_tier``. Default
    ``complexity_tier=None`` preserves the v7.1.0 routing priority bytewise.
    See :func:`resolve_model_hint` for the full lookup priority.

    v8.0.0 (P-08) refactor: the parent function delegates plan-mode +
    round + complexity-routing resolution to :func:`_resolve_active_profile`,
    behavioral guideline resolution to :func:`_select_behavioral_sections`
    + :func:`_compose_behavioral_block`, optional-block concatenation to
    :func:`_append_optional_blocks`, and override resolution to
    :func:`_resolve_dispatch_overrides`. This brings the cyclomatic
    complexity from 16 (NineS finding ``[CC-448821-0000]``) down to ≤ 8.
    The dispatch-payload contract is preserved bytewise for the v7.x
    return key set; the new ``behavioral_guidelines`` key is purely
    additive (``None`` when the profile omits the block).
    """
    config = load_profiles(profiles_path)
    skill_text = load_skill_md(config)
    sections_registry = config.get("sections", {})

    profile_name, profile, active_plan_mode = _resolve_active_profile(
        config, task_type, plan_mode, round_num, escalation_config
    )
    budget = profile.get("token_budget", 6000)

    advisor_enabled, advisor_text, advisor_reserve = _resolve_advisor_text(profile)
    learnings_config = profile.get("learnings", {})
    learnings_reserve = _compute_learnings_reserve(learnings_config, profiles_path, budget)

    behavioral_guidelines = _select_behavioral_sections(profile, config)
    behavioral_text = _compose_behavioral_block(behavioral_guidelines)
    behavioral_reserve = estimate_tokens(behavioral_text) if behavioral_text else 0

    section_budget = budget - advisor_reserve - learnings_reserve - behavioral_reserve

    priority_buckets, skipped = _build_priority_buckets(profile.get("section_priorities", {}))
    selected, overflow_skipped, used_tokens = _select_sections_within_budget(
        priority_buckets,
        sections_registry,
        skill_text,
        section_budget,
        verbose,
    )
    skipped.extend(overflow_skipped)

    base_text = "\n\n".join(text for _, text, _ in selected)
    learnings_text = _integrate_learnings(
        learnings_config, profile_name, profiles_path, learnings_reserve
    )
    learnings_cost = estimate_tokens(learnings_text) if learnings_text else 0
    assembled_text, used_tokens = _append_optional_blocks(
        base_text,
        used_tokens,
        [
            (learnings_text, learnings_cost),
            (advisor_text, advisor_reserve),
            (behavioral_text, behavioral_reserve),
        ],
    )

    escalation_applied = round_num > 1
    profile_overrides_applied = escalation_applied or active_plan_mode
    model_hint, compression_intensity = _resolve_dispatch_overrides(
        profile, task_type, complexity_tier, config, profile_overrides_applied
    )

    return {
        "profile_name": profile_name,
        "description": profile.get("description", ""),
        "selected_sections": [{"name": name, "tokens": tok} for name, _, tok in selected],
        "assembled_text": assembled_text,
        "total_tokens": used_tokens,
        "budget": budget,
        "utilization_pct": round(used_tokens / budget * 100, 1) if budget > 0 else 0,
        "skipped_sections": skipped,
        "extra_context": profile.get("extra_context", []),
        "rationale": profile.get("rationale", "").strip(),
        "learnings_included": bool(learnings_text),
        "model_hint": model_hint,
        "advisor_enabled": advisor_enabled,
        "decomposition": resolve_decomposition_config(profile),
        "compression_intensity": compression_intensity,
        "round_num": round_num,
        "escalation_applied": escalation_applied,
        "plan_mode": active_plan_mode,
        "plan_mode_applied": active_plan_mode,
        "behavioral_guidelines": behavioral_guidelines,
    }


_ROUND_ESCALATION_DEFAULTS: dict[int, dict[str, Any]] = {
    2: {
        "section_priority_overrides": {
            "rationalization_prevention": "critical",
            "convergence_loop": "critical",
        },
        "compression_intensity": "minimal",
    },
    3: {
        "section_priority_overrides": {
            "rationalization_prevention": "critical",
            "convergence_loop": "critical",
            "gate_mechanism": "critical",
        },
        "model_hint_override": "quality",
        "token_budget_increase_pct": 20,
    },
}


# ---------------------------------------------------------------------------
# v8.0.0 (P-07) — apply_round_escalation refactor (NineS [CC-448821-0001]
# closure). The legacy single-function body had cyclomatic complexity 11;
# splitting into 3 named helpers (``select_round_result`` /
# ``apply_severity_filter`` / ``escalate_round``) brings every leaf
# function's cc to ≤ 6 (per ``patch_plan §3 P-07 AC #6``) while keeping
# the public ``apply_round_escalation`` wrapper byte-identical to the
# v7.x return contract (verified by
# ``tests/test_feedback_reinforcement.py::TestApplyRoundEscalation``).
# ---------------------------------------------------------------------------


def select_round_result(
    round_num: int,
    escalation_config: dict[int, dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """Pick the override block for ``round_num`` from ``escalation_config``.

    Lookup priority:
      1. Exact match on ``round_num`` in the active config.
      2. ``round_num`` above the highest configured key → reuse the
         highest-budget block (the v7.x "max-round overflow" semantic).
      3. Otherwise → ``None`` (caller returns the profile untouched).

    The ``escalation_config`` parameter may be ``None`` to use the
    module-level :data:`_ROUND_ESCALATION_DEFAULTS`. Returns a borrow
    of the internal dict — callers MUST treat the result as read-only
    or copy-on-write.
    """
    config = escalation_config or _ROUND_ESCALATION_DEFAULTS
    overrides = config.get(round_num)
    if overrides is not None:
        return overrides
    if round_num > max(config, default=0):
        return max(
            config.values(),
            key=lambda v: v.get("token_budget_increase_pct", 0),
            default={},
        )
    return None


def apply_severity_filter(
    result: dict[str, Any],
    overrides: dict[str, Any],
) -> None:
    """Apply section-priority + model-hint overrides to ``result`` in place.

    The "severity filter" naming reflects the ratchet vocabulary in
    ``patch_plan §3 P-07``: the per-round overrides effectively raise
    the severity floor for the next convergence round so safety-critical
    primitives (rationalization_prevention, convergence_loop, …) are
    promoted to ``critical``.

    Mutates ``result``; does NOT return anything (S-5 — never silently
    swallow the mutation by returning a fresh dict the caller forgets
    to use).
    """
    prio_overrides = overrides.get("section_priority_overrides", {})
    if prio_overrides:
        existing = dict(result.get("section_priorities", {}))
        existing.update(prio_overrides)
        result["section_priorities"] = existing
    if "model_hint_override" in overrides:
        result["model_hint"] = overrides["model_hint_override"]


def escalate_round(
    result: dict[str, Any],
    overrides: dict[str, Any],
) -> None:
    """Apply compression + token-budget escalation to ``result`` in place.

    Bumps ``compression_intensity`` (typically to ``"minimal"`` on
    higher rounds) and grows ``token_budget`` by
    ``overrides["token_budget_increase_pct"]`` percent — the v7.x
    round-3 escalation budget grew the budget by 20 % so the escalated
    convergence round had room to load the additional gate-mechanism /
    rationalization sections (per ``patch_plan §3 P-07``: this helper is
    the round-level companion to the new
    :class:`devolaflow.gate.ratchet.MonotonicRatchet`).
    """
    if "compression_intensity" in overrides:
        result["compression_intensity"] = overrides["compression_intensity"]
    increase_pct = overrides.get("token_budget_increase_pct", 0)
    if increase_pct and "token_budget" in result:
        result["token_budget"] = int(result["token_budget"] * (1 + increase_pct / 100))


def apply_round_escalation(
    profile: dict[str, Any],
    round_num: int,
    escalation_config: dict[int, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return a profile copy with round-based escalation overrides applied.

    Higher convergence rounds get stricter section priorities, better
    model hints, and increased token budgets.  Does not mutate *profile*.

    v8.0.0 (P-07) refactor: delegates lookup to :func:`select_round_result`,
    priority + model-hint overrides to :func:`apply_severity_filter`, and
    compression + budget escalation to :func:`escalate_round`. Legacy
    cyclomatic complexity 11 (NineS finding ``[CC-448821-0001]``) drops
    to ≤ 4 on the wrapper and ≤ 6 on every helper. Return contract is
    byte-identical to v7.x (verified by
    ``tests/test_feedback_reinforcement.py::TestApplyRoundEscalation``
    and ``tests/test_compressor.py::TestRoundEscalationBudget``).
    """
    overrides = select_round_result(round_num, escalation_config)
    if overrides is None:
        return profile
    result = {**profile}
    apply_severity_filter(result, overrides)
    escalate_round(result, overrides)
    return result


def _print_cli_usage() -> None:
    """Print the CLI usage banner shown when no task_type is supplied."""
    print(
        "Usage: task_adaptive_selector.py <task_type> "
        "[--verbose] [--full] [--round N] [--plan-mode|--no-plan-mode]"
    )
    print()
    print("Task types: hotfix, feature, research, refactor, review, design")
    print("Also matches goal hints: 'fix bug', 'implement feature', etc.")


def _parse_round_arg(argv: list[str]) -> int:
    """Return the ``--round N`` value from *argv*, defaulting to 1.

    Invalid integer values are silently coerced to 1 (matching the legacy
    behaviour preserved by ``test_main_round_flag_invalid_falls_back_to_one``).
    """
    round_num = 1
    for i, arg in enumerate(argv):
        if arg == "--round" and i + 1 < len(argv):
            with contextlib.suppress(ValueError):
                round_num = int(argv[i + 1])
    return round_num


def _parse_plan_mode_flag(argv: list[str]) -> bool | None:
    """Return ``True`` / ``False`` / ``None`` for ``--plan-mode`` / ``--no-plan-mode``."""
    if "--plan-mode" in argv:
        return True
    if "--no-plan-mode" in argv:
        return False
    return None


def _print_cli_summary(result: dict[str, Any], *, verbose: bool, round_num: int) -> None:
    """Print the per-profile summary block (lines 1–N of CLI output)."""
    print(f"Profile: {result['profile_name']}")
    print(f"Description: {result['description']}")
    print(f"Model hint: {result['model_hint']}")
    print(f"Token budget: {result['budget']}")
    print(f"Tokens used: {result['total_tokens']} ({result['utilization_pct']}%)")
    if verbose:
        print(f"Round: {round_num}")
        print(f"Plan mode: {result['plan_mode']}")
    print()


def _print_cli_sections(result: dict[str, Any]) -> None:
    """Print selected/skipped/extra-context lines for a CLI run."""
    print("Selected sections:")
    for sec in result["selected_sections"]:
        print(f"  [{sec['tokens']:>4} tok] {sec['name']}")

    if result.get("learnings_included"):
        print("  [learnings] operational learnings injected")

    print()
    print(f"Skipped sections: {', '.join(result['skipped_sections'])}")
    print()
    print(f"Extra context to load: {', '.join(result['extra_context'])}")


def _print_cli_assembled(result: dict[str, Any]) -> None:
    """Print the full assembled context block (only when ``--full`` was given)."""
    print()
    print("=" * 72)
    print("ASSEMBLED CONTEXT")
    print("=" * 72)
    print(result["assembled_text"])


def main():
    """CLI entry point for the task-adaptive context selector."""
    if len(sys.argv) < 2:
        _print_cli_usage()
        sys.exit(1)

    task_type = sys.argv[1]
    verbose = "--verbose" in sys.argv
    show_full = "--full" in sys.argv
    round_num = _parse_round_arg(sys.argv)
    plan_mode_flag = _parse_plan_mode_flag(sys.argv)

    result = select_context(
        task_type,
        verbose=verbose,
        round_num=round_num,
        plan_mode=plan_mode_flag,
    )

    _print_cli_summary(result, verbose=verbose, round_num=round_num)
    _print_cli_sections(result)

    if show_full:
        _print_cli_assembled(result)


if __name__ == "__main__":
    main()
