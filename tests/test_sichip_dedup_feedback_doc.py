"""Tests for the v10.2.1 PV-02 DEFER feedback-doc dedupe surface (D-S-5).

Pins the contract in
:func:`devolaflow.lifecycle.post_skill_edit._write_feedback_doc`:

1. **First DEFER doc writes normally** — when no prior fingerprint exists,
   a new dated `sichip_deferred_<timestamp>.md` file is created.
2. **Duplicate inputs skip the write** — a second invocation with identical
   ``(skill_files, verdict, notes)`` does NOT create a new file; the helper
   returns the prior path instead.
3. **Different inputs write a fresh doc** — when ``notes`` differ (or
   ``skill_files`` differ, or ``verdict`` differs), a new doc is created
   even though some inputs overlap with a prior write.

Closes D-S-5 from `.local/research/v10.2.0_gap_analysis.md` §3.2: with
DEEP integration always-on (`DEVOLAFLOW_SI_CHIP_DEEP=1`), every
skill-corpus commit produced a NEW feedback doc — `.local/feedbacks/`
filled with low-information DEFER timestamps. This dedupe collapses
duplicate writes idempotently.

Source: `.local/research/v10.2.0_cycle_plan.md` §3 PV-02 owned-files
manifest.
External tool reference: https://github.com/YoRHa-Agents/Si-Chip
"""

from __future__ import annotations

from pathlib import Path

from devolaflow.lifecycle.post_skill_edit import (
    FINGERPRINT_SIDECAR_NAME,
    _compute_defer_fingerprint,
    _write_feedback_doc,
)


def _list_defer_docs(feedback_dir: Path) -> list[Path]:
    """Enumerate all sichip_deferred_*.md files in the feedback dir."""
    return sorted(feedback_dir.glob("sichip_deferred_*.md"))


def test_first_defer_doc_writes_normally(tmp_path: Path) -> None:
    """The initial DEFER write creates a fresh dated doc + sidecar entry."""
    feedback_dir = tmp_path / "feedbacks"
    skill_files = ["workflow-system/agent/SKILL.md"]
    notes = ["profile: ability='devola-flow' meta_tokens=229 body_tokens=7088"]

    out_path = _write_feedback_doc(
        feedback_dir=feedback_dir,
        skill_files=skill_files,
        notes=notes,
        install_source="cursor_global",
        verdict="DEFER",
    )

    assert out_path.is_file(), "First DEFER write must create the doc on disk"
    assert out_path.parent == feedback_dir
    assert out_path.name.startswith("sichip_deferred_")
    assert out_path.suffix == ".md"

    # Sidecar contains exactly one fingerprint line.
    sidecar = feedback_dir / FINGERPRINT_SIDECAR_NAME
    assert sidecar.is_file(), "Sidecar fingerprint file must be authored on first write"
    sidecar_lines = [
        line for line in sidecar.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    assert len(sidecar_lines) == 1, (
        f"Sidecar must contain exactly 1 fingerprint after first write; got {sidecar_lines!r}"
    )

    # Doc body contains the embedded fingerprint marker for downstream lookup.
    doc_text = out_path.read_text(encoding="utf-8")
    fingerprint = _compute_defer_fingerprint(skill_files, notes, "DEFER")
    assert f"<!-- sichip_fingerprint:{fingerprint} -->" in doc_text


def test_duplicate_defer_doc_is_skipped(tmp_path: Path) -> None:
    """Two writes with identical inputs produce ONE doc on disk.

    The second invocation must:
      a) NOT create a new file (directory still has 1 doc).
      b) Return the SAME path as the first call.
      c) Leave the sidecar at exactly 1 fingerprint entry (no duplicates).
    """
    feedback_dir = tmp_path / "feedbacks"
    skill_files = ["workflow-system/agent/SKILL.md"]
    notes = ["evaluate: skipped — runs_dir/baseline_dir not supplied"]

    first_path = _write_feedback_doc(
        feedback_dir=feedback_dir,
        skill_files=skill_files,
        notes=notes,
        install_source="cursor_global",
        verdict="DEFER",
    )
    second_path = _write_feedback_doc(
        feedback_dir=feedback_dir,
        skill_files=skill_files,
        notes=notes,
        install_source="cursor_global",
        verdict="DEFER",
    )

    docs = _list_defer_docs(feedback_dir)
    assert len(docs) == 1, (
        f"D-S-5 violation: duplicate write produced a NEW doc; expected 1 "
        f"on disk, got {len(docs)}: {[p.name for p in docs]!r}"
    )
    assert second_path == first_path, (
        f"D-S-5 contract: duplicate write must return the prior doc path; "
        f"got first={first_path!r} second={second_path!r}"
    )

    # Sidecar still has exactly one entry — set semantics, no duplicate appends.
    sidecar = feedback_dir / FINGERPRINT_SIDECAR_NAME
    sidecar_lines = [
        line for line in sidecar.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    assert len(sidecar_lines) == 1, (
        f"Sidecar must remain at 1 fingerprint after duplicate skip; "
        f"got {sidecar_lines!r} (set semantics violated)"
    )


def test_different_notes_writes_new_doc(tmp_path: Path) -> None:
    """Same skill_files + verdict but different notes → 2 distinct docs."""
    feedback_dir = tmp_path / "feedbacks"
    skill_files = ["workflow-system/agent/SKILL.md"]

    first_path = _write_feedback_doc(
        feedback_dir=feedback_dir,
        skill_files=skill_files,
        notes=["evaluate: skipped — runs_dir not supplied"],
        install_source="cursor_global",
        verdict="DEFER",
    )
    second_path = _write_feedback_doc(
        feedback_dir=feedback_dir,
        skill_files=skill_files,
        notes=["iteration_delta=+0.05 vs threshold +0.10 → DEFER"],
        install_source="cursor_global",
        verdict="DEFER",
    )

    docs = _list_defer_docs(feedback_dir)
    assert len(docs) == 2, (
        f"Different notes must produce a fresh doc; expected 2, got "
        f"{len(docs)}: {[p.name for p in docs]!r}"
    )
    assert first_path != second_path

    # Sidecar accumulates 2 distinct fingerprints.
    sidecar = feedback_dir / FINGERPRINT_SIDECAR_NAME
    sidecar_lines = [
        line for line in sidecar.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    assert len(sidecar_lines) == 2, (
        f"Sidecar must record 2 distinct fingerprints; got {sidecar_lines!r}"
    )
    assert len(set(sidecar_lines)) == 2, (
        f"Sidecar must NOT contain duplicate fingerprints; got {sidecar_lines!r}"
    )


def test_different_skill_files_writes_new_doc(tmp_path: Path) -> None:
    """Different skill_files (same notes + verdict) → 2 distinct docs."""
    feedback_dir = tmp_path / "feedbacks"
    notes = ["evaluate: skipped — runs_dir not supplied"]

    first_path = _write_feedback_doc(
        feedback_dir=feedback_dir,
        skill_files=["workflow-system/agent/SKILL.md"],
        notes=notes,
        install_source="cursor_global",
        verdict="DEFER",
    )
    second_path = _write_feedback_doc(
        feedback_dir=feedback_dir,
        skill_files=["workflow-system/agent/references/env-flags.md"],
        notes=notes,
        install_source="cursor_global",
        verdict="DEFER",
    )

    docs = _list_defer_docs(feedback_dir)
    assert len(docs) == 2
    assert first_path != second_path


def test_fingerprint_is_order_invariant_across_skill_files(tmp_path: Path) -> None:
    """``[a.md, b.md]`` and ``[b.md, a.md]`` produce the SAME fingerprint.

    Documents the sort-before-hash convention in
    :func:`_compute_defer_fingerprint`. Two callers passing the same set
    of files in different orderings must NOT cause a spurious second
    write — that would defeat the dedup.
    """
    feedback_dir = tmp_path / "feedbacks"
    notes = ["evaluate: skipped"]

    first_path = _write_feedback_doc(
        feedback_dir=feedback_dir,
        skill_files=["workflow-system/agent/SKILL.md", "workflow-system/agent/CLAUDE.md"],
        notes=notes,
        install_source="cursor_global",
        verdict="DEFER",
    )
    second_path = _write_feedback_doc(
        feedback_dir=feedback_dir,
        skill_files=["workflow-system/agent/CLAUDE.md", "workflow-system/agent/SKILL.md"],
        notes=notes,
        install_source="cursor_global",
        verdict="DEFER",
    )

    docs = _list_defer_docs(feedback_dir)
    assert len(docs) == 1, (
        f"Order-invariant fingerprint failed: reordered skill_files produced "
        f"a new doc instead of returning the prior path. Got "
        f"{[p.name for p in docs]!r}"
    )
    assert second_path == first_path
