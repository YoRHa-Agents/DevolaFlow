const STAGES = {
  research: {
    category: "Discover", team: "Research", duration: "Medium-Long",
    purpose: "Gather information, survey prior art, benchmark alternatives, identify constraints",
    input: "ResearchRequest { question, scope[], criteria[], source_hints[] }",
    output: "ResearchReport { findings[], comparison_matrix, risk_assessment[], knowledge_gaps[] }",
    config: "depth: shallow|standard|comprehensive, source_types: [web, repo, paper, docs]",
    workflows: "research-only, design-only, RDRR, migration, spike-poc, full-pipeline (optional)",
  },
  analyze: {
    category: "Discover", team: "Research", duration: "Medium",
    purpose: "Examine existing artifacts (code, metrics, logs) to produce structured assessments",
    input: "AnalyzeRequest { targets[], analysis_type, baseline_metrics? }",
    output: "AnalysisReport { findings[], hotspots[], priority_ranking[] }",
    config: "analysis_type: code|performance|security|dependency, severity_threshold",
    workflows: "hotfix (as bug-triage), security-audit (as scan/analyze), refactoring (as scope)",
  },
  design: {
    category: "Shape", team: "Design", duration: "Medium-Long",
    purpose: "Synthesize inputs into architecture, API spec, schema, or system specification",
    input: "DesignRequest { inputs[], constraints[], quality_requirements[] }",
    output: "DesignDocument { diagrams[], interfaces[], decisions[], specification }",
    config: "design_type: architecture|api|schema|component, formality: sketch|standard|formal",
    workflows: "design-only, RDRR, full-pipeline, feature-enhancement",
  },
  plan: {
    category: "Shape", team: "Design", duration: "Medium",
    purpose: "Decompose a design into implementable work units with ordering and dependencies",
    input: "PlanRequest { design, capacity_constraints?, priority_rules[] }",
    output: "ImplementationPlan { waves[], dependency_matrix, risk_register[], acceptance_criteria[] }",
    config: "granularity: coarse|standard|fine, max_parallel_waves, estimate_unit",
    workflows: "full-pipeline, refactoring, migration, feature-enhancement",
  },
  implement: {
    category: "Build", team: "Implement", duration: "Long",
    purpose: "Execute plan tasks: write code, create tests, build config, produce artifacts",
    input: "ImplRequest { tasks[], code_rules[], language_conventions[], existing_code_context[] }",
    output: "ImplResult { artifacts[], files_changed[], tests_written[], build_status }",
    config: "test_strategy: tdd|test_after|no_test, target_coverage: float",
    workflows: "full-pipeline, hotfix (as fix), refactoring, migration, feature-enhancement",
  },
  review: {
    category: "Verify", team: "Review", duration: "Medium",
    purpose: "Evaluate artifacts against quality criteria, standards, and requirements",
    input: "ReviewRequest { artifacts[], checklist, acceptance_criteria[], review_type }",
    output: "ReviewVerdict { decision: pass|revise|reject, score, findings[], blocking_count }",
    config: "review_type: design|code|security|documentation, pass_threshold: 0.80",
    workflows: "All workflows with quality gates (most common stage)",
  },
  test: {
    category: "Verify", team: "Test", duration: "Medium",
    purpose: "Execute automated test suites and produce structured results",
    input: "TestRequest { code_refs[], test_suites[], coverage_threshold }",
    output: "TestResult { suite_results[], pass_rate, coverage, failures[] }",
    config: "suites: [unit, integration, e2e], fail_fast: bool, timeout_per_suite",
    workflows: "full-pipeline, hotfix, refactoring, feature-enhancement, security-audit (as verify)",
  },
  validate: {
    category: "Verify", team: "Review", duration: "Quick",
    purpose: "Aggregate review + test results into a readiness verdict",
    input: "ValidateRequest { review_verdict?, test_result?, acceptance_criteria[] }",
    output: "ValidationReport { ready: bool, unmet_criteria[], gap_analysis[] }",
    config: "require_all_criteria: bool, allow_waivers: bool",
    workflows: "full-pipeline (as testgate), migration",
  },
  refine: {
    category: "Build", team: "Implement", duration: "Medium",
    purpose: "Address findings from review/test/validate -- fix bugs, resolve comments",
    input: "RefineRequest { findings[], original_artifacts[], refine_scope }",
    output: "RefineResult { updated_artifacts[], changelog[], unresolved[] }",
    config: "scope: targeted|broad, allow_new_features: false",
    workflows: "full-pipeline, RDRR, feature-enhancement (in convergence loops)",
  },
  release: {
    category: "Deliver", team: "Implement", duration: "Quick-Medium",
    purpose: "Package, tag, and publish artifacts -- create releases, update changelogs",
    input: "ReleaseRequest { artifacts[], version_strategy, changelog_template? }",
    output: "ReleaseRecord { version, tag, changelog, artifacts_published[] }",
    config: "version_strategy: semver|calver, require_human_approval: bool",
    workflows: "full-pipeline, hotfix, feature-enhancement",
  },
  deploy: {
    category: "Deliver", team: "Implement", duration: "Medium",
    purpose: "Deploy released artifacts to target environments",
    input: "DeployRequest { release, environment, strategy, rollback_plan }",
    output: "DeployResult { status: success|failed|rolled_back, health_check }",
    config: "strategy: rolling|blue_green|canary, auto_rollback_on_failure: bool",
    workflows: "full-pipeline (optional), GitHub/GitLab mode only",
  },
  monitor: {
    category: "Deliver", team: "Test", duration: "Long",
    purpose: "Post-deploy observation -- watch metrics, detect anomalies, confirm stability",
    input: "MonitorRequest { deployment, watch_metrics[], anomaly_thresholds[] }",
    output: "MonitorReport { status: stable|degraded|critical, recommendation }",
    config: "duration_minutes, check_interval_seconds, alert_on_degraded: bool",
    workflows: "full-pipeline (optional, post-deploy verification)",
  },
  gate: {
    category: "Control", team: "(Orchestrator)", duration: "Quick",
    purpose: "Explicit quality checkpoint that blocks progression unless criteria are met",
    input: "GateRequest { criteria[], inputs }",
    output: "GateResult { passed: bool, criteria_results[], blocking_failures[] }",
    config: "on_fail: loop_back|escalate|block, require_human_override: bool",
    workflows: "All workflows (auto-inserted between stages by template policy)",
  },
};

const TEAM_COLORS = {
  Research: "#6f42c1", Design: "#0d6efd", Implement: "#198754",
  Test: "#fd7e14", Review: "#dc3545", "(Orchestrator)": "#6c757d",
};

const CTX_BUDGETS = { Project: 3000, Stage: 5000, Wave: 4000, Task: 8000 };

function renderStage(key) {
  const s = STAGES[key];
  if (!s) return;

  document.getElementById("stage-name").textContent = key;
  document.getElementById("stage-category").textContent = s.category;
  document.getElementById("stage-team").textContent = s.team;
  document.getElementById("stage-team").style.color = TEAM_COLORS[s.team] || "inherit";
  document.getElementById("stage-duration").textContent = s.duration;
  document.getElementById("stage-purpose").textContent = s.purpose;
  document.getElementById("stage-input").textContent = s.input;
  document.getElementById("stage-output").textContent = s.output;
  document.getElementById("stage-config").textContent = s.config;
  document.getElementById("stage-workflows").textContent = s.workflows;

  const chain = document.getElementById("delegation-chain");
  chain.innerHTML = `
    <div class="chain-layer" style="border-left:3px solid #6f42c1">
      <strong>Project Agent</strong> <span class="budget">~3K tokens</span><br>
      <small>dispatches stage, never reads source code</small>
    </div>
    <div class="chain-arrow">|</div>
    <div class="chain-layer" style="border-left:3px solid #0d6efd">
      <strong>Stage Agent: ${key}</strong> <span class="budget">~5K tokens</span><br>
      <small>decomposes into waves, runs quality gate</small>
    </div>
    <div class="chain-arrow">|</div>
    <div class="chain-layer" style="border-left:3px solid #198754">
      <strong>Wave Agent</strong> <span class="budget">~4K tokens</span><br>
      <small>dispatches up to 5 tasks in parallel</small>
    </div>
    <div class="chain-arrow">|</div>
    <div class="chain-layer" style="border-left:3px solid #dc3545">
      <strong>Task Agent (${s.team} team)</strong> <span class="budget">~8K tokens</span><br>
      <small>executes work using tools -- the ONLY layer that acts</small>
    </div>
  `;

  const budgetBar = document.getElementById("budget-bar");
  const total = Object.values(CTX_BUDGETS).reduce((a, b) => a + b, 0);
  budgetBar.innerHTML = Object.entries(CTX_BUDGETS).map(([layer, tokens]) => {
    const pct = (tokens / total * 100).toFixed(0);
    const colors = { Project: "#6f42c1", Stage: "#0d6efd", Wave: "#198754", Task: "#dc3545" };
    return `<div class="budget-segment" style="width:${pct}%;background:${colors[layer]}" title="${layer}: ~${tokens} tokens">${layer}</div>`;
  }).join("");
}

document.addEventListener("DOMContentLoaded", () => {
  const sel = document.getElementById("stage-select");
  Object.keys(STAGES).forEach(k => {
    const opt = document.createElement("option");
    opt.value = k;
    opt.textContent = `${k} (${STAGES[k].category})`;
    sel.appendChild(opt);
  });
  sel.addEventListener("change", () => renderStage(sel.value));
  sel.value = "implement";
  renderStage("implement");
});
