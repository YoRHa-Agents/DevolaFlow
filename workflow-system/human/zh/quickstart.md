---
title: "快速入门指南"
description: "10 分钟内开始使用 DevolaFlow。"
source_files:
  - "SKILL.md"
auto_generated: true
last_synced: "2026-04-12T07:41:06Z"
source_version: "4.0.1"
---

# 快速入门指南

10 分钟内开始使用 DevolaFlow。

## 前置条件

- Python 3.11+
- pip
- 以下工具之一：Cursor、Claude Code、GitHub Copilot 或 OpenAI Codex

## 第一步：安装 DevolaFlow

选择适合你的安装方式：

**方式 A — 一键安装（推荐）：**

```bash
INSTALLER="https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh"

# 为 Cursor 安装（项目级）
curl -fsSL $INSTALLER | bash -s cursor

# 或为所有工具一次性安装
curl -fsSL $INSTALLER | bash -s all
```

**方式 B — pip 安装：**

```bash
pip install git+https://github.com/YoRHa-Agents/DevolaFlow.git
cd your-project/
devola-init cursor       # 仅 Cursor
devola-init all          # 所有工具
```

**方式 C — 手动安装（单文件）：**

下载 [MVP-SKILL.md](https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/workflow-system/agent/MVP-SKILL.md) 并放置到：

| 工具 | 路径 |
|------|------|
| Cursor | `.cursor/skills/devola-flow/SKILL.md` |
| Claude Code | `./CLAUDE.md` |
| Copilot | `.github/copilot-instructions.md` |
| Codex | `~/.codex/skills/devola-flow/SKILL.md` |

## 第二步：验证安装

```bash
devola-version   # 应输出当前 DevolaFlow 版本
```

## 第三步：尝试你的第一个工作流

打开你的 AI 工具，尝试以下提示词：

### 示例：修复一个 Bug（热修复工作流）

```
修复登录超时 bug — 用户在 30 秒不活动后报告 500 错误
```

幕后发生了什么：
1. DevolaFlow 从 "修复" + "bug" 检测到 **hotfix** 意图
2. **分诊阶段**：Agent 分析 bug，定位根因
3. **修复阶段**：Agent 实现最小化修复
4. **测试阶段**：Agent 对受影响代码运行聚焦测试
5. **发布阶段**：Agent 准备补丁部署

### 示例：构建新功能（完整流水线）

```
实现一个用户通知系统，支持邮件和应用内消息两种渠道
```

发生了什么：
1. DevolaFlow 选择 **full-pipeline** 工作流（8 个阶段）
2. **设计**：通知系统架构
3. **规划**：分解为批次和任务
4. **实现**：TDD 编写代码（目标 80% 覆盖率）
5. **审查 → 测试 → 修正**：收敛循环直到质量达标
6. **质量门**：复合评分须达到 ≥85 且零阻断问题
7. **发布**：打包和标签

### 示例：快速调研（无代码）

```
调研实时通知的最佳方案 — 对比 WebSocket、SSE 和轮询
```

发生了什么：
1. DevolaFlow 选择 **research-only** 工作流
2. Agent 生成结构化对比报告 — 不写代码

## 第四步：深入探索

- 查看全部 17 种工作流：[工作流类型](workflow-types.md)
- 了解架构：[架构概述](architecture-overview.md)
- 为你的工具进行设置：[集成指南](integration-guide.md)
- 自定义工作流：[自定义指南](customization-guide.md)

## 检查更新

在 AI 工具中输入：`"update devola"` — 它会从 GitHub 检查新版本并提供更新命令。

或在终端中：

```bash
# 安装器更新
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s update

# pip 更新
pip install --upgrade git+https://github.com/YoRHa-Agents/DevolaFlow.git
```
