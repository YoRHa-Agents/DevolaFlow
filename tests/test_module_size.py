"""Tests for the code-line size and comment-density gates."""

from __future__ import annotations

import pytest

from scripts.check_module_size import (
    ModuleMetrics,
    check_comment_ratios,
    check_line_counts,
    main,
    measure_module,
    measure_source,
)


def test_new_module_must_fit_ceiling() -> None:
    assert check_line_counts({"src/new.py": 801}, {}) == [
        "src/new.py: new module has 801 code lines (limit 800)"
    ]


def test_existing_module_must_not_grow() -> None:
    assert check_line_counts({"src/old.py": 901}, {"src/old.py": 900}) == [
        "src/old.py: grew from 900 to 901 code lines"
    ]


def test_unchanged_and_shrunk_modules_pass() -> None:
    assert (
        check_line_counts(
            {"src/same.py": 10, "src/smaller.py": 8},
            {"src/same.py": 10, "src/smaller.py": 900},
        )
        == []
    )


def test_metric_excludes_blanks_comments_and_docstrings() -> None:
    metrics = measure_source(
        '"""module docs\n\nmore docs\n"""\n'
        "\n"
        "# a pure comment\n"
        "def run():\n"
        '    """function docs"""\n'
        "    return 1\n"
    )

    assert metrics.code_lines == 2
    assert metrics.comment_lines == 1
    assert metrics.docstring_lines == 4
    assert metrics.nonblank_lines == 7


def test_multiline_runtime_string_is_code_not_docstring_or_comment() -> None:
    metrics = measure_source('payload = """\n# this is runtime data\n\nvalue\n"""\nresult = 1\n')

    assert metrics.code_lines == 5
    assert metrics.comment_lines == 0
    assert metrics.docstring_lines == 0


def test_nested_docstrings_are_only_excluded_in_docstring_positions() -> None:
    metrics = measure_source(
        "class Example:\n"
        '    """class docs\n'
        "    more docs\n"
        '    """\n'
        "    def run(self):\n"
        '        """method docs"""\n'
        "        return 1\n"
    )

    assert metrics.code_lines == 3
    assert metrics.docstring_lines == 4


def test_comment_ratio_boundary_passes_and_above_boundary_fails() -> None:
    boundary = ModuleMetrics(code_lines=2, comment_lines=2, docstring_lines=0, nonblank_lines=4)
    over = ModuleMetrics(code_lines=2, comment_lines=3, docstring_lines=0, nonblank_lines=5)

    assert check_comment_ratios({"src/boundary.py": boundary}) == []
    assert check_comment_ratios({"src/over.py": over}) == [
        "src/over.py: comment/docstring ratio 60.0% exceeds 50% "
        "(3 comment/docstring lines / 5 nonblank physical lines)"
    ]


def test_code_metric_makes_comment_growth_irrelevant_to_ratchet() -> None:
    baseline = measure_source("value = 1\n")
    current = measure_source("# explanation\n\nvalue = 1\n")

    assert baseline.code_lines == current.code_lines == 1
    assert (
        check_line_counts(
            {"src/example.py": current.code_lines},
            {"src/example.py": baseline.code_lines},
        )
        == []
    )


def test_main_uses_code_metric_for_git_baseline(monkeypatch, tmp_path, capsys) -> None:
    module = tmp_path / "src" / "devolaflow" / "example.py"
    module.parent.mkdir(parents=True)
    module.write_text("# current explanation\nvalue = 1\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "scripts.check_module_size._changed_modules",
        lambda root, baseline_ref: [module],
    )
    monkeypatch.setattr(
        "scripts.check_module_size._git",
        lambda root, *args: "value = 1\n" if args[0] == "show" else "",
    )

    assert main(["--baseline-ref", "BASE", "--maximum", "0"]) == 0
    assert "PASS: module-size gate (1 changed source module(s))" in capsys.readouterr().out


def test_new_module_limit_uses_code_lines_not_physical_lines() -> None:
    source = ("# comment\n\n" * 500) + ("value = 1\n" * 801)

    metrics = measure_source(source)

    assert metrics.code_lines == 801
    assert check_line_counts({"src/new.py": metrics.code_lines}, {}) == [
        "src/new.py: new module has 801 code lines (limit 800)"
    ]


def test_measure_source_rejects_malformed_python() -> None:
    with pytest.raises(ValueError, match="unable to measure Python source"):
        measure_source('unterminated = """\n')


def test_measure_module_reports_unreadable_path(tmp_path) -> None:
    with pytest.raises(ValueError, match="unable to read or measure"):
        measure_module(tmp_path / "missing.py")
