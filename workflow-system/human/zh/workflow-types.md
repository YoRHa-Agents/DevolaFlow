---
title: "工作流类型目录"
description: "22 种内置工作流类型及选择指南。"
source_files:
  - "SKILL.md"
auto_generated: true
last_synced: "2026-05-08T17:06:37Z"
source_version: "11.3.0"
---

# 工作流类型目录

22 种内置工作流类型及选择指南。

## 工作流选择

DevolaFlow 根据你的提示词自动选择合适的工作流。你也可以显式指定。

**选择策略：**
- 紧急信号（"紧急"、"生产环境故障"）→ `hotfix`"从零开始" / "新项目" →`full-pipeline`问题形式（"什么"、"如何"、"哪个"）→`research-only`显式指定类型 → 直接匹配（最高优先级）

## 全部 22 种内置工作流类型

发现类工作流

`research-only`
**适用场景**：调研先例、比较方案、评估选项。
**阶段**：research → compare → report
**示例**：`"调研最适合我们 Python 项目的 ORM — 对比 SQLAlchemy、Peewee 和 Tortoise"`

`onboarding`
**适用场景**：新成员加入、了解陌生代码库、恢复休眠项目。
**阶段**：analyze → document → setup → verify
**示例**：`"我是这个项目的新人 — 帮我了解代码库并设置开发环境"`

优化类工作流

`skill-optimization`
**适用场景**：优化 Agent 技能、基准测试上下文密度、改进信息路由。
**阶段**：survey → profile → optimize → benchmark → iterate → document
**示例**：`"优化 DevolaFlow 技能 — 基准测试上下文密度并减少噪声"`

塑形类工作流

`design-only`
**适用场景**：架构决策、API 设计、Schema 设计。
**阶段**：research → design → review
**示例**：`"设计多租户通知服务的 API"`

`RDRR`（调研-设计-审查-精炼）
**适用场景**：需要调研支撑的迭代设计。
**阶段**：research → design → review → refine（循环）
**示例**：`"设计缓存架构 — 先调研选项，然后迭代设计"`

### 构建类工作流

`hotfix`
**适用场景**：生产 bug、紧急修复、安全补丁。
**阶段**：triage → fix → test → release
**示例**：`"修复登录超时 bug — 用户 30 秒后报 500 错误"`

`refactoring`
**适用场景**：技术债务、代码重构、简化。
**阶段**：scope → plan → implement → test → review
**示例**：`"将支付模块重构为策略模式"`

`migration`
**适用场景**：升级框架、系统迁移、数据库迁移。
**阶段**：assess → plan → implement → validate → cutover
**示例**：`"从 Express.js 迁移到 Fastify — 保留所有现有端点"`

`performance-optimization`
**适用场景**：应用慢、延迟高、内存问题、构建时间优化。
**阶段**：profile → design → optimize → benchmark → validate
**示例**：`"我们的 API 响应时间超过 2 秒 — 分析并优化热路径"`

`dependency-setup`
**适用场景**：搭建开发环境、添加依赖、配置工具链。
**阶段**：research → plan → configure → verify
**示例**：`"为我们的 Python API 搭建 Docker 开发环境，支持热重载"`

`feature-enhancement`
**适用场景**：扩展现有功能。
**阶段**：scope → design → plan → implement → review → test → release
**示例**：`"为设置页面添加暗色模式"`

`full-pipeline`
**适用场景**：全新功能、新项目、需要完整生命周期的任务。
**阶段**：design → plan → implement → review → test → refine → gate → release
**示例**：`"构建用户认证系统，支持 OAuth2、JWT 和角色权限"`

验证类工作流

`security-audit`
**适用场景**：漏洞扫描、合规检查、CVE 修复。
**阶段**：threat-model → scan → analyze → remediate → verify
**示例**：`"对认证模块进行安全审计 — 检查 OWASP Top 10"`

交付类工作流

`documentation`
**适用场景**：编写或更新文档、README、API 参考。
**阶段**：survey → author → review
**示例**：`"为支付模块编写完整的 API 文档"`

`demo-showcase`
**适用场景**：为利益相关者构建演示、交互式展示、会议演讲。
**阶段**：research → storyboard → build-demo → demo-review → polish → package
**示例**：`"构建一个交互式演示展示我们的新仪表板 — 要展示级别的质量"`

### 复合工作流

`spike-poc`
**适用场景**：可行性测试、原型开发、评估新技术。
**阶段**：research → prototype → evaluate
**示例**：`"使用 CRDT 原型实现实时协作 — 在我们的规模下可行吗？"`

`self-update`
**适用场景**：跟踪外部参考依赖并集成改进。
**阶段**：check-refs → research-updates → decompose → integrate → test → evaluate
**示例**：`"update refs"`、`"self-update"`、`"check references"`

#### `change-driven`
**适用场景**：以结构化 `.local/.agent/active/<id>/` 工件（goal、acceptance、spec、tasks、STATUS、owned_files）管理在制品变更；成功后归档并自动生成 REPORT.md，向 source-of-truth 规范提议增量合并。
**阶段**：propose → apply → verify → archive（mode: lite \| full）
**示例**：`"propose change to add dark mode"`、`"apply v8.3.0-pv09"`、`"archive add-auth-bug"`

## 快速参考表

| 类型 | 触发关键词 | 阶段数 | 门控配置 |
|------|-----------|--------|---------|
| `research-only` | 调研, 比较, 评估 | 3 | — |
| `design-only` | 设计, 架构, API | 3 | standard |
| `hotfix` | 修复, bug, 崩溃 | 4 | relaxed |
| `refactoring` | 重构, 清理, 技术债 | 5 | standard |
| `migration` | 迁移, 升级, 转换 | 5 | standard |
| `spike-poc` | 原型, 实验, PoC | 3 | — |
| `documentation` | 写文档, README | 3 | relaxed |
| `security-audit` | 安全, 审计, CVE | 5 | strict |
| `feature-enhancement` | 添加, 扩展, 增强 | 7 | standard |
| `full-pipeline` | 从零开始, 新项目 | 8 | standard |
| `RDRR` | 带调研的设计, ADR | 4 (循环) | standard |
| `demo-showcase` | 演示, 展示, 演讲 | 6 | relaxed |
| `performance-optimization` | 慢, 优化, 基准测试 | 5 | standard |
| `dependency-setup` | 搭建, 安装, 配置环境 | 4 | relaxed |
| `onboarding` | 新加入项目, 入门 | 4 |, |
| `skill-optimization` | 优化技能, 基准测试上下文 | 6 | convergence |
| `self-update` | 更新引用, 自更新, 检查参考 | 6 | standard |
| `change-driven` | 变更, 提议, 应用, 归档, 生命周期, OpenSpec | 4 | convergence |
