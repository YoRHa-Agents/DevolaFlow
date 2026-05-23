# Codegraph Reference

DevolaFlow's integration with `colbymchenry/codegraph` — a 100% local, MCP-first, pre-indexed code knowledge graph (tree-sitter AST → SQLite FTS5). v12.5.0 PV-03 D-1 ships codegraph as the primary deliverable: a tracked reference repo, fully wired plugin, and Python wrapper exposed to L0/L1/L2/L3 dispatchers.

**Upstream**: <https://github.com/colbymchenry/codegraph> · npm: `@colbymchenry/codegraph@>=0.9.3`

## §1 — What codegraph is + when L3 should use it

Codegraph indexes the project's source files into a SQLite FTS5 database stored locally at `.codegraph/codegraph.db` (gitignored, project-relative per S-2). The index is populated via tree-sitter parsers covering 19+ languages; auto-syncs on file events with a 2-second debounce. Files matching `.gitignore` and files larger than 1MB are skipped automatically.

**Upstream-published benchmark (verbatim)**: across 7 codebases × 7 languages, codegraph delivers **35% cheaper API cost / 70% fewer tool calls / 59% fewer tokens / 49% faster** wall-clock per agent query, vs. the Read+Grep+Glob baseline.

L3 task agents should reach for codegraph instead of Read/Glob/Grep when:

| L3 use-case | Codegraph helper | Token-spend delta (est.) |
|---|---|---|
| "Find all callers of `process_payment`" | `codegraph callers process_payment` | -65% vs. `Grep "process_payment"` + Read each match |
| "Show me the related code around `MerchantOnboarding`" | `codegraph context "MerchantOnboarding"` | -55% vs. multi-Read of related files |
| "What gets affected if I change `parse_invoice`?" | `codegraph impact parse_invoice --depth 3` | -50% vs. heuristic call-graph trace |
| "What's the project structure here?" | `codegraph files --format tree` | -60% vs. recursive `Glob "**/*.{py,ts,go}"` |
| "Which tests should I run for these changed files?" | `codegraph affected --files <files>` | New capability — no manual equivalent |

L0/L1/L2 dispatchers should reach for codegraph during planning when:

* `analyze` stage of a workflow needs project-shape data (replaces fs scanning)
* `scaffold` stage needs related-symbol seeds for `owned_files.txt`
* Gate scoring needs blast-radius for code-review weight allocation

L3 should NOT reach for codegraph when:

* The .codegraph/ index is missing (CLI not installed or `codegraph init` never ran) — fall back to Read/Glob/Grep per §5 degraded-mode contract
* The query is for a literal string that doesn't correspond to a symbol (e.g. arbitrary code comments) — Grep is faster
* The file in question is gitignored or > 1MB — codegraph deliberately skips these

## §2 — The 9 MCP tools (with L3 decision tree)

Codegraph ships an MCP server with 9 tools. L3 agents running inside an MCP-aware host (Cursor, Claude Code, Codex CLI) invoke these directly; L3 agents running through DevolaFlow's Python wrapper (`devolaflow.codegraph.researcher`) get 5 of them as direct method calls (see §3).

| Tool | When to use | Returns |
|---|---|---|
| `codegraph_search` | "Find symbols matching `<query>`" | List of symbol records (name + kind + file + line) |
| `codegraph_context` | "Build me a context bundle around `<query>`" | Markdown / JSON: entry points + related symbols + snippets |
| `codegraph_callers` | "Who calls `<symbol>`?" | List of caller records (caller name + file + line + edge kind) |
| `codegraph_callees` | "What does `<symbol>` call?" | List of callee records (forward-edge equivalent) |
| `codegraph_impact` | "What's the blast radius if `<symbol>` changes?" | Structured payload: directly + transitively affected symbols, depth-N traversal |
| `codegraph_node` | "Get the source for `<symbol>`" | Single-node record with full source body |
| `codegraph_explore` | "Get the source for `<symbol>` AND its related cluster" | Multi-node response (replaces multi-Read) |
| `codegraph_files` | "What's the project file structure?" | File-tree (flat list / tree format) |
| `codegraph_status` | "Is the index healthy?" | Index health: db path + symbol count + last sync timestamp |

**Decision tree for L3 (single-symbol query)**:

```
"I need to know about <symbol>"
    ├── "Where is it defined?"               → codegraph_node
    ├── "What calls it?"                     → codegraph_callers
    ├── "What does it call?"                 → codegraph_callees
    ├── "What changes if I edit it?"         → codegraph_impact
    └── "What lives near it (siblings)?"     → codegraph_explore
```

**Decision tree for L3 (multi-symbol / topic query)**:

```
"I need to know about <topic>"
    ├── "What symbols match the topic?"      → codegraph_search
    ├── "Build me a topic-shaped bundle"     → codegraph_context
    ├── "Show me the project file shape"     → codegraph_files
    └── "Index health check"                 → codegraph_status
```

## §3 — CLI surface

The codegraph CLI binary exposes these subcommands:

| Subcommand | Purpose | Typical invocation |
|---|---|---|
| `codegraph init [<project_root>]` | Create `.codegraph/` index for a project | `codegraph init .` |
| `codegraph index` | Re-index files (full or incremental) | `codegraph index --prune-deleted` |
| `codegraph sync` | Force a sync pass (debugging file-watcher) | `codegraph sync` |
| `codegraph query "<query>"` | FTS5 query (low-level; prefer `search`) | `codegraph query "process_payment"` |
| `codegraph search "<query>"` | Symbol search with kind filter | `codegraph search Foo --kind class --json` |
| `codegraph context "<query>"` | Context bundle for a topic | `codegraph context "auth flow" --max-nodes 30` |
| `codegraph callers <symbol>` | Reverse-call edges | `codegraph callers handler --limit 20 --json` |
| `codegraph callees <symbol>` | Forward-call edges | `codegraph callees handler --json` |
| `codegraph impact <symbol>` | Blast-radius analysis | `codegraph impact parse_x --depth 3 --json` |
| `codegraph files [--format <fmt>]` | File-tree dump | `codegraph files --format tree` |
| `codegraph affected --files <f1> <f2>` | Selective test-impact | `codegraph affected --files src/foo.py --json` |
| `codegraph serve` | Run the MCP server | `codegraph serve` |
| `codegraph status` | Health check | `codegraph status` |
| `codegraph install --target <ai>` | Agent-installer (writes `.cursor/rules/codegraph.mdc` etc.) | `codegraph install --target cursor --yes` |

Most subcommands accept `--json` to force JSON output (machine-friendly); the default text output is markdown / human-friendly.

## §4 — DevolaFlow integration map

### §4.1 — Plugin registries (per A-5 SSOT)

| Registry surface | File | Codegraph entry |
|---|---|---|
| Plugin catalog (PluginRegistry consumer) | `workflow-system/agent/plugins.yaml` | `plugins.codegraph` block + `plugin_roles.code_intelligence` |
| Runtime registry (installer consumer) | `workflow-system/agent/knowledge/runtime-plugins.yaml` | `plugins[id=codegraph]` entry |
| Reference tracking (W-2 / SI-2 reference review) | `workflow-system/agent/knowledge/reference-dependencies.yaml` | `active_tracking[id=codegraph]` entry (12th of 12) |

### §4.2 — Workflow templates (per W-15 / CO-6 section relevance)

| Workflow | Stage | Codegraph wiring |
|---|---|---|
| repo-init | analyze | `config.codegraph_commands` (status + files) |
| repo-init | scaffold | `config.codegraph_init` (cmd + on_failure: warn + add_to_gitignore) — runs in **ALL modes** (core/standard/full) |
| repo-init | verify | `config.codegraph_smoke` (path presence check) — mode=full only |
| onboarding | analyze | `config.codegraph_commands` (entry_points + files) |
| security-audit | analyze | `config.codegraph_commands` (callers + impact for attack-surface) |
| product-verification | analyze | `config.codegraph_commands` (explore + impact for feature surface) |

### §4.3 — Context profile

`workflow-system/agent/context_profiles.yaml::meta.codegraph_integration` declares the 5 commands recipes (`repo_init`, `analyze`, `research`, `impact`, `affected`) + 6 capability triggers (`smart_context_building`, `full_text_search`, `impact_analysis`, `callers_callees_trace`, `file_structure_lookup`, `test_impact_selection`). The block is parallel to `meta.nines_integration` and `meta.ui_integration`.

### §4.4 — Python wrapper

`devolaflow.codegraph` exposes 5 public researcher helpers:

| Function | Wraps CLI | Returns | On degraded |
|---|---|---|---|
| `build_context(query, *, max_nodes=20, fmt="markdown")` | `codegraph context` | `str` (markdown) | `""` |
| `search_symbols(query, *, kind=None, limit=10)` | `codegraph search` | `list[dict]` | `[]` |
| `get_impact(symbol, *, depth=3)` | `codegraph impact` | `dict` | `{}` |
| `get_callers(symbol, *, limit=20)` | `codegraph callers` | `list[dict]` | `[]` |
| `get_affected_tests(changed_files)` | `codegraph affected` | `list[str]` | `[]` |

The empty result is the SIGNAL to the caller that codegraph is degraded. Callers MUST then fall back to Read/Glob/Grep per §5.

The thin subprocess wrapper at `devolaflow.codegraph._cli.run_codegraph_cli` is the single owner of every codegraph CLI invocation. It distinguishes 4 structured causes for unavailability (`path_missing`, `timeout`, `nonzero_exit`, `json_parse_error`) via the `CodegraphUnavailableError.cause` attribute.

### §4.5 — Env flag (per W-20 reuse-first)

NO new `DEVOLAFLOW_*` env flag is introduced. Codegraph reuses the existing `DEVOLAFLOW_AUTO_INSTALL_PLUGINS=1` flag for opt-in runtime installation through `devolaflow.lifecycle.pre_plugin_invocation`. The W-20 orthogonality test passed because codegraph shares the runtime-installer activation surface with `nines` + `ui-pro` + `rtk` + `si-chip` (the 4 existing v10.2.0 baseline plugins).

Operators who want codegraph auto-installed AND don't want manual `npm install`:

```bash
export DEVOLAFLOW_AUTO_INSTALL_PLUGINS=1
# ... run any DevolaFlow workflow that invokes codegraph
```

When the env flag is unset (default), codegraph CLI is expected to be on `$PATH` already (manually installed via `npm install -g @colbymchenry/codegraph`); when both fail, the degraded-mode contract takes over.

## §5 — Degraded-mode contract

When codegraph CLI is unavailable, every researcher helper degrades gracefully. The degraded path is the documented contract per `references/degraded-mode.md` codegraph row.

### §5.1 — Detection

`devolaflow.codegraph._cli.run_codegraph_cli` raises `CodegraphUnavailableError` with one of 4 structured `cause` values:

| Cause | Trigger | Caller fallback |
|---|---|---|
| `path_missing` | `shutil.which("codegraph")` returns `None` | Read/Glob/Grep + WARN suggesting `npm install -g @colbymchenry/codegraph` |
| `timeout` | Subprocess exceeded the timeout window | Retry once with longer timeout, then fall back |
| `nonzero_exit` | CLI present but the subcommand failed | Fall back; log stderr at WARNING |
| `json_parse_error` | CLI returned non-JSON when JSON expected | Fall back; treat as malformed-index signal |

### §5.2 — Researcher API behaviour

Each public helper in `devolaflow.codegraph.researcher`:

1. Catches `CodegraphUnavailableError` from `run_codegraph_cli`
2. Logs WARNING **once per process** (deduplicated via module-level sentinel `_DEGRADED_MODE_NOTIFIED`); subsequent calls log at DEBUG to preserve auditability without spam
3. Returns the empty / sentinel result documented in §4.4

The caller (L0/L1/L2/L3 dispatcher OR gate scorer) detects the empty result and falls back to the equivalent Read/Glob/Grep planning path.

### §5.3 — Repo-init scaffold step behaviour

`workflow-system/agent/templates/builtin/repo-init.yaml::scaffold.config.codegraph_init` declares `on_failure: "warn"`. When the CLI is not on `$PATH` AND `DEVOLAFLOW_AUTO_INSTALL_PLUGINS=1` is unset:

* Scaffold step emits a non-blocking WARN: `npm i -g @colbymchenry/codegraph` recommendation
* Workflow CONTINUES — codegraph integration is opt-in for cost-conscious environments
* Per S-5: WARN + continue, NOT silent fail

### §5.4 — Verify step behaviour (mode=full only)

`workflow-system/agent/templates/builtin/repo-init.yaml::verify.config.codegraph_smoke` checks for `.codegraph/codegraph.db` presence with `on_missing: "warn"`. When the index is missing:

* Verify smoke emits a WARN
* The verify suite as a whole still reports PASS — codegraph index absence is a degraded-mode signal, not a verification failure

### §5.5 — Gate scoring degraded behaviour

When the gate scorer normally consumes `get_impact()` for blast-radius weighting, an empty `{}` result causes the `codegraph_impact` dimension's weight to redistribute proportionally to the other gate inputs. The gate verdict is still computed; the dimension is dropped silently from THAT gate evaluation only.

## §6 — Cache management

### §6.1 — Storage layout

```
<project_root>/
├── .codegraph/
│   ├── codegraph.db      # SQLite FTS5 index (project-local; gitignored)
│   ├── parser-cache/     # tree-sitter parser binaries (per-language; small)
│   └── lock              # file-watcher lock file
└── ...
```

The `.codegraph/` directory MUST be gitignored. The repo-init scaffold step adds `.codegraph/` to `.gitignore` automatically (see §4.2). Manual installs should add the entry by hand.

### §6.2 — Index size expectations

| Repo size | Typical .codegraph/ size |
|---|---|
| < 10K LOC | < 5MB |
| 10K-100K LOC | 5-50MB |
| 100K-1M LOC (monorepo) | 50-500MB |
| > 1M LOC | Use `codegraph index --prune-deleted` periodically |

### §6.3 — File-watcher discipline

Codegraph auto-syncs via OS file events:

* macOS: FSEvents
* Linux: inotify
* Windows: ReadDirectoryChangesW (RDCW)

Debounce is 2 seconds — rapid edits within a 2-second window trigger a single re-index pass. For sessions with very high-frequency edits (e.g. test-driven development with watch-mode test runners), `codegraph status` confirms the last-sync timestamp; manual `codegraph sync` forces a flush.

### §6.4 — Privacy considerations

The `.codegraph/codegraph.db` contains symbol names + signatures + snippet offsets for every file NOT matching `.gitignore`. For repos with secrets-in-comments anti-patterns, consider:

* Adding `.local/secrets/` style patterns to `.gitignore` proactively
* Auditing the index after first build via `codegraph search "TODO\|FIXME\|password\|secret"` to spot-check exposure
* The index is project-local and never uploaded; codegraph has zero network egress

### §6.5 — When to wipe + rebuild

Wipe `.codegraph/` and re-run `codegraph init` when:

* Upgrading codegraph to a new major version (the index schema MAY change)
* Switching git branches with significant file structure differences
* The index size grows beyond expected (likely a leaked large file)
* `codegraph status` reports parser version drift across languages

The wipe is harmless — the index rebuilds on the next workflow invocation.

---

**Source**: `.local/research/v12.5.0_gap_analysis.md` §2 D-1 + `.local/research/v12.5.0_codegraph_benefit_analysis.md` §1-§6. **External tool URL** (per S-7): `https://github.com/colbymchenry/codegraph`.
