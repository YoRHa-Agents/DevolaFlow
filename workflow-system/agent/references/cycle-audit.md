---
id: "agent/references/cycle-audit"
version: "24.3.0"
purpose: >
  Define the read-only per-cycle audit sweep W-7 requires before a
  retrospective is authored: what it covers, what it may not do, and the two
  artifacts it must leave behind.
triggers:
  - "cycle audit"
  - "audit sweep"
  - "closing a cycle"
  - "before the retrospective"
tier: 2
token_estimate: 1200
dependencies:
  - "agent/SKILL.md"
  - "agent/references/risk-parking.md"
  - "agent/references/retro-digest.md"
last_updated: "2026-09-01"
---

# Cycle Audit

## Purpose

A read-only sweep of the surfaces this repository builds for itself, run once
per MAJOR or MINOR cycle before the retrospective is written. It produces
parked risks, not commits: nothing it finds is fixed in the same pass.

The sweep exists because of its own record. The v24.2.0 audit was a single
read-only pass over the parking and compaction surfaces and it returned a
blocker (`apply_plan` moving a file before recording it) plus a critical
(`write_digest` withholding the ledger table over a prose complaint). Both had
survived a MAJOR and a MINOR with every gate green, because both were states no
test had reached and no gate was shaped to ask about. One pass, two findings
neither the six gates nor the harness would have surfaced: that ratio is the
argument for running it every cycle rather than after a MAJOR.

## When to Load

Load this reference when closing a cycle — after implementation is complete and
before the W-7 retrospective is authored.

## Body

### 1. What the sweep is, and is not

**It is** an agent reading its own recently shipped surfaces as a hostile user
would: following each documented promise to the code that must keep it, and
each piece of state to the code that writes and reads it.

**It is not** a test run. The six SI-10 gates answer "does the code do what the
tests say". The sweep answers a question tests structurally cannot: "is there a
state the tests never reach, and is the code honest when it gets there". A gate
can only fail on a case someone thought of. The sweep is where new cases come
from.

**It is not a fixing pass.** Findings are parked through `devola-parking`, with
severity, and triaged into a cycle by the usual planning route. Fixing while
auditing costs the sweep its coverage: attention spent on a fix is attention
not spent on the next surface, and a half-audited surface reads as a clean one
in the next cycle.

### 2. Canonical surfaces

Each cycle's sweep covers everything that cycle shipped, plus these standing
surfaces:

| Surface | The question to ask |
|---|---|
| `.local/tasks/*/parking/` | Does every risk's recorded state match what the ledger says happened to it? Does any live risk have no owner cycle? |
| `.local/telemetry/` + `src/devolaflow/harness/` | Does a recorded event mean what its field names claim? Does an aggregate hide a row it could not parse? |
| Vocabulary sets (enums, `Final[str]` constants) | `python -c "from devolaflow.enum_writers import find_unwritten_vocabulary as f; print(f('.'))"` — a declared value nothing writes is a promise nothing keeps |
| Generated artifacts (`DIGEST.md`, `INDEX.md`, mapping ledgers) | If generation is skipped or fails, does a reader see the absence, or a stale file that looks current? |
| CLI contracts | Does every documented output shape hold on the failure paths too, or only the success path? |

The recurring shape across all five is the same: **a result that is honest when
things go well and silent when they do not.** Search for the silence.

### 3. Worked examples

**Two fields doing one job.** v24.2.0's `refused` count was derived from a
`findings` list that accumulated results from two unrelated phases — the moves,
and the digest rendered after them. A digest complaint therefore reported as a
refused move. The audit found it by asking what each reported number is
computed from, rather than whether it was correct in the tested case.

**Record-after-act.** `apply_plan` moved a file and then appended its mapping
row. The audit found it by reading the apply loop for the order of its two
side effects and asking what a crash between them leaves behind. No test
crashes between two statements; only a reader notices the window.

**Declared and unwritten.** `bypassed` was a compaction telemetry outcome:
declared, collected into the validating frozenset, documented, tested, and
produced by nothing. Found by asking, for one value, who writes it. That
question is now `src/devolaflow/enum_writers.py` and runs in CI — an audit
finding that graduated into a gate, which is the intended lifecycle for
anything the sweep finds twice.

### 4. Output

Two artifacts, both required:

1. **Parked risks** — one per finding, via `devola-parking open`, with a
   severity and the evidence path. A finding not parked did not happen.
2. **A line in the retrospective** — the surfaces covered and the finding count,
   including zero. A sweep that found nothing is evidence about the sweep as
   much as about the code, and a cycle with no such line cannot be told apart
   from a cycle that skipped it.

Severity governs urgency, not the audit: a blocker may still be deferred to the
next cycle with a stated reason (v24.2.0 deferred `RISK-001` because a
durability change did not belong inside an unrelated MINOR). What may not
happen is a finding that is neither parked nor reported.

## Cross-References

- `references/risk-parking.md` — how findings are parked, and what an archived
  risk's state means
- `references/retro-digest.md` — how retrospectives become extractable lessons
- `references/meta-framework.md` — workflow primitives

## History

- Scaffolded by `scripts/scaffold_reference.py` (D-X-2).
- v24.3.0: authored, following the v24.2.0 retrospective's telegraphed item.
  Cited by W-7; no new numbered rule was added.
