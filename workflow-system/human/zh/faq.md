---
title: "常见问题"
description: "关于工作流系统的常见问题解答。"
source_files: ["SKILL.md"]
auto_generated: true
last_synced: "2026-04-05T00:00:00Z"
source_version: "1.0.0"
---

# 常见问题

## 通用

**问：DevolaFlow 是什么？**

答：一个用于 AI 辅助软件开发的可组合工作流元框架。它将多阶段交付管线定义为声明式 YAML 模板，通过 4 层代理层级和质量门来编排。

**问：支持多少种工作流类型？**

答：11 种内置类型，加上无限自定义模板。

**问：支持哪些 AI 工具？**

答：Cursor、OpenAI Codex (CLI)、Claude Code、GitHub Copilot。

## 安装

**问：最快的上手方式？**

答：一条命令：`curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s cursor`。下载 SKILL.md、8 个引用文件、3 个示例和规则到 `.cursor/skills/devola-flow/`。加 `--global` 安装到用户全局目录。

**问：项目本地还是全局安装？**

答：Cursor 两种都支持：`--project`（默认）安装到 `.cursor/skills/`，skill 随项目提交；`--global` 安装到 `~/.cursor/skills/`，所有项目共享但不提交。Claude Code 也支持两种范围：项目本地是 `./CLAUDE.md`，用户全局是 `~/.claude/CLAUDE.md`。

**问：如何更新到最新版本？**

答：运行 `curl ... | bash -s update`，自动查找所有已安装位置并重新下载。

**问：需要 Python 吗？**

答：不需要。`curl` 安装器和手动下载无需 Python。Python 3.11+ 仅用于 CLI 工具（模板验证、质量门评分、构建管线）。

## 架构

**问：调度代理能写代码吗？**

答：不能。只有任务代理（第 3 层）执行实际工作。这是系统最强不变式。

**问：质量门的通过阈值是多少？**

答：默认（standard 配置）：组合分数 >= 85，零 blocker 发现，至少 1 轮评审。

**问：质量门失败怎么办？**

答：如果还有轮次（默认最多 3 轮），运行收敛循环。超过最大轮次则向人类提交分歧报告。

## 使用

**问：如何创建自定义工作流？**

答：在 `workflow-system/agent/templates/custom/` 中创建 YAML 文件。运行 `validate-template your-file.yaml` 检查。参见[自定义指南](customization-guide.md)。

**问：lattice 警告是问题吗？**

答：不是。Lattice 警告是建议性的，不阻止验证。
