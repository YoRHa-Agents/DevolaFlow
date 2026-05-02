"""Predecessor summary delta-compression tests (v9.7.0 PV-02).

Couples the production landing of
:func:`devolaflow.compressor.transforms.dedup_predecessor_summaries` to
a small set of pytest-native regression guards. Six concerns are
covered:

1. **Round-1 pass-through** — round 1 dispatches MUST be byte-identical
   to the input payload. No ledger field added. Verifies the
   ``round_num <= 1`` short-circuit.
2. **Round-2 dedup hit** — when round 2's ``pred[i].summary`` matches a
   round 1 hash, the summary is replaced by a canonical reference and
   the ledger records the hit.
3. **Round-2 no-hit** — when round 2's summaries are all NEW (no
   matches against round 1), the ledger field is OMITTED so the
   dispatch stays byte-identical to a no-dedup round-N>1 dispatch.
4. **Cross-round stability** — chained rounds (1 → 2 → 3) work
   correctly; the round-3 dedup index reads from the round-2 ledger
   plus payload, producing transitively-deduplicated content.
5. **Hash collision graceful fallback** — non-string / empty-string
   summaries are skipped (graceful S-5 fallback) without raising.
6. **Ledger schema** — the emitted ledger conforms to the schema
   declared in ``schemas/lean-dispatch.yaml`` (`round_num: int`,
   `entries: list[{pred_index, hash, ref}]`).

W-17 NEW-test-function tally: this module adds 7 new test functions.
Parametrize expansions are absent — the regression guards are
deliberately separate so a failure surface identifies which axis broke.
"""

from __future__ import annotations

from devolaflow.compressor import (
    DEDUP_HASH_PREFIX_LENGTH,
    _build_dedup_index,
    _hash_summary,
    assert_dispatch_layout,
    dedup_predecessor_summaries,
)


def _round_payload(round_num: int, summaries: list[str]) -> dict:
    """Build a minimal canonical-order payload for round ``round_num`` with the
    given pred summaries.

    Mirrors the v9.6.0 / v9.7.0 dispatch shape: includes the FROZEN
    PREFIX positions 1-12 plus ``reinforce.round`` so the dedup helper
    can read the round number from the prior payload (per
    :func:`_build_dedup_index`).
    """
    return {
        "hdr": {"id": f"d-r{round_num}", "parent": "stage-test", "layer": "wave"},
        "task": {"id": "T-DEDUP-001", "type": "test", "title": "predecessor dedup"},
        "goal": "validate dedup_predecessor_summaries",
        "assumptions": [],
        "pred": [{"name": f"pred-{i}", "summary": s} for i, s in enumerate(summaries)],
        "files": [],
        "rules": {},
        "shared": "",
        "accept": [],
        "reinforce": {"round": round_num},
        "verify_cfg": {},
        "gate": {},
    }


def test_round_1_is_pass_through() -> None:
    """Round 1 dispatches MUST be byte-identical to the input payload.

    No prior rounds means no dedup state; the helper short-circuits
    via the ``round_num <= 1`` guard. The returned payload IS the input
    object (same identity); no ``predecessor_dedup_ledger`` is added.
    """
    payload = _round_payload(1, ["A", "B", "C"])
    result = dedup_predecessor_summaries(payload, round_num=1, prior_rounds=None)
    assert result is payload, (
        "round 1 MUST short-circuit to identity return — dedup helper allocated a copy"
    )
    assert "predecessor_dedup_ledger" not in result, "round 1 MUST NOT add a ledger field"

    # Also: round 1 with non-empty prior_rounds is ALSO a no-op (defensive).
    bogus_prior = [_round_payload(1, ["something else"])]
    result2 = dedup_predecessor_summaries(payload, round_num=1, prior_rounds=bogus_prior)
    assert result2 is payload


def test_round_2_dedup_hit_emits_ledger_and_reference() -> None:
    """Round 2's matching summaries are replaced by ``"@round-N-1:pred-K"`` refs."""
    round1 = _round_payload(1, ["alpha-summary-text", "beta-summary-text"])
    round2 = _round_payload(2, ["alpha-summary-text", "fresh-summary-text"])

    result = dedup_predecessor_summaries(round2, round_num=2, prior_rounds=[round1])

    # Index 0 hit: pred[0].summary becomes the canonical reference.
    assert result["pred"][0]["summary"] == "@round-1:pred-0", (
        f"expected dedup hit for pred[0], got {result['pred'][0]['summary']!r}"
    )
    # Index 1 miss: pred[1].summary stays verbatim.
    assert result["pred"][1]["summary"] == "fresh-summary-text"
    # Ledger reflects exactly one hit.
    ledger = result["predecessor_dedup_ledger"]
    assert ledger["round_num"] == 2
    assert len(ledger["entries"]) == 1
    entry = ledger["entries"][0]
    assert entry["pred_index"] == 0
    assert entry["ref"] == "@round-1:pred-0"
    assert len(entry["hash"]) == DEDUP_HASH_PREFIX_LENGTH
    assert entry["hash"] == _hash_summary("alpha-summary-text")


def test_round_2_no_hit_omits_ledger() -> None:
    """When round 2 has no matching summaries, the ledger MUST be OMITTED.

    Preserves byte-identical contract for round-N>1 dispatches that
    happen to have no duplicates — a no-hit round-N>1 dispatch is byte-
    identical to the v9.6.0 / v9.3.0 / v8.4.0 baselines.
    """
    round1 = _round_payload(1, ["alpha", "beta"])
    round2 = _round_payload(2, ["gamma", "delta"])

    result = dedup_predecessor_summaries(round2, round_num=2, prior_rounds=[round1])

    assert "predecessor_dedup_ledger" not in result, (
        "round 2 with NO dedup hits MUST OMIT the ledger field"
    )
    # The pred entries must be byte-identical (no rewriting happened).
    assert result["pred"][0]["summary"] == "gamma"
    assert result["pred"][1]["summary"] == "delta"


def test_chained_rounds_round_3_dedups_against_round_2() -> None:
    """Round 3 reads round 2's payload to build its dedup index (transitivity).

    The helper uses the LAST element of ``prior_rounds`` for the dedup
    index. A chained 1 → 2 → 3 dispatch tests that the most-recent
    prior round drives the dedup, not the original round 1.
    """
    round1 = _round_payload(1, ["alpha"])
    round2 = _round_payload(2, ["alpha", "beta-new"])
    # Apply round-2 dedup so round2 has the canonical reference + ledger.
    round2_dedupd = dedup_predecessor_summaries(round2, round_num=2, prior_rounds=[round1])
    # Round 3 carries beta-new (matches round 2's pred-1) plus a fresh one.
    round3 = _round_payload(3, ["beta-new", "gamma-totally-fresh"])

    result = dedup_predecessor_summaries(round3, round_num=3, prior_rounds=[round1, round2_dedupd])

    # pred[0].summary should now be the round-2:pred-1 reference.
    assert result["pred"][0]["summary"] == "@round-2:pred-1", (
        f"expected round-3 to dedup against round-2 (transitivity); "
        f"got {result['pred'][0]['summary']!r}"
    )
    # pred[1] is fresh — no dedup.
    assert result["pred"][1]["summary"] == "gamma-totally-fresh"
    ledger = result["predecessor_dedup_ledger"]
    assert ledger["round_num"] == 3
    assert len(ledger["entries"]) == 1
    assert ledger["entries"][0]["pred_index"] == 0


def test_empty_or_non_string_summary_skipped_gracefully() -> None:
    """Per S-5, empty / non-string summaries are skipped (no raise, no ledger)."""
    round1 = _round_payload(1, ["alpha"])
    # Round 2: pred[0] empty, pred[1] non-string (defensive — wouldn't normally
    # happen but the helper must not raise).
    round2 = {
        "hdr": {"id": "d-r2"},
        "task": {"id": "T-001"},
        "goal": "test",
        "assumptions": [],
        "pred": [
            {"name": "pred-0", "summary": ""},
            {"name": "pred-1", "summary": 42},  # type: ignore[dict-item]
            {"name": "pred-2", "summary": "alpha"},
        ],
        "files": [],
        "rules": {},
        "shared": "",
        "accept": [],
        "reinforce": {"round": 2},
        "verify_cfg": {},
        "gate": {},
    }

    result = dedup_predecessor_summaries(round2, round_num=2, prior_rounds=[round1])

    # pred[0] / pred[1] preserved verbatim; pred[2] deduped.
    assert result["pred"][0]["summary"] == ""
    assert result["pred"][1]["summary"] == 42
    assert result["pred"][2]["summary"] == "@round-1:pred-0"
    # Ledger has only the one valid hit.
    assert len(result["predecessor_dedup_ledger"]["entries"]) == 1
    assert result["predecessor_dedup_ledger"]["entries"][0]["pred_index"] == 2


def test_dedup_ledger_passes_assert_dispatch_layout() -> None:
    """A round-2 deduped payload MUST validate via ``assert_dispatch_layout``.

    The new ``predecessor_dedup_ledger`` field is at canonical position 17
    of ``DEFAULT_DISPATCH_LAYOUT`` per A-2.2. ``assert_dispatch_layout``
    treats it as a recognised key (no DispatchLayoutError raised) and
    enforces it appears AFTER ``change_context`` (position 16) when
    both are present.
    """
    round1 = _round_payload(1, ["alpha"])
    round2 = _round_payload(2, ["alpha"])
    result = dedup_predecessor_summaries(round2, round_num=2, prior_rounds=[round1])

    # Should not raise.
    assert assert_dispatch_layout(result) is None


def test_invalid_args_raise_explicitly() -> None:
    """Per S-5, bad arg shapes raise rather than silently coercing."""
    import pytest

    with pytest.raises(TypeError):
        dedup_predecessor_summaries("not a dict", round_num=2, prior_rounds=[])  # type: ignore[arg-type]

    payload = _round_payload(2, ["alpha"])
    with pytest.raises(ValueError):
        dedup_predecessor_summaries(payload, round_num=0, prior_rounds=[])
    with pytest.raises(ValueError):
        dedup_predecessor_summaries(payload, round_num=-3, prior_rounds=[])

    # Malformed prior round payload (non-dict) is graceful — no raise.
    bogus_prior = ["not a dict"]
    result = dedup_predecessor_summaries(
        payload,
        round_num=2,
        prior_rounds=bogus_prior,  # type: ignore[arg-type]
    )
    assert result is payload, (
        "malformed prior-round payload MUST be ignored gracefully (S-5 graceful fallback)"
    )


def test_build_dedup_index_handles_missing_pred() -> None:
    """The internal index builder is robust against missing / non-list pred fields.

    Returns an empty dict (no raise) for: empty payload, missing pred,
    non-list pred, list of non-dicts. This is the helper's S-5
    graceful-fallback contract; the caller (dedup_predecessor_summaries)
    relies on it to skip dedup gracefully when the prior round's payload
    is malformed.
    """
    assert _build_dedup_index({}) == {}
    assert _build_dedup_index({"pred": None}) == {}
    assert _build_dedup_index({"pred": "not a list"}) == {}
    assert _build_dedup_index({"pred": [None, 42, "string"]}) == {}
    assert _build_dedup_index({"pred": [{"summary": ""}]}) == {}

    # Index does NOT carry a round number when reinforce is absent — the ref
    # falls back to "prev" (informational; the receiver only uses the hash).
    idx = _build_dedup_index({"pred": [{"summary": "alpha"}]})
    assert len(idx) == 1
    assert list(idx.values())[0] == "@round-prev:pred-0"
