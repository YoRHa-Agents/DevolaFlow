"""Verify the v8.3.0 Q-5 `agent_plus_specs` gitignore policy.

Per `.local/research/v8.3.0_design.md` §11.2 Q-5 (RESOLVED 2026-04-22) and
`.local/research/v8.3.0_patch_plan.md` §v8.2.4, `.gitignore` must:

* TRACK in git the union of:
  - the full `.local/.agent/` tree (active + handoff + archive + config)
  - `.local/memory/specs/` (source-of-truth specs per A-4 / M-004 ADR)
* Keep gitignored:
  - everything else under `.local/` (research, feedbacks, sandbox, etc.)
  - `.local/memory/operational.jsonl` (runtime learnings JSONL)
  - `.local/memory/session_state.json` (PV-03 unified session state)
  - `.local/memory/prefs.md` (personal preferences)
  - `.local/memory/plugin_install.log` (v8.2.1 plugin runtime log)
  - `.local/.agent/active/*/learnings.jsonl` (per-change learnings — secret)
  - `.local/.agent/archive/*/learnings.jsonl` (archived per-change learnings)

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
# Path tables — verbatim from .local/research/v8.3.0_design.md §11.2 Q-5 +
# .local/research/v8.3.0_patch_plan.md §v8.2.4 owned-files notes.
# -----------------------------------------------------------------------------

# Paths that MUST be tracked (re-included after the parent `.local/` ignore).
TRACKED_PATHS: list[str] = [
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
]

# Paths that MUST stay ignored (rest of `.local/` + secrets + per-change learnings).
IGNORED_PATHS: list[str] = [
    # rest of .local/ — research artifacts, feedbacks, scratch
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


# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------


@pytest.mark.parametrize("path", TRACKED_PATHS)
def test_paths_under_agent_and_specs_are_tracked(path: str) -> None:
    """v8.3.0 Q-5: paths under .local/.agent/ and .local/memory/specs/ are NOT ignored."""
    status, rule = _check_ignore(path)
    assert status == "TRACKED", (
        f"path {path!r} should be TRACKED per Q-5 agent_plus_specs policy, "
        f"but git matched ignore rule {rule!r}"
    )


@pytest.mark.parametrize("path", IGNORED_PATHS)
def test_secrets_and_legacy_paths_remain_ignored(path: str) -> None:
    """v8.3.0 Q-5: secrets + non-public `.local/` content stay gitignored."""
    status, rule = _check_ignore(path)
    assert status == "IGNORED", (
        f"path {path!r} should be IGNORED per Q-5 agent_plus_specs policy, "
        f"but git treats it as TRACKED (matching rule: {rule!r})"
    )


def test_gitignore_carries_the_q5_block() -> None:
    """The .gitignore file documents the Q-5 policy with a clear comment block."""
    text = GITIGNORE_PATH.read_text(encoding="utf-8")
    assert "v8.3.0 Q-5" in text, "missing Q-5 attribution comment"
    assert "agent_plus_specs" in text or "Q-5" in text, "missing Q-5 policy reference"
    assert "!.local/.agent/" in text, "missing un-ignore for .local/.agent/"
    assert "!.local/memory/specs/" in text, "missing un-ignore for .local/memory/specs/"


def test_gitignore_explicitly_re_ignores_secrets() -> None:
    """The Q-5 policy lists each secret/runtime file explicitly (defense in depth)."""
    text = GITIGNORE_PATH.read_text(encoding="utf-8")
    for sentinel in (
        ".local/memory/operational.jsonl",
        ".local/memory/session_state.json",
        ".local/memory/prefs.md",
        ".local/memory/plugin_install.log",
        ".local/.agent/active/*/learnings.jsonl",
        ".local/.agent/archive/*/learnings.jsonl",
    ):
        assert sentinel in text, f"missing re-ignore line: {sentinel}"


def test_gitignore_uses_local_star_not_local_dir() -> None:
    """Per gitignore docs we MUST use `.local/*` (contents) not `.local/` (dir)
    so that re-include patterns can take effect — ignoring the dir itself
    prevents Git from recursing in.
    """
    text = GITIGNORE_PATH.read_text(encoding="utf-8")
    lines = [ln.strip() for ln in text.splitlines()]
    # Look for the Q-5 block line that ignores .local/ contents.
    star_form_present = ".local/*" in lines
    bare_dir_form_present = ".local/" in lines
    assert star_form_present, "missing `.local/*` (contents-only ignore)"
    assert not bare_dir_form_present, (
        "`.local/` (bare dir) ignore would block re-include patterns; "
        "use `.local/*` instead per Q-5 implementation notes"
    )


def test_total_path_count_meets_ac9_minimum() -> None:
    """AC-9 mandates ≥ 8 test cases verifying ignore status; we cover 14 + 14 = 28."""
    assert len(TRACKED_PATHS) + len(IGNORED_PATHS) >= 8, (
        f"AC-9 requires ≥ 8 test cases; have {len(TRACKED_PATHS) + len(IGNORED_PATHS)}"
    )
    # Spot-check both buckets are non-trivial.
    assert len(TRACKED_PATHS) >= 4, "tracked path coverage too thin"
    assert len(IGNORED_PATHS) >= 4, "ignored path coverage too thin"


def test_no_overlap_between_tracked_and_ignored() -> None:
    """A path can't be both — sanity guard against future test maintenance bugs."""
    overlap = set(TRACKED_PATHS) & set(IGNORED_PATHS)
    assert not overlap, f"path appears in both buckets: {overlap}"


def test_gitignore_path_exists() -> None:
    """The .gitignore file is at the expected location."""
    assert GITIGNORE_PATH.is_file(), f".gitignore missing at {GITIGNORE_PATH}"


def test_gitignore_references_design_md_for_traceability() -> None:
    """The Q-5 block cites the design doc for future maintainers."""
    text = GITIGNORE_PATH.read_text(encoding="utf-8")
    assert "v8.3.0_design.md" in text, "missing design.md reference in gitignore comment"
    assert "v8.3.0_patch_plan.md" in text or "v8.2.4" in text, (
        "missing patch_plan.md / v8.2.4 reference in gitignore comment"
    )


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
