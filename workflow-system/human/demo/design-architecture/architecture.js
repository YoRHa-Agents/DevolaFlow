// DevolaFlow Framework Architecture Data
// Maps every skill file to its design source, tier, and associated workflows

const FRAMEWORK = {
  // ─── Tier 1: Entry Point ───────────────────────────────────────
  entry: {
    id: "SKILL.md",
    path: "workflow-system/agent/SKILL.md",
    tier: 1,
    lines: 429,
    tokenEstimate: 3100,
    purpose: "Entry point for the workflow orchestration skill. Loaded first on intent match. Contains compact section summaries with pointers to Tier-2 references. v9.0.0 PV-01 (v8.4.1) compressed PLAN MODE + Reinforcement Rules detail into references/plan-mode-enforcement.md; the v14.5.0 G-019 IA pass demoted Template Quick-Reference to references/meta-framework.md and tightened the ceremony sections (492 → 429 lines).",
    designSource: "design_delivery_architecture.md §3.4",
    sections: [
      "Version & Update", "Quick Action Decision", "Mode Awareness",
      "Overview", "Execution Model", "Stages", "Constraints Checklist",
      "Invariants", "Quick Start — Workflow Selection", "4-Layer Agent Hierarchy",
      "Stage Primitives Index", "Gate Mechanism", "AgentTeam Quick Reference",
      "Context Isolation", "Dispatch & Report Protocol", "Lifecycle Hooks",
      "Repo Mode Detection", "Reference Navigation Guide", "Task Quality Score"
    ],
    triggers: ["implement feature", "build from scratch", "fix bug", "refactor code", "migrate system", "full pipeline", "hotfix", "workflow orchestration"],
  },

  // ─── Tier 2: Domain References ─────────────────────────────────
  references: [
    {
      id: "agent-hierarchy",
      path: "workflow-system/agent/references/agent-hierarchy.md",
      tier: 2, tokenEstimate: 3200,
      purpose: "4-layer hierarchy with full specs, delegation rules, per-layer MUST/MUST NOT, context budgets, message flow.",
      designSource: "design_agent_hierarchy.md",
      designSections: "§2 (4-Layer Hierarchy), §3 (Communication Protocol), §6 (Context Isolation), §7 (Delegation Examples)",
      triggers: ["setting up agent hierarchy", "debugging delegation", "understanding layer roles"],
      relatedWorkflows: ["all — defines the execution model for every workflow"],
    },
    {
      id: "meta-framework",
      path: "workflow-system/agent/references/meta-framework.md",
      tier: 2, tokenEstimate: 4500,
      purpose: "13 stage primitives with I/O contracts, dependency lattice, 5 composition operators, BNF grammar, composition patterns.",
      designSource: "design_meta_framework.md",
      designSections: "§2 (Primitives), §3 (Composability), §4 (Template Schema), §5 (Registry), §6 (Auto-Recommendation)",
      triggers: ["understanding stage primitives", "designing workflow composition", "template authoring"],
      relatedWorkflows: ["all — defines what stages exist and how they compose"],
    },
    {
      id: "decomposition-gate",
      path: "workflow-system/agent/references/decomposition-gate.md",
      tier: 2, tokenEstimate: 4200,
      purpose: "Stage/Wave/Task decomposition rules, gate quality mechanism (composite score, profiles, convergence), failure handling chain.",
      designSource: "design_decomposition_gate.md",
      designSections: "§2 (Stage Rules), §3 (Wave Rules), §4 (Task Rules), §5 (Gate Mechanism), §6 (Dependency Matrix), §7 (Failure Chain)",
      triggers: ["decomposing work into stages/waves/tasks", "evaluating gate quality", "handling failures"],
      relatedWorkflows: ["full-pipeline", "feature-enhancement", "refactoring", "migration", "security-audit"],
    },
    {
      id: "repo-modes",
      path: "workflow-system/agent/references/repo-modes.md",
      tier: 2, tokenEstimate: 3000,
      purpose: "3 repository modes (local/github/other-git), feature matrix, detection logic, CI/CD pipeline templates.",
      designSource: "design_repo_modes.md",
      designSections: "§1 (Mode Definitions), §2 (Feature Matrix), §3 (Detection Logic), §4 (Pipeline Templates)",
      triggers: ["detecting repository mode", "configuring mode-specific features", "setting up CI/CD"],
      relatedWorkflows: ["all — determines release/deploy behavior per mode"],
    },
    {
      id: "execution-protocol",
      path: "workflow-system/agent/references/execution-protocol.md",
      tier: 2, tokenEstimate: 3800,
      purpose: "Pre-decision phase, checkpoint/resume mechanism, exception severity classification, human intervention breakpoints.",
      designSource: "design_execution_protocol.md",
      designSections: "§2 (Pre-Decision), §3 (Information Collection), §4 (Checkpoint/Resume), §5 (Exception Classification), §6 (Human Breakpoints), §7 (Execution Log)",
      triggers: ["running pre-decision phase", "checkpoint management", "handling exceptions", "resuming workflow"],
      relatedWorkflows: ["full-pipeline", "feature-enhancement — pre-decision is universal"],
    },
    {
      id: "message-schemas",
      path: "workflow-system/agent/references/message-schemas.md",
      tier: 2, tokenEstimate: 3500,
      purpose: "Full YAML schemas for TaskDispatch, StatusReport, ExceptionEscalation with field docs and examples.",
      designSource: "design_agent_hierarchy.md §3",
      designSections: "§3.1 (TaskDispatch), §3.2 (StatusReport), §3.3 (ExceptionEscalation)",
      triggers: ["constructing dispatch messages", "parsing status reports", "handling escalations"],
      relatedWorkflows: ["all — messages are the inter-layer communication protocol"],
    },
    {
      id: "team-roles",
      path: "workflow-system/agent/references/team-roles.md",
      tier: 2, tokenEstimate: 4500,
      purpose: "5 AgentTeam specifications (Research/Design/Implement/Test/Review) with I/O contracts, quality criteria, handoff protocol.",
      designSource: "design_agent_hierarchy.md §4-§5",
      designSections: "§4.1 (Research), §4.2 (Design), §4.3 (Implement), §4.4 (Test), §4.5 (Review), §5 (Handoff Protocol)",
      triggers: ["configuring task agents", "understanding team capabilities", "setting up handoff protocols"],
      relatedWorkflows: ["all — teams are assigned to stages via the workflow template"],
    },
    {
      id: "context-isolation",
      path: "workflow-system/agent/references/context-isolation.md",
      tier: 2, tokenEstimate: 2800,
      purpose: "Context isolation principles, injection template, what must NOT leak between agents, budget management by layer.",
      designSource: "design_agent_hierarchy.md §6",
      designSections: "§6.1 (Principles), §6.2 (Isolated Windows), §6.3 (Injection Template), §6.4 (Leak Prevention), §6.5 (Budget Management)",
      triggers: ["setting up context injection", "debugging context leaks", "configuring agent budgets"],
      relatedWorkflows: ["all — context isolation is a cross-cutting invariant"],
    },
  ],

  // ─── Tier 3: On-Demand (Examples, Knowledge, Schemas) ─────────
  examples: [
    {
      id: "full-pipeline-trace",
      path: "workflow-system/agent/examples/full-pipeline-trace.md",
      tier: 3, tokenEstimate: 4500,
      purpose: "Complete delegation chain walkthrough: 18 agents, 7 stages, all 6 message types.",
      designSource: "design_agent_hierarchy.md §7.1",
      relatedWorkflows: ["full-pipeline"],
    },
    {
      id: "hotfix-trace",
      path: "workflow-system/agent/examples/hotfix-trace.md",
      tier: 3, tokenEstimate: 2200,
      purpose: "Minimal 4-stage hotfix workflow trace: 5 agents, rapid triage-to-release.",
      designSource: "design_agent_hierarchy.md §7.2",
      relatedWorkflows: ["hotfix"],
    },
    {
      id: "convergence-loop-trace",
      path: "workflow-system/agent/examples/convergence-loop-trace.md",
      tier: 3, tokenEstimate: 3500,
      purpose: "8-phase convergence round with 2-round example, gate scoring, stagnation detection.",
      designSource: "design_agent_hierarchy.md Appendix C, design_decomposition_gate.md §5",
      relatedWorkflows: ["full-pipeline", "refactoring", "migration", "security-audit", "feature-enhancement"],
    },
  ],

  knowledge: [
    {
      id: "code-rules-mapping",
      path: "workflow-system/agent/knowledge/code-rules-mapping.md",
      tier: 3, tokenEstimate: 2800,
      purpose: "How code rules load per-language/per-task during implement and review stages.",
      designSource: "code-rules system integration",
      relatedWorkflows: ["full-pipeline", "hotfix", "refactoring", "feature-enhancement"],
    },
    {
      id: "principle-mapping",
      path: "workflow-system/agent/knowledge/principle-mapping.md",
      tier: 3, tokenEstimate: 2600,
      purpose: "SOLID/TDD/Clean Architecture/DDD mapped to workflow stages and gate dimensions.",
      designSource: "Software engineering principles",
      relatedWorkflows: ["full-pipeline", "feature-enhancement"],
    },
  ],

  // ─── Templates ─────────────────────────────────────────────────
  templates: [
    { id: "full-pipeline", stages: 8, category: "composite", gateType: "convergence", designSource: "design_meta_framework.md §7.2" },
    { id: "hotfix", stages: 4, category: "build", gateType: "standard", designSource: "design_meta_framework.md §4.4 Ex2" },
    { id: "research-only", stages: 3, category: "discover", gateType: "standard", designSource: "design_meta_framework.md §4.4 Ex1" },
    { id: "research-design-review-refine", stages: 5, category: "composite", gateType: "convergence", designSource: "design_meta_framework.md §7.1" },
    { id: "design-only", stages: 3, category: "shape", gateType: "standard", designSource: "design_decomposition_gate.md §2.6" },
    { id: "refactoring", stages: 5, category: "build", gateType: "convergence", designSource: "design_decomposition_gate.md §2.6" },
    { id: "migration", stages: 5, category: "build", gateType: "convergence", designSource: "design_decomposition_gate.md §2.6" },
    { id: "spike-poc", stages: 3, category: "discover", gateType: "standard", designSource: "design_decomposition_gate.md §2.6" },
    { id: "documentation-only", stages: 3, category: "deliver", gateType: "standard", designSource: "design_decomposition_gate.md §2.6" },
    { id: "security-audit", stages: 5, category: "verify", gateType: "convergence", designSource: "design_decomposition_gate.md §2.6" },
    { id: "feature-enhancement", stages: 7, category: "composite", gateType: "convergence", designSource: "design_decomposition_gate.md §2.6" },
    { id: "demo-showcase", stages: 6, category: "composite", gateType: "convergence", designSource: "design_decomposition_gate.md §2.6" },
    { id: "performance-optimization", stages: 5, category: "build", gateType: "convergence", designSource: "design_decomposition_gate.md §2.6" },
    { id: "dependency-setup", stages: 4, category: "build", gateType: "convergence", designSource: "design_decomposition_gate.md §2.6" },
    { id: "onboarding", stages: 4, category: "discover", gateType: "standard", designSource: "design_decomposition_gate.md §2.6" },
    { id: "skill-optimization", stages: 5, category: "composite", gateType: "convergence", designSource: "design_decomposition_gate.md §2.6" },
    { id: "self-update", stages: 6, category: "composite", gateType: "convergence", designSource: "design_decomposition_gate.md §2.6" },
  ],

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
    { id: "hierarchy", file: "design_agent_hierarchy.md", lines: 1512, purpose: "4-layer hierarchy, 5 teams, communication, context isolation" },
    { id: "decomposition", file: "design_decomposition_gate.md", lines: 1859, purpose: "Decomposition rules, gate mechanism, failure handling" },
    { id: "execution", file: "design_execution_protocol.md", lines: 1613, purpose: "Pre-decision, checkpoint/resume, exception classification" },
    { id: "meta", file: "design_meta_framework.md", lines: 2132, purpose: "13 primitives, 5 operators, template schema, registry, auto-recommendation" },
    { id: "repo", file: "design_repo_modes.md", lines: 838, purpose: "3 repo modes, feature matrix, CI/CD templates" },
    { id: "delivery", file: "design_delivery_architecture.md", lines: 975, purpose: "4-tool comparison, multi-level index, adapter pipeline, MVP spec" },
    { id: "dual", file: "design_dual_system.md", lines: 1097, purpose: "Agent/Human dual system, sync pipeline, VSCode plugin roadmap" },
  ],
};

// ─── Rendering ─────────────────────────────────────────────────────

const TIER_COLORS = { 1: "#9B4444", 2: "#B8860B", 3: "#5B7553" };
const TIER_LABELS = { 1: "Tier 1 — Entry (always loaded)", 2: "Tier 2 — Reference (per-stage)", 3: "Tier 3 — On-Demand" };
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
    refs["8 References (Tier 2)"]
    examples["3 Examples (Tier 3)"]
    knowledge["2 Knowledge (Tier 3)"]
    templates["17 Templates (YAML)"]
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
  templates --> demo
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
    html += `<div class="file-card tier3" data-file="${k.id}">
      <div class="file-header"><span class="tier-badge" style="background:${TIER_COLORS[3]}">T3</span><strong>${k.id}.md</strong><span class="token-badge">${k.tokenEstimate} tok</span></div>
      <p class="file-purpose">${k.purpose}</p>
      <div class="file-workflows">Workflows: <em>${k.relatedWorkflows.join(", ")}</em></div>
    </div>`;
  });

  el.innerHTML = html;
}

function renderTemplateList() {
  const el = document.getElementById("template-list");
  let html = `<div class="template-grid">`;
  FRAMEWORK.templates.forEach(t => {
    const color = CAT_COLORS[t.category] || "#666";
    html += `<div class="template-card">
      <div class="template-header">
        <span class="cat-badge" style="background:${color}">${t.category}</span>
        <strong>${t.id}</strong>
      </div>
      <div class="template-meta">
        <span>${t.stages} stages</span>
        <span>gate: ${t.gateType}</span>
      </div>
      <div class="template-design">Design: ${t.designSource}</div>
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
      <div class="budget-row"><span class="tier-badge" style="background:${TIER_COLORS[2]}">T2</span> References: <strong>${tier2}</strong> tokens total (1-2 loaded per stage)</div>
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

document.addEventListener("DOMContentLoaded", () => {
  renderSkillFileList();
  renderTemplateList();
  renderAdapterList();
  renderDesignDocList();
  renderTokenBudget();
  renderFrameworkOverview();
});
