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
    text = f"## Tiny Header\n\nJust three words here.\n\n## Next Section\n\n{long_body}\n"
    out = headers.apply(text, DOCUMENTATION_NATURAL)
    assert "## Tiny Header" not in out
    assert "**Tiny Header**" in out
    assert "## Next Section" in out


def test_headers_preserves_long_section() -> None:
    body = " ".join(f"word{i}" for i in range(60))
    text = f"## Real Section\n\n{body}\n"
    out = headers.apply(text, DOCUMENTATION_NATURAL)
    assert "## Real Section" in out


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
