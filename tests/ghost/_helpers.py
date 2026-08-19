"""Shared helpers for the ``tests/ghost/`` audit package.

Moved verbatim from ``tests/test_no_ghost_features.py`` per
``docs/cycle-archive/adr/v15-ADR-001-ghost-audit-decomposition.md``
(v14.3.0 split). Pure utilities only — shared *pins* (SF-4 set, SSOT
registries, rule-cap constants) live in their domain owner modules.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(_read(path))


def _resolve_artifact_path(
    project_root: Path,
    local_path: Path,
    archive_candidates: tuple[Path, ...],
) -> Path:
    """Return a local research artifact or its committed W-19 archive copy."""
    for rel_path in (local_path, *archive_candidates):
        candidate = project_root / rel_path
        if candidate.is_file():
            return candidate

    searched = ", ".join(str(path) for path in (local_path, *archive_candidates))
    pytest.fail(f"W-18 research artifact missing; expected one of: {searched}")


_W18_RESEARCH_ARCHIVE_CANDIDATES: dict[Path, tuple[Path, ...]] = {
    Path(".local/research/v10.2.1_dogfood_pass1.md"): (
        Path("docs/cycle-archive/v10.3.0/other/v10.2.1_dogfood_pass1.md"),
    ),
    Path(".local/research/v10.2.2_nines.json"): (
        Path("docs/cycle-archive/v10.3.0/nines/v10.2.2_nines.json"),
    ),
    Path(".local/research/v10.2.2_nines_plugins.json"): (
        Path("docs/cycle-archive/v10.3.0/nines/v10.2.2_nines_plugins.json"),
    ),
    Path(".local/research/v10.2.2_nines_lifecycle.json"): (
        Path("docs/cycle-archive/v10.3.0/nines/v10.2.2_nines_lifecycle.json"),
    ),
    Path(".local/research/v10.2.2_nines.md"): (
        Path("docs/cycle-archive/v10.3.0/nines/v10.2.2_nines.md"),
    ),
    Path(".local/research/v10.2.2_dogfood_pass2.md"): (
        Path("docs/cycle-archive/v10.3.0/other/v10.2.2_dogfood_pass2.md"),
    ),
    Path(".local/research/v10.2.3_dogfood_pass3.md"): (
        Path("docs/cycle-archive/v10.3.0/other/v10.2.3_dogfood_pass3.md"),
    ),
    Path(".local/research/v10.2.3_iteration_round1.md"): (
        Path("docs/cycle-archive/v10.3.0/other/v10.2.3_iteration_round1.md"),
    ),
    Path(".local/research/v10.2.4_iteration_round2.md"): (
        Path("docs/cycle-archive/v10.3.0/other/v10.2.4_iteration_round2.md"),
    ),
    Path(".local/research/v10.2.4_w17_mid_cycle_audit.md"): (
        Path("docs/cycle-archive/v10.3.0/other/v10.2.4_w17_mid_cycle_audit.md"),
    ),
    Path(".local/research/v10.2.4_w8_stagnation_check.md"): (
        Path("docs/cycle-archive/v10.3.0/other/v10.2.4_w8_stagnation_check.md"),
    ),
    Path(".local/research/v10.2.4_dogfood_pass4.md"): (
        Path("docs/cycle-archive/v10.3.0/other/v10.2.4_dogfood_pass4.md"),
    ),
    Path(".local/research/v10.3.0_evaluation.md"): (
        Path("docs/cycle-archive/v10.3.0/evaluation/v10.3.0_evaluation.md"),
    ),
    Path(".local/research/v10.3.0_retrospective.md"): (
        Path("docs/cycle-archive/v10.3.0/v10.3.0_retrospective.md"),
    ),
    Path(".local/research/v10.3.0_nines.json"): (
        Path("docs/cycle-archive/v10.3.0/nines/v10.3.0_nines.json"),
    ),
    Path(".local/research/v10.3.0_nines.md"): (
        Path("docs/cycle-archive/v10.3.0/nines/v10.3.0_nines.md"),
    ),
    Path(".local/research/v10.4.0_retrospective.md"): (
        Path("docs/cycle-archive/v11.0.0/v10.4.0_retrospective.md"),
    ),
    Path(".local/research/v10.4.1_reference_utilization.md"): (
        Path("docs/cycle-archive/v11.0.0/other/v10.4.1_reference_utilization.md"),
    ),
    Path(".local/research/v10.4.2_long_reference_usage.md"): (
        Path("docs/cycle-archive/v11.0.0/other/v10.4.2_long_reference_usage.md"),
    ),
    Path(".local/research/v10.5.0_retrospective.md"): (
        Path("docs/cycle-archive/v11.0.0/v10.5.0_retrospective.md"),
    ),
    Path(".local/research/v10.5.1_layer_usage_audit.md"): (
        Path("docs/cycle-archive/v11.0.0/other/v10.5.1_layer_usage_audit.md"),
    ),
    Path(".local/research/v10.5.2_template_usage_audit.md"): (
        Path("docs/cycle-archive/v11.0.0/other/v10.5.2_template_usage_audit.md"),
    ),
    Path(".local/research/v10.5.3_reference_friction.md"): (
        Path("docs/cycle-archive/v11.0.0/other/v10.5.3_reference_friction.md"),
    ),
    Path(".local/research/v10.5.4_w18_lint_audit.md"): (
        Path("docs/cycle-archive/v11.0.0/other/v10.5.4_w18_lint_audit.md"),
    ),
    Path(".local/research/v10.6.0_compressor_health.md"): (
        Path("docs/cycle-archive/v11.0.0/other/v10.6.0_compressor_health.md"),
    ),
    Path(".local/research/v10.6.0_retrospective.md"): (
        Path("docs/cycle-archive/v11.0.0/v10.6.0_retrospective.md"),
    ),
    Path(".local/research/v10.7.0_retrospective.md"): (
        Path("docs/cycle-archive/v11.0.0/v10.7.0_retrospective.md"),
    ),
    Path(".local/research/v10.7.1_canonical_order_emptiness.md"): (
        Path("docs/cycle-archive/v11.0.0/other/v10.7.1_canonical_order_emptiness.md"),
    ),
    Path(".local/research/v10.7.2_evaluator_rosetta.md"): (
        Path("docs/cycle-archive/v11.0.0/other/v10.7.2_evaluator_rosetta.md"),
    ),
    Path(".local/research/v10.7.3_si3_auto_collection.md"): (
        Path("docs/cycle-archive/v11.0.0/other/v10.7.3_si3_auto_collection.md"),
    ),
    Path(".local/research/v10.7.4_research_index.md"): (
        Path("docs/cycle-archive/v11.0.0/other/v10.7.4_research_index.md"),
    ),
    Path(".local/research/v10.8.0_retrospective.md"): (
        Path("docs/cycle-archive/v11.0.0/v10.8.0_retrospective.md"),
    ),
    Path(".local/research/v11.0.0_w21_threshold_empirical_check.md"): (
        Path("docs/cycle-archive/v11.0.0/other/v11.0.0_w21_threshold_empirical_check.md"),
    ),
    Path(".local/research/v11.0.0_si10_gate_growth_analysis.md"): (
        Path("docs/cycle-archive/v11.0.0/other/v11.0.0_si10_gate_growth_analysis.md"),
    ),
    Path(".local/research/v11.0.0_retrospective.md"): (
        Path("docs/cycle-archive/v11.0.0/v11.0.0_retrospective.md"),
        Path("docs/cycle-archive/v11.0.0/retrospective.md"),
    ),
    Path(".local/research/v11.0.0_evaluation.md"): (
        Path("docs/cycle-archive/v11.0.0/evaluation/v11.0.0_evaluation.md"),
    ),
}


def _w18_research_artifact_path(project_root: Path, local_path: Path) -> Path:
    archive_candidates = _W18_RESEARCH_ARCHIVE_CANDIDATES.get(local_path)
    if archive_candidates is None:
        pytest.fail(f"W-18 archive mapping missing for research artifact: {local_path}")
    return _resolve_artifact_path(project_root, local_path, archive_candidates)
