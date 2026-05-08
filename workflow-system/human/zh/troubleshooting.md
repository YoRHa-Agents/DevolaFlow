---
title: "故障排查"
description: "工作流执行中的常见问题和解决方案。"
source_files:
  - "SKILL.md"
auto_generated: true
last_synced: "2026-05-08T06:28:19Z"
source_version: "11.0.4"
---

# 故障排查

工作流执行中的常见问题和解决方案。

## 安装问题

`devola-init` 命令未找到

CLI 工具需要 pip 安装：
```bash
pip install git+https://github.com/YoRHa-Agents/DevolaFlow.git
# 或开发版：
pip install -e ".[dev]"
```

安装器报 "权限拒绝"

安装器需要对目标目录的写入权限。全局安装写入 `~/.cursor/skills/`，应该是用户可写的。

## 工作流问题

Agent 没有选择正确的工作流

DevolaFlow 使用关键词匹配。让你的意图更明确：
- 不要说："帮我处理登录页面"
- 改为说："修复登录页面的 bug"（→ hotfix）或 "重新设计登录页面 UI"（→ design-only）

也可以直接指定："使用 refactoring 工作流清理认证模块。"

Agent 试图一次完成所有事情

通常意味着 skill 文件未加载。检查：
1. 确认 skill 文件存在：`ls .cursor/skills/devola-flow/SKILL.md`
2. 在 Cursor 设置中确认 skill 可见
3. 尝试显式附加：`@devola-flow 实现用户系统`

收敛循环运行太多次

默认最大 3 次迭代。如果持续循环：
1. 检查验收标准是否过于严格
2. 查找阻止收敛的冲突需求
3. 达到最大迭代后 Agent 会升级到你 — 查看差异报告

## 测试与构建问题

修改 SKILL.md 后测试失败

运行 `python -m pytest tests/test_version.py -v` 检查版本一致性。使用 `scripts/bump_version.py` 进行统一更新。

`build-skill` 报告超出预算

SKILL.md 必须保持在 500 行以内（规则 SF-1）。运行 `build-skill --all` 验证。

模板验证失败

```bash
validate-template path/to/template.yaml
```

常见原因：
- 缺少必需字段（`schema_version`、`metadata`、`stages`、`composition`）
- `composition` 中的阶段引用与 `stages[].id` 不匹配
- 循环引用与 `loops[].name` 不匹配
- 无效的原语名称（必须是 13 个原语之一）

## 基准测试问题

EvoBench 显示回退

```bash
python -m benchmarks.devolaflow_context.runner --scenario all --compare-baseline
```

如果某个场景回退：
1. 检查近期对 `context_profiles.yaml` 或 SKILL.md 段落边界的更改
2. 审查特定场景的预期 vs 实际段落选择
3. 修复后更新基线：`python -m benchmarks.devolaflow_context.runner --generate-baseline`

## 获取帮助

**GitHub Issues**:[https://github.com/YoRHa-Agents/DevolaFlow/issues](https://github.com/YoRHa-Agents/DevolaFlow/issues)**交互式演示**:[https://yorha-agents.github.io/DevolaFlow/](https://yorha-agents.github.io/DevolaFlow/)
