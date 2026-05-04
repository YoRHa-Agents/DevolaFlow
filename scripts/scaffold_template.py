#!/usr/bin/env python3
"""Scaffold a new DevolaFlow workflow template across all 9 SF surfaces.

Per `.local/research/v11.0.0_patches/D-X-1.md` §2 algorithm. Adding a new
template historically required editing 9 distinct surfaces by hand:

    1. workflow-system/agent/templates/builtin/<name>.yaml
    2. workflow-system/agent/templates/registry.yaml stanza
    3. workflow-system/agent/references/meta-framework.md §4 alias rows
    4. workflow-system/agent/SKILL.md "Template Quick-Reference" row
    5. workflow-system/agent/references/team-roles.md §7 matrix row
    6. tests/test_<name>_template.py
    7. make build-skill (verifier; not authored)
    8. tests/test_no_ghost_features.py W-18 lint stanza
    9. CHANGELOG.md `## [vX.Y.Z]` entry

This CLI collapses surfaces 1–6 into a single invocation. Surfaces 8 + 9
are printed to stdout as paste-ready stanzas (NOT auto-injected — per the
D-X-1 R2 mitigation, fail-loud rather than silently mis-inject adjacent
edits the operator may have queued).

Usage:
    python scripts/scaffold_template.py <name> \\
        --primitives analyze,implement,test \\
        --category build \\
        --tags refactor,improve

    python scripts/scaffold_template.py <name> ... --dry-run    # preview only
    python scripts/scaffold_template.py <name> ... --force      # overwrite
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

VALID_PRIMITIVES = frozenset(
    {
        "research",
        "analyze",
        "design",
        "plan",
        "implement",
        "refine",
        "review",
        "test",
        "validate",
        "verify",
        "release",
        "deploy",
        "monitor",
        "gate",
    }
)
VALID_CATEGORIES = frozenset({"discover", "shape", "build", "verify", "deliver", "composite"})
DEFAULT_DURATION_CLASS = "medium"
TEMPLATE_NAME_RE = re.compile(r"^[a-z][a-z0-9-]*$")


@dataclass(frozen=True)
class ScaffoldPlan:
    """Resolved inputs + computed paths for one scaffold invocation."""

    name: str
    primitives: tuple[str, ...]
    category: str
    tags: tuple[str, ...]
    repo_root: Path
    builtin_yaml: Path
    registry_yaml: Path
    meta_framework_md: Path
    skill_md: Path
    team_roles_md: Path
    test_file: Path

    @property
    def display_name(self) -> str:
        return self.name.replace("-", " ").title()


def resolve_repo_root(start: Path | None = None) -> Path:
    """Walk upward from *start* until a ``pyproject.toml`` is found."""
    p = (start or Path(__file__)).resolve()
    if p.is_file():
        p = p.parent
    while p != p.parent:
        if (p / "pyproject.toml").exists():
            return p
        p = p.parent
    raise SystemExit("could not locate repo root (no pyproject.toml found)")


def build_plan(
    name: str,
    primitives: list[str],
    category: str,
    tags: list[str],
    *,
    repo_root: Path,
) -> ScaffoldPlan:
    if not TEMPLATE_NAME_RE.match(name):
        raise SystemExit(f"invalid template name {name!r}: must match {TEMPLATE_NAME_RE.pattern}")
    if category not in VALID_CATEGORIES:
        raise SystemExit(f"invalid category {category!r}: choose from {sorted(VALID_CATEGORIES)}")
    bad = [p for p in primitives if p not in VALID_PRIMITIVES]
    if bad:
        raise SystemExit(f"unknown primitive(s) {bad}: choose from {sorted(VALID_PRIMITIVES)}")
    if not primitives:
        raise SystemExit("--primitives must list at least one primitive")
    return ScaffoldPlan(
        name=name,
        primitives=tuple(primitives),
        category=category,
        tags=tuple(tags),
        repo_root=repo_root,
        builtin_yaml=repo_root / "workflow-system/agent/templates/builtin" / f"{name}.yaml",
        registry_yaml=repo_root / "workflow-system/agent/templates/registry.yaml",
        meta_framework_md=repo_root / "workflow-system/agent/references/meta-framework.md",
        skill_md=repo_root / "workflow-system/agent/SKILL.md",
        team_roles_md=repo_root / "workflow-system/agent/references/team-roles.md",
        test_file=repo_root / "tests" / f"test_{name.replace('-', '_')}_template.py",
    )


def render_builtin_yaml(plan: ScaffoldPlan) -> str:
    """Render a stage-by-stage skeleton with sequential composition."""
    lines = [
        'schema_version: "1.0"',
        "",
        "metadata:",
        f"  name: {plan.name}",
        '  version: "1.0.0"',
        f'  display_name: "{plan.display_name}"',
        f'  description: "TODO: review composition — {plan.name} workflow"',
        f"  category: {plan.category}",
        "  applicable_scenarios:",
        f'    - "TODO: describe scenario for {plan.name}"',
        f"  tags: [{', '.join(plan.tags) if plan.tags else plan.name}]",
        "",
        "stages:",
    ]
    for prim in plan.primitives:
        lines.extend(
            [
                f"  - id: {prim}",
                f"    primitive: {prim}",
                f'    description: "TODO: review composition — {prim} stage"',
                "    team: implement",
                f"    duration_class: {DEFAULT_DURATION_CLASS}",
            ]
        )
    lines.extend(
        [
            "",
            "composition:",
            "  compose: sequence",
            "  stages:",
        ]
    )
    for prim in plan.primitives:
        lines.append(f"    - stage: {prim}")
    lines.append("")
    return "\n".join(lines)


def render_registry_stanza(plan: ScaffoldPlan) -> str:
    tags = list(plan.tags) if plan.tags else [plan.name]
    return "\n".join(
        [
            f"  - name: {plan.name}",
            f"    path: builtin/{plan.name}.yaml",
            "    source: builtin",
            '    version: "1.0.0"',
            f"    category: {plan.category}",
            f"    tags: [{', '.join(tags)}]",
            "",
        ]
    )


def render_test_file(plan: ScaffoldPlan) -> str:
    """Skeleton test that loads the yaml and asserts the contracted shape."""
    return f'''"""Schema regression for the ``{plan.name}`` builtin workflow template."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = REPO_ROOT / "workflow-system/agent/templates/builtin/{plan.name}.yaml"


@pytest.fixture(scope="module")
def template() -> dict:
    assert TEMPLATE_PATH.is_file(), f"missing template: {{TEMPLATE_PATH}}"
    with TEMPLATE_PATH.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def test_schema_version_pinned(template: dict) -> None:
    assert template["schema_version"] == "1.0"


def test_metadata_name_matches_filename(template: dict) -> None:
    assert template["metadata"]["name"] == "{plan.name}"


def test_metadata_category_valid(template: dict) -> None:
    assert template["metadata"]["category"] == "{plan.category}"


def test_stages_match_primitives(template: dict) -> None:
    primitives = [s["primitive"] for s in template["stages"]]
    assert primitives == {list(plan.primitives)!r}


def test_composition_is_sequence(template: dict) -> None:
    assert template["composition"]["compose"] == "sequence"
'''


def append_unique(target: Path, marker: str, payload: str, *, force: bool = False) -> bool:
    """Append *payload* to *target* if *marker* is absent. Returns True on write."""
    if not target.is_file():
        raise SystemExit(f"missing canonical file: {target}")
    text = target.read_text(encoding="utf-8")
    if marker in text and not force:
        return False
    if not text.endswith("\n"):
        text = text + "\n"
    target.write_text(text + payload, encoding="utf-8")
    return True


def insert_meta_framework_row(plan: ScaffoldPlan, *, force: bool = False) -> bool:
    """Insert one alias-mapping row per primitive into meta-framework.md §4."""
    text = plan.meta_framework_md.read_text(encoding="utf-8")
    marker = f"| {plan.primitives[0]} | {plan.primitives[0]} | {plan.name} |"
    if marker in text and not force:
        return False
    new_rows = "\n".join(f"| {p} | {p} | {plan.name} |" for p in plan.primitives)
    end_token = "**Composition operators**"
    if end_token not in text:
        text = text.rstrip("\n") + "\n" + new_rows + "\n"
    else:
        text = text.replace(end_token, new_rows + "\n\n" + end_token, 1)
    plan.meta_framework_md.write_text(text, encoding="utf-8")
    return True


def insert_skill_md_row(plan: ScaffoldPlan, *, force: bool = False) -> bool:
    """Append a row to SKILL.md "Template Quick-Reference" table."""
    text = plan.skill_md.read_text(encoding="utf-8")
    row_marker = f"| {plan.name} |"
    if row_marker in text and not force:
        return False
    new_row = f"| {plan.name} | {len(plan.primitives)} | standard |"
    section = "## Template Quick-Reference"
    idx = text.find(section)
    if idx < 0:
        text = text.rstrip("\n") + "\n" + new_row + "\n"
        plan.skill_md.write_text(text, encoding="utf-8")
        return True
    after = text.find("\n\n", idx)
    insert_at = after if after > 0 else len(text)
    text = text[:insert_at].rstrip("\n") + "\n" + new_row + text[insert_at:]
    plan.skill_md.write_text(text, encoding="utf-8")
    return True


def insert_team_roles_row(plan: ScaffoldPlan, *, force: bool = False) -> bool:
    """Append a row to team-roles.md §7 matrix using a derived participation."""
    text = plan.team_roles_md.read_text(encoding="utf-8")
    row_marker = f"| {plan.name} |"
    if row_marker in text and not force:
        return False
    has_research = "research" in plan.primitives or "analyze" in plan.primitives
    has_design = "design" in plan.primitives or "plan" in plan.primitives
    has_test = "test" in plan.primitives or "validate" in plan.primitives
    has_review = "review" in plan.primitives or "validate" in plan.primitives
    cells = [
        "Active" if has_research else "—",
        "Active" if has_design else "—",
        "**Primary**",
        "Active" if has_test else "—",
        "Active" if has_review else "—",
    ]
    new_row = f"| {plan.name} | " + " | ".join(cells) + " |"
    end_token = "**Primary** = drives the stage."
    if end_token not in text:
        text = text.rstrip("\n") + "\n" + new_row + "\n"
    else:
        text = text.replace(end_token, new_row + "\n\n" + end_token, 1)
    plan.team_roles_md.write_text(text, encoding="utf-8")
    return True


def write_files(plan: ScaffoldPlan, *, force: bool = False) -> dict[str, str]:
    """Run all 6 surfaces; return a name -> action mapping."""
    actions: dict[str, str] = {}
    if plan.builtin_yaml.exists() and not force:
        actions[str(plan.builtin_yaml)] = "skipped (exists; use --force to overwrite)"
    else:
        plan.builtin_yaml.parent.mkdir(parents=True, exist_ok=True)
        plan.builtin_yaml.write_text(render_builtin_yaml(plan), encoding="utf-8")
        actions[str(plan.builtin_yaml)] = "created"
    actions[str(plan.registry_yaml)] = (
        "appended"
        if append_unique(
            plan.registry_yaml,
            f"name: {plan.name}",
            render_registry_stanza(plan),
            force=force,
        )
        else "skipped (already present)"
    )
    actions[str(plan.meta_framework_md)] = (
        "row inserted"
        if insert_meta_framework_row(plan, force=force)
        else "skipped (already present)"
    )
    actions[str(plan.skill_md)] = (
        "row inserted" if insert_skill_md_row(plan, force=force) else "skipped (already present)"
    )
    actions[str(plan.team_roles_md)] = (
        "row inserted" if insert_team_roles_row(plan, force=force) else "skipped (already present)"
    )
    if plan.test_file.exists() and not force:
        actions[str(plan.test_file)] = "skipped (exists; use --force to overwrite)"
    else:
        plan.test_file.write_text(render_test_file(plan), encoding="utf-8")
        actions[str(plan.test_file)] = "created"
    return actions


def render_w18_stanza(plan: ScaffoldPlan) -> str:
    safe = plan.name.replace("-", "_")
    return f"""
# === paste below into tests/test_no_ghost_features.py ===
def test_template_{safe}_present(project_root):
    \"\"\"W-18: scaffolded template `{plan.name}` is registered.\"\"\"
    yaml_path = project_root / "workflow-system/agent/templates/builtin/{plan.name}.yaml"
    registry = project_root / "workflow-system/agent/templates/registry.yaml"
    assert yaml_path.is_file(), f"template missing: {{yaml_path}}"
    assert "name: {plan.name}" in registry.read_text(encoding="utf-8")
"""


def render_changelog_stanza(plan: ScaffoldPlan) -> str:
    primitives_csv = ", ".join(plan.primitives)
    return f"""
# === paste under CHANGELOG.md ## [vX.Y.Z] ===
- **NEW workflow template `{plan.name}`** ({plan.category};
  primitives: {primitives_csv}).
  Generated by `scripts/scaffold_template.py` per D-X-1.
  TODO: review composition + AC.
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", help="template basename (lowercase-kebab)")
    parser.add_argument(
        "--primitives",
        required=True,
        help="comma-separated primitives composing the template",
    )
    parser.add_argument("--category", default="build", help="registry category")
    parser.add_argument("--tags", default="", help="comma-separated tags")
    parser.add_argument("--dry-run", action="store_true", help="preview without writes")
    parser.add_argument("--force", action="store_true", help="overwrite existing surfaces")
    parser.add_argument("--repo-root", type=Path, default=None)
    args = parser.parse_args(argv)

    primitives = [p.strip() for p in args.primitives.split(",") if p.strip()]
    tags = [t.strip() for t in args.tags.split(",") if t.strip()]
    repo_root = args.repo_root or resolve_repo_root()
    plan = build_plan(args.name, primitives, args.category, tags, repo_root=repo_root)

    if args.dry_run:
        print(f"[dry-run] would scaffold template '{plan.name}' under {repo_root}")
        print("\n--- builtin yaml preview ---")
        print(render_builtin_yaml(plan))
        print("\n--- registry stanza preview ---")
        print(render_registry_stanza(plan))
        print("\n--- test file preview ---")
        print(render_test_file(plan)[:500] + "\n... (truncated)")
        print(render_w18_stanza(plan))
        print(render_changelog_stanza(plan))
        return 0

    actions = write_files(plan, force=args.force)
    rel = lambda p: str(Path(p).relative_to(repo_root))  # noqa: E731
    print(f"[scaffold-template] wrote/touched {len(actions)} surface(s) for '{plan.name}':")
    for path, status in actions.items():
        print(f"  - {rel(path):<70s} {status}")
    print(render_w18_stanza(plan))
    print(render_changelog_stanza(plan))
    print(
        "[scaffold-template] NEXT STEPS:\n"
        "  1) Review the generated yaml + adjust stage descriptions / configs.\n"
        "  2) Paste the W-18 stanza above into tests/test_no_ghost_features.py.\n"
        "  3) Paste the CHANGELOG stanza above into CHANGELOG.md under your PV header.\n"
        "  4) Run `make validate-templates && make build-skill` before committing."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
