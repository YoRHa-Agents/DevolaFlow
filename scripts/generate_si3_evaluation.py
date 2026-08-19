#!/usr/bin/env python3
"""v8.5.0 PV-05 (M-04 / C-04 closure) — generate SI-3 evaluation report skeleton.

Emits a per-PV SI-3 evaluation report into ``.local/research/<version>_evaluation.md``
with the **C-04 split** that separates the binding **Quality Gate** block
(EvoBench-anchored, the W-3 / SI-3 ACCEPT verdict) from the advisory
**Research Snapshot** block (NineS-anchored, informational only).

Why split: the v8.4.x cycles surfaced a subtle conflation in the
single-block format where NineS hygiene metrics (e.g. ``code_coverage:
0.0`` from the upstream timeout artifact) leaked into the binding
ACCEPT/REJECT verdict. The C-04 split makes the source-of-authority
explicit:

* **Quality Gate (binding)** — uses the W-3 / SI-3 6-dimension formula
  (Code quality 0.20 + Architecture 0.20 + Tests 0.20 + Maintainability
  0.15 + Compatibility 0.10 + Performance 0.15) anchored on the
  EvoBench composite + the W-9 / SI-10 6-step verification harness.
  Composite ≥ 8.5/10 → ACCEPT; below threshold → iterate or escalate.
* **Research Snapshot (advisory)** — surfaces the latest NineS
  self-eval metrics (capability_mean, hygiene_mean, per-metric
  breakdown). NineS measurement timeouts / index staleness do NOT
  block the gate — they are informational inputs to the W-1 / SI-1
  planning gate of the NEXT cycle.

Usage::

    python scripts/generate_si3_evaluation.py 8.5.0
    python scripts/generate_si3_evaluation.py 8.5.0 --pv PV-05 --cycle v9.0.0

The script writes a SKELETON — the L0 cycle-lead fills in the per-
dimension scores + rationale before committing the file. The skeleton
ensures every report has the C-04 split structure.
"""

from __future__ import annotations

import argparse
import re
from datetime import datetime, timezone
from pathlib import Path

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


def _find_root() -> Path:
    p = Path(__file__).resolve().parent
    while p != p.parent:
        if (p / "pyproject.toml").exists():
            return p
        p = p.parent
    return Path.cwd()


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def render_skeleton(version: str, *, pv: str | None = None, cycle: str | None = None) -> str:
    """Return the SI-3 evaluation report skeleton with C-04 split."""
    pv_label = pv or "PV-NN"
    cycle_label = cycle or "v9.0.0"

    return f"""# {version} — SI-3 Evaluation Report

> Per W-3 / SI-3 (`.rules/workflow.mdc` + `AGENTS.md` §W-3):
> every pre-release requires a weighted-composite evaluation across 6
> dimensions; threshold for ACCEPT is composite ≥ 8.5/10 (MINOR/PATCH)
> or ≥ 9.0/10 (MAJOR). Below threshold → iterate (loop back to SI-1)
> or escalate to human.
> Cycle: {cycle_label} {pv_label} (PATCH/MINOR `v{version}`).
> Date: {_today()}.

## Part A — Quality Gate (EvoBench-anchored, BINDING)

> **C-04 split** (v8.5.0 PV-05 codification): Part A is the binding
> ACCEPT/REJECT verdict. It uses ONLY EvoBench-anchored metrics + the
> W-9 / SI-10 6-step CI harness. NineS measurements are advisory and
> live in Part B. NineS measurement timeouts / index staleness MUST
> NOT block the Part A verdict.

### A.1 Composite Score (Weighted)

| Dimension | Weight | Score | Weighted | Rationale |
|-----------|--------|-------|----------|-----------|
| **Code quality**            | 0.20 | TBD | TBD | TBD — ruff lint/format, complexity, error handling, S-5 compliance |
| **Architecture rationality**| 0.20 | TBD | TBD | TBD — separation of concerns, layering, P1-P5 invariants, ADR coverage |
| **Test adequacy**           | 0.20 | TBD | TBD | TBD — coverage ≥ 80%, edge cases, regression tests, R5 byte-identical |
| **Maintainability**         | 0.15 | TBD | TBD | TBD — readability, documentation, naming, S-2 / SF-5 path discipline |
| **Compatibility**           | 0.10 | TBD | TBD | TBD — schema versions, P6 cache layout, multi-baseline byte tests |
| **Performance impact**      | 0.15 | TBD | TBD | TBD — EvoBench composite no >5% regression, latency budgets |

**Composite (weighted sum)**: **TBD / 10**

**Verdict**: **ACCEPT / REJECT** (≥ 8.5 threshold per SI-3 + W-3 — adjust to 9.0 for MAJOR).

### A.2 W-9 / SI-10 6-step CI verification harness

```bash
$ python -m pytest tests/ -q
TBD passed, TBD skipped in TBDs

$ ruff check src/ tests/
TBD

$ ruff format --check src/ tests/
TBD

$ python -m pytest tests/test_version.py -v
TBD passed in TBDs

$ python -m pytest tests/test_benchmarks.py -v
TBD passed in TBDs

$ make check-cursor-skill
TBD (exit 0)
```

### A.3 Findings closure summary

| Finding | Severity | Source | Closure | Verification |
|---------|----------|--------|---------|--------------|
| TBD | TBD | TBD | TBD | TBD |

## Part B — Research Snapshot (NineS-anchored, ADVISORY)

> **C-04 split**: Part B is informational. NineS provides a
> capability/hygiene measurement series across cycles; the snapshot
> here is the input to the NEXT cycle's W-1 / SI-1 planning gate.
> Below-threshold NineS metrics (e.g. `code_coverage: 0.0` from
> upstream timeout) DO NOT block the Part A verdict — they feed the
> A1..A4 hygiene closure plan tracked separately.

### B.1 NineS self-eval headline

| Metric | Value | Trend vs prior cycle |
|---|---|---|
| **overall composite** | TBD | TBD |
| capability_mean | TBD | TBD |
| hygiene_mean | TBD | TBD |
| group_means.capability | TBD | TBD |
| group_means.hygiene | TBD | TBD |
| weighted_overall | TBD | TBD |

### B.2 Capability sub-scores

| Metric | Value | Notes |
|---|---|---|
| scoring_accuracy | TBD | TBD |
| eval_coverage | TBD | TBD |
| scoring_reliability | TBD | TBD |
| report_quality | TBD | TBD |
| scorer_agreement | TBD | TBD |
| source_coverage | TBD | TBD |
| source_freshness | TBD | TBD |
| change_detection | TBD | TBD |
| data_completeness | TBD | TBD |
| collection_throughput | TBD | TBD |
| decomposition_coverage | TBD | TBD |
| abstraction_quality | TBD | TBD |
| code_review_accuracy | TBD | TBD |
| index_recall | TBD | TBD (A3 closure target ≥ 0.85 post-PV-05) |
| structure_recognition | TBD | TBD |
| pipeline_latency | TBD | TBD |
| sandbox_isolation | TBD | TBD |
| convergence_rate | TBD | TBD |
| cross_vertex_synergy | TBD | TBD |
| agent_analysis_quality | TBD | TBD |

### B.3 Hygiene sub-scores

| Metric | Value | Notes |
|---|---|---|
| code_coverage | TBD | TBD (A1 closure target > 0 post-PV-05 cov-timeout bump) |
| test_count | TBD | TBD (W-17 cap: ≤ +30 per PV; ≤ +150 per cycle) |
| module_count | TBD | TBD |
| docstring_coverage | TBD | TBD |
| lint_cleanliness | TBD | TBD |

### B.4 Hygiene closure status (A1-A4)

| Closure | Target | Current | Status |
|---|---|---|---|
| **A1** code_coverage > 0 | upstream NineS bump 60→180s budget | TBD | TBD |
| **A2** agent_overhead ≤ 40000 tokens | tests/test_agent_context_overhead.py | TBD | TBD |
| **A3** index_recall > 0.85 | make nines-index-rebuild | TBD | TBD |
| **A4** capability_mean ≥ 0.95 byte-stable | golden_test_set refresh | TBD | TBD |

## Cross-references

- `.local/research/{version}_nines.json` — raw NineS output (Part B source)
- `.local/research/{version}_nines.md` — NineS summary (Part B source)
- `.local/research/v9.0.0_implementation_plan.md` §<PV section> — runbook
- `docs/cycle-archive/adr/v9-ADR-005-nines-hygiene-and-w-rules.md` — C-04 split ADR
- `AGENTS.md` §W-3 — SI-3 ACCEPT threshold definition
- `AGENTS.md` §W-9 — SI-10 6-step verification harness
- DevolaFlow canonical URL: https://github.com/YoRHa-Agents/DevolaFlow
- NineS canonical URL: https://github.com/YoRHa-Agents/NineS
"""


def emit(version: str, *, pv: str | None = None, cycle: str | None = None,
         dry_run: bool = False, force: bool = False) -> int:
    root = _find_root()
    target = root / ".local" / "research" / f"v{version}_evaluation.md"

    if target.exists() and not force:
        print(f"  EXISTS  {target.relative_to(root)} — pass --force to overwrite")
        return 0

    content = render_skeleton(version, pv=pv, cycle=cycle)

    if dry_run:
        print(f"  WOULD   {target.relative_to(root)} ({len(content)} chars)")
        return 0

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    print(f"  WROTE   {target.relative_to(root)} ({len(content)} chars)")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("version", help="version being evaluated (e.g. 8.5.0)")
    parser.add_argument("--pv", help="PV label (e.g. PV-05)", default=None)
    parser.add_argument("--cycle", help="cycle label (e.g. v9.0.0)", default=None)
    parser.add_argument("--dry-run", action="store_true", help="show planned write without emitting")
    parser.add_argument("--force", action="store_true", help="overwrite existing file")
    args = parser.parse_args()

    if not SEMVER_RE.match(args.version):
        print(f"Error: '{args.version}' is not a valid semver (expected X.Y.Z)")
        raise SystemExit(1)

    raise SystemExit(emit(args.version, pv=args.pv, cycle=args.cycle,
                          dry_run=args.dry_run, force=args.force))


if __name__ == "__main__":
    main()
