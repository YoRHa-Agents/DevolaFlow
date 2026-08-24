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
  "demo-showcase": {
    name: "Demo & Showcase",
    description:
      "Build a presentation-ready demo or showcase: audience research, storyboard, polished build, review, polish loop, and packaging for delivery.",
    stages: [
      { id: "research", label: "Research", team: "Research", gate: "standard" },
      { id: "storyboard", label: "Storyboard", team: "Design", gate: "standard" },
      { id: "build", label: "Build", team: "Implement", gate: "convergence" },
      { id: "review", label: "Review", team: "Review", gate: null },
      { id: "polish", label: "Polish", team: "Implement", gate: "standard" },
      { id: "package", label: "Package", team: "Implement", gate: "standard" },
    ],
    loops: ["build->review->polish (max 2)"],
    category: "composite",
    useWhen: "Stakeholder demos, interactive showcases, conference talks, pitch-ready UI",
  },
  "performance-optimization": {
    name: "Performance Optimization",
    description:
      "Profile-driven optimization: measure bottlenecks, design changes, implement, benchmark, validate targets — with optimize↔benchmark convergence.",
    stages: [
      { id: "profile", label: "Profile", team: "Research", gate: "standard" },
      { id: "design", label: "Design", team: "Design", gate: "standard" },
      { id: "optimize", label: "Optimize", team: "Implement", gate: "convergence" },
      { id: "benchmark", label: "Benchmark", team: "Test", gate: "standard" },
      { id: "validate", label: "Validate", team: "Review", gate: "standard" },
    ],
    loops: ["optimize->benchmark (max 3)"],
    category: "build",
    useWhen: "Latency, throughput, memory, build/CI speed — measure before/after and prove gains",
  },
  "dependency-setup": {
    name: "Dependency & Environment Setup",
    description:
      "Install and validate dependencies and dev environment: research versions, plan the graph, configure, verify with smoke tests.",
    stages: [
      { id: "research", label: "Research", team: "Research", gate: "standard" },
      { id: "plan", label: "Plan", team: "Design", gate: "standard" },
      { id: "configure", label: "Configure", team: "Implement", gate: "convergence" },
      { id: "verify", label: "Verify", team: "Test", gate: "standard" },
    ],
    loops: ["configure->verify (max 3)"],
    category: "build",
    useWhen: "New dev environment, major deps, runtime upgrades, Docker/CI tooling",
  },
  "onboarding": {
    name: "Project Onboarding",
    description:
      "Onboard a contributor: survey the codebase, write onboarding docs, set up the environment, verify build and tests.",
    stages: [
      { id: "analyze", label: "Analyze", team: "Research", gate: "standard" },
      { id: "document", label: "Document", team: "Implement", gate: "standard" },
      { id: "setup", label: "Setup", team: "Implement", gate: "standard" },
      { id: "verify", label: "Verify", team: "Test", gate: "standard" },
    ],
    loops: [],
    category: "discover",
    useWhen: "New hires, OSS contributors, resuming unfamiliar or dormant projects",
  },
  "skill-optimization": {
    name: "Skill Optimization",
    description:
      "Iterative skill and context optimization: survey targets, profile with the built-in harness, optimize artifacts, evaluate measured telemetry, iterate, then document results.",
    stages: [
      { id: "survey", label: "Survey", team: "Research", gate: "standard" },
      { id: "profile", label: "Profile", team: "Test", gate: "standard" },
      { id: "optimize", label: "Optimize", team: "Implement", gate: "convergence" },
      { id: "benchmark", label: "Benchmark", team: "Test", gate: "standard" },
      { id: "iterate", label: "Iterate", team: "Review", gate: "convergence" },
      { id: "document", label: "Document", team: "Implement", gate: "standard" },
    ],
    loops: ["optimize->benchmark (max 3)"],
    category: "composite",
    useWhen: "SKILL.md density, context profiles, harness-driven iteration on agent skills",
  },
  "self-update": {
    name: "Self-Update",
    description:
      "Self-referential skill and workflow update: check references for staleness, research upstream changes, decompose updates, integrate, test, and evaluate the result.",
    stages: [
      { id: "check-refs", label: "Check Refs", team: "Research", gate: "standard" },
      { id: "research-updates", label: "Research Updates", team: "Research", gate: "standard" },
      { id: "decompose", label: "Decompose", team: "Design", gate: "standard" },
      { id: "integrate", label: "Integrate", team: "Implement", gate: "convergence" },
      { id: "test", label: "Test", team: "Test", gate: "standard" },
      { id: "evaluate", label: "Evaluate", team: "Review", gate: "standard" },
    ],
    loops: ["integrate->test (max 3)"],
    category: "composite",
    useWhen: "Skill refresh, workflow registry updates, upstream dependency sync, self-referential maintenance",
  },
};

const TEAM_COLORS = {
  Research: "#B8860B",
  Design: "#C49A3C",
  Implement: "#5B7553",
  Test: "#D4A843",
  Review: "#9B4444",
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

  // Build Mermaid diagram with Project Agent as orchestrator
  let m = "graph TD\n";
  m += `  PA["Project Agent\\n(dispatches stages)"] --> S0_gate{"Pre-Decision\\nGate"}\n`;
  m += `  S0_gate --> ${wf.stages[0].id}\n`;

  wf.stages.forEach((s, i) => {
    const shape = s.gate === "convergence" ? `${s.id}[["Stage: ${s.label}\\n(${s.team} team)"]]`
                : s.gate === "standard" ? `${s.id}["Stage: ${s.label}\\n(${s.team} team)"]`
                : `${s.id}("Stage: ${s.label}\\n(${s.team} team)")`;
    if (i > 0) {
      const prev = wf.stages[i - 1];
      const gateId = `gate_${prev.id}`;
      if (prev.gate) {
        m += `  ${prev.id} --> ${gateId}{"Gate\\n${prev.gate}"}\n`;
        m += `  ${gateId} -->|PASS| ${shape}\n`;
      } else {
        m += `  ${prev.id} --> ${shape}\n`;
      }
    } else {
      m += `  ${shape}\n`;
    }
  });

  // Final gate after last stage
  const last = wf.stages[wf.stages.length - 1];
  if (last.gate) {
    m += `  ${last.id} --> gate_final{"Gate\\n${last.gate}"}\n`;
    m += `  gate_final -->|PASS| done["Project Agent\\n(reports to Human)"]\n`;
  } else {
    m += `  ${last.id} --> done["Project Agent\\n(reports to Human)"]\n`;
  }

  const el = document.getElementById("diagram");
  el.innerHTML = "";
  const div = document.createElement("pre");
  div.className = "mermaid";
  div.textContent = m;
  el.appendChild(div);
  if (window.mermaid) {
    window.mermaid.run({ nodes: [div] });
  }

  // Teams
  const teamList = document.getElementById("wf-teams");
  const teams = [...new Set(wf.stages.map(s => s.team))];
  teamList.innerHTML = teams.map(t =>
    `<span class="team-badge" style="background:${TEAM_COLORS[t] || '#666'}">${t}</span>`
  ).join(" ");

  // Agent hierarchy for this workflow
  const hierarchyEl = document.getElementById("wf-hierarchy");
  hierarchyEl.innerHTML = `
    <div class="agent-chain">
      <div class="agent-box project">
        <strong>Project Agent (L0)</strong>
        <p>Selects the <em>${wf.name}</em> seed, owns the change checklist, decomposes rounds into waves, evaluates gates, decides loop-back vs advance. Round groups for <em>${wf.name}</em>: ${wf.stages.map(s => s.label).join(" / ")}.</p>
        <span class="ctx">~5K tokens | MUST NOT: read code, write code, run tests</span>
      </div>
      <div class="agent-arrow">dispatches each wave to</div>
      <div class="agent-box wave">
        <strong>Wave Agent (L1)</strong> &mdash; one per wave
        <p>Dispatches up to 5 parallel tasks, collects results, checks cross-task conflicts (file ownership).</p>
        <span class="ctx">~5K tokens | MUST NOT: execute task work, modify outputs</span>
      </div>
      <div class="agent-arrow">dispatches each task to</div>
      <div class="agent-box task">
        <strong>Task Agent (L2)</strong> &mdash; the ONLY layer that works
        <p>Assigned to a team (${teams.join(" / ")}). Writes code, runs tests, authors documents, performs reviews. Owns a disjoint file set.</p>
        <span class="ctx">~8K tokens | MUST NOT: spawn sub-agents, modify files outside owned set</span>
      </div>
    </div>`;
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
