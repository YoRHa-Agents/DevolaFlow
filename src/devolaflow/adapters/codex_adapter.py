"""Codex adapter — generates SKILL.md with inline rules + openai.yaml.

Design ref: design_delivery_architecture.md §4.4 Codex Adapter table
"""

from __future__ import annotations

from pathlib import Path

import yaml

from devolaflow.adapters.base import AdapterResult, BaseAdapter


class CodexAdapter(BaseAdapter):
    """Generate Codex skill output: SKILL.md (rules inlined) + agents/openai.yaml."""

    MAX_LINES = 500

    def build(self, source: dict, agent_dir: Path, output_dir: Path) -> AdapterResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        files: list[str] = []
        identity = source.get("identity", {})
        rules = source.get("content", {}).get("rules", [])

        skill_src = agent_dir / "SKILL.md"
        body = skill_src.read_text() if skill_src.exists() else ""

        rules_section = "\n## Hard Rules\n\n"
        for rule in rules:
            rules_section += f"- **{rule.get('id')}**: {rule.get('text')}\n"

        fm = (
            "---\n"
            f"name: {identity.get('name', 'devola-flow')}\n"
            f"description: >\n  {identity.get('description', '').strip()}\n"
            "---\n\n"
        )
        lines = body.split("---", 2)
        content = lines[2] if len(lines) >= 3 else body
        full = fm + content.strip() + "\n" + rules_section
        (output_dir / "SKILL.md").write_text(full)
        files.append("SKILL.md")

        agents_dir = output_dir / "agents"
        agents_dir.mkdir(exist_ok=True)
        openai_yaml = {
            "display_name": identity.get("display_name", "DevolaFlow"),
            "short_description": identity.get("description", "")[:200],
            "default_prompt": "Run a workflow for the user's request.",
        }
        (agents_dir / "openai.yaml").write_text(yaml.dump(openai_yaml, default_flow_style=False))
        files.append("agents/openai.yaml")

        line_count = len(full.splitlines())
        budget_ok = line_count < self.MAX_LINES
        return AdapterResult(
            tool="codex",
            output_dir=output_dir,
            files_created=files,
            budget_ok=budget_ok,
            budget_details=f"SKILL.md: {line_count}/{self.MAX_LINES} lines",
        )
