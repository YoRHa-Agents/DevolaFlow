#!/usr/bin/env node
'use strict';

// DevolaFlow npm installer — a THIN installer, not a skill bundle.
//
// Skill files are never shipped inside the npm tarball. At install time this
// CLI downloads them from GitHub raw at the tag matching the package version
// (override with DEVOLA_FLOW_REF), and the file list is derived at runtime
// from workflow-system/agent/manifest.yaml — the install-manifest single
// source of truth shared with scripts/install.sh (repo rules A-5 / C-7).
//
// Zero npm dependencies: Node >= 18 built-ins only (fetch, fs, path, os).

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const pkg = require(path.join(__dirname, '..', 'package.json'));

const REPO = 'YoRHa-Agents/DevolaFlow';
const DEFAULT_REF = `v${pkg.version}`;
const STAMP = '.devola-flow-version';
const RUNTIME_PYTHON = '3.13';
const UV_INSTALL_URL = 'https://astral.sh/uv/install.sh';
const UV_INSTALL_PS1_URL = 'https://astral.sh/uv/install.ps1';

// npm-surface targets. install.sh covers more tools; this package covers the
// five user-level skill directories selected by the Host Support Contract.
const TARGETS = {
  cursor: {
    profile: 'cursor',
    dir: () => path.join(os.homedir(), '.cursor', 'skills', 'devola-flow'),
  },
  claude: {
    profile: 'claude',
    dir: () => path.join(os.homedir(), '.claude', 'skills', 'devola-flow'),
  },
  codex: {
    profile: 'codex',
    dir: () =>
      path.join(process.env.CODEX_HOME || path.join(os.homedir(), '.codex'), 'skills', 'devola-flow'),
  },
  kimicode: {
    profile: 'kimicode',
    dir: () => path.join(os.homedir(), '.kimi', 'skills', 'devola-flow'),
  },
  dsh: {
    profile: 'dsh',
    dir: () => path.join(process.env.DSH_HOME || path.join(os.homedir(), '.dsh'), 'skills', 'devola-flow'),
  },
};

/** Expected operational failure — printed without a stack trace. */
class CliError extends Error {}

function gitRef() {
  return process.env.DEVOLA_FLOW_REF || DEFAULT_REF;
}

function rawBase() {
  return `https://raw.githubusercontent.com/${REPO}/${gitRef()}`;
}

function agentBase() {
  return `${rawBase()}/workflow-system/agent`;
}

async function fetchText(url) {
  let res;
  try {
    res = await fetch(url, { redirect: 'follow' });
  } catch (err) {
    throw new CliError(`network error fetching ${url}: ${err.message}`);
  }
  if (!res.ok) {
    throw new CliError(`HTTP ${res.status} fetching ${url}`);
  }
  return res.text();
}

// ── Manifest (A-5 SSOT) ─────────────────────────────────────────────
//
// Minimal purpose-built parser for the manifest's actual shape (the manifest
// deliberately keeps flat "  - path" lists and single-line flow-style
// install_profiles entries so line-oriented parsers like this one and the
// awk/sed pair in scripts/install.sh stay trivial):
//
//   schema_version: "1.0"          <- top-level scalar, ignored
//   core:                          <- flat list section
//     - SKILL.md
//   install_profiles:              <- one flow-style mapping per line
//     cursor: {kind: skill-dir, sets: [core, references, examples]}

function parseManifest(text) {
  const sets = {};
  const profiles = {};
  let currentSet = null;
  let inProfiles = false;

  for (const line of text.split(/\r?\n/)) {
    if (!line.trim() || line.trim().startsWith('#')) continue;

    const top = line.match(/^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$/);
    if (top) {
      const [, key, rest] = top;
      inProfiles = key === 'install_profiles';
      currentSet = null;
      if (!inProfiles && rest === '') {
        currentSet = key;
        sets[key] = [];
      }
      continue;
    }

    if (inProfiles) {
      const prof = line.match(/^ {2}([A-Za-z0-9_-]+):\s*\{.*\bsets:\s*\[([^\]]*)\].*\}/);
      if (prof) {
        profiles[prof[1]] = prof[2].split(',').map((s) => s.trim()).filter(Boolean);
      }
      continue;
    }

    const item = line.match(/^ {2}- (.+)$/);
    if (item && currentSet) {
      sets[currentSet].push(item[1].trim());
    }
  }

  if (Object.keys(profiles).length === 0) {
    throw new CliError('manifest parse failed: no install_profiles found');
  }
  return { sets, profiles };
}

function profileFiles(manifest, profile) {
  const setNames = manifest.profiles[profile];
  if (!setNames) {
    throw new CliError(`manifest has no install profile '${profile}'`);
  }
  const files = [];
  for (const name of setNames) {
    const entries = manifest.sets[name];
    if (!entries || entries.length === 0) {
      throw new CliError(`manifest profile '${profile}' references empty/undefined set '${name}'`);
    }
    files.push(...entries);
  }
  return files;
}

async function loadManifest(opts) {
  if (opts.manifestFile) {
    let text;
    try {
      text = fs.readFileSync(opts.manifestFile, 'utf8');
    } catch (err) {
      throw new CliError(`cannot read manifest file ${opts.manifestFile}: ${err.message}`);
    }
    return parseManifest(text);
  }
  return parseManifest(await fetchText(`${agentBase()}/manifest.yaml`));
}

// ── Install / update ────────────────────────────────────────────────

// Same stamp semantics as scripts/install.sh: record the remote
// __version__ at the resolved ref. Falls back to the package version with an
// explicit warning (never silently — S-5) when the remote read fails.
async function resolveStampVersion() {
  try {
    const text = await fetchText(`${rawBase()}/src/devolaflow/__init__.py`);
    const match = text.match(/__version__\s*=\s*"([^"]+)"/);
    if (match) return match[1];
    console.error(`devola-flow: warning: no __version__ found at ref ${gitRef()}; stamping package version ${pkg.version}`);
  } catch (err) {
    console.error(`devola-flow: warning: could not resolve remote version (${err.message}); stamping package version ${pkg.version}`);
  }
  return pkg.version;
}

function readStamp(dir) {
  try {
    return fs.readFileSync(path.join(dir, STAMP), 'utf8').split(/\r?\n/)[0] || null;
  } catch {
    return null;
  }
}

function runtimeSpec() {
  return `devolaflow @ git+https://github.com/${REPO}.git@v${pkg.version}`;
}

function runtimeInstallCommand() {
  return `uv tool install --force --python ${RUNTIME_PYTHON} '${runtimeSpec()}'`;
}

function executableCandidates(name) {
  const names = process.platform === 'win32' ? [name, `${name}.exe`] : [name];
  const pathDirs = (process.env.PATH || '').split(path.delimiter).filter(Boolean);
  const home = os.homedir();
  const extraDirs =
    process.platform === 'win32'
      ? [
          path.join(home, '.local', 'bin'),
          path.join(process.env.LOCALAPPDATA || '', 'uv'),
          path.join(process.env.LOCALAPPDATA || '', 'bin'),
        ]
      : [path.join(home, '.local', 'bin'), path.join(home, '.cargo', 'bin')];
  // Prefer the active HOME's tool directories over inherited PATH entries.
  // This prevents a stale user-level DevolaFlow executable from masking the
  // runtime just installed into an isolated HOME or uv environment.
  const dirs = [...new Set([...extraDirs, ...pathDirs])];
  return dirs.flatMap((dir) => names.map((candidate) => path.join(dir, candidate)));
}

function findExecutable(name) {
  for (const candidate of executableCandidates(name)) {
    if (fs.existsSync(candidate)) return candidate;
  }
  return null;
}

function runExecutable(command, args = []) {
  const executable = findExecutable(command) || command;
  const envPath = executable.includes(path.sep)
    ? `${path.dirname(executable)}${path.delimiter}${process.env.PATH || ''}`
    : process.env.PATH;
  const result = spawnSync(executable, args, {
    encoding: 'utf8',
    timeout: 120000,
    env: { ...process.env, PATH: envPath },
  });
  return { executable, result };
}

function probeRuntime() {
  const { result } = runExecutable('devola-version');
  const output = `${result.stdout || ''}\n${result.stderr || ''}`;
  const match = output.match(/DevolaFlow v([0-9A-Za-z.-]+)/);
  return {
    version: match ? match[1] : null,
    available: result.error == null && result.status === 0 && Boolean(match),
  };
}

function bootstrapUv() {
  const existing = findExecutable('uv');
  if (existing) return existing;

  const command =
    process.platform === 'win32'
      ? [
          'powershell.exe',
          [
            '-NoProfile',
            '-ExecutionPolicy',
            'Bypass',
            '-Command',
            `irm ${UV_INSTALL_PS1_URL} | iex`,
          ],
        ]
      : ['/bin/sh', ['-c', `curl -LsSf ${UV_INSTALL_URL} | sh`]];
  const result = spawnSync(command[0], command[1], {
    encoding: 'utf8',
    timeout: 120000,
    env: process.env,
  });
  if (result.error || result.status !== 0) {
    const detail = (result.stderr || result.stdout || result.error?.message || '').trim();
    throw new CliError(
      `could not bootstrap uv (${detail || `exit ${result.status}`}); ` +
        `install uv manually, then run: ${runtimeInstallCommand()}`,
    );
  }
  const installed = findExecutable('uv');
  if (!installed) {
    throw new CliError(
      `uv bootstrap completed but uv is not on PATH; ` +
        `install uv manually, then run: ${runtimeInstallCommand()}`,
    );
  }
  return installed;
}

async function ensureRuntime() {
  const expected = pkg.version;
  const before = probeRuntime();
  if (before.available && before.version === expected) {
    return { state: 'full-runtime', version: before.version };
  }

  const uv = bootstrapUv();
  const result = spawnSync(
    uv,
    ['tool', 'install', '--force', '--python', RUNTIME_PYTHON, runtimeSpec()],
    {
      encoding: 'utf8',
      timeout: 300000,
      env: { ...process.env, PATH: `${path.dirname(uv)}${path.delimiter}${process.env.PATH || ''}` },
    },
  );
  if (result.error || result.status !== 0) {
    const detail = (result.stderr || result.stdout || result.error?.message || '').trim();
    throw new CliError(
      `runtime install failed (${detail || `exit ${result.status}`}); ` +
        `retry with: ${runtimeInstallCommand()}`,
    );
  }

  const after = probeRuntime();
  if (!after.available || after.version !== expected) {
    throw new CliError(
      `runtime install completed but devola-version reported ` +
        `${after.version || 'no usable runtime'}; retry with: ${runtimeInstallCommand()}`,
    );
  }
  return { state: 'full-runtime', version: after.version };
}

function runtimeFromStamp(dir) {
  try {
    const lines = fs.readFileSync(path.join(dir, STAMP), 'utf8').split(/\r?\n/);
    const state = lines.find((line) => line.startsWith('runtime:'))?.split(':', 2)[1]?.trim();
    const version = lines
      .find((line) => line.startsWith('runtime_version:'))
      ?.split(':', 2)[1]
      ?.trim();
    return { state: state || null, version: version || null };
  } catch {
    return { state: null, version: null };
  }
}

function writeStamp(dir, stampVersion, runtime) {
  const lines = [`${stampVersion}`, `runtime: ${runtime.state}`];
  if (runtime.version) lines.push(`runtime_version: ${runtime.version}`);
  if (runtime.error) {
    lines.push(`runtime_error: ${runtime.error.replace(/\s+/g, ' ').slice(0, 300)}`);
  }
  fs.writeFileSync(path.join(dir, STAMP), `${lines.join('\n')}\n`);
}

async function installTarget(name, manifest, stampVersion, runtime) {
  const target = TARGETS[name];
  const dir = target.dir();
  const files = profileFiles(manifest, target.profile);
  console.log(`> ${name}: ${files.length} files (manifest profile '${target.profile}') -> ${dir}`);
  fs.mkdirSync(dir, { recursive: true });

  const failures = [];
  for (const rel of files) {
    const dest = path.join(dir, ...rel.split('/'));
    try {
      const body = await fetchText(`${agentBase()}/${rel}`);
      fs.mkdirSync(path.dirname(dest), { recursive: true });
      fs.writeFileSync(dest, body);
      console.log(`    ${rel}  ok`);
    } catch (err) {
      failures.push(`${rel}: ${err.message}`);
      console.error(`    ${rel}  FAILED`);
    }
  }
  if (failures.length > 0) {
    throw new CliError(
      `${failures.length}/${files.length} downloads failed for target '${name}':\n  ` +
        failures.join('\n  ')
    );
  }
  writeStamp(dir, stampVersion, runtime);
}

async function cmdInstall(targetArg, opts, isUpdate) {
  const targets = resolveTargets(targetArg);
  const manifest = await loadManifest(opts);
  const stampVersion = await resolveStampVersion();
  console.log(`DevolaFlow installer (package v${pkg.version}, ref ${gitRef()})`);
  let runtime = { state: 'docs-only', version: null };

  for (const name of targets) {
    const previous = isUpdate ? readStamp(TARGETS[name].dir()) : null;
    await installTarget(name, manifest, stampVersion, runtime);
    if (isUpdate && previous) {
      console.log(`  ${name}: updated ${previous} -> ${stampVersion}`);
    } else {
      console.log(`  ${name}: installed v${stampVersion}`);
    }
  }

  if (opts.noRuntime) {
    console.log('Runtime: docs-only (--no-runtime requested)');
  } else {
    try {
      runtime = await ensureRuntime();
      console.log(`Runtime: ${runtime.state} v${runtime.version}`);
    } catch (err) {
      runtime.error = err.message;
      console.error(`devola-flow: warning: ${err.message}`);
      console.error(`devola-flow: warning: skill files will remain docs-only`);
    }
  }
  for (const name of targets) {
    writeStamp(TARGETS[name].dir(), stampVersion, runtime);
  }
  console.log('Done.');
}

// ── Doctor ──────────────────────────────────────────────────────────

function listInstalledFiles(dir) {
  const out = [];
  const walk = (sub) => {
    for (const entry of fs.readdirSync(path.join(dir, sub), { withFileTypes: true })) {
      const rel = sub ? `${sub}/${entry.name}` : entry.name;
      if (entry.isDirectory()) {
        walk(rel);
      } else {
        out.push(rel);
      }
    }
  };
  walk('');
  return out;
}

async function cmdDoctor(opts) {
  const manifest = await loadManifest(opts);
  const runtimeProbe = probeRuntime();
  console.log(`DevolaFlow doctor (package v${pkg.version}, ref ${gitRef()})`);
  if (runtimeProbe.available && runtimeProbe.version === pkg.version) {
    console.log(`Runtime: full-runtime v${runtimeProbe.version}`);
  } else if (runtimeProbe.available) {
    console.log(`Runtime: runtime-mismatch v${runtimeProbe.version} (expected v${pkg.version})`);
  } else {
    console.log(`Runtime: docs-only (devola-version is unavailable)`);
    console.log(`  fix: ${runtimeInstallCommand()}`);
  }

  for (const [name, target] of Object.entries(TARGETS)) {
    const dir = target.dir();
    if (!fs.existsSync(dir)) {
      console.log(`  ${name}: not installed (${dir})`);
      continue;
    }
    const stamp = readStamp(dir) || '(no stamp)';
    const stampedRuntime = runtimeFromStamp(dir);
    const expectedRuntime = stamp === '(no stamp)' ? pkg.version : stamp;
    const expected = profileFiles(manifest, target.profile);
    const installed = listInstalledFiles(dir).filter((rel) => rel !== STAMP);
    const missing = expected.filter((rel) => !installed.includes(rel));
    const extra = installed.filter((rel) => !expected.includes(rel));
    const runtimeState =
      runtimeProbe.available && runtimeProbe.version === expectedRuntime
        ? `full-runtime v${runtimeProbe.version}`
        : stampedRuntime.state === 'docs-only'
          ? 'docs-only'
          : `runtime-mismatch (expected v${expectedRuntime})`;
    console.log(`  ${name}: installed, version ${stamp}, ${runtimeState} (${dir})`);
    if (missing.length === 0 && extra.length === 0) {
      console.log(`    files: OK (${expected.length}/${expected.length} match the manifest)`);
    } else {
      if (missing.length > 0) console.log(`    files MISSING vs manifest: ${missing.join(', ')}`);
      if (extra.length > 0) console.log(`    files NOT in manifest: ${extra.join(', ')}`);
      console.log(`    fix: npx @yorha-agents/devola-flow update ${name}`);
    }
    if (runtimeState !== `full-runtime v${expectedRuntime}`) {
      console.log(`    runtime fix: ${runtimeInstallCommand()}`);
    }
  }
}

// ── CLI plumbing ────────────────────────────────────────────────────

function resolveTargets(name) {
  if (!name) {
    throw new CliError("missing target: expected 'cursor', 'claude', 'codex', 'kimicode', 'dsh', or 'all'");
  }
  if (name === 'all') return Object.keys(TARGETS);
  if (!TARGETS[name]) {
    throw new CliError(
      `unknown target '${name}': expected 'cursor', 'claude', 'codex', 'kimicode', 'dsh', or 'all'`,
    );
  }
  return [name];
}

// Hidden subcommand: print a target's manifest-resolved file list, one per
// line. Lets tests (and operators) verify the manifest derivation offline
// via --manifest-file.
async function cmdFiles(targetArg, opts) {
  const targets = resolveTargets(targetArg);
  if (targets.length !== 1) {
    throw new CliError("'files' takes a single target ('cursor', 'claude', 'codex', 'kimicode', or 'dsh')");
  }
  const manifest = await loadManifest(opts);
  console.log(profileFiles(manifest, TARGETS[targets[0]].profile).join('\n'));
}

function printHelp() {
  console.log(`DevolaFlow npm installer v${pkg.version}

Usage:
  npx @yorha-agents/devola-flow <command> [target]

Commands:
  install <cursor|claude|codex|kimicode|dsh|all>   Download the DevolaFlow skill file set into
                                the user-level skill directory
  update  <cursor|claude|codex|kimicode|dsh|all>   Re-install (overwrite) and report the
                                previous -> new version
  doctor                        Report installed targets, stamp versions, and
                                whether files match the install manifest
  help                          Show this help
  version                       Show the package version

Install locations:
  cursor   <home>/.cursor/skills/devola-flow/
  claude   <home>/.claude/skills/devola-flow/
  codex    <CODEX_HOME or home>/.codex/skills/devola-flow/
  kimicode <home>/.kimi/skills/devola-flow/
  dsh      <DSH_HOME or home>/.dsh/skills/devola-flow/

Environment:
  DEVOLA_FLOW_REF   Git ref to download from (branch, tag, or SHA).
                    Default: the tag matching this package version (${DEFAULT_REF}).
  --no-runtime      Install skill files without provisioning the Python runtime.

Skill files are not bundled in this package: they are downloaded from
https://github.com/${REPO} at the resolved ref, and the file list is derived
from workflow-system/agent/manifest.yaml (the same install-manifest source of
truth used by scripts/install.sh).`);
}

function parseArgs(argv) {
  const args = { positional: [], manifestFile: null, help: false, version: false, noRuntime: false };
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === '--help' || arg === '-h') {
      args.help = true;
    } else if (arg === '--version' || arg === '-v') {
      args.version = true;
    } else if (arg === '--manifest-file') {
      args.manifestFile = argv[++i];
      if (!args.manifestFile) throw new CliError('--manifest-file requires a path');
    } else if (arg.startsWith('--manifest-file=')) {
      args.manifestFile = arg.slice('--manifest-file='.length);
    } else if (arg === '--no-runtime') {
      args.noRuntime = true;
    } else if (arg.startsWith('-')) {
      throw new CliError(`unknown option '${arg}' (run --help for usage)`);
    } else {
      args.positional.push(arg);
    }
  }
  return args;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.version) {
    console.log(pkg.version);
    return;
  }
  const command = args.positional[0];
  if (args.help || !command || command === 'help') {
    printHelp();
    return;
  }
  switch (command) {
    case 'version':
      console.log(pkg.version);
      break;
    case 'install':
      await cmdInstall(args.positional[1], args, false);
      break;
    case 'update':
      await cmdInstall(args.positional[1], args, true);
      break;
    case 'doctor':
      await cmdDoctor(args);
      break;
    case 'files':
      await cmdFiles(args.positional[1], args);
      break;
    default:
      throw new CliError(`unknown command '${command}' (run --help for usage)`);
  }
}

main().catch((err) => {
  // S-5: no silent failures — every error path prints and exits non-zero.
  const message = err instanceof CliError ? err.message : err.stack || String(err);
  console.error(`devola-flow: ${message}`);
  process.exit(1);
});
