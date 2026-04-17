/**
 * DevolaFlow — Design System page
 *
 * Responsibilities:
 *   1. Register the 24 page-specific `ds.*` translations (EN + ZH) per
 *      spec §6.3, plus 3 supporting keys (page.designSystem,
 *      card.frameworkChain, card.contextFlow) so the title and the hero
 *      cross-page CTAs resolve until S02-T05 lands them in shared/i18n.js.
 *   2. Render the 19 palette swatches (14 inherited + 5 new) into
 *      #palette-grid.
 *   3. Wire swatch clicks → copy CSS-var name to clipboard +
 *      1.5s "copied" toast (with execCommand fallback).
 *   4. Wire each `.motion-replay` button → restart its animation by
 *      removing/re-adding the keyframe class (forced reflow).
 *   5. Re-call setLanguage() at the end of init so the dynamically
 *      injected swatches and the late-registered translations apply.
 */
(function () {
  'use strict';

  /* ====================================================================
     §1  i18n registration
        24 ds.* keys + 3 supporting keys (page.designSystem,
        card.frameworkChain, card.contextFlow).
     ==================================================================== */

  if (typeof window.addTranslations === 'function') {
    window.addTranslations('en', {
      'page.designSystem':              'Design System — DevolaFlow',
      'card.frameworkChain':            'Framework Chain',
      'card.contextFlow':               'Context Flow',

      'ds.subtitle':                    'The Devola design language, on display.',
      'ds.section.palette':             'Palette',
      'ds.section.palette.desc':        '14 inherited tokens plus 5 new tokens for the v6.3 redesign — light + dark side-by-side.',
      'ds.section.typography':          'Typography',
      'ds.section.typography.desc':     'Cinzel for headings, Inter for body, JetBrains Mono for code.',
      'ds.section.motion':              'Motion',
      'ds.section.motion.desc':         'Three new patterns (pulse-dispatch / flow-down / verify-gate-glow) plus the existing scan-flicker reference — all reduce-motion safe.',
      'ds.section.components':          'Components',
      'ds.section.components.desc':     'Eight reusable building blocks the new pages depend on.',
      'ds.section.states':              'States',
      'ds.section.states.desc':         'How active / pass / fail / escalated / reinforced are styled.',
      'ds.section.accessibility':       'Accessibility',
      'ds.section.accessibility.desc':  'Reduced-motion fallbacks, WCAG contrast targets, keyboard focus, bilingual switching.',
      'ds.swatch.copy':                 'Copy CSS var',
      'ds.swatch.copied':               'Copied',
      'ds.motion.replay':               'Replay',
      'ds.motion.label.pulse':          'pulse-dispatch',
      'ds.motion.label.flow':           'flow-down',
      'ds.motion.label.gateGlow':       'verify-gate-glow',
      'ds.motion.label.scanFlicker':    'scan-flicker (existing)',
      'ds.a11y.reducedMotion':          'All animations honour `prefers-reduced-motion: reduce`.',
      'ds.a11y.contrast':               'Body text meets WCAG AA on both themes; new tokens were chosen for AA.',
      'ds.a11y.keyboard':               'Every interactive control is keyboard-focusable with visible focus ring.',
      'ds.a11y.bilingual':              'EN/ZH switch is one click; preference persists in localStorage.'
    });

    window.addTranslations('zh', {
      'page.designSystem':              '设计体系 — DevolaFlow',
      'card.frameworkChain':            '框架链路',
      'card.contextFlow':               '上下文流转',

      'ds.subtitle':                    'Devola 设计语言全面陈列。',
      'ds.section.palette':             '调色板',
      'ds.section.palette.desc':        '14 个继承令牌加 5 个 v6.3 新增令牌——浅色与深色并列展示。',
      'ds.section.typography':          '排版',
      'ds.section.typography.desc':     '标题用 Cinzel，正文用 Inter，代码用 JetBrains Mono。',
      'ds.section.motion':              '动效',
      'ds.section.motion.desc':         '三种新动效（pulse-dispatch / flow-down / verify-gate-glow）外加现有的 scan-flicker 参考——全部支持 reduce-motion。',
      'ds.section.components':          '组件',
      'ds.section.components.desc':     '新页面依赖的八个可复用基础组件。',
      'ds.section.states':              '状态',
      'ds.section.states.desc':         'active / pass / fail / escalated / reinforced 的样式约定。',
      'ds.section.accessibility':       '可访问性',
      'ds.section.accessibility.desc':  '动效降级、WCAG 对比度、键盘焦点、双语切换的承诺。',
      'ds.swatch.copy':                 '复制 CSS 变量',
      'ds.swatch.copied':               '已复制',
      'ds.motion.replay':               '重放',
      'ds.motion.label.pulse':          'pulse-dispatch',
      'ds.motion.label.flow':           'flow-down',
      'ds.motion.label.gateGlow':       'verify-gate-glow',
      'ds.motion.label.scanFlicker':    'scan-flicker（现有）',
      'ds.a11y.reducedMotion':          '所有动效遵循 `prefers-reduced-motion: reduce`。',
      'ds.a11y.contrast':               '正文在双主题下均满足 WCAG AA；新令牌均为此选定。',
      'ds.a11y.keyboard':               '所有交互控件均可键盘聚焦，焦点可见。',
      'ds.a11y.bilingual':              '一键切换中英文，偏好保存于 localStorage。'
    });
  }

  /* ====================================================================
     §2  Palette data
        14 inherited tokens cited verbatim from
        workflow-system/human/demo/shared/styles.css lines 8–26
        (13 colour tokens + --shadow). 5 NEW tokens per spec §3.2.
     ==================================================================== */

  // 14 inherited (the 14th is --shadow, rendered specially).
  var PALETTE_INHERITED = [
    { name: '--bg',           light: '#F0EBE0',           dark: '#1A1714' },
    { name: '--fg',           light: '#3D3429',           dark: '#E8DFD0' },
    { name: '--card-bg',      light: '#FAF7F2',           dark: '#252018' },
    { name: '--border',       light: '#D4CBB8',           dark: '#3D3628' },
    { name: '--accent',       light: '#B8860B',           dark: '#D4A843' },
    { name: '--accent-hover', light: '#9A7209',           dark: '#E8BC4E' },
    { name: '--accent-light', light: '#F5EDD8',           dark: '#2A2418' },
    { name: '--muted',        light: '#8A7E6D',           dark: '#968D7C' },
    { name: '--success',      light: '#5B7553',           dark: '#7A9E70' },
    { name: '--error',        light: '#B54040',           dark: '#D06060' },
    { name: '--warning',      light: '#C49A3C',           dark: '#D4A843' },
    { name: '--code-bg',      light: '#EAE4D4',           dark: '#2A2520' },
    { name: '--secondary',    light: '#9B4444',           dark: '#C76B6B' },
    { name: '--shadow',       light: 'rgba(61,52,41,.08)', dark: 'rgba(0,0,0,.3)', kind: 'shadow' }
  ];

  // 5 NEW (per spec §3.2; values inlined locally in styles.css :root/.dark).
  var PALETTE_NEW = [
    { name: '--ink-deep',       light: '#2A241B',                dark: '#0F0D0A' },
    { name: '--gold-glow',      light: 'rgba(184,134,11,0.45)',  dark: 'rgba(212,168,67,0.55)' },
    { name: '--scanline-alpha', light: '0.04',                   dark: '0.06', kind: 'alpha' },
    { name: '--rail-track',     light: '#E5DCC4',                dark: '#2E2820' },
    { name: '--ember-red',      light: '#7A2E2E',                dark: '#B85050' }
  ];

  /* ====================================================================
     §3  Build a single swatch button
     ==================================================================== */

  function buildSwatch(tok, isNew) {
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'swatch' + (isNew ? ' swatch-new' : '');
    btn.setAttribute('data-var', tok.name);
    btn.setAttribute('aria-label', tok.name + ' — copy CSS variable name');
    btn.setAttribute('data-i18n-title', 'ds.swatch.copy');
    btn.style.setProperty('--swatch-light', tok.light);
    btn.style.setProperty('--swatch-dark', tok.dark);

    var halves = document.createElement('span');
    halves.className = 'swatch-halves swatch-halves-' + (tok.kind || 'color');

    var lh = document.createElement('span');
    lh.className = 'swatch-half swatch-half-light';
    var rh = document.createElement('span');
    rh.className = 'swatch-half swatch-half-dark';

    if (tok.kind === 'shadow') {
      var lInner = document.createElement('i');
      lInner.className = 'swatch-shadow-card';
      lInner.style.boxShadow = '0 1px 4px ' + tok.light;
      lh.appendChild(lInner);
      var rInner = document.createElement('i');
      rInner.className = 'swatch-shadow-card';
      rInner.style.boxShadow = '0 1px 4px ' + tok.dark;
      rh.appendChild(rInner);
    } else if (tok.kind === 'alpha') {
      lh.style.setProperty('--alpha-val', tok.light);
      rh.style.setProperty('--alpha-val', tok.dark);
    }

    halves.appendChild(lh);
    halves.appendChild(rh);

    var meta = document.createElement('span');
    meta.className = 'swatch-meta';
    var code = document.createElement('code');
    code.textContent = tok.name;
    var values = document.createElement('small');
    values.textContent = tok.light + ' / ' + tok.dark;
    meta.appendChild(code);
    meta.appendChild(values);

    if (isNew) {
      var newBadge = document.createElement('span');
      newBadge.className = 'swatch-new-badge';
      newBadge.textContent = 'NEW';
      meta.appendChild(newBadge);
    }

    btn.appendChild(halves);
    btn.appendChild(meta);
    return btn;
  }

  function renderPalette() {
    var grid = document.getElementById('palette-grid');
    if (!grid) {
      console.error('design-system: #palette-grid not found in DOM');
      return;
    }
    grid.innerHTML = '';
    PALETTE_INHERITED.forEach(function (tok) {
      grid.appendChild(buildSwatch(tok, false));
    });
    PALETTE_NEW.forEach(function (tok) {
      grid.appendChild(buildSwatch(tok, true));
    });
  }

  /* ====================================================================
     §4  Clipboard + toast
        Clipboard API → execCommand('copy') fallback. Errors are logged
        and surfaced via the toast (per workspace rule "No Silent Failures").
     ==================================================================== */

  function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text);
    }
    return new Promise(function (resolve, reject) {
      var ta = document.createElement('textarea');
      ta.value = text;
      ta.setAttribute('readonly', '');
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      ta.style.pointerEvents = 'none';
      document.body.appendChild(ta);
      ta.select();
      var err;
      var ok = false;
      try {
        ok = document.execCommand('copy');
      } catch (e) {
        err = e;
      }
      document.body.removeChild(ta);
      if (ok) {
        resolve();
      } else {
        reject(err || new Error('execCommand("copy") returned false'));
      }
    });
  }

  var toastTimer = null;
  function showToast(message) {
    var toast = document.getElementById('ds-toast');
    if (!toast) { return; }
    toast.textContent = message;
    toast.classList.add('is-visible');
    if (toastTimer) { clearTimeout(toastTimer); }
    toastTimer = setTimeout(function () {
      toast.classList.remove('is-visible');
    }, 1500);
  }

  function copiedLabel() {
    if (typeof window.t === 'function') {
      return window.t('ds.swatch.copied');
    }
    return 'Copied';
  }

  function wireSwatches() {
    document.querySelectorAll('.swatch').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var varName = btn.getAttribute('data-var');
        if (!varName) { return; }
        copyText(varName).then(function () {
          showToast(copiedLabel() + ': ' + varName);
          btn.classList.add('is-copied');
          setTimeout(function () {
            btn.classList.remove('is-copied');
          }, 1500);
        }).catch(function (err) {
          // Surface the failure (no silent swallowing).
          console.error('design-system: failed to copy CSS var', varName, err);
          showToast('Could not copy ' + varName);
        });
      });
    });
  }

  /* ====================================================================
     §5  Motion replay
        Maps each motion-id → its keyframe-binding class. Replay by
        toggling the class with a forced reflow in between.
     ==================================================================== */

  var REPLAY_CLASS = {
    'pulse-dispatch':   'has-pulse-dispatch',
    'flow-down':        'has-flow-down',
    'verify-gate-glow': 'has-verify-glow',
    'scan-flicker':     'scan-flicker'
  };

  function replayMotion(target) {
    var cls = REPLAY_CLASS[target];
    if (!cls) {
      console.error('design-system: unknown motion target', target);
      return;
    }
    var stage = document.querySelector(
      '.motion-demo[data-motion="' + target + '"] .motion-stage'
    );
    if (!stage) { return; }
    var els = stage.querySelectorAll('.' + cls);
    els.forEach(function (el) {
      el.classList.remove(cls);
      // Force a reflow so the browser commits the removed state before
      // we re-add the class — this restarts the animation cleanly.
      void el.offsetWidth;
      el.classList.add(cls);
    });
  }

  function wireMotionReplays() {
    document.querySelectorAll('.motion-replay').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var target = btn.getAttribute('data-target');
        if (target) { replayMotion(target); }
      });
    });
  }

  /* ====================================================================
     §6  Init
     ==================================================================== */

  function init() {
    renderPalette();
    wireSwatches();
    wireMotionReplays();
    // Re-apply translations now that addTranslations and the dynamically
    // injected swatch DOM are both in place. Without this, shared/i18n.js's
    // initial setLanguage (which ran before this script loaded) leaves the
    // ds.* keys un-translated and the title showing the raw key.
    if (typeof window.setLanguage === 'function') {
      var lang = document.documentElement.getAttribute('data-lang') || 'en';
      window.setLanguage(lang);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
