---
title: "快速入门指南"
description: "10 分钟内开始使用 DevolaFlow。"
source_files:
  - "SKILL.md"
auto_generated: true
last_synced: "2026-04-10T06:02:57Z"
source_version: "3.0.0"
---

# 快速入门指南

10 分钟内开始使用 DevolaFlow。

## 前置条件

- Python 3.11+
- pip

## 安装

```bash
pip install -e ".[dev]"
```

## 你的第一个工作流

1. 运行 `detect-repo-mode` 识别仓库类型
2. 运行 `validate-template --all` 验证模板有效性
3. 根据任务选择工作流类型
4. 遵循 4 层层级：项目代理分派阶段代理

## 查看版本

```bash
devola-version   # 输出 DevolaFlow vX.X.X
```

或在 AI 工具中输入 `"update devola"` 查看已安装版本并检查是否有新版本。

## 更新 DevolaFlow

**在 AI 工具中更新**（推荐）：

输入 `"update devola"` 或 `"/update-devola"`。代理会从 GitHub 检查最新版本并提供对应的更新命令。

**在终端中更新：**

```bash
# 安装器更新
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s update

# pip 更新
pip install --upgrade git+https://github.com/YoRHa-Agents/DevolaFlow.git
```

