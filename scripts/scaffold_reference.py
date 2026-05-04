#!/usr/bin/env python3
"""Scaffold a new agent reference doc across the canonical SF-3 surface.

Per `.local/research/v11.0.0_patches/D-X-2.md` §2 algorithm. Adding a new
reference historically required editing 7 surfaces by hand:

    1. workflow-system/agent/references/<name>.md
    2. workflow-system/agent/SKILL.md "## Reference Navigation Guide" row
    3. scripts/sync_cursor_skill.py::MIRRORED_FILES (the canonical 14+
       reference list mirrored to .cursor/skills/devola-flow/)
    4. tests/test_reference_size_budgets.py (auto-covered via parametrize)
    5. tests/test_integration.py (SKILL.md <500-line check; auto)
    6. tests/test_no_ghost_features.py W-18 lint stanza
    7. make sync-cursor-skill (verifier; not authored)

This CLI collapses 1 + 2 + 3 into a single invocation; surface 6 is
printed to stdout as a paste-ready stanza.

Usage:
    python scripts/scaffold_reference.py <name> \\
        --tier large \\
        --load-when "<short trigger description for SKILL.md>"

    python scripts/scaffold_reference.py <name> ... --dry-run
    python scripts/scaffold_reference.py <name> ... --force
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

VALID_TIERS = frozenset({"default", "large", "xl"})
REFERENCE_NAME_RE = re.compile(r"^[a-z][a-z0-9-]*$")


@dataclass(frozen=True)
class ReferencePlan:
    name: str
    tier: str
    load_when: str
    repo_root: Path
    reference_md: Path
    skill_md: Path
    sync_script: Path

    @property
    def relative_reference(self) -> str:
        return f"references/{self.name}.md"


def resolve_repo_root(start: Path | None = None) -> Path:
    p = (start or Path(__file__)).resolve()
    if p.is_file():
        p = p.parent
    while p != p.parent:
        if (p / "pyproject.toml").exists():
            return p
        p = p.parent
    raise SystemExit("could not locate repo root (no pyproject.toml found)")


def build_plan(name: str, tier: str, load_when: str, *, repo_root: Path) -> ReferencePlan:
    if not REFERENCE_NAME_RE.match(name):
        raise SystemExit(f"invalid reference name {name!r}: must match {REFERENCE_NAME_RE.pattern}")
    if tier not in VALID_TIERS:
        raise SystemExit(f"invalid tier {tier!r}: choose from {sorted(VALID_TIERS)}")
    return ReferencePlan(
        name=name,
        tier=tier,
        load_when=load_when.strip() or "TODO: describe trigger",
        repo_root=repo_root,
        reference_md=repo_root / "workflow-system/agent/references" / f"{name}.md",
        skill_md=repo_root / "workflow-system/agent/SKILL.md",
        sync_script=repo_root / "scripts/sync_cursor_skill.py",
    )


def render_reference_md(plan: ReferencePlan) -> str:
    """5-section skeleton: Purpose / When to Load / Body / Cross-Refs / History."""
    title = plan.name.replace("-", " ").title()
    return f"""# {title}

## Purpose

TODO: 1-3 sentences describing what this reference covers and the
canonical artifacts it pairs with (Python module, schema, YAML config).

## When to Load

Load this reference when {plan.load_when}.

## Body

TODO: replace with the substantive content. Suggested sub-sections:

### 1. Concept Overview

TODO: explain the abstraction this reference documents.

### 2. Canonical Surfaces

TODO: list the source-of-truth files the reference cites.

### 3. Worked Examples

TODO: 2-3 concrete examples or recipes.

## Cross-References

- `references/meta-framework.md` — workflow primitives
- `references/agent-hierarchy.md` — L0/L1/L2/L3 layering

## History

- Scaffolded by `scripts/scaffold_reference.py` (D-X-2).
- TODO: add cycle entry once the reference's first substantive content lands.
"""


def insert_skill_row(plan: ReferencePlan, *, force: bool = False) -> bool:
    """Insert one row into SKILL.md "Reference Navigation Guide" Tier-2 table.

    Insertion preserves alphabetical order over existing rows. If a row
    already references this name (and ``force`` is not set), no write
    happens — the function is idempotent.
    """
    text = plan.skill_md.read_text(encoding="utf-8")
    needle = f"| `references/{plan.name}.md` |"
    if needle in text and not force:
        return False
    new_row = f"| `references/{plan.name}.md` | {plan.load_when} |"
    lines = text.splitlines()
    table_start = -1
    for i, ln in enumerate(lines):
        if ln.startswith("| `references/") and "Load When" not in ln:
            table_start = i
            break
    if table_start < 0:
        plan.skill_md.write_text(text.rstrip("\n") + "\n" + new_row + "\n", encoding="utf-8")
        return True
    table_end = table_start
    while table_end < len(lines) and lines[table_end].startswith("| `references/"):
        table_end += 1
    block = lines[table_start:table_end] + [new_row]
    block.sort(key=lambda ln: ln.lower())
    new_lines = lines[:table_start] + block + lines[table_end:]
    plan.skill_md.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    return True


def append_mirrored_files(plan: ReferencePlan, *, force: bool = False) -> bool:
    """Append `references/<name>.md` to MIRRORED_FILES in sync_cursor_skill.py."""
    text = plan.sync_script.read_text(encoding="utf-8")
    entry = f'    "references/{plan.name}.md",'
    if f'"references/{plan.name}.md"' in text and not force:
        return False
    examples_anchor = '    "examples/full-pipeline-trace.md",'
    if examples_anchor not in text:
        raise SystemExit(
            f"{plan.sync_script}: missing anchor {examples_anchor!r} — refusing to mutate"
        )
    new_text = text.replace(examples_anchor, entry + "\n" + examples_anchor, 1)
    plan.sync_script.write_text(new_text, encoding="utf-8")
    return True


def write_files(plan: ReferencePlan, *, force: bool = False) -> dict[str, str]:
    actions: dict[str, str] = {}
    if plan.reference_md.exists() and not force:
        actions[str(plan.reference_md)] = "skipped (exists; use --force to overwrite)"
    else:
        plan.reference_md.parent.mkdir(parents=True, exist_ok=True)
        plan.reference_md.write_text(render_reference_md(plan), encoding="utf-8")
        actions[str(plan.reference_md)] = "created"
    actions[str(plan.skill_md)] = (
        "row inserted" if insert_skill_row(plan, force=force) else "skipped (already present)"
    )
    actions[str(plan.sync_script)] = (
        "MIRRORED_FILES appended"
        if append_mirrored_files(plan, force=force)
        else "skipped (already present)"
    )
    return actions


def render_w18_stanza(plan: ReferencePlan) -> str:
    safe = plan.name.replace("-", "_")
    return f"""
# === paste into tests/test_no_ghost_features.py ===
def test_reference_{safe}_present(project_root):
    \"\"\"W-18: scaffolded reference `{plan.name}.md` is registered.\"\"\"
    ref_path = project_root / "workflow-system/agent/references/{plan.name}.md"
    skill = (project_root / "workflow-system/agent/SKILL.md").read_text(encoding="utf-8")
    assert ref_path.is_file(), f"reference missing: {{ref_path}}"
    assert "references/{plan.name}.md" in skill
"""


def render_changelog_stanza(plan: ReferencePlan) -> str:
    return f"""
# === paste under CHANGELOG.md ## [vX.Y.Z] ===
- **NEW reference `references/{plan.name}.md`** ({plan.tier} tier).
  Generated by `scripts/scaffold_reference.py` per D-X-2. TODO: author body.
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", help="reference basename without .md (lowercase-kebab)")
    parser.add_argument("--tier", default="large", help="size tier: default | large | xl")
    parser.add_argument(
        "--load-when",
        default="",
        help="short load-trigger description for SKILL.md table",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--repo-root", type=Path, default=None)
    args = parser.parse_args(argv)

    repo_root = args.repo_root or resolve_repo_root()
    plan = build_plan(args.name, args.tier, args.load_when, repo_root=repo_root)

    if args.dry_run:
        print(f"[dry-run] would scaffold reference '{plan.name}' under {repo_root}")
        print("\n--- reference body preview ---")
        print(render_reference_md(plan))
        print(render_w18_stanza(plan))
        print(render_changelog_stanza(plan))
        return 0

    actions = write_files(plan, force=args.force)
    rel = lambda p: str(Path(p).relative_to(repo_root))  # noqa: E731
    print(f"[scaffold-reference] wrote/touched {len(actions)} surface(s) for '{plan.name}':")
    for path, status in actions.items():
        print(f"  - {rel(path):<60s} {status}")
    print(render_w18_stanza(plan))
    print(render_changelog_stanza(plan))
    print(
        "[scaffold-reference] NEXT STEPS:\n"
        "  1) Author the reference body (the skeleton has TODOs marked).\n"
        "  2) Update `tests/test_no_ghost_features.py::_SF4_REFERENCE_SET` and\n"
        "     bump cardinality counts if you advance the SF-1 cap.\n"
        "  3) Paste the W-18 + CHANGELOG stanzas above.\n"
        "  4) Run `make sync-cursor-skill && "
        "python -m pytest tests/test_reference_size_budgets.py`."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
