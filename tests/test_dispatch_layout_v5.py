"""Cache-layout v4 → v5 transition tests (P6, v8.2.5 PV-05).

Closes M-006 verification per
``.local/research/v8.3.0_gap_analysis.md`` §2.3 and AC-8 of v8.2.5
``.local/research/v8.3.0_patch_plan.md``. The P6 transition rule (R3) is
the cycle's largest-risk patch contract:

* canonical_order grew 15 → 16 by APPENDING ``change_context`` AT THE END.
* version bumped 4 → 5.
* Positions 1..15 are byte-identical to v4 — the v7.0.0 / v7.3.0 / v8.0.0
  P-08 / v8.0.0 P-10 byte-baselines all continue passing.
* ``assert_dispatch_layout`` accepts BOTH v4-shape payloads (omitting
  ``change_context``) AND v5-shape payloads (carrying it).
* ``change_context`` is OPTIONAL — absence == free-floating workflow ==
  current v4 behaviour preserved exactly.

The test pattern mirrors
``tests/test_compressor.py::TestDefaultDispatchLayoutV730`` which
verified the v7.2.6 → v8.0.0-P-10 transition (the precedent we follow
verbatim).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from devolaflow.compressor import (
    DEFAULT_DISPATCH_LAYOUT,
    DispatchLayoutError,
    assert_dispatch_layout,
    compute_dispatch_lcp_pct,
)

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "lean-dispatch.yaml"


# Verbatim canonical orders from PRIOR generations — the P6 invariant
# requires every prior baseline to keep passing after the v4 → v5 bump.
V7_0_0_CANONICAL_ORDER: tuple[str, ...] = (
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

V7_3_0_CANONICAL_ORDER: tuple[str, ...] = V7_0_0_CANONICAL_ORDER + ("repos",)

V8_0_0_P08_CANONICAL_ORDER: tuple[str, ...] = V7_3_0_CANONICAL_ORDER + ("behavioral_guidelines",)

V8_0_0_P10_CANONICAL_ORDER: tuple[str, ...] = V8_0_0_P08_CANONICAL_ORDER + (
    "acceptance_criteria_v2",
)

# v5 = v8.3.0 PV-05 — the new generation under test.
V8_3_0_PV05_CANONICAL_ORDER: tuple[str, ...] = V8_0_0_P10_CANONICAL_ORDER + ("change_context",)


def _load_schema() -> dict:
    return yaml.safe_load(SCHEMA_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Schema-file shape assertions
# ---------------------------------------------------------------------------


class TestSchemaFileShape:
    def test_canonical_order_length_is_17(self):
        schema = _load_schema()
        assert len(schema["layout_invariant"]["canonical_order"]) == 17, (
            f"canonical_order length = {len(schema['layout_invariant']['canonical_order'])}; "
            "expected 17 after v9.7.0 PV-02 (additive append of predecessor_dedup_ledger)"
        )

    def test_layout_invariant_version_is_6(self):
        schema = _load_schema()
        assert schema["layout_invariant"]["version"] == 6, (
            f"layout_invariant.version = {schema['layout_invariant']['version']}; "
            "expected 6 after v9.7.0 PV-02 schema bump (per ADR-001 §2)"
        )

    def test_last_key_is_predecessor_dedup_ledger(self):
        schema = _load_schema()
        canonical = schema["layout_invariant"]["canonical_order"]
        assert canonical[-1] == "predecessor_dedup_ledger", (
            f"canonical_order[-1] is {canonical[-1]!r}, expected 'predecessor_dedup_ledger'"
        )

    def test_position_16_remains_change_context(self):
        """v8.3.0 PV-05 invariant: ``change_context`` MUST stay at position 16
        (1-indexed) even after v9.7.0 PV-02 appends ``predecessor_dedup_ledger``."""
        schema = _load_schema()
        canonical = schema["layout_invariant"]["canonical_order"]
        assert canonical[15] == "change_context", (
            f"position 16 (0-indexed 15) is {canonical[15]!r}; "
            "expected 'change_context' to stay at position 16 "
            "after v9.7.0 PV-02 append (additivity rule, ADR-001 §2)"
        )

    def test_position_15_remains_acceptance_criteria_v2(self):
        """v8.0.0 P-10 invariant: ``acceptance_criteria_v2`` MUST stay at position 15
        (1-indexed) even after PV-05 appends ``change_context``."""
        schema = _load_schema()
        canonical = schema["layout_invariant"]["canonical_order"]
        assert canonical[14] == "acceptance_criteria_v2", (
            f"position 15 (0-indexed 14) is {canonical[14]!r}; "
            "expected 'acceptance_criteria_v2' to stay at position 15 "
            "after PV-05 append (additivity rule, ADR-001 §2)"
        )

    def test_position_14_remains_behavioral_guidelines(self):
        schema = _load_schema()
        canonical = schema["layout_invariant"]["canonical_order"]
        assert canonical[13] == "behavioral_guidelines"

    def test_first_15_positions_byte_identical_to_v4(self):
        schema = _load_schema()
        canonical = tuple(schema["layout_invariant"]["canonical_order"])
        assert canonical[:15] == V8_0_0_P10_CANONICAL_ORDER, (
            f"positions 1..15 drift detected; got {canonical[:15]}, expected "
            f"{V8_0_0_P10_CANONICAL_ORDER} (v8.0.0 P-10 byte-baseline)"
        )

    def test_first_12_positions_byte_identical_to_v7_0_0(self):
        schema = _load_schema()
        canonical = tuple(schema["layout_invariant"]["canonical_order"])
        assert canonical[:12] == V7_0_0_CANONICAL_ORDER, (
            "v7.0.0 12-key byte-baseline drift — RELEASE BLOCKER per "
            "devola-flow-rules.mdc Rule 6 (P6) and v7-ADR-001 §2"
        )

    def test_first_13_positions_byte_identical_to_v7_3_0(self):
        schema = _load_schema()
        canonical = tuple(schema["layout_invariant"]["canonical_order"])
        assert canonical[:13] == V7_3_0_CANONICAL_ORDER

    def test_change_context_field_is_documented(self):
        """The ``lean_format_spec.change_context`` documentation block MUST
        accompany the canonical_order entry (per the v8.0.0 P-08 / P-10
        precedent style)."""
        schema = _load_schema()
        assert "change_context" in schema["lean_format_spec"], (
            "lean_format_spec.change_context block is missing — per the "
            "v8.0.0 P-08 / P-10 precedent, every new top-level dispatch "
            "key MUST carry its field-shape documentation in lean_format_spec"
        )
        block = schema["lean_format_spec"]["change_context"]
        assert block.get("optional") is True, (
            "change_context MUST declare optional: true (R5 backward-compat — "
            "v4 callers omit it and continue working)"
        )

    def test_backward_compat_block_present(self):
        """The new ``layout_invariant.enforcement.backward_compat`` block must
        document the v4 → v5 invariant explicitly (audit trail)."""
        schema = _load_schema()
        bc = schema["layout_invariant"]["enforcement"].get("backward_compat", {})
        assert bc, "backward_compat block missing from layout_invariant.enforcement"
        assert bc.get("v4_payloads_still_valid") is True
        assert bc.get("v7_0_0_baseline_passes") is True
        assert bc.get("v7_3_0_baseline_passes") is True


# ---------------------------------------------------------------------------
# DEFAULT_DISPATCH_LAYOUT constant assertions
# ---------------------------------------------------------------------------


class TestDefaultDispatchLayoutV5:
    def test_default_dispatch_layout_length_is_17(self):
        assert len(DEFAULT_DISPATCH_LAYOUT) == 17

    def test_default_dispatch_layout_last_entry_is_predecessor_dedup_ledger(self):
        assert DEFAULT_DISPATCH_LAYOUT[-1] == "predecessor_dedup_ledger"

    def test_default_dispatch_layout_position_16_remains_change_context(self):
        """v9.7.0 PV-02 invariant: ``change_context`` stays at position 16."""
        assert DEFAULT_DISPATCH_LAYOUT[15] == "change_context"

    def test_default_dispatch_layout_first_15_unchanged(self):
        assert tuple(DEFAULT_DISPATCH_LAYOUT[:15]) == V8_0_0_P10_CANONICAL_ORDER, (
            "DEFAULT_DISPATCH_LAYOUT[:15] drift — R5 byte-identical "
            "invariant for v4 callers VIOLATED"
        )

    def test_default_dispatch_layout_matches_schema(self):
        schema = _load_schema()
        assert tuple(DEFAULT_DISPATCH_LAYOUT) == tuple(
            schema["layout_invariant"]["canonical_order"]
        )


# ---------------------------------------------------------------------------
# Validator behaviour — v4 backward-compat + v5 acceptance
# ---------------------------------------------------------------------------


class TestValidatorBackwardCompat:
    @staticmethod
    def _v4_payload() -> dict:
        """Synthetic v4-shape dispatch — 15 keys, no change_context."""
        return {
            "hdr": {"id": "d-v4-001", "parent": "stage-v4", "layer": "wave"},
            "task": {"id": "T-V4-001", "type": "code", "title": "v4 dispatch"},
            "goal": "verify v4 backward-compat after v5 bump",
            "assumptions": ["v4 callers omit change_context"],
            "pred": [{"ref": "ADR-001", "key_facts": ["additivity rule"]}],
            "files": ["src/devolaflow/compressor.py"],
            "rules": {"strategy": "standard", "lang": "python"},
            "shared": "Python 3.11+",
            "accept": ["v4 payloads validate against v5 spec"],
            "reinforce": {"round": 1, "rules": []},
            "verify_cfg": {"visual": False, "accept": True},
            "gate": {"coverage": 85, "quality": 85, "blockers": 0, "retries": 2},
            "repos": [
                {"name": "auth", "root_path": "repos/auth", "primary": True, "branch": "main"},
            ],
            "behavioral_guidelines": {
                "think_first": True,
                "simplicity_check": True,
                "surgical_scope": "module",
                "goal_loop": True,
            },
            "acceptance_criteria_v2": [
                {
                    "id": "AC-1",
                    "description": "v4 payload valid",
                    "verification_type": "test",
                    "verification_cmd": "pytest -q",
                    "metric": "",
                    "threshold": "",
                },
            ],
        }

    @staticmethod
    def _v5_payload() -> dict:
        """Synthetic v5-shape dispatch — 16 keys including change_context."""
        v4 = TestValidatorBackwardCompat._v4_payload()
        cid = "v8.3.0-pv05-agent-workspace-api-and-layout-v5"
        active_folder = f".local/.agent/active/{cid}"
        v4["change_context"] = {
            "change_id": cid,
            "active_folder": active_folder,
            "state": "IN_PROGRESS",
            "spec_delta_target": "agent_workspace",
            "owned_files_ref": f"{active_folder}/owned_files.txt",
            "acceptance_ref": f"{active_folder}/acceptance.md",
        }
        return v4

    def test_v4_payload_validates(self):
        """R5 / I-PV05-C: v4 callers continue working byte-identical."""
        assert assert_dispatch_layout(self._v4_payload()) is None

    def test_v5_payload_validates(self):
        """v5 payloads with the new change_context field validate."""
        assert assert_dispatch_layout(self._v5_payload()) is None

    def test_change_context_is_optional(self):
        """I-PV05-F: free-floating workflow == v4 behaviour preserved."""
        v4 = self._v4_payload()
        assert "change_context" not in v4
        assert assert_dispatch_layout(v4) is None

    def test_v4_payload_with_explicit_v5_layout_spec_passes(self):
        """Even when the caller passes the explicit v5 layout, v4 payloads validate."""
        assert (
            assert_dispatch_layout(self._v4_payload(), layout_spec=list(DEFAULT_DISPATCH_LAYOUT))
            is None
        )

    def test_v5_payload_with_legacy_v4_layout_spec_treats_change_context_as_unknown(self):
        """A caller that pins ``layout_spec=DEFAULT_DISPATCH_LAYOUT[:-1]`` (v4
        canonical) MUST tolerate the new change_context as an "unknown" key
        appearing AFTER the last spec entry — additive rule per ADR-001 §2."""
        v5 = self._v5_payload()
        legacy_spec = list(DEFAULT_DISPATCH_LAYOUT[:-1])
        assert assert_dispatch_layout(v5, layout_spec=legacy_spec) is None

    def test_change_context_before_acceptance_criteria_v2_rejected(self):
        v5 = self._v5_payload()
        keys = list(v5.keys())
        ac_idx = keys.index("acceptance_criteria_v2")
        cc_idx = keys.index("change_context")
        keys[ac_idx], keys[cc_idx] = keys[cc_idx], keys[ac_idx]
        reordered = {k: v5[k] for k in keys}
        with pytest.raises(DispatchLayoutError) as exc_info:
            assert_dispatch_layout(reordered)
        assert "change_context" in str(exc_info.value) or "acceptance_criteria_v2" in str(
            exc_info.value
        )

    def test_change_context_after_unknown_top_level_key_rejected(self):
        """A spec key after a non-spec key violates the additive rule."""
        v5 = self._v5_payload()
        bogus_first: dict = {"telemetry": {"foo": "bar"}}
        bogus_first.update(v5)
        with pytest.raises(DispatchLayoutError):
            assert_dispatch_layout(bogus_first)


class TestPriorBaselinesStillPass:
    def test_v7_0_0_baseline_payload_validates(self):
        """The 12-key v7.0.0 byte-baseline still validates against v5 spec."""
        payload = {
            "hdr": {"id": "d-v7-001"},
            "task": {"id": "T-V7-001"},
            "goal": "v7.0.0 12-key shape",
            "assumptions": ["pre-P-06 dispatcher renderer"],
            "pred": [{"ref": "ADR-001", "key_facts": ["12-key shape"]}],
            "files": ["src/legacy/module.py"],
            "rules": {"strategy": "standard", "lang": "python"},
            "shared": "Python 3.11+",
            "accept": ["legacy CI green"],
            "verify_cfg": {"visual": False, "accept": True},
            "gate": {"coverage": 85, "quality": 85, "blockers": 0, "retries": 2},
        }
        assert assert_dispatch_layout(payload) is None

    def test_v7_3_0_baseline_payload_validates(self):
        """The 13-key v7.3.0 byte-baseline (with `repos`) still validates."""
        payload = {
            "hdr": {"id": "d-v7-3"},
            "task": {"id": "T-V73-001"},
            "goal": "v7.3.0 13-key shape",
            "pred": [{"ref": "ADR-001"}],
            "files": ["repos/x/src/x.py"],
            "rules": {"strategy": "standard"},
            "gate": {"coverage": 85, "quality": 85},
            "repos": [
                {"name": "auth", "root_path": "repos/auth", "primary": True, "branch": "main"},
            ],
        }
        assert assert_dispatch_layout(payload) is None

    def test_v8_0_0_p08_baseline_payload_validates(self):
        """The 14-key v8.0.0 P-08 byte-baseline (with `behavioral_guidelines`)."""
        payload = {
            "hdr": {"id": "d-p08"},
            "task": {"id": "T-P08-001"},
            "gate": {"coverage": 85},
            "repos": [{"name": "x", "root_path": "x", "primary": True, "branch": "main"}],
            "behavioral_guidelines": {
                "think_first": True,
                "simplicity_check": True,
                "surgical_scope": "function",
                "goal_loop": True,
            },
        }
        assert assert_dispatch_layout(payload) is None

    def test_v8_0_0_p10_baseline_payload_validates(self):
        """The 15-key v8.0.0 P-10 byte-baseline (with `acceptance_criteria_v2`)."""
        payload = {
            "hdr": {"id": "d-p10"},
            "task": {"id": "T-P10-001"},
            "gate": {"coverage": 85},
            "behavioral_guidelines": {
                "think_first": True,
                "simplicity_check": True,
                "surgical_scope": "function",
                "goal_loop": True,
            },
            "acceptance_criteria_v2": [
                {
                    "id": "AC-1",
                    "description": "passes",
                    "verification_type": "test",
                    "verification_cmd": "pytest -q",
                    "metric": "",
                    "threshold": "",
                },
            ],
        }
        assert assert_dispatch_layout(payload) is None


# ---------------------------------------------------------------------------
# LCP stability — v5 schema MUST NOT degrade round-over-round prefix stability
# ---------------------------------------------------------------------------


class TestLcpStabilityWithV5:
    def test_v5_lcp_byte_prefix_unchanged(self):
        """Adding ``change_context`` (with stable contents) MUST NOT shrink
        the absolute common-prefix BYTES — the new field is appended after
        the cached prefix per ADR-001 §2.

        Note: the LCP fraction can mathematically shrink when the
        denominator (payload size) grows; the meaningful invariant is the
        *absolute* common-prefix byte count, which the additive append
        rule guarantees stays the same or grows.
        """
        v4_round1 = TestValidatorBackwardCompat._v4_payload()
        v4_round2 = TestValidatorBackwardCompat._v4_payload()
        v4_round2["reinforce"] = {"round": 2, "rules": []}

        cc = {
            "change_id": "test-change",
            "active_folder": ".local/.agent/active/test-change",
            "state": "IN_PROGRESS",
            "spec_delta_target": "x",
            "owned_files_ref": ".local/.agent/active/test-change/owned_files.txt",
            "acceptance_ref": ".local/.agent/active/test-change/acceptance.md",
        }
        v5_round1 = {**v4_round1, "change_context": cc}
        v5_round2 = {**v4_round2, "change_context": cc}

        # Use the LCP fraction × payload size to derive the absolute byte
        # count, then assert v5_bytes >= v4_bytes (additivity invariant).
        v4_a_bytes = yaml.safe_dump(v4_round1, sort_keys=False).encode("utf-8")
        v5_a_bytes = yaml.safe_dump(v5_round1, sort_keys=False).encode("utf-8")
        lcp_v4_bytes = int(round(compute_dispatch_lcp_pct(v4_round1, v4_round2) * len(v4_a_bytes)))
        lcp_v5_bytes = int(round(compute_dispatch_lcp_pct(v5_round1, v5_round2) * len(v5_a_bytes)))

        assert lcp_v5_bytes >= lcp_v4_bytes, (
            f"v5 absolute common-prefix is {lcp_v5_bytes} bytes vs v4 "
            f"{lcp_v4_bytes} bytes; appending change_context after "
            "acceptance_criteria_v2 MUST NOT degrade prefix stability "
            "(per ADR-001 §2 additive rule)"
        )

    def test_v5_change_context_appended_after_cached_prefix(self):
        """The ``change_context`` block is RENDERED after every other v4 key
        (cached-prefix preservation contract — ADR-001 §2)."""
        v5 = TestValidatorBackwardCompat._v5_payload()
        rendered = yaml.safe_dump(v5, sort_keys=False)
        cc_pos = rendered.index("change_context:")
        ac_pos = rendered.index("acceptance_criteria_v2:")
        gate_pos = rendered.index("gate:")
        assert cc_pos > ac_pos > gate_pos, (
            "change_context: MUST render AFTER acceptance_criteria_v2: "
            "(which itself MUST render AFTER gate:) — additive ordering"
        )
