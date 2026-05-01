"""I-001 closure tests — `devola-init` works on pip-wheel-only installs.

These tests pin the v9.2.2 PV-01 surgical fix: the `devola-init` CLI
must succeed for the `local` target on a wheel-only install (no parent
``workflow-system/`` tree on disk) and must emit an *informative* error
for ``cursor`` / ``claude`` / ``codex`` / ``copilot`` targets — never
recommending the same ``pip install devolaflow`` path that landed users
in I-001 in the first place.

The fixture pattern (`_isolated_pip_wheel_repo`) simulates what a
fresh ``pip install --upgrade git+https://github.com/...`` produces:
``site-packages/devolaflow/`` exists (the wheel is importable), but
neither the CWD nor any parent of the package directory carries a
``workflow-system/agent/SKILL.md``. To force ``_find_agent_dir`` to
miss in this test suite (the in-repo dev install of DevolaFlow itself
DOES have a parent ``workflow-system/``), we monkeypatch the helper
to return a path that genuinely lacks SKILL.md.

Source artefacts:

* ``.local/feedbacks/feedback_for_v9.2.1.md`` §1 (I-001 root-cause
  reproduction).
* ``.local/research/v9.2.2_gap_analysis.md`` §1 + §2 (cycle plan).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from devolaflow import init_project
from devolaflow.init_project import AGENT_DIR_REQUIRED_TARGETS, main


@pytest.fixture
def isolated_pip_wheel_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Simulate a pip-wheel install where ``workflow-system/`` is absent.

    Three orchestration steps for every test below:

    1. Force ``_find_agent_dir`` to return a path inside ``tmp_path``
       that demonstrably lacks ``SKILL.md`` (the I-001 reproduction
       condition — the wheel doesn't bundle ``workflow-system/``).
    2. ``chdir`` into ``tmp_path`` so the CLI's ``Path.cwd()`` lands
       in a clean repo with no in-tree ``workflow-system/agent/``
       fallback either.
    3. Isolate ``HOME`` + ``CODEX_HOME`` so per-target installers that
       DO succeed (``local`` only — ``install_local`` doesn't need
       ``agent_dir``) write into ``tmp_path`` rather than into the
       developer's home directory.
    """
    fake_agent_dir = tmp_path / "_fake_site_packages_workflow_system_agent"
    fake_agent_dir.mkdir(parents=True, exist_ok=False)
    assert not (fake_agent_dir / "SKILL.md").exists(), (
        "fixture precondition: agent_dir/SKILL.md MUST be absent "
        "to reproduce the I-001 wheel-install scenario"
    )

    monkeypatch.setattr(init_project, "_find_agent_dir", lambda: fake_agent_dir)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "_isolated_home"))
    monkeypatch.delenv("CODEX_HOME", raising=False)
    return tmp_path


def test_local_target_succeeds_without_workflow_system(
    isolated_pip_wheel_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`devola-init local --no-compile` succeeds on a pip-wheel install.

    The headline I-001 closure: pre-v9.2.2 this invocation aborted
    before any per-target dispatch with the misleading "Run from the
    DevolaFlow repo root, or install with: pip install devolaflow"
    error. Post-v9.2.2 the deferred check waives ``local`` from the
    SKILL.md gate (because ``install_local`` uses
    ``scaffold_local`` + ``importlib.resources``) and the call exits
    cleanly with all 8 canonical scaffold paths created.
    """
    monkeypatch.setattr(sys, "argv", ["devola-init", "local", "--no-compile"])

    main()

    out = capsys.readouterr().out
    assert "DevolaFlow Quick Setup" in out, (
        "I-001 regression: setup banner missing — the deferred check should "
        "let `local` proceed past the banner instead of aborting"
    )
    assert "Now Using DevolaFlow" in out, (
        "I-001 regression: closing banner missing — the loop should run to "
        "completion for the `local` target on a pip-wheel install"
    )
    cwd = isolated_pip_wheel_repo
    assert (cwd / ".local").is_dir(), "I-001 regression: .local/ not scaffolded"
    assert (cwd / ".local" / "feedbacks").is_dir()
    assert (cwd / ".local" / "tasks").is_dir()
    assert (cwd / ".local" / "memory").is_dir()
    assert (cwd / ".local" / ".agent").is_dir()
    assert (cwd / ".local" / ".agent" / "active").is_dir()
    assert (cwd / ".local" / ".agent" / "handoff").is_dir()
    assert (cwd / ".local" / ".agent" / "archive").is_dir()
    assert (cwd / ".local" / "index.md").is_file()


@pytest.mark.parametrize("target", sorted(AGENT_DIR_REQUIRED_TARGETS))
def test_required_target_fails_clearly_without_workflow_system(
    isolated_pip_wheel_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    target: str,
) -> None:
    """Each agent-dir-required target exits 1 with an informative message.

    Parametrised across the full ``AGENT_DIR_REQUIRED_TARGETS`` set so
    the contract is uniform: every cursor/claude/codex/copilot dispatch
    on a pip-wheel install MUST exit 1 with the wheel-limitation hint
    + the `local` fallback + the I-001 tracking pointer.
    """
    monkeypatch.setattr(sys, "argv", ["devola-init", target])

    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 1, (
        f"I-001 contract: target {target!r} on a pip-wheel install MUST exit 1 "
        f"(got {exc_info.value.code!r})"
    )

    captured = capsys.readouterr()
    out = captured.out + captured.err
    assert f"target {target!r} needs the workflow-system/agent/ source tree" in out, (
        f"I-001 contract: error message MUST name the failing target "
        f"({target!r}) explicitly so the operator knows which install path "
        f"to follow next"
    )
    assert "The pip wheel does not bundle workflow-system/" in out, (
        "I-001 contract: error MUST cite the wheel limitation explicitly "
        "(this is the diagnosis the operator was missing pre-v9.2.2)"
    )
    assert "devola-init local" in out, (
        "I-001 contract: error MUST point operators at the `local` fallback "
        "which works on wheel-only installs"
    )
    assert "git clone" in out, (
        "I-001 contract: error MUST mention the `git clone` install path for "
        "operators who genuinely need cursor/claude/codex/copilot"
    )
    assert "I-001" in out, (
        "I-001 contract: error MUST cite the issue ID for tracking — operators "
        "filing follow-up bugs should be able to reference this surface"
    )


def test_list_succeeds_without_workflow_system(
    isolated_pip_wheel_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`devola-init --list` always succeeds (regression preserved).

    The `--list` short-circuit at the top of `main()` returns BEFORE
    the per-target dispatch loop, so it never trips the deferred check.
    This test pins that invariant — a regression here would block
    operators from inspecting their install state.
    """
    monkeypatch.setattr(sys, "argv", ["devola-init", "--list"])

    main()

    out = capsys.readouterr().out
    assert "Detected tools:" in out
    assert "Available targets:" in out
    assert "Agent source:" in out
    assert "SKILL.md exists:" in out
    assert "False" in out, (
        "regression: --list must report SKILL.md existence accurately — on a "
        "pip-wheel install the answer is False"
    )


def test_local_then_cursor_dispatches_local_before_cursor_fails(
    isolated_pip_wheel_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """When `local` is included in expanded targets, it dispatches first.

    Operators who specify multiple targets explicitly — e.g.
    ``devola-init local cursor`` — should still get the `local`
    scaffold even when a follow-up agent-dir-required target fails.
    The dispatch loop iterates in argv order; `local` first means
    `local` runs to completion before the deferred check rejects
    `cursor`.

    Closes the worry that the surgical I-001 fix would silently regress
    the multi-target dispatch path: the local scaffold MUST be visible
    on disk after the call, even though the call exits 1 due to cursor.
    """
    monkeypatch.setattr(sys, "argv", ["devola-init", "local", "cursor", "--no-compile"])

    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 1, (
        "expected exit 1 because cursor cannot dispatch on a wheel-only install"
    )

    cwd = isolated_pip_wheel_repo
    assert (cwd / ".local").is_dir(), (
        "I-001 dispatch-ordering regression: `local` must scaffold BEFORE "
        "the `cursor` deferred check fires"
    )
    assert (cwd / ".local" / "index.md").is_file(), (
        "I-001 dispatch-ordering regression: `local` scaffold must complete "
        "(index.md is written near the end of scaffold_local)"
    )

    out = capsys.readouterr().out
    assert "target 'cursor' needs the workflow-system/agent/ source tree" in out, (
        "the cursor failure must surface the v9.2.2 informative message even "
        "when local has already dispatched"
    )


def test_local_with_no_compile_pip_wheel_install_full_smoke(
    isolated_pip_wheel_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end smoke: pip-wheel install + `local --no-compile` is canonical.

    Asserts every Pre-Dispatch Contract path materialises after a
    pip-wheel-equivalent ``devola-init local --no-compile`` invocation.
    The 8-path canonical manifest mirrors the SKILL.md "Repo-Init
    Pre-Dispatch Contract" — the same checklist the user verified
    manually in `feedback_for_v9.2.1.md` after bypassing the CLI.
    """
    monkeypatch.setattr(sys, "argv", ["devola-init", "local", "--no-compile"])

    main()

    cwd = isolated_pip_wheel_repo
    canonical_paths = (
        cwd / ".local",
        cwd / ".local" / "feedbacks",
        cwd / ".local" / "tasks",
        cwd / ".local" / "memory",
        cwd / ".local" / "memory" / "specs",
        cwd / ".local" / ".agent",
        cwd / ".local" / ".agent" / "active",
        cwd / ".local" / ".agent" / "handoff",
    )
    for path in canonical_paths:
        assert path.is_dir(), (
            f"Pre-Dispatch Contract violation: required scaffold path {path} "
            f"missing after `devola-init local --no-compile`"
        )

    rules_dir = cwd / ".rules"
    assert rules_dir.is_dir(), "install_local must scaffold .rules/"
    assert (rules_dir / "compile-config.yaml").is_file(), (
        "install_local must seed the compile-config.yaml template"
    )

    cursor_rules_out = cwd / ".cursor" / "rules" / "repo-governance.mdc"
    agents_md_out = cwd / "AGENTS.md"
    assert not cursor_rules_out.exists(), (
        "--no-compile escape hatch regressed: cursor rules output must NOT "
        "be written when --no-compile is set"
    )
    assert not agents_md_out.exists(), (
        "--no-compile escape hatch regressed: AGENTS.md must NOT be written "
        "when --no-compile is set"
    )


def test_error_message_does_not_recommend_pip_install(
    isolated_pip_wheel_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Regression lint: error message MUST NOT recommend `pip install devolaflow`.

    The pre-v9.2.2 error message ended with::

        Run from the DevolaFlow repo root, or install with:
          pip install devolaflow

    …which silently landed users in I-001 because they had ALREADY done
    `pip install` (that's how they got the broken CLI in the first
    place). The v9.2.2 fix MUST avoid recommending the same install
    path; the new message recommends `devola-init local` (works on a
    wheel install) or `git clone + pip install -e .` (which DOES
    bundle workflow-system/).

    A regression here would re-introduce the misleading recommendation
    that motivated the entire I-001 cycle.
    """
    monkeypatch.setattr(sys, "argv", ["devola-init", "cursor"])

    with pytest.raises(SystemExit):
        main()

    captured = capsys.readouterr()
    out = captured.out + captured.err
    assert "pip install devolaflow" not in out, (
        "I-001 regression: error message MUST NOT recommend "
        "`pip install devolaflow` — that's the install path that landed "
        "operators in I-001. Use `devola-init local` (works on wheel "
        "install) or `git clone + pip install -e .` (bundles "
        "workflow-system/) instead."
    )
    assert "pip install --upgrade git+" not in out, (
        "I-001 regression: error message MUST NOT recommend the "
        "`pip install --upgrade git+...` path either — same misleading "
        "loop reason"
    )
