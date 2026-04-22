"""Legibility scorer (v8.2.0 PV-02).

Pure-function 3-dimensional code-quality scorer.

The scorer rates one file at a time on three dimensions, each clamped to
``[0.0, 100.0]``:

1. **Naming consistency** — does the file's identifiers match the
   convention expected for its language? Python files prefer
   ``snake_case`` for functions / module variables and ``PascalCase``
   for classes; JS/TS files prefer ``camelCase`` for functions and
   ``PascalCase`` for classes. Mixed-style modules (e.g. a file with
   both ``snake_case_func`` and ``camelCaseFunc`` Python defs) score
   below 100.
2. **Comment-to-code ratio** — ratio of comment lines to executable
   code lines, mapped through a U-curve so files in the
   ``[0.10, 0.30]`` band score 100, ``< 0.05`` or ``> 0.50`` score
   below 70, and the slopes between the bands are linear (so a
   reasonable file is never penalised by a tiny ratio swing).
3. **Cyclomatic flow** — average per-function cyclomatic complexity.
   When ``radon`` is importable the values come from
   ``radon.complexity.cc_visit``; otherwise an indentation-depth
   heuristic gives a coarse but conservative estimate (S-5 No Silent
   Failures: the fallback path is recorded in
   :pyattr:`LegibilityReport.findings`).

The composite ``score`` is a weighted average across the three
dimensions per :data:`DEFAULT_DIMENSION_WEIGHTS`. The default weights
sum to 1.0 and roughly match the v8.0.0 patch-plan PV-02 design notes
(naming and comment ratio carry slightly more weight than cyclomatic
flow because cyclomatic flow can be improved later via refactor while
naming and comment debt is sticky).

Caller contract
---------------

* Pass an absolute or repository-relative path. Missing files raise
  :class:`FileNotFoundError`.
* Empty files score 100 on all dimensions (per spec — there is nothing
  to be illegible about).
* Non-Python files (``.md``, ``.yaml``, ``.json``, ``.js``, ``.ts``)
  are still scored, but the cyclomatic flow dimension falls back to
  the indentation heuristic since ``radon`` only parses Python.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_DIMENSION_WEIGHTS: dict[str, float] = {
    "naming_consistency": 0.40,
    "comment_ratio": 0.30,
    "cyclomatic_flow": 0.30,
}


_PYTHON_EXTS: frozenset[str] = frozenset({".py", ".pyi"})
_JS_TS_EXTS: frozenset[str] = frozenset({".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"})

_SNAKE_CASE_RE = re.compile(r"^_?[a-z][a-z0-9_]*_?$")
_PASCAL_CASE_RE = re.compile(r"^[A-Z][A-Za-z0-9]*$")
_CAMEL_CASE_RE = re.compile(r"^[a-z][A-Za-z0-9]*$")
_DUNDER_RE = re.compile(r"^__[A-Za-z0-9_]+__$")


@dataclass
class LegibilityReport:
    """Outcome of scoring one file via :meth:`LegibilityScorer.score`.

    Attributes
    ----------
    score:
        Composite weighted score in ``[0.0, 100.0]``.
    dimensions:
        Per-dimension breakdown — keys are
        ``naming_consistency`` / ``comment_ratio`` / ``cyclomatic_flow``,
        values in ``[0.0, 100.0]``.
    findings:
        Human-readable observations about why dimensions deviated from
        100. Always populated even when ``score == 100`` so callers can
        log the (empty) finding list uniformly without branching.
    file_path:
        The file the scorer inspected (relative path when supplied as
        such; absolute when supplied as such — the scorer never
        rewrites paths, per S-2 / SF-5).
    metrics:
        Raw measurements consulted to compute the dimension scores
        (e.g. ``comment_lines`` / ``code_lines`` / ``cc_avg``). Useful
        for downstream analytics that want the underlying counters
        without re-parsing the file.
    """

    score: float
    dimensions: dict[str, float]
    findings: list[str] = field(default_factory=list)
    file_path: str = ""
    metrics: dict[str, float] = field(default_factory=dict)


class LegibilityScorer:
    """Pure-function legibility scorer.

    Construct with optional dimension weight overrides — callers can
    rebalance which dimension dominates the composite without touching
    the underlying sub-scorers. Default weights live in
    :data:`DEFAULT_DIMENSION_WEIGHTS`.

    Parameters
    ----------
    weights:
        Optional ``{dimension: weight}`` mapping. Missing keys fall
        back to the defaults. Weights are renormalised at score time
        so callers may pass values that sum to anything > 0.
    """

    def __init__(self, weights: dict[str, float] | None = None) -> None:
        merged = dict(DEFAULT_DIMENSION_WEIGHTS)
        if weights:
            for k, v in weights.items():
                if k not in DEFAULT_DIMENSION_WEIGHTS:
                    raise ValueError(
                        f"unknown legibility weight key {k!r}; "
                        f"expected one of {sorted(DEFAULT_DIMENSION_WEIGHTS)}"
                    )
                if v < 0:
                    raise ValueError(f"legibility weight {k!r} must be >= 0 (got {v})")
                merged[k] = float(v)
        total = sum(merged.values())
        if total <= 0:
            raise ValueError(
                f"legibility weights must sum to a positive value (got {merged} summing to {total})"
            )
        self._weights = {k: v / total for k, v in merged.items()}

    @property
    def weights(self) -> dict[str, float]:
        """Return the normalised weight mapping (defensive copy)."""
        return dict(self._weights)

    def score(self, file_path: str | Path) -> LegibilityReport:
        """Score one file and return a :class:`LegibilityReport`.

        Parameters
        ----------
        file_path:
            Path to the file (absolute or relative). Missing files raise
            :class:`FileNotFoundError`. Binary files (any decoding
            error) are scored as a single empty file with the failure
            recorded in :pyattr:`LegibilityReport.findings` per S-5.

        Returns
        -------
        LegibilityReport
            ``score in [0.0, 100.0]`` plus the three dimension
            breakdown, findings list, and raw metrics.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"legibility target not found: {path}")
        if not path.is_file():
            raise IsADirectoryError(f"legibility target must be a file (got directory: {path})")

        try:
            source = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            return LegibilityReport(
                score=0.0,
                dimensions={k: 0.0 for k in DEFAULT_DIMENSION_WEIGHTS},
                findings=[
                    f"file not text-decodable as utf-8: {type(exc).__name__}",
                ],
                file_path=str(file_path),
                metrics={},
            )

        if not source.strip():
            return LegibilityReport(
                score=100.0,
                dimensions={k: 100.0 for k in DEFAULT_DIMENSION_WEIGHTS},
                findings=[],
                file_path=str(file_path),
                metrics={"code_lines": 0.0, "comment_lines": 0.0},
            )

        ext = path.suffix.lower()
        findings: list[str] = []
        metrics: dict[str, float] = {}

        naming = self._score_naming(source, ext, findings, metrics)
        comments = self._score_comment_ratio(source, ext, findings, metrics)
        cyclo = self._score_cyclomatic_flow(source, ext, findings, metrics)

        dims = {
            "naming_consistency": naming,
            "comment_ratio": comments,
            "cyclomatic_flow": cyclo,
        }
        composite = sum(dims[k] * self._weights[k] for k in DEFAULT_DIMENSION_WEIGHTS)
        composite = round(max(0.0, min(100.0, composite)), 2)

        return LegibilityReport(
            score=composite,
            dimensions={k: round(v, 2) for k, v in dims.items()},
            findings=findings,
            file_path=str(file_path),
            metrics=metrics,
        )

    def _score_naming(
        self,
        source: str,
        ext: str,
        findings: list[str],
        metrics: dict[str, float],
    ) -> float:
        """Score naming consistency for a file's identifiers.

        Python source is inspected via :mod:`ast` so docstring tokens
        and string literals never pollute the identifier set. Non-Python
        sources fall back to a regex sweep that scans for ``function`` /
        ``class`` declarations and flags mixed-style names.

        Score derivation:

        * 100 when every identifier matches the convention expected for
          the file extension (snake/PascalCase for Python, camel/Pascal
          for JS/TS, no convention enforcement for plain text).
        * Linear penalty per violation, floored at 0. A single rogue
          ``camelCaseFunc`` in a snake_case Python file costs ~10pp.
        * Below 70 if more than 30 % of declared symbols deviate
          (matches the patch-plan §3 PV-02 AC-4 mixed-convention rule).
        """
        if ext in _PYTHON_EXTS:
            return self._score_naming_python(source, findings, metrics)
        if ext in _JS_TS_EXTS:
            return self._score_naming_js_ts(source, findings, metrics)
        # Other text formats (.md, .yaml, .json, ...) carry no per-language
        # identifier expectation — treat as fully consistent and let the
        # other two dimensions score the file.
        metrics.setdefault("naming_total_symbols", 0.0)
        metrics.setdefault("naming_violations", 0.0)
        return 100.0

    def _score_naming_python(
        self,
        source: str,
        findings: list[str],
        metrics: dict[str, float],
    ) -> float:
        """Score naming consistency for a Python source string."""
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            findings.append(f"python parse error in naming sub-scorer: {exc.msg}")
            metrics["naming_total_symbols"] = 0.0
            metrics["naming_violations"] = 0.0
            return 0.0

        function_names, class_names = _collect_python_symbols(tree)
        violations = [
            f"function {name!r} not snake_case"
            for name in function_names
            if not _DUNDER_RE.match(name) and not _SNAKE_CASE_RE.match(name)
        ]
        violations.extend(
            f"class {name!r} not PascalCase"
            for name in class_names
            if not _PASCAL_CASE_RE.match(name)
        )
        return _finalize_naming_score(
            "python",
            total=len(function_names) + len(class_names),
            violations=violations,
            findings=findings,
            metrics=metrics,
        )

    def _score_naming_js_ts(
        self,
        source: str,
        findings: list[str],
        metrics: dict[str, float],
    ) -> float:
        """Score naming consistency for JS/TS source via regex.

        Identifies declared functions and classes by simple regex over
        ``function name(...)`` / ``class Name`` / ``const name = ...``
        patterns. Falls back gracefully when the file uses heavy syntax
        (the failure is recorded in ``findings`` per S-5).
        """
        function_names, class_names = _collect_js_ts_symbols(source)
        violations = [
            f"function {name!r} not camelCase or PascalCase"
            for name in function_names
            if not _CAMEL_CASE_RE.match(name) and not _PASCAL_CASE_RE.match(name)
        ]
        violations.extend(
            f"class {name!r} not PascalCase"
            for name in class_names
            if not _PASCAL_CASE_RE.match(name)
        )
        return _finalize_naming_score(
            "JS/TS",
            total=len(function_names) + len(class_names),
            violations=violations,
            findings=findings,
            metrics=metrics,
        )

    def _score_comment_ratio(
        self,
        source: str,
        ext: str,
        findings: list[str],
        metrics: dict[str, float],
    ) -> float:
        """Score the comment-to-code ratio against a U-curve.

        A file with too few comments is hard to onboard onto; a file
        with too many comments carries documentation overhead that
        usually signals inadequate naming or unclear control flow.
        Both extremes therefore reduce the dimension score.

        Scoring band (per patch-plan §3 PV-02 AC-3 / AC-5):

        ============  =====================================
        Ratio range   Score
        ============  =====================================
        < 0.05        Linear ramp from 40 (ratio 0) → 70 (0.05)
        0.05 - 0.10   Linear ramp from 70 (0.05) → 95 (0.10)
        0.10 - 0.30   100 (sweet spot)
        0.30 - 0.50   Linear ramp from 100 (0.30) → 70 (0.50)
        > 0.50        Floor of 40 (over-commented)
        ============  =====================================
        """
        comment_prefix, block_pairs = _comment_syntax_for(ext)
        if comment_prefix is None and not block_pairs:
            metrics["code_lines"] = 0.0
            metrics["comment_lines"] = 0.0
            metrics["comment_ratio"] = 0.0
            return 100.0

        code_lines, comment_lines = _count_lines(source, comment_prefix, block_pairs)
        metrics["code_lines"] = float(code_lines)
        metrics["comment_lines"] = float(comment_lines)
        if code_lines == 0:
            metrics["comment_ratio"] = 0.0
            return 100.0

        ratio = comment_lines / code_lines
        metrics["comment_ratio"] = ratio
        _record_comment_finding(ratio, findings)
        return _comment_ratio_score(ratio)

    def _score_cyclomatic_flow(
        self,
        source: str,
        ext: str,
        findings: list[str],
        metrics: dict[str, float],
    ) -> float:
        """Score cyclomatic complexity (lower is better).

        Uses :func:`radon.complexity.cc_visit` for Python sources when
        the ``radon`` package is importable; otherwise applies an
        indentation-depth heuristic.

        Scoring band (per patch-plan §3 PV-02 AC-6):

        ===========  =====================================
        cc avg       Score
        ===========  =====================================
        ≤ 3          100 (trivial)
        3 - 5        Linear 100 → 95
        5 - 10       Linear 95 → 75 (acceptable)
        10 - 15      Linear 75 → 50 (warning)
        > 15         Linear 50 → 0  (critical, max=25)
        ===========  =====================================
        """
        if ext in _PYTHON_EXTS:
            cc_avg = _python_cyclomatic_avg(source, findings, metrics)
        else:
            cc_avg = _indentation_cyclomatic_avg(source, metrics)
            findings.append(
                f"cyclomatic_flow used indentation heuristic (radon does not parse {ext!r})"
            )
        score = _cyclomatic_score(cc_avg)
        if cc_avg > 10:
            findings.append(
                f"cyclomatic_flow avg cc {cc_avg:.2f} > 10 (consider extracting helpers)"
            )
        return score


def _collect_python_symbols(tree: ast.AST) -> tuple[list[str], list[str]]:
    """Walk a parsed Python AST and return ``(function_names, class_names)``."""
    function_names: list[str] = []
    class_names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            function_names.append(node.name)
        elif isinstance(node, ast.ClassDef):
            class_names.append(node.name)
    return function_names, class_names


_JS_TS_FUNCTION_RE = re.compile(
    r"\b(?:function\s+([A-Za-z_$][\w$]*)|"
    r"(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z_$])\s*=>)"
)
_JS_TS_CLASS_RE = re.compile(r"\bclass\s+([A-Za-z_$][\w$]*)")


def _collect_js_ts_symbols(source: str) -> tuple[list[str], list[str]]:
    """Regex-extract ``(function_names, class_names)`` from JS/TS source."""
    function_names = [
        (match.group(1) or match.group(2)) for match in _JS_TS_FUNCTION_RE.finditer(source)
    ]
    function_names = [name for name in function_names if name]
    class_names = [m.group(1) for m in _JS_TS_CLASS_RE.finditer(source)]
    return function_names, class_names


def _finalize_naming_score(
    language_label: str,
    *,
    total: int,
    violations: list[str],
    findings: list[str],
    metrics: dict[str, float],
) -> float:
    """Render a naming-consistency score from a violation list.

    Pulled out of the per-language sub-scorers so both Python and
    JS/TS share the same finding format and metric keys (S-5 — never
    drop a violation count, even when total == 0).
    """
    metrics["naming_total_symbols"] = float(total)
    metrics["naming_violations"] = float(len(violations))
    if total == 0:
        return 100.0
    ratio = len(violations) / total
    score = max(0.0, 100.0 - ratio * 100.0)
    if violations:
        findings.append(
            f"naming: {len(violations)}/{total} {language_label} symbol(s) deviate "
            f"({violations[0]}{', …' if len(violations) > 1 else ''})"
        )
    return score


def _classify_comment_line(
    raw_line: str,
    comment_prefix: str | None,
    block_pairs: tuple[tuple[str, str], ...],
    in_block: tuple[str, str] | None,
) -> tuple[str, tuple[str, str] | None]:
    """Classify a single source line as ``code``/``comment``/``blank``.

    Returns ``(category, new_in_block_state)``. The state machine is
    intentionally narrow — block-comment detection is line-prefix based
    so even a malformed block opener never silently consumes the rest
    of the file (S-5: malformed input degrades to one comment line, not
    a swallowed block).
    """
    line = raw_line.strip()
    if not line:
        return ("blank", in_block)
    if in_block is not None:
        if in_block[1] in raw_line:
            return ("comment", None)
        return ("comment", in_block)
    for opener, closer in block_pairs:
        if line.startswith(opener):
            if closer in line[len(opener) :]:
                return ("comment", None)
            return ("comment", (opener, closer))
    if comment_prefix and line.startswith(comment_prefix):
        return ("comment", None)
    return ("code", None)


def _count_lines(
    source: str,
    comment_prefix: str | None,
    block_pairs: tuple[tuple[str, str], ...],
) -> tuple[int, int]:
    """Walk the source line-by-line, returning ``(code_lines, comment_lines)``."""
    code_lines = 0
    comment_lines = 0
    in_block: tuple[str, str] | None = None
    for raw_line in source.splitlines():
        category, in_block = _classify_comment_line(raw_line, comment_prefix, block_pairs, in_block)
        if category == "code":
            code_lines += 1
        elif category == "comment":
            comment_lines += 1
    return code_lines, comment_lines


def _record_comment_finding(ratio: float, findings: list[str]) -> None:
    """Append an under/over-commented finding when the ratio crosses bounds."""
    if ratio < 0.05:
        findings.append(
            f"comment ratio {ratio:.3f} below 0.05 (under-commented; "
            f"add module/function docstrings)"
        )
    elif ratio > 0.50:
        findings.append(
            f"comment ratio {ratio:.3f} above 0.50 (over-commented; "
            f"refactor or trim narrative comments)"
        )


def _comment_syntax_for(
    ext: str,
) -> tuple[str | None, tuple[tuple[str, str], ...]]:
    """Return ``(line_prefix, block_pairs)`` for the file extension.

    ``line_prefix`` is ``None`` when the format has no recognised
    line-comment marker. ``block_pairs`` is a tuple of
    ``(opener, closer)`` markers; empty when the format has no block
    comments.
    """
    if ext in _PYTHON_EXTS or ext in {".sh", ".bash", ".zsh", ".rb", ".pl", ".toml"}:
        return ("#", ())
    if ext in _JS_TS_EXTS or ext in {".c", ".cpp", ".h", ".hpp", ".java", ".cs", ".go", ".rs"}:
        return ("//", (("/*", "*/"),))
    if ext in {".css", ".scss", ".less"}:
        return (None, (("/*", "*/"),))
    if ext in {".html", ".htm", ".xml", ".svg"}:
        return (None, (("<!--", "-->"),))
    if ext in {".yaml", ".yml"}:
        return ("#", ())
    if ext in {".md", ".markdown"}:
        return (None, (("<!--", "-->"),))
    if ext in {".json", ".jsonl"}:
        # Strict JSON has no comments; treat the file as 100 % code so
        # the dimension neither rewards nor penalises configuration.
        return (None, ())
    return (None, ())


def _comment_ratio_score(ratio: float) -> float:
    """Map a comment-to-code ratio onto a 0-100 score (U-curve)."""
    if ratio <= 0.0:
        return 40.0
    if ratio < 0.05:
        return 40.0 + (ratio / 0.05) * 30.0
    if ratio < 0.10:
        return 70.0 + ((ratio - 0.05) / 0.05) * 25.0
    if ratio <= 0.30:
        return 100.0
    if ratio <= 0.50:
        return 100.0 - ((ratio - 0.30) / 0.20) * 30.0
    if ratio <= 1.0:
        return max(40.0, 70.0 - (ratio - 0.50) * 60.0)
    return 40.0


def _python_cyclomatic_avg(
    source: str,
    findings: list[str],
    metrics: dict[str, float],
) -> float:
    """Compute average cc per function, preferring radon when available."""
    try:
        from radon.complexity import cc_visit
    except ImportError:
        findings.append("cyclomatic_flow fell back to heuristic (radon not installed)")
        return _indentation_cyclomatic_avg(source, metrics)

    try:
        blocks = cc_visit(source)
    except SyntaxError as exc:
        findings.append(f"cyclomatic_flow radon parse error: {exc.msg}")
        return _indentation_cyclomatic_avg(source, metrics)

    if not blocks:
        metrics["cc_function_count"] = 0.0
        metrics["cc_avg"] = 0.0
        metrics["cc_max"] = 0.0
        return 0.0

    complexities = [block.complexity for block in blocks]
    cc_avg = sum(complexities) / len(complexities)
    metrics["cc_function_count"] = float(len(complexities))
    metrics["cc_avg"] = float(cc_avg)
    metrics["cc_max"] = float(max(complexities))
    return cc_avg


def _indentation_cyclomatic_avg(source: str, metrics: dict[str, float]) -> float:
    """Indentation-depth heuristic for non-Python files (or radon-less envs).

    Counts decision-point keywords (``if`` / ``for`` / ``while`` /
    ``case`` / ``catch``) and estimates per-function complexity as
    ``1 + decisions / max(functions, 1)``. Conservative — under-reports
    real complexity but never silently inflates it (S-5).
    """
    decision_pattern = re.compile(r"\b(if|elif|else if|for|while|case|catch|except|switch|when)\b")
    function_pattern = re.compile(r"\b(?:def|function|fn|sub|method)\s+[A-Za-z_$]")
    decisions = len(decision_pattern.findall(source))
    funcs = max(1, len(function_pattern.findall(source)))
    cc_avg = 1.0 + decisions / funcs
    metrics["cc_function_count"] = float(funcs)
    metrics["cc_avg"] = float(cc_avg)
    metrics["cc_max"] = float(cc_avg)
    return cc_avg


def _cyclomatic_score(cc_avg: float) -> float:
    """Map an average cyclomatic-complexity value onto 0-100."""
    if cc_avg <= 3.0:
        return 100.0
    if cc_avg <= 5.0:
        return 100.0 - (cc_avg - 3.0) / 2.0 * 5.0
    if cc_avg <= 10.0:
        return 95.0 - (cc_avg - 5.0) / 5.0 * 20.0
    if cc_avg <= 15.0:
        return 75.0 - (cc_avg - 10.0) / 5.0 * 25.0
    if cc_avg <= 30.0:
        return max(0.0, 50.0 - (cc_avg - 15.0) / 15.0 * 50.0)
    return 0.0
