"""Test harness for ``scripts/install.sh``.

Targets the new ``auto_detect()`` branch added in v7.4.2 (deficiency D-6 in
``.local/research/v7.4.2_gap_analysis.md``) that invokes ``install_local``
when ``.local/`` is absent — root-cause fix for feedback #1 ("init workflow
did not correctly initialize ``.local``").

Sandboxing strategy: **Option (ii) — curl stub.** The bash installer fetches
SKILL.md and references via ``curl``; tests must remain offline. We prepend
a fake ``curl`` (exits 0 with no IO) to ``PATH`` so the cursor / claude /
copilot branches "complete" instantly without network IO. ``install_local()``
itself uses no ``curl`` — only ``mkdir -p`` plus an opt-in ``python3 -m
devolaflow.local.workspace`` invocation — so the assertions target the
``.local/feedbacks/`` and ``.local/tasks/`` directories that ``install_local``
creates unconditionally via ``mkdir -p``.

Tests skip cleanly when ``bash`` is not on ``PATH`` (CI-portability).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALL_SH = REPO_ROOT / "scripts" / "install.sh"


def _bash_available() -> bool:
    return shutil.which("bash") is not None


def _make_curl_stub(bin_dir: Path) -> None:
    """Create a fake ``curl`` in ``bin_dir`` that exits 0 with no network IO.

    install.sh swallows individual download failures via ``|| true`` and
    internal counters in ``dl_batch``; an exit-0 stub keeps the installer
    fast and offline-deterministic.
    """
    bin_dir.mkdir(parents=True, exist_ok=True)
    curl = bin_dir / "curl"
    curl.write_text("#!/usr/bin/env bash\nexit 0\n")
    curl.chmod(0o755)


def _run_install_sh(target: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run ``bash scripts/install.sh <target>`` in ``cwd`` with curl stubbed."""
    bin_dir = cwd / ".test_bin"
    _make_curl_stub(bin_dir)

    env = os.environ.copy()
    env["HOME"] = str(cwd)
    env["PATH"] = f"{bin_dir}:{env.get('PATH', '/usr/bin:/bin')}"
    env.pop("CODEX_HOME", None)

    return subprocess.run(
        ["bash", str(INSTALL_SH), target],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


@pytest.mark.skipif(not _bash_available(), reason="bash not available")
def test_auto_detect_invokes_install_local_when_local_missing(tmp_path: Path) -> None:
    """``auto`` target → new D-6 branch fires ``install_local`` when ``.local/`` is absent."""
    (tmp_path / ".cursor").mkdir()

    result = _run_install_sh("auto", tmp_path)

    assert result.returncode == 0, (
        f"install.sh exited {result.returncode}; stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert (tmp_path / ".local" / "feedbacks").is_dir(), (
        "install_local should have created .local/feedbacks/ via mkdir -p; "
        f"stdout={result.stdout!r}"
    )
    assert (tmp_path / ".local" / "tasks").is_dir()
    assert "Initializing local workspace" in result.stdout, (
        "Expected install_local's info message to appear, proving the "
        f"new auto_detect branch fired; stdout={result.stdout!r}"
    )


@pytest.mark.skipif(not _bash_available(), reason="bash not available")
def test_auto_detect_skips_install_local_when_local_present(tmp_path: Path) -> None:
    """``auto`` target → D-6 branch is SKIPPED when ``.local/`` already exists (idempotent)."""
    (tmp_path / ".cursor").mkdir()
    (tmp_path / ".local" / "feedbacks").mkdir(parents=True)
    sentinel = tmp_path / ".local" / "feedbacks" / "preexisting.md"
    sentinel.write_text("keep-me\n", encoding="utf-8")

    result = _run_install_sh("auto", tmp_path)

    assert result.returncode == 0, (
        f"install.sh exited {result.returncode}; stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert (tmp_path / ".local" / "feedbacks").is_dir()
    assert sentinel.read_text(encoding="utf-8") == "keep-me\n", (
        "Idempotency: pre-existing content under .local/ must NOT be touched"
    )
    assert "Initializing local workspace" not in result.stdout, (
        "install_local was invoked even though .local/ already exists; "
        'the new auto_detect branch must be guarded by `[ ! -d ".local" ]`. '
        f"stdout={result.stdout!r}"
    )


@pytest.mark.skipif(not _bash_available(), reason="bash not available")
def test_install_sh_local_target_explicit_still_works(tmp_path: Path) -> None:
    """Regression guard: explicit ``local`` target unchanged by the D-6 fix."""
    result = _run_install_sh("local", tmp_path)

    assert result.returncode == 0, (
        f"install.sh exited {result.returncode}; stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert (tmp_path / ".local" / "feedbacks").is_dir()
    assert (tmp_path / ".local" / "tasks").is_dir()
    # Track C-1: the success line now reflects the REAL scaffold outcome
    # (previously an unconditional "initialized" even when the python
    # scaffold silently no-op'd — R5 F1-H3).
    assert "Local workspace scaffolded" in result.stdout
