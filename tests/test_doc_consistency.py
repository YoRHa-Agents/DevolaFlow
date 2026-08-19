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


def _registry_composition_names(project_root: Path) -> set[str]:
    """Return composition names from registry.yaml (schema v2.0).

    Since the v15.0.0 Phase B collapse (v15-ADR-002) the registered
    workflow-type universe is `templates:` (survivor yamls on disk) plus
    `compositions:` (the 16 collapsed legacy names) — doc surfaces that
    enumerate workflow TYPES are checked against the union, while
    surfaces that enumerate yaml FILES are checked against disk.
    """
    import yaml

    raw = yaml.safe_load(
        (project_root / "workflow-system/agent/templates/registry.yaml").read_text()
    )
    return {entry["name"] for entry in raw.get("compositions") or []}


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
        r"(?:### |\*\*|^)\d+ Built-in Workflow Types(?:\*\*)?\n(.*?)(?=\n### |\n## |\Z)",
        readme,
        re.DOTALL | re.MULTILINE,
    )
    assert section_match, "Could not find 'Built-in Workflow Types' section in README"
    section = section_match.group(1)
    table_lines = [line for line in section.splitlines() if line.startswith("|")]
    table_rows = len(table_lines) - 2  # subtract header + separator

    yaml_count = len(list(templates_dir.glob("*.yaml")))

    # v7.4.2: 19 → 20 with repo-init added; v8.0.0 P-11: 20 → 21 with
    # entropy-cleanup added; v8.2.6: 21 → 22 with change-driven added
    # (README/SKILL rows deferred to v8.2.9 — see _DEFERRED_DOC_TEMPLATES_V8_2_9).
    # v15.0.0 (v15-ADR-002 Phase B): 16 legacy yamls became named
    # compositions; the README enumerates workflow TYPES, so the expected
    # row count is survivors-on-disk + compositions (every name resolves
    # via the alias layer).
    composition_count = len(_registry_composition_names(project_root))
    deferred_present = _DEFERRED_DOC_TEMPLATES_V8_2_9 & _registry_template_names(project_root)
    expected_table_rows = yaml_count + composition_count - len(deferred_present)
    assert table_rows == expected_table_rows, (
        f"README table has {table_rows} rows, disk has {yaml_count} templates "
        f"+ {composition_count} compositions, expected {expected_table_rows} "
        f"(- {len(deferred_present)} deferred to v8.2.9: {sorted(deferred_present)})"
    )


def test_readme_template_count_in_dev_setup(project_root: Path):
    """Dev setup section template count must match actual template count
    (modulo templates whose README integration is deferred to v8.2.9 —
    see ``_DEFERRED_DOC_TEMPLATES_V8_2_9`` at the top of this module)."""
    readme = (project_root / "README.md").read_text()
    templates_dir = project_root / "workflow-system" / "agent" / "templates" / "builtin"

    section_match = re.search(
        r"(?:### |\*\*|^)Full Development Setup(?:\*\*)?\n(.*?)(?=\n## |\n### |\Z)",
        readme,
        re.DOTALL | re.MULTILINE,
    )
    assert section_match, "Could not find 'Full Development Setup' section in README"
    match = re.search(r"(\d+)\s+templates", section_match.group(1))
    assert match, "Could not find template count in dev setup section"
    claimed = int(match.group(1))
    actual = len(list(templates_dir.glob("*.yaml")))

    # v15.0.0 (v15-ADR-002 Phase B): the README count covers workflow
    # TYPES = survivor yamls + named compositions (see
    # _registry_composition_names docstring).
    composition_count = len(_registry_composition_names(project_root))
    deferred_present = _DEFERRED_DOC_TEMPLATES_V8_2_9 & _registry_template_names(project_root)
    expected_claim = actual + composition_count - len(deferred_present)
    assert claimed == expected_claim, (
        f"README dev setup claims {claimed} templates, disk has {actual} "
        f"+ {composition_count} compositions, expected claim {expected_claim} "
        f"(- {len(deferred_present)} deferred to v8.2.9)"
    )


def test_readme_design_docs_count(project_root: Path):
    """README project structure design doc count must match disk."""
    readme = (project_root / "README.md").read_text()
    design_dir = project_root / "docs" / "designs"

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
    """workflow-skill.yaml workflow-type surface must match disk + registry
    (modulo templates whose workflow-skill.yaml entry is deferred to v8.2.9 —
    see ``_DEFERRED_DOC_TEMPLATES_V8_2_9`` at the top of this module).

    v15.0.0 (v15-ADR-002 Phase B, doc-sync slice): `content.templates.builtin`
    carries one `file: "templates/builtin/..."` entry per SURVIVOR yaml on
    disk, and `content.templates.compositions.ids` mirrors the registry's
    `compositions:` names 1:1. Count parity of the resolvable-name set
    (survivors + compositions = 23) is what this test guards.
    """
    import yaml

    skill_yaml_path = project_root / "workflow-system" / "agent" / "workflow-skill.yaml"
    skill_yaml = skill_yaml_path.read_text()
    templates_dir = project_root / "workflow-system" / "agent" / "templates" / "builtin"

    yaml_entries = len(re.findall(r'file:\s*"templates/builtin/', skill_yaml))
    disk_count = len(list(templates_dir.glob("*.yaml")))
    deferred_present = _DEFERRED_DOC_TEMPLATES_V8_2_9 & _registry_template_names(project_root)
    expected_entries = disk_count - len(deferred_present)
    assert yaml_entries == expected_entries, (
        f"workflow-skill.yaml has {yaml_entries} builtin file entries, disk has "
        f"{disk_count} survivor yamls, expected {expected_entries} "
        f"(- {len(deferred_present)} deferred to v8.2.9)"
    )

    payload = yaml.safe_load(skill_yaml)
    composition_ids = set(
        (payload.get("content", {}).get("templates", {}).get("compositions", {}) or {}).get(
            "ids", []
        )
    )
    registry_compositions = _registry_composition_names(project_root)
    assert composition_ids == registry_compositions, (
        f"workflow-skill.yaml content.templates.compositions.ids drifted from "
        f"registry.yaml compositions — missing: "
        f"{sorted(registry_compositions - composition_ids)}, extra: "
        f"{sorted(composition_ids - registry_compositions)}"
    )


def test_registry_template_count(project_root: Path):
    """registry.yaml template entries must match the on-disk yaml files.

    Schema v2.0 (v15-ADR-002): the `templates:` list mirrors disk 1:1;
    the `compositions:` manifest must not shadow any template name.
    """
    import yaml

    raw = yaml.safe_load(
        (project_root / "workflow-system" / "agent" / "templates" / "registry.yaml").read_text()
    )
    templates_dir = project_root / "workflow-system" / "agent" / "templates" / "builtin"

    template_names = {entry["name"] for entry in raw.get("templates", [])}
    composition_names = {entry["name"] for entry in raw.get("compositions", [])}
    disk_names = {p.stem for p in templates_dir.glob("*.yaml")}

    assert template_names == disk_names, (
        f"registry.yaml templates {sorted(template_names)} != disk {sorted(disk_names)}"
    )
    assert not (template_names & composition_names), (
        f"compositions shadow templates: {sorted(template_names & composition_names)}"
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
    """Demo index.html 'Repository Rules' count must match the canonical .rules/ corpus.

    v14.2.1 (G-008) demoted the 4 remaining fully-migrated legacy
    `.cursor/rules/*.mdc` files to deprecated pointer stubs, so counting
    `## Rule X-N` headings there no longer reflects the live corpus. The
    honest derivation now counts rule-id headings in the canonical
    `.rules/*.mdc` layer sources — H2 for soul/architecture/conventions/
    workflow, H3 for style (ST-* nests under DS-*/WX-* grouping H2s); the
    " — " separator excludes sub-section headings like `### A-2.1 — …`.
    Mirrors the G-034 parity derivation in
    tests/test_no_ghost_features.py::test_rule_count_under_cap.
    """
    demo_index = (project_root / "workflow-system" / "human" / "demo" / "index.html").read_text()

    match = re.search(r"(\d+)\s+Repository\s+Rules", demo_index)
    assert match, "Could not find 'Repository Rules' count in demo/index.html"
    claimed = int(match.group(1))

    rules_dir = project_root / ".rules"
    rule_id_pattern = re.compile(r"^#{2,3} ((?:S|A|C|W|ST)-\d+) — ", re.MULTILINE)
    actual_ids: set[str] = set()
    for mdc in rules_dir.glob("*.mdc"):
        actual_ids.update(rule_id_pattern.findall(mdc.read_text()))

    assert claimed == len(actual_ids), (
        f"demo/index.html claims {claimed} rules, "
        f"but .rules/ contains {len(actual_ids)} rule IDs: {sorted(actual_ids)}"
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
