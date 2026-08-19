# 本地开发工作区结构最佳实践研究报告

> 研究日期：2026-04-20
> 研究范围：AI 辅助开发中的本地 gitignored 工作区目录设计模式

---

## 一、现有惯例调研

### 1.1 `.local` 后缀/目录的行业惯例

#### 环境变量层叠模式

最早被广泛采用的 `.local` 模式来自前端生态：

| 文件 | 作用 | 是否提交 |
|------|------|----------|
| `.env` | 共享默认值 | ✅ |
| `.env.local` | 本地覆盖 | ❌ |
| `.env.development.local` | 开发环境覆盖 | ❌ |
| `.env.production.local` | 生产环境覆盖 | ❌ |

该模式被 Next.js、Vite、Create React App 等框架推广，核心理念是 **团队共享 + 个人覆盖** 分层。

#### Docker Compose 层叠模式

```
docker-compose.yml          # 团队共享（提交）
docker-compose.override.yml # 本地覆盖（gitignored）
```

#### VS Code 工作区 `.local` 提案

微软 VS Code 在 Issue #282806 中提出了 `.code-workspace.local` 文件，用于个人工作区设置覆盖，遵循相同的「共享 + 本地」分层原则。

#### Andrew Nesbitt 的 `.gitlocal` 提案（2026年3月）

这是一个新兴标准提案，核心思想是 **让工具作者主动声明哪些文件不应被提交**，而非依赖仓库维护者事后配置 `.gitignore`。支持三种标记方式：

1. **目录标记文件**：在工具配置目录中放置空的 `.gitlocal` 文件（如 `.sometool/.gitlocal`），自动忽略整个目录
2. **文件扩展名**：使用 `.gitlocal` 扩展名标记单个文件（如 `credentials.gitlocal`）
3. **注释头部**：在文本文件首行添加 `# gitlocal` 注释

实现方式为 pre-commit hook，已有 PoC 实现（github.com/andrew/gitlocal）。

### 1.2 Monorepo 中的本地工作区

在 pnpm Workspaces + Turborepo 等 monorepo 方案中，`.local` 模式帮助实现：
- 共享配置（提交到 Git）与个人偏好（`.local` 变体，gitignored）的清晰分离
- 不需要 Git workaround 的本地覆盖机制
- 跨包的一致本地开发体验

---

## 二、AI 工具工作区模式调研

### 2.1 各主流 AI 编码工具的目录结构对比

| 工具 | 项目级目录 | 全局目录 | 指令文件 | 本地/个人文件 | 附加状态 |
|------|-----------|---------|---------|-------------|---------|
| **Cursor** | `.cursor/rules/*.mdc` | `~/.cursor/rules/` | `.cursor/rules/` | — | Skills, settings |
| **Claude Code** | `.claude/` | `~/.claude/` | `CLAUDE.md` | `CLAUDE.local.md` | `~/.claude/projects/`, Memory, sessions |
| **Codex** | `.codex/` | `~/.codex/` | `AGENTS.md` | `AGENTS.override.md` | context/, tools/, prompts/ |
| **Windsurf** | `.windsurf/rules/` | `~/.codeium/windsurf/` | `.windsurfrules` | — | Memories (自动生成) |
| **Copilot** | `.github/copilot-instructions.md` | `~/.copilot/` | `.github/instructions/**/*.instructions.md` | — | — |
| **Aider** | `.aider/` | `~/.aider/` | `.aider.conf.yml` | — | `sessions/`, `chat.history.md` |

### 2.2 关键发现

#### 分层优先级模型

所有工具都采用了类似的分层优先级模型（从高到低）：

```
项目级配置 > 全局配置
工具特定规则 > 通用规则
本地覆盖 > 团队共享
```

Claude Code 的优先级最为精细，提供了 6 层：

| 优先级 | 位置 | 范围 |
|--------|------|------|
| 1 | 托管策略 (Managed policy) | 组织级 |
| 2 | 项目 `CLAUDE.md` | 项目（团队共享） |
| 3 | `.claude/rules/` | 项目（团队共享） |
| 4 | 用户 `~/.claude/CLAUDE.md` | 用户级（跨项目） |
| 5 | `CLAUDE.local.md` | 个人（本项目） |
| 6 | Auto memory | 自动（本项目+本用户） |

#### 通用标准 AGENTS.md 的崛起

2025年8月由 OpenAI 发起，2025年12月移交 Linux 基金会 Agentic AI Foundation（AWS、Anthropic、Google、Microsoft、OpenAI 共同支持），已被 60,000+ GitHub 仓库采用。

Princeton 研究表明：AGENTS.md 可实现 28.6% 中位运行时间缩减和 16.6% token 节约，且人工编写的显著优于自动生成的。

#### 记忆 vs 规则的区分

Windsurf 明确区分了两个概念：
- **Rules（规则）**：显式编写、版本控制、团队共享
- **Memories（记忆）**：自动生成、本地存储、不提交

Claude Code 也有类似区分：
- **CLAUDE.md**：用户编写的指令
- **Auto Memory**：Claude 自己写的笔记

### 2.3 Claude Code 的 `~/.claude/` 详细结构

```
~/.claude/
├── projects/           # 按项目的会话数据和持久记忆（MEMORY.md）
├── debug/              # 按 UUID 的完整会话调试日志
├── file-history/       # 按会话的文件编辑快照
├── settings.json       # 全局用户设置
├── cache/              # 应用管理缓存
├── downloads/          # 下载文件
├── history.jsonl       # 会话历史
└── skills/             # 用户级技能
```

### 2.4 Codex 的 `.codex/` 结构

```
~/.codex/               # 全局
├── config.toml         # 全局配置
├── context/            # 可重用上下文笔记
├── tools/              # 辅助脚本和自定义命令
├── mcp/                # MCP 服务器定义
└── prompts/            # 自定义提示

.codex/                 # 项目级（与全局合并/覆盖）
├── config.toml
├── context/
├── tools/
├── mcp/
└── prompts/
```

---

## 三、结构化本地工作区设计案例

### 3.1 DevolaFlow 的 `.local/` 现状

DevolaFlow 项目自身已使用 `.local/` 目录存放本地开发制品，通过 `.gitignore` 排除。当前结构：

```
.local/
├── benchmarks/           # 基准测试脚本和报告
│   ├── variants/         # 变体对比数据
│   ├── 选型决策报告.md
│   └── *.py              # 测试脚本
├── designs/              # 设计文档
├── feedbacks/            # 迭代反馈记录
│   ├── feedback_for_v7.3.0.md
│   ├── feedback_for_v6.3.x.md
│   ├── feedback_from_NineS/
│   └── from_evobench/
├── nines-analysis/       # NineS 工具分析结果
│   ├── self-eval/
│   └── src-analysis/
├── nines-review/         # NineS 审查结果
│   ├── full-analysis/
│   ├── gate-analysis/
│   └── benchmark/
├── prototypes/           # 原型代码
├── research/             # 调研制品（最丰富的子目录）
│   ├── adr/              # 架构决策记录
│   ├── v6.0.0/ ~ v7.2.0_refs/  # 按版本组织的研究
│   ├── retrospective_v7.0_to_v7.1.md
│   └── *.md / *.json     # 研究报告和数据
├── sandbox/              # 实验性代码沙箱
│   └── v7.2.0/V01~V07   # 按版本和变体组织
└── tasks/                # 任务管理
    └── task_update_for_5.5.0/
```

**特点**：
- 以版本号为组织维度（v6.0.0、v7.2.0 等）
- 反馈来源多元化（人工、NineS、EvoBench）
- 研究→设计→原型→沙箱的完整流水线
- 缺少 `index.md` 索引文件

### 3.2 Claude Agent Workspace Model（Daniel Rosehill）

```
workspace/
├── CLAUDE.md             # 轻量入口（stub 到详细文件）
├── context/              # 用户提供的上下文
│   ├── project.md        # 项目描述
│   ├── role.md           # 角色定义
│   ├── constraints.md    # 约束条件
│   └── for-agent/        # 面向 Agent 的详细指令
│       ├── environment.md
│       └── workflows.md
├── work-log/             # Agent 操作的日志记录
├── planning/             # 工作区规划
├── user-docs/            # 用户文档
└── .claude/commands/     # 斜杠命令
```

**设计哲学**：
- 仓库即 Agent 的持久记忆
- 机器可读性优先于人类便利性
- Convention over Configuration
- 用户提供的上下文与 Agent 生成的操作严格分离
- 三阶段生命周期：Scaffold → Personalize → Success

### 3.3 Ralph（fitchmultz）— 本地优先任务编排

```
.ralph/
├── queue.jsonc           # 结构化任务队列
├── done.jsonc            # 已完成任务
├── config.jsonc          # 配置
└── merge-queue.jsonl     # 并行合并追踪（append-only + 文件锁）
```

**设计哲学**：
- 纯 JSONC 文件，人类和机器都可读
- 项目隔离，防止跨项目污染
- 显式任务生命周期和依赖链接
- 支持多 Runner（Codex, Claude, Cursor, Gemini 等）
- 明确声明的 Non-goal：不做 SaaS 编排、不隐藏状态

### 3.4 Codex Workspace（Richard George Davis）

```
Codex Workspace/
├── docs/                 # 规范文档
├── repos/                # 独立仓库集合
│   └── workspace-hub/    # 工作区管理应用
├── tools/                # 辅助工具
├── cache/                # 生成的摘要和缓存（不追踪）
├── shared/               # 工作区元数据
│   ├── repo-index.json   # 仓库索引
│   └── standards.md      # 标准规范
└── workspace.code-workspace
```

**三层上下文模型**：
1. 短摘要优先使用
2. 更深层仓库细节按需读取
3. 持久仓库知识与操作者记忆、密钥、机器特定笔记分离

### 3.5 Local Brain（Sander Moon）

```
~/brain/
├── projects/             # 项目管理
├── tasks/                # 任务追踪
├── notes/                # 笔记
├── references/           # 参考资料
└── journal/              # 日志
```

纯 Markdown 项目管理，提供 CLI、TUI 和 MCP 服务器集成。

### 3.6 dev-agent-work（farra）

使用 Org-mode 格式进行会话追踪：

```
sessions/
└── YYYY-MM-DD-session-name.org
    ├── Objective（目标声明，2-3句）
    ├── Context（背景信息）
    ├── Tasks（复选框任务追踪）
    ├── Work Log（时间戳工作日志）
    └── Lessons Learned（经验教训）
```

### 3.7 Moltbot — Workspace Memory v2

```
~/clawd/
├── memory.md             # 核心记忆
├── memory/YYYY-MM-DD.md  # 按天日志
└── bank/                 # 策划的事实、实体、观点
```

**记忆架构**：叙事性日志 + 派生索引的组合，核心上下文（角色 + 关键事实）始终可用，其余按需工具检索。

---

## 四、工作流编排工具的本地状态管理

### 4.1 持久执行模式

| 工具 | 状态管理方式 | 崩溃恢复 | 人类审批 |
|------|------------|---------|---------|
| **DBOS** | 持久执行引擎 | 自动恢复 | 原生支持 |
| **Microsoft Agent Framework** | 图工作流 + 检查点 | 时间旅行调试 | 原生支持 |
| **Conductor** | 分布式工作流引擎 | 自动重试 + 指数退避 | ✅ |
| **Agentspan** | 进程外状态持久化 | 精确恢复点 | 无限等待门 |
| **Orra** | 持久执行 + 状态回退 | 预验证执行计划 | 审计日志 |

### 4.2 共同趋势

1. **状态外部化**：执行状态不依赖进程内存，而是持久化到外部存储
2. **崩溃恢复即默认**：不是可选特性，而是基础架构要求
3. **人类在环 (Human-in-the-loop)**：审批门、无限等待、状态保持
4. **全量执行历史**：可审计、可重放、可分析

### 4.3 多 Agent 协作工作区（2026 趋势）

CODITECT Development Studio v2.0 和 KaizenAI 等工具展示了新趋势：
- 多个 AI Agent（Claude, Gemini, Codex, Kimi）在统一持久工作区中协作
- 8 小时长会话 + GCS FUSE 存储
- SQLite + JSONL 审计尾随
- Agent 间通过消息总线共享上下文和文件锁
- 工作区内协调替代外部路由

---

## 五、关键设计原则提炼

基于以上调研，提炼出以下核心设计原则：

### 原则 1：分层覆盖（Layered Override）

```
组织策略 → 项目共享 → 用户全局 → 项目本地 → 自动记忆
```

每一层都可以覆盖上一层，确保团队一致性和个人灵活性共存。这是所有主流 AI 工具（Cursor、Claude Code、Codex、Windsurf、Copilot）的共同模式。

### 原则 2：提交/本地二分法（Committed vs Local Dichotomy）

| 维度 | 提交到 Git | 本地保留 |
|------|-----------|---------|
| 团队规则 | ✅ | |
| 个人偏好 | | ✅ |
| 项目配置 | ✅ | |
| 机器特定状态 | | ✅ |
| 密钥/凭证 | | ✅ |
| 研究制品 | | ✅ |
| 会话历史 | | ✅ |
| 迭代反馈 | | ✅（可选择性提取）|

### 原则 3：文件系统即真相源（Filesystem as Source of Truth）

- 纯文本格式（Markdown、YAML、JSONC）优先
- 避免数据库或二进制状态
- 人类和机器都可读
- 支持 Git diff 和版本控制（即使不提交，本地也可用 Git 追踪）

### 原则 4：Convention over Configuration

- 目录名即语义（`research/`、`feedbacks/`、`tasks/`）
- 不需要额外的元数据文件来解释目录用途
- 但 `index.md` 索引可提供导航和概览

### 原则 5：按需创建，渐进丰富（Progressive Enrichment）

- 不要一次创建所有目录
- 目录按需开通（需要研究时创建 `research/`，需要沙箱时创建 `sandbox/`）
- 避免空目录占位

### 原则 6：时间/版本维度组织（Temporal Organization）

DevolaFlow 的实践和 dev-agent-work 的模式都表明，按时间或版本组织本地制品是有效的：

```
research/
├── v6.0.0/       # 版本维度
├── v7.2.0_refs/
└── retrospective_v7.0_to_v7.1.md  # 跨版本回顾
```

```
sessions/
└── 2026-04-20-feature-x.org  # 时间维度
```

### 原则 7：上下文隔离和分级加载（Context Isolation）

- 核心摘要始终可用（< 500 行）
- 详细内容按需加载
- Agent 不应一次读取整个工作区
- DevolaFlow 的 token 预算模型（L0~L3）是此原则的系统化实现

### 原则 8：工具声明自身的忽略需求

`.gitlocal` 提案的核心思想：**工具应该能声明自己的文件不应被提交**，而不是依赖仓库维护者猜测。这对 AI 工具生态特别重要——每个工具都有自己的状态目录。

---

## 六、对比矩阵

### 6.1 本地工作区目录方案对比

| 维度 | DevolaFlow `.local/` | Claude Workspace Model | Ralph `.ralph/` | Codex Workspace | Aider `.aider/` |
|------|---------------------|----------------------|----------------|----------------|----------------|
| **组织粒度** | 按功能+版本 | 按角色+流程 | 按任务状态 | 按仓库+缓存 | 按会话 |
| **索引机制** | 无（缺失） | CLAUDE.md stub | queue.jsonc | repo-index.json | history.md |
| **支持迭代** | ✅ 强（feedbacks, research, sandbox） | ⚠️ 弱（work-log） | ✅（done.jsonc） | ⚠️ 弱 | ❌ |
| **多工具兼容** | ⚠️ 仅 Cursor/Claude | ❌ Claude only | ✅ 多 Runner | ❌ Codex only | ❌ Aider only |
| **研究制品** | ✅ 丰富 | ❌ | ❌ | ⚠️ cache/ | ❌ |
| **人类可读性** | ✅ Markdown | ✅ Markdown | ✅ JSONC | ⚠️ JSON | ✅ Markdown |
| **自动维护** | ❌ 手动 | ⚠️ 部分（commands） | ✅ CLI管理 | ⚠️ 部分 | ✅ 自动 |
| **跨项目复用** | ❌ | ⚠️ 模板 | ❌ | ✅ workspace-hub | ❌ |

### 6.2 AI 工具指令文件对比

| 维度 | AGENTS.md | CLAUDE.md | .cursor/rules/ | .windsurfrules | .codex/ |
|------|-----------|-----------|---------------|---------------|---------|
| **跨工具兼容** | ✅ 60K+ 仓库，15+ 工具 | ❌ Claude only | ❌ Cursor only | ❌ Windsurf only | ⚠️ 仅 AGENTS.md 部分 |
| **模块化** | ⚠️ 按目录 | ⚠️ rules/ 子目录 | ✅ 多 .mdc 文件 | ✅ rules/ 子目录 | ⚠️ context/ |
| **条件应用** | ❌ | ❌ | ✅ glob + alwaysApply | ❌ | ❌ |
| **本地覆盖** | AGENTS.override.md | CLAUDE.local.md | — | — | config.toml merge |
| **Token 预算** | 无限制 | 200K 窗口 | 无明确限制 | 6K token 上限 | 无明确限制 |
| **治理机构** | Linux Foundation Agentic AI | Anthropic | Cursor/Anysphere | Codeium | OpenAI |

---

## 七、推荐模式

### 7.1 推荐的 `.local/` 目录结构

基于上述调研，推荐以下结构作为 AI 辅助开发的本地工作区标准：

```
.local/
├── index.md                    # 工作区索引和概览（必选）
│
├── feedbacks/                  # 迭代反馈记录（按需）
│   ├── feedback_for_{version}.md
│   └── from_{source}/          # 按来源分组（NineS, EvoBench, 人工等）
│
├── tasks/                      # 任务管理（按需）
│   ├── active/                 # 当前活跃任务
│   └── archived/               # 归档任务
│
├── research/                   # 调研制品（按需）
│   ├── {version}/              # 按版本组织
│   ├── adr/                    # 架构决策记录
│   └── {topic}_*.md            # 主题性研究
│
├── designs/                    # 设计文档（按需）
│
├── sandbox/                    # 实验性代码沙箱（按需）
│   └── {version}/{variant}/
│
├── sessions/                   # 会话状态持久化（按需）
│   └── {YYYY-MM-DD}-{name}.md
│
├── benchmarks/                 # 基准测试数据（按需）
│   └── {topic}/
│
└── reviews/                    # 代码/质量审查结果（按需）
    └── {tool}-{type}/
```

### 7.2 `index.md` 设计建议

```markdown
# .local 工作区索引

## 当前焦点
- 版本：v7.3.0
- 主要任务：本地工作区结构设计
- 阻塞项：无

## 目录说明
| 目录 | 状态 | 说明 |
|------|------|------|
| feedbacks/ | 活跃 | 迭代反馈 |
| research/ | 活跃 | 调研制品 |
| tasks/ | 待启用 | 任务管理 |
| ...   | ...  | ...  |

## 最近活动
- 2026-04-20: 完成本地工作区结构调研
```

### 7.3 与 AI 工具的集成策略

推荐采用 **AGENTS.md（通用基线） + 工具特定配置（深度集成）** 的双轨策略：

```
项目根/
├── AGENTS.md                           # 通用基线（所有 AI 工具可读）
├── CLAUDE.md                           # Claude Code 深度配置
├── CLAUDE.local.md                     # Claude Code 个人覆盖（gitignored）
├── .cursor/rules/*.mdc                 # Cursor 深度配置
├── .codex/                             # Codex 配置
├── .github/copilot-instructions.md     # Copilot 配置
├── .local/                             # 本地工作区（gitignored）
└── .gitignore                          # 包含 .local/, CLAUDE.local.md 等
```

### 7.4 核心设计原则总结

1. **提交与本地严格分离**：规则提交，状态本地
2. **通用标准兜底，专用配置增强**：AGENTS.md + 工具特定文件
3. **索引驱动**：`index.md` 作为工作区的入口和导航
4. **按需创建**：目录不预创建，使用时生成
5. **版本+时间双维度**：支持按版本迭代和按时间追踪
6. **多来源反馈汇聚**：feedbacks/ 支持多种反馈来源
7. **沙箱隔离**：实验性代码与正式代码分离
8. **人机共读**：Markdown/YAML/JSONC 优先，避免二进制
9. **Token 敏感**：索引轻量、详情按需加载，适配 AI 工具的上下文窗口限制

---

## 八、参考来源

### 文章与博客
1. Andrew Nesbitt, ".gitlocal", nesbitt.io, 2026-03-06
2. "Cursor Rules: The Complete Guide", skillsplayground.com, 2026
3. "The Complete Guide to Cursor Rules in 2026", localskills.sh
4. "Inside ~/.claude", diljitpr.net, 2026-02-24
5. "Claude Code CLAUDE.md", dev.to/subprime2010
6. "Designing CLAUDE.md for Maximum Productivity", claudelab.net
7. "AGENTS.md Guide (2026)", vibecoding.app
8. "AI Agent Configuration Files: Complete Cross-Tool Guide", productbuilder.net
9. "Agentic Workflow: AI-Assisted Development with Claude Code", wal.sh

### GitHub 仓库
10. github.com/andrew/gitlocal — .gitlocal 提案实现
11. github.com/danielrosehill/Claude-Agent-Workspace-Model — Claude 工作区参考架构
12. github.com/fitchmultz/ralph — 本地优先任务编排
13. github.com/RichardGeorgeDavis/Codex-Workspace — Codex 工作区结构
14. github.com/SanderMoon/local-brain — Markdown 项目管理
15. github.com/farra/dev-agent-work — Agent 会话追踪
16. github.com/openai/codex/issues/5881 — `.agents` 标准化提案
17. github.com/openai/codex/issues/3706 — 项目级 .codex/ 支持
18. github.com/shanraisshan/claude-code-best-practice — Claude Code 最佳实践
19. github.com/shakacode/claude-code-commands-skills-agents — Claude Code 技能与命令

### 官方文档
20. cursor.com/help/customization/rules — Cursor 规则文档
21. code.claude.com/docs/en/claude-directory — Claude Code .claude 目录文档
22. developers.openai.com/codex/config-reference — Codex 配置参考
23. docs.github.com/en/copilot — Copilot 文档
24. docs.codeium.com/windsurf/cascade/memories — Windsurf 记忆文档

### 工具与框架
25. kaizenai.codes — KaizenAI 本地优先工作区
26. agentspan.ai — 持久执行引擎
27. dbos.dev — 持久工作流编排
28. github.com/microsoft/agent-framework — Microsoft Agent Framework
