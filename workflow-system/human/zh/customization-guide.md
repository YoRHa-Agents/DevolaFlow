---
title: "自定义指南"
description: "创建自定义工作流模板和派生配置。"
source_files: ["SKILL.md"]
auto_generated: true
last_synced: "2026-04-04T00:00:00Z"
source_version: "1.0.0"
---

# 自定义指南

DevolaFlow 内置 11 种工作流模板。你可以通过创建自定义模板或从现有模板派生来扩展。

## 方式 1：创建自定义模板

在 `workflow-system/agent/templates/custom/` 中创建 YAML 文件，遵循模板 Schema。

验证：`validate-template workflow-system/agent/templates/custom/your-template.yaml`

## 方式 2：从内置模板派生

使用 `extends` 和 `overrides` 字段：

```yaml
extends: full-pipeline
overrides:
  stages:
    impl:
      config:
        test_strategy: test_after
```

放在 `templates/derived/` 目录。派生模板自动按名称优先级覆盖基础模板。

## 发现优先级

1. `templates/custom/` (最高优先级)
2. `templates/derived/`
3. `templates/builtin/` (出厂默认)
