"""Cache-layout governance — frozen prefix, dispatch layout invariants, LCP computation.

Per A-2 cache-layout governance v2.
"""

from __future__ import annotations

DEFAULT_DISPATCH_LAYOUT: list[str] = [
    "hdr",
    "task",
    "goal",
    "assumptions",
    "pred",
    "files",
    "rules",
    "shared",
    "accept",
    "reinforce",
    "verify_cfg",
    "gate",
    # v7.2.6 (P-06) — appended at position 13 per ADR-001 §2 additive rule.
    # Field shape: [{name: str, root_path: str, primary: bool, branch: str}].
    # Optional — single-repo dispatches may omit it (assert_dispatch_layout
    # treats absence as canonical, preserving v7.0.0 byte-baseline parity).
    "repos",
    # v8.0.0 (P-08) — appended at position 14 per ADR-001 §2 additive rule.
    # Schema version bumped 2 → 3 in schemas/lean-dispatch.yaml. Field shape:
    #   {think_first: bool, simplicity_check: bool, surgical_scope: str,
    #    goal_loop: bool}
    # Optional — dispatches without behavioral injection may omit it
    # (assert_dispatch_layout treats absence as canonical, preserving BOTH
    # the v7.0.0 byte-baseline AND the v7.3.0 byte-baseline parity — proves
    # additivity holds across two schema generations). See
    # ``workflow-system/agent/references/behavioral-guidelines.md`` for the
    # full rule semantics, severity classification, and self-check questions.
    "behavioral_guidelines",
    # v8.0.0 (P-10) — appended at position 15 per ADR-001 §2 additive rule.
    # Schema version bumped 3 → 4 in schemas/lean-dispatch.yaml. Field shape:
    #   [{id: str, description: str, verification_type: str,
    #     verification_cmd: str, metric: str, threshold: str}]
    # Optional — dispatches without structured acceptance criteria may
    # omit it. The legacy ``acceptance_criteria: list[str]`` alias
    # (recognised by ``src/devolaflow/lifecycle/validate_dispatch.py``)
    # is PRESERVED unchanged for R5 backward compatibility per
    # ``.local/research/v8.0.0_patch_plan.md`` §9. assert_dispatch_layout
    # treats absence as canonical (preserves v7.x byte-stable dispatch
    # shape — proves additivity holds across THREE schema generations).
    # See ``src/devolaflow/ac_generator.py`` for the generator and
    # ``src/devolaflow/gate/scorer.py::evaluate_acceptance_criteria_v2``
    # for the auto-evaluator that produces per-criterion verdicts.
    "acceptance_criteria_v2",
    # v8.3.0 (PV-05 / v8.2.5) — appended at position 16 per ADR-001 §2
    # additive rule. Schema version bumped 4 → 5 in
    # schemas/lean-dispatch.yaml. Sources:
    # ``.local/research/v8.3.0_design.md §9`` +
    # ``.local/research/v8.3.0_patch_plan.md §v8.2.5`` +
    # ``.local/research/v8.3.0_gap_analysis.md §2.3 M-006``.
    #
    # Field shape:
    #   change_context:
    #     change_id: str                      # lowercase-kebab-case
    #     active_folder: str                  # ".local/.agent/active/<id>"
    #     state: str                          # PROPOSED | IN_PROGRESS | VERIFYING
    #     spec_delta_target: str              # source-of-truth domain
    #     owned_files_ref: str                # ".local/.agent/active/<id>/owned_files.txt"
    #     acceptance_ref: str                 # ".local/.agent/active/<id>/acceptance.md"
    #
    # Field is OPTIONAL — when absent, the dispatch is a "free-floating"
    # workflow (current v4 behaviour preserved). assert_dispatch_layout
    # treats absence as canonical, so v4-shape callers (and the
    # v7.0.0 / v7.3.0 / v8.0.0-P-08 / v8.0.0-P-10 byte-baselines) ALL
    # CONTINUE TO PASS without modification. R5 backward-compat invariant
    # I-PV05-C / I-PV05-F is the cycle's largest-risk patch contract.
    # See ``src/devolaflow/agent_workspace/change.py::ChangeStore`` for
    # the dataclass + state machine that authors / mutates this payload.
    "change_context",
    # v9.7.0 (PV-02) — appended at position 17 per A-2.2 append-only tail.
    # Schema version bumped 5 → 6 in schemas/lean-dispatch.yaml. Source:
    # ``.local/research/v9.7.0_perf_research.md`` §2 + the v10.0.0 cycle
    # plan §3 v9.7.0 PV-02.
    #
    # Field shape:
    #   predecessor_dedup_ledger:
    #     round_num: int                       # current round number (>= 2)
    #     entries:                             # one per dedup hit
    #       - pred_index: int                  # 0-based index into pred[]
    #         hash: str                        # 12-char sha256 prefix
    #         ref: str                         # "@round-N-1:pred-K" reference
    #
    # When a convergence round N>1 dispatches, the
    # :func:`devolaflow.compressor.transforms.dedup_predecessor_summaries`
    # helper compares each ``pred[i].summary`` against the ledger from
    # round N-1; matching summaries are replaced by ``"@round-N-1:pred-K"``
    # references and the ledger records the dedup hit so the receiver can
    # decompress.
    #
    # Field is OPTIONAL — when absent (round 1, or no dedup hits in round
    # N>1), the dispatch is byte-identical to the v9.6.0 / v9.3.0 / v8.4.0
    # / v8.3.0-PV05 baselines. The 8 historical multi-baseline byte-tests
    # in ``tests/test_layout_invariant_multi_baseline.py`` ALL CONTINUE TO
    # PASS unchanged because the new field's absence is canonical.
    "predecessor_dedup_ledger",
]


class DispatchLayoutError(ValueError):
    """Raised when a dispatch payload's top-level key order violates the
    canonical layout invariant declared in lean-dispatch.yaml."""


# ---------------------------------------------------------------------------
# v9.0.0 PV-02 (v8.4.2) — Cache-Layout Governance v2 (nest-vs-append rule).
#
# FROZEN_PREFIX_V7 is the v7.0.0 canonical 12-key prefix. Per
# ``.local/research/adr/v9-ADR-002-cache-layout-governance-v2.md`` D1, these
# 12 positions are FROZEN — reordering any of them is a release blocker
# (LLM cache-prefix invalidation cost is prohibitive). Positions 13-16 are
# APPEND-ONLY per D2; new top-level keys land at position N+1, never
# inserted into a lower slot.
#
# The nest-vs-append decision rule (D3) biases authors toward NEST under an
# existing canonical key whenever the data shape allows; APPEND is reserved
# for orthogonal payload that does not nest naturally. Historical NEST
# decisions (v8.0.0+): ``gate.token_budget`` (P-03), ``pred[*].compact_directive``
# (P-02), ``pred[*].summary_mode`` / ``summary_max_tokens`` (P-02),
# ``compression_rules.bypass_conditions`` (v7.2.0 C-002),
# ``compression_rules.data_envelope_required`` (v7.2.4 P-02). Historical
# APPEND decisions: ``repos`` (v7.2.6 P-06 -> pos 13),
# ``behavioral_guidelines`` (v8.0.0 P-08 -> pos 14),
# ``acceptance_criteria_v2`` (v8.0.0 P-10 -> pos 15), ``change_context``
# (v8.3.0 PV-05 -> pos 16).
# ---------------------------------------------------------------------------

FROZEN_PREFIX_V7: tuple[str, ...] = (
    "hdr",
    "task",
    "goal",
    "assumptions",
    "pred",
    "files",
    "rules",
    "shared",
    "accept",
    "reinforce",
    "verify_cfg",
    "gate",
)
"""The 12 v7.0.0 canonical top-level keys whose order is FROZEN per v9-ADR-002.

Reordering any of these keys is a release blocker — the LLM cache prefix
invalidates from the first divergent byte. New top-level dispatch keys MUST
be appended at position 13+ (positions 13-16 are append-only). Authors who
need a new field SHOULD prefer NEST under an existing key per the
nest-vs-append decision rule (v9-ADR-002 D3) whenever the data shape allows.
"""

FROZEN_PREFIX_LENGTH: int = len(FROZEN_PREFIX_V7)


class LayoutSpecInvariantError(DispatchLayoutError):
    """Raised when a layout spec's frozen prefix has drifted from
    :data:`FROZEN_PREFIX_V7` (v9-ADR-002 D5 spec-level guard).

    Subclass of :class:`DispatchLayoutError` so legacy callers that catch
    the parent class continue to work (R5 backward-compat). New callers
    that want to distinguish spec-level drift from payload-level reorder
    can catch this class specifically.
    """


def assert_layout_spec_invariant(spec: list[str] | tuple[str, ...] | None = None) -> None:
    """Validate that ``spec``'s first 12 positions match :data:`FROZEN_PREFIX_V7`.

    Per ``.local/research/adr/v9-ADR-002-cache-layout-governance-v2.md`` D1
    + D5: positions 1-12 of any layout spec MUST be byte-identical to the
    v7.0.0 canonical sequence. This is the spec-level guard that catches
    a renamer / re-orderer / sneaky inserter at module-load time, before
    any payload is ever validated.

    The check is REDUNDANT with payload-level validation in the canonical
    case (where ``DEFAULT_DISPATCH_LAYOUT`` is consistent with
    ``FROZEN_PREFIX_V7``); it exists to catch the case where a future PV
    accidentally reorders the constants in this module without bumping
    schema version. Module-import-time invocation pattern::

        from devolaflow.compressor import (
            DEFAULT_DISPATCH_LAYOUT, assert_layout_spec_invariant,
        )
        assert_layout_spec_invariant(DEFAULT_DISPATCH_LAYOUT)

    ``spec=None`` defaults to :data:`DEFAULT_DISPATCH_LAYOUT` (the live
    canonical). Empty list and lists shorter than 12 entries raise
    :class:`LayoutSpecInvariantError`. Lists with the wrong order at any
    of positions 1-12 raise :class:`LayoutSpecInvariantError` identifying
    the first divergent slot.

    Append-only check (D2): if ``len(spec) > 12``, NO check is performed
    on positions 13+. Those slots are append-only by contract; the
    validator does NOT freeze them. Adding a new key past position 12 is
    allowed; reordering positions 13-16 is allowed (though not currently
    practiced); REMOVING a position 13-16 key is allowed only via the
    full deprecation path documented in v9-ADR-002 M4.
    """
    if spec is None:
        spec = list(DEFAULT_DISPATCH_LAYOUT)
    if not isinstance(spec, (list, tuple)):
        raise LayoutSpecInvariantError(
            f"layout spec must be a list or tuple, got {type(spec).__name__}"
        )
    if len(spec) < FROZEN_PREFIX_LENGTH:
        raise LayoutSpecInvariantError(
            f"layout spec length {len(spec)} is shorter than the v7.0.0 frozen "
            f"prefix length {FROZEN_PREFIX_LENGTH}; positions 1-{FROZEN_PREFIX_LENGTH} "
            f"are FROZEN per v9-ADR-002 D1 -- removing any of them is a release blocker"
        )
    for idx, expected in enumerate(FROZEN_PREFIX_V7):
        actual = spec[idx]
        if actual != expected:
            raise LayoutSpecInvariantError(
                f"layout spec position {idx + 1} expected {expected!r} (FROZEN_PREFIX_V7) "
                f"but found {actual!r}; positions 1-{FROZEN_PREFIX_LENGTH} are FROZEN per "
                f"v9-ADR-002 D1 -- reordering / renaming any of them invalidates the "
                f"LLM cache prefix and is a release blocker"
            )


def assert_dispatch_layout(
    payload: dict,
    layout_spec: list[str] | None = None,
    *,
    enforce_frozen_prefix: bool = True,
) -> None:
    """Validate that ``payload``'s top-level key insertion order is a
    subsequence of the canonical layout (default ``DEFAULT_DISPATCH_LAYOUT``).

    Each spec key may be absent, but none may appear out of order. Unknown keys
    MUST appear after the last spec key (additive rule per ADR-001 §2). Raises
    :class:`DispatchLayoutError` identifying the first violating key.

    P6 cache-layout invariant — backward-compat (R5):

    * ``DEFAULT_DISPATCH_LAYOUT`` is the v5 canonical (16 keys, version 5).
    * v4 payloads (15 keys, omitting ``change_context``) validate exactly
      as before — the new key is optional and absent v4 dispatchers are
      treated as canonical (v4-to-v5 additivity).
    * v7.0.0 + v7.3.0 + v8.0.0-P-08 + v8.0.0-P-10 byte-baselines all
      continue to PASS unchanged after the v4 → v5 schema bump.
    * Callers MAY pass a custom ``layout_spec`` (e.g.
      ``DEFAULT_DISPATCH_LAYOUT[:-1]`` to validate against the v4
      canonical) for legacy interop without copying the canonical list.

    v9.0.0 PV-02 (v8.4.2) — nest-vs-append rule (per
    ``.local/research/adr/v9-ADR-002-cache-layout-governance-v2.md`` D5):

    * The first 12 positions of ``layout_spec`` are the FROZEN PREFIX
      (:data:`FROZEN_PREFIX_V7`); reordering any of them is a release
      blocker (LLM cache-prefix invalidation cost). The
      ``enforce_frozen_prefix`` keyword (default ``True``) gates a
      pre-check via :func:`assert_layout_spec_invariant`. Pass
      ``enforce_frozen_prefix=False`` ONLY for deliberate v6-historical-
      shape interop tests where the legacy spec is known-different.
    * Positions 13+ are APPEND-ONLY per D2. Authors of new top-level
      dispatch keys SHOULD prefer NEST under an existing canonical key
      whenever the data shape allows (D3 decision rule — bias toward
      NEST). The historical 5 NEST decisions (gate.token_budget,
      pred[*].compact_directive, pred[*].summary_mode,
      compression_rules.bypass_conditions,
      compression_rules.data_envelope_required) preserved cache-prefix
      length; the historical 4 APPEND decisions (repos,
      behavioral_guidelines, acceptance_criteria_v2, change_context)
      carried orthogonal cross-block payload that did not nest naturally.
    """
    if not isinstance(payload, dict):
        raise DispatchLayoutError(f"payload must be a dict, got {type(payload).__name__}")

    spec = list(layout_spec) if layout_spec is not None else list(DEFAULT_DISPATCH_LAYOUT)

    if enforce_frozen_prefix and len(spec) >= FROZEN_PREFIX_LENGTH:
        # v9-ADR-002 D5: spec-level guard runs BEFORE payload-level checks.
        # Catches a drifted spec at the entry point of every dispatch
        # validation (cheap call: 12 string comparisons).
        assert_layout_spec_invariant(spec)

    spec_index = {key: idx for idx, key in enumerate(spec)}
    last_position = -1
    seen_unknown = False

    for key in payload:
        if key not in spec_index:
            seen_unknown = True
            continue
        if seen_unknown:
            raise DispatchLayoutError(
                f"spec key {key!r} appears after non-spec key(s); new top-level "
                f"keys MUST be appended after {spec[-1]!r} (additive rule, ADR-001 §2)"
            )
        position = spec_index[key]
        if position < last_position:
            raise DispatchLayoutError(
                f"key {key!r} (canonical position {position}) appears after "
                f"{spec[last_position]!r} (canonical position {last_position}); "
                f"canonical order is {spec!r}"
            )
        last_position = position


def compute_dispatch_lcp_pct(payload_a: dict, payload_b: dict) -> float:
    """Longest common prefix of the rendered YAML for two dispatch payloads,
    as a fraction of ``payload_a``'s rendered byte length.

    Used by the H.2 stability test (ADR-001 §6). Renders both via
    ``yaml.safe_dump(..., sort_keys=False, default_flow_style=False)`` to
    preserve insertion order across implementations. Returns 0.0 if
    ``payload_a`` renders empty.
    """
    import yaml

    bytes_a = yaml.safe_dump(payload_a, sort_keys=False, default_flow_style=False).encode("utf-8")
    bytes_b = yaml.safe_dump(payload_b, sort_keys=False, default_flow_style=False).encode("utf-8")
    if not bytes_a:
        return 0.0
    common = 0
    for byte_a, byte_b in zip(bytes_a, bytes_b, strict=False):
        if byte_a != byte_b:
            break
        common += 1
    return common / len(bytes_a)
