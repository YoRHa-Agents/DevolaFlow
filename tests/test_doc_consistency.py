"""Tests that verify documentation numeric claims match actual repo state.

Prevents drift where README, demo pages, or other docs claim stale counts
for checklist seeds, runtime templates, tests, etc.
"""

import re
from pathlib import Path


def _registry_template_names(project_root: Path) -> set[str]:
    """Return the registry-v3 checklist-seed name universe."""
    import yaml

    raw = yaml.safe_load(
        (project_root / "workflow-system/agent/templates/registry.yaml").read_text()
    )
    entries = (raw.get("compositions") or []) + (raw.get("templates") or [])
    return {entry["name"] for entry in entries}


def test_curl_all_and_update_scope_is_explicit(project_root: Path):
    """curl all excludes standalone; update scans host skill copies only."""
    readme = (project_root / "README.md").read_text()
    skill = (project_root / "workflow-system/agent/SKILL.md").read_text()
    human_root = project_root / "workflow-system/human"
    en_quickstart = (human_root / "en/quickstart.md").read_text()
    zh_quickstart = (human_root / "zh/quickstart.md").read_text()
    en_integration = (human_root / "en/integration-guide.md").read_text()
    zh_integration = (human_root / "zh/integration-guide.md").read_text()

    for source in (readme, skill, en_quickstart, en_integration):
        assert re.search(r"excludes\s+`standalone`", source)
        assert "runs every curl target" not in source
    for source in (zh_quickstart, zh_integration):
        assert re.search(r"不包含\s+`standalone`", source)
        assert "运行全部 curl 目标" not in source

    assert "curl `update` scans supported host skill-copy locations only" in readme
    assert "scans supported host skill copies only" in skill
    assert "curl `update` scans supported host skill-copy locations" in en_integration
    assert "curl `update` 只扫描受支持的宿主 skill" in zh_integration
    for source in (readme, en_quickstart, en_integration):
        assert "bash -s local" in source
        assert "bash -s standalone" in source
    for source in (zh_quickstart, zh_integration):
        assert "bash -s local" in source
        assert "bash -s standalone" in source


def test_readme_workflow_type_count(project_root: Path):
    """README seed table must match the registry-v3 seed universe exactly."""
    readme = (project_root / "README.md").read_text()

    section_match = re.search(
        r"(?:### |\*\*|^)\d+ Non-Executable Checklist Seeds \+ One Runtime"
        r"(?:\*\*)?\n(.*?)(?=\n### |\n## |\Z)",
        readme,
        re.DOTALL | re.MULTILINE,
    )
    assert section_match, "Could not find current checklist-seed section in README"
    section = section_match.group(1)
    documented = set(re.findall(r"^\|\s*`([^`]+)`\s*\|", section, re.MULTILINE))
    registered = _registry_template_names(project_root)
    assert documented == registered, (
        f"README seed table drifted — missing: {sorted(registered - documented)}, "
        f"extra: {sorted(documented - registered)}"
    )


def test_readme_template_count_in_dev_setup(project_root: Path):
    """Dev setup must claim the current seed count and sole runtime."""
    readme = (project_root / "README.md").read_text()
    templates_root = project_root / "workflow-system" / "agent" / "templates"

    section_match = re.search(
        r"(?:### |\*\*|^)Full Development Setup(?:\*\*)?\n(.*?)(?=\n## |\n### |\Z)",
        readme,
        re.DOTALL | re.MULTILINE,
    )
    assert section_match, "Could not find 'Full Development Setup' section in README"
    section = section_match.group(1)
    match = re.search(r"(\d+)\s+non-executable seeds", section)
    assert match, "Could not find non-executable seed count in dev setup section"
    claimed = int(match.group(1))
    registered = _registry_template_names(project_root)
    disk_seeds = {path.stem for path in (templates_root / "seeds").glob("*.yaml")}
    assert claimed == len(registered) == len(disk_seeds), (
        f"README claims {claimed} seeds; registry has {len(registered)} and "
        f"disk has {len(disk_seeds)}"
    )
    assert registered == disk_seeds
    assert "sole runtime" in section


def test_readme_links_design_docs_without_brittle_count(project_root: Path):
    """README points to the design index without freezing a volatile count."""
    readme = (project_root / "README.md").read_text()
    assert "[Design documents](docs/designs/)" in readme
    assert not re.search(r"\d+\s+design\s+(?:documents?|specs?)", readme, re.IGNORECASE)


def test_design_index_classifies_current_and_historical_documents(project_root: Path):
    """Every design-directory document is classified without blurring runtime truth."""
    design_root = project_root / "docs" / "designs"
    index = (design_root / "README.md").read_text()
    current, historical = index.split("## Historical Design and Research", 1)
    current = current.split("## Current Operational Design", 1)[1]

    local_link = re.compile(r"\]\(([a-z0-9_]+\.md)\)")
    current_documents = set(local_link.findall(current))
    historical_documents = set(local_link.findall(historical))
    disk_documents = {path.name for path in design_root.glob("*.md")} - {"README.md"}

    assert current_documents == {"design_release_workflow.md"}
    assert historical_documents == disk_documents - current_documents
    assert not current_documents & historical_documents
    assert "not runtime instructions" in index
    for normative_path in (
        "../../workflow-system/agent/SKILL.md",
        "../../workflow-system/agent/references/agent-hierarchy.md",
        "../../workflow-system/agent/references/execution-protocol.md",
        "../../workflow-system/agent/references/meta-framework.md",
        "../../schemas/",
        "../../src/devolaflow/",
    ):
        assert normative_path in current


def test_superseded_designs_banner_current_checklist_round_contract(project_root: Path):
    """Retired architecture designs lead with a current-contract warning."""
    design_root = project_root / "docs" / "designs"
    superseded = (
        "workflow_specification.md",
        "design_agent_hierarchy.md",
        "design_meta_framework.md",
        "design_delivery_architecture.md",
        "design_dual_system.md",
        "design_decomposition_gate.md",
        "design_execution_protocol.md",
        "design_repo_modes.md",
    )
    current_links = (
        "../../workflow-system/agent/SKILL.md",
        "../../workflow-system/agent/references/agent-hierarchy.md",
        "../../workflow-system/agent/references/execution-protocol.md",
        "../../workflow-system/agent/references/meta-framework.md",
        "../../schemas/",
        "../../src/devolaflow/",
    )

    for filename in superseded:
        source = (design_root / filename).read_text()
        leading_lines = source.splitlines()[:12]
        leading = "\n".join(leading_lines)
        normalized_leading = leading.replace("\n> ", " ")
        assert leading_lines[2] == "> [!WARNING]", f"{filename} warning is not prominent"
        assert "**Historical design — superseded before v16.**" in normalized_leading
        assert "preserves rationale and evolution evidence" in normalized_leading
        assert "not a runtime instruction" in normalized_leading
        assert "current three-layer Project → Wave → Task" in normalized_leading
        assert "checklist-round contracts" in normalized_leading
        for link in current_links:
            assert link in leading, f"{filename} banner does not link {link}"

    for filename in ("workflow_specification.md", "design_meta_framework.md"):
        source = (design_root / filename).read_text()
        assert "> **Status**: Historical / Superseded" in source
        assert "authoritative reference" not in source.casefold()


def test_workflow_skill_yaml_template_count(project_root: Path):
    """workflow-skill.yaml must expose all seeds and the sole runtime."""
    import yaml

    skill_yaml_path = project_root / "workflow-system" / "agent" / "workflow-skill.yaml"
    payload = yaml.safe_load(skill_yaml_path.read_text())
    templates = payload["content"]["templates"]
    declared_seeds = {entry["id"]: entry["file"] for entry in templates["seeds"]}
    registered = _registry_template_names(project_root)
    disk_seeds = {
        path.stem
        for path in (project_root / "workflow-system/agent/templates/seeds").glob("*.yaml")
    }

    assert set(declared_seeds) == registered == disk_seeds
    assert set(declared_seeds.values()) == {f"templates/seeds/{name}.yaml" for name in registered}
    runtime = templates["runtime"]
    assert runtime["id"] == "change-driven"
    assert runtime["file"] == "templates/builtin/change-driven.yaml"
    assert "sole executable" in runtime["description"].lower()


def test_registry_template_count(project_root: Path):
    """Registry-v3 entries must map 1:1 to seeds and one runtime path."""
    import yaml

    raw = yaml.safe_load(
        (project_root / "workflow-system" / "agent" / "templates" / "registry.yaml").read_text()
    )
    templates_root = project_root / "workflow-system" / "agent" / "templates"
    entries = (raw.get("compositions") or []) + (raw.get("templates") or [])
    registry_names = {entry["name"] for entry in entries}
    disk_seeds = {path.stem for path in (templates_root / "seeds").glob("*.yaml")}
    seed_paths = {entry["seed"] for entry in entries}
    runtime_entries = [entry for entry in entries if "path" in entry]
    disk_runtimes = {path.name for path in (templates_root / "builtin").glob("*.yaml")}

    assert raw["schema_version"] == "3.0"
    assert len(entries) == len(registry_names) == 26
    assert registry_names == disk_seeds
    assert seed_paths == {f"seeds/{name}.yaml" for name in registry_names}
    assert runtime_entries == [
        next(entry for entry in raw["templates"] if entry["name"] == "change-driven")
    ]
    assert runtime_entries[0]["path"] == "builtin/change-driven.yaml"
    assert disk_runtimes == {"change-driven.yaml"}


def test_demo_seed_catalogs_match_registry(project_root: Path):
    """Demo routes must consume the generated registry catalog, not duplicate it."""
    registered = _registry_template_names(project_root)
    demo_root = project_root / "workflow-system" / "human" / "demo"

    home_text = (demo_root / "index.html").read_text(encoding="utf-8")
    generated_text = (demo_root / "shared" / "seed-catalog.js").read_text(encoding="utf-8")
    seed_library_text = (demo_root / "workflow-visualizer" / "visualizer.js").read_text(
        encoding="utf-8"
    )
    explorer_text = (demo_root / "stage-explorer" / "explorer.js").read_text(encoding="utf-8")
    generated_names = set(re.findall(r'^\s{6}"name": "([^"]+)",$', generated_text, re.MULTILINE))

    assert len(registered) == 26
    assert generated_names == registered
    assert "window.DEVOLAFLOW_SEED_CATALOG" in home_text
    assert "window.DEVOLAFLOW_SEED_CATALOG" in seed_library_text
    assert "window.DEVOLAFLOW_SEED_CATALOG" in explorer_text
    assert not re.search(r"<li><code>[a-z0-9-]+</code></li>", home_text)
    assert "const SEEDS = [" not in seed_library_text
    assert not re.search(r"\bseeds\s*:\s*\[", explorer_text)


def test_demo_pages_load_shared_assets(project_root: Path):
    """Every demo HTML entry point must load shared assets at its route depth."""
    demo_root = project_root / "workflow-system" / "human" / "demo"
    favicon_path = demo_root / "shared" / "favicon.svg"
    favicon = favicon_path.read_text(encoding="utf-8")
    assert "<svg" in favicon
    assert {"#B8860B", "#9B4444", "DevolaFlow"} <= set(
        re.findall(r"#[A-Fa-f0-9]{6}|DevolaFlow", favicon)
    )

    for page_path in sorted(demo_root.rglob("index.html")):
        source = page_path.read_text(encoding="utf-8")
        relative_path = page_path.relative_to(demo_root)
        for asset in ("styles.css", "i18n.js", "nav.js"):
            pattern = rf'(?:href|src)="(?:\.\./)*shared/{re.escape(asset)}"'
            assert re.search(pattern, source), f"{relative_path} does not load shared/{asset}"
        route_prefix = "../" * len(relative_path.parent.parts)
        favicon_link = (
            f'<link rel="icon" type="image/svg+xml" href="{route_prefix}shared/favicon.svg">'
        )
        assert source.count(favicon_link) == 1, (
            f"{relative_path} must load shared/favicon.svg with route prefix {route_prefix!r}"
        )


def test_demo_shared_css_excludes_orphans_and_harness_css_is_external(project_root: Path):
    """Managed zero-reference families stay absent and Harness owns its CSS."""
    demo_root = project_root / "workflow-system" / "human" / "demo"
    shared_css = (demo_root / "shared/styles.css").read_text(encoding="utf-8")
    orphan_families = (
        "gate-badge",
        "wave-strip",
        "task-dot",
        "metric-micro",
        "dispatch-dot",
        "cf-aside",
        "era-filter",
        "tl-card",
        "tl-rail",
        "tl-dot",
        "tl-expand",
    )
    present = [selector for selector in orphan_families if selector in shared_css]
    assert not present, f"shared/styles.css retains orphan selector families: {present}"

    harness_html = (demo_root / "benchmark-results/index.html").read_text(encoding="utf-8")
    harness_css = demo_root / "benchmark-results/styles.css"
    shared_link = harness_html.index('href="../shared/styles.css"')
    page_link = harness_html.index('href="styles.css"')
    assert shared_link < page_link
    assert "<style" not in harness_html
    assert harness_css.is_file()
    assert ".harness-version" in harness_css.read_text(encoding="utf-8")


def test_harness_page_pins_dimensions_verdicts_and_version_source(project_root: Path):
    """Harness documents six dimensions, explicit verdicts, and Timeline version derivation."""
    harness_path = (
        project_root / "workflow-system" / "human" / "demo" / "benchmark-results" / "index.html"
    )
    source = harness_path.read_text(encoding="utf-8")

    dimension_keys = set(re.findall(r'<h3 data-i18n="(harness\.dimension[A-Z][A-Za-z]+)">', source))
    assert dimension_keys == {
        "harness.dimensionCode",
        "harness.dimensionArchitecture",
        "harness.dimensionTests",
        "harness.dimensionMaintainability",
        "harness.dimensionCompatibility",
        "harness.dimensionPerformance",
    }
    assert set(re.findall(r"<h3><code>(READY|NOT_READY|INSUFFICIENT)</code></h3>", source)) == {
        "READY",
        "NOT_READY",
        "INSUFFICIENT",
    }
    assert "fetch('../version-timeline/versions.json'" in source
    assert "versionElement.textContent = 'v' + newest.version" in source
    assert "STATIC FALLBACK" in source


def test_active_demo_copy_excludes_precise_retired_claims(project_root: Path):
    """Current pages reject obsolete claims while Timeline and Blog retain history."""
    demo_root = project_root / "workflow-system" / "human" / "demo"
    obsolete_phrases = (
        "EvoBench Results",
        "Project Agent (dispatches stages)",
        "17 Workflow Templates",
        "22 workflow types",
        "13 stage primitives",
        "NineS evaluator",
        "NineS plugin",
        "fixed Stage DAG",
        "ordered stage pipeline",
        "L3 Task Agent",
        "composite score is the gate",
    )
    active_sources = sorted((*demo_root.rglob("*.html"), *demo_root.rglob("*.js")))
    for source_path in active_sources:
        relative_path = source_path.relative_to(demo_root)
        if relative_path.parts[0] in {"version-timeline", "blog"}:
            continue
        source = source_path.read_text(encoding="utf-8").casefold()
        stale = [phrase for phrase in obsolete_phrases if phrase.casefold() in source]
        assert not stale, f"{relative_path} contains obsolete active-copy phrases: {stale}"


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


def test_bump_version_locations_match_seven_sync_locations_across_eight_files(
    project_root: Path,
):
    """README describes distinct files, not the script's replacement-pattern count."""
    bump_script = (project_root / "scripts" / "bump_version.py").read_text()
    readme = (project_root / "README.md").read_text()

    paths = set(re.findall(r'"path":\s*"([^"]+)"', bump_script))
    source = "src/devolaflow/__init__.py"
    assert source in paths
    assert len(paths) == 8
    assert len(paths - {source}) == 7
    assert "Seven canonical sync\nlocations across eight files" in readme
    assert not re.search(r"all\s+\d+\s+version\s+locations?", readme)


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

    # v16 introduced "advisory" as a constraint-tier term, so the stale-name
    # ban targets gate-type phrasing only, not the bare words.
    for stale in ("advisory gate", "automated gate", "gate: advisory", "gate: automated"):
        assert stale not in demo_index, (
            f"demo/index.html still references stale gate type phrasing '{stale}'"
        )


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
