"""PV-04 tests for bounded inline and referenced StatusReport evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import yaml

from devolaflow.agent_workspace.handoff import HandoffEnvelope, HandoffStore
from devolaflow.compressor import (
    DEFAULT_DISPATCH_LAYOUT,
    DEFAULT_EVIDENCE_INLINE_MAX_BYTES,
    EvidenceReferenceError,
    EvidenceReferenceRequired,
    prepare_status_report_evidence,
    serialize_status_report_evidence,
    validate_status_report_evidence,
)

CHANGE_ID = "evidence-test"


def _content_ref(repo_root: Path, value: object, name: str = "manual.json") -> dict[str, object]:
    content = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    target = repo_root / ".local/.agent/active" / CHANGE_ID / "evidence" / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return {
        "path": target.relative_to(repo_root).as_posix(),
        "artifact_id": f"manual-{name.removesuffix('.json')}",
        "type": "status-report-evidence",
        "digest": f"sha256:{hashlib.sha256(content).hexdigest()}",
        "size_bytes": len(content),
    }


def test_small_evidence_stays_inline_and_legacy_shape_is_unchanged(tmp_path: Path) -> None:
    report = {
        "self_check": {"goal_anchor": "small"},
        "ac_results": [{"id": "AC-1", "verdict": "pass", "cmd_digest": "exit 0"}],
        "diff_stats": {"files": 1, "insertions": 2, "deletions": 0},
    }
    prepared = prepare_status_report_evidence(report, repo_root=tmp_path, change_id=CHANGE_ID)
    assert prepared == report
    assert prepared is not report
    assert not (tmp_path / ".local/.agent/active" / CHANGE_ID / "evidence").exists()
    assert serialize_status_report_evidence(
        {"state": "completed"}, repo_root=tmp_path, change_id=CHANGE_ID
    ) == {"state": "completed"}


def test_oversized_blocks_materialize_as_stable_refs_without_copying_content(
    tmp_path: Path,
) -> None:
    report = {"self_check": {"goal_anchor": "x" * (DEFAULT_EVIDENCE_INLINE_MAX_BYTES + 1)}}
    prepared = prepare_status_report_evidence(report, repo_root=tmp_path, change_id=CHANGE_ID)
    block = prepared["self_check"]
    assert set(block) == {"evidence_ref"}
    reference = block["evidence_ref"]
    assert reference["path"].startswith(f".local/.agent/active/{CHANGE_ID}/evidence/")
    assert reference["artifact_id"].startswith("sr-self_check-")
    assert reference["size_bytes"] > DEFAULT_EVIDENCE_INLINE_MAX_BYTES
    assert "goal_anchor" not in block
    path = tmp_path / reference["path"]
    assert path.is_file()
    assert (
        path.read_bytes()
        == b'{"goal_anchor":"' + (b"x" * (DEFAULT_EVIDENCE_INLINE_MAX_BYTES + 1)) + b'"}'
    )


def test_existing_small_and_large_refs_validate_without_hydration(tmp_path: Path) -> None:
    small_ref = _content_ref(tmp_path, {"ok": True}, "small.json")
    large_value = {"payload": "z" * (DEFAULT_EVIDENCE_INLINE_MAX_BYTES + 100)}
    large_report = prepare_status_report_evidence(
        {"diff_stats": large_value}, repo_root=tmp_path, change_id=CHANGE_ID
    )
    large_ref = large_report["diff_stats"]["evidence_ref"]
    report = {
        "self_check": {"evidence_ref": small_ref},
        "diff_stats": {"evidence_ref": large_ref},
    }
    prepared = prepare_status_report_evidence(report, repo_root=tmp_path, change_id=CHANGE_ID)
    assert prepared == report
    assert prepared["self_check"]["evidence_ref"] == small_ref
    validate_status_report_evidence(prepared, repo_root=tmp_path, change_id=CHANGE_ID)


def test_validation_requires_a_ref_for_oversized_inline_evidence(tmp_path: Path) -> None:
    report = {"ac_results": [{"id": "AC-1", "verdict": "pass", "cmd_digest": "q" * 2000}]}
    with pytest.raises(EvidenceReferenceRequired, match="ac_results exceeds inline"):
        validate_status_report_evidence(report, repo_root=tmp_path, change_id=CHANGE_ID)


@pytest.mark.parametrize(
    "path",
    [
        "/tmp/evidence.json",
        "../outside.json",
        ".local/.agent/active/other-change/evidence/x.json",
    ],
)
def test_absolute_and_out_of_tree_refs_are_rejected(tmp_path: Path, path: str) -> None:
    reference = _content_ref(tmp_path, {"x": 1})
    reference["path"] = path
    with pytest.raises(EvidenceReferenceError):
        validate_status_report_evidence(
            {"self_check": {"evidence_ref": reference}},
            repo_root=tmp_path,
            change_id=CHANGE_ID,
        )


def test_missing_ref_is_rejected(tmp_path: Path) -> None:
    reference = _content_ref(tmp_path, {"x": 1})
    (tmp_path / reference["path"]).unlink()
    with pytest.raises(EvidenceReferenceError, match="does not exist"):
        validate_status_report_evidence(
            {"self_check": {"evidence_ref": reference}},
            repo_root=tmp_path,
            change_id=CHANGE_ID,
        )


def test_symlink_ref_is_rejected_even_when_target_is_inside_boundary(tmp_path: Path) -> None:
    evidence_dir = tmp_path / ".local/.agent/active" / CHANGE_ID / "evidence"
    evidence_dir.mkdir(parents=True)
    actual = evidence_dir / "actual.json"
    actual.write_text('{"x":1}', encoding="utf-8")
    link = evidence_dir / "link.json"
    link.symlink_to(actual)
    content = actual.read_bytes()
    reference = {
        "path": link.relative_to(tmp_path).as_posix(),
        "artifact_id": "link",
        "type": "status-report-evidence",
        "digest": f"sha256:{hashlib.sha256(content).hexdigest()}",
        "size_bytes": len(content),
    }
    with pytest.raises(EvidenceReferenceError, match="symlink"):
        validate_status_report_evidence(
            {"diff_stats": {"evidence_ref": reference}},
            repo_root=tmp_path,
            change_id=CHANGE_ID,
        )


def test_inline_and_ref_forms_are_mutually_exclusive(tmp_path: Path) -> None:
    reference = _content_ref(tmp_path, {"x": 1})
    with pytest.raises(EvidenceReferenceError, match="mutually exclusive"):
        prepare_status_report_evidence(
            {"self_check": {"goal_anchor": "x", "evidence_ref": reference}},
            repo_root=tmp_path,
            change_id=CHANGE_ID,
        )


def test_handoff_serializer_materializes_report_evidence_without_mutating_envelope(
    tmp_path: Path,
) -> None:
    report = {"self_check": {"goal_anchor": "x" * 2000}}
    envelope = HandoffEnvelope(
        seq=1,
        from_layer="L2",
        to_layer="L0",
        change_id=CHANGE_ID,
        created="2026-08-29T00:00:00Z",
        envelope_kind="StatusReport",
        report=report,
    )
    store = HandoffStore(repo_root=tmp_path)
    path = store.write_envelope(envelope)
    written = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert "evidence_ref" in written["report"]["self_check"]
    assert envelope.report == report


def test_report_evidence_does_not_change_dispatch_layout() -> None:
    assert len(DEFAULT_DISPATCH_LAYOUT) == 17
    assert DEFAULT_DISPATCH_LAYOUT[:12] == [
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
    ]
