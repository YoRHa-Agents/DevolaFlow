#!/usr/bin/env python3
"""v8.5.0 PV-05 (W-19 archive mechanism) — copy cycle research artifacts to docs/cycle-archive/.

W-19 codifies that after a MAJOR or MINOR cycle ships, the
``.local/research/<cycle-prefix>*`` artifacts are committed into
``docs/cycle-archive/<cycle-version>/`` so future cycle-N+1 SI-1
planning gates + external reviewers + new contributors can read the
design history without depending on ``.local/`` (gitignored on most
clones).

Usage::

    python scripts/archive_research_artifacts.py 9.0.0
    python scripts/archive_research_artifacts.py 9.0.0 --dry-run
    python scripts/archive_research_artifacts.py 9.2.0 --extra-prefix v9.1.
    python scripts/archive_research_artifacts.py 9.0.0 --refresh
    python scripts/archive_research_artifacts.py --misc

The ``--extra-prefix`` flag was added in v9.2.0 PV-06 so the headline
MINOR-cycle archive can capture artefacts from the in-cycle PATCH
versions whose research files are named under the pre-rollup prefix.
Example: the v9.2.0 cycle ships PV-01..PV-05 as v9.1.1..v9.1.5
artefacts (prefix ``v9.1.``) and PV-06 + PV-07 as v9.2.0 / v9.2.1
artefacts (prefix ``v9.2.``); a single
``archive_research_artifacts.py 9.2.0 --extra-prefix v9.1.`` invocation
copies BOTH prefix sets into ``docs/cycle-archive/v9.2.0/``. Multiple
``--extra-prefix`` values are accepted (the flag may be repeated).

clean_repo Phase B1 (post-v15.0.0) added three behaviours:

* **Subdirectory recursion** — research SUBDIRECTORIES matched by the
  cycle prefix (e.g. ``.local/research/v11.0.0_patches/``) are archived
  whole-tree under the archive root, keeping their original name
  (``docs/cycle-archive/v11.0.0/v11.0.0_patches/...``). The directory
  name itself is the classification — subdir contents are NOT flattened
  into the 7 flat buckets (flattening would collide on generic names
  such as ``README.md``).
* **``--refresh``** — an existing destination copy whose bytes differ
  from the source is OVERWRITTEN (status ``REFRESH``) and the archive
  ``README.md`` index is regenerated. Without ``--refresh`` a differing
  copy is reported as ``STALE`` and left untouched (S-5: surfaced, not
  silent). The default (no flag) keeps the original idempotent
  semantics byte-for-byte.
* **``--misc``** — archives the NON-versioned ``.local/research/`` root
  files (name not matching ``v<digits>.`` / ``v<digits>-``, i.e. files
  that carry no cycle version) into the single flat
  ``docs/cycle-archive/misc/`` destination with its own README index
  (decision D5: these artifacts belong to no release cycle; a
  nearest-cycle mapping would fabricate provenance). ``--misc`` and the
  positional ``version`` are mutually exclusive — exactly one is
  required.

The script is idempotent — re-running it is a no-op when the
destination already exists (no overwrites unless ``--refresh``). Per
the W-19 spec, the archive is created at cycle CLOSE (after the final
patch of a MINOR series ships); calling mid-cycle is supported for
incremental checkpoints.

Output structure (per cycle)::

    docs/cycle-archive/v<MAJOR>.<MINOR>.0/
    ├── README.md             # auto-generated index
    ├── gap_analysis.md       # copy of v<MAJOR>.<MINOR>.0_gap_analysis.md
    ├── implementation_plan.md
    ├── design/               # copy of v<MAJOR>.<MINOR>.0_pv*_design.md
    ├── harness/              # current built-in harness evaluations/baselines
    ├── nines/                # legacy NineS artifacts (historical routing only)
    ├── evaluation/           # copy of v<MAJOR>.<MINOR>.*_evaluation.md
    ├── retrospective.md      # copy of v<MAJOR>.<MINOR>.0_retrospective.md
    └── <subdir>/             # whole-tree copy of v<MAJOR>.<MINOR>.*/ research subdirs
"""

from __future__ import annotations

import argparse
import filecmp
import re
import shutil
import sys
from pathlib import Path

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")

# --misc gathers .local/research/ root FILES whose name does NOT match
# this pattern (decision D5 — non-versioned artifacts belong to no cycle).
# The pattern requires a separator after the version digits (``v9.6.0_x``
# dot form, ``v15-cycle_x`` dash form) so that cycle-LESS v-prefixed names
# (e.g. ``v10_internal_optimization_directions.md``) route to misc/ — they
# match no ``v<MAJOR>.<MINOR>.`` cycle prefix, so without this they would
# fall through every archive destination.
VERSIONED_NAME_RE = re.compile(r"^v\d+[.-]")


def _find_root() -> Path:
    p = Path(__file__).resolve().parent
    while p != p.parent:
        if (p / "pyproject.toml").exists():
            return p
        p = p.parent
    return Path.cwd()


def _cycle_prefix(version: str) -> str:
    """Return the prefix used to match research artifacts for a cycle.

    For ``9.0.0`` returns ``"v9.0."`` — captures every patch in the
    ``v9.0.X`` line (the cycle the MINOR version starts).
    """
    major_minor = ".".join(version.split(".")[:2])
    return f"v{major_minor}."


def _same_bytes(src: Path, dst: Path) -> bool:
    """Content-compare *src* / *dst* bypassing filecmp's stat-signature cache.

    ``filecmp.cmp`` memoizes verdicts keyed on (paths, stat signatures);
    after a ``copy2`` overwrite the destination can inherit the source's
    mtime and replay a stale "differs" verdict. Clearing the cache keeps
    every comparison honest (S-5).
    """
    filecmp.clear_cache()
    return filecmp.cmp(src, dst, shallow=False)


def _copy_one(src: Path, dst: Path, *, dry_run: bool, refresh: bool = False) -> str:
    """Copy *src* to *dst* with idempotent semantics. Returns status string.

    Destination-exists semantics (clean_repo Phase B1):

    * bytes identical  -> ``EXISTS`` (skip — unchanged legacy behaviour)
    * bytes differ, ``refresh=False`` -> ``STALE`` (left untouched; S-5
      surfaced, not silent)
    * bytes differ, ``refresh=True``  -> ``REFRESH`` (overwritten)

    The ``refresh=False`` default preserves the pre-B1 write semantics:
    an existing destination is NEVER overwritten.
    """
    root = _find_root()
    if dst.exists():
        if _same_bytes(src, dst):
            return f"  EXISTS  {dst.relative_to(root)}"
        if not refresh:
            return f"  STALE   {dst.relative_to(root)} != {src.relative_to(root)} (use --refresh)"
        if dry_run:
            return f"  WOULD   {dst.relative_to(root)} <- {src.relative_to(root)} (refresh)"
        shutil.copy2(src, dst)
        return f"  REFRESH {dst.relative_to(root)} <- {src.relative_to(root)}"
    if dry_run:
        return f"  WOULD   {dst.relative_to(root)} <- {src.relative_to(root)}"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return f"  COPIED  {dst.relative_to(root)}"


def _copy_tree(src_dir: Path, archive_dir: Path, *, dry_run: bool, refresh: bool) -> list[str]:
    """Whole-tree archive: dst = archive_dir/<src_dir.name>/<relative path>.

    Every file goes through :func:`_copy_one`, so per-file idempotent /
    STALE / REFRESH semantics apply inside archived subdirectories too.
    """
    return [
        _copy_one(
            f,
            archive_dir / src_dir.name / f.relative_to(src_dir),
            dry_run=dry_run,
            refresh=refresh,
        )
        for f in sorted(src_dir.rglob("*"))
        if f.is_file()
    ]


def _gather_artifacts(
    research_dir: Path, prefix: str, *, extra_prefixes: tuple[str, ...] = ()
) -> dict[str, list[Path]]:
    """Categorize research files by W-19 archive bucket.

    Walks ``research_dir`` once for each prefix (the canonical ``prefix``
    plus any ``extra_prefixes`` from the ``--extra-prefix`` CLI flag) and
    deduplicates the union by absolute path so a file matched by both
    prefixes is enumerated exactly once. Matched DIRECTORIES land in the
    ``subdirs`` bucket (clean_repo Phase B1) — they are archived
    whole-tree by :func:`_copy_tree`, keeping their original name.
    """
    seen: set[Path] = set()
    files: list[Path] = []
    for current in (prefix, *extra_prefixes):
        for f in sorted(research_dir.glob(f"{current}*")):
            if f.resolve() in seen:
                continue
            seen.add(f.resolve())
            files.append(f)
    files.sort(key=lambda p: p.name)
    buckets: dict[str, list[Path]] = {
        "gap_analysis": [],
        "implementation_plan": [],
        "design": [],
        "harness": [],
        "nines": [],
        "evaluation": [],
        "retrospective": [],
        "other": [],
        "subdirs": [],
    }
    for f in files:
        if f.is_dir():
            buckets["subdirs"].append(f)
            continue
        if not f.is_file():
            continue
        name = f.name
        if "gap_analysis" in name:
            buckets["gap_analysis"].append(f)
        elif "implementation_plan" in name or "patch_plan" in name:
            buckets["implementation_plan"].append(f)
        elif "design" in name:
            buckets["design"].append(f)
        elif "harness" in name:
            buckets["harness"].append(f)
        elif "nines" in name:
            # Backward-compatible historical route. New evaluation evidence
            # belongs in the built-in harness bucket above.
            buckets["nines"].append(f)
        elif "evaluation" in name or "evobench" in name.lower():
            # ``evobench`` remains a read-only historical filename route.
            buckets["evaluation"].append(f)
        elif "retrospective" in name:
            buckets["retrospective"].append(f)
        else:
            buckets["other"].append(f)
    return buckets


def _render_readme(cycle_version: str, buckets: dict[str, list[Path]]) -> str:
    """Render the auto-generated index README body (byte-stable template)."""
    lines = [
        f"# Cycle Archive — v{cycle_version}",
        "",
        "Auto-generated by `scripts/archive_research_artifacts.py` per Workflow",
        f"Rule W-19. Mirrors the `.local/research/v{cycle_version[:3]}*` artifacts so",
        "future cycle-N+1 planning gates can reference cycle-N research without",
        "depending on `.local/` (which is gitignored on most clones).",
        "",
        "## Contents",
        "",
    ]
    for bucket, files in buckets.items():
        if not files:
            continue
        lines.append(f"### {bucket}")
        lines.append("")
        for f in files:
            lines.append(f"* `{f.name}/`" if f.is_dir() else f"* `{f.name}`")
        lines.append("")
    lines.append("## Cross-references")
    lines.append("")
    lines.append(f"* `CHANGELOG.md` `## [{cycle_version}]` — release note")
    lines.append("* `.local/research/` — live research workspace (gitignored)")
    lines.append("* `AGENTS.md` §W-19 — archive policy")
    lines.append("")
    return "\n".join(lines)


def _write_readme(
    archive_dir: Path,
    cycle_version: str,
    buckets: dict[str, list[Path]],
    *,
    dry_run: bool,
    refresh: bool = False,
) -> str:
    """Author the auto-generated index README at archive root.

    With ``refresh=True`` an existing README whose content drifted from
    the regenerated index is rewritten (the source set changed, so the
    index must change with it); without it the legacy exists-means-skip
    semantics are preserved byte-for-byte.
    """
    root = _find_root()
    readme_path = archive_dir / "README.md"
    content = _render_readme(cycle_version, buckets)

    if readme_path.exists():
        if not refresh:
            return f"  EXISTS  {readme_path.relative_to(root)}"
        if readme_path.read_text(encoding="utf-8") == content:
            return f"  EXISTS  {readme_path.relative_to(root)}"
        if dry_run:
            return f"  WOULD   {readme_path.relative_to(root)} (README.md refresh)"
        readme_path.write_text(content, encoding="utf-8")
        return f"  REFRESH {readme_path.relative_to(root)} (README.md index regenerated)"

    if dry_run:
        return f"  WOULD   {readme_path.relative_to(root)} (README.md)"

    readme_path.parent.mkdir(parents=True, exist_ok=True)
    readme_path.write_text(content, encoding="utf-8")
    return f"  COPIED  {readme_path.relative_to(root)}"


def _print_summary(statuses: list[str], archive_dir: Path, root: Path, *, dry_run: bool) -> None:
    """Emit the copy-count summary + STALE / REFRESH accounting lines."""
    is_refresh_line = [
        s.lstrip().startswith("REFRESH") or s.rstrip().endswith("(refresh)") for s in statuses
    ]
    total_copied = sum(
        1
        for s, is_refresh in zip(statuses, is_refresh_line, strict=True)
        if not is_refresh and ("COPIED" in s or "WOULD" in s)
    )
    total_refreshed = sum(is_refresh_line)
    total_stale = sum(1 for s in statuses if s.lstrip().startswith("STALE"))
    would = "would be " if dry_run else ""
    print(f"\n{total_copied} file(s) {would}copied to {archive_dir.relative_to(root)}.")
    if total_refreshed:
        print(f"{total_refreshed} stale file(s) {would}refreshed in place.")
    if total_stale:
        plural = "y" if total_stale == 1 else "ies"
        print(f"WARN: {total_stale} stale cop{plural} left untouched — re-run with --refresh.")


def archive(
    cycle_version: str,
    *,
    dry_run: bool = False,
    extra_prefixes: tuple[str, ...] = (),
    refresh: bool = False,
) -> int:
    """Archive .local/research/<prefix>* into docs/cycle-archive/v<cycle>/.

    ``extra_prefixes`` (added v9.2.0 PV-06) lets the caller archive
    additional prefix ranges in the same invocation — useful for the
    cycle-rollup PV that needs to capture both ``v9.1.*`` PATCH research
    AND ``v9.2.*`` MINOR-cycle research into a single
    ``docs/cycle-archive/v9.2.0/`` destination. Each prefix is searched
    independently and the union deduplicated by absolute path.

    ``refresh`` (clean_repo Phase B1) overwrites destination copies
    whose bytes drifted from the source and regenerates the README
    index; the default ``False`` preserves the legacy never-overwrite
    semantics.
    """
    root = _find_root()
    research_dir = root / ".local" / "research"
    if not research_dir.is_dir():
        print(f"ERROR: {research_dir} does not exist — nothing to archive")
        return 1

    prefix = _cycle_prefix(cycle_version)
    archive_dir = root / "docs" / "cycle-archive" / f"v{cycle_version}"

    print(f"Archiving cycle v{cycle_version}")
    print(f"  source: {research_dir.relative_to(root)} (prefix '{prefix}')")
    if extra_prefixes:
        print(f"  extra:  {list(extra_prefixes)!r}")
    print(f"  dest:   {archive_dir.relative_to(root)}")
    if dry_run:
        print("  (dry run — no files will be copied)\n")
    else:
        archive_dir.mkdir(parents=True, exist_ok=True)
        print()

    buckets = _gather_artifacts(research_dir, prefix, extra_prefixes=extra_prefixes)
    if not any(buckets.values()):
        searched = ", ".join(repr(p) for p in (prefix, *extra_prefixes))
        print(f"  WARN: no research artifacts found matching {searched}")
        return 0

    statuses: list[str] = []
    print(_write_readme(archive_dir, cycle_version, buckets, dry_run=dry_run, refresh=refresh))

    bucket_to_subdir = {
        "gap_analysis": archive_dir,
        "implementation_plan": archive_dir,
        "design": archive_dir / "design",
        "harness": archive_dir / "harness",
        "nines": archive_dir / "nines",
        "evaluation": archive_dir / "evaluation",
        "retrospective": archive_dir,
        "other": archive_dir / "other",
    }

    for bucket, files in buckets.items():
        if bucket == "subdirs" or not files:
            continue
        subdir = bucket_to_subdir[bucket]
        for src in files:
            dst = subdir / src.name
            status = _copy_one(src, dst, dry_run=dry_run, refresh=refresh)
            print(status)
            statuses.append(status)

    for src_dir in buckets["subdirs"]:
        for status in _copy_tree(src_dir, archive_dir, dry_run=dry_run, refresh=refresh):
            print(status)
            statuses.append(status)

    _print_summary(statuses, archive_dir, root, dry_run=dry_run)
    return 0


def _write_misc_readme(
    archive_dir: Path, files: list[Path], *, dry_run: bool, refresh: bool
) -> str:
    """Author the index README for the misc/ destination (decision D5)."""
    root = _find_root()
    readme_path = archive_dir / "README.md"
    lines = [
        "# Cycle Archive — misc",
        "",
        "Auto-generated by `scripts/archive_research_artifacts.py --misc` per",
        "Workflow Rule W-19 + clean_repo decision D5. Mirrors the NON-versioned",
        "`.local/research/` root artifacts (file name carrying no cycle version) —",
        "cross-cycle surveys, external-reference analyses, and early exploratory",
        "reports that belong to no single release cycle. A nearest-cycle mapping",
        "would fabricate provenance, so they live in this single flat index.",
        "",
        "## Contents",
        "",
    ]
    for f in files:
        lines.append(f"* `{f.name}`")
    lines.append("")
    lines.append("## Cross-references")
    lines.append("")
    lines.append("* `.local/research/` — live research workspace (gitignored)")
    lines.append("* `AGENTS.md` §W-19 — archive policy")
    lines.append("")
    content = "\n".join(lines)

    if readme_path.exists():
        if not refresh:
            return f"  EXISTS  {readme_path.relative_to(root)}"
        if readme_path.read_text(encoding="utf-8") == content:
            return f"  EXISTS  {readme_path.relative_to(root)}"
        if dry_run:
            return f"  WOULD   {readme_path.relative_to(root)} (README.md refresh)"
        readme_path.write_text(content, encoding="utf-8")
        return f"  REFRESH {readme_path.relative_to(root)} (README.md index regenerated)"

    if dry_run:
        return f"  WOULD   {readme_path.relative_to(root)} (README.md)"

    readme_path.parent.mkdir(parents=True, exist_ok=True)
    readme_path.write_text(content, encoding="utf-8")
    return f"  COPIED  {readme_path.relative_to(root)}"


def archive_misc(*, dry_run: bool = False, refresh: bool = False) -> int:
    """Archive non-versioned .local/research/ root files into docs/cycle-archive/misc/.

    Gathers root-level FILES whose name does not match
    :data:`VERSIONED_NAME_RE` — i.e. files carrying no cycle version
    (subdirectories such as ``adr/`` are out of scope — directories are
    never misc). The destination is a single FLAT directory with a
    README index (decision D5).
    """
    root = _find_root()
    research_dir = root / ".local" / "research"
    if not research_dir.is_dir():
        print(f"ERROR: {research_dir} does not exist — nothing to archive")
        return 1

    archive_dir = root / "docs" / "cycle-archive" / "misc"

    print("Archiving non-versioned research artifacts (misc)")
    print(f"  source: {research_dir.relative_to(root)} (root files carrying no cycle version)")
    print(f"  dest:   {archive_dir.relative_to(root)}")
    if dry_run:
        print("  (dry run — no files will be copied)\n")
    else:
        archive_dir.mkdir(parents=True, exist_ok=True)
        print()

    files = [
        f
        for f in sorted(research_dir.iterdir(), key=lambda p: p.name)
        if f.is_file() and not VERSIONED_NAME_RE.match(f.name)
    ]
    if not files:
        print("  WARN: no non-versioned research artifacts found")
        return 0

    statuses: list[str] = []
    print(_write_misc_readme(archive_dir, files, dry_run=dry_run, refresh=refresh))
    for src in files:
        status = _copy_one(src, archive_dir / src.name, dry_run=dry_run, refresh=refresh)
        print(status)
        statuses.append(status)

    _print_summary(statuses, archive_dir, root, dry_run=dry_run)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "version",
        nargs="?",
        default=None,
        help="cycle version to archive (e.g. 9.0.0); omit when using --misc",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="show planned copies without writing"
    )
    parser.add_argument(
        "--extra-prefix",
        action="append",
        default=[],
        metavar="PREFIX",
        help=(
            "Additional research-file prefix to also archive "
            "(may be repeated). Example: --extra-prefix v9.1. "
            "captures PATCH-level research into the MINOR-cycle archive. "
            "Added v9.2.0 PV-06 for the cycle-rollup MINOR archive."
        ),
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help=(
            "overwrite destination copies whose bytes drifted from the "
            "source (reported as REFRESH) and regenerate the README "
            "index; without this flag stale copies are reported as "
            "STALE and left untouched (clean_repo Phase B1)"
        ),
    )
    parser.add_argument(
        "--misc",
        action="store_true",
        help=(
            "archive NON-versioned .local/research/ root files into "
            "docs/cycle-archive/misc/ (decision D5); mutually exclusive "
            "with the positional version"
        ),
    )
    args = parser.parse_args()

    if args.misc == (args.version is not None):
        parser.error("exactly one of <version> or --misc is required")

    if args.misc:
        if args.extra_prefix:
            parser.error("--extra-prefix only applies to cycle archiving, not --misc")
        sys.exit(archive_misc(dry_run=args.dry_run, refresh=args.refresh))

    if not SEMVER_RE.match(args.version):
        print(f"Error: '{args.version}' is not a valid semver (expected X.Y.Z)")
        sys.exit(1)

    sys.exit(
        archive(
            args.version,
            dry_run=args.dry_run,
            extra_prefixes=tuple(args.extra_prefix),
            refresh=args.refresh,
        )
    )


if __name__ == "__main__":
    main()
