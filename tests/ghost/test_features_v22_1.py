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


def test_v22_1_feedback_record_contains_verification_addendum(project_root: Path) -> None:
    """The submitted feedback retains its original record and its correction."""
    feedback = (project_root / ".local/feedbacks/feedback_for_v21.2.0.md").read_text(
        encoding="utf-8"
    )

    assert "## 六、上游核验与修复方向（2026-08-31，追加）" in feedback
    assert "P2 原始结论不成立" in feedback
    assert "v22.0.0" in feedback
