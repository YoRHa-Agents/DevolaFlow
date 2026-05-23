"""Tests for v12.5.0 PV-05 D-3 — strip_l0_only_metadata helper.

Pins the contract documented in
:func:`devolaflow.agent_workspace.handoff.strip_l0_only_metadata`:

* **Pure** — operates on a deep-copy; never mutates input; never touches disk.
* **Idempotent** — applying twice == applying once (byte-equal).
* **Permissive on absent keys** — dict without banner / quality_score
  returns deep-copy unchanged.
* **Permissive on empty dict** — ``{}`` in → ``{}`` out.
* **S-5 explicit warn** — non-dict input logs a WARNING and returns the
  input unchanged.

Source: ``.local/research/v12.5.0_gap_analysis.md`` §2 D-3 +
``.local/research/v12.4.0_retrospective.md`` §6 telegraph item 2.
"""

from __future__ import annotations

import copy
import logging

import pytest

from devolaflow.agent_workspace.handoff import strip_l0_only_metadata


def test_happy_path_strips_banner_literal_from_string_field() -> None:
    """Banner literals at the leading edge of a string field are removed."""
    envelope = {
        "schema_version": 5,
        "report": {
            "delta": "🌸 DevolaFlow v12.4.0 — workflow start\n\nReal report content here.",
        },
    }
    out = strip_l0_only_metadata(envelope)
    assert "🌸" not in out["report"]["delta"]
    assert "DevolaFlow v12.4.0" not in out["report"]["delta"]
    assert "Real report content here." in out["report"]["delta"]


def test_happy_path_strips_quality_score_key() -> None:
    """``quality_score`` keys are removed at every nesting depth."""
    envelope = {
        "schema_version": 5,
        "report": {
            "delta": "stage complete",
            "quality_score": 8.7,  # subagent attempted to emit a score
        },
        "task_quality_score": 9.1,  # alias variant; also stripped
    }
    out = strip_l0_only_metadata(envelope)
    assert "quality_score" not in out["report"]
    assert "task_quality_score" not in out
    assert out["report"]["delta"] == "stage complete"


def test_happy_path_strips_session_banner_key() -> None:
    """``session_banner`` keys are removed."""
    envelope = {
        "schema_version": 5,
        "session_banner": "🌸 DevolaFlow v12.4.0",
        "report": {"delta": "done"},
    }
    out = strip_l0_only_metadata(envelope)
    assert "session_banner" not in out
    assert out["report"]["delta"] == "done"


def test_idempotency() -> None:
    """Applying twice == applying once (byte-equal)."""
    envelope = {
        "schema_version": 5,
        "report": {
            "delta": "🌸 DevolaFlow v12.4.0 — workflow end\n\nclean delta",
            "quality_score": 7.2,
        },
        "session_banner": "🌸 DevolaFlow v12.5.0",
    }
    once = strip_l0_only_metadata(envelope)
    twice = strip_l0_only_metadata(once)
    assert once == twice


def test_permissive_on_absent_keys() -> None:
    """Dict without any banner / quality_score keys returns deep-copy unchanged."""
    envelope = {
        "schema_version": 5,
        "from_layer": "L1",
        "to_layer": "L2",
        "report": {"delta": "stage 1 complete"},
    }
    out = strip_l0_only_metadata(envelope)
    assert out == envelope


def test_permissive_on_empty_dict() -> None:
    """``{}`` in → ``{}`` out (defensive zero-IO + S-5 permissive)."""
    assert strip_l0_only_metadata({}) == {}


def test_input_dict_not_mutated() -> None:
    """Pure-function invariant: input dict is byte-identical after the call."""
    envelope = {
        "schema_version": 5,
        "report": {
            "delta": "🌸 DevolaFlow v12.4.0\nclean",
            "quality_score": 8.0,
        },
    }
    snapshot = copy.deepcopy(envelope)
    _ = strip_l0_only_metadata(envelope)
    assert envelope == snapshot, (
        "v12.5.0 PV-05 D-3 violation: strip_l0_only_metadata MUST NOT "
        "mutate the input dict; the helper MUST operate on a deep-copy."
    )


def test_returns_new_dict_object() -> None:
    """The returned dict is a NEW object (deep-copy guarantee)."""
    envelope: dict = {"schema_version": 5}
    out = strip_l0_only_metadata(envelope)
    assert out is not envelope


def test_non_dict_input_warns_and_returns_unchanged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Non-dict input logs WARNING and returns the input unchanged (S-5)."""
    bad_input = ["not", "a", "dict"]
    with caplog.at_level(logging.WARNING, logger="devolaflow.agent_workspace.handoff"):
        out = strip_l0_only_metadata(bad_input)  # type: ignore[arg-type]
    assert out is bad_input  # returned unchanged, same object
    assert any(
        "non-dict" in rec.message.lower() and "S-5" in rec.message for rec in caplog.records
    ), (
        "v12.5.0 PV-05 D-3 violation: non-dict input MUST emit a "
        "WARNING citing the S-5 explicit-warn contract."
    )


def test_strips_nested_quality_score_in_list() -> None:
    """``quality_score`` keys nested in lists of dicts are also stripped."""
    envelope = {
        "schema_version": 5,
        "report": {
            "delta": "complete",
            "stages": [
                {"name": "analyze", "quality_score": 7.0},
                {"name": "implement", "quality_score": 8.5},
            ],
        },
    }
    out = strip_l0_only_metadata(envelope)
    for stage in out["report"]["stages"]:
        assert "quality_score" not in stage
    assert [s["name"] for s in out["report"]["stages"]] == ["analyze", "implement"]


def test_companion_to_banner_hook_zero_violations_post_strip() -> None:
    """Strip-then-validate: post-strip envelope passes the banner-hook detection.

    Integration scenario: an L1 subagent payload arrives with banner +
    quality_score literals. The handoff writer applies
    strip_l0_only_metadata BEFORE write. The post-strip payload should
    no longer contain ANY of the banner literal patterns the v12.4.0
    PV-05 hook detects, validating the helper closes the auto-cleanup
    loop telegraphed in v12.4.0 retro §6 item 2.
    """
    envelope = {
        "schema_version": 5,
        "from_layer": "L1",
        "to_layer": "L0",
        "report": {
            "delta": (
                "🌸 DevolaFlow v12.4.0 — workflow start\n\n"
                "Stage analyze complete.\n\n"
                "📊 Task Quality Score: 8.5/10\n"
            ),
            "quality_score": 8.5,
        },
        "session_banner": "🌸 DevolaFlow v12.4.0",
    }
    out = strip_l0_only_metadata(envelope)
    delta_text = out["report"]["delta"]
    # All 3 banner-literal patterns must be absent post-strip.
    assert "🌸" not in delta_text
    assert "DevolaFlow v" not in delta_text
    assert "Task Quality Score" not in delta_text
    # The L0-only KEYS at every nesting depth must be removed.
    assert "quality_score" not in out["report"]
    assert "session_banner" not in out
    # The non-banner content survives byte-stable.
    assert "Stage analyze complete." in delta_text
