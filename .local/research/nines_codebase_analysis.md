# NineS v2.0.0 — DevolaFlow codebase analysis

**Generated:** 2026-04-13 (research artifact, `.local/research/`)

**NineS CLI:** `nines, version 2.0.0` (`which`: `/root/miniforge/bin/nines`)

**Note on JSON output:** In NineS v2.0.0, `--format` is a **global** option (`-f` / `--format`), not a subcommand option. Use `nines -f json <command> ...` instead of `nines <command> --format json`.

---

## commands_run

| # | Command | Exit |
|---|---------|------|
| 1 | `nines analyze /home/agent/workspace/DevolaFlow/src/devolaflow --format json 2>&1` | **2** — `Error: No such option: --format` |
| 2 | `nines self-eval --format json 2>&1` | **2** — `Error: No such option: --format` |
| 3 | `nines analyze /home/agent/workspace/DevolaFlow/workflow-system/agent/SKILL.md --format json 2>&1` | **2** — same `--format` error |
| 4 | `nines analyze /home/agent/workspace/DevolaFlow/src/devolaflow 2>&1` | **2** — `Error: Missing option '--target-path'.` |
| 5 | `nines self-eval 2>&1` | **2** — `Invalid value for '--src-dir': Path 'src/nines' does not exist.` (defaults assume NineS repo layout) |
| 6 | `nines analyze /home/agent/workspace/DevolaFlow/workflow-system/agent/SKILL.md 2>&1` | **2** — missing `--target-path` |
| 7 | `nines --help 2>&1` | **0** |
| 8 | `nines analyze --help 2>&1` | **0** |
| 9 | `nines self-eval --help 2>&1` | **0** |
| 10 | `nines iterate --help 2>&1` | **0** |
| 11 | `nines collect --help 2>&1` | **0** |
| 12 | `nines -f json analyze --target-path /home/agent/workspace/DevolaFlow/src/devolaflow 2>&1` | **0** (full JSON on stdout; also saved to `.local/research/nines_analyze_devolaflow.json` via shell redirect) |
| 13 | `nines -f json self-eval --project-root /home/agent/workspace/DevolaFlow --src-dir /home/agent/workspace/DevolaFlow/src/devolaflow --test-dir /home/agent/workspace/DevolaFlow/tests 2>&1` | **0** (~40s; stderr warnings before JSON) |
| 14 | `nines -f json analyze --target-path /home/agent/workspace/DevolaFlow/workflow-system/agent/SKILL.md 2>&1` | **1** — `AnalyzerError: Not a Python file` (see below) |

**Successful corrected invocations (reference):**

```bash
nines -f json analyze --target-path /home/agent/workspace/DevolaFlow/src/devolaflow
nines -f json self-eval \
  --project-root /home/agent/workspace/DevolaFlow \
  --src-dir /home/agent/workspace/DevolaFlow/src/devolaflow \
  --test-dir /home/agent/workspace/DevolaFlow/tests
```

---

## analysis_results

**Source:** `nines -f json analyze --target-path .../src/devolaflow` (exit 0). Full machine-readable output: `.local/research/nines_analyze_devolaflow.json`.

### Summary metrics (from JSON `metrics`)

| Metric | Value |
|--------|------|
| `files_analyzed` | 44 |
| `total_lines` | 6487 |
| `total_functions` | 205 |
| `total_classes` | 67 |
| `avg_complexity` | 3.84 |
| `knowledge_units` | 272 |
| `duration_ms` | ~133–137 |
| `packages` | 7 |

### Findings by severity (main `findings` array)

| Severity | Count |
|----------|------|
| info | 89 |
| warning | 6 |
| error | 1 |

### Non-info findings (cyclomatic complexity)

NineS flags high cyclomatic complexity with suggestions to decompose functions:

| Severity | Function | Location | Suggestion |
|----------|----------|----------|------------|
| **error** | `select_context` (complexity 23) | `src/devolaflow/task_adaptive_selector.py:162` | Break into smaller pieces |
| warning | `ProposalGenerator.generate_proposals` (15) | `src/devolaflow/feedback.py:225` | Break into smaller pieces |
| warning | `evaluate_gate` (12) | `src/devolaflow/gate/scorer.py:240` | Break into smaller pieces |
| warning | `_evaluate_convergence` (11) | `src/devolaflow/gate/scorer.py:347` | Break into smaller pieces |
| warning | `_interpret_result` (13) | `src/devolaflow/nines/advisor.py:70` | Break into smaller pieces |
| warning | `parse_composition` (15) | `src/devolaflow/template_engine/parser.py:108` | Break into smaller pieces |
| warning | `_expand_loops_gates` (14) | `src/devolaflow/template_engine/validator.py:291` | Break into smaller pieces |

### Agent impact analysis (limitation for this path)

Because the target was **only** `src/devolaflow` (Python package), NineS reported:

- `AI-0000` / `AI-0001`: **0 agent-facing artifacts**; message states the repo “does not appear to target AI Agent integration.”
- This is a **scope artifact**: workflow skills, `SKILL.md`, and references under `workflow-system/` were not in the analyzed tree. For agent-integration signal, analyze a directory that includes those artifacts or run a broader `--target-path` (e.g. repo root) if/when the analyzer supports mixed content.

### Key points (`metrics.key_points`)

Three key points were extracted, including:

1. **behavioral_shaping:** agent_impact finding (0 artifacts).
2. **engineering:** `select_context` cyclomatic complexity 23 (`task_adaptive_selector.py:162`).
3. **engineering:** coverage summary (44 Python files, 272 knowledge units).

---

## self_eval_results

**Command:** `nines -f json self-eval --project-root /home/agent/workspace/DevolaFlow --src-dir /home/agent/workspace/DevolaFlow/src/devolaflow --test-dir /home/agent/workspace/DevolaFlow/tests`

**Exit:** 0  
**Duration (reported):** ~39.6s  
**Stderr (non-fatal warnings):**

```
Golden test set directory not found: data/golden_test_set
Golden test set directory not found: data/golden_test_set
Golden test set directory not found: data/golden_test_set
Pipeline target does not exist: src/nines/__init__.py
Could not parse coverage from pytest output
```

### Aggregate scores

| Field | Value |
|-------|------|
| `overall` | 0.7264895 |
| `capability_mean` | 0.694985 |
| `hygiene_mean` | 0.8 |
| Weights | capability 0.7, hygiene 0.3 |

### Major gaps (normalized 0.0 or materially low)

| Capability | Normalized | Notes |
|------------|------------|------|
| `scoring_accuracy` | 0.0 | `no golden tasks found in data/golden_test_set` |
| `eval_coverage` | 0.0 | `no TOML files found` |
| `scoring_reliability` | 0.0 | golden tasks missing |
| `scorer_agreement` | 0.0 | golden tasks missing |
| `pipeline_latency` | 0.0 | `target not found: src/nines/__init__.py` (NineS-internal path; wrong for DevolaFlow) |
| `index_recall` | 0.4 | 5 queries tested, 2 with results |
| `source_freshness` | 0.5 | 1/2 sources “fresh” under 30-day window |

### Hygiene notes

- `code_coverage` (pytest): **0.0 normalized** — “Could not parse coverage from pytest output” / metadata shows pytest source but no percentage.
- `test_count`: 643 tests collected (normalized 1.0).
- `docstring_coverage`: 100% (180/180).
- `lint_cleanliness`: 100% (0 violations).

### Strong areas (normalized 1.0 examples)

Includes: `report_quality`, `source_coverage`, `change_detection`, `data_completeness`, `collection_throughput`, `decomposition_coverage`, `abstraction_quality`, `code_review_accuracy`, `structure_recognition`, `sandbox_isolation`, `convergence_rate`, `cross_vertex_synergy`, `agent_analysis_quality` (within the Python analysis scope).

---

## skill_analysis

**Attempt:** `nines -f json analyze --target-path /home/agent/workspace/DevolaFlow/workflow-system/agent/SKILL.md`

**Result:** **Failed (exit 1).** Full traceback excerpt:

```
nines.core.errors.AnalyzerError: Not a Python file: /home/agent/workspace/DevolaFlow/workflow-system/agent/SKILL.md
```

**Assessment:** NineS `analyze` in v2.0.0 **ingests Python sources only** for the given target path. It cannot directly score `SKILL.md` as a markdown skill file.

**Indirect signal from core analysis:** Agent-facing narrative in `workflow-system/agent/` is **outside** the `src/devolaflow` analysis, so the tool’s agent-impact heuristics underreport DevolaFlow’s real agent integration (skills, adapters, docs).

**Practical workarounds for skill quality:**

1. Use human/LLM review of `SKILL.md` against repo rules (line budget, frontmatter, references).
2. If NineS adds markdown or repo-root analysis modes in a future version, re-run with those flags.
3. Optionally analyze a **Python-heavy** path that mirrors skill generation (e.g. `src/devolaflow/build_skill.py`) — already included in the main analyze run.

---

## improvement_proposals

Derived from NineS output (not edited for opinion):

1. **Refactor high-complexity functions** — Prioritize `select_context` (error-level CC 23), then `generate_proposals`, `parse_composition`, `_expand_loops_gates`, `_interpret_result`, `evaluate_gate`, `_evaluate_convergence`, per table above.
2. **Coverage tooling alignment** — Fix pytest coverage parsing for self-eval (`code_coverage` 0) so hygiene reflects DevolaFlow’s real test coverage.
3. **Golden / eval fixtures (if using NineS evaluators)** — Add `data/golden_test_set` and eval TOML fixtures if you want non-zero `scoring_*` and `eval_coverage` scores in `self-eval`.
4. **Broader target for agent-impact** — Re-run analyze with a target that includes skill and workflow trees when the analyzer supports it, to avoid false “no agent integration” signal.
5. **Index / discoverability** — `index_recall` 0.4 suggests improving searchable labels or structure for queries like “evaluation runner”, “code review”, “sandbox isolation” (per `query_details` in JSON).

---

## iterate_capability

**Available:** Yes. Command: `nines iterate`

**Purpose (from `nines iterate --help`):** “Execute a self-improvement iteration cycle.”

**Options:**

| Option | Default | Description |
|--------|---------|---------------|
| `--max-rounds` | 5 | Maximum iteration rounds |
| `--threshold` | 0.05 | Convergence variance threshold |
| `--project-root` | — | Project root directory |
| `--src-dir` | auto | Source directory for analysis |
| `--test-dir` | auto | Test directory |
| `--samples-dir` | — | Sample eval directory (EvalCoverageEvaluator) |
| `--golden-dir` | — | Golden test set for V1 scoring evaluators |

**Example (DevolaFlow-oriented):**

```bash
nines iterate \
  --project-root /home/agent/workspace/DevolaFlow \
  --src-dir /home/agent/workspace/DevolaFlow/src/devolaflow \
  --test-dir /home/agent/workspace/DevolaFlow/tests
```

**`nines collect`:** Requires `--source [github|arxiv]` and `--query` (search/collect workflow); not a codebase static analyzer.

---

## Raw artifacts

- Full analyze JSON: `.local/research/nines_analyze_devolaflow.json` (~36 KiB)
- Full self-eval JSON: `.local/research/nines_self_eval_devolaflow.json` (~15 KiB)
- Self-eval stderr (warnings): `.local/research/nines_self_eval_devolaflow.stderr`

---

## Appendix — stderr + first lines of self-eval JSON

Stderr lines are listed in **self_eval_results**. The JSON body begins with:

```json
{
  "version": "",
  "timestamp": "2026-04-13T17:07:50.621766+00:00",
  "duration": 39.63702921429649,
  "overall": 0.7264895,
  ...
}
```

(Full JSON omitted here; identical structure to terminal capture — use the saved file from the successful run if re-parsing is needed.)
