"""Ghost audit — per-cycle W-18 feature stanzas for the v12.4 cycle.

Split from ``tests/test_no_ghost_features.py`` per v15-ADR-001
(v14.3.0). New W-18 stanzas for a v12.4.x release append HERE; the
next MINOR cycle rotates to a fresh ``test_features_v<MAJ>_<MIN>.py``.
"""

from __future__ import annotations

import ast
from pathlib import Path

# ---------------------------------------------------------------------------
# v12.4.0 PV-02 W-18 ghost-audit refresh — tooling fixes (D-1).
# ---------------------------------------------------------------------------
#
# Per W-18 sequencing the ghost-audit refresh MUST land BEFORE the v12.4.0
# CHANGELOG entry mentioning the tooling fix items. This stanza pins
# the v12.4.0 PV-02 surface (closes v12.3.0 retrospective §6 items 2 + 3):
#
# * benchmarks/devolaflow_context/generate_baseline.py carries the literal
#   ``sys.modules["tiktoken"] = None`` at module-import scope (Option B
#   from tests/conftest.py docstring). Without this pin, standalone
#   baseline regens diverge from pytest scoring by ~7pp on composite
#   — see v12.3.0 retrospective §4.2 for the 3-attempt regen story.
# * scripts/realign_section_anchors.py exists with the documented
#   ``def realign_anchors(skill_md_path, profiles_yaml_path, *, dry_run=False)``
#   signature + CLI ``--dry-run`` / ``--apply`` flags. Closes v12.3.0
#   retrospective §4.3 (the ~15 min/cycle of manual context_profiles.yaml
#   section_anchors edits).
# * tests/test_generate_baseline_tiktoken_disabled.py exists and pins the
#   tiktoken-pin contract.
# * tests/test_realign_section_anchors.py exists and pins the realign
#   tool's idempotency + drift-detection + dry-run + S-5 contracts.
#
# Source: ``.local/research/v12.4.0_gap_analysis.md`` §2 D-1 +
# ``.local/research/v12.3.0_retrospective.md`` §§4.2 + 4.3 + 6.
# ---------------------------------------------------------------------------
_V12_4_0_GENERATE_BASELINE_FILE: Path = Path("benchmarks/devolaflow_context/generate_baseline.py")


_V12_4_0_TIKTOKEN_PIN_LITERAL: str = 'sys.modules["tiktoken"] = None'


_V12_4_0_REALIGN_SCRIPT: Path = Path("scripts/realign_section_anchors.py")


_V12_4_0_REALIGN_SIGNATURE_LITERAL: str = "def realign_anchors("


_V12_4_0_TIKTOKEN_TEST_FILE: Path = Path("tests/test_generate_baseline_tiktoken_disabled.py")


_V12_4_0_REALIGN_TEST_FILE: Path = Path("tests/test_realign_section_anchors.py")


def test_v12_4_0_tooling_fixes(project_root: Path) -> None:
    """W-18 v12.4.0 PV-02 D-1: tooling fixes from v12.3.0 retro §6 items 2 + 3.

    Discharges the W-18 precondition for the v12.4.0 CHANGELOG entry
    mentioning the two tooling fixes:

    * ``benchmarks/devolaflow_context/generate_baseline.py`` pins
      ``sys.modules["tiktoken"] = None`` at module top so standalone
      regens match pytest scoring (closes v12.3.0 retro §4.2).
    * ``scripts/realign_section_anchors.py`` exists and exposes the
      documented ``realign_anchors(...)`` signature so per-cycle
      section-anchor edits become a 1-command operation (closes
      v12.3.0 retro §4.3).

    Plus the two NEW test files MUST exist:

    * ``tests/test_generate_baseline_tiktoken_disabled.py`` pins the
      tiktoken-pin contract (PV-02 owned-files manifest item 3).
    * ``tests/test_realign_section_anchors.py`` pins the realign tool
      idempotency + drift-detection contracts (PV-02 owned-files
      manifest item 4).

    Source: ``.local/research/v12.4.0_gap_analysis.md`` §2 D-1.
    """
    generate_baseline_path = project_root / _V12_4_0_GENERATE_BASELINE_FILE
    assert generate_baseline_path.is_file(), (
        f"W-18 v12.4.0 PV-02 violation: {_V12_4_0_GENERATE_BASELINE_FILE} "
        "missing — release blocker. The tiktoken pin lives at module top of "
        "this file per the PV-02 owned-files manifest item 1."
    )
    generate_baseline_text = generate_baseline_path.read_text(encoding="utf-8")
    assert _V12_4_0_TIKTOKEN_PIN_LITERAL in generate_baseline_text, (
        f"W-18 v12.4.0 PV-02 violation: {_V12_4_0_GENERATE_BASELINE_FILE} "
        f"missing literal {_V12_4_0_TIKTOKEN_PIN_LITERAL!r}. The pin MUST land "
        "at module-import scope before any devolaflow/benchmarks import — "
        "without it, standalone regens diverge from pytest scoring by ~7pp on "
        "composite per v12.3.0 retrospective §4.2."
    )
    # Cross-check: docstring credits the v12.3.0 retro learning so future
    # readers can trace the design rationale.
    assert "v12.3.0 retro" in generate_baseline_text, (
        f"W-18 v12.4.0 PV-02 violation: {_V12_4_0_GENERATE_BASELINE_FILE} "
        "must credit ``v12.3.0 retro`` in its docstring per the PV-02 "
        "owned-files manifest. The docstring is the source-of-truth "
        "explanation for the Option B pin."
    )

    realign_script_path = project_root / _V12_4_0_REALIGN_SCRIPT
    assert realign_script_path.is_file(), (
        f"W-18 v12.4.0 PV-02 violation: {_V12_4_0_REALIGN_SCRIPT} missing — "
        "release blocker. The realign tool MUST exist with the documented "
        "signature per the PV-02 owned-files manifest item 2."
    )
    realign_text = realign_script_path.read_text(encoding="utf-8")
    assert _V12_4_0_REALIGN_SIGNATURE_LITERAL in realign_text, (
        f"W-18 v12.4.0 PV-02 violation: {_V12_4_0_REALIGN_SCRIPT} missing "
        f"literal {_V12_4_0_REALIGN_SIGNATURE_LITERAL!r}. The documented public "
        "signature is ``realign_anchors(skill_md_path, profiles_yaml_path, "
        "*, dry_run=False)``."
    )
    # CLI flags MUST be present per the PV-02 spec (--dry-run / --apply).
    assert "--dry-run" in realign_text, (
        f"W-18 v12.4.0 PV-02 violation: {_V12_4_0_REALIGN_SCRIPT} missing "
        "``--dry-run`` CLI flag. The CLI smoke test (PV-02 acceptance criterion 6) "
        "depends on this flag."
    )
    assert "--apply" in realign_text, (
        f"W-18 v12.4.0 PV-02 violation: {_V12_4_0_REALIGN_SCRIPT} missing "
        "``--apply`` CLI flag. The operator opts-in to mutation via --apply; "
        "default-OFF dry-run is the safety contract."
    )

    tiktoken_test_path = project_root / _V12_4_0_TIKTOKEN_TEST_FILE
    assert tiktoken_test_path.is_file(), (
        f"W-18 v12.4.0 PV-02 violation: {_V12_4_0_TIKTOKEN_TEST_FILE} missing — "
        "release blocker. The 3-test contract for the generate_baseline "
        "tiktoken pin MUST exist per PV-02 owned-files manifest item 3."
    )
    tiktoken_test_text = tiktoken_test_path.read_text(encoding="utf-8")
    for expected_test in (
        "test_tiktoken_disabled_at_import",
        "test_baseline_regen_deterministic",
        "test_no_regression_vs_pytest",
    ):
        assert f"def {expected_test}" in tiktoken_test_text, (
            f"W-18 v12.4.0 PV-02 violation: {_V12_4_0_TIKTOKEN_TEST_FILE} "
            f"missing test function ``{expected_test}``. The 3-test contract "
            "is documented in the PV-02 owned-files manifest item 3."
        )

    realign_test_path = project_root / _V12_4_0_REALIGN_TEST_FILE
    assert realign_test_path.is_file(), (
        f"W-18 v12.4.0 PV-02 violation: {_V12_4_0_REALIGN_TEST_FILE} missing — "
        "release blocker. The 5-test contract for the realign tool MUST exist "
        "per PV-02 owned-files manifest item 4."
    )
    realign_test_text = realign_test_path.read_text(encoding="utf-8")
    for expected_test in (
        "test_header_parse_correctness",
        "test_idempotent_apply",
        "test_drift_detection_proposes_correct_realignment",
        "test_dry_run_does_not_modify_file",
        "test_missing_input_raises_friendly_error",
    ):
        assert f"def {expected_test}" in realign_test_text, (
            f"W-18 v12.4.0 PV-02 violation: {_V12_4_0_REALIGN_TEST_FILE} "
            f"missing test function ``{expected_test}``. The 5-test contract "
            "is documented in the PV-02 owned-files manifest item 4."
        )


# ---------------------------------------------------------------------------
# W-18 stanza for v12.4.0 PV-03 D-2 — ``evaluate_gate`` helper extraction
# ---------------------------------------------------------------------------
#
# Per W-18 sequencing the ghost-audit refresh MUST land BEFORE the v12.4.0
# CHANGELOG entry mentioning the PV-03 cc-spike refactor. This stanza pins
# the v12.4.0 PV-03 surface (closes v12.3.0 retrospective §3 D-4 item 1):
#
# * src/devolaflow/gate/scorer.py declares all four ``_apply_*`` helpers
#   extracted from the original ``evaluate_gate`` body (cc=22 → cc=7):
#   ``_apply_breaker_check`` (cc=3), ``_apply_cycle_detection`` (cc=3),
#   ``_apply_ratchet`` (cc=2), ``_apply_complexity_and_legibility`` (cc=5).
#   Each helper is module-scope (``def`` prefixed) so static AST walkers
#   like the cc-pin test file can locate them.
# * src/devolaflow/gate/scorer.py keeps the ``evaluate_gate`` public
#   signature byte-identical to the pre-refactor form documented at
#   ``.local/research/v12.4.0_gap_analysis.md`` §2 D-2. The CO-2 / C-3
#   no-API-break invariant is what allows the 101 ``tests/test_gate.py``
#   callers + the 36 ``tests/test_benchmarks.py`` scenarios + downstream
#   consumers (W-3 SI-3 harness, PV-06 self-eval) to keep working without
#   modification.
# * tests/test_evaluate_gate_complexity.py exists and pins the per-symbol
#   cc ceilings via stdlib ``ast`` walker (no ``radon`` dev-dep added).
#
# Source: ``.local/research/v12.4.0_gap_analysis.md`` §2 D-2 +
# ``.cursor/plans/v12.4.0_expansion_refactor_cycle_240b72f0.plan.md``
# §3 PV-03 + ``.local/research/v12.4.0_nines_deep_evaluate_gate.json``
# finding ``CC-67079a-0000``.
# ---------------------------------------------------------------------------
_V12_4_0_SCORER_FILE: Path = Path("src/devolaflow/gate/scorer.py")


_V12_4_0_COMPLEXITY_TEST_FILE: Path = Path("tests/test_evaluate_gate_complexity.py")


_V12_4_0_EVALUATE_GATE_HELPERS: tuple[str, ...] = (
    "_apply_breaker_check",
    "_apply_cycle_detection",
    "_apply_ratchet",
    "_apply_complexity_and_legibility",
)


# The CO-2 / C-3 byte-identical public signature for ``evaluate_gate``.
# Must match the literal string in
# ``tests/test_evaluate_gate_complexity.py::_EVALUATE_GATE_SIGNATURE``
# verbatim — the two pins reference the same source-of-truth surface.
# v15.0.0 R1 (additive per this pin's own append rule below): the
# ``artifact_evidence`` opt-in parameter is APPENDED after
# ``legibility_files`` with a ``None`` default (v15-ADR-007 gate
# wiring); the 15 pre-existing parameter lines stay byte-identical.
_V12_4_0_EVALUATE_GATE_SIGNATURE_LITERAL: str = (
    "def evaluate_gate(\n"
    "    gate_input: GateInput,\n"
    "    profile: GateProfile,\n"
    "    round_num: int = 1,\n"
    "    history: list[ConvergenceRound] | None = None,\n"
    '    gate_type: str = "standard",\n'
    "    breaker: TokenBudgetBreaker | None = None,\n"
    "    cumulative_tokens: int | None = None,\n"
    "    cycle_detector: CycleDetector | None = None,\n"
    "    ratchet: MonotonicRatchet | None = None,\n"
    "    ratchet_artifact: dict[str, object] | None = None,\n"
    "    complexity_detector: ComplexityDetector | None = None,\n"
    "    complexity_signals: ComplexitySignals | None = None,\n"
    '    complexity_task_complexity: str = "standard",\n'
    "    legibility_scorer: LegibilityScorer | None = None,\n"
    "    legibility_files: Sequence[str] | None = None,\n"
    "    artifact_evidence: Sequence[dict] | None = None,\n"
    ") -> GateVerdict:"
)


def test_v12_4_0_evaluate_gate_refactor(project_root: Path) -> None:
    """W-18 v12.4.0 PV-03 D-2: ``evaluate_gate`` cc=22 → cc=7 helper extraction.

    Discharges the W-18 precondition for the v12.4.0 CHANGELOG entry
    mentioning the PV-03 cc-spike refactor of ``evaluate_gate``. The
    stanza asserts three load-bearing surfaces:

    (a) Every ``_apply_*`` helper symbol is present in
    ``src/devolaflow/gate/scorer.py`` at module scope (one ``def`` per
    helper). Without these four symbols the cc reduction did NOT happen
    and the CHANGELOG entry would be a ghost feature per S-4.

    (b) The public signature of ``evaluate_gate`` is byte-identical to
    the pre-refactor form. The CO-2 / C-3 no-API-break invariant pins
    the entire pinned parameter list verbatim (whitespace included;
    v15.0.0 R1 appended ``artifact_evidence`` per the additive rule).
    Any reorder / rename / default-change is a release blocker that
    would break all 101 ``tests/test_gate.py`` callers + the 36
    ``tests/test_benchmarks.py`` scenarios + downstream W-3 SI-3 harness.

    (c) The companion test file ``tests/test_evaluate_gate_complexity.py``
    exists with the three cc-pin tests (the orchestrator cc ≤ 10 pin,
    the per-helper cc ≤ 8 parametrize, and the signature byte-identical
    literal match). The companion file is what catches a future PV
    re-bloating the orchestrator body — without it the W-18 / W-4 / SI-4
    safety net has a hole.

    Source: ``.local/research/v12.4.0_gap_analysis.md`` §2 D-2 +
    ``.cursor/plans/v12.4.0_expansion_refactor_cycle_240b72f0.plan.md``
    §3 PV-03; the W-18 sequencing rule is at
    ``.cursor/rules/repo-governance.mdc`` §W-18.
    """
    scorer_path = project_root / _V12_4_0_SCORER_FILE
    assert scorer_path.is_file(), (
        f"W-18 v12.4.0 PV-03 violation: {_V12_4_0_SCORER_FILE} missing — "
        "release blocker. The refactor MUST land in the canonical scorer "
        "module per the PV-03 owned-files manifest item 1."
    )
    scorer_text = scorer_path.read_text(encoding="utf-8")

    # (a) — each ``_apply_*`` helper must be present at module scope.
    for helper_name in _V12_4_0_EVALUATE_GATE_HELPERS:
        signature_literal = f"def {helper_name}("
        assert signature_literal in scorer_text, (
            f"W-18 v12.4.0 PV-03 violation: {_V12_4_0_SCORER_FILE} missing "
            f"helper function ``{helper_name}``. The 4-helper decomposition "
            "is what brings ``evaluate_gate`` cc from 22 to 7; if this "
            "assertion fires, the refactor was either reverted or never "
            "applied. The expected helper signatures are documented at "
            "``.local/research/v12.4.0_gap_analysis.md`` §2 D-2."
        )

    # (b) — public signature of ``evaluate_gate`` must be byte-identical.
    assert _V12_4_0_EVALUATE_GATE_SIGNATURE_LITERAL in scorer_text, (
        f"W-18 v12.4.0 PV-03 violation: {_V12_4_0_SCORER_FILE} has drifted "
        "the public ``evaluate_gate`` signature from the pre-refactor form. "
        "The CO-2 / C-3 no-API-break invariant requires byte-identical "
        "preservation of the entire pinned parameter list. Expected "
        f"literal:\n\n{_V12_4_0_EVALUATE_GATE_SIGNATURE_LITERAL}\n\n"
        "If a future PV needs to ADD a parameter, append it after "
        "``legibility_files`` with a default value (additive change) — "
        "do NOT reorder existing parameters or change defaults."
    )

    # (c) — companion cc-pin test file MUST exist.
    complexity_test_path = project_root / _V12_4_0_COMPLEXITY_TEST_FILE
    assert complexity_test_path.is_file(), (
        f"W-18 v12.4.0 PV-03 violation: {_V12_4_0_COMPLEXITY_TEST_FILE} "
        "missing — release blocker. The companion cc-pin test file "
        "guards against future re-bloat of ``evaluate_gate`` per the "
        "PV-03 owned-files manifest item 3."
    )
    complexity_test_text = complexity_test_path.read_text(encoding="utf-8")
    for expected_test in (
        "test_evaluate_gate_cc_under_ceiling",
        "test_evaluate_gate_helpers_cc_under_ceiling",
        "test_evaluate_gate_signature_byte_identical",
    ):
        assert f"def {expected_test}" in complexity_test_text, (
            f"W-18 v12.4.0 PV-03 violation: {_V12_4_0_COMPLEXITY_TEST_FILE} "
            f"missing test function ``{expected_test}``. The 3-test contract "
            "is documented in the PV-03 owned-files manifest item 3."
        )


# ---------------------------------------------------------------------------
# W-18 stanza for v12.4.0 PV-04 D-3 — cc-spike refactor pair
# (``build_mapping_from_dict`` cc=21 + ``_collapse_block`` cc=25)
# ---------------------------------------------------------------------------
#
# Per W-18 sequencing the ghost-audit refresh MUST land BEFORE the v12.4.0
# CHANGELOG entry mentioning the PV-04 cc-spike refactor pair. This stanza
# pins the v12.4.0 PV-04 surface (closes v12.3.0 retrospective §3 D-4
# items 2 + 3 paired):
#
# * src/devolaflow/shell_proxy/commands.py declares all four ``_validate_*``
#   / ``_build_*`` helpers extracted from the original
#   ``build_mapping_from_dict`` body (cc=21 → cc=9):
#   ``_validate_schema_version`` (cc=4), ``_validate_scalar_fields`` (cc=6),
#   ``_validate_tags`` (cc=2), ``_build_filter_lists`` (cc=5). Each helper
#   is module-scope so the static AST walker in the cc-pin test file can
#   locate them.
# * src/devolaflow/shell_proxy/commands.py keeps the
#   ``build_mapping_from_dict`` public signature byte-identical to the
#   pre-refactor form. The CO-2 / C-3 no-API-break invariant is what
#   allows the 68 ``tests/test_shell_proxy_commands.py`` callers + the
#   loader + the apply_local_recipe layer to keep working without
#   modification.
# * src/devolaflow/writing_style/transforms/bullets.py declares all four
#   helpers extracted from the original ``_collapse_block`` body (cc=25 →
#   cc=6): ``_classify_block_lines`` (cc=7), ``_validate_bullet_constraints``
#   (cc=6), ``_collapse_no_intro`` (cc=2), ``_collapse_with_intro`` (cc=4).
# * src/devolaflow/writing_style/transforms/bullets.py keeps the
#   ``_collapse_block`` private signature byte-identical to the
#   pre-refactor form so the 27 ``tests/test_writing_style_*`` fixture
#   corpus tests keep working without modification.
# * tests/test_v12_4_0_complexity_targets.py exists and pins both
#   per-symbol cc ceilings via stdlib ``ast`` walker (no ``radon``
#   dev-dep added) AND carries a cross-PV regression guard for the
#   PV-03 ``evaluate_gate`` cc=7 invariant.
#
# Source: ``.local/research/v12.4.0_gap_analysis.md`` §2 D-3 +
# ``.local/research/v12.4.0_nines_deep_commands.json`` (finding for
# ``build_mapping_from_dict`` cc=21) +
# ``.local/research/v12.4.0_nines_deep_bullets.json`` (finding for
# ``_collapse_block`` cc=25).
# ---------------------------------------------------------------------------
_V12_4_0_COMMANDS_FILE: Path = Path("src/devolaflow/shell_proxy/commands.py")


_V12_4_0_BULLETS_FILE: Path = Path("src/devolaflow/writing_style/transforms/bullets.py")


_V12_4_0_BUILD_MAPPING_HELPERS: tuple[str, ...] = (
    "_validate_schema_version",
    "_validate_scalar_fields",
    "_validate_tags",
    "_build_filter_lists",
)


_V12_4_0_COLLAPSE_BLOCK_HELPERS: tuple[str, ...] = (
    "_classify_block_lines",
    "_validate_bullet_constraints",
    "_collapse_no_intro",
    "_collapse_with_intro",
)


# Byte-identical public signature of ``build_mapping_from_dict`` per
# the v12.4.0 PV-04 D-3 acceptance criterion (4) — must match the
# literal in ``tests/test_v12_4_0_complexity_targets.py::_BUILD_MAPPING_SIGNATURE``
# verbatim. The two pins reference the same source-of-truth surface.
_V12_4_0_BUILD_MAPPING_SIGNATURE_LITERAL: str = (
    "def build_mapping_from_dict(\n"
    "    payload: Any,\n"
    "    *,\n"
    '    source_path: str = "<command-mapping.yaml>",\n'
    '    recipe_id: str = "",\n'
    ") -> CommandMapping:"
)


# Byte-identical private signature of ``_collapse_block`` — the
# orchestrator inside ``bullets.py`` is module-private but stable.
_V12_4_0_COLLAPSE_BLOCK_SIGNATURE_LITERAL: str = (
    "def _collapse_block(lines: list[str]) -> list[str]:"
)


def test_v12_4_0_complexity_sweep_complete(project_root: Path) -> None:
    """W-18 v12.4.0 PV-04 D-3: ``build_mapping_from_dict`` cc=21 + ``_collapse_block`` cc=25 → ≤ 10.

    Discharges the W-18 precondition for the v12.4.0 CHANGELOG entry
    mentioning the PV-04 cc-spike refactor pair. The stanza asserts
    three load-bearing surfaces (mirroring the PV-03 stanza pattern):

    (a) Every helper symbol is present at module scope in
    ``src/devolaflow/shell_proxy/commands.py`` (4 ``_validate_*`` /
    ``_build_*`` helpers) and
    ``src/devolaflow/writing_style/transforms/bullets.py`` (4 helpers).
    Without these 8 symbols the cc reduction did NOT happen and the
    CHANGELOG entry would be a ghost feature per S-4.

    (b) Both public signatures are byte-identical to the pre-refactor
    forms. The CO-2 / C-3 no-API-break invariant pins:
      * ``def build_mapping_from_dict(payload, *, source_path, recipe_id) -> CommandMapping:``
        (consumed by the loader + 68 commands tests + apply_local_recipe)
      * ``def _collapse_block(lines: list[str]) -> list[str]:``
        (consumed by ``_transform_prose`` + the 27 writing_style fixture tests)
    Any reorder / rename / default-change is a release blocker.

    (c) The companion test file
    ``tests/test_v12_4_0_complexity_targets.py`` exists with the cc-pin
    tests (orchestrator ≤ cc=10 per target, per-helper ≤ cc=8
    parametrize, signature byte-identical literal match for both
    targets, and the cross-PV regression guard for ``evaluate_gate``).
    The companion file is what catches a future PV re-bloating any of
    the 3 targeted orchestrators — without it the W-18 / W-4 / SI-4
    safety net has a hole.

    Source: ``.local/research/v12.4.0_gap_analysis.md`` §2 D-3 +
    ``.local/research/v12.4.0_nines_deep_commands.json`` (finding for
    ``build_mapping_from_dict`` cc=21) +
    ``.local/research/v12.4.0_nines_deep_bullets.json`` (finding for
    ``_collapse_block`` cc=25); the W-18 sequencing rule is at
    ``.cursor/rules/repo-governance.mdc`` §W-18.
    """
    # --- (a.1) build_mapping_from_dict helpers in commands.py ----------
    commands_path = project_root / _V12_4_0_COMMANDS_FILE
    assert commands_path.is_file(), (
        f"W-18 v12.4.0 PV-04 violation: {_V12_4_0_COMMANDS_FILE} missing — "
        "release blocker. The refactor MUST land in the canonical commands "
        "module per the PV-04 owned-files manifest item 1."
    )
    commands_text = commands_path.read_text(encoding="utf-8")
    for helper_name in _V12_4_0_BUILD_MAPPING_HELPERS:
        signature_literal = f"def {helper_name}("
        assert signature_literal in commands_text, (
            f"W-18 v12.4.0 PV-04 violation: {_V12_4_0_COMMANDS_FILE} missing "
            f"helper function ``{helper_name}``. The 4-helper decomposition "
            "is what brings ``build_mapping_from_dict`` cc from 21 to 9; "
            "if this assertion fires, the refactor was either reverted or "
            "never applied. Expected helper signatures are documented at "
            "``.local/research/v12.4.0_gap_analysis.md`` §2 D-3."
        )

    # --- (a.2) _collapse_block helpers in bullets.py -------------------
    bullets_path = project_root / _V12_4_0_BULLETS_FILE
    assert bullets_path.is_file(), (
        f"W-18 v12.4.0 PV-04 violation: {_V12_4_0_BULLETS_FILE} missing — "
        "release blocker. The refactor MUST land in the canonical bullets "
        "transform module per the PV-04 owned-files manifest item 2."
    )
    bullets_text = bullets_path.read_text(encoding="utf-8")
    for helper_name in _V12_4_0_COLLAPSE_BLOCK_HELPERS:
        signature_literal = f"def {helper_name}("
        assert signature_literal in bullets_text, (
            f"W-18 v12.4.0 PV-04 violation: {_V12_4_0_BULLETS_FILE} missing "
            f"helper function ``{helper_name}``. The 4-helper decomposition "
            "is what brings ``_collapse_block`` cc from 25 to 6; if this "
            "assertion fires, the refactor was either reverted or never "
            "applied. Expected helper signatures are documented at "
            "``.local/research/v12.4.0_gap_analysis.md`` §2 D-3."
        )

    # --- (b.1) build_mapping_from_dict public signature byte-identical -
    assert _V12_4_0_BUILD_MAPPING_SIGNATURE_LITERAL in commands_text, (
        f"W-18 v12.4.0 PV-04 violation: {_V12_4_0_COMMANDS_FILE} has drifted "
        "the public ``build_mapping_from_dict`` signature from the "
        "pre-refactor form. The CO-2 / C-3 no-API-break invariant requires "
        "byte-identical preservation of the entire signature. Expected "
        f"literal:\n\n{_V12_4_0_BUILD_MAPPING_SIGNATURE_LITERAL}\n\n"
        "If a future PV needs to ADD a parameter, append it after "
        "``recipe_id`` with a default value (additive change) — do NOT "
        "reorder existing parameters or change defaults."
    )

    # --- (b.2) _collapse_block private signature byte-identical --------
    assert _V12_4_0_COLLAPSE_BLOCK_SIGNATURE_LITERAL in bullets_text, (
        f"W-18 v12.4.0 PV-04 violation: {_V12_4_0_BULLETS_FILE} has drifted "
        "the ``_collapse_block`` signature from the pre-refactor form. "
        "Per CO-2 / C-3 the in-module orchestrator's signature MUST stay "
        "byte-identical so ``_transform_prose`` + the 27 fixture-corpus "
        f"tests keep working. Expected literal:\n\n"
        f"{_V12_4_0_COLLAPSE_BLOCK_SIGNATURE_LITERAL}"
    )

    # --- (c) companion cc-pin test file -------------------------------
    pv04_complexity_test_path = project_root / Path("tests/test_v12_4_0_complexity_targets.py")
    assert pv04_complexity_test_path.is_file(), (
        "W-18 v12.4.0 PV-04 violation: tests/test_v12_4_0_complexity_targets.py "
        "missing — release blocker. The companion cc-pin test file guards "
        "against future re-bloat of ``build_mapping_from_dict``, "
        "``_collapse_block``, AND ``evaluate_gate`` (cross-PV regression "
        "guard) per the PV-04 owned-files manifest item 5."
    )
    pv04_complexity_test_text = pv04_complexity_test_path.read_text(encoding="utf-8")
    for expected_test in (
        "test_build_mapping_from_dict_cc_under_ceiling",
        "test_build_mapping_helpers_cc_under_ceiling",
        "test_build_mapping_from_dict_signature_byte_identical",
        "test_collapse_block_cc_under_ceiling",
        "test_collapse_block_helpers_cc_under_ceiling",
        "test_collapse_block_signature_byte_identical",
        "test_evaluate_gate_cc_under_ceiling_v12_4_0_pv04_regression_guard",
    ):
        assert f"def {expected_test}" in pv04_complexity_test_text, (
            f"W-18 v12.4.0 PV-04 violation: "
            f"tests/test_v12_4_0_complexity_targets.py missing test function "
            f"``{expected_test}``. The 7-function contract (3 for "
            "build_mapping_from_dict + 3 for _collapse_block + 1 cross-PV "
            "regression guard for evaluate_gate) is documented in the PV-04 "
            "owned-files manifest item 5."
        )


# ---------------------------------------------------------------------------
# W-18 stanza for v12.4.0 PV-05 D-4 — L0-only surfaces hardening
# ---------------------------------------------------------------------------
#
# Per W-18 sequencing the ghost-audit refresh MUST land BEFORE the v12.4.0
# CHANGELOG entry mentioning the PV-05 L0-only surfaces leak cluster. This
# stanza pins the v12.4.0 PV-05 surface (closes the 派发分层 user-feedback
# theme from .local/feedbacks/feedback_for_v12.1.1.md):
#
# * NEW lifecycle hook ``src/devolaflow/lifecycle/reject_subagent_banner_emission.py``
#   exists with the canonical EVENT constant + the
#   ``reject_subagent_banner_emission`` handler symbol + the opt-in
#   ``register_pre_dispatch_extra`` helper. The hook is OPT-IN only — NOT
#   auto-wired in lifecycle/__init__.py — preserving the S-10 byte-id
#   contract for v12.3.0 callers.
# * SKILL.md §"Session Banner Contract (v12.3.0+)" carries the NEW PV-05
#   prohibition line citing ``reject_subagent_banner_emission`` (verbatim
#   substring).
# * references/agent-workspace.md carries the NEW §"Handoff Envelope L0-only
#   Metadata Stripping" subsection documenting the 4 literal classes the
#   handoff writer MUST strip (banner workflow-start + banner workflow-end
#   + 📊 footer + operational_learnings session-pinned literals).
# * tests/test_l0_only_section_priorities.py exists pinning the 3-section ×
#   24-profile audit verdict (task_quality_score: skip everywhere,
#   operational_learnings: skip everywhere, version_update: skip everywhere
#   except self_update: critical).
# * tests/test_lifecycle_reject_subagent_banner_emission.py exists with the
#   ≥ 8 hook tests covering permissive default + strict mode + non-target-
#   layer skip + opt-in registration + literal detection + defensive
#   non-dict + nested-banner-exclusion + S-10 default-events preservation.
#
# Source: ``.local/research/v12.4.0_gap_analysis.md`` §2 D-4 +
# ``.local/research/v12.4.0_l0_only_audit.md`` §§A-C (per-profile audit
# table + literal enumeration + token-savings estimate) +
# ``.local/feedbacks/feedback_for_v12.1.1.md`` themes 打分体系 + 版本模块 +
# 派发分层.
# ---------------------------------------------------------------------------
_V12_4_0_PV05_HOOK_FILE: Path = Path("src/devolaflow/lifecycle/reject_subagent_banner_emission.py")


_V12_4_0_PV05_HOOK_TEST_FILE: Path = Path("tests/test_lifecycle_reject_subagent_banner_emission.py")


_V12_4_0_PV05_PRIORITIES_TEST_FILE: Path = Path("tests/test_l0_only_section_priorities.py")


_V12_4_0_PV05_SKILL_FILE: Path = Path("workflow-system/agent/SKILL.md")


_V12_4_0_PV05_AGENT_WORKSPACE_FILE: Path = Path(
    "workflow-system/agent/references/agent-workspace.md"
)


_V12_4_0_PV05_CONTEXT_PROFILES_FILE: Path = Path("workflow-system/agent/context_profiles.yaml")


_V12_4_0_PV05_SKILL_PROHIBITION_LITERAL: str = (
    "Subagent (L1/L2/L3) reports MUST NOT include banner lines — see "
    "PV-05 runtime hook `reject_subagent_banner_emission`. Banners are "
    "L0-only operator chat output."
)


_V12_4_0_PV05_AGENT_WORKSPACE_HEADING: str = (
    "### Handoff Envelope L0-only Metadata Stripping (v12.4.0 PV-05)"
)


_V12_4_0_PV05_AGENT_WORKSPACE_CROSS_LINK: str = "`reject_subagent_banner_emission`"


_V12_4_0_PV05_HOOK_MIN_TESTS: int = 8


def test_v12_4_0_l0_only_surfaces_hardened(project_root: Path) -> None:
    """W-18 v12.4.0 PV-05 D-4: L0-only surfaces leak cluster hardening.

    Discharges the W-18 precondition for the v12.4.0 CHANGELOG entry
    mentioning the PV-05 L0-only surfaces hardening. The stanza
    asserts four load-bearing surfaces:

    (a) NEW lifecycle hook module
    ``src/devolaflow/lifecycle/reject_subagent_banner_emission.py``
    exists with the canonical EVENT constant + the
    ``reject_subagent_banner_emission`` handler symbol + the opt-in
    ``register_pre_dispatch_extra`` helper. Without these symbols
    the CHANGELOG entry would be a ghost feature per S-4.

    (b) SKILL.md §"Session Banner Contract" carries the NEW PV-05
    prohibition line citing the runtime hook by name (verbatim
    substring match). Without this line, the CHANGELOG entry's
    operator-facing reinforcement is unbacked.

    (c) references/agent-workspace.md carries the NEW
    §"Handoff Envelope L0-only Metadata Stripping" subsection +
    cross-link to the runtime hook. Without this subsection, the
    handoff-writer normative obligation is undocumented.

    (d) The companion test files
    ``tests/test_l0_only_section_priorities.py`` (5 tests pinning
    the 3-section × 24-profile audit verdict) and
    ``tests/test_lifecycle_reject_subagent_banner_emission.py`` (≥ 8
    tests covering hook permissive/strict + wiring + edge cases)
    BOTH exist with the required test-function counts. Without these
    files the W-18 / W-9 SI-10 safety net has a hole.

    Source: ``.local/research/v12.4.0_gap_analysis.md`` §2 D-4 +
    ``.local/research/v12.4.0_l0_only_audit.md`` §§A-C +
    ``.local/feedbacks/feedback_for_v12.1.1.md`` (派发分层 theme).
    """
    # --- (a.1) Lifecycle hook module exists --------------------------
    hook_path = project_root / _V12_4_0_PV05_HOOK_FILE
    assert hook_path.is_file(), (
        f"W-18 v12.4.0 PV-05 violation: {_V12_4_0_PV05_HOOK_FILE} "
        "missing — release blocker. The PV-05 hook implementation MUST "
        "land per the PV-05 owned-files manifest Surface 5.2."
    )
    hook_text = hook_path.read_text(encoding="utf-8")
    assert 'EVENT = "pre_dispatch"' in hook_text, (
        f"W-18 v12.4.0 PV-05 violation: {_V12_4_0_PV05_HOOK_FILE} "
        'missing the canonical `EVENT = "pre_dispatch"` constant.'
    )
    assert "def reject_subagent_banner_emission(" in hook_text, (
        f"W-18 v12.4.0 PV-05 violation: {_V12_4_0_PV05_HOOK_FILE} "
        "missing the canonical `reject_subagent_banner_emission` "
        "function definition."
    )
    assert "def register_pre_dispatch_extra(" in hook_text, (
        f"W-18 v12.4.0 PV-05 violation: {_V12_4_0_PV05_HOOK_FILE} "
        "missing the opt-in `register_pre_dispatch_extra` helper. The "
        "PV-05 contract is OPT-IN registration to preserve the S-10 "
        "byte-id contract for v12.3.0 callers — without this helper "
        "operators have no way to wire the hook at runtime."
    )

    # --- (a.2) v15.0.0 G-038 flip 3 default wiring --------------------
    # The v12.4.0 PV-05 contract pinned the hook as OPT-IN only ("MUST
    # NOT be auto-wired") to preserve the S-10 byte-id default for
    # v12.3.0 callers. That default graduated at v15.0.0 (G-038 flip 3,
    # DEFAULTS-PERMISSIVE-IN-MINOR / STRICT-IN-NEXT-MAJOR): the hook IS
    # now auto-wired in lifecycle/__init__.py, mirroring the v12.2.0
    # PV-04 quality-score extra. The hook never mutates the payload, so
    # the S-10 byte-identical DISPATCH contract still holds (pinned by
    # tests/test_dispatch_emission_runs_hooks.py). Documented opt-out:
    # `unregister_pre_dispatch_extra()`.
    init_path = project_root / Path("src/devolaflow/lifecycle/__init__.py")
    init_text = init_path.read_text(encoding="utf-8")
    assert "register_hook(_PRE_DISPATCH_EVENT, reject_subagent_banner_emission)" in init_text, (
        "v15.0.0 G-038 flip 3 violation: `reject_subagent_banner_emission` "
        "MUST be default-wired in lifecycle/__init__.py since v15.0.0 "
        "(graduating the v12.4.0 PV-05 opt-in). Opt-out is "
        "`unregister_pre_dispatch_extra()`, NOT removal of the wiring."
    )

    # --- (b) SKILL.md prohibition line -------------------------------
    skill_path = project_root / _V12_4_0_PV05_SKILL_FILE
    skill_text = skill_path.read_text(encoding="utf-8")
    assert _V12_4_0_PV05_SKILL_PROHIBITION_LITERAL in skill_text, (
        f"W-18 v12.4.0 PV-05 violation: {_V12_4_0_PV05_SKILL_FILE} "
        "missing the §'Session Banner Contract' prohibition line. "
        f"Expected verbatim substring:\n\n"
        f"{_V12_4_0_PV05_SKILL_PROHIBITION_LITERAL}\n\n"
        "Without this line the operator-facing reinforcement of the "
        "PV-05 runtime hook is unbacked."
    )

    # --- (c.1) agent-workspace.md new subsection heading -------------
    agent_workspace_path = project_root / _V12_4_0_PV05_AGENT_WORKSPACE_FILE
    agent_workspace_text = agent_workspace_path.read_text(encoding="utf-8")
    assert _V12_4_0_PV05_AGENT_WORKSPACE_HEADING in agent_workspace_text, (
        f"W-18 v12.4.0 PV-05 violation: {_V12_4_0_PV05_AGENT_WORKSPACE_FILE} "
        "missing the §'Handoff Envelope L0-only Metadata Stripping' "
        "subsection heading. Expected verbatim heading:\n\n"
        f"{_V12_4_0_PV05_AGENT_WORKSPACE_HEADING}\n\n"
        "Without this subsection the handoff-writer normative "
        "obligation is undocumented."
    )

    # --- (c.2) agent-workspace.md cross-link to runtime hook ---------
    assert _V12_4_0_PV05_AGENT_WORKSPACE_CROSS_LINK in agent_workspace_text, (
        f"W-18 v12.4.0 PV-05 violation: {_V12_4_0_PV05_AGENT_WORKSPACE_FILE} "
        "missing the cross-link to the runtime hook "
        f"({_V12_4_0_PV05_AGENT_WORKSPACE_CROSS_LINK}). The new subsection "
        "MUST cross-reference the implementation surface."
    )

    # --- (d.1) section-priorities test file exists -------------------
    priorities_test_path = project_root / _V12_4_0_PV05_PRIORITIES_TEST_FILE
    assert priorities_test_path.is_file(), (
        f"W-18 v12.4.0 PV-05 violation: {_V12_4_0_PV05_PRIORITIES_TEST_FILE} "
        "missing — release blocker. The PV-05 section-priority audit "
        "pin MUST land per the PV-05 owned-files manifest T2."
    )
    priorities_test_text = priorities_test_path.read_text(encoding="utf-8")
    for expected_test in (
        "test_version_update_skip_for_all_subagent_profiles",
        "test_task_quality_score_skip_for_all_subagent_profiles",
        "test_operational_learnings_explicit_skip_for_all_profiles",
        "test_operational_learnings_registered_in_sections_block",
        "test_all_24_profiles_have_l0_only_skip_discipline",
    ):
        assert f"def {expected_test}" in priorities_test_text, (
            f"W-18 v12.4.0 PV-05 violation: "
            f"{_V12_4_0_PV05_PRIORITIES_TEST_FILE} missing test function "
            f"``{expected_test}``. The 5-function contract pinning the "
            "audit §A.1 + §A.2 + §A.3 + sections-block registration + "
            "cross-profile composite is documented in the PV-05 "
            "owned-files manifest T2."
        )

    # --- (d.2) hook test file exists with the required test count ---
    hook_test_path = project_root / _V12_4_0_PV05_HOOK_TEST_FILE
    assert hook_test_path.is_file(), (
        f"W-18 v12.4.0 PV-05 violation: {_V12_4_0_PV05_HOOK_TEST_FILE} "
        "missing — release blocker. The PV-05 hook test suite MUST "
        "land per the PV-05 owned-files manifest T1."
    )
    hook_test_module = ast.parse(hook_test_path.read_text(encoding="utf-8"))
    hook_test_count = sum(
        1
        for node in hook_test_module.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        and node.name.startswith("test_")
    )
    assert hook_test_count >= _V12_4_0_PV05_HOOK_MIN_TESTS, (
        f"W-18 v12.4.0 PV-05 violation: {_V12_4_0_PV05_HOOK_TEST_FILE} "
        f"declares {hook_test_count} test functions; PV-05 dispatch "
        f"requires >= {_V12_4_0_PV05_HOOK_MIN_TESTS} (permissive + "
        "strict + non-target-layer skip + opt-in wiring + literal "
        "detection + defensive non-dict + nested-banner-exclusion + "
        "S-10 default-events preservation)."
    )

    # --- (d.3) context_profiles.yaml carries the registration -------
    profiles_path = project_root / _V12_4_0_PV05_CONTEXT_PROFILES_FILE
    profiles_text = profiles_path.read_text(encoding="utf-8")
    assert "operational_learnings:" in profiles_text, (
        f"W-18 v12.4.0 PV-05 violation: {_V12_4_0_PV05_CONTEXT_PROFILES_FILE} "
        "missing the `operational_learnings:` registration in the "
        "`sections:` block. Per audit §A.3, the registration is what "
        "closes the silent-fallback S-5 violation; without it the "
        "DeprecationWarning storm persists."
    )
