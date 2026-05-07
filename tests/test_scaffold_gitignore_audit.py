"""I-003 closure tests — scaffold_local keeps .local/ private.

These tests pin the repo-init/private-workspace contract:
``scaffold_local(cwd)`` creates or repairs the repo root ``.gitignore``
so ``.local/`` is ignored as a whole. A broad ``.local/`` rule is the
expected state and must not emit README whitelist recommendations.
Narrow legacy rules may still surface a targeted warning, but the
repair path appends broad ``.local/`` coverage instead of encouraging
tracked ``.local`` contents.

Source artefacts:

* ``.local/feedbacks/feedback_for_v9.2.1.md`` §3 (I-003 reproduction).
* ``.local/research/v9.2.2_gap_analysis.md`` §2 PV-02 scope.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from devolaflow.local.workspace import (
    _path_matches_gitignore,
    _read_gitignore_rules,
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


def test_no_gitignore_emits_no_warning(tmp_repo: Path, caplog: pytest.LogCaptureFixture) -> None:
    """Without a `.gitignore` scaffold creates one with `.local/` quietly."""
    caplog.set_level(logging.WARNING, logger="devolaflow.local.workspace")
    assert not (tmp_repo / ".gitignore").exists(), "fixture precondition"

    scaffold_local(tmp_repo)

    assert (tmp_repo / ".gitignore").read_text(encoding="utf-8").splitlines() == [
        "# DevolaFlow local workspace (private)",
        ".local/",
    ]
    warnings = _scaffold_warnings(caplog)
    assert warnings == [], (
        f"private .local contract: a fresh repo must emit ZERO WARNINGs "
        f"while creating the default ignore rule (got "
        f"{[w.getMessage() for w in warnings]!r})"
    )
    assert last_gitignore_audit() == [], (
        "module-level audit cache must be empty when broad .local/ is present"
    )


def test_gitignore_without_matching_rule_no_warning(
    tmp_repo: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """An unrelated `.gitignore` is extended with `.local/` without warning."""
    caplog.set_level(logging.WARNING, logger="devolaflow.local.workspace")
    (tmp_repo / ".gitignore").write_text(
        "# unrelated rules — none touch .local/\nbuild/\ndist/\n*.pyc\n",
        encoding="utf-8",
    )

    scaffold_local(tmp_repo)

    warnings = _scaffold_warnings(caplog)
    assert warnings == [], (
        f"private .local contract: unrelated .gitignore rules must NOT "
        f"trigger warnings when `.local/` is appended (got "
        f"{[w.getMessage() for w in warnings]!r})"
    )
    assert ".local/" in _read_gitignore_rules(tmp_repo)
    assert last_gitignore_audit() == [], "audit cache must be empty when broad .local/ is present"


def test_gitignore_with_agent_active_rule_warns(
    tmp_repo: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """`.gitignore: .local/.agent/active/` triggers a targeted repair WARN.

    The headline I-003 closure: the operator who carries a session-
    scoped ignore on `.local/.agent/active/` (a common pattern when
    in-flight changes are kept private) is told the rule is narrower
    than the current private-workspace default. Scaffold appends the
    broad `.local/` rule instead of recommending README whitelists.
    """
    caplog.set_level(logging.WARNING, logger="devolaflow.local.workspace")
    (tmp_repo / ".gitignore").write_text(
        ".local/.agent/active/\n",
        encoding="utf-8",
    )

    scaffold_local(tmp_repo)

    warnings = _scaffold_warnings(caplog)
    assert len(warnings) >= 1, (
        f"I-003 contract: a `.gitignore: .local/.agent/active/` rule MUST "
        f"trigger at least 1 WARNING (got {len(warnings)})"
    )
    messages = " | ".join(w.getMessage() for w in warnings)
    assert ".local/.agent/active" in messages, (
        f"WARNING must name the ignored path explicitly so the operator "
        f"knows where to look (got {messages!r})"
    )
    assert "adding `.local/`" in messages, (
        f"WARNING must point at the broad private-workspace fix (got {messages!r})"
    )
    assert "!." not in messages, (
        f"WARNING must not recommend whitelisting .local contents (got {messages!r})"
    )
    assert ".local/" in _read_gitignore_rules(tmp_repo)

    cached = last_gitignore_audit()
    assert cached == [], "broad .local/ coverage should suppress README audit matches"


def test_gitignore_wildcard_local_is_expected_private_state(
    tmp_repo: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A broad `.gitignore: .local/` is the expected private state."""
    caplog.set_level(logging.WARNING, logger="devolaflow.local.workspace")
    (tmp_repo / ".gitignore").write_text(".local/\n", encoding="utf-8")

    scaffold_local(tmp_repo)

    warnings = _scaffold_warnings(caplog)
    assert warnings == [], (
        f"private .local contract: broad `.local/` must not warn "
        f"(got {[w.getMessage() for w in warnings]!r})"
    )
    cached = last_gitignore_audit()
    assert cached == [], "broad .local/ coverage should produce no audit matches"


def test_legacy_local_whitelist_block_is_repaired(
    tmp_repo: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Old tracked-subtree whitelist rules are collapsed to broad `.local/`."""
    caplog.set_level(logging.WARNING, logger="devolaflow.local.workspace")
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
    assert rules == [".local/"], (
        f"legacy .local whitelist block must be simplified to broad ignore (got {rules!r})"
    )
    assert _scaffold_warnings(caplog) == [], (
        "repairing the legacy whitelist block must not recommend README whitelists"
    )
    assert last_gitignore_audit() == []


def test_negation_rule_does_not_suppress_warning_on_positive_match(
    tmp_repo: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A sibling negation does not prevent broad `.local/` repair.

    Negation rules are not treated as the desired repo-init state.
    Scaffold appends `.local/` and leaves existing hand-authored lines
    intact rather than recommending more tracked contents.
    """
    caplog.set_level(logging.WARNING, logger="devolaflow.local.workspace")
    (tmp_repo / ".gitignore").write_text(
        ".local/.agent/active/\n!.local/.agent/active/README.md\n",
        encoding="utf-8",
    )

    scaffold_local(tmp_repo)

    warnings = _scaffold_warnings(caplog)
    assert len(warnings) >= 1, (
        "narrow positive rule should still trigger a repair warning even "
        "when a sibling negation exists"
    )
    messages = " | ".join(w.getMessage() for w in warnings)
    assert ".local/.agent/active" in messages, (
        f"WARN must still name the ignored path (got {messages!r})"
    )
    assert "!.local/.agent/active/README.md" not in messages, (
        f"WARN must not recommend README whitelisting (got {messages!r})"
    )
    assert ".local/" in _read_gitignore_rules(tmp_repo)
    assert last_gitignore_audit() == []


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
        "# top comment\n\n  # indented comment\n\n  .local/\n*.log  \n",
        encoding="utf-8",
    )
    rules = _read_gitignore_rules(tmp_repo)
    assert rules == [".local/", "*.log"], (
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
