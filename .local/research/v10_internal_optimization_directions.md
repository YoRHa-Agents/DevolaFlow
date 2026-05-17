# DevolaFlow v10.x 内向型优化方向（修订版）

> **状态：** Phase-0 优化方向（修订版）— 替代 `.local/research/eb613_v10_optimization_proposal.md` 的根本框架
> **修订日期：** 2026-05-04
> **修订理由：** 用户在 2026-05-04 04:53 (UTC+8) 重新校准三条原则：
>   1. 修改边界仅限 DevolaFlow 仓库自身（不得给 EvoBench / NineS / Si-Chip 提对方端建议）
>   2. 不以"通过 EvoBench 考试"为优化目标
>   3. 必须附带详细的调研和搜索方向
> **仓库状态：** v10.3.0（commit `f1d9652`，feat/v10.2.0-cycle 分支，PR #117 已开）
> **外部工具引用 (S-7)：**
> - DevolaFlow / EvoBench: https://github.com/YoRHa-Agents/DevolaFlow
> - NineS: https://github.com/YoRHa-Agents/NineS
> - Si-Chip: https://github.com/YoRHa-Agents/Si-Chip
>
> **本文件不依赖外部工具配合即可全部落地；EvoBench / NineS / Si-Chip 数据仅用作信号引用。**

---

## §1 修订的根本理由（去工具化重新对齐）

上一版 `.local/research/eb613_v10_optimization_proposal.md`（886 行）以 EvoBench v6.1.3 反馈中的 9 个方向（H-1..H-5, M-1..M-3, L-1）为骨架，**H-1..H-5 实际上是 EvoBench `r_rules_status="no rule"` 候选名单的镜像**——`mlops` / `long_horizon` / `agentic_planning` 三个 R13/R14/R15 候选直接成为新增工作流模板与协议的设计目标。这种结构本质上是"为 EvoBench gap_score 关闭而设计"，违反用户两条核心原则：(a) 新增 ML 训练/Kaggle awareness / multi-day SOP 等内容并非 DevolaFlow 作为"通用 workflow meta-framework"必须自带的能力；(b) 评估指标（条件 +0.04..+0.06 q on capability slice）来自 EvoBench multiplier 假设，而不是 DF 内在质量改善的可验证信号。

本次修订**抛弃 H-N 命名体系**，改以 7 个 DF 内部维度组织：

- **D-A 架构健康度**（A-1 4-layer / A-2 cache-prefix / 21 模板谱系是否合理）
- **D-P 协议可演进性**（17-key canonical_order / Soul rule 引入成本 / dispatch schema 复杂度）
- **D-X 开发者/操作者体验**（新建模板/reference/PR 流程的步骤数与摩擦点）
- **D-O 可观测性与自我评估**（三套外部评估器 NineS+SI-3+Si-Chip 的语义重叠）
- **D-Q 代码质量**（NineS PV-03 surface 的复杂度热点 / 上帝函数 / lifecycle hook 分组）
- **D-C 外部工具耦合度**（4 个外部依赖在不可达时 DF 是否仍可工作）
- **D-D 文档与测试体系健康度**（14 个 reference 总 ~9000 行的实际使用率 / W-17 测试膨胀）

每个 §3 方向都通过反问"如果 EvoBench 永远不再发反馈，这条方向是否仍然有内部价值？"来取舍。EvoBench 反馈降级为"外部信号"，仅作"DF 真存在盲区 vs EvoBench 评分方法学问题"的辅助判别。

## §2 与 eb613 EvoBench 反馈信号的去工具化映射

为避免重复劳动并清晰交代上一版方案的处理方式，下表逐条审视 H-1..H-5 / M-1..M-3 / L-1 在新框架下的去向。**判断标准是 DF 内部视角，而非 EvoBench 评分。**

| 原 ID | 原方向（简述） | 信号是否真实存在于 DF 内部？ | 修订归属 | 处理 |
|---|---|:---:|---|---|
| H-1 | Production tier 0% pass-rate（multi-day Kaggle/long-horizon 任务跑不通） | 部分。DF 现有 `change-driven` + `agent-workspace` 已支持长任务断点续做；缺的是"24h+ 跨 session 续接"的明确文档化协议——但这个协议是否值得通用 framework 内置仍可争论 | D-A-3（架构层"通用 framework 是否承担时间尺度专项"）+ D-P-3（schema 是否需要新增字段） | **降级保留**；以"agent-workspace 能力是否被充分使用"切入，而非新增 long-horizon 模板 |
| H-2 | mlops protocol（ML 训练/Kaggle awareness/grid search）缺位 | **否**。DF 是通用 dispatcher + skill orchestrator；ML 协议应该作为下游 skill 由用户写，不应成为 framework 自带模板。引入 `mlops_engineer` 团队会模糊 framework 边界 | — | **完全丢弃**。MLOps 属于下游 skill 的责任，不是 DF 的责任 |
| H-3 | long_horizon scaffold（multi-day cadence + checkpoint resume） | 部分。`agent-workspace.md` §3 + `execution-protocol.md` §2.4 已有 checkpoint 机制；问题不是缺协议，而是缺被使用的证据 | D-D-2（reference 实际使用率） | **重定向**：不新增模板，而是审视现有协议的被使用率与可发现性 |
| H-4 | agentic_planning（multi-step strategic planning）角色 | 部分。`plan-mode-enforcement.md` 已经定义 plan-mode；新增 `multi_horizon_planner` 角色变体 vs 优化现有 plan-mode 是设计取舍 | D-P-4（plan-mode 协议是否过度严格） | **重定向**：不新增角色，而是评估现有 plan-mode 的协议表现力 |
| H-5 | R9/R12 二轮强化（convergence + multi_repo） | 部分。`gate/reinforcement.py` + `repos` 字段已存在；问题是 5-rule cap 与 convergence-heavy profile 的设计是否最佳 | D-Q-3（`feedback.py::generate_round_dispatch` + reinforcement.py 复杂度） | **降级保留**：从代码质量视角审视，而非 EvoBench multiplier 视角 |
| M-1 | VeryComplex tier pass-rate 监测 | 否（纯 EvoBench 端观察项） | — | **完全丢弃**。这不是 DF 内部能改的事 |
| M-2 | multi_modal capability gap | 否（EvoBench R16 候选；DF 不应内置 multi-modal 协议同 H-2 同理） | — | **完全丢弃** |
| M-3 | `devolaflow_latest` 别名一致性 | 否（纯 EvoBench corpus seed audit） | — | **完全丢弃**（用户原版亦标注"DF 无 action"）|
| L-1 | Saturation tail 战略储备 | 否（纯 EvoBench logistic 拟合论） | — | **完全丢弃** |

**总结：**
- 9 项原方向中 **5 项完全丢弃**（H-2 / M-1 / M-2 / M-3 / L-1）
- **4 项以"内部价值"重新论证后保留**，但全部降级或重定向（H-1 → D-A-3 + D-P-3；H-3 → D-D-2；H-4 → D-P-4；H-5 → D-Q-3）

## §3 内向型优化方向（按 DF 内部维度组织）

每个方向反问的关键测试：**如果 EvoBench / NineS / Si-Chip 永远不再发反馈，这条方向是否仍然有内部价值？** ⭐ 标记表示通过此测试且不依赖任何外部工具配合即可独立产生改善。

### §3.1 D-A 架构健康度（Architecture）

**评估问题：**
- DF 4-layer (L0/L1/L2/L3) 设计在 v10.x cycle 实际使用模式下是否仍合理？v10.0.0 → v10.3.0 cycle 实际只用了 L0+L3，L1/L2 几乎没单独存在过（per `v10.0.0_retrospective.md` §2 ledger 与 `v10.3.0_retrospective.md` §2）。
- 22 个 builtin workflow 模板（per `meta-framework.md` §4 表）是否过度细分？
- A-2 cache-prefix v2 + 17-key canonical_order（v9.7.0 PV-02 至 v10.3.0 byte-stable 10 baselines）的复杂度对操作者认知负担是多少？
- A-6 workspace engagement auto-activation 与 `change-driven` 模板（v8.3.0+）的关系是否明确？

#### **D-A-1 ⭐ — L1/L2 实际使用率审计与可能合并**

- **现状证据：** `v10.0.0_retrospective.md` §2 PV ledger 显示 v10.0.0..v10.3.0 共 12 个 PV 中，单独存在的 L1 Stage Agent 与 L2 Wave Agent dispatch 几乎为零；几乎所有任务从 L0 直派 L3。SKILL.md `## 4-Layer Agent Hierarchy` 仍声明 4 层。
- **内部价值（DF 自身受益）：** 若 L1/L2 实际使用率 < 5%，应考虑：(a) 把 L1/L2 标注为"可选层 / 仅大型项目使用"以降低操作者认知；(b) 增加 L1/L2 启用案例的 `examples/*.md`；(c) 评估"Simple shortcut"（已有 `DEVOLAFLOW_SIMPLE_SHORTCUT` flag）是否应默认开启。
- **DF 端可独立完成范围：** 仅修改 `SKILL.md` § Quick Action Decision 表（明确何时 L1/L2 必要）+ 新增 `examples/multi-stage-trace.md` 1 篇 + 评估 `DEVOLAFLOW_SIMPLE_SHORTCUT` 默认值翻转（W-21 类似 PV-06 翻转流程）。
- **工作量：** S（≤1 PV）。
- **调研方向：** → §4.1 LangGraph 状态机抽象、§4.1 CrewAI agent 协作 multi-step 模式对比；§4.5 既有 `S01-T02-orchestration-systems.md` 复用。
- **风险与争议：** 若 L1/L2 在大型项目（≥10 stages）确有价值，简化反而损失能力；建议先实测大型项目的 dispatch 比例，而非仓促重构。

#### **D-A-2 ⭐ — 22 builtin 模板压缩到 12-15 个（按使用率分级）**

- **现状证据：** `meta-framework.md` §4 列出 22 个 builtin templates；`templates/registry.yaml` 注册 22 项；`team-roles.md` §7 7×22 participation matrix 已达视觉极限。CHANGELOG `## [10.0.0]` 与 `## [10.3.0]` 显示 v10.x cycle 实际使用过的模板仅 `change-driven` / `feature-enhancement` / `nines-assisted` / `self-update` / `repo-init`（5 个），其余 17 个使用频率不可知。
- **内部价值：** 减少操作者在 SKILL.md `## Quick Start — Workflow Selection`（22 行表）中的选择疲劳；同时降低 W-12 SKILL adapter build 时的模板序列化成本（每次 `build-skill` 都要校验 22 个 yaml）。
- **DF 端可独立完成范围：** (a) 增加 `scripts/audit_template_usage.py` 扫描 `.local/research/v*_cycle_plan.md` + `CHANGELOG.md` 提取真实使用频率；(b) 把使用频率为零的模板 deprecate（保留 yaml 但 SKILL.md 表中加 "(legacy)"）；(c) 把高频近邻模板合并成参数化的 1 个（如 `documentation-only` + `onboarding` + `dependency-setup` 是否可融合为 `init-suite`）。
- **工作量：** M（2 PV：审计 PV + 合并 PV）。
- **调研方向：** → §4.1 OpenSpec 4 阶段 propose→apply→verify→archive vs DF 22 模板对比；§4.4 Bazel/Nix DSL 中"少量原语 + 组合"哲学；§4.5 既有 `v8.3.0_openspec_deep_analysis.md` 复用（OpenSpec 用单一 propose/apply/verify/archive 模板覆盖了所有 change scope）。
- **风险：** 模板谱系折叠后可能损失 niche 用例的语义清晰度；需保留 deprecation 路径（先弱化、半个 cycle 后再删）。

#### **D-A-3 — A-1 4-layer hierarchy 与时间尺度的"通用 vs 专项"取舍**

- **现状证据：** SKILL.md §"Workspace Engagement" + `agent-workspace.md` §3 已支持跨 session 的 change folder + handoff envelope（S-9 append-only）。但 14 个 reference 中没有任何一篇明确"L0 在恢复 24h 之前的 change folder 时该读什么"。
- **内部价值：** 不需要新增 long-horizon 模板（避免 H-1 陷阱），仅在 `agent-workspace.md` §6 现有协议上加一段"Resume protocol"，覆盖"已有 active change folder + 操作者隔日返回"场景的 L0 动作。
- **DF 端可独立完成范围：** 在 `agent-workspace.md` 新增 §3.6 "Resume After Pause" 约 100-150 行；不新增 schema 字段、不新增模板。
- **工作量：** S（≤0.5 PV）。
- **调研方向：** → §4.1 Temporal / Restate "durable workflow" 设计哲学（任务暂停-恢复语义）；§4.2 long-context 类论文族；§4.5 既有 `agent-workspace.md` 已有内容审计。
- **风险：** 边界与 H-1 重叠——必须明确"DF 仅文档化已有的 resume 能力，不新增任何 long-horizon 专项 SOP"。

#### **D-A-4 — A-6 workspace activation 在两类边缘条件下的清晰度**

- **现状证据：** A-6 规定 `DEVOLAFLOW_AGENT_WORKSPACE=1` AND complexity ≥ STANDARD 触发自动 scaffold；`v9.1.5` PV-05 默认 ON（per `env-flags.md` §2.11）。但 `repo-governance.mdc` A-6.3 提到 `--no-change` opt-out 是"唯一 opt-out 通道"——若操作者忘记 opt-out 而在小修复时也开了 workspace，会带来 unnecessary 的 .local/.agent/active 目录创建。
- **内部价值：** 优化 A-6.1 classify_complexity 的 SIMPLE/TRIVIAL 检测（per `change_activation.py`）使其更敏感，把更多任务分流到 NO_CHANGE 而不是 SHOULD_OPEN_CHANGE；降低不必要的 scaffold 噪音。
- **DF 端可独立完成范围：** 调整 `src/devolaflow/skills/change_activation.py` 阈值；新增测试覆盖边界。
- **工作量：** S（≤1 PV）。
- **调研方向：** → §4.4 pre-commit hook 工具（husky/lefthook/pre-commit）的"何时跳过"策略；§4.5 既有 `change_activation.py` 测试集复用。
- **风险：** 阈值过宽可能让大型任务漏开 workspace，损失审计能力；需用历史 12 个 PV 的真实 complexity 分布做基准。

### §3.2 D-P 协议可演进性（Protocol Evolution）

**评估问题：**
- A-2 frozen prefix（位置 1-12 不可动）+ append-only tail（位置 13-17）的设计，4 个 cycle（v9.0..v10.3）后是否累积出可合并的字段？
- Soul rule 引入成本（W-21 2 周期 telegraph + SI-3 §3.2 ≥9.5/10）是否已成"实质性禁止"？v10.0.0 retrospective §3.5 与 v10.3.0 retrospective §5 都未推进 S-11，是否说明门槛过高？
- Dispatch schema (lean-dispatch.yaml) 17 个顶层字段，对 L3 Task Agent 的认知负担有多大？
- Lifecycle hook 现已 10 个事件（per `v10.3.0_retrospective.md` §6 metrics），未来增长曲线是否值得规划？

#### **D-P-1 ⭐ — A-2 canonical_order 17 个字段的"可合并"审计**

- **现状证据：** `schemas/lean-dispatch.yaml` v6 含 17 个顶层字段（v8.3.0 PV-05 时为 16；v9.7.0 PV-02 加 1）。A-2.3 NEST-vs-APPEND 决策矩阵在 v9-ADR-002 中给出，但实际 17 个字段中有几个其实可以 NEST 而被 APPEND 了？
- **内部价值：** 减少每次 dispatch 的 prefix 序列化字节数（即使 1 个字段合并也意味着更短 cache prefix → 更高 cache hit rate）；降低 L3 Task Agent 阅读 dispatch payload 的认知负担。
- **DF 端可独立完成范围：** 增加 `scripts/audit_canonical_order.py` 扫描 17 字段的实际使用率（哪些字段在 80%+ 的 dispatch 中为空？），输出"候选 NEST 报告"。审计本身**不动 schema**——仅产出建议。如未来 cycle 决定执行合并，则走 A-2 多基线字节测试。
- **工作量：** S（仅审计；≤0.5 PV）。
- **调研方向：** → §4.1 Anthropic prompt caching 设计（哪些 cache 字节最值得节省）；§4.4 LLM API cached input 设计（OpenAI v1 cached_input）；§4.5 既有 `v9-ADR-002-cache-layout-governance-v2.md` 完整复用。
- **风险：** 字段合并可能违反 A-2.1 frozen prefix（虽然合并发生在 tail），需要 A-2.4 multi-baseline byte test 全绿——审计阶段不触及，仅产出报告。

#### **D-P-2 — Soul rule 添加门槛（W-21）的实证检验**

- **现状证据：** W-21 要求 S-11 候选必须经过 2 周期 telegraph + SI-3 §3.2 ≥9.5/10。v10.0.0 retrospective §3.5 telegraph 了 "Parallel Wave Dispatch Invariant"；v10.2.0 cycle 评估**OUT**（gap analysis §3.6 D-W-1）；v10.3.0 retrospective §5 又重新 telegraph 至 v10.4.0。这个候选已在 retrospective 链中漂浮 4 个 cycle 仍未落地。
- **内部价值：** 不是放宽门槛，而是审视"telegraph 不立项"的根本原因——是 Soul rule 设计哲学排斥这条规则，还是 W-21 流程压力大？若是后者，可考虑增加"Soul-eligible 但暂不立项"的中间态（A-* 架构规则的位置）。
- **DF 端可独立完成范围：** 仅在本次研究文档中分析；不修改 W-21 规则本身。如果分析发现 W-21 门槛过高/过低，提交至下一 cycle SI-1 讨论。
- **工作量：** S（仅文档；≤0.3 PV）。
- **调研方向：** → §4.1 NixOS RFC / Rust RFC 类项目的"提案漂浮"机制研究；§4.5 既有 `v9-ADR-007-rule-rebalancing-and-rollup.md` 与 `v9.0.0_pv05_design.md` 复用。
- **风险：** 此方向有"对治理流程提建议"风险——必须明确仅给出问题陈述，不擅自改 W-21。

#### **D-P-3 — STATUS.yaml schema 的"延展性测试"**

- **现状证据：** `schemas/agent-workspace/change-status.yaml` v1（v8.3.0 引入；3.0 通过 `agent_workspace/lint.py` 测试）。v8.3.0 至 v10.3.0 跨 ~14 个 minor cycle，schema **未变**。这意味着两件事之一：(a) 设计完美无需迭代；(b) 操作者已经习惯不去碰它。
- **内部价值：** 增加一个最小可选字段（如 `last_handoff_envelope_seq`）的 schema 延展性 demo，证明"加字段是廉价的"；这反过来鼓励未来 cycle 的协议改进。
- **DF 端可独立完成范围：** 仅在 `schemas/agent-workspace/change-status.yaml` 加可选字段；运行 lint 测试 + 兼容性回归。
- **工作量：** S（≤0.5 PV）。
- **调研方向：** → §4.1 OpenSpec `openspec/config.yaml` 的字段演进史（per `v8.3.0_openspec_deep_analysis.md`）；§4.5 既有 `agent-workspace.md` §4 schema table 复用。
- **风险：** 加字段一旦加错（命名、类型）回滚需要 deprecation cycle；建议从最低风险的 metadata-only 字段开始。

#### **D-P-4 — plan-mode 协议的"多步推理"原生支持评估**

- **现状证据：** `plan-mode-enforcement.md` §3 当前的 plan-mode 是 single-pass 的（plan-then-execute）；H-4 提出 "multi_horizon_planner" 角色对应"多步策略规划"。但用户已明确丢弃 H-4 的角色化路径——问题应该转化为"现有 plan-mode 是否足以承载多步思考"。
- **内部价值：** 评估 `plan-mode-enforcement.md` §3 plan template 的字段表达力（horizon / revision / uncertainty 是否需要原生槽位），如果"多步"是协议表达问题而非角色问题，则在现有 plan template 上小改即可。
- **DF 端可独立完成范围：** 在 `plan-mode-enforcement.md` §3 加一个 §3.2 "Multi-Step Plans"，约 100 行，仅是文档化已有能力（plan template 中已经支持 stages 列表，理论上每个 stage 可以是一个 horizon）。
- **工作量：** S（≤0.5 PV）。
- **调研方向：** → §4.1 LangGraph 多步规划节点设计；§4.2 hierarchical multi-agent planning 论文族；§4.5 既有 `plan-mode-enforcement.md` 复用。
- **风险：** 文档化已有能力 vs 引入新协议字段的边界要清晰；本方向限于文档化。

### §3.3 D-X 开发者/操作者体验（Developer / Operator Experience）

**评估问题：**
- 操作者新建一个 workflow 模板需要多少步骤？是否有 scaffold 工具？
- 操作者新建一个 reference doc 的链条（写正文 + SKILL.md 索引 + build-skill + W-18 ghost-audit + ST-1 docs sync）是否过长？
- W-9 SI-10 7-gate 序列对每个 PR 都跑——是否有 fast-path 优化？
- v10.2.0 cycle 6 PV 的 PATCH 爬升模式是否合理？

#### **D-X-1 ⭐ — Workflow 模板 scaffold CLI**

- **现状证据：** 当前新建一个 builtin workflow template 需手工：(1) 写 `templates/builtin/<name>.yaml`；(2) 注册到 `templates/registry.yaml`；(3) 在 `meta-framework.md` §4 Alias Mapping Table 加行；(4) 在 SKILL.md `## Quick Start` 表加行；(5) 在 `team-roles.md` §7 participation matrix 加行；(6) 写测试 `tests/test_<name>_template.py`；(7) 跑 `build-skill` 验证 4 adapter；(8) 加 W-18 ghost-audit lint；(9) 加 CHANGELOG 行。9 步全人工。
- **内部价值：** 一个 `python -m devolaflow.scripts.scaffold_template <name> --primitives <list>` CLI 自动化前 5 步 + 生成 6 步骤 stub，操作者只需补内容。直接降低新建模板的摩擦——而模板是 framework 扩展性的关键。
- **DF 端可独立完成范围：** `scripts/scaffold_template.py`（约 200 LOC，参数化生成 yaml + 注入到 registry/meta-framework/SKILL/team-roles/test/changelog stub）；附 6-8 个测试。
- **工作量：** M（1 PV）。
- **调研方向：** → §4.1 cookiecutter / Yeoman / `npm init` scaffold 工具设计哲学；§4.4 vim plugin manager / VS Code yo extension generator；§4.5 既有 `scripts/install.sh` 复用作为参考。
- **风险：** scaffold 输出的 stub 与人工 review 的边界——需要明确 stub 不能默认 commit，必须人工补全。

#### **D-X-2 ⭐ — Reference doc 创建链路压缩**

- **现状证据：** SKILL.md `## Reference Navigation Guide` 列 14 个 Tier-2 references（含 `agent-workspace.md` 第 10 个，v8.3.0+ 加入）。新建第 15 个 reference 需要：(1) 写 `references/<name>.md` ≤1000 行；(2) 加到 SKILL.md Reference Navigation Guide；(3) 加到 `scripts/sync_cursor_skill.py` MIRRORED_FILES（per SF-3）；(4) `tests/test_reference_size_budgets.py` 自动覆盖（已 parametrize，零配置）；(5) `tests/test_integration.py::test_skill_md_under_500_lines` 验证；(6) `tests/test_no_ghost_features.py` W-18 lint；(7) `make sync-cursor-skill` 同步。7 步中 (1)、(2)、(3)、(6) 是人工。
- **内部价值：** 把 (3) 自动化（让 sync_cursor_skill.py 从 SKILL.md 导航表反推 MIRRORED_FILES）+ (6) 自动化（W-18 lint 模板生成）。每篇新 reference 节省 ~10 分钟+减少漏改风险。
- **DF 端可独立完成范围：** 修改 `scripts/sync_cursor_skill.py` 从 SKILL.md Reference Navigation Guide 表中自动提取 MIRRORED_FILES；新增 `scripts/scaffold_reference.py` 生成 reference + W-18 lint stub。
- **工作量：** M（1 PV）。
- **调研方向：** → §4.1 OpenSpec config.yaml 中"工具适配自动同步"（per `v8.3.0_openspec_deep_analysis.md`）；§4.4 cookiecutter 嵌套模板；§4.5 既有 `scripts/sync_cursor_skill.py` 复用。
- **风险：** 自动反推 MIRRORED_FILES 若导航表书写不规范会失败；需先严格化 SKILL.md 表格式（一次性整理）。

#### **D-X-3 — W-9 SI-10 fast-path（PR 级别 vs cycle 级别）**

- **现状证据：** W-9 SI-10 7 步（pytest / ruff check / ruff format / test_version / test_benchmarks / make check-cursor-skill + iteration_delta）。v10.2.0 cycle 6 个 PV 全部跑了完整 7 步——每次 PV 大约 5-10 分钟。
- **内部价值：** 区分 "PR 内 commit"（运行轻量 fast-path：pytest -x + ruff check）vs "PV close"（运行完整 7 步）。可显著减少 PV 内部迭代延迟。Conformance 不变，只是 incremental 与 final 区分。
- **DF 端可独立完成范围：** 增加 `Makefile` target `precommit-fast`（仅 pytest -x 上次失败的 + ruff check changed-only）；将完整 7-gate 重命名为 `precommit-full`；文档化使用场景。
- **工作量：** S（≤1 PV）。
- **调研方向：** → §4.4 pre-commit framework 的 stage 设计（push vs commit vs manual）；husky 的 pre-commit/pre-push 区分；§4.5 既有 `Makefile` 复用。
- **风险：** fast-path 与 full-path 的语义边界——必须明确"final commit before PR open" 必须跑 full。

#### **D-X-4 — PR 流程的 cycle-vs-PV 对齐**

- **现状证据：** v10.2.0 cycle 在 `feat/v10.2.0-cycle` 分支跑了 6 个 PV 共 6 个 commit；最终 1 个 PR (#117) 包含全 6 commit。retrospective §4.6 称这是"single feature branch + draft PR throughout the cycle"模式。但每个 PATCH PV 都做了 canonical-7 sync + CHANGELOG 行 + bump version——形成 6 个 version bump 但只有 1 个 PR review surface。reviewer 视图变得很重。
- **内部价值：** 评估"cycle-as-PR" vs "PV-as-PR"两种节奏的取舍；明确 reviewer load 与 cycle 速度的权衡。本方向不强制改流程，仅产出决策文档。
- **DF 端可独立完成范围：** 一份分析文档（约 200 行），统计 v9.0.0..v10.3.0 cycle 的 PR 大小、review 时长、回归率。
- **工作量：** S（仅文档；≤0.5 PV）。
- **调研方向：** → §4.3 大型公司（Stripe、Shopify）的 Internal PR 大小研究；§4.4 git workflow patterns（feature-branch vs trunk-based）；§4.5 既有 cycle retrospectives 复用。
- **风险：** 改 PR 流程是高风险（影响所有未来 cycle）；本方向只产出分析，不改流程。

#### **D-X-5 ⭐ — 操作者错误诊断手册**

- **现状证据：** v10.0.0 retrospective §4.2 列了 4 个"didn't work as smoothly"问题（dataclass + spec_from_file_location pitfall, _grep_symbol fragility, demo/index.html "automated" lint trip, ruff check scripts/ drift）。这些都是操作者首次踩坑学会的经验。但没有集中文档化。
- **内部价值：** 整理一份 `references/troubleshooting.md`（Large tier ≤1000 行，作为第 15 个 reference）汇集所有常见错误 + 排错路径，避免每个新操作者重复踩坑。
- **DF 端可独立完成范围：** 扫描所有 cycle retrospective §4.2 段落 + Si-Chip dogfood pass 报告 + ghost-audit failure 案例，提取 ~30 个常见错误；写成 troubleshooting reference；用 D-X-2 的 scaffold 自动化注入。
- **工作量：** M（1 PV，主要工作量在内容整理）。
- **调研方向：** → §4.3 Anthropic Cookbook / OpenAI Cookbook troubleshooting 章节设计；§4.1 superpowers 的 "rationalization prevention" 表格设计（per `karpathy_skills_analysis.md`）；§4.5 全部 retrospective 复用。
- **风险：** 第 15 个 reference 会触发 SF-1 14 文件 fixed-set 重审；可能需先扩展 SF-1 允许 troubleshooting 作为新 tier 或合并到现有 reference。

### §3.4 D-O 可观测性与自我评估机制（Observability & Self-Assessment）

**评估问题：**
- 三套外部评估器：NineS (overall composite 0.907) + W-3 SI-3 (composite 9.385/10) + Si-Chip iteration_delta (+0.9) — 语义重叠多少？是否有"meta-评估器"统一？
- W-3 SI-3 6 维度（code_quality / arch / tests / maintainability / compat / perf）全部靠 L3 task agent 主观打分——可重复性如何？
- W-19 cycle archive 仅在 cycle close 触发，中间 PV 的研究产物索引是否有更轻量方案？
- v10.2.0 cycle 增加 7th SI-10 step（iteration_delta gate）— 几个 PV 后这套 gate chain 是否会膨胀失控？

#### **D-O-1 ⭐ — 三评估器语义重叠分析**

- **现状证据：** v10.0.0 evaluation §1 给出 SI-3 composite 9.20；§5 给出 NineS 0.907 overall。v10.3.0 evaluation §1 给出 SI-3 9.385；NineS 0.906；Si-Chip iteration_delta +0.9。三个分数同时出现在每个 cycle close，但维度交叉关系（NineS hygiene_mean 0.796 vs SI-3 maintainability 9.20——它们度量同一个东西吗？）从未明确过。
- **内部价值：** 一份 `references/evaluator-rosetta.md`（Large tier ≤1000 行）明确每对评估器维度的对应关系（covers / overlaps / orthogonal），让操作者读 v10.X.0_evaluation.md 时能立即知道哪个维度被几个评估器覆盖。同时识别冗余指标可在未来 cycle 简化。
- **DF 端可独立完成范围：** 分析现有 evaluation 文档（v10.0.0 / v10.3.0 / v9.7.0 三份）的维度交叉，产出 rosetta 表格；新增 `references/evaluator-rosetta.md`。本方向**不修改任何评估器代码**——只是文档化 mapping。
- **工作量：** M（1 PV，主要在分析）。
- **调研方向：** → §4.2 multi-axis evaluation systems 论文族；§4.3 model-eval benchmark 的多维度对齐（如 HELM / BIG-bench）；§4.5 既有 `nines_v2_analysis.md` + `v9.0.0_decomposition_analysis.md` 复用。
- **风险：** 若 mapping 揭示真冗余（如 NineS lint_cleanliness 与 SI-3 code_quality.lint 完全重叠），可能引发"是否取消其中一个"的争论——本方向仅做映射，不主张取消。

#### **D-O-2 — SI-3 6 维度的"自动采集"可行性研究**

- **现状证据：** W-3 SI-3 6 维度（code_quality 0.20 / arch 0.20 / tests 0.20 / maintainability 0.15 / compat 0.10 / perf 0.15）当前全靠 L3 task agent 主观写 1-10 分的"justification"段落（per `v10.3.0_evaluation.md` §1 表）。重复性差（同一 cycle 两个 L3 可能给出不同分）。
- **内部价值：** 自动化采集**可量化**部分（如 code_quality.lint = 100 - blocker×25 / perf = benchmark composite delta），保留主观 justification 仅给"非线性维度"（如 arch 合理性）。可重复性提升 → 历史 cycle 比较有意义。
- **DF 端可独立完成范围：** 增加 `scripts/auto_collect_si3_metrics.py` 跑 ruff/pytest/cov/benchmark/W-4 输出 6 维度的"客观分量"；与 L3 主观分量做加权（如 0.6 客观 + 0.4 主观）。
- **工作量：** M（2 PV：脚本 + 与 L3 dispatch 集成）。
- **调研方向：** → §4.2 LLM-as-judge 类论文（如何避免主观漂移）；§4.3 SonarQube / CodeClimate 的多维度自动评分；§4.5 既有 `scripts/generate_si3_evaluation.py` 复用（已有部分自动采集骨架）。
- **风险：** 客观与主观的权重选择——若客观权重过高，可能丢失"架构合理性"的判断；建议从 0.3 客观 / 0.7 主观开始迭代。

#### **D-O-3 — 中间 PV 研究产物的轻量索引**

- **现状证据：** W-19 cycle archive 仅在 cycle close 时触发（per `repo-governance.mdc` W-19）；中间 PV 的研究产物（`.local/research/v10.2.X_*.md`）只在 .gitignore 中。如果操作者在 PV-04 时想找 PV-02 的设计文档，需要手动 grep `.local/research/`。
- **内部价值：** 增加一个轻量"in-cycle research index"——`.local/.agent/REPORT.md` 或 `.local/research/INDEX.md` 自动维护当前 cycle 已产出的研究文件清单（按 PV 分组）。无需 commit；纯本地导航辅助。
- **DF 端可独立完成范围：** 修改 `src/devolaflow/agent_workspace/reporter.py::render_workspace_report` 增加 "Research artifacts (this cycle)" 段落（扫描 `.local/research/v<current-version>_*.md`）。
- **工作量：** S（≤0.5 PV）。
- **调研方向：** → §4.1 OpenSpec `archive/` index 设计（per `v8.3.0_openspec_deep_analysis.md`）；§4.5 既有 `agent_workspace/reporter.py` 复用。
- **风险：** Research index 与 W-19 cycle archive 的边界——必须明确 in-cycle index 是 ephemeral，cycle archive 是 committed。

#### **D-O-4 — SI-10 gate chain 增长曲线与膨胀预警**

- **现状证据：** v10.0.0 SI-10 6 gates；v10.2.0 PV-02 增加 iteration_delta gate 到 7 个。CHANGELOG `## [10.3.0]` 提及"telegraphed for v10.4.0 to formalize as W-9 step #7"。每加一个 gate 都增加 PV 时长 + commit cycle 时长。
- **内部价值：** 评估 SI-10 gate chain 的增长曲线（v8.0 → v10.3 增加了几个？）；提前识别"何时该重组而非追加"。可能的重组方向：把"基础 hygiene"（pytest/ruff/format/version/cursor-skill mirror = 5 个）vs"validation"（benchmarks/iteration_delta = 2 个）分两组并行。
- **DF 端可独立完成范围：** 一份分析文档；提议未来 cycle 把 gate chain 分组并行（仅文档；不改 Makefile）。
- **工作量：** S（仅文档；≤0.5 PV）。
- **调研方向：** → §4.4 pre-commit framework 的 hooks 分组设计；§4.3 GitHub Actions matrix 的并行化策略；§4.5 既有 `Makefile` + `repo-governance.mdc` W-9 复用。
- **风险：** 改 SI-10 是 W-9 governance 改动；本方向仅产出分析与提议。

### §3.5 D-Q 代码质量与复杂度热点（Code Quality）

**评估问题：**
- v10.2.2 PV-03 NineS 报告 4 个 plugins/installer.py 复杂度警告——v10.2.4 关掉了 1 个，v10.2.3 关掉 2 个，剩下的何时清？
- `src/devolaflow/feedback.py::generate_round_dispatch` 是否过于"上帝函数"？
- Lifecycle hook 现 10 个事件——是否应分组（pre_/post_/validate_）？
- `src/devolaflow/compressor/` v9.3.0 PV-04 拆分后是否结构稳定？

#### **D-Q-1 ⭐ — v10.2.2 NineS 剩余 7 个 warning 的清理**

- **现状证据：** `v10.2.2_nines.md` §2 列 10 个 warning-class CC 警告；§5 标记 PV-04/PV-05 候选 3 个；其余 7 个为"v10.4.0+ 候选"。具体：`test_on_complete::_try_persist_session_state` (CC=20)、`auto_write_handoff::_extract_layers` (CC=16)、`pre_plugin_invocation::_extract_plugin_ids` (CC=16)、`installer::ensure_plugin` (CC=14)、`auto_write_handoff::auto_write_handoff` (CC=12)、`installer::plugins_for_workflow` (CC=11)、`installer::resolve_plugin` (CC=11)。
- **内部价值：** 直接降低代码维护成本；每条修复都是 mechanical refactor（无行为变更）；减少未来 NineS 报告噪音。
- **DF 端可独立完成范围：** 7 个独立的 helper 抽取 PV，每个 PV 一个；测试覆盖现成（`test_on_complete.py` / `test_auto_write_handoff.py` / `test_pre_plugin_invocation.py` / `test_runtime_plugins_smoke.py` 已经覆盖所有分支）。
- **工作量：** L（7 PV；可分散到多个 cycle）；或 M（合并 3 个文件的 helpers 在 2 PV 完成）。
- **调研方向：** → §4.2 cyclomatic complexity threshold 论文族（10 vs 15 业内常见基准）；§4.3 Google C++ style guide 的函数长度限制；§4.5 既有 `v10.2.2_nines.md` + `v10.2.3_iteration_round1.md` + `v10.2.4_iteration_round2.md` 复用模式。
- **风险：** Helper 抽取过度可能增加调用 overhead；每个 PV 都要 radon B-rated 验证。

#### **D-Q-2 ⭐ — `feedback.py::generate_round_dispatch` 上帝函数审计**

- **现状证据：** `feedback.py::ProposalGenerator.generate_round_dispatch` 是 S-10 的中央分发函数（per `repo-governance.mdc` S-10：v8.4.4 PV-04 codified）。它要做：(a) 拼接 dispatch payload；(b) 应用 reinforcement；(c) 过 pre_dispatch hook chain；(d) 过 post_dispatch hook chain；(e) 校验 layout invariant；(f) emit 至 L3。这 6 个职责揉在一个函数里。
- **内部价值：** 拆解为 ProposalBuilder（构造）+ ProposalEmitter（hook + emit）两个类，提升可测性 + 单元测试粒度；S-10 hook 触发可单独测；不影响行为。
- **DF 端可独立完成范围：** 重构 `src/devolaflow/feedback.py`；保持公共 API `generate_round_dispatch` 行为不变（外部调用方不感知）。CP-4 / W-11 不触发（feedback.py 不在 gate/ 模块）。
- **工作量：** M（1 PV：refactor + 现有 test 全绿）。
- **调研方向：** → §4.2 god object refactoring patterns 论文族；§4.3 Martin Fowler "Refactoring" Extract Class；§4.5 既有 `feedback.py` + `tests/test_dispatch_emission_runs_hooks.py` 复用。
- **风险：** S-10 是 Soul rule，重构 generate_round_dispatch 时必须确保 hook chain 仍 100% 触发；建议保留旧函数为 thin wrapper 1 个 cycle 后再删。

#### **D-Q-3 — Lifecycle hook 10 事件的分组与生命周期标注**

- **现状证据：** `lifecycle/__init__.py::DEFAULT_EVENTS` 含 10 events（v10.3.0 stable per `repo-governance.mdc` S-10 + `env-flags.md` §2.13/2.14）。命名混杂：`pre_dispatch`, `post_dispatch`, `pre_handoff`, `pre_plugin_invocation`, `post_skill_edit`, `pre_shell_call`, `validate_dispatch`, `check_file_ownership`, `test_on_complete`, `check_envelope_append_only`. 缺统一前缀规则。
- **内部价值：** 重整命名（统一 `pre_*` / `post_*` / `validate_*` / `check_*` 4 组），提升可发现性；不影响行为（旧名保留为 alias 1 cycle）。
- **DF 端可独立完成范围：** 重命名 + alias 维护；更新 `references/env-flags.md` + `references/plan-mode-enforcement.md`。
- **工作量：** S（≤1 PV）。
- **调研方向：** → §4.4 husky / lefthook hook 命名规范；Anthropic Skills hook lifecycle naming；§4.5 既有 `lifecycle/__init__.py` 复用。
- **风险：** 改名涉及外部钩子注册者；必须做 1 cycle alias 兼容。

#### **D-Q-4 — `compressor/` 拆分后的目录健康度**

- **现状证据：** `compressor/` 在 v9.3.0 PV-04 拆分（per CHANGELOG）。v10.2.2 NineS 仅分析了 `si_chip_bridge / plugins / lifecycle` 3 个包；compressor/ 未被深度分析。
- **内部价值：** 给 compressor/ 跑 NineS deep-analyze（W-2 / SI-2 标准动作），获取一份新鲜的健康度快照；识别是否有新的 CC 热点。
- **DF 端可独立完成范围：** 仅运行 `nines analyze --target-path src/devolaflow/compressor/ --depth deep --agent-impact --keypoints`；输出至 `.local/research/v10.4.X_compressor_nines.md`。
- **工作量：** S（≤0.3 PV）。
- **调研方向：** → §4.5 既有 `v10.2.2_nines.md` 模板复用。
- **风险：** 此方向依赖 NineS 可用——如果 NineS 不可达，可手动 radon 替代（per W-2 manual fallback）。

### §3.6 D-C 外部工具耦合度（External Tool Coupling）

**评估问题：**
- DF 现依赖 4 个外部工具（NineS / Si-Chip / RTK / ui-pro）— 任一上游不可达时 DF 是否仍可工作？
- v10.2.0 PV-03 的 si_chip_bridge `MetricsReport.from_yaml_dict` bridge defect — 桥接层是否应有版本协商协议？
- W-2 NineS 在 cycle 流程中是必经步骤——是否应作为可选 enhancement？
- `pre_plugin_invocation` lifecycle hook 同时管 install + 24h upgrade — 职责过度集中？

#### **D-C-1 ⭐ — 上游不可达时的 DF 行为契约**

- **现状证据：** `runtime-plugins.yaml` 注册 4 个 plugins（per `v10.3.0_retrospective.md` §6 metrics）。当 NineS / Si-Chip / RTK / ui-pro 任一上游 GitHub repo 不可达（network、rate-limit、repo-rename 之一），DF 当前行为：(a) `pre_plugin_invocation` 抛异常或静默？(b) `post_skill_edit` Si-Chip dogfood DEFER？(c) `nines analyze` 在 W-2 流程中失败？(d) cycle 是否能继续？这些边界目前未明确文档化。
- **内部价值：** 一份明确的"degraded mode"契约 + 测试覆盖。即使所有上游都不可达，DF 自身（dispatch / gate / change-driven workflow）应仍可工作。
- **DF 端可独立完成范围：** (a) 加 `references/degraded-mode.md`（Large tier ≤1000 行）文档化每个外部工具不可达时的 fallback；(b) 加测试 `tests/test_degraded_mode.py` 模拟 4 种不可达场景。
- **工作量：** M（1-2 PV）。
- **调研方向：** → §4.1 Temporal "durable execution" + circuit breaker 设计；§4.4 PyPI mirror fallback / Docker pull retry；§4.5 既有 `installer.py` retry 逻辑复用。
- **风险：** Degraded mode 文档可能给操作者错误的"可以离线"印象——必须明确"degraded ≠ 全功能"。

#### **D-C-2 ⭐ — 桥接层版本协商协议**

- **现状证据：** v10.2.3 (`MetricsReport.from_yaml_dict` MVP-8 nested-key support) 是 Si-Chip 协议升级时 DF 桥接层产生的 defect；用 unit test 没发现，end-to-end dogfood 才暴露（per `v10.2.3_iteration_round1.md`）。这种 silent shape mismatch 在未来 Si-Chip / NineS / RTK 升级时会重复出现。
- **内部价值：** 给 4 个外部工具的桥接层加一个轻量"shape contract test"——每次 cycle close 跑一次 e2e 真实输出（cached fixture），shape 不符立即 alert。比单 fixture 更敏感。
- **DF 端可独立完成范围：** 在 `tests/integration/` 下增加 `test_<tool>_shape_contract.py`（4 文件）+ 缓存 fixture 在 `tests/integration/fixtures/<tool>/`；CI 偶发跑（如 weekly schedule）。
- **工作量：** M（1 PV）。
- **调研方向：** → §4.4 contract testing（Pact / Spring Cloud Contract）；§4.3 schema registry（Confluent / Apicurio）；§4.5 既有 `si_chip_bridge/runner.py` 复用。
- **风险：** 缓存 fixture 的更新节奏——必须明确"何时刷新缓存"，否则缓存本身变成新的 defect 来源。

#### **D-C-3 — `pre_plugin_invocation` 职责拆分**

- **现状证据：** `pre_plugin_invocation` lifecycle hook 同时管：(a) auto-install plugin if missing (`DEVOLAFLOW_AUTO_INSTALL_PLUGINS`)；(b) 24h staleness check + auto-upgrade（v10.2.1 PV-02 加入 D-P-2 closure）。两个责任在一个 hook 里——v10.2.3 NineS 报告该函数 CC=18 → 折成 helper 后 CC=10（per `v10.2.3_iteration_round1.md`）。
- **内部价值：** 拆成 2 个 lifecycle event：`pre_plugin_invocation_install` 和 `pre_plugin_invocation_upgrade`，操作者可独立 opt-in/out（一个想 auto-install 但不要 daily upgrade 的用户当前没法做到）。
- **DF 端可独立完成范围：** 修改 `lifecycle/__init__.py::DEFAULT_EVENTS`（A-2.2 append-only：在 11/12 位置追加新事件，保留 9 位 `pre_plugin_invocation` 兼容）；`pre_plugin_invocation.py` 拆 2 个 handler。
- **工作量：** M（1 PV）。
- **调研方向：** → §4.4 husky pre-commit vs pre-push 分离；§4.3 Anthropic Claude Code lifecycle hook taxonomy；§4.5 既有 `pre_plugin_invocation.py` + `env-flags.md` §2.13 复用。
- **风险：** 两个 event 同时触发的执行顺序（先 install 再 upgrade），需要测试覆盖。

### §3.7 D-D 文档与测试体系健康度（Documentation / Test System）

**评估问题：**
- 14 个 reference 文档（含 SKILL.md 460 + execution-protocol.md 818 + agent-workspace.md ~750 + ... 总 ~9000 行）— 是否真都被高频使用？
- C-4 line budget 体系（Default <500 / Large ≤1000 / XL ≤1600）是否产生反作用——"为了卡 budget 而牺牲表达"？
- 4091 测试 / +121 cycle delta — W-17 mid-cycle audit 已触发 yellow 信号；测试体系是否在膨胀？
- `tests/test_no_ghost_features.py` 的 W-18 lint 每个 cycle 加新 `test_v10_X_X_new_symbols_have_coverage` — 这套 lint 自身的维护成本？

#### **D-D-1 ⭐ — Reference 实际加载率审计**

- **现状证据：** SKILL.md `## Reference Navigation Guide` Tier-2 列 14 个 reference；`task_adaptive_selector.py::select_context` 通过 task_type 决定哪些 reference 标 critical/important/skip。但操作者从来不知道：每个 reference 在过去 6 个 cycle 中实际被 critical 过多少次？
- **内部价值：** 一份"reference utilization rate"报告，识别"知识文档化但很少被 read"的浪费——可能引导未来 cycle 把不常用 reference 折叠到其他 reference，节省总 token 池。
- **DF 端可独立完成范围：** `scripts/audit_reference_utilization.py` 跑 14 task types × 5 round_nums = 70 种组合，统计每个 reference 被标 critical 的频率；产出报告。
- **工作量：** S（≤0.5 PV）。
- **调研方向：** → §4.2 sparse retrieval / cold-start eviction 论文族；§4.3 Notion / Confluence 文档使用率分析；§4.5 既有 `task_adaptive_selector.py` 复用。
- **风险：** 利用率为 0 的 reference 可能仍承载长尾价值（如 troubleshooting 紧急时才用）；建议至少保留低利用率 reference 半个 cycle 观察期。

#### **D-D-2 — `agent-workspace.md` / `execution-protocol.md` 等长 reference 的"被使用"证据**

- **现状证据：** `agent-workspace.md`（v8.3.0+，~750 行）+ `execution-protocol.md`（v8.0.0+，818 行）+ `decomposition-gate.md`（~590 行）是三个最长的 reference。`agent-workspace.md` §3 Lifecycle FSM + §6 Handoff Protocol 是核心机制；但 v10.0.0..v10.3.0 cycle 中实际产生的 handoff envelope 数量（在 `.local/.agent/handoff/` 下）有多少？
- **内部价值：** 明确"DF 是为高复杂度协调设计 vs DF 实际被用在中等复杂度任务"的差距；如果 90%+ task 没用上 handoff envelope，可以考虑把 envelope 协议在 SKILL.md 中标记为"only for complex"。
- **DF 端可独立完成范围：** 扫描历史 cycle 的 archive folder + .local/.agent/handoff/（如可访问），统计 envelope 创建率；产出报告。
- **工作量：** S（≤0.5 PV）。
- **调研方向：** → §4.5 既有 `agent-workspace.md` + 历史 cycle archive 复用。
- **风险：** 数据可能不完整（很多 cycle 没启用 `DEVOLAFLOW_AGENT_WORKSPACE`），需声明 sample size。

#### **D-D-3 ⭐ — C-4 line budget 反作用评估**

- **现状证据：** SF-1 / C-4 规定 SKILL.md <500 / references ≤1000 / examples ≤1600；当前 SKILL.md = 460 / 14 references 平均 ~600。`v10.2.4_w17_mid_cycle_audit.md` §4 提到"高信息密度"判定。但 budget 卡得过紧时，作者可能选 cryptic 缩写而不是清晰长句。
- **内部价值：** 评估 14 reference 中是否有"为卡 budget 而牺牲表达"的段落（标志：使用了大量缩写、缺少示例、缺少 cross-reference）；如果发现，建议未来 cycle 把这类 reference 升级到 XL tier（≤1600）或拆分。
- **DF 端可独立完成范围：** 一份分析报告（约 200 行）；附 5-10 个具体 segment 的"压缩前后对比"提案。
- **工作量：** S（仅文档；≤1 PV）。
- **调研方向：** → §4.2 prompt compression vs comprehension trade-off 论文族；§4.4 RFC 写作风格指南 (RFC 2119 / IETF style)；§4.5 既有 `karpathy_skills_analysis.md`（"verbatim 知识"原则）复用。
- **风险：** 评估本身是主观的；建议用对比测试（"读 5 段缩写版 vs 5 段展开版后回答 5 个问题，准确率对比"）支持。

#### **D-D-4 — W-17 测试函数膨胀曲线 + W-18 lint 的维护成本**

- **现状证据：** v10.0.0 cycle +216 NEW tests vs +150 cap (overshoot；retrospective §3.4 接受为 high-information)；v10.2.0 cycle +94 / +150 cap (62.7% utilization；mid-cycle audit GREEN)。曲线倾向"每 cycle ~+100"。`tests/test_no_ghost_features.py` 每 cycle 加新 `test_v10_X_X_new_symbols_have_coverage`（per `v10.3.0_retrospective.md` §6）— W-18 lint 列表至少在 v9.0.0..v10.3.0 累积了 8+ 个 cycle-specific lint。
- **内部价值：** (a) 测试函数总数（4091 at v10.3.0）增长曲线是否健康？10000 测试时 pytest wall clock 仍能保持 17s 吗？(b) W-18 cycle-specific lint 是否应在 cycle 关闭时自动归档/合并到一个通用 lint？
- **DF 端可独立完成范围：** (a) 一份测试增长趋势分析；(b) 一个 `scripts/consolidate_w18_lints.py` 把过去 cycle 的 W-18 lints 合并成通用断言（如 "every CHANGELOG vX.Y.Z entry has a `test_v<X>_<Y>_<Z>_*` lint"）；新加 cycle lint 自动复用通用骨架。
- **工作量：** M（1 PV：分析 + script）。
- **调研方向：** → §4.2 test bloat / test smell 论文族（如 "Test Smells" by van Deursen）；§4.3 Google testing pyramid + post-test cleanup；§4.5 既有 `tests/test_no_ghost_features.py` + `v10.0.0_retrospective.md` §3.4 + `v10.2.4_w17_mid_cycle_audit.md` 复用。
- **风险：** 合并 W-18 lints 可能损失"哪个 cycle 加了什么"的可追溯性；建议保留原 lint 的注释或链接到 CHANGELOG 行。

## §4 调研和搜索方向（**本次修订新增的核心章节**）

为每个 §3 维度提出具体的调研路径。本章是用户明确要求的核心交付。

### §4.1 同类 workflow / agent 框架对比研究

值得对比的开源项目，每个标注调研要点 + 关联的 §3 方向。

#### **对比项 1：LangGraph (LangChain)**

- **仓库：** https://github.com/langchain-ai/langgraph
- **核心抽象：** State machine + 节点编排；Graph as Workflow；Checkpointing primitive 内置
- **与 DF 的可比点：** DF 的 `meta-framework.md` §6 BNF grammar (`Workflow ::= Template Stage+`) 与 LangGraph 的 StateGraph 概念正交但相似；DF 的 stage primitives 是 14 个固定原语，LangGraph 是任意节点。
- **调研动作：** Read LangGraph 的 `docs/concepts/low_level.md` + `examples/checkpointing/` 比较：(1) 状态持久化机制 vs DF 的 STATUS.yaml + handoff envelope；(2) 节点编排自由度 vs DF 的 22 模板的限制性。
- **关联 §3：** D-A-1 (L1/L2 设计)、D-A-3 (resume 协议)、D-P-1 (cache prefix 与状态序列化)、D-O-3 (中间状态索引)。

#### **对比项 2：CrewAI**

- **仓库：** https://github.com/crewAIInc/crewAI
- **核心抽象：** Multi-agent crew + role-based 协作；任务委派；hierarchical / sequential 两种执行模式
- **与 DF 的可比点：** CrewAI 的 Agent 角色 vs DF 的 5 AgentTeam（Research/Design/Implement/Test/Review）；CrewAI 的 Process.hierarchical vs DF 的 L0/L1/L2/L3。
- **调研动作：** Read CrewAI 的 `src/crewai/process.py` + `docs/concepts/processes.md`，对比"hierarchical process"与 DF 4-layer hierarchy；评估 CrewAI 是否有 DF 缺失的 inter-agent 通讯抽象。
- **关联 §3：** D-A-1 (L1/L2 实际使用率)、D-P-4 (plan-mode 协议)、D-X-1 (新建模板的 scaffold)。

#### **对比项 3：AutoGen (Microsoft)**

- **仓库：** https://github.com/microsoft/autogen
- **核心抽象：** Conversational multi-agent；GroupChatManager；ConversableAgent
- **与 DF 的可比点：** AutoGen 的"对话式 agent 协作" vs DF 的"消息式 dispatch + handoff envelope"。AutoGen 是 P3 (free-form chat) 的反例；DF 严格禁止 free-form chat。
- **调研动作：** Read AutoGen `docs/Examples/Notebooks` 中的 GroupChatManager 案例；分析"对话流"与"结构化消息流"的认知负担差异。
- **关联 §3：** D-P-3 (schema 表达力)、D-O-1 (评估器对齐)、D-X-5 (troubleshooting 手册)。

#### **对比项 4：Metaflow (Netflix)**

- **仓库：** https://github.com/Netflix/metaflow
- **核心抽象：** Pythonic DSL + step-based workflow；Tags + namespace；Versioning by default
- **与 DF 的可比点：** Metaflow 的"step decorator"DSL 风格 vs DF 的 yaml 模板；Metaflow 的 `@step` + `next()` 的 DAG 表达 vs DF 的 14 primitives + 5 composition operators。
- **调研动作：** Read Metaflow `docs/metaflow/composing.html`，对比 DSL 写起来的"摩擦感"——为什么 Metaflow 用 Python decorator 而不是 yaml？
- **关联 §3：** D-A-2 (22 模板压缩)、D-P-1 (canonical_order 简化)、D-X-1 (scaffold CLI)。
- **重要 caveat：** Metaflow 是 ML pipeline 框架；引用其 DSL 设计哲学不等于 DF 应该变成 ML 框架（呼应 §2 H-2 完全丢弃理由）。

#### **对比项 5：Kedro (QuantumBlack / McKinsey)**

- **仓库：** https://github.com/kedro-org/kedro
- **核心抽象：** DataCatalog + Pipeline + Hooks；Modular Python pipelines
- **与 DF 的可比点：** Kedro 的 Hooks 系统 vs DF 的 lifecycle hooks (10 events)；Kedro 的 `kedro new` scaffold CLI vs DF 当前没有 scaffold。
- **调研动作：** Read Kedro `docs/source/extend_kedro/hooks.md` + `kedro/cli/cli.py`，分析 hook 命名规范（`before_pipeline_run` / `after_node_run`）与 DF 当前 mixed 命名。
- **关联 §3：** D-Q-3 (lifecycle hook 命名)、D-X-1 (scaffold CLI)、D-D-1 (reference 利用率)。

#### **对比项 6：Temporal**

- **仓库：** https://github.com/temporalio/temporal
- **核心抽象：** Durable execution；Workflow as code；Activity + signals + retries 内置
- **与 DF 的可比点：** Temporal 的"workflow 在主机重启后自动恢复" vs DF 的 change-driven workflow + STATUS.yaml resume 能力（理论上支持但未广泛使用）。
- **调研动作：** Read Temporal `docs/dev-guide/typescript/foundations` 中"replay" 概念；对比 Temporal 的 `WorkflowHandle.signal()` 与 DF 的 handoff envelope（S-9 append-only）。
- **关联 §3：** D-A-3 (resume 协议)、D-C-1 (degraded mode)、D-O-3 (中间状态索引)。

#### **对比项 7：Restate / Inngest**

- **仓库：** https://github.com/restatedev/restate / https://github.com/inngest/inngest
- **核心抽象：** Durable functions / event-driven workflow；Step memoization；Idempotency
- **与 DF 的可比点：** 这两个项目都是"轻量级 durable workflow"——比 Temporal 简单，比 LangGraph 重；DF 的位置类似——介于"对话式 multi-agent"和"重型 workflow engine"之间。
- **调研动作：** Read Restate `docs/concepts/durable_execution.md`；评估 DF 是否需要"step memoization"（即同一 task 重跑时跳过已完成的子步骤）。
- **关联 §3：** D-A-3 (resume 协议)、D-C-1 (degraded mode)。

#### **对比项 8：OpenSpec (Fission AI)**

- **仓库：** https://github.com/Fission-AI/OpenSpec
- **核心抽象：** Source-of-truth `specs/` ↔ in-flight `changes/` 分离；ADDED/MODIFIED/REMOVED delta 协议；4 阶段 propose→apply→verify→archive
- **与 DF 的可比点：** **DF 的 `change-driven` 模板已经直接采纳了 OpenSpec 的设计**（per `v8.3.0_openspec_deep_analysis.md`）——但 OpenSpec 的全部 framework 只用 1 个模板，DF 用了 22 个。
- **调研动作：** Read OpenSpec `docs/concepts.md` + `openspec/config.yaml`；对比"22 模板 + 14 reference vs 1 模板 + 1 spec"哲学差距。
- **关联 §3：** D-A-2 (22 模板压缩)、D-A-3 (resume 协议)、D-D-2 (agent-workspace 实际使用)。
- **本对比项重要性极高**——DF 的 v8.3.0 已经吸纳了 OpenSpec 的 source-of-truth 模式；新一轮深度对比可以判断"是否值得进一步收敛到 OpenSpec 路线"。

#### **对比项 9：Anthropic Skills / GitHub Copilot Skills / Codex Skills 标准**

- **仓库：** Anthropic Claude Code skills (ecosystem)；GitHub: https://github.com/github/skills；Cursor IDE skills（封闭源）
- **核心抽象：** "skill" 作为 markdown + frontmatter 文件；激活由用户提示触发；典型大小 < 5K tokens
- **与 DF 的可比点：** DF 的 SKILL.md（460 行 v10.3.0）vs Anthropic 同名概念；DF 是"skill of skills"——其他 skill 用户写一个 SKILL.md 即可，DF 的 SKILL.md 是 4-layer agent hierarchy 的入口。语义错位。
- **调研动作：** Read 3 个生态的 SKILL 标准文档；对比 frontmatter schema (id/version/triggers/description) 是否一致；评估 DF SKILL.md 是否应符合通用 skill 标准 + 在内部用另一个名字（e.g. WORKFLOW.md）作为框架入口。
- **关联 §3：** D-A-2 (模板与 skill 的关系)、D-D-1 (reference 利用率)、D-X-2 (新建 reference 链路)。

#### **对比项 10：superpowers (obra)**

- **仓库：** https://github.com/obra/superpowers
- **核心抽象：** Subagent-driven development；2-stage review (spec then quality)；rationalization prevention 表
- **与 DF 的可比点：** **DF 已直接采用 superpowers 的 2-stage review 模式**（per `team-roles.md` §6 "Two-stage review pattern"）；rationalization prevention 也借鉴自 superpowers + Karpathy。
- **调研动作：** Read superpowers `skills/subagent-driven-development/SKILL.md` 最新版（v5.0.6+）；查 superpowers v5.0.6+ 是否有 DF 还未吸纳的新模式（如 "inline self-review"——已在 `decomposition-gate.md` §8 引入）。
- **关联 §3：** D-D-3 (line budget 反作用)、D-X-5 (troubleshooting)、D-O-2 (SI-3 自动采集)。

#### **对比项 11：get-shit-done (gsd)**

- **仓库：** https://github.com/gsd-build/get-shit-done
- **核心抽象：** Gate taxonomy + Lifecycle hooks + Prompt injection defense
- **与 DF 的可比点：** **DF 已部分吸纳 gsd 的 gate taxonomy + revision gate**（per `decomposition-gate.md` §6.0 stagnation detection）；gsd 的 `references/gates.md` 是 DF gate primitives 的灵感来源之一。
- **调研动作：** Read gsd `references/gates.md` 最新版（v1.35.0+ per `reference_repos_survey.md`）；对比 gsd 的 issue-count stagnation 与 DF 的 score stagnation；探索 gsd 是否有 DF 未吸纳的 gate 类型。
- **关联 §3：** D-O-1 (评估器对齐)、D-Q-3 (lifecycle hook 命名)、D-O-4 (gate chain 增长)。

#### **对比项 12：Karpathy / forrestchang skills**

- **仓库：** https://github.com/forrestchang/andrej-karpathy-skills
- **核心抽象：** 4 行为基元（think_first / simplicity_check / surgical_scope / goal_loop）；CLAUDE.md 单文件
- **与 DF 的可比点：** **DF 已采纳 4 基元为 BG-001..BG-004**（per `references/behavioral-guidelines.md` 第 9 个 reference）；DF 把 Karpathy 的"single CLAUDE.md"扩展到 14 references——是合理扩展还是过度复杂化？
- **调研动作：** Re-read `karpathy_skills_analysis.md`（仓内已有）；对比 Karpathy 的"minimal upstream artifact"vs DF 的"14 references + 22 templates"扩张模式。
- **关联 §3：** D-D-1 (reference 利用率)、D-D-3 (line budget 反作用)、D-A-2 (22 模板压缩)。

### §4.2 学术论文搜索方向

每条搜索族给出关键词组合 + 推荐期刊/会议 + 时间窗 + 关联 §3。

#### **搜索族 1：Multi-agent orchestration 与 hierarchical agent systems**

- **关键词组合：**
  - `"multi-agent orchestration" AND "LLM" AND "hierarchical"`
  - `"agent hierarchy" AND "delegation" AND "LLM agent"`
  - `"meta-cognitive" AND "agent" -reinforcement_learning`（避开 RL 多智能体方向；用 LLM agent 框架）
- **优先来源：** arXiv (cs.AI, cs.CL)、ACL、EMNLP、NeurIPS workshops。
- **时间窗：** 2024-2026
- **关联 §3：** D-A-1 (L1/L2 设计)、D-A-3 (resume 协议)、D-P-4 (plan-mode 协议)。

#### **搜索族 2：Workflow scheduling + DAG executor 系统**

- **关键词组合：**
  - `"DAG executor" AND "checkpoint" AND ("Python" OR "TypeScript")`
  - `"workflow engine" AND "durable" AND "LLM"`
  - `"step memoization" AND "workflow"`
- **优先来源：** ICSE、ASE、SOSP（系统类）；arXiv cs.SE、cs.DC。
- **时间窗：** 2023-2026
- **关联 §3：** D-A-3 (resume 协议)、D-P-3 (schema 延展性)、D-C-1 (degraded mode)。

#### **搜索族 3：Skill libraries + context engineering + prompt caching**

- **关键词组合：**
  - `"skill library" AND "LLM agent" AND ("retrieval" OR "selection")`
  - `"prompt caching" AND ("KV cache" OR "prefix cache")`
  - `"context engineering" AND "LLM" AND "agent"`
- **优先来源：** arXiv cs.CL、ACL workshops、EMNLP system demonstrations。
- **时间窗：** 2024-2026
- **关联 §3：** D-A-2 (22 模板压缩)、D-D-1 (reference 利用率)、D-P-1 (canonical_order 审计)。

#### **搜索族 4：Dispatcher + planner-executor architectures**

- **关键词组合：**
  - `("planner-executor" OR "plan-then-act") AND "LLM" -robotics`（避开 robotics 方向）
  - `"hierarchical task network" AND "LLM" AND "code"`
  - `"task decomposition" AND "agent" AND "evaluation"`
- **优先来源：** arXiv cs.AI、ACL、AAAI。
- **时间窗：** 2024-2026
- **关联 §3：** D-A-1、D-P-4、D-X-1 (scaffold CLI 设计灵感)。

#### **搜索族 5：Self-improvement 在 LLM agent 中（meta-cognition）**

- **关键词组合：**
  - `"self-improvement" AND "LLM agent" AND ("benchmark" OR "evaluation")`
  - `"meta-cognition" AND "language model" -metacognition_human`
  - `"convergence" AND "LLM agent" AND "stagnation"`
- **优先来源：** NeurIPS、ICLR、arXiv cs.AI。
- **时间窗：** 2024-2026
- **关联 §3：** D-O-1 (评估器对齐)、D-O-2 (SI-3 自动采集)、D-O-4 (gate chain 增长)。

#### **搜索族 6：Test bloat / over-testing 在 CI 系统**

- **关键词组合：**
  - `"test smell" AND "redundancy" AND "CI"`
  - `"test bloat" AND "Python" AND "pytest"`
  - `"flaky test" AND "elimination" -ML`（排除 ML training 类）
- **优先来源：** ICSE、ASE、ESEM。
- **时间窗：** 2022-2026
- **关联 §3：** D-D-4 (W-17 测试函数膨胀曲线)。

#### **搜索族 7：Cache-aware design for prompt-based systems**

- **关键词组合：**
  - `"prompt cache" AND ("invalidation" OR "prefix")`
  - `"KV cache" AND "agent" AND "multi-turn"`
  - `"cached input" AND "LLM API" AND "design"`
- **优先来源：** SOSP、OSDI、arXiv cs.DC、cs.CL。
- **时间窗：** 2024-2026
- **关联 §3：** D-P-1 (canonical_order 审计)、D-D-3 (line budget 反作用)。

### §4.3 行业案例与生产实践

调研价值高的行业 / 公司实践（不限于开源）。

#### **行业案例 1：Anthropic / OpenAI / Google DeepMind 的 agent 公开材料**

- **来源：**
  - Anthropic Engineering blog: https://www.anthropic.com/engineering
  - OpenAI Cookbook: https://github.com/openai/openai-cookbook
  - DeepMind blog: https://deepmind.google/discover/blog
- **调研重点：**
  - Anthropic prompt caching 设计（与 DF A-2 frozen prefix 直接相关）
  - OpenAI Assistants API thread 持久化 vs DF change folder
  - DeepMind "agent grading" 论文与 DF SI-3 评估
- **关联 §3：** D-O-1 (评估器对齐)、D-P-1 (cache prefix)、D-A-3 (resume 协议)。

#### **行业案例 2：Cursor / Cline / Aider / Claude Code / Codex 的 skill 系统**

- **来源：** 各 IDE 的官方 docs；reddit r/cursor / r/aider；其 Discord 公开讨论
- **调研重点：**
  - Cursor `.cursor/skills/` vs `.cursor/rules/` 设计差异
  - Claude Code `~/.claude/skills/` 与 `.claude/skills/`（项目）的优先级模型
  - Aider `aider.conf.yml` + `.aider/` 的精简哲学
  - Codex `AGENTS.md` 单文件 corpus 模式
- **关联 §3：** D-A-2 (22 模板)、D-D-1 (reference 利用率)、D-X-2 (新建 reference)。
- **DF 仓内已部分覆盖：** `local_workspace_structure_best_practices_report.md` + `cross_tool_rules_governance_report.md`（per §4.5）。

#### **行业案例 3：Stripe / Shopify / Vercel 的 internal dev workflow 系统**

- **来源：** Stripe Engineering blog / Shopify dev blog / Vercel changelog
- **调研重点：**
  - Stripe 的 "atomic deployment" + "pre-merge gate" 设计（与 DF SI-10 7-gate 同质）
  - Shopify 的 "code review at scale"——单 cycle 大 PR 的 review 哲学
  - Vercel 的 incremental adoption pattern（feature flag + cohort）
- **关联 §3：** D-X-3 (W-9 SI-10 fast-path)、D-X-4 (PR 流程)、D-O-4 (gate chain)。

#### **行业案例 4：AI 编程助手的 lifecycle hook 生态**

- **来源：**
  - Husky: https://github.com/typicode/husky
  - Lefthook: https://github.com/evilmartians/lefthook
  - pre-commit framework: https://github.com/pre-commit/pre-commit
- **调研重点：**
  - Husky 的 git hook 命名空间（pre-commit / pre-push）
  - Lefthook 的并行 hook 执行
  - pre-commit framework 的 stage 概念（manual / push / commit / pre-rebase）
- **关联 §3：** D-Q-3 (lifecycle hook 命名)、D-X-3 (fast-path)、D-O-4 (gate chain 分组)。

#### **行业案例 5：大型开源治理项目的 RFC / proposal 流程**

- **来源：** Rust RFCs (https://github.com/rust-lang/rfcs)、Python PEP、NixOS RFC、Kotlin KEEP
- **调研重点：**
  - 提案漂浮的处理（DF W-21 的 Soul rule telegraph 漂浮 4 cycle 的现象）
  - 提案过期的归档机制
  - Stage 设计（draft → final → accepted vs DF 的 telegraph → SI-1 evaluation）
- **关联 §3：** D-P-2 (Soul rule 门槛)、D-A-2 (模板 deprecation 流程)。

### §4.4 邻近技术追踪

非直接竞品但有借鉴价值。

#### **邻近技术 1：Pre-commit hook 框架的"hook 哲学"**

- **来源：** Husky（轻量）vs Lefthook（结构化 yaml）vs pre-commit framework（语言无关）
- **借鉴点：**
  - DF 的 `lifecycle/` 包 vs git pre-commit 工具的 hook 模型差异
  - "Hook 之间的依赖"——pre-commit 的 stage + skip 设计与 DF 当前缺失
  - Hook 失败的诊断信息——pre-commit 输出与 DF lifecycle hook 的 PSC0XX 错误码
- **关联 §3：** D-Q-3 (lifecycle hook 命名)、D-X-3 (fast-path)、D-X-5 (troubleshooting)。

#### **邻近技术 2：Plugin manager 架构（vim plugin / VS Code Extension API）**

- **来源：**
  - vim-plug / packer.nvim / lazy.nvim 设计哲学
  - VS Code Extension API: https://code.visualstudio.com/api
- **借鉴点：**
  - 插件懒加载（DF 的 lazy_imports 模式与 vim lazy.nvim 同源）
  - 插件版本协商（VS Code Extension manifest engines.vscode 字段 vs DF runtime-plugins.yaml schema_version 1/2/3）
  - 插件生命周期（activate / deactivate vs DF pre_plugin_invocation / post_skill_edit）
- **关联 §3：** D-C-1 (degraded mode)、D-C-2 (桥接层版本协商)、D-C-3 (lifecycle 拆分)。

#### **邻近技术 3：DSL 设计哲学（Bazel BUILD / Nix / IBC）**

- **来源：** Bazel BUILD 语言、Nix expressions、Skaffold pipelines
- **借鉴点：**
  - "少量原语 + 强组合"哲学（DF 14 primitives + 5 operators 是这条线的延续）
  - DSL 中"宏"vs"函数"的取舍（DF 的 22 模板是不是其实可以用 5 operators 组合出来？）
  - YAML vs Python decorator vs custom DSL 的可读性 trade-off（呼应 §4.1 Metaflow vs Kedro vs DF）
- **关联 §3：** D-A-2 (22 模板压缩)、D-X-1 (scaffold CLI)。

#### **邻近技术 4：Prompt cache 与 LLM API 设计（Anthropic prompt caching、OpenAI cached_input）**

- **来源：**
  - Anthropic prompt caching docs: https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching
  - OpenAI cached input: https://platform.openai.com/docs/guides/prompt-caching
- **借鉴点：**
  - 1024-token cache 边界的对齐策略（DF A-2 frozen prefix 的字节稳定恰好是为 cache 设计）
  - cache control breakpoint 的设计（DF 是否需要在 17 canonical_order 字段中显式标 cache_control 边界？）
  - cache TTL 与 cycle bump 的耦合
- **关联 §3：** D-P-1 (canonical_order 审计)、D-D-3 (line budget)。

### §4.5 仓库内既有研究的复用

DF 仓库内 `.local/research/` 已有相关研究材料，本次提案应直接 cite 而非重做。

| 研究路径 | 与本次方向的重叠 | 复用建议 |
|---|---|---|
| `.local/research/reference_repos_survey.md` | 高度重叠 §4.1（17 reference repo 的最新 2026-04 调研） | **直接复用** §"top_5_priorities" + "cross_cutting_patterns"；§4.1 的 12 frameworks 中有 8 个已被本文覆盖 |
| `.local/research/karpathy_skills_analysis.md` | 高度重叠 §4.1 对比项 12 | **直接复用** 4 行为基元的详细对比；§3.D-D-1 / §3.D-D-3 reference 利用率讨论可引用 |
| `.local/research/v8.3.0_openspec_deep_analysis.md` | 高度重叠 §4.1 对比项 8 | **直接复用** OpenSpec source-of-truth ↔ in-flight 模式的详细分析；§3.D-A-2 / §3.D-D-2 可引用 |
| `.local/research/cross_tool_rules_governance_report.md` | 高度重叠 §4.3 行业案例 2 | **直接复用** 11 工具规则格式总览表；§3.D-A-1 / §3.D-X-2 可引用 |
| `.local/research/local_workspace_structure_best_practices_report.md` | 高度重叠 §4.3 行业案例 2 | **直接复用** 6 AI 编码工具目录结构对比；§3.D-X-2 / §3.D-X-5 可引用 |
| `.local/research/T01-subagent-decomposition-research.md` | 重叠 §3.D-A-1（L3 sub-decomposition 可行性） | **直接复用** L3 internal decomposition 风险分析；§3.D-A-1 决策需引用其结论"verdict: PARTIALLY VIABLE" |
| `.local/research/S01-T02-orchestration-systems.md` | 重叠 §4.1 对比项 1-7 | **审阅复用** —— 该文是 v3.x 时期对 orchestration 系统的早期调研；可作为 §4.1 的历史基线 |
| `.local/research/v9.6.0_reference_deltas.md` + `v9.6.0_reference_deltas/{openspec,caveman,superpowers}.json` | 重叠 §4.1 对比项 8/10/11 | **直接复用** —— v9.6.0 的 NineS 深度分析覆盖 5 reference repos |
| `.local/research/v9-ADR-002-cache-layout-governance-v2.md` | 高度重叠 §3.D-P-1（canonical_order 审计） | **必读** —— D1/D2/D3/D4 决策直接定义 §3.D-P-1 的边界 |
| `.local/research/v9-ADR-003-a5-ssot-registry.md` | 重叠 §3.D-Q-2（god function refactoring） | **审阅复用** —— A-5 SSOT 模式可作为 §3.D-Q-2 的 refactor 风格指南 |
| `.local/research/v9-ADR-007-rule-rebalancing-and-rollup.md` | 高度重叠 §3.D-P-2（Soul rule 门槛） | **必读** —— D4 Soul-set freeze governance 是 §3.D-P-2 的直接前提 |
| `.local/research/nines_v2_analysis.md` | 重叠 §3.D-O-1（评估器对齐） | **审阅复用** —— NineS 早期设计哲学；可作为评估器 rosetta 表的输入 |
| `.local/research/T02-caveman-compression-audit.md` | 重叠 §3.D-D-3（line budget 反作用） | **审阅复用** —— caveman compression 哲学与 DF C-4 line budget 同源 |
| `.local/research/v7.0.0_context_compression_research.md` | 重叠 §4.2 搜索族 3、§3.D-D-3 | **审阅复用** —— v7.0.0 的 context 压缩研究 |
| `.local/research/claude_skill_integration_gap_analysis.md` | 重叠 §4.1 对比项 9 + §4.3 行业案例 2 | **直接复用** —— Claude Code skill 与 DF 集成的 gap 分析 |
| `.local/research/tweet_analysis_harness_engineering_v7.8.md` | 重叠 §4.3（行业实践） | **审阅复用** —— harness engineering 行业实践 |

**§4.5 复用结论：** 本次提案的 §4 调研需求中，约 60% 的内容已被仓内既有研究覆盖；新增工作集中于 (a) 把已有材料按 §3 的 7 个内部维度重新索引；(b) 补充 §4.1 中 LangGraph / CrewAI / AutoGen / Metaflow / Kedro / Temporal / Restate 等仓内未覆盖的 7 个项目；(c) §4.2 论文族需要新做。

## §5 推荐执行优先级（重新排序）

放弃旧方案的"H-1..H-5 + cycle 排程"。新优先级**严格基于 DF 内部内在收益**，与 EvoBench 评分预期解耦。

### 排序原则（必读）

1. **内部价值密度优先**——修一个点能改善多少处下游使用？> 外部信号强度
2. **零依赖优先**——不需要 NineS / EvoBench / Si-Chip 配合即可落地的方向优先
3. **小而锐**——< 1 PV 的方向优先于 multi-PV 大动作
4. **去工具化标记 ⭐**——凡是改善 DF 自身后无论 EvoBench 是否变化都仍有价值的方向，标 ⭐ 高优先

### Top-10 优先方向

| 排序 | ID | 方向标题 | 内部价值（一句话） | 依赖外部数据? | 工作量 | ⭐ |
|:---:|---|---|---|:---:|:---:|:---:|
| 1 | **D-X-1** | Workflow 模板 scaffold CLI | 把新建模板从 9 步降到 ~3 步；直接降低 framework 扩展摩擦 | 否 | M | ⭐ |
| 2 | **D-X-2** | Reference doc 创建链路压缩 | 从 7 步降到 ~3 步；减少漏改风险 | 否 | M | ⭐ |
| 3 | **D-X-3** | W-9 SI-10 fast-path | PR 内迭代延迟从 5-10 分钟降到 < 2 分钟 | 否 | S | — |
| 4 | **D-D-1** | Reference 实际加载率审计 | 识别"知识文档化但少 read"的浪费；引导未来收敛 | 否 | S | ⭐ |
| 5 | **D-A-1** | L1/L2 实际使用率审计 | 决定是否标"可选层"；从 4-layer 简化到 3-layer 候选评估 | 否 | S | ⭐ |
| 6 | **D-A-2** | 22 模板压缩到 12-15 个 | 减少 SKILL.md 选择疲劳 + W-12 build 成本 | 否 | M | ⭐ |
| 7 | **D-O-1** | 三评估器 rosetta 表 | 让评估读者 5 秒看懂 NineS 0.907 vs SI-3 9.385 vs Si-Chip +0.9 关系 | 否 | M | ⭐ |
| 8 | **D-Q-1** | v10.2.2 NineS 7 个 warning 清理 | 直接降低代码维护成本；mechanical 修复 | 部分（NineS 验证） | L (7 PV) | ⭐ |
| 9 | **D-P-1** | A-2 canonical_order 17 字段合并审计 | 输出报告（不动 schema），为未来 cache 优化奠基 | 否 | S | ⭐ |
| 10 | **D-X-5** | 操作者错误诊断手册 | 减少新操作者重复踩坑 | 否 | M | ⭐ |

**Top-10 中 9 个标 ⭐——这是去工具化对齐后的核心改善线。** 其余方向（D-A-3 / D-A-4 / D-P-2 / D-P-3 / D-P-4 / D-O-2 / D-O-3 / D-O-4 / D-Q-2 / D-Q-3 / D-Q-4 / D-C-1 / D-C-2 / D-C-3 / D-D-2 / D-D-3 / D-D-4）按内部价值密度排在 11-30 位，建议未来 cycle 按需选择。

### 与 EvoBench 评分的关系（明示）

**Top-10 全部不以 EvoBench 评分提升为目标。** 如果在 v10.4.0+ 实施这 10 个方向后，EvoBench `q` 反而下降，**也不应作为本批方向的失败信号**——本批方向衡量的是 DF 内部内在质量。EvoBench 信号应继续作为外部观察项独立追踪。

## §6 操作者待决问题（修订）

10 个问题，全部可在 DF 内部完成判断，不依赖外部数据。

| # | 问题 | 影响哪些方向 | 默认值（若不选） |
|:---:|---|---|---|
| 1 | 是否同意把 22 个 workflow 模板压缩到 12-15 个？（需 deprecation 流程） | D-A-2 | 不压缩；先做使用率审计（D-A-2 的 PV-A），再 cycle 后决定 |
| 2 | 是否同意把 SI-3 6 维度引入自动化采集（不再 100% 靠 L3 主观）？ | D-O-2 | 不引入；保留主观打分（reproducibility 由 rosetta 表 D-O-1 替代） |
| 3 | 是否同意把 NineS 从 W-2 必经环节降级为可选 enhancement？ | D-C-1 + D-Q-4 | 保持必经；degraded mode 文档化即可（D-C-1） |
| 4 | 是否同意把 14 个 references 中利用率 < 5% 的折叠到其他 reference？ | D-D-1 | 不折叠；先做利用率审计（D-D-1），再 cycle 后决定 |
| 5 | 是否同意 W-21 Soul rule 门槛在分析后小幅放宽（如 SI-3 §3.2 ≥ 9.0 而非 9.5）？ | D-P-2 | 不放宽；本次仅做漂浮分析，不改 W-21 |
| 6 | 是否同意把 4-layer hierarchy 在 SKILL.md 中明确标注 L1/L2 为"可选层 / 仅大型项目使用"？ | D-A-1 | 保持当前措辞；先做使用率审计 |
| 7 | 是否同意把 SI-10 7-gate 拆为"基础 hygiene"（5 个）+ "validation"（2 个）两组并行？ | D-O-4 + D-X-3 | 保持顺序；仅产出分析报告，不改 Makefile |
| 8 | 是否同意把 lifecycle hook 10 events 重命名（`pre_*` / `post_*` / `validate_*` / `check_*` 4 组）？ | D-Q-3 | 不重命名；保留 alias 方案在文档化即可 |
| 9 | 是否同意为 4 个外部工具的桥接层加 cached fixture e2e 测试（weekly schedule）？ | D-C-2 | 不加；保持现有 unit fixture（v10.2.3 bridge defect 风险接受）|
| 10 | 是否同意把 W-18 cycle-specific lints 在 cycle close 时合并为通用骨架？ | D-D-4 | 不合并；保留 cycle-specific lint 用于追溯 |

## §7 决策清单（可勾选）

操作者勾选下列项之一或组合：

- [ ] **A. 先做 §5 Top-3 D-X 类方向**（D-X-1 + D-X-2 + D-X-3；低门槛、高 DX 收益；目标 ~3 PV）
- [ ] **B. 先做 §5 Top-3 D-Q 类方向**（D-Q-1 部分 + D-Q-2 + D-Q-4；代码质量优先；目标 ~3-4 PV）
- [ ] **C. 先做 §5 Top-3 D-A 类方向**（D-A-1 + D-A-2 + D-A-3；架构层重构；目标 ~3-4 PV，风险较高）
- [ ] **D. 先做 §5 Top-3 D-D 类方向**（D-D-1 + D-D-2 + D-D-3；文档健康度优先；目标 ~3 PV，风险低）
- [ ] **E. 启动 §4 调研先行**（不立即立项；先做 2-3 周调研后再决定）
- [ ] **F. 综合 plan**：组合 D-X-1 + D-X-2 + D-D-1 + D-O-1 + D-Q-1 部分（5 PV，全 ⭐ 方向，无外部依赖）
- [ ] **G. 退回修订** —— 列明修订点

如选项 F，建议作为 v10.4.0 cycle plan 的 SI-1 输入；其他选项请明示是否需要本文件进一步细化为 cycle plan。

## §8 出范围声明

明确不在本提案内：

- **任何对 EvoBench / NineS / Si-Chip 对方端代码** 的建议——三个外部工具的演进由各自团队负责。本提案仅讨论 DF 仓库自身的修改。
- **以 EvoBench q / pass_rate / gap_score 为主要 KPI 的方向**——上一版方案书的 H-1..H-5 直接复用已被丢弃；如未来要做 mlops / long_horizon / agentic_planning 类专项，必须先重新通过 §3 内部维度论证。
- **上一版方案书的 H-1..H-5 直接复用**——本次修订已对 5 项做去工具化判定（§2），任何 EvoBench 反馈再来时应同样按 7 内部维度过滤。
- **S-11 Soul 规则添加**——W-21 2 周期 telegraph 至早 v10.6.0；本提案仅在 D-P-2 做漂浮分析，不主张推进。
- **新增 W-* / A-* / S-* / C-* 规则**——本次修订**不引入任何新治理规则**；W-20 / W-21 + A-2 已有充分约束。
- **新增 env flag 或 Soul 规则**——本次修订零新增。
- **修改 4-layer hierarchy 数量**——本提案仅在 D-A-1 评估"L1/L2 是否标可选"，不动 4-layer 结构。
- **修改 A-2 frozen prefix 的位置 1-12**——本提案仅在 D-P-1 审计 tail 13-17 是否可合并；frozen prefix 不可动是 release blocker。

## §9 引用

### 被本文修订的文档

- 上一版完整方案书：`.local/research/eb613_v10_optimization_proposal.md`（886 行；H-1..H-5 + M-1..M-3 + L-1 框架；本文丢弃 5 项 + 重定向 4 项）
- 上一版中文清单：`.local/research/eb613_v10_improvement_checklist_zh.md`（196 行）

### EvoBench 反馈（仅作外部信号）

- `.local/feedbacks/from_evobench/eb613_for_devola_v10.0.0.md`（v6.1.3 反馈，2026-05-03）

### v10.x cycle 自我评估材料

- `.local/research/v10.0.0_evaluation.md`（W-3 SI-3 composite 9.20）
- `.local/research/v10.0.0_retrospective.md`（W-7 SI-8 4 mandatory sections + 6 deferred）
- `.local/research/v10.0.0_nines.md`（NineS V3.3.0 self-eval 0.907332）
- `.local/research/v10.0.0_cycle_plan.md`（5-MINOR + 1-MAJOR rollup shape）
- `.local/research/v10.3.0_evaluation.md`（W-3 SI-3 composite 9.385）
- `.local/research/v10.3.0_retrospective.md`（W-7 SI-8 8 deferred + 7 learnings）
- `.local/research/v10.2.2_nines.md`（PV-03 NineS 包级分析；10 warnings；3 closed in PV-04/05；7 carried forward）
- `.local/research/v10.2.4_w17_mid_cycle_audit.md`（W-17 GREEN at PV-05；93/150 cap）
- `.local/research/v10.2.4_w8_stagnation_check.md`（W-8 CONTINUE）

### DF 自身核心 references

- `workflow-system/agent/SKILL.md`（v10.3.0；460 行；Tier 1 entry）
- `workflow-system/agent/references/meta-framework.md`（v1.0.0；14 primitives + 22 templates + 5 operators）
- `workflow-system/agent/references/team-roles.md`（v1.0.0；5 AgentTeam roles）
- `workflow-system/agent/references/decomposition-gate.md`（v1.0.0；gate primitives + convergence loop）
- `workflow-system/agent/references/agent-workspace.md`（v1.0.0；change folder + handoff envelope）
- `workflow-system/agent/references/plan-mode-enforcement.md`（plan-mode + S-10 lifecycle hook）
- `workflow-system/agent/references/env-flags.md`（v9.1.5；16+ active runtime flags）
- `workflow-system/agent/references/shell-proxy.md`（v8.4.0 RTK + memory_router stack）

### Governance / 规则

- `.cursor/rules/repo-governance.mdc`（W-* / S-* / A-* / C-* / ST-* compiled corpus）
- `AGENTS.md`（同上 markdown corpus）
- `.rules/architecture.mdc`（A-1..A-6 canonical source）

### 仓内既有研究（§4.5 复用清单）

- `.local/research/reference_repos_survey.md`
- `.local/research/karpathy_skills_analysis.md`
- `.local/research/v8.3.0_openspec_deep_analysis.md`
- `.local/research/cross_tool_rules_governance_report.md`
- `.local/research/local_workspace_structure_best_practices_report.md`
- `.local/research/T01-subagent-decomposition-research.md`
- `.local/research/S01-T02-orchestration-systems.md`
- `.local/research/v9.6.0_reference_deltas.md` + 子目录 JSON（superpowers/caveman/openspec）
- `.local/research/adr/v9-ADR-002-cache-layout-governance-v2.md`
- `.local/research/adr/v9-ADR-003-a5-ssot-registry.md`
- `.local/research/adr/v9-ADR-007-rule-rebalancing-and-rollup.md`
- `.local/research/nines_v2_analysis.md`
- `.local/research/T02-caveman-compression-audit.md`
- `.local/research/v7.0.0_context_compression_research.md`
- `.local/research/claude_skill_integration_gap_analysis.md`

### 外部工具 (S-7)

- DevolaFlow / EvoBench: https://github.com/YoRHa-Agents/DevolaFlow
- NineS: https://github.com/YoRHa-Agents/NineS
- Si-Chip: https://github.com/YoRHa-Agents/Si-Chip

---

*本文件 PHASE-0；批准任一 §7 选项后由 L0 触发对应 W-1 SI-1 流程。本文修订替代 `.local/research/eb613_v10_optimization_proposal.md` 的根本框架，去工具化重新对齐至 DF 内部 7 维度。*
