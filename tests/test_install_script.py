"""Tests for the shell installer entrypoints."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

_FAKE_CURL = """#!/usr/bin/env bash
set -eu
dest=""
url=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    -o)
      dest="$2"
      shift 2
      ;;
    --connect-timeout|--max-time|--retry)
      shift 2
      ;;
    -*)
      shift
      ;;
    *)
      url="$1"
      shift
      ;;
  esac
done

basename="${url##*/}"
if [ "$basename" = "SKILL.md" ]; then
  cp "$FAKE_SKILL_SOURCE" "$dest"
elif [ "$basename" = "manifest.yaml" ]; then
  cp "$FAKE_MANIFEST_SOURCE" "$dest"
elif [ "$basename" = "__init__.py" ]; then
  echo '__version__ = "0.0.0"'
elif echo "$basename" | grep -q '\\.md$'; then
  echo "# $basename" > "$dest"
else
  echo "unsupported url: $url" >&2
  exit 1
fi
"""


def test_install_script_supports_global_claude_and_update(tmp_path: Path):
    env, project_dir, home_dir, script_path = _install_env(tmp_path)

    install = subprocess.run(
        ["bash", str(script_path), "claude", "--global", "--no-plugins"],
        cwd=project_dir,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert install.returncode == 0, install.stderr

    skill_md = home_dir / ".claude" / "skills" / "devola-flow" / "SKILL.md"
    assert skill_md.exists()
    assert "DevolaFlow" in skill_md.read_text()

    # B-2 version-compare: the stamp (0.0.0 from the fake remote) matches the
    # remote __version__, so a plain `update` must SKIP the re-download even
    # though the on-disk SKILL.md was corrupted — the stamp is the authority.
    skill_md.write_text("devola-flow stale install\n")
    update = subprocess.run(
        ["bash", str(script_path), "update"],
        cwd=project_dir,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert update.returncode == 0, update.stderr
    assert "up-to-date" in update.stdout
    assert skill_md.read_text() == "devola-flow stale install\n"

    # `update --force` bypasses the version compare and re-downloads.
    force = subprocess.run(
        ["bash", str(script_path), "update", "--force"],
        cwd=project_dir,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert force.returncode == 0, force.stderr
    assert "DevolaFlow" in skill_md.read_text()


def test_update_redownloads_when_stamp_is_stale(tmp_path: Path):
    """A stamp that differs from the remote __version__ triggers a re-download."""
    env, project_dir, home_dir, script_path = _install_env(tmp_path)

    install = subprocess.run(
        ["bash", str(script_path), "claude", "--global", "--no-plugins"],
        cwd=project_dir,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert install.returncode == 0, install.stderr

    skill_dir = home_dir / ".claude" / "skills" / "devola-flow"
    (skill_dir / ".devola-flow-version").write_text("0.0.0-older\n")
    (skill_dir / "SKILL.md").write_text("devola-flow stale install\n")

    update = subprocess.run(
        ["bash", str(script_path), "update"],
        cwd=project_dir,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert update.returncode == 0, update.stderr
    assert "up-to-date" not in update.stdout
    assert "DevolaFlow" in (skill_dir / "SKILL.md").read_text()


def test_uninstall_dry_run_then_real(tmp_path: Path):
    """`uninstall --dry-run` lists removals without deleting; plain run deletes."""
    env, project_dir, home_dir, script_path = _install_env(tmp_path)

    install = subprocess.run(
        ["bash", str(script_path), "claude", "--global", "--no-plugins"],
        cwd=project_dir,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert install.returncode == 0, install.stderr
    skill_dir = home_dir / ".claude" / "skills" / "devola-flow"
    assert (skill_dir / "SKILL.md").exists()

    dry = subprocess.run(
        ["bash", str(script_path), "uninstall", "--dry-run"],
        cwd=project_dir,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert dry.returncode == 0, dry.stderr
    assert "would remove" in dry.stdout
    assert (skill_dir / "SKILL.md").exists(), "--dry-run must not delete anything"

    real = subprocess.run(
        ["bash", str(script_path), "uninstall"],
        cwd=project_dir,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert real.returncode == 0, real.stderr
    assert not skill_dir.exists()


def _install_env(tmp_path: Path) -> tuple[dict, Path, Path, Path]:
    """Shared fixture body: fake curl + isolated HOME/project dirs."""
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "install.sh"

    fakebin = tmp_path / "fakebin"
    fakebin.mkdir()
    fake_curl = fakebin / "curl"
    fake_curl.write_text(_FAKE_CURL)
    fake_curl.chmod(0o755)

    home_dir = tmp_path / "home"
    project_dir = tmp_path / "project"
    home_dir.mkdir()
    project_dir.mkdir()

    env = os.environ.copy()
    env["HOME"] = str(home_dir)
    # Pin CODEX_HOME inside the fake home — the operator's real CODEX_HOME
    # (if exported) must never leak a real install into detection/uninstall.
    env["CODEX_HOME"] = str(home_dir / ".codex")
    env["PATH"] = f"{fakebin}:{env['PATH']}"
    env["FAKE_SKILL_SOURCE"] = str(repo_root / "workflow-system" / "agent" / "SKILL.md")
    env["FAKE_MANIFEST_SOURCE"] = str(repo_root / "workflow-system" / "agent" / "manifest.yaml")
    return env, project_dir, home_dir, script_path
