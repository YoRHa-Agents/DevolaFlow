"""Tests for ``devolaflow.section_registry`` (v8.2.0 PV-05).

Covers:

* :class:`SectionAnchorRegistry` register / lookup / has / anchors / __len__ / __contains__
* ``register_from_yaml`` short-form + extended-form parsing + error paths
* :func:`extract_section_by_heading` heading discovery + fenced-code-block guard
* :func:`discover_section_content` end-to-end discovery
* Backward-compat fallback in :func:`devolaflow.task_adaptive_selector._resolve_section_text`
* B3 partial closure: STRICT profile ``legibility_enabled`` /
  ``cycle_detector_enabled`` defaults
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any

import pytest

from devolaflow.gate.profiles import AUDIT, RELAXED, STANDARD, STRICT
from devolaflow.section_registry import (
    SectionAnchorRegistry,
    discover_section_content,
    extract_section_by_heading,
)
from devolaflow.task_adaptive_selector import (
    _DEPRECATION_WARNED_ANCHORS,
    _resolve_section_text,
    build_section_registry,
    load_profiles,
    select_context,
)

# ---------------------------------------------------------------------------
# 1. SectionAnchorRegistry — core register / lookup contract.
# ---------------------------------------------------------------------------


class TestSectionAnchorRegistryCore:
    def test_register_and_lookup(self) -> None:
        registry = SectionAnchorRegistry()
        registry.register("behavioral_guidelines", "references/behavioral-guidelines.md")
        assert registry.lookup("behavioral_guidelines") == "references/behavioral-guidelines.md"

    def test_lookup_missing_raises_key_error(self) -> None:
        registry = SectionAnchorRegistry()
        with pytest.raises(KeyError, match="not registered"):
            registry.lookup("nonexistent_anchor")

    def test_register_empty_anchor_raises(self) -> None:
        registry = SectionAnchorRegistry()
        with pytest.raises(ValueError, match="non-empty string"):
            registry.register("", "some/file.md")

    def test_register_empty_file_raises(self) -> None:
        registry = SectionAnchorRegistry()
        with pytest.raises(ValueError, match="non-empty string"):
            registry.register("anchor", "")

    def test_register_absolute_path_raises(self) -> None:
        registry = SectionAnchorRegistry()
        with pytest.raises(ValueError, match="repo-root-relative"):
            registry.register("anchor", "/abs/path/to/file.md")

    def test_has_returns_true_for_registered(self) -> None:
        registry = SectionAnchorRegistry()
        registry.register("foo", "bar.md")
        assert registry.has("foo") is True
        assert registry.has("baz") is False

    def test_contains_dunder(self) -> None:
        registry = SectionAnchorRegistry()
        registry.register("foo", "bar.md")
        assert "foo" in registry
        assert "missing" not in registry
        # Non-string keys must not crash; just return False.
        assert 42 not in registry  # type: ignore[operator]

    def test_len_and_anchors(self) -> None:
        registry = SectionAnchorRegistry()
        assert len(registry) == 0
        registry.register("z_anchor", "z.md")
        registry.register("a_anchor", "a.md")
        assert len(registry) == 2
        assert registry.anchors() == ["a_anchor", "z_anchor"]

    def test_register_overwrites_previous_entry(self) -> None:
        registry = SectionAnchorRegistry()
        registry.register("anchor", "first.md")
        registry.register("anchor", "second.md")
        assert registry.lookup("anchor") == "second.md"
        assert len(registry) == 1

    def test_register_with_explicit_heading(self) -> None:
        registry = SectionAnchorRegistry()
        registry.register("mode", "SKILL.md", heading="## Mode Awareness")
        assert registry.heading("mode") == "## Mode Awareness"

    def test_heading_returns_none_when_not_set(self) -> None:
        registry = SectionAnchorRegistry()
        registry.register("anchor", "f.md")
        assert registry.heading("anchor") is None
        assert registry.heading("missing") is None

    def test_register_clears_old_heading_when_omitted(self) -> None:
        registry = SectionAnchorRegistry()
        registry.register("anchor", "f.md", heading="## H1")
        registry.register("anchor", "g.md")  # no heading override on rewrite
        assert registry.heading("anchor") is None


# ---------------------------------------------------------------------------
# 2. register_from_yaml — short / extended forms + malformed input.
# ---------------------------------------------------------------------------


class TestRegisterFromYaml:
    def test_short_form_anchor_to_path(self) -> None:
        registry = SectionAnchorRegistry()
        count = registry.register_from_yaml(
            {"section_anchors": {"behavioral_guidelines": "references/behavioral-guidelines.md"}}
        )
        assert count == 1
        assert registry.lookup("behavioral_guidelines") == "references/behavioral-guidelines.md"
        assert registry.heading("behavioral_guidelines") is None

    def test_extended_form_with_heading(self) -> None:
        registry = SectionAnchorRegistry()
        count = registry.register_from_yaml(
            {
                "section_anchors": {
                    "mode_detection": {
                        "file": "workflow-system/agent/SKILL.md",
                        "heading": "## Mode Awareness",
                    },
                }
            }
        )
        assert count == 1
        assert registry.lookup("mode_detection") == "workflow-system/agent/SKILL.md"
        assert registry.heading("mode_detection") == "## Mode Awareness"

    def test_missing_section_anchors_block_returns_zero(self) -> None:
        registry = SectionAnchorRegistry()
        count = registry.register_from_yaml({"sections": {}})
        assert count == 0
        assert len(registry) == 0

    def test_extended_form_missing_file_raises(self) -> None:
        registry = SectionAnchorRegistry()
        with pytest.raises(ValueError, match="extended form requires 'file'"):
            registry.register_from_yaml({"section_anchors": {"bad": {"heading": "## X"}}})

    def test_invalid_value_type_raises(self) -> None:
        registry = SectionAnchorRegistry()
        with pytest.raises(ValueError, match="must be str or dict"):
            registry.register_from_yaml({"section_anchors": {"weird": 42}})

    def test_section_anchors_not_a_mapping_raises(self) -> None:
        registry = SectionAnchorRegistry()
        with pytest.raises(ValueError, match="must be a mapping"):
            registry.register_from_yaml({"section_anchors": "not_a_dict"})

    def test_mixed_short_and_extended_forms(self) -> None:
        registry = SectionAnchorRegistry()
        count = registry.register_from_yaml(
            {
                "section_anchors": {
                    "anchor_a": "path/a.md",
                    "anchor_b": {
                        "file": "path/b.md",
                        "heading": "## B Heading",
                    },
                }
            }
        )
        assert count == 2
        assert registry.lookup("anchor_a") == "path/a.md"
        assert registry.heading("anchor_a") is None
        assert registry.lookup("anchor_b") == "path/b.md"
        assert registry.heading("anchor_b") == "## B Heading"


# ---------------------------------------------------------------------------
# 3. extract_section_by_heading — heading discovery + fenced-code guard.
# ---------------------------------------------------------------------------


SAMPLE_DOC = """# Title

Intro paragraph.

## Section One

Content of section one.

## Section Two

Content of section two.

### Subsection 2.1

Sub content.

## Section Three

Final section.
"""


class TestExtractSectionByHeading:
    def test_match_with_full_heading_form(self) -> None:
        out = extract_section_by_heading(SAMPLE_DOC, "## Section Two")
        assert out.startswith("## Section Two")
        assert "Content of section two." in out
        assert "Sub content." in out
        assert "## Section Three" not in out

    def test_match_with_title_only_form(self) -> None:
        out = extract_section_by_heading(SAMPLE_DOC, "Section One")
        assert "## Section One" in out
        assert "Content of section one." in out
        assert "## Section Two" not in out

    def test_unknown_heading_returns_empty(self) -> None:
        assert extract_section_by_heading(SAMPLE_DOC, "## Missing") == ""

    def test_empty_text_returns_empty(self) -> None:
        assert extract_section_by_heading("", "## Anything") == ""

    def test_empty_heading_returns_empty(self) -> None:
        assert extract_section_by_heading(SAMPLE_DOC, "") == ""

    def test_section_includes_nested_subsections(self) -> None:
        out = extract_section_by_heading(SAMPLE_DOC, "## Section Two")
        assert "### Subsection 2.1" in out
        assert "Sub content." in out

    def test_fenced_code_block_headings_ignored(self) -> None:
        doc = (
            "# Top\n\n## Real Heading\n\nbody\n\n"
            "```\n## Fake Heading In Code\nignore me\n```\n\n"
            "more body\n\n## Next Real Heading\n\ntail\n"
        )
        out = extract_section_by_heading(doc, "## Real Heading")
        assert "body" in out
        assert "## Fake Heading In Code" in out  # included as literal text
        assert "ignore me" in out
        assert "more body" in out
        assert "## Next Real Heading" not in out

    def test_substring_fallback_after_exact_miss(self) -> None:
        doc = "## PLAN MODE — Design the Plan\n\nbody\n\n## Next\n\ntail\n"
        out = extract_section_by_heading(doc, "## PLAN MODE")
        assert "## PLAN MODE" in out
        assert "body" in out
        assert "## Next" not in out

    def test_case_insensitive_match(self) -> None:
        out = extract_section_by_heading(SAMPLE_DOC, "## section two")
        assert "## Section Two" in out


# ---------------------------------------------------------------------------
# 4. discover_section_content — end-to-end with real registry + tmpfs.
# ---------------------------------------------------------------------------


class TestDiscoverSectionContent:
    def test_discover_section_in_skill_md(self, tmp_path: Path) -> None:
        skill = tmp_path / "fake_skill.md"
        skill.write_text("# Top\n\n## Quick Action Decision\n\nbody\n\n## Next\n\ntail\n")
        registry = SectionAnchorRegistry()
        registry.register(
            "quick_action_decision",
            "fake_skill.md",
            heading="## Quick Action Decision",
        )
        out = discover_section_content("quick_action_decision", registry, repo_root=tmp_path)
        assert "## Quick Action Decision" in out
        assert "body" in out
        assert "## Next" not in out

    def test_discover_returns_empty_when_file_missing(self, tmp_path: Path) -> None:
        registry = SectionAnchorRegistry()
        registry.register("missing_file", "absent.md")
        assert discover_section_content("missing_file", registry, repo_root=tmp_path) == ""

    def test_discover_falls_back_to_full_file_for_references_dir(self, tmp_path: Path) -> None:
        ref_dir = tmp_path / "workflow-system" / "agent" / "references"
        ref_dir.mkdir(parents=True)
        ref = ref_dir / "behavioral-guidelines.md"
        ref.write_text("# Behavioral Guidelines\n\nFull doc body.\n")
        registry = SectionAnchorRegistry()
        registry.register(
            "behavioral_guidelines_reference",
            "workflow-system/agent/references/behavioral-guidelines.md",
        )
        out = discover_section_content(
            "behavioral_guidelines_reference", registry, repo_root=tmp_path
        )
        # The auto-derived heading is "Behavioral Guidelines Reference" which
        # does not exact-match "Behavioral Guidelines"; the substring fallback
        # captures it. Both paths return the section; reference-doc fallback
        # serves as backup.
        assert "Full doc body." in out


# ---------------------------------------------------------------------------
# 5. Backward-compat fallback — line-based lookup with DeprecationWarning.
# ---------------------------------------------------------------------------


class TestBackwardCompatFallback:
    def setup_method(self) -> None:
        # Reset warning de-duplication across tests so each fixture
        # starts clean.
        _DEPRECATION_WARNED_ANCHORS.clear()

    def test_missing_anchor_falls_back_to_lines(self) -> None:
        registry = SectionAnchorRegistry()  # empty
        sections_registry = {"my_section": {"lines": "1-2"}}
        skill_text = "line one\nline two\nline three\n"
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", DeprecationWarning)
            text = _resolve_section_text("my_section", registry, sections_registry, skill_text)
        assert text == "line one\nline two"
        deprecation = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        assert deprecation, "expected DeprecationWarning on legacy line lookup"
        assert "my_section" in str(deprecation[0].message)

    def test_registered_anchor_skips_fallback(self, tmp_path: Path) -> None:
        skill = tmp_path / "fake.md"
        skill.write_text("# Top\n\n## Real Section\n\nbody\n\n## Next\n\ntail\n")
        registry = SectionAnchorRegistry()
        registry.register("real_section", "fake.md", heading="## Real Section")
        # Patch repo root via discover_section_content's parameter — we
        # invoke that helper directly to bypass the module-level
        # _REPO_ROOT constant.
        out = discover_section_content("real_section", registry, repo_root=tmp_path)
        assert "body" in out

    def test_deprecation_warning_only_fires_once_per_anchor(self) -> None:
        registry = SectionAnchorRegistry()  # empty
        sections_registry = {"sec": {"lines": "1-1"}}
        skill_text = "single\n"
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", DeprecationWarning)
            _resolve_section_text("sec", registry, sections_registry, skill_text)
            _resolve_section_text("sec", registry, sections_registry, skill_text)
        deprecation = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        assert len(deprecation) == 1, "deprecation must be one-shot per anchor"

    def test_unknown_section_returns_empty_string(self) -> None:
        registry = SectionAnchorRegistry()  # empty
        sections_registry: dict[str, Any] = {}  # also empty
        assert _resolve_section_text("ghost", registry, sections_registry, "txt") == ""

    def test_invalid_line_range_returns_empty(self) -> None:
        registry = SectionAnchorRegistry()
        sections_registry = {"sec": {"lines": "N/A"}}
        assert _resolve_section_text("sec", registry, sections_registry, "txt") == ""


# ---------------------------------------------------------------------------
# 6. End-to-end integration — task_adaptive_selector still works.
# ---------------------------------------------------------------------------


class TestEndToEndIntegration:
    def test_select_context_feature_profile_smoke(self) -> None:
        """Full select_context flow must produce a non-empty dispatch."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            result = select_context("feature")
        assert result["profile_name"] == "feature"
        assert len(result["selected_sections"]) > 0
        assert result["total_tokens"] > 0
        assert result["total_tokens"] <= result["budget"]

    def test_build_section_registry_returns_anchor_for_behavioral(self) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            config = load_profiles()
        registry = build_section_registry(config)
        assert registry.has("behavioral_guidelines_reference")
        path = registry.lookup("behavioral_guidelines_reference")
        assert path == "workflow-system/agent/references/behavioral-guidelines.md"

    def test_anchor_registry_reads_canonical_yaml(self) -> None:
        """The shipped context_profiles.yaml must register
        ``behavioral_guidelines_reference`` per PV-05 AC #1."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            config = load_profiles()
        registry = build_section_registry(config)
        assert "behavioral_guidelines_reference" in registry


# ---------------------------------------------------------------------------
# 7. STRICT profile B3 partial flips (PV-05 — legibility + cycle_detector).
# ---------------------------------------------------------------------------


class TestStrictProfileOptInFlips:
    def test_strict_legibility_enabled_default_true(self) -> None:
        assert STRICT.legibility_enabled is True

    def test_strict_cycle_detector_enabled_default_true(self) -> None:
        assert STRICT.cycle_detector_enabled is True

    def test_standard_legibility_enabled_remains_false(self) -> None:
        assert STANDARD.legibility_enabled is False

    def test_standard_cycle_detector_enabled_remains_false(self) -> None:
        assert STANDARD.cycle_detector_enabled is False

    def test_relaxed_keeps_both_disabled(self) -> None:
        assert RELAXED.legibility_enabled is False
        assert RELAXED.cycle_detector_enabled is False

    def test_audit_keeps_both_opt_in_for_v8_2_x_bench(self) -> None:
        # AUDIT is intentionally NOT flipped this cycle — the two flags
        # stay False per PV-05's "STRICT only this cycle" decision so
        # AUDIT users can opt-in explicitly when their pipeline is
        # ready. Bench item for v8.2.x.
        assert AUDIT.legibility_enabled is False
        assert AUDIT.cycle_detector_enabled is False
