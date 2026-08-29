#!/usr/bin/env python3
"""Batch repository-wide hygiene checks for release preflight.

The lifecycle task hooks intentionally validate task-local ownership and
reported evidence only.  This module owns the release-side batch of checks
whose inputs span the repository.  Cache entries are keyed by the checked
inputs, command, Python version, and baseline revision; a changed input can
never reuse an old result.

``--changed-only`` and ``--dry-run`` are local inspection modes.  Both report
``INSUFFICIENT`` for checks they do not execute and return 2, so neither mode
can satisfy the hard release gate.

Historical ghost modules are the batch's ghost input.  Current-cycle ghost
modules already execute in ``test-core``; partitioning them here avoids
running the same ghost inventory twice while preserving complete release
coverage.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

STATUS_PASS = "PASS"
STATUS_FAIL = "FAIL"
STATUS_INSUFFICIENT = "INSUFFICIENT"
CACHE_VERSION = 1
DEFAULT_CACHE = Path(".local/telemetry/repo_hygiene_cache.json")
BATCH_SCRIPT = "scripts/check_repo_hygiene.py"


@dataclass(frozen=True)
class CheckSpec:
    """One deterministic release-side check and its input inventory."""

    name: str
    command: tuple[str, ...]
    inputs: tuple[str, ...]
    cacheable: bool = True


@dataclass(frozen=True)
class CheckResult:
    """Machine-readable result for one check."""

    name: str
    status: str
    cached: bool = False
    detail: str = ""
    stdout: str = ""
    stderr: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "cached": self.cached,
            "detail": self.detail,
            "stdout": self.stdout,
            "stderr": self.stderr,
        }


def _specs(baseline_ref: str) -> tuple[CheckSpec, ...]:
    """Return the fixed check order used by text and JSON output."""
    python = sys.executable
    return (
        CheckSpec(
            "agent-language",
            (python, "scripts/check_agent_language.py"),
            (
                "AGENTS.md",
                ".rules",
                ".cursor/skills",
                ".cursor/rules",
                "workflow-system/agent",
                "schemas",
                ".github/copilot-instructions.md",
                "src/devolaflow/task_adaptive_selector.py",
                "src/devolaflow/harness",
                "tests/fixtures/harness",
                "scripts/check_agent_language.py",
                BATCH_SCRIPT,
            ),
        ),
        CheckSpec(
            "import-graph",
            (python, "scripts/check_import_graph.py"),
            ("src/devolaflow", "scripts/check_import_graph.py", BATCH_SCRIPT),
        ),
        CheckSpec(
            "module-size",
            (python, "scripts/check_module_size.py", "--baseline-ref", baseline_ref),
            ("src/devolaflow", "scripts/check_module_size.py", BATCH_SCRIPT),
        ),
        CheckSpec(
            "functional-matrix",
            (python, "scripts/check_functional_matrix.py", "--json"),
            ("tests/functional", "scripts/check_functional_matrix.py", BATCH_SCRIPT),
            cacheable=False,
        ),
        CheckSpec(
            "ghost",
            (python, "-m", "pytest", "tests/ghost/", "-v", "--tb=short"),
            ("tests/ghost", BATCH_SCRIPT),
            cacheable=False,
        ),
    )


def _path_files(root: Path, relative: str) -> list[Path]:
    """Expand one repository-relative input into stable file paths."""
    path = root / relative
    if path.is_file():
        return [path]
    if path.is_dir():
        return sorted(item for item in path.rglob("*") if item.is_file())
    return []


def _fingerprint(root: Path, spec: CheckSpec) -> str:
    """Hash all declared inputs and execution context for cache safety."""
    digest = hashlib.sha256()
    digest.update(f"cache={CACHE_VERSION}\n".encode())
    digest.update(f"python={sys.version}\n".encode())
    digest.update(json.dumps(spec.command, sort_keys=True).encode())
    for relative in spec.inputs:
        digest.update(f"path={relative}\n".encode())
        files = _path_files(root, relative)
        if not files:
            digest.update(b"<missing>\n")
        for path in files:
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(b"\0")
            try:
                digest.update(path.read_bytes())
            except (OSError, UnicodeError) as exc:
                digest.update(f"<unreadable:{type(exc).__name__}:{exc}>\n".encode())
    if spec.name == "module-size":
        try:
            revision = _git(root, "rev-parse", spec.command[-1])
        except (OSError, subprocess.CalledProcessError):
            revision = "<unresolved>"
        digest.update(f"baseline-revision={revision}\n".encode())
    return digest.hexdigest()


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return result.stdout.strip()


def _changed_paths(root: Path, baseline_ref: str) -> set[str] | None:
    """Return changed paths, or ``None`` when git cannot establish them."""
    try:
        changed = set(_git(root, "diff", "--name-only", baseline_ref, "--").splitlines())
        changed.update(_git(root, "ls-files", "--others", "--exclude-standard", "--").splitlines())
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    return {path for path in changed if path}


def _applies_to_changed(spec: CheckSpec, changed: set[str]) -> bool:
    """Return whether a changed path intersects a check's input inventory."""
    for path in changed:
        for input_path in spec.inputs:
            if path == input_path or path.startswith(input_path.rstrip("/") + "/"):
                return True
    return False


def _load_cache(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"WARNING: repo-hygiene cache ignored: {exc}", file=sys.stderr)
        return {}
    if not isinstance(payload, dict) or payload.get("version") != CACHE_VERSION:
        print("WARNING: repo-hygiene cache ignored: invalid schema", file=sys.stderr)
        return {}
    checks = payload.get("checks")
    if not isinstance(checks, dict):
        print("WARNING: repo-hygiene cache ignored: invalid checks", file=sys.stderr)
        return {}
    return checks


def _save_cache(path: Path, cache: dict[str, Any]) -> None:
    """Atomically update the optimization cache without partial JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        {"version": CACHE_VERSION, "checks": cache},
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    )
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as handle:
        handle.write(payload)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(path)


def _cached_result(spec: CheckSpec, fingerprint: str, cache: dict[str, Any]) -> CheckResult | None:
    entry = cache.get(spec.name)
    if not isinstance(entry, dict) or entry.get("fingerprint") != fingerprint:
        return None
    status = entry.get("status")
    if status not in {STATUS_PASS, STATUS_FAIL}:
        return None
    return CheckResult(
        name=spec.name,
        status=status,
        cached=True,
        detail="cache-hit",
        stdout=str(entry.get("stdout", "")),
        stderr=str(entry.get("stderr", "")),
    )


def _run_spec(root: Path, spec: CheckSpec) -> CheckResult:
    environment = os.environ.copy()
    command = list(spec.command)
    if spec.name == "ghost":
        environment["GHOST_FULL"] = "1"
        command = _legacy_ghost_command(root, command)
    try:
        completed = subprocess.run(
            command,
            cwd=root,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return CheckResult(spec.name, STATUS_FAIL, detail=f"execution-error:{exc}")
    return CheckResult(
        spec.name,
        STATUS_PASS if completed.returncode == 0 else STATUS_FAIL,
        detail=f"exit={completed.returncode}",
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def _legacy_ghost_command(root: Path, command: list[str]) -> list[str]:
    """Run historical ghost modules; current modules belong to test-core."""
    legacy = ["tests/ghost/test_features_legacy.py"]
    for path in sorted((root / "tests" / "ghost").glob("test_features_v*.py")):
        match = re.match(r"test_features_v(?P<major>\d+)_", path.name)
        if match and int(match.group("major")) < 16:
            legacy.append(path.relative_to(root).as_posix())
    return [*command[:3], *legacy, *command[4:]]


def run_checks(
    root: Path,
    *,
    baseline_ref: str = "HEAD",
    cache_path: Path | None = DEFAULT_CACHE,
    changed_only: bool = False,
    dry_run: bool = False,
) -> tuple[CheckResult, ...]:
    """Run or classify the batch checks in their canonical order."""
    root = root.resolve()
    specs = _specs(baseline_ref)
    if dry_run:
        return tuple(
            CheckResult(spec.name, STATUS_INSUFFICIENT, detail="dry-run") for spec in specs
        )

    changed = _changed_paths(root, baseline_ref) if changed_only else None
    if changed_only and changed is None:
        return tuple(
            CheckResult(spec.name, STATUS_INSUFFICIENT, detail="changed-set-unavailable")
            for spec in specs
        )

    cache = _load_cache(root / cache_path) if cache_path is not None else {}
    results: list[CheckResult] = []
    cache_changed = False
    for spec in specs:
        if changed_only and not _applies_to_changed(spec, changed or set()):
            results.append(CheckResult(spec.name, STATUS_INSUFFICIENT, detail="unchanged-inputs"))
            continue
        fingerprint = _fingerprint(root, spec)
        result = _cached_result(spec, fingerprint, cache) if spec.cacheable else None
        if result is None:
            result = _run_spec(root, spec)
            if (
                cache_path is not None
                and spec.cacheable
                and result.status
                in {
                    STATUS_PASS,
                    STATUS_FAIL,
                }
            ):
                cache[spec.name] = {
                    "fingerprint": fingerprint,
                    "status": result.status,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                }
                cache_changed = True
        results.append(result)
    if cache_path is not None and cache_changed:
        try:
            _save_cache(root / cache_path, cache)
        except OSError as exc:
            print(f"WARNING: repo-hygiene cache update failed: {exc}", file=sys.stderr)
    return tuple(results)


def _overall_status(results: tuple[CheckResult, ...]) -> str:
    if any(result.status == STATUS_FAIL for result in results):
        return STATUS_FAIL
    if any(result.status == STATUS_INSUFFICIENT for result in results):
        return STATUS_INSUFFICIENT
    return STATUS_PASS


def _render_text(results: tuple[CheckResult, ...]) -> str:
    lines = [
        f"[repo-hygiene] check={result.name} status={result.status} "
        f"cache={'HIT' if result.cached else 'MISS'} detail={result.detail}"
        for result in results
    ]
    overall = _overall_status(results)
    lines.append(f"[repo-hygiene] status={overall}")
    for result in results:
        if result.status == STATUS_FAIL:
            output = (result.stdout + result.stderr).strip()
            if output:
                lines.append(f"[repo-hygiene] diagnostics={result.name}")
                lines.extend(output.splitlines())
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--baseline-ref", default="HEAD")
    parser.add_argument("--cache-file", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--changed-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)
    results = run_checks(
        args.root,
        baseline_ref=args.baseline_ref,
        cache_path=None if args.no_cache else args.cache_file,
        changed_only=args.changed_only,
        dry_run=args.dry_run,
    )
    overall = _overall_status(results)
    if args.format == "json":
        print(
            json.dumps(
                {
                    "status": overall,
                    "checks": [result.to_dict() for result in results],
                },
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            )
        )
    else:
        print(_render_text(results))
    return {STATUS_PASS: 0, STATUS_FAIL: 1, STATUS_INSUFFICIENT: 2}[overall]


if __name__ == "__main__":
    raise SystemExit(main())
