"""Scaffold and manage the .local/ workspace directory."""

from __future__ import annotations

from pathlib import Path

REQUIRED_DIRS = ["feedbacks", "tasks", "memory"]
ON_DEMAND_DIRS = ["research", "design", "benchmarks", "logs", "scratch"]

_DIR_README_CONTENT: dict[str, str] = {
    "feedbacks": """\
# feedbacks/

Format: `feedback_for_vX.Y.Z.md` (one file per version).

Conventions:
- Line 1: `# Feedback for DevolaFlow vX.Y.Z`
- Line 3: `> Date: YYYY-MM-DD | Author: name | Version: vX.Y.Z`
- Sections: Issues (with Severity), Positives, user feedback
- Session logs: `feedback_for_vX.Y.Z_session.md`
- External sources: subdirectories (e.g. `from_evobench/`)
- Resolution tracking: see `TRACKER.md` (do not edit source files)
""",
    "tasks": """\
# tasks/

Format: Markdown overview + optional YAML specs.

Conventions:
- Line 1: `# Task: [title]`
- Line 3: `> ID: T-[ver]-[seq] | Priority: P1-P4 | Status: planned/active/done`
- Sections: Description, Acceptance Criteria (checklist), Files
- YAML specs for machine-readable dispatch live alongside .md overviews
""",
    "memory": """\
# memory/

Auto-memory workspace for DevolaFlow learnings.

Files:
- `MEMORY.md` — index (loaded at session start)
- `prefs.md` — personal preferences (role, communication style)
- `operational.jsonl` — machine-managed learnings (JSONL)
- `topic-*.md` — on-demand topic notes
""",
}


def scaffold_local(
    cwd: str | Path,
    dirs: list[str] | None = None,
) -> Path:
    """Create .local/ with required dirs + optional on-demand dirs.

    Args:
        cwd: Working directory (repo root).
        dirs: Additional on-demand directories to create.  Only names
              listed in ON_DEMAND_DIRS are accepted; unknown names are
              silently ignored.

    Returns:
        Path to the .local/ directory.
    """
    local_dir = Path(cwd) / ".local"
    local_dir.mkdir(exist_ok=True)

    for d in REQUIRED_DIRS:
        (local_dir / d).mkdir(exist_ok=True)
        generate_dir_readme(local_dir / d, d)

    generate_tracker(local_dir / "feedbacks")
    generate_memory_index(local_dir / "memory")

    for d in dirs or []:
        if d in ON_DEMAND_DIRS:
            (local_dir / d).mkdir(exist_ok=True)

    generate_index(local_dir)
    return local_dir


def generate_memory_index(memory_dir: Path) -> Path:
    """Create MEMORY.md index in the memory directory if it doesn't exist.

    Args:
        memory_dir: Path to the memory/ directory.

    Returns:
        Path to the generated MEMORY.md file.
    """
    path = memory_dir / "MEMORY.md"
    if not path.exists():
        path.write_text(
            "# Memory Index\n"
            "\n"
            "> Auto-maintained by DevolaFlow. Updated on scaffold.\n"
            "\n"
            "## Files\n"
            "\n"
            "(No entries yet. Memory files will appear here as the project evolves.)\n",
            encoding="utf-8",
        )
    return path


def generate_tracker(feedbacks_dir: Path) -> Path:
    """Create TRACKER.md in the feedbacks directory if it doesn't exist.

    Args:
        feedbacks_dir: Path to the feedbacks/ directory.

    Returns:
        Path to the generated TRACKER.md file.
    """
    path = feedbacks_dir / "TRACKER.md"
    if not path.exists():
        path.write_text(
            "# Feedback Tracker\n"
            "\n"
            "> Auto-maintained by DevolaFlow. Do not edit feedback source files.\n"
            "> Last updated: (auto)\n"
            "\n"
            "## Open\n"
            "\n"
            "(No open items.)\n"
            "\n"
            "## Resolved\n"
            "\n"
            "(No resolved items yet.)\n"
            "\n"
            "## Deferred\n"
            "\n"
            "(No deferred items.)\n",
            encoding="utf-8",
        )
    return path


def generate_dir_readme(dir_path: Path, dir_name: str) -> Path:
    """Create a README.md convention file in the given directory if it doesn't exist.

    Args:
        dir_path: Path to the target directory.
        dir_name: Logical name of the directory (used to select content template).

    Returns:
        Path to the generated README.md file.
    """
    path = dir_path / "README.md"
    if not path.exists():
        content = _DIR_README_CONTENT.get(dir_name)
        if content is not None:
            path.write_text(content, encoding="utf-8")
    return path


def generate_index(local_dir: str | Path) -> Path:
    """Generate index.md listing existing subdirectories.

    Returns:
        Path to the generated index.md.
    """
    local_dir = Path(local_dir)
    subdirs = sorted(p.name for p in local_dir.iterdir() if p.is_dir())

    lines = [
        "# .local/ workspace index",
        "",
        "Auto-generated directory listing.",
        "",
    ]
    for name in subdirs:
        lines.append(f"- `{name}/`")

    index_path = local_dir / "index.md"
    index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return index_path
