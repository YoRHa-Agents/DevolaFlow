"""Verify the private `.local/` gitignore policy.

The DevolaFlow local workspace is runtime/planning state and must stay out of
git as a whole. `.gitignore` therefore carries one broad `.local/` rule and no
legacy Q-5 re-include rules for `.local/.agent/**` or `.local/memory/specs/**`.

Detection note: `git check-ignore -v` prints the matching rule for ANY pattern
hit (negation rules included) and exits 0 in BOTH cases, so the test parses
the rule prefix `!` to determine whether a path is ultimately TRACKED (rule
starts with `!`) or IGNORED (matching rule does NOT start with `!`).
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Literal

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
GITIGNORE_PATH = REPO_ROOT / ".gitignore"


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


def _check_ignore(path: str) -> tuple[Literal["IGNORED", "TRACKED"], str]:
    """Return (status, matching_rule_text) for the given path.

    Status semantics:
      * "TRACKED" — no rule matched OR a negation rule (`!`-prefixed) matched
      * "IGNORED" — a non-negation rule matched

    The matching_rule_text is the verbatim rule (sans line number) that git
    reported, or "<no match>" when no rule matched.
    """
    result = subprocess.run(
        ["git", "check-ignore", "-v", "--no-index", path],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 1 and not result.stdout:
        # No rule matched — file is implicitly tracked.
        return ("TRACKED", "<no match>")
    # Format: "<gitignore-file>:<line>:<rule>\t<path>"
    line = result.stdout.strip().split("\n")[0]
    parts = line.split("\t")[0].split(":", 2)
    if len(parts) != 3:
        return ("IGNORED" if result.returncode == 0 else "TRACKED", line)
    rule = parts[2]
    if rule.startswith("!"):
        # Negation rule matched — file is RE-INCLUDED (tracked).
        return ("TRACKED", rule)
    return ("IGNORED", rule)


# -----------------------------------------------------------------------------
# Path tables for the private `.local/` policy.
# -----------------------------------------------------------------------------

# Paths under `.local/` that MUST stay ignored, including the formerly
# re-included Q-5 subtrees.
LOCAL_PRIVATE_PATHS: list[str] = [
    ".local/.agent/config.yaml",
    ".local/.agent/active/test/goal.md",
    ".local/.agent/active/test/acceptance.md",
    ".local/.agent/active/test/spec.md",
    ".local/.agent/active/test/tasks.md",
    ".local/.agent/active/test/STATUS.yaml",
    ".local/.agent/active/test/owned_files.txt",
    ".local/.agent/handoff/L0__L1__test__0001.yaml",
    ".local/.agent/handoff/L1__L3__test__0002.yaml",
    ".local/.agent/archive/2026-04-22-test/spec.md",
    ".local/.agent/archive/2026-04-22-test/REPORT.md",
    ".local/.agent/archive/2026-04-22-test/handoff_chain.yaml",
    ".local/memory/specs/auth/spec.md",
    ".local/memory/specs/agent_workspace/spec.md",
    ".local/research/v8.3.0_gap_analysis.md",
    ".local/research/v7.5.0_ghost_audit.md",
    ".local/feedbacks/feedback_for_v8.2.0.md",
    ".local/feedbacks/TRACKER.md",
    ".local/sandbox/scratch.md",
    ".local/podcast/episode01.md",
    ".local/index.md",
    ".local/designs/T04-advisor-integration-designs.md",
    # memory secrets — explicitly re-ignored after the .local/memory/ un-ignore
    ".local/memory/operational.jsonl",
    ".local/memory/session_state.json",
    ".local/memory/prefs.md",
    ".local/memory/plugin_install.log",
    # per-change learnings — explicitly re-ignored even under the public subtree
    ".local/.agent/active/foo/learnings.jsonl",
    ".local/.agent/archive/2026-04-22-foo/learnings.jsonl",
]

# Control paths outside `.local/` keep the helper's "no rule means tracked"
# behavior pinned.
TRACKED_CONTROL_PATHS: list[str] = [
    "pyproject.toml",
    "src/devolaflow/local/workspace.py",
    "tests/test_gitignore_policy.py",
]

LEGACY_LOCAL_WHITELIST_RULES: tuple[str, ...] = (
    ".local/*",
    "!.local/.agent/",
    "!.local/.agent/**",
    "!.local/memory/",
    ".local/memory/*",
    "!.local/memory/specs/",
    "!.local/memory/specs/**",
)


# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------


@pytest.mark.parametrize("path", LOCAL_PRIVATE_PATHS)
def test_all_local_paths_are_ignored(path: str) -> None:
    """The full `.local/` tree is private, including `.agent` and `memory/specs`."""
    status, rule = _check_ignore(path)
    assert status == "IGNORED", (
        f"path {path!r} should be IGNORED by the private .local/ policy, "
        f"but git treats it as TRACKED (matching rule: {rule!r})"
    )
    assert rule == ".local/", f"path {path!r} should be covered by the broad .local/ rule"


@pytest.mark.parametrize("path", TRACKED_CONTROL_PATHS)
def test_non_local_control_paths_are_tracked(path: str) -> None:
    """Guard helper semantics: paths without matching ignore rules are tracked."""
    status, rule = _check_ignore(path)
    assert status == "TRACKED", (
        f"non-local control path {path!r} should remain TRACKED, "
        f"but git matched ignore rule {rule!r}"
    )


def test_gitignore_uses_broad_local_dir_rule() -> None:
    """The private policy uses `.local/`, not the old re-include-friendly `.local/*`."""
    text = GITIGNORE_PATH.read_text(encoding="utf-8")
    lines = [ln.strip() for ln in text.splitlines()]
    assert ".local/" in lines, "missing broad `.local/` private workspace rule"
    assert ".local/*" not in lines, "legacy `.local/*` re-include scaffold must be removed"


def test_gitignore_has_no_legacy_local_whitelist_rules() -> None:
    """The legacy Q-5 tracked-subtree whitelist block must not reappear."""
    text = GITIGNORE_PATH.read_text(encoding="utf-8")
    lines = [ln.strip() for ln in text.splitlines()]
    present = sorted(rule for rule in LEGACY_LOCAL_WHITELIST_RULES if rule in lines)
    assert present == [], f"legacy .local whitelist rules remain: {present!r}"


def test_total_path_count_meets_ac9_minimum() -> None:
    """AC-9 mandates ≥ 8 test cases verifying ignore status."""
    assert len(LOCAL_PRIVATE_PATHS) >= 8, (
        f"AC-9 requires ≥ 8 ignored .local test cases; have {len(LOCAL_PRIVATE_PATHS)}"
    )
    assert len(TRACKED_CONTROL_PATHS) >= 2, "tracked control path coverage too thin"


def test_no_overlap_between_tracked_and_ignored() -> None:
    """A path can't be both — sanity guard against future test maintenance bugs."""
    overlap = set(TRACKED_CONTROL_PATHS) & set(LOCAL_PRIVATE_PATHS)
    assert not overlap, f"path appears in both buckets: {overlap}"


def test_gitignore_path_exists() -> None:
    """The .gitignore file is at the expected location."""
    assert GITIGNORE_PATH.is_file(), f".gitignore missing at {GITIGNORE_PATH}"


def test_gitignore_documents_private_local_policy() -> None:
    """The .gitignore file labels `.local/` as private workspace state."""
    text = GITIGNORE_PATH.read_text(encoding="utf-8")
    assert "DevolaFlow local workspace (private)" in text


def test_real_existing_research_file_still_ignored() -> None:
    """Spot-check: an actual file currently on disk under `.local/research/` is ignored."""
    target = REPO_ROOT / ".local/research/v8.3.0_design.md"
    if not target.exists():
        pytest.skip("v8.3.0_design.md not present (run from a clean checkout?)")
    status, rule = _check_ignore(".local/research/v8.3.0_design.md")
    assert status == "IGNORED", (
        f".local/research/v8.3.0_design.md unexpectedly TRACKED (rule: {rule!r})"
    )


def test_real_existing_memory_log_still_ignored() -> None:
    """Spot-check: the actual `.local/memory/plugin_install.log` is ignored."""
    target = REPO_ROOT / ".local/memory/plugin_install.log"
    if not target.exists():
        pytest.skip(".local/memory/plugin_install.log not present in this checkout")
    status, rule = _check_ignore(".local/memory/plugin_install.log")
    assert status == "IGNORED", (
        f".local/memory/plugin_install.log unexpectedly TRACKED (rule: {rule!r})"
    )
