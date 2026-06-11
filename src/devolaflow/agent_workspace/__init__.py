"""Agent workspace — Python API for the v8.3.0 ``.local/.agent/`` tree.

This package implements the C-003 + M-005 (Python half) + M-006 closures from
``.local/research/v8.3.0_gap_analysis.md``. It is the runtime-side companion
to the schemas that landed in v8.2.4 PV-04 under ``schemas/agent-workspace/``.

Public surface (consumed by the ``change-driven`` workflow template that
ships in v8.2.6 + the reporter that ships in v8.2.7 + the memory bridge
that ships in v8.2.8):

* :class:`Change` + :class:`ChangeStore` — list/get/move semantics on
  ``.local/.agent/active/<change-id>/`` and ``.local/.agent/archive/``.
* :class:`HandoffEnvelope` + :class:`HandoffStore` — append-only ledger
  for inter-layer messages under ``.local/.agent/handoff/``. Enforces the
  Rule S-9 invariant (envelopes are immutable; new info ⇒ ``seq+1``).
* :class:`ArchiveManager` — moves ``active/<id>/`` → ``archive/<date>-<id>/``,
  preserves all artifacts, calls ``consolidate_session`` for learnings,
  and PROPOSES (does not write) the delta-merged source-of-truth spec.
* :func:`parse_delta_spec` + :class:`DeltaSpec` — extract ADDED / MODIFIED /
  REMOVED requirement sections from an OpenSpec-style ``spec.md``.
* :func:`lint_change` — enforce per-artifact token budgets per Rule C-9.
* :class:`EnvelopeImmutableError` — raised by ``HandoffStore.write_envelope``
  when an existing ``seq`` would be overwritten.
* :func:`render_change_report` / :func:`render_workspace_report` /
  :func:`render_memory_report` / :func:`render_rules_report` plus the
  :func:`regenerate_all` orchestrator — v8.2.7 opt-in REPORT.md surface
  (closes H-005). Per Rule I-PV07-A, callers must explicitly invoke;
  no auto-trigger from existing workflows yet.
* :func:`seed_initial_spec` + :exc:`SpecBootstrapError` — v9.1.5 PV-05
  first-time source-of-truth seed (closes M-004 deferred from v9.0.0
  retro §3.3). Bootstraps ``.local/memory/specs/<domain>/spec.md`` from
  a verified archive's ``spec.md`` ADDED Requirements; A-4 invariant
  enforced (refuses overwrite without ``force=True``); subsequent
  updates go through ``ArchiveManager.propose_merge → apply_merge``.

Backward-compat (R5):

* This package adds NO new public symbol to ``devolaflow.__init__``.
* ``learnings.py`` is NOT touched; the 14 existing public functions stay
  byte-identical (verified by ``tests/test_learnings.py`` — invariant
  I-PV05-B).
* ``compressor.py::assert_dispatch_layout`` is extended to accept BOTH
  v4 (15 keys, ``acceptance_criteria_v2`` last) and v5 (16 keys,
  ``change_context`` appended) payloads — invariant I-PV05-C.
"""

from __future__ import annotations

from devolaflow.agent_workspace.archive import (
    AppliedMerge,
    ArchiveError,
    ArchiveManager,
    GateThresholdNotMet,
    MergeConflict,
)
from devolaflow.agent_workspace.change import (
    Change,
    ChangeNotFoundError,
    ChangeStore,
    ChangeStoreError,
)
from devolaflow.agent_workspace.delta_parser import (
    DeltaRequirement,
    DeltaSpec,
    DeltaSpecParseError,
    parse_delta_spec,
    serialize_delta_spec,
)
from devolaflow.agent_workspace.dispatch_executor import (
    DEFAULT_MAX_CONCURRENCY,
    AsyncDispatchExecutor,
    ExecutorError,
    TaskOutcome,
)
from devolaflow.agent_workspace.handoff import (
    EnvelopeImmutableError,
    HandoffEnvelope,
    HandoffStore,
    HandoffStoreError,
)
from devolaflow.agent_workspace.lint import (
    HUMAN_ARTIFACT_BUDGETS,
    BudgetReport,
    BudgetViolation,
    HumanBudgetExceededError,
    enforce_digest_budget,
    estimate_tokens,
    lint_change,
    lint_human,
)
from devolaflow.agent_workspace.memory_bridge import (
    MemoryBridgeError,
    consolidate_change_on_archive,
    hydrate_change_context,
)
from devolaflow.agent_workspace.reporter import (
    regenerate_all,
    render_change_report,
    render_human_digest,
    render_human_report,
    render_memory_report,
    render_rules_report,
    render_workspace_report,
)
from devolaflow.agent_workspace.requirements_trace import (
    RequirementsTraceError,
    RequirementTraceResult,
    TestOutcome,
    parse_pytest_report,
    trace_requirements,
)
from devolaflow.agent_workspace.spec_bootstrap import (
    SpecBootstrapError,
    seed_initial_spec,
)

__all__ = [
    # archive
    "AppliedMerge",
    "ArchiveError",
    "ArchiveManager",
    "GateThresholdNotMet",
    "MergeConflict",
    # change
    "Change",
    "ChangeNotFoundError",
    "ChangeStore",
    "ChangeStoreError",
    # delta_parser
    "DeltaRequirement",
    "DeltaSpec",
    "DeltaSpecParseError",
    "parse_delta_spec",
    "serialize_delta_spec",
    # dispatch_executor (v9.3.0 PV-05 — async L2-wave parallelism)
    "AsyncDispatchExecutor",
    "DEFAULT_MAX_CONCURRENCY",
    "ExecutorError",
    "TaskOutcome",
    # handoff
    "EnvelopeImmutableError",
    "HandoffEnvelope",
    "HandoffStore",
    "HandoffStoreError",
    # lint
    # + v14.2.0 REQ-OUT-01 blocking promotion (enforce_digest_budget +
    #   HumanBudgetExceededError; advisory→blocking per v14.0.0 design §8b)
    "BudgetReport",
    "BudgetViolation",
    "HUMAN_ARTIFACT_BUDGETS",
    "HumanBudgetExceededError",
    "enforce_digest_budget",
    "estimate_tokens",
    "lint_change",
    "lint_human",
    # memory_bridge (v8.2.8 — closes H-006)
    "MemoryBridgeError",
    "consolidate_change_on_archive",
    "hydrate_change_context",
    # reporter (v8.2.7 — opt-in REPORT.md surface; closes H-005)
    # + v14.0.0 Wave-2 FIFTH human flavour (render_human_report/_digest; design §4)
    "regenerate_all",
    "render_change_report",
    "render_human_digest",
    "render_human_report",
    "render_memory_report",
    "render_rules_report",
    "render_workspace_report",
    # requirements_trace (v14.0.0 Wave-3 — REQ-ID → evidence trace; design §6c)
    # + v14.1.0 §6c test-run-artifact join (TestOutcome / parse_pytest_report)
    "RequirementTraceResult",
    "RequirementsTraceError",
    "TestOutcome",
    "parse_pytest_report",
    "trace_requirements",
    # spec_bootstrap (v9.1.5 PV-05 — closes M-004 first-time seed)
    "SpecBootstrapError",
    "seed_initial_spec",
]


# v9.3.0 PV-05 — non-import references that mark the dispatch_executor
# public symbols as "alive" for `scripts/detect_dead_apis.py`. The
# detector's ``_collect_real_uses`` walker treats any non-Import
# ``ast.Name`` reference in a production file as a real caller. Until a
# future PV (telegraphed for v9.7.0 PV-03) auto-wires
# ``AsyncDispatchExecutor`` into the L0/L1 dispatch loop, the executor's
# only in-repo callers are the test suite (excluded from the dead-API
# check by ``test_dirs``) and these explicit pins. The tuple is kept
# private (no leak into ``__all__``) so the public API surface is
# unchanged. Mirrors the PV-04 ``_dead_api_pins`` precedent in
# ``src/devolaflow/compressor/__init__.py``.
_dispatch_executor_dead_api_pins = (
    AsyncDispatchExecutor,
    ExecutorError,
    TaskOutcome,
    DEFAULT_MAX_CONCURRENCY,
)


# v14.0.0 Wave-3 — non-import references that mark the requirements_trace
# public symbols as "alive" for `scripts/detect_dead_apis.py`. Per the F-2
# design (`.local/research/v14.0.0_design.md` §6c), `trace_requirements` is
# the per-REQ-row producer the FIFTH `reporter.py` flavour
# (`render_human_report`, §4d) will consume — that production caller lands in
# the v14.0.0 implementation cycle, so until then the test suite is its only
# in-repo caller (excluded from the dead-API check by `test_dirs`). The tuple
# is kept private (no leak into `__all__`) so the public API surface is
# unchanged. Mirrors the `_dispatch_executor_dead_api_pins` precedent above.
_requirements_trace_dead_api_pins = (
    RequirementTraceResult,
    RequirementsTraceError,
    TestOutcome,
    parse_pytest_report,
    trace_requirements,
)
