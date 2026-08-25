---
title: "清单种子目录"
description: "23 个内置清单种子与 change-driven 运行时。"
source_files:
  - "SKILL.md"
auto_generated: true
last_synced: "2026-08-25T10:02:23Z"
source_version: "17.0.0"
---

# 清单种子目录

23 个内置清单种子与 change-driven 运行时。

## 种子选择

DevolaFlow 根据提示词意图匹配清单种子，也可以直接指定种子名。执行前，所选种子会实体化为用户确认的目标和可测清单断言。

| 信号 | 选择的种子 |
|------|------------|
| “紧急”“生产环境故障” | `hotfix` |
| “从零开始”“新项目” | `full-pipeline` |
| “什么”“如何”“哪个”等问题形式 | `research-only` |
| 显式指定种子名 | 直接匹配 |

## 23 个内置清单种子

全部 23 个种子都是 **不可执行的分解知识**。下表中的原语列表只记录来源：它说明领域知识从何而来，但列表顺序与来源 ID 都不规定运行时顺序。

| 种子 | 适用场景 | 原语来源（不可执行） |
|------|----------|----------------------|
| `hotfix` | 紧急缺陷诊断与有界修复 | analyze, implement, test, release |
| `research-only` | 对比方案并给出有证据的建议 | research, analyze, validate |
| `design-only` | 产出带审查证据的架构、API 或 Schema | research, design, review |
| `documentation-only` | 调研、编写并审查文档 | research, implement, review |
| `spike-poc` | 通过有界的一次性原型验证可行性 | research, implement, validate |
| `refactoring` | 在保持行为的前提下重构代码 | analyze, plan, implement, test, review |
| `feature-enhancement` | 扩展现有功能并形成发布证据 | design, plan, implement, review, test, release |
| `full-pipeline` | 构建全新或端到端能力 | design, plan, implement, review, test, refine, gate, release |
| `performance-optimization` | 改善已测量的延迟、内存或吞吐问题 | analyze, design, implement, test, validate |
| `security-audit` | 威胁建模、扫描、修复并验证安全性 | research, analyze, implement, validate |
| `research-design-review-refine` | 迭代调研驱动的设计 | research, design, review, refine |
| `dependency-setup` | 配置环境、依赖或工具链 | research, plan, implement, verify |
| `onboarding` | 帮助贡献者理解并验证仓库环境 | analyze, implement, verify |
| `demo-showcase` | 构建展示级演示 | research, design, implement, review, refine, release |
| `product-verification` | 验证视觉、交互、无障碍与验收质量 | analyze, design, implement, test, verify, review, validate |
| `entropy-cleanup` | 发现并修复过期文档或漂移 | analyze, plan, review, implement |
| `migration` | 在具备回滚准备的前提下升级或迁移系统 | analyze, plan, implement, validate, deploy |
| `skill-optimization` | 分析并改进 Agent Skill | research, analyze, implement, test, refine |
| `self-update` | 调研并集成参考资料更新 | research, plan, implement, test, validate |
| `nines-assisted` | 使用内建 harness 支撑的评估知识 | research, design, plan, implement, review, test, refine, validate, release |
| `repo-init` | 初始化仓库工作区与治理面 | analyze, implement, validate |
| `change-driven` | 实体化有证据的变更生命周期清单 | design, implement, verify, deploy |
| `web-design` | 设计、精修并确定性验证前端 | design, implement, refine, verify |

## 种子如何转化为工作

1. 意图匹配选出一个种子。
2. L0 将分区和断言模板渲染为 `goal.md` 与 `checklist.md`。
3. 用户确认措辞、P0/P1/P2 优先级、人工检查项和 preflight 决策。
4. `change-driven` 运行时以有界轮次执行已确认清单。

建议优先级仅供参考。种子不包含 checkbox、证据、轮次状态或运行时依赖；这些信息只属于实体化后的变更工作区。

## 唯一可执行运行时

`change-driven` 是唯一可执行模板，其生命周期为：

```
propose → preflight → 有界清单轮次 → archive
```

每轮由 L0 取项，L1 Wave 向隔离的 L2 Task 分派任务，Task 报告证据，L0 只勾选核验通过的断言。23 个种子共用这一运行时。

## 示例提示词

- `hotfix`：`"修复登录超时 bug；用户 30 秒后收到 500"`
- `security-audit`：`"按 OWASP Top 10 审计认证模块"`
- `research-design-review-refine`：`"先调研缓存方案，再设计并根据审查精修"`
- `product-verification`：`"从视觉和无障碍要求验证结账流程"`
- `repo-init`：`"为这个仓库初始化 DevolaFlow"`
- `web-design`：`"构建并精修一个非通用的价格页"`
