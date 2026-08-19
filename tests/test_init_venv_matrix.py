"""Track C-4 — clean minimal-environment matrix smoke (E1 × S1–S3).

The 05-init-quality-fixes §6 matrix: E1 (minimal — python + git only on
``$PATH``) is the CI must-run axis; E2/E3 (node/npm/curl, codegraph/nines
preinstalled) stay local/nightly per the CI-time trade-off documented
there. E1 is reproduced hermetically by running ``devola-init local`` in
a subprocess whose ``$PATH`` contains a sanitised bin dir with ONLY the
whitelisted binaries — no venv-creation cost, no network, same external-
tool visibility as a clean venv.

Scenario axis:

* S1 — fresh empty git repo
* S2 — pre-existing ``.gitignore`` with user content + partial structure
* S3 — repeat run ×2 (idempotency)

Acceptance pins (05 §8): exit 0 in the minimal env, gitignore entries
correct and non-duplicated, structure contract clean, one hint per
missing optional dependency, foreground path ≤ 30s, and the missing-git
case fails UP FRONT with one explicit message and zero scaffold writes.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from devolaflow.init_probe import INIT_DEPENDENCIES
from devolaflow.local.workspace import verify_scaffold_structure

_REPO_ROOT: Path = Path(__file__).resolve().parents[1]

_ENTRY_SNIPPET = (
    "import sys; sys.argv = ['devola-init', 'local']; "
    "from devolaflow.init_project import main; main()"
)


def _sanitized_bin(tmp_path: Path, binaries: set[str]) -> Path:
    """Build a bin dir containing symlinks for *binaries* only (E1 axis)."""
    bin_dir = tmp_path / "sanitized-bin"
    bin_dir.mkdir()
    for name in binaries:
        real = shutil.which(name)
        assert real is not None, f"test host lacks {name!r}; cannot build the E1 env"
        (bin_dir / name).symlink_to(real)
    return bin_dir


def _run_init_local(repo: Path, bin_dir: Path, home: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PATH"] = str(bin_dir)
    env["HOME"] = str(home)
    env["PYTHONPATH"] = str(_REPO_ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-c", _ENTRY_SNIPPET],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


def _assert_e1_success(repo: Path, result: subprocess.CompletedProcess) -> None:
    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    # Capability table printed with exactly one hint per missing optional dep.
    assert "Capability probe (init chain)" in result.stdout
    for dep in INIT_DEPENDENCIES:
        if dep.tier != "required":
            assert dep.absent_hint in result.stdout, (
                f"E1 output missing the {dep.name} degradation hint"
            )
    # Gitignore entries present exactly once (C-1 idempotency contract).
    gitignore = (repo / ".gitignore").read_text(encoding="utf-8")
    assert gitignore.count(".codegraph/") == 1
    # Structure contract clean (C-2).
    missing, _drifted = verify_scaffold_structure(repo)
    assert missing == [], f"structure gaps in E1: {missing}"


@pytest.mark.parametrize("scenario", ["S1-fresh", "S2-existing", "S3-idempotent"])
def test_e1_minimal_env_matrix(scenario: str, tmp_path: Path) -> None:
    """E1 (python + git only): `devola-init local` succeeds in all 3 scenarios."""
    repo = tmp_path / "repo"
    repo.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    bin_dir = _sanitized_bin(tmp_path, {"git"})

    git_env = {**os.environ, "PATH": str(bin_dir), "HOME": str(home)}
    subprocess.run(["git", "init", "-q"], cwd=repo, env=git_env, check=True, capture_output=True)

    user_line = "node_modules/  # user entry, must survive"
    if scenario == "S2-existing":
        (repo / ".gitignore").write_text(user_line + "\n", encoding="utf-8")
        (repo / ".local" / "memory").mkdir(parents=True)  # partial structure

    started = time.monotonic()
    result = _run_init_local(repo, bin_dir, home)
    elapsed = time.monotonic() - started

    if scenario == "S3-idempotent":
        result = _run_init_local(repo, bin_dir, home)

    _assert_e1_success(repo, result)
    # 05 §3 acceptance: foreground critical path ≤ 30s (no codegraph wait).
    assert elapsed <= 30, f"E1 foreground path took {elapsed:.1f}s (> 30s budget)"
    if scenario == "S2-existing":
        assert user_line in (repo / ".gitignore").read_text(encoding="utf-8")


def test_missing_required_git_fails_upfront(tmp_path: Path) -> None:
    """No git on $PATH → one explicit error, exit 1, ZERO scaffold writes."""
    repo = tmp_path / "repo"
    repo.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    bin_dir = _sanitized_bin(tmp_path, set())  # not even git

    result = _run_init_local(repo, bin_dir, home)

    assert result.returncode == 1
    assert "required init dependency missing" in result.stdout
    assert "git" in result.stdout
    assert "Traceback" not in result.stderr, "must be one hint, not a stack trace"
    assert not (repo / ".local").exists(), "nothing may be scaffolded before the gate"
    assert not (repo / ".gitignore").exists()
