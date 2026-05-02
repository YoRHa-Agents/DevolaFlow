"""Tests for ``scripts/humanize_doc.py`` and the humanize wiring in
``scripts/generate_human_docs.py``."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HUMANIZE_DOC = REPO_ROOT / "scripts" / "humanize_doc.py"


def _run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(HUMANIZE_DOC), *args],
        check=False,
        capture_output=True,
        text=True,
        cwd=str(cwd or REPO_ROOT),
    )


def test_score_subcommand_prints_composite(tmp_path: Path) -> None:
    doc = tmp_path / "sample.md"
    doc.write_text(
        "# Title\n\nThis is a short paragraph with no em-dashes.\n",
        encoding="utf-8",
    )
    result = _run("score", str(doc))
    assert result.returncode == 0
    assert "naturalness=" in result.stdout
    assert "profile=documentation_natural" in result.stdout


def test_check_subcommand_returns_zero_for_clean_doc(tmp_path: Path) -> None:
    doc = tmp_path / "clean.md"
    doc.write_text(
        "# Clean\n\nShort human prose. Another sentence. And a third. Done.\n",
        encoding="utf-8",
    )
    result = _run("check", str(doc))
    assert result.returncode in (0, 1)
    assert "pre=" in result.stdout
    assert "post=" in result.stdout
    assert "delta=" in result.stdout


def test_apply_subcommand_writes_file(tmp_path: Path) -> None:
    doc = tmp_path / "bad.md"
    doc.write_text(
        (
            "# Bad Doc\n\n"
            "In conclusion, the feature is shipped. It is -- with -- many -- em-dashes -- here.\n"
        ),
        encoding="utf-8",
    )
    result = _run("apply", str(doc), "-v")
    assert result.returncode == 0
    text = doc.read_text(encoding="utf-8")
    assert "in conclusion" not in text.lower() or "In conclusion," not in text
    assert "--" not in text


def test_apply_dry_run_does_not_modify(tmp_path: Path) -> None:
    doc = tmp_path / "dry.md"
    original = "In conclusion, we test. It is -- AI -- heavy.\n"
    doc.write_text(original, encoding="utf-8")
    result = _run("apply", str(doc), "--dry-run", "-v")
    assert result.returncode == 0
    assert doc.read_text(encoding="utf-8") == original


def test_apply_on_missing_file_returns_error() -> None:
    result = _run("apply", "/nonexistent/path/to/doc.md")
    assert result.returncode == 3


def test_profile_override_is_respected(tmp_path: Path) -> None:
    doc = tmp_path / "any.md"
    doc.write_text("# T\n\nA line.\n", encoding="utf-8")
    result = _run("score", str(doc), "--profile", "technical_concise")
    assert result.returncode == 0
    assert "profile=technical_concise" in result.stdout


def test_generate_human_docs_humanize_flag_default_on(tmp_path: Path) -> None:
    """Sanity check that the --no-humanize flag is parsed."""
    from scripts import generate_human_docs

    en_dir = tmp_path / "en"
    en_dir.mkdir()
    generate_human_docs._gen_doc(
        "quickstart",
        "Test",
        "Test desc — with em-dash.",
        "en",
        en_dir,
        humanize=False,
    )
    text = (en_dir / "quickstart.md").read_text(encoding="utf-8")
    assert "Test desc — with em-dash." in text


def test_generate_human_docs_humanize_applies_when_on(tmp_path: Path) -> None:
    from scripts import generate_human_docs

    en_dir = tmp_path / "en"
    en_dir.mkdir()
    generate_human_docs._gen_doc(
        "quickstart",
        "Test",
        "Test desc — with em-dash.",
        "en",
        en_dir,
        humanize=True,
    )
    text = (en_dir / "quickstart.md").read_text(encoding="utf-8")
    assert "Test desc — with em-dash." in text


def test_generate_human_docs_script_exposes_no_humanize_flag() -> None:
    """The generator script parses the `--no-humanize` opt-out flag."""
    script = REPO_ROOT / "scripts" / "generate_human_docs.py"
    text = script.read_text(encoding="utf-8")
    assert "--no-humanize" in text
    assert "_HUMANIZE_AVAILABLE" in text
