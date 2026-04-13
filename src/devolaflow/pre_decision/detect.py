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


# ── URL normalisation ────────────────────────────────────────────────────


def _strip_ssh_user(url: str) -> str:
    """Strip ``ssh://`` prefix and optional ``user@`` from URL."""
    url = url.removeprefix("ssh://")
    if "@" in url:
        url = url.split("@", maxsplit=1)[1]
    return url


def _strip_scheme(url: str) -> str:
    """Strip known URL scheme prefixes, returning the host+path portion."""
    for prefix in ("git@", "https://", "http://"):
        if url.startswith(prefix):
            return url.removeprefix(prefix)
    if url.startswith("ssh://"):
        return _strip_ssh_user(url)
    return url


def normalize_git_url(url: str) -> str:
    """Normalize SSH/HTTPS/ssh:// git URLs to a comparable form."""
    url = url.strip().removesuffix(".git")
    return _strip_scheme(url).lower()


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


# ── Git config helpers ───────────────────────────────────────────────────


def _is_remote_section(section: str) -> bool:
    """True when *section* is a ``[remote "..."]`` git-config section."""
    return section.startswith('remote "') and section.endswith('"')


def _parse_remotes_from_config(git_config_path: Path) -> dict[str, str]:
    """Parse .git/config to extract remote name->URL pairs."""
    parser = configparser.ConfigParser()
    parser.read(git_config_path)
    return {
        section[8:-1]: parser.get(section, "url")
        for section in parser.sections()
        if _is_remote_section(section)
        if parser.has_option(section, "url")
    }


# ── CI config fallback ──────────────────────────────────────────────────

_CI_CONFIG_MARKERS: list[tuple[str, str, bool]] = [
    (".gitlab-ci.yml", "gitlab", False),
    (".gitea/workflows", "gitea", True),
    (".forgejo/workflows", "gitea", True),
    ("bitbucket-pipelines.yml", "bitbucket", False),
    (".github/workflows", "github", True),
]


def _detect_by_ci_config(repo_path: Path) -> str:
    """Fallback: infer platform from CI config files in the repo root."""
    for rel_path, platform, check_dir in _CI_CONFIG_MARKERS:
        candidate = repo_path / rel_path
        if candidate.is_dir() if check_dir else candidate.exists():
            return platform
    return "generic"


# ── Repo mode detection ─────────────────────────────────────────────────


def _load_remotes(git_dir: Path) -> dict[str, str]:
    """Load remote URLs from .git/config, returning empty dict if absent."""
    git_config = git_dir / "config"
    if git_config.exists():
        return _parse_remotes_from_config(git_config)
    return {}


def _pick_remote_url(remotes: dict[str, str]) -> str:
    """Pick the canonical remote URL, preferring 'origin'."""
    if "origin" in remotes:
        return remotes["origin"]
    return next(iter(remotes.values()))


def _resolve_platform(remote_url: str, repo_path: Path) -> str:
    """Resolve platform from remote URL, falling back to CI config heuristics."""
    platform = match_platform(remote_url)
    if platform == "generic":
        ci_platform = _detect_by_ci_config(repo_path)
        if ci_platform != "generic":
            return ci_platform
    return platform


def detect_repo_mode(repo_path: Path) -> RepoMode:
    """Auto-detect repository hosting mode from .git/config remote URLs.

    Falls back to CI config file heuristics when the URL is unrecognised.
    """
    git_dir = repo_path / ".git"
    if not git_dir.exists():
        return RepoMode(mode="local", variant=None, remote_url=None)

    remotes = _load_remotes(git_dir)
    if not remotes:
        return RepoMode(mode="local", variant=None, remote_url=None)

    remote_url = _pick_remote_url(remotes)
    platform = _resolve_platform(remote_url, repo_path)

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
