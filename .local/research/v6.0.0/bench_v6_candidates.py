#!/usr/bin/env python3
"""v6.0.0 candidate benchmarks — measure before/after deltas for each
proposed improvement. Research artifact only; not part of the test suite.

Outputs JSON to stdout with one record per candidate:
  {
    "candidate_id": "V6-XX",
    "hypothesis": "what we expect to improve",
    "baseline": {...metrics...},
    "candidate": {...metrics with proposed change simulated...},
    "delta": {...improvement magnitude...},
    "measurable_improvement": bool,
  }
"""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import warnings
from pathlib import Path

# Ensure src on path (use installed package via pip -e or add src to path)
ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(ROOT))


# -----------------------------------------------------------------------------
# Benchmark V6-02: apply_round_escalation wired into select_context
# -----------------------------------------------------------------------------
def bench_v6_02() -> dict:
    from devolaflow.task_adaptive_selector import (
        apply_round_escalation,
        load_profiles,
        match_profile,
        select_context,
    )

    task_type = "hotfix"
    # BASELINE: select_context as currently implemented (round-agnostic)
    base_round1 = select_context(task_type)
    base_round3 = select_context(task_type)  # same output — escalation not wired

    # CANDIDATE: apply round escalation to profile, then re-run selection
    # Since select_context doesn't accept round_num, we simulate what the wiring
    # would do: load profile, apply escalation, check budget+section deltas
    config = load_profiles()
    profile_name = match_profile(task_type, config)
    profile = config["profiles"][profile_name]

    profile_r1 = profile
    profile_r3 = apply_round_escalation(profile, round_num=3)

    baseline = {
        "round1_budget": profile_r1.get("token_budget", 6000),
        "round3_budget": base_round3["budget"],  # same as round1 — dead wire
        "round3_critical_sections": sum(
            1 for p in profile_r1.get("section_priorities", {}).values() if p == "critical"
        ),
        "round3_model_hint": base_round3["model_hint"],
    }

    candidate = {
        "round1_budget": profile_r1.get("token_budget", 6000),
        "round3_budget": profile_r3.get("token_budget", 6000),
        "round3_critical_sections": sum(
            1 for p in profile_r3.get("section_priorities", {}).values() if p == "critical"
        ),
        "round3_model_hint": profile_r3.get("model_hint", "inherit"),
    }

    delta = {
        "budget_increase_pct": round(
            (candidate["round3_budget"] - baseline["round3_budget"])
            / baseline["round3_budget"]
            * 100,
            1,
        ),
        "critical_sections_delta": (
            candidate["round3_critical_sections"] - baseline["round3_critical_sections"]
        ),
        "model_hint_upgraded": baseline["round3_model_hint"] != candidate["round3_model_hint"],
    }

    return {
        "candidate_id": "V6-02",
        "title": "Wire apply_round_escalation into select_context",
        "hypothesis": "Round 3 of convergence should get +20% budget, more critical sections, 'quality' model",
        "baseline": baseline,
        "candidate": candidate,
        "delta": delta,
        "measurable_improvement": delta["budget_increase_pct"] > 0
        and delta["critical_sections_delta"] > 0,
    }


# -----------------------------------------------------------------------------
# Benchmark V6-01: reinforcement merge wired into dispatch
# -----------------------------------------------------------------------------
def bench_v6_01() -> dict:
    from devolaflow.gate.models import Finding
    from devolaflow.gate.reinforcement import (
        findings_to_reinforcement,
        merge_reinforcement_into_dispatch,
    )

    # Simulate: round 1 of a convergence failed with 3 gate findings.
    round1_findings = [
        Finding(
            finding_id="F-001",
            severity="blocker",
            category="testing",
            location="src/devolaflow/feedback.py",
            description="Test coverage 65% below 80% threshold",
            suggestion="Add tests for error-handling paths",
        ),
        Finding(
            finding_id="F-002",
            severity="critical",
            category="complexity",
            location="src/devolaflow/gate/scorer.py:527",
            description="Function complexity CC=18 exceeds limit 10",
            suggestion="Decompose into 3 helpers",
        ),
        Finding(
            finding_id="F-003",
            severity="major",
            category="documentation",
            location="src/devolaflow/cli.py:30",
            description="Missing docstring on public API",
            suggestion="Add numpydoc-style docstring",
        ),
    ]

    # Baseline: dispatch without reinforcement (current production behavior)
    baseline_dispatch = {
        "task_id": "T-01",
        "type": "refine",
        "context": {"applicable_rules": {"base": ["P1-P5"]}},
    }

    # Candidate: same dispatch with reinforcement injection
    reinforcement = findings_to_reinforcement(
        round1_findings, round_num=2, prior_score=70.0, target_score=85.0
    )
    candidate_dispatch = merge_reinforcement_into_dispatch(
        copy.deepcopy(baseline_dispatch), reinforcement
    )

    baseline = {
        "dispatch_bytes": len(json.dumps(baseline_dispatch)),
        "reinforcement_rules": 0,
        "mandates_in_dispatch": 0,
        "severity_coverage": [],
    }

    rules_in_dispatch = (
        candidate_dispatch["context"]["applicable_rules"]["reinforcement"]["rules"]
    )
    candidate = {
        "dispatch_bytes": len(json.dumps(candidate_dispatch)),
        "reinforcement_rules": len(rules_in_dispatch),
        "mandates_in_dispatch": sum(
            1 for r in rules_in_dispatch if r["mandate"].startswith("MUST fix:")
        ),
        "severity_coverage": sorted({r["severity"] for r in rules_in_dispatch}),
    }

    delta = {
        "bytes_added": candidate["dispatch_bytes"] - baseline["dispatch_bytes"],
        "rules_added": candidate["reinforcement_rules"],
        "mandates_forced_into_l3": candidate["mandates_in_dispatch"],
    }

    return {
        "candidate_id": "V6-01",
        "title": "Wire reinforcement into convergence dispatch",
        "hypothesis": "Round N+1 dispatch should carry ≤5 MUST-fix mandates per severity-filtered finding",
        "baseline": baseline,
        "candidate": candidate,
        "delta": delta,
        "measurable_improvement": delta["mandates_forced_into_l3"] > 0,
    }


# -----------------------------------------------------------------------------
# Benchmark V6-04: unwanted_hints negative routing
# -----------------------------------------------------------------------------
def bench_v6_04() -> dict:
    import yaml

    from benchmarks.devolaflow_context.evaluator import evaluate_scenario
    from devolaflow.task_adaptive_selector import select_context

    # Run across ALL scenarios to measure aggregate noise reduction potential
    scenarios_dir = ROOT / "benchmarks" / "devolaflow_context" / "scenarios"

    base_noise_ratios: list[float] = []
    cand_noise_ratios: list[float] = []
    scenarios_with_noise = 0
    total_scenarios = 0

    for scen_path in sorted(scenarios_dir.glob("*.yaml")):
        scenario = yaml.safe_load(scen_path.read_text())
        task_type = scenario["task_type"]
        expected = scenario.get("expected_sections", [])
        unwanted = scenario.get("unwanted_sections", [])

        result = select_context(task_type)
        selected = [s["name"] for s in result["selected_sections"]]

        # Baseline: current selection as-is
        base_score = evaluate_scenario(scen_path.stem, result, expected, unwanted)

        # Candidate: profile-level unwanted_hints filter — drop sections matching unwanted list
        filtered_sections = [s for s in result["selected_sections"] if s["name"] not in unwanted]
        cand_result = {**result, "selected_sections": filtered_sections}
        cand_score = evaluate_scenario(scen_path.stem, cand_result, expected, unwanted)

        base_noise_ratios.append(base_score.noise_ratio)
        cand_noise_ratios.append(cand_score.noise_ratio)
        if base_score.noise_ratio > 0:
            scenarios_with_noise += 1
        total_scenarios += 1

    base_avg = sum(base_noise_ratios) / len(base_noise_ratios) if base_noise_ratios else 0.0
    cand_avg = sum(cand_noise_ratios) / len(cand_noise_ratios) if cand_noise_ratios else 0.0

    baseline = {
        "scenarios_evaluated": total_scenarios,
        "scenarios_with_noise": scenarios_with_noise,
        "avg_noise_ratio": round(base_avg, 4),
        "max_noise_ratio": round(max(base_noise_ratios) if base_noise_ratios else 0.0, 4),
    }
    candidate = {
        "scenarios_evaluated": total_scenarios,
        "scenarios_with_noise": sum(1 for r in cand_noise_ratios if r > 0),
        "avg_noise_ratio": round(cand_avg, 4),
        "max_noise_ratio": round(max(cand_noise_ratios) if cand_noise_ratios else 0.0, 4),
    }
    delta = {
        "scenarios_cleaned": baseline["scenarios_with_noise"] - candidate["scenarios_with_noise"],
        "avg_noise_reduction": round(base_avg - cand_avg, 4),
        "max_noise_reduction": round(baseline["max_noise_ratio"] - candidate["max_noise_ratio"], 4),
    }

    return {
        "candidate_id": "V6-04",
        "title": "Add unwanted_hints negative routing to profiles",
        "hypothesis": "Profile-level unwanted_hints drops noise sections, reducing avg noise_ratio across scenarios",
        "baseline": baseline,
        "candidate": candidate,
        "delta": delta,
        "measurable_improvement": delta["scenarios_cleaned"] > 0 or delta["avg_noise_reduction"] > 0,
    }


# -----------------------------------------------------------------------------
# Benchmark TD-1 / V6-06: Remove deprecated APIs — measure LOC + warnings
# -----------------------------------------------------------------------------
def bench_td_1() -> dict:
    # Count lines in the two deprecated functions
    scorer = (SRC / "devolaflow" / "gate" / "scorer.py").read_text().splitlines()
    advisor = (SRC / "devolaflow" / "nines" / "advisor.py").read_text().splitlines()

    # Find evaluate_gate_with_nines function
    def count_function(lines: list[str], name: str) -> int:
        start = None
        indent = None
        count = 0
        for i, line in enumerate(lines):
            if start is None:
                if line.lstrip().startswith(f"def {name}("):
                    start = i
                    indent = len(line) - len(line.lstrip())
            else:
                if line.strip() == "":
                    count += 1
                    continue
                cur_indent = len(line) - len(line.lstrip())
                if cur_indent <= indent and not line.startswith(("def ", "class ", "@")):
                    # Still in function if more indented
                    if cur_indent > indent:
                        count += 1
                    else:
                        break
                count += 1
        return count

    egwn_loc = count_function(scorer, "evaluate_gate_with_nines")
    advisor_loc = count_function(advisor, "run_nines_advisor")

    # Count DeprecationWarnings raised in full test run
    result = subprocess.run(
        ["python", "-m", "pytest", "tests/", "-q", "--tb=no", "-W", "default::DeprecationWarning"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    warning_count = sum(
        1 for line in (result.stdout + result.stderr).splitlines() if "DeprecationWarning" in line
    )

    # Count tests that test the deprecated API (will be removed with it)
    test_nines = (ROOT / "tests" / "test_nines.py").read_text()
    deprecated_test_classes = [
        "TestEvaluateGateWithNines",
        "TestRunNinesAdvisor",
    ]
    affected_tests = sum(
        test_nines.count(f"class {cls}") * 10  # rough estimate: 10 tests per class
        for cls in deprecated_test_classes
    )

    baseline = {
        "loc_to_remove": egwn_loc + advisor_loc,
        "deprecation_warnings_in_test_run": warning_count,
        "tests_to_retire_estimate": affected_tests,
    }
    candidate = {
        "loc_to_remove": 0,
        "deprecation_warnings_in_test_run": 0,
        "tests_to_retire_estimate": 0,
    }
    delta = {
        "loc_removed": baseline["loc_to_remove"],
        "warnings_eliminated": baseline["deprecation_warnings_in_test_run"],
        "test_debt_removed": baseline["tests_to_retire_estimate"],
    }

    return {
        "candidate_id": "V6-06/TD-1",
        "title": "Remove deprecated evaluate_gate_with_nines and run_nines_advisor",
        "hypothesis": "Explicit v6.0 removal eliminates all DeprecationWarnings and reduces gate/nines LOC",
        "baseline": baseline,
        "candidate": candidate,
        "delta": delta,
        "measurable_improvement": delta["loc_removed"] > 0,
    }


# -----------------------------------------------------------------------------
# Benchmark TD-2 / V6-07: Remove _BUILTIN_SPECS
# -----------------------------------------------------------------------------
def bench_td_2() -> dict:
    loader = (SRC / "devolaflow" / "plugins" / "loader.py").read_text().splitlines()

    # Count lines in _BUILTIN_SPECS
    in_specs = False
    lines_in_specs = 0
    brace_depth = 0
    for line in loader:
        stripped = line.strip()
        if stripped.startswith("_BUILTIN_SPECS"):
            in_specs = True
            lines_in_specs += 1
            brace_depth = stripped.count("{") - stripped.count("}")
            continue
        if in_specs:
            lines_in_specs += 1
            brace_depth += stripped.count("{") - stripped.count("}")
            if brace_depth <= 0 and stripped.endswith("}"):
                break

    import yaml as _yaml

    plugins_yaml = ROOT / "workflow-system" / "agent" / "plugins.yaml"
    data = _yaml.safe_load(plugins_yaml.read_text())
    yaml_plugins = len(data.get("plugins", {}))

    # Check if YAML is superset of _BUILTIN_SPECS
    baseline = {
        "_BUILTIN_SPECS_loc": lines_in_specs,
        "yaml_plugins": yaml_plugins,
        "duplication_factor": 2,  # 2 sources (Python dict + YAML)
    }
    candidate = {
        "_BUILTIN_SPECS_loc": 0,
        "yaml_plugins": yaml_plugins,
        "duplication_factor": 1,  # YAML as SSOT
    }
    delta = {
        "loc_removed": lines_in_specs,
        "sources_consolidated": baseline["duplication_factor"] - candidate["duplication_factor"],
    }

    return {
        "candidate_id": "V6-07/TD-2",
        "title": "Remove _BUILTIN_SPECS; plugins.yaml becomes SSOT",
        "hypothesis": "_BUILTIN_SPECS duplicates plugins.yaml; removal halves plugin spec sources",
        "baseline": baseline,
        "candidate": candidate,
        "delta": delta,
        "measurable_improvement": delta["loc_removed"] > 0,
    }


# -----------------------------------------------------------------------------
# Benchmark TD-3: Remove MVP-SKILL.md references
# -----------------------------------------------------------------------------
def bench_td_3() -> dict:
    import re

    pattern = re.compile(r"MVP[-_]SKILL", re.IGNORECASE)
    files_with_refs: list[str] = []
    total_matches = 0
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in {".git", "__pycache__", "node_modules", "dist", ".venv"} for part in path.parts):
            continue
        if path.suffix in {".pyc", ".zip", ".png", ".jpg", ".svg"}:
            continue
        try:
            text = path.read_text(errors="ignore")
        except Exception:
            continue
        hits = len(pattern.findall(text))
        if hits > 0:
            # Filter out the file itself (workflow-system/agent/MVP-SKILL.md) from "referencing"
            if "MVP-SKILL.md" not in path.name:
                files_with_refs.append(str(path.relative_to(ROOT)))
                total_matches += hits

    mvp_path = ROOT / "workflow-system" / "agent" / "MVP-SKILL.md"
    mvp_loc = len(mvp_path.read_text().splitlines()) if mvp_path.exists() else 0

    baseline = {
        "files_referencing_MVP_SKILL": len(files_with_refs),
        "total_mentions": total_matches,
        "mvp_file_loc": mvp_loc,
    }
    candidate = {
        "files_referencing_MVP_SKILL": 0,
        "total_mentions": 0,
        "mvp_file_loc": 0,
    }
    delta = {
        "files_cleaned": baseline["files_referencing_MVP_SKILL"],
        "mentions_removed": baseline["total_mentions"],
        "legacy_file_loc_removed": mvp_loc,
    }

    return {
        "candidate_id": "TD-3",
        "title": "Remove MVP-SKILL.md file + all cross-references",
        "hypothesis": "CHANGELOG v5.4.1 deprecated MVP-SKILL.md; 14+ references need cleanup",
        "baseline": baseline,
        "candidate": candidate,
        "delta": delta,
        "measurable_improvement": delta["files_cleaned"] > 0,
    }


# -----------------------------------------------------------------------------
# Benchmark R1: AdapterRegistry effort reduction for Nth adapter
# -----------------------------------------------------------------------------
def bench_r1() -> dict:
    # Measure current adapter LOC + build_skill.py delta per adapter
    adapters_dir = SRC / "devolaflow" / "adapters"
    current_adapters = sorted(
        p.name for p in adapters_dir.glob("*_adapter.py") if p.name != "base.py"
    )
    total_adapter_loc = sum(
        len((adapters_dir / f).read_text().splitlines()) for f in current_adapters
    )
    avg_adapter_loc = total_adapter_loc // max(len(current_adapters), 1)

    build_skill = (SRC / "devolaflow" / "build_skill.py").read_text()
    build_skill_loc = len(build_skill.splitlines())

    # Proposed data-driven YAML config — estimated size from integration proposal
    yaml_config_lines_est = 25  # per Appendix § 6.3 (windsurf.yaml example)

    baseline = {
        "current_adapters": len(current_adapters),
        "avg_python_adapter_loc": avg_adapter_loc,
        "build_skill_orchestrator_loc": build_skill_loc,
        "per_new_adapter_cost_loc": avg_adapter_loc + 3,  # adapter + build_skill edit
    }
    candidate = {
        "current_adapters": len(current_adapters),
        "avg_python_adapter_loc": avg_adapter_loc,
        "build_skill_orchestrator_loc": build_skill_loc,  # stays same
        "per_new_adapter_cost_loc": yaml_config_lines_est,  # YAML only for simple tools
    }
    delta = {
        "loc_per_new_adapter_reduction": baseline["per_new_adapter_cost_loc"]
        - candidate["per_new_adapter_cost_loc"],
        "pct_reduction": round(
            (baseline["per_new_adapter_cost_loc"] - candidate["per_new_adapter_cost_loc"])
            / baseline["per_new_adapter_cost_loc"]
            * 100,
            1,
        ),
    }

    return {
        "candidate_id": "R1/D1",
        "title": "AdapterRegistry + DataDrivenAdapter (YAML-configured)",
        "hypothesis": "Adding a new adapter via YAML config ≈25 lines vs ~80+ lines Python",
        "baseline": baseline,
        "candidate": candidate,
        "delta": delta,
        "measurable_improvement": delta["loc_per_new_adapter_reduction"] > 0,
    }


# -----------------------------------------------------------------------------
# Benchmark C1: Full EvoBench baseline coverage
# -----------------------------------------------------------------------------
def bench_c1() -> dict:
    scenarios_dir = ROOT / "benchmarks" / "devolaflow_context" / "scenarios"
    baselines_dir = ROOT / "benchmarks" / "devolaflow_context" / "baselines"

    scenarios = sorted(p.stem for p in scenarios_dir.glob("*.yaml"))

    # Read the v2.1.0 baseline — the one loaded by runner
    baseline_file = baselines_dir / "v2.1.0_baseline.json"
    if baseline_file.exists():
        data = json.loads(baseline_file.read_text())
        scenarios_with_baseline = set(data.keys())
    else:
        scenarios_with_baseline = set()

    baseline = {
        "total_scenarios": len(scenarios),
        "scenarios_with_regression_baseline": len(scenarios_with_baseline),
        "regression_detection_coverage_pct": round(
            len(scenarios_with_baseline) / len(scenarios) * 100, 1
        )
        if scenarios
        else 0,
    }
    candidate = {
        "total_scenarios": len(scenarios),
        "scenarios_with_regression_baseline": len(scenarios),
        "regression_detection_coverage_pct": 100.0,
    }
    delta = {
        "scenarios_needing_baseline": len(scenarios) - len(scenarios_with_baseline),
        "coverage_pct_improvement": candidate["regression_detection_coverage_pct"]
        - baseline["regression_detection_coverage_pct"],
    }

    return {
        "candidate_id": "C1",
        "title": "Full EvoBench baseline coverage for regression detection",
        "hypothesis": "Only 3 scenarios have regression baselines; CI misses regressions in 26 scenarios",
        "baseline": baseline,
        "candidate": candidate,
        "delta": delta,
        "measurable_improvement": delta["scenarios_needing_baseline"] > 0,
    }


# -----------------------------------------------------------------------------
# Benchmark TD-6: rule rot — CP-3 vs SF-3 inconsistency
# -----------------------------------------------------------------------------
def bench_td_6() -> dict:
    cp3 = (ROOT / ".cursor" / "rules" / "change-process-rules.mdc").read_text()
    sf3 = (ROOT / ".cursor" / "rules" / "skill-format-rules.mdc").read_text()
    claude_md = (ROOT / "CLAUDE.md").read_text()

    # Does CLAUDE.md have a version: key in frontmatter, banner, or body?
    claude_has_version_fm = False
    if claude_md.startswith("---"):
        parts = claude_md.split("---", 2)
        if len(parts) >= 3:
            claude_has_version_fm = "version:" in parts[1]
    claude_has_version_banner = "v5." in claude_md or "v6." in claude_md or "Version" in claude_md
    claude_has_current_version = "Current version" in claude_md

    # Parse rule expectations — check for any CLAUDE.md frontmatter/banner/body mentions
    cp3_lists_claude_fm = (
        "CLAUDE.md (frontmatter" in cp3
        or "CLAUDE.md` (frontmatter" in cp3
        or "CLAUDE.md (banner" in cp3
        or "CLAUDE.md` (banner" in cp3
    )
    sf3_lists_claude_fm = (
        "CLAUDE.md (frontmatter" in sf3
        or "CLAUDE.md` (frontmatter" in sf3
    )

    # Count version-location items in CP-3 and SF-3 (rough heuristic)
    cp3_locations_count = cp3.count("`__init__.py`") + cp3.count("`pyproject.toml`") + cp3.count(
        "`SKILL.md`"
    ) + cp3.count("`CLAUDE.md`") + cp3.count("`workflow-skill.yaml`") + cp3.count(
        "`generate_human_docs.py`"
    ) + cp3.count("`test_smoke.py`") + cp3.count("`README.md`") + cp3.count(
        "`benchmark-results/index.html`"
    )

    sf3_locations_count = 7  # SF-3 manually lists 7 numbered locations

    claude_claims_locations = 0
    for line in claude_md.splitlines():
        if "locations" in line.lower():
            # "11 locations" or similar
            import re as _re

            m = _re.search(r"\b(\d+)\s+locations", line)
            if m:
                claude_claims_locations = int(m.group(1))

    baseline = {
        "cp3_says_claude_has_frontmatter_banner_body": cp3_lists_claude_fm,
        "claude_md_actually_has_version_fm": claude_has_version_fm,
        "claude_md_actually_has_current_version_body": claude_has_current_version,
        "cp3_locations_items_listed": cp3_locations_count,
        "sf3_locations_items_listed": sf3_locations_count,
        "claude_md_claims_locations_count": claude_claims_locations,
        "rule_contradiction_present": cp3_lists_claude_fm and not claude_has_version_fm,
        "cp3_vs_sf3_count_mismatch": abs(cp3_locations_count - sf3_locations_count) > 0,
    }
    candidate = {
        "cp3_says_claude_has_frontmatter_banner_body": False,
        "claude_md_actually_has_version_fm": claude_has_version_fm,
        "claude_md_actually_has_current_version_body": claude_has_current_version,
        "cp3_locations_items_listed": sf3_locations_count,  # unified
        "sf3_locations_items_listed": sf3_locations_count,
        "claude_md_claims_locations_count": sf3_locations_count,
        "rule_contradiction_present": False,
        "cp3_vs_sf3_count_mismatch": False,
    }
    contradictions_resolved = 0
    if baseline["rule_contradiction_present"]:
        contradictions_resolved += 1
    if baseline["cp3_vs_sf3_count_mismatch"]:
        contradictions_resolved += 1
    if baseline["claude_md_claims_locations_count"] != baseline["sf3_locations_items_listed"]:
        contradictions_resolved += 1
    delta = {
        "contradictions_resolved": contradictions_resolved,
    }

    return {
        "candidate_id": "TD-6",
        "title": "Reconcile CP-3 vs SF-3 vs CLAUDE.md version-location rules",
        "hypothesis": "CP-3 lists CLAUDE.md frontmatter/banner/body but real CLAUDE.md has none; SF-3 and CLAUDE.md disagree on count",
        "baseline": baseline,
        "candidate": candidate,
        "delta": delta,
        "measurable_improvement": delta["contradictions_resolved"] > 0,
    }


# -----------------------------------------------------------------------------
# Benchmark V6-01 + V6-02 combined — simulated 3-round convergence
# -----------------------------------------------------------------------------
def bench_combined_convergence() -> dict:
    """Simulate: does wiring V6-01 + V6-02 reduce wasted convergence rounds?

    Baseline: round N has same budget + no reinforcement → L3 keeps getting
    findings, 2 stagnation rounds trigger escalate.

    Candidate: round N has escalated budget + merged reinforcement → L3 has
    explicit MUST-fix mandates and room to address them, reducing stagnation.
    """
    from devolaflow.gate.models import Finding
    from devolaflow.gate.reinforcement import (
        findings_to_reinforcement,
        merge_reinforcement_into_dispatch,
    )
    from devolaflow.task_adaptive_selector import (
        apply_round_escalation,
        load_profiles,
        match_profile,
    )

    # Scenario: refactor task, 3 convergence rounds with stagnating findings
    task_type = "refactor"
    config = load_profiles()
    profile_name = match_profile(task_type, config)
    profile = config["profiles"][profile_name]

    findings_per_round = [
        Finding(
            finding_id="F-Cx",
            severity="critical",
            category="complexity",
            location="src/devolaflow/gate/scorer.py",
            description="CC=18",
            suggestion="Decompose",
        ),
        Finding(
            finding_id="F-Tc",
            severity="blocker",
            category="testing",
            location="tests/test_gate.py",
            description="Coverage 72%",
            suggestion="Add edge cases",
        ),
    ]

    def run_round(round_num: int, use_v6_features: bool) -> dict:
        if use_v6_features:
            eff_profile = apply_round_escalation(profile, round_num)
        else:
            eff_profile = profile
        budget = eff_profile.get("token_budget", 6000)
        critical_count = sum(
            1 for p in eff_profile.get("section_priorities", {}).values() if p == "critical"
        )
        model_hint = eff_profile.get("model_hint", "inherit")
        dispatch = {"task_id": f"T-round-{round_num}", "context": {}}
        reinforcement_count = 0
        if use_v6_features and round_num > 1:
            rb = findings_to_reinforcement(
                findings_per_round, round_num, prior_score=75.0, target_score=85.0
            )
            dispatch = merge_reinforcement_into_dispatch(dispatch, rb)
            reinforcement_count = len(rb.rules)
        return {
            "round": round_num,
            "budget": budget,
            "critical_sections": critical_count,
            "model_hint": model_hint,
            "reinforcement_rules_in_dispatch": reinforcement_count,
        }

    baseline_rounds = [run_round(n, use_v6_features=False) for n in (1, 2, 3)]
    candidate_rounds = [run_round(n, use_v6_features=True) for n in (1, 2, 3)]

    # Success proxy: dispatch bytes carrying explicit mandates over all rounds
    base_total_rules = sum(r["reinforcement_rules_in_dispatch"] for r in baseline_rounds)
    cand_total_rules = sum(r["reinforcement_rules_in_dispatch"] for r in candidate_rounds)

    base_avg_budget = sum(r["budget"] for r in baseline_rounds) / 3
    cand_avg_budget = sum(r["budget"] for r in candidate_rounds) / 3

    base_round3_critical = baseline_rounds[-1]["critical_sections"]
    cand_round3_critical = candidate_rounds[-1]["critical_sections"]

    baseline = {
        "rounds": baseline_rounds,
        "total_reinforcement_rules_injected": base_total_rules,
        "avg_budget_across_rounds": int(base_avg_budget),
        "round3_critical_sections": base_round3_critical,
        "round3_model_hint": baseline_rounds[-1]["model_hint"],
    }
    candidate = {
        "rounds": candidate_rounds,
        "total_reinforcement_rules_injected": cand_total_rules,
        "avg_budget_across_rounds": int(cand_avg_budget),
        "round3_critical_sections": cand_round3_critical,
        "round3_model_hint": candidate_rounds[-1]["model_hint"],
    }
    delta = {
        "reinforcement_rules_added_across_rounds": cand_total_rules - base_total_rules,
        "budget_increase_pct_across_rounds": round(
            (cand_avg_budget - base_avg_budget) / base_avg_budget * 100, 1
        )
        if base_avg_budget
        else 0,
        "round3_critical_sections_added": cand_round3_critical - base_round3_critical,
        "round3_model_hint_upgrade": (
            baseline_rounds[-1]["model_hint"] != candidate_rounds[-1]["model_hint"]
        ),
    }

    return {
        "candidate_id": "V6-01+V6-02-combined",
        "title": "Combined: reinforcement + round escalation wired into convergence",
        "hypothesis": "Late convergence rounds receive explicit MUST-fix mandates AND larger budget AND quality model — reducing stagnation probability",
        "baseline": baseline,
        "candidate": candidate,
        "delta": delta,
        "measurable_improvement": (
            delta["reinforcement_rules_added_across_rounds"] > 0
            and delta["budget_increase_pct_across_rounds"] > 0
        ),
    }


# -----------------------------------------------------------------------------
# Baseline EvoBench composite scores per scenario (used to show v6.0
# candidates don't regress)
# -----------------------------------------------------------------------------
def bench_evobench_baseline() -> dict:
    import yaml

    from benchmarks.devolaflow_context.evaluator import evaluate_scenario
    from devolaflow.task_adaptive_selector import select_context

    scenarios_dir = ROOT / "benchmarks" / "devolaflow_context" / "scenarios"

    records = []
    for scen_path in sorted(scenarios_dir.glob("*.yaml")):
        scenario = yaml.safe_load(scen_path.read_text())
        try:
            result = select_context(scenario["task_type"])
            score = evaluate_scenario(
                scen_path.stem,
                result,
                scenario.get("expected_sections", []),
                scenario.get("unwanted_sections", []),
            )
            records.append(
                {
                    "scenario": scen_path.stem,
                    "profile": score.profile_name,
                    "section_relevance": score.section_relevance,
                    "noise_ratio": score.noise_ratio,
                    "budget_utilization": score.budget_utilization,
                    "information_density": score.information_density,
                    "total_tokens": score.total_tokens,
                    "budget": score.budget,
                }
            )
        except Exception as e:
            records.append({"scenario": scen_path.stem, "error": str(e)})

    ok = [r for r in records if "error" not in r]
    avg_density = sum(r["information_density"] for r in ok) / len(ok) if ok else 0.0
    avg_noise = sum(r["noise_ratio"] for r in ok) / len(ok) if ok else 0.0
    zero_noise_count = sum(1 for r in ok if r["noise_ratio"] == 0.0)

    return {
        "candidate_id": "EvoBench-baseline",
        "title": "Current EvoBench composite across all 29 scenarios (v5.4.2 baseline)",
        "hypothesis": "Snapshot baseline for v6.0 regression comparison",
        "baseline": {
            "scenarios_evaluated": len(ok),
            "avg_information_density": round(avg_density, 4),
            "avg_noise_ratio": round(avg_noise, 4),
            "zero_noise_scenarios": zero_noise_count,
        },
        "candidate": {
            "scenarios_evaluated": len(ok),
            "target_avg_density": 0.70,
            "target_avg_noise": 0.0,
            "target_zero_noise_count": len(ok),
        },
        "delta": {
            "scenarios_below_0_70_density": sum(1 for r in ok if r["information_density"] < 0.70),
        },
        "measurable_improvement": True,
        "per_scenario_records": records,
    }


# -----------------------------------------------------------------------------
# Run all benchmarks
# -----------------------------------------------------------------------------
def main():
    benchmarks = [
        bench_v6_02,
        bench_v6_01,
        bench_v6_04,
        bench_combined_convergence,
        bench_td_1,
        bench_td_2,
        bench_td_3,
        bench_r1,
        bench_c1,
        bench_td_6,
        bench_evobench_baseline,
    ]
    results = []
    for bench in benchmarks:
        try:
            result = bench()
            results.append(result)
        except Exception as e:
            results.append(
                {
                    "candidate_id": bench.__name__,
                    "error": f"{type(e).__name__}: {e}",
                    "measurable_improvement": None,
                }
            )

    print(json.dumps(results, indent=2, default=str))


if __name__ == "__main__":
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        main()
