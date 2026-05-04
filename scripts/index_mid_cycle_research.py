#!/usr/bin/env python3
"""Build a chronological mid-cycle research artifact index.

Implements the v10.7.0 D-O-3 deliverable per
`.local/research/v11.0.0_patches/D-O-3.md`. The script scans
``.local/research/v*_*.md`` and emits a chronological index — a
markdown table by default, JSON via ``--json``.

Why this matters: during a mid-cycle PV (e.g., PV-04 of v10.2.0
cycle), an operator looking for a prior PV's design doc has to
manually grep `.local/research/`. There is no in-cycle navigation
aid today. This script produces one.

**Boundary with W-19 (cycle-end committed archive)**:

* W-19 ``scripts/archive_research_artifacts.py`` runs at cycle CLOSE
  and copies `.local/research/v<cycle-prefix>*` into the COMMITTED
  ``docs/cycle-archive/v<X.Y.0>/`` tree. The W-19 archive is durable
  + cited by future cycles' SI-1 planning gate.
* This script is the **mid-cycle, ephemeral** index — runs at any
  time, scans `.local/research/`, emits a navigation aid. It DOES
  NOT touch ``docs/cycle-archive/``, DOES NOT delete files, and DOES
  NOT modify any source artifact.

Algorithm (per PDS §2 + §6 admission verdict):

1. Glob ``.local/research/v*_*.md`` files matching the strict pattern
   ``v(\\d+)\\.(\\d+)\\.(\\d+)_<topic>\\.md``.
2. Group by cycle (X.Y.0); within each group, sort by patch / topic.
3. Allow filtering by cycle (``--cycle vX.Y.0``) and category
   (``--category gap_analysis|cycle_plan|pds|retrospective|nines|evaluation``).
4. Emit a 4-column markdown table (PV / Date / Topic / Path) by
   default; JSON via ``--json``.

Public API:

* :func:`scan_research_artifacts(research_dir)` -> list[ResearchArtifact]
* :func:`group_by_cycle(artifacts)` -> dict[str, list[ResearchArtifact]]
* :func:`filter_artifacts(artifacts, *, cycle, category)` -> list[ResearchArtifact]
* :func:`render_markdown(artifacts)` -> str
* :func:`render_json(artifacts)` -> str
* :func:`run(repo_root, *, output, cycle, category, json_out)` -> int

Entry point: ``python scripts/index_mid_cycle_research.py
[--repo-root .] [--cycle vX.Y.0] [--category KIND] [--json]
[--output PATH]``

Source: v10.7.0 D-O-3 — codified per
`.local/research/v11.0.0_patches/D-O-3.md` §2.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

__all__ = [
    "ARTIFACT_PATTERN",
    "CATEGORY_KEYWORDS",
    "ResearchArtifact",
    "filter_artifacts",
    "group_by_cycle",
    "render_json",
    "render_markdown",
    "run",
    "scan_research_artifacts",
]

# Strict version-prefix regex: vX.Y.Z_<topic>.md.
# Topic must start with [a-z] then [a-z0-9_]*.
ARTIFACT_PATTERN: re.Pattern[str] = re.compile(
    r"^v(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)_(?P<topic>[a-z][a-z0-9_]*)\.md$"
)

# Topic-keyword → category mapping. Multiple keywords per category enable
# the --category filter to match historical naming variations.
CATEGORY_KEYWORDS: dict[str, frozenset[str]] = {
    "gap_analysis": frozenset({"gap_analysis", "gap-analysis"}),
    "cycle_plan": frozenset({"cycle_plan", "cycle-plan", "implementation_plan", "patch_plan"}),
    "pds": frozenset({"_design", "_patches"}),
    "retrospective": frozenset({"retrospective"}),
    "nines": frozenset({"nines"}),
    "evaluation": frozenset({"evaluation", "eval"}),
    "audit": frozenset({"audit", "snapshot", "compressor_health", "canonical_order"}),
}


@dataclass(frozen=True)
class ResearchArtifact:
    """One in-cycle research file."""

    path: Path
    cycle: str  # "X.Y.0" (the cycle prefix, derived from major.minor)
    version: str  # "X.Y.Z" (full version this artifact ships under)
    topic: str
    mtime_iso: str  # ISO-8601 UTC timestamp (file mtime)
    category: str  # one of CATEGORY_KEYWORDS keys, or "other"


def _categorize(topic: str) -> str:
    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in topic:
                return category
    return "other"


def scan_research_artifacts(research_dir: Path) -> list[ResearchArtifact]:
    """Walk ``research_dir`` and return parsed artifact records.

    Files NOT matching ``ARTIFACT_PATTERN`` are silently excluded
    (they're not part of the cycle versioning convention).
    """
    if not research_dir.is_dir():
        return []
    out: list[ResearchArtifact] = []
    for path in sorted(research_dir.glob("v*.md")):
        match = ARTIFACT_PATTERN.match(path.name)
        if match is None:
            continue
        major = match.group("major")
        minor = match.group("minor")
        patch = match.group("patch")
        topic = match.group("topic")
        cycle = f"{major}.{minor}.0"
        version = f"{major}.{minor}.{patch}"
        try:
            mtime = path.stat().st_mtime
        except OSError:
            mtime = 0.0
        mtime_iso = (
            datetime.fromtimestamp(mtime, tz=UTC).strftime("%Y-%m-%d") if mtime > 0 else "unknown"
        )
        out.append(
            ResearchArtifact(
                path=path,
                cycle=cycle,
                version=version,
                topic=topic,
                mtime_iso=mtime_iso,
                category=_categorize(topic),
            )
        )
    return out


def group_by_cycle(
    artifacts: list[ResearchArtifact],
) -> dict[str, list[ResearchArtifact]]:
    """Return artifacts grouped by cycle prefix (e.g. "10.7.0")."""
    out: dict[str, list[ResearchArtifact]] = {}
    for art in artifacts:
        out.setdefault(art.cycle, []).append(art)
    # Sort within each cycle: descending by version then ascending by topic.
    for cycle in out:
        out[cycle].sort(key=lambda a: (-_version_key(a.version), a.topic))
    return out


def _version_key(version: str) -> int:
    """Compute a sortable integer key from "X.Y.Z" (Z + Y*100 + X*10000)."""
    try:
        x, y, z = (int(part) for part in version.split("."))
        return x * 10000 + y * 100 + z
    except (ValueError, TypeError):
        return 0


def filter_artifacts(
    artifacts: list[ResearchArtifact],
    *,
    cycle: str | None = None,
    category: str | None = None,
) -> list[ResearchArtifact]:
    """Filter the artifact list by cycle / category (both optional)."""
    out = list(artifacts)
    if cycle is not None:
        cycle_norm = cycle.lstrip("v")
        out = [a for a in out if a.cycle == cycle_norm]
    if category is not None:
        out = [a for a in out if a.category == category]
    return out


def render_markdown(artifacts: list[ResearchArtifact]) -> str:
    """Render the index as a markdown table."""
    lines: list[str] = []
    lines.append("# Mid-Cycle Research Artifact Index")
    lines.append("")
    lines.append(
        "_This index is workspace-local + ephemeral._ The committed "
        "cycle archive lives at `docs/cycle-archive/v<X.Y.0>/` (W-19; "
        "cycle-close only). Use this index for in-cycle navigation; "
        "use the W-19 archive for cross-cycle citation."
    )
    lines.append("")
    lines.append(f"- Total artifacts: **{len(artifacts)}**")
    if not artifacts:
        lines.append("")
        lines.append("_No research artifacts found matching the filter._")
        lines.append("")
        return "\n".join(lines) + "\n"
    by_cycle = group_by_cycle(artifacts)
    lines.append(f"- Cycles: **{len(by_cycle)}**")
    lines.append("")
    for cycle in sorted(by_cycle.keys(), key=lambda c: -_version_key(c)):
        cycle_artifacts = by_cycle[cycle]
        lines.append(f"## v{cycle} ({len(cycle_artifacts)} artifacts)")
        lines.append("")
        lines.append("| Version | Date (mtime) | Category | Topic | Path |")
        lines.append("|---|---|---|---|---|")
        for art in cycle_artifacts:
            rel = art.path.relative_to(art.path.parent.parent.parent)
            lines.append(
                f"| v{art.version} | {art.mtime_iso} | {art.category} | "
                f"{art.topic} | `{rel}` |"
            )
        lines.append("")
    return "\n".join(lines) + "\n"


def render_json(artifacts: list[ResearchArtifact]) -> str:
    """Render the index as JSON."""
    return json.dumps(
        {
            "artifact_count": len(artifacts),
            "artifacts": [
                {
                    "path": str(a.path),
                    "cycle": a.cycle,
                    "version": a.version,
                    "topic": a.topic,
                    "mtime_iso": a.mtime_iso,
                    "category": a.category,
                }
                for a in artifacts
            ],
        },
        indent=2,
    )


def _resolve_repo_root(start: Path | None = None) -> Path:
    p = (start or Path(__file__)).resolve()
    if p.is_file():
        p = p.parent
    while p != p.parent:
        if (p / "pyproject.toml").exists():
            return p
        p = p.parent
    raise SystemExit("could not locate repo root (no pyproject.toml)")


def run(
    repo_root: Path,
    *,
    output: Path | None = None,
    cycle: str | None = None,
    category: str | None = None,
    json_out: bool = False,
) -> int:
    """Top-level driver — scan + filter + emit."""
    research_dir = repo_root / ".local" / "research"
    artifacts = scan_research_artifacts(research_dir)
    filtered = filter_artifacts(artifacts, cycle=cycle, category=category)
    body = render_json(filtered) if json_out else render_markdown(filtered)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(body, encoding="utf-8")
        print(f"[index] wrote {output}")
    else:
        sys.stdout.write(body)
        if not body.endswith("\n"):
            sys.stdout.write("\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument(
        "--cycle",
        type=str,
        default=None,
        help="filter by cycle prefix (e.g. v10.7.0)",
    )
    parser.add_argument(
        "--category",
        type=str,
        default=None,
        choices=sorted(list(CATEGORY_KEYWORDS.keys()) + ["other"]),
        help="filter by topic category",
    )
    parser.add_argument(
        "--json", action="store_true", help="emit JSON instead of markdown"
    )
    args = parser.parse_args(argv)
    repo_root = args.repo_root or _resolve_repo_root()
    return run(
        repo_root,
        output=args.output,
        cycle=args.cycle,
        category=args.category,
        json_out=args.json,
    )


if __name__ == "__main__":
    sys.exit(main())
