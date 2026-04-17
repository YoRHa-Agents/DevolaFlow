/**
 * DevolaFlow — Version Timeline page
 *
 * Responsibilities:
 *   1. Register 22 spec-required i18n keys + page-supporting keys (EN + ZH)
 *      so every visible string survives the EN/ZH toggle.
 *   2. Fetch versions.json (try/catch — logs to console.error AND renders a
 *      visible error state per spec rule 12 / Rule "No Silent Failures").
 *   3. Render one TimelineCard per version into its era's .tl-rail.
 *   4. Wire era-filter chips (URL hash #vt-era-platforms deep-links to that
 *      filtered view on first load — AC-VT-5).
 *   5. Wire compact / detailed view toggle, persisted in localStorage under
 *      key "devolaflow-timeline-view" (AC-VT-6).
 *   6. Wire per-card expand / collapse (AC-VT-4).
 *   7. Era reveal cascade via IntersectionObserver — vt-flow-down keyframe is
 *      defined in styles.css and respects the global prefers-reduced-motion
 *      rule (shared/styles.css line 339; spec rule 10).
 *
 * No absolute paths anywhere (Rule SF-5 / CO-4).
 */
(function () {
  'use strict';

  /* ==================================================================
     i18n — 22 SPEC-REQUIRED page keys + supporting keys.
     Registered for BOTH en and zh so the ZH toggle never falls back to a
     key-shaped string.  shared/i18n.js init() runs on DOMContentLoaded;
     this script tag loads synchronously after shared/i18n.js but BEFORE
     DOMContentLoaded fires, so every key is registered before setLanguage.
     ================================================================== */

  if (typeof window.addTranslations !== 'function') {
    /* shared/i18n.js failed to load — surface the error explicitly
       rather than silently falling back to default text. */
    console.error('[version-timeline] addTranslations unavailable; shared/i18n.js missing');
    return;
  }

  /* ----- 22 SPEC-REQUIRED page-specific keys (EN) ----- */
  var EN_REQUIRED = {
    'vt.subtitle':              'From v0.1.0 to v6.2.1 — five eras of guarded change.',
    'vt.era.foundations':       'Foundations',
    'vt.era.evobench':          'EvoBench & Hardening',
    'vt.era.selfImprove':       'Self-Improvement Loops',
    'vt.era.platforms':         'Platforms & Closure',
    'vt.era.rollup':            'Rollup & Stabilization',
    'vt.era.foundations.desc':  'v0.1.0 – v2.2.0: scaffolding, the first 11 templates, +93% information density.',
    'vt.era.evobench.desc':     'v3.0.0 – v3.9.x: EvoBench, repository rules, full workflow coverage, P1 enforced.',
    'vt.era.selfImprove.desc':  'v4.0.0 – v5.4.2: model routing, plugin registry, NineS, reinforcement infrastructure.',
    'vt.era.platforms.desc':    'v6.0.0 – v6.1.5: 11 platforms, dead-wire closure, schema parity, plan-mode runtime.',
    'vt.era.rollup.desc':       'v6.2.0 – v6.2.1: SI-3 9.43/10, 1009 tests, NineS 0.7405 → 0.8805, CI flake closed.',
    'vt.filter.all':            'All eras',
    'vt.toggle.compact':        'Compact',
    'vt.toggle.detailed':       'Detailed',
    'vt.card.expand':           'Expand',
    'vt.card.collapse':         'Collapse',
    'vt.metric.tests':          'Tests',
    'vt.metric.coverage':       'Coverage',
    'vt.metric.nines':          'NineS',
    'vt.metric.composite':      'Composite',
    'vt.cta.changelog':         'Read CHANGELOG',
    'vt.cta.releases':          'GitHub Releases'
  };

  /* ----- 22 SPEC-REQUIRED page-specific keys (ZH) ----- */
  var ZH_REQUIRED = {
    'vt.subtitle':              '从 v0.1.0 到 v6.2.1——五个时代、有守护的演进。',
    'vt.era.foundations':       '奠基',
    'vt.era.evobench':          'EvoBench 与加固',
    'vt.era.selfImprove':       '自我改进闭环',
    'vt.era.platforms':         '平台扩展与收口',
    'vt.era.rollup':            '总集与稳定',
    'vt.era.foundations.desc':  'v0.1.0 – v2.2.0：脚手架、最初的 11 个模板、信息密度 +93%。',
    'vt.era.evobench.desc':     'v3.0.0 – v3.9.x：EvoBench、仓库规则、全工作流覆盖、P1 真正落地。',
    'vt.era.selfImprove.desc':  'v4.0.0 – v5.4.2：模型路由、插件注册、NineS、强化基础设施。',
    'vt.era.platforms.desc':    'v6.0.0 – v6.1.5：11 个平台、死线接通、schema 对齐、Plan-mode 运行时。',
    'vt.era.rollup.desc':       'v6.2.0 – v6.2.1：SI-3 9.43/10、1009 测试、NineS 0.7405 → 0.8805、CI flake 收口。',
    'vt.filter.all':            '全部时代',
    'vt.toggle.compact':        '简洁',
    'vt.toggle.detailed':       '详细',
    'vt.card.expand':           '展开',
    'vt.card.collapse':         '折叠',
    'vt.metric.tests':          '测试',
    'vt.metric.coverage':       '覆盖率',
    'vt.metric.nines':          'NineS',
    'vt.metric.composite':      '综合分',
    'vt.cta.changelog':         '查看 CHANGELOG',
    'vt.cta.releases':          'GitHub 发布'
  };

  /* ----- Supporting keys: page title, CTAs, status / error / empty
     messages, highlights heading, link cluster heading. Not part of the
     22 required, but referenced by data-i18n in the markup or by the
     renderer below; registered so EN/ZH toggle leaves nothing untranslated. */
  var EN_SUPPORTING = {
    'page.versionTimeline':     'R&D Timeline — DevolaFlow',
    'vt.cta.designSystem':      'Design System →',
    'vt.cta.frameworkChain':    'Framework Chain →',
    'vt.status.loading':        'Loading versions…',
    'vt.status.loaded':         '{n} versions across 5 eras.',
    'vt.status.filtered':       'Showing {n} versions in “{era}”.',
    'vt.error.title':           'Could not load versions.json',
    'vt.error.detail':          'Open the browser console for the underlying network or parse error.',
    'vt.empty.era':             'No versions match the current filter in this era.',
    'vt.detail.highlights':     'Highlights',
    'vt.detail.metrics':        'Metrics',
    'vt.detail.links':          'Cross-links'
  };
  var ZH_SUPPORTING = {
    'page.versionTimeline':     '研发演进 — DevolaFlow',
    'vt.cta.designSystem':      '设计体系 →',
    'vt.cta.frameworkChain':    '框架链路 →',
    'vt.status.loading':        '正在加载版本…',
    'vt.status.loaded':         '共 {n} 个版本，覆盖 5 个时代。',
    'vt.status.filtered':       '在「{era}」中显示 {n} 个版本。',
    'vt.error.title':           '无法加载 versions.json',
    'vt.error.detail':          '请打开浏览器控制台查看具体的网络或解析错误。',
    'vt.empty.era':             '当前筛选条件下，本时代没有匹配版本。',
    'vt.detail.highlights':     '亮点',
    'vt.detail.metrics':        '指标',
    'vt.detail.links':          '跨页跳转'
  };

  /* Register all keys BEFORE setLanguage runs. */
  window.addTranslations('en', EN_REQUIRED);
  window.addTranslations('en', EN_SUPPORTING);
  window.addTranslations('zh', ZH_REQUIRED);
  window.addTranslations('zh', ZH_SUPPORTING);

  /* ==================================================================
     Constants / DOM helpers
     ================================================================== */

  var VIEW_KEY = 'devolaflow-timeline-view';   /* localStorage key per spec rule 8 */
  var VIEW_DETAILED = 'detailed';
  var VIEW_COMPACT  = 'compact';
  var ERAS = ['foundations', 'evobench', 'self-improve', 'platforms', 'rollup'];

  /* Map era enum -> i18n key for the era label */
  var ERA_LABEL_KEY = {
    'foundations':  'vt.era.foundations',
    'evobench':     'vt.era.evobench',
    'self-improve': 'vt.era.selfImprove',
    'platforms':    'vt.era.platforms',
    'rollup':       'vt.era.rollup'
  };

  function t(key) {
    return (typeof window.t === 'function') ? window.t(key) : key;
  }

  function format(template, params) {
    /* Tiny `{key}` interpolator — keeps the page from pulling in a
       templating dependency just to fill 2 status strings. */
    return String(template).replace(/\{(\w+)\}/g, function (_, k) {
      return params[k] !== undefined ? params[k] : '{' + k + '}';
    });
  }

  /* --- Dynamic status line: holds a re-renderable record so the EN/ZH
     toggle can refresh formatted strings (otherwise shared/i18n.js setLanguage
     would overwrite them with the literal `{n}` template). --------------- */
  var _statusState = { kind: 'loading', params: {} };

  function setStatus(kind, params) {
    _statusState = { kind: kind, params: params || {} };
    paintStatus();
  }

  function paintStatus() {
    var el = document.getElementById('vt-status');
    if (!el) { return; }
    el.classList.remove('is-error');
    if (_statusState.kind === 'loading') {
      el.setAttribute('data-i18n', 'vt.status.loading');
      el.textContent = t('vt.status.loading');
    } else if (_statusState.kind === 'loaded') {
      el.removeAttribute('data-i18n'); /* prevent setLanguage from clobbering */
      el.textContent = format(t('vt.status.loaded'), _statusState.params);
    } else if (_statusState.kind === 'filtered') {
      el.removeAttribute('data-i18n');
      el.textContent = format(t('vt.status.filtered'), _statusState.params);
    } else if (_statusState.kind === 'error') {
      el.classList.add('is-error');
      el.setAttribute('data-i18n', 'vt.error.title');
      el.textContent = t('vt.error.title');
    }
  }

  /* Wrap the shared setLanguage so that, after it processes static
     data-i18n nodes, our dynamic strings (status line, expand-button labels
     when their parameters depend on state) are re-painted with the new
     locale. The status line is the only string with template parameters;
     other dynamic-i18n nodes (era badge, expand button) carry data-i18n
     and are handled by setLanguage natively. */
  if (typeof window.setLanguage === 'function' && !window.__vt_setLanguageWrapped) {
    var _origSetLanguage = window.setLanguage;
    window.setLanguage = function (lang) {
      _origSetLanguage(lang);
      paintStatus();
    };
    window.__vt_setLanguageWrapped = true;
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function ready(fn) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', fn);
    } else {
      fn();
    }
  }

  /* ==================================================================
     Headline-metric selection for the MetricMicroBar
     ================================================================== */

  /**
   * Decide which single metric becomes the card's headline bar.
   * Priority: composite (0-100) > coverage_pct (0-100) > nines (0-1)
   *          > tests (relative to known max 1009).
   * Returns null when no metric is available — card omits the bar row.
   */
  function pickHeadlineMetric(metrics) {
    if (!metrics || typeof metrics !== 'object') { return null; }
    if (typeof metrics.composite === 'number') {
      return {
        labelKey: 'vt.metric.composite',
        value: metrics.composite,
        valueText: metrics.composite.toFixed(metrics.composite >= 100 ? 0 : 2),
        pct: clamp(metrics.composite, 0, 100)
      };
    }
    if (typeof metrics.coverage_pct === 'number') {
      return {
        labelKey: 'vt.metric.coverage',
        value: metrics.coverage_pct,
        valueText: metrics.coverage_pct.toFixed(2) + '%',
        pct: clamp(metrics.coverage_pct, 0, 100)
      };
    }
    if (typeof metrics.nines === 'number') {
      var ninesPct = metrics.nines * 100;
      return {
        labelKey: 'vt.metric.nines',
        value: metrics.nines,
        valueText: metrics.nines.toFixed(4),
        pct: clamp(ninesPct, 0, 100)
      };
    }
    if (typeof metrics.tests === 'number') {
      var TESTS_MAX = 1009; /* repo's current test count, verbatim from CHANGELOG v6.2.0 */
      return {
        labelKey: 'vt.metric.tests',
        value: metrics.tests,
        valueText: String(metrics.tests),
        pct: clamp((metrics.tests / TESTS_MAX) * 100, 0, 100)
      };
    }
    return null;
  }

  function clamp(n, lo, hi) {
    return Math.max(lo, Math.min(hi, n));
  }

  /* ==================================================================
     Rendering — versions.json -> .tl-rail innerHTML per era
     ================================================================== */

  function renderTimeline(versions) {
    /* Group versions by era for stable per-era ordering. We render each
       era's rail in CHANGELOG order (which is reverse-chronological inside
       versions.json) but reversed to be chronological top-to-bottom on the
       page so the timeline reads as a journey. */
    var grouped = {};
    ERAS.forEach(function (era) { grouped[era] = []; });

    versions.forEach(function (v) {
      if (grouped[v.era] === undefined) {
        console.warn('[version-timeline] unknown era for v%s: %s', v.version, v.era);
        return;
      }
      grouped[v.era].push(v);
    });

    /* Reverse so the oldest version in an era appears at the top of the
       rail and the newest at the bottom — matches reader expectation. */
    ERAS.forEach(function (era) {
      grouped[era].sort(function (a, b) {
        /* Date-then-version sort, ascending. */
        if (a.date < b.date) { return -1; }
        if (a.date > b.date) { return 1; }
        return compareVersions(a.version, b.version);
      });
    });

    ERAS.forEach(function (era) {
      var rail = document.getElementById('vt-rail-' + era);
      if (!rail) {
        console.warn('[version-timeline] rail not found for era:', era);
        return;
      }
      var html = grouped[era].map(function (v, idx) {
        return renderCard(v, idx);
      }).join('');
      rail.innerHTML = html;
    });

    /* Status line: how many versions loaded total */
    setStatus('loaded', { n: versions.length });
  }

  function compareVersions(a, b) {
    /* Lightweight semver-ish compare so v5.1.0-pre sorts before v5.2.0. */
    var pa = String(a).split(/[.\-+]/).map(function (p) { return /^\d+$/.test(p) ? parseInt(p, 10) : p; });
    var pb = String(b).split(/[.\-+]/).map(function (p) { return /^\d+$/.test(p) ? parseInt(p, 10) : p; });
    var len = Math.max(pa.length, pb.length);
    for (var i = 0; i < len; i++) {
      var x = pa[i] === undefined ? 0 : pa[i];
      var y = pb[i] === undefined ? 0 : pb[i];
      if (typeof x !== typeof y) {
        x = String(x); y = String(y);
      }
      if (x < y) { return -1; }
      if (x > y) { return 1; }
    }
    return 0;
  }

  function renderCard(v, idx) {
    var headline   = pickHeadlineMetric(v.metrics);
    var eraLabel   = t(ERA_LABEL_KEY[v.era] || '');
    var summary    = escapeHtml(v.summary || '');
    var headlineH  = escapeHtml(v.headline || '');
    var versionStr = escapeHtml(v.version || '');
    var dateStr    = escapeHtml(v.date || '');

    var metricRowHTML = '';
    if (headline) {
      metricRowHTML =
        '<div class="tl-metric-row" aria-label="' + escapeHtml(t(headline.labelKey)) + '">' +
          '<span class="tl-metric-label" data-i18n="' + headline.labelKey + '">' +
            escapeHtml(t(headline.labelKey)) +
          '</span>' +
          '<span class="metric-micro" role="img" aria-label="' + escapeHtml(t(headline.labelKey)) + ' ' + escapeHtml(headline.valueText) + '">' +
            '<i class="metric-micro-fill" style="--pct:' + headline.pct.toFixed(2) + '%"></i>' +
          '</span>' +
          '<span class="tl-metric-value">' + escapeHtml(headline.valueText) + '</span>' +
        '</div>';
    }

    var inlineSummary =
      '<span class="tl-summary-inline" title="' + escapeHtml(v.summary || '') + '">' +
        summary +
      '</span>';

    var eraLabelKey = ERA_LABEL_KEY[v.era] || '';

    var head =
      '<div class="tl-card-head">' +
        '<span class="tl-version">v' + versionStr + '</span>' +
        '<time datetime="' + dateStr + '">' + dateStr + '</time>' +
        inlineSummary +
        '<span class="tl-era-badge"' +
          (eraLabelKey ? ' data-i18n="' + eraLabelKey + '"' : '') +
        '>' + escapeHtml(eraLabel) + '</span>' +
        '<button type="button" class="tl-expand"' +
          ' aria-expanded="false" aria-controls="tl-detail-' + versionStr + '"' +
          ' data-i18n="vt.card.expand">' +
          escapeHtml(t('vt.card.expand')) +
        '</button>' +
        '<h3 class="tl-headline">' + headlineH + '</h3>' +
        '<p class="tl-summary">' + summary + '</p>' +
        metricRowHTML +
      '</div>';

    var highlightsHTML = '';
    if (Array.isArray(v.highlights) && v.highlights.length > 0) {
      highlightsHTML =
        '<h4 data-i18n="vt.detail.highlights">' + escapeHtml(t('vt.detail.highlights')) + '</h4>' +
        '<ul class="tl-highlights">' +
          v.highlights.map(function (h) { return '<li>' + escapeHtml(h) + '</li>'; }).join('') +
        '</ul>';
    }

    var metricsGridHTML = renderMetricsGrid(v.metrics);

    var linksHTML = '';
    if (Array.isArray(v.links) && v.links.length > 0) {
      linksHTML =
        '<h4 data-i18n="vt.detail.links">' + escapeHtml(t('vt.detail.links')) + '</h4>' +
        '<div class="tl-links">' +
          v.links.map(function (l) {
            var href  = escapeHtml(l.href || '#');
            var label = escapeHtml(l.label || href);
            return '<a class="tl-link" href="' + href + '">' + label + '</a>';
          }).join('') +
        '</div>';
    }

    var detail =
      '<div class="tl-detail" id="tl-detail-' + versionStr + '" hidden>' +
        highlightsHTML +
        metricsGridHTML +
        linksHTML +
      '</div>';

    return (
      '<li class="tl-card" data-version="' + versionStr + '"' +
        ' data-era="' + escapeHtml(v.era) + '"' +
        ' style="--vt-stagger:' + idx + ';">' +
        '<span class="tl-dot" aria-hidden="true"></span>' +
        head +
        detail +
      '</li>'
    );
  }

  function renderMetricsGrid(metrics) {
    if (!metrics || typeof metrics !== 'object') { return ''; }
    var entries = Object.keys(metrics);
    if (entries.length === 0) { return ''; }

    var cells = entries.map(function (k) {
      var raw = metrics[k];
      var val = (typeof raw === 'number')
        ? (Number.isInteger(raw) ? String(raw) : raw.toFixed(raw < 1 ? 4 : 2))
        : String(raw);
      return (
        '<div class="tl-metric-cell">' +
          '<span class="k">' + escapeHtml(k) + '</span>' +
          '<span class="v">' + escapeHtml(val) + '</span>' +
        '</div>'
      );
    }).join('');

    return (
      '<h4 data-i18n="vt.detail.metrics">' + escapeHtml(t('vt.detail.metrics')) + '</h4>' +
      '<div class="tl-metrics-grid">' + cells + '</div>'
    );
  }

  /* ==================================================================
     Era filter — chips + URL hash deep-link
     ================================================================== */

  function applyEraFilter(era) {
    var validEra = era === 'all' || ERAS.indexOf(era) !== -1;
    if (!validEra) { era = 'all'; }

    /* Chip pressed-state */
    document.querySelectorAll('.vt-era-chip').forEach(function (chip) {
      var match = (chip.getAttribute('data-era') === era);
      chip.classList.toggle('is-active', match);
      chip.setAttribute('aria-pressed', match ? 'true' : 'false');
    });

    /* Section visibility */
    document.querySelectorAll('.vt-era').forEach(function (sec) {
      var match = (era === 'all') || (sec.getAttribute('data-era') === era);
      sec.classList.toggle('is-hidden', !match);
    });

    /* Status line update — only after data has actually been rendered, so
       the pre-fetch hash filter pass doesn't flash "Showing 0 versions". */
    var totalCards = document.querySelectorAll('.tl-card').length;
    if (totalCards === 0) { return; }

    if (era !== 'all') {
      var visibleCards = document.querySelectorAll(
        '.vt-era[data-era="' + era + '"] .tl-card'
      ).length;
      setStatus('filtered', { n: visibleCards, era: t(ERA_LABEL_KEY[era] || era) });
    } else {
      setStatus('loaded', { n: totalCards });
    }
  }

  function wireEraFilter() {
    document.querySelectorAll('.vt-era-chip').forEach(function (chip) {
      chip.addEventListener('click', function () {
        var era = chip.getAttribute('data-era') || 'all';
        applyEraFilter(era);
        /* Reflect to URL hash so deep-linking works.
           Use replaceState so the back button doesn't accumulate filter spam. */
        var hash = (era === 'all') ? '' : '#vt-era-' + era;
        if (hash) {
          history.replaceState(null, '', hash);
          /* Programmatic scroll to anchor (avoids jump if user is mid-page) */
          var target = document.getElementById('vt-era-' + era);
          if (target) {
            target.scrollIntoView({ behavior: 'smooth', block: 'start' });
          }
        } else {
          history.replaceState(null, '', window.location.pathname + window.location.search);
        }
      });
    });
  }

  function readEraFromHash() {
    var hash = window.location.hash || '';
    var match = hash.match(/^#vt-era-([a-z\-]+)$/);
    if (!match) { return null; }
    var candidate = match[1];
    return ERAS.indexOf(candidate) !== -1 ? candidate : null;
  }

  /* ==================================================================
     View toggle (compact / detailed) — persisted to localStorage
     ================================================================== */

  function readView() {
    try {
      var stored = localStorage.getItem(VIEW_KEY);
      if (stored === VIEW_COMPACT || stored === VIEW_DETAILED) { return stored; }
    } catch (e) {
      /* localStorage may be denied (private mode, sandbox, etc.) — fall
         through to the default and keep the page functional. */
      console.warn('[version-timeline] localStorage read failed:', e);
    }
    return VIEW_DETAILED;
  }

  function writeView(view) {
    try {
      localStorage.setItem(VIEW_KEY, view);
    } catch (e) {
      console.warn('[version-timeline] localStorage write failed:', e);
    }
  }

  function applyView(view) {
    if (view !== VIEW_COMPACT && view !== VIEW_DETAILED) { view = VIEW_DETAILED; }
    document.body.classList.toggle('is-compact', view === VIEW_COMPACT);

    document.querySelectorAll('.vt-view-btn').forEach(function (btn) {
      var match = (btn.getAttribute('data-view') === view);
      btn.classList.toggle('is-active', match);
      btn.setAttribute('aria-pressed', match ? 'true' : 'false');
    });
  }

  function wireViewToggle() {
    document.querySelectorAll('.vt-view-btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var view = btn.getAttribute('data-view') || VIEW_DETAILED;
        applyView(view);
        writeView(view);
      });
    });
  }

  /* ==================================================================
     Per-card expand / collapse
     ================================================================== */

  function wireCardExpand(rootEl) {
    var buttons = (rootEl || document).querySelectorAll('.tl-expand');
    buttons.forEach(function (btn) {
      btn.addEventListener('click', function () {
        var card = btn.closest('.tl-card');
        if (!card) { return; }
        var expanded = card.classList.toggle('is-expanded');
        btn.setAttribute('aria-expanded', expanded ? 'true' : 'false');

        var nextLabelKey = expanded ? 'vt.card.collapse' : 'vt.card.expand';
        btn.setAttribute('data-i18n', nextLabelKey);
        btn.textContent = t(nextLabelKey);

        var detail = card.querySelector('.tl-detail');
        if (detail) {
          if (expanded) { detail.removeAttribute('hidden'); }
          else          { detail.setAttribute('hidden', ''); }
        }
      });
    });
  }

  /* ==================================================================
     Era reveal cascade — IntersectionObserver triggers vt-flow-down on
     each era's cards once when the era first scrolls into view.
     `prefers-reduced-motion: reduce` is honoured automatically by the
     global rule in shared/styles.css line 339 (animation-duration → 0.01ms).
     ================================================================== */

  function wireRevealCascade() {
    if (typeof IntersectionObserver !== 'function') {
      /* Older browsers: just reveal everything immediately. */
      document.querySelectorAll('.tl-card').forEach(function (card) {
        card.classList.add('is-revealed');
      });
      return;
    }
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) { return; }
        var era = entry.target;
        era.querySelectorAll('.tl-card').forEach(function (card) {
          card.classList.add('is-revealed');
        });
        observer.unobserve(era);
      });
    }, { rootMargin: '0px 0px -10% 0px', threshold: 0.05 });

    document.querySelectorAll('.vt-era').forEach(function (era) {
      observer.observe(era);
    });
  }

  /* ==================================================================
     Error state — visible to the user (per spec rule 12 / "No Silent
     Failures").  Renders a card-shaped block above the eras and replaces
     the status line with a localised error message.
     ================================================================== */

  function renderErrorState(err) {
    console.error('[version-timeline] failed to load versions.json:', err);
    setStatus('error', {});

    var existing = document.querySelector('.vt-error');
    if (existing) { existing.remove(); }

    var errBlock = document.createElement('div');
    errBlock.className = 'vt-error';
    errBlock.setAttribute('role', 'alert');
    errBlock.innerHTML =
      '<h3 data-i18n="vt.error.title">' + escapeHtml(t('vt.error.title')) + '</h3>' +
      '<p data-i18n="vt.error.detail">' + escapeHtml(t('vt.error.detail')) + '</p>' +
      '<p><code>' + escapeHtml(String(err && err.message ? err.message : err)) + '</code></p>';

    var firstEra = document.querySelector('.vt-era');
    if (firstEra && firstEra.parentNode) {
      firstEra.parentNode.insertBefore(errBlock, firstEra);
    } else {
      var container = document.querySelector('.container');
      if (container) { container.appendChild(errBlock); }
    }
  }

  /* ==================================================================
     Boot
     ================================================================== */

  ready(function () {
    /* 1. Restore persisted view first so layout is stable before render. */
    applyView(readView());
    wireViewToggle();
    wireEraFilter();

    /* 2. Apply hash filter on first load (AC-VT-5). */
    var hashEra = readEraFromHash();
    if (hashEra) { applyEraFilter(hashEra); }

    /* 3. Fetch versions.json and render.  Wrapped in try/catch — logs to
       console.error AND renders a visible error state per spec rule 12. */
    fetchVersions()
      .then(function (versions) {
        if (!Array.isArray(versions)) {
          throw new Error('versions.json did not parse to an array');
        }
        renderTimeline(versions);
        wireCardExpand(document);
        wireRevealCascade();

        /* If the URL hash filter applied above, refresh the status count
           now that the cards have been rendered. */
        if (hashEra) { applyEraFilter(hashEra); }

        /* If the user toggled language while we were fetching, re-bind
           the freshly-injected data-i18n nodes. */
        if (typeof window.setLanguage === 'function') {
          var lang = document.documentElement.getAttribute('data-lang') || 'en';
          window.setLanguage(lang);
        }
      })
      .catch(function (err) {
        renderErrorState(err);
      });
  });

  function fetchVersions() {
    /* Keep the path RELATIVE so it works under file://, http://, and Pages.
       Rule SF-5 / CO-4: never use absolute filesystem paths. */
    return fetch('versions.json', { cache: 'no-cache' })
      .then(function (res) {
        if (!res.ok) {
          throw new Error('HTTP ' + res.status + ' ' + res.statusText + ' for versions.json');
        }
        return res.json();
      });
  }
})();
