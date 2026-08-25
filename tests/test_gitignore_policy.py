"""Verify the v12.2.0 selective whitelist `.local/` gitignore policy.

Closes `.local/feedbacks/feedback_for_v12.1.0.md`: the DevolaFlow local
workspace is private by default, but two team-collab subdirs are explicitly
tracked under git so PR reviewers see them mid-cycle:

* `.local/memory/specs/` — A-4 source-of-truth contracts (per Rule A-4)
* `.local/research/`     — narrowed by clean_repo Phase A + B2 + C1-1:
                            only current-cycle (v15*) research stays
                            tracked; archived history (incl. all ADRs)
                            lives in docs/cycle-archive/ (W-19)

Everything else under `.local/` stays private (machine state, scratch dirs,
per-developer change folders, handoff envelopes).

Supersedes the v9.2.3 PV-02 broad `.local/` rule. The v12.2.0 whitelist
block is written by `devolaflow.local.workspace.ensure_local_gitignore`
and the DevolaFlow source repo itself adopts it.

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
# Path tables for the v12.2.0 selective whitelist policy.
# -----------------------------------------------------------------------------

# Paths under `.local/` that MUST stay IGNORED (private — not on the whitelist).
LOCAL_PRIVATE_PATHS: list[str] = [
    ".local/.agent/config.yaml",
    ".local/.agent/active/test/goal.md",
    ".local/.agent/active/test/checklist.md",
    ".local/.agent/active/test/spec.md",
    ".local/.agent/active/test/stage.md",
    ".local/.agent/active/test/STATUS.yaml",
    ".local/.agent/active/test/owned_files.txt",
    ".local/.agent/handoff/L0__L1__test__0001.yaml",
    ".local/.agent/handoff/L1__L3__test__0002.yaml",
    ".local/.agent/archive/2026-04-22-test/spec.md",
    ".local/.agent/archive/2026-04-22-test/REPORT.md",
    ".local/.agent/archive/2026-04-22-test/handoff_chain.yaml",
    ".local/feedbacks/feedback_for_v8.2.0.md",
    ".local/feedbacks/TRACKER.md",
    ".local/tasks/example_task.md",
    ".local/sandbox/scratch.md",
    ".local/podcast/episode01.md",
    ".local/index.md",
    ".local/designs/T04-advisor-integration-designs.md",
    # memory secrets — covered by `.local/memory/*` (NOT re-enabled, since
    # only `.local/memory/specs/` carries a negation rule).
    ".local/memory/operational.jsonl",
    ".local/memory/session_state.json",
    ".local/memory/prefs.md",
    ".local/memory/plugin_install.log",
    # per-change learnings — under .agent/active/ which has no negation
    ".local/.agent/active/foo/learnings.jsonl",
    ".local/.agent/archive/2026-04-22-foo/learnings.jsonl",
]

# Paths under `.local/` that MUST be TRACKED via the v12.2.0 whitelist
# (the negation rules re-enable these specific subtrees).
LOCAL_WHITELISTED_PATHS: list[str] = [
    # A-4 source-of-truth contracts — re-enabled via !.local/memory/specs/**
    ".local/memory/specs/auth/spec.md",
    ".local/memory/specs/agent_workspace/spec.md",
    ".local/memory/specs/example_domain/spec.md",
    # W-7/W-19 research artifacts — narrowed by clean_repo Phase A + B2 +
    # C1-1: only current-cycle v15* loose files (via !.local/research/v15*)
    # stay re-enabled; the 2 formerly hard-read v15 ADRs moved to the
    # archived bucket once Phase C1-1 landed the ghost-test archive fallback.
    ".local/research/v15.0.0_retrospective.md",
    # v14.0.0 — human INPUT zone (authoritative, durable, PR-reviewable)
    # re-enabled via !.local/human/input/** (D-4 / ADR-2). output/ + archive/
    # stay PRIVATE (D2 locked) — see LOCAL_HUMAN_PRIVATE_PATHS below.
    ".local/human/input/constitution.md",
    ".local/human/input/requirements.md",
    ".local/human/input/amendments/2026-06-03-immutable-input.md",
]

# clean_repo Phase A + B2 + C1-1 — archived research files are IGNORED
# after the whitelist narrowings (their canonical copies live in
# docs/cycle-archive/; local files are kept but no longer tracked). C1-1
# drops the last 2 adr/ negations: the whole adr/ subtree now falls under
# `.local/research/*` (the 2 v15 hard-read ADRs resolve via the W-18
# archive fallback in tests/ghost/_helpers.py).
LOCAL_RESEARCH_ARCHIVED_PRIVATE_PATHS: list[str] = [
    ".local/research/v8.3.0_gap_analysis.md",
    ".local/research/v7.5.0_ghost_audit.md",
    ".local/research/v12.2.0_gap_analysis.md",
    ".local/research/v8.3.0_design.md",
    ".local/research/adr/v9-ADR-002-cache-layout-governance-v2.md",
    ".local/research/adr/v15-ADR-002-template-phase-b-collapse.md",
    ".local/research/adr/v15-ADR-006-scorer-selector-module-split.md",
]

# v14.0.0 — human OUTPUT + archive zones MUST stay IGNORED (D2 operator
# decision: bounded reports + dated snapshots are local-only, not PR-visible).
# The `.local/human/*` re-exclusion line keeps them private while INPUT is
# tracked. Asserted via the dedicated `test_human_output_zone_stays_private`
# (NOT folded into LOCAL_PRIVATE_PATHS, whose matching-rule assertion is
# specific to `.local/*` / `.local/memory/*`).
LOCAL_HUMAN_PRIVATE_PATHS: list[str] = [
    ".local/human/output/DIGEST.md",
    ".local/human/output/convergence/v14.0.0-convergence.md",
    ".local/human/archive/2026-06-03-superseded-req/spec.md",
]

# Control paths outside `.local/` keep the helper's "no rule means tracked"
# behavior pinned.
TRACKED_CONTROL_PATHS: list[str] = [
    "pyproject.toml",
    "src/devolaflow/local/workspace.py",
    "tests/test_gitignore_policy.py",
]

# v12.2.0 whitelist block — the required positive rules that the
# `ensure_local_gitignore` write surface emits. The 4th rule `!.local/human/`
# (v14.0.0) re-includes the human dir so the `!.local/human/input/**` negation
# can track the INPUT zone (D-4 / ADR-2); it is the detection key the repair
# path uses to graduate older (pre-v14.0.0) whitelists.
V12_2_0_WHITELIST_REQUIRED_RULES: tuple[str, ...] = (
    ".local/*",
    "!.local/memory/specs/",
    "!.local/research/",
    "!.local/human/",
)

# v9.2.3 PV-02 broad rule — superseded; MUST NOT appear in the source repo.
V92_LEGACY_BROAD_RULE: str = ".local/"

# Pre-v9.2.3 legacy whitelist re-include rules — superseded; MUST NOT reappear.
# Note: `!.local/memory/` IS in the v12.2.0 whitelist as a stepping-stone for
# the `!.local/memory/specs/` re-include, so it's not in this superseded list.
# The legacy `!.local/.agent/**` rules ARE superseded because the user
# explicitly chose NOT to track `.agent/active/` etc. in the v12.2.0 fix
# (per `.local/feedbacks/feedback_for_v12.1.0.md`).
LEGACY_LOCAL_WHITELIST_RULES: tuple[str, ...] = (
    "!.local/.agent/",
    "!.local/.agent/**",
)


# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------


@pytest.mark.parametrize("path", LOCAL_PRIVATE_PATHS)
def test_all_local_paths_are_ignored(path: str) -> None:
    """Non-whitelisted `.local/` paths stay IGNORED under v12.2.0 policy.

    The v12.2.0 whitelist tracks `.local/memory/specs/` + `.local/research/`
    via negation rules. Everything else under `.local/` is covered by the
    `.local/*` (or `.local/memory/*`) broad rules.
    """
    status, rule = _check_ignore(path)
    assert status == "IGNORED", (
        f"path {path!r} should be IGNORED by the v12.2.0 selective whitelist "
        f"policy, but git treats it as TRACKED (matching rule: {rule!r})"
    )
    # The matching rule MUST be one of the v12.2.0 whitelist's positive
    # ignore rules (`.local/*` or `.local/memory/*`) — NOT the v9.2.3 broad
    # `.local/` rule (which the source repo has graduated away from).
    assert rule in (".local/*", ".local/memory/*"), (
        f"path {path!r}: matched unexpected rule {rule!r}; expected v12.2.0 "
        f"whitelist positive rule (.local/* or .local/memory/*)"
    )


@pytest.mark.parametrize("path", LOCAL_WHITELISTED_PATHS)
def test_whitelisted_local_paths_are_tracked(path: str) -> None:
    """v12.2.0 team-collab subdirs (`.local/memory/specs/` + `.local/research/`) stay TRACKED.

    Closes `.local/feedbacks/feedback_for_v12.1.0.md` — the user wants
    A-4 source-of-truth contracts + W-7/W-19 research artifacts visible
    to teammates mid-cycle without `git add -f` workarounds.
    """
    status, rule = _check_ignore(path)
    assert status == "TRACKED", (
        f"path {path!r} should be TRACKED by the v12.2.0 whitelist negation "
        f"rule, but git treats it as IGNORED (matching rule: {rule!r})"
    )
    # The negation rule MUST be one of the whitelist's negation rules:
    # `!.local/memory/specs/**`, `!.local/research/**`, or the v14.0.0
    # `!.local/human/input/**` (INPUT-only — D-4 / ADR-2).
    assert (
        rule.startswith("!.local/memory/specs/")
        or rule.startswith("!.local/research/")
        or rule.startswith("!.local/human/")
    ), (
        f"path {path!r}: matched unexpected negation rule {rule!r}; expected "
        f"a whitelist negation (`!.local/memory/specs/**`, `!.local/research/**`, "
        f"or `!.local/human/input/**`)"
    )


@pytest.mark.parametrize("path", LOCAL_RESEARCH_ARCHIVED_PRIVATE_PATHS)
def test_archived_research_paths_are_ignored(path: str) -> None:
    """clean_repo Phase A + B2 + C1-1：已归档 research（含全部 adr/）改为 IGNORED。"""
    status, rule = _check_ignore(path)
    assert status == "IGNORED"
    assert rule == ".local/research/*"


@pytest.mark.parametrize("path", LOCAL_HUMAN_PRIVATE_PATHS)
def test_human_output_zone_stays_private(path: str) -> None:
    """v14.0.0 D2: `.local/human/output/` + `archive/` stay IGNORED.

    The operator locked INPUT-only git tracking (ADR-2): the authoritative
    `.local/human/input/**` zone is re-included, but the bounded (C-9-capped)
    convergence reports + digest in `output/` and the dated snapshots in
    `archive/` are local-only, NOT PR-visible. The `.local/human/*`
    re-exclusion line keeps them private even though `!.local/human/`
    re-includes the parent dir.
    """
    status, rule = _check_ignore(path)
    assert status == "IGNORED", (
        f"path {path!r} must stay IGNORED (D2 locked: output/ + archive/ are "
        f"private), but git treats it as TRACKED (matching rule: {rule!r})"
    )
    assert rule == ".local/human/*", (
        f"path {path!r}: expected the `.local/human/*` re-exclusion to keep the "
        f"OUTPUT/archive zone private, but matched {rule!r}"
    )


@pytest.mark.parametrize("path", TRACKED_CONTROL_PATHS)
def test_non_local_control_paths_are_tracked(path: str) -> None:
    """Guard helper semantics: paths without matching ignore rules are tracked."""
    status, rule = _check_ignore(path)
    assert status == "TRACKED", (
        f"non-local control path {path!r} should remain TRACKED, "
        f"but git matched ignore rule {rule!r}"
    )


def test_gitignore_uses_v12_2_0_whitelist_block() -> None:
    """v12.2.0 PV-02: `.gitignore` carries the 3 required positive rules.

    The v12.2.0 whitelist supersedes the v9.2.3 broad `.local/` rule. The
    source repo MUST demonstrate the same pattern it teaches consumer repos
    (per the W-18 v12.2.0 ghost-audit stanza).
    """
    text = GITIGNORE_PATH.read_text(encoding="utf-8")
    lines = [ln.strip() for ln in text.splitlines()]
    for required_rule in V12_2_0_WHITELIST_REQUIRED_RULES:
        assert required_rule in lines, (
            f"missing v12.2.0 whitelist rule {required_rule!r}; the source "
            f"repo MUST adopt the whitelist alongside the consumer-repo "
            f"helper code (per `.local/feedbacks/feedback_for_v12.1.0.md`)"
        )
    assert V92_LEGACY_BROAD_RULE not in lines, (
        f"legacy v9.2.3 broad `{V92_LEGACY_BROAD_RULE}` rule must be stripped "
        f"during v12.2.0 PV-02 graduation"
    )


def test_gitignore_has_no_legacy_local_whitelist_rules() -> None:
    """Pre-v9.2.3 tracked-subtree whitelist block must not reappear."""
    text = GITIGNORE_PATH.read_text(encoding="utf-8")
    lines = [ln.strip() for ln in text.splitlines()]
    present = sorted(rule for rule in LEGACY_LOCAL_WHITELIST_RULES if rule in lines)
    assert present == [], (
        f"pre-v9.2.3 legacy .local whitelist rules must NOT reappear: {present!r}. "
        f"The v12.2.0 whitelist is the only sanctioned re-include block; "
        f".agent/* + memory/ (non-specs) stay private per the v12.1.0 feedback."
    )


def test_total_path_count_meets_ac9_minimum() -> None:
    """AC-9 mandates ≥ 8 test cases verifying ignore status."""
    assert len(LOCAL_PRIVATE_PATHS) >= 8, (
        f"AC-9 requires ≥ 8 ignored .local test cases; have {len(LOCAL_PRIVATE_PATHS)}"
    )
    assert len(LOCAL_WHITELISTED_PATHS) >= 4, (
        f"v12.2.0 whitelist requires ≥ 4 tracked .local test cases (2 specs "
        f"domains + 2 research artifacts); have {len(LOCAL_WHITELISTED_PATHS)}"
    )
    assert len(TRACKED_CONTROL_PATHS) >= 2, "tracked control path coverage too thin"


def test_no_overlap_between_tracked_and_ignored() -> None:
    """A path can't be both — sanity guard against future test maintenance bugs."""
    all_tracked = set(TRACKED_CONTROL_PATHS) | set(LOCAL_WHITELISTED_PATHS)
    overlap = all_tracked & set(LOCAL_PRIVATE_PATHS)
    assert not overlap, f"path appears in both tracked and ignored buckets: {overlap}"


def test_gitignore_path_exists() -> None:
    """The .gitignore file is at the expected location."""
    assert GITIGNORE_PATH.is_file(), f".gitignore missing at {GITIGNORE_PATH}"


def test_gitignore_documents_v12_2_0_whitelist_policy() -> None:
    """The .gitignore file labels `.local/` as whitelist-tracked workspace state."""
    text = GITIGNORE_PATH.read_text(encoding="utf-8")
    assert "DevolaFlow local workspace (whitelist team-collab subdirs" in text, (
        "v12.2.0 banner missing — `.gitignore` must document the selective "
        "whitelist policy that supersedes the v9.2.3 broad `.local/` rule"
    )
    assert "feedback_for_v12.1.0.md" in text, (
        "v12.2.0 banner must cite the v12.1.0 feedback that motivated the fix"
    )


def test_real_existing_research_file_now_tracked() -> None:
    """Spot-check: an actual file currently on disk under `.local/research/` is TRACKED.

    Inverted from the v9.2.3 expectation — under v12.2.0, research artifacts
    are visible to PR reviewers mid-cycle. The matching negation rule
    `!.local/research/v15*` re-includes the file.
    """
    target = REPO_ROOT / ".local/research/v15.0.0_retrospective.md"
    if not target.exists():
        pytest.skip("v15.0.0_retrospective.md not present (run from a clean checkout?)")
    status, rule = _check_ignore(".local/research/v15.0.0_retrospective.md")
    assert status == "TRACKED", (
        f".local/research/v15.0.0_retrospective.md unexpectedly IGNORED under v12.2.0 "
        f"whitelist (rule: {rule!r}). The negation `!.local/research/v15*` MUST "
        f"re-include the file."
    )


def test_real_existing_memory_log_still_ignored() -> None:
    """Spot-check: the actual `.local/memory/plugin_install.log` stays ignored.

    Confirms the v12.2.0 whitelist does NOT accidentally leak machine logs
    via the `.local/memory/*` ignore (only `.local/memory/specs/` is re-enabled).
    """
    target = REPO_ROOT / ".local/memory/plugin_install.log"
    if not target.exists():
        pytest.skip(".local/memory/plugin_install.log not present in this checkout")
    status, rule = _check_ignore(".local/memory/plugin_install.log")
    assert status == "IGNORED", (
        f".local/memory/plugin_install.log unexpectedly TRACKED (rule: {rule!r}); "
        f"the v12.2.0 whitelist intentionally re-ignores everything under "
        f"`.local/memory/` except the `specs/` subtree"
    )


def test_real_existing_memory_specs_dir_tracked_when_present() -> None:
    """Spot-check: if `.local/memory/specs/<domain>/spec.md` exists, it's TRACKED."""
    target = REPO_ROOT / ".local/memory/specs"
    if not target.exists():
        pytest.skip(".local/memory/specs/ not yet populated in this checkout")
    # Pick any spec file under specs/
    spec_files = list(target.rglob("spec.md"))
    if not spec_files:
        pytest.skip(".local/memory/specs/ exists but no spec.md files yet")
    rel = spec_files[0].relative_to(REPO_ROOT).as_posix()
    status, rule = _check_ignore(rel)
    assert status == "TRACKED", (
        f"{rel!r} unexpectedly IGNORED under v12.2.0 whitelist (rule: {rule!r}); "
        f"the negation `!.local/memory/specs/**` MUST re-include the file"
    )
