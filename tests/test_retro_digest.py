"""Focused contracts for the report-only Retro-Digest runtime."""

from __future__ import annotations

from pathlib import Path

import pytest

from devolaflow.skills import (
    DigestCuration,
    DigestRecord,
    build_digest,
    classify_retro_digest_intent,
    discover_retrospectives,
    extract_evaluation_findings,
    extract_retrospective_records,
    recent_cycles,
    render_digest_report,
    to_learning_entries,
)


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("Please create a RETRO DIGEST", "DIGEST_REQUESTED"),
        ("Digest the retrospectives and keep the source text", "DIGEST_REQUESTED"),
        ("What did we learn from this cycle?", "DIGEST_SUGGESTED"),
        ("Review this retrospective", "DIGEST_SUGGESTED"),
        ("Implement the endpoint", "NO_DIGEST"),
        ("", "NO_DIGEST"),
        ("  \n", "NO_DIGEST"),
    ],
)
def test_classify_retro_digest_intent(message: str, expected: str) -> None:
    assert classify_retro_digest_intent(message) == expected


def test_requested_digest_intent_precedes_suggested() -> None:
    assert (
        classify_retro_digest_intent("Digest the retrospectives and review this retrospective")
        == "DIGEST_REQUESTED"
    )


@pytest.mark.parametrize(
    ("heading", "body"),
    [
        ("## 4. Key learnings", "- Exact English lesson\n- Second lesson"),
        ("## 4. 关键学习", "- 精确的中文学习\n- 第二条"),
    ],
)
def test_extracts_bilingual_lessons_verbatim(heading: str, body: str) -> None:
    records = extract_retrospective_records(
        f"# Cycle\n\n{heading}\n{body}\n\n## Next section\n- ignored",
        source_path=".local/research/v1.2.0_retrospective.md",
    )
    assert [record.text for record in records] == body[2:].split("\n- ")
    assert records[0].source_path == ".local/research/v1.2.0_retrospective.md"
    assert records[0].source_span == (3, 3)
    assert records[0].record_id.endswith("#L3")


def test_extracts_evaluation_findings_and_numeric_evidence() -> None:
    markdown = """# Evaluation

### A.4 Findings Closure
- W-17 observation is `64`
| score | value |
|---|---:|
| test adequacy | 6.67 |

## Part B
- ignored
"""
    records = extract_evaluation_findings(
        markdown,
        source_path="docs/cycle-archive/v20.0.0/evaluation/v20.0.0_evaluation.md",
    )
    assert [record.text for record in records] == [
        "W-17 observation is `64`",
        "| score | value |",
        "| test adequacy | 6.67 |",
    ]
    assert all(record.category == "benefit" for record in records)


def test_discovery_deduplicates_current_research_and_orders_paths(tmp_path: Path) -> None:
    current = tmp_path / ".local" / "research"
    archived = tmp_path / "docs" / "cycle-archive" / "v1.0.0"
    (current).mkdir(parents=True)
    archived.mkdir(parents=True)
    (current / "v2.0.0_retrospective.md").write_text("## Key learnings\n- current")
    duplicate = tmp_path / "docs" / "cycle-archive" / "v2.0.0"
    duplicate.mkdir(parents=True)
    (duplicate / "v2.0.0_retrospective.md").write_text("## Key learnings\n- archived")
    (archived / "v1.0.0_retrospective.md").write_text("## Key learnings\n- old")

    sources = discover_retrospectives(tmp_path)

    assert [source.path for source in sources] == [
        ".local/research/v2.0.0_retrospective.md",
        "docs/cycle-archive/v1.0.0/v1.0.0_retrospective.md",
    ]
    assert [source.cycle for source in sources] == ["v2.0.0", "v1.0.0"]


def test_build_digest_has_explicit_empty_status_and_missing_root_error(tmp_path: Path) -> None:
    empty = build_digest(tmp_path)
    assert empty.status == "INSUFFICIENT"
    assert empty.lessons == ()
    with pytest.raises(FileNotFoundError):
        build_digest(tmp_path / "missing")


def test_learning_fields_and_curation_do_not_mutate_base_records() -> None:
    records = (
        DigestRecord(
            record_id=".local/research/v1.0.0_retrospective.md#L2",
            cycle="v1.0.0",
            category="lesson",
            text="Preserve this exact lesson: 91.0%",
            source_path=".local/research/v1.0.0_retrospective.md",
            start_line=2,
            end_line=2,
            source_kind="retrospective",
            section="Key learnings",
            raw_text="- Preserve this exact lesson: 91.0%",
        ),
        DigestRecord(
            record_id=".local/research/v1.0.0_retrospective.md#L3",
            cycle="v1.0.0",
            category="benefit",
            text="coverage_pct: 91.0",
            source_path=".local/research/v1.0.0_retrospective.md",
            start_line=3,
            end_line=3,
            source_kind="evaluation",
            section="Findings",
        ),
    )
    original = records[0]
    entries = to_learning_entries(records, DigestCuration.select([original.record_id]))

    assert records[0] == original
    assert len(entries) == 1
    assert entries[0].key == "v1.0.0:preserve-this-exact-lesson-91-0"
    assert entries[0].insight == original.text
    assert entries[0].stage == "retro-digest"
    assert entries[0].task_type == "retro-digest"
    assert entries[0].confidence == 0.9
    assert entries[0].confidence_half_life_days == 30
    assert entries[0].ttl_days == 90
    assert entries[0].source == "retro-digest-curated"
    assert entries[0].files == [original.source_path]
    assert entries[0].source_task_id == original.record_id


def test_report_is_deterministic_and_separates_lessons_from_benefits() -> None:
    digest = build_digest(Path("."))
    first = render_digest_report(digest)
    second = render_digest_report(digest)

    assert first == second
    assert "## Lessons" in first
    assert "## Benefits" in first
    assert "coverage_pct: 91.0" not in "\n".join(
        entry.insight for entry in to_learning_entries(digest)
    )


@pytest.mark.parametrize(
    "markdown",
    [
        "",
        "# No supported section\n- not extracted",
        "## Key learnings\n",
    ],
)
def test_missing_or_malformed_sections_are_empty(markdown: str) -> None:
    assert extract_retrospective_records(markdown, source_path="sample.md") == ()
    assert extract_evaluation_findings(markdown, source_path="sample_evaluation.md") == ()


# --------------------------------------------------------------------------
# v24.1.0 — the digest was silently skipping the newest cycles
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "heading",
    [
        "## Key learnings",
        "## Learning",
        "## Learnings",
        "## 4. What we learned",
        "## Lessons learned",
    ],
)
def test_lesson_sections_are_recognised_across_real_heading_phrasings(heading: str) -> None:
    """v24 matched only "key learnings", so newer retrospectives contributed nothing.

    `## Learning` (v23.1.0) and `## 4. What we learned` (v24.0.0) were both
    skipped while the digest still reported OK — the two most recent cycles
    were exactly the ones dropped.
    """
    markdown = f"{heading}\n\n- one durable lesson\n"
    records = extract_retrospective_records(markdown, source_path="r.md", cycle="v1.0.0")
    assert [record.text for record in records] == ["one durable lesson"]


def test_bold_lead_paragraphs_are_extracted_verbatim() -> None:
    """A lesson too long for a bullet is written as a bold-lead paragraph.

    v24.0.0 wrote its entire learnings section that way and the extractor,
    which recognised only bullets and table rows, returned nothing from it.
    """
    markdown = (
        "## What we learned\n"
        "\n"
        "**The obvious metric was the wrong one.** Splitting one blob into\n"
        "per-risk files adds structure, so the stored total grows.\n"
        "\n"
        "**Compaction has a fixed cost.** It only pays above a threshold.\n"
    )
    records = extract_retrospective_records(markdown, source_path="r.md", cycle="v24.0.0")

    assert len(records) == 2
    first = records[0]
    assert first.text == (
        "**The obvious metric was the wrong one.** Splitting one blob into "
        "per-risk files adds structure, so the stored total grows."
    ), "W-29 requires the passage verbatim; the paragraph must not be truncated to its lede"
    assert first.end_line > first.start_line, "a multi-line passage must span its real lines"
    assert records[1].text.startswith("**Compaction has a fixed cost.**")


def test_emphasis_inside_prose_is_not_mistaken_for_a_lede(tmp_path: Path) -> None:
    """A lede is a deliberate opening claim; emphasised prose is ordinary prose.

    v24.3.0: the distinction is no longer visible in whether a record appears —
    prose in a learnings section is now read — so it is checked where it still
    matters. Alongside a bullet, a lede is a peer record and plain prose is not.
    """
    markdown = (
        "## Learnings\n\nThis paragraph merely **emphasises** a word.\n\n- an unambiguous bullet\n"
    )

    records = extract_retrospective_records(markdown, source_path="r.md", cycle="v1.0.0")

    assert [record.text for record in records] == ["an unambiguous bullet"]


def test_a_discovered_source_that_yields_nothing_is_reported_not_hidden(tmp_path: Path) -> None:
    """Aggregate OK over hundreds of records hid that the newest source gave zero.

    W-29: missing evidence is INSUFFICIENT, never PASS. A source the extractor
    did not understand is a different problem from an empty file, and the
    caller needs the list to tell them apart.
    """
    research = tmp_path / ".local" / "research"
    research.mkdir(parents=True)
    (research / "v1.0.0_retrospective.md").write_text(
        "## Key learnings\n\n- a recognised lesson\n", encoding="utf-8"
    )
    (research / "v2.0.0_retrospective.md").write_text(
        "## Postmortem Notes\n\n- an unrecognised section\n", encoding="utf-8"
    )

    result = build_digest(tmp_path)

    assert result.status == "OK"
    assert result.silent_sources == (".local/research/v2.0.0_retrospective.md",)
    assert "unrecognised, not empty" in result.reason


def test_no_silent_sources_leaves_the_reason_empty(tmp_path: Path) -> None:
    """The warning must not fire when every discovered source contributed."""
    research = tmp_path / ".local" / "research"
    research.mkdir(parents=True)
    (research / "v1.0.0_retrospective.md").write_text(
        "## Key learnings\n\n- a recognised lesson\n", encoding="utf-8"
    )

    result = build_digest(tmp_path)

    assert result.silent_sources == ()
    assert result.reason == ""


# --------------------------------------------------------------------------
# v24.3.0 — silence had two causes and only one of them is a defect
# --------------------------------------------------------------------------


def test_a_learnings_section_written_as_prose_is_read(tmp_path: Path) -> None:
    """Four cycles state their learnings in paragraphs and were read as zero.

    v18.0.0, v21.0.0, v22.0.0, and v23.1.0 each write an unadorned prose
    section. The extractor recognised the heading, found no bullet, and
    returned nothing while the digest still reported OK.
    """
    markdown = (
        "## Learning\n\n"
        "Transport artifact hashes must not define measurement identity when\n"
        "an ingestion path rewrites the artifact.\n\n"
        "Missing provider evidence must remain explicit through archival.\n"
    )

    records = extract_retrospective_records(markdown, source_path="r.md", cycle="v23.1.0")

    assert len(records) == 2
    assert records[0].text.startswith("Transport artifact hashes")
    assert records[0].text.endswith("rewrites the artifact.")
    assert records[1].text == "Missing provider evidence must remain explicit through archival."


def test_prose_does_not_compete_with_the_bullets_beside_it(tmp_path: Path) -> None:
    """The fallback is per section, so a working section is left exactly as it was."""
    markdown = "## Key learnings\n\nHere is what we found:\n\n- the actual lesson\n"

    records = extract_retrospective_records(markdown, source_path="r.md", cycle="v1.0.0")

    assert [record.text for record in records] == ["the actual lesson"]


def test_a_heading_that_delivers_nothing_forces_insufficient(tmp_path: Path) -> None:
    """W-29: promised evidence that does not arrive is INSUFFICIENT, never PASS.

    Distinct from an absent heading, which may legitimately mean the file has
    no learnings. Only the unmet promise downgrades the whole digest, and it
    does so even with a hundred good records beside it.
    """
    research = tmp_path / ".local" / "research"
    research.mkdir(parents=True)
    (research / "v1.0.0_retrospective.md").write_text(
        "## Key learnings\n\n- a recognised lesson\n", encoding="utf-8"
    )
    (research / "v2.0.0_retrospective.md").write_text(
        "## Key learnings\n\n\n## Next steps\n\n- unrelated\n", encoding="utf-8"
    )

    result = build_digest(tmp_path)

    assert result.unparsed_sources == (".local/research/v2.0.0_retrospective.md",)
    assert result.status == "INSUFFICIENT"
    assert "could not read" in result.reason
    assert result.lessons, "the downgrade reports the gap; it does not discard the evidence"


def test_an_absent_section_is_reported_without_being_called_a_defect(tmp_path: Path) -> None:
    """Two kinds of silence, and conflating them was the v24.1.0 wording gap."""
    research = tmp_path / ".local" / "research"
    research.mkdir(parents=True)
    (research / "v1.0.0_retrospective.md").write_text(
        "## Key learnings\n\n- a recognised lesson\n", encoding="utf-8"
    )
    (research / "v2.0.0_retrospective.md").write_text(
        "## Postmortem Notes\n\n- an unrecognised section\n", encoding="utf-8"
    )

    result = build_digest(tmp_path)

    assert result.silent_sources == (".local/research/v2.0.0_retrospective.md",)
    assert result.unparsed_sources == ()
    assert result.status == "OK"


def test_this_repository_has_no_unparsed_source() -> None:
    """The closing condition for C-G3.3, measured against the real corpus."""
    result = build_digest(Path("."))

    assert result.unparsed_sources == (), "\n".join(result.unparsed_sources)


def test_persistence_takes_the_current_and_previous_cycle_only(tmp_path: Path) -> None:
    """Twenty cycles of conclusions must not all become live operational guidance."""
    records = tuple(
        DigestRecord(
            record_id=f"r{index}",
            cycle=cycle,
            category="lesson",
            text=f"lesson from {cycle}",
            source_path=f"{cycle}.md",
            start_line=1,
            end_line=1,
            source_kind="retrospective",
            section="Key learnings",
        )
        for index, cycle in enumerate(("v9.5.0", "v23.1.0", "v24.1.0", "v24.2.0"))
    )

    persisted = {entry.insight for entry in to_learning_entries(records)}

    assert persisted == {"lesson from v24.1.0", "lesson from v24.2.0"}


def test_cycles_are_ordered_by_number_not_by_string() -> None:
    """`v9.5.0` sorts below `v24.0.0`; a string comparison puts it on top."""
    records = tuple(
        DigestRecord(
            record_id=f"r{index}",
            cycle=cycle,
            category="lesson",
            text="x",
            source_path="s.md",
            start_line=1,
            end_line=1,
            source_kind="retrospective",
            section="Key learnings",
        )
        for index, cycle in enumerate(("v9.5.0", "v24.0.0", "v3.0.0"))
    )

    assert recent_cycles(records) == ("v24.0.0", "v9.5.0")


def test_history_stays_in_the_report_it_is_excluded_from_the_ledger() -> None:
    """Not backfilled is not hidden: the report keeps every cycle it found."""
    digest = build_digest(Path("."))

    report = render_digest_report(digest)
    persisted_cycles = {entry.key.split(":", 1)[0] for entry in to_learning_entries(digest)}

    assert len(persisted_cycles) <= 2
    older = {record.cycle for record in digest.lessons} - persisted_cycles
    assert older, "the repository has more than two cycles of retrospectives"
    assert any(f"[{cycle}]" in report for cycle in older)
