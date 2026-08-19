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


def test_rule_tree_warns_on_partial_reference_downloads(tmp_path: Path):
    """PR #169 Bugbot finding: install_rule_tree must count + warn on failed
    reference downloads (the || true form hid partial references/ trees)."""
    env, project_dir, _home_dir, script_path = _install_env(tmp_path)

    # Fake curl variant: SKILL.md + manifest succeed, every reference fails.
    fake_curl = Path(env["PATH"].split(os.pathsep)[0]) / "curl"
    patched = _FAKE_CURL.replace(
        'elif echo "$basename" | grep -q \'\\.md$\'; then\n  echo "# $basename" > "$dest"\n',
        "elif echo \"$url\" | grep -q '/references/'; then\n  exit 22\n",
    )
    assert patched != _FAKE_CURL, "fake-curl patch anchor drifted"
    fake_curl.write_text(patched)

    zed = subprocess.run(
        ["bash", str(script_path), "zed", "--no-plugins"],
        cwd=project_dir,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    # Partial reference tree stays warn-not-fatal (S-5 warn path) …
    assert zed.returncode == 0, zed.stderr
    # … but the failure count must now be operator-visible.
    combined = zed.stdout + zed.stderr
    assert "references failed" in combined, combined
    assert (project_dir / ".rules" / "devola-flow.md").exists()


def test_auto_and_all_propagate_local_scaffold_failure(tmp_path: Path):
    """PR #173 Bugbot finding: `auto` and `all` must propagate install_local's
    exit 1 instead of finishing with the success footer on a broken scaffold."""
    env, project_dir, _home_dir, script_path = _install_env(tmp_path)

    # Fake python3: devolaflow imports fine, but the scaffold module fails —
    # the exact Track C-1 failure mode auto/all used to swallow.
    fakebin = Path(env["PATH"].split(os.pathsep)[0])
    fake_python = fakebin / "python3"
    fake_python.write_text(
        "#!/usr/bin/env bash\n"
        'case "$*" in\n'
        '  *"devolaflow.local.workspace"*) echo "forced scaffold failure" >&2; exit 1 ;;\n'
        "  *) exit 0 ;;\n"
        "esac\n"
    )
    fake_python.chmod(0o755)

    for target in ("auto", "all"):
        run = subprocess.run(
            ["bash", str(script_path), target, "--no-plugins"],
            cwd=project_dir,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert run.returncode == 1, f"{target}: {run.stdout}\n{run.stderr}"
        assert "Now Using DevolaFlow" not in run.stdout, f"{target} printed success footer"


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
