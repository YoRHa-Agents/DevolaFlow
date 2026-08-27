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

import functools
import logging
import os
import re
import warnings
from pathlib import Path
from typing import Any

import yaml

from devolaflow.learnings import (
    format_learnings_section,
    load_relevant_learnings,
    resolve_learnings_path,
)
from devolaflow.section_registry import (
    SectionAnchorRegistry,
    discover_section_content,
    extract_section_by_heading,
)

logger = logging.getLogger(__name__)

PROFILES_PATH = Path(__file__).parents[2] / "workflow-system" / "agent" / "context_profiles.yaml"

PRIORITY_ORDER = ["critical", "important", "supplementary"]

VALID_MODEL_HINTS = {"quality", "balanced", "budget", "inherit"}

VALID_COMPRESSION_INTENSITIES = {"minimal", "standard", "aggressive"}

# v12.2.0 PV-04 — per-task-type timeout defaults (seconds). Sourced from
# the v12.1.0 SKILL.md §"Subagent Hang Prevention" L0 contract:
#     research=2700 / impl=1800 / test=900 / review=1200 / hotfix=600
# (default fail-safe ceiling 7200s for unknown task types).
#
# Consumed by :func:`default_timeout_for` which dispatchers pass into
# :meth:`devolaflow.agent_workspace.dispatch_executor.AsyncDispatchExecutor.dispatch_parallel`
# as the ``timeouts={task_id: seconds}`` kwarg. Default-OFF — no auto-wire;
# callers opt-in by invoking the helper. Per W-20 §3, this is purely
# library-level (no env flag).
#
# Source: `.local/research/v12.2.0_gap_analysis.md` §2 D-4; v12.0.0
TASK_TYPE_TIMEOUT_DEFAULTS: dict[str, int] = {
    "research": 2700,
    "impl": 1800,
    "test": 900,
    "review": 1200,
    "hotfix": 600,
    "pathfind": 2700,
}

TASK_TYPE_TIMEOUT_FALLBACK: int = 7200
"""Fail-safe ceiling for unrecognised task types.

Matches the SKILL.md §"Dispatch & Report Protocol" default. Operators
should treat 7200 as the ceiling, not the target — pass an explicit
per-task ``timeout_seconds`` in TaskDispatch when the task type is known.
"""


def default_timeout_for(task_type: str) -> int:
    """Return the v12.2.0 PV-04 default ``timeout_seconds`` for ``task_type``.

    Lookup is exact-match against :data:`TASK_TYPE_TIMEOUT_DEFAULTS`;
    unrecognised task types fall back to :data:`TASK_TYPE_TIMEOUT_FALLBACK`
    (7200 s — the SKILL.md fail-safe ceiling per §"Dispatch & Report
    Protocol").

    The helper is pure (no side effects, no env reads, no file IO) so it
    is safe to call from any dispatcher layer without R5 strict gating.
    Callers SHOULD invoke this when constructing the ``timeouts={}``
    kwarg for :meth:`AsyncDispatchExecutor.dispatch_parallel`; the
    library-level default-OFF discipline is preserved because callers
    opt in by passing the kwarg at all.

    Source: SKILL.md §"Subagent Hang Prevention" L0 contract +
    `.local/research/v12.2.0_gap_analysis.md` §2 D-4.
    """
    if not isinstance(task_type, str):
        return TASK_TYPE_TIMEOUT_FALLBACK
    return TASK_TYPE_TIMEOUT_DEFAULTS.get(task_type.strip().lower(), TASK_TYPE_TIMEOUT_FALLBACK)


DEFAULT_TIMEOUT_CLASS = "impl"
"""Timeout class assumed for profiles that omit ``timeout_class``.

Per the v14.5.0 G-037 delta-only overlay discipline (G-026), the 16
impl-class profiles carry NO ``timeout_class`` key in
``context_profiles.yaml`` — only the 8 profiles whose class differs
from ``impl`` declare a delta.
"""


def resolve_timeout_seconds(
    profile_config: dict[str, Any],
    config: dict[str, Any],
) -> int:
    """Resolve the auto-populated ``timeout_seconds`` for a profile.

    v14.5.0 (G-037) — graduation of the v12.3.0 PV-04 discovery hint
    (``references/execution-protocol.md`` §14): :func:`select_context`
    now populates ``timeout_seconds`` from the profile's timeout class
    instead of leaving the integration opt-in by call-site.

    Lookup priority (mirrors the :func:`resolve_model_hint` precedent):
      1. ``profile_config["timeout_class"]`` — per-profile delta
         (default :data:`DEFAULT_TIMEOUT_CLASS` when absent).
      2. ``defaults.timeout_class_map[class]`` in
         ``context_profiles.yaml`` — the SSOT map (SKILL.md §"Subagent
         Hang Prevention" values: research=2700 / impl=1800 / test=900 /
         review=1200 / hotfix=600).
      3. ``defaults.timeout_class_map["fallback"]`` — 7200 s fail-safe
         ceiling for unrecognised classes.
      4. :func:`default_timeout_for` — library-constant mirror, for
         configs that predate (or omit) the ``defaults.timeout_class_map``
         block. Keeps minimal test fixtures and external YAML consumers
         absence-safe.

    Pure function (no env reads, no file IO); never raises on malformed
    class values — an unknown class resolves to the fail-safe ceiling
    per the SKILL.md L0 contract.
    """
    timeout_class = profile_config.get("timeout_class", DEFAULT_TIMEOUT_CLASS)
    if not isinstance(timeout_class, str):
        timeout_class = DEFAULT_TIMEOUT_CLASS
    timeout_class = timeout_class.strip().lower()

    defaults_block = config.get("defaults") or {}
    timeout_map = defaults_block.get("timeout_class_map") or {}
    if timeout_class in timeout_map:
        return int(timeout_map[timeout_class])
    if "fallback" in timeout_map:
        return int(timeout_map["fallback"])
    return default_timeout_for(timeout_class)


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
        "hierarchy_table": "critical",
        "gate_mechanism": "critical",
        "rationalization_prevention": "critical",
        "convergence_loop": "important",
        "agent_mode_protocol": "supplementary",
    },
    "compression_intensity": "minimal",
    "model_hint_override": "quality",
    # v11.1.0 PV-04 — G-PLAN-2 cascade-required runtime carrier.
    # Default True under v11.1.0 to match the user's "在 Plan 模式中，也需要
    # 能够体现出多层级调度的原则" directive (cycle plan §1 verbatim block);
    # downstream consumers (L0 plan-render code, future PV-05 A-7 strict
    # validator) read this key from the merged profile dict to learn the
    # plan-mode default. The schema-side carrier is gate.cascade_required
    # (NEST sub-field added in W01); this dict-side carrier is the
    # plan-mode runtime knob. R5 backward-compat: the key is purely
    # additive — pre-v11.1.0 callers that never read this key see the
    # same byte-stable behaviour. Source: cycle plan §3 PV-04 W05.
    "plan_mode_cascade_required": True,
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

    v11.1.0 PV-04 — G-PLAN-2 propagates the
    ``plan_mode_cascade_required`` runtime knob from
    :data:`_PLAN_MODE_OVERRIDES` onto the returned profile dict so
    downstream L0 plan-render callers can read it without round-tripping
    through the override block. Default ``True`` under v11.1.0 (cascade
    is the normative plan-mode default per the user feedback ‘在 Plan
    模式中，也需要能够体现出多层级调度的原则’). Pre-v11.1.0 callers that
    never read the key see byte-stable behaviour (R5 strict additive
    contract).
    """
    result = {**profile}

    prio_overrides = _PLAN_MODE_OVERRIDES["section_priority_overrides"]
    existing = dict(result.get("section_priorities", {}))
    existing.update(prio_overrides)
    result["section_priorities"] = existing

    result["model_hint"] = _PLAN_MODE_OVERRIDES["model_hint_override"]
    result["compression_intensity"] = _PLAN_MODE_OVERRIDES["compression_intensity"]
    result["plan_mode_cascade_required"] = _PLAN_MODE_OVERRIDES["plan_mode_cascade_required"]
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

    boundary: one of l0_to_l1, l1_to_l2, l2_to_l1, l1_to_l0
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


# ---------------------------------------------------------------------------
# v9.3.0 PV-03 — mtime-probed LRU cache layer.
#
# Closes D-S-1..D-S-5 from `.local/research/v9.3.0_gap_analysis.md` §1.1.
# Per the PV-01 cProfile harness:
#   - load_profiles    : 600 calls × 121.266 s cumulative = 96.6 % of select_context cost
#   - load_skill_md    : ~32 KB read on every call (no cache)
#   - estimate_tokens  : 12,549 calls × 4.117 s cumulative (BPE encode = 3.596 s)
#
# Pattern: mtime probed as part of the cache key. A `path.stat().st_mtime_ns`
# read on every call is microseconds (one fs syscall, no read), and the
# composite key `(realpath_str, mtime_ns)` invalidates automatically when
# the file changes — no explicit `cache_clear` needed by callers.
#
# The lru_cache `maxsize` ceilings honour the spec:
#   - load_profiles    : 16  (one entry per distinct profiles_path; usually 1
#                             in production, up to ~5 in test workspaces)
#   - load_skill_md    : 16  (matched ceiling; usually 1 in production)
#   - estimate_tokens  : 2048 (high ceiling because section text fragments
#                              vary widely and recur across calls; the cache
#                              absorbs the BPE encode cost when the same
#                              section is re-rendered across rounds)
#
# Mutability contract: the cached `_load_profiles_cached` returns a single
# dict shared across cache hits. The existing `select_context` codepath
# treats the result as READ-ONLY — every helper that derives from it
# (`apply_plan_mode_overrides`, `apply_round_escalation`,
# `_resolve_active_profile`) constructs new dicts via `{**profile, ...}`
# copy-on-write semantics rather than mutating the source. This invariant
# is verified by `tests/test_selector_lru_cache.py::TestCacheImmutability`.
# ---------------------------------------------------------------------------


@functools.lru_cache(maxsize=16)
def _load_profiles_cached(path_str: str, mtime_ns: int) -> dict[str, Any]:
    """Cached YAML-parse stage of :func:`load_profiles`.

    The ``mtime_ns`` argument is the cache-invalidation key — a file edit
    bumps ``stat().st_mtime_ns`` and forces a fresh parse on the next
    :func:`load_profiles` call. ``path_str`` is the resolved path so two
    callers asking for the same file via different relative paths share
    the same cache entry.

    DO NOT mutate the returned dict — see the §"Mutability contract"
    block above the cache layer. Callers receive a SHARED reference;
    every downstream helper copy-on-writes via ``{**profile, ...}``.
    """
    return yaml.safe_load(Path(path_str).read_text(encoding="utf-8"))


@functools.lru_cache(maxsize=16)
def _load_skill_md_cached(path_str: str, mtime_ns: int) -> str:
    """Cached read of SKILL.md.

    Same mtime-probe pattern as :func:`_load_profiles_cached`. Strings
    are immutable in Python so the mutability contract is automatic
    here — cache hits return the same ``str`` reference and any
    downstream slicing/splitting produces independent new strings.
    """
    return Path(path_str).read_text(encoding="utf-8")


def load_profiles(path: Path | None = None) -> dict[str, Any]:
    """Load context profiles from a YAML configuration file.

    v9.3.0 PV-03: now backed by an mtime-probed LRU cache
    (:func:`_load_profiles_cached`). The first call against a given
    ``(path, mtime_ns)`` key parses the YAML; subsequent calls against
    the same key return the cached dict in O(1). A file edit bumps
    ``mtime_ns`` and invalidates automatically — no explicit
    ``cache_clear`` needed.

    Returns the raw cached dict for the live process; mutating the
    returned structure is undefined behaviour. The downstream
    ``select_context`` helpers honour the read-only contract via
    copy-on-write — see the §"Mutability contract" block in the cache
    layer above.

    The ``stat`` lookup is the only filesystem syscall on the hot path
    when the cache is warm; pre-PV-03 ``yaml.safe_load`` averaged 121 s
    cumulative across 600 calls (96.6 % of ``select_context`` wall
    clock). Post-PV-03 the warm path is a single dict.get-shaped lookup
    plus the mtime probe.
    """
    p = path or PROFILES_PATH
    stat_result = p.stat()
    return _load_profiles_cached(str(p), stat_result.st_mtime_ns)


def load_skill_md(config: dict[str, Any]) -> str:
    """Load the SKILL.md file contents as a string.

    v9.3.0 PV-03: now backed by an mtime-probed LRU cache
    (:func:`_load_skill_md_cached`). The fallback rglob path (used when
    the canonical relative location is missing) participates in the
    cache through the resolved candidate's mtime — a fresh clone with
    a moved SKILL.md still benefits from the cache after the first
    call.

    Strings are immutable so cache hits are byte-identical references
    by design.
    """
    skill_path = Path(__file__).parents[2] / "workflow-system" / "agent" / "SKILL.md"
    if not skill_path.exists():
        repo_root = Path(__file__).parents[2]
        candidates = list(repo_root.rglob("SKILL.md"))
        if candidates:
            skill_path = candidates[0]
        else:
            raise FileNotFoundError(f"SKILL.md not found relative to {repo_root}")
    stat_result = skill_path.stat()
    return _load_skill_md_cached(str(skill_path), stat_result.st_mtime_ns)


_LINE_RANGE_RE = re.compile(r"^\d+-\d+$")
_DEPRECATION_WARNED_ANCHORS: set[str] = set()


def extract_section(full_text: str, line_range: str) -> str:
    """Extract lines from full_text given a range like '57-68'.

    v8.2.0 (PV-05): retained as a **deprecated fallback** for sections
    not yet migrated to the section-anchor registry. New section lookups
    should go through :class:`devolaflow.section_registry.SectionAnchorRegistry`
    + :func:`devolaflow.section_registry.discover_section_content`. The
    deprecation surfaces via a one-shot ``DeprecationWarning`` per anchor
    in :func:`_select_sections_within_budget` (S-5 — never silently use
    the legacy path).
    """
    if not line_range or not _LINE_RANGE_RE.match(line_range):
        return ""
    lines = full_text.splitlines()
    start, end = map(int, line_range.split("-"))
    return "\n".join(lines[start - 1 : end])


def build_section_registry(config: dict[str, Any]) -> SectionAnchorRegistry:
    """Build a :class:`SectionAnchorRegistry` from the loaded profiles config.

    Parses the top-level ``section_anchors:`` mapping in
    ``workflow-system/agent/context_profiles.yaml``. When the mapping
    is absent (older configs predating PV-05) returns an empty registry
    so :func:`_select_sections_within_budget` transparently falls back
    to the deprecated line-based ``sections:`` lookup.
    """
    registry = SectionAnchorRegistry()
    registry.register_from_yaml(config)
    return registry


def _resolve_section_text(
    section_name: str,
    registry: SectionAnchorRegistry,
    sections_registry: dict[str, Any],
    skill_text: str,
) -> str:
    """Resolve section content using the anchor registry first, falling back to lines.

    v8.2.0 (PV-05) — primary path uses
    :func:`devolaflow.section_registry.discover_section_content` so the
    section text is sourced by markdown heading match (no SKILL.md line
    numbers involved). When the anchor is not registered, falls back to
    the legacy line-based lookup with a one-shot ``DeprecationWarning``
    per anchor (S-5 — never silently swallow the deprecation signal).

    Returns ``""`` when neither path resolves to content (the caller
    treats this as a deliberate skip — e.g. a legacy advisory profile
    whose ``lines: "N/A"`` value never extracted any content).
    """
    if registry.has(section_name):
        text = discover_section_content(section_name, registry)
        if text:
            return text

    sec_info = sections_registry.get(section_name)
    if not isinstance(sec_info, dict):
        return ""
    line_range = sec_info.get("lines", "")
    if not line_range or not _LINE_RANGE_RE.match(line_range):
        return ""

    if section_name not in _DEPRECATION_WARNED_ANCHORS:
        _DEPRECATION_WARNED_ANCHORS.add(section_name)
        warnings.warn(
            f"section {section_name!r} resolved via deprecated line-based lookup "
            f"(lines={line_range!r}); migrate to section_anchors registry per "
            f"PV-05 (.local/research/v8.2.0_patch_plan.md §3 PV-05 AC #1).",
            DeprecationWarning,
            stacklevel=2,
        )
    return extract_section(skill_text, line_range)


@functools.lru_cache(maxsize=2048)
def _estimate_tokens_tiktoken_cached(text: str) -> int:
    """Cached tiktoken-BPE-encode stage of :func:`estimate_tokens`.

    Used when the tiktoken module is importable AND the resulting
    encoder loads cleanly. See :func:`estimate_tokens` for the routing
    contract.
    """
    import tiktoken

    enc = tiktoken.encoding_for_model("gpt-4o")
    return len(enc.encode(text))


@functools.lru_cache(maxsize=2048)
def _estimate_tokens_fallback_cached(text: str) -> int:
    """Cached deterministic-fallback stage of :func:`estimate_tokens`.

    Used when tiktoken is unavailable. The 4-char-per-token heuristic
    is the v6.x baseline that ``conftest.py::_force_fallback_token_estimator``
    pins for benchmark scenarios so CI vs local-dev token counts agree
    deterministically.
    """
    return max(1, len(text) // 4)


def estimate_tokens(text: str) -> int:
    """Estimate token count. Uses tiktoken if available, otherwise ~4 chars/token.

    v9.3.0 PV-03: closes D-S-5. Pre-PV-03 the BPE encode step
    (``tiktoken.CoreBPE.encode``) ran 12,549 times during a 600-call
    selector batch and consumed 3.596 s of self time — the second-largest
    self-time bucket after PyYAML scanning. Most of those calls were
    on identical section text (the same SKILL.md section rendered
    across rounds), so a content-keyed LRU cache absorbs ~95 % of
    the cost.

    Routing contract: the public function picks BETWEEN
    :func:`_estimate_tokens_tiktoken_cached` and
    :func:`_estimate_tokens_fallback_cached` on every call based on
    whether ``tiktoken`` is currently importable. The two-cache split
    is mandatory because ``tests/conftest.py::_force_fallback_token_estimator``
    monkey-patches ``sys.modules['tiktoken'] = None`` per-test for
    benchmark determinism — a single cache would lock in the FIRST
    branch's verdict and tests run after a tiktoken-using test would
    silently keep using the (now-poisoned) tiktoken cache. Splitting by
    branch keeps each cache pure: the tiktoken cache only ever holds
    tiktoken-derived counts, and the fallback cache only ever holds
    ``len(text) // 4`` counts.

    The ``maxsize=2048`` per-cache ceiling balances cache hit-rate
    against memory use (2048 × ~256 bytes per string ≈ 500 KB per cache;
    1 MB total in the worst case where both branches see traffic).
    """
    try:
        import tiktoken  # noqa: F401  (probe import only — actual use is in the cached helper)
    except (ImportError, Exception):
        return _estimate_tokens_fallback_cached(text)
    try:
        return _estimate_tokens_tiktoken_cached(text)
    except Exception:
        return _estimate_tokens_fallback_cached(text)


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
    anchor_registry: SectionAnchorRegistry | None = None,
) -> tuple[list[tuple[str, str, int]], list[str], int]:
    """Pick sections in priority order until the token budget is exhausted.

    v8.0.0 (P-02) — accepts an optional ``directive`` dict that is forwarded
    to :func:`_select_sections_by_priority` so directed-compaction overlays
    can promote focus sections within each priority tier. Default
    ``directive=None`` preserves byte-stable v7.x behaviour for every
    existing caller (verified by :class:`tests.test_compressor.
    TestSelectorDirectiveBackwardCompat`).

    v8.2.0 (PV-05) — accepts an optional ``anchor_registry`` so section
    text is resolved via the symbolic anchor → file path mapping
    (:func:`_resolve_section_text`) before falling back to the legacy
    line-based lookup. Default ``anchor_registry=None`` instantiates an
    empty registry so every section lookup goes through the deprecated
    line-based path with a one-shot ``DeprecationWarning`` per anchor —
    preserves byte-stable behaviour for any caller still on the
    pre-PV-05 ``sections:`` registry.
    """
    selected: list[tuple[str, str, int]] = []
    overflow: list[str] = []
    used_tokens = 0
    registry = anchor_registry if anchor_registry is not None else SectionAnchorRegistry()

    for section_name in _select_sections_by_priority(priority_buckets, directive):
        text = _resolve_section_text(section_name, registry, sections_registry, skill_text)
        if not text:
            continue
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
# v8.0.0 (P-08) — L2 Task behavioral guideline injection.
#
# Behavioral guidelines are 4 Karpathy-derived primitives (think_first,
# simplicity_check, surgical_scope, goal_loop) documented in
# ``workflow-system/agent/references/behavioral-guidelines.md`` and
# expressed in the dispatch payload via the top-level
# ``behavioral_guidelines`` field (canonical_order position 14, schema
# version 3 — added by P-08, P6 additive). The two helpers below resolve
# per-profile defaults and render the injectable text block. They are
# extracted from ``select_context`` so the parent function's cyclomatic
# complexity stays ≤ 8 (historical complexity-finding closure).
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
_BEHAVIORAL_ANCHOR = "behavioral_guidelines_reference"


def _resolve_behavioral_ref_path(
    anchor_registry: SectionAnchorRegistry | None = None,
    ref_path: Path | None = None,
) -> Path:
    """Resolve the behavioral-guidelines reference doc path.

    Lookup order (per PV-05 — anchors first, file paths second):
      1. Explicit ``ref_path`` parameter (test / script override).
      2. ``anchor_registry`` lookup of
         :data:`_BEHAVIORAL_ANCHOR` when the registry is supplied AND
         the anchor is registered.
      3. Module-level :data:`_BEHAVIORAL_REF_PATH` (legacy fallback).
    """
    if ref_path is not None:
        return ref_path
    if anchor_registry is not None and anchor_registry.has(_BEHAVIORAL_ANCHOR):
        rel = anchor_registry.lookup(_BEHAVIORAL_ANCHOR)
        return Path(__file__).parents[2] / rel
    return _BEHAVIORAL_REF_PATH


def _load_line_level_criteria(
    ref_path: Path | None = None,
    anchor_registry: SectionAnchorRegistry | None = None,
) -> list[str]:
    """Extract line-level behavioural criteria verbatim from the reference doc.

    v8.2.0 (PV-05): the ``ref_path`` is resolved through
    :func:`_resolve_behavioral_ref_path` so callers can supply a
    :class:`SectionAnchorRegistry` instead of hard-wiring the path. The
    anchor registry path uses :func:`extract_section_by_heading` for
    section discovery — no SKILL.md / reference-doc line numbers are
    consulted. The legacy module-level path remains as the fallback so
    callers that pre-date the registry continue to work byte-identically.

    Per CO-2 / C-3 (verbatim extraction), each bullet's text is preserved
    as-written in the markdown — no paraphrasing, normalisation, or
    re-ordering. Continuation lines (indented under a bullet, common for
    line-wrapped markdown) are joined into the parent bullet with a
    single space so the returned list carries each criterion's full
    prose. Nested bullets (lines that themselves start with ``- ``
    after indentation) terminate the parent bullet and start a fresh
    entry — matches Markdown rendering semantics.

    Returns ``[]`` when:
      * the resolved file does not exist (S-5 — explicit empty signal,
        never a silent exception),
      * the heading is absent (older reference docs predating PV-04),
      * the section is empty.
    """
    path = _resolve_behavioral_ref_path(anchor_registry=anchor_registry, ref_path=ref_path)
    if not path.exists():
        return []

    text = path.read_text(encoding="utf-8")
    section_body = extract_section_by_heading(text, _LINE_LEVEL_HEADING)
    if not section_body:
        return []
    section_body_lines = section_body.splitlines()
    if section_body_lines and section_body_lines[0].lstrip("# ").strip().lower().startswith(
        "line-level behavioral criteria"
    ):
        section_body = "\n".join(section_body_lines[1:])

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
    anchor_registry: SectionAnchorRegistry | None = None,
) -> dict[str, Any] | None:
    """Resolve the L2 Task behavioral_guidelines for ``profile``.

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
        criteria = _load_line_level_criteria(anchor_registry=anchor_registry)
        if criteria:
            base["line_level_criteria"] = criteria

    return base


def _compose_behavioral_block(
    behavioral_guidelines: dict[str, Any] | None,
    fold_advisory: bool = False,
) -> str:
    """Render the active behavioral guidelines into an injectable text block.

    The block is a compact ``## Behavioral Guidelines (L2 Task active)`` markdown
    section with one bullet per active rule. Inactive rules (those with a
    falsy flag) are NOT rendered so the token cost scales with the number
    of active rules. ``surgical_scope`` is always rendered (str field with
    no opt-out) when the block is non-None.

    The full rule prose lives in
    ``workflow-system/agent/references/behavioral-guidelines.md`` (Tier 3
    on-demand reference, loaded only when this block surfaces). This helper
    emits a 5-line summary block (~ 30-100 tokens depending on active
    rules) intended for verbatim injection into the L2 Task dispatch context.

    v8.2.0 (PV-04): when ``surgical_scope='line'`` AND
    ``line_level_criteria`` is present, each criterion is rendered as an
    indented sub-bullet under BG-003 so the L2 Task agent sees the
    line-diff validation rules verbatim. ``surgical_scope='function'`` /
    ``'module'`` paths emit output byte-identical to v8.0.0-p08
    (R5 backward-compat discipline).

    When ``fold_advisory`` is true, active fields explicitly classified as
    ``advisory`` are replaced by one authorization line. Guard fields remain
    verbatim, including BG-003 and any line-level criteria. The default is
    false so legacy callers retain byte-identical text and ordering.

    Returns "" when ``behavioral_guidelines`` is None or empty so callers
    can ``if block:`` without a None-check.
    """
    if not behavioral_guidelines:
        return ""

    lines = ["## Behavioral Guidelines (L2 Task active)"]
    constraint_tiers = behavioral_guidelines.get("constraint_tiers")
    if not isinstance(constraint_tiers, dict):
        constraint_tiers = {}
    folded_count = 0

    def append_rule(field: str, text: str) -> None:
        nonlocal folded_count
        if not behavioral_guidelines.get(field):
            return
        if fold_advisory and constraint_tiers.get(field) == "advisory":
            folded_count += 1
            return
        lines.append(text)

    append_rule(
        "think_first",
        "- BG-001 think_first ENABLED — emit numbered plan before any source edit.",
    )
    append_rule(
        "simplicity_check",
        "- BG-002 simplicity_check ENABLED — audit 3 over-engineering smells before commit.",
    )
    scope = behavioral_guidelines.get("surgical_scope", "function")
    lines.append(f"- BG-003 surgical_scope = {scope!r} — diff hunks MUST stay within this tier.")
    if scope == "line":
        for criterion in behavioral_guidelines.get("line_level_criteria") or []:
            lines.append(f"  - {criterion}")
    append_rule(
        "goal_loop",
        "- BG-004 goal_loop ENABLED — restate user goal verbatim at round start.",
    )
    # v12.2.0 PV-03 — Mnimiy 3-rule extension. Active rules render as
    # 1-line bullets (~ 20-30 tokens each); inactive rules omit the
    # bullet so the token cost scales with active-rule count.
    append_rule(
        "no_llm_for_deterministic",
        "- BG-005 no_llm_for_deterministic ENABLED — route deterministic "
        "decisions (retry / routing / thresholds) through code, not prompts.",
    )
    append_rule(
        "surface_conflicts",
        "- BG-006 surface_conflicts ENABLED — when 2 patterns disagree, "
        "flag the conflict as a finding; do NOT average both into one solution.",
    )
    append_rule(
        "convention_first",
        "- BG-007 convention_first ENABLED — match the codebase's existing "
        "pattern; introduce novelty only via explicit ADR / escalation.",
    )
    if folded_count:
        lines.append(
            f"advisory 约束 {folded_count} 条已折叠"
            "（清单见 workflow-system/agent/references/behavioral-guidelines.md），"
            "授权模型自行判断遵从"
        )
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
    after a historical complexity finding. Returns
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
        compression_intensity = resolve_compression_intensity("l1_to_l2", config)

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
      - behavioral_guidelines (v8.0.0 P-08, v16.0.0 M5-a): resolved guideline
        dict with nested ``constraint_tiers`` and ``advisory_folded`` metadata
        when the profile carries the block, otherwise ``None`` (preserves the
        exact no-block return shape)
      - timeout_seconds (v14.5.0 G-037): per-task-type ``timeout_seconds``
        default resolved from the profile's ``timeout_class`` via
        :func:`resolve_timeout_seconds` (SSOT:
        ``defaults.timeout_class_map`` in ``context_profiles.yaml``).
        Purely additive — callers ignoring the key see zero behavior
        change; the lean-dispatch schema already documents the
        ``header.timeout_seconds`` field this hint feeds.
      - agents_md_slice (v17.0.0 R3 / G17-B3): additive compact account from
        ``agents_md_slice.slice_account``; ``{}`` + WARNING on failure (S-5).

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
    complexity from 16 down to ≤ 8, closing the historical complexity
    finding.
    The dispatch-payload contract is preserved bytewise for the v7.x
    return key set; the new ``behavioral_guidelines`` key is purely
    additive (``None`` when the profile omits the block).
    """
    config = load_profiles(profiles_path)
    skill_text = load_skill_md(config)
    sections_registry = config.get("sections", {})
    anchor_registry = build_section_registry(config)

    profile_name, profile, active_plan_mode = _resolve_active_profile(
        config, task_type, plan_mode, round_num, escalation_config
    )
    budget = profile.get("token_budget", 6000)

    escalation_applied = round_num > 1
    profile_overrides_applied = escalation_applied or active_plan_mode
    model_hint, compression_intensity = _resolve_dispatch_overrides(
        profile, task_type, complexity_tier, config, profile_overrides_applied
    )

    advisor_enabled, advisor_text, advisor_reserve = _resolve_advisor_text(profile)
    learnings_config = profile.get("learnings", {})
    learnings_reserve = _compute_learnings_reserve(learnings_config, profiles_path, budget)

    # Imported at the selector boundary to avoid the harness package's
    # telemetry -> selector import cycle during module initialization.
    from devolaflow.harness.tiers import (
        annotate_behavioral_guidelines,
        should_fold_advisory,
    )

    resolved_behavioral = _select_behavioral_sections(profile, config, anchor_registry)
    behavioral_guidelines = annotate_behavioral_guidelines(resolved_behavioral)
    has_behavioral = behavioral_guidelines is not None
    advisory_folded = has_behavioral and should_fold_advisory(model_hint, profiles_path)
    behavioral_text = _compose_behavioral_block(
        behavioral_guidelines,
        fold_advisory=advisory_folded,
    )
    if behavioral_guidelines is not None:
        behavioral_guidelines["advisory_folded"] = advisory_folded
    behavioral_reserve = estimate_tokens(behavioral_text) if behavioral_text else 0

    section_budget = budget - advisor_reserve - learnings_reserve - behavioral_reserve

    priority_buckets, skipped = _build_priority_buckets(profile.get("section_priorities", {}))
    selected, overflow_skipped, used_tokens = _select_sections_within_budget(
        priority_buckets,
        sections_registry,
        skill_text,
        section_budget,
        verbose,
        anchor_registry=anchor_registry,
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

    # v14.5.0 (G-037) — additive dispatch hint resolved from the profile's
    # timeout class (SSOT: defaults.timeout_class_map). Deliberately NOT
    # round-escalated: no W-8 / P4 rule grows timeouts across convergence
    # rounds, and apply_round_escalation never touches ``timeout_class``.
    timeout_seconds = resolve_timeout_seconds(profile, config)

    # v17.0.0 R3 (G17-B3/D-R3-1) — additive slice account (owner-cached; S-5 safe).
    from devolaflow.agents_md_slice import slice_account

    agents_md_slice = slice_account(task_type, profiles_path=profiles_path)

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
        "timeout_seconds": timeout_seconds,
        "round_num": round_num,
        "escalation_applied": escalation_applied,
        "plan_mode": active_plan_mode,
        "plan_mode_applied": active_plan_mode,
        "behavioral_guidelines": behavioral_guidelines,
        "agents_md_slice": agents_md_slice,
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
# v8.0.0 (P-07) — apply_round_escalation refactor (historical complexity
# finding closure). The legacy single-function body had cyclomatic complexity 11;
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
    cyclomatic complexity 11 drops to ≤ 4 on the wrapper and ≤ 6 on every
    helper, closing the historical complexity finding. Return contract is
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


# v9.7.0 (PV-04 — Performance Overhaul #2) — Selector cache warmup.
# Pre-populates top-5 task types × rounds 1-3 to avoid cold-cache dispatches.
# ``DEVOLAFLOW_WARMUP`` is R5-strict: only literal ``"1"`` opts in.
# Source: `.local/research/v9.7.0_gap_analysis.md` §1.3 D-N-2.

WARMUP_ENV_FLAG: str = "DEVOLAFLOW_WARMUP"
"""Env-flag name. Activates :func:`warmup_selector_cache` when set EXACTLY
to the literal string ``"1"`` (R5 strict pattern). Any other value
(unset, ``""``, ``"true"``, ``"0"``, ...) is DEFAULT-OFF."""

WARMUP_TRUTHY_VALUE: str = "1"
"""The single literal env-flag value that activates warmup. Surfaces the
R5 strict contract so callers / tests can branch on the same constant."""

WARMUP_TASK_TYPES: tuple[str, ...] = (
    "implement",
    "research",
    "design",
    "hotfix",
    "review",
)
"""Top-5 task_types pre-populated by :func:`warmup_selector_cache`.

These match the canonical task-type set declared in
``workflow-system/agent/context_profiles.yaml#profiles`` and the
``select_context`` matrix exercised by selector and harness tests. A future
PV that adds or renames task types SHOULD update this tuple in the same PR
(silent drift would mean warmup misses supported entries)."""

WARMUP_ROUND_NUMS: tuple[int, ...] = (1, 2, 3)
"""Round numbers pre-populated by :func:`warmup_selector_cache`.

Round 1 is the most common (~80 % of dispatches); rounds 2 and 3 cover
the convergence-loop hot path. Higher rounds are rarer and not worth
the warmup cost."""


def warmup_selector_cache(
    task_types: tuple[str, ...] = WARMUP_TASK_TYPES,
    round_nums: tuple[int, ...] = WARMUP_ROUND_NUMS,
    *,
    force: bool = False,
) -> int:
    """Pre-populate the LRU caches for the top-N task_types × M round_nums.

    Opt-in via ``DEVOLAFLOW_WARMUP=1`` (R5 strict — only the literal
    string ``"1"`` activates; any other value is DEFAULT-OFF). When the
    env flag is unset, this function is a STRICT no-op (returns ``0``
    without spending any IO or CPU). When the flag IS set, the function
    iterates the cartesian product of ``task_types`` and ``round_nums``
    and calls :func:`select_context` once for each pair, populating the
    v9.3.0 PV-03 LRU caches on ``load_profiles`` / ``load_skill_md`` /
    ``estimate_tokens``. Returns the number of warmup calls that
    completed (so callers can log / verify the warmup actually ran).

    The ``force=True`` keyword bypasses the env-flag check — used by
    tests to assert the warmup mechanism without requiring the env
    var. Production callers should NEVER pass ``force=True`` (it
    defeats the opt-in contract).

    Idempotency: a second call against an already-warm cache is
    cheap (each ``select_context`` call hits the LRU cache in O(1)).
    Calling repeatedly is safe and bounded by ``len(task_types) ×
    len(round_nums)`` cache lookups.

    S-5 graceful: if a single warmup call raises (e.g. profiles.yaml
    missing for a transient reason), the helper logs a WARNING and
    continues with the next pair. The warmup is best-effort by
    contract — a partial warmup is still strictly better than a cold
    cache, and a hard-raise on the first transient failure would
    block session startup unnecessarily.

    Args:
      task_types: Tuple of task_type names to warm. Default
        :data:`WARMUP_TASK_TYPES` (top-5 canonical).
      round_nums: Tuple of round numbers to warm. Default
        :data:`WARMUP_ROUND_NUMS` ((1, 2, 3)).
      force: When ``True``, bypasses the env-flag check. ONLY for
        test code — production callers MUST NOT pass ``force=True``.

    Returns:
      Number of warmup calls that completed successfully (S-5 partial
      warmup is reported via this count; a cold-cache run with
      ``force=True`` would return ``len(task_types) * len(round_nums)``
      on success).
    """
    if not force and os.environ.get(WARMUP_ENV_FLAG) != WARMUP_TRUTHY_VALUE:
        return 0

    completed = 0
    for task_type in task_types:
        for round_num in round_nums:
            try:
                select_context(task_type=task_type, round_num=round_num)
                completed += 1
            except Exception as exc:  # noqa: BLE001 - S-5 graceful warmup
                logger.warning(
                    "warmup_selector_cache: select_context(task_type=%r, "
                    "round_num=%d) raised %s; continuing with next pair",
                    task_type,
                    round_num,
                    exc,
                )
    return completed


# ---------------------------------------------------------------------------
# v17.0.0 shim retirement (ADR-006 revisit): the v14.5.0 re-export shims
# that lived here were DELETED after every in-repo call site migrated to
# the owner modules. Import from:
#
#   * ``agents_md_slice.py`` — select_agents_md_slice + count_agents_md_rules
#   * ``selector_cli.py``    — the CLI block (main + _print_cli_* helpers)
#
# ``python -m devolaflow.task_adaptive_selector`` keeps working via the
# run-time import in the guard below. Absence pinned by
# ``tests/test_module_split_shims.py``.
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    from devolaflow.selector_cli import main

    main()
