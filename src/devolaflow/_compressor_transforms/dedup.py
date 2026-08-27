"""Focused implementation slice for the legacy module."""

# ruff: noqa: F403, F405

from __future__ import annotations

from .common import *  # noqa: F403


def _digest_summary(summary: str) -> str:
    """Self-contained verbatim digest of a deduplicated summary (G-007 fix).

    Pure function: no I/O, no clock, no randomness — bytewise
    deterministic for the same input (CO-2 verbatim safety, same
    contract as :func:`_hash_summary`).

    Three tiers, all verbatim (no paraphrase ever occurs):

    1. ``len(summary) <= DEDUP_DIGEST_MAX_CHARS`` → the summary itself,
       verbatim. Maximal fidelity; the dedup saves nothing for short
       summaries, but the reference stays fully informative.
    2. Longer summaries → key_facts extraction via
       :func:`extract_named_entities` (the 8 structured preserve-list
       classes: file_paths, task_ids, version_strings, commit_hashes,
       metric_values, error_messages, acceptance_criterion_bullets,
       interface_signatures), joined ``"; "`` in document order until
       the next whole entity would exceed the bound.
    3. No extractable entities → verbatim head slice at the bound
       (character-boundary truncation, mirroring
       ``truncate_tool_output``'s convention).

    Never returns a ref-shaped string for non-ref input: callers
    guarantee ``summary`` is real content by guarding with
    :data:`_DEDUP_REF_RE` before deduplicating.
    """
    if len(summary) <= DEDUP_DIGEST_MAX_CHARS:
        return summary
    entities = extract_named_entities(summary)
    parts: list[str] = []
    used = 0
    for entity in entities:
        value = entity["value"]
        cost = len(value) + (2 if parts else 0)
        if used + cost > DEDUP_DIGEST_MAX_CHARS:
            break
        parts.append(value)
        used += cost
    if parts:
        return "; ".join(parts)
    return summary[:DEDUP_DIGEST_MAX_CHARS]


def _hash_summary(summary: str) -> str:
    """Return the canonical 12-char sha256 prefix of ``summary``.

    Pure function: no I/O, no clock, no randomness. Used by both the
    sender (compute hash to compare against prior round's ledger) and
    the receiver (compute hash of the resolved verbatim summary to
    verify the dedup pointer is consistent).

    Returns the empty string for empty input — callers SHOULD branch on
    truthy/falsy to skip dedup for empty summaries (a missing summary
    is canonical absence, not a deduplicatable value).
    """
    import hashlib

    if not summary:
        return ""
    return hashlib.sha256(summary.encode("utf-8")).hexdigest()[:DEDUP_HASH_PREFIX_LENGTH]


def _build_dedup_index(prior_round_payload: dict) -> dict[str, str]:
    """Return ``{hash: "@round-N:pred-K"}`` index from a prior round's payload.

    Walks ``prior_round_payload["pred"]`` (if present), hashes each
    ``summary`` via :func:`_hash_summary`, and builds a lookup keyed by
    the 12-char hash. The reference value embeds the prior round's
    number (read from ``prior_round_payload["reinforce"]["round"]`` when
    present, defaulting to ``"prev"`` when absent — round numbers are
    informational; the receiver only uses the hash to resolve).

    Returns an empty dict when ``prior_round_payload`` lacks a ``pred``
    list (e.g. the very first dispatch, where dedup is a no-op anyway).

    Ref-shaped summaries (matching :data:`_DEDUP_REF_RE` — e.g. a
    prior-round payload that was itself deduplicated) are NEVER indexed:
    they carry no content, and indexing them would let a later round
    dedup against a reference and emit a ref-shaped ``digest`` —
    unresolvable for a fresh L2 and forbidden per the G-007
    self-containment contract.
    """
    pred_list = prior_round_payload.get("pred")
    if not isinstance(pred_list, list) or not pred_list:
        return {}
    reinforce = prior_round_payload.get("reinforce")
    round_label = reinforce.get("round", "prev") if isinstance(reinforce, dict) else "prev"
    index: dict[str, str] = {}
    for k, pred_entry in enumerate(pred_list):
        if not isinstance(pred_entry, dict):
            continue
        summary = pred_entry.get("summary", "")
        if not isinstance(summary, str) or not summary:
            continue
        if _DEDUP_REF_RE.match(summary):
            continue
        h = _hash_summary(summary)
        if not h:
            continue
        # First-seen-wins: a duplicate hash within the same prior round
        # is collapsed to the lowest-index reference (deterministic).
        index.setdefault(h, f"@round-{round_label}:pred-{k}")
    return index


def dedup_predecessor_summaries(
    payload: dict,
    round_num: int,
    prior_rounds: list[dict] | None = None,
) -> dict:
    """Apply hash-based dedup to ``payload["pred"][*].summary`` across rounds.

    When ``round_num <= 1`` (or no ``prior_rounds`` are provided), this
    function is a no-op and returns ``payload`` byte-identical to its
    input. The v9.7.0 schema-v6 ``predecessor_dedup_ledger`` field is
    NOT added — round 1 dispatches preserve the byte-stable v9.6.0 /
    v9.3.0 / v8.4.0 / v8.3.0-PV-05 baselines.

    When ``round_num >= 2`` AND ``prior_rounds`` carries at least one
    payload, the function:

    1. Builds a hash index from the most recent prior round's
       ``pred[*].summary`` via :func:`_build_dedup_index` (ref-shaped
       summaries are never indexed).
    2. For each entry in the current ``payload["pred"]``, computes the
       hash of its ``summary`` and looks it up in the index. Ref-shaped
       summaries (already a ledger reference) are preserved verbatim —
       re-deduplicating them would chain references, which is forbidden
       per G-007.
    3. If a hit is found, replaces the summary with the canonical
       ``"@round-N-1:pred-K"`` reference string AND emits a ledger
       entry recording ``pred_index`` / ``hash`` / ``ref`` / ``digest``.
       The ``digest`` (v15.0.0 G-007 design fix, finding F-P4-4) is the
       self-contained verbatim key_facts digest of the replaced summary
       per :func:`_digest_summary` — the reference resolves
       INTRA-PAYLOAD (``ref → entries[j].digest``) so a fresh L2 never
       needs the round-N-1 dispatch it never saw. The replacement and
       the digest emission happen in the SAME loop iteration: no code
       path can emit a reference without its same-payload digest
       (coherence by construction).
    4. Appends an OPTIONAL ``predecessor_dedup_ledger`` field at the
       canonical position 17 of the payload. Empty entries list (no
       hits) → the ledger field is OMITTED so the dispatch stays
       byte-identical to a no-dedup round-N>1 dispatch.

    Per S-5 (No Silent Failures), an entry with an unhashable summary
    (empty string, non-string type, etc.) is skipped — the original
    summary is preserved verbatim and no ledger entry is emitted for
    it. This is graceful fallback, not a silent silencer; the warning
    surface is the absence of a ledger entry where the caller might
    have expected one.

    Per A-2 cache-layout governance, the field is appended at position
    17 of :data:`devolaflow.compressor.layout.DEFAULT_DISPATCH_LAYOUT`.
    Positions 1-16 are unchanged. The 8 historical multi-baseline
    byte-tests in ``tests/test_layout_invariant_multi_baseline.py``
    continue to pass because the new field's absence is canonical.

    Returns a NEW dict (shallow copy of ``payload`` plus the optional
    ledger) — never mutates the caller's input. Pure function: no I/O,
    no clock, no randomness. Determinism: bytewise identical across
    Python runs for the same inputs (CO-2 verbatim safety).

    Args:
      payload: The dispatch payload. MUST be a dict; ``pred`` MAY be
        absent (no-op) or a list of dicts (each with optional ``summary``).
      round_num: Current round number (1-indexed). Round 1 is a strict
        no-op regardless of ``prior_rounds``.
      prior_rounds: List of prior-round payloads, OR ``None`` (treated
        as empty). Only the LAST element is consulted for dedup; older
        rounds are kept for receiver-side audit but do not contribute
        to the current round's dedup index. ``None`` and ``[]`` are
        equivalent (no-op).

    Raises:
      TypeError: when ``payload`` is not a dict (S-5 — explicit rather
        than silent type coercion).
      ValueError: when ``round_num`` is not a positive int (S-5 —
        explicit rather than silent fallthrough).
    """
    if not isinstance(payload, dict):
        raise TypeError(f"payload must be a dict, got {type(payload).__name__}")
    if not isinstance(round_num, int) or round_num < 1:
        raise ValueError(f"round_num must be a positive int (>= 1), got {round_num!r}")

    if round_num <= 1 or not prior_rounds:
        return payload

    # Use the MOST RECENT prior round's payload for dedup. Older rounds
    # are kept by the caller (e.g., for receiver-side audit) but not
    # consulted here — by construction round N-1's ledger references
    # round N-2, which transitively chains the audit trail.
    prior_payload = prior_rounds[-1]
    if not isinstance(prior_payload, dict):
        # S-5: a malformed prior-round payload is ignored (graceful) but
        # the function does NOT raise — round-N dispatch should not be
        # blocked by a corrupt audit trail. The dedup ledger is OMITTED.
        return payload

    dedup_index = _build_dedup_index(prior_payload)
    if not dedup_index:
        return payload

    current_pred = payload.get("pred")
    if not isinstance(current_pred, list) or not current_pred:
        return payload

    new_pred: list = []
    ledger_entries: list[dict] = []
    for i, pred_entry in enumerate(current_pred):
        if not isinstance(pred_entry, dict):
            new_pred.append(pred_entry)
            continue
        summary = pred_entry.get("summary", "")
        if not isinstance(summary, str) or not summary:
            new_pred.append(pred_entry)
            continue
        if _DEDUP_REF_RE.match(summary):
            # Already a ledger reference (e.g. a deduplicated round-N-1
            # payload reused verbatim by the caller). Re-deduplicating
            # would chain references and yield a ref-shaped digest —
            # unresolvable for a fresh L2, forbidden per G-007.
            new_pred.append(pred_entry)
            continue
        h = _hash_summary(summary)
        ref = dedup_index.get(h)
        if ref is None:
            new_pred.append(pred_entry)
            continue
        # Dedup hit — replace summary with reference, emit ledger entry.
        # The self-contained digest is computed from the very summary
        # being replaced, in the same iteration: a reference without a
        # same-payload digest is impossible by construction (G-007).
        rewritten_entry = dict(pred_entry)
        rewritten_entry["summary"] = ref
        new_pred.append(rewritten_entry)
        ledger_entries.append(
            {"pred_index": i, "hash": h, "ref": ref, "digest": _digest_summary(summary)}
        )

    if not ledger_entries:
        # No hits — return unchanged. Preserves byte-stable v9.6.0 contract
        # for round-N>1 dispatches that happen to have no duplicates.
        return payload

    new_payload = dict(payload)
    new_payload["pred"] = new_pred
    new_payload["predecessor_dedup_ledger"] = {
        "round_num": round_num,
        "entries": ledger_entries,
    }
    return new_payload


__all__ = [
    name
    for name in globals()
    if name not in {"__name__", "__package__", "__loader__", "__spec__", "__builtins__", "__all__"}
]
