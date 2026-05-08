"""CHANGELOG.md no-duplicate-version-header lint (v11.1.1 D-1).

Closes the v11.1.0 cycle's PV-03 N-2 class-of-bug observed during the
cascade-restoration cycle: an L3 task agent commit (``da1c489``)
double-applied the ``## [11.0.3]`` CHANGELOG entry diff (67-line
duplicate; same diff appended twice). The duplicate was reconciled
in-PV by ``f7f1f93`` (-68 lines).

The PV-03 N-2 mitigation enforced single-application via the
``grep -c '^## \\[X\\.Y\\.Z\\]' CHANGELOG.md == 1`` discipline + the
L1-per-PV invariant (no parallel L1 sessions on the same branch).
PV-04..PV-07 inherited that discipline cleanly. This CI-time lint
(deferral D-5 in the v11.1.0 retrospective; first of the 3 staged
v11.1.x stability patches per the dispatcher's D-1 / D-2 / D-3
in-series labels) fails fast at every commit if a future cycle
re-introduces the class-of-bug — converting an in-PV reconciliation
cost into a CI-time block.

Source: ``docs/cycle-archive/v11.1.0/retrospective.md`` §3 D-5
(CHANGELOG single-application CI lint deferral; v11.1.x stability
patch landing target). See also §5 P-5 next-cycle proposal.
"""

from __future__ import annotations

import re
from pathlib import Path

# Permissive on the version-string content so historical or future
# pre-release tags like ``[11.0.0-rc1]`` flow through without false
# negatives. The contract is "the bracketed token is what we
# de-duplicate"; the token's syntax is irrelevant to the lint.
_VERSION_HEADER_RE = re.compile(r"^## \[([^\]]+)\]", re.MULTILINE)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_CHANGELOG_PATH = _REPO_ROOT / "CHANGELOG.md"


def find_duplicate_version_headers(text: str) -> list[tuple[str, list[int]]]:
    """Return ``[(version, [line_numbers]), ...]`` for duplicate headers.

    A header line is the 1-indexed line number of the matched
    ``## [<version>]``. Versions appearing exactly once are NOT in the
    return value (the function reports duplicates only). Comparison is
    by ``str.strip()``-normalized version string so trailing
    whitespace inside the bracket cannot mask a duplicate.

    Returns:
        Empty list when the CHANGELOG is single-application clean.
        Otherwise ``[(version, [line, line, ...]), ...]`` sorted in
        the order the version's first occurrence appears.
    """
    seen: dict[str, list[int]] = {}
    for match in _VERSION_HEADER_RE.finditer(text):
        version = match.group(1).strip()
        line_no = text[: match.start()].count("\n") + 1
        seen.setdefault(version, []).append(line_no)
    return [(v, lines) for v, lines in seen.items() if len(lines) > 1]


def test_changelog_has_no_duplicate_version_headers() -> None:
    """The actual CHANGELOG.md must have no duplicate ``## [X.Y.Z]`` headers.

    This is the load-bearing lint — it runs against the real
    ``CHANGELOG.md`` checked into the repo. Failure here means a
    future commit re-introduced the PV-03 N-2 class-of-bug (commit
    ``da1c489`` for historical context).
    """
    text = _CHANGELOG_PATH.read_text(encoding="utf-8")
    duplicates = find_duplicate_version_headers(text)
    assert not duplicates, (
        "CHANGELOG.md has duplicate version headers (class-of-bug "
        "PV-03 N-2 'da1c489'). Each version string MUST appear "
        f"exactly once. Duplicates found: {duplicates}. "
        "See docs/cycle-archive/v11.1.0/retrospective.md §3 D-5."
    )


def test_changelog_lint_detects_synthetic_duplicate() -> None:
    """Positive control: a synthetic 2-version CHANGELOG with 1 duplicate."""
    synthetic = """# Changelog

## [1.0.0]
First entry.

## [1.0.0]
Duplicate entry — the bug.
"""
    duplicates = find_duplicate_version_headers(synthetic)
    assert duplicates == [("1.0.0", [3, 6])], (
        f"Helper failed to detect a synthetic duplicate; got {duplicates}."
    )


def test_changelog_lint_passes_on_unique_versions() -> None:
    """Negative control: a synthetic CHANGELOG with all unique version headers."""
    synthetic = """# Changelog

## [1.0.0]
First.

## [0.9.0]
Older.
"""
    duplicates = find_duplicate_version_headers(synthetic)
    assert duplicates == [], f"Helper false-positived on unique versions; got {duplicates}."
