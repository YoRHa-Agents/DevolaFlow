---
id: "agent/references/env-flags"
version: "8.5.0"
purpose: >
  Canonical inventory of every `DEVOLAFLOW_*` environment variable consumed
  by the runtime, the test fixtures, and the forward-declared gate primitives.
  Pairs with Workflow Rule W-20 (env-flag reuse vs new-flag policy) — every
  L3 Task Agent that proposes a new env-flag MUST consult this reference
  FIRST and prefer reuse of an existing flag whenever the data shape allows.
triggers:
  - "introducing a new feature flag"
  - "adding a runtime env-var"
  - "auditing default-off / R5 strict surfaces"
  - "wiring a v8.0.0 gate primitive (PV-06 prep)"
  - "debugging a feature that should be off-by-default"
  - "investigating a `lookup_case is None` cache miss"
  - "preparing T8 NineS hygiene closure"
tier: 2
token_estimate: 4200
dependencies:
  - "agent/SKILL.md"
  - "agent/references/shell-proxy.md"
  - "agent/references/decomposition-gate.md"
  - "agent/references/plan-mode-enforcement.md"
last_updated: "2026-04-24"
---

# Environment Flag Reference

> **Tier-2 reference** — load when the dispatcher is about to author a
> new env-flag, audit an existing default-off surface, debug a feature
> that operators expect to be inactive, or prepare the v9.0.0 PV-06 flip
> of the 5 v8.0.0 gate primitives. Pairs with **Workflow Rule W-20**
> (env-flag reuse vs new-flag policy): every NEW env-flag proposal MUST
> first consult §1 to confirm no existing flag covers the same surface.

## 1. Why this reference exists

Two distinct hygiene gaps motivate this reference (the **13th SF-4
canonical**, added in v8.5.0 PV-05):

1. **Operator surface bloat** — without a single source-of-truth, every
   PV that adds a new feature is tempted to author its own env-flag
   ("the PV-04 command-mapping layer reuses `DEVOLAFLOW_RTK_PROXY`
   precisely because the PV-04 design doc consulted PV-02's wording
   and chose REUSE"). Without this reference, the next PV will lack
   that lookup.
2. **W-20 enforceability** — Rule W-20 (added in v8.5.0 PV-05) states
   *"new behaviours should reuse existing env-flags rather than
   introduce new ones unless behaviorally orthogonal."* Enforcement
   requires the reviewer to **see** the inventory; without this
   reference, W-20 is normative-only, not actionable.

## 2. Active runtime flags (wired in `src/devolaflow/`)

These flags are read by production code paths. Tests in
`tests/test_shell_proxy*.py`, `tests/test_memory_router.py`, and
`tests/test_task_adaptive_selector.py` codify the parsing contract
(strict `"1"` matching; rejects `"true"`, `"yes"`, `"on"`, `"01"`, `""`).

### 2.1 `DEVOLAFLOW_PLAN_MODE` — plan-mode auto-detect

| Field | Value |
|---|---|
| **Owner** | `src/devolaflow/task_adaptive_selector.py::_PLAN_MODE_ENV` |
| **Introduced** | v6.1.5 |
| **Default** | unset (= disabled) |
| **Activation** | env value in `{"1", "true", "yes", "on"}` (loose match) OR `select_context(plan_mode=True)` keyword OR `.devolaflow_plan_mode` filesystem marker |
| **Effect** | `apply_plan_mode_overrides()` escalates `agent_hierarchy`, `decomposition_gate`, `rationalization_prevention` priorities to `critical`; upgrades `model_hint` to `quality`; sets `compression_intensity` to `minimal` |
| **Composition** | Plan-mode applies BEFORE round-escalation (v6.0.3 round-based escalation runs on top) |
| **R5 strict?** | NO — historical loose-parsing matches Cursor SwitchMode contract; tests in `tests/test_task_adaptive_selector.py::TestPlanModeDetect` codify the loose semantics (e.g. `"garbage"` → false, `"1"` / `"true"` / `"yes"` / `"on"` → true) |
| **Reference** | `references/plan-mode-enforcement.md` §1 (When to Load) + §2 (Detection table) |

### 2.2 `DEVOLAFLOW_RTK_PROXY` — RTK rewrite + command-mapping activation

| Field | Value |
|---|---|
| **Owner** | `src/devolaflow/shell_proxy/proxy.py::_ENV_FLAG` (also consumed by `src/devolaflow/shell_proxy/commands.py::is_command_mapping_active`) |
| **Introduced** | v8.3.2 PV-02; REUSED by v8.3.4 PV-04 (NO new flag added) |
| **Default** | unset (= disabled) |
| **Activation** | env value EXACTLY `"1"` (R5 strict — rejects `"true"`, `"yes"`, `"on"`, `"01"`, `""`) AND `rtk` binary on PATH AND `rtk gain` probe succeeds (collision-warning per RTK INSTALL.md) |
| **Effect (Tier 1)** | `pre_shell_call` rewrites `pytest`, `ruff check`, `git diff`, `git log`, `git status` via `rtk rewrite <cmd>`; per RTK README ~80% token reduction on captured stdout |
| **Effect (PV-04 layer)** | `apply_local_recipe` consults `.local/memory/commands/<repo>/<cmd>.yaml` BEFORE returning the proxied output; precedence: local recipe → RTK rewrite → passthrough |
| **R5 strict?** | YES — `is_proxy_enabled()` is a pure env-var read with NO `shutil.which` lookup, NO subprocess spawn, NO Path.read_text when unset. Codified in `tests/test_shell_proxy_disabled_is_noop.py` + `tests/test_shell_proxy_commands.py::TestLoadR5StrictOff` (`monkeypatch.setattr(Path, "read_text", watcher)` proves zero IO when off). |
| **Reference** | `references/shell-proxy.md` §3.1 (env-flag table) + §4 (R5 strict zero-overhead breakdown) |

### 2.3 `DEVOLAFLOW_RTK_PROXY_TIER2` — Tier 2 commands opt-in

| Field | Value |
|---|---|
| **Owner** | `src/devolaflow/shell_proxy/proxy.py::_TIER2_ENV_FLAG` |
| **Introduced** | v8.3.2 PV-02 |
| **Default** | unset (= Tier 1 only) |
| **Activation** | env value EXACTLY `"1"` AND #2.2 also active |
| **Effect** | Adds `git add`, `git commit`, `git show`, `cargo test`, `npm test`, `make` to the proxy whitelist (per `shell_proxy/registry.py::WHITELIST` Tier 2 block) |
| **R5 strict?** | YES — has no effect unless #2.2 is set; the Tier 2 enablement is captured in `ShellProxyConfig` snapshot at activation time |
| **Why secondary?** | Tier 1 commands are read-only / safe; Tier 2 commands have side-effects (git mutations, build invocations). Operators opt in to Tier 2 when they have separate audit logging in place. |

### 2.4 `DEVOLAFLOW_MEMORY_ROUTER` — planning fast-path

| Field | Value |
|---|---|
| **Owner** | `src/devolaflow/memory_router/router.py::ENV_FLAG` |
| **Introduced** | v8.3.3 PV-03 |
| **Default** | unset (= disabled) |
| **Activation** | env value EXACTLY `"1"` AND `.local/memory/cases/index.yaml` exists AND yields a matching case |
| **Effect** | `lookup_case(intent, env)` consults the cases index BEFORE the L0/L1 dispatcher re-derives workflow + stage decomposition from SKILL.md; cache-hit short-circuits ~3K tokens of planning context per matched route (~93% reduction per the v8.3.3 PV-03 retrospective) |
| **Cache-miss path** | Returns `None` in O(1); caller falls through to the existing planner per cycle plan §6 R3 "cache-miss is the safe path" |
| **R5 strict?** | YES — codified in `tests/test_memory_router.py::TestLookupCaseR5StrictOff` with `monkeypatch.setattr(Path, "read_text", watcher)` proving zero IO when off; the EvoBench scenario `memory_router_fastpath.yaml` codifies the dispatch-surface invariant (composite floor 90, actual 99.73 at v8.3.3 cut) |
| **Reference** | `references/shell-proxy.md` §5 (memory-router fast-path) + §7 (R5 strict zero-overhead breakdown) |

### 2.5 `DEVOLAFLOW_AUTO_INSTALL` — plugin auto-install opt-out

| Field | Value |
|---|---|
| **Owner** | `src/devolaflow/plugins/installer.py` |
| **Introduced** | v8.3.0 PV-01 (earlier baseline preserved) |
| **Default** | `1` (auto-install ACTIVE) — this is the only flag in this reference that is **default-on** |
| **Opt-out** | env value `"0"` (any truthy other-than-1 also disables) |
| **Effect when enabled** | `installer.py::ensure_plugin('rtk' \| 'nines' \| 'ui-pro')` may invoke `curl` / `cargo install` / `npm install` / `pip install -e` from the workflow's `precondition.config.ensure_plugins` stage |
| **Why default-on?** | The v8.3.0 PV-01 contract trades a one-time ~5-30s install latency for full workflow capability — operators who have offline / pinned-version requirements opt out by setting `0` |
| **R5 strict?** | N/A — this flag governs an explicit subprocess (the install itself); R5 zero-overhead does not apply |
| **Reference** | `CHANGELOG.md` §[v8.3.0-pv01] for the PV-01 contract; `runtime-plugins.yaml` for the plugin registry |

## 3. Test-fixture flags (NOT runtime flags)

These flags are read ONLY by tests (`tests/`) and never by production
code. They appear in this reference because operators sometimes set
them in CI configs and need to know they have NO production effect.

### 3.1 `DEVOLAFLOW_NINES_EDITABLE_PATH` — local NineS editable install path

| Field | Value |
|---|---|
| **Owner** | `tests/test_plugins.py` (line 549, fixture only) |
| **Default** | `/home/agent/workspace/NineS` |
| **Effect** | When the plugin-install integration test runs, it uses this path as the local fallback for `pip install -e <path>` instead of fetching from PyPI |
| **Production effect** | NONE — production paths use `pip install nines==<min_version>` per `runtime-plugins.yaml` |
| **Per S-7** | This is a test-side override; the production reference file MUST NOT hardcode this path |

### 3.2 `DEVOLAFLOW_PROBE_SCENARIO` — compression probe scenario selector

| Field | Value |
|---|---|
| **Owner** | `tests/conftest.py::_compression_e2e_workspace` |
| **Default** | `easy` |
| **Effect** | Selects the scenario tier for `tests/test_e2e_compression.py` — `easy` (~500-token artifact, 5 entities), `medium` (~5K tokens, 20 entities), `hard` (~15K tokens, 50 entities) |
| **Production effect** | NONE — runtime never reads this |

### 3.3 `DEVOLAFLOW_MOCK_KEY` — mock LLM provider key

| Field | Value |
|---|---|
| **Owner** | `src/devolaflow/llm_client.py::_API_KEY_ENV_VARS["mock"]` |
| **Introduced** | v8.0.0 P-12 (Stage B abstractive client) |
| **Default** | unset |
| **Effect** | When the LLM Stage B client runs with `provider="mock"`, this env var is consulted as the API key; tests use any non-empty value, production uses provider-specific keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc.) |
| **Production effect** | Test-only path — production never selects `provider="mock"` |

## 4. Forward-declared gate-primitive flags (PV-06 flip target)

These flags are **declared in this reference** (and in
`references/decomposition-gate.md` §11) but **NOT yet wired** in
`src/devolaflow/`. They ship as part of v9.0.0 Theme T5 (PV-06 = v8.5.1).
Codifying them here in v8.5.0 PV-05 means:

* W-20 (env-flag reuse vs new-flag policy) has a complete inventory at
  the moment T5 starts, so PV-06 cannot accidentally re-use a flag name
  for a different purpose.
* Operators reading SKILL.md → `references/env-flags.md` get the full
  surface in one place rather than chasing the gate-primitive table in
  `decomposition-gate.md`.

| # | Flag | Owner module (PV-06 target) | Per-profile default | Companion config key |
|---|------|------------------------------|---------------------|----------------------|
| 1 | `DEVOLAFLOW_TOKEN_BUDGET_BREAKER` | `src/devolaflow/gate/budget.py::TokenBudgetBreaker` | OFF on standard/relaxed; ESCALATE on strict/audit | `gate.budget_breaker_enabled` |
| 2 | `DEVOLAFLOW_CYCLE_DETECTOR`       | `src/devolaflow/gate/cycle_detector.py`               | OFF (opt-in)                                    | `gate.cycle_detection`         |
| 3 | `DEVOLAFLOW_GATE_RATCHET`         | `src/devolaflow/gate/ratchet.py`                      | OFF (opt-in)                                    | `gate.ratchet_enabled`         |
| 4 | `DEVOLAFLOW_COMPLEXITY_DETECTOR`  | `src/devolaflow/gate/complexity_detector.py`          | OFF (opt-in)                                    | `gate.complexity_detection`    |
| 5 | `DEVOLAFLOW_AC_GEN`               | `src/devolaflow/ac_generator.py`                      | OFF (opt-in companion to legacy `accept` list)  | `ac_generator.enabled`         |
| 6 | `DEVOLAFLOW_LEGIBILITY_CHECK`     | `src/devolaflow/legibility/scorer.py`                 | OFF (opt-in)                                    | `decomposition.legibility_check` |

**Theme T5 PV-06 flip plan**: primitives 1, 3, 4, 5, 6 are scheduled to
flip to ON for `audit` + `strict` decomposition-enabled profiles when the
post-flip composite EvoBench score (≥ 90 floor per W-4) holds. Primitive
2 stays opt-in (the legacy `accept` list remains the default-on path).
The flip is the v9.0.0 PV-06 deliverable per playbook §6.6.

## 5. Karpathy 4-primitive defaults (default-ON, no flag)

The 4 Karpathy-derived behavioral primitives (BG-001..BG-004) ship
**default-ON** in v8.0.0 P-08 and have **NO env-flag override**.
Operators who want to disable them adjust the per-profile
`behavioral_guidelines` dispatch field (canonical_order position 14).

| BG | Primitive | Default | Override mechanism |
|----|-----------|---------|--------------------|
| BG-001 | `think_first`     | ON | dispatch field `behavioral_guidelines.think_first=false` |
| BG-002 | `simplicity_check`| ON | dispatch field `behavioral_guidelines.simplicity_check=false` |
| BG-003 | `surgical_scope`  | ON | dispatch field `behavioral_guidelines.surgical_scope=line\|chunk\|module\|file` |
| BG-004 | `goal_loop`       | ON | dispatch field `behavioral_guidelines.goal_loop=false` |

**Why no env-flag?** The behavioral primitives are part of the
**dispatch payload contract** — they ship at the per-task granularity,
not the per-process granularity. An env-flag would force every L3 Task
Agent in a process to share the same value; the dispatch field allows
per-task tuning. See `references/behavioral-guidelines.md` for the full
BG-001..BG-004 spec.

## 6. R5 strict pattern — the conjunction contract

For the R5 strict flags (#2.2 `DEVOLAFLOW_RTK_PROXY`, #2.3
`DEVOLAFLOW_RTK_PROXY_TIER2`, #2.4 `DEVOLAFLOW_MEMORY_ROUTER`) the
"feature is active" predicate is the **conjunction** of:

1. env-var read returns EXACTLY `"1"` (rejects `"true"`, `"yes"`, `"on"`, `"01"`, `""`)
2. The companion runtime probe succeeds (e.g. `shutil.which("rtk")` for #2.2, `Path.exists` for #2.4's index file)

When EITHER side is missing, the feature is a **zero-IO no-op**:

* NO `Path.read_text` (codified by `tests/test_*_r5_strict_off.py` watchers)
* NO `subprocess.run`
* NO `shutil.which` (for the strict-affected modules — the post-activation `ShellProxyConfig` caches the result)
* NO `import` of the heavy code path (the watcher tests prove the cold-path import is not triggered)

This is the **R5 strict contract** that lets the v8.x codebase ship
~3000 tests where the new opt-in surfaces add ZERO baseline cost when
unset. The contract is verified at FOUR layers:

| Layer | Test file | Mechanism |
|-------|-----------|-----------|
| Unit  | `tests/test_shell_proxy_disabled_is_noop.py` | `monkeypatch.setattr(subprocess, 'run', ...)` watcher |
| Unit  | `tests/test_memory_router.py::TestLookupCaseR5StrictOff` | `monkeypatch.setattr(Path, 'read_text', ...)` watcher |
| Unit  | `tests/test_shell_proxy_commands.py::TestLoadR5StrictOff` | same Path.read_text watcher |
| EvoBench | `benchmarks/devolaflow_context/scenarios/{shell_proxy_disabled,memory_router_fastpath,command_mapping_density}.yaml` | composite floor 90 vs `simple_implementation` baseline; actual ~99 |

## 7. Adding a NEW env-flag — W-20 enforcement checklist

Before authoring a NEW `DEVOLAFLOW_*` env-flag, an L3 Task Agent MUST
walk the W-20 checklist:

1. **Inventory check** — read this reference §2..§5 to confirm no
   existing flag covers the same surface.
2. **Behavioural orthogonality test** — would the new flag activate
   independently of every existing flag? If NO (e.g. it always
   piggybacks on an existing flag), REUSE the existing flag with a
   sub-condition (the v8.3.4 PV-04 command-mapping layer is the
   canonical example: it REUSES `DEVOLAFLOW_RTK_PROXY` rather than
   adding `DEVOLAFLOW_COMMAND_MAPPING`).
3. **R5 strict design** — if the new flag is a runtime activation flag
   (not a config tuning knob), the companion code path MUST be
   zero-IO when the flag is unset. Authors MUST author a watcher test
   in the same PV that proves zero IO.
4. **Reference update** — add the new flag to §2.1..§2.5 (active) or
   §4 (forward-declared) in this reference IN THE SAME PR as the
   handler implementation.
5. **CHANGELOG entry** — the PR's CHANGELOG entry MUST cite the new
   flag by name in the §"Operator-visible behavior change" section.

A NEW env-flag PR that fails any of the 5 checks is a **W-20
violation** — block at code review and either remove the flag (REUSE)
or document the orthogonality argument explicitly.

## 8. Cross-references

* SKILL.md §"Reference Navigation Guide" Tier-2 row — discovery surface
* `references/shell-proxy.md` §3.1 — RTK + memory-router env-flag table (cross-link from §2.2..§2.4)
* `references/decomposition-gate.md` §11 — gate primitive table (cross-link from §4)
* `references/plan-mode-enforcement.md` §2 — plan-mode detection table (cross-link from §2.1)
* `references/behavioral-guidelines.md` — BG-001..BG-004 spec (cross-link from §5)
* `AGENTS.md` §"W-20" — env-flag reuse vs new-flag policy (the rule this reference enforces)
* `.local/research/v9.0.0_pv05_design.md` §1 — full PV-05 audit + decision rationale
* `.local/research/adr/v9-ADR-005-nines-hygiene-and-w-rules.md` D5 — ADR for AGENTS.md ceiling bump + W-rule batch

---

> Maintenance contract — this reference is the **single source of
> truth** for env-flag inventory. PV-06 (Theme T5 5-primitive flip)
> MUST update §4 to move the flipped primitives from "forward-declared"
> to "active runtime flags" (§2). The W-20 checklist (§7) MUST stay
> current with the cycle-N inventory.
