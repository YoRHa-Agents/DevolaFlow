/**
 * DevolaFlow — framework-chain page
 *
 * Wires up:
 *   1. #fc-hierarchy   : flow-down cascade on first scroll-into-view + replay,
 *                        LayerNode click → .cf-aside sheet (Esc / outside-click close).
 *   2. #fc-gate        : segmented control switches Standard (4-dim) ↔ Extended (7-dim);
 *                        "Simulate fail on benchmark" flips one badge to .is-fail and
 *                        recomputes the composite shown above the strip.
 *
 * Behaviour falls back gracefully under prefers-reduced-motion:
 *   • shared/styles.css collapses animation-duration to 0.01ms (auto-snap);
 *   • the cascade is also short-circuited explicitly so reduced-motion users
 *     see all four layers immediately even if IntersectionObserver hasn't fired.
 */
(function () {
  'use strict';

  /* ============================================================
     Reduced-motion detection
     ============================================================ */
  var prefersReducedMotion = (function () {
    if (typeof window.matchMedia !== 'function') { return false; }
    var mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    return !!mq.matches;
  })();

  /* ============================================================
     1. Hierarchy cascade + replay
     ============================================================ */

  var cascade = document.getElementById('fc-layer-cascade');
  var replayBtn = document.getElementById('fc-replay');
  var layerNodes = cascade ? cascade.querySelectorAll('.layer-node') : [];

  function clearCascadeClass() {
    layerNodes.forEach(function (node) {
      node.classList.remove('flow-cascade');
      node.style.animationDelay = '';
    });
  }

  function playCascade() {
    if (!layerNodes.length) { return; }
    clearCascadeClass();
    /* Force reflow so re-adding the class restarts the animation. */
    void cascade.offsetWidth;
    layerNodes.forEach(function (node, idx) {
      node.style.animationDelay = (idx * 0.15) + 's';
      node.classList.add('flow-cascade');
    });
  }

  function snapCascadeVisible() {
    layerNodes.forEach(function (node) {
      node.style.opacity = '1';
      node.style.transform = 'none';
      node.style.animation = 'none';
    });
  }

  if (cascade && layerNodes.length) {
    if (prefersReducedMotion) {
      snapCascadeVisible();
    } else if ('IntersectionObserver' in window) {
      var hasPlayed = false;
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting && !hasPlayed) {
            hasPlayed = true;
            playCascade();
          }
        });
      }, { threshold: 0.15 });
      io.observe(cascade);
    } else {
      /* No IO support — play once on load. */
      playCascade();
    }

    if (replayBtn) {
      replayBtn.addEventListener('click', function () {
        if (prefersReducedMotion) {
          /* Replay is a visual flourish; in reduced-motion mode just keep
             nodes visible — no animation cycle. */
          snapCascadeVisible();
          return;
        }
        playCascade();
      });
    }
  }

  /* ============================================================
     2. LayerNode click → .cf-aside sheet
     ============================================================ */

  var aside = document.getElementById('fc-aside');
  var asideTitle = document.getElementById('fc-aside-title');
  var asideDeleg = document.getElementById('fc-aside-deleg');
  var asideMustNot = document.getElementById('fc-aside-mustnot');
  var asideClose = document.getElementById('fc-aside-close');

  function openAside(node) {
    if (!aside || !node) { return; }
    var layer = node.dataset.layer || '';
    var name = node.dataset.name || '';
    var budget = node.dataset.budget || '';
    var deleg = node.dataset.delegates || '';
    var mustNotRaw = node.dataset.mustnot || '';
    var items = mustNotRaw.split('|').map(function (s) { return s.trim(); }).filter(Boolean);

    asideTitle.textContent = (layer + ' ' + name + ' — ' + budget).trim();

    if (asideDeleg) {
      asideDeleg.textContent = '→ ' + deleg;
    }

    asideMustNot.innerHTML = '';
    items.forEach(function (item) {
      var li = document.createElement('li');
      li.textContent = item;
      asideMustNot.appendChild(li);
    });

    aside.hidden = false;
    aside.setAttribute('aria-hidden', 'false');

    layerNodes.forEach(function (n) {
      n.classList.toggle('is-active', n === node);
    });

    if (asideClose && typeof asideClose.focus === 'function') {
      asideClose.focus();
    }
  }

  function closeAside() {
    if (!aside) { return; }
    aside.hidden = true;
    aside.setAttribute('aria-hidden', 'true');
    layerNodes.forEach(function (n) { n.classList.remove('is-active'); });
  }

  if (aside) {
    layerNodes.forEach(function (node) {
      node.addEventListener('click', function () { openAside(node); });
      node.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ' || e.key === 'Spacebar') {
          e.preventDefault();
          openAside(node);
        }
      });
    });

    if (asideClose) {
      asideClose.addEventListener('click', closeAside);
    }

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && !aside.hidden) {
        closeAside();
      }
    });

    document.addEventListener('click', function (e) {
      if (aside.hidden) { return; }
      if (aside.contains(e.target)) { return; }
      if (e.target.closest && e.target.closest('.layer-node')) { return; }
      closeAside();
    });
  }

  /* ============================================================
     3. Gate strip (Standard 4-dim ↔ Extended 7-dim) + simulate-fail
     ============================================================ */

  var STANDARD_BADGES = [
    { dim: 'test_quality', weight: 0.30 },
    { dim: 'code_review',  weight: 0.30 },
    { dim: 'architecture', weight: 0.20 },
    { dim: 'benchmark',    weight: 0.20 }
  ];

  var EXTENDED_BADGES = [
    { dim: 'test_quality',            weight: 0.20 },
    { dim: 'code_review',             weight: 0.20 },
    { dim: 'architecture',            weight: 0.15 },
    { dim: 'benchmark',               weight: 0.15 },
    { dim: 'visual_fidelity',         weight: 0.10 },
    { dim: 'interaction_quality',     weight: 0.10 },
    { dim: 'acceptance_verification', weight: 0.10 }
  ];

  var COMPOSITE_THRESHOLD = 85; /* default per SKILL.md gate profile = standard */
  var BASE_SCORE = 100;
  var FAIL_SCORE = 0;

  var stripEl = document.getElementById('fc-gate-strip');
  var compositeValueEl = document.getElementById('fc-composite-value');
  var compositeStateEl = document.getElementById('fc-composite-state');
  var compositeThresholdEl = document.getElementById('fc-composite-threshold');
  var failToggle = document.getElementById('fc-simulate-fail');
  var segBtns = document.querySelectorAll('.seg-btn');

  var gateMode = 'standard';
  var simulateFail = false;

  function buildBadge(dim, weight, failing) {
    var span = document.createElement('span');
    span.className = 'gate-badge ' + (failing ? 'is-fail' : 'is-pass');
    span.dataset.dim = dim;
    span.dataset.weight = String(weight);

    var dimEl = document.createElement('span');
    dimEl.className = 'gate-dim';
    dimEl.textContent = dim;

    var weightEl = document.createElement('span');
    weightEl.className = 'gate-weight';
    weightEl.textContent = '\u00d7' + weight.toFixed(2); /* × */

    var thresholdEl = document.createElement('span');
    thresholdEl.className = 'gate-threshold';
    thresholdEl.textContent = '\u2265' + COMPOSITE_THRESHOLD; /* ≥ */

    span.appendChild(dimEl);
    span.appendChild(weightEl);
    span.appendChild(thresholdEl);
    return span;
  }

  function renderStrip() {
    if (!stripEl) { return; }
    var badges = (gateMode === 'extended') ? EXTENDED_BADGES : STANDARD_BADGES;
    stripEl.innerHTML = '';

    var composite = 0;
    badges.forEach(function (b) {
      var failing = simulateFail && b.dim === 'benchmark';
      var score = failing ? FAIL_SCORE : BASE_SCORE;
      composite += score * b.weight;
      stripEl.appendChild(buildBadge(b.dim, b.weight, failing));
    });

    if (compositeValueEl) {
      compositeValueEl.textContent = composite.toFixed(0);
    }
    if (compositeStateEl) {
      var pass = composite >= COMPOSITE_THRESHOLD;
      compositeStateEl.textContent = pass ? 'PASS' : 'FAIL';
      compositeStateEl.classList.toggle('is-pass', pass);
      compositeStateEl.classList.toggle('is-fail', !pass);
    }
    if (compositeThresholdEl) {
      compositeThresholdEl.textContent = '/ \u2265' + COMPOSITE_THRESHOLD;
    }
  }

  segBtns.forEach(function (btn) {
    btn.addEventListener('click', function () {
      var mode = btn.dataset.mode;
      if (!mode || mode === gateMode) { return; }
      gateMode = mode;
      segBtns.forEach(function (b) {
        b.classList.toggle('is-active', b === btn);
        b.setAttribute('aria-pressed', b === btn ? 'true' : 'false');
      });
      renderStrip();
    });
  });

  if (failToggle) {
    failToggle.addEventListener('change', function () {
      simulateFail = !!failToggle.checked;
      renderStrip();
    });
  }

  /* Initial paint */
  renderStrip();
})();
