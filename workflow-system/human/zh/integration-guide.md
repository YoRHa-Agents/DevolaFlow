---
title: "集成指南"
description: "将 DevolaFlow 与 Cursor、Claude Code、Copilot 和 Codex 集成。"
source_files:
  - "SKILL.md"
auto_generated: true
last_synced: "2026-04-12T06:33:24Z"
source_version: "3.9.2"
---

# 集成指南

将 DevolaFlow 与 Cursor、Claude Code、Copilot 和 Codex 集成。

## 支持的平台

| 平台 | 安装方式 | Skill 格式 | 范围 |
|------|---------|-----------|------|
| **Cursor** | `devola-init cursor` | SKILL.md + references/ + examples/ | 项目或全局 |
| **Claude Code** | `devola-init claude` | CLAUDE.md（自包含） | 项目或全局 |
| **Copilot** | `devola-init copilot` | copilot-instructions.md | 仅项目 |
| **Codex** | `devola-init codex` | SKILL.md + openai.yaml | 仅全局 |

## Cursor — 详细设置

### 安装

```bash
# 项目级安装（推荐）
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s cursor

# 或用户全局安装
curl -fsSL $INSTALLER | bash -s cursor --global
```

安装内容：
- `.cursor/skills/devola-flow/SKILL.md` — 主 skill 文件
- `.cursor/skills/devola-flow/references/` — 8 个领域参考文件
- `.cursor/skills/devola-flow/examples/` — 3 个执行追踪示例

### 在 Cursor 中如何工作

DevolaFlow 作为 **Cursor Skill** 加载。当你在 Agent 模式中发送提示词时，Cursor 将 skill 内容加载到代理上下文中。DevolaFlow 的工作流选择启发式规则根据你的意图关键词激活。

### 示例会话：构建功能

1. 在项目中打开 Cursor
2. 切换到 **Agent 模式**（Cmd+L / Ctrl+L）
3. 输入请求：

```
实现用户管理 REST API，包含 CRUD 操作、JWT 认证和基于角色的访问控制
```

4. DevolaFlow 激活，Agent 将：
   - 选择 `full-pipeline` 工作流
   - **设计阶段**：定义 API 端点、数据模型、认证流程
   - **规划阶段**：分解为批次 — 认证模块（批次 1）、CRUD 端点（批次 2）、RBAC（批次 3）
   - **实现阶段**：通过并行任务代理创建源文件和测试
   - **审查阶段**：检查代码质量、安全性、风格
   - **测试阶段**：运行单元 + 集成测试，测量覆盖率
   - **质量门**：验证复合评分 ≥ 85、覆盖率 ≥ 80%
   - **发布阶段**：更新 changelog，准备提交

### Cursor 使用技巧

- **手动附加 skill**：输入 `@devola-flow` 显式引用
- **使用 Plan 模式**：Agent 会生成结构化计划而不执行
- **子代理支持**：Cursor 的 Task 工具自然映射到 DevolaFlow 的 Wave→Task 委托

## Claude Code — 详细设置

### 安装

```bash
# 项目级
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s claude

# 用户全局
curl -fsSL $INSTALLER | bash -s claude --global
```

安装一个自包含的 `CLAUDE.md` 文件。Claude Code 在每个会话开始时自动读取。

### 在 Claude Code 中如何工作

`CLAUDE.md` 始终生效 — Claude Code 自动加载。每个提示词都受益于 DevolaFlow 的工作流结构。

### 示例会话

```bash
claude

> 为数据库查询实现缓存层，支持 TTL 和缓存失效
```

Claude Code 将：
1. 检测 `full-pipeline` 意图
2. 使用 `Task` 子代理进行并行实现
3. 遵循收敛循环确保质量
4. 最后报告任务质量评分

## GitHub Copilot — 详细设置

### 安装

```bash
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s copilot
```

安装内容：
- `.github/copilot-instructions.md` — 根指令
- `.github/instructions/workflow.instructions.md` — 工作流指令

### 在 Copilot 中如何工作

Copilot 为每个请求读取 `copilot-instructions.md`。工作流启发式规则引导 Copilot 的代码建议和聊天回复遵循结构化模式。

## OpenAI Codex — 详细设置

### 安装

```bash
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s codex
```

安装内容：
- `~/.codex/skills/devola-flow/SKILL.md`
- `~/.codex/skills/devola-flow/agents/openai.yaml`

## CI/CD 集成

在 CI 管线中添加 DevolaFlow 验证：

```yaml
# .github/workflows/ci.yml
- name: DevolaFlow Checks
  run: |
    pip install -e '.[dev]'
    python -m pytest tests/ --cov=devolaflow -q
    ruff check src/ tests/ benchmarks/
    validate-template --all
    build-skill --all
```
