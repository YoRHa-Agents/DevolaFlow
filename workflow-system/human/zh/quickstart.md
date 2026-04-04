---
title: "快速入门指南"
description: "5 分钟内将 DevolaFlow 接入你的 AI 工具。"
source_files: ["SKILL.md"]
auto_generated: true
last_synced: "2026-04-04T00:00:00Z"
source_version: "1.0.0"
---

# 快速入门指南

5 分钟内将 DevolaFlow 接入你的 AI 工具。

## 1. 安装（三选一）

### 最快：一条命令

```bash
# Cursor（项目本地）
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s cursor

# Cursor（用户全局，所有项目共享）
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s cursor --global

# Claude Code
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s claude

# Copilot
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s copilot
```

### 备选：pip

```bash
pip install git+https://github.com/YoRHa-Agents/DevolaFlow.git
devola-init cursor       # 或: devola-init claude / copilot / all
```

### 最简：下载单文件

下载 [MVP-SKILL.md](https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/workflow-system/agent/MVP-SKILL.md) 放到对应位置：

| 工具 | 放置位置 |
|------|---------|
| Cursor | `.cursor/skills/devola-flow/SKILL.md` 或 `~/.cursor/skills/devola-flow/SKILL.md` |
| Claude Code | 项目根目录 `./CLAUDE.md` |
| Copilot | `.github/copilot-instructions.md` |
| Codex | `~/.codex/skills/devola-flow/SKILL.md` |

## 2. 使用

安装后，DevolaFlow 会在你让 AI 工具做多步骤任务时自动激活。试试这些提示词：

```
"从零实现一个用户认证系统"
```
Agent 选择 `full-pipeline`（8 阶段），建立 4 层层级，先通过子代理分派设计阶段。不会试图一次性完成所有工作。

```
"修复登录超时的 bug"
```
Agent 选择 `hotfix`（4 阶段：分析 - 修复 - 测试 - 发布），跳过设计和计划，直接分析 bug。

```
"调研 Rust 最好的 TUI 框架"
```
Agent 选择 `research-only`（3 阶段），产出结构化对比报告，不写代码。

### Agent 行为变化

| 没有 DevolaFlow | 有 DevolaFlow |
|----------------|--------------|
| 一次性大段处理 | 按阶段通过子代理逐步分派 |
| 一次加载全部上下文 | 每个任务只注入 ~8K token 的精准上下文 |
| 写完直接提交 | 质量门：composite >= 85，0 blocker，已评审 |
| 发现问题手动修 | 收敛循环：评审 - 修复 - 测试 - 修复（自动，最多 3 轮） |
| 无结构，随意改文件 | 任务拥有互斥文件集，每批次最多 5 个并行 |

### 提示词对照表

| 你说的话 | 选择的工作流 | 阶段 |
|---------|------------|------|
| "从零实现 X" | `full-pipeline` | 设计 - 计划 - 实现 - 评审 - 测试 - 质量门 - 发布 |
| "修复 X 的 bug" | `hotfix` | 分析 - 修复 - 测试 - 发布 |
| "重构 X" | `refactoring` | 范围 - 计划 - 实现 - 测试 - 评审 |
| "调研 X" / "对比 X 和 Y" | `research-only` | 调研 - 对比 - 报告 |
| "设计 X 的架构" | `RDRR` | 调研 - 设计 - 评审 - 优化（循环） |
| "给 Y 加 X 功能" | `feature-enhancement` | 范围 - 设计 - 计划 - 实现 - 评审 - 测试 - 发布 |
| "从 X 迁移到 Y" | `migration` | 评估 - 计划 - 实现 - 验证 - 切换 |
| "X 可行吗？" | `spike-poc` | 调研 - 原型 - 评估 |
| "写 X 的文档" | `documentation` | 调查 - 编写 - 评审 |
| "X 的安全审计" | `security-audit` | 威胁建模 - 扫描 - 分析 - 修复 - 验证 |

## 3. 更新

```bash
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s update
```

自动查找所有已安装的位置并更新到最新版本。

## 4. 基本概念

### 11 种工作流类型

| 任务 | 推荐工作流 |
|------|-----------|
| 从零构建新功能 | `full-pipeline`（8 阶段） |
| 修复生产 bug | `hotfix`（4 阶段） |
| 清理技术债务 | `refactoring`（5 阶段） |
| 调研评估方案 | `research-only`（3 阶段） |
| 设计系统架构 | `design-only` 或 `RDRR` |

### 4 层层级

```
项目代理  -- 选择工作流，分派阶段（不写代码）
  阶段代理  -- 分解为批次，运行质量门（不写代码）
    批次代理  -- 并行分派任务（不写代码）
      任务代理  -- 唯一执行工作的层级（写代码、跑测试、做评审）
```

### 质量门

每个阶段后: `composite = test*0.30 + review*0.30 + arch*0.20 + bench*0.20 >= 85`

## 下一步

| 想要... | 阅读 |
|--------|------|
| 查看全部工作流 | [工作流类型](workflow-types.md) |
| 理解系统架构 | [架构概述](architecture-overview.md) |
| 创建自定义工作流 | [自定义指南](customization-guide.md) |
| 集成 CI/CD | [集成指南](integration-guide.md) |
| 交互式探索 | [在线演示](https://yorha-agents.github.io/DevolaFlow/) |
