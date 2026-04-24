#!/usr/bin/env python3
"""Static analyzer: detect public APIs in src/devolaflow with no production callers.

Catches the bug class where a public function/class exists, has unit tests
that import it, but no actual production code uses it. The v6.0.3 dead-wire
bug (``apply_round_escalation`` and ``merge_reinforcement_into_dispatch`` had
passing unit tests but ZERO production callers) cost 3 versions to detect and
fix. This script catches that class of bug at the source via CI.

Usage::

    python scripts/detect_dead_apis.py                  # text report, exit 0
    python scripts/detect_dead_apis.py --strict          # exit 2 if dead found
    python scripts/detect_dead_apis.py --format json     # JSON output

Programmatic API::

    from scripts.detect_dead_apis import find_dead_apis
    dead = find_dead_apis(src_dirs, test_dirs, allowlist=...)

Algorithm:

1. Walk ``src/devolaflow/**/*.py`` with the ``ast`` module. For each file,
   collect top-level ``def`` and ``class`` statements that:
   - Do not start with ``_`` (skip private and dunder)
   - Are not a CLI entry point (``main``, ``cli``, ``*_cmd``)
2. For each public symbol, scan candidate caller files in
   ``src/devolaflow/`` plus ``scripts/`` plus ``benchmarks/`` (NOT tests/)
   using AST. A "real use" is an ``ast.Name`` or ``ast.Attribute`` reference
   outside of an ``Import``/``ImportFrom`` statement — this excludes pure
   re-exports in ``__init__.py``. The defining file IS included in the
   search; the ``def``/``class`` statement that creates the symbol does not
   itself produce a ``Name`` node, so any other reference (recursive call,
   factory, decorator usage, instantiation by sibling code) keeps the
   symbol "alive". The dead-wire bug pattern was a function with literally
   zero production references — exactly what this catches.
3. Symbols with zero real-use references in any production file are
   reported as dead, unless they appear in the allowlist.

Stdlib only.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

CLI_ENTRY_NAMES: frozenset[str] = frozenset({"main", "cli"})
CLI_ENTRY_SUFFIX: str = "_cmd"


DEFAULT_ALLOWLIST: frozenset[str] = frozenset(
    {
        # v9.0.0 PV-07 (ADR-007 D5) — count_agents_md_rules is the canonical
        # rule-census helper consumed by
        # `tests/test_no_ghost_features.py::test_rule_count_under_cap` (the
        # 60-rule HARD cap lint) and by
        # `tests/test_pv07_agents_md_slice.py::test_count_agents_md_rules_matches_layer_split`
        # (the slice-vs-census parity test). The function exists solely to
        # surface the rule-count invariant — its in-repo "production caller"
        # IS the CI lint. NOT a domain-SSOT registry symbol per A-5.2 —
        # `count_agents_md_rules` is a pure read-only helper that walks the
        # compiled AGENTS.md file.
        "devolaflow.task_adaptive_selector:count_agents_md_rules",
        # v9.0.0 PV-07 (ADR-007 D2) — check_stub_drift verifies the 2
        # deprecated `.cursor/rules/{devola-flow,workflow}-rules.mdc` stubs
        # match the pinned fingerprints in `.rules/.compile-hashes.json`.
        # Consumed by `tests/test_no_ghost_features.py::test_rule_surfaces_compile_only`
        # (the ADR-007 D2 stub-drift lint). Like `check_rules_drift` (which
        # is also test-only), it exists solely to surface the deprecation
        # invariant. NOT a domain-SSOT registry symbol per A-5.2 — it's a
        # pure SHA-256 comparison helper paired with the
        # `RuleCompiler.compile_all()` writer.
        "devolaflow.local.drift:check_stub_drift",
        # v9.0.0 PV-07 (ADR-007 D2) — compute_stub_fingerprints is the
        # SHA-256 helper that the rule compiler invokes when emitting
        # the `.rules/.compile-hashes.json` store. Public so external
        # tooling that wants to verify stub fingerprints without
        # invoking the full `compile_all()` pipeline can do so.
        # NOT a domain-SSOT registry symbol per A-5.2 — pure
        # read-only fingerprint helper.
        "devolaflow.local.drift:compute_stub_fingerprints",
        # v9.0.0 PV-07 (ADR-007 D3) — select_agents_md_slice is the OPERATOR-
        # FACING per-task-type AGENTS.md slicing entry point. Default behavior
        # (`meta.agents_md_slice.enabled: false`) returns the full AGENTS.md
        # byte-identical to v8.5.1. When operators flip the YAML knob to
        # `true`, the function filters AGENTS.md per the per-profile layer
        # mapping. Currently consumed by `tests/test_pv07_agents_md_slice.py`
        # and the `--show-slice` CLI flag in `task_adaptive_selector.main()`;
        # the L0/L1/L2/L3 dispatch wiring is intentionally OPT-IN per ADR-007
        # D3 (the OPERATOR-VISIBLE breaking-change facet of v9.0.0 MAJOR
        # semver — see CHANGELOG `## [9.0.0]` "Adoption notes"). NOT a
        # domain-SSOT registry symbol per A-5.2 — pure read-only filter.
        "devolaflow.task_adaptive_selector:select_agents_md_slice",
        # v8.5.0 PV-05 (T8 NineS Hygiene A3 closure) — rebuild_index() is the
        # Python entry-point invoked by the Makefile target
        # `make nines-index-rebuild` via a `python -c "from devolaflow.nines.researcher
        # import rebuild_index; ..."` subprocess. The dead-API detector only
        # sees Python callers; the Makefile subprocess invocation does NOT
        # register as a caller in the AST walk. Allowlisted with this
        # comment so the W-19 / Workflow Rule W-18 ghost-audit refresh
        # contract is satisfied. NOT a domain-SSOT registry symbol per
        # A-5.2 — `rebuild_index` is a pure CLI wrapper around
        # `nines analyze --target-path . --depth deep --agent-impact --keypoints`.
        "devolaflow.nines.researcher:rebuild_index",
        # ---- Lifecycle hooks public API (P-05 in v7.4.8) ----
        # Per the v7.5.0 ghost-audit §3.C G-C1 closure design and the
        # P-05 dispatch directive, the lifecycle package is intentionally
        # NOT wired into existing dispatch / write / status flows in this
        # patch — integration is deferred to a future iteration. The four
        # public entry-points below are advertised in
        # ``workflow-system/agent/SKILL.md`` §"Lifecycle Hooks" and consumed
        # by external orchestrators (and ``tests/test_lifecycle_hooks.py``)
        # in lieu of an in-repo production call site.
        "devolaflow.lifecycle.dispatcher:run_hooks",
        "devolaflow.lifecycle.dispatcher:register_hook",
        "devolaflow.lifecycle.dispatcher:clear_hooks",
        "devolaflow.lifecycle.dispatcher:registered_events",
        # v8.3.2 PV-02 — shell_proxy module-level convenience wrapper.
        # ``proxy_command(cmd, env)`` is the flat-call equivalent of
        # ``ShellProxy(env).wrap_command(cmd)``; advertised in
        # ``src/devolaflow/shell_proxy/__init__.py::__all__`` for external
        # callers (the lifecycle hook ``pre_shell_call`` constructs a
        # ``ShellProxy`` instance directly because it needs the resolved
        # ``ShellProxyConfig`` snapshot for hook metadata, so it does not
        # use ``proxy_command``). External orchestrators that just need
        # a single rewrite call without retaining the config can use this.
        "devolaflow.shell_proxy.proxy:proxy_command",
        # ---- Adapter base API — subclassed/instantiated externally ----
        "devolaflow.adapters.base:BaseAdapter",
        "devolaflow.adapters.base:AdapterResult",
        "devolaflow.adapters.base:load_workflow_skill",
        # ---- Registry factories — entry points for external consumers ----
        "devolaflow.adapters.registry:create_default_registry",
        "devolaflow.plugins.loader:create_default_registry",
        # ---- CLI entry-point modules (also caught by name patterns) ----
        "devolaflow.build_skill:build_all",
        # ---- MIGRATION-v6.md recommended stable public API ----
        # The documented stable replacements for v6.0 removals. Allowlisted
        # even when an in-repo caller exists, so a future refactor that
        # drops the caller does not silently break the public contract.
        "devolaflow.gate.scorer:evaluate_gate",
        # v8.0.0 P-05 verification ladder — opt-in entry point exposed via
        # devolaflow.gate.__all__ for external L0/L1/L2 dispatchers that
        # want to short-circuit the 6-rung R1..R6 ladder. Activated when
        # ``profile.ladder_enabled=True`` (STRICT/AUDIT default); when
        # False the function delegates to evaluate_gate() byte-identically
        # (patch_plan §3 P-05 AC #3). Not yet wired into evaluate_gate
        # itself — orchestrator opt-in only at v8.0.0 cut.
        "devolaflow.gate.scorer:evaluate_ladder",
        # v8.0.0 P-10 acceptance-criteria auto-evaluator + verdict aggregator.
        # ``evaluate_acceptance_criteria_v2`` runs the new structured criteria
        # (canonical_order position 15, schema version 4) and emits per-criterion
        # :class:`AcceptanceCriterionVerdict` outcomes; ``aggregate_criterion_verdicts``
        # folds them into a :class:`CheckResult` for legacy
        # ``GateInput.acceptance_criteria_results`` integration. Both are
        # exposed via ``devolaflow.gate.__all__`` for external L0/L1/L2
        # orchestrators that opt in to ``acceptance_criteria_v2`` dispatch
        # field. NOT yet wired into ``evaluate_gate`` itself at the v8.0.0
        # cut — orchestrator opt-in only (R5: legacy ``acceptance_criteria:
        # list[str]`` alias remains the byte-identical default per
        # ``patch_plan §3 P-10``). Verified by
        # ``tests/test_ac_generator.py::TestEvaluateAcceptanceCriteriaV2``
        # and ``::TestAggregateCriterionVerdicts``.
        "devolaflow.gate.scorer:evaluate_acceptance_criteria_v2",
        "devolaflow.gate.scorer:aggregate_criterion_verdicts",
        # v8.0.0 P-10 ACGenerator — pure-Python pattern-matching synthesiser
        # for the new ``acceptance_criteria_v2`` dispatch field. Consumed by
        # external L0/L1/L2 orchestrators that opt in via
        # ``context_profiles.yaml#profiles.<name>.ac_generation.enabled=true``
        # (default ``false`` — opt-in per ``patch_plan §3 P-10``). Not wired
        # into any in-repo dispatch flow at the v8.0.0 cut; companion to
        # ``evaluate_acceptance_criteria_v2`` above. Verified by
        # ``tests/test_ac_generator.py::TestACGeneratorGenerate``.
        "devolaflow.ac_generator:ACGenerator",
        "devolaflow.gate.reinforcement:findings_to_reinforcement",
        "devolaflow.gate.reinforcement:merge_reinforcement_into_dispatch",
        "devolaflow.gate.reinforcement:reinforcement_to_dict",
        # v8.0.0 P-07 monotonic ratchet — convergence-loop bridge helpers.
        # Both are exposed via devolaflow.gate.__all__ for external L0/L1/L2
        # orchestrators that need to thread the new ratchet into their
        # convergence-round bookkeeping (per ``patch_plan §3 P-07``).
        # ``record_round_with_ratchet`` is the canonical way to append to
        # ``list[ConvergenceRound]`` AND record on ``MonotonicRatchet`` in
        # one call; ``detect_ratchet_escalation`` short-circuits the
        # stagnation path when the ratchet's most recent verdict is
        # ``ESCALATE``. Not yet wired into evaluate_gate / evaluate_ladder
        # at v8.0.0 cut — orchestrator opt-in only (matches the
        # evaluate_ladder allowlisting precedent above).
        "devolaflow.gate.convergence:record_round_with_ratchet",
        "devolaflow.gate.convergence:detect_ratchet_escalation",
        "devolaflow.task_adaptive_selector:apply_round_escalation",
        "devolaflow.task_adaptive_selector:apply_plan_mode_overrides",
        "devolaflow.task_adaptive_selector:select_context",
        # v8.0.0 P-07 apply_round_escalation refactor (NineS [CC-448821-0001]
        # closure). The three named helpers (``select_round_result`` /
        # ``apply_severity_filter`` / ``escalate_round``) are intentionally
        # public so external dispatchers can compose round-level overrides
        # piecemeal without re-running ``apply_round_escalation`` end-to-end.
        # Verified by ``tests/test_ratchet.py::TestApplyRoundEscalationRefactor``.
        "devolaflow.task_adaptive_selector:select_round_result",
        "devolaflow.task_adaptive_selector:apply_severity_filter",
        "devolaflow.task_adaptive_selector:escalate_round",
        "devolaflow.nines.advisor:get_research_advice",
        # ---- Compressor module — runtime lean format validators (CO-1) ----
        # Public API exported via module path; consumed by external workflow
        # agents and CI checks (validate dispatch/report compliance).
        "devolaflow.compressor:compress_message",
        "devolaflow.compressor:validate_lean_format",
        # v7.0.0 cache-layout invariant validators — consumed by external
        # workflow agents before sending lean dispatches; mandated by Rule P6
        # in .cursor/rules/devola-flow-rules.mdc and ADR v7-ADR-001.
        "devolaflow.compressor:assert_dispatch_layout",
        "devolaflow.compressor:compute_dispatch_lcp_pct",
        "devolaflow.compressor:DispatchLayoutError",
        # v7.0.1 tool-output truncation primitives — consumed by external
        # runtimes (L3 task agents producing StatusReports, L2 wave agents
        # composing predecessor context) per ADR-002 §2.1. The dataclass +
        # two helpers are opted in via context_profiles.yaml's per-profile
        # `tool_output_truncation:` block (default disabled at v7.0.1 cut).
        "devolaflow.compressor:truncate_tool_output",
        "devolaflow.compressor:clear_old_tool_uses",
        "devolaflow.compressor:ToolUseTruncation",
        # v7.0.2 hierarchical predecessor summariser primitives — consumed by
        # external dispatchers (L0/L1/L2) before composing pred[*].key_facts
        # (per ADR-003 §2.4 trigger threshold). The persistence probe planned
        # in v7.0.3 (ADR-004) re-uses extract_named_entities for entity
        # carry-through scoring.
        "devolaflow.compressor:summarise_predecessor",
        "devolaflow.compressor:extract_named_entities",
        # P-02 v7.2.4 envelope helpers — surface API for v7.3.x dispatcher
        # integration; not yet wired into compress_message but exported for
        # L0 dispatcher consumption per execution-protocol.md §8. The
        # helpers wrap predecessor key_facts and tool outputs in
        # <data channel="..."> ... </data> envelopes so L3 agents can
        # syntactically refuse imperatives that arrive via the data channel
        # (mitigation for arXiv:2604.02837v1 prompt-injection variants).
        "devolaflow.compressor:wrap_data_envelope",
        "devolaflow.compressor:unwrap_data_envelope",
        "devolaflow.compressor:detect_data_channel_instructions",
        # v8.0.0 P-02 directed compaction — Layer-3 of the layered compression
        # pipeline. Public API exported for L0/L1/L2 dispatchers that consume
        # `pred[*].compact_directive` (NESTED schema field added to
        # schemas/lean-dispatch.yaml in v8.0.0 P-02). The dispatcher consumer
        # calls directed_compact(text, focus_keywords, max_drop_pct=0.20)
        # on the predecessor's key_facts block before rendering the lean
        # dispatch payload. Not yet wired into compressor.compress_message
        # at v8.0.0 cut — opt-in via per-pred directive only (see
        # context_profiles.yaml#meta.recency_decay_factor for the
        # complementary Layer-2 overlay default of 0.9).
        "devolaflow.compressor:directed_compact",
        # ---- Self-improving feedback loop (S02-T08 §5) ----
        # Public class hierarchy exposed via devolaflow.feedback.*; documented
        # in SKILL.md (ProposalGenerator.generate_round_dispatch is wired in
        # feedback.py for v6.0.x convergence rounds, but the classes
        # themselves are entry points for external workflow agents).
        "devolaflow.feedback:Proposal",
        "devolaflow.feedback:FeedbackCollector",
        "devolaflow.feedback:FeedbackAnalyzer",
        "devolaflow.feedback:ProposalGenerator",
        # ---- Gate report generators ----
        # Exported via devolaflow.gate.__all__; consumed by external CI tools
        # and validate-gate console_script via direct module access.
        "devolaflow.gate.reporter:generate_yaml_report",
        "devolaflow.gate.reporter:generate_markdown_report",
        # ---- Operational learnings utilities ----
        # Exposed via devolaflow.learnings.*; called by self-update workflow
        # template (workflow-system/agent/templates/builtin/self-update.yaml)
        # and by external workflow agents for learnings management. v7.0.3
        # (ADR-005) adds consolidate_session / decay_confidence /
        # pin_learning_for_session — consumed by L1/L0 session-end hooks and
        # by dispatchers that need cross-round pinning. v7.2.0 (C-007 / CCT-3)
        # adds dedup_learnings — dormant in v7.2.0; promoted to a writer in
        # v7.3 via C-009 (reflective reflex) per the explicit two-phase plan.
        # v7.2.3 (P-03 / C-009) adds capture_session_reflection — the writer
        # that activates the dormant operational.jsonl substrate; called by
        # L1/L0 status-report consumers that persist L3 task-completion
        # reflections (read-side already wired via load_relevant_learnings).
        "devolaflow.learnings:prune_learnings",
        "devolaflow.learnings:promote_learning",
        "devolaflow.learnings:get_learnings_stats",
        "devolaflow.learnings:log_external_source_review",
        "devolaflow.learnings:consolidate_session",
        "devolaflow.learnings:decay_confidence",
        "devolaflow.learnings:pin_learning_for_session",
        "devolaflow.learnings:dedup_learnings",
        "devolaflow.learnings:capture_session_reflection",
        # ---- NineS subsystem — research, analysis, advisor APIs ----
        # All exported via devolaflow.nines.__all__ for external research
        # workflows; the NineS CLI integration is invoked by the user via
        # SI-2 (self-improve-iteration-rules.mdc) and not from in-repo
        # production code.
        "devolaflow.nines.commands:build_command",
        "devolaflow.nines.commands:build_stage_command",
        "devolaflow.nines.detector:ensure_nines",
        "devolaflow.nines.detector:get_nines_capabilities",
        "devolaflow.nines.researcher:NinesResearchConfig",
        "devolaflow.nines.researcher:collect_research",
        "devolaflow.nines.researcher:analyze_target",
        "devolaflow.nines.researcher:run_self_evaluation",
        "devolaflow.nines.researcher:run_skill_iteration",
        "devolaflow.nines.researcher:run_nines_benchmark",
        "devolaflow.nines.researcher:run_nines_update",
        "devolaflow.nines.researcher:run_self_improve_loop",
        "devolaflow.nines.researcher:refresh_reference_dependency",
        "devolaflow.nines.scorer:nines_dimension_scores",
        # ---- Agent workspace public API (v8.2.5 PV-05) ----
        # New in v8.3.0 PV-05 per .local/research/v8.3.0_design.md §1.1 + §4
        # and .local/research/v8.3.0_patch_plan.md §v8.2.5. The package
        # implements C-003 + M-005 (Python half) + M-006 closures from the
        # gap analysis. Production callers land in:
        #
        #   - v8.2.6 (`change-driven` workflow template) — invokes
        #     ChangeStore + ArchiveManager via the workflow runtime.
        #   - v8.2.7 (reporter module) — invokes serialize_delta_spec +
        #     ArchiveManager.propose_merge to render REPORT.md surfaces.
        #   - v8.2.8 (memory_bridge.py) — invokes ChangeStore + HandoffStore
        #     to hydrate change context for L0/L1/L2/L3 dispatch.
        #
        # Allowlisting these for v8.2.5 unblocks the patch ledger; the
        # production callers ship in subsequent PVs per the cycle plan.
        "devolaflow.agent_workspace.archive:ArchiveManager",
        "devolaflow.agent_workspace.delta_parser:serialize_delta_spec",
        "devolaflow.agent_workspace.handoff:HandoffStore",
        "devolaflow.agent_workspace.handoff:make_envelope",
        # ---- Memory bridge public API (v8.2.8 PV-08 — H-006 closure) ----
        # Per .local/research/v8.3.0_design.md §4 and
        # .local/research/v8.3.0_patch_plan.md §"v8.2.8 — Memory Bridge +
        # Change-Aware Learnings". The two functions exposed by
        # devolaflow.agent_workspace.memory_bridge are intentionally public
        # so the v8.2.9 /devola:archive command (and L0/L1/L2/L3 dispatch
        # context-injection in subsequent PVs of the v8.3.0 cycle) can
        # invoke them without reaching into the package internals.
        # Same allowlist pattern as the v8.2.5 PV-05 entries above —
        # production callers ship in subsequent PVs per the cycle plan.
        "devolaflow.agent_workspace.memory_bridge:consolidate_change_on_archive",
        "devolaflow.agent_workspace.memory_bridge:hydrate_change_context",
        # ---- Pre-decision phase API ----
        # Exposed via devolaflow.pre_decision.__all__; called by detect-repo-mode
        # console_script and external pre-flight workflow agents.
        "devolaflow.pre_decision.checklist:auto_detect",
        "devolaflow.pre_decision.freeze:freeze_config",
        "devolaflow.pre_decision.recommend:recommend_workflow",
        # ---- Template engine — composer, models, parser, registry ----
        # All exported via devolaflow.template_engine.__all__ for external
        # template authoring tools and the validate-template CLI.
        "devolaflow.template_engine.composer:collect_all_refs",
        "devolaflow.template_engine.models:JoinStrategy",
        "devolaflow.template_engine.models:OnExhaustion",
        "devolaflow.template_engine.models:GateFailAction",
        "devolaflow.template_engine.nines_bridge:nines_commands_to_dispatch_context",
        "devolaflow.template_engine.parser:parse_template_string",
        "devolaflow.template_engine.registry:TemplateRegistry",
        # ---- Runtime stage selector (P-04 in v7.4.9) ----
        # Per the v7.5.0 ghost-audit §3.G G-G1/G-G2/§3.I G-I2 closure design
        # and the P-04 dispatch directive, the runtime layer is intentionally
        # NOT wired into existing dispatch / compose / status flows in this
        # patch — integration with the L0/L1 plan generator is deferred per
        # audit §9 ("scope mode-skip strictly to dispatch composition ...
        # NOT to compressor input shape"). The public entry point is
        # advertised via ``devolaflow.template_engine.__all__`` and consumed
        # by external orchestrators (and ``tests/test_composer_runtime.py``,
        # ``tests/test_template_repo_init.py``) in lieu of an in-repo
        # production call site.
        "devolaflow.template_engine.runtime:select_stages_for_runtime",
        # ---- init_interview module (v7.7 — interview stage for repo-init) ----
        # Public API consumed by L3 task agents during the interview stage
        # of repo-init (mode=full). Not called from in-repo production code.
        "devolaflow.init_interview:detect_project_tools",
        "devolaflow.init_interview:suggest_skills",
        "devolaflow.init_interview:suggest_hooks",
        "devolaflow.init_interview:write_skill",
        "devolaflow.init_interview:generate_claude_hook_config",
        # ---- Learnings + compiler prefs (v7.7 memory system) ----
        "devolaflow.learnings:load_prefs",
        "devolaflow.local.compiler:compile_prefs",
        # ---- Session-state bridge (v8.2.0 PV-03) ----
        # Public migration helper that lazily constructs a populated
        # :class:`devolaflow.session.SessionState` from the JSONL substrate
        # without forcing an eager import (avoids circular import between
        # ``devolaflow.learnings`` and ``devolaflow.session.state``).
        # Consumed by L3 Task Agents and external orchestrators that opt
        # into the unified session model; not wired into in-repo
        # production at the v8.2.0 cut. Same allowlist pattern as
        # ``devolaflow.entropy_manager:cleanup`` above.
        "devolaflow.learnings:build_session_state_for",
        # ---- Entropy manager GC entrypoint (v8.0.0 P-11) ----
        # Public GC dispatcher exported via ``devolaflow.entropy_manager.__all__``
        # and consumed by L3 Task Agents executing the ``entropy-cleanup``
        # workflow template (``workflow-system/agent/templates/builtin/
        # entropy-cleanup.yaml``). Not yet wired into in-repo production at the
        # v8.0.0 cut — opt-in via the template's ``apply`` stage only. Same
        # allowlist pattern as v8.0.0 P-02 ``directed_compact`` above.
        "devolaflow.entropy_manager:cleanup",
        # ---- Token-budget breaker factory (v8.0.0 P-03) ----
        # Public factory exported via ``devolaflow.gate.__init__`` and
        # ``devolaflow.gate.budget.__all__``. Consumed by L3 Task Agents and
        # CLI tooling that resolves a profile name string into a
        # ``TokenBudgetBreaker`` (mirrors the policy in
        # ``devolaflow.gate.scorer.run_gate_cli``). Direct construction via
        # ``TokenBudgetBreaker(profile=PROFILES[name])`` is the in-repo
        # call-site at the v8.0.0 cut; the factory is the user-facing
        # ergonomic API. Same allowlist pattern as v8.0.0 P-11 above.
        "devolaflow.gate.budget:from_profile_name",
        # ---- Progressive merge (v7.7 — diff-suggest for existing files) ----
        "devolaflow.local.merge:propose_merge",
        "devolaflow.local.merge:apply_merge",
        "devolaflow.local.merge:format_diff_for_review",
        # ---- NineS internal helper exposed in private _cli module ----
        # Public name (no underscore) inside private module; documented in
        # CHANGELOG v5.x as a public helper for callers needing nines.toml
        # auto-discovery before invoking run_nines_cli(config_path=...).
        "devolaflow.nines._cli:find_nines_config",
        # ---- v8.2.1 runtime plugin auto-install (H-001 / design.md §6) ----
        # Entry points of the new runtime plugin surface. They are consumed
        # declaratively by workflow YAML precondition stages
        # (``workflow-system/agent/templates/builtin/nines-assisted.yaml``
        # and ``product-verification.yaml`` now both start with a
        # ``config.ensure_plugins: [...]`` stage per PV-01) and invoked
        # externally by the workflow runner. A production Python caller
        # lands in v8.2.6 when the ``change-driven`` template wires
        # ``ensure_plugins`` config into dispatch — allowlisted here until
        # that caller exists, matching the same pattern used by the
        # lifecycle hooks block at the top of this allowlist (P-05 v7.4.8).
        # Verified by ``tests/test_plugins.py`` TestEnsurePluginFailureModes
        # (8 failure-mode scenarios per design.md §6.5) + TestEnsurePluginNpmBackend
        # (ui-pro 2-step install) + smoke test against /home/agent/workspace/NineS.
        "devolaflow.plugins.installer:ensure_plugin",
        "devolaflow.plugins.installer:load_registry",
        "devolaflow.plugins.installer:resolve_plugin",
        "devolaflow.plugins.installer:RuntimePluginSpec",
        # ---- v9.0.0 PV-06 (v8.5.1) — CompressionPipeline unification ----
        # The CompressionStage protocol + CompressionPipeline orchestrator
        # ship as the canonical composition layer for the 6 pre-existing
        # text-side transforms. The 5 stage-factory entry points
        # (compression_pipeline_stages in compressor.py;
        # compression_pipeline_stage in shell_proxy.commands +
        # llm_client) wrap the existing functions for the unified
        # pipeline; production callers (L0/L1 dispatchers using
        # ``CompressionPipeline.run`` directly) ship in v9.x cycle PVs
        # per .local/research/adr/v9-ADR-006-compression-pipeline-and-b3-flip.md
        # §"Migration". Allowlisted here until the dispatcher integration
        # PV lands — matches the pattern used for v8.2.5 ChangeStore +
        # v8.2.8 memory_bridge entries above. Tests exercise every entry
        # point (tests/test_compression_pipeline.py).
        "devolaflow.compression_pipeline:BYPASS_ALWAYS",
        "devolaflow.compressor:compression_pipeline_stages",
        "devolaflow.shell_proxy.commands:compression_pipeline_stage",
        "devolaflow.llm_client:compression_pipeline_stage",
        # ---- v9.0.0 PV-06 (v8.5.1) — Theme T5 5-primitive default-on
        # flip helper functions ----
        # The 5 ``is_<primitive>_active(profile, env)`` helpers combine
        # the GateProfile flag (post-flip True for STRICT/AUDIT) with the
        # corresponding R5 strict env-flag override (``DEVOLAFLOW_<NAME>``
        # set EXACTLY ``"0"`` opts out, EXACTLY ``"1"`` forces on). They
        # are the canonical "should this primitive run" predicate that
        # downstream orchestrators consult before instantiating
        # TokenBudgetBreaker / MonotonicRatchet / ComplexityDetector /
        # ACGenerator / evaluate_ladder. Production callers (L0/L1/L2/L3
        # gate-evaluation orchestrators) ship in subsequent v9.x PVs per
        # the cycle plan (Theme T5 closure). Allowlisted here until those
        # callers exist — verified by tests/test_pv06_primitive_flip.py
        # which exercises all 5 helpers' R5 strict opt-out / opt-in /
        # loose-value-rejection contract.
        "devolaflow.gate.budget:is_token_budget_breaker_active",
        "devolaflow.gate.scorer:is_verification_ladder_active",
        "devolaflow.gate.ratchet:is_gate_ratchet_active",
        "devolaflow.gate.complexity_detector:is_complexity_detector_active",
        "devolaflow.ac_generator:is_ac_generator_active",
    }
)


# A-5 — Single-Source-of-Truth Registry Pattern (.rules/architecture.mdc).
# These qualified names denote the Python-backed domain-SSOT registries that
# currently ship in DevolaFlow (v8.4.3 baseline). Each one HAS in-repo
# production callers in the owner module's siblings (e.g. ``WHITELIST`` is
# consumed by ``shell_proxy.proxy`` + ``lifecycle.pre_shell_call``), so they
# are NOT eligible for ``DEFAULT_ALLOWLIST``. The two YAML-backed registries
# (``plugins.yaml`` + ``runtime-plugins.yaml``) have no Python symbol to
# guard at this layer; they are guarded by file-path uniqueness in
# ``tests/test_no_ghost_features.py::test_registry_single_owner``.
SSOT_REGISTRY_QUALIFIED_NAMES: frozenset[str] = frozenset(
    {
        "devolaflow.shell_proxy.registry:WHITELIST",
        "devolaflow.memory_router.cache:MemoryCase",
        "devolaflow.shell_proxy.commands:CommandMapping",
    }
)


def _check_allowlist_domain_overlap(
    allowlist: Iterable[str],
    registry_names: Iterable[str] = SSOT_REGISTRY_QUALIFIED_NAMES,
) -> set[str]:
    """Return the set of ``allowlist`` entries that name a domain-SSOT registry.

    Per Architecture Rule A-5 (`.rules/architecture.mdc` §A-5.2), a
    domain-SSOT registry symbol MUST NOT appear in ``DEFAULT_ALLOWLIST``
    because, by definition, such symbols ARE consumed in-repo by their
    owner module's siblings. An overlap means either the allowlist entry
    is stale OR the registry surface lost its only caller — both warrant
    operator attention.

    The empty-set return value is the success signal; a non-empty return
    enumerates the offending qualified names so the caller (the script
    import-time guard + ``tests/test_dead_apis.py``) can format a precise
    error message.
    """
    return set(allowlist) & set(registry_names)


# A-5.2 — script-import-time strict guard. Importing the module evaluates
# this assertion immediately so a stale or accidentally-added domain-SSOT
# entry surfaces as an ``AssertionError`` at the first import (under
# pytest, this fails the whole ``tests/test_dead_apis.py`` module load
# with a clear A-5 message; under direct CLI invocation, the script
# refuses to start). Per Soul Rule S-5 (No Silent Failures), the guard
# never swallows the violation.
_DEFAULT_ALLOWLIST_OVERLAP = _check_allowlist_domain_overlap(DEFAULT_ALLOWLIST)
if _DEFAULT_ALLOWLIST_OVERLAP:
    raise AssertionError(
        "A-5 violation: DEFAULT_ALLOWLIST contains domain-SSOT registry "
        f"symbol(s) {sorted(_DEFAULT_ALLOWLIST_OVERLAP)}; per "
        ".rules/architecture.mdc::A-5.2 these names denote SSOT registries "
        "with in-repo production callers and must not be allowlisted as "
        "'no production caller'. Remove them from DEFAULT_ALLOWLIST."
    )


@dataclass(frozen=True)
class PublicSymbol:
    """A public function or class definition discovered at module level."""

    name: str
    kind: str
    module: str
    file: Path
    lineno: int

    @property
    def qualified(self) -> str:
        """Return the ``module:name`` identifier used by the allowlist."""
        return f"{self.module}:{self.name}"

    def to_dict(self, root: Path | None = None) -> dict[str, object]:
        """Return a JSON-serialisable representation."""
        path_str = str(self.file)
        if root is not None:
            try:
                path_str = str(self.file.relative_to(root))
            except ValueError:
                path_str = str(self.file)
        return {
            "name": self.name,
            "kind": self.kind,
            "module": self.module,
            "qualified": self.qualified,
            "file": path_str,
            "lineno": self.lineno,
        }


@dataclass(frozen=True)
class DeadSymbol:
    """A public symbol with zero non-test, non-self callers."""

    symbol: PublicSymbol
    reason: str = "no caller in src/scripts/benchmarks (excluding the defining file)"
    callers: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self, root: Path | None = None) -> dict[str, object]:
        """Return a JSON-serialisable representation."""
        return {
            "symbol": self.symbol.to_dict(root),
            "reason": self.reason,
            "callers": list(self.callers),
        }


def _module_for(file: Path, src_root: Path) -> str:
    """Convert ``src/devolaflow/foo/bar.py`` -> ``devolaflow.foo.bar``."""
    rel = file.resolve().relative_to(src_root.resolve())
    parts = list(rel.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _iter_python_files(root: Path) -> Iterable[Path]:
    """Yield all ``*.py`` files under *root*, skipping caches."""
    for f in sorted(root.rglob("*.py")):
        if any(p == "__pycache__" or p.startswith(".") for p in f.parts):
            continue
        yield f


def _is_cli_entry(name: str) -> bool:
    """Return True when *name* matches a CLI entry-point convention."""
    return name in CLI_ENTRY_NAMES or name.endswith(CLI_ENTRY_SUFFIX)


def collect_public_symbols(src_root: Path) -> list[PublicSymbol]:
    """Return every public top-level ``def``/``class`` under *src_root*.

    *src_root* is the directory whose top-level package directories we want
    to scan (e.g. ``src/`` for the ``devolaflow`` package).
    """
    symbols: list[PublicSymbol] = []
    if not src_root.exists():
        return symbols
    for f in _iter_python_files(src_root):
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except (SyntaxError, ValueError, OSError):
            continue
        try:
            module = _module_for(f, src_root)
        except ValueError:
            continue
        for node in tree.body:
            name = getattr(node, "name", None)
            if not isinstance(name, str):
                continue
            if name.startswith("_") or _is_cli_entry(name):
                continue
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                kind = "function"
            elif isinstance(node, ast.ClassDef):
                kind = "class"
            else:
                continue
            symbols.append(
                PublicSymbol(
                    name=name,
                    kind=kind,
                    module=module,
                    file=f.resolve(),
                    lineno=node.lineno,
                )
            )
    return symbols


def _collect_real_uses(file: Path) -> set[str]:
    """Return all symbol names *file* references outside of import statements.

    A "real use" is any ``ast.Name`` or ``ast.Attribute`` reference that is
    not a child of an ``ast.Import`` or ``ast.ImportFrom`` node. This excludes
    pure re-exports such as ``from .foo import bar`` in ``__init__.py``.
    """
    try:
        tree = ast.parse(file.read_text(encoding="utf-8"))
    except (SyntaxError, ValueError, OSError):
        return set()

    used: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        if isinstance(node, ast.Name):
            used.add(node.id)
        elif isinstance(node, ast.Attribute):
            used.add(node.attr)
    return used


def find_dead_apis(
    src_dirs: Iterable[Path],
    test_dirs: Iterable[Path] = (),
    other_caller_dirs: Iterable[Path] = (),
    allowlist: Iterable[str] = DEFAULT_ALLOWLIST,
) -> list[DeadSymbol]:
    """Return public symbols with zero references in production files.

    "Production files" = ``src_dirs`` plus ``other_caller_dirs`` (typically
    ``scripts/`` and ``benchmarks/``), excluding everything under
    ``test_dirs``. The defining file itself IS scanned; the ``def``/``class``
    statement that creates a symbol does not produce a ``Name`` node, so any
    other reference (instantiation, recursive call, decorator) keeps the
    symbol alive. The dead-wire bug pattern was a function with literally
    zero production references — exactly what this detects.

    Parameters
    ----------
    src_dirs:
        Directories whose ``*.py`` files define the public symbols (e.g.
        ``[Path("src")]``).
    test_dirs:
        Directories that are EXCLUDED from the caller search. Tests do not
        count as production callers — that is the bug class we are catching.
    other_caller_dirs:
        Additional directories to include in the caller search, typically
        ``scripts/`` and ``benchmarks/``.
    allowlist:
        Iterable of ``"module.path:Name"`` strings for symbols that are
        intentionally external-only public API and must never be flagged.
    """
    src_dirs_list = [Path(p) for p in src_dirs]
    test_dirs_list = [Path(p) for p in test_dirs]
    other_caller_list = [Path(p) for p in other_caller_dirs]
    allowed = set(allowlist)

    all_symbols: list[PublicSymbol] = []
    for sd in src_dirs_list:
        all_symbols.extend(collect_public_symbols(sd))

    test_files: set[Path] = set()
    for td in test_dirs_list:
        if td.exists():
            test_files.update(p.resolve() for p in _iter_python_files(td))

    caller_files: list[Path] = []
    for d in src_dirs_list + other_caller_list:
        if not d.exists():
            continue
        caller_files.extend(p.resolve() for p in _iter_python_files(d))
    caller_files = [f for f in caller_files if f not in test_files]

    file_uses: dict[Path, set[str]] = {f: _collect_real_uses(f) for f in caller_files}

    dead: list[DeadSymbol] = []
    for sym in all_symbols:
        if sym.qualified in allowed:
            continue
        has_caller = any(sym.name in names for names in file_uses.values())
        if not has_caller:
            dead.append(DeadSymbol(symbol=sym, callers=()))
    return dead


def _format_text(dead: list[DeadSymbol], root: Path) -> str:
    """Return a human-readable report grouped by file."""
    if not dead:
        return "OK: 0 dead public APIs detected.\n"

    by_file: dict[str, list[DeadSymbol]] = {}
    for d in dead:
        try:
            key = str(d.symbol.file.relative_to(root))
        except ValueError:
            key = str(d.symbol.file)
        by_file.setdefault(key, []).append(d)

    lines: list[str] = [f"FAIL: {len(dead)} dead public API(s) detected.\n"]
    for path in sorted(by_file):
        lines.append(f"\n  {path}")
        for d in by_file[path]:
            lines.append(f"    L{d.symbol.lineno:>4}  {d.symbol.kind:<8} {d.symbol.qualified}")
    lines.append(
        "\nFix options:\n"
        "  1. Wire the symbol into a real production caller.\n"
        "  2. Mark it private (rename with leading underscore).\n"
        "  3. Add it to DEFAULT_ALLOWLIST in scripts/detect_dead_apis.py "
        "with a comment explaining why.\n"
    )
    return "\n".join(lines)


def _format_json(dead: list[DeadSymbol], root: Path) -> str:
    """Return a JSON report suitable for programmatic consumption."""
    return json.dumps(
        {
            "dead_count": len(dead),
            "dead": [d.to_dict(root) for d in dead],
        },
        indent=2,
    )


def _resolve_repo_root(start: Path) -> Path:
    """Walk upward from *start* to find the repo root (contains ``pyproject.toml``)."""
    p = start.resolve()
    while p != p.parent:
        if (p / "pyproject.toml").exists():
            return p
        p = p.parent
    return start.resolve()


def main(argv: list[str] | None = None) -> int:
    """CLI entry — return the process exit code."""
    parser = argparse.ArgumentParser(
        description="Detect public APIs in src/devolaflow with no production callers.",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with code 2 if any dead APIs are found (for CI use).",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Repository root (default: auto-detect via pyproject.toml)",
    )
    args = parser.parse_args(argv)

    root = args.root.resolve() if args.root else _resolve_repo_root(Path(__file__).parent)

    src_dirs = [root / "src"]
    test_dirs = [root / "tests"]
    other_dirs = [root / "scripts", root / "benchmarks"]

    dead = find_dead_apis(
        src_dirs=src_dirs,
        test_dirs=test_dirs,
        other_caller_dirs=other_dirs,
        allowlist=DEFAULT_ALLOWLIST,
    )

    if args.format == "json":
        print(_format_json(dead, root))
    else:
        print(_format_text(dead, root))

    if args.strict and dead:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
