"""v12.2.0 PV-02 — `scaffold_local` writes / repairs the `.local/` whitelist.

Closes `.local/feedbacks/feedback_for_v12.1.0.md`: "everything under .local/
except necessary git-repo / team-collaboration content should be properly
ignored". The selective whitelist tracks `.local/memory/specs/` (A-4
source-of-truth contracts) and `.local/research/` (W-7 / W-19 retrospective
artifacts), while keeping all other `.local/` content private.

These tests supersede the v9.2.3 PV-02 broad-ignore semantics (preserved
in module-level constants for backward-compat with consumer repos that have
not yet re-run `devola-init local`). The W-18 ghost-audit pin in
`tests/test_no_ghost_features.py::test_v9_2_3_new_symbols_have_coverage`
still relies on this file having >= 5 test functions and the public
`_audit_gitignore_coverage` + `last_gitignore_audit` symbols.

Source artefacts:

* `.local/feedbacks/feedback_for_v12.1.0.md` (v12.2.0 cycle input)
* `.local/research/v12.2.0_gap_analysis.md` §2 D-1 (decomposition)
* `.local/research/v9.2.2_gap_analysis.md` §2 PV-02 (predecessor for `_OLD_LOCAL_WHITELIST_RULES`)
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from devolaflow.local.workspace import (
    _LOCAL_WHITELIST_BLOCK_LINES,
    _LOCAL_WHITELIST_REQUIRED_RULES,
    _path_matches_gitignore,
    _read_gitignore_rules,
    ensure_local_gitignore,
    last_gitignore_audit,
    scaffold_local,
)


@pytest.fixture
def tmp_repo(tmp_path: Path) -> Path:
    """Return an isolated tmp_path acting as a fresh repo root."""
    return tmp_path


def _scaffold_warnings(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    """Return the WARNING records emitted by ``scaffold_local``'s audit."""
    return [
        record
        for record in caplog.records
        if record.name == "devolaflow.local.workspace" and record.levelno == logging.WARNING
    ]


def _whitelist_lines() -> list[str]:
    """Return the canonical v12.2.0 whitelist block as a list of lines."""
    return list(_LOCAL_WHITELIST_BLOCK_LINES)


def _fresh_scaffold_lines() -> list[str]:
    """Return the full expected fresh-repo `.gitignore` (Track C-1 contract).

    The v12.2.0 whitelist block, then the deterministic scaffold-entries
    block written by `ensure_gitignore_entries`.
    """
    from devolaflow.local.workspace import _SCAFFOLD_ENTRIES_HEADER, SCAFFOLD_GITIGNORE_ENTRIES

    return (
        list(_LOCAL_WHITELIST_BLOCK_LINES)
        + ["", _SCAFFOLD_ENTRIES_HEADER]
        + list(SCAFFOLD_GITIGNORE_ENTRIES)
    )


def test_no_gitignore_writes_v12_2_0_whitelist_block(
    tmp_repo: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Without a `.gitignore` scaffold creates one with the v12.2.0 whitelist.

    The default rules track `.local/memory/specs/` (A-4) + `.local/research/`
    (W-7/W-19) and keep every other `.local/` subdir private. ZERO warnings
    on a fresh repo (no narrow rules to repair). Since Track C-1 the file
    """
    caplog.set_level(logging.WARNING, logger="devolaflow.local.workspace")
    assert not (tmp_repo / ".gitignore").exists(), "fixture precondition"

    scaffold_local(tmp_repo)

    actual_lines = (tmp_repo / ".gitignore").read_text(encoding="utf-8").splitlines()
    expected_lines = _fresh_scaffold_lines()
    assert actual_lines == expected_lines, (
        f"fresh-repo contract: scaffold must write the v12.2.0 whitelist block "
        f"+ the Track C-1 scaffold-entries block verbatim "
        f"(got {actual_lines!r}, expected {expected_lines!r})"
    )
    warnings = _scaffold_warnings(caplog)
    assert warnings == [], (
        f"fresh-repo contract: a new whitelist must emit ZERO WARNINGs (got "
        f"{[w.getMessage() for w in warnings]!r})"
    )
    assert last_gitignore_audit() == [], (
        "audit cache must be empty when the v12.2.0 whitelist is present"
    )


def test_gitignore_without_local_rule_appends_v12_2_0_block(
    tmp_repo: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """An unrelated `.gitignore` is extended with the v12.2.0 whitelist."""
    caplog.set_level(logging.WARNING, logger="devolaflow.local.workspace")
    (tmp_repo / ".gitignore").write_text(
        "# unrelated rules — none touch .local/\nbuild/\ndist/\n*.pyc\n",
        encoding="utf-8",
    )

    scaffold_local(tmp_repo)

    rules = _read_gitignore_rules(tmp_repo)
    for required in _LOCAL_WHITELIST_REQUIRED_RULES:
        assert required in rules, (
            f"v12.2.0 whitelist contract: rule {required!r} must be present "
            f"after scaffold (got {rules!r})"
        )
    warnings = _scaffold_warnings(caplog)
    assert warnings == [], (
        f"unrelated rules must not trigger warnings when the whitelist is "
        f"appended (got {[w.getMessage() for w in warnings]!r})"
    )
    assert last_gitignore_audit() == [], (
        "audit cache must be empty when the v12.2.0 whitelist is present"
    )


def test_v9_2_3_broad_local_rule_is_repaired_to_whitelist(
    tmp_repo: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The v9.2.3 broad `.local/` rule is graduated to the v12.2.0 whitelist.

    Closes the v12.1.0 feedback: a repo that ran `devola-init local` against
    v9.2.3..v12.1.0 carries a broad `.local/` line that hides specs +
    research from teammates. Running scaffold under v12.2.0 strips that
    rule and writes the selective whitelist.
    """
    caplog.set_level(logging.INFO, logger="devolaflow.local.workspace")
    (tmp_repo / ".gitignore").write_text(
        "# DevolaFlow local workspace (private)\n.local/\n",
        encoding="utf-8",
    )

    scaffold_local(tmp_repo)

    rules = _read_gitignore_rules(tmp_repo)
    assert ".local/" not in rules, (
        f"v9.2.3 broad rule must be stripped during repair (got {rules!r})"
    )
    for required in _LOCAL_WHITELIST_REQUIRED_RULES:
        assert required in rules, (
            f"v12.2.0 whitelist contract: rule {required!r} must replace the "
            f"v9.2.3 broad ignore (got {rules!r})"
        )
    repair_logs = [
        record.getMessage()
        for record in caplog.records
        if record.name == "devolaflow.local.workspace" and record.levelno == logging.INFO
    ]
    assert any("v9.2.3 broad .local/ rule" in msg for msg in repair_logs), (
        f"repair path MUST log an explicit INFO citing the v9.2.3 graduation "
        f"so operators understand why their .gitignore changed (got {repair_logs!r})"
    )


def test_legacy_local_whitelist_block_is_graduated_to_v12_2_0(
    tmp_repo: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Pre-v9.2.3 multi-line whitelist is collapsed + graduated to v12.2.0."""
    caplog.set_level(logging.INFO, logger="devolaflow.local.workspace")
    (tmp_repo / ".gitignore").write_text(
        "\n".join(
            [
                ".local/*",
                "!.local/.agent/",
                "!.local/.agent/**",
                "!.local/memory/",
                ".local/memory/*",
                "!.local/memory/specs/",
                "!.local/memory/specs/**",
                ".local/.agent/active/*/learnings.jsonl",
                ".local/.agent/archive/*/learnings.jsonl",
                ".local/memory/operational.jsonl",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    scaffold_local(tmp_repo)

    rules = _read_gitignore_rules(tmp_repo)
    for required in _LOCAL_WHITELIST_REQUIRED_RULES:
        assert required in rules, (
            f"v12.2.0 whitelist contract: rule {required!r} must be present "
            f"after legacy graduation (got {rules!r})"
        )
    legacy_only_rules = {
        "!.local/.agent/",
        ".local/.agent/active/*/learnings.jsonl",
        ".local/memory/operational.jsonl",
    }
    for legacy in legacy_only_rules:
        assert legacy not in rules, (
            f"legacy rule {legacy!r} must be stripped during graduation (got {rules!r})"
        )
    repair_logs = [
        record.getMessage()
        for record in caplog.records
        if record.name == "devolaflow.local.workspace" and record.levelno == logging.INFO
    ]
    assert any("legacy .local gitignore whitelist" in msg for msg in repair_logs), (
        f"repair path MUST log an INFO citing the legacy graduation (got {repair_logs!r})"
    )


def test_v12_2_0_whitelist_is_idempotent_no_op_second_run(tmp_repo: Path) -> None:
    """Running scaffold on a v12.2.0-whitelisted repo is a no-op."""
    scaffold_local(tmp_repo)
    first_text = (tmp_repo / ".gitignore").read_text(encoding="utf-8")
    first_mtime = (tmp_repo / ".gitignore").stat().st_mtime

    changed = ensure_local_gitignore(tmp_repo)

    assert changed is False, (
        "v12.2.0 whitelist contract: a 2nd `ensure_local_gitignore` call on "
        "an already-whitelisted repo MUST return False (idempotency)"
    )
    second_text = (tmp_repo / ".gitignore").read_text(encoding="utf-8")
    second_mtime = (tmp_repo / ".gitignore").stat().st_mtime
    assert second_text == first_text, (
        "v12.2.0 whitelist contract: 2nd call must not mutate the file content"
    )
    assert second_mtime == first_mtime, (
        "v12.2.0 whitelist contract: 2nd call must not bump the file mtime"
    )


def test_narrow_pre_existing_rule_triggers_warning_alongside_whitelist(
    tmp_repo: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A surviving narrow rule (e.g. `.local/.agent/active/`) warns at write.

    The narrow rule is NOT a recognised v9.2.3 broad or legacy whitelist
    entry, so the repair path leaves it intact and appends the v12.2.0
    block alongside. A single WARN names the surviving narrow rule so the
    operator can review whether it intentionally hides files the whitelist
    would otherwise track.
    """
    caplog.set_level(logging.WARNING, logger="devolaflow.local.workspace")
    (tmp_repo / ".gitignore").write_text(
        ".local/.agent/active/\n",
        encoding="utf-8",
    )

    scaffold_local(tmp_repo)

    warnings = _scaffold_warnings(caplog)
    assert len(warnings) >= 1, (
        f"narrow rule survival must trigger at least 1 WARNING (got {len(warnings)})"
    )
    messages = " | ".join(w.getMessage() for w in warnings)
    assert ".local/.agent/active" in messages, (
        f"WARN must name the surviving narrow rule (got {messages!r})"
    )
    assert "v12.2.0 whitelist" in messages, (
        f"WARN must point at the v12.2.0 whitelist context (got {messages!r})"
    )
    rules = _read_gitignore_rules(tmp_repo)
    assert ".local/.agent/active/" in rules, (
        "narrow rule must survive the repair (not auto-stripped — only "
        "recognised legacy/v9.2.3 rules are graduated)"
    )
    for required in _LOCAL_WHITELIST_REQUIRED_RULES:
        assert required in rules, (
            f"v12.2.0 whitelist contract: rule {required!r} must coexist with "
            f"the surviving narrow rule (got {rules!r})"
        )


# ── Direct helper coverage (improves _read/_match line coverage to ≥ 80%) ──


def test_helper_internals_cover_edge_cases(
    tmp_repo: Path, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Single-test consolidation of the 3 remaining helper branches.

    Pinned branches (each one is a single ``if`` arm in the helper
    bodies — collapsed into one test to honour the W-17 PV NEW-test
    discipline while still raising coverage on the audit module to
    ≥ 80%):

    1. ``_read_gitignore_rules`` strips comments + blank lines + leading
       whitespace, and short-circuits to ``[]`` (returning EMPTY) when
       the file is unreadable (``OSError`` path; logs a WARN per S-5).
    2. ``_path_matches_gitignore`` honours leading-``/`` root anchors
       (the leading slash is stripped before pattern matching).
    3. ``_path_matches_gitignore`` returns ``False`` for an empty rule
       (the ``if not cleaned: continue`` arm — defensive against rules
       that consist solely of ``/`` characters).
    """
    caplog.set_level(logging.WARNING, logger="devolaflow.local.workspace")

    (tmp_repo / ".gitignore").write_text(
        "# top comment\n\n  # indented comment\n\n  .local/*\n*.log  \n",
        encoding="utf-8",
    )
    rules = _read_gitignore_rules(tmp_repo)
    assert rules == [".local/*", "*.log"], (
        f"reader must strip blanks + comments and trim whitespace (got {rules!r})"
    )

    assert _path_matches_gitignore(".local/feedbacks", ["/.local/"]), (
        "root-anchored rule (leading slash) must still match"
    )
    assert not _path_matches_gitignore("src/devolaflow", ["/.local/"]), (
        "root-anchored rule must NOT spuriously match unrelated paths"
    )
    assert not _path_matches_gitignore(".local/anything", ["/", "//"]), (
        "empty-after-strip rules must short-circuit to no-match"
    )

    # Force the OSError path of `_read_gitignore_rules` via monkeypatch
    # on Path.read_text — simulates a permission-denied .gitignore. The
    # helper must log a WARN (S-5 explicit error state) and return [].
    real_read_text = Path.read_text

    def _raising_read_text(self: Path, *args: object, **kwargs: object) -> str:
        if self.name == ".gitignore":
            raise PermissionError("simulated permission denied")
        return real_read_text(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "read_text", _raising_read_text)
    caplog.clear()
    rules = _read_gitignore_rules(tmp_repo)
    assert rules == [], "OSError path must short-circuit to empty rules"
    perm_warnings = [
        record.getMessage()
        for record in caplog.records
        if record.levelno == logging.WARNING and "could not read" in record.getMessage()
    ]
    assert perm_warnings, "OSError path must log a WARNING (S-5: no silent failure)"
