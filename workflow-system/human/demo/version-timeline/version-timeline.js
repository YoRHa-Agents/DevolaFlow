/**
 * DevolaFlow release archive.
 *
 * versions.json remains the release-data source of truth. Era controls and
 * rails are derived from that data so a new era never requires new markup.
 */
(function () {
  'use strict';

  var VIEW_KEY = 'devolaflow-timeline-view';
  var CURRENT_MAJOR = 16;
  var RETIRED_TERMS = [
    { label: 'EvoBench', pattern: /\bEvoBench\b/i },
    { label: 'NineS', pattern: /\bNineS\b/i },
    { label: 'L3', pattern: /\bL3\b/i },
    { label: 'Stage-DAG', pattern: /\b(?:fixed\s+)?Stage[- ]DAG\b/i }
  ];
  var ERA_LABELS_ZH = {
    'foundations': '奠基',
    'evobench': 'EvoBench 与加固（历史）',
    'self-improve': '自我改进闭环',
    'platforms': '平台与收口',
    'rollup': '总集与稳定',
    'compression': '分阶段上下文压缩',
    'agent-workspace-trilogy': 'Agent 工作区三部曲',
    'rule-rebalancing': '规则再平衡',
    'performance-overhaul': '性能重构',
    'self-improvement': '自我改进',
    'major-rollup': '大版本总集',
    'human-voice': '人类表达',
    'plugin-review': '插件评审',
    'developer-experience': '开发者体验',
    'cascade-restoration': '级联恢复',
    'article-synthesis': '文章综合',
    'polish-cycle': '打磨周期',
    'design-cycle': '设计周期',
    'human-surface': '人类界面',
    'init-reliability': '初始化可靠性',
    'checklist-harness': '清单与内置评估'
  };

  var EN = {
    'vt.eyebrow': 'Sole release archive',
    'vt.subtitle': 'Every recorded DevolaFlow release, with current behavior separated from retired history.',
    'vt.jump.current': 'Current releases',
    'vt.jump.history': 'Historical archive',
    'vt.boundary.eyebrow': 'Behavior boundary',
    'vt.boundary.title': 'Current contract vs Historical record',
    'vt.current': 'Current',
    'vt.current.title': 'Checklist rounds + built-in harness',
    'vt.current.body': 'v16.0.0 onward: Project → Wave → Task, one change-driven runtime, checklist evidence, and the built-in harness.',
    'vt.historical': 'Historical',
    'vt.historical.title': 'Retired systems stay archived',
    'vt.historical.body': 'Pre-v16 EvoBench, NineS, L3, and fixed Stage-DAG references are historical release evidence, not current behavior.',
    'vt.controls.eyebrow': 'Archive controls',
    'vt.controls.title': 'Find a release',
    'vt.search.label': 'Search releases',
    'vt.search.placeholder': 'Version, headline, highlight, or metric',
    'vt.scope.aria': 'Release status filter',
    'vt.scope.all': 'All releases',
    'vt.scope.current': 'Current',
    'vt.scope.historical': 'Historical',
    'vt.view.aria': 'Timeline density',
    'vt.view.detailed': 'Detailed',
    'vt.view.compact': 'Compact',
    'vt.era.aria': 'Era filter',
    'vt.era.all': 'All eras',
    'vt.loading': 'Loading the release archive…',
    'vt.status': 'Showing {visible} of {total} releases.',
    'vt.error.title': 'The release archive could not be loaded',
    'vt.error.body': 'Check the console for the explicit fetch or data-validation error.',
    'vt.current.archive': 'Checklist + harness era',
    'vt.current.archive.body': 'Releases on the active three-layer, checklist-anchored product model.',
    'vt.historical.archive': 'Retired-system archive',
    'vt.historical.archive.body': 'Release text is preserved as evidence. EvoBench, NineS, L3, and Stage-DAG language below is retired history.',
    'vt.release.current': 'Current behavior',
    'vt.release.historical': 'Historical release',
    'vt.release.retired': 'Historical/retired terminology in this record: {terms}. These labels do not describe current behavior.',
    'vt.card.expand': 'Show details',
    'vt.card.collapse': 'Hide details',
    'vt.card.highlights': 'Release highlights',
    'vt.card.metrics': 'Recorded metrics',
    'vt.card.links': 'Related pages',
    'vt.era.count': '{count} releases · {range}',
    'vt.section.empty': 'No matching releases in this part of the archive.',
    'vt.empty.title': 'No releases match',
    'vt.empty.body': 'Clear the search or choose a different era or status.',
    'vt.empty.reset': 'Reset filters',
    'vt.cta.eyebrow': 'Continue exploring',
    'vt.cta.title': 'Current system companions',
    'vt.cta.design': 'Design system',
    'vt.cta.system': 'System / framework chain',
    'vt.cta.io': 'I/O / context flow',
    'vt.cta.skill': 'Read SKILL ↗',
    'vt.cta.changelog': 'Source CHANGELOG ↗'
  };

  var ZH = {
    'vt.eyebrow': '唯一发布档案',
    'vt.subtitle': '收录 DevolaFlow 的每个已记录版本，并将当前行为与已退役历史清晰分开。',
    'vt.jump.current': '当前版本',
    'vt.jump.history': '历史档案',
    'vt.boundary.eyebrow': '行为边界',
    'vt.boundary.title': '当前契约与历史记录',
    'vt.current': '当前',
    'vt.current.title': '清单轮次 + 内置评估体系',
    'vt.current.body': '从 v16.0.0 起：Project → Wave → Task、唯一 change-driven 运行时、清单证据与内置评估体系。',
    'vt.historical': '历史',
    'vt.historical.title': '已退役系统保留在档案中',
    'vt.historical.body': 'v16 之前的 EvoBench、NineS、L3 与固定 Stage-DAG 仅是历史发布证据，不代表当前行为。',
    'vt.controls.eyebrow': '档案控制',
    'vt.controls.title': '查找版本',
    'vt.search.label': '搜索版本',
    'vt.search.placeholder': '版本、标题、亮点或指标',
    'vt.scope.aria': '版本状态筛选',
    'vt.scope.all': '全部版本',
    'vt.scope.current': '当前',
    'vt.scope.historical': '历史',
    'vt.view.aria': '时间线密度',
    'vt.view.detailed': '详细',
    'vt.view.compact': '紧凑',
    'vt.era.aria': '时代筛选',
    'vt.era.all': '全部时代',
    'vt.loading': '正在加载发布档案…',
    'vt.status': '显示 {visible} / {total} 个版本。',
    'vt.error.title': '无法加载发布档案',
    'vt.error.body': '请在控制台查看明确的网络或数据校验错误。',
    'vt.current.archive': '清单与内置评估时代',
    'vt.current.archive.body': '采用当前三层、清单锚定产品模型的版本。',
    'vt.historical.archive': '已退役系统档案',
    'vt.historical.archive.body': '发布文本作为证据原样保留；下方 EvoBench、NineS、L3 与 Stage-DAG 均为已退役历史。',
    'vt.release.current': '当前行为',
    'vt.release.historical': '历史版本',
    'vt.release.retired': '本记录中的历史/已退役术语：{terms}。这些标签不描述当前行为。',
    'vt.card.expand': '显示详情',
    'vt.card.collapse': '收起详情',
    'vt.card.highlights': '版本亮点',
    'vt.card.metrics': '已记录指标',
    'vt.card.links': '相关页面',
    'vt.era.count': '{count} 个版本 · {range}',
    'vt.section.empty': '档案的这一部分没有匹配版本。',
    'vt.empty.title': '没有匹配版本',
    'vt.empty.body': '请清除搜索，或选择其他时代或状态。',
    'vt.empty.reset': '重置筛选',
    'vt.cta.eyebrow': '继续探索',
    'vt.cta.title': '当前系统配套页面',
    'vt.cta.design': '设计体系',
    'vt.cta.system': '系统 / 框架链路',
    'vt.cta.io': '输入输出 / 上下文流',
    'vt.cta.skill': '阅读 SKILL ↗',
    'vt.cta.changelog': '查看源 CHANGELOG ↗'
  };

  var state = {
    all: [],
    loaded: false,
    scope: 'all',
    era: 'all',
    query: '',
    view: readStoredView(),
    expandedVersion: null
  };

  if (typeof window.addTranslations !== 'function') {
    console.error('[version-timeline] shared i18n failed to load');
    return;
  }
  window.addTranslations('en', EN);
  window.addTranslations('zh', ZH);

  function t(key) {
    return typeof window.t === 'function' ? window.t(key) : key;
  }

  function interpolate(template, values) {
    return String(template).replace(/\{(\w+)\}/g, function (_, key) {
      return values[key] === undefined ? '{' + key + '}' : values[key];
    });
  }

  function readStoredView() {
    try {
      var stored = window.localStorage.getItem(VIEW_KEY);
      return stored === 'compact' ? 'compact' : 'detailed';
    } catch (error) {
      console.warn('[version-timeline] could not read view preference:', error);
      return 'detailed';
    }
  }

  function writeStoredView(view) {
    try {
      window.localStorage.setItem(VIEW_KEY, view);
    } catch (error) {
      console.warn('[version-timeline] could not save view preference:', error);
    }
  }

  function versionParts(version) {
    return String(version).replace(/^v/, '').split(/[.-]/).map(function (part) {
      return /^\d+$/.test(part) ? Number(part) : part;
    });
  }

  function compareVersions(left, right) {
    var a = versionParts(left);
    var b = versionParts(right);
    var length = Math.max(a.length, b.length);
    for (var index = 0; index < length; index += 1) {
      var av = a[index] === undefined ? 0 : a[index];
      var bv = b[index] === undefined ? 0 : b[index];
      if (typeof av !== typeof bv) {
        av = String(av);
        bv = String(bv);
      }
      if (av < bv) { return -1; }
      if (av > bv) { return 1; }
    }
    return 0;
  }

  function isCurrentRelease(release) {
    var major = Number(versionParts(release.version)[0]);
    return Number.isFinite(major) && major >= CURRENT_MAJOR;
  }

  function validateVersions(payload) {
    if (!Array.isArray(payload)) {
      throw new Error('versions.json root must be an array');
    }
    var required = ['version', 'date', 'era', 'headline', 'summary', 'highlights', 'metrics'];
    payload.forEach(function (release, index) {
      if (!release || typeof release !== 'object') {
        throw new Error('versions.json entry ' + index + ' must be an object');
      }
      required.forEach(function (field) {
        if (!Object.prototype.hasOwnProperty.call(release, field)) {
          throw new Error('versions.json entry ' + index + ' is missing "' + field + '"');
        }
      });
      if (!Array.isArray(release.highlights)) {
        throw new Error('versions.json entry ' + index + ' has non-array highlights');
      }
      if (!release.metrics || typeof release.metrics !== 'object' || Array.isArray(release.metrics)) {
        throw new Error('versions.json entry ' + index + ' has invalid metrics');
      }
    });
    return payload.slice().sort(function (left, right) {
      var versionOrder = compareVersions(right.version, left.version);
      return versionOrder || String(right.date).localeCompare(String(left.date));
    });
  }

  function eraLabel(era) {
    var lang = document.documentElement.getAttribute('data-lang') || 'en';
    if (lang === 'zh' && ERA_LABELS_ZH[era]) {
      return ERA_LABELS_ZH[era];
    }
    if (era === 'evobench') {
      return 'EvoBench & Hardening (Historical)';
    }
    return String(era)
      .split('-')
      .map(function (part) {
        return part ? part.charAt(0).toUpperCase() + part.slice(1) : '';
      })
      .join(' ');
  }

  function searchableText(release) {
    return [
      release.version,
      release.date,
      release.era,
      release.headline,
      release.summary,
      release.highlights.join(' '),
      JSON.stringify(release.metrics)
    ].join(' ').toLowerCase();
  }

  function filteredReleases() {
    return state.all.filter(function (release) {
      var current = isCurrentRelease(release);
      if (state.scope === 'current' && !current) { return false; }
      if (state.scope === 'historical' && current) { return false; }
      if (state.era !== 'all' && release.era !== state.era) { return false; }
      return !state.query || searchableText(release).indexOf(state.query) !== -1;
    });
  }

  function retiredTerms(release) {
    if (isCurrentRelease(release)) { return []; }
    var text = JSON.stringify(release);
    return RETIRED_TERMS.filter(function (term) {
      return term.pattern.test(text);
    }).map(function (term) {
      return term.label;
    });
  }

  function element(tag, className, text) {
    var node = document.createElement(tag);
    if (className) { node.className = className; }
    if (text !== undefined) { node.textContent = text; }
    return node;
  }

  function renderEraFilters() {
    var host = document.getElementById('vt-era-filters');
    if (!host) { return; }
    host.replaceChildren();

    var eras = [];
    state.all.forEach(function (release) {
      if (eras.indexOf(release.era) === -1) { eras.push(release.era); }
    });

    addEraButton(host, 'all', t('vt.era.all'));
    eras.forEach(function (era) {
      addEraButton(host, era, eraLabel(era));
    });
  }

  function addEraButton(host, era, label) {
    var button = element('button', 'vt-era-filter' + (state.era === era ? ' is-active' : ''), label);
    button.type = 'button';
    button.dataset.era = era;
    button.setAttribute('aria-pressed', state.era === era ? 'true' : 'false');
    button.addEventListener('click', function () {
      state.era = era;
      state.expandedVersion = null;
      render();
    });
    host.appendChild(button);
  }

  function groupByEra(releases) {
    var groups = [];
    releases.forEach(function (release) {
      var group = groups.find(function (candidate) {
        return candidate.era === release.era;
      });
      if (!group) {
        group = { era: release.era, releases: [] };
        groups.push(group);
      }
      group.releases.push(release);
    });
    return groups;
  }

  function renderArchive(hostId, releases, historical) {
    var host = document.getElementById(hostId);
    if (!host) { return; }
    host.replaceChildren();

    if (!releases.length) {
      host.appendChild(element('p', 'vt-section-empty', t('vt.section.empty')));
      return;
    }

    groupByEra(releases).forEach(function (group) {
      var section = element('section', 'vt-era-group');
      section.dataset.era = group.era;

      var header = element('div', 'vt-era-heading');
      header.appendChild(element('h3', '', eraLabel(group.era)));
      var newest = group.releases[0].version;
      var oldest = group.releases[group.releases.length - 1].version;
      header.appendChild(element(
        'p',
        '',
        interpolate(t('vt.era.count'), {
          count: group.releases.length,
          range: 'v' + oldest + (oldest === newest ? '' : ' → v' + newest)
        })
      ));
      section.appendChild(header);

      var rail = element('ol', 'vt-rail');
      group.releases.forEach(function (release) {
        rail.appendChild(renderCard(release, historical));
      });
      section.appendChild(rail);
      host.appendChild(section);
    });
  }

  function renderCard(release, historical) {
    var expanded = state.expandedVersion === release.version;
    var card = element('li', 'vt-card' + (expanded ? ' is-expanded' : ''));
    card.dataset.version = release.version;

    var meta = element('div', 'vt-card-meta');
    meta.appendChild(element('span', 'vt-version', 'v' + release.version));
    var time = element('time', '', release.date);
    time.dateTime = release.date;
    meta.appendChild(time);
    meta.appendChild(element(
      'span',
      'vt-release-badge ' + (historical ? 'is-historical' : 'is-current'),
      historical ? t('vt.release.historical') : t('vt.release.current')
    ));
    card.appendChild(meta);

    card.appendChild(element('h4', 'vt-headline', release.headline));
    card.appendChild(element('p', 'vt-summary', release.summary));

    var terms = retiredTerms(release);
    if (terms.length) {
      card.appendChild(element(
        'p',
        'vt-retired-note',
        interpolate(t('vt.release.retired'), { terms: terms.join(', ') })
      ));
    }

    var detailId = 'vt-detail-' + String(release.version).replace(/[^a-z0-9]+/gi, '-');
    var button = element(
      'button',
      'vt-expand',
      expanded ? t('vt.card.collapse') : t('vt.card.expand')
    );
    button.type = 'button';
    button.setAttribute('aria-expanded', expanded ? 'true' : 'false');
    button.setAttribute('aria-controls', detailId);
    button.addEventListener('click', function () {
      state.expandedVersion = expanded ? null : release.version;
      renderArchives();
      var refreshed = document.querySelector('[data-version="' + release.version + '"] .vt-expand');
      if (refreshed) { refreshed.focus(); }
    });
    card.appendChild(button);

    var detail = element('div', 'vt-detail');
    detail.id = detailId;
    detail.hidden = !expanded;

    if (release.highlights.length) {
      detail.appendChild(element('h5', '', t('vt.card.highlights')));
      var highlights = element('ul', 'vt-highlights');
      release.highlights.forEach(function (highlight) {
        highlights.appendChild(element('li', '', highlight));
      });
      detail.appendChild(highlights);
    }

    var metricKeys = Object.keys(release.metrics);
    if (metricKeys.length) {
      detail.appendChild(element('h5', '', t('vt.card.metrics')));
      var metrics = element('dl', 'vt-metrics');
      metricKeys.forEach(function (key) {
        var item = element('div', 'vt-metric');
        item.appendChild(element('dt', '', key.replace(/_/g, ' ')));
        item.appendChild(element('dd', '', String(release.metrics[key])));
        metrics.appendChild(item);
      });
      detail.appendChild(metrics);
    }

    if (Array.isArray(release.links) && release.links.length) {
      detail.appendChild(element('h5', '', t('vt.card.links')));
      var links = element('div', 'vt-links');
      release.links.forEach(function (link) {
        var anchor = element('a', '', link.label || link.href || '');
        anchor.href = safeHref(link.href);
        links.appendChild(anchor);
      });
      detail.appendChild(links);
    }

    card.appendChild(detail);
    return card;
  }

  function safeHref(href) {
    var value = String(href || '');
    if (/^(?:https:\/\/|\.{0,2}\/|#)/.test(value)) { return value; }
    console.warn('[version-timeline] ignored unsafe release link:', value);
    return '#';
  }

  function renderArchives() {
    if (!state.loaded) {
      var loadingEmpty = document.getElementById('vt-empty');
      var loadingStatus = document.getElementById('vt-status');
      if (loadingEmpty) { loadingEmpty.hidden = true; }
      if (loadingStatus) {
        loadingStatus.setAttribute('data-i18n', 'vt.loading');
        loadingStatus.textContent = t('vt.loading');
      }
      return;
    }

    var visible = filteredReleases();
    var current = visible.filter(isCurrentRelease);
    var historical = visible.filter(function (release) {
      return !isCurrentRelease(release);
    });

    renderArchive('vt-current-eras', current, false);
    renderArchive('vt-historical-eras', historical, true);

    var currentSection = document.getElementById('current-releases');
    var historicalSection = document.getElementById('historical-releases');
    if (currentSection) { currentSection.hidden = state.scope === 'historical'; }
    if (historicalSection) { historicalSection.hidden = state.scope === 'current'; }

    var empty = document.getElementById('vt-empty');
    if (empty) { empty.hidden = visible.length !== 0; }
    updateStatus(visible.length);
  }

  function updateStatus(visibleCount) {
    var status = document.getElementById('vt-status');
    if (!status) { return; }
    status.removeAttribute('data-i18n');
    status.textContent = interpolate(t('vt.status'), {
      visible: visibleCount,
      total: state.all.length
    });
  }

  function render() {
    document.body.classList.toggle('is-compact', state.view === 'compact');
    document.querySelectorAll('.vt-filter').forEach(function (button) {
      var active = button.dataset.scope === state.scope;
      button.classList.toggle('is-active', active);
      button.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
    document.querySelectorAll('.vt-view').forEach(function (button) {
      var active = button.dataset.view === state.view;
      button.classList.toggle('is-active', active);
      button.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
    renderEraFilters();
    renderArchives();
  }

  function wireControls() {
    var search = document.getElementById('vt-search');
    if (search) {
      search.addEventListener('input', function () {
        state.query = search.value.slice(0, 80).trim().toLowerCase();
        state.expandedVersion = null;
        renderArchives();
      });
    }

    document.querySelectorAll('.vt-filter').forEach(function (button) {
      button.addEventListener('click', function () {
        state.scope = button.dataset.scope || 'all';
        state.expandedVersion = null;
        render();
      });
    });

    document.querySelectorAll('.vt-view').forEach(function (button) {
      button.addEventListener('click', function () {
        state.view = button.dataset.view === 'compact' ? 'compact' : 'detailed';
        writeStoredView(state.view);
        render();
      });
    });

    var reset = document.getElementById('vt-reset');
    if (reset) {
      reset.addEventListener('click', function () {
        state.scope = 'all';
        state.era = 'all';
        state.query = '';
        state.expandedVersion = null;
        if (search) { search.value = ''; }
        render();
        if (search) { search.focus(); }
      });
    }

    document.addEventListener('devolaflow:languagechange', function () {
      if (state.all.length) { render(); }
    });
  }

  function showError(error) {
    console.error('[version-timeline] failed to load versions.json:', error);
    var status = document.getElementById('vt-status');
    if (status) {
      status.removeAttribute('data-i18n');
      status.textContent = t('vt.error.title');
      status.classList.add('is-error');
    }
    var panel = document.getElementById('vt-error');
    var detail = document.getElementById('vt-error-detail');
    if (panel) { panel.hidden = false; }
    if (detail) { detail.textContent = error && error.message ? error.message : String(error); }
    var current = document.getElementById('current-releases');
    var historical = document.getElementById('historical-releases');
    if (current) { current.hidden = true; }
    if (historical) { historical.hidden = true; }
  }

  function boot() {
    wireControls();
    render();
    fetch('versions.json', { cache: 'no-cache' })
      .then(function (response) {
        if (!response.ok) {
          throw new Error('HTTP ' + response.status + ' ' + response.statusText + ' for versions.json');
        }
        return response.json();
      })
      .then(function (payload) {
        state.all = validateVersions(payload);
        state.loaded = true;
        render();
      })
      .catch(showError);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
