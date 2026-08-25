---
title: "集成指南"
description: "将 DevolaFlow 与 Cursor、Claude Code、Copilot 和 Codex 集成。"
source_files:
  - "SKILL.md"
auto_generated: true
last_synced: "2026-08-25T08:45:55Z"
source_version: "17.0.0"
---

# 集成指南

将 DevolaFlow 与 Cursor、Claude Code、Copilot 和 Codex 集成。

## 支持的平台

| 平台 | 安装方式 | Skill 格式 | 范围 |
|------|---------|-----------|------|
| **Cursor** | `devola-init cursor` | SKILL.md + references/ + examples/ | 项目或全局 |
| **Claude Code** | `devola-init claude` | SKILL.md + references/ + examples/ | 项目或全局 |
| **Copilot** | `devola-init copilot` | copilot-instructions.md | 仅项目 |
| **Codex** | `devola-init codex` | SKILL.md + references/ | 仅全局 |

各工具的安装文件清单声明在 `workflow-system/agent/manifest.yaml`
（安装清单的单一事实源）— 上表与其 `install_profiles` 段保持一致。

## Cursor — 详细设置

### 安装

```bash
# 项目级安装（推荐）
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s cursor

# 或用户全局安装
curl -fsSL $INSTALLER | bash -s cursor --global
```

安装内容（依 `workflow-system/agent/manifest.yaml` 的 `cursor` profile）：
- `.cursor/skills/devola-flow/SKILL.md`, 主 skill 文件
- `.cursor/skills/devola-flow/references/`, Tier-2 领域参考文件
- `.cursor/skills/devola-flow/examples/`, Tier-3 执行追踪示例

在 Cursor 中如何工作

DevolaFlow 作为 **Cursor Skill** 加载。当你在 Agent 模式中发送提示词时，Cursor 将 skill 内容加载到 Agent 上下文中。DevolaFlow 的种子选择启发式规则根据你的意图关键词激活。

### 示例会话：构建功能

1. 在项目中打开 Cursor
2. 切换到 **Agent 模式**（Cmd+L / Ctrl+L）
3. 输入请求：

```
实现用户管理 REST API，包含 CRUD 操作、JWT 认证和基于角色的访问控制
```

4. DevolaFlow 激活，Agent 将：
   - 选择 `full-pipeline` 清单种子
   - 从原语来源实体化 API 设计、实现、审查、测试和发布断言
   - 请你确认清单优先级与 preflight 决策
   - 运行有界轮次：L0 Project 取项，L1 Wave 向并行 L2 Task 分派任务
   - 核验证据后才勾选断言
   - 在变更源真相前执行 archive gate

Cursor 使用技巧

**手动附加 skill**：输入`@devola-flow` 显式引用
- **使用 Plan 模式**：Agent 会生成结构化计划而不执行
- **子 Agent 支持**：Cursor 的 Task 工具自然映射到 DevolaFlow 的 L1 Wave → L2 Task 委托

## Claude Code, 详细设置

### 安装

```bash
# 项目级
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s claude

# 用户全局
curl -fsSL $INSTALLER | bash -s claude --global
```

将 skill 包安装到 `.claude/skills/devola-flow/`（项目级）或 `~/.claude/skills/devola-flow/`（`--global`）：`SKILL.md` 加上 `references/` 与 `examples/` 目录树，依 `workflow-system/agent/manifest.yaml` 的 `claude` profile。

在 Claude Code 中如何工作

DevolaFlow 作为 **Claude Code Skill** 加载。它在意图匹配的提示词（实现 / 修复 / 重构 / 调研）上激活，Claude Code 按需读取参考文件，而非每个会话全量加载。

示例会话

```bash
claude

> 为数据库查询实现缓存层，支持 TTL 和缓存失效
```

Claude Code 将：
1. 检测 `full-pipeline` 种子意图
2. 锚定可测清单与已签署的 preflight
3. 使用 L1 Wave 协调和 L2 Task 隔离实现
4. 重复有证据的有界轮次，直到 archive gate 通过或需要升级

## GitHub Copilot, 详细设置

安装

```bash
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s copilot
```

安装内容：
- `.github/copilot-instructions.md`, 完整 SKILL.md 内容作为根指令

在 Copilot 中如何工作

Copilot 为每个请求读取 `copilot-instructions.md`。工作流启发式规则引导 Copilot 的代码建议和聊天回复遵循结构化模式。

## OpenAI Codex, 详细设置

安装

```bash
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s codex
```

安装内容（依 `workflow-system/agent/manifest.yaml` 的 `codex` profile）：
- `~/.codex/skills/devola-flow/SKILL.md`
- `~/.codex/skills/devola-flow/references/`

## CI/CD 集成

在 CI 管线中添加 DevolaFlow 验证：

```yaml
# .github/workflows/ci.yml
- name: DevolaFlow Checks
  run: |
    pip install -e '.[dev]'
    python -m pytest tests/ --cov=devolaflow -q
    ruff check src/ tests/
    validate-template --all
    build-skill --all
```
