"""I-003 closure tests — scaffold_local audits .gitignore coverage.

These tests pin the v9.2.3 PV-02 ``_audit_gitignore_coverage`` surface:
``scaffold_local(cwd)`` emits a single WARNING log per scaffold path
that an existing ``.gitignore`` rule already covers, naming the path
and the recommended ``!<rel>/README.md`` whitelist line. Quiet on
absent / unrelated rules; conservative on negation rules (positive
matches still warn even when a sibling whitelist exists).

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
    """Without a `.gitignore` the audit is fully quiet."""
    caplog.set_level(logging.WARNING, logger="devolaflow.local.workspace")
    assert not (tmp_repo / ".gitignore").exists(), "fixture precondition"

    scaffold_local(tmp_repo)

    warnings = _scaffold_warnings(caplog)
    assert warnings == [], (
        f"I-003 contract: a fresh repo with no .gitignore must emit ZERO "
        f"WARNINGs from the audit (got {[w.getMessage() for w in warnings]!r})"
    )
    assert last_gitignore_audit() == [], (
        "module-level audit cache must be empty when no rules are loaded"
    )


def test_gitignore_without_matching_rule_no_warning(
    tmp_repo: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """An unrelated `.gitignore` (e.g. `build/`) does not trigger the audit."""
    caplog.set_level(logging.WARNING, logger="devolaflow.local.workspace")
    (tmp_repo / ".gitignore").write_text(
        "# unrelated rules — none touch .local/\nbuild/\ndist/\n*.pyc\n",
        encoding="utf-8",
    )

    scaffold_local(tmp_repo)

    warnings = _scaffold_warnings(caplog)
    assert warnings == [], (
        f"I-003 contract: unrelated .gitignore rules must NOT trigger the "
        f"audit (got {[w.getMessage() for w in warnings]!r})"
    )
    assert last_gitignore_audit() == [], (
        "audit cache must be empty when no rule matches a scaffold path"
    )


def test_gitignore_with_agent_active_rule_warns(
    tmp_repo: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """`.gitignore: .local/.agent/active/` triggers a targeted WARN.

    The headline I-003 closure: the operator who carries a session-
    scoped ignore on `.local/.agent/active/` (a common pattern when
    in-flight changes are kept private) is told that the new
    convention README is invisible — and given the exact whitelist
    line to fix it.
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
    assert "!.local/.agent/active/README.md" in messages, (
        f"WARNING must include the recommended `!<rel>/README.md` whitelist "
        f"line so the operator gets the exact fix (got {messages!r})"
    )

    cached = last_gitignore_audit()
    assert any(p.name == "active" for p in cached), (
        "module-level audit cache must record the active/ match"
    )


def test_gitignore_wildcard_local_warns_all_local_paths(
    tmp_repo: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A broad `.gitignore: .local/` ignores every scaffold path under .local/.

    Sanity check that the matcher's directory-prefix semantics work —
    `.local/` should sweep the 6 REQUIRED + 1 MEMORY_SUBDIRS scaffold
    roots into a single audit batch, each with its own WARNING.
    """
    caplog.set_level(logging.WARNING, logger="devolaflow.local.workspace")
    (tmp_repo / ".gitignore").write_text(".local/\n", encoding="utf-8")

    scaffold_local(tmp_repo)

    warnings = _scaffold_warnings(caplog)
    # Expect ≥ 7 matches: 6 REQUIRED_DIRS (feedbacks, tasks, memory,
    # .agent/active, .agent/handoff, .agent/archive) + 1 MEMORY_SUBDIRS
    # entry (memory/specs). The exact count is a floor, not a ceiling —
    # additional on-demand directories would also match.
    assert len(warnings) >= 7, (
        f"I-003 contract: broad `.gitignore: .local/` rule must sweep ≥ 7 "
        f"scaffold paths into the audit (got {len(warnings)})"
    )
    cached = last_gitignore_audit()
    assert len(cached) == len(warnings), (
        "audit cache size must match the WARN count (1:1 path → log invariant)"
    )
    # Every WARNING references a `.local/` path.
    for record in warnings:
        assert ".local/" in record.getMessage() or ".local " in record.getMessage(), (
            f"WARN must reference a .local-prefixed path (got {record.getMessage()!r})"
        )


def test_negation_rule_does_not_suppress_warning_on_positive_match(
    tmp_repo: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """`!path/README.md` does NOT mute the directory-level positive match.

    Per the conservative audit design (`_path_matches_gitignore`
    docstring), negation rules are intentionally skipped — the audit
    only needs to detect the "written but hidden" case for the
    directory itself; a negation is the operator's explicit whitelist
    for a sibling file. The directory-level WARN still fires so the
    operator can decide whether the negation alone is sufficient.
    """
    caplog.set_level(logging.WARNING, logger="devolaflow.local.workspace")
    (tmp_repo / ".gitignore").write_text(
        ".local/.agent/active/\n!.local/.agent/active/README.md\n",
        encoding="utf-8",
    )

    scaffold_local(tmp_repo)

    warnings = _scaffold_warnings(caplog)
    assert len(warnings) >= 1, (
        "I-003 conservative-audit contract: positive rule still triggers "
        "the warning even when a sibling whitelist exists; the operator "
        "can resolve the conflict themselves once they see it"
    )
    messages = " | ".join(w.getMessage() for w in warnings)
    assert ".local/.agent/active" in messages, (
        f"WARN must still name the ignored path (got {messages!r})"
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
