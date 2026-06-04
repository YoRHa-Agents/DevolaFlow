"""Tests for the ``check_human_input_append_only`` lifecycle hook (v14.0.0 Wave-3).

Gives the new hook direct unit coverage. The hook is the named, proposed
enforcement surface from ``.local/research/v14.0.0_design.md`` §3c: a
``### REQ-*`` block frozen by ``Lifecycle: RATIFIED`` (or a constitution
principle frozen by the file's ``**Ratified**`` stamp) MUST NOT be edited or
removed in place — a change MUST instead append a dated amendment AND bump the
file's ``**Version**`` stamp (S-9 append discipline, reused).

Test strategy mirrors
``tests/test_lifecycle_envelope_append_only.py`` (the sister S-9 hook):

* Ratified-block in-place edit WITHOUT an amendment → CHI001 blocker;
  strict mode re-raises.
* Ratified edit WITH a paired amendment + version bump → clean pass.
* A ``Lifecycle: DRAFT`` block is exempt (the trigger is RATIFIED-ness, NOT
  ``Status`` — design finding F-1).
* A footer-only ``**Version**`` bump is NOT a block edit (false-positive guard).
* Payload-shape errors emit CHI010 / CHI011 / CHI012 (error severity).

The hook is exported additively but is NOT wired into ``DEFAULT_EVENTS``
(two CI tests pin ``len(DEFAULT_EVENTS) == 16``); a guard test below confirms
the registry was left untouched.
"""

from __future__ import annotations

import logging
import textwrap

import pytest

from devolaflow.lifecycle import (
    DEFAULT_EVENTS,
    HookViolation,
    check_human_input_append_only,
)
from devolaflow.lifecycle.check_human_input_append_only import EVENT

_PRIOR_REQ = textwrap.dedent(
    """\
    # Requirements (`artifact: human-requirements`)

    ## Requirements

    ### REQ-INPUT-01: Ratified requirements are append-only
    - **Constraint:** A ratified block MUST NOT be edited in place.
    - **Acceptance:** `tests/test_human_input_immutability.py` PASSES.
    - **Lifecycle:** RATIFIED 2026-06-03
    - **Status:** Pending
    - **Amendments:** none

    **Version**: 1.0.0 | **Last Amended**: 2026-06-03
    """
)

# In-place edit of the ratified block's Constraint text (version stamp unchanged).
_EDIT_NO_BUMP = _PRIOR_REQ.replace(
    "A ratified block MUST NOT be edited in place.",
    "A ratified block MUST NOT be edited in place (reworded).",
)
# Same edit, but paired with a version-stamp bump (the sanctioned-amendment path).
_EDIT_BUMPED = _EDIT_NO_BUMP.replace("**Version**: 1.0.0", "**Version**: 1.0.1")
# Footer-only bump: no block body changed.
_FOOTER_ONLY_BUMP = _PRIOR_REQ.replace("**Version**: 1.0.0", "**Version**: 1.0.1")
# The ratified block removed in place.
_REMOVED = textwrap.dedent(
    """\
    # Requirements (`artifact: human-requirements`)

    ## Requirements

    (REQ-INPUT-01 was deleted.)

    **Version**: 1.0.0 | **Last Amended**: 2026-06-03
    """
)
# DRAFT variant — same block, but not yet ratified (exempt).
_PRIOR_DRAFT = _PRIOR_REQ.replace("**Lifecycle:** RATIFIED 2026-06-03", "**Lifecycle:** DRAFT")
_DRAFT_EDIT = _PRIOR_DRAFT.replace(
    "A ratified block MUST NOT be edited in place.",
    "A draft block may be freely revised.",
)

_PRIOR_CONST = textwrap.dedent(
    """\
    ---
    artifact: human-constitution
    version: 1.0.0
    ---
    # DevolaFlow Constitution

    ## Principle 2: Human intent is immutable post-approval
    The project MUST treat a ratified requirement as immutable.
    Rationale: preserves regression value.

    ## Governance
    - Amendments require rationale, approval, and a migration note.

    **Version**: 1.0.0 | **Ratified**: 2026-06-03 | **Last Amended**: 2026-06-03
    """
)
_CONST_EDIT = _PRIOR_CONST.replace(
    "The project MUST treat a ratified requirement as immutable.",
    "The project MUST treat a ratified requirement as permanently immutable.",
)


def test_ratified_inplace_edit_without_amendment_flagged(caplog) -> None:
    """Editing a RATIFIED block with no amendment → single CHI001 blocker + WARNING."""
    payload = {"prior": _PRIOR_REQ, "proposed": _EDIT_NO_BUMP, "amendment_added": False}
    with caplog.at_level(logging.WARNING, logger="devolaflow.lifecycle.dispatcher"):
        result = check_human_input_append_only(payload)
    assert result.passed is False
    assert len(result.violations) == 1
    assert result.violations[0].code == "CHI001"
    assert result.violations[0].severity == "blocker"
    assert "REQ-INPUT-01" in result.violations[0].message
    assert result.event == EVENT
    assert any("CHI001" in rec.message for rec in caplog.records)


def test_strict_mode_raises_on_ratified_edit() -> None:
    """Strict mode + ratified in-place edit → raises the CHI001 blocker."""
    payload = {"prior": _PRIOR_REQ, "proposed": _EDIT_NO_BUMP}
    with pytest.raises(HookViolation) as exc_info:
        check_human_input_append_only(payload, strict=True)
    assert exc_info.value.code == "CHI001"
    assert exc_info.value.severity == "blocker"


def test_ratified_edit_with_amendment_and_bump_passes() -> None:
    """A ratified edit paired with an amendment AND a version bump is OK."""
    payload = {"prior": _PRIOR_REQ, "proposed": _EDIT_BUMPED, "amendment_added": True}
    result = check_human_input_append_only(payload)
    assert result.passed is True
    assert result.violations == []


def test_amendment_without_version_bump_flags_chi002() -> None:
    """An amendment without the required ``**Version**`` bump → CHI002 error."""
    payload = {"prior": _PRIOR_REQ, "proposed": _EDIT_NO_BUMP, "amendment_added": True}
    result = check_human_input_append_only(payload)
    assert result.passed is False
    assert result.violations[0].code == "CHI002"
    assert result.violations[0].severity == "error"


def test_draft_block_edit_passes() -> None:
    """A ``Lifecycle: DRAFT`` block is freely editable (F-1: trigger is RATIFIED, not Status)."""
    payload = {"prior": _PRIOR_DRAFT, "proposed": _DRAFT_EDIT, "amendment_added": False}
    result = check_human_input_append_only(payload)
    assert result.passed is True
    assert result.violations == []


def test_version_footer_only_change_passes() -> None:
    """A footer-only ``**Version**`` bump does not count as a ratified block edit."""
    payload = {"prior": _PRIOR_REQ, "proposed": _FOOTER_ONLY_BUMP, "amendment_added": False}
    result = check_human_input_append_only(payload)
    assert result.passed is True


def test_unchanged_input_passes() -> None:
    """Identical prior/proposed text → no violations."""
    payload = {"prior": _PRIOR_REQ, "proposed": _PRIOR_REQ}
    result = check_human_input_append_only(payload)
    assert result.passed is True


def test_ratified_block_removed_in_place_flagged() -> None:
    """Removing a RATIFIED block without an amendment → CHI001 blocker."""
    payload = {"prior": _PRIOR_REQ, "proposed": _REMOVED, "amendment_added": False}
    result = check_human_input_append_only(payload)
    assert result.passed is False
    assert result.violations[0].code == "CHI001"
    assert "REQ-INPUT-01" in result.violations[0].message


def test_constitution_principle_edit_flagged() -> None:
    """A ratified constitution (``**Ratified**`` stamp) freezes its principle blocks."""
    payload = {
        "prior": _PRIOR_CONST,
        "proposed": _CONST_EDIT,
        "amendment_added": False,
        "path": ".local/human/input/constitution.md",
    }
    result = check_human_input_append_only(payload)
    assert result.passed is False
    assert result.violations[0].code == "CHI001"
    assert "Principle" in result.violations[0].message


def test_payload_shape_errors() -> None:
    """Missing / wrong-type / non-dict payloads emit CHI011 / CHI012 / CHI010 errors."""
    missing_prior = check_human_input_append_only({"proposed": "x"})
    assert missing_prior.passed is False
    assert missing_prior.violations[0].code == "CHI011"
    assert missing_prior.violations[0].severity == "error"

    missing_proposed = check_human_input_append_only({"prior": "x"})
    assert missing_proposed.violations[0].code == "CHI012"

    wrong_type = check_human_input_append_only({"prior": 123, "proposed": "x"})
    assert wrong_type.violations[0].code == "CHI011"

    not_a_mapping = check_human_input_append_only([])
    assert not_a_mapping.violations[0].code == "CHI010"


def test_hook_exported_but_not_registered_as_default() -> None:
    """The hook is additively exported but NOT wired into DEFAULT_EVENTS.

    Two CI tests pin ``len(DEFAULT_EVENTS) == 16`` exactly; this Wave-3 hook
    therefore stays unregistered (event wiring lands in the implementation
    cycle alongside those test updates). Guard against an accidental append.
    """
    assert EVENT not in DEFAULT_EVENTS
    assert len(DEFAULT_EVENTS) == 16
