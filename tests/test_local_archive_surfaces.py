"""Focused coverage for the registered local-archive surfaces."""

from __future__ import annotations

import subprocess
from pathlib import Path

from devolaflow.local.archive import (
    ARCHIVE_ADAPTERS,
    ArchiveApproval,
    ProtectionVerdict,
    apply_archive_plan,
    build_archive_plan,
    inspect_safety,
)


def _commit(repo: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=archive-surface-test",
            "-c",
            "user.email=archive-surface-test@example.invalid",
            "commit",
            "-qm",
            "fixture",
        ],
        cwd=repo,
        check=True,
        capture_output=True,
    )


def test_registry_contains_exactly_the_three_supported_surfaces() -> None:
    assert set(ARCHIVE_ADAPTERS) == {"tasks", "feedbacks", "research"}
    assert ARCHIVE_ADAPTERS["feedbacks"].mapping_path.endswith(
        ".local/feedbacks/archive/archive-mappings.yaml"
    )
    assert ARCHIVE_ADAPTERS["research"].index_path.endswith(".local/research/archive/INDEX.md")


def test_feedback_requires_released_version_and_resolved_tracker(tmp_path: Path) -> None:
    feedbacks = tmp_path / ".local/feedbacks"
    feedbacks.mkdir(parents=True)
    source = feedbacks / "feedback_for_v21.1.0.md"
    source.write_text("preserve this feedback\n", encoding="utf-8")
    (tmp_path / "CHANGELOG.md").write_text("## [21.1.0] - 2026-08-29\n", encoding="utf-8")
    (feedbacks / "TRACKER.md").write_text(
        "# Feedback Tracker\n\n## Resolved\n\n- `feedback_for_v21.1.0.md`\n",
        encoding="utf-8",
    )

    plan = build_archive_plan(tmp_path, surface="feedbacks")

    assert plan.entries[0].action == "move"
    assert plan.entries[0].destination == ".local/feedbacks/archive/feedback_for_v21.1.0.md"
    assert plan.entries[0].protection is ProtectionVerdict.ALLOWED

    (feedbacks / "TRACKER.md").write_text("# Feedback Tracker\n\n## Open\n", encoding="utf-8")
    refused = build_archive_plan(tmp_path, surface="feedbacks")
    assert refused.entries[0].action == "refuse"
    assert "FEEDBACK_NOT_RESOLVED" in {item.code for item in refused.entries[0].findings}


def test_research_requires_existing_cycle_archive(tmp_path: Path) -> None:
    research = tmp_path / ".local/research"
    research.mkdir(parents=True)
    source = research / "v21.1.0_retrospective.md"
    source.write_text("research bytes\n", encoding="utf-8")

    missing = build_archive_plan(tmp_path, surface="research")
    assert missing.entries[0].action == "refuse"
    assert "RESEARCH_CYCLE_ARCHIVE_MISSING" in {item.code for item in missing.entries[0].findings}

    (tmp_path / "docs/cycle-archive/v21.1.0").mkdir(parents=True)
    ready = build_archive_plan(tmp_path, surface="research")
    assert ready.entries[0].action == "move"
    assert ready.entries[0].destination == (
        ".local/research/archive/21.1.0/v21.1.0_retrospective.md"
    )


def test_surface_apply_uses_own_mapping_and_generated_index(tmp_path: Path) -> None:
    feedbacks = tmp_path / ".local/feedbacks"
    feedbacks.mkdir(parents=True)
    source = feedbacks / "feedback_for_v21.1.0.md"
    source.write_text("feedback bytes\n", encoding="utf-8")
    (tmp_path / "CHANGELOG.md").write_text("## [21.1.0] - 2026-08-29\n", encoding="utf-8")
    (feedbacks / "TRACKER.md").write_text(
        "# Feedback Tracker\n\n## Resolved\n\n- feedback_for_v21.1.0.md\n",
        encoding="utf-8",
    )
    _commit(tmp_path)

    plan = build_archive_plan(tmp_path, surface="feedbacks")
    result = apply_archive_plan(
        tmp_path, plan, ArchiveApproval(plan.fingerprint, (plan.entries[0].key,))
    )

    assert result.success
    assert not source.exists()
    assert (tmp_path / plan.entries[0].destination).read_text(encoding="utf-8") == (
        "feedback bytes\n"
    )
    assert (tmp_path / ".local/feedbacks/archive/archive-mappings.yaml").is_file()
    assert (
        (tmp_path / ".local/feedbacks/archive/INDEX.md")
        .read_text(encoding="utf-8")
        .startswith("<!-- devolaflow: generated feedback archive index -->")
    )


def test_surface_safety_rejects_symlink_and_out_of_boundary_paths(tmp_path: Path) -> None:
    source_root = tmp_path / ".local/feedbacks"
    source_root.mkdir(parents=True)
    outside = tmp_path / "outside.md"
    outside.write_text("outside\n", encoding="utf-8")
    (source_root / "feedback_for_v1.0.0.md").symlink_to(outside)

    inspection = inspect_safety(
        tmp_path,
        ".local/feedbacks/feedback_for_v1.0.0.md",
        ".local/feedbacks/archive/1.0.0/feedback_for_v1.0.0.md",
        source_boundary=".local/feedbacks",
        destination_boundary=".local/feedbacks/archive",
        requires_directory=False,
    )

    assert not inspection.safe
    assert "SYMLINK_PATH" in {item.code for item in inspection.findings}
