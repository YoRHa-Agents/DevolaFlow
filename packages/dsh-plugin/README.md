# @yorha-agents/devola-flow-dsh

DevolaFlow boundary bridge for **DeepSeek Harness (DSH)**. A cordis
plugin that intercepts the `tools/pre-execute` waterfall and routes
each tool event (file writes, shell commands) through
`python -m devolaflow.hostbridge --host dsh` for S-8 owned-files
boundary enforcement.

> **Pre-release** — version `0.1.0`, versioned independently of the
> DevolaFlow Python package. v17.4.1 repairs the DSH bundle manifest and
> real tool payload mapping; npm publication rides the R6 release channel.

## How it works

1. On every `tools/pre-execute` event the plugin classifies the tool
   call (`file_write` / `shell` / `unknown`) and feeds one JSON object
   (`{tool, kind, path, command}`) to the bridge on stdin.
2. The bridge answers with exit code `0` (allow) or `2` (deny, reason
   on stderr). Deny returns `{kind: 'deny', reason}` into the
   waterfall; everything else falls through to `next()`.
3. **Fail-open**: a missing Python interpreter, spawn error, or the 5s
   timeout all allow the tool call. Enforcement additionally requires
   `DEVOLAFLOW_HOST_ENFORCE=1` in the DSH process environment — without
   it the bridge itself is a zero-IO allow.

## Install

```bash
dsh plugin add @yorha-agents/devola-flow-dsh
```

The package is a DSH bundle: its `dsh.bundle.patch` metadata points to
`cordis.patch.yml`, which mounts the plugin into the active profile.

The plugin resolves Python as `.venv/bin/python` under the workspace
root when present, else `python3` on PATH. The `devolaflow` Python
package (v17+) must be importable by that interpreter.

## Degraded mode: sidecar / Center only

If your deployment only mounts the DSH agent sidecar or Center (no
plugin channel), pre-execution blocking is NOT available. You still get
**post-hoc audit**: run the sidecar with `DEVOLAFLOW_HOST_ENFORCE=1`
in the workspace and review `.local/telemetry/hostbridge.jsonl` after
the fact (every framework-side enforced decision is ledgered), or
replay suspect tool calls through
`python -m devolaflow.hostbridge --host dsh` manually. Blocking
requires the plugin channel.

## Contract

- Enforcement flag: `DEVOLAFLOW_HOST_ENFORCE=1` (R5 strict — literal
  `"1"` only). See `workflow-system/agent/references/env-flags.md`
  §2.18 in the DevolaFlow repo.
- Audit ledger: `.local/telemetry/hostbridge.jsonl` (JSONL; schema in
  `workflow-system/agent/references/host-bridges.md`).
- Shell events are advisory-only in this release (allowed + audited).

The DSH tool vocabulary is `write`, `edit`, and `str_replace_editor` for
file writes, plus `bash` and `pwsh` for shell commands. The plugin reads
the native `exec.arguments` object before falling back to legacy aliases.
