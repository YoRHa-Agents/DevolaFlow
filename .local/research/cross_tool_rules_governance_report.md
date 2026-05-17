# 仓库治理规则与跨工具 AI 配置研究报告

> 研究日期：2026-04-20  
> 研究范围：AI 辅助开发中仓库级治理规则的跨工具消费模式、"灵魂规则"设计、规则编译/分发架构

---

## 一、AI 工具规则消费格局

### 1.1 各工具规则格式总览

| 工具 | 规则文件/目录 | 格式 | 激活方式 | 模块化支持 |
|------|-------------|------|---------|-----------|
| **Cursor** | `.cursor/rules/*.mdc` | Markdown + YAML frontmatter | alwaysApply / globs / AI 判断 / @引用 | 多文件、子目录 |
| **Claude Code** | `CLAUDE.md` + `.claude/rules/*.md` | 纯 Markdown（可含 YAML frontmatter） | 自动加载（层级继承） | 多文件、路径作用域 |
| **GitHub Copilot** | `.github/copilot-instructions.md` + `.github/instructions/*.instructions.md` | Markdown + `applyTo` frontmatter | 全局 / 路径匹配 | 多文件、路径绑定 |
| **Windsurf** | `.windsurfrules`（根目录）或 `.windsurf/rules/` | 纯文本/Markdown | 自动加载 | 单文件（旧）/ 多文件（新） |
| **Cline** | `.clinerules/` | Markdown | 自动加载 + 兼容 .cursorrules、AGENTS.md | 多文件 |
| **Roo Code** | `.roo/rules/` + `.roo/rules-{mode}/` | Markdown/纯文本 | 层级加载（全局→项目→模式） | 多文件、递归子目录、模式绑定 |
| **Zed** | `.rules`（优先级最高）| 纯 Markdown | 自动注入 Agent Panel | 单文件 + Rules Library |
| **KimiCode** | `~/.kimi/config.toml` + SKILL.md | TOML 配置 + Markdown 技能 | 配置文件 + 技能发现 | Agent YAML + Skills |
| **Gemini CLI** | `GEMINI.md`（可自定义文件名） | 纯 Markdown + `@file` 导入 | 层级加载 + JIT 扫描 | 模块化导入 |
| **AGENTS.md** | `AGENTS.md`（各目录层级） | 纯 Markdown | 就近原则（目录树） | 多文件（monorepo 友好） |
| **Codex (OpenAI)** | `AGENTS.md` | 纯 Markdown | 自动加载 | 多文件 |

### 1.2 规则读取优先级模型

**多数工具采用层级继承模型：**

```
组织策略（最高优先级）
  └── 全局用户级（~/.cursor/rules, ~/.claude/CLAUDE.md 等）
       └── 项目根目录（.cursor/rules/, CLAUDE.md 等）
            └── 子目录级别（就近原则）
                 └── 路径匹配（globs/applyTo）
```

**Zed 的互斥模型：** 仅读取第一个匹配文件（.rules > .cursorrules > .windsurfrules > AGENTS.md > CLAUDE.md），不做合并。

**Gemini CLI 的 JIT 模型：** 除了层级加载外，当工具访问文件时自动扫描该目录的 GEMINI.md，实现"按需注入"。

### 1.3 关键差异分析

| 维度 | 收敛方向 | 分歧点 |
|------|---------|--------|
| 文件格式 | Markdown 为主流 | frontmatter schema 不统一 |
| 模块化 | 多文件目录 | 目录命名各异 |
| 作用域 | 支持路径绑定 | globs vs applyTo vs mode 语义不同 |
| 激活策略 | 自动+手动 | "AI 判断是否相关"仅 Cursor 支持 |
| 跨仓库 | monorepo 层级 | 全局 vs 项目优先级冲突 |

---

## 二、"灵魂规则"（Soul Rules）与核心约束模式

### 2.1 Soul Spec 规范

**SoulSpec**（v0.5.2）是目前最完整的 AI 代理身份治理标准：

```
project/
├── soul.json        # 元数据清单（必选）
├── SOUL.md          # 核心人格/原则（必选）
├── IDENTITY.md      # 身份特征（可选）
├── AGENTS.md        # 操作流程（可选）
├── STYLE.md         # 沟通风格（可选）
└── HEARTBEAT.md     # 自主检查行为（可选）
```

**核心洞察：** 身份（Identity）与治理（Governance）是架构上独立的层，需要分别定义和实施。SoulSpec 解决"谁是这个 Agent"，而治理规则解决"它能做什么"。

### 2.2 ADR（架构决策记录）模式

ADR 在 AI 时代获得新用途——作为向 AI 解释"为什么这样设计"的上下文：

- **n8n 项目**：在 AGENTS.md 中内联 ADR，帮助 AI 在歧义场景做更好的决策
- **DevolaFlow 实践**：`.local/research/adr/` 存储架构决策，通过 SKILL.md 引用
- **rjmurillo/ai-agents**：专设 `.agents/governance/PROJECT-CONSTRAINTS.md`

**ADR 对 AI 的价值：** 研究表明，包含 ADR 的规则文件使 AI 中位运行时间减少 28.6%，Token 消耗减少 16.6%。

### 2.3 灵魂规则的分层模型

```
┌─────────────────────────────────────┐
│  Layer 5: 安全合规（不可变）          │  不可绕过的红线规则
├─────────────────────────────────────┤
│  Layer 4: 架构约束（核心）            │  项目基础设施决策
├─────────────────────────────────────┤
│  Layer 3: 编码规范（团队）            │  命名、格式、模式
├─────────────────────────────────────┤
│  Layer 2: 工作流偏好（可调）          │  提交流程、审查规则
├─────────────────────────────────────┤
│  Layer 1: 风格建议（弱约束）          │  注释风格、文档偏好
└─────────────────────────────────────┘
```

### 2.4 治理框架对比

| 框架 | 关注点 | 层级 | 工具支持 |
|------|--------|------|---------|
| SoulSpec | Agent 身份 | 人格/价值观 | Claude、Cursor、Windsurf |
| MaatSpec | 行为治理 | 5级风险分层 | 通用 |
| ABGS | 部署合规 | 9域30控制点 | CI/CD 集成 |
| DevolaFlow Rules | 工作流约束 | P1-P6 原则 | Cursor、Claude Code |

---

## 三、跨工具编译/分发方案

### 3.1 现有工具对比

| 工具 | 架构 | 输入格式 | 输出目标数 | 特色 |
|------|------|---------|-----------|------|
| **Crag** | 分析→编译→同步 | 自动检测仓库 | 14 | 零依赖、无 LLM、确定性 |
| **Rulix** | 单源→多目标同步 | `.rulix/rules/` Markdown | 5 | Token 预算验证 |
| **Rulesets** | CommonMark 编译 | `.ruleset/rules/` | 5 | Watch 模式 |
| **rule-composer** | 模板占位符替换 | Markdown + `{{}}` | 10 | compose/decompose 双向 |
| **ai-rules-sync** | 符号链接同步 | Git 仓库 | 12+ | 多源混合、隐私保护 |
| **Rulesync** | 处理器架构生成 | 统一规则文件 | 10+ | 技能/子代理/Hooks 支持 |

### 3.2 三种核心架构模式

#### 模式 A：编译器模式（Crag, Rulesets）

```
governance.md (源) → 编译器 → .cursor/rules/
                            → CLAUDE.md
                            → .github/copilot-instructions.md
                            → .windsurfrules
                            → AGENTS.md
```

**优点：** 输出独立、无运行时依赖、可 CI/CD 集成  
**缺点：** 需要构建步骤、输出文件可能被直接编辑导致漂移

#### 模式 B：链接同步模式（ai-rules-sync）

```
rules-repo/ (Git) ──symlink──→ project/.cursor/rules/
                   ──symlink──→ project/.claude/rules/
                   ──symlink──→ project/.github/instructions/
```

**优点：** 编辑即生效、多仓库共享、团队协作  
**缺点：** 不支持格式转换、符号链接在 Windows 上有兼容问题

#### 模式 C：模板+占位符模式（rule-composer）

```
rules/base.md (含 {{RULES_DIR}}, {{TOOL_NAME}}) → 渲染 → 工具特定文件
```

**优点：** 精细控制每个工具的差异点  
**缺点：** 模板维护复杂、难以自动检测漂移

### 3.3 Crag 的"分析驱动"创新

Crag 的独特之处在于它**不需要手写源文件**——直接分析仓库中的：
- `package.json` / `pyproject.toml` / `Cargo.toml`
- CI 工作流（`.github/workflows/`）
- Makefile / Dockerfile
- 25+ 技术栈信号

然后自动生成 `governance.md` 作为中间表示。这意味着规则始终与实际仓库状态保持同步。

### 3.4 DevolaFlow 现有的适配器构建

DevolaFlow 已有类似实践：`scripts/sync_cursor_skill.py` 将 `workflow-system/agent/` 下的规范文件同步到 `.cursor/skills/devola-flow/`。这是"单源多目标"的垂直实现，但目前仅覆盖 Cursor。

---

## 四、Gap 分析——当前方案的不足

### 4.1 格式碎片化

**问题：** 10+ 种工具使用不同的文件名、目录结构、frontmatter schema。即使有编译器，语义映射仍不完美（例如 Cursor 的"AI 判断激活"无法直接映射到 Copilot 的 `applyTo` glob）。

**影响：** 规则在不同工具中可能有不同的生效范围，导致开发者行为不一致。

### 4.2 缺少"不可变层"标准

**问题：** 现有工具都将规则视为平等的文本块，没有内建的"优先级层"或"不可覆盖"标记。SoulSpec 的 Layer 5 安全约束在编译到 .cursorrules 后与普通编码规范无法区分。

**影响：** AI 可能在上下文窗口压力下"忘记"关键安全规则。

### 4.3 语义损失

**问题：** 编译过程中会丢失元数据。例如：
- Cursor 的 `alwaysApply: true` 无法映射到 Claude Code 的路径作用域
- Roo Code 的模式绑定（`rules-code/`, `rules-architect/`）没有其他工具的对应概念
- Gemini 的 `@file` 导入语法不被其他工具识别

**影响：** 跨工具编译器要么选择最小公约数（功能退化），要么需要工具特定的覆盖层。

### 4.4 验证与漂移检测

**问题：** 大多数方案缺少运行时验证——规则是否真的被 AI 遵守？当前只有 Crag 提供"漂移审计"功能，但也只是文件级别的diff，不验证 AI 行为合规性。

**影响：** "写了规则但 AI 不遵守"是最常见的用户投诉，但没有闭环反馈机制。

### 4.5 上下文预算管理

**问题：** 仅 Rulix 提供 Token 预算验证。其他工具盲目将所有规则注入 prompt，在规则膨胀时导致 AI 性能下降。研究表明自动生成的规则文件反而**降低**AI 表现。

**影响：** 规则文件需要像代码一样有"性能预算"，超出则需要分层/按需加载。

### 4.6 缺少双向同步

**问题：** 当开发者直接编辑工具特定文件（例如在 Cursor UI 中修改 .mdc）后，变更无法自动回流到源文件。只有 rule-composer 的 `decompose` 命令尝试解决此问题。

**影响：** 团队中有人用 Cursor 改了规则，有人用 Claude Code，最终两套规则分叉。

---

## 五、推荐架构设计

### 5.1 推荐方案：分层编译 + 漂移检测

```
.rules/                          ← 仓库治理规则单一源（Source of Truth）
├── index.md                     ← 规则目录与分层说明
├── soul.md                      ← L5 不可变核心约束
├── architecture.md              ← L4 架构决策
├── conventions.md               ← L3 编码规范
├── workflow.md                  ← L2 工作流偏好
└── style.md                     ← L1 风格建议
```

```
scripts/compile-rules.py         ← 规则编译器
  输入: .rules/*.md
  输出:
    → .cursor/rules/*.mdc        (带 frontmatter 的 MDC)
    → CLAUDE.md                  (合并后的 Claude Code 格式)
    → .github/copilot-instructions.md
    → AGENTS.md                  (通用格式)
    → .windsurfrules             (合并后的纯文本)
    → .roo/rules/*.md            (Roo Code 格式)
```

### 5.2 核心设计原则

| 原则 | 说明 |
|------|------|
| **单源真理** | `.rules/` 是唯一可编辑位置，其他文件均为生成产物 |
| **分层优先级** | soul > architecture > conventions > workflow > style |
| **预算感知** | 编译器计算 Token 预算，超限时按优先级裁剪 |
| **漂移检测** | CI 中验证生成文件与源文件一致 |
| **向下兼容** | 生成的文件本身有效，不依赖编译器运行时 |
| **工具特定覆盖** | 允许 `.rules/overrides/cursor.md` 添加工具专有指令 |

### 5.3 编译策略

```yaml
# .rules/compile-config.yaml
version: "1.0"
targets:
  cursor:
    output_dir: ".cursor/rules"
    format: "mdc"
    frontmatter:
      soul: { alwaysApply: true }
      architecture: { alwaysApply: true }
      conventions: { globs: ["**/*.{ts,py,go}"] }
    token_budget: 12000
    
  claude:
    output_file: "CLAUDE.md"
    format: "merged-markdown"
    sections: [soul, architecture, conventions, workflow]
    token_budget: 8000
    
  copilot:
    output_file: ".github/copilot-instructions.md"
    format: "markdown"
    sections: [soul, architecture, conventions]
    token_budget: 6000
    
  agents_md:
    output_file: "AGENTS.md"
    format: "markdown"
    sections: [soul, architecture, conventions, workflow]
    token_budget: 10000
    
  windsurf:
    output_file: ".windsurfrules"
    format: "plaintext"
    sections: [soul, architecture, conventions]
    token_budget: 8000
```

### 5.4 Soul 规则设计示例

```markdown
<!-- .rules/soul.md -->
# Soul Rules — 不可变核心约束

## 安全红线
- 永远不提交密钥、Token、密码到版本控制
- 不执行 `rm -rf /`、`git push --force main` 等破坏性操作
- 不修改 `.env` 文件除非明确要求

## 架构边界
- 前端代码不直接访问数据库
- 微服务间通过 API 通信，不共享数据库
- 所有公开 API 必须经过认证中间件

## 质量底线
- 新代码必须有测试（覆盖率 ≥ 80%）
- 不使用 any / unknown 绕过类型检查
- 错误必须处理，不允许空 catch

## 工作流不变量
- 不直接推送到 main/master 分支
- PR 必须通过 CI 后才能合并
- 版本号更新必须通过 bump 脚本
```

### 5.5 与 DevolaFlow 的集成点

```
DevolaFlow 扩展点:
├── devola-local 技能（新增）
│   ├── 初始化 .rules/ 结构
│   ├── 初始化 .local/ 工作区
│   ├── 运行编译器生成多工具配置
│   └── 漂移检测（make check-rules）
│
├── SKILL.md 引用
│   └── references/rules-governance.md  ← 引用 .rules/ 中的规则
│
└── Gate 模块集成
    └── gate/rules_compliance.py  ← 验证生成代码是否违反 soul rules
```

### 5.6 Tradeoff 分析

| 方案 | 维护成本 | 精确度 | 团队协作 | 工具覆盖 | 推荐场景 |
|------|---------|--------|---------|---------|---------|
| **编译器（推荐）** | 中 | 高 | 好（生成文件可提交） | 广 | 大型团队、多工具环境 |
| 符号链接 | 低 | 中（无格式转换） | 一般 | 中 | 个人开发者、统一工具 |
| 手动维护 | 高 | 最高 | 差 | 无限 | 小项目、单工具 |
| 外部服务 | 低 | 中 | 好 | 依赖服务 | 企业级、有 SaaS 预算 |

---

## 六、参考实现与工具链

| 工具 | GitHub | 特点 | Star |
|------|--------|------|------|
| Crag | github.com/WhitehatD/crag | 零依赖、自动分析仓库 | ~200 |
| Rulix | github.com/danielcinome/rulix | Token 预算验证 | ~150 |
| Rulesets | github.com/outfitter-dev/rulesets | CommonMark 编译器 | ~100 |
| rule-composer | github.com/mia-cx/rule-composer | 双向 compose/decompose | ~80 |
| ai-rules-sync | github.com/lbb00/ai-rules-sync | 符号链接、12+ 工具 | ~500 |
| Rulesync | rulesync.dyoshikawa.com | 处理器架构 | ~50 |
| SoulSpec | github.com/clawsouls/soulspec | Agent 身份标准 | ~300 |

---

## 七、核心结论

1. **市场正在收敛**：AGENTS.md 作为 Linux Foundation 下的跨工具标准正在获得广泛支持，但各工具仍保留自有格式作为"增强层"。

2. **单源编译是最佳实践**：从一套规则源文件编译到多个工具格式是当前最成熟的模式，Crag 的"仓库分析驱动"是最创新的方向。

3. **分层是关键**：规则必须有明确的优先级层，soul rules（安全/合规）应该在所有工具中始终加载且不可被覆盖。

4. **Token 预算是被忽视的维度**：规则膨胀会降低 AI 表现，需要像性能预算一样管理规则的 Token 消耗。

5. **DevolaFlow 优势**：已有 `sync_cursor_skill.py` 基础设施、版本一致性验证（11 位置同步）、Gate 模块验证，天然适合扩展为跨工具规则编译器。

---

*报告完成。后续可进入方案设计阶段，产出 `.rules/` 目录结构规范与 devola-local 技能实现方案。*
