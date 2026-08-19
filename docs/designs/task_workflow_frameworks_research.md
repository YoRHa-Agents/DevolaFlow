# Task: 自动化 Agent 工作流体系设计 (Automated Agent Workflow System Design)

> 设计一套完整的自动化 Agent 工作流体系，用于管理从任务调研、架构设计、代码实现、测试验证到部署发布的全生命周期。工作流体系需作为元框架（meta-framework）支持多种工作流类型（如 research-design-review-refine、design-plan-impl-review-test-refine-testgate-release 等），而非仅绑定单一流水线。需支持多层级 Agent 委派（Project → Stage → Wave → Task），利用 SubAgent 隔离上下文，通过 AgentTeams 实现职责分治（Research/Design/Implement/Test/Review），并内置多种仓库模式（本地/GitHub/其他 Git 平台）。最终产物需以多工具兼容的 Skill 组合形式交付（兼容 Cursor/Claude Code/Copilot），采用多级索引管控上下文，同时输出面向 Agent 的英文体系和面向人类开发者的中英文经验体系，并预留 VSCode 插件化入口。当前任务仅做方向性调研和体系设计，不进行具体代码实现。

## Targets

1. **已有工作流最佳实践调研**: 调研 2025年9月之后的 Agent 工作流相关 best-practice、论文、设计文档、开源实现（如 CrewAI、AutoGen、LangGraph、OpenHands、Devin 工作流等），提炼可复用的工作流模式与教训
2. **Agent 层级委派模型设计**: 设计 Project-Main-Agent → Stage-Main-Agent → Wave-Main-Agent → Task-Sub-Agent 的四层委派架构，明确每层职责边界与通信协议，确保主 Agent 仅做调度不做具体工作
3. **AgentTeams 职责划分设计**: 设计 Research / Design / Implement / Test / Review 五个 AgentTeam 的角色定义、输入输出契约、评估标准，以及团队间的协作流程
4. **任务精细化分解框架**: 设计 Stage → Wave → Task 的三级分解框架，包含依赖管理、并行策略、Gate（质量门禁）机制，确保每个原子任务足够单元化（<30 min agent work）
5. **仓库模式系统设计**: 设计内置多种模式的切换系统——本地仓库模式（无 release/CI）、GitHub 仓库模式（跨平台构建、README、UserGuide、GitHub Actions、GitHub Pages、在线 Demo）、其他 Git 平台模式（MR 流程等），以及模式间的功能矩阵
6. **前置决策阶段设计**: 设计 Pre-Decision Phase，在研发阶段开始前最大化收集用户输入与决策信息，减少研发中的阻断项，包含决策清单模板与信息收集协议
7. **设计原则整合方案**: 将 SOLID、TDD、DDD、Code-Rules（`/home/agent/workspace/code-rules`）、Clean Architecture 等设计原则整合进工作流各环节，明确在哪个阶段由哪个 AgentTeam 负责哪些原则的执行
8. **连续执行协议设计**: 设计确认后可连续运行的执行协议，包含 checkpoint/resume 机制、异常处理策略、人工干预点定义，目标是前期确认后尽量无中断完成整个研发周期
9. **产品形态调研与交付架构设计**: 调研 Agent Skill/Rules/Knowledge 的主流产品形态（Cursor Skills、Codex Skills、Claude Code CLAUDE.md、Copilot Instructions 等），设计多工具兼容的交付架构——多级索引 Skill 组合（避免单一超长文件）+ MVP 单文件 Skill（面向 Cursor shared-script）
10. **双体系产出设计**: 设计面向 Agent 的英文体系（skill + rules + knowledge 组合，机器可解析）和面向人类开发者的中英文经验体系（文档 + demo page，人类可读可理解），明确两个体系的内容映射关系与同步机制
11. **VSCode 插件化预留设计**: 设计未来将工作流体系从 Skill/Rules 文件形态升级为 VSCode 插件的扩展入口，定义插件化边界（哪些能力适合插件化、哪些保持文件形态），输出插件化路线图草案
12. **工作流类型谱系调研与元框架设计**: 调研不同类型的工作流实际形式——research-only 流、research-design-review-refine 流、design-plan-impl-review-test-refine-testgate-release 全流程、hotfix 快速修复流、refactoring 重构流等——并设计工作流体系如何作为元框架（meta-framework）整合和支持这些不同类型，包含工作流模板注册、阶段可组合性、条件分支与跳过机制

## Acceptance Criteria

### Step 1: Agent 工作流最佳实践调研 (no dependencies — start here)
- [ ] 调研至少 8 个 Agent 工作流框架/平台（CrewAI, AutoGen, LangGraph, OpenHands, Devin, MetaGPT, ChatDev, Cursor Agent 等）
- [ ] 每个框架记录：名称、架构模式、Agent 协作模型、任务分解策略、错误处理方式、优劣势
- [ ] 收集 2025年9月后的 Agent 编排相关论文/博客/设计文档（至少 10 篇）
- [ ] 分析 `/home/agent/workspace/EchoAccess/.local/stages/` 现有 Stage/Wave 模式的成功经验与痛点
- [ ] 分析 `~/.cursor` 下最近的 plan 文件，提炼 Cursor Agent 使用中的共性模式
- [ ] 输出调研汇总报告（含对比矩阵表格）

### Step 2: Agent 层级架构与通信协议设计 (depends on Step 1)
- [ ] 定义四层 Agent 层级（Project → Stage → Wave → Task）的职责边界
- [ ] 设计每层 Agent 的输入/输出契约（接收什么、产出什么、如何汇报）
- [ ] 设计层间通信协议（任务下发格式、状态汇报格式、异常上报格式）
- [ ] 明确"主 Agent 不做具体工作"的执行约束与违规检测机制
- [ ] 设计 Agent 上下文隔离策略（每个 SubAgent 独立上下文窗口，避免污染）
- [ ] 提供至少 2 个完整的委派链示例（从 Project 到 Task 的完整流转）

### Step 3: AgentTeams 角色定义与协作流程设计 (parallel with Step 2)
- [ ] 定义 Research Team：调研范围确定、信息收集、对比分析、报告产出的标准流程
- [ ] 定义 Design Team：架构设计、接口定义、文档产出、设计评审的标准流程
- [ ] 定义 Implement Team：代码编写、单元测试、Code-Rules 遵循的标准流程
- [ ] 定义 Test Team：测试策略制定、集成测试、回归测试、覆盖率验证的标准流程
- [ ] 定义 Review Team：代码审查、设计审查、安全审查、质量评分的标准流程
- [ ] 设计 Team 间的手续接口（Handoff Protocol）：交付物格式、验收标准、回退机制
- [ ] 设计 Team 内的 Sub-Agent 分工策略（何时并行、何时串行）

### Step 4: 任务分解框架与 Gate 机制设计 (depends on Step 2)
- [ ] 设计 Stage 分解规则：如何将项目目标拆分为 Stage，Stage 间依赖关系的表达方式
- [ ] 设计 Wave 分解规则：Stage 内的 Wave 并行策略，Wave 间同步点定义
- [ ] 设计 Task 分解规则：Wave 内的原子任务定义标准（<30 min），任务间依赖描述
- [ ] 设计 Gate 质量门禁机制：每个 Stage/Wave/Task 完成后的验收标准（参考 EchoAccess gate_report.md 格式）
- [ ] 设计依赖矩阵自动生成策略（参考 EchoAccess wp1a_dependency_matrix.md）
- [ ] 设计失败处理流程：Task 失败 → Wave 回退 → Stage 重试的递归处理链

### Step 5: 仓库模式与部署策略设计 (parallel with Step 4)
- [ ] 定义 Local 模式功能集：无远程发布、本地构建验证、本地文档
- [ ] 定义 GitHub 模式功能集：GitHub Actions CI/CD、跨平台构建矩阵、README 生成、UserGuide、GitHub Pages 部署、在线 Demo、Release 流程、CHANGELOG 生成
- [ ] 定义 Other-Git 模式功能集：MR/PR 流程适配、CI 集成适配（GitLab CI、Gitea Actions 等）
- [ ] 设计模式检测与自动切换逻辑（根据 .git/config 远程 URL 自动识别）
- [ ] 设计功能矩阵表（模式 × 功能 的开关映射）
- [ ] 设计每种模式的部署 Pipeline 模板

### Step 6: 前置决策与连续执行协议设计 (depends on Step 2, Step 3)
- [ ] 设计 Pre-Decision Phase 决策清单模板（覆盖：技术栈、仓库模式、语言选型、目标平台、质量标准、发布策略）
- [ ] 设计信息收集协议（哪些信息必须提前收集、哪些可以有默认值、哪些需要用户确认）
- [ ] 设计连续执行的 Checkpoint/Resume 机制（每个 Gate 后持久化状态）
- [ ] 设计异常处理策略分级：可自动恢复 / 需暂停等待 / 需人工干预 / 需整体回退
- [ ] 设计人工干预点（Breakpoint）定义标准：何时必须等用户确认、何时可自动继续
- [ ] 设计执行日志与进度报告格式（参考 EchoAccess overview.md 的进度表格格式）

### Step 7: 设计原则整合与工作流规范文档 (depends on Step 4, Step 5, Step 6, Step 10)
- [ ] 将 Code-Rules 体系（`/home/agent/workspace/code-rules`）映射到工作流各环节：哪个 Phase 加载哪些 rules
- [ ] 将 SOLID/TDD/DDD 原则映射到 AgentTeam 职责：Design Team 负责 SOLID 审查、Implement Team 执行 TDD 流程、Review Team 验证 DDD 合规
- [ ] 设计工作流元数据格式（workflow.yaml 或类似），用于描述完整工作流实例
- [ ] 整合所有设计产出为一份完整的工作流规范文档
- [ ] 设计工作流模板（可复用的 Stage/Wave/Task 模板），便于快速启动新项目
- [ ] 提供至少 1 个完整的端到端示例（从用户需求到部署完成的全流程演练）

### Step 10: 工作流类型谱系调研与元框架设计 (parallel with Step 1)
- [ ] 调研 research-design-review-refine 工作流的实际形式：阶段定义、每阶段输入输出、review 触发 refine 的循环条件、终止判据
- [ ] 调研 design-plan-impl-review-test-refine-testgate-release 全流程工作流：完整阶段链、Gate 在各阶段间的作用、refine 回环的触发条件与回退范围
- [ ] 调研其他常见工作流类型并建立工作流类型谱系（至少覆盖 8 种）：research-only、design-only、hotfix（bug-triage-fix-test-release）、refactoring（analyze-plan-refactor-test-verify）、migration、spike/PoC、documentation-only、security-audit 等
- [ ] 对每种工作流类型记录：名称、适用场景、阶段组成（有序列表）、必选/可选阶段、循环/回环点、典型时长、参与的 AgentTeam 子集
- [ ] 分析不同工作流类型间的共性阶段（如 review、test、gate 是否为通用原语）与差异点
- [ ] 设计元框架的阶段可组合性模型：将工作流定义为阶段原语的有序组合（类似 pipeline-as-code），支持条件分支、循环回环、阶段跳过
- [ ] 设计工作流模板注册机制：如何定义、存储、选择工作流模板（workflow-template.yaml），支持用户自定义与内置模板共存
- [ ] 设计工作流类型自动推荐逻辑：根据用户任务描述自动推荐适合的工作流类型（如"修复一个 bug" → hotfix 流，"从零开发一个库" → 全流程流）
- [ ] 提供至少 3 个完整的工作流实例定义示例（research-design-review-refine、全流程、hotfix），展示元框架如何表达不同工作流

### Step 8: 产品形态调研与多工具兼容交付架构设计 (parallel with Step 4)
- [ ] 调研 Cursor Skill 格式（`~/.cursor/skills/`，SKILL.md + 目录结构，progressive disclosure 模式）
- [ ] 调研 Codex Skill 格式（`~/.codex/skills/`，SKILL.md + scripts/ + references/ + assets/ 结构）
- [ ] 调研 Claude Code 的 CLAUDE.md / .claude/ 配置约定及其 Agent 指令加载机制
- [ ] 调研 GitHub Copilot 的 .github/copilot-instructions.md 及自定义 instructions 机制
- [ ] 分析各工具的 Skill/Rules 加载机制共性（触发机制、上下文窗口预算、progressive disclosure）
- [ ] 设计多级索引架构：入口 Skill（<500 行）→ 分域 reference 文件 → 按需加载的 knowledge 文件，避免单一超长文件
- [ ] 设计跨工具兼容层：统一的 workflow YAML schema，各工具适配器（Cursor adapter、Codex adapter、Claude Code adapter、Copilot adapter）
- [ ] 设计 MVP 单文件 Skill 方案：将核心工作流精炼为一个自包含的 Cursor shared-script 文件（<500 行），覆盖最小可行功能集

### Step 9: 双体系产出与 VSCode 插件化预留设计 (depends on Step 8)
- [ ] 设计 Agent 体系目录结构：英文 skill 组合 + rules 文件 + knowledge base，机器可解析的元数据格式
- [ ] 设计 Human 体系目录结构：中英文文档 + 交互式 demo page + 可视化工作流图 + 快速入门指南
- [ ] 设计两体系间的内容映射关系：Agent 体系是 source of truth，Human 体系从 Agent 体系自动/半自动生成
- [ ] 设计同步机制：Agent 体系更新后，Human 体系的同步策略（CI 驱动生成 vs 手动同步 vs hybrid）
- [ ] 设计 VSCode 插件化边界分析：哪些能力适合插件化（UI 面板、命令面板、状态栏、TreeView）vs 保持文件形态（skills、rules、knowledge）
- [ ] 输出 VSCode 插件化路线图草案：Phase 1 文件形态 → Phase 2 命令面板集成 → Phase 3 完整插件
- [ ] 设计产物版本管理策略：skill 版本号、兼容性矩阵（工具版本 × skill 版本）

## Context

### Repos:
- `/home/agent/workspace/EchoAccess/.local/` — 已有的多 Stage 工作流实践案例，包含完整的 Stage/Wave/Gate 结构
  - `stages/overview.md` — Stage 进度总览表（含 Stage/Wave/Status/Round/Coverage 等字段）
  - `stages/S01_scaffold/gate_report.md` — Gate 质量门禁报告示例
  - `wp_outputs/wp1a_dependency_matrix.md` — 依赖矩阵示例
  - `task_make_impl_plan.md` — Plan 生成任务描述
- `/home/agent/workspace/code-rules/` — Agent 代码生成规则体系
  - `agent/en/guide.md` — Agent 规则加载协议（Minimal/Standard/Full 三策略）
  - `agent/en/core/principles.md` — 核心通用规则（20-30 条 MUST/SHOULD/MAY）
  - `agent/en/quality/` — 7 维质量维度规则（security/performance/maintainability 等）
  - `agent/en/tasks/` — 4 种任务类型 overlay（new_feature/bug_fix/refactoring/test_writing）
  - `agent/en/languages/` — 8 语言规则（python/cpp/rust/go/typescript 等）
- `/home/agent/workspace/code-rules/design/en/architecture.md` — 规则系统架构设计文档（4 层结构、冲突解决、评估系统）
- `/home/agent/workspace/code-rules/research/en/design_principles_and_literature.md` — 设计原则综述（78 原则、57 book rules、22 code smells、80 language rules）
- `/home/agent/research/tui_best_practice_solution/task.md` — 已有 task.md 样例参考（TUI 调研任务）
- `~/.cursor/skills-cursor/` — Cursor 内置 Skill 实现参考（9 个 Skill，展示标准目录结构和 SKILL.md 格式）
  - `create-skill/SKILL.md` — Skill 创建指南（含目录布局、description 最佳实践、progressive disclosure 模式、<500 行限制）
  - `create-rule/SKILL.md` — Rule 创建指南（.cursor/rules/ 目录结构、.mdc 格式）
  - `babysit/SKILL.md` — 复杂工作流 Skill 示例（PR 维护循环）
- `~/.codex/skills/.system/` — Codex Skill 体系参考
  - `skill-creator/SKILL.md` — Codex Skill 创建指南（含 scripts/references/assets 三类资源、agents/openai.yaml UI 元数据、forward-testing 验证流程）
  - `plugin-creator/SKILL.md` — Codex 插件创建指南（plugin.json 结构、marketplace 元数据）

### Docs:
**Agent 工作流框架:**
- CrewAI: https://docs.crewai.com/
- AutoGen: https://microsoft.github.io/autogen/
- LangGraph: https://langchain-ai.github.io/langgraph/
- MetaGPT: https://docs.deepwisdom.ai/
- OpenHands (previously OpenDevin): https://docs.all-hands.dev/
- ChatDev: https://github.com/OpenBMB/ChatDev

**Agent 编排最佳实践:**
- Anthropic Agent Design Patterns: https://docs.anthropic.com/en/docs/build-with-claude/agent-patterns
- OpenAI Agents SDK: https://openai.github.io/openai-agents-python/
- Cursor Agent Best Practices (2026): https://docs.cursor.com/agent

**设计原则 & 方法论:**
- Clean Architecture (R.C. Martin): https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html
- Hexagonal Architecture (A. Cockburn): https://alistair.cockburn.us/hexagonal-architecture/
- TDD Red-Green-Refactor: 见 `/home/agent/workspace/code-rules/research/en/design_principles_and_literature.md` Part 2

**CI/CD & 部署:**
- GitHub Actions: https://docs.github.com/en/actions
- GitLab CI: https://docs.gitlab.com/ee/ci/

**工作流类型与模式参考:**
- GitHub Flow: https://docs.github.com/en/get-started/using-github/github-flow
- GitLab Flow: https://about.gitlab.com/topics/version-control/what-is-gitlab-flow/
- Trunk-Based Development: https://trunkbaseddevelopment.com/
- SDLC Workflow Models: https://en.wikipedia.org/wiki/Software_development_process
- CI/CD Pipeline Patterns: https://martinfowler.com/articles/continuousIntegration.html
- Inner Source Workflows: https://innersourcecommons.org/learn/learning-path/

**Skill/Rules 产品形态参考:**
- Cursor Skills 文档: https://docs.cursor.com/agent/skills
- Cursor Rules 文档: https://docs.cursor.com/context/rules
- Claude Code CLAUDE.md 约定: https://docs.anthropic.com/en/docs/claude-code/settings
- GitHub Copilot Instructions: https://docs.github.com/en/copilot/customizing-copilot/adding-repository-custom-instructions-for-github-copilot
- Codex Skills 体系: 见 `~/.codex/skills/.system/skill-creator/SKILL.md`

**VSCode 插件开发:**
- VSCode Extension API: https://code.visualstudio.com/api
- VSCode Extension Guides: https://code.visualstudio.com/api/extension-guides/overview

### Developer insights:
- **EchoAccess 经验总结**: 已实践 17-Stage、7-Wave 的工程结构，每 Stage 有 Gate Report 质量门禁（build/clippy/test/fmt 四项检查），Stage 间通过 Wave 编号管理并行度，overview.md 实时追踪进度（含 Composite Score、Coverage、Blockers）
- **SubAgent 上下文隔离**: Cursor 环境下 SubAgent 通过 Task tool 启动独立上下文，避免主 Agent 上下文窗口被细节污染。关键经验：必须在任务描述中提供完整上下文（SubAgent 看不到用户消息和主 Agent 历史）
- **Code-Rules 加载策略**: 已有三级加载策略（Minimal ~2K tokens / Standard ~5K / Full ~12K），可按语言+任务类型+质量维度按需加载，避免上下文浪费。此策略可直接整合到工作流的 Implement/Review 阶段
- **设计原则冲突解决**: SOLID vs YAGNI/KISS 存在已知张力，已有解决框架——在架构边界用 SOLID，模块内部用 YAGNI。此经验需编入工作流的 Design Team 职责规范
- **Gate 机制实效**: EchoAccess 实践中 Gate 四项检查（build/clippy/test/fmt）可在 <2 min 完成，失败后自动进入修复轮次（Round），成功则推进下一 Stage。Round 计数对追踪质量趋势有价值
- **依赖矩阵前置**: 在 Plan 阶段即产出依赖矩阵（如 wp1a），可有效避免 Stage 执行时的循环依赖和阻塞。此实践应固化到工作流 Pre-Decision Phase
- **Agent 行为约束**: 已有经验——主 Agent 越界执行具体任务时，容易导致上下文溢出和质量下降。需在工作流中设计强约束：每层 Agent 仅做调度、状态管理和质量检查
- **Checkpoint 需求**: 长时间运行的工作流（10+ Stage）在 Cursor 环境中可能因 session 中断而丢失状态。需设计基于文件的 checkpoint 机制（如 EchoAccess overview.md 的做法）
- **Skill 上下文预算**: Cursor Skill 的 SKILL.md 应控制在 <500 行，通过 progressive disclosure 将详细内容拆分到 reference 文件按需加载。Codex Skill 有三级加载：metadata ~100 词（始终在上下文）→ SKILL.md body <5K 词（触发后加载）→ bundled resources（按需加载）。此模式与 code-rules 的 Minimal/Standard/Full 三策略天然对齐
- **多工具格式差异**: Cursor 使用 `~/.cursor/skills/` + `.cursor/rules/`，Codex 使用 `~/.codex/skills/` + `agents/openai.yaml`，Claude Code 使用 `CLAUDE.md` + `.claude/` 目录，Copilot 使用 `.github/copilot-instructions.md`。四者的核心抽象一致（触发条件 + 指令内容 + 资源引用），但文件格式和加载机制不同。需要一个统一的 source schema + 各工具适配器
- **MVP 单文件约束**: Cursor 的 shared-script 功能要求单文件自包含，不能引用外部 reference 文件。需将核心工作流逻辑（Agent 层级、Gate 机制、仓库模式选择）压缩为一个高度精炼的单文件 Skill（类似 nexis-create-task 命令的自包含模式）
- **双体系经验**: code-rules 已有 `en/` 和 `zh/` 双语对称结构（相同 rule ID，不同语言文本），此模式可直接复用于面向 Agent 体系（英文）和面向 Human 体系（中英文）的双轨设计
- **插件化渐进路径**: 从文件形态到 VSCode 插件的渐进路径——Phase 1: 纯文件（skills/rules/knowledge），Phase 2: 命令面板 + TreeView（状态可视化），Phase 3: 完整插件（内置 Agent 调度 UI）。前两阶段的设计需确保能无缝升级到后续阶段
- **工作流类型多样性**: 实际使用中不同任务需要不同的工作流形式——纯调研任务（research → compare → report）无需 impl/test/release 阶段；hotfix 任务（triage → fix → test → release）需要跳过 design 阶段直接进入修复；重构任务（analyze → plan → refactor → test → verify）则需要特别的回归验证。工作流系统不能是单一刚性管线，而应是可组合的阶段原语框架
- **回环（Loop-back）模式**: review-refine 和 test-refine 是两种核心回环模式——review 不通过时需要回退到 design 或 impl 阶段重做，test 不通过时需要回退到 impl 修复。回环需要有明确的终止条件（如最大轮次数、质量分阈值），避免无限循环。EchoAccess 的 Round 计数机制就是回环控制的实践
- **阶段原语化**: 如果将 research / design / plan / impl / review / test / refine / gate / release 等视为可组合的原语（primitive），则不同工作流类型就是这些原语的不同排列组合。类似 CI/CD pipeline-as-code（GitHub Actions 的 jobs/steps 模型），工作流定义应该是声明式的 YAML 模板
- **工作流类型推荐**: 用户描述任务时往往不会主动选择工作流类型（"帮我修个 bug" vs "帮我从零设计一个系统"）。系统需要根据任务描述的关键词和意图自动推荐合适的工作流模板，同时允许用户覆盖选择

### Editable Paths
- `/home/agent/research/full_workflow_of_impl_and_deploy_design.md/` — 工作流设计产出目录
- `/home/agent/reference/` — 参考项目 clone 目标目录（如需 clone 仓库）

### Agent Rules
- Use plan mode first to create a plan before implementation.
- Ask the user when in doubt.
- Write tests before implementation.
- Set up `.cursor/` hooks for develop-test-debug loops.
- Use subagent to dive into separated tasks.
<!-- Add task-specific rules below -->
- **方向性调研，不写代码**: 当前 task 仅产出调研报告和设计文档，不进行任何代码实现或深度技术 PoC
- **分层调研**: 不同调研方向（Agent 框架对比、设计原则整合、仓库模式分析）使用独立 SubAgent 并行执行
- **经验复用优先**: 优先从 EchoAccess 实践和 code-rules 体系中提取已验证的模式，而非从零设计
- **引用溯源**: 所有设计决策必须附带依据来源（论文/文档/实践经验/参考项目）
- **中英双语**: 核心设计文档和术语表需中英双语输出
- **可操作性验证**: 每个设计元素需附带"如何在 Cursor Agent 环境中落地"的操作说明
- **MVP 优先**: 先设计最小可行工作流（覆盖 local 模式 + 单语言），再扩展到完整多模式版本
- **参考历史 plan**: 充分利用 `~/.cursor` 下的历史 plan 文件（尤其近一周内的），提炼共性模式和反模式
- **Skill 500 行硬约束**: 任何入口级 SKILL.md 不超过 500 行，详细内容通过 progressive disclosure 拆分到 reference 文件（一级深度，不嵌套引用）
- **多工具兼容优先**: 产物设计需同时考虑 Cursor/Claude Code/Codex/Copilot 四种工具的加载机制差异，设计统一 source schema + 工具适配器，而非为每个工具单独维护
- **MVP 先行**: 先产出 MVP 单文件 Skill（面向 Cursor shared-script），验证核心工作流可行后再扩展为完整多文件 Skill 组合
- **Agent 体系为 Source of Truth**: 面向 Agent 的英文体系是唯一 source of truth，面向 Human 的中英文文档从 Agent 体系生成/派生，不独立维护
- **工作流类型全覆盖**: 不能仅设计全流程（design-plan-impl-test-release）一种工作流，需至少覆盖 8 种工作流类型（research-only、design-review-refine、全流程、hotfix、refactoring、migration、spike/PoC、doc-only 等），并验证元框架能够通过阶段原语组合统一表达它们

## Skills

### Open URL
Use browser to open URLs and read the contents.
If the url is *feishu.cn* url, let user login in browser first.

### Web Research
搜索 Agent 工作流编排的最新实践（2025-2026）、多 Agent 协作论文、CI/CD 自动化最佳实践。重点搜索 Anthropic/OpenAI/Google 的 Agent 设计指南和 Cursor/Devin/Windsurf 的工作流模式。

### Code Exploration
浏览 EchoAccess 项目的 `.local/stages/` 目录结构和历史 plan 文件，提取已有工作流模式。浏览 code-rules 体系的完整结构，理解规则加载和冲突解决机制。

### Parallel Subagent
使用 SubAgent 并行调研不同方向：(1) Agent 框架对比 (2) 设计原则整合方案 (3) 仓库模式与部署策略 (4) 前置决策与连续执行。每个 SubAgent 需提供完整上下文描述，避免依赖主 Agent 历史。

## TODOs

### Phase 1: Agent 工作流生态调研（Step 1, no dependencies — start here）
- [ ] 1.1 调研 CrewAI、AutoGen、LangGraph 的多 Agent 编排架构与任务分解模式
- [ ] 1.2 调研 MetaGPT、ChatDev 的 Agent 角色分工与协作流程设计
- [ ] 1.3 调研 OpenHands、Devin 的端到端工作流与 CI/CD 集成方式
- [ ] 1.4 调研 Anthropic/OpenAI 官方的 Agent 设计指南与最佳实践
- [ ] 1.5 分析 EchoAccess `.local/stages/` 的 Stage/Wave/Gate 模式，提炼成功经验与改进点
- [ ] 1.6 分析 `~/.cursor` 下近期 plan 文件，提取 Cursor Agent 使用的共性模式
- [ ] 1.7 输出综合调研报告（含框架对比矩阵 + 模式提炼清单）

### Phase 2: Agent 层级架构与 AgentTeams 设计（Step 2 + Step 3, depends on Phase 1）
- [ ] 2.1 设计四层 Agent 层级模型（Project → Stage → Wave → Task）及其职责边界
- [ ] 2.2 设计层间通信协议（任务下发/状态汇报/异常上报的消息格式）
- [ ] 2.3 设计 Research/Design/Implement/Test/Review 五个 AgentTeam 的角色规范
- [ ] 2.4 设计 Team 间 Handoff Protocol（交付物格式、验收标准、回退机制）
- [ ] 2.5 设计上下文隔离策略与 SubAgent 上下文注入模板

### Phase 3: 任务分解框架与 Gate 机制（Step 4, depends on Phase 2）
- [ ] 3.1 设计 Stage/Wave/Task 三级分解规则与依赖表达格式
- [ ] 3.2 设计 Gate 质量门禁机制（参考 EchoAccess gate_report.md）
- [ ] 3.3 设计依赖矩阵自动生成策略
- [ ] 3.4 设计失败处理与回退策略

### Phase 4: 仓库模式与部署策略（Step 5, parallel with Phase 3）
- [ ] 4.1 定义 Local/GitHub/Other-Git 三种模式的功能矩阵
- [ ] 4.2 设计模式检测与自动切换逻辑
- [ ] 4.3 设计各模式的 CI/CD Pipeline 模板

### Phase 5: 前置决策与连续执行协议（Step 6, depends on Phase 2）
- [ ] 5.1 设计 Pre-Decision Phase 决策清单模板
- [ ] 5.2 设计 Checkpoint/Resume 机制
- [ ] 5.3 设计异常分级与人工干预点定义

### Phase 6: 设计原则整合与规范文档（Step 7, depends on Phase 3, Phase 4, Phase 5, Phase 7）
- [ ] 6.1 将 Code-Rules 体系映射到工作流各环节
- [ ] 6.2 将 SOLID/TDD/DDD 原则映射到 AgentTeam 职责
- [ ] 6.3 整合产出完整工作流规范文档
- [ ] 6.4 设计可复用的工作流模板
- [ ] 6.5 提供端到端示例演练

### Phase 7: 工作流类型谱系调研与元框架设计（Step 10, parallel with Phase 1）
- [ ] 7.1 调研 research-design-review-refine 工作流的阶段定义、回环条件与终止判据
- [ ] 7.2 调研 design-plan-impl-review-test-refine-testgate-release 全流程的完整阶段链与 Gate 机制
- [ ] 7.3 调研并建立工作流类型谱系（至少 8 种类型：research-only、hotfix、refactoring、migration、spike/PoC、doc-only 等）
- [ ] 7.4 提取共性阶段原语（research/design/plan/impl/review/test/refine/gate/release）与差异点
- [ ] 7.5 设计元框架的阶段可组合性模型与工作流模板注册机制
- [ ] 7.6 设计工作流类型自动推荐逻辑
- [ ] 7.7 提供至少 3 个完整工作流实例定义示例

### Phase 8: 产品形态调研与交付架构设计（Step 8, parallel with Phase 3）
- [ ] 8.1 调研 Cursor/Codex/Claude Code/Copilot 四工具的 Skill/Rules 格式与加载机制
- [ ] 8.2 分析四工具的共性抽象（触发机制、上下文预算、progressive disclosure）
- [ ] 8.3 设计多级索引 Skill 架构（入口 SKILL.md → 分域 reference → 按需 knowledge）
- [ ] 8.4 设计跨工具兼容层（统一 source schema + 工具适配器）
- [ ] 8.5 设计 MVP 单文件 Skill（Cursor shared-script，<500 行自包含）

### Phase 9: 双体系产出与插件化预留（Step 9, depends on Phase 8）
- [ ] 9.1 设计 Agent 体系目录结构与元数据格式（英文，机器可解析）
- [ ] 9.2 设计 Human 体系目录结构与内容规范（中英文，含 demo page）
- [ ] 9.3 设计两体系间映射关系与同步机制
- [ ] 9.4 设计 VSCode 插件化边界与渐进路线图
- [ ] 9.5 设计产物版本管理与兼容性矩阵
