"""Current-cycle W-18 ghost audit for v21.0.0 close contracts."""

from __future__ import annotations

import json
from pathlib import Path

from devolaflow.compressor import (
    DEFAULT_EVIDENCE_INLINE_MAX_BYTES,
    EVIDENCE_TYPE,
)
from devolaflow.gate.budget import CEREMONY_SHARE_WARN_THRESHOLD
from devolaflow.harness.metadata import METADATA_FIELDS
from devolaflow.harness.telemetry import CONTEXT_TOKEN_FIELDS
from devolaflow.skills.change_activation import evaluate_trivial_path


def test_v21_t1_t2_t3_t6_close_surfaces_are_live(project_root: Path) -> None:
    """W-18 covers the four shipped v21 close surfaces before CHANGELOG."""
    # T1 — S1/trivial-path validation is a pure public runtime surface.
    result = evaluate_trivial_path(
        "TRIVIAL",
        {"files": 1, "insertions": 1, "deletions": 1},
    )
    assert result.passed is True
    assert result.upgrade_target is None

    # T2 — bounded StatusReport evidence references remain typed and compact.
    assert DEFAULT_EVIDENCE_INLINE_MAX_BYTES == 1024
    assert EVIDENCE_TYPE == "status-report-evidence"
    schema = (project_root / "schemas" / "status-report.schema.yaml").read_text(encoding="utf-8")
    assert "evidence_ref:" in schema

    # T3 — component accounting distinguishes all three ceremony components.
    assert CONTEXT_TOKEN_FIELDS == ("skill_tokens", "rule_tokens", "report_tokens")
    assert CEREMONY_SHARE_WARN_THRESHOLD == 0.5

    # T6 — reproducibility metadata is explicit, and final evidence is JSON.
    assert METADATA_FIELDS[-1] == "status"
    final_evaluation = (
        project_root / ".local" / "research" / "v21.0.0_harness_evaluation_final.json"
    )
    if final_evaluation.is_file():
        payload = json.loads(final_evaluation.read_text(encoding="utf-8"))
        assert isinstance(payload, dict)
        assert "verdict" in payload
