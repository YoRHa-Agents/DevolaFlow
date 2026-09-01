---
id: "agent/references/meta-framework"
version: "1.0.0"
purpose: >
  Defines registry-v3 intent routing, the 26 declarative checklist seeds,
  the sole change-driven runtime, seed provenance and four-draft materialization,
  compatibility aliases, and the historical primitive taxonomy.
triggers:
  - "selecting checklist seed"
  - "understanding registry v3"
  - "authoring checklist seed"
tier: 2
token_estimate: 2800
dependencies:
  - "agent/SKILL.md"
last_updated: "2026-08-26"
---

# Meta-Framework Reference

## 1. Current Model

Registry schema v3 separates decomposition knowledge from execution:

```text
user intent
  → TemplateRegistry.load_seed(<mode>)
    → materialized entrance.md + goal.md + checklist.md + preflight.md
      → TemplateRegistry.load_template("change-driven")
        → propose → preflight → bounded checklist rounds → archive
```

The shipped registry contains:

- **26 checklist seeds**;
- **1 executable path**, `builtin/change-driven.yaml`;
- **0 executable composition DAGs**.

The 26 workflow names remain useful as intent modes. They no
longer prescribe stage order.

## 2. Registry v3 Contract

`workflow-system/agent/templates/registry.yaml` has two catalog blocks:

| Block | Count | Meaning |
|---|---:|---|
| `compositions` | 19 | Historical composition names, now seed-only |
| `templates` | 7 | Historical survivor names, all with seeds |

Every entry declares:

```yaml
- name: security-audit
  seed: seeds/security-audit.yaml
  category: composite
  tags: [security, audit, vulnerability, CVE, scan]
  description: "Threat modeling, scanning, remediation, and verification knowledge."
```

Only the `change-driven` entry additionally declares:

```yaml
path: builtin/change-driven.yaml
```

No other entry may declare an executable path.

### 2.1 The 26 modes

Seed-only names from the `compositions` block:

1. `hotfix`
2. `research-only`
3. `design-only`
4. `documentation-only`
5. `spike-poc`
6. `refactoring`
7. `feature-enhancement`
8. `full-pipeline`
9. `performance-optimization`
10. `security-audit`
11. `research-design-review-refine`
12. `dependency-setup`
13. `onboarding`
14. `demo-showcase`
15. `product-verification`
16. `entropy-cleanup`
17. `local-archive`
18. `harness-construction`
19. `pathfinder`

Names retained in the `templates` block, each still backed by a seed:

20. `migration`
21. `skill-optimization`
22. `self-update`
23. `nines-assisted`
24. `repo-init`
25. `change-driven`
26. `web-design`

The block distinction preserves catalog compatibility. It does not imply two
execution mechanisms.

#### 2.2.1 Multi-team codebase analysis pattern (v9.6.0 — understand-anything integration)

The v9.6.0 integration with
<https://github.com/Lum1104/Understand-Anything> remains a useful
decomposition pattern: L1 may fan out independent L2 Research Tasks by
subdomain, then dispatch a bounded synthesis Task over their artifact refs.
`merge-subdomain-graphs.py` is the historical helper name retained by that
integration.

“Multi-team” is the external pattern label. Current execution uses fresh L2
Tasks, at most 5 per wave and 7 waves per round; it does not create persistent
teams or a stage DAG.

## 3. Checklist Seed Contract

Each file under `workflow-system/agent/templates/seeds/` is:

```yaml
schema_version: "1.0"
kind: checklist-seed
metadata: {}
placeholders: {}
partitions: []
```

Seeds are declarative decomposition knowledge. They may contain:

- intent keywords and scenario metadata;
- placeholders resolved during materialization;
- presentation partitions;
- concise assertion templates;
- suggested P0/P1/P2 priorities;
- command, metric, or manual verification templates;
- historical `source_stages` provenance.

Seeds MUST NOT contain executable fields such as:

- `stages`;
- `composition`;
- `loops`;
- `gates`;
- `team`;
- `duration_class`;
- `input_mapping`;
- `skip_condition`.

### 3.1 Non-executable provenance

`source_stages` records the historical stage ID and primitive that contributed
an assertion partition:

```yaml
source_stages:
  - id: threat_model
    primitive: research
  - id: scan
    primitive: analyze
```

This is C-3 provenance only:

- preserve IDs and primitive labels verbatim;
- include each historical source stage exactly once in its seed;
- treat ordering as presentation-only;
- never infer runtime dependencies, waves, loops, or gates from the sequence.

Dependencies enter the executable contract only when L0 materializes
checklist item-level `depends` with user confirmation.

### 3.2 Materialization

L0 materializes a seed by:

1. resolving required placeholders;
2. mapping partitions to numbered goals;
3. rendering assertion templates as checklist items;
4. presenting suggested priorities for user confirmation;
5. attaching bounded verification modes;
6. adding item dependencies only when the actual change needs them;
7. assigning repository-relative owned and read-only files;
8. drafting `entrance.md` as the static entry router and artifact inventory; 9. drafting preflight blockers and authorization;
10. validating that no placeholder or executable seed field leaked through; 11. recording W-30 wait bounds, heartbeat/escalation paths, item/task scope of ordinary blocker pauses so unaffected siblings continue;
    classify pauses as `dependency-blocked`, `finding-blocked`, or `wave conflict`.
The four drafts are a user contract, not a workflow template; `entrance.md` routes readers to minimal scenario artifacts and does not encode execution steps, round state, or a stage DAG.

## 4. Loader API

### 4.1 New call path

```python
from devolaflow.template_engine import TemplateRegistry

registry = TemplateRegistry()
seed = registry.load_seed("security-audit")
runtime = registry.load_template("change-driven")
```

`load_seed(name)`:

- loads and validates the registered seed;
- checks metadata name/category parity with registry v3;
- returns `None` for an unknown name;
- caches the validated immutable model.

`load_template("change-driven")`:

- loads the sole shipped checklist-round runtime;
- carries no `checklist_seed` alias metadata;
- returns `None` if the runtime cannot be found.

`discover()` returns catalog metadata for all 26 names without emitting alias
warnings. Discovery does not prove executability.

### 4.2 Retired composition synthesis

Registry-v2 `base`/`steps`/`params` DAG synthesis is retired. On a v3
manifest:

- `TemplateRegistry.compositions()` fails explicitly;
- `load_composition_manifest()` fails explicitly;
- the v16 always-raise synthesis/validation stubs were removed in v17.0.0.

Do not rebuild a DAG from seed partitions or provenance.

## 5. Compatibility Aliases

For one migration window, historical calls such as:

```python
registry.load_template("hotfix")
```

return a deep copy of the `change-driven` runtime with:

- alias name, description, category, and tags from the seed;
- `parameters.checklist_seed.name`;
- `parameters.checklist_seed.path`;
- `parameters.checklist_seed.runtime: change-driven`;
- `parameters.checklist_seed.compatibility_alias: true`.

The registry emits one `ChecklistSeedAliasWarning` and one warning log per
alias per registry instance. The warning directs callers to:

```python
registry.load_seed("hotfix")
registry.load_template("change-driven")
```

Compatibility aliases are deprecated since v16.0.0 and scheduled for removal
in v17.0.0. They preserve caller migration, not old stage behavior.

## 6. Historical Primitive Taxonomy

The 14 primitive names survive as provenance labels and authoring vocabulary:

| Category | Primitives | Seed authoring meaning |
|---|---|---|
| Discover | `research`, `analyze` | Gather or inspect evidence |
| Shape | `design`, `plan` | Define decisions or decomposition knowledge |
| Build | `implement`, `refine` | Change or correct artifacts |
| Verify | `review`, `test`, `validate`, `verify` | Check quality or user-visible behavior |
| Deliver | `release`, `deploy`, `monitor` | Prepare, place, or observe output |
| Control | `gate` | Preserve a historical control/checkpoint source |

Primitive labels do not select AgentTeam, duration, ordering, or runtime gate.
The current checklist assertion, ownership, and verification fields control
execution.

## 7. Intent Selection

Select the seed whose intent keywords best match the user's goal:

| Intent | Seed examples |
|---|---|
| urgent defect | `hotfix` |
| investigation/comparison | `research-only` |
| architecture/API/schema | `design-only` |
| documentation | `documentation-only` |
| experiment | `spike-poc` |
| cleanup/restructure | `refactoring`, `entropy-cleanup` |
| local-task archiving | `local-archive` |
| feature or greenfield build | `feature-enhancement`, `full-pipeline` |
| performance/security | `performance-optimization`, `security-audit` |
| environment/onboarding | `dependency-setup`, `onboarding`, `repo-init` |
| user-facing demo/verification | `demo-showcase`, `product-verification`, `web-design` |
| migration | `migration` |
| harness/evaluation infrastructure | `harness-construction` |
| look-ahead infrastructure reconnaissance | `pathfinder` |
| agent-system optimization | `skill-optimization`, `self-update`, `nines-assisted` |
| lifecycle-specific change | `change-driven` |

High-confidence intent may auto-select a seed. Medium confidence presents
ranked options. Low confidence asks the user before materialization. The
selected seed never changes the runtime: execution remains `change-driven`.

### Template Quick-Reference — Gate Types

This stable heading remains for documentation tooling. "Checklist-round"
means the mode uses the one `change-driven` runtime; no row owns a separate
gate DAG.

| Template | Runtime gate type |
|---|---|
| hotfix | checklist-round |
| research-only | checklist-round |
| design-only | checklist-round |
| documentation-only | checklist-round |
| spike-poc | checklist-round |
| refactoring | checklist-round |
| feature-enhancement | checklist-round |
| full-pipeline | checklist-round |
| performance-optimization | checklist-round |
| security-audit | checklist-round |
| research-design-review-refine | checklist-round |
| dependency-setup | checklist-round |
| onboarding | checklist-round |
| demo-showcase | checklist-round |
| product-verification | checklist-round |
| entropy-cleanup | checklist-round |
| local-archive | checklist-round |
| harness-construction | checklist-round |
| pathfinder | checklist-round |
| retro-digest | checklist-round |
| migration | checklist-round |
| skill-optimization | checklist-round |
| self-update | checklist-round |
| nines-assisted | checklist-round |
| repo-init | checklist-round |
| change-driven | checklist-round |
| web-design | checklist-round |
| workspace-compact | checklist-round |

## 8. Authoring and Validation Checklist

```text
REGISTRY
□ schema_version is "3.0"
□ 19 composition entries + 7 template entries = 26
□ Every entry has exactly one seeds/<name>.yaml
□ Only change-driven declares builtin/change-driven.yaml

SEED
□ kind is checklist-seed and schema_version is "1.0"
□ metadata matches registry name and category
□ Placeholder syntax is exact and fully declared
□ Partitions contain measurable assertions
□ source_stages are complete provenance only
□ No executable fields appear anywhere
□ All paths are repository-relative

CONSUMER
□ Uses load_seed(<mode>)
□ Uses load_template("change-driven") only
□ Confirms priorities, verification, dependencies, and ownership with user
□ Does not infer a fixed DAG from seed order
```
