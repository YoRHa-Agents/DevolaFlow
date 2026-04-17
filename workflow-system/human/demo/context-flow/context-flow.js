/**
 * DevolaFlow — Context Flow page
 * Registers 26 page-specific i18n keys (EN + ZH), then wires up:
 *   - Play/Pause toggle for the dispatch + report routes
 *   - Collapsible MessageEnvelope headers
 *   - 4 escalation severity buttons firing an `is-escalated` envelope
 *   - 4-state Reinforcement step machine (Round 1 -> FAIL -> findings -> Round 2)
 *
 * The shared `prefers-reduced-motion: reduce` rule in shared/styles.css
 * already neutralises animation-duration globally; nothing to override here.
 */
(function () {
  'use strict';

  /* ==================================================================
     i18n — 26 page-specific keys + supporting keys (page title, CTAs,
     table headers, cadence notes). Registered for BOTH en and zh so the
     ZH toggle never falls back to a key-shaped string.
     ================================================================== */

  if (typeof window.addTranslations !== 'function') {
    /* shared/i18n.js failed to load — surface the error explicitly
       rather than silently falling back to default text. */
    console.error('[context-flow] addTranslations unavailable; shared/i18n.js missing');
    return;
  }

  /* ----- 26 SPEC-REQUIRED page-specific keys (EN) ----- */
  var EN_REQUIRED = {
    'cf.subtitle':                            'Watch the messages travel — dispatch down, report up, escalate up, reinforce on round 2+.',
    'cf.section.dispatch':                    'Dispatch (L0 → L3)',
    'cf.section.dispatch.desc':               'TaskDispatch envelopes travel down the route track from Project to Task.',
    'cf.section.report':                      'Status Report (L3 → L0)',
    'cf.section.report.desc':                 'StatusReport envelopes travel up the route on completion or partial progress.',
    'cf.section.escalation':                  'Escalation Chain',
    'cf.section.escalation.desc':             'Always upward, never skip levels — Task → Wave → Stage → Project → Human.',
    'cf.section.reinforcement':               'Round-Reinforcement (v5.1+, wired v6.0.3)',
    'cf.section.reinforcement.desc':          'Gate FAIL → top 5 findings (≥ major) → injected into next dispatch as MUST-fix.',
    'cf.section.isolation':                   'Context Isolation',
    'cf.section.isolation.desc':              'What MUST NOT leak between agents, what IS shared via artifact summaries.',
    'cf.envelope.fields':                     'Required fields',
    'cf.envelope.example':                    'Example payload',
    'cf.escalation.severity.autoRecover':     'AUTO_RECOVER — retry up to 3× with exponential backoff',
    'cf.escalation.severity.pause':           'PAUSE — pause task, queue question, continue parallel work',
    'cf.escalation.severity.humanIntervene':  'HUMAN_INTERVENE — stop stage, present options to human',
    'cf.escalation.severity.fullRollback':    'FULL_ROLLBACK — rollback to checkpoint, halt all',
    'cf.reinforcement.step':                  'Step ▶',
    'cf.reinforcement.reset':                 'Reset',
    'cf.reinforcement.round1':                'Round 1 dispatch',
    'cf.reinforcement.round2':                'Round 2 dispatch (reinforced)',
    'cf.reinforcement.findings':              'Findings filtered by severity',
    'cf.isolation.mustNotLeak':               'MUST NOT leak',
    'cf.isolation.isShared':                  'IS shared via artifact summaries',
    'cf.play':                                'Play',
    'cf.pause':                               'Pause'
  };

  /* ----- 26 SPEC-REQUIRED page-specific keys (ZH) ----- */
  var ZH_REQUIRED = {
    'cf.subtitle':                            '看消息流动——下派、上报、上升、轮次强化。',
    'cf.section.dispatch':                    '派发（L0 → L3）',
    'cf.section.dispatch.desc':               'TaskDispatch 信封沿轨道从 Project 流向 Task。',
    'cf.section.report':                      '状态汇报（L3 → L0）',
    'cf.section.report.desc':                 'StatusReport 信封在完成或部分进度时沿轨道向上流转。',
    'cf.section.escalation':                  '升级链',
    'cf.section.escalation.desc':             '始终向上、不跳级——Task → Wave → Stage → Project → 人类。',
    'cf.section.reinforcement':               '轮次强化（v5.1+，v6.0.3 真正接通）',
    'cf.section.reinforcement.desc':          '门控 FAIL → 取前 5 条（≥ major）→ 作为 MUST-fix 注入下一轮派发。',
    'cf.section.isolation':                   '上下文隔离',
    'cf.section.isolation.desc':              '哪些不可在代理间泄露，哪些可通过制品摘要共享。',
    'cf.envelope.fields':                     '必填字段',
    'cf.envelope.example':                    '示例负载',
    'cf.escalation.severity.autoRecover':     'AUTO_RECOVER — 指数退避重试最多 3 次',
    'cf.escalation.severity.pause':           'PAUSE — 暂停任务、排队提问、并行工作继续',
    'cf.escalation.severity.humanIntervene':  'HUMAN_INTERVENE — 暂停阶段、向人类呈现选项',
    'cf.escalation.severity.fullRollback':    'FULL_ROLLBACK — 回滚至检查点、全部停止',
    'cf.reinforcement.step':                  '下一步 ▶',
    'cf.reinforcement.reset':                 '重置',
    'cf.reinforcement.round1':                '第 1 轮派发',
    'cf.reinforcement.round2':                '第 2 轮派发（已强化）',
    'cf.reinforcement.findings':              '按严重性过滤的发现',
    'cf.isolation.mustNotLeak':               '禁止泄漏',
    'cf.isolation.isShared':                  '通过制品摘要共享',
    'cf.play':                                '播放',
    'cf.pause':                               '暂停'
  };

  /* ----- Supporting keys: page title, CTAs, table headers, cadence notes -----
     Not part of the spec-required 26, but referenced by data-i18n in the HTML.
     Registered alongside so the ZH toggle leaves no untranslated strings. */
  var EN_SUPPORTING = {
    'page.contextFlow':                'Context Flow — DevolaFlow',
    'cf.cta.frameworkChain':           'Framework Chain →',
    'cf.cta.versionTimeline':          'Version Timeline →',
    'cf.cta.readSkill':                'Read SKILL ↗',
    'cf.dispatch.cadence':             'Loops every ~1.4s',
    'cf.report.cadence':               'Loops every ~1.4s upward',
    'cf.dispatch.envelopeSummary':     '12 required fields, schema in references/message-schemas.md',
    'cf.report.envelopeSummary':       '5 required fields, emitted on completion / failure / escalation',
    'cf.escalation.col.severity':      'Severity',
    'cf.escalation.col.action':        'Action',
    'cf.escalation.activeLabel':       'Active severity',
    'cf.reinforcement.stateLabel':     'State',
    'cf.reinforcement.gateFailNote':   'Gate FAIL → reinforcement extraction begins.',
    'cf.isolation.budgetTitle':        'context_injection budgets',
    'cf.isolation.col.section':        'Section',
    'cf.isolation.col.fields':         'Fields',
    'cf.isolation.col.budget':         'Budget'
  };
  var ZH_SUPPORTING = {
    'page.contextFlow':                '上下文流转 — DevolaFlow',
    'cf.cta.frameworkChain':           '框架链路 →',
    'cf.cta.versionTimeline':          '版本演进 →',
    'cf.cta.readSkill':                '阅读 SKILL ↗',
    'cf.dispatch.cadence':             '每约 1.4 秒循环一次',
    'cf.report.cadence':               '每约 1.4 秒向上循环',
    'cf.dispatch.envelopeSummary':     '12 个必填字段，schema 见 references/message-schemas.md',
    'cf.report.envelopeSummary':       '5 个必填字段，在完成 / 失败 / 升级时发出',
    'cf.escalation.col.severity':      '严重性',
    'cf.escalation.col.action':        '动作',
    'cf.escalation.activeLabel':       '当前严重性',
    'cf.reinforcement.stateLabel':     '状态',
    'cf.reinforcement.gateFailNote':   '门控 FAIL → 强化抽取开始。',
    'cf.isolation.budgetTitle':        'context_injection 预算',
    'cf.isolation.col.section':        '区段',
    'cf.isolation.col.fields':         '字段',
    'cf.isolation.col.budget':         '预算'
  };

  /* Register all keys BEFORE setLanguage runs (i18n init is on DOMContentLoaded;
     this script runs synchronously before that event fires). */
  window.addTranslations('en', EN_REQUIRED);
  window.addTranslations('en', EN_SUPPORTING);
  window.addTranslations('zh', ZH_REQUIRED);
  window.addTranslations('zh', ZH_SUPPORTING);

  /* ==================================================================
     DOM wiring
     ================================================================== */

  function ready(fn) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', fn);
    } else {
      fn();
    }
  }

  ready(function () {
    wirePlayPauseControls();
    wireEnvelopeCollapse();
    wireEscalationButtons();
    wireReinforcementStepMachine();
  });

  /* ----- Play / Pause for dispatch + report routes ----- */
  function wirePlayPauseControls() {
    var toggles = document.querySelectorAll('.cf-play-toggle');
    toggles.forEach(function (btn) {
      var targetId = btn.getAttribute('data-target');
      var route = document.querySelector('#' + targetId + ' .cf-route');
      if (!route) {
        console.warn('[context-flow] play-toggle target not found:', targetId);
        return;
      }
      var label = btn.querySelector('.cf-play-label');
      btn.addEventListener('click', function () {
        var paused = route.classList.toggle('is-paused');
        btn.setAttribute('aria-pressed', paused ? 'true' : 'false');
        if (label) {
          label.setAttribute('data-i18n', paused ? 'cf.play' : 'cf.pause');
          label.textContent = (typeof window.t === 'function')
            ? window.t(paused ? 'cf.play' : 'cf.pause')
            : (paused ? 'Play' : 'Pause');
        }
      });
    });
  }

  /* ----- Collapsible envelope headers ----- */
  function wireEnvelopeCollapse() {
    var headers = document.querySelectorAll('.msg-envelope-header');
    headers.forEach(function (header) {
      header.addEventListener('click', function () {
        toggleEnvelope(header);
      });
      header.addEventListener('keydown', function (ev) {
        if (ev.key === 'Enter' || ev.key === ' ') {
          ev.preventDefault();
          toggleEnvelope(header);
        }
      });
    });
  }

  function toggleEnvelope(header) {
    var envelope = header.closest('.msg-envelope');
    if (!envelope) { return; }
    var collapsed = envelope.classList.toggle('is-collapsed');
    header.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
    var toggle = header.querySelector('.msg-envelope-toggle');
    if (toggle) {
      toggle.textContent = collapsed ? '+' : '\u2212';
    }
  }

  /* ----- Escalation severity buttons ----- */
  function wireEscalationButtons() {
    var buttons = document.querySelectorAll('.cf-esc-btn');
    var dot = document.querySelector('#cf-escalation .dispatch-dot.is-escalated');
    var activeCode = document.getElementById('cf-escalation-active-code');
    if (!dot) {
      console.warn('[context-flow] escalation envelope dot not found');
      return;
    }
    buttons.forEach(function (btn) {
      btn.addEventListener('click', function () {
        var severity = btn.getAttribute('data-severity');
        fireEscalation(dot, severity);
        buttons.forEach(function (b) { b.classList.remove('is-firing'); });
        btn.classList.add('is-firing');
        if (activeCode) { activeCode.textContent = severity; }
      });
    });
  }

  function fireEscalation(dot, severity) {
    /* Restart the one-shot animation by removing + re-adding the class */
    dot.classList.remove('is-active-escalation');
    /* Force reflow so the next add triggers the animation again */
    void dot.offsetWidth;
    dot.setAttribute('data-severity', severity);
    dot.classList.add('is-active-escalation');
  }

  /* ----- Reinforcement 4-state step machine ----- */
  function wireReinforcementStepMachine() {
    var stage    = document.getElementById('cf-reinforcement-stage');
    var stepBtn  = document.getElementById('cf-reinforcement-step');
    var resetBtn = document.getElementById('cf-reinforcement-reset');
    var stateCode = document.getElementById('cf-reinforcement-state-code');
    if (!stage || !stepBtn || !resetBtn) { return; }

    var gateEl = document.getElementById('cf-reinforcement-gate');
    var findingsEl = document.getElementById('cf-reinforcement-findings');
    var findingsNoteEl = document.getElementById('cf-reinforcement-findings-note');
    var round2El = document.getElementById('cf-reinforcement-round2');
    var MAX_STATE = 3;

    function applyState(state) {
      stage.setAttribute('data-state', String(state));
      if (stateCode) { stateCode.textContent = String(state); }
      setHidden(gateEl,         state < 1);
      setHidden(findingsEl,     state < 2);
      setHidden(findingsNoteEl, state < 2);
      setHidden(round2El,       state < 3);
      stepBtn.disabled = state >= MAX_STATE;
    }

    function setHidden(el, hidden) {
      if (!el) { return; }
      if (hidden) { el.setAttribute('hidden', ''); }
      else        { el.removeAttribute('hidden'); }
    }

    stepBtn.addEventListener('click', function () {
      var current = parseInt(stage.getAttribute('data-state') || '0', 10);
      if (current < MAX_STATE) { applyState(current + 1); }
    });
    resetBtn.addEventListener('click', function () {
      applyState(0);
    });

    applyState(0);
  }
})();
