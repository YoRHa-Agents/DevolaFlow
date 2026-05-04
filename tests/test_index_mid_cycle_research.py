"""Tests for ``scripts/index_mid_cycle_research.py`` (v10.7.0 D-O-3).

Pins the contract from `.local/research/v11.0.0_patches/D-O-3.md`:

* ARTIFACT_PATTERN matches ``vX.Y.Z_<topic>.md`` strictly + rejects
  edge-cases like ``nines_v2_analysis.md`` or ``v10.0.0_evaluation_methodology.md``
  (the latter is OK; the former is NOT in the version-prefix grammar).
* ``scan_research_artifacts`` returns the right shape on a synthetic
  fixture tree.
* ``filter_artifacts`` honours ``--cycle`` and ``--category``.
* ``render_markdown`` produces non-empty output for both empty + populated
  inputs.
* ``group_by_cycle`` sorts within-cycle by version desc / topic asc.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load_index_module() -> object:
    repo_root = Path(__file__).resolve().parent.parent
    script = repo_root / "scripts" / "index_mid_cycle_research.py"
    name = "index_mid_cycle_research"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_INDEX = _load_index_module()


def _make_research_dir(root: Path, files: list[str]) -> Path:
    research = root / ".local" / "research"
    research.mkdir(parents=True, exist_ok=True)
    for filename in files:
        (research / filename).write_text("# stub artifact\n", encoding="utf-8")
    return research


def test_artifact_pattern_strict_matching() -> None:
    """Strict regex MUST match canonical patterns + reject edge cases."""
    matches = [
        "v10.7.0_retrospective.md",
        "v10.0.0_evaluation_methodology.md",
        "v8.2.4_w8_stagnation_check.md",
        "v9.7.0_pv02_design.md",
    ]
    rejects = [
        "nines_v2_analysis.md",  # no version prefix
        "v10.7.0_.md",  # empty topic
        "v10.7.0.md",  # no underscore + topic
        "v10.7.0_Topic.md",  # uppercase rejected
        "v10.0_thing.md",  # missing patch digit
    ]
    for ok in matches:
        assert _INDEX.ARTIFACT_PATTERN.match(ok) is not None, f"should match: {ok}"
    for bad in rejects:
        assert _INDEX.ARTIFACT_PATTERN.match(bad) is None, f"should reject: {bad}"


def test_scan_returns_artifacts_grouped_by_cycle(tmp_path: Path) -> None:
    """Synthetic tree → 5 artifacts; group_by_cycle splits them correctly."""
    _make_research_dir(
        tmp_path,
        [
            "v10.7.0_retrospective.md",
            "v10.7.0_pv02_design.md",
            "v10.7.1_canonical_order_emptiness.md",  # patch-of-cycle
            "v10.6.0_retrospective.md",
            "nines_v2_analysis.md",  # NOT versioned → excluded
        ],
    )
    artifacts = _INDEX.scan_research_artifacts(tmp_path / ".local" / "research")
    assert len(artifacts) == 4
    by_cycle = _INDEX.group_by_cycle(artifacts)
    assert set(by_cycle.keys()) == {"10.7.0", "10.6.0"}
    assert len(by_cycle["10.7.0"]) == 3
    assert len(by_cycle["10.6.0"]) == 1
    # Within v10.7.0: descending version order — v10.7.1 first, then v10.7.0 entries.
    versions = [a.version for a in by_cycle["10.7.0"]]
    assert versions[0] == "10.7.1"


def test_filter_by_cycle_and_category(tmp_path: Path) -> None:
    """Filters compose correctly."""
    _make_research_dir(
        tmp_path,
        [
            "v10.7.0_retrospective.md",
            "v10.7.0_evaluation.md",
            "v10.7.0_pv02_design.md",
            "v10.6.0_retrospective.md",
        ],
    )
    artifacts = _INDEX.scan_research_artifacts(tmp_path / ".local" / "research")
    only_107 = _INDEX.filter_artifacts(artifacts, cycle="v10.7.0")
    assert all(a.cycle == "10.7.0" for a in only_107)
    assert len(only_107) == 3

    only_retro = _INDEX.filter_artifacts(artifacts, category="retrospective")
    assert all(a.category == "retrospective" for a in only_retro)
    assert len(only_retro) == 2

    composed = _INDEX.filter_artifacts(artifacts, cycle="v10.7.0", category="retrospective")
    assert len(composed) == 1
    assert composed[0].path.name == "v10.7.0_retrospective.md"


def test_render_markdown_handles_empty_and_populated(tmp_path: Path) -> None:
    """Empty input → renders empty-state notice; populated → carries cycle headers."""
    research = _make_research_dir(tmp_path, [])
    artifacts = _INDEX.scan_research_artifacts(research)
    body = _INDEX.render_markdown(artifacts)
    assert "Total artifacts: **0**" in body
    assert "No research artifacts" in body

    _make_research_dir(tmp_path, ["v10.7.0_retrospective.md"])
    artifacts = _INDEX.scan_research_artifacts(research)
    body = _INDEX.render_markdown(artifacts)
    assert "## v10.7.0" in body
    assert "Total artifacts: **1**" in body
    # The W-19 boundary disclaimer MUST be present (R-1 mitigation).
    assert "ephemeral" in body
    assert "docs/cycle-archive" in body


def test_render_json_round_trips(tmp_path: Path) -> None:
    """JSON shape matches the documented schema."""
    _make_research_dir(
        tmp_path,
        [
            "v10.7.0_retrospective.md",
            "v10.7.0_evaluation.md",
        ],
    )
    artifacts = _INDEX.scan_research_artifacts(tmp_path / ".local" / "research")
    body = _INDEX.render_json(artifacts)
    payload = json.loads(body)
    assert payload["artifact_count"] == 2
    assert len(payload["artifacts"]) == 2
    for art in payload["artifacts"]:
        assert set(art.keys()) >= {
            "path",
            "cycle",
            "version",
            "topic",
            "mtime_iso",
            "category",
        }
        assert art["cycle"] == "10.7.0"


def test_categorize_handles_documented_kinds(tmp_path: Path) -> None:
    """Each topic keyword maps to the documented category."""
    _make_research_dir(
        tmp_path,
        [
            "v10.7.0_retrospective.md",  # → retrospective
            "v10.7.0_gap_analysis.md",  # → gap_analysis
            "v10.7.0_cycle_plan.md",  # → cycle_plan
            "v10.7.0_evaluation.md",  # → evaluation
            "v10.7.0_pv02_design.md",  # → pds
            "v10.7.0_nines.md",  # → nines
            "v10.7.0_canonical_order_emptiness.md",  # → audit
            "v10.7.0_random_topic.md",  # → other
        ],
    )
    artifacts = _INDEX.scan_research_artifacts(tmp_path / ".local" / "research")
    cat_by_topic = {a.topic: a.category for a in artifacts}
    assert cat_by_topic["retrospective"] == "retrospective"
    assert cat_by_topic["gap_analysis"] == "gap_analysis"
    assert cat_by_topic["cycle_plan"] == "cycle_plan"
    assert cat_by_topic["evaluation"] == "evaluation"
    assert cat_by_topic["pv02_design"] == "pds"
    assert cat_by_topic["nines"] == "nines"
    assert cat_by_topic["canonical_order_emptiness"] == "audit"
    assert cat_by_topic["random_topic"] == "other"
