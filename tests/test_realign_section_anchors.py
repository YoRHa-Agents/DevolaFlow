"""v12.4.0 PV-02 — verify ``scripts/realign_section_anchors.py`` behaviour.

Closes the v12.3.0 retrospective §4.3 learning. The script auto-realigns
``context_profiles.yaml`` ``sections:`` block ``lines: "X-Y"`` ranges
against the current ``workflow-system/agent/SKILL.md`` headers, eliminating
the ~15 min/cycle of manual edits the v12.3.0 cycle hit.

Five primary assertions, each isolated against a ``tmp_path`` fixture so
the production SKILL.md / context_profiles.yaml stays untouched:

1. ``test_header_parse_correctness`` — fixture SKILL.md → expected list
   of ``Header`` (line, depth, title) tuples.
2. ``test_idempotent_apply`` — apply twice ⇒ second run rewrites 0
   anchors and the YAML file content is byte-identical between the two
   states that follow run-1 and run-2.
3. ``test_drift_detection_proposes_correct_realignment`` — fixture
   SKILL.md edit shifts headers; running the script with start-aligned
   YAML proposes the correct new end ranges.
4. ``test_dry_run_does_not_modify_file`` — the YAML file's bytes are
   identical before and after a ``dry_run=True`` invocation, AND the
   proposals are still computed for the operator to review.
5. ``test_missing_input_raises_friendly_error`` — ``S-5`` compliance:
   missing input files raise ``FileNotFoundError`` with a clear message
   (no silent failure).

Source: ``.local/research/v12.3.0_retrospective.md`` §4.3 +
``.local/research/v12.4.0_gap_analysis.md`` §2 D-1 (item 2).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR_STR = str(REPO_ROOT / "scripts")
if _SCRIPTS_DIR_STR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR_STR)

from realign_section_anchors import (  # noqa: E402  # sys.path adjusted above
    AnchorChange,
    Header,
    _format_report,
    _main,
    compute_realignment,
    parse_section_anchors,
    parse_skill_md_headers,
    realign_anchors,
)

FIXTURE_SKILL_MD = """---
name: test-skill
---

# Top-level title

Intro prose.

## Alpha Section

Alpha body line 1.
Alpha body line 2.

### Alpha-Sub Section

Alpha-sub body.

## Beta Section

Beta body line 1.
Beta body line 2.
Beta body line 3.

## Gamma Section

Gamma body.
"""

FIXTURE_PROFILES_YAML_TEMPLATE = """# Fixture context_profiles.yaml for realign tests.
section_anchors: {{}}

sections:
  frontmatter:
    lines: "1-4"
    tokens_est: 10
    content_type: metadata

  alpha_section:
    lines: "{alpha_lines}"
    tokens_est: 50
    content_type: prose

  alpha_sub_section:
    lines: "{alpha_sub_lines}"
    tokens_est: 30
    content_type: spec

  beta_section:
    lines: "{beta_lines}"
    tokens_est: 60
    content_type: table

  beta_inner:
    lines: "{beta_inner_lines}"
    tokens_est: 25
    content_type: constraints

  external_advisor:
    lines: "N/A"
    tokens_est: 100
    content_type: integration

# Context profiles per task type
profiles: {{}}
"""


def _write_fixture(
    tmp_path: Path,
    skill_text: str = FIXTURE_SKILL_MD,
    *,
    alpha_lines: str = "9-13",
    alpha_sub_lines: str = "14-17",
    beta_lines: str = "18-23",
    beta_inner_lines: str = "20-22",
) -> tuple[Path, Path]:
    """Write SKILL.md + context_profiles.yaml under ``tmp_path``.

    Returns ``(skill_md_path, profiles_yaml_path)``. ``alpha_lines`` etc are
    parameterised so each test can construct a YAML whose ranges either match
    or deliberately mismatch the SKILL.md fixture.
    """
    skill_path = tmp_path / "SKILL.md"
    skill_path.write_text(skill_text, encoding="utf-8")
    profiles_path = tmp_path / "context_profiles.yaml"
    profiles_path.write_text(
        FIXTURE_PROFILES_YAML_TEMPLATE.format(
            alpha_lines=alpha_lines,
            alpha_sub_lines=alpha_sub_lines,
            beta_lines=beta_lines,
            beta_inner_lines=beta_inner_lines,
        ),
        encoding="utf-8",
    )
    return skill_path, profiles_path


def test_header_parse_correctness(tmp_path: Path) -> None:
    """``parse_skill_md_headers`` returns the expected ``Header`` tuples.

    The fixture has 1 ``#`` title (ignored — script only reads ``##``/``###``),
    3 ``##`` sections, and 1 ``###`` subsection. The parser MUST preserve
    line numbers (1-indexed) and depths exactly so downstream realignment
    arithmetic is correct.
    """
    skill_path, _ = _write_fixture(tmp_path)
    headers = parse_skill_md_headers(skill_path)

    expected = [
        Header(line=9, depth=2, title="Alpha Section"),
        Header(line=14, depth=3, title="Alpha-Sub Section"),
        Header(line=18, depth=2, title="Beta Section"),
        Header(line=24, depth=2, title="Gamma Section"),
    ]
    assert headers == expected, (
        f"Header parse mismatch: got {headers!r}, expected {expected!r}. "
        "The parser must skip ``#`` (depth=1) titles and only return ``##``/``###``."
    )


def test_idempotent_apply(tmp_path: Path) -> None:
    """``realign_anchors(dry_run=False)`` applied twice yields byte-identical YAML.

    Idempotency contract: after the first apply, the YAML matches SKILL.md.
    A second apply MUST be a no-op (0 rewrites) because the proposals are
    all "old_range == new_range". The file bytes between the two states
    following run-1 and run-2 must be identical.

    Fixture: ``alpha_lines="9-99"`` — start (9) IS a SKILL.md header line
    so the script will engage; end (99) is past EOF so the rewrite shrinks
    it to the correct value (13 = next_header_line 14 minus 1).
    """
    skill_path, profiles_path = _write_fixture(
        tmp_path,
        alpha_lines="9-99",
        alpha_sub_lines="14-17",
        beta_lines="18-23",
        beta_inner_lines="20-22",
    )

    result_a = realign_anchors(skill_path, profiles_path, dry_run=False)
    assert result_a["rewritten"] >= 1, (
        f"Run-1 expected to rewrite >= 1 anchor; got {result_a['rewritten']}. "
        "The fixture deliberately mismatches alpha_section's END line "
        "(9-99) so realignment MUST happen on the first apply."
    )
    state_after_run_1 = profiles_path.read_bytes()

    result_b = realign_anchors(skill_path, profiles_path, dry_run=False)
    assert result_b["rewritten"] == 0, (
        f"Run-2 must be idempotent — expected rewritten=0; got "
        f"{result_b['rewritten']}. After a successful apply, re-running the "
        "script with the SAME inputs must propose no further changes."
    )
    state_after_run_2 = profiles_path.read_bytes()

    assert state_after_run_1 == state_after_run_2, (
        "YAML bytes diverged between run-1 and run-2 even though the "
        "rewritten count was 0. Either the file is being touched without "
        "content change, or the regex rewrite has a hidden non-determinism."
    )


def test_drift_detection_proposes_correct_realignment(tmp_path: Path) -> None:
    """A SKILL.md edit shifts headers; the script proposes the new ranges.

    Simulates the real-world cycle: a PV inserts a new section into
    SKILL.md, shifting every downstream header down by N lines. After
    manually fixing each anchor's START to land on the new header line
    (typical operator workflow), the script computes the correct new END.
    The fixture exercises the dry-run mode so no file is written.
    """
    # Replace "blank + ## Alpha" with "3 inserted + blank + ## Alpha" so the
    # net shift is exactly +3 lines:
    #   old: Intro prose. (7) | (8 blank) | ## Alpha (9)
    #   new: Intro prose. (7) | Inserted-1 (8) | Inserted-2 (9) | Inserted-3 (10)
    #        | (11 blank) | ## Alpha (12)
    shifted_skill = FIXTURE_SKILL_MD.replace(
        "Intro prose.\n\n## Alpha Section",
        "Intro prose.\nInserted line 1.\nInserted line 2.\nInserted line 3.\n\n## Alpha Section",
    )
    skill_path, profiles_path = _write_fixture(
        tmp_path,
        skill_text=shifted_skill,
        alpha_lines="12-99",
        alpha_sub_lines="17-99",
        beta_lines="21-99",
        beta_inner_lines="23-25",
    )

    result = realign_anchors(skill_path, profiles_path, dry_run=True)
    changes_by_anchor = {c.anchor: c for c in result["changes"]}

    assert changes_by_anchor["alpha_section"].new_range == "12-16", (
        f"Expected alpha_section -> 12-16 after +3 shift; got "
        f"{changes_by_anchor['alpha_section'].new_range!r}."
    )
    assert changes_by_anchor["alpha_sub_section"].new_range == "17-20", (
        f"Expected alpha_sub_section -> 17-20; got "
        f"{changes_by_anchor['alpha_sub_section'].new_range!r}."
    )
    assert changes_by_anchor["beta_section"].new_range == "21-26", (
        f"Expected beta_section -> 21-26; got {changes_by_anchor['beta_section'].new_range!r}."
    )
    assert not changes_by_anchor["beta_inner"].changed, (
        f"Expected beta_inner unchanged (sub-range — start not a header); got "
        f"old={changes_by_anchor['beta_inner'].old_range!r} -> "
        f"new={changes_by_anchor['beta_inner'].new_range!r}."
    )


def test_dry_run_does_not_modify_file(tmp_path: Path) -> None:
    """``dry_run=True`` leaves ``profiles_yaml_path`` byte-identical.

    Fixture: ``alpha_lines="9-99"`` so the start IS a header (engages the
    realign path) but the end is deliberately past EOF — the script should
    PROPOSE a change but NOT write the file.
    """
    skill_path, profiles_path = _write_fixture(
        tmp_path,
        alpha_lines="9-99",
    )
    before = profiles_path.read_bytes()
    result = realign_anchors(skill_path, profiles_path, dry_run=True)
    after = profiles_path.read_bytes()
    assert before == after, (
        "dry_run=True modified the YAML file. The dry-run mode MUST be "
        "side-effect-free per the CLI contract (operator uses dry-run for "
        "review BEFORE applying)."
    )
    assert result["dry_run"] is True
    assert result["rewritten"] == 0, (
        f"dry_run=True should never write; got rewritten={result['rewritten']}."
    )
    assert result["changed_count"] >= 1, (
        f"Expected >= 1 proposed change for the deliberately mismatched fixture; "
        f"got {result['changed_count']}. dry_run should still COMPUTE the "
        "proposals, just not apply them."
    )


def test_missing_input_raises_friendly_error(tmp_path: Path) -> None:
    """S-5: missing input files raise ``FileNotFoundError`` with a friendly message.

    No silent fallback — the operator must see a clear actionable error.
    """
    missing_skill = tmp_path / "does_not_exist_SKILL.md"
    profiles_path = tmp_path / "context_profiles.yaml"
    profiles_path.write_text(
        FIXTURE_PROFILES_YAML_TEMPLATE.format(
            alpha_lines="9-13",
            alpha_sub_lines="14-17",
            beta_lines="18-23",
            beta_inner_lines="20-22",
        ),
        encoding="utf-8",
    )
    with pytest.raises(FileNotFoundError, match="SKILL.md not found"):
        realign_anchors(missing_skill, profiles_path)

    skill_path = tmp_path / "SKILL.md"
    skill_path.write_text(FIXTURE_SKILL_MD, encoding="utf-8")
    missing_profiles = tmp_path / "does_not_exist_profiles.yaml"
    with pytest.raises(FileNotFoundError, match="context_profiles.yaml not found"):
        realign_anchors(skill_path, missing_profiles)


def test_parse_section_anchors_extracts_all_entries(tmp_path: Path) -> None:
    """``parse_section_anchors`` returns every anchor in the ``sections:`` block."""
    _, profiles_path = _write_fixture(tmp_path)
    anchors = parse_section_anchors(profiles_path)
    assert set(anchors) == {
        "frontmatter",
        "alpha_section",
        "alpha_sub_section",
        "beta_section",
        "beta_inner",
        "external_advisor",
    }, f"Got anchors: {sorted(anchors)}"
    assert anchors["external_advisor"] == "N/A"


def test_compute_realignment_leaves_na_and_frontmatter_alone(tmp_path: Path) -> None:
    """``N/A`` anchors and start-at-line-1 anchors are reported as unchanged."""
    skill_path, profiles_path = _write_fixture(tmp_path)
    headers = parse_skill_md_headers(skill_path)
    anchors = parse_section_anchors(profiles_path)
    changes = compute_realignment(headers, anchors)
    by_anchor = {c.anchor: c for c in changes}
    assert not by_anchor["frontmatter"].changed, (
        "frontmatter (start=1) must be left alone — line 1 of a SKILL.md is "
        "YAML frontmatter, not a header."
    )
    assert not by_anchor["external_advisor"].changed, (
        "external_advisor (lines='N/A') must be left alone — external "
        "references have no SKILL.md line range."
    )


def test_format_report_renders_changes(tmp_path: Path) -> None:
    """``_format_report`` produces the documented dry-run / apply messages."""
    skill_path, profiles_path = _write_fixture(tmp_path, alpha_lines="9-99")
    result = realign_anchors(skill_path, profiles_path, dry_run=True)
    msg = _format_report(result)
    assert "would change" in msg, f"Expected 'would change' in dry-run report; got: {msg!r}"
    assert "alpha_section" in msg, f"Expected alpha_section anchor name in report; got: {msg!r}"


def test_cli_smoke_dry_run_exits_zero(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The ``--dry-run`` CLI smoke test exits 0 and prints a status line.

    Acceptance criterion 6 of the PV-02 spec: the CLI must exit 0 with a
    clear "no changes" or "would change N anchors" message in dry-run.
    """
    skill_path, profiles_path = _write_fixture(tmp_path, alpha_lines="9-99")
    rc = _main(
        [
            "--skill-md",
            str(skill_path),
            "--profiles-yaml",
            str(profiles_path),
            "--dry-run",
        ]
    )
    assert rc == 0, f"Expected dry-run CLI exit code 0; got {rc}."
    captured = capsys.readouterr()
    assert "realign_section_anchors:" in captured.out, (
        f"Expected status line in stdout; got out={captured.out!r}, err={captured.err!r}."
    )


def test_cli_smoke_missing_input_exits_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """CLI returns non-zero exit on missing input (S-5 friendly error)."""
    missing = tmp_path / "nope.md"
    profiles_path = tmp_path / "context_profiles.yaml"
    profiles_path.write_text(
        FIXTURE_PROFILES_YAML_TEMPLATE.format(
            alpha_lines="9-13",
            alpha_sub_lines="14-17",
            beta_lines="18-23",
            beta_inner_lines="20-22",
        ),
        encoding="utf-8",
    )
    rc = _main(
        [
            "--skill-md",
            str(missing),
            "--profiles-yaml",
            str(profiles_path),
            "--dry-run",
        ]
    )
    assert rc == 1, f"Expected exit code 1 for missing input; got {rc}."
    err = capsys.readouterr().err
    assert "ERROR" in err and "SKILL.md not found" in err, (
        f"Expected friendly S-5 error in stderr; got err={err!r}."
    )


def test_anchor_change_dataclass_changed_property() -> None:
    """``AnchorChange.changed`` returns True iff old != new (frozen dataclass)."""
    same = AnchorChange(anchor="x", old_range="1-5", new_range="1-5")
    differ = AnchorChange(anchor="y", old_range="1-5", new_range="1-8")
    assert not same.changed
    assert differ.changed
