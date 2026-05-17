# NineS v2.0.0 vs DevolaFlow Integration Analysis

**Generated:** 2026-04-13  
**NineS CLI (observed):** `nines, version 2.0.0`  
**DevolaFlow baseline:** v4.5.0 (`src/devolaflow/nines/*`)  
**Reference doc:** `.local/feedbacks/feedback_from_NineS/integration_feedback.md` (NineS v1.0.0-pre)

**External release notes:** A dedicated v2.0.0 changelog was not retrieved from GitHub in this session (`CHANGELOG.md` 404 on `main`; releases page fetch timed out). Canonical repo: [https://github.com/YoRHa-Agents/NineS](https://github.com/YoRHa-Agents/NineS). Verify release text there when implementing upgrades.

---

## version_comparison

| Area | NineS v1.0.0-pre (integration feedback) | NineS v2.0.0 (CLI `--help`, 2026-04-13) |
|------|----------------------------------------|------------------------------------------|
| **Top-level commands** | `eval`, `collect`, `analyze`, `self-eval`, `iterate`, `install` | Same set **plus** `benchmark` (end-to-end workflow) and `update` (version check, install, skill refresh) |
| **Global CLI** | Implied `--format json` per subcommand | Explicit root options: `-c/--config`, `-v/--verbose`, `-q/--quiet`, `-o/--output`, `-f/--format [text\|json\|markdown]`, `--no-color` |
| **`collect`** | `nines collect github "<query>" --limit N` (positional source + query) | **Flag-based:** `--source [github\|arxiv]`, `--query TEXT`, `--max-results` (default 30), optional `--store-path` (SQLite persistence) |
| **`analyze`** | Positional path; `--depth deep`; `--decompose --index`; separate `nines analyze review <path> --reviewers …` | **Required** `--target-path PATH`; `--strategy [functional\|concern\|layer]`; `--output-dir`; `--depth [shallow\|deep]` (default **shallow**); `--agent-impact` / `--keypoints` toggles. No `review` subcommand in top-level help. Subcommand help shows **no** `--format` (use global `nines -f json analyze …`). |
| **`eval`** | Suite as main arg; `--scorer composite`; `--sandbox`; `--parallel`; `--report` | **`--tasks-path` required** (file or directory of TOML tasks); `--output-dir`; **`--scorers`** (repeatable; default `exact`); `--parallel` exists but help states **“not yet supported”** |
| **`self-eval`** | `--dimensions {list\|all}`; `--compare`; `--report` | **`--baseline-version`**, `--output-dir`, **`--project-root`**, **`--src-dir`**, **`--test-dir`**, **`--capability-only`**, **`--samples-dir`**, **`--golden-dir`**. No `--dimensions` in v2 help. |
| **`iterate` (MAPIM)** | `--max-rounds`, `--convergence-threshold`, `--format json` | `--max-rounds` (default 5), **`--threshold`** (default 0.05; replaces `--convergence-threshold` name), **`--project-root`**, **`--src-dir`**, **`--test-dir`**, **`--samples-dir`**, **`--golden-dir`**. No `--format` on subcommand (use global `-f json`). |
| **`install`** | `--target`, implied project-local | Adds **`--global`**, **`--force`**, **`--dry-run`**, **`--uninstall`** |
| **`benchmark`** | Not described in v1 feedback | **New:** “Full analysis→benchmark→evaluate→mapping workflow” with `--target-path`, `--rounds`, `--convergence-threshold`, `--output-dir`, `--suite-id`, `--tasks-path` |
| **`update`** | Not present | **New:** `nines update` with `--check`, `--skip-skills`, `--target`, `--global` |

**Compatibility risk:** DevolaFlow’s Python wrappers still emit **v1-style argv** in several places; against v2.0.0 those invocations are **likely to fail** (wrong positional patterns, renamed flags, or removed options).

---

## new_capabilities

1. **`benchmark` command** — Single entry for analyze → benchmark → evaluate → mapping; tunable rounds, convergence, custom `tasks-path`, suite id, output dir.
2. **`update` command** — Check/install NineS, optionally refresh skills across Cursor/Claude/Codex/Copilot (`--target`, `--global`, `--skip-skills`).
3. **Structured `collect`** — SQLite persistence via `--store-path`; consistent `--source` / `--query` API.
4. **`analyze` decomposition strategies** — `functional` | `concern` | `layer`; explicit `--output-dir` for artifacts.
5. **Project-scoped self-improvement** — `iterate` and `self-eval` accept **`--project-root`**, **`--src-dir`**, **`--test-dir`**, plus evaluator support dirs **`--samples-dir`**, **`--golden-dir`** (aligns V1 scoring evaluators D01/D03/D05 per help text).
6. **`self-eval` modes** — `--capability-only` for faster iteration; `--baseline-version` for comparisons over time.
7. **Global output control** — `-o` for file output; `-f json|markdown|text` at root for machine-readable pipelines.
8. **`install` lifecycle** — `--uninstall`, `--dry-run`, `--force`, `--global`.

---

## integration_gaps

### `detector.py`
- `_KNOWN_SUBCOMMANDS` omits **`benchmark`** and **`update`** (lines 20–21), so capability discovery does not reflect v2.
- Version regex may still match `2.0.0`; no gap if output remains `nines, version 2.0.0`.

### `scorer.py`
- `run_nines_eval` uses `["nines", "eval", artifact_path, …]` — v2 **`eval` requires `--tasks-path`**, not a bare positional suite path; **`--scorer` → `--scorers`**.
- `run_nines_analyze` uses positional `analyze <target>` + `--format json` — v2 requires **`--target-path`**; `--format` is not on the subcommand help (should use **`nines -f json analyze`** or root `-f`).
- `nines_dimension_scores` passes **`--parallel`, `--report`** to eval — **`--parallel` unsupported** in v2 help; may error or be ignored.

### `advisor.py`
- Default **`nines analyze review {path}`** — no `review` subcommand in v2 top-level `analyze` help.
- Default **`nines self-eval --dimensions all`** — **`--dimensions` absent** from v2 `self-eval --help`.
- Default **`nines iterate --max-rounds 1`** omits v2-relevant **`--project-root`** / dirs; uses old mental model of “single measure pass” without repo context.

### `researcher.py`
- **`collect_research`**: builds `nines collect <source> <query> … --limit` — v2 expects **`--source`**, **`--query`**, **`--max-results`** (not `--limit`).
- **`analyze_target`**: positional analyze + `--decompose --index` — v2 uses **`--target-path`** and does not document **`--decompose` / `--index`** on `analyze --help`.
- **`run_self_evaluation`**: **`--dimensions`** — not in v2 help; should map to **`--project-root`**, **`--capability-only`**, **`--baseline-version`**, etc.
- **`run_skill_iteration`**: uses **`--convergence-threshold`** — v2 renamed to **`--threshold`**; should pass **`--project-root`** (and optional test/sample/golden dirs) for meaningful MAPIM runs on DevolaFlow.

### Cross-cutting
- No wrapper for **`nines benchmark`** or **`nines update`**.
- No use of **`-c / --config`** (`nines.toml`) for reproducible DevolaFlow+NineS runs.
- Tests in `tests/test_nines.py` assert **old argv shapes** (e.g. `collect` line 847); they document v1 contracts, not v2.

---

## improvement_proposals

1. **Argv modernization (breaking, targeted)**  
   - Update `collect_research` to: `nines collect --source <s> --query <q> --max-results <n>` and optional `--store-path`.  
   - Update `run_nines_analyze` / `analyze_target` to: `nines -f json analyze --target-path <path> --depth deep` plus flags for strategy, output dir, agent-impact/keypoints as needed.  
   - Update `run_nines_eval` to: `nines -f json eval --tasks-path <path> --scorers <…>` and drop or guard unsupported `--parallel`.  
   - Update `run_self_evaluation` and `run_skill_iteration` to v2 flags (`--threshold`, project/src/test dirs, `--capability-only` where appropriate).

2. **`detector.get_nines_capabilities`**  
   - Extend `_KNOWN_SUBCOMMANDS` with **`benchmark`** and **`update`**, or parse the `Commands:` section dynamically instead of a fixed tuple.

3. **New thin APIs**  
   - `run_nines_benchmark(...)` wrapping `nines benchmark` with `target-path`, `tasks-path`, `output-dir`.  
   - `run_nines_update(check_only: bool, ...)` for self-update workflow alignment with `nines update`.

4. **`NinesAdvisorConfig` defaults**  
   - Replace deprecated command strings with v2-safe templates (e.g. `self-eval` with `--project-root {path}` and `-f json` at root). Remove or replace `analyze review` trigger until NineS exposes an equivalent in v2 docs.

5. **Documentation**  
   - Refresh internal references (e.g. gate/scorer comments, plugin YAML examples) so examples match v2; link [NineS repo](https://github.com/YoRHa-Agents/NineS) for canonical CLI changes.

6. **Tests**  
   - Adjust unit tests to expected argv for v2; add optional integration test marked slow/skipped if `nines` is v2.

---

## self_improve_loop

**Goal:** Use NineS v2.0.0 MAPIM-style tooling for DevolaFlow’s **self-update / skill-optimization** workflows (research → profile → optimize → benchmark → iterate).

1. **Baseline measurement (`self-eval`)**  
   Run against the DevolaFlow repo root with explicit layout so V1/V3 evaluators can find code and tests, e.g. conceptually:  
   `nines -f json self-eval --project-root . --src-dir src --test-dir tests --baseline-version v4.5.0 --output-dir .local/nines/self-eval/`  
   Use **`--capability-only`** during rapid tuning; full runs when preparing a release.

2. **Structured improvement cycle (`iterate`)**  
   Point MAPIM iteration at the same project surfaces:  
   `nines -f json iterate --project-root . --src-dir src --test-dir tests --max-rounds N --threshold <variance>`  
   Optional **`--samples-dir`** / **`--golden-dir`** when exercising EvalCoverage / golden-based scorers (per help).

3. **End-to-end quality pass (`benchmark`)**  
   For a single “self-improve loop” artifact bundle, use **`nines benchmark`** to run the full analyze→benchmark→evaluate→mapping pipeline when you need a consolidated report (e.g. before tagging a DevolaFlow minor release).

4. **Distribution sync (`update` + `install`)**  
   After upgrading NineS: `nines update` (or `nines update --check`) and refresh skills so **Cursor/Codex/Claude** copies stay aligned; parallels DevolaFlow’s own `build-skill` / adapter sync.

5. **DevolaFlow orchestration fit**  
   Map the above to stages: **validate** / **monitor** primitives can trigger `self-eval` + compare baselines; **refine** / convergence rounds can invoke `iterate`; **release** can run `benchmark` once + archive `output-dir` under `.local/` or CI artifacts. Keep machine-readable output via **`nines -f json`** and optional **`-o`** for logs.

---

## Appendix: v2.0.0 subcommand summaries (observed)

- **Root:** `-c/--config`, `-v/--verbose`, `-q/--quiet`, `-o/--output`, `-f/--format`, `--no-color`  
- **analyze:** `--target-path` (required), `--strategy`, `--output-dir`, `--agent-impact` / `--keypoints`, `--depth`  
- **benchmark:** `--target-path`, `--rounds`, `--convergence-threshold`, `--output-dir`, `--suite-id`, `--tasks-path`  
- **collect:** `--source`, `--query`, `--max-results`, `--store-path`  
- **eval:** `--tasks-path` (required), `--output-dir`, `--scorers`, `--parallel` (not yet supported)  
- **install:** `--target`, `--global`, `--force`, `--dry-run`, `--uninstall`  
- **iterate:** `--max-rounds`, `--threshold`, `--project-root`, `--src-dir`, `--test-dir`, `--samples-dir`, `--golden-dir`  
- **self-eval:** `--baseline-version`, `--output-dir`, `--project-root`, `--src-dir`, `--test-dir`, `--capability-only`, `--samples-dir`, `--golden-dir`  
- **update:** `--check`, `--skip-skills`, `--target`, `--global`
