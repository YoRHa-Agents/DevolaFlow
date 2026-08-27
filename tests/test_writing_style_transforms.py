"""Tests for the five SAFE writing-style transforms (PV-03)."""

from __future__ import annotations

from devolaflow.writing_style import (
    DOCUMENTATION_NATURAL,
    TECHNICAL_CONCISE,
    apply_transforms,
)
from devolaflow.writing_style.transforms import (
    TRANSFORM_ORDER,
    bullets,
    cliches,
    emdash,
    headers,
    signposts,
)


def test_apply_transforms_returns_result_with_fields() -> None:
    result = apply_transforms("Plain text.", DOCUMENTATION_NATURAL)
    assert result.before == "Plain text."
    assert isinstance(result.after, str)
    assert "emdash" in result.transforms_run


def test_region_split_round_trip_under_all_transforms() -> None:
    text = (
        "Before prose — with em-dash.\n\n"
        "```python\n"
        "# code: -- -- -- never touch\n"
        "x = 1\n"
        "```\n\n"
        "After code. Version v10.1.0 stays intact. "
        "A link [here](https://example.com/--/--) keeps its -- too.\n"
    )
    result = apply_transforms(text, DOCUMENTATION_NATURAL)
    assert "# code: -- -- -- never touch" in result.after
    assert "v10.1.0" in result.after
    assert "https://example.com/--/--" in result.after


def test_emdash_normalises_ascii_dashdash() -> None:
    text = "First -- then more -- and final."
    out = emdash.apply(text, DOCUMENTATION_NATURAL)
    assert "--" not in out
    assert out.count("\u2014") >= 1


def test_emdash_caps_density_in_paragraph() -> None:
    text = "One \u2014 two \u2014 three \u2014 four \u2014 five."
    out = emdash.apply(text, DOCUMENTATION_NATURAL)
    assert out.count("\u2014") == 1


def test_emdash_idempotent() -> None:
    text = "One \u2014 two \u2014 three \u2014 four."
    once = emdash.apply(text, DOCUMENTATION_NATURAL)
    twice = emdash.apply(once, DOCUMENTATION_NATURAL)
    assert once == twice


def test_emdash_preserves_code_block() -> None:
    text = "Prose -- one.\n\n```\ncode -- stays -- here\n```\n\nPost -- prose."
    out = emdash.apply(text, DOCUMENTATION_NATURAL)
    assert "code -- stays -- here" in out


def test_emdash_document_density_cap_demotes_excess() -> None:
    paragraphs = [
        f"Paragraph {i} contains enough ordinary prose words for density checks — pause here."
        for i in range(20)
    ]
    out = emdash.apply("\n\n".join(paragraphs), DOCUMENTATION_NATURAL)
    assert out.count("\u2014") == 1
    assert out.count(", ") >= 19


def test_emdash_demote_helper_clamps_negative_budget() -> None:
    out = emdash._demote_excess_emdashes("left — middle — right", -1)
    assert out == "left, middle, right"


def test_bullets_collapses_single_item_list_after_colon() -> None:
    text = "Here are the options:\n\n- Use emdash\n\nNext paragraph."
    out = bullets.apply(text, DOCUMENTATION_NATURAL)
    assert "- Use emdash" not in out
    assert "Use emdash" in out


def test_bullets_preserves_three_or_more_item_lists() -> None:
    text = "Three things:\n\n- First\n- Second\n- Third\n\nEnd."
    out = bullets.apply(text, DOCUMENTATION_NATURAL)
    assert "- First" in out
    assert "- Second" in out
    assert "- Third" in out


def test_bullets_skips_long_bullets() -> None:
    long_item = "x" * 150
    text = f"List:\n\n- {long_item}\n- short\n\nEnd."
    out = bullets.apply(text, DOCUMENTATION_NATURAL)
    assert f"- {long_item}" in out


def test_bullets_preserves_code_yaml() -> None:
    text = "Config below:\n\n```yaml\n- item1\n- item2\n```\n\nDone."
    out = bullets.apply(text, DOCUMENTATION_NATURAL)
    assert "- item1" in out
    assert "- item2" in out


def test_signposts_strips_sentence_start_prefix() -> None:
    text = "It's worth noting that the system caches aggressively."
    out = signposts.apply(text, DOCUMENTATION_NATURAL)
    assert not out.lower().startswith("it's worth noting")
    assert "caches aggressively" in out.lower()


def test_signposts_preserves_link_text() -> None:
    text = "See [in conclusion, an example](https://example.com) for details."
    out = signposts.apply(text, DOCUMENTATION_NATURAL)
    assert "[in conclusion, an example]" in out


def test_signposts_idempotent() -> None:
    text = "In conclusion, it works. Furthermore, it is fast."
    once = signposts.apply(text, DOCUMENTATION_NATURAL)
    twice = signposts.apply(once, DOCUMENTATION_NATURAL)
    assert once == twice


def test_headers_demotes_orphan_short_section() -> None:
    long_body = " ".join(f"word{i}" for i in range(60))
    text = f"### Tiny Header\n\nJust three words here.\n\n### Next Section\n\n{long_body}\n"
    out = headers.apply(text, DOCUMENTATION_NATURAL)
    assert "### Tiny Header" not in out
    assert "**Tiny Header**" in out
    assert "### Next Section" in out


def test_headers_preserves_long_section() -> None:
    body = " ".join(f"word{i}" for i in range(60))
    text = f"### Real Section\n\n{body}\n"
    out = headers.apply(text, DOCUMENTATION_NATURAL)
    assert "### Real Section" in out


def test_headers_preserves_h2_as_real_landmark() -> None:
    """H2 headers are never demoted — they are the coarse section
    structure authors deliberately set up."""
    text = "## Short H2\n\nOnly a couple of words here.\n"
    out = headers.apply(text, DOCUMENTATION_NATURAL)
    assert "## Short H2" in out


def test_headers_preserves_h1_document_title() -> None:
    text = "# Project Title\n\nShort intro.\n"
    out = headers.apply(text, DOCUMENTATION_NATURAL)
    assert "# Project Title" in out


def test_cliches_strips_sycophantic_phrases() -> None:
    text = "Great question! The answer is yes. Absolutely! here we go."
    out = cliches.apply(text, DOCUMENTATION_NATURAL)
    assert "great question" not in out.lower()
    assert "absolutely!" not in out.lower()


def test_cliches_preserves_code_block_content() -> None:
    text = "```\nfake_response = 'Great question!'\n```\n\nOutside: Great question! here."
    out = cliches.apply(text, DOCUMENTATION_NATURAL)
    assert "'Great question!'" in out


def test_apply_transforms_respects_technical_concise_disabled_set() -> None:
    """CHANGELOG policy (technical_concise) disables T-S2/T-S3/T-S4 —
    bullets, signposts, and headers transforms must not run."""
    text = (
        "In conclusion, note the change.\n\nChanges:\n\n- One change\n\n## Tiny section\n\nShort.\n"
    )
    result = apply_transforms(text, TECHNICAL_CONCISE)
    assert "bullets" not in result.transforms_run
    assert "signposts" not in result.transforms_run
    assert "headers" not in result.transforms_run
    assert "emdash" in result.transforms_run
    assert "cliches" in result.transforms_run


def test_apply_transforms_canonical_order() -> None:
    assert TRANSFORM_ORDER == ("emdash", "bullets", "signposts", "cliches", "headers")


def test_apply_transforms_enabled_override() -> None:
    text = "One -- two -- three -- four -- five."
    result = apply_transforms(text, DOCUMENTATION_NATURAL, enabled={"emdash": True})
    assert result.transforms_run == ("emdash",)


def test_apply_transforms_byte_delta_matches_before_after() -> None:
    text = "Plain — text."
    result = apply_transforms(text, DOCUMENTATION_NATURAL)
    assert result.byte_delta == len(result.after) - len(result.before)


def test_region_split_round_trip_on_fixture() -> None:
    """The regions.split contract must round-trip on a fixture that
    stresses every protected region type."""
    from devolaflow.writing_style.regions import split

    text = (
        "# Heading\n\n"
        "Prose with `inline.code()`.\n\n"
        "See [docs](https://example.com) and `more-code`.\n\n"
        "```python\n"
        "# fence -- with -- dashes\n"
        "x = 'hello'\n"
        "```\n\n"
        "Version v10.1.0 + v9.2.3-rc1.\n"
        "Bare url: https://example.com/path?q=1.\n"
        'HTML <span class="x">inline</span> span.\n'
    )
    regions = split(text)
    assert "".join(r.text for r in regions) == text


def test_humanize_preserves_version_string_round_trip() -> None:
    """A paragraph containing vX.Y.Z must come through every transform
    byte-identical on the version token."""
    text = (
        "Shipped v10.1.0 after testing. In conclusion, the upgrade "
        "went well. We also shipped v9.2.3-rc1 earlier."
    )
    result = apply_transforms(text, DOCUMENTATION_NATURAL)
    assert "v10.1.0" in result.after
    assert "v9.2.3-rc1" in result.after


def test_signposts_catalog_loads_without_error() -> None:
    from devolaflow.writing_style.transforms.signposts import _load_prefixes

    prefixes = _load_prefixes()
    assert len(prefixes) >= 20
    assert all(p == p.lower() for p in prefixes)


def test_cliches_catalog_loads_without_error() -> None:
    from devolaflow.writing_style.transforms.cliches import _load_phrases

    phrases = _load_phrases()
    assert len(phrases) >= 5
    assert all(p == p.lower() for p in phrases)


# ---------------------------------------------------------------------------
# v12.4.0 PV-04 D-3 — helper-level tests for the ``_collapse_block`` refactor.
#
# The PV-04 refactor extracted four helpers from the cc=25 original
# (see ``.local/research/v12.4.0_gap_analysis.md`` §2 D-3):
#
# * ``_classify_block_lines`` — split into intro / bullets / tail
# * ``_validate_bullet_constraints`` — ≤2 items / no indent / ≤80 chars / non-empty
# * ``_collapse_no_intro`` — emit when intro is empty
# * ``_collapse_with_intro`` — emit when intro is present, dispatch on suffix
#
# These tests pin per-helper invariants so a future PV that grows a
# helper's branch space catches the regression at the helper level
# instead of bubbling up through the orchestrator's fixture tests. Per
# the v8.3.0 retro §4.6 test-discipline lesson: loop-asserts within
# single test functions so the cycle stays under the W-17 +30/PV cap.
# ---------------------------------------------------------------------------


def test_classify_block_lines_partitions_and_rejects() -> None:
    """``_classify_block_lines`` partitions normal blocks and rejects malformed ones.

    Three sub-cases in one fixture: (1) happy path with intro + 2
    bullets + tail, (2) bullet at different indent within the same
    block returns None (mis-aligned list), (3) block with no bullets at
    all returns None.
    """
    from devolaflow.writing_style.transforms.bullets import _classify_block_lines

    # (1) Happy path — intro paragraph + 2 bullets + tail.
    parts = _classify_block_lines(
        ["Intro paragraph:", "- first item", "- second item", "tail text"]
    )
    assert parts is not None
    assert parts.intro == ["Intro paragraph:"]
    assert parts.bullets_indent == ""
    assert parts.bullet_items == ["first item", "second item"]
    assert parts.tail == ["tail text"]

    # (2) Indent mismatch — second bullet has different indentation; reject.
    rejected = _classify_block_lines(["- a", "  - b"])
    assert rejected is None

    # (3) No bullets — nothing to collapse, reject.
    no_bullets = _classify_block_lines(["just prose", "more prose"])
    assert no_bullets is None


def test_validate_bullet_constraints_accept_and_reject_paths() -> None:
    """``_validate_bullet_constraints`` enforces the 4 collapse-eligibility rules.

    Five sub-cases: (1) happy path accepts, (2) 3+ items reject,
    (3) non-empty indent reject (nested list), (4) bullet too long
    reject, (5) empty bullet reject.
    """
    from devolaflow.writing_style.transforms.bullets import (
        _BlockParts,
        _validate_bullet_constraints,
    )

    # (1) Happy path — 1-2 items, no indent, all ≤ 80 chars, non-empty.
    ok = _BlockParts(intro=[], bullets_indent="", bullet_items=["short item"], tail=[])
    assert _validate_bullet_constraints(ok) is True

    # (2) > 2 items — real list, reject.
    too_many = _BlockParts(intro=[], bullets_indent="", bullet_items=["a", "b", "c"], tail=[])
    assert _validate_bullet_constraints(too_many) is False

    # (3) Non-empty indent — nested or indented list, reject.
    nested = _BlockParts(intro=[], bullets_indent="  ", bullet_items=["x"], tail=[])
    assert _validate_bullet_constraints(nested) is False

    # (4) Bullet too long — real list structure, reject.
    long_item = "x" * 150
    too_long = _BlockParts(intro=[], bullets_indent="", bullet_items=[long_item], tail=[])
    assert _validate_bullet_constraints(too_long) is False

    # (5) Empty bullet — author was editing, reject.
    empty = _BlockParts(intro=[], bullets_indent="", bullet_items=["   "], tail=[])
    assert _validate_bullet_constraints(empty) is False


def test_collapse_no_intro_one_and_two_item_shapes() -> None:
    """``_collapse_no_intro`` emits the bullet body for 1-item and a merged pair for 2-item."""
    from devolaflow.writing_style.transforms.bullets import _collapse_no_intro

    # 1-item case — single bullet body becomes a standalone line.
    out1 = _collapse_no_intro(["use emdash"], ["tail line"])
    assert out1 == ["use emdash", "tail line"]

    # 2-item case — merged ``"X, and Y"`` continuation.
    out2 = _collapse_no_intro(["first thing", "second thing"], [])
    assert out2 == ["first thing, and second thing"]

    # rstrip() applied to each bullet so trailing whitespace is normalised.
    out3 = _collapse_no_intro(["one   ", "two   "], ["tail"])
    assert out3 == ["one, and two", "tail"]


def test_collapse_with_intro_dispatches_on_suffix_punctuation() -> None:
    """``_collapse_with_intro`` emits different continuation shapes based on intro suffix.

    Four sub-cases dispatch on the intro's final punctuation:
    (1) ``:`` → colon-prefix continuation,
    (2) ``.`` → em-dash continuation with trailing period,
    (3) ``!`` / ``?`` → space-joined continuation preserving the
    sentence-final punctuation in the intro_body.
    Plus the 2-item ``"X, and Y"`` merge interaction.
    """
    from devolaflow.writing_style.transforms.bullets import _collapse_with_intro

    intro_paragraphs = ["earlier paragraph", ""]

    # (1) ``:`` suffix — colon-prefix continuation.
    out_colon = _collapse_with_intro(
        intro_paragraphs + ["Note this:"], "Note this:", ["use emdash"], ["after"]
    )
    assert out_colon == [*intro_paragraphs, "Note this: use emdash", "after"]

    # (2) ``.`` suffix — em-dash continuation with period.
    out_dot = _collapse_with_intro(
        intro_paragraphs + ["Note this."], "Note this.", ["use emdash"], []
    )
    assert out_dot == [*intro_paragraphs, "Note this \u2014 use emdash."]

    # (3) ``!`` suffix — space-joined continuation preserves the ``!``.
    out_bang = _collapse_with_intro(intro_paragraphs + ["Look!"], "Look!", ["use emdash"], [])
    assert out_bang == [*intro_paragraphs, "Look! use emdash"]

    # (4) 2-item merge interaction — colon suffix + merged continuation.
    out_two = _collapse_with_intro(
        intro_paragraphs + ["Options:"],
        "Options:",
        ["first thing", "second thing"],
        ["after"],
    )
    assert out_two == [*intro_paragraphs, "Options: first thing, and second thing", "after"]


def test_classify_then_validate_round_trip_through_collapse_block() -> None:
    """Composition test — the 4 helpers compose into byte-identical ``_collapse_block`` behaviour.

    Lights up the orchestrator's full pipeline (classify → validate →
    collapse_no_intro / collapse_with_intro) for a fixture that
    exercises every helper at least once, mirroring the pre-refactor
    apply(text, profile) byte-identical guarantee from the
    ``test_bullets_*`` fixture corpus above.
    """
    from devolaflow.writing_style.transforms.bullets import _collapse_block

    # Single-bullet block with ``:`` intro suffix — colon-prefix continuation.
    out_colon = _collapse_block(["Note this:", "- only item"])
    assert out_colon == ["Note this: only item"]

    # Two-bullet block with ``.`` intro suffix — em-dash continuation.
    out_dot = _collapse_block(["Earlier paragraph.", "- first", "- second"])
    assert out_dot == ["Earlier paragraph \u2014 first, and second."]

    # Pure-bullet block (no intro) — emits the bullet bodies as prose.
    out_pure = _collapse_block(["- standalone item"])
    assert out_pure == ["standalone item"]

    # Reject path (3+ bullets) — return input unchanged byte-identically.
    out_long = _collapse_block(["Three items:", "- a", "- b", "- c"])
    assert out_long == ["Three items:", "- a", "- b", "- c"]
