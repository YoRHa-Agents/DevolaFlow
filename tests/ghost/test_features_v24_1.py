"""Ghost audit for v24.1.0 self-digest improvements (W-18).

Every symbol named in the v24.1.0 CHANGELOG entry must resolve to real,
reachable code here before that entry may land (S-4, sharpened by W-18 into a
sequencing requirement). These are existence-and-contract checks; the
behaviour lives in `tests/test_handoff_envelope_immutable.py`,
`tests/test_workspace_compact.py`, `tests/harness/test_aggregator.py`, and
`tests/test_retro_digest.py`.
"""

from __future__ import annotations

from pathlib import Path


def test_s9_amendment_is_present_in_the_compiled_rule_corpus(project_root: Path) -> None:
    """The amendment is only real once it survives `make compile-rules`."""

    source = (project_root / ".rules" / "soul.mdc").read_text(encoding="utf-8")
    compiled = (project_root / "AGENTS.md").read_text(encoding="utf-8")
    for text in (source, compiled):
        assert "S-9.1 — Tool-Mediated Relocation of Archived-Change Envelopes" in text
        assert "Envelopes belonging to an active change MUST NOT be relocated" in text


def test_soul_set_count_is_unchanged_by_the_amendment(project_root: Path) -> None:
    """W-21: S-9.1 narrows an existing invariant; it does not add an eleventh."""

    source = (project_root / ".rules" / "soul.mdc").read_text(encoding="utf-8")
    headings = [line for line in source.splitlines() if line.startswith("## S-")]
    assert len(headings) == 10, headings


def test_handoff_relocation_surface_exists() -> None:
    from devolaflow.workspace_compact import handoff_relocate

    for symbol in (
        "plan_relocation",
        "apply_relocation",
        "verify_relocations",
        "archived_change_ids",
        "RelocationPlan",
        "RelocationResult",
    ):
        assert hasattr(handoff_relocate, symbol), f"handoff_relocate.{symbol} is missing"


def test_relocation_hook_names_the_only_sanctioned_mover() -> None:
    """S-9.1 condition 2 is enforced against a named module, not a role."""

    from devolaflow.lifecycle.check_envelope_append_only import RELOCATION_TOOL

    assert RELOCATION_TOOL == "devolaflow.workspace_compact.handoff_relocate"


def test_compact_plan_reports_net_benefit_and_include_candidates() -> None:
    from devolaflow.workspace_compact.models import CompactPlan

    for name in ("digest_tokens", "net_tokens", "pays_for_itself", "candidates"):
        assert isinstance(getattr(CompactPlan, name), property), f"CompactPlan.{name} is missing"


def test_digest_can_be_rendered_without_an_on_disk_ledger() -> None:
    """Pricing a plan's digest requires rendering rows that do not exist yet."""

    from devolaflow.workspace_compact.digest import estimate_digest_tokens, render_digest_rows

    assert callable(render_digest_rows)
    assert estimate_digest_tokens(()) > 0


def test_ledger_reader_supports_row_level_quarantine() -> None:
    """F-00's class fix: one bad row costs one record, not the whole ledger."""

    import inspect

    from devolaflow.harness.aggregator import QuarantinedRow, load_ledger_records

    assert "quarantine" in inspect.signature(load_ledger_records).parameters
    for field_name in ("path", "line", "reason"):
        assert field_name in QuarantinedRow.__dataclass_fields__


def test_retro_digest_reports_sources_that_contributed_nothing() -> None:
    """W-29: a discovered source yielding zero records must be named, not hidden."""

    from devolaflow.skills.retro_digest import DigestResult

    assert "silent_sources" in DigestResult.__dataclass_fields__


def test_retro_digest_recognises_the_lesson_headings_this_repo_actually_writes() -> None:
    from devolaflow.skills.retro_digest import extract_retrospective_records

    for heading in ("## Key learnings", "## Learning", "## 4. What we learned"):
        records = extract_retrospective_records(f"{heading}\n\n- a lesson\n", source_path="r.md")
        assert records, f"heading {heading!r} yields no records"
