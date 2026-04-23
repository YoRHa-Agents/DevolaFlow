"""Tests that verify documentation numeric claims match actual repo state.

Prevents drift where README, demo pages, or other docs claim stale counts
for workflow types, benchmark scenarios, templates, tests, etc.
"""

import json
import re
from pathlib import Path

# v8.3.0 PV-06 (v8.2.6) added the `change-driven` workflow template to the
# registry + Python API surface. v8.2.9 closure: change-driven row added to
# README + SKILL + workflow-skill.yaml + EN/ZH workflow-types guides in this
# PV; the deferral set is now empty. Kept as a typed sentinel so future
# deferrals can re-populate it without changing call-site shapes.
_DEFERRED_DOC_TEMPLATES_V8_2_9: frozenset[str] = frozenset()


def _registry_template_names(project_root: Path) -> set[str]:
    """Return template names from registry.yaml — used to size the deferred-set
    drift allowance precisely (so a stray template doesn't sneak in)."""
    import yaml

    raw = yaml.safe_load(
        (project_root / "workflow-system/agent/templates/registry.yaml").read_text()
    )
    return {entry["name"] for entry in raw.get("templates", [])}


def test_readme_workflow_type_count(project_root: Path):
    """README workflow types table rows must match template YAML file count.

    Templates in ``_DEFERRED_DOC_TEMPLATES_V8_2_9`` are excluded from this
    check because their README rows are intentionally deferred to v8.2.9
    (see module-level docstring); the table is permitted to lag the disk
    count by exactly the size of the deferred set.
    """
    readme = (project_root / "README.md").read_text()
    templates_dir = project_root / "workflow-system" / "agent" / "templates" / "builtin"

    section_match = re.search(
        r"### \d+ Built-in Workflow Types\n(.*?)(?=\n### |\n## |\Z)",
        readme,
        re.DOTALL,
    )
    assert section_match, "Could not find 'Built-in Workflow Types' section in README"
    section = section_match.group(1)
    table_lines = [line for line in section.splitlines() if line.startswith("|")]
    table_rows = len(table_lines) - 2  # subtract header + separator

    yaml_count = len(list(templates_dir.glob("*.yaml")))

    # v7.4.2: 19 → 20 with repo-init added; v8.0.0 P-11: 20 → 21 with
    # entropy-cleanup added; v8.2.6: 21 → 22 with change-driven added
    # (README/SKILL rows deferred to v8.2.9 — see _DEFERRED_DOC_TEMPLATES_V8_2_9).
    deferred_present = _DEFERRED_DOC_TEMPLATES_V8_2_9 & _registry_template_names(project_root)
    expected_table_rows = yaml_count - len(deferred_present)
    assert table_rows == expected_table_rows, (
        f"README table has {table_rows} rows, disk has {yaml_count} templates, "
        f"expected {expected_table_rows} (= disk - {len(deferred_present)} deferred to v8.2.9: "
        f"{sorted(deferred_present)})"
    )


def test_readme_template_count_in_dev_setup(project_root: Path):
    """Dev setup section template count must match actual template count
    (modulo templates whose README integration is deferred to v8.2.9 —
    see ``_DEFERRED_DOC_TEMPLATES_V8_2_9`` at the top of this module)."""
    readme = (project_root / "README.md").read_text()
    templates_dir = project_root / "workflow-system" / "agent" / "templates" / "builtin"

    section_match = re.search(
        r"### Full Development Setup\n(.*?)(?=\n## |\n### |\Z)",
        readme,
        re.DOTALL,
    )
    assert section_match, "Could not find 'Full Development Setup' section in README"
    match = re.search(r"(\d+)\s+templates", section_match.group(1))
    assert match, "Could not find template count in dev setup section"
    claimed = int(match.group(1))
    actual = len(list(templates_dir.glob("*.yaml")))

    deferred_present = _DEFERRED_DOC_TEMPLATES_V8_2_9 & _registry_template_names(project_root)
    expected_claim = actual - len(deferred_present)
    assert claimed == expected_claim, (
        f"README dev setup claims {claimed} templates, disk has {actual}, "
        f"expected claim {expected_claim} (= disk - {len(deferred_present)} deferred to v8.2.9)"
    )


def test_readme_design_docs_count(project_root: Path):
    """README project structure design doc count must match disk."""
    readme = (project_root / "README.md").read_text()
    design_dir = project_root / "doc" / "designs"

    matches = re.findall(r"(\d+)\s+design\s+(?:documents?|specs?)", readme, re.IGNORECASE)
    assert matches, "Could not find design docs count in README"
    actual = len(list(design_dir.glob("*.md")))

    for claimed_str in matches:
        claimed = int(claimed_str)
        assert claimed == actual, f"README claims {claimed} design docs, disk has {actual}"


def test_readme_benchmark_scenario_count(project_root: Path):
    """README benchmark scenario count must match actual scenario files."""
    readme = (project_root / "README.md").read_text()
    scenario_dir = project_root / "benchmarks" / "devolaflow_context" / "scenarios"

    match = re.search(r"(\d+)\s+scenarios", readme)
    assert match, "Could not find scenario count in README"
    claimed = int(match.group(1))
    actual = len(list(scenario_dir.glob("*.yaml")))

    assert claimed == actual, f"README claims {claimed} scenarios, disk has {actual}"


def test_demo_index_scenario_count(project_root: Path):
    """Demo index.html scenario references must match actual count."""
    demo_index = (project_root / "workflow-system" / "human" / "demo" / "index.html").read_text()
    scenario_dir = project_root / "benchmarks" / "devolaflow_context" / "scenarios"
    actual = len(list(scenario_dir.glob("*.yaml")))

    counts = [
        int(m.group(1)) for m in re.finditer(r"(\d+)\s+(?:benchmark\s+)?scenarios", demo_index)
    ]
    assert counts, "Could not find scenario counts in demo/index.html"

    for claimed in counts:
        assert claimed == actual, f"demo/index.html claims {claimed} scenarios, disk has {actual}"


def test_demo_benchmark_sample_data_scenarios(project_root: Path):
    """SAMPLE_DATA in benchmark-results/index.html must cover all scenario files."""
    bench_html = (
        project_root / "workflow-system" / "human" / "demo" / "benchmark-results" / "index.html"
    ).read_text()
    scenario_dir = project_root / "benchmarks" / "devolaflow_context" / "scenarios"

    match = re.search(r"const\s+SAMPLE_DATA\s*=\s*(\{.*?\});", bench_html)
    assert match, "Could not find SAMPLE_DATA in benchmark-results/index.html"

    data = json.loads(match.group(1))
    sample_scenarios: set[str] = set()
    for round_data in data["rounds"]:
        sample_scenarios.update(round_data["scenarios"].keys())

    disk_scenarios = {f.stem for f in scenario_dir.glob("*.yaml")}

    missing = disk_scenarios - sample_scenarios
    assert not missing, f"SAMPLE_DATA missing scenarios: {sorted(missing)}"


def test_workflow_skill_yaml_template_count(project_root: Path):
    """workflow-skill.yaml builtin template count must match disk
    (modulo templates whose workflow-skill.yaml entry is deferred to v8.2.9 —
    see ``_DEFERRED_DOC_TEMPLATES_V8_2_9`` at the top of this module)."""
    skill_yaml = (project_root / "workflow-system" / "agent" / "workflow-skill.yaml").read_text()
    templates_dir = project_root / "workflow-system" / "agent" / "templates" / "builtin"

    yaml_entries = len(re.findall(r'file:\s*"templates/builtin/', skill_yaml))
    disk_count = len(list(templates_dir.glob("*.yaml")))

    deferred_present = _DEFERRED_DOC_TEMPLATES_V8_2_9 & _registry_template_names(project_root)
    expected_entries = disk_count - len(deferred_present)
    assert yaml_entries == expected_entries, (
        f"workflow-skill.yaml has {yaml_entries} builtin entries, disk has "
        f"{disk_count}, expected {expected_entries} (= disk - {len(deferred_present)} "
        f"deferred to v8.2.9)"
    )


def test_registry_template_count(project_root: Path):
    """registry.yaml template count must match actual template files."""
    registry = (
        project_root / "workflow-system" / "agent" / "templates" / "registry.yaml"
    ).read_text()
    templates_dir = project_root / "workflow-system" / "agent" / "templates" / "builtin"

    registry_entries = len(re.findall(r"^\s+- name:", registry, re.MULTILINE))
    disk_count = len(list(templates_dir.glob("*.yaml")))

    assert registry_entries == disk_count, (
        f"registry.yaml has {registry_entries} entries, disk has {disk_count}"
    )


def test_context_profiles_count(project_root: Path):
    """Context profile count in YAML must match demo page references."""
    profiles_yaml = (
        project_root / "workflow-system" / "agent" / "context_profiles.yaml"
    ).read_text()
    demo_index = (project_root / "workflow-system" / "human" / "demo" / "index.html").read_text()

    profiles_section = profiles_yaml.split("\nprofiles:\n", 1)[-1]
    profile_count = len(re.findall(r"^  [a-z][\w-]*:\s*$", profiles_section, re.MULTILINE))

    counts = [int(m.group(1)) for m in re.finditer(r"(\d+)\s+context\s+profiles", demo_index)]
    assert counts, "Could not find context profile counts in demo/index.html"

    for claimed in counts:
        assert claimed == profile_count, (
            f"demo/index.html claims {claimed} profiles, YAML has {profile_count}"
        )


def test_architecture_js_skill_lines(project_root: Path):
    """architecture.js SKILL.md line reference must be within 10 of actual."""
    skill_md = project_root / "workflow-system" / "agent" / "SKILL.md"
    arch_js = (
        project_root
        / "workflow-system"
        / "human"
        / "demo"
        / "design-architecture"
        / "architecture.js"
    )

    actual_lines = len(skill_md.read_text().splitlines())

    match = re.search(r"lines:\s*(\d+)", arch_js.read_text())
    assert match, "Could not find SKILL.md line count in architecture.js"
    claimed_lines = int(match.group(1))

    assert abs(actual_lines - claimed_lines) <= 10, (
        f"architecture.js claims {claimed_lines} lines, SKILL.md has {actual_lines} "
        f"(delta {abs(actual_lines - claimed_lines)} > 10)"
    )


def test_bump_version_location_count(project_root: Path):
    """VERSION_LOCATIONS count must match README reference."""
    bump_script = (project_root / "scripts" / "bump_version.py").read_text()
    readme = (project_root / "README.md").read_text()

    locations = len(re.findall(r'"path":', bump_script))

    match = re.search(r"all\s+(\d+)\s+version\s+locations?", readme)
    assert match, "Could not find version location count in README"
    claimed = int(match.group(1))

    assert locations == claimed, (
        f"bump_version.py has {locations} VERSION_LOCATIONS, README claims {claimed}"
    )


def test_demo_index_rules_count(project_root: Path):
    """Demo index.html 'Repository Rules' count must match actual rule IDs in .cursor/rules/."""
    demo_index = (project_root / "workflow-system" / "human" / "demo" / "index.html").read_text()

    match = re.search(r"(\d+)\s+Repository\s+Rules", demo_index)
    assert match, "Could not find 'Repository Rules' count in demo/index.html"
    claimed = int(match.group(1))

    rules_dir = project_root / ".cursor" / "rules"
    rule_id_pattern = re.compile(r"^## Rule ([A-Z]+-\d+)", re.MULTILINE)
    actual_ids: set[str] = set()
    for mdc in rules_dir.glob("*.mdc"):
        actual_ids.update(rule_id_pattern.findall(mdc.read_text()))

    assert claimed == len(actual_ids), (
        f"demo/index.html claims {claimed} rules, "
        f"but .cursor/rules/ contains {len(actual_ids)} rule IDs: {sorted(actual_ids)}"
    )


def test_demo_index_gate_types(project_root: Path):
    """Demo index.html must reference the canonical gate types, not legacy names."""
    demo_index = (project_root / "workflow-system" / "human" / "demo" / "index.html").read_text()

    for canonical in ("preflight", "revision", "escalation", "abort"):
        assert canonical in demo_index, f"demo/index.html missing canonical gate type '{canonical}'"

    for stale in ("advisory", "automated"):
        assert stale not in demo_index, (
            f"demo/index.html still references stale gate type '{stale}'"
        )


def test_readme_evobench_composite_not_stale(project_root: Path):
    """README composite score claim must be >= 95.0 and baselines must exist."""
    readme = (project_root / "README.md").read_text()

    match = re.search(r"avg composite:\s*\*\*(\d+(?:\.\d+)?)/100\*\*", readme)
    assert match, "Could not find avg composite score in README"
    claimed = float(match.group(1))

    assert claimed >= 95.0, f"README claims composite {claimed}, expected >= 95.0"

    baselines_dir = project_root / "benchmarks" / "devolaflow_context" / "baselines"
    assert baselines_dir.exists(), f"Baselines directory missing: {baselines_dir}"
    assert list(baselines_dir.iterdir()), "Baselines directory is empty"


def test_demo_index_version_matches_package(project_root: Path):
    """Demo index.html 'New in vX.Y.Z' version must match or be at most one patch behind."""
    demo_index = (project_root / "workflow-system" / "human" / "demo" / "index.html").read_text()
    init_py = (project_root / "src" / "devolaflow" / "__init__.py").read_text()

    demo_match = re.search(r"New in v(\d+\.\d+\.\d+)", demo_index)
    assert demo_match, "Could not find 'New in vX.Y.Z' heading in demo/index.html"
    demo_version = demo_match.group(1)

    pkg_match = re.search(r'__version__\s*=\s*"(\d+\.\d+\.\d+)(?:-[a-zA-Z0-9.]+)?"', init_py)
    assert pkg_match, "Could not find __version__ in __init__.py"
    pkg_version = pkg_match.group(1)

    demo_parts = [int(x) for x in demo_version.split(".")]
    pkg_parts = [int(x) for x in pkg_version.split(".")]

    assert demo_parts[0] == pkg_parts[0] and demo_parts[1] == pkg_parts[1], (
        f"demo version {demo_version} major.minor differs from package {pkg_version}"
    )
    patch_delta = pkg_parts[2] - demo_parts[2]
    assert 0 <= patch_delta <= 1, (
        f"demo version {demo_version} is more than 1 patch behind package {pkg_version}"
    )


def test_changelog_has_v7_6_0_entry(project_root: Path):
    """CHANGELOG.md must carry a top-level [7.6.0] entry (P-13 backfill)."""
    changelog = (project_root / "CHANGELOG.md").read_text()
    assert "## [7.6.0]" in changelog, (
        "CHANGELOG.md missing '## [7.6.0]' entry; "
        "P-13 backfilled v7.6.0 from commit 1a4f1ee — re-run scripts/bump_version.py "
        "or restore the entry per CO-2 verbatim contract"
    )


def test_changelog_has_v7_7_0_entry(project_root: Path):
    """CHANGELOG.md must carry a top-level [7.7.0] entry (P-13 backfill)."""
    changelog = (project_root / "CHANGELOG.md").read_text()
    assert "## [7.7.0]" in changelog, (
        "CHANGELOG.md missing '## [7.7.0]' entry; "
        "P-13 backfilled v7.7.0 from commit 828b9ff — re-run scripts/bump_version.py "
        "or restore the entry per CO-2 verbatim contract"
    )


def test_changelog_has_v7_8_0_entry(project_root: Path):
    """CHANGELOG.md must carry a top-level [7.8.0] entry (P-13 backfill)."""
    changelog = (project_root / "CHANGELOG.md").read_text()
    assert "## [7.8.0]" in changelog, (
        "CHANGELOG.md missing '## [7.8.0]' entry; "
        "P-13 backfilled v7.8.0 from commit 17d2a14 — re-run scripts/bump_version.py "
        "or restore the entry per CO-2 verbatim contract"
    )
