---
title: "FAQ"
description: "Common questions about checklist rounds, installation scope, updates, and release evidence."
source_files:
  - "SKILL.md"
auto_generated: true
last_synced: "2026-09-01T07:32:53Z"
source_version: "24.2.0"
---

# FAQ

Common questions about checklist rounds, installation scope, updates, and release evidence.

## What does DevolaFlow execute?

It selects one of 28 registry-derived checklist seeds as
decomposition knowledge, materializes a user-confirmed checklist, and executes
that contract through the sole `change-driven` runtime.

## Do the three `all` targets mean the same thing?

No. npm `all` is user-level Cursor plus Claude. Python `devola-init all` is
Cursor, Claude, Copilot, and Codex and excludes `local`. curl `all` installs
all supported host targets plus `local` and excludes `standalone`.

## Which doctor should I run?

- `npx @yorha-agents/devola-flow doctor`: npm-supported user installs.
- `devola-init-doctor`: current Python local workspace.
- `devola-init-doctor --skills`: known copied-skill locations.

The curl installer has no doctor.

## Does updating Python update copied skills?

No. Update the package, then rerun `devola-init local` for a local scaffold or
rerun the desired host target from a source checkout. npm and curl have their
own update commands.

## Is host bridge enforcement automatic?

No. Skill installation and host bridge wiring are separate. Verify a supported
host bridge before setting `DEVOLAFLOW_HOST_ENFORCE=1`.

## Is harness archive rollup automatic?

No. Baseline settlement and archive retention are release policy performed
manually at cycle close. Current runtime does not provide an automatic archive
hook.
