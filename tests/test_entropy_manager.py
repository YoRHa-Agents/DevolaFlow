"""Tests for :mod:`devolaflow.entropy_manager` (v8.0.0 P-11).

Covers three responsibilities of the entropy manager plus integration with
:mod:`devolaflow.check_drift`:

* :class:`DocFreshness` — scan, scoring, threshold behaviour.
* :class:`DeviationScanner` — frontmatter mismatch detection, print output.
* :func:`cleanup` — dry-run planning, apply with destructive actions,
  error handling (S-5 no silent failures).

Target: ≥ 35 tests. Each behaviour has at least one happy-path + one
edge-case test. Integration tests verify the entropy-cleanup template
instantiates and that ``check_drift`` delegates correctly.
"""

from __future__ import annotations

import io
import os
import sys
import time
from contextlib import redirect_stdout
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from devolaflow.entropy_manager import (
    ApplyReport,
    DeviationRecord,
    DeviationReport,
    DeviationScanner,
    DocFreshness,
    DocFreshnessRecord,
    DocFreshnessReport,
    DryRunReport,
    RetentionRule,
    _apply_action,
    _match_rule,
    _parse_frontmatter,
    _plan_actions,
    cleanup,
    iter_documents,
)

# ── Helpers ─────────────────────────────────────────────────────────────


def _write_md(path: Path, frontmatter: dict | None = None, body: str = "# Body\n") -> Path:
    """Create a markdown file with optional YAML frontmatter."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if frontmatter is None:
        path.write_text(body, encoding="utf-8")
        return path
    lines = ["---"]
    for key, value in frontmatter.items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                lines.append(f"  - {item}")
        else:
            lines.append(f"{key}: {value}")
    lines.append("---")
    lines.append(body)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _age_file(path: Path, age_days: float) -> None:
    """Backdate a file's mtime by ``age_days``."""
    target_ts = time.time() - age_days * 86400.0
    os.utime(path, (target_ts, target_ts))


# ── iter_documents ──────────────────────────────────────────────────────


class TestIterDocuments:
    def test_returns_empty_for_missing_root(self, tmp_path: Path) -> None:
        assert iter_documents(tmp_path / "does-not-exist") == []

    def test_finds_markdown(self, tmp_path: Path) -> None:
        _write_md(tmp_path / "a.md", body="hello")
        _write_md(tmp_path / "nested/b.md", body="world")
        files = iter_documents(tmp_path)
        names = {f.name for f in files}
        assert names == {"a.md", "b.md"}

    def test_skips_hidden_directories(self, tmp_path: Path) -> None:
        _write_md(tmp_path / ".git/ignore_me.md", body="x")
        _write_md(tmp_path / "keep.md", body="y")
        assert {f.name for f in iter_documents(tmp_path)} == {"keep.md"}

    def test_filters_by_suffix(self, tmp_path: Path) -> None:
        _write_md(tmp_path / "a.md", body="x")
        (tmp_path / "b.txt").write_text("not a doc")
        files = iter_documents(tmp_path, suffixes=(".md",))
        assert [f.name for f in files] == ["a.md"]

    def test_accepts_custom_suffixes(self, tmp_path: Path) -> None:
        (tmp_path / "a.rst").write_text("x")
        (tmp_path / "b.md").write_text("y")
        files = iter_documents(tmp_path, suffixes=(".rst",))
        assert [f.name for f in files] == ["a.rst"]

    def test_is_sorted(self, tmp_path: Path) -> None:
        for name in ["z.md", "a.md", "m.md"]:
            (tmp_path / name).write_text("x")
        assert [f.name for f in iter_documents(tmp_path)] == ["a.md", "m.md", "z.md"]


# ── _parse_frontmatter ──────────────────────────────────────────────────


class TestParseFrontmatter:
    def test_returns_empty_when_no_frontmatter(self, tmp_path: Path) -> None:
        p = tmp_path / "a.md"
        p.write_text("no fence here\n")
        assert _parse_frontmatter(p) == {}

    def test_parses_valid_frontmatter(self, tmp_path: Path) -> None:
        p = _write_md(tmp_path / "a.md", {"version": "1.2.3", "title": "T"})
        fm = _parse_frontmatter(p)
        assert fm["version"] == "1.2.3"
        assert fm["title"] == "T"

    def test_returns_empty_on_malformed_yaml(self, tmp_path: Path) -> None:
        p = tmp_path / "a.md"
        p.write_text("---\n  foo:\n\tbad_indent\n---\nbody")
        assert _parse_frontmatter(p) == {}

    def test_returns_empty_on_missing_file(self, tmp_path: Path) -> None:
        assert _parse_frontmatter(tmp_path / "does-not-exist.md") == {}

    def test_returns_empty_on_incomplete_fence(self, tmp_path: Path) -> None:
        p = tmp_path / "a.md"
        p.write_text("---\nversion: 1.0\n")
        assert _parse_frontmatter(p) == {}


# ── DocFreshness ────────────────────────────────────────────────────────


class TestDocFreshnessConstruction:
    def test_default_values(self) -> None:
        df = DocFreshness()
        assert df.staleness_threshold_days == 30
        assert df.max_age_days == 365

    def test_rejects_negative_threshold(self) -> None:
        with pytest.raises(ValueError, match="staleness_threshold_days"):
            DocFreshness(staleness_threshold_days=-1)

    def test_rejects_zero_max_age(self) -> None:
        with pytest.raises(ValueError, match="max_age_days"):
            DocFreshness(max_age_days=0)


class TestDocFreshnessScoring:
    def test_score_zero_for_fresh(self) -> None:
        assert DocFreshness().score(0.0) == 0.0

    def test_score_clamped_to_one(self) -> None:
        df = DocFreshness(max_age_days=10)
        assert df.score(9999) == 1.0

    def test_score_linear(self) -> None:
        df = DocFreshness(max_age_days=100)
        assert df.score(50) == pytest.approx(0.5)

    def test_score_negative_age_is_zero(self) -> None:
        assert DocFreshness().score(-5) == 0.0


class TestDocFreshnessScan:
    def test_scan_empty_directory(self, tmp_path: Path) -> None:
        report = DocFreshness().scan(tmp_path)
        assert report.records == ()
        assert report.stale_count == 0
        assert report.fresh_count == 0

    def test_scan_marks_stale_by_threshold(self, tmp_path: Path) -> None:
        stale = _write_md(tmp_path / "stale.md", body="old")
        _age_file(stale, age_days=100)
        _write_md(tmp_path / "fresh.md", body="new")
        df = DocFreshness(staleness_threshold_days=30, max_age_days=200)
        report = df.scan(tmp_path)
        by_name = {r.path.name: r for r in report.records}
        assert by_name["stale.md"].is_stale is True
        assert by_name["fresh.md"].is_stale is False

    def test_scan_stale_count_matches(self, tmp_path: Path) -> None:
        for i in range(3):
            _age_file(_write_md(tmp_path / f"old{i}.md", body="x"), age_days=60)
        _write_md(tmp_path / "new.md", body="y")
        report = DocFreshness(staleness_threshold_days=30).scan(tmp_path)
        assert report.stale_count == 3
        assert report.fresh_count == 1

    def test_scan_preserves_threshold_in_report(self, tmp_path: Path) -> None:
        report = DocFreshness(staleness_threshold_days=45).scan(tmp_path)
        assert report.threshold_days == 45

    def test_scan_handles_missing_root(self, tmp_path: Path) -> None:
        report = DocFreshness().scan(tmp_path / "no-such-dir")
        assert report.records == ()

    def test_scan_score_ordering(self, tmp_path: Path) -> None:
        old = _write_md(tmp_path / "old.md", body="x")
        _age_file(old, age_days=200)
        _write_md(tmp_path / "new.md", body="y")
        df = DocFreshness(staleness_threshold_days=30, max_age_days=365)
        report = df.scan(tmp_path)
        scores = {r.path.name: r.staleness_score for r in report.records}
        assert scores["old.md"] > scores["new.md"]


# ── DeviationScanner ────────────────────────────────────────────────────


def _build_human_agent_fixture(root: Path, expected: str, declared: str) -> None:
    """Lay out a minimal human + agent frontmatter pair under ``root``."""
    agent_dir = root / "workflow-system" / "agent"
    human_dir = root / "workflow-system" / "human" / "en"
    _write_md(agent_dir / "skill.md", {"version": expected}, body="# skill")
    _write_md(
        human_dir / "overview.md",
        {"source_version": declared, "source_files": ["skill.md"]},
        body="# overview",
    )


class TestDeviationScanner:
    def test_detects_version_drift(self, tmp_path: Path) -> None:
        _build_human_agent_fixture(tmp_path, expected="2.0.0", declared="1.0.0")
        scanner = DeviationScanner(project_root=tmp_path)
        report = scanner.scan()
        assert report.drift_detected
        assert len(report.stale_docs) == 1
        rec = report.stale_docs[0]
        assert rec.expected_version == "2.0.0"
        assert rec.declared_version == "1.0.0"

    def test_no_drift_when_versions_match(self, tmp_path: Path) -> None:
        _build_human_agent_fixture(tmp_path, expected="1.0.0", declared="1.0.0")
        report = DeviationScanner(project_root=tmp_path).scan()
        assert not report.drift_detected
        assert report.stale_docs == ()

    def test_ignores_missing_source_files(self, tmp_path: Path) -> None:
        human_dir = tmp_path / "workflow-system" / "human" / "en"
        _write_md(
            human_dir / "overview.md",
            {"source_version": "1.0.0", "source_files": ["missing.md"]},
            body="# x",
        )
        report = DeviationScanner(project_root=tmp_path).scan()
        assert not report.drift_detected

    def test_handles_missing_human_dir(self, tmp_path: Path) -> None:
        report = DeviationScanner(project_root=tmp_path).scan()
        assert report.stale_docs == ()

    def test_multiple_source_refs(self, tmp_path: Path) -> None:
        agent_dir = tmp_path / "workflow-system" / "agent"
        human_dir = tmp_path / "workflow-system" / "human" / "en"
        _write_md(agent_dir / "a.md", {"version": "2.0.0"}, body="x")
        _write_md(agent_dir / "b.md", {"version": "3.0.0"}, body="y")
        _write_md(
            human_dir / "overview.md",
            {"source_version": "1.0.0", "source_files": ["a.md", "b.md"]},
            body="# doc",
        )
        report = DeviationScanner(project_root=tmp_path).scan()
        assert len(report.stale_docs) == 2
        refs = sorted(r.source_ref for r in report.stale_docs)
        assert refs == ["a.md", "b.md"]

    def test_print_report_no_drift(self, tmp_path: Path) -> None:
        _build_human_agent_fixture(tmp_path, expected="1.0.0", declared="1.0.0")
        buf = io.StringIO()
        with redirect_stdout(buf):
            result = DeviationScanner(project_root=tmp_path).print_report()
        assert result is False
        assert "No drift detected" in buf.getvalue()

    def test_print_report_with_drift(self, tmp_path: Path) -> None:
        _build_human_agent_fixture(tmp_path, expected="2.0.0", declared="1.0.0")
        buf = io.StringIO()
        with redirect_stdout(buf):
            result = DeviationScanner(project_root=tmp_path).print_report()
        output = buf.getvalue()
        assert result is True
        assert "Drift detected" in output
        assert "source=2.0.0" in output
        assert "doc has=1.0.0" in output
        assert "1 stale file(s)" in output

    def test_print_report_accepts_preloaded(self, tmp_path: Path) -> None:
        preloaded = DeviationReport(scanned_at="now", stale_docs=())
        buf = io.StringIO()
        with redirect_stdout(buf):
            result = DeviationScanner(project_root=tmp_path).print_report(preloaded)
        assert result is False
        assert "No drift" in buf.getvalue()

    def test_deviation_record_fields(self) -> None:
        rec = DeviationRecord(
            human_doc=Path("workflow-system/human/en/overview.md"),
            source_ref="skill.md",
            expected_version="2.0.0",
            declared_version="1.0.0",
        )
        assert rec.source_ref == "skill.md"


# ── RetentionRule ───────────────────────────────────────────────────────


class TestRetentionRule:
    def test_construction(self) -> None:
        rule = RetentionRule(min_staleness_score=0.5, action="flag", reason="demo")
        assert rule.action == "flag"
        assert rule.reason == "demo"

    def test_rejects_out_of_range_score(self) -> None:
        with pytest.raises(ValueError, match="min_staleness_score"):
            RetentionRule(min_staleness_score=1.5, action="flag")

    def test_rejects_negative_score(self) -> None:
        with pytest.raises(ValueError, match="min_staleness_score"):
            RetentionRule(min_staleness_score=-0.1, action="flag")

    def test_rejects_unknown_action(self) -> None:
        with pytest.raises(ValueError, match="Unknown cleanup action"):
            RetentionRule(min_staleness_score=0.5, action="nuke")  # type: ignore[arg-type]


# ── _match_rule / _plan_actions ─────────────────────────────────────────


class TestRuleMatching:
    def test_match_rule_returns_highest_threshold(self) -> None:
        rules = [
            RetentionRule(min_staleness_score=0.3, action="flag"),
            RetentionRule(min_staleness_score=0.7, action="archive"),
            RetentionRule(min_staleness_score=0.9, action="delete"),
        ]
        assert _match_rule(0.8, rules).action == "archive"
        assert _match_rule(0.95, rules).action == "delete"
        assert _match_rule(0.4, rules).action == "flag"

    def test_match_rule_returns_none_when_under_threshold(self) -> None:
        rules = [RetentionRule(min_staleness_score=0.5, action="flag")]
        assert _match_rule(0.1, rules) is None

    def test_plan_actions_collects_matches(self, tmp_path: Path) -> None:
        df = DocFreshness(staleness_threshold_days=1, max_age_days=100)
        old = _write_md(tmp_path / "old.md", body="x")
        _age_file(old, age_days=99)
        _write_md(tmp_path / "fresh.md", body="y")
        report = df.scan(tmp_path)
        rules = [RetentionRule(min_staleness_score=0.5, action="flag")]
        plan = _plan_actions(report, rules)
        assert len(plan) == 1
        assert plan[0][0].name == "old.md"
        assert plan[0][1] == "flag"


# ── cleanup (dry-run + apply) ───────────────────────────────────────────


class TestCleanupDryRun:
    def test_dry_run_default_rule_flags_stale(self, tmp_path: Path) -> None:
        old = _write_md(tmp_path / "old.md", body="x")
        _age_file(old, age_days=365)
        report = cleanup(
            tmp_path,
            freshness=DocFreshness(staleness_threshold_days=30, max_age_days=200),
        )
        assert isinstance(report, DryRunReport)
        assert len(report.planned_actions) == 1
        assert report.planned_actions[0][1] == "flag"
        assert old.exists()  # dry-run must not touch FS

    def test_dry_run_skips_fresh_files(self, tmp_path: Path) -> None:
        _write_md(tmp_path / "fresh.md", body="x")
        report = cleanup(tmp_path)
        assert isinstance(report, DryRunReport)
        assert report.planned_actions == ()

    def test_dry_run_with_deviation(self, tmp_path: Path) -> None:
        _build_human_agent_fixture(tmp_path, expected="2.0.0", declared="1.0.0")
        scanner = DeviationScanner(project_root=tmp_path)
        report = cleanup(tmp_path, deviation=scanner)
        assert isinstance(report, DryRunReport)
        assert report.deviation_report is not None
        assert report.deviation_report.drift_detected

    def test_dry_run_includes_freshness_report(self, tmp_path: Path) -> None:
        _write_md(tmp_path / "a.md", body="x")
        report = cleanup(tmp_path)
        assert report.freshness_report is not None
        assert len(report.freshness_report.records) == 1


class TestCleanupApply:
    def test_apply_deletes_when_rule_allows(self, tmp_path: Path) -> None:
        doomed = _write_md(tmp_path / "doomed.md", body="x")
        _age_file(doomed, age_days=365)
        rules = [RetentionRule(min_staleness_score=0.5, action="delete", reason="age")]
        report = cleanup(
            tmp_path,
            retention_rules=rules,
            freshness=DocFreshness(staleness_threshold_days=30, max_age_days=200),
            dry_run=False,
        )
        assert isinstance(report, ApplyReport)
        assert any(action == "delete" for _, action, _ in report.applied_actions)
        assert not doomed.exists()

    def test_apply_flag_is_noop_on_disk(self, tmp_path: Path) -> None:
        doc = _write_md(tmp_path / "a.md", body="x")
        _age_file(doc, age_days=365)
        report = cleanup(
            tmp_path,
            freshness=DocFreshness(staleness_threshold_days=30, max_age_days=200),
            dry_run=False,
        )
        assert isinstance(report, ApplyReport)
        assert doc.exists()
        assert any(action == "flag" for _, action, _ in report.applied_actions)

    def test_apply_archive_moves_file(self, tmp_path: Path) -> None:
        doc = _write_md(tmp_path / "a.md", body="x")
        _age_file(doc, age_days=365)
        rules = [RetentionRule(min_staleness_score=0.5, action="archive", reason="age")]
        report = cleanup(
            tmp_path,
            retention_rules=rules,
            freshness=DocFreshness(staleness_threshold_days=30, max_age_days=200),
            dry_run=False,
        )
        assert isinstance(report, ApplyReport)
        assert not doc.exists()
        assert (tmp_path / "_archive" / "a.md").exists()
        assert any(action == "archive" for _, action, _ in report.applied_actions)

    def test_apply_touch_refreshes_mtime(self, tmp_path: Path) -> None:
        doc = _write_md(tmp_path / "a.md", body="x")
        _age_file(doc, age_days=365)
        before = doc.stat().st_mtime
        rules = [RetentionRule(min_staleness_score=0.5, action="touch", reason="refresh")]
        cleanup(
            tmp_path,
            retention_rules=rules,
            freshness=DocFreshness(staleness_threshold_days=30, max_age_days=200),
            dry_run=False,
        )
        after = doc.stat().st_mtime
        assert after > before

    def test_apply_records_errors_without_silencing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """S-5: errors surface via :attr:`ApplyReport.errors`, never silent."""
        doomed = _write_md(tmp_path / "a.md", body="x")
        _age_file(doomed, age_days=365)

        def boom(path, action):  # noqa: ARG001
            raise OSError("permission denied")

        monkeypatch.setattr("devolaflow.entropy_manager._apply_action", boom)
        rules = [RetentionRule(min_staleness_score=0.5, action="delete", reason="age")]
        report = cleanup(
            tmp_path,
            retention_rules=rules,
            freshness=DocFreshness(staleness_threshold_days=30, max_age_days=200),
            dry_run=False,
        )
        assert isinstance(report, ApplyReport)
        assert report.applied_actions == ()
        assert len(report.errors) == 1
        assert "permission denied" in report.errors[0][1]

    def test_apply_action_rejects_invalid_inline(self, tmp_path: Path) -> None:
        """``_apply_action`` with an unknown string is treated as a no-op (flag)."""
        doc = _write_md(tmp_path / "a.md", body="x")
        _apply_action(doc, "flag")
        assert doc.exists()


# ── Integration: check_drift delegates to DeviationScanner ──────────────


class TestCheckDriftIntegration:
    def test_check_drift_delegates_to_scanner(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``devolaflow.check_drift.check_drift`` should route via DeviationScanner."""
        _build_human_agent_fixture(tmp_path, expected="2.0.0", declared="1.0.0")
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
        monkeypatch.setattr("devolaflow.check_drift._find_project_root", lambda: tmp_path)
        from devolaflow.check_drift import check_drift

        buf = io.StringIO()
        with redirect_stdout(buf):
            has_drift = check_drift()
        assert has_drift is True
        assert "Drift detected" in buf.getvalue()

    def test_check_drift_no_drift_returns_false(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _build_human_agent_fixture(tmp_path, expected="1.0.0", declared="1.0.0")
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
        monkeypatch.setattr("devolaflow.check_drift._find_project_root", lambda: tmp_path)
        from devolaflow.check_drift import check_drift

        buf = io.StringIO()
        with redirect_stdout(buf):
            assert check_drift() is False
        assert "No drift detected" in buf.getvalue()


# ── Integration: entropy-cleanup composition (v15-ADR-002) ──────────────
# entropy-cleanup.yaml was deleted at v15.0.0 (Phase B collapse per
# v15-ADR-002); the name lives on as a named composition over the
# change-driven survivor in templates/registry.yaml#compositions. The
# original v8.0.0 P-11 pins below are updated to the alias-layer truth.


class TestEntropyCleanupTemplate:
    def test_template_registered_as_composition(self) -> None:
        from devolaflow.template_engine.registry import TemplateRegistry

        reg = TemplateRegistry()
        assert "entropy-cleanup" in reg.compositions(), (
            "entropy-cleanup must stay registered as a composition alias "
            "(v15-ADR-002 >=1-major guarantee)"
        )

    def test_template_validates(self) -> None:
        from devolaflow.template_engine.registry import TemplateRegistry
        from devolaflow.template_engine.validator import validate_template

        reg = TemplateRegistry()
        tpl = reg.load_template("entropy-cleanup")
        assert tpl is not None
        result = validate_template(tpl)
        assert result.valid, f"template invalid: {result.errors}"

    def test_template_resolves_via_change_driven(self) -> None:
        # Post-collapse the alias resolves to a template SYNTHESIZED from
        # the manifest entry's C-3 verbatim stage sequence (the deleted
        # yaml's stages survive byte-equal), with the change-driven base
        # + stage_aliases recorded under parameters["composition"].
        from devolaflow.template_engine.registry import TemplateRegistry

        reg = TemplateRegistry()
        tpl = reg.load_template("entropy-cleanup")
        assert tpl is not None
        assert {s.id for s in tpl.stages} == {"scan", "propose", "review", "apply"}
        record = tpl.parameters["composition"]
        assert record["alias_of"] == "change-driven"
        assert record["params"]["stage_aliases"] == {"propose": "scan", "verify": "review"}

    def test_template_count_matches_survivor_set(self) -> None:
        # Was `test_template_count_is_23`: the 23-name surface is now
        # 7 survivor yamls + 16 compositions (v15-ADR-002 survivor set).
        from devolaflow.template_engine.registry import TemplateRegistry

        reg = TemplateRegistry()
        assert len(reg.discover()) == 7
        assert len(reg.compositions()) == 16
        assert len(reg.discover()) + len(reg.compositions()) == 23


# ── Regression: learnings refactor preserves public API ─────────────────


class TestLearningsRefactor:
    def test_load_relevant_learnings_still_imports(self) -> None:
        from devolaflow.learnings import load_relevant_learnings

        assert callable(load_relevant_learnings)

    def test_decay_confidence_still_imports(self) -> None:
        from devolaflow.learnings import decay_confidence

        assert callable(decay_confidence)

    def test_entry_to_learning_skips_malformed(self) -> None:
        from devolaflow.learnings import _entry_to_learning

        assert _entry_to_learning({"not_a_learning_field": 1}) is None

    def test_entry_ttl_valid_accepts_missing_timestamp(self) -> None:
        from devolaflow.learnings import _entry_ttl_valid

        assert _entry_ttl_valid({}, datetime.now(UTC)) is True

    def test_entry_ttl_valid_rejects_expired(self) -> None:
        from devolaflow.learnings import _entry_ttl_valid

        expired = (datetime.now(UTC) - timedelta(days=200)).isoformat()
        assert _entry_ttl_valid({"timestamp": expired, "ttl_days": 30}, datetime.now(UTC)) is False

    def test_entry_ttl_valid_rejects_malformed(self) -> None:
        from devolaflow.learnings import _entry_ttl_valid

        assert _entry_ttl_valid({"timestamp": "nonsense"}, datetime.now(UTC)) is False

    def test_decay_formula_returns_clamped_value(self) -> None:
        from devolaflow.learnings import _decay_formula

        new_conf = _decay_formula(prior_confidence=0.8, delta_days=15, half_life_days=30)
        assert 0.0 <= new_conf <= 1.0


# ── Module import smoke test ────────────────────────────────────────────


def test_module_all_exports_are_resolvable() -> None:
    """Every name in ``__all__`` must be importable."""
    from devolaflow import entropy_manager as em

    for name in em.__all__:
        assert hasattr(em, name), f"missing export: {name}"


def test_freshness_record_fields() -> None:
    rec = DocFreshnessRecord(path=Path("a.md"), age_days=1.0, staleness_score=0.01, is_stale=False)
    assert rec.path.name == "a.md"


def test_freshness_report_counts_align() -> None:
    fr = DocFreshnessReport(scanned_at="now", threshold_days=30, records=())
    assert fr.stale_count == 0
    assert fr.fresh_count == 0


def test_python_version_compatible() -> None:
    """Module requires Python 3.11+ for ``datetime.UTC``."""
    assert sys.version_info >= (3, 11)
