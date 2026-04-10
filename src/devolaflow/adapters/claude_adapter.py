"""Claude Code adapter -- generates compressed CLAUDE.md (under 200 lines).

Design ref: design_delivery_architecture.md section 4.4 Claude Code Adapter table
Compression strategy: rules verbatim, quick-start, hierarchy table, 1-line ref summaries.
"""

from __future__ import annotations

import json
from pathlib import Path

from devolaflow.adapters.base import AdapterResult, BaseAdapter


class ClaudeAdapter(BaseAdapter):
    """Generate Claude Code output: CLAUDE.md (under 200 lines) + settings.json."""

    MAX_LINES = 200

    def build(self, source: dict, agent_dir: Path, output_dir: Path) -> AdapterResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        files: list[str] = []
        identity = source.get("identity", {})
        rules = source.get("content", {}).get("rules", [])
        refs = source.get("content", {}).get("references", [])

        out: list[str] = []
        out.append(f"# {identity.get('display_name', 'DevolaFlow')}")
        out.append("")
        desc = identity.get("description", "")
        out.append(desc.strip())
        out.append("")

        out.append("## Hard Rules")
        out.append("")
        for rule in rules:
            out.append(f"- ALWAYS: {rule.get('text', '')}")
        out.append("")

        out.append("## Workflow Types")
        out.append("")
        use_when = {
            "research-only": "Survey, compare, evaluate alternatives",
            "design-only": "Architecture, API design, schema design",
            "hotfix": "Production bug, urgent fix, CVE patch",
            "refactoring": "Tech debt, restructure, simplify",
            "migration": "Upgrade, port, convert systems",
            "spike-poc": "Prototype, experiment, feasibility",
            "documentation": "Docs, README, API reference",
            "security-audit": "Vulnerability scan, compliance review",
            "feature-enhancement": "Extend existing functionality",
            "full-pipeline": "New feature, greenfield, complete lifecycle",
            "RDRR": "Design with research, ADR workflow",
            "demo-showcase": "Build demo, presentation, pitch",
            "perf-optimization": "Profile, benchmark, optimize speed",
            "dependency-setup": "Environment, install, configure tools",
            "onboarding": "New contributor, codebase survey",
            "skill-optimization": "Optimize agent skill, benchmark context",
        }
        out.append("| Type | Use When |")
        out.append("|------|----------|")
        for t, w in use_when.items():
            out.append(f"| {t} | {w} |")
        out.append("")

        out.append("## 4-Layer Hierarchy")
        out.append("")
        out.append("| Layer | Role | Budget | MUST NOT |")
        out.append("|-------|------|--------|---------|")
        out.append("| Project | Dispatch stages, track status | ~3K | Write code, run tests |")
        out.append("| Stage | Decompose to waves, run gates | ~5K | Write code, run tests |")
        out.append("| Wave | Parallel dispatch tasks | ~4K | Execute task work |")
        out.append("| Task | Execute actual work | ~8K | Spawn sub-agents |")
        out.append("")

        out.append("## Gate Formula")
        out.append("")
        out.append("composite = test(0.30) + review(0.30) + arch(0.20) + bench(0.20)")
        out.append("PASS when: composite >= 85 AND blockers == 0 AND round >= 1")
        out.append("")

        out.append("## Plan Mode Constraints")
        out.append("")
        out.append("When in Plan mode, enforce these rigid constraints in plan output:")
        out.append("- <=5 tasks/wave, <=7 waves/stage, disjoint writable files within wave")
        out.append("- Task limits: impl <=30min, research <=45min, <=6 writable files")
        out.append("- Each stage specifies gate_type (standard/convergence/passthrough)")
        out.append("- Gates block advancement: no stage starts until predecessor PASS (D4)")
        out.append("- P1-P5 enforced: dispatch-only layers, typed YAML, bounded retry, artifacts")
        out.append("")

        if refs:
            out.append("## Reference Files")
            out.append("")
            for ref in refs:
                out.append(f"- `{ref.get('file', '')}`: {ref.get('load_when', '')}")
            out.append("")

        claude_md = "\n".join(out)
        (output_dir / "CLAUDE.md").write_text(claude_md)
        files.append("CLAUDE.md")

        settings_dir = output_dir / ".claude"
        settings_dir.mkdir(exist_ok=True)
        settings = {"permissions": {"allow_tools": True}}
        (settings_dir / "settings.json").write_text(json.dumps(settings, indent=2))
        files.append(".claude/settings.json")

        line_count = len(out)
        budget_ok = line_count < self.MAX_LINES
        return AdapterResult(
            tool="claude",
            output_dir=output_dir,
            files_created=files,
            budget_ok=budget_ok,
            budget_details=f"CLAUDE.md: {line_count}/{self.MAX_LINES} lines",
        )
