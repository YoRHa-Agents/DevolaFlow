#!/usr/bin/env python3
"""Generate the SI-3 report skeleton backed by the built-in harness.

Emits ``.local/research/v<version>_evaluation.md`` with one binding
source of authority: ``python -m devolaflow.harness evaluate`` over the
repository telemetry ledger. The deterministic evaluator owns the six
W-3 dimensions, weighted composite, evidence completeness, and release
verdict.

Verdict mapping is explicit:

* ``READY`` -> SI-3 ``ACCEPT``.
* ``NOT_READY`` -> SI-3 ``REJECT`` and iterate.
* ``INSUFFICIENT`` -> release ``BLOCKED``; resolve or escalate missing
  evidence. There is no external-tool or manual fallback.

Usage::

    python scripts/generate_si3_evaluation.py 16.0.0
    python scripts/generate_si3_evaluation.py 16.0.0 --pv PV-05 --cycle v16.0.0

The script writes a skeleton. The cycle lead copies machine evidence
verbatim from the generated JSON and records any closure action.
"""

from __future__ import annotations

import argparse
import re
from datetime import UTC, datetime
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
    return datetime.now(UTC).strftime("%Y-%m-%d")


def render_skeleton(version: str, *, pv: str | None = None, cycle: str | None = None) -> str:
    """Return the SI-3 evaluation skeleton for the built-in harness."""
    pv_label = pv or "PV-NN"
    cycle_label = cycle or f"v{version}"
    major_release = version.split(".")[1:] == ["0", "0"]
    release_kind = "MAJOR" if major_release else "MINOR/PATCH"
    threshold = "9.0" if major_release else "8.5"

    return f"""# {version} — SI-3 Evaluation Report

> Per W-3 / SI-3 (`.rules/workflow.mdc` + `AGENTS.md` §W-3):
> every pre-release requires the built-in harness evaluation across six
> weighted dimensions. This {release_kind} release requires composite
> ≥ {threshold}/10 with complete evidence.
> Cycle: {cycle_label} {pv_label} (`v{version}`).
> Date: {_today()}.

## Part A — Built-in Harness Evaluation (BINDING)

Run the canonical evaluator from the repository root:

```bash
python -m devolaflow.harness evaluate \\
  --ledger .local/telemetry/harness.jsonl \\
  --repo . \\
  --base HEAD~1 \\
  --threshold {threshold} \\
  --output .local/research/v{version}_harness_evaluation.json
```

The command exit code is part of the evidence: `0=READY`, `1=NOT_READY`,
`2=INSUFFICIENT` or invalid input. Do not replace an unavailable signal
with an estimate. Resolve the evidence gap or escalate before release.

### A.1 Machine Verdict

| JSON field | Verbatim value |
|---|---|
| `verdict` | TBD — `READY` / `NOT_READY` / `INSUFFICIENT` |
| `composite` | TBD / 10 |
| `threshold` | {threshold} |
| `auto_fill_rate` | TBD |
| `sampled_at` | TBD |

**SI-3 disposition**: **TBD** — map `READY` to **ACCEPT**,
`NOT_READY` to **REJECT / iterate**, and `INSUFFICIENT` to
**BLOCKED / resolve or escalate**.

### A.2 Six-Dimension Evidence

| Dimension | Weight | Score | Weighted | Rationale |
|-----------|--------|-------|----------|-----------|
| **Code quality** | 0.20 | TBD | TBD | `code_quality` |
| **Architecture rationality** | 0.20 | TBD | TBD | `architecture_rationality` |
| **Test adequacy** | 0.20 | TBD | TBD | `test_adequacy` |
| **Maintainability** | 0.15 | TBD | TBD | `maintainability` |
| **Compatibility** | 0.10 | TBD | TBD | `compatibility` |
| **Performance impact** | 0.15 | TBD | TBD | `performance_impact` |

**Composite (weighted sum)**: **TBD / 10**

For every row, copy the matching `scores[*].metadata.subcomponents`
envelope verbatim into the rationale evidence.

**Verdict**: **TBD** (binding machine verdict from
`.local/research/v{version}_harness_evaluation.json`).

### A.3 Supporting Verification Evidence

```bash
$ make release-preflight
TBD (exit code and final summary)

$ make test-harness
TBD (exit code and pass count)
```

These commands support the machine report; they do not override its
`verdict`. Record command, exit code, and stable result digest verbatim.

### A.4 Findings Closure

| Finding | Severity | Source | Closure | Verification |
|---------|----------|--------|---------|--------------|
| TBD | TBD | TBD | TBD | TBD |

## Part B — Harness Telemetry and Trend (ADVISORY)

Copy the built-in report's `harness_summary` and compare it with the
active W-16 baseline. Trends inform the next W-1 / SI-1 planning round;
they do not replace the Part A verdict.

| Signal | Current | Baseline | Delta | Disposition |
|---|---|---|---|---|
| `tokens.budget_compliance_ratio` | TBD | TBD | TBD | TBD |
| `tokens.p95_budget_utilization` | TBD | TBD | TBD | TBD |
| `constraints.quantifiable_ratio` | TBD | TBD | TBD | TBD |
| `constraints.advisory_folded_ratio` | TBD | TBD | TBD | TBD |
| checklist completion trend | TBD | TBD | TBD | TBD |
| reversion / blocker trend | TBD | TBD | TBD | TBD |

## Cross-references

- `.local/research/v{version}_harness_evaluation.json` — binding machine evidence
- `.local/telemetry/harness.jsonl` — append-only dispatch telemetry source
- `.local/telemetry/baselines/harness_baseline_<cycle>.json` — W-16 comparison
- `workflow-system/agent/references/evaluator-rosetta.md` — 6 × 9 signal cross-walk
- `AGENTS.md` §W-3 — SI-3 ACCEPT threshold definition
- `AGENTS.md` §W-2 — built-in evaluator and no-fallback contract
- `AGENTS.md` §W-4 — harness regression guard
- DevolaFlow canonical URL: https://github.com/YoRHa-Agents/DevolaFlow
"""


def emit(
    version: str,
    *,
    pv: str | None = None,
    cycle: str | None = None,
    dry_run: bool = False,
    force: bool = False,
) -> int:
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
    parser.add_argument("version", help="version being evaluated (e.g. 16.0.0)")
    parser.add_argument("--pv", help="PV label (e.g. PV-05)", default=None)
    parser.add_argument("--cycle", help="cycle label (e.g. v16.0.0)", default=None)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="show planned write without emitting",
    )
    parser.add_argument("--force", action="store_true", help="overwrite existing file")
    args = parser.parse_args()

    if not SEMVER_RE.match(args.version):
        print(f"Error: '{args.version}' is not a valid semver (expected X.Y.Z)")
        raise SystemExit(1)

    raise SystemExit(
        emit(
            args.version,
            pv=args.pv,
            cycle=args.cycle,
            dry_run=args.dry_run,
            force=args.force,
        )
    )


if __name__ == "__main__":
    main()
