"""Exercise stub modules and CLI entrypoints for coverage (pyproject fail_under)."""

import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def test_stub_helpers():
    from devolaflow.build_skill import build_all
    from devolaflow.check_drift import check_drift
    from devolaflow.gate.scorer import run_gate_cli
    from devolaflow.pre_decision.detect import detect_and_print
    from devolaflow.template_engine.validator import validate_all_templates

    assert check_drift() is False
    assert validate_all_templates(False) is True
    assert validate_all_templates(True) is True

    buf = io.StringIO()
    with redirect_stdout(buf):
        detect_and_print()
    output = buf.getvalue().strip().split("\n")[0]
    assert output in ("local", "github", "gitlab", "gitea", "bitbucket", "generic")

    buf2 = io.StringIO()
    with redirect_stdout(buf2):
        build_all([])
        run_gate_cli([])


def test_validate_template_cmd(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["validate-template", "--all"])
    from devolaflow.cli import validate_template_cmd

    with pytest.raises(SystemExit) as exc:
        validate_template_cmd()
    assert exc.value.code == 0


def test_validate_gate_cmd(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["validate-gate", "x"])
    from devolaflow.cli import validate_gate_cmd

    validate_gate_cmd()


def test_build_skill_cmd(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["build-skill"])
    from devolaflow.cli import build_skill_cmd

    build_skill_cmd()


def test_check_drift_cmd(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["check-drift"])
    from devolaflow.cli import check_drift_cmd

    with pytest.raises(SystemExit) as exc:
        check_drift_cmd()
    assert exc.value.code == 0


def test_detect_repo_mode_cmd(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["detect-repo-mode"])
    from devolaflow.cli import detect_repo_mode_cmd

    buf = io.StringIO()
    with redirect_stdout(buf):
        detect_repo_mode_cmd()
    output = buf.getvalue().strip().split("\n")[0]
    assert output in ("local", "github", "gitlab", "gitea", "bitbucket", "generic")


# ── v6.1.0 C4 coverage: devolaflow.cli ──────────────────────────────────────


def test_version_cmd(capsys):
    from devolaflow import __version__
    from devolaflow.cli import version_cmd

    version_cmd()
    out = capsys.readouterr().out.strip()
    assert __version__ in out
    assert out.startswith("DevolaFlow v")


def test_cli_validate_template_single_path(monkeypatch, capsys):
    """Single-path branch: valid template prints PASS and exits 0."""
    template_path = FIXTURES / "research_only.yaml"
    assert template_path.exists()
    monkeypatch.setattr(sys, "argv", ["validate-template", str(template_path)])
    from devolaflow.cli import validate_template_cmd

    with pytest.raises(SystemExit) as exc:
        validate_template_cmd()
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "PASS" in out


def test_cli_validate_template_all_flag(monkeypatch):
    """The --all branch exits with 0 when every builtin template validates."""
    monkeypatch.setattr(sys, "argv", ["validate-template", "--all"])
    from devolaflow.cli import validate_template_cmd

    with pytest.raises(SystemExit) as exc:
        validate_template_cmd()
    assert exc.value.code == 0


def test_cli_validate_template_missing_file(monkeypatch, tmp_path, capsys):
    """Missing file prints ``FAIL`` and exits 1."""
    missing = tmp_path / "not_a_template.yaml"
    monkeypatch.setattr(sys, "argv", ["validate-template", str(missing)])
    from devolaflow.cli import validate_template_cmd

    with pytest.raises(SystemExit) as exc:
        validate_template_cmd()
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "FAIL" in out
    assert "file not found" in out


def test_cli_validate_template_no_args_exits_1(monkeypatch, capsys):
    """With no positional arg and no --all, cmd prints usage and exits 1."""
    monkeypatch.setattr(sys, "argv", ["validate-template"])
    from devolaflow.cli import validate_template_cmd

    with pytest.raises(SystemExit) as exc:
        validate_template_cmd()
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "Usage" in out


def test_cli_validate_template_parse_error(monkeypatch, tmp_path, capsys):
    """Unparseable YAML triggers the parse-error branch and exits 1."""
    bad = tmp_path / "bad.yaml"
    bad.write_text("schema_version: '1.0'\nmetadata: [unclosed\n")
    monkeypatch.setattr(sys, "argv", ["validate-template", str(bad)])
    from devolaflow.cli import validate_template_cmd

    with pytest.raises(SystemExit) as exc:
        validate_template_cmd()
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "FAIL" in out


def test_cli_validate_template_invalid_content(monkeypatch, capsys):
    """A parseable-but-invalid template hits the invalid-result branch."""
    invalid_template = FIXTURES / "invalid_missing_stage_ref.yaml"
    assert invalid_template.exists()
    monkeypatch.setattr(sys, "argv", ["validate-template", str(invalid_template)])
    from devolaflow.cli import validate_template_cmd

    with pytest.raises(SystemExit) as exc:
        validate_template_cmd()
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "FAIL" in out


def test_cli_build_skill_cmd_no_tools(monkeypatch, tmp_path, capsys):
    """build_skill_cmd without --tools builds all registered adapters."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["build-skill"])
    from devolaflow.cli import build_skill_cmd

    build_skill_cmd()
    out = capsys.readouterr().out
    assert "cursor" in out
    assert "claude" in out


def test_cli_build_skill_cmd_with_tools(monkeypatch, tmp_path, capsys):
    """build_skill_cmd with --tools cursor builds only Cursor."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["build-skill", "--tools", "cursor"])
    from devolaflow.cli import build_skill_cmd

    build_skill_cmd()
    out = capsys.readouterr().out
    assert "cursor" in out
    assert "1 total" in out or "1 passed" in out


def test_cli_check_drift_cmd_no_drift(monkeypatch):
    """check_drift_cmd passes (exit 0) when no drift is present."""
    monkeypatch.setattr(sys, "argv", ["check-drift"])
    from devolaflow.cli import check_drift_cmd

    with pytest.raises(SystemExit) as exc:
        check_drift_cmd()
    assert exc.value.code == 0


# ── v6.1.0 C4 coverage: devolaflow.init_project ─────────────────────────────


def test_init_project_list_target_types(monkeypatch, tmp_path, capsys):
    """``--list`` must print detected tools + available targets and return."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["devola-init", "--list"])
    from devolaflow.init_project import main

    main()
    out = capsys.readouterr().out
    assert "Detected tools" in out
    assert "Available targets" in out
    assert "cursor" in out and "claude" in out and "copilot" in out and "codex" in out


def test_init_project_unknown_target_errors(monkeypatch, tmp_path, capsys):
    """An unknown target prints a friendly error without raising."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["devola-init", "not-a-real-tool"])
    from devolaflow.init_project import main

    main()
    out = capsys.readouterr().out
    assert "Unknown target" in out
    assert "not-a-real-tool" in out


def test_init_project_all_target(monkeypatch, tmp_path, capsys):
    """``all`` expands to the full TOOLS dict — every registered installer runs."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["devola-init", "all"])
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / ".codex"))
    from devolaflow.init_project import main

    main()
    out = capsys.readouterr().out
    # All 4 built-in installers should leave a trace in stdout.
    assert "Cursor" in out
    assert "Claude" in out
    assert "Copilot" in out
    assert "Codex" in out


def test_init_project_missing_agent_dir(monkeypatch, tmp_path, capsys):
    """When SKILL.md source cannot be found, main exits with code 1."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["devola-init", "cursor"])
    fake_missing = tmp_path / "no_such_dir"
    import devolaflow.init_project as ip

    monkeypatch.setattr(ip, "_find_agent_dir", lambda: fake_missing)

    with pytest.raises(SystemExit) as exc:
        ip.main()
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "Agent source not found" in out


def test_init_project_copilot_global_note(monkeypatch, tmp_path, capsys):
    """install_copilot prints its no-global-support note when scope=global."""
    from devolaflow.init_project import _find_agent_dir, install_copilot

    agent_dir = _find_agent_dir()
    if not (agent_dir / "SKILL.md").exists():
        pytest.skip("requires an installed DevolaFlow agent source tree to cover")

    install_copilot(agent_dir, tmp_path, scope="global")
    out = capsys.readouterr().out
    assert "does not support a global install" in out
    assert (tmp_path / ".github" / "copilot-instructions.md").exists()


def test_init_project_codex(monkeypatch, tmp_path, capsys):
    """install_codex copies SKILL.md + references into $CODEX_HOME."""
    from devolaflow.init_project import _find_agent_dir, install_codex

    agent_dir = _find_agent_dir()
    if not (agent_dir / "SKILL.md").exists():
        pytest.skip("requires an installed DevolaFlow agent source tree to cover")

    codex_home = tmp_path / "codex"
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    install_codex(agent_dir, tmp_path)
    out = capsys.readouterr().out
    assert "Codex" in out
    assert (codex_home / "skills" / "devola-flow" / "SKILL.md").exists()
    refs = list((codex_home / "skills" / "devola-flow" / "references").glob("*.md"))
    assert len(refs) >= 6


def test_init_project_copy_file_missing_source(monkeypatch, tmp_path, capsys):
    """_copy_file prints SKIP for a missing source and returns False."""
    from devolaflow.init_project import _copy_file

    missing = tmp_path / "does_not_exist.md"
    dest = tmp_path / "out.md"
    assert _copy_file(missing, dest) is False
    out = capsys.readouterr().out
    assert "SKIP" in out


def test_init_project_copy_dir_nonexistent(tmp_path):
    """_copy_dir on a non-directory source returns 0 without raising."""
    from devolaflow.init_project import _copy_dir

    non_dir = tmp_path / "no-such"
    assert _copy_dir(non_dir, tmp_path / "dest") == 0


# ── v6.1.0 C4 coverage: template_engine.composer ────────────────────────────


def test_composer_sequence_op_stage_order():
    """SequenceOp.stage_order returns child nodes in order."""
    from devolaflow.template_engine.composer import SequenceOp
    from devolaflow.template_engine.models import Sequence, StageRef

    seq = Sequence(stages=[StageRef("a"), StageRef("b"), StageRef("c")])
    ordered = SequenceOp.stage_order(seq)
    assert [s.stage for s in ordered] == ["a", "b", "c"]


def test_composer_parallel_op_join_counts():
    """ParallelOp.join_count resolves each join strategy correctly."""
    from devolaflow.template_engine.composer import ParallelOp
    from devolaflow.template_engine.models import Parallel, StageRef

    three = [StageRef("a"), StageRef("b"), StageRef("c")]
    assert ParallelOp.join_count(Parallel(stages=three, join="all")) == 3
    assert ParallelOp.join_count(Parallel(stages=three, join="any")) == 1
    assert ParallelOp.join_count(Parallel(stages=three, join="n_of", n_of_count=2)) == 2
    # Unknown join strategy falls back to len(stages)
    assert ParallelOp.join_count(Parallel(stages=three, join="unknown-fallback")) == 3


def test_composer_collect_all_refs_with_loops_and_gates():
    """collect_all_refs walks composition + loop bodies + gate targets."""
    from devolaflow.template_engine.composer import collect_all_refs
    from devolaflow.template_engine.models import (
        GateCriterion,
        GateDef,
        GateOnFail,
        LoopDef,
        Sequence,
        StageRef,
    )

    comp = Sequence(stages=[StageRef("a"), StageRef("b")])
    loops = {
        "L1": LoopDef(
            name="L1",
            body_stages=["b", "c"],
            until="quality>=0.9",
            max_iterations=3,
            escalation_target="escalation_stage",
        ),
    }
    gates = {
        "G1": GateDef(
            name="G1",
            position="after:b",
            criteria=[GateCriterion(field="coverage", operator=">=", value=80)],
            on_pass="d",
            on_fail=GateOnFail(action="loop_back", target="refine_stage"),
        ),
        "G2": GateDef(
            name="G2",
            position="after:c",
            criteria=[],
            on_pass="next",
            on_fail=GateOnFail(action="escalate", target=None),
        ),
    }
    refs = collect_all_refs(comp, loops=loops, gates=gates)
    # Composition stages
    assert "a" in refs and "b" in refs
    # Loop body stages + escalation target
    assert "c" in refs
    assert "escalation_stage" in refs
    # Gate on_pass (non-"next") + on_fail target
    assert "d" in refs
    assert "refine_stage" in refs
    # Sanity: "next" sentinel is not added as a stage id
    assert "next" not in refs
