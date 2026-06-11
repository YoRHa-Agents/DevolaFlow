"""Ghost audit — per-cycle W-18 feature stanzas for the v9.2 cycle.

Split from ``tests/test_no_ghost_features.py`` per v15-ADR-001
(v14.3.0). New W-18 stanzas for a v9.2.x release append HERE; the
next MINOR cycle rotates to a fresh ``test_features_v<MAJ>_<MIN>.py``.
"""

from __future__ import annotations

import ast
from pathlib import Path

# ---------------------------------------------------------------------------
# v9.2.0 PV-06 — repo-init seed examples + e2e capability test ghost-audit
# ---------------------------------------------------------------------------

# v9.2.0 PV-06 (the cycle-rollup MINOR headline) introduces TWO operator-visible
# deliverables that the W-18 precondition pins BEFORE the [9.2.0] CHANGELOG
# entry mentioning them:
#
# 1. EXTEND src/devolaflow/init_project.py::install_local with the new
#    `with_examples: bool = False` kwarg + the `_seed_example_artifacts(cwd)`
#    helper that materialises 3 worked-trace fixtures under
#    `.local/.agent/active/example-add-dark-mode/` + `.local/.agent/handoff/
#    L0__L2__example-add-dark-mode__0001.yaml` + `.local/memory/specs/
#    example-domain/spec.md` so new repos demonstrate the change-driven
#    pattern out-of-the-box. Closes G-006 deferred from v9.1.0 retro §3.
# 2. NEW tests/test_capability_e2e.py — 10 end-to-end capability tests that
#    cross every PV's deliverable through a tmp-path repo fixture. Closes
#    G-015 deferred from v9.1.0 retro §3.
_V9_2_0_NEW_FILES: tuple[str, ...] = ("tests/test_capability_e2e.py",)


# Minimum byte size for a v9.2.0 NEW surface — guards against an empty
# stub silently slipping through and satisfying mere file-presence.
_V9_2_0_FILE_MIN_BYTES: int = 1000


# The e2e test file ships with EXACTLY 10 test functions per the cycle
# plan §PV-06 W-17 budget pin (the headline lint of the v9.2.0 cycle).
# A regression below this count means a test was deleted; a regression
# above means a test was added without bumping the W-17 ledger.
_V9_2_0_CAPABILITY_E2E_MIN_TESTS: int = 10


def test_v9_2_0_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v9.2.0: every NEW v9.2.0 surface has presence + import-smoke coverage.

    Discharges the W-18 precondition — every CHANGELOG entry mentioning
    a feature MUST have a backing ghost-audit lint in THIS file BEFORE
    the CHANGELOG entry is authored. v9.2.0 PV-06 (the sixth and
    headline PV of the cycle, the cycle rollup) introduces:

    1. ``install_local(*, with_examples: bool = False)`` kwarg in
       :mod:`devolaflow.init_project` plus the
       ``_seed_example_artifacts(cwd: Path) -> None`` helper. Closes
       G-006 deferred from the v9.1.0 retrospective §3.
    2. ``tests/test_capability_e2e.py`` (10 tests) — the cycle's
       headline lint that crosses every PV's deliverable through a
       tmp-path repo fixture. Closes G-015 deferred from the v9.1.0
       retrospective §3.

    Coverage matrix:

    1. **Presence** — each path in ``_V9_2_0_NEW_FILES`` is a regular
       file and its size is ``>= _V9_2_0_FILE_MIN_BYTES`` (1000 bytes
       — the e2e test file is the largest single new file in the
       cycle so the floor is intentionally above the 50-byte v9.1.5
       stub-guard).
    2. **Import-smoke (install_local)** — :func:`install_local` is
       importable from :mod:`devolaflow.init_project` AND its
       :func:`inspect.signature` reports ``with_examples`` as a
       keyword-only parameter with default ``False`` (the A-4 / W-20
       contract — additive opt-in, default OFF for compatibility).
    3. **Import-smoke (_seed_example_artifacts)** — the helper is
       importable from the same module and is callable.
    4. **Import-smoke (test_capability_e2e)** — the e2e test module
       importable AND its ``__all__`` lists ≥ 10 test functions
       (matches ``_V9_2_0_CAPABILITY_E2E_MIN_TESTS``); each name in
       ``__all__`` is a callable test function in the module.
    5. **W-20 reuse-first** — no new env-flag introduced (the
       v9.2.0 cycle plan §"Self-iteration constraint compliance
       matrix" pin "0 new flags across the entire 7-PV cycle" is
       upheld). The 5 env flags touched (DEVOLAFLOW_AGENT_WORKSPACE
       for PV-01/02/03; DEVOLAFLOW_MEMORY_ROUTER for PV-04;
       DEVOLAFLOW_AGENTS_MD_SLICE for PV-05) ALL existed before
       this cycle started.

    Failure modes:
      * "missing on disk" → a v9.2.0 surface was deleted or never
        landed; either restore it OR remove it from
        ``_V9_2_0_NEW_FILES`` if the surface was intentionally rolled
        back.
      * "< 1000 byte minimum" → the file regressed to a stub;
        re-author the contents.
      * "with_examples kwarg signature mismatch" → ``install_local``
        lost its ``with_examples`` keyword-only parameter or the
        default flipped from ``False``; restore the original
        signature OR document the operator-visible change with an
        ADR.
      * "_seed_example_artifacts not callable" → the seed helper
        regressed; restore it.
      * "< 10 test functions in test_capability_e2e __all__" → the
        cycle's headline lint regressed below the W-17 budget pin;
        restore the deleted test(s).
    """
    import inspect

    for relpath in _V9_2_0_NEW_FILES:
        full = project_root / relpath
        assert full.is_file(), (
            f"W-18 v9.2.0 violation: NEW v9.2.0 surface {relpath!r} missing on "
            f"disk — the CHANGELOG entry mentioning this feature MUST be backed "
            f"by a file that exists"
        )
        size = full.stat().st_size
        assert size >= _V9_2_0_FILE_MIN_BYTES, (
            f"W-18 v9.2.0 violation: NEW v9.2.0 surface {relpath!r} is {size} "
            f"bytes (< {_V9_2_0_FILE_MIN_BYTES} byte minimum); empty/stub files "
            f"do not satisfy the W-18 precondition"
        )

    # Import-smoke: install_local exists with the new with_examples
    # keyword-only parameter (default False).
    from devolaflow.init_project import _seed_example_artifacts, install_local

    sig = inspect.signature(install_local)
    assert "with_examples" in sig.parameters, (
        "W-18 v9.2.0 violation: install_local() lost its with_examples "
        "keyword-only parameter — the v9.2.0 PV-06 example-seed surface "
        "regressed; restore the kwarg per cycle plan §PV-06"
    )
    with_examples_param = sig.parameters["with_examples"]
    assert with_examples_param.kind == inspect.Parameter.KEYWORD_ONLY, (
        f"W-18 v9.2.0 violation: install_local(with_examples=...) must be "
        f"keyword-only (after the * marker); got kind={with_examples_param.kind!r}"
    )
    assert with_examples_param.default is False, (
        f"W-18 v9.2.0 violation: install_local(with_examples=...) default must "
        f"be False (additive opt-in for backward compatibility per W-20); got "
        f"default={with_examples_param.default!r}"
    )

    assert callable(_seed_example_artifacts), (
        "W-18 v9.2.0 violation: devolaflow.init_project._seed_example_artifacts "
        "is not callable — the seed helper regressed"
    )

    # Import-smoke: tests/test_capability_e2e.py module + __all__ lists
    # at least the W-17 budget pin of test functions.
    import tests.test_capability_e2e as e2e_module

    assert hasattr(e2e_module, "__all__"), (
        "W-18 v9.2.0 violation: tests/test_capability_e2e.py must declare "
        "__all__ with the cycle's headline test names (per cycle plan §PV-06 "
        "W-17 budget pin)"
    )
    e2e_tests = e2e_module.__all__
    assert len(e2e_tests) >= _V9_2_0_CAPABILITY_E2E_MIN_TESTS, (
        f"W-18 v9.2.0 violation: tests/test_capability_e2e.py.__all__ has "
        f"{len(e2e_tests)} entries; the cycle's W-17 budget pin requires at "
        f"least {_V9_2_0_CAPABILITY_E2E_MIN_TESTS} (per cycle plan §PV-06)"
    )
    for name in e2e_tests:
        assert callable(getattr(e2e_module, name, None)), (
            f"W-18 v9.2.0 violation: tests/test_capability_e2e.py.__all__ "
            f"entry {name!r} is not a callable test function in the module"
        )

    # W-20 reuse-first proof: PV-06 specifically does NOT introduce a
    # new DEVOLAFLOW_* env-flag. The seed helper writes static template
    # content + reads no env-vars — the entire flow is filesystem-only.
    init_module_path = project_root / "src" / "devolaflow" / "init_project.py"
    init_source = init_module_path.read_text(encoding="utf-8")
    assert "DEVOLAFLOW_" not in init_source, (
        "W-20 v9.2.0 violation: src/devolaflow/init_project.py introduced a "
        "new DEVOLAFLOW_* env-flag during PV-06 — the cycle plan §"
        '"Self-iteration constraint compliance matrix" pins "0 new flags '
        'across the entire 7-PV cycle". Either remove the new flag or '
        "document the W-20 §3 orthogonality argument in the PR body."
    )


# ---------------------------------------------------------------------------
# v9.2.0 PV-06 — supplementary lint for the W-19 cycle archive + the
# scripts/archive_research_artifacts.py --extra-prefix extension.
# ---------------------------------------------------------------------------
#
# The primary v9.2.0 ghost-audit ``test_v9_2_0_new_symbols_have_coverage``
# above pins the install_local(with_examples) kwarg + the
# tests/test_capability_e2e.py module ``__all__`` ≥ 10 + the W-20 reuse
# proof. This supplementary lint pins the OTHER PV-06 cycle-rollup
# surfaces — the W-19 archive directory presence and the
# scripts/archive_research_artifacts.py ``--extra-prefix`` flag the
# rollup invocation depends on. Splitting the audit into two test
# functions keeps each one focused on a single deliverable per the
# v8.0.0 retro §3.4 lesson "tests should be small + named after their
# specific contract".


def test_v9_2_0_cycle_archive_and_extra_prefix(project_root: Path) -> None:
    """W-18 v9.2.0: W-19 cycle archive directory + --extra-prefix flag wired.

    Pins the two cycle-rollup deliverables NOT covered by the primary
    ``test_v9_2_0_new_symbols_have_coverage`` lint:

    1. ``docs/cycle-archive/v9.2.0/`` directory exists with the W-19
       auto-generated ``README.md`` index AND the cycle's
       ``v9.2.0_retrospective.md`` copy. Both files are ≥ 200 bytes
       (catches an empty-stub regression that would silently pass a
       mere existence check).
    2. ``scripts/archive_research_artifacts.py`` exposes the
       ``--extra-prefix`` argparse flag AND the corresponding
       ``extra_prefixes`` kwarg on the ``archive(cycle_version, ...)``
       callable. Without this extension the cycle-rollup invocation
       ``archive_research_artifacts.py 9.2.0 --extra-prefix v9.1.``
       cannot capture both PATCH-cycle and MINOR-cycle research
       artefacts in a single run.

    Failure modes:
      * "v9.2.0 archive missing" → W-19 archive run was skipped or
        rolled back; re-run ``python scripts/archive_research_artifacts.py
        9.2.0 --extra-prefix v9.1.`` and commit the directory.
      * "no extra-prefix argument" → the v9.2.0 PV-06 archive-script
        extension was rolled back; restore it.
    """
    archive_dir = project_root / "docs" / "cycle-archive" / "v9.2.0"
    assert archive_dir.is_dir(), (
        f"W-18 v9.2.0 violation: W-19 cycle archive at "
        f"{archive_dir.relative_to(project_root)} missing — the cycle-rollup "
        f"CHANGELOG entry MUST be backed by a populated archive directory"
    )

    for relpath in (
        "docs/cycle-archive/v9.2.0/README.md",
        "docs/cycle-archive/v9.2.0/v9.2.0_retrospective.md",
    ):
        full = project_root / relpath
        assert full.is_file(), (
            f"W-18 v9.2.0 violation: required archive artefact {relpath!r} missing"
        )
        size = full.stat().st_size
        assert size >= 200, (
            f"W-18 v9.2.0 violation: archive artefact {relpath!r} is {size} "
            f"bytes (< 200 byte minimum); empty/stub files do not satisfy "
            f"the W-19 archive contract"
        )

    archive_script = project_root / "scripts" / "archive_research_artifacts.py"
    archive_text = archive_script.read_text(encoding="utf-8")
    assert "--extra-prefix" in archive_text, (
        "W-18 v9.2.0 violation: scripts/archive_research_artifacts.py must "
        "expose the --extra-prefix argparse flag (added v9.2.0 PV-06 to let "
        "the MINOR-cycle archive capture both v9.1.* and v9.2.* prefixes "
        "into docs/cycle-archive/v9.2.0/)"
    )
    assert "extra_prefixes" in archive_text, (
        "W-18 v9.2.0 violation: scripts/archive_research_artifacts.py::archive "
        "must accept an `extra_prefixes` kwarg (the runtime contract behind "
        "the --extra-prefix CLI flag)"
    )


# ---------------------------------------------------------------------------
# v9.2.1 PV-07 — ghost-audit for the self-update meta-validation PATCH.
# ---------------------------------------------------------------------------
#
# PV-07 ships as the final PV of the v9.2.0 cycle (PATCH sustaining that
# mirrors the v9.0.0 → v9.0.1 precedent). The cycle plan §PV-07 pins
# "zero new code paths introduced" — the deliverables are validation
# artefacts + minor test extensions ONLY:
#
# 1. tests/test_capability_e2e.py gains 4 NEW parametrized test functions
#    covering the 4 canonical consumer-repo fixture shapes (empty /
#    local-only / rules-only / full-stack). The __all__ list grows from
#    10 entries (v9.2.0 pin) to >= 14 entries (10 baseline + 4 PV-07).
# 2. .local/research/v9.2.1_{check_refs,nines_aggregate,validation_tasks,
#    integration_report,e2e_report,evaluation}.md ship as the self-update
#    workflow's 6 stage-output artefacts (plus the cycle-close
#    v9.2.1_nines.{json,md} pair per W-2). NB: these artefacts live
#    under .local/ which is gitignored; the W-19 re-archive to
#    docs/cycle-archive/v9.2.0/ is the committed counterpart. This lint
#    therefore checks the docs/cycle-archive/ copies (the canonical
#    tracked surface) rather than the gitignored .local/ originals.
# 3. The recursive-engagement proof — PV-07 opened
#    .local/.agent/active/v9.2.1-self-update-validation/ via the PV-02
#    /devola:propose surface and archived it at Stage 7 to
#    .local/.agent/archive/<YYYY-MM-DD>-v9.2.1-self-update-validation/.
#    Like (2) this lives under gitignored .local/; this lint asserts
#    presence when the workspace is live OR skips cleanly on a fresh
#    clone.

_V9_2_1_CAPABILITY_E2E_MIN_ENTRIES: int = 14


_V9_2_1_ARCHIVED_RESEARCH_FILES: tuple[str, ...] = (
    # scripts/archive_research_artifacts.py routes v9.2.1_nines*.{json,md}
    # to the nines/ subdir and evaluation/* to evaluation/; everything else
    # lands in other/. These per-subdir paths are the canonical post-run
    # locations for the 6 stage-output artefacts.
    "docs/cycle-archive/v9.2.0/other/v9.2.1_check_refs.md",
    "docs/cycle-archive/v9.2.0/nines/v9.2.1_nines_aggregate.md",
    "docs/cycle-archive/v9.2.0/other/v9.2.1_validation_tasks.md",
    "docs/cycle-archive/v9.2.0/other/v9.2.1_integration_report.md",
    "docs/cycle-archive/v9.2.0/other/v9.2.1_e2e_report.md",
    "docs/cycle-archive/v9.2.0/evaluation/v9.2.1_evaluation.md",
)


def test_v9_2_1_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v9.2.1: PV-07 meta-validation surfaces have presence + import-smoke coverage.

    Discharges the W-18 precondition for the v9.2.1 PATCH — every
    CHANGELOG entry mentioning a v9.2.1 feature MUST have a backing
    ghost-audit lint in THIS file BEFORE the CHANGELOG entry is authored.

    v9.2.1 PV-07 is the self-update meta-validation PATCH; by design
    it introduces **zero new code paths** (cycle plan §PV-07 verbatim).
    The surfaces this lint pins are therefore:

    1. ``tests/test_capability_e2e.py.__all__`` has ≥ 14 entries — the
       10 v9.2.0 headline tests + 4 NEW PV-07 parametrized tests. A
       regression below 14 means one of the PV-07 tests was deleted.
    2. Each of the 4 PV-07 test functions is a callable attribute of
       ``tests.test_capability_e2e``. Guards against a dangling
       ``__all__`` entry that references a deleted / renamed function.
    3. W-17 PV-07 budget proof — the 4 NEW test function names begin
       with ``test_pv07_`` so the cap-counting grep `git diff | grep
       "test_pv07_[a-z_]\\+("` matches exactly 4 lines in the PV-07
       diff.
    4. W-19 re-archive: when the consumer repo has run the post-PV-07
       re-archive (``scripts/archive_research_artifacts.py 9.2.0
       --extra-prefix v9.2.``), each of the 6 v9.2.1 research artefacts
       lands under ``docs/cycle-archive/v9.2.0/``. Self-skips when the
       archive directory lacks the v9.2.1 nested files (fresh clone
       that has not run the re-archive yet).

    Failure modes:
      * "< 14 entries in __all__" → a PV-07 test was deleted; restore it.
      * "PV-07 test not callable" → ``__all__`` drifted from module
        reality; fix the ``__all__`` list OR the missing function.
      * "archive artefact missing AND directory populated" → the
        re-archive ran but without the v9.2.* extra-prefix sweep;
        re-run ``python scripts/archive_research_artifacts.py 9.2.0
        --extra-prefix v9.2.``.
    """
    import tests.test_capability_e2e as e2e_module

    assert hasattr(e2e_module, "__all__"), (
        "W-18 v9.2.1 violation: tests/test_capability_e2e.py must declare "
        "__all__ with both the v9.2.0 headline names AND the v9.2.1 PV-07 "
        "multi-fixture tests"
    )
    all_names = e2e_module.__all__
    assert len(all_names) >= _V9_2_1_CAPABILITY_E2E_MIN_ENTRIES, (
        f"W-18 v9.2.1 violation: tests/test_capability_e2e.py.__all__ has "
        f"{len(all_names)} entries; the PV-07 extension requires at least "
        f"{_V9_2_1_CAPABILITY_E2E_MIN_ENTRIES} (10 v9.2.0 baseline + 4 PV-07)"
    )
    pv07_entries = [name for name in all_names if name.startswith("test_pv07_")]
    assert len(pv07_entries) >= 4, (
        f"W-18 v9.2.1 violation: tests/test_capability_e2e.py.__all__ must "
        f"carry at least 4 test_pv07_* entries (the PV-07 multi-fixture "
        f"E2E set); got {pv07_entries!r}"
    )
    for name in pv07_entries:
        target = getattr(e2e_module, name, None)
        assert callable(target), (
            f"W-18 v9.2.1 violation: tests/test_capability_e2e.py.__all__ "
            f"entry {name!r} is not a callable test function in the module"
        )

    archive_dir = project_root / "docs" / "cycle-archive" / "v9.2.0"
    if archive_dir.is_dir():
        for relpath in _V9_2_1_ARCHIVED_RESEARCH_FILES:
            full = project_root / relpath
            if not full.is_file():
                # Self-skip: the v9.2.0 archive exists but the v9.2.1
                # sweep has not run yet on this clone (pre-PV-07
                # re-archive state). Per W-19 the re-archive is
                # idempotent — run it once to populate.
                import pytest as _pytest

                _pytest.skip(
                    f"v9.2.1 archive artefact {relpath!r} not yet re-archived; "
                    f"run `python scripts/archive_research_artifacts.py 9.2.0 "
                    f"--extra-prefix v9.2.` to populate"
                )
            size = full.stat().st_size
            assert size >= 200, (
                f"W-18 v9.2.1 violation: archive artefact {relpath!r} is {size} "
                f"bytes (< 200 byte minimum); empty/stub files do not satisfy "
                f"the W-19 archive contract"
            )

    # No else branch: when `docs/cycle-archive/v9.2.0/` is absent the W-19
    # cycle archive has not been committed yet; the separate
    # `test_v9_2_0_cycle_archive_and_extra_prefix` lint fails loudly for
    # that case and this PV-07 lint stays permissive on the v9.2.1 half.


# ---------------------------------------------------------------------------
# v9.2.2 PV-01 — W-18 ghost-audit refresh for the I-001 critical CLI fix.
# ---------------------------------------------------------------------------
#
# v9.2.2 PV-01 is the first PV of the v9.2.2 PATCH cycle (3 PVs:
# v9.2.2 -> v9.2.3 -> v9.2.4) addressing the 4 issues catalogued in
# `.local/feedbacks/feedback_for_v9.2.1.md`. PV-01 ships:
#
# 1. NEW tests/test_init_project_pip_wheel.py — 6 NEW test functions
#    (one parametrized x4 = 9 test cases) pinning the deferred-check
#    surface, the informative error message, the `--list` regression,
#    the multi-target dispatch ordering invariant, the canonical
#    8-path scaffold smoke, and the no-pip-install-recommendation
#    regression lint.
# 2. EDIT src/devolaflow/init_project.py — surgical I-001 fix:
#    introduces `AGENT_DIR_REQUIRED_TARGETS` (frozenset) and defers
#    the SKILL.md existence check to inside the per-target dispatch
#    loop. `local` is exempt because `install_local` uses
#    `scaffold_local` + `importlib.resources`. The error message no
#    longer recommends `pip install devolaflow` (the misleading
#    recommendation that landed users in I-001).
# 3. EDIT workflow-system/agent/SKILL.md §"Version & Update" — I-004
#    one-line note about the wheel/CLI mismatch + `local` fallback.
#
# This W-18 refresh discharges the precondition: every CHANGELOG entry
# mentioning a v9.2.2 feature MUST have a backing ghost-audit lint in
# THIS file BEFORE the CHANGELOG entry is authored.

_V9_2_2_NEW_FILES: tuple[str, ...] = ("tests/test_init_project_pip_wheel.py",)


# Minimum byte size for a v9.2.2 NEW surface — guards against an empty
# stub silently slipping through and satisfying mere file-presence.
_V9_2_2_FILE_MIN_BYTES: int = 50


# The pip-wheel test file ships with EXACTLY 6 test FUNCTIONS per the
# PV-01 W-17 budget pin (one of which is parametrized x4 -> 9 cases at
# collection time). The function-count floor catches regression below
# the W-17 ledger; collection-time case count is intentionally NOT
# pinned because parametrize expansions don't count against the cap.
_V9_2_2_PIP_WHEEL_MIN_TEST_FUNCTIONS: int = 6


# AGENT_DIR_REQUIRED_TARGETS — the deferred-check gate surface. Pinning
# the exact membership here catches a silent widening / narrowing of
# which dispatch paths require the on-disk workflow-system/agent/ tree.
_V9_2_2_AGENT_DIR_REQUIRED_TARGETS: frozenset[str] = frozenset(
    {"cursor", "claude", "copilot", "codex"}
)


def test_v9_2_2_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v9.2.2: every NEW v9.2.2 surface has presence + import-smoke coverage.

    Discharges the W-18 precondition for the v9.2.2 PATCH — every
    CHANGELOG entry mentioning a v9.2.2 feature MUST have a backing
    ghost-audit lint in THIS file BEFORE the CHANGELOG entry is authored.

    v9.2.2 PV-01 is the I-001 critical-fix PV; the surfaces this lint
    pins are:

    1. ``tests/test_init_project_pip_wheel.py`` exists on disk and
       carries ≥ 6 test FUNCTIONS (the PV-01 W-17 budget pin —
       parametrize expansions don't count against the cap, so the floor
       is on the ``def test_*`` count, not the collection-time case
       count).
    2. ``AGENT_DIR_REQUIRED_TARGETS`` is importable from
       :mod:`devolaflow.init_project`, equals exactly the 4-element
       frozenset ``{"cursor", "claude", "copilot", "codex"}``, and does
       NOT contain ``"local"`` (the I-001 closure invariant —
       ``install_local`` uses ``scaffold_local`` + ``importlib.resources``
       and has zero dependency on ``agent_dir``).

    Failure modes:
      * "missing on disk" → a v9.2.2 surface was deleted or never
        landed; either restore it OR remove it from
        ``_V9_2_2_NEW_FILES`` if the surface was intentionally rolled
        back.
      * "< 50 byte minimum" → the file regressed to an empty stub;
        re-author the contents.
      * "AGENT_DIR_REQUIRED_TARGETS membership drift" → the deferred-
        check surface was silently widened or narrowed; either restore
        the original 4-element set OR document the operator-visible
        change with an ADR.
      * "test function count regressed" → a PV-01 test was deleted;
        restore it.
    """
    import ast

    for relpath in _V9_2_2_NEW_FILES:
        full = project_root / relpath
        assert full.is_file(), (
            f"W-18 v9.2.2 violation: NEW v9.2.2 surface {relpath!r} missing on "
            f"disk — the CHANGELOG entry mentioning this feature MUST be backed "
            f"by a file that exists"
        )
        size = full.stat().st_size
        assert size >= _V9_2_2_FILE_MIN_BYTES, (
            f"W-18 v9.2.2 violation: NEW v9.2.2 surface {relpath!r} is {size} "
            f"bytes (< {_V9_2_2_FILE_MIN_BYTES} byte minimum); empty/stub "
            f"files do not satisfy the W-18 precondition"
        )

    pip_wheel_test_file = project_root / "tests" / "test_init_project_pip_wheel.py"
    pip_wheel_ast = ast.parse(pip_wheel_test_file.read_text(encoding="utf-8"))
    test_functions = [
        node
        for node in pip_wheel_ast.body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    ]
    assert len(test_functions) >= _V9_2_2_PIP_WHEEL_MIN_TEST_FUNCTIONS, (
        f"W-18 v9.2.2 violation: tests/test_init_project_pip_wheel.py declares "
        f"{len(test_functions)} test_* functions; the PV-01 W-17 budget pin "
        f"requires at least {_V9_2_2_PIP_WHEEL_MIN_TEST_FUNCTIONS}"
    )

    from devolaflow.init_project import AGENT_DIR_REQUIRED_TARGETS

    assert AGENT_DIR_REQUIRED_TARGETS == _V9_2_2_AGENT_DIR_REQUIRED_TARGETS, (
        f"W-18 v9.2.2 violation: AGENT_DIR_REQUIRED_TARGETS = "
        f"{AGENT_DIR_REQUIRED_TARGETS!r}; expected "
        f"{_V9_2_2_AGENT_DIR_REQUIRED_TARGETS!r} (exactly the 4 historical "
        f"agent-dir consumers — cursor / claude / copilot / codex). "
        f"`local` is intentionally absent — the I-001 closure invariant"
    )
    assert "local" not in AGENT_DIR_REQUIRED_TARGETS, (
        "W-18 v9.2.2 violation: `local` MUST NOT appear in "
        "AGENT_DIR_REQUIRED_TARGETS — install_local uses scaffold_local + "
        "importlib.resources and has ZERO dependency on agent_dir. "
        "Adding `local` here would re-introduce the I-001 abort scenario "
        "for wheel-only installs."
    )
    assert isinstance(AGENT_DIR_REQUIRED_TARGETS, frozenset), (
        f"W-18 v9.2.2 violation: AGENT_DIR_REQUIRED_TARGETS must be a "
        f"frozenset (immutable surface); got "
        f"{type(AGENT_DIR_REQUIRED_TARGETS).__name__!r}"
    )


def test_v9_2_2_local_target_no_workflow_system_dependency(project_root: Path) -> None:
    """W-18 v9.2.2: install_local body MUST NOT reference agent_dir.

    The I-001 closure invariant — ``install_local`` is the ONE per-target
    installer that does NOT consume ``agent_dir``. The deferred-check
    fix relies on this invariant: if ``install_local`` ever starts
    reading from ``agent_dir`` (e.g. copying a file from
    ``agent_dir / "templates" / "..."``), the I-001 abort scenario
    re-emerges for wheel-only installs even when the user explicitly
    requests ``devola-init local``.

    This lint walks the ``install_local`` function body via AST and
    asserts no ``Name`` node references the ``agent_dir`` parameter
    (other than the parameter declaration itself, which the AST walk
    distinguishes via ``ast.arg`` vs ``ast.Name``).

    Failure modes:
      * "install_local body references agent_dir" → the agent-dir-
        independence invariant regressed; either remove the new
        agent_dir reference (recommended) OR add ``"local"`` to
        ``AGENT_DIR_REQUIRED_TARGETS`` AND update the W-18 v9.2.2
        ghost-audit lint above to reflect the operator-visible change.
        The latter path RE-INTRODUCES the I-001 wheel-install regression
        and requires explicit ADR documentation per W-21 governance.
    """
    import ast

    init_module_path = project_root / "src" / "devolaflow" / "init_project.py"
    tree = ast.parse(init_module_path.read_text(encoding="utf-8"))

    install_local_node = next(
        (
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "install_local"
        ),
        None,
    )
    assert install_local_node is not None, (
        "W-18 v9.2.2 violation: install_local function definition missing "
        "from src/devolaflow/init_project.py — the I-001 fix depends on this "
        "function existing as the agent-dir-independent installer"
    )

    agent_dir_references: list[ast.Name] = []
    for child in ast.walk(install_local_node):
        if isinstance(child, ast.Name) and child.id == "agent_dir":
            agent_dir_references.append(child)

    assert agent_dir_references == [], (
        f"W-18 v9.2.2 violation: install_local body references `agent_dir` "
        f"on lines {[n.lineno for n in agent_dir_references]} — the I-001 "
        f"closure invariant requires install_local to be agent-dir-"
        f"independent (uses scaffold_local + importlib.resources only). "
        f"If a new agent_dir consumer was intentionally added, also "
        f"register `local` in AGENT_DIR_REQUIRED_TARGETS (which RE-INTRODUCES "
        f"the I-001 wheel-install scenario for `devola-init local`) and "
        f"document the operator-visible change with an ADR."
    )


# ---------------------------------------------------------------------------
# v9.2.3 PV-02 — W-18 ghost-audit refresh for the DX-improvement cluster.
# ---------------------------------------------------------------------------
#
# v9.2.3 PV-02 is the second PV of the v9.2.2 PATCH cycle (3 PVs:
# v9.2.2 → v9.2.3 → v9.2.4). PV-02 ships:
#
# 1. NEW tests/test_scaffold_gitignore_audit.py — 6 NEW test functions
#    pinning the I-003 `_audit_gitignore_coverage` surface in
#    `src/devolaflow/local/workspace.py` (logs WARN per scaffold path
#    that an existing .gitignore rule already covers; quiet on
#    absent / unrelated rules; conservative on negation rules).
# 2. NEW tests/test_init_project_mode_flag.py — 5 NEW test functions
#    pinning the `--mode={core,standard,full}` shorthand surface
#    + the explicit-beats-implicit precedence rule + the invalid-mode
#    exit path.
# 3. EDIT src/devolaflow/local/workspace.py — added `_read_gitignore_rules`,
#    `_path_matches_gitignore`, `_audit_gitignore_coverage` helpers,
#    `last_gitignore_audit` accessor, and integrated the audit at the
#    tail of `scaffold_local`.
# 4. EDIT src/devolaflow/init_project.py — added `VALID_MODES` constant,
#    `_parse_mode` resolver, and the mode-derived default wiring in
#    `main()`. `_parse_no_compile` + `_parse_with_examples` gained
#    keyword-only `default=` kwargs (backward-compat preserved by the
#    default value on each).
# 5. EDIT README.md — new "Troubleshooting installs" subsection
#    documenting I-002 (baidubce mirror), I-001 closure (v9.2.2), and
#    the `--mode=core` shorthand discovery hint.
# 6. EDIT workflow-system/agent/SKILL.md §"Version & Update" —
#    install note refreshed to cite v9.2.3 `--mode=core` shorthand.
#
# This W-18 refresh discharges the precondition: every CHANGELOG entry
# mentioning a v9.2.3 feature MUST have a backing ghost-audit lint in
# THIS file BEFORE the CHANGELOG entry is authored.

_V9_2_3_NEW_FILES: tuple[str, ...] = (
    "tests/test_scaffold_gitignore_audit.py",
    "tests/test_init_project_mode_flag.py",
)


# Minimum byte size for a v9.2.3 NEW surface — guards against an empty
# stub silently slipping through and satisfying mere file-presence.
_V9_2_3_FILE_MIN_BYTES: int = 50


# Test-function floor per file — pinned by the dispatch's PV-02 budget
# (5 named acceptance tests + 1 helper-edge-cases on the gitignore side;
# 5 named acceptance tests on the mode side).
_V9_2_3_GITIGNORE_MIN_TEST_FUNCTIONS: int = 5


_V9_2_3_MODE_MIN_TEST_FUNCTIONS: int = 5


# VALID_MODES — the `--mode=` shorthand surface. Pinning the exact
# membership here catches a silent widening (e.g. a new mode added
# without operator-facing docs) or narrowing (e.g. a mode dropped
# without a deprecation cycle).
_V9_2_3_VALID_MODES: frozenset[str] = frozenset({"core", "standard", "full"})


def test_v9_2_3_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v9.2.3: every NEW v9.2.3 surface has presence + import-smoke coverage.

    Discharges the W-18 precondition for the v9.2.3 PATCH — every
    CHANGELOG entry mentioning a v9.2.3 feature MUST have a backing
    ghost-audit lint in THIS file BEFORE the CHANGELOG entry is authored.

    v9.2.3 PV-02 surfaces this lint pins:

    1. ``tests/test_scaffold_gitignore_audit.py`` and
       ``tests/test_init_project_mode_flag.py`` exist on disk and
       carry ≥ 5 test FUNCTIONS each (the PV-02 dispatch budget pin —
       parametrize expansions don't count against the cap).
    2. ``_audit_gitignore_coverage`` and ``last_gitignore_audit`` are
       importable from :mod:`devolaflow.local.workspace`.
    3. ``_parse_mode`` and ``VALID_MODES`` are importable from
       :mod:`devolaflow.init_project`, and ``VALID_MODES`` equals
       exactly the 3-element frozenset
       ``{"core", "standard", "full"}``.

    Failure modes:
      * "missing on disk" → a v9.2.3 surface was deleted or never
        landed; either restore it OR remove it from
        ``_V9_2_3_NEW_FILES`` if the surface was intentionally rolled
        back.
      * "< 50 byte minimum" → the file regressed to an empty stub;
        re-author the contents.
      * "VALID_MODES membership drift" → the `--mode=` surface was
        silently widened or narrowed; either restore the original
        3-element set OR document the operator-visible change with
        an ADR.
      * "test function count regressed" → a PV-02 test was deleted;
        restore it.
    """
    import ast

    for relpath in _V9_2_3_NEW_FILES:
        full = project_root / relpath
        assert full.is_file(), (
            f"W-18 v9.2.3 violation: NEW v9.2.3 surface {relpath!r} missing on "
            f"disk — the CHANGELOG entry mentioning this feature MUST be backed "
            f"by a file that exists"
        )
        size = full.stat().st_size
        assert size >= _V9_2_3_FILE_MIN_BYTES, (
            f"W-18 v9.2.3 violation: NEW v9.2.3 surface {relpath!r} is {size} "
            f"bytes (< {_V9_2_3_FILE_MIN_BYTES} byte minimum); empty/stub "
            f"files do not satisfy the W-18 precondition"
        )

    gitignore_test_file = project_root / "tests" / "test_scaffold_gitignore_audit.py"
    gitignore_ast = ast.parse(gitignore_test_file.read_text(encoding="utf-8"))
    gitignore_test_functions = [
        node
        for node in gitignore_ast.body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    ]
    assert len(gitignore_test_functions) >= _V9_2_3_GITIGNORE_MIN_TEST_FUNCTIONS, (
        f"W-18 v9.2.3 violation: tests/test_scaffold_gitignore_audit.py "
        f"declares {len(gitignore_test_functions)} test_* functions; the "
        f"PV-02 dispatch budget pin requires at least "
        f"{_V9_2_3_GITIGNORE_MIN_TEST_FUNCTIONS}"
    )

    mode_test_file = project_root / "tests" / "test_init_project_mode_flag.py"
    mode_ast = ast.parse(mode_test_file.read_text(encoding="utf-8"))
    mode_test_functions = [
        node
        for node in mode_ast.body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    ]
    assert len(mode_test_functions) >= _V9_2_3_MODE_MIN_TEST_FUNCTIONS, (
        f"W-18 v9.2.3 violation: tests/test_init_project_mode_flag.py "
        f"declares {len(mode_test_functions)} test_* functions; the "
        f"PV-02 dispatch budget pin requires at least "
        f"{_V9_2_3_MODE_MIN_TEST_FUNCTIONS}"
    )

    from devolaflow.init_project import VALID_MODES, _parse_mode
    from devolaflow.local.workspace import (
        _audit_gitignore_coverage,
        last_gitignore_audit,
    )

    assert callable(_audit_gitignore_coverage), (
        "W-18 v9.2.3 violation: _audit_gitignore_coverage must be importable "
        "from devolaflow.local.workspace"
    )
    assert callable(last_gitignore_audit), (
        "W-18 v9.2.3 violation: last_gitignore_audit accessor must be importable "
        "from devolaflow.local.workspace"
    )
    assert callable(_parse_mode), (
        "W-18 v9.2.3 violation: _parse_mode must be importable from devolaflow.init_project"
    )

    assert VALID_MODES == _V9_2_3_VALID_MODES, (
        f"W-18 v9.2.3 violation: VALID_MODES = {VALID_MODES!r}; expected "
        f"exactly {_V9_2_3_VALID_MODES!r} (the 3-mode dispatch contract: "
        f"core / standard / full)"
    )
    assert isinstance(VALID_MODES, frozenset), (
        f"W-18 v9.2.3 violation: VALID_MODES must be a frozenset (immutable "
        f"surface); got {type(VALID_MODES).__name__!r}"
    )


def test_v9_2_3_mode_flag_surface_complete(project_root: Path) -> None:
    """W-18 v9.2.3: `_parse_mode` returns one of {core, standard, full, None}.

    AST walk over `_parse_mode` asserts the function body's `return`
    statements yield only valid mode strings (the elements of
    `VALID_MODES`) or `None`. A future PV that introduces a 4th mode
    MUST also update `VALID_MODES` AND this lint's expected set —
    catching a regression where the parser silently accepts a value
    that the docstring + README never advertised.
    """
    import ast

    init_module_path = project_root / "src" / "devolaflow" / "init_project.py"
    tree = ast.parse(init_module_path.read_text(encoding="utf-8"))

    parse_mode_node = next(
        (
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "_parse_mode"
        ),
        None,
    )
    assert parse_mode_node is not None, (
        "W-18 v9.2.3 violation: _parse_mode function definition missing "
        "from src/devolaflow/init_project.py — the PV-02 mode shorthand "
        "depends on this resolver existing"
    )

    # Walk the body; collect every `return <expr>` and assert each one
    # is either `return None`, `return mode` (the validated variable),
    # or `return <Name>` referring to one of the local mode-derivation
    # variables. The intent: the function must NEVER return a literal
    # string outside VALID_MODES (catches a silent widening like
    # `return "lite"` slipped into the body).
    return_nodes = [node for node in ast.walk(parse_mode_node) if isinstance(node, ast.Return)]
    assert len(return_nodes) >= 2, (
        f"W-18 v9.2.3 violation: _parse_mode must have ≥ 2 return statements "
        f"(the None-fallback + the validated mode return); got "
        f"{len(return_nodes)}"
    )

    for ret in return_nodes:
        if ret.value is None:
            continue  # bare `return` — equivalent to `return None`, fine
        if isinstance(ret.value, ast.Constant) and ret.value.value is None:
            continue  # `return None`
        if isinstance(ret.value, ast.Name):
            continue  # `return mode` (validated variable) — fine
        if (
            isinstance(ret.value, ast.Constant)
            and isinstance(ret.value.value, str)
            and ret.value.value in {"core", "standard", "full"}
        ):
            continue
        raise AssertionError(
            f"W-18 v9.2.3 violation: _parse_mode returns an unexpected "
            f"expression at line {ret.lineno}: {ast.dump(ret.value)!r}. "
            f"Expected `return None` or `return <variable>` or `return "
            f'"core"/"standard"/"full"`. Adding a new mode requires '
            f"updating BOTH VALID_MODES AND this lint's expected set."
        )


# ---------------------------------------------------------------------------
# v9.2.4 PV-03 — W-18 ghost-audit refresh for the cycle-close validation.
# ---------------------------------------------------------------------------
#
# v9.2.4 PV-03 is the FINAL PV of the v9.2.2 PATCH cycle (3 PVs:
# v9.2.2 -> v9.2.3 -> v9.2.4). PV-03 ships ZERO new code paths — only
# cycle-close validation artefacts:
#
# 1. EXTEND tests/test_init_project_pip_wheel.py with
#    test_cycle_close_e2e_local_mode_core_works — parametrized across
#    4 fixture shapes (empty / with_gitignore_local / with_gitignore_all /
#    full_pip_wheel_install). Each shape validates: `devola-init local
#    --mode=core` exits 0; 8 canonical paths created; --mode=core implies
#    --no-compile so cursor-rules + AGENTS.md compile artefacts NOT
#    written; gitignore-covered paths emit per-path WARN; absent /
#    unrelated rules emit ZERO WARN.
#
# 2. NEW .local/research/v9.2.2_retrospective.md — W-7 / SI-8 cycle-
#    close retrospective with the 4 mandatory sections (Gaps Identified
#    / What was Implemented / What was Deferred / Key Learnings) +
#    the W-21 Soul-set freeze telegraph for v9.4.0.
#
# 3. W-19 archive refresh: docs/cycle-archive/v9.2.0/ now contains
#    v9.2.2_retrospective.md (post `python scripts/archive_research_artifacts.py
#    9.2.0 --extra-prefix v9.2.`), making the retrospective accessible
#    from a fresh clone (where .local/ is gitignored).
#
# This W-18 refresh discharges the precondition: every CHANGELOG entry
# mentioning a v9.2.4 feature MUST have a backing ghost-audit lint in
# THIS file BEFORE the CHANGELOG entry is authored.

# The 4 mandatory W-7 retrospective section headings — must ALL appear
# in the retrospective for it to be a valid W-7 / SI-8 artefact.
_V9_2_4_W7_MANDATORY_SECTIONS: tuple[str, ...] = (
    "## 1. Gaps identified",
    "## 2. What was implemented",
    "## 3. What was deferred and why",
    "## 4. Key learnings",
)


# The exact parametrize cardinality on the cycle-close E2E test —
# pinned by the cycle plan §PV-03 contract (4 representative install
# fixture shapes). A future PV that drops a shape MUST update this
# constant + document the operator-visible scope reduction.
_V9_2_4_E2E_PARAMETRIZE_CASES: int = 4


_V9_2_4_E2E_FIXTURE_SHAPES: frozenset[str] = frozenset(
    {"empty", "with_gitignore_local", "with_gitignore_all", "full_pip_wheel_install"}
)


def test_v9_2_4_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v9.2.4: every NEW v9.2.4 surface has presence + structural coverage.

    Discharges the W-18 precondition for the v9.2.4 cycle-close PATCH —
    every CHANGELOG entry mentioning a v9.2.4 feature MUST have a
    backing ghost-audit lint in THIS file BEFORE the CHANGELOG entry
    is authored.

    v9.2.4 PV-03 surfaces this lint pins:

    1. ``.local/research/v9.2.2_retrospective.md`` exists (the
       canonical write-target — gitignored on most clones, so we
       prefer the W-19 archive copy under ``docs/cycle-archive/v9.2.0/``
       for the load-bearing assertion below) and contains all 4 W-7
       mandatory section headings.
    2. ``tests/test_init_project_pip_wheel.py`` declares
       ``test_cycle_close_e2e_local_mode_core_works`` and parametrizes
       it across exactly 4 fixture shapes (the cycle plan §PV-03
       contract — empty / with_gitignore_local / with_gitignore_all /
       full_pip_wheel_install).
    3. ``docs/cycle-archive/v9.2.0/v9.2.2_retrospective.md`` exists
       (the W-19 archive contract — PATCH series rolls into the parent
       MINOR cycle archive), making the retrospective visible to a
       fresh-clone reviewer who doesn't carry ``.local/``.

    Failure modes:
      * "retrospective missing on disk" → the W-7 / SI-8 artefact was
        not authored; cycle-close PATCH is incomplete.
      * "missing mandatory section heading" → the retrospective is
        partial; W-7 §"4 mandatory sections" requires ALL of Gaps /
        Implemented / Deferred / Learnings.
      * "parametrize cardinality drift" → the cycle-close E2E lost
        a fixture shape; either restore it OR update both the cycle
        plan §PV-03 contract AND this lint's pinned constant.
      * "archive missing the retrospective" → run
        ``python scripts/archive_research_artifacts.py 9.2.0
        --extra-prefix v9.2.`` to populate (idempotent).
    """
    import ast

    archived_retrospective = (
        project_root / "docs" / "cycle-archive" / "v9.2.0" / "v9.2.2_retrospective.md"
    )
    assert archived_retrospective.is_file(), (
        f"W-18 v9.2.4 violation: W-19 archive contract — "
        f"{archived_retrospective.relative_to(project_root)} missing. "
        f"Run `python scripts/archive_research_artifacts.py 9.2.0 "
        f"--extra-prefix v9.2.` to populate (idempotent)."
    )
    archived_size = archived_retrospective.stat().st_size
    assert archived_size >= 1000, (
        f"W-18 v9.2.4 violation: archived retrospective is "
        f"{archived_size} bytes (< 1000 byte minimum); empty/stub "
        f"retrospective does not satisfy the W-7 4-section contract"
    )

    archived_text = archived_retrospective.read_text(encoding="utf-8")
    for heading in _V9_2_4_W7_MANDATORY_SECTIONS:
        assert heading in archived_text, (
            f"W-18 v9.2.4 violation: retrospective missing mandatory "
            f"W-7 section heading {heading!r}; the W-7 / SI-8 contract "
            f"requires ALL of {list(_V9_2_4_W7_MANDATORY_SECTIONS)!r}"
        )

    pip_wheel_test_file = project_root / "tests" / "test_init_project_pip_wheel.py"
    pip_wheel_ast = ast.parse(pip_wheel_test_file.read_text(encoding="utf-8"))
    e2e_node = next(
        (
            node
            for node in pip_wheel_ast.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "test_cycle_close_e2e_local_mode_core_works"
        ),
        None,
    )
    assert e2e_node is not None, (
        "W-18 v9.2.4 violation: tests/test_init_project_pip_wheel.py "
        "MUST declare test_cycle_close_e2e_local_mode_core_works; the "
        "cycle plan §PV-03 contract requires this multi-fixture E2E "
        "validation surface"
    )

    parametrize_decorators = [
        dec
        for dec in e2e_node.decorator_list
        if (
            isinstance(dec, ast.Call)
            and isinstance(dec.func, ast.Attribute)
            and dec.func.attr == "parametrize"
        )
    ]
    assert len(parametrize_decorators) == 1, (
        f"W-18 v9.2.4 violation: test_cycle_close_e2e_local_mode_core_works "
        f"must carry exactly ONE @pytest.mark.parametrize decorator; "
        f"got {len(parametrize_decorators)}"
    )

    parametrize_call = parametrize_decorators[0]
    shape_list_arg = parametrize_call.args[1] if len(parametrize_call.args) >= 2 else None
    assert shape_list_arg is not None and isinstance(shape_list_arg, ast.List), (
        "W-18 v9.2.4 violation: parametrize values argument must be a "
        "literal list of fixture shapes"
    )
    shape_values = {
        elt.value
        for elt in shape_list_arg.elts
        if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
    }
    assert len(shape_values) == _V9_2_4_E2E_PARAMETRIZE_CASES, (
        f"W-18 v9.2.4 violation: cycle plan §PV-03 contract requires "
        f"exactly {_V9_2_4_E2E_PARAMETRIZE_CASES} parametrize cases on "
        f"test_cycle_close_e2e_local_mode_core_works; got "
        f"{len(shape_values)} ({sorted(shape_values)!r})"
    )
    assert shape_values == _V9_2_4_E2E_FIXTURE_SHAPES, (
        f"W-18 v9.2.4 violation: parametrize fixture shapes drifted "
        f"from the cycle plan §PV-03 contract. Got {sorted(shape_values)!r}; "
        f"expected exactly {sorted(_V9_2_4_E2E_FIXTURE_SHAPES)!r}"
    )

    # The .local/research/ retrospective is the canonical write-target
    # but is gitignored on most clones. Skip the local-presence assertion
    # gracefully when the file is absent — the load-bearing W-7 contract
    # was already verified above against the archived copy under
    # docs/cycle-archive/v9.2.0/, which IS committed.
    local_retrospective = project_root / ".local" / "research" / "v9.2.2_retrospective.md"
    if local_retrospective.is_file():
        # When present, the local copy MUST match the same 4-section
        # contract (catches a future bug where the local + archived
        # copies drift apart).
        local_text = local_retrospective.read_text(encoding="utf-8")
        local_rel = local_retrospective.relative_to(project_root)
        for heading in _V9_2_4_W7_MANDATORY_SECTIONS:
            assert heading in local_text, (
                f"W-18 v9.2.4 violation: local retrospective {local_rel} "
                f"is missing mandatory section heading {heading!r}; "
                f"the local + archived copies have drifted (re-run "
                f"`python scripts/archive_research_artifacts.py 9.2.0 "
                f"--extra-prefix v9.2.` to refresh the archive)"
            )
