const WORKFLOWS = {
  "full-pipeline": {
    name: "Full Pipeline",
    description: "Complete development lifecycle from design through release with review and test gates. The maximal workflow type.",
    stages: [
      { id: "design", label: "Design", team: "Design", gate: "standard" },
      { id: "plan", label: "Plan", team: "Design", gate: "standard" },
      { id: "implement", label: "Implement", team: "Implement", gate: "convergence" },
      { id: "review", label: "Review", team: "Review", gate: null },
      { id: "test", label: "Test", team: "Test", gate: null },
      { id: "refine", label: "Refine", team: "Implement", gate: null },
      { id: "testgate", label: "TestGate", team: "Review", gate: "passthrough" },
      { id: "release", label: "Release", team: "Implement", gate: "standard" },
    ],
    loops: ["impl->review->refine (max 3)", "test->refine (max 5)"],
    category: "composite",
    useWhen: "Greenfield features, new projects, major system changes",
  },
  "hotfix": {
    name: "Hotfix",
    description: "Rapid incident response: triage, minimal fix, focused test, fast-track release. Optimized for speed.",
    stages: [
      { id: "bug_triage", label: "Bug Triage", team: "Implement", gate: "standard" },
      { id: "fix", label: "Fix", team: "Implement", gate: "standard" },
      { id: "test", label: "Test", team: "Test", gate: "standard" },
      { id: "release", label: "Release", team: "Implement", gate: "standard" },
    ],
    loops: ["fix->test (max 3)"],
    category: "build",
    useWhen: "Production bugs, security patches, critical dependency updates",
  },
  "refactoring": {
    name: "Refactoring",
    description: "Restructure existing code with regression testing. No new features, only structural improvement.",
    stages: [
      { id: "scope", label: "Scope Analysis", team: "Research", gate: "standard" },
      { id: "plan", label: "Plan", team: "Design", gate: "standard" },
      { id: "implement", label: "Implement", team: "Implement", gate: "convergence" },
      { id: "test", label: "Test", team: "Test", gate: "standard" },
      { id: "review", label: "Review", team: "Review", gate: "standard" },
    ],
    loops: ["implement->test (max 3)"],
    category: "build",
    useWhen: "Tech debt, restructure, simplify, reduce coupling",
  },
  "research-only": {
    name: "Research Only",
    description: "Gather information, compare alternatives, produce a structured report. No code output.",
    stages: [
      { id: "research", label: "Research", team: "Research", gate: null },
      { id: "compare", label: "Compare", team: "Research", gate: null },
      { id: "report", label: "Report", team: "Research", gate: "standard" },
    ],
    loops: ["research->compare (knowledge loop, max 3)"],
    category: "discover",
    useWhen: "Technology evaluation, competitive analysis, feasibility assessment",
  },
  "design-only": {
    name: "Design Only",
    description: "Research-backed design workflow. Produces reviewed architecture, not code.",
    stages: [
      { id: "research", label: "Research", team: "Research", gate: "standard" },
      { id: "design", label: "Design", team: "Design", gate: "standard" },
      { id: "review", label: "Review", team: "Review", gate: "standard" },
    ],
    loops: [],
    category: "shape",
    useWhen: "Architecture decisions, API design, database schema design",
  },
  "migration": {
    name: "Migration",
    description: "Assess, plan, implement, validate, and cut over to a new system or version.",
    stages: [
      { id: "assess", label: "Assessment", team: "Research", gate: "standard" },
      { id: "plan", label: "Plan", team: "Design", gate: "standard" },
      { id: "implement", label: "Implement", team: "Implement", gate: "convergence" },
      { id: "validate", label: "Validate", team: "Test", gate: "standard" },
      { id: "cutover", label: "Cutover", team: "Implement", gate: "standard" },
    ],
    loops: ["implement->validate (max 3)"],
    category: "build",
    useWhen: "Database migration, framework upgrade, platform transition",
  },
  "spike-poc": {
    name: "Spike / PoC",
    description: "Quick experiment to validate feasibility. Minimal process, throwaway code.",
    stages: [
      { id: "research", label: "Research", team: "Research", gate: "standard" },
      { id: "prototype", label: "Prototype", team: "Implement", gate: "standard" },
      { id: "evaluate", label: "Evaluate", team: "Review", gate: "standard" },
    ],
    loops: [],
    category: "discover",
    useWhen: "Is this possible? Technology experiments, risk reduction",
  },
  "documentation": {
    name: "Documentation",
    description: "Survey existing content, write documentation, review for accuracy and completeness.",
    stages: [
      { id: "survey", label: "Survey", team: "Research", gate: "standard" },
      { id: "author", label: "Author", team: "Implement", gate: "standard" },
      { id: "review", label: "Review", team: "Review", gate: "standard" },
    ],
    loops: [],
    category: "deliver",
    useWhen: "README, API docs, user guides, tutorials, architecture docs",
  },
  "security-audit": {
    name: "Security Audit",
    description: "Threat modeling, scanning, analysis, remediation, and verification.",
    stages: [
      { id: "threat", label: "Threat Model", team: "Research", gate: "standard" },
      { id: "scan", label: "Scan", team: "Test", gate: "standard" },
      { id: "analyze", label: "Analyze", team: "Research", gate: "standard" },
      { id: "remediate", label: "Remediate", team: "Implement", gate: "convergence" },
      { id: "verify", label: "Verify", team: "Test", gate: "standard" },
    ],
    loops: ["remediate->verify (max 4)"],
    category: "verify",
    useWhen: "Vulnerability scan, compliance review, CVE remediation",
  },
  "feature-enhancement": {
    name: "Feature Enhancement",
    description: "Extend existing functionality. Lighter than full-pipeline, heavier than hotfix.",
    stages: [
      { id: "scope", label: "Scope", team: "Research", gate: "standard" },
      { id: "design", label: "Design", team: "Design", gate: "standard" },
      { id: "plan", label: "Plan", team: "Design", gate: "standard" },
      { id: "implement", label: "Implement", team: "Implement", gate: "convergence" },
      { id: "review", label: "Review", team: "Review", gate: null },
      { id: "test", label: "Test", team: "Test", gate: "standard" },
      { id: "release", label: "Release", team: "Implement", gate: "standard" },
    ],
    loops: ["implement->review->test (max 3)"],
    category: "composite",
    useWhen: "Add pagination, new endpoint, additional option to existing system",
  },
  "rdrr": {
    name: "Research-Design-Review-Refine",
    description: "Iterative knowledge-building and design-convergence loop. Research grounds design; review drives refinement.",
    stages: [
      { id: "research", label: "Research", team: "Research", gate: "standard" },
      { id: "design", label: "Design", team: "Design", gate: null },
      { id: "review", label: "Review", team: "Review", gate: "standard" },
      { id: "refine", label: "Refine", team: "Design", gate: "convergence" },
    ],
    loops: ["design->review->refine (max 3)"],
    category: "composite",
    useWhen: "ADR workflow, system architecture with unknowns, design for uncertain domains",
  },
};

const TEAM_COLORS = {
  Research: "#6f42c1",
  Design: "#0d6efd",
  Implement: "#198754",
  Test: "#fd7e14",
  Review: "#dc3545",
};

function renderWorkflow(key) {
  const wf = WORKFLOWS[key];
  if (!wf) return;

  document.getElementById("wf-name").textContent = wf.name;
  document.getElementById("wf-desc").textContent = wf.description;
  document.getElementById("wf-category").textContent = wf.category;
  document.getElementById("wf-stages").textContent = wf.stages.length;
  document.getElementById("wf-use").textContent = wf.useWhen;

  const loopsEl = document.getElementById("wf-loops");
  if (wf.loops.length > 0) {
    loopsEl.innerHTML = wf.loops.map(l => `<span class="loop-tag">${l}</span>`).join(" ");
  } else {
    loopsEl.textContent = "none (linear flow)";
  }

  let mermaidDef = "graph LR\n";
  wf.stages.forEach((s, i) => {
    const shape = s.gate === "convergence" ? `${s.id}[["${s.label}"]]`
                : s.gate === "standard" ? `${s.id}["${s.label}"]`
                : `${s.id}("${s.label}")`;
    if (i === 0) {
      mermaidDef += `  ${shape}\n`;
    }
    if (i > 0) {
      const prev = wf.stages[i - 1];
      const prevShape = prev.gate === "convergence" ? `${prev.id}[["${prev.label}"]]`
                      : prev.gate === "standard" ? `${prev.id}["${prev.label}"]`
                      : `${prev.id}("${prev.label}")`;
      mermaidDef += `  ${prevShape} --> ${shape}\n`;
    }
  });

  const el = document.getElementById("diagram");
  el.innerHTML = "";
  const div = document.createElement("pre");
  div.className = "mermaid";
  div.textContent = mermaidDef;
  el.appendChild(div);
  if (window.mermaid) {
    window.mermaid.run({ nodes: [div] });
  }

  const teamList = document.getElementById("wf-teams");
  const teams = [...new Set(wf.stages.map(s => s.team))];
  teamList.innerHTML = teams.map(t =>
    `<span class="team-badge" style="background:${TEAM_COLORS[t] || '#666'}">${t}</span>`
  ).join(" ");
}

document.addEventListener("DOMContentLoaded", () => {
  const sel = document.getElementById("workflow-select");
  Object.entries(WORKFLOWS).forEach(([k, v]) => {
    const opt = document.createElement("option");
    opt.value = k;
    opt.textContent = `${v.name} (${v.stages.length} stages)`;
    sel.appendChild(opt);
  });
  sel.addEventListener("change", () => renderWorkflow(sel.value));
  sel.value = "full-pipeline";
  renderWorkflow("full-pipeline");
});
