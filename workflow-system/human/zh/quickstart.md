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

## 2. 验证

向你的 AI 工具发送：

> "使用 full-pipeline 工作流实现一个新功能"

它应该设置 4 层层级（项目代理分派阶段代理）并选择 8 阶段的 `full-pipeline` 工作流。

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
