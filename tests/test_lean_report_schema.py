"""Doctrine pins for schemas/lean-report.yaml metrics (v14.2.1 G-013)
and the v14.3.0-era L2 evidence blocks (G-002 + G-003, per v15-ADR-007).

G-013 (v14.2.1) closes `.local/research/v14.2.0_gap_analysis.md` §2.3
(source finding F-P4-3): the lean StatusReport spec used to define
``metrics.quality``, contradicting the SKILL.md / task-quality-score.md
doctrine "Subagent reports DO NOT include `quality_score` (L0-only)".

Pinned contract:

* The metrics field is named ``gate_input_score`` — gate-dimension input
  evidence — in the lean spec, the lean example, AND the verbose
  original example. Neither ``quality`` nor ``quality_score`` may
  reappear in any report-metrics block of this file.
* The schema carries the doctrine note distinguishing the field from the
  L0-only Task Quality Score (``references/task-quality-score.md``).

The ``reject_subagent_quality_score`` pre_dispatch hook keeps checking
only the TOP-LEVEL ``quality_score`` key (strict graduation is a later
rung); these pins are schema-side only.

G-002 + G-003 (v14.3.0) close `.local/research/v14.2.0_gap_analysis.md`
§2.1 (source findings F-P4-2 / F-P4-6): the behavioral-guidelines
evidence (BG-001 ``plan_artifact``, BG-004 ``goal_anchor``, BG-002
simplicity audit, BG-006/BG-007 typed findings) and the per-AC verdict /
diff-stat evidence had no transport in ``lean_format_spec``. Pinned
contract:

* ``lean_format_spec.self_check`` carries all five evidence fields.
* ``lean_format_spec.ac_results`` per-entry shape is
  ``{id, verdict, cmd_digest}`` with the ``pass|fail|skip`` verdict enum.
* ``lean_format_spec.diff_stats`` carries ``{files, insertions, deletions}``.
* The lean example exercises all three blocks.
* Doctrine guard (v15-ADR-007: L3 emits EVIDENCE ONLY — never scores):
  no ``quality_score``/``quality`` key anywhere in the spec or example,
  and the three evidence blocks define no score-named field — coherent
  with the ``reject_subagent_quality_score`` pre_dispatch hook.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import yaml

LEAN_REPORT_PATH = Path(__file__).resolve().parent.parent / "schemas" / "lean-report.yaml"

SELF_CHECK_FIELDS = ("plan_artifact", "goal_anchor", "simplicity", "conflicts", "conventions")


def _load() -> dict[str, Any]:
    return yaml.safe_load(LEAN_REPORT_PATH.read_text(encoding="utf-8"))


def _walk_keys(node: Any) -> Iterator[str]:
    """Yield every dict key (at any depth) inside *node*."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield str(key)
            yield from _walk_keys(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk_keys(item)


def test_report_metrics_use_gate_input_score_not_quality() -> None:
    """All three metrics blocks carry gate_input_score; quality* is gone."""
    doc = yaml.safe_load(LEAN_REPORT_PATH.read_text(encoding="utf-8"))

    spec_fields = doc["lean_format_spec"]["metrics"]["fields"]
    lean_metrics = doc["lean_example"]["metrics"]
    original_metrics = doc["original_example"]["result"]["metrics"]

    for label, block in (
        ("lean_format_spec.metrics.fields", spec_fields),
        ("lean_example.metrics", lean_metrics),
        ("original_example.result.metrics", original_metrics),
    ):
        assert "gate_input_score" in block, (
            f"G-013 regression: {label} is missing `gate_input_score` "
            f"(the v14.2.1 rename of the doctrine-violating `quality` field)."
        )
        assert "quality" not in block and "quality_score" not in block, (
            f"G-013 regression: {label} carries a quality/quality_score key — "
            f"subagent reports DO NOT include a quality score "
            f"(L0-only per references/task-quality-score.md)."
        )


def test_report_metrics_doctrine_note_present() -> None:
    """The inline 'NOT the Task Quality Score' note ships with the rename."""
    text = LEAN_REPORT_PATH.read_text(encoding="utf-8")
    assert "NOT the Task Quality" in text, (
        "G-013 regression: lean-report.yaml lost the doctrine note "
        "'gate-dimension input evidence — NOT the Task Quality Score'."
    )
    assert "references/task-quality-score.md" in text, (
        "G-013 regression: the doctrine note must cite "
        "references/task-quality-score.md (the L0-only scoring rubric)."
    )


# ---------------------------------------------------------------------------
# v14.3.0 G-002 — self_check evidence transport
# ---------------------------------------------------------------------------


def test_lean_format_spec_defines_self_check_block() -> None:
    """lean_format_spec.self_check carries all five BG evidence fields."""
    doc = _load()
    assert "self_check" in doc["lean_format_spec"], (
        "G-002 regression: lean_format_spec is missing the `self_check` "
        "evidence-transport block (BG-001/002/004/006/007)."
    )
    spec = doc["lean_format_spec"]["self_check"]
    for field in SELF_CHECK_FIELDS:
        assert field in spec["fields"], (
            f"G-002 regression: lean_format_spec.self_check.fields is missing "
            f"`{field}` — the behavioral-guidelines evidence has no transport."
        )
        assert "optional" in str(spec["fields"][field]).lower(), (
            f"G-002 regression: self_check.{field} must carry an explicit "
            f"'optional' marker (lean convention for non-required fields)."
        )


# ---------------------------------------------------------------------------
# v14.3.0 G-003 — ac_results + diff_stats evidence transport
# ---------------------------------------------------------------------------


def test_lean_format_spec_defines_ac_results_and_diff_stats() -> None:
    """lean_format_spec carries the per-AC verdict and diff-stat blocks."""
    doc = _load()
    spec = doc["lean_format_spec"]

    assert "ac_results" in spec, (
        "G-003 regression: lean_format_spec is missing the `ac_results` block."
    )
    per_entry = spec["ac_results"]["per_entry"]
    assert set(per_entry) == {"id", "verdict", "cmd_digest"}, (
        f"G-003 regression: ac_results.per_entry must be exactly "
        f"{{id, verdict, cmd_digest}}; got {sorted(per_entry)}."
    )
    assert "acceptance_criteria_v2" in str(spec["ac_results"]), (
        "G-003 regression: ac_results must be keyed to dispatch acceptance_criteria_v2 ids."
    )
    assert "execution-protocol.md" in str(spec["ac_results"]["description"]), (
        "G-003 regression: ac_results must cross-reference the self-verify "
        "protocol in references/execution-protocol.md (verdict provenance: "
        "the L3 actually ran verification_cmd)."
    )

    assert "diff_stats" in spec, (
        "G-003 regression: lean_format_spec is missing the `diff_stats` block."
    )
    assert set(spec["diff_stats"]["fields"]) == {"files", "insertions", "deletions"}, (
        f"G-003 regression: diff_stats.fields must be exactly "
        f"{{files, insertions, deletions}}; got {sorted(spec['diff_stats']['fields'])}."
    )


def test_ac_results_verdict_enum() -> None:
    """The ac_results verdict spec pins the pass|fail|skip enum verbatim."""
    doc = _load()
    verdict_spec = doc["lean_format_spec"]["ac_results"]["per_entry"]["verdict"]
    assert verdict_spec == "pass|fail|skip", (
        f"G-003 regression: ac_results.per_entry.verdict must be the verbatim "
        f"enum 'pass|fail|skip'; got {verdict_spec!r}."
    )


def test_lean_example_carries_evidence_blocks() -> None:
    """The worked lean example parses and exercises all three new blocks."""
    doc = _load()
    example = doc["lean_example"]

    assert "self_check" in example, "G-002 regression: lean_example lacks self_check."
    assert set(SELF_CHECK_FIELDS) <= set(example["self_check"]), (
        f"G-002 regression: lean_example.self_check must carry all five fields "
        f"{SELF_CHECK_FIELDS}; got {sorted(example['self_check'])}."
    )

    assert "ac_results" in example, "G-003 regression: lean_example lacks ac_results."
    assert example["ac_results"], "G-003 regression: lean_example.ac_results is empty."
    for entry in example["ac_results"]:
        assert set(entry) == {"id", "verdict", "cmd_digest"}, (
            f"G-003 regression: lean_example.ac_results entry keys must be "
            f"{{id, verdict, cmd_digest}}; got {sorted(entry)}."
        )
        assert entry["verdict"] in ("pass", "fail", "skip"), (
            f"G-003 regression: lean_example ac_results verdict "
            f"{entry['verdict']!r} outside the pass|fail|skip enum."
        )

    assert "diff_stats" in example, "G-003 regression: lean_example lacks diff_stats."
    assert set(example["diff_stats"]) == {"files", "insertions", "deletions"}, (
        f"G-003 regression: lean_example.diff_stats keys must be "
        f"{{files, insertions, deletions}}; got {sorted(example['diff_stats'])}."
    )


# ---------------------------------------------------------------------------
# v14.3.0 doctrine guard — evidence only, never scores (v15-ADR-007)
# ---------------------------------------------------------------------------


def test_spec_defines_no_subagent_quality_score() -> None:
    """L3 emits EVIDENCE ONLY — the spec defines no subagent score field.

    Coherent with the ``reject_subagent_quality_score`` pre_dispatch hook
    (which guards the top-level ``quality_score`` key) and v15-ADR-007:
    L0 derives scores from evidence; no ``quality_score``/``quality`` key
    may exist anywhere in the lean spec or example, and the three v14.3.0
    evidence blocks may not define ANY score-named field (the only
    permitted score-suffixed key in the file is ``gate_input_score``,
    the v14.2.1 G-013 gate-dimension input — kept OUT of the evidence
    blocks).
    """
    doc = _load()

    for label, node in (
        ("lean_format_spec", doc["lean_format_spec"]),
        ("lean_example", doc["lean_example"]),
    ):
        keys = set(_walk_keys(node))
        assert "quality_score" not in keys and "quality" not in keys, (
            f"v15-ADR-007 doctrine violation: {label} defines a "
            f"quality/quality_score key — subagent reports MUST NOT carry a "
            f"quality score (L0-only per references/task-quality-score.md)."
        )

    for block in ("self_check", "ac_results", "diff_stats"):
        for scope, node in (
            (f"lean_format_spec.{block}", doc["lean_format_spec"][block]),
            (f"lean_example.{block}", doc["lean_example"][block]),
        ):
            score_keys = [k for k in _walk_keys(node) if "score" in k.lower()]
            assert not score_keys, (
                f"v15-ADR-007 doctrine violation: {scope} defines score-named "
                f"field(s) {score_keys} — the v14.3.0 evidence blocks carry "
                f"EVIDENCE ONLY, never scores."
            )
