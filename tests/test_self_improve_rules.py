"""Tests for .cursor/rules/self-improve-iteration-rules.mdc structure and content."""

import re
from pathlib import Path

import pytest

MDC_REL_PATH = ".cursor/rules/self-improve-iteration-rules.mdc"
EXPECTED_RULES = [f"SI-{i}" for i in range(1, 11)]
ABS_PATH_PATTERN = re.compile(r"(?<!\w)(/(?:home|Users|tmp|var|opt|usr|etc|benchmarks)/\S+)")


@pytest.fixture
def mdc_path(project_root: Path) -> Path:
    return project_root / MDC_REL_PATH


@pytest.fixture
def mdc_content(mdc_path: Path) -> str:
    return mdc_path.read_text(encoding="utf-8")


class TestFileExists:
    def test_mdc_file_exists(self, mdc_path: Path):
        assert mdc_path.is_file(), f"{MDC_REL_PATH} does not exist"


class TestFrontmatter:
    def test_has_yaml_frontmatter(self, mdc_content: str):
        assert mdc_content.startswith("---"), "File must start with YAML frontmatter delimiter"
        parts = mdc_content.split("---", 2)
        assert len(parts) >= 3, "File must have opening and closing --- delimiters"

    def test_always_apply_true(self, mdc_content: str):
        frontmatter = mdc_content.split("---", 2)[1]
        assert "alwaysApply: true" in frontmatter or "alwaysApply: True" in frontmatter

    def test_has_description(self, mdc_content: str):
        frontmatter = mdc_content.split("---", 2)[1]
        assert "description:" in frontmatter


class TestRuleSections:
    @pytest.mark.parametrize("rule_id", EXPECTED_RULES)
    def test_rule_section_present(self, mdc_content: str, rule_id: str):
        pattern = rf"## Rule {rule_id}\s+—"
        assert re.search(pattern, mdc_content), f"Missing rule section: {rule_id}"

    def test_all_ten_rules_present(self, mdc_content: str):
        found = re.findall(r"## Rule (SI-\d+)\s+—", mdc_content)
        assert len(found) == 10, f"Expected 10 rules, found {len(found)}: {found}"

    def test_rules_in_order(self, mdc_content: str):
        found = re.findall(r"## Rule (SI-\d+)\s+—", mdc_content)
        expected_order = [f"SI-{i}" for i in range(1, 11)]
        assert found == expected_order, f"Rules out of order: {found}"


class TestNoAbsolutePaths:
    def test_no_absolute_filesystem_paths(self, mdc_content: str):
        matches = ABS_PATH_PATTERN.findall(mdc_content)
        assert not matches, (
            f"Absolute filesystem paths found (use relative paths or GitHub URLs): {matches}"
        )

    def test_no_home_paths(self, mdc_content: str):
        assert "/home/" not in mdc_content, "Contains /home/ absolute path"

    def test_no_users_paths(self, mdc_content: str):
        assert "/Users/" not in mdc_content, "Contains /Users/ absolute path"


class TestContentQuality:
    def test_references_github_urls(self, mdc_content: str):
        assert "https://github.com/YoRHa-Agents/DevolaFlow" in mdc_content
        assert "https://github.com/YoRHa-Agents/NineS" in mdc_content

    def test_references_evobench(self, mdc_content: str):
        assert "test_benchmarks.py" in mdc_content

    def test_references_reinforcement(self, mdc_content: str):
        assert "reinforcement" in mdc_content.lower()

    def test_references_nines(self, mdc_content: str):
        assert "nines" in mdc_content.lower()
