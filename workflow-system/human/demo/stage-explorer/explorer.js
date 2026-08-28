/**
 * Primitive Explorer — bilingual, finite disclosure of historical provenance.
 * Input and Output descriptions are conceptual authoring vocabulary, not APIs.
 */
(function () {
  'use strict';

  var EN = {
    'exp.hero.eyebrow': 'Provenance I/O companion',
    'exp.hero.count': '14 historical',
    'exp.hero.title': 'primitive labels',
    'exp.hero.tagline': 'A finite vocabulary reference for seed authors—not an execution view.',
    'exp.contract.kicker': 'Read this boundary first',
    'exp.contract.body': 'These 14 historical labels are non-executable authoring vocabulary. They are not layers, not an ordered pipeline, and do not select teams or gates. The current runtime is change-driven with user-confirmed checklist rounds.',
    'exp.index.eyebrow': 'Historical taxonomy',
    'exp.index.title': 'Filter the vocabulary',
    'exp.index.desc': 'Category groups are for scanning only. Select one label to disclose its conceptual Input, Output, authoring meaning, and seed usage.',
    'exp.detail.status': 'Provenance only',
    'exp.detail.contractNote': 'Conceptual authoring contract—not a live callable stage API.',
    'exp.detail.input': 'Input',
    'exp.detail.output': 'Output',
    'exp.detail.seedUsage': 'Seed usage',
    'exp.runtime.eyebrow': 'Vocabulary versus runtime',
    'exp.runtime.title': 'Provenance informs authoring; checklist fields control execution',
    'exp.runtime.desc': 'A seed may record source_stages with an ID and primitive label. L0 materializes actual assertions, priorities, verification, dependencies, and file ownership before the sole runtime executes.',
    'exp.runtime.provenanceLabel': 'Historical seed provenance',
    'exp.runtime.provenanceText': 'Preserves where decomposition knowledge came from. Sequence is presentation-only.',
    'exp.runtime.runtimeLabel': 'Current execution contract',
    'exp.runtime.runtimeText': 'Confirmed assertions, evidence checks, dependencies, and ownership determine work.',
    'exp.links.eyebrow': 'Canonical sources',
    'exp.links.title': 'Continue with the active contracts',
    'exp.link.io': 'Canonical I/O',
    'exp.link.ioDesc': 'typed messages and artifact boundaries',
    'exp.link.seeds': 'Seed Library ↗',
    'exp.link.seedsDesc': '27 declarative checklist seeds',
    'exp.link.system': 'System',
    'exp.link.systemDesc': 'current Project → Wave → Task model',
    'exp.link.skill': 'Read SKILL.md ↗',
    'exp.link.skillDesc': 'canonical orchestration contract',
    'exp.aria.heroLinks': 'Primary companion links',
    'exp.aria.filters': 'Filter primitive labels by category',
    'exp.aria.grid': 'Historical primitive labels',
    'exp.aria.sourceLinks': 'Primitive companion and source links',
    'exp.filter.all': 'All labels',
    'exp.category.discover': 'Discover',
    'exp.category.shape': 'Shape',
    'exp.category.build': 'Build',
    'exp.category.verify': 'Verify',
    'exp.category.deliver': 'Deliver',
    'exp.category.control': 'Control',
    'exp.count.visible': '{visible} of {total} labels',
    'exp.card.seedCount': '{count} / 27 seeds',
    'exp.card.open': 'Show {label} conceptual I/O and seed usage',
    'exp.seed.count': '{count} seeds reference this label',
    'exp.seed.none': 'No current seed references this label',
    'exp.seed.note': 'Current source_stages references across the 27 shipped seeds.',
    'exp.seed.noneNote': 'Retained because SKILL.md and the meta-framework preserve it in the canonical historical taxonomy.',
    'exp.seed.noneItem': 'No current seed reference',
    'exp.catalog.error': 'The generated seed catalog is unavailable or malformed. Primitive membership cannot be shown.'
  };

  var ZH = {
    'exp.hero.eyebrow': '溯源输入输出配套页',
    'exp.hero.count': '14 个历史',
    'exp.hero.title': '原语标签',
    'exp.hero.tagline': '面向清单种子作者的有限词汇参考，而非执行视图。',
    'exp.contract.kicker': '请先阅读此边界',
    'exp.contract.body': '这 14 个历史标签是不可执行的编写词汇。它们不是层级，不是有序流水线，也不选择团队或门控。当前运行时是 change-driven，并执行用户确认的清单轮次。',
    'exp.index.eyebrow': '历史分类',
    'exp.index.title': '筛选词汇',
    'exp.index.desc': '分类仅用于浏览。选择一个标签，即可查看其概念输入、输出、编写含义与清单种子用法。',
    'exp.detail.status': '仅限溯源',
    'exp.detail.contractNote': '概念编写契约，不是可实时调用的阶段 API。',
    'exp.detail.input': '输入',
    'exp.detail.output': '输出',
    'exp.detail.seedUsage': '清单种子用法',
    'exp.runtime.eyebrow': '词汇与运行时',
    'exp.runtime.title': '溯源辅助编写；清单字段控制执行',
    'exp.runtime.desc': '清单种子可通过 ID 与原语标签记录 source_stages。唯一运行时执行前，L0 会实体化实际断言、优先级、验证、依赖与文件所有权。',
    'exp.runtime.provenanceLabel': '历史清单种子溯源',
    'exp.runtime.provenanceText': '保留分解知识的来源。序列仅用于展示。',
    'exp.runtime.runtimeLabel': '当前执行契约',
    'exp.runtime.runtimeText': '经确认的断言、证据检查、依赖与所有权决定实际工作。',
    'exp.links.eyebrow': '规范来源',
    'exp.links.title': '继续阅读当前有效契约',
    'exp.link.io': '规范输入输出',
    'exp.link.ioDesc': '类型化消息与制品边界',
    'exp.link.seeds': '清单种子库 ↗',
    'exp.link.seedsDesc': '27 个声明式清单种子',
    'exp.link.system': '系统',
    'exp.link.systemDesc': '当前 Project → Wave → Task 模型',
    'exp.link.skill': '阅读 SKILL.md ↗',
    'exp.link.skillDesc': '规范编排契约',
    'exp.aria.heroLinks': '主要配套链接',
    'exp.aria.filters': '按分类筛选原语标签',
    'exp.aria.grid': '历史原语标签',
    'exp.aria.sourceLinks': '原语配套与来源链接',
    'exp.filter.all': '全部标签',
    'exp.category.discover': '发现',
    'exp.category.shape': '塑形',
    'exp.category.build': '构建',
    'exp.category.verify': '验证',
    'exp.category.deliver': '交付',
    'exp.category.control': '控制',
    'exp.count.visible': '显示 {visible} / {total} 个标签',
    'exp.card.seedCount': '{count} / 27 个清单种子',
    'exp.card.open': '查看 {label} 的概念输入输出与清单种子用法',
    'exp.seed.count': '{count} 个清单种子引用此标签',
    'exp.seed.none': '当前没有清单种子引用此标签',
    'exp.seed.note': '27 个已发布清单种子中的当前 source_stages 引用。',
    'exp.seed.noneNote': 'SKILL.md 与元框架将其保留在规范历史分类中，因此本页仍予收录。',
    'exp.seed.noneItem': '当前无清单种子引用',
    'exp.catalog.error': '生成的清单种子目录不可用或格式错误，无法显示原语成员关系。'
  };

  var CATEGORIES = ['discover', 'shape', 'build', 'verify', 'deliver', 'control'];
  var CANONICAL_LABELS = [
    'research', 'analyze', 'design', 'plan', 'implement', 'refine', 'review',
    'test', 'validate', 'verify', 'release', 'deploy', 'monitor', 'gate'
  ];

  var PRIMITIVES = [
    {
      id: 'research',
      category: 'discover',
      meaning: {
        en: 'Gather evidence, sources, prior art, and comparisons that can support a checklist assertion.',
        zh: '收集可支撑清单断言的证据、来源、既有工作与比较信息。'
      },
      input: {
        en: 'A bounded question, scope, comparison criteria, and source hints.',
        zh: '有边界的问题、范围、比较标准与来源提示。'
      },
      output: {
        en: 'Cited findings, comparisons, constraints, risks, and explicit knowledge gaps.',
        zh: '带引用的发现、比较、约束、风险与明确知识缺口。'
      }
    },
    {
      id: 'analyze',
      category: 'discover',
      meaning: {
        en: 'Inspect existing artifacts or evidence and organize what is already observable.',
        zh: '检查现有制品或证据，并组织已经可以观察到的信息。'
      },
      input: {
        en: 'Code, documents, logs, metrics, dependencies, or a stated baseline.',
        zh: '代码、文档、日志、指标、依赖项或已声明基线。'
      },
      output: {
        en: 'Structured findings, hotspots, gaps, severity, and a priority ranking.',
        zh: '结构化发现、热点、缺口、严重度与优先级排序。'
      }
    },
    {
      id: 'design',
      category: 'shape',
      meaning: {
        en: 'Define decisions or decomposition knowledge before implementation claims are made.',
        zh: '在提出实施主张前，定义决策或分解知识。'
      },
      input: {
        en: 'Confirmed goals, research evidence, requirements, constraints, and trade-offs.',
        zh: '已确认目标、研究证据、需求、约束与取舍。'
      },
      output: {
        en: 'Decisions, interfaces, schemas, specifications, and recorded trade-offs.',
        zh: '决策、接口、模式、规格与已记录取舍。'
      }
    },
    {
      id: 'plan',
      category: 'shape',
      meaning: {
        en: 'Propose bounded work units and relationships for user confirmation.',
        zh: '提出有边界的工作单元及其关系，供用户确认。'
      },
      input: {
        en: 'A goal or design, known risks, constraints, priorities, and repository context.',
        zh: '目标或设计、已知风险、约束、优先级与仓库上下文。'
      },
      output: {
        en: 'Candidate checklist items, dependencies, ownership boundaries, and verification modes.',
        zh: '候选清单项、依赖、所有权边界与验证模式。'
      }
    },
    {
      id: 'implement',
      category: 'build',
      meaning: {
        en: 'Change artifacts to satisfy an authorized checklist assertion.',
        zh: '修改制品以满足已授权的清单断言。'
      },
      input: {
        en: 'An atomic task, owned files, acceptance criteria, constraints, and relevant context.',
        zh: '原子任务、拥有的文件、验收条件、约束与相关上下文。'
      },
      output: {
        en: 'Changed artifacts, a bounded diff, checks performed, and explicit unresolved work.',
        zh: '变更制品、有边界的差异、已执行检查与明确未解决工作。'
      }
    },
    {
      id: 'refine',
      category: 'build',
      meaning: {
        en: 'Correct or improve artifacts in response to bounded findings.',
        zh: '根据有边界的发现修正或改进制品。'
      },
      input: {
        en: 'Specific findings, affected artifacts, allowed scope, and prior verification evidence.',
        zh: '具体发现、受影响制品、允许范围与先前验证证据。'
      },
      output: {
        en: 'Updated artifacts, closed findings, new evidence, and remaining exceptions.',
        zh: '更新后的制品、已闭合发现、新证据与剩余例外。'
      }
    },
    {
      id: 'review',
      category: 'verify',
      meaning: {
        en: 'Inspect quality, correctness, risks, or contract fit without silently changing the artifact.',
        zh: '检查质量、正确性、风险或契约符合度，不静默修改制品。'
      },
      input: {
        en: 'Artifacts, acceptance criteria, applicable rules, and a declared review scope.',
        zh: '制品、验收条件、适用规则与已声明审查范围。'
      },
      output: {
        en: 'Severity-classified findings, evidence references, and a bounded verdict.',
        zh: '按严重度分类的发现、证据引用与有边界的判定。'
      }
    },
    {
      id: 'test',
      category: 'verify',
      meaning: {
        en: 'Run specified checks against artifacts and record reproducible results.',
        zh: '针对制品运行指定检查，并记录可复现结果。'
      },
      input: {
        en: 'Artifact references, named suites or commands, thresholds, and a timeout.',
        zh: '制品引用、具名测试套件或命令、阈值与超时。'
      },
      output: {
        en: 'Exit states, failures, measurements, coverage where relevant, and command evidence.',
        zh: '退出状态、失败、测量值、相关覆盖率与命令证据。'
      }
    },
    {
      id: 'validate',
      category: 'verify',
      meaning: {
        en: 'Check whether supplied evidence satisfies a stated requirement or readiness condition.',
        zh: '检查所提供证据是否满足已声明需求或就绪条件。'
      },
      input: {
        en: 'Acceptance criteria, findings, test evidence, waivers, and required thresholds.',
        zh: '验收条件、发现、测试证据、豁免与必需阈值。'
      },
      output: {
        en: 'Satisfied and unmet criteria, evidence gaps, and an explicit readiness result.',
        zh: '已满足与未满足条件、证据缺口与明确就绪结果。'
      }
    },
    {
      id: 'verify',
      category: 'verify',
      meaning: {
        en: 'Confirm observable behavior or a user-facing assertion with direct evidence.',
        zh: '用直接证据确认可观察行为或面向用户的断言。'
      },
      input: {
        en: 'An assertion, expected behavior, target environment, and bounded verification method.',
        zh: '断言、预期行为、目标环境与有边界的验证方法。'
      },
      output: {
        en: 'Observed behavior, pass or discrepancy evidence, and reproducible notes.',
        zh: '观察到的行为、通过或差异证据与可复现说明。'
      }
    },
    {
      id: 'release',
      category: 'deliver',
      meaning: {
        en: 'Prepare an approved artifact set for a named distribution boundary.',
        zh: '为具名分发边界准备已批准的制品集合。'
      },
      input: {
        en: 'Release-ready artifacts, version policy, approvals, and required release notes.',
        zh: '发布就绪制品、版本策略、批准与必需发布说明。'
      },
      output: {
        en: 'A versioned package or record, changelog evidence, and distribution references.',
        zh: '带版本的包或记录、变更日志证据与分发引用。'
      }
    },
    {
      id: 'deploy',
      category: 'deliver',
      meaning: {
        en: 'Place an approved release into a declared target context.',
        zh: '把已批准发布放入已声明的目标上下文。'
      },
      input: {
        en: 'An approved release, target, strategy, authorization, and rollback constraints.',
        zh: '已批准发布、目标、策略、授权与回滚约束。'
      },
      output: {
        en: 'Placement status, target references, health evidence, and rollback outcome if used.',
        zh: '部署状态、目标引用、健康证据及必要时的回滚结果。'
      }
    },
    {
      id: 'monitor',
      category: 'deliver',
      meaning: {
        en: 'Observe delivered output and preserve the historical idea of post-delivery evidence.',
        zh: '观察已交付输出，并保留交付后证据这一历史概念。'
      },
      input: {
        en: 'A delivered target, named signals, observation window, and anomaly thresholds.',
        zh: '已交付目标、具名信号、观察窗口与异常阈值。'
      },
      output: {
        en: 'Time-bounded observations, anomalies, stability evidence, and a recommendation.',
        zh: '有时间边界的观察、异常、稳定性证据与建议。'
      }
    },
    {
      id: 'gate',
      category: 'control',
      meaning: {
        en: 'Preserve a historical control or checkpoint source in decomposition vocabulary.',
        zh: '在分解词汇中保留历史控制或检查点来源。'
      },
      input: {
        en: 'Stated criteria, referenced evidence, blocker state, and required checks.',
        zh: '已声明标准、引用证据、阻断状态与必需检查。'
      },
      output: {
        en: 'A conceptual pass or fail checkpoint with criteria results and blockers.',
        zh: '包含条件结果与阻断项的概念通过或失败检查点。'
      }
    }
  ];

  if (typeof window.addTranslations !== 'function') {
    console.error('[stage-explorer] shared i18n did not expose addTranslations');
    return;
  }

  assertTranslationParity();
  assertCanonicalDataset();
  window.addTranslations('en', EN);
  window.addTranslations('zh', ZH);

  var seedMembership = buildSeedMembership(window.DEVOLAFLOW_SEED_CATALOG);
  var activeCategory = 'all';
  var selectedId = 'research';

  ready(function () {
    if (!requiredMarkupExists()) {
      console.error('[stage-explorer] primitive explorer markup is incomplete');
      return;
    }
    document.addEventListener('devolaflow:languagechange', handleLanguageChange);
    if (!seedMembership) {
      showCatalogError();
      return;
    }

    render();
    translateAriaLabels();
  });

  function handleLanguageChange() {
    if (!seedMembership) {
      showCatalogError();
      translateAriaLabels();
      return;
    }
    render();
    translateAriaLabels();
  }

  function assertTranslationParity() {
    var enKeys = Object.keys(EN).sort();
    var zhKeys = Object.keys(ZH).sort();
    if (enKeys.length !== zhKeys.length || enKeys.some(function (key, index) {
      return key !== zhKeys[index];
    })) {
      console.error('[stage-explorer] EN/ZH page-local translation keys differ');
    }
  }

  function assertCanonicalDataset() {
    var ids = PRIMITIVES.map(function (primitive) { return primitive.id; });
    var matchesCanonical = ids.length === 14 &&
      ids.every(function (id, index) { return id === CANONICAL_LABELS[index]; });
    if (!matchesCanonical) {
      throw new Error('[stage-explorer] primitive data must match the canonical 14 historical labels');
    }
  }

  function buildSeedMembership(catalog) {
    if (!catalog ||
        catalog.schema_version !== '1.0' ||
        catalog.record_count !== 27 ||
        !Array.isArray(catalog.seeds) ||
        catalog.seeds.length !== 27) {
      return null;
    }

    var memberships = Object.create(null);
    CANONICAL_LABELS.forEach(function (label) {
      memberships[label] = [];
    });
    var names = Object.create(null);

    for (var seedIndex = 0; seedIndex < catalog.seeds.length; seedIndex += 1) {
      var seed = catalog.seeds[seedIndex];
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
          names[seed.name] ||
          !Array.isArray(seed.partitions)) {
        return null;
      }
      names[seed.name] = true;

      for (var partitionIndex = 0; partitionIndex < seed.partitions.length; partitionIndex += 1) {
        var partition = seed.partitions[partitionIndex];
        if (!partition ||
            typeof partition.key !== 'string' ||
            typeof partition.title !== 'string' ||
            !Array.isArray(partition.source_stages) ||
            !Array.isArray(partition.assertions) ||
            !partition.assertions.every(function (assertion) {
              return assertion &&
                typeof assertion.key === 'string' &&
                typeof assertion.statement === 'string' &&
                typeof assertion.suggested_priority === 'string' &&
                assertion.verify &&
                typeof assertion.verify.mode === 'string';
            })) {
          return null;
        }
        for (var sourceIndex = 0; sourceIndex < partition.source_stages.length; sourceIndex += 1) {
          var source = partition.source_stages[sourceIndex];
          if (!source ||
              typeof source.id !== 'string' ||
              typeof source.primitive !== 'string' ||
              !memberships[source.primitive]) {
            return null;
          }
          if (memberships[source.primitive].indexOf(seed.name) === -1) {
            memberships[source.primitive].push(seed.name);
          }
        }
      }
    }
    return memberships;
  }

  function primitiveSeeds(primitiveId) {
    return seedMembership[primitiveId];
  }

  function showCatalogError() {
    console.warn('[stage-explorer] generated seed catalog is unavailable or malformed');
    var message = text('exp.catalog.error');
    var grid = document.getElementById('primitive-grid');
    var error = document.createElement('p');
    error.className = 'seed-list-empty';
    error.setAttribute('role', 'alert');
    error.textContent = message;
    document.getElementById('primitive-filters').replaceChildren();
    grid.replaceChildren(error);
    document.getElementById('primitive-detail').hidden = true;
    document.getElementById('primitive-count').textContent = message;
  }

  function requiredMarkupExists() {
    return Boolean(
      document.getElementById('primitive-filters') &&
      document.getElementById('primitive-grid') &&
      document.getElementById('primitive-detail') &&
      document.getElementById('primitive-count')
    );
  }

  function ready(callback) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', callback);
    } else {
      callback();
    }
  }

  function currentLanguage() {
    return document.documentElement.getAttribute('data-lang') === 'zh' ? 'zh' : 'en';
  }

  function text(key) {
    return typeof window.t === 'function' ? window.t(key) : (EN[key] || key);
  }

  function format(key, values) {
    var result = text(key);
    Object.keys(values).forEach(function (name) {
      result = result.replace('{' + name + '}', String(values[name]));
    });
    return result;
  }

  function categoryName(category) {
    return text('exp.category.' + category);
  }

  function visiblePrimitives() {
    if (activeCategory === 'all') {
      return PRIMITIVES.slice();
    }
    return PRIMITIVES.filter(function (primitive) {
      return primitive.category === activeCategory;
    });
  }

  function render() {
    renderFilters();
    renderGrid();
    renderDetail();
    renderCount();
  }

  function renderFilters() {
    var filters = document.getElementById('primitive-filters');
    filters.replaceChildren();

    ['all'].concat(CATEGORIES).forEach(function (category) {
      var count = category === 'all'
        ? PRIMITIVES.length
        : PRIMITIVES.filter(function (primitive) {
          return primitive.category === category;
        }).length;
      var button = document.createElement('button');
      var countLabel = document.createElement('span');

      button.type = 'button';
      button.className = 'filter-button';
      button.setAttribute('aria-pressed', category === activeCategory ? 'true' : 'false');
      button.appendChild(document.createTextNode(
        category === 'all' ? text('exp.filter.all') : categoryName(category)
      ));

      countLabel.className = 'filter-count';
      countLabel.textContent = String(count);
      button.appendChild(countLabel);
      button.addEventListener('click', function () {
        activeCategory = category;
        var visible = visiblePrimitives();
        if (!visible.some(function (primitive) { return primitive.id === selectedId; })) {
          selectedId = visible[0].id;
        }
        render();
      });
      filters.appendChild(button);
    });
  }

  function renderGrid() {
    var grid = document.getElementById('primitive-grid');
    var language = currentLanguage();
    grid.replaceChildren();

    visiblePrimitives().forEach(function (primitive) {
      var button = document.createElement('button');
      var category = document.createElement('span');
      var name = document.createElement('span');
      var summary = document.createElement('span');
      var meta = document.createElement('span');

      button.type = 'button';
      button.className = 'primitive-card';
      button.setAttribute('aria-pressed', primitive.id === selectedId ? 'true' : 'false');
      button.setAttribute('aria-label', format('exp.card.open', {label: primitive.id}));

      category.className = 'primitive-card-category';
      category.textContent = categoryName(primitive.category);
      name.className = 'primitive-card-name';
      name.textContent = primitive.id;
      summary.className = 'primitive-card-summary';
      summary.textContent = primitive.meaning[language];
      meta.className = 'primitive-card-meta';
      meta.textContent = format('exp.card.seedCount', {
        count: primitiveSeeds(primitive.id).length
      });

      button.append(category, name, summary, meta);
      button.addEventListener('click', function () {
        selectedId = primitive.id;
        renderGrid();
        renderDetail();
      });
      grid.appendChild(button);
    });
  }

  function renderDetail() {
    var language = currentLanguage();
    var primitive = PRIMITIVES.find(function (candidate) {
      return candidate.id === selectedId;
    });
    if (!primitive) {
      primitive = PRIMITIVES[0];
      selectedId = primitive.id;
    }

    document.getElementById('primitive-detail-category').textContent =
      categoryName(primitive.category);
    document.getElementById('primitive-detail-name').textContent = primitive.id;
    document.getElementById('primitive-detail-meaning').textContent =
      primitive.meaning[language];
    document.getElementById('primitive-detail-input').textContent =
      primitive.input[language];
    document.getElementById('primitive-detail-output').textContent =
      primitive.output[language];

    var seedCount = document.getElementById('primitive-seed-count');
    var seedNote = document.getElementById('primitive-seed-note');
    var seedList = document.getElementById('primitive-seed-list');
    var seeds = primitiveSeeds(primitive.id);
    seedList.replaceChildren();

    seedCount.textContent = seeds.length
      ? format('exp.seed.count', {count: seeds.length})
      : text('exp.seed.none');
    seedNote.textContent = seeds.length
      ? text('exp.seed.note')
      : text('exp.seed.noneNote');

    if (seeds.length) {
      seeds.forEach(function (seed) {
        var item = document.createElement('li');
        item.textContent = seed;
        seedList.appendChild(item);
      });
    } else {
      var emptyItem = document.createElement('li');
      emptyItem.className = 'seed-list-empty';
      emptyItem.textContent = text('exp.seed.noneItem');
      seedList.appendChild(emptyItem);
    }
  }

  function renderCount() {
    document.getElementById('primitive-count').textContent = format('exp.count.visible', {
      visible: visiblePrimitives().length,
      total: PRIMITIVES.length
    });
  }

  function translateAriaLabels() {
    document.querySelectorAll('[data-i18n-aria]').forEach(function (element) {
      element.setAttribute('aria-label', text(element.getAttribute('data-i18n-aria')));
    });
  }
})();
