# v7-ADR-005 — Learnings v2 Schema: Confidence Decay, Session Pinning, Consolidation

- **Status:** Accepted
- **Date:** 2026-04-17
- **Authors:** Design team L3 task agent for V7.0.0-S02-T01
- **Ships in:** v7.0.3 (see `.local/research/v7.0.0_version_roadmap.md`)
- **Research source:** `.local/research/v7.0.0_context_compression_research.md` §§B.5, F row 7, G row 7, J.5
- **Decides:** Open question K.5 (memory-tool surface area)

## 1. Context

DevolaFlow's existing operational memory lives in
`workflow-system/agent/knowledge/learnings/operational.jsonl` and is
managed by `src/devolaflow/learnings.py`. Today's schema is intentionally
minimal — each entry has `{stage, task_type, key, insight, confidence,
rule_id, timestamp, ttl_days, source_task_id}`. The file is append-only
and filtered at read time by `load_relevant_learnings()` (confidence
floor + TTL expiry + top-N by confidence).

Two operational gaps have accumulated:

1. **Confidence is frozen at write time.** A learning captured once
   with confidence 0.8 stays 0.8 until `promote_learning()` explicitly
   bumps it or TTL expires. There is no mechanism for confidence to
   *decay* when a learning is not re-surfaced over N sessions, so the
   learnings list slowly accumulates stale-but-recent entries.
2. **No session-level consolidation.** At the end of a session, the
   currently-relevant learnings are not promoted; the most-useful
   learning of a session has the same weight as any prior.

Research §B.5 + §F row 7 note that Anthropic's memory tool pattern
treats memory as a *curated* resource — entries are promoted into a
higher tier when re-validated, demoted when stale, and optionally
pinned for a session. Research §J.5 budgets the additive schema
migration at ~250 LOC.

Open question K.5 asks whether we should surface the memory tool as a
Claude-style file-system-shaped tool. The design doc resolves that
question: **no**, we stay with JSONL for v7.x because (a) the hook system
(`check_file_ownership`, `test_on_complete`) already validates JSONL
shape trivially; (b) a file-system tool would double the surface area
without a corresponding workflow gain; (c) this keeps v7 scope tight.

## 2. Decision

### 2.1 Additive schema v2

Extend the `Learning` dataclass in `src/devolaflow/learnings.py` with
**four optional fields**, defaulting to `None` or zero for backwards
compatibility:

```python
@dataclass
class Learning:
    # Existing fields (unchanged):
    stage: str
    task_type: str
    key: str
    insight: str
    confidence: float
    rule_id: str = ""
    timestamp: str = ""
    ttl_days: int = 90
    source_task_id: str = ""

    # New v2 fields (additive, default-safe):
    confidence_half_life_days: int = 30
    # Linear decay: confidence -= (days_since_last_accessed / half_life) * 0.5 per reload cycle.

    last_accessed: str = ""
    # ISO timestamp. Refreshed by load_relevant_learnings() when the entry is returned.

    pinned_for_session: str = ""
    # Non-empty session_id → entry is always surfaced regardless of confidence.

    promotion_count: int = 0
    # How many times this learning has been confirmed by promote_learning() or
    # by consolidate_session().
```

All four fields have **schema-safe defaults**: pre-v7 JSONL entries that
omit these keys still parse via `Learning(**fields)` where
`Learning.__dataclass_fields__` is the filter.

### 2.2 New public functions

```python
def consolidate_session(
    session_id: str,
    session_learnings: list[Learning],
    jsonl_path: Path,
) -> dict:
    """At session end, promote learnings that were USED during the session.

    For each learning in session_learnings:
      - If key+stage+task_type matches a persisted entry: bump its
        confidence by 0.05, increment promotion_count, refresh
        last_accessed.
      - If not matched: capture as a new entry with promotion_count=1.

    Returns {promoted: int, captured: int, skipped: int}.
    """

def decay_confidence(
    jsonl_path: Path,
    half_life_days: int | None = None,
) -> dict:
    """Apply linear confidence decay to every entry that has a last_accessed.

    For each entry:
      delta_days = (now - last_accessed) days
      decay_factor = min(1.0, delta_days / entry.confidence_half_life_days)
      new_confidence = entry.confidence - 0.5 * decay_factor

    Clamps to [0.0, 1.0]. Writes file in-place. Returns {decayed_count,
    dropped_below_floor_count} where dropped_below_floor_count counts
    entries whose confidence fell below 0.1 and were pruned.
    """

def pin_learning_for_session(
    key: str,
    stage: str,
    task_type: str,
    session_id: str,
    jsonl_path: Path,
) -> bool:
    """Mark a specific learning as pinned for a session_id.

    Pinned entries are surfaced by load_relevant_learnings()
    regardless of confidence as long as the filter session_id matches.
    Returns True if a match was found and pinned.
    """
```

### 2.3 Filter changes

`load_relevant_learnings()` gains an optional `session_id: str | None`
parameter. When provided, pinned entries for that session are surfaced
*in addition* to the confidence-sorted top-N. Unpinned entries still
honour `min_confidence`.

### 2.4 Migration

- Existing JSONL file reads unchanged (new fields default).
- First call to `decay_confidence()` on a legacy entry sets
  `last_accessed = entry.timestamp` as a compatibility shim (entries
  accessed before v7.0.3 get their original timestamp as the starting
  `last_accessed`).
- No file rewrite is forced; the migration is lazy, per entry, on
  first touch.

## 3. Consequences

### Positive

- Operational memory becomes *curated* instead of *accumulating*.
  Stale entries naturally decay and drop off without manual pruning.
- Session-level consolidation means "the most-useful learning of this
  session" gets an automatic bump, aligning with Anthropic's memory
  tool pattern.
- Pinning supports cross-round convergence workflows that need to
  keep a specific learning in context regardless of confidence.
- All changes are schema-additive; no existing consumer of
  `operational.jsonl` breaks.

### Negative

- Four new fields → doubled schema size; agents reading raw JSONL for
  debugging have more to scan.
- Decay introduces a time-dependent behaviour that is not obvious
  from the code — SKILL.md gains a short "Decay half-life" paragraph.
- `consolidate_session()` must be called at session end; failure to
  call it means the bump never happens (operational discipline, not
  a code defect).

### Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Decay drops a learning right before it's needed | P2 | Floor at 0.1 (never decay below) rather than 0.0; pinning override exists for critical learnings. |
| `consolidate_session` is never wired into a session-end hook | P2 | Provide a `session_end` entry point in `src/devolaflow/cli.py` with a dedicated test; document in SKILL.md. |
| Legacy JSONL readers parse new fields as string instead of int | P3 | Dataclass `__post_init__` coerces via `int(...)`; writer emits canonical types. |
| Pinning proliferates (every session pins everything) | P3 | `pinned_for_session` is a single string (one session at a time), and SKILL.md guidance reserves pinning for blockers only. |

## 4. Alternatives Considered

### 4a. **File-system memory tool (Claude-style view/create/str_replace/insert/delete/rename)**

Expose a full file-system memory API. **Rejected** per K.5 decision:
(1) hook-based validation already covers JSONL shape, (2) the file-
system API duplicates functionality the `Read`/`Write`/`StrReplace`
tools already provide against the JSONL file, (3) v7 scope is tight.
Revisit in v8.x if learnings-consumption metrics show a workflow gain.

### 4b. **Full rewrite: swap JSONL for SQLite**

Move learnings into a SQLite DB for native indexing. **Rejected**
because (1) SQLite adds a non-stdlib dependency variant (file-locking
quirks on macOS + containerised CI), (2) JSONL diffs cleanly in
git-history reviews, (3) the query workloads are append-heavy and
filter-light — SQLite overkill.

### 4c. **Semantic embedding for similarity retrieval**

Embed each insight and retrieve by cosine similarity. **Rejected**
because (1) embedding inference needs a model call per read, (2) we
already have `task_type` as a strong filter, (3) this introduces
non-determinism into the test path.

### 4d. **Confidence decay only, no consolidation**

Ship decay without `consolidate_session`. **Rejected** — decay alone
drifts all entries downward; without a counter-force, the learnings
file trends toward empty over N sessions. Consolidation is the
necessary counter-force.

## 5. Reversibility

**Cost to undo:** Very low.

- Remove the four new fields from `Learning` (dataclass default
  arguments drop cleanly).
- Remove `consolidate_session`, `decay_confidence`,
  `pin_learning_for_session`.
- Revert `load_relevant_learnings()` signature to pre-v7.

Existing JSONL entries with v2 fields still parse via the filter
(unknown fields dropped). Rollback window: ≤ 1 patch version.

## 6. Test Plan

Tests that would falsify this decision:

1. **`tests/test_learnings.py::test_decay_confidence_linear`** —
   insert an entry with `last_accessed` = now - 15 days,
   `confidence_half_life_days = 30`, initial confidence = 0.8; after
   one `decay_confidence()` pass, confidence = 0.55 (0.8 - 0.5 * 0.5).
2. **`tests/test_learnings.py::test_decay_confidence_floor`** — entry
   decays to 0.05; floored at 0.0 (never negative), and entry is
   dropped when decay crosses 0.1.
3. **`tests/test_learnings.py::test_consolidate_session_promotes_matched`** —
   session uses a learning that already exists in JSONL;
   consolidation bumps confidence by 0.05 and increments
   `promotion_count`.
4. **`tests/test_learnings.py::test_consolidate_session_captures_new`** —
   session uses a new learning; consolidation appends it with
   `promotion_count=1`.
5. **`tests/test_learnings.py::test_pin_for_session`** — pinning
   makes an entry surface regardless of confidence when
   `load_relevant_learnings(session_id=X)` is called.
6. **`tests/test_learnings.py::test_legacy_entry_parses`** — a
   v1-shaped JSONL entry (no new fields) loads without error and
   behaves identically to pre-v7 semantics.
7. **`tests/test_learnings.py::test_migration_last_accessed_shim`** —
   legacy entry with `timestamp` but no `last_accessed` is auto-
   populated on first `decay_confidence()` call.
8. **`tests/test_learnings.py::test_consolidate_session_idempotent`** —
   calling `consolidate_session` twice with the same payload promotes
   only once per call (no double-bump on a single invocation).

Failure of tests #1 or #6 blocks the release.

## 7. Cross-References

- Depends on: **v7-ADR-001** (no schema reordering in downstream
  dispatches that consume learnings).
- Depended on by: no direct dependents; this ADR is a leaf.
- Related rules: `.cursor/rules/change-process-rules.mdc` (CP-2
  coverage floor), `.cursor/rules/self-improve-iteration-rules.mdc`
  (SI-9 reinforcement loop — learnings feed reinforcement).
- Research §: B.5, F row 7, G row 7, J.5, K.5.
