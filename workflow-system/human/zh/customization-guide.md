---
title: "自定义指南"
description: "在不分叉运行时事实源的前提下自定义种子、上下文配置、规则与本地脚手架。"
source_files:
  - "SKILL.md"
auto_generated: true
last_synced: "2026-09-01T07:32:21Z"
source_version: "24.1.0"
---

# 自定义指南

在不分叉运行时事实源的前提下自定义种子、上下文配置、规则与本地脚手架。

## 清单种子

在 `workflow-system/agent/templates/seeds/` 下添加种子，并在
`templates/registry.yaml` 中注册一次。种子可以定义意图、分区、断言模板、建议
优先级、验证与来源，但不得定义另一个可执行 DAG；运行时仍是 `change-driven`。

## 上下文配置

编辑 `workflow-system/agent/context_profiles.yaml`，确保 critical 段落不超预算，
并运行 `python -m devolaflow.task_adaptive_selector <task-type> --verbose` 检查
受影响的选择结果。

## 规则

编辑 `.rules/*.mdc` 后运行 `make compile-rules`。不得手改生成的 `AGENTS.md`、
`.cursor/rules/repo-governance.mdc` 或 `docs/STYLE-RULES.md`。

## 本地脚手架深度

`devola-init local --mode=core|standard|full` 选择脚手架深度。单独传入的
`--no-compile`、`--with-examples`、`--no-with-examples` 会覆盖 mode 默认值。
重复运行保持幂等。
