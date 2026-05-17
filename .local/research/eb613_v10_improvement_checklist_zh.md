# DevolaFlow v10.x 改进选项清单（基于 EvoBench v6.1.3 反馈）

> **状态：** Phase-0 改进选项清单 — 操作者决策面向，非周期计划
> **来源：** `.local/research/eb613_v10_optimization_proposal.md`（完整提案 886 行）
> **EvoBench 反馈：** `.local/feedbacks/from_evobench/eb613_for_devola_v10.0.0.md`
> **仓库状态：** v10.3.0（commit `f1d9652`，feat/v10.2.0-cycle 分支，PR #117 已开）
> **日期：** 2026-05-04
> **外部工具引用 (S-7)：**
> - DevolaFlow / EvoBench: https://github.com/YoRHa-Agents/DevolaFlow
> - NineS: https://github.com/YoRHa-Agents/NineS
> - Si-Chip: https://github.com/YoRHa-Agents/Si-Chip

---

## §1 总体判断（一段话）

EvoBench v6.1.3 评估 v10.0.0 状态 **HEALTHY**：`q=0.5898 / pr=0.3099`，对比 v9.1.0 **+0.0077 q**，对比 `plan_and_agent` 基线 **+0.245 q（+71%）**。**核心约束**：当前已实现 logistic 拟合上界 **88.1%**（`L=0.6698`），纯 factor lift 顶多再涨 ~0.06-0.08 q（封顶 ~0.65）。**唯一突破口**：扩展 capability 协议覆盖（DevolaFlow 责任范围），而非 factor 调优。**最高优先 3 个 capability 缺位** — `mlops`（gap=0.802）、`long_horizon`（gap=0.792）、`agentic_planning`（gap=0.783），三者在 `workflow-system/agent/` 下**零协议覆盖**，是 R13/R14/R15 的 EvoBench 候选。

---

## §2 9 项改进方向总表（按优先级）

| ID | 方向 | DF 现有覆盖 | 影响估算 (q) | 工作量 | 边界 | 推荐 | 触发版本 |
|---:|---|---|---:|:---:|---|:---:|---|
| **H-1** | Production tier 0% pass-rate 穿透 | 完全缺失（multi-day SOP 无） | DF 单边 +0.05..+0.09；过 50% 阈值需 EvoBench 协调 partial-credit 评分 | **L** | 部分 DF-bound + 部分 EvoBench-bound | ⏸ 暂缓 | v10.5.0+ |
| **H-2** | `mlops` protocol（R13 候选） | 0 处命中 | 条件 +0.04..+0.06（取决 EvoBench R13） | **M** (2 PVs) | DF-bound primary | ✅ 推荐 | v10.4.0 |
| **H-3** | `long_horizon` scaffold（R14 候选） | `agent-workspace.md` 部分覆盖 multi_session，无 multi-day SOP | 条件 +0.04..+0.06（取决 EvoBench R14） | **M** (2 PVs) | DF-bound primary | ✅ 推荐（首发） | v10.4.0 |
| **H-4** | `agentic_planning` 角色（R15 候选） | `plan_and_agent` 仅单遍计划 | 条件 +0.03..+0.05（取决 EvoBench R15） | **M** (1-2 PVs) | DF-bound primary | ✅ 推荐 | v10.4.0 |
| **H-5** | R9/R12 二轮强化 | `gate/reinforcement.py` + `repos` 字段已就绪 | 条件 +0.02..+0.04 | **M** (2-3 PVs) | EvoBench 协调先于 DF 改造 | ⚠ 需协商 | v10.4.0 末段 |
| **M-1** | VeryComplex tier 监测 | 监测项，无新协议 | n/a（仅监测） | **S** (报告) | EvoBench-bound | ✅ 推荐 | v10.4.0 cycle-close 报告 |
| **M-2** | `multi_modal` capability gap | 0 处命中 | 暂时不可估（先 H-2 落地，R16 才考虑） | **0 PVs** | EvoBench-gated | ⏸ DEFER | v10.5.0+ |
| **M-3** | `devolaflow_latest` 别名一致性 | n/a | 0（不影响 DF） | **0 PVs** | EvoBench-bound | ❌ 无需动作 | — |
| **L-1** | 饱和段战略储备 | 已通过 H-2/H-3/H-4 隐式回应 | 包含在 H-2/H-3/H-4 中 | 含于 H-2/H-3/H-4 | DF-bound | ✅（已含 v10.4.0） | v10.4.0 |

**图例：** ✅ 推荐 / ⚠ 需协商 / ⏸ 暂缓 / ❌ 无需动作

---

## §3 各方向核心摘要（按优先级展开）

### §3.1 ✅ H-3 — `long_horizon` 协议（R14 候选）— **建议 v10.4.0 首发**

- **EvoBench 数据：** q=0.208 / gap=0.792 / 48 任务；Bottom-50 任务中 **94% 含此 tag**。
- **DF 提案核心：**
  - **新增** `workflow-system/agent/templates/builtin/long-horizon.yaml`（multi-day workflow 模板）
  - **新增** `workflow-system/agent/references/long-horizon-protocol.md`（Large 阶 ≤1000 行 — 多日 SOP）
  - **扩展** `references/agent-workspace.md` §3 增 §3.5 Long-Horizon Mode（STATUS.yaml 增 1 个可选字段 `long_horizon_mode: bool`，加性变更，字节稳定）
- **验收要点：** multi-day cadence 测试 + checkpoint 自动写入 + session 重启后状态恢复
- **风险：** 无 — 与现有 `agent-workspace.md` 兼容；零新 env flag
- **工作量：** 2 PVs

### §3.2 ✅ H-2 — `mlops` 协议（R13 候选）

- **EvoBench 数据：** q=0.198 / gap=0.802（37 项 capability 中**最高**）；19 任务全 Production tier
- **DF 提案核心：**
  - **新增** `workflow-system/agent/templates/builtin/mlops.yaml`（ML 训练/评估/部署闭环）
  - **新增** `workflow-system/agent/references/mlops-protocol.md`（Large 阶；含 Kaggle awareness、checkpoint resume、grid search orchestration）
  - **扩展** `references/team-roles.md` 增 `mlops_engineer` 团队
  - **扩展** SKILL.md 工作流选择表增 mlops 行
- **验收要点：** Kaggle-style 多日 ML 任务模板可调用 + checkpoint resume 机制 + 与 H-3 long-horizon 联动
- **风险：** 与 H-3 部分重叠 — 必须先 H-3 落地，H-2 才能复用 long-horizon checkpoint
- **工作量：** 2 PVs（强制后于 H-3）

### §3.3 ✅ H-4 — `agentic_planning` 角色（R15 候选）

- **EvoBench 数据：** q=0.217 / gap=0.783 / 32 任务；56% Bottom-50 任务含此 tag
- **DF 提案核心：**
  - **扩展** `references/plan-mode-enforcement.md` 增 §11 multi_horizon_planner 角色（多步策略规划，与 metacognition SOP 互补）
  - **扩展** `references/team-roles.md` 增 `multi_horizon_planner` 团队 / 角色变体
  - **新增** `workflow-system/agent/templates/builtin/multi-horizon-plan.yaml`（多步策略规划模板）
- **验收要点：** 多步策略规划 ≠ 单遍 plan-then-execute；与现有 `plan_and_agent` 共存（不替换）
- **风险：** 较轻 — DF 已有 plan-mode 基础设施，主要是扩展
- **工作量：** 1-2 PVs

### §3.4 ⚠ H-5 — R9 / R12 二轮强化 — **需先与 EvoBench 协商**

- **EvoBench 数据：** R9（convergence）gap_to_one=0.611 / R12（multi_repo）gap_to_one=0.618；两者均已 active 但 quality 仅 0.38-0.39
- **DF 端可做：**
  - 复审 `src/devolaflow/gate/reinforcement.py`（W-8/SI-9 reinforcement primitive）
  - 复审 `schemas/lean-dispatch.yaml#layout_invariant.canonical_order` 第 13 位 `repos` 字段是否够 expressive
  - 评估是否新增协议层（不只是依赖 EvoBench multiplier 上调）
- **EvoBench 端待决：** multiplier 是否提至 1.20+
- **风险：** 触及 `src/devolaflow/gate/` 即触发 W-11（CP-4）gate test suite；A-2 frozen prefix 不可动
- **工作量：** 2-3 PVs；EvoBench 协调成本是主要瓶颈

### §3.5 ⏸ H-1 — Production tier 0% 通过率 — **建议暂缓至 v10.5.0+**

- **EvoBench 数据：** v2..v10 9 代 27 patches × ~510K Production task-trials，pass_rate 始终为 0；最强 cell 也仅 q=0.36 / pass=0.00
- **为什么暂缓：**
  - **DF 单边可推 q 从 0.36 到 ~0.45**，但跨过 0.50 pass_rate 阈值需 EvoBench 改造 partial-credit 评分（**EvoBench-bound**）
  - 与 H-2/H-3 重度重叠（Production capability 集中度：long_horizon 94% / agentic_planning 56% / mlops 36%）— 先做 H-2/H-3/H-4 已涵盖大部分 lift 来源
  - 单独立项需多周期 + EvoBench corpus 协调
- **何时做：** v10.5.0+ — 待 H-2/H-3/H-4 落地后评估剩余增量

### §3.6 ✅ M-1 — VeryComplex tier pass-rate 监测

- **EvoBench 数据：** v7→v10 通过率从 0.019 → 0.087，每代 +0.014-0.035 稳定增长
- **DF 端动作：** v10.4.0 cycle-close `.local/research/v10.4.0_evaluation.md` 加专项 §"VeryComplex 趋势复核"小节（数据驱动报告，无新协议）
- **工作量：** S（仅报告项；0 个专属 PV）

### §3.7 ⏸ M-2 — `multi_modal` capability gap

- **EvoBench 数据：** q=0.357 / gap=0.643 / 10 任务（rank 4）
- **为什么暂缓：** EvoBench 反馈明确说"等 R13 (mlops) 落地后，multi_modal 可作为 R16 候选；DF 端不需现在动作"

### §3.8 ❌ M-3 — `devolaflow_latest` 别名一致性 — **DF 无需动作**

- **EvoBench 数据：** baseline q=0.5643 vs growth q=0.5898，Δ=0.0255（比 v9.1.0 同类差异 0.0028 大 9 倍）
- **EvoBench 反馈明确：** 建议 EvoBench v6.1.4 alias-vs-direct seed audit；**对 DF 无 action**

### §3.9 ✅ L-1 — 饱和段战略储备 — **已隐式包含**

- **核心论点：** v9→v10 +0.0077 q；logistic 拟合预测 v11≈0.621，v12≈0.633。引入 1 个新 R-rule 可见 ~0.02-0.04 非饱和提升（vs 现行 +0.008/代）。
- **DF 端响应：** v10.4.0 通过 H-2/H-3/H-4 已经引入 3 个新 R-rule 触发条件（mlops/long_horizon/agentic_planning），自动覆盖 L-1。**无需独立立项。**

---

## §4 推荐分阶段路径

### §4.1 v10.3.x PATCH 系列（短期、低风险）

- **建议：** 不立项独立 PATCH。本次反馈无适合单 PATCH 完成的项。
- **例外：** 若 H-3 拆出"仅 STATUS.yaml schema 增 `long_horizon_mode: bool` 字段"作为前置 PATCH（不含模板/SOP），可考虑 v10.3.1。**但通常更建议整合入 v10.4.0 PV-01。**

### §4.2 v10.4.0 MINOR 周期（**主推**，6 PV）

| PV | 主题 | 关闭方向 | 预计影响 |
|----|------|---------|---------|
| PV-01 | W-1 SI-1 + W-16 wholesale baseline regen | 周期入口 | n/a |
| PV-02 | **H-3 long_horizon 协议**（含 long-horizon-protocol.md + template + agent-workspace.md §3.5 + 测试） | H-3 | 条件 +0.04..+0.06 (R14) |
| PV-03 | **H-2 mlops 协议**（含 mlops-protocol.md + template + team-roles.md + SKILL.md） | H-2 | 条件 +0.04..+0.06 (R13) |
| PV-04 | **H-4 agentic_planning** 角色（含 plan-mode-enforcement.md §11 + template + team-roles.md） | H-4 | 条件 +0.03..+0.05 (R15) |
| PV-05 | **H-5 R9/R12 复审 + 协议增强**（含 reinforcement.py 评估 + repos 字段评估 + 与 EvoBench 协商记录） | H-5 | 条件 +0.02..+0.04 |
| PV-06 | 周期关闭：W-2 NineS / W-3 SI-3 ≥9.0 STRICT / W-7 retrospective / W-19 archive / M-1 VeryComplex 监测报告 | 周期关闭 | — |

**累计预期影响（条件 EvoBench R13/R14/R15 multiplier 在 1.20-1.30 同步落地）：+0.13..+0.21 q**
**纯 DF 单边（EvoBench 不同步）：+0.04..+0.10 q（infrastructure-only deliverables）**

### §4.3 v10.5.0+ 多周期路径（更深难题）

- **H-1 Production tier 穿透** — 需 multi-cycle DF 工作 + EvoBench 协作改造 partial-credit 评分（双向协商）
- **M-2 multi_modal** — 等 R13 落地、R16 候选化后激活

### §4.4 明确 DEFER

- **M-3 别名一致性**：永久 DEFER，DF 无 action
- **S-11 "Parallel Wave Dispatch Invariant" Soul 规则**：v10.0.0 retrospective §3.5 已 telegraph，本提案**不**与 H-2/H-4 同期评估，避免与 W-3 SI-3 §3.2 ≥9.5 浮顶冲突；按 W-21 2 周期规则改 telegraph 至 v10.4.0 retrospective，最早 v10.6.0 评估

---

## §5 操作者待决问题（决策前提）

| # | 问题 | 影响哪些方向 | 默认（若不选） |
|---|------|--------------|---------------|
| 1 | 是否需要与 EvoBench 协调 R13/R14/R15 multiplier 同步落地？ | H-2/H-3/H-4/H-5 | DF 单边推进，infrastructure 先行；q 提升等 EvoBench 同步 |
| 2 | v10.4.0 是否同时评估 S-11 Soul 候选（W-21 telegraphed）？ | 周期 SI-3 §3.2 浮顶 | 推迟到 v10.6.0（避开撞期） |
| 3 | H-3 STATUS.yaml schema 增字段（`long_horizon_mode: bool`）是否需要单独 v10.3.x PATCH 试点？ | H-3 节奏 | 整合入 v10.4.0 PV-02 |
| 4 | 是否接受 EvoBench-side 改造（partial-credit 评分）作为 v10.5.0 H-1 协作前置？ | H-1 时间表 | 推迟至 v10.5.0 cycle-start 再决定 |
| 5 | 操作者是否有外部 LLM 资源用于真实 with-ability/no-ability 数据生成（影响 Si-Chip OA-1）？ | 与本提案非直接相关，但跨周期协同 | 维持 v10.2.0 的 NineS-as-evaluator 适配器路径 |
| 6 | v10.4.0 cycle-cap 测试函数 W-17 +150 是否有调整空间（H-2+H-3+H-4 三协议测试密集）？ | 周期内 W-17 frugality | 维持 +150；PV-05 mid-cycle audit 必要时 reservoir conserve |
| 7 | 新引用文档（`mlops-protocol.md`、`long-horizon-protocol.md`）是否接受占用 Large 阶 ≤1000 行预算？ | C-4 line budgets | 接受（每文档 ~600-800 行预期） |
| 8 | 是否考虑借用 NineS analyze 在 PV-02..PV-04 之间做协议有效性验证？ | 与 v10.2.0 cycle 经验衔接 | 周期 PV-05 含 NineS deep-analysis 子任务 |
| 9 | 是否在 v10.4.0 PV-01 触发 W-16 wholesale baseline regen？ | W-16 / 基准漂移 | YES（cycle-start MINOR 强制） |
| 10 | 周期闭合后是否对 PR 沿用 v10.2.0 的"feat/v10.4.0-cycle 单分支" 模式？ | 评审节奏 | YES（v10.2.0 已验证有效） |

---

## §6 决策清单（可勾选）

请操作者在审阅后勾选下列项之一或组合：

- [ ] **A. 全部批准** — 按 §4.2 推进 v10.4.0 MINOR 周期（6 PVs，H-3 → H-2 → H-4 → H-5）
- [ ] **B. 部分批准** — 仅做 H-3 + H-2（v10.4.0 减为 4 PVs；H-4/H-5 推迟到 v10.5.0）
- [ ] **C. 最低风险** — 仅做 H-3（v10.3.1 PATCH 试点 STATUS.yaml schema + v10.4.0 PV-02 完整 long-horizon 协议；其他全部推迟）
- [ ] **D. 暂不行动** — 等待更多 EvoBench 反馈周期（next eb614+）后再决策
- [ ] **E. 退回修订** — 列明修订点 → 重新提案

如需进入 SI-1 流程，操作者明确批准后，由 L0 启动 v10.4.0 W-1 gap analysis（路径 `.local/research/v10.4.0_gap_analysis.md`）。

---

## §7 引用

- **完整方案书**：`.local/research/eb613_v10_optimization_proposal.md`（886 行）
- **EvoBench 反馈源**：`.local/feedbacks/from_evobench/eb613_for_devola_v10.0.0.md`
- **W-* 规则**：`.cursor/rules/repo-governance.mdc`（W-1 / W-3 / W-9 / W-16 / W-17 / W-18 / W-19 / W-20 / W-21）
- **A-2 cache-prefix 不变量**：`schemas/lean-dispatch.yaml#layout_invariant`
- **C-4 行数预算分级**：参 `references/decomposition-gate.md` C-4 节
- **外部工具 (S-7)：**
  - DevolaFlow / EvoBench: https://github.com/YoRHa-Agents/DevolaFlow
  - NineS: https://github.com/YoRHa-Agents/NineS
  - Si-Chip: https://github.com/YoRHa-Agents/Si-Chip

---

*本清单为 Phase-0 决策辅助文档；批准任一选项后，即由 L0 触发对应版本的 W-1 SI-1 流程。*
