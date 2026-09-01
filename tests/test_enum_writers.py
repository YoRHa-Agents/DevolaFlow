"""v24.3.0 — declared vocabulary must have a production writer.

v24.1.0 found `bypassed` declared in the compaction telemetry vocabulary,
collected into the frozenset that validated it, documented, tested, and never
produced by production code. The one-line fix shipped; the class of defect did
not get a guard. This suite is that guard's contract.
"""

from __future__ import annotations

import pytest

from devolaflow.enum_writers import (
    ALLOWLIST,
    find_unwritten_vocabulary,
    unused_allowlist_entries,
)


@pytest.fixture
def repo(tmp_path):
    """A miniature repository with the same layout the scan expects."""

    package = tmp_path / "src" / "devolaflow"
    package.mkdir(parents=True)
    return tmp_path, package


def test_the_repository_has_no_unwritten_vocabulary():
    """The whole point: this must stay at zero or name what broke it."""

    findings = find_unwritten_vocabulary(".")
    assert findings == (), "\n".join(str(item) for item in findings)


def test_every_allowlist_entry_still_names_something_that_exists():
    """A-5.2: an exemption outliving its subject is an unverifiable claim."""

    assert unused_allowlist_entries(".") == ()


def test_every_allowlist_entry_carries_a_reason():
    """ "Not got round to it" is the finding, so an empty reason is not allowed."""

    for name, reason in ALLOWLIST.items():
        assert reason.strip(), name
        assert len(reason) > 30, f"{name}: a one-word reason is not a reason"


def test_the_bypassed_shape_is_caught(repo):
    """The exact v24.1.0 defect: declared, validated, imported, never written."""

    root, package = repo
    (package / "telemetry.py").write_text(
        "from typing import Final\n\n"
        'OUTCOME_APPLIED: Final[str] = "applied"\n'
        'OUTCOME_BYPASSED: Final[str] = "bypassed"\n'
        "OUTCOMES: Final[frozenset[str]] = frozenset({OUTCOME_APPLIED, OUTCOME_BYPASSED})\n",
        encoding="utf-8",
    )
    (package / "writer.py").write_text(
        "from devolaflow.telemetry import OUTCOME_APPLIED, OUTCOME_BYPASSED\n\n"
        "def emit():\n"
        "    return OUTCOME_APPLIED\n",
        encoding="utf-8",
    )

    reported = {item.qualified_name for item in find_unwritten_vocabulary(root, allowlist=())}
    assert reported == {"OUTCOME_BYPASSED"}, (
        "membership in the validating set and an import are not writers"
    )


def test_an_enum_member_nothing_writes_is_reported(repo):
    root, package = repo
    (package / "models.py").write_text(
        "from enum import StrEnum\n\n"
        "class Outcome(StrEnum):\n"
        '    KEPT = "kept"\n'
        '    DROPPED = "dropped"\n',
        encoding="utf-8",
    )
    (package / "engine.py").write_text(
        "from devolaflow.models import Outcome\n\ndef decide():\n    return Outcome.KEPT\n",
        encoding="utf-8",
    )

    reported = {item.qualified_name for item in find_unwritten_vocabulary(root, allowlist=())}
    assert reported == {"Outcome.DROPPED"}


def test_a_test_only_writer_does_not_count(repo):
    """A test proves the value *can* be written, not that anything writes it."""

    root, package = repo
    (package / "models.py").write_text(
        'from enum import StrEnum\n\nclass Outcome(StrEnum):\n    DROPPED = "dropped"\n',
        encoding="utf-8",
    )
    tests = root / "tests"
    tests.mkdir()
    (tests / "test_models.py").write_text(
        "from devolaflow.models import Outcome\n\n"
        "def test_dropped():\n"
        "    assert Outcome.DROPPED\n",
        encoding="utf-8",
    )

    reported = {item.qualified_name for item in find_unwritten_vocabulary(root, allowlist=())}
    assert reported == {"Outcome.DROPPED"}


def test_an_allowlisted_member_is_silent(repo):
    root, package = repo
    (package / "models.py").write_text(
        'from enum import StrEnum\n\nclass Outcome(StrEnum):\n    DROPPED = "dropped"\n',
        encoding="utf-8",
    )

    assert find_unwritten_vocabulary(root, allowlist=("Outcome.DROPPED",)) == ()
