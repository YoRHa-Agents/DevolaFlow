"""PV-2 delivery checks for wheel and npm artifacts.

These tests intentionally exercise only the supported delivery boundaries:
the Python wheel's public version/compression surface and wheel-only local
scaffolding, plus the npm package's offline tarball and packed executable.
They do not require a source checkout in the isolated consumer environment.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tarfile
from pathlib import Path

import pytest

pytestmark = [pytest.mark.functional, pytest.mark.slow]

REPO_ROOT = Path(__file__).resolve().parents[2]
PROJECT_PYTHON = REPO_ROOT / ".venv" / "bin" / "python"


def _isolated_env(*, home: Path | None = None, path_prefix: Path | None = None) -> dict[str, str]:
    """Return an environment that cannot import from the checkout or user site."""
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env["PYTHONNOUSERSITE"] = "1"
    if home is not None:
        env["HOME"] = str(home)
    if path_prefix is not None:
        env["PATH"] = f"{path_prefix}{os.pathsep}{env['PATH']}"
    return env


@pytest.fixture(scope="session")
def built_wheel(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build one wheel with uv's cached build dependencies and no network."""
    if not PROJECT_PYTHON.is_file():
        pytest.skip(f"optional project interpreter is missing: {PROJECT_PYTHON}")
    if shutil.which("uv") is None:
        pytest.skip("optional uv executable is unavailable for offline wheel testing")

    wheel_dir = tmp_path_factory.mktemp("wheelhouse")
    result = subprocess.run(
        [
            "uv",
            "build",
            "--wheel",
            "--offline",
            "--out-dir",
            str(wheel_dir),
        ],
        cwd=REPO_ROOT,
        env=_isolated_env(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"offline wheel build failed; stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    wheels = sorted(wheel_dir.glob("devolaflow-*.whl"))
    assert len(wheels) == 1, f"expected one wheel, found {wheels}"
    return wheels[0]


@pytest.fixture
def wheel_consumer(built_wheel: Path, tmp_path: Path) -> tuple[Path, Path]:
    """Create a dependency-free consumer venv and install only the wheel."""
    venv_dir = tmp_path / "consumer-venv"
    create = subprocess.run(
        [str(PROJECT_PYTHON), "-m", "venv", str(venv_dir)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert create.returncode == 0, create.stderr

    consumer_python = venv_dir / "bin" / "python"
    install = subprocess.run(
        [
            str(consumer_python),
            "-m",
            "pip",
            "install",
            "--no-index",
            "--no-deps",
            str(built_wheel),
        ],
        capture_output=True,
        text=True,
        check=False,
        env=_isolated_env(home=tmp_path / "home", path_prefix=venv_dir / "bin"),
    )
    assert install.returncode == 0, (
        f"wheel-only offline install failed; stdout:\n{install.stdout}\nstderr:\n{install.stderr}"
    )
    dependencies = subprocess.run(
        [
            "uv",
            "pip",
            "install",
            "--offline",
            "--python",
            str(consumer_python),
            "pyyaml>=6.0",
            "jsonschema>=4.20",
            "Jinja2>=3.1",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert dependencies.returncode == 0, (
        "offline wheel dependency install failed; stdout:\n"
        f"{dependencies.stdout}\nstderr:\n{dependencies.stderr}"
    )
    return consumer_python, venv_dir


def test_wheel_exposes_curated_api_without_checkout(
    wheel_consumer: tuple[Path, Path], tmp_path: Path
) -> None:
    """The wheel imports and runs a small supported API boundary offline."""
    consumer_python, _venv_dir = wheel_consumer
    probe = """
import json
from pathlib import Path

import devolaflow
from devolaflow.compression_pipeline import (
    BYPASS_NEVER,
    CompressionPipeline,
    CompressionStage,
)

stage = CompressionStage(
    name="append_marker",
    transform=lambda payload, _context: payload + "!",
    bypass=BYPASS_NEVER,
)
result = CompressionPipeline((stage,), name="delivery-probe").run("wheel")
print(json.dumps({
    "version": devolaflow.__version__,
    "payload": result.payload,
    "module": str(Path(devolaflow.__file__).resolve()),
}))
"""
    run = subprocess.run(
        [str(consumer_python), "-c", probe],
        cwd=tmp_path,
        env=_isolated_env(home=tmp_path / "home", path_prefix=consumer_python.parent),
        capture_output=True,
        text=True,
        check=False,
    )
    from devolaflow import __version__ as checkout_version

    assert run.returncode == 0, run.stderr
    payload = json.loads(run.stdout)
    assert payload["version"] == checkout_version
    assert payload["payload"] == "wheel!"
    assert str(REPO_ROOT) not in payload["module"]


def test_wheel_only_devola_init_local_scaffolds_consumer_repo(
    wheel_consumer: tuple[Path, Path], tmp_path: Path
) -> None:
    """The installed entry point initializes a clean repo without source files."""
    consumer_python, venv_dir = wheel_consumer
    consumer_repo = tmp_path / "consumer-repo"
    consumer_repo.mkdir()
    home = tmp_path / "home"
    run = subprocess.run(
        [str(venv_dir / "bin" / "devola-init"), "local", "--no-compile"],
        cwd=consumer_repo,
        env=_isolated_env(home=home, path_prefix=venv_dir / "bin"),
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 0, (
        f"wheel-only local initialization failed with Python {consumer_python}:\n"
        f"stdout:\n{run.stdout}\nstderr:\n{run.stderr}"
    )
    assert (consumer_repo / ".local").is_dir()
    assert (consumer_repo / ".local" / "index.md").is_file()
    assert (consumer_repo / ".rules" / "compile-config.yaml").is_file()
    assert not (consumer_repo / "workflow-system").exists()


def _npm_json(result: subprocess.CompletedProcess[str]) -> object:
    """Decode npm's JSON result while preserving useful failure output."""
    assert result.returncode == 0, (
        f"npm command failed:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(f"npm --json output was not JSON: {exc}\n{result.stdout}")


def _pack_entries(payload: object) -> list[dict[str, object]]:
    """Normalise `npm pack --json` across the two shapes npm has shipped.

    npm emitted a list of pack results for years and now emits an object keyed
    by package name. The contract under test is the packed file set, which is
    identical either way, so the test asserts on that rather than on whichever
    envelope the locally installed npm happens to use.
    """

    if isinstance(payload, list):
        return [entry for entry in payload if isinstance(entry, dict)]
    if isinstance(payload, dict):
        return [entry for entry in payload.values() if isinstance(entry, dict)]
    pytest.fail(f"unrecognised npm pack --json payload: {payload!r}")


@pytest.mark.skipif(
    shutil.which("node") is None or shutil.which("npm") is None,
    reason="optional npm delivery contract skipped: node and npm are required",
)
def test_npm_pack_and_packed_bin_contract(tmp_path: Path) -> None:
    """Offline npm pack and the packed executable retain their contract."""
    npm = shutil.which("npm")
    node = shutil.which("node")
    assert npm is not None and node is not None
    package_dir = REPO_ROOT / "packages" / "npm"
    pack_env = _isolated_env(home=tmp_path / "npm-home")

    dry_run = subprocess.run(
        [npm, "pack", "--dry-run", "--offline", "--ignore-scripts", "--json"],
        cwd=package_dir,
        env=pack_env,
        capture_output=True,
        text=True,
        check=False,
    )
    dry_metadata = _npm_json(dry_run)
    dry_entries = _pack_entries(dry_metadata)
    assert len(dry_entries) == 1
    dry_files = {entry["path"] for entry in dry_entries[0]["files"]}
    assert "bin/devola-flow.js" in dry_files
    assert "package.json" in dry_files
    assert all(not path.startswith("src/") for path in dry_files)

    packed_dir = tmp_path / "packed"
    packed_dir.mkdir()
    packed = subprocess.run(
        [
            npm,
            "pack",
            "--offline",
            "--ignore-scripts",
            "--json",
            "--pack-destination",
            str(packed_dir),
        ],
        cwd=package_dir,
        env=pack_env,
        capture_output=True,
        text=True,
        check=False,
    )
    packed_metadata = _npm_json(packed)
    packed_entries = _pack_entries(packed_metadata)
    assert len(packed_entries) == 1
    tarball = packed_dir / packed_entries[0]["filename"]
    assert tarball.is_file()

    with tarfile.open(tarball) as archive:
        names = archive.getnames()
        assert "package/bin/devola-flow.js" in names
        archive.extractall(tmp_path / "extracted")
    packed_bin = tmp_path / "extracted" / "package" / "bin" / "devola-flow.js"

    help_result = subprocess.run(
        [node, str(packed_bin), "--help"],
        env=pack_env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert help_result.returncode == 0
    assert "install <cursor|claude|codex|kimicode|dsh|all>" in help_result.stdout

    from devolaflow import __version__ as checkout_version

    version_result = subprocess.run(
        [node, str(packed_bin), "--version"],
        env=pack_env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert version_result.returncode == 0
    assert version_result.stdout.strip() == checkout_version

    files_result = subprocess.run(
        [
            node,
            str(packed_bin),
            "files",
            "cursor",
            "--manifest-file",
            str(REPO_ROOT / "workflow-system" / "agent" / "manifest.yaml"),
        ],
        env=pack_env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert files_result.returncode == 0, files_result.stderr
    assert "SKILL.md" in files_result.stdout.splitlines()
