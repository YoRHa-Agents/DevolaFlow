/**
 * DevolaFlow — shared/i18n.js
 * Lightweight i18n system. Swaps text via data-i18n attributes;
 * persists language choice in localStorage.
 */
(function () {
  'use strict';

  var LANG_KEY = 'devolaflow-lang';
  var DEFAULT_LANG = 'en';

  /* ==================================================================
     Translation dictionaries — EN / ZH
     ================================================================== */

  var TRANSLATIONS = {
    en: {
      /* -- Navigation -- */
      'nav.home':           'Home',
      'nav.architecture':   'Architecture',
      'nav.visualizer':     'Visualizer',
      'nav.explorer':       'Explorer',
      'nav.benchmarks':     'Benchmarks',
      'nav.docs':           'Docs',
      'nav.userGuide':      'User Guide',
      'nav.zhGuide':        'Chinese Guide',

      /* -- Theme toggle -- */
      'theme.toggle':       'Toggle dark mode',

      /* -- Footer -- */
      'footer.text':        'DevolaFlow',
      'footer.github':      'GitHub',
      'footer.license':     'MIT License',

      /* -- Landing page: header -- */
      'landing.title':      'DevolaFlow',
      'landing.tagline':    'Composable workflow meta-framework for AI-assisted software development',
      'landing.subtitle':   'Define multi-stage delivery pipelines as declarative YAML. Let any AI coding tool orchestrate them through a 4-layer agent hierarchy with quality gates.',

      /* -- Landing: quick start -- */
      'landing.install':    'Install in 1 command',

      /* -- Landing: How It Works -- */
      'landing.howItWorks':        'How It Works',
      'landing.howItWorks.desc':   'Every workflow executes through a strict 4-layer hierarchy. Upper layers dispatch; only the bottom layer works.',
      'landing.layer.project':     'Project',
      'landing.layer.project.desc':'picks workflow type, dispatches stages',
      'landing.layer.stage':       'Stage',
      'landing.layer.stage.desc':  'decomposes into waves, runs quality gates',
      'landing.layer.wave':        'Wave',
      'landing.layer.wave.desc':   'dispatches tasks in parallel, collects results',
      'landing.layer.task':        'Task',
      'landing.layer.task.desc':   'writes code, runs tests, reviews — the ONLY layer that works',

      /* -- Landing: Workflow Types -- */
      'landing.workflows':         '17 Built-in Workflow Types',
      'landing.workflows.desc':    'Pick the right workflow for your task. Each is a different composition of the same 13 stage primitives.',
      'landing.workflow.col.name': 'Workflow',
      'landing.workflow.col.when': 'When to use',
      'landing.workflow.col.stages':'Stages',

      /* -- Landing: Interactive Tools -- */
      'landing.tools':             'Interactive Tools',
      'landing.tools.desc':        'Explore the framework, workflows, and stages visually — no installation required.',

      /* -- Landing: Version highlights -- */
      'landing.whatsNew':          'What\'s New',
      'landing.highlights':        'Highlights',

      /* -- Landing: AI Tool integration -- */
      'landing.aiTools':           'Use with Your AI Tool',
      'landing.aiTools.desc':      'DevolaFlow adapts to four AI coding tools from a single source. Run make build-skill and copy the output.',

      /* -- Card labels -- */
      'label.architecture':  'ARCHITECTURE',
      'label.interactive':   'INTERACTIVE',
      'label.docsEn':        'DOCS EN',
      'label.docsZh':        'DOCS ZH',
      'label.docs':          'DOCS',
      'label.benchmarks':    'BENCHMARKS',
      'label.rules':         'RULES',
      'label.context':       'CONTEXT',
      'label.visualization': 'VISUALIZATION',
      'label.knowledge':     'KNOWLEDGE',
      'label.feedback':      'FEEDBACK',
      'label.gates':         'GATES',
      'label.metrics':       'METRICS',
      'label.cursor':        'CURSOR',
      'label.codex':         'CODEX',
      'label.claude':        'CLAUDE',
      'label.copilot':       'COPILOT',

      /* -- Tool cards -- */
      'card.designArch':        'Design Architecture',
      'card.designArch.desc':   'The complete framework map: every skill file, its design document source, tier, token budget, and the workflows it enables.',
      'card.visualizer':        'Workflow Visualizer',
      'card.visualizer.desc':   'Select any of the 17 workflow types and see its stage pipeline, teams, gate types, and loop structure rendered as a diagram.',
      'card.explorer':          'Stage Explorer',
      'card.explorer.desc':     'Deep-dive into any of the 13 stage primitives. See input/output types, delegation chains, and context budget allocation.',
      'card.userGuide':         'User Guide',
      'card.userGuide.desc':    'Step-by-step: install, configure, run your first workflow, integrate with AI tools.',
      'card.zhGuide':           'Chinese Guide',
      'card.zhGuide.desc':      'Quick start: install, configure, run your first workflow, integrate with AI tools.',
      'card.archOverview':      'Architecture Overview',
      'card.archOverview.desc': 'System architecture: 4-layer hierarchy, 13 stage primitives, gate mechanism, context isolation.',

      /* -- Buttons -- */
      'btn.openArchMap':    'Open Architecture Map',
      'btn.openVisualizer': 'Open Visualizer',
      'btn.openExplorer':   'Open Explorer',
      'btn.github':         'GitHub',
      'btn.viewSkill':      'View SKILL',
      'btn.viewResults':    'View Results',
      'btn.viewBenchmarks': 'View Benchmarks',
      'btn.viewRules':      'View Rules',
      'btn.viewProfiles':   'View Profiles',
      'btn.readOverview':   'Read Overview',
      'btn.gateReference':  'Gate Reference',

      /* -- Common labels -- */
      'common.version':     'Version',
      'common.scenarios':   'Scenarios',
      'common.category':    'Category',
      'common.status':      'Status',
      'common.total':       'Total',
      'common.average':     'Average',
      'common.improvement': 'Improvement',
      'common.baseline':    'Baseline',
      'common.current':     'Current',
      'common.loading':     'Loading…',
      'common.error':       'Error',
      'common.success':     'Success',
      'common.warning':     'Warning',
      'common.back':        'Back',
      'common.learnMore':   'Learn more',
      'common.viewAll':     'View all',
      'common.close':       'Close',

      /* -- Page titles -- */
      'page.landing':       'DevolaFlow — Composable Workflow Meta-Framework',
      'page.architecture':  'Design Architecture — DevolaFlow',
      'page.visualizer':    'Workflow Visualizer — DevolaFlow',
      'page.explorer':      'Stage Explorer — DevolaFlow',
      'page.benchmarks':    'EvoBench Results — DevolaFlow',

      /* -- Benchmark page -- */
      'bench.overview':     'Overview',
      'bench.overview.desc':'Aggregate stats from the latest optimization run.',
      'bench.totalScenarios':'Total scenarios',
      'bench.avgComposite': 'Avg composite',
      'bench.budgetUtil':   'Budget utilization',
      'bench.rounds':       'Optimization rounds',
      'bench.scenarios':    'Scenario Breakdown',
      'bench.history':      'Optimization History',
      'bench.history.desc': 'Score progression across optimization rounds.',

      /* -- Architecture page -- */
      'arch.subtitle':      'The complete framework map',
      'arch.files':         'Skill Files',
      'arch.templates':     'Workflow Templates',
      'arch.adapters':      'Adapter Outputs',
      'arch.designDocs':    'Design Documents',
      'arch.tokenBudget':   'Token Budget',

      /* -- Visualizer page -- */
      'viz.subtitle':       'Select a workflow to visualize its stage pipeline',
      'viz.selectWorkflow':  'Select workflow',
      'viz.stages':         'Stages',
      'viz.teams':          'Teams',
      'viz.gates':          'Gates',
      'viz.loops':          'Loops',

      /* -- Explorer page -- */
      'exp.subtitle':       'Deep-dive into stage primitives',
      'exp.selectStage':    'Select stage',
      'exp.inputs':         'Inputs',
      'exp.outputs':        'Outputs',
      'exp.delegation':     'Delegation Chain',
      'exp.contextBudget':  'Context Budget'
    },

    zh: {
      /* -- 导航 -- */
      'nav.home':           '首页',
      'nav.architecture':   '架构',
      'nav.visualizer':     '可视化',
      'nav.explorer':       '探索器',
      'nav.benchmarks':     '基准测试',
      'nav.docs':           '文档',
      'nav.userGuide':      '使用指南',
      'nav.zhGuide':        '中文指南',

      /* -- 主题 -- */
      'theme.toggle':       '切换深色模式',

      /* -- 页脚 -- */
      'footer.text':        'DevolaFlow',
      'footer.github':      'GitHub',
      'footer.license':     'MIT 协议',

      /* -- 首页：头部 -- */
      'landing.title':      'DevolaFlow',
      'landing.tagline':    '面向 AI 辅助软件开发的可组合工作流元框架',
      'landing.subtitle':   '将多阶段交付流水线定义为声明式 YAML。让任何 AI 编程工具通过四层代理层次结构和质量门控来编排工作流。',

      /* -- 首页：快速开始 -- */
      'landing.install':    '一条命令安装',

      /* -- 首页：工作原理 -- */
      'landing.howItWorks':        '工作原理',
      'landing.howItWorks.desc':   '每个工作流通过严格的四层层次结构执行。上层调度，只有底层执行。',
      'landing.layer.project':     '项目层',
      'landing.layer.project.desc':'选择工作流类型，分派阶段',
      'landing.layer.stage':       '阶段层',
      'landing.layer.stage.desc':  '分解为波次，运行质量门控',
      'landing.layer.wave':        '波次层',
      'landing.layer.wave.desc':   '并行分派任务，收集结果',
      'landing.layer.task':        '任务层',
      'landing.layer.task.desc':   '写代码、跑测试、做审查——唯一执行工作的层',

      /* -- 首页：工作流类型 -- */
      'landing.workflows':         '17 种内置工作流类型',
      'landing.workflows.desc':    '为你的任务选择合适的工作流。每种工作流是 13 个阶段原语的不同组合。',
      'landing.workflow.col.name': '工作流',
      'landing.workflow.col.when': '使用场景',
      'landing.workflow.col.stages':'阶段',

      /* -- 首页：交互工具 -- */
      'landing.tools':             '交互工具',
      'landing.tools.desc':        '可视化探索框架、工作流和阶段——无需安装。',

      /* -- 首页：版本亮点 -- */
      'landing.whatsNew':          '最新更新',
      'landing.highlights':        '亮点',

      /* -- 首页：AI 工具集成 -- */
      'landing.aiTools':           '集成 AI 工具',
      'landing.aiTools.desc':      'DevolaFlow 从单一源文件适配四种 AI 编程工具。运行 make build-skill 并复制输出即可。',

      /* -- 卡片标签 -- */
      'label.architecture':  '架构',
      'label.interactive':   '交互',
      'label.docsEn':        '英文文档',
      'label.docsZh':        '中文文档',
      'label.docs':          '文档',
      'label.benchmarks':    '基准测试',
      'label.rules':         '规则',
      'label.context':       '上下文',
      'label.visualization': '可视化',
      'label.knowledge':     '知识',
      'label.feedback':      '反馈',
      'label.gates':         '门控',
      'label.metrics':       '指标',
      'label.cursor':        'CURSOR',
      'label.codex':         'CODEX',
      'label.claude':        'CLAUDE',
      'label.copilot':       'COPILOT',

      /* -- 工具卡片 -- */
      'card.designArch':        '设计架构',
      'card.designArch.desc':   '完整的框架地图：每个技能文件、其设计文档来源、层级、Token 预算及其启用的工作流。',
      'card.visualizer':        '工作流可视化',
      'card.visualizer.desc':   '选择 17 种工作流类型中的任何一种，查看其阶段流水线、团队、门控类型和循环结构图。',
      'card.explorer':          '阶段探索器',
      'card.explorer.desc':     '深入了解 13 个阶段原语中的任何一个。查看输入/输出类型、委派链和上下文预算分配。',
      'card.userGuide':         '使用指南',
      'card.userGuide.desc':    '分步指南：安装、配置、运行第一个工作流、集成 AI 工具。',
      'card.zhGuide':           '中文指南',
      'card.zhGuide.desc':      '快速入门：安装、配置、运行第一个工作流、接入 AI 工具。',
      'card.archOverview':      '架构概览',
      'card.archOverview.desc': '系统架构：四层层次结构、13 个阶段原语、门控机制、上下文隔离。',

      /* -- 按钮 -- */
      'btn.openArchMap':    '打开架构地图',
      'btn.openVisualizer': '打开可视化器',
      'btn.openExplorer':   '打开探索器',
      'btn.github':         'GitHub',
      'btn.viewSkill':      '查看技能',
      'btn.viewResults':    '查看结果',
      'btn.viewBenchmarks': '查看基准测试',
      'btn.viewRules':      '查看规则',
      'btn.viewProfiles':   '查看配置',
      'btn.readOverview':   '阅读概览',
      'btn.gateReference':  '门控参考',

      /* -- 通用标签 -- */
      'common.version':     '版本',
      'common.scenarios':   '场景',
      'common.category':    '分类',
      'common.status':      '状态',
      'common.total':       '合计',
      'common.average':     '平均',
      'common.improvement': '改进',
      'common.baseline':    '基线',
      'common.current':     '当前',
      'common.loading':     '加载中…',
      'common.error':       '错误',
      'common.success':     '成功',
      'common.warning':     '警告',
      'common.back':        '返回',
      'common.learnMore':   '了解更多',
      'common.viewAll':     '查看全部',
      'common.close':       '关闭',

      /* -- 页面标题 -- */
      'page.landing':       'DevolaFlow — 可组合工作流元框架',
      'page.architecture':  '设计架构 — DevolaFlow',
      'page.visualizer':    '工作流可视化 — DevolaFlow',
      'page.explorer':      '阶段探索器 — DevolaFlow',
      'page.benchmarks':    '基准测试结果 — DevolaFlow',

      /* -- 基准测试页 -- */
      'bench.overview':     '概览',
      'bench.overview.desc':'最新优化运行的汇总统计。',
      'bench.totalScenarios':'场景总数',
      'bench.avgComposite': '平均综合分',
      'bench.budgetUtil':   '预算利用率',
      'bench.rounds':       '优化轮次',
      'bench.scenarios':    '场景明细',
      'bench.history':      '优化历史',
      'bench.history.desc': '各优化轮次的分数变化。',

      /* -- 架构页 -- */
      'arch.subtitle':      '完整的框架地图',
      'arch.files':         '技能文件',
      'arch.templates':     '工作流模板',
      'arch.adapters':      '适配器输出',
      'arch.designDocs':    '设计文档',
      'arch.tokenBudget':   'Token 预算',

      /* -- 可视化器页 -- */
      'viz.subtitle':       '选择一个工作流以可视化其阶段流水线',
      'viz.selectWorkflow':  '选择工作流',
      'viz.stages':         '阶段',
      'viz.teams':          '团队',
      'viz.gates':          '门控',
      'viz.loops':          '循环',

      /* -- 探索器页 -- */
      'exp.subtitle':       '深入了解阶段原语',
      'exp.selectStage':    '选择阶段',
      'exp.inputs':         '输入',
      'exp.outputs':        '输出',
      'exp.delegation':     '委派链',
      'exp.contextBudget':  '上下文预算'
    }
  };

  /* ==================================================================
     Public API
     ================================================================== */

  /**
   * Look up a translation key for the current language.
   * Falls back to English, then returns the key itself.
   */
  function t(key) {
    var lang = currentLang();
    if (TRANSLATIONS[lang] && TRANSLATIONS[lang][key] !== undefined) {
      return TRANSLATIONS[lang][key];
    }
    if (TRANSLATIONS.en[key] !== undefined) {
      return TRANSLATIONS.en[key];
    }
    return key;
  }

  function currentLang() {
    return document.documentElement.getAttribute('data-lang') || DEFAULT_LANG;
  }

  /**
   * Set the active language. Swaps all data-i18n, data-i18n-placeholder,
   * and data-i18n-title elements. Updates <html lang> and data-lang.
   */
  function setLanguage(lang) {
    if (!TRANSLATIONS[lang]) { lang = DEFAULT_LANG; }
    document.documentElement.setAttribute('data-lang', lang);
    document.documentElement.lang = lang;
    localStorage.setItem(LANG_KEY, lang);

    document.querySelectorAll('[data-i18n]').forEach(function (el) {
      var key = el.getAttribute('data-i18n');
      var val = t(key);
      if (val) { el.textContent = val; }
    });

    document.querySelectorAll('[data-i18n-placeholder]').forEach(function (el) {
      var key = el.getAttribute('data-i18n-placeholder');
      var val = t(key);
      if (val) { el.placeholder = val; }
    });

    document.querySelectorAll('[data-i18n-title]').forEach(function (el) {
      var key = el.getAttribute('data-i18n-title');
      var val = t(key);
      if (val) { el.title = val; }
    });

    if (typeof window.updateNavLabels === 'function') {
      window.updateNavLabels();
    }
  }

  /**
   * Register additional translations (for page-specific keys).
   * Merges into the existing dictionaries.
   */
  function addTranslations(lang, entries) {
    if (!TRANSLATIONS[lang]) { TRANSLATIONS[lang] = {}; }
    for (var key in entries) {
      if (entries.hasOwnProperty(key)) {
        TRANSLATIONS[lang][key] = entries[key];
      }
    }
  }

  /* ---- Initialise ---- */

  function init() {
    var stored = localStorage.getItem(LANG_KEY);
    var lang = stored || DEFAULT_LANG;
    setLanguage(lang);
  }

  /* Expose globals */
  window.t = t;
  window.setLanguage = setLanguage;
  window.addTranslations = addTranslations;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
