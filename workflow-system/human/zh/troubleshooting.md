---
title: "故障排查"
description: "诊断安装渠道、本地脚手架、已复制的 skill 与 host bridge。"
source_files:
  - "SKILL.md"
auto_generated: true
last_synced: "2026-08-28T04:45:44Z"
source_version: "19.0.0"
---

# 故障排查

诊断安装渠道、本地脚手架、已复制的 skill 与 host bridge。

## 先识别安装渠道

**npm 用户级安装**

```bash
node --version
npx @yorha-agents/devola-flow doctor
npx @yorha-agents/devola-flow update cursor
```

Node 必须为 18 或更高版本。npm 只支持用户级 Cursor 与 Claude。安装 ref 异常时
检查 `DEVOLA_FLOW_REF`。

### curl 安装

```bash
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s help
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s update --force
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s uninstall --dry-run
```

每段命令都可独立复制。curl 有 `update` 与 `uninstall`，但没有 doctor。
`update` 只扫描受支持的宿主 skill 副本位置，不扫描 `local` 工作区或
`standalone` 文件；这些表面需重新运行对应的显式安装目标。只有同时安装了
Python 包，并需要审计已知 skill 路径时，才使用 `devola-init-doctor --skills`。

### pip 或 wheel 安装

```bash
python -c "import devolaflow; print(devolaflow.__version__)"
devola-init local --mode=core
devola-init-doctor
```

仅 wheel 安装支持 local 脚手架。如果 `devola-init cursor`（或其他非 local 目标）
报告缺少 agent 源码树，请 clone 仓库并 editable 安装：

```bash
git clone https://github.com/YoRHa-Agents/DevolaFlow.git
cd DevolaFlow
pip install -e ".[dev]"
devola-init cursor
```

## 本地脚手架恢复

```bash
devola-init local --mode=core
devola-init local --mode=standard
devola-init local --mode=full
devola-init-doctor
sync-rules
```

`core` 有意跳过规则编译，`standard` 编译但不生成示例，`full` 编译并播种示例。
编译修复命令是 `sync-rules`（在 clone 内也可用 `make compile-rules`）。

全局安装 skill 但不尝试默认插件：

```bash
devola-init cursor --global --no-plugins
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s cursor --global --no-plugins
```

## skill 复制与 host bridge

如果 skill 可见但宿主越界写入没有被阻止，请单独验证可选 bridge。按照
[host bridge 矩阵](https://github.com/YoRHa-Agents/DevolaFlow/blob/main/workflow-system/agent/references/host-bridges.md) 检查宿主专用配置与事件 matcher；Codex
还需信任 hooks。先测试一个事件，再持久设置 `DEVOLAFLOW_HOST_ENFORCE=1`。
不支持的宿主保持 skill-only。

## 工作流症状

- 选错种子：明确表达意图或直接指定种子。
- 单轮完成全部工作：确认 skill 已加载，并请求带可测检查的有界多步骤变更。
- 反复收敛：检查未完成断言与 blocker；有界重试最终会升级。

## Harness 与归档证据

运行 `make test-harness` 验证确定性合同。W-16 结算与 W-19 周期归档汇总是人工发布
政策步骤；没有自动归档 hook。不要把缺少自动归档诊断为运行时故障。
