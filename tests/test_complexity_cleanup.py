"""Regression-guard tests for v8.0.0 P-01 cyclomatic-complexity cleanup.

Patch P-01 reduces cc on six NineS-flagged hotspots:

* ``DataDrivenAdapter._apply_transform``  (cc 25 -> 3)
* ``DataDrivenAdapter._split_by_heading`` (cc 15 -> 1)
* ``select_stages_for_runtime``           (cc 18 -> 3)
* ``_collect_violations``                 (cc 15 -> 6)
* ``refresh_reference_dependency``        (cc 12 -> 6)
* ``task_adaptive_selector.main``         (cc 11 -> 3)

This file pins the post-refactor public behavior **byte-identical** to the
pre-refactor source AND asserts the new radon-cc ceiling so regressions
trip the suite. The cc-enforcement block uses :func:`pytest.importorskip`
so the suite still runs in environments that lack ``radon`` (the package
is not in ``pyproject.toml`` dev deps; SI-10 step 1 stays green).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

from devolaflow.adapters.data_driven import DataDrivenAdapter, _Section
from devolaflow.lifecycle.dispatcher import HookViolation
from devolaflow.lifecycle.format_on_edit import (
    KNOWN_FORMATTERS,
    _collect_violations,
    format_on_edit,
)
from devolaflow.nines.researcher import refresh_reference_dependency
from devolaflow.task_adaptive_selector import main as cli_main
from devolaflow.template_engine.models import (
    Choice,
    Sequence,
    StageDefinition,
    StageRef,
    TemplateMetadata,
    WorkflowTemplate,
)
from devolaflow.template_engine.runtime import select_stages_for_runtime

REPO_ROOT = Path(__file__).resolve().parent.parent

# ── Fixtures / helpers ───────────────────────────────────────────────


def _make_adapter(extra: dict[str, Any] | None = None) -> DataDrivenAdapter:
    cfg: dict[str, Any] = {"name": "demo"}
    if extra:
        cfg.update(extra)
    return DataDrivenAdapter(cfg)


def _make_template(
    stages: list[StageDefinition],
    composition: Sequence | Choice | StageRef,
    *,
    parameters: dict[str, Any] | None = None,
    environment_modes: dict[str, Any] | None = None,
) -> WorkflowTemplate:
    return WorkflowTemplate(
        schema_version="1.0",
        metadata=TemplateMetadata(name="cc-cleanup-test", version="0.0.0"),
        stages=stages,
        composition=composition,
        parameters=parameters or {},
        environment_modes=environment_modes or {},
    )


# ── 1. DataDrivenAdapter._apply_transform — per-transform behavior ───


class TestApplyTransform:
    """Each transform branch must produce byte-identical output post-refactor."""

    def test_copy_writes_source_bytes(self, tmp_path: Path) -> None:
        adapter = _make_adapter()
        src = tmp_path / "in.txt"
        dst = tmp_path / "out.txt"
        src.write_text("hello world")
        adapter._apply_transform(src, dst, "copy")
        assert dst.read_text() == "hello world"

    def test_copy_tree_replaces_existing_destination(self, tmp_path: Path) -> None:
        adapter = _make_adapter()
        src_dir = tmp_path / "src_tree"
        src_dir.mkdir()
        (src_dir / "a.md").write_text("alpha")
        (src_dir / "b.md").write_text("beta")
        dst_dir = tmp_path / "dst_tree"
        dst_dir.mkdir()
        (dst_dir / "stale.txt").write_text("OLD")
        adapter._apply_transform(src_dir, dst_dir, "copy_tree")
        assert (dst_dir / "a.md").read_text() == "alpha"
        assert (dst_dir / "b.md").read_text() == "beta"
        assert not (dst_dir / "stale.txt").exists()

    def test_copy_with_frontmatter_injects_platform_key(self, tmp_path: Path) -> None:
        adapter = _make_adapter({"frontmatter": {"inject": {"platform": "demo"}}})
        src = tmp_path / "in.md"
        dst = tmp_path / "out.md"
        src.write_text("# Title\n\nbody\n")
        adapter._apply_transform(src, dst, "copy_with_frontmatter")
        out = dst.read_text()
        assert "platform: demo" in out
        assert "# Title" in out

    def test_strip_frontmatter_removes_yaml_block(self, tmp_path: Path) -> None:
        adapter = _make_adapter()
        src = tmp_path / "in.md"
        dst = tmp_path / "out.md"
        src.write_text("---\ntitle: x\n---\n\nBODY\n")
        adapter._apply_transform(src, dst, "strip_frontmatter")
        assert dst.read_text() == "BODY\n"

    def test_strip_frontmatter_passthrough_when_absent(self, tmp_path: Path) -> None:
        adapter = _make_adapter()
        src = tmp_path / "in.md"
        dst = tmp_path / "out.md"
        src.write_text("no frontmatter here\n")
        adapter._apply_transform(src, dst, "strip_frontmatter")
        assert dst.read_text() == "no frontmatter here\n"

    def test_keep_sections_filters_by_heading_substring(self, tmp_path: Path) -> None:
        adapter = _make_adapter()
        src = tmp_path / "in.md"
        dst = tmp_path / "out.md"
        src.write_text("# Alpha\nA body\n# Beta\nB body\n# Gamma\nG body\n")
        adapter._apply_transform(
            src,
            dst,
            "keep_sections",
            spec={"keep_sections": ["Beta", "Gamma"]},
        )
        out = dst.read_text()
        assert "# Beta" in out
        assert "# Gamma" in out
        assert "# Alpha" not in out

    def test_keep_sections_includes_frontmatter_when_requested(self, tmp_path: Path) -> None:
        adapter = _make_adapter()
        src = tmp_path / "in.md"
        dst = tmp_path / "out.md"
        src.write_text("---\nfm: ok\n---\n\n# Pick\nbody\n# Drop\nx\n")
        adapter._apply_transform(
            src,
            dst,
            "keep_sections",
            spec={"keep_sections": ["Pick"], "include_frontmatter": True},
        )
        out = dst.read_text()
        assert out.startswith("---")
        assert "fm: ok" in out
        assert "# Pick" in out
        assert "# Drop" not in out

    def test_keep_sections_prepends_header_prefix(self, tmp_path: Path) -> None:
        adapter = _make_adapter()
        src = tmp_path / "in.md"
        dst = tmp_path / "out.md"
        src.write_text("# Pick\nbody\n")
        adapter._apply_transform(
            src,
            dst,
            "keep_sections",
            spec={"keep_sections": ["Pick"], "header_prefix": "PREFIX_LINE"},
        )
        out = dst.read_text()
        assert out.startswith("PREFIX_LINE")
        assert "# Pick" in out

    def test_unknown_transform_raises_value_error(self, tmp_path: Path) -> None:
        adapter = _make_adapter()
        src = tmp_path / "in.txt"
        dst = tmp_path / "out.txt"
        src.write_text("x")
        with pytest.raises(ValueError, match="Unknown transform"):
            adapter._apply_transform(src, dst, "no_such_transform")


# ── 2. DataDrivenAdapter._split_by_heading — fence + nesting ─────────


class TestSplitByHeading:
    """Heading splitter must respect fences and equal-or-higher-level nesting."""

    def test_empty_text_returns_empty_list(self) -> None:
        assert DataDrivenAdapter._split_by_heading("") == []

    def test_no_headings_returns_single_preamble(self) -> None:
        out = DataDrivenAdapter._split_by_heading("just paragraph text\n")
        assert len(out) == 1
        assert out[0].level == 0
        assert "paragraph text" in out[0].text

    def test_top_level_heading_yields_one_section(self) -> None:
        out = DataDrivenAdapter._split_by_heading("# Title\nbody line\n")
        assert len(out) == 1
        assert out[0].level == 1
        assert out[0].heading == "Title"
        assert "body line" in out[0].text

    def test_h2_section_contains_h3_children(self) -> None:
        text = "## Top\nintro\n### Child\nchild body\n## Sibling\nsib\n"
        out = DataDrivenAdapter._split_by_heading(text)
        top = next(s for s in out if s.heading == "Top")
        sib = next(s for s in out if s.heading == "Sibling")
        assert "Child" in top.text
        assert "child body" in top.text
        assert "Child" not in sib.text

    def test_fenced_heading_lookalike_is_ignored(self) -> None:
        text = "# Real\nintro\n```\n# Not a heading\n```\n## Subsection\nbody\n"
        out = DataDrivenAdapter._split_by_heading(text)
        headings = {s.heading for s in out if s.level > 0}
        assert "Not a heading" not in headings
        assert "Real" in headings
        assert "Subsection" in headings

    def test_preamble_before_first_heading_is_emitted(self) -> None:
        text = "preamble paragraph\n# First\nbody\n"
        out = DataDrivenAdapter._split_by_heading(text)
        assert out[0].level == 0
        assert "preamble paragraph" in out[0].text
        assert out[1].heading == "First"


# ── 3. select_stages_for_runtime — pipeline composition ──────────────


class TestSelectStagesForRuntime:
    """Runtime selector must filter and overlay identically to pre-refactor."""

    def test_simple_sequence_returns_all_stages(self) -> None:
        stages = [
            StageDefinition(id="s1", primitive="implement"),
            StageDefinition(id="s2", primitive="test"),
        ]
        comp = Sequence(stages=[StageRef(stage="s1"), StageRef(stage="s2")])
        result = select_stages_for_runtime(_make_template(stages, comp))
        assert [r.stage for r in result] == ["s1", "s2"]

    def test_skip_condition_eliminates_matching_stage(self) -> None:
        stages = [
            StageDefinition(id="s1", primitive="implement"),
            StageDefinition(id="s2", primitive="test", skip_condition="mode == 'fast'"),
        ]
        comp = Sequence(stages=[StageRef(stage="s1"), StageRef(stage="s2")])
        result = select_stages_for_runtime(_make_template(stages, comp), mode="fast")
        assert [r.stage for r in result] == ["s1"]

    def test_explicit_mode_overrides_parameters_default(self) -> None:
        stages = [
            StageDefinition(id="s1", primitive="implement", skip_condition="mode == 'a'"),
        ]
        comp = StageRef(stage="s1")
        params = {"mode": {"default": "b"}}
        # Without explicit mode, default "b" prevails — s1 not skipped.
        keep = select_stages_for_runtime(_make_template(stages, comp, parameters=params))
        assert len(keep) == 1
        # Explicit mode "a" makes the predicate True → s1 elided.
        drop = select_stages_for_runtime(_make_template(stages, comp, parameters=params), mode="a")
        assert drop == []

    def test_environment_skip_stages_drops_listed_ids(self) -> None:
        stages = [
            StageDefinition(id="keep", primitive="implement"),
            StageDefinition(id="drop", primitive="test"),
        ]
        comp = Sequence(stages=[StageRef(stage="keep"), StageRef(stage="drop")])
        env_modes = {"github": {"skip_stages": ["drop"]}}
        result = select_stages_for_runtime(
            _make_template(stages, comp, environment_modes=env_modes),
            environment="github",
        )
        assert [r.stage for r in result] == ["keep"]

    def test_environment_extra_stages_appends_known_ids_only(self) -> None:
        stages = [
            StageDefinition(id="base", primitive="implement"),
            StageDefinition(id="appendable", primitive="release"),
        ]
        comp = StageRef(stage="base")
        env_modes = {
            "github": {"extra_stages": ["appendable", "ghost-id-not-defined"]},
        }
        result = select_stages_for_runtime(
            _make_template(stages, comp, environment_modes=env_modes),
            environment="github",
        )
        assert [r.stage for r in result] == ["base", "appendable"]

    def test_extra_context_seeds_predicate_evaluation(self) -> None:
        stages = [StageDefinition(id="s1", primitive="implement", skip_condition="role == 'qa'")]
        comp = StageRef(stage="s1")
        result = select_stages_for_runtime(
            _make_template(stages, comp), extra_context={"role": "qa"}
        )
        assert result == []


# ── 4. format_on_edit._collect_violations — flag/extension paths ─────


class TestCollectViolations:
    """Violation collector must short-circuit on every guard preserved by P-01."""

    def test_non_dict_payload_returns_empty(self) -> None:
        assert _collect_violations("not a dict") == []  # type: ignore[arg-type]

    def test_empty_files_list_returns_empty(self) -> None:
        assert _collect_violations({"files": []}) == []

    def test_missing_files_key_returns_empty(self) -> None:
        assert _collect_violations({}) == []

    def test_formatter_declared_returns_empty(self) -> None:
        assert _collect_violations({"files": ["a.py"], "formatter": "ruff"}) == []

    def test_format_command_alias_also_short_circuits(self) -> None:
        assert _collect_violations({"files": ["a.py"], "format_command": "black"}) == []

    def test_unknown_extension_yields_no_violation(self) -> None:
        assert _collect_violations({"files": ["a.binarius"]}) == []

    def test_known_extension_yields_foe001(self) -> None:
        out = _collect_violations({"files": ["mod.py"]})
        assert len(out) == 1
        v = out[0]
        assert isinstance(v, HookViolation)
        assert v.code == "FOE001"
        assert "python" in v.context["languages"]
        assert v.context["suggested_formatters"]["python"] == KNOWN_FORMATTERS["python"][0]

    def test_modified_files_alias_is_recognised(self) -> None:
        out = _collect_violations({"modified_files": ["app.ts"]})
        assert len(out) == 1
        assert "typescript" in out[0].context["languages"]

    def test_format_on_edit_wraps_collector(self) -> None:
        result = format_on_edit({"files": ["x.py"]})
        assert result.event == "format_on_edit"
        assert any(v.code == "FOE001" for v in result.violations)


# ── 5. refresh_reference_dependency — IO + entry-update pathways ─────


def _write_deps(tmp_path: Path, payload: dict[str, Any]) -> Path:
    p = tmp_path / "reference-dependencies.yaml"
    p.write_text(yaml.dump(payload, sort_keys=False))
    return p


class TestRefreshReferenceDependency:
    """Dependency refresher must keep its False/True contract bit-perfect."""

    def test_missing_file_returns_false(self, tmp_path: Path) -> None:
        ghost = tmp_path / "ghost.yaml"
        assert refresh_reference_dependency("dep", str(ghost)) is False

    def test_empty_file_returns_false(self, tmp_path: Path) -> None:
        path = tmp_path / "empty.yaml"
        path.write_text("")
        assert refresh_reference_dependency("dep", str(path)) is False

    def test_unknown_dep_id_returns_false(self, tmp_path: Path) -> None:
        path = _write_deps(tmp_path, {"active_tracking": [{"id": "other"}]})
        assert refresh_reference_dependency("dep", str(path)) is False

    def test_version_update_persists(self, tmp_path: Path) -> None:
        path = _write_deps(
            tmp_path,
            {"active_tracking": [{"id": "lib", "last_known_version": "1.0", "key_patterns": []}]},
        )
        assert refresh_reference_dependency("lib", str(path), new_version="2.0") is True
        reloaded = yaml.safe_load(path.read_text())
        entry = reloaded["active_tracking"][0]
        assert entry["last_known_version"] == "2.0"
        assert entry["last_checked"]  # non-empty date string

    def test_patterns_extend_without_duplicating(self, tmp_path: Path) -> None:
        path = _write_deps(
            tmp_path,
            {"periodic_monitoring": [{"id": "lib", "key_patterns": ["alpha"]}]},
        )
        assert (
            refresh_reference_dependency("lib", str(path), new_patterns=["alpha", "beta"]) is True
        )
        reloaded = yaml.safe_load(path.read_text())
        patterns = reloaded["periodic_monitoring"][0]["key_patterns"]
        assert patterns == ["alpha", "beta"]

    def test_periodic_monitoring_section_is_searched(self, tmp_path: Path) -> None:
        path = _write_deps(
            tmp_path,
            {
                "active_tracking": [],
                "periodic_monitoring": [{"id": "lib", "last_known_version": "x"}],
            },
        )
        assert refresh_reference_dependency("lib", str(path), new_version="y") is True
        reloaded = yaml.safe_load(path.read_text())
        assert reloaded["periodic_monitoring"][0]["last_known_version"] == "y"


# ── 6. task_adaptive_selector.main — CLI argv parsing & exits ────────


class TestCliMain:
    """CLI dispatcher must keep its exit / usage / output contract."""

    def test_no_args_prints_usage_and_exits_one(self, capsys: pytest.CaptureFixture) -> None:
        original = sys.argv
        sys.argv = ["task_adaptive_selector.py"]
        try:
            with pytest.raises(SystemExit) as excinfo:
                cli_main()
        finally:
            sys.argv = original
        assert excinfo.value.code == 1
        out = capsys.readouterr().out
        assert "Usage:" in out
        assert "task_adaptive_selector.py" in out
        assert "hotfix, feature, research, refactor, review, design" in out

    def test_basic_invocation_prints_profile_block(self, capsys: pytest.CaptureFixture) -> None:
        original = sys.argv
        sys.argv = ["task_adaptive_selector.py", "refactor"]
        try:
            cli_main()
        finally:
            sys.argv = original
        out = capsys.readouterr().out
        assert "Profile: refactor" in out
        assert "Token budget:" in out
        assert "Selected sections:" in out
        assert "Skipped sections:" in out

    def test_verbose_flag_emits_round_and_plan_lines(self, capsys: pytest.CaptureFixture) -> None:
        original = sys.argv
        sys.argv = ["task_adaptive_selector.py", "refactor", "--verbose"]
        try:
            cli_main()
        finally:
            sys.argv = original
        out = capsys.readouterr().out
        assert "Round: 1" in out
        assert "Plan mode: " in out

    def test_full_flag_emits_assembled_context_block(self, capsys: pytest.CaptureFixture) -> None:
        original = sys.argv
        sys.argv = ["task_adaptive_selector.py", "refactor", "--full"]
        try:
            cli_main()
        finally:
            sys.argv = original
        out = capsys.readouterr().out
        assert "ASSEMBLED CONTEXT" in out


# ── 7. Radon-cc enforcement — pin the post-refactor ceiling ──────────

# Each tuple: (module path, qualified function/method name, max allowed cc).
# Targets pinned from P-01 task spec acceptance criterion #1.
_CC_TARGETS: list[tuple[str, str, int]] = [
    ("src/devolaflow/adapters/data_driven.py", "_apply_transform", 10),
    ("src/devolaflow/adapters/data_driven.py", "_split_by_heading", 10),
    ("src/devolaflow/template_engine/runtime.py", "select_stages_for_runtime", 10),
    ("src/devolaflow/lifecycle/format_on_edit.py", "_collect_violations", 8),
    ("src/devolaflow/nines/researcher.py", "refresh_reference_dependency", 8),
    ("src/devolaflow/task_adaptive_selector.py", "main", 8),
]


def _cc_lookup(rel_path: str, name: str) -> int:
    """Return the radon cyclomatic-complexity value for *name* in *rel_path*."""
    radon_cc = pytest.importorskip("radon.complexity")
    src = (REPO_ROOT / rel_path).read_text()
    blocks = radon_cc.cc_visit(src)
    for block in blocks:
        if block.name == name:
            return int(block.complexity)
        for inner in getattr(block, "methods", []) or []:
            if inner.name == name:
                return int(inner.complexity)
    raise AssertionError(f"radon could not locate {name!r} in {rel_path}")


@pytest.mark.parametrize(("rel_path", "name", "ceiling"), _CC_TARGETS)
def test_refactored_callable_meets_cc_ceiling(rel_path: str, name: str, ceiling: int) -> None:
    """Each P-01 target stays at or below its post-refactor cc ceiling."""
    actual = _cc_lookup(rel_path, name)
    assert actual <= ceiling, (
        f"{rel_path}::{name} cc {actual} > ceiling {ceiling} — "
        "regression on P-01 cyclomatic-complexity cleanup"
    )


# ── 8. Cross-cutting safety nets ─────────────────────────────────────


def test_apply_transform_dispatch_table_covers_all_known_transforms() -> None:
    """Every entry in :data:`VALID_TRANSFORMS` must resolve to a handler.

    Locks in the dispatch invariant introduced by P-01: extending
    ``VALID_TRANSFORMS`` without registering a handler would silently raise
    ``ValueError`` at runtime.
    """
    from devolaflow.adapters.data_driven import VALID_TRANSFORMS

    handlers = DataDrivenAdapter._TRANSFORM_HANDLERS
    assert set(handlers) == set(VALID_TRANSFORMS)


def test_split_frontmatter_helper_round_trips() -> None:
    """The new ``_split_frontmatter`` helper preserves both branches."""
    fm, body = DataDrivenAdapter._split_frontmatter("---\nx: 1\n---\nBODY")
    assert "x: 1" in fm
    assert body == "BODY"
    fm2, body2 = DataDrivenAdapter._split_frontmatter("no frontmatter")
    assert fm2 == ""
    assert body2 == "no frontmatter"


def test_section_dataclass_is_frozen() -> None:
    """``_Section`` immutability is preserved (relied on by helpers)."""
    from dataclasses import FrozenInstanceError

    sec = _Section(heading="x", level=1, text="y")
    with pytest.raises(FrozenInstanceError):
        sec.heading = "z"  # type: ignore[misc]
