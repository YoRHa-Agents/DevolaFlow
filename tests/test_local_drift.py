"""Tests for devolaflow.local.drift module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from devolaflow.local.compiler import CompileResult, RuleCompiler
from devolaflow.local.drift import DriftResult, check_rules_drift, save_hashes


@pytest.fixture()
def compiled_env(tmp_path: Path) -> Path:
    """Set up a .rules/ dir, compile, and save hashes — returns the .rules/ dir."""
    rd = tmp_path / ".rules"
    rd.mkdir()

    (rd / "soul.mdc").write_text(
        '---\ndescription: "Soul"\npriority: P0\nalwaysApply: true\n---\n\n'
        "# Soul\n\nImmutable rules.\n",
        encoding="utf-8",
    )

    config = {
        "version": "1.0",
        "layers": [
            {"name": "soul", "file": "soul.mdc", "priority": 0, "always_include": True},
        ],
        "targets": {
            "cursor": {
                "output": ".cursor/rules/repo-governance.mdc",
                "format": "mdc",
                "token_budget": 8000,
                "include_layers": ["soul"],
                "frontmatter": {"description": "Compiled", "alwaysApply": True},
            },
        },
        "drift_detection": {
            "enabled": True,
            "hash_file": ".rules/.compile-hashes.json",
        },
    }
    (rd / "compile-config.yaml").write_text(
        yaml.dump(config, default_flow_style=False), encoding="utf-8"
    )

    rc = RuleCompiler(rd / "compile-config.yaml")
    rc.load_layers(rd)
    rc.compile_all()

    return rd


class TestSaveHashes:
    def test_creates_hash_file(self, tmp_path: Path) -> None:
        results = [
            CompileResult(
                target="t1",
                content="body",
                tokens_used=10,
                tokens_budget=100,
                layers_included=["soul"],
                content_hash="aabb",
            ),
        ]
        hash_file = tmp_path / ".compile-hashes.json"
        save_hashes(results, hash_file)
        assert hash_file.exists()
        data = json.loads(hash_file.read_text())
        assert data["t1"] == "aabb"

    def test_overwrites_existing(self, tmp_path: Path) -> None:
        hash_file = tmp_path / "hashes.json"
        hash_file.write_text('{"old": "val"}')

        results = [
            CompileResult(
                target="new",
                content="c",
                tokens_used=1,
                tokens_budget=10,
                layers_included=[],
                content_hash="xx",
            ),
        ]
        save_hashes(results, hash_file)
        data = json.loads(hash_file.read_text())
        assert "old" not in data
        assert data["new"] == "xx"


class TestCheckRulesDrift:
    def test_in_sync_after_compile(self, compiled_env: Path) -> None:
        results = check_rules_drift(compiled_env)
        assert len(results) == 1
        assert results[0].status == "in_sync"
        assert results[0].target == "cursor"

    def test_drifted_after_edit(self, compiled_env: Path) -> None:
        repo_root = compiled_env.parent
        output = repo_root / ".cursor" / "rules" / "repo-governance.mdc"
        output.write_text("manually edited content\n", encoding="utf-8")

        results = check_rules_drift(compiled_env)
        assert results[0].status == "drifted"

    def test_missing_output_file(self, compiled_env: Path) -> None:
        repo_root = compiled_env.parent
        output = repo_root / ".cursor" / "rules" / "repo-governance.mdc"
        output.unlink()

        results = check_rules_drift(compiled_env)
        assert results[0].status == "missing"

    def test_missing_hash_file(self, tmp_path: Path) -> None:
        """When no hash file exists, all targets show as drifted or missing."""
        rd = tmp_path / ".rules"
        rd.mkdir()

        config = {
            "version": "1.0",
            "layers": [],
            "targets": {
                "t": {
                    "output": "out.md",
                    "format": "markdown",
                    "token_budget": 1000,
                    "include_layers": [],
                }
            },
            "drift_detection": {
                "enabled": True,
                "hash_file": ".rules/.compile-hashes.json",
            },
        }
        (rd / "compile-config.yaml").write_text(yaml.dump(config), encoding="utf-8")

        results = check_rules_drift(rd)
        assert len(results) == 1
        assert results[0].status == "missing"


class TestDriftResult:
    def test_fields(self) -> None:
        dr = DriftResult(
            target="cursor",
            status="in_sync",
            expected_hash="aabb",
            actual_hash="aabb",
        )
        assert dr.target == "cursor"
        assert dr.status == "in_sync"
        assert dr.expected_hash == dr.actual_hash
