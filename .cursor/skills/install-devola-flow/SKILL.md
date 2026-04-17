---
name: install-devola-flow
description: >-
  Install or update the DevolaFlow workflow orchestration skill into the
  user-wide Cursor skill directory (~/.cursor/skills/devola-flow/) plus
  the matching rules file. Use when the user asks to install devola-flow,
  install devolaflow globally, setup devola-flow on this machine, update
  devola-flow, or bootstrap devola for all Cursor projects. Matches
  Chinese phrasings such as "安装 devola-flow", "全局安装 devola",
  "把 devola 装到 cursor", "更新 devola-flow".
  (Claude Code install is intentionally out of scope for now.)
---

# Install DevolaFlow (Global Cursor)

Drive the canonical installer at
`https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh`
so the `devola-flow` skill is available user-wide in Cursor
(`~/.cursor/skills/devola-flow/` + `~/.cursor/rules/devola-flow-rules.mdc`).

## When to Trigger

Activate on any of these user intents (EN or ZH):

- "install devola-flow" / "安装 devola-flow" / "安装 devola"
- "setup devola globally" / "全局安装 devola-flow"
- "update devola-flow" / "升级 devola" / "/update-devola"
- "bootstrap devola-flow on this machine"
- "把 devola 装到 cursor"

If the user scopes to project-local (`--project`) follow the matching
**Variants** block below instead of the default flow.

## Defaults

| Question | Default |
|---|---|
| Target | Cursor only (`cursor --global`) |
| Scope | `--global` (writes under `$HOME/.cursor`) |
| Source | `main` branch of `YoRHa-Agents/DevolaFlow` |
| Behaviour on partial failure | Stop and report, never half-install |

## Prerequisites

Run these checks first; stop and report if any fails:

```bash
command -v curl >/dev/null && echo "curl ok"
command -v bash >/dev/null && echo "bash ok"
curl -fsI --max-time 30 https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh \
  >/dev/null && echo "network ok"
test -d ~/.cursor && echo "~/.cursor ok"
```

If the network check fails or times out, jump to **Network Fallback
(Proxy)** before giving up. If `~/.cursor` is missing the user does not
have Cursor installed — stop and tell them.

## Execution Flow

### Step 1 — Announce the plan

Tell the user exactly what will happen:

```
Install DevolaFlow globally:
  • Cursor → ~/.cursor/skills/devola-flow/        (SKILL + refs + examples)
            ~/.cursor/rules/devola-flow-rules.mdc
Source: github.com/YoRHa-Agents/DevolaFlow (branch: main)
```

### Step 2 — Install to Cursor (global)

```bash
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh \
  | bash -s cursor --global
```

Expected artifacts on success:

```
~/.cursor/skills/devola-flow/SKILL.md
~/.cursor/skills/devola-flow/references/         (8 files)
~/.cursor/skills/devola-flow/examples/           (3 files)
~/.cursor/skills/devola-flow/.devola-flow-version
~/.cursor/rules/devola-flow-rules.mdc
```

The installer prints one `ok` line per file; any `✗ failed:` must be
treated as a Step 2 failure and surfaced up.

### Step 3 — Verify

Do not report success until **all** of these return `[PASS]`:

```bash
test -f ~/.cursor/skills/devola-flow/SKILL.md      && echo "[PASS] SKILL.md"      || echo "[FAIL] SKILL.md"
[ "$(ls ~/.cursor/skills/devola-flow/references 2>/dev/null | wc -l)" = "8" ] \
                                                   && echo "[PASS] 8 references"  || echo "[FAIL] references"
[ "$(ls ~/.cursor/skills/devola-flow/examples   2>/dev/null | wc -l)" = "3" ] \
                                                   && echo "[PASS] 3 examples"    || echo "[FAIL] examples"
test -f ~/.cursor/rules/devola-flow-rules.mdc      && echo "[PASS] rules"         || echo "[FAIL] rules"
```

Compare the installed version with upstream:

```bash
UPSTREAM=$(curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/src/devolaflow/__init__.py \
  | grep '__version__' | head -1 | sed 's/.*"\(.*\)".*/\1/')
LOCAL=$(cat ~/.cursor/skills/devola-flow/.devola-flow-version)
[ "$UPSTREAM" = "$LOCAL" ] && echo "v$LOCAL (current)" \
                          || echo "mismatch: upstream=$UPSTREAM local=$LOCAL"
```

### Step 4 — Report

Emit a structured summary:

```
✓ DevolaFlow v{VERSION} installed (Cursor, global)
  Path        : ~/.cursor/skills/devola-flow/   (SKILL + 8 refs + 3 examples)
  Rules       : ~/.cursor/rules/devola-flow-rules.mdc
  Docs        : https://yorha-agents.github.io/DevolaFlow/
  Repo        : https://github.com/YoRHa-Agents/DevolaFlow
  Re-run      : trigger this skill again, or
                curl -fsSL <...>/install.sh | bash -s update
```

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

### Project-local (current repo instead of `$HOME`)

Drop `--global` to write under `./.cursor/skills/devola-flow/`:

```bash
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh \
  | bash -s cursor
```

### Update existing installs on this machine

Refreshes whichever install (global or project) the installer detects:

```bash
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh \
  | bash -s update
```

### All supported tools at once

Covers Cursor, Codex, Claude, Copilot, KimiCode, Windsurf. Only use when
the user explicitly asks for a multi-tool install — this skill's default
scope is Cursor only:

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
| `Unknown target: ...` from installer | Typo in target argument | Re-run with `cursor` or `update` |
| Version stamp differs from upstream | Partial download | Re-run `bash -s update`; if still mismatched, escalate |
| `~/.cursor` missing | Cursor not installed on this machine | Stop; tell user to install Cursor first |

Never silently skip `✗ failed:` lines in the installer output. Report
the exact filename(s) that failed.

## Post-install

- The skill auto-activates on Cursor triggers such as "implement
  feature", "fix bug", "run workflow", "hotfix".
- Uninstall:

  ```bash
  rm -rf ~/.cursor/skills/devola-flow \
         ~/.cursor/rules/devola-flow-rules.mdc
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
- All writes stay inside `~/.cursor/` — no `sudo`, no system paths, no
  credentials.
- Downloads are anonymous HTTPS against `raw.githubusercontent.com`
  (directly or via proxy).
