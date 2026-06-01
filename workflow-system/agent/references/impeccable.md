---
id: impeccable
version: "13.0.0"
purpose: >
  Canonical operating contract for DevolaFlow's impeccable integration —
  a cross-provider design language system (1 agent skill + 23 /impeccable
  steering commands) plus a no-LLM deterministic anti-pattern detector
  (`impeccable detect`). Shipped in v13.0.0 as a tracked reference repo +
  fully wired 6th plugin + the new web-design workflow's refine/verify
  surface. Covers the command catalog, the detector exit-code contract,
  the ui-pro → impeccable composition, the DevolaFlow integration map, and
  the degraded-mode fallback for L0/L1/L2/L3 dispatchers + L3 task agents.
triggers:
  - "web-design workflow refine stage polishes / critiques an UI"
  - "web-design workflow verify stage runs the anti-pattern gate"
  - "L3 needs to refine an already-built UI (typography / spacing / motion)"
  - "pre-ship design audit (a11y / performance / responsive / theming)"
  - "deterministic anti-pattern scan in CI (no LLM, no API key)"
  - "ui-pro designed a system; impeccable refines + verifies it"
tier: 2
token_estimate: 2600
last_updated: "2026-06-01"
---

# Impeccable Reference

DevolaFlow's integration with `pbakaus/impeccable` — a cross-provider **design language system** for AI coding agents (1 agent skill + 23 `/impeccable` steering commands) plus a **no-LLM deterministic anti-pattern detector** (`impeccable detect`). v13.0.0 ships impeccable as the cycle's primary deliverable: a tracked reference repo, the 6th fully-wired plugin, and the refine + verify surface of the new `web-design` workflow.

**Upstream**: <https://github.com/pbakaus/impeccable> · npm: `impeccable@>=2.0.0` (Apache-2.0; Node 18+)

## §1 — What impeccable is + when L3 should use it

Impeccable is the **refinement + verification** half of DevolaFlow's UI flow. Where `ui-pro` (the `ui_tooling` role) DESIGNS a system from scratch — style, palette, typography, design-system primitives — impeccable REFINES an already-built UI and then VERIFIES it against a deterministic anti-pattern scan. The two compose on the `web-design` workflow: **ui-pro designs → implement → impeccable refines → impeccable verifies**.

Impeccable has two surfaces:

1. **The agent skill** — a single skill exposing 23 sub-commands accessed via `/impeccable <command> <target>` (e.g. `/impeccable polish the pricing page`). The skill teaches a shared design vocabulary and a curated set of anti-patterns the agent should design *against*.
2. **The detector CLI** — `impeccable detect <file|dir|url>`, a 100% deterministic, no-LLM, no-API-key scanner. It runs 27 anti-pattern rules (a 12-rule LLM critique pass is available inside the skill) and is the canonical CI / verify-stage gate.

L3 task agents should reach for impeccable when:

| L3 use-case | impeccable surface |
|---|---|
| "Polish this page before shipping" | `/impeccable polish <target>` |
| "Run a UX design review with scoring" | `/impeccable critique <target>` |
| "Audit a11y / performance / responsive / theming" | `/impeccable audit <target>` |
| "Fix font choices, hierarchy, sizing" | `/impeccable typeset <target>` |
| "Fix layout, spacing, visual rhythm" | `/impeccable arrange <target>` |
| "Add purposeful motion" | `/impeccable animate <target>` |
| "Gate the build on anti-patterns (CI / verify)" | `impeccable detect --json <path>` |

Impeccable is NOT a substitute for ui-pro: ui-pro picks styles / palettes / typography systems; impeccable assumes a built UI and sharpens it. On the `web-design` workflow both are auto-ensured at their respective stages.

## §2 — The 23 /impeccable commands

All commands are accessed through the single `/impeccable` skill: `/impeccable <command> <target>`. Typing `/impeccable` alone lists them. The catalog (verbatim from upstream `impeccable@2.3.2`):

| Command | What it does |
|---|---|
| `/impeccable init` (a.k.a. `teach-impeccable`) | One-time setup: gather design context, write a `PRODUCT.md` |
| `/impeccable craft` | Full shape-then-build flow on a brand-new feature |
| `/impeccable shape` | Shape a feature's design before building |
| `/impeccable critique` | UX design review: hierarchy, clarity, emotional resonance, scoring, persona tests + automated detection |
| `/impeccable audit` | Technical quality checks: a11y, performance, responsive, theming, anti-patterns |
| `/impeccable polish` | Final pass before shipping |
| `/impeccable normalize` | Align with design-system standards |
| `/impeccable distill` | Strip to essence |
| `/impeccable clarify` | Improve unclear UX copy |
| `/impeccable optimize` | Performance improvements |
| `/impeccable harden` | Error handling, i18n, edge cases |
| `/impeccable animate` | Add purposeful motion |
| `/impeccable colorize` | Introduce strategic color |
| `/impeccable bolder` | Amplify boring designs |
| `/impeccable quieter` | Tone down overly bold designs |
| `/impeccable delight` | Add moments of joy |
| `/impeccable extract` | Pull into reusable components |
| `/impeccable adapt` | Adapt for different devices |
| `/impeccable onboard` | Design onboarding flows |
| `/impeccable typeset` | Fix font choices, hierarchy, sizing |
| `/impeccable arrange` | Fix layout, spacing, visual rhythm |
| `/impeccable overdrive` | Add technically extraordinary effects |

The skill also teaches **anti-patterns** the agent designs against — e.g. overused fonts (Arial, Inter, system defaults), gray text on colored backgrounds, pure black/gray (always tint), card-nesting, bounce/elastic easing (feels dated), purple gradients, side-tab borders, dark glows, cramped padding, small touch targets, skipped heading levels.

## §3 — The detector CLI (`impeccable detect`)

The detector is the no-LLM half — deterministic, regex/jsdom-based, no API key. It scans HTML, CSS, JSX, TSX, Vue, and Svelte files (and live URLs via Puppeteer) for 27 anti-pattern rules covering AI-generated UI "tells" and general design-quality problems.

```bash
impeccable detect src/                   # scan a directory
impeccable detect index.html             # scan a single file
impeccable detect https://example.com    # scan a live URL (Puppeteer)
impeccable detect --fast --json src/     # regex-only (faster), JSON output
```

**Flags**: `--json` (machine-readable findings for CI/tooling), `--fast` (regex-only mode, skip jsdom; faster but less accurate), `--help`.

**Exit codes (the verify-stage gate contract):**

| Exit | Meaning | web-design verify verdict |
|---|---|---|
| `0` | No issues found | PASS |
| `2` | Anti-patterns detected | FAIL → loop back to refine |

This exit-code contract is what the `web-design` workflow's `verify` stage keys on: a non-zero exit (`2`) routes the convergence loop back to `refine`; exit `0` passes the gate.

## §4 — DevolaFlow integration map

### §4.1 — Plugin registries (per A-5 SSOT)

| Surface | File | Entry |
|---|---|---|
| Catalog | `workflow-system/agent/plugins.yaml` | `plugins.impeccable` block + `plugin_roles.ui_refinement` (provider=impeccable) |
| Runtime | `workflow-system/agent/knowledge/runtime-plugins.yaml` | `id: impeccable` (`backend: npm_then_init`; `invoked_by_workflows: [web-design]`) |
| Reference pin | `workflow-system/agent/knowledge/reference-dependencies.yaml` | 13th `active_tracking` entry |

### §4.2 — Install backend (npm_then_init)

Impeccable reuses the `npm_then_init` backend (ui-pro / codegraph precedent): `npm install -g impeccable`, then a per-harness skill install. **Unlike** ui-pro (`uipro init --ai {ai_platform}`) and codegraph (`codegraph install --target {ai_platform}`), impeccable's `skills install` **auto-detects** the harness — it scans for `.cursor` / `.claude` / `.agents` (codex) / `.gemini` / ... folders, with an optional `--providers=` narrowing flag. There is **no per-AI `--ai` flag**, so the init template carries no `{ai_platform}` placeholder and `init_targets` is a single sentinel `auto` entry:

```yaml
init_cmd_template: "impeccable skills install --yes"
init_targets: [auto]
version_check_cmd: "impeccable --version"   # prints pkg.version
```

### §4.3 — Workflow (per W-15 / CO-6 section relevance)

`workflow-system/agent/templates/builtin/web-design.yaml` — stages `design` (ensure `ui-pro`) → `implement` → `refine` (ensure `impeccable`; `/impeccable polish|critique|typeset|arrange|animate`) → `verify` (`impeccable detect --json`). The `refine ↔ verify` convergence loop runs until the detector exits `0`. `plugins_for_workflow("web-design")` resolves to `[ui-pro, impeccable]` in registry order.

### §4.4 — Context profile

`workflow-system/agent/context_profiles.yaml` — the `impeccable_integration` top-level block (parallel to `ui_integration` / `codegraph_integration`) surfaces the polish / critique / audit / detect recipes to the dispatcher. Marked `important` for the web-design profile, `skip` elsewhere.

### §4.5 — Env flag (per W-20 reuse-first)

Runtime auto-install reuses the existing `DEVOLAFLOW_AUTO_INSTALL_PLUGINS` flag (same surface as ui-pro / codegraph). **NO new `DEVOLAFLOW_*` flag** is introduced for impeccable.

## §5 — Degraded-mode contract

Per `references/degraded-mode.md` (and the leading "Degraded ≠ Full" warning there): impeccable being unreachable does NOT block a dispatch in permissive mode.

### §5.1 — Detection

The `pre_plugin_invocation` lifecycle hook calls `ensure_plugin('impeccable')`. When the npm registry is unreachable, the binary is missing, or the install fails, the installer raises `PluginInstallError` / `PluginNotFoundError` / `PluginVersionMismatch`.

### §5.2 — Permissive-continue behaviour

* The hook emits `PPI001` (severity `error`); **in permissive mode (default) the dispatch continues** — the violation is aggregated onto the `HookResult` for observers.
* In strict mode the dispatch blocks.
* The `web-design` verify stage degrades to a non-gating advisory when `impeccable detect` is unavailable: the agent records that the anti-pattern signal was lost (it does not fabricate a PASS).

### §5.3 — Operator action

Install impeccable per the canonical URL (`npm install -g impeccable`) OR set `DEVOLAFLOW_AUTO_INSTALL_PLUGINS=0` to bypass auto-install entirely. The detector also runs standalone via `npx impeccable detect` without any harness install.

**Test coverage**: `tests/test_degraded_mode.py::test_impeccable_unreachable_emits_ppi001_permissive_continues` pins the PPI001 + permissive-continue invariant (mirrors the ui-pro contract).

## §6 — Cache / install management

### §6.1 — Install footprint

`npm install -g impeccable` installs the CLI + skill bundle (~537KB unpacked; Node 18+). `jsdom` ships as a dependency (HTML scanning); `puppeteer` is optional (only for URL scanning).

### §6.2 — Skill install location

`impeccable skills install` writes the compiled skill into the detected harness folder(s) — `.cursor/skills/`, `.claude/skills/`, `.agents/skills/` (codex), etc. Re-run after a harness reload. `--force` reinstalls; `--providers=.cursor,.claude` narrows the targets.

### §6.3 — Updates

`impeccable skills update` (or `npx impeccable skills update`) refreshes the installed skill; `impeccable skills check` reports whether updates are available. The runtime registry's `upgrade_cmd` is `npm install -g impeccable@latest`.

### §6.4 — Verifying health

`impeccable --version` prints the installed version. `impeccable skills help` lists available commands. After install, type `/` in the harness and confirm `/impeccable` appears in the autocomplete.

### §6.5 — Running without a harness install

The detector is fully usable without installing the skill: `npx impeccable detect <path|url>` runs the deterministic scan directly. This is the recommended path for cost-conscious CI or restricted-network environments — no harness write, no API key.
