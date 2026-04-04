"""Repository mode detection.

Design ref: design_repo_modes.md §3
"""

from __future__ import annotations

import configparser
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class RepoMode:
    """Detected repository hosting mode."""

    mode: str  # local | github | other-git
    variant: str | None  # gitlab | gitea | bitbucket | generic (only for other-git)
    remote_url: str | None


def normalize_git_url(url: str) -> str:
    """Normalize SSH/HTTPS/ssh:// git URLs to a comparable form."""
    url = url.strip().removesuffix(".git")
    if url.startswith("git@"):
        url = url.removeprefix("git@")
    elif url.startswith("https://") or url.startswith("http://"):
        url = url.removeprefix("https://").removeprefix("http://")
    elif url.startswith("ssh://"):
        url = url.removeprefix("ssh://")
        if "@" in url:
            url = url.split("@", maxsplit=1)[1]
    return url.lower()


# Ordered list — first match wins
_PLATFORM_PATTERNS: list[tuple[str, str]] = [
    (r"github\.com[:/]", "github"),
    (r"gitlab\.com[:/]", "gitlab"),
    (r"gitlab\.[a-z]+\.[a-z]+[:/]", "gitlab"),
    (r"gitea\.", "gitea"),
    (r"forgejo\.", "gitea"),
    (r"codeberg\.org[:/]", "gitea"),
    (r"bitbucket\.org[:/]", "bitbucket"),
]


def match_platform(url: str) -> str:
    """Match a remote URL against known hosting platform patterns."""
    normalized = normalize_git_url(url)
    for pattern, platform in _PLATFORM_PATTERNS:
        if re.search(pattern, normalized):
            return platform
    return "generic"


def _parse_remotes_from_config(git_config_path: Path) -> dict[str, str]:
    """Parse .git/config to extract remote name→URL pairs."""
    parser = configparser.ConfigParser()
    parser.read(git_config_path)
    remotes: dict[str, str] = {}
    for section in parser.sections():
        if section.startswith('remote "') and section.endswith('"'):
            name = section[8:-1]
            if parser.has_option(section, "url"):
                remotes[name] = parser.get(section, "url")
    return remotes


def _detect_by_ci_config(repo_path: Path) -> str:
    """Fallback: infer platform from CI config files in the repo root."""
    if (repo_path / ".gitlab-ci.yml").exists():
        return "gitlab"
    if (repo_path / ".gitea" / "workflows").is_dir():
        return "gitea"
    if (repo_path / ".forgejo" / "workflows").is_dir():
        return "gitea"
    if (repo_path / "bitbucket-pipelines.yml").exists():
        return "bitbucket"
    if (repo_path / ".github" / "workflows").is_dir():
        return "github"
    return "generic"


def detect_repo_mode(repo_path: Path) -> RepoMode:
    """Auto-detect repository hosting mode from .git/config remote URLs.

    Falls back to CI config file heuristics when the URL is unrecognised.
    """
    git_dir = repo_path / ".git"
    if not git_dir.exists():
        return RepoMode(mode="local", variant=None, remote_url=None)

    git_config = git_dir / "config"
    remotes: dict[str, str] = {}
    if git_config.exists():
        remotes = _parse_remotes_from_config(git_config)

    if not remotes:
        return RepoMode(mode="local", variant=None, remote_url=None)

    remote_url = remotes.get("origin") or next(iter(remotes.values()))
    platform = match_platform(remote_url)

    if platform == "generic":
        ci_platform = _detect_by_ci_config(repo_path)
        if ci_platform != "generic":
            platform = ci_platform

    if platform == "github":
        return RepoMode(mode="github", variant=None, remote_url=remote_url)

    return RepoMode(mode="other-git", variant=platform, remote_url=remote_url)


def detect_and_print() -> None:
    """CLI entry point: detect repo mode and print result."""
    result = detect_repo_mode(Path.cwd())
    if result.variant:
        print(f"{result.mode} ({result.variant})")
    else:
        print(result.mode)
    if result.remote_url:
        print(f"Remote: {result.remote_url}")
