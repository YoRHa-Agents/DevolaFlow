"""Tests for version consistency across all DevolaFlow version locations."""

from __future__ import annotations

import json
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


def test_npm_package_json_version_matches(project_root: Path):
    """packages/npm/package.json version must match __init__.py (C-6, v17 R6).

    The npm package version doubles as the default download ref (v<version>
    tag) in packages/npm/bin/devola-flow.js, so drift here would make
    `npx @yorha-agents/devola-flow install` fetch the wrong skill set.
    Managed by scripts/bump_version.py.
    """
    canonical = _read_version_from_init(project_root)
    pkg_path = project_root / "packages" / "npm" / "package.json"
    pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
    assert pkg["version"] == canonical, (
        f"packages/npm/package.json version {pkg['version']} != {canonical}"
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


def test_readme_version_badge_is_dynamic(project_root: Path):
    """README version badge derives at render time from pyproject.toml (G-031).

    v14.4.0 replaced the pre-existing value pin (badge literal == __version__)
    with a mechanism pin: the badge is a shields.io dynamic TOML badge that
    reads `$.project.version` from the repo's main-branch raw pyproject.toml,
    so there is no static version literal for bump_version.py to manage.
    """
    readme = (project_root / "README.md").read_text()
    badge = re.search(r"https://img\.shields\.io/badge/dynamic/toml\?(\S+?)\)", readme)
    assert badge, "dynamic version badge not found in README.md"
    query_string = badge.group(1)
    assert "query=%24.project.version" in query_string, "dynamic badge must query $.project.version"
    assert (
        "url=https%3A%2F%2Fraw.githubusercontent.com%2FYoRHa-Agents%2FDevolaFlow"
        "%2Fmain%2Fpyproject.toml" in query_string
    ), "dynamic badge must read pyproject.toml from the main-branch raw URL"
    assert not re.search(r"badge/version-\d+\.\d+\.\d+-green", readme), (
        "static version badge found in README.md — it is no longer "
        "pattern-managed by bump_version.py and would silently go stale; "
        "use the shields.io dynamic TOML badge form (C-6 / G-031)"
    )


def test_benchmark_results_version_is_derived(project_root: Path):
    """Benchmark results page derives its version from versions.json (G-031).

    v14.4.0 replaced the pre-existing value pin (SAMPLE_DATA literal ==
    __version__) with a mechanism pin: the page fetches
    ../version-timeline/versions.json at load time and shows the newest
    entry's version; the SAMPLE_DATA literal is a clearly-marked static
    fallback for file:// contexts that MAY lag __version__ and is
    intentionally NOT synced by bump_version.py.
    """
    bench = project_root / "workflow-system" / "human" / "demo" / "benchmark-results" / "index.html"
    text = bench.read_text()
    assert "fetch('../version-timeline/versions.json'" in text, (
        "load-time version derivation (fetch of ../version-timeline/versions.json) "
        "missing from benchmark-results/index.html"
    )
    # The relative fetch target must exist; scripts/build-site.sh copies
    # demo/* to the site root, so the repo layout mirrors the deployed one.
    versions_json = (
        project_root / "workflow-system" / "human" / "demo" / "version-timeline" / "versions.json"
    )
    assert versions_json.is_file(), "version-timeline/versions.json missing"
    assert "STATIC FALLBACK" in text, (
        "SAMPLE_DATA fallback must stay clearly marked as a static fallback"
    )
    match = re.search(r'"version":"(\d+\.\d+\.\d+(?:-[a-zA-Z0-9.]+)?)"', text)
    assert match, "SAMPLE_DATA fallback version literal missing (must stay valid semver)"


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
# v8.4.0 rollup grew this set 14 -> 15 by appending references/memory-router.md
# (the memory-router planning fast-path and its .local/memory/cases recipes).
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
    "references/memory-router.md",
    "references/plan-mode-enforcement.md",
    # v8.5.0 PV-05 — 13th SF-4 canonical reference (env-flag inventory).
    "references/env-flags.md",
    # v8.5.1 PV-06 — 14th SF-4 canonical reference (CompressionPipeline protocol
    # + 6-transform unification + multi-pass filter chain T3 #5).
    "references/compression-pipeline.md",
    # v10.4.0 PV-05 — 15th SF-4 canonical reference (operator troubleshooting
    # handbook). Quick lookup index + per-symptom diagnostic patterns; D-X-5.
    "references/troubleshooting.md",
    # v10.7.0 D-O-1 — 16th SF-4 canonical reference (three-evaluator
    # rosetta). 6 × 9 cross-walk between SI-3 dimensions + NineS axes +
    # quality scalar with per-cell verbatim source citations.
    # Pairs with `scripts/auto_collect_si3_metrics.py` (D-O-2) and
    # `scripts/generate_evaluator_rosetta.py` (D-O-1 companion).
    "references/evaluator-rosetta.md",
    # v10.8.0 D-C-1 — 17th SF-4 canonical reference (upstream-unreachable
    # degraded-mode contract). Per-plugin fallback doc for NineS /
    # ui-pro with "Degraded ≠ Full" leading warning (D-C-1 §9 R1
    # mitigation). Pairs with `tests/test_degraded_mode.py` regression
    # suite and closes the v10.3.0 retrospective §3 NineS A1 pain.
    "references/degraded-mode.md",
    "examples/full-pipeline-trace.md",
    "examples/hotfix-trace.md",
    "examples/convergence-loop-trace.md",
    # v10.5.0 PV-01 (D-A-1) — 4th XL-tier example (multi-team analyze
    # + cross-stage merge counter-example). Pairs with the D-A-1
    # advisory annotation in SKILL.md §"Quick Action Decision".
    "examples/multi-stage-trace.md",
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
