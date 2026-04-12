/**
 * DevolaFlow — shared/nav.js
 * Injects a consistent navigation bar, theme toggle, and language switcher
 * into every demo page. Auto-detects landing vs sub-page for relative paths.
 */
(function () {
  'use strict';

  var THEME_KEY = 'devolaflow-theme';
  var GITHUB_URL = 'https://github.com/YoRHa-Agents/DevolaFlow';

  var isLanding = (function () {
    var path = window.location.pathname;
    return path.endsWith('/demo/') ||
           path.endsWith('/demo/index.html') ||
           path.match(/\/demo\/?$/);
  })();

  function prefix(subPath) {
    return isLanding ? subPath : '../' + subPath;
  }

  var NAV_LINKS = [
    { key: 'nav.home',         href: isLanding ? 'index.html' : '../index.html' },
    { key: 'nav.architecture', href: prefix('design-architecture/index.html') },
    { key: 'nav.visualizer',   href: prefix('workflow-visualizer/index.html') },
    { key: 'nav.explorer',     href: prefix('stage-explorer/index.html') },
    { key: 'nav.benchmarks',   href: prefix('benchmark-results/index.html') },
    { key: 'nav.docs',         href: GITHUB_URL + '/blob/main/workflow-system/human/en/quickstart.md' }
  ];

  var LABELS_EN = {
    'nav.home': 'Home', 'nav.architecture': 'Architecture',
    'nav.visualizer': 'Visualizer', 'nav.explorer': 'Explorer',
    'nav.benchmarks': 'Benchmarks', 'nav.docs': 'Docs'
  };
  var LABELS_ZH = {
    'nav.home': '首页', 'nav.architecture': '架构',
    'nav.visualizer': '可视化', 'nav.explorer': '探索器',
    'nav.benchmarks': '基准测试', 'nav.docs': '文档'
  };

  function currentPageId() {
    var path = window.location.pathname;
    if (path.match(/design-architecture/)) { return 'nav.architecture'; }
    if (path.match(/workflow-visualizer/))  { return 'nav.visualizer'; }
    if (path.match(/stage-explorer/))       { return 'nav.explorer'; }
    if (path.match(/benchmark-results/))    { return 'nav.benchmarks'; }
    if (isLanding)                          { return 'nav.home'; }
    return '';
  }

  /* ---- Theme ---- */

  function getPreferredTheme() {
    var stored = localStorage.getItem(THEME_KEY);
    if (stored === 'dark' || stored === 'light') { return stored; }
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }

  function applyTheme(theme) {
    document.documentElement.classList.toggle('dark', theme === 'dark');
    localStorage.setItem(THEME_KEY, theme);
    var btn = document.getElementById('df-theme-toggle');
    if (btn) { btn.textContent = theme === 'dark' ? '☀️' : '🌙'; }
  }

  function toggleTheme() {
    applyTheme(document.documentElement.classList.contains('dark') ? 'light' : 'dark');
  }

  /* ---- Language ---- */

  function currentLang() {
    return document.documentElement.getAttribute('data-lang') || 'en';
  }

  function toggleLang() {
    var next = currentLang() === 'en' ? 'zh' : 'en';
    if (typeof window.setLanguage === 'function') {
      window.setLanguage(next);
    } else {
      document.documentElement.setAttribute('data-lang', next);
      document.documentElement.lang = next;
      localStorage.setItem('devolaflow-lang', next);
    }
    updateNavLabels();
    updateLangButton();
  }

  function updateLangButton() {
    var lang = currentLang();
    document.querySelectorAll('.lang-option').forEach(function (el) {
      el.classList.toggle('active', el.dataset.lang === lang);
    });
  }

  function updateNavLabels() {
    var lang = currentLang();
    var labels = lang === 'zh' ? LABELS_ZH : LABELS_EN;
    document.querySelectorAll('[data-nav-key]').forEach(function (el) {
      var key = el.getAttribute('data-nav-key');
      if (labels[key]) { el.textContent = labels[key]; }
    });
  }

  /* ---- Mobile Menu ---- */

  function openMobile() {
    document.getElementById('df-nav-overlay').classList.add('open');
    document.getElementById('df-nav-mobile').classList.add('open');
    document.body.style.overflow = 'hidden';
  }

  function closeMobile() {
    document.getElementById('df-nav-overlay').classList.remove('open');
    document.getElementById('df-nav-mobile').classList.remove('open');
    document.body.style.overflow = '';
  }

  /* ---- Build DOM ---- */

  function buildNav() {
    var activeId = currentPageId();
    var lang = currentLang();
    var labels = lang === 'zh' ? LABELS_ZH : LABELS_EN;

    var linksHTML = NAV_LINKS.map(function (l) {
      var cls = l.key === activeId ? ' class="active"' : '';
      var label = labels[l.key] || l.key;
      var target = l.href.startsWith('http') ? ' target="_blank" rel="noopener"' : '';
      return '<li><a href="' + l.href + '"' + cls + target +
             ' data-nav-key="' + l.key + '">' + label + '</a></li>';
    }).join('');

    var mobileLinksHTML = NAV_LINKS.map(function (l) {
      var cls = l.key === activeId ? ' class="active"' : '';
      var label = labels[l.key] || l.key;
      var target = l.href.startsWith('http') ? ' target="_blank" rel="noopener"' : '';
      return '<li><a href="' + l.href + '"' + cls + target +
             ' data-nav-key="' + l.key + '">' + label + '</a></li>';
    }).join('');

    var themeIcon = getPreferredTheme() === 'dark' ? '☀️' : '🌙';
    var langActive = lang;

    var nav = document.createElement('nav');
    nav.className = 'site-nav';
    nav.innerHTML =
      '<div class="nav-inner">' +
        '<a class="nav-logo" href="' + (isLanding ? 'index.html' : '../index.html') + '">' +
          '<span class="logo-accent">Devola</span>Flow' +
        '</a>' +
        '<ul class="nav-links">' + linksHTML + '</ul>' +
        '<div class="nav-controls">' +
          '<button class="theme-toggle" id="df-theme-toggle" title="Toggle dark mode">' +
            themeIcon +
          '</button>' +
          '<button class="lang-btn" id="df-lang-toggle" title="Switch language">' +
            '<span class="lang-option' + (langActive === 'en' ? ' active' : '') +
            '" data-lang="en">EN</span>' +
            ' <span style="opacity:.3">|</span> ' +
            '<span class="lang-option' + (langActive === 'zh' ? ' active' : '') +
            '" data-lang="zh">ZH</span>' +
          '</button>' +
          '<button class="nav-hamburger" id="df-hamburger" aria-label="Menu">' +
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">' +
              '<line x1="3" y1="6" x2="21" y2="6"/>' +
              '<line x1="3" y1="12" x2="21" y2="12"/>' +
              '<line x1="3" y1="18" x2="21" y2="18"/>' +
            '</svg>' +
          '</button>' +
        '</div>' +
      '</div>';

    var overlay = document.createElement('div');
    overlay.className = 'nav-overlay';
    overlay.id = 'df-nav-overlay';

    var mobile = document.createElement('div');
    mobile.className = 'nav-mobile';
    mobile.id = 'df-nav-mobile';
    mobile.innerHTML =
      '<button class="mobile-close" id="df-mobile-close">&times;</button>' +
      '<ul class="mobile-links">' + mobileLinksHTML + '</ul>';

    document.body.prepend(mobile);
    document.body.prepend(overlay);
    document.body.prepend(nav);

    document.getElementById('df-theme-toggle').addEventListener('click', toggleTheme);
    document.getElementById('df-lang-toggle').addEventListener('click', toggleLang);
    document.getElementById('df-hamburger').addEventListener('click', openMobile);
    document.getElementById('df-mobile-close').addEventListener('click', closeMobile);
    overlay.addEventListener('click', closeMobile);

    applyTheme(getPreferredTheme());
  }

  /* ---- Init ---- */

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', buildNav);
  } else {
    buildNav();
  }
})();
