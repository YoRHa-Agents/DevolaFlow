#!/usr/bin/env python3
"""Enforce code-line and comment-density budgets for Python source modules."""

from __future__ import annotations

import argparse
import ast
import io
import subprocess
import sys
import tokenize
from dataclasses import dataclass
from pathlib import Path

COMMENT_RATIO_LIMIT = 0.50
_IGNORED_TOKEN_TYPES = frozenset(
    {
        tokenize.COMMENT,
        tokenize.ENCODING,
        tokenize.ENDMARKER,
        tokenize.INDENT,
        tokenize.DEDENT,
        tokenize.NEWLINE,
        tokenize.NL,
    }
)


@dataclass(frozen=True)
class ModuleMetrics:
    """Deterministic physical-line metrics for one Python source module.

    ``code_lines`` counts nonblank physical lines touched by a non-comment
    token, except tokens belonging to a real module/class/function docstring.
    Runtime multiline strings are therefore code; only strings in the
    positions Python recognises as docstrings are excluded. The comment and
    docstring counters also count only nonblank physical lines, so blank
    lines inside a multiline docstring do not inflate the ratio.
    """

    code_lines: int
    comment_lines: int
    docstring_lines: int
    nonblank_lines: int

    @property
    def comment_ratio(self) -> float:
        """Return comment/docstring lines divided by nonblank lines."""
        if self.nonblank_lines == 0:
            return 0.0
        return (self.comment_lines + self.docstring_lines) / self.nonblank_lines


def _line_span(start: tuple[int, int], end: tuple[int, int]) -> set[int]:
    """Return the 1-based physical lines covered by a token or AST node."""
    return set(range(start[0], end[0] + 1))


def _docstring_spans(tree: ast.AST) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    """Find exact source spans of module, class, and function docstrings."""
    spans: list[tuple[tuple[int, int], tuple[int, int]]] = []
    for node in ast.walk(tree):
        if not isinstance(
            node,
            (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef),
        ):
            continue
        body = node.body
        if not body or not isinstance(body[0], ast.Expr):
            continue
        value = body[0].value
        if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
            continue
        if not hasattr(body[0], "end_lineno") or not hasattr(body[0], "end_col_offset"):
            continue
        spans.append(
            (
                (body[0].lineno, body[0].col_offset),
                (body[0].end_lineno, body[0].end_col_offset),
            )
        )
    return spans


def _token_is_in_docstring(
    token: tokenize.TokenInfo,
    docstring_spans: list[tuple[tuple[int, int], tuple[int, int]]],
) -> bool:
    """Return whether a string token is inside a recognised docstring span."""
    if token.type != tokenize.STRING:
        return False
    token_start = token.start
    token_end = token.end
    for span_start, span_end in docstring_spans:
        if span_start <= token_start and token_end <= span_end:
            return True
    return False


def measure_source(source: str) -> ModuleMetrics:
    """Measure Python source using AST docstring positions and ``tokenize``.

    AST parsing is used only to identify docstring positions precisely:
    arbitrary runtime strings, including multiline strings, are never
    treated as documentation. Token line spans and comment handling come
    exclusively from the stdlib tokenizer. Syntax and tokenization failures
    are surfaced as ``ValueError`` with a stable prefix.
    """
    physical_lines = source.splitlines()
    nonblank_lines = {number for number, line in enumerate(physical_lines, start=1) if line.strip()}
    try:
        tree = ast.parse(source)
        docstring_spans = _docstring_spans(tree)
        tokens = tokenize.generate_tokens(io.StringIO(source).readline)
        code_lines: set[int] = set()
        comment_lines: set[int] = set()
        for token in tokens:
            if token.type == tokenize.COMMENT:
                if physical_lines and physical_lines[token.start[0] - 1].lstrip().startswith("#"):
                    comment_lines.add(token.start[0])
                continue
            if token.type in _IGNORED_TOKEN_TYPES or _token_is_in_docstring(token, docstring_spans):
                continue
            code_lines.update(_line_span(token.start, token.end) & nonblank_lines)
    except (IndentationError, SyntaxError, tokenize.TokenError) as exc:
        raise ValueError(f"unable to measure Python source: {exc}") from exc

    docstring_lines: set[int] = set()
    for start, end in docstring_spans:
        docstring_lines.update(_line_span(start, end) & nonblank_lines)
    return ModuleMetrics(
        code_lines=len(code_lines),
        comment_lines=len(comment_lines),
        docstring_lines=len(docstring_lines),
        nonblank_lines=len(nonblank_lines),
    )


def measure_module(path: Path) -> ModuleMetrics:
    """Measure a Python file, preserving its declared source encoding."""
    try:
        with tokenize.open(str(path)) as source_file:
            return measure_source(source_file.read())
    except (OSError, SyntaxError, UnicodeError, tokenize.TokenError) as exc:
        raise ValueError(f"unable to read or measure {path}: {exc}") from exc


def check_comment_ratios(
    metrics: dict[str, ModuleMetrics], limit: float = COMMENT_RATIO_LIMIT
) -> list[str]:
    """Return stable diagnostics for changed modules over the ratio limit."""
    violations = []
    for path, module_metrics in sorted(metrics.items()):
        if module_metrics.comment_ratio > limit:
            violations.append(
                f"{path}: comment/docstring ratio "
                f"{module_metrics.comment_ratio:.1%} exceeds {limit:.0%} "
                f"({module_metrics.comment_lines + module_metrics.docstring_lines} "
                f"comment/docstring lines / {module_metrics.nonblank_lines} "
                "nonblank physical lines)"
            )
    return violations


def check_line_counts(
    current: dict[str, int], baseline: dict[str, int], maximum: int = 800
) -> list[str]:
    """Return new-module and grandfather-ratchet violations."""
    violations = []
    for path, lines in sorted(current.items()):
        if path not in baseline and lines > maximum:
            violations.append(f"{path}: new module has {lines} code lines (limit {maximum})")
        elif path in baseline and baseline[path] > maximum and lines > baseline[path]:
            violations.append(f"{path}: grew from {baseline[path]} to {lines} code lines")
    return violations


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)
    return result.stdout


def _changed_modules(root: Path, baseline_ref: str) -> list[Path]:
    changed = set(
        _git(root, "diff", "--name-only", baseline_ref, "--", "src/devolaflow").splitlines()
    )
    changed.update(
        _git(
            root, "ls-files", "--others", "--exclude-standard", "--", "src/devolaflow"
        ).splitlines()
    )
    return [
        root / path for path in sorted(changed) if path.endswith(".py") and (root / path).is_file()
    ]


def main(argv: list[str] | None = None) -> int:
    """Check changed source modules against the baseline."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-ref", default="origin/main")
    parser.add_argument("--maximum", type=int, default=800)
    args = parser.parse_args(argv)
    root = Path.cwd()

    try:
        modules = _changed_modules(root, args.baseline_ref)
        current_metrics = {str(path.relative_to(root)): measure_module(path) for path in modules}
        current = {path: metrics.code_lines for path, metrics in current_metrics.items()}
        baseline = {}
        for path in current:
            try:
                baseline_text = _git(root, "show", f"{args.baseline_ref}:{path}")
                baseline[path] = measure_source(baseline_text).code_lines
            except subprocess.CalledProcessError:
                continue
    except (OSError, subprocess.CalledProcessError, ValueError) as exc:
        print(f"ERROR: module-size baseline check failed: {exc}", file=sys.stderr)
        return 1

    violations = check_line_counts(current, baseline, args.maximum)
    violations.extend(check_comment_ratios(current_metrics))
    if violations:
        print("FAIL: module-size gate")
        print("\n".join(f"  {violation}" for violation in violations))
        return 1
    print(f"PASS: module-size gate ({len(modules)} changed source module(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
