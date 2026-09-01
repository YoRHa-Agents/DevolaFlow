#!/usr/bin/env python3
"""Generate deterministic EN/ZH human guides from repository sources.

The generator owns every Markdown file under ``workflow-system/human/en`` and
``workflow-system/human/zh``. Inventory values come from the seed registry,
install manifest, context profiles, and canonical rule sources rather than
being copied into prose.
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import yaml

from devolaflow.host_contract import load_host_contract, profile_projection

try:
    from devolaflow.writing_style import apply_transforms, profile_for_path

    _HUMANIZE_AVAILABLE = True
except ImportError:  # pragma: no cover - the package supplies writing_style
    apply_transforms = None  # type: ignore[assignment]
    profile_for_path = None  # type: ignore[assignment]
    _HUMANIZE_AVAILABLE = False


ROOT = Path(__file__).resolve().parent.parent
SOURCE_FILES = ["SKILL.md"]
SOURCE_VERSION = "24.3.0"
INSTALLER_URL = "https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/scripts/install.sh"
HOST_BRIDGE_URL = (
    "https://github.com/YoRHa-Agents/DevolaFlow/blob/main/"
    "workflow-system/agent/references/host-bridges.md"
)
_LAST_SYNCED_RE = re.compile(r'^last_synced:\s*"[^"]*"$', re.MULTILINE)
_RULE_ID_RE = re.compile(r"^#{2,3} ((?:S|A|C|W|ST)-\d+) — ", re.MULTILINE)

ZH_SEED_DESCRIPTIONS = {
    "hotfix": "快速完成缺陷分诊、最小修复、聚焦测试与快速发布。",
    "research-only": "开展纯研究与比较，并产出经验证的报告。",
    "design-only": "基于研究完成设计与架构评审。",
    "documentation-only": "调研、编写并评审文档。",
    "spike-poc": "构建有边界的可丢弃原型，并给出明确评估结论。",
    "refactoring": "以证据为依据重构技术债务。",
    "feature-enhancement": "通过设计、实现与发布证据扩展现有功能。",
    "full-pipeline": "为绿地项目或端到端交付提供分解知识。",
    "performance-optimization": "分析性能、实施优化、运行基准并验证可测结果。",
    "security-audit": "执行威胁建模、扫描、分析、修复与验证。",
    "research-design-review-refine": "迭代完成研究、设计、评审、改进与知识缺口闭环。",
    "dependency-setup": "配置环境与工具，并进行有界验证。",
    "onboarding": "通过分析、文档、配置与验证完成贡献者入门。",
    "demo-showcase": "以视觉质量证据支撑演示与展示分解。",
    "product-verification": "从视觉、交互、无障碍与验收维度验证用户体验。",
    "entropy-cleanup": "清理过期文档与漂移。",
    "local-archive": "独立任务归档工作流：先报告并明确批准，在严格安全与来源约束下执行有界的非删除移动。",
    "workspace-compact": "任务目录内的非破坏式收缩：风险按生命周期独立建档、判决独立追加成账，已关闭的原件搬入归档并留下可校验的映射与摘要。",
    "harness-construction": "构建 harness 基建（观测/评测/探针/基线/信号/闭环覆盖），以机器化缺口分析打底并在归档时评审能力增量。",
    "pathfinder": "以只读方式前瞻侦察基础设施与 harness 缺口，并在后续轮次前完成有界交接。",
    "retro-digest": "确定性提取回顾内容，支持可选整理，并以仅报告方式总结周期学习。",
    "migration": "系统化迁移，并验证切换与回滚准备。",
    "skill-optimization": "分析、优化、验证并记录 Agent skill。",
    "self-update": "研究、集成、测试并评估引用依赖更新。",
    "nines-assisted": "基于内置 harness 的历史研究与迭代分解知识。",
    "repo-init": "初始化仓库工作区与治理。",
    "change-driven": "唯一可执行的清单轮次生命周期运行时。",
    "web-design": "前端设计、实现、改进与确定性验证知识。",
}


@dataclass(frozen=True)
class Inventory:
    """Derived catalog data used by generated prose."""

    seeds: tuple[dict[str, object], ...]
    primitives: tuple[str, ...]
    profiles: tuple[tuple[str, str, tuple[str, ...]], ...]
    reference_count: int
    rule_count: int
    context_profile_count: int
    host_tiers: tuple[tuple[str, str], ...]
    copilot_bridge_status: str


def _read_yaml(path: Path) -> dict:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path.relative_to(ROOT)} must contain a YAML mapping")
    return payload


def _load_inventory(root: Path = ROOT) -> Inventory:
    registry_path = root / "workflow-system/agent/templates/registry.yaml"
    registry = _read_yaml(registry_path)
    seeds = tuple((registry.get("compositions") or []) + (registry.get("templates") or []))
    seed_names = {str(entry["name"]) for entry in seeds}
    zh_names = set(ZH_SEED_DESCRIPTIONS)
    if seed_names != zh_names:
        missing = sorted(seed_names - zh_names)
        extra = sorted(zh_names - seed_names)
        raise ValueError(
            "ZH seed description keys must match registry names exactly; "
            f"missing={missing}, extra={extra}"
        )

    primitives: set[str] = set()
    for entry in seeds:
        seed_path = root / "workflow-system/agent/templates" / str(entry["seed"])
        seed = _read_yaml(seed_path)
        for partition in seed.get("partitions") or []:
            for source_stage in partition.get("source_stages") or []:
                primitive = source_stage.get("primitive")
                if primitive:
                    primitives.add(str(primitive))

    manifest = _read_yaml(root / "workflow-system/agent/manifest.yaml")
    profiles = tuple(
        (
            str(name),
            str(profile["kind"]),
            tuple(str(set_name) for set_name in profile["sets"]),
        )
        for name, profile in (manifest.get("install_profiles") or {}).items()
    )
    references = tuple(manifest.get("references") or ())

    rule_ids: set[str] = set()
    for rule_file in sorted((root / ".rules").glob("*.mdc")):
        rule_ids.update(_RULE_ID_RE.findall(rule_file.read_text(encoding="utf-8")))

    context_profiles = _read_yaml(root / "workflow-system/agent/context_profiles.yaml")
    profile_count = len(context_profiles.get("profiles") or {})
    contract = load_host_contract(root / "workflow-system/agent/hosts.yaml")
    hsc_profiles = profile_projection(contract)
    missing_hsc_profiles = sorted(set(name for name, _, _ in profiles) - set(hsc_profiles))
    if missing_hsc_profiles:
        raise ValueError(f"manifest profiles missing from hosts.yaml: {missing_hsc_profiles}")
    host_tiers = tuple((str(name), str(entry["tier"])) for name, entry in contract["hosts"].items())

    return Inventory(
        seeds=seeds,
        primitives=tuple(sorted(primitives)),
        profiles=profiles,
        reference_count=len(references),
        rule_count=len(rule_ids),
        context_profile_count=profile_count,
        host_tiers=host_tiers,
        copilot_bridge_status=str(
            contract["hosts"]["copilot"]["extras"]["boundary_bridge"]["status"]
        ),
    )


INVENTORY = _load_inventory()

DOCS = [
    (
        "quickstart",
        "Quick Start Guide",
        "Install DevolaFlow, verify the correct channel, and run a first checklist workflow.",
        "快速入门指南",
        "安装 DevolaFlow，按正确渠道验证，并运行第一个清单工作流。",
    ),
    (
        "architecture-overview",
        "Architecture Overview",
        "Three-layer checklist-round architecture, provenance primitives, and evidence gates.",
        "架构概述",
        "三层清单轮次架构、来源原语与证据门。",
    ),
    (
        "workflow-types",
        "Checklist Seed Catalog",
        "Registry-derived checklist seeds and the sole change-driven runtime.",
        "清单种子目录",
        "从注册表派生的清单种子与唯一的 change-driven 运行时。",
    ),
    (
        "agent-hierarchy-guide",
        "Agent Hierarchy Guide",
        "Project, Wave, and Task responsibilities and escalation.",
        "Agent 层级指南",
        "Project、Wave、Task 的职责与升级链。",
    ),
    (
        "customization-guide",
        "Customization Guide",
        "Customize seeds, context profiles, rules, and local scaffolds without forking runtime truth.",
        "自定义指南",
        "在不分叉运行时事实源的前提下自定义种子、上下文配置、规则与本地脚手架。",
    ),
    (
        "integration-guide",
        "Integration Guide",
        "Manifest-derived host profiles, installation channels, and optional host bridges.",
        "集成指南",
        "从清单派生的宿主配置、安装渠道与可选 host bridge。",
    ),
    (
        "troubleshooting",
        "Troubleshooting",
        "Diagnose installation channels, local scaffolds, copied skills, and host bridges.",
        "故障排查",
        "诊断安装渠道、本地脚手架、已复制的 skill 与 host bridge。",
    ),
    (
        "faq",
        "FAQ",
        "Common questions about checklist rounds, installation scope, updates, and release evidence.",
        "常见问题",
        "关于清单轮次、安装范围、更新与发布证据的常见问题。",
    ),
]


def _run_timestamp() -> str:
    """Return one UTC timestamp for the current generator run."""
    source_date_epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if source_date_epoch is None:
        instant = datetime.now(UTC)
    else:
        try:
            instant = datetime.fromtimestamp(int(source_date_epoch), tz=UTC)
        except (OverflowError, OSError, ValueError) as exc:
            raise ValueError("SOURCE_DATE_EPOCH must be a valid integer Unix timestamp") from exc
    return instant.strftime("%Y-%m-%dT%H:%M:%SZ")


def _semantic_text(content: str) -> str:
    """Normalize only the generated clock field for semantic comparison."""
    normalized, count = _LAST_SYNCED_RE.subn('last_synced: "<semantic-clock>"', content)
    if count != 1:
        raise ValueError("generated document must contain exactly one last_synced field")
    return normalized


def _render_doc(
    slug: str,
    title: str,
    desc: str,
    lang: str,
    *,
    synced_at: str,
    humanize: bool,
) -> str:
    frontmatter = (
        f'---\ntitle: "{title}"\ndescription: "{desc}"\nsource_files:\n'
        + "".join(f'  - "{source_file}"\n' for source_file in SOURCE_FILES)
        + "auto_generated: true\n"
        + f'last_synced: "{synced_at}"\n'
        + f'source_version: "{SOURCE_VERSION}"\n---\n\n'
    )
    body = _gen_en_content(slug) if lang == "en" else _gen_zh_content(slug)
    content = frontmatter + f"# {title}\n\n{desc}\n\n" + body

    if humanize and _HUMANIZE_AVAILABLE:
        rel_path = f"workflow-system/human/{lang}/{slug}.md"
        profile = profile_for_path(rel_path)
        content = apply_transforms(content, profile).after
    return content


def _gen_doc(
    slug: str,
    title: str,
    desc: str,
    lang: str,
    output_dir: Path,
    *,
    humanize: bool = True,
    synced_at: str | None = None,
) -> bool:
    """Write one guide and return whether its bytes changed.

    Existing bytes win when the rendered semantics differ only in
    ``last_synced``. A real semantic change receives the supplied run-level
    timestamp (or a fresh timestamp for direct callers).
    """
    timestamp = synced_at or _run_timestamp()
    candidate = _render_doc(
        slug,
        title,
        desc,
        lang,
        synced_at=timestamp,
        humanize=humanize,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / f"{slug}.md"
    if target.exists():
        existing = target.read_text(encoding="utf-8")
        if _semantic_text(existing) == _semantic_text(candidate):
            return False
    target.write_text(candidate, encoding="utf-8", newline="\n")
    return True


def generate_docs(
    output_root: Path,
    *,
    languages: tuple[str, ...] = ("en", "zh"),
    humanize: bool = True,
    synced_at: str | None = None,
) -> tuple[int, int]:
    """Generate selected languages with one shared timestamp."""
    timestamp = synced_at or _run_timestamp()
    generated = 0
    changed = 0
    for slug, en_title, en_desc, zh_title, zh_desc in DOCS:
        for lang in languages:
            title, desc = (en_title, en_desc) if lang == "en" else (zh_title, zh_desc)
            changed += int(
                _gen_doc(
                    slug,
                    title,
                    desc,
                    lang,
                    output_root / lang,
                    humanize=humanize,
                    synced_at=timestamp,
                )
            )
            generated += 1
    return generated, changed


def _profile_rows(lang: str) -> str:
    if lang == "en":
        rows = ["| Target | Manifest kind | File sets |", "|---|---|---|"]
    else:
        rows = ["| 目标 | 清单类型 | 文件集合 |", "|---|---|---|"]
    rows.extend(
        f"| `{name}` | `{kind}` | {', '.join(f'`{item}`' for item in sets)} |"
        for name, kind, sets in INVENTORY.profiles
    )
    return "\n".join(rows)


def _seed_rows(lang: str) -> str:
    if lang == "en":
        rows = [
            "| Seed ID | Category | Canonical description | Intent tags |",
            "|---|---|---|---|",
        ]
        rows.extend(
            f"| `{entry['name']}` | `{entry['category']}` | {entry['description']} | "
            f"{', '.join(f'`{tag}`' for tag in entry.get('tags') or [])} |"
            for entry in INVENTORY.seeds
        )
    else:
        rows = ["| 种子 ID | 类别 | 本地化描述 | 意图标签 |", "|---|---|---|---|"]
        rows.extend(
            f"| `{entry['name']}` | `{entry['category']}` | "
            f"{ZH_SEED_DESCRIPTIONS[str(entry['name'])]} | "
            f"{', '.join(f'`{tag}`' for tag in entry.get('tags') or [])} |"
            for entry in INVENTORY.seeds
        )
    return "\n".join(rows)


def _en_quickstart() -> str:
    return f"""\
## 1. Choose an installation channel

The channels do not have identical scope.

### npm / npx: user-level Cursor and Claude

Requires Node 18 or newer and works on Windows. The npm meaning of `all` is
only the two user-level targets supported by this package: Cursor and Claude.

```bash
npx @yorha-agents/devola-flow install cursor
npx @yorha-agents/devola-flow install claude
npx @yorha-agents/devola-flow install all
npx @yorha-agents/devola-flow doctor
```

Downloads default to the tag matching the npm package version. Set
`DEVOLA_FLOW_REF` only when you intentionally need a branch, tag, or SHA.

### curl: broader project/global target set

The curl installer defaults to project scope and supports every target listed
by its `help`, including Cursor, Claude, Codex, Copilot, KimiCode, Windsurf,
Zed, Cline, Roo, `local`, and `standalone`.

```bash
curl -fsSL {INSTALLER_URL} | bash -s cursor
curl -fsSL {INSTALLER_URL} | bash -s claude --global
curl -fsSL {INSTALLER_URL} | bash -s all
```

The curl `all` target installs every supported host target plus the `local`
scaffold; it excludes `standalone`. Some hosts are project-only even when
`--global` is requested. A global install also attempts the default-bundled
runtime plugins; Codegraph and impeccable are bundled, while optional plugin
ui-pro remains explicit-only.
Add `--no-plugins` for skill files only. The curl installer has no doctor command.

### pip or wheel: Python runtime and local scaffold

```bash
pip install git+https://github.com/YoRHa-Agents/DevolaFlow.git
cd your-project
devola-init local --mode=standard
```

A wheel provides the Python runtime, CLIs, and `devola-init local`. It does not
bundle `workflow-system/agent/`, so wheel-only installs cannot copy non-local
host skills.

For `devola-init cursor`, `claude`, `copilot`, `codex`, or `all`, use a source
checkout plus an editable install:

```bash
git clone https://github.com/YoRHa-Agents/DevolaFlow.git
cd DevolaFlow
pip install -e ".[dev]"
devola-init cursor
```

The Python meaning of `all` is Cursor, Claude, Copilot, and Codex; it excludes
the local scaffold. With `--global`, default-bundled plugin installation is
attempted unless `--no-plugins` is present. Codegraph and impeccable are
bundled; optional plugin ui-pro remains explicit-only.

### Manual fallback

Copying only
[`SKILL.md`](https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/workflow-system/agent/SKILL.md)
can make basic instructions visible, but it omits the manifest-declared
references and examples. Prefer a channel above for a complete profile.

## 2. Verify the right surface

```bash
# npm-supported user installs and manifest parity
npx @yorha-agents/devola-flow doctor

# Python local workspace structure
devola-init-doctor

# Python audit of known copied-skill locations
devola-init-doctor --skills
```

Skill-copy success does not prove host bridge wiring. Host bridges are an
optional, separate enforcement layer; see the [host bridge reference]({HOST_BRIDGE_URL}).
Install the host-specific bridge, verify one supported event reaches the
bridge, and only then persist `DEVOLAFLOW_HOST_ENFORCE=1`.

## 3. Run the first checklist workflow

Open the installed AI host and make a natural-language request:

```text
Fix the login timeout bug and verify the regression.
```

Expected flow:

1. DevolaFlow selects one of the {len(INVENTORY.seeds)} registry-derived
   checklist seeds as decomposition knowledge.
2. You confirm the goal, measurable checklist, P0/P1/P2 priorities, and
   preflight decisions.
3. The sole `change-driven` runtime executes bounded rounds through
   L0 Project → L1 Wave → L2 Task.
4. Tasks return evidence in StatusReports; L0 checks items only after
   verification.

No workflow runner CLI is required.

## 4. Update by channel

```bash
# npm user-level Cursor/Claude copies
npx @yorha-agents/devola-flow update all

# curl-supported host skill copies; --force re-downloads matching stamps
curl -fsSL {INSTALLER_URL} | bash -s update

# local workspace and standalone file: rerun the explicit install target
curl -fsSL {INSTALLER_URL} | bash -s local
curl -fsSL {INSTALLER_URL} | bash -s standalone

# Python runtime or wheel
pip install --upgrade git+https://github.com/YoRHa-Agents/DevolaFlow.git
devola-init local --mode=standard

# source checkout and copied host skills
git pull
pip install -e ".[dev]"
devola-init cursor
```

curl `update` scans supported host skill-copy locations only. It does not scan
the `local` workspace or `standalone` file; rerun the explicit install target
for either surface. Updating the Python package does not silently refresh
previously copied host skills.
"""


def _zh_quickstart() -> str:
    return f"""\
## 1. 选择安装渠道

各渠道的范围并不相同。

### npm / npx：用户级 Cursor 与 Claude

需要 Node 18 或更高版本，可在 Windows 使用。npm 中的 `all` 只表示该包支持
的两个用户级目标：Cursor 与 Claude。

```bash
npx @yorha-agents/devola-flow install cursor
npx @yorha-agents/devola-flow install claude
npx @yorha-agents/devola-flow install all
npx @yorha-agents/devola-flow doctor
```

默认从与 npm 包版本相同的 tag 下载。只有明确需要分支、tag 或 SHA 时才设置
`DEVOLA_FLOW_REF`。

### curl：更广的项目级/全局目标集合

curl 安装器默认使用项目级范围，并支持 `help` 中列出的全部目标，包括 Cursor、
Claude、Codex、Copilot、KimiCode、Windsurf、Zed、Cline、Roo、`local` 与
`standalone`。

```bash
curl -fsSL {INSTALLER_URL} | bash -s cursor
curl -fsSL {INSTALLER_URL} | bash -s claude --global
curl -fsSL {INSTALLER_URL} | bash -s all
```

curl 的 `all` 会安装所有受支持宿主目标和 `local` 脚手架，但不包含
`standalone`。即使传入 `--global`，部分宿主仍只支持项目级。全局安装还会尝试
安装默认捆绑的运行时插件（Codegraph 和 impeccable）；ui-pro 等可选插件仅可显式选择。只复制 skill 文件时
添加 `--no-plugins`。curl 安装器没有 doctor 命令。

### pip 或 wheel：Python 运行时与本地脚手架

```bash
pip install git+https://github.com/YoRHa-Agents/DevolaFlow.git
cd your-project
devola-init local --mode=standard
```

wheel 提供 Python 运行时、CLI 与 `devola-init local`，但不打包
`workflow-system/agent/`，因此仅有 wheel 时不能复制非 local 的宿主 skill。

要运行 `devola-init cursor`、`claude`、`copilot`、`codex` 或 `all`，请使用
源码 checkout 与 editable 安装：

```bash
git clone https://github.com/YoRHa-Agents/DevolaFlow.git
cd DevolaFlow
pip install -e ".[dev]"
devola-init cursor
```

Python 中的 `all` 表示 Cursor、Claude、Copilot 与 Codex，不包含 local
脚手架。配合 `--global` 时会尝试安装默认捆绑插件，除非传入
`--no-plugins`；Codegraph 和 impeccable 默认捆绑，ui-pro 等可选插件仅可显式选择。

### 手动回退

只复制
[`SKILL.md`](https://raw.githubusercontent.com/YoRHa-Agents/DevolaFlow/main/workflow-system/agent/SKILL.md)
可以让基础指令可见，但会缺少清单声明的 references 与 examples。完整安装应优先
使用上述渠道。

## 2. 验证正确的表面

```bash
# npm 支持的用户级安装与清单一致性
npx @yorha-agents/devola-flow doctor

# Python 当前本地工作区结构
devola-init-doctor

# Python 已知 skill 副本位置审计
devola-init-doctor --skills
```

skill 复制成功不代表 host bridge 已接线。host bridge 是可选且独立的执行边界层；
请阅读 [host bridge 参考]({HOST_BRIDGE_URL})，安装宿主专用 bridge，先确认一个
受支持事件确实到达 bridge，再持久启用 `DEVOLAFLOW_HOST_ENFORCE=1`。

## 3. 运行第一个清单工作流

打开已安装的 AI 宿主，输入自然语言请求：

```text
修复登录超时 bug，并验证回归测试。
```

预期流程：

1. DevolaFlow 从注册表派生的 {len(INVENTORY.seeds)} 个清单种子中选择一个，
   作为分解知识。
2. 你确认目标、可测清单、P0/P1/P2 优先级与 preflight 决策。
3. 唯一的 `change-driven` 运行时通过 L0 Project → L1 Wave → L2 Task 执行
   有界轮次。
4. Task 在 StatusReport 中返回证据；L0 仅在核验后勾选。

不需要工作流 runner CLI。

## 4. 按渠道更新

```bash
# npm 用户级 Cursor/Claude 副本
npx @yorha-agents/devola-flow update all

# curl 支持的宿主 skill 副本；--force 可重新下载相同 stamp
curl -fsSL {INSTALLER_URL} | bash -s update

# local 工作区与 standalone 文件：重新运行对应的显式安装目标
curl -fsSL {INSTALLER_URL} | bash -s local
curl -fsSL {INSTALLER_URL} | bash -s standalone

# Python 运行时或 wheel
pip install --upgrade git+https://github.com/YoRHa-Agents/DevolaFlow.git
devola-init local --mode=standard

# 源码 checkout 与已复制的宿主 skill
git pull
pip install -e ".[dev]"
devola-init cursor
```

curl `update` 只扫描受支持的宿主 skill 副本位置，不扫描 `local` 工作区或
`standalone` 文件；这两类表面需重新运行对应的显式安装目标。更新 Python 包
不会静默刷新之前复制的宿主 skill。
"""


def _en_architecture() -> str:
    return f"""\
## Three layers

| Layer | Responsibility | Boundary |
|---|---|---|
| L0 Project | Confirm goal/checklist/preflight, select rounds, verify evidence | Does not implement |
| L1 Wave | Partition ownership-safe tasks and aggregate reports | Does not alter Task output |
| L2 Task | Implement one atomic assignment and self-verify | Does not spawn agents |

Escalation moves Task → Wave → Project → Human. Every retry loop is bounded.

## Seeds and runtime

The registry currently supplies {len(INVENTORY.seeds)} non-executable checklist
seeds. Their {len(INVENTORY.primitives)} primitive labels
({", ".join(f"`{item}`" for item in INVENTORY.primitives)}) preserve historical
decomposition provenance; list order is not runtime order. `change-driven` is
the sole executable runtime.

## Evidence contract

A round passes only when selected checklist assertions have valid evidence,
configured checks pass, reinforcement is closed, and blockers are zero.
Composite scores remain trend signals; they do not replace item evidence.

## Context and governance

Task-adaptive selection derives from {INVENTORY.context_profile_count} profiles
in `workflow-system/agent/context_profiles.yaml`. The canonical `.rules/`
sources currently contain {INVENTORY.rule_count} rule IDs; generated surfaces
must be compiled rather than hand-edited.

Harness baseline settlement and cycle-archive retention are policy. Cycle leads
perform the archive rollup manually at cycle close; no automatic archive hook
is implemented.
"""


def _zh_architecture() -> str:
    return f"""\
## 三层架构

| 层级 | 职责 | 边界 |
|---|---|---|
| L0 Project | 确认 goal/checklist/preflight、选择轮次、核验证据 | 不实施 |
| L1 Wave | 划分所有权安全的 Task 并聚合报告 | 不修改 Task 产出 |
| L2 Task | 实施一个原子任务并自证 | 不派生 Agent |

升级链为 Task → Wave → Project → Human，每个重试循环都有上限。

## 种子与运行时

注册表当前提供 {len(INVENTORY.seeds)} 个不可执行清单种子，其中
{len(INVENTORY.primitives)} 个原语标签
（{", ".join(f"`{item}`" for item in INVENTORY.primitives)}）只保存历史分解
来源；列表顺序不是运行时顺序。`change-driven` 是唯一可执行运行时。

## 证据合同

只有所选清单断言具备有效证据、配置检查通过、reinforcement 已关闭且 blocker 为零，
轮次才通过。合成分只表示趋势，不能替代逐项证据。

## 上下文与治理

任务自适应选择来自 `workflow-system/agent/context_profiles.yaml` 中派生的
{INVENTORY.context_profile_count} 个 profile。规范 `.rules/` 源当前包含
{INVENTORY.rule_count} 个规则 ID；生成面必须经编译，不得手改。

harness 基线结算与周期归档保留是政策。周期负责人在周期关闭时人工执行归档汇总；
目前没有自动归档 hook。
"""


def _en_workflow_types() -> str:
    return f"""\
## Registry catalog

The table is generated from `workflow-system/agent/templates/registry.yaml`;
membership is not maintained in this guide.

{_seed_rows("en")}

## Selection and execution

Intent selects decomposition knowledge. L0 then materializes a measurable
goal/checklist/preflight contract. Priorities, satisfied dependencies, file
ownership, and round state determine execution order; `source_stages` does not.
Every seed runs through the sole `change-driven` runtime.
"""


def _zh_workflow_types() -> str:
    return f"""\
## 注册表目录

下表从 `workflow-system/agent/templates/registry.yaml` 生成；本指南不单独维护成员列表。

{_seed_rows("zh")}

## 选择与执行

意图匹配选择分解知识，随后 L0 将其实体化为可测的 goal/checklist/preflight 合同。
优先级、已满足依赖、文件所有权与轮次状态决定执行顺序；`source_stages` 不决定。
所有种子都通过唯一的 `change-driven` 运行时执行。
"""


def _en_hierarchy() -> str:
    return """\
## L0 Project

Confirms the goal, checklist, priorities, preflight, and round selection with
the human. It verifies evidence and decides advance, retry, escalate, or abort.
It never performs delegated work.

## L1 Wave

Dispatches at most five L2 Tasks with disjoint writable ownership, detects
conflicts, and aggregates StatusReports. It never implements or edits Task
output.

## L2 Task

Receives one atomic TaskDispatch, writes only owned files, runs bounded
verification, and returns falsifiable evidence. It cannot spawn another agent.

## Messages and escalation

TaskDispatch moves down; StatusReport moves up. Exception escalation follows
Task → Wave → Project → Human. Free-form shared state is not an artifact
contract.
"""


def _zh_hierarchy() -> str:
    return """\
## L0 Project

与用户确认目标、清单、优先级、preflight 与轮次选择，核验证据，并决定推进、重试、
升级或终止。绝不执行已委托工作。

## L1 Wave

向最多五个可写所有权互斥的 L2 Task 分派任务，检测冲突并聚合 StatusReport。
绝不实施，也不修改 Task 产出。

## L2 Task

接收一个原子 TaskDispatch，只写 owned files，执行有界验证并返回可证伪证据。
不得派生另一个 Agent。

## 消息与升级

TaskDispatch 向下，StatusReport 向上。异常按 Task → Wave → Project → Human 升级。
自由文本共享状态不是工件合同。
"""


def _en_customization() -> str:
    return """\
## Checklist seeds

Add a seed under `workflow-system/agent/templates/seeds/` and register it once
in `templates/registry.yaml`. Seeds may define intent, partitions, assertion
templates, suggested priorities, verification, and provenance. They must not
define another executable DAG; `change-driven` remains the runtime.

## Context profiles

Edit `workflow-system/agent/context_profiles.yaml`, keep critical sections
within budget, and inspect affected selectors with
`python -m devolaflow.task_adaptive_selector <task-type> --verbose`.

## Rules

Edit `.rules/*.mdc`, then run `make compile-rules`. Never hand-edit generated
`AGENTS.md`, `.cursor/rules/repo-governance.mdc`, or `docs/STYLE-RULES.md`.

## Local scaffold depth

`devola-init local --mode=core|standard|full` selects scaffolding depth.
Individual `--no-compile`, `--with-examples`, and `--no-with-examples` flags
override mode defaults. Re-running the scaffold is idempotent.
"""


def _zh_customization() -> str:
    return """\
## 清单种子

在 `workflow-system/agent/templates/seeds/` 下添加种子，并在
`templates/registry.yaml` 中注册一次。种子可以定义意图、分区、断言模板、建议
优先级、验证与来源，但不得定义另一个可执行 DAG；运行时仍是 `change-driven`。

## 上下文配置

编辑 `workflow-system/agent/context_profiles.yaml`，确保 critical 段落不超预算，
并运行 `python -m devolaflow.task_adaptive_selector <task-type> --verbose` 检查
受影响的选择结果。

## 规则

编辑 `.rules/*.mdc` 后运行 `make compile-rules`。不得手改生成的 `AGENTS.md`、
`.cursor/rules/repo-governance.mdc` 或 `docs/STYLE-RULES.md`。

## 本地脚手架深度

`devola-init local --mode=core|standard|full` 选择脚手架深度。单独传入的
`--no-compile`、`--with-examples`、`--no-with-examples` 会覆盖 mode 默认值。
重复运行保持幂等。
"""


def _en_integration() -> str:
    return f"""\
## Host Support Contract

The canonical host contract is
`workflow-system/agent/hosts.yaml`. Support is tiered; guaranteed hosts must
declare the full delivery floor, while optional capabilities are never inferred
from an unrelated install registry.

| Tier | Hosts |
|---|---|
{chr(10).join(f"| `{tier}` | {', '.join(f'`{name}`' for name, item_tier in INVENTORY.host_tiers if item_tier == tier)} |" for tier in ("guaranteed", "community-installable", "community-build-only"))}

## Manifest-derived install profiles

The profile names and file sets below come from
`workflow-system/agent/manifest.yaml`. The `references` set currently contains
{INVENTORY.reference_count} files; consumers derive the list from the manifest.

{_profile_rows("en")}

## Channel scope

| Channel | Scope and `all` meaning |
|---|---|
| npm/npx | User-level `cursor`, `claude`, or both via npm `all` |
| curl | Project by default; supported host targets plus separate `local` and `standalone` targets; `--global` where supported; curl `all` installs all supported hosts plus `local` and excludes `standalone` |
| pip/wheel | Runtime CLIs and `devola-init local`; non-local skill copy needs a clone plus editable install |
| Python source | `devola-init all` means Cursor, Claude, Copilot, and Codex; it excludes `local` |

```bash
# Complete, self-contained curl examples
curl -fsSL {INSTALLER_URL} | bash -s cursor
curl -fsSL {INSTALLER_URL} | bash -s claude --global --no-plugins
curl -fsSL {INSTALLER_URL} | bash -s kimicode
curl -fsSL {INSTALLER_URL} | bash -s zed
curl -fsSL {INSTALLER_URL} | bash -s cline
curl -fsSL {INSTALLER_URL} | bash -s roo
```

## Local workspace modes and plugins

```bash
devola-init local --mode=core
devola-init local --mode=standard
devola-init local --mode=full
devola-init cursor --global --no-plugins
```

`core` skips compilation and examples, `standard` compiles without examples,
and `full` compiles and seeds examples. Global curl/Python installs attempt
default-bundled runtime plugins by default; `--no-plugins` keeps only skill
files. Codegraph and impeccable are bundled; optional plugin ui-pro remains
explicit-only. Plugin
installation is separate from whether the host can discover the copied skill.

## Doctor and update boundaries

```bash
npx @yorha-agents/devola-flow doctor
devola-init-doctor
devola-init-doctor --skills
npx @yorha-agents/devola-flow update all
curl -fsSL {INSTALLER_URL} | bash -s update
curl -fsSL {INSTALLER_URL} | bash -s local
curl -fsSL {INSTALLER_URL} | bash -s standalone
```

The first doctor checks npm-supported user locations. The second checks the
current Python workspace. The third scans known copied-skill locations. There
is no curl doctor. curl `update` scans supported host skill-copy locations
only; it does not scan the `local` workspace or `standalone` file. Rerun the
explicit `local` or `standalone` install target for those surfaces.

## Optional host bridge enforcement

Skill copy makes Markdown discoverable. A host bridge separately routes host
tool events through lifecycle boundary enforcement. Current bridge status and
evidence are declared per host in `hosts.yaml`; Copilot's stdout-JSON bridge
path is {"implemented" if INVENTORY.copilot_bridge_status == "implemented" else "designed"}
in this release.

Follow the [host-specific bridge procedure]({HOST_BRIDGE_URL}). For example:

```bash
python -m devolaflow.hostbridge install cursor
python -m devolaflow.hostbridge install claude
python -m devolaflow.hostbridge install codex
```

Confirm the host config is active (including Codex `/hooks` trust), exercise
one known-allowed event with a one-shot enforcement environment, and inspect
`.local/telemetry/hostbridge.jsonl`. Only then persist:

```bash
export DEVOLAFLOW_HOST_ENFORCE=1
```

Unsupported hosts remain skill-only; do not describe them as enforced.
"""


def _zh_integration() -> str:
    return f"""\
## Host Support Contract

规范宿主契约位于 `workflow-system/agent/hosts.yaml`。支持按档位定义；
保证宿主必须声明完整 delivery floor，可选能力不会从其他安装注册表推断。

| 档位 | 宿主 |
|---|---|
{chr(10).join(f"| `{tier}` | {'、'.join(f'`{name}`' for name, item_tier in INVENTORY.host_tiers if item_tier == tier)} |" for tier in ("guaranteed", "community-installable", "community-build-only"))}

## 从清单派生的安装 profile

下列 profile 名称与文件集合来自 `workflow-system/agent/manifest.yaml`。
`references` 集合当前包含 {INVENTORY.reference_count} 个文件；消费者从清单派生列表。

{_profile_rows("zh")}

## 渠道范围

| 渠道 | 范围与 `all` 含义 |
|---|---|
| npm/npx | 用户级 `cursor`、`claude`，或 npm `all`（两者） |
| curl | 默认项目级；提供受支持宿主目标以及独立的 `local`、`standalone` 目标；`--global` 仅在支持时生效；curl `all` 安装所有受支持宿主和 `local`，不包含 `standalone` |
| pip/wheel | 运行时 CLI 与 `devola-init local`；非 local skill 复制需要 clone 加 editable 安装 |
| Python 源码 | `devola-init all` 表示 Cursor、Claude、Copilot、Codex，不包含 `local` |

```bash
# 完整、自包含的 curl 示例
curl -fsSL {INSTALLER_URL} | bash -s cursor
curl -fsSL {INSTALLER_URL} | bash -s claude --global --no-plugins
curl -fsSL {INSTALLER_URL} | bash -s kimicode
curl -fsSL {INSTALLER_URL} | bash -s zed
curl -fsSL {INSTALLER_URL} | bash -s cline
curl -fsSL {INSTALLER_URL} | bash -s roo
```

## 本地工作区模式与插件

```bash
devola-init local --mode=core
devola-init local --mode=standard
devola-init local --mode=full
devola-init cursor --global --no-plugins
```

`core` 跳过编译与示例，`standard` 编译但不生成示例，`full` 编译并播种示例。
全局 curl/Python 安装默认尝试默认捆绑的运行时插件；`--no-plugins` 只保留
skill 文件；Codegraph 和 impeccable 默认捆绑，ui-pro 等可选插件仅可显式选择。插件安装与宿主
能否发现已复制 skill 是两件事。

## Doctor 与更新边界

```bash
npx @yorha-agents/devola-flow doctor
devola-init-doctor
devola-init-doctor --skills
npx @yorha-agents/devola-flow update all
curl -fsSL {INSTALLER_URL} | bash -s update
curl -fsSL {INSTALLER_URL} | bash -s local
curl -fsSL {INSTALLER_URL} | bash -s standalone
```

第一个 doctor 检查 npm 支持的用户级位置，第二个检查当前 Python 工作区，第三个
扫描已知 skill 副本。curl 没有 doctor。curl `update` 只扫描受支持的宿主 skill
副本位置，不扫描 `local` 工作区或 `standalone` 文件；这些表面需重新运行显式的
`local` 或 `standalone` 安装目标。

## 可选 host bridge 执行边界

复制 skill 只让 Markdown 可发现。host bridge 另行把宿主工具事件路由到生命周期
边界执行。每个宿主的 bridge 状态与证据在 `hosts.yaml` 中声明；Copilot 的
stdout-JSON bridge 路径在本版本中为{"已实现" if INVENTORY.copilot_bridge_status == "implemented" else "已设计"}。

按 [宿主专用 bridge 流程]({HOST_BRIDGE_URL}) 操作，例如：

```bash
python -m devolaflow.hostbridge install cursor
python -m devolaflow.hostbridge install claude
python -m devolaflow.hostbridge install codex
```

确认宿主配置已激活（Codex 还需 `/hooks` trust），在单次环境中执行一个已知允许事件，
并检查 `.local/telemetry/hostbridge.jsonl`。确认后再持久启用：

```bash
export DEVOLAFLOW_HOST_ENFORCE=1
```

不支持 bridge 的宿主保持 skill-only，不应描述为已执行边界。
"""


def _en_troubleshooting() -> str:
    return f"""\
## Identify the installation channel first

### npm user install

```bash
node --version
npx @yorha-agents/devola-flow doctor
npx @yorha-agents/devola-flow update cursor
```

Node must be 18 or newer. npm targets only user-level Cursor and Claude.
Check `DEVOLA_FLOW_REF` when the installed ref is unexpected.

### curl install

```bash
curl -fsSL {INSTALLER_URL} | bash -s help
curl -fsSL {INSTALLER_URL} | bash -s update --force
curl -fsSL {INSTALLER_URL} | bash -s uninstall --dry-run
```

Every snippet is self-contained. curl has `update` and `uninstall`, but no
doctor. Its `update` scans supported host skill-copy locations only, not the
`local` workspace or `standalone` file; rerun either explicit install target
for those surfaces. Use `devola-init-doctor --skills` only when the Python
package is also installed and you want to audit known skill paths.

### pip or wheel install

```bash
python -c "import devolaflow; print(devolaflow.__version__)"
devola-init local --mode=core
devola-init-doctor
```

Wheel-only installs support the local scaffold. If `devola-init cursor` (or
another non-local target) reports that the agent source tree is missing, clone
the repository and install editable:

```bash
git clone https://github.com/YoRHa-Agents/DevolaFlow.git
cd DevolaFlow
pip install -e ".[dev]"
devola-init cursor
```

## Local scaffold recovery

```bash
devola-init local --mode=core
devola-init local --mode=standard
devola-init local --mode=full
devola-init-doctor
sync-rules
```

`core` intentionally skips rule compilation. `standard` compiles without
examples. `full` compiles and seeds examples. Compilation repair is
`sync-rules` (or `make compile-rules` in a clone).

For global skill installation without the default plugin attempts:

```bash
devola-init cursor --global --no-plugins
curl -fsSL {INSTALLER_URL} | bash -s cursor --global --no-plugins
```

## Skill copy versus host bridge

If the skill is visible but an out-of-scope host write is not blocked, verify
the optional bridge separately. Follow the [host bridge matrix]({HOST_BRIDGE_URL}),
confirm the host-specific config and event matcher, trust Codex hooks when
applicable, then test one event before persisting
`DEVOLAFLOW_HOST_ENFORCE=1`. Unsupported hosts remain skill-only.

## Workflow symptoms

- Wrong seed: state the intent explicitly or name a seed.
- One-pass execution: verify the skill is loaded and request a bounded
  multi-step change with measurable checks.
- Repeated convergence: inspect unresolved checklist assertions and blockers;
  bounded retries eventually escalate.

## Harness and archive evidence

Run `make test-harness` for deterministic contracts. W-16 settlement and W-19
cycle archive rollup are manual release-policy steps; there is no automatic
archive hook. Do not diagnose a missing automatic archive as a runtime failure.
"""


def _zh_troubleshooting() -> str:
    return f"""\
## 先识别安装渠道

### npm 用户级安装

```bash
node --version
npx @yorha-agents/devola-flow doctor
npx @yorha-agents/devola-flow update cursor
```

Node 必须为 18 或更高版本。npm 只支持用户级 Cursor 与 Claude。安装 ref 异常时
检查 `DEVOLA_FLOW_REF`。

### curl 安装

```bash
curl -fsSL {INSTALLER_URL} | bash -s help
curl -fsSL {INSTALLER_URL} | bash -s update --force
curl -fsSL {INSTALLER_URL} | bash -s uninstall --dry-run
```

每段命令都可独立复制。curl 有 `update` 与 `uninstall`，但没有 doctor。
`update` 只扫描受支持的宿主 skill 副本位置，不扫描 `local` 工作区或
`standalone` 文件；这些表面需重新运行对应的显式安装目标。只有同时安装了
Python 包，并需要审计已知 skill 路径时，才使用 `devola-init-doctor --skills`。

### pip 或 wheel 安装

```bash
python -c "import devolaflow; print(devolaflow.__version__)"
devola-init local --mode=core
devola-init-doctor
```

仅 wheel 安装支持 local 脚手架。如果 `devola-init cursor`（或其他非 local 目标）
报告缺少 agent 源码树，请 clone 仓库并 editable 安装：

```bash
git clone https://github.com/YoRHa-Agents/DevolaFlow.git
cd DevolaFlow
pip install -e ".[dev]"
devola-init cursor
```

## 本地脚手架恢复

```bash
devola-init local --mode=core
devola-init local --mode=standard
devola-init local --mode=full
devola-init-doctor
sync-rules
```

`core` 有意跳过规则编译，`standard` 编译但不生成示例，`full` 编译并播种示例。
编译修复命令是 `sync-rules`（在 clone 内也可用 `make compile-rules`）。

全局安装 skill 但不尝试默认插件：

```bash
devola-init cursor --global --no-plugins
curl -fsSL {INSTALLER_URL} | bash -s cursor --global --no-plugins
```

## skill 复制与 host bridge

如果 skill 可见但宿主越界写入没有被阻止，请单独验证可选 bridge。按照
[host bridge 矩阵]({HOST_BRIDGE_URL}) 检查宿主专用配置与事件 matcher；Codex
还需信任 hooks。先测试一个事件，再持久设置 `DEVOLAFLOW_HOST_ENFORCE=1`。
不支持的宿主保持 skill-only。

## 工作流症状

- 选错种子：明确表达意图或直接指定种子。
- 单轮完成全部工作：确认 skill 已加载，并请求带可测检查的有界多步骤变更。
- 反复收敛：检查未完成断言与 blocker；有界重试最终会升级。

## Harness 与归档证据

运行 `make test-harness` 验证确定性合同。W-16 结算与 W-19 周期归档汇总是人工发布
政策步骤；没有自动归档 hook。不要把缺少自动归档诊断为运行时故障。
"""


def _en_faq() -> str:
    return f"""\
## What does DevolaFlow execute?

It selects one of {len(INVENTORY.seeds)} registry-derived checklist seeds as
decomposition knowledge, materializes a user-confirmed checklist, and executes
that contract through the sole `change-driven` runtime.

## Do the three `all` targets mean the same thing?

No. npm `all` is user-level Cursor plus Claude. Python `devola-init all` is
Cursor, Claude, Copilot, and Codex and excludes `local`. curl `all` installs
all supported host targets plus `local` and excludes `standalone`.

## Which doctor should I run?

- `npx @yorha-agents/devola-flow doctor`: npm-supported user installs.
- `devola-init-doctor`: current Python local workspace.
- `devola-init-doctor --skills`: known copied-skill locations.

The curl installer has no doctor.

## Does updating Python update copied skills?

No. Update the package, then rerun `devola-init local` for a local scaffold or
rerun the desired host target from a source checkout. npm and curl have their
own update commands.

## Is host bridge enforcement automatic?

No. Skill installation and host bridge wiring are separate. Verify a supported
host bridge before setting `DEVOLAFLOW_HOST_ENFORCE=1`.

## Is harness archive rollup automatic?

No. Baseline settlement and archive retention are release policy performed
manually at cycle close. Current runtime does not provide an automatic archive
hook.
"""


def _zh_faq() -> str:
    return f"""\
## DevolaFlow 执行什么？

它从注册表派生的 {len(INVENTORY.seeds)} 个清单种子中选择分解知识，将其实体化为
用户确认的清单，并通过唯一的 `change-driven` 运行时执行该合同。

## 三个 `all` 含义相同吗？

不同。npm 的 `all` 是用户级 Cursor 加 Claude；Python 的 `devola-init all`
是 Cursor、Claude、Copilot、Codex，不包含 `local`；curl 的 `all` 会安装所有
受支持宿主目标和 `local`，但不包含 `standalone`。

## 应运行哪个 doctor？

- `npx @yorha-agents/devola-flow doctor`：npm 支持的用户级安装。
- `devola-init-doctor`：当前 Python 本地工作区。
- `devola-init-doctor --skills`：已知 skill 副本位置。

curl 安装器没有 doctor。

## 更新 Python 会更新已复制 skill 吗？

不会。更新包后，为本地脚手架重新运行 `devola-init local`；非 local skill 请从
源码 checkout 重新运行对应宿主目标。npm 与 curl 各有自己的 update 命令。

## host bridge 会自动执行吗？

不会。skill 安装与 host bridge 接线是独立状态。设置
`DEVOLAFLOW_HOST_ENFORCE=1` 前必须验证一个受支持的宿主 bridge。

## harness 归档汇总会自动执行吗？

不会。基线结算与归档保留是周期关闭时人工执行的发布政策；当前运行时没有自动归档
hook。
"""


def _gen_en_content(slug: str) -> str:
    sections = {
        "quickstart": _en_quickstart,
        "architecture-overview": _en_architecture,
        "workflow-types": _en_workflow_types,
        "agent-hierarchy-guide": _en_hierarchy,
        "customization-guide": _en_customization,
        "integration-guide": _en_integration,
        "troubleshooting": _en_troubleshooting,
        "faq": _en_faq,
    }
    return sections[slug]()


def _gen_zh_content(slug: str) -> str:
    sections = {
        "quickstart": _zh_quickstart,
        "architecture-overview": _zh_architecture,
        "workflow-types": _zh_workflow_types,
        "agent-hierarchy-guide": _zh_hierarchy,
        "customization-guide": _zh_customization,
        "integration-guide": _zh_integration,
        "troubleshooting": _zh_troubleshooting,
        "faq": _zh_faq,
    }
    return sections[slug]()


def main() -> None:
    if "--all" in sys.argv or "--lang" not in sys.argv:
        languages = ("en", "zh") if "--all" in sys.argv else ("en",)
    else:
        try:
            language = sys.argv[sys.argv.index("--lang") + 1]
        except IndexError as exc:
            raise SystemExit("--lang requires en or zh") from exc
        if language not in {"en", "zh"}:
            raise SystemExit("--lang requires en or zh")
        languages = (language,)

    humanize = "--no-humanize" not in sys.argv
    generated, changed = generate_docs(
        ROOT / "workflow-system/human",
        languages=languages,
        humanize=humanize,
    )
    suffix = "" if humanize else " (no-humanize)"
    print(f"Generated {generated} human doc files; {changed} changed{suffix}.")


if __name__ == "__main__":
    main()
