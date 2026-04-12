"""Tests for the shell installer entrypoints."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def test_install_script_supports_global_claude_and_update(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "install.sh"
    mvp_source = repo_root / "workflow-system" / "agent" / "MVP-SKILL.md"

    fakebin = tmp_path / "fakebin"
    fakebin.mkdir()
    fake_curl = fakebin / "curl"
    fake_curl.write_text(
        """#!/usr/bin/env bash
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

if [ "${url##*/}" = "MVP-SKILL.md" ]; then
  cp "$FAKE_MVP_SOURCE" "$dest"
else
  echo "unsupported url: $url" >&2
  exit 1
fi
"""
    )
    fake_curl.chmod(0o755)

    home_dir = tmp_path / "home"
    project_dir = tmp_path / "project"
    home_dir.mkdir()
    project_dir.mkdir()

    env = os.environ.copy()
    env["HOME"] = str(home_dir)
    env["PATH"] = f"{fakebin}:{env['PATH']}"
    env["FAKE_MVP_SOURCE"] = str(mvp_source)

    install = subprocess.run(
        ["bash", str(script_path), "claude", "--global"],
        cwd=project_dir,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert install.returncode == 0, install.stderr

    claude_md = home_dir / ".claude" / "CLAUDE.md"
    assert claude_md.exists()
    assert "devola-flow" in claude_md.read_text()

    claude_md.write_text("devola-flow stale install\n")
    update = subprocess.run(
        ["bash", str(script_path), "update"],
        cwd=project_dir,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert update.returncode == 0, update.stderr
    assert "orchestrating multi-file software tasks" in claude_md.read_text()
