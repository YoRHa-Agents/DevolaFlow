"""v16 three-layer normalization and legacy-v1 compatibility."""

from __future__ import annotations

import copy
import warnings
from pathlib import Path

import pytest

from devolaflow.agent_workspace.handoff import (
    HandoffEnvelope,
    HandoffStore,
    HandoffStoreError,
    make_envelope,
)
from devolaflow.agent_workspace.layers import (
    CURRENT_HANDOFF_SCHEMA_VERSION,
    CURRENT_LAYER_ROLES,
    LEGACY_HANDOFF_SCHEMA_VERSION,
    LEGACY_V1_LAYER_MAP,
    LegacyLayerWarning,
    normalize_hdr_layer,
    normalize_layer,
)
from devolaflow.lifecycle.validate_dispatch import validate_dispatch


def test_layer_ssot_requires_explicit_provenance_and_bounded_warnings() -> None:
    """Interpret tokens by generation and bound S-5 warnings per read context."""

    for token, expected in LEGACY_V1_LAYER_MAP.items():
        context = f"test.layer-matrix.{token}"
        with pytest.warns(LegacyLayerWarning, match="schema-v1"):
            assert (
                normalize_layer(
                    token,
                    schema_version=LEGACY_HANDOFF_SCHEMA_VERSION,
                    context=context,
                )
                == expected
            )

        if token in CURRENT_LAYER_ROLES:
            assert (
                normalize_layer(
                    token,
                    schema_version=CURRENT_HANDOFF_SCHEMA_VERSION,
                    context=f"{context}.current",
                )
                == token
            )
        else:
            with pytest.raises(ValueError, match="unknown current layer token"):
                normalize_layer(
                    token,
                    schema_version=CURRENT_HANDOFF_SCHEMA_VERSION,
                    context=f"{context}.current",
                )

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        for _ in range(2):
            assert (
                normalize_layer(
                    "L2",
                    schema_version=LEGACY_HANDOFF_SCHEMA_VERSION,
                    context="test.warning.from",
                )
                == "L1"
            )
        normalize_layer(
            "L2",
            schema_version=LEGACY_HANDOFF_SCHEMA_VERSION,
            context="test.warning.to",
        )
    assert len(caught) == 2
    assert all(item.category is LegacyLayerWarning for item in caught)

    with pytest.warns(LegacyLayerWarning):
        assert (
            normalize_hdr_layer(
                "stage",
                schema_version=LEGACY_HANDOFF_SCHEMA_VERSION,
                context="test.hdr.stage",
            )
            == "project"
        )
    with pytest.raises(ValueError, match="unknown"):
        normalize_layer("L9", schema_version=1, context="test.unknown.layer")
    with pytest.raises(ValueError, match="unknown"):
        normalize_hdr_layer("stage", schema_version=2, context="test.unknown.hdr")


def test_handoff_and_dispatch_preserve_explicit_layer_provenance(tmp_path: Path) -> None:
    """Use v16 tokens while preserving legacy ledgers and dispatch payloads."""

    store = HandoffStore(repo_root=tmp_path)
    invalid_v2 = HandoffEnvelope(
        schema_version=2,
        seq=1,
        from_layer="L3",
        to_layer="L1",
        change_id="layer-compat",
        created="2026-08-24T12:00:00Z",
        envelope_kind="StatusReport",
        report={"task_id": "T01", "state": "completed"},
    )
    with pytest.raises(HandoffStoreError, match="unknown current layer token"):
        store.write_envelope(invalid_v2)
    assert not store.handoff_root.exists()

    current = make_envelope(
        seq=1,
        from_layer="L2",
        to_layer="L1",
        change_id="current-layer",
        envelope_kind="StatusReport",
        payload={"task_id": "T02", "state": "completed"},
        created="2026-08-24T12:01:00Z",
    )
    assert current.schema_version == 2
    assert current.filename == "L2__L1__current-layer__0001.yaml"
    assert store.write_envelope(current).is_file()

    legacy_root = store.handoff_root
    legacy_path = legacy_root / "L3__L2__layer-compat__0001.yaml"
    legacy_path.write_text(
        "schema_version: 1\n"
        "seq: 1\n"
        "from_layer: L3\n"
        "to_layer: L2\n"
        "change_id: layer-compat\n"
        'created: "2026-08-24T12:02:00Z"\n'
        "envelope_kind: StatusReport\n"
        "report:\n"
        "  task_id: T01\n"
        "  state: completed\n",
        encoding="utf-8",
    )
    original = legacy_path.read_bytes()
    with warnings.catch_warnings(record=True) as legacy_warnings:
        warnings.simplefilter("always", LegacyLayerWarning)
        [legacy] = store.read_envelopes("layer-compat")
    assert len(legacy_warnings) == 2

    assert legacy.from_layer == "L3"
    assert legacy.to_layer == "L2"
    assert legacy.normalized_from_layer == "L2"
    assert legacy.normalized_to_layer == "L1"
    assert legacy.filename == legacy_path.name
    assert legacy_path.read_bytes() == original
    with pytest.raises(HandoffStoreError, match="schema-v1 envelopes are read-only"):
        store.write_envelope(legacy)
    assert legacy_path.read_bytes() == original

    legacy_payload = {
        "hdr": {"id": "d-legacy", "parent": "root", "layer": "stage", "timeout": 30},
        "accept": ["legacy header is normalized without payload mutation"],
    }
    legacy_before = copy.deepcopy(legacy_payload)
    with pytest.warns(LegacyLayerWarning, match="stage.*project"):
        result = validate_dispatch(legacy_payload)
    assert result.passed is True
    assert legacy_payload == legacy_before

    unknown_payload = {
        "hdr": {"id": "d-bad", "parent": "root", "layer": "operator", "timeout": 30},
        "accept": ["unknown header layer produces an explicit violation"],
    }
    unknown_before = copy.deepcopy(unknown_payload)
    invalid = validate_dispatch(unknown_payload)
    assert [violation.code for violation in invalid.violations] == ["VD009"]
    assert unknown_payload == unknown_before
