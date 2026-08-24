---
title: "常见问题"
description: "关于工作流系统的常见问题解答。"
source_files:
  - "SKILL.md"
auto_generated: true
last_synced: "2026-08-24T18:04:48Z"
source_version: "15.2.0"
---

# 常见问题

关于工作流系统的常见问题解答。

## 常规问题

什么是 DevolaFlow？

一个用于 AI 辅助软件开发的可组合工作流元框架。它把 23 个领域清单种子之一转为用户确认的执行合同，再通过 Project → Wave → Task 三层架构和 `change-driven` 清单轮次运行时执行。

支持哪些 AI 工具？

**Cursor** — 作为 Cursor Skill 加载, and **Claude Code**, 作为 Claude Code Skill 加载（`.claude/skills/devola-flow/SKILL.md`）
- **GitHub Copilot**, 作为 `copilot-instructions.md` 加载
- **OpenAI Codex**, 作为 Codex Skill 加载

我需要学 YAML 才能使用 DevolaFlow 吗？

不需要。DevolaFlow 根据自然语言自动激活。说“修复登录 bug”会选择 `hotfix` 种子，说“从零构建新功能”会选择 `full-pipeline`。只有编写自定义清单种子时才需要 YAML。

DevolaFlow 和直接提示 AI 工具有什么区别？

没有 DevolaFlow 时，AI 工具可能单轮处理整个请求，混淆设计、实现与验证。DevolaFlow 会与你锚定可测清单断言，每轮只执行一个有界集合，并且仅在证据核验后勾选。

## 工作流

Agent 如何选择清单种子？

DevolaFlow 使用提示词的 **意图匹配**：
- "修复 bug" / "崩溃" → `hotfix`"从零开始" / "新项目" →`full-pipeline`"调研" / "对比" →`research-only`"重构" / "清理" →`refactoring`

你也可以显式指定：“使用 migration 种子从 React 17 升级到 18。”

哪些种子来自 v3.0.0 的五个工作流新增项？

从历史来源看，v3.0.0 曾把以下能力作为可执行工作流类型引入。现在它们以不可执行清单种子保留领域知识：

- **demo-showcase**：构建展示级演示和交互式展示
- **performance-optimization**：基于分析的性能优化，包含前后对比基准测试
- **dependency-setup**：配置开发环境，安装依赖，设置工具链
- **onboarding**：帮助新贡献者了解代码库并设置环境
- **skill-optimization**：优化 Agent 技能，包括上下文分析、基准测试和迭代改进

## 质量与门控

### 什么是仓库规则？

`.rules/` 中的 62 条规则，分为 5 层，编译输出到 `AGENTS.md` 与
`.cursor/rules/repo-governance.mdc`（旧的 SF-/CP-/CO- 规则文件自 v14.2.1 起为弃用指针存根）：
- **soul.mdc**（S-1 至 S-10）：不可违背的红线, 测试覆盖率底线（≥80%）、无幽灵功能
- **architecture.mdc**（A-1 至 A-7）：三层体系、缓存布局、令牌预算
- **conventions.mdc**（C-1 至 C-9，C-8 已退役）：SKILL.md 格式约束、版本一致性
- **workflow.mdc**（W-1 至 W-24）：迭代规划、基准测试、版本升级协议
- **style.mdc**（ST-1 至 ST-13）：文档同步、Web 演示、双语完整性

什么是 EvoBench？

内置的上下文密度基准测试套件。运行：`python -m benchmarks.devolaflow_context.runner --scenario all`

质量门失败时会发生什么？

门控触发 **收敛循环**：审查发现 → 修复问题 → 重新测试 → 复查门控。最多 3 轮。如果仍然失败，升级到人工并附上差异报告。

## 更新与版本

如何检查更新？

在 AI 工具中输入 `"update devola"`, 或在终端运行 `devola-version`。
要一次性审计所有已安装副本，运行 `devola-init-doctor --skills`：它会扫描
全部已知安装位置，并将每个安装标记为 `current` / `stale` / `unknown-version`。

如何更新？

```bash
# pip
pip install --upgrade git+https://github.com/YoRHa-Agents/DevolaFlow.git

# 安装器（已是最新版本的安装会跳过；--force 强制重新下载）
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s update
```

如何卸载？

```bash
# 先预览将删除的内容，再实际删除
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s uninstall --dry-run
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s uninstall
```
