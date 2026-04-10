# EvoBench — Context Density Benchmark Suite

Measures how effectively DevolaFlow's task-adaptive context selector routes
relevant SKILL.md sections to agents based on task type.

**Repository:** https://github.com/YoRHa-Agents/DevolaFlow

## Quick Start

```bash
# Run all scenarios
python -m benchmarks.devolaflow_context.runner --scenario all

# Run with baseline comparison (detects regressions)
python -m benchmarks.devolaflow_context.runner --scenario all --compare-baseline

# Run a single scenario
python -m benchmarks.devolaflow_context.runner --scenario hotfix_jwt

# Generate new baseline after optimization
python -m benchmarks.devolaflow_context.runner --generate-baseline

# Output raw JSON for CI
python -m benchmarks.devolaflow_context.runner --scenario all --json
```

## Scoring Dimensions

| Dimension | Weight | What It Measures |
|-----------|--------|-----------------|
| section_relevance | 40% | Fraction of expected sections that were selected |
| information_density | 30% | Relevance * budget utilization (quality per token) |
| 1 - noise_ratio | 20% | Fraction of selected sections that are NOT noise |
| budget_utilization | 10% | How much of the token budget is actually used |

**Composite score** = weighted sum, range 0-100.

## Adding a Scenario

Create a YAML file in `scenarios/`:

```yaml
name: "my_scenario"
task_type: "hotfix"  # maps to a context profile
description: "What this scenario tests"

expected_sections:    # sections that SHOULD be selected
  - quick_action_decision
  - context_isolation

unwanted_sections:    # sections that should NOT appear (noise)
  - stage_primitives
  - convergence_loop

quality_thresholds:
  min_composite: 50.0
  max_noise_ratio: 0.3
  min_relevance: 0.5
```

## Baselines

Baseline results are stored in `baselines/v2.1.0_baseline.json`. When running
with `--compare-baseline`, a regression is flagged if the composite score drops
more than 5% below the baseline for any scenario.

To update the baseline after making improvements:

```bash
python -m benchmarks.devolaflow_context.runner --generate-baseline
```

## Running in Tests

```bash
python -m pytest tests/test_benchmarks.py -v
```

The test suite verifies:
- All scenarios load and parse correctly
- The evaluator produces valid scores
- Baseline comparison detects regressions
- No scenario regresses below quality thresholds
