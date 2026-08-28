(function () {
  'use strict';

  // Presentation-only translations keyed by canonical seed ID. Membership and
  // all structural data come exclusively from DEVOLAFLOW_SEED_CATALOG.
  const ZH_DESCRIPTIONS = {
    'hotfix': '快速完成缺陷分诊、最小修复、聚焦测试与快速发布。',
    'research-only': '以经验证的报告完成纯研究与比较。',
    'design-only': '由研究支撑的设计与架构评审。',
    'documentation-only': '文档调研、撰写与评审。',
    'spike-poc': '带有明确评估结论的有界一次性原型。',
    'refactoring': '由证据支撑的技术债重构。',
    'feature-enhancement': '通过设计、实现与发布证据扩展现有功能。',
    'full-pipeline': '绿地或端到端构建的分解知识。',
    'performance-optimization': '分析、优化、基准测试并验证可度量的性能。',
    'security-audit': '威胁建模、扫描、分析、修复与验证。',
    'research-design-review-refine': '迭代开展研究、设计、评审、修订与知识缺口闭环。',
    'dependency-setup': '带有有界验证的环境与工具设置。',
    'onboarding': '通过分析、文档、设置与验证完成贡献者入门。',
    'demo-showcase': '带有视觉质量证据的演示与展示分解知识。',
    'product-verification': '覆盖视觉、交互、无障碍与验收维度的用户侧验证。',
    'entropy-cleanup': '陈旧文档与漂移清理知识。',
    'migration': '包含验证、切换与回滚准备的系统化迁移。',
    'skill-optimization': '代理技能分析、优化、验证与文档知识。',
    'self-update': '引用依赖研究、集成、测试与评估知识。',
    'nines-assisted': '由内置评估体系支撑的历史研究与迭代分解知识。',
    'repo-init': '仓库工作区与治理初始化知识。',
    'change-driven': '唯一的可执行清单轮次生命周期运行时。',
    'web-design': '前端设计、实现、修订与确定性验证知识。'
  };

  const catalog = window.DEVOLAFLOW_SEED_CATALOG;
  const catalogIsValid = validateCatalog(catalog);
  const SEEDS = catalogIsValid ? catalog.seeds : [];
  const state = {
    selectedName: SEEDS.length ? SEEDS[0].name : null,
    search: '',
    category: 'all',
    visible: SEEDS.slice()
  };

  function validateCatalog(candidate) {
    if (!candidate ||
        candidate.schema_version !== '1.0' ||
        candidate.record_count !== 27 ||
        !Array.isArray(candidate.seeds) ||
        candidate.seeds.length !== 27) {
      return false;
    }
    const names = new Set();
    return candidate.seeds.every(function (seed) {
      if (!seed ||
          seed.registry_schema_version !== '3.0' ||
          typeof seed.seed_schema_version !== 'string' ||
          !seed.source ||
          typeof seed.source !== 'object' ||
          typeof seed.name !== 'string' ||
          typeof seed.category !== 'string' ||
          typeof seed.description !== 'string' ||
          typeof seed.seed_path !== 'string' ||
          !Array.isArray(seed.tags) ||
          !Array.isArray(seed.partitions) ||
          names.has(seed.name)) {
        return false;
      }
      names.add(seed.name);
      return seed.partitions.every(function (partition) {
        return partition &&
          typeof partition.key === 'string' &&
          typeof partition.title === 'string' &&
          Array.isArray(partition.source_stages) &&
          partition.source_stages.every(function (source) {
            return source &&
              typeof source.id === 'string' &&
              typeof source.primitive === 'string';
          }) &&
          Array.isArray(partition.assertions) &&
          partition.assertions.every(function (assertion) {
            return assertion &&
              typeof assertion.key === 'string' &&
              typeof assertion.statement === 'string' &&
              typeof assertion.suggested_priority === 'string' &&
              assertion.verify &&
              typeof assertion.verify.mode === 'string';
          });
      });
    });
  }

  function text(key) {
    return typeof window.t === 'function' ? window.t(key) : key;
  }

  function isChinese() {
    return document.documentElement.getAttribute('data-lang') === 'zh';
  }

  function seedDescription(seed) {
    if (isChinese() && ZH_DESCRIPTIONS[seed.name]) {
      return ZH_DESCRIPTIONS[seed.name];
    }
    return seed.description;
  }

  function makeElement(tag, className, content) {
    const element = document.createElement(tag);
    if (className) {
      element.className = className;
    }
    if (content !== undefined) {
      element.textContent = content;
    }
    return element;
  }

  function categoryLabel(category) {
    return text('seed.category.' + category);
  }

  function sourceCount(seed) {
    return seed.partitions.reduce(function (total, partition) {
      return total + partition.source_stages.length;
    }, 0);
  }

  function assertionCount(seed) {
    return seed.partitions.reduce(function (total, partition) {
      return total + partition.assertions.length;
    }, 0);
  }

  function populateCategories() {
    const select = document.getElementById('category-filter');
    const categories = [];
    SEEDS.forEach(function (seed) {
      if (categories.indexOf(seed.category) === -1) {
        categories.push(seed.category);
      }
    });

    select.replaceChildren();
    const all = makeElement('option', '', text('seed.allCategories'));
    all.value = 'all';
    select.appendChild(all);
    categories.forEach(function (category) {
      const option = makeElement('option', '', categoryLabel(category));
      option.value = category;
      select.appendChild(option);
    });
    select.value = state.category;
  }

  function filterSeeds() {
    const query = state.search.trim().toLocaleLowerCase();
    state.visible = SEEDS.filter(function (seed) {
      if (state.category !== 'all' && seed.category !== state.category) {
        return false;
      }
      if (!query) {
        return true;
      }
      const searchable = [
        seed.name,
        seed.category,
        seed.description,
        ZH_DESCRIPTIONS[seed.name] || '',
        seed.tags.join(' ')
      ];
      seed.partitions.forEach(function (partition) {
        searchable.push(partition.title);
        partition.assertions.forEach(function (assertion) {
          searchable.push(assertion.statement);
        });
      });
      return searchable.join(' ').toLocaleLowerCase().indexOf(query) !== -1;
    });

    if (state.visible.length &&
        !state.visible.some(function (seed) { return seed.name === state.selectedName; })) {
      state.selectedName = state.visible[0].name;
    }
  }

  function selectSeed(name, focusSelected) {
    if (!state.visible.some(function (seed) { return seed.name === name; })) {
      return;
    }
    state.selectedName = name;
    renderIndex();
    renderDetail();
    if (focusSelected) {
      const selected = document.querySelector('.seed-row[aria-pressed="true"]');
      if (selected) {
        selected.focus();
      }
    }
  }

  function handleIndexKeydown(event) {
    const buttons = Array.from(document.querySelectorAll('.seed-row'));
    const current = buttons.indexOf(event.currentTarget);
    let next = current;
    if (event.key === 'ArrowDown') {
      next = Math.min(current + 1, buttons.length - 1);
    } else if (event.key === 'ArrowUp') {
      next = Math.max(current - 1, 0);
    } else if (event.key === 'Home') {
      next = 0;
    } else if (event.key === 'End') {
      next = buttons.length - 1;
    } else {
      return;
    }
    event.preventDefault();
    if (buttons[next]) {
      selectSeed(buttons[next].dataset.name, true);
    }
  }

  function renderIndex() {
    const list = document.getElementById('seed-list');
    const empty = document.getElementById('empty-state');
    list.replaceChildren();
    empty.hidden = state.visible.length !== 0;

    state.visible.forEach(function (seed) {
      const item = document.createElement('li');
      const button = makeElement('button', 'seed-row');
      button.type = 'button';
      button.dataset.name = seed.name;
      button.setAttribute('aria-pressed', String(seed.name === state.selectedName));
      button.appendChild(
        makeElement('span', 'seed-number', String(SEEDS.indexOf(seed) + 1).padStart(2, '0'))
      );
      button.appendChild(makeElement('span', 'seed-name', seed.name));
      button.appendChild(makeElement('span', 'seed-category', categoryLabel(seed.category)));
      button.addEventListener('click', function () {
        selectSeed(seed.name, false);
      });
      button.addEventListener('keydown', handleIndexKeydown);
      item.appendChild(button);
      list.appendChild(item);
    });

    document.getElementById('result-summary').textContent = text('seed.results')
      .replace('{visible}', String(state.visible.length))
      .replace('{total}', String(SEEDS.length));
  }

  function makeAssertion(assertion) {
    const item = makeElement('li', 'assertion-item');
    item.appendChild(makeElement('p', 'assertion-statement', assertion.statement));

    const meta = makeElement('div', 'assertion-meta');
    const priority = makeElement('span');
    priority.appendChild(document.createTextNode(text('seed.priority') + ' '));
    priority.appendChild(makeElement('code', '', assertion.suggested_priority));
    meta.appendChild(priority);

    const verification = makeElement('span');
    verification.appendChild(document.createTextNode(text('seed.verification') + ' · '));
    verification.appendChild(document.createTextNode(text('seed.verify.' + assertion.verify.mode)));
    meta.appendChild(verification);
    if (assertion.verify.template) {
      meta.appendChild(makeElement('code', '', assertion.verify.template));
    }
    item.appendChild(meta);
    return item;
  }

  function makePartition(partition, index) {
    const section = makeElement('section', 'partition');
    const heading = makeElement('div', 'partition-title');
    heading.appendChild(makeElement('span', '', String(index + 1).padStart(2, '0')));
    heading.appendChild(makeElement('h4', '', partition.title));
    section.appendChild(heading);

    const assertions = makeElement('ul', 'assertion-list');
    partition.assertions.forEach(function (assertion) {
      assertions.appendChild(makeAssertion(assertion));
    });
    section.appendChild(assertions);

    const provenance = makeElement('div', 'provenance');
    provenance.appendChild(makeElement('span', 'provenance-label', text('seed.sourceStages')));
    const sources = makeElement('ul', 'source-list');
    partition.source_stages.forEach(function (source) {
      const item = document.createElement('li');
      item.appendChild(makeElement('code', '', source.id + ' · ' + source.primitive));
      sources.appendChild(item);
    });
    provenance.appendChild(sources);
    section.appendChild(provenance);
    return section;
  }

  function renderDetail() {
    const detail = document.getElementById('seed-detail');
    const seed = SEEDS.find(function (candidate) {
      return candidate.name === state.selectedName;
    });
    detail.hidden = !seed || state.visible.length === 0;
    if (!seed || state.visible.length === 0) {
      return;
    }

    document.getElementById('detail-name').textContent = seed.name;
    document.getElementById('detail-category').textContent = categoryLabel(seed.category);
    document.getElementById('detail-description').textContent = seedDescription(seed);
    document.getElementById('partition-count').textContent = String(seed.partitions.length);
    document.getElementById('assertion-count').textContent = String(assertionCount(seed));
    document.getElementById('source-count').textContent = String(sourceCount(seed));

    const partitions = document.getElementById('partition-list');
    partitions.replaceChildren();
    seed.partitions.forEach(function (partition, index) {
      partitions.appendChild(makePartition(partition, index));
    });
  }

  function updateAriaLabels() {
    document.querySelectorAll('[data-i18n-aria-label]').forEach(function (element) {
      element.setAttribute('aria-label', text(element.getAttribute('data-i18n-aria-label')));
    });
  }

  function render() {
    populateCategories();
    filterSeeds();
    renderIndex();
    renderDetail();
    updateAriaLabels();
  }

  function showCatalogError() {
    console.warn('[workflow-visualizer] generated seed catalog is unavailable or malformed');
    const message = text('seed.catalogError');
    const summary = document.getElementById('result-summary');
    const list = document.getElementById('seed-list');
    const detail = document.getElementById('seed-detail');
    const error = makeElement('li', 'empty-state', message);
    error.setAttribute('role', 'alert');
    summary.textContent = message;
    list.replaceChildren(error);
    detail.hidden = true;
    document.getElementById('seed-search').disabled = true;
    document.getElementById('category-filter').disabled = true;
  }

  function handleLanguageChange() {
    if (!catalogIsValid) {
      showCatalogError();
      return;
    }
    render();
  }

  function init() {
    document.addEventListener('devolaflow:languagechange', handleLanguageChange);
    if (!catalogIsValid) {
      showCatalogError();
      return;
    }
    const search = document.getElementById('seed-search');
    const category = document.getElementById('category-filter');
    search.addEventListener('input', function () {
      state.search = search.value;
      filterSeeds();
      renderIndex();
      renderDetail();
    });
    category.addEventListener('change', function () {
      state.category = category.value;
      filterSeeds();
      renderIndex();
      renderDetail();
    });
    render();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
