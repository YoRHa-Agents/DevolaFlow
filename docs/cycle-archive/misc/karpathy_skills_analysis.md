# Andrej Karpathy Skills — Research Analysis (DevolaFlow v4.5.0)

**Generated:** 2026-04-13  
**Sources:** upstream `CLAUDE.md` (raw GitHub), GitHub API metadata, web synthesis (AIToolly 2026-04-12, playbooks.com skill listing, AIBit blog). Star count verified via API at generation time.

---

```yaml
repo_analysis:
  repo_url: "https://github.com/forrestchang/andrej-karpathy-skills"
  summary: >
    Minimal upstream artifact: a single CLAUDE.md that encodes four behavioral
    guidelines for LLM-assisted coding—assumption surfacing, simplicity,
    surgical diffs, and verifiable goals. The project packages the same ideas as
    an optional Claude Code plugin and a Playbooks-listed skill
    (karpathy-guidelines), amplifying distribution beyond raw markdown.
  star_count: 22770
  star_count_as_of: "2026-04-13T17:06:52Z"
  star_count_note: "Highly volatile social signal; re-query GitHub API for audits."
  key_philosophy:
    - "Bias caution over speed; trivial tasks may waive strictness."
    - "Reduce silent interpretation: multiple readings must be surfaced, not chosen quietly."
    - "Minimize blast radius: match style, avoid opportunistic cleanup."
    - "Replace vague intent with checks: tests, reproducers, before/after invariants."
  community_notes:
    - "Widely copied as a drop-in project instruction file; secondary articles frame it as structured prompt optimization for Claude Code."
    - "Complements (does not duplicate) DevolaFlow's existing gist track `karpathy-llm-wiki`—that gist is about persistent wiki workflows, not these coding norms."

guideline_mapping:

  - guideline: "Think Before Coding"
    devolaflow_coverage:
      - "references/execution-protocol.md: six-step pre-decision phase (DETECT→DISPATCH) and mandatory vs confirm fields reduce silent defaults."
      - "Exception model: PAUSE / HUMAN_INTERVENE escalation paths when spec is ambiguous (CLAUDE.md / workflow docs)."
      - "Lean dispatch/report schemas: discourage paraphrase; push verbatim facts (CO-2) — aligns with 'name what is confusing' at artifact boundaries."
      - "Decomposition gate and workflow templates: force staged clarification before large implementation commitments."
    gap_assessment: >
      Partial. Orchestration emphasizes upfront project-level decisions; L3 task prompts do not uniformly require an explicit
      'assumptions + open questions' block before first tool use. Risk: task agents may still infer silently under time pressure
      unless the parent message mandates a clarification checkpoint.
    improvement_proposals:
      - "Add an optional TaskDispatch field or checklist item: explicit_assumptions_and_questions (bounded length) before implementation."
      - "In MVP-SKILL / L3 brief: one required bullet 'Ambiguities surfaced (or none)' for Standard+ complexity."
      - "Mirror Karpathy's 'if multiple interpretations' rule in lean-dispatch key_facts: support multiple verbatim hypotheses with disambiguation asks."

  - guideline: "Simplicity First"
    devolaflow_coverage:
      - "Task sizing caps (~300 lines net change, max files) and wave limits reduce unbounded scope."
      - "Rationalization prevention tables (superpowers-inspired) attack 'I need extra abstraction' excuses."
      - "User-facing rules in CLAUDE.md (repo copy): avoid drive-by refactors and scope creep."
      - "Context profiles + task_adaptive_selector: skip irrelevant sections — reduces over-building context."
    gap_assessment: >
      Moderate gap. Gates score quality and coverage but do not explicitly penalize speculative features or 'future-proof'
      config that was not requested. No automated heuristic for 'lines vs minimal fix' beyond human review.
    improvement_proposals:
      - "Extend review primitive or gate rubric with a Simplicity / Scope-creep dimension (minor weight) with explicit anti-patterns."
      - "Document a 'YAGNI checklist' snippet for Review agents aligned with Karpathy bullets."
      - "Optional post-diff prompt: 'List removed speculative code' in refine stage when convergence triggers."

  - guideline: "Surgical Changes"
    devolaflow_coverage:
      - "P1 Dispatcher-Not-Implementer: L0–L2 avoid touching implementation files."
      - "Wave rules: disjoint owned_files; parallel tasks cannot share writable paths."
      - "CLAUDE.md user rules (this repo): match style, avoid unrelated edits — cultural alignment."
      - "Lean reporting: delta must be verbatim extractions — limits narrative refactoring."
    gap_assessment: >
      Strong cultural coverage via rules; weak automated enforcement. Nothing in CI blocks large unrelated diffs; reliance on
      review stage and human judgment. Karpathy's 'mention dead code, do not delete' is a nuanced policy not encoded in tooling.
    improvement_proposals:
      - "Review task acceptance criteria: require diff attribution — 'each changed hunk ties to task_id objective'."
      - "Optional hook: lint for touched paths outside owned_files / allowlist (where repo supports it)."
      - "Add explicit guidance for 'mention-only' cleanup vs requested cleanup in references/team-roles.md Review column."

  - guideline: "Goal-Driven Execution"
    devolaflow_coverage:
      - "TaskDispatch acceptance_criteria and timeout_seconds — contract-first tasks."
      - "Convergence loops with test and benchmark dimensions; gate composite includes test_quality."
      - "Mandatory verification rules (workspace): tests for new logic; pytest coverage expectations."
      - "Task Quality Score (user request scoring): Success Criteria dimension rewards explicit testable outcomes."
      - "Execution protocol checkpoints: verify before advancing stages."
    gap_assessment: >
      Strong. Possible refinement: Karpathy's micro-plan 'Step → verify' pattern is not a required L3 output format; agents may
      batch work without intermediate verification hooks unless test-first is culture-enforced.
    improvement_proposals:
      - "Standardize a compact 'plan_with_verification' optional YAML block in task specs (3–7 steps) for multi-step L3 work."
      - "Map hotfix workflow to Karpathy's bug pattern: reproducer test first, then fix (already implied; make explicit in hotfix template)."
      - "In status reports, optional field verification_steps_completed: list of checks passed this turn."

tracking_recommendation:
  should_track: true
  relevance_score: 4
  rationale: >
    High star count and stable, text-only upstream make it cheap to monitor. Content overlaps DevolaFlow themes (discipline,
    anti-rationalization, verification) but is not redundant with tracked `karpathy-llm-wiki` (different problem). Infrequent
    CLAUDE.md edits still warrant periodic diff review for community-validated wording changes. Fits `reference-dependencies.yaml`
    policy trigger: popular repo in agent-behavior space with clear integration hooks (SKILL, MVP-SKILL, review rubric).
  integration_points:
    - "workflow-system/agent/knowledge/reference-dependencies.yaml (new active_tracking entry)"
    - "CLAUDE.md / MVP-SKILL.md — short 'Karpathy norms' callout or cross-link if SF rules allow"
    - "references/execution-protocol.md or message-schemas.md — clarify when L3 must pause for ambiguity"
    - "Gate or review docs — optional simplicity and surgical-diff criteria"
  periodic_vs_active: "active_tracking with biweekly checks is sufficient; low churn file."

proposed_improvements:

  - id: KARP-01
    title: "Optional explicit pre-implementation assumptions block in task contracts"
    description: >
      Add a documented optional field or subsection for L3 tasks: stated assumptions, open questions, and interpretation
      branches before coding. Aligns with Think Before Coding and CO verbatim rules.
    affected_files:
      - "schemas/lean-dispatch.yaml"
      - "workflow-system/agent/context_profiles.yaml"
      - "MVP-SKILL.md"
    priority: P2
    effort: M

  - id: KARP-02
    title: "Review rubric: simplicity and surgical-diff criteria"
    description: >
      Extend review-stage guidance with explicit scoring hints for speculative features, unnecessary abstraction, and unrelated
      file churn; reference Karpathy tests ('every line traces to request').
    affected_files:
      - "workflow-system/agent/references/team-roles.md"
      - "SKILL.md"
    priority: P2
    effort: S

  - id: KARP-03
    title: "Track andrej-karpathy-skills in reference-dependencies.yaml"
    description: >
      Register repo under active_tracking with update_triggers on CLAUDE.md changes, relevance_score 4, and integration_points
      listing SKILL/MVP-SKILL/gate docs. Deduplicate against karpathy-llm-wiki (different scope).
    affected_files:
      - "workflow-system/agent/knowledge/reference-dependencies.yaml"
    priority: P3
    effort: S

  - id: KARP-04
    title: "Hotfix and multi-step templates: verification-first micro-plan"
    description: >
      Embed Karpathy's 'Step → verify' pattern in workflow templates for hotfix and feature-enhancement L3 dispatch examples.
    affected_files:
      - "CLAUDE.md"
      - "workflow-system/agent/references/execution-protocol.md"
    priority: P3
    effort: S

  - id: KARP-05
    title: "Optional path ownership enforcement hook"
    description: >
      Where feasible, add automation or hook that flags edits outside TaskDispatch owned_files to reinforce Surgical Changes.
      May be opt-in per repo mode.
    affected_files:
      - "lifecycle hooks documentation"
      - ".cursor/rules/ (if hook-based)"
    priority: P1
    effort: L
```

---

## External references (web synthesis)

- **Distribution:** The same guidelines appear as a [Playbooks skill](https://playbooks.com/skills/forrestchang/andrej-karpathy-skills/karpathy-guidelines) and in secondary coverage (e.g. AIToolly, AIBit) as Karpathy-inspired structured prompting for coding agents—not as competing orchestration frameworks.
- **Relation to DevolaFlow:** Behavioral complement to hierarchy/gates; does not replace P1–P5 mechanics but sharpens L3 execution norms.

---

## Verification

- [x] Upstream `CLAUDE.md` fetched from raw GitHub (2026-04-13).
- [x] Star count cross-checked via GitHub API.
- [x] `reference-dependencies.yaml` reviewed for deduplication and fit.
