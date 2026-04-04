"""Copilot adapter — generates copilot-instructions.md (<4000 chars).

Design ref: design_delivery_architecture.md §4.4 Copilot Adapter table
"""

from __future__ import annotations

from pathlib import Path

from devolaflow.adapters.base import AdapterResult, BaseAdapter


class CopilotAdapter(BaseAdapter):
    """Generate Copilot output: copilot-instructions.md + workflow.instructions.md."""

    MAX_CHARS = 4000

    def build(self, source: dict, agent_dir: Path, output_dir: Path) -> AdapterResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        files: list[str] = []
        identity = source.get("identity", {})
        rules = source.get("content", {}).get("rules", [])

        gh_dir = output_dir / ".github"
        gh_dir.mkdir(exist_ok=True)

        lines: list[str] = []
        lines.append(f"# {identity.get('display_name', 'Workflow Orchestrator')}")
        lines.append("")
        lines.append(identity.get("description", "").strip()[:300])
        lines.append("")

        lines.append("## Things to Avoid")
        lines.append("")
        for rule in rules:
            lines.append(f"- NEVER violate: {rule.get('text', '')}")
        lines.append("")

        lines.append("## Workflow Types")
        lines.append("")
        lines.append(
            "Available: research-only, design-only, hotfix, refactoring, migration, "
            "spike-poc, documentation, security-audit, feature-enhancement, full-pipeline"
        )
        lines.append("")

        lines.append("## Hierarchy")
        lines.append("")
        lines.append("Project (dispatch) -> Stage (decompose) -> Wave (parallel) -> Task (work)")
        lines.append("Only Task agents perform actual work.")
        lines.append("")

        lines.append("## Gate")
        lines.append("")
        lines.append("composite = test(0.30) + review(0.30) + arch(0.20) + bench(0.20) >= 85")

        content = "\n".join(lines)
        (gh_dir / "copilot-instructions.md").write_text(content)
        files.append(".github/copilot-instructions.md")

        inst_dir = gh_dir / "instructions"
        inst_dir.mkdir(exist_ok=True)
        (inst_dir / "workflow.instructions.md").write_text(
            "# Workflow Orchestration\n\n"
            "When working on multi-step tasks, use the 4-layer hierarchy:\n"
            "Project -> Stage -> Wave -> Task.\n"
            "Each task agent owns specific files and must not modify others.\n"
        )
        files.append(".github/instructions/workflow.instructions.md")

        char_count = len(content)
        budget_ok = char_count < self.MAX_CHARS
        return AdapterResult(
            tool="copilot",
            output_dir=output_dir,
            files_created=files,
            budget_ok=budget_ok,
            budget_details=f"copilot-instructions.md: {char_count}/{self.MAX_CHARS} chars",
        )
