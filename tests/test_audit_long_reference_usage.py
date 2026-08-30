"""Unit tests for `scripts/audit_long_reference_usage.py` (D-D-2)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def audit_module():
    repo_root = Path(__file__).resolve().parent.parent
    script_path = repo_root / "scripts" / "audit_long_reference_usage.py"
    spec = importlib.util.spec_from_file_location("audit_long_reference_usage", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["audit_long_reference_usage"] = module
    spec.loader.exec_module(module)
    return module


def _seed_pyproject(repo_root: Path) -> None:
    (repo_root / "pyproject.toml").write_text("[tool.test]\n", encoding="utf-8")


def _seed_long_reference(repo_root: Path, name: str) -> None:
    refs = repo_root / "workflow-system/agent/references"
    refs.mkdir(parents=True, exist_ok=True)
    body = "\n".join(f"# heading {i}" for i in range(700))
    (refs / f"{name}.md").write_text(body, encoding="utf-8")


def _seed_short_reference(repo_root: Path, name: str) -> None:
    refs = repo_root / "workflow-system/agent/references"
    refs.mkdir(parents=True, exist_ok=True)
    (refs / f"{name}.md").write_text("# short\nbody\n", encoding="utf-8")


def _seed_envelope(
    repo_root: Path,
    *,
    from_layer: str,
    to_layer: str,
    change_id: str,
    seq: int,
    cited: str | None = None,
) -> Path:
    handoff = repo_root / ".local/.agent/handoff"
    handoff.mkdir(parents=True, exist_ok=True)
    name = f"{from_layer}__{to_layer}__{change_id}__{seq:04d}.yaml"
    payload = "schema_version: '1.0'\n"
    if cited:
        payload += f"references_cited:\n  - {cited}\n"
    path = handoff / name
    path.write_text(payload, encoding="utf-8")
    return path


def test_empty_handoff_dir_yields_zero_envelopes(audit_module, tmp_path: Path) -> None:
    _seed_pyproject(tmp_path)
    _seed_long_reference(tmp_path, "agent-workspace")
    report = audit_module.build_report(repo_root=tmp_path)
    assert report.envelopes == ()
    assert report.archive_count == 0
    assert "agent-workspace.md" in report.long_references


def test_envelope_with_cited_long_reference(audit_module, tmp_path: Path) -> None:
    _seed_pyproject(tmp_path)
    _seed_long_reference(tmp_path, "agent-workspace")
    _seed_short_reference(tmp_path, "team-roles")
    _seed_envelope(
        tmp_path,
        from_layer="L0",
        to_layer="L1",
        change_id="v10.4.0-cycle",
        seq=1,
        cited="references/agent-workspace.md",
    )
    report = audit_module.build_report(repo_root=tmp_path)
    assert len(report.envelopes) == 1
    assert report.citations["agent-workspace.md"] == 1


def test_filename_parsing_rejects_malformed(audit_module, tmp_path: Path) -> None:
    _seed_pyproject(tmp_path)
    _seed_long_reference(tmp_path, "execution-protocol")
    handoff = tmp_path / ".local/.agent/handoff"
    handoff.mkdir(parents=True, exist_ok=True)
    (handoff / "garbage_name.yaml").write_text("schema_version: '1.0'\n", encoding="utf-8")
    _seed_envelope(
        tmp_path,
        from_layer="L1",
        to_layer="L0",
        change_id="legit-change",
        seq=2,
        cited="references/execution-protocol.md",
    )
    report = audit_module.build_report(repo_root=tmp_path)
    assert len(report.envelopes) == 1, "malformed filenames must be rejected, not crash"


def test_render_markdown_lists_each_long_reference(audit_module, tmp_path: Path) -> None:
    _seed_pyproject(tmp_path)
    _seed_long_reference(tmp_path, "agent-workspace")
    _seed_long_reference(tmp_path, "execution-protocol")
    report = audit_module.build_report(repo_root=tmp_path)
    md = audit_module.render_markdown(report)
    assert "agent-workspace.md" in md
    assert "execution-protocol.md" in md
    assert "complex / change-driven workflows only" in md


def test_render_json_round_trip(audit_module, tmp_path: Path) -> None:
    _seed_pyproject(tmp_path)
    _seed_long_reference(tmp_path, "memory-router")
    _seed_envelope(
        tmp_path,
        from_layer="operator",
        to_layer="L0",
        change_id="abc",
        seq=1,
        cited="references/memory-router.md",
    )
    report = audit_module.build_report(repo_root=tmp_path)
    payload = json.loads(audit_module.render_json(report))
    assert payload["envelope_count"] == 1
    assert payload["citations"]["memory-router.md"] == 1
    assert "memory-router.md" in payload["long_references"]
