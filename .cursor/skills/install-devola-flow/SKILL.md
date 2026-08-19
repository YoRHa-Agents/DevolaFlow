---
name: install-devola-flow
description: >-
  Install or update the DevolaFlow workflow orchestration skill into the
  user-wide Cursor skill directory (~/.cursor/skills/devola-flow/) plus
  the matching rules file, AND into the user-wide Claude Code skill
  directory (~/.claude/skills/devola-flow/). Use when the user asks to
  install devola-flow, install devolaflow globally, setup devola-flow on
  this machine, update devola-flow, install devola for claude or claude
  code, or bootstrap devola for all Cursor / Claude projects. Matches
  Chinese phrasings such as "安装 devola-flow", "全局安装 devola",
  "把 devola 装到 cursor", "把 devola 装到 claude",
  "全局安装 devola 到 cursor 和 claude", "更新 devola-flow".
---

# Install DevolaFlow (Global Cursor + Claude)

Drives the canonical installer at
`https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh`
so the `devola-flow` skill is available user-wide in **Cursor**
(`~/.cursor/skills/devola-flow/`)
**and Claude Code** (`~/.claude/skills/devola-flow/`).

## When to Trigger

Activate on any of these user intents (EN or ZH):

- "install devola-flow" / "安装 devola-flow" / "安装 devola"
- "setup devola globally" / "全局安装 devola-flow"
- "update devola-flow" / "升级 devola" / "/update-devola"
- "bootstrap devola-flow on this machine"
- "把 devola 装到 cursor"
- "install devola for claude" / "install devola for claude code"
- "把 devola 装到 claude" / "把 devola 全局装到 claude"
- "全局安装 devola 到 cursor 和 claude"

If the user scopes to project-local (`--project`) follow the matching
**Variants** block below instead of the default flow.

## Defaults

| Question | Default |
|---|---|
| Targets | **Cursor + Claude Code** (both, user-global) |
| Scope | `--global` (writes under `$HOME/.cursor` and `$HOME/.claude`) |
| Source | `main` branch of `YoRHa-Agents/DevolaFlow` |
| Behaviour on partial failure | Stop and report, never half-install |
| Behaviour when only one tool is present | Install to whichever of `~/.cursor` / `~/.claude` exists; warn that the other wasn't found (not an error) |
| Behaviour when neither tool is present | Stop; tell user to install Cursor or Claude Code first |

## Prerequisites

Run these checks first:

```bash
command -v curl >/dev/null && echo "curl ok"
command -v bash >/dev/null && echo "bash ok"
curl -fsI --max-time 30 https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh \
  >/dev/null && echo "network ok"
test -d ~/.cursor && echo "~/.cursor present" || echo "~/.cursor absent"
test -d ~/.claude && echo "~/.claude present" || echo "~/.claude absent"
```

Stop rules:

- Stop ONLY if **both** `~/.cursor` and `~/.claude` are absent — tell
  the user to install Cursor or Claude Code first.
- If exactly one is present, proceed with **that target only** and
  explicitly note in the Step 1 plan which one was skipped (this is a
  non-error warning, not a failure).
- If the network check fails or times out, jump to **Network Fallback
  (Proxy)** before giving up.

## Execution Flow

### Step 1 — Announce the plan

Based on the Prerequisites output, tell the user exactly which targets
will be installed. Omit any target whose parent dir is absent and mark
it "skipped (~/.X absent)". Example when both are present:

```
Install DevolaFlow globally:
  • Cursor       → ~/.cursor/skills/devola-flow/        (SKILL + refs + examples)
  • Claude Code  → ~/.claude/skills/devola-flow/        (SKILL + refs + examples)
                   (no separate rules file — rules are inlined in SKILL.md)
Source: github.com/YoRHa-Agents/DevolaFlow (branch: main)
```

### Step 2a — Install to Cursor (global)

Conditional on `~/.cursor` present. Skip this step if Cursor is absent.

```bash
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh \
  | bash -s cursor --global
```

Expected artifacts on success:

```
~/.cursor/skills/devola-flow/SKILL.md
~/.cursor/skills/devola-flow/references/         (9 files)
~/.cursor/skills/devola-flow/examples/           (3 files)
~/.cursor/skills/devola-flow/.devola-flow-version
```

The installer prints one `ok` line per file; any `✗ failed:` must be
treated as a Step 2a failure and surfaced up.

### Step 2b — Install to Claude Code (global)

Conditional on `~/.claude` present. Skip this step if Claude is absent.

```bash
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh \
  | bash -s claude --global
```

Expected artifacts on success:

```
~/.claude/skills/devola-flow/SKILL.md
~/.claude/skills/devola-flow/references/         (9 files)
~/.claude/skills/devola-flow/examples/           (3 files)
~/.claude/skills/devola-flow/.devola-flow-version
```

**Note:** There is **no** separate rules file for Claude Code — the
rules are inlined in `SKILL.md`. Any `✗ failed:` line must be treated
as a Step 2b failure and surfaced up.

### Step 3 — Verify

Run only the block(s) matching the target(s) that were actually
installed. Do not report success until **all** applicable checks return
`[PASS]`.

**Cursor block** (skip if Step 2a was skipped):

```bash
test -f ~/.cursor/skills/devola-flow/SKILL.md      && echo "[PASS] Cursor SKILL.md"      || echo "[FAIL] Cursor SKILL.md"
[ "$(ls ~/.cursor/skills/devola-flow/references 2>/dev/null | wc -l)" = "10" ] \
                                                   && echo "[PASS] Cursor 10 references" || echo "[FAIL] Cursor references"
[ "$(ls ~/.cursor/skills/devola-flow/examples   2>/dev/null | wc -l)" = "3" ] \
                                                   && echo "[PASS] Cursor 3 examples"    || echo "[FAIL] Cursor examples"
UPSTREAM=$(curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/src/devolaflow/__init__.py \
  | grep '__version__' | head -1 | sed 's/.*"\(.*\)".*/\1/')
LOCAL=$(head -1 ~/.cursor/skills/devola-flow/.devola-flow-version)
[ "$UPSTREAM" = "$LOCAL" ] && echo "[PASS] Cursor v$LOCAL matches upstream" \
                          || echo "[FAIL] Cursor mismatch: upstream=$UPSTREAM local=$LOCAL"
```

**Claude block** (skip if Step 2b was skipped):

```bash
test -f ~/.claude/skills/devola-flow/SKILL.md     && echo "[PASS] Claude SKILL.md"     || echo "[FAIL] Claude SKILL.md"
[ "$(ls ~/.claude/skills/devola-flow/references 2>/dev/null | wc -l)" = "10" ] \
                                                  && echo "[PASS] Claude 10 references" || echo "[FAIL] Claude references"
[ "$(ls ~/.claude/skills/devola-flow/examples   2>/dev/null | wc -l)" = "3" ] \
                                                  && echo "[PASS] Claude 3 examples"   || echo "[FAIL] Claude examples"
UPSTREAM=$(curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/src/devolaflow/__init__.py \
  | grep '__version__' | head -1 | sed 's/.*"\(.*\)".*/\1/')
LOCAL=$(head -1 ~/.claude/skills/devola-flow/.devola-flow-version)
[ "$UPSTREAM" = "$LOCAL" ] && echo "[PASS] Claude v$LOCAL matches upstream" \
                          || echo "[FAIL] Claude mismatch: upstream=$UPSTREAM local=$LOCAL"
```

`head -1` is important because older stamps may contain a timestamp
second line that is not part of the semver.

### Step 4 — Report

Use this format verbatim (substitute `{VERSION}`, `{CURSOR_STATUS}`,
`{CLAUDE_STATUS}`):

```
✓ DevolaFlow v{VERSION} installed
  Cursor (global): {CURSOR_STATUS}
    Path  : ~/.cursor/skills/devola-flow/   (SKILL + 8 refs + 3 examples)
    Rules : (inlined in SKILL.md — no separate file since v15.0.0)
  Claude Code (global): {CLAUDE_STATUS}
    Path  : ~/.claude/skills/devola-flow/   (SKILL + 8 refs + 3 examples)
    Rules : (inlined in SKILL.md — no separate file)
  Docs  : https://yorha-agents.github.io/DevolaFlow/
  Repo  : https://github.com/YoRHa-Agents/DevolaFlow
  Re-run: trigger this skill again, or
          curl -fsSL <...>/install.sh | bash -s update
```

`{*_STATUS}` is one of: `"v7.1.1 installed"`, `"skipped (~/.X absent)"`,
or `"failed — see Step 2X"`.

## Network Fallback (Proxy)

If the Step 2 pipe hangs or the Prerequisites network check fails
(`curl: (28) Operation timed out`, `Could not resolve host`, empty body
after TLS handshake, etc.), **do not abort** — try a proxy first.

### Step A — Probe through a known HTTP proxy

Replace the host below with whichever proxy is reachable in the user's
environment (corporate dev-proxy, shared regional mirror, etc.). One
proxy that has been observed to work in restricted sandboxes:

```bash
export http_proxy=http://10.10.64.15:18000
export https_proxy=http://10.10.64.15:18000
time curl -fsSL --max-time 30 \
  https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh \
  -o /tmp/devola-probe.sh && echo "proxy ok ($(wc -c < /tmp/devola-probe.sh) bytes)"
```

If `proxy ok` prints, proceed to **Step B**. If it still fails, ask the
user which proxy/mirror the machine uses and retry; never guess
credentials.

### Step B — Re-run the install under the same proxy

With `http_proxy` / `https_proxy` exported in the current shell, the
installer's own `curl` calls inherit the proxy automatically:

```bash
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh \
  | bash -s cursor --global
```

Then run **Step 3 — Verify** as usual. If verification passes, the
proxy-based install is as good as a direct one; the installed skill
contents are byte-identical.

### Step C — Clean up (optional)

If the proxy is not needed for subsequent shells, unset it:

```bash
unset http_proxy https_proxy
```

Common sandbox symptom to match on: TLS handshake to
`raw.githubusercontent.com` succeeds over IPv6, then the request stalls
with zero body bytes. Forcing `curl -4` usually avoids the IPv6 path; if
that still fails, fall through to the proxy fallback above.

## Variants

### Cursor only (global)

When the user explicitly scopes to Cursor only:

```bash
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh \
  | bash -s cursor --global
```

### Claude only (global)

When the user explicitly scopes to Claude Code only:

```bash
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh \
  | bash -s claude --global
```

### Both Cursor + Claude (global) — default

Run both commands sequentially (this is the default when both
`~/.cursor` and `~/.claude` are present):

```bash
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh \
  | bash -s cursor --global
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh \
  | bash -s claude --global
```

### Project-local (current repo)

Drop `--global` to write under the current repository instead of
`$HOME`:

```bash
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh \
  | bash -s cursor
```

Claude Code also supports project-local — `bash -s claude` (no
`--global`) writes to `./.claude/skills/devola-flow/`.

### Update existing installs on this machine

Refreshes whichever installs the installer detects — now auto-detects
**both** Cursor and Claude installs. `do_update` walks
`~/.cursor/skills/devola-flow/`, `~/.claude/skills/devola-flow/`, and
the project-local equivalents, refreshing each that exists:

```bash
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh \
  | bash -s update
```

### All supported tools at once

Covers Cursor, Codex, Claude, Copilot, KimiCode, Windsurf, Zed, Cline,
and Roo. Only use when the user explicitly asks for a multi-tool
install — this skill's default scope is Cursor + Claude:

```bash
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh \
  | bash -s all --global
```

## Failure Handling

| Symptom | Likely cause | Action |
|---|---|---|
| `curl: (6) Could not resolve host` | No network / DNS | Try **Network Fallback (Proxy)**; if still failing, stop |
| `curl: (28) Operation timed out` | Firewall / IPv6 black-hole to `raw.githubusercontent.com` | Try **Network Fallback (Proxy)**; `-4` alone can also help |
| `✗ failed: SKILL.md (after 3 attempts)` | GitHub rate-limit or transient 5xx | Wait 30 s, retry once; if still failing, stop and surface the filename |
| `Unknown target: ...` from installer | Typo in target argument | Re-run with `cursor`, `claude`, or `update` |
| Version stamp differs from upstream | Partial download | Re-run `bash -s update`; if still mismatched, escalate |
| `~/.cursor` missing | Cursor not installed on this machine | Skip the Cursor step; Claude install still proceeds. If BOTH `~/.cursor` and `~/.claude` are missing, stop and tell the user to install at least one of them first |
| `~/.claude` missing | Claude Code not installed | Skip the Claude step; Cursor install still proceeds. If BOTH `~/.cursor` and `~/.claude` are missing, stop and tell the user to install at least one of them first |
| Claude version stamp contains only a timestamp (no semver line) | Legacy install predating the version-fetch upgrade | Re-run `bash -s update` — new installs stamp the canonical `X.Y.Z` as the FIRST line |

Never silently skip `✗ failed:` lines in the installer output. Report
the exact filename(s) that failed.

## Post-install

- The skill auto-activates on Cursor / Claude triggers such as
  "implement feature", "fix bug", "run workflow", "hotfix".
- Uninstall:

  ```bash
  # Cursor (the legacy ~/.cursor/rules/devola-flow-rules.mdc pointer
  # was retired in v15.0.0 — remove it too if present from old installs)
  rm -rf ~/.cursor/skills/devola-flow \
         ~/.cursor/rules/devola-flow-rules.mdc
  # Claude Code
  rm -rf ~/.claude/skills/devola-flow
  ```

- To make **this** `install-devola-flow` skill available in every
  project (not only inside the DevolaFlow repo), copy it to the
  user-wide Cursor skills directory:

  ```bash
  mkdir -p ~/.cursor/skills/install-devola-flow
  cp .cursor/skills/install-devola-flow/SKILL.md \
     ~/.cursor/skills/install-devola-flow/SKILL.md
  ```

## Security Notes

- The installer is piped from the internet into `bash`. The canonical
  source is the public `YoRHa-Agents/DevolaFlow` repo on GitHub; review
  `scripts/install.sh` there before trusting it on a new machine.
- All writes stay inside `~/.cursor/` and `~/.claude/` — no `sudo`, no
  system paths, no credentials.
- Downloads are anonymous HTTPS against `raw.githubusercontent.com`
  (directly or via proxy).
