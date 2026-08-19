"""Initialize DevolaFlow skill files in the current project or user scope.

Usage:
  devola-init                       Auto-detect tools and install
  devola-init cursor                Install for Cursor only
  devola-init claude                Install for Claude Code only
  devola-init claude --global       Install Claude Code globally
  devola-init <tool> --global       Global skill install ALSO installs all
                                    runtime plugins (nines/ui-pro/rtk/si-chip/
                                    codegraph/impeccable) by default; per-plugin
                                    failures are warn-not-fatal (S-5)
  devola-init <tool> --global --no-plugins
                                    Global install WITHOUT the bundled
                                    runtime-plugin install (skill files only)
  devola-init copilot               Install for Copilot only
  devola-init local                 Initialize .local/ workspace + .rules/
                                    (auto-compiles .rules/ to .cursor/rules/
                                    repo-governance.mdc + AGENTS.md)
  devola-init local --no-compile    Same as above, but skip the auto-compile
  devola-init local --with-examples Seed .local/.agent/active/example-add-dark-mode/
                                    + handoff envelope + memory/specs example
                                    so new repos demonstrate the
                                    change-driven pattern out-of-the-box
                                    (default ON for full-mode installs;
                                    pass --no-with-examples to skip)
  devola-init local --mode=core     Equivalent to --no-compile --no-with-examples
                                    (lean install — scaffolding only)
  devola-init local --mode=standard Default — compile rules, no example seeds
  devola-init local --mode=full     Equivalent to --with-examples (compile + seeds)
  devola-init --list                Show what would be installed

Mode + individual flags: when both ``--mode=X`` and individual
``--no-compile`` / ``--with-examples`` / ``--no-with-examples`` flags are
present, the individual flags OVERRIDE the mode-derived default
(explicit-beats-implicit). This prevents subtle conflicts in CI scripts
that compose both surfaces.
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


def _profile_file_list(agent_dir: Path, profile: str) -> list[str] | None:
    """Resolve *profile*'s file list from the install-manifest SSOT.

    Returns ``None`` (after printing an explicit WARN per S-5) when the
    manifest is absent or unusable — e.g. an old clone predating
    ``workflow-system/agent/manifest.yaml`` — so callers can fall back to
    the legacy whole-directory copy instead of aborting the install.
    """
    try:
        from devolaflow.install_manifest import ManifestError, load_manifest, profile_files
    except ImportError as exc:  # pragma: no cover — wheel without the module
        print(f"  WARN install manifest loader unavailable ({exc}); using directory copy")
        return None
    try:
        manifest = load_manifest(agent_dir)
        return profile_files(manifest, profile)
    except ManifestError as exc:
        print(f"  WARN install manifest unusable ({exc}); using directory copy")
        return None


def _copy_profile_files(agent_dir: Path, skill_dir: Path, files: list[str]) -> int:
    """Copy manifest-declared files preserving their relative layout."""
    copied = 0
    for rel in files:
        if _copy_file(agent_dir / rel, skill_dir / rel):
            copied += 1
    return copied


def _parse_scope(argv: list[str]) -> str:
    """Parse --global/--project flags from argv to determine install scope."""
    scope = "project"
    for arg in argv:
        if arg == "--global":
            scope = "global"
        elif arg == "--project":
            scope = "project"
    return scope


def _parse_no_plugins(argv: list[str]) -> bool:
    """Return True iff ``--no-plugins`` is present in argv.

    v13.0.0 — opt-out for the bundled runtime-plugin install that runs by
    default after a ``--global`` skill install (per the v13.0.0 cycle ask
    "make devola install also install all plugins"). The flag is a CLI arg,
    NOT a new environment flag (W-20 reuse-first: dispatch-time auto-install
    still keys on the existing auto-install env flag — see CHANGELOG +
    references/env-flags.md). Default-OFF (i.e. plugins DO install) for
    ``--global``; ``--no-plugins`` suppresses the bundled install.
    """
    return "--no-plugins" in argv


def install_plugins(scope: str) -> None:
    """Install every runtime-registered plugin (default-ON for ``--global``).

    v13.0.0 — closes the cycle ask "make devola install also install all
    plugins". Iterates the runtime plugin registry
    (``workflow-system/agent/knowledge/runtime-plugins.yaml``) and calls
    :func:`devolaflow.plugins.installer.ensure_plugin` per plugin, so the
    install commands stay single-source-of-truth (A-5 — no duplication of the
    per-backend install logic here).

    Per-plugin failures are **warn-not-fatal** (Soul Rule S-5: every failure
    is logged explicitly via a ``WARN`` line and an explicit ok/warn count is
    returned to the operator — never silently swallowed). A single unreachable
    plugin (npm/pip/curl registry down, missing toolchain, sandbox/CI without
    network) MUST NOT abort the whole ``devola-init --global`` run.

    The registry / package-import guards degrade gracefully when run from a
    wheel-only install that lacks ``workflow-system/`` or the
    ``devolaflow.plugins`` package — the function prints a single WARN and
    returns instead of raising (mirrors the ``install_local`` S-5 pattern).
    """
    try:
        from devolaflow.plugins.exceptions import PluginRuntimeError
        from devolaflow.plugins.installer import ensure_plugin, load_registry
    except ImportError as exc:
        print(f"  WARN plugin install skipped (devolaflow.plugins unavailable): {exc}")
        return

    try:
        registry = load_registry()
    except FileNotFoundError as exc:
        print(f"  WARN plugin install skipped (runtime registry not found): {exc}")
        return
    except PluginRuntimeError as exc:
        print(f"  WARN plugin install skipped (runtime registry unparseable): {exc}")
        return

    plugin_ids = [
        entry["id"]
        for entry in registry.get("plugins", [])
        if isinstance(entry, dict) and entry.get("id")
    ]
    if not plugin_ids:
        print("  WARN plugin install skipped (no plugins registered)")
        return

    print(f"\n  Installing {len(plugin_ids)} runtime plugins ({scope}) ...")
    ok_count = 0
    for pid in plugin_ids:
        try:
            version = ensure_plugin(pid)
        except PluginRuntimeError as exc:
            # S-5: explicit WARN (logged, never silent); install continues
            # so one unreachable plugin does not abort the whole run.
            print(f"  WARN plugin {pid} install failed (non-fatal): {exc}")
            continue
        ok_count += 1
        print(f"  OK   plugin {pid} @ {version}")
    warned = len(plugin_ids) - ok_count
    print(f"  ({ok_count}/{len(plugin_ids)} plugins installed, {warned} warned)")


def _parse_no_compile(argv: list[str], *, default: bool = False) -> bool:
    """Return True iff ``--no-compile`` is present in argv (else ``default``).

    Closes G-007 + G-016 (v9.1.0 W2-02): operators who want
    ``devola-init local`` to scaffold ``.local/`` + ``.rules/`` WITHOUT
    auto-running the rule compiler can pass ``--no-compile``. The flag
    is propagated to :func:`install_local` via ``compile_rules=False``
    so test fixtures can exercise the same skip path without mocking
    argv.

    v9.2.3 PV-02 — added the ``default`` keyword-only kwarg so
    :func:`_parse_mode` can feed a mode-derived default (e.g. ``--mode=core``
    sets ``default=True`` to imply ``--no-compile``). The default value
    ``default=False`` preserves the pre-v9.2.3 behaviour byte-identically
    for every existing direct caller.
    """
    if "--no-compile" in argv:
        return True
    return default


def _parse_with_examples(
    argv: list[str], targets: list[str], *, default: bool | None = None
) -> bool:
    """Return ``True`` iff the example-seed artefacts should be installed.

    Resolves the v9.2.0 PV-06 ``with_examples`` boolean:

    * ``--with-examples`` explicitly requests the seed artefacts → True.
    * ``--no-with-examples`` explicitly opts out → False.
    * Neither flag set → return ``default`` if not None; else fall back
      to the pre-v9.2.3 implicit matrix (``True`` when ``"all"`` is in
      ``targets``, ``False`` otherwise — preserves the v9.2.0 PV-06
      contract for every existing direct caller).

    The cycle plan §"PV-06 — repo-init seed examples" pins the default
    matrix: "default ON for ``mode: full``, OFF for ``mode: core``".
    Operators who run ``devola-init local`` alone get the lean core
    install (no examples) while operators who run ``devola-init all``
    or pass ``--with-examples`` explicitly get the worked trace.

    v9.2.3 PV-02 — added the ``default`` keyword-only kwarg so
    :func:`_parse_mode` can feed a mode-derived default (e.g.
    ``--mode=full`` sets ``default=True``). ``default=None`` preserves
    the pre-v9.2.3 ``"all" in targets`` fallback byte-identically for
    every existing direct caller.
    """
    if "--no-with-examples" in argv:
        return False
    if "--with-examples" in argv:
        return True
    if default is None:
        return "all" in targets
    return default


# v9.2.3 PV-02 — `--mode=core|standard|full` shorthand CLI flag.
#
# Closes the v9.2.1 feedback note "Mode dispatch shorthand suggestion"
# (`.local/feedbacks/feedback_for_v9.2.1.md` §Notes). The shorthand
# consolidates the existing `--no-compile` / `--with-examples` pair per
# the v9.2.0 PV-06 default matrix:
#
#   `--mode=core`     → `--no-compile --no-with-examples` (lean scaffolding)
#   `--mode=standard` → default behaviour (compile rules, no examples)
#   `--mode=full`     → `--with-examples` + compile-on (full demonstration)
#
# Individual flags STILL override `--mode` (explicit-beats-implicit) so
# CI scripts that compose both surfaces are protected against subtle
# conflicts. The membership of `VALID_MODES` is pinned by
# `tests/test_no_ghost_features.py::test_v9_2_3_mode_flag_surface_complete`
# so a future PV cannot silently widen / narrow the set without
# refreshing the W-18 ghost-audit.

VALID_MODES: frozenset[str] = frozenset({"core", "standard", "full"})


def _parse_mode(argv: list[str]) -> str | None:
    """Return the ``--mode={core,standard,full}`` value or ``None`` if absent.

    Closes the v9.2.1 feedback note "Mode dispatch shorthand suggestion".
    When both ``--mode=X`` and individual ``--no-compile`` /
    ``--with-examples`` flags are present, the individual flags OVERRIDE
    ``--mode`` (explicit-beats-implicit; prevents subtle conflicts in
    CI scripts). Precedence is documented in the module docstring + the
    README "Troubleshooting installs" section.

    Invalid mode values (anything outside :data:`VALID_MODES`) print an
    informative error and exit 1 — S-5 explicit-error-state, NEVER a
    silent fallback to standard. The error message lists the valid
    values so the operator can fix the typo without consulting docs.
    """
    for arg in argv:
        if arg.startswith("--mode="):
            mode = arg.removeprefix("--mode=")
            if mode not in VALID_MODES:
                valid = ", ".join(sorted(VALID_MODES))
                print(f"  Error: --mode must be one of {valid} (got {mode!r})")
                sys.exit(1)
            return mode
    return None


def install_cursor(agent_dir: Path, cwd: Path, scope: str = "project") -> None:
    """Install DevolaFlow skill files for Cursor IDE.

    v15.0.0 (clean_repo C1-2, decision D1): the legacy rules copy
    (`.cursor/rules/workflow-rules.mdc` → `<base>/rules/devola-flow-rules.mdc`)
    retired together with the source pointer stub — the stub carried no
    live rules and its cross-references were repo-relative, dangling
    outside this repository. The SKILL.md carries the orchestrator
    contract; no separate rules file is installed.
    """
    base_dir = Path.home() / ".cursor" if scope == "global" else cwd / ".cursor"
    skill_dir = base_dir / "skills" / "devola-flow"
    print(f"\n  Cursor ({scope}) -> {skill_dir}/")
    files = _profile_file_list(agent_dir, "cursor")
    if files is None:
        _copy_file(agent_dir / "SKILL.md", skill_dir / "SKILL.md")
        refs = _copy_dir(agent_dir / "references", skill_dir / "references")
        examples = _copy_dir(agent_dir / "examples", skill_dir / "examples")
        print(f"  ({refs} references, {examples} examples)")
        return
    copied = _copy_profile_files(agent_dir, skill_dir, files)
    print(f"  ({copied}/{len(files)} files per manifest profile 'cursor')")


def install_claude(agent_dir: Path, cwd: Path, scope: str = "project") -> None:
    """Install DevolaFlow skill files for Claude Code."""
    base_dir = Path.home() / ".claude" if scope == "global" else cwd / ".claude"
    skill_dir = base_dir / "skills" / "devola-flow"
    print(f"\n  Claude Code ({scope}) -> {skill_dir}/")
    files = _profile_file_list(agent_dir, "claude")
    if files is None:
        _copy_file(agent_dir / "SKILL.md", skill_dir / "SKILL.md")
        refs = _copy_dir(agent_dir / "references", skill_dir / "references")
        examples = _copy_dir(agent_dir / "examples", skill_dir / "examples")
        print(f"  ({refs} references, {examples} examples)")
        return
    copied = _copy_profile_files(agent_dir, skill_dir, files)
    print(f"  ({copied}/{len(files)} files per manifest profile 'claude')")


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
    files = _profile_file_list(agent_dir, "codex")
    if files is None:
        _copy_file(agent_dir / "SKILL.md", skill_dir / "SKILL.md")
        refs = _copy_dir(agent_dir / "references", skill_dir / "references")
        print(f"  ({refs} references)")
        return
    copied = _copy_profile_files(agent_dir, skill_dir, files)
    print(f"  ({copied}/{len(files)} files per manifest profile 'codex')")


def install_local(
    agent_dir: Path,
    cwd: Path,
    scope: str = "project",
    *,
    compile_rules: bool = True,
    with_examples: bool = False,
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

    v9.2.0 PV-06 — example seed (``with_examples=True``): scaffolds a
    populated ``.local/.agent/active/example-add-dark-mode/`` change
    folder (all 7 C-9-budgeted artifacts), one
    ``.local/.agent/handoff/L0__L2__example-add-dark-mode__0001.yaml``
    envelope, and a minimal ``.local/memory/specs/example-domain/spec.md``
    so new repos can demonstrate the change-driven pattern out-of-the-
    box. Default-OFF here; the CLI defaults to ON for ``mode: full`` and
    OFF for ``mode: core`` per the v9.2.0 PV-06 cycle plan §"PV-06 —
    repo-init seed examples". Idempotent — never overwrites an existing
    example folder, envelope, or spec; safe to re-run.

    Track C-4 (R5 F4) — pre-flight capability probe: the function starts
    by probing the init-chain dependency tier table
    (:data:`devolaflow.init_probe.INIT_DEPENDENCIES`) and printing the
    capability table. Missing REQUIRED dependencies (git) exit 1 with
    one explicit message BEFORE any filesystem write; missing optional
    dependencies (node/npm/codegraph/nines) each surface exactly one
    degradation hint and the install continues.
    """
    print(f"\n  Local workspace -> {cwd / '.local/'}")

    # Track C-4 (R5 F4): unified pre-flight capability probe. Required
    # dependencies missing → ONE explicit error up front and exit 1
    # BEFORE any scaffold write; optional/situational gaps print exactly
    # one hint line each inside the table (degraded paths, never a
    # mid-flow stack trace).
    from devolaflow.init_probe import (
        MissingRequiredDependencyError,
        assert_required_present,
        format_capability_table,
        probe_capabilities,
    )

    findings = probe_capabilities()
    print(format_capability_table(findings))
    try:
        assert_required_present(findings)
    except MissingRequiredDependencyError as exc:
        print(f"  FAIL {exc}")
        sys.exit(1)

    from devolaflow.local.workspace import (
        ScaffoldStructureError,
        ScaffoldVerificationError,
        scaffold_local,
    )

    try:
        scaffold_local(cwd)
    except (ScaffoldVerificationError, ScaffoldStructureError) as exc:
        # Track C-1/C-2 (S-5): a post-scaffold self-check failed (gitignore
        # rules or structure contract). Surface the exact diff + a recovery
        # hint instead of a traceback, and exit non-zero — no more silent
        # "success".
        print(f"  FAIL {exc}")
        sys.exit(1)

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

    if with_examples:
        _seed_example_artifacts(cwd)

    if not compile_rules:
        print("  SKIP compile (--no-compile flag set)")
        _verify_local_install_health(cwd)
        return

    if config_path.exists():
        try:
            from devolaflow.local.compiler import RuleCompiler

            compiler = RuleCompiler(config_path)
            results = compiler.compile_all()
            # Track C-2 (R5 F3): report the ACTUAL compiled targets instead
            # of the historic hardcoded ".cursor/rules/... + AGENTS.md"
            # claim, which was wrong for user-edited configs.
            targets = ", ".join(r.target for r in results) or "(no targets configured)"
            print(f"  OK   compiled .rules/ → {targets}")
        except Exception as exc:
            # S-5 graceful degradation: log + continue. Init must still
            # succeed even when the compiler hits a read-only FS, a
            # malformed user-edited compile-config.yaml, or any other
            # non-fatal issue. Operators can re-run `devola-init sync-rules`
            # to retry the compile step in isolation.
            print(f"  WARN compile failed (non-fatal): {exc}")

    _verify_local_install_health(cwd)


def _verify_local_install_health(cwd: Path) -> None:
    """Track C-2 (R5 F3): mandatory post-install structure contract check.

    Runs the same doctor contract (`check_init_health`, itself derived from
    `devolaflow.local.workspace.expected_scaffold_paths` — A-5 single owner)
    that `devola-init-doctor` exposes, immediately after `install_local`
    finishes. Missing paths print an explicit diff list and exit 1 (S-5 —
    no silent "success" with a deviant structure). Advisory skeleton drift
    is summarised but never fatal.
    """
    from devolaflow.lifecycle.validate_owned_files import check_init_health

    report = check_init_health(cwd)
    if report.healthy:
        advisory_note = (
            f"; {len(report.advisories)} advisory finding(s) — run devola-init-doctor"
            if report.advisories
            else ""
        )
        print(f"  OK   structure contract verified ({report.summary()}){advisory_note}")
        return

    print(f"  FAIL structure contract check: {report.summary()}")
    for f in report.findings:
        if not f.ok and not f.advisory:
            print(f"       ❌ {f.path} — {f.detail}")
    print("       Re-run `devola-init local`; if it persists, check filesystem permissions.")
    sys.exit(1)


# ---------------------------------------------------------------------------
# v9.2.0 PV-06 — example seed artefacts
# ---------------------------------------------------------------------------
#
# When ``install_local(..., with_examples=True)`` is invoked (the canonical
# CLI default for full-mode installs per the v9.2.0 PV-06 cycle plan),
# ``_seed_example_artifacts`` writes 3 fixtures into the freshly-scaffolded
# workspace so consumer-side agents can read a worked trace BEFORE having
# to author their own change folder:
#
# 1. ``.local/.agent/active/example-add-dark-mode/`` — full 7-artifact set
#    (goal / acceptance / spec / tasks / STATUS / owned_files / README)
#    demonstrating the change-driven workflow shape per Soul Rule S-8.
# 2. ``.local/.agent/handoff/L0__L2__example-add-dark-mode__0001.yaml`` —
#    one TaskDispatch envelope showing the append-only ledger contract
#    (Soul Rule S-9) + the v8.2.4 schemas/agent-workspace/handoff-envelope.yaml
#    discriminated-union shape.
# 3. ``.local/memory/specs/example-domain/spec.md`` — a minimal valid
#    source-of-truth spec for the placeholder ``example-domain`` so the
#    A-4 invariant is illustrated without polluting any real domain.
#
# Every artefact respects its C-9 token-budget hard ceiling (verified at
# write time by ``_verify_artifact_within_budget`` and at test time by
# ``tests/test_capability_e2e.py::test_artifacts_respect_c9_token_budgets``).
# All paths are repo-relative per Soul Rule S-2 — no absolute paths.
#
# Source: v9.2.0 cycle plan §PV-06 — closes the bootstrap-gap noted in
# the cycle plan §"Diagnosis": "New repos have nothing to learn from".


_EXAMPLE_CHANGE_ID: str = "example-add-dark-mode"
_EXAMPLE_DOMAIN: str = "example-domain"
_EXAMPLE_HANDOFF_FROM: str = "L0"
_EXAMPLE_HANDOFF_TO: str = "L2"
_EXAMPLE_HANDOFF_SEQ: int = 1
_EXAMPLE_TIMESTAMP: str = "2026-05-01T00:00:00Z"


_EXAMPLE_GOAL_MD: str = """\
# Goal: Add dark mode toggle

Add a user-facing dark mode toggle to the demo app. The toggle persists
the user's preference across sessions via local storage and respects the
operating-system color-scheme preference on first load.

Status: example fixture only — this folder ships via `devola-init local
--with-examples` so new repos can read a worked trace of the
change-driven workflow before authoring their own change.
"""

_EXAMPLE_ACCEPTANCE_MD: str = """\
# Acceptance Criteria: example-add-dark-mode

1. **Toggle present**: a `<DarkModeToggle/>` component renders in the
   header and is keyboard-accessible (Tab focus + Space/Enter activates).
2. **Preference persists**: after toggling, the choice survives a full
   page reload via `localStorage["devola-theme"]`.
3. **OS preference respected**: on first load with no stored preference,
   the toggle initialises from `prefers-color-scheme: dark` media query.
4. **No visual regression in light mode**: existing visual snapshots
   under `tests/visual/` remain byte-identical when the user is in light
   mode (the new dark theme is additive, not replacing).
5. **Coverage**: `src/components/DarkModeToggle.tsx` reaches >= 80%
   per S-3 / Rule CP-2.
"""

_EXAMPLE_SPEC_MD: str = """\
---
parent: example-add-dark-mode
delta_target: example-domain
delta_kind: lite
---

# Operation Spec for example-add-dark-mode

## Purpose
Introduce a user-facing dark mode toggle that persists across sessions
and respects the OS color-scheme preference on first load. This spec is
the per-change DELTA against the `example-domain` source-of-truth at
`.local/memory/specs/example-domain/spec.md` per Architecture Rule A-4.

## ADDED Requirements

### Requirement: Dark mode toggle is rendered in the header
The system MUST render a keyboard-accessible `<DarkModeToggle/>`
component in the application header.

#### Scenario: User clicks the toggle
- GIVEN the user is on any page of the demo app
- WHEN the user activates the toggle (click or Space / Enter while focused)
- THEN the body class flips between `theme-light` and `theme-dark`
  AND `localStorage["devola-theme"]` records the new preference

### Requirement: Theme preference persists across reloads
The system MUST restore the user's previously-selected theme on next visit.

#### Scenario: Returning visitor with stored preference
- GIVEN `localStorage["devola-theme"] == "dark"`
- WHEN the page loads
- THEN the body class is `theme-dark` BEFORE first paint (no flash)

### Requirement: OS preference is the first-load default
The system MUST initialise from `prefers-color-scheme` when no stored
preference exists.

#### Scenario: First-time visitor with OS dark mode
- GIVEN the visitor has never set a preference
- AND the browser reports `prefers-color-scheme: dark`
- WHEN the page loads
- THEN the body class is `theme-dark`
"""

_EXAMPLE_TASKS_MD: str = """\
# Tasks: example-add-dark-mode

> Worked-trace fixture — reflects a typical change-driven task list.
> See `goal.md` + `acceptance.md` + `spec.md` for full context.

## T1 — Theme tokens + body classes
- Add `--color-bg-dark` / `--color-fg-dark` to `src/styles/theme.ts`.
- Wire `body.theme-dark` overrides into the existing CSS layer.
- Owners: `src/styles/theme.ts`.

## T2 — Toggle component
- Implement `src/components/DarkModeToggle.tsx` with controlled state
  + keyboard handler.
- Render in `src/layouts/Header.tsx`; add `aria-label`.
- Owners: `src/components/DarkModeToggle.tsx`, `src/layouts/Header.tsx`.

## T3 — Persistence + OS-preference bootstrap
- Read `localStorage["devola-theme"]` on mount; fall back to
  `window.matchMedia("(prefers-color-scheme: dark)").matches`.
- Hydrate body class BEFORE first paint to avoid FOUC.

## T4 — Tests
- Unit: toggle click flips class + writes localStorage.
- Integration: hydration path picks OS preference when storage empty.
- Visual: light mode snapshots remain byte-identical (AC #4).
"""

_EXAMPLE_STATUS_YAML: str = """\
schema_version: 1
change_id: example-add-dark-mode
state: PROPOSED
created: "2026-05-01T00:00:00Z"
last_updated: "2026-05-01T00:00:00Z"
percent_complete: 0
last_handoff_seq: 1
delta_target: example-domain
delta_kind: lite
note: example fixture seeded by `devola-init local --with-examples`
"""

_EXAMPLE_OWNED_FILES_TXT: str = """\
src/components/DarkModeToggle.tsx
src/layouts/Header.tsx
src/styles/theme.ts
tests/components/DarkModeToggle.test.tsx
"""

_EXAMPLE_README_MD: str = """\
# example-add-dark-mode

Worked-trace fixture seeded by `devola-init local --with-examples`
(v9.2.0 PV-06). Demonstrates the 7-artifact `change-driven` shape:

| File | Role |
|---|---|
| `goal.md` | 100-word intent statement |
| `acceptance.md` | testable AC checklist |
| `spec.md` | OpenSpec ADDED Requirements (A-4 delta) |
| `tasks.md` | implementation checklist |
| `STATUS.yaml` | machine-readable FSM state |
| `owned_files.txt` | S-8 ownership manifest |
| `README.md` | this file |

Pair with `.local/.agent/handoff/L0__L2__example-add-dark-mode__0001.yaml`
(one TaskDispatch envelope) + `.local/memory/specs/example-domain/spec.md`
(source-of-truth contract).

Delete this folder once you author your first real change — it is
illustrative only.
"""


_EXAMPLE_HANDOFF_ENVELOPE_YAML: str = """\
schema_version: 1
seq: 1
from_layer: L0
to_layer: L2
change_id: example-add-dark-mode
created: "2026-05-01T00:00:00Z"
envelope_kind: TaskDispatch
dispatch:
  task_id: T1-theme-tokens
  type: implement
  acceptance_criteria_ref: .local/.agent/active/example-add-dark-mode/acceptance.md
  owned_files_ref: .local/.agent/active/example-add-dark-mode/owned_files.txt
  note: example fixture envelope seeded by `devola-init local --with-examples`
"""


_EXAMPLE_SOURCE_OF_TRUTH_SPEC_MD: str = """\
---
domain: example-domain
schema_version: 1
last_merged_change: null
last_merged_at: null
---

# Spec: Example-Domain — Source-of-Truth

## Requirement: Example domain placeholder
The system MAY provide a minimal valid source-of-truth spec for the
placeholder `example-domain` so new repos can read a worked-trace
example of the A-4 contract before authoring their first real domain.

### Scenario: A consumer-repo agent inspects the source-of-truth shape
- GIVEN `devola-init local --with-examples` has run
- WHEN the agent reads `.local/memory/specs/example-domain/spec.md`
- THEN it sees a populated H1 + frontmatter + a single placeholder
  Requirement following the v8.2.4 source-of-truth-spec schema

> Note: this domain is example-only. Mutate via the canonical
> `propose_merge → apply_merge` flow once you have a real change to
> propose; bootstrap a fresh domain via
> `devolaflow.agent_workspace.spec_bootstrap.seed_initial_spec`
> instead of editing this file by hand.
"""


_EXAMPLE_ARTIFACT_BUDGETS: dict[str, tuple[int, int]] = {
    # (soft_tokens, hard_tokens) — verbatim from C-9 / lint.ARTIFACT_BUDGETS.
    "goal.md": (200, 400),
    "acceptance.md": (400, 800),
    "spec.md": (1500, 3000),
    "tasks.md": (800, 1500),
    "STATUS.yaml": (100, 200),
    "owned_files.txt": (50, 100),
    # Handoff envelope is bounded at 600 / 1200 per design.md §1.1.
    "L0__L2__example-add-dark-mode__0001.yaml": (600, 1200),
}


def _estimate_tokens(text: str) -> int:
    """Mirror :func:`devolaflow.agent_workspace.lint.estimate_tokens`.

    Kept as a private helper (not imported from ``lint``) so the seed
    helper does not pull the lint module's CLI argparse footprint into
    every ``devola-init local`` invocation. Identical formula:
    ``len(text) // 4``.
    """
    if not text:
        return 0
    return len(text) // 4


def _verify_artifact_within_budget(filename: str, content: str) -> None:
    """Raise :class:`ValueError` when the seed payload would breach C-9.

    The seed templates above are static — they cannot regress at runtime
    — but the verification keeps this function as a defensive S-5
    explicit-error-state guard against a future edit that grows the
    template past the hard ceiling. A hard breach is a release blocker
    per Rule C-9.
    """
    budget = _EXAMPLE_ARTIFACT_BUDGETS.get(filename)
    if budget is None:
        return
    soft, hard = budget
    observed = _estimate_tokens(content)
    if observed > hard:
        raise ValueError(
            f"_seed_example_artifacts: {filename!r} payload is {observed} tokens, "
            f"exceeding the C-9 hard ceiling of {hard}. Trim the template before "
            f"shipping (soft budget {soft})."
        )


def _seed_example_artifacts(cwd: Path) -> None:
    """Seed worked-trace fixtures under ``.local/.agent/`` + ``.local/memory/``.

    Idempotent: every write is gated by ``Path.exists()``; the function
    NEVER overwrites an existing file. Re-running ``devola-init local
    --with-examples`` is therefore safe (per the install-skill semantic
    invariant — first run creates, subsequent runs are no-ops).

    Seeds three fixtures total:

    * ``.local/.agent/active/example-add-dark-mode/`` (7 files)
    * ``.local/.agent/handoff/L0__L2__example-add-dark-mode__0001.yaml``
    * ``.local/memory/specs/example-domain/spec.md``

    Per Soul Rule S-9 the handoff envelope is APPEND-ONLY — once seeded
    the file MUST NOT be modified or deleted by any agent; new envelopes
    go to ``seq=2`` etc.

    All artefacts respect their C-9 token-budget hard ceilings; the
    pre-write :func:`_verify_artifact_within_budget` check raises
    :class:`ValueError` if a future template edit would breach.
    """
    print(f"\n  Example seed -> {cwd / '.local/.agent/'} + .local/memory/specs/")

    active_folder = cwd / ".local" / ".agent" / "active" / _EXAMPLE_CHANGE_ID
    active_folder.mkdir(parents=True, exist_ok=True)

    artifacts: dict[str, str] = {
        "goal.md": _EXAMPLE_GOAL_MD,
        "acceptance.md": _EXAMPLE_ACCEPTANCE_MD,
        "spec.md": _EXAMPLE_SPEC_MD,
        "tasks.md": _EXAMPLE_TASKS_MD,
        "STATUS.yaml": _EXAMPLE_STATUS_YAML,
        "owned_files.txt": _EXAMPLE_OWNED_FILES_TXT,
        "README.md": _EXAMPLE_README_MD,
    }

    for filename, content in artifacts.items():
        _verify_artifact_within_budget(filename, content)
        target = active_folder / filename
        if target.exists():
            print(f"  SKIP {target} (already exists)")
            continue
        target.write_text(content, encoding="utf-8", newline="\n")
        print(f"  OK   {target}")

    handoff_dir = cwd / ".local" / ".agent" / "handoff"
    handoff_dir.mkdir(parents=True, exist_ok=True)
    envelope_filename = (
        f"{_EXAMPLE_HANDOFF_FROM}__{_EXAMPLE_HANDOFF_TO}"
        f"__{_EXAMPLE_CHANGE_ID}__{_EXAMPLE_HANDOFF_SEQ:04d}.yaml"
    )
    envelope_path = handoff_dir / envelope_filename
    _verify_artifact_within_budget(envelope_filename, _EXAMPLE_HANDOFF_ENVELOPE_YAML)
    if envelope_path.exists():
        print(f"  SKIP {envelope_path} (already exists; S-9 append-only)")
    else:
        envelope_path.write_text(_EXAMPLE_HANDOFF_ENVELOPE_YAML, encoding="utf-8", newline="\n")
        print(f"  OK   {envelope_path}")

    spec_dir = cwd / ".local" / "memory" / "specs" / _EXAMPLE_DOMAIN
    spec_dir.mkdir(parents=True, exist_ok=True)
    spec_path = spec_dir / "spec.md"
    if spec_path.exists():
        print(f"  SKIP {spec_path} (already exists)")
    else:
        spec_path.write_text(_EXAMPLE_SOURCE_OF_TRUTH_SPEC_MD, encoding="utf-8", newline="\n")
        print(f"  OK   {spec_path}")


TOOLS = {
    "cursor": install_cursor,
    "claude": install_claude,
    "copilot": install_copilot,
    "codex": install_codex,
    "local": install_local,
}


# v9.2.2 PV-01 — I-001 critical fix.
#
# The set of `devola-init` targets that consume the on-disk
# `workflow-system/agent/` source tree (specifically `agent_dir / "SKILL.md"`
# and the `references/` + `examples/` siblings). The pip wheel does NOT
# bundle `workflow-system/` (excluded from `MANIFEST.in` / wheel
# `data_files`), so a wheel-only install lacks these paths — every target
# in this set MUST raise an informative error in that scenario instead of
# aborting the whole CLI before any per-target dispatch can run.
#
# `local` is intentionally absent: `install_local` uses
# `devolaflow.local.workspace.scaffold_local` + `importlib.resources` for
# the `compile_config_template.yaml` — it has ZERO dependency on
# `agent_dir`, so a wheel-only `devola-init local` MUST succeed (this is
# the I-001 closure). See `.local/feedbacks/feedback_for_v9.2.1.md` §1
# for the user-side reproduction and `.local/research/v9.2.2_gap_analysis.md`
# §1 for the cycle-side decomposition.
#
# Membership is pinned by `tests/test_no_ghost_features.py::
# test_v9_2_2_new_symbols_have_coverage` so future PVs cannot silently
# add a target to the set without bumping the W-18 ghost-audit lint.
AGENT_DIR_REQUIRED_TARGETS: frozenset[str] = frozenset({"cursor", "claude", "copilot", "codex"})


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
    # v9.2.3 PV-02 — `--mode={core,standard,full}` shorthand resolves
    # FIRST so its mode-derived defaults can feed the per-flag resolvers.
    # Invalid `--mode=` values exit 1 inside `_parse_mode` (S-5 explicit
    # error state) so we never reach the per-target dispatch loop with an
    # ambiguous configuration.
    mode = _parse_mode(sys.argv[1:])
    if mode == "core":
        default_no_compile = True
        default_with_examples: bool | None = False
    elif mode == "full":
        default_no_compile = False
        default_with_examples = True
    elif mode == "standard":
        default_no_compile = False
        default_with_examples = False
    else:  # mode is None — preserve pre-v9.2.3 implicit behaviour
        default_no_compile = False
        default_with_examples = None  # signals "use 'all' in targets" fallback

    no_compile = _parse_no_compile(sys.argv[1:], default=default_no_compile)
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

    targets = args if args else _auto_detect(cwd)

    # `with_examples` resolves BEFORE the `all` keyword expansion so the
    # default-matrix decision sees the user's verbatim choice (the
    # cycle plan §PV-06 default-ON-for-full matrix). Mode-derived
    # default (default_with_examples) is overridden when the operator
    # passes `--with-examples` / `--no-with-examples` explicitly
    # (explicit-beats-implicit; v9.2.3 PV-02 dispatch contract).
    with_examples = _parse_with_examples(sys.argv[1:], targets, default=default_with_examples)

    # `all` excludes `local` (explicit-opt-in via auto-detect or `local` arg).
    if "all" in targets:
        targets = [t for t in TOOLS if t != "local"]

    if not targets:
        print("  No AI tools detected. Installing for Cursor (most common).")
        targets = ["cursor"]

    for t in targets:
        if t in TOOLS:
            # v9.2.2 PV-01 — I-001 critical fix: deferred SKILL.md
            # existence check. Per-target dispatch only requires the
            # `workflow-system/agent/` tree for the targets in
            # `AGENT_DIR_REQUIRED_TARGETS`; `local` is exempt because
            # `install_local` is fully pip-wheel-portable (uses
            # `scaffold_local` + `importlib.resources`). Pre-v9.2.2
            # `main()` aborted unconditionally before this loop on any
            # missing SKILL.md, so every operator with a wheel-only
            # install hit a misleading error that recommended the same
            # `pip install` they had already run. The deferred check
            # exits 1 only for genuinely-required targets and never
            # recommends `pip install devolaflow` (the recommendation
            # that landed users in I-001 in the first place).
            if t in AGENT_DIR_REQUIRED_TARGETS and not (agent_dir / "SKILL.md").exists():
                print(f"  Error: target {t!r} needs the workflow-system/agent/ source tree.")
                print(f"    Searched: {agent_dir}")
                print("    The pip wheel does not bundle workflow-system/.")
                print(
                    "    Either install from a clone "
                    "(`git clone https://github.com/YoRHa-Agents/DevolaFlow "
                    "&& pip install -e ./DevolaFlow`)"
                )
                print("    or run `devola-init local` (which does not require workflow-system/).")
                print(
                    "    See: https://github.com/YoRHa-Agents/DevolaFlow "
                    "(track I-001 — v9.2.2 surgical fix)."
                )
                sys.exit(1)
            # `--no-compile` and `--with-examples` are local-only — other
            # installers don't accept the kwargs. Build the extras dict
            # conditionally so the cursor / claude / codex / copilot
            # installers stay byte-identical to v9.1.5 behaviour.
            extra: dict[str, bool] = {}
            if t == "local":
                if no_compile:
                    extra["compile_rules"] = False
                extra["with_examples"] = with_examples
            TOOLS[t](agent_dir, cwd, scope, **extra)
        else:
            print(f"  Unknown target: {t} (use: cursor, claude, copilot, codex, local, all)")

    # v13.0.0 — bundled runtime-plugin install. Default-ON for --global
    # (the cycle ask: "make devola install also install all plugins"),
    # suppressed by --no-plugins. Project-scope installs do NOT auto-install
    # plugins (kept lean; plugins are user-wide tools). Warn-not-fatal per S-5.
    if scope == "global" and not _parse_no_plugins(sys.argv[1:]):
        install_plugins(scope)

    print(f"\n  Now Using DevolaFlow v{__version__}")
    print("  Start using DevolaFlow by asking your AI tool to")
    print("  'implement a feature' or 'run a full-pipeline workflow'.\n")
