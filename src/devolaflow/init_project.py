"""Initialize DevolaFlow skill files in the current project or user scope.

Usage:
  devola-init                       Auto-detect tools and install
  devola-init cursor                Install for Cursor only
  devola-init claude                Install for Claude Code only
  devola-init claude --global       Install Claude Code globally
  devola-init copilot               Install for Copilot only
  devola-init local                 Initialize .local/ workspace + .rules/
                                    (auto-compiles .rules/ to .cursor/rules/
                                    repo-governance.mdc + AGENTS.md)
  devola-init local --no-compile    Same as above, but skip the auto-compile
  devola-init --list                Show what would be installed
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


def _parse_no_compile(argv: list[str]) -> bool:
    """Return True iff ``--no-compile`` is present in argv.

    Closes G-007 + G-016 (v9.1.0 W2-02): operators who want
    ``devola-init local`` to scaffold ``.local/`` + ``.rules/`` WITHOUT
    auto-running the rule compiler can pass ``--no-compile``. The flag
    is propagated to :func:`install_local` via ``compile_rules=False``
    so test fixtures can exercise the same skip path without mocking
    argv.
    """
    return "--no-compile" in argv


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


def install_local(
    agent_dir: Path,
    cwd: Path,
    scope: str = "project",
    *,
    compile_rules: bool = True,
) -> None:
    """Initialize .local/ workspace and .rules/ governance structure.

    Closes audit ghost G-J1 (v7.4.10 P-08): scaffolds a default
    ``compile-config.yaml`` into ``.rules/`` so that a follow-up
    ``sync-rules`` invocation has a config to read instead of dead-ending
    with "No .rules/compile-config.yaml found." The template is copied
    from ``devolaflow/local/compile_config_template.yaml`` (packaged via
    ``importlib.resources``). Idempotent — never overwrites an existing
    config.

    Auto-compile (v9.1.0 W2-02 — closes G-007 + G-016): after seeding the
    config, ``install_local`` chains ``RuleCompiler.compile_all()`` so
    that fresh repos receive their compiled ``.cursor/rules/repo-governance.mdc``
    + ``AGENTS.md`` immediately, instead of leaving Cursor / Codex agents
    without governance until the operator discovers ``devola-init sync-rules``.

    The compile step honours **S-5 (No Silent Failures)** with graceful
    degradation: any exception raised by ``RuleCompiler`` is caught,
    printed as ``WARN compile failed (non-fatal): <exc>``, and execution
    continues so that ``init`` itself never blocks on a read-only
    filesystem or a malformed user-edited ``compile-config.yaml``. Pass
    ``compile_rules=False`` (or the CLI flag ``--no-compile``) to skip
    the auto-compile entirely while preserving scaffolding behaviour.
    """
    print(f"\n  Local workspace -> {cwd / '.local/'}")

    from devolaflow.local.workspace import scaffold_local

    scaffold_local(cwd)

    rules_dir = cwd / ".rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    config_path = rules_dir / "compile-config.yaml"
    if not config_path.exists():
        from importlib import resources

        template = resources.files("devolaflow.local").joinpath("compile_config_template.yaml")
        config_path.write_text(template.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"  OK   {config_path} (template created)")
    else:
        print(f"  SKIP {config_path} (already exists)")

    if not compile_rules:
        print("  SKIP compile (--no-compile flag set)")
        return

    if config_path.exists():
        try:
            from devolaflow.local.compiler import RuleCompiler

            compiler = RuleCompiler(config_path)
            compiler.compile_all()
            print("  OK   compiled .rules/ → .cursor/rules/repo-governance.mdc + AGENTS.md")
        except Exception as exc:
            # S-5 graceful degradation: log + continue. Init must still
            # succeed even when the compiler hits a read-only FS, a
            # malformed user-edited compile-config.yaml, or any other
            # non-fatal issue. Operators can re-run `devola-init sync-rules`
            # to retry the compile step in isolation.
            print(f"  WARN compile failed (non-fatal): {exc}")


TOOLS = {
    "cursor": install_cursor,
    "claude": install_claude,
    "copilot": install_copilot,
    "codex": install_codex,
    "local": install_local,
}


def _auto_detect(cwd: Path) -> list[str]:
    """Detect which AI coding tools are present in the project directory.

    Also includes ``"local"`` when ``.local/`` is absent so a fresh repo gets
    its workspace scaffolded on the first ``devola-init`` run (feedback #1
    root-cause fix per gap analysis D-4); idempotent thereafter because
    ``.local/`` exists after the first run.
    """
    found = []
    if (cwd / ".cursor").is_dir():
        found.append("cursor")
    if (cwd / ".claude").is_dir():
        found.append("claude")
    if (cwd / ".github").is_dir():
        found.append("copilot")
    if Path.home().joinpath(".codex").is_dir():
        found.append("codex")
    if not (cwd / ".local").is_dir():
        found.append("local")
    return found


def main() -> None:
    """Entry point for the devola-init CLI command."""
    cwd = Path.cwd()
    agent_dir = _find_agent_dir()
    scope = _parse_scope(sys.argv[1:])
    no_compile = _parse_no_compile(sys.argv[1:])
    args = [a for a in sys.argv[1:] if not a.startswith("-")]

    if "--list" in sys.argv:
        detected = _auto_detect(cwd)
        print("Detected tools:", ", ".join(detected) if detected else "(none)")
        print("\nAvailable targets: cursor, claude, copilot, codex, local, all")
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

    # `all` excludes `local` (explicit-opt-in via auto-detect or `local` arg).
    if "all" in targets:
        targets = [t for t in TOOLS if t != "local"]

    if not targets:
        print("  No AI tools detected. Installing for Cursor (most common).")
        targets = ["cursor"]

    for t in targets:
        if t in TOOLS:
            # `--no-compile` is local-only; other installers don't accept the kwarg.
            extra = {"compile_rules": False} if (t == "local" and no_compile) else {}
            TOOLS[t](agent_dir, cwd, scope, **extra)
        else:
            print(f"  Unknown target: {t} (use: cursor, claude, copilot, codex, local, all)")

    print(f"\n  Now Using DevolaFlow v{__version__}")
    print("  Start using DevolaFlow by asking your AI tool to")
    print("  'implement a feature' or 'run a full-pipeline workflow'.\n")
