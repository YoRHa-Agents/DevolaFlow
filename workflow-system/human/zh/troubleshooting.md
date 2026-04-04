---
title: "故障排查"
description: "工作流执行中的常见问题和解决方案。"
source_files: ["SKILL.md"]
auto_generated: true
last_synced: "2026-04-04T00:00:00Z"
source_version: "1.0.0"
---

# 故障排查

## 模板验证失败

| 错误 | 含义 | 解决 |
|-----|------|-----|
| 缺少必需字段 | 阶段或元数据字段缺失 | 对照 schema 补全 |
| 阶段引用完整性 | composition 引用了不存在的阶段 ID | 确保所有引用的 ID 都在 stages 列表中 |
| 循环无终止条件 | 循环缺少 `until` 或 `max_iterations` | 两个字段都必须存在 |
| 孤立阶段 | 阶段已定义但未被引用 | 在 composition 中使用或删除 |

## 质量门分数过低

诊断步骤：
1. 查看质量门报告：哪个维度得分最低？
2. 重点关注：`blocker` (每个扣 25 分)、`critical` (每个扣 15 分)

公式：`quality_score = max(0, 100 - blocker*25 - critical*15 - major*5 - minor*1)`

## 收敛循环停滞

连续 2 轮分数未提升时系统会升级给人类处理。提供方向：优先处理哪些发现，或降低质量阈值。

## 上下文溢出

任务代理输出质量下降时，检查上下文注入量是否超过 ~8K token 预算。控制 `owned_files` 不超过 6 个，`read_only` 不超过 15 个。
