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


# v17.0.0 R1 audit (G17-A6): purged 48 stale entries whose symbols gained
# in-repo production callers; see docs/cycle-archive for history.
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
        "devolaflow.agents_md_slice:count_agents_md_rules",
        # v10.2.0 PV-01 (D-P-3 closure) — read_installed_si_chip_version is
        # invoked by the si-chip entry's `version_check_cmd` in
        # `workflow-system/agent/knowledge/runtime-plugins.yaml`, which
        # `devolaflow.plugins.installer._probe_version` executes as a
        # `python -c "..."` subprocess. The dead-API detector only sees
        # Python AST callers; the yaml-embedded subprocess invocation
        # does NOT register as a caller. Allowlisted with this comment
        # so the D-P-3 closure (read frontmatter `version:` instead of
        # echoing hardcoded `0.4.0`) stays pinned. NOT a domain-SSOT
        # registry symbol per A-5.2 — pure read-only YAML-frontmatter
        # parser.
        "devolaflow.si_chip_bridge.install_resolver:read_installed_si_chip_version",
        # Track C-3 D-11 (full_review_and_improve) — the tri-state marker
        # protocol for the backgrounded `codegraph init`. The writers +
        # reader are invoked at WORKFLOW RUNTIME: the repo-init scaffold
        # step (`repo-init.yaml::codegraph_init`, `execution: background`)
        # and downstream analyze consumers call them via agent-side
        # `python -c "..."` subprocesses, which the AST walk cannot see —
        # same shape as `read_installed_si_chip_version` above. Behaviour
        # pinned by tests/test_codegraph_markers.py; the
        # W-18 stanza is
        # tests/ghost/test_features_v15_0.py::test_v15_0_x_codegraph_backgrounding_registered.
        # NOT domain-SSOT registry symbols per A-5.2 — pure marker-file
        # IO helpers with no registration data.
        "devolaflow.codegraph.markers:mark_indexing",
        "devolaflow.codegraph.markers:mark_ready",
        "devolaflow.codegraph.markers:mark_failed",
        "devolaflow.codegraph.markers:read_marker_state",
        # v10.2.1 PV-02 (D-S-2 closure) — dispatch_dogfood_cycle is the
        # public L0/L1 wrapper that exposes the persistent BasicAbility
        # optimisation factory at the workflow-stage surface. v10.2.1
        # ships the integration surface; the actual workflow-template
        # wiring (`skill-optimization` / `self-update` / `nines-assisted`
        # templates calling the wrapper from a stage handler) lands in
        # PV-04 / PV-05 self-iteration rounds. Dogfood pass #1 in PV-02
        # is the first non-mocked invocation evidence. NOT a domain-SSOT
        # registry symbol per A-5.2 — pure delegation wrapper around
        # `devolaflow.si_chip_bridge.runner.run_dogfood_cycle` with no
        # registration data of its own.
        "devolaflow.dispatch:dispatch_dogfood_cycle",
        # ---- Lifecycle hooks public API (P-05 in v7.4.8) ----
        # ``clear_hooks`` and ``registered_events`` are test-harness /
        # introspection helpers with no production caller by design:
        # test fixtures reset handler state via ``clear_hooks``, and
        # external orchestrators enumerate the wired event set via
        # ``registered_events``. Their siblings ``run_hooks`` /
        # ``register_hook`` gained in-repo production callers when S-10
        # wired the hook chain into every dispatch, and were purged in
        # the v17.0.0 R1 audit.
        "devolaflow.lifecycle.dispatcher:clear_hooks",
        "devolaflow.lifecycle.dispatcher:registered_events",
        # v12.4.0 PV-05 (D-4 L0-only surfaces hardening) —
        # ``register_pre_dispatch_extra`` is the OPT-IN registration
        # helper for the ``reject_subagent_banner_emission`` hook. The
        # hook is deliberately NOT auto-wired in lifecycle/__init__.py
        # (unlike the v12.2.0 PV-04 ``reject_subagent_quality_score``
        # default-extra) to preserve the S-10 byte-id contract for
        # v12.3.0 callers — operators opt in by calling this helper at
        # process startup. Consumed by
        # ``tests/test_lifecycle_reject_subagent_banner_emission.py``
        # (the ``opt_in_registered`` fixture). NOT a domain-SSOT registry
        # symbol per A-5.2 — pure module-level wrapper around
        # ``register_hook(EVENT, reject_subagent_banner_emission)``.
        "devolaflow.lifecycle.reject_subagent_banner_emission:register_pre_dispatch_extra",
        # v12.5.0 PV-05 D-3 closure — ``strip_l0_only_metadata`` is the
        # auto-strip companion to the v12.4.0 PV-05
        # ``reject_subagent_banner_emission`` detect-only hook. Pure
        # function: deep-copies the envelope, removes banner literals +
        # quality_score keys, returns the cleaned envelope. NEVER touches
        # disk (S-9 append-only handoff envelopes are written by
        # callers); idempotent; permissive on absent keys; logs WARN via
        # logging.getLogger(__name__) on malformed input per S-5. The
        # in-repo "production caller" is the operator opt-in path —
        # external orchestrators invoke this BEFORE writing handoff
        # envelopes to ``.local/.agent/handoff/``. Consumed by
        # ``tests/test_handoff_strip_metadata.py``. NOT a domain-SSOT
        # registry symbol per A-5.2 — pure transformation helper.
        "devolaflow.agent_workspace.handoff:strip_l0_only_metadata",
        # v12.5.0 PV-03 D-1.1 closure — codegraph researcher Python
        # wrapper. The 5 helpers are the L2-task-agent surface for
        # invoking codegraph CLI (the 9 MCP tools wrapped as Python
        # subprocess calls). Each wraps a distinct codegraph CLI
        # subcommand: ``build_context`` → ``codegraph context``,
        # ``search_symbols`` → ``codegraph search``, ``get_impact`` →
        # ``codegraph impact``, ``get_callers`` → ``codegraph callers``,
        # ``get_affected_tests`` → ``codegraph affected``. The Python
        # wrapper IS the canonical entry surface for L2 agents per the
        # A-5 SSOT registry pattern; the in-repo "production caller" is
        # the L2 task agent invocation contract documented in
        # ``workflow-system/agent/references/codegraph.md``.
        # NOT domain-SSOT registry symbols per A-5.2 — pure subprocess
        # wrappers with no registration data.
        "devolaflow.codegraph.researcher:build_context",
        "devolaflow.codegraph.researcher:search_symbols",
        "devolaflow.codegraph.researcher:get_impact",
        "devolaflow.codegraph.researcher:get_callers",
        "devolaflow.codegraph.researcher:get_affected_tests",
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
        # v8.0.0 P-05 verification ladder — opt-in entry point exposed via
        # devolaflow.gate.__all__ for external L0/L1/L2 dispatchers that
        # want to short-circuit the 6-rung R1..R6 ladder. Activated when
        # ``profile.ladder_enabled=True`` (STRICT/AUDIT default); when
        # False the function delegates to evaluate_gate() byte-identically
        # (patch_plan §3 P-05 AC #3). Not yet wired into evaluate_gate
        # itself — orchestrator opt-in only at v8.0.0 cut.
        "devolaflow.gate.ladder:evaluate_ladder",
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
        "devolaflow.gate.acceptance_v2:evaluate_acceptance_criteria_v2",
        "devolaflow.gate.acceptance_v2:aggregate_criterion_verdicts",
        # v8.0.0 P-10 ACGenerator — pure-Python pattern-matching synthesiser
        # for the new ``acceptance_criteria_v2`` dispatch field. Consumed by
        # external L0/L1/L2 orchestrators that opt in via
        # ``context_profiles.yaml#profiles.<name>.ac_generation.enabled=true``
        # (default ``false`` — opt-in per ``patch_plan §3 P-10``). Not wired
        # into any in-repo dispatch flow at the v8.0.0 cut; companion to
        # ``evaluate_acceptance_criteria_v2`` above. Verified by
        # ``tests/test_ac_generator.py::TestACGeneratorGenerate``.
        "devolaflow.ac_generator:ACGenerator",
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
        # ---- Compressor module — runtime lean format validators (CO-1) ----
        # Public APIs remain exported from ``devolaflow.compressor`` for
        # callers, but their definitions moved to ``compressor.transforms``
        # in the package split. External workflow agents and CI checks use
        # them to compress messages and validate dispatch/report compliance.
        # NOT domain-SSOT registry symbols per A-5.2 — both are stateless
        # transformations with no registration data.
        "devolaflow.compressor.transforms:compress_message",
        "devolaflow.compressor.transforms:validate_lean_format",
        # ---- Self-improving feedback loop (S02-T08 §5) ----
        # Public class hierarchy exposed via devolaflow.feedback.*; documented
        # in SKILL.md (ProposalGenerator.generate_round_dispatch is wired in
        # feedback.py for v6.0.x convergence rounds, but the classes
        # themselves are entry points for external workflow agents).
        "devolaflow.feedback:Proposal",
        "devolaflow.feedback:FeedbackCollector",
        "devolaflow.feedback:FeedbackAnalyzer",
        "devolaflow.feedback:ProposalGenerator",
        # v9.7.0 PV-03 — auto-wired L1-wave async dispatch entry point.
        # Wraps the v9.3.0 PV-05 ``AsyncDispatchExecutor`` (also a public
        # API surface that's pinned via ``_dispatch_executor_dead_api_pins``
        # in ``src/devolaflow/agent_workspace/__init__.py``). This is the
        # canonical caller for L1 Wave dispatchers in repos that opt into
        # the Python-driven dispatch path; LLM-orchestrated workflows
        # invoke the Task tool directly without going through this helper,
        # so the in-repo "production caller" IS the ``Task`` tool surface
        # exposed via the SKILL.md dispatch contract. Documented in
        # ``workflow-system/agent/references/execution-protocol.md`` §13.
        "devolaflow.dispatch:dispatch_wave_tasks",
        # v9.7.0 PV-04 — opt-in selector LRU cache pre-warmup. Activated
        # by ``DEVOLAFLOW_WARMUP=1`` per W-20 §3 orthogonality test (no
        # existing flag activates this surface). The function is a
        # session-start hook for operators who opt in; the in-repo
        # "production caller" is ``__main__`` of the
        # ``task_adaptive_selector`` CLI when run with the env flag set,
        # NOT a sibling module call. Documented in
        # ``workflow-system/agent/references/env-flags.md`` §2.15 +
        # ``.local/research/v9.7.0_perf_research.md`` §4.
        "devolaflow.task_adaptive_selector:warmup_selector_cache",
        # ---- Gate report generators ----
        # Exported via devolaflow.gate.__all__; consumed by external CI tools
        # and validate-gate console_script via direct module access.
        "devolaflow.gate.reporter:generate_yaml_report",
        "devolaflow.gate.reporter:generate_markdown_report",
        # ---- Operational learnings utilities ----
        # Exposed via devolaflow.learnings.*; called by self-update workflow
        # template (workflow-system/agent/templates/builtin/self-update.yaml)
        # and by external workflow agents for learnings management. v7.0.3
        # (ADR-005) adds decay_confidence / pin_learning_for_session —
        # consumed by L1/L0 session-end hooks and by dispatchers that need
        # cross-round pinning. v7.2.3 (P-03 / C-009) adds
        # capture_session_reflection — the writer that activates the dormant
        # operational.jsonl substrate; called by L1/L0 status-report
        # consumers that persist L2 task-completion reflections (read-side
        # already wired via load_relevant_learnings). The siblings
        # consolidate_session / dedup_learnings gained in-repo production
        # callers and were purged in the v17.0.0 R1 audit.
        "devolaflow.learnings:prune_learnings",
        "devolaflow.learnings:promote_learning",
        "devolaflow.learnings:get_learnings_stats",
        "devolaflow.learnings:log_external_source_review",
        "devolaflow.learnings:decay_confidence",
        "devolaflow.learnings:pin_learning_for_session",
        "devolaflow.learnings:capture_session_reflection",
        # ---- Agent workspace public API (v8.2.5 PV-05) ----
        # `serialize_delta_spec` renders a delta-spec structure back to the
        # per-change spec.md DELTA format (A-4). It remains external-facing:
        # REPORT.md rendering tools and external orchestrators consume it,
        # with no in-repo production call site. The sibling v8.2.5 entries
        # (ArchiveManager / HandoffStore / make_envelope) gained in-repo
        # production callers in later cycles and were purged in the
        # v17.0.0 R1 audit.
        "devolaflow.agent_workspace.delta_parser:serialize_delta_spec",
        # ---- Memory bridge public API (v8.2.8 PV-08 — H-006 closure) ----
        # Per .local/research/v8.3.0_design.md §4 and
        # .local/research/v8.3.0_patch_plan.md §"v8.2.8 — Memory Bridge +
        # Change-Aware Learnings". The two functions exposed by
        # devolaflow.agent_workspace.memory_bridge are intentionally public
        # so the v8.2.9 /devola:archive command (and L0/L1/L2 dispatch
        # context-injection in subsequent PVs of the v8.3.0 cycle) can
        # invoke them without reaching into the package internals.
        # Same allowlist pattern as the v8.2.5 PV-05 entries above —
        # production callers ship in subsequent PVs per the cycle plan.
        "devolaflow.agent_workspace.memory_bridge:consolidate_change_on_archive",
        "devolaflow.agent_workspace.memory_bridge:hydrate_change_context",
        # ---- Pre-decision phase API ----
        # Exposed via devolaflow.pre_decision.__all__; called by detect-repo-mode
        # console_script and external pre-flight workflow agents.
        "devolaflow.pre_decision.freeze:freeze_config",
        "devolaflow.pre_decision.recommend:recommend_workflow",
        # ---- Template engine — composer, models, parser, registry ----
        # All exported via devolaflow.template_engine.__all__ for external
        # template authoring tools and the validate-template CLI.
        "devolaflow.template_engine.composer:collect_all_refs",
        "devolaflow.template_engine.models:JoinStrategy",
        "devolaflow.template_engine.models:OnExhaustion",
        "devolaflow.template_engine.models:GateFailAction",
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
        # Public API consumed by L2 task agents during the interview stage
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
        # Consumed by L2 Task Agents and external orchestrators that opt
        # into the unified session model; not wired into in-repo
        # production at the v8.2.0 cut. Same allowlist pattern as
        # ``devolaflow.entropy_manager:cleanup`` above.
        "devolaflow.learnings:build_session_state_for",
        # ---- Entropy manager GC entrypoint (v8.0.0 P-11) ----
        # Public GC dispatcher exported via ``devolaflow.entropy_manager.__all__``
        # and consumed by L2 Task Agents executing the ``entropy-cleanup``
        # workflow template (``workflow-system/agent/templates/builtin/
        # entropy-cleanup.yaml``). Not yet wired into in-repo production at the
        # v8.0.0 cut — opt-in via the template's ``apply`` stage only. Same
        # allowlist pattern as v8.0.0 P-02 ``directed_compact`` above.
        "devolaflow.entropy_manager:cleanup",
        # ---- Token-budget breaker factory (v8.0.0 P-03) ----
        # Public factory exported via ``devolaflow.gate.__init__`` and
        # ``devolaflow.gate.budget.__all__``. Consumed by L2 Task Agents and
        # CLI tooling that resolves a profile name string into a
        # ``TokenBudgetBreaker`` (mirrors the policy in
        # ``devolaflow.gate.scorer.run_gate_cli``). Direct construction via
        # ``TokenBudgetBreaker(profile=PROFILES[name])`` is the in-repo
        # call-site at the v8.0.0 cut; the factory is the user-facing
        # ergonomic API. Same allowlist pattern as v8.0.0 P-11 above.
        "devolaflow.gate.budget:from_profile_name",
        # ---- Progressive merge (v7.7 — diff-suggest for existing files) ----
        "devolaflow.local.merge:apply_merge",
        "devolaflow.local.merge:format_diff_for_review",
        # ---- v9.0.0 PV-06 (v8.5.1) — CompressionPipeline stage factories ----
        # The two surviving stage-factory entry points wrap the shell-proxy
        # command-mapping and llm_client transforms for the unified
        # CompressionPipeline; external L0/L1 dispatchers compose them via
        # ``CompressionPipeline.run`` per
        # docs/cycle-archive/adr/v9-ADR-006-compression-pipeline-and-b3-flip.md
        # §"Migration" — no in-repo production call site. Tests exercise
        # both entry points (tests/test_compression_pipeline.py). The
        # siblings ``compression_pipeline_stages`` / ``BYPASS_ALWAYS``
        # gained in-repo production callers and were purged in the
        # v17.0.0 R1 audit.
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
        # ACGenerator / evaluate_ladder. Production callers (L0/L1/L2
        # gate-evaluation orchestrators) ship in subsequent v9.x PVs per
        # the cycle plan (Theme T5 closure). Allowlisted here until those
        # callers exist — verified by tests/test_pv06_primitive_flip.py
        # which exercises all 5 helpers' R5 strict opt-out / opt-in /
        # loose-value-rejection contract.
        "devolaflow.gate.budget:is_token_budget_breaker_active",
        "devolaflow.gate.ladder:is_verification_ladder_active",
        "devolaflow.gate.ratchet:is_gate_ratchet_active",
        "devolaflow.gate.complexity_detector:is_complexity_detector_active",
        "devolaflow.ac_generator:is_ac_generator_active",
        # ---- v9.1.1 PV-01 (cycle v9.2.0) — workspace_context discovery API ----
        # `scan_workspace(repo_root) -> WorkspaceContext` is the pure-function
        # discovery API for `.local/` + `.local/.agent/` + `.rules/` surfaces
        # in a consumer repo. SKILL.md §"Workspace Engagement (Read at Session
        # Start)" instructs L0 to call it at session start; the prompt-side
        # consumer is the dispatcher itself, not an in-repo Python module.
        # The first in-repo Python production caller lands in v9.1.4 PV-04
        # (memory_router.consult_for_dispatch + plan-mode feedback ingestion
        # per the v9.2.0 cycle plan §PV-04); v9.1.1 PV-01 ships the
        # discovery API only as the prerequisite. NOT a domain-SSOT registry
        # symbol per A-5.2 — pure read-only filesystem-walk helper following
        # the established forward-looking allowlist pattern (public surface
        # advertised in SKILL.md, in-repo caller lands
        # in a subsequent PV per the cycle plan). Verified by
        # `tests/test_workspace_context_scan.py` (6 tests covering
        # presence/detection/sort/freeze contract) +
        # `tests/test_no_ghost_features.py::test_v9_1_1_new_symbols_have_coverage`
        # (W-18 ghost-audit refresh: presence + import-smoke + frozen
        # dataclass invariant).
        "devolaflow.workspace_context:scan_workspace",
        # ---- v9.1.2 PV-02 (cycle v9.2.0) — change-driven activation skill ----
        # `classify_complexity(files_count, loc_estimate, is_cross_cutting=False)
        # -> Complexity` and `activation_verdict(complexity, env_agent_workspace,
        # opt_out=False) -> ActivationVerdict` and `from_env(env=None) -> bool`
        # are the public heuristic surface that Architecture rule A-6
        # ("Workspace Engagement Auto-Activation" per `.rules/architecture.mdc`)
        # cites. SKILL.md §"When to engage `change-driven` (Rule A-6)" instructs
        # L0 to call them at dispatch decision time; the prompt-side consumer
        # is the dispatcher itself, not an in-repo Python module. Slash commands
        # (`devolaflow.skills.slash_commands`) DO consume the contract via the
        # `--no-change` opt-out path documented by A-6.3, but do not call the
        # heuristic functions directly (they are activation-side, the slash
        # commands are lifecycle-side). NOT domain-SSOT registry symbols per
        # A-5.2 — pure functions with zero side effects, mirrors the
        # `workspace_context.scan_workspace` allowlist precedent above
        # (public surface advertised in SKILL.md, in-repo Python caller lands
        # in a subsequent PV per the v9.2.0 cycle plan §"Execution model").
        # Verified by `tests/test_change_activation_heuristic.py` (13 tests
        # covering classifier thresholds + verdict matrix + R5 strict env
        # parsing) + `tests/test_no_ghost_features.py::
        # test_v9_1_2_new_symbols_have_coverage` (W-18 ghost-audit refresh:
        # presence + import-smoke + W-20 reuse + R5 strict assertions).
        "devolaflow.skills.change_activation:classify_complexity",
        "devolaflow.skills.change_activation:activation_verdict",
        "devolaflow.skills.change_activation:from_env",
        # ---- v9.1.4 PV-04 (cycle v9.2.0) — memory_router.consult_for_dispatch ----
        # `consult_for_dispatch(payload, repo_root, *, max_hits=3) -> list[MemoryCase]`
        # is the advisory companion to `MemoryRouter.lookup_case`. Where
        # `lookup_case` is the planner-replacement fast-path keyed on
        # workflow_type+task_type, `consult_for_dispatch` is keyword-scored
        # against the dispatch payload's task description and surfaces the
        # top-3 matched MemoryCase IDs in the dispatch payload's
        # `change_context.memory_case_hits` sub-field (NEST extension per
        # A-2.3 — schema documented in
        # `schemas/lean-dispatch.yaml#lean_format_spec.change_context`).
        # The function is REUSE-gated by `DEVOLAFLOW_MEMORY_ROUTER` (NOT a
        # new env-flag — per the v9.2.0 cycle plan §"Self-iteration
        # constraint compliance matrix" W-20 row, "0 new flags across the
        # entire 7-PV cycle"). The first in-repo Python production caller
        # lands in v9.2.0 PV-06 (`tests/test_capability_e2e.py` + the
        # repo-init seed examples that the E2E test exercises);
        # v9.1.4 PV-04 ships the function only as the prerequisite. NOT a
        # domain-SSOT registry symbol per A-5.2 — pure read-only YAML-
        # parser + keyword-overlap scorer (no module-level state); mirrors
        # the `workspace_context.scan_workspace` allowlist precedent above
        # (public surface advertised in `references/plan-mode-enforcement.md`
        # §5.5 "Automatic Ingestion at Plan-Mode Entry (v9.1.4+)", in-repo
        # caller lands in a subsequent PV per the v9.2.0 cycle plan).
        # Verified by `tests/test_memory_consult_for_dispatch.py` (5 tests
        # covering env-flag OFF zero-IO noop / missing index fallback /
        # malformed YAML WARNING / keyword overlap scoring / TTL+version
        # filtering) + `tests/test_no_ghost_features.py::
        # test_v9_1_4_new_symbols_have_coverage` (W-18 ghost-audit refresh:
        # presence + import-smoke + W-20 reuse env-flag pin + return-type
        # callable).
        "devolaflow.memory_router.cache:consult_for_dispatch",
        # ---- v9.1.5 PV-05 (cycle v9.2.0) — agent_workspace.spec_bootstrap ----
        # `seed_initial_spec(domain, archive_id, repo_root, *, force=False) -> Path`
        # closes M-004 deferred from the v9.0.0 retrospective §3.3 (source-
        # of-truth first-time seed surface). Given a verified archive folder
        # under `.local/.agent/archive/<archive_id>/` and a target `domain`,
        # the function bootstraps `.local/memory/specs/<domain>/spec.md` from
        # the archive's spec.md ADDED Requirements via the existing
        # `ArchiveManager.propose_merge` machinery; A-4 invariant honoured
        # (refuses overwrite without `force=True`; `force=True` logs a
        # WARNING per S-5 and wipes the stale target before re-seeding).
        # NOT a domain-SSOT registry symbol per A-5.2 — pure pathlib +
        # archive-engine glue with no module-level state. The first in-repo
        # Python production caller lands in v9.2.0 PV-06 (the repo-init
        # `--with-examples` seed flow + `tests/test_capability_e2e.py`);
        # v9.1.5 PV-05 ships the function only as the prerequisite. Mirrors
        # the `consult_for_dispatch` / `scan_workspace` allowlist precedents
        # above (public surface advertised in
        # `workflow-system/agent/SKILL.md` companion docs, in-repo caller
        # lands in a subsequent PV per the v9.2.0 cycle plan §"Execution
        # model"). Verified by `tests/test_spec_bootstrap.py` (6 tests
        # covering happy path / A-4 refusal / force=True overwrite-with-
        # WARNING / missing-archive error / gate-score independence /
        # MergeConflict surface) + `tests/test_no_ghost_features.py::
        # test_v9_1_5_new_symbols_have_coverage` (W-18 ghost-audit refresh:
        # presence + import-smoke + W-20 reuse env-flag pin + force kwarg
        # default).
        "devolaflow.agent_workspace.spec_bootstrap:seed_initial_spec",
        # v9.2.3 PV-02 — `last_gitignore_audit` is the public read-only
        # accessor over the module-level `_LAST_GITIGNORE_AUDIT` cache
        # written by `_audit_gitignore_coverage` at the tail of
        # `scaffold_local`. Allowed-listed because the in-repo production
        # caller lands in v9.3.0 (`devola-init doctor` will surface the
        # most-recent audit result without re-walking the disk). The
        # accessor is exercised today by
        # `tests/test_scaffold_gitignore_audit.py::test_no_gitignore_emits_no_warning`
        # + `test_gitignore_with_agent_active_rule_warns` (and their
        # siblings) so the surface is non-vestigial; the W-18 v9.2.3
        # ghost-audit lint
        # (`tests/test_no_ghost_features.py::test_v9_2_3_new_symbols_have_coverage`)
        # pins the `callable(last_gitignore_audit)` import-smoke. NOT a
        # domain-SSOT registry symbol per A-5.2 — pure pathlib accessor
        # over a module-private list with no module-level state beyond
        # the cache. Mirrors the `consult_for_dispatch` / `scan_workspace`
        # / `seed_initial_spec` allowlist precedents above (public surface
        # advertised in
        # `workflow-system/agent/references/agent-workspace.md` companion
        # docs once the v9.3.0 doctor surface lands).
        "devolaflow.local.workspace:last_gitignore_audit",
        # ---- v9.5.0 PV-02 — Si-Chip bridge subprocess wrapper ----
        # `count_tokens(skill_md, ...)` runs `count_tokens.py --file <skill_md>
        # --both` and returns `(metadata_tokens, body_tokens)` — the cheap
        # budget pre-check exposed for external Si-Chip tooling and
        # operator opt-in flows; no in-repo Python production call site.
        # Verified by `tests/test_si_chip_bridge.py` and by
        # `tests/test_no_ghost_features.py::test_v9_5_0_new_symbols_have_coverage`
        # (W-18 ghost-audit refresh). The sibling `run_dogfood_cycle`
        # gained an in-repo production caller
        # (`devolaflow.dispatch.dispatch_dogfood_cycle`) and was purged in
        # the v17.0.0 R1 audit.
        "devolaflow.si_chip_bridge.runner:count_tokens",
        # ---- v9.5.0 PV-04 — post_skill_edit operator-facing convenience ----
        # `metadata_to_json(result)` serialises the HookResult.metadata
        # to a deterministic single-line JSON string. Used by operators
        # tailing the lifecycle log AND by the v9.5.0 PV-05 dogfood
        # pass when capturing the run-log to .local/research/. Not
        # consumed by any in-repo Python production caller — it is
        # exposed for external observers (mirrors the v8.4.4 PV-04
        # post_dispatch convenience pattern). Tests cover it indirectly
        # via the W-18 ghost-audit refresh in PV-06 cycle close.
        "devolaflow.lifecycle.post_skill_edit:metadata_to_json",
        # ---- v10.1.0 PV-02 — writing_style region helper ----
        # `prose_only(text)` returns the text with all protected regions
        # (fenced code, inline code, markdown links, version strings,
        # html tags, bare URLs) replaced by single spaces. Used by the
        # humanizer transforms shipping in v10.1.0 PV-03 — the region
        # classifier is the load-bearing boundary between "code/version
        # data that transforms must never edit" and "prose that
        # transforms may rewrite". Tests cover it via
        # `tests/test_writing_style_scorer.py::test_prose_only_strips_protected_regions`.
        # Ghost-audit refresh lands in v10.1.0 PV-06 with
        # `test_v10_1_0_new_symbols_have_coverage`.
        "devolaflow.writing_style.regions:prose_only",
        # ---- v11.1.0 PV-05 (cycle v11.1.0) — Architecture rule A-7 cascade
        # depth invariant helpers ----
        # `populate_cascade_gate_fields(base_dispatch, complexity)` is the
        # OPT-IN dispatch-payload populator that NESTs ``gate.cascade_required``
        # + ``gate.cascade_min_layers`` under the existing ``gate`` block per
        # A-2.3 when ``cascade_requirement(complexity) == "CASCADE_REQUIRED"``
        # (STANDARD/COMPLEX). `validate_cascade_gate_fields(gate_block, *,
        # actual_layers=None)` is the SOFT cascade validator that returns a
        # warnings list (no raise) when the dispatch chain is below
        # ``cascade_min_layers``. Both helpers are wired declaratively into
        # the cascade-restoration architecture per ``.rules/architecture.mdc``
        # §A-7 "Cascade-Depth Invariant for Standard+ Dispatches" and pinned
        # by `tests/test_cascade_enforcement.py` (13 tests covering strict +
        # soft + backward-compat + skip-path + truth-table propagation).
        # The PV-04 placeholder pin tuples
        # (`_populate_cascade_gate_fields_dead_api_pins` in feedback.py +
        # `_validate_cascade_gate_fields_dead_api_pins` in gate/scorer.py)
        # were REMOVED in v11.0.5 PV-05 per cycle plan §3 PV-05 W03 ("dead-API
        # pin cleanup now that A-7 wires the symbols"); these allowlist
        # entries are the canonical replacement, mirroring the established
        # pattern for forward-looking helpers (cf. `consult_for_dispatch`,
        # `seed_initial_spec`, `scan_workspace` precedents above). The full
        # production wiring (an L0/L1/L2 dispatcher build path that invokes
        # `populate_cascade_gate_fields` + a strict-mode call site that raises
        # `CascadeViolationError` from `validate_cascade_gate_fields`) lands
        # at v12.0.0 STRICT promotion per cycle plan §6 finding 1
        # ("DEFAULTS-PERMISSIVE-IN-MINOR / STRICT-IN-NEXT-MAJOR" pattern) AND
        # per W-21 2-cycle deliberation cadence. NOT domain-SSOT registry
        # symbols per A-5.2 — pure functions with zero module-level state.
        "devolaflow.gate.cascade:populate_cascade_gate_fields",
        "devolaflow.gate.cascade:validate_cascade_gate_fields",
        # ---- v14.4.0 (G-005 NEST slice) — intra-task-convergence helpers ----
        # `populate_intra_task_convergence(base_dispatch, task_type)` +
        # `validate_intra_task_convergence_fields(gate_block, *, strict=False)`
        # mirror the v11.1.0 cascade helper pair above VERBATIM: opt-in
        # forward-looking helpers that land wired-but-unused at the cycle
        # that introduces them (pinned by tests/test_intra_task_convergence.py);
        # production dispatcher call sites land when an L0/L1/L2 build path
        # adopts the §15 self-verify signal. NOT domain-SSOT registry
        # symbols per A-5.2 — pure functions with zero module-level state.
        "devolaflow.gate.cascade:populate_intra_task_convergence",
        "devolaflow.gate.cascade:validate_intra_task_convergence_fields",
        # v16.0.0 M5b — single-file harness fixture loader. The probe runtime
        # uses the bounded directory loader, while external harness tooling
        # and focused fixture diagnostics use this public one-file entry
        # point. The dead-API detector excludes tests, where filename-to-id
        # binding and schema validation are pinned. NOT a domain-SSOT
        # registry symbol per A-5.2 — pure read-and-validate helper with no
        # module-level registration data.
        "devolaflow.harness.fixtures:load_harness_fixture",
        # NOTE (v15.0.0 R1): `devolaflow.gate.artifact_score:score_artifact_evidence`
        # was allowlisted here during the v15-ADR-007 phase-2 standalone
        # landing; the entry was REMOVED when the R1 gate wiring gave it a
        # production caller (`gate/scorer.py::_attach_artifact_evidence`
        # via `evaluate_gate(artifact_evidence=...)`).
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
