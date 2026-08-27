"""Tests for the task-adaptive context selector.

Covers: load_profiles, load_skill_md, extract_section, estimate_tokens,
match_profile, select_context, and the CLI main() entry point.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

from devolaflow.selector_cli import main
from devolaflow.task_adaptive_selector import (
    PRIORITY_ORDER,
    TASK_TYPE_TIMEOUT_DEFAULTS,
    TASK_TYPE_TIMEOUT_FALLBACK,
    VALID_COMPRESSION_INTENSITIES,
    VALID_MODEL_HINTS,
    _resolve_advisor_text,
    apply_plan_mode_overrides,
    estimate_tokens,
    extract_section,
    load_profiles,
    load_skill_md,
    match_profile,
    resolve_compression_intensity,
    resolve_decomposition_config,
    resolve_model_hint,
    resolve_timeout_seconds,
    select_context,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
PROFILES_YAML = REPO_ROOT / "workflow-system" / "agent" / "context_profiles.yaml"


class TestLoadProfiles:
    def test_loads_default_path(self) -> None:
        config = load_profiles(PROFILES_YAML)
        assert "meta" in config
        assert "profiles" in config
        assert "sections" in config
        assert config["meta"]["layer_token_budgets"] == {
            "l0_project": 5000,
            "l1_wave": 5000,
            "l2_task": 8000,
        }

    def test_loads_explicit_path(self, tmp_path: Path) -> None:
        data = {
            "meta": {"default_profile": "test"},
            "sections": {"sec1": {"lines": "1-5", "tokens_est": 50}},
            "profiles": {
                "test": {
                    "token_budget": 1000,
                    "section_priorities": {"sec1": "critical"},
                }
            },
        }
        p = tmp_path / "profiles.yaml"
        p.write_text(yaml.dump(data))
        config = load_profiles(p)
        assert config["meta"]["default_profile"] == "test"

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_profiles(tmp_path / "nonexistent.yaml")


class TestLoadSkillMd:
    def test_loads_skill_md(self) -> None:
        config = load_profiles(PROFILES_YAML)
        text = load_skill_md(config)
        assert "DevolaFlow" in text
        assert len(text) > 100


class TestExtractSection:
    def test_extract_valid_range(self) -> None:
        text = "line1\nline2\nline3\nline4\nline5"
        result = extract_section(text, "2-4")
        assert result == "line2\nline3\nline4"

    def test_extract_single_line(self) -> None:
        text = "line1\nline2\nline3"
        result = extract_section(text, "2-2")
        assert result == "line2"

    def test_extract_first_line(self) -> None:
        text = "line1\nline2\nline3"
        result = extract_section(text, "1-1")
        assert result == "line1"

    def test_extract_all_lines(self) -> None:
        text = "a\nb\nc"
        result = extract_section(text, "1-3")
        assert result == "a\nb\nc"


class TestEstimateTokens:
    def test_nonempty_string(self) -> None:
        tokens = estimate_tokens("hello world this is a test")
        assert tokens >= 1

    def test_empty_string(self) -> None:
        tokens = estimate_tokens("")
        assert tokens >= 0

    def test_long_string_proportional(self) -> None:
        short = estimate_tokens("hello")
        long_ = estimate_tokens("hello " * 100)
        assert long_ > short


class TestMatchProfile:
    @pytest.fixture
    def config(self) -> dict:
        return load_profiles(PROFILES_YAML)

    def test_exact_match(self, config: dict) -> None:
        assert match_profile("hotfix", config) == "hotfix"
        assert match_profile("feature", config) == "feature"
        assert match_profile("research", config) == "research"
        assert match_profile("refactor", config) == "refactor"
        assert match_profile("review", config) == "review"
        assert match_profile("design", config) == "design"

    def test_goal_hint_match(self, config: dict) -> None:
        assert match_profile("fix bug in auth", config) == "hotfix"
        assert match_profile("implement feature for users", config) == "feature"
        assert match_profile("compare frameworks", config) == "research"
        assert match_profile("clean up legacy code", config) == "refactor"
        assert match_profile("security audit", config) == "security-audit"
        assert match_profile("architect new API", config) == "design"

    def test_new_profile_routing(self, config: dict) -> None:
        assert match_profile("migrate", config) == "migration"
        assert match_profile("upgrade database", config) == "migration"
        assert match_profile("security", config) == "security-audit"
        assert match_profile("write docs", config) == "documentation"
        assert match_profile("prototype", config) == "spike-poc"
        assert match_profile("RDRR", config) == "rdrr"
        assert match_profile("demo", config) == "demo-showcase"
        assert match_profile("optimize", config) == "perf-optimization"
        assert match_profile("setup env", config) == "dependency-setup"
        assert match_profile("onboard", config) == "onboarding"
        assert match_profile("optimize skill", config) == "skill-optimization"
        assert match_profile("self_update", config) == "self_update"
        assert match_profile("feedback", config) == "feedback"

    def test_longest_match_wins(self, config: dict) -> None:
        """Verify the longest hint match takes priority over shorter ones."""
        assert match_profile("optimize skill context", config) == "skill-optimization"
        assert match_profile("benchmark context", config) == "skill-optimization"

    def test_fallback_to_default(self, config: dict) -> None:
        result = match_profile("completely_unknown_xyzzy", config)
        assert result == config["meta"]["default_profile"]

    def test_case_insensitive_hint(self, config: dict) -> None:
        assert match_profile("FIX BUG", config) == "hotfix"
        assert match_profile("REFACTOR", config) == "refactor"

    def test_bare_next_wave_does_not_route_to_pathfind(self, config: dict) -> None:
        """A generic wave reference is not enough to select reconnaissance."""
        assert match_profile("prepare the next wave", config) != "pathfind"


class TestSelectContext:
    def test_hotfix_profile(self) -> None:
        result = select_context("hotfix", profiles_path=PROFILES_YAML)
        assert result["profile_name"] == "hotfix"
        assert result["total_tokens"] <= result["budget"]
        assert result["utilization_pct"] <= 100.0
        assert len(result["selected_sections"]) > 0
        assert len(result["assembled_text"]) > 0

    def test_feature_profile(self) -> None:
        result = select_context("feature", profiles_path=PROFILES_YAML)
        assert result["profile_name"] == "feature"
        assert result["total_tokens"] <= result["budget"]
        assert len(result["selected_sections"]) > 0

    def test_research_profile(self) -> None:
        result = select_context("research", profiles_path=PROFILES_YAML)
        assert result["profile_name"] == "research"
        assert result["total_tokens"] <= result["budget"]

    def test_refactor_profile(self) -> None:
        result = select_context("refactor", profiles_path=PROFILES_YAML)
        assert result["profile_name"] == "refactor"

    def test_review_profile(self) -> None:
        result = select_context("review", profiles_path=PROFILES_YAML)
        assert result["profile_name"] == "review"

    def test_design_profile(self) -> None:
        result = select_context("design", profiles_path=PROFILES_YAML)
        assert result["profile_name"] == "design"

    def test_new_profiles_select(self) -> None:
        for task_type, expected_profile in [
            ("migrate", "migration"),
            ("security", "security-audit"),
            ("write docs", "documentation"),
            ("prototype", "spike-poc"),
            ("RDRR", "rdrr"),
            ("demo", "demo-showcase"),
            ("optimize", "perf-optimization"),
            ("setup env", "dependency-setup"),
            ("onboard", "onboarding"),
            ("self update", "self_update"),
            ("feedback loop", "feedback"),
        ]:
            result = select_context(task_type, profiles_path=PROFILES_YAML)
            assert result["profile_name"] == expected_profile, (
                f"{task_type} → {result['profile_name']} (expected {expected_profile})"
            )
            assert result["total_tokens"] <= result["budget"]
            assert len(result["selected_sections"]) > 0

    def test_goal_hint_routing(self) -> None:
        result = select_context("fix bug in JWT", profiles_path=PROFILES_YAML)
        assert result["profile_name"] == "hotfix"

    def test_budget_respected(self) -> None:
        result = select_context("hotfix", profiles_path=PROFILES_YAML)
        assert result["total_tokens"] <= result["budget"]

    def test_skipped_sections_reported(self) -> None:
        result = select_context("hotfix", profiles_path=PROFILES_YAML)
        assert isinstance(result["skipped_sections"], list)
        assert len(result["skipped_sections"]) > 0

    def test_extra_context_populated(self) -> None:
        result = select_context("hotfix", profiles_path=PROFILES_YAML)
        assert isinstance(result["extra_context"], list)

    def test_verbose_mode(self, capsys: pytest.CaptureFixture) -> None:
        select_context("hotfix", profiles_path=PROFILES_YAML, verbose=True)

    def test_result_structure(self) -> None:
        result = select_context("feature", profiles_path=PROFILES_YAML)
        expected_keys = {
            "profile_name",
            "description",
            "selected_sections",
            "assembled_text",
            "total_tokens",
            "budget",
            "utilization_pct",
            "skipped_sections",
            "extra_context",
            "rationale",
            "learnings_included",
            "model_hint",
            "advisor_enabled",
            "decomposition",
            "compression_intensity",
            "timeout_seconds",  # v14.5.0 G-037 — additive dispatch hint
            "round_num",
            "escalation_applied",
            "plan_mode",
            "plan_mode_applied",
            "behavioral_guidelines",
            "agents_md_slice",  # v17.0.0 R3 G17-B3 — additive slice account
        }
        assert set(result.keys()) == expected_keys

    def test_budget_overflow_handling(self, tmp_path: Path) -> None:
        """With a very small budget, sections should be skipped."""
        data = {
            "meta": {"default_profile": "tiny"},
            "sections": {
                "sec1": {"lines": "1-5", "tokens_est": 100},
                "sec2": {"lines": "6-10", "tokens_est": 200},
            },
            "profiles": {
                "tiny": {
                    "description": "tiny budget",
                    "token_budget": 10,
                    "section_priorities": {"sec1": "critical", "sec2": "critical"},
                    "goal_hints": [],
                }
            },
        }
        p = tmp_path / "profiles.yaml"
        p.write_text(yaml.dump(data))

        skill = tmp_path / "SKILL.md"
        skill.write_text("\n".join(f"line{i}" for i in range(1, 20)))

        from unittest.mock import patch

        with patch(
            "devolaflow.task_adaptive_selector.load_skill_md",
            return_value=skill.read_text(),
        ):
            result = select_context("tiny", profiles_path=p)
        assert result["total_tokens"] <= result["budget"] or len(result["skipped_sections"]) > 0


class TestResolveModelHint:
    def test_returns_override_when_matched(self) -> None:
        profile_config = {
            "model_hints": {
                "default_tier": "balanced",
                "overrides": {"code_review": "quality", "test_execution": "budget"},
            }
        }
        assert resolve_model_hint("code_review", profile_config) == "quality"
        assert resolve_model_hint("test_execution", profile_config) == "budget"

    def test_returns_default_tier_when_no_override(self) -> None:
        profile_config = {
            "model_hints": {
                "default_tier": "balanced",
                "overrides": {"code_review": "quality"},
            }
        }
        assert resolve_model_hint("unknown_task", profile_config) == "balanced"

    def test_returns_inherit_when_no_model_hints(self) -> None:
        assert resolve_model_hint("any_task", {}) == "inherit"

    def test_returns_inherit_for_invalid_default(self) -> None:
        profile_config = {"model_hints": {"default_tier": "invalid_tier"}}
        assert resolve_model_hint("any_task", profile_config) == "inherit"

    def test_returns_inherit_for_invalid_override(self) -> None:
        profile_config = {
            "model_hints": {
                "default_tier": "balanced",
                "overrides": {"code_review": "invalid_tier"},
            }
        }
        assert resolve_model_hint("code_review", profile_config) == "balanced"

    def test_all_valid_hints_accepted(self) -> None:
        for hint in VALID_MODEL_HINTS:
            config = {"model_hints": {"default_tier": hint}}
            assert resolve_model_hint("task", config) == hint


class TestNewProfiles:
    def test_self_update_profile_routing(self) -> None:
        config = load_profiles(PROFILES_YAML)
        assert match_profile("self_update", config) == "self_update"
        assert match_profile("self update workflow", config) == "self_update"
        assert match_profile("update skill", config) == "self_update"

    def test_feedback_profile_routing(self) -> None:
        config = load_profiles(PROFILES_YAML)
        assert match_profile("feedback", config) == "feedback"
        assert match_profile("feedback loop", config) == "feedback"
        assert match_profile("retrospective", config) == "feedback"

    def test_self_update_select(self) -> None:
        result = select_context("self_update", profiles_path=PROFILES_YAML)
        assert result["profile_name"] == "self_update"
        assert result["total_tokens"] <= result["budget"]
        assert result["budget"] == 3100
        assert len(result["selected_sections"]) > 0
        assert result["model_hint"] in VALID_MODEL_HINTS

    def test_feedback_select(self) -> None:
        result = select_context("feedback", profiles_path=PROFILES_YAML)
        assert result["profile_name"] == "feedback"
        assert result["total_tokens"] <= result["budget"]
        # v7.0.0: bumped 2375 → 2475 to fit rationalization_prevention after
        # corrected line ranges (cache-layout invariant cycle, ADR-001).
        assert result["budget"] == 2475
        assert len(result["selected_sections"]) > 0
        assert result["model_hint"] in VALID_MODEL_HINTS


class TestModelHintInSelectContext:
    def test_model_hint_present_in_result(self) -> None:
        result = select_context("feature", profiles_path=PROFILES_YAML)
        assert "model_hint" in result
        assert result["model_hint"] in VALID_MODEL_HINTS

    def test_all_profiles_have_valid_model_hint(self) -> None:
        config = load_profiles(PROFILES_YAML)
        for profile_name in config["profiles"]:
            result = select_context(profile_name, profiles_path=PROFILES_YAML)
            assert result["model_hint"] in VALID_MODEL_HINTS, (
                f"Profile {profile_name} has invalid model_hint: {result['model_hint']}"
            )


class TestMain:
    def test_no_args_exits(self) -> None:
        old_argv = sys.argv
        sys.argv = ["task_adaptive_selector.py"]
        try:
            with pytest.raises(SystemExit) as exc:
                main()
            assert exc.value.code == 1
        finally:
            sys.argv = old_argv

    def test_with_task_type(self, capsys: pytest.CaptureFixture) -> None:
        old_argv = sys.argv
        sys.argv = ["task_adaptive_selector.py", "hotfix"]
        try:
            main()
        finally:
            sys.argv = old_argv
        out = capsys.readouterr().out
        assert "Profile: hotfix" in out
        assert "Token budget:" in out
        assert "Selected sections:" in out

    def test_with_verbose_flag(self, capsys: pytest.CaptureFixture) -> None:
        old_argv = sys.argv
        sys.argv = ["task_adaptive_selector.py", "hotfix", "--verbose"]
        try:
            main()
        finally:
            sys.argv = old_argv
        out = capsys.readouterr().out
        assert "Profile:" in out

    def test_with_full_flag(self, capsys: pytest.CaptureFixture) -> None:
        old_argv = sys.argv
        sys.argv = ["task_adaptive_selector.py", "feature", "--full"]
        try:
            main()
        finally:
            sys.argv = old_argv
        out = capsys.readouterr().out
        assert "ASSEMBLED CONTEXT" in out


class TestAdvisorConfig:
    def test_advisor_enabled_for_feature(self) -> None:
        result = select_context("feature", profiles_path=PROFILES_YAML)
        assert result["advisor_enabled"] is True
        assert "## Advisor Tool" in result["assembled_text"]
        assert "Advisor enabled" in result["assembled_text"]

    def test_advisor_enabled_for_refactor(self) -> None:
        result = select_context("refactor", profiles_path=PROFILES_YAML)
        assert result["advisor_enabled"] is True
        assert "## Advisor Tool" in result["assembled_text"]

    def test_advisor_enabled_for_security_audit(self) -> None:
        result = select_context("security", profiles_path=PROFILES_YAML)
        assert result["advisor_enabled"] is True
        assert "## Advisor Tool" in result["assembled_text"]

    def test_advisor_enabled_for_migration(self) -> None:
        result = select_context("migrate", profiles_path=PROFILES_YAML)
        assert result["advisor_enabled"] is True
        assert "## Advisor Tool" in result["assembled_text"]

    def test_advisor_disabled_for_hotfix(self) -> None:
        result = select_context("hotfix", profiles_path=PROFILES_YAML)
        assert result["advisor_enabled"] is False
        assert "## Advisor Tool" not in result["assembled_text"]

    def test_advisor_disabled_for_research(self) -> None:
        result = select_context("research", profiles_path=PROFILES_YAML)
        assert result["advisor_enabled"] is False
        assert "## Advisor Tool" not in result["assembled_text"]

    def test_advisor_disabled_for_design(self) -> None:
        result = select_context("design", profiles_path=PROFILES_YAML)
        assert result["advisor_enabled"] is False

    def test_advisor_disabled_for_review(self) -> None:
        result = select_context("review", profiles_path=PROFILES_YAML)
        assert result["advisor_enabled"] is False

    def test_advisor_text_contains_config(self) -> None:
        result = select_context("feature", profiles_path=PROFILES_YAML)
        text = result["assembled_text"]
        assert "max 3 uses" in text
        assert "$0.3" in text
        assert "complexity_high" in text
        assert "cross_module_architecture" in text
        assert "stalled_convergence" in text

    def test_advisor_key_present_in_all_profiles(self) -> None:
        config = load_profiles(PROFILES_YAML)
        for profile_name in config["profiles"]:
            result = select_context(profile_name, profiles_path=PROFILES_YAML)
            assert "advisor_enabled" in result, (
                f"Profile {profile_name} missing advisor_enabled key"
            )
            assert isinstance(result["advisor_enabled"], bool)


class TestPriorityOrder:
    def test_priority_order_values(self) -> None:
        assert PRIORITY_ORDER == ["critical", "important", "supplementary"]


class TestResolveDecompositionConfig:
    def test_enabled_profile(self) -> None:
        profile = {
            "decomposition": {
                "enabled": True,
                "max_sub_agents": 4,
                "max_nesting_depth": 1,
                "sub_agent_model_hint": "budget",
                "sub_agent_context_budget": 3000,
                "coordinator_retains_advisor": True,
                "gen_verify_mode": True,
                "gen_verify_max_rounds": 3,
            }
        }
        result = resolve_decomposition_config(profile)
        assert result["enabled"] is True
        assert result["max_sub_agents"] == 4
        assert result["gen_verify_mode"] is True

    def test_disabled_profile(self) -> None:
        profile = {"decomposition": {"enabled": False}}
        result = resolve_decomposition_config(profile)
        assert result["enabled"] is False
        assert result["max_sub_agents"] == 4  # default

    def test_missing_decomposition_key(self) -> None:
        result = resolve_decomposition_config({})
        assert result["enabled"] is False
        assert result["max_sub_agents"] == 4
        assert result["sub_agent_model_hint"] == "budget"
        assert result["gen_verify_mode"] is False

    def test_feature_profile_has_decomposition_enabled(self) -> None:
        result = select_context("feature", profiles_path=PROFILES_YAML)
        assert result["decomposition"]["enabled"] is True

    def test_hotfix_profile_has_decomposition_disabled(self) -> None:
        result = select_context("hotfix", profiles_path=PROFILES_YAML)
        assert result["decomposition"]["enabled"] is False

    def test_partial_decomposition_config_fills_defaults(self) -> None:
        profile = {"decomposition": {"enabled": True, "max_sub_agents": 6}}
        result = resolve_decomposition_config(profile)
        assert result["enabled"] is True
        assert result["max_sub_agents"] == 6
        assert result["max_nesting_depth"] == 1
        assert result["sub_agent_model_hint"] == "budget"
        assert result["sub_agent_context_budget"] == 3000
        assert result["coordinator_retains_advisor"] is True
        assert result["gen_verify_mode"] is False
        assert result["gen_verify_max_rounds"] == 3

    def test_all_profiles_have_decomposition(self) -> None:
        config = load_profiles(PROFILES_YAML)
        for profile_name in config["profiles"]:
            result = select_context(profile_name, profiles_path=PROFILES_YAML)
            assert "decomposition" in result, f"Profile {profile_name} missing decomposition key"
            assert isinstance(result["decomposition"], dict)
            assert "enabled" in result["decomposition"]


class TestResolveCompressionIntensity:
    def test_known_boundary(self) -> None:
        config = {"meta": {"compression_defaults": {"l1_to_l2": "minimal"}}}
        assert resolve_compression_intensity("l1_to_l2", config) == "minimal"

    def test_unknown_boundary_defaults_to_standard(self) -> None:
        config = {"meta": {"compression_defaults": {}}}
        assert resolve_compression_intensity("unknown", config) == "standard"

    def test_missing_compression_defaults(self) -> None:
        assert resolve_compression_intensity("l1_to_l2", {}) == "standard"

    def test_invalid_value_defaults_to_standard(self) -> None:
        config = {"meta": {"compression_defaults": {"l1_to_l2": "invalid"}}}
        assert resolve_compression_intensity("l1_to_l2", config) == "standard"

    def test_all_valid_intensities(self) -> None:
        for intensity in VALID_COMPRESSION_INTENSITIES:
            config = {"meta": {"compression_defaults": {"l1_to_l2": intensity}}}
            assert resolve_compression_intensity("l1_to_l2", config) == intensity

    def test_compression_intensity_in_select_context(self) -> None:
        result = select_context("feature", profiles_path=PROFILES_YAML)
        assert "compression_intensity" in result
        assert result["compression_intensity"] in VALID_COMPRESSION_INTENSITIES

    def test_compression_intensity_matches_l1_to_l2_config(self) -> None:
        config = load_profiles(PROFILES_YAML)
        result = select_context("hotfix", profiles_path=PROFILES_YAML)
        assert set(config["meta"]["compression_defaults"]) == {
            "l0_to_l1",
            "l1_to_l2",
            "l2_to_l1",
            "l1_to_l0",
        }
        expected = resolve_compression_intensity("l1_to_l2", config)
        assert result["compression_intensity"] == expected

    def test_all_profiles_have_compression_intensity(self) -> None:
        config = load_profiles(PROFILES_YAML)
        for profile_name in config["profiles"]:
            result = select_context(profile_name, profiles_path=PROFILES_YAML)
            assert "compression_intensity" in result, (
                f"Profile {profile_name} missing compression_intensity"
            )
            assert result["compression_intensity"] in VALID_COMPRESSION_INTENSITIES


class TestSelectContextRoundEscalation:
    """V6-02: select_context must honour the ``round_num`` parameter."""

    def test_select_context_round1_no_escalation(self) -> None:
        result = select_context("refactor", profiles_path=PROFILES_YAML)
        assert result["round_num"] == 1
        assert result["escalation_applied"] is False

    def test_select_context_round2_budget_increased(self) -> None:
        r1 = select_context("refactor", profiles_path=PROFILES_YAML, round_num=1)
        r2 = select_context("refactor", profiles_path=PROFILES_YAML, round_num=2)
        # Round 2 defaults don't bump budget but MUST add critical sections
        assert r2["escalation_applied"] is True
        assert r2["round_num"] == 2
        r2_critical_in_skipped = any(
            s in r2["skipped_sections"] for s in ("rationalization_prevention", "convergence_loop")
        )
        r1_critical_forced = not r2_critical_in_skipped or r2["total_tokens"] >= r1["total_tokens"]
        assert r1_critical_forced

    def test_select_context_round3_quality_model(self) -> None:
        r1 = select_context("refactor", profiles_path=PROFILES_YAML, round_num=1)
        r3 = select_context("refactor", profiles_path=PROFILES_YAML, round_num=3)
        assert r3["model_hint"] == "quality"
        assert r3["escalation_applied"] is True
        assert r3["budget"] > r1["budget"]
        assert r3["budget"] == int(r1["budget"] * 1.2)

    def test_select_context_round_num_in_result(self) -> None:
        for rn in (1, 2, 3, 5):
            result = select_context("refactor", profiles_path=PROFILES_YAML, round_num=rn)
            assert result["round_num"] == rn, f"round_num={rn} expected, got {result['round_num']}"

    def test_select_context_custom_escalation_config(self) -> None:
        custom = {
            2: {
                "model_hint_override": "balanced",
                "token_budget_increase_pct": 50,
            }
        }
        r1 = select_context("refactor", profiles_path=PROFILES_YAML, round_num=1)
        r2 = select_context(
            "refactor",
            profiles_path=PROFILES_YAML,
            round_num=2,
            escalation_config=custom,
        )
        assert r2["model_hint"] == "balanced"
        assert r2["budget"] == int(r1["budget"] * 1.5)


class TestMainRoundFlag:
    """V6-02: CLI ``--round N`` flag wiring."""

    def test_main_with_round_flag(self, capsys: pytest.CaptureFixture) -> None:
        old_argv = sys.argv
        sys.argv = ["task_adaptive_selector.py", "refactor", "--round", "3", "--verbose"]
        try:
            main()
        finally:
            sys.argv = old_argv
        out = capsys.readouterr().out
        assert "Round: 3" in out
        assert "Profile: refactor" in out

    def test_main_round_flag_defaults_to_one(self, capsys: pytest.CaptureFixture) -> None:
        old_argv = sys.argv
        sys.argv = ["task_adaptive_selector.py", "refactor", "--verbose"]
        try:
            main()
        finally:
            sys.argv = old_argv
        out = capsys.readouterr().out
        assert "Round: 1" in out

    def test_main_round_flag_invalid_falls_back_to_one(self, capsys: pytest.CaptureFixture) -> None:
        old_argv = sys.argv
        sys.argv = ["task_adaptive_selector.py", "refactor", "--round", "abc", "--verbose"]
        try:
            main()
        finally:
            sys.argv = old_argv
        out = capsys.readouterr().out
        assert "Round: 1" in out


class TestPlanModeDetection:
    """V6-03: Plan-mode detection drives :func:`select_context` overrides."""

    def test_plan_mode_default_auto_detect_off(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Without env var or marker file, default behaviour is unchanged."""
        monkeypatch.delenv("DEVOLAFLOW_PLAN_MODE", raising=False)
        monkeypatch.chdir(tmp_path)
        result = select_context("refactor", profiles_path=PROFILES_YAML)
        assert result["plan_mode"] is False
        assert result["plan_mode_applied"] is False

    def test_plan_mode_explicit_true_overrides_priorities(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """plan_mode=True escalates plan-relevant sections + sets quality model.

        Section-priority overrides are verified at the profile level via
        :func:`apply_plan_mode_overrides`; every override name is a current
        ``context_profiles.yaml`` section key backed by the live SKILL.md.
        ``model_hint`` is verified via :func:`select_context` directly.
        """
        monkeypatch.delenv("DEVOLAFLOW_PLAN_MODE", raising=False)
        monkeypatch.chdir(tmp_path)

        result = select_context("refactor", profiles_path=PROFILES_YAML, plan_mode=True)
        assert result["plan_mode"] is True
        assert result["model_hint"] == "quality"

        baseline_profile = {"section_priorities": {"agent_mode_protocol": "important"}}
        plan_profile = apply_plan_mode_overrides(baseline_profile)
        assert plan_profile["section_priorities"]["hierarchy_table"] == "critical"
        assert plan_profile["section_priorities"]["gate_mechanism"] == "critical"
        assert plan_profile["section_priorities"]["rationalization_prevention"] == "critical"
        assert plan_profile["section_priorities"]["agent_mode_protocol"] == "supplementary"

    def test_plan_mode_explicit_false_skips_detection(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """plan_mode=False disables detection even when env var is set."""
        monkeypatch.setenv("DEVOLAFLOW_PLAN_MODE", "1")
        monkeypatch.chdir(tmp_path)
        result = select_context("refactor", profiles_path=PROFILES_YAML, plan_mode=False)
        assert result["plan_mode"] is False
        assert result["plan_mode_applied"] is False

    def test_plan_mode_env_var_detection(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """DEVOLAFLOW_PLAN_MODE=1 triggers auto-detect when plan_mode param is None."""
        monkeypatch.setenv("DEVOLAFLOW_PLAN_MODE", "1")
        monkeypatch.chdir(tmp_path)
        result = select_context("refactor", profiles_path=PROFILES_YAML)
        assert result["plan_mode"] is True
        assert result["model_hint"] == "quality"

    def test_plan_mode_marker_file_detection(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A `.devolaflow_plan_mode` file in cwd triggers auto-detect."""
        monkeypatch.delenv("DEVOLAFLOW_PLAN_MODE", raising=False)
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".devolaflow_plan_mode").write_text("")
        result = select_context("refactor", profiles_path=PROFILES_YAML)
        assert result["plan_mode"] is True
        assert result["plan_mode_applied"] is True

    def test_plan_mode_overrides_apply_before_round_escalation(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """plan_mode=True AND round_num=3 compose: plan adds critical, round adds budget.

        The visible composition is verified via :func:`select_context`
        (model_hint, budget delta, both flags set). The plan-then-round
        section-priority composition is verified by chaining
        :func:`apply_plan_mode_overrides` and :func:`apply_round_escalation`
        directly on a baseline profile: plan-mode lifts ``convergence_loop``
        to ``important``, round-3 then re-escalates it to ``critical``.
        """
        from devolaflow.task_adaptive_selector import apply_round_escalation

        monkeypatch.delenv("DEVOLAFLOW_PLAN_MODE", raising=False)
        monkeypatch.chdir(tmp_path)

        r_round1 = select_context("refactor", profiles_path=PROFILES_YAML, round_num=1)
        r_combo = select_context(
            "refactor", profiles_path=PROFILES_YAML, plan_mode=True, round_num=3
        )

        assert r_combo["plan_mode"] is True
        assert r_combo["escalation_applied"] is True
        assert r_combo["round_num"] == 3
        assert r_combo["model_hint"] == "quality"
        assert r_combo["budget"] == int(r_round1["budget"] * 1.2)

        baseline = {"section_priorities": {}, "token_budget": 5000}
        composed = apply_round_escalation(apply_plan_mode_overrides(baseline), 3)
        assert composed["section_priorities"]["hierarchy_table"] == "critical"
        assert composed["section_priorities"]["rationalization_prevention"] == "critical"
        assert composed["section_priorities"]["convergence_loop"] == "critical"
        assert composed["section_priorities"]["gate_mechanism"] == "critical"
        assert composed["token_budget"] == int(5000 * 1.2)

    def test_plan_mode_in_result_dict(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Return value always exposes both plan_mode and plan_mode_applied."""
        monkeypatch.delenv("DEVOLAFLOW_PLAN_MODE", raising=False)
        monkeypatch.chdir(tmp_path)
        result = select_context("refactor", profiles_path=PROFILES_YAML)
        assert "plan_mode" in result
        assert "plan_mode_applied" in result
        assert isinstance(result["plan_mode"], bool)
        assert isinstance(result["plan_mode_applied"], bool)

    def test_apply_plan_mode_overrides_does_not_mutate_profile(self) -> None:
        """The helper must return a new dict and leave its input untouched."""
        original = {
            "section_priorities": {
                "hierarchy_table": "supplementary",
                "agent_mode_protocol": "critical",
            },
            "model_hint": "balanced",
            "compression_intensity": "standard",
            "token_budget": 4000,
        }
        snapshot = {
            "section_priorities": dict(original["section_priorities"]),
            "model_hint": original["model_hint"],
            "compression_intensity": original["compression_intensity"],
            "token_budget": original["token_budget"],
        }
        result = apply_plan_mode_overrides(original)

        assert original["section_priorities"] == snapshot["section_priorities"]
        assert original["model_hint"] == snapshot["model_hint"]
        assert original["compression_intensity"] == snapshot["compression_intensity"]
        assert original["token_budget"] == snapshot["token_budget"]

        assert result["model_hint"] == "quality"
        assert result["compression_intensity"] == "minimal"
        assert result["section_priorities"]["hierarchy_table"] == "critical"
        assert result["section_priorities"]["agent_mode_protocol"] == "supplementary"
        assert result["token_budget"] == 4000

    def test_plan_mode_invalid_env_value_treated_as_false(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Unrecognised env values like 'garbage' must NOT enable plan-mode."""
        monkeypatch.setenv("DEVOLAFLOW_PLAN_MODE", "garbage")
        monkeypatch.chdir(tmp_path)
        result = select_context("refactor", profiles_path=PROFILES_YAML)
        assert result["plan_mode"] is False
        assert result["plan_mode_applied"] is False

    def test_plan_mode_compression_intensity_minimal(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Plan-mode forces compression_intensity to 'minimal' regardless of config default."""
        monkeypatch.delenv("DEVOLAFLOW_PLAN_MODE", raising=False)
        monkeypatch.chdir(tmp_path)
        result = select_context("refactor", profiles_path=PROFILES_YAML, plan_mode=True)
        assert result["compression_intensity"] == "minimal"


class TestAdvisorPRDAdditiveBlocks:
    """v7.2.0 PR-D — C-001 (conciseness) + C-003 (timing + reconcile).

    Verifies the three additive blocks emitted by ``_resolve_advisor_text`` are
    present by default, individually opt-out-able via per-profile flags, and that
    the +200 token_budget bump on the 4 advisor profiles preserves headroom under
    both the tiktoken and chars//4 token estimators.
    """

    CONCISENESS_MARKER = "Reply in under 100 words and use enumerated steps"
    TIMING_MARKER = "Timing: Call advisor BEFORE substantive work"
    RECONCILE_MARKER = "On conflict: If you've already retrieved data"

    def test_advisor_text_contains_conciseness_default(self) -> None:
        result = select_context("feature", profiles_path=PROFILES_YAML)
        assert result["advisor_enabled"] is True
        assert self.CONCISENESS_MARKER in result["assembled_text"]

    def test_advisor_text_contains_timing_default(self) -> None:
        result = select_context("feature", profiles_path=PROFILES_YAML)
        assert result["advisor_enabled"] is True
        assert self.TIMING_MARKER in result["assembled_text"]

    def test_advisor_text_contains_reconcile_default(self) -> None:
        result = select_context("feature", profiles_path=PROFILES_YAML)
        assert result["advisor_enabled"] is True
        assert self.RECONCILE_MARKER in result["assembled_text"]

    @pytest.mark.parametrize(
        ("flag", "marker"),
        [
            ("conciseness_instruction", CONCISENESS_MARKER),
            ("timing_block", TIMING_MARKER),
            ("reconcile_block", RECONCILE_MARKER),
        ],
    )
    def test_advisor_text_optout_per_flag(self, flag: str, marker: str) -> None:
        """Setting any of the 3 additive flags to False must suppress only its block."""
        base_advisor = {
            "enabled": True,
            "max_uses": 3,
            "cost_ceiling_usd": 0.30,
            "trigger_conditions": ["complexity_high"],
            "conciseness_instruction": True,
            "timing_block": True,
            "reconcile_block": True,
        }
        enabled, baseline_text, baseline_tokens = _resolve_advisor_text({"advisor": base_advisor})
        assert enabled is True
        assert marker in baseline_text

        opt_out = {**base_advisor, flag: False}
        enabled_opt, opt_text, opt_tokens = _resolve_advisor_text({"advisor": opt_out})
        assert enabled_opt is True
        assert marker not in opt_text, (
            f"Flag {flag}=False must suppress its block (marker still present)."
        )
        assert opt_tokens < baseline_tokens, (
            f"Suppressing {flag} must not grow the section token count."
        )
        always_present = {
            "## Advisor Tool",
            "Advisor enabled (max 3 uses",
            "Invoke for: complexity_high",
        }
        for snippet in always_present:
            assert snippet in opt_text, (
                f"Opt-out of {flag} must not remove core advisor scaffolding "
                f"(missing: {snippet!r})."
            )
        other_markers = {
            "conciseness_instruction": self.CONCISENESS_MARKER,
            "timing_block": self.TIMING_MARKER,
            "reconcile_block": self.RECONCILE_MARKER,
        }
        for other_flag, other_marker in other_markers.items():
            if other_flag == flag:
                continue
            assert other_marker in opt_text, (
                f"Opt-out of {flag} must NOT suppress {other_flag} block."
            )

    @pytest.mark.parametrize(
        ("profile_name", "goal_hint"),
        [
            ("feature", "implement feature"),
            ("refactor", "refactor"),
            ("migration", "migrate"),
            ("security-audit", "security"),
        ],
    )
    def test_advisor_section_token_growth_within_budget(
        self, profile_name: str, goal_hint: str
    ) -> None:
        """The 4 advisor profiles must absorb the C-001+C-003 advisor section
        growth without exceeding their (post-bump) token_budget under whichever
        estimator is active in the running environment."""
        result = select_context(goal_hint, profiles_path=PROFILES_YAML)
        assert result["profile_name"] == profile_name, (
            f"goal_hint {goal_hint!r} must map to profile {profile_name!r}; "
            f"got {result['profile_name']!r}."
        )
        assert result["advisor_enabled"] is True
        assert result["total_tokens"] <= result["budget"], (
            f"Profile {profile_name}: total_tokens={result['total_tokens']} "
            f"exceeds post-bump budget={result['budget']}."
        )
        assembled = result["assembled_text"]
        assert self.CONCISENESS_MARKER in assembled
        assert self.TIMING_MARKER in assembled
        assert self.RECONCILE_MARKER in assembled


class TestComplexityTierRouting:
    """v7.2.1 P-04 — complexity-tier-aware model routing.

    Verifies the new ``complexity_tier`` kwarg on
    :func:`resolve_model_hint` and :func:`select_context`. Lookup priority:
    ``complexity_routing[complexity_tier]`` > ``model_hints.overrides[task_type]``
    > ``model_hints.default_tier`` > ``"inherit"``. The complexity-tier table
    lives under top-level ``meta.complexity_routing`` in
    ``context_profiles.yaml``; :func:`select_context` injects it into the
    per-profile dict via copy-on-write.

    Default ``complexity_tier=None`` MUST preserve bytewise behaviour on
    every existing selector test (verified by the rest of this test module
    plus the explicit baseline-equality assertion below).

    Locks in the built-in harness evaluation guidance for model interaction:
    route Complex+ work to the quality tier and Simple/Medium work to the
    budget/balanced tiers.
    """

    PROFILE_WITH_ROUTING = {
        "model_hints": {
            "default_tier": "balanced",
            "overrides": {
                "code_review": "quality",
                "simple_implementation": "budget",
            },
        },
        "complexity_routing": {
            "simple": "budget",
            "medium": "balanced",
            "complex": "quality",
            "very_complex": "quality",
        },
    }

    @pytest.mark.parametrize(
        ("tier", "expected_hint"),
        [
            ("simple", "budget"),
            ("medium", "balanced"),
            ("complex", "quality"),
            ("very_complex", "quality"),
        ],
    )
    def test_complexity_tier_overrides_per_task_overrides(
        self, tier: str, expected_hint: str
    ) -> None:
        """complexity_tier MUST take priority over model_hints.overrides.

        ``code_review`` is in ``overrides`` mapped to ``quality``; passing
        ``complexity_tier="simple"`` MUST return ``budget`` instead because
        the new branch is checked first.
        """
        result = resolve_model_hint("code_review", self.PROFILE_WITH_ROUTING, tier)
        assert result == expected_hint, (
            f"complexity_tier={tier!r} expected {expected_hint!r}; "
            f"got {result!r} (lookup priority broken — overrides won)."
        )

    @pytest.mark.parametrize(
        ("tier", "expected_hint"),
        [
            ("simple", "budget"),
            ("medium", "balanced"),
            ("complex", "quality"),
            ("very_complex", "quality"),
        ],
    )
    def test_complexity_tier_overrides_default_tier(self, tier: str, expected_hint: str) -> None:
        """complexity_tier MUST take priority over model_hints.default_tier.

        ``unknown_task`` is NOT in overrides, so without complexity_tier
        the hint would resolve to ``balanced`` (the default_tier). With
        complexity_tier set, the new branch must win.
        """
        result = resolve_model_hint("unknown_task", self.PROFILE_WITH_ROUTING, tier)
        assert result == expected_hint

    def test_complexity_tier_none_matches_baseline_overrides(self) -> None:
        """complexity_tier=None MUST match v7.1.0 lookup priority bytewise.

        For ``code_review`` in overrides mapped to ``quality``:
        - 2-arg call (legacy): returns ``quality``.
        - 3-arg call with None: must return identical ``quality``.
        - 3-arg call with valid tier: returns the tier hint, NOT ``quality``.
        """
        legacy = resolve_model_hint("code_review", self.PROFILE_WITH_ROUTING)
        explicit_none = resolve_model_hint("code_review", self.PROFILE_WITH_ROUTING, None)
        assert legacy == explicit_none == "quality"

        tier_branch = resolve_model_hint("code_review", self.PROFILE_WITH_ROUTING, "simple")
        assert tier_branch == "budget"
        assert tier_branch != legacy, (
            "complexity_tier branch and overrides branch must produce different "
            "hints for this fixture; otherwise the test is not exercising the new code."
        )

    def test_complexity_tier_none_matches_baseline_default_tier(self) -> None:
        """complexity_tier=None MUST fall through to default_tier as in v7.1.0."""
        legacy = resolve_model_hint("unknown_task", self.PROFILE_WITH_ROUTING)
        explicit_none = resolve_model_hint("unknown_task", self.PROFILE_WITH_ROUTING, None)
        assert legacy == explicit_none == "balanced"

    def test_complexity_tier_unknown_falls_through_to_overrides(self) -> None:
        """An unknown complexity_tier must fall through to overrides/default."""
        result = resolve_model_hint("code_review", self.PROFILE_WITH_ROUTING, "epic")
        assert result == "quality", (
            "Unknown complexity_tier must fall through to model_hints.overrides[task_type]."
        )

    def test_complexity_tier_invalid_hint_falls_through(self) -> None:
        """A complexity_routing entry with an invalid hint must fall through."""
        bad_profile = {
            "model_hints": {
                "default_tier": "balanced",
                "overrides": {"code_review": "quality"},
            },
            "complexity_routing": {"simple": "not_a_valid_tier"},
        }
        result = resolve_model_hint("code_review", bad_profile, "simple")
        assert result == "quality", (
            "Invalid complexity_routing hint must NOT be returned; "
            "resolution must fall through to model_hints.overrides."
        )

    def test_complexity_tier_no_routing_table_falls_through(self) -> None:
        """A profile without complexity_routing must behave exactly like v7.1.0."""
        no_routing = {
            "model_hints": {
                "default_tier": "balanced",
                "overrides": {"code_review": "quality"},
            }
        }
        with_tier = resolve_model_hint("code_review", no_routing, "complex")
        without_tier = resolve_model_hint("code_review", no_routing)
        assert with_tier == without_tier == "quality"

    def test_complexity_tier_lookup_does_not_mutate_profile(self) -> None:
        """The resolve_model_hint complexity_tier branch MUST be read-only.

        Verified via deepcopy comparison: the input profile_config dict
        (including its nested model_hints + complexity_routing dicts) must
        be byte-identical after every resolve_model_hint call across all
        4 tiers + None.
        """
        from copy import deepcopy

        profile = deepcopy(self.PROFILE_WITH_ROUTING)
        snapshot = deepcopy(profile)

        for tier in (None, "simple", "medium", "complex", "very_complex", "unknown_xyz"):
            resolve_model_hint("code_review", profile, tier)
            resolve_model_hint("unknown_task", profile, tier)
            assert profile == snapshot, (
                f"resolve_model_hint mutated profile_config (tier={tier!r}). "
                f"The lookup must be read-only."
            )

    def test_select_context_default_complexity_tier_preserves_baseline(self) -> None:
        """select_context() called WITHOUT complexity_tier must match the v7.1.0 result.

        The 4 advisor profiles + plan-mode/round-escalation paths are covered
        by their dedicated test classes; this test is the entry-point check
        that the new complexity_tier kwarg defaults to None and produces
        bytewise-identical model_hint vs. the legacy 6-arg signature.
        """
        legacy = select_context("feature", profiles_path=PROFILES_YAML)
        explicit_none = select_context("feature", profiles_path=PROFILES_YAML, complexity_tier=None)
        assert legacy["model_hint"] == explicit_none["model_hint"]
        assert [s["name"] for s in legacy["selected_sections"]] == [
            s["name"] for s in explicit_none["selected_sections"]
        ]
        assert legacy["budget"] == explicit_none["budget"]
        assert legacy["total_tokens"] == explicit_none["total_tokens"]

    @pytest.mark.parametrize(
        ("tier", "expected_hint"),
        [
            ("simple", "budget"),
            ("medium", "balanced"),
            ("complex", "quality"),
            ("very_complex", "quality"),
        ],
    )
    def test_select_context_forwards_complexity_tier(self, tier: str, expected_hint: str) -> None:
        """select_context must forward complexity_tier to resolve_model_hint.

        The ``feature`` profile's ``architecture_decisions`` override maps to
        ``quality``; with ``complexity_tier="simple"`` the resolved hint must
        flip to ``budget`` because the complexity branch wins. For tasks not
        in the overrides map (e.g. plain ``feature``), the complexity branch
        also wins over ``default_tier``.
        """
        result = select_context(
            "architecture_decisions",
            profiles_path=PROFILES_YAML,
            complexity_tier=tier,
        )
        assert result["model_hint"] == expected_hint, (
            f"select_context did not forward complexity_tier={tier!r} correctly; "
            f"expected {expected_hint!r}, got {result['model_hint']!r}."
        )

    def test_select_context_complexity_tier_unknown_falls_through(self) -> None:
        """An unknown complexity_tier in select_context must fall through to overrides."""
        result = select_context(
            "architecture_decisions",
            profiles_path=PROFILES_YAML,
            complexity_tier="epic",
        )
        assert result["model_hint"] == "quality", (
            "Unknown complexity_tier must fall through to feature profile's "
            "architecture_decisions override (quality)."
        )

    def test_meta_complexity_routing_yaml_block_is_valid(self) -> None:
        """The yaml meta.complexity_routing block must define all 4 tiers in VALID_MODEL_HINTS."""
        config = load_profiles(PROFILES_YAML)
        complexity_routing = config["meta"].get("complexity_routing")
        assert complexity_routing is not None, (
            "meta.complexity_routing block missing from context_profiles.yaml"
        )
        expected_tiers = {"simple", "medium", "complex", "very_complex"}
        assert set(complexity_routing.keys()) == expected_tiers, (
            f"meta.complexity_routing keys must be exactly {expected_tiers}; "
            f"got {set(complexity_routing.keys())}"
        )
        for tier, hint in complexity_routing.items():
            assert hint in VALID_MODEL_HINTS, (
                f"meta.complexity_routing[{tier!r}]={hint!r} not in VALID_MODEL_HINTS"
            )

        assert complexity_routing["simple"] == "budget"
        assert complexity_routing["medium"] == "balanced"
        assert complexity_routing["complex"] == "quality"
        assert complexity_routing["very_complex"] == "quality"


# ---------------------------------------------------------------------------
# v14.4.0 (G-026) — overlay-refactor exact-hash harness.
#
# context_profiles.yaml was restructured from 24 fully-expanded profiles
# into ``defaults:`` (one canonical section_priorities map + shared
# knob anchors) + per-profile DELTA overlays composed via YAML merge keys
# (``<<:``), and the 4 orphan top-level keys (complex_feature /
# abstractive_llm / legibility_audit / session_state) were relocated under
# their canonical parents (summary_modes: / meta:) with back-compat
# top-level aliases. The refactor contract is ZERO behavioral delta: for
# every profile the PARSED config — and therefore every ``select_context``
# resolution — must be identical (keys, ORDER, values) to the
# pre-refactor expansion.
#
# The snapshot hashes below are VENDORED verbatim from the pre-refactor
# file (git parent of the v14.4.0-T3 change; captured mechanically by the
# C-3 verbatim-extraction harness).
#
# v14.5.0 (G-019 / T6) re-pin: the 19 canonical-order profiles' hashes
# were recomputed mechanically (same canonicalisation) after the
# `template_quick_ref: skip` row was removed from the shared defaults
# map alongside the SKILL.md §"Template Quick-Reference" demotion to
# references/meta-framework.md §4. The DELIBERATE delta is exactly
# `template_quick_ref` disappearing from each resolved map (it was
# `skip` in all 24 profiles — zero behavioural change to selection);
# the explicit-map profiles keep their original pre-refactor hashes except
# repo-init, whose five retired section IDs were migrated to current SKILL
# anchors by M4-W4-A1 without changing their priorities.
# v16.0.0 intentional re-pin: all 19 default-overlay profiles were
# mechanically re-hashed after the retired external-advisor section was
# removed from their resolved maps. The skill-optimization profile also
# replaced its obsolete evaluator hint and prose with built-in harness
# evaluation. The 5 explicit-map profiles retain their prior hashes. No
# additional fields are excluded and the exact key/order/value assertions
# remain unchanged in strength.
# Canonicalisation:
#   * section-priority hash  = sha256(json.dumps([[k, v], ...],
#     ensure_ascii=False)) over the profile's ordered
#     section_priorities items — pins keys AND insertion order AND
#     values (order feeds `_build_priority_buckets` bucket ordering).
#   * profile hash = sha256(json.dumps({k: v for k, v in profile if
#     k not in {"ac_generation", "timeout_class"}}, sort_keys=True,
#     ensure_ascii=False)) — pins every other profile knob. The two
#     exclusions are the existing documented G-006/G-037 deltas.
#   * orphan hash = sha256(json.dumps(block, sort_keys=True,
#     ensure_ascii=False)) over each relocated top-level block.
# ---------------------------------------------------------------------------

_PRE_G026_SECTION_PRIORITY_HASHES: dict[str, str] = {
    "hotfix": "5d334f1dd6c268c8ced9555064082a6a19b355b6053d9841bfed27d95d06bf26",
    "feature": "bc7d429f177ee3807728cedb1b204a16f88a6a1b0515f2e698fa9966424335c6",
    "research": "7c0b3d0b924dd04066a255e212cbbbb8e0d4c2ecd046fdf72cc486355eb8ac88",
    "refactor": "b25a0c22241c5cf4f314886d425697a41c9376829e5096a507a755cfda88c999",
    "review": "0ee38a92308fc4fa0ee9a48ccda5349bfa63e2a06b08883b2127d465d15aa3a3",
    "design": "6c845943836baf46fed2577acbe77c3decb077cf8870b1546dc96865eba9fec7",
    "skill-optimization": "ed84abd68cf573a854c856daec4eda18d5b97fe5d8c694654b61204564634dae",
    "migration": "3cdb6215db21fed11486c8ad9a2e8954b6ab760b76ae834a23d4e8c29a075635",
    "security-audit": "a7a78a86f0f5e72a4f0a43892e5dc554ab3a272c9c617424338f59e50c50cf7c",
    "documentation": "f6eec9575d23932ad677add8a479b35b0ed37b86941002c5a44d1f7bfc35ea54",
    "spike-poc": "e9525fef863eba3ca9564d2db2fef46551ac38ddb3b8128b94b9924cb38f1a3f",
    "rdrr": "143d67c95e7f8bcbc2bb580de32110f19acf5de42c83d4a47cca92b3c1e18b7f",
    "demo-showcase": "035dc881398af4225013d4fa0f091d6ca5d0d673af2cbd8f046a0e030384c4f5",
    "perf-optimization": "5f49f3db14b2e37cdb4839a22807b01a3dfe2195697dd781f39f672065fdf396",
    "dependency-setup": "c6c6236637000d626c6a1618c959092d7df31a11b298c5abdffc03a50c662724",
    "onboarding": "8c6f3da35f2de0118066d52e889c872c56bda092478b69b9d86d87b8d01547c1",
    "self_update": "d03a43115877ea8fe347b441dd2a6728f1cc1602892627ac4679896b6fd320ed",
    "feedback": "ce6873ffd92b102cffb651ded97f4279bf29db2f00e2e2315aa8e8ecd9a8a700",
    "verify_visual": "8f8a54b6773b9712138f680810a583c67b5d904fe9feaf9a5cf3cc654d4ccc2d",
    "verify_acceptance": "8f8a54b6773b9712138f680810a583c67b5d904fe9feaf9a5cf3cc654d4ccc2d",
    "verify_interaction": "8f8a54b6773b9712138f680810a583c67b5d904fe9feaf9a5cf3cc654d4ccc2d",
    "repo-init": "2858037d83647ce0e067cf92f57ed6e712b2086bec2861401c46fe10d07c4b3d",
    "product_verification": "00af0cba5de0131906444e4420b1fd89a0fa3d6c42c5ba4ea22bf74db4962ec8",
    "entropy_scan": "d3c3c1ba7a0eda531da681ed34d9a85df124c32f079c435b369302426f750391",
    "pathfind": "5c1f6b6198d2d93f59ed31e9680f71af8f2fe8aecac0c2d79ddc7c14e351c287",
}

_PRE_G026_PROFILE_HASHES: dict[str, str] = {
    "hotfix": "f5a93d34208bdc61dd3f1a474ed94cda36f4f802cd30a1c8bc413614e0e63511",
    "feature": "051b581c5f571270baf1b83ae069dd36645c0c68b7f6ec515cbd98af83a35b7d",
    "research": "2aad51d0d14f4db9cbc6787402d651efed2fc1ba53e2a7b6fed4de9f629507ba",
    "refactor": "30d218a4e8054cd2872b249681180b8983dd95c811b473ad1ced318d6356c2b6",
    "review": "580efcc076b26095658ff8682aecb24055b97898d78124a632c071c462a2c860",
    "design": "fb579d80d2297eb06cc12e90f95ee723b67bd0d63425b3ea889560154cc40786",
    "skill-optimization": "f75c916a5675c8f80366644d3894e6e3bec491e3d9762b787b63acde6d217940",
    "migration": "afb3408095d64fc33b3cf6740793c6a0733cae108a3224fd922304d5a020e155",
    "security-audit": "9478934af4994c5fd5d694770da0b57a9d1db56d788df6fc66de609ec5556dfc",
    "documentation": "3d950d1607620797ff55b03f6908f8ad6ed0c0be613c889a8054d22345684eb8",
    "spike-poc": "195590f18508868726a752742aa3f873b1a313a7a63e6421d712b2a57e90e46b",
    "rdrr": "a043dfec3cf163e5145fdb8b4ba0ee3e1beb846d50c3f457f2e61b0aa105f8f3",
    "demo-showcase": "384cf0652bab748f51fc15235cd4c89c5b10c8e78094db9743507bb3a67f006d",
    "perf-optimization": "e5c66e2e0af195f3ca9154bac20c46e64a59a2c0d9c8b63b0437f4449e8690a2",
    "dependency-setup": "b1bc884cfff3e5775ba2c459096797d2ec2504427a6c347853564774cef88969",
    "onboarding": "3f9b06561da6a78b175fff480b9a4108928c5e3f1f7a8486a349eead27e80ba3",
    "self_update": "852b56113f2b2fe0a2c916f5aa29290433cd0a0e86f0d8f7d304bb0547ada8be",
    "feedback": "19d016d086f04c2d3c89610ce22c7fd1a0f84a94ed7166fb4a33b05fcf2a68ba",
    "verify_visual": "48c63ae115031c1d9f587c48e75288700c070cb68f5f5d58b51b715b38c0e09d",
    "verify_acceptance": "d6ff6666f67dab86b3f70bae867d05ba100400fdb6c6c7bd33563a1dd43fa70b",
    "verify_interaction": "afb7d6b50d887ca392af0ab01e3800e857c149a672d525672a1403ecb40667ac",
    "repo-init": "82dfa7335f3175dc69079ab6286eb6391e02cb19c675ad7c0e0088a72867aa46",
    "product_verification": "d929fe08d2a66615205281514aa9df15bb1c1c7aff1adf2cd5371b29a7ac92dd",
    "entropy_scan": "1d68da96923c67dbe7004447b946aa3c42c72194076439729e71fd68473ca101",
    "pathfind": "ca81880c08c3e223d3799d3053ec60ff2aa6831343d7de9d7ef7291de61832a3",
}

_PRE_G026_ORPHAN_HASHES: dict[str, str] = {
    "complex_feature": "f9adc44d5befb9ddec266d9af2779cb3df4a30c176eecb0af65abb55c22239f2",
    "abstractive_llm": "7b6c6eee210ed7049cede7591707ecbbc9c43b656cf9ddb91f4f6de93b59c093",
    "legibility_audit": "6a51a42340bd3235902736c5fe474b473fa3b4837d049b90f5550b22bda87c53",
    "session_state": "f91173667bd5b55c392c1def4cbcbe0bceef290f00db5b869f3049270aeb3a4e",
}

# Canonical parent for each relocated orphan key (G-026).
_G026_ORPHAN_CANONICAL_PARENTS: dict[str, tuple[str, ...]] = {
    "complex_feature": ("summary_modes", "complex_feature"),
    "abstractive_llm": ("summary_modes", "abstractive_llm"),
    "legibility_audit": ("meta", "legibility_audit"),
    "session_state": ("meta", "session_state"),
}


def _sha256_json(payload: object, *, sort_keys: bool = False) -> str:
    import hashlib
    import json

    return hashlib.sha256(
        json.dumps(payload, sort_keys=sort_keys, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


class TestG026OverlayEquivalence:
    """W-6 exact-hash guard for the resolved G-026 overlay contract."""

    @pytest.fixture(scope="class")
    def config(self) -> dict:
        return load_profiles(PROFILES_YAML)

    def test_g026_section_priorities_match_pre_refactor_snapshot(self, config: dict) -> None:
        """Every profile's RESOLVED section_priorities map (keys + insertion
        order + values, post merge-key expansion) must hash-match the
        mechanically pinned exact snapshot. Order matters behaviorally: the
        ``_build_priority_buckets`` buckets preserve insertion order, which
        decides which same-tier section wins the budget race."""
        profiles = config["profiles"]
        assert set(profiles) == set(_PRE_G026_SECTION_PRIORITY_HASHES), (
            "G-026 exact contract: profile SET changed unexpectedly"
        )
        mismatches = []
        for name, expected in _PRE_G026_SECTION_PRIORITY_HASHES.items():
            pairs = [[k, v] for k, v in profiles[name]["section_priorities"].items()]
            if _sha256_json(pairs) != expected:
                mismatches.append(f"{name}: resolved map drifted -> {pairs}")
        assert not mismatches, (
            "G-026 exact-hash violation — resolved section_priorities drifted for:\n  "
            + "\n  ".join(mismatches)
        )

    def test_g026_profiles_equivalent_modulo_ac_generation(self, config: dict) -> None:
        """Every OTHER profile knob (budgets, model_hints, learnings,
        advisor, decomposition, tool_output_truncation, summary,
        behavioral_guidelines, goal_hints, extra_context, rationale, ...)
        must be value-identical to the mechanically pinned exact snapshot.

        Two keys are DELIBERATE deltas excluded from the hash:
          * ``ac_generation`` — v14.4.0 G-006 impl-class extension.
          * ``timeout_class`` — v14.5.0 G-037 timeout-class deltas (8
            profiles whose class differs from the ``impl`` default).
            Their resolution is pinned separately by
            ``TestG037TimeoutClassResolution``; every other knob in
            those profiles must STILL hash-match the pre-G-026 snapshot.
        """
        deliberate_deltas = {"ac_generation", "timeout_class"}
        profiles = config["profiles"]
        mismatches = []
        for name, expected in _PRE_G026_PROFILE_HASHES.items():
            rest = {k: v for k, v in profiles[name].items() if k not in deliberate_deltas}
            if _sha256_json(rest, sort_keys=True) != expected:
                mismatches.append(name)
        assert not mismatches, (
            "G-026 exact-hash violation — profile knobs outside the documented "
            f"ac_generation / timeout_class deltas drifted for: {mismatches}"
        )

    def test_g026_orphan_keys_relocated_with_identical_content(self, config: dict) -> None:
        """The 4 former orphan top-level keys must (a) keep their TOP-LEVEL
        back-compat aliases byte-equivalent to the pre-refactor blocks for
        raw yaml.safe_load consumers, and (b) resolve to the SAME content
        at their canonical relocated parents (summary_modes: / meta:)."""
        for orphan, expected in _PRE_G026_ORPHAN_HASHES.items():
            assert orphan in config, (
                f"G-026 back-compat violation: top-level alias {orphan!r} missing"
            )
            assert _sha256_json(config[orphan], sort_keys=True) == expected, (
                f"G-026 violation: top-level {orphan!r} content drifted from the pre-refactor block"
            )
            parent_key, child_key = _G026_ORPHAN_CANONICAL_PARENTS[orphan]
            canonical = config.get(parent_key, {}).get(child_key)
            assert canonical == config[orphan], (
                f"G-026 violation: canonical {parent_key}.{child_key} does not "
                f"match the top-level {orphan!r} back-compat alias"
            )


# ---------------------------------------------------------------------------
# v14.5.0 (G-037) — timeout-class SSOT map + select_context auto-population.
#
# ``defaults.timeout_class_map`` in context_profiles.yaml is the SSOT for
# the per-task-type ``timeout_seconds`` defaults (SKILL.md §"Subagent Hang
# Prevention": research=2700 / impl=1800 / test=900 / review=1200 /
# hotfix=600; fallback 7200 = fail-safe ceiling). 8 profiles carry a
# ``timeout_class`` delta (≠ impl default); the other 16 inherit ``impl``
# implicitly per the G-026 delta-only overlay discipline.
# ---------------------------------------------------------------------------

# Expected profile → timeout_seconds resolution (delta profiles + two
# impl-default representatives). Mirrors the YAML delta comments verbatim.
_G037_PROFILE_TIMEOUTS: dict[str, int] = {
    "hotfix": 600,
    "research": 2700,
    "review": 1200,
    "feedback": 1200,
    "verify_visual": 900,
    "verify_acceptance": 900,
    "verify_interaction": 900,
    "product_verification": 900,
    "pathfind": 2700,
    "feature": 1800,
    "refactor": 1800,
}


class TestG037TimeoutClassResolution:
    """v14.5.0 G-037 — timeout-class map resolution + absence safety."""

    @pytest.fixture(scope="class")
    def config(self) -> dict:
        return load_profiles(PROFILES_YAML)

    def test_timeout_class_map_matches_skill_md_contract(self, config: dict) -> None:
        """The SSOT map must carry the SKILL.md §"Subagent Hang Prevention"
        values verbatim AND stay lock-step with the v12.2.0 library mirror
        (TASK_TYPE_TIMEOUT_DEFAULTS + TASK_TYPE_TIMEOUT_FALLBACK)."""
        timeout_map = config["defaults"]["timeout_class_map"]
        assert timeout_map == {
            "research": 2700,
            "impl": 1800,
            "test": 900,
            "review": 1200,
            "hotfix": 600,
            "fallback": 7200,
        }
        for cls, seconds in TASK_TYPE_TIMEOUT_DEFAULTS.items():
            assert timeout_map[cls] == seconds, (
                f"timeout_class_map[{cls!r}] drifted from TASK_TYPE_TIMEOUT_DEFAULTS"
            )
        assert timeout_map["fallback"] == TASK_TYPE_TIMEOUT_FALLBACK

    def test_resolve_timeout_seconds_per_class_and_fallback(self, config: dict) -> None:
        """Direct resolver checks: every class resolves via the YAML map;
        unknown classes hit the map's fallback ceiling; configs without
        the map fall back to the library constants (absence-safe)."""
        for cls in ("research", "impl", "test", "review", "hotfix"):
            assert (
                resolve_timeout_seconds({"timeout_class": cls}, config)
                == (TASK_TYPE_TIMEOUT_DEFAULTS[cls])
            )
        # Absent timeout_class → impl default.
        assert resolve_timeout_seconds({}, config) == 1800
        # Unknown / malformed class → fail-safe ceiling, never raises.
        assert resolve_timeout_seconds({"timeout_class": "no-such-class"}, config) == 7200
        assert resolve_timeout_seconds({"timeout_class": 42}, config) == 1800
        # No defaults block at all → library-constant mirror.
        assert resolve_timeout_seconds({"timeout_class": "test"}, {}) == 900
        assert resolve_timeout_seconds({}, {}) == 1800
        assert resolve_timeout_seconds({"timeout_class": "no-such-class"}, {}) == 7200

    @pytest.mark.parametrize(
        ("task_type", "expected_seconds"),
        sorted(_G037_PROFILE_TIMEOUTS.items()),
    )
    def test_profile_timeout_class_deltas_resolve_in_select_context(
        self, task_type: str, expected_seconds: int
    ) -> None:
        """The 8 delta profiles resolve their class; impl-class profiles
        (no ``timeout_class`` key — delta-only discipline) resolve 1800."""
        result = select_context(task_type, profiles_path=PROFILES_YAML)
        assert result["timeout_seconds"] == expected_seconds, (
            f"{task_type}: expected timeout_seconds={expected_seconds}, "
            f"got {result['timeout_seconds']}"
        )

    def test_timeout_seconds_absence_safe_without_defaults_block(self, tmp_path: Path) -> None:
        """A minimal config that predates the timeout knobs (no ``defaults:``
        block, no ``timeout_class``) must still resolve — impl default via
        the library mirror — with zero behavior change elsewhere."""
        data = {
            "meta": {"default_profile": "legacy"},
            "sections": {"sec1": {"lines": "1-5", "tokens_est": 50}},
            "profiles": {
                "legacy": {
                    "description": "pre-G-037 config",
                    "token_budget": 1000,
                    "section_priorities": {"sec1": "critical"},
                    "goal_hints": [],
                }
            },
        }
        p = tmp_path / "profiles.yaml"
        p.write_text(yaml.dump(data))
        skill = tmp_path / "SKILL.md"
        skill.write_text("\n".join(f"line{i}" for i in range(1, 20)))

        from unittest.mock import patch

        with patch(
            "devolaflow.task_adaptive_selector.load_skill_md",
            return_value=skill.read_text(),
        ):
            result = select_context("legacy", profiles_path=p)
        assert result["timeout_seconds"] == 1800
        assert result["profile_name"] == "legacy"

    def test_round_escalation_leaves_timeout_untouched(self) -> None:
        """Item-3 coherence pin: round-aware escalation (round-2 priority
        bumps, round-3 model/budget bumps) must NOT alter the resolved
        timeout — no W-8 / P4 rule grows timeouts across rounds, and the
        escalation override schema carries no timeout keys."""
        from devolaflow.task_adaptive_selector import _ROUND_ESCALATION_DEFAULTS

        for overrides in _ROUND_ESCALATION_DEFAULTS.values():
            assert not any("timeout" in key for key in overrides), (
                "round-escalation overrides must not carry timeout keys; "
                "a rule change (W-8/P4) is required first"
            )
        round1 = select_context("feature", profiles_path=PROFILES_YAML, round_num=1)
        round3 = select_context("feature", profiles_path=PROFILES_YAML, round_num=3)
        assert round1["timeout_seconds"] == round3["timeout_seconds"] == 1800

    def test_w6_timeout_knobs_do_not_displace_critical_sections(self, config: dict) -> None:
        """W-6 spot-check: the timeout knobs are zero-token metadata, so no
        section marked ``critical`` may be dropped for any profile that
        gained a ``timeout_class`` delta (plus two impl representatives)."""
        for task_type in sorted(_G037_PROFILE_TIMEOUTS):
            result = select_context(task_type, profiles_path=PROFILES_YAML)
            profile = config["profiles"][result["profile_name"]]
            critical = {
                name
                for name, prio in profile.get("section_priorities", {}).items()
                if prio == "critical"
            }
            skipped = set(result["skipped_sections"])
            dropped = critical & skipped
            assert not dropped, (
                f"W-6 violation for {task_type}: critical sections dropped: {sorted(dropped)}"
            )


# ---------------------------------------------------------------------------
# v17.0.0 R3 (G17-B3 / D-R3-1) — additive ``agents_md_slice`` return key
# ---------------------------------------------------------------------------


class TestAgentsMdSliceAccount:
    """select_context attaches the compact AGENTS.md-slice account (D-R3-1).

    The key is purely ADDITIVE — the pre-existing return-key pins
    (``TestSelectContext::test_result_structure`` and the assembled-text /
    total-tokens assertions across this suite) verify the legacy contract
    is untouched; these tests pin the new account's own shape.
    """

    _COMPACT_KEYS = frozenset(
        {
            "profile_name",
            "slice_enabled",
            "total_tokens",
            "full_tokens",
            "slice_savings_pct",
            "included_rules_count",
        }
    )

    @pytest.mark.parametrize("task_type", ["hotfix", "research"])
    def test_sliceable_task_types_carry_positive_savings(self, task_type: str) -> None:
        result = select_context(task_type, profiles_path=PROFILES_YAML)
        account = result["agents_md_slice"]
        assert set(account) == self._COMPACT_KEYS
        assert account["profile_name"] == task_type
        assert account["slice_enabled"] is True
        assert account["slice_savings_pct"] > 0
        assert 0 < account["total_tokens"] < account["full_tokens"]
        assert account["included_rules_count"] > 0

    def test_env_opt_out_normalizes_included_rules_all_to_minus_one(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """R5 strict env opt-out: the literal ``"all"`` fast path is
        normalized to the ``-1`` sentinel in ``included_rules_count``."""
        monkeypatch.setenv("DEVOLAFLOW_AGENTS_MD_SLICE", "0")
        result = select_context("hotfix", profiles_path=PROFILES_YAML)
        account = result["agents_md_slice"]
        assert account["slice_enabled"] is False
        assert account["slice_savings_pct"] == 0.0
        assert account["included_rules_count"] == -1
        assert account["total_tokens"] == account["full_tokens"] > 0

    def test_unreadable_agents_md_yields_empty_account_and_warns(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """S-5: a missing AGENTS.md degrades the account to ``{}`` with a
        WARNING — selection itself never crashes and the legacy keys stay
        fully populated."""
        import devolaflow.agents_md_slice as agents_md_slice

        monkeypatch.setattr(agents_md_slice, "_AGENTS_MD_PATH", tmp_path / "missing" / "AGENTS.md")
        with caplog.at_level("WARNING", logger="devolaflow.agents_md_slice"):
            result = select_context("hotfix", profiles_path=PROFILES_YAML)
        assert result["agents_md_slice"] == {}
        assert "AGENTS.md" in caplog.text
        assert result["profile_name"] == "hotfix"
        assert result["total_tokens"] > 0
        assert result["assembled_text"]
