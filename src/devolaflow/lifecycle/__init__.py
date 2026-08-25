"""Lifecycle hooks package — deterministic enforcement layer (P-05).

Closes the **BLOCKER** ghost G-C1 documented in
``.local/research/v7.5.0_ghost_audit.md`` §3.C: ``workflow-system/agent/SKILL.md``
§"Lifecycle Hooks" promised three hooks (``validate_dispatch``,
``check_file_ownership``, ``test_on_complete``) with "100% compliance"
enforcement, but until v7.4.8 no implementation existed.

This package lands the missing implementations as three small modules
plus a central :func:`run_hooks` orchestrator. The hooks ship two
enforcement modes:

* **Permissive** (default): violations are collected on the returned
  :class:`HookResult` and logged at WARNING level via Python's standard
  :mod:`logging` module. No exception is raised. Suitable for advisory
  / observability use cases where the surrounding orchestrator decides
  what to do with the violations.

* **Strict** (opt-in via ``strict=True``): after all handlers run and
  violations are aggregated, the top-severity :class:`HookViolation`
  (``blocker > error > warning``) is re-raised so the caller can
  block / reject / escalate per the SKILL.md "On Violation" column.

Runtime wiring (v14.3.0, G-001 closure per
``docs/cycle-archive/adr/v15-ADR-003-output-closure-enforcement-locus.md``):
the dispatch-side events (``pre_dispatch`` → ``post_dispatch`` →
``pre_handoff`` → ``pre_plugin_invocation``) fire from
``feedback_emit.ProposalEmitter._fire_hook_chain`` on every dispatch
emission (S-10), and — NEW at v14.3.0 — the execution-side events fire
from :mod:`devolaflow.lifecycle.runtime_wiring`:

* ``file_write`` fires from the framework's change-driven write surface
  (``agent_workspace.change.Change.to_active_folder``) via
  :func:`fire_file_write` BEFORE each artifact write.
* ``task_stop`` fires from the L2 report emission surface
  (``agent_workspace.handoff.HandoffStore.write_envelope`` for
  ``StatusReport`` envelopes) via :func:`fire_task_stop`.

Both adapters are STRICT by default since v15.0.0 (block + escalate
per S-8 "mode: full"; ADR-003 §Decision 3, riding the G-038
strict-graduation cluster) and remain byte-identical zero-IO no-ops
unless ``DEVOLAFLOW_AGENT_WORKSPACE=1`` (W-20 env-flag reuse — same
activation surface as A-6 / ``pre_handoff``; NO new flag; the
activation gate is UNCHANGED by the strict flip). Opt-out: pass
``strict=False`` explicitly to either adapter (S-8 "mode: lite" — warn
+ log, the v14.3.0 permissive behaviour). Out-of-band writes (raw
shell) bypass the ``file_write`` adapter by design — the ``task_stop``
evidence checks catch the net effect (ADR-003 §Consequences).

Public API
----------
* :func:`run_hooks` — dispatch by event name (``pre_dispatch``,
  ``file_write``, ``task_stop``, ``format_on_edit``).
* :func:`register_hook` — add an extra handler for an event (defaults
  remain installed).
* :func:`clear_hooks` — clear extras only; defaults are immutable.
* :class:`HookResult` / :class:`HookViolation` — result/error envelopes.
* The default hooks are re-exported so callers can invoke them directly
  with the same ``(payload, *, strict=False)`` signature without going
  through :func:`run_hooks`.
"""

from __future__ import annotations

from devolaflow.harness.telemetry import record_dispatch_telemetry
from devolaflow.lifecycle.assert_layer_budget import (
    assert_layer_token_budget,
)
from devolaflow.lifecycle.auto_write_handoff import (
    EVENT as _PRE_HANDOFF_EVENT,
)
from devolaflow.lifecycle.auto_write_handoff import (
    auto_write_handoff,
)
from devolaflow.lifecycle.check_envelope_append_only import (
    EVENT as _ENVELOPE_WRITE_EVENT,
)
from devolaflow.lifecycle.check_envelope_append_only import (
    check_envelope_append_only,
)
from devolaflow.lifecycle.check_file_ownership import (
    EVENT as _FILE_WRITE_EVENT,
)
from devolaflow.lifecycle.check_file_ownership import (
    check_file_ownership,
)
from devolaflow.lifecycle.check_human_input_append_only import (
    EVENT as _CHECK_HUMAN_INPUT_WRITE_EVENT,
)
from devolaflow.lifecycle.check_human_input_append_only import (
    check_human_input_append_only,
)
from devolaflow.lifecycle.dispatcher import (
    HookHandler,
    HookResult,
    HookViolation,
    Severity,
    _alias_event,
    _set_default_hook,
    clear_hooks,
    emit_violations,
    finalize,
    list_handlers,
    register_hook,
    registered_events,
    run_hooks,
)
from devolaflow.lifecycle.format_on_edit import (
    EVENT as _FORMAT_ON_EDIT_EVENT,
)
from devolaflow.lifecycle.format_on_edit import (
    format_on_edit,
)
from devolaflow.lifecycle.post_dispatch import (
    EVENT as _POST_DISPATCH_EVENT,
)
from devolaflow.lifecycle.post_dispatch import (
    post_dispatch,
)
from devolaflow.lifecycle.post_skill_edit import (
    EVENT as _POST_SKILL_EDIT_EVENT,
)
from devolaflow.lifecycle.post_skill_edit import (
    post_skill_edit,
)
from devolaflow.lifecycle.pre_plugin_invocation import (
    EVENT as _PRE_PLUGIN_INVOCATION_EVENT,
)
from devolaflow.lifecycle.pre_plugin_invocation import (
    pre_plugin_invocation,
)
from devolaflow.lifecycle.pre_plugin_invocation_install import (
    EVENT as _PRE_PLUGIN_INVOCATION_INSTALL_EVENT,
)
from devolaflow.lifecycle.pre_plugin_invocation_install import (
    pre_plugin_invocation_install,
)
from devolaflow.lifecycle.pre_plugin_invocation_upgrade import (
    EVENT as _PRE_PLUGIN_INVOCATION_UPGRADE_EVENT,
)
from devolaflow.lifecycle.pre_plugin_invocation_upgrade import (
    pre_plugin_invocation_upgrade,
)
from devolaflow.lifecycle.pre_shell_call import (
    EVENT as _PRE_SHELL_CALL_EVENT,
)
from devolaflow.lifecycle.pre_shell_call import (
    pre_shell_call,
)
from devolaflow.lifecycle.reject_subagent_banner_emission import (
    reject_subagent_banner_emission,
    unregister_pre_dispatch_extra,
)
from devolaflow.lifecycle.reject_subagent_quality_score import (
    reject_subagent_quality_score,
)
from devolaflow.lifecycle.runtime_wiring import (
    fire_file_write,
    fire_task_stop,
    is_workspace_engaged,
)
from devolaflow.lifecycle.test_on_complete import (
    EVENT as _TASK_STOP_EVENT,
)
from devolaflow.lifecycle.test_on_complete import (
    test_on_complete,
)
from devolaflow.lifecycle.validate_dispatch import (
    EVENT as _PRE_DISPATCH_EVENT,
)
from devolaflow.lifecycle.validate_dispatch import (
    validate_dispatch,
)
from devolaflow.lifecycle.validate_owned_files import (
    DoctorFinding,
    DoctorReport,
    check_init_health,
    get_canonical_manifest,
    validate_owned_files,
)
from devolaflow.lifecycle.validate_surgical_scope import (
    DiffStats,
    FileDiffStat,
    ScopeViolation,
    SurgicalScopeError,
    check_function_scope,
    check_module_scope,
    collect_diff_stats,
    evaluate_surgical_scope,
    register_surgical_scope_hook,
    validate_surgical_scope,
)

# v11.0.0 PV-02 D-Q-3 — NEW canonical lifecycle event names per the
# `pre_*` / `post_*` / `check_*` taxonomy. Each NEW name is wired as a
# PURE-ALIAS for the corresponding OLD name via ``_alias_event`` BELOW
# (BEFORE ``_set_default_hook`` calls); both names then accept
# ``register_hook`` / ``run_hooks`` calls and route to the SAME
# underlying handler list. The OLD names at positions 3, 4, 5, 7 of
# DEFAULT_EVENTS are preserved BYTE-IDENTICALLY as ALIASES for 1 full
# cycle (v11.0.0 → v11.x); deprecation telegraphed for v12.0.0+ per
# the v11.0.0 retrospective §3 deferred items list and `references/
# env-flags.md` lifecycle-event taxonomy section.
#
# Rename mapping (D-Q-3 §2):
#   file_write       → check_file_write    (S-8 ownership check; check_* prefix)
#   task_stop        → post_task_complete  (post-action; post_* prefix)
#   format_on_edit   → post_file_edit      (post-action; post_* prefix)
#   envelope_write   → check_envelope_write (S-9 append-only check; check_*)
CHECK_FILE_WRITE_EVENT: str = "check_file_write"
POST_TASK_COMPLETE_EVENT: str = "post_task_complete"
POST_FILE_EDIT_EVENT: str = "post_file_edit"
CHECK_ENVELOPE_WRITE_EVENT: str = "check_envelope_write"

# Wire D-Q-3 PURE-ALIAS rename BEFORE the ``_set_default_hook`` calls
# below — every subsequent ``_set_default_hook(_FILE_WRITE_EVENT, ...)``
# call resolves the OLD name to the NEW canonical via the alias map and
# stores the handler under the NEW canonical key in ``_DEFAULT_HOOKS``.
# 1-cycle alias schedule: OLD names removed at v12.0.0+ once operators
# have migrated their hook registrations.
_alias_event(_FILE_WRITE_EVENT, CHECK_FILE_WRITE_EVENT)
_alias_event(_TASK_STOP_EVENT, POST_TASK_COMPLETE_EVENT)
_alias_event(_FORMAT_ON_EDIT_EVENT, POST_FILE_EDIT_EVENT)
_alias_event(_ENVELOPE_WRITE_EVENT, CHECK_ENVELOPE_WRITE_EVENT)

# Wire the canonical defaults. The OLD-name constants below are passed
# to ``_set_default_hook``; each call internally resolves through the
# alias map (set up above) and stores the handler under the NEW
# canonical key. Callers using EITHER the OLD constant string or the
# NEW canonical string see byte-identical handler dispatch.
_set_default_hook(_PRE_DISPATCH_EVENT, validate_dispatch)
_set_default_hook(_POST_DISPATCH_EVENT, post_dispatch)
# v16.0.0 M2-W4-T1 — keep the canonical post_dispatch default as the
# byte-preserving no-op, then add harness telemetry as an observational extra.
# The identity check keeps module reloads idempotent while preserving
# deterministic default-first handler order.
if record_dispatch_telemetry not in list_handlers(_POST_DISPATCH_EVENT):
    register_hook(_POST_DISPATCH_EVENT, record_dispatch_telemetry)
_set_default_hook(_FILE_WRITE_EVENT, check_file_ownership)
_set_default_hook(_TASK_STOP_EVENT, test_on_complete)
_set_default_hook(_FORMAT_ON_EDIT_EVENT, format_on_edit)
_set_default_hook(_PRE_SHELL_CALL_EVENT, pre_shell_call)
_set_default_hook(_ENVELOPE_WRITE_EVENT, check_envelope_append_only)
_set_default_hook(_PRE_HANDOFF_EVENT, auto_write_handoff)
_set_default_hook(_PRE_PLUGIN_INVOCATION_EVENT, pre_plugin_invocation)
_set_default_hook(_POST_SKILL_EDIT_EVENT, post_skill_edit)
_set_default_hook(_PRE_PLUGIN_INVOCATION_INSTALL_EVENT, pre_plugin_invocation_install)
_set_default_hook(_PRE_PLUGIN_INVOCATION_UPGRADE_EVENT, pre_plugin_invocation_upgrade)
# v15.0.0 G-038 flip 4 — the v14.0.0 Wave-3 hook graduates from
# "exported additively, NOT wired" to a canonical default event (the
# wiring the v14.0.0 design §3c deferred to "the implementation cycle
# alongside those test updates"). Both former `len == 16` pins
# (tests/ghost/test_features_v11_0.py + tests/test_lifecycle_hooks.py)
# are re-pinned in the same MAJOR.
_set_default_hook(_CHECK_HUMAN_INPUT_WRITE_EVENT, check_human_input_append_only)

# Register validate_owned_files as an extra on pre_dispatch (runs after default).
register_hook(_PRE_DISPATCH_EVENT, validate_owned_files)

# v12.2.0 PV-04 — runtime closure of v12.1.0 D-1 (the prompt-side guarantee
# that subagents MUST NOT score). Registered as an extra (not a default
# replacement) per the S-10 byte-id contract — the existing default
# `validate_dispatch` runs FIRST + this hook runs AFTER. STRICT default on
# direct invocation since v15.0.0 (G-038 flip 2; `run_hooks` chains stay
# permissive at aggregate time); opt-out = explicit `strict=False`.
register_hook(_PRE_DISPATCH_EVENT, reject_subagent_quality_score)

# v15.0.0 G-038 flip 3 — the v12.4.0 PV-05 banner hook graduates from
# opt-in (`register_pre_dispatch_extra()`) to default-wired, mirroring the
# v12.2.0 quality-score extra above. Runs AFTER the quality-score extra in
# insertion order. The hook never mutates the payload, so the S-10
# byte-identical dispatch contract is preserved
# (tests/test_dispatch_emission_runs_hooks.py). Documented opt-out:
# `reject_subagent_banner_emission.unregister_pre_dispatch_extra()`.
register_hook(_PRE_DISPATCH_EVENT, reject_subagent_banner_emission)

# v17.0.0 R2 (G17-B2 / D-R2-5) — layer-token-budget assertion. Registered
# as the LAST pre_dispatch extra (after validate_owned_files +
# reject_subagent_quality_score + reject_subagent_banner_emission) so the
# content validators run first. Non-mutating (S-10 byte-identity preserved);
# measures estimate_tokens(stable_yaml(payload)) against
# harness.telemetry.LAYER_TOKEN_BUDGETS and surfaces ALB001 on overrun —
# blocks under the strict pre_dispatch emission default, warns in lite mode.
# Payloads without telemetry-resolvable layer attribution PASS (backward
# compatible with legacy dispatches).
register_hook(_PRE_DISPATCH_EVENT, assert_layer_token_budget)

PRE_DISPATCH_EVENT: str = _PRE_DISPATCH_EVENT
POST_DISPATCH_EVENT: str = _POST_DISPATCH_EVENT
FILE_WRITE_EVENT: str = _FILE_WRITE_EVENT
TASK_STOP_EVENT: str = _TASK_STOP_EVENT
FORMAT_ON_EDIT_EVENT: str = _FORMAT_ON_EDIT_EVENT
PRE_SHELL_CALL_EVENT: str = _PRE_SHELL_CALL_EVENT
ENVELOPE_WRITE_EVENT: str = _ENVELOPE_WRITE_EVENT
PRE_HANDOFF_EVENT: str = _PRE_HANDOFF_EVENT
PRE_PLUGIN_INVOCATION_EVENT: str = _PRE_PLUGIN_INVOCATION_EVENT
POST_SKILL_EDIT_EVENT: str = _POST_SKILL_EDIT_EVENT
PRE_PLUGIN_INVOCATION_INSTALL_EVENT: str = _PRE_PLUGIN_INVOCATION_INSTALL_EVENT
PRE_PLUGIN_INVOCATION_UPGRADE_EVENT: str = _PRE_PLUGIN_INVOCATION_UPGRADE_EVENT
CHECK_HUMAN_INPUT_WRITE_EVENT: str = _CHECK_HUMAN_INPUT_WRITE_EVENT

# v8.4.4 PV-04: bumped 5 → 6 with the addition of `post_dispatch` (the
# symmetric tail event to `pre_dispatch`). The new slot is wired to a
# permissive no-op default in `post_dispatch.py`; the actual governance-
# contract handler (Soul Rule S-10) lands in PV-07 with the rule-corpus
# selectivity slice. R5 strict byte-identical: zero behaviour change with
# no extras registered (verified by
# `tests/test_dispatch_emission_runs_hooks.py`).
#
# v9.1.0 W1-02: bumped 6 → 7 with the addition of `envelope_write` per
# Soul Rule S-9 closure (handoff envelopes are append-only). The new
# slot is wired to `check_envelope_append_only.py` which blocks
# overwrites of existing handoff envelopes in STRICT mode. The new
# event is APPENDED at the END of the tuple to preserve A-2.4 /
# cache-prefix invariants — existing event positions 1-6 remain
# byte-stable.
#
# v9.1.3 PV-03: bumped 7 → 8 with the addition of `pre_handoff` per
# G-005 closure (HandoffStore.write_envelope gains its FIRST production
# caller — `auto_write_handoff`). The new slot is wired to
# `auto_write_handoff.py` which materialises a handoff envelope under
# `.local/.agent/handoff/` when `DEVOLAFLOW_AGENT_WORKSPACE=1` AND the
# dispatch payload carries a populated `change_context` block. The
# event is APPENDED at the END of the tuple to preserve A-2.4 /
# cache-prefix invariants — existing event positions 1-7 remain
# byte-stable. The env-flag is REUSED per Workflow Rule W-20 (same
# activation surface as v9.1.1 PV-01 SKILL.md §"Workspace Engagement"
# and v9.1.2 PV-02 Architecture rule A-6).
#
# v9.4.0 PV-02: bumped 8 → 9 with the addition of `pre_plugin_invocation`
# per D-P-1 closure (the `ensure_plugin()` dead-wire from
# `.local/research/v9.4.0_gap_analysis.md` §3.1). The new slot is
# wired to `pre_plugin_invocation.py` which auto-installs plugins
# cited in the dispatch payload BEFORE the L2 dispatch fires when
# `DEVOLAFLOW_AUTO_INSTALL_PLUGINS=1`. The event is APPENDED at the
# END of the tuple to preserve A-2.4 / cache-prefix invariants —
# existing event positions 1-8 remain byte-stable. NEW env-flag
# justified per Workflow Rule W-20 §3 orthogonality (different
# activation surface from `DEVOLAFLOW_AUTO_INSTALL` install primitive
# AND from `DEVOLAFLOW_AGENT_WORKSPACE` workspace-lifecycle); see
# `references/env-flags.md` §2.13 for the full argument.
#
# v9.5.0 PV-04: bumped 9 → 10 with the addition of `post_skill_edit`
# per D-S-4 closure (the user Q2=B DEEP integration signoff from
# `.local/research/v9.5.0_gap_analysis.md` §3.1). The new slot is
# wired to `post_skill_edit.py` which auto-runs the Si-Chip
# iteration_delta gate after any commit touching
# `workflow-system/agent/**` when `DEVOLAFLOW_SI_CHIP_DEEP=1`. The
# event is APPENDED at the END of the tuple to preserve A-2.4 /
# cache-prefix invariants — existing event positions 1-9 remain
# byte-stable. NEW env-flag justified per Workflow Rule W-20 §3
# orthogonality (different activation surface from
# `DEVOLAFLOW_AUTO_INSTALL_PLUGINS` plugin pre-flight AND from
# `DEVOLAFLOW_AGENT_WORKSPACE` workspace-lifecycle AND from
# `DEVOLAFLOW_AUTO_INSTALL` install primitive); see
# `references/env-flags.md` §2.14 for the full argument.
#
# v10.8.0 D-C-3: bumped 10 → 12 with the split of `pre_plugin_invocation`
# (position 9) into two focused handlers per
# `.local/research/v11.0.0_patches/D-C-3.md`:
#
#   * `pre_plugin_invocation_install` (position 11) — INSTALL
#     responsibility only (PPI001 surface).
#   * `pre_plugin_invocation_upgrade` (position 12) — UPGRADE
#     responsibility only (PPI003 surface).
#
# Both new slots REUSE `DEVOLAFLOW_AUTO_INSTALL_PLUGINS=1` per
# Workflow Rule W-20 during the 1-cycle alias window;
# `DEVOLAFLOW_AUTO_UPGRADE_PLUGINS` is TELEGRAPHED for v12.0.0+ SI-1
# re-evaluation per D-C-3 §2 step 4. The existing event at position 9
# (`pre_plugin_invocation`) is preserved BYTE-IDENTICALLY as a
# 1-cycle backward-compat alias; its handler body delegates to the
# install + upgrade handlers in sequence so operators registering
# extras on the alias event see identical behaviour.
#
# Per A-2.2 append-only, positions 1-10 are byte-stable — positions
# 11 + 12 appended at the tail preserving the cache-prefix invariant.
# See `references/env-flags.md` §2.13 row for the full split doc.
#
# v11.0.0 PV-02 D-Q-3: bumped 12 → 16 by APPENDING the 4 NEW canonical
# event names per the `pre_*` / `post_*` / `check_*` taxonomy. The 4
# OLD names at positions 3, 4, 5, 7 (`file_write`, `task_stop`,
# `format_on_edit`, `envelope_write`) are preserved BYTE-IDENTICALLY
# as ALIASES routed through the dispatcher's ``_EVENT_ALIASES`` map.
# Both names accept ``register_hook`` / ``run_hooks`` calls; both
# dispatch the SAME underlying handler list.
#
#   * `check_file_write`     (position 13) — alias of `file_write`
#   * `post_task_complete`   (position 14) — alias of `task_stop`
#   * `post_file_edit`       (position 15) — alias of `format_on_edit`
#   * `check_envelope_write` (position 16) — alias of `envelope_write`
#
# 1-cycle alias schedule: OLD names removed at v12.0.0+ once operators
# have migrated their hook registrations. Telegraphed in v11.0.0
# retrospective §3 deferred items list per the W-21-pattern multi-cycle
# deliberation cadence (NOT W-21 itself; W-21 governs Soul rules only).
#
# Per A-2.2 append-only, positions 1-12 are byte-stable — positions
# 13-16 appended at the tail preserving the cache-prefix-style
# invariant for ``DEFAULT_EVENTS`` (note: ``DEFAULT_EVENTS`` is an
# internal lifecycle tuple, NOT the dispatch payload's ``canonical_order``;
# the A-2.1 frozen prefix on ``schemas/lean-dispatch.yaml#layout_invariant``
# is on a SEPARATE registry surface and is unaffected).
#
# v15.0.0 G-038 flip 4: bumped 16 → 17 with the addition of
# `check_human_input_write` (the v14.0.0 Wave-3
# `check_human_input_append_only` hook — exported additively since
# v14.0.0 but kept OUT of the tuple because two CI tests pinned
# `len(DEFAULT_EVENTS) == 16` exactly and the v14.1.0 retro §3 deferred
# the growth as cache-layout-sensitive). Growing the tuple is
# in-contract for this MAJOR: the event is APPENDED at position 17 per
# A-2.2 append-only (positions 1-16 stay byte-stable) and both former
# `== 16` pins (tests/ghost/test_features_v11_0.py +
# tests/test_lifecycle_hooks.py, plus the derived pins in
# tests/test_hook_runtime_wiring.py + tests/test_human_input_immutability.py)
# are re-pinned to the 17-entry shape in the same MAJOR.
DEFAULT_EVENTS: tuple[str, ...] = (
    PRE_DISPATCH_EVENT,
    POST_DISPATCH_EVENT,
    FILE_WRITE_EVENT,
    TASK_STOP_EVENT,
    FORMAT_ON_EDIT_EVENT,
    PRE_SHELL_CALL_EVENT,
    ENVELOPE_WRITE_EVENT,
    PRE_HANDOFF_EVENT,
    PRE_PLUGIN_INVOCATION_EVENT,
    POST_SKILL_EDIT_EVENT,
    PRE_PLUGIN_INVOCATION_INSTALL_EVENT,
    PRE_PLUGIN_INVOCATION_UPGRADE_EVENT,
    CHECK_FILE_WRITE_EVENT,
    POST_TASK_COMPLETE_EVENT,
    POST_FILE_EDIT_EVENT,
    CHECK_ENVELOPE_WRITE_EVENT,
    CHECK_HUMAN_INPUT_WRITE_EVENT,
)

__all__ = [
    "CHECK_ENVELOPE_WRITE_EVENT",
    "CHECK_FILE_WRITE_EVENT",
    "CHECK_HUMAN_INPUT_WRITE_EVENT",
    "DEFAULT_EVENTS",
    "DiffStats",
    "DoctorFinding",
    "DoctorReport",
    "ENVELOPE_WRITE_EVENT",
    "FILE_WRITE_EVENT",
    "FORMAT_ON_EDIT_EVENT",
    "FileDiffStat",
    "HookHandler",
    "HookResult",
    "HookViolation",
    "POST_DISPATCH_EVENT",
    "POST_FILE_EDIT_EVENT",
    "POST_SKILL_EDIT_EVENT",
    "POST_TASK_COMPLETE_EVENT",
    "PRE_DISPATCH_EVENT",
    "PRE_HANDOFF_EVENT",
    "PRE_PLUGIN_INVOCATION_EVENT",
    "PRE_PLUGIN_INVOCATION_INSTALL_EVENT",
    "PRE_PLUGIN_INVOCATION_UPGRADE_EVENT",
    "PRE_SHELL_CALL_EVENT",
    "ScopeViolation",
    "Severity",
    "SurgicalScopeError",
    "TASK_STOP_EVENT",
    "auto_write_handoff",
    "check_envelope_append_only",
    "check_file_ownership",
    "check_function_scope",
    "check_human_input_append_only",
    "check_init_health",
    "check_module_scope",
    "clear_hooks",
    "collect_diff_stats",
    "emit_violations",
    "evaluate_surgical_scope",
    "finalize",
    "fire_file_write",
    "fire_task_stop",
    "format_on_edit",
    "get_canonical_manifest",
    "is_workspace_engaged",
    "list_handlers",
    "post_dispatch",
    "post_skill_edit",
    "pre_plugin_invocation",
    "pre_plugin_invocation_install",
    "pre_plugin_invocation_upgrade",
    "pre_shell_call",
    "register_hook",
    "register_surgical_scope_hook",
    "registered_events",
    "record_dispatch_telemetry",
    "reject_subagent_banner_emission",
    "reject_subagent_quality_score",
    "run_hooks",
    "test_on_complete",
    "unregister_pre_dispatch_extra",
    "validate_dispatch",
    "validate_owned_files",
    "validate_surgical_scope",
]


# v15.0.0 G-038 flip 4 note: the former v14.0.0
# `_check_human_input_dead_api_pins` tuple is GONE — the hook is now a real
# production default (`_set_default_hook(_CHECK_HUMAN_INPUT_WRITE_EVENT, ...)`
# above), so the dead-API liveness no longer needs a synthetic pin.

# v15.0.0 G-038 flip 3 — non-import reference that marks
# `unregister_pre_dispatch_extra` as "alive" for `scripts/detect_dead_apis.py`.
# The opt-out helper is intentionally NOT called at import time (calling it
# would defeat the default wiring it opts out of); its callers are operators
# + the test suite (excluded from the dead-API check by `test_dirs`).
# Mirrors `_surgical_scope_dead_api_pins` below.
_banner_opt_out_dead_api_pins = (unregister_pre_dispatch_extra,)

# v14.4.0 T2 — non-import reference that marks `register_surgical_scope_hook`
# as "alive" for `scripts/detect_dead_apis.py`. The opt-in registration helper
# is intentionally NOT called at import time: the `task_stop` default chain
# stays byte-stable at `(test_on_complete,)` (default wiring of the BG-003
# surgical-scope verifier is a v15.0.0 decision per the ADR-003
# strict-graduation telegraph), so the helper's only in-repo callers are
# operators + the test suite (excluded from the dead-API check by
# `test_dirs`). Mirrors `_check_human_input_dead_api_pins` above.
_surgical_scope_dead_api_pins = (register_surgical_scope_hook,)
