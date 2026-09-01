"""Ghost audit — consolidated W-18 feature stanza for the v17.1.0 slice.

Pins the harness-construction branch surfaces (24th seed / 17th
composition, the ``harness gap`` inventory CLI + capability-review
comparison, the OPTIONAL ``harness_preflight.md`` C-9 artifact + HPF
lint family, the archive capability-review gate, and the 27th SF-4
reference) BEFORE the cycle's CHANGELOG entry lands, per W-18.

Design contract: ``.local/tasks/add_harness_design/design.md``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from tests.ghost.test_registries import _SF4_REFERENCE_SET

# Public gap-inventory API re-exported from ``devolaflow.harness``
# (owner module ``devolaflow.harness.gap``).
_GAP_PUBLIC_API: tuple[str, ...] = (
    "BUILTIN_GAP_AXES",
    "GapConfigError",
    "build_gap_report",
    "compare_gap_reports",
    "load_gap_report",
    "render_capability_review",
)


@pytest.mark.parametrize("symbol", _GAP_PUBLIC_API)
def test_v17_1_0_gap_public_api_exported(symbol: str) -> None:
    """W-18 v17.1.0: every gap symbol is real and package-exported."""
    import devolaflow.harness as harness

    assert symbol in harness.__all__, f"{symbol} missing from devolaflow.harness.__all__"
    value = getattr(harness, symbol)
    if symbol == "BUILTIN_GAP_AXES":
        # The six built-in coverage axes (design §3.2), low-intrusion by
        # construction: observation points are enumerated, never hooked.
        assert value == (
            "observation",
            "evaluation",
            "probe",
            "baseline",
            "signal",
            "loop-closure",
        )
    elif symbol == "GapConfigError":
        # Malformed --axes-config fails loud per S-5.
        assert issubclass(value, ValueError)
    else:
        assert callable(value)


def test_v17_1_0_harness_construction_branch_wired(project_root: Path) -> None:
    """W-18 v17.1.0: seed + gap CLI + preflight lint + archive gate + SF-4.

    Pins (a) the ``harness-construction`` seed registration (24th seed,
    17th composition), (b) the ``gap`` subcommand in the harness argparse
    tree with its documented flags, (c) the ``harness_preflight.md`` C-9
    budget row + the five HPF finding codes, (d) the harness-flagged
    archive gate symbols, (e) the schema file + 27th SF-4 reference.
    """
    # ── (a) seed registered in registry.yaml ──
    template_dir = project_root / "workflow-system" / "agent" / "templates"
    registry = yaml.safe_load((template_dir / "registry.yaml").read_text(encoding="utf-8"))
    compositions = registry["compositions"]
    composition_names = {entry["name"] for entry in compositions}
    assert "harness-construction" in composition_names
    # The v17.1 feature claim above remains historical; these are live
    # registry-parity checks and must follow later seed additions.
    assert len(compositions) == 21
    assert len(compositions) + len(registry["templates"]) == 28
    seed_entry = next(e for e in compositions if e["name"] == "harness-construction")
    assert (template_dir / seed_entry["seed"]).is_file()
    assert seed_entry["seed"] == "seeds/harness-construction.yaml"

    # ── (b) gap CLI subcommand present in the argparse tree ──
    from devolaflow.harness.__main__ import _parser

    args = _parser().parse_args(
        [
            "gap",
            "--ledger",
            "ledger.jsonl",
            "--repo",
            ".",
            "--axes-config",
            "harness_axes.yaml",
            "--compare",
            "harness_gap_before.json",
            "--review-output",
            "harness_capability_review.md",
        ]
    )
    assert args.command == "gap"

    # ── (c) C-9 budget row + HPF finding codes ──
    from devolaflow.agent_workspace.lint import (
        CHECKLIST_ARTIFACT_BUDGETS,
        _check_harness_preflight,
    )
    from devolaflow.agent_workspace.lint import (
        HARNESS_PREFLIGHT_FILENAME as LINT_HARNESS_PREFLIGHT_FILENAME,
    )

    assert LINT_HARNESS_PREFLIGHT_FILENAME == "harness_preflight.md"
    assert CHECKLIST_ARTIFACT_BUDGETS["harness_preflight.md"] == (800, 1600)
    assert callable(_check_harness_preflight)
    lint_source = (
        project_root / "src" / "devolaflow" / "_workspace_lint" / "advanced_semantics.py"
    ).read_text(encoding="utf-8")
    for finding_code in (
        "HPF_FRONTMATTER",
        "HPF_SCHEMA_VERSION",
        "HPF_SECTION_ORDER",
        "HPF_GAP_REPORT",
        "HPF_AXES_CONFIG",
    ):
        assert finding_code in lint_source, f"lint.py lost HPF finding code {finding_code}"

    # ── (d) harness-flagged archive gate ──
    from devolaflow.agent_workspace.archive import (
        HARNESS_CAPABILITY_REVIEW_RELPATH,
        HARNESS_PREFLIGHT_FILENAME,
        ArchiveManager,
    )

    assert HARNESS_PREFLIGHT_FILENAME == "harness_preflight.md"
    assert HARNESS_CAPABILITY_REVIEW_RELPATH == "evidence/harness_capability_review.md"
    assert callable(ArchiveManager._guard_harness_capability_review)

    # ── (e) schema file + 27th SF-4 reference, fully wired per C-7 ──
    assert (project_root / "schemas" / "agent-workspace" / "harness-preflight.yaml").is_file()
    reference_path = (
        project_root / "workflow-system" / "agent" / "references" / "harness-construction.md"
    )
    assert reference_path.is_file()
    assert "harness-construction.md" in set(_SF4_REFERENCE_SET)
    skill_text = (project_root / "workflow-system" / "agent" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "references/harness-construction.md" in skill_text
    manifest = yaml.safe_load(
        (project_root / "workflow-system" / "agent" / "manifest.yaml").read_text(encoding="utf-8")
    )
    assert "references/harness-construction.md" in manifest["references"]
