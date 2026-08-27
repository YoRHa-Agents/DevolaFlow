"""Tests for opt-in execution of immutable pre-v16 ghost audits."""

from __future__ import annotations

from pathlib import Path

from tests.ghost.conftest import full_ghost_enabled, is_legacy_feature_module


def test_ghost_full_requires_exact_one_value() -> None:
    assert full_ghost_enabled({}) is False
    assert full_ghost_enabled({"GHOST_FULL": "0"}) is False
    assert full_ghost_enabled({"GHOST_FULL": "true"}) is False
    assert full_ghost_enabled({"GHOST_FULL": "1"}) is True


def test_legacy_feature_module_detection() -> None:
    assert is_legacy_feature_module(Path("test_features_legacy.py"))
    assert is_legacy_feature_module(Path("test_features_v15_2.py"))
    assert not is_legacy_feature_module(Path("test_features_v16_0.py"))
    assert not is_legacy_feature_module(Path("test_rules.py"))
