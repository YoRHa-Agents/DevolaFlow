"""Tests that verify documentation numeric claims match actual repo state.

Prevents drift where README, demo pages, or other docs claim stale counts
for workflow types, benchmark scenarios, templates, tests, etc.
"""

import json
import re
from pathlib import Path


def test_readme_workflow_type_count(project_root: Path):
    """README workflow types table rows must match template YAML file count."""
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

    assert table_rows == yaml_count == 17, (
        f"README table has {table_rows} rows, disk has {yaml_count} templates, expected 17"
    )


def test_readme_template_count_in_dev_setup(project_root: Path):
    """Dev setup section template count must match actual template count."""
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

    assert claimed == actual, f"README dev setup claims {claimed} templates, disk has {actual}"


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
    """workflow-skill.yaml builtin template count must match disk."""
    skill_yaml = (project_root / "workflow-system" / "agent" / "workflow-skill.yaml").read_text()
    templates_dir = project_root / "workflow-system" / "agent" / "templates" / "builtin"

    yaml_entries = len(re.findall(r'file:\s*"templates/builtin/', skill_yaml))
    disk_count = len(list(templates_dir.glob("*.yaml")))

    assert yaml_entries == disk_count, (
        f"workflow-skill.yaml has {yaml_entries} builtin entries, disk has {disk_count}"
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
