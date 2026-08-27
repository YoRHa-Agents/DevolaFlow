#!/usr/bin/env python3
"""Bump DevolaFlow version across all files that contain version references.

Usage:
    python scripts/bump_version.py 0.3.0
    python scripts/bump_version.py 0.3.0 --dry-run
    python scripts/bump_version.py 0.3.0 --tag          # tag committed current version
    python scripts/bump_version.py 0.3.0 --tag --dry-run

Single source of truth: src/devolaflow/__init__.py (__version__).
This script synchronizes all other locations to match.

Safe release sequence: bump -> verify/preflight -> commit -> tag.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

SEMVER_TOKEN = r"\d+\.\d+\.\d+(?:-[0-9A-Za-z]+(?:[.-][0-9A-Za-z]+)*)?"

VERSION_LOCATIONS = [
    {
        "path": "src/devolaflow/__init__.py",
        "pattern": r'__version__\s*=\s*"[^"]+"',
        "replacement": '__version__ = "{version}"',
    },
    {
        "path": "pyproject.toml",
        "pattern": r'^version\s*=\s*"[^"]+"',
        "replacement": 'version = "{version}"',
    },
    {
        "path": "workflow-system/agent/SKILL.md",
        "pattern": r'^version:\s*"[^"]+"',
        "replacement": 'version: "{version}"',
    },
    {
        "path": "workflow-system/agent/SKILL.md",
        "pattern": r"> \*\*Now Using DevolaFlow v[^*]+\*\*",
        "replacement": "> **Now Using DevolaFlow v{version}**",
    },
    {
        "path": "workflow-system/agent/SKILL.md",
        "pattern": rf"\*\*Current version:\*\* {SEMVER_TOKEN}",
        "replacement": "**Current version:** {version}",
    },
    # v14.4.0 G-031: two former pattern-managed surfaces are now DERIVED and
    # intentionally absent from this list (Rule C-6):
    #   - README.md version badge → shields.io dynamic TOML badge reading
    #     pyproject.toml from the GitHub raw URL at render time;
    #   - workflow-system/human/demo/benchmark-results/index.html SAMPLE_DATA
    #     version → load-time fetch of ../version-timeline/versions.json
    #     (newest entry; the in-file literal is a file:// fallback that may lag).
    {
        "path": "README.md",
        "pattern": rf'prints "DevolaFlow v{SEMVER_TOKEN}"',
        "replacement": 'prints "DevolaFlow v{version}"',
    },
    {
        "path": "workflow-system/agent/workflow-skill.yaml",
        "pattern": r'^\s{2}version:\s*"[^"]+"',
        "replacement": '  version: "{version}"',
    },
    {
        "path": "scripts/generate_human_docs.py",
        "pattern": r'SOURCE_VERSION\s*=\s*"[^"]+"',
        "replacement": 'SOURCE_VERSION = "{version}"',
    },
    {
        "path": "tests/test_smoke.py",
        "pattern": r'assert devolaflow\.__version__\s*==\s*"[^"]+"',
        "replacement": 'assert devolaflow.__version__ == "{version}"',
    },
    # v17.0.0 R6 (Rule C-6): the npm installation surface. The package version
    # doubles as the default download ref (v<version> tag) in
    # packages/npm/bin/devola-flow.js, and npm-publish.yml refuses to publish
    # when the pushed tag differs from it. The count=1 substitution relies on
    # the package "version" key being the FIRST "version" match in the file.
    {
        "path": "packages/npm/package.json",
        "pattern": r'"version":\s*"[^"]+"',
        "replacement": '"version": "{version}"',
    },
]

SEMVER_RE = re.compile(rf"^{SEMVER_TOKEN}$")


def _find_root() -> Path:
    p = Path(__file__).resolve().parent
    while p != p.parent:
        if (p / "pyproject.toml").exists():
            return p
        p = p.parent
    return Path.cwd()


def _get_current_version(root: Path) -> str:
    init = root / "src" / "devolaflow" / "__init__.py"
    match = re.search(r'__version__\s*=\s*"([^"]+)"', init.read_text())
    if not match:
        raise RuntimeError(f"Cannot read version from {init}")
    return match.group(1)


def _tag_error(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def _run_git(
    root: Path,
    *args: str,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    command = ["git", *args]
    try:
        return subprocess.run(
            command,
            cwd=str(root),
            check=check,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        _tag_error("git executable not found; cannot create a release tag")
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip() or f"exit {exc.returncode}"
        _tag_error(f"git command failed ({' '.join(command)}): {detail}")


def _check_version_tag_readiness(root: Path, version: str) -> tuple[str, str]:
    """Return the tag name and HEAD after read-only release-readiness checks."""
    tag_name = f"v{version}"
    head_sha = _run_git(root, "rev-parse", "HEAD").stdout.strip()

    branch = _run_git(root, "branch", "--show-current").stdout.strip()
    if branch != "main":
        branch_label = branch or "detached HEAD"
        _tag_error(
            "release tags must be created from main; "
            f"current branch is {branch_label}. Merge the release PR, then run "
            "`git checkout main` before tagging."
        )

    origin_main_ref = "refs/remotes/origin/main"
    origin_main_probe = _run_git(
        root,
        "rev-parse",
        "--verify",
        "--quiet",
        origin_main_ref,
        check=False,
    )
    if origin_main_probe.returncode == 0:
        origin_main_sha = origin_main_probe.stdout.strip()
        if head_sha != origin_main_sha:
            _tag_error(
                f"HEAD {head_sha} does not match origin/main {origin_main_sha}; "
                "run `git fetch origin main`, update local main to the merged "
                "remote commit, and retry."
            )
    elif origin_main_probe.returncode != 1:
        detail = (origin_main_probe.stderr or origin_main_probe.stdout or "").strip()
        _tag_error(
            f"git command failed while checking {origin_main_ref}: "
            f"{detail or f'exit {origin_main_probe.returncode}'}"
        )

    committed_source = _run_git(
        root,
        "show",
        "HEAD:src/devolaflow/__init__.py",
    ).stdout
    committed_match = re.search(r'__version__\s*=\s*"([^"]+)"', committed_source)
    if not committed_match:
        _tag_error(
            "cannot verify the package version committed at current HEAD; "
            "src/devolaflow/__init__.py has no __version__ assignment"
        )
    committed_version = committed_match.group(1)
    if committed_version != version:
        _tag_error(
            f"requested version {version} is not committed at current HEAD "
            f"(HEAD contains {committed_version}); bump, verify, and commit first"
        )

    # Ignore untracked files, but reject every staged or unstaged tracked change.
    status = _run_git(
        root,
        "status",
        "--porcelain=v1",
        "--untracked-files=no",
    ).stdout.strip()
    if status:
        _tag_error(
            "tracked worktree is not clean; "
            "`git status --short --untracked-files=no` reported:\n"
            f"{status}\nCommit staged and unstaged tracked changes before tagging."
        )

    tag_ref = f"refs/tags/{tag_name}"
    tag_probe = _run_git(
        root,
        "rev-parse",
        "--verify",
        "--quiet",
        tag_ref,
        check=False,
    )
    if tag_probe.returncode == 0:
        _tag_error(f"git tag {tag_name} already exists; refusing to replace it")
    if tag_probe.returncode != 1:
        detail = (tag_probe.stderr or tag_probe.stdout or "").strip()
        _tag_error(
            f"git command failed while checking {tag_ref}: "
            f"{detail or f'exit {tag_probe.returncode}'}"
        )

    return tag_name, head_sha


def _create_version_tag(root: Path, version: str) -> None:
    """Validate merged/clean readiness, then run git tag at current HEAD."""
    tag_name, head_sha = _check_version_tag_readiness(root, version)
    _run_git(
        root,
        "tag",
        "-a",
        "-m",
        f"Release {tag_name}",
        tag_name,
        head_sha,
    )
    print(f"\n  TAG    {tag_name} created at current HEAD {head_sha}")
    print(f"  Push with: git push origin {tag_name}")


def bump(
    new_version: str,
    *,
    dry_run: bool = False,
    tag: bool = False,
    root: Path | None = None,
) -> list[str]:
    root = root if root is not None else _find_root()
    current = _get_current_version(root)
    updated: list[str] = []
    missed: list[tuple[str, str]] = []
    planned_text: dict[Path, str] = {}
    matched_paths: list[str] = []

    if tag and current == new_version:
        tag_name = f"v{new_version}"
        print(f"Preparing release tag for committed version: {new_version}")
        if dry_run:
            print("(dry run — no files or git refs will be modified)")
            _, head_sha = _check_version_tag_readiness(root, new_version)
            print(f"\n  READY  verified main at {head_sha}")
            print(f"  WOULD  create annotated git tag {tag_name} at current HEAD")
            print(
                "  READY  requested version is committed, tracked worktree is "
                "clean, main matches origin/main when present, and tag is absent"
            )
            return []
        _create_version_tag(root, new_version)
        return []

    if tag and not dry_run:
        _tag_error(
            f"--tag is a finalization step, but current package version is "
            f"{current} and requested version is {new_version}. Run without "
            "--tag to bump, run release-preflight, verify and commit the "
            "changes, then rerun the same version with --tag."
        )

    print(f"Bumping version: {current} -> {new_version}")
    if dry_run:
        print("(dry run — no files will be modified)\n")

    for loc in VERSION_LOCATIONS:
        fpath = root / loc["path"]
        if not fpath.exists():
            # File-not-found stays a soft SKIP — absent files are the
            # legitimately-missing case (e.g. opt-in mirrors / partial
            # checkouts), mirroring the sync_cursor_skill no-op contract.
            print(f"  SKIP  {loc['path']} (not found)")
            continue

        text = planned_text.get(fpath)
        if text is None:
            text = fpath.read_text()
        pattern = re.compile(loc["pattern"], re.MULTILINE)
        replacement = loc["replacement"].format(version=new_version)

        match_count = len(pattern.findall(text))
        new_text, count = pattern.subn(replacement, text, count=1)
        if match_count == 1 and count == 1:
            planned_text[fpath] = new_text
            matched_paths.append(loc["path"])
            updated.append(loc["path"])
        else:
            reason = (
                "pattern not found"
                if match_count == 0
                else f"expected exactly one match, found {match_count}"
            )
            print(f"  MISS  {loc['path']} ({reason}: {loc['pattern']})")
            missed.append((loc["path"], loc["pattern"]))

    if missed:
        # G-032 / S-5: a canonical-location regex that matches nothing means
        # the bump is silently partial — hard-fail instead of exiting 0.
        print(
            f"\nERROR: {len(missed)} canonical location(s) exist but their "
            f"version pattern matched nothing — the bump is incomplete:",
            file=sys.stderr,
        )
        for path, pat in missed:
            print(f"  - {path}: pattern {pat!r} not found", file=sys.stderr)
        print(
            "Fix the file content or the VERSION_LOCATIONS pattern in "
            "scripts/bump_version.py, then re-run.",
            file=sys.stderr,
        )
        sys.exit(1)

    if not dry_run:
        for fpath, text in planned_text.items():
            fpath.write_text(text)

    status = "OK" if not dry_run else "WOULD"
    for path in matched_paths:
        print(f"  {status:6s} {path}")

    print(f"\n{len(updated)} locations {'would be ' if dry_run else ''}updated.")

    if tag:
        print(
            "\n  NEXT   this dry run previews version-file updates only. "
            "Apply the bump without --tag, run release-preflight, commit, "
            f"then rerun {new_version} with --tag."
        )

    return updated


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    dry_run = "--dry-run" in sys.argv
    create_tag = "--tag" in sys.argv

    if not args:
        root = _find_root()
        current = _get_current_version(root)
        print(f"Current version: {current}")
        print(f"\nUsage: {sys.argv[0]} <new-version> [--dry-run] [--tag]")
        print(f"Example: {sys.argv[0]} 0.3.0")
        print(f"         {sys.argv[0]} 0.3.0 --tag  # tag committed current version")
        sys.exit(0)

    new_version = args[0]
    if not SEMVER_RE.match(new_version):
        print(f"Error: '{new_version}' is not a valid semver (expected X.Y.Z)")
        sys.exit(1)

    updated = bump(new_version, dry_run=dry_run, tag=create_tag)

    # Final tag creation is intentionally write-free apart from the git ref.
    # Cursor-skill synchronization belongs to the first (version-bump) phase.
    if create_tag and not updated:
        return

    # Keep the .cursor/skills/devola-flow/ project-local mirror in sync with the
    # freshly-bumped canonical skill under workflow-system/agent/. The mirror is
    # opt-in (gitignored) — skip the subprocess entirely when it's not present
    # so fresh clones / CI bump cleanly. See C-6 in .rules/conventions.mdc
    # (ex skill-format-rules.mdc SF-3 + change-process-rules.mdc CP-3;
    # both legacy files retired v15.0.0 per clean_repo C1-2).
    sync_script = Path(__file__).parent / "sync_cursor_skill.py"
    mirror_dir = _find_root() / ".cursor" / "skills" / "devola-flow"
    if dry_run:
        print(f"\n[sync-cursor-skill] WOULD run {sync_script} (skipped: --dry-run)")
    elif not mirror_dir.exists():
        print(
            f"\n[sync-cursor-skill] skipped — {mirror_dir.relative_to(_find_root())} "
            "not present (opt-in mirror)"
        )
    else:
        print(f"\n[sync-cursor-skill] {sync_script}", flush=True)
        result = subprocess.run(
            [sys.executable, str(sync_script)],
            check=False,
        )
        if result.returncode != 0:
            print("ERROR: sync_cursor_skill.py failed", file=sys.stderr)
            sys.exit(result.returncode)


if __name__ == "__main__":
    main()
