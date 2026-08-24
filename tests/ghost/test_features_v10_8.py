"""Ghost audit — per-cycle W-18 feature stanzas for the v10.8 cycle.

Split from ``tests/test_no_ghost_features.py`` per v15-ADR-001
(v14.3.0). New W-18 stanzas for a v10.8.x release append HERE; the
next MINOR cycle rotates to a fresh ``test_features_v<MAJ>_<MIN>.py``.
"""

from __future__ import annotations

from pathlib import Path

from tests.ghost._helpers import _w18_research_artifact_path
from tests.ghost.test_registries import _SF4_REFERENCE_SET

# =====================================================================
# v10.8.0 — External Tool Coupling Hardening (D-C-1 / D-C-2 / D-C-3)
# =====================================================================
#
# v10.8.0 collapses 3 v11.0.0-cycle PDSs (D-C-1 degraded-mode contract;
# D-C-2 bridge shape contract tests; D-C-3 pre_plugin_invocation split)
# into a single coherent MINOR cycle per
# `.local/research/v11.0.0_patches/`. The cycle ships:
#
#  1. D-C-1 — `references/degraded-mode.md` 17th SF-4 canonical
#     reference (per-plugin upstream-unreachable fallback contract)
#     + `tests/test_degraded_mode.py` regression suite (8 tests).
#  2. D-C-2 — `tests/integration/` package (conftest + 4 shape
#     contract files + captured fixtures) + `scripts/refresh_bridge_fixtures.py`
#     + `.github/workflows/bridge-fixture-refresh.yml` weekly cron.
#  3. D-C-3 — `lifecycle/pre_plugin_invocation_install.py` +
#     `lifecycle/pre_plugin_invocation_upgrade.py` (DEFAULT_EVENTS 10 → 12
#     per A-2.2 append-only) + `tests/test_pre_plugin_invocation_split.py`.
#  4. CHANGELOG `## [10.8.0]` + canonical 7 sync 10.7.0 → 10.8.0.
#  5. `.local/research/v10.8.0_retrospective.md` (W-7 / SI-8).

# D-C-1 surfaces.
_V10_8_0_DEGRADED_MODE_REF: Path = Path("workflow-system/agent/references/degraded-mode.md")


_V10_8_0_DEGRADED_MODE_TESTS: Path = Path("tests/test_degraded_mode.py")


# D-C-2 surfaces.
_V10_8_0_INTEGRATION_INIT: Path = Path("tests/integration/__init__.py")


_V10_8_0_INTEGRATION_CONFTEST: Path = Path("tests/integration/conftest.py")


_V10_8_0_INTEGRATION_TESTS: tuple[Path, ...] = (
    Path("tests/integration/test_si_chip_shape_contract.py"),
    Path("tests/integration/test_rtk_shape_contract.py"),
    Path("tests/integration/test_ui_pro_shape_contract.py"),
)


_V10_8_0_REFRESH_SCRIPT: Path = Path("scripts/refresh_bridge_fixtures.py")


_V10_8_0_FIXTURE_REFRESH_WORKFLOW: Path = Path(".github/workflows/bridge-fixture-refresh.yml")


# D-C-3 surfaces.
_V10_8_0_PPI_INSTALL_MODULE: Path = Path(
    "src/devolaflow/lifecycle/pre_plugin_invocation_install.py"
)


_V10_8_0_PPI_UPGRADE_MODULE: Path = Path(
    "src/devolaflow/lifecycle/pre_plugin_invocation_upgrade.py"
)


_V10_8_0_PPI_SPLIT_TESTS: Path = Path("tests/test_pre_plugin_invocation_split.py")


# Cycle close surfaces.
_V10_8_0_RETROSPECTIVE_DOC: Path = Path(".local/research/v10.8.0_retrospective.md")


_V10_8_0_CHANGELOG_LITERAL: str = "## [10.8.0]"


# Makefile target for D-C-2 fixture refresh.
_V10_8_0_MAKEFILE_TARGETS: tuple[str, ...] = ("refresh-bridge-fixtures:",)


def test_v10_8_0_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v10.8.0: every NEW v10.8.0 D-C-1 / D-C-2 / D-C-3 surface is pinned.

    Discharges the W-18 precondition for the v10.8.0 MINOR cycle. The
    CHANGELOG entry mentions:

    * NEW `workflow-system/agent/references/degraded-mode.md` (17th SF-4
      canonical reference; opens with "Degraded ≠ Full" warning per
      D-C-1 §9 R1 mitigation).
    * NEW `tests/test_degraded_mode.py` (D-C-1 regression suite).
    * NEW `tests/integration/` package (D-C-2 bridge shape contract
      tests) + retained contract test files + fixture package.
    * NEW `scripts/refresh_bridge_fixtures.py` (D-C-2 fixture refresh).
    * NEW `.github/workflows/bridge-fixture-refresh.yml` (D-C-2 weekly
      cron).
    * NEW `src/devolaflow/lifecycle/pre_plugin_invocation_install.py`
      (D-C-3 install handler at DEFAULT_EVENTS position 11).
    * NEW `src/devolaflow/lifecycle/pre_plugin_invocation_upgrade.py`
      (D-C-3 upgrade handler at DEFAULT_EVENTS position 12).
    * NEW `tests/test_pre_plugin_invocation_split.py` (D-C-3 regression).
    * NEW Makefile target `refresh-bridge-fixtures`.
    * Canonical 7 sync 10.7.0 → 10.8.0 + CHANGELOG `## [10.8.0]`.
    * NEW `.local/research/v10.8.0_retrospective.md` (W-7 / SI-8).
    """
    # D-C-1: degraded-mode reference + tests.
    assert (project_root / _V10_8_0_DEGRADED_MODE_REF).is_file(), (
        f"W-18 v10.8.0 violation: degraded-mode reference missing at "
        f"{_V10_8_0_DEGRADED_MODE_REF}. v10.8.0 D-C-1 ships this file."
    )
    deg_text = (project_root / _V10_8_0_DEGRADED_MODE_REF).read_text(encoding="utf-8")
    assert "Degraded ≠ Full" in deg_text[:500], (
        "W-18 v10.8.0 violation: degraded-mode.md must OPEN with the "
        "'Degraded ≠ Full' warning section (D-C-1 §9 R1 mitigation)"
    )
    assert (project_root / _V10_8_0_DEGRADED_MODE_TESTS).is_file(), (
        f"W-18 v10.8.0 violation: degraded-mode tests missing at {_V10_8_0_DEGRADED_MODE_TESTS}."
    )

    # D-C-2: integration test infrastructure.
    for integration_file in (
        _V10_8_0_INTEGRATION_INIT,
        _V10_8_0_INTEGRATION_CONFTEST,
    ):
        assert (project_root / integration_file).is_file(), (
            f"W-18 v10.8.0 violation: integration file missing at "
            f"{integration_file} — D-C-2 ships the tests/integration/ package."
        )
    for contract_test in _V10_8_0_INTEGRATION_TESTS:
        assert (project_root / contract_test).is_file(), (
            f"W-18 v10.8.0 violation: bridge contract test missing at "
            f"{contract_test} — D-C-2 retains this contract test file."
        )
    assert (project_root / _V10_8_0_REFRESH_SCRIPT).is_file(), (
        f"W-18 v10.8.0 violation: fixture refresh script missing at "
        f"{_V10_8_0_REFRESH_SCRIPT}. v10.8.0 D-C-2 ships this script."
    )
    assert (project_root / _V10_8_0_FIXTURE_REFRESH_WORKFLOW).is_file(), (
        f"W-18 v10.8.0 violation: fixture-refresh CI workflow missing at "
        f"{_V10_8_0_FIXTURE_REFRESH_WORKFLOW}. v10.8.0 D-C-2 ships this."
    )

    # D-C-3: split handlers + tests.
    for split_module in (_V10_8_0_PPI_INSTALL_MODULE, _V10_8_0_PPI_UPGRADE_MODULE):
        assert (project_root / split_module).is_file(), (
            f"W-18 v10.8.0 violation: split handler missing at {split_module}. "
            f"v10.8.0 D-C-3 ships the pre_plugin_invocation split."
        )
    assert (project_root / _V10_8_0_PPI_SPLIT_TESTS).is_file(), (
        f"W-18 v10.8.0 violation: split-contract tests missing at "
        f"{_V10_8_0_PPI_SPLIT_TESTS}. v10.8.0 D-C-3 ships 5+ tests."
    )

    # DEFAULT_EVENTS length bump (10 → 12 by v10.8.0 D-C-3 split). The
    # SUPERSET containment check (`>= 12`) accommodates future
    # APPEND-ONLY additions per A-2.2 — e.g., v11.0.0 PV-02 D-Q-3
    # appends 4 NEW canonical event names (positions 13-16) without
    # disturbing positions 1-12 (which stay byte-stable per A-2.4).
    from devolaflow.lifecycle import DEFAULT_EVENTS

    assert len(DEFAULT_EVENTS) >= 12, (
        f"W-18 v10.8.0 violation: D-C-3 ships DEFAULT_EVENTS at length 12 "
        f"(positions 1-12 byte-stable per A-2.4); got len={len(DEFAULT_EVENTS)}"
    )

    # 17th SF-4 canonical reference pinned in the _SF4_REFERENCE_SET above.
    assert "degraded-mode.md" in set(_SF4_REFERENCE_SET), (
        "W-18 v10.8.0 violation: _SF4_REFERENCE_SET must include 'degraded-mode.md' after D-C-1."
    )

    # Makefile target for fixture refresh.
    makefile_text = (project_root / "Makefile").read_text(encoding="utf-8")
    for target in _V10_8_0_MAKEFILE_TARGETS:
        assert target in makefile_text, (
            f"W-18 v10.8.0 violation: Makefile missing literal {target!r} "
            f"(D-C-2 refresh-bridge-fixtures target)."
        )

    # Retrospective + CHANGELOG.
    _w18_research_artifact_path(project_root, _V10_8_0_RETROSPECTIVE_DOC)
    changelog = (project_root / "CHANGELOG.md").read_text(encoding="utf-8")
    assert _V10_8_0_CHANGELOG_LITERAL in changelog, (
        f"W-18 v10.8.0 violation: CHANGELOG entry "
        f"{_V10_8_0_CHANGELOG_LITERAL!r} missing; v10.8.0 ships this entry."
    )
