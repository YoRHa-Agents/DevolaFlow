"""Host/channel routing tests for dispatch context injection."""

from __future__ import annotations

from devolaflow.harness.dispatch_context import (
    current_dispatch_context,
    dispatch_context,
    prepare_dispatch_context,
    route_context_injection,
)


def _slice_selection() -> dict:
    return {
        "source": "selector",
        "rule_text": "## W-9\nRun the required checks.\n",
        "agents_md_slice": {"slice_enabled": True},
    }


def test_cursor_ide_does_not_embed_or_claim_observed_host_context() -> None:
    selection = _slice_selection()
    dispatch = {"task": {"type": "hotfix"}, "rules": {"text": selection["rule_text"]}}

    prepared = prepare_dispatch_context(
        dispatch,
        selection,
        host="cursor",
        channel="cursor-ide",
    )

    routing = prepared["routing"]
    assert routing["status"] == "host-injected-unsliceable"
    assert routing["evidence_status"] == "INSUFFICIENT"
    assert routing["embedded"] is False
    assert routing["source"] == "selector"
    assert routing["host"] == "cursor"
    assert routing["channel"] == "cursor-ide"
    assert routing["duplicate_prevented"] is True
    assert "text" not in prepared["dispatch"]["rules"]
    assert dispatch["rules"]["text"] == selection["rule_text"]


def test_subprocess_channel_may_embed_slice() -> None:
    prepared = prepare_dispatch_context(
        {"task": {"type": "hotfix"}, "rules": {}},
        _slice_selection(),
        host="claude",
        channel="claude",
    )

    routing = prepared["routing"]
    assert routing["status"] == "slice-embedded"
    assert routing["evidence_status"] == "AVAILABLE"
    assert routing["embedded"] is True
    assert prepared["dispatch"]["rules"]["text"] == routing["embedded_text"]


def test_unknown_host_and_channel_are_explicit_insufficient_states() -> None:
    unknown_host = route_context_injection(
        _slice_selection(),
        host="not-a-real-host",
        channel="claude",
    )
    assert unknown_host["status"] == "unknown-host"
    assert unknown_host["evidence_status"] == "INSUFFICIENT"
    assert unknown_host["embedded"] is False

    unknown_channel = route_context_injection(
        _slice_selection(),
        host="claude",
        channel="not-a-real-channel",
    )
    assert unknown_channel["status"] == "unknown-channel"
    assert unknown_channel["evidence_status"] == "INSUFFICIENT"
    assert unknown_channel["embedded"] is False


def test_missing_selection_text_never_removes_unrelated_rules() -> None:
    prepared = prepare_dispatch_context(
        {"rules": {"focus": "tests"}},
        {"source": "selector", "agents_md_slice": {"slice_enabled": True}},
        host="cursor",
        channel="cursor-ide",
    )

    assert prepared["routing"]["status"] == "INSUFFICIENT"
    assert prepared["dispatch"]["rules"] == {"focus": "tests"}


def test_dispatch_context_exposes_routing_sidecar() -> None:
    with dispatch_context(
        host="cursor",
        channel="cursor-ide",
        context_selection=_slice_selection(),
    ):
        current = current_dispatch_context()

    assert current is not None
    assert current["context_routing"]["status"] == "host-injected-unsliceable"
    assert current["context_routing"]["evidence_status"] == "INSUFFICIENT"
