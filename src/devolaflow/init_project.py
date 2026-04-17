"""Initialize DevolaFlow skill files in the current project or user scope.

Usage:
  devola-init                  Auto-detect tools and install
  devola-init cursor           Install for Cursor only
  devola-init claude           Install for Claude Code only
  devola-init claude --global  Install Claude Code globally
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
    """Copy a single file to dest, creating parent directories as needed."""
    if not src.exists():
        print(f"  SKIP {dest} (source not found: {src})")
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    print(f"  OK   {dest}")
    return True


def _copy_dir(src: Path, dest: Path) -> int:
    """Copy all markdown files from src directory to dest, returning the count copied."""
    if not src.is_dir():
        return 0
    count = 0
    for f in sorted(src.glob("*.md")):
        if _copy_file(f, dest / f.name):
            count += 1
    return count


def _parse_scope(argv: list[str]) -> str:
    """Parse --global/--project flags from argv to determine install scope."""
    scope = "project"
    for arg in argv:
        if arg == "--global":
            scope = "global"
        elif arg == "--project":
            scope = "project"
    return scope


def install_cursor(agent_dir: Path, cwd: Path, scope: str = "project") -> None:
    """Install DevolaFlow skill files and rules for Cursor IDE."""
    base_dir = Path.home() / ".cursor" if scope == "global" else cwd / ".cursor"
    skill_dir = base_dir / "skills" / "devola-flow"
    print(f"\n  Cursor ({scope}) -> {skill_dir}/")
    _copy_file(agent_dir / "SKILL.md", skill_dir / "SKILL.md")
    refs = _copy_dir(agent_dir / "references", skill_dir / "references")
    examples = _copy_dir(agent_dir / "examples", skill_dir / "examples")
    print(f"  ({refs} references, {examples} examples)")

    rules_src = agent_dir.parent.parent / ".cursor" / "rules" / "workflow-rules.mdc"
    rules_dest = base_dir / "rules" / "devola-flow-rules.mdc"
    _copy_file(rules_src, rules_dest)


def install_claude(agent_dir: Path, cwd: Path, scope: str = "project") -> None:
    """Install DevolaFlow skill files for Claude Code."""
    base_dir = Path.home() / ".claude" if scope == "global" else cwd / ".claude"
    skill_dir = base_dir / "skills" / "devola-flow"
    print(f"\n  Claude Code ({scope}) -> {skill_dir}/")
    _copy_file(agent_dir / "SKILL.md", skill_dir / "SKILL.md")
    refs = _copy_dir(agent_dir / "references", skill_dir / "references")
    examples = _copy_dir(agent_dir / "examples", skill_dir / "examples")
    print(f"  ({refs} references, {examples} examples)")


def install_copilot(agent_dir: Path, cwd: Path, scope: str = "project") -> None:
    """Install DevolaFlow full skill for GitHub Copilot."""
    if scope == "global":
        print("\n  Copilot does not support a global install. Using project-local path.")
    print("\n  Copilot -> .github/copilot-instructions.md")
    skill = agent_dir / "SKILL.md"
    _copy_file(skill, cwd / ".github" / "copilot-instructions.md")


def install_codex(agent_dir: Path, cwd: Path, scope: str = "project") -> None:
    """Install DevolaFlow full skill for Codex."""
    import os

    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    skill_dir = codex_home / "skills" / "devola-flow"
    print(f"\n  Codex -> {skill_dir}/")
    _copy_file(agent_dir / "SKILL.md", skill_dir / "SKILL.md")
    refs = _copy_dir(agent_dir / "references", skill_dir / "references")
    print(f"  ({refs} references)")


TOOLS = {
    "cursor": install_cursor,
    "claude": install_claude,
    "copilot": install_copilot,
    "codex": install_codex,
}


def _auto_detect(cwd: Path) -> list[str]:
    """Detect which AI coding tools are present in the project directory."""
    found = []
    if (cwd / ".cursor").is_dir():
        found.append("cursor")
    if (cwd / ".claude").is_dir():
        found.append("claude")
    if (cwd / ".github").is_dir():
        found.append("copilot")
    if Path.home().joinpath(".codex").is_dir():
        found.append("codex")
    return found


def main() -> None:
    """Entry point for the devola-init CLI command."""
    cwd = Path.cwd()
    agent_dir = _find_agent_dir()
    scope = _parse_scope(sys.argv[1:])
    args = [a for a in sys.argv[1:] if not a.startswith("-")]

    if "--list" in sys.argv:
        detected = _auto_detect(cwd)
        print("Detected tools:", ", ".join(detected) if detected else "(none)")
        print("\nAvailable targets: cursor, claude, copilot, codex, all")
        print(f"Scope: {scope}")
        print(f"Agent source: {agent_dir}")
        print(f"SKILL.md exists: {(agent_dir / 'SKILL.md').exists()}")
        return

    from devolaflow import __version__

    print(f"\n  DevolaFlow Quick Setup (v{__version__})\n")

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
            TOOLS[t](agent_dir, cwd, scope)
        else:
            print(f"  Unknown target: {t} (use: cursor, claude, copilot, codex, all)")

    print(f"\n  Now Using DevolaFlow v{__version__}")
    print("  Start using DevolaFlow by asking your AI tool to")
    print("  'implement a feature' or 'run a full-pipeline workflow'.\n")
