"""Ghost audit — per-cycle W-18 feature stanzas for the v10.1 cycle.

Split from ``tests/test_no_ghost_features.py`` per v15-ADR-001
(v14.3.0). New W-18 stanzas for a v10.1.x release append HERE; the
next MINOR cycle rotates to a fresh ``test_features_v<MAJ>_<MIN>.py``.
"""

from __future__ import annotations

from pathlib import Path

_V10_1_0_WRITING_STYLE_MODULES: tuple[Path, ...] = (
    Path("src/devolaflow/writing_style/__init__.py"),
    Path("src/devolaflow/writing_style/errors.py"),
    Path("src/devolaflow/writing_style/profiles.py"),
    Path("src/devolaflow/writing_style/regions.py"),
    Path("src/devolaflow/writing_style/scorer.py"),
    Path("src/devolaflow/writing_style/transforms/__init__.py"),
    Path("src/devolaflow/writing_style/transforms/emdash.py"),
    Path("src/devolaflow/writing_style/transforms/bullets.py"),
    Path("src/devolaflow/writing_style/transforms/signposts.py"),
    Path("src/devolaflow/writing_style/transforms/headers.py"),
    Path("src/devolaflow/writing_style/transforms/cliches.py"),
    Path("src/devolaflow/writing_style/data/cliche_catalog.yaml"),
)


_V10_1_0_WRITING_STYLE_PUBLIC_SYMBOLS: frozenset[str] = frozenset(
    {
        "score_text",
        "score_corpus",
        "extract_features",
        "compute_composite",
        "apply_transforms",
        "load_profile",
        "profile_for_path",
        "NaturalnessScore",
        "RawFeatures",
        "CorpusScore",
        "ToneProfile",
        "FeatureCaps",
        "TransformResult",
        "StyleError",
    }
)


_V10_1_0_BASELINE_FILES: tuple[Path, ...] = (
    Path("benchmarks/writing_style/baselines/v10.1.0_pre.json"),
    Path("benchmarks/writing_style/baselines/v10.1.0_post.json"),
)


_V10_1_0_HUMANIZE_SCRIPT = Path("scripts/humanize_doc.py")


_V10_1_0_HUMANIZE_MAKE_TARGET = "humanize-docs:"


_V10_1_0_CHANGELOG_LITERAL = "## [10.1.0]"


def test_v10_1_0_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v10.1.0: every NEW v10.1.0 writing_style surface has presence
    coverage.

    Discharges the W-18 precondition for the v10.1.0 cycle-close MINOR.
    The CHANGELOG entry cites the writing_style package, the humanizer
    transforms, the CLI surface, the benchmark baselines, and the
    `make humanize-docs` target — each needs a presence assertion here
    before the CHANGELOG mention is valid.

    v10.1.0 pins:

    1. **writing_style package modules** — every module listed in
       `_V10_1_0_WRITING_STYLE_MODULES` must exist on disk.
    2. **writing_style public API** — every symbol in
       `_V10_1_0_WRITING_STYLE_PUBLIC_SYMBOLS` must be importable from
       the package (either defined in ``__init__.py`` or imported by it).
    3. **Benchmark baselines** — both `v10.1.0_pre.json` and
       `v10.1.0_post.json` must exist under
       `benchmarks/writing_style/baselines/`.
    4. **Humanize CLI** — `scripts/humanize_doc.py` exists.
    5. **Makefile target** — `humanize-docs:` target is defined.
    6. **CHANGELOG entry** — `## [10.1.0]` header is present.
    """
    for module_rel in _V10_1_0_WRITING_STYLE_MODULES:
        module_path = project_root / module_rel
        assert module_path.is_file(), (
            f"W-18 v10.1.0 violation: writing_style module {module_rel} "
            f"missing. v10.1.0 PV-02 / PV-03 ship this module; restore "
            "it or remove the CHANGELOG mention."
        )

    init_path = project_root / "src/devolaflow/writing_style/__init__.py"
    init_source = init_path.read_text(encoding="utf-8")
    for sym in _V10_1_0_WRITING_STYLE_PUBLIC_SYMBOLS:
        assert sym in init_source, (
            f"W-18 v10.1.0 violation: writing_style public symbol {sym!r} "
            "not exposed by __init__.py; the CHANGELOG documents the "
            "public API and cannot cite a missing surface."
        )

    for baseline_rel in _V10_1_0_BASELINE_FILES:
        baseline_path = project_root / baseline_rel
        assert baseline_path.is_file(), (
            f"W-18 v10.1.0 violation: benchmark baseline {baseline_rel} "
            "missing. v10.1.0 PV-02 / PV-05 commit these baselines; "
            "regenerate with `python -m benchmarks.writing_style.runner "
            "--corpus devolaflow --output <path>`."
        )

    humanize_path = project_root / _V10_1_0_HUMANIZE_SCRIPT
    assert humanize_path.is_file(), (
        f"W-18 v10.1.0 violation: humanize CLI "
        f"{_V10_1_0_HUMANIZE_SCRIPT} missing. v10.1.0 PV-04 ships this "
        "surface; restore it or remove the CHANGELOG mention."
    )

    makefile_path = project_root / "Makefile"
    makefile_text = makefile_path.read_text(encoding="utf-8")
    assert _V10_1_0_HUMANIZE_MAKE_TARGET in makefile_text, (
        f"W-18 v10.1.0 violation: Makefile target "
        f"{_V10_1_0_HUMANIZE_MAKE_TARGET!r} missing; v10.1.0 PV-04 "
        "ships this target."
    )

    changelog_path = project_root / "CHANGELOG.md"
    changelog_text = changelog_path.read_text(encoding="utf-8")
    assert _V10_1_0_CHANGELOG_LITERAL in changelog_text, (
        f"W-18 v10.1.0 violation: CHANGELOG entry "
        f"{_V10_1_0_CHANGELOG_LITERAL!r} missing; PV-06 ships this entry."
    )
