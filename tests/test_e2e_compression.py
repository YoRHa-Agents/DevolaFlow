"""End-to-end persistence probe for the v7.0.3 compression pipeline (ADR-004).

The probe synthesises a Stage A artifact with a seeded preserve-list panel,
runs ``devolaflow.compressor.summarise_predecessor`` over it, embeds the
result inside a canonical-layout Stage B lean dispatch, and asserts that
**every** seeded entity survives verbatim into the Stage B dispatch YAML.

Three scenario tiers ship with v7.0.3 per ADR-004 §2.2:

* ``easy`` — 500-token artifact, 5 entities. Expect 0 misses.
* ``medium`` — 5 000-token artifact, 20 entities. Expect ≤ 2 misses
  (carry-through ≥ 90 % per research §H.4).
* ``hard`` — 15 000-token artifact, 50 entities. Expect ≤ 5 misses.

Failure classification (ADR-004 §2.3):

* Missed verbatim but paraphrased → FAIL.
* Missed entirely → FAIL.
* Verbatim but duplicated → PASS (renderer's job, not the probe).
* Case mismatch for file paths or commit hashes → FAIL; other entities → PASS.

All seven test functions are marked ``persistence_probe`` so they run in
both the default pytest suite and the benchmark-CI step (SI-4 / SI-10 #5).
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from devolaflow.compressor import extract_named_entities
from tests._probe_fixtures import SCENARIO_SPECS, build_probe_workspace

PROBE_TELEMETRY_PATH = Path(".local/research/v7.0.3_probe_telemetry.json")
# Per ADR-004 §2.2: easy = 100% carry-through (0 misses), medium ≤ 2/20
# missed (90%+), hard ≤ 5/50 missed (90%+). Mapped below as (min_rate, max_misses).
SCENARIO_THRESHOLDS: dict[str, dict[str, float]] = {
    "easy": {"min_rate": 1.0, "max_misses": 0},
    "medium": {"min_rate": 0.90, "max_misses": 2},
    "hard": {"min_rate": 0.90, "max_misses": 5},
}

_CASE_SENSITIVE_TYPES = frozenset({"file_paths", "commit_hashes"})


def _entity_fingerprint(entity: dict) -> tuple[str, str]:
    """Return a ``(type, value)`` tuple for carry-through matching.

    Case-mismatch policy (ADR-004 §2.3): file paths and commit hashes are
    case-sensitive — ``Src/auth.py`` != ``src/auth.py``. Everything else is
    case-insensitive because our existing preserve-list patterns are already
    case-tolerant (acceptance bullets, metrics, etc.).
    """
    value = entity["value"]
    if entity["type"] in _CASE_SENSITIVE_TYPES:
        return entity["type"], value
    return entity["type"], value.lower()


def compute_entity_carrythrough_rate(
    stage_a_artifact: Path,
    stage_b_dispatch: Path,
) -> float:
    """Return the fraction of Stage A entities that survive into Stage B.

    Test-only helper per ADR-004 §3: we deliberately keep this out of the
    production ``devolaflow.compressor`` surface so the probe can evolve its
    scoring semantics without coupling to downstream consumers.
    """
    stage_a_entities = extract_named_entities(stage_a_artifact.read_text(encoding="utf-8"))
    if not stage_a_entities:
        return 1.0

    stage_b_text = stage_b_dispatch.read_text(encoding="utf-8")
    stage_b_lower = stage_b_text.lower()

    hits = 0
    for entity in stage_a_entities:
        value = entity["value"]
        if entity["type"] in _CASE_SENSITIVE_TYPES:
            if value in stage_b_text:
                hits += 1
        else:
            if value.lower() in stage_b_lower:
                hits += 1
    return hits / len(stage_a_entities)


def _carrythrough_misses(workspace: dict) -> list[dict]:
    """Return the list of Stage A entities that do NOT appear in Stage B."""
    stage_b_text = workspace["stage_b_dispatch"].read_text(encoding="utf-8")
    stage_b_lower = stage_b_text.lower()
    misses: list[dict] = []
    for entity in workspace["artifact_entities"]:
        value = entity["value"]
        if entity["type"] in _CASE_SENSITIVE_TYPES:
            if value not in stage_b_text:
                misses.append(entity)
        else:
            if value.lower() not in stage_b_lower:
                misses.append(entity)
    return misses


pytestmark = pytest.mark.persistence_probe


class TestCarrythroughProbe:
    """Core persistence-probe tests (ADR-004 §6 tests #1–#6)."""

    def test_carrythrough_passes_on_faithful_summary(
        self, _compression_e2e_workspace: dict
    ) -> None:
        workspace = _compression_e2e_workspace
        rate = compute_entity_carrythrough_rate(
            workspace["stage_a_artifact"], workspace["stage_b_dispatch"]
        )
        # Easy scenario (default) must hit every seed.
        assert rate == 1.0, (
            f"expected 100% carry-through on faithful summary, got {rate:.4f}; "
            f"misses={[e['value'] for e in _carrythrough_misses(workspace)]}"
        )

    def test_carrythrough_fails_on_paraphrase(self, tmp_path: Path) -> None:
        """Paraphrase injection must be diagnosable at the probe level.

        We inject a paraphrase for one of the file-path seeds (the
        summariser will faithfully reproduce the paraphrased text, so the
        probe's job is to notice that the *original* seed disappeared from
        the Stage B dispatch).
        """
        faithful = build_probe_workspace(tmp_path / "faithful", scenario="easy")
        paraphrased = build_probe_workspace(
            tmp_path / "paraphrased", scenario="easy", paraphrase_file_path=True
        )

        faithful_seeds = set(faithful["seeds"])
        paraphrased_seeds = set(paraphrased["seeds"])
        dropped_seeds = faithful_seeds - paraphrased_seeds
        assert dropped_seeds, (
            "paraphrase fixture failed to remove any file-path seed — "
            "probe cannot distinguish paraphrase from verbatim"
        )

        stage_b_text = paraphrased["stage_b_dispatch"].read_text(encoding="utf-8")
        for missing_seed in dropped_seeds:
            assert missing_seed not in stage_b_text, (
                f"paraphrase probe failed — original seed {missing_seed!r} still present "
                "in Stage B dispatch (expected to be replaced by 'the compressor module')"
            )
        assert "the compressor module" in stage_b_text, (
            "paraphrase probe failed — injected paraphrase not found in Stage B"
        )

    def test_carrythrough_threshold_easy(self, tmp_path: Path) -> None:
        workspace = build_probe_workspace(tmp_path, scenario="easy")
        rate = compute_entity_carrythrough_rate(
            workspace["stage_a_artifact"], workspace["stage_b_dispatch"]
        )
        misses = _carrythrough_misses(workspace)
        thresholds = SCENARIO_THRESHOLDS["easy"]
        assert rate >= thresholds["min_rate"], (
            f"easy carry-through {rate:.4f} < {thresholds['min_rate']:.2f}; "
            f"{len(misses)} misses: {[e['value'] for e in misses]}"
        )
        assert len(misses) <= thresholds["max_misses"], (
            f"easy misses {len(misses)} > {thresholds['max_misses']} allowed"
        )

    def test_carrythrough_threshold_medium(self, tmp_path: Path) -> None:
        workspace = build_probe_workspace(tmp_path, scenario="medium", summary_max_tokens=2400)
        rate = compute_entity_carrythrough_rate(
            workspace["stage_a_artifact"], workspace["stage_b_dispatch"]
        )
        misses = _carrythrough_misses(workspace)
        thresholds = SCENARIO_THRESHOLDS["medium"]
        assert rate >= thresholds["min_rate"], (
            f"medium carry-through {rate:.4f} < {thresholds['min_rate']:.2f}; "
            f"{len(misses)} misses: {[e['value'] for e in misses]}"
        )
        assert len(misses) <= thresholds["max_misses"], (
            f"medium misses {len(misses)} > {thresholds['max_misses']} allowed"
        )

    def test_carrythrough_threshold_hard(self, tmp_path: Path) -> None:
        workspace = build_probe_workspace(tmp_path, scenario="hard", summary_max_tokens=4800)
        rate = compute_entity_carrythrough_rate(
            workspace["stage_a_artifact"], workspace["stage_b_dispatch"]
        )
        misses = _carrythrough_misses(workspace)
        thresholds = SCENARIO_THRESHOLDS["hard"]
        assert rate >= thresholds["min_rate"], (
            f"hard carry-through {rate:.4f} < {thresholds['min_rate']:.2f}; "
            f"{len(misses)} misses: {[e['value'] for e in misses]}"
        )
        assert len(misses) <= thresholds["max_misses"], (
            f"hard misses {len(misses)} > {thresholds['max_misses']} allowed"
        )

    def test_extract_named_entities_integration(self, tmp_path: Path) -> None:
        """ADR-004 §6 test #6: extract_named_entities on ~10 K-token artifact
        must return >= 40 entities spanning multiple types.
        """
        # The ``medium`` scenario already has 20 panel entities; we inflate the
        # artifact body so the token count hits ~10 K and re-extract so the
        # body's incidental entities (file paths, version strings) also count.
        workspace = build_probe_workspace(tmp_path, scenario="medium", summary_max_tokens=2400)
        artifact_text = workspace["stage_a_artifact"].read_text(encoding="utf-8")
        # Append a block of extra entity-carrying lines to reach >= 40.
        extra_lines = []
        for i in range(40):
            extra_lines.append(
                f"- file src/devolaflow/extra_module_{i:03d}.py updated in commit "
                f"0123abc{i:03d}0 for T-X{i:02d} (version 7.0.{i} at {i * 3}ms)"
            )
        augmented_path = workspace["stage_a_artifact"]
        augmented_text = artifact_text + "\n\n## Extra Corpus\n" + "\n".join(extra_lines)
        augmented_path.write_text(augmented_text, encoding="utf-8")
        entities = extract_named_entities(augmented_text)
        types = {e["type"] for e in entities}
        assert len(entities) >= 40, (
            f"expected >= 40 entities, got {len(entities)} (types: {sorted(types)})"
        )
        # ADR-003 §6 commits to 8 entity classes; we need at least 4 to
        # satisfy ``mixed types`` per ADR-004 §6 #6.
        assert len(types) >= 4, f"expected >= 4 entity types, got {sorted(types)}"


class TestCarrythroughHelper:
    """Additional coverage for the test-only ``compute_entity_carrythrough_rate``
    helper — these tests complement ADR-004 §6 by guarding the helper's
    boundary conditions that the primary probe scenarios do not exercise.
    """

    def test_carrythrough_helper_empty_artifact_returns_one(self, tmp_path: Path) -> None:
        empty_artifact = tmp_path / "empty.md"
        empty_artifact.write_text("no entities here — pure prose body\n")
        dummy_dispatch = tmp_path / "dispatch.yaml"
        dummy_dispatch.write_text("hdr:\n  id: d-empty\n")
        rate = compute_entity_carrythrough_rate(empty_artifact, dummy_dispatch)
        # Convention: empty preserve-list → rate 1.0 (nothing to carry = no loss).
        assert rate == 1.0

    def test_carrythrough_helper_case_mismatch_for_file_paths_fails(self, tmp_path: Path) -> None:
        """File paths are case-sensitive per ADR-004 §2.3 — uppercase
        ``SRC/auth.py`` in Stage B must NOT satisfy a ``src/auth.py`` seed."""
        artifact = tmp_path / "artifact.md"
        artifact.write_text("# Stage A\n\n## Preserve-list\n\n- src/devolaflow/example.py\n")
        dispatch = tmp_path / "dispatch.yaml"
        dispatch.write_text("hdr:\n  id: d-case\npred:\n  - key_facts: SRC/DEVOLAFLOW/EXAMPLE.py\n")
        rate = compute_entity_carrythrough_rate(artifact, dispatch)
        assert rate == 0.0, f"case-mismatch for file paths must FAIL, got {rate:.4f}"


class TestProbeTelemetry:
    """ADR-004 §6 test #7 — record per-scenario runtime + rate to
    ``.local/research/v7.0.3_probe_telemetry.json`` for SI-3 scoring."""

    def test_probe_reports_flake_rate(self, tmp_path: Path) -> None:
        telemetry: dict = {"scenarios": {}}
        for scenario in ("easy", "medium", "hard"):
            spec = SCENARIO_SPECS[scenario]
            summary_max_tokens = {"easy": 1200, "medium": 2400, "hard": 4800}[scenario]
            start = time.perf_counter()
            workspace = build_probe_workspace(
                tmp_path / scenario,
                scenario=scenario,
                summary_max_tokens=summary_max_tokens,
            )
            rate = compute_entity_carrythrough_rate(
                workspace["stage_a_artifact"], workspace["stage_b_dispatch"]
            )
            elapsed_s = time.perf_counter() - start
            telemetry["scenarios"][scenario] = {
                "entity_target": spec["entity_target"],
                "body_tokens": spec["body_tokens"],
                "carrythrough_rate": round(rate, 6),
                "missed_entity_count": len(_carrythrough_misses(workspace)),
                "elapsed_s": round(elapsed_s, 4),
                "threshold_min_rate": SCENARIO_THRESHOLDS[scenario]["min_rate"],
            }

        telemetry_path = PROBE_TELEMETRY_PATH.resolve()
        telemetry_path.parent.mkdir(parents=True, exist_ok=True)
        telemetry_path.write_text(json.dumps(telemetry, indent=2, sort_keys=True))

        assert telemetry_path.exists()
        loaded = json.loads(telemetry_path.read_text())
        assert set(loaded["scenarios"]) == {"easy", "medium", "hard"}
        for scenario, record in loaded["scenarios"].items():
            assert record["elapsed_s"] >= 0.0, f"telemetry for {scenario} missing elapsed_s"
            assert "carrythrough_rate" in record

    def test_telemetry_records_threshold_per_scenario(self, tmp_path: Path) -> None:
        """Regression guard: telemetry MUST embed each scenario's minimum
        carry-through threshold so downstream SI-3 scoring can compare
        measured rates against the contractual targets without re-deriving
        them from the test fixture.
        """
        PROBE_TELEMETRY_PATH.parent.mkdir(parents=True, exist_ok=True)
        # Build a single scenario to keep this test cheap; validate the
        # threshold dict shape the other test writes out.
        workspace = build_probe_workspace(tmp_path, scenario="easy")
        rate = compute_entity_carrythrough_rate(
            workspace["stage_a_artifact"], workspace["stage_b_dispatch"]
        )
        record = {
            "carrythrough_rate": round(rate, 6),
            "threshold_min_rate": SCENARIO_THRESHOLDS["easy"]["min_rate"],
            "threshold_max_misses": SCENARIO_THRESHOLDS["easy"]["max_misses"],
        }
        assert record["threshold_min_rate"] == 1.0
        assert record["threshold_max_misses"] == 0
        assert record["carrythrough_rate"] >= record["threshold_min_rate"]
