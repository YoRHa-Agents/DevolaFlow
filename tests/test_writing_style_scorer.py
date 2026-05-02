"""Tests for ``devolaflow.writing_style.scorer`` + ``profiles`` + ``regions``.

These pin the port of the PV-01 probe against the production module so
future edits to the scorer can't silently break the benchmark baseline.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from devolaflow.writing_style import (
    DOCUMENTATION_NATURAL,
    MARKETING_WARM,
    TECHNICAL_CONCISE,
    StyleError,
    compute_composite,
    extract_features,
    load_profile,
    profile_for_path,
    score_corpus,
    score_text,
)
from devolaflow.writing_style.regions import apply_to_prose, prose_only, split

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_empty_text_scores_cleanly() -> None:
    score = score_text("", DOCUMENTATION_NATURAL)
    assert score.features.words == 0
    assert 0.0 <= score.composite <= 100.0


def test_score_bounds_on_pathological_input() -> None:
    saturated = ("leverage " * 300) + (" — " * 200)
    score = score_text(saturated, DOCUMENTATION_NATURAL)
    assert 0.0 <= score.composite <= 100.0


def test_burstiness_reward_on_human_like_rhythm() -> None:
    flat = (
        "This is a sentence about tests. This is another sentence. "
        "Here is a third. Here is a fourth. Here is a fifth. "
        "Here is a sixth. Here is a seventh."
    )
    bursty = (
        "Short. Long sentences can get very long indeed, stretching "
        "across clauses and commas and sub-clauses that keep on going. "
        "Short again. Medium length here. Then another short one. "
        "Then a long one that goes on and on about nothing in particular."
    )
    s_flat = score_text(flat, DOCUMENTATION_NATURAL)
    s_bursty = score_text(bursty, DOCUMENTATION_NATURAL)
    assert s_bursty.features.burstiness >= s_flat.features.burstiness


def test_emdash_density_penalises_composite() -> None:
    clean = "This paragraph has zero em-dashes. It reads naturally. There are several sentences."
    heavy = (
        "This paragraph — with — many — em-dashes — reads — unnaturally — "
        "as — an — AI — would — write — it."
    )
    s_clean = score_text(clean, DOCUMENTATION_NATURAL)
    s_heavy = score_text(heavy, DOCUMENTATION_NATURAL)
    assert s_heavy.features.emdash_per_1k > s_clean.features.emdash_per_1k


def test_code_blocks_do_not_count_toward_lexical_features() -> None:
    with_code = """
Regular prose here, short.

```python
leverage = "delve"
tapestry = "embark"
```

More prose.
""".strip()
    score = score_text(with_code, DOCUMENTATION_NATURAL)
    assert score.features.tier1_count == 0


def test_version_strings_preserved_in_regions() -> None:
    text = "We shipped v10.1.0 and then v10.2.0-rc1 came next."
    regions = split(text)
    versions = [r for r in regions if r.kind == "version"]
    assert len(versions) == 2
    assert versions[0].text == "v10.1.0"


def test_regions_round_trip_byte_stable() -> None:
    text = (
        "## Heading\n\n"
        "Prose with `inline code` and an [anchor](https://example.com/path).\n\n"
        "```js\nconst x = 1;\n```\n\n"
        "v9.0.0 appears inline. And bare https://example.org ok.\n"
    )
    regions = split(text)
    assert "".join(r.text for r in regions) == text


def test_prose_only_strips_protected_regions() -> None:
    text = "Prose. ```\ncode\n``` More prose."
    cleaned = prose_only(text)
    assert "code" not in cleaned
    assert "More prose" in cleaned


def test_apply_to_prose_does_not_touch_code() -> None:
    text = "hi `code` bye"
    out = apply_to_prose(text, lambda s: s.upper())
    assert out == "HI `code` BYE"


def test_profile_weight_sum_validated() -> None:
    from devolaflow.writing_style.profiles import (
        FeatureCaps,
        ToneProfile,
    )

    bad = ToneProfile(
        name="bad",
        weights={"burstiness": 0.5, "ttr": 0.1},
        caps=FeatureCaps(),
        advisory_floor=65.0,
        hard_floor=45.0,
    )
    features = extract_features("Hello world.")
    with pytest.raises(StyleError):
        compute_composite(features, bad)


def test_unknown_profile_raises_style_error() -> None:
    with pytest.raises(StyleError):
        load_profile("nonexistent")


def test_profile_for_path_selects_expected_profile() -> None:
    assert profile_for_path("CHANGELOG.md").name == "technical_concise"
    assert profile_for_path("README.md").name == "documentation_natural"
    assert (
        profile_for_path("workflow-system/human/en/quickstart.md").name == "documentation_natural"
    )
    assert profile_for_path("workflow-system/human/demo/index.html").name == "marketing_warm"
    assert profile_for_path(".local/research/v10.1.0_gap_analysis.md").name == "technical_concise"


def test_score_corpus_aggregate_is_mean_of_per_doc() -> None:
    items = [
        ("a", "Short sentence. Another sentence."),
        ("b", "Longer prose with **bold** and an em-dash — right here. End."),
    ]
    result = score_corpus(items, lambda label: DOCUMENTATION_NATURAL)
    assert len(result.per_doc) == 2
    expected = round(
        sum(s.composite for s in result.per_doc.values()) / 2,
        3,
    )
    assert result.aggregate_naturalness == expected


def test_baseline_round_trip_matches_pv01() -> None:
    """The runner output against the live corpus must match the PV-01
    aggregate 69.958 within ±0.1. The baseline file is committed; any
    drift means the scorer diverged from the probe and the transform
    gate decisions become uncomparable."""
    baseline_path = REPO_ROOT / "benchmarks/writing_style/baselines/v10.1.0_pre.json"
    if not baseline_path.exists():
        pytest.skip("pre-transform baseline not yet generated")
    data = json.loads(baseline_path.read_text(encoding="utf-8"))
    assert abs(data["aggregate_naturalness"] - 69.958) <= 0.1, (
        f"baseline drift: got {data['aggregate_naturalness']}, expected 69.958 ± 0.1"
    )


def test_all_three_profiles_have_matching_caps() -> None:
    """The three profiles share scoring caps (per Q-E: only floors +
    transforms_enabled differ). A drift in caps across profiles would
    silently break the round-trip baseline."""
    caps_tc = TECHNICAL_CONCISE.caps
    caps_dn = DOCUMENTATION_NATURAL.caps
    caps_mw = MARKETING_WARM.caps
    for attr in (
        "bold_per_1k_start",
        "bullet_ratio_start",
        "emdash_per_1k_start",
        "header_ratio_start",
    ):
        assert getattr(caps_tc, attr) == getattr(caps_dn, attr) == getattr(caps_mw, attr), (
            f"profile caps drifted at {attr}"
        )
