---
title: "常见问题"
description: "关于清单轮次、安装范围、更新与发布证据的常见问题。"
source_files:
  - "SKILL.md"
auto_generated: true
last_synced: "2026-08-29T11:23:55Z"
source_version: "21.2.0"
---

# 常见问题

关于清单轮次、安装范围、更新与发布证据的常见问题。

## DevolaFlow 执行什么？

它从注册表派生的 27 个清单种子中选择分解知识，将其实体化为
用户确认的清单，并通过唯一的 `change-driven` 运行时执行该合同。

## 三个 `all` 含义相同吗？

不同。npm 的 `all` 是用户级 Cursor 加 Claude；Python 的 `devola-init all`
是 Cursor、Claude、Copilot、Codex，不包含 `local`；curl 的 `all` 会安装所有
受支持宿主目标和 `local`，但不包含 `standalone`。

## 应运行哪个 doctor？

- `npx @yorha-agents/devola-flow doctor`：npm 支持的用户级安装。
- `devola-init-doctor`：当前 Python 本地工作区。
- `devola-init-doctor --skills`：已知 skill 副本位置。

curl 安装器没有 doctor。

## 更新 Python 会更新已复制 skill 吗？

不会。更新包后，为本地脚手架重新运行 `devola-init local`；非 local skill 请从
源码 checkout 重新运行对应宿主目标。npm 与 curl 各有自己的 update 命令。

## host bridge 会自动执行吗？

不会。skill 安装与 host bridge 接线是独立状态。设置
`DEVOLAFLOW_HOST_ENFORCE=1` 前必须验证一个受支持的宿主 bridge。

## harness 归档汇总会自动执行吗？

不会。基线结算与归档保留是周期关闭时人工执行的发布政策；当前运行时没有自动归档
hook。
