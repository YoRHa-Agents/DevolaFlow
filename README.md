# DevolaFlow

*From the guardians of YoRHa — a framework that watches over your code.*

[![CI](https://github.com/YoRHa-Agents/DevolaFlow/actions/workflows/ci.yml/badge.svg)](https://github.com/YoRHa-Agents/DevolaFlow/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org)
[![Version](https://img.shields.io/badge/dynamic/toml?url=https%3A%2F%2Fraw.githubusercontent.com%2FYoRHa-Agents%2FDevolaFlow%2Fmain%2Fpyproject.toml&query=%24.project.version&label=version&color=green)](https://github.com/YoRHa-Agents/DevolaFlow/releases)

DevolaFlow is a checklist-round orchestration meta-framework for AI-assisted
software development. It selects non-executable decomposition knowledge, then
executes a user-confirmed checklist through one `change-driven` runtime and a
three-layer Project → Wave → Task hierarchy.

```text
natural-language request
  → checklist seed
  → goal + checklist + preflight
  → bounded Project/Wave/Task rounds
  → evidence-backed completion or escalation
```

## Install

The installation channels have different scopes. In particular, `all` does
not mean the same thing in npm, curl, and `devola-init`.

### npm / npx: user-level guaranteed skill hosts

Requires Node 18 or newer and works on Windows.

```bash
npx @yorha-agents/devola-flow install cursor
npx @yorha-agents/devola-flow install claude
npx @yorha-agents/devola-flow install codex
npx @yorha-agents/devola-flow install kimicode
npx @yorha-agents/devola-flow install dsh
npx @yorha-agents/devola-flow install all
npx @yorha-agents/devola-flow doctor
npx @yorha-agents/devola-flow update all
```

npm `all` means the five user-level skill targets supported by the package:
Cursor, Claude, Codex, KimiCode, and DSH. Downloads default to the tag matching
the npm package version;
`DEVOLA_FLOW_REF` can intentionally select another branch, tag, or SHA.

### curl: broad project/global installer

The curl installer defaults to project scope and covers the target set
implemented by [`scripts/install.sh`](scripts/install.sh): Cursor, Claude,
Codex, Copilot, KimiCode, DSH, Windsurf, Zed, Cline, Roo, local workspace, and
a standalone file.

```bash
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s cursor
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s claude --global
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s all
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s update
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s uninstall --dry-run
```

curl `all` installs all supported host targets plus the local scaffold; it
excludes `standalone`. Some hosts are project-only even when `--global` is
requested. Global installation also attempts the default-bundled runtime
plugins codegraph and impeccable; optional plugin ui-pro remains explicit-only. Add
`--no-plugins` to copy only skill files. curl supports `update` and
`uninstall`, but has no doctor target.

### Host Support Contract

The canonical support registry is
[`workflow-system/agent/hosts.yaml`](workflow-system/agent/hosts.yaml). It
distinguishes guaranteed delivery from community support and records optional
capabilities with evidence:

- **Guaranteed:** Cursor, Claude Code, Codex, GitHub Copilot, KimiCode, DSH
- **Community-installable:** Windsurf, Zed, Cline, Roo
- **Community-build-only:** Continue, OpenClaw, Gemini, JetBrains, Amazon Q,
  Augment, Trae

Skill delivery and host-bridge enforcement are separate capabilities. Consult
the [Host Support Contract reference](workflow-system/agent/references/host-contract.md)
and [host-bridge matrix](workflow-system/agent/references/host-bridges.md)
before describing a host as boundary-enforced.

### pip or wheel: Python runtime and local scaffold

```bash
pip install git+https://github.com/YoRHa-Agents/DevolaFlow.git
cd your-project
devola-init local --mode=core
devola-init local --mode=standard
devola-init local --mode=full
devola-init-doctor
```

A wheel supplies the Python runtime, CLIs, and `devola-init local`. It does not
bundle `workflow-system/agent/`, so wheel-only installs cannot copy guaranteed
host skill files.

Use a clone plus editable install for non-local `devola-init` targets:

```bash
git clone https://github.com/YoRHa-Agents/DevolaFlow.git
cd DevolaFlow
pip install -e ".[dev]"
devola-init cursor
devola-init all
```

Python `all` means Cursor, Claude, Copilot, Codex, KimiCode, and DSH; it
excludes the local scaffold. With `--global`, default-bundled plugin
installation is attempted unless `--no-plugins` is passed. Codegraph and
impeccable are bundled; optional plugin ui-pro remains explicit-only.

### Manual fallback

You can copy
[`SKILL.md`](https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/workflow-system/agent/SKILL.md)
into a host instruction location, but a single-file copy omits
manifest-declared references and examples. Use
[`workflow-system/agent/manifest.yaml`](workflow-system/agent/manifest.yaml)
or a supported installer for a complete host profile.

### Full Development Setup

```bash
git clone https://github.com/YoRHa-Agents/DevolaFlow.git
cd DevolaFlow
pip install -e ".[dev]"
make test
make validate-templates
```

The validation covers 27 non-executable seeds and the sole runtime. The
registry and on-disk seed files are parity-tested rather than copied into build
scripts.

## Doctor and Update Surfaces

Use the doctor that matches the installation surface:

```bash
# npm-supported user-level Cursor/Claude copies and manifest parity
npx @yorha-agents/devola-flow doctor

# current Python local workspace structure
devola-init-doctor

# known copied-skill locations and their version stamps
devola-init-doctor --skills
```

Update through the same channel that owns the installed bytes:

```bash
# npm
npx @yorha-agents/devola-flow update all

# curl
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s update

# curl local workspace or standalone file: rerun the explicit install target
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s local
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s standalone

# Python runtime or wheel
pip install --upgrade git+https://github.com/YoRHa-Agents/DevolaFlow.git
devola-init local --mode=standard

# editable checkout and copied host skill
git pull
pip install -e ".[dev]"
devola-init cursor
```

curl `update` scans supported host skill-copy locations only. It does not scan
the local workspace or standalone file; rerun the explicit install target for
either surface. Updating the Python package does not silently refresh copied
host skills.
`sync-rules` (or repository-local `make compile-rules`) repairs rule
compilation; it is not a `devola-init` target.

## First Workflow

After the appropriate doctor or visibility check passes, open the AI host and
ask for a bounded multi-step change:

```text
Fix the login timeout bug and verify the regression.
```

DevolaFlow will:

1. select a checklist seed as decomposition knowledge;
2. confirm a goal, measurable checklist, P0/P1/P2 priorities, and preflight;
3. execute the checklist through bounded `change-driven` rounds;
4. dispatch L0 Project → L1 Wave → L2 Task;
5. check items only after StatusReport evidence is verified.

No workflow runner CLI is required. `source_stages` entries in seed YAML
preserve historical provenance only; priorities, dependencies, ownership, and
round state determine execution order.

## Optional Host Bridge

Skill installation and host bridge wiring are separate states. Copying
Markdown makes DevolaFlow discoverable; it does not prove host tool events are
connected to lifecycle boundary enforcement.

Follow the
[host bridge reference](workflow-system/agent/references/host-bridges.md) for
Cursor, Claude Code, Codex, KimiCode, DSH, or GitHub Copilot. Confirm the
host-specific config, exercise a known-allowed event, and inspect
`.local/telemetry/hostbridge.jsonl` before persistently setting:

```bash
export DEVOLAFLOW_HOST_ENFORCE=1
```

Unsupported hosts remain skill-only and must not be described as enforced.

## What's Inside

### 27 Non-Executable Checklist Seeds + One Runtime

The registry exposes these seeds through `TemplateRegistry.load_seed(<name>)`.
Seeds carry decomposition knowledge and provenance; they do not define an
executable DAG. `TemplateRegistry.load_template("change-driven")` loads the
sole runtime.

| Seed | Use when |
|---|---|
| `hotfix` | Urgent defect diagnosis and bounded remediation |
| `research-only` | Compare alternatives and produce an evidenced recommendation |
| `design-only` | Create architecture, API, or schema decisions |
| `documentation-only` | Survey, author, and review documentation |
| `spike-poc` | Test feasibility with a bounded prototype |
| `refactoring` | Restructure code while preserving behavior |
| `feature-enhancement` | Extend an existing feature |
| `full-pipeline` | Build a greenfield or end-to-end capability |
| `performance-optimization` | Improve measured performance |
| `security-audit` | Threat-model, scan, remediate, and verify |
| `research-design-review-refine` | Iterate on research-backed design |
| `dependency-setup` | Configure an environment or toolchain |
| `onboarding` | Guide contributor setup and repository understanding |
| `demo-showcase` | Build a presentation-ready demonstration |
| `product-verification` | Verify visual, interaction, accessibility, and acceptance quality |
| `entropy-cleanup` | Repair stale documentation or drift |
| `local-archive` | Inventory and archive local tasks with approved non-deletion moves |
| `workspace-compact` | Park risks by lifecycle and relocate settled work out of a task folder |
| `harness-construction` | Build harness infrastructure with machine-grounded gap analysis and a capability review |
| `pathfinder` | Look ahead for infrastructure and harness gaps before a later wave |
| `retro-digest` | Extract retrospective evidence and report cycle learning without implicit persistence |
| `migration` | Upgrade or port with rollback readiness |
| `skill-optimization` | Profile and improve an agent skill |
| `self-update` | Research and integrate reference updates |
| `nines-assisted` | Opaque historical compatibility seed ID |
| `repo-init` | Initialize workspace and governance surfaces |
| `change-driven` | Materialize the evidence-backed change lifecycle |
| `web-design` | Design, refine, and verify a frontend |

### Three-Layer Hierarchy

| Layer | Responsibility | Boundary |
|---|---|---|
| Project (L0) | Confirm contract, select rounds, adjudicate gates | Does not implement |
| Wave (L1) | Partition ownership-safe Tasks and aggregate evidence | Does not edit Task output |
| Task (L2) | Implement, converge, and report evidence | Does not spawn agents |

TaskDispatch moves down, StatusReport moves up, and escalation moves Task →
Wave → Project → Human.

### Built-in Harness

```bash
make test-harness
python -m devolaflow.harness aggregate --ledger .local/telemetry/harness.jsonl
python -m devolaflow.harness evaluate --ledger .local/telemetry/harness.jsonl --repo .
```

The built-in harness is the current evaluation source of truth. W-16 baseline
settlement and W-19 cycle archive retention are release policy performed
manually at cycle close; no automatic harness archive hook is implemented.
Immutable A-2.4 layout witnesses are separate from harness baselines.

## Versioning

The source version is `src/devolaflow/__init__.py`. Seven canonical sync
locations across eight files are updated by `scripts/bump_version.py`:

1. `workflow-system/agent/SKILL.md` (three patterns in one file)
2. `workflow-system/agent/workflow-skill.yaml`
3. `pyproject.toml`
4. `scripts/generate_human_docs.py`
5. `tests/test_smoke.py`
6. `README.md`
7. `packages/npm/package.json`

The source plus those sync locations make eight files. The README badge reads
`pyproject.toml` dynamically, and the Harness page reads the newest Timeline
entry at load time.

```bash
devola-version  # prints "DevolaFlow v24.0.0"
python scripts/bump_version.py X.Y.Z --dry-run
python -m pytest tests/test_version.py -v
```

## Repository Development

```bash
python -m pytest tests/ -q
ruff check src/ tests/
ruff format --check src/ tests/
make test-harness
make release-preflight
```

Governance sources live in `.rules/` and compile to `AGENTS.md`,
`.cursor/rules/repo-governance.mdc`, and `docs/STYLE-RULES.md`. Edit the source
layer and run `make compile-rules`; never hand-edit generated rule surfaces.

Release work uses a feature branch and Pull Request. After the release commit
is merged, maintainers create and push the version tag; the tag workflow runs
checks, creates the GitHub Release, and deploys Pages. See
[Release Workflow Design](docs/designs/design_release_workflow.md).

## Documentation and History

- [English Quickstart](workflow-system/human/en/quickstart.md)
- [中文快速入门](workflow-system/human/zh/quickstart.md)
- [English Integration Guide](workflow-system/human/en/integration-guide.md)
- [中文集成指南](workflow-system/human/zh/integration-guide.md)
- [Interactive documentation](https://yorha-agents.github.io/DevolaFlow/)
- [Timeline](https://yorha-agents.github.io/DevolaFlow/version-timeline/)
- [CHANGELOG](CHANGELOG.md)
- [Design documents](docs/designs/)

Release archaeology belongs in Timeline and CHANGELOG; this README describes
the current product contract.

## License

MIT, see [LICENSE](LICENSE).
