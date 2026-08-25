---
title: "快速入门指南"
description: "10 分钟内开始使用 DevolaFlow。"
source_files:
  - "SKILL.md"
auto_generated: true
last_synced: "2026-08-25T07:21:59Z"
source_version: "16.0.0"
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

下载 [SKILL.md](https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/workflow-system/agent/SKILL.md) 并放置到：

| 工具 | 路径 |
|------|------|
| Cursor | `.cursor/skills/devola-flow/SKILL.md` |
| Claude Code | `.claude/skills/devola-flow/SKILL.md` |
| Copilot | `.github/copilot-instructions.md` |
| Codex | `~/.codex/skills/devola-flow/SKILL.md` |

## 第二步：验证安装

```bash
devola-version   # 应输出当前 DevolaFlow 版本
```

## 第三步：尝试你的第一个工作流

打开你的 AI 工具，尝试以下提示词：

示例：修复一个 Bug（热修复工作流）

```
修复登录超时 bug — 用户在 30 秒不活动后报告 500 错误
```

幕后发生了什么：
1. DevolaFlow 从“修复”与“bug”匹配 **hotfix 清单种子**
2. L0 与你共同锚定目标、实体化清单和已签署的 preflight
3. L0 选取最高优先级清单项并划分波次
4. L1 Wave 向隔离的 L2 Task 下发诊断、修复和取证工作
5. L0 核验证据并勾选已通过的断言；如有未完成项，再开启一个有界轮次

示例：构建新功能（完整流水线）

```
实现一个用户通知系统，支持邮件和应用内消息两种渠道
```

发生了什么：
1. DevolaFlow 选择 **full-pipeline 清单种子**
2. 种子依据历史原语来源实体化可测的设计、实现、审查、测试和发布断言；这些来源不规定执行顺序
3. 你确认清单优先级和 preflight 决策
4. L0 通过 L1 Wave 与隔离的 L2 Task 运行有界清单轮次
5. 每个已勾选项都附带证据，未解决的 blocker 保持未勾选
6. 只有清单合同通过 archive gate 后，源真相才可变更

示例：快速调研（无代码）

```
调研实时通知的最佳方案 — 对比 WebSocket、SSE 和轮询
```

发生了什么：
1. DevolaFlow 选择 **research-only 清单种子**
2. 实体化后的清单要求产出有证据的结构化对比报告，不写代码

## 第四步：深入探索

查看全部 23 个清单种子：[清单种子目录](workflow-types.md)了解架构：[架构概述](architecture-overview.md)为你的工具进行设置：[集成指南](integration-guide.md)自定义工作流：[自定义指南](customization-guide.md)

## 检查更新

在 AI 工具中输入：`"update devola"` — 它会从 GitHub 检查新版本并提供更新命令。

或在终端中：

```bash
# 安装器更新
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s update

# pip 更新
pip install --upgrade git+https://github.com/YoRHa-Agents/DevolaFlow.git
```
