// DevolaFlow boundary bridge — DSH (DeepSeek Harness) cordis plugin.
// v17.4.1 G3 (design §4.7): intercepts the tools/pre-execute waterfall
// and asks `python -m devolaflow.hostbridge --host dsh` for a verdict.
// Fail-open by contract: python missing, spawn error, timeout, or any
// non-2 exit code all fall through to `next()` (the tool call proceeds).

import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { join } from 'node:path';

export const name = 'devolaflow-boundary';
export const inject = ['tools'];

const BRIDGE_TIMEOUT_MS = 5000;

const WRITE_TOOLS = new Set([
  'write_file', 'str_replace', 'edit_file', 'create_file',
  'Write', 'StrReplace', 'Edit', 'MultiEdit',
  'write', 'edit', 'str_replace_editor',
]);
const SHELL_TOOLS = new Set(['shell', 'run_shell', 'bash', 'exec', 'Bash', 'Shell']);

function resolvePython(cwd) {
  const venv = join(cwd ?? process.cwd(), '.venv', 'bin', 'python');
  return existsSync(venv) ? venv : 'python3';
}

// Map a DSH tool execution to the bridge's explicit stdin contract:
// {tool, kind: "file_write"|"shell", path, command} (we own both ends).
function toBridgePayload(exec) {
  const tool = exec?.name ?? '';
  const input = exec?.arguments ?? exec?.args ?? exec?.input ?? {};
  const path = input.path ?? input.file_path ?? input.target_file ?? null;
  const command = input.command ?? input.cmd ?? null;
  // Only known WRITE tools become file_write: a bare `path` is NOT enough,
  // because read-family tools also carry paths and must never be denied
  // (S-8 governs writes only). Unrecognized tools stay "unknown" -> allow.
  let kind = 'unknown';
  if (WRITE_TOOLS.has(tool)) kind = 'file_write';
  else if (SHELL_TOOLS.has(tool) || command) kind = 'shell';
  return { tool, kind, path, command };
}

// Spawn the bridge; resolve {code, stderr} or null on any spawn-side
// failure (which the caller treats as allow).
function runBridge(payload, cwd) {
  return new Promise((resolve) => {
    let settled = false;
    const done = (value) => {
      if (!settled) { settled = true; resolve(value); }
    };
    let child;
    try {
      child = spawn(resolvePython(cwd), ['-m', 'devolaflow.hostbridge', '--host', 'dsh'], {
        cwd: cwd ?? process.cwd(),
        stdio: ['pipe', 'ignore', 'pipe'],
      });
    } catch {
      return done(null);
    }
    const timer = setTimeout(() => { child.kill('SIGKILL'); done(null); }, BRIDGE_TIMEOUT_MS);
    let stderr = '';
    child.stderr.on('data', (chunk) => { stderr += chunk; });
    child.on('error', () => { clearTimeout(timer); done(null); });
    child.on('close', (code) => { clearTimeout(timer); done({ code, stderr }); });
    try {
      child.stdin.write(JSON.stringify(payload));
      child.stdin.end();
    } catch {
      // stdin failure -> let the close/error handlers settle the verdict.
    }
  });
}

export function apply(ctx) {
  ctx.on('tools/pre-execute', async (exec, next) => {
    try {
      const result = await runBridge(toBridgePayload(exec), ctx?.baseDir ?? process.cwd());
      if (result && result.code === 2) {
        return {
          kind: 'deny',
          reason: result.stderr.trim() || 'blocked by DevolaFlow host-bridge (S-8 ownership)',
        };
      }
      return next();
    } catch {
      return next(); // fail-open — never block on plugin-side errors
    }
  });
}

export default { name, inject, apply };
