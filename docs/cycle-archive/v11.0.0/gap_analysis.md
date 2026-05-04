# DevolaFlow v11.0.0 主线选型清单（中文版）

> **状态：** L0 SI-1 规划门最终选型表（中文化）
> **日期：** 2026-05-04
> **基线：** v10.3.0（commit `f1d9652`）
> **目标：** v11.0.0 MAJOR
> **输入：** 27 份 PDS（`.local/research/v11.0.0_patches/*.md`）+ 4 份 L0 规划文档
> **完整英文版：** `.local/research/v11.0.0_cycle_plan.md`

## §1 — 主线准入清单（9 道硬门 G-1..G-9）

每个 patch 必须**全部通过**以下 9 道门才能进入 v11.0.0 主线：

| 门 ID | 名称 | 通过条件 | 拒绝条件 |
|:---:|---|---|---|
| **G-1** | 内在价值门 | 至少 1 项可量化的 DF 内部指标改善（来自评测方法学 §4.1-4.6） | PDS 把 EvoBench `q` / `pass_rate` / `gap_score` 当主指标 |
| **G-2** | 双层收益门 | 小型项目（合成 minimal repo）+ 大型项目（DevolaFlow 自身 v10.3.0）**都**有改善 | 任一层无改善或回归 > 5% |
| **G-3** | 零外部依赖门 | DEPS 列表只含 DF 内部 `<dir-id>`；不要求 NineS / Si-Chip / RTK / ui-pro 上游做事 | 描述里出现 "需要 Si-Chip 加 X" / "需要 NineS 暴露 Y" |
| **G-4** | 周期预算门 | 全部录用 patch 的 NEW 测试 ≤ 150（W-17 cycle 上限）；单 PV ≤ 30 | 超额且无法拆 PV |
| **G-5** | Soul-集合冻结门 | 不新增任何 S-* Soul 规则（W-21 强制） | 任何 PDS 提议 S-11+ |
| **G-6** | Cache-prefix 门 | canonical_order 位置 1-12 字节恒等（A-2.1 frozen prefix） | 任何重排 / 重命名 / 删除位置 1-12 |
| **G-7** | 兼容门 | 零破坏性变更；纯加性 / 纯内部重构 / 文档 | 公共 API 重命名（函数签名、env flag 名、schema 字段、文件路径） |
| **G-8** | 测试覆盖门 | 新模块 ≥ 80% 覆盖；改动模块不回归（CP-2） | "测试以后再加"模式 |
| **G-9** | 文档完整性门 | 按变动范围齐备：CHANGELOG + W-18 ghost-audit lint + 双语 EN/ZH（如用户面）+ 适配器 build 验证（如改 SKILL/CLAUDE） | 缺关键文档面 |

**结果：27/27 directions 全部通过 9 道门**（22 PASS + 5 CONDITIONAL_PASS；0 拒绝；0 暂存）。

## §2 — 27 个 directions 完整裁定矩阵

按家族分组，verdict / tier / effort 一目了然。

### 2.1 D-X 开发者/操作者体验（4 directions，全 PASS）

| ID | 中文标题 | 裁定 | 等级 | 工作量 | v11.0.0 落点 |
|---|---|:---:|:---:|:---:|---|
| **D-X-1** | Workflow 模板 scaffold CLI | PASS | core | M | v10.4.0 PV-02 |
| **D-X-2** | Reference 文档创建链路压缩 | PASS | core | M | v10.4.0 PV-03 |
| **D-X-3** | W-9 SI-10 fast-path（PR 内 vs cycle close） | PASS | standard | S | v10.4.0 PV-01 |
| **D-X-5** | 操作者错误 troubleshooting 手册 | PASS | standard | M | v10.4.0 PV-05 |

### 2.2 D-A 架构健康度（4 directions，3 PASS + 1 CONDITIONAL_PASS）

| ID | 中文标题 | 裁定 | 等级 | 工作量 | v11.0.0 落点 |
|---|---|:---:|:---:|:---:|---|
| **D-A-1** | L1/L2 实际使用率审计 + 可选层标注 | CONDITIONAL_PASS（仅大型项目可证） | standard | S | v10.5.0 PV-01 |
| **D-A-2** | 22 builtin 模板 → 6 USED + 16 (legacy) 标签（仅 Phase A） | PASS | core | M | v10.5.0 PV-02 |
| **D-A-3** | A-1 4-layer 时间尺度 resume 协议（agent-workspace.md §3.6） | PASS | standard | S | v10.5.0 PV-03 |
| **D-A-4** | A-6 workspace 激活阈值微调 + force_no_change 参数 | PASS | standard | S | v10.5.0 PV-03 |

### 2.3 D-D 文档与测试体系健康度（4 directions，3 PASS + 1 CONDITIONAL_PASS）

| ID | 中文标题 | 裁定 | 等级 | 工作量 | v11.0.0 落点 |
|---|---|:---:|:---:|:---:|---|
| **D-D-1** | Reference 实际加载率审计（70 cell 扫描） | PASS | core | S | v10.4.0 PV-04 |
| **D-D-2** | 长 reference "被使用"实证（envelope 创建率 6%） | PASS | core | S | v10.4.0 PV-05 |
| **D-D-3** | C-4 line budget 反作用评估（3 段落 case） | PASS | standard | S | v10.5.0 PV-04 |
| **D-D-4** | W-17 测试增长 + W-18 lint 维护（30 lints 盘点） | CONDITIONAL_PASS | standard | M | v10.5.0 PV-05 |

### 2.4 D-P 协议可演进性（4 directions，全 PASS）

| ID | 中文标题 | 裁定 | 等级 | 工作量 | v11.0.0 落点 |
|---|---|:---:|:---:|:---:|---|
| **D-P-1** | A-2 canonical_order 17 字段非空率审计（不动 schema） | PASS | standard | S | v10.7.0 PV-01 |
| **D-P-2** | W-21 Soul rule 门槛漂移分析（仅文档） | PASS | stretch | S | v11.0.0 PV-01 |
| **D-P-3** | STATUS.yaml 加 1 个 NEST 字段示范延展性 | PASS | standard | S | v10.7.0 PV-02 |
| **D-P-4** | plan-mode §3.2 多步推理子节（仅文档） | PASS | stretch | S | v11.0.0 PV-01 |

### 2.5 D-O 可观测性与自我评估（4 directions，2 PASS + 2 CONDITIONAL_PASS）

| ID | 中文标题 | 裁定 | 等级 | 工作量 | v11.0.0 落点 |
|---|---|:---:|:---:|:---:|---|
| **D-O-1** | 三评估器 rosetta 表（SI-3 × NineS × Si-Chip 6×9 cell） | CONDITIONAL_PASS | standard | M | v10.7.0 PV-03 |
| **D-O-2** | SI-3 6 维度自动采集（before 0% / after 87%） | PASS | standard | M | v10.7.0 PV-04 |
| **D-O-3** | 中间 PV 研究产物轻量索引（reporter 加段） | PASS | standard | S | v10.7.0 PV-05 |
| **D-O-4** | SI-10 gate chain 增长曲线 + 重组阈值（v13.0=10）分析 | CONDITIONAL_PASS | stretch | S | v11.0.0 PV-02 |

### 2.6 D-Q 代码质量与复杂度热点（4 directions，3 PASS + 1 CONDITIONAL_PASS）

| ID | 中文标题 | 裁定 | 等级 | 工作量 | v11.0.0 落点 |
|---|---|:---:|:---:|:---:|---|
| **D-Q-1** | NineS 7 个剩余 warning helper 抽取（CC 14.3→≤8.1） | PASS | standard | L（4-7 微 PV） | v10.6.0 PV-01-03 |
| **D-Q-2** | feedback.py 上帝函数 ProposalEmitter 抽取 | PASS | standard | M | v10.6.0 PV-04 |
| **D-Q-3** | Lifecycle 10 events 重命名为 pre_*/post_*/check_* 4 组 | CONDITIONAL_PASS | stretch | S | v11.0.0 PV-02 |
| **D-Q-4** | compressor/ 拆分后 NineS 健康快照 | PASS | standard | S | v10.6.0 PV-05 |

### 2.7 D-C 外部工具耦合度（3 directions，全 PASS）

| ID | 中文标题 | 裁定 | 等级 | 工作量 | v11.0.0 落点 |
|---|---|:---:|:---:|:---:|---|
| **D-C-1** | 上游不可达时的 degraded mode 契约（4 plugin 全覆盖） | PASS | core | M | v10.8.0 PV-01 |
| **D-C-2** | 桥接层 shape contract 测试（4 plugin × cached fixture） | PASS | core | M | v10.8.0 PV-02-03 |
| **D-C-3** | pre_plugin_invocation 拆 install + upgrade 两个事件 | PASS | standard | M | v10.8.0 PV-03 |

## §3 — 录用统计

| 维度 | 计数 | 列表 |
|---|---:|---|
| **PASS verdict** | 22 | 除下方 5 个 CONDITIONAL 外的全部 |
| **CONDITIONAL_PASS verdict** | 5 | D-A-1 / D-D-4 / D-O-1 / D-O-4 / D-Q-3（仅 large 层验证） |
| **FAIL** | 0 | — |
| **DEFER** | 0 | — |
| **Tier core**（必入） | 7 | D-X-1, D-X-2, D-A-2, D-D-1, D-D-2, D-C-1, D-C-2 |
| **Tier standard**（应入） | 16 | 见 §2 各表 standard 行 |
| **Tier stretch**（条件入，并入 MAJOR rollup） | 4 | D-P-2, D-P-4, D-O-4, D-Q-3 |
| **Effort S**（≤0.5 PV） | 15 | — |
| **Effort M**（1 PV） | 11 | — |
| **Effort L**（2-7 PV） | 1 | D-Q-1（4-7 微 PV 分散） |

## §4 — v11.0.0 最终版本构成（5 MINORs + 1 MAJOR rollup，31 PVs）

镜像 v10.0.0 cycle 形状（5 MINOR + 1 MAJOR rollup）。

| MINOR 版本 | 主题 | 录用 patches | PV 数 | NEW 测试预算 | 关键 gate |
|---|---|---|:---:|---:|---|
| **v10.4.0** | 开发者体验 + Reference 审计基础 | D-X-1, D-X-2, D-X-3, D-X-5, D-D-1, D-D-2 | 6 | ~28 | standard |
| **v10.5.0** | 架构与文档健康度 | D-A-1, D-A-2, D-A-3, D-A-4, D-D-3, D-D-4 | 6 | ~25 | standard |
| **v10.6.0** | 代码质量（NineS 清理 + 重构） | D-Q-1（L），D-Q-2，D-Q-4 | 6 | ~12 | strict |
| **v10.7.0** | 协议审计 + 可观测性增强 | D-P-1, D-P-3, D-O-1, D-O-2, D-O-3 | 6 | ~23 | standard |
| **v10.8.0** | 外部工具耦合加固 | D-C-1, D-C-2, D-C-3 | 4 | ~25 | standard |
| **v11.0.0** | MAJOR rollup + stretch + 全回归 | D-P-2, D-P-4, D-O-4, D-Q-3 | 3 | ~10 | strict ≥9.0 |
| **合计** | | **27 directions** | **31 PVs** | **~138 / 150 cap（剩 12 测试 buffer）** | — |

## §5 — 周期预算合规检查

| 约束 | 上限 | 预测值 | 余量 |
|---|---:|---:|---:|
| W-17 单 PV NEW 测试 | 30 | 最大 28（v10.6.0 PV-04 D-Q-2） | +2 |
| W-17 全周期 NEW 测试 | 150 | ~138 | +12 |
| 覆盖率底线 | ≥80% | ~92%（重构周期稀释 1pp） | +12pp |
| canonical_order 新增字段 | ≥18 位（append-only） | 0（D-P-3 是 STATUS.yaml NEST，不动 canonical_order） | 全部 |
| 新增 env flag | 0（除非正交） | 0 | 全部 |
| 新增 Soul 规则 | 0（W-21） | 0 | 全部 |
| 新增 reference | ≤2 | 3（troubleshooting + evaluator-rosetta + degraded-mode） | **超 1**（需 v10.4.0 PV-01 SF-1 软上限放宽至 ≤20） |
| 新增 example | ≤1 | 1（multi-stage-trace） | 满 |
| SKILL.md 行数变化 | ≤+20 | ~+15（D-A-2 deprecation tags + D-D-2 注释） | +5 |

## §6 — 风险登记（11 dedup 风险）

按严重度排序：

| # | 风险 | 严重度 | 缓解 |
|:---:|---|:---:|---|
| **R-4** | 14→17 reference 触碰 SF-1 ≤14 硬上限 | **blocker** | v10.4.0 PV-01 单行编辑 `MIRRORED_FILES` 常量 + reference-size-budgets 自动覆盖 |
| **R-5** | D-Q-2 ProposalEmitter 抽取破坏 S-10 hook chain 字节恒等 | **blocker** | `tests/test_dispatch_emission_runs_hooks.py` 11 测试是 release-blocker；refactor 必须保留所有绿；保留 `generate_round_dispatch` 5 行 façade |
| **R-1** | D-Q-1 batch 可能溢出 v10.6.0 测试预算 | major | 已分配 +12 测试 buffer；每 batch 备 fallback delay 1 helper |
| **R-2** | D-D-2 envelope 样本（3 文件 / 50 PV）可能被质疑过小 | major | 在 SKILL.md 注释里标注 "complex / change-driven workflows only"；引用经验路径 |
| **R-3** | D-X-5 troubleshooting（第 15 reference）触发 SF-1 重审 | major | 与 R-4 合并解决（SF-1 软上限放宽至 ≤20） |
| **R-6** | D-C-2 cached fixture 可能静默过期 | major | weekly CI cron + `make refresh-bridge-fixtures` + lint 检测 fixture 时戳 |
| **R-7** | D-A-2 (legacy) 标签可能被误读为"已弃用" | major | meta-framework.md §4 显式注释："(legacy) = 注册但 v9.0.0..v10.3.0 周期未使用；保留可用；Phase B 折叠延至 v12.0+" |
| **R-10** | D-O-2 0.6 obj / 0.4 subj 权重可能与历史手评分歧 | major | 前 2 cycle 双跑（自动 + 手评）对比；偏差 > 0.5/10 则重校准 |
| **R-11** | D-A-2 + D-A-1 + D-A-3 + D-A-4 同时编辑多个 SKILL/reference 文件，v10.5.0 内 PV 间 merge 冲突 | major | PV-01 D-A-1 → PV-02 D-A-2 → PV-03 D-A-3+D-A-4 顺序确保串行 file-touch |
| **R-8** | D-X-1 scaffold 输出与人工模板约定漂移 | minor | scaffold 输出标注 `# AUTO-GENERATED — manual completion required` |
| **R-9** | D-D-3 段落扩展可能逼近 reference Large tier ≤1000 行 | minor | 仅 3 段落定向扩展；超出则拆分而非升 tier |

**净风险画像：2 blockers + 6 major + 3 minor + 0 critical**（两个 blocker 的 mitigation 都安排在 v10.4.0 PV-01 preflight，先期解除）。

## §7 — 操作者待决问题（10 项 sign-off）

| # | 问题 | 默认值（不选时） |
|:---:|---|---|
| **Q1** | 同意 5 MINOR + 1 MAJOR rollup 形状（v10.4 → v11.0）？ | 是（镜像 v10.0.0 周期） |
| **Q2** | 同意录用全部 27 directions（22 PASS + 5 CONDITIONAL_PASS）？或丢弃 5 CONDITIONAL 入 defer-list | 是 — 全部录用 |
| **Q3** | 同意新增 3 个 reference（14→17）？或把 troubleshooting 折成 team-roles.md 附录 | 是 — 新增 3 个 + R-4 mitigation |
| **Q4** | 同意 D-A-2 仅 Phase A（审计 + 标签），Phase B 延至 v12.0+？ | 是 — 仅 Phase A |
| **Q5** | 同意 D-Q-3 lifecycle 重命名移到 v11.0.0 stretch（不在 v10.6.0）？ | 是 — 延至 stretch |
| **Q6** | 同意 D-C-2 weekly CI cron（每周 refresh bridge fixtures）？ | 是 |
| **Q7** | 同意 W-19 cycle archive 在 v11.0.0 PV-03 一次性归档 5 MINOR 的研究产物？ | 是 — 单次归档（W-19 idempotent） |
| **Q8** | 同意 D-O-2 0.6 客观 / 0.4 主观权重？或 0.5/0.5 / 0.7/0.3 | 是 — 0.6/0.4（前 2 cycle 双跑验证） |
| **Q9** | 同意 W-3 SI-3 STRICT MAJOR ≥9.0 阈值（v11.0.0 close）？ | 是 |
| **Q10** | PR 节奏：每 MINOR 1 PR + 1 MAJOR rollup PR（共 6 PRs，镜像 v10.0.0 Q5）？或单 feature branch + 1 PR（v10.2.0 模式） | 默认每 MINOR PR；如 cycle 速度优先则切单分支 |

## §8 — 用户任一决策模板

如要快捷决定，可勾选下面 7 个组合之一：

- [ ] **A. 完全采纳本方案**（默认全部 §7 答案 = 是；27 directions 全录用；6 cycle）
- [ ] **B. 精简版**（仅 7 core + 16 standard；4 stretch 全部 defer 至 v12.0；测试预算降至 ~128）
- [ ] **C. 极速版**（仅 7 core + 8 高频 standard；其余 12 项 defer；缩至 4 MINOR + 1 MAJOR）
- [ ] **D. 谨慎版**（drop 5 CONDITIONAL_PASS；仅 22 PASS + 4 stretch；保 5 MINOR + 1 MAJOR；R 风险减少）
- [ ] **E. 大重构版**（D-A-2 直接做 Phase B 模板折叠；周期延至 6 MINOR + 1 MAJOR；测试预算 +30）
- [ ] **F. 仅出文档版**（仅录用 11 个 S-effort 的 doc/audit 类，code 类全 defer；快速 cycle ~3 MINOR）
- [ ] **G. 其他**（请明示需调整的项）

**缺省=A**。如选 G，请指明哪些 directions 改裁定 / 改 tier / 改 cycle 落点。

## §9 — 关键链接

- 完整英文 cycle plan：`.local/research/v11.0.0_cycle_plan.md`
- 评测方法学：`.local/research/v11.0.0_evaluation_methodology.md`
- 准入门 G-1..G-9 详细：`.local/research/v11.0.0_admission_checklist.md`
- 27 份 PDS：`.local/research/v11.0.0_patches/D-{A,C,D,O,P,Q,X}-*.md`
- 来源（v10 内向优化方向）：`.local/research/v10_internal_optimization_directions.md`

---

*本中文版选型清单是 `.local/research/v11.0.0_cycle_plan.md` 的精炼镜像，仅供操作者快速 sign-off。任何决策落地以英文版 cycle plan 为准。*
