"""Tests for cli local-rule shims (sync-rules, check-rules-drift, scaffold-local).

Covers the three v7.4.0 console-script shims:
``sync_rules_cmd`` (cli.py:90-105), ``check_rules_drift_cmd`` (cli.py:108-124),
``scaffold_local_cmd`` (cli.py:127-134).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from devolaflow.cli import check_rules_drift_cmd, scaffold_local_cmd, sync_rules_cmd

_CONFIG_YAML = """\
version: "1.0"
layers:
  - {name: soul, file: soul.mdc, priority: 0, always_include: true}
targets:
  cursor:
    output: .cursor/rules/repo-governance.mdc
    format: mdc
    token_budget: 8000
    include_layers: [soul]
    frontmatter: {description: Compiled, alwaysApply: true}
drift_detection:
  enabled: true
  hash_file: .rules/.compile-hashes.json
"""


@pytest.fixture()
def valid_rules_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Tmp repo with a minimal valid `.rules/` setup; cwd patched to tmp_path."""
    rd = tmp_path / ".rules"
    rd.mkdir()
    (rd / "soul.mdc").write_text(
        '---\ndescription: "Soul"\npriority: P0\nalwaysApply: true\n---\n\n'
        "# Soul\n\nImmutable rules.\n",
        encoding="utf-8",
    )
    (rd / "compile-config.yaml").write_text(_CONFIG_YAML, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    return tmp_path


class TestSyncRulesCmd:
    def test_happy_path_compiles_all_targets(
        self, valid_rules_repo: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        sync_rules_cmd()
        out = capsys.readouterr().out
        assert "cursor:" in out and "tokens" in out and "1 target(s) compiled" in out
        assert (valid_rules_repo / ".cursor" / "rules" / "repo-governance.mdc").exists()

    def test_missing_config_exits_1(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.chdir(tmp_path)
        with pytest.raises(SystemExit) as exc:
            sync_rules_cmd()
        assert exc.value.code == 1
        assert "Run 'devola-init' first" in capsys.readouterr().out


class TestCheckRulesDriftCmd:
    def test_in_sync_after_compile_exits_0(
        self, valid_rules_repo: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        sync_rules_cmd()
        capsys.readouterr()
        with pytest.raises(SystemExit) as exc:
            check_rules_drift_cmd()
        assert exc.value.code == 0
        assert "in_sync" in capsys.readouterr().out

    def test_missing_rules_dir_exits_1(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.chdir(tmp_path)
        with pytest.raises(SystemExit) as exc:
            check_rules_drift_cmd()
        assert exc.value.code == 1
        assert "No .rules/ directory found" in capsys.readouterr().out

    def test_drifted_after_edit_exits_1(
        self, valid_rules_repo: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        sync_rules_cmd()
        capsys.readouterr()
        (valid_rules_repo / ".cursor" / "rules" / "repo-governance.mdc").write_text(
            "tampered\n", encoding="utf-8"
        )
        with pytest.raises(SystemExit) as exc:
            check_rules_drift_cmd()
        assert exc.value.code == 1
        assert "drifted" in capsys.readouterr().out


class TestScaffoldLocalCmd:
    def test_happy_path_no_args_creates_required_dirs(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, "argv", ["scaffold-local"])
        scaffold_local_cmd()
        assert ".local/ workspace initialized" in capsys.readouterr().out
        assert (tmp_path / ".local" / "feedbacks").is_dir()
        assert (tmp_path / ".local" / "tasks").is_dir()
        assert (tmp_path / ".local" / "index.md").exists()
        assert not (tmp_path / ".local" / "research").exists()

    def test_with_on_demand_dirs_creates_extras(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, "argv", ["scaffold-local", "research", "logs"])
        scaffold_local_cmd()
        assert ".local/ workspace initialized" in capsys.readouterr().out
        assert (tmp_path / ".local" / "research").is_dir()
        assert (tmp_path / ".local" / "logs").is_dir()

    def test_structure_error_prints_fail_and_exits_1(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """PR #174 Bugbot finding: ScaffoldStructureError (Track C-2) must get
        the same FAIL-message + exit-1 handling as ScaffoldVerificationError
        at every CLI boundary — not a raw traceback."""
        from devolaflow.local import workspace as ws

        def _boom(*args: object, **kwargs: object) -> None:
            raise ws.ScaffoldStructureError([".local/memory/specs"], tmp_path)

        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, "argv", ["scaffold-local"])
        monkeypatch.setattr(ws, "scaffold_local", _boom)
        with pytest.raises(SystemExit) as exc:
            scaffold_local_cmd()
        assert exc.value.code == 1
        out = capsys.readouterr().out
        assert "FAIL" in out
        assert ".local/memory/specs" in out
