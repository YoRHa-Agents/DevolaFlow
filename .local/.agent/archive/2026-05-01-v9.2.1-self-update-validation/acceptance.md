# Acceptance Criteria — v9.2.1-self-update-validation

Source: v9.2.0 cycle plan §PV-07.

## AC (verbatim)

- [ ] AC1 — All 7 `self-update` stages complete with PASS verdict
- [ ] AC2 — 4-fixture E2E test PASSES across all 4 fixture shapes
  (empty / `.local/`-only / `.rules/`-only / full-stack)
- [ ] AC3 — Cycle-close NineS composite ≥ 0.85
- [ ] AC4 — SI-3 weighted composite ≥ 8.5 (PATCH floor matches MINOR floor)
- [ ] AC5 — PV-07 itself opened + archived
  `.local/.agent/active/v9.2.1-self-update-validation/`
  (recursive-engagement proof)
- [ ] AC6 — Validation report cross-references every
  G-005 / G-006 / G-015 / M-004 / M-007 / agents_md_slice closure
  with explicit before/after metric
- [ ] AC7 — Zero new code paths introduced (PATCH discipline)
- [ ] AC8 — W-9 6/6 PASS; W-2 NineS PASS

## Cycle-level ACs (plan §"Cycle-level acceptance criteria" 1–12)

- [ ] #1 — 4 new discovery symbols in production (`scan_workspace`,
  `consult_for_dispatch`, `seed_initial_spec`, `auto_write_handoff`)
- [ ] #2 — `write_envelope(` callers ≥ 2 in `src/devolaflow/`
  (closes G-005; was 1 at v9.1.0)
- [ ] #10 — NineS cycle composite ≥ 0.85 at `--baseline-version 9.2.0`
- [ ] #11 — self-update workflow PASSES all 7 stages with the
  recursive-engagement proof (this change folder)
- [ ] #12 — Multi-adapter regen PASSES (4 core + 5 tier-2 within budget)
