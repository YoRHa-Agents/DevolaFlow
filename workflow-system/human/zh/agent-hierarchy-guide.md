---
title: "Agent 层级指南"
description: "Project、Wave、Task 的职责与升级链。"
source_files:
  - "SKILL.md"
auto_generated: true
last_synced: "2026-08-31T11:34:52Z"
source_version: "22.1.0"
---

# Agent 层级指南

Project、Wave、Task 的职责与升级链。

## L0 Project

与用户确认目标、清单、优先级、preflight 与轮次选择，核验证据，并决定推进、重试、
升级或终止。绝不执行已委托工作。

## L1 Wave

向最多五个可写所有权互斥的 L2 Task 分派任务，检测冲突并聚合 StatusReport。
绝不实施，也不修改 Task 产出。

## L2 Task

接收一个原子 TaskDispatch，只写 owned files，执行有界验证并返回可证伪证据。
不得派生另一个 Agent。

## 消息与升级

TaskDispatch 向下，StatusReport 向上。异常按 Task → Wave → Project → Human 升级。
自由文本共享状态不是工件合同。
