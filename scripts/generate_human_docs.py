#!/usr/bin/env python3
"""Generate human-readable docs from agent system files.

Design ref: design_dual_system.md section 4.1-4.2
Simplified v0.1.0: generates structured docs with practical content.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

DOCS = [
    ("quickstart", "Quick Start Guide",
     "Getting started with DevolaFlow in under 10 minutes.",
     "快速入门指南", "10 分钟内开始使用 DevolaFlow。"),
    ("architecture-overview", "Architecture Overview",
     "System architecture: 4-layer hierarchy, stage primitives, gate mechanism.",
     "架构概述", "系统架构：4 层层级、阶段原语、质量门机制。"),
    ("workflow-types", "Workflow Types Catalog",
     "11 built-in workflow types with selection guidance.",
     "工作流类型目录", "11 种内置工作流类型及选择指南。"),
    ("agent-hierarchy-guide", "Agent Hierarchy Guide",
     "Understanding the 4-layer delegation hierarchy.",
     "Agent 层级指南", "理解 4 层委托层级架构。"),
    ("customization-guide", "Customization Guide",
     "Creating custom workflow templates and derived configurations.",
     "自定义指南", "创建自定义工作流模板和派生配置。"),
    ("integration-guide", "Integration Guide",
     "Integrating DevolaFlow with existing tools and CI/CD pipelines.",
     "集成指南", "将 DevolaFlow 与现有工具和 CI/CD 管线集成。"),
    ("troubleshooting", "Troubleshooting",
     "Common issues and solutions for workflow execution.",
     "故障排查", "工作流执行中的常见问题和解决方案。"),
    ("faq", "FAQ",
     "Frequently asked questions about the workflow system.",
     "常见问题", "关于工作流系统的常见问题解答。"),
]

SOURCE_FILES = ["SKILL.md"]
SOURCE_VERSION = "2.1.0"


def _gen_doc(slug: str, title: str, desc: str, lang: str, output_dir: Path) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    fm = (
        "---\n"
        f"title: \"{title}\"\n"
        f"description: \"{desc}\"\n"
        f"source_files:\n"
    )
    for sf in SOURCE_FILES:
        fm += f"  - \"{sf}\"\n"
    fm += (
        f"auto_generated: true\n"
        f"last_synced: \"{now}\"\n"
        f"source_version: \"{SOURCE_VERSION}\"\n"
        "---\n\n"
    )
    content = fm + f"# {title}\n\n{desc}\n\n"

    if lang == "en":
        content += _gen_en_content(slug)
    else:
        content += _gen_zh_content(slug)

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / f"{slug}.md").write_text(content, encoding="utf-8")


def _gen_en_content(slug: str) -> str:
    sections = {
        "quickstart": (
            "## Prerequisites\n\n- Python 3.11+\n- pip\n\n"
            "## Installation\n\n```bash\npip install -e \".[dev]\"\n```\n\n"
            "## Your First Workflow\n\n"
            "1. Run `detect-repo-mode` to identify your repository type\n"
            "2. Run `validate-template --all` to verify templates are valid\n"
            "3. Choose a workflow type based on your task\n"
            "4. Follow the 4-layer hierarchy: Project dispatches Stages\n\n"
            "## Checking Your Version\n\n"
            "```bash\ndevola-version   # prints DevolaFlow vX.X.X\n```\n\n"
            "Or ask your AI agent: `\"update devola\"` to check the installed version "
            "and whether a newer release is available.\n\n"
            "## Updating DevolaFlow\n\n"
            "**From inside your AI tool** (recommended):\n\n"
            "Type `\"update devola\"` or `\"/update-devola\"`. The agent checks GitHub "
            "for the latest version and provides the right command for your setup.\n\n"
            "**From the terminal:**\n\n"
            "```bash\n"
            "# Installer update\n"
            "curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/"
            "main/scripts/install.sh | bash -s update\n\n"
            "# pip update\n"
            "pip install --upgrade git+https://github.com/YoRHa-Agents/DevolaFlow.git\n"
            "```\n\n"
            "## Next Steps\n\n"
            "- Read the [Architecture Overview](architecture-overview.md)\n"
            "- Explore [Workflow Types](workflow-types.md)\n"
        ),
        "architecture-overview": (
            "## System Overview\n\n"
            "DevolaFlow uses a 4-layer agent hierarchy to orchestrate complex workflows.\n\n"
            "## The 4-Layer Hierarchy\n\n"
            "| Layer | Role | Context Budget |\n"
            "|-------|------|---------------|\n"
            "| Project | Dispatch stages, track status | ~3K tokens |\n"
            "| Stage | Decompose to waves, run gates | ~5K tokens |\n"
            "| Wave | Parallel dispatch tasks | ~4K tokens |\n"
            "| Task | Execute actual work | ~8K tokens |\n\n"
            "## Stage Primitives\n\n"
            "13 universal primitives: research, analyze, design, plan, implement, "
            "review, test, validate, refine, release, deploy, monitor, gate.\n\n"
            "## Gate Mechanism\n\n"
            "Quality checkpoints between stages. Composite score formula:\n"
            "`composite = test(0.30) + review(0.30) + arch(0.20) + bench(0.20)`\n"
            "Pass threshold: >= 85 with zero blockers.\n"
        ),
        "workflow-types": (
            "## Available Workflow Types\n\n"
            "| Type | Use When |\n|------|----------|\n"
            "| research-only | Survey, compare, evaluate |\n"
            "| design-only | Architecture, API design |\n"
            "| hotfix | Production bug, urgent fix |\n"
            "| refactoring | Tech debt, restructure |\n"
            "| migration | Upgrade, port systems |\n"
            "| spike-poc | Prototype, experiment |\n"
            "| documentation | Docs, README |\n"
            "| security-audit | Vulnerability scan |\n"
            "| feature-enhancement | Extend functionality |\n"
            "| full-pipeline | New feature, complete lifecycle |\n"
            "| RDRR | Design with research |\n\n"
        ),
    }
    return sections.get(slug, f"## {slug.replace('-', ' ').title()}\n\nContent coming soon.\n")


def _gen_zh_content(slug: str) -> str:
    sections = {
        "quickstart": (
            "## 前置条件\n\n- Python 3.11+\n- pip\n\n"
            "## 安装\n\n```bash\npip install -e \".[dev]\"\n```\n\n"
            "## 你的第一个工作流\n\n"
            "1. 运行 `detect-repo-mode` 识别仓库类型\n"
            "2. 运行 `validate-template --all` 验证模板有效性\n"
            "3. 根据任务选择工作流类型\n"
            "4. 遵循 4 层层级：项目代理分派阶段代理\n\n"
            "## 查看版本\n\n"
            "```bash\ndevola-version   # 输出 DevolaFlow vX.X.X\n```\n\n"
            "或在 AI 工具中输入 `\"update devola\"` 查看已安装版本并检查是否有新版本。\n\n"
            "## 更新 DevolaFlow\n\n"
            "**在 AI 工具中更新**（推荐）：\n\n"
            "输入 `\"update devola\"` 或 `\"/update-devola\"`。"
            "代理会从 GitHub 检查最新版本并提供对应的更新命令。\n\n"
            "**在终端中更新：**\n\n"
            "```bash\n"
            "# 安装器更新\n"
            "curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/"
            "main/scripts/install.sh | bash -s update\n\n"
            "# pip 更新\n"
            "pip install --upgrade git+https://github.com/YoRHa-Agents/DevolaFlow.git\n"
            "```\n\n"
        ),
        "architecture-overview": (
            "## 系统概述\n\n"
            "DevolaFlow 使用 4 层代理层级编排复杂工作流。\n\n"
            "## 4 层层级\n\n"
            "| 层级 | 角色 | 上下文预算 |\n"
            "|------|------|----------|\n"
            "| 项目代理 | 分派阶段，跟踪状态 | ~3K tokens |\n"
            "| 阶段代理 | 分解为批次，运行质量门 | ~5K tokens |\n"
            "| 批次代理 | 并行分派任务 | ~4K tokens |\n"
            "| 任务代理 | 执行实际工作 | ~8K tokens |\n\n"
            "## 质量门机制\n\n"
            "阶段间的质量检查点。收敛循环确保质量达标。\n"
        ),
    }
    return sections.get(slug, f"## {slug.replace('-', ' ').title()}\n\n内容即将推出。\n")


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    human_dir = root / "workflow-system" / "human"

    do_en = "--all" in sys.argv or "--lang" not in sys.argv or (
        "--lang" in sys.argv and sys.argv[sys.argv.index("--lang") + 1] == "en"
    )
    do_zh = "--all" in sys.argv or (
        "--lang" in sys.argv and sys.argv[sys.argv.index("--lang") + 1] == "zh"
    )

    count = 0
    for slug, en_title, en_desc, zh_title, zh_desc in DOCS:
        if do_en:
            _gen_doc(slug, en_title, en_desc, "en", human_dir / "en")
            count += 1
        if do_zh:
            _gen_doc(slug, zh_title, zh_desc, "zh", human_dir / "zh")
            count += 1

    print(f"Generated {count} human doc files.")


if __name__ == "__main__":
    main()
