"""Tests for the DataDrivenAdapter YAML-driven engine (v6.0.4 D1)."""

from __future__ import annotations

from pathlib import Path

import pytest

from devolaflow.adapters.data_driven import (
    DataDrivenAdapter,
    load_data_driven_adapters,
)
from devolaflow.adapters.registry import AdapterRegistry


def _make_agent_dir(tmp_path: Path) -> Path:
    """Build a tiny fake agent_dir with a SKILL.md, references/, examples/."""
    agent = tmp_path / "agent"
    agent.mkdir()
    (agent / "SKILL.md").write_text("---\nid: demo\nversion: 1.0\n---\n# Hello\n")
    refs = agent / "references"
    refs.mkdir()
    (refs / "one.md").write_text("# one\n")
    (refs / "two.md").write_text("# two\n")
    examples = agent / "examples"
    examples.mkdir()
    (examples / "ex.md").write_text("# example\n")
    return agent


def test_data_driven_copy_transform(tmp_path: Path):
    agent = _make_agent_dir(tmp_path)
    out = tmp_path / "out"
    config = {
        "name": "demo",
        "output": {
            "base_dir": "dest",
            "files": [
                {"source": "SKILL.md", "target": "SKILL.md", "transform": "copy"},
            ],
        },
    }
    result = DataDrivenAdapter(config).build({}, agent, out)
    assert result.tool == "demo"
    copied = out / "dest" / "SKILL.md"
    assert copied.exists()
    assert copied.read_text() == (agent / "SKILL.md").read_text()
    assert "SKILL.md" in str(result.files_created[0])


def test_data_driven_copy_tree_transform(tmp_path: Path):
    agent = _make_agent_dir(tmp_path)
    out = tmp_path / "out"
    config = {
        "name": "demo",
        "output": {
            "base_dir": "dest",
            "files": [
                {"source": "references", "target": "references", "transform": "copy_tree"},
            ],
        },
    }
    DataDrivenAdapter(config).build({}, agent, out)
    dest = out / "dest" / "references"
    assert (dest / "one.md").exists()
    assert (dest / "two.md").exists()


def test_data_driven_copy_tree_overwrites_existing(tmp_path: Path):
    agent = _make_agent_dir(tmp_path)
    out = tmp_path / "out"
    config = {
        "name": "demo",
        "output": {
            "base_dir": "dest",
            "files": [
                {"source": "references", "target": "references", "transform": "copy_tree"},
            ],
        },
    }
    adapter = DataDrivenAdapter(config)
    adapter.build({}, agent, out)
    # Delete a source file, then rebuild — the dest tree should match source again.
    (agent / "references" / "two.md").unlink()
    adapter.build({}, agent, out)
    assert not (out / "dest" / "references" / "two.md").exists()
    assert (out / "dest" / "references" / "one.md").exists()


def test_data_driven_copy_with_frontmatter_injects(tmp_path: Path):
    agent = _make_agent_dir(tmp_path)
    out = tmp_path / "out"
    config = {
        "name": "demo",
        "output": {
            "base_dir": "dest",
            "files": [
                {"source": "SKILL.md", "target": "SKILL.md", "transform": "copy_with_frontmatter"},
            ],
        },
        "frontmatter": {"inject": {"platform": "demo", "extra": "yes"}},
    }
    DataDrivenAdapter(config).build({}, agent, out)
    text = (out / "dest" / "SKILL.md").read_text()
    assert "platform: demo" in text
    assert "extra: yes" in text
    # Existing frontmatter keys are preserved.
    assert "id: demo" in text
    assert "version: 1.0" in text
    # The document body is preserved too.
    assert "# Hello" in text


def test_data_driven_copy_with_frontmatter_no_existing_frontmatter(tmp_path: Path):
    agent = tmp_path / "agent"
    agent.mkdir()
    (agent / "doc.md").write_text("# plain body\n")
    out = tmp_path / "out"
    config = {
        "name": "demo",
        "output": {
            "base_dir": ".",
            "files": [
                {"source": "doc.md", "target": "doc.md", "transform": "copy_with_frontmatter"},
            ],
        },
        "frontmatter": {"inject": {"platform": "demo"}},
    }
    DataDrivenAdapter(config).build({}, agent, out)
    text = (out / "doc.md").read_text()
    assert text.startswith("---\nplatform: demo\n---\n")
    assert "# plain body" in text


def test_data_driven_strip_frontmatter_transform(tmp_path: Path):
    agent = tmp_path / "agent"
    agent.mkdir()
    (agent / "SKILL.md").write_text("---\nkey: value\n---\n# body content\n")
    out = tmp_path / "out"
    config = {
        "name": "demo",
        "output": {
            "base_dir": ".",
            "files": [
                {"source": "SKILL.md", "target": "body.md", "transform": "strip_frontmatter"},
            ],
        },
    }
    DataDrivenAdapter(config).build({}, agent, out)
    text = (out / "body.md").read_text()
    assert "key: value" not in text
    assert "---" not in text
    assert "# body content" in text


def test_data_driven_strip_frontmatter_no_frontmatter_is_passthrough(tmp_path: Path):
    agent = tmp_path / "agent"
    agent.mkdir()
    (agent / "plain.md").write_text("# no frontmatter here\n")
    out = tmp_path / "out"
    config = {
        "name": "demo",
        "output": {
            "base_dir": ".",
            "files": [
                {"source": "plain.md", "target": "plain.md", "transform": "strip_frontmatter"},
            ],
        },
    }
    DataDrivenAdapter(config).build({}, agent, out)
    assert (out / "plain.md").read_text() == "# no frontmatter here\n"


def test_data_driven_budget_lines_ok(tmp_path: Path):
    agent = tmp_path / "agent"
    agent.mkdir()
    (agent / "SKILL.md").write_text("\n".join(f"line {i}" for i in range(50)))
    out = tmp_path / "out"
    config = {
        "name": "demo",
        "output": {
            "base_dir": "dest",
            "files": [{"source": "SKILL.md", "target": "SKILL.md", "transform": "copy"}],
        },
        "budget": {"type": "lines", "max": 100, "target_file": "SKILL.md"},
    }
    result = DataDrivenAdapter(config).build({}, agent, out)
    assert result.budget_ok
    assert "50/100" in result.budget_details
    assert "lines" in result.budget_details


def test_data_driven_budget_lines_exceeded(tmp_path: Path):
    agent = tmp_path / "agent"
    agent.mkdir()
    (agent / "SKILL.md").write_text("\n".join(f"line {i}" for i in range(200)))
    out = tmp_path / "out"
    config = {
        "name": "demo",
        "output": {
            "base_dir": "dest",
            "files": [{"source": "SKILL.md", "target": "SKILL.md", "transform": "copy"}],
        },
        "budget": {"type": "lines", "max": 100, "target_file": "SKILL.md"},
    }
    result = DataDrivenAdapter(config).build({}, agent, out)
    assert not result.budget_ok
    assert "200/100" in result.budget_details


def test_data_driven_budget_chars(tmp_path: Path):
    agent = tmp_path / "agent"
    agent.mkdir()
    (agent / "SKILL.md").write_text("hello")
    out = tmp_path / "out"
    config = {
        "name": "demo",
        "output": {
            "base_dir": "dest",
            "files": [{"source": "SKILL.md", "target": "SKILL.md", "transform": "copy"}],
        },
        "budget": {"type": "chars", "max": 100, "target_file": "SKILL.md"},
    }
    result = DataDrivenAdapter(config).build({}, agent, out)
    assert result.budget_ok
    assert "5/100" in result.budget_details
    assert "chars" in result.budget_details


def test_data_driven_budget_target_missing(tmp_path: Path):
    agent = tmp_path / "agent"
    agent.mkdir()
    out = tmp_path / "out"
    config = {
        "name": "demo",
        "output": {"base_dir": "dest", "files": []},
        "budget": {"type": "lines", "max": 10, "target_file": "does_not_exist.md"},
    }
    result = DataDrivenAdapter(config).build({}, agent, out)
    assert not result.budget_ok
    assert "missing" in result.budget_details


def test_data_driven_no_budget_configured(tmp_path: Path):
    agent = tmp_path / "agent"
    agent.mkdir()
    (agent / "SKILL.md").write_text("hi")
    out = tmp_path / "out"
    config = {
        "name": "demo",
        "output": {
            "base_dir": ".",
            "files": [{"source": "SKILL.md", "target": "SKILL.md", "transform": "copy"}],
        },
    }
    result = DataDrivenAdapter(config).build({}, agent, out)
    assert result.budget_ok
    assert "no budget check" in result.budget_details


def test_data_driven_missing_source_skipped(tmp_path: Path):
    agent = tmp_path / "agent"
    agent.mkdir()
    (agent / "SKILL.md").write_text("# exists\n")
    out = tmp_path / "out"
    config = {
        "name": "demo",
        "output": {
            "base_dir": ".",
            "files": [
                {"source": "SKILL.md", "target": "SKILL.md", "transform": "copy"},
                {"source": "missing.md", "target": "missing.md", "transform": "copy"},
            ],
        },
    }
    result = DataDrivenAdapter(config).build({}, agent, out)
    assert (out / "SKILL.md").exists()
    assert not (out / "missing.md").exists()
    # Only the existing source should appear in files_created.
    assert any("SKILL.md" in f for f in result.files_created)
    assert not any("missing.md" in f for f in result.files_created)


def test_data_driven_unknown_transform_raises(tmp_path: Path):
    agent = tmp_path / "agent"
    agent.mkdir()
    (agent / "SKILL.md").write_text("hi")
    out = tmp_path / "out"
    config = {
        "name": "demo",
        "output": {
            "base_dir": ".",
            "files": [
                {"source": "SKILL.md", "target": "SKILL.md", "transform": "weird_thing"},
            ],
        },
    }
    with pytest.raises(ValueError) as exc:
        DataDrivenAdapter(config).build({}, agent, out)
    assert "weird_thing" in str(exc.value)


def test_data_driven_config_without_name_raises():
    with pytest.raises(ValueError):
        DataDrivenAdapter({})


def test_load_data_driven_adapters_scans_configs(tmp_path: Path):
    configs = tmp_path / "adapter_configs"
    configs.mkdir()
    (configs / "alpha.yaml").write_text(
        "name: alpha\ndisplay_name: Alpha\ntier: tier_1\noutput:\n  base_dir: .\n  files: []\n"
    )
    (configs / "beta.yaml").write_text(
        "name: beta\ntier: tier_2\noutput:\n  base_dir: .\n  files: []\n"
    )
    reg = AdapterRegistry()
    load_data_driven_adapters(reg, configs_dir=configs)
    assert set(reg.list_names()) == {"alpha", "beta"}
    assert reg.metadata("alpha")["tier"] == "tier_1"
    assert reg.metadata("alpha")["description"] == "Alpha"
    assert reg.metadata("beta")["tier"] == "tier_2"


def test_load_data_driven_adapters_ignores_invalid_yaml(tmp_path: Path):
    configs = tmp_path / "adapter_configs"
    configs.mkdir()
    (configs / "bad.yaml").write_text(":::not: valid: yaml:::\n  - [ unbalanced")
    (configs / "good.yaml").write_text("name: good\noutput:\n  base_dir: .\n  files: []\n")
    (configs / "noname.yaml").write_text("tier: tier_1\n")
    reg = AdapterRegistry()
    load_data_driven_adapters(reg, configs_dir=configs)
    assert reg.list_names() == ["good"]


def test_load_data_driven_adapters_missing_dir(tmp_path: Path):
    reg = AdapterRegistry()
    # Should not raise when the directory does not exist.
    load_data_driven_adapters(reg, configs_dir=tmp_path / "nonexistent")
    assert reg.list_names() == []
