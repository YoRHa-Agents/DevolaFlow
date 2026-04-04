---
id: "agent/examples/hotfix-trace"
version: "1.0.0"
purpose: >
  Hotfix workflow delegation trace demonstrating how the same 4-layer
  hierarchy and message schemas handle a minimal 4-stage workflow for
  a critical unicode path bug fix.
triggers:
  - "Need a hotfix workflow example"
  - "How does hotfix delegation differ from full-pipeline"
  - "Show me a minimal workflow trace"
tier: 3
token_estimate: 3000
last_updated: "2026-04-04"
---

# Hotfix Delegation Trace

## Scenario

A user reports a critical bug: the sync engine corrupts files when the
target directory contains unicode characters in its path. The Project Agent
selects `hotfix` workflow with 4 stages: bug-triage → fix → test → release.

**Project:** `filesync` — the same Rust CLI tool from the full-pipeline example.
**Bug:** `Path::new()` doesn't handle non-UTF8 paths on Windows (SEV2).
**Workflow type:** `hotfix`
**Gate profile:** `standard`

## Full Delegation Trace

```
TIME  LAYER  AGENT              ACTION                           MESSAGE TYPE
─────────────────────────────────────────────────────────────────────────────────
T+0   L0   Project Agent       Receive bug report                —
T+1   L0   Project Agent       Select workflow: hotfix            —
T+2   L0   Project Agent       Dispatch Stage: Bug-Triage        StageDispatch

      L1   Stage:BugTriage     Decompose → 1 wave, 1 task        —
      L1   Stage:BugTriage     Dispatch Wave 1                   WaveDispatch
      L2   Wave:BT-W1          Dispatch Task: Triage              TaskDispatch
      L3   Task:Research       [WORK] Analyze error logs          —
                               Identify root cause: Path::new()
                               doesn't handle non-UTF8 on Windows
                               Severity: SEV2
                               Scope: sync_engine/path.rs L42-58
      L3   Task:Research       Return triage report               StatusReport
      L2   Wave:BT-W1          Collect results                   WaveReport
      L1   Stage:BugTriage     Gate: PASS (root cause identified) —
      L1   Stage:BugTriage     Report to Project                 StageReport(PASS)

T+5   L0   Project Agent       Dispatch Stage: Fix               StageDispatch
                               (includes triage report as predecessor artifact)

      L1   Stage:Fix           Decompose → 1 wave, 2 tasks       —
      L1   Stage:Fix           Dispatch Wave 1                   WaveDispatch
      L2   Wave:F-W1           Dispatch 2 parallel tasks          TaskDispatch ×2
      L3   Task:Impl-Fix       [WORK] Fix path handling           —  ┐
                               Modify: sync_engine/path.rs        │ PARALLEL
      L3   Task:Impl-Test      [WORK] Write regression test       —  ┘
                               Create: tests/regression/
                                       unicode_path_test.rs
      L3   Task:Impl-Fix       Return patched code                StatusReport
      L3   Task:Impl-Test      Return regression test             StatusReport
      L2   Wave:F-W1           Conflict check: OK                WaveReport
      L1   Stage:Fix           Gate: PASS (build passes)          —
      L1   Stage:Fix           Report to Project                 StageReport(PASS)

T+10  L0   Project Agent       Dispatch Stage: Test              StageDispatch

      L1   Stage:Test          Decompose → 1 wave, 1 task        —
      L1   Stage:Test          Dispatch Wave 1                   WaveDispatch
      L2   Wave:T-W1           Dispatch Task: Run tests           TaskDispatch
      L3   Task:Test           [WORK] Run:                        —
                               - cargo test (all 59 pass)
                               - regression test (PASS)
                               - smoke test with unicode paths (PASS)
      L3   Task:Test           Return test results                StatusReport
      L2   Wave:T-W1           Collect results                   WaveReport
      L1   Stage:Test          Gate: PASS (zero failures)         —
      L1   Stage:Test          Report to Project                 StageReport(PASS)

T+12  L0   Project Agent       Dispatch Stage: Release           StageDispatch

      L1   Stage:Release       Decompose → 1 wave, 1 task        —
      L1   Stage:Release       Dispatch Wave 1                   WaveDispatch
      L2   Wave:R-W1           Dispatch Task: Release             TaskDispatch
      L3   Task:Implement      [WORK] git tag v1.2.1              —
                               Update CHANGELOG.md
                               Create release commit
      L3   Task:Implement      Return release artifacts           StatusReport
      L2   Wave:R-W1           Collect results                   WaveReport
      L1   Stage:Release       Gate: PASS                         —
      L1   Stage:Release       Report to Project                 StageReport(PASS)

T+14  L0   Project Agent       All 4 stages PASS                 —
      L0   Project Agent       Produce hotfix report             —
      L0   Project Agent       Present to user                   —
```

## Compact Message Examples

### StageDispatch — Fix Stage

```yaml
task_dispatch:
  header:
    dispatch_id: "d-20260404-hf-002"
    parent_id: "project-hotfix-001"
    layer: "project"
    timestamp: "2026-04-04T14:05:00Z"
    timeout_seconds: 1800
  task:
    task_id: "S02-fix"
    type: "stage"
    title: "Fix Stage — Unicode Path Handling"
    description: >
      Apply fix for unicode path corruption in sync_engine/path.rs.
      Write regression test covering the identified root cause.
  context:
    predecessor_artifacts:
      - artifact_id: "triage-report-v1"
        path: ".local/stages/S01_triage/triage_report.md"
        summary: "Root cause: Path::new() on L42-58 of path.rs. SEV2. Scope: 1 file"
    applicable_rules:
      loading_strategy: "minimal"
      language: "rust"
      task_type: "bug_fix"
      quality_focus: ["correctness"]
  acceptance:
    criteria:
      - "cargo build succeeds"
      - "Regression test for unicode paths passes"
    quality_thresholds:
      max_blocker_findings: 0
    max_retry_rounds: 1
```

### TaskDispatch — Regression Test

```yaml
task_dispatch:
  header:
    dispatch_id: "d-20260404-hf-005"
    parent_id: "d-20260404-hf-003"
    layer: "wave"
    timestamp: "2026-04-04T14:06:00Z"
    timeout_seconds: 900
  task:
    task_id: "S02-W01-T02"
    type: "test"
    title: "Write Unicode Path Regression Test"
    description: >
      Create regression test covering unicode directory paths on all
      platforms. Must test: CJK chars, emoji, combining marks, RTL.
  context:
    predecessor_artifacts:
      - artifact_id: "triage-report-v1"
        path: ".local/stages/S01_triage/triage_report.md"
        summary: "Bug in Path::new() L42-58, fails on non-ASCII Windows paths"
    owned_files:
      - "tests/regression/unicode_path_test.rs"
    applicable_rules:
      loading_strategy: "minimal"
      language: "rust"
      task_type: "bug_fix"
      quality_focus: ["correctness"]
  acceptance:
    criteria:
      - "Test covers CJK, emoji, combining marks, and RTL paths"
      - "Test fails against unfixed code, passes against fixed code"
    max_retry_rounds: 1
```

## Comparison: Full-Pipeline vs Hotfix

| Dimension | Full Pipeline | Hotfix |
|-----------|--------------|--------|
| **Stages** | 7 (design → plan → impl → review → test → testgate → release) | 4 (triage → fix → test → release) |
| **Total Task Agents** | ~18 | 5 |
| **Max parallelism** | 4 tasks (impl wave 2) | 2 tasks (fix wave 1) |
| **Convergence loops** | Yes (review-fix, test-fix cycles) | No (single pass per gate) |
| **Design phase** | Full architecture + ADRs | None (scope known from triage) |
| **Review depth** | 3 parallel reviewers (code, security, SOLID) | Implicit in test stage |
| **Gate evaluations** | 7 gates (6 standard + 1 passthrough) | 4 gates (all standard) |
| **Context per task** | ~8K tokens (full rule loading) | ~5K tokens (minimal rules) |
| **Typical duration** | Hours to days | 30 min to 2 hours |
| **Gate profile** | standard (composite ≥ 85) | standard (but fewer checks) |

## Structural Invariants

Both workflows share identical structural properties:

1. **Same 4-layer hierarchy:** Project → Stage → Wave → Task
2. **Same message schemas:** StageDispatch, WaveDispatch, TaskDispatch, StatusReport
3. **Same gate mechanism:** All stages evaluated before advancement
4. **Same escalation chain:** Task → Wave → Stage → Project → Human
5. **Same file ownership rules:** Disjoint writable files within each wave
6. **Same context isolation:** Each Task Agent spawns with fresh context window

The only difference is the workflow template — which stages are included and
how many waves each stage produces. The architectural invariants (P1–P5) hold
for both workflows without exception.
