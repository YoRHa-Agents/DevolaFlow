---
title: "快速入门指南"
description: "10 分钟内开始使用 DevolaFlow。"
source_files: ["SKILL.md"]
auto_generated: true
last_synced: "2026-04-04T00:00:00Z"
source_version: "1.0.0"
---

# 快速入门指南

10 分钟内让 DevolaFlow 跑起来，编排你的第一个工作流。

## 1. 安装

```bash
git clone https://github.com/YoRHa-Agents/DevolaFlow.git
cd DevolaFlow
pip install -e ".[dev]"
```

验证：`validate-template --all` 应输出 `11 passed, 0 failed`。

## 2. 检测仓库模式

```bash
detect-repo-mode
```

DevolaFlow 自动检测仓库类型并调整行为：

| 模式 | 检测条件 | Release | CI/CD |
|------|---------|---------|-------|
| `local` | 无 `.git` 或无 remote | 跳过 | 无 |
| `github` | Remote 包含 `github.com` | GitHub Releases | GitHub Actions |
| `gitlab` | Remote 包含 `gitlab` | Registry | GitLab CI |

## 3. 选择工作流类型

| 你的任务 | 推荐工作流 |
|---------|-----------|
| 从零构建新功能 | `full-pipeline` (8 阶段，完整生命周期) |
| 修复生产 bug | `hotfix` (4 阶段，快速通道) |
| 清理技术债务 | `refactoring` (5 阶段，含回归测试) |
| 调研评估方案 | `research-only` (3 阶段，无代码) |
| 设计系统架构 | `design-only` 或 `RDRR` (调研驱动设计循环) |

全部 11 种类型：参见[工作流类型目录](workflow-types.md)。

## 4. 理解 4 层层级

```
你 (人类) 提出任务
    |
项目代理  -- 选择工作流类型，分派阶段
    |
阶段代理  -- 分解为批次，运行质量门
    |
批次代理  -- 并行分派任务
    |
任务代理  -- 唯一执行实际工作的层级
              (写代码 / 跑测试 / 做评审)
```

**黄金法则**：第 0-2 层（项目/阶段/批次）**绝不做**具体工作。它们只分派、监控、评估。只有任务代理（第 3 层）才接触文件和工具。

## 5. 接入 AI 工具

### 方式 A：快速启动（单文件）

把 `workflow-system/agent/MVP-SKILL.md` 复制到你的 AI 工具：

- **Cursor**: `.cursor/skills/workflow-orchestrator/SKILL.md`
- **Claude Code**: 项目根目录 `CLAUDE.md`
- **Copilot**: `.github/copilot-instructions.md`

### 方式 B：完整 Skill 系统

```bash
make build-skill    # 在 dist/ 下生成 cursor/codex/claude/copilot 四种输出
```

## 6. 交互式探索

浏览器打开 `workflow-system/human/demo/index.html`，或访问[在线演示](https://yorha-agents.github.io/DevolaFlow/)：

- **工作流可视化器**：选择任一工作流类型，查看阶段管线图
- **阶段探索器**：深入了解 13 个阶段原语的团队、时长、质量门标准

## 下一步

| 想要... | 阅读 |
|--------|------|
| 理解系统架构 | [架构概述](architecture-overview.md) |
| 查看全部工作流 | [工作流类型目录](workflow-types.md) |
| 创建自定义工作流 | [自定义指南](customization-guide.md) |
| 集成 CI/CD | [集成指南](integration-guide.md) |
| 排查问题 | [故障排查](troubleshooting.md) |
