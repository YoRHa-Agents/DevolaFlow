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


# ---------- .cursor/skills/devola-flow/ mirror parity ----------
# Added by feat/cursor-skill-mirror-sync; relaxed by chore/cursor-skill-mirror-untrack.
# The project-local skill mirror under .cursor/skills/devola-flow/ is now
# gitignored (opt-in via `make sync-cursor-skill --init` or the project-local
# installer). When present, it must stay bytewise identical to the canonical
# skill under workflow-system/agent/ (SKILL + 10 refs + 3 examples, matching
# what scripts/install.sh::install_cursor downloads for end users) and its
# stamp .cursor/skills/devola-flow/.devola-flow-version must first-line equal
# src/devolaflow/__init__.py __version__. When absent (fresh clones, CI), the
# tests pytest.skip so the suite passes cleanly. See Rule SF-3 / CP-3.
#
# v8.0.0 P-08 grew this set 12 -> 13 by appending references/behavioral-guidelines.md
# (the L3 behavioral primitives reference wired through the new top-level
# behavioral_guidelines dispatch field at canonical_order position 14, schema v3).
# v8.3.0 PV-09 grew this set 13 -> 14 by appending references/agent-workspace.md
# (the change-driven workspace reference covering .local/.agent/, append-only
# handoff envelopes, source-of-truth specs, and per-artifact token budgets).
# v8.4.0 rollup grew this set 14 -> 15 by appending references/shell-proxy.md
# (the RTK + memory-router stack reference covering runtime-plugins.yaml RTK row,
# the shell_proxy/ package, the pre_shell_call lifecycle hook, the memory_router/
# planning fast-path, and the .local/memory/{cases,commands}/ recipe layers).
# v9.0.0 PV-01 (v8.4.1) grew this set 15 -> 16 by appending references/plan-mode-enforcement.md
# (the plan-mode L0 operating contract reference absorbing SKILL.md §"Mode
# Awareness" PLAN MODE detail + §"Reinforcement Rules" mechanism, freeing
# ~57 lines of SKILL.md headroom and closing R7 carry-forward + B-01).

_MIRRORED_SKILL_FILES = [
    "SKILL.md",
    "references/agent-hierarchy.md",
    "references/agent-workspace.md",
    "references/meta-framework.md",
    "references/decomposition-gate.md",
    "references/repo-modes.md",
    "references/execution-protocol.md",
    "references/message-schemas.md",
    "references/team-roles.md",
    "references/context-isolation.md",
    "references/behavioral-guidelines.md",
    "references/shell-proxy.md",
    "references/plan-mode-enforcement.md",
    "examples/full-pipeline-trace.md",
    "examples/hotfix-trace.md",
    "examples/convergence-loop-trace.md",
]
_MIRROR_DIR_REL = Path(".cursor/skills/devola-flow")


def _mirror_present(project_root: Path) -> bool:
    return (project_root / _MIRROR_DIR_REL).is_dir()


@pytest.mark.parametrize("rel_path", _MIRRORED_SKILL_FILES)
def test_cursor_skill_mirror_bytewise_parity(project_root: Path, rel_path: str):
    if not _mirror_present(project_root):
        pytest.skip(".cursor/skills/devola-flow/ not locally installed (gitignored, opt-in)")
    canonical = project_root / "workflow-system" / "agent" / rel_path
    mirror = project_root / ".cursor" / "skills" / "devola-flow" / rel_path
    assert canonical.is_file(), f"canonical missing: {canonical}"
    assert mirror.is_file(), f"mirror missing: {mirror} — run `make sync-cursor-skill`"
    assert canonical.read_bytes() == mirror.read_bytes(), (
        f"{rel_path} drifted between canonical and .cursor mirror — run `make sync-cursor-skill`"
    )


def test_cursor_skill_stamp_matches_version(project_root: Path):
    if not _mirror_present(project_root):
        pytest.skip(".cursor/skills/devola-flow/ not locally installed (gitignored, opt-in)")
    stamp = project_root / ".cursor" / "skills" / "devola-flow" / ".devola-flow-version"
    assert stamp.is_file(), f"stamp missing: {stamp} — run `make sync-cursor-skill`"
    lines = stamp.read_text(encoding="utf-8").splitlines()
    assert lines, f"stamp empty: {stamp}"
    first_line = lines[0]
    init = (project_root / "src" / "devolaflow" / "__init__.py").read_text(encoding="utf-8")
    m = re.search(r'__version__\s*=\s*"([^"]+)"', init)
    assert m, "could not find __version__ in src/devolaflow/__init__.py"
    canonical_version = m.group(1)
    assert first_line == canonical_version, (
        f".cursor/skills/devola-flow/.devola-flow-version first-line={first_line!r} "
        f"!= __version__={canonical_version!r} — run `make sync-cursor-skill`"
    )
    assert len(lines) == 1, (
        f"stamp must be a single line; got {len(lines)} — run `make sync-cursor-skill`"
    )
