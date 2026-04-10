---
title: "常见问题"
description: "关于工作流系统的常见问题解答。"
source_files:
  - "SKILL.md"
auto_generated: true
last_synced: "2026-04-10T06:14:27Z"
source_version: "3.0.0"
---

# 常见问题

关于工作流系统的常见问题解答。

## 什么是 DevolaFlow？

一个用于 AI 辅助软件开发的可组合工作流元框架。通过声明式 YAML 模板定义多阶段交付流水线，由 4 层代理层级和质量门机制进行编排。

## 支持哪些 AI 工具？

Cursor、Claude Code、GitHub Copilot 和 OpenAI Codex。

## 什么是仓库规则？

`.cursor/rules/` 中的 18 条规则，分为 3 个文件：
- **skill-format-rules.mdc** (SF-1 至 SF-6)：SKILL.md 格式约束
- **change-process-rules.mdc** (CP-1 至 CP-7)：测试和版本护栏
- **context-optimization-rules.mdc** (CO-1 至 CO-6)：精简消息和基准测试

## 什么是 EvoBench？

内置的上下文密度基准测试套件，衡量上下文选择质量。运行：`python -m benchmarks.devolaflow_context.runner --scenario all`

## 如何检查更新？

在 AI 工具中输入 `"update devola"` 或在终端运行 `devola-version`。
