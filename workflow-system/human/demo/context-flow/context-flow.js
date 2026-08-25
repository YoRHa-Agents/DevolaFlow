/**
 * Context Flow — page-local translations and finite I/O stepper.
 * The control is user-driven: no timer, autoplay, or unbounded loop.
 */
(function () {
  'use strict';

  if (typeof window.addTranslations !== 'function') {
    console.error('[context-flow] shared i18n did not expose addTranslations');
    return;
  }

  var EN = {
    'cf.hero.eyebrow': 'Canonical I/O',
    'cf.hero.inputs': 'Inputs',
    'cf.hero.runtime': 'Runtime I/O',
    'cf.hero.outputs': 'Outputs',
    'cf.hero.tagline': 'See exactly what people author, what agents exchange, and what returns for a human decision.',
    'cf.hero.note': 'Contract view · user-controlled · no live telemetry',
    'cf.cta.system': 'Open System',
    'cf.cta.harness': 'Open Harness',
    'cf.boundaries.title': 'Three boundaries, one auditable flow',
    'cf.boundaries.desc': 'Human intent enters once. Runtime artifacts and typed messages carry the work. Only bounded conclusions return.',
    'cf.zone.input.kind': 'Human-authored INPUT',
    'cf.zone.input.title': 'Inputs',
    'cf.zone.input.desc': 'Durable intent and constraints are binding context; they are not agent progress logs.',
    'cf.zone.input.intent': 'Human intent',
    'cf.zone.input.intentDesc': 'request, constraints, and approval',
    'cf.zone.input.anchorKind': 'Agent runtime anchors',
    'cf.zone.input.anchorNote': 'L0 drafts these from confirmed intent. They are runtime artifacts, not human-authored INPUT.',
    'cf.zone.runtime.kind': 'Agent runtime artifacts',
    'cf.zone.runtime.title': 'Runtime I/O',
    'cf.zone.runtime.desc': 'Typed, repository-relative messages cross layer boundaries; files carry durable evidence.',
    'cf.zone.runtime.dispatch': 'down Project → Wave → Task',
    'cf.zone.runtime.status': 'Task evidence returned to Wave',
    'cf.zone.runtime.wave': 'aggregated evidence returned to Project',
    'cf.zone.runtime.escalation': 'bounded failure routed upward',
    'cf.zone.runtime.evidence': 'checks, command results, and artifact deltas',
    'cf.zone.runtime.checkpoint': 'checkpoint',
    'cf.zone.runtime.checkpointDesc': 'passing round state',
    'cf.zone.runtime.ledger': 'harness ledger',
    'cf.zone.runtime.ledgerDesc': 'cross-change evaluation input',
    'cf.zone.output.kind': 'Bounded human OUTPUT',
    'cf.zone.output.title': 'Outputs',
    'cf.zone.output.desc': 'The human receives a concise conclusion and only the decisions that require human authority.',
    'cf.zone.output.digest': 'read-first state summary',
    'cf.zone.output.convergence': 'requirement-keyed evidence',
    'cf.zone.output.decision': 'Decision request',
    'cf.zone.output.decisionDesc': 'only after Project cannot resolve an escalation',
    'cf.zone.output.completion': 'Completion summary',
    'cf.zone.output.completionDesc': 'outcome, evidence, and next action',
    'cf.flow.title': 'Follow the contract',
    'cf.flow.desc': 'Choose a finite step. Nothing advances on its own, and Reset always returns to the input boundary.',
    'cf.tab.input': 'Anchor inputs',
    'cf.tab.dispatch': 'Dispatch down',
    'cf.tab.report': 'Evidence up',
    'cf.tab.gate': 'Gate & checkpoint',
    'cf.tab.escalation': 'Escalate upward',
    'cf.tab.output': 'Return outputs',
    'cf.panel.input.direction': 'INPUT · Human → L0 Project',
    'cf.panel.input.title': 'Confirm intent before runtime work',
    'cf.panel.input.desc': 'L0 turns the request into a goal, checklist item IDs, and a signed preflight. The human owns intent; L0 owns the runtime anchors.',
    'cf.node.author': 'Author',
    'cf.node.human': 'Human',
    'cf.node.project': 'Project',
    'cf.node.wave': 'Wave',
    'cf.node.task': 'Task',
    'cf.node.authority': 'Authority',
    'cf.route.intent': 'intent + approval',
    'cf.route.taskEvidence': 'evidence + StatusReport',
    'cf.panel.dispatch.direction': 'DISPATCH DOWN · L0 → L1 → L2',
    'cf.panel.dispatch.title': 'TaskDispatch narrows context at each boundary',
    'cf.panel.dispatch.desc': 'Project selects a bounded wave; Wave sends atomic, disjoint work to Task. L2 receives only authorized files, relevant contracts, and checklist-derived acceptance.',
    'cf.message.lean': 'lean YAML · current concepts',
    'cf.panel.report.direction': 'EVIDENCE & REPORT UP · L2 → L1 → L0',
    'cf.panel.report.title': 'Evidence rises; implementation details stay scoped',
    'cf.panel.report.desc': 'Task emits StatusReport with falsifiable evidence. Wave checks conflicts and aggregates a WaveReport. Project adjudicates checklist progress.',
    'cf.message.evidence': 'evidence, not self-scoring',
    'cf.panel.gate.direction': 'RUNTIME CONTROL · evidence → gate → checkpoint',
    'cf.panel.gate.title': 'A passing round requires item-level proof',
    'cf.panel.gate.desc': 'L0 checks selected checklist IDs, configured commands, blocker closure, and ownership conflicts before writing a checkpoint or choosing a bounded next round.',
    'cf.panel.gate.evidence': 'verbatim command and artifact evidence',
    'cf.panel.gate.checklist': 'Checklist gate',
    'cf.panel.gate.checklistDesc': 'IO-1…IO-4 checked independently',
    'cf.panel.gate.checkpoint': 'checkpoint',
    'cf.panel.gate.checkpointDesc': 'only after the selected round passes',
    'cf.panel.gate.harness': 'harness ledger',
    'cf.panel.gate.harnessDesc': 'telemetry retained for cross-change evaluation; not a fake live feed',
    'cf.panel.escalation.direction': 'ESCALATION UP · Task → Wave → Project → Human',
    'cf.panel.escalation.title': 'Failures are classified and routes never skip a layer',
    'cf.panel.escalation.desc': 'Recoverable failures retry only within the declared ceiling. Blocking or fatal failures become an EscalationEvent and move upward until resolved.',
    'cf.panel.escalation.recoverable': 'bounded retry inside Task',
    'cf.panel.escalation.blocking': 'contract or dependency resolution through L1 and L0',
    'cf.panel.escalation.fatal': 'stop the round; Project requests human authority',
    'cf.panel.output.direction': 'OUTPUT · L0 Project → Human',
    'cf.panel.output.title': 'Return a conclusion, not the agent transcript',
    'cf.panel.output.desc': 'The output boundary compresses runtime evidence into a read-first digest, a requirement-keyed convergence report, and any unresolved decision.',
    'cf.panel.output.digest': 'Where we are · blocking asks · requirement rollup · next report',
    'cf.panel.output.report': 'Verdict · requirement evidence · findings · next step',
    'cf.panel.output.boundary': 'Human decision boundary',
    'cf.panel.output.boundaryDesc': 'approve, clarify, or redirect only when authority is required',
    'cf.control.previous': 'Previous',
    'cf.control.next': 'Next',
    'cf.control.reset': 'Reset',
    'cf.step.position': 'Step {current} of {total} — {label}',
    'cf.provenance.eyebrow': 'Secondary provenance I/O',
    'cf.provenance.title': 'Companion routes',
    'cf.provenance.desc': 'These routes explain design, system structure, and history. The primitive explorer preserves seed vocabulary provenance; it does not define current execution.',
    'cf.cta.designSystem': 'Design system',
    'cf.cta.designSystemDesc': 'visual tokens and components',
    'cf.cta.framework': 'Framework chain',
    'cf.cta.frameworkDesc': 'canonical System model',
    'cf.cta.timeline': 'Version timeline',
    'cf.cta.timelineDesc': 'complete historical record',
    'cf.cta.skill': 'Read SKILL.md ↗',
    'cf.cta.skillDesc': 'source contract',
    'cf.cta.explorer': 'Primitive provenance companion',
    'cf.cta.explorerDesc': 'historical seed vocabulary only',
    'cf.aria.primaryCtas': 'Primary companion pages',
    'cf.aria.steps': 'I/O contract steps',
    'cf.aria.inputRoute': 'Human intent enters Project',
    'cf.aria.anchors': 'Runtime anchor artifacts',
    'cf.aria.dispatchRoute': 'Dispatch travels from Project through Wave to Task',
    'cf.aria.reportRoute': 'Evidence and reports travel from Task through Wave to Project',
    'cf.aria.escalationRoute': 'Escalation travels from Task through Wave and Project to Human',
    'cf.aria.companions': 'I/O companion routes'
  };

  var ZH = {
    'cf.hero.eyebrow': '规范输入输出',
    'cf.hero.inputs': '输入',
    'cf.hero.runtime': '运行时 I/O',
    'cf.hero.outputs': '输出',
    'cf.hero.tagline': '清楚查看人类编写什么、代理交换什么，以及哪些内容回到人类决策边界。',
    'cf.hero.note': '契约视图 · 用户控制 · 非实时遥测',
    'cf.cta.system': '打开系统',
    'cf.cta.harness': '打开评估体系',
    'cf.boundaries.title': '三道边界，一条可审计流',
    'cf.boundaries.desc': '人类意图只进入一次。运行时制品与类型化消息承载工作，最终只返回有界结论。',
    'cf.zone.input.kind': '人类编写的输入',
    'cf.zone.input.title': '输入',
    'cf.zone.input.desc': '持久意图与约束是绑定上下文，不是代理进度日志。',
    'cf.zone.input.intent': '人类意图',
    'cf.zone.input.intentDesc': '请求、约束与批准',
    'cf.zone.input.anchorKind': '代理运行时锚点',
    'cf.zone.input.anchorNote': 'L0 根据已确认意图起草这些文件。它们是运行时制品，不是人类编写的输入。',
    'cf.zone.runtime.kind': '代理运行时制品',
    'cf.zone.runtime.title': '运行时 I/O',
    'cf.zone.runtime.desc': '类型化、仓库相对路径消息跨越层级边界；文件承载持久证据。',
    'cf.zone.runtime.dispatch': '从 Project 向下到 Wave，再到 Task',
    'cf.zone.runtime.status': 'Task 证据返回 Wave',
    'cf.zone.runtime.wave': '聚合证据返回 Project',
    'cf.zone.runtime.escalation': '有界失败向上路由',
    'cf.zone.runtime.evidence': '检查、命令结果与制品增量',
    'cf.zone.runtime.checkpoint': '检查点',
    'cf.zone.runtime.checkpointDesc': '通过的轮次状态',
    'cf.zone.runtime.ledger': '评估台账',
    'cf.zone.runtime.ledgerDesc': '跨变更评估输入',
    'cf.zone.output.kind': '有界人类输出',
    'cf.zone.output.title': '输出',
    'cf.zone.output.desc': '人类收到简洁结论，以及仅限需要人类权限的决策。',
    'cf.zone.output.digest': '阅读优先的状态摘要',
    'cf.zone.output.convergence': '按需求标识的证据',
    'cf.zone.output.decision': '决策请求',
    'cf.zone.output.decisionDesc': '仅在 Project 无法解决升级时出现',
    'cf.zone.output.completion': '完成摘要',
    'cf.zone.output.completionDesc': '结果、证据与下一步行动',
    'cf.flow.title': '沿契约逐步查看',
    'cf.flow.desc': '选择一个有限步骤。页面不会自行前进，重置始终返回输入边界。',
    'cf.tab.input': '锚定输入',
    'cf.tab.dispatch': '向下派发',
    'cf.tab.report': '证据上行',
    'cf.tab.gate': '门控与检查点',
    'cf.tab.escalation': '向上升级',
    'cf.tab.output': '返回输出',
    'cf.panel.input.direction': '输入 · Human → L0 Project',
    'cf.panel.input.title': '运行工作前先确认意图',
    'cf.panel.input.desc': 'L0 将请求转为目标、清单条目标识与已签署预检。人类拥有意图，L0 拥有运行时锚点。',
    'cf.node.author': '作者',
    'cf.node.human': '人类',
    'cf.node.project': '项目层',
    'cf.node.wave': '波次层',
    'cf.node.task': '任务层',
    'cf.node.authority': '决策权限',
    'cf.route.intent': '意图 + 批准',
    'cf.route.taskEvidence': '证据 + StatusReport',
    'cf.panel.dispatch.direction': '向下派发 · L0 → L1 → L2',
    'cf.panel.dispatch.title': 'TaskDispatch 在每道边界收窄上下文',
    'cf.panel.dispatch.desc': 'Project 选择有界波次；Wave 将原子、互斥的工作发送给 Task。L2 只接收授权文件、相关契约与由清单派生的验收条件。',
    'cf.message.lean': '精简 YAML · 当前概念',
    'cf.panel.report.direction': '证据与汇报上行 · L2 → L1 → L0',
    'cf.panel.report.title': '证据上行，实施细节保持隔离',
    'cf.panel.report.desc': 'Task 通过 StatusReport 发出可证伪证据。Wave 检查冲突并聚合 WaveReport，Project 判定清单进度。',
    'cf.message.evidence': '证据，而非自评分',
    'cf.panel.gate.direction': '运行控制 · 证据 → 门控 → 检查点',
    'cf.panel.gate.title': '轮次通过需要逐条证据',
    'cf.panel.gate.desc': '写入检查点或选择有界下一轮前，L0 检查所选清单标识、配置命令、阻断项闭合与所有权冲突。',
    'cf.panel.gate.evidence': '逐字命令与制品证据',
    'cf.panel.gate.checklist': '清单门控',
    'cf.panel.gate.checklistDesc': '独立检查 IO-1…IO-4',
    'cf.panel.gate.checkpoint': '检查点',
    'cf.panel.gate.checkpointDesc': '仅在所选轮次通过后写入',
    'cf.panel.gate.harness': '评估台账',
    'cf.panel.gate.harnessDesc': '为跨变更评估保留遥测；不是伪造的实时数据流',
    'cf.panel.escalation.direction': '向上升级 · Task → Wave → Project → Human',
    'cf.panel.escalation.title': '失败必须分类，路由不得跳层',
    'cf.panel.escalation.desc': '可恢复失败只能在声明上限内重试。阻断或致命失败成为 EscalationEvent，并逐层上移直到解决。',
    'cf.panel.escalation.recoverable': 'Task 内有界重试',
    'cf.panel.escalation.blocking': '通过 L1 与 L0 解决契约或依赖问题',
    'cf.panel.escalation.fatal': '停止轮次；Project 请求人类权限',
    'cf.panel.output.direction': '输出 · L0 Project → Human',
    'cf.panel.output.title': '返回结论，而非代理完整记录',
    'cf.panel.output.desc': '输出边界把运行时证据压缩为阅读优先摘要、按需求标识的收敛报告，以及任何未决决策。',
    'cf.panel.output.digest': '当前位置 · 阻断请求 · 需求汇总 · 最新报告',
    'cf.panel.output.report': '判定 · 需求证据 · 发现 · 下一步',
    'cf.panel.output.boundary': '人类决策边界',
    'cf.panel.output.boundaryDesc': '仅在需要权限时批准、澄清或重定向',
    'cf.control.previous': '上一步',
    'cf.control.next': '下一步',
    'cf.control.reset': '重置',
    'cf.step.position': '第 {current} / {total} 步 — {label}',
    'cf.provenance.eyebrow': '次级溯源 I/O',
    'cf.provenance.title': '配套入口',
    'cf.provenance.desc': '这些页面解释设计、系统结构与历史。原语探索器保留清单种子词汇来源，不定义当前执行。',
    'cf.cta.designSystem': '设计体系',
    'cf.cta.designSystemDesc': '视觉令牌与组件',
    'cf.cta.framework': '框架链路',
    'cf.cta.frameworkDesc': '规范系统模型',
    'cf.cta.timeline': '版本时间线',
    'cf.cta.timelineDesc': '完整历史记录',
    'cf.cta.skill': '阅读 SKILL.md ↗',
    'cf.cta.skillDesc': '源契约',
    'cf.cta.explorer': '原语溯源配套页',
    'cf.cta.explorerDesc': '仅限历史清单种子词汇',
    'cf.aria.primaryCtas': '主要配套页面',
    'cf.aria.steps': '输入输出契约步骤',
    'cf.aria.inputRoute': '人类意图进入 Project',
    'cf.aria.anchors': '运行时锚点制品',
    'cf.aria.dispatchRoute': '派发从 Project 经 Wave 到 Task',
    'cf.aria.reportRoute': '证据与汇报从 Task 经 Wave 到 Project',
    'cf.aria.escalationRoute': '升级从 Task 经 Wave、Project 到 Human',
    'cf.aria.companions': '输入输出配套入口'
  };

  function assertTranslationParity() {
    var enKeys = Object.keys(EN).sort();
    var zhKeys = Object.keys(ZH).sort();
    if (enKeys.length !== zhKeys.length || enKeys.some(function (key, index) {
      return key !== zhKeys[index];
    })) {
      console.error('[context-flow] EN/ZH page-local translation keys differ');
    }
  }

  assertTranslationParity();
  window.addTranslations('en', EN);
  window.addTranslations('zh', ZH);

  function ready(callback) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', callback);
    } else {
      callback();
    }
  }

  function translate(key) {
    return typeof window.t === 'function' ? window.t(key) : (EN[key] || key);
  }

  function translateAriaLabels() {
    document.querySelectorAll('[data-i18n-aria]').forEach(function (element) {
      element.setAttribute('aria-label', translate(element.getAttribute('data-i18n-aria')));
    });
  }

  ready(function () {
    var controller = wireFiniteStepper();
    translateAriaLabels();
    document.addEventListener('devolaflow:languagechange', function () {
      translateAriaLabels();
      if (controller) {
        controller.refresh();
      }
    });
  });

  function wireFiniteStepper() {
    var workbench = document.getElementById('io-workbench');
    var tabs = Array.prototype.slice.call(document.querySelectorAll('.io-tablist [role="tab"]'));
    var panels = Array.prototype.slice.call(document.querySelectorAll('.io-panels [role="tabpanel"]'));
    var previous = document.getElementById('io-step-prev');
    var next = document.getElementById('io-step-next');
    var reset = document.getElementById('io-step-reset');
    var status = document.getElementById('io-step-status');

    if (!workbench || !tabs.length || tabs.length !== panels.length ||
        !previous || !next || !reset || !status) {
      console.error('[context-flow] finite stepper markup is incomplete');
      return null;
    }

    var current = 0;
    var tabKeys = [
      'cf.tab.input',
      'cf.tab.dispatch',
      'cf.tab.report',
      'cf.tab.gate',
      'cf.tab.escalation',
      'cf.tab.output'
    ];

    function render(index, moveFocus) {
      current = Math.max(0, Math.min(index, tabs.length - 1));
      workbench.setAttribute('data-step', String(current));

      tabs.forEach(function (tab, tabIndex) {
        var active = tabIndex === current;
        tab.setAttribute('aria-selected', active ? 'true' : 'false');
        tab.setAttribute('tabindex', active ? '0' : '-1');
      });

      panels.forEach(function (panel, panelIndex) {
        panel.hidden = panelIndex !== current;
      });

      previous.disabled = current === 0;
      next.disabled = current === tabs.length - 1;
      status.textContent = translate('cf.step.position')
        .replace('{current}', String(current + 1))
        .replace('{total}', String(tabs.length))
        .replace('{label}', translate(tabKeys[current]));

      if (moveFocus) {
        tabs[current].focus();
      }
    }

    tabs.forEach(function (tab, index) {
      tab.addEventListener('click', function () {
        render(index, false);
      });

      tab.addEventListener('keydown', function (event) {
        var target = null;
        if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
          target = Math.min(index + 1, tabs.length - 1);
        } else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
          target = Math.max(index - 1, 0);
        } else if (event.key === 'Home') {
          target = 0;
        } else if (event.key === 'End') {
          target = tabs.length - 1;
        }

        if (target !== null) {
          event.preventDefault();
          render(target, true);
        }
      });
    });

    previous.addEventListener('click', function () {
      render(current - 1, true);
    });
    next.addEventListener('click', function () {
      render(current + 1, true);
    });
    reset.addEventListener('click', function () {
      render(0, true);
    });

    render(0, false);
    return {
      refresh: function () {
        render(current, false);
      }
    };
  }
})();
