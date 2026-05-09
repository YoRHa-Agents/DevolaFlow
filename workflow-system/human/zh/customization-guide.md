---
title: "自定义指南"
description: "创建自定义工作流模板和派生配置。"
source_files:
  - "SKILL.md"
auto_generated: true
last_synced: "2026-05-08T21:49:42Z"
source_version: "11.4.0"
---

# 自定义指南

创建自定义工作流模板和派生配置。

## 创建自定义工作流模板

工作流模板是 `workflow-system/agent/templates/builtin/` 中的 YAML 文件。每个模板遵循 `schemas/workflow-template.schema.yaml` 中定义的架构。

### 模板结构

```yaml
schema_version: "1.0"

metadata:
  name: my-workflow          # 唯一的 kebab-case id
  version: "1.0.0"
  display_name: "我的工作流"
  description: "这个工作流的用途"
  category: build            # discover | shape | build | deliver | composite
  applicable_scenarios:
    - "何时推荐这个工作流"
  tags: [关键词1, 关键词2]

stages:
  - id: stage_id
    primitive: implement     # 13 个原语之一
    alias: friendly-name     # 可选显示名
    description: "这个阶段的用途"
    team: implement          # research | design | implement | test | review
    duration_class: medium   # quick | medium | long
    config:
      test_strategy: tdd

composition:
  compose: sequence
  stages:
    - stage: stage_id
    - compose: loop
      ref: my_loop

loops:
  - name: my_loop
    body_stages: [stage_a, stage_b]
    until: "stage_b.pass_rate == 1.0"
    max_iterations: 3
    on_exhaustion: escalate

gates: []

environment_modes:
  local:
    skip_stages: []
  github:
    extra_stages: []
```

### 示例：自定义 "仅代码审查" 模板

```yaml
schema_version: "1.0"

metadata:
  name: code-review
  version: "1.0.0"
  display_name: "仅代码审查"
  description: "独立的代码审查，不包含实现。"
  category: verify
  applicable_scenarios:
    - "审查 PR 或代码提交"
  tags: [review, quality, check]

stages:
  - id: review
    primitive: review
    description: "审查代码的质量、安全性和风格"
    team: review
    duration_class: medium
    config:
      review_type: code
      pass_threshold: 0.80

composition:
  compose: sequence
  stages:
    - stage: review

loops: []
gates: []

environment_modes:
  local:
    skip_stages: []
  github:
    extra_stages: []
```

## 自定义上下文配置

编辑 `workflow-system/agent/context_profiles.yaml` 添加新任务类型的配置。每个配置指定 SKILL.md 段落的优先级：

- **critical**：始终包含，优先加载
- **important**：预算允许时包含
- **supplementary**：仅剩余空间时包含
- **skip**：对此任务类型永不包含

## 验证更改

自定义后，务必验证：

```bash
validate-template --all                # 模板有效
python -m pytest tests/ -q             # 所有测试通过
python -m benchmarks.devolaflow_context.runner --scenario all  # 无回退
build-skill --all                      # 适配器构建成功
```
