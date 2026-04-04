---
title: "集成指南"
description: "将 DevolaFlow 与现有工具和 CI/CD 管线集成。"
source_files: ["SKILL.md"]
auto_generated: true
last_synced: "2026-04-04T00:00:00Z"
source_version: "1.0.0"
---

# 集成指南

## AI 工具集成

### 快速方法：单文件

把 `workflow-system/agent/MVP-SKILL.md` 复制到对应工具的指令文件位置即可。

### 完整方法：构建管线

```bash
make build-skill    # 生成 dist/cursor/, dist/codex/, dist/claude/, dist/copilot/
```

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
