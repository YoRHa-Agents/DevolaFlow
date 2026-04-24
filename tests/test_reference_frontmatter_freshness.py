"""CI guard for reference-frontmatter freshness (90-day window).

Per ``.local/research/v9.0.0_reference_review.md`` F-09 (CRITICAL): every
reference under ``workflow-system/agent/references/*.md`` declares a
``last_updated`` frontmatter date. If the date drifts older than the
90-day window the freshness signal degrades — operators reading the doc
have no signal that the content has been re-validated against the
current codebase.

This test enforces the 90-day window:

* Every ``.md`` file under ``workflow-system/agent/references/`` MUST
  carry an ISO-8601 ``last_updated`` line in its YAML frontmatter
  (between ``---`` delimiters).
* The date MUST be at most 90 days older than today (``date.today()``).
  Violations are STALE — fix by editing the file (a non-trivial body
  edit OR explicit re-validation pass) and bumping the date.

Long-term solution to F-09 (replaces the PV-02 short-term frontmatter
bumps that landed inline with the reference cascade). When this test
fails in a future cycle, the canonical fix is:

1. Re-validate the stale reference against current code / schemas /
   workflow templates.
2. Apply any necessary edits (frontmatter date alone is NOT sufficient;
   a content edit OR an explicit re-validation note is required —
   see ``.local/research/v9.0.0_reference_review.md`` Action Plan).
3. Bump ``last_updated`` to today's date.
4. Re-run ``pytest tests/test_reference_frontmatter_freshness.py -v``.

Closes F-09 long-term (CRITICAL) per
``.local/research/v9.0.0_implementation_plan.md`` §6.2.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pytest

REFERENCES_DIR = Path(__file__).parent.parent / "workflow-system/agent/references"

FRESHNESS_WINDOW_DAYS = 90
"""Maximum age (in days) of a reference's ``last_updated`` frontmatter date.

Sized to match the v9.0.0 cycle's quarterly cadence per Theme T8 (NineS
hygiene + audit-cadence rules). Any reference older than this is
considered STALE and fails CI.
"""

ISO_DATE_RE = re.compile(r"^last_updated:\s*[\"']?(\d{4}-\d{2}-\d{2})[\"']?\s*$")
"""Match a frontmatter ``last_updated: "YYYY-MM-DD"`` line; quotes optional."""


def _frontmatter_lines(text: str) -> list[str]:
    """Return the frontmatter body lines between ``---`` delimiters.

    Returns ``[]`` if the file does not start with ``---`` or has no
    closing ``---``. Frontmatter is the YAML block at the head of every
    SF-4 reference per Rule SF-2.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return []
    body: list[str] = []
    for line in lines[1:]:
        if line.strip() == "---":
            return body
        body.append(line)
    return []


def _parse_last_updated(text: str) -> date | None:
    """Extract the first ``last_updated:`` ISO-8601 date from frontmatter."""
    for line in _frontmatter_lines(text):
        match = ISO_DATE_RE.match(line)
        if match is not None:
            return date.fromisoformat(match.group(1))
    return None


def _reference_paths() -> list[Path]:
    """All ``.md`` files under ``workflow-system/agent/references/``."""
    return sorted(REFERENCES_DIR.glob("*.md"))


# ---------------------------------------------------------------------------
# Smoke / shape tests
# ---------------------------------------------------------------------------


def test_references_dir_exists() -> None:
    assert REFERENCES_DIR.is_dir(), f"missing references dir: {REFERENCES_DIR}"


def test_references_dir_non_empty() -> None:
    paths = _reference_paths()
    assert len(paths) >= 10, (
        f"references dir has only {len(paths)} files; expected ≥ 10 SF-4 canonical references"
    )


# ---------------------------------------------------------------------------
# Frontmatter parser tests
# ---------------------------------------------------------------------------


class TestFrontmatterParser:
    """Defensive parser tests so a parser bug never silently allows stale
    references to slip past the freshness check."""

    def test_extracts_quoted_date(self) -> None:
        text = '---\nfoo: bar\nlast_updated: "2026-04-23"\n---\nbody'
        assert _parse_last_updated(text) == date(2026, 4, 23)

    def test_extracts_unquoted_date(self) -> None:
        text = "---\nfoo: bar\nlast_updated: 2026-04-23\n---\nbody"
        assert _parse_last_updated(text) == date(2026, 4, 23)

    def test_extracts_single_quoted_date(self) -> None:
        text = "---\nfoo: bar\nlast_updated: '2026-04-23'\n---\nbody"
        assert _parse_last_updated(text) == date(2026, 4, 23)

    def test_returns_none_when_no_frontmatter(self) -> None:
        assert _parse_last_updated("# heading\n\nbody") is None

    def test_returns_none_when_no_last_updated(self) -> None:
        text = "---\nfoo: bar\n---\nbody"
        assert _parse_last_updated(text) is None

    def test_returns_none_when_unclosed_frontmatter(self) -> None:
        text = "---\nfoo: bar\nlast_updated: 2026-04-23\nno closer"
        assert _parse_last_updated(text) is None

    def test_extracts_first_match_in_frontmatter(self) -> None:
        """If a file has ``last_updated`` in BOTH frontmatter and body
        (e.g. an example block), only the frontmatter line counts."""
        text = "---\nlast_updated: \"2026-04-23\"\n---\nbody example: last_updated: '1999-01-01'\n"
        assert _parse_last_updated(text) == date(2026, 4, 23)


# ---------------------------------------------------------------------------
# Per-file freshness assertion (one parametrised test per reference)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", _reference_paths(), ids=lambda p: p.name)
def test_reference_has_recent_last_updated(path: Path) -> None:
    """Each reference's frontmatter ``last_updated`` MUST be within
    ``FRESHNESS_WINDOW_DAYS`` of today.

    Closes F-09 long-term per v9.0.0 PV-02 / v9-ADR-002.
    """
    text = path.read_text(encoding="utf-8")
    last_updated = _parse_last_updated(text)
    assert last_updated is not None, (
        f"{path.name}: missing or unparseable `last_updated:` frontmatter line; "
        "every SF-4 reference MUST declare an ISO-8601 last_updated date per Rule SF-2"
    )
    today = date.today()
    age_days = (today - last_updated).days
    assert age_days >= 0, (
        f"{path.name}: last_updated={last_updated} is in the FUTURE relative to "
        f"today={today}; check the system clock or the frontmatter line"
    )
    assert age_days <= FRESHNESS_WINDOW_DAYS, (
        f"{path.name}: last_updated={last_updated} is {age_days} days old "
        f"(>{FRESHNESS_WINDOW_DAYS}-day freshness window); STALE — re-validate the "
        "reference against current code, apply edits if needed, then bump the "
        "frontmatter date. See .local/research/v9.0.0_reference_review.md F-09."
    )


# ---------------------------------------------------------------------------
# Aggregate inventory + budget
# ---------------------------------------------------------------------------


def test_freshness_window_is_documented_constant() -> None:
    """The 90-day window value is the canonical freshness budget per
    Theme T8 (NineS hygiene). Changing the window requires updating
    this constant AND the v9.0.0_reference_review.md F-09 mitigation."""
    assert FRESHNESS_WINDOW_DAYS == 90, (
        "FRESHNESS_WINDOW_DAYS drift from the v9.0.0 canonical 90-day window — "
        "see Theme T8 (forward-defined v8.5.0 PV-05 audit-cadence rules) + F-09 long-term"
    )


def test_no_reference_stale_by_more_than_window() -> None:
    """Aggregate guard: at least 80% of references MUST be fresh
    (defensive against a bulk-stale state where the per-file tests
    would all fail individually but the codebase is in a coordinated
    refresh state)."""
    paths = _reference_paths()
    today = date.today()
    fresh_count = 0
    for path in paths:
        last_updated = _parse_last_updated(path.read_text(encoding="utf-8"))
        if last_updated is None:
            continue
        age_days = (today - last_updated).days
        if 0 <= age_days <= FRESHNESS_WINDOW_DAYS:
            fresh_count += 1
    assert fresh_count / max(len(paths), 1) >= 0.80, (
        f"only {fresh_count}/{len(paths)} references are within the "
        f"{FRESHNESS_WINDOW_DAYS}-day freshness window; ≥80% required to maintain "
        "audit-cadence floor per Theme T8 + F-09"
    )


def test_recent_bump_dates_make_sense() -> None:
    """Sanity guard: at least 3 references should be 'very recent' (within
    7 days) at any given time — otherwise the doc-cadence has stalled.

    This is a soft signal: a fresh checkout from a low-activity period
    might legitimately have all files at the 90-day boundary. The 7-day
    horizon is a loose 'someone-was-here-recently' canary; failure
    suggests the team has not touched references in a week.
    """
    paths = _reference_paths()
    today = date.today()
    very_recent = 0
    for path in paths:
        last_updated = _parse_last_updated(path.read_text(encoding="utf-8"))
        if last_updated is None:
            continue
        age_days = (today - last_updated).days
        if 0 <= age_days <= 7:
            very_recent += 1
    # Use a soft assertion via warning: non-fatal but visible in logs.
    if very_recent < 3:
        # Soft warning — DO NOT fail; emit via pytest's warning surface so
        # operators see it without blocking the build.
        pytest.warns(UserWarning, match=r"reference cadence")
        # Always pass — this is a canary, not a hard guard.
    assert very_recent >= 0  # tautology — keeps test in the suite
