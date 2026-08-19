# User-Facing Testing & Product-to-Test-to-Feedback Research Report

**Task ID:** research-user-facing-testing  
**Date:** 2026-04-15  
**Scope:** Visual testing, acceptance testing, interaction testing, feedback loops, user-facing benchmarks  
**Target:** DevolaFlow v5.3.0 → v5.4.0 capability enhancement  

---

## 1. Executive Summary

DevolaFlow's current gate mechanism evaluates four dimensions: `test_quality` (0.30), `code_review` (0.30), `architecture` (0.20), and `benchmark` (0.20). All four are developer-side metrics. There is **no user-facing quality dimension** — no visual fidelity measurement, no interaction success tracking, no accessibility scoring, and no acceptance benchmark tied to user-visible behavior.

**Key findings across all five research areas:**

1. **Visual testing** has matured significantly: Playwright's `toHaveScreenshot()`, Applitools' Visual AI, and Percy's AI-powered triage provide production-grade screenshot regression at different cost/accuracy tradeoffs. The three comparison paradigms (pixel-diff, perceptual-diff, AI-based) each serve distinct use cases.

2. **Acceptance testing** frameworks (Cucumber/Gherkin, Behave, Robot Framework) provide well-established patterns for mapping user stories → acceptance criteria → executable tests. The BDD Given-When-Then structure creates "living specs" that bridge product and engineering.

3. **Interaction testing** requires layered coverage: E2E flows (Playwright/Cypress), accessibility checks (axe-core/Pa11y), and cross-browser validation. Automated tools catch ~30-50% of accessibility issues; the remaining require structured manual verification.

4. **Shift-left testing** integrated into product design phases reduces production defects by 60-90%. Quality gates at every stage — not just post-implementation — are the industry standard.

5. **User-perceived quality benchmarks** are an active research area. Frameworks like AppEvalPilot (0.92 accuracy vs. human judges), FineState-Bench, and FullFront measure visual fidelity, interaction success, and dynamic behavior — dimensions absent from most developer-side testing.

**Core recommendation:** Extend DevolaFlow's gate mechanism with three new verification dimensions — `visual_fidelity`, `interaction_quality`, and `acceptance_verification` — and add a new `verify` stage primitive for user-facing validation.

---

## 2. Area 1: Visual Testing / Screenshot Testing

### 2.1 Framework Landscape

| Framework | Approach | False Positive Rate | Cost | Best For |
|-----------|----------|-------------------|------|----------|
| **Playwright** | Pixel-diff (pixelmatch) | Medium (configurable via `maxDiffPixels`) | Free/OSS | Teams already using Playwright for E2E |
| **Applitools** | Visual AI (human-vision simulation) | Very Low | From $399/mo | Enterprise, high-accuracy needs |
| **Percy** (BrowserStack) | Pixel-diff + AI triage agent | Medium (improving) | From $199/mo | CI/CD-first teams, startups |
| **BackstopJS** | Pure pixel comparison | High (strict diffing) | Free/OSS | Open-source control, simple setups |
| **Cypress** | Plugin-based (percy-cypress, cypress-image-snapshot) | Varies by plugin | Free/OSS + plugin cost | Existing Cypress test suites |

### 2.2 Comparison Approaches

**Pixel-Diff (BackstopJS, Playwright default):**
- Exact pixel-by-pixel comparison using libraries like pixelmatch
- Pros: Deterministic, zero false negatives
- Cons: High false positive rate from anti-aliasing, sub-pixel rendering, font smoothing
- Configuration levers: `maxDiffPixels`, `maxDiffPixelRatio`, threshold tolerance

**Perceptual-Diff (Applitools Visual AI):**
- Simulates human visual perception; ignores sub-pixel artifacts, font rendering differences
- Pros: Very low false positive rate (5-10 flagged diffs per sprint vs. 50-100 with pixel-diff)
- Cons: Proprietary, paid, black-box comparison logic
- Key feature: "Intelli Ignore" for dynamic content regions

**AI-Based Triage (Percy Visual Review Agent, 2026):**
- Uses LLM/vision models to analyze flagged diffs and produce natural-language summaries
- Pros: Reduces human review time; OCR analysis detects text regressions; shift detection handles layout drifts
- Cons: Post-hoc (does not prevent false positives, manages them after detection)
- Key innovation: Natural-language diff summaries for non-technical stakeholders

### 2.3 Best Practices for CI/CD Integration

1. **Consistent rendering environment:** Run tests in identical environments (OS, browser version, display settings) to baseline capture. Docker containers are standard.
2. **Baseline management:** Store baselines in version control; update with explicit commands (`--update-snapshots`). Name with `{test}-{browser}-{platform}` convention.
3. **Element-level targeting:** Capture specific components rather than full pages to reduce noise and improve signal-to-noise ratio.
4. **Dynamic content masking:** Use CSS stylesheets (`stylePath` in Playwright) or region masking to exclude timestamps, ads, animations.
5. **Multi-browser baselines:** Maintain separate golden images per browser/platform combination; Playwright supports this natively.
6. **Threshold tuning:** Start strict (low `maxDiffPixels`), gradually relax based on false positive data.

### 2.4 DevolaFlow Integration Recommendations

- **New gate dimension: `visual_fidelity`** — scored 0-100 based on screenshot comparison pass rate across test suite.
- **Stage primitive usage:** Visual testing fits within the `test` and `validate` stage primitives.
- **Task agent tooling:** L3 Task Agents running visual tests need `Shell` (to execute Playwright/BackstopJS) and `Read` (to analyze diff reports).
- **Convergence integration:** Visual regression failures should generate findings with severity levels (blocker: layout break, critical: component misalignment, major: color/spacing drift, minor: sub-pixel variance).
- **CI artifact contract:** Visual test tasks produce `{test-name}-expected.png`, `{test-name}-actual.png`, `{test-name}-diff.png` as gate input artifacts.

---

## 3. Area 2: User-Facing / Acceptance Testing (UAT)

### 3.1 Framework Analysis

| Framework | Language | Syntax | Strength | Weakness |
|-----------|----------|--------|----------|----------|
| **Cucumber** | Multi-lang (Java, JS, Ruby) | Gherkin (Given-When-Then) | Industry standard BDD; 3-10 scenarios/feature file | Verbose for simple tests; step def maintenance |
| **Behave** | Python | Gherkin | Pythonic; direct mapping to Python steps | Smaller ecosystem than Cucumber |
| **Robot Framework** | Python | Keyword-driven tabular | ATDD-native; 50% faster business-facing test creation; 1.5M monthly downloads | Steeper initial learning curve for keyword design |

### 3.2 BDD and ATDD Patterns

**BDD (Behavior-Driven Development):**
- Workflow: User story → Acceptance criteria → Gherkin scenarios → Step definitions → Automation
- Feature files act as "living specifications" — executable documentation shared across product/engineering/QA
- Best practice: One feature file per capability, 3-10 scenarios per file, skimmable in under 2 minutes
- Tag-based execution (`@SmokeTest`, `@Regression`, `@UAT`) enables selective runs in CI

**ATDD (Acceptance Test-Driven Development):**
- Tests written *before* implementation based on acceptance criteria
- Robot Framework's keyword-driven approach: high-level business keywords compose low-level technical actions
- Structure: `Given [precondition keyword] → When [action keyword] → Then [verification keyword]`
- Key benefit: Non-technical stakeholders can read and validate test cases

### 3.3 User Story → Test Case Mapping

```
User Story: "As a user, I want to filter search results by date range"
  ↓
Acceptance Criteria:
  AC-1: Date picker allows selecting start and end dates
  AC-2: Results are filtered to show only items within range
  AC-3: Empty range shows "no results" message
  ↓
Gherkin Scenarios:
  Scenario: Filter by valid date range
    Given the search results page is loaded with 50 items
    When I set the date range to "2026-01-01" through "2026-03-31"
    Then only items within that date range are displayed
    And the result count updates to reflect the filter

  Scenario: Empty date range shows message
    Given the search results page is loaded
    When I set the date range to a period with no items
    Then the message "No results found for this date range" is displayed
```

### 3.4 Acceptance Benchmark Design

Acceptance benchmarks verify **user-visible behavior**, not code internals:

| Benchmark Type | Measures | Example |
|---------------|----------|---------|
| **Functional completeness** | % of acceptance criteria passing | 8/10 AC pass = 80% |
| **User flow success rate** | % of end-to-end user journeys completing | Login→Search→Filter→Export succeeds |
| **Error message quality** | Are error states user-comprehensible? | "File too large (max 10MB)" vs. "Error 413" |
| **State consistency** | Does UI reflect backend state correctly? | After deletion, item disappears from list |

### 3.5 DevolaFlow Integration Recommendations

- **New gate dimension: `acceptance_verification`** — scored based on acceptance criteria pass rate per stage.
- **Acceptance criteria as dispatch artifacts:** When dispatching implementation tasks, include Gherkin-format acceptance criteria as part of `acceptance_criteria` in TaskDispatch. Post-implementation, a verification task validates each criterion.
- **Acceptance Readiness Score (ARS) enhancement:** The existing ARS (testability, completeness, measurability, clarity, independence) is a *pre-work* gate. Add a post-work **Acceptance Verification Score (AVS)** that measures actual pass rate against defined criteria.
- **Stage primitive mapping:** `design` stage produces acceptance criteria → `implement` stage builds against them → `validate` stage runs acceptance tests → `gate` evaluates AVS.

---

## 4. Area 3: Interaction Testing

### 4.1 End-to-End User Flow Testing

**Framework Capabilities (2026):**

| Capability | Playwright | Cypress | Selenium |
|-----------|-----------|---------|----------|
| Click/type/navigate | Native | Native | Native |
| Multi-tab/multi-origin | Yes | Limited | Yes |
| File upload/download | Yes | Yes (with workarounds) | Yes |
| Network interception | Yes | Yes | Via proxy |
| API mocking | Yes | Yes | External |
| Visual assertions | Built-in `toHaveScreenshot()` | Plugin-based | External |
| Trace recording | Built-in trace viewer | Dashboard | External |

**Best practices for user flow tests:**
1. **Arrange-Act-Assert pattern:** Setup state → Perform user action → Verify visible outcome
2. **Realistic data:** Use factory patterns for test data, not hardcoded strings
3. **Resilient selectors:** Prefer `data-testid`, `role`, `label` over CSS classes or XPath
4. **Isolated flows:** Each test creates its own state; no test-to-test dependencies
5. **Timeout strategy:** Explicit waits for dynamic content; avoid fixed `sleep()` calls

### 4.2 Accessibility Testing Integration

**Automated tools and their coverage:**

| Tool | Coverage | Integration | Output |
|------|----------|-------------|--------|
| **axe-core** | ~30-50% of WCAG issues | Playwright (AxeBuilder), Cypress (cypress-axe), Jest | JSON violations with impact levels |
| **Pa11y** | ~30-50% of WCAG issues | CLI, Pa11y-CI for multi-URL | HTML/JSON reports |
| **Lighthouse** | Accessibility audit score | Chrome DevTools, CI via lighthouse-ci | Score 0-100 + violations |
| **Guidepup** | Screen reader simulation | Node.js API | Announcement log |

**Automated vs. Manual coverage:**
- **Automated catches:** Missing alt text, low contrast, missing labels, heading structure, ARIA roles
- **Manual required:** Cognitive load assessment, screen reader flow quality, keyboard navigation paths, meaningful alt text evaluation
- **Recommendation:** Automate structural checks in CI; schedule periodic manual audits

**Accessibility scoring for gates:**
- Use axe-core violation counts by impact (critical/serious/moderate/minor) mapped to finding severities
- Define threshold: zero critical/serious violations = pass; moderate/minor tracked as tech debt
- Lighthouse accessibility score ≥ 90 as gate threshold for web projects

### 4.3 Cross-Browser / Cross-Device Strategies

**Testing matrix approach:**
1. **Tier 1 (every PR):** Chrome latest + Firefox latest (desktop)
2. **Tier 2 (nightly):** Safari/WebKit + Edge + Chrome mobile
3. **Tier 3 (release):** Full matrix including older browser versions + real devices

**Key insight from research:** Real-browser testing (not emulators) is necessary for accurate results. Focus indicators, ARIA announcements, and font rendering vary across real browser engines in ways emulators miss.

### 4.4 CLI/Tool Testing from User Perspective

For non-web deliverables (CLIs, developer tools, scripts):

| Test Type | Approach | Example |
|-----------|----------|---------|
| **Command execution** | Shell subprocess with input/output capture | `tool --flag input.txt` produces expected output |
| **Error handling** | Invalid input → user-readable error | `tool --invalid` shows help, not stack trace |
| **Help/documentation** | `--help` output is complete and accurate | All flags documented; examples work |
| **Exit codes** | Correct codes for success/failure/error | 0 = success, 1 = user error, 2 = system error |
| **Interactive mode** | Scripted stdin for prompts | Automated responses to interactive prompts |

### 4.5 DevolaFlow Integration Recommendations

- **New gate dimension: `interaction_quality`** — composite of E2E flow pass rate, accessibility score, and cross-browser pass rate.
- **Interaction test task type:** Add `interaction_test` as a task type alongside existing `code`, `test`, `review`, `research` types. L3 agents dispatched for interaction testing receive browser/accessibility tool configuration.
- **Accessibility as gate input:** Extend `GateInput` with an `accessibility_results` field (score + violation counts by impact level).
- **CLI verification task type:** For tool/CLI projects, dispatch `cli_verification` tasks that test every command from the user's perspective.

---

## 5. Area 4: Product Design → Test → Feedback Loop

### 5.1 Shift-Left Testing Integration

**Research finding:** Organizations implementing shift-left testing achieve 60-90% production defect reductions and 40-60% cost-of-quality reductions (source: Total Shift Left, 2026 survey data).

**The shift-left test pyramid applied to DevolaFlow stages:**

```
Stage: design    → Acceptance criteria quality gate (ARS)
Stage: plan      → Test plan review (coverage mapping)
Stage: implement → Unit/integration tests written alongside code (TDD)
Stage: review    → Test adequacy review (coverage gaps, edge cases)
Stage: test      → Execution of all test levels
Stage: validate  → User-facing acceptance verification
Stage: gate      → Composite scoring across all dimensions
```

**Key practice: Test design during requirements.**
- Acceptance criteria must be testable *before* implementation begins
- ARS gate (already in DevolaFlow) enforces this, but currently only evaluates criteria quality — not whether corresponding tests exist

### 5.2 Leading Engineering Organization Patterns

**Google's approach (via DORA metrics):**
- Four key metrics: Deployment Frequency, Lead Time, Change Failure Rate, Time to Restore
- Product performance measured across: usability, functionality, value, availability, performance, security
- Developer experience treated as a first-class metric

**SPACE Framework (GitHub/Microsoft):**
- Five dimensions: Satisfaction, Performance, Activity, Communication & Collaboration, Efficiency & Flow
- Balances quantitative metrics (deploy frequency, bug rates) with qualitative developer experience

**Common patterns across high-performing orgs:**
1. Quality gates at every stage (automated, not manual)
2. Fast feedback loops (test results available within minutes, not hours)
3. Test pyramid enforcement (many unit, fewer integration, fewest E2E)
4. Metrics-driven improvement with dashboards visible to product + engineering

### 5.3 Feedback Loop Mechanisms

```
Design → Implement → Test → [Results] → Analyze → Iterate
                                 ↓
                        Findings classified:
                        • Functional failure → Fix in convergence
                        • Visual regression → Screenshot diff → Fix
                        • Acceptance gap → Criteria refinement
                        • Interaction failure → UX redesign
```

**Critical feedback loop properties:**
1. **Fast:** Results within minutes of code change (unit/lint/build), hours at most (E2E/visual)
2. **Specific:** Failure points to exact test, screenshot, or acceptance criterion
3. **Actionable:** Each finding includes suggested fix (not just "test failed")
4. **Traceable:** From production issue → test gap → design oversight → process improvement

### 5.4 DevolaFlow Integration Recommendations

- **Stage-level test design:** The `design` stage should output not just architecture/API specs, but also a test strategy document listing which acceptance criteria map to which test types (unit, integration, E2E, visual, accessibility).
- **Feedback artifact schema:** Define a `FeedbackReport` artifact schema that aggregates test results, visual diffs, accessibility violations, and acceptance pass rates into a single structured document. This feeds the convergence loop.
- **Quality metrics dashboard:** After each stage gate evaluation, produce a structured metrics summary covering both developer-side and user-facing dimensions.

---

## 6. Area 5: Benchmark Design for User-Facing Quality

### 6.1 Research Frameworks

| Framework | What It Measures | Key Metric | Accuracy vs. Humans |
|-----------|-----------------|------------|---------------------|
| **AppEvalPilot** (RealDevWorld) | Functional correctness + visual fidelity + runtime behavior | Three-dimension score via GUI interaction | 0.92 accuracy, 0.85 correlation |
| **FineState-Bench** | Fine-grained GUI interaction accuracy | Four-phase perception-to-control score | Best models achieve 32.8% |
| **FullFront** | Full frontend workflow | Design conceptualization + visual QA + code gen | Multi-stage evaluation |
| **WebVR** | Webpage recreation fidelity | Global aesthetics + section layout + interaction | Static 87%, dynamic 60% |
| **MobileGUIPerf** | User-perceived responsiveness | Response time + finish time (from screencast) | 0.96 precision, 89% within 50-100ms |

### 6.2 User-Facing Quality Dimensions

Based on research, a comprehensive user-facing quality benchmark should measure:

| Dimension | Description | Measurement Method | Weight |
|-----------|-------------|-------------------|--------|
| **Visual Fidelity** | Does the rendered output match the design spec? | Screenshot comparison against mockup (pixel/perceptual) | 0.25 |
| **Functional Completeness** | Do all acceptance criteria pass? | Automated acceptance test pass rate | 0.25 |
| **Interaction Success** | Do user flows complete correctly? | E2E test pass rate across defined user journeys | 0.20 |
| **Accessibility Compliance** | Does the output meet WCAG standards? | axe-core/Pa11y violation count + Lighthouse score | 0.15 |
| **Responsiveness** | Is the UI responsive within acceptable time? | Response time measurement (< 200ms for interaction feedback) | 0.10 |
| **Error UX Quality** | Are error states user-comprehensible? | Error message review + edge case test coverage | 0.05 |

### 6.3 Developer-Side vs. User-Facing Metrics Comparison

| Developer-Side (Current) | User-Facing (Proposed) |
|--------------------------|----------------------|
| Code coverage % | Acceptance criteria pass rate |
| Lint error count | Accessibility violation count |
| Build pass/fail | Visual fidelity score |
| Unit test pass rate | E2E interaction success rate |
| Architecture review score | User flow completion rate |
| Benchmark regression | Response time / perceived performance |

**Critical insight:** Developer-side metrics can be 100% green while user-facing quality is poor. A page can have 100% code coverage but broken layout. All unit tests pass but the CLI help text is misleading. Zero lint errors but WCAG-critical accessibility violations. **Both dimensions are necessary for comprehensive quality assessment.**

### 6.4 DevolaFlow Integration Recommendations

- **Extended gate composite formula:**

```
Current:  composite = test_quality×0.30 + code_review×0.30 + architecture×0.20 + benchmark×0.20
Proposed: composite = test_quality×0.20 + code_review×0.20 + architecture×0.15 + benchmark×0.15
                    + visual_fidelity×0.10 + interaction_quality×0.10 + acceptance_verification×0.10
```

- **User-facing benchmark scenarios:** Add to `benchmarks/devolaflow_context/scenarios/`:
  - `visual_regression_webapp.yaml` — web project visual testing scenario
  - `acceptance_verification_feature.yaml` — feature acceptance testing scenario
  - `cli_verification_tool.yaml` — CLI tool user-facing testing scenario

---

## 7. Consolidated Recommendations for DevolaFlow v5.4.0

### 7.1 New Gate Verification Dimensions

Add three user-facing dimensions to the gate mechanism:

| Dimension | Weight | Source | Gate Input Field |
|-----------|--------|--------|-----------------|
| `visual_fidelity` | 0.10 | Screenshot comparison results (pass rate, diff scores) | `visual_test_results: CheckResult` |
| `interaction_quality` | 0.10 | E2E flow pass rate + accessibility score | `interaction_results: CheckResult` |
| `acceptance_verification` | 0.10 | Acceptance criteria test pass rate | `acceptance_verification_results: CheckResult` |

Rebalance existing dimensions: `test_quality` 0.30→0.20, `code_review` 0.30→0.20, `architecture` 0.20→0.15, `benchmark` 0.20→0.15.

### 7.2 New/Enhanced Stage Primitive

Add a `verify` stage primitive (or enhance `validate`):

| Primitive | Category | Purpose | Default Team |
|-----------|----------|---------|-------------|
| **verify** | Verify | User-facing validation: visual tests, acceptance tests, interaction tests, accessibility checks | Test |

The `verify` primitive runs *after* `test` (developer-side) and *before* the final `gate`:

```
... → implement → test → review → verify → gate → release
```

Verify stage waves:
- **Wave 1:** Visual regression tests (screenshot capture + comparison)
- **Wave 2:** Acceptance verification (run Gherkin/Robot scenarios against acceptance criteria)
- **Wave 3:** Interaction testing (E2E user flows + accessibility audit)

### 7.3 Extended GateInput Model

```python
@dataclass
class GateInput:
    build_status: CheckResult
    test_results: CheckResult
    lint_status: CheckResult
    review_findings: list[Finding]
    acceptance_criteria_results: CheckResult | None = None
    acceptance_readiness_criteria: list[AcceptanceCriterionResult] = field(default_factory=list)
    # New user-facing fields
    visual_test_results: CheckResult | None = None
    interaction_test_results: CheckResult | None = None
    accessibility_results: CheckResult | None = None
    acceptance_verification_results: CheckResult | None = None
```

### 7.4 Task Types to Add

| Task Type | Dispatched By | Tools Needed | Artifact Output |
|-----------|--------------|-------------|-----------------|
| `visual_test` | L2 Wave Agent | Shell (Playwright/BackstopJS), Read | Screenshot diffs, pass/fail summary |
| `acceptance_test` | L2 Wave Agent | Shell (Cucumber/Behave/Robot), Read | Gherkin report, criteria pass matrix |
| `interaction_test` | L2 Wave Agent | Shell (Playwright E2E), Read | Flow results, accessibility report |
| `cli_verification` | L2 Wave Agent | Shell, Read | Command output validation report |

### 7.5 Workflow Template Updates

Update workflow templates to include verification stages:

| Template | Current Stages | Add |
|----------|---------------|-----|
| `full-pipeline` | design → plan → impl → review → test → refine → testgate → release | Add `verify` between `testgate` and `release` |
| `feature-enhancement` | scope → design → plan → impl → review → test → release | Add `verify` before `release` |
| `hotfix` | triage → fix → test → release | Add `verify` (lightweight: acceptance only) before `release` |

### 7.6 Gate Profile Enhancements

| Profile | Visual Fidelity Threshold | Interaction Quality Threshold | Accessibility Threshold |
|---------|--------------------------|------------------------------|------------------------|
| `strict` | ≥ 95% screenshot pass | ≥ 95% flow success | Lighthouse ≥ 95, zero critical a11y |
| `standard` | ≥ 90% screenshot pass | ≥ 90% flow success | Lighthouse ≥ 90, zero critical a11y |
| `relaxed` | ≥ 80% screenshot pass | ≥ 80% flow success | Lighthouse ≥ 80 |
| `audit` | ≥ 98% screenshot pass | ≥ 98% flow success | Lighthouse ≥ 95, zero serious+ a11y |

### 7.7 Context Profile for Verification Tasks

Add to `context_profiles.yaml`:

```yaml
verify_visual:
  token_budget: 8000
  critical_sections:
    - task_spec
    - visual_test_config
    - design_mockup_refs
  important_sections:
    - predecessor_summary
    - browser_config
  skip_sections:
    - architecture_ref
    - convergence_history

verify_acceptance:
  token_budget: 8000
  critical_sections:
    - task_spec
    - acceptance_criteria
    - user_story_ref
  important_sections:
    - predecessor_summary
    - test_framework_config
  skip_sections:
    - architecture_ref

verify_interaction:
  token_budget: 8000
  critical_sections:
    - task_spec
    - user_flow_definitions
    - accessibility_config
  important_sections:
    - predecessor_summary
    - browser_matrix
  skip_sections:
    - architecture_ref
```

---

## 8. Key Reference Frameworks Summary

### Visual Testing
1. **Playwright** — OSS, built-in `toHaveScreenshot()`, pixel-diff with configurable tolerance
2. **Applitools** — Proprietary Visual AI, lowest false positive rate, enterprise pricing
3. **Percy** (BrowserStack) — AI triage agent (2026), natural-language diff summaries
4. **BackstopJS** — OSS, pure pixel comparison, free, highest noise

### Acceptance Testing
1. **Cucumber** — Industry-standard BDD, Gherkin syntax, multi-language support
2. **Behave** — Python BDD, direct Gherkin-to-Python mapping
3. **Robot Framework** — Keyword-driven ATDD, 50% faster business-facing test creation
4. **Gauge** — Markdown-based specs, less Gherkin overhead

### Interaction & Accessibility
1. **Playwright** — Multi-browser E2E, built-in visual + API + network mocking
2. **Cypress** — Developer-friendly E2E, strong CI integration
3. **axe-core** — Industry-standard accessibility engine, lowest false positive rate
4. **Pa11y** — CLI accessibility testing, multi-URL scanning via Pa11y-CI

### Quality Metrics
1. **DORA** — Deployment frequency, lead time, change failure rate, MTTR
2. **SPACE** — Satisfaction, Performance, Activity, Communication, Efficiency
3. **AppEvalPilot** — GUI-based evaluation: functional + visual + runtime (0.92 accuracy)

---

## 9. Proposed Verification Dimensions for Gate Mechanism

### New Composite Formula

```
composite = (
    test_quality      × 0.20 +   # Unit/integration test pass rate + coverage
    code_review       × 0.20 +   # Review findings quality score
    architecture      × 0.15 +   # Architecture review + lint score
    benchmark         × 0.15 +   # Performance benchmark pass/regression
    visual_fidelity   × 0.10 +   # Screenshot comparison pass rate
    interaction_quality × 0.10 + # E2E flow success + accessibility score
    acceptance_verification × 0.10  # Acceptance criteria test pass rate
)
```

### Dimension Computation

**`visual_fidelity` (0-100):**
```
score = (screenshots_passing / screenshots_total) × 100
Penalty: -10 per layout-breaking diff, -5 per component misalignment, -1 per minor variance
```

**`interaction_quality` (0-100):**
```
e2e_score = (flows_passing / flows_total) × 100
a11y_score = max(0, 100 - (critical_violations×25 + serious×15 + moderate×5 + minor×1))
score = e2e_score × 0.60 + a11y_score × 0.40
```

**`acceptance_verification` (0-100):**
```
score = (acceptance_criteria_passing / acceptance_criteria_total) × 100
Blocker if any AC marked "must-pass" fails.
```

### Severity Mapping for User-Facing Findings

| Finding Type | Blocker | Critical | Major | Minor |
|-------------|---------|----------|-------|-------|
| Visual | Full layout break | Component misalignment | Color/spacing drift | Sub-pixel variance |
| Interaction | Flow cannot complete | Flow completes with error | Step requires workaround | Cosmetic during flow |
| Accessibility | Critical WCAG (no keyboard access) | Serious (missing labels) | Moderate (contrast) | Minor (best practice) |
| Acceptance | Must-pass AC fails | AC partially fails | AC edge case fails | AC non-functional fails |

---

## 10. Implementation Priority

| Priority | Item | Effort | Impact |
|----------|------|--------|--------|
| **P0** | Extend `GateInput` with user-facing fields | Small | Foundation for all other changes |
| **P0** | Add `visual_fidelity`, `interaction_quality`, `acceptance_verification` to scorer | Medium | Core capability |
| **P1** | Add `verify` stage primitive to workflow templates | Medium | Integrates into all workflows |
| **P1** | Add verification task types (`visual_test`, `acceptance_test`, `interaction_test`, `cli_verification`) | Medium | L3 agent capability |
| **P1** | Update gate profiles with user-facing thresholds | Small | Enforcement mechanism |
| **P2** | Add context profiles for verification tasks | Small | Context isolation |
| **P2** | Add benchmark scenarios for user-facing testing | Medium | EvoBench integration |
| **P3** | Design feedback artifact schema (`FeedbackReport`) | Medium | Closes feedback loop |
| **P3** | Update workflow template documentation | Small | Completeness |
