# Design Documents

This directory contains both current operational design and historical
research/design inputs. Historical documents preserve rationale and evolution
evidence; they are not runtime instructions.

## Current Operational Design

- [Release workflow](design_release_workflow.md) — current tag, GitHub Release,
  npm publication, and path-filtered Pages deployment design.

The current normative runtime contract lives outside this directory:

- [DevolaFlow SKILL](../../workflow-system/agent/SKILL.md)
- [Three-layer agent hierarchy](../../workflow-system/agent/references/agent-hierarchy.md)
- [Checklist-round execution protocol](../../workflow-system/agent/references/execution-protocol.md)
- [Registry-v3 meta-framework](../../workflow-system/agent/references/meta-framework.md)
- [Message schemas](../../schemas/)
- [Runtime implementation](../../src/devolaflow/)

## Historical Design and Research

### Superseded Pre-v16 Designs

These documents describe retired four-layer, stage-agent, or fixed stage-DAG
architecture. Their original bodies remain as historical evidence:

- [Unified workflow specification](workflow_specification.md)
- [Agent hierarchy and team architecture](design_agent_hierarchy.md)
- [Workflow meta-framework](design_meta_framework.md)
- [Delivery architecture](design_delivery_architecture.md)
- [Dual-system architecture](design_dual_system.md)
- [Task decomposition and gate mechanism](design_decomposition_gate.md)
- [Execution protocol](design_execution_protocol.md)
- [Repository mode system](design_repo_modes.md)

### Historical Research and Inputs

These self-contained research/work-product documents informed earlier designs;
they do not define current runtime behavior:

- [Project desires](desires.md)
- [Agent framework research](wp1_frameworks_research.md)
- [Local pattern extraction](wp2_local_patterns.md)
- [Workflow type research](wp3_workflow_types.md)
- [Research synthesis](research_synthesis_report.md)
- [Task workflow framework research](task_workflow_frameworks_research.md)
