---
title: "集成指南"
description: "从清单派生的宿主配置、安装渠道与可选 host bridge。"
source_files:
  - "SKILL.md"
auto_generated: true
last_synced: "2026-08-28T15:33:00Z"
source_version: "20.0.0"
---

# 集成指南

从清单派生的宿主配置、安装渠道与可选 host bridge。

## Host Support Contract

规范宿主契约位于 `workflow-system/agent/hosts.yaml`。支持按档位定义；
保证宿主必须声明完整 delivery floor，可选能力不会从其他安装注册表推断。

| 档位 | 宿主 |
|---|---|
| `guaranteed` | `cursor`、`claude`、`codex`、`copilot`、`kimicode`、`dsh` |
| `community-installable` | `windsurf`、`zed`、`cline`、`roo` |
| `community-build-only` | `continue`、`openclaw`、`gemini`、`jetbrains`、`amazon_q`、`augment`、`trae` |

## 从清单派生的安装 profile

下列 profile 名称与文件集合来自 `workflow-system/agent/manifest.yaml`。
`references` 集合当前包含 31 个文件；消费者从清单派生列表。

| 目标 | 清单类型 | 文件集合 |
|---|---|---|
| `cursor` | `skill-dir` | `core`, `references`, `examples` |
| `claude` | `skill-dir` | `core`, `references`, `examples` |
| `codex` | `skill-dir` | `core`, `references` |
| `kimicode` | `skill-dir` | `core`, `references`, `examples` |
| `dsh` | `skill-dir` | `core`, `references`, `examples` |
| `copilot` | `rule-file` | `core` |
| `windsurf` | `rule-file` | `core` |
| `zed` | `rule-tree` | `core`, `references` |
| `cline` | `rule-tree` | `core`, `references` |
| `roo` | `rule-tree` | `core`, `references` |

## 渠道范围

| 渠道 | 范围与 `all` 含义 |
|---|---|
| npm/npx | 用户级 `cursor`、`claude`，或 npm `all`（两者） |
| curl | 默认项目级；提供受支持宿主目标以及独立的 `local`、`standalone` 目标；`--global` 仅在支持时生效；curl `all` 安装所有受支持宿主和 `local`，不包含 `standalone` |
| pip/wheel | 运行时 CLI 与 `devola-init local`；非 local skill 复制需要 clone 加 editable 安装 |
| Python 源码 | `devola-init all` 表示 Cursor、Claude、Copilot、Codex，不包含 `local` |

```bash
# 完整、自包含的 curl 示例
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s cursor
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s claude --global --no-plugins
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s kimicode
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s zed
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s cline
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s roo
```

## 本地工作区模式与插件

```bash
devola-init local --mode=core
devola-init local --mode=standard
devola-init local --mode=full
devola-init cursor --global --no-plugins
```

`core` 跳过编译与示例，`standard` 编译但不生成示例，`full` 编译并播种示例。
全局 curl/Python 安装默认尝试运行时插件；`--no-plugins` 只保留 skill 文件。
插件安装与宿主能否发现已复制 skill 是两件事。

## Doctor 与更新边界

```bash
npx @yorha-agents/devola-flow doctor
devola-init-doctor
devola-init-doctor --skills
npx @yorha-agents/devola-flow update all
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s update
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s local
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s standalone
```

第一个 doctor 检查 npm 支持的用户级位置，第二个检查当前 Python 工作区，第三个
扫描已知 skill 副本。curl 没有 doctor。curl `update` 只扫描受支持的宿主 skill
副本位置，不扫描 `local` 工作区或 `standalone` 文件；这些表面需重新运行显式的
`local` 或 `standalone` 安装目标。

## 可选 host bridge 执行边界

复制 skill 只让 Markdown 可发现。host bridge 另行把宿主工具事件路由到生命周期
边界执行。每个宿主的 bridge 状态与证据在 `hosts.yaml` 中声明；Copilot 的
stdout-JSON bridge 路径在本版本中为已实现。

按 [宿主专用 bridge 流程](https://github.com/YoRHa-Agents/DevolaFlow/blob/main/workflow-system/agent/references/host-bridges.md) 操作，例如：

```bash
python -m devolaflow.hostbridge install cursor
python -m devolaflow.hostbridge install claude
python -m devolaflow.hostbridge install codex
```

确认宿主配置已激活（Codex 还需 `/hooks` trust），在单次环境中执行一个已知允许事件，
并检查 `.local/telemetry/hostbridge.jsonl`。确认后再持久启用：

```bash
export DEVOLAFLOW_HOST_ENFORCE=1
```

不支持 bridge 的宿主保持 skill-only，不应描述为已执行边界。
