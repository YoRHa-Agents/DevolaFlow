"""Si-Chip bridge shape contract tests.

Pins the v10.8.0 D-C-2 contract: DevolaFlow's Si-Chip bridge parsers
(``MetricsReport.from_yaml_dict`` + ``BasicAbilityProfile.from_yaml_dict``)
correctly parse REAL Si-Chip output captured at a pinned version.

The fixtures under ``tests/integration/fixtures/si-chip/`` are captured
from Si-Chip v0.1.6 (MVP-8 nested layout) + v0.4.0 (profile_static) and
carry the R1 version header mandated by D-C-2 §9 R1 mitigation.

Canonical Si-Chip URL: https://github.com/YoRHa-Agents/Si-Chip
"""

from __future__ import annotations

import pytest

from devolaflow.si_chip_bridge.models import BasicAbilityProfile, MetricsReport
from tests.integration.conftest import load_yaml_fixture


class TestMetricsReportShape:
    """Pin that ``MetricsReport.from_yaml_dict`` parses MVP-8 nested layout.

    This is precisely the defect class the v10.2.3 PV-04 bridge fix closed
    (`.local/research/v10.2.3_iteration_round1.md` §1 — pre-fix: every
    probed file returned composite=0.0 → DEFER). The contract test keeps
    the nested-path lookup honest across future upstream shapes.
    """

    def test_composite_non_zero_from_real_yaml(self) -> None:
        """Real Si-Chip MVP-8 YAML must produce composite > 0.0 (not silent zero).

        Consolidates the 4 per-field parse checks (composite, task_delta,
        metadata_tokens, body_tokens) into a single regression — the defect
        the v10.2.3 PV-04 fix closed manifested as composite=0.0 + every
        field zeroed, so a single assertion chain catches the whole class.
        """
        data = load_yaml_fixture("si-chip", "metrics_report.yaml")
        report = MetricsReport.from_yaml_dict(data)
        assert report.composite > 0.0, (
            f"v10.2.3 bridge defect would regress here — composite parsed "
            f"as {report.composite}; expected > 0.0 from fixture's "
            f"metrics.task_quality.T1_pass_rate = 0.9"
        )
        assert report.composite == pytest.approx(0.9, abs=1e-6)
        # task_delta must parse from MVP-8 summary.baseline_delta.
        assert report.task_delta == pytest.approx(0.9, abs=1e-6)
        # Nested context-economy tokens populate correctly.
        assert report.metadata_tokens == 310
        assert report.body_tokens == 4823

    def test_forward_compat_unknown_nested_keys_do_not_crash(self) -> None:
        """Forward-compat: future Si-Chip fields captured in ``raw`` for later consumption."""
        data = load_yaml_fixture("si-chip", "metrics_report.yaml")
        # Add a hypothetical future field to the nested layout.
        data["metrics"]["future_axis"] = {"F1_unknown_metric": 42}
        report = MetricsReport.from_yaml_dict(data)
        # Parser MUST NOT crash — unknown keys preserved in raw.
        assert "future_axis" in report.raw.get("metrics", {})
        # Known paths still resolve correctly.
        assert report.composite == pytest.approx(0.9, abs=1e-6)

    def test_legacy_top_level_shape_still_works(self) -> None:
        """Backward-compat: legacy flat top-level shape still parses."""
        legacy_data = {
            "composite": 0.7,
            "task_delta": 0.5,
            "value_vector": 0.3,
            "C1_metadata_tokens": 200,
            "C2_body_tokens": 3000,
        }
        report = MetricsReport.from_yaml_dict(legacy_data)
        assert report.composite == pytest.approx(0.7, abs=1e-6)
        assert report.metadata_tokens == 200
        assert report.body_tokens == 3000


class TestBasicAbilityProfileShape:
    """Pin that ``BasicAbilityProfile.from_yaml_dict`` parses real profile_static output."""

    def test_profile_fields_populated_from_fixture(self) -> None:
        """ability_id + token counts + reference/example counts populate correctly."""
        data = load_yaml_fixture("si-chip", "basic_ability_profile.yaml")
        profile = BasicAbilityProfile.from_yaml_dict(data)
        assert profile.ability_id == "devola-flow"
        assert profile.metadata_tokens == 87
        assert profile.body_tokens == 3200
        assert profile.references_count == 17
        assert profile.examples_count == 4

    def test_raw_preserves_unmodelled_fields_for_forward_compat(self) -> None:
        """raw dict preserves every field for forward-compat consumption."""
        data = load_yaml_fixture("si-chip", "basic_ability_profile.yaml")
        profile = BasicAbilityProfile.from_yaml_dict(data)
        # Fields NOT modelled by DF (but captured in raw).
        assert "router_floor" in profile.raw
        assert "neighbour_skills" in profile.raw
        assert profile.raw["router_floor"] == "composer_2/fast"


class TestCountTokensShape:
    """Pin that count_tokens.py output parses into metadata_tokens + body_tokens."""

    def test_count_tokens_fixture_has_expected_keys(self) -> None:
        """count_tokens.yaml surfaces metadata_tokens + body_tokens scalars."""
        data = load_yaml_fixture("si-chip", "count_tokens.yaml")
        assert isinstance(data.get("metadata_tokens"), int)
        assert isinstance(data.get("body_tokens"), int)
        assert data["metadata_tokens"] == 87
        assert data["body_tokens"] == 3200
