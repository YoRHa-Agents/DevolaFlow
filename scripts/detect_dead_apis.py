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
        # and by external workflow agents for learnings management.
        "devolaflow.learnings:prune_learnings",
        "devolaflow.learnings:promote_learning",
        "devolaflow.learnings:get_learnings_stats",
        "devolaflow.learnings:log_external_source_review",
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
