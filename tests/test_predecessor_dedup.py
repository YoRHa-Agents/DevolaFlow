"""Predecessor summary delta-compression tests (v9.7.0 PV-02 + v15.0.0 G-007).

Couples the production landing of
:func:`devolaflow.compressor.transforms.dedup_predecessor_summaries` to
a small set of pytest-native regression guards. Seven concerns are
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
   `entries: list[{pred_index, hash, ref, digest}]`).
7. **G-007 self-containment (v15.0.0)** — every emitted reference is
   resolvable INTRA-PAYLOAD via the ledger entry's self-contained
   ``digest``; ref-shaped summaries are never re-deduplicated or
   indexed; the contract docs (``schemas/lean-dispatch.yaml`` pos-17 +
   ``references/context-isolation.md`` §10) pin the coherent contract.
   Sources: ``.local/research/v14.2.0_gap_analysis.md`` §2.1 G-007 +
   finding F-P4-4 in
   ``.local/research/v15-cycle_design_review_product.md`` §4.

W-17 NEW-test-function tally: 7 new test functions at v9.7.0 PV-02;
+4 new test functions at v15.0.0 (G-007 self-containment guards).
Parametrize expansions are absent — the regression guards are
deliberately separate so a failure surface identifies which axis broke.
"""

from __future__ import annotations

from pathlib import Path

from devolaflow.compressor import (
    DEDUP_DIGEST_MAX_CHARS,
    DEDUP_HASH_PREFIX_LENGTH,
    _build_dedup_index,
    _digest_summary,
    _hash_summary,
    assert_dispatch_layout,
    dedup_predecessor_summaries,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]


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
    # v15.0.0 G-007: the entry carries the self-contained digest of the
    # replaced summary. Summaries at or under DEDUP_DIGEST_MAX_CHARS
    # travel verbatim — zero input-quality loss for the fresh L3.
    assert entry["digest"] == "alpha-summary-text", (
        "G-007 violation: ledger entry MUST carry the self-contained verbatim "
        "digest of the replaced summary"
    )


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
    # v15.0.0 G-007: the chained-round entry is self-contained too.
    assert ledger["entries"][0]["digest"] == "beta-new"


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


# ---------------------------------------------------------------------------
# v15.0.0 G-007 self-containment guards (design fix for finding F-P4-4).
#
# A fresh round-N L3 spawns with an EMPTY context (context-isolation.md §2
# Mechanism 1) — it can never resolve a reference into a conversation
# history it never had. The 4 tests below pin the coherence-by-construction
# contract: every emitted reference resolves INTRA-PAYLOAD via the ledger
# entry's self-contained ``digest``.
# ---------------------------------------------------------------------------


def test_every_emitted_reference_is_intra_payload_resolvable() -> None:
    """G-007 negative guard: an L3-unresolvable reference CANNOT be emitted.

    Structural invariant over the emitting path: for EVERY pred entry
    whose summary was rewritten to a ``"@round-…"`` reference, the SAME
    payload's ledger MUST carry exactly one entry with a matching
    ``ref`` and a non-empty, non-ref-shaped ``digest``. Resolution uses
    nothing but the returned payload — no ``prior_rounds`` access.
    """
    round1 = _round_payload(1, ["alpha-summary-text", "beta-summary-text", "gamma-fresh"])
    round2 = _round_payload(2, ["alpha-summary-text", "beta-summary-text", "delta-new"])

    result = dedup_predecessor_summaries(round2, round_num=2, prior_rounds=[round1])

    refs = [
        entry["summary"]
        for entry in result["pred"]
        if isinstance(entry.get("summary"), str) and entry["summary"].startswith("@round-")
    ]
    assert refs, "fixture must produce at least one dedup hit"
    ledger_entries = result["predecessor_dedup_ledger"]["entries"]
    # One ledger entry per emitted reference — no orphan refs, no orphan entries.
    assert len(ledger_entries) == len(refs)
    by_ref = {entry["ref"]: entry for entry in ledger_entries}
    for ref in refs:
        entry = by_ref.get(ref)
        assert entry is not None, (
            f"G-007 violation: reference {ref!r} has NO same-payload ledger entry — "
            "a fresh L3 cannot resolve it"
        )
        digest = entry["digest"]
        assert isinstance(digest, str) and digest, (
            f"G-007 violation: ledger entry for {ref!r} lacks a self-contained digest"
        )
        assert not digest.startswith("@round-"), (
            f"G-007 violation: digest for {ref!r} is itself a reference — unresolvable"
        )


def test_ref_shaped_summary_is_never_re_deduplicated() -> None:
    """G-007: chained ``ref → ref`` emission is impossible.

    A caller that reuses a deduplicated round-2 payload verbatim as the
    round-3 ``pred`` content presents a ref-shaped summary to the
    emitter. The emitter MUST preserve it untouched (no re-dedup, no
    ledger entry, no ref-shaped digest), and the index builder MUST NOT
    index ref-shaped summaries from the prior round.
    """
    round1 = _round_payload(1, ["alpha-summary-text"])
    # "beta-new" is FRESH at round 2 — it survives verbatim while
    # "alpha-summary-text" dedups to a reference.
    round2 = _round_payload(2, ["alpha-summary-text", "beta-new"])
    round2_dedupd = dedup_predecessor_summaries(round2, round_num=2, prior_rounds=[round1])
    assert round2_dedupd["pred"][0]["summary"] == "@round-1:pred-0"
    assert round2_dedupd["pred"][1]["summary"] == "beta-new"

    # Index built from the deduplicated round-2 payload skips ref-shaped
    # summaries — only "beta-new" is indexable.
    index = _build_dedup_index(round2_dedupd)
    assert _hash_summary("@round-1:pred-0") not in index, (
        "G-007 violation: ref-shaped summary was indexed — a later round could "
        "dedup against a reference"
    )
    assert _hash_summary("beta-new") in index

    # Round 3 reuses the deduplicated round-2 payload verbatim.
    round3 = _round_payload(3, ["@round-1:pred-0", "beta-new"])
    result = dedup_predecessor_summaries(round3, round_num=3, prior_rounds=[round2_dedupd])

    # The ref-shaped summary is preserved untouched; only "beta-new" deduped.
    assert result["pred"][0]["summary"] == "@round-1:pred-0"
    assert result["pred"][1]["summary"] == "@round-2:pred-1"
    ledger_entries = result["predecessor_dedup_ledger"]["entries"]
    assert len(ledger_entries) == 1
    assert ledger_entries[0]["pred_index"] == 1
    assert ledger_entries[0]["digest"] == "beta-new"
    for entry in ledger_entries:
        assert not entry["digest"].startswith("@round-")


def test_digest_is_bounded_verbatim_key_facts_for_long_summaries() -> None:
    """G-007 digest shape: bounded, verbatim, deterministic.

    Tier 1 — short summaries travel verbatim. Tier 2 — long summaries
    collapse to the document-order key_facts extraction (verbatim
    entity values joined by ``"; "``). Tier 3 — entity-free long
    summaries fall back to the bounded verbatim head slice. All tiers
    are bytewise deterministic across calls (CO-2).
    """
    # Tier 1: short summary → verbatim identity.
    short = "S04_W01 scaffolded src/config/mod.rs"
    assert _digest_summary(short) == short

    # Tier 2: long summary with seeded preserve-list entities.
    long_with_entities = (
        "The refactor touched src/devolaflow/compressor/transforms.py and "
        "bumped the package to v15.0.0 while keeping coverage at 94.2%. "
    ) + ("Filler prose that dilutes information density. " * 12)
    assert len(long_with_entities) > DEDUP_DIGEST_MAX_CHARS
    digest = _digest_summary(long_with_entities)
    assert len(digest) <= DEDUP_DIGEST_MAX_CHARS
    assert "src/devolaflow/compressor/transforms.py" in digest, (
        "key_facts digest MUST carry the file path verbatim (CO-2)"
    )
    assert "v15.0.0" in digest
    # Deterministic: bytewise identical across calls.
    assert _digest_summary(long_with_entities) == digest

    # Tier 3: entity-free long summary → bounded verbatim head slice.
    long_no_entities = "plain narrative prose with no extractable entities " * 20
    assert len(long_no_entities) > DEDUP_DIGEST_MAX_CHARS
    fallback = _digest_summary(long_no_entities)
    assert fallback == long_no_entities[:DEDUP_DIGEST_MAX_CHARS]

    # End-to-end: the emitter wires the same digest into the ledger entry.
    round1 = _round_payload(1, [long_with_entities])
    round2 = _round_payload(2, [long_with_entities])
    result = dedup_predecessor_summaries(round2, round_num=2, prior_rounds=[round1])
    assert result["predecessor_dedup_ledger"]["entries"][0]["digest"] == digest


def test_pos17_contract_docs_pin_self_contained_digest() -> None:
    """G-007 doc coherence: schema + context-isolation.md describe the fix.

    Acceptance criterion 1 of the v15.0.0 G-007 design fix requires the
    pos-17 contract docs and the Context Isolation reference to teach
    ONE coherent contract. Pins: (a) the schema's ``entries`` field
    documents ``digest``; (b) the schema description names the
    self-containment contract; (c) context-isolation.md §10 carries the
    G-007 self-containment passage while the §4 "MUST NOT leak" row 1
    (conversation history) stays authoritative.
    """
    import yaml

    schema = yaml.safe_load(
        (_REPO_ROOT / "schemas" / "lean-dispatch.yaml").read_text(encoding="utf-8")
    )
    ledger_spec = schema["lean_format_spec"]["predecessor_dedup_ledger"]
    assert "digest" in ledger_spec["fields"]["entries"], (
        "lean-dispatch.yaml pos-17 entries field MUST document the digest sub-field"
    )
    assert "SELF-CONTAINED" in ledger_spec["description"], (
        "lean-dispatch.yaml pos-17 description MUST name the self-containment contract"
    )

    isolation_md = (
        _REPO_ROOT / "workflow-system" / "agent" / "references" / "context-isolation.md"
    ).read_text(encoding="utf-8")
    assert "`predecessor_dedup_ledger` self-containment (v15.0.0, G-007 / F-P4-4):" in (
        isolation_md
    ), "context-isolation.md §10 MUST carry the G-007 self-containment passage"
    assert "**Conversation history**" in isolation_md, (
        "context-isolation.md §4 'MUST NOT leak' row 1 MUST stay authoritative"
    )
