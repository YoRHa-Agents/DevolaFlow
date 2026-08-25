/**
 * DevolaFlow shared internationalization infrastructure.
 *
 * This dictionary intentionally contains shell-level language only. Individual
 * pages register their bilingual content through window.addTranslations().
 */
(function () {
  'use strict';

  var LANG_KEY = 'devolaflow-lang';
  var DEFAULT_LANG = 'en';

  var TRANSLATIONS = {
    en: {
      /* Primary navigation: keep this set aligned with shared/nav.js. */
      'nav.home': 'Home',
      'nav.system': 'System',
      'nav.io': 'I/O',
      'nav.harness': 'Harness',
      'nav.timeline': 'Timeline',
      'nav.home.desc': 'Current product overview and installation.',
      'nav.system.desc': 'Three-layer orchestration, checklist rounds, and gates.',
      'nav.io.desc': 'Typed dispatch, report, escalation, and artifact flow.',
      'nav.harness.desc': 'Evidence inputs, six-dimension evaluation, and verdicts.',
      'nav.timeline.desc': 'Release history with retired eras clearly marked.',

      /* Shared controls and footer. */
      'theme.toggle': 'Toggle color theme',
      'control.navigation': 'Primary navigation',
      'control.menu': 'Open navigation menu',
      'control.close': 'Close navigation menu',
      'control.language': 'Switch language',
      'common.skip': 'Skip to main content',
      'footer.text': 'DevolaFlow',
      'footer.github': 'GitHub',
      'footer.license': 'MIT License',

      /* Shared statuses and actions. */
      'common.version': 'Version',
      'common.status': 'Status',
      'common.current': 'Current',
      'common.historical': 'Historical',
      'common.ready': 'Ready',
      'common.insufficient': 'Insufficient',
      'common.loading': 'Loading…',
      'common.error': 'Error',
      'common.success': 'Success',
      'common.warning': 'Warning',
      'common.back': 'Back',
      'common.learnMore': 'Learn more',
      'common.viewAll': 'View all',
      'common.open': 'Open',
      'common.close': 'Close',
      'common.play': 'Play',
      'common.pause': 'Pause',
      'common.retry': 'Retry',

      /* Primary destination titles. */
      'page.home': 'DevolaFlow — A Guardian\'s Song for Your Code',
      'page.system': 'System — DevolaFlow',
      'page.io': 'I/O — DevolaFlow',
      'page.harness': 'Harness — DevolaFlow',
      'page.timeline': 'Timeline — DevolaFlow',

      /* Stable compatibility-route titles. */
      'page.landing': 'DevolaFlow — A Guardian\'s Song for Your Code',
      'page.frameworkChain': 'System — DevolaFlow',
      'page.contextFlow': 'I/O — DevolaFlow',
      'page.benchmarks': 'Harness — DevolaFlow',
      'page.versionTimeline': 'Timeline — DevolaFlow',
      'page.designSystem': 'Design System — DevolaFlow',
      'page.architecture': 'Design Architecture — DevolaFlow',
      'page.visualizer': 'Workflow Visualizer — DevolaFlow',
      'page.explorer': 'Primitive Explorer — DevolaFlow'
    },

    zh: {
      /* 主导航：与 shared/nav.js 保持一致。 */
      'nav.home': '首页',
      'nav.system': '系统',
      'nav.io': '输入输出',
      'nav.harness': '评估',
      'nav.timeline': '时间线',
      'nav.home.desc': '当前产品概览与安装入口。',
      'nav.system.desc': '三层编排、清单轮次与门控。',
      'nav.io.desc': '类型化派发、汇报、升级与制品流。',
      'nav.harness.desc': '证据输入、六维评估与明确判定。',
      'nav.timeline.desc': '完整发布历史，并清晰标记已退役时代。',

      /* 共享控件与页脚。 */
      'theme.toggle': '切换颜色主题',
      'control.navigation': '主导航',
      'control.menu': '打开导航菜单',
      'control.close': '关闭导航菜单',
      'control.language': '切换语言',
      'common.skip': '跳到主要内容',
      'footer.text': 'DevolaFlow',
      'footer.github': 'GitHub',
      'footer.license': 'MIT 协议',

      /* 共享状态与操作。 */
      'common.version': '版本',
      'common.status': '状态',
      'common.current': '当前',
      'common.historical': '历史',
      'common.ready': '就绪',
      'common.insufficient': '证据不足',
      'common.loading': '加载中…',
      'common.error': '错误',
      'common.success': '成功',
      'common.warning': '警告',
      'common.back': '返回',
      'common.learnMore': '了解更多',
      'common.viewAll': '查看全部',
      'common.open': '打开',
      'common.close': '关闭',
      'common.play': '播放',
      'common.pause': '暂停',
      'common.retry': '重试',

      /* 五个主目的地标题。 */
      'page.home': 'DevolaFlow — 守护者为代码而歌',
      'page.system': '系统 — DevolaFlow',
      'page.io': '输入输出 — DevolaFlow',
      'page.harness': '评估体系 — DevolaFlow',
      'page.timeline': '时间线 — DevolaFlow',

      /* 稳定兼容路由标题。 */
      'page.landing': 'DevolaFlow — 守护者为代码而歌',
      'page.frameworkChain': '系统 — DevolaFlow',
      'page.contextFlow': '输入输出 — DevolaFlow',
      'page.benchmarks': '评估体系 — DevolaFlow',
      'page.versionTimeline': '时间线 — DevolaFlow',
      'page.designSystem': '设计体系 — DevolaFlow',
      'page.architecture': '设计架构 — DevolaFlow',
      'page.visualizer': '工作流可视化 — DevolaFlow',
      'page.explorer': '原语探索器 — DevolaFlow'
    }
  };

  /**
   * Look up a translation for the current language.
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

  function readStoredLanguage() {
    try {
      return window.localStorage.getItem(LANG_KEY);
    } catch (error) {
      console.warn('DevolaFlow i18n could not read localStorage.', error);
      return null;
    }
  }

  function storeLanguage(lang) {
    try {
      window.localStorage.setItem(LANG_KEY, lang);
    } catch (error) {
      console.warn('DevolaFlow i18n could not write localStorage.', error);
    }
  }

  function setLanguage(lang) {
    if (!TRANSLATIONS[lang]) { lang = DEFAULT_LANG; }
    document.documentElement.setAttribute('data-lang', lang);
    document.documentElement.lang = lang;
    storeLanguage(lang);

    document.querySelectorAll('[data-i18n]').forEach(function (element) {
      var value = t(element.getAttribute('data-i18n'));
      if (value) { element.textContent = value; }
    });

    document.querySelectorAll('[data-i18n-placeholder]').forEach(function (element) {
      var value = t(element.getAttribute('data-i18n-placeholder'));
      if (value) { element.placeholder = value; }
    });

    document.querySelectorAll('[data-i18n-title]').forEach(function (element) {
      var value = t(element.getAttribute('data-i18n-title'));
      if (value) { element.title = value; }
    });

    document.querySelectorAll('[data-i18n-aria]').forEach(function (element) {
      var value = t(element.getAttribute('data-i18n-aria'));
      if (value) { element.setAttribute('aria-label', value); }
    });

    document.dispatchEvent(new CustomEvent('devolaflow:languagechange', {
      detail: { lang: lang }
    }));
  }

  function addTranslations(lang, entries) {
    if (!TRANSLATIONS[lang]) { TRANSLATIONS[lang] = {}; }
    for (var key in entries) {
      if (Object.prototype.hasOwnProperty.call(entries, key)) {
        TRANSLATIONS[lang][key] = entries[key];
      }
    }
    if (lang === currentLang()) {
      setLanguage(lang);
    }
  }

  function init() {
    setLanguage(readStoredLanguage() || DEFAULT_LANG);
  }

  window.t = t;
  window.setLanguage = setLanguage;
  window.addTranslations = addTranslations;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
