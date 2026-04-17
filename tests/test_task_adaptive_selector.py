"""Tests for the task-adaptive context selector.

Covers: load_profiles, load_skill_md, extract_section, estimate_tokens,
match_profile, select_context, and the CLI main() entry point.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

from devolaflow.task_adaptive_selector import (
    PRIORITY_ORDER,
    VALID_COMPRESSION_INTENSITIES,
    VALID_MODEL_HINTS,
    apply_plan_mode_overrides,
    estimate_tokens,
    extract_section,
    load_profiles,
    load_skill_md,
    main,
    match_profile,
    resolve_compression_intensity,
    resolve_decomposition_config,
    resolve_model_hint,
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
            "round_num",
            "escalation_applied",
            "plan_mode",
            "plan_mode_applied",
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
        assert result["budget"] == 2375
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
        config = {"meta": {"compression_defaults": {"l2_to_l3": "minimal"}}}
        assert resolve_compression_intensity("l2_to_l3", config) == "minimal"

    def test_unknown_boundary_defaults_to_standard(self) -> None:
        config = {"meta": {"compression_defaults": {}}}
        assert resolve_compression_intensity("unknown", config) == "standard"

    def test_missing_compression_defaults(self) -> None:
        assert resolve_compression_intensity("l2_to_l3", {}) == "standard"

    def test_invalid_value_defaults_to_standard(self) -> None:
        config = {"meta": {"compression_defaults": {"l2_to_l3": "invalid"}}}
        assert resolve_compression_intensity("l2_to_l3", config) == "standard"

    def test_all_valid_intensities(self) -> None:
        for intensity in VALID_COMPRESSION_INTENSITIES:
            config = {"meta": {"compression_defaults": {"l2_to_l3": intensity}}}
            assert resolve_compression_intensity("l2_to_l3", config) == intensity

    def test_compression_intensity_in_select_context(self) -> None:
        result = select_context("feature", profiles_path=PROFILES_YAML)
        assert "compression_intensity" in result
        assert result["compression_intensity"] in VALID_COMPRESSION_INTENSITIES

    def test_compression_intensity_matches_l2_to_l3_config(self) -> None:
        config = load_profiles(PROFILES_YAML)
        result = select_context("hotfix", profiles_path=PROFILES_YAML)
        expected = resolve_compression_intensity("l2_to_l3", config)
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
        :func:`apply_plan_mode_overrides` (the names ``agent_hierarchy`` and
        ``decomposition_gate`` are aspirational keys that may not all exist
        in the section registry yet — what matters is that the priority dict
        carries the ``critical`` mark so future registry additions inherit it).
        ``model_hint`` is verified via :func:`select_context` directly.
        """
        monkeypatch.delenv("DEVOLAFLOW_PLAN_MODE", raising=False)
        monkeypatch.chdir(tmp_path)

        result = select_context("refactor", profiles_path=PROFILES_YAML, plan_mode=True)
        assert result["plan_mode"] is True
        assert result["model_hint"] == "quality"

        baseline_profile = {"section_priorities": {"execution_protocol": "important"}}
        plan_profile = apply_plan_mode_overrides(baseline_profile)
        assert plan_profile["section_priorities"]["agent_hierarchy"] == "critical"
        assert plan_profile["section_priorities"]["decomposition_gate"] == "critical"
        assert plan_profile["section_priorities"]["rationalization_prevention"] == "critical"
        assert plan_profile["section_priorities"]["execution_protocol"] == "supplementary"

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
        assert composed["section_priorities"]["agent_hierarchy"] == "critical"
        assert composed["section_priorities"]["decomposition_gate"] == "critical"
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
                "agent_hierarchy": "supplementary",
                "execution_protocol": "critical",
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
        assert result["section_priorities"]["agent_hierarchy"] == "critical"
        assert result["section_priorities"]["execution_protocol"] == "supplementary"
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
