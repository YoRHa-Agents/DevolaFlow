"""Ghost audit — per-cycle W-18 feature stanzas for the v9.1 cycle.

Split from ``tests/test_no_ghost_features.py`` per v15-ADR-001
(v14.3.0). New W-18 stanzas for a v9.1.x release append HERE; the
next MINOR cycle rotates to a fresh ``test_features_v<MAJ>_<MIN>.py``.
"""

from __future__ import annotations

from pathlib import Path

from tests.ghost._helpers import _load_yaml, _read

# ── v9.1.0 W3-04 — W-18 ghost-audit refresh for v9.1.0 NEW symbols ────
# Per Workflow Rule W-18 (`.rules/workflow.mdc` §W-18), every CHANGELOG
# entry mentioning a feature MUST have a corresponding ghost-audit lint
# in this file BEFORE the CHANGELOG entry is authored. v9.1.0 introduces
# the surfaces below; this block adds presence + import-smoke + signature
# coverage for all of them as the W-18 PRECONDITION discharge:
#
#   * src/devolaflow/lifecycle/check_envelope_append_only.py — new module
#     binding the S-9 invariant (handoff envelopes are append-only) to
#     the `envelope_write` lifecycle event.
#   * lifecycle/ENVELOPE_WRITE_EVENT — new exported event constant
#     (canonical name `"envelope_write"`).
#   * lifecycle/DEFAULT_EVENTS keeps envelope_write at position 6 in the
#     post-v22 live tuple after the retired pre_shell_call event is removed.
#   * tests/test_handoff_envelope_immutable.py — new test file pinning
#     the S-9 invariant against the envelope writer.
#   * tests/test_lifecycle_envelope_append_only.py — new test file
#     covering the envelope-write hook unit semantics.
#   * tests/test_rules_index_accuracy.py — new test file covering the
#     G-013 lint (rules index accuracy).
#   * tests/test_local_layer_completeness.py — new test file covering
#     the G-014 lint (local-layer completeness audit).
#   * init_project.install_local(compile_rules=True) — new keyword-only
#     parameter wired to the `--no-compile` CLI flag (closes G-007 +
#     G-016: `devola-init local` now auto-compiles `.rules/` →
#     `.cursor/rules/repo-governance.mdc` + `AGENTS.md` immediately).

_V9_1_0_NEW_FILES: tuple[str, ...] = (
    "src/devolaflow/lifecycle/check_envelope_append_only.py",
    "tests/test_handoff_envelope_immutable.py",
    "tests/test_lifecycle_envelope_append_only.py",
    "tests/test_rules_index_accuracy.py",
    "tests/test_local_layer_completeness.py",
)


# Minimum byte size for a v9.1.0 NEW surface — guards against an empty
# stub silently slipping through and satisfying mere file-presence.
_V9_1_0_FILE_MIN_BYTES: int = 50


# Expected DEFAULT_EVENTS tuple length floor after the v9.1.0 W1-02 bump.
# Before W1-02: 5 (pre_dispatch, post_dispatch, file_write, task_stop,
# format_on_edit). The post-v22 live tuple keeps envelope_write at
# position 6 after removing pre_shell_call. Future PVs
# may append additional events at the tail (e.g. v9.1.3 PV-03 appended
# `pre_handoff` at position 8); the v9.1.0 invariant is that
# envelope_write STAYS at position 7 — this lint asserts the floor +
# the position pin, NOT exact equality on length.
_V9_1_0_DEFAULT_EVENTS_COUNT: int = 6


def test_v9_1_0_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v9.1.0: every NEW v9.1.0 surface has presence + import-smoke coverage.

    Discharges the W-18 precondition — every CHANGELOG entry mentioning
    a feature MUST have a backing ghost-audit lint in THIS file BEFORE
    the CHANGELOG entry is authored. v9.1.0 introduces the surfaces
    enumerated in the comment block above this test; this lint asserts
    each one as a cheap presence + import-smoke check.

    Coverage matrix:

    1. **Presence** — each path in ``_V9_1_0_NEW_FILES`` is a regular
       file and its size is ``>= _V9_1_0_FILE_MIN_BYTES`` (50 bytes —
       guards against an empty stub silently slipping through).
    2. **Import-smoke** — ``ENVELOPE_WRITE_EVENT`` and
       ``check_envelope_append_only`` are importable from
       :mod:`devolaflow.lifecycle` and the event constant equals
       ``"envelope_write"`` (the canonical name re-exported from
       :mod:`devolaflow.lifecycle.check_envelope_append_only`).
    3. **DEFAULT_EVENTS** tuple length is at least
       ``_V9_1_0_DEFAULT_EVENTS_COUNT`` (6 — the live post-v22 tuple
       keeps ``envelope_write`` at position 6 after removing
       ``pre_shell_call``) and contains
       ``ENVELOPE_WRITE_EVENT``.

    Failure modes:
      * "missing on disk" → a v9.1.0 surface was deleted or never
        landed; either restore it OR remove it from
        ``_V9_1_0_NEW_FILES`` if the surface was intentionally rolled
        back.
      * "< 50 byte minimum" → the file regressed to an empty stub;
        re-author the contents.
      * "DEFAULT_EVENTS lost envelope_write" → the lifecycle event tuple
        was edited in violation of the post-v22 ordering; verify
        ``envelope_write`` remains at position 6.
    """
    for relpath in _V9_1_0_NEW_FILES:
        full = project_root / relpath
        assert full.is_file(), (
            f"W-18 v9.1.0 violation: NEW v9.1.0 surface {relpath!r} missing on "
            f"disk — the CHANGELOG entry mentioning this feature MUST be backed "
            f"by a file that exists"
        )
        size = full.stat().st_size
        assert size >= _V9_1_0_FILE_MIN_BYTES, (
            f"W-18 v9.1.0 violation: NEW v9.1.0 surface {relpath!r} is {size} "
            f"bytes (< {_V9_1_0_FILE_MIN_BYTES} byte minimum); empty/stub files "
            f"do not satisfy the W-18 precondition"
        )

    from devolaflow.lifecycle import (
        DEFAULT_EVENTS,
        ENVELOPE_WRITE_EVENT,
        check_envelope_append_only,
    )

    assert ENVELOPE_WRITE_EVENT == "envelope_write", (
        f"W-18 v9.1.0 violation: ENVELOPE_WRITE_EVENT exported value "
        f"{ENVELOPE_WRITE_EVENT!r} != 'envelope_write' (the canonical event "
        f"name from check_envelope_append_only.EVENT)"
    )
    assert callable(check_envelope_append_only), (
        "W-18 v9.1.0 violation: check_envelope_append_only is not callable — "
        "the export from devolaflow.lifecycle must be the hook function itself"
    )
    assert len(DEFAULT_EVENTS) >= _V9_1_0_DEFAULT_EVENTS_COUNT, (
        f"W-18 v9.1.0 violation: lifecycle.DEFAULT_EVENTS length is "
        f"{len(DEFAULT_EVENTS)}, expected ≥ {_V9_1_0_DEFAULT_EVENTS_COUNT} "
        f"(v9.1.0 W1-02 bumped 6 → 7 with envelope_write APPENDED at "
        f"position 7 per A-2.4 cache-prefix invariant). Current events: "
        f"{DEFAULT_EVENTS!r}"
    )
    assert ENVELOPE_WRITE_EVENT in DEFAULT_EVENTS, (
        f"W-18 v9.1.0 violation: ENVELOPE_WRITE_EVENT not registered in "
        f"DEFAULT_EVENTS tuple {DEFAULT_EVENTS!r} — the W1-02 append step "
        f"was incomplete"
    )
    # Current live position after v22 removed pre_shell_call.
    assert DEFAULT_EVENTS[5] == ENVELOPE_WRITE_EVENT, (
        f"Lifecycle re-numbering violation: envelope_write must be at "
        f"position 6 after v22 removed pre_shell_call. Got "
        f"DEFAULT_EVENTS[5]={DEFAULT_EVENTS[5]!r}; full tuple: {DEFAULT_EVENTS!r}"
    )


def test_install_local_has_compile_rules_kwarg() -> None:
    """W-18 v9.1.0: install_local() exposes the compile_rules keyword.

    Asserts the v9.1.0 W2-02 (G-007 + G-016 closure) signature change:
    :func:`devolaflow.init_project.install_local` MUST accept a
    ``compile_rules`` parameter that:

    * is present in :func:`inspect.signature(install_local).parameters`,
    * defaults to ``True`` (auto-compile on by default — fresh repos
      receive their compiled ``.cursor/rules/repo-governance.mdc`` +
      ``AGENTS.md`` on the first ``devola-init local`` run instead of
      requiring a separate ``devola-init sync-rules`` invocation),
    * is ``KEYWORD_ONLY`` (the function signature uses ``*`` as the
      separator so positional callers are forbidden — keeps the call
      site explicit and prevents the kwarg from drifting into the
      positional-argument cache prefix per A-2.4 reasoning).

    The kwarg is wired to the ``--no-compile`` CLI flag in
    :func:`devolaflow.init_project.main` so operators can disable
    auto-compile without mocking ``sys.argv`` in tests.
    """
    import inspect

    from devolaflow.init_project import install_local

    sig = inspect.signature(install_local)
    params = sig.parameters

    assert "compile_rules" in params, (
        f"W-18 v9.1.0 violation: install_local() signature missing "
        f"compile_rules parameter — present parameters: {sorted(params)}. "
        f"v9.1.0 W2-02 (G-007 + G-016) requires the kwarg to wire "
        f"`devola-init local --no-compile`."
    )

    cr = params["compile_rules"]
    assert cr.default is True, (
        f"W-18 v9.1.0 violation: install_local(compile_rules=...) default is "
        f"{cr.default!r}, expected True (auto-compile is the v9.1.0 W2-02 "
        f"default — fresh repos receive their compiled rules immediately; "
        f"--no-compile is the explicit opt-out)"
    )
    assert cr.kind == inspect.Parameter.KEYWORD_ONLY, (
        f"W-18 v9.1.0 violation: install_local(compile_rules=...) kind is "
        f"{cr.kind.name}, expected KEYWORD_ONLY (the function signature uses "
        f"`*` as the separator so positional callers are forbidden — keeps "
        f"the call site explicit per A-2.4 cache-prefix reasoning)"
    )


# ── v9.1.1 PV-01 — W-18 ghost-audit refresh for v9.1.1 NEW symbols ────
# Per Workflow Rule W-18 (`.rules/workflow.mdc` §W-18), every CHANGELOG
# entry mentioning a feature MUST have a corresponding ghost-audit lint
# in this file BEFORE the CHANGELOG entry is authored. v9.1.1 PV-01
# (cycle v9.2.0 start) introduces the surfaces below; this block adds
# presence + import-smoke + signature coverage for all of them as the
# W-18 PRECONDITION discharge:
#
#   * src/devolaflow/workspace_context.py — new module exposing
#     scan_workspace() + WorkspaceContext frozen dataclass (the
#     discovery API for `.local/` + `.rules/` + `.local/.agent/`
#     surfaces in a consumer repo).
#   * tests/test_workspace_context_scan.py — new test file pinning
#     the scan_workspace() detection contract (6 tests).
#   * docs/cycle-archive/v15.2.0/evobench-baselines/v9.2.0_baseline.json —
#     archived W-16 wholesale baseline evidence.

_V9_1_1_NEW_FILES: tuple[str, ...] = (
    "src/devolaflow/workspace_context.py",
    "tests/test_workspace_context_scan.py",
    "docs/cycle-archive/v15.2.0/evobench-baselines/v9.2.0_baseline.json",
)


# Minimum byte size for a v9.1.1 NEW surface — guards against an empty
# stub silently slipping through and satisfying mere file-presence.
_V9_1_1_FILE_MIN_BYTES: int = 50


def test_v9_1_1_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v9.1.1: every NEW v9.1.1 surface has presence + import-smoke coverage.

    Discharges the W-18 precondition — every CHANGELOG entry mentioning
    a feature MUST have a backing ghost-audit lint in THIS file BEFORE
    the CHANGELOG entry is authored. v9.1.1 PV-01 (the v9.2.0 cycle
    start) introduces the surfaces enumerated in the comment block above
    this test; this lint asserts each one as a cheap presence +
    import-smoke check.

    Coverage matrix:

    1. **Presence** — each path in ``_V9_1_1_NEW_FILES`` is a regular
       file and its size is ``>= _V9_1_1_FILE_MIN_BYTES`` (50 bytes —
       guards against an empty stub silently slipping through).
    2. **Import-smoke** — ``scan_workspace`` and ``WorkspaceContext``
       are importable from :mod:`devolaflow.workspace_context`,
       ``scan_workspace`` is callable, and ``WorkspaceContext`` is a
       :func:`dataclasses.is_dataclass`-true frozen dataclass.
    3. **Public summary surface** — :data:`MAX_FEEDBACKS_RETURNED` is
       importable and equals ``3`` (matching
       ``references/plan-mode-enforcement.md`` §"Feedback Ingestion"),
       AND :meth:`WorkspaceContext.to_summary_dict` exists and is
       callable (the JSON-serialisable rendering used by dispatch
       context injection).

    Failure modes:
      * "missing on disk" → a v9.1.1 surface was deleted or never
        landed; either restore it OR remove it from
        ``_V9_1_1_NEW_FILES`` if the surface was intentionally rolled
        back.
      * "< 50 byte minimum" → the file regressed to an empty stub;
        re-author the contents.
      * "WorkspaceContext is not frozen" → the dataclass dropped
        ``frozen=True`` (the design contract — consumers cannot mutate
        a snapshot in flight); restore the freeze.
    """
    import dataclasses

    for relpath in _V9_1_1_NEW_FILES:
        full = project_root / relpath
        assert full.is_file(), (
            f"W-18 v9.1.1 violation: NEW v9.1.1 surface {relpath!r} missing on "
            f"disk — the CHANGELOG entry mentioning this feature MUST be backed "
            f"by a file that exists"
        )
        size = full.stat().st_size
        assert size >= _V9_1_1_FILE_MIN_BYTES, (
            f"W-18 v9.1.1 violation: NEW v9.1.1 surface {relpath!r} is {size} "
            f"bytes (< {_V9_1_1_FILE_MIN_BYTES} byte minimum); empty/stub files "
            f"do not satisfy the W-18 precondition"
        )

    from devolaflow.workspace_context import (
        MAX_FEEDBACKS_RETURNED,
        WorkspaceContext,
        scan_workspace,
    )

    assert scan_workspace is not None, "W-18 v9.1.1 violation: scan_workspace import yielded None"
    assert callable(scan_workspace), (
        "W-18 v9.1.1 violation: scan_workspace is not callable — the export "
        "from devolaflow.workspace_context must be the function itself"
    )
    assert WorkspaceContext is not None, (
        "W-18 v9.1.1 violation: WorkspaceContext import yielded None"
    )
    assert dataclasses.is_dataclass(WorkspaceContext), (
        "W-18 v9.1.1 violation: WorkspaceContext is not a dataclass — the "
        "discovery API contract requires a structured frozen dataclass"
    )
    assert MAX_FEEDBACKS_RETURNED == 3, (
        f"W-18 v9.1.1 violation: MAX_FEEDBACKS_RETURNED is "
        f"{MAX_FEEDBACKS_RETURNED!r} (expected 3) — the public constant pins "
        f"the plan-mode feedback ingestion default per "
        f"references/plan-mode-enforcement.md §'Feedback Ingestion'"
    )
    assert hasattr(WorkspaceContext, "to_summary_dict"), (
        "W-18 v9.1.1 violation: WorkspaceContext is missing the "
        "to_summary_dict() method — the JSON-serialisable summary contract "
        "is part of the v9.1.1 PV-01 public surface"
    )
    assert callable(WorkspaceContext.to_summary_dict), (
        "W-18 v9.1.1 violation: WorkspaceContext.to_summary_dict is not callable"
    )

    # Frozen invariant: instantiating + attempting to mutate raises
    # FrozenInstanceError. Pins the design contract that consumers cannot
    # mutate a snapshot in flight (the snapshot is a value type — derive
    # a new one via dataclasses.replace if you need a modified copy).
    sample = WorkspaceContext(
        repo_root=project_root,
        has_local=False,
        has_rules=False,
        has_agent_dir=False,
    )
    try:
        sample.has_local = True  # type: ignore[misc]
    except dataclasses.FrozenInstanceError:
        pass
    else:  # pragma: no cover — the assert below catches the regression
        raise AssertionError(
            "W-18 v9.1.1 violation: WorkspaceContext is not frozen — "
            "attribute assignment did not raise FrozenInstanceError. "
            "The dataclass MUST be declared with frozen=True so consumers "
            "cannot mutate a snapshot in flight."
        )


# ── v9.1.2 PV-02 — W-18 ghost-audit refresh for v9.1.2 NEW symbols ────
# Per Workflow Rule W-18 (`.rules/workflow.mdc` §W-18), every CHANGELOG
# entry mentioning a feature MUST have a corresponding ghost-audit lint
# in this file BEFORE the CHANGELOG entry is authored. v9.1.2 PV-02
# (cycle v9.2.0 second PV) introduces the surfaces below; this block
# adds presence + import-smoke + signature coverage for all of them as
# the W-18 PRECONDITION discharge:
#
#   * src/devolaflow/skills/__init__.py — new package marker.
#   * src/devolaflow/skills/change_activation.py — pure-function
#     classifier + activation verdict (the heuristic codified by
#     Architecture rule A-6 "Workspace Engagement Auto-Activation"
#     per `.rules/architecture.mdc`).
#   * src/devolaflow/skills/slash_commands.py — `/devola:propose` /
#     `/devola:apply` / `/devola:verify` / `/devola:archive` thin
#     wrappers around `agent_workspace.ChangeStore` +
#     `ArchiveManager` (closes M-007 from v9.0.0 retro §3.3).
#   * tests/test_change_activation_heuristic.py — heuristic contract
#     pin (5+ tests covering the 3 verdict cases + opt-out + R5
#     strict env-flag parsing).
#   * tests/test_slash_commands.py — CLI happy-path pin (6+ tests
#     covering propose / apply / verify / archive + main entry).

_V9_1_2_NEW_FILES: tuple[str, ...] = (
    "src/devolaflow/skills/__init__.py",
    "src/devolaflow/skills/change_activation.py",
    "src/devolaflow/skills/slash_commands.py",
    "tests/test_change_activation_heuristic.py",
    "tests/test_slash_commands.py",
)


# Minimum byte size for a v9.1.2 NEW surface — guards against an empty
# stub silently slipping through and satisfying mere file-presence.
_V9_1_2_FILE_MIN_BYTES: int = 50


def test_v9_1_2_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v9.1.2: every NEW v9.1.2 surface has presence + import-smoke coverage.

    Discharges the W-18 precondition — every CHANGELOG entry mentioning
    a feature MUST have a backing ghost-audit lint in THIS file BEFORE
    the CHANGELOG entry is authored. v9.1.2 PV-02 (the second PV of
    the v9.2.0 cycle) introduces the surfaces enumerated in the comment
    block above this test; this lint asserts each one as a cheap
    presence + import-smoke check.

    Coverage matrix:

    1. **Presence** — each path in ``_V9_1_2_NEW_FILES`` is a regular
       file and its size is ``>= _V9_1_2_FILE_MIN_BYTES`` (50 bytes —
       guards against an empty stub silently slipping through).
    2. **Heuristic import-smoke** — ``classify_complexity`` and
       ``activation_verdict`` are importable from
       :mod:`devolaflow.skills.change_activation`, both are callable,
       and the ``ENV_FLAG_NAME`` constant equals
       ``"DEVOLAFLOW_AGENT_WORKSPACE"`` (W-20 reuse — same surface as
       v9.1.1 PV-01 SKILL.md §"Workspace Engagement").
    3. **Slash-command import-smoke** — ``main`` and ``slugify`` and
       ``scaffold_change_folder`` are importable from
       :mod:`devolaflow.skills.slash_commands`, ``main`` is callable
       (the ``python -m devolaflow.skills.slash_commands`` entry
       point), and ``REQUIRE_VERIFY_STATE == "VERIFYING"`` (the
       canonical FSM state name per
       ``schemas/agent-workspace/change-status.yaml#fsm_states``).

    Failure modes:
      * "missing on disk" → a v9.1.2 surface was deleted or never
        landed; either restore it OR remove it from
        ``_V9_1_2_NEW_FILES`` if the surface was intentionally rolled
        back.
      * "< 50 byte minimum" → the file regressed to an empty stub;
        re-author the contents.
      * "ENV_FLAG_NAME mismatch" → a NEW env flag was authored,
        violating W-20 reuse-first; either restore the REUSE or
        document the orthogonality argument per W-20 §3.
      * "REQUIRE_VERIFY_STATE mismatch" → the slash command drifted
        from the canonical FSM state; restore the contract.
    """
    for relpath in _V9_1_2_NEW_FILES:
        full = project_root / relpath
        assert full.is_file(), (
            f"W-18 v9.1.2 violation: NEW v9.1.2 surface {relpath!r} missing on "
            f"disk — the CHANGELOG entry mentioning this feature MUST be backed "
            f"by a file that exists"
        )
        size = full.stat().st_size
        assert size >= _V9_1_2_FILE_MIN_BYTES, (
            f"W-18 v9.1.2 violation: NEW v9.1.2 surface {relpath!r} is {size} "
            f"bytes (< {_V9_1_2_FILE_MIN_BYTES} byte minimum); empty/stub files "
            f"do not satisfy the W-18 precondition"
        )

    from devolaflow.skills.change_activation import (
        ENV_FLAG_NAME,
        ENV_FLAG_TRUTHY,
        activation_verdict,
        classify_complexity,
        from_env,
    )

    assert callable(classify_complexity), (
        "W-18 v9.1.2 violation: classify_complexity is not callable — the "
        "heuristic export from devolaflow.skills.change_activation must be "
        "the function itself"
    )
    assert callable(activation_verdict), "W-18 v9.1.2 violation: activation_verdict is not callable"
    assert callable(from_env), "W-18 v9.1.2 violation: from_env is not callable"
    assert ENV_FLAG_NAME == "DEVOLAFLOW_AGENT_WORKSPACE", (
        f"W-18 v9.1.2 violation: ENV_FLAG_NAME is {ENV_FLAG_NAME!r} (expected "
        f"'DEVOLAFLOW_AGENT_WORKSPACE') — W-20 reuse-first MUST hold; the "
        f"v9.1.2 PV-02 activation surface MUST REUSE the v9.1.1 PV-01 flag, "
        f"not author a new one"
    )
    assert ENV_FLAG_TRUTHY == "1", (
        f"W-18 v9.1.2 violation: ENV_FLAG_TRUTHY is {ENV_FLAG_TRUTHY!r} "
        f"(expected '1') — R5 strict opt-in REQUIRES the literal '1' string"
    )

    from devolaflow.skills.slash_commands import (
        ARCHIVE_GATE_THRESHOLD,
        REQUIRE_VERIFY_STATE,
        main,
        scaffold_change_folder,
        slugify,
    )

    assert callable(main), (
        "W-18 v9.1.2 violation: slash_commands.main is not callable — the "
        "`python -m devolaflow.skills.slash_commands` entry point requires it"
    )
    assert callable(slugify), "W-18 v9.1.2 violation: slugify is not callable"
    assert callable(scaffold_change_folder), (
        "W-18 v9.1.2 violation: scaffold_change_folder is not callable"
    )
    assert REQUIRE_VERIFY_STATE == "VERIFYING", (
        f"W-18 v9.1.2 violation: REQUIRE_VERIFY_STATE is "
        f"{REQUIRE_VERIFY_STATE!r} (expected 'VERIFYING') — the canonical "
        f"FSM state name per schemas/agent-workspace/change-status.yaml"
    )
    assert ARCHIVE_GATE_THRESHOLD == 8.5, (
        f"W-18 v9.1.2 violation: ARCHIVE_GATE_THRESHOLD is "
        f"{ARCHIVE_GATE_THRESHOLD!r} (expected 8.5) — the W-3 / SI-3 "
        f"PATCH/MINOR composite floor per Rule A-4"
    )


# ── v9.1.3 PV-03 — W-18 ghost-audit refresh for v9.1.3 NEW symbols ────
# Per Workflow Rule W-18 (`.rules/workflow.mdc` §W-18), every CHANGELOG
# entry mentioning a feature MUST have a corresponding ghost-audit lint
# in this file BEFORE the CHANGELOG entry is authored. v9.1.3 PV-03
# (cycle v9.2.0 third PV) closes G-005 deferred from v9.1.0 by creating
# the FIRST production caller of `HandoffStore.write_envelope` outside
# the module itself; this block adds presence + import-smoke + signature
# coverage for all new surfaces as the W-18 PRECONDITION discharge:
#
#   * src/devolaflow/lifecycle/auto_write_handoff.py — new module
#     binding the auto-write decision to the new `pre_handoff` lifecycle
#     event. Permissive no-op when `DEVOLAFLOW_AGENT_WORKSPACE` is unset
#     (R5 strict byte-identical); writes a handoff envelope when the
#     env-flag is set AND the dispatch payload carries a populated
#     `change_context` block. Honours Rule S-9 append-only ledger via
#     EnvelopeImmutableError surfacing (AWH002 warning in permissive,
#     re-raise in strict).
#   * lifecycle/PRE_HANDOFF_EVENT — new exported event constant
#     (canonical name `"pre_handoff"`).
#   * lifecycle/DEFAULT_EVENTS length 7 → 8 (pre_handoff APPENDED at
#     position 7 in the post-v22 live tuple — existing
#     event positions 1-6 stay ordered per the lifecycle/__init__.py
#     v9.1.3 PV-03 changelog comment).
#   * tests/test_handoff_auto_write.py — new test file pinning the
#     auto-write hook contract (env-flag OFF noop, AWH001/AWH002 codes,
#     seq monotonic, strict-mode raise propagation).

_V9_1_3_NEW_FILES: tuple[str, ...] = (
    "src/devolaflow/lifecycle/auto_write_handoff.py",
    "tests/test_handoff_auto_write.py",
)


# Minimum byte size for a v9.1.3 NEW surface — guards against an empty
# stub silently slipping through and satisfying mere file-presence.
_V9_1_3_FILE_MIN_BYTES: int = 50


# Expected DEFAULT_EVENTS tuple length after the v9.1.3 PV-03 bump.
# Before PV-03: 6 (pre_dispatch, post_dispatch, file_write, task_stop,
# format_on_edit, envelope_write). After PV-03: 7 (above
# + pre_handoff at position 7 in the post-v22 live tuple).
# Per A-2.2 append-only governance, future cycles MAY bump this number
# higher (v9.4.0 PV-02 bumped 8 → 9 with pre_plugin_invocation appended
# at position 8; v9.4.0 W-18 lint pins the new tail). The v9.1.3 lint
# below uses ``>= _V9_1_3_DEFAULT_EVENTS_MIN`` so future appends do not
# break this historic ghost-audit — the v9.1.3 contract is "pre_handoff
# must be in the tuple at position 8 OR LATER (depending on subsequent
# appends)", not "the tuple is exactly 8 long forever".
_V9_1_3_DEFAULT_EVENTS_MIN: int = 7


_V9_1_3_PRE_HANDOFF_POSITION: int = 7  # 1-indexed; tuple index 6 (zero-based)


def test_v9_1_3_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v9.1.3: every NEW v9.1.3 surface has presence + import-smoke coverage.

    Discharges the W-18 precondition — every CHANGELOG entry mentioning
    a feature MUST have a backing ghost-audit lint in THIS file BEFORE
    the CHANGELOG entry is authored. v9.1.3 PV-03 (the third PV of the
    v9.2.0 cycle) introduces the surfaces enumerated in the comment
    block above this test; this lint asserts each one as a cheap
    presence + import-smoke check.

    Coverage matrix:

    1. **Presence** — each path in ``_V9_1_3_NEW_FILES`` is a regular
       file and its size is ``>= _V9_1_3_FILE_MIN_BYTES`` (50 bytes —
       guards against an empty stub silently slipping through).
    2. **Import-smoke** — ``auto_write_handoff``, ``PRE_HANDOFF_EVENT``
       are importable from :mod:`devolaflow.lifecycle`,
       ``auto_write_handoff`` is callable, and the event constant
       equals ``"pre_handoff"`` (the canonical name re-exported from
       :mod:`devolaflow.lifecycle.auto_write_handoff`).
    3. **DEFAULT_EVENTS** tuple length is at least
       ``_V9_1_3_DEFAULT_EVENTS_MIN`` (7 — the live post-v22 tuple
       keeps ``pre_handoff`` at position 7 after removing
       ``pre_shell_call``) AND ``PRE_HANDOFF_EVENT`` is at
       the post-v22 position 7 (1-indexed; tuple index 6).
       Subsequent A-2.2 append-only bumps (v9.4.0 PV-02 added
       ``pre_plugin_invocation`` at position 8) do NOT invalidate this
       lint — the v9.1.3 contract is the historic position freeze for
       ``pre_handoff``, not the tuple length.
    4. **W-20 reuse-first** — the auto-write module's ``ENV_FLAG``
       constant equals ``"DEVOLAFLOW_AGENT_WORKSPACE"`` (REUSED from
       v9.1.1 PV-01 + v9.1.2 PV-02; no new flag) AND
       ``ENV_FLAG_TRUTHY == "1"`` (R5 strict literal-only opt-in).

    Failure modes:
      * "missing on disk" → a v9.1.3 surface was deleted or never
        landed; either restore it OR remove it from
        ``_V9_1_3_NEW_FILES`` if the surface was intentionally rolled
        back.
      * "< 50 byte minimum" → the file regressed to an empty stub;
        re-author the contents.
      * "DEFAULT_EVENTS lost pre_handoff" → the lifecycle event tuple
        was edited in violation of the post-v22 ordering; verify
        ``pre_handoff`` is still present at position 7 (1-indexed).
        Append-only growth (length > 8) is permitted per A-2.2 — see
        the v9.4.0 PV-02 ``pre_plugin_invocation`` precedent.
      * "ENV_FLAG mismatch" → a NEW env flag was authored, violating
        W-20 reuse-first; either restore the REUSE or document the
        orthogonality argument per W-20 §3.
    """
    for relpath in _V9_1_3_NEW_FILES:
        full = project_root / relpath
        assert full.is_file(), (
            f"W-18 v9.1.3 violation: NEW v9.1.3 surface {relpath!r} missing on "
            f"disk — the CHANGELOG entry mentioning this feature MUST be backed "
            f"by a file that exists"
        )
        size = full.stat().st_size
        assert size >= _V9_1_3_FILE_MIN_BYTES, (
            f"W-18 v9.1.3 violation: NEW v9.1.3 surface {relpath!r} is {size} "
            f"bytes (< {_V9_1_3_FILE_MIN_BYTES} byte minimum); empty/stub files "
            f"do not satisfy the W-18 precondition"
        )

    from devolaflow.lifecycle import (
        DEFAULT_EVENTS,
        PRE_HANDOFF_EVENT,
        auto_write_handoff,
    )
    from devolaflow.lifecycle.auto_write_handoff import (
        ENV_FLAG,
        ENV_FLAG_TRUTHY,
    )

    assert PRE_HANDOFF_EVENT == "pre_handoff", (
        f"W-18 v9.1.3 violation: PRE_HANDOFF_EVENT exported value "
        f"{PRE_HANDOFF_EVENT!r} != 'pre_handoff' (the canonical event "
        f"name from auto_write_handoff.EVENT)"
    )
    assert callable(auto_write_handoff), (
        "W-18 v9.1.3 violation: auto_write_handoff is not callable — "
        "the export from devolaflow.lifecycle must be the hook function itself"
    )
    assert len(DEFAULT_EVENTS) >= _V9_1_3_DEFAULT_EVENTS_MIN, (
        f"W-18 v9.1.3 violation: lifecycle.DEFAULT_EVENTS length is "
        f"{len(DEFAULT_EVENTS)}, expected >= {_V9_1_3_DEFAULT_EVENTS_MIN} "
        f"(post-v22 lifecycle tuple keeps pre_handoff at position 7 after "
        f"removing pre_shell_call; A-2.2 permits "
        f"future append-only growth). Current events: {DEFAULT_EVENTS!r}"
    )
    assert PRE_HANDOFF_EVENT in DEFAULT_EVENTS, (
        f"W-18 v9.1.3 violation: PRE_HANDOFF_EVENT not registered in "
        f"DEFAULT_EVENTS tuple {DEFAULT_EVENTS!r} — the PV-03 append step "
        f"was incomplete"
    )
    # Current live position: pre_handoff at 1-indexed position 7
    # (tuple index 6), with v22 removing pre_shell_call.
    handoff_idx = _V9_1_3_PRE_HANDOFF_POSITION - 1
    assert DEFAULT_EVENTS[handoff_idx] == PRE_HANDOFF_EVENT, (
        f"W-18 v9.1.3 violation: DEFAULT_EVENTS[{handoff_idx}] is "
        f"{DEFAULT_EVENTS[handoff_idx]!r}, expected {PRE_HANDOFF_EVENT!r}; "
        f"pre_handoff MUST stay frozen at 1-indexed position "
        f"{_V9_1_3_PRE_HANDOFF_POSITION} per the v9.1.3 PV-03 + A-2.4 "
        f"lifecycle re-numbering invariant (positions 1-7 stay ordered)"
    )

    # W-20 reuse-first lint: same activation surface as v9.1.1 PV-01 +
    # v9.1.2 PV-02. Authoring a new env flag here would violate W-20.
    assert ENV_FLAG == "DEVOLAFLOW_AGENT_WORKSPACE", (
        f"W-20 violation: auto_write_handoff.ENV_FLAG is {ENV_FLAG!r}, "
        f"expected 'DEVOLAFLOW_AGENT_WORKSPACE' (REUSE per Workflow Rule "
        f"W-20 — same activation surface as v9.1.1 PV-01 SKILL.md "
        f"§'Workspace Engagement' and v9.1.2 PV-02 Architecture rule A-6)"
    )
    assert ENV_FLAG_TRUTHY == "1", (
        f"R5 strict violation: auto_write_handoff.ENV_FLAG_TRUTHY is "
        f"{ENV_FLAG_TRUTHY!r}, expected '1' (R5 strict opt-in REQUIRES "
        f"the literal '1' string — every other variant treated as OFF)"
    )


def test_v9_1_3_handoff_production_caller_exists(project_root: Path) -> None:
    """G-005 closure proof: ``HandoffStore.write_envelope`` has ≥ 2 callers.

    The headline acceptance criterion of v9.1.3 PV-03 (cycle plan
    §PV-03 AC #1): ``rg "write_envelope\\(" src/devolaflow/`` MUST
    return at least 2 hits — the definition site at
    ``src/devolaflow/agent_workspace/handoff.py:281`` AND the new
    production caller in
    ``src/devolaflow/lifecycle/auto_write_handoff.py``.

    Through v9.1.2, the audit returned exactly 1 hit (the definition
    site only) — ``HandoffStore`` and ``ChangeStore`` were both
    "registered but never engaged" surfaces, which is the smoking-gun
    diagnosis from the v9.2.0 cycle plan §"Diagnosis — capability is
    taught but never engaged". v9.1.3 PV-03 closes that gap by
    materialising the FIRST production caller. This lint pins the
    closure so a future regression that deletes the auto-write module
    fails CI immediately.

    Implementation: AST-walks every Python file under
    ``src/devolaflow/`` and counts module-level + nested attribute
    accesses of the form ``write_envelope(`` (any expression containing
    that substring). The 2-hit floor catches both the definition (a
    method ``def write_envelope(...)``) and the call site (a function
    invocation like ``store.write_envelope(envelope)``). The single
    file ``handoff.py`` carries the definition; ``auto_write_handoff.py``
    carries the call.
    """
    src_root = project_root / "src" / "devolaflow"
    assert src_root.is_dir(), f"src/devolaflow/ missing — cannot audit (looked under {src_root})"

    callers: list[tuple[str, int]] = []
    for py_file in sorted(src_root.rglob("*.py")):
        if any(part == "__pycache__" for part in py_file.parts):
            continue
        text = _read(py_file)
        for line_num, line in enumerate(text.splitlines(), start=1):
            if "write_envelope(" in line:
                callers.append((py_file.relative_to(project_root).as_posix(), line_num))

    assert len(callers) >= 2, (
        f"G-005 NOT closed: rg 'write_envelope\\(' src/devolaflow/ found "
        f"only {len(callers)} hit(s) — expected ≥ 2 (1 definition + ≥ 1 caller). "
        f"Hits: {callers!r}. The v9.1.3 PV-03 production caller must live in "
        f"src/devolaflow/lifecycle/auto_write_handoff.py."
    )
    relpaths = {relpath for relpath, _line in callers}
    assert "src/devolaflow/agent_workspace/handoff.py" in relpaths, (
        "Definition site missing: src/devolaflow/agent_workspace/handoff.py "
        "MUST contain the canonical write_envelope definition"
    )
    assert "src/devolaflow/lifecycle/auto_write_handoff.py" in relpaths, (
        f"v9.1.3 PV-03 production caller missing: "
        f"src/devolaflow/lifecycle/auto_write_handoff.py MUST contain the "
        f"FIRST production caller of HandoffStore.write_envelope (G-005 "
        f"closure). Found callers in: {sorted(relpaths)}"
    )


# ── v9.1.4 PV-04 — W-18 ghost-audit refresh for v9.1.4 NEW symbols ────
# Per Workflow Rule W-18 (`.rules/workflow.mdc` §W-18), every CHANGELOG
# entry mentioning a feature MUST have a corresponding ghost-audit lint
# in this file BEFORE the CHANGELOG entry is authored. v9.1.4 PV-04
# (the fourth PV of the v9.2.0 cycle) introduces the surfaces enumerated
# in the comment block above this test; this lint asserts each one as a
# cheap presence + import-smoke check.
#
#   * src/devolaflow/memory_router/cache.py — EXTENDED with the new
#     consult_for_dispatch() pure function. The advisory companion to
#     MemoryRouter.lookup_case (which is the planner-replacement
#     fast-path); consult_for_dispatch is keyword-scored and surfaces
#     the top-3 MemoryCase hits in the dispatch payload's
#     `change_context.memory_case_hits` NEST sub-field.
#   * tests/test_memory_consult_for_dispatch.py — new test file pinning
#     the consult_for_dispatch contract (5 tests covering env-flag OFF
#     zero-IO, missing index, malformed YAML WARNING, keyword overlap
#     ranking, TTL+version-stamp filtering).
#   * tests/test_feedback_ingestion_plan_mode.py — new test file pinning
#     the plan-mode feedback ingestion contract (4 tests covering empty
#     dir, S-2 repo-relative paths, 3-feedback cap, plan-mode doc cite).
#   * benchmarks/devolaflow_context/baselines/layout_invariant_v9.2.0.yaml
#     — NEW witness baseline (byte-identical to v8.4.0); proves the
#     v9.1.4 PV-04 NEST extension preserved canonical_order length 16
#     and version 5 (the headline I-8 invariant for PV-04).
#   * schemas/lean-dispatch.yaml — EXTENDED change_context.fields with
#     3 NEW OPTIONAL sub-fields: prior_feedback_themes / memory_case_hits
#     / source_of_truth_excerpt (NEST per A-2.3 — canonical_order length
#     STAYS at 16, version STAYS at 5).

_V9_1_4_NEW_FILES: tuple[str, ...] = (
    "tests/test_memory_consult_for_dispatch.py",
    "tests/test_feedback_ingestion_plan_mode.py",
    "benchmarks/devolaflow_context/baselines/layout_invariant_v9.2.0.yaml",
)


# Minimum byte size for a v9.1.4 NEW surface — guards against an empty
# stub silently slipping through and satisfying mere file-presence.
_V9_1_4_FILE_MIN_BYTES: int = 50


# Expected length / version of `schemas/lean-dispatch.yaml#layout_invariant`
# AFTER the v9.1.4 PV-04 NEST extension. The headline I-8 invariant for
# PV-04 — the NEST extension MUST preserve canonical_order at 16 keys and
# the schema version at 5 (positions 1-16 byte-stable; v9-ADR-002 D2
# append-only contract preserved; v8.3.0 PV-05 + v8.4.0 multi-baseline
# byte tests continue to PASS without modification).
#
# v9.7.0 PV-02 update: the v9.7.0 cycle APPENDED a NEW top-level key
# ``predecessor_dedup_ledger`` at canonical position 17 per A-2.2 append-only
# rule. Schema version bumped 5 → 6. The post-v9.1.4 NEST byte-stability
# invariant (positions 1-16 byte-identical to v8.4.0) IS PRESERVED — the
# v9.7.0 PV-02 APPEND is at position 17, which v9.1.4 PV-04 explicitly
# anticipated ("A future PV that wants to add a TRULY orthogonal new
# payload would APPEND a new top-level key — that PV would update both
# this expected length AND the multi-baseline golden YAML").
_V9_1_4_CANONICAL_ORDER_LENGTH: int = 17


_V9_1_4_LAYOUT_VERSION: int = 6


# The 3 NEW change_context sub-fields added in v9.1.4 PV-04 per the
# A-2.3 nest-vs-append decision rule. Each is OPTIONAL (so absence is
# canonical and the v8.3.0 PV-05 + v8.4.0 + v9.2.0 baseline byte tests
# continue to PASS). The schema documents per-field caps (≤ 5 / ≤ 30 /
# ≤ 3 / ≤ 200) but those caps are NOT runtime-enforced in PV-04 — they
# are normative for L0 agents per references/plan-mode-enforcement.md
# §5.5 + the v9.2.0 PV-06 e2e test that will exercise them.
_V9_1_4_NEW_CHANGE_CONTEXT_FIELDS: tuple[str, ...] = (
    "prior_feedback_themes",
    "memory_case_hits",
    "source_of_truth_excerpt",
)


def test_v9_1_4_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v9.1.4: every NEW v9.1.4 surface has presence + import-smoke coverage.

    Discharges the W-18 precondition — every CHANGELOG entry mentioning
    a feature MUST have a backing ghost-audit lint in THIS file BEFORE
    the CHANGELOG entry is authored. v9.1.4 PV-04 (the fourth PV of the
    v9.2.0 cycle) introduces the surfaces enumerated in the comment
    block above this test; this lint asserts each one as a cheap
    presence + import-smoke check.

    Coverage matrix:

    1. **Presence** — each path in ``_V9_1_4_NEW_FILES`` is a regular
       file and its size is ``>= _V9_1_4_FILE_MIN_BYTES`` (50 bytes —
       guards against an empty stub silently slipping through).
    2. **Import-smoke** — ``consult_for_dispatch`` is importable from
       :mod:`devolaflow.memory_router` AND from
       :mod:`devolaflow.memory_router.cache`, and is callable.
    3. **W-20 reuse-first** — ``consult_for_dispatch`` is gated by the
       SAME env-flag the existing :class:`MemoryRouter` consults
       (``DEVOLAFLOW_MEMORY_ROUTER``); no new env-flag was introduced.
       This is the headline W-20 lint for PV-04: the v9.2.0 cycle plan
       §"Self-iteration constraint compliance matrix" pins "0 new flags
       across the entire 7-PV cycle".
    4. **change_context schema NEST extension** — the 3 NEW OPTIONAL
       sub-fields (``prior_feedback_themes`` / ``memory_case_hits`` /
       ``source_of_truth_excerpt``) are documented in
       ``schemas/lean-dispatch.yaml#lean_format_spec.change_context.fields``.
       Their presence in the schema documents the contract surfaced by
       :func:`consult_for_dispatch` (memory_case_hits) and by the
       plan-mode feedback ingestion (prior_feedback_themes).

    Failure modes:
      * "missing on disk" → a v9.1.4 surface was deleted or never
        landed; either restore it OR remove it from
        ``_V9_1_4_NEW_FILES`` if the surface was intentionally rolled
        back.
      * "< 50 byte minimum" → the file regressed to an empty stub;
        re-author the contents.
      * "consult_for_dispatch not callable" → the cache.py module
        broke its public surface contract.
      * "env-flag mismatch" → a NEW env-flag was authored in violation
        of W-20; either restore the REUSE or document the
        orthogonality argument per W-20 §3.
      * "missing schema sub-field" → the lean-dispatch.yaml NEST
        extension was reverted; restore the 3 sub-fields OR document
        the de-NEST decision.
    """
    for relpath in _V9_1_4_NEW_FILES:
        full = project_root / relpath
        assert full.is_file(), (
            f"W-18 v9.1.4 violation: NEW v9.1.4 surface {relpath!r} missing on "
            f"disk — the CHANGELOG entry mentioning this feature MUST be backed "
            f"by a file that exists"
        )
        size = full.stat().st_size
        assert size >= _V9_1_4_FILE_MIN_BYTES, (
            f"W-18 v9.1.4 violation: NEW v9.1.4 surface {relpath!r} is {size} "
            f"bytes (< {_V9_1_4_FILE_MIN_BYTES} byte minimum); empty/stub files "
            f"do not satisfy the W-18 precondition"
        )

    # Import-smoke from BOTH the package facade and the owning module —
    # catches a regression where one re-export path is dropped.
    from devolaflow.memory_router import consult_for_dispatch as facade_consult
    from devolaflow.memory_router.cache import (
        consult_for_dispatch as module_consult,
    )

    assert callable(facade_consult), (
        "W-18 v9.1.4 violation: devolaflow.memory_router.consult_for_dispatch "
        "is not callable — the export from devolaflow.memory_router/__init__.py "
        "must be the function itself"
    )
    assert callable(module_consult), (
        "W-18 v9.1.4 violation: devolaflow.memory_router.cache.consult_for_dispatch "
        "is not callable — the function definition is missing or shadowed"
    )
    assert facade_consult is module_consult, (
        "W-18 v9.1.4 violation: facade vs module export of consult_for_dispatch "
        "diverge — the package __init__.py must re-export the cache.py symbol "
        "directly without wrapping"
    )

    # W-20 reuse-first lint: PV-04 MUST reuse DEVOLAFLOW_MEMORY_ROUTER (the
    # existing MemoryRouter activation surface) per the v9.2.0 cycle plan
    # §"Self-iteration constraint compliance matrix". Authoring a new env
    # flag here would violate W-20.
    from devolaflow.memory_router.cache import (
        _CONSULT_ENV_FLAG,
        _CONSULT_ENV_TRUTHY,
    )

    assert _CONSULT_ENV_FLAG == "DEVOLAFLOW_MEMORY_ROUTER", (
        f"W-20 violation: consult_for_dispatch._CONSULT_ENV_FLAG is "
        f"{_CONSULT_ENV_FLAG!r}, expected 'DEVOLAFLOW_MEMORY_ROUTER' (REUSE per "
        f"Workflow Rule W-20 — same activation surface as the existing "
        f"MemoryRouter.lookup_case fast-path; no new env-flag introduced "
        f"in the entire v9.2.0 7-PV cycle)"
    )
    assert _CONSULT_ENV_TRUTHY == "1", (
        f"R5 strict violation: consult_for_dispatch._CONSULT_ENV_TRUTHY is "
        f"{_CONSULT_ENV_TRUTHY!r}, expected '1' (R5 strict opt-in REQUIRES "
        f"the literal '1' string — every other variant treated as OFF)"
    )

    # Schema NEST extension lint — the 3 NEW change_context sub-fields
    # MUST be documented in `schemas/lean-dispatch.yaml`.
    schema_path = project_root / "schemas" / "lean-dispatch.yaml"
    assert schema_path.is_file(), f"missing schemas/lean-dispatch.yaml at {schema_path}"
    schema = _load_yaml(schema_path)
    change_context_fields = (
        schema.get("lean_format_spec", {}).get("change_context", {}).get("fields", {})
    )
    for new_field in _V9_1_4_NEW_CHANGE_CONTEXT_FIELDS:
        assert new_field in change_context_fields, (
            f"W-18 v9.1.4 violation: NEST sub-field {new_field!r} missing from "
            f"`schemas/lean-dispatch.yaml#lean_format_spec.change_context.fields`. "
            f"The v9.1.4 PV-04 NEST extension (per A-2.3 nest-vs-append rule) "
            f"requires all 3 sub-fields (prior_feedback_themes / memory_case_hits "
            f"/ source_of_truth_excerpt). Present sub-fields: "
            f"{sorted(change_context_fields)}"
        )


def test_v9_1_4_nest_preserves_canonical_order_length(project_root: Path) -> None:
    """W-18 v9.1.4: NEST extension preserved canonical_order at 16 / version 5.

    The headline I-8 invariant proof for PV-04 — the v9.1.4 PV-04 NEST
    extension (3 NEW OPTIONAL sub-fields under ``change_context``) MUST
    NOT bump the canonical_order length nor the schema version. Per
    A-2.3 nest-vs-append decision rule, NEST is byte-stable wrt the
    LLM cache prefix (the historical baselines from v7.0.0 through
    v8.4.0 continue to render byte-identically because the new
    sub-fields are OPTIONAL and absent from those baselines).

    A future PV that wants to add a TRULY orthogonal new payload
    (cannot be expressed as a sub-field of an existing block) would
    APPEND a new top-level key — that PV would update both this
    expected length AND the
    ``tests/test_layout_invariant_multi_baseline.py`` golden YAML.
    """
    schema_path = project_root / "schemas" / "lean-dispatch.yaml"
    assert schema_path.is_file(), f"missing schemas/lean-dispatch.yaml at {schema_path}"
    schema = _load_yaml(schema_path)

    layout_invariant = schema.get("layout_invariant", {})
    canonical_order = layout_invariant.get("canonical_order", [])
    layout_version = layout_invariant.get("version")

    assert isinstance(canonical_order, list), (
        f"layout_invariant.canonical_order must be a list; got {type(canonical_order).__name__}"
    )
    assert len(canonical_order) == _V9_1_4_CANONICAL_ORDER_LENGTH, (
        f"v9.1.4 PV-04 I-8 invariant violation: "
        f"`schemas/lean-dispatch.yaml#layout_invariant.canonical_order` length is "
        f"{len(canonical_order)}, expected {_V9_1_4_CANONICAL_ORDER_LENGTH} "
        f"(NEST extension MUST preserve canonical_order length per A-2.3 +  "
        f"v9-ADR-002 D2). Current order: {canonical_order!r}"
    )
    assert layout_version == _V9_1_4_LAYOUT_VERSION, (
        f"v9.1.4 PV-04 I-8 invariant violation: "
        f"`schemas/lean-dispatch.yaml#layout_invariant.version` is "
        f"{layout_version!r}, expected {_V9_1_4_LAYOUT_VERSION} (NEST "
        f"extension MUST NOT bump schema version per A-2.3 + v9-ADR-002 D2)"
    )

    # The NEW v9.2.0 baseline witness MUST exist + be byte-identical to
    # v8.4.0. This couples the I-8 invariant proof to the on-disk
    # fixture so a renamed/moved baseline file fails CI immediately.
    baselines_dir = project_root / "benchmarks" / "devolaflow_context" / "baselines"
    v9_2_0_path = baselines_dir / "layout_invariant_v9.2.0.yaml"
    v8_4_0_path = baselines_dir / "layout_invariant_v8.4.0.yaml"
    assert v9_2_0_path.is_file(), (
        f"v9.1.4 PV-04 missing baseline witness at {v9_2_0_path}. "
        f"NEST extension proof requires this file to be byte-identical "
        f"to {v8_4_0_path}."
    )
    assert v8_4_0_path.is_file(), f"v8.4.0 baseline missing at {v8_4_0_path}"
    assert v9_2_0_path.read_text() == v8_4_0_path.read_text(), (
        "v9.1.4 PV-04 I-8 invariant violation: the v9.2.0 baseline witness "
        "diverged from the v8.4.0 baseline. The NEST extension was supposed "
        "to be byte-identical (the new sub-fields are OPTIONAL — their "
        "absence is canonical). See "
        "tests/test_layout_invariant_multi_baseline.py::"
        "test_v9_2_0_baseline_byte_identical_to_v8_4_0 for the wider context."
    )


# ---------------------------------------------------------------------------
# v9.1.5 PV-05 — spec_bootstrap + agents_md_slice default-ON ghost-audit
# ---------------------------------------------------------------------------

# v9.1.5 PV-05 introduces TWO operator-visible deliverables that the W-18
# precondition pins BEFORE the CHANGELOG entry mentioning them:
#
# 1. NEW src/devolaflow/agent_workspace/spec_bootstrap.py with
#    seed_initial_spec() + SpecBootstrapError — closes M-004 deferred
#    from v9.0.0 retrospective §3.3 (source-of-truth first-time seed).
# 2. context_profiles.yaml#meta.agents_md_slice.enabled flips false → true
#    (operator-visible default-ON; opt-out via DEVOLAFLOW_AGENTS_MD_SLICE=0
#    per W-20 reuse — telegraphed v9.0.0 PV-07 ADR-007 D3, runtime read
#    landed v9.1.5 PV-05).
_V9_1_5_NEW_FILES: tuple[str, ...] = (
    "src/devolaflow/agent_workspace/spec_bootstrap.py",
    "tests/test_spec_bootstrap.py",
)


# Minimum byte size for a v9.1.5 NEW surface — guards against an empty
# stub silently slipping through and satisfying mere file-presence.
_V9_1_5_FILE_MIN_BYTES: int = 50


def test_v9_1_5_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v9.1.5: every NEW v9.1.5 surface has presence + import-smoke coverage.

    Discharges the W-18 precondition — every CHANGELOG entry mentioning
    a feature MUST have a backing ghost-audit lint in THIS file BEFORE
    the CHANGELOG entry is authored. v9.1.5 PV-05 (the fifth PV of the
    v9.2.0 cycle, the most behaviour-flipping one) introduces:

    1. ``src/devolaflow/agent_workspace/spec_bootstrap.py`` — closes
       M-004 deferred from v9.0.0 retrospective §3.3 (source-of-truth
       first-time seed via :func:`seed_initial_spec`).
    2. ``tests/test_spec_bootstrap.py`` — 6 NEW tests pinning the
       seed contract.

    Coverage matrix:

    1. **Presence** — each path in ``_V9_1_5_NEW_FILES`` is a regular
       file and its size is ``>= _V9_1_5_FILE_MIN_BYTES`` (50 bytes —
       guards against an empty stub silently slipping through).
    2. **Import-smoke** — :func:`seed_initial_spec` and
       :exc:`SpecBootstrapError` are importable from BOTH the package
       facade :mod:`devolaflow.agent_workspace` AND the owning module
       :mod:`devolaflow.agent_workspace.spec_bootstrap`; ``facade is
       module`` (catches the regression where one re-export path is
       dropped) and the function is callable.
    3. **W-20 reuse-first** — :data:`_AGENTS_MD_SLICE_ENV_FLAG` equals
       ``"DEVOLAFLOW_AGENTS_MD_SLICE"`` (NO new env-flag introduced in
       PV-05; the flag was telegraphed in v9.0.0 PV-07 ADR-007 D3).
    4. **A-4 invariant signature** — :func:`seed_initial_spec` accepts
       ``force=False`` as the canonical default (the A-4 first-time
       seed gate); operator overrides via ``force=True`` only.

    Failure modes:
      * "missing on disk" → a v9.1.5 surface was deleted or never
        landed; either restore it OR remove it from
        ``_V9_1_5_NEW_FILES`` if the surface was intentionally rolled
        back.
      * "< 50 byte minimum" → the file regressed to an empty stub;
        re-author the contents.
      * "seed_initial_spec not callable" → the spec_bootstrap module
        broke its public surface contract.
      * "env-flag mismatch" → a NEW env-flag was authored in violation
        of W-20; either restore the REUSE or document the
        orthogonality argument per W-20 §3.
      * "force kwarg default mismatch" → the A-4 first-time-seed gate
        was relaxed; restore ``force=False`` or document the override
        with an ADR.
    """
    import inspect

    for relpath in _V9_1_5_NEW_FILES:
        full = project_root / relpath
        assert full.is_file(), (
            f"W-18 v9.1.5 violation: NEW v9.1.5 surface {relpath!r} missing on "
            f"disk — the CHANGELOG entry mentioning this feature MUST be backed "
            f"by a file that exists"
        )
        size = full.stat().st_size
        assert size >= _V9_1_5_FILE_MIN_BYTES, (
            f"W-18 v9.1.5 violation: NEW v9.1.5 surface {relpath!r} is {size} "
            f"bytes (< {_V9_1_5_FILE_MIN_BYTES} byte minimum); empty/stub files "
            f"do not satisfy the W-18 precondition"
        )

    # Import-smoke from BOTH the package facade and the owning module —
    # catches a regression where one re-export path is dropped. The
    # `as facade_*` / `as module_*` rebinds intentionally use lowercase
    # because they are not used as types — they are used as identity
    # comparison handles for the `facade is module` invariant. ruff N813
    # is suppressed at the import-block level.
    from devolaflow.agent_workspace import (  # noqa: N813
        SpecBootstrapError as facade_error,
    )
    from devolaflow.agent_workspace import (
        seed_initial_spec as facade_seed,
    )
    from devolaflow.agent_workspace.spec_bootstrap import (  # noqa: N813
        SpecBootstrapError as module_error,
    )
    from devolaflow.agent_workspace.spec_bootstrap import (
        seed_initial_spec as module_seed,
    )

    assert callable(facade_seed), (
        "W-18 v9.1.5 violation: devolaflow.agent_workspace.seed_initial_spec "
        "is not callable — the export from devolaflow.agent_workspace/__init__.py "
        "must be the function itself"
    )
    assert callable(module_seed), (
        "W-18 v9.1.5 violation: devolaflow.agent_workspace.spec_bootstrap."
        "seed_initial_spec is not callable — the function definition is "
        "missing or shadowed"
    )
    assert facade_seed is module_seed, (
        "W-18 v9.1.5 violation: facade vs module export of seed_initial_spec "
        "diverge — the package __init__.py must re-export the spec_bootstrap.py "
        "symbol directly without wrapping"
    )
    assert facade_error is module_error, (
        "W-18 v9.1.5 violation: facade vs module export of SpecBootstrapError "
        "diverge — the package __init__.py must re-export the spec_bootstrap.py "
        "exception directly without aliasing"
    )
    assert issubclass(facade_error, RuntimeError), (
        "W-18 v9.1.5 violation: SpecBootstrapError must subclass RuntimeError "
        "(per S-5 explicit error states; allows callers to catch RuntimeError "
        "without importing the agent_workspace package)"
    )

    # A-4 invariant signature lint — `force` defaults to False so the
    # first-time-seed gate is the canonical entry path.
    sig = inspect.signature(module_seed)
    force_param = sig.parameters.get("force")
    assert force_param is not None, (
        "W-18 v9.1.5 violation: seed_initial_spec must accept a `force` kwarg "
        "(the A-4 first-time-seed override hatch documented in the cycle plan §PV-05)"
    )
    assert force_param.default is False, (
        f"W-18 v9.1.5 violation: seed_initial_spec(force=...) default is "
        f"{force_param.default!r}, expected False (A-4 first-time-seed gate "
        f"defaults to refuse-overwrite — operators opt into wholesale "
        f"replacement explicitly via force=True)"
    )

    # W-20 reuse-first lint — PV-05 MUST reuse DEVOLAFLOW_AGENTS_MD_SLICE
    # (the v9.0.0 PV-07 ADR-007 D3 telegraphed flag) per the v9.2.0 cycle
    # plan §"Self-iteration constraint compliance matrix" "0 new flags
    # across the entire 7-PV cycle".
    #
    # v14.5.0 (ADR-006 G-025) ghost-pin update: the two PRIVATE helpers
    # moved from task_adaptive_selector.py to the new owner module
    # devolaflow.agents_md_slice (private symbols are not shimmed); the
    # pin now imports from the re-export truth's owner module.
    from devolaflow.agents_md_slice import (
        _AGENTS_MD_SLICE_ENV_FLAG,
        _agents_md_slice_env_override,
    )

    assert _AGENTS_MD_SLICE_ENV_FLAG == "DEVOLAFLOW_AGENTS_MD_SLICE", (
        f"W-20 violation: _AGENTS_MD_SLICE_ENV_FLAG is "
        f"{_AGENTS_MD_SLICE_ENV_FLAG!r}, expected 'DEVOLAFLOW_AGENTS_MD_SLICE' "
        f"(REUSE per Workflow Rule W-20 — the flag was telegraphed in v9.0.0 "
        f"PV-07 ADR-007 D3; v9.1.5 PV-05 is the runtime-wiring landing PV; "
        f"NO new env-flag introduced in the entire v9.2.0 7-PV cycle)"
    )
    assert _agents_md_slice_env_override({"DEVOLAFLOW_AGENTS_MD_SLICE": "0"}) is False, (
        "R5 strict violation: env-flag value '0' must force opt-out (return False); "
        "this is the headline v9.1.5 PV-05 escape hatch for the default-ON flip"
    )
    assert _agents_md_slice_env_override({"DEVOLAFLOW_AGENTS_MD_SLICE": "1"}) is True, (
        "R5 strict violation: env-flag value '1' must force opt-in (return True)"
    )


def test_v9_1_5_agents_md_slice_default_on(project_root: Path) -> None:
    """W-18 v9.1.5: context_profiles.yaml#agents_md_slice.enabled is True.

    Pins the headline operator-visible behaviour change of v9.1.5 PV-05.
    Pre-v9.1.5 the canonical YAML default was ``enabled: false`` (the
    v9.0.0 MAJOR-cycle telegraphed flip with a 2-cycle lead time per
    W-21 governance precedent applied to operator-visible defaults).
    v9.1.5 PV-05 flips the canonical default to ``true``, so dispatchers
    on the unmodified YAML receive sliced AGENTS.md content automatically.

    This lint catches a regression where the canonical YAML is
    accidentally reverted to ``enabled: false`` (would silently revert
    the operator-visible behaviour change without bumping the
    CHANGELOG). It is paired with
    ``tests/test_pv07_agents_md_slice.py::test_agents_md_slice_default_on_in_v9_1_5``
    which loads the YAML directly + with
    ``test_agents_md_slice_env_flag_0_opts_out`` which proves the R5
    strict opt-out is byte-stable.
    """
    import yaml as yaml_module

    profiles_path = project_root / "workflow-system" / "agent" / "context_profiles.yaml"
    assert profiles_path.is_file(), (
        f"W-18 v9.1.5 violation: context_profiles.yaml missing at {profiles_path}"
    )
    config = yaml_module.safe_load(profiles_path.read_text(encoding="utf-8"))
    slice_cfg = config.get("meta", {}).get("agents_md_slice", {})

    assert slice_cfg.get("enabled") is True, (
        f"W-18 v9.1.5 violation: context_profiles.yaml#meta.agents_md_slice."
        f"enabled is {slice_cfg.get('enabled')!r}, expected True (v9.1.5 PV-05 "
        f"default-ON flip — the headline operator-visible behaviour change). "
        f"If the flip was rolled back, also remove the [9.1.5] CHANGELOG "
        f"entry citing the flip."
    )
    # The fallback strategy must remain "full" so unmatched task types
    # still see byte-identical AGENTS.md (W-20 R5 strict — the slice is
    # additive opt-in for matched profiles; unmatched falls through).
    assert slice_cfg.get("fallback") == "full", (
        f"W-18 v9.1.5 violation: agents_md_slice.fallback must be 'full' "
        f"(unmatched task types fall through to byte-identical AGENTS.md per "
        f"R5 strict); got {slice_cfg.get('fallback')!r}"
    )
