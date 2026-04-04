"""Initialize DevolaFlow skill files in the current project.

Usage:
  devola-init                  Auto-detect tools and install
  devola-init cursor           Install for Cursor only
  devola-init claude           Install for Claude Code only
  devola-init copilot          Install for Copilot only
  devola-init --list           Show what would be installed
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path


def _find_agent_dir() -> Path:
    """Locate the workflow-system/agent/ directory from the installed package."""
    pkg_dir = Path(__file__).resolve().parent
    candidates = [
        pkg_dir.parent.parent / "workflow-system" / "agent",
        Path.cwd() / "workflow-system" / "agent",
    ]
    for p in candidates:
        if (p / "SKILL.md").exists():
            return p

    for parent in pkg_dir.parents:
        agent = parent / "workflow-system" / "agent"
        if (agent / "SKILL.md").exists():
            return agent

    return candidates[0]


def _copy_file(src: Path, dest: Path) -> bool:
    if not src.exists():
        print(f"  SKIP {dest} (source not found: {src})")
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    print(f"  OK   {dest}")
    return True


def _copy_dir(src: Path, dest: Path) -> int:
    if not src.is_dir():
        return 0
    count = 0
    for f in sorted(src.glob("*.md")):
        if _copy_file(f, dest / f.name):
            count += 1
    return count


def install_cursor(agent_dir: Path, cwd: Path) -> None:
    skill_dir = cwd / ".cursor" / "skills" / "devola-flow"
    print(f"\n  Cursor -> {skill_dir}/")
    _copy_file(agent_dir / "SKILL.md", skill_dir / "SKILL.md")
    refs = _copy_dir(agent_dir / "references", skill_dir / "references")
    examples = _copy_dir(agent_dir / "examples", skill_dir / "examples")
    print(f"  ({refs} references, {examples} examples)")

    rules_src = agent_dir.parent.parent / ".cursor" / "rules" / "workflow-rules.mdc"
    rules_dest = cwd / ".cursor" / "rules" / "devola-flow-rules.mdc"
    _copy_file(rules_src, rules_dest)


def install_claude(agent_dir: Path, cwd: Path) -> None:
    print("\n  Claude Code -> ./CLAUDE.md")
    mvp = agent_dir / "MVP-SKILL.md"
    _copy_file(mvp, cwd / "CLAUDE.md")


def install_copilot(agent_dir: Path, cwd: Path) -> None:
    print("\n  Copilot -> .github/copilot-instructions.md")
    mvp = agent_dir / "MVP-SKILL.md"
    _copy_file(mvp, cwd / ".github" / "copilot-instructions.md")


def install_codex(agent_dir: Path, cwd: Path) -> None:
    import os

    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    skill_dir = codex_home / "skills" / "devola-flow"
    print(f"\n  Codex -> {skill_dir}/")
    _copy_file(agent_dir / "MVP-SKILL.md", skill_dir / "SKILL.md")


TOOLS = {
    "cursor": install_cursor,
    "claude": install_claude,
    "copilot": install_copilot,
    "codex": install_codex,
}


def _auto_detect(cwd: Path) -> list[str]:
    found = []
    if (cwd / ".cursor").is_dir():
        found.append("cursor")
    if (cwd / ".claude").is_dir() or (cwd / "CLAUDE.md").exists():
        found.append("claude")
    if (cwd / ".github").is_dir():
        found.append("copilot")
    if Path.home().joinpath(".codex").is_dir():
        found.append("codex")
    return found


def main() -> None:
    cwd = Path.cwd()
    agent_dir = _find_agent_dir()
    args = [a for a in sys.argv[1:] if not a.startswith("-")]

    if "--list" in sys.argv:
        detected = _auto_detect(cwd)
        print("Detected tools:", ", ".join(detected) if detected else "(none)")
        print("\nAvailable targets: cursor, claude, copilot, codex, all")
        print(f"Agent source: {agent_dir}")
        print(f"SKILL.md exists: {(agent_dir / 'SKILL.md').exists()}")
        return

    print("\n  DevolaFlow Quick Setup\n")

    if not (agent_dir / "SKILL.md").exists():
        print(f"  Error: Agent source not found at {agent_dir}")
        print("  Run from the DevolaFlow repo root, or install with:")
        print("    pip install devolaflow")
        sys.exit(1)

    targets = args if args else _auto_detect(cwd)

    if "all" in targets:
        targets = list(TOOLS.keys())

    if not targets:
        print("  No AI tools detected. Installing for Cursor (most common).")
        targets = ["cursor"]

    for t in targets:
        if t in TOOLS:
            TOOLS[t](agent_dir, cwd)
        else:
            print(f"  Unknown target: {t} (use: cursor, claude, copilot, codex, all)")

    print("\n  Done! Start using DevolaFlow by asking your AI tool to")
    print("  'implement a feature' or 'run a full-pipeline workflow'.\n")
