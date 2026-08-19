# v15-ADR-004 — Rule-Cap Denominator + v15.0.0 Rule-Diet Scope

* **Status**: PROPOSED (L0/human ratifies — amends ADR-007 D5)
* **Date**: 2026-06-12
* **Cycle**: v14.2.0 T5 (SI-1 planning gate for the v14.2.x → v15.0.0 ladder)
* **Feeds**: F-R2 (major), F-R5 (major), F-R14 (minor) per
  `.local/research/v15-cycle_design_review_repo.md` §1/§2/§7-D1; gaps G-009, G-010
* **3-condition gate** (verbatim from the repo review §7): "Hard to reverse: the cap number is
  cited in ADR-007 D5, test code, and index.md — re-pinning it rewrites governance history every
  later cycle builds on. Surprising without context: '63 rules under a 60 HARD cap, test green'
  is incomprehensible without the AGENTS.md-only denominator story. Real trade-off: full-corpus
  cap (honest, forces Style diet) vs compiled-target cap (status quo, but Style becomes
  ungoverned)." → **qualifies**.

## Context

Measured state: `.rules/soul.mdc` 10 / `architecture.mdc` 7 / `conventions.mdc` 9 /
`workflow.mdc` 24 / `style.mdc` 13 = **63 total**. `.rules/index.md` line 5: "Total rules:
**63** … cap 60 HARD per ADR-007 D5". The enforcement test counts a different denominator —
`tests/test_no_ghost_features.py:1220`: "test_rule_count_under_cap — total compiled-AGENTS.md
rule count ≤ 60 (HARD per ADR-007 D5). Rule count = sum of `^## ([SACW]|ST)-\d+` headings in
AGENTS.md", with `_RULE_COUNT_CAP_HARD: int = 60`. AGENTS.md carries 50 S/A/C/W headings and
zero ST headings (Style compiles only to the cursor target), so the test passes at 50/60 while
the documented corpus is 63 — the regex includes `ST` for a surface where ST never appears.

Coupled growth problem (F-R5): `workflow.mdc` holds 24 of the 50 compiled rules, +1 W-rule per
minor cycle since v8.5.0, and recent rule bodies embed full design rationale ("Source: v11.4.0
SI-1 gap analysis §4 + §5 + §7 + §8 risk register"). At the observed rate the 5-version ladder
adds ~3–5 more W-rules, re-saturating the 14000 compile budget and the cap mid-cycle. F-R14:
A-5's enumerated registry table is frozen at "v8.4.3 baseline" while the live test enforces the
invariant generically. Healthy counter-model (F-R8): the Soul freeze — "few rules, hard
enforcement, zero narrative payload".

## Decision (recommended)

1. **Denominator = full compiled corpus, all layers including Style**: the canonical count is
   the sum of rule headings across `.rules/*.mdc` sources (today **63**). The cap governs the
   corpus, not one distribution target.
2. **Cap stays 60 HARD** — do NOT raise it. The corpus is over-cap at 63; the deficit is the
   forcing function for the v15.0.0 rule-diet rather than a number that drifts upward on demand
   (the compile-budget history 8000 → 12000 → 14000 is the anti-pattern to break).
3. **Rule-diet scope (v15.0.0)**, target ≤ 55 post-diet (≥ 5 slots headroom):
   * Strip `Source:` / history / per-cycle narrative blocks from ALL rule bodies into
     `docs/cycle-archive/` + ADRs — a rule becomes "normative statement + enforcement pointer".
   * Fold W-10..W-15 (pure CP-*/CO-* mirrors) into their C-* duplicates.
   * Drop the A-5 version-stamped registry table (the AST test is the live inventory); keep
     A-5.1 normative text.
   * C-8 deletion already lands v14.2.x (G-012) — counts toward the 63 → ≤ 60 path early.
4. **Test re-pin (after diet, v14.5.0–v15.0.0)**: `test_rule_count_under_cap` counts the
   `.rules/` source corpus (all 5 layers); the `ST` regex branch finally matches something.
   Interim (pre-diet): the test keeps the AGENTS.md denominator but gains a comment + companion
   informational assertion that prints the full-corpus count, so the 63-vs-60 state is visible,
   not silent.
5. **W-set telegraph (consider, not bind)**: adopt an analogous-to-W-21 telegraph discipline for
   NEW W-rules (repo review F-R8 recommendation) — evaluate inside the v15.0.0 diet PR.

## Consequences

### Positive
* One unambiguous governance number; operators and tests quote the same denominator.
* The diet directly serves the north star: per the repo review §8, always-applied rule text is
  the single largest per-dispatch context waste; stripping narrative shrinks every session.
* Style layer comes under governance instead of silently escaping the cap.

### Negative
* The corpus is formally in violation (63 > 60) from ratification until the diet lands — must
  be tracked as a visible, time-boxed exception (release-note + the informational assertion),
  not a green test.
* Folding W-10..W-15 renumbers/retires W-identifiers cited across docs and retros — needs a
  redirect table in the diet PR (same class of churn as v9.0.0 PV-07 rebalancing, which has
  precedent tooling).

### Neutral
* Soul layer untouched (W-21 freeze 10/12 preserved); cap-12 Soul sub-cap unaffected.

## Alternatives considered

* **A1 — Cap = AGENTS.md-only (status quo, document it)**: makes the test honest by fiat but
  leaves 13 Style rules ungoverned and index.md misleading; the cap stops constraining exactly
  the layer (Style/WX) that historically grew via showcase mandates. Rejected.
* **A2 — Raise cap to 70**: removes the violation without work; repeats the compile-budget
  bump-on-saturation anti-pattern (F-R4 history) and removes the diet's forcing function.
  Rejected.
* **A3 — Per-layer caps (the deferred "A-* per-layer 14-cap" backlog item)**: finer-grained but
  multiplies governance numbers (5 caps to quote/maintain); can be layered later if one layer
  re-bloats post-diet. Deferred, not rejected — re-evaluate at v15.0.0 SI-3.
