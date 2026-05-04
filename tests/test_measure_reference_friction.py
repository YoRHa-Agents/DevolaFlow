"""Tests for the v10.5.0 PV-04 D-D-3 reference-friction measurement script.

Pins the public contract of ``scripts/measure_reference_friction.py``
per `.local/research/v11.0.0_patches/D-D-3.md` §2.

The abbrev regex is ``\\b[A-Z]{1,}-\\d+\\b`` — captures the canonical
DevolaFlow rule-ref shape (S-9, A-6, C-4, W-18, BG-001, PV-04,
ADR-007). Per the PDS §2 example list, single-letter rule refs ARE
intended candidates for the cryptic-density heuristic (the Soul
S-1..S-10 / Architecture A-1..A-6 / Convention C-1..C-9 / Workflow
W-1..W-21 corpus is the dominant abbreviation source in the v10.x
references).

1. :func:`scan_targets` returns SKILL.md + references/*.md in
   stable order; gracefully empty on missing dirs.
2. :func:`compute_density` returns deterministic per-doc metrics.
3. :func:`find_dense_paragraphs` flags paragraphs satisfying the
   PDS heuristic (>= 100 words AND >= 5 abbreviations AND no
   embedded fenced block).
4. :func:`render_markdown_report` carries the required section
   headings + per-target table.
5. :func:`run` exits 0 on missing inputs (operator-friendly
   empty-audit on a fresh clone).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import measure_reference_friction as friction  # noqa: E402

# ── scan_targets ───────────────────────────────────────────────────────


def test_scan_targets_returns_skill_first_then_refs(tmp_path: Path) -> None:
    """SKILL.md first, then references sorted alphabetically."""
    base = tmp_path / "workflow-system" / "agent"
    refs = base / "references"
    refs.mkdir(parents=True)
    (base / "SKILL.md").write_text("# skill", encoding="utf-8")
    (refs / "zzz-late.md").write_text("# z", encoding="utf-8")
    (refs / "aaa-early.md").write_text("# a", encoding="utf-8")
    targets = friction.scan_targets(tmp_path)
    names = [t.name for t in targets]
    assert names == ["SKILL.md", "aaa-early.md", "zzz-late.md"]


def test_scan_targets_handles_missing_dirs(tmp_path: Path) -> None:
    """No `workflow-system/agent/` -> empty list (no error)."""
    assert friction.scan_targets(tmp_path) == []


# ── compute_density ────────────────────────────────────────────────────


def test_compute_density_counts_abbrev_and_ref_links() -> None:
    """Abbrev regex matches the canonical DevolaFlow rule-ref corpus.

    Inputs cover the 4 rule-letter cardinalities present in the real
    corpus: 1-letter (S-9, C-4, A-6 — Soul / Convention /
    Architecture); 2-letter (BG-001, CO-4, PV-04, SF-1); 3-letter
    (ADR-007). All are counted by the heuristic.
    """
    text = (
        "Pins BG-001, ADR-007, S-9, and CO-4. See references/agent-workspace.md.\n"
        "PV-04 ships D-D-3. SF-1 applies. C-4 line budgets.\n"
        "```\nfenced\n```\n"
    )
    d = friction.compute_density(text)
    # BG-001, ADR-007, S-9, CO-4, PV-04, D-3 (from D-D-3), SF-1, C-4 = 8.
    assert d["abbrev_count"] == 8
    assert d["ref_link_count"] == 1  # references/agent-workspace.md
    assert d["fenced_blocks"] == 1
    assert d["line_count"] > 0
    assert d["word_count"] > 0
    assert d["abbrev_per_100_lines"] > 0
    assert d["fenced_blocks_per_100_lines"] > 0


def test_compute_density_empty_text_returns_zeros() -> None:
    """Empty text -> all zero metrics, no division-by-zero."""
    d = friction.compute_density("")
    assert d["line_count"] == 0
    assert d["word_count"] == 0
    assert d["abbrev_count"] == 0
    assert d["ref_link_count"] == 0
    assert d["fenced_blocks"] == 0
    assert d["abbrev_per_100_lines"] == 0.0
    assert d["avg_line_length"] == 0.0


# ── find_dense_paragraphs ─────────────────────────────────────────────


def test_find_dense_paragraphs_detects_high_abbrev_para() -> None:
    """Paragraph with > 100 words AND > 5 abbreviations matches."""
    para = "This paragraph pins S-9 S-10 S-8 C-4 A-6 W-18 contracts " + "word " * 110 + "."
    candidates = friction.find_dense_paragraphs(para, source_path="x.md")
    assert len(candidates) == 1
    c = candidates[0]
    assert c["source_path"] == "x.md"
    assert c["word_count"] >= friction.DENSITY_PARA_MIN_WORDS
    assert c["abbrev_count"] >= friction.DENSITY_PARA_MIN_ABBREVS


def test_find_dense_paragraphs_skips_short_paragraphs() -> None:
    """Paragraphs below min_words are not candidates."""
    text = "Short S-9 mention only. Another S-10 line."
    assert friction.find_dense_paragraphs(text, source_path="x.md") == []


def test_find_dense_paragraphs_skips_fenced_content() -> None:
    """Paragraphs inside fenced blocks are excluded (they ARE examples)."""
    text = "```\n" + "abbrev S-9 S-10 S-8 C-4 A-6 W-18 " + "word " * 150 + "\n```"
    assert friction.find_dense_paragraphs(text, source_path="x.md") == []


# ── render_markdown_report ────────────────────────────────────────────


def test_render_markdown_report_contains_required_sections() -> None:
    """Output carries Summary + Per-Target Density + Worst-N + Recommendation."""
    per_target = {
        "workflow-system/agent/SKILL.md": friction.compute_density(
            "S-9 PV-04 some text and another line."
        ),
    }
    md = friction.render_markdown_report(per_target, [])
    assert "# v10.5.0 PV-04 D-D-3 Reference Friction Measurement" in md
    assert "## Summary" in md
    assert "## Per-Target Density" in md
    assert "## Worst-N Compressed-and-Cryptic Candidates" in md
    assert "## Recommendation" in md
    assert "SKILL.md" in md


# ── run smoke ──────────────────────────────────────────────────────────


def test_run_emits_markdown_to_output_fresh_clone(tmp_path: Path) -> None:
    """``run`` on a fresh tree (no workflow-system/) exits 0 with empty report."""
    out = tmp_path / "r.md"
    rc = friction.run(tmp_path, output=out)
    assert rc == 0
    text = out.read_text(encoding="utf-8")
    assert "# v10.5.0 PV-04 D-D-3 Reference Friction Measurement" in text


def test_run_emits_json_with_per_target(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """``--json`` path returns parseable JSON with `per_target` key."""
    base = tmp_path / "workflow-system" / "agent"
    base.mkdir(parents=True)
    (base / "SKILL.md").write_text("# skill\npins S-9 and C-4.\n", encoding="utf-8")
    rc = friction.run(tmp_path, json_out=True)
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert "per_target" in payload
    assert "dense_paragraphs" in payload
