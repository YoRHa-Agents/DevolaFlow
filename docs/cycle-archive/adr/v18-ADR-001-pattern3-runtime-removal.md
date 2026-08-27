# ADR v18-001 — Remove Pattern 3 dispatch prewiring

## Status

Accepted for v18.0.0.

## Decision

DevolaFlow supports the Inline Tool and Fan-Out subagent patterns. The
experimental `AGENT_POOL_FORWARD` verdict and dispatcher-side
`gate.subagent_pattern` population are removed.

The `gate.subagent_pattern` schema declaration remains as a deprecated,
tolerated tombstone. Tier-A layout witnesses contain historical payloads with
that field, so deleting the declaration would make immutable compatibility
fixtures unreadable. New dispatches omit the field.

## Consequences

- `select_pattern` returns only `INLINE` or `FAN_OUT`; Teams remains an
  operator-education sentinel.
- `populate_cascade_gate_fields` retains deprecated compatibility arguments but
  emits only cascade fields.
- A future pool implementation requires a new SI-1 design covering persistent
  state, ownership, recovery, and schema contracts.
- Historical design and test artifacts remain immutable evidence.
