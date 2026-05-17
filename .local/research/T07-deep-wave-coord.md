# T07 Deep Research: Wave Coordination Modes — Sub-Variant Design

**Task ID:** T07-deep-research-wave-coord
**Team:** Research
**Date:** 2026-04-11
**Input:** `.local/designs/T04-advisor-integration-designs.md` (Card 1+2 merged)
**Baseline:** SKILL.md v3.6.0 (402 lines), EvoBench avg composite 99.13
**Current Card 1+2 Impact:** +21 lines, Δ composite -0.52

---

## 1. Web Research Findings

### 1.1 Anthropic Generator-Evaluator Harness (2026-03-31)

**Source:** Anthropic engineering blog "Harness design for long-running application development"

**Key findings:**
- Three-agent architecture: **Planner → Generator → Evaluator**, each with independent context windows and hard resets between sessions
- Addresses two failure modes: **context degradation** (premature task wrap-up as context fills) and **self-evaluation bias** (agents overrate own output)
- Context resets prove more effective than in-place compaction
- Iterative feedback loop runs **5-15 iterations** per session, up to 4 hours
- **Sprint contracts**: generator proposes scope + explicit success criteria validated by evaluator before coding begins (ATDD for agents)
- Evaluator checks **27+ criteria per sprint** and files structured bug reports
- Shared state via single disk file with structured sections (plan, work log, contracts, evaluation results, feedback)
- Evaluator is tuned to be **skeptical** — more tractable than making generator self-critical

**Relevance to DevolaFlow:**
- DevolaFlow's gen-verify maps to Anthropic's generator-evaluator, but at L2 Wave level (not standalone harness)
- Sprint contracts ≈ acceptance_criteria in TaskDispatch schema — already present
- Key insight: **separate evaluator with skeptical tuning** is critical; self-evaluation fails reliably
- 5-15 iterations is far higher than our default max_rounds=3; consider whether 3 is sufficient
- Context reset between rounds aligns with DevolaFlow's context isolation (P5)

### 1.2 AdaptOrch DAG Topology Routing (2026-02)

**Source:** arXiv 2602.16873 — "AdaptOrch: Task-Adaptive Multi-Agent Orchestration in the Era of LLM Performance Convergence"

**Key findings:**
- As LLMs converge within 2-5% on benchmarks, **orchestration topology becomes the dominant optimization variable**
- Four canonical topologies: parallel, sequential, hierarchical, hybrid
- **Topology Routing Algorithm**: O(|V|+|E|) linear-time mapping from task DAG to optimal topology
- **12-23% improvement** over static single-topology baselines across coding (SWE-bench), reasoning (GPQA), and RAG tasks
- Three contributions: (1) Performance Convergence Scaling Law, (2) Topology Routing Algorithm, (3) Adaptive Synthesis Protocol with provable termination guarantees

**Relevance to DevolaFlow:**
- DevolaFlow currently uses fixed hierarchical topology for all workflows — exactly the static baseline AdaptOrch outperforms
- O(|V|+|E|) analysis is trivially cheap compared to LLM inference
- "Adaptive Synthesis Protocol with provable termination guarantees" maps to our gen-verify termination problem
- Key question: should DevolaFlow expose all 4 topologies or pre-filter to the 3 that matter at L2 Wave level? (hierarchical is already the L0→L1→L2→L3 structure itself)

### 1.3 Multi-Agent Coordination Mode Selection Criteria

**Source:** Multiple — DeMAC (ACL Anthology), Augment Code guides, AdaptOrch

**Key findings:**
- Task **parallelizability** is the dominant selection criterion: +81% improvement on parallelizable tasks, -70% degradation on sequential ones when parallelized
- Dynamic DAG routing with Manager-Player Dual-Feedback (DeMAC) handles shifting priorities and unpredictable disruptions
- Multi-agent systems consume **4-220x more tokens** than single-agent — coordination overhead is a significant cost factor
- Context isolation and dependency conflicts influence topology choice as much as task structure

**Relevance to DevolaFlow:**
- The 4-220x token cost range validates DevolaFlow's concern about gen-verify token overhead (2-3x per round)
- Dynamic DAG routing could be overkill — DevolaFlow's DAGs are small (≤5 tasks per wave)
- For ≤5-node DAGs, simple heuristics (edge count, shared files) beat formal graph algorithms

### 1.4 Generator-Verifier Loop Termination Strategies

**Source:** Multiple — Medium (Agent Loops), EmergentMind, arXiv

**Key findings:**
- **Convergence-based termination**: model as absorbing Markov chain — transient states = pipeline stages, absorbing state = "success"; enables provable convergence bounds
- **Quality thresholding (β)**: verifier assigns quality scores; iterate until score ≥ β or preset iteration limit
- **Search-based selection**: sample multiple candidates, score, pick best (Tree of Thoughts, self-consistency)
- **Feedback-driven iteration**: convert generation into sequential decision process with checkpoints and correction mechanisms
- **Reinforced co-evolution** (TANGO): generator and verifier co-evolve through mutual RL rewards

**Relevance to DevolaFlow:**
- Current design uses simple `max_rounds` — this is the weakest termination strategy
- Quality thresholding (β) maps naturally to gate composite scores: terminate when verifier score ≥ stage gate threshold
- Stagnation detection (score unchanged 2+ rounds) is already in the design — good
- **Optimization opportunity**: replace `max_rounds` with `min(max_rounds, quality_threshold_met, stagnation_detected)` — a compound termination condition
- Markov chain modeling is overkill for ≤3 rounds but validates that bounded iteration converges

### 1.5 Wave-Level vs Stage-Level Convergence Tradeoffs

**Source:** Multiple — AgentOrchestra, production patterns blog posts

**Key findings:**
- Stage-level convergence: explicit handling of dependencies, cleaner state handoff, but **higher latency per feedback cycle**
- Wave-level convergence: reduces latency for tight feedback loops, but **can cause problems under stress** (parallel failures, context pollution)
- Best practice: **hybrid** — router dispatches to specialist agents while supervisor coordinates through explicit stages
- Key insight: when models are functionally interchangeable, how agents are **composed and coordinated** determines system-level performance

**Relevance to DevolaFlow:**
- DevolaFlow currently only has stage-level convergence — wave-level gen-verify fills the gap
- Risk: wave-level convergence might make stage-level convergence redundant for simple cases, confusing agents about which loop to use
- **Optimization opportunity**: explicitly scope when to use each — gen-verify for **intra-wave quality** (single task output), stage convergence for **cross-wave integration** (multi-task coherence)

### 1.6 Context-Centric vs Problem-Centric Decomposition

**Source:** Multiple — Oboe (Context Rot), huuhka.net (Primary vs Subagents), arXiv

**Key findings:**
- Context-centric: subagents exist to **protect orchestrator context window**, not organized by functional specialization
- Problem-centric: decomposition follows **problem structure** — divide into sub-problems assigned to specialists
- Context isolation pattern: Lead Agent delegates noisy work to isolated sub-agents → returns only distilled results
- **Dynamic Attentional Context Scoping (DACS)**: 90-98% steering accuracy vs 21-60% for flat-context baselines
- Good subagent outputs: compact, structured — summaries, file paths, key findings; avoid full dumps

**Relevance to DevolaFlow:**
- DevolaFlow uses **problem-centric** decomposition (stage primitives → tasks by function) with **context-centric** isolation (P5, context_profiles.yaml)
- Gen-verify is inherently context-centric: verifier gets only generator output + criteria, not full generator context
- This is correct — validates the design. The SKILL.md text should make this implicit design choice explicit

### 1.7 Anthropic Harness Termination Specifics

**Source:** Deep dive into Anthropic engineering blog + community implementations

**Key findings:**
- Sprint contracts with **hard pass/fail thresholds** — not soft scores
- Evaluator checks 27+ criteria per sprint → files structured bug reports
- Self-evaluation bias confirmed: "AI can't evaluate its own work" — external evaluator is essential
- Each sprint has explicit scope + success criteria validated **before coding begins**
- The GAN-inspired loop (generator ↔ evaluator) runs 5-15 iterations

**Relevance to DevolaFlow:**
- 27+ criteria per sprint is far denser than typical DevolaFlow acceptance_criteria (usually 3-5 items)
- Pre-validated criteria (sprint contracts) reduces wasted gen-verify rounds
- Confirms: `max_rounds=3` may be insufficient for complex tasks; but 5-15 is for 4-hour sessions — DevolaFlow tasks are 30min max
- For 30min tasks, max_rounds=3 is reasonable; for convergence stages (review+fix), consider max_rounds=5

---

## 2. Sub-Variant Designs

### 2.1 Variant A — Minimal (11 lines)

**Design philosophy:** Only the mode table + one-line gen-verify summary. Relies on agent prior knowledge of generator-verifier patterns. Minimum viable instruction surface.

**Exact SKILL.md text:**

```markdown
### Wave Coordination Modes

L2 Wave selects coordination mode by analyzing task DAG before dispatch:

| DAG Shape | Mode | Mechanism |
|-----------|------|-----------|
| No dependency edges | `parallel` | Dispatch all, collect results (default) |
| Linear chain (A→B→C) | `sequential` | Dispatch N+1 after N completes |
| Quality-critical + shared context | `generator_verifier` | Generator output → verifier evaluates → refine on FAIL (max_rounds from gate) |
| Mixed dependencies | `hybrid` | Partition: parallel groups + sequential chains |

Selection: O(|V|+|E|) DAG analysis. L1 Stage may override via `topology_override`.
```

**Line count:** 11
**Token estimate:** ~140
**Pros:** Smallest footprint, leaves gen-verify details to agent inference, maximum density per line
**Cons:** Agent may not understand gen-verify termination, verifier criteria derivation, or when to use gen-verify vs stage convergence. Relies heavily on agent prior knowledge of Anthropic patterns.
**EvoBench prediction:** Δ composite ~-0.25 to -0.35 (smaller than current -0.52 due to fewer tokens consumed)

---

### 2.2 Variant B — Standard (16 lines, current design)

**Design philosophy:** Mode table + DAG selection note + gen-verify 4-step protocol + use cases. The existing merged Card 1+2 design.

**Exact SKILL.md text:**

```markdown
### Wave Coordination Modes

L2 Wave auto-selects coordination mode by analyzing task DAG before dispatch:

| DAG Shape | Mode | Mechanism |
|-----------|------|-----------|
| No dependency edges | `parallel` | Dispatch all, collect results (default) |
| Linear chain (A→B→C) | `sequential` | Dispatch N+1 after N completes |
| Quality-critical + shared context | `generator_verifier` | Generate → Evaluate → Refine loop |
| Mixed dependencies | `hybrid` | Partition: parallel groups + sequential chains |

Selection: O(|V|+|E|) DAG analysis at dispatch time. L1 Stage may override via `topology_override`.

**Generator-Verifier protocol:**
1. Wave dispatches **generator** task + **verifier** criteria (from acceptance_criteria)
2. Generator output → verifier evaluates → structured verdict {PASS | FAIL + feedback}
3. FAIL → generator refines with feedback (round N+1). PASS → wave completes
4. Termination: verifier PASS **or** `max_rounds` reached → escalate to L1

Use for: convergence stages (review+fix, test+fix, benchmark+optimize). Reduces stage-level convergence rounds.
```

**Line count:** 16 (+ 5 blank lines = 21 total)
**Token estimate:** ~240
**Pros:** Complete protocol description, clear termination rule, explicit use cases
**Cons:** 5 blank lines waste budget; protocol steps could be compressed; "Use for" line is supplementary
**EvoBench actual:** Δ composite -0.52

---

### 2.3 Variant C — Extended (21 lines)

**Design philosophy:** Add explicit DAG classification rules (edge counting heuristic), verifier criteria derivation from AC, and anti-patterns. Maximum behavioral clarity.

**Exact SKILL.md text:**

```markdown
### Wave Coordination Modes

L2 Wave auto-selects coordination mode by analyzing task DAG before dispatch:

| DAG Shape | Mode | Mechanism |
|-----------|------|-----------|
| No dependency edges | `parallel` | Dispatch all, collect results (default) |
| Linear chain (A→B→C) | `sequential` | Dispatch N+1 after N completes |
| Quality-critical + shared context | `generator_verifier` | Generate → Evaluate → Refine loop |
| Mixed dependencies | `hybrid` | Partition: parallel groups + sequential chains |

**DAG classification:** 0 edges → parallel. All nodes in single path → sequential. Shared `owned_files` + AC requires evaluation → gen-verify. Else → hybrid. L1 Stage overrides via `topology_override`.

**Generator-Verifier protocol:**
1. Wave dispatches **generator** task + **verifier** with criteria derived from `acceptance_criteria` (each AC item → testable check)
2. Generator output → verifier evaluates each criterion → verdict `{PASS | FAIL + specific_feedback[]}`
3. FAIL → feedback injected as `predecessor_artifacts` → generator refines (round N+1). PASS → wave completes
4. Termination: verifier PASS **or** `max_rounds` reached **or** score stagnant 2 rounds → escalate to L1

**Anti-patterns:** Rubber-stamp verifier (verifier must check ≥1 machine-testable criterion). Early victory (first-round PASS without testing → suspicious, log warning).
Use for: convergence stages (review+fix, test+fix, benchmark+optimize).
```

**Line count:** 21 (content lines, ~26 total with blanks)
**Token estimate:** ~310
**Pros:** Explicit DAG classification rules prevent agent guessing; anti-patterns prevent common failure modes; feedback injection mechanism specified; compound termination strategy (PASS ∨ max_rounds ∨ stagnation)
**Cons:** Exceeds current 21-line footprint; anti-patterns may be over-specified for agent consumption; DAG classification rules could go in a reference doc instead
**EvoBench prediction:** Δ composite ~-0.70 to -0.85 (more tokens, more sections to allocate)

---

### 2.4 Variant D — Compact-Optimized (13 lines)

**Design philosophy:** Rewrite current 16-line design to maximize information density. Same concepts, fewer lines. Uses DevolaFlow's terse table-heavy style. Zero information loss vs Variant B.

**Exact SKILL.md text:**

```markdown
### Wave Coordination Modes

L2 Wave auto-selects mode via O(|V|+|E|) DAG analysis. L1 may override (`topology_override`).

| DAG Shape | Mode | Mechanism |
|-----------|------|-----------|
| No edges | `parallel` | Dispatch all, collect results (default) |
| Linear chain | `sequential` | Dispatch N+1 after N completes |
| Quality-critical + shared context | `generator_verifier` | Gen → Verify → Refine loop (below) |
| Mixed | `hybrid` | Partition: parallel groups + sequential chains |

**Gen-Verify loop** (convergence stages: review+fix, test+fix, benchmark+optimize):
1. Wave dispatches **generator** + **verifier** (criteria from `acceptance_criteria`)
2. Verifier evaluates → `{PASS | FAIL + feedback}`. PASS → done. FAIL → generator refines (round N+1)
3. Terminates on: verifier PASS, `max_rounds` reached, or score stagnant 2 rounds → escalate L1
```

**Line count:** 13 (content lines, ~15 total with blanks)
**Token estimate:** ~185
**Pros:** 3 fewer lines than Variant B, zero information loss; merged "Use for" into header; merged termination into step 3; collapsed DAG labels; higher tokens-per-concept ratio
**Cons:** Slightly denser prose — may reduce comprehension for less capable models; "below" reference in table is a minor readability compromise
**EvoBench prediction:** Δ composite ~-0.30 to -0.40 (fewer tokens than Variant B, same concepts)

---

## 3. Context Profile Priority Schemes

### Current Profile List (15 profiles)

hotfix, feature, research, refactor, review, design, skill-optimization, migration, security-audit, documentation, spike-poc, rdrr, demo-showcase, perf-optimization, dependency-setup, onboarding

### 3.1 Priority Scheme P1 — Aggressive

**Philosophy:** Wave coordination is broadly useful. Mark as `critical` for any profile that involves multi-task waves or benefits from topology awareness.

| Profile | wave_coordination | Rationale |
|---------|:-:|---|
| hotfix | skip | Single-task waves, no coordination needed |
| feature | critical | Multi-wave impl stages, gen-verify for review+fix |
| research | skip | Single-stage, no wave loops |
| refactor | critical | Review-fix convergence cycles |
| review | important | May trigger gen-verify for fix cycles |
| design | important | Design iteration can use gen-verify |
| skill-optimization | critical | Optimize-benchmark iterations |
| migration | critical | Validate-fix cycles common |
| security-audit | critical | Scan-remediate-verify natural gen-verify |
| documentation | skip | Doc authoring is linear |
| spike-poc | skip | Exploratory, no tight loops |
| rdrr | critical | Research→design→review→refine IS gen-verify |
| demo-showcase | important | Build stages may benefit from polish loops |
| perf-optimization | critical | Profile→optimize→benchmark is gen-verify |
| dependency-setup | skip | Configure-verify is simpler than gen-verify |
| onboarding | skip | Analysis/documentation, no gen-verify |

**Summary:** 8 critical, 3 important, 0 supplementary, 5 skip
**Token budget impact:** +180 tokens across critical profiles; may push migration over budget
**Risk:** Aggressive allocation may crowd out other critical sections for budget-tight profiles (migration, hotfix)

---

### 3.2 Priority Scheme P2 — Conservative

**Philosophy:** Only mark as `critical` for profiles with **natural gen-verify cycles** (where the workflow pattern inherently matches generator-verifier). Others get `important` or `skip`.

| Profile | wave_coordination | Rationale |
|---------|:-:|---|
| hotfix | skip | Single-task fix, no wave coordination |
| feature | important | Benefits from topology selection, but gen-verify is secondary |
| research | skip | No wave loops |
| refactor | critical | Review-fix is the canonical gen-verify use case |
| review | supplementary | Primarily evaluates, rarely generates |
| design | supplementary | Design iteration is stage-level, not wave-level |
| skill-optimization | important | Benchmark+optimize cycles benefit |
| migration | important | Validate-fix benefits, but migration is budget-sensitive |
| security-audit | critical | Scan-remediate-verify is tight gen-verify |
| documentation | skip | Linear authoring |
| spike-poc | skip | Exploratory |
| rdrr | critical | Core loop is gen-verify |
| demo-showcase | skip | Build→polish is simpler than gen-verify |
| perf-optimization | critical | Profile→optimize→benchmark is the textbook gen-verify case |
| dependency-setup | skip | Configure→verify is simple |
| onboarding | skip | No gen-verify pattern |

**Summary:** 4 critical, 3 important, 2 supplementary, 7 skip
**Token budget impact:** +180 tokens for critical profiles only; important profiles include only if budget allows
**Risk:** Conservative approach may under-serve feature and migration profiles that could benefit from topology selection. However, this preserves budget for these already-tight profiles.

---

### 3.3 Priority Scheme P3 — Selective (Gate-Aligned)

**Philosophy:** Align wave_coordination priority with the profile's gate type. Convergence gates need gen-verify. Standard gates get topology selection. Passthrough gates skip.

Profiles with convergence gates: refactor, rdrr, perf-optimization, security-audit, migration, skill-optimization
Profiles with standard gates: feature, review, design, demo-showcase, documentation
Profiles with passthrough/relaxed gates: hotfix, research, spike-poc, dependency-setup, onboarding

| Profile | wave_coordination | Gate Alignment |
|---------|:-:|---|
| hotfix | skip | Passthrough — fast fix, no convergence |
| feature | supplementary | Standard — topology selection useful but gen-verify rare |
| research | skip | Passthrough — single stage |
| refactor | critical | Convergence — review+fix loop |
| review | supplementary | Standard — evaluation focus, no generation |
| design | supplementary | Standard — design iteration is at stage level |
| skill-optimization | critical | Convergence — optimize+benchmark loop |
| migration | critical | Convergence — validate+fix cycle |
| security-audit | critical | Convergence — scan+remediate+verify |
| documentation | skip | Standard but doc authoring is linear, no topology benefit |
| spike-poc | skip | Passthrough — no quality gates |
| rdrr | critical | Convergence — the RDRR loop itself |
| demo-showcase | supplementary | Standard — build+polish benefits from topology, not gen-verify |
| perf-optimization | critical | Convergence — benchmark-driven optimization |
| dependency-setup | skip | Passthrough — configure+verify |
| onboarding | skip | Passthrough — analysis focus |

**Summary:** 5 critical, 0 important, 4 supplementary, 7 skip
**Token budget impact:** Smallest footprint — only convergence profiles pay the token cost
**Risk:** Misses legitimate topology selection benefits for feature and demo-showcase. However, `supplementary` still includes them when budget allows, which is a safer tradeoff for budget-sensitive profiles.

---

### Priority Scheme Comparison

| Scheme | # critical | # important | # supplementary | # skip | Migration priority | Feature priority | Budget pressure |
|--------|:-:|:-:|:-:|:-:|:-:|:-:|---|
| **P1 Aggressive** | 8 | 3 | 0 | 5 | critical | critical | High — may exacerbate migration -9.89 regression |
| **P2 Conservative** | 4 | 3 | 2 | 7 | important | important | Low — migration budget preserved |
| **P3 Selective** | 5 | 0 | 4 | 7 | critical | supplementary | Medium — migration is convergence-gated |

**Recommendation:** **P2 (Conservative)** or **P3 (Selective)**

P1 is risky because migration_upgrade already shows -9.89 composite regression — making wave_coordination `critical` for migration would worsen this by forcing inclusion even when budget is tight.

P2 is safest: migration gets `important` (included only if budget allows), preserving the existing profile's budget allocation. P3 is more principled (gate-aligned) but marks migration as `critical`, which conflicts with the benchmark data showing migration is budget-sensitive.

**Recommended hybrid:** Use P3's gate-alignment logic but **override migration to `important`** (not `critical`) based on benchmark data. This gives:
- 4 critical: refactor, rdrr, perf-optimization, security-audit (natural convergence loops)
- 1 important: migration (convergence loop but budget-sensitive)
- 4 supplementary: feature, review, design, demo-showcase
- 7 skip: hotfix, research, documentation, spike-poc, dependency-setup, onboarding, skill-optimization

Wait — skill-optimization has convergence gates (optimize→benchmark→iterate). Revising:
- 5 critical: refactor, rdrr, perf-optimization, security-audit, skill-optimization
- 1 important: migration
- 3 supplementary: feature, design, demo-showcase
- 1 supplementary: review
- 6 skip: hotfix, research, documentation, spike-poc, dependency-setup, onboarding

---

## 4. Optimization Opportunities

### 4.1 Can the gen-verify protocol be more compact without losing behavioral clarity?

**Analysis:** The current 4-step protocol (Variant B) has redundancy:
- Step 1 (dispatch generator + verifier criteria) is dispatch mechanics — already covered by the mode table's "Mechanism" column
- Step 2 (generator → verifier → verdict) is the core loop
- Step 3 (FAIL → refine) is the feedback path
- Step 4 (termination) is the exit condition

**Recommendation:** Yes — merge steps 1-3 into 2 steps (Variant D approach):
1. Dispatch generator + verifier (criteria from AC). Verifier evaluates → `{PASS|FAIL+feedback}`
2. PASS → done. FAIL → generator refines with feedback. Terminates on PASS, max_rounds, or stagnation → escalate

This preserves all behavioral information in 2 lines instead of 4. Variant D demonstrates this works.

**Token savings:** ~55 tokens (from ~240 to ~185)

### 4.2 Are there better termination heuristics than max_rounds?

**Analysis based on research:**

| Heuristic | Source | Complexity | Applicable? |
|-----------|--------|:-:|---|
| Quality threshold (score ≥ β) | IGVL, AdaptOrch | Low | Yes — use gate composite score as β |
| Stagnation detection (Δscore < ε for 2 rounds) | DevolaFlow existing | Low | Already in design — keep |
| max_rounds hard cap | Standard | Trivial | Keep as safety net |
| Markov chain convergence | Predict-then-Verify | High | Overkill for ≤3 rounds |
| Multi-candidate sampling (best-of-N) | Tree of Thoughts | Medium | Possible for impl tasks — spawn N generators, pick best |
| RL co-evolution | TANGO | Very High | Not applicable — requires training data |
| Sprint contracts (pre-validated criteria) | Anthropic | Low | Already present via acceptance_criteria |

**Recommendation:** Use **compound termination**: terminate on `min(PASS, max_rounds, stagnation)`. This is what Variant C and D implement. Additionally, consider using the **gate composite score** as the quality threshold β: if verifier can compute a composite score ≥ stage threshold, terminate early even before explicit PASS.

For DevolaFlow's 30-min task sizing, `max_rounds=3` is appropriate. Anthropic's 5-15 iterations are for 4-hour sessions. Suggest keeping max_rounds=3 as default, with L1 Stage able to set max_rounds=5 for complex convergence stages.

### 4.3 Should DAG analysis be in SKILL.md or a reference doc?

**Analysis:**

| Factor | SKILL.md | Reference doc |
|--------|----------|---------------|
| Agent needs to understand concept | Yes — mode selection is a core L2 behavior | Agent may not load reference in time |
| Implementation detail (edge counting) | Adds lines without changing behavior | Better fit for reference |
| DAG classification rules | Borderline — useful but not critical for correct mode selection | Can go in reference with SKILL.md saying "auto-selects" |
| Token budget impact | Every line costs across all critical profiles | Reference loaded only when topic arises |

**Recommendation:** Keep the **mode table + "auto-selects via DAG analysis"** in SKILL.md. Move DAG classification details (edge counting heuristic, shared_files detection) to a reference doc (either `references/execution-protocol.md` or a new `references/wave-coordination.md`).

Variant D demonstrates this: the table + "O(|V|+|E|) DAG analysis" gives L2 Wave enough to understand the concept, while implementation details live elsewhere.

### 4.4 Optimal balance between instruction density and agent comprehension

**Analysis based on benchmark data + research:**

| Metric | Variant A (11 lines) | Variant B (16 lines) | Variant C (21 lines) | Variant D (13 lines) |
|--------|:-:|:-:|:-:|:-:|
| Information completeness | 70% — missing protocol details | 100% — full protocol | 120% — includes anti-patterns | 100% — same as B, compressed |
| Agent comprehension (estimated) | 85% — relies on prior knowledge | 95% — explicit steps | 90% — information overload risk | 93% — dense but clear |
| Token cost | ~140 | ~240 | ~310 | ~185 |
| Predicted Δ composite | -0.30 | -0.52 (actual) | -0.75 | -0.35 |
| Budget pressure | Low | Medium | High | Low-Medium |

**Key insight from research:** Context-centric decomposition research (DACS) shows that **90-98% steering accuracy** comes from focused, relevant context — not from exhaustive context. DevolaFlow's context profiles already implement this principle. The optimal SKILL.md text should provide enough for the agent to make correct mode selection decisions, not enough to implement the DAG router from scratch.

**Recommendation:** **Variant D** is the optimal balance:
- Same information as Variant B (zero loss)
- 30% fewer tokens (~185 vs ~240)
- Predicted benchmark improvement of ~0.15-0.20 over Variant B
- Compound termination (PASS ∨ max_rounds ∨ stagnation) is better than Variant B's simpler rule
- The table-heavy style matches DevolaFlow's existing patterns

### 4.5 Additional optimizations identified from research

**O1 — Verifier skepticism tuning:**
Anthropic's key finding is that the evaluator should be tuned to be **skeptical**. Current design doesn't specify verifier behavior beyond "evaluates." Add to verifier criteria derivation: "Verifier evaluates as external reviewer, not author."

**Implementation:** Zero additional SKILL.md lines — this goes into the Task Agent prompt template for verifier tasks, not SKILL.md.

**O2 — Feedback structure:**
Current design says "structured verdict {PASS | FAIL + feedback}." Research shows structured bug reports (Anthropic uses 27+ criteria) outperform prose feedback. Specify that feedback uses the same format as gate findings: `{severity, file, description}`.

**Implementation:** 0 additional SKILL.md lines — this maps to the existing StatusReport schema's `findings_by_severity` field.

**O3 — Wave-level vs stage-level scope clarification:**
Research highlights confusion potential between wave-level and stage-level convergence. Add explicit scoping: gen-verify handles **single-output quality** (one task's work), stage convergence handles **cross-task integration** (multiple tasks' outputs fit together).

**Implementation:** Can be folded into the "Use for" line or a reference doc. Not worth a separate SKILL.md line.

**O4 — Sprint contract validation:**
Anthropic validates criteria **before** the generator starts work. DevolaFlow's acceptance_criteria are validated at dispatch time (validate_dispatch hook from Card 4). Without hooks, this validation is prompt-based. Consider adding to gen-verify protocol: "Verifier validates criteria are testable before generator starts."

**Implementation:** 0 additional lines if using Card 4 hooks. Without hooks, add as step 0 in the protocol (+1 line).

---

## 5. Final Recommendations

### Recommended Sub-Variant: **Variant D (Compact-Optimized)**

**Rationale:**
1. **Zero information loss** vs current Variant B
2. **30% fewer tokens** (~185 vs ~240) → reduced budget pressure on all profiles
3. **Compound termination** (PASS ∨ max_rounds ∨ stagnation) — better than Variant B's simple rule
4. **Predicted EvoBench improvement** of ~0.15-0.20 over Variant B (Δ composite -0.30 to -0.35 vs -0.52)
5. **Table-heavy style** matches DevolaFlow's existing patterns
6. **13 content lines** vs Variant B's 16 → better line budget utilization

### Recommended Priority Scheme: **P2 (Conservative) with P3 gate-alignment for critical selections**

Hybrid approach:
- 5 critical: refactor, rdrr, perf-optimization, security-audit, skill-optimization
- 1 important: migration (convergence but budget-sensitive)
- 4 supplementary: feature, review, design, demo-showcase
- 6 skip: hotfix, research, documentation, spike-poc, dependency-setup, onboarding

**Rationale:** Protects migration profile's budget (the biggest regression risk) while ensuring convergence-loop profiles get wave coordination.

### Recommended Additional Optimizations

| ID | Optimization | Lines Added | Effort |
|----|-------------|:-:|---|
| O1 | Verifier skepticism tuning in task prompt template | 0 | Low — template change only |
| O2 | Structured feedback using existing findings format | 0 | Low — schema reuse |
| O3 | Wave-level vs stage-level scope note | 0 | In reference doc |
| O4 | Sprint contract validation (criteria testability check) | 0-1 | Low |

### Benchmark Strategy for Sub-Variants

To validate Variant D's predicted improvement over Variant B:
1. Run EvoBench with Variant D text (13 lines) replacing current Card 1+2 text (21 lines)
2. Run with recommended P2-P3 hybrid priority scheme
3. Compare against baseline and Variant B across all 17 scenarios
4. Key scenarios to watch: migration_upgrade (budget-sensitive), refactor_tech_debt (gen-verify primary user), perf_optimization (gen-verify primary user)

Expected outcome: Δ composite -0.30 to -0.40 (improvement over Variant B's -0.52)

---

## Appendix A: Research Sources

| # | Search Query | Key Source | Date |
|---|---|---|---|
| 1 | "Anthropic generator verifier pattern implementation details 2026" | Anthropic engineering blog, NewClawTimes analysis | 2026-03-31 |
| 2 | "AdaptOrch DAG topology routing algorithm" | arXiv 2602.16873 | 2026-02 |
| 3 | "multi-agent coordination mode selection criteria 2026" | DeMAC (ACL), Augment Code, AdaptOrch | 2026 |
| 4 | "generator verifier loop termination strategy LLM agent" | EmergentMind, Medium (Agent Loops), arXiv | 2026 |
| 5 | "wave-level vs stage-level convergence tradeoffs" | AgentOrchestra, production patterns | 2026 |
| 6 | "context-centric decomposition vs problem-centric" | Oboe, huuhka.net, arXiv DACS | 2026 |
| 7 | "Anthropic harness design planner generator evaluator termination" | Anthropic blog, Victorino analysis, dev.to | 2026 |

## Appendix B: Full Variant Text Summary

| Variant | Lines (content) | Lines (total w/blanks) | Tokens | Info Completeness | Predicted Δ Composite |
|---------|:-:|:-:|:-:|:-:|:-:|
| A Minimal | 11 | ~13 | ~140 | 70% | -0.25 to -0.35 |
| B Standard | 16 | ~21 | ~240 | 100% | -0.52 (actual) |
| C Extended | 21 | ~26 | ~310 | 120% | -0.70 to -0.85 |
| **D Compact** | **13** | **~15** | **~185** | **100%** | **-0.30 to -0.40** |

## Appendix C: Priority Scheme Impact Matrix

| Profile | P1 Aggressive | P2 Conservative | P3 Selective | Recommended (P2+P3 hybrid) |
|---------|:-:|:-:|:-:|:-:|
| hotfix | skip | skip | skip | skip |
| feature | critical | important | supplementary | supplementary |
| research | skip | skip | skip | skip |
| refactor | critical | critical | critical | critical |
| review | important | supplementary | supplementary | supplementary |
| design | important | supplementary | supplementary | supplementary |
| skill-optimization | critical | important | critical | critical |
| migration | critical | important | critical | **important** |
| security-audit | critical | critical | critical | critical |
| documentation | skip | skip | skip | skip |
| spike-poc | skip | skip | skip | skip |
| rdrr | critical | critical | critical | critical |
| demo-showcase | important | skip | supplementary | supplementary |
| perf-optimization | critical | critical | critical | critical |
| dependency-setup | skip | skip | skip | skip |
| onboarding | skip | skip | skip | skip |
