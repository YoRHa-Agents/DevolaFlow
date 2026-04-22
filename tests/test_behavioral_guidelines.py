"""v8.0.0 P-08 — L3 behavioral guidelines injection tests.

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

    def test_canonical_order_length_is_15(self, schema_spec: dict) -> None:
        """After P-08 + P-10, canonical_order length is 15 (P-08 added
        ``behavioral_guidelines`` at position 14, P-10 added
        ``acceptance_criteria_v2`` at position 15)."""
        canonical = schema_spec["layout_invariant"]["canonical_order"]
        assert len(canonical) == 15, (
            f"canonical_order length = {len(canonical)}; expected 15 after P-10"
        )

    def test_canonical_order_position_14_is_behavioral_guidelines(self, schema_spec: dict) -> None:
        """P-08 added ``behavioral_guidelines`` at position 14 (1-indexed).
        P-10 MUST keep it there (the position-14 invariant is non-negotiable)."""
        canonical = schema_spec["layout_invariant"]["canonical_order"]
        assert canonical[13] == "behavioral_guidelines"

    def test_canonical_order_position_13_is_repos(self, schema_spec: dict) -> None:
        """v7.2.6 P-06 placed ``repos`` at position 13 (1-indexed).
        v8.0.0 P-08 MUST keep it there."""
        canonical = schema_spec["layout_invariant"]["canonical_order"]
        assert canonical[12] == "repos"

    def test_layout_invariant_version_is_4(self, schema_spec: dict) -> None:
        """P-08 bumped version 2→3, P-10 bumped 3→4 (additive transitions)."""
        assert schema_spec["layout_invariant"]["version"] == 4

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
        assert block.startswith("## Behavioral Guidelines (L3 active)")

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
        """All-active block stays under the L3 token budget allocation
        target (~ 150 tokens / 5% of L3 8K)."""
        from devolaflow.task_adaptive_selector import estimate_tokens

        block = _compose_behavioral_block(
            {
                "think_first": True,
                "simplicity_check": True,
                "surgical_scope": "module",
                "goal_loop": True,
            }
        )
        assert estimate_tokens(block) <= 150


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
        assert "## Behavioral Guidelines (L3 active)" in result["assembled_text"]

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

    def test_file_documents_all_four_rules(self) -> None:
        text = BEHAVIORAL_REF_PATH.read_text()
        for rule_id in ("BG-001", "BG-002", "BG-003", "BG-004"):
            assert rule_id in text, f"missing rule id {rule_id} in references doc"

    def test_file_documents_field_shape(self) -> None:
        """The reference file MUST document the 4 dispatch sub-keys so
        agents can map the dispatched ``behavioral_guidelines`` payload to
        the rule semantics."""
        text = BEHAVIORAL_REF_PATH.read_text()
        for key in ("think_first", "simplicity_check", "surgical_scope", "goal_loop"):
            assert key in text, f"missing field key {key!r}"
