/**
 * DevolaFlow — shared/nav.js
 * Injects a consistent navigation bar, theme toggle, and language switcher
 * into every demo page. Auto-detects landing vs sub-page for relative paths.
 */
(function () {
  'use strict';

  var THEME_KEY = 'devolaflow-theme';
  var LANG_KEY = 'devolaflow-lang';

  // Compatibility route registry. Keep this independent from primary navigation:
  // every deployed directory must remain detectable even when it is not a nav item.
  var SUBPAGE_DIRS = [
    'design-system', 'framework-chain', 'context-flow',
    'version-timeline', 'design-architecture',
    'workflow-visualizer', 'stage-explorer',
    'benchmark-results', 'blog'
  ];

  // Detect landing by ABSENCE of any known sub-page dir in the URL path.
  // GitHub Pages deploys at '/DevolaFlow/' (not '/demo/'), so the prior
  // '/demo/'-only check resolved to false on the deployed landing page.
  var isLanding = (function () {
    var path = window.location.pathname;
    return !SUBPAGE_DIRS.some(function (d) {
      return path.indexOf('/' + d + '/') !== -1 ||
             path.endsWith('/' + d);
    });
  })();

  function rootPrefix() {
    var parts = window.location.pathname.split('/').filter(function (part) {
      return part.length > 0;
    });
    var routeIndex = parts.findIndex(function (part) {
      return SUBPAGE_DIRS.indexOf(part) !== -1;
    });
    if (routeIndex === -1) { return ''; }
    var routeParts = parts.slice(routeIndex);
    if (routeParts.length && /\.[a-z0-9]+$/i.test(routeParts[routeParts.length - 1])) {
      routeParts.pop();
    }
    return routeParts.map(function () { return '../'; }).join('');
  }

  var ROOT_PREFIX = rootPrefix();

  function prefix(subPath) {
    return ROOT_PREFIX + subPath;
  }

  // The public information architecture has exactly five destinations.
  var NAV_LINKS = [
    { key: 'nav.home',     href: prefix('index.html'), fallback: 'Home' },
    { key: 'nav.system',   href: prefix('framework-chain/index.html'), fallback: 'System' },
    { key: 'nav.io',       href: prefix('context-flow/index.html'), fallback: 'I/O' },
    { key: 'nav.harness',  href: prefix('benchmark-results/index.html'), fallback: 'Harness' },
    { key: 'nav.timeline', href: prefix('version-timeline/index.html'), fallback: 'Timeline' }
  ];

  function translated(key, fallback) {
    if (typeof window.t !== 'function') { return fallback; }
    var value = window.t(key);
    return value === key ? fallback : value;
  }

  function navLabel(link) {
    return translated(link.key, link.fallback);
  }

  function currentPageId() {
    var path = window.location.pathname;
    if (/framework-chain|design-system|design-architecture|workflow-visualizer/.test(path)) {
      return 'nav.system';
    }
    if (/context-flow|stage-explorer/.test(path)) { return 'nav.io'; }
    if (/benchmark-results/.test(path)) { return 'nav.harness'; }
    if (/version-timeline/.test(path)) { return 'nav.timeline'; }
    if (isLanding || /\/blog(\/|$)/.test(path)) { return 'nav.home'; }
    return '';
  }

  /* ---- Theme ---- */

  function readPreference(key) {
    try {
      return window.localStorage.getItem(key);
    } catch (error) {
      console.warn('DevolaFlow navigation could not read localStorage.', error);
      return null;
    }
  }

  function writePreference(key, value) {
    try {
      window.localStorage.setItem(key, value);
    } catch (error) {
      console.warn('DevolaFlow navigation could not write localStorage.', error);
    }
  }

  function getPreferredTheme() {
    var stored = readPreference(THEME_KEY);
    if (stored === 'dark' || stored === 'light') { return stored; }
    return window.matchMedia &&
      window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }

  function applyTheme(theme) {
    document.documentElement.classList.toggle('dark', theme === 'dark');
    document.documentElement.style.colorScheme = theme;
    writePreference(THEME_KEY, theme);
    var btn = document.getElementById('df-theme-toggle');
    if (btn) {
      btn.textContent = themeIcon(theme);
      btn.setAttribute('aria-pressed', theme === 'dark' ? 'true' : 'false');
    }
  }

  function themeIcon(theme) {
    return theme === 'dark' ? '☀' : '☾';
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
      writePreference(LANG_KEY, next);
      updateNavLabels();
      updateLangButton();
    }
  }

  function updateLangButton() {
    var lang = currentLang();
    document.querySelectorAll('.lang-option').forEach(function (el) {
      el.classList.toggle('active', el.dataset.lang === lang);
    });
  }

  function updateNavLabels() {
    document.querySelectorAll('[data-nav-key]').forEach(function (el) {
      var key = el.getAttribute('data-nav-key');
      var link = NAV_LINKS.find(function (candidate) {
        return candidate.key === key;
      });
      if (link) { el.textContent = navLabel(link); }
    });
    var nav = document.querySelector('.site-nav');
    var menu = document.getElementById('df-hamburger');
    var close = document.getElementById('df-mobile-close');
    var theme = document.getElementById('df-theme-toggle');
    var language = document.getElementById('df-lang-toggle');
    var mobile = document.getElementById('df-nav-mobile');
    if (nav) {
      nav.setAttribute('aria-label', translated('control.navigation', 'Primary navigation'));
    }
    if (menu) {
      menu.setAttribute('aria-label', translated('control.menu', 'Open navigation menu'));
    }
    if (close) {
      close.setAttribute('aria-label', translated('control.close', 'Close navigation menu'));
    }
    if (theme) {
      var themeLabel = translated('theme.toggle', 'Toggle color theme');
      theme.setAttribute('aria-label', themeLabel);
      theme.title = themeLabel;
    }
    if (language) {
      var languageLabel = translated('control.language', 'Switch language');
      language.setAttribute('aria-label', languageLabel);
      language.title = languageLabel;
    }
    if (mobile) {
      mobile.setAttribute('aria-label', translated('control.navigation', 'Primary navigation'));
    }
  }

  /* ---- Mobile Menu ---- */

  var lastFocused = null;

  function openMobile() {
    var overlay = document.getElementById('df-nav-overlay');
    var mobile = document.getElementById('df-nav-mobile');
    var menu = document.getElementById('df-hamburger');
    if (!overlay || !mobile || !menu) { return; }
    lastFocused = document.activeElement;
    overlay.classList.add('open');
    overlay.setAttribute('aria-hidden', 'false');
    mobile.classList.add('open');
    mobile.setAttribute('aria-hidden', 'false');
    menu.setAttribute('aria-expanded', 'true');
    document.body.style.overflow = 'hidden';
    var close = document.getElementById('df-mobile-close');
    if (close) { close.focus(); }
  }

  function closeMobile() {
    var overlay = document.getElementById('df-nav-overlay');
    var mobile = document.getElementById('df-nav-mobile');
    var menu = document.getElementById('df-hamburger');
    if (!overlay || !mobile || !menu) { return; }
    overlay.classList.remove('open');
    overlay.setAttribute('aria-hidden', 'true');
    mobile.classList.remove('open');
    mobile.setAttribute('aria-hidden', 'true');
    menu.setAttribute('aria-expanded', 'false');
    document.body.style.overflow = '';
    if (lastFocused && typeof lastFocused.focus === 'function') {
      lastFocused.focus();
    }
  }

  function handleMenuKeydown(event) {
    var mobile = document.getElementById('df-nav-mobile');
    if (!mobile || !mobile.classList.contains('open')) { return; }
    if (event.key === 'Escape') {
      event.preventDefault();
      closeMobile();
      return;
    }
    if (event.key !== 'Tab') { return; }
    var focusable = mobile.querySelectorAll('a[href], button:not([disabled])');
    if (!focusable.length) { return; }
    var first = focusable[0];
    var last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  /* ---- Build DOM ---- */

  function buildNav() {
    var activeId = currentPageId();
    var lang = currentLang();

    var linksHTML = NAV_LINKS.map(function (l) {
      var cls = l.key === activeId ? ' class="active"' : '';
      var current = l.key === activeId ? ' aria-current="page"' : '';
      var label = navLabel(l);
      var target = l.href.startsWith('http') ? ' target="_blank" rel="noopener"' : '';
      return '<li><a href="' + l.href + '"' + cls + current + target +
             ' data-nav-key="' + l.key + '">' + label + '</a></li>';
    }).join('');

    var mobileLinksHTML = NAV_LINKS.map(function (l) {
      var cls = l.key === activeId ? ' class="active"' : '';
      var current = l.key === activeId ? ' aria-current="page"' : '';
      var label = navLabel(l);
      var target = l.href.startsWith('http') ? ' target="_blank" rel="noopener"' : '';
      return '<li><a href="' + l.href + '"' + cls + current + target +
             ' data-nav-key="' + l.key + '">' + label + '</a></li>';
    }).join('');

    var preferredTheme = getPreferredTheme();
    var langActive = lang;

    var nav = document.createElement('nav');
    nav.className = 'site-nav';
    nav.setAttribute('aria-label', translated('control.navigation', 'Primary navigation'));
    nav.innerHTML =
      '<div class="nav-inner">' +
        '<a class="nav-logo" href="' + prefix('index.html') + '">' +
          '<span class="logo-accent">Devola</span>Flow' +
        '</a>' +
        '<ul class="nav-links">' + linksHTML + '</ul>' +
        '<div class="nav-controls">' +
          '<button type="button" class="theme-toggle" id="df-theme-toggle"' +
          ' aria-pressed="false">' +
            themeIcon(preferredTheme) +
          '</button>' +
          '<button type="button" class="lang-btn" id="df-lang-toggle">' +
            '<span class="lang-option' + (langActive === 'en' ? ' active' : '') +
            '" data-lang="en">EN</span>' +
            ' <span class="lang-divider" aria-hidden="true">/</span> ' +
            '<span class="lang-option' + (langActive === 'zh' ? ' active' : '') +
            '" data-lang="zh">ZH</span>' +
          '</button>' +
          '<button type="button" class="nav-hamburger" id="df-hamburger"' +
          ' aria-expanded="false" aria-controls="df-nav-mobile">' +
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
    overlay.setAttribute('aria-hidden', 'true');

    var mobile = document.createElement('div');
    mobile.className = 'nav-mobile';
    mobile.id = 'df-nav-mobile';
    mobile.setAttribute('role', 'dialog');
    mobile.setAttribute('aria-modal', 'true');
    mobile.setAttribute('aria-hidden', 'true');
    mobile.innerHTML =
      '<button type="button" class="mobile-close" id="df-mobile-close"' +
      ' aria-label="' + translated('control.close', 'Close navigation menu') +
      '">&times;</button>' +
      '<ul class="mobile-links">' + mobileLinksHTML + '</ul>';

    document.body.prepend(mobile);
    document.body.prepend(overlay);
    document.body.prepend(nav);

    document.getElementById('df-theme-toggle').addEventListener('click', toggleTheme);
    document.getElementById('df-lang-toggle').addEventListener('click', toggleLang);
    document.getElementById('df-hamburger').addEventListener('click', openMobile);
    document.getElementById('df-mobile-close').addEventListener('click', closeMobile);
    overlay.addEventListener('click', closeMobile);
    mobile.addEventListener('keydown', handleMenuKeydown);
    mobile.querySelectorAll('a').forEach(function (link) {
      link.addEventListener('click', closeMobile);
    });
    document.addEventListener('devolaflow:languagechange', function () {
      updateNavLabels();
      updateLangButton();
    });
    window.addEventListener('resize', function () {
      if (window.innerWidth > 640 && mobile.classList.contains('open')) {
        closeMobile();
      }
    });

    applyTheme(preferredTheme);
    updateNavLabels();
  }

  /* ---- Init ---- */

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', buildNav);
  } else {
    buildNav();
  }
})();
