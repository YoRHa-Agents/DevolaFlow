---
title: "Agent 层级指南"
description: "理解 Project、Wave、Task 三层委托架构。"
source_files:
  - "SKILL.md"
auto_generated: true
last_synced: "2026-08-25T08:45:55Z"
source_version: "17.0.0"
---

# Agent 层级指南

理解 Project、Wave、Task 三层委托架构。

## 为什么需要层级？

单个 AI 代理处理复杂任务（如 "构建认证系统"）面临两个问题：
1. **上下文溢出** — 它试图同时记住所有内容
2. **范围蔓延**, 它在设计、实现和审查之间无序切换

DevolaFlow 用三层架构约束上下文漂移，同时缩短分派链。

## L0: Project Agent（~5K tokens）

Project Agent 是 **乐团指挥**。它选择清单种子，并与用户锚定 `goal.md`、`checklist.md`、`preflight.md`。此外，它还会：
- 每个有界轮次按 P0/P1/P2 取项并划分波次
- 核验 Task 证据后才勾选断言
- 评估轮次门与 archive gate：推进、重试或升级
- 向用户报告最终状态

**绝不会**：实施、运行测试、撰写交付物或修改 Task 产出。

## L1: Wave Agent（~5K tokens）

Wave Agent 协调一组有界并行 Task。它：
- 接收清单项 ID、逐字断言、验证规则与文件所有权
- 向最多五个 L2 Task 分派互不重叠的可写文件
- 收集 StatusReport 并检查跨任务冲突
- 聚合证据，向 L0 提交精简的勾选提案

**绝不会**：执行任何 Task 的工作或修改其产出。

## L2: Task Agent（~8K tokens）

Task Agent 是 **唯一实施层**。它：
- 接收一个与清单项 ID 绑定的原子任务
- 只在 owned files 内工作
- 根据所给断言自证，但不自评分
- 向 L1 报告工件、测试结果和逐字证据

**约束**：不得派生子 Agent，不得写出 owned set。

## 清单轮次流

```
L0 取出未完成清单断言，并在 stage.md 记录本轮
  └─ L1 Wave 向隔离的 L2 Task 分派任务
       ├─ L2 Task 执行并报告证据
       └─ L2 Task 执行并报告证据
  └─ L1 聚合证据并提出勾选建议
L0 核验证据、勾选通过项，然后结束或重复本轮
```

`stage.md` 是轮次管控工件，不是 Agent 角色。清单种子中的 `source_stages` 只保留历史来源 ID 与原语来源，不具备可执行顺序语义。

## 升级链

```
Task Agent → Wave Agent → Project Agent → Human
```

升级始终 **向上** 移动，绝不跳级。每个失败都有分类：

| 严重度 | 动作 |
|--------|------|
| `AUTO_RECOVER` | 重试最多 3 次，指数退避 |
| `PAUSE` | 暂停任务，排队提问，继续并行工作 |
| `HUMAN_INTERVENE` | 停止轮次，向人工展示选项 |
| `FULL_ROLLBACK` | 回滚到检查点，终止所有工作 |

## 通信协议

所有层间通信使用 **类型化 YAML 消息**（非自由文本）：

- **TaskDispatch**：task_id、type、title、description、owned_files、acceptance_criteria、timeout
- **StatusReport**：task_id、state、progress_pct、artifacts、metrics
- **ExceptionEscalation**：severity、context、options

## 示例：热修复追踪

```
用户："修复登录超时 bug"
  └─ L0 Project：选择 hotfix 种子；用户确认清单与 preflight
       └─ 第 1 轮 / L1 Wave
            └─ L2 Task：复现缺陷并报告根因证据
       └─ L0：核验证据并勾选诊断断言
       └─ 第 2 轮 / L1 Wave
            ├─ L2 Task：实现最小修复
            └─ L2 Task：运行聚焦回归测试
       └─ L1：聚合证据；L0 核验并勾选两项断言
  └─ L0 Project：archive gate 通过，向用户报告 SUCCESS
```
