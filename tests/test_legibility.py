"""Comprehensive tests for v8.2.0 PV-02 — Agent Legibility Scoring.

Covers (per ``.local/research/v8.2.0_patch_plan.md`` §3 PV-02):

- 3 sub-scorer unit tests for naming consistency (snake_case violations,
  PascalCase classes, mixed-style modules, JS/TS camelCase, dunder
  exemption).
- 3 sub-scorer unit tests for comment-to-code ratio (low / sweet-spot /
  high, U-curve mid-band sweet-spot, score-range bounds).
- 3 sub-scorer unit tests for cyclomatic flow (simple / complex /
  fallback heuristic, radon integration, indentation fallback).
- ``LegibilityScorer.score()`` contract tests — 0-100 score, three
  dimensions populated, findings list populated.
- Gate integration tests — ``legibility_scorer=None`` byte-identical to
  v8.1.0-rc.1, STRICT profile +0.05 weight uplift, composite delta.
- Profile defaults — STRICT/AUDIT default 0.05; STANDARD/RELAXED 0.0.
- Edge cases — empty file, missing file, binary file, syntax-error
  file, custom weights, zero-weight kwargs.

Target: ≥ 25 tests + ≥ 90 % line coverage on
``src/devolaflow/legibility/scorer.py`` (per CP-2 / SI-3 v8.x ≥ 90 %
convention).
"""

from __future__ import annotations

import textwrap
from dataclasses import replace
from pathlib import Path

import pytest

from devolaflow.gate.models import CheckResult, ConvergenceRound, GateInput
from devolaflow.gate.profiles import AUDIT, RELAXED, STANDARD, STRICT
from devolaflow.gate.scorer import (
    _aggregate_legibility_reports,
    _attach_legibility_evaluation,
    composite_score,
    evaluate_gate,
)
from devolaflow.legibility import (
    DEFAULT_DIMENSION_WEIGHTS,
    LegibilityReport,
    LegibilityScorer,
)
from devolaflow.legibility.scorer import (
    _classify_comment_line,
    _comment_ratio_score,
    _comment_syntax_for,
    _cyclomatic_score,
    _indentation_cyclomatic_avg,
)

# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def scorer() -> LegibilityScorer:
    """Default scorer with the canonical dimension weights."""
    return LegibilityScorer()


@pytest.fixture
def write_file(tmp_path: Path):
    """Write a transient source file and return its path."""

    def _write(name: str, body: str) -> Path:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(body), encoding="utf-8")
        return path

    return _write


def _pass_gate_input() -> GateInput:
    """Produce an all-PASS :class:`GateInput`."""
    return GateInput(
        build_status=CheckResult(status="pass"),
        test_results=CheckResult(
            status="pass",
            details={"coverage_pct": 90.0, "tests_total": 10, "tests_passed": 10},
        ),
        lint_status=CheckResult(status="pass", details={"architecture_score": 90.0}),
        review_findings=[],
        acceptance_criteria_results=CheckResult(status="pass"),
    )


def _round(num: int, score: float = 90.0) -> ConvergenceRound:
    """Build a :class:`ConvergenceRound` so ``evaluate_gate`` enters the
    convergence branch and produces a non-None ``composite_score``."""
    return ConvergenceRound(
        round_num=num,
        composite_score=score,
        blocker_count=0,
        critical_count=0,
        timestamp="2026-04-22T00:00:00Z",
    )


# ---------------------------------------------------------------------------
# 1. LegibilityScorer construction / weight handling
# ---------------------------------------------------------------------------


class TestLegibilityScorerConstruction:
    def test_default_weights_sum_to_one(self) -> None:
        s = LegibilityScorer()
        assert pytest.approx(sum(s.weights.values()), abs=1e-9) == 1.0

    def test_default_weights_match_module_constant(self) -> None:
        s = LegibilityScorer()
        for k, v in DEFAULT_DIMENSION_WEIGHTS.items():
            assert s.weights[k] == pytest.approx(v)

    def test_custom_weights_renormalised(self) -> None:
        s = LegibilityScorer(
            weights={
                "naming_consistency": 2.0,
                "comment_ratio": 1.0,
                "cyclomatic_flow": 1.0,
            }
        )
        total = sum(s.weights.values())
        assert pytest.approx(total, abs=1e-9) == 1.0
        assert s.weights["naming_consistency"] == pytest.approx(0.5)

    def test_unknown_weight_key_raises(self) -> None:
        with pytest.raises(ValueError, match="unknown legibility weight key"):
            LegibilityScorer(weights={"not_a_dim": 0.5})

    def test_negative_weight_raises(self) -> None:
        with pytest.raises(ValueError, match="must be >= 0"):
            LegibilityScorer(weights={"naming_consistency": -0.1})

    def test_zero_total_weight_raises(self) -> None:
        with pytest.raises(ValueError, match="must sum to a positive value"):
            LegibilityScorer(
                weights={
                    "naming_consistency": 0.0,
                    "comment_ratio": 0.0,
                    "cyclomatic_flow": 0.0,
                }
            )


# ---------------------------------------------------------------------------
# 2. score() contract — file path handling
# ---------------------------------------------------------------------------


class TestLegibilityScorerContract:
    def test_score_returns_legibility_report(self, scorer: LegibilityScorer, write_file) -> None:
        path = write_file(
            "snake.py",
            """
            def my_function():
                return 1
            """,
        )
        report = scorer.score(path)
        assert isinstance(report, LegibilityReport)

    def test_score_in_0_100_range(self, scorer: LegibilityScorer, write_file) -> None:
        path = write_file(
            "snake.py",
            """
            def my_function():
                return 1
            """,
        )
        report = scorer.score(path)
        assert 0.0 <= report.score <= 100.0

    def test_score_three_dimensions_populated(self, scorer: LegibilityScorer, write_file) -> None:
        path = write_file(
            "snake.py",
            """
            def my_function():
                return 1
            """,
        )
        report = scorer.score(path)
        assert set(report.dimensions) == {
            "naming_consistency",
            "comment_ratio",
            "cyclomatic_flow",
        }
        for v in report.dimensions.values():
            assert 0.0 <= v <= 100.0

    def test_score_findings_is_list(self, scorer: LegibilityScorer, write_file) -> None:
        path = write_file(
            "snake.py",
            """
            def my_function():
                return 1
            """,
        )
        report = scorer.score(path)
        assert isinstance(report.findings, list)

    def test_score_missing_file_raises(self, scorer: LegibilityScorer) -> None:
        with pytest.raises(FileNotFoundError):
            scorer.score("does/not/exist/anywhere.py")

    def test_score_directory_raises(self, scorer: LegibilityScorer, tmp_path: Path) -> None:
        with pytest.raises(IsADirectoryError):
            scorer.score(tmp_path)

    def test_score_empty_file_returns_perfect(self, scorer: LegibilityScorer, write_file) -> None:
        path = write_file("empty.py", "")
        report = scorer.score(path)
        assert report.score == 100.0
        for v in report.dimensions.values():
            assert v == 100.0

    def test_score_whitespace_only_file_returns_perfect(
        self, scorer: LegibilityScorer, write_file
    ) -> None:
        path = write_file("blank.py", "   \n\n  \n")
        report = scorer.score(path)
        assert report.score == 100.0

    def test_score_binary_decode_failure_logs_finding(
        self, scorer: LegibilityScorer, tmp_path: Path
    ) -> None:
        path = tmp_path / "binary.py"
        path.write_bytes(b"\xff\xfe\x00\x01undecodable")
        report = scorer.score(path)
        assert report.score == 0.0
        assert any("not text-decodable" in f for f in report.findings)


# ---------------------------------------------------------------------------
# 3. Naming consistency — Python sub-scorer
# ---------------------------------------------------------------------------


class TestNamingConsistencyPython:
    def test_snake_case_python_scores_100(self, scorer: LegibilityScorer, write_file) -> None:
        path = write_file(
            "good.py",
            """
            def my_function():
                return 1

            def another_function():
                return 2

            class MyClass:
                pass
            """,
        )
        report = scorer.score(path)
        assert report.dimensions["naming_consistency"] == 100.0

    def test_camelcase_function_in_python_flagged(
        self, scorer: LegibilityScorer, write_file
    ) -> None:
        path = write_file(
            "mixed.py",
            """
            def my_function():
                return 1

            def myFunction():
                return 2
            """,
        )
        report = scorer.score(path)
        assert report.dimensions["naming_consistency"] < 100.0
        assert any("not snake_case" in f for f in report.findings)

    def test_pascalcase_class_passes(self, scorer: LegibilityScorer, write_file) -> None:
        path = write_file(
            "good_class.py",
            """
            class Frob:
                pass

            class FrobTwo:
                pass
            """,
        )
        report = scorer.score(path)
        assert report.dimensions["naming_consistency"] == 100.0

    def test_lowercase_class_in_python_flagged(self, scorer: LegibilityScorer, write_file) -> None:
        path = write_file(
            "bad_class.py",
            """
            class lowerclass:
                pass
            """,
        )
        report = scorer.score(path)
        assert report.dimensions["naming_consistency"] < 100.0
        assert any("not PascalCase" in f for f in report.findings)

    def test_dunder_method_exempt_from_snake_check(
        self, scorer: LegibilityScorer, write_file
    ) -> None:
        path = write_file(
            "with_dunder.py",
            """
            class MyClass:
                def __init__(self):
                    pass

                def __repr__(self):
                    return ''

                def helper_func(self):
                    return 1
            """,
        )
        report = scorer.score(path)
        assert report.dimensions["naming_consistency"] == 100.0

    def test_python_syntax_error_yields_zero_naming(
        self, scorer: LegibilityScorer, write_file
    ) -> None:
        path = write_file("broken.py", "def !!!syntax error\n")
        report = scorer.score(path)
        assert report.dimensions["naming_consistency"] == 0.0
        assert any("python parse error" in f for f in report.findings)

    def test_async_function_classified_as_function(
        self, scorer: LegibilityScorer, write_file
    ) -> None:
        path = write_file(
            "async_def.py",
            """
            async def my_handler():
                return 1
            """,
        )
        report = scorer.score(path)
        assert report.dimensions["naming_consistency"] == 100.0


# ---------------------------------------------------------------------------
# 4. Naming consistency — JS/TS sub-scorer
# ---------------------------------------------------------------------------


class TestNamingConsistencyJsTs:
    def test_camelcase_js_scores_100(self, scorer: LegibilityScorer, write_file) -> None:
        path = write_file(
            "good.js",
            """
            function myHelper() { return 1; }
            function anotherHelper() { return 2; }
            class MyComponent { }
            """,
        )
        report = scorer.score(path)
        assert report.dimensions["naming_consistency"] == 100.0

    def test_snake_case_function_in_js_flagged(self, scorer: LegibilityScorer, write_file) -> None:
        path = write_file(
            "mixed.ts",
            """
            function my_helper() { return 1; }
            function goodHelper() { return 2; }
            """,
        )
        report = scorer.score(path)
        assert report.dimensions["naming_consistency"] < 100.0

    def test_arrow_const_function_recognised(self, scorer: LegibilityScorer, write_file) -> None:
        path = write_file(
            "arrow.ts",
            """
            const myHelper = () => 1;
            const anotherHelper = (x) => x + 1;
            class GoodClass { }
            """,
        )
        report = scorer.score(path)
        assert report.dimensions["naming_consistency"] == 100.0

    def test_non_python_non_js_file_gets_full_naming_score(
        self, scorer: LegibilityScorer, write_file
    ) -> None:
        path = write_file(
            "data.json",
            """
            { "key": "value" }
            """,
        )
        report = scorer.score(path)
        assert report.dimensions["naming_consistency"] == 100.0


# ---------------------------------------------------------------------------
# 5. Comment-to-code ratio — U-curve sub-scorer
# ---------------------------------------------------------------------------


class TestCommentRatio:
    def test_low_comment_ratio_under_0_05_finds_finding(
        self, scorer: LegibilityScorer, write_file
    ) -> None:
        body_lines = ["def foo():", "    pass"] * 30
        body = "\n".join(body_lines) + "\n# one\n"
        path = write_file("under.py", body)
        report = scorer.score(path)
        assert any("under-commented" in f for f in report.findings)

    def test_sweet_spot_comment_ratio_scores_100(
        self, scorer: LegibilityScorer, write_file
    ) -> None:
        # 4 comment lines / 20 code lines = 0.20 (sweet-spot mid-band)
        code = "\n".join([f"    x{i} = {i}" for i in range(20)])
        comments = "\n".join([f"    # comment for x{i}" for i in range(4)])
        body = f"def foo():\n{comments}\n{code}\n"
        path = write_file("sweet.py", body)
        report = scorer.score(path)
        assert report.metrics["comment_ratio"] == pytest.approx(0.20, abs=0.01)
        assert report.dimensions["comment_ratio"] == 100.0

    def test_over_commented_ratio_above_0_50_finds_finding(
        self, scorer: LegibilityScorer, write_file
    ) -> None:
        body = "\n".join([f"# comment {i}" for i in range(20)] + ["x = 1", "y = 2"])
        path = write_file("over.py", body)
        report = scorer.score(path)
        assert any("over-commented" in f for f in report.findings)
        assert report.dimensions["comment_ratio"] < 70.0

    def test_zero_comments_zero_ratio_score_floor(
        self, scorer: LegibilityScorer, write_file
    ) -> None:
        body = "\n".join([f"x = {i}" for i in range(20)])
        path = write_file("nocomments.py", body)
        report = scorer.score(path)
        assert report.dimensions["comment_ratio"] == 40.0

    def test_block_comment_recognised_in_c_style_file(
        self, scorer: LegibilityScorer, write_file
    ) -> None:
        body = "\n".join(
            [
                "/*",
                " * block 1",
                " */",
                "function helper() {",
                "    // line 1",
                "    return 1;",
                "}",
            ]
        )
        path = write_file("comments.js", body)
        report = scorer.score(path)
        assert report.metrics["comment_lines"] >= 4.0

    def test_comment_ratio_score_helper_curve(self) -> None:
        assert _comment_ratio_score(0.0) == 40.0
        assert _comment_ratio_score(0.05) == 70.0
        assert _comment_ratio_score(0.20) == 100.0
        assert _comment_ratio_score(0.50) == 70.0
        assert _comment_ratio_score(0.80) == pytest.approx(52.0, abs=2.0)
        assert _comment_ratio_score(2.0) == 40.0


class TestCommentSyntaxAndClassification:
    def test_comment_syntax_for_python(self) -> None:
        prefix, blocks = _comment_syntax_for(".py")
        assert prefix == "#"
        assert blocks == ()

    def test_comment_syntax_for_unknown_returns_empty(self) -> None:
        prefix, blocks = _comment_syntax_for(".unknown")
        assert prefix is None
        assert blocks == ()

    def test_comment_syntax_for_html_uses_arrow_block(self) -> None:
        prefix, blocks = _comment_syntax_for(".html")
        assert prefix is None
        assert blocks == (("<!--", "-->"),)

    def test_comment_syntax_for_css_uses_block_only(self) -> None:
        prefix, blocks = _comment_syntax_for(".css")
        assert prefix is None
        assert blocks == (("/*", "*/"),)

    def test_comment_syntax_for_yaml_uses_hash_prefix(self) -> None:
        prefix, blocks = _comment_syntax_for(".yaml")
        assert prefix == "#"

    def test_comment_syntax_for_markdown_uses_html_block(self) -> None:
        prefix, blocks = _comment_syntax_for(".md")
        assert prefix is None
        assert blocks == (("<!--", "-->"),)

    def test_comment_syntax_for_json_no_comments(self) -> None:
        prefix, blocks = _comment_syntax_for(".json")
        assert prefix is None
        assert blocks == ()

    def test_comments_only_file_returns_perfect_comment_score(
        self, scorer: LegibilityScorer, write_file
    ) -> None:
        # A file with only comments and no executable code lines exercises
        # the "code_lines == 0" early-return path of _score_comment_ratio.
        body = "# header\n# documentation only\n# end\n"
        path = write_file("doc.py", body)
        report = scorer.score(path)
        assert report.dimensions["comment_ratio"] == 100.0
        assert report.metrics["code_lines"] == 0.0

    def test_classify_blank_line(self) -> None:
        cat, state = _classify_comment_line("   ", "#", (), None)
        assert cat == "blank"
        assert state is None

    def test_classify_python_comment(self) -> None:
        cat, state = _classify_comment_line("# hello", "#", (), None)
        assert cat == "comment"
        assert state is None

    def test_classify_block_comment_open_close_same_line(self) -> None:
        cat, state = _classify_comment_line("/* short */", "//", (("/*", "*/"),), None)
        assert cat == "comment"
        assert state is None

    def test_classify_block_comment_continuation(self) -> None:
        cat, state = _classify_comment_line("/* opening", "//", (("/*", "*/"),), None)
        assert cat == "comment"
        assert state == ("/*", "*/")
        cat2, state2 = _classify_comment_line(" still inside", None, (), state)
        assert cat2 == "comment"
        assert state2 == ("/*", "*/")
        cat3, state3 = _classify_comment_line("end */", None, (), state)
        assert cat3 == "comment"
        assert state3 is None


# ---------------------------------------------------------------------------
# 6. Cyclomatic flow — radon + heuristic
# ---------------------------------------------------------------------------


class TestCyclomaticFlow:
    def test_simple_function_high_cyclomatic_score(
        self, scorer: LegibilityScorer, write_file
    ) -> None:
        path = write_file(
            "simple.py",
            """
            def add(x, y):
                return x + y

            def sub(x, y):
                return x - y
            """,
        )
        report = scorer.score(path)
        assert report.dimensions["cyclomatic_flow"] == 100.0

    def test_complex_function_lower_score(self, scorer: LegibilityScorer, write_file) -> None:
        body = "def complex_fn(x):\n"
        for i in range(20):
            body += f"    if x == {i}:\n        return {i}\n"
        body += "    return -1\n"
        path = write_file("complex.py", body)
        report = scorer.score(path)
        assert report.dimensions["cyclomatic_flow"] < 70.0
        assert any("avg cc" in f for f in report.findings)

    def test_no_functions_gets_perfect_cyclomatic(
        self, scorer: LegibilityScorer, write_file
    ) -> None:
        path = write_file("constants.py", "X = 1\nY = 2\nZ = 3\n")
        report = scorer.score(path)
        assert report.dimensions["cyclomatic_flow"] == 100.0

    def test_indentation_heuristic_used_for_non_python_files(
        self, scorer: LegibilityScorer, write_file
    ) -> None:
        body = "function helper(x) {\n    if (x > 0) { return 1; }\n    return 0;\n}\n"
        path = write_file("logic.js", body)
        report = scorer.score(path)
        assert any("indentation heuristic" in f for f in report.findings)

    def test_indentation_heuristic_helper_returns_baseline(self) -> None:
        metrics: dict[str, float] = {}
        avg = _indentation_cyclomatic_avg("def foo():\n    return 1\n", metrics)
        assert avg >= 1.0
        assert metrics["cc_avg"] >= 1.0

    def test_cyclomatic_score_helper_curve(self) -> None:
        assert _cyclomatic_score(2.0) == 100.0
        assert _cyclomatic_score(5.0) == 95.0
        assert _cyclomatic_score(10.0) == 75.0
        assert _cyclomatic_score(15.0) == 50.0
        assert _cyclomatic_score(40.0) == 0.0

    def test_radon_import_error_falls_back_to_heuristic(
        self, scorer: LegibilityScorer, write_file, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = write_file(
            "bigfn.py",
            """
            def loop_a(x):
                if x:
                    return 1
                return 0
            """,
        )
        # Force the dynamic ``from radon.complexity import cc_visit`` inside
        # _python_cyclomatic_avg to raise ImportError so the fallback branch
        # records a "radon not installed" finding (S-5 — never silently
        # treat absence as success).
        import builtins

        original_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "radon.complexity":
                raise ImportError("simulated absent radon")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        report = scorer.score(path)
        assert any("radon not installed" in f for f in report.findings)

    def test_radon_syntax_error_records_finding(
        self, scorer: LegibilityScorer, write_file, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = write_file(
            "ok.py",
            """
            def fine():
                return 1
            """,
        )
        # When radon raises a SyntaxError on otherwise-valid Python (rare
        # but possible for some edge-case constructs), we fall back to the
        # heuristic and surface the parse failure verbatim.
        from radon import complexity as radon_complexity

        def raising_cc_visit(_source: str):
            raise SyntaxError("simulated radon parse error")

        monkeypatch.setattr(radon_complexity, "cc_visit", raising_cc_visit)
        report = scorer.score(path)
        assert any("radon parse error" in f for f in report.findings)


# ---------------------------------------------------------------------------
# 7. Integration with gate evaluation — opt-in opt-out semantics
# ---------------------------------------------------------------------------


class TestGateIntegrationOptInOptOut:
    def test_legibility_scorer_none_byte_identical_to_v8_1_0_rc_1(self) -> None:
        gi = _pass_gate_input()
        history = [_round(1, 88.0)]
        baseline = evaluate_gate(gi, STRICT, round_num=2, history=history)
        with_kwarg = evaluate_gate(
            gi,
            STRICT,
            round_num=2,
            history=history,
            legibility_scorer=None,
            legibility_files=None,
        )
        assert baseline.decision == with_kwarg.decision
        assert baseline.composite_score == with_kwarg.composite_score
        assert baseline.details == with_kwarg.details
        assert "legibility" not in with_kwarg.details

    def test_legibility_scorer_with_empty_files_byte_identical(
        self, scorer: LegibilityScorer
    ) -> None:
        gi = _pass_gate_input()
        history = [_round(1, 88.0)]
        baseline = evaluate_gate(gi, STRICT, round_num=2, history=history)
        with_empty = evaluate_gate(
            gi,
            STRICT,
            round_num=2,
            history=history,
            legibility_scorer=scorer,
            legibility_files=[],
        )
        assert baseline.composite_score == with_empty.composite_score
        assert "legibility" not in with_empty.details

    def test_legibility_attached_when_files_supplied(
        self, scorer: LegibilityScorer, write_file
    ) -> None:
        path = write_file(
            "good.py",
            """
            def good_function():
                # explain why
                return 1
            """,
        )
        gi = _pass_gate_input()
        verdict = evaluate_gate(
            gi,
            STRICT,
            round_num=2,
            history=[_round(1, 88.0)],
            legibility_scorer=scorer,
            legibility_files=[str(path)],
        )
        leg = verdict.details["legibility"]
        assert leg["file_count"] == 1
        assert leg["mean_score"] > 0.0
        assert leg["weight"] == STRICT.legibility_weight

    def test_strict_profile_legibility_weight_is_0_05(self) -> None:
        assert STRICT.legibility_weight == pytest.approx(0.05)

    def test_audit_profile_legibility_weight_is_0_05(self) -> None:
        assert AUDIT.legibility_weight == pytest.approx(0.05)

    def test_standard_profile_legibility_weight_is_zero(self) -> None:
        assert STANDARD.legibility_weight == 0.0

    def test_relaxed_profile_legibility_weight_is_zero(self) -> None:
        assert RELAXED.legibility_weight == 0.0

    def test_strict_profile_uplift_well_legible_files(
        self, scorer: LegibilityScorer, write_file
    ) -> None:
        path = write_file(
            "wellnamed.py",
            """
            \"\"\"Module docstring.\"\"\"

            def add(x, y):
                # sum two numbers
                return x + y
            """,
        )
        gi = _pass_gate_input()
        history = [_round(1, 88.0)]
        baseline = evaluate_gate(gi, STRICT, round_num=2, history=history)
        with_legibility = evaluate_gate(
            gi,
            STRICT,
            round_num=2,
            history=history,
            legibility_scorer=scorer,
            legibility_files=[str(path)],
        )
        assert with_legibility.composite_score is not None
        assert baseline.composite_score is not None
        delta = with_legibility.composite_score - baseline.composite_score
        leg = with_legibility.details["legibility"]
        if leg["mean_score"] > 50.0:
            assert delta >= 0.0
            assert leg["composite_delta"] >= 0.0

    def test_zero_weight_profile_no_composite_change(
        self, scorer: LegibilityScorer, write_file
    ) -> None:
        path = write_file(
            "any.py",
            """
            def foo():
                return 1
            """,
        )
        gi = _pass_gate_input()
        history = [_round(1, 80.0)]
        baseline = evaluate_gate(gi, STANDARD, round_num=2, history=history)
        with_legibility = evaluate_gate(
            gi,
            STANDARD,
            round_num=2,
            history=history,
            legibility_scorer=scorer,
            legibility_files=[str(path)],
        )
        assert with_legibility.composite_score == baseline.composite_score
        assert with_legibility.details["legibility"]["composite_delta"] == 0.0

    def test_missing_file_recorded_in_errors_not_raised(self, scorer: LegibilityScorer) -> None:
        gi = _pass_gate_input()
        verdict = evaluate_gate(
            gi,
            STRICT,
            round_num=2,
            history=[_round(1, 88.0)],
            legibility_scorer=scorer,
            legibility_files=["does/not/exist.py"],
        )
        leg = verdict.details["legibility"]
        assert leg["file_count"] == 0
        assert any("FileNotFoundError" in e for e in leg["errors"])


# ---------------------------------------------------------------------------
# 8. _aggregate_legibility_reports + _attach_legibility_evaluation helpers
# ---------------------------------------------------------------------------


class TestLegibilityAggregation:
    def test_aggregate_empty_returns_zero(self) -> None:
        mean, dims = _aggregate_legibility_reports([])
        assert mean == 0.0
        assert dims == {}

    def test_aggregate_single_report_passes_through(
        self, scorer: LegibilityScorer, write_file
    ) -> None:
        path = write_file(
            "x.py",
            """
            def good():
                return 1
            """,
        )
        report = scorer.score(path)
        mean, dims = _aggregate_legibility_reports([report])
        assert mean == report.score
        assert set(dims) == set(report.dimensions)

    def test_aggregate_multiple_reports_means_dimensions(
        self, scorer: LegibilityScorer, write_file
    ) -> None:
        a = write_file(
            "a.py",
            """
            def a_one():
                return 1
            """,
        )
        b = write_file(
            "b.py",
            """
            def b_two():
                return 2
            """,
        )
        reports = [scorer.score(a), scorer.score(b)]
        mean, dims = _aggregate_legibility_reports(reports)
        expected = round(sum(r.score for r in reports) / len(reports), 2)
        assert mean == expected
        assert set(dims) == set(reports[0].dimensions)

    def test_attach_legibility_with_zero_weight_profile_does_not_change_composite(
        self, scorer: LegibilityScorer, write_file
    ) -> None:
        path = write_file(
            "x.py",
            """
            def y():
                return 1
            """,
        )
        gi = _pass_gate_input()
        verdict = evaluate_gate(gi, STANDARD, round_num=2, history=[_round(1, 80.0)])
        baseline_score = verdict.composite_score
        zero_weight_profile = replace(STANDARD, legibility_weight=0.0)
        _attach_legibility_evaluation(verdict, scorer, [str(path)], zero_weight_profile)
        assert verdict.composite_score == baseline_score
        assert verdict.details["legibility"]["composite_delta"] == 0.0


# ---------------------------------------------------------------------------
# 9. Composite score sanity (regression vs baseline composite_score helper)
# ---------------------------------------------------------------------------


class TestCompositeRegression:
    def test_composite_score_baseline_unaffected(self) -> None:
        dims = {"test_quality": 90.0, "code_review": 80.0, "architecture": 80.0, "benchmark": 100.0}
        # No weight key for legibility — composite_score must not implicitly
        # introduce one.
        assert composite_score(dims) == round(
            90.0 * 0.30 + 80.0 * 0.30 + 80.0 * 0.20 + 100.0 * 0.20,
            4,
        )
