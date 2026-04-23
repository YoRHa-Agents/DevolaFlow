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
      'landing.tagline':    'A guardian\'s song for your code — orchestrating workflows so nothing is left behind.',
      'landing.subtitle':   'Define multi-stage delivery pipelines as declarative YAML. A 4-layer agent hierarchy watches over every task with quality gates, so your code is never unprotected.',

      /* -- Landing: quick start -- */
      'landing.install':    'Install in 1 command',

      /* -- Landing: How It Works -- */
      'landing.howItWorks':        'How It Works',
      'landing.howItWorks.desc':   'Like Devola watching over the old world, the hierarchy ensures every task is protected and guided. Upper layers dispatch; only the bottom layer works.',
      'landing.layer.project':     'Project',
      'landing.layer.project.desc':'the overseer — picks workflow type, dispatches stages',
      'landing.layer.stage':       'Stage',
      'landing.layer.stage.desc':  'the conductor — decomposes into waves, runs quality gates',
      'landing.layer.wave':        'Wave',
      'landing.layer.wave.desc':   'the coordinator — dispatches tasks in parallel, collects results',
      'landing.layer.task':        'Task',
      'landing.layer.task.desc':   'the hands that build — writes code, runs tests, reviews. The ONLY layer that works.',

      /* -- Landing: Workflow Types -- */
      'landing.workflows':         '22 Built-in Workflow Types',
      'landing.workflows.desc':    'Every task deserves the right approach. Each workflow is a different arrangement of the same 13 stage primitives.',
      'landing.workflow.col.name': 'Workflow',
      'landing.workflow.col.when': 'When to use',
      'landing.workflow.col.stages':'Stages',

      /* -- Landing: Interactive Tools -- */
      'landing.tools':             'Interactive Tools',
      'landing.tools.desc':        'Explore the framework visually — see the architecture, trace workflows, and inspect stage primitives. No installation required.',

      /* -- Landing: Version highlights (v6.2.1) -- */
      'landing.whatsNew':          'What\'s New',
      'landing.whatsNew.desc':     'v6.2.1 closes the v6.0 + v6.1 rollup with a CI-flake fix (deterministic benchmark estimator via tests/conftest.py). 1009 tests passing, NineS overall 0.8805 stable, 11 platform adapters [OK]. The v6.0→v6.2 journey shipped +18.9% NineS gain via tool-config (zero source changes), schema parity + 29/29 EvoBench baselines, dead-wire closure of v5.3.0 reinforcement infrastructure, plan-mode runtime hook, and four new theme showcases (Design System, Framework Chain, Context Flow, R&D Timeline).',
      'landing.whatsNew.identity':      'NieR: Automata Visual Redesign',
      'landing.whatsNew.identity.desc': 'Full visual identity overhaul: warm parchment palette, Cinzel serif headings, gold accent borders, diamond section ornaments, corner marks on hover, and scan-flicker boot animation — all inspired by Devola\'s world.',
      'landing.whatsNew.ci':            'Improved GitHub Actions CI',
      'landing.whatsNew.ci.desc':       'Concurrency controls prevent duplicate runs, required status checks enforce quality gates on every PR, and the release pipeline is streamlined for faster delivery.',
      'landing.whatsNew.docs':          'Documentation Sync Rules',
      'landing.whatsNew.docs.desc':     'New rules ensure human-facing docs stay synchronized with agent-facing skill files. Version bumps propagate automatically across all eight sync targets.',
      'landing.whatsNew.adapters':      '11 Platform Adapters',
      'landing.whatsNew.adapters.desc': 'Cursor, Codex, Claude Code, Copilot (core) + KimiCode, Windsurf, Continue.dev, OpenClaw, Zed, Cline, Roo Code via a single YAML-driven adapter contract. New platforms need ~25 LOC of YAML.',
      'landing.whatsNew.deadwire':      'Round-Aware Convergence',
      'landing.whatsNew.deadwire.desc': 'v5.3.0 infrastructure finally wired in v6.0.3: select_context(round_num=N) auto-escalates critical sections, bumps budget +20% on round 3, and merges prior-round gate findings into applicable_rules.reinforcement as MUST-fix mandates.',
      'landing.whatsNew.schemas':       'Schema Parity + 29/29 Baselines',
      'landing.whatsNew.schemas.desc':  'Parity enforcer (6 tests) catches any field drift between task-dispatch, lean-dispatch, and gate-report schemas. EvoBench regression baselines now cover all 29 scenarios (up from 3) — any composite regression >5% fails CI.',
      'landing.whatsNew.metrics':       '1009 Tests, 94% Coverage',
      'landing.whatsNew.metrics.desc':  '+191 tests across the v6.0+v6.1 rollup (818 → 1009), coverage 91% → 94%. NineS overall 0.7405 → 0.8805 (+18.9%). cli.py and composer.py pushed to 98% and 100%. 0 DeprecationWarnings.',
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
      'label.identity':      'IDENTITY',
      'label.ci':            'CI',
      'label.adapters':      'ADAPTERS',
      'label.deadwire':      'DEAD-WIRE',
      'label.schemas':       'SCHEMAS',
      'label.cursor':        'CURSOR',
      'label.codex':         'CODEX',
      'label.claude':        'CLAUDE',
      'label.copilot':       'COPILOT',

      /* -- Tool cards -- */
      'card.designArch':        'Design Architecture',
      'card.designArch.desc':   'The complete framework map: every skill file, its design document source, tier, token budget, and the workflows it enables.',
      'card.visualizer':        'Workflow Visualizer',
      'card.visualizer.desc':   'Select any of the 22 workflow types and see its stage pipeline, teams, gate types, and loop structure rendered as a diagram.',
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
      'btn.viewCI':         'View CI',
      'btn.viewConfigs':    'View Configs',
      'btn.readMore':       'Read More',

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
      'page.landing':       'DevolaFlow — A Guardian\'s Song for Your Code',
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
      'exp.contextBudget':  'Context Budget',

      /* -- Navigation: v6.3 new pages -- */
      'nav.designSystem':    'Design System',
      'nav.frameworkChain':  'Framework Chain',
      'nav.contextFlow':     'Context Flow',
      'nav.versionTimeline': 'Timeline',

      /* -- Page titles: v6.3 new pages -- */
      'page.designSystem':    'Design System — DevolaFlow',
      'page.frameworkChain':  'Framework Chain — DevolaFlow',
      'page.contextFlow':     'Context Flow — DevolaFlow',
      'page.versionTimeline': 'R&D Timeline — DevolaFlow',

      /* -- Landing: Theme Showcases (v6.3) -- */
      'landing.showcase':           'Theme Showcases',
      'landing.showcase.desc':      'Four new pages making the design language, framework chain, context flow, and R&D journey first-class citizens.',
      'label.designSystem':         'DESIGN SYSTEM',
      'label.frameworkChain':       'FRAMEWORK CHAIN',
      'label.contextFlow':          'CONTEXT FLOW',
      'label.versionTimeline':      'TIMELINE',
      'card.designSystem':          'Design System',
      'card.designSystem.desc':     'Palette, typography, motion, components, states, accessibility — the Devola design language as an artifact.',
      'card.frameworkChain':        'Framework Chain',
      'card.frameworkChain.desc':   'Animated 4-layer hierarchy + 5 AgentTeams + gate convergence + reinforcement loop.',
      'card.contextFlow':           'Context Flow',
      'card.contextFlow.desc':      'Dispatch / Report / Escalation / Round-Reinforcement message routing animations.',
      'card.versionTimeline':       'R&D Timeline',
      'card.versionTimeline.desc':  'Cross-version journey from v3.x → v6.2.1 across 5 R&D eras.',

      /* -- Design System page -- */
      'ds.subtitle':                  'The Devola design language, on display.',
      'ds.section.palette':           'Palette',
      'ds.section.palette.desc':      '14 inherited tokens plus 5 new tokens for the v6.3 redesign — light + dark side-by-side.',
      'ds.section.typography':        'Typography',
      'ds.section.typography.desc':   'Cinzel for headings, Inter for body, JetBrains Mono for code.',
      'ds.section.motion':            'Motion',
      'ds.section.motion.desc':       'Three new patterns (pulse-dispatch / flow-down / verify-gate-glow) plus the existing scan-flicker reference — all reduce-motion safe.',
      'ds.section.components':        'Components',
      'ds.section.components.desc':   'Eight reusable building blocks the new pages depend on.',
      'ds.section.states':            'States',
      'ds.section.states.desc':       'How active / pass / fail / escalated / reinforced are styled.',
      'ds.section.accessibility':     'Accessibility',
      'ds.section.accessibility.desc':'Reduced-motion fallbacks, WCAG contrast targets, keyboard focus, bilingual switching.',
      'ds.swatch.copy':               'Copy CSS var',
      'ds.swatch.copied':             'Copied',
      'ds.motion.replay':             'Replay',
      'ds.motion.label.pulse':        'pulse-dispatch',
      'ds.motion.label.flow':         'flow-down',
      'ds.motion.label.gateGlow':     'verify-gate-glow',
      'ds.motion.label.scanFlicker':  'scan-flicker (existing)',
      'ds.a11y.reducedMotion':        'All animations honour `prefers-reduced-motion: reduce`.',
      'ds.a11y.contrast':             'Body text meets WCAG AA on both themes; new tokens were chosen for AA.',
      'ds.a11y.keyboard':             'Every interactive control is keyboard-focusable with visible focus ring.',
      'ds.a11y.bilingual':            'EN/ZH switch is one click; preference persists in localStorage.',

      /* -- Framework Chain page -- */
      'fc.subtitle':                       'Project → Stage → Wave → Task — see the chain move.',
      'fc.section.hierarchy':              '4-Layer Hierarchy',
      'fc.section.hierarchy.desc':         'Each layer dispatches downward and reports upward; only L3 does work.',
      'fc.section.teams':                  'AgentTeams',
      'fc.section.teams.desc':             'Five teams: Research / Design / Implement / Test / Review.',
      'fc.section.gate':                   'Gate Mechanism',
      'fc.section.gate.desc':              'Composite score across 4 (or 7 with verification) dimensions; four profiles, three pass conditions.',
      'fc.section.loops':                  'Wave Coordination',
      'fc.section.loops.desc':             'Parallel / Sequential / Generator-Verifier / Hybrid — auto-selected by DAG analysis.',
      'fc.section.rationalization':        'Rationalization Prevention',
      'fc.section.rationalization.desc':   'Eight canned excuses pre-countered by the SKILL — no shortcuts.',
      'fc.layer.mustNot':                  'MUST NOT',
      'fc.gate.standardLabel':             'Standard (4-dim)',
      'fc.gate.extendedLabel':             'Extended (7-dim)',
      'fc.gate.simulateFail':              'Simulate fail on benchmark',
      'fc.replay':                         'Replay cascade',
      'fc.aside.close':                    'Close',
      'fc.team.research':                  'Research',
      'fc.team.design':                    'Design',
      'fc.team.implement':                 'Implement',
      'fc.team.test':                      'Test',
      'fc.team.review':                    'Review',
      'fc.loop.parallel':                  'Parallel',
      'fc.loop.sequential':                'Sequential',
      'fc.loop.genVerify':                 'Generator-Verifier',
      'fc.loop.hybrid':                    'Hybrid',

      /* -- Context Flow page -- */
      'cf.subtitle':                              'Watch the messages travel — dispatch down, report up, escalate up, reinforce on round 2+.',
      'cf.section.dispatch':                      'Dispatch (L0 → L3)',
      'cf.section.dispatch.desc':                 'TaskDispatch envelopes travel down the route track from Project to Task.',
      'cf.section.report':                        'Status Report (L3 → L0)',
      'cf.section.report.desc':                   'StatusReport envelopes travel up the route on completion or partial progress.',
      'cf.section.escalation':                    'Escalation Chain',
      'cf.section.escalation.desc':               'Always upward, never skip levels — Task → Wave → Stage → Project → Human.',
      'cf.section.reinforcement':                 'Round-Reinforcement (v5.1+, wired v6.0.3)',
      'cf.section.reinforcement.desc':            'Gate FAIL → top 5 findings (≥ major) → injected into next dispatch as MUST-fix.',
      'cf.section.isolation':                     'Context Isolation',
      'cf.section.isolation.desc':                'What MUST NOT leak between agents, what IS shared via artifact summaries.',
      'cf.envelope.fields':                       'Required fields',
      'cf.envelope.example':                      'Example payload',
      'cf.escalation.severity.autoRecover':       'AUTO_RECOVER — retry up to 3× with exponential backoff',
      'cf.escalation.severity.pause':             'PAUSE — pause task, queue question, continue parallel work',
      'cf.escalation.severity.humanIntervene':    'HUMAN_INTERVENE — stop stage, present options to human',
      'cf.escalation.severity.fullRollback':      'FULL_ROLLBACK — rollback to checkpoint, halt all',
      'cf.reinforcement.step':                    'Step ▶',
      'cf.reinforcement.reset':                   'Reset',
      'cf.reinforcement.round1':                  'Round 1 dispatch',
      'cf.reinforcement.round2':                  'Round 2 dispatch (reinforced)',
      'cf.reinforcement.findings':                'Findings filtered by severity',
      'cf.isolation.mustNotLeak':                 'MUST NOT leak',
      'cf.isolation.isShared':                    'IS shared via artifact summaries',
      'cf.play':                                  'Play',
      'cf.pause':                                 'Pause',

      /* -- Version Timeline page -- */
      'vt.subtitle':                       'From v0.1.0 to v7.1.0 — six eras of guarded change.',
      'vt.era.foundations':                'Foundations',
      'vt.era.evobench':                   'EvoBench & Hardening',
      'vt.era.selfImprove':                'Self-Improvement Loops',
      'vt.era.platforms':                  'Platforms & Closure',
      'vt.era.compression':                'Staged Context Compression',
      'vt.era.rollup':                     'Rollup & Stabilization',
      'vt.era.foundations.desc':           'v0.1.0 – v2.2.0: scaffolding, the first 11 templates, +93% information density.',
      'vt.era.evobench.desc':              'v3.0.0 – v3.9.x: EvoBench, repository rules, full workflow coverage, P1 enforced.',
      'vt.era.selfImprove.desc':           'v4.0.0 – v5.4.2: model routing, plugin registry, NineS, reinforcement infrastructure.',
      'vt.era.platforms.desc':             'v6.0.0 – v6.1.5: 11 platforms, dead-wire closure, schema parity, plan-mode runtime.',
      'vt.era.compression.desc':           'v7.0.0 → v7.1.0 — cache-layout invariant, tool-output truncation, hierarchical summariser, persistence probe, learnings v2.',
      'vt.era.rollup.desc':                'v6.2.0 – v7.1.0: SI-3 9.47/10, 1100 tests, NineS 0.8805 stable, cycle closure.',
      'vt.filter.all':                     'All eras',
      'vt.toggle.compact':                 'Compact',
      'vt.toggle.detailed':                'Detailed',
      'vt.card.expand':                    'Expand',
      'vt.card.collapse':                  'Collapse',
      'vt.metric.tests':                   'Tests',
      'vt.metric.coverage':                'Coverage',
      'vt.metric.nines':                   'NineS',
      'vt.metric.composite':               'Composite',
      'vt.cta.changelog':                  'Read CHANGELOG',
      'vt.cta.releases':                   'GitHub Releases'
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
      'landing.tagline':    '守护者为代码而歌——编排工作流，不让任何任务被遗忘。',
      'landing.subtitle':   '将多阶段交付流水线定义为声明式 YAML。四层代理层次结构守护每一个任务，以质量门控确保代码万无一失。',

      /* -- 首页：快速开始 -- */
      'landing.install':    '一条命令安装',

      /* -- 首页：工作原理 -- */
      'landing.howItWorks':        '工作原理',
      'landing.howItWorks.desc':   '如同 Devola 守望旧世界，层级结构确保每个任务都受到保护与引导。上层调度，只有底层执行。',
      'landing.layer.project':     '项目层',
      'landing.layer.project.desc':'监督者——选择工作流类型，分派阶段',
      'landing.layer.stage':       '阶段层',
      'landing.layer.stage.desc':  '指挥者——分解为波次，运行质量门控',
      'landing.layer.wave':        '波次层',
      'landing.layer.wave.desc':   '协调者——并行分派任务，收集结果',
      'landing.layer.task':        '任务层',
      'landing.layer.task.desc':   '建造之手——写代码、跑测试、做审查。唯一执行工作的层。',

      /* -- 首页：工作流类型 -- */
      'landing.workflows':         '22 种内置工作流类型',
      'landing.workflows.desc':    '每项任务都值得最合适的方案。每种工作流是 13 个阶段原语的不同编排。',
      'landing.workflow.col.name': '工作流',
      'landing.workflow.col.when': '使用场景',
      'landing.workflow.col.stages':'阶段',

      /* -- 首页：交互工具 -- */
      'landing.tools':             '交互工具',
      'landing.tools.desc':        '可视化探索框架——查看架构、追踪工作流、检视阶段原语。无需安装。',

      /* -- 首页：版本亮点（v6.2.1） -- */
      'landing.whatsNew':          '最新更新',
      'landing.whatsNew.desc':     'v6.2.1 收口 v6.0+v6.1 总集，修复 CI flake（通过 tests/conftest.py 让基准估算器具备确定性）。1009 个测试通过，NineS 综合 0.8805 稳定，11 个平台适配器 [OK]。v6.0→v6.2 旅程贡献：工具配置带来 NineS +18.9%（零源码改动）、schema 对齐 + 29/29 EvoBench 基线、v5.3.0 强化基础设施死线接通、Plan-mode 运行时钩子，以及四个新主题展示页（设计体系、框架链路、上下文流转、研发演进）。',
      'landing.whatsNew.identity':      'NieR: Automata 视觉重设计',
      'landing.whatsNew.identity.desc': '全面视觉升级：温暖的羊皮纸色调、Cinzel 衬线标题、金色强调边框、菱形分节装饰、悬停时的角标动效，以及扫描闪烁启动动画——灵感源自 Devola 的世界。',
      'landing.whatsNew.ci':            'GitHub Actions CI 优化',
      'landing.whatsNew.ci.desc':       '并发控制防止重复运行，必需的状态检查在每个 PR 上强制执行质量门控，发布流水线更加精简高效。',
      'landing.whatsNew.docs':          '文档同步规则',
      'landing.whatsNew.docs.desc':     '新规则确保面向用户的文档与面向代理的技能文件保持同步。版本升级自动传播到全部八个同步目标。',
      'landing.whatsNew.adapters':      '11 个平台适配器',
      'landing.whatsNew.adapters.desc': 'Cursor、Codex、Claude Code、Copilot（核心）+ KimiCode、Windsurf、Continue.dev、OpenClaw、Zed、Cline、Roo Code，全部基于同一份 YAML 适配契约。新增平台仅需约 25 行 YAML。',
      'landing.whatsNew.deadwire':      '轮次感知收敛',
      'landing.whatsNew.deadwire.desc': 'v5.3.0 基础设施在 v6.0.3 终于接通：select_context(round_num=N) 自动升级关键章节、第 3 轮预算 +20%，并将上一轮门控发现合并入 applicable_rules.reinforcement 作为 MUST-fix 强制项。',
      'landing.whatsNew.schemas':       'Schema 对齐 + 29/29 基线',
      'landing.whatsNew.schemas.desc':  '对齐校验器（6 个测试）防止 task-dispatch、lean-dispatch、gate-report schema 之间字段漂移。EvoBench 回归基线已覆盖全部 29 个场景（原仅 3 个）——综合分回退 >5% 即 CI 失败。',
      'landing.whatsNew.metrics':       '1009 个测试，94% 覆盖率',
      'landing.whatsNew.metrics.desc':  'v6.0+v6.1 总集 +191 个测试（818 → 1009），覆盖率 91% → 94%。NineS 综合 0.7405 → 0.8805（+18.9%）。cli.py 与 composer.py 拉到 98% 与 100%。0 条 DeprecationWarning。',
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
      'label.identity':      '视觉',
      'label.ci':            'CI',
      'label.adapters':      '适配器',
      'label.deadwire':      '死线接通',
      'label.schemas':       'SCHEMA',
      'label.cursor':        'CURSOR',
      'label.codex':         'CODEX',
      'label.claude':        'CLAUDE',
      'label.copilot':       'COPILOT',

      /* -- 工具卡片 -- */
      'card.designArch':        '设计架构',
      'card.designArch.desc':   '完整的框架地图：每个技能文件、其设计文档来源、层级、Token 预算及其启用的工作流。',
      'card.visualizer':        '工作流可视化',
      'card.visualizer.desc':   '选择 22 种工作流类型中的任何一种，查看其阶段流水线、团队、门控类型和循环结构图。',
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
      'btn.viewCI':         '查看 CI',
      'btn.viewConfigs':    '查看配置',
      'btn.readMore':       '阅读更多',

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
      'page.landing':       'DevolaFlow — 守护者为代码而歌',
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
      'exp.contextBudget':  '上下文预算',

      /* -- 导航：v6.3 新页 -- */
      'nav.designSystem':    '设计体系',
      'nav.frameworkChain':  '框架链路',
      'nav.contextFlow':     '上下文流转',
      'nav.versionTimeline': '版本演进',

      /* -- 页面标题：v6.3 新页 -- */
      'page.designSystem':    '设计体系 — DevolaFlow',
      'page.frameworkChain':  '框架链路 — DevolaFlow',
      'page.contextFlow':     '上下文流转 — DevolaFlow',
      'page.versionTimeline': '研发演进 — DevolaFlow',

      /* -- 首页：主题展示（v6.3） -- */
      'landing.showcase':           '主题展示',
      'landing.showcase.desc':      '四个新页面将设计语言、框架链路、上下文流转和研发历程作为一等公民呈现。',
      'label.designSystem':         '设计体系',
      'label.frameworkChain':       '框架链路',
      'label.contextFlow':          '上下文流转',
      'label.versionTimeline':      '版本演进',
      'card.designSystem':          '设计体系',
      'card.designSystem.desc':     '调色板、排版、动效、组件、状态、可访问性——将 Devola 设计语言作为可见的艺术品呈现。',
      'card.frameworkChain':        '框架链路',
      'card.frameworkChain.desc':   '动态展示四层层次结构 + 5 个代理团队 + 门控收敛 + 强化循环。',
      'card.contextFlow':           '上下文流转',
      'card.contextFlow.desc':      '派发 / 报告 / 升级 / 轮次强化的消息路由动画。',
      'card.versionTimeline':       '研发演进',
      'card.versionTimeline.desc':  '从 v3.x 到 v6.2.1 跨越 5 个研发时代的版本演进。',

      /* -- 设计体系页 -- */
      'ds.subtitle':                  'Devola 设计语言全面陈列。',
      'ds.section.palette':           '调色板',
      'ds.section.palette.desc':      '14 个继承令牌加 5 个 v6.3 新增令牌——浅色与深色并列展示。',
      'ds.section.typography':        '排版',
      'ds.section.typography.desc':   '标题用 Cinzel，正文用 Inter，代码用 JetBrains Mono。',
      'ds.section.motion':            '动效',
      'ds.section.motion.desc':       '三种新动效（pulse-dispatch / flow-down / verify-gate-glow）外加现有的 scan-flicker 参考——全部支持 reduce-motion。',
      'ds.section.components':        '组件',
      'ds.section.components.desc':   '新页面依赖的八个可复用基础组件。',
      'ds.section.states':            '状态',
      'ds.section.states.desc':       'active / pass / fail / escalated / reinforced 的样式约定。',
      'ds.section.accessibility':     '可访问性',
      'ds.section.accessibility.desc':'动效降级、WCAG 对比度、键盘焦点、双语切换的承诺。',
      'ds.swatch.copy':               '复制 CSS 变量',
      'ds.swatch.copied':             '已复制',
      'ds.motion.replay':             '重放',
      'ds.motion.label.pulse':        'pulse-dispatch',
      'ds.motion.label.flow':         'flow-down',
      'ds.motion.label.gateGlow':     'verify-gate-glow',
      'ds.motion.label.scanFlicker':  'scan-flicker（现有）',
      'ds.a11y.reducedMotion':        '所有动效遵循 `prefers-reduced-motion: reduce`。',
      'ds.a11y.contrast':             '正文在双主题下均满足 WCAG AA；新令牌均为此选定。',
      'ds.a11y.keyboard':             '所有交互控件均可键盘聚焦，焦点可见。',
      'ds.a11y.bilingual':            '一键切换中英文，偏好保存于 localStorage。',

      /* -- 框架链路页 -- */
      'fc.subtitle':                       '项目 → 阶段 → 波次 → 任务——让链路动起来。',
      'fc.section.hierarchy':              '四层层次结构',
      'fc.section.hierarchy.desc':         '每层向下派发、向上汇报；只有 L3 真正执行工作。',
      'fc.section.teams':                  '代理团队',
      'fc.section.teams.desc':             '五大团队：调研 / 设计 / 实现 / 测试 / 评审。',
      'fc.section.gate':                   '门控机制',
      'fc.section.gate.desc':              '4 维（含校验时为 7 维）综合评分；四种配置、三个通过条件。',
      'fc.section.loops':                  '波次协调',
      'fc.section.loops.desc':             '并行 / 顺序 / 生成-校验 / 混合——通过 DAG 分析自动选择。',
      'fc.section.rationalization':        '规避借口',
      'fc.section.rationalization.desc':   'SKILL 预先反驳的八条常见借口——没有捷径。',
      'fc.layer.mustNot':                  '禁止',
      'fc.gate.standardLabel':             '标准（4 维）',
      'fc.gate.extendedLabel':             '扩展（7 维）',
      'fc.gate.simulateFail':              '模拟基准维度失败',
      'fc.replay':                         '重放级联动效',
      'fc.aside.close':                    '关闭',
      'fc.team.research':                  '调研',
      'fc.team.design':                    '设计',
      'fc.team.implement':                 '实现',
      'fc.team.test':                      '测试',
      'fc.team.review':                    '评审',
      'fc.loop.parallel':                  '并行',
      'fc.loop.sequential':                '顺序',
      'fc.loop.genVerify':                 '生成-校验',
      'fc.loop.hybrid':                    '混合',

      /* -- 上下文流转页 -- */
      'cf.subtitle':                              '看消息流动——下派、上报、上升、轮次强化。',
      'cf.section.dispatch':                      '派发（L0 → L3）',
      'cf.section.dispatch.desc':                 'TaskDispatch 信封沿轨道从 Project 流向 Task。',
      'cf.section.report':                        '状态汇报（L3 → L0）',
      'cf.section.report.desc':                   'StatusReport 信封在完成或部分进度时沿轨道向上流转。',
      'cf.section.escalation':                    '升级链',
      'cf.section.escalation.desc':               '始终向上、不跳级——Task → Wave → Stage → Project → 人类。',
      'cf.section.reinforcement':                 '轮次强化（v5.1+，v6.0.3 真正接通）',
      'cf.section.reinforcement.desc':            '门控 FAIL → 取前 5 条（≥ major）→ 作为 MUST-fix 注入下一轮派发。',
      'cf.section.isolation':                     '上下文隔离',
      'cf.section.isolation.desc':                '哪些不可在代理间泄露，哪些可通过制品摘要共享。',
      'cf.envelope.fields':                       '必填字段',
      'cf.envelope.example':                      '示例负载',
      'cf.escalation.severity.autoRecover':       'AUTO_RECOVER — 指数退避重试最多 3 次',
      'cf.escalation.severity.pause':             'PAUSE — 暂停任务、排队提问、并行工作继续',
      'cf.escalation.severity.humanIntervene':    'HUMAN_INTERVENE — 暂停阶段、向人类呈现选项',
      'cf.escalation.severity.fullRollback':      'FULL_ROLLBACK — 回滚至检查点、全部停止',
      'cf.reinforcement.step':                    '下一步 ▶',
      'cf.reinforcement.reset':                   '重置',
      'cf.reinforcement.round1':                  '第 1 轮派发',
      'cf.reinforcement.round2':                  '第 2 轮派发（已强化）',
      'cf.reinforcement.findings':                '按严重性过滤的发现',
      'cf.isolation.mustNotLeak':                 '禁止泄漏',
      'cf.isolation.isShared':                    '通过制品摘要共享',
      'cf.play':                                  '播放',
      'cf.pause':                                 '暂停',

      /* -- 版本演进页 -- */
      'vt.subtitle':                       '从 v0.1.0 到 v7.1.0——六个时代、有守护的演进。',
      'vt.era.foundations':                '奠基',
      'vt.era.evobench':                   'EvoBench 与加固',
      'vt.era.selfImprove':                '自我改进闭环',
      'vt.era.platforms':                  '平台扩展与收口',
      'vt.era.compression':                '分阶段上下文压缩',
      'vt.era.rollup':                     '总集与稳定',
      'vt.era.foundations.desc':           'v0.1.0 – v2.2.0：脚手架、最初的 11 个模板、信息密度 +93%。',
      'vt.era.evobench.desc':              'v3.0.0 – v3.9.x：EvoBench、仓库规则、全工作流覆盖、P1 真正落地。',
      'vt.era.selfImprove.desc':           'v4.0.0 – v5.4.2：模型路由、插件注册、NineS、强化基础设施。',
      'vt.era.platforms.desc':             'v6.0.0 – v6.1.5：11 个平台、死线接通、schema 对齐、Plan-mode 运行时。',
      'vt.era.compression.desc':           'v7.0.0 → v7.1.0：缓存布局不变量、工具输出截断、层级化摘要、持久化探针、操作学习 v2。',
      'vt.era.rollup.desc':                'v6.2.0 – v7.1.0：SI-3 9.47/10、1100 测试、NineS 0.8805 稳定、周期收口。',
      'vt.filter.all':                     '全部时代',
      'vt.toggle.compact':                 '简洁',
      'vt.toggle.detailed':                '详细',
      'vt.card.expand':                    '展开',
      'vt.card.collapse':                  '折叠',
      'vt.metric.tests':                   '测试',
      'vt.metric.coverage':                '覆盖率',
      'vt.metric.nines':                   'NineS',
      'vt.metric.composite':               '综合分',
      'vt.cta.changelog':                  '查看 CHANGELOG',
      'vt.cta.releases':                   'GitHub 发布'
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
