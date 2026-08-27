---
id: "agent/references/host-contract"
version: "17.4.0"
purpose: >
  Define the machine-readable Host Support Contract and the evidence-backed
  meaning of supported host delivery.
triggers:
  - "checking whether a host is supported"
  - "adding a host install channel"
  - "updating hosts.yaml"
  - "reviewing host capability evidence"
tier: 2
token_estimate: 2200
dependencies:
  - "agent/SKILL.md"
  - "agent/references/host-bridges.md"
  - "agent/references/env-flags.md"
last_updated: "2026-08-27"
---

# Host Support Contract

## Purpose

`workflow-system/agent/hosts.yaml` is the single source of truth for host
identity, support tier, delivery floor, and optional capability declarations.
The Python loader is `devolaflow.host_contract`; the install manifest remains
the owner of file-set contents and is a derived install-profile view.

“Supported” is tiered. A guaranteed host satisfies all five floor axes. An
optional axis is supported only when its status and evidence are explicitly
declared; absence is not support.

## Contract shape

The contract is validated by `schemas/host-contract.yaml` and
`devolaflow.host_contract.load_host_contract()`.

### Guaranteed floor

Every Tier-G host declares:

1. `skill_delivery`: delivery kind, manifest file sets, and project/global paths.
2. `instruction_format`: artifact, frontmatter contract, and line/character budget.
3. `install_channels`: at least one real `install.sh`, `devola-init`, or `npm` channel.
4. `doctor`: stamp status and verification kind.
5. `tests`: install parity and adapter-budget verification paths.

### Declared extras

Every host declares all five optional axes:

| Axis | Meaning |
|---|---|
| `boundary_bridge` | Host tool events routed through lifecycle enforcement |
| `session_resume` | Session-start resume event and injection support |
| `subagent_dispatch` | Host-native delegation primitive |
| `mcp` | Host MCP configuration surface |
| `tool_vocabulary` | Host-specific write and shell tool names |

Statuses are closed: `implemented`, `designed`, `broken`, `undeclared`, and
`native`. A bridge marked `implemented` must list fixtures and use
`captured` or `vendor-doc` provenance. `vendor-doc` additionally requires a
`provenance_ref` URL. `synthetic` and `TBD-audit` cannot support an
`implemented` claim.

## Host matrix

| Tier | Hosts | Contract obligation |
|---|---|---|
| Guaranteed | cursor, claude, codex, copilot, kimicode, dsh | Full F1-F5 floor; every extra explicit |
| Community-installable | windsurf, zed, cline, roo | Adapter, budget test, and valid install path |
| Community-build-only | continue, openclaw, gemini, jetbrains, amazon_q, augment, trae | Adapter and budget test; no install or extras claim |

`kimi` is an alias for canonical id `kimicode`. The host set is deliberately
larger than the adapter set: DSH is guaranteed even though it uses a plugin
channel rather than a build adapter.

## Derived views

The manifest continues to own `core`, `references`, and `examples`. Its
`install_profiles` entries must match the `skill_delivery.kind` and `sets`
projection from `hosts.yaml` for every profile currently present. A later
delivery phase may add a new profile; it must add the host entry first and
then update the mirror plus its parity test.

Consumers must not introduce a second host registry. Resolve aliases through
`devolaflow.host_contract.resolve_host()`. Additions to the host domain update
`hosts.yaml`, its schema/loader tests, and the ghost registry in the same
change.

## Evidence and fixture rules

Host-side fixtures are contracts, not illustrative examples:

- `captured`: payload captured from a real host session;
- `vendor-doc`: payload shaped from an upstream official document and linked by
  `provenance_ref`;
- `synthetic`: self-authored shape, useful for negative tests only;
- `TBD-audit`: not yet traced to evidence and temporary only.

Before changing an `implemented` claim, run the host-specific bridge tests and
confirm the fixture's tool names and argument fields against its evidence.
Never upgrade provenance merely to make a test pass.

## Contract revision procedure

Adding a host, capability axis, or install channel follows this sequence:

1. Add or amend the gap/design artifact with the observed host evidence and
   file-level scope.
2. Update `hosts.yaml` and, when needed, `schemas/host-contract.yaml`.
3. Add loader, parity, and ghost-audit coverage before any CHANGELOG claim.
4. Regenerate derived install/documentation views and run their parity tests.
5. Record unsupported or deferred capabilities as explicit `undeclared`,
   `designed`, or `broken` states with a reason.

Adding a new capability axis is a contract revision, not an empty placeholder.
It requires a follow-up rule review and an evidence-backed test surface.
Changes to host-native environment flags still follow
`references/env-flags.md`; this contract introduces no new
`DEVOLAFLOW_*` flag.

## Related surfaces

- `schemas/host-contract.yaml` — closed schema and example
- `workflow-system/agent/hosts.yaml` — canonical registry
- `src/devolaflow/host_contract.py` — loader, alias resolver, and projection
- `tests/test_host_contract.py` — schema and provenance checks
- `tests/test_host_contract_parity.py` — derived-profile parity checks
- `references/host-bridges.md` — bridge-specific event and response protocols
