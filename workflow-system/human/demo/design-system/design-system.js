/**
 * DevolaFlow Design System showcase
 * Renders live shared tokens, registers page-local EN/ZH copy, and wires
 * keyboard-native copy and motion replay controls.
 */
(function () {
  'use strict';

  var TRANSLATIONS = {
    en: {
      'page.designSystem': 'Design System — DevolaFlow',
      'ds.skip': 'Skip to design system content',
      'ds.hero.eyebrow': 'System companion · v17 visual foundation',
      'ds.hero.title': 'Design System',
      'ds.hero.tagline': 'A quiet, warm interface for evidence-backed software change.',
      'ds.hero.note': 'One token source serves every demo route. Light and Dark values stay visible together below.',
      'ds.aria.ctas': 'Design system companion pages',
      'ds.cta.system': 'Open System',
      'ds.cta.io': 'Open I/O',
      'ds.cta.timeline': 'Open Timeline',
      'ds.cta.skill': 'Read SKILL ↗',
      'ds.tokens.title': 'Live Light / Dark tokens',
      'ds.tokens.desc': 'Every value is read from the shared stylesheet at runtime. Select a TokenSwatch to copy its CSS variable name.',
      'ds.tokens.loading': 'Reading shared tokens…',
      'ds.theme.light': 'Warm parchment',
      'ds.theme.light.desc': 'Gold guides action; Devola Red marks human attention.',
      'ds.theme.dark': 'Quiet bunker',
      'ds.theme.dark.desc': 'The same hierarchy and semantics hold without glow or novelty effects.',
      'ds.preview.primary': 'Primary action',
      'ds.foundations.title': 'Typography and layout policy',
      'ds.foundations.desc': 'The system uses one deliberate type stack and a compact spacing, radius, and border vocabulary.',
      'ds.type.heading': 'Editorial headings and the DevolaFlow wordmark · weights 400 / 700',
      'ds.type.body': 'Body copy, navigation, forms, and controls · weights 400 / 500 / 600 / 700',
      'ds.type.mono': 'Commands, paths, message names, tokens, and measured facts · weights 400 / 500',
      'ds.policy.spacing': 'spacing · 4px base',
      'ds.policy.spacing.desc': 'Use the six shared steps. Prefer whitespace over nested containers.',
      'ds.policy.radius': 'radius · 3 / 6 / 10px',
      'ds.policy.radius.desc': 'Controls stay compact; larger radii are reserved for broad preview surfaces.',
      'ds.policy.border': 'border · 1px by default',
      'ds.policy.border.desc': 'Borders carry hierarchy. Four-pixel left rules are reserved for semantic emphasis.',
      'ds.policy.elevation': 'elevation · two restrained levels',
      'ds.policy.elevation.desc': 'Shadows clarify overlays and active surfaces; they never simulate glow.',
      'ds.states.title': 'Semantic states',
      'ds.states.desc': 'Color is paired with explicit language and a stable border treatment. A scalar score is never the primary message.',
      'ds.state.ready': 'Evidence available and threshold met',
      'ds.state.ready.desc': 'Use success green only after required evidence is available.',
      'ds.state.review': 'Attention without failure',
      'ds.state.review.desc': 'Gold marks the current action, a bounded warning, or a decision in progress.',
      'ds.state.insufficient': 'Required evidence is unavailable',
      'ds.state.insufficient.desc': 'Devola Red signals a human-visible stop; prose cannot convert it into a pass.',
      'ds.components.title': 'Shared component examples',
      'ds.components.desc': 'Components stay shallow, rectangular, and evidence-first. These are live shared classes, not screenshots.',
      'ds.component.confirm': 'Confirm',
      'ds.component.inspect': 'Inspect',
      'ds.component.defer': 'Defer',
      'ds.component.button.desc': 'Three emphasis levels; all controls keep a 44px minimum target.',
      'ds.component.task': 'Task',
      'ds.component.task.desc': 'Implements one atomic assignment and returns criterion-level evidence.',
      'ds.component.layer.desc': 'Layer identity, budget, and responsibility without decorative nesting.',
      'ds.component.message.desc': 'Typed payloads use a border direction and verbatim field names.',
      'ds.component.swatch.desc': 'A keyboard-operable token reference with copy feedback and failure recovery.',
      'ds.motion.title': 'Motion restraint',
      'ds.motion.desc': 'Motion is brief, finite, and explanatory: no looping glow, decorative scanlines, or hover transforms. Replay is always user-initiated.',
      'ds.motion.replay': 'Replay motion',
      'ds.motion.replayed': 'Motion replayed.',
      'ds.motion.reduced': 'Motion is minimized by your reduced-motion preference.',
      'ds.access.title': 'Accessibility is part of the component contract',
      'ds.access.desc': 'The shared layer defines the baseline; page-local CSS may specialize layout without weakening it.',
      'ds.access.focus': 'A high-contrast 3px focus ring appears for keyboard navigation.',
      'ds.access.target': 'Buttons, links acting as controls, and navigation targets meet the minimum touch size.',
      'ds.access.motion': 'Animation and transition duration collapses while content remains complete.',
      'ds.access.theme': 'Semantic contrast is maintained in both themes; state meaning never relies on color alone.',
      'ds.access.language': 'Navigation, interaction feedback, labels, and explanations switch together.',
      'ds.access.keyboard': 'Native buttons power token copy and motion replay; no pointer-only interaction is required.',
      'ds.access.try': 'Use Tab to inspect the shared focus treatment:',
      'ds.access.link': 'Jump to tokens',
      'ds.access.button': 'Focusable button',
      'ds.access.input': 'Labeled input',
      'ds.footer': 'DevolaFlow v17 visual foundation · warm, legible, and restrained.',
      'ds.token.group.colors': 'Color and semantic roles',
      'ds.token.group.colors.desc': 'Exact palette values for surfaces, text, action, and state.',
      'ds.token.group.type': 'Typography',
      'ds.token.group.type.desc': 'One family for editorial, interface, and code contexts.',
      'ds.token.group.spacing': 'Spacing',
      'ds.token.group.spacing.desc': 'A 4px-based scale shared by page and component layout.',
      'ds.token.group.geometry': 'Radius, border, and focus',
      'ds.token.group.geometry.desc': 'Small geometry choices keep the interface precise.',
      'ds.token.group.behavior': 'Elevation, motion, and navigation',
      'ds.token.group.behavior.desc': 'Restrained depth, finite timing, and one shared header height.',
      'ds.token.light': 'Light',
      'ds.token.dark': 'Dark',
      'ds.token.copy': 'Copy CSS variable',
      'ds.copy.success': 'Copied',
      'ds.copy.failed': 'Copy failed. Select this token name manually:'
    },
    zh: {
      'page.designSystem': '设计体系 — DevolaFlow',
      'ds.skip': '跳到设计体系内容',
      'ds.hero.eyebrow': '系统配套页 · v17 视觉基础',
      'ds.hero.title': '设计体系',
      'ds.hero.tagline': '为证据驱动的软件变更提供安静、温暖的界面。',
      'ds.hero.note': '一套令牌服务全部演示路由；下方同时展示浅色与深色值。',
      'ds.aria.ctas': '设计体系配套页面',
      'ds.cta.system': '打开系统',
      'ds.cta.io': '打开输入输出',
      'ds.cta.timeline': '打开时间线',
      'ds.cta.skill': '阅读 SKILL ↗',
      'ds.tokens.title': '实时浅色 / 深色令牌',
      'ds.tokens.desc': '所有值均在运行时从共享样式表读取。选择 TokenSwatch 可复制其 CSS 变量名。',
      'ds.tokens.loading': '正在读取共享令牌…',
      'ds.theme.light': '温暖羊皮纸',
      'ds.theme.light.desc': '金色引导操作；Devola 红标记需要人关注之处。',
      'ds.theme.dark': '安静地堡',
      'ds.theme.dark.desc': '保持相同层级与语义，不使用光晕或猎奇效果。',
      'ds.preview.primary': '主要操作',
      'ds.foundations.title': '排版与布局策略',
      'ds.foundations.desc': '系统只采用一套明确字型栈，以及紧凑的间距、圆角和边框词汇。',
      'ds.type.heading': '编辑式标题与 DevolaFlow 字标 · 字重 400 / 700',
      'ds.type.body': '正文、导航、表单与控件 · 字重 400 / 500 / 600 / 700',
      'ds.type.mono': '命令、路径、消息名、令牌与实测事实 · 字重 400 / 500',
      'ds.policy.spacing': '间距 · 以 4px 为基准',
      'ds.policy.spacing.desc': '使用六个共享档位，以留白取代嵌套容器。',
      'ds.policy.radius': '圆角 · 3 / 6 / 10px',
      'ds.policy.radius.desc': '控件保持紧凑；较大圆角只用于宽阔预览表面。',
      'ds.policy.border': '边框 · 默认 1px',
      'ds.policy.border.desc': '边框承担层级表达；4px 左边线仅用于语义强调。',
      'ds.policy.elevation': '层级 · 两档克制阴影',
      'ds.policy.elevation.desc': '阴影只澄清浮层与活动表面，绝不模拟光晕。',
      'ds.states.title': '语义状态',
      'ds.states.desc': '颜色必须搭配明确文字与稳定边框；单一分数绝不成为主要信息。',
      'ds.state.ready': '证据可用且达到阈值',
      'ds.state.ready.desc': '仅当必需证据可用后才使用成功绿。',
      'ds.state.review': '需要注意，但尚未失败',
      'ds.state.review.desc': '金色标记当前操作、有界警告或进行中的决定。',
      'ds.state.insufficient': '必需证据不可用',
      'ds.state.insufficient.desc': 'Devola 红表示人可见的停止；文字说明不能把它改写为通过。',
      'ds.components.title': '共享组件示例',
      'ds.components.desc': '组件保持扁平、矩形且证据优先；这些是共享类的实时渲染，不是截图。',
      'ds.component.confirm': '确认',
      'ds.component.inspect': '检查',
      'ds.component.defer': '暂缓',
      'ds.component.button.desc': '三种强调级别；所有控件保留至少 44px 的目标尺寸。',
      'ds.component.task': 'Task',
      'ds.component.task.desc': '实现一个原子任务，并返回逐项验收证据。',
      'ds.component.layer.desc': '呈现层级身份、预算与职责，不做装饰性嵌套。',
      'ds.component.message.desc': '类型化载荷使用方向边线与原样字段名。',
      'ds.component.swatch.desc': '支持键盘操作的令牌参考，提供复制反馈与失败恢复。',
      'ds.motion.title': '克制动效',
      'ds.motion.desc': '动效短暂、有限且用于解释：不循环发光，不使用装饰扫描线或悬停位移。重放始终由用户触发。',
      'ds.motion.replay': '重放动效',
      'ds.motion.replayed': '动效已重放。',
      'ds.motion.reduced': '已按你的减少动态效果偏好最小化动效。',
      'ds.access.title': '可访问性属于组件契约',
      'ds.access.desc': '共享层定义基线；页面局部 CSS 可以专门化布局，但不能削弱基线。',
      'ds.access.focus': '键盘导航时显示高对比度 3px 焦点环。',
      'ds.access.target': '按钮、充当控件的链接和导航目标均满足最小触控尺寸。',
      'ds.access.motion': '动画与过渡时长被压缩，内容仍保持完整。',
      'ds.access.theme': '双主题均保持语义对比，状态含义从不只依赖颜色。',
      'ds.access.language': '导航、交互反馈、标签与说明同步切换。',
      'ds.access.keyboard': '令牌复制与动效重放均使用原生按钮，不要求仅指针操作。',
      'ds.access.try': '使用 Tab 检查共享焦点样式：',
      'ds.access.link': '跳到令牌',
      'ds.access.button': '可聚焦按钮',
      'ds.access.input': '有标签输入框',
      'ds.footer': 'DevolaFlow v17 视觉基础 · 温暖、清晰、克制。',
      'ds.token.group.colors': '颜色与语义角色',
      'ds.token.group.colors.desc': '表面、文字、操作与状态的精确调色值。',
      'ds.token.group.type': '排版',
      'ds.token.group.type.desc': '分别服务编辑、界面与代码场景的三种字族。',
      'ds.token.group.spacing': '间距',
      'ds.token.group.spacing.desc': '页面和组件布局共享的 4px 基准比例。',
      'ds.token.group.geometry': '圆角、边框与焦点',
      'ds.token.group.geometry.desc': '小而明确的几何选择保持界面精确。',
      'ds.token.group.behavior': '层级、动效与导航',
      'ds.token.group.behavior.desc': '克制深度、有限时长与统一页头高度。',
      'ds.token.light': '浅色',
      'ds.token.dark': '深色',
      'ds.token.copy': '复制 CSS 变量',
      'ds.copy.success': '已复制',
      'ds.copy.failed': '复制失败，请手动选择此令牌名：'
    }
  };

  var TOKEN_GROUPS = [
    {
      label: 'ds.token.group.colors',
      description: 'ds.token.group.colors.desc',
      kind: 'color',
      tokens: [
        '--bg', '--fg', '--card-bg', '--border', '--border-strong',
        '--accent', '--accent-hover', '--accent-light', '--muted',
        '--success', '--warning', '--error', '--secondary', '--code-bg',
        '--rail-track', '--ink-deep'
      ]
    },
    {
      label: 'ds.token.group.type',
      description: 'ds.token.group.type.desc',
      kind: 'text',
      tokens: ['--font-heading', '--font-body', '--font-mono']
    },
    {
      label: 'ds.token.group.spacing',
      description: 'ds.token.group.spacing.desc',
      kind: 'text',
      tokens: ['--space-1', '--space-2', '--space-3', '--space-4', '--space-5', '--space-6']
    },
    {
      label: 'ds.token.group.geometry',
      description: 'ds.token.group.geometry.desc',
      kind: 'text',
      tokens: ['--radius-sm', '--radius', '--radius-lg', '--border-width', '--focus-ring']
    },
    {
      label: 'ds.token.group.behavior',
      description: 'ds.token.group.behavior.desc',
      kind: 'text',
      tokens: ['--shadow', '--shadow-lg', '--motion-fast', '--motion-standard', '--nav-height']
    }
  ];

  function translate(key) {
    if (typeof window.t === 'function') {
      return window.t(key);
    }
    return TRANSLATIONS.en[key] || key;
  }

  function registerTranslations() {
    if (typeof window.addTranslations !== 'function') {
      console.warn('design-system: shared i18n registration is unavailable');
      return;
    }
    window.addTranslations('en', TRANSLATIONS.en);
    window.addTranslations('zh', TRANSLATIONS.zh);
  }

  function readToken(probe, token) {
    return window.getComputedStyle(probe).getPropertyValue(token).trim();
  }

  function createValue(themeKey, value, kind) {
    var item = document.createElement('span');
    item.className = 'token-value';

    var label = document.createElement('span');
    label.className = 'token-value-label';
    label.textContent = translate(themeKey);
    item.appendChild(label);

    if (kind === 'color') {
      var chip = document.createElement('i');
      chip.className = 'token-color-chip';
      chip.style.backgroundColor = value;
      chip.setAttribute('aria-hidden', 'true');
      item.appendChild(chip);
    }

    var output = document.createElement('span');
    output.className = 'token-value-output';
    output.textContent = value;
    item.appendChild(output);
    return item;
  }

  function createTokenCard(token, kind, lightValue, darkValue) {
    var button = document.createElement('button');
    button.type = 'button';
    button.className = 'token-card swatch';
    button.setAttribute('data-copy-token', token);
    button.setAttribute('aria-label', translate('ds.token.copy') + ': ' + token);

    var header = document.createElement('span');
    header.className = 'token-card-header';
    var code = document.createElement('code');
    code.textContent = token;
    var hint = document.createElement('small');
    hint.textContent = translate('ds.token.copy');
    header.appendChild(code);
    header.appendChild(hint);

    var values = document.createElement('span');
    values.className = 'token-values';
    values.appendChild(createValue('ds.token.light', lightValue, kind));
    values.appendChild(createValue('ds.token.dark', darkValue, kind));

    button.appendChild(header);
    button.appendChild(values);
    return button;
  }

  function renderTokenGroups() {
    var host = document.getElementById('ds-token-groups');
    var lightProbe = document.getElementById('ds-light-probe');
    var darkProbe = document.getElementById('ds-dark-probe');
    if (!host || !lightProbe || !darkProbe) {
      console.warn('design-system: token host or theme probes are unavailable');
      return;
    }

    host.replaceChildren();
    TOKEN_GROUPS.forEach(function (group) {
      var section = document.createElement('section');
      section.className = 'token-group';

      var heading = document.createElement('div');
      heading.className = 'token-group-heading';
      var title = document.createElement('h3');
      title.textContent = translate(group.label);
      var description = document.createElement('p');
      description.textContent = translate(group.description);
      heading.appendChild(title);
      heading.appendChild(description);

      var grid = document.createElement('div');
      grid.className = 'token-grid';
      group.tokens.forEach(function (token) {
        grid.appendChild(createTokenCard(
          token,
          group.kind,
          readToken(lightProbe, token),
          readToken(darkProbe, token)
        ));
      });

      section.appendChild(heading);
      section.appendChild(grid);
      host.appendChild(section);
    });
  }

  function legacyCopy(text) {
    return new Promise(function (resolve, reject) {
      var textarea = document.createElement('textarea');
      var previousFocus = document.activeElement;
      textarea.value = text;
      textarea.setAttribute('readonly', '');
      textarea.style.position = 'fixed';
      textarea.style.left = '-9999px';
      document.body.appendChild(textarea);
      textarea.focus();
      textarea.select();

      var copied = false;
      var copyError = null;
      try {
        copied = document.execCommand('copy');
      } catch (error) {
        copyError = error;
      }
      document.body.removeChild(textarea);
      if (previousFocus && typeof previousFocus.focus === 'function') {
        previousFocus.focus();
      }

      if (copied) {
        resolve();
      } else {
        reject(copyError || new Error('document.execCommand("copy") returned false'));
      }
    });
  }

  function copyText(text) {
    if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
      try {
        return Promise.resolve(navigator.clipboard.writeText(text)).catch(function (error) {
          console.warn('design-system: Clipboard API failed; trying the selection fallback.', error);
          return legacyCopy(text);
        });
      } catch (error) {
        console.warn('design-system: Clipboard API threw; trying the selection fallback.', error);
        return legacyCopy(text);
      }
    }
    return legacyCopy(text);
  }

  var toastTimer = null;
  function showToast(message, duration) {
    var toast = document.getElementById('ds-toast');
    if (!toast) {
      console.warn('design-system: feedback toast is unavailable:', message);
      return;
    }
    toast.textContent = message;
    toast.classList.add('is-visible');
    if (toastTimer) {
      window.clearTimeout(toastTimer);
    }
    toastTimer = window.setTimeout(function () {
      toast.classList.remove('is-visible');
    }, duration || 2200);
  }

  function handleCopy(button) {
    var token = button.getAttribute('data-copy-token');
    if (!token) {
      console.warn('design-system: copy control has no token name');
      return;
    }
    copyText(token).then(function () {
      button.classList.add('is-copied');
      showToast(translate('ds.copy.success') + ': ' + token);
      window.setTimeout(function () {
        button.classList.remove('is-copied');
      }, 1600);
    }).catch(function (error) {
      console.warn('design-system: clipboard and fallback copy both failed for ' + token, error);
      showToast(translate('ds.copy.failed') + ' ' + token, 5000);
    });
  }

  function wireCopyControls() {
    document.querySelectorAll('[data-copy-token]').forEach(function (button) {
      button.setAttribute(
        'aria-label',
        translate('ds.token.copy') + ': ' + button.getAttribute('data-copy-token')
      );
      if (button.getAttribute('data-copy-bound') === 'true') {
        return;
      }
      button.setAttribute('data-copy-bound', 'true');
      button.addEventListener('click', function () {
        handleCopy(button);
      });
    });
  }

  function reducedMotionRequested() {
    return window.matchMedia &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  }

  function setMotionStatus(message) {
    var status = document.getElementById('ds-motion-status');
    if (status) {
      status.textContent = message;
    }
  }

  function replayMotion(button) {
    var className = button.getAttribute('data-motion-class');
    var figure = button.closest('[data-motion]');
    var target = figure && figure.querySelector('.motion-object');
    if (!className || !target) {
      console.warn('design-system: motion replay target is unavailable');
      return;
    }
    target.classList.remove(className);
    void target.offsetWidth;
    target.classList.add(className);
    setMotionStatus(translate(
      reducedMotionRequested() ? 'ds.motion.reduced' : 'ds.motion.replayed'
    ));
  }

  function wireMotionControls() {
    document.querySelectorAll('.motion-replay').forEach(function (button) {
      button.addEventListener('click', function () {
        replayMotion(button);
      });
    });

    if (reducedMotionRequested()) {
      setMotionStatus(translate('ds.motion.reduced'));
    }
  }

  function applyAriaLabels() {
    document.querySelectorAll('[data-ds-aria]').forEach(function (element) {
      element.setAttribute('aria-label', translate(element.getAttribute('data-ds-aria')));
    });
  }

  function refreshLocalizedInteractions() {
    renderTokenGroups();
    wireCopyControls();
    applyAriaLabels();
    if (reducedMotionRequested()) {
      setMotionStatus(translate('ds.motion.reduced'));
    }
  }

  function init() {
    refreshLocalizedInteractions();
    wireMotionControls();
    document.addEventListener('devolaflow:languagechange', refreshLocalizedInteractions);

    if (typeof window.setLanguage === 'function') {
      window.setLanguage(
        document.documentElement.getAttribute('data-lang') || 'en'
      );
    }
  }

  registerTranslations();
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
