"""NineS bridge shape contract tests.

Pins the v10.8.0 D-C-2 contract: DevolaFlow's NineS adapter
(`scripts/nines_to_sichip_eval_adapter.py`) correctly parses REAL NineS
JSON output captured at a pinned version.

The fixtures under ``tests/integration/fixtures/nines/`` carry the R1
version header mandated by D-C-2 §9 R1 mitigation; a schema-drift
between upstream NineS minor releases will fail these tests loudly.

Canonical NineS URL: https://github.com/YoRHa-Agents/NineS
"""

from __future__ import annotations

from tests.integration.conftest import load_json_fixture


class TestNineSAnalyzeShape:
    """Pin the shape of ``nines analyze`` JSON output."""

    def test_analyze_has_expected_top_level_blocks(self) -> None:
        """analyze output carries summary + findings + agent_impact + keypoints."""
        data = load_json_fixture("nines", "analyze_output.json")
        # Summary with file / line counts.
        summary = data.get("summary")
        assert isinstance(summary, dict)
        assert isinstance(summary.get("total_files"), int)
        assert summary["total_files"] > 0
        # Findings list with per-function cc integer.
        findings = data.get("findings")
        assert isinstance(findings, list)
        for finding in findings:
            assert "cc" in finding
            assert isinstance(finding["cc"], int)
        # agent_impact + keypoints.
        agent_impact = data.get("agent_impact")
        assert isinstance(agent_impact, dict)
        assert isinstance(agent_impact.get("suggested_agent"), str)
        keypoints = data.get("keypoints")
        assert isinstance(keypoints, list)


class TestNineSSelfEvalShape:
    """Pin the shape of ``nines self-eval`` JSON output.

    This is the adapter target for `scripts/nines_to_sichip_eval_adapter.py`:
    the adapter expects a top-level ``scores`` array with a
    ``scoring_accuracy`` entry whose ``metadata.details`` provides per-task
    entries.
    """

    def test_self_eval_has_scores_array_with_required_dims(self) -> None:
        data = load_json_fixture("nines", "self_eval_output.json")
        scores = data.get("scores")
        assert isinstance(scores, list)
        assert len(scores) >= 4, f"expected >= 4 score entries (SI-3 6-dim); got {len(scores)}"

    def test_scoring_accuracy_has_per_task_metadata_details(self) -> None:
        """Adapter precondition: ``scoring_accuracy.metadata.details`` is a dict.

        Consolidates the adapter-preconditions + required-keys checks from
        the original 3 tests into one per-task validation.
        """
        data = load_json_fixture("nines", "self_eval_output.json")
        scores = data.get("scores") or []
        scoring_accuracy = next(
            (s for s in scores if s.get("id") == "scoring_accuracy"),
            None,
        )
        assert scoring_accuracy is not None, (
            "missing 'scoring_accuracy' score — adapter expects this entry "
            "per `scripts/nines_to_sichip_eval_adapter.py::validate_nines_shape`"
        )
        metadata = scoring_accuracy.get("metadata") or {}
        details = metadata.get("details")
        assert isinstance(details, dict)
        assert len(details) > 0
        # Per-task entries carry required keys.
        required = {"nines_score", "golden_score", "delta", "accurate", "scorer"}
        for task_id, task_data in details.items():
            missing = required - set(task_data.keys())
            assert not missing, (
                f"per-task entry {task_id} missing keys: {sorted(missing)}. "
                f"Adapter requires all of: {sorted(required)}"
            )

    def test_composite_verdict_and_score_ranges(self) -> None:
        """Top-level composite (float) + verdict (str) + score range [0, 10]."""
        data = load_json_fixture("nines", "self_eval_output.json")
        assert isinstance(data.get("composite"), (int, float))
        assert isinstance(data.get("verdict"), str)
        # Per-dim scores must land in [0.0, 10.0].
        scores = data.get("scores") or []
        for entry in scores:
            if entry.get("id") == "scoring_accuracy":
                continue
            score = entry.get("score")
            assert isinstance(score, (int, float))
            assert 0.0 <= score <= 10.0
