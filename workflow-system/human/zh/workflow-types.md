---
title: "清单种子目录"
description: "从注册表派生的清单种子与唯一的 change-driven 运行时。"
source_files:
  - "SKILL.md"
auto_generated: true
last_synced: "2026-08-28T04:45:44Z"
source_version: "19.0.0"
---

# 清单种子目录

从注册表派生的清单种子与唯一的 change-driven 运行时。

## 注册表目录

下表从 `workflow-system/agent/templates/registry.yaml` 生成；本指南不单独维护成员列表。

| 种子 ID | 类别 | 本地化描述 | 意图标签 |
|---|---|---|---|
| `hotfix` | `build` | 快速完成缺陷分诊、最小修复、聚焦测试与快速发布。 | `bug`, `fix`, `hotfix`, `patch`, `urgent` |
| `research-only` | `discover` | 开展纯研究与比较，并产出经验证的报告。 | `research`, `compare`, `evaluate` |
| `design-only` | `shape` | 基于研究完成设计与架构评审。 | `design`, `research`, `review`, `architecture` |
| `documentation-only` | `deliver` | 调研、编写并评审文档。 | `documentation`, `docs`, `write`, `review` |
| `spike-poc` | `discover` | 构建有边界的可丢弃原型，并给出明确评估结论。 | `spike`, `poc`, `prototype`, `experiment` |
| `refactoring` | `build` | 以证据为依据重构技术债务。 | `refactor`, `tech-debt`, `improve`, `restructure` |
| `feature-enhancement` | `composite` | 通过设计、实现与发布证据扩展现有功能。 | `feature`, `enhance`, `extend`, `modify` |
| `full-pipeline` | `composite` | 为绿地项目或端到端交付提供分解知识。 | `full`, `pipeline`, `feature`, `implementation`, `release` |
| `performance-optimization` | `build` | 分析性能、实施优化、运行基准并验证可测结果。 | `performance`, `optimize`, `profiling`, `benchmark`, `speed`, `latency` |
| `security-audit` | `composite` | 执行威胁建模、扫描、分析、修复与验证。 | `security`, `audit`, `vulnerability`, `CVE`, `scan` |
| `research-design-review-refine` | `composite` | 迭代完成研究、设计、评审、改进与知识缺口闭环。 | `research`, `design`, `review`, `refine`, `iterate` |
| `dependency-setup` | `build` | 配置环境与工具，并进行有界验证。 | `setup`, `install`, `dependency`, `environment`, `tooling`, `configuration` |
| `onboarding` | `discover` | 通过分析、文档、配置与验证完成贡献者入门。 | `onboarding`, `setup`, `getting-started`, `contributor`, `codebase` |
| `demo-showcase` | `composite` | 以视觉质量证据支撑演示与展示分解。 | `demo`, `showcase`, `presentation`, `prototype`, `ui`, `visual`, `pitch` |
| `product-verification` | `composite` | 从视觉、交互、无障碍与验收维度验证用户体验。 | `verify`, `visual`, `acceptance`, `interaction`, `accessibility`, `uat`, `e2e`, `product`, `quality` |
| `entropy-cleanup` | `control` | 清理过期文档与漂移。 | `entropy`, `gc`, `cleanup`, `freshness`, `drift`, `maintenance`, `meta`, `documentation` |
| `local-archive` | `control` | 独立任务归档工作流：先报告并明确批准，在严格安全与来源约束下执行有界的非删除移动。 | `local-archive`, `task-archive`, `archive`, `tasks`, `clustering`, `mapping`, `index`, `report-only` |
| `harness-construction` | `composite` | 构建 harness 基建（观测/评测/探针/基线/信号/闭环覆盖），以机器化缺口分析打底并在归档时评审能力增量。 | `harness`, `evaluation-infrastructure`, `observability`, `telemetry`, `coverage`, `gap-analysis`, `baseline` |
| `pathfinder` | `control` | 以只读方式前瞻侦察基础设施与 harness 缺口，并在后续轮次前完成有界交接。 | `pathfinder`, `path-find`, `look-ahead`, `infrastructure`, `harness`, `gap-analysis`, `reconnaissance` |
| `migration` | `build` | 系统化迁移，并验证切换与回滚准备。 | `migrate`, `upgrade`, `transition`, `port` |
| `skill-optimization` | `composite` | 分析、优化、验证并记录 Agent skill。 | `skill`, `optimize`, `benchmark`, `context`, `compress`, `iterate`, `density` |
| `self-update` | `control` | 研究、集成、测试并评估引用依赖更新。 | `self-update`, `update`, `upgrade`, `refs`, `validate`, `meta` |
| `nines-assisted` | `composite` | 基于内置 harness 的历史研究与迭代分解知识。 | `harness`, `evaluation`, `analysis`, `pipeline`, `self-eval`, `review`, `assisted`, `full` |
| `repo-init` | `discover` | 初始化仓库工作区与治理。 | `init`, `scaffold`, `bootstrap`, `repo`, `workspace`, `rules` |
| `change-driven` | `composite` | 唯一可执行的清单轮次生命周期运行时。 | `change`, `propose`, `preflight`, `round`, `archive`, `lifecycle`, `agent-workspace`, `opsx` |
| `web-design` | `composite` | 前端设计、实现、改进与确定性验证知识。 | `web-design`, `frontend`, `landing-page`, `ui`, `design`, `polish`, `impeccable`, `ui-pro` |

## 选择与执行

意图匹配选择分解知识，随后 L0 将其实体化为可测的 goal/checklist/preflight 合同。
优先级、已满足依赖、文件所有权与轮次状态决定执行顺序；`source_stages` 不决定。
所有种子都通过唯一的 `change-driven` 运行时执行。
