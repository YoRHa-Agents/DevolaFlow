---
title: "集成指南"
description: "将 DevolaFlow 接入 AI 工具和 CI/CD 管线。"
source_files: ["SKILL.md"]
auto_generated: true
last_synced: "2026-04-05T00:00:00Z"
source_version: "1.0.0"
---

# 集成指南

## AI 工具集成

### 最快：一条命令

```bash
INSTALLER="https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh"

curl -fsSL $INSTALLER | bash -s cursor            # 项目本地
curl -fsSL $INSTALLER | bash -s cursor --global    # 用户全局 (~/.cursor/)
curl -fsSL $INSTALLER | bash -s claude             # Claude Code（项目本地）
curl -fsSL $INSTALLER | bash -s claude --global    # Claude Code（用户全局 ~/.claude/CLAUDE.md）
curl -fsSL $INSTALLER | bash -s copilot            # Copilot
curl -fsSL $INSTALLER | bash -s update             # 更新已有安装
```

### 备选：pip + devola-init

```bash
pip install git+https://github.com/YoRHa-Agents/DevolaFlow.git
devola-init cursor               # 自动复制 skill 文件到 .cursor/skills/devola-flow/
devola-init claude --global      # 安装到 ~/.claude/CLAUDE.md
```

### 手动：单文件

下载 [MVP-SKILL.md](https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/workflow-system/agent/MVP-SKILL.md) 并复制到：

| 工具 | 项目本地 | 用户全局 |
|------|---------|---------|
| Cursor | `.cursor/skills/devola-flow/SKILL.md` | `~/.cursor/skills/devola-flow/SKILL.md` |
| Claude Code | `./CLAUDE.md` | `~/.claude/CLAUDE.md` |
| Copilot | `.github/copilot-instructions.md` | -- |
| Codex | -- | `~/.codex/skills/devola-flow/SKILL.md` |

## 仓库模式

```bash
detect-repo-mode    # 输出: local / github / gitlab / gitea / bitbucket / generic
```

| 模式 | CI/CD | Release |
|------|-------|---------|
| local | make 本地运行 | 无 |
| github | GitHub Actions | 标签触发 |
| gitlab | GitLab CI | 标签触发 |

## 漂移检测

```bash
make check-drift       # 检查人类文档是否与 Agent 源同步
make sync-human-docs   # 从 Agent 源重新生成
```
