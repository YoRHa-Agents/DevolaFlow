---
title: "常见问题"
description: "关于工作流系统的常见问题解答。"
source_files:
  - "SKILL.md"
auto_generated: true
last_synced: "2026-06-11T19:11:09Z"
source_version: "14.2.2"
---

# 常见问题

关于工作流系统的常见问题解答。

## 常规问题

什么是 DevolaFlow？

一个用于 AI 辅助软件开发的可组合工作流元框架。它通过声明式 YAML 模板定义多阶段交付流水线，由 4 层代理层级和质量门机制进行编排。可以把它理解为一个你的 AI 编程工具会自动遵循的项目管理框架。

支持哪些 AI 工具？

**Cursor** — 作为 Cursor Skill 加载, and **Claude Code**, 作为`CLAUDE.md` 加载（每个会话自动生效）
- **GitHub Copilot**, 作为 `copilot-instructions.md` 加载
- **OpenAI Codex**, 作为 Codex Skill 加载

我需要学 YAML 才能使用 DevolaFlow 吗？

不需要。DevolaFlow 根据你的自然语言提示词自动激活。说 "修复登录 bug" 它就选择 hotfix 工作流，说 "从零构建新功能" 它就选择 full-pipeline。只有创建自定义工作流模板时才需要 YAML。

DevolaFlow 和直接提示 AI 工具有什么区别？

没有 DevolaFlow 时，AI 工具在单轮中处理整个请求，经常丢失上下文或混淆关注点（一边设计一边编码一边测试）。有了 DevolaFlow，工作被分解为隔离的阶段并带有质量检查点，代理先设计，再规划，再实现，再审查, 每个边界都有质量门确保质量。

## 工作流

Agent 如何选择工作流？

DevolaFlow 使用提示词的 **意图匹配**：
- "修复 bug" / "崩溃" → `hotfix`"从零开始" / "新项目" →`full-pipeline`"调研" / "对比" →`research-only`"重构" / "清理" →`refactoring`

你也可以显式指定："使用 migration 工作流从 React 17 升级到 18。"

v3.0.0的 5 种新工作流是什么？

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
- **architecture.mdc**（A-1 至 A-7）：4 层体系、缓存布局、令牌预算
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

如何更新？

```bash
# pip
pip install --upgrade git+https://github.com/YoRHa-Agents/DevolaFlow.git

# 安装器
curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh | bash -s update
```
