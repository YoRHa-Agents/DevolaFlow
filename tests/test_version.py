"""Tests for version consistency across all DevolaFlow version locations."""

from __future__ import annotations

import re
from pathlib import Path

import pytest


@pytest.fixture
def project_root() -> Path:
    return Path(__file__).parent.parent


def _read_version_from_init(root: Path) -> str:
    init = root / "src" / "devolaflow" / "__init__.py"
    match = re.search(r'__version__\s*=\s*"([^"]+)"', init.read_text())
    assert match, "__version__ not found in __init__.py"
    return match.group(1)


def test_version_format():
    """Version string must be valid semver."""
    from devolaflow import __version__

    assert re.match(r"^\d+\.\d+\.\d+(-[\w.]+)?$", __version__), (
        f"Invalid version format: {__version__}"
    )


def test_pyproject_version_matches(project_root: Path):
    """pyproject.toml version must match __init__.py."""
    canonical = _read_version_from_init(project_root)
    pyproject = project_root / "pyproject.toml"
    match = re.search(r'^version\s*=\s*"([^"]+)"', pyproject.read_text(), re.MULTILINE)
    assert match, "version not found in pyproject.toml"
    assert match.group(1) == canonical, f"pyproject.toml version {match.group(1)} != {canonical}"


def test_skill_md_version_matches(project_root: Path):
    """SKILL.md frontmatter version must match __init__.py."""
    canonical = _read_version_from_init(project_root)
    skill = project_root / "workflow-system" / "agent" / "SKILL.md"
    match = re.search(r'^version:\s*"([^"]+)"', skill.read_text(), re.MULTILINE)
    assert match, "version not found in SKILL.md frontmatter"
    assert match.group(1) == canonical, f"SKILL.md version {match.group(1)} != {canonical}"


def test_skill_md_banner_matches(project_root: Path):
    """SKILL.md version banner must match __init__.py."""
    canonical = _read_version_from_init(project_root)
    skill = project_root / "workflow-system" / "agent" / "SKILL.md"
    match = re.search(r"> \*\*Now Using DevolaFlow v([^*]+)\*\*", skill.read_text())
    assert match, "Version banner not found in SKILL.md"
    assert match.group(1) == canonical, f"SKILL.md banner version {match.group(1)} != {canonical}"


def test_mvp_skill_md_version_matches(project_root: Path):
    """MVP-SKILL.md frontmatter version must match __init__.py."""
    canonical = _read_version_from_init(project_root)
    mvp = project_root / "workflow-system" / "agent" / "MVP-SKILL.md"
    match = re.search(r'^version:\s*"([^"]+)"', mvp.read_text(), re.MULTILINE)
    assert match, "version not found in MVP-SKILL.md frontmatter"
    assert match.group(1) == canonical, f"MVP-SKILL.md version {match.group(1)} != {canonical}"


def test_mvp_skill_md_banner_matches(project_root: Path):
    """MVP-SKILL.md version banner must match __init__.py."""
    canonical = _read_version_from_init(project_root)
    mvp = project_root / "workflow-system" / "agent" / "MVP-SKILL.md"
    match = re.search(r"> \*\*Now Using DevolaFlow v([^*]+)\*\*", mvp.read_text())
    assert match, "Version banner not found in MVP-SKILL.md"
    assert match.group(1) == canonical, (
        f"MVP-SKILL.md banner version {match.group(1)} != {canonical}"
    )


def test_workflow_skill_yaml_version_matches(project_root: Path):
    """workflow-skill.yaml identity.version must match __init__.py."""
    canonical = _read_version_from_init(project_root)
    ws = project_root / "workflow-system" / "agent" / "workflow-skill.yaml"
    match = re.search(r'version:\s*"([^"]+)"', ws.read_text())
    assert match, "version not found in workflow-skill.yaml"
    assert match.group(1) == canonical, (
        f"workflow-skill.yaml version {match.group(1)} != {canonical}"
    )


def test_generate_human_docs_version_matches(project_root: Path):
    """generate_human_docs.py SOURCE_VERSION must match __init__.py."""
    canonical = _read_version_from_init(project_root)
    gen = project_root / "scripts" / "generate_human_docs.py"
    match = re.search(r'SOURCE_VERSION\s*=\s*"([^"]+)"', gen.read_text())
    assert match, "SOURCE_VERSION not found in generate_human_docs.py"
    assert match.group(1) == canonical, (
        f"generate_human_docs.py SOURCE_VERSION {match.group(1)} != {canonical}"
    )


def test_skill_md_has_update_section(project_root: Path):
    """SKILL.md must contain the Version & Update section."""
    skill = project_root / "workflow-system" / "agent" / "SKILL.md"
    content = skill.read_text()
    assert "## Version & Update" in content
    assert "update devola" in content.lower() or "update_devola" in content.lower()


def test_mvp_skill_md_has_update_section(project_root: Path):
    """MVP-SKILL.md must contain the Version & Update section."""
    mvp = project_root / "workflow-system" / "agent" / "MVP-SKILL.md"
    content = mvp.read_text()
    assert "## Version & Update" in content


def test_bump_version_script_exists(project_root: Path):
    """bump_version.py must exist and be importable as a script."""
    script = project_root / "scripts" / "bump_version.py"
    assert script.is_file(), "scripts/bump_version.py not found"
    content = script.read_text()
    assert "VERSION_LOCATIONS" in content
    assert "def bump(" in content


def test_skill_md_body_version_matches(project_root: Path):
    """SKILL.md body 'Current version:' must match __init__.py."""
    canonical = _read_version_from_init(project_root)
    skill = project_root / "workflow-system" / "agent" / "SKILL.md"
    pat = r"\*\*Current version:\*\*\s*(\d+\.\d+\.\d+(?:-[a-zA-Z0-9.]+)?)"
    match = re.search(pat, skill.read_text())
    assert match, "Current version not found in SKILL.md body"
    assert match.group(1) == canonical, f"SKILL.md body version {match.group(1)} != {canonical}"


def test_mvp_skill_md_body_version_matches(project_root: Path):
    """MVP-SKILL.md body 'Current version:' must match __init__.py."""
    canonical = _read_version_from_init(project_root)
    mvp = project_root / "workflow-system" / "agent" / "MVP-SKILL.md"
    text = mvp.read_text()
    match = re.search(r"\*\*Current version:\*\*\s*(\d+\.\d+\.\d+(?:-[a-zA-Z0-9.]+)?)", text)
    assert match, "Current version not found in MVP-SKILL.md body"
    assert match.group(1) == canonical, f"MVP-SKILL.md body version {match.group(1)} != {canonical}"
    assert f"Compare with current version ({canonical})" in text
    assert f"DevolaFlow v{canonical} is the latest version." in text


def test_readme_version_badge_matches(project_root: Path):
    """README.md version badge must match __init__.py."""
    canonical = _read_version_from_init(project_root)
    readme = project_root / "README.md"
    match = re.search(r"version-(\d+\.\d+\.\d+(?:-[a-zA-Z0-9.]+)?)-green", readme.read_text())
    assert match, "Version badge not found in README.md"
    assert match.group(1) == canonical, f"README badge version {match.group(1)} != {canonical}"


def test_benchmark_results_version_matches(project_root: Path):
    """Benchmark results page SAMPLE_DATA version must match __init__.py."""
    canonical = _read_version_from_init(project_root)
    bench = project_root / "workflow-system" / "human" / "demo" / "benchmark-results" / "index.html"
    match = re.search(r'"version":"(\d+\.\d+\.\d+(?:-[a-zA-Z0-9.]+)?)"', bench.read_text())
    assert match, "version not found in benchmark-results SAMPLE_DATA"
    assert match.group(1) == canonical, f"benchmark-results version {match.group(1)} != {canonical}"


def test_cli_version_cmd():
    """CLI version_cmd must produce expected output."""
    import io
    import sys

    from devolaflow import __version__
    from devolaflow.cli import version_cmd

    captured = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = captured
    try:
        version_cmd()
    except SystemExit:
        pass
    finally:
        sys.stdout = old_stdout

    output = captured.getvalue()
    assert f"DevolaFlow v{__version__}" in output
