"""Tests for ``scripts/audit_canonical_order_emptiness.py`` (v10.7.0 D-P-1).

Covers the audit-only, zero-schema-mutation contract from
`.local/research/v11.0.0_patches/D-P-1.md`:

* Per-position non-empty rate computation across a synthetic payload
  set.
* Frozen-prefix flag (positions 1-12) is set deterministically.
* NEST candidate flag fires only on TAIL positions (13+) below the
  ``NEST_CANDIDATE_THRESHOLD`` (default 0.05).
* The ``--include-positions`` CLI flag is rejected at argparse time
  (G-6 frozen-prefix gate enforcement at the operator interface).
* The audit produces a non-empty markdown report for an empty input
  (empty-state preserved).
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest


def _load_audit_module() -> object:
    """Import ``scripts/audit_canonical_order_emptiness.py`` as a module."""
    repo_root = Path(__file__).resolve().parent.parent
    script = repo_root / "scripts" / "audit_canonical_order_emptiness.py"
    name = "audit_canonical_order_emptiness"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_AUDIT = _load_audit_module()


def _synthetic_canonical_order_17() -> tuple[str, ...]:
    """Mirror schemas/lean-dispatch.yaml#layout_invariant.canonical_order at v8.3.0+."""
    return (
        "hdr",
        "task",
        "goal",
        "assumptions",
        "pred",
        "files",
        "rules",
        "shared",
        "accept",
        "reinforce",
        "verify_cfg",
        "gate",
        # APPEND-ONLY TAIL (positions 13-17):
        "repos",
        "behavioral_guidelines",
        "acceptance_criteria_v2",
        "change_context",
        "predecessor_dedup_ledger",
    )


def test_compute_emptiness_report_per_position_rates() -> None:
    """3 synthetic payloads → expected per-position rates."""
    canonical_order = _synthetic_canonical_order_17()
    payloads = [
        # All 12 frozen-prefix keys populated; only `change_context` in tail.
        {k: f"v-{k}" for k in canonical_order[:12]} | {"change_context": {"id": "c1"}},
        {k: f"v-{k}" for k in canonical_order[:12]} | {"behavioral_guidelines": ["BG-001"]},
        # Third payload: empty for `repos` (explicit []), null for `predecessor_dedup_ledger`.
        {k: f"v-{k}" for k in canonical_order[:12]}
        | {"repos": [], "predecessor_dedup_ledger": None},
    ]
    report = _AUDIT.compute_emptiness_report(
        canonical_order, payloads, handoff_count=2, research_count=1
    )
    assert report.sampled_count == 3
    assert len(report.rows) == 17
    assert report.handoff_count == 2
    assert report.research_count == 1

    rate_by_key = {row.key: row.non_empty_rate for row in report.rows}
    # Frozen prefix: every key populated in every payload → rate 1.0.
    for k in canonical_order[:12]:
        assert rate_by_key[k] == pytest.approx(1.0), (
            f"frozen-prefix {k!r} should be 100% non-empty across 3 synthetic payloads"
        )
    # Tail: only `change_context` (1/3) and `behavioral_guidelines` (1/3) populated.
    assert rate_by_key["change_context"] == pytest.approx(1 / 3)
    assert rate_by_key["behavioral_guidelines"] == pytest.approx(1 / 3)
    # `repos` set to [] in payload 3, absent from 1+2 → still 0% non-empty.
    assert rate_by_key["repos"] == pytest.approx(0.0)
    # `acceptance_criteria_v2` never present → 0%.
    assert rate_by_key["acceptance_criteria_v2"] == pytest.approx(0.0)
    # `predecessor_dedup_ledger` set to None → counts as empty.
    assert rate_by_key["predecessor_dedup_ledger"] == pytest.approx(0.0)


def test_frozen_prefix_and_nest_candidate_flags_are_mutually_exclusive() -> None:
    """Frozen prefix never gets `nest_candidate`; tail-with-low-rate gets it."""
    canonical_order = _synthetic_canonical_order_17()
    # All 17 keys absent → all rates 0%.
    payloads = [{}, {}]
    report = _AUDIT.compute_emptiness_report(canonical_order, payloads)
    for row in report.rows:
        if row.is_frozen:
            assert row.position <= _AUDIT.FROZEN_PREFIX_LENGTH
            assert not row.nest_candidate, (
                f"frozen position {row.position} ({row.key}) must NEVER get "
                f"nest_candidate=True even at 0% rate (G-6 gate)"
            )
        else:
            # Tail with 0% rate is below threshold → flag fires.
            assert row.position > _AUDIT.FROZEN_PREFIX_LENGTH
            assert row.nest_candidate, (
                f"tail position {row.position} ({row.key}) at 0% should be flagged"
            )


def test_render_markdown_contains_g6_warning_and_table_header() -> None:
    """The markdown report carries the G-6 reminder and per-position table."""
    canonical_order = _synthetic_canonical_order_17()
    report = _AUDIT.compute_emptiness_report(canonical_order, [], handoff_count=0)
    md = _AUDIT.render_markdown(report)
    # Hard requirements per PDS §2 step 5:
    assert "G-6 frozen-prefix gate" in md
    assert "FROZEN" in md
    assert "NEST" in md
    assert "A-2.1" in md
    assert "A-2.3" in md
    # Table header contract (operator-facing).
    assert "| Pos | Key |" in md
    # Each canonical_order key MUST appear verbatim in the rendered body.
    for key in canonical_order:
        assert f"`{key}`" in md, f"missing key in rendered table: {key}"


def test_include_positions_flag_is_rejected_at_argparse() -> None:
    """``--include-positions`` is a deliberate argparse-error per PDS §2 step 5.

    Operators MUST NOT be able to opt into mutating positions 1-12.
    The error must mention A-2.1 and FROZEN_PREFIX_V7.
    """
    captured = io.StringIO()
    old_stderr = sys.stderr
    sys.stderr = captured
    try:
        with pytest.raises(SystemExit):
            _AUDIT.main(["--include-positions", "1-12"])
    finally:
        sys.stderr = old_stderr
    err = captured.getvalue()
    assert "A-2.1" in err
    assert "FROZEN" in err


def test_render_json_round_trip_is_machine_consumable() -> None:
    """``render_json`` emits valid JSON with the expected top-level keys."""
    canonical_order = _synthetic_canonical_order_17()
    payloads = [{k: f"v-{k}" for k in canonical_order}]
    report = _AUDIT.compute_emptiness_report(canonical_order, payloads, handoff_count=1)
    raw = _AUDIT.render_json(report)
    parsed = json.loads(raw)
    assert parsed["canonical_order"] == list(canonical_order)
    assert parsed["sampled_count"] == 1
    assert parsed["frozen_prefix_length"] == _AUDIT.FROZEN_PREFIX_LENGTH
    assert parsed["nest_candidate_threshold"] == _AUDIT.NEST_CANDIDATE_THRESHOLD
    rows = parsed["rows"]
    assert len(rows) == 17
    assert all("non_empty_rate" in row for row in rows)
    # Every field present + non-empty in our synthetic payload.
    assert all(row["non_empty_rate"] == 1.0 for row in rows)
