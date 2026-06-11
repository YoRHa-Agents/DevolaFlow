"""Ghost audit — per-cycle W-18 feature stanzas for the v10.6 cycle.

Split from ``tests/test_no_ghost_features.py`` per v15-ADR-001
(v14.3.0). New W-18 stanzas for a v10.6.x release append HERE; the
next MINOR cycle rotates to a fresh ``test_features_v<MAJ>_<MIN>.py``.
"""

from __future__ import annotations

from pathlib import Path

from tests.ghost._helpers import _w18_research_artifact_path

# =====================================================================
# v10.6.0 PV-01..PV-03 — Code Quality (NineS cleanup + god-function refactor)
# =====================================================================
#
# v10.6.0 collapses 3 v11.0.0-cycle PDSs (D-Q-1, D-Q-2, D-Q-4) into a
# single coherent MINOR cycle per `.local/research/v11.0.0_patches/`.
# The cycle ships:
#  1. PV-01 D-Q-1 — 7 helper extractions across `src/devolaflow/lifecycle/`
#     + `src/devolaflow/plugins/installer.py` (zero behaviour change;
#     pure CC reduction).
#  2. PV-02 D-Q-2 — `feedback.py::ProposalGenerator` god-function
#     refactor: extracts `_emit_dispatch` into NEW
#     `src/devolaflow/feedback_emit.py::ProposalEmitter` class with
#     `_fire_hook_chain` helper (composition over inheritance);
#     `generate_round_dispatch` becomes a 5-line façade. S-10
#     invariant (10/10 tests in `test_dispatch_emission_runs_hooks.py`)
#     preserved byte-identical.
#  3. PV-03 D-Q-4 — NEW `scripts/snapshot_compressor_health.py` audit
#     script + `tests/test_snapshot_compressor_health.py` (5 tests) +
#     Makefile `snapshot-compressor` target + first audit output
#     committed to `.local/research/v10.6.0_compressor_health.md`.
#  4. CHANGELOG `## [10.6.0]` entry; canonical 7 sync 10.5.0 -> 10.6.0
#  5. .local/research/v10.6.0_retrospective.md (W-7 / SI-8)

# 7 NEW helpers extracted by PV-01 (D-Q-1).
_V10_6_0_DQ1_HELPERS: tuple[tuple[str, str], ...] = (
    ("src/devolaflow/lifecycle/test_on_complete.py", "_persist_learnings_shard"),
    ("src/devolaflow/lifecycle/test_on_complete.py", "_persist_legibility_shard"),
    ("src/devolaflow/lifecycle/test_on_complete.py", "_persist_lifecycle_event_shard"),
    ("src/devolaflow/lifecycle/auto_write_handoff.py", "_layer_lookup_table"),
    ("src/devolaflow/lifecycle/auto_write_handoff.py", "_resolve_envelope_inputs"),
    ("src/devolaflow/lifecycle/auto_write_handoff.py", "_write_envelope_or_violation"),
    ("src/devolaflow/lifecycle/pre_plugin_invocation.py", "_parse_plugin_ids_list"),
    ("src/devolaflow/lifecycle/pre_plugin_invocation.py", "_parse_plugin_id_single"),
    ("src/devolaflow/lifecycle/pre_plugin_invocation.py", "_parse_workflow_plugins"),
    ("src/devolaflow/plugins/installer.py", "_handle_already_installed_path"),
    ("src/devolaflow/plugins/installer.py", "_handle_install_path"),
    ("src/devolaflow/plugins/installer.py", "_iter_workflow_matches"),
    ("src/devolaflow/plugins/installer.py", "_validate_required_keys"),
    ("src/devolaflow/plugins/installer.py", "_validate_npm_then_init_keys"),
)


_V10_6_0_FEEDBACK_EMIT_MODULE: Path = Path("src/devolaflow/feedback_emit.py")


_V10_6_0_FEEDBACK_EMIT_TESTS: Path = Path("tests/test_feedback_emit.py")


_V10_6_0_SNAPSHOT_SCRIPT: Path = Path("scripts/snapshot_compressor_health.py")


_V10_6_0_SNAPSHOT_TESTS: Path = Path("tests/test_snapshot_compressor_health.py")


_V10_6_0_COMPRESSOR_HEALTH_DOC: Path = Path(".local/research/v10.6.0_compressor_health.md")


_V10_6_0_RETROSPECTIVE_DOC: Path = Path(".local/research/v10.6.0_retrospective.md")


_V10_6_0_CHANGELOG_LITERAL: str = "## [10.6.0]"


_V10_6_0_MAKEFILE_SNAPSHOT_LITERAL: str = "snapshot-compressor:"


def test_v10_6_0_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v10.6.0: every NEW v10.6.0 PV-01..PV-03 surface has presence coverage.

    Discharges the W-18 precondition for the v10.6.0 MINOR cycle. The
    CHANGELOG entry mentions:

    * 14 NEW helpers extracted by PV-01 D-Q-1 (across 4 files in
      `lifecycle/` + `plugins/`); pure refactor, zero behaviour change.
    * NEW `src/devolaflow/feedback_emit.py` module with the
      `ProposalEmitter` class (PV-02 D-Q-2 god-function refactor).
    * NEW `tests/test_feedback_emit.py` with 8 unit tests for
      `ProposalEmitter` in isolation.
    * NEW `scripts/snapshot_compressor_health.py` audit script
      (PV-03 D-Q-4); NEW `tests/test_snapshot_compressor_health.py`
      with 5 tests; NEW Makefile `snapshot-compressor` target;
      NEW `.local/research/v10.6.0_compressor_health.md` audit output.
    * canonical 7 sync 10.5.0 -> 10.6.0 + CHANGELOG `## [10.6.0]`.

    Each pin protects the W-18 sequencing per
    `.local/research/v9.0.0_pv05_design.md` §3 + ADR-005 D2.
    """
    # PV-01 (D-Q-1) — 14 helpers extracted across 4 files.
    for src_path, helper_name in _V10_6_0_DQ1_HELPERS:
        text = (project_root / src_path).read_text(encoding="utf-8")
        assert f"def {helper_name}(" in text, (
            f"W-18 v10.6.0 violation: D-Q-1 helper `{helper_name}` missing "
            f"from {src_path}. v10.6.0 PV-01 extracts this helper as part "
            f"of the NineS cleanup. Author the helper OR remove the "
            f"CHANGELOG mention."
        )

    # PV-02 (D-Q-2) — NEW feedback_emit.py + ProposalEmitter + tests.
    feedback_emit_path = project_root / _V10_6_0_FEEDBACK_EMIT_MODULE
    assert feedback_emit_path.is_file(), (
        f"W-18 v10.6.0 violation: NEW module missing at "
        f"{_V10_6_0_FEEDBACK_EMIT_MODULE}. v10.6.0 PV-02 extracts the "
        f"S-10 hook-chain firing into ProposalEmitter."
    )
    feedback_emit_text = feedback_emit_path.read_text(encoding="utf-8")
    assert "class ProposalEmitter" in feedback_emit_text, (
        "W-18 v10.6.0 violation: feedback_emit.py must define "
        "`class ProposalEmitter` (D-Q-2 §2 patch_design)."
    )
    assert "_fire_hook_chain" in feedback_emit_text, (
        "W-18 v10.6.0 violation: feedback_emit.py must define "
        "`_fire_hook_chain` (the S-10 4-event chain helper)."
    )

    feedback_text = (project_root / "src/devolaflow/feedback.py").read_text(encoding="utf-8")
    assert "from devolaflow.feedback_emit import ProposalEmitter" in feedback_text, (
        "W-18 v10.6.0 violation: feedback.py must import ProposalEmitter "
        "(D-Q-2 §2 composition wiring) — `_emit_dispatch` was extracted."
    )
    assert "self._emitter = ProposalEmitter()" in feedback_text, (
        "W-18 v10.6.0 violation: ProposalGenerator.__init__ must compose "
        "ProposalEmitter (D-Q-2 §2 composition over inheritance)."
    )

    feedback_emit_tests = project_root / _V10_6_0_FEEDBACK_EMIT_TESTS
    assert feedback_emit_tests.is_file(), (
        f"W-18 v10.6.0 violation: NEW unit tests missing at "
        f"{_V10_6_0_FEEDBACK_EMIT_TESTS}. v10.6.0 PV-02 ships 8 unit "
        f"tests for ProposalEmitter in isolation."
    )

    # PV-03 (D-Q-4) — snapshot script + tests + Makefile target + audit output.
    snapshot_script = project_root / _V10_6_0_SNAPSHOT_SCRIPT
    assert snapshot_script.is_file(), (
        f"W-18 v10.6.0 violation: NEW audit script missing at "
        f"{_V10_6_0_SNAPSHOT_SCRIPT}. v10.6.0 PV-03 ships the "
        f"compressor/ post-split health snapshot."
    )
    snapshot_tests = project_root / _V10_6_0_SNAPSHOT_TESTS
    assert snapshot_tests.is_file(), (
        f"W-18 v10.6.0 violation: NEW snapshot tests missing at "
        f"{_V10_6_0_SNAPSHOT_TESTS}. v10.6.0 PV-03 ships 5 tests for "
        f"the snapshot script."
    )
    _w18_research_artifact_path(project_root, _V10_6_0_COMPRESSOR_HEALTH_DOC)

    makefile_text = (project_root / "Makefile").read_text(encoding="utf-8")
    assert _V10_6_0_MAKEFILE_SNAPSHOT_LITERAL in makefile_text, (
        f"W-18 v10.6.0 violation: Makefile missing literal "
        f"{_V10_6_0_MAKEFILE_SNAPSHOT_LITERAL!r} (D-Q-4 audit target)."
    )

    # Retrospective + CHANGELOG.
    _w18_research_artifact_path(project_root, _V10_6_0_RETROSPECTIVE_DOC)

    changelog = (project_root / "CHANGELOG.md").read_text(encoding="utf-8")
    assert _V10_6_0_CHANGELOG_LITERAL in changelog, (
        f"W-18 v10.6.0 violation: CHANGELOG entry "
        f"{_V10_6_0_CHANGELOG_LITERAL!r} missing; v10.6.0 ships this entry."
    )
