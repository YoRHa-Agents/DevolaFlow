---
title: "快速入门指南"
description: "安装 DevolaFlow，按正确渠道验证，并运行第一个清单工作流。"
source_files:
  - "SKILL.md"
auto_generated: true
last_synced: "2026-08-27T08:33:55Z"
source_version: "17.4.0"
---

# 快速入门指南

安装 DevolaFlow，按正确渠道验证，并运行第一个清单工作流。

## 1. 选择安装渠道

各渠道的范围并不相同。

### npm / npx：用户级 Cursor 与 Claude

需要 Node 18 或更高版本，可在 Windows 使用。npm 中的 `all` 只表示该包支持
的两个用户级目标：Cursor 与 Claude。

```bash
npx @yorha-agents/devola-flow install cursor
npx @yorha-agents/devola-flow install claude
npx @yorha-agents/devola-flow install all
npx @yorha-agents/devola-flow doctor
```

默认从与 npm 包版本相同的 tag 下载。只有明确需要分支、tag 或 SHA 时才设置
`DEVOLA_FLOW_REF`。

### curl：更广的项目级/全局目标集合

curl 安装器默认使用项目级范围，并支持 `help` 中列出的全部目标，包括 Cursor、
Claude、Codex、Copilot、KimiCode、Windsurf、Zed、Cline、Roo、`local` 与
`standalone`。

```bash
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s cursor
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s claude --global
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s all
```

curl 的 `all` 会安装所有受支持宿主目标和 `local` 脚手架，但不包含
`standalone`。即使传入 `--global`，部分宿主仍只支持项目级。全局安装还会尝试
安装已注册运行时插件；只复制 skill 文件时添加 `--no-plugins`。curl 安装器没有
doctor 命令。

### pip 或 wheel：Python 运行时与本地脚手架

```bash
pip install git+https://github.com/YoRHa-Agents/DevolaFlow.git
cd your-project
devola-init local --mode=standard
```

wheel 提供 Python 运行时、CLI 与 `devola-init local`，但不打包
`workflow-system/agent/`，因此仅有 wheel 时不能复制非 local 的宿主 skill。

要运行 `devola-init cursor`、`claude`、`copilot`、`codex` 或 `all`，请使用
源码 checkout 与 editable 安装：

```bash
git clone https://github.com/YoRHa-Agents/DevolaFlow.git
cd DevolaFlow
pip install -e ".[dev]"
devola-init cursor
```

Python 中的 `all` 表示 Cursor、Claude、Copilot 与 Codex，不包含 local
脚手架。配合 `--global` 时会尝试安装插件，除非传入 `--no-plugins`。

**手动回退**

只复制
[`SKILL.md`](https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/workflow-system/agent/SKILL.md)
可以让基础指令可见，但会缺少清单声明的 references 与 examples。完整安装应优先
使用上述渠道。

## 2. 验证正确的表面

```bash
# npm 支持的用户级安装与清单一致性
npx @yorha-agents/devola-flow doctor

# Python 当前本地工作区结构
devola-init-doctor

# Python 已知 skill 副本位置审计
devola-init-doctor --skills
```

skill 复制成功不代表 host bridge 已接线。host bridge 是可选且独立的执行边界层；
请阅读 [host bridge 参考](https://github.com/YoRHa-Agents/DevolaFlow/blob/main/workflow-system/agent/references/host-bridges.md)，安装宿主专用 bridge，先确认一个
受支持事件确实到达 bridge，再持久启用 `DEVOLAFLOW_HOST_ENFORCE=1`。

## 3. 运行第一个清单工作流

打开已安装的 AI 宿主，输入自然语言请求：

```text
修复登录超时 bug，并验证回归测试。
```

预期流程：

1. DevolaFlow 从注册表派生的 25 个清单种子中选择一个，
   作为分解知识。
2. 你确认目标、可测清单、P0/P1/P2 优先级与 preflight 决策。
3. 唯一的 `change-driven` 运行时通过 L0 Project → L1 Wave → L2 Task 执行
   有界轮次。
4. Task 在 StatusReport 中返回证据；L0 仅在核验后勾选。

不需要工作流 runner CLI。

## 4. 按渠道更新

```bash
# npm 用户级 Cursor/Claude 副本
npx @yorha-agents/devola-flow update all

# curl 支持的宿主 skill 副本；--force 可重新下载相同 stamp
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s update

# local 工作区与 standalone 文件：重新运行对应的显式安装目标
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s local
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s standalone

# Python 运行时或 wheel
pip install --upgrade git+https://github.com/YoRHa-Agents/DevolaFlow.git
devola-init local --mode=standard

# 源码 checkout 与已复制的宿主 skill
git pull
pip install -e ".[dev]"
devola-init cursor
```

curl `update` 只扫描受支持的宿主 skill 副本位置，不扫描 `local` 工作区或
`standalone` 文件；这两类表面需重新运行对应的显式安装目标。更新 Python 包
不会静默刷新之前复制的宿主 skill。
