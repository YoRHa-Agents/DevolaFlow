// DevolaFlow Framework Architecture Data
// Maps current agent surfaces to their tier and runtime role.

const reference = (id, purpose, triggers) => ({
  id,
  path: `workflow-system/agent/references/${id}.md`,
  tier: 2,
  tokenEstimate: 2500,
  purpose,
  designSource: "Current agent contract",
  designSections: "Load the named reference only when its trigger applies.",
  triggers,
  relatedWorkflows: ["all 23 checklist seeds; sole change-driven runtime"],
});

const FRAMEWORK = {
  // ─── Tier 1: Entry Point ───────────────────────────────────────
  entry: {
    id: "SKILL.md",
    path: "workflow-system/agent/SKILL.md",
    tier: 1,
    lines: 425,
    tokenEstimate: 6000,
    purpose: "Tier-1 checklist-round entry point: 23 non-executable seeds, one change-driven runtime, and a three-layer Project → Wave → Task hierarchy.",
    designSource: "workflow-system/agent/SKILL.md",
    sections: [
      "Version & Update", "Workspace Engagement", "Quick Action Decision",
      "Mode Awareness", "Quick Start — Workflow Selection",
      "Repo-Init Pre-Dispatch Contract", "3-Layer Agent Hierarchy",
      "Seed Provenance Labels", "Gate Mechanism", "AgentTeam Quick Reference",
      "Context Isolation", "Subagent Hang Prevention",
      "Dispatch & Report Protocol", "Lifecycle Hooks", "Repo Mode Detection",
      "Reference Navigation Guide", "Task Quality Score"
    ],
    triggers: ["implement feature", "build from scratch", "fix bug", "refactor code", "migrate system", "full pipeline", "hotfix", "workflow orchestration"],
  },

  // ─── Tier 2: Domain References ─────────────────────────────────
  references: [
    reference("agent-hierarchy", "Three-layer Project → Wave → Task responsibilities and escalation.", ["delegating work", "checking layer boundaries"]),
    reference("agent-workspace", "Active-change folders, handoffs, archive, and ownership.", ["opening or resuming a change"]),
    reference("artifact-quality", "L2 evidence rubric; numeric scoring remains L0-only.", ["building or checking task evidence"]),
    reference("behavioral-guidelines", "Task behavior primitives and evidence attestations.", ["dispatching implementation or review"]),
    reference("codegraph", "Suggest-tier indexed discovery and degraded behavior.", ["exploring symbols or impact"]),
    reference("compression-pipeline", "Context compression and preservation rules.", ["building a bounded dispatch"]),
    reference("context-isolation", "5K/5K/8K budgets and leak prevention.", ["isolating task context"]),
    reference("decomposition-gate", "Checklist round, wave, task, convergence, and evidence gates.", ["partitioning or gating work"]),
    reference("degraded-mode", "Explicit fallback when optional capabilities are absent.", ["handling missing tools"]),
    reference("domain-awareness", "Glossary, contexts, and ADR decision boundaries.", ["resolving domain language"]),
    reference("env-flags", "Canonical runtime-flag inventory and reuse-first checks.", ["adding or inspecting a flag"]),
    reference("evaluator-rosetta", "Cross-walk among evaluator outputs.", ["interpreting evaluation evidence"]),
    reference("execution-protocol", "Preflight, checkpoints, failures, and bounded execution.", ["running or resuming work"]),
    reference("grill-mode", "One-question-at-a-time plan stress testing.", ["challenging a plan"]),
    reference("host-bridges", "Five-host boundary bridge, enforcement flag, and audit ledger.", ["wiring host hooks", "debugging a host-side deny"]),
    reference("human-surface", "Human-authored input and generated output contracts.", ["reading or writing human surfaces"]),
    reference("impeccable", "Visual-quality refinement and verification.", ["polishing user-facing design"]),
    reference("message-schemas", "Typed TaskDispatch, StatusReport, and escalation fields.", ["constructing inter-layer messages"]),
    reference("meta-framework", "Registry-v3 checklist seeds and sole runtime selection.", ["selecting a seed"]),
    reference("plan-mode-enforcement", "Goal, checklist, preflight, and approval contract.", ["planning before implementation"]),
    reference("repo-modes", "Repository capability detection and behavior.", ["detecting repository mode"]),
    reference("shell-proxy", "Shell routing and allowlist behavior.", ["routing bounded shell commands"]),
    reference("subagent-patterns", "Inline, fan-out, and forward-only pool selection.", ["choosing delegation topology"]),
    reference("task-quality-score", "L0-only, user-requested post-workflow request scoring.", ["scoring the completed request"]),
    reference("team-roles", "L2 research, design, implementation, test, and review roles.", ["assigning task specialization"]),
    reference("troubleshooting", "Installation and workflow failure diagnostics.", ["diagnosing a failure"]),
  ],

  // ─── Tier 3: On-Demand (Examples, Knowledge, Schemas) ─────────
  examples: [
    {
      id: "full-pipeline-trace",
      path: "workflow-system/agent/examples/full-pipeline-trace.md",
      tier: 3, tokenEstimate: 4500,
      purpose: "Checklist-round full-pipeline evidence walkthrough.",
      designSource: "Current execution example",
      relatedWorkflows: ["full-pipeline"],
    },
    {
      id: "hotfix-trace",
      path: "workflow-system/agent/examples/hotfix-trace.md",
      tier: 3, tokenEstimate: 2200,
      purpose: "Concise hotfix checklist and evidence walkthrough.",
      designSource: "Current execution example",
      relatedWorkflows: ["hotfix"],
    },
    {
      id: "multi-stage-trace",
      path: "workflow-system/agent/examples/multi-stage-trace.md",
      tier: 3, tokenEstimate: 3500,
      purpose: "Historical staged trace retained for provenance; not a current runtime.",
      designSource: "Historical compatibility example",
      relatedWorkflows: ["provenance only"],
    },
    {
      id: "convergence-loop-trace",
      path: "workflow-system/agent/examples/convergence-loop-trace.md",
      tier: 3, tokenEstimate: 3500,
      purpose: "Bounded convergence, evidence, and stagnation walkthrough.",
      designSource: "Current execution example",
      relatedWorkflows: ["implementation-class checklist items"],
    },
  ],

  knowledge: [
    {
      id: "index",
      path: "workflow-system/agent/knowledge/index.md",
      tier: 3, tokenEstimate: 500,
      purpose: "On-demand knowledge catalog.",
      designSource: "Knowledge navigation",
      relatedWorkflows: ["all"],
    },
    {
      id: "interview-protocol",
      path: "workflow-system/agent/knowledge/interview-protocol.md",
      tier: 3, tokenEstimate: 1200,
      purpose: "Bounded interview prompts and termination.",
      designSource: "Planning support",
      relatedWorkflows: ["plan and grill modes"],
    },
    {
      id: "code-rules-mapping",
      path: "workflow-system/agent/knowledge/code-rules-mapping.md",
      tier: 3, tokenEstimate: 2800,
      purpose: "How code rules load per language and task.",
      designSource: "code-rules system integration",
      relatedWorkflows: ["implementation and review tasks"],
    },
    {
      id: "principle-mapping",
      path: "workflow-system/agent/knowledge/principle-mapping.md",
      tier: 3, tokenEstimate: 2600,
      purpose: "Engineering principles mapped to checklist assertions and gate evidence.",
      designSource: "Software engineering principles",
      relatedWorkflows: ["implementation-class checklist items"],
    },
    {
      id: "reference-dependencies",
      path: "workflow-system/agent/knowledge/reference-dependencies.yaml",
      tier: 3, tokenEstimate: 800,
      purpose: "Machine-readable reference dependency map.",
      designSource: "Knowledge navigation",
      relatedWorkflows: ["all"],
    },
    {
      id: "runtime-plugins",
      path: "workflow-system/agent/knowledge/runtime-plugins.yaml",
      tier: 3, tokenEstimate: 900,
      purpose: "Canonical runtime plugin registration data.",
      designSource: "Plugin registry",
      relatedWorkflows: ["plugin-assisted tasks"],
    },
  ],

  // ─── Checklist seeds + sole runtime ────────────────────────────
  seeds: [
    { id: "hotfix", category: "build", focus: "triage, minimal fix, focused checks" },
    { id: "research-only", category: "discover", focus: "sources, comparison, report" },
    { id: "design-only", category: "shape", focus: "research, decisions, review" },
    { id: "documentation-only", category: "deliver", focus: "survey, authoring, review" },
    { id: "spike-poc", category: "discover", focus: "bounded prototype and verdict" },
    { id: "refactoring", category: "build", focus: "scope, regression safety, review" },
    { id: "feature-enhancement", category: "composite", focus: "design, implementation, release evidence" },
    { id: "full-pipeline", category: "composite", focus: "end-to-end delivery assertions" },
    { id: "performance-optimization", category: "build", focus: "profile, optimize, benchmark" },
    { id: "security-audit", category: "composite", focus: "threat model, scan, remediation" },
    { id: "research-design-review-refine", category: "composite", focus: "research, design, review, refinement" },
    { id: "dependency-setup", category: "build", focus: "setup and bounded verification" },
    { id: "onboarding", category: "discover", focus: "analysis, docs, setup" },
    { id: "demo-showcase", category: "composite", focus: "story, build, visual evidence" },
    { id: "product-verification", category: "composite", focus: "visual, interaction, accessibility, UAT" },
    { id: "entropy-cleanup", category: "control", focus: "scan, proposal, cleanup evidence" },
    { id: "migration", category: "build", focus: "migration, cutover, rollback readiness" },
    { id: "skill-optimization", category: "composite", focus: "measure, harness-evaluate, optimize" },
    { id: "self-update", category: "control", focus: "research, integration, evaluation" },
    { id: "nines-assisted", category: "composite", focus: "opaque historical compatibility ID; built-in harness evidence" },
    { id: "repo-init", category: "discover", focus: "canonical scaffold assertions" },
    { id: "change-driven", category: "composite", focus: "checklist knowledge plus runtime name" },
    { id: "web-design", category: "composite", focus: "design, implementation, deterministic checks" },
  ],
  runtime: {
    id: "change-driven",
    path: "workflow-system/agent/templates/builtin/change-driven.yaml",
    purpose: "Sole executable checklist-round lifecycle runtime.",
  },

  // ─── Adapters ──────────────────────────────────────────────────
  adapters: [
    { tool: "Cursor", format: "SKILL.md + references/ + rules.mdc", budget: "<500 lines", designSource: "design_delivery_architecture.md §4.4" },
    { tool: "Codex", format: "SKILL.md (rules inlined) + openai.yaml", budget: "<500 lines", designSource: "design_delivery_architecture.md §4.4" },
    { tool: "Claude Code", format: "CLAUDE.md (compressed)", budget: "<200 lines", designSource: "design_delivery_architecture.md §4.4" },
    { tool: "Copilot", format: "copilot-instructions.md", budget: "<4000 chars", designSource: "design_delivery_architecture.md §4.4" },
  ],

  // ─── Design Documents (Source of Truth) ────────────────────────
  designDocs: [
    { id: "desires", file: "desires.md", lines: 25, purpose: "Original requirements (9 core + 5 product form)" },
    { id: "wp1", file: "wp1_frameworks_research.md", lines: 704, purpose: "8 agent frameworks deep research" },
    { id: "wp2", file: "wp2_local_patterns.md", lines: 610, purpose: "13 local plan pattern analysis" },
    { id: "wp3", file: "wp3_workflow_types.md", lines: 993, purpose: "10 workflow type catalog" },
    { id: "synthesis", file: "research_synthesis_report.md", lines: 374, purpose: "10 key findings, framework scoring matrix" },
    { id: "hierarchy", file: "design_agent_hierarchy.md", lines: 1512, purpose: "Historical hierarchy research; current contract is Project → Wave → Task" },
    { id: "decomposition", file: "design_decomposition_gate.md", lines: 1859, purpose: "Decomposition rules, gate mechanism, failure handling" },
    { id: "execution", file: "design_execution_protocol.md", lines: 1613, purpose: "Pre-decision, checkpoint/resume, exception classification" },
    { id: "meta", file: "design_meta_framework.md", lines: 2132, purpose: "Historical taxonomy source; current registry exposes non-executable seeds" },
    { id: "repo", file: "design_repo_modes.md", lines: 838, purpose: "3 repo modes, feature matrix, CI/CD templates" },
    { id: "delivery", file: "design_delivery_architecture.md", lines: 975, purpose: "4-tool comparison, multi-level index, adapter pipeline, MVP spec" },
    { id: "dual", file: "design_dual_system.md", lines: 1097, purpose: "Agent/Human dual system, sync pipeline, VSCode plugin roadmap" },
  ],
};

// ─── Rendering ─────────────────────────────────────────────────────

const TIER_COLORS = { 1: "#9B4444", 2: "#B8860B", 3: "#5B7553" };
const TIER_LABELS = { 1: "Tier 1 — Entry (always loaded)", 2: "Tier 2 — Reference (per need)", 3: "Tier 3 — On-Demand" };
const CAT_COLORS = { discover: "#B8860B", shape: "#C49A3C", build: "#5B7553", verify: "#D4A843", deliver: "#9B4444", composite: "#495057", control: "#6c757d" };

function renderFrameworkOverview() {
  const el = document.getElementById("framework-diagram");
  el.innerHTML = `<pre class="mermaid">
graph TB
  subgraph design ["Design Documents (Source of Truth)"]
    desires["desires.md"]
    wp["wp1 + wp2 + wp3 (Research)"]
    synthesis["research_synthesis_report.md"]
    hierarchy["design_agent_hierarchy.md"]
    decomposition["design_decomposition_gate.md"]
    execution["design_execution_protocol.md"]
    meta["design_meta_framework.md"]
    repo["design_repo_modes.md"]
    delivery["design_delivery_architecture.md"]
    dual["design_dual_system.md"]
  end

  subgraph agent ["Agent Skill System"]
    skill["SKILL.md (Tier 1)"]
    refs["25 References (Tier 2)"]
    examples["4 Examples (Tier 3)"]
    knowledge["6 Knowledge (Tier 3)"]
    seeds["23 Non-Executable Seeds"]
    runtime["1 Runtime: change-driven"]
    schemas["7 Schemas"]
  end

  subgraph adapters ["Adapter Pipeline"]
    build["build-skill.py"]
    cursor["Cursor Output"]
    codex["Codex Output"]
    claude["Claude Output"]
    copilot["Copilot Output"]
  end

  subgraph human ["Human System"]
    en["EN Docs (8)"]
    zh["ZH Docs (8)"]
    demo["Interactive Demo"]
  end

  desires --> wp
  wp --> synthesis
  synthesis --> hierarchy
  hierarchy --> decomposition
  hierarchy --> execution
  synthesis --> meta
  hierarchy --> delivery
  hierarchy --> repo
  delivery --> dual

  hierarchy --> skill
  meta --> skill
  decomposition --> refs
  execution --> refs
  repo --> refs

  skill --> build
  refs --> build
  build --> cursor
  build --> codex
  build --> claude
  build --> copilot

  skill --> en
  refs --> en
  en --> zh
  seeds --> runtime
  runtime --> demo
</pre>`;
  if (window.mermaid) window.mermaid.run({ nodes: [el.querySelector(".mermaid")] });
}

function renderSkillFileList() {
  const el = document.getElementById("skill-files");
  let html = "";

  // Tier 1
  const e = FRAMEWORK.entry;
  html += `<div class="file-card tier1" data-file="${e.id}">
    <div class="file-header"><span class="tier-badge" style="background:${TIER_COLORS[1]}">T1</span><strong>${e.id}</strong><span class="token-badge">${e.tokenEstimate} tok</span></div>
    <p class="file-purpose">${e.purpose}</p>
    <div class="file-meta"><span class="design-ref">Design: ${e.designSource}</span></div>
    <div class="file-sections">${e.sections.map(s => `<span class="section-tag">${s}</span>`).join("")}</div>
  </div>`;

  // Tier 2
  html += `<h3 class="tier-heading">Tier 2 — Domain References <span class="count">${FRAMEWORK.references.length} files</span></h3>`;
  FRAMEWORK.references.forEach(r => {
    html += `<div class="file-card tier2" data-file="${r.id}">
      <div class="file-header"><span class="tier-badge" style="background:${TIER_COLORS[2]}">T2</span><strong>${r.id}.md</strong><span class="token-badge">${r.tokenEstimate} tok</span></div>
      <p class="file-purpose">${r.purpose}</p>
      <div class="file-meta">
        <span class="design-ref">Design: ${r.designSource}</span>
        <span class="design-sections">${r.designSections}</span>
      </div>
      <div class="file-triggers">Load when: ${r.triggers.map(t => `<span class="trigger-tag">${t}</span>`).join("")}</div>
      <div class="file-workflows">Workflows: <em>${r.relatedWorkflows.join(", ")}</em></div>
    </div>`;
  });

  // Tier 3
  html += `<h3 class="tier-heading">Tier 3 — Examples <span class="count">${FRAMEWORK.examples.length} files</span></h3>`;
  FRAMEWORK.examples.forEach(ex => {
    html += `<div class="file-card tier3" data-file="${ex.id}">
      <div class="file-header"><span class="tier-badge" style="background:${TIER_COLORS[3]}">T3</span><strong>${ex.id}.md</strong><span class="token-badge">${ex.tokenEstimate} tok</span></div>
      <p class="file-purpose">${ex.purpose}</p>
      <div class="file-meta"><span class="design-ref">Design: ${ex.designSource}</span></div>
      <div class="file-workflows">Workflows: <em>${ex.relatedWorkflows.join(", ")}</em></div>
    </div>`;
  });

  html += `<h3 class="tier-heading">Tier 3 — Knowledge <span class="count">${FRAMEWORK.knowledge.length} files</span></h3>`;
  FRAMEWORK.knowledge.forEach(k => {
    const fileName = k.path.split("/").pop();
    html += `<div class="file-card tier3" data-file="${k.id}">
      <div class="file-header"><span class="tier-badge" style="background:${TIER_COLORS[3]}">T3</span><strong>${fileName}</strong><span class="token-badge">${k.tokenEstimate} tok</span></div>
      <p class="file-purpose">${k.purpose}</p>
      <div class="file-workflows">Workflows: <em>${k.relatedWorkflows.join(", ")}</em></div>
    </div>`;
  });

  el.innerHTML = html;
}

function renderTemplateList() {
  const el = document.getElementById("template-list");
  let html = `<div class="template-card">
    <div class="template-header"><span class="cat-badge" style="background:${CAT_COLORS.control}">runtime</span><strong>${FRAMEWORK.runtime.id}</strong></div>
    <p>${FRAMEWORK.runtime.purpose}</p>
    <div class="template-design">${FRAMEWORK.runtime.path}</div>
  </div><div class="template-grid">`;
  FRAMEWORK.seeds.forEach(seed => {
    const color = CAT_COLORS[seed.category] || "#666";
    html += `<div class="template-card">
      <div class="template-header">
        <span class="cat-badge" style="background:${color}">${seed.category}</span>
        <strong>${seed.id}</strong>
      </div>
      <div class="template-meta">
        <span>non-executable seed</span>
      </div>
      <div class="template-design">${seed.focus}</div>
    </div>`;
  });
  html += `</div>`;
  el.innerHTML = html;
}

function renderAdapterList() {
  const el = document.getElementById("adapter-list");
  let html = `<div class="adapter-grid">`;
  FRAMEWORK.adapters.forEach(a => {
    html += `<div class="adapter-card">
      <strong>${a.tool}</strong>
      <p>${a.format}</p>
      <span class="budget-badge">Budget: ${a.budget}</span>
      <div class="adapter-design">Design: ${a.designSource}</div>
    </div>`;
  });
  html += `</div>`;
  el.innerHTML = html;
}

function renderDesignDocList() {
  const el = document.getElementById("design-doc-list");
  let html = `<table><thead><tr><th>Document</th><th>Lines</th><th>Purpose</th></tr></thead><tbody>`;
  FRAMEWORK.designDocs.forEach(d => {
    html += `<tr><td><strong>${d.file}</strong></td><td>${d.lines}</td><td>${d.purpose}</td></tr>`;
  });
  html += `</tbody></table>`;
  el.innerHTML = html;
}

function renderTokenBudget() {
  const el = document.getElementById("token-budget");
  const tier1 = FRAMEWORK.entry.tokenEstimate;
  const tier2 = FRAMEWORK.references.reduce((s, r) => s + r.tokenEstimate, 0);
  const tier3 = FRAMEWORK.examples.reduce((s, e) => s + e.tokenEstimate, 0) + FRAMEWORK.knowledge.reduce((s, k) => s + k.tokenEstimate, 0);
  const total = tier1 + tier2 + tier3;

  el.innerHTML = `
    <div class="budget-breakdown">
      <div class="budget-row"><span class="tier-badge" style="background:${TIER_COLORS[1]}">T1</span> Entry: <strong>${tier1}</strong> tokens (always loaded)</div>
      <div class="budget-row"><span class="tier-badge" style="background:${TIER_COLORS[2]}">T2</span> References: <strong>${tier2}</strong> tokens total (loaded per need)</div>
      <div class="budget-row"><span class="tier-badge" style="background:${TIER_COLORS[3]}">T3</span> On-Demand: <strong>${tier3}</strong> tokens total (loaded when needed)</div>
      <div class="budget-total">Total knowledge base: <strong>${total}</strong> tokens across ${1 + FRAMEWORK.references.length + FRAMEWORK.examples.length + FRAMEWORK.knowledge.length} files</div>
    </div>
    <div class="budget-bar">
      <div style="width:${(tier1/total*100).toFixed(0)}%;background:${TIER_COLORS[1]}" title="Tier 1: ${tier1}">T1</div>
      <div style="width:${(tier2/total*100).toFixed(0)}%;background:${TIER_COLORS[2]}" title="Tier 2: ${tier2}">T2</div>
      <div style="width:${(tier3/total*100).toFixed(0)}%;background:${TIER_COLORS[3]}" title="Tier 3: ${tier3}">T3</div>
    </div>`;
}

// ─── Tab navigation ────────────────────────────────────────────────
function showTab(tabId) {
  document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
  document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
  document.getElementById(tabId).classList.add("active");
  document.querySelector(`[data-tab="${tabId}"]`).classList.add("active");

  if (tabId === "tab-overview" && !document.querySelector("#framework-diagram .mermaid svg")) {
    renderFrameworkOverview();
  }
}

function syncPageCopy() {
  const seedTab = document.querySelector('[data-tab="tab-templates"]');
  const seedPanel = document.getElementById("tab-templates");
  const skillPanel = document.getElementById("tab-skills");
  const designPanel = document.getElementById("tab-design");

  seedTab.textContent = "Checklist Seeds + Runtime";
  seedPanel.querySelector("h2").textContent = "23 Non-Executable Seeds + One Runtime";
  seedPanel.querySelector("p").textContent =
    "Seeds retain decomposition knowledge and provenance only. change-driven is the sole executable checklist-round runtime.";
  skillPanel.querySelector("p").textContent =
    "Tier 1 is always loaded; the exact 25-reference Tier 2 catalog loads per need; Tier 3 knowledge and examples load on demand.";
  designPanel.querySelector("h2").textContent = "Design Documents (Historical Sources)";
  designPanel.querySelector("p").textContent =
    "Historical research remains traceable here; current behavior is defined by the agent contracts and registry-v3 runtime surfaces.";
}

document.addEventListener("DOMContentLoaded", () => {
  syncPageCopy();
  renderSkillFileList();
  renderTemplateList();
  renderAdapterList();
  renderDesignDocList();
  renderTokenBudget();
  renderFrameworkOverview();
});
