"""Tests for devola-init project initialization."""

import sys
from pathlib import Path

import pytest

from devolaflow import init_project
from devolaflow.init_project import (
    AGENT_DIR_REQUIRED_TARGETS,
    _auto_detect,
    _find_agent_dir,
    _parse_scope,
)


def test_find_agent_dir():
    agent_dir = _find_agent_dir()
    assert (agent_dir / "SKILL.md").exists() or not agent_dir.exists()


def test_auto_detect_empty(tmp_path: Path):
    result = _auto_detect(tmp_path)
    assert isinstance(result, list)


def test_auto_detect_cursor(tmp_path: Path):
    (tmp_path / ".cursor").mkdir()
    result = _auto_detect(tmp_path)
    assert "cursor" in result


def test_auto_detect_github(tmp_path: Path):
    (tmp_path / ".github").mkdir()
    result = _auto_detect(tmp_path)
    assert "copilot" in result


def test_auto_detect_claude(tmp_path: Path):
    (tmp_path / ".claude").mkdir()
    result = _auto_detect(tmp_path)
    assert "claude" in result


def test_parse_scope_defaults_to_project():
    assert _parse_scope([]) == "project"


def test_parse_scope_uses_last_flag():
    assert _parse_scope(["--global"]) == "global"
    assert _parse_scope(["--global", "--project"]) == "project"
    assert _parse_scope(["--project", "--global"]) == "global"


def test_install_cursor(tmp_path: Path, monkeypatch: Path):
    agent_dir = _find_agent_dir()
    if not (agent_dir / "SKILL.md").exists():
        return

    from devolaflow.init_project import install_cursor

    install_cursor(agent_dir, tmp_path)
    assert (tmp_path / ".cursor" / "skills" / "devola-flow" / "SKILL.md").exists()
    refs = list((tmp_path / ".cursor" / "skills" / "devola-flow" / "references").glob("*.md"))
    assert len(refs) >= 7


def test_install_cursor_global(tmp_path: Path, monkeypatch):
    agent_dir = _find_agent_dir()
    if not (agent_dir / "SKILL.md").exists():
        return

    from devolaflow.init_project import install_cursor

    monkeypatch.setenv("HOME", str(tmp_path))
    install_cursor(agent_dir, tmp_path / "project", scope="global")
    assert (tmp_path / ".cursor" / "skills" / "devola-flow" / "SKILL.md").exists()
    # The legacy devola-flow-rules.mdc copy retired at v15.0.0 (clean_repo
    # C1-2, decision D1) together with its workflow-rules.mdc stub source.
    assert not (tmp_path / ".cursor" / "rules" / "devola-flow-rules.mdc").exists()


def test_install_claude(tmp_path: Path):
    agent_dir = _find_agent_dir()
    if not (agent_dir / "SKILL.md").exists():
        return

    from devolaflow.init_project import install_claude

    install_claude(agent_dir, tmp_path)
    skill = tmp_path / ".claude" / "skills" / "devola-flow" / "SKILL.md"
    assert skill.exists()
    refs = list((tmp_path / ".claude" / "skills" / "devola-flow" / "references").glob("*.md"))
    assert len(refs) >= 7


def test_install_claude_global(tmp_path: Path, monkeypatch):
    agent_dir = _find_agent_dir()
    if not (agent_dir / "SKILL.md").exists():
        return

    from devolaflow.init_project import install_claude

    monkeypatch.setenv("HOME", str(tmp_path))
    install_claude(agent_dir, tmp_path / "project", scope="global")
    skill = tmp_path / ".claude" / "skills" / "devola-flow" / "SKILL.md"
    assert skill.exists()
    content = skill.read_text()
    assert "DevolaFlow" in content


def test_install_copilot(tmp_path: Path):
    agent_dir = _find_agent_dir()
    if not (agent_dir / "SKILL.md").exists():
        return

    from devolaflow.init_project import install_copilot

    install_copilot(agent_dir, tmp_path)
    assert (tmp_path / ".github" / "copilot-instructions.md").exists()


def test_auto_detect_local_when_missing(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    result = _auto_detect(tmp_path)
    assert "local" in result


def test_auto_detect_no_local_when_present(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".local").mkdir()
    result = _auto_detect(tmp_path)
    assert "local" not in result


def test_auto_detect_local_idempotent(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    first = _auto_detect(tmp_path)
    assert "local" in first

    from devolaflow.init_project import install_local

    install_local(_find_agent_dir(), tmp_path)
    second = _auto_detect(tmp_path)
    assert "local" not in second


def test_main_with_no_local_scaffolds_workspace(tmp_path: Path, monkeypatch):
    agent_dir = _find_agent_dir()
    if not (agent_dir / "SKILL.md").exists():
        return

    (tmp_path / ".cursor").mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "_home"))
    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.setattr(sys, "argv", ["devola-init"])

    from devolaflow.init_project import main

    main()

    assert (tmp_path / ".local" / "feedbacks").is_dir()
    assert (tmp_path / ".local" / "tasks").is_dir()
    assert (tmp_path / ".local" / "index.md").is_file()
    assert (tmp_path / ".cursor" / "skills" / "devola-flow" / "SKILL.md").exists()


def test_install_codex(tmp_path: Path, monkeypatch):
    agent_dir = _find_agent_dir()
    if not (agent_dir / "SKILL.md").exists():
        return

    from devolaflow.init_project import install_codex

    monkeypatch.setenv("CODEX_HOME", str(tmp_path / ".codex"))
    install_codex(agent_dir, tmp_path)
    skill = tmp_path / ".codex" / "skills" / "devola-flow" / "SKILL.md"
    assert skill.exists()


def test_install_local_with_existing_rules_dir(tmp_path: Path):
    agent_dir = _find_agent_dir()
    if not (agent_dir / "SKILL.md").exists():
        return

    from devolaflow.init_project import install_local

    (tmp_path / ".rules").mkdir()
    install_local(agent_dir, tmp_path)
    assert (tmp_path / ".local" / "feedbacks").is_dir()
    assert (tmp_path / ".rules").is_dir()
    assert (tmp_path / ".rules" / "compile-config.yaml").is_file()


def test_install_local_creates_compile_config_in_fresh_dir(tmp_path: Path):
    """G-J1 closure: install_local() scaffolds a default compile-config.yaml.

    Closes the v7.4.0 circular UX dead-end where ``sync-rules`` demanded a
    config that ``devola-init`` itself never produced (audit §3.J G-J1).
    """
    agent_dir = _find_agent_dir()
    if not (agent_dir / "SKILL.md").exists():
        return

    from devolaflow.init_project import install_local

    install_local(agent_dir, tmp_path)
    config_path = tmp_path / ".rules" / "compile-config.yaml"
    assert config_path.is_file(), "install_local must scaffold .rules/compile-config.yaml"


def test_install_local_compile_config_is_idempotent(tmp_path: Path):
    """G-J1 idempotency: second invocation MUST NOT overwrite existing config."""
    agent_dir = _find_agent_dir()
    if not (agent_dir / "SKILL.md").exists():
        return

    from devolaflow.init_project import install_local

    install_local(agent_dir, tmp_path)
    config_path = tmp_path / ".rules" / "compile-config.yaml"
    user_marker = '# user-edited config; do not regenerate\nversion: "99.99"\n'
    config_path.write_text(user_marker, encoding="utf-8")

    install_local(agent_dir, tmp_path)
    assert config_path.read_text(encoding="utf-8") == user_marker, (
        "install_local must NOT overwrite an existing compile-config.yaml"
    )


def test_install_local_compile_config_is_valid_yaml_and_consumable(tmp_path: Path):
    """G-J1 acceptance: the scaffolded config must parse via RuleCompiler.

    Mirrors the ``sync-rules`` execution path — RuleCompiler.compile_all()
    must not raise on the freshly-scaffolded config (closes the silent UX
    dead-end from audit §3.J G-J1 / S-5).
    """
    import yaml

    from devolaflow.init_project import install_local
    from devolaflow.local.compiler import RuleCompiler

    agent_dir = _find_agent_dir()
    if not (agent_dir / "SKILL.md").exists():
        return

    install_local(agent_dir, tmp_path)
    config_path = tmp_path / ".rules" / "compile-config.yaml"

    parsed = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert isinstance(parsed, dict), "compile-config.yaml must parse to a mapping"
    assert "version" in parsed and "layers" in parsed and "targets" in parsed

    compiler = RuleCompiler(config_path)
    results = compiler.compile_all()
    assert isinstance(results, list), "RuleCompiler.compile_all must return a list"


def test_install_local_then_sync_rules_does_not_dead_end(tmp_path: Path, monkeypatch):
    """G-J1 UX closure: sync_rules_cmd() must NOT exit 1 after install_local.

    Pre-v7.4.10: ``devola-init local`` left ``.rules/`` empty, so
    ``sync-rules`` printed "No .rules/compile-config.yaml found." and
    exited 1. Post-v7.4.10: install_local scaffolds the config, so
    sync-rules proceeds to compile_all() without dead-ending.
    """
    from devolaflow.cli import sync_rules_cmd
    from devolaflow.init_project import install_local

    agent_dir = _find_agent_dir()
    if not (agent_dir / "SKILL.md").exists():
        return

    install_local(agent_dir, tmp_path)
    monkeypatch.chdir(tmp_path)
    sync_rules_cmd()


def test_install_local_compiles_rules(tmp_path: Path):
    """G-007 + G-016 closure (v9.1.0 W2-02): install_local auto-compiles .rules/.

    Pre-v9.1.0: ``devola-init local`` only seeded the compile config and
    left compilation as a separate ``devola-init sync-rules`` step that
    fresh-repo operators frequently missed, leaving Cursor and Codex
    agents without compiled governance. Post-v9.1.0: install_local
    chains ``RuleCompiler.compile_all()`` so the cursor target
    (``.cursor/rules/repo-governance.mdc``) and the agents_md target
    (``AGENTS.md``) materialise on the same invocation.

    This test pre-seeds a richer compile-config.yaml (cursor + agents_md
    targets, single soul layer) into ``tmp_path/.rules/`` BEFORE calling
    install_local — the install_local config-seeding step then SKIPs
    template overwrite (idempotent) and the new auto-compile step writes
    both target outputs.
    """
    import yaml

    agent_dir = _find_agent_dir()
    if not (agent_dir / "SKILL.md").exists():
        return

    from devolaflow.init_project import install_local

    rules_dir = tmp_path / ".rules"
    rules_dir.mkdir()
    (rules_dir / "soul.mdc").write_text(
        '---\ndescription: "Soul"\nalwaysApply: true\n---\n\n'
        "# Soul\n\n## S-1 — Test rule\n\nMinimal content for compile.\n",
        encoding="utf-8",
    )
    config = {
        "version": "1.0",
        "source_dir": ".rules",
        "layers": [
            {"name": "soul", "priority": 0, "always_include": True},
        ],
        "targets": {
            "cursor": {
                "output": ".cursor/rules/repo-governance.mdc",
                "format": "mdc",
                "token_budget": 8000,
                "include_layers": ["soul"],
                "frontmatter": {
                    "description": "Compiled governance rules",
                    "alwaysApply": True,
                },
            },
            "agents_md": {
                "output": "AGENTS.md",
                "format": "markdown",
                "token_budget": 6000,
                "include_layers": ["soul"],
            },
        },
    }
    (rules_dir / "compile-config.yaml").write_text(
        yaml.dump(config, default_flow_style=False), encoding="utf-8"
    )

    install_local(agent_dir, tmp_path)

    cursor_out = tmp_path / ".cursor" / "rules" / "repo-governance.mdc"
    agents_out = tmp_path / "AGENTS.md"
    assert cursor_out.exists(), "install_local must auto-compile the cursor target"
    assert agents_out.exists(), "install_local must auto-compile the agents_md target"
    assert cursor_out.stat().st_size > 0, "cursor output must not be empty"
    assert agents_out.stat().st_size > 0, "AGENTS.md must not be empty"


def test_install_local_no_compile_flag_skips(tmp_path: Path):
    """G-007 + G-016 escape hatch: ``compile_rules=False`` skips auto-compile.

    Mirrors the ``devola-init local --no-compile`` CLI path. Asserts that
    scaffold + config seeding still run (so the operator can hand-edit
    the seeded ``compile-config.yaml`` before any compile happens) but
    the cursor + AGENTS.md targets are NOT written, proving the
    ``--no-compile`` opt-out is wired through to the compile step.
    """
    import yaml

    agent_dir = _find_agent_dir()
    if not (agent_dir / "SKILL.md").exists():
        return

    from devolaflow.init_project import install_local

    rules_dir = tmp_path / ".rules"
    rules_dir.mkdir()
    (rules_dir / "soul.mdc").write_text(
        '---\ndescription: "Soul"\nalwaysApply: true\n---\n\n'
        "# Soul\n\n## S-1 — Test rule\n\nMinimal content.\n",
        encoding="utf-8",
    )
    config = {
        "version": "1.0",
        "source_dir": ".rules",
        "layers": [{"name": "soul", "priority": 0, "always_include": True}],
        "targets": {
            "cursor": {
                "output": ".cursor/rules/repo-governance.mdc",
                "format": "mdc",
                "token_budget": 8000,
                "include_layers": ["soul"],
            },
            "agents_md": {
                "output": "AGENTS.md",
                "format": "markdown",
                "token_budget": 6000,
                "include_layers": ["soul"],
            },
        },
    }
    (rules_dir / "compile-config.yaml").write_text(
        yaml.dump(config, default_flow_style=False), encoding="utf-8"
    )

    install_local(agent_dir, tmp_path, compile_rules=False)

    assert (tmp_path / ".local").is_dir(), "scaffold must still run with compile_rules=False"
    assert (tmp_path / ".rules" / "compile-config.yaml").is_file(), (
        "config seeding must still run with compile_rules=False"
    )
    assert not (tmp_path / "AGENTS.md").exists(), (
        "compile_rules=False must skip the AGENTS.md auto-compile"
    )
    assert not (tmp_path / ".cursor" / "rules" / "repo-governance.mdc").exists(), (
        "compile_rules=False must skip the cursor auto-compile"
    )


def test_main_list_flag(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "_home"))
    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.setattr(sys, "argv", ["devola-init", "--list"])

    from devolaflow.init_project import main

    main()
    out = capsys.readouterr().out
    assert "Detected tools:" in out
    assert "local" in out
    assert "Available targets:" in out


# ── v9.2.2 PV-01 — I-001 deferred-check regression assertions ───────


def test_main_local_target_succeeds_without_skill_md(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """v9.2.2 I-001 closure: `devola-init local` MUST succeed when SKILL.md is absent.

    Pre-v9.2.2 ``main()`` aborted unconditionally on a missing
    ``agent_dir / "SKILL.md"`` BEFORE dispatching to any per-target
    installer. This assertion pins the deferred-check fix: when the
    user requests only the ``local`` target — which uses
    ``scaffold_local`` + ``importlib.resources`` and has zero
    dependency on ``agent_dir`` — the call must complete successfully
    even though SKILL.md is genuinely absent.

    This is a regression sentinel for the I-001 critical fix; the
    parallel parametrized + explicit-message assertions live in
    ``tests/test_init_project_pip_wheel.py``.
    """
    fake_agent_dir = tmp_path / "_no_skill_md_here"
    fake_agent_dir.mkdir()
    assert not (fake_agent_dir / "SKILL.md").exists()

    monkeypatch.setattr(init_project, "_find_agent_dir", lambda: fake_agent_dir)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "_home"))
    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.setattr(sys, "argv", ["devola-init", "local", "--no-compile"])

    from devolaflow.init_project import main

    main()

    out = capsys.readouterr().out
    assert "Now Using DevolaFlow" in out, (
        "I-001 regression: `local` target must run to completion when "
        "SKILL.md is absent (deferred-check fix)"
    )
    assert (tmp_path / ".local").is_dir(), (
        "I-001 regression: scaffold_local must run for the `local` target "
        "even without workflow-system/"
    )


def test_agent_dir_required_targets_membership_pinned():
    """v17.4.0 surface pin: all guaranteed hosts need agent source files.

    The deferred-check gate is keyed off this constant; adding (or
    removing) a target here changes which dispatch paths require the
    on-disk ``workflow-system/agent/`` tree. Membership MUST stay at
    exactly the 6 guaranteed host consumers (cursor / claude / copilot /
    codex / kimicode / dsh). ``local`` is intentionally absent (the I-001
    closure invariant).

    A regression here would silently widen or narrow the deferred-check
    surface — caught here BEFORE the W-18 ghost-audit lint runs.
    """
    expected = frozenset({"cursor", "claude", "copilot", "codex", "kimicode", "dsh"})
    assert expected == AGENT_DIR_REQUIRED_TARGETS, (
        f"v9.2.2 I-001 surface drift: AGENT_DIR_REQUIRED_TARGETS = "
        f"{AGENT_DIR_REQUIRED_TARGETS!r}; expected exactly "
        f"{expected!r}"
    )
    assert "local" not in AGENT_DIR_REQUIRED_TARGETS, (
        "v9.2.2 I-001 invariant violation: `local` MUST NOT appear in "
        "AGENT_DIR_REQUIRED_TARGETS — install_local uses scaffold_local + "
        "importlib.resources and has zero dependency on agent_dir"
    )


# ── v9.2.3 PV-02 — `default=` kwarg backward-compat regressions ─────


def test_parse_no_compile_default_kwarg_signature() -> None:
    """v9.2.3 PV-02: ``_parse_no_compile`` accepts ``default=`` keyword-only.

    The shorthand ``--mode={core,standard,full}`` resolver feeds a
    mode-derived default (e.g. ``--mode=core`` sets ``default=True``
    to imply ``--no-compile``). The new kwarg is keyword-only and
    defaults to ``False`` so every pre-v9.2.3 direct caller continues
    to behave byte-identically.

    Sanity-pinned cases:

    * ``argv=[]`` + ``default=False`` → ``False`` (legacy default).
    * ``argv=[]`` + ``default=True`` → ``True`` (mode-derived path).
    * ``argv=["--no-compile"]`` + ``default=False`` → ``True``
      (explicit flag wins).
    * ``argv=["--no-compile"]`` + ``default=True`` → ``True``
      (explicit flag agrees with mode-derived default — both paths
      converge on ``True``; redundant but legal).
    """
    from devolaflow.init_project import _parse_no_compile

    assert _parse_no_compile([]) is False, (
        "regression: bare argv must keep the pre-v9.2.3 False default"
    )
    assert _parse_no_compile([], default=False) is False, (
        "explicit default=False must match the legacy default"
    )
    assert _parse_no_compile([], default=True) is True, (
        "v9.2.3 PV-02: --mode=core sets default=True to imply --no-compile"
    )
    assert _parse_no_compile(["--no-compile"]) is True, (
        "regression: --no-compile must still resolve to True"
    )
    assert _parse_no_compile(["--no-compile"], default=False) is True, (
        "explicit flag must beat default=False"
    )
    assert _parse_no_compile(["--no-compile"], default=True) is True, (
        "explicit flag agrees with default=True; both resolve to True"
    )


def test_parse_with_examples_default_kwarg_signature() -> None:
    """v9.2.3 PV-02: ``_parse_with_examples`` accepts ``default=`` keyword-only.

    The kwarg is ``bool | None`` because the legacy fallback uses
    ``"all" in targets`` as the implicit default. ``default=None``
    preserves the pre-v9.2.3 behaviour byte-identically:

    * ``argv=[]``, ``targets=["local"]``, ``default=None`` → ``False``
      (no ``"all"`` in targets → fallback returns False)
    * ``argv=[]``, ``targets=["all"]``, ``default=None`` → ``True``
      (the implicit-matrix default-ON for ``mode: full``).
    * ``argv=[]``, ``targets=["local"]``, ``default=True`` → ``True``
      (mode-derived default — bypasses the fallback).
    * ``argv=["--with-examples"]`` + any default → ``True`` (explicit
      wins).
    * ``argv=["--no-with-examples"]`` + any default → ``False``
      (explicit wins; AC #5 explicit-beats-implicit).
    """
    from devolaflow.init_project import _parse_with_examples

    assert _parse_with_examples([], ["local"]) is False, (
        "regression: no flag + no `all` + no default → False (legacy fallback)"
    )
    assert _parse_with_examples([], ["all"]) is True, (
        "regression: no flag + `all` in targets → True (legacy fallback)"
    )
    assert _parse_with_examples([], ["local"], default=None) is False, (
        "explicit default=None must match the legacy fallback"
    )
    assert _parse_with_examples([], ["local"], default=False) is False, (
        "v9.2.3 PV-02: --mode=core / --mode=standard set default=False"
    )
    assert _parse_with_examples([], ["local"], default=True) is True, (
        "v9.2.3 PV-02: --mode=full sets default=True to imply --with-examples"
    )

    for default_val in (None, False, True):
        assert _parse_with_examples(["--with-examples"], ["local"], default=default_val) is True, (
            f"explicit --with-examples must beat default={default_val!r}"
        )
        assert (
            _parse_with_examples(["--no-with-examples"], ["all"], default=default_val) is False
        ), f"explicit --no-with-examples must beat default={default_val!r}"


# ── v9.2.3 PV-02 — backward-compat regressions for the new default= kwargs ──


def test_parse_no_compile_default_kwarg_preserves_pre_v9_2_3_behavior():
    """v9.2.3 PV-02: `_parse_no_compile(argv)` returns False without `--no-compile`.

    The `default=` kwarg landed in PV-02 to let `_parse_mode` feed
    mode-derived defaults into the per-flag resolver. The default value
    `default=False` MUST preserve the pre-v9.2.3 behaviour for every
    direct caller that omits the kwarg — when this test passes, every
    pre-v9.2.3 call site (CLI, fixtures, downstream tooling) gets the
    same boolean it always did.
    """
    from devolaflow.init_project import _parse_no_compile

    assert _parse_no_compile([]) is False, (
        "v9.2.3 backward-compat: `_parse_no_compile([])` MUST return False "
        "(the pre-v9.2.3 default; caller passes no `default=` kwarg)"
    )
    assert _parse_no_compile(["local"]) is False, (
        "v9.2.3 backward-compat: argv without `--no-compile` MUST return False"
    )
    assert _parse_no_compile(["local", "--no-compile"]) is True, (
        "v9.2.3 contract: explicit `--no-compile` overrides the default"
    )
    assert _parse_no_compile([], default=True) is True, (
        "v9.2.3 contract: mode-derived `default=True` (mode=core) is honoured"
    )
    assert _parse_no_compile(["--no-compile"], default=False) is True, (
        "v9.2.3 contract: explicit `--no-compile` beats default=False"
    )


def test_parse_with_examples_default_kwarg_preserves_pre_v9_2_3_behavior():
    """v9.2.3 PV-02: `_parse_with_examples` falls back to `"all" in targets` by default.

    The `default=None` sentinel preserves the pre-v9.2.3 PV-06 fallback
    — when the operator passes neither `--with-examples` nor
    `--no-with-examples` AND no `--mode=` flag, the resolver falls back
    to the historical "True iff `all` is in the targets list" rule.
    Mode-derived defaults (`default=True` / `default=False`) override
    the fallback per the PV-02 dispatch contract.
    """
    from devolaflow.init_project import _parse_with_examples

    # default=None (omitted): pre-v9.2.3 "all in targets" behaviour
    assert _parse_with_examples([], ["local"]) is False, (
        "v9.2.3 backward-compat: narrow targets without `all` → False (default)"
    )
    assert _parse_with_examples([], ["all"]) is True, (
        "v9.2.3 backward-compat: `all` keyword target → True (default)"
    )
    assert _parse_with_examples(["--with-examples"], ["local"]) is True, (
        "v9.2.3 contract: explicit `--with-examples` beats narrow targets"
    )
    assert _parse_with_examples(["--no-with-examples"], ["all"]) is False, (
        "v9.2.3 contract: explicit `--no-with-examples` beats `all` keyword"
    )
    # Mode-derived defaults override the "all in targets" fallback
    assert _parse_with_examples([], ["local"], default=True) is True, (
        "v9.2.3 contract: mode-derived default=True (mode=full) is honoured"
    )
    assert _parse_with_examples([], ["all"], default=False) is False, (
        "v9.2.3 contract: mode-derived default=False (mode=core/standard) is "
        "honoured even when `all` would otherwise have implied True"
    )


# ---------------------------------------------------------------------------
# v13.0.0 — bundled runtime-plugin install (install_plugins + --no-plugins)
# ---------------------------------------------------------------------------


def _run_main_recording_install_plugins(tmp_path, monkeypatch, argv):
    """Run init_project.main() with install_plugins() mocked; return scope calls."""
    agent_dir = _find_agent_dir()
    if not (agent_dir / "SKILL.md").exists():
        pytest.skip("workflow-system/agent/ source tree not available (wheel-only)")
    (tmp_path / ".cursor").mkdir(exist_ok=True)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "_home"))
    monkeypatch.delenv("CODEX_HOME", raising=False)
    calls: list[str] = []
    monkeypatch.setattr(init_project, "install_plugins", lambda scope: calls.append(scope))
    monkeypatch.setattr(sys, "argv", argv)
    from devolaflow.init_project import main

    main()
    return calls


def test_main_global_triggers_install_plugins(tmp_path: Path, monkeypatch):
    """v13.0.0: a --global skill install ALSO installs runtime plugins."""
    calls = _run_main_recording_install_plugins(
        tmp_path, monkeypatch, ["devola-init", "cursor", "--global"]
    )
    assert calls == ["global"], (
        f"--global install must call install_plugins('global') exactly once; got {calls}"
    )


def test_main_global_no_plugins_skips_install_plugins(tmp_path: Path, monkeypatch):
    """v13.0.0: --no-plugins suppresses the bundled plugin install."""
    calls = _run_main_recording_install_plugins(
        tmp_path, monkeypatch, ["devola-init", "cursor", "--global", "--no-plugins"]
    )
    assert calls == [], f"--no-plugins must skip install_plugins; got {calls}"


def test_main_project_scope_does_not_install_plugins(tmp_path: Path, monkeypatch):
    """v13.0.0: project-scope installs stay lean (no bundled plugin install)."""
    calls = _run_main_recording_install_plugins(tmp_path, monkeypatch, ["devola-init", "cursor"])
    assert calls == [], f"project-scope install must not call install_plugins; got {calls}"


def test_parse_no_plugins_flag():
    """`--no-plugins` is detected only when present."""
    from devolaflow.init_project import _parse_no_plugins

    assert _parse_no_plugins(["cursor", "--global", "--no-plugins"]) is True
    assert _parse_no_plugins(["cursor", "--global"]) is False
    assert _parse_no_plugins([]) is False


def test_install_plugins_warn_not_fatal(monkeypatch, capsys):
    """A failing plugin is warned (S-5) and does NOT abort the loop."""
    from devolaflow.plugins.exceptions import PluginInstallError

    def _fake_ensure(pid: str, **_kwargs: object) -> str:
        if pid == "codegraph":
            raise PluginInstallError("network down")
        return "9.9.9"

    monkeypatch.setattr("devolaflow.plugins.installer.ensure_plugin", _fake_ensure)
    init_project.install_plugins("global")
    out = capsys.readouterr().out
    assert "WARN plugin codegraph install failed" in out
    assert "impeccable @ 9.9.9" in out  # loop continued past the codegraph failure
