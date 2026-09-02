# DevolaFlow v30 — philosophy rebuild

This branch (`dev/v30/philosophy_rebuild`) rebuilds DevolaFlow from an empty tree. Nothing from
v24 is carried over implicitly: every prior capability is listed in a benchmark ledger and either
kept, restructured, or explicitly retired, with a recorded reason.

## What changes

- **Philosophy is the first principle of the repository.** Principles are held in hash-chained,
  ratified files under `.devola/philosophy/`; every artifact or method decision must cite one.
  The universal principles are owned by a separate repository,
  [AgentOrganon](https://github.com/shendeguize/AgentOrganon), and arrive here as versioned
  proposals; this repository keeps only the Charter (the form) and its own reflections.
- **One tool, `devola`, owns every managed surface.** Checklists, parking, ledgers, decisions,
  telemetry, and interactions are append-only JSONL written exclusively through the CLI.
  Markdown is a generated view.
- **Three layers, mechanically checked.** `core/` (delivered capability), `harness/` and `tests/`
  (internal scaffolding whose removal leaves the capability intact), and sources
  (`philosophy/`, `docs/`). The capability layer must not depend on the harness.
- **Host-agnostic.** Cursor, Claude Code, Codex, Copilot CLI and dsh are adapter instances;
  engine code never names a host.
- **Names are boundaries.** Every command, file, field, enum, prefix and role carries its
  definition where it is declared; renames retire the old name as a forbidden word.

## Status

Design phase closed (35 grilling rounds). Implementation starts from this commit.
The design record lives in the private goal workspace (`.local/`, ignored) and will surface into
`docs/` only through explicit transformation. The Chinese reader's guide to the philosophy is at
`docs/philosophy/philosophy.zh.md`.

## Lineage

Rebuilt from `main` at v23.0.0; the v24.3.0 capability inventory is the benchmark input.
