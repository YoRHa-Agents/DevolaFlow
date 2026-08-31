"""Current-cycle ghost audit for the self-contained npm runtime channel."""

from __future__ import annotations

import json
from pathlib import Path


def test_v22_1_npm_channel_provisions_a_pinned_runtime(project_root: Path) -> None:
    """The npm surface keeps runtime provisioning and version pinning present."""
    package = json.loads((project_root / "packages/npm/package.json").read_text(encoding="utf-8"))
    installer = (project_root / "packages/npm/bin/devola-flow.js").read_text(encoding="utf-8")
    skill = (project_root / "workflow-system/agent/SKILL.md").read_text(encoding="utf-8")

    assert "provisions the matching Python runtime" in package["description"]
    assert "uv tool install" in installer
    assert "v${pkg.version}" in installer
    assert "docs-only" in installer
    assert "runtime-dependent commands" in skill


def test_v22_1_cycle_archive_contains_verification_evidence(project_root: Path) -> None:
    """The committed cycle archive retains the feedback correction."""
    gap_analysis = (project_root / "docs/cycle-archive/v22.1.0/v22.1.0_gap_analysis.md").read_text(
        encoding="utf-8"
    )

    assert "D-5" in gap_analysis
    assert "measurement error" in gap_analysis
    assert "v22.0.0" in gap_analysis
