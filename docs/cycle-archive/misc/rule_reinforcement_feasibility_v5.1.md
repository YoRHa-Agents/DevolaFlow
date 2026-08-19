# 收敛迭代中规则强化机制可行性调研报告

**任务 ID:** T02-rule-reinforcement-feasibility
**版本目标:** v5.1.0-pre
**日期:** 2026-04-14
**状态:** 完成

---

## 1. 背景与问题定义

### 1.1 核心需求

用户反馈原文：
> "在任务处理阶段在涉及多轮次迭代时，使用不可被覆写的规则，例如 mdc 或其他形式进行强化（需要调研是否可行，以及是否存在不使用实体文件交互的合理方式）"

### 1.2 问题拆解

1. **多轮迭代中行为漂移**：当收敛轮次 (convergence round) 反复执行时，L3 Task Agent 可能在后续轮次中"遗忘"前几轮发现的问题模式，导致相同错误重复出现。
2. **规则强化时机**：Gate FAIL → 下一轮 dispatch 之间，是否有机制将上一轮的 findings 转化为对下一轮 agent 行为的硬约束？
3. **文件 vs 无文件**：`.mdc` 等规则依赖实体文件，是否有办法在不写文件的前提下实现等效的行为强化？

### 1.3 当前系统状态

| 组件 | 文件 | 现有能力 | 缺口 |
|------|------|----------|------|
| 收敛检测 | `gate/convergence.py` | 停滞检测 (`detect_stagnation`)、趋势计算 (`compute_trend`) | 无轮次间规则传递 |
| 评分器 | `gate/scorer.py` | 综合评分、收敛门禁 (`_evaluate_convergence`) | 评分结果不影响下轮 dispatch |
| 数据模型 | `gate/models.py` | `ConvergenceRound`、`GateVerdict`、`Finding` | `Finding.rule_id` 存在但未用于规则注入 |
| 门禁配置 | `gate/profiles.py` | 4 套预定义配置 (strict/standard/relaxed/audit) | 无轮次级别配置切换 |
| Dispatch 模式 | `schemas/task-dispatch.schema.yaml` | `applicable_rules` 字段含 `loading_strategy`、`quality_focus` | 无 `round_overrides` 或 `reinforcement_rules` |
| Cursor 适配器 | `adapters/cursor_adapter.py` | 构建时生成 `.mdc` 文件 | 仅构建时，无运行时 `.mdc` 创建 |
| 反馈系统 | `feedback.py` | `ProposalGenerator` 可建议 `.cursor/rules/*.mdc` | 未接入收敛循环 |
| 上下文配置 | `context_profiles.yaml` | 按任务类型定义 section 优先级和 token 预算 | 无按轮次变化的配置 |

---

## 2. 方案分析

### 方案 A：动态 `.mdc` 文件创建/修改

#### 2.1A 机制描述

在每轮收敛结束、Gate 返回 FAIL 后，由 L1 Stage Agent（或专用 Rule Injector 模块）根据 `GateVerdict.details` 和 `Finding` 列表，动态生成或修改 `.cursor/rules/` 下的 `.mdc` 文件，使下一轮 L3 Task Agent 在启动时自动加载这些规则。

**集成路径：**
```
Gate FAIL (scorer.py)
  → 提取 findings (Finding.rule_id, severity, description)
  → 调用 RuleInjector.generate_mdc(findings, round_num)
  → 写入 .cursor/rules/convergence-round-{N}.mdc (alwaysApply: true)
  → 下一轮 Task Agent 启动时 Cursor 自动加载该 .mdc
  → Gate PASS 后清理临时 .mdc 文件
```

**`.mdc` 文件示例：**
```yaml
---
description: "Round 2 convergence reinforcement — do NOT repeat these violations"
alwaysApply: true
---

## CONVERGENCE ROUND 2 — MANDATORY FIXES

Previous round findings that MUST be addressed:

1. **[blocker] F-001**: Missing error handling in auth middleware → MUST add try-catch
2. **[critical] F-003**: Test coverage below 80% for module X → MUST add tests
3. **[major] F-007**: Unused import in file Y → MUST remove

These rules are non-negotiable for this round.
```

#### 2.2A 可行性评分：4/5

#### 2.3A 优势

| 优势 | 说明 |
|------|------|
| **Cursor 原生支持** | `.mdc` 文件的 `alwaysApply: true` 确保每个 agent 都会加载，无需改变 agent 启动流程 |
| **不可覆写性强** | `.mdc` 由系统级别管理，agent 无法通过对话修改其内容 |
| **可审计** | 文件系统上有物理记录，可追溯每轮注入了什么规则 |
| **现有基础** | `CursorAdapter` 已有 `.mdc` 生成逻辑，`feedback.py` 的 `ProposalGenerator` 已能建议 `.mdc` target |
| **IDE 集成深度** | Cursor 规则系统对 `.mdc` 文件有一级支持，包括优先级、作用域控制 |

#### 2.4A 劣势

| 劣势 | 说明 |
|------|------|
| **文件 I/O 开销** | 每轮收敛需写文件，收敛结束需清理，涉及文件系统操作 |
| **并发风险** | 多个 wave 并行时，多个 agent 可能同时读取 `.mdc`，写入方需加锁 |
| **P5 违规风险** | 如果由 L1/L2 直接写文件，可能违反"调度器不实现"原则（P1）；需要专用 RuleInjector 模块或委托给 L3 |
| **清理复杂性** | 收敛结束后需可靠清理临时 `.mdc`，否则残留规则会污染后续工作流 |
| **平台耦合** | 仅对 Cursor IDE 有效；Codex、Claude Code、Copilot 适配器需要各自的等效方案 |

#### 2.5A 实现复杂度：中等

- **需新增模块**：`src/devolaflow/gate/rule_injector.py`（~100-150 行）
- **需修改**：`scorer.py` 在 `_evaluate_convergence` FAIL 路径中调用注入器；增加清理钩子
- **测试**：文件 I/O mock 测试 + 并发安全测试
- **预估工时**：2-3 天

#### 2.6A 运行时开销

- 文件写入：~1-5ms per `.mdc` 文件
- 文件清理：~1ms
- Cursor 规则重加载：取决于 IDE，通常 <100ms
- **总开销**：可忽略

---

### 方案 B：Dispatch 级 `applicable_rules` 升级（无文件 I/O）

#### 2.1B 机制描述

利用现有 `task-dispatch.schema.yaml` 中的 `applicable_rules` 字段，扩展其结构以支持轮次特定的规则注入。Gate FAIL 后，L1 Stage Agent 在构建下一轮的 TaskDispatch 消息时，将上一轮 findings 编码为 `applicable_rules.reinforcement` 块，直接嵌入 dispatch YAML 中。

**集成路径：**
```
Gate FAIL (scorer.py)
  → GateVerdict 包含 findings + round_num
  → L1 Stage Agent 构建下一轮 TaskDispatch
  → applicable_rules 中增加 reinforcement 块
  → L3 Task Agent 的 system prompt 中包含这些规则
  → 无文件写入
```

**Schema 扩展：**
```yaml
applicable_rules:
  loading_strategy: standard
  language: typescript
  task_type: code
  quality_focus: [security, error-handling]
  # === 新增字段 ===
  reinforcement:
    round: 2
    severity_floor: major  # 只传递 >= major 的 findings
    rules:
      - id: "F-001"
        severity: blocker
        mandate: "MUST add error handling to auth middleware"
        file: "src/middleware/auth.ts"
      - id: "F-003"
        severity: critical
        mandate: "MUST achieve >80% coverage for auth module"
    escalation_note: "Round 1 score: 72.3/85. These violations caused FAIL."
```

#### 2.2B 可行性评分：5/5

#### 2.3B 优势

| 优势 | 说明 |
|------|------|
| **零文件 I/O** | 完全通过 dispatch 消息传递，不写入任何物理文件 |
| **平台无关** | 不依赖 Cursor `.mdc`；适用于所有 IDE 适配器（Cursor、Codex、Claude Code、Copilot） |
| **上下文隔离兼容** | 完美符合 P2（Minimal Context）和 P5（Artifacts as Contracts）——规则嵌入 dispatch artifact |
| **精确控制** | 可按 severity 过滤、按文件过滤、按轮次递增强度 |
| **自然集成点** | `applicable_rules` 字段已存在于 schema 中，扩展是向后兼容的 |
| **Token 可控** | 可通过 `severity_floor` 控制注入量，避免 context 膨胀 |
| **无清理开销** | 规则只存在于 dispatch 消息中，不需要事后清理 |

#### 2.4B 劣势

| 劣势 | 说明 |
|------|------|
| **"软"强化** | 嵌入 dispatch 的规则本质是 system prompt 的一部分，理论上 agent 仍可忽略 |
| **上下文竞争** | reinforcement 规则占用 L3 的 ~8K token 预算，findings 多时可能挤压正常上下文 |
| **Schema 变更** | 需要修改 `task-dispatch.schema.yaml` 和 `lean-dispatch.yaml`，影响所有消费方 |
| **L1 编码负担** | L1 Stage Agent 需理解如何将 findings 转为 reinforcement rules，增加 L1 提示复杂度 |

#### 2.5B 实现复杂度：低

- **需修改 schema**：`task-dispatch.schema.yaml` 增加 `reinforcement` 字段定义（~20 行）
- **需修改 lean schema**：`lean-dispatch.yaml` 增加精简版 `reinforce` 字段（~10 行）
- **需新增函数**：`gate/reinforcement.py` 中的 `findings_to_reinforcement(findings, round_num, severity_floor)` (~50 行)
- **需修改 SKILL.md/CLAUDE.md**：在 Convergence Loop 节增加 reinforcement 指令
- **测试**：纯数据转换测试，无 I/O mock
- **预估工时**：1-2 天

#### 2.6B 运行时开销

- 数据转换：~0.1ms（Python 字典操作）
- Token 增量：~50-200 tokens per dispatch（取决于 findings 数量和 severity_floor）
- **总开销**：可忽略

---

### 方案 C：基于轮次的上下文配置切换

#### 2.1C 机制描述

在 `context_profiles.yaml` 中为收敛轮次定义渐进式配置升级策略。随着轮次增加，自动切换 section 优先级、token 预算分配、甚至 model tier，使后续轮次获得更强的"纪律约束"。

**集成路径：**
```
Gate FAIL at round N
  → 查询 context_profiles.yaml 的 convergence_escalation 配置
  → round 1: 使用 standard 配置
  → round 2: 提升 convergence_loop 和 gate_mechanism 为 critical
  → round 3: 切换 model_hint 到 quality tier
  → round 4 (if audit): 启用 full loading_strategy
```

**配置扩展示例：**
```yaml
convergence_escalation:
  strategy: progressive
  round_overrides:
    2:
      section_priority_overrides:
        rationalization_prevention: critical
        convergence_loop: critical
      loading_strategy_override: full
      compression_intensity: minimal
    3:
      model_hint_override: quality
      section_priority_overrides:
        rationalization_prevention: critical
        convergence_loop: critical
        gate_mechanism: critical
      token_budget_increase_pct: 20
    4:
      model_hint_override: quality
      loading_strategy_override: full
      token_budget_increase_pct: 40
```

#### 2.2C 可行性评分：3/5

#### 2.3C 优势

| 优势 | 说明 |
|------|------|
| **零文件 I/O** | 配置是静态的，运行时只是读取不同的配置段 |
| **渐进式强化** | 自然地随轮次升级约束力度，符合 P4（Bounded Retry）的精神 |
| **全局一致** | 所有任务类型共享相同的升级策略，减少维护负担 |
| **Model 升级** | 后期轮次可自动使用更强的模型，提高修复成功率 |

#### 2.4C 劣势

| 劣势 | 说明 |
|------|------|
| **不够精确** | 只能做"全局加压"，无法针对具体 findings 进行精准强化 |
| **配置膨胀** | 为每个轮次定义覆盖配置，`context_profiles.yaml` 已有 1200+ 行，再增加会加重维护 |
| **效果间接** | 提升 section 优先级或 model tier 不等于 agent 会修复特定问题 |
| **与 findings 脱耦** | 不携带"上一轮到底哪里出了问题"的具体信息 |
| **成本增加** | model tier 升级意味着更高的 API 调用成本 |

#### 2.5C 实现复杂度：低-中

- **需修改**：`context_profiles.yaml` 增加 `convergence_escalation` 顶级 section
- **需修改**：`task_adaptive_selector.py`（如存在）读取 round_overrides
- **需新增**：`gate/escalation_config.py` 将 round_num 映射到 profile overrides（~60 行）
- **测试**：配置解析 + override 合并测试
- **预估工时**：1.5-2 天

#### 2.6C 运行时开销

- 配置查询：~0.05ms
- **总开销**：可忽略

---

### 方案 D：Dispatch 内联 System Prompt 注入（混合方案）

#### 2.1D 机制描述

结合方案 B 的 dispatch 级传递和方案 A 的"不可覆写"诉求，在 dispatch 消息中增加一个 `system_reinforcement` 字段，由宿主 IDE 解释为等效于 `.mdc` `alwaysApply: true` 的系统级指令——即在 agent 的 system prompt 最前面注入，而非作为用户消息的一部分。

**关键区别**：普通 dispatch 内容在 user prompt 中传递，agent 可选择性忽略；而 system_reinforcement 由 IDE 插入到 system prompt，优先级等同于 `.mdc` 规则。

**集成路径：**
```
Gate FAIL
  → findings → reinforcement_rules
  → 写入 dispatch.system_reinforcement (YAML 字段)
  → IDE 适配器读取 system_reinforcement
  → 注入 agent system prompt (与 .mdc 同级)
  → agent 无法通过对话覆写
```

#### 2.2D 可行性评分：2/5

#### 2.3D 优势

| 优势 | 说明 |
|------|------|
| **不可覆写性最强** | 等效于 system prompt 级别的硬约束 |
| **无文件 I/O** | 通过 dispatch 消息传递 |
| **理论上最优** | 如果 IDE 支持，是"无文件但不可覆写"的理想答案 |

#### 2.4D 劣势

| 劣势 | 说明 |
|------|------|
| **IDE 支持未知** | Cursor 目前无公开 API 允许外部程序动态注入 system prompt 内容 |
| **依赖 IDE 适配** | 每个 IDE 需实现 system_reinforcement → system prompt 的转换 |
| **高实现风险** | 如果 IDE 不支持，整个方案不可行 |
| **架构侵入性大** | 需要修改所有 4 个 adapter，且需要 IDE 侧配合 |

#### 2.5D 实现复杂度：高

- 需要 IDE 侧 API 支持（当前不确定）
- 需修改所有 adapter
- **预估工时**：不确定（取决于 IDE 能力）

#### 2.6D 运行时开销

- 与方案 B 相同：可忽略

---

### 方案 E：反馈-收敛桥接（将 `feedback.py` 接入收敛循环）

#### 2.1E 机制描述

利用已有的 `FeedbackAnalyzer.detect_recurring_violations()` 和 `ProposalGenerator`，在收敛循环中实时运行反馈分析。当 Gate FAIL 时，先运行反馈分析，将 `Proposal` 转化为下一轮 dispatch 的 reinforcement rules（方案 B）或临时 `.mdc`（方案 A）。

这不是独立方案，而是方案 A/B 的**增强层**——提供更智能的规则生成。

**集成路径：**
```
Gate FAIL
  → FeedbackCollector.collect_from_gate(verdict)
  → FeedbackAnalyzer.detect_recurring_violations(learnings)
  → FeedbackAnalyzer.detect_convergence_stagnation(rounds)
  → ProposalGenerator.generate_proposals(analysis)
  → Proposals → reinforcement rules (方案 B) 或 .mdc (方案 A)
```

#### 2.2E 可行性评分：4/5（作为增强层）

#### 2.3E 优势

- 复用现有代码（`feedback.py` 的 3 个类已完全实现）
- 带有置信度筛选（`CONFIDENCE_FLOOR = 0.7`）避免低质量规则注入
- 带有作用域锁定（`LOCKED_FILES`）避免修改核心文件
- 每工作流最多 3 个 proposal 的安全限制

#### 2.4E 劣势

- `feedback.py` 当前依赖 `learnings.py` 的持久化历史，收敛轮次间可能没有足够历史
- 需要在收敛循环中增加 learnings 写入步骤

---

## 3. 对比矩阵

| 维度 | 方案 A (动态 .mdc) | 方案 B (Dispatch 强化) | 方案 C (配置切换) | 方案 D (System Prompt) | 方案 E (反馈桥接) |
|------|:---:|:---:|:---:|:---:|:---:|
| **可行性评分** | 4/5 | **5/5** | 3/5 | 2/5 | 4/5 (增强) |
| **无文件 I/O** | ❌ 需要 | **✅** | **✅** | **✅** | 取决于搭配 |
| **不可覆写性** | ★★★★★ | ★★★☆☆ | ★★☆☆☆ | ★★★★★ | 取决于搭配 |
| **精准度** | ★★★★☆ | **★★★★★** | ★★☆☆☆ | ★★★★★ | ★★★★★ |
| **平台通用性** | ★☆☆☆☆ | **★★★★★** | ★★★★★ | ★☆☆☆☆ | ★★★★★ |
| **实现复杂度** | 中 | **低** | 低-中 | 高 | 低 (桥接) |
| **Token 开销** | 0 (系统级) | 50-200 | 0-300 | 0 (系统级) | 同搭配方案 |
| **P1-P5 兼容性** | 需小心 P1 | **完全兼容** | **完全兼容** | 完全兼容 | **完全兼容** |
| **预估工时** | 2-3 天 | **1-2 天** | 1.5-2 天 | 不确定 | 0.5-1 天 |

---

## 4. 关键问题回答

### 4.1 "是否存在不使用实体文件交互的合理方式？"

**是的，方案 B（Dispatch 级 `applicable_rules` 升级）是完全不依赖实体文件的合理方案。**

理由：
1. `task-dispatch.schema.yaml` 的 `applicable_rules` 字段是为规则传递而设计的现有基础设施
2. 规则通过 dispatch 消息传递，属于 P5 所定义的"artifact 作为合约"的正统实现
3. 与 P2（Minimal Context）兼容——reinforcement rules 占用 token 可控
4. 不依赖任何特定 IDE 的文件监控机制

**但存在一个权衡**：Dispatch 级规则的"不可覆写性"弱于 `.mdc`。`.mdc` 是 Cursor system prompt 级别的注入，agent 无法通过对话修改；而 dispatch 级规则本质是用户消息的一部分，理论上 agent 可以"选择性忽略"。

**缓解措施**：
- 在规则文本中使用强制性措辞（"MUST"、"MANDATORY"、"NON-NEGOTIABLE"）
- 配合 SKILL.md/CLAUDE.md 中的 convergence 章节说明"reinforcement 规则不可违反"
- 在下一轮 Gate 评估时显式检查上轮 findings 是否已修复

### 4.2 `.mdc` 运行时动态创建是否可行？

**技术上可行，但有限制：**

1. **Cursor 的 `.mdc` 加载机制**：Cursor 会监控 `.cursor/rules/` 目录的文件变化，新文件会被自动加载。因此运行时创建 `.mdc` 是有效的。
2. **`alwaysApply: true`**：确保文件一旦存在就会被注入所有 agent 的上下文。
3. **限制**：`.mdc` 文件的生效时机取决于 Cursor 的文件监控刷新频率。在快速连续的收敛轮次中，可能存在竞态条件。

### 4.3 多轮迭代中行为漂移的根本原因

分析 `_evaluate_convergence()` 的流程后发现：

```
Round N Gate FAIL
  → GateVerdict (包含 composite_score, rationale, findings)
  → L1 Stage Agent 决定 "Retry"
  → L1 dispatch 下一轮任务
  → L3 Task Agent 收到新的 dispatch（不含上轮 findings）← 断裂点
  → L3 可能重复相同错误
```

**断裂点在 L1→L3 的 dispatch 中**：当前 `TaskDispatch` 的 `predecessor_artifacts` 只传递 path + summary，不传递上轮 Gate 的具体 findings。L3 Task Agent 对"上一轮为什么失败"一无所知。

---

## 5. 推荐方案

### 5.1 首选：方案 B + E 组合（Dispatch 规则注入 + 反馈桥接）

**推荐在 v5.1.0-pre 中实现方案 B，并将方案 E 作为增强层。**

理由：
1. **零文件 I/O**——直接回答用户"是否存在不使用实体文件交互的合理方式"
2. **平台通用**——不绑定 Cursor，所有 4 个 adapter 都能受益
3. **实现成本最低**——扩展现有 schema + 编写数据转换函数
4. **风险最低**——向后兼容，`reinforcement` 字段为可选
5. **与 P1-P5 完全兼容**——规则通过 artifact（dispatch 消息）传递

### 5.2 次选：方案 A 作为 Cursor 特化增强

如果方案 B 的"软强化"在实践中不足以防止行为漂移，可追加方案 A 作为 Cursor 特定的硬强化层。这需要评估方案 B 上线后的实际收敛效果。

### 5.3 方案 C 作为独立正交优化

方案 C（配置切换）与方案 B 不冲突，可作为独立优化项：后期轮次使用更强的模型、更多的上下文预算。建议作为 v5.1.0 正式版的次优先级特性。

### 5.4 不推荐方案 D

方案 D（System Prompt 注入）依赖不确定的 IDE 能力，实现风险过高，不建议纳入 v5.1.0 规划。

---

## 6. 推荐实现路径（方案 B + E）

### 6.1 Schema 变更

**文件**：`schemas/task-dispatch.schema.yaml`

在 `applicable_rules.children` 下增加：
```yaml
reinforcement:
  type: object
  optional: true
  description: "Round-specific rule injection from previous convergence failures."
  children:
    round: { type: int, description: "Current convergence round number." }
    severity_floor: { type: string, description: "Minimum severity to include (blocker|critical|major)." }
    prior_score: { type: number, description: "Previous round composite score." }
    target_score: { type: number, description: "Gate threshold to achieve." }
    rules:
      type: list
      description: "Specific findings that MUST be addressed."
      item_fields:
        id: { type: string }
        severity: { type: string }
        mandate: { type: string, description: "Imperative instruction (MUST/SHALL)." }
        file: { type: string, optional: true }
    escalation_note: { type: string, optional: true }
```

### 6.2 核心模块

**新文件**：`src/devolaflow/gate/reinforcement.py`（~80 行）

```python
def findings_to_reinforcement(
    findings: list[Finding],
    round_num: int,
    prior_score: float,
    target_score: float,
    severity_floor: str = "major",
) -> dict:
    """Convert gate findings into a dispatch reinforcement block."""
    ...

def merge_reinforcement_into_dispatch(
    dispatch: dict,
    reinforcement: dict,
) -> dict:
    """Inject reinforcement into an existing dispatch's applicable_rules."""
    ...
```

### 6.3 反馈桥接

**修改**：`src/devolaflow/feedback.py`

在 `ProposalGenerator` 中增加 `generate_reinforcement()` 方法，复用 `detect_recurring_violations()` 和 `detect_convergence_stagnation()` 的分析结果，输出方案 B 格式的 reinforcement 块。

### 6.4 SKILL.md / CLAUDE.md 更新

在 Convergence Loop 章节增加：

```
Round N (N > 1):
  ...
  3b. DISPATCH includes applicable_rules.reinforcement from Gate findings
  ...
  L3 Task Agent MUST address all reinforcement.rules before other work.
  Failure to address reinforcement rules = automatic blocker finding in next gate.
```

### 6.5 Token 预算影响

| 轮次 | reinforcement 预估 tokens | L3 总预算 | 剩余可用 |
|------|:---:|:---:|:---:|
| Round 1 | 0 (无 reinforcement) | ~8000 | ~8000 |
| Round 2 | ~80-150 | ~8000 | ~7850-7920 |
| Round 3 | ~120-250 | ~8000 | ~7750-7880 |
| Round 4 | ~200-350 | ~8000 | ~7650-7800 |

影响在 5% 以内，完全可接受。

---

## 7. 风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| Agent 忽略 dispatch 级 reinforcement | 中 | 中 | 使用 MUST/MANDATORY 措辞；Gate 显式检查上轮 findings 修复情况 |
| reinforcement 规则太多导致 context 膨胀 | 低 | 中 | `severity_floor` 控制 + 最多 5 条规则限制 |
| Schema 变更破坏现有消费方 | 低 | 高 | `reinforcement` 字段标记为 optional，向后兼容 |
| 反馈分析在短期收敛中数据不足 | 中 | 低 | fallback 到直接 findings 转换，不依赖历史数据 |

---

## 8. 结论

1. **动态 `.mdc` 创建（方案 A）**技术上可行且强化力度最高，但有文件 I/O 和平台绑定限制。
2. **Dispatch 级规则注入（方案 B）**是"不使用实体文件交互"的最佳答案，可行性最高、成本最低、平台通用。
3. **推荐 v5.1.0-pre 优先实现方案 B + E 组合**，在收敛循环的 Gate FAIL → 下轮 Dispatch 路径中注入 reinforcement 规则。
4. 如果方案 B 的"软强化"不足，可后续追加方案 A 作为 Cursor 特定的硬强化层。
5. 方案 C（配置切换）可作为独立正交优化在 v5.1.0 正式版中实现。
