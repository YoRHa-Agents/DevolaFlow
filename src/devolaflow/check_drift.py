"""Drift detection -- compare agent source versions vs human doc versions.

Design ref: design_dual_system.md section 4.4
"""

from __future__ import annotations

from pathlib import Path

import yaml


def _parse_frontmatter(path: Path) -> dict:
    """Extract YAML frontmatter from a markdown file."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    try:
        return yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        return {}


def _find_project_root() -> Path:
    p = Path(__file__).resolve()
    while p != p.parent:
        if (p / "pyproject.toml").exists():
            return p
        p = p.parent
    return Path.cwd()


def check_drift() -> bool:
    """Check human docs for drift against agent source. Returns True if drift found."""
    root = _find_project_root()
    human_dirs = [root / "workflow-system" / "human" / lang for lang in ("en", "zh")]
    agent_dir = root / "workflow-system" / "agent"

    stale: list[tuple[str, str, str]] = []

    for human_dir in human_dirs:
        if not human_dir.is_dir():
            continue
        for doc in human_dir.glob("*.md"):
            fm = _parse_frontmatter(doc)
            source_version = fm.get("source_version", "0.0.0")
            source_files = fm.get("source_files", [])
            for src_ref in source_files:
                src_path = agent_dir / src_ref
                if not src_path.exists():
                    continue
                src_fm = _parse_frontmatter(src_path)
                src_ver = src_fm.get("version", "0.0.0")
                if src_ver != source_version:
                    stale.append((str(doc.relative_to(root)), src_ver, source_version))

    if stale:
        print("Drift detected:")
        for doc, expected, actual in stale:
            print(f"  {doc}: source={expected}, doc has={actual}")
        print(f"\n{len(stale)} stale file(s). Run 'make sync-human-docs' to update.")
        return True

    print("No drift detected. All human docs are in sync.")
    return False
