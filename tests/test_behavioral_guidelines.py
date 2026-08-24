"""v8.0.0 P-08 — L2 Task behavioral guidelines injection tests.

Coverage targets:
1. Schema additivity (canonical_order grew 13→14, version 2→3, last entry =
   ``behavioral_guidelines``, ``repos`` stays at position 13, the v7.0.0
   AND v7.3.0 byte-baselines STILL pass with the new shape).
2. ``_select_behavioral_sections()`` per-profile + tier-default merging.
3. ``_compose_behavioral_block()`` rendering shape and active-rule filtering.
4. ``assert_dispatch_layout()`` accepts BOTH v2 (no behavioral_guidelines)
   AND v3 (with behavioral_guidelines) payloads — backward compatibility.
5. Integration: ``select_context()`` returns the resolved
   ``behavioral_guidelines`` field; the assembled text carries the
   compose block when active; v7.x byte-stable shape is preserved when
   the field is absent.
6. References file (``references/behavioral-guidelines.md``) is well-formed
   and within Large-tier line budget.

NineS finding closed: ``[CC-448821-0000]`` (cc=11 → ≤8 on ``select_context``).

These tests are part of the P-08 owned scope per the patch plan
``.local/research/v8.0.0_patch_plan.md`` §3 P-08.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from devolaflow.compressor import (
    DEFAULT_DISPATCH_LAYOUT,
    DispatchLayoutError,
    assert_dispatch_layout,
)
from devolaflow.task_adaptive_selector import (
    _append_optional_blocks,
    _compose_behavioral_block,
    _load_line_level_criteria,
    _resolve_active_profile,
    _resolve_dispatch_overrides,
    _select_behavioral_sections,
    select_context,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schemas" / "lean-dispatch.yaml"
PROFILES_PATH = REPO_ROOT / "workflow-system" / "agent" / "context_profiles.yaml"
BEHAVIORAL_REF_PATH = (
    REPO_ROOT / "workflow-system" / "agent" / "references" / "behavioral-guidelines.md"
)


# ---------------------------------------------------------------------------
# 1. Schema additivity (P6 invariant transition: 13→14, version 2→3)
# ---------------------------------------------------------------------------


class TestSchemaAdditivity:
    """P6 cache-layout invariant: P-08 APPENDED behavioral_guidelines at
    position 14 after ``repos``, bumping version 2→3. P-10 then APPENDED
    ``acceptance_criteria_v2`` at position 15, bumping version 3→4 (see
    ``tests/test_ac_generator.py::TestSchemaAdditivity``). Positions
    1-13 remain UNCHANGED across both transitions, and behavioral_guidelines
    stays pinned at position 14 — the v7.0.0 + v7.3.0 byte-baseline
    parity is preserved across THREE schema generations."""

    @pytest.fixture
    def schema_spec(self) -> dict:
        return yaml.safe_load(SCHEMA_PATH.read_text(encoding="utf-8"))

    def test_canonical_order_length_is_17(self, schema_spec: dict) -> None:
        """After P-08 + P-10 + PV-05 + v9.7.0 PV-02, canonical_order length
        is 17 (P-08 added ``behavioral_guidelines`` at 14, P-10 added
        ``acceptance_criteria_v2`` at 15, PV-05 added ``change_context``
        at 16, v9.7.0 PV-02 added ``predecessor_dedup_ledger`` at 17).
        Position 14 invariant remains non-negotiable across all generations."""
        canonical = schema_spec["layout_invariant"]["canonical_order"]
        assert len(canonical) == 17, (
            f"canonical_order length = {len(canonical)}; expected 17 after v9.7.0 PV-02"
        )

    def test_canonical_order_position_14_is_behavioral_guidelines(self, schema_spec: dict) -> None:
        """P-08 added ``behavioral_guidelines`` at position 14 (1-indexed).
        P-10 MUST keep it there (the position-14 invariant is non-negotiable);
        PV-05 also MUST keep it (positions 1..15 byte-identical)."""
        canonical = schema_spec["layout_invariant"]["canonical_order"]
        assert canonical[13] == "behavioral_guidelines"

    def test_canonical_order_position_13_is_repos(self, schema_spec: dict) -> None:
        """v7.2.6 P-06 placed ``repos`` at position 13 (1-indexed).
        v8.0.0 P-08 + P-10 + v8.3.0 PV-05 MUST keep it there."""
        canonical = schema_spec["layout_invariant"]["canonical_order"]
        assert canonical[12] == "repos"

    def test_layout_invariant_version_is_6(self, schema_spec: dict) -> None:
        """P-08 bumped version 2→3, P-10 bumped 3→4, PV-05 bumped 4→5,
        v9.7.0 PV-02 bumped 5→6 (additive transitions across SIX
        schema generations)."""
        assert schema_spec["layout_invariant"]["version"] == 6

    def test_canonical_order_first_12_keys_unchanged(self, schema_spec: dict) -> None:
        """Positions 1-12 (1-indexed) MUST be byte-identical to the v7.0.0
        canonical sequence — REORDERING ANY EXISTING KEY IS A RELEASE BLOCKER
        per devola-flow-rules.mdc Rule 6 (P6) and v7-ADR-001 §2."""
        canonical = schema_spec["layout_invariant"]["canonical_order"]
        v7_0_0_canonical = (
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
        assert tuple(canonical[:12]) == v7_0_0_canonical

    def test_default_dispatch_layout_constant_matches_schema(self, schema_spec: dict) -> None:
        """The Python constant ``DEFAULT_DISPATCH_LAYOUT`` MUST stay in lock
        step with ``schemas/lean-dispatch.yaml#layout_invariant.canonical_order``.
        """
        canonical = schema_spec["layout_invariant"]["canonical_order"]
        assert list(DEFAULT_DISPATCH_LAYOUT) == list(canonical)

    def test_behavioral_guidelines_field_documented_in_lean_format_spec(
        self, schema_spec: dict
    ) -> None:
        """The new top-level field MUST have a documented field shape under
        ``lean_format_spec`` so dispatchers know the 4 sub-keys."""
        bg_spec = schema_spec["lean_format_spec"]["behavioral_guidelines"]
        assert "fields" in bg_spec
        for key in ("think_first", "simplicity_check", "surgical_scope", "goal_loop"):
            assert key in bg_spec["fields"]


# ---------------------------------------------------------------------------
# 2. assert_dispatch_layout backward compatibility (v2 + v3 acceptance)
# ---------------------------------------------------------------------------


class TestAssertDispatchLayoutBackwardCompat:
    """``assert_dispatch_layout`` MUST accept BOTH:
      (a) v2 payloads — no ``behavioral_guidelines`` field (v7.x dispatchers).
      (b) v3 payloads — with ``behavioral_guidelines`` at the canonical end.
    Reordered payloads (behavioral_guidelines BEFORE repos / gate / etc.)
    MUST be rejected with :class:`DispatchLayoutError`.
    """

    @staticmethod
    def _v2_payload_no_behavioral() -> dict:
        return {
            "hdr": {"id": "d-v2"},
            "task": {"id": "T-v2", "type": "code"},
            "goal": "v2 dispatch with no behavioral_guidelines",
            "gate": {"coverage": 80, "quality": 85, "blockers": 0, "retries": 2},
        }

    @staticmethod
    def _v2_payload_with_repos() -> dict:
        return {
            "hdr": {"id": "d-v2-repos"},
            "task": {"id": "T-v2-repos"},
            "gate": {"coverage": 85},
            "repos": [{"name": "primary", "primary": True, "branch": "main"}],
        }

    @staticmethod
    def _v3_payload_full() -> dict:
        return {
            "hdr": {"id": "d-v3-full"},
            "task": {"id": "T-v3-full"},
            "gate": {"coverage": 90},
            "repos": [{"name": "primary", "primary": True}],
            "behavioral_guidelines": {
                "think_first": True,
                "simplicity_check": True,
                "surgical_scope": "function",
                "goal_loop": False,
            },
        }

    def test_accepts_v2_payload_without_behavioral_guidelines(self) -> None:
        assert assert_dispatch_layout(self._v2_payload_no_behavioral()) is None

    def test_accepts_v2_payload_with_repos_no_behavioral(self) -> None:
        assert assert_dispatch_layout(self._v2_payload_with_repos()) is None

    def test_accepts_v3_payload_with_behavioral_guidelines(self) -> None:
        assert assert_dispatch_layout(self._v3_payload_full()) is None

    def test_accepts_v3_payload_sparse_no_repos(self) -> None:
        """A dispatch may carry behavioral_guidelines but no repos — the
        canonical_order tolerates absent positions per ADR-001 §2."""
        sparse = {
            "hdr": {"id": "d-sparse"},
            "task": {"id": "T-sparse"},
            "gate": {"coverage": 80},
            "behavioral_guidelines": {"think_first": True, "surgical_scope": "function"},
        }
        assert assert_dispatch_layout(sparse) is None

    def test_rejects_behavioral_guidelines_before_repos(self) -> None:
        """REORDER attack: behavioral_guidelines placed BEFORE repos must
        fail — the canonical position-14 invariant is non-negotiable."""
        bad = {
            "hdr": {"id": "x"},
            "task": {"id": "T"},
            "behavioral_guidelines": {"think_first": True},
            "repos": [{"name": "p", "primary": True}],
        }
        with pytest.raises(DispatchLayoutError):
            assert_dispatch_layout(bad)

    def test_rejects_behavioral_guidelines_before_gate(self) -> None:
        bad = {
            "hdr": {"id": "x"},
            "behavioral_guidelines": {"think_first": True},
            "gate": {"coverage": 80},
        }
        with pytest.raises(DispatchLayoutError):
            assert_dispatch_layout(bad)


# ---------------------------------------------------------------------------
# 3. _select_behavioral_sections — per-profile + tier-default merging
# ---------------------------------------------------------------------------


class TestSelectBehavioralSections:
    """Profile-level resolution of the 4-key behavioral_guidelines block.
    When the profile omits it, return None (preserves v7.x). When the
    profile sets ``tier``, fall back to ``meta.behavioral_guidelines_defaults``
    and let per-profile keys override on a per-key basis."""

    DEFAULTS = {
        "trivial": {
            "think_first": False,
            "simplicity_check": False,
            "surgical_scope": "line",
            "goal_loop": False,
        },
        "simple": {
            "think_first": True,
            "simplicity_check": False,
            "surgical_scope": "function",
            "goal_loop": False,
        },
        "standard": {
            "think_first": True,
            "simplicity_check": True,
            "surgical_scope": "function",
            "goal_loop": False,
        },
        "complex": {
            "think_first": True,
            "simplicity_check": True,
            "surgical_scope": "module",
            "goal_loop": True,
        },
    }

    @classmethod
    def _config_with_defaults(cls) -> dict:
        return {"meta": {"behavioral_guidelines_defaults": cls.DEFAULTS}}

    def test_returns_none_when_profile_omits_block(self) -> None:
        result = _select_behavioral_sections({}, self._config_with_defaults())
        assert result is None

    def test_returns_none_when_block_is_not_dict(self) -> None:
        """Defensive: malformed YAML may render the block as a string or
        list. Helper MUST treat malformed shape as 'absent' rather than
        raise — preserves S-5 No Silent Failures by explicitly returning
        None (ABSENT signal) instead of swallowing an exception."""
        result = _select_behavioral_sections(
            {"behavioral_guidelines": "malformed"}, self._config_with_defaults()
        )
        assert result is None

    def test_explicit_block_with_no_tier_returns_block_verbatim(self) -> None:
        profile = {
            "behavioral_guidelines": {
                "think_first": True,
                "simplicity_check": False,
                "surgical_scope": "function",
                "goal_loop": False,
            }
        }
        result = _select_behavioral_sections(profile, self._config_with_defaults())
        assert result == profile["behavioral_guidelines"]

    def test_tier_only_block_falls_back_to_defaults(self) -> None:
        profile = {"behavioral_guidelines": {"tier": "complex"}}
        result = _select_behavioral_sections(profile, self._config_with_defaults())
        assert result == self.DEFAULTS["complex"]

    def test_per_key_override_beats_tier_default(self) -> None:
        """Profile may inherit ``tier: standard`` defaults yet flip
        ``goal_loop=true`` for that one profile."""
        profile = {"behavioral_guidelines": {"tier": "standard", "goal_loop": True}}
        result = _select_behavioral_sections(profile, self._config_with_defaults())
        assert result["goal_loop"] is True
        assert result["think_first"] is True  # inherited from standard tier
        assert result["surgical_scope"] == "function"  # inherited

    def test_unknown_tier_returns_per_profile_keys_only(self) -> None:
        """An unknown tier falls back to {} so the per-profile keys
        determine the resolved block on their own."""
        profile = {
            "behavioral_guidelines": {
                "tier": "nonexistent_tier",
                "think_first": True,
                "surgical_scope": "function",
            }
        }
        result = _select_behavioral_sections(profile, self._config_with_defaults())
        assert result == {"think_first": True, "surgical_scope": "function"}

    def test_returns_none_when_block_is_empty_dict_after_merge(self) -> None:
        """If the profile sets `behavioral_guidelines: {}` and there is no
        usable tier, the merged result is empty so the helper returns None
        rather than an empty dict — prevents downstream consumers from
        rendering an empty injected block."""
        result = _select_behavioral_sections({"behavioral_guidelines": {}}, {"meta": {}})
        assert result is None


# ---------------------------------------------------------------------------
# 4. _compose_behavioral_block — rendering shape + active-rule filtering
# ---------------------------------------------------------------------------


class TestComposeBehavioralBlock:
    """Rendering: only active rules emit bullets; ``surgical_scope`` always
    renders when the block is non-None; the heading is a fixed string."""

    def test_returns_empty_string_for_none(self) -> None:
        assert _compose_behavioral_block(None) == ""

    def test_returns_empty_string_for_empty_dict(self) -> None:
        assert _compose_behavioral_block({}) == ""

    def test_emits_heading_when_active(self) -> None:
        block = _compose_behavioral_block({"think_first": True})
        assert block.startswith("## Behavioral Guidelines (L2 Task active)")

    def test_active_think_first_rule_emits_bg001(self) -> None:
        block = _compose_behavioral_block({"think_first": True})
        assert "BG-001 think_first ENABLED" in block

    def test_active_simplicity_check_rule_emits_bg002(self) -> None:
        block = _compose_behavioral_block({"simplicity_check": True})
        assert "BG-002 simplicity_check ENABLED" in block

    def test_surgical_scope_always_renders_when_block_active(self) -> None:
        block = _compose_behavioral_block({"think_first": True, "surgical_scope": "module"})
        assert "BG-003 surgical_scope = 'module'" in block

    def test_surgical_scope_defaults_to_function_when_unset(self) -> None:
        block = _compose_behavioral_block({"think_first": True})
        assert "'function'" in block

    def test_active_goal_loop_rule_emits_bg004(self) -> None:
        block = _compose_behavioral_block({"goal_loop": True})
        assert "BG-004 goal_loop ENABLED" in block

    def test_inactive_rules_omit_their_bullet(self) -> None:
        """think_first=False MUST NOT emit a BG-001 bullet — token cost
        scales with active-rule count."""
        block = _compose_behavioral_block({"think_first": False, "goal_loop": True})
        assert "BG-001" not in block
        assert "BG-004 goal_loop ENABLED" in block

    def test_block_token_bounds(self) -> None:
        """All-active block stays under the L2 Task token budget allocation
        target (~ 225 tokens / 3% of L2 Task 8K, post v12.2.0 PV-03)."""
        from devolaflow.task_adaptive_selector import estimate_tokens

        block = _compose_behavioral_block(
            {
                "think_first": True,
                "simplicity_check": True,
                "surgical_scope": "module",
                "goal_loop": True,
                "no_llm_for_deterministic": True,
                "surface_conflicts": True,
                "convention_first": True,
            }
        )
        # 7-rule all-active block ~ 200 tokens (~ 30 per active bullet).
        # Budget raised from 150 → 225 for v12.2.0 PV-03 (3-rule extension).
        assert estimate_tokens(block) <= 225


# ---------------------------------------------------------------------------
# 4b. v12.2.0 PV-03 — Mnimiy 3-rule extension (BG-005..BG-007)
# ---------------------------------------------------------------------------


class TestMnimiyBehavioralExtensions:
    """v12.2.0 PV-03 — `no_llm_for_deterministic` (BG-005) +
    `surface_conflicts` (BG-006) + `convention_first` (BG-007) added per
    the Mnimiy May-2026 X article cross-walk (`.local/research/v12.2.0_gap_analysis.md`
    §2 D-2). Each NEW rule is a NEST sub-field under the existing
    `behavioral_guidelines` dispatch block — canonical_order length stays
    at 17 and schema version stays at 6 (verified in TestSchemaAdditivity
    above).
    """

    def test_active_no_llm_for_deterministic_emits_bg005(self) -> None:
        block = _compose_behavioral_block({"no_llm_for_deterministic": True})
        assert "BG-005 no_llm_for_deterministic ENABLED" in block
        assert "deterministic decisions" in block

    def test_active_surface_conflicts_emits_bg006(self) -> None:
        block = _compose_behavioral_block({"surface_conflicts": True})
        assert "BG-006 surface_conflicts ENABLED" in block
        assert "flag the conflict" in block

    def test_active_convention_first_emits_bg007(self) -> None:
        block = _compose_behavioral_block({"convention_first": True})
        assert "BG-007 convention_first ENABLED" in block
        assert "match the codebase" in block

    def test_inactive_v12_2_0_rules_omit_their_bullets(self) -> None:
        """Default-False keys MUST NOT emit bullets — backward-compat with
        v8.x profiles that never set the 3 new fields."""
        block = _compose_behavioral_block(
            {
                "think_first": True,
                "no_llm_for_deterministic": False,
                "surface_conflicts": False,
                "convention_first": False,
            }
        )
        assert "BG-005" not in block
        assert "BG-006" not in block
        assert "BG-007" not in block

    def test_select_behavioral_sections_resolves_v12_2_0_keys_from_tier(self) -> None:
        """When a profile uses `tier: standard`, the resolved block MUST
        include the 3 NEW v12.2.0 keys (all True per the default matrix)."""
        from devolaflow.task_adaptive_selector import _select_behavioral_sections

        defaults = {
            "standard": {
                "think_first": True,
                "simplicity_check": True,
                "surgical_scope": "function",
                "goal_loop": False,
                "no_llm_for_deterministic": True,
                "surface_conflicts": True,
                "convention_first": True,
            }
        }
        config = {"meta": {"behavioral_guidelines_defaults": defaults}}
        profile = {"behavioral_guidelines": {"tier": "standard"}}
        result = _select_behavioral_sections(profile, config)
        assert result is not None
        assert result["no_llm_for_deterministic"] is True
        assert result["surface_conflicts"] is True
        assert result["convention_first"] is True

    def test_per_key_override_works_for_v12_2_0_keys(self) -> None:
        """A profile MAY opt out of the standard-tier defaults for a
        single new rule (e.g. disable `convention_first` for a greenfield
        profile)."""
        from devolaflow.task_adaptive_selector import _select_behavioral_sections

        defaults = {
            "standard": {
                "think_first": True,
                "simplicity_check": True,
                "surgical_scope": "function",
                "goal_loop": False,
                "no_llm_for_deterministic": True,
                "surface_conflicts": True,
                "convention_first": True,
            }
        }
        config = {"meta": {"behavioral_guidelines_defaults": defaults}}
        profile = {
            "behavioral_guidelines": {"tier": "standard", "convention_first": False},
        }
        result = _select_behavioral_sections(profile, config)
        assert result["convention_first"] is False
        # Other keys still inherited from standard tier
        assert result["no_llm_for_deterministic"] is True
        assert result["surface_conflicts"] is True

    def test_pre_v12_2_0_profile_without_new_keys_resolves_falsy(self) -> None:
        """Backward-compat: a v8.x profile that omits the 3 new keys gets
        them as absent (falsy) so `_compose_behavioral_block` does NOT emit
        the corresponding bullets."""
        from devolaflow.task_adaptive_selector import _select_behavioral_sections

        defaults = {
            "standard": {
                "think_first": True,
                "simplicity_check": True,
                "surgical_scope": "function",
                "goal_loop": False,
                # NO v12.2.0 keys — simulates a v8.x-era defaults block
            }
        }
        config = {"meta": {"behavioral_guidelines_defaults": defaults}}
        profile = {"behavioral_guidelines": {"tier": "standard"}}
        result = _select_behavioral_sections(profile, config)
        assert result.get("no_llm_for_deterministic") in (None, False)
        assert result.get("surface_conflicts") in (None, False)
        assert result.get("convention_first") in (None, False)
        block = _compose_behavioral_block(result)
        assert "BG-005" not in block
        assert "BG-006" not in block
        assert "BG-007" not in block

    def test_canonical_yaml_carries_v12_2_0_defaults(self) -> None:
        """The repo's `context_profiles.yaml` MUST carry the 3 NEW keys
        in `meta.behavioral_guidelines_defaults` for the standard +
        complex tiers (per the gap analysis tier-rollout table)."""
        config = yaml.safe_load(PROFILES_PATH.read_text())
        defaults = config["meta"]["behavioral_guidelines_defaults"]
        for tier in ("standard", "complex"):
            tier_defaults = defaults[tier]
            assert tier_defaults["no_llm_for_deterministic"] is True, (
                f"tier {tier!r} MUST opt into no_llm_for_deterministic per "
                f"the v12.2.0 PV-03 rollout"
            )
            assert tier_defaults["surface_conflicts"] is True, (
                f"tier {tier!r} MUST opt into surface_conflicts per the v12.2.0 PV-03 rollout"
            )
            assert tier_defaults["convention_first"] is True, (
                f"tier {tier!r} MUST opt into convention_first per the v12.2.0 PV-03 rollout"
            )
        # trivial tier opts out of all 3 (one-liner edits don't benefit)
        for new_key in ("no_llm_for_deterministic", "surface_conflicts", "convention_first"):
            assert defaults["trivial"][new_key] is False, (
                f"tier 'trivial' MUST opt out of {new_key!r}"
            )


# ---------------------------------------------------------------------------
# 5. select_context integration — backward compat + behavioral_guidelines key
# ---------------------------------------------------------------------------


class TestSelectContextIntegration:
    """End-to-end via the canonical ``context_profiles.yaml`` — verifies
    the new ``behavioral_guidelines`` key is present in the return dict
    and that profiles that opt-in surface a non-None resolved block."""

    def test_return_dict_contains_behavioral_guidelines_key(self) -> None:
        result = select_context("feature", profiles_path=PROFILES_PATH)
        assert "behavioral_guidelines" in result

    def test_feature_profile_resolves_standard_tier(self) -> None:
        result = select_context("feature", profiles_path=PROFILES_PATH)
        bg = result["behavioral_guidelines"]
        assert bg is not None
        assert bg.get("think_first") is True
        assert bg.get("simplicity_check") is True
        assert bg.get("surgical_scope") == "function"
        assert bg.get("goal_loop") is False

    def test_refactor_profile_resolves_complex_tier(self) -> None:
        result = select_context("refactor", profiles_path=PROFILES_PATH)
        bg = result["behavioral_guidelines"]
        assert bg is not None
        assert bg.get("goal_loop") is True

    def test_design_profile_uses_module_surgical_scope(self) -> None:
        result = select_context("design", profiles_path=PROFILES_PATH)
        bg = result["behavioral_guidelines"]
        assert bg is not None
        assert bg.get("surgical_scope") == "module"

    def test_verify_acceptance_profile_uses_simple_tier(self) -> None:
        result = select_context("acceptance verification", profiles_path=PROFILES_PATH)
        bg = result["behavioral_guidelines"]
        assert bg is not None
        assert bg.get("simplicity_check") is False  # simple tier omits simplicity_check

    def test_profile_without_behavioral_block_returns_none(self) -> None:
        """``hotfix`` profile does NOT carry a behavioral_guidelines block;
        the resolved field MUST be None (preserves v7.x byte-stable shape)."""
        result = select_context("hotfix", profiles_path=PROFILES_PATH)
        assert result["behavioral_guidelines"] is None

    def test_assembled_text_contains_behavioral_block_when_active(self) -> None:
        result = select_context("feature", profiles_path=PROFILES_PATH)
        assert "## Behavioral Guidelines (L2 Task active)" in result["assembled_text"]

    def test_assembled_text_omits_behavioral_block_when_inactive(self) -> None:
        """Profiles without behavioral_guidelines MUST NOT see the block in
        their assembled_text — preserves byte-stable v7.x dispatch shape."""
        result = select_context("hotfix", profiles_path=PROFILES_PATH)
        assert "## Behavioral Guidelines" not in result["assembled_text"]

    def test_behavioral_block_does_not_displace_critical_sections(self) -> None:
        """Token cost of the behavioral block (~ 150 tokens) MUST NOT push
        any ``critical`` section out of the assembled text. Compares
        critical-section count between feature (with block) and hotfix
        (without) — both should retain all their critical-marked sections.
        """
        feature_result = select_context("feature", profiles_path=PROFILES_PATH)
        feature_skipped = set(feature_result["skipped_sections"])
        # 'critical' sections in feature profile must NOT appear in skipped
        config = yaml.safe_load(PROFILES_PATH.read_text())
        feature_priorities = config["profiles"]["feature"]["section_priorities"]
        critical_sections = {
            name for name, prio in feature_priorities.items() if prio == "critical"
        }
        # No critical section was skipped due to budget pressure
        assert critical_sections.isdisjoint(feature_skipped), (
            f"Behavioral block displaced critical sections: {critical_sections & feature_skipped}"
        )


# ---------------------------------------------------------------------------
# 6. _resolve_active_profile + _resolve_dispatch_overrides + helpers
# ---------------------------------------------------------------------------


class TestRefactorHelpers:
    """The refactor extracted three helpers from select_context to reduce
    cyclomatic complexity. These tests exercise the helpers in isolation
    so the parent's cc reduction is robust against future regressions."""

    def test_append_optional_blocks_skips_empty(self) -> None:
        text, tokens = _append_optional_blocks("base", 10, [("", 0), ("extra", 5), ("", 99)])
        assert text == "base\n\nextra"
        assert tokens == 15

    def test_append_optional_blocks_handles_empty_base(self) -> None:
        text, tokens = _append_optional_blocks("", 0, [("first", 7), ("second", 3)])
        assert text == "first\n\nsecond"
        assert tokens == 10

    def test_append_optional_blocks_no_blocks_returns_base_unchanged(self) -> None:
        text, tokens = _append_optional_blocks("base", 99, [])
        assert text == "base"
        assert tokens == 99

    def test_resolve_active_profile_returns_match_without_overrides(self) -> None:
        config = yaml.safe_load(PROFILES_PATH.read_text())
        name, profile, plan_mode = _resolve_active_profile(
            config, "feature", plan_mode=False, round_num=1, escalation_config=None
        )
        assert name == "feature"
        assert profile["description"]
        assert plan_mode is False

    def test_resolve_active_profile_applies_round_escalation(self) -> None:
        config = yaml.safe_load(PROFILES_PATH.read_text())
        _, profile_r1, _ = _resolve_active_profile(
            config, "refactor", plan_mode=False, round_num=1, escalation_config=None
        )
        _, profile_r3, _ = _resolve_active_profile(
            config, "refactor", plan_mode=False, round_num=3, escalation_config=None
        )
        # Round-3 escalation bumps the budget by 20%
        assert profile_r3["token_budget"] > profile_r1.get("token_budget", 0)

    def test_resolve_dispatch_overrides_returns_pair(self) -> None:
        config = yaml.safe_load(PROFILES_PATH.read_text())
        profile = config["profiles"]["feature"]
        model_hint, compression = _resolve_dispatch_overrides(
            profile, "feature", None, config, profile_overrides_applied=False
        )
        assert isinstance(model_hint, str)
        assert isinstance(compression, str)
        assert compression in {"minimal", "standard", "aggressive"}


# ---------------------------------------------------------------------------
# 7. behavioral-guidelines.md reference file health
# ---------------------------------------------------------------------------


class TestReferenceFile:
    """Verify the new references/behavioral-guidelines.md is well-formed
    and within the Large-tier line budget (≤ 1000 lines per SF-1 / C-4)."""

    def test_file_exists(self) -> None:
        assert BEHAVIORAL_REF_PATH.exists()

    def test_file_within_large_tier_line_budget(self) -> None:
        line_count = sum(1 for _ in BEHAVIORAL_REF_PATH.read_text().splitlines())
        assert line_count <= 1000, (
            f"behavioral-guidelines.md has {line_count} lines; "
            "Large tier ceiling is 1000 (SF-1 / C-4)"
        )

    def test_file_has_yaml_frontmatter(self) -> None:
        text = BEHAVIORAL_REF_PATH.read_text()
        assert text.startswith("---\n")
        # Frontmatter MUST contain id, version, purpose, triggers, tier, last_updated
        head = text.split("\n---\n", 1)[0]
        for key in ("id:", "version:", "purpose:", "triggers:", "tier:", "last_updated:"):
            assert key in head, f"missing {key!r} in frontmatter"

    def test_file_documents_all_seven_rules(self) -> None:
        text = BEHAVIORAL_REF_PATH.read_text()
        for rule_id in ("BG-001", "BG-002", "BG-003", "BG-004", "BG-005", "BG-006", "BG-007"):
            assert rule_id in text, f"missing rule id {rule_id} in references doc"

    def test_file_documents_field_shape(self) -> None:
        """The reference file MUST document the 7 dispatch sub-keys so
        agents can map the dispatched ``behavioral_guidelines`` payload to
        the rule semantics. v12.2.0 PV-03 added 3 NEW keys via NEST per A-2.3."""
        text = BEHAVIORAL_REF_PATH.read_text()
        for key in (
            "think_first",
            "simplicity_check",
            "surgical_scope",
            "goal_loop",
            "no_llm_for_deterministic",
            "surface_conflicts",
            "convention_first",
        ):
            assert key in text, f"missing field key {key!r}"


# ---------------------------------------------------------------------------
# 8. v8.2.0 PV-04 — surgical_scope='line' completion
# ---------------------------------------------------------------------------


class TestSurgicalScopeLine:
    """v8.2.0 PV-04 — Line-tier verification.

    Closes the v8.0.0 P-08 deferred AC #2 (line-tier verification). When
    the resolved behavioural block sets ``surgical_scope='line'``,
    :func:`_select_behavioral_sections` augments the returned dict with
    ``line_level_criteria`` (verbatim list extracted from
    ``references/behavioral-guidelines.md#line-level-behavioral-criteria``).
    ``surgical_scope='function'`` and ``surgical_scope='module'`` paths
    MUST stay byte-identical to v8.0.0-p08 (R5 backward-compat
    discipline) so existing dispatchers see no behavioural drift.
    """

    DEFAULTS = TestSelectBehavioralSections.DEFAULTS

    @classmethod
    def _config_with_defaults(cls) -> dict:
        return {"meta": {"behavioral_guidelines_defaults": cls.DEFAULTS}}

    @staticmethod
    def _line_scope_profile() -> dict:
        return {
            "behavioral_guidelines": {
                "think_first": True,
                "simplicity_check": False,
                "surgical_scope": "line",
                "goal_loop": False,
            }
        }

    @staticmethod
    def _function_scope_profile() -> dict:
        return {
            "behavioral_guidelines": {
                "think_first": True,
                "simplicity_check": True,
                "surgical_scope": "function",
                "goal_loop": False,
            }
        }

    @staticmethod
    def _module_scope_profile() -> dict:
        return {
            "behavioral_guidelines": {
                "think_first": True,
                "simplicity_check": True,
                "surgical_scope": "module",
                "goal_loop": True,
            }
        }

    # --- T1-T2: line-scope criteria loading -----------------------------

    def test_load_line_level_criteria_returns_nonempty_list(self) -> None:
        """The reference doc carries the v8.2.0 PV-04 ``Line-Level
        Behavioral Criteria`` section; the loader MUST surface ≥ 1
        criterion (LL-001..LL-005 in the canonical doc)."""
        criteria = _load_line_level_criteria()
        assert isinstance(criteria, list)
        assert len(criteria) >= 1
        assert all(isinstance(c, str) and c for c in criteria)

    def test_load_line_level_criteria_contains_all_canonical_ll_ids(self) -> None:
        """Per the v8.2.0 PV-04 patch plan, the reference doc ships 5
        canonical line-level criteria (LL-001..LL-005). Verbatim
        extraction (CO-2 / C-3) MUST surface every LL-XXX identifier
        present in the markdown."""
        criteria = _load_line_level_criteria()
        joined = "\n".join(criteria)
        for ll_id in ("LL-001", "LL-002", "LL-003", "LL-004", "LL-005"):
            assert ll_id in joined, f"missing canonical line-level id {ll_id}"

    def test_load_line_level_criteria_returns_empty_for_missing_path(self, tmp_path: Path) -> None:
        """S-5 No Silent Failures: a missing reference path returns an
        explicit empty list, never raises ``FileNotFoundError`` — the
        absent-signal is the legitimate v7.x backward-compat shape (older
        reference docs predating PV-04 also surface the same empty list).
        """
        missing = tmp_path / "does-not-exist.md"
        assert _load_line_level_criteria(missing) == []

    def test_load_line_level_criteria_returns_empty_when_section_absent(
        self, tmp_path: Path
    ) -> None:
        """A reference doc that lacks the ``## Line-Level Behavioral
        Criteria`` heading (e.g. a v8.0.0 P-08 baseline doc) returns
        an empty list — no implicit section synthesis."""
        ref = tmp_path / "ref.md"
        ref.write_text("# unrelated heading\n\nSome other text\n", encoding="utf-8")
        assert _load_line_level_criteria(ref) == []

    def test_load_line_level_criteria_extracts_verbatim_bullet_text(self, tmp_path: Path) -> None:
        """Per CO-2 / C-3, the loader MUST preserve bullet text verbatim
        (no paraphrasing, no normalisation, no re-ordering). Continuation
        lines under a bullet are joined with a single space so wrapped
        markdown bullets become single-line criteria."""
        ref = tmp_path / "ref.md"
        ref.write_text(
            "## Line-Level Behavioral Criteria\n\n"
            "- LL-099 fixture rule: first bullet stays\n"
            "  on a wrapped line.\n"
            "- LL-100 second rule single line.\n\n"
            "## Next Section\n\n"
            "- LL-999 outside section, MUST NOT appear.\n",
            encoding="utf-8",
        )
        criteria = _load_line_level_criteria(ref)
        assert criteria == [
            "LL-099 fixture rule: first bullet stays on a wrapped line.",
            "LL-100 second rule single line.",
        ]

    def test_load_line_level_criteria_handles_edge_case_layouts(self, tmp_path: Path) -> None:
        """Coverage pin for the loader's defensive paths:
        * nested-bullet continuation (``- `` prefix on an indented
          continuation line MUST be stripped before joining),
        * paragraph interruption (a non-bullet, non-blank line flushes
          the current bullet without dropping it),
        * trailing bullet at EOF (no blank line after the last
          bullet) is still emitted.
        """
        ref = tmp_path / "ref.md"
        ref.write_text(
            "## Line-Level Behavioral Criteria\n\n"
            "- LL-A first bullet\n"
            "  - nested continuation chunk\n"
            "Plain paragraph mid-section flushes prior bullet.\n"
            "- LL-B trailing bullet without trailing blank",
            encoding="utf-8",
        )
        criteria = _load_line_level_criteria(ref)
        assert criteria == [
            "LL-A first bullet nested continuation chunk",
            "LL-B trailing bullet without trailing blank",
        ]

    # --- T3-T5: _select_behavioral_sections branch behaviour ------------

    def test_line_scope_augments_dict_with_line_level_criteria(self) -> None:
        """``surgical_scope='line'`` MUST inject the verbatim criteria
        list under the new ``line_level_criteria`` key — this is the
        primary closure of v8.0.0 P-08 deferred AC #2."""
        result = _select_behavioral_sections(
            self._line_scope_profile(), self._config_with_defaults()
        )
        assert result is not None
        assert "line_level_criteria" in result
        assert isinstance(result["line_level_criteria"], list)
        assert len(result["line_level_criteria"]) >= 1
        # Verbatim — at least one canonical LL- id must surface.
        joined = "\n".join(result["line_level_criteria"])
        assert "LL-" in joined

    def test_function_scope_byte_identical_to_p08_no_line_criteria_key(self) -> None:
        """R5 backward-compat: ``surgical_scope='function'`` MUST produce
        a dict equal to v8.0.0 P-08 (no ``line_level_criteria`` key)."""
        result = _select_behavioral_sections(
            self._function_scope_profile(), self._config_with_defaults()
        )
        assert result is not None
        assert "line_level_criteria" not in result
        # And the dict equals the input block verbatim (P-08 invariant).
        assert result == self._function_scope_profile()["behavioral_guidelines"]

    def test_module_scope_byte_identical_to_p08_no_line_criteria_key(self) -> None:
        """R5 backward-compat: ``surgical_scope='module'`` MUST produce
        a dict equal to v8.0.0 P-08 (no ``line_level_criteria`` key)."""
        result = _select_behavioral_sections(
            self._module_scope_profile(), self._config_with_defaults()
        )
        assert result is not None
        assert "line_level_criteria" not in result
        assert result == self._module_scope_profile()["behavioral_guidelines"]

    def test_trivial_tier_inherits_line_scope_and_loads_criteria(self) -> None:
        """``tier: trivial`` inherits ``surgical_scope: line`` from
        ``meta.behavioral_guidelines_defaults.trivial`` AND the line-
        level criteria are auto-injected — confirms the tier-fallback
        path participates in PV-04 augmentation."""
        profile = {"behavioral_guidelines": {"tier": "trivial"}}
        result = _select_behavioral_sections(profile, self._config_with_defaults())
        assert result is not None
        assert result["surgical_scope"] == "line"
        assert "line_level_criteria" in result
        assert len(result["line_level_criteria"]) >= 1

    def test_per_key_override_to_line_scope_loads_criteria(self) -> None:
        """A profile that inherits ``tier: standard`` (function scope)
        but overrides ``surgical_scope: line`` MUST receive line criteria
        — per-key override beats tier default and triggers augmentation."""
        profile = {"behavioral_guidelines": {"tier": "standard", "surgical_scope": "line"}}
        result = _select_behavioral_sections(profile, self._config_with_defaults())
        assert result is not None
        assert result["surgical_scope"] == "line"
        assert "line_level_criteria" in result

    # --- T6-T7: _compose_behavioral_block rendering ---------------------

    def test_compose_block_emits_line_criteria_under_bg003_when_line_scope(self) -> None:
        """When the rendered block carries ``surgical_scope='line'`` AND
        ``line_level_criteria`` is populated, each criterion is emitted
        as an indented sub-bullet under BG-003."""
        block = _compose_behavioral_block(
            {
                "think_first": True,
                "surgical_scope": "line",
                "line_level_criteria": [
                    "LL-001 short rule",
                    "LL-002 second rule",
                ],
            }
        )
        assert "BG-003 surgical_scope = 'line'" in block
        assert "  - LL-001 short rule" in block
        assert "  - LL-002 second rule" in block
        # And BG-003 appears BEFORE the criteria sub-bullets (rendering order).
        bg003_index = block.find("BG-003")
        ll001_index = block.find("LL-001 short rule")
        assert 0 <= bg003_index < ll001_index

    def test_compose_block_omits_line_criteria_when_function_scope(self) -> None:
        """R5 backward-compat: ``surgical_scope='function'`` MUST NOT
        emit any LL-XXX sub-bullet even if the dict happened to carry
        ``line_level_criteria`` (defensive — protects against accidental
        cross-scope leakage)."""
        block = _compose_behavioral_block(
            {
                "think_first": True,
                "surgical_scope": "function",
                "line_level_criteria": ["LL-001 should not surface"],
            }
        )
        assert "BG-003 surgical_scope = 'function'" in block
        assert "LL-001" not in block

    # --- T8: select_context end-to-end integration ----------------------

    def test_select_context_with_line_scope_override_loads_criteria(self, tmp_path: Path) -> None:
        """End-to-end via the canonical ``context_profiles.yaml`` — load
        a profile, override ``surgical_scope`` to ``'line'`` via a
        synthetic profile YAML, and verify the resolved
        ``behavioral_guidelines`` carries ``line_level_criteria`` AND
        the rendered ``assembled_text`` carries the LL-XXX sub-bullets.
        """
        config = yaml.safe_load(PROFILES_PATH.read_text())
        # Synthesize a tiny profile with line-scope behavioural block.
        config["profiles"]["pv04_test"] = {
            "description": "PV-04 line-scope integration test profile",
            "goal_hints": ["pv04 line scope"],
            "token_budget": 4000,
            "model_hints": {"default_tier": "balanced"},
            "section_priorities": {"agent_mode_protocol": "critical"},
            "behavioral_guidelines": {
                "think_first": True,
                "simplicity_check": False,
                "surgical_scope": "line",
                "goal_loop": False,
            },
        }
        profile_path = tmp_path / "profiles.yaml"
        profile_path.write_text(yaml.safe_dump(config), encoding="utf-8")

        result = select_context("pv04 line scope", profiles_path=profile_path)
        assert result["profile_name"] == "pv04_test"
        bg = result["behavioral_guidelines"]
        assert bg is not None
        assert bg["surgical_scope"] == "line"
        assert "line_level_criteria" in bg
        # And the rendered text carries the LL-XXX sub-bullets.
        assembled = result["assembled_text"]
        assert "BG-003 surgical_scope = 'line'" in assembled
        assert "LL-" in assembled

    # --- T9: existing function/module dispatch byte-identicality -------

    def test_existing_function_scope_dispatch_unchanged_after_pv04(self) -> None:
        """Regression pin: the canonical ``feature`` profile uses
        ``surgical_scope: function`` per v8.0.0 P-08; PV-04 MUST NOT
        introduce ``line_level_criteria`` into its resolved block,
        and the assembled text MUST NOT carry any LL-XXX sub-bullet.
        Couples with the existing
        :class:`TestSelectContextIntegration` to enforce R5
        byte-identicality on real profiles."""
        result = select_context("feature", profiles_path=PROFILES_PATH)
        bg = result["behavioral_guidelines"]
        assert bg is not None
        assert bg.get("surgical_scope") == "function"
        assert "line_level_criteria" not in bg
        assert "LL-001" not in result["assembled_text"]

    def test_existing_module_scope_dispatch_unchanged_after_pv04(self) -> None:
        """Regression pin (mirror of function-scope test): ``design``
        profile uses ``surgical_scope: module`` per v8.0.0 P-08; PV-04
        MUST NOT mutate its resolved block."""
        result = select_context("design", profiles_path=PROFILES_PATH)
        bg = result["behavioral_guidelines"]
        assert bg is not None
        assert bg.get("surgical_scope") == "module"
        assert "line_level_criteria" not in bg
        assert "LL-001" not in result["assembled_text"]


# ---------------------------------------------------------------------------
# 9. v8.2.0 PV-04 — references file health (line-budget + section presence)
# ---------------------------------------------------------------------------


class TestReferenceFilePV04Section:
    """The references/behavioral-guidelines.md doc gained a new
    ``## Line-Level Behavioral Criteria`` section in v8.2.0 PV-04.
    Verify the section exists, holds ≥ 5 LL-XXX bullets, and stays
    within the SF-1 Large-tier 1000-line budget (with a tighter
    220-line per-patch ceiling per the v8.2.0 patch_plan PV-04 entry).
    """

    def test_pv04_section_heading_present(self) -> None:
        text = BEHAVIORAL_REF_PATH.read_text()
        assert "## Line-Level Behavioral Criteria" in text

    def test_pv04_section_documents_canonical_ll_ids(self) -> None:
        text = BEHAVIORAL_REF_PATH.read_text()
        for ll_id in ("LL-001", "LL-002", "LL-003", "LL-004", "LL-005"):
            assert ll_id in text, f"missing canonical line-level id {ll_id}"

    def test_pv04_section_within_tight_per_patch_line_ceiling(self) -> None:
        """v8.2.0 patch_plan §3 PV-04 originally capped the file at ≤ 220 lines
        (well within the SF-1 Large-tier 1000 ceiling). Tighter
        per-patch ceiling acts as an early-warning regression pin so
        future PV-04-style appends don't silently consume the headroom.

        v9.0.0 PV-02 (v8.4.2) closure of F-04 body extension added the
        S-8 Composition Rule + Severity Matrix + v8.2.x Primitive
        References sections (~+64 LOC). Per-patch ceiling bumped 240 →
        320 to absorb the documented PV-02 extension; still 32% of the
        SF-1 Large-tier 1000 ceiling so the early-warning function is
        preserved. See `.local/research/v9.0.0_reference_review.md` F-04
        + `.local/research/v9.0.0_implementation_plan.md` §6.2.

        v12.2.0 PV-03 added BG-005..BG-007 (Mnimiy 3-rule extension)
        per `.local/research/v12.2.0_gap_analysis.md` §2 D-2: 3 new Rule
        sections (~30 lines each = ~90 LOC) + 3 new Severity Matrix rows
        + extended Rule Application Matrix + extended Field Shape + token
        cost recalibration text. Per-patch ceiling bumped 320 → 500 to
        absorb the v12.2.0 PV-03 extension; still 50% of the SF-1 Large-
        tier 1000 ceiling.
        """
        line_count = sum(1 for _ in BEHAVIORAL_REF_PATH.read_text().splitlines())
        assert line_count <= 500, (
            f"behavioral-guidelines.md has {line_count} lines; "
            "v12.2.0 PV-03 per-patch ceiling is 500 (Large-tier ceiling 1000)"
        )
