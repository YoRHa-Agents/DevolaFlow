---
id: "agent/references/host-bridges"
version: "17.4.0"
purpose: >
  Operating contract for the host-bridge core (src/devolaflow/hostbridge/)
  that routes host-agent tool events (file writes, shell commands) from
  Cursor, Claude Code, Codex, KimiCode, DSH, and GitHub Copilot into DevolaFlow's
  lifecycle hook chain for S-8 owned-files boundary enforcement, gated
  by the R5-strict DEVOLAFLOW_HOST_ENFORCE flag (env-flags.md §2.18).
triggers:
  - "wiring host-agent hooks into boundary enforcement"
  - "configuring DEVOLAFLOW_HOST_ENFORCE"
  - "debugging an unexpected host-side write deny"
  - "reading the hostbridge audit ledger"
  - "installing the bridge for a new host"
tier: 2
token_estimate: 2400
dependencies:
  - "agent/SKILL.md"
  - "agent/references/env-flags.md"
  - "agent/references/agent-workspace.md"
  - "agent/references/shell-proxy.md"
  - "agent/references/host-contract.md"
last_updated: "2026-08-25"
---

# Host Bridges

## Purpose

Operating contract for the **host-bridge core** (`src/devolaflow/hostbridge/`)
that routes host-agent tool events — file writes and shell commands — from
five hosts (Cursor, Claude Code, Codex, KimiCode, DSH) into DevolaFlow's
lifecycle hook chain for S-8 owned-files boundary enforcement. Pairs with
the per-host config artifacts (`.cursor/hooks.json`, `.claude/settings.json`,
`.codex/hooks.json`, `packages/dsh-plugin/`), the enforcement flag
`DEVOLAFLOW_HOST_ENFORCE` (`references/env-flags.md` §2.18), the Host Support
Contract (`references/host-contract.md`), and the audit
ledger `.local/telemetry/hostbridge.jsonl`. Closes G17-B1 per
`docs/cycle-archive/v17.0.0` design §D-R2-1..§D-R2-4.

## When to Load

Load this reference when wiring host-agent tool events (Cursor/Claude/
Codex/Kimi/DSH hooks) into boundary enforcement, configuring
`DEVOLAFLOW_HOST_ENFORCE`, debugging an unexpected host-side deny, or
reading the host-bridge audit ledger.

## 1. Why a host bridge

Before v17.0.0, S-8 (no writes outside owned files) was enforced only on
the framework's OWN write surface (`fire_file_write` in
`src/devolaflow/lifecycle/runtime_wiring.py`), and `pre_shell_call` had
zero production callers. Host IDE tools (Write / StrReplace / Bash / …)
bypassed both entirely. The bridge closes that gap at the host-hook
layer: every participating host delivers its pre-tool-use event to
`python -m devolaflow.hostbridge --host <host>` on stdin; the bridge
normalizes the event, evaluates it against the union of active-change
`owned_files.txt` manifests through `run_hooks("file_write", ...)`, and
answers in the host's own block protocol.

## 2. Six-host matrix

| Host | Config surface | Intercepted events | Block mechanism | Degradation notes |
|---|---|---|---|---|
| Cursor | `.cursor/hooks.json` + `.cursor/hooks/devola-boundary.sh` (project-level, committed) | `preToolUse` matcher `Write\|StrReplace`; `beforeShellExecution` | stdout JSON `{"permission": "deny", "agent_message": ...}` (exit always 0) | No `failClosed` set — every error path allows |
| Claude Code | `.claude/settings.json` hooks block + `.claude/hooks/devola-boundary.sh` (project-level, committed) | `PreToolUse` matcher `Edit\|Write\|MultiEdit` and `Bash` | exit 2 + reason on stderr | Merge is additive — foreign settings keys/hook entries preserved |
| Codex | `.codex/hooks.json` + `.codex/hooks/devola-boundary.sh` | `PreToolUse` matcher `^(Bash\|apply_patch)$` | exit 2 + stderr | **Partial coverage** (upstream documents PreToolUse exemptions) and the project-level hooks file requires an interactive `/hooks` trust step before it fires |
| KimiCode | user-level `~/.kimi-code/config.toml` `[[hooks]]` (Beta) — NO project file possible | `PreToolUse` matcher `WriteFile\|StrReplaceFile\|Shell` | exit 2 (hook timeout = fail-open) | Beta + user-level: run `python -m devolaflow.hostbridge install kimi` to print the TOML snippet; operator pastes it manually |
| DSH | cordis plugin `packages/dsh-plugin/` (npm `@yorha-agents/devola-flow-dsh`) | `tools/pre-execute` waterfall (tool-level, all tools) | waterfall `{kind: 'deny', reason}` | Plugin channel required for blocking; sidecar/Center-only deployments degrade to post-hoc ledger audit (see the plugin README) |
| GitHub Copilot | `.github/hooks/devola-boundary.json` + wrapper (project-level) | `preToolUse` command hook for file and shell tools | stdout JSON `{"permissionDecision": "deny", "message": ...}` (exit always 0) | Copilot's native command hook is fail-closed; the wrapper absorbs internal errors and normalizes DevolaFlow's fail-open contract |

## 3. Enforcement-flag contract (`DEVOLAFLOW_HOST_ENFORCE`)

* R5 strict: only the literal string `"1"` activates enforcement.
  Absent / `"0"` / `"true"` / `"01"` → the bridge (and the bash
  wrappers, in pure bash without starting Python) allow with ZERO
  filesystem IO.
* NEW flag per W-20 §3 (orthogonality argument + checklist walk in
  `references/env-flags.md` §2.18): host tool-event interception is a
  different runtime surface than `DEVOLAFLOW_AGENT_WORKSPACE`
  (workspace scaffolding + framework-internal `fire_*` adapters).
  Operators may enforce without scaffolding, or scaffold without
  enforcing.
* Fail-open everywhere: unknown/unparseable stdin, missing Python,
  hook timeout, or ANY internal bridge exception → allow (internal
  errors additionally ledger `"verdict": "error_allow"`, S-5).

## 4. Decision semantics (v17 R2)

1. Flag off → allow (zero IO fast path; nothing is ledgered).
2. `file_write` — no active change under `.local/.agent/active/` →
   allow. Otherwise the owned set is the UNION of every active
   change's `owned_files.txt`, plus the S-8 §2/§3 exemptions
   materialised the same way `lifecycle/runtime_wiring.py` does
   (targets inside a change folder itself or `.local/.agent/handoff/`).
   A `CFO006` blocker from `run_hooks("file_write", ...)` denies,
   quoting the path and active change id(s). Codex `apply_patch`
   patches are split into per-file targets (`*** Update/Add/Delete
   File:` markers); every target must pass.
3. `shell` — ALWAYS allowed this round. The bridge is the first
   production caller of the `pre_shell_call` hook; its rewrite
   metadata (`wrapped_cmd` / `proxy_enabled` / `was_rewritten`) is
   recorded in the ledger as advisory evidence only. Advisory errors
   are swallowed into the ledger, never raised (S-5).
4. Unknown event kind → allow + ledger line.

## 5. Install per host

```bash
# project-level configs, idempotent regeneration (dogfooded in-repo):
python -m devolaflow.hostbridge install cursor
python -m devolaflow.hostbridge install claude   # merges .claude/settings.json additively
python -m devolaflow.hostbridge install codex    # then trust via /hooks inside Codex

# user-level snippet (Beta): prints the [[hooks]] TOML block to paste
# into the KimiCode user config:
python -m devolaflow.hostbridge install kimi

# DSH (plugin channel):
dsh plugin add @yorha-agents/devola-flow-dsh
```

Then opt in per session/CI job:

```bash
export DEVOLAFLOW_HOST_ENFORCE=1
```

The bash wrappers prefer `.venv/bin/python` at the repo root, falling
back to `python3` on PATH, and allow when neither exists.

## 6. Audit-ledger schema (`.local/telemetry/hostbridge.jsonl`)

One JSON object per enforced decision (append-only JSONL; parent dirs
auto-created; ledger failures are logged and never affect the verdict):

| Field | Type | Notes |
|---|---|---|
| `ts` | str | ISO-8601 UTC timestamp |
| `host` | str | `cursor` / `claude` / `codex` / `kimi` / `dsh` / `copilot` |
| `kind` | str | `file_write` / `shell` / `unknown` |
| `path` | str? | write target (repo-relative when resolvable) |
| `cmd` | str? | first 120 chars of the shell command |
| `verdict` | str | `allow` / `deny` / `error_allow` |
| `reason` | str | human-readable verdict rationale |
| `elapsed_ms` | float | bridge decision latency |
| `active_changes` | list? | change ids whose manifests were unioned |
| `shell_advisory` | obj? | `pre_shell_call` rewrite metadata |
| `shell_advisory_error` / `error` | str? | swallowed-error evidence (S-5) |

The ledger feeds the v17 R7 evidence round (real per-event telemetry
instead of fixture-only baselines).

## 7. Stdin shapes accepted (normalization contract)

Precedence: CLI `--event` override > DSH explicit `kind` > tool-name
classification (`tool_name` before `tool`) > `hook_event_name` hint >
shape inference (path → file_write; command → shell) > `unknown`
(fail-open). Path keys inside `tool_input` (then top level): `path` >
`file_path` > `target_file`.

* Cursor: `{"tool": "Write"|"StrReplace", "tool_input": {"path"|"file_path"|"target_file": ...}}`;
  shell: `{"command": "..."}` (optionally with `hook_event_name`).
* Claude Code: `{"tool_name": "Write"|"Edit"|"MultiEdit", "tool_input": {"file_path": ...}}`;
  `{"tool_name": "Bash", "tool_input": {"command": ...}}`.
* Codex: same family; `apply_patch` input text is scanned for
  `*** Update/Add/Delete File:` targets (no target → shell-kind
  advisory allow).
* Kimi: `{"tool_name": "WriteFile"|"StrReplaceFile"|"Shell", "tool_input": {...}}`.
* DSH: `{"tool": ..., "kind": "file_write"|"shell", "path": ..., "command": ...}`
  (authored by our own plugin).
* Copilot: `{"toolName": ..., "toolArgs": ...}` or the VS Code-compatible
  `{"tool_name": ..., "tool_input": ...}`; both forms normalize to one event.

Fixtures for every shape live in `tests/fixtures/hostbridge/`.

## 8. Session-start resume adapter (v17 R4)

`python -m devolaflow.hostbridge resume [--host cursor|claude]` prints a
compact checklist-resume summary on stdout at session start for the host
to inject as context (change-id, disposition, resume round, checked
count, next-round selection, and a GOAL_DRIFT warning when goal.md
changed since the last checkpoint). Gating REUSES
`DEVOLAFLOW_AGENT_WORKSPACE=1` per W-20 (session-start resume IS the
A-6.2 workspace-engagement surface — NOT `DEVOLAFLOW_HOST_ENFORCE`);
any other value → empty stdout, exit 0, zero filesystem IO. Read-only
throughout; 0 active changes → silent; >1 → only the change-id list
(never auto-picked); any exception → empty stdout, exit 0, plus an
`error_allow` line in the audit ledger (kind `session_resume`, S-5).

Wired hosts: Cursor (`sessionStart` in `.cursor/hooks.json` →
`.cursor/hooks/devola-session.sh`) and Claude Code (`SessionStart`
matcher `startup|resume` in `.claude/settings.json` →
`.claude/hooks/devola-session.sh`), both regenerated by the §5
installers. **Deliberately NOT wired this round**: Codex (project-level
hooks require the interactive `/hooks` trust step — session injection
would silently no-op for most operators), KimiCode (user-level Beta
config only; no project-level session surface to install), and DSH
(session context goes through the cordis plugin channel — deferred to a
later plugin release). These hosts degrade gracefully: no session hook
means no injected context, and boundary enforcement (§2) is unaffected.

## Cross-References

- `references/env-flags.md` §2.18 — the enforcement flag row + W-20 walk
- `references/agent-workspace.md` — change folders, `owned_files.txt`, S-8
- `references/shell-proxy.md` — the `pre_shell_call` advisory machinery
- `references/agent-hierarchy.md` — L0/L1/L2 layering the boundary protects
- `src/devolaflow/hostbridge/` — normalize / decision / audit / install
- `tests/test_hostbridge.py` + `tests/test_hostbridge_disabled_is_noop.py`

## History

- Scaffolded by `scripts/scaffold_reference.py` (D-X-2).
- v17.0.0 R2 — first substantive body: five-host matrix, enforcement
  flag contract, decision semantics, install guide, ledger schema
  (G17-B1 closure per §D-R2-1..§D-R2-4).
- v17.0.0 R4 — session-start resume adapter (§8): Cursor/Claude session
  hooks, W-20 reuse of `DEVOLAFLOW_AGENT_WORKSPACE`, Codex/Kimi/DSH
  downgrade rationale (§D-R4-1).
- v17.4.0 — HSC matrix adds Copilot's `preToolUse` bridge and links host
  declarations to the canonical `hosts.yaml` contract.
