"""DevolaFlow operator-facing skill surfaces (v9.1.2 PV-02+; v11.3.0 PV-01; v11.4.0 PV-01).

This package bundles thin CLI / heuristic surfaces consumed by the
operator and by L0 dispatchers when steering toward the
``change-driven`` workflow:

* :mod:`devolaflow.skills.change_activation` — pure-function
  complexity classifier + activation verdict (the heuristic codified
  by Architecture rule **A-6** "Workspace Engagement Auto-Activation"
  per ``.rules/architecture.mdc``).
* :mod:`devolaflow.skills.slash_commands` — ``/devola:propose``,
  ``/devola:apply``, ``/devola:verify``, ``/devola:archive`` thin
  wrappers around the existing
  :class:`devolaflow.agent_workspace.ChangeStore` /
  :class:`devolaflow.agent_workspace.ArchiveManager` APIs (closes
  M-007 from the v9.0.0 retrospective §3.3 — operator-facing slash
  command surface was telegraphed for v9.1.x).
* :mod:`devolaflow.skills.grill_mode` — pure-function heuristics for
  the v11.3.0 grill-with-docs integration (one-question-at-a-time
  interview, fuzzy-term sharpening, 3-condition ADR gate, CONTEXT.md
  layout inference). The five public functions are documented by the
  forthcoming Wave 2 rules **W-22** (Grill Mode Activation Contract)
  and **W-23** (Domain Glossary Maintenance); the integration design
  is in ``.local/research/v11.3.0_gap_analysis.md`` §4 P1.3.
* :mod:`devolaflow.skills.subagent_pattern` — pure-function selection
  heuristic for the v11.4.0 philschmid 4-pattern subagent taxonomy
  (Inline Tool, Fan-Out, Agent Pool, Teams). The three public
  functions plus two Literal aliases are forward-defined by workflow
  rule **W-24** ("Subagent Pattern Selection") authored in v11.4.0
  Wave 2 alongside the new Tier-2 reference
  ``workflow-system/agent/references/subagent-patterns.md``; the
  integration design is in
  ``.local/research/v11.4.0_subagent_pattern_analysis.md`` §6 P1.2.
* :mod:`devolaflow.skills.pathfinder` — pure-function natural-language
  activation for the read-only v17.3.0 Pathfinder L2 look-ahead role.

All five modules are R5-strict additive:

* No existing public symbol is mutated.
* No new top-level dispatch key lands in
  ``schemas/lean-dispatch.yaml#layout_invariant`` (every heuristic is
  prompt-side only — A-2 invariant intact).
* The slash commands use ``argparse`` exit codes (``0`` happy path,
  non-zero on failure); errors are logged + re-raised per S-5
  (no silent failures).

Per W-20 (env-flag reuse-first), the activation surface honoured by
:mod:`change_activation` REUSES the existing
``DEVOLAFLOW_AGENT_WORKSPACE`` env flag (introduced by v9.1.1 PV-01
SKILL.md §"Workspace Engagement (Read at Session Start)") rather than
introducing a new flag. The same flag will be REUSED by the v9.1.3
PV-03 ``pre_handoff`` lifecycle hook so the activation contract stays
single-surface. :mod:`grill_mode` and :mod:`subagent_pattern` do NOT
introduce new env flags — their activation surface is natural-language
only (per gap-analyses §4 P1.3 R-7 and §6 P1.2 + §8 R-6 respectively),
preserving the v11.1.x env-flag count at 8.

Source: v9.2.0 cycle plan §PV-02 — ``.cursor/plans/workspace-
capability-activation_ec560bc8.plan.md``; v11.3.0 cycle plan §P1.3 —
``.local/research/v11.3.0_gap_analysis.md``; v11.4.0 cycle plan §P1.2 —
``.local/research/v11.4.0_subagent_pattern_analysis.md``.
"""

from __future__ import annotations

from devolaflow.skills.grill_mode import (
    AdrConditionName,
    CanonicalTermSuggestion,
    ContextLayout,
    DecisionDescriptor,
    FuzzyTerm,
    GrillVerdict,
    classify_grill_intent,
    detect_fuzzy_terms,
    infer_context_layout,
    propose_canonical_term,
    qualifies_as_adr,
)
from devolaflow.skills.pathfinder import (
    PathfindVerdict,
    classify_pathfind_intent,
    should_schedule_pathfind,
)
from devolaflow.skills.subagent_pattern import (
    ModelTier,
    PatternVerdict,
    forbidden_pattern_rationale,
    select_pattern,
    validate_inputs,
)

__all__: list[str] = [
    "AdrConditionName",
    "CanonicalTermSuggestion",
    "ContextLayout",
    "DecisionDescriptor",
    "FuzzyTerm",
    "GrillVerdict",
    "ModelTier",
    "PathfindVerdict",
    "PatternVerdict",
    "classify_grill_intent",
    "classify_pathfind_intent",
    "should_schedule_pathfind",
    "detect_fuzzy_terms",
    "forbidden_pattern_rationale",
    "infer_context_layout",
    "propose_canonical_term",
    "qualifies_as_adr",
    "select_pattern",
    "validate_inputs",
]
