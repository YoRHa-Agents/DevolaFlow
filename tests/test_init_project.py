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
    assert (tmp_path / ".cursor" / "rules" / "devola-flow-rules.mdc").exists()


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
    """v9.2.2 I-001 surface pin: AGENT_DIR_REQUIRED_TARGETS = exact 4 targets.

    The deferred-check gate is keyed off this constant; adding (or
    removing) a target here changes which dispatch paths require the
    on-disk ``workflow-system/agent/`` tree. Membership MUST stay at
    exactly the 4 historical agent-dir consumers (cursor / claude /
    copilot / codex). ``local`` is intentionally absent (the I-001
    closure invariant).

    A regression here would silently widen or narrow the deferred-check
    surface — caught here BEFORE the W-18 ghost-audit lint runs.
    """
    assert frozenset({"cursor", "claude", "copilot", "codex"}) == AGENT_DIR_REQUIRED_TARGETS, (
        f"v9.2.2 I-001 surface drift: AGENT_DIR_REQUIRED_TARGETS = "
        f"{AGENT_DIR_REQUIRED_TARGETS!r}; expected exactly "
        f"frozenset({{'cursor', 'claude', 'copilot', 'codex'}})"
    )
    assert "local" not in AGENT_DIR_REQUIRED_TARGETS, (
        "v9.2.2 I-001 invariant violation: `local` MUST NOT appear in "
        "AGENT_DIR_REQUIRED_TARGETS — install_local uses scaffold_local + "
        "importlib.resources and has zero dependency on agent_dir"
    )
