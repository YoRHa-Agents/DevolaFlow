#!/usr/bin/env python3
"""Audit which builtin workflow templates are actually USED in cycle docs.

This script implements the v10.5.0 PV-02 D-A-2 Phase A deliverable per
`.local/research/v11.0.0_patches/D-A-2.md` §2 Phase A. It answers:
**of the builtin templates registered in
`workflow-system/agent/templates/builtin/*.yaml` (22 at the v10.3.0
audit corpus; 7 survivors since the v15.0.0 Phase B collapse per
v15-ADR-002), which were actually invoked as a cycle workflow vs which
exist only as registered placeholders?**

The audit's verdict is then surfaced in 3 places:

1. SKILL.md "Template Quick-Reference" table — TIER-2/3 names
   gain a ``(legacy)`` suffix.
2. `references/meta-framework.md` "Per-Workflow Template Catalog" —
   same ``(legacy)`` suffix.
3. `references/team-roles.md` "Team Participation Matrix" — same
   suffix on the workflow-type column.
4. The TIER-2/3 yaml files themselves — gain a comment block at the
   top: ``# DEPRECATED in v11.0.0; retained for backward compat —
   Phase B collapse decision lands v15.0.0 per v15-ADR-002``.

Phase B (compose-not-define collapse — replace TIER-2/3 yaml files
with parametrized invocations of TIER-1 templates) LANDED at v15.0.0
per v15-ADR-002: the 16 TIER-2 yamls were deleted and re-expressed as
named compositions in `templates/registry.yaml#compositions` (schema
v2.0). The baseline frozensets below are the FROZEN v10.3.0 audit
corpus (historical record), NOT a current-disk derivation —
:func:`scan_template_yamls` derives the live set from disk.

Algorithm (per PDS §2):

1. Read the 22 template yaml files from
   `workflow-system/agent/templates/builtin/`.
2. For each template name, count:
   - cycle-doc mentions: ``rg -c <name>`` across
     `.local/research/v9.*.0_*.md` + `v10.*.0_*.md`.
   - git-commit subj. mentions: ``git log --pretty=format:"%s"``
     filtered by the template name.
   - CHANGELOG mentions in workflow-execution context
     (``## [v...]`` block + name in body).
3. Classify into TIER-1 USED (cycle invocation evidenced) vs
   TIER-2 REGISTERED (defined but no v9.x-v10.x invocation).
4. Emit markdown report with the per-template verdict table.

Public API:

* :func:`scan_template_yamls(repo_root)` -> list[str]
* :func:`count_cycle_mentions(repo_root, name)` -> int
* :func:`count_changelog_mentions(repo_root, name)` -> int
* :func:`classify_template(repo_root, name)` -> str (USED|REGISTERED)
* :func:`render_markdown_report(verdicts)` -> str
* :func:`run(repo_root, *, json_out, output)` -> int

Entry point: ``python scripts/audit_template_usage.py [--repo-root .]
[--json] [--output PATH]``

Source: v10.5.0 PV-02 — codified per
`.local/research/v11.0.0_patches/D-A-2.md` §2.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

__all__ = [
    "TIER_1_USED_BASELINE",
    "TIER_2_LEGACY_BASELINE",
    "classify_template",
    "count_changelog_mentions",
    "count_cycle_mentions",
    "render_markdown_report",
    "run",
    "scan_compositions",
    "scan_template_yamls",
]


# Audit baseline from `.local/research/v11.0.0_patches/D-A-2.md` §1.
# These 6 templates are USED in cycle execution (cycle plan + commit
# subject + CHANGELOG mentions all > 0 across v9.0.0..v10.3.0). The
# remaining 16 are REGISTERED but never invoked as a cycle workflow.
# FROZEN historical pins (v10.3.0 corpus): since the v15.0.0 Phase B
# collapse (v15-ADR-002) the TIER-2 names live on only as compositions
# in templates/registry.yaml — do NOT re-derive these sets from disk.
TIER_1_USED_BASELINE: frozenset[str] = frozenset(
    {
        "change-driven",
        "self-update",
        "skill-optimization",
        "repo-init",
        "migration",
        "nines-assisted",
    }
)

# 16 TIER-2/3 templates per PDS §1.
TIER_2_LEGACY_BASELINE: frozenset[str] = frozenset(
    {
        "hotfix",
        "refactoring",
        "feature-enhancement",
        "full-pipeline",
        "documentation-only",
        "research-only",
        "design-only",
        "research-design-review-refine",
        "spike-poc",
        "security-audit",
        "demo-showcase",
        "performance-optimization",
        "dependency-setup",
        "onboarding",
        "product-verification",
        "entropy-cleanup",
    }
)


def scan_template_yamls(repo_root: Path) -> list[str]:
    """Return sorted list of template basenames under templates/builtin/.

    Args:
      repo_root: Repository root.

    Returns:
      Sorted list of template basenames (without ``.yaml`` extension).
      Empty list if ``workflow-system/agent/templates/builtin/`` does
      not exist (operator-friendly: no error on a fresh clone).
    """
    template_dir = repo_root / "workflow-system" / "agent" / "templates" / "builtin"
    if not template_dir.is_dir():
        return []
    return sorted(p.stem for p in template_dir.glob("*.yaml"))


def scan_compositions(repo_root: Path) -> list[str]:
    """Return sorted composition names from registry.yaml (schema v2.0).

    Since the v15.0.0 Phase B collapse (v15-ADR-002), the 16 former
    legacy workflow types live in the ``compositions:`` manifest of
    ``workflow-system/agent/templates/registry.yaml`` instead of as
    per-name yaml files. The audit walks them alongside the on-disk
    survivors so all registered workflow types stay auditable.

    Args:
      repo_root: Repository root.

    Returns:
      Sorted list of composition names. Empty list when the registry is
      absent or carries no ``compositions:`` block (pre-v2.0 layouts).
    """
    registry = repo_root / "workflow-system" / "agent" / "templates" / "registry.yaml"
    if not registry.is_file():
        return []
    import yaml

    raw = yaml.safe_load(registry.read_text(encoding="utf-8")) or {}
    return sorted(
        str(entry["name"])
        for entry in (raw.get("compositions") or [])
        if isinstance(entry, dict) and entry.get("name")
    )


def count_cycle_mentions(repo_root: Path, name: str) -> int:
    """Count occurrences of ``name`` across cycle plans + retros.

    Args:
      repo_root: Repository root.
      name: Template basename (e.g. ``"hotfix"``).

    Returns:
      Total mention count across `.local/research/v{9,10}.*.0_*.md`.
      Zero when the research dir is absent.
    """
    research = repo_root / ".local" / "research"
    if not research.is_dir():
        return 0
    pattern = re.compile(rf"\b{re.escape(name)}\b")
    total = 0
    for glob_pattern in (
        "v9.*.0_cycle_plan.md",
        "v9.*.0_retrospective.md",
        "v10.*.0_cycle_plan.md",
        "v10.*.0_retrospective.md",
    ):
        for doc in research.glob(glob_pattern):
            total += len(pattern.findall(doc.read_text(encoding="utf-8")))
    return total


def count_changelog_mentions(repo_root: Path, name: str) -> int:
    """Count occurrences of ``name`` in CHANGELOG.md (release entries).

    Args:
      repo_root: Repository root.
      name: Template basename.

    Returns:
      Count of mentions in `CHANGELOG.md`. Zero when the file is
      absent.
    """
    changelog = repo_root / "CHANGELOG.md"
    if not changelog.is_file():
        return 0
    text = changelog.read_text(encoding="utf-8")
    pattern = re.compile(rf"\b{re.escape(name)}\b")
    return len(pattern.findall(text))


def count_git_subject_mentions(repo_root: Path, name: str) -> int:
    """Count occurrences of ``name`` in git commit subject lines.

    Args:
      repo_root: Repository root.
      name: Template basename.

    Returns:
      Count of subject-line mentions. Zero when git is unavailable
      OR there is no git history (S-5 — explicit zero, never raise).
    """
    try:
        result = subprocess.run(
            ["git", "log", "--pretty=format:%s"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return 0
    if result.returncode != 0:
        return 0
    pattern = re.compile(rf"\b{re.escape(name)}\b")
    return len(pattern.findall(result.stdout))


def classify_template(repo_root: Path, name: str) -> str:
    """Classify ``name`` as USED or REGISTERED.

    Args:
      repo_root: Repository root.
      name: Template basename.

    Returns:
      ``"USED"`` if the template appears in any of the 3 evidence
      sources (cycle docs + CHANGELOG release entries + git subject
      lines); ``"REGISTERED"`` otherwise.

    Note: the audit's baseline classification (per
    :data:`TIER_1_USED_BASELINE` + :data:`TIER_2_LEGACY_BASELINE`) is
    pinned to the v10.3.0 corpus. This function recomputes the
    verdict from scratch on every invocation so the audit picks up
    new usage evidence as cycles accumulate.
    """
    cycle = count_cycle_mentions(repo_root, name)
    changelog = count_changelog_mentions(repo_root, name)
    git = count_git_subject_mentions(repo_root, name)
    if cycle > 0 or changelog > 0 or git > 0:
        return "USED"
    return "REGISTERED"


def render_markdown_report(
    verdicts: dict[str, dict[str, object]],
) -> str:
    """Render the audit results as a markdown report.

    Args:
      verdicts: Mapping of template name -> dict with keys
        ``cycle_mentions`` / ``changelog_mentions`` /
        ``git_mentions`` / ``verdict``.

    Returns:
      Markdown string ready to write to
      ``.local/research/v10.5.X_template_usage_audit.md``.
    """
    used = sorted(n for n, v in verdicts.items() if v["verdict"] == "USED")
    registered = sorted(n for n, v in verdicts.items() if v["verdict"] == "REGISTERED")
    n_compositions = sum(1 for v in verdicts.values() if v.get("source") == "composition")
    n_templates = len(verdicts) - n_compositions
    lines: list[str] = [
        "# v10.5.0 PV-02 D-A-2 Template Usage Audit (Phase A)",
        "",
        "> Generated by `scripts/audit_template_usage.py` per",
        "> `.local/research/v11.0.0_patches/D-A-2.md` §2 Phase A.",
        "",
        "## Summary",
        "",
        f"- Workflow types registered: **{len(verdicts)}**"
        + (
            f" (**{n_templates}** survivor templates + **{n_compositions}**"
            f" compositions per v15-ADR-002)"
            if n_compositions
            else ""
        ),
        f"- Templates USED in cycles (TIER-1): **{len(used)}**",
        f"- Templates REGISTERED but never invoked (TIER-2): **{len(registered)}**",
        f"- Utilization rate: **{len(used) / max(1, len(verdicts)):.1%}**",
        "",
        "## TIER-1 USED",
        "",
        "Templates with cycle-plan, CHANGELOG, OR git-subject mentions.",
        "",
        "| Template | Cycle mentions | CHANGELOG mentions | Git subj. mentions |",
        "|---|---:|---:|---:|",
    ]
    for name in used:
        v = verdicts[name]
        lines.append(
            f"| `{name}` | {v['cycle_mentions']} | "
            f"{v['changelog_mentions']} | {v['git_mentions']} |"
        )

    lines.extend(
        [
            "",
            "## TIER-2 REGISTERED",
            "",
            "Templates with ZERO mentions across all 3 evidence sources.",
            "Phase A of D-A-2 ships a `# DEPRECATED in v11.0.0; retained",
            "for backward compat — Phase B collapse decision lands v15.0.0",
            "per v15-ADR-002` comment block on each yaml file.",
            "",
            "| Template | Cycle mentions | CHANGELOG mentions | Git subj. mentions |",
            "|---|---:|---:|---:|",
        ]
    )
    for name in registered:
        v = verdicts[name]
        lines.append(
            f"| `{name}` | {v['cycle_mentions']} | "
            f"{v['changelog_mentions']} | {v['git_mentions']} |"
        )

    lines.extend(
        [
            "",
            "## Phase A deliverables (this PV)",
            "",
            "1. Each TIER-2 yaml file gains a 3-line deprecation comment",
            "   at the top (pure-additive — yaml still parses; tests pass).",
            '2. SKILL.md "Template Quick-Reference" table appends',
            "   `(legacy)` suffix to TIER-2 names.",
            '3. `references/meta-framework.md` "Per-Workflow Template',
            '   Catalog" + `references/team-roles.md` "Team Participation',
            '   Matrix" — same `(legacy)` suffix.',
            "4. CHANGELOG `## [10.5.0]` entry cites the 6 USED + 16",
            "   REGISTERED counts explicitly.",
            "",
            "Phase B (compose-not-define collapse) decision lands",
            "v15.0.0 per v15-ADR-002.",
            "",
        ]
    )
    return "\n".join(lines)


def run(
    repo_root: Path,
    *,
    json_out: bool = False,
    output: Path | None = None,
) -> int:
    """Entry-point — scan templates, classify, emit report.

    Args:
      repo_root: Repository root.
      json_out: Emit JSON instead of markdown.
      output: Write to this path instead of (or in addition to)
        stdout when set.

    Returns:
      Always 0 (observability-only audit).
    """
    template_names = scan_template_yamls(repo_root)
    composition_names = scan_compositions(repo_root)
    verdicts: dict[str, dict[str, object]] = {}
    for name, source in [
        *((n, "template") for n in template_names),
        *((n, "composition") for n in composition_names),
    ]:
        cycle = count_cycle_mentions(repo_root, name)
        changelog = count_changelog_mentions(repo_root, name)
        git = count_git_subject_mentions(repo_root, name)
        verdicts[name] = {
            "cycle_mentions": cycle,
            "changelog_mentions": changelog,
            "git_mentions": git,
            "source": source,
            "verdict": "USED" if (cycle or changelog or git) else "REGISTERED",
        }
    payload: str
    if json_out:
        payload = json.dumps({"verdicts": verdicts}, indent=2, sort_keys=True)
    else:
        payload = render_markdown_report(verdicts)
    if output is not None:
        output.write_text(payload + ("\n" if not payload.endswith("\n") else ""), encoding="utf-8")
    else:
        print(payload)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Repository root (default: current working directory)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_out",
        help="Emit JSON instead of markdown",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write report to this path",
    )
    args = parser.parse_args(argv)
    return run(args.repo_root, json_out=args.json_out, output=args.output)


if __name__ == "__main__":
    sys.exit(main())
