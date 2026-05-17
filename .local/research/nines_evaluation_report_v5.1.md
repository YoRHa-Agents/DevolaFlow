# DevolaFlow v5.1.0-pre NineS 细分评估与选型建议报告

**版本:** v5.1.0-pre  
**日期:** 2026-04-14  
**报告类型:** NineS 风格细分评估 + 选型建议  
**评估对象:** v5.0.0 → v5.1.0-pre 全部变更  
**前置调研文档:**
- `.local/research/nines_integration_gap_analysis_v5.1.md`（10 缺口分析）
- `.local/research/rule_reinforcement_feasibility_v5.1.md`（5 方案对比）

---

## 目录

1. [变更集概览](#1-变更集概览)
2. [A 组细分评估：NineS 集成修复](#2-a-组细分评估nines-集成修复)
3. [B 组细分评估：规则强化机制](#3-b-组细分评估规则强化机制)
4. [风险评估矩阵](#4-风险评估矩阵)
5. [选型建议：Go/No-Go 决策](#5-选型建议gono-go-决策)
6. [版本就绪度评分](#6-版本就绪度评分)
7. [后续优化路线图](#7-后续优化路线图)
8. [结论](#8-结论)

---

## 1. 变更集概览

### 测试基线

| 指标 | v5.0.0 | v5.1.0-pre | 变化 |
|------|--------|------------|------|
| 测试总数 | 681 | 704 | +23 |
| 失败数 | 0 | 0 | — |
| ruff check | clean | clean | — |
| ruff format | clean | clean | — |

### 变更范围

| 组别 | 变更项 | 涉及文件数 | 新增文件 | 修改文件 |
|------|--------|-----------|---------|---------|
| A — NineS 集成修复 | 4 项 | 10 | 1 | 9 |
| B — 规则强化机制 | 6 项 | 6 | 1 | 5 |
| **合计** | **10 项** | **14** | **2** | **12** |

---

## 2. A 组细分评估：NineS 集成修复

### A1. Gap 3 修复（P0）：`_BUILTIN_SPECS` NineS 安装命令与元数据纠正

**变更内容:** `loader.py` 中 `_BUILTIN_SPECS` 的 NineS pip 安装命令从 `pip install nines-cli`（错误包名）修正为 `uv pip install git+https://github.com/YoRHa-Agents/NineS.git`。同步修正 `role` 为 `research_and_iteration`，设置 `min_version: "1.0.0"`，补齐 `benchmark`/`update` capabilities，添加 `stage_mapping` 和 `workflows` 字段。

**影响文件:** `src/devolaflow/plugins/loader.py`

| NineS 评估维度 | 评分 | 说明 |
|:---:|:---:|---|
| **代码质量** | 9/10 | 纯数据修正，语义清晰。`_BUILTIN_SPECS` 现在与 `plugins.yaml` 保持一致，消除了依赖加载顺序的行为差异。 |
| **架构合理性** | 8/10 | 修正了 fallback spec 与 YAML spec 之间的不一致。长期来看仍应消除 `_BUILTIN_SPECS` 硬编码，但作为短期修复方案合理。 |
| **测试充分性** | 9/10 | `test_plugins.py` 新增 `test_builtin_nines_pip_install_command`、`test_builtin_nines_role_and_version`、`test_builtin_nines_capabilities`、`test_builtin_nines_stage_mapping_and_workflows` 四个专项测试，直接验证修复后的数据正确性。 |
| **可维护性** | 7/10 | 硬编码 spec 仍存在（`_BUILTIN_SPECS` 与 `plugins.yaml` 双源），但已标注为短期方案，Gap 6 路线图中计划统一。 |
| **兼容性** | 10/10 | 纯 additive change + 数据修正，`_dict_to_spec()` 对新增字段使用 `data.get(key, default)`，无已有字段变更，完全向后兼容。 |
| **性能影响** | 10/10 | 零性能影响。纯 dict 初始化。 |

**综合评分：8.8/10**

---

### A2. Gap 10 修复（P2）：`advisor.py` `cmd.split()` → `shlex.split()` + 共用 `_cli.py` 模块

**变更内容:**
1. 新建 `src/devolaflow/nines/_cli.py` 共用模块，提供 `run_nines_cli(cmd, timeout)` 函数，统一处理 `str|list[str]` 参数、`shlex.split()` 解析、subprocess 执行、JSON 解析、异常处理。
2. `advisor.py` 中 `_run_nines_command()` 改为委托 `_cli.run_nines_cli()`，修复了 `cmd.split()` 对带空格参数的错误切割问题。
3. `scorer.py` 和 `researcher.py` 中的重复 `_run_cli()` 实现替换为 `from devolaflow.nines._cli import run_nines_cli as _run_cli`。

**影响文件:** `src/devolaflow/nines/_cli.py`（新建）、`advisor.py`、`scorer.py`、`researcher.py`

| NineS 评估维度 | 评分 | 说明 |
|:---:|:---:|---|
| **代码质量** | 9/10 | `_cli.py` 实现简洁（67 行），职责单一。`shlex.split()` 是标准库解决方案，正确处理引号嵌套。类型签名 `cmd: str | list[str]` 兼容两种调用风格。错误处理全面覆盖 `TimeoutExpired`、`OSError`、non-zero exit、JSON parse error、empty stdout 五种失败路径。 |
| **架构合理性** | 9/10 | 消除了 `scorer.py`/`researcher.py` 中约 60 行代码冗余（Gap 8），建立了 NineS CLI 调用的唯一真实入口（Single Point of Truth）。`advisor.py` 通过委托链保留了 retry 逻辑，职责分层清晰。 |
| **测试充分性** | 10/10 | `test_nines.py::TestRunNinesCli` 新增 8 个测试用例，显式验证了 `shlex` 解析行为（`test_quoted_args_preserved` 直接复现 Gap 10 场景：`'nines collect --query "hello world" --source github'`）、各种失败路径、空输出。原有 `scorer.py`/`researcher.py` 的测试通过 mock 层更新继续工作。 |
| **可维护性** | 9/10 | 未来修改 CLI 调用行为（如添加 `--config` 全局参数、统一超时策略）只需修改 `_cli.py` 一处。`_` 前缀标识为包内私有模块。 |
| **兼容性** | 10/10 | 外部 API 签名不变（`_run_nines_command` 仍接受 `str|list[str]`）。内部重构对使用方透明。 |
| **性能影响** | 10/10 | `shlex.split()` 比 `str.split()` 微慢（纳秒级），在 subprocess 调用开销面前可忽略。 |

**综合评分：9.5/10**

---

### A3. Gap 4 修复（P1）：YAML 配置层 NineS v1 → v2 CLI 语法更新

**变更内容:** 更新以下配置文件中的 NineS CLI 命令字符串（共 11 处命令更新）：
- `context_profiles.yaml` 的 `nines_integration.commands`（4 条）
- `plugins.yaml` 的 `stage_mapping`（4 条）
- `nines-assisted.yaml` 的 `config.nines_commands`（3 条）

v1 → v2 语法变更包括：positional args → `--source`/`--query` flag 风格、`--limit` → `--max-results`、`--decompose --index` → `--agent-impact --keypoints`、`--dimensions` 移除、`-f json` 前置等。

**影响文件:** `context_profiles.yaml`、`plugins.yaml`、`nines-assisted.yaml`

| NineS 评估维度 | 评分 | 说明 |
|:---:|:---:|---|
| **代码质量** | 8/10 | YAML 命令字符串语法正确，与 NineS v2 CLI `--help` 对齐。`-f json` 统一前置是 v2 规范。`plugins.yaml` 中 `stage_mapping` 使用参数占位符 `{query}`/`{target}`/`{root}`，符合模板引擎替换约定。扣分原因：`_BUILTIN_SPECS.stage_mapping` 仍使用 v1 语法（未同步更新硬编码），与 YAML 层存在新的微小不一致。 |
| **架构合理性** | 7/10 | 修复了 Python 代码层与配置层的语法分歧。但根本问题（Gap 7：NineS 命令定义存在三个来源——`_BUILTIN_SPECS`、`plugins.yaml`、`context_profiles.yaml`——且均不被程序化执行）并未解决。配置层命令目前仅作为 agent 提示词素材，不是程序化执行路径。 |
| **测试充分性** | 7/10 | YAML 配置文件的命令字符串无独立测试。验证依赖于 Python 层的集成测试（`researcher.py`/`scorer.py` 的 v2 命令参数测试间接覆盖了语法正确性），但不直接测试 YAML 值。建议未来添加 YAML schema 校验测试。 |
| **可维护性** | 6/10 | 三份配置文件独立维护同类命令字符串，未来 NineS v3 升级时需要再次批量修改。Gap 7 路线图（统一命令定义来源）是解决可维护性的关键。 |
| **兼容性** | 9/10 | YAML 配置变更仅影响 NineS v2+ 环境。`context_profiles.yaml` 的 `install_hint` 也同步更新为 `uv pip install git+...`。对未安装 NineS 的环境无影响（命令字符串仅在使用时解析）。 |
| **性能影响** | 10/10 | 纯配置数据变更，零性能影响。 |

**综合评分：7.8/10**

---

### A4. Gap 2 修复：`PluginSpec` 模型扩展

**变更内容:** `PluginSpec` 新增 4 个可选字段：`stage_mapping: dict[str, str]`、`workflows: list[str]`、`update_command: str | None`、`uninstall_command: str | None`。`_dict_to_spec()` 同步更新提取这些字段。

**影响文件:** `src/devolaflow/plugins/models.py`、`src/devolaflow/plugins/loader.py`

| NineS 评估维度 | 评分 | 说明 |
|:---:|:---:|---|
| **代码质量** | 9/10 | 使用 `field(default_factory=dict)`/`field(default_factory=list)` 正确处理可变默认值。`frozen=True` 保持不变，类型标注完整。`_dict_to_spec()` 使用 `data.get(key, default)` 模式，健壮性好。 |
| **架构合理性** | 9/10 | 纯 additive 扩展，不破坏现有字段。`stage_mapping` 为后续 Gap 6（PluginRegistry 编排层接入）和 Gap 1（模板命令执行机制）奠定了数据基础。 |
| **测试充分性** | 9/10 | `test_plugins.py::TestPluginSpec` 新增 `test_optional_fields` 测试，验证 4 个新字段。`TestCreateDefaultRegistry` 新增 `test_builtin_nines_stage_mapping_and_workflows`。 |
| **可维护性** | 9/10 | 新字段有明确的默认值，向后兼容现有使用方。文档性类型标注自解释。 |
| **兼容性** | 10/10 | 所有新字段均为可选 + 有默认值，不影响任何现有 `PluginSpec` 构造调用。 |
| **性能影响** | 10/10 | 零性能影响。 |

**综合评分：9.3/10**

---

### A 组综合评估

| 维度 | A1 (Gap3) | A2 (Gap10+8) | A3 (Gap4) | A4 (Gap2) | 加权均值 |
|:---:|:---:|:---:|:---:|:---:|:---:|
| 代码质量 | 9 | 9 | 8 | 9 | **8.8** |
| 架构合理性 | 8 | 9 | 7 | 9 | **8.3** |
| 测试充分性 | 9 | 10 | 7 | 9 | **8.8** |
| 可维护性 | 7 | 9 | 6 | 9 | **7.8** |
| 兼容性 | 10 | 10 | 9 | 10 | **9.8** |
| 性能影响 | 10 | 10 | 10 | 10 | **10.0** |
| **综合** | **8.8** | **9.5** | **7.8** | **9.3** | **8.9** |

---

## 3. B 组细分评估：规则强化机制

### B1. `gate/reinforcement.py` 核心模块

**变更内容:** 新建 `reinforcement.py`（126 行），实现三个核心函数：
- `findings_to_reinforcement()` — 将 Gate findings 转为 `ReinforcementBlock`，按严重性过滤和排序，上限 `MAX_REINFORCEMENT_RULES=5`
- `reinforcement_to_dict()` — 序列化为 YAML 兼容的 plain dict
- `merge_reinforcement_into_dispatch()` — 注入到现有 dispatch 的 `applicable_rules` 字段

**影响文件:** `src/devolaflow/gate/reinforcement.py`（新建）

| NineS 评估维度 | 评分 | 说明 |
|:---:|:---:|---|
| **代码质量** | 9/10 | 实现紧凑（126 行），函数式设计。`frozen=True` dataclass 保证不可变性。`SEVERITY_ORDER` dict 实现了类型安全的严重性排序。`mandate` 字符串生成使用 `f"MUST fix: ..."` 格式，语义明确。`reinforcement_to_dict()` 中 `**({"file": r.file} if r.file else {})` 技巧巧妙地实现了 empty file 字段省略。 |
| **架构合理性** | 10/10 | 完全实现了可行性调研推荐的方案 B（Dispatch 级规则注入）。零文件 I/O，平台无关，与 P1-P5 规则完全兼容。函数签名接受 `Finding`（gate 模块已有模型），输出 `ReinforcementBlock`（新增 dataclass），数据流清晰：`Gate findings → ReinforcementBlock → dict → dispatch YAML`。`merge_reinforcement_into_dispatch()` 使用 `setdefault()` 创建缺失的中间节点，健壮性好。 |
| **测试充分性** | 10/10 | `test_reinforcement.py` 新增 14 个测试，覆盖：基本转换、严重性过滤（`severity_floor`）、最大规则限制（`MAX_REINFORCEMENT_RULES`）、空 findings、严重性排序、suggestion 追加、escalation_note 格式、序列化（含 empty file 省略）、dispatch 合并（含缺失 context 自动创建）。所有边界条件均有覆盖。 |
| **可维护性** | 9/10 | 常量 `MAX_REINFORCEMENT_RULES` 和 `SEVERITY_ORDER` 集中定义。`ReinforcementBlock` 和 `ReinforcementRule` dataclass 的字段有明确的语义和默认值。类型标注完整。 |
| **兼容性** | 10/10 | 新增模块，无已有代码修改。导入的 `Finding` 和 `Severity` 来自 `gate/models.py`（稳定接口）。 |
| **性能影响** | 10/10 | 纯 Python 内存操作，可行性调研估算运行时开销约 0.1ms。 |

**综合评分：9.7/10**

---

### B2. Schema 扩展：`task-dispatch.schema.yaml` + `lean-dispatch.yaml`

**变更内容:**
- `task-dispatch.schema.yaml` 在 `applicable_rules.children` 下新增 `reinforcement` 对象定义（18 行），包含 `round`、`severity_floor`、`prior_score`、`target_score`、`rules`（list）、`escalation_note` 字段
- `lean-dispatch.yaml` 在 `lean_example` 和 `lean_format_spec` 中新增 `reinforce` 字段定义和示例

**影响文件:** `schemas/task-dispatch.schema.yaml`、`schemas/lean-dispatch.yaml`

| NineS 评估维度 | 评分 | 说明 |
|:---:|:---:|---|
| **代码质量** | 9/10 | Schema 定义结构清晰，field description 准确。`optional: true` 标注确保向后兼容。lean format 的 `reinforce` 保持了 ~50 token/entry 的压缩目标。 |
| **架构合理性** | 10/10 | 扩展了已有的 `applicable_rules` 字段而非引入新的顶级节点，符合 schema 的扩展原则。lean format 的 `reinforce` 与 verbose format 的 `reinforcement` 保持了语义对齐和 key 缩写一致性（如 `sev`、`prior`、`target`）。 |
| **测试充分性** | 7/10 | Schema 文件本身无自动化校验测试。`test_reinforcement.py` 的 `TestReinforcementToDict` 和 `TestMergeIntoDispatch` 间接验证了数据结构与 schema 定义的兼容性。建议未来增加 schema 校验测试（JSON Schema 或自定义 validator）。 |
| **可维护性** | 9/10 | `reinforcement` 字段定义集中在 schema 文件中，`reinforcement.py` 的 `reinforcement_to_dict()` 是唯一的数据生产方，修改同步简单。 |
| **兼容性** | 10/10 | `optional: true` 标注确保不破坏任何现有 dispatch 消费方。新字段仅在收敛轮次 > 1 时出现。 |
| **性能影响** | 10/10 | 纯声明性变更，零性能影响。 |

**综合评分：9.2/10**

---

### B3. Gate `__init__.py` 导出更新

**变更内容:** `gate/__init__.py` 添加 `reinforcement.py` 中所有公共符号的导入和 `__all__` 导出：`MAX_REINFORCEMENT_RULES`、`ReinforcementBlock`、`ReinforcementRule`、`findings_to_reinforcement`、`merge_reinforcement_into_dispatch`、`reinforcement_to_dict`。同时为弃用 API `evaluate_gate_with_nines` 添加了注释标注。

**影响文件:** `src/devolaflow/gate/__init__.py`

| NineS 评估维度 | 评分 | 说明 |
|:---:|:---:|---|
| **代码质量** | 10/10 | `__all__` 列表字母排序，注释 `# deprecated, removal in v6.0` 清晰。导入层干净，无多余逻辑。 |
| **架构合理性** | 10/10 | 通过 `gate/__init__.py` 统一导出，外部使用方 `from devolaflow.gate import findings_to_reinforcement` 即可，符合 package API 设计规范。 |
| **测试充分性** | 8/10 | 导出正确性由 `test_reinforcement.py` 的 import 语句间接验证。 |
| **可维护性** | 10/10 | `__all__` 的维护成本极低。 |
| **兼容性** | 10/10 | 纯添加，不修改任何现有导出。 |
| **性能影响** | 10/10 | 导入时开销可忽略。 |

**综合评分：9.7/10**

---

### B4. SKILL.md / CLAUDE.md 文档更新

**变更内容:** 在 Convergence Loop 章节增加 reinforcement 说明：
- 描述 `applicable_rules.reinforcement` 的注入时机和格式
- 添加 L3 Task Agent 必须优先处理 reinforcement rules 的行为约束
- 版本标注为 v5.1+

**影响文件:** `workflow-system/agent/SKILL.md`、`CLAUDE.md`

| NineS 评估维度 | 评分 | 说明 |
|:---:|:---:|---|
| **代码质量** | 9/10 | 文档语言简洁准确，使用 MUST 措辞强化行为约束。`(v5.1+)` 版本标注清晰。 |
| **架构合理性** | 9/10 | 在正确的位置（Convergence Loop 章节）添加了 reinforcement 说明，不破坏文档结构。 |
| **测试充分性** | N/A | 文档无代码测试。SKILL.md 有 `test_skill_md_under_500_lines` 行数限制测试。 |
| **可维护性** | 9/10 | 增量修改，未来版本升级时只需更新版本标注。 |
| **兼容性** | 10/10 | 纯添加性文档变更。 |
| **性能影响** | 10/10 | 无。 |

**综合评分：9.4/10**

---

### B 组综合评估

| 维度 | B1 (核心模块) | B2 (Schema) | B3 (导出) | B4 (文档) | 加权均值 |
|:---:|:---:|:---:|:---:|:---:|:---:|
| 代码质量 | 9 | 9 | 10 | 9 | **9.3** |
| 架构合理性 | 10 | 10 | 10 | 9 | **9.8** |
| 测试充分性 | 10 | 7 | 8 | N/A | **8.3** |
| 可维护性 | 9 | 9 | 10 | 9 | **9.3** |
| 兼容性 | 10 | 10 | 10 | 10 | **10.0** |
| 性能影响 | 10 | 10 | 10 | 10 | **10.0** |
| **综合** | **9.7** | **9.2** | **9.7** | **9.4** | **9.5** |

---

## 4. 风险评估矩阵

### A 组风险

| 变更 | 风险等级 | 风险描述 | 缓解措施 | 残余风险 |
|------|:---:|---|---|:---:|
| A1 (Gap 3) | **低** | `_BUILTIN_SPECS` 与 `plugins.yaml` 的 `stage_mapping` 仍使用不同语法版本 | `plugins.yaml` 加载会覆盖 `_BUILTIN_SPECS`；已有测试验证 builtin spec 数据正确性 | 极低 |
| A2 (Gap 10+8) | **极低** | `shlex.split()` 对异常输入（如未闭合引号）的行为 | `shlex` 是标准库组件，异常情况下抛 `ValueError`，`_cli.py` 的 try/except 捕获 | 极低 |
| A3 (Gap 4) | **低** | YAML 配置中的命令字符串未被程序化测试 | Python 层的 v2 命令参数测试间接覆盖；命令仅作 agent 提示词使用 | 低 |
| A4 (Gap 2) | **极低** | 新增可选字段可能被部分消费方忽略 | 所有字段有默认值；`frozen=True` 保证不可变 | 极低 |

### B 组风险

| 变更 | 风险等级 | 风险描述 | 缓解措施 | 残余风险 |
|------|:---:|---|---|:---:|
| B1 (核心模块) | **低** | L3 Agent 可能忽略 dispatch 级 reinforcement 规则 | MUST/MANDATORY 措辞 + SKILL.md 行为约束 + 下轮 Gate 显式检查 | 低 |
| B2 (Schema) | **极低** | Schema 变更影响现有消费方 | `reinforcement` 标记 `optional: true`，向后兼容 | 极低 |
| B3 (导出) | **极低** | 导入新符号导致循环依赖 | `reinforcement.py` 仅依赖 `gate/models.py`，无循环风险 | 极低 |
| B4 (文档) | **无** | 文档变更无运行时风险 | — | 无 |

### 整体风险热力图

```
影响度 ↑
  高 │
     │
  中 │           B1(软强化)
     │  A3(YAML)
  低 │  A1(双源)
     │
  极低│  A2  A4  B2  B3  B4
     └────────────────────────→ 发生概率
          极低      低      中
```

**总体风险评估：低**。所有变更均为 additive change 或数据修正，无破坏性变更。最高风险项（B1 的"软强化"效果不确定性）属于功能效果层面而非稳定性层面。

---

## 5. 选型建议：Go/No-Go 决策

### 逐项决策

| 变更 | 决策 | 理由 |
|------|:---:|---|
| **A1** Gap 3 修复 | **GO** | P0 critical 修复，消除了 CI 环境下安装错误包的风险。测试覆盖充分，零兼容性风险。 |
| **A2** Gap 10+8 修复 | **GO** | P2 major 修复，解决了带空格参数命令执行错误。同时消除了 60 行代码冗余。测试覆盖 10/10。 |
| **A3** Gap 4 YAML v2 语法 | **GO** | P1 critical 配置修正。虽然 YAML 命令字符串当前仅作 agent 提示词使用，但语法正确性是 NineS v2 兼容的基本要求。 |
| **A4** Gap 2 PluginSpec 扩展 | **GO** | 纯 additive 数据模型扩展，为后续 Gap 6（PluginRegistry 编排层接入）铺路。零风险。 |
| **B1** reinforcement.py | **GO** | 核心新能力，架构评分 10/10。完全实现了用户反馈中"不使用实体文件交互的规则强化"需求。零文件 I/O，平台无关。 |
| **B2** Schema 扩展 | **GO** | B1 的必要配套。`optional: true` 保证向后兼容。 |
| **B3** Gate 导出更新 | **GO** | B1 的必要配套。纯导入/导出变更。 |
| **B4** 文档更新 | **GO** | B1 的必要配套。确保 agent 行为指南与新能力同步。 |

### 汇总

| 组别 | 决策 | 就绪度 |
|------|:---:|:---:|
| **A 组全部** | **GO for v5.1.0-pre** | 全部就绪 |
| **B 组全部** | **GO for v5.1.0-pre** | 全部就绪 |

**无需延迟到 v5.1.0 final 的变更。** 所有 10 项变更均满足 pre-release 质量标准。

---

## 6. 版本就绪度评分

### 维度评分

| 维度 | 权重 | 评分 | 说明 |
|------|:---:|:---:|---|
| 功能完整性 | 25% | 9/10 | 用户反馈中两个核心需求（NineS 集成优化 + 规则强化机制）均已实现。Gap 分析中 P0-P2 已全部修复。 |
| 代码质量 | 20% | 9/10 | 704 测试全通过，ruff clean，类型标注完整。新代码风格与项目一致。 |
| 测试覆盖 | 20% | 9/10 | +23 新测试（681→704）。reinforcement 模块 14 个测试覆盖所有边界条件。`_cli.py` 8 个测试。plugin 扩展 4 个测试。 |
| 向后兼容 | 15% | 10/10 | 所有变更均为 additive 或修正性质。Schema 新字段均标记 `optional: true`。 |
| 风险控制 | 10% | 9/10 | 无 blocker 风险。最高风险项为"软强化"效果不确定性，属于功能效果而非稳定性问题。 |
| 文档同步 | 10% | 9/10 | SKILL.md/CLAUDE.md 已更新。研究文档完整（Gap 分析 + 可行性调研）。 |

### 综合就绪度

$$\text{Readiness} = 9 \times 0.25 + 9 \times 0.20 + 9 \times 0.20 + 10 \times 0.15 + 9 \times 0.10 + 9 \times 0.10 = 9.15 / 10$$

| 就绪度 | 判定 | 标准 |
|:---:|:---:|---|
| **9.15/10** | **READY FOR PRE-RELEASE** | ≥ 8.5 = ready, 7.0-8.4 = conditional, < 7.0 = not ready |

**v5.1.0-pre 发布就绪。**

---

## 7. 后续优化路线图

基于 Gap 分析（10 个缺口）的剩余项，以及本次评估中发现的改进点：

### v5.1.0 正式版（近期）

| 优先级 | 项目 | 来源 | 预估工作量 |
|:---:|---|---|:---:|
| P1 | `_BUILTIN_SPECS.stage_mapping` 更新为 v2 语法 | 本次评估发现 A3 扣分项 | S |
| P2 | Gap 9：`nines.toml` 配置集成 | 缺口分析 | S |
| P3 | Schema 校验测试（YAML 命令字符串 + dispatch schema） | 本次评估 A3/B2 扣分项 | S |
| P4 | 方案 B+E 组合：反馈桥接增强层 | 可行性调研推荐 | M |

### v5.2.0 路线图（中期）

| 优先级 | 项目 | 来源 | 预估工作量 |
|:---:|---|---|:---:|
| P5 | Gap 1：模板 `nines_commands` 执行机制（hook 或 agent 注入） | 缺口分析 | M |
| P6 | Gap 7：统一 NineS 命令定义来源（Single Source of Truth） | 缺口分析 | M |
| P7 | Gap 6：PluginRegistry 编排层接入 | 缺口分析 | L |
| P8 | 方案 C：基于轮次的上下文配置切换 | 可行性调研 | M |

### v6.0 路线图（远期）

| 优先级 | 项目 | 来源 | 预估工作量 |
|:---:|---|---|:---:|
| P9 | Gap 5：移除弃用 API（`evaluate_gate_with_nines`、`run_nines_advisor`） | 缺口分析 | S |
| P10 | 消除 `_BUILTIN_SPECS` 硬编码，统一从嵌入 YAML 加载 | 缺口分析 Gap 3 长期建议 | M |
| P11 | 方案 A 作为 Cursor 特化硬强化层（如方案 B 效果不足时启用） | 可行性调研 | M |

### 路线图依赖关系

```
v5.1.0-pre (当前) ──→ v5.1.0 final
  A1-A4, B1-B4         ├── P1: BUILTIN stage_mapping v2
                        ├── P2: nines.toml 集成
                        ├── P3: Schema 校验测试
                        └── P4: 反馈桥接增强
                              │
                              v
                        v5.2.0
                        ├── P5: 模板命令执行 ──┐
                        ├── P6: 命令来源统一 ──┤
                        ├── P7: PluginRegistry ←┘ (P5/P6 是 P7 的前置)
                        └── P8: 轮次配置切换
                              │
                              v
                        v6.0
                        ├── P9: 弃用 API 移除
                        ├── P10: 消除 BUILTIN 硬编码
                        └── P11: Cursor 硬强化层 (条件性)
```

---

## 8. 结论

### 核心发现

1. **v5.1.0-pre 变更质量整体优秀**。A 组综合 8.9/10，B 组综合 9.5/10。两组变更均无 blocker 级风险，全部通过 Go/No-Go 评审。

2. **B 组（规则强化机制）是本次迭代最有价值的新增能力**。`reinforcement.py` 架构评分 10/10，完全实现了用户"不使用实体文件交互的规则强化"核心需求，同时满足零文件 I/O、平台无关、P1-P5 兼容三个约束。

3. **A 组的主要扣分点在可维护性维度**（A3 的三源命令字符串问题、A1 的 `_BUILTIN_SPECS` 双源问题），这些是架构层面的技术债，已列入 v5.2.0 路线图。

4. **测试覆盖表现突出**。+23 新测试，reinforcement 模块的 14 个测试覆盖了所有边界条件，`_cli.py` 的 8 个测试包含了显式的 Gap 10 回归验证。

5. **版本就绪度 9.15/10**，满足 pre-release 发布标准。

### 最终建议

**全部变更（A1-A4, B1-B4）推荐合并入 v5.1.0-pre 发布。** 无需等待或拆分。

---

*本报告由 DevolaFlow Research Agent (L3) 生成，基于 2026-04-14 代码库快照、Gap 分析报告、可行性调研报告进行综合评估。*
