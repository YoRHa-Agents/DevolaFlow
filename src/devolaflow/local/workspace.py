"""Scaffold and manage the .local/ workspace directory."""

from __future__ import annotations

from pathlib import Path

REQUIRED_DIRS = ["feedbacks", "tasks"]
ON_DEMAND_DIRS = ["research", "design", "benchmarks", "logs", "scratch"]


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

    for d in dirs or []:
        if d in ON_DEMAND_DIRS:
            (local_dir / d).mkdir(exist_ok=True)

    generate_index(local_dir)
    return local_dir


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
