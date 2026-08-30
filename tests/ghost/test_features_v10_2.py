"""Ghost audit — per-cycle W-18 feature stanzas for the v10.2 cycle.

Split from ``tests/test_no_ghost_features.py`` per v15-ADR-001
(v14.3.0). New W-18 stanzas for a v10.2.x release append HERE; the
next MINOR cycle rotates to a fresh ``test_features_v<MAJ>_<MIN>.py``.
"""

from __future__ import annotations

import ast
from pathlib import Path

from tests.ghost._helpers import _w18_research_artifact_path

# ---------------------------------------------------------------------------
# W-18 v10.2.0 ghost-audit refresh — MINOR cycle-start (plugin deep review).
# ---------------------------------------------------------------------------

# v10.2.0 PV-01 NEW test files (D-P-1 / D-P-4 / D-P-6 closures).
_V10_2_0_NEW_TEST_FILES: tuple[Path, ...] = (
    Path("tests/test_runtime_plugins_smoke.py"),
    Path("tests/test_plugin_refresh_first_run.py"),
)


# v10.2.0 PV-01 NEW baseline fixtures (W-16 wholesale regen + 10th multi-baseline pin).
_V10_2_0_NEW_BASELINE_FILES: tuple[Path, ...] = (
    Path("docs/cycle-archive/v15.2.0/evobench-baselines/v10.2.0_baseline.json"),
    Path("benchmarks/devolaflow_context/baselines/layout_invariant_v10.2.0.yaml"),
)


_V10_2_0_CHANGELOG_LITERAL: str = "## [10.2.0]"


def test_v10_2_0_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v10.2.0: every NEW v10.2.0 PV-01 surface has presence coverage.

    Discharges the W-18 precondition for the v10.2.0 cycle-start MINOR.
    The historical stanza retains the active test files and baseline
    fixtures. Each needs a presence assertion here BEFORE the CHANGELOG
    mention is valid — per W-18 refresh-before-document sequencing.

    v10.2.0 PV-01 pins:

    1. **2 retained test files** — every file in `_V10_2_0_NEW_TEST_FILES`
       must exist on disk (D-P-1 / D-P-4 closures).
    2. **2 NEW baseline fixtures** — `v10.2.0_baseline.json` (W-16
       wholesale regen) + `layout_invariant_v10.2.0.yaml` (10th multi-
       baseline pin).
    3. **CHANGELOG entry** — `## [10.2.0]` header is present.
    """
    for test_rel in _V10_2_0_NEW_TEST_FILES:
        test_path = project_root / test_rel
        assert test_path.is_file(), (
            f"W-18 v10.2.0 violation: NEW test file {test_rel} missing. "
            f"v10.2.0 PV-01 ships this file per the cycle plan §3 PV-01; "
            f"restore it or remove the CHANGELOG mention of the "
            f"corresponding gap closure."
        )

    for baseline_rel in _V10_2_0_NEW_BASELINE_FILES:
        baseline_path = project_root / baseline_rel
        assert baseline_path.is_file(), (
            f"W-18 v10.2.0 violation: NEW baseline fixture {baseline_rel} "
            f"missing. Restore the archived W-16 evidence or immutable "
            f"layout witness; do not regenerate retired EvoBench data."
        )

    changelog_path = project_root / "CHANGELOG.md"
    changelog_text = changelog_path.read_text(encoding="utf-8")
    assert _V10_2_0_CHANGELOG_LITERAL in changelog_text, (
        f"W-18 v10.2.0 violation: CHANGELOG entry "
        f"{_V10_2_0_CHANGELOG_LITERAL!r} missing; PV-01 ships this entry."
    )


# ---------------------------------------------------------------------------
# W-18 v10.2.1 ghost-audit refresh — retained lifecycle/plugin checks.
# ---------------------------------------------------------------------------

# v10.2.1 PV-02 NEW test files (D-S-2 / D-S-3 / D-S-5 closures).
_V10_2_1_NEW_TEST_FILES: tuple[Path, ...] = ()


_V10_2_1_PRE_PLUGIN_INVOCATION_CONST: str = "EVENT_TRIGGERS_DAILY_UPGRADE"


# v10.2.1 PV-02 dogfood pass #1 deliverable path (gitignored content; the
# path-presence assertion is the operator-visible contract).
_V10_2_1_DOGFOOD_PASS1_DOC: Path = Path(".local/research/v10.2.1_dogfood_pass1.md")


_V10_2_1_CHANGELOG_LITERAL: str = "## [10.2.1]"


def test_v10_2_1_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v10.2.1: every NEW v10.2.1 PV-02 surface has presence coverage.

    Discharges the W-18 precondition for the v10.2.1 PV-02 PATCH.
    The CHANGELOG entry mentions the dogfood pass #1 research artifact.
    It needs a presence assertion here BEFORE the CHANGELOG mention is valid —
    presence assertion here BEFORE the CHANGELOG mention is valid — per
    W-18 refresh-before-document sequencing.

    v10.2.1 PV-02 retains one historical artifact:

    1. **Dogfood pass #1 artifact** — file path presence at
       `.local/research/v10.2.1_dogfood_pass1.md` (gitignored content;
       path-presence is the operator-visible contract).
    2. **CHANGELOG entry** — `## [10.2.1]` header is present.
    """
    for test_rel in _V10_2_1_NEW_TEST_FILES:
        test_path = project_root / test_rel
        assert test_path.is_file(), (
            f"W-18 v10.2.1 violation: NEW test file {test_rel} missing. "
            f"v10.2.1 PV-02 ships this file per the cycle plan §3 PV-02; "
            f"restore it or remove the CHANGELOG mention of the "
            f"corresponding gap closure."
        )

    pre_plugin_path = project_root / "src/devolaflow/lifecycle/pre_plugin_invocation.py"
    assert pre_plugin_path.is_file(), "W-18 v10.2.1 violation: pre_plugin_invocation.py missing."
    pre_plugin_source = pre_plugin_path.read_text(encoding="utf-8")
    assert _V10_2_1_PRE_PLUGIN_INVOCATION_CONST in pre_plugin_source, (
        f"W-18 v10.2.1 violation: lifecycle hook missing the "
        f"{_V10_2_1_PRE_PLUGIN_INVOCATION_CONST!r} introspection "
        f"constant; v10.2.1 PV-02 D-P-2 daily-upgrade integration "
        f"requires this surface for downstream governance + tests."
    )

    _w18_research_artifact_path(project_root, _V10_2_1_DOGFOOD_PASS1_DOC)

    changelog_path = project_root / "CHANGELOG.md"
    changelog_text = changelog_path.read_text(encoding="utf-8")
    assert _V10_2_1_CHANGELOG_LITERAL in changelog_text, (
        f"W-18 v10.2.1 violation: CHANGELOG entry "
        f"{_V10_2_1_CHANGELOG_LITERAL!r} missing; PV-02 ships this entry."
    )


# ---------------------------------------------------------------------------
# W-18 v10.2.2 ghost-audit refresh — retained evaluation evidence.
# ---------------------------------------------------------------------------

# v10.2.2 PV-03 dogfood pass #2 deliverable (gitignored content;
# path-presence contract).
_V10_2_2_DOGFOOD_PASS2_DOC: Path = Path(".local/research/v10.2.2_dogfood_pass2.md")


_V10_2_2_CHANGELOG_LITERAL: str = "## [10.2.2]"


def test_v10_2_2_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v10.2.2: every NEW v10.2.2 PV-03 surface has presence coverage.

    Discharges the W-18 precondition for the v10.2.2 PV-03 PATCH.
    The retired external adapter/probe surfaces are no longer live. This
    historical stanza retains only:

    1. **Dogfood pass #2** — `.local/research/v10.2.2_dogfood_pass2.md`
       exists (D-N-1 + D-S-1 closure; adapter outcome + per-file
       evaluation capture).
    2. **CHANGELOG entry** — `## [10.2.2]` header is present.
    """
    _w18_research_artifact_path(project_root, _V10_2_2_DOGFOOD_PASS2_DOC)

    changelog_path = project_root / "CHANGELOG.md"
    changelog_text = changelog_path.read_text(encoding="utf-8")
    assert _V10_2_2_CHANGELOG_LITERAL in changelog_text, (
        f"W-18 v10.2.2 violation: CHANGELOG entry "
        f"{_V10_2_2_CHANGELOG_LITERAL!r} missing; PV-03 ships this entry."
    )


# ---------------------------------------------------------------------------
# W-18 v10.2.3 ghost-audit refresh — PV-04 PATCH (self-iteration round 1:
# bridge defect fix + Track B CC reductions).
# ---------------------------------------------------------------------------

# v10.2.3 PV-04 dogfood pass #3 deliverable (gitignored content;
# path-presence is the operator-visible contract).
_V10_2_3_DOGFOOD_PASS3_DOC: Path = Path(".local/research/v10.2.3_dogfood_pass3.md")


# v10.2.3 PV-04 self-iteration round 1 report (gitignored content;
# path-presence contract).
_V10_2_3_ITERATION_ROUND1_DOC: Path = Path(".local/research/v10.2.3_iteration_round1.md")


# v10.2.3 PV-04 Track B-1 — pre_plugin_invocation helpers.
_V10_2_3_PPI_FILE: Path = Path("src/devolaflow/lifecycle/pre_plugin_invocation.py")


_V10_2_3_PPI_HELPERS: tuple[str, ...] = (
    "_resolve_upgrade_threshold_hours",
    "_run_install_then_upgrade_for_plugin",
)


_V10_2_3_CHANGELOG_LITERAL: str = "## [10.2.3]"


def test_v10_2_3_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v10.2.3: every NEW v10.2.3 PV-04 surface has presence coverage.

    Discharges the W-18 precondition for the v10.2.3 PV-04 PATCH
    (self-iteration round 1). The CHANGELOG entry mentions the
    pre-plugin CC reduction and the two research deliverables (dogfood
    pass #3 + iteration round 1 report). Each needs a presence
    assertion here BEFORE the CHANGELOG mention is valid — per W-18
    refresh-before-document sequencing.

    v10.2.3 PV-04 pins:

    1. **CC reduction Track B-1** —
       `src/devolaflow/lifecycle/pre_plugin_invocation.py` defines
       `_resolve_upgrade_threshold_hours` and
       `_run_install_then_upgrade_for_plugin`.
    2. **Dogfood pass #3 deliverable** —
       `.local/research/v10.2.3_dogfood_pass3.md` exists.
    3. **Self-iteration round 1 report** —
       `.local/research/v10.2.3_iteration_round1.md` exists.
    4. **CHANGELOG entry** — `## [10.2.3]` header is present.
    """
    ppi_path = project_root / _V10_2_3_PPI_FILE
    assert ppi_path.is_file(), (
        f"W-18 v10.2.3 violation: pre_plugin_invocation file "
        f"{_V10_2_3_PPI_FILE} missing. v10.2.3 PV-04 Track B-1 extracts "
        f"helpers in this file; restore it or remove the CHANGELOG mention."
    )
    ppi_source = ppi_path.read_text(encoding="utf-8")
    ppi_module = ast.parse(ppi_source)
    ppi_defined = {
        node.name
        for node in ast.walk(ppi_module)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    for helper in _V10_2_3_PPI_HELPERS:
        assert helper in ppi_defined, (
            f"W-18 v10.2.3 violation: pre_plugin_invocation.py missing "
            f"helper {helper!r}; v10.2.3 PV-04 Track B-1 ships this helper "
            f"as part of the CC=18 → ≤10 reduction. Either restore the "
            f"helper OR remove the CHANGELOG mention of Track B-1."
        )

    _w18_research_artifact_path(project_root, _V10_2_3_DOGFOOD_PASS3_DOC)

    _w18_research_artifact_path(project_root, _V10_2_3_ITERATION_ROUND1_DOC)

    changelog_path = project_root / "CHANGELOG.md"
    changelog_text = changelog_path.read_text(encoding="utf-8")
    assert _V10_2_3_CHANGELOG_LITERAL in changelog_text, (
        f"W-18 v10.2.3 violation: CHANGELOG entry "
        f"{_V10_2_3_CHANGELOG_LITERAL!r} missing; PV-04 ships this entry."
    )


# ---------------------------------------------------------------------------
# W-18 v10.2.4 ghost-audit refresh — PV-05 PATCH (self-iteration round 2:
# 1 mechanical CC reduction in installer.py + W-8 stagnation predicate +
# W-17 mid-cycle audit + dogfood pass #4).
# ---------------------------------------------------------------------------

# v10.2.4 PV-05 round-2 mechanical extraction surface (CC=15→8 in
# `read_last_checked` per PV-03 finding CC-a5d310-0003).
_V10_2_4_INSTALLER_FILE: Path = Path("src/devolaflow/plugins/installer.py")


_V10_2_4_INSTALLER_HELPERS: tuple[str, ...] = ("_parse_log_event_timestamp",)


_V10_2_4_INSTALLER_MODULE_CONSTANTS: tuple[str, ...] = ("_LAST_CHECKED_SUCCESSFUL_EVENTS",)


# v10.2.4 PV-05 research deliverables (gitignored content; path-presence
# is the operator-visible contract).
_V10_2_4_ITERATION_ROUND2_DOC: Path = Path(".local/research/v10.2.4_iteration_round2.md")


_V10_2_4_W17_AUDIT_DOC: Path = Path(".local/research/v10.2.4_w17_mid_cycle_audit.md")


_V10_2_4_W8_STAGNATION_DOC: Path = Path(".local/research/v10.2.4_w8_stagnation_check.md")


_V10_2_4_DOGFOOD_PASS4_DOC: Path = Path(".local/research/v10.2.4_dogfood_pass4.md")


_V10_2_4_CHANGELOG_LITERAL: str = "## [10.2.4]"


# W-17 mid-cycle audit cumulative-count sentinel — the CHANGELOG entry
# MUST cite the cycle-cumulative NEW-test count so the audit assertion
# is discoverable by W-17 readers without spelunking through the
# research artifact. The literal "93 / 150" is the post-PV-05 cumulative
# (see `.local/research/v10.2.4_w17_mid_cycle_audit.md` §1).
_V10_2_4_CHANGELOG_W17_LITERAL: str = "93 / 150"


def test_v10_2_4_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v10.2.4: every NEW v10.2.4 PV-05 surface has presence coverage.

    Discharges the W-18 precondition for the v10.2.4 PV-05 PATCH
    (self-iteration round 2 + W-17 mid-cycle audit + W-8 stagnation
    predicate). The CHANGELOG entry mentions the round-2 mechanical CC
    reduction in `installer.py::read_last_checked` (CC=15→8 via
    `_parse_log_event_timestamp` helper extraction) and the four
    research deliverables (round 2 report, W-17 audit, W-8 stagnation
    check, dogfood pass #4). Each needs a presence assertion here
    BEFORE the CHANGELOG mention is valid — per W-18 refresh-before-
    document sequencing.

    v10.2.4 PV-05 pins:

    1. **Round-2 mechanical extraction (Track A)** —
       `src/devolaflow/plugins/installer.py` defines
       `_parse_log_event_timestamp` (helper) AND
       `_LAST_CHECKED_SUCCESSFUL_EVENTS` (lifted module-level constant).
       Without these the v10.2.4 PV-05 round-2 fix is not shipped.
    2. **Self-iteration round 2 report** —
       `.local/research/v10.2.4_iteration_round2.md` exists.
    3. **W-17 mid-cycle audit** —
       `.local/research/v10.2.4_w17_mid_cycle_audit.md` exists; cumulative
       count is documented in CHANGELOG (literal "93 / 150").
    4. **W-8 stagnation predicate evaluation** —
       `.local/research/v10.2.4_w8_stagnation_check.md` exists.
    5. **Dogfood pass #4 deliverable** —
       `.local/research/v10.2.4_dogfood_pass4.md` exists.
    6. **CHANGELOG entry** — `## [10.2.4]` header is present.
    """
    installer_path = project_root / _V10_2_4_INSTALLER_FILE
    assert installer_path.is_file(), (
        f"W-18 v10.2.4 violation: installer file {_V10_2_4_INSTALLER_FILE} "
        f"missing. v10.2.4 PV-05 round-2 patches `read_last_checked` in "
        f"this file via `_parse_log_event_timestamp` helper extraction; "
        f"restore it or remove the CHANGELOG mention."
    )
    installer_source = installer_path.read_text(encoding="utf-8")
    installer_module = ast.parse(installer_source)
    installer_defined = {
        node.name
        for node in ast.walk(installer_module)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    for helper in _V10_2_4_INSTALLER_HELPERS:
        assert helper in installer_defined, (
            f"W-18 v10.2.4 violation: installer.py missing helper "
            f"{helper!r}; v10.2.4 PV-05 round-2 ships this helper as "
            f"part of the CC=15 → ≤10 reduction in `read_last_checked` "
            f"per PV-03 finding CC-a5d310-0003. Either restore "
            f"the helper OR remove the CHANGELOG mention of the round-2 "
            f"installer.py extraction."
        )

    installer_module_assigns = {
        target.id
        for node in ast.walk(installer_module)
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    } | {
        node.target.id
        for node in ast.walk(installer_module)
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    }
    for constant in _V10_2_4_INSTALLER_MODULE_CONSTANTS:
        assert constant in installer_module_assigns, (
            f"W-18 v10.2.4 violation: installer.py missing module-level "
            f"constant {constant!r}; v10.2.4 PV-05 round-2 lifts the "
            f"successful-event set to a module-level frozenset for "
            f"introspection. Restore the constant OR remove the CHANGELOG "
            f"mention of the round-2 lift."
        )

    _w18_research_artifact_path(project_root, _V10_2_4_ITERATION_ROUND2_DOC)

    _w18_research_artifact_path(project_root, _V10_2_4_W17_AUDIT_DOC)

    _w18_research_artifact_path(project_root, _V10_2_4_W8_STAGNATION_DOC)

    _w18_research_artifact_path(project_root, _V10_2_4_DOGFOOD_PASS4_DOC)

    changelog_path = project_root / "CHANGELOG.md"
    changelog_text = changelog_path.read_text(encoding="utf-8")
    assert _V10_2_4_CHANGELOG_LITERAL in changelog_text, (
        f"W-18 v10.2.4 violation: CHANGELOG entry "
        f"{_V10_2_4_CHANGELOG_LITERAL!r} missing; PV-05 ships this entry."
    )
    assert _V10_2_4_CHANGELOG_W17_LITERAL in changelog_text, (
        f"W-18 v10.2.4 violation: CHANGELOG entry must cite the cycle-"
        f"cumulative NEW-test count {_V10_2_4_CHANGELOG_W17_LITERAL!r} "
        f"to document the W-17 audit verdict. Without this literal "
        f"the W-17 §3 mid-cycle audit assertion is not discoverable to "
        f"future cycle authors. Update CHANGELOG `## [10.2.4]` to cite "
        f"the W-17 cumulative count."
    )
