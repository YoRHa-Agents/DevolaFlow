"""Tests for the v10.5.0 PV-01 D-A-1 layer usage audit script.

Pins the public contract of ``scripts/audit_layer_usage.py`` per
`.local/research/v11.0.0_patches/D-A-1.md` §2:

1. :func:`scan_cycle_docs` matches the documented v9.x + v10.x
   cycle-plan + retrospective globs and ignores unrelated files.
2. :func:`extract_layer_signals` returns deterministic counts for
   the L0/L1/L2/L3 mention regex AND the more precise
   ``Dispatch type:`` lines.
3. :func:`compute_layer_ratios` produces sensible aggregate ratios
   given a known-good fixture; gracefully returns 0.0 ratios when
   no dispatch lines exist.
4. :func:`render_markdown_report` produces output containing the
   required summary headings.
5. :func:`run` exits 0 even when ``.local/research/`` does not
   exist (operator-friendly empty-audit on fresh clones).

Each test runs in O(1) — pure-function inputs, no filesystem
state outside ``tmp_path`` fixtures.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Make ``scripts/`` importable.
_SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import audit_layer_usage as audit_layer  # noqa: E402

# ── extract_layer_signals ──────────────────────────────────────────────


def test_extract_layer_signals_counts_layer_mentions() -> None:
    """``\\bL{n}\\b`` regex captures plain ``L0/L1/L2/L3`` tokens."""
    text = """
    L0 plans the cycle. L1 Stage owns one stage; L2 Wave dispatches.
    L3 Task is the only one that does work. Refer back to L0 again.
    """
    signals = audit_layer.extract_layer_signals(text)
    assert signals["L0"] == 2
    assert signals["L1"] == 1
    assert signals["L2"] == 1
    assert signals["L3"] == 1


def test_extract_layer_signals_dispatch_type_lines() -> None:
    """``Dispatch type:`` lines are the precise signal."""
    text = """
    PV-01 plan:
      Dispatch type: Wave
    PV-02 plan:
      Dispatch type: Stage
    PV-03 plan:
      Dispatch type: Task
    PV-04 plan:
      Dispatch type: Wave
    """
    signals = audit_layer.extract_layer_signals(text)
    assert signals["dispatch_wave"] == 2
    assert signals["dispatch_stage"] == 1
    assert signals["dispatch_task"] == 1


# ── v11.1.2 D-2 regex bold-markdown coverage ──────────────────────────


def test_dispatch_type_regex_matches_plain_style() -> None:
    """Negative-control: plain ``Dispatch type:`` style still matches.

    Pins the v10.5.0 legacy contract — the broadened regex must not
    regress plain-text matching (W-20 backward-compat). Same fixture
    as ``test_extract_layer_signals_dispatch_type_lines`` but asserted
    via the public regex object directly so the test fails fast on
    any regex-source drift, not just the count side-effect.
    """
    text = "Dispatch type: Wave\nDispatch type: Stage\nDispatch type: Task\n"
    matches = audit_layer._DISPATCH_TYPE_RE.findall(text)
    assert matches == ["Wave", "Stage", "Task"]


def test_dispatch_type_regex_matches_bold_markdown_style() -> None:
    """v11.1.2 D-2 fix: ``**Dispatch type:** Wave`` markdown-bold style matches.

    Closes the PV-05 N-2 finding documented at
    ``docs/cycle-archive/v11.1.0/retrospective.md`` §3 D-4: the legacy
    v10.5.0 regex did NOT match v11.x cycle docs that use the
    markdown-bold convention `**Dispatch type:** Wave`. As a result
    `cascade_ratio` reported `0` for all v11.x cycle docs (undermining
    the audit's signal value). The v11.1.2 regex broadening uses
    `\\*{0,2}` quantifiers around the label and value to admit 0/1/2
    asterisks uniformly.
    """
    text = "**Dispatch type:** Wave\n**Dispatch type:** Stage\n**Dispatch type:** Task\n"
    matches = audit_layer._DISPATCH_TYPE_RE.findall(text)
    assert matches == ["Wave", "Stage", "Task"]


def test_dispatch_type_regex_matches_bold_value_only() -> None:
    """Defensive: ``Dispatch type: **Wave**`` (bold on value only) matches.

    Some authors emphasise the layer name without bolding the label;
    the broadened regex MUST handle this asymmetric case so partial
    bold conventions don't silently drop from the cascade signal.
    """
    text = "Dispatch type: **Wave**\nDispatch type: **Stage**\nDispatch type: **Task**\n"
    matches = audit_layer._DISPATCH_TYPE_RE.findall(text)
    assert matches == ["Wave", "Stage", "Task"]


def test_dispatch_type_regex_matches_full_bold() -> None:
    """Defensive: ``**Dispatch type:** **Wave**`` (bold on label AND value) matches.

    The full-bold case has TWO adjacent asterisk runs between ``:`` and
    the value — closing-label ``**`` + space + opening-value ``**`` —
    which is why the broadened regex carries a dual ``\\*{0,2}\\s*\\*{0,2}``
    slot. Without the second slot the regex drops the value asterisks
    onto the value group itself and the alternation fails. This test
    pins the dual-slot design and the resulting capture remains the
    bare layer name (``Wave`` / ``Stage`` / ``Task``).
    """
    text = (
        "**Dispatch type:** **Wave**\n**Dispatch type:** **Stage**\n**Dispatch type:** **Task**\n"
    )
    matches = audit_layer._DISPATCH_TYPE_RE.findall(text)
    assert matches == ["Wave", "Stage", "Task"]


def test_extract_layer_signals_collapse_markers() -> None:
    """Collapse markers (L0->L3 / SHORTCUT_SIMPLE / Single-Task shortcut) count."""
    text = (
        "Per PV-06 the SHORTCUT_SIMPLE verdict ships;\n"
        "see also the L0 -> L3 collapse pattern.\n"
        "Single-Task shortcut applies for trivial-tier tasks.\n"
    )
    signals = audit_layer.extract_layer_signals(text)
    assert signals["collapse_l0_l3"] >= 3


def test_extract_layer_signals_ignores_unrelated_text() -> None:
    """Text without any of the patterns yields zero counts."""
    signals = audit_layer.extract_layer_signals("plain prose; no agent layer mentioned at all.")
    for key in ("L0", "L1", "L2", "L3"):
        assert signals[key] == 0
    assert signals["dispatch_wave"] == 0
    assert signals["dispatch_stage"] == 0
    assert signals["dispatch_task"] == 0
    assert signals["collapse_l0_l3"] == 0


# ── compute_layer_ratios ───────────────────────────────────────────────


def test_compute_layer_ratios_zero_dispatch_returns_zeros() -> None:
    """No dispatch lines -> all ratios 0.0 (no division-by-zero)."""
    per_doc: dict[str, dict[str, int]] = {
        "a": {
            "L0": 1,
            "L1": 0,
            "L2": 0,
            "L3": 1,
            "dispatch_wave": 0,
            "dispatch_stage": 0,
            "dispatch_task": 0,
            "collapse_l0_l3": 0,
        }
    }
    ratios = audit_layer.compute_layer_ratios(per_doc)
    assert ratios["standalone_l1_ratio"] == 0.0
    assert ratios["standalone_l2_ratio"] == 0.0
    assert ratios["standalone_l3_ratio"] == 0.0
    assert ratios["collapse_ratio"] == 0.0
    assert ratios["total_dispatch_lines"] == 0.0


def test_compute_layer_ratios_aggregates_across_docs() -> None:
    """Aggregate ratios are total_kind / sum(dispatch lines)."""
    per_doc: dict[str, dict[str, int]] = {
        "a": {
            "L0": 1,
            "L1": 0,
            "L2": 1,
            "L3": 1,
            "dispatch_wave": 5,
            "dispatch_stage": 1,
            "dispatch_task": 0,
            "collapse_l0_l3": 2,
        },
        "b": {
            "L0": 1,
            "L1": 0,
            "L2": 0,
            "L3": 1,
            "dispatch_wave": 5,
            "dispatch_stage": 1,
            "dispatch_task": 0,
            "collapse_l0_l3": 1,
        },
    }
    ratios = audit_layer.compute_layer_ratios(per_doc)
    assert ratios["total_dispatch_lines"] == 12
    assert ratios["standalone_l2_ratio"] == pytest.approx(10 / 12)
    assert ratios["standalone_l1_ratio"] == pytest.approx(2 / 12)
    assert ratios["standalone_l3_ratio"] == pytest.approx(0 / 12)
    assert ratios["collapse_ratio"] == pytest.approx(3 / 12)


# ── render_markdown_report ────────────────────────────────────────────


def test_render_markdown_report_contains_headings() -> None:
    """Output carries the expected section headings + per-doc table."""
    per_doc = {
        "x.md": {
            "L0": 1,
            "L1": 0,
            "L2": 1,
            "L3": 1,
            "dispatch_wave": 1,
            "dispatch_stage": 0,
            "dispatch_task": 0,
            "collapse_l0_l3": 0,
        }
    }
    ratios = audit_layer.compute_layer_ratios(per_doc)
    md = audit_layer.render_markdown_report(per_doc, ratios)
    assert "# v10.5.0 PV-01 D-A-1 Layer Usage Audit" in md
    assert "## Summary" in md
    assert "## Per-Doc Layer Mentions" in md
    assert "## Recommendation" in md
    assert "`x.md`" in md


# ── scan_cycle_docs + run smoke ─────────────────────────────────────────


def test_scan_cycle_docs_returns_sorted(tmp_path: Path) -> None:
    """Globs return sorted matches from ``.local/research/``."""
    research = tmp_path / ".local" / "research"
    research.mkdir(parents=True)
    (research / "v9.5.0_cycle_plan.md").write_text("Dispatch type: Wave\nL0 L3", encoding="utf-8")
    (research / "v10.2.0_cycle_plan.md").write_text("Dispatch type: Wave", encoding="utf-8")
    (research / "v10.3.0_retrospective.md").write_text("Dispatch type: Stage", encoding="utf-8")
    (research / "unrelated.md").write_text("not a cycle doc", encoding="utf-8")

    matches = audit_layer.scan_cycle_docs(tmp_path)
    names = [m.name for m in matches]
    assert "unrelated.md" not in names
    assert names == sorted(names)
    assert "v9.5.0_cycle_plan.md" in names
    assert "v10.3.0_retrospective.md" in names


def test_scan_cycle_docs_handles_missing_research_dir(tmp_path: Path) -> None:
    """Fresh clone without ``.local/research/`` -> empty list, no error."""
    assert audit_layer.scan_cycle_docs(tmp_path) == []


def test_run_emits_markdown_to_output(tmp_path: Path) -> None:
    """The CLI run() writes markdown to --output when provided."""
    research = tmp_path / ".local" / "research"
    research.mkdir(parents=True)
    (research / "v10.4.0_cycle_plan.md").write_text(
        "L0 dispatches.\nDispatch type: Wave\n", encoding="utf-8"
    )

    out = tmp_path / "report.md"
    rc = audit_layer.run(tmp_path, output=out)
    assert rc == 0
    text = out.read_text(encoding="utf-8")
    assert "## Summary" in text
    assert "v10.4.0_cycle_plan.md" in text


def test_run_emits_json_when_requested(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """``--json`` path returns parseable JSON with both ``per_doc`` + ``ratios``."""
    research = tmp_path / ".local" / "research"
    research.mkdir(parents=True)
    (research / "v10.4.0_cycle_plan.md").write_text(
        "Dispatch type: Wave\nL0 dispatches.", encoding="utf-8"
    )

    rc = audit_layer.run(tmp_path, json_out=True)
    assert rc == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert "per_doc" in payload
    assert "ratios" in payload
    assert payload["ratios"]["total_dispatch_lines"] == 1


# ── v11.1.0 PV-05 G-AUDIT-1 cascade-ratchet tests ──────────────────────


def test_strict_flag_returns_zero_when_above_threshold(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Strict-mode invocation returns 0 when cascade_ratio > threshold.

    Cascade-compliance signal = (Stage + Wave) / total_dispatch.
    Fixture: 4 Wave + 4 Stage + 2 Task -> cascade_ratio = 8/10 = 0.80,
    well above the 0.30 threshold -> exit 0.
    """
    research = tmp_path / ".local" / "research"
    research.mkdir(parents=True)
    (research / "v10.0.0_cycle_plan.md").write_text(
        "\n".join(
            [
                "Dispatch type: Wave",
                "Dispatch type: Wave",
                "Dispatch type: Wave",
                "Dispatch type: Wave",
                "Dispatch type: Stage",
                "Dispatch type: Stage",
                "Dispatch type: Stage",
                "Dispatch type: Stage",
                "Dispatch type: Task",
                "Dispatch type: Task",
            ]
        ),
        encoding="utf-8",
    )
    rc = audit_layer.run(tmp_path, strict=True, threshold=0.30)
    capsys.readouterr()
    assert rc == 0


def test_strict_flag_returns_one_when_below_threshold(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Strict-mode invocation returns 1 when cascade_ratio < threshold.

    Fixture: 5 Task lines only -> cascade_ratio = 0/5 = 0.0, well below
    the 0.30 floor -> exit 1 (the v11.1.0 PV-05 ratchet fires).
    """
    research = tmp_path / ".local" / "research"
    research.mkdir(parents=True)
    (research / "v10.1.0_cycle_plan.md").write_text(
        "\n".join(
            [
                "Dispatch type: Task",
                "Dispatch type: Task",
                "Dispatch type: Task",
                "Dispatch type: Task",
                "Dispatch type: Task",
            ]
        ),
        encoding="utf-8",
    )
    rc = audit_layer.run(tmp_path, strict=True, threshold=0.30)
    capsys.readouterr()
    assert rc == 1


def test_strict_flag_default_off_preserves_byte_identical_v11_0x(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """R5 strict backward-compat: default ``run()`` returns 0 even on a low-cascade fixture.

    Without ``strict=True``, the same all-Task fixture that triggers
    the strict-mode failure path MUST still return 0 — byte-identical
    to v11.0.x observability-only behaviour.
    """
    research = tmp_path / ".local" / "research"
    research.mkdir(parents=True)
    (research / "v10.2.0_cycle_plan.md").write_text(
        "\n".join(
            [
                "Dispatch type: Task",
                "Dispatch type: Task",
                "Dispatch type: Task",
            ]
        ),
        encoding="utf-8",
    )
    rc = audit_layer.run(tmp_path)
    capsys.readouterr()
    assert rc == 0


def test_cascade_ratio_field_present_in_output() -> None:
    """``compute_layer_ratios`` exposes the new ``cascade_ratio`` field.

    Pins:
      * Field name + type (float in [0.0, 1.0]).
      * Formula = (total_stage + total_wave) / total_dispatch on a
        fixture where the input counts are known a priori.
      * Empty-input handling: cascade_ratio == 0.0 when
        total_dispatch == 0 (matches the other ratios' empty-input
        contract — no division-by-zero, no false positive).
    """
    per_doc: dict[str, dict[str, int]] = {
        "a": {
            "L0": 1,
            "L1": 1,
            "L2": 1,
            "L3": 1,
            "dispatch_wave": 3,
            "dispatch_stage": 2,
            "dispatch_task": 5,
            "collapse_l0_l3": 0,
        },
    }
    ratios = audit_layer.compute_layer_ratios(per_doc)
    assert "cascade_ratio" in ratios
    cascade = ratios["cascade_ratio"]
    assert isinstance(cascade, float)
    assert 0.0 <= cascade <= 1.0
    assert cascade == pytest.approx((2 + 3) / 10)
    assert ratios["total_dispatch_lines"] == 10

    empty_doc: dict[str, dict[str, int]] = {
        "z": {
            "L0": 0,
            "L1": 0,
            "L2": 0,
            "L3": 0,
            "dispatch_wave": 0,
            "dispatch_stage": 0,
            "dispatch_task": 0,
            "collapse_l0_l3": 0,
        },
    }
    empty_ratios = audit_layer.compute_layer_ratios(empty_doc)
    assert "cascade_ratio" in empty_ratios
    assert empty_ratios["cascade_ratio"] == 0.0
