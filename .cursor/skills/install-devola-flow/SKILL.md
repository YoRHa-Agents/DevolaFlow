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

> **Installation SSOT: `scripts/install.sh`** (canonical remote:
> `https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh`).
> This skill carries NO install procedure of its own — every step below
> DELEGATES to that installer, which owns the target semantics
> (`cursor, codex, claude, copilot, kimicode, windsurf, zed, cline, roo,
> local, standalone, all, auto (default), update` — see its header
> comment), the per-file download/retry logic, the installed artifact
> layout, and the `.devola-flow-version` stamping. If this document and
> the script ever disagree, the script wins.

This skill's default job: make the `devola-flow` skill available
user-wide in **Cursor** (`~/.cursor/skills/devola-flow/`) **and Claude
Code** (`~/.claude/skills/devola-flow/`) by invoking the installer with
the right target and scope.

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
Install DevolaFlow globally (via scripts/install.sh):
  • Cursor       → ~/.cursor/skills/devola-flow/
  • Claude Code  → ~/.claude/skills/devola-flow/
Source: github.com/YoRHa-Agents/DevolaFlow (branch: main)
```

### Step 2 — Delegate to the installer

Run one installer invocation per present target; skip a target whose
parent directory is absent:

```bash
# Cursor (skip if ~/.cursor absent)
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh \
  | bash -s cursor --global

# Claude Code (skip if ~/.claude absent)
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh \
  | bash -s claude --global
```

The success signal is the installer's OWN output: exit code 0, one `ok`
line per downloaded file, and zero `✗ failed:` lines. Do NOT re-check
the downloaded set against a hardcoded file manifest here — the
artifact list is owned by `scripts/install.sh` and changes across
versions. Any `✗ failed:` line means the invocation failed; surface the
exact filename(s) verbatim.

### Step 3 — Verify (lean)

Per installed target, confirm the two installer-owned markers exist:
the skill entry point and the version stamp the installer wrote.

```bash
for ROOT in ~/.cursor ~/.claude; do
  DIR="$ROOT/skills/devola-flow"
  [ -d "$DIR" ] || continue
  test -f "$DIR/SKILL.md" && echo "[PASS] $DIR/SKILL.md" || echo "[FAIL] $DIR/SKILL.md"
  test -f "$DIR/.devola-flow-version" \
    && echo "[PASS] stamp: $(head -1 "$DIR/.devola-flow-version")" \
    || echo "[FAIL] $DIR/.devola-flow-version missing"
done
```

`head -1` is important because older stamps may contain a timestamp
second line that is not part of the semver. Deeper artifact or version
validation is the installer's job — if anything looks stale or partial,
re-run `bash -s update` instead of hand-checking files.

### Step 4 — Report

Use this format (substitute `{VERSION}` from the stamp,
`{CURSOR_STATUS}`, `{CLAUDE_STATUS}`):

```
✓ DevolaFlow v{VERSION} installed via scripts/install.sh
  Cursor (global): {CURSOR_STATUS}
    Path : ~/.cursor/skills/devola-flow/
  Claude Code (global): {CLAUDE_STATUS}
    Path : ~/.claude/skills/devola-flow/
  Docs  : https://yorha-agents.github.io/DevolaFlow/
  Repo  : https://github.com/YoRHa-Agents/DevolaFlow
  Re-run: trigger this skill again, or
          curl -fsSL <...>/install.sh | bash -s update
```

`{*_STATUS}` is one of: `"v{VERSION} installed"`, `"skipped (~/.X
absent)"`, or `"failed — see Step 2"`.

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

## Variants — installer target semantics

Every variant is just a different `scripts/install.sh` target/flag
combination; the script header documents the full target list and the
`--global` / `--project` / `--no-plugins` flags.

### Cursor only (global)

```bash
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh \
  | bash -s cursor --global
```

### Claude only (global)

```bash
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh \
  | bash -s claude --global
```

### Both Cursor + Claude (global) — default

Run both Step 2 commands sequentially (this is the default when both
`~/.cursor` and `~/.claude` are present).

### Project-local (current repo)

Drop `--global` to write under the current repository instead of
`$HOME` — e.g. `bash -s cursor` writes to `./.cursor/skills/devola-flow/`
and `bash -s claude` writes to `./.claude/skills/devola-flow/`.

### Update existing installs on this machine

The installer's `update` target auto-detects and refreshes every
existing install it finds (Cursor + Claude, global + project-local):

```bash
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh \
  | bash -s update
```

### All supported tools at once

The `all` target covers every tool adapter the installer supports. Only
use when the user explicitly asks for a multi-tool install — this
skill's default scope is Cursor + Claude:

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
| `Unknown target: ...` from installer | Typo in target argument | Re-run with a target from the script-header list (e.g. `cursor`, `claude`, `update`) |
| Version stamp missing or timestamp-only | Partial download or legacy install predating the version-fetch upgrade | Re-run `bash -s update` — the installer stamps the canonical `X.Y.Z` as the FIRST line; if still broken, escalate |
| `~/.cursor` missing | Cursor not installed on this machine | Skip the Cursor step; Claude install still proceeds. If BOTH `~/.cursor` and `~/.claude` are missing, stop and tell the user to install at least one of them first |
| `~/.claude` missing | Claude Code not installed | Skip the Claude step; Cursor install still proceeds. If BOTH `~/.cursor` and `~/.claude` are missing, stop and tell the user to install at least one of them first |

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
