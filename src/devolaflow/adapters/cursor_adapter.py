"""Cursor adapter — generates SKILL.md + .mdc rules.

Design ref: design_delivery_architecture.md §4.4 Cursor Adapter table
"""

from __future__ import annotations

import shutil
from pathlib import Path

from devolaflow.adapters.base import AdapterResult, BaseAdapter


class CursorAdapter(BaseAdapter):
    """Generate Cursor skill output: SKILL.md + references + rules."""

    MAX_LINES = 500

    def build(self, source: dict, agent_dir: Path, output_dir: Path) -> AdapterResult:
        """Copy skill assets and emit Cursor rule files into *output_dir*."""
        output_dir.mkdir(parents=True, exist_ok=True)
        files: list[str] = []

        skill_src = agent_dir / "SKILL.md"
        skill_dst = output_dir / "SKILL.md"
        if skill_src.exists():
            shutil.copy2(skill_src, skill_dst)
            files.append("SKILL.md")

        refs_src = agent_dir / "references"
        if refs_src.is_dir():
            refs_dst = output_dir / "references"
            if refs_dst.exists():
                shutil.rmtree(refs_dst)
            shutil.copytree(refs_src, refs_dst)
            files.append("references/")

        examples_src = agent_dir / "examples"
        if examples_src.is_dir():
            ex_dst = output_dir / "examples"
            if ex_dst.exists():
                shutil.rmtree(ex_dst)
            shutil.copytree(examples_src, ex_dst)
            files.append("examples/")

        rules_dir = output_dir / "rules"
        rules_dir.mkdir(exist_ok=True)
        rules = source.get("content", {}).get("rules", [])
        mdc_lines = [
            "---",
            'description: "Hard constraints for DevolaFlow workflow orchestration"',
            "alwaysApply: true",
            "---",
            "",
        ]
        for rule in rules:
            mdc_lines.append(f"## {rule.get('id', 'unknown')}")
            mdc_lines.append(f"**Severity**: {rule.get('severity', 'hard')}")
            mdc_lines.append(f"{rule.get('text', '')}")
            mdc_lines.append("")
        (rules_dir / "workflow-hard-rules.mdc").write_text("\n".join(mdc_lines))
        files.append("rules/workflow-hard-rules.mdc")

        line_count = len(skill_dst.read_text().splitlines()) if skill_dst.exists() else 0
        budget_ok = line_count < self.MAX_LINES
        return AdapterResult(
            tool="cursor",
            output_dir=output_dir,
            files_created=files,
            budget_ok=budget_ok,
            budget_details=f"SKILL.md: {line_count}/{self.MAX_LINES} lines",
        )
