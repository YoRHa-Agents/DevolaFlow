"""Multi-baseline byte-stability tests for the cache-layout invariant.

Per ``.local/research/adr/v9-ADR-002-cache-layout-governance-v2.md`` D4:
CI enforcement pins ALL 6 historical schema baselines so any drift in
ANY baseline fails CI immediately. The combinatorial coverage scales
O(N) with prior baselines and catches three distinct attack classes
(renamer / re-orderer / sneaky inserter) that the v7.0.0 + v7.3.0
additivity-by-transitive-logic guarantees only catch O(1) of.

Baselines covered:

* v7.0.0 — length 12 (initial canonical set)
* v7.3.0 — length 13 (P-06: appended ``repos`` at position 13)
* v8.0.0 P-08 — length 14 (P-08: appended ``behavioral_guidelines``)
* v8.0.0 P-10 — length 15 (P-10: appended ``acceptance_criteria_v2``)
* v8.3.0 PV-05 — length 16 (PV-05: appended ``change_context``)
* v8.4.0 — length 16 stable (no schema bump; v8.4.0 cycle was 0 P6 transitions)
* v9.2.0 — length 16 stable (v9.1.4 PV-04 NEST extension inside
  ``change_context`` sub-fields; canonical_order length unchanged at 16,
  version unchanged at 5 — the witness baseline is byte-identical to
  v8.4.0; absence of the new OPTIONAL sub-fields is the canonical
  rendering per the v9.1.4 PV-04 NEST decision per A-2.3)

Each test renders the canonical payload via
``yaml.safe_dump(..., sort_keys=False, default_flow_style=False)`` and
byte-compares against the golden YAML under
``benchmarks/devolaflow_context/baselines/``.

The v7.0.0 + v7.3.0 baselines reuse the existing fixtures from
``tests/test_benchmarks.py::TestLayoutInvariantBaseline``; the
v8.0.0 P-08 + v8.3.0 PV-05 + v8.4.0 baselines use new fixtures committed
in PV-02. The v8.0.0 P-10 baseline is verified PREFIX-wise against the
v8.3.0 PV-05 baseline (the v8.0.0 P-10 payload would be a prefix of the
v8.3.0 PV-05 baseline minus ``change_context``); a dedicated golden
would be redundant given the prefix-property byte test below.

Closes B-02 from ``.local/research/v9.0.0_gap_analysis.md`` §5.2.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from devolaflow.compressor import (
    DEFAULT_DISPATCH_LAYOUT,
    FROZEN_PREFIX_LENGTH,
    FROZEN_PREFIX_V7,
    LayoutSpecInvariantError,
    assert_dispatch_layout,
    assert_layout_spec_invariant,
    compute_dispatch_lcp_pct,
)

BASELINES_DIR = Path(__file__).parent.parent / "benchmarks/devolaflow_context/baselines"

# Canonical payload constructors (kept here so a future renumber of the
# fixtures in test_benchmarks.py does NOT silently break this module).
# The v7.0.0 + v7.3.0 constructors mirror the existing fixtures verbatim.


def _v7_0_0_payload() -> dict:
    """v7.0.0 12-key canonical payload (matches layout_invariant_v7.0.0.yaml)."""
    return {
        "hdr": {"id": "d-baseline-v7.0.0", "parent": "stage-baseline", "layer": "wave"},
        "task": {"id": "T-BASELINE-001", "type": "code", "title": "cache layout baseline"},
        "goal": "golden rendered dispatch for layout invariant",
        "assumptions": ["yaml renderer preserves insertion order", "utf-8 byte comparison"],
        "pred": [
            {
                "ref": ".local/research/adr/v7-ADR-001-cache-layout-invariant.md",
                "key_facts": [
                    "canonical 12-key order",
                    "additive rule for new keys",
                    "LCP thresholds 0.80 and 0.70",
                ],
            }
        ],
        "files": ["src/devolaflow/compressor.py", "schemas/lean-dispatch.yaml"],
        "rules": {"strategy": "standard", "lang": "python", "focus": ["cache-discipline"]},
        "shared": "Python 3.11+, PyYAML, pytest",
        "accept": [
            "render byte-stable across CI runs",
            "top-level keys remain in canonical order",
            "reinforce slot present at position 10",
        ],
        "reinforce": {
            "round": 2,
            "prior": 78.0,
            "target": 85,
            "rules": [
                {
                    "id": "F-LAY-001",
                    "sev": "blocker",
                    "mandate": "MUST validate via assert_dispatch_layout before send",
                    "file": "src/devolaflow/compressor.py",
                }
            ],
        },
        "verify_cfg": {
            "visual": False,
            "accept": True,
            "interact": False,
            "a11y": False,
            "threshold": 0.85,
        },
        "gate": {"coverage": 85, "quality": 85, "blockers": 0, "retries": 2},
    }


def _v7_3_0_payload() -> dict:
    """v7.3.0 13-key payload — v7.0.0 + ``repos`` at position 13."""
    payload = _v7_0_0_payload()
    payload["repos"] = [
        {
            "name": "auth-service",
            "root_path": "repos/auth-service",
            "primary": True,
            "branch": "main",
        },
        {
            "name": "web-frontend",
            "root_path": "repos/web-frontend",
            "primary": False,
            "branch": "develop",
        },
        {
            "name": "api-gateway",
            "root_path": "repos/api-gateway",
            "primary": False,
            "branch": "main",
        },
    ]
    return payload


def _v8_0_0_p08_payload() -> dict:
    """v8.0.0 P-08 14-key payload — v7.3.0 + ``behavioral_guidelines`` at position 14."""
    payload = _v7_3_0_payload()
    payload["behavioral_guidelines"] = {
        "think_first": True,
        "simplicity_check": True,
        "surgical_scope": "function",
        "goal_loop": False,
    }
    return payload


def _v8_0_0_p10_payload() -> dict:
    """v8.0.0 P-10 15-key payload — v8.0.0 P-08 + ``acceptance_criteria_v2`` at position 15."""
    payload = _v8_0_0_p08_payload()
    payload["acceptance_criteria_v2"] = [
        {
            "id": "AC-001",
            "description": "render byte-stable across CI runs",
            "verification_type": "test",
            "verification_cmd": "pytest tests/test_layout_invariant_multi_baseline.py -v",
        },
        {
            "id": "AC-002",
            "description": "top-level keys remain in canonical order",
            "verification_type": "test",
            "verification_cmd": "pytest tests/test_compressor.py::TestDispatchLayoutInvariant -v",
        },
        {
            "id": "AC-003",
            "description": "frozen prefix positions 1-12 byte-identical to v7.0.0",
            "verification_type": "test",
            "verification_cmd": (
                "pytest tests/test_layout_invariant_multi_baseline.py::TestFrozenPrefixInvariant -v"
            ),
        },
    ]
    return payload


def _v8_3_0_pv05_payload() -> dict:
    """v8.3.0 PV-05 16-key payload — v8.0.0 P-10 + ``change_context`` at position 16."""
    payload = _v8_0_0_p10_payload()
    payload["change_context"] = {
        "change_id": "v9-pv02-cache-layout-governance",
        "active_folder": ".local/.agent/active/v9-pv02-cache-layout-governance",
        "state": "VERIFYING",
        "spec_delta_target": "cache_layout_governance",
        "owned_files_ref": ".local/.agent/active/v9-pv02-cache-layout-governance/owned_files.txt",
        "acceptance_ref": ".local/.agent/active/v9-pv02-cache-layout-governance/acceptance.md",
    }
    return payload


def _v8_4_0_payload() -> dict:
    """v8.4.0 16-key stable payload (no schema bump in v8.4.0 cycle)."""
    payload = _v8_0_0_p10_payload()
    payload["change_context"] = {
        "change_id": "v8.4.0-rtk-memory-router-rollup",
        "active_folder": ".local/.agent/active/v8.4.0-rtk-memory-router-rollup",
        "state": "VERIFYING",
        "spec_delta_target": "rtk_memory_router_stack",
        "owned_files_ref": ".local/.agent/active/v8.4.0-rtk-memory-router-rollup/owned_files.txt",
        "acceptance_ref": ".local/.agent/active/v8.4.0-rtk-memory-router-rollup/acceptance.md",
    }
    return payload


def _v9_2_0_payload() -> dict:
    """v9.2.0 16-key stable payload — v8.4.0 byte-identical witness.

    PV-04 (v9.1.4) introduced 3 NEW OPTIONAL sub-fields under
    ``change_context`` (``prior_feedback_themes`` / ``memory_case_hits`` /
    ``source_of_truth_excerpt``) per A-2.3 nest-vs-append decision. The
    witness payload here OMITS the new sub-fields — that is the canonical
    rendering per the OPTIONAL contract — so the resulting YAML is
    byte-identical to ``layout_invariant_v8.4.0.yaml`` and proves that
    callers who do NOT yet emit the new sub-fields continue to see the
    same cache-prefix bytes (the headline I-8 invariant proof for v9.1.4
    PV-04). The constructor reuses ``_v8_4_0_payload()`` directly to make
    the byte-identical contract obvious to any reader.
    """
    return _v8_4_0_payload()


def _render(payload: dict) -> str:
    """Canonical rendering for byte-comparison (matches v7.0.0 baseline test)."""
    return yaml.safe_dump(payload, sort_keys=False, default_flow_style=False)


# ---------------------------------------------------------------------------
# D4 — Multi-baseline byte-stability tests (one per historical generation).
# ---------------------------------------------------------------------------


class TestMultiBaselineByteStability:
    """Per v9-ADR-002 D4 — every historical baseline pinned independently.

    Catches the 3 attack classes the v7.0.0 + v7.3.0 additivity-by-
    transitive-logic guarantees miss:

    1. Renamer (e.g. ``pred`` → ``predecessors`` in a NEW key would pass v7.0.0
       baseline by coincidence).
    2. Re-orderer below the v7.0.0 horizon (e.g. ``repos`` ↔
       ``behavioral_guidelines`` swap passes v7.0.0 + v7.3.0 byte-test but
       breaks v8.0.0 P-08 baseline).
    3. Sneaky inserter between positions 14 and 15 (passes v7.0.0 + v7.3.0 but
       breaks v8.0.0 P-10 baseline).
    """

    def test_v7_0_0_baseline_byte_identical(self) -> None:
        path = BASELINES_DIR / "layout_invariant_v7.0.0.yaml"
        assert path.exists(), f"missing baseline {path}"
        recorded = path.read_text()
        rendered = _render(_v7_0_0_payload())
        assert rendered == recorded, (
            f"v7.0.0 baseline drift in {path} — see v7-ADR-001 §6 + v9-ADR-002 D4"
        )

    def test_v7_3_0_baseline_byte_identical(self) -> None:
        path = BASELINES_DIR / "layout_invariant_v7.3.0.yaml"
        assert path.exists(), f"missing baseline {path}"
        recorded = path.read_text()
        rendered = _render(_v7_3_0_payload())
        assert rendered == recorded, (
            f"v7.3.0 baseline drift in {path} — see v7-ADR-001 §2 + v9-ADR-002 D4"
        )

    def test_v8_0_0_p08_baseline_byte_identical(self) -> None:
        path = BASELINES_DIR / "layout_invariant_v8.0.0.yaml"
        assert path.exists(), f"missing baseline {path} — v9-ADR-002 D4 requires this fixture"
        recorded = path.read_text()
        rendered = _render(_v8_0_0_p08_payload())
        assert rendered == recorded, (
            f"v8.0.0 P-08 baseline drift in {path} — see "
            ".local/research/v8.0.0_patch_plan.md §3 P-08 + v9-ADR-002 D4"
        )

    def test_v8_0_0_p10_baseline_via_prefix_check(self) -> None:
        """v8.0.0 P-10 (length 15) is verified by prefix-byte equality against
        the v8.3.0 PV-05 baseline (length 16). The v8.3.0 PV-05 payload is
        the v8.0.0 P-10 payload + ``change_context`` appended; rendering
        the first 15 keys of the v8.3.0 PV-05 baseline MUST byte-equal a
        full v8.0.0 P-10 render (P6 cache-prefix preservation proof)."""
        v8_3_0_path = BASELINES_DIR / "layout_invariant_v8.3.0.yaml"
        assert v8_3_0_path.exists(), f"missing baseline {v8_3_0_path}"
        v8_0_0_p10_render = _render(_v8_0_0_p10_payload())
        v8_3_0_pv05_render = v8_3_0_path.read_text()
        # The v8.0.0 P-10 render is a strict prefix of the v8.3.0 PV-05 render
        # (they share keys 1-15; v8.3.0 PV-05 appends `change_context` at 16).
        assert v8_3_0_pv05_render.startswith(v8_0_0_p10_render), (
            "v8.0.0 P-10 render is NOT a byte-prefix of v8.3.0 PV-05 baseline — "
            "the cache-prefix preservation guarantee from P-10 → PV-05 is broken; "
            "see v9-ADR-002 D4"
        )

    def test_v8_3_0_pv05_baseline_byte_identical(self) -> None:
        path = BASELINES_DIR / "layout_invariant_v8.3.0.yaml"
        assert path.exists(), f"missing baseline {path} — v9-ADR-002 D4 requires this fixture"
        recorded = path.read_text()
        rendered = _render(_v8_3_0_pv05_payload())
        assert rendered == recorded, (
            f"v8.3.0 PV-05 baseline drift in {path} — see "
            ".local/research/v8.3.0_design.md §9 + v9-ADR-002 D4"
        )

    def test_v8_4_0_baseline_byte_identical(self) -> None:
        path = BASELINES_DIR / "layout_invariant_v8.4.0.yaml"
        assert path.exists(), f"missing baseline {path} — v9-ADR-002 D4 requires this fixture"
        recorded = path.read_text()
        rendered = _render(_v8_4_0_payload())
        assert rendered == recorded, (
            f"v8.4.0 baseline drift in {path} — v8.4.0 cycle was 0 P6 transitions; "
            "see v9-ADR-002 D4"
        )

    def test_v9_2_0_baseline_byte_identical(self) -> None:
        """v9.2.0 mid-cycle witness — v9.1.4 PV-04 NEST extension proof.

        PV-04 (v9.1.4) added 3 OPTIONAL sub-fields under
        ``change_context`` (``prior_feedback_themes`` /
        ``memory_case_hits`` / ``source_of_truth_excerpt``) per A-2.3
        nest-vs-append rule. Since the new sub-fields are OPTIONAL and
        their absence is canonical, a payload that omits them MUST
        render byte-identical to the v8.4.0 baseline (no canonical
        ordering disturbance — the I-8 invariant the entire v9.0.0
        cycle's cache-layout governance protects). The witness file at
        ``benchmarks/devolaflow_context/baselines/layout_invariant_v9.2.0.yaml``
        is committed as a byte-identical copy of the v8.4.0 baseline so
        a future renamer / re-orderer / sneaky inserter that disturbs
        the v8.4.0 layout would also break this v9.2.0 pin AND any
        future PV that lands legitimate sub-field content can keep this
        baseline as the "no-sub-fields canonical" pin while adding a
        sibling pin for the populated case.
        """
        path = BASELINES_DIR / "layout_invariant_v9.2.0.yaml"
        assert path.exists(), (
            f"missing baseline {path} — v9.1.4 PV-04 requires this fixture "
            "(witness for the NEST extension I-8 invariant)"
        )
        recorded = path.read_text()
        rendered = _render(_v9_2_0_payload())
        assert rendered == recorded, (
            f"v9.2.0 baseline drift in {path} — the v9.1.4 PV-04 NEST "
            "extension was supposed to be byte-identical to the v8.4.0 "
            "baseline (the OPTIONAL sub-fields are absent in canonical "
            "rendering); see v9-ADR-002 D4 + the v9.1.4 PV-04 schema "
            "comment in schemas/lean-dispatch.yaml"
        )

    def test_v9_2_0_baseline_byte_identical_to_v8_4_0(self) -> None:
        """The v9.2.0 baseline file is a verbatim copy of v8.4.0.

        The PV-04 commit ships
        ``benchmarks/devolaflow_context/baselines/layout_invariant_v9.2.0.yaml``
        as a byte-identical copy of
        ``benchmarks/devolaflow_context/baselines/layout_invariant_v8.4.0.yaml``.
        This pin catches any future drift where one file is updated and
        the other is forgotten — both files must move together OR the
        v9.2.0 file must gain its own dedicated payload constructor and
        this guard test must be removed in the same PR.
        """
        v8_4_0_path = BASELINES_DIR / "layout_invariant_v8.4.0.yaml"
        v9_2_0_path = BASELINES_DIR / "layout_invariant_v9.2.0.yaml"
        assert v8_4_0_path.exists(), f"missing baseline {v8_4_0_path}"
        assert v9_2_0_path.exists(), f"missing baseline {v9_2_0_path}"
        v8_4_0_text = v8_4_0_path.read_text()
        v9_2_0_text = v9_2_0_path.read_text()
        assert v8_4_0_text == v9_2_0_text, (
            "v9.2.0 baseline file diverged from v8.4.0 — the v9.1.4 PV-04 "
            "contract requires byte-identical copy (NEST extension preserved "
            "the canonical layout). Either restore the byte-identical copy "
            "OR introduce a dedicated v9.2.0 payload constructor and remove "
            "this guard test in the same PR."
        )


# ---------------------------------------------------------------------------
# D1 + D5 — Frozen-prefix invariant tests.
# ---------------------------------------------------------------------------


class TestFrozenPrefixInvariant:
    """Per v9-ADR-002 D1 + D5 — positions 1-12 of any layout spec MUST
    be byte-identical to ``FROZEN_PREFIX_V7``.

    These tests catch a renamer / re-orderer / sneaky inserter at the
    SPEC level, before any payload is ever validated. They are
    constant-time guards (12 string comparisons).
    """

    def test_frozen_prefix_length_is_twelve(self) -> None:
        assert FROZEN_PREFIX_LENGTH == 12, (
            "FROZEN_PREFIX_V7 length MUST be 12 (v7.0.0 baseline); see v9-ADR-002 D1"
        )

    def test_frozen_prefix_matches_v7_0_0_canonical_keys(self) -> None:
        """The 12 keys must match the v7.0.0 canonical sequence verbatim."""
        expected = (
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
        assert expected == FROZEN_PREFIX_V7, (
            f"FROZEN_PREFIX_V7 drift: {FROZEN_PREFIX_V7!r} != {expected!r} "
            "(v7.0.0 baseline) — see v9-ADR-002 D1"
        )

    def test_default_dispatch_layout_first_12_keys_match_frozen_prefix(self) -> None:
        """``DEFAULT_DISPATCH_LAYOUT[:12]`` MUST byte-equal ``FROZEN_PREFIX_V7``."""
        assert tuple(DEFAULT_DISPATCH_LAYOUT[:FROZEN_PREFIX_LENGTH]) == FROZEN_PREFIX_V7, (
            f"DEFAULT_DISPATCH_LAYOUT prefix drift: "
            f"{DEFAULT_DISPATCH_LAYOUT[:FROZEN_PREFIX_LENGTH]!r} != {FROZEN_PREFIX_V7!r} — "
            "see v9-ADR-002 D5"
        )

    def test_assert_layout_spec_invariant_accepts_canonical(self) -> None:
        """The live ``DEFAULT_DISPATCH_LAYOUT`` MUST pass the spec-level guard."""
        assert_layout_spec_invariant(DEFAULT_DISPATCH_LAYOUT)

    def test_assert_layout_spec_invariant_default_arg_passes(self) -> None:
        """``spec=None`` defaults to ``DEFAULT_DISPATCH_LAYOUT``."""
        assert_layout_spec_invariant()

    def test_assert_layout_spec_invariant_accepts_extended_spec(self) -> None:
        """Specs longer than 16 (forward-compat with future schema bumps)
        MUST pass as long as positions 1-12 match the frozen prefix."""
        extended = list(DEFAULT_DISPATCH_LAYOUT) + ["future_key_v6", "future_key_v7"]
        assert_layout_spec_invariant(extended)

    def test_assert_layout_spec_invariant_rejects_renamed_prefix_key(self) -> None:
        """A spec with a renamed prefix key (e.g. ``pred`` → ``predecessors``)
        MUST raise :class:`LayoutSpecInvariantError`."""
        bad = list(DEFAULT_DISPATCH_LAYOUT)
        bad[4] = "predecessors"  # rename `pred` (position 5)
        with pytest.raises(LayoutSpecInvariantError) as exc_info:
            assert_layout_spec_invariant(bad)
        assert "pred" in str(exc_info.value)
        assert "predecessors" in str(exc_info.value)

    def test_assert_layout_spec_invariant_rejects_reordered_prefix(self) -> None:
        """A spec with two frozen-prefix positions swapped MUST raise."""
        bad = list(DEFAULT_DISPATCH_LAYOUT)
        bad[4], bad[9] = bad[9], bad[4]  # swap `pred` (5) and `reinforce` (10)
        with pytest.raises(LayoutSpecInvariantError):
            assert_layout_spec_invariant(bad)

    def test_assert_layout_spec_invariant_rejects_short_spec(self) -> None:
        """A spec shorter than 12 entries MUST raise (positions 1-12 are FROZEN)."""
        short = list(DEFAULT_DISPATCH_LAYOUT)[:8]
        with pytest.raises(LayoutSpecInvariantError) as exc_info:
            assert_layout_spec_invariant(short)
        assert "shorter than" in str(exc_info.value)

    def test_assert_layout_spec_invariant_rejects_non_list_input(self) -> None:
        with pytest.raises(LayoutSpecInvariantError):
            assert_layout_spec_invariant("not a list")  # type: ignore[arg-type]

    def test_assert_dispatch_layout_calls_spec_invariant_by_default(self) -> None:
        """``assert_dispatch_layout(payload)`` MUST run the spec-level guard
        on ``DEFAULT_DISPATCH_LAYOUT`` by default (D5 entry-point check)."""
        # Canonical payload — should pass cleanly.
        payload = {"hdr": {"id": "d-001"}, "task": {"id": "T-001"}, "goal": "x"}
        assert assert_dispatch_layout(payload) is None

    def test_assert_dispatch_layout_rejects_drifted_custom_spec(self) -> None:
        """A custom layout_spec whose first 12 positions don't match the
        frozen prefix MUST be rejected unless ``enforce_frozen_prefix=False``
        is explicitly passed."""
        bad = list(DEFAULT_DISPATCH_LAYOUT)
        bad[0] = "header"  # rename `hdr` to `header`
        payload = {"header": {"id": "x"}}
        with pytest.raises(LayoutSpecInvariantError):
            assert_dispatch_layout(payload, layout_spec=bad)

    def test_enforce_frozen_prefix_false_allows_legacy_interop(self) -> None:
        """``enforce_frozen_prefix=False`` MUST allow legacy v6-shape interop
        tests where the spec is known-different (escape hatch per D5)."""
        legacy_v6 = ["header", "task_meta", "goal", "files"]
        payload = {"header": {"id": "x"}}
        # Should NOT raise even though `legacy_v6` doesn't match FROZEN_PREFIX_V7.
        assert (
            assert_dispatch_layout(
                payload,
                layout_spec=legacy_v6,
                enforce_frozen_prefix=False,
            )
            is None
        )


# ---------------------------------------------------------------------------
# Cache-prefix LCP regression tests across the multi-baseline chain.
# ---------------------------------------------------------------------------


class TestMultiBaselineLCP:
    """Each successive baseline MUST be a byte-prefix of the next per
    v9-ADR-002 D2 append-only contract. Concretely: rendering v7.0.0 (12
    keys) MUST be a prefix of rendering v7.3.0 (13 keys), which MUST be a
    prefix of v8.0.0 P-08 (14 keys), and so on. ``compute_dispatch_lcp_pct``
    returns 1.0 when the smaller payload is a perfect prefix of the larger.
    """

    @pytest.mark.parametrize(
        ("smaller", "larger", "name"),
        [
            (_v7_0_0_payload, _v7_3_0_payload, "v7.0.0 → v7.3.0"),
            (_v7_3_0_payload, _v8_0_0_p08_payload, "v7.3.0 → v8.0.0 P-08"),
            (_v8_0_0_p08_payload, _v8_0_0_p10_payload, "v8.0.0 P-08 → v8.0.0 P-10"),
            (_v8_0_0_p10_payload, _v8_3_0_pv05_payload, "v8.0.0 P-10 → v8.3.0 PV-05"),
        ],
    )
    def test_each_baseline_is_byte_prefix_of_next(self, smaller, larger, name: str) -> None:
        """Append-only D2 verification: smaller payload renders as a strict
        byte-prefix of larger payload."""
        smaller_render = _render(smaller())
        larger_render = _render(larger())
        assert larger_render.startswith(smaller_render), (
            f"{name} prefix-property violation — append-only D2 broken; see v9-ADR-002 D2 + D4"
        )
        # LCP MUST be 1.0 (perfect prefix).
        lcp = compute_dispatch_lcp_pct(smaller(), larger())
        assert lcp == 1.0, (
            f"{name} LCP({lcp:.4f}) != 1.0 — append-only D2 broken; "
            f"see v9-ADR-002 D2 + tests/test_compressor.py LCP SLO (>= 0.80)"
        )
