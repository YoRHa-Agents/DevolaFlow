---
title: "自定义指南"
description: "创建不可执行的清单种子与派生配置。"
source_files:
  - "SKILL.md"
auto_generated: true
last_synced: "2026-08-24T23:40:32Z"
source_version: "16.0.0"
---

# 自定义指南

创建不可执行的清单种子与派生配置。

## 创建清单种子

清单种子是 `workflow-system/agent/templates/seeds/` 下的 YAML 文件，遵循 `schemas/checklist-seed.schema.yaml`。它保存领域分解知识，但不会创建新的可执行运行时。

唯一可执行模板是 `workflow-system/agent/templates/builtin/change-driven.yaml`。自定义种子会实体化到这个共享清单轮次运行时中。

### 种子结构

```yaml
schema_version: "1.0"
kind: checklist-seed
metadata:
  name: code-review
  version: "1.0.0"
  description: "独立代码审查证据种子。"
  category: composite
  intent_keywords: [review, quality, pull-request]
  source:
    kind: composition
    name: code-review
    path: workflow-system/agent/templates/registry.yaml
    schema_version: "3.0"

placeholders:
  review_command:
    description: "仓库批准的有界审查命令。"
    required: true
    example: "ruff check src/ tests/"

partitions:
  - key: review
    title_template: "代码审查"
    source_stages:                 # 只记录来源，绝不表示执行顺序
      - {id: review, primitive: review}
    assertions:
      - key: findings-resolved
        statement_template: "所有 blocker 与 critical 审查发现均已解决"
        suggested_priority: P0
        verify:
          mode: metric
          template: "open_blocker_count == 0 and open_critical_count == 0"
      - key: checks-pass
        statement_template: "批准的静态审查命令通过"
        suggested_priority: P1
        verify:
          mode: command
          template: "{{ review_command }}"
```

种子可以表达什么

- 意图关键词与可选场景
- 面向用户的清单分区
- 渲染后不超过 25 词的可测断言模板
- 用户可以修改的 P0/P1/P2 建议优先级
- 有界命令、指标或人工检查三种验证方式
- `source_stages` 中仅含历史来源 ID 与 14 种原语标签之一

种子禁止表达什么

种子不是运行时 DAG。禁止顶层 `stages`、`composition`、`loops`、`gates`，也禁止 `team`、`duration_class`、`input_mapping`、`skip_condition` 等运行时字段。种子顺序仅供展示。

checkbox、证据路径、轮次号、checked-by 元数据和运行时依赖也不属于种子。只有 L0 将种子实体化为用户确认的变更清单时，才会分配这些信息。

## 注册种子

在注册表中新增一个带 `seed:` 路径且不含可执行 `path:` 的条目。只有 `change-driven` 条目可以声明 `path: builtin/change-driven.yaml`。

## 自定义上下文配置

编辑 `workflow-system/agent/context_profiles.yaml` 添加新任务类型的配置。每个配置指定 SKILL.md 段落的优先级：

- **critical**：始终包含，优先加载
- **important**：预算允许时包含
- **supplementary**：仅剩余空间时包含
- **skip**：对此任务类型永不包含

## 验证更改

自定义后，务必验证：

```bash
validate-template --all                # 23 个种子 + 一个运行时有效
python -m pytest tests/ -q             # 所有测试通过
python -m pytest tests/harness/ -v       # harness 合约通过
build-skill --all                      # 适配器构建成功
```
