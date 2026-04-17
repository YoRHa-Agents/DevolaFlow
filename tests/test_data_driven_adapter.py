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


def test_valid_transforms_enumeration_lists_keep_sections():
    """``VALID_TRANSFORMS`` must include all transforms accepted by ``_apply_transform``."""
    from devolaflow.adapters.data_driven import VALID_TRANSFORMS

    assert "keep_sections" in VALID_TRANSFORMS
    expected = {
        "copy",
        "copy_tree",
        "copy_with_frontmatter",
        "strip_frontmatter",
        "keep_sections",
    }
    assert set(VALID_TRANSFORMS) == expected


def _write_sectioned_skill(agent: Path) -> Path:
    """Write a SKILL.md with multiple markdown sections for keep_sections tests."""
    content = (
        "---\n"
        "id: demo\n"
        "version: 1.0\n"
        "---\n"
        "\n"
        "Preamble text before any heading.\n"
        "\n"
        "# DevolaFlow\n"
        "\n"
        "## Alpha Section\n"
        "Alpha body line 1.\n"
        "Alpha body line 2.\n"
        "\n"
        "### Alpha Subsection\n"
        "Nested alpha content.\n"
        "\n"
        "## Beta Section\n"
        "Beta body.\n"
        "\n"
        "## Gamma Section\n"
        "Gamma body.\n"
    )
    path = agent / "SKILL.md"
    path.write_text(content)
    return path


def test_keep_sections_extracts_named_sections(tmp_path: Path):
    agent = tmp_path / "agent"
    agent.mkdir()
    _write_sectioned_skill(agent)
    out = tmp_path / "out"
    config = {
        "name": "demo",
        "output": {
            "base_dir": ".",
            "files": [
                {
                    "source": "SKILL.md",
                    "target": "rules.md",
                    "transform": "keep_sections",
                    "keep_sections": ["Alpha Section", "Gamma Section"],
                }
            ],
        },
    }
    DataDrivenAdapter(config).build({}, agent, out)
    text = (out / "rules.md").read_text()
    assert "## Alpha Section" in text
    assert "Alpha body line 1." in text
    assert "### Alpha Subsection" in text
    assert "Nested alpha content." in text
    assert "## Gamma Section" in text
    assert "Gamma body." in text
    assert "## Beta Section" not in text
    assert "Beta body." not in text


def test_keep_sections_excludes_frontmatter_by_default(tmp_path: Path):
    agent = tmp_path / "agent"
    agent.mkdir()
    _write_sectioned_skill(agent)
    out = tmp_path / "out"
    config = {
        "name": "demo",
        "output": {
            "base_dir": ".",
            "files": [
                {
                    "source": "SKILL.md",
                    "target": "rules.md",
                    "transform": "keep_sections",
                    "keep_sections": ["Beta Section"],
                }
            ],
        },
    }
    DataDrivenAdapter(config).build({}, agent, out)
    text = (out / "rules.md").read_text()
    assert not text.startswith("---")
    assert "id: demo" not in text
    assert "version: 1.0" not in text
    assert "## Beta Section" in text


def test_keep_sections_includes_frontmatter_when_requested(tmp_path: Path):
    agent = tmp_path / "agent"
    agent.mkdir()
    _write_sectioned_skill(agent)
    out = tmp_path / "out"
    config = {
        "name": "demo",
        "output": {
            "base_dir": ".",
            "files": [
                {
                    "source": "SKILL.md",
                    "target": "rules.md",
                    "transform": "keep_sections",
                    "keep_sections": ["Beta Section"],
                    "include_frontmatter": True,
                }
            ],
        },
    }
    DataDrivenAdapter(config).build({}, agent, out)
    text = (out / "rules.md").read_text()
    assert text.startswith("---")
    assert "id: demo" in text
    assert "version: 1.0" in text
    assert "## Beta Section" in text


def test_keep_sections_prepends_header_prefix(tmp_path: Path):
    agent = tmp_path / "agent"
    agent.mkdir()
    _write_sectioned_skill(agent)
    out = tmp_path / "out"
    config = {
        "name": "demo",
        "output": {
            "base_dir": ".",
            "files": [
                {
                    "source": "SKILL.md",
                    "target": "rules.md",
                    "transform": "keep_sections",
                    "keep_sections": ["Alpha Section"],
                    "header_prefix": "# Compressed Rules\nSee full docs.\n",
                }
            ],
        },
    }
    DataDrivenAdapter(config).build({}, agent, out)
    text = (out / "rules.md").read_text()
    assert text.startswith("# Compressed Rules\nSee full docs.")
    assert "## Alpha Section" in text
    header_end = text.index("## Alpha Section")
    assert "See full docs." in text[:header_end]


def test_keep_sections_empty_list_produces_empty_body(tmp_path: Path):
    agent = tmp_path / "agent"
    agent.mkdir()
    _write_sectioned_skill(agent)
    out = tmp_path / "out"
    config = {
        "name": "demo",
        "output": {
            "base_dir": ".",
            "files": [
                {
                    "source": "SKILL.md",
                    "target": "rules.md",
                    "transform": "keep_sections",
                    "keep_sections": [],
                    "header_prefix": "# Only Prefix\n",
                }
            ],
        },
    }
    DataDrivenAdapter(config).build({}, agent, out)
    text = (out / "rules.md").read_text()
    assert "## Alpha Section" not in text
    assert "## Beta Section" not in text
    assert "## Gamma Section" not in text
    assert "Alpha body" not in text
    assert text.strip() == "# Only Prefix"


def test_keep_sections_substring_match_not_exact(tmp_path: Path):
    agent = tmp_path / "agent"
    agent.mkdir()
    _write_sectioned_skill(agent)
    out = tmp_path / "out"
    config = {
        "name": "demo",
        "output": {
            "base_dir": ".",
            "files": [
                {
                    "source": "SKILL.md",
                    "target": "rules.md",
                    "transform": "keep_sections",
                    "keep_sections": ["Beta"],
                }
            ],
        },
    }
    DataDrivenAdapter(config).build({}, agent, out)
    text = (out / "rules.md").read_text()
    assert "## Beta Section" in text
    assert "Beta body." in text
    assert "## Alpha Section" not in text
    assert "## Gamma Section" not in text


def test_keep_sections_handles_missing_source(tmp_path: Path):
    agent = tmp_path / "agent"
    agent.mkdir()
    out = tmp_path / "out"
    config = {
        "name": "demo",
        "output": {
            "base_dir": ".",
            "files": [
                {
                    "source": "missing.md",
                    "target": "rules.md",
                    "transform": "keep_sections",
                    "keep_sections": ["Alpha Section"],
                    "header_prefix": "# Prefix\n",
                }
            ],
        },
    }
    result = DataDrivenAdapter(config).build({}, agent, out)
    assert not (out / "rules.md").exists()
    assert result.files_created == []


def test_keep_sections_ignores_fenced_code_block_headings(tmp_path: Path):
    """Headings inside fenced code blocks must NOT be treated as section boundaries."""
    agent = tmp_path / "agent"
    agent.mkdir()
    (agent / "SKILL.md").write_text(
        "## Real Section\n"
        "Real body.\n"
        "\n"
        "```markdown\n"
        "## Fake Heading Inside Code\n"
        "This line looks like a heading but is inside code.\n"
        "```\n"
        "\n"
        "## Another Real\n"
        "Another body.\n"
    )
    out = tmp_path / "out"
    config = {
        "name": "demo",
        "output": {
            "base_dir": ".",
            "files": [
                {
                    "source": "SKILL.md",
                    "target": "rules.md",
                    "transform": "keep_sections",
                    "keep_sections": ["Real Section"],
                }
            ],
        },
    }
    DataDrivenAdapter(config).build({}, agent, out)
    text = (out / "rules.md").read_text()
    assert "## Real Section" in text
    assert "Real body." in text
    assert "## Fake Heading Inside Code" in text
    assert "This line looks like a heading but is inside code." in text
    assert "## Another Real" not in text
    assert "Another body." not in text


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
