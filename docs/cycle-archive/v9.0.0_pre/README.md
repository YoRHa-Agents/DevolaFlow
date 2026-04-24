# Cycle Archive — v9.0.0 (in-flight; pre-final-tag placeholder)

> Placeholder created in v8.5.0 PV-05 per Workflow Rule W-19. The
> v9.0.0 cycle is **in-flight** as of this directory's creation; the
> final archive will be written by `scripts/archive_research_artifacts.py 9.0.0`
> after the v9.0.0 release tag is pushed.

## Purpose

`docs/cycle-archive/v9.0.0_pre/` exists so the W-19 archive directory
has a tracked entry IN the repository BEFORE the v9.0.0 cycle closes.
Without this placeholder, fresh clones / external reviewers would not
know that:

1. The W-19 archive mechanism is active for the v9.0.0 cycle.
2. The final archive will live in `docs/cycle-archive/v9.0.0/` once
   the cycle ships.
3. The archive script is `scripts/archive_research_artifacts.py`.

## Cycle status (as of v8.5.0 cut, PV-05)

| PV | Tag | Theme | Status |
|----|-----|-------|--------|
| PV-01 | v8.4.1 | Skill headroom reclamation | shipped |
| PV-02 | v8.4.2 | Reference cascade + cache governance v2 | shipped |
| PV-03 | v8.4.3 | A-5 SSOT registry pattern | shipped |
| PV-04 | v8.4.4 | Lifecycle wiring + Soul Rule S-10 | shipped |
| PV-05 | **v8.5.0** | NineS hygiene A1-A4 + W-16..W-20 + env-flags ref | **shipping (this PV)** |
| PV-06 | v8.5.1 | CompressionPipeline + B3 5-primitive flip | planned |
| ...   | v8.5.X / v9.0.0 | per `.local/research/v9.0.0_implementation_plan.md` | planned |

## Final archive (when v9.0.0 ships)

```bash
python scripts/archive_research_artifacts.py 9.0.0
git add docs/cycle-archive/v9.0.0/
git commit -m "chore(v9.0.0): archive cycle research artifacts per W-19"
```

The final archive supersedes this placeholder; the placeholder is
removed in the same release commit.

## Cross-references

* `AGENTS.md` §W-19 — Research Artifact Archive at Cycle End
* `.local/research/v9.0.0_implementation_plan.md` — runbook
* `scripts/archive_research_artifacts.py` — archive mechanism
