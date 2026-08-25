---
title: "架构概述"
description: "三层清单轮次架构、来源原语与质量门机制。"
source_files:
  - "SKILL.md"
auto_generated: true
last_synced: "2026-08-25T10:02:23Z"
source_version: "17.0.0"
---

# 架构概述

三层清单轮次架构、来源原语与质量门机制。

## 系统概述

DevolaFlow 通过 **清单轮次** 与 **三层 Agent 架构** 编排复杂软件任务。经用户确认的 checklist 是执行合同：每项都可测、每次完成都有证据、每个循环都有上限。

```
用户请求
    │
    ▼
┌─────────────────────┐
│   清单种子            │  选择领域分解知识
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│  L0: Project Agent   │  锚定清单，管理轮次      (~5K tokens)
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│  L1: Wave Agent      │  分派任务，聚合证据      (~5K tokens)
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│  L2: Task Agent      │  **执行实际工作**        (~8K tokens)
└─────────────────────┘
```

**关键不变量**：只有 L2 Task Agent 执行实际工作，包括编写代码、运行测试、审查和撰写文档。L0 Project 与 L1 Wave 只负责分派、监控、核验证据和汇报。

## 三层层级

| 层级 | 角色 | 上下文预算 | 委托给 | 不可以 |
|------|------|-----------|--------|--------|
| **L0: Project** | 锚定 goal/checklist/preflight、每轮取项、核验证据与门控 | ~5K tokens | L1 Wave | 实施或修改 Task 产出 |
| **L1: Wave** | 分派并行 Task、检查文件冲突、聚合证据提案 | ~5K tokens | L2 Task | 执行任何 Task 的工作 |
| **L2: Task** | 执行单一原子清单任务并报告证据 | ~8K tokens | 无（叶节点） | 派生子 Agent 或写出 owned set |

升级链始终向上：**Task → Wave → Project → Human**。

## 清单轮次运行时

`change-driven` 是唯一可执行运行时：

1. **Propose**：L0 与用户锚定编号目标和可测清单。
2. **Preflight**：用户一次性签署项目决策与卡点预授权。
3. **Round**：L0 选取最高优先级未完成项，划分波次，并把计划写入 `stage.md`。
4. **Execute**：L1 每波最多向五个隔离的 L2 Task 下发任务。
5. **Verify**：Task 报告证据，L1 聚合，L0 核验后才可勾选。
6. **Repeat or archive**：本轮取项全部有证据地勾选且无 blocker 才通过；完整清单与 archive gate 均通过后才能归档。

轮次中的合成分只用于趋势观测，不能替代主合同：有有效证据的已勾选断言与零 blocker。

## 23 个清单种子与原语来源

注册表包含 **23 个不可执行的清单种子**，外加唯一的 `change-driven` 运行时。种子提供意图关键词、清单分区、可测断言模板和验证建议，不提供运行时 DAG。

种子中的 `source_stages` **只记录来源**。它保留历史来源 ID 与 14 种原语标签之一；列表顺序仅供展示，不决定执行顺序：

| 类别 | 原语 | 用途 |
|------|------|------|
| **发现** | `research`, `analyze` | 收集信息，评估现状 |
| **塑形** | `design`, `plan` | 定义架构，分解为任务 |
| **构建** | `implement`, `refine` | 编写代码，修复问题 |
| **验证** | `review`, `test`, `validate`, `verify` | 检查质量，运行测试 |
| **交付** | `release`, `deploy`, `monitor` | 打包，发布，观测 |
| **控制** | `gate` | 阻断推进的质量检查点 |

## 任务自适应上下文选择

每种任务类型有一个 **上下文配置**，只选择相关的 SKILL.md 段落：

- **热修复** 代理接收：分诊流程、修复指南、测试要求 — 跳过设计原语
- **调研** 代理接收：调研方法、对比框架, 跳过收敛循环
- **设计** 代理接收：架构模式、ADR 模板, 跳过发布流程

## 质量门机制

```
composite = test_quality × 0.30 + code_review × 0.30
          + architecture × 0.20 + benchmark × 0.20
```

**通过条件**（全部必须满足）：
1. 本轮取出的每个清单项都有有效证据并已勾选
2. 零 blocker 且零 MUST 优先级违规
3. 归档时还须达到配置的合成分与覆盖率阈值

**失败时**：未完成项和发现会作为 reinforcement 进入下一个有界轮次。进度停滞或达到轮次上限时，按 Task → Wave → Project → Human 升级。

## 人类交互界面

除了仅供 Agent 使用的 `.local/.agent/` 工作区之外，DevolaFlow 还维护持久化的 **`.local/human/`** 界面（v14.0.0+）。这个三区目录树将 **不可变的 INPUT**（人类想要什么）与 **简洁的 OUTPUT**（Agent 回报什么）分离：

| 区域 | 所有权与内容 |
|------|--------------|
| **`input/`** | 由人类拥有，一经批准即不可变：constitution、以 REQ-ID 为键的需求，以及只追加的修订账本 |
| **`output/`** | 由 Agent 写入且简洁：`DIGEST.md` 与收敛报告 |
| **`archive/`** | 已被取代的工件 |

每个工件都有 TOKEN 预算以保持精简。可用 `python -c "from devolaflow.agent_workspace import lint_human; print(lint_human())"` 验证。

## 仓库规则

`.rules/` 中的 62 条可执行规则（5 个分层源文件），编译输出到 `AGENTS.md` 与
`.cursor/rules/repo-governance.mdc`：

| 规则层 | 涵盖内容 |
|---------|---------|
| `soul.mdc`（S-1 到 S-10，P0） | 不可违背的红线 — 测试覆盖率底线（≥80%）、无幽灵功能、无静默失败、保护分支 |
| `architecture.mdc`（A-1 到 A-7，P1） | 三层 Agent 体系、缓存布局治理、令牌预算、单一事实源注册表 |
| `conventions.mdc`（C-1 到 C-9，P2；C-8 已退役） | 行数预算、前置元数据、版本一致性、精简消息、逐字提取 |
| `workflow.mdc`（W-1 到 W-24，P3） | 迭代规划、基准守护、版本升级协议、环境变量复用策略 |
| `style.mdc`（ST-1 到 ST-13，P4） | 文档同步、Web 体验、双语完整性 |

v14.2.1 之前的独立规则文件（`skill-format-rules.mdc`、`change-process-rules.mdc`、
`context-optimization-rules.mdc` 等）曾转换为弃用指针存根，并已于 v15.0.0 退役，
其 SF-/CP-/CO- 内容已并入上述各层。
