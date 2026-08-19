# 推文深度分析与 DevolaFlow 工作流性能提升报告

> 分析日期: 2026-04-21 (v2 refresh) | DevolaFlow 当前版本: v7.8.0 | 目标版本: v8.0.0+ (8.0.0 → 8.1.0 pre-release → 8.2.0 final)
> v2 补充更新: 2026-04-21 — 3 个版本周期后的现实校准 + Karpathy 仓库星标 3.06× 增长 + NineS 深度分析

---

## 0. v2 校准说明 (2026-04-21 Refresh)

### 0.1 三个版本周期的现实

本报告 v1 (2026-04-21 早) 提议 v7.8.0 实施 4.1-4.14 共 14 项提升。实际上 v7.6.0 → v7.8.0 三个版本周期的工程容量全部投入了 **repo-init 子系统** (v7.6 redesign + lifecycle hooks; v7.7 interview + memory wiring; v7.8 canonical manifest enforcement + doctor)，与 Harness/Behavioral/Ratchet 三大维度的工作正交。结果: 截至 v7.8.0 (2026-04-21 发布), 报告中 4.1-4.14 共 14 项提议**没有任何一项落地**:

| 维度 | 提议项 | 当前状态 | 证据 |
|------|--------|----------|------|
| Harness | 4.3 token budget circuit breaker | 不存在 | `src/devolaflow/gate/` 无 `budget.py` |
| Harness | 4.4 cycle detection middleware | 不存在 | `src/devolaflow/gate/` 无 `cycle_detector.py` |
| Harness | 4.9 deterministic fence expansion | 部分 | `reinforcement.py` 存在但无 `fence_to_instruction()` |
| Harness | 4.10 verification ladder formalization | 不存在 | `scorer.py` 无 `evaluate_ladder()` |
| Ratchet | 4.11 monotonic ratchet guarantee | 不存在 | `src/devolaflow/gate/` 无 `ratchet.py` |
| Behavioral | 4.12 L3 behavioral guidelines injection | 不存在 | `schemas/lean-dispatch.yaml` 无 `behavioral_guidelines` 字段; 无 `behavioral-guidelines.md` |
| Behavioral | 4.13 overcomplexity detector | 不存在 | `src/devolaflow/gate/` 无 `complexity_detector.py` |
| Behavioral | 4.14 automatic AC generation | 不存在 | `src/devolaflow/` 无 `ac_generator.py` |
| Context | 4.1, 4.2, 4.6 layered/directed/abstractive compaction | 不存在 | `compressor.py` 仅有原有 INTENSITY_TIERS |
| Other | 4.5, 4.7, 4.8 entropy GC / agent legibility / unified session | 不存在 | 无相关模块 |

辅助证据: `git log --oneline -8` 显示 v7.6.0 (`1a4f1ee`) / v7.7.0 (`828b9ff`) / v7.8.0 (`17d2a14`) 三个 feat commit 主题均为 `feat(repo-init):`, 无任何 gate / compressor / behavioral 相关提交。`CHANGELOG.md` 至 v7.5.0 截止 (2026-04-20), v7.6/v7.7/v7.8 三段亦缺失 — 进一步印证容量错配。

**结论**: 14 个提议项全部进入 v8.0.0 + 候选清单。

### 0.2 Karpathy 仓库 8 天演化

- 2026-04-13 快照 (`.local/research/karpathy_skills_analysis.md` line 17): **22,770 stars**, 0 forks, CLAUDE.md 4 准则 (Think Before Coding / Simplicity First / Surgical Changes / Goal-Driven Execution)
- 2026-04-21 快照: **69,825 stars (+47,055 net, +207%, 3.06× 增长)**, 0 forks, CLAUDE.md 4 准则**字节级未变化**
- 信号解读:
  1. **病毒扩散加速** (8 天 +47K stars) — 行为准则注入仍是开发者的高频痛点, 验证 4.12 提议项的市场需求
  2. **artifact 稳定** (CLAUDE.md 0 字节变化) — 4 准则在大规模社区检验下达到稳态, 适合作为 DevolaFlow `behavioral-guidelines.md` 的 v1 模板基线
  3. **0 forks** (单文件项目) — 印证 Harness Engineering 推论: 简洁、稳定、可复制的 prompt 资产比"完整框架"更易传播; DevolaFlow 应延续"小核心 SKILL.md + 渐进式 references"的定位
  4. **biweekly 跟踪频率合适** — `karpathy_skills_analysis.md` §tracking_recommendation 中 `periodic_vs_active: "active_tracking with biweekly checks is sufficient"` 的判断在 8 天 3.06× 增长后仍然成立 (内容稳定, 仅星标波动)

### 0.3 NineS 深度分析摘要

NineS 命令成功执行 (exit 0), `nines -f json analyze --target-path src/devolaflow --depth deep --agent-impact --keypoints` (artifacts 在 `.local/research/v8.0.0_nines_artifacts/analysis_report.json`)。规模指标: 64 Python 文件 / 12,433 LOC / 384 函数 / 89 类 / 平均圈复杂度 3.83 / 473 个知识单元 / 9 个包。141 个 finding 中 1 个 ERROR + 11 个 WARNING (均为 `complexity` 类别), 其余 129 个为 `info` (summary + dependencies)。

**NineS 12 个非 info finding (按严重度 + 行为影响排序)**:

| # | NineS ID | 严重度 | 复杂度 | 文件:行 | 函数 | v8.0.0 关联 |
|---|----------|--------|--------|---------|------|--------------|
| 1 | `[NineS:CC-70f79c-0000]` | **error** | **22** | `adapters/data_driven.py:117` | `DataDrivenAdapter._apply_transform` | 4.6 抽象摘要前置重构 |
| 2 | `[NineS:CC-39ab83-0001]` | warn | 15 | `compressor.py:1187` | `summarise_predecessor` | **4.1 / 4.2 直接重构入口** (分层压缩 + 定向压缩) |
| 3 | `[NineS:CC-70f79c-0001]` | warn | 15 | `adapters/data_driven.py:171` | `DataDrivenAdapter._split_by_heading` | 4.6 抽象摘要前置重构 |
| 4 | `[NineS:CC-631b33-0000]` | warn | 14 | `learnings.py:202` | `load_relevant_learnings` | 4.5 熵管理基础 |
| 5 | `[NineS:CC-0c2755-0000]` | warn | 13 | `template_engine/runtime.py:167` | `select_stages_for_runtime` | repo-init 工作流性能 |
| 6 | `[NineS:CC-631b33-0001]` | warn | 12 | `learnings.py:522` | `decay_confidence` | 4.5 熵管理 |
| 7 | `[NineS:CC-f1cb7a-0000]` | warn | 12 | `lifecycle/format_on_edit.py:38` | `_collect_violations` | lifecycle hooks 可读性 |
| 8 | `[NineS:CC-89508c-0000]` | warn | 12 | `nines/researcher.py:424` | `refresh_reference_dependency` | NineS 自适配 |
| 9 | `[NineS:CC-448821-0002]` | warn | 12 | `task_adaptive_selector.py:585` | `main` | CLI 重构 |
| 10 | `[NineS:CC-39ab83-0000]` | warn | 11 | `compressor.py:945` | `extract_named_entities` | 4.1 分层压缩前置 |
| 11 | `[NineS:CC-448821-0000]` | warn | 11 | `task_adaptive_selector.py:392` | `select_context` | 4.6 抽象摘要前置 |
| 12 | `[NineS:CC-448821-0001]` | warn | 11 | `task_adaptive_selector.py:543` | `apply_round_escalation` | 4.11 ratchet 集成点 |

**Key Points** (NineS `metrics.key_points`):

- `[NineS:kp-find-3de75952]` (behavioral_shaping): "Repository contains 0 Agent-facing artifact(s) across 0 mechanism(s)" — **重要观察**: NineS 把 `src/devolaflow/` (Python 源码) 视作纯工程 artifact, 0 个 agent-facing 文件。这是因为 SKILL.md / references / examples 全部位于 `workflow-system/agent/` 而非 `src/`。**v8.0.0 行动项**: 在 SI-2 阶段补充一次 `nines analyze --target-path workflow-system/agent` 以获取 agent-facing 表面的独立评分 (并非本次 refresh 范围)。
- `[NineS:kp-eng-bda76927]` (engineering): "Function `DataDrivenAdapter._apply_transform` has cyclomatic complexity 22" — 与 finding #1 一致, 是当前唯一 ERROR 级别的复杂度热点。
- `[NineS:kp-summary-69ff6fdd]` (engineering): "Analysis covered 64 Python files and 65 total files. 473 knowledge units extracted."

**审计警告** (advisory only, 不阻断): NineS audit_report 报 `finding_id_namespace` warn — 当前 finding ID 形如 `SUM-914ca1-0000` 不符合 NineS v3.3.0 的 `^[A-Z]+-[0-9a-f]{8}-[0-9]+$` 命名空间格式 (短哈希位数差异)。这是 NineS 自身 schema 版本演进遗留问题, 不影响 v8.0.0 决策。

**对 v8.0.0 patch 排序的关键启示** (详见 §7.2):
1. **`compressor.py` 已是热点重构靶心** — `summarise_predecessor` cc=15 + `extract_named_entities` cc=11 同时命中 4.1 (分层压缩) 与 4.2 (定向压缩) 的预期改造区域 → 这两项可以"借势"在 v8.0.0 早期 patch 落地, 复杂度分数会同步改善。
2. **`task_adaptive_selector.py` 三个 cc≥11 函数** (`select_context` / `apply_round_escalation` / `main`) 是 4.11 (ratchet) 与 4.6 (抽象摘要) 的天然集成点; ratchet 改造时强制拆分 `apply_round_escalation` 可一次同时降低复杂度 + 引入单调约束。
3. **`adapters/data_driven.py:_apply_transform` cc=22** 是唯一 ERROR — 不在 14 项原始提议覆盖范围内, 但应在 v8.0.0 周期内补一个独立"小净化" patch (CC-cleanup), 否则会持续拖低 NineS 自评分。
4. **`learnings.py` 两个高复杂度函数** (`load_relevant_learnings` cc=14, `decay_confidence` cc=12) 与 4.5 (熵管理 / GC) 设计目标深度耦合 — 4.5 落地天然需要重构这两个函数。
5. **agent-facing artifact 计为 0** 是 v8.0.0 的隐性 gap: §7 路径门控应包含 "在 v8.1.0 self-eval 阶段对 `workflow-system/agent/` 单独跑一次 NineS analyze" 的附加要求。

---

## 1. 推文内容深度分析

### 1.1 推文一: Thariq (trq212) — Session 管理与 1M 上下文

**来源**: Anthropic 工程师 Thariq, 2026-04-15 发布, 关于 Claude Code 在 1M 上下文窗口下的 Session 管理策略。

#### 核心洞察一: 上下文腐烂 (Context Rot)

Thariq 提出了一个被广泛忽视的反直觉现象: **更大的上下文窗口并不等于更好的性能**。随着 context 增长，模型的注意力 (attention) 会分散到越来越多的 token 上，而早期不相关的内容会持续"污染"对当前任务的判断。

这一论断在 DevolaFlow 的语境下有直接对应:
- `compressor.py` 中的 `INTENSITY_TIERS` 本质上是对 context rot 的局部缓解 — 通过移除 `filler_phrases`、`hedging_language` 等低信息密度内容减少噪声
- 但 DevolaFlow 目前缺少对 **时间维度** 上的 context rot 的感知: 系统不知道一个 predecessor artifact 是 5 轮前的还是当前轮次的，所有 `pred` 条目在 dispatch 中被同等对待

关键引用: "Don't use approach A, the foo module doesn't expose that — go straight to B." — 这揭示了一个本质问题: **失败路径的残留是 context rot 最有害的形式**，因为它不仅占用 token 预算，还会让模型产生"已尝试但失败了"的锚定偏差。

#### 核心洞察二: 五种 Session 管理策略的选择框架

| 策略 | 信息保留 | 人类介入 | 适用场景 |
|------|----------|----------|----------|
| **Continue** | 100% (含噪声) | 零 | 任务连续且上下文健康时 |
| **Rewind** | 精确裁剪 | 低 | 方向错误需回退到已知好状态 |
| **/clear** | 0% (人类重写) | 高 | 全新不相关任务 |
| **Compact** | 有损摘要 | 零 | 上下文过长但任务延续时 |
| **Subagents** | 隔离执行 | 零 | 产生大量中间输出的子任务 |

**关键架构洞察**: 这五种策略暗示了一个隐含的 **Session 状态机** — 每个策略对应状态转换。DevolaFlow 的 P5 (Artifacts as Contracts) 天然支持 "Subagents" 模式（L3 Task Agent 的上下文隔离），但缺少对 Rewind 和 Directed Compact 的支持。

#### 核心洞察三: 定向压缩 (Directed Compaction)

`/compact focus on the auth refactor, drop the test debugging` — 这不是简单的"压缩"，而是 **带语义指引的选择性遗忘**。这要求压缩引擎能够:
1. 理解内容的语义主题分布
2. 接受外部指令决定保留/丢弃的主题
3. 在保留主题上进行高保真摘要，在丢弃主题上进行极致压缩

DevolaFlow 当前的 `compress_message()` 是纯模式匹配的确定性压缩 — 它按 `DROP_LIST` 中的词汇类别操作，不具备语义层面的选择性保留能力。`summarise_predecessor()` 的 `retrieval_query` 参数（v7.2.5 P-05）是最接近的已有机制，但它仅在 section 排名层面生效，不涉及 section 内部的选择性摘要。

#### 核心洞察四: 压缩时机悖论

"Context rot happens at worst time: when compacting, model is at its least intelligent point due to context rot."

这是一个深刻的 meta-level 困境: 需要压缩时恰恰是模型能力最差的时候。解法有两个方向:
1. **提前压缩** (proactive compaction) — 在 context rot 尚未严重时就启动压缩
2. **委托压缩** (delegated compaction) — 用独立的、干净上下文的子 agent 来执行压缩

DevolaFlow 的 `task_adaptive_selector.py` 在 dispatch 组装时已做了优先级排序和预算分配（提前裁剪），但这是静态的预构建阶段行为，不是运行时的动态压缩响应。

### 1.2 推文二: SaitoWu — Harness Engineering 的本质

**来源**: SaitoWu (吴新, Podwise 创始人), 2026-04-18 发布, 引用 OpenAI 的 Ryan Lopopolo 发表的 Harness Engineering 博客，并加入 Louis Wang 的架构分析。

#### "代码已经免费了" — 范式转移的核心

SaitoWu 的核心论断 "代码已经免费了 (code is free), 实施不再是瓶颈, 人类真正的价值是 steering (指导)" 标志着软件工程从 **实现驱动** 到 **指导驱动** 的范式转移。

这意味着:
- **工程师的角色从"写代码"变为"设计约束"** — 编写确定性栅栏、定义验证阶梯、维护代码库的 agent 可读性
- **吞吐量改变合并哲学** — 当纠正成本低而等待成本高时，减少阻塞性门控
- **仓库知识成为唯一的真实来源 (single source of truth)** — Slack 讨论、脑中知识、口头约定对 agent 不存在

#### OpenAI 的 Harness Engineering 实践: 零人类代码实验

1M 行代码，1500 个 PR，5 个月，约 3.5 PR/工程师/天 — 这组数据的意义不在于规模，而在于验证了一种全新的工程模式:
- **AGENTS.md 作为目录而非百科全书**: 渐进式披露 — 小而稳定的入口点加上指向深层源的指针。巨大的指令文件会挤占实际任务的空间。DevolaFlow 的 SKILL.md（< 500 行，SF-1 上限）+ references/*.md（≤ 1000 行，8 个专题文件）+ examples/*.md（≤ 1600 行，3 个示例文件）的三层渐进式披露架构天然契合这一理念
- **确定性栅栏 (Deterministic Fences)**: 机械验证（自定义 linter、结构性测试）让构建失败。Prompt 是建议; 栅栏是结构性的。当被违反时，将错误重写为修复指令注入到 agent 上下文
- **熵管理 / 垃圾回收**: 定期运行的"文档园艺"和清理 agent 扫描偏差、更新质量等级、发起重构 PR。类似代码库技术债的 GC 机制

#### Louis Wang 的四大架构原语

Louis Wang 的分析将 Harness Engineering 提炼为四个架构原语，每个在 DevolaFlow 中都有对应（但完成度不同）:

**1. 确定性栅栏 (Deterministic Fences)**
- DevolaFlow 已有: `gate/` 模块的多维评分（`scorer.py:DEFAULT_DIMENSION_WEIGHTS`）、`compressor.py` 的 `BYPASS_CONDITIONS` + `INJECTION_PATTERNS` 安全栅栏、`lifecycle/` 的 dispatch 验证
- 缺失: 缺少 "violation → remediation instruction injection" 闭环。当前 `reinforcement.py` 将 findings 转为 mandates，但这是 gate 发现到下一轮 dispatch 的注入，不是 build-failure 到 agent-context 的注入

**2. 验证阶梯 (Verification Ladder)**
- 6 级管道: 静态分析 → linters → 编译 → 单元测试 → 无头 UI → LLM 审计
- DevolaFlow 已有: `GateInput` 模型的 `build_status` + `test_results` + `lint_status` + `review_findings` + `acceptance_criteria_results` 覆盖了大部分层级
- 缺失: 层级之间没有显式的短路逻辑（如果 lint 失败就不该运行 LLM 审计），验证顺序未形式化为管道

**3. 外化状态与上下文压缩 (Externalized State & Context Compaction)**
- "Context window = CPU register; filesystem + git = persistent storage"
- DevolaFlow 已有: P5 (Artifacts as Contracts) + JSONL learnings + lean YAML interchange + `assert_dispatch_layout()` 缓存前缀稳定性
- 缺失: 没有显式的"register ↔ storage"溢出/换入机制，没有 session state model 将散布在 learnings、lifecycle、schema 中的状态统一抽象

**4. 循环终止保障 (Loop Termination Guarantees)**
- Budget-aware runtimes + cycle detection + durable execution checkpointing
- DevolaFlow 已有: 模板的 `max_iterations` + `until` + `on_exhaustion: escalate`; gate 的 `max_rounds` → ESCALATE; report status routing (`NEEDS_CONTEXT → retry, BLOCKED → escalate`)
- 缺失: **无 token 预算断路器** (per-task token budget circuit breaker); **无循环检测中间件** (semantic similarity of consecutive tool calls); **无持久执行检查点**

#### 四个框架的横向对比

Louis Wang 引用了四个框架: Autoresearch (ratchet loop), Ralph Loop (filesystem-first), Superpowers (TDD enforcement), GSD (parallel wave orchestration)。**GSD 与 DevolaFlow 架构最相似** — 两者都采用 wave 级并行编排。但 GSD 有 DevolaFlow 尚未实现的:
- Parallel wave 的 token 预算共享
- Build-failure → agent-context 的 remediation instruction 注入
- 文档新鲜度跟踪 (documentation freshness tracking)

### 1.3 推文三 (补充参考): forrestchang/andrej-karpathy-skills — Karpathy 的 LLM 编码准则与 AutoResearch 模式

**来源**: forrestchang/andrej-karpathy-skills 仓库 (69,634 stars), 2026-01-27 创建, 2026-04-20 最后更新。单日最高 5,828 stars (2026-04-13), 位列 GitHub Trending #2。同日 GitHub 趋势榜前五中有四个是 Claude Code 生态工具 — 这是平台成熟度的信号: 社区构建优化工具的速度超过 Anthropic 自身的迭代速度。

辅助来源: Karpathy 的 AutoResearch 项目 (2026-03-07, 630 行 Python); Multica 平台 (multica-ai/multica, 12,681 stars)。

#### 四项准则的深度解析与 DevolaFlow 映射

**准则一: Think Before Coding — "不要假设。不要隐藏困惑。暴露权衡。"**

核心观察: LLM 经过训练后倾向于自信断言 (confidently assertive)，会用看似合理的假设填补信息空白并直接执行。Karpathy 的准则要求 agent 在不确定时停下来 — 明确说明假设、呈现多种解读、在更简单的方案存在时反向推荐、在困惑时命名困惑点并提问。

DevolaFlow 映射:
- **已有对应**: P3 Structured Messages 禁止层间自由自然语言。`TaskDispatch` 的 `goal` + `assumptions` + `acceptance_criteria` 字段强制 L2 Wave Agent 在 dispatch 时显式化假设和验收标准
- **关键缺口**: P3 约束的是 **层间通信格式**，而非 **L3 Task Agent 的内部行为**。当 L3 agent 收到 dispatch 后，它的编码行为不受任何"先思考再动手"的准则约束。DevolaFlow 没有向 L3 agent 注入行为准则 (behavioral guidelines) 的机制 — dispatch 告诉 agent "做什么"和"验收标准是什么"，但不告诉 agent "如何思考"

**准则二: Simplicity First — "解决问题的最少代码。不做投机性设计。"**

核心观察: LLM 从训练数据中模式匹配到复杂的企业级代码，倾向于产出 5 倍于实际需要的代码量 — 不必要的抽象、未请求的"灵活性"、单次使用场景的过度工程。自检标准: "一个高级工程师会说这过于复杂吗？"

DevolaFlow 映射:
- **已有对应**: Quick Action Decision table 按 trivial/simple/standard/complex 四级匹配仪式感。`context_profiles.yaml` 中 `trivial_fix` profile 将大量 SKILL.md section 标记为 `skip`，降低 agent 获取复杂模式的机会
- **关键缺口**: 没有 **过度复杂检测器** (overcomplexity detector)。Gate 的多维评分 (`scorer.py:DEFAULT_DIMENSION_WEIGHTS`) 评估测试通过率、代码审查、架构合理性和 benchmark，但不评估"解决方案是否过于复杂"。一个 agent 可能产出 500 行完全正确、测试全过、架构合理但本可用 50 行解决的代码，gate 会给出高分

**准则三: Surgical Changes — "只碰必须碰的。只清理你自己造成的混乱。"**

核心观察: LLM 倾向于"顺便改进"相邻代码、注释和格式。测试标准: 每一行改动都应该能直接追溯到用户的请求。

DevolaFlow 映射:
- **已有对应**: P5 Artifacts as Contracts + `lifecycle/validate_owned_files.py` 的 `check_file_ownership` 钩子直接实现了手术精度。L3 Task Agent 被限制在 `owned_files` 列表内操作，越界操作在 strict 模式下被拒绝
- **关键缺口**: 文件所有权检查是 **文件级别** 的精度，不是 **diff 行级别** 的精度。一个 agent 拥有 `src/devolaflow/compressor.py` 的写权限后，可以在修复目标 bug 的同时"顺便"重构 500 行无关代码。`check_file_ownership` 只验证"是否允许写这个文件"，不验证"写入的变更是否与 task goal 相关"

**准则四: Goal-Driven Execution — "定义成功标准。循环直到验证通过。"**

核心观察: Karpathy 的关键洞见 — "LLMs are exceptionally good at looping until they meet specific goals. Don't tell it what to do, give it success criteria and watch it go." 将命令式任务转化为声明式目标 + 验证循环。强成功标准让 LLM 独立循环; 弱标准需要持续澄清。

DevolaFlow 映射:
- **已有对应**: Gate 机制 + `acceptance_criteria` 本身就是 goal-driven execution 的系统级实现。`GateVerdict` 的 PASS/ITERATE/ESCALATE 决策 + convergence loop 的 `max_rounds` + `detect_stagnation()` 构成了一个完整的"循环直到满足目标"框架
- **关键缺口**: 没有 **自动验收标准生成** 机制。当用户给出模糊请求（如"让这个模块更快"）时，L0 Project Agent 的 decomposition 产出的 `acceptance_criteria` 质量完全取决于 LLM 的推理能力，没有结构化的标准生成管道来确保 criteria 的 specificity 和 measurability

#### S/O/R 模式 (Surface/Oracle/Ratchet) 的架构启示

Karpathy 的 AutoResearch 项目 (2026-03-07) 将 agent-driven 实验提炼为三个架构原语:

**Surface (约束表面)** — 定义 agent 可修改的文件集合，其余一切冻结。在 AutoResearch 中: 仅 `train.py` 可编辑，`prepare.py` (评估框架) 和 `program.md` (指令) 不可触碰。这定义了爆炸半径 (blast radius)。

DevolaFlow 对应: `owned_files` 机制 + `check_file_ownership` 钩子。但 DevolaFlow 的 Surface 定义比 AutoResearch 粗糙 — AutoResearch 的 Surface 是 **单文件**，DevolaFlow 的 `owned_files` 可以是多文件列表。更精细的 Surface 意味着更可控的变异空间。

**Oracle (自动化评判)** — 产出 pass/fail 或数值分数的自动化评估，不涉及人类判断。AutoResearch 使用 `val_bpb` (validation bits per byte) — 词汇无关、不可博弈的度量。关键: oracle 必须不可被 agent 操纵。

DevolaFlow 对应: Gate 的 `evaluate_gate()` composite scoring。但 DevolaFlow 的 oracle 有一个微妙的脆弱性 — `review_findings` 维度的评分取决于 LLM 审计结果，而 LLM 审计可能受 agent 生成的代码注释/文档的影响（间接操纵）。AutoResearch 的 oracle 完全是确定性计算，DevolaFlow 的 oracle 混合了确定性 (test/lint/build) 和非确定性 (LLM review) 组件。

**Ratchet (单调递进)** — 保留改进，回退失败。代码只会变好或保持不变，永远不会变差。AutoResearch 的关键指标: 700 次实验 / 2 天 / 单 GPU，发现 20 项优化。每次实验恰好 5 分钟壁钟时间 (~12/小时, ~100/过夜)。

DevolaFlow 对应: **这是最大的架构缺口**。DevolaFlow 的 convergence loop (generate → verify → refine) 没有强制单调递进。一个 convergence round 的 gate score 可能 **低于** 前一轮 — 因为 `reinforcement.py` 注入的 mandates 可能导致 agent 在修复一个问题时引入另一个问题。`detect_stagnation()` 检测停滞但不检测回退。没有机制在检测到分数下降时自动回退到前一轮的 artifact。

#### "Agentic Engineering" 范式转移

Karpathy 自 2025 年 12 月以来没有手动编写代码，而是同时运行 10-20 个 AI agent，每个处理不同的功能。他的贡献是编写 `program.md` — 通过"上下文工程"表达意图、约束和成功定义。瓶颈从编码能力变成了 "skill issue — 与 agent 工具清晰沟通的能力"。

这一实践模式对 DevolaFlow 的启示:
1. **Dispatch 质量 >> Agent 能力**: 当 agent 已经"足够聪明"时（Karpathy 所说的 2025 年 12 月的"连贯性阈值"），系统性能的瓶颈从 agent 能力转移到 dispatch 质量。DevolaFlow 的 `TaskDispatch` schema 的设计质量直接决定了 L3 Task Agent 的表现上限
2. **并行化是默认模式**: 10-20 个并行 agent 意味着 wave-level parallelism 不是优化而是基线。DevolaFlow 的 wave 并行编排 (`parallel: true` in templates) 已具备基础，但缺少 Karpathy 实践中的 **实验隔离** — 每个 agent 修改独立的 Surface，失败不污染其他 agent 的工作空间
3. **程序化 intent 表达**: `program.md` 的结构是 intent + constraints + success_criteria，与 `TaskDispatch` 的 `goal` + `rules` + `acceptance_criteria` 高度同构。但 `program.md` 是人类直接编写的高质量文档，而 DevolaFlow 的 dispatch 由 L1/L2 agent 自动生成 — 自动生成的 dispatch 质量不稳定

#### 69K Stars 病毒式传播的信号解读

不到三个月 0→69.6K stars 的增长曲线, 以及单日 5,828 stars 的爆发, 揭示了三个关键信号:

1. **行为准则的需求是普遍的**: 一个不到 200 行的 `CLAUDE.md` 文件获得的关注度超过大多数完整框架。这说明 agent 行为优化不是框架开发者的小众需求，而是每个使用 AI 编码的开发者的痛点
2. **平台生态已进入加速期**: 同一天 GitHub 趋势榜前五中四个是 Claude Code 生态工具。Multica (12,681 stars) 作为 multi-agent 管理平台的兴起表明，生态已从"单 agent 优化"进入"multi-agent orchestration"阶段 — 这正是 DevolaFlow 的核心定位
3. **"150-200 条指令预算"的限制揭示了 advisory vs deterministic 的鸿沟**: CLAUDE.md 是建议性的 (advisory, ~80% compliance)。超过 150-200 条指令，合规率下降。对确定性执行，需要 hooks（Git 钩子、CI 检查）。DevolaFlow 的 `lifecycle/` hooks 和 gate 机制正是在这个 deterministic enforcement 层面运作 — 这是 DevolaFlow 相对于纯 CLAUDE.md 准则方案的结构性优势

### 1.4 三个信息源的内在关联

三个信息源分别从 **微观 (micro)**、**宏观 (macro)** 和 **行为 (behavioral)** 三个层面揭示了同一个核心趋势:

**Thariq 的推文是微观层面 — 单 Session/单 Agent 的上下文管理**:
- 如何在 1M token 窗口内保持模型的有效注意力
- 五种 session 策略构成的状态机
- Directed compaction 作为精细化的信息管理工具

**SaitoWu/OpenAI 的内容是宏观层面 — 系统架构的 harness 设计**:
- 确定性栅栏如何替代 prompt-based 的不确定性指导
- 验证阶梯如何系统化质量保障
- 熵管理如何保持系统长期健康

**Karpathy 准则 + S/O/R 是行为层面 — Agent 的执行品质与实验框架**:
- 四项行为准则约束 agent 的编码行为 (think → simplify → surgical → goal-driven)
- S/O/R 模式将实验循环形式化为 Surface (约束) → Oracle (评判) → Ratchet (递进)
- "Agentic Engineering" 范式将人类角色从实现者彻底转变为 intent 表达者

**三者的交汇点是 "Context Engineering" 的三维完整性**:
- 微观: 管理单个 agent 的 **上下文质量** (Thariq — 信息密度、时效性、选择性保留)
- 宏观: 设计让多个 agent 在正确上下文中协作的 **系统架构** (SaitoWu/OpenAI — 栅栏、阶梯、状态外化)
- 行为: 引导 agent 在给定上下文内产出 **高质量行为** (Karpathy — 审慎思考、最简方案、精确变更、目标驱动)

**三者的递进关系构成了一个完整的 agent 效能栈**:

```
┌─────────────────────────────────────────────┐
│ L3: Behavioral Layer (Karpathy 准则)        │ ← Agent 如何思考和行动
│     think → simplify → surgical → verify    │
├─────────────────────────────────────────────┤
│ L2: System Layer (Harness Engineering)      │ ← 系统如何约束和验证
│     fences → ladder → state → termination   │
├─────────────────────────────────────────────┤
│ L1: Context Layer (Session Management)      │ ← 信息如何流动和压缩
│     compact → rewind → subagent → clear     │
└─────────────────────────────────────────────┘
```

DevolaFlow 的 **4 层 Agent 层次结构 (L0-L3)** + **Lean YAML interchange** + **Task-Adaptive Context Selection** 已经在三个层面都有了基础架构，但三个信息源揭示的差距集中在:
1. **动态性不足** — 当前的 context 管理主要是静态的 dispatch-time 决策，缺少运行时的 adaptive 响应
2. **闭环不足** — verification 的结果未形成完整的 remediation → injection → re-verification 闭环
3. **持续性不足** — 缺少 entropy management 这样的持续性质量维护机制
4. **行为层空白** — L3 Task Agent 接收结构化的"做什么"指令，但不接收"如何做"的行为准则; 没有过度复杂检测、自动验收标准生成等行为品质保障
5. **递进性缺失** — 收敛循环缺少单调递进保障 (Ratchet)，可以在迭代中退步

---

## 2. 行业趋势提炼

### 2.1 从 Prompt Engineering → Context Engineering → Harness Engineering

行业正在经历三次范式跃迁:

| 阶段 | 核心关注 | 工程师角色 | 质量保障方式 |
|------|----------|-----------|-------------|
| **Prompt Engineering** (2023-2024) | 单次输入的措辞优化 | Prompt 工匠 | 人工评估 |
| **Context Engineering** (2025-2026H1) | 上下文窗口的信息密度最大化 | 上下文架构师 | Token 预算 + 压缩比 |
| **Harness Engineering** (2026H1-) | 整个 AI-辅助开发系统的约束设计 | 约束设计师 | 确定性栅栏 + 验证阶梯 |

DevolaFlow v7.x 处于 **Context Engineering 的成熟阶段**:
- `task_adaptive_selector.py` 的 profile-based section priority ordering = 成熟的 context engineering
- `compressor.py` 的 PRESERVE_LIST/DROP_LIST/INTENSITY_TIERS = 系统化的 context 信息密度管理
- `context_profiles.yaml` 的 per-task-type token budget = 显式的 context 预算治理

但向 Harness Engineering 的跃迁尚未完成:
- Gate 模块是 **最接近 Harness Engineering 的部分** (确定性评分 + convergence loop + reinforcement rules)
- 缺少完整的 **verification ladder** 形式化
- 缺少 **entropy management** 持续性机制
- 缺少 **agent legibility** 可观测性

### 2.2 四大架构原语的行业共识

从 OpenAI (Harness Engineering)、Anthropic (Claude Code session 管理)、GSD (wave orchestration)、Autoresearch (ratchet loop) 等多个来源，可以提取出 **行业正在趋同的四大架构原语**:

**原语 1: 确定性边界 (Deterministic Boundaries)**
- 共识: Prompt 是建议，test/lint/type-check 是结构性约束
- DevolaFlow 对应: `gate/profiles.py` (STRICT/STANDARD/RELAXED/AUDIT), `compressor.py:BYPASS_CONDITIONS`, `lifecycle/` hooks
- 行业领先实践: 将 lint error → remediation instruction 注入到 agent context（当前 DevolaFlow 的 `reinforcement.py` 是最接近的实现）

**原语 2: 分层验证 (Layered Verification)**
- 共识: 廉价检查先行 (fail-fast)，昂贵检查后行 (fail-slow)
- DevolaFlow 对应: `GateInput` 的 `build_status`/`test_results`/`lint_status` 隐式排序
- 缺口: 验证层级之间的短路逻辑未显式编码

**原语 3: 上下文生命周期 (Context Lifecycle)**
- 共识: 上下文 = 寄存器; 文件系统 + git = 持久存储; 需要溢出/换入机制
- DevolaFlow 对应: P5 (Artifacts as Contracts), lean dispatch/report, `learnings.py` JSONL persistence
- 缺口: 没有运行时 context 压力感知和动态响应

**原语 4: 收敛保障 (Convergence Guarantees)**
- 共识: 所有循环必须有退出条件; budget-aware; cycle detection
- DevolaFlow 对应: `max_iterations`/`max_rounds`, `detect_stagnation()`, `on_exhaustion: escalate`
- 缺口: 无 token budget circuit breaker; 无 tool-call semantic similarity 循环检测

### 2.3 "代码免费"时代的工程范式转移

SaitoWu 提出的 "代码免费" 论断暗示了三个工程范式的根本变化:

**1. 从"实现成本"到"验证成本"**
- 当 AI 可以以近乎零成本生成代码时，瓶颈从"写代码"移到"验证代码是否正确"
- 这解释了为什么 OpenAI 的实践中 **确定性栅栏** 成为核心 — 因为验证成本必须低于重新生成成本
- DevolaFlow 的 gate 模块 composite scoring + convergence loop 本质上就是一个验证成本管理系统

**2. 从"吞吐量"到"吞吐量 × 精度"**
- 高吞吐量（3.5 PR/工程师/天）只有在精度足够高时才有价值
- OpenAI 的 "minimal blocking gates when corrections are cheap" 意味着 gate 策略应该根据纠正成本动态调整
- DevolaFlow 的 4 种 gate profile (strict/standard/relaxed/audit) 对应不同的精度/吞吐量权衡，但切换是静态的（人类选择 profile），不是根据 correction cost 动态的

**3. 从"写文档给人看"到"写文档给 agent 看"**
- "Agent legibility" — 代码库应该首先为 agent 的理解能力优化
- "Everything agents can't see in-context doesn't exist" — 如果信息不在 agent 能获取的路径上，它等于不存在
- DevolaFlow 的 `SKILL.md` + references + templates 三层体系已经体现了这一理念，但缺少 **可读性评分** 和 **文档新鲜度跟踪**

### 2.4 Surface/Oracle/Ratchet 作为通用编排原语

Karpathy 的 S/O/R 模式虽然源自 ML 实验自动化 (AutoResearch)，但其三元组结构具备通用编排原语的特征，可以与 Section 2.2 中的四大原语形成互补关系。

#### S/O/R 与四大原语的映射

| S/O/R 原语 | 本质 | 四大原语对应 | 新增维度 |
|------------|------|-------------|----------|
| **Surface** | 约束变异空间 | 确定性边界 (原语 1) | 从"检查违规"升级为"预先限定可变集合" |
| **Oracle** | 自动化评判 | 分层验证 (原语 2) | 强调不可博弈性和数值化 |
| **Ratchet** | 单调递进 | 收敛保障 (原语 4) | 从"终止循环"升级为"只进不退" |

关键区别: 四大原语侧重于 **防御性约束** (防止坏事发生 — 越界、验证失败、无限循环)。S/O/R 侧重于 **进攻性优化** (确保每次迭代都比上次更好)。两者结合形成完整的编排保障: 防御 + 进攻。

#### S/O/R 在 DevolaFlow 场景下的实例化

**Surface 实例化 — 精细化的变异约束**:

AutoResearch 的 Surface 是单文件级别 (`train.py`)。DevolaFlow 当前的 Surface 是 `owned_files` 列表 (多文件)。可以引入 **分层 Surface**:
- **File Surface**: 当前 `owned_files` 机制（已实现）
- **Function Surface**: 限定可修改的函数/类集合（未实现; 需要 AST-level 的变更验证）
- **Line Surface**: 限定可修改的行范围（未实现; 最精细但实现成本最高）

这与 Karpathy 准则三 (Surgical Changes) 直接呼应 — Surface 的粒度决定了"手术精度"的上限。

**Oracle 实例化 — 不可博弈的质量度量**:

AutoResearch 使用 `val_bpb` 作为不可博弈的 oracle。DevolaFlow 的 gate composite score 混合了确定性组件 (test pass rate, lint errors, build status) 和非确定性组件 (LLM review findings)。要实现 S/O/R 的 oracle 保障:
- **确定性 oracle**: `test_results` + `lint_status` + `build_status` → 纯机械评分，不可被 agent 操纵
- **非确定性 oracle**: `review_findings` → LLM 审计，有被间接操纵的风险（通过注释/文档引导 reviewer）
- **改进方向**: 在 Ratchet 判断中只使用确定性 oracle 组件; 非确定性组件仅作为参考信号

**Ratchet 实例化 — 收敛循环的单调递进保障**:

这是 DevolaFlow 当前架构中最明确的缺口。实现 Ratchet 需要:
1. 每轮结束时保存 artifact snapshot (已有 `ConvergenceRound` 但不保存完整 artifact)
2. 下轮结束时比较确定性 oracle 分数
3. 如果分数下降 → 回退到上轮 artifact，使用不同的 reinforcement rules 重新尝试
4. 如果连续 N 轮无法超越历史最佳 → 触发 escalation

#### S/O/R 作为第五原语的理论定位

将 S/O/R 视为四大原语之外的 **第五原语 — 单调递进 (Monotonic Advancement)**:

| # | 原语 | 核心问题 | DevolaFlow 完成度 |
|---|------|----------|-------------------|
| 1 | 确定性边界 | Agent 可以做什么? | ★★★★☆ (gate + lifecycle + bypass) |
| 2 | 分层验证 | 结果是否正确? | ★★★☆☆ (多维评分, 无短路) |
| 3 | 上下文生命周期 | 信息如何流动? | ★★★★☆ (P5 + lean YAML + P6) |
| 4 | 收敛保障 | 何时停止? | ★★★☆☆ (max_rounds + stagnation, 无 budget breaker) |
| **5** | **单调递进** | **每步都在进步?** | **★☆☆☆☆ (无 Ratchet 机制)** |

这是 DevolaFlow v7.8.0 最大的架构机会 — 引入 Ratchet 原语使收敛循环从"最终收敛或停止"升级为"每步保证不退步"。

---

## 3. DevolaFlow 现状评估与差距分析

### 3.1 已有优势 (与行业方向一致的部分)

**A. 成熟的确定性压缩管道**
- `compressor.py` (1302 行): `PRESERVE_LIST` (12 项) 确保关键信息不丢失，`DROP_LIST` (9 项) 系统消除低密度内容，`INTENSITY_TIERS` (minimal/standard/aggressive) 支持分级压缩
- `BYPASS_CONDITIONS` (4 条) + `BYPASS_PATTERNS` (4 条) 确保安全敏感和顺序敏感内容不被压缩
- `INJECTION_PATTERNS` (4 类) + `<data>` envelope 机制对抗 prompt injection

**B. 行业领先的 Task-Adaptive Context Selection**
- `task_adaptive_selector.py` (652 行): 基于 `context_profiles.yaml` 的 task-type → profile → section priority → token budget 全链路
- Plan-mode overrides (检测 `DEVOLAFLOW_PLAN_MODE` 环境变量 → 调整 section 优先级和压缩强度)
- `retrieval_query` 支持的查询引导 section 排名 (v7.2.5)

**C. 完备的 Gate 质量机制**
- 多维复合评分: `DEFAULT_DIMENSION_WEIGHTS` (4 维, test/review/architecture/benchmark), `EXTENDED_DIMENSION_WEIGHTS` (7 维, 含 UI), `ARS_DIMENSION_WEIGHTS` (5 维, acceptance readiness)
- 收敛检测: `detect_stagnation()` + noise tolerance + `compute_smoothed_trend()` (moving average window)
- 4 种 profile: STRICT (90/85/0/0), STANDARD (85/80/0/2), RELAXED (70/60/0/5), AUDIT (95/90/0/0)
- Reinforcement rules: `findings_to_reinforcement()` 将 gate findings 转为下一轮 mandates，最多 5 条，severity-filtered

**D. P5 Artifacts as Contracts + P6 Cache Layout Invariant**
- Lean YAML dispatch/report 格式确保层间通信结构化
- `DEFAULT_DISPATCH_LAYOUT` (13 keys) + `assert_dispatch_layout()` 确保 key ordering 稳定性，利于 KV-cache 复用
- JSONL learnings 带 confidence decay, session pinning, deduplication, consolidation

**E. 渐进式 Agent 知识披露**
- `SKILL.md` (< 500 行) → `references/*.md` (≤ 1000 行 × 8 文件) → `examples/*.md` (≤ 1600 行 × 3 文件)
- 三层架构完全匹配 OpenAI 的 "AGENTS.md as table of contents, not encyclopedia" 理念
- Tiered line budget (SF-1) 有测试强制执行

**F. 生命周期钩子 (v7.5.0)**
- `lifecycle/` 包: `validate_dispatch` + `check_file_ownership` + `test_on_complete`
- Permissive (默认) / Strict (opt-in) 两种执行模式
- 清除了审计中的唯一 BLOCKER (G-C1)

### 3.2 待改进区域 (差距清单)

| # | 差距 | 来源 | 严重度 | 当前状态 | 对应文件 |
|---|------|------|--------|----------|----------|
| G1 | 无分层上下文压缩管道 | Thariq: context rot; Louis Wang: context compaction | 高 | `compress_message()` 仅单层确定性压缩 | `src/devolaflow/compressor.py` |
| G2 | 无定向压缩能力 | Thariq: directed compact | 高 | `summarise_predecessor()` 的 `retrieval_query` 仅影响 section 排名，不支持 topic-level 选择性保留 | `src/devolaflow/compressor.py` |
| G3 | 抽象摘要引擎未实现 | Thariq: compact as model summarization | 高 | `summarise_predecessor(mode='abstractive')` 抛出 `NotImplementedError` | `src/devolaflow/compressor.py:1231` |
| G4 | 无 token 预算断路器 | Louis Wang: budget-aware runtimes | 高 | 模板 `max_iterations` 和 gate `max_rounds` 只限轮次，不限 token 消耗 | `gate/models.py`, `gate/scorer.py` |
| G5 | 无循环检测中间件 | Louis Wang: cycle detection | 中 | 仅有 `detect_stagnation()` (score stagnation)，无 tool-call 语义相似度检测 | `gate/convergence.py` |
| G6 | 无熵管理/GC agent | OpenAI: entropy management / garbage collection | 中 | 完全缺失 — 无文档新鲜度跟踪，无偏差扫描，无清理 agent | (不存在) |
| G7 | 无 Agent 可读性评分 | OpenAI: agent legibility; Louis Wang: optimize for agent | 中 | 无任何代码库可读性度量 | (不存在) |
| G8 | 无统一 Session 状态模型 | Thariq: 5 session management options | 中 | 会话状态散布在 `learnings.py` (JSONL), `lifecycle/` (hooks), `schemas/` (lean dispatch/report) | 多个文件 |
| G9 | 验证阶梯未形式化 | Louis Wang: verification ladder | 低 | `GateInput` 有 5 个 check 字段但无显式层级/短路逻辑 | `gate/models.py`, `gate/scorer.py` |
| G10 | 确定性栅栏 → 修复指令注入闭环不完整 | OpenAI: rewrite error → remediation instruction | 低 | `reinforcement.py` 仅在 convergence round 间注入，不支持 build-failure → agent-context 实时注入 | `gate/reinforcement.py` |
| G11 | Reinforcement shape 不一致 | 内部问题 | 低 | `reinforcement.py` 的 `ReinforcementBlock` dataclass vs lean dispatch schema 的 `reinforce` key 可能存在 shape 差异 | `gate/reinforcement.py`, `schemas/lean-dispatch.yaml` |
| G12 | 无 Rewind 等价机制 | Thariq: rewind pattern | 低 | L3 task agent 无法"回退"到之前的某个状态，只能重新 dispatch | (不存在) |
| G13 | 无单调递进保障 (Ratchet Guarantee) | Karpathy: S/O/R Ratchet 原语 | 高 | convergence loop 可以退步 — round N+1 的 gate score 可能低于 round N。`detect_stagnation()` 检测停滞但不检测回退，无自动回退到历史最佳 artifact 的机制 | `gate/convergence.py`, `gate/scorer.py` |
| G14 | 无 L3 Task Agent 行为准则注入 | Karpathy: Think Before Coding / Simplicity First | 高 | dispatch 告诉 L3 agent "做什么"(goal) 和"验收标准"(acceptance_criteria)，但不注入"如何做"的行为准则。L3 agent 的编码风格完全取决于底层 LLM 的默认行为，没有 "先思考再编码"、"最简方案优先" 等行为引导 | `schemas/lean-dispatch.yaml`, `workflow-system/agent/context_profiles.yaml` |
| G15 | 无过度复杂检测 (Overcomplexity Detection) | Karpathy: Simplicity First 自检标准 | 中 | gate 评估测试通过率、代码审查、架构合理性，但不评估"解决方案是否过于复杂"。agent 可能产出完全正确但过度工程的代码，gate 会给出高分 | `gate/scorer.py`, `gate/models.py` |
| G16 | 无自动验收标准生成 | Karpathy: Goal-Driven Execution 依赖强 success criteria | 中 | 模糊用户请求的 acceptance_criteria 质量取决于 L0/L1 agent 的推理能力，无结构化标准生成管道确保 criteria 的 specificity 和 measurability | `gate/models.py` |
| G17 | 无 diff-level 手术精度验证 | Karpathy: Surgical Changes — 每行变更可追溯到请求 | 中 | `check_file_ownership` 验证文件级写权限，不验证 diff 内容与 task goal 的相关性。agent 可在目标文件内做大量无关变更 | `lifecycle/validate_owned_files.py` |

---

## 4. 性能提升机会拆解

### 4.1 分层上下文压缩管道 (Layered Context Compaction Pipeline)

- **来源推文/概念**: Thariq (context rot), Louis Wang (externalized state & context compaction)
- **当前状态**: `compressor.py:compress_message()` 提供单层确定性压缩（模式匹配 DROP_LIST → 移除 → 空白折叠）。`task_adaptive_selector.py` 在 dispatch 组装时做 section-level 预算分配。两者之间没有中间层
- **提升方案概述**:

  引入三层压缩管道，每层解决不同粒度的 context rot:

  **Layer 1 — Token-level (现有)**: `compress_message()` 的词汇模式移除。保持不变
  
  **Layer 2 — Section-level (增强)**: 增强 `task_adaptive_selector.py` 的 section 选择逻辑，加入 **时效性权重** (recency weighting) — 越新的 predecessor artifact 获得越高的 section 优先级。实现方式: 在 `context_profiles.yaml` 中为每个 profile 增加 `recency_decay_factor` 参数，在 `_select_sections_by_priority()` 中乘以 section 的基础优先级

  **Layer 3 — Semantic-level (新增)**: 在 `summarise_predecessor()` 中实现 **主题相关性过滤** — 给定当前 task 的 `goal` 字段，对 predecessor artifact 的每个 section 计算相关性分数，低于阈值的 section 被替换为单行摘要。这是 `retrieval_query` 机制的自然扩展，但从 section 排名升级到 section 内容的选择性保留

- **预期影响**: 高 — 直接减少 L3 Task Agent 的 context rot，提高 task 执行质量
- **实现复杂度**: 中 — Layer 2 是对现有 `task_adaptive_selector.py` 的参数扩展; Layer 3 需要在 `compressor.py:summarise_predecessor()` 中新增 topic-relevance 计算逻辑
- **涉及文件**:
  - `src/devolaflow/task_adaptive_selector.py` — 增加 recency_decay_factor 参数和加权逻辑
  - `src/devolaflow/compressor.py` — `summarise_predecessor()` 增加 topic-relevance 过滤
  - `workflow-system/agent/context_profiles.yaml` — 每个 profile 增加 recency 参数
  - `schemas/lean-dispatch.yaml` — `pred` 条目增加可选的 `recency_round` 字段
  - `tests/test_compressor.py` — 新增 Layer 2/3 测试
  - `tests/test_benchmarks.py` — 新增/更新 EvoBench 场景

### 4.2 定向压缩/有指导的上下文摘要 (Directed Compaction)

- **来源推文/概念**: Thariq (`/compact focus on the auth refactor, drop the test debugging`)
- **当前状态**: `compress_message()` 不接受语义指引; `summarise_predecessor()` 的 `retrieval_query` 仅影响 section 排名顺序，不支持 "focus on X, drop Y" 语义
- **提升方案概述**:

  新增 `directed_compact()` 函数，接受三个参数:
  - `text: str` — 待压缩文本
  - `focus_topics: list[str]` — 保留主题列表
  - `drop_topics: list[str]` — 丢弃主题列表

  实现分两阶段:
  1. **Topic segmentation**: 利用已有的 `_parse_markdown_sections()` / `_parse_yaml_sections()` 解析器将文本分段，对每段计算与 focus_topics / drop_topics 的词汇重叠度 (类似 `_tokenize_for_retrieval()` 的 bag-of-words 方法)
  2. **Selective compression**: focus 段保留全文或轻度压缩 (intensity=minimal); drop 段压缩到 1-2 行摘要或完全移除; 中立段使用 standard 压缩

  集成点: `summarise_predecessor()` 增加可选的 `focus_topics` / `drop_topics` 参数; dispatch schema 的 `pred` 条目增加可选的 `compact_directive` 字段

- **预期影响**: 高 — 使得 L2 Wave Agent 在构建 dispatch 时可以指导 L3 的 context 焦点
- **实现复杂度**: 中 — 核心是 section-level topic matching + 分级压缩，不需要 LLM 调用
- **涉及文件**:
  - `src/devolaflow/compressor.py` — 新增 `directed_compact()` 函数
  - `schemas/lean-dispatch.yaml` — `pred` 增加 `compact_directive` 字段
  - `workflow-system/agent/references/context-isolation.md` — 更新 directed compaction 说明
  - `tests/test_compressor.py` — 新增 directed compact 测试

### 4.3 Token 预算断路器 (Token Budget Circuit Breaker)

- **来源推文/概念**: Louis Wang (budget-aware runtimes + loop termination guarantees)
- **当前状态**: DevolaFlow 有两种终止机制 — 模板的 `max_iterations` 和 gate 的 `max_rounds`。两者都基于 **轮次计数** 而非 **token 消耗**。一个 task 可能在 2 轮内消耗大量 token（如反复读取大文件），而 `max_iterations=5` 的限制不会触发
- **提升方案概述**:

  新增 `TokenBudgetBreaker` 中间件:

  ```python
  @dataclass
  class TokenBudgetBreaker:
      max_tokens_per_task: int  # e.g., 50000
      max_tokens_per_round: int  # e.g., 15000
      current_round_tokens: int = 0
      total_tokens: int = 0

      def check(self, token_delta: int) -> BreakerAction:
          """返回 CONTINUE / WARN / BREAK"""
  ```

  集成方式:
  - 在 `gate/scorer.py:evaluate_gate()` 中注入 token 消耗检查
  - 在 `gate/convergence.py` 的 stagnation detection 中加入 token 维度
  - 在 lean dispatch schema 中增加 `token_budget` 字段（可选，默认不限）
  - `BreakerAction.BREAK` 触发 escalation (ESCALATE 到上层)
  - `BreakerAction.WARN` 在 status report 中标记 `budget_warning: true`

- **预期影响**: 高 — 防止 token 浪费是 cost management 的核心; 直接映射到 Louis Wang 的 "budget-aware runtimes"
- **实现复杂度**: 中 — 需要在 gate 和 dispatch 两侧分别增加 token tracking 和 budget enforcement
- **涉及文件**:
  - `src/devolaflow/gate/` — 新增 `budget.py` 模块（`TokenBudgetBreaker` 类）
  - `src/devolaflow/gate/scorer.py` — `evaluate_gate()` 集成 token 检查
  - `src/devolaflow/gate/models.py` — `GateProfile` 增加 `max_tokens_per_task` / `max_tokens_per_round` 字段
  - `schemas/lean-dispatch.yaml` — 增加 `token_budget` 字段
  - `schemas/lean-report.yaml` — 增加 `tokens_consumed` 字段
  - `tests/test_gate.py` — 新增 budget breaker 测试
  - `tests/test_benchmarks.py` — 验证无 EvoBench 回归

### 4.4 循环检测中间件 (Cycle Detection Middleware)

- **来源推文/概念**: Louis Wang (cycle detection), Thariq (context rot 的根源之一是重复的失败尝试)
- **当前状态**: `gate/convergence.py` 的 `detect_stagnation()` 检测 **分数停滞** (score-based stagnation)，但不检测 **行为循环** (behavioral cycles) — 即 agent 在不同轮次中重复执行相同或相似的 tool calls / 代码修改
- **提升方案概述**:

  新增 `CycleDetector` 模块:

  ```python
  @dataclass
  class ToolCallSignature:
      tool_name: str
      target_file: str
      action_hash: str  # hash of edit content / command

  class CycleDetector:
      window_size: int = 3
      similarity_threshold: float = 0.8

      def record(self, signature: ToolCallSignature) -> None: ...
      def detect_cycle(self) -> CycleReport | None: ...
  ```

  检测策略:
  1. **Exact match**: 连续两轮的 tool-call 序列完全相同 → 确定性循环
  2. **Fuzzy match**: 连续 N 轮中有 >80% 的 tool-call 目标文件和 action 类型重复 → 高概率循环
  3. **Edit oscillation**: 对同一文件的编辑在两轮中互相"撤销" (edit A→B, then B→A) → 振荡检测

  集成点: 在 `gate/scorer.py:evaluate_gate()` 中检查 `CycleReport`; 如果检测到循环，在 `reinforcement.py` 生成 "MUST NOT repeat: [description of repeated action]" mandate

- **预期影响**: 中高 — 防止 "做-拆-做" 振荡是降低浪费的关键; 与 token budget breaker 互补
- **实现复杂度**: 中 — 需要定义 tool-call signature 的抽象和相似度计算
- **涉及文件**:
  - `src/devolaflow/gate/` — 新增 `cycle_detector.py` 模块
  - `src/devolaflow/gate/scorer.py` — 集成 cycle detection 到 `evaluate_gate()`
  - `src/devolaflow/gate/reinforcement.py` — 循环检测 → mandate 生成
  - `src/devolaflow/gate/models.py` — 新增 `CycleReport` dataclass
  - `schemas/lean-report.yaml` — 增加 `cycle_detected` 字段
  - `tests/test_gate.py` — 新增 cycle detection 测试

### 4.5 熵管理与代码库"垃圾回收" (Entropy Management / GC Agent)

- **来源推文/概念**: OpenAI Harness Engineering (entropy management, "doc-gardening" agents)
- **当前状态**: DevolaFlow 完全缺失此类机制。`check_drift.py` 提供了 SKILL.md 与 `workflow-skill.yaml` 之间的 drift 检测，但这是一次性的 CLI 命令而非持续运行的 entropy 监控。`learnings.py` 的 `decay_confidence()` 和 `prune_learnings()` 是最接近 "GC" 概念的已有机制，但仅作用于 learnings 数据
- **提升方案概述**:

  设计 `entropy_manager` 模块，提供三类 GC 功能:

  **1. Documentation Freshness Tracking**
  - 为每个 agent-facing 文件维护 `last_verified_date` 和 `staleness_score`
  - staleness_score = f(days_since_last_verify, lines_changed_in_deps, test_failures_referencing_doc)
  - 每次 version iteration 时 scan 一遍，输出 staleness report

  **2. Deviation Scanner**
  - 检测 SKILL.md 中声明的能力与实际代码实现之间的偏差（扩展 v7.5.0 ghost audit 的自动化版本）
  - 核心: 解析 SKILL.md 中的每个声明 → 在 `src/devolaflow/` 中搜索对应实现 → 标记 unmatched 声明

  **3. Cleanup Agent Template**
  - 新增 builtin template `workflow-system/agent/templates/builtin/entropy-cleanup.yaml`
  - 包含 stages: `scan` (staleness + deviation), `triage` (severity ranking), `fix` (auto-fix or issue creation)

- **预期影响**: 中 — 长期维护效益显著，但单次版本迭代内的 ROI 不高
- **实现复杂度**: 高 — 涉及文档解析、代码搜索、deviation matching 等多个子系统
- **涉及文件**:
  - `src/devolaflow/` — 新增 `entropy_manager.py` 模块
  - `src/devolaflow/check_drift.py` — 重构为 entropy_manager 的子组件
  - `workflow-system/agent/templates/builtin/` — 新增 `entropy-cleanup.yaml` 模板
  - `workflow-system/agent/context_profiles.yaml` — 新增 `entropy_scan` profile
  - `tests/` — 新增 `test_entropy_manager.py`

### 4.6 抽象摘要引擎 (Abstractive Summarization Engine)

- **来源推文/概念**: Thariq (compact = model summarizes conversation), DevolaFlow 内部 (ADR-003 §2.3 已规划但未实现)
- **当前状态**: `compressor.py:summarise_predecessor(mode='abstractive')` 在第 1231 行抛出 `NotImplementedError`，注释标注 "planned for v7.0.3+"。当前只有 extractive 模式 — 逐字提取 `key_facts` + section 排名 + token 截断
- **提升方案概述**:

  实现 abstractive 摘要路径，分为两个子阶段:

  **阶段 A — Local Abstractive (无 LLM 调用)**:
  - 利用现有的 section parsing + entity extraction 基础
  - 对每个 section 计算 "信息密度分数" (entity count / token count)
  - 低密度 section 用 heuristic 规则压缩（如: 移除示例代码块、折叠枚举列表）
  - 高密度 section 保留全文
  - 这是 extractive 和 full-abstractive 之间的中间层

  **阶段 B — LLM-Assisted Abstractive (可选)**:
  - 使用独立的、干净上下文的 agent (解决 Thariq 指出的"压缩时模型最笨"问题)
  - 生成 task-goal-aligned 的摘要而非通用摘要
  - Budget: 输出 token 不超过输入的 30%

  集成: `context_profiles.yaml` 中 `summary_mode` 已预留了 `abstractive` 选项（ADR-003 遗留），只需实现并测试

- **预期影响**: 高 — 直接解决 predecessor artifact 在 context 中占用过多 token 的问题
- **实现复杂度**: 中 (阶段 A) / 高 (阶段 B — 需要 LLM 调用集成)
- **涉及文件**:
  - `src/devolaflow/compressor.py` — 实现 abstractive 分支，移除 `NotImplementedError`
  - `workflow-system/agent/context_profiles.yaml` — 配置哪些 profile 启用 abstractive
  - `tests/test_compressor.py` — 新增 abstractive 测试套件
  - `tests/test_benchmarks.py` — 新增 abstractive vs extractive 对比场景

### 4.7 Agent 可读性评分系统 (Agent Legibility Scoring)

- **来源推文/概念**: OpenAI Harness Engineering (agent legibility — optimize codebase for agent understanding first)
- **当前状态**: DevolaFlow 没有任何度量来衡量代码库/文档对 agent 的可读性。`check_drift.py` 检查的是声明与实现的一致性，不是可读性
- **提升方案概述**:

  新增 `legibility_scorer.py` 模块，计算三个维度的分数:

  **维度 1 — 结构可预测性 (Structural Predictability)** [0-100]
  - 文件命名是否遵循一致的 convention
  - 目录结构是否 flat-enough (agent 偏好浅层目录)
  - 模块大小是否在 agent 的有效处理范围内 (100-500 行最佳)

  **维度 2 — 文档完备性 (Documentation Completeness)** [0-100]
  - 每个公共 API 是否有 docstring
  - 每个模块是否有 module-level docstring
  - 复杂逻辑是否有内联注释

  **维度 3 — 技术选型亲和度 (Technology Affinity)** [0-100]
  - 使用的库/框架是否在主流 LLM 的训练集中有良好表示
  - 是否避免了过于晦涩的语法 (如过度使用 metaclass、descriptor protocol)
  - 是否使用 "boring technology" (标准库 > 小众库)

  输出: per-file 和 per-module 的 legibility score，以及改进建议列表

- **预期影响**: 中 — 提供了量化的 agent 可读性度量，引导代码库向 agent-friendly 方向演进
- **实现复杂度**: 中 — 大部分可以通过 AST 分析 + 正则匹配实现，无需 LLM
- **涉及文件**:
  - `src/devolaflow/` — 新增 `legibility_scorer.py` 模块
  - `src/devolaflow/cli.py` — 新增 `check-legibility` 子命令
  - `tests/` — 新增 `test_legibility_scorer.py`
  - `workflow-system/agent/references/` — 可考虑新增 legibility 说明

### 4.8 统一会话状态模型 (Unified Session State Model)

- **来源推文/概念**: Thariq (5 session management options 隐含的状态机)
- **当前状态**: 会话相关状态分散在多个子系统:
  - `learnings.py` — JSONL 的 `pinned_for_session`, `source_task_id`, `last_accessed`
  - `lifecycle/` — hook 执行的 per-dispatch state
  - `schemas/lean-dispatch.yaml` — `hdr.timeout`, `verify_cfg` 轮次配置
  - `gate/convergence.py` — `ConvergenceRound` history
  - 无统一的 "session" 抽象将这些关联
- **提升方案概述**:

  引入 `SessionState` 抽象:

  ```python
  @dataclass
  class SessionState:
      session_id: str
      task_id: str
      round_history: list[RoundSnapshot]
      token_consumed: int
      context_health: float  # 0-1, 基于 compress_message 的 compliance_score
      active_learnings: list[str]  # learning IDs pinned for this session
      cycle_detector: CycleDetector
      budget_breaker: TokenBudgetBreaker
  ```

  功能:
  - **State persistence**: 每轮结束时序列化到 `.local/sessions/{session_id}.json`
  - **State recovery**: 新 dispatch 可以引用 `prev_session_id` 实现 context 延续
  - **Health monitoring**: 基于 `context_health` + `token_consumed` / budget 计算 session quality
  - **Rewind support**: `round_history` 允许回退到任意历史 round 的状态

- **预期影响**: 中 — 为 Rewind、Directed Compact、Budget Breaker 提供统一的状态基础
- **实现复杂度**: 中 — 核心是 dataclass 设计 + JSON 序列化; 真正的复杂度在集成
- **涉及文件**:
  - `src/devolaflow/` — 新增 `session.py` 模块
  - `src/devolaflow/gate/scorer.py` — `evaluate_gate()` 接受并更新 `SessionState`
  - `src/devolaflow/gate/convergence.py` — 从 `SessionState.round_history` 读取
  - `src/devolaflow/learnings.py` — session pinning 迁移到 `SessionState`
  - `schemas/` — 新增 `session-state.schema.yaml`
  - `tests/` — 新增 `test_session.py`

### 4.9 确定性栅栏扩展 (Deterministic Fence Expansion)

- **来源推文/概念**: OpenAI (deterministic fences), Louis Wang (原语 1)
- **当前状态**: DevolaFlow 的确定性栅栏有三层:
  - **Gate 层**: `gate/profiles.py` 的阈值 + `gate/scorer.py` 的评分
  - **压缩层**: `compressor.py:BYPASS_CONDITIONS` + `INJECTION_PATTERNS`
  - **生命周期层**: `lifecycle/validate_dispatch` + `check_file_ownership` + `test_on_complete`
  
  缺失: **violation → remediation instruction 闭环**。当前 `reinforcement.py` 在 convergence round 之间注入 findings，但没有将 build/lint/test failure 实时转化为 agent-context 修复指令

- **提升方案概述**:

  扩展 `reinforcement.py` 的职责，新增 `fence_to_instruction()` 函数:

  ```python
  def fence_to_instruction(
      failure_type: str,  # "lint" | "test" | "build" | "type_check"
      failure_details: str,  # 原始错误输出
      max_tokens: int = 200,
  ) -> ReinforcementRule:
      """将构建失败转化为可直接注入 dispatch 的修复指令"""
  ```

  转化规则:
  - `lint` failure → "MUST fix lint error at {file}:{line}: {rule_id} — {description}"
  - `test` failure → "MUST fix failing test {test_name}: {assertion_error_first_line}"
  - `build` failure → "MUST resolve build error: {compiler_error_first_line}"
  - 每种 failure type 的输出经过 `compress_message(intensity='aggressive')` 确保不超 budget

  集成: 在 `gate/scorer.py` 的 `_evaluate_checks()` 中，当 `check.status == 'fail'` 时调用 `fence_to_instruction()` 并追加到 `ReinforcementBlock.rules`

- **预期影响**: 中 — 缩短 "发现问题 → 修复问题" 的反馈环路
- **实现复杂度**: 低 — 本质是字符串模板 + 现有 reinforcement 机制的扩展
- **涉及文件**:
  - `src/devolaflow/gate/reinforcement.py` — 新增 `fence_to_instruction()`
  - `src/devolaflow/gate/scorer.py` — 集成到 `_evaluate_checks()`
  - `tests/test_gate.py` — 新增 fence instruction 测试

### 4.10 验证阶梯形式化 (Verification Ladder Formalization)

- **来源推文/概念**: Louis Wang (verification ladder — 6-rung sequential pipeline)
- **当前状态**: `gate/models.py:GateInput` 包含 `build_status`, `test_results`, `lint_status`, `review_findings`, `acceptance_criteria_results` 五个检查维度，但:
  - 没有显式的执行顺序定义
  - 没有层级之间的短路逻辑（lint fail 时仍会评估 review findings）
  - `gate/scorer.py:evaluate_gate()` 在所有维度上并行评分，不是阶梯式
- **提升方案概述**:

  形式化验证阶梯为 6 级管道:

  | 层级 | 检查项 | 短路条件 | 现有对应 |
  |------|--------|----------|----------|
  | R1 | 结构完整性 (schema validation) | 任何 required 字段缺失 → FAIL | `lifecycle/validate_dispatch` |
  | R2 | 静态分析 (lint) | blocker-severity lint → FAIL | `GateInput.lint_status` |
  | R3 | 构建 (build/compile) | build failure → FAIL | `GateInput.build_status` |
  | R4 | 单元测试 | coverage < threshold → FAIL | `GateInput.test_results` |
  | R5 | 集成测试/UI | visual/interaction < threshold → FAIL | `EXTENDED_DIMENSION_WEIGHTS` |
  | R6 | LLM 审计 (review) | blocker finding → FAIL | `GateInput.review_findings` |

  关键设计: **短路执行** — R_n fail 时，R_{n+1}..R_6 不执行，节省 token 消耗（尤其是 R6 的 LLM 审计是最昂贵的）

  实现: 在 `gate/scorer.py` 中新增 `evaluate_ladder()` 函数，按层级顺序执行检查，每层返回 `PASS`/`FAIL`/`SKIP`，`FAIL` 立即返回 `GateVerdict` 而不继续

- **预期影响**: 中低 — 优化 gate 评估效率（避免在已知失败情况下运行昂贵检查）
- **实现复杂度**: 低 — 主要是 `evaluate_gate()` 内部的执行顺序重构
- **涉及文件**:
  - `src/devolaflow/gate/scorer.py` — 新增 `evaluate_ladder()`, 重构 `evaluate_gate()` 调用链
  - `src/devolaflow/gate/models.py` — 新增 `LadderRung` enum, `LadderResult` dataclass
  - `tests/test_gate.py` — 新增 ladder 短路逻辑测试

### 4.11 单调递进保障 (Monotonic Ratchet Guarantee)

- **来源推文/概念**: Karpathy AutoResearch S/O/R 模式中的 Ratchet 原语
- **当前状态**: DevolaFlow 的 convergence loop (`gate/convergence.py`) 在多轮迭代中不保证分数单调递增。`detect_stagnation()` 使用 `compute_smoothed_trend()` 检测分数趋于平稳，但不检测分数回退。`reinforcement.py` 在轮次间注入 mandates 时可能导致 agent 修复一个问题却引入另一个，使得 round N+1 的 composite score 低于 round N。当前没有机制保存历史最佳 artifact 并在检测到回退时自动回滚
- **提升方案概述**:

  新增 `RatchetGuard` 组件，嵌入 convergence loop:

  ```python
  @dataclass
  class RatchetGuard:
      best_score: float = 0.0
      best_round: int = 0
      best_artifact_snapshot: dict | None = None
      regression_tolerance: float = 0.02  # 允许 2% 波动
      max_regressions: int = 2  # 连续回退 N 次后触发回滚

      def record_round(self, round_num: int, score: float, artifact: dict) -> RatchetAction:
          """返回 ADVANCE (新最佳) / TOLERATE (小幅波动) / ROLLBACK (回退到历史最佳)"""
  ```

  工作流程:
  1. 每轮 gate 评估后，调用 `ratchet.record_round(round, score, artifact)`
  2. 如果 `score > best_score` → `ADVANCE`: 更新 best_score 和 best_artifact_snapshot
  3. 如果 `best_score - score < regression_tolerance` → `TOLERATE`: 继续下一轮
  4. 如果连续 `max_regressions` 轮 `score < best_score - regression_tolerance` → `ROLLBACK`: 回退到 best_artifact_snapshot，生成新的 reinforcement rules (不同于导致回退的那组)
  5. 如果 ROLLBACK 后仍无法超越 best_score → `ESCALATE` 到上层

  关键设计决策:
  - Ratchet 判断 **只使用确定性 oracle 组件** (`test_results` + `lint_status` + `build_status` 的加权分数)，排除非确定性的 `review_findings`。这遵循 Karpathy 的原则: oracle 必须不可被 agent 操纵
  - `regression_tolerance` 允许小幅波动 (e.g., 一个新增测试暂时失败但其他指标改善)，避免过于刚性的 ratchet 导致系统在噪声中反复 rollback

- **预期影响**: 高 — 直接消除 G13 (无单调递进保障)，使 convergence loop 从"尽力收敛"升级为"保证不退步"
- **实现复杂度**: 中 — 核心是 comparator + snapshot 管理; 与现有 `convergence.py` 和 `scorer.py` 松耦合
- **涉及文件**:
  - `src/devolaflow/gate/` — 新增 `ratchet.py` 模块 (`RatchetGuard`, `RatchetAction`)
  - `src/devolaflow/gate/convergence.py` — 在 `ConvergenceRound` 中集成 `RatchetGuard.record_round()`
  - `src/devolaflow/gate/scorer.py` — 新增 `compute_deterministic_oracle_score()` 提取确定性分数子集
  - `src/devolaflow/gate/models.py` — 新增 `RatchetAction` enum, `ArtifactSnapshot` dataclass
  - `tests/test_gate.py` — 新增 ratchet guard 测试 (advance/tolerate/rollback/escalate 四种路径)
  - `tests/test_benchmarks.py` — 验证 ratchet 不导致 EvoBench 回归

### 4.12 L3 行为准则注入框架 (L3 Behavioral Guidelines Injection)

- **来源推文/概念**: Karpathy 四准则 (Think Before Coding, Simplicity First, Surgical Changes, Goal-Driven Execution); 69K stars 验证的行为准则需求普遍性
- **当前状态**: `TaskDispatch` 包含 `goal`, `rules`, `acceptance_criteria`, `owned_files` 等结构化字段，告诉 L3 agent "做什么"和"在哪些约束下做"，但不包含 "如何做" 的行为准则。`context_profiles.yaml` 定义了哪些 SKILL.md section 加载到 agent context，但 section 内容是架构/流程层面的指导，不是编码行为层面的准则。L3 agent 的编码风格完全取决于底层 LLM 的默认行为 — 这正是 Karpathy 准则试图纠正的问题空间
- **提升方案概述**:

  在 dispatch schema 中新增 `behavioral_guidelines` 字段，支持 task-type-adaptive 的行为准则注入:

  **1. Schema 扩展**:
  ```yaml
  # schemas/lean-dispatch.yaml (新增字段, 位于 gate 之后以遵循 P6)
  behavioral_guidelines:
    think_first: bool       # 是否注入 "先思考再编码" 准则
    simplicity_check: bool  # 是否注入 "最简方案" 自检
    surgical_scope: str     # "file" | "function" | "line" — 手术精度级别
    goal_loop: bool         # 是否注入 "定义验证标准 → 循环验证" 模式
  ```

  **2. Profile-Based 默认值** (在 `context_profiles.yaml` 中配置):
  ```yaml
  trivial_fix:
    behavioral_guidelines:
      think_first: false     # 简单任务无需额外思考开销
      simplicity_check: false
      surgical_scope: "file"
      goal_loop: false
  complex_feature:
    behavioral_guidelines:
      think_first: true      # 复杂任务必须先思考
      simplicity_check: true # 启用过度复杂自检
      surgical_scope: "function"
      goal_loop: true        # 启用验证循环
  ```

  **3. 准则模板** (新增 `workflow-system/agent/references/behavioral-guidelines.md`):
  - 包含 Karpathy 四准则的 DevolaFlow 适配版本
  - 每条准则附带 DevolaFlow-specific 的自检标准
  - 按 `behavioral_guidelines` 字段的布尔值选择性加载

  **4. 与 150-200 条指令预算的兼容性**:
  - Karpathy 仓库指出 CLAUDE.md 有 ~150-200 条指令的合规预算
  - 行为准则的注入必须极度精炼 — 每条准则不超过 3 行
  - 总注入量控制在 20-30 行以内，留出充足预算给 task-specific 指令

- **预期影响**: 高 — 直接消除 G14 (无 L3 行为准则注入)，系统化地提升 L3 agent 的编码行为质量。Karpathy 仓库 69K stars 验证了这类行为准则的有效性
- **实现复杂度**: 中 — schema 扩展 + profile 配置 + 准则模板; 与现有 `task_adaptive_selector.py` 的 section loading 机制集成
- **涉及文件**:
  - `schemas/lean-dispatch.yaml` — 新增 `behavioral_guidelines` 字段 (位于 `gate` 之后, 遵循 P6 `assert_dispatch_layout`)
  - `workflow-system/agent/context_profiles.yaml` — 每个 profile 新增 `behavioral_guidelines` 默认值
  - `workflow-system/agent/references/` — 新增 `behavioral-guidelines.md` (准则模板)
  - `src/devolaflow/task_adaptive_selector.py` — 新增准则字段解析和选择性加载逻辑
  - `src/devolaflow/compressor.py` — `assert_dispatch_layout()` 更新以包含新字段
  - `tests/test_compressor.py` — dispatch layout 断言更新
  - `tests/test_benchmarks.py` — 验证准则注入不超出 token 预算

### 4.13 过度复杂检测器 (Overcomplexity Detector)

- **来源推文/概念**: Karpathy Simplicity First — "LLMs pattern-match against complex enterprise code in training data, producing 5x more code than needed"
- **当前状态**: gate 的 `DEFAULT_DIMENSION_WEIGHTS` 评估 test (0.35), review (0.30), architecture (0.25), benchmark (0.10)。没有"复杂度"或"简洁性"维度。一个 500 行的过度工程解决方案与一个 50 行的精炼解决方案在 gate 评分中无法区分（假设两者都通过测试和审查）
- **提升方案概述**:

  新增 `OvercomplexityDetector` 作为 gate 评估的可选维度:

  ```python
  @dataclass
  class ComplexitySignals:
      lines_changed: int
      files_touched: int
      new_abstractions: int      # 新增的 class/protocol/ABC 数量
      nesting_depth_max: int     # 最大嵌套深度
      cyclomatic_complexity: int # 圈复杂度 (McCabe)
      ratio_to_minimal: float    # 实际行数 / 预估最小行数

  class OvercomplexityDetector:
      def evaluate(self, signals: ComplexitySignals, task_complexity: str) -> ComplexityVerdict:
          """
          根据 task_complexity (trivial/simple/standard/complex) 设定不同阈值:
          - trivial: lines_changed > 50 或 new_abstractions > 0 → WARNING
          - simple: lines_changed > 200 或 nesting_depth > 3 → WARNING
          - standard: lines_changed > 500 或 new_abstractions > 3 → WARNING
          - complex: 仅在 ratio_to_minimal > 5.0 时 WARNING
          """
  ```

  集成方式:
  - 在 `gate/scorer.py` 中作为可选的评分维度 (权重可配, 默认 0.0 — opt-in)
  - 在 `gate/profiles.py` 的 STRICT profile 中默认启用 (权重 0.10)
  - `ComplexityVerdict.WARNING` 生成 `reinforcement` mandate: "Solution may be overcomplicated. Review if simpler approach exists."
  - `ComplexityVerdict.CRITICAL` 降低 gate composite score，触发 ITERATE

  预估最小行数 (`ratio_to_minimal`): 基于 task type 和 goal 的关键词启发式估算。例如 "fix typo" → 预估 5 行; "add field to model" → 预估 20 行; "implement new module" → 预估 200 行。这是粗糙的启发式, 但足以捕获 5x 以上的过度工程

- **预期影响**: 中 — 部分消除 G15 (无过度复杂检测)。启发式检测有假阳性风险，但 opt-in 设计和 WARNING/CRITICAL 分级可控
- **实现复杂度**: 中 — 需要 AST 分析 (cyclomatic complexity) + 启发式行数估算; 但可以从简单的行数/文件数阈值开始，逐步增加 AST 维度
- **涉及文件**:
  - `src/devolaflow/gate/` — 新增 `complexity_detector.py` 模块
  - `src/devolaflow/gate/scorer.py` — 新增 `complexity` 可选维度到评分链
  - `src/devolaflow/gate/models.py` — 新增 `ComplexitySignals`, `ComplexityVerdict` dataclass
  - `src/devolaflow/gate/profiles.py` — STRICT profile 增加 complexity 权重
  - `tests/test_gate.py` — 新增 overcomplexity 检测测试

### 4.14 自动验收标准生成 (Automatic Acceptance Criteria Generation)

- **来源推文/概念**: Karpathy Goal-Driven Execution — "Strong success criteria let LLMs loop independently; weak criteria require constant clarification"
- **当前状态**: `TaskDispatch.acceptance_criteria` 由 L1/L2 agent 从用户请求和 task decomposition 中自动生成。criteria 的质量完全依赖上层 agent 的推理能力 — 当用户给出模糊请求 (如"让这个模块更快"、"改善用户体验") 时，生成的 criteria 可能同样模糊 (如"模块性能有改善")。模糊的 criteria 导致 gate 评估无法产出有意义的 PASS/FAIL 判断，使 convergence loop 退化为盲目迭代
- **提升方案概述**:

  新增 `ACGenerator` (Acceptance Criteria Generator) 模块:

  **1. 结构化 AC 模板**:
  ```python
  @dataclass
  class AcceptanceCriterion:
      description: str        # 人类可读描述
      verification_type: str  # "test" | "lint" | "metric" | "review" | "manual"
      verification_cmd: str   # 可执行的验证命令 (如 "pytest tests/test_X.py -k test_Y")
      threshold: str | None   # 数值阈值 (如 "latency_p99 < 100ms")
      measurable: bool        # 是否可自动测量
  ```

  **2. 生成策略 (rule-based + template-matching)**:

  | 用户请求模式 | 生成的 AC 类型 |
  |------------|--------------|
  | "fix bug X" | verification_type="test", verification_cmd="pytest ... -k test_that_reproduced_X" |
  | "add feature Y" | verification_type="test" + verification_type="review" |
  | "improve performance" | verification_type="metric", threshold="latency < baseline * 0.9" |
  | "refactor Z" | verification_type="lint" + verification_type="test" (所有现有测试仍通过) |

  **3. AC 质量评分**:
  - `specificity_score`: criteria 是否指向具体文件/函数/度量 (vs 模糊的"改善")
  - `measurability_score`: 多少 criteria 可自动验证 (vs 需要人工判断)
  - `completeness_score`: criteria 是否覆盖 goal 中所有动词/对象
  - 低质量 AC (composite < 0.6) → 在 dispatch 前生成 WARNING，建议 L1/L2 agent 细化

  **4. 与 Goal-Driven Loop 的集成**:
  - 高质量 AC (所有 criteria 的 `measurable=true`) → gate 可自动评估，支持 Karpathy 所说的"给 success criteria 让 LLM 自行循环"
  - 混合 AC (部分 `measurable=false`) → gate 对可测量部分自动评估，不可测量部分在 status report 中标记 `needs_human_review`

- **预期影响**: 中高 — 消除 G16 (无自动验收标准生成)，提升 convergence loop 的有效性。但 rule-based 模板只能覆盖常见模式，罕见请求仍需人类干预
- **实现复杂度**: 中 — 核心是模板匹配 + 质量评分; 不需要 LLM 调用 (阶段一)，可选 LLM 辅助 (阶段二)
- **涉及文件**:
  - `src/devolaflow/` — 新增 `ac_generator.py` 模块
  - `src/devolaflow/gate/models.py` — 新增 `AcceptanceCriterion` dataclass (替代当前的 string-based criteria)
  - `src/devolaflow/gate/scorer.py` — 使用结构化 AC 的 `verification_cmd` 进行自动化评估
  - `schemas/lean-dispatch.yaml` — `acceptance_criteria` 字段从 `list[str]` 升级为 `list[AcceptanceCriterion]` (保持向后兼容)
  - `workflow-system/agent/context_profiles.yaml` — 新增 `ac_generation` 配置 (哪些 profile 启用自动 AC)
  - `tests/` — 新增 `test_ac_generator.py`

---

## 5. 优先级路线图

### 5.1 优先级矩阵 (Impact × Complexity)

```
Impact ↑
  高 │ [4.1 分层压缩]    [4.3 Token断路器]   [4.6 抽象摘要]
     │ [4.2 定向压缩]    [4.11 Ratchet保障]
     │                   [4.12 行为准则注入]
     │
  中 │ [4.4 循环检测]    [4.8 统一Session]    [4.5 熵管理/GC]
  高 │ [4.9 栅栏扩展]    [4.14 AC自动生成]
     │
  中 │ [4.10 验证阶梯]   [4.13 复杂度检测]    [4.7 可读性评分]
     │
  低 │
     │
     └──────────────┼──────────────────┼──────────────────→ Complexity
                    低                  中                  高
```

### 5.2 推荐实施顺序

基于 **"高影响 + 低/中复杂度优先"** 原则和 **依赖关系排序**:

**第一批 (Quick Wins — 立即可开始)**:
1. **4.9 确定性栅栏扩展** — 低复杂度 + 中影响; 扩展现有 `reinforcement.py`，不引入新模块
2. **4.10 验证阶梯形式化** — 低复杂度 + 中低影响; 重构 `evaluate_gate()` 内部逻辑
3. **4.3 Token 预算断路器** — 中复杂度 + 高影响; 新增 `gate/budget.py`，与现有 gate 松耦合

**第二批 (Core Gate — 需要 4.3 的 token tracking 基础; 含 S/O/R 核心)**:
4. **4.11 单调递进保障 (Ratchet)** — 中复杂度 + 高影响; 新增 `gate/ratchet.py`，消除最大架构缺口 G13。与 4.3 协同: budget breaker 控制成本上限，ratchet 保证质量下限
5. **4.4 循环检测中间件** — 中复杂度 + 中高影响; 新增 `gate/cycle_detector.py`，与 4.3/4.11 共享 per-round 监控
6. **4.12 L3 行为准则注入** — 中复杂度 + 高影响; 在 dispatch schema 和 context profiles 中新增 behavioral_guidelines，消除 G14

**第三批 (Context Enhancement — 需要第二批的行为框架)**:
7. **4.1 分层上下文压缩管道** — 中复杂度 + 高影响; 增强 `compressor.py` + `task_adaptive_selector.py`
8. **4.2 定向压缩** — 中复杂度 + 高影响; 依赖 4.1 的 section-level 增强
9. **4.14 自动验收标准生成** — 中复杂度 + 中高影响; 消除 G16，与 4.11 (Ratchet) 配合: 高质量 AC 使 Ratchet 的 oracle 判断更精确

**第四批 (Advanced Features — 需要第三批的基础)**:
10. **4.8 统一 Session 状态模型** — 中复杂度 + 中影响; 依赖 4.3 (budget) + 4.4 (cycle) + 4.11 (ratchet) 的集成
11. **4.6 抽象摘要引擎** — 中/高复杂度 + 高影响; 阶段 A (heuristic) 可先行，阶段 B (LLM) 延后
12. **4.13 过度复杂检测器** — 中复杂度 + 中影响; 与 4.12 (行为准则) 互补 — 准则是预防，检测器是事后验证

**第五批 (Long-term — 独立模块)**:
13. **4.7 Agent 可读性评分** — 中复杂度 + 中影响; 独立模块，不阻塞其他工作
14. **4.5 熵管理/GC Agent** — 高复杂度 + 中影响; 需要最完整的基础设施

### 5.3 v7.8.0 目标范围建议

基于上述排序和 DevolaFlow 的单版本迭代容量（参考 v7.5.0 的 8 patches / 1 day 产出），**v7.8.0 建议覆盖第一批 + 第二批**:

**v7.8.0 Must-Have (P0)**:
- 4.9 确定性栅栏扩展 — `gate/reinforcement.py` 增加 `fence_to_instruction()`
- 4.3 Token 预算断路器 — 新增 `gate/budget.py`，集成到 `evaluate_gate()`
- 4.11 单调递进保障 — 新增 `gate/ratchet.py`，消除 G13 (最大架构缺口)

**v7.8.0 Should-Have (P1)**:
- 4.10 验证阶梯形式化 — `gate/scorer.py` 增加 `evaluate_ladder()` 短路逻辑
- 4.4 循环检测中间件 — 新增 `gate/cycle_detector.py`
- 4.12 L3 行为准则注入 — dispatch schema + context profiles + `behavioral-guidelines.md` 参考文档

**v7.8.0 Could-Have (P2)**:
- 4.1 分层压缩管道 Layer 2 (recency weighting) — `task_adaptive_selector.py` 增强
- 4.2 定向压缩 (basic topic matching) — `compressor.py` 新增 `directed_compact()`
- 4.14 自动验收标准生成 (阶段一: rule-based 模板) — 新增 `ac_generator.py`

**v7.9.0+ Deferred**:
- 4.8 统一 Session 状态模型
- 4.6 抽象摘要引擎
- 4.13 过度复杂检测器
- 4.7 Agent 可读性评分
- 4.5 熵管理/GC Agent
- 4.1 分层压缩 Layer 3 (semantic-level)
- 4.14 阶段二 (LLM-assisted AC generation)

**预估测试增量**: +120~160 tests (参考 v7.5.0 的 +161; 新增 ratchet + behavioral guidelines 覆盖)
**预估模块增量**: +3~5 新文件 (`gate/budget.py`, `gate/cycle_detector.py`, `gate/ratchet.py`, 可选 `ac_generator.py`, 可选 `behavioral-guidelines.md`)
**EvoBench 影响**: 需要新增 5~8 benchmark scenarios 覆盖 budget/cycle/ladder/ratchet/behavioral 行为
**SKILL.md 影响**: 可能需要 3-5 行更新描述新的 gate 能力 (Ratchet + 行为准则)，需注意 SF-1 的 498/500 行余量; 可能需要将部分现有内容压缩到 references/ 以腾出空间
**references/ 影响**: 新增 `behavioral-guidelines.md` (SF-4 需更新 valid references 列表); 需遵循 Large tier ≤ 1000 行限制

---

## 6. 总结与展望

### 核心发现

三个信息源从不同视角揭示了同一个行业趋势: **AI 辅助开发正在从 "如何让 AI 写好代码" 转向 "如何设计让 AI 可靠、高质量地工作的系统"**。

Thariq 的推文揭示了 **单 agent 层面的核心挑战** — context rot 是 1M token 窗口时代的阿喀琉斯之踵。五种 session 管理策略（Continue/Rewind/Clear/Compact/Subagents）构成了一个状态机，而 Directed Compaction 是这个状态机中最有价值的转换操作。

SaitoWu 引用的 Harness Engineering 揭示了 **系统层面的架构原语** — 确定性栅栏、验证阶梯、外化状态、循环终止保障。这四个原语构成了任何 reliable AI-assisted development system 的基础，而 DevolaFlow 在四个维度上都有覆盖但完成度参差不齐。

Karpathy 准则与 S/O/R 模式揭示了 **行为层面的品质保障** 和 **实验框架的递进保障**。69,634 stars 的市场验证表明, agent 行为准则不是框架开发者的小众需求, 而是每个使用 AI 编码的开发者的痛点。S/O/R 的 Ratchet 原语填补了四大原语中"单调递进"的空白, 构成第五原语。Karpathy 的 "agentic engineering" 实践模式 (10-20 并行 agent, 人类仅编写 intent) 验证了 DevolaFlow 的 wave-level 并行编排方向, 同时暴露了 dispatch 质量和实验隔离的差距。

### DevolaFlow 的战略定位

DevolaFlow v7.7.0 处于 **Context Engineering 到 Harness Engineering 的过渡期**, 同时需要开辟 **Behavioral Engineering 这一新维度**:

- **Context Engineering 维度** (成熟): 确定性压缩管道、task-adaptive selection、token 预算、P6 缓存前缀稳定性
- **Harness Engineering 维度** (初期): Gate 多维评分、convergence loop、reinforcement rules、lifecycle hooks
- **Behavioral Engineering 维度** (空白): 无 L3 agent 行为准则注入、无过度复杂检测、无自动验收标准生成

行业正在形成的共识是: **系统约束 (Harness) + 行为引导 (Behavioral) + 递进保障 (Ratchet) = 可信赖的 Agent 编排**。DevolaFlow 在系统约束维度有坚实基础, 但行为引导和递进保障是两个清晰的空白区域。

v7.8.0 的机会在于 **三线并进**:
1. **补齐 Harness 缺失** — token 预算断路器、循环检测、验证阶梯形式化 (延续原有方向)
2. **引入 Ratchet 原语** — 单调递进保障, 使 convergence loop 从 "尽力收敛" 升级为 "保证不退步" (S/O/R 启发的新方向)
3. **开辟 Behavioral 维度** — L3 行为准则注入框架, 将 Karpathy 四准则系统化地注入 dispatch 流程 (全新维度)

### Karpathy 效应与生态位判断

forrestchang/andrej-karpathy-skills 的病毒式传播 (不到三个月 0→69.6K stars) 以及 Multica 平台 (12,681 stars) 的兴起, 传递了两个战略信号:

**1. "advisory vs deterministic" 的互补性是 DevolaFlow 的核心差异化**

Karpathy 准则是 advisory — CLAUDE.md 本质上是建议, ~80% 合规率, 150-200 条指令后合规度下降。DevolaFlow 的 gate + lifecycle hooks 是 deterministic — 机械验证, 100% 执行率。两者不是竞争关系而是互补关系:
- CLAUDE.md / behavioral_guidelines = 行为预期设定 (soft constraint)
- gate composite scoring + ratchet = 结果验证强制 (hard constraint)

v7.8.0 通过引入 `behavioral_guidelines` dispatch 字段 (4.12) 将 advisory 准则纳入 DevolaFlow 的 deterministic 框架, 实现 **soft priming → hard verification** 的完整闭环。

**2. Multi-agent orchestration 正从 "有用" 进入 "必需"**

Karpathy 同时运行 10-20 个 agent 的实践, Multica 作为 multi-agent 管理平台的市场验证, 以及 GitHub Trending 上 Claude Code 生态工具的密集出现 — 都指向同一个结论: multi-agent orchestration 不再是框架开发者的技术探索, 而是每日开发实践的基础设施需求。DevolaFlow 的 4-layer hierarchy + wave parallelism + gate mechanism 在这一生态中占据了 **"structured orchestration with quality gates"** 的独特定位。

### 长期展望

随着 "代码免费" 时代的到来和 "agentic engineering" 范式的确立, DevolaFlow 的核心价值将从 **"编排多个 agent 完成任务"** 演变为 **"确保多个 agent 的协作是可靠、可观测、可终止、且只进不退的"**。14 项提升机会覆盖了这一演变所需的全部基础设施:

| 维度 | 原有 (4.1-4.10) | 新增 (4.11-4.14) | v7.8.0 目标 |
|------|-----------------|------------------|-------------|
| Harness Engineering | 4.3 Token 断路器, 4.4 循环检测, 4.9 栅栏扩展, 4.10 验证阶梯 | — | 4 项全部落地 |
| Monotonic Advancement | — | 4.11 Ratchet 保障 | 核心落地 |
| Behavioral Engineering | — | 4.12 行为准则注入, 4.13 过度复杂检测, 4.14 AC 自动生成 | 4.12 落地, 4.13/4.14 部分 |
| Context Optimization | 4.1 分层压缩, 4.2 定向压缩, 4.6 抽象摘要 | — | Layer 2 落地 |
| System Model | 4.5 熵管理, 4.7 可读性评分, 4.8 统一 Session | — | 延后 |

v7.8.0 的 6~9 项落地 (P0+P1+部分 P2) 将使 DevolaFlow 成为行业中对 **五大编排原语** (确定性边界 + 分层验证 + 上下文生命周期 + 收敛保障 + 单调递进) 覆盖最完整的开源框架, 同时开辟 Behavioral Engineering 这一差异化维度。

---

> **本报告为 SI-1 Planning Gate 输入，建议在开始 v7.8.0 实施前由 human stakeholder review 并确认 P0/P1/P2 范围。**
> **补充更新注记: 2026-04-21 新增 Karpathy 准则与 S/O/R 模式分析后, 差距清单从 G1-G12 扩展为 G1-G17, 提升机会从 10 项扩展为 14 项, v7.8.0 P0 新增 4.11 Ratchet 保障, P1 新增 4.12 行为准则注入。**

---

## 7. v8.0.0 升级目标重新评估 (v2)

### 7.1 范围扩展: 从单版本到三版本路径

v1 报告将 14 项提议分配到 v7.8.0 (P0/P1/P2)。v2 重新评估为**三版本路径**:

- **v8.0.0 (主要发布)**: 14 项提议拆解为 N 个独立 patch (P-01..P-N), 每个 patch 必须有量化收益指标 (test count delta, EvoBench delta, gate composite delta), 每个 patch 完成后执行 `self-update` workflow 进行优化与文档同步; 完成后聚合为 v8.0.0 → v8.1.0-rc.1 pre-release。
- **v8.1.0 (pre-release + 自分析)**: v8.0.0 patches 全部聚合, 运行一轮完整自分析迭代 (NineS self-eval + EvoBench 基线对比 + retrospective + 第二轮 gap analysis)。基于自分析产出 v8.1.0 → v8.2.0 patch 清单。
- **v8.2.0 (最终发布与合入)**: 第二轮 patches 落地, 通过完整 SI-1..SI-10 闸门, 最终 release/merge 到 main 并 tag。

设计意图: v7.6 → v7.8 三个 cycle 全部消耗在 repo-init 是因为缺乏"主线 vs 副线"的版本路径分层 — v8 路径首次显式划分 "实现层 (8.0.0) / 自检层 (8.1.0) / 收口层 (8.2.0)", 让 self-update 与 self-eval 不再被挤出周期。

### 7.2 NineS 决议 (基于 §0.3 摘要)

基于 NineS 12 个非 info finding, 对 v8.0.0 patch 优先级给出以下具体调整:

1. **将 4.1 (分层压缩) + 4.2 (定向压缩) 合并为同一 patch P-01**, 落点 `src/devolaflow/compressor.py`。理由: NineS 把 `summarise_predecessor` (cc=15) + `extract_named_entities` (cc=11) 同时标记为 `compressor.py` 内的复杂度热点 (`[NineS:CC-39ab83-0001]` + `[NineS:CC-39ab83-0000]`); 一次重构可同时降低 2 个 cc 分数 + 落地 4.1/4.2 功能 + 不破坏 cache prefix (compressor 输出位于 dispatch 末段)。预期复杂度收益: cc=15→≤10, cc=11→≤8。

2. **新增 patch P-CC-cleanup (不在 v1 14 项内)**, 唯一目标是降 `DataDrivenAdapter._apply_transform` cc=22 → ≤10 (`[NineS:CC-70f79c-0000]` 唯一 ERROR 级 finding)。该函数与 v1 14 项无直接关系, 但若不处理会持续拉低 NineS 自评分, 影响 v8.1.0 G2 门控 (composite ≥ 8.5) 通过率。建议作为 v8.0.0 第 1-2 个 patch 早期落地, 风险隔离。

3. **将 4.11 (ratchet) 与 `task_adaptive_selector.apply_round_escalation` 重构耦合** (`[NineS:CC-448821-0001]` cc=11)。`apply_round_escalation` 当前混合了 round 推进 + 严重度过滤 + 结果选择三种关注点, 引入 ratchet 时将其拆分为 `escalate_round()` + `apply_severity_filter()` + `select_round_result()` 三个职能, 顺带把 cc 降至 ≤6/each。

4. **将 4.5 (熵管理 / GC) 与 `learnings.py` 双热点重构耦合** (`[NineS:CC-631b33-0000]` cc=14 + `[NineS:CC-631b33-0001]` cc=12)。`load_relevant_learnings` 与 `decay_confidence` 是熵管理设计的核心入口; 4.5 落地必须重写这两个函数, 顺带降复杂度。

5. **补充一项非 v1 项 P-NINES-AGENT**: 在 v8.1.0 self-eval 阶段对 `workflow-system/agent/` 单独跑一次 `nines analyze --agent-impact`, 产出独立 agent-facing artifact 评分 (`[NineS:kp-find-3de75952]` 显示当前 src/ 视角下 agent-facing 计为 0)。该评分将作为 4.12 (behavioral guidelines) 实施前后的 mechanism_count + economics_score 对照基线。

辅助决议:
- 4.13 (overcomplexity detector) 的实现可以**复用 NineS 的 `--depth deep` complexity 输出** — 不必在 DevolaFlow 内重复写圈复杂度计算器, 而是 wrap NineS subprocess 并把 12 个非 info finding 转译为 gate `complexity_violation` 类型 finding。可显著降低 4.13 的 effort 估算 (从 L → M)。
- 4.14 (AC 自动生成) 与 NineS findings 无直接耦合, 维持 v1 优先级不变。
- 4.7 (agent legibility) / 4.8 (unified session) 在 NineS deep analyze 中无任何信号 — 维持 v1 P3 / 延后判定。

### 7.3 v8.0.0 → v8.2.0 路径门控

| 门控 | 触发版本 | 通过条件 | 失败动作 |
|------|----------|----------|----------|
| G1 v8.0.0 patch 完整性 | v8.0.0-rc.1 | N/N patches ACCEPT, 0 EvoBench 回归, SI-10 6/6 PASS | 单 patch REJECT → 重新 dispatch; 系统性失败 → 拆分为 v7.9 中间版本 |
| G2 v8.1.0 自分析质量 | v8.1.0-rc.1 | NineS self-eval composite ≥ 8.5/10, retrospective 4 sections 完整, agent-facing artifact NineS 二次扫描 mechanism_count > 0 | 分数不足 → 第二轮 patch 清单优先级重排; 退化 → 回滚到 v7.8.0 基线 |
| G3 v8.2.0 release | v8.2.0 | NineS composite ≥ 9.0/10, EvoBench 至少 +5pp 净增益, 0 ghost feature, NineS 12 个非 info finding 至少消除 8 个 | release 推迟; 拆分为 v8.1.x patch 系列 |

各门控均强制要求 W-9 (SI-10) 6 步 pre-commit 序列全部 PASS, 任一 patch 失败一次 → 触发 W-8 (SI-9) reinforcement 注入下一轮; 连续 2 轮停滞 → P4 升级到人类决策 (L0 不直接 abort)。

### 7.4 v8.0.0 patch 清单的 14 项映射

v1 报告的 14 项提议 (4.1-4.14) 与 v8.0.0 patch 编号的对应关系将由后续 `.local/research/v8.0.0_patch_plan.md` 详细定义。本次报告仅完成 **决策依据汇总**, 不在本文件中产出 patch 编号 — 那是设计阶段任务 (Task B)。

预定的 patch 清单输入 (供 Task B 参考, 非最终编号):
- 4.1 + 4.2 合并 (compressor 一次重构, 见 §7.2 决议 1)
- 4.3 / 4.4 / 4.9 / 4.10 (Harness Engineering, 4 项各自独立 patch)
- 4.11 (Ratchet, 与 `apply_round_escalation` 耦合, 见 §7.2 决议 3)
- 4.12 / 4.13 / 4.14 (Behavioral Engineering, 3 项, 4.13 借力 NineS 见 §7.2 辅助决议)
- 4.5 / 4.6 (Entropy + Abstractive, 与 `learnings.py` 双热点耦合, 见 §7.2 决议 4)
- 4.7 / 4.8 (Agent Legibility + Unified Session, 维持 P3)
- 新增: P-CC-cleanup (`_apply_transform` 唯一 ERROR 净化, 见 §7.2 决议 2)
- 新增: P-NINES-AGENT (agent-facing 表面 NineS 二次扫描, 见 §7.2 决议 5)

预估 N ≈ 12-14 个 patch (不含 4.1+4.2 合并产生的 -1 与新增 +2)。

### 7.5 self-update 集成点

每个 v8.0.0 patch 完成后必须运行 `self-update` workflow (workflow type: `self-update`, 7 stages: check-refs → research-updates → decompose → integrate → test → evaluate → release)。该 workflow 的输出是该 patch 的 micro-retrospective, 供下一 patch 的 SI-1 planning gate 复用。

具体集成要点:
- `check-refs` 阶段强制 diff `workflow-system/agent/knowledge/reference-dependencies.yaml` 中所有 `active_tracking` 条目 (含 Karpathy 仓库 — 因 §0.2 显示其 8 天 3.06× 增长, biweekly 间隔在 v8.0.0 周期内可能产生 ≥ 2 次 trigger)。
- `evaluate` 阶段必须捕获本 patch 的 NineS finding delta (相对 §0.3 12 项基线)。
- `release` 阶段不打 ANNOTATED tag (那是 v8.0.0 / v8.1.0 / v8.2.0 三个里程碑的专属), 仅打 lightweight tag `v8.0.0-pNN` (沿用 v7.5.0 cycle 的命名约定)。

最终 v8.2.0 的 SI-8 retrospective 将聚合所有 patch 的 micro-retrospective + 两轮 NineS self-eval delta + EvoBench 净增益 + 4 个 sections (gaps / implemented / deferred / learnings), 形成对 v7.6→v7.8 单线性重构周期的完整反例。

---

## 8. v3 Refresh — v8.0.0 实际着陆 + Karpathy biweekly 校准 + v8.2.0 候选信号 (2026-04-22)

> v3 补充更新: 2026-04-22 — v8.0.0 已发布 (HEAD `469ec20`, ANNOTATED tag `v8.0.0` 已打), §7 预测的 13-patch 实际全部落地, §8 在 §7 预测之上做实际 vs 计划的对照 + 第一次 `workflow-system/agent` NineS 二次扫描 + Karpathy 仓库自 v2 (2026-04-21) 起 ≥ 24 小时窗口的快讯, 并产出 v8.2.0 候选清单 (5 项, 按 Type A/B/C/D 归类)。
>
> 上游 v3 artifact:
> - `.local/research/v8.1.0_nines_self_eval.json` (51 KB; overall 0.9046 → **9.05/10** ≥ 8.5 ✓; weighted_overall 0.7044 dragged by `code_coverage: 0.0`)
> - `.local/research/v8.1.0_nines_workflow_system.json` (24 KB; **mechanism_count: 8** ✓ > 0; 1 warning re: 46179 token overhead)
> - `benchmarks/devolaflow_context/baselines/v8.1.0_baseline.json` (13.6 KB; rebased from v8.0.0; 36/36 PASS in 12.78s; **0pp regression**)
> - `.local/research/v8.0.0_evaluation.md` (347 lines; SI-3 composite **9.55/10** READY)
> - `.local/research/v8.0.0_retrospective.md` (443 lines; SI-8 4 sections; 12/12 NineS findings closed; +778 tests)

### 8.1 v8.0.0 实际着陆 vs §7 预测 (deviations)

§7 预测 13 patch / 5 wave / 0 EvoBench 回归 / 12 NineS finding closure 已**完全实现** (per `.local/research/v8.0.0_retrospective.md` §1.1 表格 + §2.1 表格), 但实施过程中出现 4 类 deviation, 全部记入 v8.1.0 self-analysis 的新发现:

| # | 维度 | §7 预测 | v8.0.0 实际 | Deviation 类型 | 影响 |
|---|------|---------|-------------|----------------|------|
| D1 | 测试增量 | 总 +325 tests (per-patch ~25-35) | **+778 tests** (140% 超出, +726 post-W1) | 系统性低估 | 单一 patch overshoot 100-350% (P-04 +53 vs +15, P-06 +100 vs +30, P-07 +85 vs +30, P-09 +74 vs +25, P-10 +66 vs +30) — 任何含 NEW module 的 patch 至少 +50, 含 oracle/state-machine 的至少 +85 |
| D2 | Gate suite 扩张 | ≥ 600 gate-related tests (§6.3 expected outcome) | **948 gate tests** (158% 超出, 9.77× v7.8.0 baseline 97) | 超额完成 | 7 个新 primitive 全部 ≥80% 覆盖, 多个 100% 覆盖 (gate/budget.py, gate/ratchet.py) |
| D3 | EvoBench scenario 增量 | 8-13 个新 scenario (§6.3) | **仅 2 个着陆** (P-02 layered_recency_decay + directed_compaction_focused) | 严重不足 (~10 个 deferred) | 7 个新 gate primitive 缺乏端到端 scenario 验证, 只能依赖 unit tests 间接证明 — 是 v8.2.0 P0 候选 |
| D4 | SKILL.md Tier 3 行 (P-08 计划新增) | 498→499/500 | **493→495/500** (P-08 行 deferred, P-11 +2 行 entropy-cleanup) | 架构耦合阻塞 | 发现 R7 line-anchored section registry 与 SKILL.md 行号深度耦合 — 任何 SKILL.md 行号变化触发 ≥ 3 EvoBench scenario > 5pp 漂移; **R7 是 v8.2.0 highest-priority 架构债** |

**未在 §7 预见的 NEW gap (3 项)**:

| # | 来源 | 内容 | 严重度 | v8.2.0 candidate |
|---|------|------|--------|-------------------|
| N1 | T01 NineS self-eval `code_coverage: 0.0` | NineS internal `pytest --cov` 在 NineS 自身的 54 秒 budget 内 timeout (stderr: *"pytest --cov timed out after 54.0s (budget-derived)"*); 导致 hygiene 复合分被拖至 0.7947 / 0.4939 (group_means.hygiene), weighted_overall 跌至 0.7044 vs overall 的 0.9046 | medium (掩盖真实覆盖率 ~96.78% per evaluation §2.3) | **A1: NineS self-eval --cov budget 提升 OR 预计算 coverage artifact** |
| N2 | T02 NineS workflow-system warning `AI-24c4f48d-0002` | "Agent context overhead is high (46179 tokens). Consider compressing or splitting Agent-facing files." (suggestion: *"Split large instruction files into role-specific segments or apply token-compression techniques."*); 单一 SKILL.md 占 5131 token/mechanism × 8 mechanism = 41048 token expected baseline | medium (break_even_interactions: 9 仍 < L0 typical session length, economics_score: 0.1606 在可接受区间) | **A2: SKILL.md 进一步切片到角色化 references (与 R7 line-registry 解耦后实施)** |
| N3 | T02 NineS workflow-system 仅识别 1 个 agent_facing_file (`SKILL.md`) | NineS analyze 不爬取 `workflow-system/agent/references/*.md` (8 文件) + `workflow-system/agent/examples/*.md` (3 文件) + `workflow-system/agent/references/behavioral-guidelines.md` (P-08 NEW) — 8 个 mechanism 全部从 SKILL.md 内容提取, 其他 12 个 .md 在 file_type_counts 中可见 (19 .md 总数) 但未被解析为 agent_mechanism | low (NineS schema 限制, 非 DevolaFlow 缺陷) | **D7: 给 NineS PR 增加 references/examples 子目录扫描** (外部 contribution, 非本仓 patch) |

### 8.2 Karpathy `forrestchang/andrej-karpathy-skills` 24 小时 biweekly check (2026-04-21 → 2026-04-22)

**环境约束**: 当前 sandboxed 环境无法做远程 GitHub HTTP 请求 (受限网络), 严格 biweekly 校验 (≥ 14 天窗口) 推迟到 v8.2.0 周期由 user 提供 GitHub fetch 输出。本节仅完成基于 §0.2 v2 baseline (2026-04-21 快照: 69,825 stars) 的**外推预测 + biweekly 触发条件设定**:

- **预测带**: 按 v2 (8 天 +47K stars, 3.06× growth) 的指数增长率, 24 小时窗口预期 +5-7K stars (达 ~75-77K stars 区间); CLAUDE.md 4 准则在 v2 中已字节级稳定, 预期 v3 仍 0 字节变化 (大规模社区检验下 advisory artifact 已达稳态)
- **biweekly 触发条件 (active_tracking 配置)**:
  1. star delta ≥ 5K 在 14 天窗口 → 触发 `self-update` workflow `check-refs` 阶段强制 diff (per `workflow-system/agent/knowledge/reference-dependencies.yaml` 中 Karpathy 仓库的 `active_tracking` 条目)
  2. CLAUDE.md SHA-256 变化 → 触发 `behavioral-guidelines.md` (P-08 NEW reference) 的同步更新 patch
  3. 任一新 .md 在仓库 root 出现 → 触发 NineS deep analyze on the new file + 评估是否纳入 DevolaFlow `behavioral_guidelines` 字典
- **defer to user verification**: v8.2.0 SI-1 planning gate 启动时, 由 user 提供 `gh repo view forrestchang/andrej-karpathy-skills --json stargazerCount,updatedAt` + `gh api repos/forrestchang/andrej-karpathy-skills/commits?path=CLAUDE.md` 输出, 由 L3 task agent 比对 v3 baseline 决定是否触发 P-K01 patch (Karpathy v2 准则同步)
- **Karpathy 效应在 v8.0.0 中已得到完整制度化兑现** (per `.local/research/v8.0.0_retrospective.md` §4.13): 4 准则 → P-08 BG-001..BG-004 + S/O/R 三元组 → P-07 oracle + ratchet + P-08 surgical_scope; 这意味着 Karpathy 上游若发布**第 5 准则**, DevolaFlow 已具备 1-patch 整合能力 (BG-005 字段直接 append 到 `behavioral_guidelines` map, P6 schema 不变)

### 8.3 v8.2.0 候选信号 (5 patches, Type A/B/C/D 归类)

按 plan c "5 patches per forecast" 的决策, 综合 v8.0.0 retrospective §3.1-§3.8 的 deferred 项 + §4.x 的 key learnings + 本 §8.1 的 4 个 deviations + 3 个 NEW gaps, 排序如下:

#### Type A — NineS 驱动 (硬量化指标改善)

| 编号 | 名称 | 量化收益 | NineS 关联 | 优先级 |
|------|------|----------|------------|--------|
| **A1** | NineS self-eval `--cov` budget 提升至 ≥120s OR 预计算 coverage artifact 路径 | hygiene_mean 0.7947 → ≥0.96; weighted_overall 0.7044 → ≥0.88 (+0.18pp); group_means.hygiene 0.4939 → ≥0.80 | T01 `code_coverage: 0.0` (timeout in nested `pytest --cov` after 54s) | P0 |
| **A2** | 把 SKILL.md 内 ~5K token / 8 mechanism 的内容切片到角色化 references (依赖 R7) | overhead_tokens 46179 → ≤30000; `kp-find-5ddd489b` warning 消除; economics_score 0.1606 → ≥0.25 | T02 warning `AI-24c4f48d-0002` "Agent context overhead is high (46179 tokens)" | P1 (依赖 B1) |

#### Type B — workflow-system gap 关闭 (架构债务 + EvoBench 缺口)

| 编号 | 名称 | 量化收益 | 来源 | 优先级 |
|------|------|----------|------|--------|
| **B1** | R7 line-anchored section registry → section-anchor registry 重构 | 解锁 SKILL.md 任意行编辑 (含 P-08 deferred Tier 3 行); 触发 ≥ 3 EvoBench scenario > 5pp 漂移问题归零 | retrospective §3.3 R7 ("v8.0.x SI-1 entry point") | **P0** (highest priority — blocks A2/B5) |
| **B2** | ~10 个 deferred EvoBench scenario 着陆 (auto_ac_specificity / overcomplexity_warning / ratchet_rollback / ratchet_advance_chain / cycle_exact_match / cycle_edit_oscillation / behavioral_guidelines_complex/trivial / token_budget_breaker / fence_instruction_injection / abstractive_vs_extractive) | EvoBench scenario count 36 → ~46 (+10); 7 个 v8.0.0 新 gate primitive 全部获得端到端 scenario 验证 | retrospective §3.5 + §3.8 第 2 点 | P0 |
| **B3** | Auto-wire 7 个 opt-in primitive 到 orchestrator (evaluate_ladder/MonotonicRatchet/cycle_detector/complexity_detector/acceptance_criteria_v2/_evaluate_checks/entropy-cleanup) | 默认 OFF→ON 后 gate composite 预期 +0.3-0.5pp; orchestrator 表面降低 7 个 opt-in 旗标的表面积 | retrospective §3.4 (7 项详细列表) | P1 (依赖 dogfooding telemetry) |

#### Type C — Karpathy-aligned 新 primitive

| 编号 | 名称 | 量化收益 | 来源 | 优先级 |
|------|------|----------|------|--------|
| **C1** | Stage B abstractive summariser (LLM-assisted) — 7-mode fallback chain | `long_context_repo_qa` 预期 +3-5pp (per Stage A +0.59pp 实测的 5-8× LLM 路径乘数估算) | retrospective §3.1 + 设计文档 `.local/research/v8.0.0_p12_abstractive_stage_b_design.md` (260 lines READY) | P1 |

#### Type D — 从 v8.0.0 retrospective 的 key learnings 涌现

| 编号 | 名称 | 量化收益 | 来源 | 优先级 |
|------|------|----------|------|--------|
| **D1** | SKILL.md budget pre-commit hook (auto track 行数 + per-section token estimate) | 阻断 SKILL.md 跨阈值的 commit, 防止 P-08 类 deferral 再次出现; 给 v8.x 后续 schema bump 留出可观测的 headroom 信号 | retrospective §3.8 第 3 点 + key learning §4.4 | P2 |

**综合优先级 ranking**:

1. **B1 (R7 line-registry decoupling)** — highest priority, 是 A2 / B2 部分 / D1 的前置依赖, 不解决会持续阻塞 SKILL.md 演进
2. **A1 (NineS self-eval --cov budget)** — 单文件改动 (`nines.toml` 配置 OR `scripts/precompute_coverage.py` 新增), 立即把 weighted_overall 从 0.7044 推到 ≥0.85, 解锁 v8.2.0 G3 release 阈值 9.0/10 的可达性
3. **B3 (auto-wire opt-in primitives)** — 7 个 v8.0.0 新 primitive 从 "advisor" 升级为 "default executor", 是 v8.0.0 投入的兑现路径
4. **B2 (~10 deferred EvoBench scenarios)** — 与 B3 配对落地, 给新 default-on primitive 提供回归保护
5. **C1 (Stage B abstractive summariser)** — 长周期收益最高, 但涉及 LLM 调用 (latency + cost + 非确定性), 风险也最高, 排第 5 (依赖 v8.2.0 telemetry 数据触发)

**预期 v8.2.0 cycle 规模**: 5 patch / 3 wave / +400-500 tests / +10 EvoBench scenarios / 0 P6 schema bump (5 个候选均为 nested field / 配置改动 / 新模块, 不触 top-level canonical_order; LCP 100% on positions 1-15) / NineS composite 9.05 → ≥9.5 (target G3 release 阈值 9.0/10).

### 8.4 与 v8.0.0 retrospective 的去重策略

§8 的所有内容都是 v8.0.0 retrospective `.local/research/v8.0.0_retrospective.md` 已记录的事实之上的**前瞻 deviation analysis + v8.2.0 候选清单**, 不重复 retrospective 已经覆盖的 13 patch 详情或 12 NineS finding closure 表格 (这些是 retrospective §1.1 + §1.2 + §2 的职责)。本 §8 专注于:

1. **§7 预测 vs v8.0.0 实际的对照** (§8.1 D1-D4) — retrospective 不做对照, 因为它的视角是 "已落地的事实", 而本 §8 的视角是 "原计划是否准确"
2. **v8.1.0 self-analysis 的 NEW 发现** (§8.1 N1-N3) — retrospective 不知道未来的 self-analysis 会跑出什么, 本 §8 是首次承载这些发现的 artifact
3. **Karpathy 的 v3 biweekly 校准** (§8.2) — retrospective 仅记录 v8.0.0 周期内 Karpathy 的稳定性, 本 §8 设定 v8.2.0 触发条件
4. **v8.2.0 候选 5 patch 清单** (§8.3) — retrospective §3 列出大量 deferred 项 (按维度分组), 本 §8 把它们排序压缩到 5 项 ranked candidate, 是 v8.1.0 → v8.2.0 SI-1 planning gate 的直接输入

下游消费者: `.local/research/v8.1.0_gap_analysis.md` 引用本 §8 作为 v8.2.0 candidate list 的源头; `.local/research/v8.2.0_patch_plan.md` (未来 artifact) 把 5 项展开成 5-patch 详细计划。
