---
parent: v16-checklist-rounds
schema_version: 1
total_items: 3
checked: 0
priority_dist: {P0: 1, P1: 1, P2: 1}
reverted_open: 0
---

# Checklist

## G1: Keep v16 workspace state internally consistent
- [ ] C-G1.1 (P0) All six v16 fixture artifacts parse under their declared schemas
      verify: `python -m pytest tests/test_agent_workspace_schemas.py -q`
- [ ] C-G1.2 (P1) Checklist and status counters remain aligned at zero of three
      verify: metric: checklist.checked == STATUS.checklist_checked == 0 and checklist.total_items == STATUS.checklist_total == 3

## G2: Authorize bounded checklist-round execution
- [ ] C-G2.1 (P2) The signed preflight hash matches the project configuration bytes
      verify: metric: sha256(tests/fixtures/agent-workspace/v16/project_config.yaml) == preflight.project_config_hash
