/**
 * Canonical System page.
 * Registers page-local EN/ZH copy, exposes keyboard-native layer disclosures,
 * and advances one round through exactly four manually triggered states.
 */
(function () {
  'use strict';

  var translations = {
    en: {
      'system.hero.eyebrow': 'Canonical system model',
      'system.hero.title': 'System',
      'system.hero.lede': 'One change-driven runtime turns a user-confirmed checklist into bounded rounds of delegated work, evidence, and decisions.',
      'system.hero.guardrail': 'Seeds suggest decomposition. They never prescribe execution order.',
      'system.fact.runtime': 'Runtime',
      'system.fact.layers': 'Layers',
      'system.fact.loop': 'Loop',
      'system.fact.loop.value': 'bounded checklist rounds',
      'system.cta.design': 'Design system',
      'system.cta.io': 'Explore I/O',
      'system.cta.timeline': 'View timeline',
      'system.cta.skill': 'Read SKILL ↗',
      'system.companions.label': 'System companions',
      'system.companion.design': 'Design system',
      'system.companion.architecture': 'Design architecture',
      'system.companion.visualizer': 'Workflow visualizer',
      'system.hierarchy.title': 'Three layers, one implementation boundary',
      'system.hierarchy.desc': 'Project and Wave are dispatchers, not implementers. Only Task performs the assigned work; every layer receives a deliberately small context.',
      'system.layer.project': 'Project',
      'system.layer.project.role': 'Round orchestrator and evidence adjudicator',
      'system.layer.wave': 'Wave',
      'system.layer.wave.role': 'Bounded task coordinator',
      'system.layer.task': 'Task',
      'system.layer.task.role': 'Fresh-context leaf implementer',
      'system.layer.inspect': 'Inspect boundary',
      'system.layer.mustnot': 'Must not:',
      'system.layer.project.does': 'Owns goal, checklist, preflight, priority selection, gate decisions, reinforcement, checkpoints, and human reporting.',
      'system.layer.project.not': 'implement delegated output, run delegated checks, or substitute a score for evidence.',
      'system.layer.wave.does': 'Validates dependencies and disjoint ownership, dispatches up to five Tasks, checks conflicts, and aggregates item-level evidence.',
      'system.layer.wave.not': 'perform Task work, alter Task artifacts, or mark checklist items complete.',
      'system.layer.task.does': 'Implements one atomic assignment, modifies only owned files, self-verifies, and returns a lean StatusReport with observable evidence.',
      'system.layer.task.not': 'spawn agents, self-award a score, mark checklist items complete, or exceed ownership.',
      'system.boundary.name': 'Dispatcher-not-implementer',
      'system.boundary.flow': 'Dispatch moves Project → Wave → Task. Evidence returns Task → Wave → Project. Escalation continues upward to the human.',
      'system.rounds.title': 'From intent to archive',
      'system.rounds.desc': 'The seed shapes a checklist; the sole runtime advances only through bounded, evidence-backed round decisions.',
      'system.round.seed.title': 'Select a seed',
      'system.round.seed.body': 'L0 maps user intent to registered decomposition knowledge with TemplateRegistry.load_seed(name), then loads the change-driven runtime. Seed labels remain provenance, not a schedule.',
      'system.round.anchor.title': 'Anchor the contract',
      'system.round.anchor.body': 'The user confirms goal.md, checklist.md, and preflight.md: assertions, P0/P1/P2 priorities, dependencies, ownership, verification recipes, and execution authorization.',
      'system.round.select.title': 'Select the next round',
      'system.round.select.body': 'L0 orders open work by reverted blockers → P0 → P1 → P2 → satisfied dependencies → stable checklist order. The selection is finite and recorded.',
      'system.round.wave.title': 'Partition and dispatch Wave work',
      'system.round.wave.body': 'L0 partitions the selection into no more than seven Waves. L1 validates each Wave and dispatches no more than five pairwise-disjoint Tasks.',
      'system.round.task.title': 'Converge inside each Task',
      'system.round.task.body': 'L2 runs a declared implement → review → fix → re-review loop within max_iterations, then stops with success, concerns, or escalation. It never continues indefinitely.',
      'system.round.evidence.title': 'Return evidence, not self-certification',
      'system.round.evidence.body': 'Task emits item-keyed checks and artifacts; Wave preserves exact command and metric facts, checks conflicts, and submits an evidence proposal to Project.',
      'system.round.gate.title': 'Apply the L0 evidence gate',
      'system.round.gate.body': 'Project verifies every selected item, configured checks, reinforcement closure, zero blockers, and zero unresolved ownership or interface conflicts before a round can PASS.',
      'system.round.decision.title': 'Reinforce or checkpoint',
      'system.round.decision.body': 'FAIL produces up to five severity-filtered reinforcement rules for the next bounded round. PASS creates a convergence_round_complete checkpoint and selects remaining work.',
      'system.round.archive.title': 'Archive only a complete change',
      'system.round.archive.body': 'After every checklist item is checked, evidence and preflight references validate, mergeability passes, and release-readiness is sufficient, L0 may archive the change and propose source-of-truth updates.',
      'system.sim.title': 'Advance one bounded round',
      'system.sim.desc': 'Use the controls to move through four explicit states. Nothing auto-runs, auto-restarts, or creates an unbounded loop.',
      'system.sim.bound': 'Manual · 4 states · bounded',
      'system.sim.anchored': 'anchored',
      'system.sim.dispatched': 'dispatched',
      'system.sim.evidenced': 'evidenced',
      'system.sim.checked': 'checked',
      'system.sim.advance': 'Advance state',
      'system.sim.reset': 'Reset round',
      'system.sim.complete': 'Round state complete',
      'system.sim.status.anchored': 'State 1 of 4 — anchored',
      'system.sim.status.dispatched': 'State 2 of 4 — dispatched',
      'system.sim.status.evidenced': 'State 3 of 4 — evidenced',
      'system.sim.status.checked': 'State 4 of 4 — checked',
      'system.sim.readout.anchored.label': 'Contract locked',
      'system.sim.readout.anchored.body': 'goal.md, checklist.md, and preflight.md define the authorized work.',
      'system.sim.readout.dispatched.label': 'Ownership routed',
      'system.sim.readout.dispatched.body': 'Project selects the round, Wave validates the partition, and Task receives one bounded assignment.',
      'system.sim.readout.evidenced.label': 'Facts returned',
      'system.sim.readout.evidenced.body': 'Task reports observable checks; Wave checks conflicts and proposes item-level evidence.',
      'system.sim.readout.checked.label': 'L0 decision point',
      'system.sim.readout.checked.body': 'Project verifies evidence, checks, reinforcement, and blockers. PASS may checkpoint; FAIL must reinforce or escalate.',
      'system.gate.title': 'What decides PASS',
      'system.gate.desc': 'Round completion and release readiness are related decisions with different evidence obligations.',
      'system.gate.round.title': 'Round PASS',
      'system.gate.round.body': 'All selected checklist items have valid evidence and passing configured checks; reinforcement is accounted for; there are zero blockers and no unresolved ownership or interface conflicts.',
      'system.gate.composite.title': 'Composite signal',
      'system.gate.composite.body': 'The composite is recorded as trend context during rounds and used for release-readiness at archive. It never replaces item evidence, checks, or blocker closure.',
      'system.gate.failure.title': 'A failed round has a ceiling.',
      'system.gate.failure.body': 'L0 carries actionable findings forward as reinforcement. When max rounds are reached or progress stagnates, execution escalates upward instead of continuing autonomously.',
      'system.companions.title': 'Secondary System views',
      'system.companions.desc': 'These stable routes provide supporting views. This page remains the canonical current-state explanation.',
      'system.companion.design.desc': 'Tokens, typography, components, and motion vocabulary.',
      'system.companion.architecture.desc': 'A supporting architectural lens on the product model.',
      'system.companion.visualizer.desc': 'A compatibility visualization for inspecting workflow concepts.',
      'system.footer.io': 'Next: I/O',
      'system.footer.timeline': 'History: Timeline',
      'system.aria.facts': 'System facts',
      'system.aria.links': 'System page links',
      'system.aria.companions': 'System companions',
      'system.aria.states': 'Bounded round states'
    },
    zh: {
      'system.hero.eyebrow': '规范系统模型',
      'system.hero.title': '系统',
      'system.hero.lede': '唯一的 change-driven 运行时，将用户确认的清单转化为有边界的委派、证据与决策轮次。',
      'system.hero.guardrail': '种子只建议如何分解，不规定执行顺序。',
      'system.fact.runtime': '运行时',
      'system.fact.layers': '层级',
      'system.fact.loop': '循环',
      'system.fact.loop.value': '有边界的清单轮次',
      'system.cta.design': '设计体系',
      'system.cta.io': '探索输入输出',
      'system.cta.timeline': '查看时间线',
      'system.cta.skill': '阅读 SKILL ↗',
      'system.companions.label': '系统配套页面',
      'system.companion.design': '设计体系',
      'system.companion.architecture': '设计架构',
      'system.companion.visualizer': '工作流可视化',
      'system.hierarchy.title': '三层结构，一条实现边界',
      'system.hierarchy.desc': 'Project 与 Wave 只负责派发，不负责实现。只有 Task 执行分配的工作；每层都只接收刻意压缩的上下文。',
      'system.layer.project': '项目层',
      'system.layer.project.role': '轮次编排与证据裁决',
      'system.layer.wave': '波次层',
      'system.layer.wave.role': '有边界的任务协调',
      'system.layer.task': '任务层',
      'system.layer.task.role': '全新上下文中的叶子实现者',
      'system.layer.inspect': '查看边界',
      'system.layer.mustnot': '禁止：',
      'system.layer.project.does': '负责目标、清单、预检、优先级选择、门控决策、强化规则、检查点与面向人的汇报。',
      'system.layer.project.not': '实现已委派产物、运行已委派检查，或用分数代替证据。',
      'system.layer.wave.does': '校验依赖与互斥写入范围，派发最多五个 Task，检查冲突，并汇总到清单项级别的证据。',
      'system.layer.wave.not': '执行 Task 工作、修改 Task 产物，或直接勾选清单项。',
      'system.layer.task.does': '实现一个原子任务，只修改被授权文件，自行校验，并用精简 StatusReport 返回可观察证据。',
      'system.layer.task.not': '派生代理、自行评分、勾选清单项，或越过文件所有权。',
      'system.boundary.name': '派发者不实现',
      'system.boundary.flow': '派发沿 Project → Wave → Task 向下；证据沿 Task → Wave → Project 返回；升级继续向上到人。',
      'system.rounds.title': '从意图到归档',
      'system.rounds.desc': '种子塑造清单；唯一运行时只通过有边界、以证据为依据的轮次决策推进。',
      'system.round.seed.title': '选择种子',
      'system.round.seed.body': 'L0 通过 TemplateRegistry.load_seed(name) 将用户意图映射为已注册的分解知识，再加载 change-driven 运行时。种子标签只保留来源含义，不是日程表。',
      'system.round.anchor.title': '锚定契约',
      'system.round.anchor.body': '用户确认 goal.md、checklist.md 与 preflight.md：断言、P0/P1/P2 优先级、依赖、所有权、验证方法和执行授权。',
      'system.round.select.title': '选择下一轮',
      'system.round.select.body': 'L0 按“被撤回的阻塞项 → P0 → P1 → P2 → 已满足依赖 → 清单稳定顺序”选择开放工作；选择是有限且有记录的。',
      'system.round.wave.title': '分区并派发 Wave 工作',
      'system.round.wave.body': 'L0 将所选工作划分为不超过七个 Wave；L1 校验每个 Wave，并派发不超过五个写入范围互斥的 Task。',
      'system.round.task.title': '在每个 Task 内收敛',
      'system.round.task.body': 'L2 在 max_iterations 内运行明确的“实现 → 评审 → 修复 → 再评审”循环，然后以成功、存疑或升级结束，绝不无限继续。',
      'system.round.evidence.title': '返回证据，而非自我认证',
      'system.round.evidence.body': 'Task 输出按清单项索引的检查与产物；Wave 保留准确的命令和指标事实，检查冲突，再向 Project 提交证据提案。',
      'system.round.gate.title': '执行 L0 证据门控',
      'system.round.gate.body': '只有 Project 验证每个所选清单项、已配置检查、强化闭环、零阻塞项及零未解决所有权或接口冲突后，轮次才能通过。',
      'system.round.decision.title': '强化或建立检查点',
      'system.round.decision.body': '失败会为下一轮生成最多五条按严重度筛选的强化规则；通过会创建 convergence_round_complete 检查点，并选择剩余工作。',
      'system.round.archive.title': '只归档完整变更',
      'system.round.archive.body': '当所有清单项已勾选、证据和预检引用有效、可合并检查通过且发布就绪度充分后，L0 才可归档变更并提出事实源更新。',
      'system.sim.title': '推进一个有边界的轮次',
      'system.sim.desc': '使用控件经过四个明确状态。页面不会自动运行、自动重启，也不会制造无边界循环。',
      'system.sim.bound': '手动 · 4 个状态 · 有边界',
      'system.sim.anchored': '已锚定',
      'system.sim.dispatched': '已派发',
      'system.sim.evidenced': '已有证据',
      'system.sim.checked': '已检查',
      'system.sim.advance': '推进状态',
      'system.sim.reset': '重置轮次',
      'system.sim.complete': '轮次状态已完成',
      'system.sim.status.anchored': '状态 1/4 — 已锚定',
      'system.sim.status.dispatched': '状态 2/4 — 已派发',
      'system.sim.status.evidenced': '状态 3/4 — 已有证据',
      'system.sim.status.checked': '状态 4/4 — 已检查',
      'system.sim.readout.anchored.label': '契约已锁定',
      'system.sim.readout.anchored.body': 'goal.md、checklist.md 与 preflight.md 定义获授权的工作。',
      'system.sim.readout.dispatched.label': '所有权已路由',
      'system.sim.readout.dispatched.body': 'Project 选择轮次，Wave 校验分区，Task 接收一个有边界的任务。',
      'system.sim.readout.evidenced.label': '事实已返回',
      'system.sim.readout.evidenced.body': 'Task 汇报可观察检查；Wave 检查冲突并提出清单项级证据。',
      'system.sim.readout.checked.label': 'L0 决策点',
      'system.sim.readout.checked.body': 'Project 验证证据、检查、强化与阻塞项。通过可建立检查点；失败必须强化或升级。',
      'system.gate.title': '什么决定通过',
      'system.gate.desc': '轮次完成与发布就绪是两个相关但证据义务不同的决策。',
      'system.gate.round.title': '轮次通过',
      'system.gate.round.body': '所有所选清单项都有有效证据且配置检查通过；强化事项已处理；阻塞项为零，且没有未解决的所有权或接口冲突。',
      'system.gate.composite.title': '综合信号',
      'system.gate.composite.body': '综合分在轮次中只记录为趋势背景，在归档时用于发布就绪度；它绝不替代清单项证据、检查或阻塞闭环。',
      'system.gate.failure.title': '失败轮次有明确上限。',
      'system.gate.failure.body': 'L0 将可执行发现作为强化规则带入后续轮次。达到最大轮次或进展停滞时，执行会向上升级，而不是自主持续。',
      'system.companions.title': '系统的次级视图',
      'system.companions.desc': '这些稳定路由提供辅助视角；本页仍是当前系统状态的规范说明。',
      'system.companion.design.desc': '设计令牌、字体、组件与动效语言。',
      'system.companion.architecture.desc': '从架构角度辅助理解产品模型。',
      'system.companion.visualizer.desc': '用于查看工作流概念的兼容可视化页面。',
      'system.footer.io': '下一页：输入输出',
      'system.footer.timeline': '历史：时间线',
      'system.aria.facts': '系统事实',
      'system.aria.links': '系统页面链接',
      'system.aria.companions': '系统配套页面',
      'system.aria.states': '有边界的轮次状态'
    }
  };

  var roundStates = ['anchored', 'dispatched', 'evidenced', 'checked'];
  var roundIndex = 0;

  function translate(key) {
    return typeof window.t === 'function' ? window.t(key) : key;
  }

  function registerTranslations() {
    if (typeof window.addTranslations !== 'function') {
      console.error('DevolaFlow System page could not register translations.');
      return;
    }
    window.addTranslations('en', translations.en);
    window.addTranslations('zh', translations.zh);
  }

  function applyAriaTranslations() {
    document.querySelectorAll('[data-system-aria]').forEach(function (element) {
      element.setAttribute('aria-label', translate(element.dataset.systemAria));
    });
  }

  function initLayerDisclosures() {
    var controls = document.querySelectorAll('[data-layer-control]');
    controls.forEach(function (control) {
      control.addEventListener('click', function () {
        var willOpen = control.getAttribute('aria-expanded') !== 'true';

        controls.forEach(function (other) {
          var panel = document.getElementById(other.getAttribute('aria-controls'));
          other.setAttribute('aria-expanded', 'false');
          if (panel) { panel.hidden = true; }
        });

        var target = document.getElementById(control.getAttribute('aria-controls'));
        control.setAttribute('aria-expanded', willOpen ? 'true' : 'false');
        if (target) { target.hidden = !willOpen; }
      });
    });
  }

  function renderRound() {
    var state = roundStates[roundIndex];
    var status = document.getElementById('simulator-status');
    var label = document.getElementById('simulator-readout-label');
    var readout = document.getElementById('simulator-readout');
    var advance = document.getElementById('simulator-advance');

    document.querySelectorAll('[data-round-step]').forEach(function (step, index) {
      var isCurrent = index === roundIndex;
      step.classList.toggle('is-current', isCurrent);
      step.classList.toggle('is-complete', index < roundIndex);
      if (isCurrent) {
        step.setAttribute('aria-current', 'step');
      } else {
        step.removeAttribute('aria-current');
      }
    });

    if (status) { status.textContent = translate('system.sim.status.' + state); }
    if (label) { label.textContent = translate('system.sim.readout.' + state + '.label'); }
    if (readout) { readout.textContent = translate('system.sim.readout.' + state + '.body'); }
    if (advance) {
      advance.disabled = roundIndex === roundStates.length - 1;
      advance.textContent = translate(advance.disabled ? 'system.sim.complete' : 'system.sim.advance');
    }
  }

  function initRoundSimulator() {
    var advance = document.getElementById('simulator-advance');
    var reset = document.getElementById('simulator-reset');

    if (advance) {
      advance.addEventListener('click', function () {
        if (roundIndex < roundStates.length - 1) {
          roundIndex += 1;
          renderRound();
        }
      });
    }

    if (reset) {
      reset.addEventListener('click', function () {
        roundIndex = 0;
        renderRound();
      });
    }

    renderRound();
  }

  function init() {
    registerTranslations();
    applyAriaTranslations();
    initLayerDisclosures();
    initRoundSimulator();

    document.addEventListener('devolaflow:languagechange', function () {
      applyAriaTranslations();
      renderRound();
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
