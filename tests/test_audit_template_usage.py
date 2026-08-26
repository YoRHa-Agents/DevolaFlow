"""Tests for the v10.5.0 PV-02 D-A-2 template usage audit script.

Pins the public contract of ``scripts/audit_template_usage.py`` per
`.local/research/v11.0.0_patches/D-A-2.md` §2 Phase A:

1. :func:`scan_template_yamls` returns the basenames of every yaml
   under ``workflow-system/agent/templates/builtin/``.
2. :func:`count_cycle_mentions` + :func:`count_changelog_mentions`
   are conservative regex counts; zero on missing inputs.
3. :func:`classify_template` returns ``"USED"`` iff any of the 3
   evidence sources is non-zero; ``"REGISTERED"`` otherwise.
4. :func:`render_markdown_report` produces the expected sections.
5. :func:`run` exits 0 on missing inputs (operator-friendly).
6. The pinned baseline sets (TIER_1_USED_BASELINE +
   TIER_2_LEGACY_BASELINE) cover all 22 v10.3.0 templates.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import audit_template_usage as audit  # noqa: E402


def test_baseline_sets_cover_22_templates() -> None:
    """The pinned TIER-1 + TIER-2 sets union to 22 names with no overlap.

    Pins the v10.3.0 corpus baseline per
    `.local/research/v11.0.0_patches/D-A-2.md` §1.
    """
    union = audit.TIER_1_USED_BASELINE | audit.TIER_2_LEGACY_BASELINE
    assert len(union) == 22, f"expected 22 templates total, got {len(union)}"
    assert audit.TIER_1_USED_BASELINE.isdisjoint(audit.TIER_2_LEGACY_BASELINE), (
        "TIER-1 and TIER-2 must be disjoint"
    )
    assert len(audit.TIER_1_USED_BASELINE) == 6
    assert len(audit.TIER_2_LEGACY_BASELINE) == 16


def test_scan_template_yamls_returns_sorted(tmp_path: Path) -> None:
    """Returns sorted basenames; ignores non-yaml siblings."""
    template_dir = tmp_path / "workflow-system" / "agent" / "templates" / "builtin"
    template_dir.mkdir(parents=True)
    for name in ("hotfix.yaml", "change-driven.yaml", "spike-poc.yaml", "README.md"):
        (template_dir / name).write_text("schema_version: '1.0'", encoding="utf-8")
    names = audit.scan_template_yamls(tmp_path)
    assert names == ["change-driven", "hotfix", "spike-poc"]


def test_scan_template_yamls_handles_missing_dir(tmp_path: Path) -> None:
    """Missing template dir -> empty list, no error."""
    assert audit.scan_template_yamls(tmp_path) == []


def test_scan_compositions_derives_from_registry(tmp_path: Path) -> None:
    """v15-ADR-002: composition names derive from registry.yaml; absent -> [].

    The real repo manifest is walked alongside the survivors so all
    registered workflow types stay auditable after the Phase B collapse.
    """
    assert audit.scan_compositions(tmp_path) == []

    templates = tmp_path / "workflow-system" / "agent" / "templates"
    templates.mkdir(parents=True)
    (templates / "registry.yaml").write_text(
        'schema_version: "2.0"\n'
        "compositions:\n"
        "  - name: hotfix\n"
        "    base: change-driven\n"
        "  - name: spike-poc\n"
        "    base: change-driven\n"
        "templates:\n"
        "  - name: change-driven\n",
        encoding="utf-8",
    )
    assert audit.scan_compositions(tmp_path) == ["hotfix", "spike-poc"]

    repo_root = Path(__file__).resolve().parents[1]
    live = audit.scan_compositions(repo_root)
    assert len(live) == 17, f"expected the 17 collapsed names, got {len(live)}: {live}"


def test_count_cycle_mentions_counts_across_globs(tmp_path: Path) -> None:
    """Counts every doc match across the v9.* + v10.* globs."""
    research = tmp_path / ".local" / "research"
    research.mkdir(parents=True)
    (research / "v9.5.0_cycle_plan.md").write_text(
        "the hotfix template is mentioned. hotfix again.", encoding="utf-8"
    )
    (research / "v10.2.0_retrospective.md").write_text(
        "the hotfix template was used in v10.0.0", encoding="utf-8"
    )
    assert audit.count_cycle_mentions(tmp_path, "hotfix") == 3


def test_count_cycle_mentions_zero_when_research_absent(tmp_path: Path) -> None:
    """Missing `.local/research/` -> 0 (no error)."""
    assert audit.count_cycle_mentions(tmp_path, "hotfix") == 0


def test_count_changelog_mentions_zero_when_absent(tmp_path: Path) -> None:
    """Missing CHANGELOG -> 0."""
    assert audit.count_changelog_mentions(tmp_path, "hotfix") == 0


def test_count_changelog_mentions_counts_word_boundary(tmp_path: Path) -> None:
    """Only counts ``\\b<name>\\b`` not substring matches."""
    (tmp_path / "CHANGELOG.md").write_text(
        "## [10.5.0]\nThe hotfix template ships. hotfix-related improvements.\n",
        encoding="utf-8",
    )
    # Both 'hotfix' words count, but 'hotfix-related' has a word boundary
    # at the hyphen too — so 'hotfix' as a whole word matches there as well.
    assert audit.count_changelog_mentions(tmp_path, "hotfix") == 2


def test_classify_template_used_when_any_source_nonzero(tmp_path: Path) -> None:
    """USED iff any of cycle / changelog / git mentions > 0."""
    (tmp_path / "CHANGELOG.md").write_text("## [10.5.0]\nspike-poc shipped.", encoding="utf-8")
    assert audit.classify_template(tmp_path, "spike-poc") == "USED"
    # No mention anywhere -> REGISTERED.
    assert audit.classify_template(tmp_path, "non-existent-template") == "REGISTERED"


def test_render_markdown_report_carries_required_sections() -> None:
    """Output carries Summary + TIER-1 + TIER-2 + Phase A headings."""
    verdicts = {
        "change-driven": {
            "cycle_mentions": 8,
            "changelog_mentions": 1,
            "git_mentions": 0,
            "verdict": "USED",
        },
        "feature-enhancement": {
            "cycle_mentions": 0,
            "changelog_mentions": 0,
            "git_mentions": 0,
            "verdict": "REGISTERED",
        },
    }
    md = audit.render_markdown_report(verdicts)
    assert "# v10.5.0 PV-02 D-A-2 Template Usage Audit (Phase A)" in md
    assert "## Summary" in md
    assert "## TIER-1 USED" in md
    assert "## TIER-2 REGISTERED" in md
    assert "## Phase A deliverables (this PV)" in md
    assert "`change-driven`" in md
    assert "`feature-enhancement`" in md


def test_run_emits_json_with_verdicts(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """``--json`` emits parseable JSON with ``verdicts`` mapping."""
    template_dir = tmp_path / "workflow-system" / "agent" / "templates" / "builtin"
    template_dir.mkdir(parents=True)
    (template_dir / "spike-poc.yaml").write_text("schema_version: '1.0'", encoding="utf-8")

    rc = audit.run(tmp_path, json_out=True)
    assert rc == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert "verdicts" in payload
    assert "spike-poc" in payload["verdicts"]
    # No mentions anywhere -> REGISTERED.
    assert payload["verdicts"]["spike-poc"]["verdict"] == "REGISTERED"


def test_run_emits_markdown_to_output(tmp_path: Path) -> None:
    """``--output`` writes markdown to disk."""
    template_dir = tmp_path / "workflow-system" / "agent" / "templates" / "builtin"
    template_dir.mkdir(parents=True)
    (template_dir / "hotfix.yaml").write_text("schema_version: '1.0'", encoding="utf-8")
    out = tmp_path / "report.md"
    rc = audit.run(tmp_path, output=out)
    assert rc == 0
    assert "# v10.5.0 PV-02 D-A-2 Template Usage Audit" in out.read_text(encoding="utf-8")
