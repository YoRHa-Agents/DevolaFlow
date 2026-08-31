/**
 * Design Architecture companion.
 * Registers complete page-local EN/ZH copy and exposes one finite,
 * keyboard-accessible selector for the three current agent layers.
 */
(function () {
  'use strict';

  var sourceFacts = Object.freeze({
    skill: Object.freeze({
      path: 'workflow-system/agent/SKILL.md',
      lines: 399
    }),
    seedCatalog: Object.freeze({
      path: 'workflow-system/human/demo/shared/seed-catalog.js',
      count: 27,
      requiredSeed: 'retro-digest'
    })
  });

  function reference(stem) {
    return Object.freeze({
      stem: stem,
      path: 'workflow-system/agent/references/' + stem + '.md'
    });
  }

  var referenceInventory = Object.freeze([
    reference("agent-hierarchy"),
    reference("agent-workspace"),
    reference("artifact-quality"),
    reference("behavioral-guidelines"),
    reference("codegraph"),
    reference("compression-pipeline"),
    reference("context-isolation"),
    reference("decomposition-gate"),
    reference("degraded-mode"),
    reference("domain-awareness"),
    reference("env-flags"),
    reference("evaluator-rosetta"),
    reference("execution-protocol"),
    reference("wave-dispatch"),
    reference("grill-mode"),
    reference("harness-construction"),
    reference("host-bridges"),
    reference("host-contract"),
    reference("human-surface"),
    reference("impeccable"),
    reference("local-archive"),
    reference("message-schemas"),
    reference("meta-framework"),
    reference("pathfinder"),
    reference("plan-mode-enforcement"),
    reference("repo-modes"),
    reference("retro-digest"),
    reference("memory-router"),
    reference("subagent-patterns"),
    reference("task-quality-score"),
    reference("team-roles"),
    reference("troubleshooting")
  ]);

  var knowledgeInventory = Object.freeze([
    { path: "workflow-system/agent/knowledge/index.md" },
    { path: "workflow-system/agent/knowledge/interview-protocol.md" },
    { path: "workflow-system/agent/knowledge/code-rules-mapping.md" },
    { path: "workflow-system/agent/knowledge/principle-mapping.md" },
    { path: "workflow-system/agent/knowledge/reference-dependencies.yaml" },
    { path: "workflow-system/agent/knowledge/runtime-plugins.yaml" }
  ]);

  var translations = {
    en: {
      'arch.hero.eyebrow': 'Current architecture companion',
      'arch.hero.source': 'Source',
      'arch.hero.title': 'to runtime',
      'arch.hero.lede': 'A vertical map of what people author, what tooling compiles or distributes, what agents exchange, what the runtime controls, and what evidence returns.',
      'arch.hero.guardrail': 'Read downward as a flow of authority. Generated surfaces point back to editable sources; they do not become new sources.',
      'arch.fact.seeds': 'Checklist seeds',
      'arch.fact.runtime': 'Executable runtime',
      'arch.fact.layers': 'Agent layers',
      'arch.fact.references': 'Domain references',
      'arch.fact.budgets': 'Context budgets',
      'arch.link.system': 'System',
      'arch.link.seeds': 'Seed library ↗',
      'arch.link.harness': 'Harness',
      'arch.link.skill': 'Read SKILL ↗',
      'arch.link.design': 'Design system',
      'arch.link.visualizer': 'Workflow visualizer',
      'arch.companions.label': 'System companions',
      'arch.flow.title': 'The current source → contract → runtime → evidence flow',
      'arch.flow.desc': 'The map groups responsibilities instead of listing every file. Each band names the authoritative input and the boundary it feeds.',
      'arch.flow.authoring.kicker': 'Editable source',
      'arch.flow.authoring.title': 'Authoring sources',
      'arch.flow.authoring.body': 'SKILL defines operator-facing orchestration; the manifest owns the 32-reference install set; the registry owns 27 checklist seeds, including retro-digest; context profiles own 5K / 5K / 8K layer budgets; schemas own message shapes; and .rules/*.mdc owns governance prose.',
      'arch.inventory.summary': 'Browse 32 references + 6 knowledge files',
      'arch.inventory.desc': 'This compact inventory is rendered from the same page data checked against the install manifest and the on-disk knowledge catalog.',
      'arch.inventory.filterLabel': 'Filter source paths',
      'arch.inventory.filterPlaceholder': 'Type a name or path',
      'arch.inventory.references': 'Tier-2 references · 32',
      'arch.inventory.knowledge': 'Tier-3 knowledge · 6',
      'arch.inventory.status': 'Showing {shown} of {total} files',
      'arch.flow.compiled.kicker': 'Generated and shipped',
      'arch.flow.compiled.title': 'Compiled & distributed surfaces',
      'arch.flow.compiled.body': 'The rule compiler renders .rules/ into AGENTS.md, the on-demand Cursor repo-governance surface, and the Style reference. The install manifest selects SKILL, 32 references, and examples for each host profile. These outputs are generated views, not editable rule sources.',
      'arch.flow.contracts.kicker': 'Typed boundary',
      'arch.flow.contracts.title': 'Contracts',
      'arch.flow.contracts.body': 'Lean TaskDispatch carries goals, owned files, acceptance criteria, bounded gates, and optional change context downward. Lean StatusReport carries artifacts, item-keyed results, metrics, concerns, and self-check evidence upward. Paths, IDs, errors, and metrics remain verbatim.',
      'arch.flow.contracts.down': 'Project → Wave → Task',
      'arch.flow.contracts.up': 'Task → Wave → Project',
      'arch.flow.runtime.kicker': 'Executable control',
      'arch.flow.runtime.title': 'Runtime',
      'arch.flow.runtime.body': 'TemplateRegistry.load_seed(name) turns one of 27 seeds into checklist decomposition knowledge, including retro-digest. A seed’s source_stages field records provenance only: it does not schedule work. TemplateRegistry.load_template("change-driven") loads templates/builtin/change-driven.yaml, the sole executable lifecycle for signed preflight, bounded checklist rounds, evidence gates, and archive.',
      'arch.runtime.propose': 'Propose',
      'arch.runtime.preflight': 'Preflight',
      'arch.runtime.round': 'Bounded round',
      'arch.runtime.archive': 'Guarded archive',
      'arch.flow.evidence.kicker': 'Measured return path',
      'arch.flow.evidence.title': 'Evidence',
      'arch.flow.harness.title': 'Harness',
      'arch.flow.evidence.body': 'Dispatch telemetry records measured token use, budgets, constraint counts, quantifiable ratios, layer attribution, and round context in append-only JSONL. The built-in harness aggregates that ledger and deterministic repository signals into six W-3 dimensions, then emits READY, NOT_READY, or explicit INSUFFICIENT.',
      'arch.flow.evidence.note': 'Tuning proposals remain immutable and hash-bound. Applying one requires a separate explicit approval artifact; evaluation alone never mutates runtime configuration.',
      'arch.flow.human.kicker': 'Readable projection',
      'arch.flow.human.title': 'Human output',
      'arch.flow.human.body': 'People confirm goals, checklist assertions, preflight authorization, and proposal approvals. Human-facing digests, convergence reports, guides, and this demo project current contracts into reviewable output without becoming the runtime source of truth.',
      'arch.layers.title': 'Select one runtime layer',
      'arch.layers.desc': 'The selector has exactly three states. Each state shows the layer’s context budget, authority, evidence responsibility, and implementation boundary.',
      'arch.layer.project': 'Project',
      'arch.layer.wave': 'Wave',
      'arch.layer.task': 'Task',
      'arch.layer.receives': 'Receives',
      'arch.layer.controls': 'Controls',
      'arch.layer.boundary': 'Boundary',
      'arch.layer.project.title': 'Owns the round decision',
      'arch.layer.project.receives': 'User goal, checklist, preflight, round status, and bounded evidence summaries.',
      'arch.layer.project.controls': 'Round selection, Wave partitioning, gates, reinforcement, checkpoints, archive, and human reporting.',
      'arch.layer.project.boundary': 'Dispatches delegated work; never implements it or replaces item evidence with a score.',
      'arch.layer.wave.title': 'Coordinates a bounded partition',
      'arch.layer.wave.receives': 'A selected task list, dependency map, ownership map, and predecessor evidence summaries.',
      'arch.layer.wave.controls': 'Conflict checks, pairwise-disjoint Task dispatch, and item-level evidence aggregation.',
      'arch.layer.wave.boundary': 'May dispatch no more than five Tasks; never edits Task output or marks checklist items complete.',
      'arch.layer.task.title': 'Implements one atomic assignment',
      'arch.layer.task.receives': 'One TaskDispatch, owned and read-only paths, relevant contracts, rules, and bounded predecessor facts.',
      'arch.layer.task.controls': 'Owned-file changes, bounded self-verification, and a lean evidence-bearing StatusReport.',
      'arch.layer.task.boundary': 'Only implementation layer; never spawns agents, self-scores, or writes outside ownership.',
      'arch.truths.title': 'Three distinctions that prevent drift',
      'arch.truths.desc': 'The architecture stays understandable when knowledge, executable control, and generated projection remain separate.',
      'arch.truth.seed.title': 'Seed ≠ runtime',
      'arch.truth.seed.body': 'A seed contributes checklist decomposition knowledge. source_stages preserves where that knowledge came from; only change-driven executes the lifecycle.',
      'arch.truth.rule.title': 'Compiled ≠ authored',
      'arch.truth.rule.body': 'Governance edits begin in .rules/*.mdc. AGENTS.md, repo-governance.mdc, and STYLE-RULES.md are compiler outputs protected by drift checks.',
      'arch.truth.evidence.title': 'Evidence ≠ verdict shortcut',
      'arch.truth.evidence.body': 'Item-level checks and artifacts decide round completion. Harness dimensions and a composite support release readiness; unavailable inputs stay INSUFFICIENT.',
      'arch.aria.facts': 'Current architecture facts',
      'arch.aria.heroLinks': 'Architecture links',
      'arch.aria.companions': 'System companions',
      'arch.aria.authoringPaths': 'Authoring source paths',
      'arch.aria.contractRoute': 'Contract direction',
      'arch.aria.runtimeRail': 'Runtime lifecycle',
      'arch.aria.layerSelection': 'Runtime layer selection',
      'arch.aria.footerLinks': 'Architecture destinations'
    },
    zh: {
      'arch.hero.eyebrow': '当前架构配套视图',
      'arch.hero.source': '从源头',
      'arch.hero.title': '到运行时',
      'arch.hero.lede': '一张垂直地图：人编写什么，工具编译或分发什么，代理交换什么，运行时控制什么，以及证据如何返回。',
      'arch.hero.guardrail': '请自上而下阅读权威流。生成面指回可编辑源，但不会成为新的事实源。',
      'arch.fact.seeds': '清单种子',
      'arch.fact.runtime': '可执行运行时',
      'arch.fact.layers': '代理层级',
      'arch.fact.references': '领域参考',
      'arch.fact.budgets': '上下文预算',
      'arch.link.system': '系统',
      'arch.link.seeds': '种子库 ↗',
      'arch.link.harness': '评估体系',
      'arch.link.skill': '阅读 SKILL ↗',
      'arch.link.design': '设计体系',
      'arch.link.visualizer': '工作流可视化',
      'arch.companions.label': '系统配套页面',
      'arch.flow.title': '当前的源头 → 契约 → 运行时 → 证据流',
      'arch.flow.desc': '本图按职责分组，而不是穷举文件。每一层都标出权威输入及其流向的边界。',
      'arch.flow.authoring.kicker': '可编辑源',
      'arch.flow.authoring.title': '编写源',
      'arch.flow.authoring.body': 'SKILL 定义面向操作者的编排；manifest 拥有 32 个参考文件的安装集合；registry 拥有 27 个清单种子（包括 retro-digest）；context profiles 拥有 5K / 5K / 8K 分层预算；schemas 拥有消息形状；.rules/*.mdc 拥有治理规则正文。',
      'arch.inventory.summary': '浏览 32 个参考 + 6 个知识文件',
      'arch.inventory.desc': '这个紧凑清单由页面中的同一份数据渲染，并与安装 manifest 和磁盘上的知识目录进行一致性检查。',
      'arch.inventory.filterLabel': '筛选源路径',
      'arch.inventory.filterPlaceholder': '输入名称或路径',
      'arch.inventory.references': '二级参考 · 32',
      'arch.inventory.knowledge': '三级知识 · 6',
      'arch.inventory.status': '正在显示 {shown}/{total} 个文件',
      'arch.flow.compiled.kicker': '生成与分发',
      'arch.flow.compiled.title': '编译与分发表面',
      'arch.flow.compiled.body': '规则编译器把 .rules/ 渲染为 AGENTS.md、按需加载的 Cursor repo-governance 表面和 Style 参考文档。安装 manifest 为各宿主选择 SKILL、32 个参考与示例。这些输出是生成视图，不是可编辑的规则源。',
      'arch.flow.contracts.kicker': '类型化边界',
      'arch.flow.contracts.title': '契约',
      'arch.flow.contracts.body': '精简 TaskDispatch 向下携带目标、文件所有权、验收标准、有边界的门控和可选变更上下文；精简 StatusReport 向上携带制品、逐项结果、指标、关注点和自检证据。路径、ID、错误与指标保持原文。',
      'arch.flow.contracts.down': 'Project → Wave → Task',
      'arch.flow.contracts.up': 'Task → Wave → Project',
      'arch.flow.runtime.kicker': '可执行控制',
      'arch.flow.runtime.title': '运行时',
      'arch.flow.runtime.body': 'TemplateRegistry.load_seed(name) 把 27 个种子之一（包括 retro-digest）转成清单分解知识。种子的 source_stages 字段只记录来源，不安排工作。TemplateRegistry.load_template("change-driven") 加载 templates/builtin/change-driven.yaml；它是唯一可执行生命周期，负责签署预检、有边界清单轮次、证据门控与归档。',
      'arch.runtime.propose': '提出变更',
      'arch.runtime.preflight': '预检',
      'arch.runtime.round': '有边界轮次',
      'arch.runtime.archive': '受保护归档',
      'arch.flow.evidence.kicker': '可测量返回路径',
      'arch.flow.evidence.title': '证据',
      'arch.flow.harness.title': '评估体系',
      'arch.flow.evidence.body': '派发遥测在只追加 JSONL 中记录实测令牌、预算、约束数量、可量化比率、层级归属与轮次上下文。内置评估体系汇总台账和确定性的仓库信号，形成六个 W-3 维度，再输出 READY、NOT_READY 或明确的 INSUFFICIENT。',
      'arch.flow.evidence.note': '调优提案保持不可变并由哈希绑定。应用提案需要独立、明确的批准制品；评估本身绝不会修改运行时配置。',
      'arch.flow.human.kicker': '可读投影',
      'arch.flow.human.title': '面向人的输出',
      'arch.flow.human.body': '人确认目标、清单断言、预检授权和提案批准。面向人的摘要、收敛报告、指南和本演示把当前契约投影为可评审输出，但不会成为运行时事实源。',
      'arch.layers.title': '选择一个运行时层级',
      'arch.layers.desc': '选择器严格只有三个状态。每个状态展示该层的上下文预算、权限、证据责任与实现边界。',
      'arch.layer.project': '项目层',
      'arch.layer.wave': '波次层',
      'arch.layer.task': '任务层',
      'arch.layer.receives': '接收',
      'arch.layer.controls': '控制',
      'arch.layer.boundary': '边界',
      'arch.layer.project.title': '拥有轮次决策权',
      'arch.layer.project.receives': '用户目标、清单、预检、轮次状态与有边界的证据摘要。',
      'arch.layer.project.controls': '轮次选择、Wave 分区、门控、强化、检查点、归档与面向人的汇报。',
      'arch.layer.project.boundary': '派发已委派工作；绝不亲自实现，也不以分数替代逐项证据。',
      'arch.layer.wave.title': '协调一个有边界的分区',
      'arch.layer.wave.receives': '选定任务列表、依赖图、所有权图与前置证据摘要。',
      'arch.layer.wave.controls': '冲突检查、写入范围互斥的 Task 派发，以及清单项级证据汇总。',
      'arch.layer.wave.boundary': '最多派发五个 Task；绝不编辑 Task 输出，也不直接勾选清单项。',
      'arch.layer.task.title': '实现一个原子任务',
      'arch.layer.task.receives': '一份 TaskDispatch、可写与只读路径、相关契约、规则和有边界的前置事实。',
      'arch.layer.task.controls': '授权文件变更、有边界的自检，以及携带证据的精简 StatusReport。',
      'arch.layer.task.boundary': '唯一实现层；绝不派生代理、自行评分或越过文件所有权。',
      'arch.truths.title': '防止漂移的三个区分',
      'arch.truths.desc': '只有把知识、可执行控制与生成投影分开，架构才始终易懂。',
      'arch.truth.seed.title': '种子 ≠ 运行时',
      'arch.truth.seed.body': '种子贡献清单分解知识。source_stages 保留知识来源；只有 change-driven 执行生命周期。',
      'arch.truth.rule.title': '编译 ≠ 编写',
      'arch.truth.rule.body': '治理修改始于 .rules/*.mdc。AGENTS.md、repo-governance.mdc 与 STYLE-RULES.md 是受漂移检查保护的编译输出。',
      'arch.truth.evidence.title': '证据 ≠ 判定捷径',
      'arch.truth.evidence.body': '清单项级检查与制品决定轮次完成。评估维度与综合值支持发布就绪判断；输入缺失时保持 INSUFFICIENT。',
      'arch.aria.facts': '当前架构事实',
      'arch.aria.heroLinks': '架构链接',
      'arch.aria.companions': '系统配套页面',
      'arch.aria.authoringPaths': '编写源路径',
      'arch.aria.contractRoute': '契约方向',
      'arch.aria.runtimeRail': '运行时生命周期',
      'arch.aria.layerSelection': '运行时层级选择',
      'arch.aria.footerLinks': '架构目的地'
    }
  };

  var layerOrder = ['project', 'wave', 'task'];

  function translate(key) {
    return typeof window.t === 'function' ? window.t(key) : key;
  }

  function registerTranslations() {
    if (typeof window.addTranslations !== 'function') {
      console.error('DevolaFlow Design Architecture could not register translations.');
      return;
    }
    window.addTranslations('en', translations.en);
    window.addTranslations('zh', translations.zh);
  }

  function applyAriaTranslations() {
    document.querySelectorAll('[data-arch-aria]').forEach(function (element) {
      element.setAttribute('aria-label', translate(element.dataset.archAria));
    });
  }

  function renderInventoryList(container, entries, query) {
    var shown = 0;
    container.replaceChildren();

    entries.forEach(function (entry) {
      if (query && entry.path.toLowerCase().indexOf(query) === -1) {
        return;
      }
      var item = document.createElement('li');
      var path = document.createElement('code');
      path.textContent = entry.path;
      item.appendChild(path);
      container.appendChild(item);
      shown += 1;
    });

    return shown;
  }

  function renderInventory() {
    var filter = document.getElementById('architecture-inventory-filter');
    var references = document.getElementById('reference-inventory');
    var knowledge = document.getElementById('knowledge-inventory');
    var status = document.getElementById('architecture-inventory-status');
    if (!filter || !references || !knowledge || !status) {
      console.error('DevolaFlow Design Architecture inventory controls are incomplete.');
      return;
    }

    var query = filter.value.trim().toLowerCase();
    var shown = renderInventoryList(references, referenceInventory, query);
    shown += renderInventoryList(knowledge, knowledgeInventory, query);
    status.textContent = translate('arch.inventory.status')
      .replace('{shown}', String(shown))
      .replace('{total}', String(referenceInventory.length + knowledgeInventory.length));
  }

  function initInventory() {
    var filter = document.getElementById('architecture-inventory-filter');
    if (!filter) {
      console.error('DevolaFlow Design Architecture inventory filter is unavailable.');
      return;
    }
    filter.addEventListener('input', renderInventory);
    renderInventory();
  }

  function selectLayer(layer) {
    if (layerOrder.indexOf(layer) === -1) {
      console.error('Unknown Design Architecture layer selection:', layer);
      return;
    }

    document.querySelectorAll('[data-layer-select]').forEach(function (button) {
      var selected = button.dataset.layerSelect === layer;
      button.classList.toggle('is-active', selected);
      button.setAttribute('aria-pressed', selected ? 'true' : 'false');
    });

    document.querySelectorAll('[data-layer-panel]').forEach(function (panel) {
      var selected = panel.dataset.layerPanel === layer;
      panel.classList.toggle('is-active', selected);
      panel.hidden = !selected;
    });
  }

  function initLayerSelector() {
    var buttons = Array.from(document.querySelectorAll('[data-layer-select]'));
    buttons.forEach(function (button) {
      button.addEventListener('click', function () {
        selectLayer(button.dataset.layerSelect);
      });

      button.addEventListener('keydown', function (event) {
        var currentIndex = layerOrder.indexOf(button.dataset.layerSelect);
        var nextIndex = currentIndex;

        if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
          nextIndex = (currentIndex + 1) % layerOrder.length;
        } else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
          nextIndex = (currentIndex - 1 + layerOrder.length) % layerOrder.length;
        } else if (event.key === 'Home') {
          nextIndex = 0;
        } else if (event.key === 'End') {
          nextIndex = layerOrder.length - 1;
        } else {
          return;
        }

        event.preventDefault();
        selectLayer(layerOrder[nextIndex]);
        buttons[nextIndex].focus();
      });
    });

    selectLayer(layerOrder[0]);
  }

  function init() {
    registerTranslations();
    document.documentElement.dataset.skillSourceLines = String(sourceFacts.skill.lines);
    document.documentElement.dataset.seedCatalogPath = sourceFacts.seedCatalog.path;
    document.documentElement.dataset.seedCatalogCount = String(sourceFacts.seedCatalog.count);
    document.documentElement.dataset.requiredSeed = sourceFacts.seedCatalog.requiredSeed;
    applyAriaTranslations();
    initInventory();
    initLayerSelector();

    document.addEventListener('devolaflow:languagechange', function () {
      applyAriaTranslations();
      renderInventory();
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
