"""npm installation surface (packages/npm) — v17.0.0 R6.

Pins the @yorha-agents/devola-flow package scaffold:

* package.json contract — name/version/bin/engines/files/publishConfig, and
  ZERO runtime dependencies (the bin uses Node >= 18 built-ins only);
* the thin-installer bin — syntax-valid, offline ``--help``/``--version``,
  loud failures on unknown commands/targets (Rule S-5), and manifest-derived
  file lists byte-equal to ``devolaflow.install_manifest`` resolution
  (Rule A-5: the JS must not shadow the manifest SSOT);
* the CI wiring — npm-publish.yml (tag-triggered publish with provenance and
  a tag==version fail-fast) and the ci-checks.yml ``npm-package`` job;
* scripts/bump_version.py managing packages/npm/package.json (Rule C-6).

Node-dependent tests skip gracefully when ``node`` is not on PATH.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from scripts.bump_version import VERSION_LOCATIONS

REPO_ROOT = Path(__file__).resolve().parents[1]
NPM_DIR = REPO_ROOT / "packages" / "npm"
BIN_JS = NPM_DIR / "bin" / "devola-flow.js"
AGENT_DIR = REPO_ROOT / "workflow-system" / "agent"
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"

_NODE = shutil.which("node")
requires_node = pytest.mark.skipif(_NODE is None, reason="node not on PATH")


def _run_bin(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [_NODE, str(BIN_JS), *args],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def _load_pkg() -> dict:
    return json.loads((NPM_DIR / "package.json").read_text(encoding="utf-8"))


def test_package_json_contract() -> None:
    """package.json fields match the R6 spec; zero runtime dependencies."""
    from devolaflow import __version__

    pkg = _load_pkg()
    assert pkg["name"] == "@yorha-agents/devola-flow"
    assert pkg["version"] == __version__
    assert pkg["bin"] == {"devola-flow": "./bin/devola-flow.js"}
    assert pkg["engines"] == {"node": ">=18"}
    assert pkg["publishConfig"] == {"access": "public", "provenance": True}
    assert pkg["license"] == "MIT"
    assert "github.com/YoRHa-Agents/DevolaFlow" in pkg["repository"]["url"]
    assert "github.com/YoRHa-Agents/DevolaFlow" in pkg["homepage"]
    assert pkg["files"] == ["bin/"], "tarball allowlist must ship bin/ only (plus npm defaults)"
    for banned in ("dependencies", "devDependencies", "optionalDependencies"):
        assert banned not in pkg, f"installer must stay zero-dependency; found {banned!r}"


@requires_node
def test_bin_node_syntax_check() -> None:
    """The installer bin passes `node --check` (parses without executing)."""
    result = subprocess.run(
        [_NODE, "--check", str(BIN_JS)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr


@requires_node
def test_bin_help_and_version_offline() -> None:
    """--help and --version run offline, exit 0, and report the pkg version."""
    help_run = _run_bin("--help")
    assert help_run.returncode == 0, help_run.stderr
    for expected in ("install", "update", "doctor", "DEVOLA_FLOW_REF", "manifest.yaml"):
        assert expected in help_run.stdout, f"--help output missing {expected!r}"

    version_run = _run_bin("--version")
    assert version_run.returncode == 0, version_run.stderr
    assert version_run.stdout.strip() == _load_pkg()["version"]


@requires_node
@pytest.mark.parametrize("target", ["cursor", "claude"])
def test_bin_file_list_derives_from_manifest(target: str) -> None:
    """JS manifest resolution == devolaflow.install_manifest resolution (A-5)."""
    from devolaflow.install_manifest import load_manifest, profile_files

    expected = profile_files(load_manifest(AGENT_DIR), target)
    result = _run_bin("files", target, "--manifest-file", str(AGENT_DIR / "manifest.yaml"))
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().splitlines() == expected, (
        f"JS-resolved file list for {target!r} drifted from the manifest SSOT"
    )


@requires_node
def test_bin_fails_loudly_on_bad_input() -> None:
    """S-5: unknown commands/targets exit non-zero with a clear message."""
    unknown_target = _run_bin("install", "emacs")
    assert unknown_target.returncode != 0
    assert "emacs" in unknown_target.stderr

    unknown_command = _run_bin("frobnicate")
    assert unknown_command.returncode != 0
    assert "frobnicate" in unknown_command.stderr

    bad_manifest = _run_bin("files", "cursor", "--manifest-file", "does/not/exist.yaml")
    assert bad_manifest.returncode != 0
    assert "does/not/exist.yaml" in bad_manifest.stderr


def test_npm_publish_workflow_contract() -> None:
    """npm-publish.yml: v* tag trigger, provenance permissions, fail-fast verify."""
    text = (WORKFLOWS_DIR / "npm-publish.yml").read_text(encoding="utf-8")
    workflow = yaml.safe_load(text)
    # YAML 1.1 parses a bare `on:` key as boolean True.
    triggers = workflow.get("on", workflow.get(True))
    assert triggers["push"]["tags"] == ["v*"]
    assert workflow["permissions"] == {}
    checks = workflow["jobs"]["checks"]
    assert checks["permissions"] == {"contents": "read"}
    assert checks["uses"] == "./.github/workflows/ci-checks.yml"

    publish = workflow["jobs"]["publish"]
    assert publish["needs"] == "checks"
    assert publish["permissions"] == {"contents": "read", "id-token": "write"}
    steps_blob = json.dumps(publish["steps"])
    assert "npm publish --provenance --access public" in steps_blob
    assert "NPM_TOKEN" in steps_blob
    verify_idx = next(
        i for i, s in enumerate(publish["steps"]) if "packages/npm/package.json" in s.get("run", "")
    )
    publish_idx = next(
        i for i, s in enumerate(publish["steps"]) if "npm publish" in s.get("run", "")
    )
    assert verify_idx < publish_idx, "tag==version verify must precede npm publish"
    assert "packages/npm/package.json" in publish["steps"][verify_idx]["run"]


def test_ci_checks_npm_job_contract() -> None:
    """ci-checks.yml gains the offline npm-package job without needs: edges."""
    workflow = yaml.safe_load((WORKFLOWS_DIR / "ci-checks.yml").read_text(encoding="utf-8"))
    job = workflow["jobs"]["npm-package"]
    assert "needs" not in job, "D11: shared check jobs run in parallel (no needs edges)"
    steps_blob = json.dumps(job["steps"])
    assert "node --check packages/npm/bin/devola-flow.js" in steps_blob
    assert "--help" in steps_blob
    assert "--version" in steps_blob
    assert "npm pack --dry-run" in steps_blob


def test_all_workflow_yamls_parse() -> None:
    """Every .github/workflows/*.yml stays parseable YAML with a jobs map."""
    workflow_files = sorted(WORKFLOWS_DIR.glob("*.yml"))
    assert workflow_files, "no workflow files found"
    for wf_path in workflow_files:
        workflow = yaml.safe_load(wf_path.read_text(encoding="utf-8"))
        assert isinstance(workflow, dict), f"{wf_path.name} did not parse to a mapping"
        assert workflow.get("jobs"), f"{wf_path.name} has no jobs"


def test_bump_version_manages_npm_package_json() -> None:
    """C-6: packages/npm/package.json is a bump_version.py-managed location."""
    entries = [loc for loc in VERSION_LOCATIONS if loc["path"] == "packages/npm/package.json"]
    assert len(entries) == 1, "packages/npm/package.json must be declared exactly once"

    pkg_text = (NPM_DIR / "package.json").read_text(encoding="utf-8")
    pattern = re.compile(entries[0]["pattern"])
    first_match = pattern.search(pkg_text)
    assert first_match, "bump_version pattern does not match packages/npm/package.json"
    # count=1 substitution rewrites only the FIRST match — it must be the
    # package's own version key, so no earlier key may shadow it.
    assert first_match.group(0).split(":")[0] == '"version"'
    prefix = pkg_text[: first_match.start()]
    assert '"version"' not in prefix, "another version-like key precedes the package version"
