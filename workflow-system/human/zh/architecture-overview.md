---
title: "架构概述"
description: "三层清单轮次架构、来源原语与证据门。"
source_files:
  - "SKILL.md"
auto_generated: true
last_synced: "2026-08-26T18:26:37Z"
source_version: "17.1.1"
---

# 架构概述

三层清单轮次架构、来源原语与证据门。

## 三层架构

| 层级 | 职责 | 边界 |
|---|---|---|
| L0 Project | 确认 goal/checklist/preflight、选择轮次、核验证据 | 不实施 |
| L1 Wave | 划分所有权安全的 Task 并聚合报告 | 不修改 Task 产出 |
| L2 Task | 实施一个原子任务并自证 | 不派生 Agent |

升级链为 Task → Wave → Project → Human，每个重试循环都有上限。

## 种子与运行时

注册表当前提供 24 个不可执行清单种子，其中
12 个原语标签
（`analyze`, `deploy`, `design`, `implement`, `plan`, `refine`, `release`, `research`, `review`, `test`, `validate`, `verify`）只保存历史分解
来源；列表顺序不是运行时顺序。`change-driven` 是唯一可执行运行时。

## 证据合同

只有所选清单断言具备有效证据、配置检查通过、reinforcement 已关闭且 blocker 为零，
轮次才通过。合成分只表示趋势，不能替代逐项证据。

## 上下文与治理

任务自适应选择来自 `workflow-system/agent/context_profiles.yaml` 中派生的
24 个 profile。规范 `.rules/` 源当前包含
56 个规则 ID；生成面必须经编译，不得手改。

harness 基线结算与周期归档保留是政策。周期负责人在周期关闭时人工执行归档汇总；
目前没有自动归档 hook。
