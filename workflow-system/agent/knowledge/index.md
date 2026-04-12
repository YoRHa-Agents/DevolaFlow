# Knowledge Index

Central catalog of DevolaFlow knowledge pages. Task Agents read this index first, then load relevant pages.

| Page | Load When | Token Est. |
|------|-----------|-----------|
| `principle-mapping.md` | Quality review, gate evaluation, SOLID/TDD/DDD task focus | ~800 |
| `code-rules-mapping.md` | Task dispatch with `applicable_rules`, rule loading strategy config | ~600 |
| `reference-dependencies.yaml` | Self-update workflow, reference tracking, external integration | ~500 |
| `learnings/operational.jsonl` | Any task execution (auto-loaded via context profiles if enabled) | ~500 max |

## Auto-Update Protocol

When a knowledge page is created or significantly modified:
1. Add or update its entry in this index
2. Verify the "Load When" condition accurately reflects usage
3. Update the token estimate if content size changed significantly
