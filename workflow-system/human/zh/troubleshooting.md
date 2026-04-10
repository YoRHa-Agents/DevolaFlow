---
title: "故障排查"
description: "工作流执行中的常见问题和解决方案。"
source_files:
  - "SKILL.md"
auto_generated: true
last_synced: "2026-04-10T06:14:27Z"
source_version: "3.0.0"
---

# 故障排查

工作流执行中的常见问题和解决方案。

## 常见问题

### 修改 SKILL.md 后测试失败
运行 `python -m pytest tests/test_version.py -v` 检查版本一致性。使用 `scripts/bump_version.py` 进行统一更新。

### build-skill 报告超出预算
SKILL.md 必须保持在 500 行以内。运行 `build-skill --all` 验证。

### EvoBench 显示回退
运行 `python -m benchmarks.devolaflow_context.runner --scenario all --compare-baseline`，检查哪个场景出现回退。

### 上下文配置未加载
确认 `context_profiles.yaml` 存在于 `workflow-system/agent/context_profiles.yaml`。
