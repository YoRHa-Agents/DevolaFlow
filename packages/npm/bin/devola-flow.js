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
// Zero runtime dependencies: Node >= 18 built-ins only (fetch, fs, path, os).

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const pkg = require(path.join(__dirname, '..', 'package.json'));

const REPO = 'YoRHa-Agents/DevolaFlow';
const DEFAULT_REF = `v${pkg.version}`;
const STAMP = '.devola-flow-version';

// npm-surface targets. install.sh covers more tools; this package covers the
// two user-level skill directories that exist on every OS.
const TARGETS = {
  cursor: {
    profile: 'cursor',
    dir: () => path.join(os.homedir(), '.cursor', 'skills', 'devola-flow'),
  },
  claude: {
    profile: 'claude',
    dir: () => path.join(os.homedir(), '.claude', 'skills', 'devola-flow'),
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

async function installTarget(name, manifest, stampVersion) {
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
  fs.writeFileSync(path.join(dir, STAMP), `${stampVersion}\n`);
}

async function cmdInstall(targetArg, opts, isUpdate) {
  const targets = resolveTargets(targetArg);
  const manifest = await loadManifest(opts);
  const stampVersion = await resolveStampVersion();
  console.log(`DevolaFlow installer (package v${pkg.version}, ref ${gitRef()})`);

  for (const name of targets) {
    const previous = isUpdate ? readStamp(TARGETS[name].dir()) : null;
    await installTarget(name, manifest, stampVersion);
    if (isUpdate && previous) {
      console.log(`  ${name}: updated ${previous} -> ${stampVersion}`);
    } else {
      console.log(`  ${name}: installed v${stampVersion}`);
    }
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
  console.log(`DevolaFlow doctor (package v${pkg.version}, ref ${gitRef()})`);

  for (const [name, target] of Object.entries(TARGETS)) {
    const dir = target.dir();
    if (!fs.existsSync(dir)) {
      console.log(`  ${name}: not installed (${dir})`);
      continue;
    }
    const stamp = readStamp(dir) || '(no stamp)';
    const expected = profileFiles(manifest, target.profile);
    const installed = listInstalledFiles(dir).filter((rel) => rel !== STAMP);
    const missing = expected.filter((rel) => !installed.includes(rel));
    const extra = installed.filter((rel) => !expected.includes(rel));
    console.log(`  ${name}: installed, version ${stamp} (${dir})`);
    if (missing.length === 0 && extra.length === 0) {
      console.log(`    files: OK (${expected.length}/${expected.length} match the manifest)`);
    } else {
      if (missing.length > 0) console.log(`    files MISSING vs manifest: ${missing.join(', ')}`);
      if (extra.length > 0) console.log(`    files NOT in manifest: ${extra.join(', ')}`);
      console.log(`    fix: npx @yorha-agents/devola-flow update ${name}`);
    }
  }
}

// ── CLI plumbing ────────────────────────────────────────────────────

function resolveTargets(name) {
  if (!name) {
    throw new CliError("missing target: expected 'cursor', 'claude', or 'all'");
  }
  if (name === 'all') return Object.keys(TARGETS);
  if (!TARGETS[name]) {
    throw new CliError(`unknown target '${name}': expected 'cursor', 'claude', or 'all'`);
  }
  return [name];
}

// Hidden subcommand: print a target's manifest-resolved file list, one per
// line. Lets tests (and operators) verify the manifest derivation offline
// via --manifest-file.
async function cmdFiles(targetArg, opts) {
  const targets = resolveTargets(targetArg);
  if (targets.length !== 1) {
    throw new CliError("'files' takes a single target ('cursor' or 'claude')");
  }
  const manifest = await loadManifest(opts);
  console.log(profileFiles(manifest, TARGETS[targets[0]].profile).join('\n'));
}

function printHelp() {
  console.log(`DevolaFlow npm installer v${pkg.version}

Usage:
  npx @yorha-agents/devola-flow <command> [target]

Commands:
  install <cursor|claude|all>   Download the DevolaFlow skill file set into
                                the user-level skill directory
  update  <cursor|claude|all>   Re-install (overwrite) and report the
                                previous -> new version
  doctor                        Report installed targets, stamp versions, and
                                whether files match the install manifest
  help                          Show this help
  version                       Show the package version

Install locations:
  cursor   <home>/.cursor/skills/devola-flow/
  claude   <home>/.claude/skills/devola-flow/

Environment:
  DEVOLA_FLOW_REF   Git ref to download from (branch, tag, or SHA).
                    Default: the tag matching this package version (${DEFAULT_REF}).

Skill files are not bundled in this package: they are downloaded from
https://github.com/${REPO} at the resolved ref, and the file list is derived
from workflow-system/agent/manifest.yaml (the same install-manifest source of
truth used by scripts/install.sh).`);
}

function parseArgs(argv) {
  const args = { positional: [], manifestFile: null, help: false, version: false };
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
