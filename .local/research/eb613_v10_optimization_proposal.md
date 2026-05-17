# DevolaFlow Optimization Proposal — Response to EvoBench v6.1.3 (eb613) Feedback

> **Status:** Phase-0 optimization proposal (research-only).
> **Author:** L1 Research Stage Agent.
> **Date:** 2026-05-04.
> **Source feedback:** `.local/feedbacks/from_evobench/eb613_for_devola_v10.0.0.md` (EvoBench v6.1.3, generated 2026-05-03).
> **Repo state at proposal:** v10.3.0 (commit `f1d9652` on `feat/v10.2.0-cycle`; PR #117 OPEN; v10.2.0 cycle just closed).
> **External tools (S-7):**
> - DevolaFlow / EvoBench: https://github.com/YoRHa-Agents/DevolaFlow
> - NineS: https://github.com/YoRHa-Agents/NineS
> - Si-Chip: https://github.com/YoRHa-Agents/Si-Chip
> **Scope:** This document proposes optimization directions ONLY. No code changes, no SI-1 gap analysis, no cycle plan. The operator decides whether/how to act; if approved, this artifact feeds a future SI-1 gate.

---

## §1 — Executive Summary

EvoBench v6.1.3 declares DevolaFlow v10.0.0 **HEALTHY**: growth-matrix `q=0.5898 / pr=0.3099`, **+0.0077 q vs v9.1.0** and **+0.245 q (+71%) vs `plan_and_agent`**. The v10 marginal-band factor (1.760) lift translated into a 4.9:1 damping ratio — saturation behaviour, not regression. The current point sits at **88.1% of the logistic ceiling** (`L=0.6698`); inside the existing 337-task corpus the remaining factor-lift headroom is only ~0.06–0.08 q. **Breaking the 0.65 ceiling requires new R-rules covering uncovered capabilities — that is squarely a DevolaFlow protocol-coverage problem, not a factor-tuning problem.**

The eb613 feedback identifies **9 actionable directions (H-1..H-5, M-1..M-3, L-1)**. The Top-3 are **`mlops` (gap 0.802, R13)**, **`long_horizon` (gap 0.792, R14)**, and **`agentic_planning` (gap 0.783, R15)** — the three highest gap_score capability tags out of 37, all currently `r_rule_status="no rule"`. They concentrate on the **Production tier** (50 tasks, 14.8% of corpus, `pass_rate=0.000` across all 9 generations × 27 patches). DevolaFlow has **no protocol coverage for any of the three**: a `Glob workflow-system/agent/**/*.md` + `Grep` for `mlops|long_horizon|agentic_planning|multi_horizon` returns zero matches across SKILL.md, all 14 reference docs, all 22 builtin templates, and all 3 examples.

**Recommended posture:** ship a 3-capability MINOR cycle (**v10.4.0**) targeting **H-3 long_horizon → H-2 mlops → H-4 agentic_planning** as 3 dedicated PVs, with a 4th PV revisiting **H-5 R9/R12 second-iteration** under DevolaFlow control (multipliers stay EvoBench-side). H-1 (Production-tier 0% pass rate) requires **multi-cycle DF work + EvoBench corpus coordination** and must defer to v10.5.0+. Net expected impact, conditional on EvoBench R13/R14/R15 multipliers landing in the 1.20–1.30 range: **+0.04..+0.06 mean quality** (+0.02..+0.04 from DF protocol coverage alone if EvoBench R-rules don't land in the same window).

**Two risks the operator should hold:** (i) DF-side protocols ship the *infrastructure* — actual q-lift gating waits on EvoBench R-rule multiplier landing; if EvoBench defers, the cycle ships with infrastructure-only deliverables and per-protocol q-lift evidence is **operator-deferred**, repeating the v9.5.0 → v10.2.0 dogfood-deferred precedent; (ii) the v10.0.0 retrospective §3.5 telegraphs an S-11 candidate ("Parallel Wave Dispatch Invariant") for v10.4.0 evaluation — if H-2..H-4 land alongside an S-11 evaluation, the SI-1 architecture-rationality SI-3 §3.2 score (≥9.5/10 floor per W-21) becomes the gating constraint for the cycle, not the W-3 ≥9.0 composite.

---

## §2 — Findings Digest (verbatim where it matters)

### §2.1 — Healthy v10.0.0 baseline (no immediate action)

Verbatim from `.local/feedbacks/from_evobench/eb613_for_devola_v10.0.0.md` §1.1:

| 指标 | v10.0.0 | v9.2.4 | v9.1.0 | v2.0.0 | naive |
|---|---:|---:|---:|---:|---:|
| `quality_mean` | **0.5898** | 0.5867 | 0.5821 | 0.3174 | 0.1708 |
| `pass_rate_mean` | **0.3099** | 0.3086 | 0.3055 | 0.0554 | 0.0000 |
| `tokens_total_mean` | 30 949 | 30 884 | 30 894 | 30 900 | 30 773 |
| `latency_p50 (s)` | 28.81 | 28.55 | 28.48 | 28.45 | 28.69 |
| `factor (AX-4)` | **1.760** | 1.746 | 1.722 | 0.95 | 0.55 |

> "v10 → v9.1 +0.038 factor 跳变换来 +0.0077 q（**4.9:1 阻尼比**，与 eb410 v9.0.1→v9.1.0 的 4.3:1 相当）——v10 marginal band 仍处 simulator clamp 饱和段。tokens / latency 在噪声内，cost_per_quality 微升至 12 939。"

**Annotation.** Baseline state — **no DF action required**. The +0.0077 q lift correctly translates the +0.038 factor lift through clamp damping; the tokens / latency / cost_per_quality numbers are within noise. The `pass_rate_mean=0.3099` ranks `naive < basic < v2 < plan < v9 < v10` per AX-4 — chain preserved.

### §2.2 — Capability gaps (the actionable surface)

Verbatim from feedback §2.2:

| rank | capability_tag | n_tasks | quality_mean | pass_rate | gap_score | r_rule_status |
|---:|---|---:|---:|---:|---:|---|
| 1 | **mlops** | 19 | 0.1977 | 0.0060 | **0.8023** | no rule (R13 候选) |
| 2 | **long_horizon** | 48 | 0.2079 | 0.0050 | **0.7921** | no rule (R14 候选) |
| 3 | **agentic_planning** | 32 | 0.2166 | 0.0051 | **0.7834** | no rule (R15 候选) |
| 4 | multi_modal | 10 | 0.3574 | 0.2307 | 0.6426 | no rule |
| 5 | incident_response | 10 | 0.3894 | 0.2722 | 0.6106 | no rule |
| 6 | multi_module | 59 | 0.3911 | 0.2664 | 0.6089 | no rule |
| 7 | delegation | 5 | 0.4640 | 0.3847 | 0.5360 | no rule |
| 8 | negotiation | 12 | 0.4691 | 0.3728 | 0.5309 | no rule |
| 9 | decomposition | 20 | 0.4744 | 0.4086 | 0.5256 | no rule |
| 10 | instruction_following | 10 | 0.5028 | 0.4495 | 0.4972 | no rule |

**Per-row DF mapping.**

| rank | tag | DF protocol coverage today | Bound |
|---:|---|---|---|
| 1 | mlops | **absent** — `Grep mlops` over `workflow-system/` returns zero hits. No template; no role variant; no reference doc. | **DF-bound primary** |
| 2 | long_horizon | **partial** — `agent-workspace.md` ships change folder + handoff envelope (multi-session state), `execution-protocol.md` §2 ships checkpoint/resume; neither names "long-horizon" or formalises multi-day cadence. | **DF-bound primary** |
| 3 | agentic_planning | **partial** — `plan-mode-enforcement.md` ships `plan_and_agent` (single-pass plan-then-execute); no multi-step strategic-planning role. | **DF-bound primary** |
| 4 | multi_modal | absent | DF-bound but **secondary** — gated on R16 EvoBench landing (R13 first, per feedback §4.2) |
| 5 | incident_response | partial via `hotfix` template + `incident_commander_simulation` task tags | **DF-bound secondary** |
| 6 | multi_module | partial via `change-driven` template (owned_files manifest); not a dedicated capability | **DF-bound secondary** |
| 7 | delegation | partial — A-1 4-layer hierarchy IS delegation; but `delegation` capability tag implies a different L0→external-team handoff | **DF-bound secondary** |
| 8 | negotiation | absent | corpus-bound (no obvious DF protocol mapping) |
| 9 | decomposition | covered — `decomposition-gate.md` IS the DF surface; the `gap_score=0.526` reflects EvoBench-side scoring, not DF coverage | **EvoBench-bound** |
| 10 | instruction_following | covered — DF dispatch contract IS instruction-following; `gap_score=0.497` reflects per-LLM behaviour, not DF | **EvoBench-bound** |

**Verdict.** Rows 1–3 are **DF-bound primary** (DF can directly affect via new templates/roles/refs). Rows 4–8 are **DF-bound secondary** (depend on EvoBench R-rule landing for q-lift to materialise). Rows 9–10 are **EvoBench-bound** (DF coverage is already complete; gap_score reflects scoring methodology or per-LLM behaviour).

### §2.3 — Production tier hard ceiling

Verbatim from feedback §1.4 + §2.1:

```
tier         v2     v3     v4     v5     v6     v7     v8     v9     v10
Simple      0.91   0.96   1.00   1.00   1.00   1.00   1.00   1.00   1.00
Medium      0.39   0.80   0.95   1.00   1.00   1.00   1.00   1.00   1.00
Complex     0.00   0.06   0.29   0.59   0.86   0.99   1.00   1.00   1.00
VeryComplex 0.00   0.00   0.00   0.00   0.00   0.02   0.05   0.07   0.09
Production  0.00   0.00   0.00   0.00   0.00   0.00   0.00   0.00   0.00
```

> "**Production tier 是 v2..v10 硬上限**——9 代 27 patches **无一个 cell pass**（pr=0.0 全程）。"

| Tier | n_obs | quality_mean | pass_rate | tokens_mean |
|---|---:|---:|---:|---:|
| **Production** | 1 890 | **0.3569** | **0.0000** | 54 655 |

**Annotation.** Production tier = **50 tasks, 1890 observations**. Capability concentration per feedback §2.3: `long_horizon 47/50 (94%) / agentic_planning 28/50 (56%) / mlops 18/50 (36%) / multi_module 15/50 / data_pipeline 14/50`. Per feedback §3.1:

> "Production `q=0.357 / pr=0.000` 表示 v10 在多日 Kaggle / live-env 任务上拿到 **35 % partial credit**，距 50 % 通过门槛 **0.143**——是真实 partial-completion 信号而非完全失败。"

**Boundary verdict.** This row is **partly DF-bound (long-horizon scaffold absent + mlops protocol absent + agentic_planning protocol absent → can lift q from ~0.36 toward ~0.45) AND partly EvoBench-bound (the 0.50 pass_rate threshold is binary — partial credit currently scores quality_mean but NOT pass_rate; fixing this requires EvoBench corpus / scoring methodology change)**. DF-side actions push q without crossing the pass-rate threshold; EvoBench-side action is required to convert partial credit into pass_rate signal.

### §2.4 — Logistic saturation

Verbatim from feedback §3.3:

```
generation:  v2     v3     v4     v5     v6     v7     v8     v9     v10
quality:    0.317  0.359  0.417  0.453  0.488  0.535  0.569  0.582  0.590
Δq:         —     +0.041 +0.058 +0.037 +0.035 +0.047 +0.034 +0.013 +0.008
```

> "**最优拟合**：`L = 0.6698`、`k = 0.300`、`x0 = 2.50`，SSE = 0.000530."
> "拟合上界 L ≈ 0.670 — v10 已实现 **88.1 %**."
> "预测：v11 ≈ 0.621 (Δ +0.032)、v12 ≈ 0.633 (Δ +0.043)、v15 ≈ 0.654 (Δ +0.064)."
> "**结论**：现行 337 任务矩阵下，DF 单纯 factor lift 顶多再涨 0.06-0.08 q（约 0.65 上界）。**突破上限只能新 R-rule 拓展 capability 覆盖**——这在 DF 责任范围内。"

**Implication.** Factor-lift inside the v10 marginal band is asymptotically capped at ~0.65 q. **The lever DF can pull is protocol depth on uncovered capabilities (rows 1–3 of §2.2), NOT factor-lift refinement.** This is the strategic anchor of every direction in §3.

### §2.5 — R-rule second-iteration evidence

Verbatim from feedback §4.1:

| rule_id | tag | since | mult | n_apply | current_q | gap_to_one | status |
|---:|---|---|---:|---:|---:|---:|---|
| **R8** | adversarial | v7.2.4 | 1.18 | 47 | 0.4966 | **0.5034** | active |
| **R9** | convergence | v7.2.2 | 1.12 | 49 | 0.3888 | **0.6112** | active |
| **R10** | multi_session | v7.2.3 | 1.12 | 48 | 0.5096 | 0.4904 | active |
| **R11** | long_context | v7.2.5 | 1.18 | 46 | 0.5326 | 0.4674 | active |
| **R12** | multi_repo | v7.2.6 | 1.15 | 45 | 0.3823 | **0.6177** | active |

**Annotation.**

- **R9 (convergence)** `gap_to_one=0.611` since v7.2.2 with multiplier 1.12. DF surfaces: `src/devolaflow/gate/reinforcement.py` (W-8 / SI-9 reinforcement primitive — 5 reinforcement rules per round, severity-filtered), `references/decomposition-gate.md` §6 convergence loop, `references/plan-mode-enforcement.md` §6.1–§6.4 reinforcement payload + L3 obligation + round-aware escalation. **Action surface**: revisit whether DF's convergence-loop machinery is exhausted or still has slack — quality 0.39 with a 0.6 gap suggests the DF protocol **may** be DF-bound, not just multiplier-bound.
- **R12 (multi_repo)** `gap_to_one=0.618` since v7.2.6 with multiplier 1.15. DF surfaces: `repos` canonical_order position 13 in `schemas/lean-dispatch.yaml` (APPENDED v7.2.6), the `repos` block consumed by L0/L1 dispatchers. **Action surface**: revisit whether DF's multi-repo dispatch surface (single `repos` field + per-repo manifest) is the right shape for cross-repo work, or whether richer multi-repo coordination protocol is needed.

---

## §3 — Optimization Directions (mapped to concrete DF surfaces)

For EACH direction in feedback §7 (H-1..H-5, M-1..M-3, L-1), this section produces a structured proposal with verbatim problem statement, file-level DF-side scope, coordination requirement, effort, dependencies, acceptance criteria, risks, and out-of-scope.

### §3.1 — H-1 — Production tier 0% pass-rate穿透

**Problem statement (verbatim from feedback §7.1):**
> "**[H-1] Production tier 通过率穿透——v2..v10 全程 0 % 是 DF 进化最大硬上限**
>
> - **数据**：9 代 27 patches × ~510 K Production task-trials，**pass_rate 始终为 0**；即使最强 `claude-code · opus4.7 · max · v10.0.0` 也只到 q=0.36 / pass=0.00。
> - **影响**：tier=Production (50 任务，corpus 14.8 %)；capability 集中 mlops/long_horizon/agentic_planning/multi_modal/data_pipeline。
> - **方向**：(i) 引入 dedicated long-horizon protocol（cross-session checkpoint + state restore SOP）；(ii) 与 EvoBench 协作探索 Production partial-credit scoring；(iii) live-mode 优先 schedule。"

**DF-side concrete proposal:**

- **NEW** `workflow-system/agent/templates/builtin/long-horizon.yaml` — multi-day workflow template; stages `propose → checkpoint → apply ↔ verify → checkpoint → archive`; `max_rounds=10` (vs default 5); checkpoint every wave per `execution-protocol.md` §2.4.
- **NEW** `workflow-system/agent/references/long-horizon-protocol.md` (Large tier ≤1000 lines) — multi-day SOP: cross-session state restore (extends `agent-workspace.md` STATUS.yaml + handoff envelopes); progressive planning (re-plan boundary at each checkpoint); long-tail work resilience (24h+ task survives session restart); cite `R10 multi_session` + `R11 long_context` as adjacent prior art.
- **EXTEND** `workflow-system/agent/references/agent-workspace.md` §3 Lifecycle FSM with **§3.5 Long-Horizon Mode** subsection — formalise multi-day cadence: (a) `STATUS.yaml.long_horizon_mode: true` field, (b) checkpoint cadence = every wave or every 4 hours whichever sooner, (c) state-restore protocol on session resume, (d) handoff envelope `seq` increments at every checkpoint. The `STATUS.yaml` schema (`schemas/agent-workspace/change-status.yaml`) gains a single new optional field `long_horizon_mode: bool` — additive, byte-stable.
- **EXTEND** `workflow-system/agent/references/decomposition-gate.md` §6.5 with explicit long-horizon checkpoint hook — every wave gate PASS triggers checkpoint write per `execution-protocol.md` §2.4.

**Coordination required with external tools:**

- **EvoBench: YES (HARD).** The 0.0 `pass_rate` ceiling is corpus-side: Production tasks score `quality_mean` but the binary 0.5 threshold for `pass_rate` doesn't credit partial completions even when q reaches ~0.45. Production-tier partial-credit scoring (e.g. `pass_rate_partial = max(0, q-0.4)/0.1`) is an EvoBench corpus / scoring methodology change — DF cannot affect this from its codebase.
- **NineS: PARTIAL.** `nines analyze --target-path src/devolaflow/agent_workspace/ --depth deep` validates the long-horizon protocol's architectural soundness pre-cycle.
- **Si-Chip: NO direct dependency** — long-horizon protocol is structural, not skill-corpus-shrink.

**New env flags:** Per W-20 §3 reuse-first analysis — **REUSE `DEVOLAFLOW_AGENT_WORKSPACE`**. The activation surface is identical ("workspace folder management for in-flight changes" extends naturally to "long-horizon multi-day mode"); a NEW `DEVOLAFLOW_LONG_HORIZON` flag would fail W-20's orthogonality test. Operator opt-in via `STATUS.yaml.long_horizon_mode: true` (data-channel, not env flag).

**New Soul rules:** Not required. The H-1 protocol is operational, not invariant; closest fit would be reinforcement of S-9 handoff append-only (already covers checkpoint envelopes). W-21 cap = 12 — no consumption proposed.

**Estimated impact (q-points and pass_rate, where computable):**

- **DF-side alone:** lifts Production-tier `quality_mean` from 0.357 → ~0.45 (ceiling-permitting; the 47/50 long_horizon-tagged tasks are direct beneficiaries). Per feedback §3.3 logistic L=0.6698, this corresponds to ~+0.02..+0.04 mean-quality at the corpus level (Production tier weight ~14.8%).
- **DF + EvoBench R14 (long_horizon multiplier 1.20–1.30):** an additional ~+0.02 mean quality.
- **DF + EvoBench partial-credit scoring:** Production `pass_rate` lifts from 0.0 toward ~0.05–0.10 (the v7.x VeryComplex pass-rate trajectory restarted at the next tier).
- **DF-bound; EvoBench gating dominates the pass_rate axis. State explicitly: H-1's pass_rate impact is gated by EvoBench scoring methodology change.**

**Effort estimate:** **L (full MINOR cycle).** Long-horizon protocol design + reference doc + template + agent-workspace extension + checkpoint hook ≈ 4–6 PVs. Multi-cycle if EvoBench coordination delays.

**Dependencies:**

- §3.2 H-2 (mlops) protocol — Production tier capability concentration overlaps; H-2 should ship before H-1 to avoid scope ballooning.
- §3.3 H-3 (long_horizon R14) — H-1 ABSORBS the H-3 long_horizon protocol; if both are pursued, H-3 ships first as a dedicated PV inside H-1's MINOR cycle, then H-1 wraps up with the cross-tier integration.
- **Operator decisions required:** (a) approve EvoBench coordination start? (b) approve long-cycle (~6 PVs vs 3 PVs); (c) approve `STATUS.yaml` schema additive field?

**Acceptance criteria (testable):**

- W-3 SI-3 ≥ 9.0 STRICT-MINOR-cycle-close (per A-4 / v10.3.0 evaluation precedent).
- `tests/test_long_horizon_protocol.py` (NEW) — pin (a) `STATUS.yaml.long_horizon_mode` schema field exists and defaults to False; (b) checkpoint cadence on wave gate PASS; (c) state-restore protocol on session resume reads the latest checkpoint; (d) handoff envelope `seq` monotonic across checkpoints (S-9 invariant preserved).
- W-4 SI-4 EvoBench composite stable across all 53 scenarios (baseline `v10.4.0_baseline.json` from W-16 wholesale at cycle-start).
- A-2.1 frozen prefix (positions 1–12) byte-stable across 11 historical baselines (10 existing + new `v10.4.0` baseline).
- C-4 line budget: `references/long-horizon-protocol.md` ≤ 1000 lines (Large tier).

**Risks:**

- **R-1 EvoBench coordination delay:** likelihood MED, impact HIGH. If EvoBench partial-credit scoring lands in v6.2+ (not v6.1.x patch), DF ships infrastructure-only; pass_rate impact deferred. **Mitigation:** ship DF-side independently; iterate on quality_mean improvement; track Production tier quality_mean delta per PV.
- **R-2 Schema invariant break:** likelihood LOW, impact CRITICAL. New `STATUS.yaml.long_horizon_mode` field could violate `schemas/agent-workspace/change-status.yaml` byte invariants. **Mitigation:** additive optional field, default False, all existing tests pass byte-identically.
- **R-3 Long-horizon mode bloats every dispatch:** likelihood LOW, impact MED. Even non-long-horizon dispatches pay the schema overhead. **Mitigation:** R5-strict default-OFF; no dispatch payload changes when `long_horizon_mode != true`.

**Out-of-scope (within this proposal direction):**

- We do NOT propose modifying EvoBench R14 multiplier — that's EvoBench-side.
- We do NOT propose live-mode execution (Production-tier graduation to live-LLM is separate from in-simulator partial-credit scoring); per feedback §10 caveats, live-mode lands in a future EvoBench cycle.
- We do NOT propose changing the `pass_rate` definition in DF's gate scoring — DF's gate `pass_rate` (per `references/decomposition-gate.md` §5) is a different axis from EvoBench's `pass_rate_mean` benchmark statistic; conflating the two is a category error.

### §3.2 — H-2 — `mlops` capability protocol (R13 candidate)

**Problem statement (verbatim from feedback §7.1):**
> "**[H-2] mlops capability 缺位——v10 q 仅 0.198，是 R13 候选**
>
> - **数据**：mlops 5 tier 平均 q=0.198 / gap_score=0.802（**全 37 capability 中最高**）；19 task 全 Production；Bottom-50 任务 36 % 含此 tag。
> - **方向**：v10.x patch 或 v10.1.0 minor 引入 dedicated `mlops_protocol`（ML 训练/评估/部署闭环、Kaggle awareness、checkpoint resume、grid search orchestration）。EvoBench 加入 R13 后预计给 mlops 拉升 ~0.04-0.06 q。"

**DF-side concrete proposal:**

- **NEW** `workflow-system/agent/templates/builtin/mlops.yaml` — ML-task workflow template; stages `data-survey → train-eval → tune → deploy → monitor` (mapping per `meta-framework.md` Alias Mapping Table: `data-survey → analyze`, `train-eval → implement+test`, `tune → loop(implement+test)`, `deploy → deploy`, `monitor → monitor`); `gate_type: convergence` on tune stage; `max_rounds=5`; primary teams Research+Implement+Test.
- **NEW** `workflow-system/agent/references/mlops-protocol.md` (Large tier ≤1000 lines) — ML training/evaluation/deployment SOP: (1) Kaggle-style awareness (data-card audit, leakage check, holdout discipline), (2) checkpoint-resume protocol (extends H-1 long-horizon scaffold), (3) grid-search orchestration (multi-config dispatch via L2 wave parallel mode + result aggregation in L1 stage), (4) reproducibility primitives (seed pinning, env capture, artifact hashing).
- **EXTEND** `workflow-system/agent/references/team-roles.md` §4 with optional `mlops_engineer` role variant (specialisation of Implement team — same input/output contracts plus ML-specific quality criteria like "no data leakage in train/test split", "checkpoint resumability tested"). Does NOT increase the canonical 5-team count; adds a documented variant within Implement.
- **EXTEND** `workflow-system/agent/SKILL.md` §"Quick Start — Workflow Selection" table with ML-task keyword row: `train, evaluate, deploy ML, kaggle, hyperparameter | mlops | data-survey → train-eval → tune → deploy → monitor`. Per C-4, SKILL.md current line count is 460 (per CHANGELOG `[9.3.0]`); single new row keeps comfortable headroom.
- **EXTEND** `meta-framework.md` §4 Alias Mapping Table with the 5 new mlops aliases (`data-survey`, `train-eval`, `tune`, `deploy-ml`, `monitor-ml`).

**Coordination required with external tools:**

- **EvoBench: YES (SOFT).** EvoBench's R13 multiplier landing in v6.2+ converts the protocol into observed q-lift. Without R13, DF ships protocol-only; Si-Chip iteration_delta from on-corpus dogfood (per v10.2.4 cycle precedent) would surface as DEFER until R13 lands.
- **NineS: PARTIAL.** `nines analyze --target-path workflow-system/agent/templates/builtin/mlops.yaml --depth deep --agent-impact` at PV close validates template architecture.
- **Si-Chip: PARTIAL.** Post-template-edit, `post_skill_edit` hook (per `references/env-flags.md` §2.14 `DEVOLAFLOW_SI_CHIP_DEEP=1`) auto-runs `iteration_delta` against the new template + reference doc. Verdict APPLY → ship; DEFER → feedback doc per v9.5.0 precedent.

**New env flags:** **0** per W-20 §3. mlops protocol doesn't gate runtime behaviour; activation is via workflow selection (`workflow_type: mlops`), which is data-channel.

**New Soul rules:** Not required.

**Estimated impact (q-points and pass_rate, where computable):**

- **DF-side alone:** mlops capability tag mean quality 0.198 → ~0.30 expected (closing 50% of gap_to_one within the protocol's 1-cycle window). Corpus weight: 19 / 337 ≈ 5.6%; expected mean-quality delta ~+0.006 q.
- **DF + EvoBench R13 (multiplier 1.20–1.30):** per feedback §4.2 — "EvoBench 加入 R13 后预计给 mlops 拉升 ~0.04-0.06 q" (verbatim). Gain attributable mostly to R-rule landing.
- **Per feedback §4.2 R13 multiplier prediction:** combined DF+EvoBench expected ~+0.04..+0.06 mean quality on the mlops slice; corpus-level ~+0.0023..+0.0034 (5.6% weight).

**Effort estimate:** **M (2 PVs).** PV-A: template + reference doc + SKILL.md row + meta-framework alias updates (~50 LOC reference + 50 LOC template). PV-B: tests + W-18 ghost-audit + retrospective.

**Dependencies:**

- §3.1 H-1 (Production tier) — overlapping capability concentration (mlops 36% of Bottom-50). Shipping H-2 alone produces partial mlops protocol coverage; full coverage waits on H-1 long-horizon scaffold.
- §3.3 H-3 (long_horizon) — checkpoint-resume primitives for mlops jobs depend on long-horizon protocol; if H-3 doesn't ship first, H-2's mlops protocol references the long-horizon doc as a forward declaration.
- **Operator decisions required:** (a) sequence H-2 vs H-3 first; (b) approve `mlops_engineer` role variant (vs separate 6th team); (c) approve template registration in `templates/registry.yaml`.

**Acceptance criteria (testable):**

- `tests/test_mlops_template_registered.py` (NEW) — pin: (1) `templates/builtin/mlops.yaml` parses without error; (2) `templates/registry.yaml` lists the template; (3) `meta-framework.md` Alias Mapping Table entries for `data-survey / train-eval / tune / deploy-ml / monitor-ml` exist; (4) SKILL.md keyword row for "train, evaluate, deploy ML, kaggle" routes to `mlops`.
- W-3 SI-3 ≥ 8.5 (STANDARD MINOR if H-2 ships standalone; STRICT ≥9.0 if part of larger MINOR cycle close).
- W-4 SI-4 EvoBench composite stable; mlops scenario (NEW: `benchmarks/devolaflow_context/scenarios/mlops_protocol_active.yaml`) composite ≥ 90.
- C-4 line budget: `references/mlops-protocol.md` ≤ 1000 lines (Large tier).
- Si-Chip dogfood pass verdict APPLY OR DEFER-with-feedback-doc (per v9.5.0 precedent — if DEFER, the deferred doc cites EvoBench R13 dependency).

**Risks:**

- **R-2A R13 multiplier doesn't land:** likelihood MED, impact HIGH. Without R13, q-lift signal is corpus-noise floor. **Mitigation:** ship protocol independently; track mlops-tag quality_mean per PV; defer to v10.5.0 if EvoBench coordination stalls.
- **R-2B mlops protocol over-specialised:** likelihood LOW, impact MED. Protocol assumes Kaggle-shape ML work; live ML-engineering work might want different cadence. **Mitigation:** treat v10.4.0 mlops protocol as "Kaggle-flavour"; live-mlops as v10.6.0+ extension.
- **R-2C `mlops_engineer` role variant breaks 5-team count invariant:** likelihood LOW, impact LOW. **Mitigation:** document as VARIANT within Implement, not 6th team; team-roles.md §1 "Team Relationship to Layers" diagram unchanged.

**Out-of-scope (within this proposal direction):**

- We do NOT propose actual ML training in DF's runtime — DF orchestrates ML-engineering tasks performed by L3 task agents using their existing tool surface.
- We do NOT propose modifying EvoBench R13 multiplier — that's EvoBench-side.
- We do NOT propose new env flag — W-20 §3 reuse-first applies (no orthogonal activation surface).

### §3.3 — H-3 — `long_horizon` capability protocol (R14 candidate)

**Problem statement (verbatim from feedback §7.1):**
> "**[H-3] long_horizon capability——R14 候选，Bottom-50 出现频率最高 tag (94 %)**
>
> - **数据**：long_horizon q=0.208 / gap=0.792 / n_tasks=48；47/50 Bottom-50 携带此 tag。与 multi_session (R10) 邻近但**时间尺度更长**（多日 vs 多回合）。
> - **方向**：DF v9.x envelope_write 已为 multi_session 保底；multi-day 长尾任务需更专门 long-horizon scaffold——"任务分段 checkpoint" + 与 R10 联动的"长任务摘要 + 续接"协议。"

**DF-side concrete proposal:**

- **NEW** `workflow-system/agent/templates/builtin/long-horizon.yaml` — multi-day workflow template (also serves H-1 §3.1; this is the same template, double-counted because both H-1 and H-3 share it). Reuses `change-driven` envelope lifecycle but extends `apply ↔ verify` loop for multi-day cadence (`max_rounds=10` vs default 5; checkpoint cadence per wave).
- **NEW** `workflow-system/agent/references/long-horizon-protocol.md` (Large tier ≤1000 lines) — same as H-1 §3.1 above; this direction H-3 IS the protocol surface H-1 references.
- **EXTEND** `workflow-system/agent/references/agent-workspace.md` §3 + §4 + §6 with **multi-day cadence formalisation**: (a) `STATUS.yaml.long_horizon_mode` field, (b) explicit handoff envelope cadence ("every wave OR every 4 hours wall-clock"), (c) state-restore protocol citing `R10 multi_session` adjacency (R10 covers multi-round same-session; R14 covers multi-day cross-session; the two compose).
- **EXTEND** `workflow-system/agent/references/execution-protocol.md` §2.4 Checkpoint Trigger Rules with `long_horizon_session_pause` trigger (between wall-clock cadence boundaries), in addition to the 7 existing triggers.
- **EXTEND** `src/devolaflow/agent_workspace/` reporter — `render_change_report` includes a "Long-horizon checkpoints" section listing each per-wave checkpoint with timestamp + state delta.

**Coordination required with external tools:**

- **EvoBench: YES (SOFT).** R14 multiplier (1.20–1.30 per feedback §4.2) is the q-lift gate.
- **NineS: PARTIAL.** Cycle-close `nines self-eval` validates long-horizon protocol's architectural soundness.
- **Si-Chip: PARTIAL.** Post-skill-edit dogfood; APPLY iteration_delta verdict expected since long-horizon protocol is tightly scoped (~800 lines of reference content concentrated in a single doc, not 18 widely-distributed files).

**New env flags:** **0** per W-20 §3. REUSE `DEVOLAFLOW_AGENT_WORKSPACE` (same activation surface).

**New Soul rules:** Not required, but worth flagging for W-21 telegraph: a candidate Soul rule "Long-Horizon Checkpoint Cadence Invariant" (every long-horizon mode wave gate PASS triggers a checkpoint) could be a future S-12 candidate. **Telegraph for v10.6.0 (cycle N+2 after v10.4.0 lands the protocol).** Per W-21, the telegraph requires this proposal §5 to flag the candidate; the §5 §"W-21 Soul-set freeze" subsection does so.

**Estimated impact (q-points and pass_rate, where computable):**

- **DF-side alone:** long_horizon capability tag mean quality 0.208 → ~0.32 expected (closing ~55% of gap_to_one within 1-cycle window; protocol is the most direct intervention since 47/50 Bottom-50 tasks carry this tag). Corpus weight: 48 / 337 ≈ 14.2%; expected mean-quality delta ~+0.016 q.
- **DF + EvoBench R14 (multiplier 1.20–1.30):** combined ~+0.04..+0.06 q on the long_horizon slice; corpus-level ~+0.006..+0.009 q (per feedback §4.2 multiplier band).
- **Per feedback §3.3 logistic prediction:** v11 ≈ 0.621 (+0.032) is achievable IF H-2 + H-3 + H-4 land together with EvoBench R13/R14/R15 coordinated; H-3 alone contributes the largest single delta of the three.

**Effort estimate:** **M (2 PVs).** Heavier than H-2 because the agent-workspace.md + execution-protocol.md extensions are critical-path; the new template overlaps H-1.

**Dependencies:**

- §3.1 H-1 — H-3 IS the long-horizon protocol H-1 references; if H-1 ships, H-3 is subsumed.
- §3.2 H-2 — mlops protocol references H-3's long-horizon scaffold (checkpoint-resume primitive). H-3 should ship FIRST.
- **Operator decisions required:** (a) approve sequence H-3 → H-2 → H-4 (long-horizon foundation first); (b) approve `STATUS.yaml.long_horizon_mode` schema additive field; (c) approve `execution-protocol.md` §2.4 checkpoint trigger row addition.

**Acceptance criteria (testable):**

- `tests/test_long_horizon_protocol.py` (NEW) — same as H-1 §3.1 acceptance.
- W-3 SI-3 ≥ 8.5 (STANDARD if standalone PV); ≥ 9.0 (STRICT if part of MINOR cycle close).
- C-4 line budget: `references/long-horizon-protocol.md` ≤ 1000 lines.
- A-2.1 frozen prefix preserved across 11 baselines.
- W-19 cycle archive: `docs/cycle-archive/v10.4.0/` includes the long-horizon design ADR (NEW `.local/research/v10.4.0_long_horizon_design.md` archived).

**Risks:**

- **R-3A R14 multiplier landing delayed:** likelihood MED, impact MED. **Mitigation:** ship DF-side protocol; track long_horizon-tag quality_mean per cycle.
- **R-3B Schema additive field break:** likelihood LOW, impact CRITICAL. **Mitigation:** R5-strict default-OFF for `STATUS.yaml.long_horizon_mode`; existing tests pass byte-identically.
- **R-3C Reference doc balloons past Large tier:** likelihood MED, impact LOW. **Mitigation:** decompose into `long-horizon-protocol.md` (≤500 lines, core SOP) + `references/long-horizon-checkpoints.md` (≤500 lines, deep-dive on checkpoint mechanism) — splits to two Large-tier files within budget.
- **R-3D L3 Task Agent doesn't honour long_horizon mode:** likelihood MED, impact HIGH. The protocol describes the cadence; L3 must actively trigger checkpoints. **Mitigation:** pin a `pre_handoff` lifecycle hook that asserts checkpoint freshness; PSC005-class violation if envelope older than wave gate (S-9 append-only is preserved — checkpoint is an envelope at `seq+1`).

**Out-of-scope (within this proposal direction):**

- We do NOT propose new env flag — REUSE `DEVOLAFLOW_AGENT_WORKSPACE` per W-20 §3.
- We do NOT propose modifying EvoBench R10 (multi_session) multiplier — that's EvoBench-side.
- We do NOT propose live-mode execution; long-horizon protocol applies inside the in-simulator corpus first.

### §3.4 — H-4 — `agentic_planning` capability protocol (R15 candidate)

**Problem statement (verbatim from feedback §7.1):**
> "**[H-4] agentic_planning capability——R15 候选**
>
> - **数据**：q=0.217 / gap=0.783 / n_tasks=32；56 % Bottom-50 任务含此 tag。
> - **方向**：当前 `plan_and_agent` 是基础 plan-then-execute；agentic_planning 需要 **multi-step strategic planning**——可探索 dedicated `multi_horizon_planner` 角色（与 metacognition SOP 互补）。"

**DF-side concrete proposal:**

- **NEW** `workflow-system/agent/references/agentic-planning-protocol.md` (Large tier ≤1000 lines) — multi-step strategic planning SOP: (1) **horizon decomposition** (multi-stage plans where each stage's output feeds the next stage's planning input — distinct from the current single-pass plan template in `plan-mode-enforcement.md` §3); (2) **plan revision protocol** (mid-execution plan rewrite when reality diverges from forecast — the gap-and-fix loop on the planning axis, not the implementation axis); (3) **uncertainty propagation** (plans cite confidence; downstream stages adjust based on confidence gates).
- **EXTEND** `workflow-system/agent/references/team-roles.md` §3 (Design Team) with **`multi_horizon_planner` role variant** — specialisation of Design team: same input/output contracts plus multi-horizon-specific quality criteria like "every horizon ≤2 has explicit revision criteria", "uncertainty band propagated downstream". Does NOT increase the canonical 5-team count.
- **EXTEND** `workflow-system/agent/references/plan-mode-enforcement.md` §3 with **§3.2 Multi-Horizon Plan Template** — extends the current plan template with an outer "Horizons" section (H1, H2, H3, ...; each horizon owns 1–N stages); horizon-boundary revision criteria; uncertainty propagation rules. Preserves §3 single-horizon template byte-identically as the default; multi-horizon is opt-in.
- **NEW** `workflow-system/agent/templates/builtin/agentic-planning.yaml` — workflow template invoking the multi-horizon planner; stages `horizon-1-plan → horizon-1-execute → horizon-2-plan ↔ horizon-1-revise → horizon-2-execute → ... → final-validate`; gate `convergence` with `max_rounds=3` per horizon boundary.

**Coordination required with external tools:**

- **EvoBench: YES (SOFT).** R15 multiplier (1.18–1.25 per feedback §4.2) gates q-lift.
- **NineS: PARTIAL.** Validates protocol architectural soundness.
- **Si-Chip: PARTIAL.** Post-skill-edit dogfood on the protocol-touching files; APPLY verdict expected if the 3 new docs (reference + SKILL.md row addition + plan-mode extension) are tightly scoped.

**New env flags:** **0** per W-20 §3. Activation via `workflow_type: agentic-planning` (data channel).

**New Soul rules:** Not required.

**Estimated impact (q-points and pass_rate, where computable):**

- **DF-side alone:** agentic_planning capability tag mean quality 0.217 → ~0.31 expected (closing ~50% of gap_to_one). Corpus weight: 32 / 337 ≈ 9.5%; expected mean-quality delta ~+0.009 q.
- **DF + EvoBench R15 (multiplier 1.18–1.25):** combined ~+0.04 q on the agentic_planning slice; corpus-level ~+0.004 q.
- **Per feedback §4.2 R15 multiplier prediction:** smaller multiplier band (1.18–1.25) than R13/R14 (1.20–1.30) reflects expected smaller marginal impact since `agentic_planning` is closer to existing DF coverage (`plan_and_agent`).

**Effort estimate:** **M (1–2 PVs).** Lighter than H-2 / H-3 because DF already has plan-mode infrastructure; H-4 is mostly extension.

**Dependencies:**

- §3.1 H-1 — agentic_planning often co-occurs with long_horizon (56% of Bottom-50 carries `agentic_planning`; 94% carries `long_horizon` — overlap is large).
- **Operator decisions required:** (a) approve `multi_horizon_planner` role variant (vs separate 6th team); (b) approve plan-mode-enforcement.md §3.2 multi-horizon template extension; (c) sequence H-4 vs H-2 / H-3.

**Acceptance criteria (testable):**

- `tests/test_agentic_planning_protocol.py` (NEW) — pin: (1) `agentic-planning.yaml` template parses; (2) `templates/registry.yaml` lists it; (3) `plan-mode-enforcement.md` §3.2 multi-horizon template structure exists; (4) `team-roles.md` §3 `multi_horizon_planner` variant section exists.
- W-3 SI-3 ≥ 8.5 STANDARD; ≥ 9.0 STRICT.
- W-4 SI-4 EvoBench composite stable; new scenario `agentic_planning_protocol_active.yaml` composite ≥ 90.
- C-4 line budget: `references/agentic-planning-protocol.md` ≤ 1000 lines.

**Risks:**

- **R-4A `plan_and_agent` cannibalisation:** likelihood LOW, impact MED. Multi-horizon protocol overlaps existing single-pass plan template; operators might confuse the two. **Mitigation:** explicit "When to use" decision tree at top of new reference doc; SKILL.md routing keyword "multi-step strategic planning" vs "build a plan".
- **R-4B R15 multiplier band tighter than R13/R14:** likelihood HIGH (per feedback explicit estimate), impact LOW. The smaller band is expected; doesn't invalidate the direction but means impact is at the lower end.
- **R-4C `multi_horizon_planner` role variant drift:** likelihood LOW, impact LOW. **Mitigation:** document as Design-team variant; team-roles.md §1 "Team Relationship to Layers" diagram unchanged.

**Out-of-scope (within this proposal direction):**

- We do NOT propose modifying EvoBench R15 multiplier — that's EvoBench-side.
- We do NOT propose deprecating `plan_and_agent` — multi-horizon is additive.
- We do NOT propose new Soul rule.

### §3.5 — H-5 — R9 (convergence) and R12 (multi_repo) second-iteration

**Problem statement (verbatim from feedback §7.1):**
> "**[H-5] R9 (convergence) 与 R12 (multi_repo) 二轮强化**
>
> - **数据**：R9 since v7.2.2 / q=0.389 / gap_to_one=**0.611**；R12 since v7.2.6 / q=0.382 / gap_to_one=**0.618**。R-rule active 但 quality 仍卡 ~0.38——multiplier 1.12 / 1.15 不足。
> - **方向**：联合 EvoBench 评估 R9/R12 multiplier 是否提至 1.20+；同时 DF 端在 v10.x 评估这两类 capability 协议是否已穷尽。"

**DF-side concrete proposal:**

This direction has TWO axes — DF-side protocol exhaustion check (this proposal can plan) + EvoBench-side multiplier discussion (out of DF scope). Below is the DF-side action only.

- **REVISE** `src/devolaflow/gate/reinforcement.py` (gate module per CP-4 / W-11 — full gate test suite required) — review whether the 5-rule cap per round is the right shape for convergence-heavy stages; current cap was set in v8.0.0; revisit empirically against `R9 convergence q=0.389 gap_to_one=0.611` to determine if relaxing the cap to 8 OR adding a "convergence-heavy" profile changes the convergence trajectory.
- **REVISE** `workflow-system/agent/references/decomposition-gate.md` §6 Convergence Loop with **§6.6 Convergence-Heavy Profile** — a new gate profile variant for tasks heavy on convergence (e.g. `feedback_loop_convergence_under_noise` from feedback §2.3 Bottom-50 representative tasks) where `max_rounds=8` (vs default 5) and `min_rounds=3`.
- **REVISE** `workflow-system/agent/references/agent-workspace.md` §"multi-repo dispatch" with **§7.5 Multi-Repo Coordination Protocol** — formalise cross-repo protocol: (1) per-repo manifest validation at L0 dispatch time, (2) cross-repo dependency tracking via the `repos` canonical_order position 13 block, (3) per-repo handoff envelope segregation (separate `handoff/<from>__<to>__<change-id>__<repo-slug>__<seq>.yaml` naming convention or single envelope with `repo_segment` discriminator).
- **REVISE** `schemas/lean-dispatch.yaml` `repos` block — NEST per A-2.3 a `repos[*].coordination_mode: parallel|sequential|fanout` sub-field (preserves frozen prefix, no new top-level position). The `repos` block already lives at canonical_order position 13 (added v7.2.6 P-06); the new sub-field rides the existing position.

**Coordination required with external tools:**

- **EvoBench: YES (HARD).** R9/R12 multiplier discussion (1.12 → 1.20+ for R9; 1.15 → 1.20+ for R12) is purely EvoBench-side. DF can ship protocol exhaustion check; the multiplier landing is external. **Coordinate with EvoBench team FIRST before DF-side action — if multipliers stay at 1.12 / 1.15, DF protocol exhaustion check might still surface fixes worth shipping but the q-lift signal is bounded.**
- **NineS: PARTIAL.** Pre-cycle deep-analyze on `src/devolaflow/gate/reinforcement.py` validates protocol exhaustion claim; if NineS surfaces unaddressed complexity hotspots, those become the cycle work.
- **Si-Chip: NO.** This direction touches gate module + agent-workspace, not skill corpus.

**New env flags:** Possibly **1 NEW** `DEVOLAFLOW_CONVERGENCE_HEAVY=1` — opt-in gate profile activation. Per W-20 §3 orthogonality test, the convergence-heavy profile activation is **NOT covered** by any existing flag (the 16 active flags in `references/env-flags.md` §2 are all subsystem-specific or per-task). However, `DEVOLAFLOW_CONVERGENCE_HEAVY` could be argued as a profile-level activation and integrated into existing gate-profile mechanism (per `references/env-flags.md` §2.6–§2.10 the 5 gate-primitive flags pattern). **Recommend deeper W-20 §3 analysis BEFORE landing — this proposal flags it as "needs orthogonality argument inline in PR body if pursued".**

**New Soul rules:** Not required.

**Estimated impact (q-points and pass_rate, where computable):**

- **DF-side alone (without multiplier change):** marginal — DF protocol exhaustion check might lift R9/R12 q from 0.389/0.382 toward 0.42 (5% improvement) if hidden DF-side bottlenecks exist; otherwise zero impact. Gap_to_one 0.611 / 0.618 remains dominant after DF action.
- **DF + EvoBench multiplier change (1.12 → 1.20):** R9 quality lifts from 0.389 toward 0.46 (per the same factor-multiplier ratio R8 1.18 already achieves — q=0.50). Corpus-level for R9 ~+0.013 q, R12 ~+0.012 q.
- **DF-bound; impact gated by EvoBench R-rule landing.** State explicitly: H-5's primary q-lift lever is multiplier increase, not DF protocol; DF action alone yields 5% improvement (0.02 q on the R9/R12 slices, 0.005 corpus-level).

**Effort estimate:** **M (2–3 PVs).** Gate module change requires CP-4 / W-11 full gate test suite; multi-repo protocol formalisation is another PV; coordination overhead with EvoBench is the dominant cost.

**Dependencies:**

- **EvoBench team coordination MANDATORY before cycle begins.** Without confirmed multiplier change discussion, the DF-side cycle ships protocol exhaustion check only — high effort for low expected q-lift.
- §3.1 H-1, §3.2 H-2, §3.3 H-3 — H-5 is independent; can ship as standalone MINOR or alongside H-1..H-4 cycle.
- **Operator decisions required:** (a) approve EvoBench coordination start? (b) accept DF-side ships protocol exhaustion check ALONE if multiplier change deferred? (c) approve gate module CP-4 trigger (full gate test suite required); (d) approve possible new env flag (W-20 §3 orthogonality argument required).

**Acceptance criteria (testable):**

- `tests/test_gate.py -v` per CP-4 — full gate test suite green.
- `tests/test_convergence_heavy_profile.py` (NEW) — pin: (1) convergence-heavy profile registered; (2) `max_rounds=8` and `min_rounds=3` for the profile; (3) profile activation via `DEVOLAFLOW_CONVERGENCE_HEAVY=1` (R5 strict default-OFF) — IF env flag adopted.
- W-4 SI-4 EvoBench composite stable; convergence and multi_repo scenarios composite stable.
- A-2.3 NEST validation: `repos[*].coordination_mode` sub-field is byte-stable when absent (R5 strict).

**Risks:**

- **R-5A EvoBench multiplier change deferred:** likelihood MED, impact HIGH. Without multiplier change, DF-side cycle is high-effort low-q-lift. **Mitigation:** explicit operator-decision gate before cycle begins; if multiplier change uncertain, defer the entire H-5 direction.
- **R-5B Gate module CC inflation:** likelihood LOW, impact MED. Adding convergence-heavy profile inflates `gate/reinforcement.py` complexity. **Mitigation:** CP-4 full gate test suite + NineS pre/post complexity check.
- **R-5C `repos` block schema change breaks A-2.1 frozen prefix:** likelihood LOW (NEST per A-2.3 is canonical), impact CRITICAL. **Mitigation:** A-2 multi-baseline byte test green at every commit; the `repos` block at position 13 is APPEND-only-tail (positions 13+ per A-2.2) — sub-field NEST per A-2.3 doesn't move position 13.
- **R-5D New env flag W-20 violation:** likelihood MED, impact MED. **Mitigation:** W-20 §3 orthogonality argument inline in PR body OR use existing gate-profile activation pattern; reject the flag if argument fails.

**Out-of-scope (within this proposal direction):**

- We do NOT propose modifying EvoBench R9 or R12 multiplier — that's EvoBench-side.
- We do NOT propose deprecating R8/R10/R11 — they are working as expected (q=0.50/0.51/0.53 with adequate gap_to_one).
- We do NOT propose new Soul rule.

### §3.6 — M-1 — VeryComplex tier pass-rate linear growth

**Problem statement (verbatim from feedback §7.2):**
> "**[M-1] VeryComplex tier pass_rate 仍线性爬升——v10..v12 唯一 pass-rate 信号源**
>
> - **数据**：v7 (0.019) → v8 (0.054) → v9 (0.073) → v10 (**0.087**)，每代 +0.014-0.035 稳定增长。如 v11 不再涨（pr 卡 ~0.10），就该认真考虑 EvoBench corpus ceil。"

**DF-side concrete proposal:**

- **No dedicated DF action.** M-1 is a **monitoring direction**, not an actionable lift. VeryComplex pass-rate growth is a **secondary effect of H-2 / H-3 / H-4** — every percentage point of capability-tag improvement (mlops / long_horizon / agentic_planning) translates into a fraction of a pass on VeryComplex tasks because the capability concentration overlaps.
- **MONITOR** at every PV close: report VeryComplex `pass_rate` delta vs prior PV. If the v9→v10 +0.014 trajectory continues to v11 (i.e. v11 → ~0.10), no action needed. If trajectory flattens (v11 stays at ~0.087), escalate to operator + EvoBench team — corpus ceil hypothesis becomes load-bearing.

**Coordination required with external tools:**

- **EvoBench: ONLY IF ESCALATED.** Corpus ceil hypothesis = EvoBench-side investigation.
- **NineS: NO.**
- **Si-Chip: NO.**

**New env flags:** **0**.

**New Soul rules:** Not required.

**Estimated impact:**

- **DF-side alone:** zero direct impact; piggybacks on H-2/H-3/H-4 q-lift.
- **Combined with H-2/H-3/H-4:** VeryComplex `pass_rate` 0.087 → ~0.10 expected (continues linear trajectory).

**Effort estimate:** **S (0 dedicated PVs; report-only at cycle close).**

**Dependencies:**

- §3.2 H-2, §3.3 H-3, §3.4 H-4.

**Acceptance criteria (testable):**

- W-4 SI-4 cycle-close report includes VeryComplex `pass_rate` delta.
- If trajectory flattens, retrospective §3 deferral entry escalates to EvoBench coordination.

**Risks:**

- **R-6 Trajectory flattens despite H-2/H-3/H-4:** likelihood MED, impact LOW. **Mitigation:** retrospective deferral + escalation to operator/EvoBench.

**Out-of-scope:**

- No DF-side action proposed beyond monitoring.

### §3.7 — M-2 — `multi_modal` capability gap (R16 candidate)

**Problem statement (verbatim from feedback §7.2):**
> "**[M-2] multi_modal capability gap (rank 4)**
>
> - **数据**：multi_modal 10 task / q=0.357 / gap=0.643。等 R13 (mlops) 落地后，multi_modal 可作为 R16 候选；DF 端不需现在动作。"

**DF-side concrete proposal:**

- **DEFER until R13 lands and v10.4.0 ships.** M-2 explicitly acknowledges DF-side action is not needed now ("DF 端不需现在动作").
- **TELEGRAPH for v10.6.0 cycle plan SI-1 entry** — once R13/R14/R15 land in EvoBench v6.2+ and DF v10.4.0 ships H-2/H-3/H-4, M-2 becomes the next protocol-coverage candidate: multi-modal capability tag warrants a `multimodal_protocol` reference doc (image / audio / video task awareness; vision-language model orchestration). Effort estimate at telegraph: M (2 PVs).

**Coordination required with external tools:**

- **EvoBench: YES (post-v10.4.0).** R16 multiplier landing depends on R13/R14/R15 stability first.
- **NineS / Si-Chip: PARTIAL** at the time the direction becomes live.

**New env flags:** **0** at telegraph stage.

**New Soul rules:** Not required.

**Estimated impact:**

- **At telegraph:** zero (deferred). When direction becomes live (post-v10.4.0): expected ~+0.04 mean-quality on multi_modal slice (small sample n=10 = 3.0% corpus; corpus-level ~+0.001 q).

**Effort estimate:** **0 PVs now (deferred); M (2 PVs) when activated post-v10.4.0.**

**Dependencies:**

- §3.2 H-2 R13 multiplier landing.
- v10.4.0 cycle close as a precondition.
- **Operator decisions required:** none NOW; defer to v10.6.0 cycle plan.

**Acceptance criteria (testable):**

- v10.6.0 cycle plan §"Telegraph carry-forward" section cites M-2 carry-forward.
- v10.4.0 retrospective §3 includes M-2 explicit deferral with rationale.

**Risks:** None at telegraph stage.

**Out-of-scope:**

- We do NOT propose any DF-side action in v10.4.0 cycle scope — M-2 is post-v10.4.0 deferral.

### §3.8 — M-3 — `devolaflow_latest` alias consistency

**Problem statement (verbatim from feedback §7.2):**
> "**[M-3] devolaflow_latest 别名一致性**
>
> - **数据**：baseline q=0.5643 vs growth q=0.5898，Δ=0.0255 比 v9.1.0 同类差异（0.0028）大 9 倍。**DF 无 action**；建议 EvoBench v6.1.4 alias seed audit。"

**DF-side concrete proposal:**

- **NO DF action.** M-3 explicitly states "DF 无 action" verbatim.
- **MONITOR.** Operator confirms with EvoBench team that the v6.1.4 alias seed audit is queued; if not, operator escalates EvoBench-side.

**Coordination required:** EvoBench-side only (v6.1.4 alias seed audit).

**New env flags / Soul rules:** None.

**Estimated impact:** Zero on DF.

**Effort estimate:** **0 PVs.**

**Dependencies:** None on DF side.

**Acceptance criteria:** None on DF side.

**Risks:** None on DF.

**Out-of-scope:**

- We explicitly DO NOT propose any DF-side intervention — M-3 is EvoBench responsibility per feedback.

### §3.9 — L-1 — Saturation tail strategic reserve

**Problem statement (verbatim from feedback §7.3):**
> "**[L-1] Saturation tail 战略储备**
>
> - **数据**：v9→v10 +0.0077 q，logistic L=0.6698，预测 v11 ~0.621 / v12 ~0.633。现行 corpus 上 factor lift 边际收益将衰减到 +0.005..+0.013/代。
> - **方向**：DF 主动评估"能否在 v10.x 周期引入 R13/R14/R15 之一以触发 step-jump"——若能落地 1 个新 capability_modulator，v11 可见 ~0.02-0.04 非饱和 q 提升（vs 现行 +0.008/代）。"

**DF-side concrete proposal:**

L-1 is **not a separate direction** — it is the **strategic framing** for the entire H-2/H-3/H-4 sequence. The recommended posture below crystallises it:

- **APPROVE H-2 + H-3 + H-4 as the v10.4.0 MINOR cycle** to land at least 1 new capability_modulator (R13 OR R14 OR R15) in coordination with EvoBench. The expected v11 step-jump (~0.02–0.04 non-saturated q-lift) MORE THAN OFFSETS the +0.005..+0.013/代 saturation-decay default trajectory. Per feedback §7.3 verbatim — "若能落地 1 个新 capability_modulator，v11 可见 ~0.02-0.04 非饱和 q 提升".
- **REJECT** the alternative posture of incremental factor lifts (+0.005..+0.013 per cycle) — feedback §3.3 explicit conclusion: *"现行 337 任务矩阵下，DF 单纯 factor lift 顶多再涨 0.06-0.08 q（约 0.65 上界）"* — diminishing returns with ceiling-bound payoff.

**Coordination required with external tools:**

- **EvoBench: YES (HARD)** for R13/R14/R15 multiplier landing.
- **NineS: PARTIAL** for cycle-close architectural validation.
- **Si-Chip: PARTIAL** for skill-corpus shrink dogfood (continues v10.2.0 cycle's APPLY trajectory).

**New env flags / Soul rules:** Per H-2/H-3/H-4 directions individually.

**Estimated impact:** Per H-2 + H-3 + H-4 combined: ~+0.04..+0.06 mean quality on covered slices; corpus-level ~+0.014..+0.020 (vs default trajectory +0.008/cycle = step-change).

**Effort estimate:** Per H-2 (M) + H-3 (M) + H-4 (M) combined: 1 MINOR cycle (~6 PVs).

**Dependencies:**

- All H-2/H-3/H-4 directions.
- EvoBench R13/R14/R15 multiplier coordination (operator-decision gate).

**Acceptance criteria:**

- v10.4.0 cycle-close evaluation reports capability_modulator landing status.
- W-3 SI-3 ≥ 9.0 STRICT MINOR-cycle-close.

**Risks:** Per H-2/H-3/H-4 individually.

**Out-of-scope:**

- We do NOT propose 5+ R-rules in a single cycle — the W-8 SI-9 reinforcement cap (5 rules per round) is dispatcher-internal, not corpus-modulator landing; but corpus-modulator landing is bounded by EvoBench engineering bandwidth, not DF policy.

---

## §4 — Recommended Phased Rollout (proposal — not yet a cycle plan)

This section sketches how the 9 directions could be sequenced across 1–3 future cycles. **No SI-1 gate commitment is made here**; if approved, this artifact feeds a future SI-1 gate.

### §4.1 — v10.3.x PATCH series (low-risk, high-leverage)

**No direction fits a single PATCH bump cleanly.** The 5 high-priority directions H-1..H-5 all require new template files OR new reference docs OR gate-module changes — all of which trigger MINOR-scope governance (W-12 SKILL adapter build, W-11 gate module change, W-15 context profile validation). PATCH PVs are reserved for surgical fixes, not capability-protocol additions.

**Recommendation: skip v10.3.x PATCH series.** Either tackle the next direction inside a v10.4.0 MINOR or hold cycle until operator approves.

### §4.2 — v10.4.0 MINOR cycle (the 3-capability cycle)

**Recommended sequence (6 PVs):**

| PV | Direction | Headline | Acceptance |
|---|---|---|---|
| PV-01 | W-16 wholesale baseline regen + cycle-start | `v10.4.0_baseline.json` byte-identical to `v10.3.0_baseline.json`; 11th multi-baseline byte test pin | A-2.1 frozen prefix preserved across 11 baselines |
| PV-02 | §3.3 H-3 long_horizon protocol | NEW `references/long-horizon-protocol.md` + EXTEND `agent-workspace.md` + NEW `templates/builtin/long-horizon.yaml` | W-3 ≥ 8.5 STANDARD; tests green |
| PV-03 | §3.2 H-2 mlops protocol | NEW `references/mlops-protocol.md` + NEW `templates/builtin/mlops.yaml` + EXTEND `team-roles.md` | W-3 ≥ 8.5 STANDARD; tests green |
| PV-04 | §3.4 H-4 agentic_planning protocol | NEW `references/agentic-planning-protocol.md` + EXTEND `plan-mode-enforcement.md` §3.2 + EXTEND `team-roles.md` | W-3 ≥ 8.5 STANDARD; tests green |
| PV-05 | §3.5 H-5 R9/R12 second-iteration (DF-side protocol exhaustion check ONLY; EvoBench multiplier discussion in parallel) | REVISE `gate/reinforcement.py` + REVISE `decomposition-gate.md` §6 + EXTEND `agent-workspace.md` §"multi-repo" | CP-4 full gate test suite green; W-3 ≥ 8.5 STANDARD |
| PV-06 | Cycle close MINOR | Canonical 7 sync 10.3.0 → 10.4.0; CHANGELOG MINOR entry; W-3 SI-3 evaluation; W-7 retrospective; W-19 archive; PR posture | W-3 ≥ 9.0 STRICT MINOR-cycle-close |

**W-1 / W-2 / W-3 / W-7 / W-9 / W-19 hygiene applied** — every PV runs `nines analyze` + `nines self-eval`; cycle close runs full SI-3 evaluation; W-19 cycle archive at `docs/cycle-archive/v10.4.0/`.

**W-17 test cap forecast:** +30 NEW test functions per PV cap; cycle-cumulative 6 × 30 = +180 forecast; well within +150 cap with buffer for parametrize expansions. **W-17 mid-cycle audit at PV-04 mandatory** (per W-17 rule for cycle PV halfway).

**Estimated cumulative q-impact (cite logistic prediction from feedback §3.3):**

> "v11 ≈ 0.621 (Δ +0.032)" — verbatim feedback §3.3.

Adjusted for DF-side R13/R14/R15 protocol effects:

| Scenario | Estimated v11 q | Trajectory |
|---|---:|---|
| All 3 R-rules land in EvoBench v6.2 + DF protocols ship | **~0.621** (matches logistic prediction) | step-jump |
| 2 of 3 R-rules land + DF protocols ship | ~0.605 | partial step-jump |
| 1 of 3 R-rules lands + DF protocols ship | ~0.598 | small lift |
| 0 R-rules land; DF protocols ship infrastructure-only | ~0.595..0.598 | saturation continues; per-protocol q-lift deferred to next cycle |

The **upside** (~0.621 v11) materialises ONLY with EvoBench R-rule coordination. **Without R-rules, the cycle still ships valuable infrastructure** (templates, reference docs, role variants) but the q-lift signal is bounded.

### §4.3 — v10.5.0+ (the harder ceilings)

| Direction | Why post-v10.4.0 | Recommended cycle |
|---|---|---|
| §3.1 H-1 Production tier 0% pass rate | Multi-cycle DF work + EvoBench partial-credit scoring coordination required; absorbs H-3 long-horizon scaffold from v10.4.0 | v10.5.0 (if EvoBench scoring methodology lands) OR v11.0.0 MAJOR cycle (if methodology lands later) |
| §3.5 H-5 R9/R12 — full version with multiplier discussion | If v10.4.0 PV-05 ships only DF-side protocol exhaustion check, the full multiplier-coordinated H-5 lands here | v10.5.0 (alongside EvoBench v6.2+ multiplier release) |

### §4.4 — Carry-forward / DEFER

| Direction | Rationale (per v9.5.0 deferred §1.4 HIGH-risk pattern) |
|---|---|
| §3.7 M-2 multi_modal | Wait for R13 (mlops) landing in EvoBench v6.2+; multi_modal is R16 candidate — telegraphed for v10.6.0 |
| §3.8 M-3 alias consistency | EvoBench v6.1.4 audit responsibility — DF has no action |
| §3.9 L-1 saturation tail | Subsumed by H-2/H-3/H-4 sequencing — strategic framing, not separate direction |
| W-21 S-12 candidate "Long-Horizon Checkpoint Cadence Invariant" | Telegraphed for v10.6.0 (cycle N+2 from v10.4.0 if H-3 lands) per W-21 2-cycle deliberation rule |

---

## §5 — Cross-cutting Concerns

### W-20 env-flag reuse-first

| Direction | New flag proposed? | Reuse decision | Justification |
|---|---|---|---|
| §3.1 H-1 | NO | REUSE `DEVOLAFLOW_AGENT_WORKSPACE` | Same activation surface (workspace folder management extends naturally to long-horizon mode) |
| §3.2 H-2 | NO | None — data-channel activation via `workflow_type: mlops` | Workflow-type selection, not runtime opt-in |
| §3.3 H-3 | NO | REUSE `DEVOLAFLOW_AGENT_WORKSPACE` | Same as H-1 |
| §3.4 H-4 | NO | None — data-channel activation via `workflow_type: agentic-planning` | Same as H-2 |
| §3.5 H-5 | **POSSIBLY** `DEVOLAFLOW_CONVERGENCE_HEAVY` | W-20 §3 orthogonality argument REQUIRED inline if pursued | Profile-level activation; closer to gate-primitive flag pattern (§2.6–§2.10) |
| §3.6 M-1 | NO | None | Monitoring only |
| §3.7 M-2 | NO | None at telegraph | Deferred |
| §3.8 M-3 | NO | None | EvoBench-side |
| §3.9 L-1 | NO | None | Strategic framing |

**Net new flags across the proposal: 0 (if H-5 pursues no new flag) or 1 (if `DEVOLAFLOW_CONVERGENCE_HEAVY` lands with W-20 §3 orthogonality argument).**

### W-21 Soul-set freeze (cap = 12; current = 10)

| Direction | New Soul rule proposed? | Telegraph cycle |
|---|---|---|
| §3.1 H-1 | NO | n/a |
| §3.2 H-2 | NO | n/a |
| §3.3 H-3 | TELEGRAPH only — candidate "Long-Horizon Checkpoint Cadence Invariant" (S-12 candidate) | v10.6.0 (cycle N+2 from v10.4.0) per W-21 2-cycle rule |
| §3.4 H-4 | NO | n/a |
| §3.5 H-5 | NO | n/a |

**Existing v10.0.0-telegraphed S-11 "Parallel Wave Dispatch Invariant"** — re-telegraphed for v10.4.0 evaluation per the v10.3.0 retrospective §5. This proposal does NOT propose advancing S-11; it remains operator's call. If H-2/H-3/H-4 land alongside an S-11 evaluation, the SI-1 architecture-rationality SI-3 §3.2 score (≥9.5/10 floor per W-21) becomes the gating constraint for the cycle.

**Net Soul-rule proposals: 0 (telegraph-only — actual landing is v10.6.0+ subject to gap-analysis + SI-3 §3.2 ≥9.5/10).**

### A-2 cache-prefix invariant

| Direction | Schema impact | Decision |
|---|---|---|
| §3.1 H-1 | `STATUS.yaml.long_horizon_mode` schema additive (under `schemas/agent-workspace/change-status.yaml`); no top-level `canonical_order` change | NEST per A-2.3 (additive optional field; default False; byte-stable) |
| §3.2 H-2 | None — workflow template registration only | n/a |
| §3.3 H-3 | Same as H-1 | NEST per A-2.3 |
| §3.4 H-4 | None — reference doc + role variant only | n/a |
| §3.5 H-5 | `repos[*].coordination_mode` sub-field | NEST per A-2.3 (rides existing `repos` block at canonical_order position 13; preserves 17-key canonical_order) |
| §3.6–§3.9 | None | n/a |

**Net canonical_order edits: 0 across the proposal.** All schema impact is sub-field NEST per A-2.3 nest-vs-append decision rule (preserves frozen prefix positions 1–12 and 17-key canonical_order length).

### C-4 line budgets

Three NEW reference docs proposed:

| Path | Tier | Ceiling | Risk |
|---|---|---:|---|
| `references/long-horizon-protocol.md` | Large | ≤1000 | **MED** — per R-3C, may balloon; mitigation = split into two Large-tier files |
| `references/mlops-protocol.md` | Large | ≤1000 | LOW |
| `references/agentic-planning-protocol.md` | Large | ≤1000 | LOW |

Three existing files proposed for EXTEND (delta < 200 lines each):

| Path | Current ceiling | Current line count (per CHANGELOG) | Risk |
|---|---|---:|---|
| `workflow-system/agent/SKILL.md` | <500 | 460 | LOW (+1 row addition) |
| `references/agent-workspace.md` | ≤1000 | (per file ~750) | LOW (+50 lines) |
| `references/team-roles.md` | ≤1000 | (per file ~580) | LOW (+50 lines) |
| `references/plan-mode-enforcement.md` | ≤1000 | (per file ~650) | LOW (+150 lines) |
| `references/decomposition-gate.md` | ≤1000 | (per file ~600) | LOW (+50 lines) |
| `references/execution-protocol.md` | ≤1000 | (per file ~820) | MED (+50 lines; close to ceiling) |
| `references/meta-framework.md` | ≤1000 | (per file ~600) | LOW (+10 lines for Alias Mapping additions) |

### S-7 external-resource URLs

All EvoBench / NineS / Si-Chip references throughout this proposal cite canonical GitHub URLs:

- DevolaFlow / EvoBench: `https://github.com/YoRHa-Agents/DevolaFlow`
- NineS: `https://github.com/YoRHa-Agents/NineS`
- Si-Chip: `https://github.com/YoRHa-Agents/Si-Chip`

No absolute filesystem paths used (S-2 compliance). All paths in this proposal are repo-relative.

### W-19 cycle archive

If approved, this proposal artifact (`.local/research/eb613_v10_optimization_proposal.md`) becomes a cycle-archive candidate at v10.4.0 close — either as a standalone artifact in `docs/cycle-archive/v10.4.0/` or rolled into `docs/cycle-archive/v10.4.0/gap_analysis.md`. **Operator decides** at v10.4.0 PV-06 (W-19 step) whether to include it.

---

## §6 — Open Questions for the Operator

The operator MUST answer these BEFORE SI-1 begins. If unanswered, defaults shown apply.

| # | Question | Why it matters | Default if unanswered |
|---|---|---|---|
| 1 | Does the operator want EvoBench R13/R14/R15 coordination, or just DF-side protocol? | Some directions are partly EvoBench-bound; without R-rule landing, DF-side q-lift alone caps ~+0.02–0.04 per direction (per feedback §4.2 multiplier band) | Assume DF-side-only; coordinate with EvoBench team in parallel; track R-rule landing per cycle |
| 2 | Should H-2 / H-3 / H-4 ship in parallel (single MINOR cycle) or sequentially (3 separate MINOR cycles)? | Single cycle = ~6 PVs MINOR (faster lift if EvoBench coordinates simultaneously); sequential = 3 × 3 PVs MINOR (lower per-cycle risk; spreads validation across 3 cycles) | Single cycle (v10.4.0 MINOR) — matches v10.3.0 cycle-close shape (5 PATCH + 1 MINOR cycle close) |
| 3 | What is the acceptance threshold for "successful" mlops / long_horizon / agentic_planning protocol? | Without explicit threshold, every cycle might claim success without measurable lift. Si-Chip iteration_delta + EvoBench composite are the candidates | Si-Chip iteration_delta ≥ +0.10 (matches v9.5.0 dogfood threshold); EvoBench composite ≥ 90 on each new scenario |
| 4 | Should H-1 (Production partial-credit scoring) be DF or EvoBench responsibility? | Boundary clarity matters — DF can lift Production quality_mean from 0.357 to ~0.45 via long-horizon scaffold, but the binary 0.5 pass_rate threshold is corpus-side | EvoBench-side (corpus / scoring methodology change); DF ships long-horizon scaffold to lift quality_mean only |
| 5 | Should we reuse `DEVOLAFLOW_AGENT_WORKSPACE` for long_horizon, or create new flag? | Per W-20 §3 orthogonality test, reuse is correct. Operator confirmation guards against unintended scope creep | REUSE `DEVOLAFLOW_AGENT_WORKSPACE`; the H-5 `DEVOLAFLOW_CONVERGENCE_HEAVY` is the only flag candidate this proposal flags as needing fresh W-20 §3 analysis |
| 6 | Team role expansion strategy: extend existing 5 OR add 6th `mlops_engineer` / 7th `multi_horizon_planner`? | Adds canonical-team-count invariant question per `references/team-roles.md` §1; affects A-1 4-layer hierarchy | Document as VARIANTS within Implement (mlops_engineer) and Design (multi_horizon_planner); preserve canonical 5-team count |
| 7 | Should H-3 long-horizon AND H-1 Production tier ship together or split? | H-1 absorbs H-3 protocol; if both in one cycle, scope is L (full MINOR cycle); if split, H-3 ships in v10.4.0 and H-1 in v10.5.0+ | Split — H-3 ships in v10.4.0; H-1 ships in v10.5.0+ once EvoBench partial-credit scoring lands |
| 8 | PR cadence: per-PV PRs or single MINOR cycle PR? | v10.0.0 cycle ran on a single feature branch with all 6 PV commits; v10.2.0 cycle did the same. v10.4.0 could continue this cadence or change | Continue v10.0.0 / v10.2.0 cadence — single `feat/v10.4.0-cycle` branch; cycle-close PR posture flip at PV-06 |
| 9 | Should we open a NineS-driven validation pre-cycle? | Per W-2 SI-2, deep-analyze on `agent_workspace/`, `gate/`, `lifecycle/` would surface architectural risks BEFORE H-2/H-3/H-4 land | YES — pre-cycle NineS validation is W-2 standard practice for new MINOR cycles |
| 10 | Should the proposal artifact itself become committed to the repo at v10.4.0 cycle archive? | W-19 cycle archive captures `.local/research/<cycle>_*` artifacts; this proposal pre-dates v10.4.0 cycle but motivates it | YES — copy to `docs/cycle-archive/v10.4.0/eb613_v10_optimization_proposal.md` at cycle close |

---

## §7 — Risk Register (proposal-wide)

Aggregate risk register. Per row: ID, risk, likelihood, impact, mitigation, link to direction.

| ID | Risk | Likelihood | Impact | Mitigation | Direction |
|---|---|---|---|---|---|
| R-1 | EvoBench partial-credit scoring delayed (Production tier 0% pass remains) | MED | HIGH | Ship DF-side independently; track quality_mean delta; defer pass_rate impact to v10.5.0+ | §3.1 H-1 |
| R-2 | Schema invariant break on `STATUS.yaml.long_horizon_mode` field addition | LOW | CRITICAL | Additive optional field; default False; byte-stable tests pre/post | §3.1 H-1, §3.3 H-3 |
| R-3 | Reference doc balloons past Large tier (≤1000) | MED | LOW | Decompose into 2 Large-tier files within budget | §3.1 H-1, §3.3 H-3 |
| R-4 | Long-horizon mode bloats every dispatch | LOW | MED | R5-strict default-OFF; no dispatch payload changes when `long_horizon_mode != true` | §3.1 H-1, §3.3 H-3 |
| R-5 | EvoBench R13/R14/R15 multipliers don't land in v6.2+ window | MED | HIGH | Ship DF-side protocol independently; track per-cycle Si-Chip iteration_delta + EvoBench composite | §3.2 H-2, §3.3 H-3, §3.4 H-4 |
| R-6 | mlops protocol over-specialised (Kaggle-flavour vs live-mlops) | LOW | MED | Treat v10.4.0 mlops as "Kaggle-flavour"; live-mlops as v10.6.0+ extension | §3.2 H-2 |
| R-7 | `mlops_engineer` / `multi_horizon_planner` role variants drift from canonical 5-team | LOW | LOW | Document as VARIANTS within Implement / Design; preserve canonical count; team-roles.md §1 diagram unchanged | §3.2 H-2, §3.4 H-4 |
| R-8 | `plan_and_agent` cannibalisation by multi-horizon protocol | LOW | MED | Explicit "When to use" decision tree at top of new ref doc; SKILL.md routing keyword "multi-step strategic planning" vs "build a plan" | §3.4 H-4 |
| R-9 | EvoBench R9/R12 multiplier discussion deferred; H-5 ships protocol-exhaustion-check only | MED | HIGH | Operator-decision gate before H-5 cycle begins; defer if multiplier change uncertain | §3.5 H-5 |
| R-10 | Gate module CC inflation from convergence-heavy profile addition | LOW | MED | CP-4 full gate test suite + NineS pre/post complexity check | §3.5 H-5 |
| R-11 | New env flag `DEVOLAFLOW_CONVERGENCE_HEAVY` violates W-20 §3 orthogonality test | MED | MED | W-20 §3 inline orthogonality argument in PR body OR use existing gate-profile activation pattern; reject the flag if argument fails | §3.5 H-5 |
| R-12 | VeryComplex pass-rate trajectory flattens despite H-2/H-3/H-4 protocols landing | MED | LOW | Retrospective deferral + escalation to operator/EvoBench | §3.6 M-1 |
| R-13 | Cycle scope creep — H-2 + H-3 + H-4 + H-5 + cycle hygiene exceeds 6 PVs | MED | MED | Defer H-5 to v10.5.0 if v10.4.0 capacity blown; W-17 mid-cycle audit at PV-04 | §4.2 |
| R-14 | W-21 S-11 evaluation in v10.4.0 SI-1 collides with new direction proposals | MED | MED | Operator-decision sequencing — S-11 first OR new directions first; SI-3 §3.2 ≥ 9.5/10 floor binds either way | §5 |
| R-15 | Si-Chip iteration_delta verdict DEFER on protocol-touching files (no observable shrink) | LOW | LOW | DEFER feedback doc per v9.5.0 precedent; operator decides whether shrink lands in v10.4.x or v10.6.0 | All H-2/H-3/H-4 |
| R-16 | Operator approves proposal but cycle plan §SI-1 deviates significantly | MED | LOW | This proposal is Phase-0; SI-1 has full discretion; the proposal's open-questions §6 catches every decision the SI-1 must answer | §4 |
| R-17 | NineS deep-analyze in pre-cycle validation surfaces architectural showstopper | LOW | HIGH | Pre-cycle gate per W-2 SI-2; proposal §3 acceptance criteria includes NineS green pre-PV01 dispatch | §4.2 |

---

## §8 — Out-of-Scope (proposal-wide)

What is EXPLICITLY NOT in this proposal:

- **EvoBench-side changes** — R-rule multiplier adjustments (R8 1.18 / R9 1.12 / R10 1.12 / R11 1.18 / R12 1.15), corpus expansion (337 → larger), Production tier partial-credit scoring methodology change, alias seed audit (M-3). Operator coordinates with EvoBench team separately.
- **Si-Chip per-file APPLY edits** — separate v10.4.0+ cadence per v9.5.0 deferred §1.4 HIGH-risk pattern. The v10.2.0 cycle deferred per-file SKILL.md / reference shrinks; this proposal does NOT propose to consume them either. Per-file shrinks remain on v9.5.0 OA-2..OA-4 backlog.
- **S-11 candidate evaluation** beyond what's already telegraphed in v10.0.0 retrospective §3.5 + v10.3.0 retrospective §5. Per W-21 2-cycle deliberation rule, S-11 evaluation belongs to v10.4.0 SI-1, not this proposal.
- **S-12 candidate landing** — this proposal telegraphs "Long-Horizon Checkpoint Cadence Invariant" for v10.6.0 evaluation; it does NOT propose landing it.
- **Any breaking changes to existing public APIs** — full additive design throughout; backward-compat preserved at every direction (per the v10.0.0 + v10.2.0 + v10.3.0 cycle compatibility 10/10 dimension).
- **Live-mode execution** — Production tier graduation to live-LLM is separate from in-simulator partial-credit scoring; per feedback §10 caveats, live-mode lands in a future EvoBench cycle.
- **DF runtime ML training / inference** — DF orchestrates ML-engineering tasks performed by L3 task agents using their existing tool surface; DF is not a training framework.
- **Modifying EvoBench R8/R10/R11 multipliers** — they are working as expected (q=0.50/0.51/0.53 with adequate gap_to_one); no second-iteration proposed.
- **Per-file `iteration_delta` decomposition** for Si-Chip (v10.2.0 cycle deferral §3 carry-forward).
- **PR cadence reform** — v10.4.0 inherits v10.0.0 / v10.2.0 single feature-branch cadence per recommended default in §6 question 8.

---

## §9 — Decision Surface for the Operator

Concise checklist — operator selects ONE primary action plus any deferrals:

- [ ] **APPROVE this proposal as v10.4.0 SI-1 input** — proposal feeds the SI-1 gap analysis; SI-1 produces the cycle plan.
- [ ] **APPROVE §4.1 v10.3.x PATCH (immediate next step)** — proposal recommends SKIP (no direction fits a single PATCH); operator may override.
- [ ] **APPROVE §4.2 v10.4.0 cycle structure (6-PV MINOR cycle)** — operator approves the 6-PV sequence (W-16 wholesale + H-3 + H-2 + H-4 + H-5 + cycle close).
- [ ] **APPROVE §4.3 v10.5.0+ multi-cycle plan** — H-1 + H-5 full version land in v10.5.0+.
- [ ] **DEFER M-2 to v10.6.0** — multi_modal carry-forward.
- [ ] **DEFER M-3 to EvoBench v6.1.4** — alias consistency (no DF action).
- [ ] **REJECT and request revision (with what changes)** — operator specifies revision scope; proposal is re-authored.

**Open questions §6 must be answered for the SI-1 to consume the proposal cleanly.** Defaults shown in §6 apply if operator unavailable.

---

## §10 — References

All paths relative to repo root. External tools by canonical URL.

### Primary feedback (this proposal's source-of-truth)

- `.local/feedbacks/from_evobench/eb613_for_devola_v10.0.0.md` — EvoBench v6.1.3 feedback (2026-05-03) — the source the proposal is responding to.

### Prior EvoBench feedback sequence (evolution context)

- `.local/feedbacks/from_evobench/eb070_for_devola_v2.1.0.md` — earliest in series (2026-04-12)
- ... 16 v3.x and v4.x intermediate feedbacks ...
- `.local/feedbacks/from_evobench/eb220_for_devola_v7.1.1.md` — VeryComplex hard-failure analysis (2026-04-17)
- `.local/feedbacks/from_evobench/eb310_for_devola_v9.1.0.md` — v9.1.0 baseline (2026-04-29)
- `.local/feedbacks/from_evobench/eb410_for_devola_v9.1.0.md` — v4.1.0 corpus depth shift; v9 saturation tail flagged (2026-04-30)
- `.local/feedbacks/from_evobench/evobench_v1.3.0_full_benchmark.md` — earliest comprehensive (2026-04-23)

### DevolaFlow CHANGELOG (recent cycle entries)

- `CHANGELOG.md` — v10.0.0 / v10.1.0 / v10.2.0..v10.2.4 / v10.3.0 entries (most recent ~1300 lines)

### DevolaFlow research artifacts (v10.x cycle)

- `.local/research/v10.0.0_evaluation.md` — W-3 SI-3 MAJOR-cycle-close evaluation (composite 9.20 / 10)
- `.local/research/v10.0.0_retrospective.md` — W-7 SI-8 MAJOR cycle close
- `.local/research/v10.0.0_cycle_plan.md` — cycle plan template (5-MINOR + 1-MAJOR rollup shape)
- `.local/research/v10.3.0_evaluation.md` — W-3 SI-3 MINOR-cycle-close evaluation (composite 9.385 / 10)
- `.local/research/v10.3.0_retrospective.md` — W-7 SI-8 MINOR cycle close (deferral §5 + W-21 telegraph)

### DevolaFlow agent-facing surfaces (impact assessment)

- `workflow-system/agent/SKILL.md` — current top-level skill (line count 460)
- `workflow-system/agent/references/meta-framework.md` — 14-primitive catalog + 22 builtin templates
- `workflow-system/agent/references/team-roles.md` — 5 AgentTeam roles (Research / Design / Implement / Test / Review)
- `workflow-system/agent/references/decomposition-gate.md` — gate machinery + convergence loop (§6)
- `workflow-system/agent/references/execution-protocol.md` — task execution lifecycle + checkpoint mechanism (§2)
- `workflow-system/agent/references/agent-workspace.md` — `.local/.agent/` change folder + handoff envelope substrate
- `workflow-system/agent/references/plan-mode-enforcement.md` — `plan_and_agent` infrastructure + S-10 lifecycle hook
- `workflow-system/agent/references/env-flags.md` — 16 active runtime flags (W-20 reuse-first inventory)
- `workflow-system/agent/templates/builtin/*.yaml` — 22 builtin templates (no mlops / long_horizon / agentic_planning)

### Governance rules

- `.cursor/rules/repo-governance.mdc` — compiled full corpus (W-* / S-* / A-* / C-* / ST-* rules)
- `AGENTS.md` — Markdown corpus mirror
- `.rules/architecture.mdc` — A-1..A-6 architecture rules (canonical source)

### External tools (S-7 compliance)

- DevolaFlow / EvoBench: https://github.com/YoRHa-Agents/DevolaFlow
- NineS: https://github.com/YoRHa-Agents/NineS
- Si-Chip: https://github.com/YoRHa-Agents/Si-Chip

---

*L1 Research Stage Agent — Phase-0 optimization proposal authored 2026-05-04 in response to EvoBench v6.1.3 (eb613) feedback. Operator decides whether to advance to SI-1.*
