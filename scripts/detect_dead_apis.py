#!/usr/bin/env python3
"""Static analyzer: detect public APIs in src/devolaflow with no production callers.

Catches the bug class where a public function/class exists, has unit tests
that import it, but no actual production code uses it. The v6.0.3 dead-wire
bug (``apply_round_escalation`` and ``merge_reinforcement_into_dispatch`` had
passing unit tests but ZERO production callers) cost 3 versions to detect and
fix. This script catches that class of bug at the source via CI.

Usage::

    python scripts/detect_dead_apis.py                  # text report, exit 0
    python scripts/detect_dead_apis.py --strict          # exit 2 if dead found
    python scripts/detect_dead_apis.py --format json     # JSON output

Programmatic API::

    from scripts.detect_dead_apis import find_dead_apis
    dead = find_dead_apis(src_dirs, test_dirs, allowlist=...)

Algorithm:

1. Walk ``src/devolaflow/**/*.py`` with the ``ast`` module. For each file,
   collect top-level ``def`` and ``class`` statements that:
   - Do not start with ``_`` (skip private and dunder)
   - Are not a CLI entry point (``main``, ``cli``, ``*_cmd``)
2. For each public symbol, scan candidate caller files in
   ``src/devolaflow/`` plus ``scripts/`` plus ``benchmarks/`` (NOT tests/)
   using AST. A "real use" is an ``ast.Name`` or ``ast.Attribute`` reference
   outside of an ``Import``/``ImportFrom`` statement — this excludes pure
   re-exports in ``__init__.py``. The defining file IS included in the
   search; the ``def``/``class`` statement that creates the symbol does not
   itself produce a ``Name`` node, so any other reference (recursive call,
   factory, decorator usage, instantiation by sibling code) keeps the
   symbol "alive". The dead-wire bug pattern was a function with literally
   zero production references — exactly what this catches.
3. Symbols with zero real-use references in any production file are
   reported as dead, unless they appear in the allowlist.

Stdlib only.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

CLI_ENTRY_NAMES: frozenset[str] = frozenset({"main", "cli"})
CLI_ENTRY_SUFFIX: str = "_cmd"


DEFAULT_ALLOWLIST: frozenset[str] = frozenset(
    {
        # ---- Lifecycle hooks public API (P-05 in v7.4.8) ----
        # Per the v7.5.0 ghost-audit §3.C G-C1 closure design and the
        # P-05 dispatch directive, the lifecycle package is intentionally
        # NOT wired into existing dispatch / write / status flows in this
        # patch — integration is deferred to a future iteration. The four
        # public entry-points below are advertised in
        # ``workflow-system/agent/SKILL.md`` §"Lifecycle Hooks" and consumed
        # by external orchestrators (and ``tests/test_lifecycle_hooks.py``)
        # in lieu of an in-repo production call site.
        "devolaflow.lifecycle.dispatcher:run_hooks",
        "devolaflow.lifecycle.dispatcher:register_hook",
        "devolaflow.lifecycle.dispatcher:clear_hooks",
        "devolaflow.lifecycle.dispatcher:registered_events",
        # ---- Adapter base API — subclassed/instantiated externally ----
        "devolaflow.adapters.base:BaseAdapter",
        "devolaflow.adapters.base:AdapterResult",
        "devolaflow.adapters.base:load_workflow_skill",
        # ---- Registry factories — entry points for external consumers ----
        "devolaflow.adapters.registry:create_default_registry",
        "devolaflow.plugins.loader:create_default_registry",
        # ---- CLI entry-point modules (also caught by name patterns) ----
        "devolaflow.build_skill:build_all",
        # ---- MIGRATION-v6.md recommended stable public API ----
        # The documented stable replacements for v6.0 removals. Allowlisted
        # even when an in-repo caller exists, so a future refactor that
        # drops the caller does not silently break the public contract.
        "devolaflow.gate.scorer:evaluate_gate",
        "devolaflow.gate.reinforcement:findings_to_reinforcement",
        "devolaflow.gate.reinforcement:merge_reinforcement_into_dispatch",
        "devolaflow.gate.reinforcement:reinforcement_to_dict",
        "devolaflow.task_adaptive_selector:apply_round_escalation",
        "devolaflow.task_adaptive_selector:apply_plan_mode_overrides",
        "devolaflow.task_adaptive_selector:select_context",
        "devolaflow.nines.advisor:get_research_advice",
        # ---- Compressor module — runtime lean format validators (CO-1) ----
        # Public API exported via module path; consumed by external workflow
        # agents and CI checks (validate dispatch/report compliance).
        "devolaflow.compressor:compress_message",
        "devolaflow.compressor:validate_lean_format",
        # v7.0.0 cache-layout invariant validators — consumed by external
        # workflow agents before sending lean dispatches; mandated by Rule P6
        # in .cursor/rules/devola-flow-rules.mdc and ADR v7-ADR-001.
        "devolaflow.compressor:assert_dispatch_layout",
        "devolaflow.compressor:compute_dispatch_lcp_pct",
        "devolaflow.compressor:DispatchLayoutError",
        # v7.0.1 tool-output truncation primitives — consumed by external
        # runtimes (L3 task agents producing StatusReports, L2 wave agents
        # composing predecessor context) per ADR-002 §2.1. The dataclass +
        # two helpers are opted in via context_profiles.yaml's per-profile
        # `tool_output_truncation:` block (default disabled at v7.0.1 cut).
        "devolaflow.compressor:truncate_tool_output",
        "devolaflow.compressor:clear_old_tool_uses",
        "devolaflow.compressor:ToolUseTruncation",
        # v7.0.2 hierarchical predecessor summariser primitives — consumed by
        # external dispatchers (L0/L1/L2) before composing pred[*].key_facts
        # (per ADR-003 §2.4 trigger threshold). The persistence probe planned
        # in v7.0.3 (ADR-004) re-uses extract_named_entities for entity
        # carry-through scoring.
        "devolaflow.compressor:summarise_predecessor",
        "devolaflow.compressor:extract_named_entities",
        # P-02 v7.2.4 envelope helpers — surface API for v7.3.x dispatcher
        # integration; not yet wired into compress_message but exported for
        # L0 dispatcher consumption per execution-protocol.md §8. The
        # helpers wrap predecessor key_facts and tool outputs in
        # <data channel="..."> ... </data> envelopes so L3 agents can
        # syntactically refuse imperatives that arrive via the data channel
        # (mitigation for arXiv:2604.02837v1 prompt-injection variants).
        "devolaflow.compressor:wrap_data_envelope",
        "devolaflow.compressor:unwrap_data_envelope",
        "devolaflow.compressor:detect_data_channel_instructions",
        # v8.0.0 P-02 directed compaction — Layer-3 of the layered compression
        # pipeline. Public API exported for L0/L1/L2 dispatchers that consume
        # `pred[*].compact_directive` (NESTED schema field added to
        # schemas/lean-dispatch.yaml in v8.0.0 P-02). The dispatcher consumer
        # calls directed_compact(text, focus_keywords, max_drop_pct=0.20)
        # on the predecessor's key_facts block before rendering the lean
        # dispatch payload. Not yet wired into compressor.compress_message
        # at v8.0.0 cut — opt-in via per-pred directive only (see
        # context_profiles.yaml#meta.recency_decay_factor for the
        # complementary Layer-2 overlay default of 0.9).
        "devolaflow.compressor:directed_compact",
        # ---- Self-improving feedback loop (S02-T08 §5) ----
        # Public class hierarchy exposed via devolaflow.feedback.*; documented
        # in SKILL.md (ProposalGenerator.generate_round_dispatch is wired in
        # feedback.py for v6.0.x convergence rounds, but the classes
        # themselves are entry points for external workflow agents).
        "devolaflow.feedback:Proposal",
        "devolaflow.feedback:FeedbackCollector",
        "devolaflow.feedback:FeedbackAnalyzer",
        "devolaflow.feedback:ProposalGenerator",
        # ---- Gate report generators ----
        # Exported via devolaflow.gate.__all__; consumed by external CI tools
        # and validate-gate console_script via direct module access.
        "devolaflow.gate.reporter:generate_yaml_report",
        "devolaflow.gate.reporter:generate_markdown_report",
        # ---- Operational learnings utilities ----
        # Exposed via devolaflow.learnings.*; called by self-update workflow
        # template (workflow-system/agent/templates/builtin/self-update.yaml)
        # and by external workflow agents for learnings management. v7.0.3
        # (ADR-005) adds consolidate_session / decay_confidence /
        # pin_learning_for_session — consumed by L1/L0 session-end hooks and
        # by dispatchers that need cross-round pinning. v7.2.0 (C-007 / CCT-3)
        # adds dedup_learnings — dormant in v7.2.0; promoted to a writer in
        # v7.3 via C-009 (reflective reflex) per the explicit two-phase plan.
        # v7.2.3 (P-03 / C-009) adds capture_session_reflection — the writer
        # that activates the dormant operational.jsonl substrate; called by
        # L1/L0 status-report consumers that persist L3 task-completion
        # reflections (read-side already wired via load_relevant_learnings).
        "devolaflow.learnings:prune_learnings",
        "devolaflow.learnings:promote_learning",
        "devolaflow.learnings:get_learnings_stats",
        "devolaflow.learnings:log_external_source_review",
        "devolaflow.learnings:consolidate_session",
        "devolaflow.learnings:decay_confidence",
        "devolaflow.learnings:pin_learning_for_session",
        "devolaflow.learnings:dedup_learnings",
        "devolaflow.learnings:capture_session_reflection",
        # ---- NineS subsystem — research, analysis, advisor APIs ----
        # All exported via devolaflow.nines.__all__ for external research
        # workflows; the NineS CLI integration is invoked by the user via
        # SI-2 (self-improve-iteration-rules.mdc) and not from in-repo
        # production code.
        "devolaflow.nines.commands:build_command",
        "devolaflow.nines.commands:build_stage_command",
        "devolaflow.nines.detector:ensure_nines",
        "devolaflow.nines.detector:get_nines_capabilities",
        "devolaflow.nines.researcher:NinesResearchConfig",
        "devolaflow.nines.researcher:collect_research",
        "devolaflow.nines.researcher:analyze_target",
        "devolaflow.nines.researcher:run_self_evaluation",
        "devolaflow.nines.researcher:run_skill_iteration",
        "devolaflow.nines.researcher:run_nines_benchmark",
        "devolaflow.nines.researcher:run_nines_update",
        "devolaflow.nines.researcher:run_self_improve_loop",
        "devolaflow.nines.researcher:refresh_reference_dependency",
        "devolaflow.nines.scorer:nines_dimension_scores",
        # ---- Pre-decision phase API ----
        # Exposed via devolaflow.pre_decision.__all__; called by detect-repo-mode
        # console_script and external pre-flight workflow agents.
        "devolaflow.pre_decision.checklist:auto_detect",
        "devolaflow.pre_decision.freeze:freeze_config",
        "devolaflow.pre_decision.recommend:recommend_workflow",
        # ---- Template engine — composer, models, parser, registry ----
        # All exported via devolaflow.template_engine.__all__ for external
        # template authoring tools and the validate-template CLI.
        "devolaflow.template_engine.composer:collect_all_refs",
        "devolaflow.template_engine.models:JoinStrategy",
        "devolaflow.template_engine.models:OnExhaustion",
        "devolaflow.template_engine.models:GateFailAction",
        "devolaflow.template_engine.nines_bridge:nines_commands_to_dispatch_context",
        "devolaflow.template_engine.parser:parse_template_string",
        "devolaflow.template_engine.registry:TemplateRegistry",
        # ---- Runtime stage selector (P-04 in v7.4.9) ----
        # Per the v7.5.0 ghost-audit §3.G G-G1/G-G2/§3.I G-I2 closure design
        # and the P-04 dispatch directive, the runtime layer is intentionally
        # NOT wired into existing dispatch / compose / status flows in this
        # patch — integration with the L0/L1 plan generator is deferred per
        # audit §9 ("scope mode-skip strictly to dispatch composition ...
        # NOT to compressor input shape"). The public entry point is
        # advertised via ``devolaflow.template_engine.__all__`` and consumed
        # by external orchestrators (and ``tests/test_composer_runtime.py``,
        # ``tests/test_template_repo_init.py``) in lieu of an in-repo
        # production call site.
        "devolaflow.template_engine.runtime:select_stages_for_runtime",
        # ---- init_interview module (v7.7 — interview stage for repo-init) ----
        # Public API consumed by L3 task agents during the interview stage
        # of repo-init (mode=full). Not called from in-repo production code.
        "devolaflow.init_interview:detect_project_tools",
        "devolaflow.init_interview:suggest_skills",
        "devolaflow.init_interview:suggest_hooks",
        "devolaflow.init_interview:write_skill",
        "devolaflow.init_interview:generate_claude_hook_config",
        # ---- Learnings + compiler prefs (v7.7 memory system) ----
        "devolaflow.learnings:load_prefs",
        "devolaflow.local.compiler:compile_prefs",
        # ---- Entropy manager GC entrypoint (v8.0.0 P-11) ----
        # Public GC dispatcher exported via ``devolaflow.entropy_manager.__all__``
        # and consumed by L3 Task Agents executing the ``entropy-cleanup``
        # workflow template (``workflow-system/agent/templates/builtin/
        # entropy-cleanup.yaml``). Not yet wired into in-repo production at the
        # v8.0.0 cut — opt-in via the template's ``apply`` stage only. Same
        # allowlist pattern as v8.0.0 P-02 ``directed_compact`` above.
        "devolaflow.entropy_manager:cleanup",
        # ---- Token-budget breaker factory (v8.0.0 P-03) ----
        # Public factory exported via ``devolaflow.gate.__init__`` and
        # ``devolaflow.gate.budget.__all__``. Consumed by L3 Task Agents and
        # CLI tooling that resolves a profile name string into a
        # ``TokenBudgetBreaker`` (mirrors the policy in
        # ``devolaflow.gate.scorer.run_gate_cli``). Direct construction via
        # ``TokenBudgetBreaker(profile=PROFILES[name])`` is the in-repo
        # call-site at the v8.0.0 cut; the factory is the user-facing
        # ergonomic API. Same allowlist pattern as v8.0.0 P-11 above.
        "devolaflow.gate.budget:from_profile_name",
        # ---- Progressive merge (v7.7 — diff-suggest for existing files) ----
        "devolaflow.local.merge:propose_merge",
        "devolaflow.local.merge:apply_merge",
        "devolaflow.local.merge:format_diff_for_review",
        # ---- NineS internal helper exposed in private _cli module ----
        # Public name (no underscore) inside private module; documented in
        # CHANGELOG v5.x as a public helper for callers needing nines.toml
        # auto-discovery before invoking run_nines_cli(config_path=...).
        "devolaflow.nines._cli:find_nines_config",
    }
)


@dataclass(frozen=True)
class PublicSymbol:
    """A public function or class definition discovered at module level."""

    name: str
    kind: str
    module: str
    file: Path
    lineno: int

    @property
    def qualified(self) -> str:
        """Return the ``module:name`` identifier used by the allowlist."""
        return f"{self.module}:{self.name}"

    def to_dict(self, root: Path | None = None) -> dict[str, object]:
        """Return a JSON-serialisable representation."""
        path_str = str(self.file)
        if root is not None:
            try:
                path_str = str(self.file.relative_to(root))
            except ValueError:
                path_str = str(self.file)
        return {
            "name": self.name,
            "kind": self.kind,
            "module": self.module,
            "qualified": self.qualified,
            "file": path_str,
            "lineno": self.lineno,
        }


@dataclass(frozen=True)
class DeadSymbol:
    """A public symbol with zero non-test, non-self callers."""

    symbol: PublicSymbol
    reason: str = "no caller in src/scripts/benchmarks (excluding the defining file)"
    callers: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self, root: Path | None = None) -> dict[str, object]:
        """Return a JSON-serialisable representation."""
        return {
            "symbol": self.symbol.to_dict(root),
            "reason": self.reason,
            "callers": list(self.callers),
        }


def _module_for(file: Path, src_root: Path) -> str:
    """Convert ``src/devolaflow/foo/bar.py`` -> ``devolaflow.foo.bar``."""
    rel = file.resolve().relative_to(src_root.resolve())
    parts = list(rel.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _iter_python_files(root: Path) -> Iterable[Path]:
    """Yield all ``*.py`` files under *root*, skipping caches."""
    for f in sorted(root.rglob("*.py")):
        if any(p == "__pycache__" or p.startswith(".") for p in f.parts):
            continue
        yield f


def _is_cli_entry(name: str) -> bool:
    """Return True when *name* matches a CLI entry-point convention."""
    return name in CLI_ENTRY_NAMES or name.endswith(CLI_ENTRY_SUFFIX)


def collect_public_symbols(src_root: Path) -> list[PublicSymbol]:
    """Return every public top-level ``def``/``class`` under *src_root*.

    *src_root* is the directory whose top-level package directories we want
    to scan (e.g. ``src/`` for the ``devolaflow`` package).
    """
    symbols: list[PublicSymbol] = []
    if not src_root.exists():
        return symbols
    for f in _iter_python_files(src_root):
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except (SyntaxError, ValueError, OSError):
            continue
        try:
            module = _module_for(f, src_root)
        except ValueError:
            continue
        for node in tree.body:
            name = getattr(node, "name", None)
            if not isinstance(name, str):
                continue
            if name.startswith("_") or _is_cli_entry(name):
                continue
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                kind = "function"
            elif isinstance(node, ast.ClassDef):
                kind = "class"
            else:
                continue
            symbols.append(
                PublicSymbol(
                    name=name,
                    kind=kind,
                    module=module,
                    file=f.resolve(),
                    lineno=node.lineno,
                )
            )
    return symbols


def _collect_real_uses(file: Path) -> set[str]:
    """Return all symbol names *file* references outside of import statements.

    A "real use" is any ``ast.Name`` or ``ast.Attribute`` reference that is
    not a child of an ``ast.Import`` or ``ast.ImportFrom`` node. This excludes
    pure re-exports such as ``from .foo import bar`` in ``__init__.py``.
    """
    try:
        tree = ast.parse(file.read_text(encoding="utf-8"))
    except (SyntaxError, ValueError, OSError):
        return set()

    used: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        if isinstance(node, ast.Name):
            used.add(node.id)
        elif isinstance(node, ast.Attribute):
            used.add(node.attr)
    return used


def find_dead_apis(
    src_dirs: Iterable[Path],
    test_dirs: Iterable[Path] = (),
    other_caller_dirs: Iterable[Path] = (),
    allowlist: Iterable[str] = DEFAULT_ALLOWLIST,
) -> list[DeadSymbol]:
    """Return public symbols with zero references in production files.

    "Production files" = ``src_dirs`` plus ``other_caller_dirs`` (typically
    ``scripts/`` and ``benchmarks/``), excluding everything under
    ``test_dirs``. The defining file itself IS scanned; the ``def``/``class``
    statement that creates a symbol does not produce a ``Name`` node, so any
    other reference (instantiation, recursive call, decorator) keeps the
    symbol alive. The dead-wire bug pattern was a function with literally
    zero production references — exactly what this detects.

    Parameters
    ----------
    src_dirs:
        Directories whose ``*.py`` files define the public symbols (e.g.
        ``[Path("src")]``).
    test_dirs:
        Directories that are EXCLUDED from the caller search. Tests do not
        count as production callers — that is the bug class we are catching.
    other_caller_dirs:
        Additional directories to include in the caller search, typically
        ``scripts/`` and ``benchmarks/``.
    allowlist:
        Iterable of ``"module.path:Name"`` strings for symbols that are
        intentionally external-only public API and must never be flagged.
    """
    src_dirs_list = [Path(p) for p in src_dirs]
    test_dirs_list = [Path(p) for p in test_dirs]
    other_caller_list = [Path(p) for p in other_caller_dirs]
    allowed = set(allowlist)

    all_symbols: list[PublicSymbol] = []
    for sd in src_dirs_list:
        all_symbols.extend(collect_public_symbols(sd))

    test_files: set[Path] = set()
    for td in test_dirs_list:
        if td.exists():
            test_files.update(p.resolve() for p in _iter_python_files(td))

    caller_files: list[Path] = []
    for d in src_dirs_list + other_caller_list:
        if not d.exists():
            continue
        caller_files.extend(p.resolve() for p in _iter_python_files(d))
    caller_files = [f for f in caller_files if f not in test_files]

    file_uses: dict[Path, set[str]] = {f: _collect_real_uses(f) for f in caller_files}

    dead: list[DeadSymbol] = []
    for sym in all_symbols:
        if sym.qualified in allowed:
            continue
        has_caller = any(sym.name in names for names in file_uses.values())
        if not has_caller:
            dead.append(DeadSymbol(symbol=sym, callers=()))
    return dead


def _format_text(dead: list[DeadSymbol], root: Path) -> str:
    """Return a human-readable report grouped by file."""
    if not dead:
        return "OK: 0 dead public APIs detected.\n"

    by_file: dict[str, list[DeadSymbol]] = {}
    for d in dead:
        try:
            key = str(d.symbol.file.relative_to(root))
        except ValueError:
            key = str(d.symbol.file)
        by_file.setdefault(key, []).append(d)

    lines: list[str] = [f"FAIL: {len(dead)} dead public API(s) detected.\n"]
    for path in sorted(by_file):
        lines.append(f"\n  {path}")
        for d in by_file[path]:
            lines.append(f"    L{d.symbol.lineno:>4}  {d.symbol.kind:<8} {d.symbol.qualified}")
    lines.append(
        "\nFix options:\n"
        "  1. Wire the symbol into a real production caller.\n"
        "  2. Mark it private (rename with leading underscore).\n"
        "  3. Add it to DEFAULT_ALLOWLIST in scripts/detect_dead_apis.py "
        "with a comment explaining why.\n"
    )
    return "\n".join(lines)


def _format_json(dead: list[DeadSymbol], root: Path) -> str:
    """Return a JSON report suitable for programmatic consumption."""
    return json.dumps(
        {
            "dead_count": len(dead),
            "dead": [d.to_dict(root) for d in dead],
        },
        indent=2,
    )


def _resolve_repo_root(start: Path) -> Path:
    """Walk upward from *start* to find the repo root (contains ``pyproject.toml``)."""
    p = start.resolve()
    while p != p.parent:
        if (p / "pyproject.toml").exists():
            return p
        p = p.parent
    return start.resolve()


def main(argv: list[str] | None = None) -> int:
    """CLI entry — return the process exit code."""
    parser = argparse.ArgumentParser(
        description="Detect public APIs in src/devolaflow with no production callers.",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with code 2 if any dead APIs are found (for CI use).",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Repository root (default: auto-detect via pyproject.toml)",
    )
    args = parser.parse_args(argv)

    root = args.root.resolve() if args.root else _resolve_repo_root(Path(__file__).parent)

    src_dirs = [root / "src"]
    test_dirs = [root / "tests"]
    other_dirs = [root / "scripts", root / "benchmarks"]

    dead = find_dead_apis(
        src_dirs=src_dirs,
        test_dirs=test_dirs,
        other_caller_dirs=other_dirs,
        allowlist=DEFAULT_ALLOWLIST,
    )

    if args.format == "json":
        print(_format_json(dead, root))
    else:
        print(_format_text(dead, root))

    if args.strict and dead:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
