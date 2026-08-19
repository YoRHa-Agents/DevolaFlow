"""Lint + smoke suite for the install-manifest SSOT (Track B-1, D-5).

``workflow-system/agent/manifest.yaml`` is the single owner (Rule A-5)
of the per-tool install file lists. This suite pins:

* three-way parity — manifest ``references:`` ↔ on-disk
  ``workflow-system/agent/references/*.md`` ↔ ``_SF4_REFERENCE_SET``
  (upgrading Rule C-7's four-place sync with a machine-readable source);
* examples parity — manifest ``examples:`` ↔ on-disk ``examples/*.md``;
* consumer derivation — ``scripts/sync_cursor_skill.py::MIRRORED_FILES``
  equals the manifest's ``cursor`` profile resolution, and
  ``scripts/install.sh`` carries NO hardcoded per-file reference list;
* loader error states (Rule S-5 — explicit ``ManifestError``, no guessing);
* an offline end-to-end install smoke: ``bash scripts/install.sh cursor
  --project --base-url file://<repo>`` must download exactly the manifest
  profile (the B-1 clean-clone install gate).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from devolaflow.install_manifest import (
    ManifestError,
    load_manifest,
    profile_files,
)
from tests.ghost.test_registries import _SF4_REFERENCE_SET

REPO_ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = REPO_ROOT / "workflow-system" / "agent"
INSTALL_SH = REPO_ROOT / "scripts" / "install.sh"

# Tools whose install profile MUST exist (the install.sh / devola-init /
# sync_cursor_skill consumer set).
_REQUIRED_PROFILES = frozenset(
    {"cursor", "claude", "codex", "kimicode", "copilot", "windsurf", "zed", "cline", "roo"}
)


def test_manifest_sections_match_disk() -> None:
    """Manifest core/references/examples lists mirror the on-disk tree exactly."""
    manifest = load_manifest(AGENT_DIR)

    assert manifest["core"] == ["SKILL.md"]
    assert (AGENT_DIR / "SKILL.md").is_file()

    on_disk_refs = {f"references/{p.name}" for p in (AGENT_DIR / "references").glob("*.md")}
    assert set(manifest["references"]) == on_disk_refs, (
        "manifest references drifted from workflow-system/agent/references/: "
        f"missing={sorted(on_disk_refs - set(manifest['references']))}, "
        f"stale={sorted(set(manifest['references']) - on_disk_refs)}"
    )
    assert manifest["references"] == sorted(manifest["references"]), (
        "manifest references list must stay alphabetical (scaffold_reference.py contract)"
    )

    on_disk_examples = {f"examples/{p.name}" for p in (AGENT_DIR / "examples").glob("*.md")}
    assert set(manifest["examples"]) == on_disk_examples, (
        "manifest examples drifted from workflow-system/agent/examples/: "
        f"missing={sorted(on_disk_examples - set(manifest['examples']))}, "
        f"stale={sorted(set(manifest['examples']) - on_disk_examples)}"
    )


def test_manifest_references_match_sf4_set() -> None:
    """Three-way parity leg 2: manifest references ↔ the canonical SF-4 pin."""
    manifest = load_manifest(AGENT_DIR)
    basenames = {entry.removeprefix("references/") for entry in manifest["references"]}
    assert basenames == set(_SF4_REFERENCE_SET), (
        "manifest references drifted from _SF4_REFERENCE_SET: "
        f"missing={sorted(set(_SF4_REFERENCE_SET) - basenames)}, "
        f"extra={sorted(basenames - set(_SF4_REFERENCE_SET))}"
    )


def test_manifest_profiles_reference_defined_sets() -> None:
    """Every profile resolves; the consumer tool set is fully covered."""
    manifest = load_manifest(AGENT_DIR)
    names = set(manifest["install_profiles"])
    assert names >= _REQUIRED_PROFILES, (
        f"manifest install_profiles missing tools: {sorted(_REQUIRED_PROFILES - names)}"
    )
    for name in names:
        files = profile_files(manifest, name)
        assert files, f"profile {name!r} resolved to an empty file list"
        assert files[0] == "SKILL.md", f"profile {name!r} must ship SKILL.md first (core)"
        missing = [rel for rel in files if not (AGENT_DIR / rel).is_file()]
        assert not missing, f"profile {name!r} lists files missing on disk: {missing}"


def test_mirrored_files_derive_from_manifest_cursor_profile() -> None:
    """scripts/sync_cursor_skill.py::MIRRORED_FILES == manifest cursor profile."""
    from scripts.sync_cursor_skill import MIRRORED_FILES

    manifest = load_manifest(AGENT_DIR)
    assert profile_files(manifest, "cursor") == MIRRORED_FILES, (
        "MIRRORED_FILES no longer matches the manifest cursor profile — "
        "the derivation in scripts/sync_cursor_skill.py must not be shadowed "
        "by a local list (Rule A-5.1)"
    )


def test_install_sh_has_no_hardcoded_file_list() -> None:
    """install.sh consumes the manifest; per-file reference literals are banned."""
    text = INSTALL_SH.read_text(encoding="utf-8")
    assert "manifest.yaml" in text, "install.sh must fetch the install manifest"
    hardcoded = [
        line.strip()
        for line in text.splitlines()
        if "references/" in line and ".md" in line and not line.lstrip().startswith("#")
    ]
    assert not hardcoded, (
        "install.sh regained hardcoded reference-file literals (G1 drift); "
        f"route them through manifest.yaml instead: {hardcoded}"
    )


def test_load_manifest_explicit_error_states(tmp_path: Path) -> None:
    """S-5: loader raises ManifestError for absent/invalid manifests, never guesses."""
    with pytest.raises(ManifestError, match="missing"):
        load_manifest(tmp_path)

    bad = tmp_path / "manifest.yaml"
    bad.write_text("- not\n- a\n- mapping\n", encoding="utf-8")
    with pytest.raises(ManifestError, match="mapping"):
        load_manifest(tmp_path)

    bad.write_text(
        "core:\n  - SKILL.md\nreferences: []\nexamples:\n  - examples/x.md\n",
        encoding="utf-8",
    )
    with pytest.raises(ManifestError, match="references"):
        load_manifest(tmp_path)

    bad.write_text(
        "core:\n  - SKILL.md\n"
        "references:\n  - references/a.md\n"
        "examples:\n  - examples/x.md\n"
        "install_profiles:\n  cursor: {kind: skill-dir, sets: [core, bogus]}\n",
        encoding="utf-8",
    )
    with pytest.raises(ManifestError, match="undefined sets"):
        load_manifest(tmp_path)

    bad.write_text(
        "core:\n  - SKILL.md\n"
        "references:\n  - references/a.md\n"
        "examples:\n  - examples/x.md\n"
        "install_profiles:\n  cursor: {kind: skill-dir, sets: [core]}\n",
        encoding="utf-8",
    )
    manifest = load_manifest(tmp_path)
    assert profile_files(manifest, "cursor") == ["SKILL.md"]
    with pytest.raises(ManifestError, match="unknown install profile"):
        profile_files(manifest, "nonexistent")


@pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("curl") is None,
    reason="bash/curl not available",
)
def test_install_sh_e2e_file_base_url(tmp_path: Path) -> None:
    """Offline E2E: file:// base-url install ships exactly the manifest profile."""
    env = os.environ.copy()
    env["HOME"] = str(tmp_path)
    env.pop("CODEX_HOME", None)

    result = subprocess.run(
        [
            "bash",
            str(INSTALL_SH),
            "cursor",
            "--project",
            f"--base-url=file://{REPO_ROOT}",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, (
        f"install.sh exited {result.returncode}; stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "manifest unavailable" not in result.stdout, (
        f"file:// manifest fetch failed — fallback fired: {result.stdout!r}"
    )

    dest = tmp_path / ".cursor" / "skills" / "devola-flow"
    manifest = load_manifest(AGENT_DIR)
    expected = set(profile_files(manifest, "cursor"))
    installed = {
        p.relative_to(dest).as_posix()
        for p in dest.rglob("*")
        if p.is_file() and p.name != ".devola-flow-version"
    }
    assert installed == expected, (
        f"installed set != manifest cursor profile: "
        f"missing={sorted(expected - installed)}, extra={sorted(installed - expected)}"
    )

    stamp = dest / ".devola-flow-version"
    assert stamp.is_file(), "install must write the .devola-flow-version stamp"
    from devolaflow import __version__

    assert stamp.read_text(encoding="utf-8").strip() == __version__


def test_manifest_flow_style_profiles_shell_parseable() -> None:
    """The shell parser contract: every profile entry is single-line flow style.

    scripts/install.sh parses ``install_profiles`` with a line-oriented
    sed expression — a profile broken across lines (block style) would
    silently vanish from the shell's view. Assert the raw text keeps one
    ``{...sets: [...]}`` line per profile declared in the parsed YAML.
    """
    text = (AGENT_DIR / "manifest.yaml").read_text(encoding="utf-8")
    parsed = yaml.safe_load(text)
    for name in parsed["install_profiles"]:
        matching = [
            line
            for line in text.splitlines()
            if line.startswith(f"  {name}:") and "{" in line and "sets:" in line and "}" in line
        ]
        assert matching, (
            f"install profile {name!r} is not single-line flow style — "
            "scripts/install.sh's sed parser cannot read it"
        )
