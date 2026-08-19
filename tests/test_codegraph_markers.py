"""Tests for Track C-3 — tri-state markers for backgrounded ``codegraph init``.

Pins ``devolaflow.codegraph.markers``: the coordination surface between
the backgrounded init (D-11 overturns the 2026-05-23 synchronous
ALL-modes decision per the R5 F2 root cause) and downstream analyze
consumers.

NO subprocess. NO network. Pure tmp_path filesystem assertions.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest
import yaml

from devolaflow.codegraph.markers import (
    FAILED_MARKER,
    INDEXING_MARKER,
    MARKER_DIR,
    READY_MARKER,
    MarkerState,
    mark_failed,
    mark_indexing,
    mark_ready,
    read_marker_state,
)

_REPO_ROOT: Path = Path(__file__).resolve().parent.parent
_REPO_INIT_PATH: Path = (
    _REPO_ROOT / "workflow-system" / "agent" / "templates" / "builtin" / "repo-init.yaml"
)


class TestMarkerTransitions:
    def test_absent_when_no_markers(self, tmp_path: Path) -> None:
        state = read_marker_state(tmp_path)
        assert state == MarkerState(state="absent", payload={})

    def test_mark_indexing_writes_pid_and_started_at(self, tmp_path: Path) -> None:
        path = mark_indexing(tmp_path, pid=4242)
        assert path == tmp_path / MARKER_DIR / INDEXING_MARKER
        state = read_marker_state(tmp_path)
        assert state.state == "indexing"
        assert state.payload["pid"] == 4242
        assert "started_at" in state.payload

    def test_mark_ready_clears_indexing_and_records_duration(self, tmp_path: Path) -> None:
        mark_indexing(tmp_path)
        mark_ready(tmp_path, duration_seconds=12.5)
        assert not (tmp_path / MARKER_DIR / INDEXING_MARKER).exists(), (
            "mark_ready must clear the .indexing sibling — a completed init is no longer in-flight."
        )
        state = read_marker_state(tmp_path)
        assert state.state == "ready"
        # Duration recorded verbatim (C-3), not paraphrased/rounded.
        assert state.payload["duration_seconds"] == 12.5
        assert "completed_at" in state.payload

    def test_mark_failed_records_error_summary(self, tmp_path: Path) -> None:
        mark_indexing(tmp_path)
        mark_failed(tmp_path, error_summary="codegraph init exited 1: parser panic")
        assert not (tmp_path / MARKER_DIR / INDEXING_MARKER).exists()
        state = read_marker_state(tmp_path)
        assert state.state == "failed"
        # S-5: the failure reason is explicit, never silent.
        assert state.payload["error_summary"] == "codegraph init exited 1: parser panic"


class TestCrashLeftoverPrecedence:
    def test_ready_wins_over_stale_siblings(self, tmp_path: Path) -> None:
        """Coexisting markers (writer died mid-swap) resolve ready > failed > indexing."""
        marker_dir = tmp_path / MARKER_DIR
        marker_dir.mkdir()
        (marker_dir / INDEXING_MARKER).write_text("{}\n", encoding="utf-8")
        (marker_dir / FAILED_MARKER).write_text("{}\n", encoding="utf-8")
        (marker_dir / READY_MARKER).write_text(
            json.dumps({"duration_seconds": 3.0}), encoding="utf-8"
        )
        state = read_marker_state(tmp_path)
        assert state.state == "ready", (
            "ready must win crash-leftover precedence — an index that "
            "finished IS usable regardless of stale siblings."
        )

    def test_failed_wins_over_stale_indexing(self, tmp_path: Path) -> None:
        marker_dir = tmp_path / MARKER_DIR
        marker_dir.mkdir()
        (marker_dir / INDEXING_MARKER).write_text("{}\n", encoding="utf-8")
        (marker_dir / FAILED_MARKER).write_text("{}\n", encoding="utf-8")
        assert read_marker_state(tmp_path).state == "failed"

    def test_malformed_payload_keeps_state_drops_payload(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """S-5: unparseable marker payloads WARN, but the state survives."""
        marker_dir = tmp_path / MARKER_DIR
        marker_dir.mkdir()
        (marker_dir / READY_MARKER).write_text("{not json", encoding="utf-8")
        with caplog.at_level(logging.WARNING, logger="devolaflow.codegraph.markers"):
            state = read_marker_state(tmp_path)
        assert state == MarkerState(state="ready", payload={})
        assert any("could not parse" in rec.message for rec in caplog.records)


class TestTemplateParity:
    def test_repo_init_markers_match_module_constants(self) -> None:
        """repo-init.yaml's declared marker paths mirror the module constants."""
        template = yaml.safe_load(_REPO_INIT_PATH.read_text(encoding="utf-8"))
        scaffold = next(s for s in template["stages"] if s.get("id") == "scaffold")
        declared = scaffold["config"]["codegraph_init"]["markers"]
        assert declared == {
            "indexing": f"{MARKER_DIR}/{INDEXING_MARKER}",
            "ready": f"{MARKER_DIR}/{READY_MARKER}",
            "failed": f"{MARKER_DIR}/{FAILED_MARKER}",
        }

    def test_package_exports_marker_surface(self) -> None:
        """The marker protocol is reachable from the package root (no probe duplicate)."""
        import devolaflow.codegraph as pkg

        for symbol in (
            "MarkerState",
            "mark_indexing",
            "mark_ready",
            "mark_failed",
            "read_marker_state",
        ):
            assert symbol in pkg.__all__, f"devolaflow.codegraph.__all__ missing {symbol}"
        # A-5 single owner: the suggest-tier probe stays is_codegraph_available;
        # markers.py must NOT ship a second shutil.which wrapper.
        assert "is_codegraph_available" in pkg.__all__
        import devolaflow.codegraph.markers as markers_mod

        assert not hasattr(markers_mod, "codegraph_cli_available")
