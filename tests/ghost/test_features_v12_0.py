"""Ghost audit — per-cycle W-18 feature stanzas for the v12.0 cycle.

Split from ``tests/test_no_ghost_features.py`` per v15-ADR-001
(v14.3.0). New W-18 stanzas for a v12.0.x release append HERE; the
next MINOR cycle rotates to a fresh ``test_features_v<MAJ>_<MIN>.py``.
"""

from __future__ import annotations

import ast
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# v12.0.0 PV-02 D-1 — A-7 STRICT graduation lint
#
# Per W-18 sequencing the ghost-audit refresh MUST land BEFORE the v12.0.0
# CHANGELOG entry (which PV-07 owns). This stanza closes that precondition
# at the source of the BREAKING graduation: scorer.py + audit_layer_usage.py
# + the cascade-enforcement test suite. The CHANGELOG positive-substring pin
# is intentionally OMITTED here — PV-07 owns the rollup CHANGELOG, and per
# the v12.0.0 cycle plan §8.4 the version bump + CHANGELOG entry are
# deferred to the cycle-rollup commit. PV-02 only ships the source-side
# pins. The L0 cycle-lead refreshes this stanza at PV-07 to add the
# ``## [12.0.0]`` substring assertions once the rollup CHANGELOG lands.
# Source: ``.local/research/v12.0.0_gap_analysis.md`` §3 (D-1 spec) + §8.4
# (PV-07 owns the bump).
# v14.5.0 (ADR-006 G-025) ghost-pin update: CascadeViolationError +
# validate_cascade_gate_fields moved VERBATIM from gate/scorer.py to the
# new owner module gate/cascade.py. v17.0.0 retired the historical
# devolaflow.gate.scorer re-export shim after call-site migration
# (absence pinned by tests/test_module_split_shims.py); the owner module
# is now the sole import surface. The AST pins below follow it.
_V12_0_0_PV02_SCORER_FILE: Path = Path("src/devolaflow/gate/cascade.py")


_V12_0_0_PV02_AUDIT_FILE: Path = Path("scripts/audit_layer_usage.py")


_V12_0_0_PV02_TEST_FILE: Path = Path("tests/test_cascade_enforcement.py")


# Required NEW test functions in tests/test_cascade_enforcement.py — the
# canonical 7-name Branch 6 subset enumerated in
# ``.local/research/v12.0.0_gap_analysis.md`` §3.3 PV-02 NEW tests row.
# The L3 author may have ADDED tests beyond this set; we DO NOT pin those
# so the audit remains robust against later test-suite refactors that
# consolidate or expand coverage.
_V12_0_0_PV02_REQUIRED_NEW_TESTS: tuple[str, ...] = (
    "test_cascade_violation_error_inherits_from_exception",
    "test_cascade_violation_error_message_cites_a7",
    "test_validate_cascade_gate_fields_raises_on_missing_cascade_required",
    "test_validate_cascade_gate_fields_raises_on_invalid_type",
    "test_validate_cascade_gate_fields_raises_on_actual_layers_below_min",
    "test_validate_cascade_gate_fields_returns_none_on_pass",
    "test_audit_strict_default_on_v12_0_0",
)


# Positive substrings for ``scripts/audit_layer_usage.py`` source — pin
# the v12.0.0 default-ON marker (``strict: bool = True``) AND the new
# ``--no-strict`` opt-out flag AND the v12.0.0 PV-02 D-1 citation in
# the source comment. The substring pinning ensures a future maintainer
# cannot silently revert the BREAKING flip without tripping this lint.
_V12_0_0_PV02_AUDIT_POSITIVE_SUBSTRINGS: tuple[str, ...] = (
    "strict: bool = True",
    "--no-strict",
    "v12.0.0 PV-02 D-1",
)


def test_v12_0_0_pv02_d1_strict_promotion(project_root: Path) -> None:
    """W-18 v12.0.0 PV-02 D-1: A-7 STRICT graduation source-side pins.

    Discharges the W-18 precondition for the BREAKING D-1 graduation.
    Per the v12.0.0 cycle plan §8.4 the version bump + CHANGELOG
    rollup are deferred to PV-07; this stanza only pins the source-side
    surfaces that PV-02 owns. PV-07's W-18 stanza will extend this with
    the ``## [12.0.0]`` CHANGELOG positive-substring assertion.

    Surfaces pinned (v12.0.0 PV-02 D-1 STRICT-graduation scope; first of
    4 v12.0.0 graduation commitments — sister PVs PV-03 D-2 SHORTCUT
    retirement, PV-04 NEW subagent NEST, PV-05 D-5 CONDITIONAL):

    * ``src/devolaflow/gate/scorer.py`` carries the NEW
      ``CascadeViolationError`` exception class (AST ``ClassDef`` pin —
      robust against body refactor; only fails on rename / removal).
      The exception MUST subclass :class:`Exception` directly (not
      :class:`ValueError`) per v12.0.0 PV-02 D-1 design rationale —
      callers writing ``except CascadeViolationError`` should not
      accidentally catch unrelated ValueErrors raised in the same
      try-block.

    * ``src/devolaflow/gate/scorer.py::validate_cascade_gate_fields``
      return annotation is ``None`` (NOT ``list[str]`` — the v11.x
      SOFT contract is REMOVED at v12.0.0 per the BREAKING graduation).
      AST ``FunctionDef.returns`` pin — robust against body refactor.

    * ``scripts/audit_layer_usage.py`` carries the v12.0.0 PV-02 D-1
      default-ON marker — the source MUST contain the substring
      ``strict: bool = True`` (the new default in ``run()`` signature)
      AND ``--no-strict`` (the new CLI opt-out flag) AND
      ``v12.0.0 PV-02 D-1`` (the citation comment that anchors the
      graduation trail in source).

    * ``tests/test_cascade_enforcement.py`` carries the 7 canonical NEW
      test functions enumerated in
      ``.local/research/v12.0.0_gap_analysis.md`` §3.3 PV-02 row (the
      L3 author may have ADDED tests beyond this set — we pin only the
      canonical subset so the audit stays robust against test-suite
      expansion).

    Coupled invariants verified GREEN at PV-02 close (no source edits
    to schemas / .rules / SKILL / CHANGELOG per cycle plan §8.4):

    * A-2.4 multi-baseline byte test: 32/32 PASS unchanged
      (canonical_order stays at 17; PV-04 owns the schema NEST that
      adds the 33rd baseline).
    * S-10 hook-chain byte-id: 10/10 PASS unchanged.
    * CP-4 gate suite: byte-stable EXCEPT for the
      ``TestCascadeGateFieldsValidator`` class which carries the
      v11.x SOFT-mode tests; those tests are EXPECTED to FAIL post-
      PV-02 as the soft contract is the BREAKING-removed surface.
      The L0 cycle-lead lands the ``TestCascadeGateFieldsValidator``
      refresh at PV-02 stage close OR via a follow-up PV inside the
      cycle.
    * v11.1.1 D-1 CHANGELOG lint: PASS (PV-02 makes ZERO CHANGELOG
      edits per cycle plan §8.4 PV-07-owns-rollup).
    * W-21 Soul-set freeze preserved at 10 entries (no S-11 proposed;
      A-7 stays at Architecture per ADR-007 §"Soul-vs-Architecture"
      decision-rule).
    * W-20 reuse-first preserved at 8 env flags (NO new
      ``DEVOLAFLOW_*`` env flag introduced — the audit ratchet's
      default-ON is a runtime flip, not a new env-flag surface).

    Source: ``.local/research/v12.0.0_gap_analysis.md`` §3 (D-1 spec)
    + §8.4 (PV-07-owns-bump separation rationale) +
    ``docs/cycle-archive/v11.1.0/retrospective.md`` §3 D-1 (telegraph).
    """
    # ----- 1. scorer.py — CascadeViolationError class + return-None pin -----
    scorer_path = project_root / _V12_0_0_PV02_SCORER_FILE
    assert scorer_path.is_file(), (
        f"W-18 v12.0.0 PV-02 violation: {_V12_0_0_PV02_SCORER_FILE} missing — "
        "release-blocker. The STRICT graduation lands AT this file."
    )
    scorer_module = ast.parse(scorer_path.read_text(encoding="utf-8"))

    # CascadeViolationError class pin (AST ClassDef walk — robust against
    # body refactor; only fails on rename / removal).
    cascade_err_class = next(
        (
            node
            for node in scorer_module.body
            if isinstance(node, ast.ClassDef) and node.name == "CascadeViolationError"
        ),
        None,
    )
    assert cascade_err_class is not None, (
        f"W-18 v12.0.0 PV-02 violation: {_V12_0_0_PV02_SCORER_FILE} missing "
        "``CascadeViolationError`` class definition. Per the v12.0.0 PV-02 "
        "D-1 STRICT graduation, the exception class MUST be defined at "
        "module scope so callers can ``from devolaflow.gate.cascade import "
        "CascadeViolationError``."
    )

    # The class MUST subclass Exception (not ValueError) per the design
    # rationale documented in CascadeViolationError.__doc__. AST base
    # walk — accept either ``Exception`` (bare ``ast.Name``) or any
    # qualified name ending in ``.Exception``.
    base_names: list[str] = []
    for base in cascade_err_class.bases:
        if isinstance(base, ast.Name):
            base_names.append(base.id)
        elif isinstance(base, ast.Attribute):
            base_names.append(base.attr)
    assert "Exception" in base_names, (
        f"W-18 v12.0.0 PV-02 violation: {_V12_0_0_PV02_SCORER_FILE} "
        f"``CascadeViolationError`` bases drift to {base_names!r}; expected "
        "``Exception`` directly per v12.0.0 PV-02 D-1 design (callers writing "
        "``except CascadeViolationError`` must not accidentally catch "
        "unrelated ValueErrors)."
    )

    # validate_cascade_gate_fields return annotation pin: AST
    # ``FunctionDef.returns`` MUST be ``None`` (a ``Constant(value=None)``
    # node), NOT a ``Subscript`` like ``list[str]``. The v11.x SOFT
    # contract returned ``list[str]``; v12.0.0 STRICT returns ``None``.
    validator_func = next(
        (
            node
            for node in scorer_module.body
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
            and node.name == "validate_cascade_gate_fields"
        ),
        None,
    )
    assert validator_func is not None, (
        f"W-18 v12.0.0 PV-02 violation: {_V12_0_0_PV02_SCORER_FILE} missing "
        "``validate_cascade_gate_fields`` function definition."
    )
    returns = validator_func.returns
    assert returns is not None, (
        "W-18 v12.0.0 PV-02 violation: ``validate_cascade_gate_fields`` "
        "return annotation is missing — the BREAKING graduation requires "
        "an explicit ``-> None`` annotation so static type checkers catch "
        "v11.x callers consuming the (now-removed) warning list."
    )
    is_none_constant = isinstance(returns, ast.Constant) and returns.value is None
    assert is_none_constant, (
        f"W-18 v12.0.0 PV-02 violation: ``validate_cascade_gate_fields`` "
        f"return annotation is {ast.unparse(returns)!r}; expected ``None`` "
        "per v12.0.0 PV-02 D-1 BREAKING graduation. The v11.x ``list[str]`` "
        "SOFT-mode return contract is REMOVED — STRICT mode raises on "
        "violations and returns ``None`` on every passing path."
    )

    # ----- 2. audit_layer_usage.py — default-ON marker + --no-strict + citation -----
    audit_path = project_root / _V12_0_0_PV02_AUDIT_FILE
    assert audit_path.is_file(), (
        f"W-18 v12.0.0 PV-02 violation: {_V12_0_0_PV02_AUDIT_FILE} missing — "
        "release-blocker. The audit ratchet default-ON flip lands AT this file."
    )
    audit_text = audit_path.read_text(encoding="utf-8")
    for sub in _V12_0_0_PV02_AUDIT_POSITIVE_SUBSTRINGS:
        assert sub in audit_text, (
            f"W-18 v12.0.0 PV-02 violation: {_V12_0_0_PV02_AUDIT_FILE} "
            f"missing positive substring {sub!r}. The v12.0.0 PV-02 D-1 "
            "default-ON graduation MUST surface the new ``strict: bool = True`` "
            "default on ``run()``, the ``--no-strict`` CLI opt-out, and the "
            "``v12.0.0 PV-02 D-1`` citation comment that anchors the trail."
        )

    # ----- 3. test_cascade_enforcement.py — 7 NEW tests AST pin -----
    test_path = project_root / _V12_0_0_PV02_TEST_FILE
    assert test_path.is_file(), (
        f"W-18 v12.0.0 PV-02 violation: {_V12_0_0_PV02_TEST_FILE} missing — release-blocker."
    )
    test_module = ast.parse(test_path.read_text(encoding="utf-8"))
    defined_tests = {
        node.name
        for node in test_module.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    missing = [t for t in _V12_0_0_PV02_REQUIRED_NEW_TESTS if t not in defined_tests]
    assert not missing, (
        f"W-18 v12.0.0 PV-02 violation: {_V12_0_0_PV02_TEST_FILE} missing "
        f"required NEW test functions {missing!r}. Required canonical "
        f"7-name set (gap analysis §3.3): "
        f"{list(_V12_0_0_PV02_REQUIRED_NEW_TESTS)!r}."
    )


# ---------------------------------------------------------------------------
# v12.0.0 PV-03 D-2 — SHORTCUT_SIMPLE retirement lint
#
# Per W-18 sequencing the ghost-audit refresh MUST land BEFORE the v12.0.0
# CHANGELOG entry (which PV-07 owns). This stanza closes that precondition
# at the source of the BREAKING retirement: the v9.3.0 PV-06 SHORTCUT_SIMPLE
# verdict + shortcut_verdict / shortcut_from_env helpers + SHORTCUT_FLAG_NAME
# constant + DEVOLAFLOW_SIMPLE_SHORTCUT env flag are all DELETED at v12.0.0
# PV-03. The CHANGELOG positive-substring pin is intentionally OMITTED here —
# PV-07 owns the rollup CHANGELOG, and per the v12.0.0 cycle plan §8.4 the
# version bump + CHANGELOG entry are deferred to the cycle-rollup commit.
# PV-03 only ships the source-side / inventory-side / test-deletion pins.
# Source: ``.local/research/v12.0.0_gap_analysis.md`` §4 (D-2 spec) + §8.4
# (PV-07 owns the bump) + ``docs/cycle-archive/v11.1.0/retrospective.md``
# §3 D-2 (telegraph rationale; env-flag count 8 → 7).
_V12_0_0_PV03_CHANGE_ACTIVATION_FILE: Path = Path("src/devolaflow/skills/change_activation.py")


_V12_0_0_PV03_ENV_FLAGS_FILE: Path = Path("workflow-system/agent/references/env-flags.md")


_V12_0_0_PV03_DELETED_TEST_FILE: Path = Path("tests/test_simple_shortcut.py")


# Symbols deleted from ``change_activation.py`` per v12.0.0 PV-03 D-2.
# The AST walk below proves NONE of these names appear at module scope as
# either a top-level ``ast.FunctionDef`` / ``ast.AsyncFunctionDef`` (for the
# two function entries) or as a top-level ``ast.AnnAssign`` / ``ast.Assign``
# target (for ``ShortcutVerdict`` / ``SHORTCUT_FLAG_NAME`` /
# ``SHORTCUT_FLAG_TRUTHY``). The ``_VALID_SHORTCUT_VERDICTS`` private cache
# is also covered because it derived from the public ``ShortcutVerdict``
# Literal alias and was deleted alongside it.
_V12_0_0_PV03_DELETED_FUNCTIONS: frozenset[str] = frozenset(
    {
        "shortcut_verdict",
        "shortcut_from_env",
    }
)


_V12_0_0_PV03_DELETED_NAMES: frozenset[str] = frozenset(
    {
        "ShortcutVerdict",
        "SHORTCUT_FLAG_NAME",
        "SHORTCUT_FLAG_TRUTHY",
        "_VALID_SHORTCUT_VERDICTS",
    }
)


# Negative substrings — the literal env-flag name MUST NOT appear in the
# canonical inventory after the v12.0.0 PV-03 retirement. The retirement
# note in env-flags.md DOES NOT contain the literal name (it paraphrases
# via "the simple-task auto-shortcut env flag" + the source-side symbol
# names) so the literal-string negative pin remains clean.
_V12_0_0_PV03_ENV_FLAGS_NEGATIVE_SUBSTRINGS: tuple[str, ...] = ("DEVOLAFLOW_SIMPLE_SHORTCUT",)


# Symbols that MUST remain in change_activation.py — these are the
# preserved-API surface that PV-03 explicitly does NOT touch (only the
# v9.3.0 PV-06 shortcut helpers retire). A regression that accidentally
# removes any of these names is a release blocker; pinning them keeps
# the audit honest about what stays vs what goes.
_V12_0_0_PV03_PRESERVED_FUNCTIONS: frozenset[str] = frozenset(
    {
        "classify_complexity",
        "activation_verdict",
        "from_env",
        "cascade_requirement",
    }
)


_V12_0_0_PV03_PRESERVED_NAMES: frozenset[str] = frozenset(
    {
        "Complexity",
        "ActivationVerdict",
        "CascadeRequirement",
        "ENV_FLAG_NAME",
        "ENV_FLAG_TRUTHY",
    }
)


def test_v12_0_0_pv03_d2_shortcut_simple_retirement(project_root: Path) -> None:
    """W-18 v12.0.0 PV-03 D-2: SHORTCUT_SIMPLE retirement source-side pins.

    Discharges the W-18 precondition for the BREAKING D-2 retirement.
    Per the v12.0.0 cycle plan §8.4 the version bump + CHANGELOG
    rollup are deferred to PV-07; this stanza only pins the source-side
    surfaces that PV-03 owns. PV-07's W-18 stanza will extend this with
    the ``## [12.0.0]`` CHANGELOG positive-substring assertion (the
    retirement migration table + env-flag count 8 → 7 line).

    Surfaces pinned (v12.0.0 PV-03 D-2 retirement scope; second of 4
    v12.0.0 graduation commitments — sister PVs PV-02 D-1 STRICT
    promotion, PV-04 NEW subagent NEST, PV-05 D-5 CONDITIONAL):

    * ``src/devolaflow/skills/change_activation.py`` does NOT define the
      retired ``shortcut_verdict`` / ``shortcut_from_env`` functions
      anywhere in the AST (top-level ``FunctionDef`` walk).

    * ``src/devolaflow/skills/change_activation.py`` does NOT define
      the retired ``ShortcutVerdict`` Literal alias / the
      ``SHORTCUT_FLAG_NAME`` + ``SHORTCUT_FLAG_TRUTHY`` constants /
      the ``_VALID_SHORTCUT_VERDICTS`` private cache (top-level
      ``Assign`` / ``AnnAssign`` walk).

    * ``src/devolaflow/skills/change_activation.py`` PRESERVES the
      v11.x public API surface: ``classify_complexity`` /
      ``activation_verdict`` / ``from_env`` / ``cascade_requirement``
      functions plus ``Complexity`` / ``ActivationVerdict`` /
      ``CascadeRequirement`` / ``ENV_FLAG_NAME`` / ``ENV_FLAG_TRUTHY``
      constants. PV-03 retirement is surgical — only the v9.3.0 PV-06
      shortcut surface goes; the activation + cascade contracts stay
      byte-stable.

    * ``workflow-system/agent/references/env-flags.md`` does NOT
      contain the literal ``DEVOLAFLOW_SIMPLE_SHORTCUT`` env-flag name
      anywhere (negative substring pin; the retirement note paraphrases
      via "the simple-task auto-shortcut env flag" so the literal
      string is fully retired from the canonical inventory). Env-flag
      count goes 8 → 7 per W-20 reuse-first preservation (no new flag
      introduced; one retired).

    * ``tests/test_simple_shortcut.py`` is DELETED (negative file pin).
      The 9-test verdict-matrix coverage is no longer needed because
      the underlying surface no longer exists.

    Coupled invariants verified GREEN at PV-03 close (no source edits
    to schemas / .rules / SKILL / CHANGELOG per cycle plan §8.4):

    * A-2.4 multi-baseline byte test: 32/32 PASS unchanged
      (canonical_order stays at 17; PV-04 owns the schema NEST that
      adds the 33rd baseline).
    * S-10 hook-chain byte-id: 10/10 PASS unchanged.
    * v11.1.1 D-1 CHANGELOG lint: PASS (PV-03 makes ZERO CHANGELOG
      edits per cycle plan §8.4 PV-07-owns-rollup).
    * W-21 Soul-set freeze preserved at 10 entries (no S-11 proposed;
      this is a Workflow / Convention edit, not a Soul invariant).
    * W-20 reuse-first preserved — env-flag count moves 8 → 7 (one
      retired, zero introduced; orthogonality test is moot for a pure
      retirement).
    * A-7 cascade-depth invariant preserved — the cascade contract
      lives at ``cascade_requirement`` which is the v11.1.0 PV-02
      surface and is INTACT at PV-03 close.

    Source: ``.local/research/v12.0.0_gap_analysis.md`` §4 (D-2 spec)
    + §8.4 (PV-07-owns-bump separation rationale) +
    ``docs/cycle-archive/v11.1.0/retrospective.md`` §3 D-2 (telegraph
    rationale; env-flag count 8 → 7).
    """
    # ----- 1. change_activation.py — deleted-functions AST negative pin -----
    src_path = project_root / _V12_0_0_PV03_CHANGE_ACTIVATION_FILE
    assert src_path.is_file(), (
        f"W-18 v12.0.0 PV-03 violation: {_V12_0_0_PV03_CHANGE_ACTIVATION_FILE} "
        "missing — release-blocker. The retirement deletes 5 surfaces FROM "
        "this file but the file itself MUST remain (it owns the preserved "
        "activation + cascade API)."
    )
    src_module = ast.parse(src_path.read_text(encoding="utf-8"))

    defined_function_names = {
        node.name
        for node in src_module.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    leaked_functions = sorted(_V12_0_0_PV03_DELETED_FUNCTIONS & defined_function_names)
    assert not leaked_functions, (
        f"W-18 v12.0.0 PV-03 violation: {_V12_0_0_PV03_CHANGE_ACTIVATION_FILE} "
        f"still defines retired functions {leaked_functions!r}. The v12.0.0 "
        "PV-03 D-2 retirement deletes the v9.3.0 PV-06 shortcut surface "
        "ENTIRELY — re-introducing any of these symbols breaks the "
        "BREAKING-graduation contract documented in the v11.1.0 "
        "retrospective §3 D-2 telegraph and the v12.0.0 CHANGELOG "
        "migration table."
    )

    # ----- 2. change_activation.py — deleted-constants AST negative pin -----
    defined_assign_names: set[str] = set()
    for node in src_module.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    defined_assign_names.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            defined_assign_names.add(node.target.id)
    leaked_names = sorted(_V12_0_0_PV03_DELETED_NAMES & defined_assign_names)
    assert not leaked_names, (
        f"W-18 v12.0.0 PV-03 violation: {_V12_0_0_PV03_CHANGE_ACTIVATION_FILE} "
        f"still defines retired top-level names {leaked_names!r}. Per the "
        "PV-03 D-2 retirement these are companion surfaces to the deleted "
        "shortcut helpers and MUST be removed alongside the functions."
    )

    # ----- 3. change_activation.py — preserved API positive pin -----
    missing_functions = sorted(_V12_0_0_PV03_PRESERVED_FUNCTIONS - defined_function_names)
    assert not missing_functions, (
        f"W-18 v12.0.0 PV-03 violation: {_V12_0_0_PV03_CHANGE_ACTIVATION_FILE} "
        f"removed preserved-API functions {missing_functions!r}. PV-03 D-2 "
        "is a SURGICAL retirement of the v9.3.0 PV-06 shortcut surface "
        "ONLY — the v11.x activation + cascade contracts MUST stay intact."
    )
    missing_names = sorted(_V12_0_0_PV03_PRESERVED_NAMES - defined_assign_names)
    assert not missing_names, (
        f"W-18 v12.0.0 PV-03 violation: {_V12_0_0_PV03_CHANGE_ACTIVATION_FILE} "
        f"removed preserved-API top-level names {missing_names!r}. PV-03 D-2 "
        "is a SURGICAL retirement — the activation env-flag constants and "
        "Literal type aliases MUST stay intact."
    )

    # ----- 4. env-flags.md — DEVOLAFLOW_SIMPLE_SHORTCUT literal negative pin -----
    env_flags_path = project_root / _V12_0_0_PV03_ENV_FLAGS_FILE
    assert env_flags_path.is_file(), (
        f"W-18 v12.0.0 PV-03 violation: {_V12_0_0_PV03_ENV_FLAGS_FILE} "
        "missing — release-blocker. The retirement edits this file's §2.12 "
        "subsection but the file itself MUST remain (it owns the canonical "
        "env-flag inventory across cycles)."
    )
    env_flags_text = env_flags_path.read_text(encoding="utf-8")
    for sub in _V12_0_0_PV03_ENV_FLAGS_NEGATIVE_SUBSTRINGS:
        assert sub not in env_flags_text, (
            f"W-18 v12.0.0 PV-03 violation: {_V12_0_0_PV03_ENV_FLAGS_FILE} "
            f"still contains the retired env-flag literal {sub!r}. Per the "
            "PV-03 D-2 retirement the env-flag inventory MUST drop the "
            "v9.3.0 PV-06 entry entirely; the retirement note paraphrases "
            "via 'the simple-task auto-shortcut env flag' so the literal "
            "name is fully retired."
        )

    # ----- 5. test_simple_shortcut.py — file-deletion negative pin -----
    deleted_test_path = project_root / _V12_0_0_PV03_DELETED_TEST_FILE
    assert not deleted_test_path.exists(), (
        f"W-18 v12.0.0 PV-03 violation: {_V12_0_0_PV03_DELETED_TEST_FILE} "
        "still exists. Per the PV-03 D-2 retirement this 9-test file pinned "
        "the v9.3.0 PV-06 shortcut verdict matrix — with the surface gone, "
        "the tests have no remaining contract to enforce and MUST be "
        "deleted."
    )


# ---------------------------------------------------------------------------
# v12.0.0 PV-04 NEW — Subagent-pattern NEST schema lint
#
# Per W-18 sequencing the ghost-audit refresh MUST land BEFORE the v12.0.0
# CHANGELOG entry (which PV-07 owns). This stanza closes that precondition
# at the source of the NEW NEST landing: schemas/lean-dispatch.yaml +
# src/devolaflow/feedback.py (helper wiring) + the v12.0.0 baseline
# fixture + the new TestCascadePatternConsistency test class. The
# CHANGELOG positive-substring pin is intentionally OMITTED here —
# PV-07 owns the rollup CHANGELOG, and per the v12.0.0 cycle plan §8.4
# the version bump + CHANGELOG entry are deferred to the cycle-rollup
# commit. PV-04 only ships the source-side / fixture-side / test-side
# pins. Source: ``.local/research/v12.0.0_gap_analysis.md`` §5 (NEST
# schema spec) + §8.4 (PV-07 owns the bump) +
# ``docs/cycle-archive/v11.4.0/other/v11.4.0_subagent_pattern_analysis.md``
# §7.1 (NEST verdict pre-staged).
_V12_0_0_PV04_SCHEMA_FILE: Path = Path("schemas/lean-dispatch.yaml")


# v14.5.0 (ADR-006 G-025) ghost-pin update: populate_cascade_gate_fields —
# the helper carrying the ``select_pattern(...)`` call this stanza pins —
# moved VERBATIM from feedback.py to the new owner module gate/cascade.py;
# the historical devolaflow.feedback import path keeps working via a
# permanent identity-preserving re-export shim (pinned by
# tests/test_module_split_shims.py). The AST call pin below follows the
# re-export truth's owner module.
_V12_0_0_PV04_FEEDBACK_FILE: Path = Path("src/devolaflow/gate/cascade.py")


_V12_0_0_PV04_BASELINE_FILE: Path = Path(
    "benchmarks/devolaflow_context/baselines/layout_invariant_v12.0.0.yaml"
)


_V12_0_0_PV04_CASCADE_TEST_FILE: Path = Path("tests/test_cascade_enforcement.py")


_V12_0_0_PV04_MULTI_BASELINE_TEST_FILE: Path = Path("tests/test_layout_invariant_multi_baseline.py")


def test_v12_0_0_pv04_subagent_nest_schema(project_root: Path) -> None:
    """W-18 v12.0.0 PV-04 NEW: Subagent-pattern NEST schema source-side pins.

    Discharges the W-18 precondition for the NEW v12.0.0 PV-04 NEST
    landing. Per the v12.0.0 cycle plan §8.4 the version bump +
    CHANGELOG rollup are deferred to PV-07; this stanza only pins the
    source-side surfaces that PV-04 owns. PV-07's W-18 stanza will
    extend this with the ``## [12.0.0]`` CHANGELOG positive-substring
    assertion.

    Surfaces pinned (v12.0.0 PV-04 NEW NEST scope; third of 4 v12.0.0
    graduation commitments — sister PVs PV-02 D-1 STRICT promotion,
    PV-03 D-2 SHORTCUT_SIMPLE retirement, PV-05 D-5 CONDITIONAL):

    * ``schemas/lean-dispatch.yaml`` contains the literal substring
      ``subagent_pattern`` (positive substring pin) — the new NEST
      sub-field is declared under the existing ``gate`` block per
      A-2.3 NEST decision rule. canonical_order length stays at 17,
      schema version stays at 6 (no top-level dispatch key added).

    * ``src/devolaflow/feedback.py`` contains a CALL to
      ``select_pattern`` (AST FunctionCall pin) — the dispatcher-side
      wiring that populates ``gate.subagent_pattern`` from the four
      v12.0.0 PV-04 input axes (model_tier / task_count /
      parallel_independence / persistent_state_needed) per the helper
      extension to ``populate_cascade_gate_fields``.

    * ``benchmarks/devolaflow_context/baselines/layout_invariant_v12.0.0.yaml``
      EXISTS on disk (file pin) — the 15th multi-baseline byte-test
      pin per A-2.4 (32/32 → 33/33 GREEN).

    * ``tests/test_cascade_enforcement.py`` contains the
      ``TestCascadePatternConsistency`` class (AST ClassDef pin) —
      the v12.0.0 PV-04 cross-couple consistency contract pins (7
      NEW tests pinning cascade × subagent-pattern orthogonality).

    * ``tests/test_layout_invariant_multi_baseline.py`` references the
      literal substring ``v12.0.0`` (positive substring pin) — the
      new multi-baseline pin is wired into the test registry. The
      multi-baseline byte-test count moves 32 → 33; the new entry is
      ``test_v12_0_0_baseline_byte_identical``.

    Coupled invariants verified GREEN at PV-04 close (no source edits
    to .rules / SKILL / CHANGELOG / version per cycle plan §8.4):

    * A-2.4 multi-baseline byte test: 32/32 → 33/33 GREEN (the new
      v12.0.0 baseline pins the NEST shape; absence is canonical so
      all 32 prior baselines pass byte-identically).
    * S-10 hook-chain byte-id: 10/10 PASS unchanged (the NEST
      sub-field is OPTIONAL; legacy v11.x dispatches without
      ``gate.subagent_pattern`` flow through byte-identically).
    * v11.1.1 D-1 CHANGELOG lint: PASS (PV-04 makes ZERO CHANGELOG
      edits per cycle plan §8.4 PV-07-owns-rollup).
    * W-21 Soul-set freeze preserved at 10 entries (no S-11 proposed;
      this is a Convention / Architecture edit, not a Soul invariant).
    * W-20 reuse-first preserved — no NEW ``DEVOLAFLOW_*`` env flag
      introduced (the new sub-field is purely a dispatch payload field;
      activation is via the four kw-only axes, not an env flag).
    * A-7 cascade-depth invariant preserved — the cascade contract
      lives at ``gate.cascade_required`` + ``gate.cascade_min_layers``
      which PV-04 leaves byte-stable; the new ``gate.subagent_pattern``
      is orthogonal to cascade depth per W-24.
    * Frozen prefix (positions 1-12) preserved per A-2.1; the new
      sub-field NESTs UNDER position 12 (``gate``), preserving the
      cache-prefix length every L0/L1/L2/L3 dispatcher keys on.

    Source: ``.local/research/v12.0.0_gap_analysis.md`` §5 (NEST schema
    spec) + §8.4 (PV-07 owns the bump) +
    ``docs/cycle-archive/v11.4.0/other/v11.4.0_subagent_pattern_analysis.md``
    §7.1 (NEST verdict pre-staged + canonical_order=17 invariant).
    """
    # ----- 1. schemas/lean-dispatch.yaml — subagent_pattern positive pin -----
    schema_path = project_root / _V12_0_0_PV04_SCHEMA_FILE
    assert schema_path.is_file(), (
        f"W-18 v12.0.0 PV-04 violation: {_V12_0_0_PV04_SCHEMA_FILE} missing — "
        "release-blocker. The NEST schema lands AT this file."
    )
    schema_text = schema_path.read_text(encoding="utf-8")
    assert "subagent_pattern" in schema_text, (
        f"W-18 v12.0.0 PV-04 violation: {_V12_0_0_PV04_SCHEMA_FILE} missing "
        "the literal substring 'subagent_pattern'. The v12.0.0 PV-04 NEST "
        "extension MUST declare the new sub-field under the ``gate`` block "
        "per A-2.3 NEST decision rule. See "
        ".local/research/v12.0.0_gap_analysis.md §5 for the canonical NEST "
        "verdict + schema sub-field shape."
    )

    # Cross-anchor: the schema's canonical_order length stays at 17 +
    # version stays at 6 (NEST, not APPEND). Drift here would be a
    # release-blocker per A-2.4.
    schema_data = yaml.safe_load(schema_text)
    canonical_order = schema_data["layout_invariant"]["canonical_order"]
    schema_version = schema_data["layout_invariant"]["version"]
    assert len(canonical_order) == 17, (
        f"W-18 v12.0.0 PV-04 violation: canonical_order length is "
        f"{len(canonical_order)}; expected 17 per A-2.4 + NEST decision "
        "(no top-level key added at v12.0.0 PV-04)."
    )
    assert schema_version == 6, (
        f"W-18 v12.0.0 PV-04 violation: schema version is {schema_version}; "
        "expected 6 per A-2.3 NEST contract (sub-field addition, no version "
        "bump)."
    )

    # ----- 2. src/devolaflow/feedback.py — select_pattern call AST pin -----
    feedback_path = project_root / _V12_0_0_PV04_FEEDBACK_FILE
    assert feedback_path.is_file(), (
        f"W-18 v12.0.0 PV-04 violation: {_V12_0_0_PV04_FEEDBACK_FILE} missing — "
        "release-blocker. The dispatcher-side helper wiring lands AT this file."
    )
    feedback_module = ast.parse(feedback_path.read_text(encoding="utf-8"))

    # AST walk: find the ``select_pattern(...)`` call inside any
    # function body. The call MUST appear in
    # ``populate_cascade_gate_fields`` (the helper extension), but we
    # do not pin the enclosing function name here — only that
    # ``select_pattern`` IS called somewhere in feedback.py.
    select_pattern_calls: list[ast.Call] = []
    for node in ast.walk(feedback_module):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "select_pattern"
        ):
            select_pattern_calls.append(node)
    assert select_pattern_calls, (
        f"W-18 v12.0.0 PV-04 violation: {_V12_0_0_PV04_FEEDBACK_FILE} contains "
        "no AST call to ``select_pattern``. The v12.0.0 PV-04 NEST extension "
        "wires the dispatcher-side helper to invoke "
        "``devolaflow.skills.subagent_pattern.select_pattern`` to derive "
        "``gate.subagent_pattern`` from the four input axes; this lint "
        "verifies the wiring landed."
    )

    # ----- 3. v12.0.0 baseline file — fixture existence pin -----
    baseline_path = project_root / _V12_0_0_PV04_BASELINE_FILE
    assert baseline_path.is_file(), (
        f"W-18 v12.0.0 PV-04 violation: {_V12_0_0_PV04_BASELINE_FILE} missing — "
        "release-blocker. The 15th multi-baseline byte-test pin (A-2.4) MUST "
        "exist as a checked-in fixture; see "
        ".local/research/v12.0.0_gap_analysis.md §5.3 for the regen recipe."
    )

    # ----- 4. tests/test_cascade_enforcement.py — TestCascadePatternConsistency class pin -----
    cascade_test_path = project_root / _V12_0_0_PV04_CASCADE_TEST_FILE
    assert cascade_test_path.is_file(), (
        f"W-18 v12.0.0 PV-04 violation: {_V12_0_0_PV04_CASCADE_TEST_FILE} "
        "missing — release-blocker."
    )
    cascade_test_module = ast.parse(cascade_test_path.read_text(encoding="utf-8"))
    consistency_class = next(
        (
            node
            for node in cascade_test_module.body
            if isinstance(node, ast.ClassDef) and node.name == "TestCascadePatternConsistency"
        ),
        None,
    )
    assert consistency_class is not None, (
        f"W-18 v12.0.0 PV-04 violation: {_V12_0_0_PV04_CASCADE_TEST_FILE} "
        "missing the ``TestCascadePatternConsistency`` class. The v12.0.0 "
        "PV-04 cross-couple consistency contract (cascade × subagent-pattern "
        "orthogonality) lands as a NEW test class with 5-7 NEW test "
        "methods; see .local/research/v12.0.0_gap_analysis.md §5.5 for "
        "the canonical 7 test names."
    )

    # ----- 5. tests/test_layout_invariant_multi_baseline.py — v12.0.0 substring pin -----
    multi_baseline_test_path = project_root / _V12_0_0_PV04_MULTI_BASELINE_TEST_FILE
    assert multi_baseline_test_path.is_file(), (
        f"W-18 v12.0.0 PV-04 violation: {_V12_0_0_PV04_MULTI_BASELINE_TEST_FILE} "
        "missing — release-blocker."
    )
    multi_baseline_test_text = multi_baseline_test_path.read_text(encoding="utf-8")
    assert "v12.0.0" in multi_baseline_test_text, (
        f"W-18 v12.0.0 PV-04 violation: {_V12_0_0_PV04_MULTI_BASELINE_TEST_FILE} "
        "missing the literal substring 'v12.0.0'. The new baseline pin (the "
        "33rd multi-baseline byte test) MUST register the v12.0.0 fixture; "
        "see .local/research/v12.0.0_gap_analysis.md §5.3 for the wiring "
        "recipe (PV-04 step 2 — add the v12.0.0 baseline to the "
        "parametrized fixture list)."
    )


# ---------------------------------------------------------------------------
# v12.0.0 PV-05 — cleanup-absorption stanza (compiler.py post-truncation fix)
# ---------------------------------------------------------------------------
# Per the v12.0.0 gap analysis §6 verdict, the originally-telegraphed D-5
# CHANGELOG single-application CI lint is DEFERRED to v13.0.0 SI-1
# evaluation (5/5 audit clean across v11.1.1..v11.4.0 — no recurrence; the
# existing W-18 PV-close stanza + v11.1.1 D-1 in-test lint are sufficient).
# PV-05 instead absorbs the v11.4.0 retrospective §3 deferred bug: the
# `compiler.py::_truncate_to_budget` post-truncation `layers_included`
# accounting bug, which silently masked the v11.4.0 cursor 11979/12000
# saturation pre-bump (the Style Rules layer was dropped by the truncation
# loop but `RuleCompiler.compile` reported all 5 layers in
# `layers_included`). PV-05 ships a 1-function source fix (tuple return
# from `_truncate_to_budget`) + a regression test in
# `tests/test_local_compiler.py`. The CHANGELOG positive-substring pin is
# intentionally OMITTED here — PV-07 owns the rollup CHANGELOG, and per
# the v12.0.0 gap analysis §8.4 the version bump + CHANGELOG entry are
# deferred to the cycle-rollup commit. PV-05 only ships the source-side
# + test-side pins. Source: ``.local/research/v12.0.0_gap_analysis.md``
# §6 (D-5 DEFER verdict + cleanup absorption rationale) +
# ``docs/cycle-archive/v11.4.0/v11.4.0_retrospective.md`` §3 deferred-
# bugs inventory line "compiler.py post-truncation layers_included
# accounting bug" + §4 key learning 3.
_V12_0_0_PV05_COMPILER_FILE: Path = Path("src/devolaflow/local/compiler.py")


_V12_0_0_PV05_COMPILER_TEST_FILE: Path = Path("tests/test_local_compiler.py")


_V12_0_0_PV05_REQUIRED_NEW_TEST: str = "test_compile_layers_included_reflects_post_truncation_state"


def test_v12_0_0_pv05_compiler_layers_included_post_truncation(
    project_root: Path,
) -> None:
    """W-18 v12.0.0 PV-05 NEW: compiler.py post-truncation accounting fix.

    Discharges the W-18 precondition for the v12.0.0 PV-05 cleanup-
    absorption landing. Per the v12.0.0 gap analysis §6 D-5 is DEFERRED
    to v13.0.0 SI-1 (5/5 audit clean = no recurrence; W-18 + v11.1.1
    D-1 lint sufficient). PV-05 absorbs the v11.4.0 retrospective §3
    deferred bug instead: the ``compiler.py::_truncate_to_budget``
    post-truncation ``layers_included`` accounting bug, which silently
    masked the v11.4.0 cursor 11979/12000 saturation pre-bump (the
    Style Rules layer was dropped by the truncation loop but
    ``RuleCompiler.compile`` reported ``layers_included=['soul',
    'architecture', 'conventions', 'workflow', 'style']`` because the
    list reflected pre-truncation state).

    Surfaces pinned (v12.0.0 PV-05 NEW cleanup scope; fourth and final
    of the 4 v12.0.0 graduation commitments — sister PVs PV-02 D-1
    STRICT promotion, PV-03 D-2 SHORTCUT_SIMPLE retirement, PV-04 NEW
    NEST schema; D-5 CHANGELOG CI lint is DEFERRED per gap analysis §6):

    * ``src/devolaflow/local/compiler.py`` — the ``_truncate_to_budget``
      function returns a TUPLE (AST positive pin: at least one
      ``return`` statement inside the function body has an
      ``ast.Tuple`` value node). Pre-fix the function returned a single
      string (the rendered content); the v12.0.0 PV-05 fix changes the
      signature to ``tuple[str, list[RuleLayer]]`` so the dispatcher-
      side caller (``_compile_target``) can use the post-truncation
      retained list to populate ``CompileResult.layers_included``.

    * ``tests/test_local_compiler.py`` contains the regression test
      ``test_compile_layers_included_reflects_post_truncation_state``
      (AST FunctionDef pin) — pins the post-truncation accounting
      contract against a tight-budget scenario that forces the lowest-
      priority layer to be dropped. The test asserts the dropped layer
      is ABSENT from ``layers_included`` (the bug-positive pin) and
      that ``soul`` (always_include=True) survives (the contract pin).

    Coupled invariants verified GREEN at PV-05 close (no source edits
    to .rules / SKILL / CHANGELOG / version per cycle plan):

    * ``test_rule_surfaces_compile_only`` (ADR-007 D5 drift detection):
      PASS — the fix only edits ``_truncate_to_budget`` + the truncation
      branch of ``_compile_target``; the rendered output for the cursor
      + agents_md targets is byte-identical because the current 14000-
      token budget does NOT trigger truncation on either target. The
      compiled .cursor/rules/repo-governance.mdc + AGENTS.md SHA-256
      values stay byte-stable.
    * Happy-path behaviour preserved: when ``tokens <= tc.token_budget``,
      ``layers_included`` continues to reflect the ``selected`` list
      (no truncation runs, so ``retained`` stays None and the report
      falls back to ``selected``).
    * W-21 Soul-set freeze preserved at 10 entries (cleanup edit; not
      a Soul invariant addition).
    * W-20 reuse-first preserved — no NEW ``DEVOLAFLOW_*`` env flag
      introduced (pure code-correctness fix; no behavioural axis).

    Source: ``.local/research/v12.0.0_gap_analysis.md`` §6 (D-5 DEFER
    verdict + cleanup absorption rationale) +
    ``docs/cycle-archive/v11.4.0/v11.4.0_retrospective.md`` §3 deferred
    bug "compiler.py post-truncation layers_included accounting bug"
    + §4 key learning 3.
    """
    # ----- 1. compiler.py — _truncate_to_budget tuple-return AST pin -----
    compiler_path = project_root / _V12_0_0_PV05_COMPILER_FILE
    assert compiler_path.is_file(), (
        f"W-18 v12.0.0 PV-05 violation: {_V12_0_0_PV05_COMPILER_FILE} "
        "missing — release-blocker. The post-truncation accounting fix "
        "lands AT this file."
    )
    compiler_module = ast.parse(compiler_path.read_text(encoding="utf-8"))

    truncate_func: ast.FunctionDef | None = None
    for node in ast.walk(compiler_module):
        if isinstance(node, ast.FunctionDef) and node.name == "_truncate_to_budget":
            truncate_func = node
            break
    assert truncate_func is not None, (
        f"W-18 v12.0.0 PV-05 violation: {_V12_0_0_PV05_COMPILER_FILE} missing "
        "the ``_truncate_to_budget`` function. The fix MUST preserve the "
        "function name (``_compile_target`` calls it). See v11.4.0 "
        "retrospective §3 deferred bug + §4 key learning 3."
    )

    return_nodes = [n for n in ast.walk(truncate_func) if isinstance(n, ast.Return)]
    assert return_nodes, (
        f"W-18 v12.0.0 PV-05 violation: {_V12_0_0_PV05_COMPILER_FILE} "
        "``_truncate_to_budget`` has no ``return`` statement — the "
        "function must return ``(content, retained_layers)`` per the "
        "v12.0.0 PV-05 contract."
    )
    tuple_returns = [n for n in return_nodes if isinstance(n.value, ast.Tuple)]
    assert tuple_returns, (
        f"W-18 v12.0.0 PV-05 violation: {_V12_0_0_PV05_COMPILER_FILE} "
        "``_truncate_to_budget`` does NOT return a tuple. Pre-fix the "
        "function returned a single string (the rendered content); the "
        "v12.0.0 PV-05 fix changes the signature to return "
        "``(content, retained_layers)`` so callers can report the "
        "post-truncation layer set in ``layers_included``. See "
        ".local/research/v12.0.0_gap_analysis.md §6 + v11.4.0 "
        "retrospective §3 deferred bug + §4 key learning 3 for the "
        "rationale."
    )

    # ----- 2. tests/test_local_compiler.py — regression test AST pin -----
    test_path = project_root / _V12_0_0_PV05_COMPILER_TEST_FILE
    assert test_path.is_file(), (
        f"W-18 v12.0.0 PV-05 violation: {_V12_0_0_PV05_COMPILER_TEST_FILE} "
        "missing — release-blocker."
    )
    test_module = ast.parse(test_path.read_text(encoding="utf-8"))
    defined_tests: set[str] = {
        node.name
        for node in ast.walk(test_module)
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    }
    assert _V12_0_0_PV05_REQUIRED_NEW_TEST in defined_tests, (
        f"W-18 v12.0.0 PV-05 violation: {_V12_0_0_PV05_COMPILER_TEST_FILE} "
        f"missing the regression test ``{_V12_0_0_PV05_REQUIRED_NEW_TEST}``. "
        "The v12.0.0 PV-05 cleanup absorption MUST add a regression test "
        "that pins the post-truncation accounting contract; see "
        ".local/research/v12.0.0_gap_analysis.md §6 + v11.4.0 "
        "retrospective §3 deferred bug + §4 key learning 3."
    )
