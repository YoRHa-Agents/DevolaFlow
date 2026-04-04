# Workflow Types Catalog — Comprehensive Research

> **Scope**: Workflow type definitions, stage compositions, loop-back patterns, and cross-type analysis for the Agent Workflow Meta-Framework.
> **Date**: 2026-04-04
> **Status**: Research Complete

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Deep-Dive: Research-Design-Review-Refine Workflow](#2-deep-dive-research-design-review-refine)
3. [Deep-Dive: Full Pipeline Workflow](#3-deep-dive-full-pipeline)
4. [Workflow Types Catalog](#4-workflow-types-catalog)
5. [Cross-Type Analysis](#5-cross-type-analysis)
6. [Workflow Composition Patterns](#6-workflow-composition-patterns)
7. [References](#7-references)

---

## 1. Executive Summary

This document catalogs 10 distinct workflow types applicable to an Agent-orchestrated development system. Each workflow is decomposed into ordered stage primitives — the atomic units of work that can be composed, reordered, and conditionally skipped to form any workflow variant.

**Key findings:**

- All workflows share a small set of **universal primitives**: at minimum `review` and `validate/verify` appear in every workflow type studied. `Plan` appears in 9 of 10 types.
- **Loop-back patterns** fall into two categories: *review-refine loops* (quality-driven, bounded by score thresholds) and *test-fix loops* (correctness-driven, bounded by pass/fail gates).
- Workflow types exist on a **complexity spectrum** from 3-stage (research-only) to 8-stage (full pipeline), with intermediate types occupying 4–6 stages.
- **Composition primitives** from workflow orchestration literature (Sequence, Parallel, Choice, Traverse, Identity) are sufficient to express all 10 workflow types declaratively.
- The full pipeline workflow (`design-plan-impl-review-test-refine-testgate-release`) is the **maximal superset** — every other workflow type is a strict subset of its stages.

---

## 2. Deep-Dive: Research-Design-Review-Refine

### 2.1 Overview

The **research-design-review-refine** (RDRR) workflow is an iterative knowledge-building and design-convergence loop. It is used when the goal is to produce a *design artifact* (architecture document, API specification, system design) grounded in research evidence, refined through review cycles until it meets quality criteria.

This pattern derives from the **Spiral Model**'s risk-driven iteration and Agile's inspect-and-adapt principle, applied specifically to pre-implementation design activities.

### 2.2 Stage Definitions and Ordering

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ Research  │───▸│  Design  │───▸│  Review  │───▸│  Refine  │
└──────────┘    └──────────┘    └──────────┘    └─────┬────┘
                     ▲                                │
                     └──────── loop-back ─────────────┘
```

| # | Stage | Description | Input | Output |
|---|-------|-------------|-------|--------|
| 1 | **Research** | Gather information, survey prior art, analyze constraints, benchmark alternatives | Task description, scope boundaries, reference materials | Research report: findings, comparison matrix, risk assessment, knowledge gaps |
| 2 | **Design** | Synthesize research into a concrete design artifact — architecture, API, data model, or system specification | Research report, design constraints, quality requirements | Design document: architecture diagrams, interface definitions, trade-off analysis, decision records |
| 3 | **Review** | Evaluate the design against quality criteria, consistency, completeness, feasibility, and alignment with requirements | Design document, review checklist, acceptance criteria | Review verdict: PASS/FAIL with score, itemized findings (blocking issues, suggestions, questions) |
| 4 | **Refine** | Address review findings — fix blocking issues, incorporate suggestions, resolve ambiguities, deepen under-specified areas | Review findings (itemized), original design document | Refined design document (versioned), changelog of modifications, unresolved items list |

### 2.3 Review-Triggers-Refine: Loop Conditions

The Review → Refine → Design loop is the core iteration mechanism. It triggers under these conditions:

**Trigger conditions (Review → Refine):**
1. **Blocking issues found**: Any finding classified as `blocking` (e.g., missing error handling strategy, unresolved dependency conflict, infeasible performance requirement)
2. **Quality score below threshold**: Composite review score < 80% across dimensions (completeness, consistency, feasibility, clarity)
3. **Open questions remain**: Reviewer raises questions that reveal ambiguity in the design, requiring author clarification and design update
4. **Requirement misalignment**: Design does not fully address stated requirements or introduces unstated assumptions

**Loop-back scope:**
- Refine feeds back to *Design* (not Research) in most iterations — the research foundation is stable; only the design synthesis needs adjustment
- In rare cases (~10% of loops), Refine identifies **knowledge gaps** that require returning to *Research* for additional investigation. This happens when review findings reveal that the original research was incomplete or that a new alternative must be evaluated

### 2.4 Termination Criteria

The loop terminates when ALL of the following hold:

| Criterion | Threshold | Rationale |
|-----------|-----------|-----------|
| No blocking issues | 0 blocking findings | Blocking issues indicate design is not viable |
| Quality score | ≥ 80% composite | Ensures design meets minimum quality bar |
| Max rounds | ≤ 3 review-refine cycles | Prevents infinite loops; if 3 rounds cannot resolve, escalate to human |
| Requirement coverage | 100% of stated requirements addressed | No requirement left unaddressed |
| Reviewer consensus | All reviewers approve or abstain (no reject) | Ensures multi-perspective validation |

**Escalation protocol**: If max rounds reached without convergence, the workflow pauses and produces a **divergence report** listing unresolved items, conflicting reviewer opinions, and recommended next steps for human decision.

### 2.5 Real-World Examples

1. **Architecture Decision Record (ADR) workflow**: Research alternative approaches → Design the selected approach → Review with senior engineers → Refine based on feedback. Common in organizations following the Thoughtworks ADR process.

2. **API design for a new microservice**: Research existing API patterns and consumer needs → Design OpenAPI specification → Review with API consumers and security team → Refine endpoints, error codes, and auth flows.

3. **Database schema migration design**: Research current schema usage patterns and query performance → Design new schema with migration plan → Review with DBA and application owners → Refine based on performance concerns and backward compatibility requirements.

4. **Agent Workflow Meta-Framework design** (this project): Research existing Agent frameworks (CrewAI, AutoGen, LangGraph) → Design the 4-layer delegation architecture → Review against requirements → Refine based on feasibility analysis.

### 2.6 AgentTeam Participation

| AgentTeam | Role in RDRR |
|-----------|-------------|
| **Research** | Primary owner of Stage 1 (Research). May be recalled during Refine if knowledge gaps are identified |
| **Design** | Primary owner of Stage 2 (Design) and Stage 4 (Refine). Produces and iterates on design artifacts |
| **Review** | Primary owner of Stage 3 (Review). Evaluates design quality, consistency, and feasibility |
| **Implement** | Not active — this workflow produces design artifacts, not code |
| **Test** | Not active — validation is conceptual (review-based), not executable (test-based) |

---

## 3. Deep-Dive: Full Pipeline Workflow

### 3.1 Overview

The **design-plan-impl-review-test-refine-testgate-release** (DPIRTGR) workflow is the maximal development pipeline. It covers the complete lifecycle from design through deployment, incorporating both quality review loops and automated test gates. This is the workflow for **greenfield feature development** or **major system changes** where all stages are necessary.

### 3.2 Complete Stage Chain

```
┌────────┐  ┌──────┐  ┌──────┐  ┌────────┐  ┌──────┐  ┌────────┐  ┌──────────┐  ┌─────────┐
│ Design │─▸│ Plan │─▸│ Impl │─▸│ Review │─▸│ Test │─▸│ Refine │─▸│ TestGate │─▸│ Release │
└────────┘  └──────┘  └──────┘  └───┬────┘  └──┬───┘  └───┬────┘  └─────┬────┘  └─────────┘
                 ▲                   │          │          │              │
                 │         ┌────────┘          │          │              │
                 │         │  review-refine    │          │              │
                 │         └──────────────────▸│          │              │
                 │                             │          │              │
                 │              ┌──────────────┘          │              │
                 │              │  test-refine            │              │
                 │              └────────────────────────▸│              │
                 │                                        │              │
                 └───────── refine loop-back (to Plan) ───┘              │
                                                                        │
                                        ┌───────────────────────────────┘
                                        │  testgate-fail → back to Impl
                                        ▼
```

| # | Stage | Description | Gate Role | Input | Output |
|---|-------|-------------|-----------|-------|--------|
| 1 | **Design** | Define architecture, interfaces, data models, and technical approach for the feature/change | Entry gate: validates requirements are clear and complete | Requirements document, constraints, prior research | Design document, architecture diagrams, interface contracts, ADRs |
| 2 | **Plan** | Decompose the design into implementable work units — Waves and Tasks with dependencies, estimates, and acceptance criteria | Sequencing gate: validates design is implementable and decomposable | Design document, team capacity, priority constraints | Implementation plan: Wave breakdown, Task list with estimates, dependency matrix, risk register |
| 3 | **Impl** | Execute the plan — write code, create tests, build infrastructure as specified in each Task | N/A (execution stage) | Task specifications from Plan, code-rules, language conventions | Source code, unit tests, configuration files, build artifacts |
| 4 | **Review** | Evaluate implementation quality — code review, design compliance, security review, style/convention adherence | Quality gate: blocks progression if critical issues found | Implemented code, design document (for compliance check), review checklists | Review verdict: PASS/REVISE with itemized findings, severity classification |
| 5 | **Test** | Execute automated test suites — unit, integration, E2E, performance, security scans | Correctness gate: blocks progression if tests fail | Source code, test suites, test infrastructure | Test results: pass/fail per suite, coverage report, performance benchmarks, security scan results |
| 6 | **Refine** | Address findings from Review and/or Test — fix bugs, resolve review comments, improve code quality | N/A (remediation stage) | Review findings and/or test failures, source code | Updated source code, updated tests, refine changelog |
| 7 | **TestGate** | Final quality checkpoint — runs full regression suite, validates all acceptance criteria, checks coverage thresholds, confirms release readiness | Release gate: PASS required for release, no bypass allowed | All source code and tests (post-refine), acceptance criteria from Plan, coverage/quality thresholds | TestGate report: PASS/FAIL with metrics (coverage %, test pass rate, lint score, security scan status) |
| 8 | **Release** | Package, tag, deploy, and announce — create release artifacts, update changelogs, deploy to target environments, notify stakeholders | N/A (terminal stage) | TestGate PASS, release configuration (versioning, target environments, changelog template) | Release artifacts, deployment confirmation, changelog, release notes, version tag |

### 3.3 Gate Roles Between Stages

Gates serve as **quality checkpoints** that enforce standards before allowing progression:

| Gate | Location | Pass Criteria | Fail Action |
|------|----------|---------------|-------------|
| **Requirements Gate** | Before Design | Requirements document exists, is unambiguous, has acceptance criteria | Block: return to requirements gathering |
| **Design Gate** | Design → Plan | Design covers all requirements, is technically feasible, has been reviewed | Loop: enter RDRR sub-workflow |
| **Plan Gate** | Plan → Impl | Plan is complete, estimates are reasonable, dependencies are resolved, risks mitigated | Loop: refine plan |
| **Review Gate** | Review → Test | No blocking findings, code quality score ≥ threshold | Loop: Review → Refine → Impl |
| **Test Gate (interim)** | Test → Refine | Determines if refine is needed | Loop: Test → Refine → Impl |
| **TestGate (final)** | TestGate → Release | All criteria met: coverage ≥ 80%, all tests pass, no critical security findings, lint clean | Loop: TestGate → Refine → Impl → Test → TestGate |
| **Release Gate** | Before Release | TestGate PASS, changelog complete, version number assigned | Block: complete missing artifacts |

### 3.4 Refine Loop-Back Conditions and Scope

The Refine stage is the central remediation mechanism. Its loop-back behavior depends on **what triggered it**:

**Trigger 1: Review findings**
- Loop: Review → Refine → Impl (re-implement affected code) → Review
- Scope: Only the code/files cited in review findings are modified
- Max rounds: 3 review-refine cycles before escalation

**Trigger 2: Test failures**
- Loop: Test → Refine → Impl (fix failing code) → Test
- Scope: Only the modules/functions that caused test failures
- Max rounds: 5 test-fix cycles (tests are deterministic, so convergence is expected)

**Trigger 3: TestGate failure**
- Loop: TestGate → Refine → Impl → Test → TestGate
- Scope: Depends on failure type:
  - Coverage gap → write additional tests (Refine targets test code)
  - Regression failure → fix implementation (Refine targets source code)
  - Security finding → remediate vulnerability (Refine targets affected module)
  - Lint failure → apply formatting/style fixes (Refine targets style)
- Max rounds: 3 TestGate cycles before escalation

**How far back does Refine go?**
- **Default**: Refine loops back to **Impl** — the assumption is that the Plan and Design are sound, and only the implementation needs adjustment
- **Escalation to Plan**: If Refine repeatedly fails (3+ rounds) or if findings indicate a fundamental approach problem (not just bugs), the loop escalates back to **Plan** for re-decomposition
- **Escalation to Design**: If Plan-level re-decomposition reveals that the architecture cannot support the requirement, escalation reaches **Design** for architectural revision. This is rare (<5% of cases) and indicates a design gap
- **Never back to Research**: In the full pipeline, Research is assumed complete before entering. If research gaps are discovered, a separate RDRR sub-workflow is spawned

### 3.5 TestGate as Quality Checkpoint

TestGate is distinct from the Test stage. While Test *runs* the test suites, TestGate *evaluates* the aggregate results against release criteria:

| Dimension | Test Stage | TestGate Stage |
|-----------|-----------|----------------|
| **Purpose** | Execute test suites | Evaluate readiness for release |
| **Scope** | Run unit/integration/E2E/perf/security tests | Aggregate all results + check coverage + check quality metrics |
| **Output** | Raw test results (pass/fail per test) | Release decision (PASS/FAIL with rationale) |
| **Failure action** | Feed failures to Refine | Block release, feed gap analysis to Refine |
| **Bypass** | Can be partially skipped (e.g., skip perf tests for minor changes) | **Never bypassed** — mandatory before release |

**TestGate checklist** (all must pass):

```yaml
testgate:
  criteria:
    test_pass_rate: ">= 100%"        # all tests must pass
    code_coverage: ">= 80%"          # line coverage threshold
    lint_score: "clean"              # zero lint errors
    security_scan: "no critical/high" # no unresolved critical/high findings
    build_reproducible: true          # build from clean checkout succeeds
    changelog_complete: true          # all changes documented
    acceptance_criteria_met: true     # all requirements verified
  max_retry_rounds: 3
  on_failure: "route to Refine with gap analysis"
  on_max_retries: "escalate to human with full report"
```

---

## 4. Workflow Types Catalog

### 4.0 Summary Table

| # | Workflow Type | Stages | Required / Optional | Loop Points | Typical Duration | AgentTeams |
|---|--------------|--------|---------------------|-------------|------------------|------------|
| 1 | Research-Only | research → compare → report | All required | compare ↔ research | 1–4 hours | Research |
| 2 | Design-Only | requirements → design → review → document | All required | review → design | 2–8 hours | Design, Review |
| 3 | Hotfix | bug-triage → fix → test → release | All required | test → fix | 30 min – 4 hours | Implement, Test |
| 4 | Refactoring | analyze → plan → refactor → test → verify | All required | test → refactor | 2–16 hours | Implement, Test, Review |
| 5 | Migration | assess → plan → migrate → validate → cutover | All required; cutover can be staged | validate → migrate | 4 hours – multi-day | Research, Implement, Test |
| 6 | Spike/PoC | hypothesis → prototype → evaluate → decide | decide optional (may defer) | evaluate → prototype | 2–8 hours (time-boxed) | Research, Implement |
| 7 | Documentation-Only | audit → write → review → publish | publish optional (draft mode) | review → write | 1–6 hours | Research, Review |
| 8 | Security Audit | scan → analyze → prioritize → fix → verify | fix optional (report-only mode) | verify → fix | 2–8 hours | Research, Implement, Test, Review |
| 9 | Research-Design-Review-Refine | research → design → review → refine | All required | review → refine → design | 4–16 hours | Research, Design, Review |
| 10 | Full Pipeline | design → plan → impl → review → test → refine → testgate → release | testgate, release context-dependent | review/test → refine → impl | 8 hours – multi-day | All five teams |

### 4.1 Research-Only

**Name**: `research-only`

**Applicable scenarios**:
- Technology evaluation and comparison (e.g., "compare React vs Svelte for our use case")
- Literature survey for a design decision
- Competitive analysis
- Feasibility assessment before committing to a project
- Gathering best practices before starting development

**Stage composition**:

| # | Stage | Description | Input | Output |
|---|-------|-------------|-------|--------|
| 1 | **Research** | Gather information from multiple sources — documentation, code repositories, papers, benchmarks | Research question, scope boundaries, evaluation criteria | Raw findings: notes, bookmarks, data points, code samples |
| 2 | **Compare** | Analyze and compare findings against evaluation criteria — create comparison matrices, identify trade-offs | Raw findings, evaluation criteria | Comparison matrix, pros/cons analysis, trade-off map |
| 3 | **Report** | Synthesize comparison into a structured deliverable — executive summary, detailed analysis, recommendation | Comparison results, audience context | Research report with recommendation, supporting evidence, confidence levels |

**Required vs optional stages**: All three are required. Compare can loop back to Research if gaps are found.

**Loop-back points**:
- Compare → Research: when comparison reveals missing data points or an unconsidered alternative
- Max 2 additional research rounds

**Typical duration**: 1–4 hours (single-agent), 4–16 hours (comprehensive multi-source)

**AgentTeams**: Research (sole participant)

---

### 4.2 Design-Only

**Name**: `design-only`

**Applicable scenarios**:
- API specification design (OpenAPI/GraphQL schema)
- Database schema design
- UI/UX wireframe and component design
- System architecture for a well-understood domain (no research needed)
- Interface contract design between teams/services

**Stage composition**:

| # | Stage | Description | Input | Output |
|---|-------|-------------|-------|--------|
| 1 | **Requirements** | Clarify and formalize requirements — functional, non-functional, constraints, out-of-scope items | User request, domain context, existing system docs | Requirements document: user stories, acceptance criteria, constraints list |
| 2 | **Design** | Create the design artifact — architecture, API spec, schema, wireframes | Requirements document, design patterns library, existing system interfaces | Design document: diagrams, specifications, decision records |
| 3 | **Review** | Evaluate design against requirements, consistency, feasibility, standards compliance | Design document, review checklist | Review verdict with itemized findings |
| 4 | **Document** | Finalize design documentation — clean up, add examples, create companion guides, version and publish | Reviewed (approved) design, documentation standards | Final design document, API reference, migration guide (if applicable) |

**Required vs optional stages**: All required. Document may be abbreviated if design is internal-only.

**Loop-back points**:
- Review → Design: when review finds issues (primary loop)
- Review → Requirements: when review reveals ambiguous or conflicting requirements (~15% of cases)
- Max 3 review cycles

**Typical duration**: 2–8 hours

**AgentTeams**: Design (primary), Review (Stage 3)

---

### 4.3 Hotfix

**Name**: `hotfix`

**Applicable scenarios**:
- Production bug causing user-visible impact (SEV1/SEV2)
- Security vulnerability requiring immediate patch
- Data corruption requiring emergency fix
- Critical dependency update (e.g., CVE in a transitive dependency)

**Stage composition**:

| # | Stage | Description | Input | Output |
|---|-------|-------------|-------|--------|
| 1 | **Bug-Triage** | Assess severity, identify root cause, determine scope of impact, decide if hotfix workflow applies | Bug report, error logs, user reports, monitoring alerts | Triage report: severity level, root cause hypothesis, affected components, fix scope |
| 2 | **Fix** | Implement the minimal fix — no refactoring, no feature additions, only the targeted correction | Triage report, affected source code | Patched code (minimal diff), regression test for the specific bug |
| 3 | **Test** | Run focused test suite — smoke tests, affected-area tests, regression test for the bug | Patched code, test suites | Test results: pass/fail, confidence level |
| 4 | **Release** | Fast-track deployment — skip staging for SEV1, minimal approval, deploy with rollback readiness | Tested patch, release configuration | Deployed fix, post-deployment verification, incident update |

**Required vs optional stages**: All required. Test may be reduced to smoke tests for SEV1.

**Loop-back points**:
- Test → Fix: if tests fail, fix is adjusted (tight loop, max 3 rounds)
- No loop back to Triage — if the root cause hypothesis is wrong, a new hotfix cycle starts

**Typical duration**: 30 minutes – 4 hours (SEV1: <1 hour target)

**AgentTeams**: Implement (Fix), Test (Test). Review is abbreviated to single-reviewer approval.

**Distinguishing characteristics**:
- Skips Design and Plan stages entirely
- Minimal review (1 reviewer, not full review board)
- Reduced test scope (focused, not comprehensive)
- Post-mortem follows *after* release (not before)

---

### 4.4 Refactoring

**Name**: `refactoring`

**Applicable scenarios**:
- Technical debt reduction sprints
- Code quality improvement campaigns
- Architectural migration within the same codebase (e.g., monolith → modules)
- Performance optimization of existing code
- Applying new coding standards to legacy code

**Stage composition**:

| # | Stage | Description | Input | Output |
|---|-------|-------------|-------|--------|
| 1 | **Analyze** | Identify refactoring targets — code smells, complexity hotspots, duplication, coupling analysis | Source code, static analysis reports, performance profiles, code-rules | Analysis report: prioritized list of refactoring targets, estimated effort, risk assessment |
| 2 | **Plan** | Design refactoring strategy — order of operations, dependency-safe sequence, behavioral preservation approach | Analysis report, test coverage report | Refactoring plan: ordered task list, test-first requirements, rollback strategy |
| 3 | **Refactor** | Execute refactoring changes — one small, behavior-preserving transformation at a time | Refactoring plan, source code, existing tests | Refactored code, updated tests, refactoring log |
| 4 | **Test** | Run full test suite — confirm behavioral equivalence, check for regressions, measure quality improvements | Refactored code, complete test suite | Test results, coverage delta, complexity delta, performance comparison |
| 5 | **Verify** | Final validation — compare before/after metrics, confirm all acceptance criteria met, document improvements | Test results, pre-refactoring baseline metrics | Verification report: metric comparisons, documented improvements, remaining tech debt |

**Required vs optional stages**: All required. The "Two Hats" principle mandates never mixing feature work with refactoring.

**Loop-back points**:
- Test → Refactor: if tests reveal regressions, fix and re-test (primary loop, max 5 rounds)
- Verify → Analyze: if verification shows the refactoring goal is only partially achieved, re-analyze remaining targets (secondary loop, max 2 rounds)

**Typical duration**: 2–16 hours per refactoring sprint

**AgentTeams**: Implement (Analyze, Refactor), Test (Test, Verify), Review (optional code review after Refactor)

---

### 4.5 Migration

**Name**: `migration`

**Applicable scenarios**:
- Database migration (schema change, engine swap)
- Cloud migration (on-prem → cloud, cloud-to-cloud)
- Language/framework migration (Python 2→3, React class→hooks)
- API version migration (v1 → v2 with backward compatibility)
- Infrastructure migration (VM → containers, monolith → microservices)

**Stage composition**:

| # | Stage | Description | Input | Output |
|---|-------|-------------|-------|--------|
| 1 | **Assess** | Map current state — inventory assets, identify dependencies, assess risks, define success metrics | Current system documentation, access to current infrastructure | Assessment report: asset inventory, dependency map, risk matrix, success criteria, effort estimate |
| 2 | **Plan** | Design migration strategy — choose approach (big-bang vs strangler fig vs parallel run), define wave-based rollout, create rollback plan | Assessment report, target architecture, business constraints | Migration plan: wave breakdown, timeline, rollback procedures, cutover checklist |
| 3 | **Migrate** | Execute migration — move/transform data, deploy new infrastructure, implement code changes per wave | Migration plan, source and target systems | Migrated components (per wave), migration logs, intermediate state artifacts |
| 4 | **Validate** | Verify migration correctness — data reconciliation, functional testing, performance comparison, compliance checks | Migrated components, validation criteria, pre-migration baseline | Validation report: data integrity confirmation, functional test results, performance comparison |
| 5 | **Cutover** | Switch production traffic to migrated system — DNS changes, load balancer updates, decommission legacy (after hypercare) | Validated migration, cutover runbook | Production on new system, legacy decommissioned (or in read-only), hypercare monitoring |

**Required vs optional stages**: All required. Cutover can be phased (progressive cutover per wave).

**Loop-back points**:
- Validate → Migrate: if validation finds data discrepancies or functional issues, re-migrate affected components (max 3 per wave)
- Cutover → Validate: if post-cutover monitoring detects issues, re-validate and potentially rollback
- Assess → (restart): if assessment reveals migration is infeasible, the workflow terminates with a no-go recommendation

**Typical duration**: 4 hours (small schema migration) to multi-week (cloud migration). Agent-assisted scope: 4 hours – 2 days for code/config migrations.

**AgentTeams**: Research (Assess), Implement (Migrate), Test (Validate), Review (optional review of migration scripts)

---

### 4.6 Spike / PoC

**Name**: `spike-poc`

**Applicable scenarios**:
- Evaluating a new technology/library before adoption
- Validating a technical approach before full implementation
- De-risking a high-uncertainty feature
- Answering a specific technical question with working code
- Exploring integration feasibility with external systems

**Stage composition**:

| # | Stage | Description | Input | Output |
|---|-------|-------------|-------|--------|
| 1 | **Hypothesis** | Define the question to answer — what specific uncertainty needs resolution? What would success look like? | Technical uncertainty description, context, constraints | Hypothesis statement: question, success criteria, time-box limit, out-of-scope boundaries |
| 2 | **Prototype** | Build a minimal working prototype that tests the hypothesis — throwaway code, shortcuts allowed, no production standards | Hypothesis, relevant APIs/libraries, existing code (if any) | Working prototype, observations during building, unexpected findings |
| 3 | **Evaluate** | Assess the prototype against success criteria — does it answer the question? What did we learn? What new questions emerged? | Prototype, hypothesis success criteria | Evaluation report: hypothesis confirmed/denied, findings, performance data, new risks/questions |
| 4 | **Decide** | Make a go/no-go decision based on evaluation — proceed with full implementation, pivot, or abandon | Evaluation report, business context | Decision record: decision (proceed/pivot/abandon), rationale, recommended next workflow type |

**Required vs optional stages**: Hypothesis, Prototype, Evaluate are required. Decide may be deferred to a human stakeholder.

**Loop-back points**:
- Evaluate → Prototype: if evaluation is inconclusive, refine the prototype (max 2 iterations within time-box)
- Evaluate → Hypothesis: if the original hypothesis was poorly framed, redefine and re-prototype (rare, max 1 round)

**Typical duration**: 2–8 hours (strictly time-boxed; time-box is defined in Hypothesis stage)

**AgentTeams**: Research (Hypothesis, Evaluate), Implement (Prototype)

**Distinguishing characteristics**:
- **Time-boxed**: Unlike other workflows, the spike has a hard time limit. If the time-box expires before Evaluate, the workflow terminates with an "inconclusive" result.
- **Throwaway output**: Prototype code is explicitly NOT production code. It must not be carried forward into implementation without being rewritten.
- **Decision-oriented**: The primary output is a *decision*, not an artifact.

---

### 4.7 Documentation-Only

**Name**: `documentation-only`

**Applicable scenarios**:
- Writing user guides, API references, or tutorials for existing systems
- Updating outdated documentation to match current code
- Creating onboarding documentation for new team members
- Generating changelog or release notes
- Compliance documentation (SOC2, ISO 27001)

**Stage composition**:

| # | Stage | Description | Input | Output |
|---|-------|-------------|-------|--------|
| 1 | **Audit** | Survey existing documentation — identify gaps, outdated content, inconsistencies with current code | Existing docs, current codebase, documentation standards | Audit report: gap analysis, outdated items, accuracy issues, priority ranking |
| 2 | **Write** | Create or update documentation — fill gaps, correct inaccuracies, add examples, improve clarity | Audit report, source code, documentation templates | Draft documentation: new content, updated sections, examples, diagrams |
| 3 | **Review** | Technical and editorial review — verify accuracy against code, check clarity, validate examples | Draft documentation, source code (for accuracy), style guide | Review feedback: accuracy corrections, clarity suggestions, missing topics |
| 4 | **Publish** | Finalize and deploy documentation — merge to docs branch, build docs site, update navigation/search index | Reviewed documentation, publishing infrastructure config | Published documentation, updated search index, notification to stakeholders |

**Required vs optional stages**: Audit, Write, Review are required. Publish is optional (draft mode for internal review).

**Loop-back points**:
- Review → Write: if review finds inaccuracies or gaps (primary loop, max 2 rounds)
- Audit → (no loop): Audit is a one-time assessment

**Typical duration**: 1–6 hours per documentation unit

**AgentTeams**: Research (Audit — surveying existing state), Review (Review — accuracy and quality check). Write and Publish are typically done by a documentation specialist agent.

---

### 4.8 Security Audit

**Name**: `security-audit`

**Applicable scenarios**:
- Pre-release security assessment
- Periodic security review (quarterly/annual)
- Post-incident security hardening
- Compliance-driven security verification (PCI-DSS, SOC2, HIPAA)
- Dependency vulnerability assessment (CVE triage)

**Stage composition**:

| # | Stage | Description | Input | Output |
|---|-------|-------------|-------|--------|
| 1 | **Scan** | Run automated security tools — SAST, DAST, SCA, secret scanning, container scanning, IaC scanning | Source code, dependencies, infrastructure config, container images | Raw scan results: vulnerability list with severity, location, and CWE/CVE identifiers |
| 2 | **Analyze** | Triage scan results — confirm true positives, dismiss false positives, understand attack vectors, assess exploitability | Raw scan results, application context, threat model | Analyzed findings: confirmed vulnerabilities with exploitability rating, attack scenario, affected data flows |
| 3 | **Prioritize** | Rank findings by risk — combine severity, exploitability, business impact, and fix effort to create a prioritized remediation queue | Analyzed findings, business risk context, fix effort estimates | Prioritized remediation plan: ordered list with risk score, recommended fix approach, effort estimate |
| 4 | **Fix** | Implement remediation — patch vulnerabilities, update dependencies, fix code patterns, add security controls | Prioritized remediation plan, source code | Patched code, updated dependencies, new security tests |
| 5 | **Verify** | Confirm remediation — re-scan to verify fixes, run security test suite, validate no regressions introduced | Patched code, security test suite | Verification report: confirmed fixes, remaining risk, re-scan results, compliance status |

**Required vs optional stages**: Scan, Analyze, Prioritize are always required. Fix is optional in report-only mode (audit produces recommendations, another team implements). Verify is required when Fix is included.

**Loop-back points**:
- Verify → Fix: if re-scan finds issues with the fix or new vulnerabilities introduced (max 3 rounds)
- Analyze → Scan: if analysis reveals scan configuration gaps (e.g., missed a scan type), re-scan with updated config (max 1 round)

**Typical duration**: 2–8 hours (automated scan + analysis), 1–3 days (with Fix and Verify)

**AgentTeams**: Research (Scan, Analyze — information gathering), Review (Prioritize — risk assessment), Implement (Fix), Test (Verify)

---

### 4.9 Additional Workflow Type: Feature Enhancement

**Name**: `feature-enhancement`

**Applicable scenarios**:
- Adding a new capability to an existing feature
- Extending an API with new endpoints
- Adding new UI components to an existing page
- Performance improvement of a specific feature
- Adding configuration options to existing behavior

**Stage composition**:

| # | Stage | Description | Input | Output |
|---|-------|-------------|-------|--------|
| 1 | **Scope** | Define the enhancement boundary — what changes, what stays the same, backward compatibility requirements | Feature request, existing feature docs, user feedback | Scope document: change description, compatibility constraints, acceptance criteria |
| 2 | **Plan** | Design the implementation approach — identify affected files, plan test strategy, estimate effort | Scope document, current codebase | Implementation plan: file list, change description per file, test plan |
| 3 | **Impl** | Implement the enhancement — modify existing code, add new code, write tests | Implementation plan, source code | Updated code, new/updated tests |
| 4 | **Review** | Code review focused on compatibility, quality, and scope adherence | Updated code, scope document | Review verdict |
| 5 | **Test** | Run tests including regression suite to verify no breakage | Updated code, test suites | Test results |

**Required vs optional stages**: All required.

**Loop-back points**: Review → Impl, Test → Impl (standard loops, max 3 rounds each)

**Typical duration**: 2–8 hours

**AgentTeams**: Design (Scope), Implement (Plan, Impl), Test (Test), Review (Review)

---

### 4.10 Additional Workflow Type: Performance Optimization

**Name**: `performance-optimization`

**Applicable scenarios**:
- Responding to performance degradation alerts
- Proactive optimization of identified bottlenecks
- Meeting SLA/SLO performance targets
- Reducing resource consumption (CPU, memory, I/O)

**Stage composition**:

| # | Stage | Description | Input | Output |
|---|-------|-------------|-------|--------|
| 1 | **Profile** | Identify bottlenecks — run profilers, analyze metrics, isolate hotspots | Performance metrics, profiling tools, source code | Profile report: hotspot list, resource consumption breakdown, baseline measurements |
| 2 | **Analyze** | Determine root causes — understand why each hotspot is slow, identify optimization opportunities | Profile report, source code, algorithm/data-structure knowledge | Root cause analysis: per-hotspot diagnosis, proposed optimizations ranked by impact/effort |
| 3 | **Optimize** | Implement optimizations — one at a time, with benchmarks before and after each change | Root cause analysis, source code | Optimized code, per-change benchmark results |
| 4 | **Benchmark** | Run comprehensive benchmarks — compare against baseline, verify no regressions, measure improvement across load scenarios | Optimized code, baseline measurements, benchmark suite | Benchmark report: improvement percentages, regression check, resource consumption comparison |
| 5 | **Verify** | Validate in production-like environment — confirm improvements hold under real traffic patterns | Benchmark results, staging environment | Production validation report, recommended for deployment or further optimization |

**Required vs optional stages**: Profile, Analyze, Optimize, Benchmark are required. Verify is optional if benchmarks are sufficient.

**Loop-back points**:
- Benchmark → Optimize: if improvement is insufficient, try next optimization (max 5 rounds)
- Verify → Analyze: if production behavior differs from benchmarks, re-analyze

**Typical duration**: 4–16 hours

**AgentTeams**: Research (Profile, Analyze), Implement (Optimize), Test (Benchmark, Verify)

---

## 5. Cross-Type Analysis

### 5.1 Universal Stage Primitives

Analyzing all 10 workflow types, certain stages appear across most or all workflows:

| Stage Primitive | Appears In | Frequency | Classification |
|----------------|-----------|-----------|----------------|
| **Review/Evaluate** | 10/10 | 100% | **Universal** |
| **Validate/Verify** | 10/10 | 100% | **Universal** |
| **Plan/Scope** | 9/10 | 90% | **Near-Universal** |
| **Analyze/Assess** | 8/10 | 80% | **Common** |
| **Implement/Execute** | 8/10 | 80% | **Common** |
| **Test** | 7/10 | 70% | **Common** |
| **Research/Investigate** | 6/10 | 60% | **Frequent** |
| **Design** | 4/10 | 40% | **Specialized** |
| **Release/Publish** | 4/10 | 40% | **Specialized** |
| **Refine** | 3/10 | 30% | **Specialized** |
| **Gate (formal checkpoint)** | 2/10 | 20% | **Specialized** |

**Insight**: `Review` and `Validate` are truly universal — every workflow must evaluate its output quality and verify correctness. `Plan` is near-universal because even short workflows benefit from explicit scoping. `Design` and `Release` are specialized because not all workflows produce design artifacts or deployable releases.

### 5.2 Type-Specific Stages

| Stage | Unique to Workflow(s) | Rationale |
|-------|-----------------------|-----------|
| **Bug-Triage** | Hotfix | Severity-based routing is unique to incident response |
| **Hypothesis** | Spike/PoC | Question-first framing is specific to exploratory work |
| **Cutover** | Migration | Traffic switching is specific to system replacement |
| **Scan** | Security Audit | Automated security tooling is specific to security workflows |
| **Profile** | Performance Optimization | Profiling instrumentation is specific to performance work |
| **Publish** | Documentation-Only | Documentation deployment infrastructure is specialized |
| **TestGate** | Full Pipeline | Formal release gate is only needed for production deployments |

### 5.3 Common Loop-Back Patterns

Three fundamental loop patterns emerge across all workflow types:

**Pattern 1: Quality Loop (Review-Refine)**
```
[Work Stage] → Review → {if FAIL} → Refine → [Work Stage]
```
- Present in: RDRR, Full Pipeline, Design-Only, Documentation-Only, Feature Enhancement
- Bounded by: quality score threshold + max iteration count
- Typical max rounds: 3

**Pattern 2: Correctness Loop (Test-Fix)**
```
[Work Stage] → Test → {if FAIL} → Fix → [Work Stage]
```
- Present in: Full Pipeline, Hotfix, Refactoring, Security Audit, Performance Optimization
- Bounded by: test pass/fail (deterministic) + max iteration count
- Typical max rounds: 5

**Pattern 3: Knowledge Loop (Evaluate-Investigate)**
```
[Analysis Stage] → Evaluate → {if INCOMPLETE} → Research → [Analysis Stage]
```
- Present in: Research-Only, Spike/PoC, Migration (Assess phase)
- Bounded by: completeness criteria + time-box
- Typical max rounds: 2

**Loop escalation hierarchy**:
All three patterns share a common escalation path when max rounds are exceeded:
1. **Auto-retry** (within max rounds): The loop continues automatically
2. **Scope escalation** (at max rounds): Loop-back target moves to an earlier stage (e.g., Impl → Plan → Design)
3. **Human escalation** (at max scope): Workflow pauses with a divergence report for human decision

### 5.4 AgentTeam Participation Matrix

| Workflow Type | Research | Design | Implement | Test | Review |
|--------------|----------|--------|-----------|------|--------|
| Research-Only | **Primary** | — | — | — | — |
| Design-Only | — | **Primary** | — | — | Active |
| Hotfix | — | — | **Primary** | Active | Minimal |
| Refactoring | — | — | **Primary** | **Primary** | Optional |
| Migration | Active | — | **Primary** | Active | Optional |
| Spike/PoC | Active | — | Active | — | — |
| Documentation-Only | Active | — | — | — | Active |
| Security Audit | Active | — | Active | Active | Active |
| Feature Enhancement | — | Active | **Primary** | Active | Active |
| Perf Optimization | Active | — | **Primary** | **Primary** | — |
| RDRR | **Primary** | **Primary** | — | — | **Primary** |
| Full Pipeline | Active | **Primary** | **Primary** | **Primary** | **Primary** |

**Legend**: **Primary** = owns and drives stages. Active = participates in specific stages. Minimal = reduced involvement. — = not involved.

---

## 6. Workflow Composition Patterns

### 6.1 SDLC Model Mapping

Each classical SDLC model maps to a composition of our stage primitives:

#### Waterfall

```yaml
type: waterfall
composition: sequence
stages:
  - requirements    # → maps to "scope/requirements" primitive
  - design          # → maps to "design" primitive
  - implementation  # → maps to "impl" primitive
  - testing         # → maps to "test" primitive
  - deployment      # → maps to "release" primitive
  - maintenance     # → maps to "monitor" (post-release, not in agent scope)
loops: none          # strictly sequential, no loop-back
gate_between_each: true  # each stage must complete before next begins
```

**Mapping insight**: Waterfall is the Full Pipeline without loop-back points. Its rigidity makes it unsuitable for agent workflows where iterative refinement is essential.

#### V-Model

```yaml
type: v-model
composition: sequence_with_parallel_verification
stages:
  # Left side (development)
  - requirements → acceptance_test_design    # parallel pair
  - system_design → system_test_design       # parallel pair
  - component_design → integration_test_design  # parallel pair
  - implementation
  # Right side (verification, mirrors left)
  - unit_test          # verifies implementation
  - integration_test   # verifies component_design
  - system_test        # verifies system_design
  - acceptance_test    # verifies requirements
loops: none
verification_traceability: true  # each test level traces to a design level
```

**Mapping insight**: V-Model pairs each design stage with a corresponding test stage. This maps to our meta-framework as a **Traverse** composition — apply a (design, test) pair for each abstraction level.

#### Agile / Scrum

```yaml
type: agile_scrum
composition: iterative_loop
sprint_stages:
  - sprint_planning    # → maps to "plan" primitive
  - implementation     # → maps to "impl" primitive
  - daily_standup      # → status check, maps to "checkpoint" mechanism
  - review             # → maps to "review" primitive (demo + feedback)
  - retrospective      # → maps to "refine" primitive (process improvement)
loop: sprint_stages repeated per sprint
termination: product_backlog_empty OR release_criteria_met
```

**Mapping insight**: Scrum is a fixed-cadence iteration of our Plan → Impl → Review → Refine loop. The sprint time-box maps to our max-rounds termination with a time dimension.

#### Kanban

```yaml
type: kanban
composition: continuous_flow
columns:
  - backlog           # → work queue
  - analysis          # → maps to "analyze" primitive
  - development       # → maps to "impl" primitive
  - review            # → maps to "review" primitive
  - testing           # → maps to "test" primitive
  - done              # → maps to "release" primitive
loops: pull-based (items can move backward on rejection)
wip_limits: per_column  # constrains parallelism
```

**Mapping insight**: Kanban maps to our meta-framework as a **continuous pull-based pipeline** with WIP limits controlling concurrency. Each column is a stage primitive, and items flow through based on capacity.

#### Spiral Model

```yaml
type: spiral
composition: iterative_with_risk_analysis
quadrant_stages:
  - planning           # → maps to "plan" primitive
  - risk_analysis      # → maps to "analyze" + "evaluate" primitives
  - engineering        # → maps to "design" + "impl" primitives
  - evaluation         # → maps to "review" + "test" primitives
loop: quadrants repeated with increasing scope/detail
termination: risk_level_acceptable AND requirements_met
```

**Mapping insight**: Spiral is risk-driven iteration. Each spiral pass is a Research-Design-Review-Refine workflow with increasing fidelity. This maps naturally to our RDRR workflow nested inside an outer loop.

### 6.2 Git Workflow Model Mapping

#### GitHub Flow

```yaml
type: github_flow
composition: branch_based_sequence
stages:
  - create_branch     # from main
  - implement         # commit changes
  - open_pr           # → maps to "review" request
  - review            # code review + CI checks
  - merge_deploy      # → maps to "release" (continuous deployment)
loops: review → implement (request changes → fix → re-review)
branching: main + short-lived feature branches
deployment: on merge to main (continuous)
```

**Agent workflow mapping**: GitHub Flow's simplicity maps directly to our Hotfix and Feature Enhancement workflows. The PR review cycle is a Quality Loop.

#### GitLab Flow

```yaml
type: gitlab_flow
composition: environment_branching
stages:
  - create_branch     # from main
  - implement
  - merge_to_main     # after review
  - deploy_staging     # main → pre-production branch
  - validate_staging
  - deploy_production  # pre-production → production branch
loops: validate_staging → fix → implement (if staging issues found)
branching: main + environment branches (staging, production)
```

**Agent workflow mapping**: GitLab Flow adds environment gates between our Test and Release stages. This maps to our TestGate concept — the staging deployment is an environment-based TestGate.

#### Trunk-Based Development

```yaml
type: trunk_based
composition: continuous_integration
stages:
  - implement          # small, focused changes
  - pre_commit_check   # lint, format, unit tests (<30s)
  - merge_to_trunk     # short-lived branch or direct commit
  - ci_pipeline        # full test suite + build
  - feature_flag_deploy # deploy behind feature flag
loops: ci_pipeline → fix → implement (if CI fails)
branching: trunk (main) + optional short-lived branches (<2 days)
```

**Agent workflow mapping**: TBD's emphasis on small changes and fast feedback maps to our Task-level granularity. Each Task in our Wave is essentially a TBD commit cycle.

### 6.3 CI/CD Pipeline-as-Code Patterns

#### GitHub Actions Jobs/Steps Model

GitHub Actions provides a declarative pipeline model:

```yaml
# GitHub Actions structure maps to our meta-framework
workflow:
  jobs:           # → maps to our Stages (parallel groups)
    build:
      steps:      # → maps to our Tasks (sequential within a Stage)
        - checkout
        - install
        - build
    test:
      needs: build  # → maps to our Stage dependencies
      steps:
        - unit_test
        - integration_test
    deploy:
      needs: test
      if: success()  # → maps to our Gate condition
      steps:
        - deploy_staging
        - smoke_test
        - deploy_production
```

**Key structural mappings**:
| GitHub Actions Concept | Our Meta-Framework Concept |
|----------------------|--------------------------|
| Workflow | Workflow Type (template) |
| Job | Stage |
| Step | Task |
| `needs:` | Stage dependency |
| `if:` condition | Gate condition |
| Matrix strategy | Wave (parallel execution) |
| Reusable workflow | Workflow template |
| Composite action | Reusable Task template |

### 6.4 Composition Primitives for Meta-Framework

Drawing from all sources, our meta-framework uses five composition primitives:

| Primitive | Description | Use Case | Example |
|-----------|-------------|----------|---------|
| **Sequence** | Execute stages A → B → C in order | Default composition for dependent stages | Design → Plan → Impl |
| **Parallel** | Execute stages A, B, C simultaneously | Independent stages that can run concurrently | Unit Tests ∥ Lint Check ∥ Security Scan |
| **Choice** | Execute A or B based on a condition | Conditional stage selection | if severity == SEV1: skip staging else: deploy to staging |
| **Loop** | Repeat stages until condition met | Review-Refine and Test-Fix cycles | repeat(Review → Refine) until quality_score ≥ 80% |
| **Gate** | Checkpoint that blocks or routes | Quality checkpoints between stages | TestGate: if all_pass → Release else → Refine |

**Composition example** — Full Pipeline expressed as primitive composition:

```yaml
full_pipeline:
  composition:
    - sequence:
        - stage: design
        - stage: plan
        - loop:
            name: implementation_cycle
            body:
              - sequence:
                  - stage: impl
                  - loop:
                      name: review_refine
                      body:
                        - stage: review
                        - choice:
                            if: review.pass
                            then: break
                            else:
                              - stage: refine
                      max_rounds: 3
                  - loop:
                      name: test_fix
                      body:
                        - parallel:
                            - stage: unit_test
                            - stage: lint_check
                            - stage: security_scan
                        - choice:
                            if: all_pass
                            then: break
                            else:
                              - stage: refine
                      max_rounds: 5
            max_rounds: 2
        - gate:
            name: testgate
            criteria:
              coverage: ">= 80%"
              tests: "all_pass"
              security: "no_critical"
            on_pass:
              - stage: release
            on_fail:
              - stage: refine
              - goto: implementation_cycle
```

### 6.5 Workflow Type Selection Heuristics

Based on analysis of all workflow types, the meta-framework can recommend workflow types based on task characteristics:

| Task Signal | Recommended Workflow | Confidence |
|-------------|---------------------|------------|
| "research", "compare", "evaluate", "survey" | research-only | High |
| "design", "architect", "API spec", "schema" | design-only or RDRR | High |
| "fix bug", "broken", "error in production" | hotfix | High |
| "refactor", "clean up", "tech debt", "improve code" | refactoring | High |
| "migrate", "upgrade", "move to", "replace" | migration | High |
| "try", "experiment", "is it possible", "prototype" | spike-poc | High |
| "document", "write docs", "update readme" | documentation-only | High |
| "security", "vulnerability", "audit", "CVE" | security-audit | High |
| "build from scratch", "new project", "implement feature" | full-pipeline | High |
| "add to existing", "extend", "enhance" | feature-enhancement | Medium |
| "slow", "performance", "optimize", "bottleneck" | performance-optimization | Medium |
| Ambiguous / multi-concern task | full-pipeline (safe default) | Low |

---

## 7. References

### SDLC Models and Methodologies

1. **Iterative and Incremental Development (IID) in Practice** — TheLinuxCode, 2026. Covers 4-phase IID structure (Inception, Elaboration, Construction, Refinement) with 1–3 week iteration cycles.
2. **SDLC Models Comparison Guide** — NumberAnalytics. Comprehensive comparison of Waterfall, V-Model, Agile, Spiral, and Iterative approaches with selection criteria.
3. **20 Software Development Life Cycle (SDLC) Models** — 8ration, 2026 Guide. Covers extended SDLC models including DevSecOps and Lean.
4. **Comparative Analysis of Software Development Methodologies** — EWADIRECT Proceedings. Academic comparison of major methodologies.
5. **Software Development Models Comparison** — EPAM Startups & SMBs. Practical comparison for team selection.

### Git Workflow Patterns

6. **Choosing the Right Branching Strategy** — Stefan Polyak, Medium. GitFlow vs TBD vs Release Flow vs GitLab Flow comparison.
7. **Git Workflow Strategies** — Lukas Niessen. GitHub Flow, GitLab Flow, GitFlow, and Trunk-Based Development analysis.
8. **Trunk-Based Development vs GitFlow** — BirJob, 2026. Current state of branching strategy debate.

### CI/CD Pipeline Patterns

9. **CI/CD Pipeline Design Patterns in 2026** — ZeonEdge. DAG model, stage architecture, quality gates.
10. **CI/CD Pipeline Testing Guide: Continuous Testing & Quality Gates** — HelpMeTest, 2026. Multi-tiered testing, feedback loop targets, quality gate enforcement.
11. **CI/CD Pipeline Design Principles** — TheLinuxCode, 2026. Fast feedback, reproducible releases, immutable artifacts.
12. **CI/CD Pipeline Best Practices** — ZTABS, 2026. Stage progression, security scanning integration.

### Specialized Workflow Patterns

13. **Hotfix Workflow** — SpecWeave. 7-stage hotfix process with severity-based routing and post-mortem requirements.
14. **How to Handle Hotfixes in a GitOps Workflow** — OneUptime, 2026. GitOps-specific hotfix patterns.
15. **The Technical Spike: A Framework for De-risking Unknowns** — Erwin Hermanto, Medium, 2026. Spike workflow with hypothesis-prototype-evaluate pattern.
16. **Engineering Feasibility Spikes** — Microsoft Engineering Playbook. Time-boxed spike methodology with pre-mortem and weekly feedback loops.
17. **Cloud Migration Step-by-Step** — AllDaysTech, 2025-2026. Wave-based migration with landing zones, 6Rs, and cutover strategies.
18. **Software Migrations: Complete 2026 Guide** — Ucodice. Planning, risks, and implementation patterns.
19. **Complete Web Application Security Audit Workflow** — InventiveHQ. Reconnaissance-to-remediation security audit stages.
20. **Secure SDLC: Map AppSec Tools to Each Phase** — AppSecSanta, 2026. Security testing integration across SDLC phases.

### Refactoring and Code Quality

21. **Beyond Generation: Plan-Implement-Refactor AI Coding Workflow** — Remio.ai. Multi-model AI refactoring with Architect/Builder/Inspector roles.
22. **Refactoring Patterns** — DeveloperToolkit.ai. 5-stage refactoring workflow (Analysis, Planning, Verification, Execution, Validation).

### Workflow Orchestration and Composition

23. **AI Agent Orchestration: LangGraph, Temporal & Custom Workflows** — dev.to, 2026. State machines, conditional edges, checkpointing, supervisor-worker patterns.
24. **Composition — Jido Composer v0.5.0** — HexDocs. Five composition primitives (Sequence, Parallel, Choice, Traverse, Identity) for composable workflows.
25. **Data Pipeline Orchestration Pattern** — AbstractAlgorithms.dev. DAG scheduling, retries, recovery, validation gates.

### Agent Workflow Frameworks

26. **CrewAI Documentation** — docs.crewai.com. Multi-agent task orchestration framework.
27. **AutoGen** — Microsoft. Multi-agent conversation framework.
28. **LangGraph** — LangChain. State machine-based agent orchestration.
29. **Anthropic Agent Design Patterns** — docs.anthropic.com. Agent patterns and best practices.

---

*Document generated: 2026-04-04 | Research status: Complete | Next: Integration into meta-framework design (Phase 7.5–7.7)*
