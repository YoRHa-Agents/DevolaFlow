"""Ghost audit — per-cycle W-18 feature stanzas for the v12.2 cycle.

Split from ``tests/test_no_ghost_features.py`` per v15-ADR-001
(v14.3.0). New W-18 stanzas for a v12.2.x release append HERE; the
next MINOR cycle rotates to a fresh ``test_features_v<MAJ>_<MIN>.py``.
"""

from __future__ import annotations

import ast
from pathlib import Path

# ---------------------------------------------------------------------------
# v12.2.0 W-18 ghost-audit refresh — PV-02 gitignore selective whitelist.
# ---------------------------------------------------------------------------
#
# Per W-18 sequencing the ghost-audit refresh MUST land BEFORE the v12.2.0
# CHANGELOG entry that mentions the gitignore selective whitelist fix.
# This stanza pins the v12.2.0 PV-02 surface:
#
# * src/devolaflow/local/workspace.py contains the 3 required positive
#   whitelist rules (.local/* + !.local/memory/specs/ + !.local/research/)
#   in `_LOCAL_WHITELIST_BLOCK_LINES` and `_LOCAL_WHITELIST_REQUIRED_RULES`.
# * The repo-root .gitignore self-fix carries the same 3 rules — so the
#   DevolaFlow source repo demonstrates the same pattern it teaches.
# * `_has_correct_local_whitelist` is importable from workspace.
# * `_V92_LOCAL_BROAD_RULE = ".local/"` is present (the rule v12.2.0
#   supersedes).
#
# Source: ``.local/research/v12.2.0_gap_analysis.md`` §2 D-1 +
# ``.local/feedbacks/feedback_for_v12.1.0.md`` (the user feedback line
# that motivated this PV).
# ---------------------------------------------------------------------------
_V12_2_0_WORKSPACE_FILE: Path = Path("src/devolaflow/local/workspace.py")


_V12_2_0_REPO_GITIGNORE: Path = Path(".gitignore")


_V12_2_0_TEST_FILE: Path = Path("tests/test_scaffold_gitignore_audit.py")


_V12_2_0_WHITELIST_REQUIRED_RULES: frozenset[str] = frozenset(
    {
        ".local/*",
        "!.local/memory/specs/",
        "!.local/research/",
        # v14.0.0 — human INPUT zone re-include key (D-4 / ADR-2). The live
        # `_LOCAL_WHITELIST_REQUIRED_RULES` grew by this 4th rule when the
        # `.local/human/input/**` whitelist landed; this pin tracks it.
        "!.local/human/",
    }
)


_V12_2_0_SUPERSEDED_RULE: str = ".local/"


_V12_2_0_REQUIRED_GITIGNORE_FN_NAMES: frozenset[str] = frozenset(
    {
        "test_no_gitignore_writes_v12_2_0_whitelist_block",
        "test_gitignore_without_local_rule_appends_v12_2_0_block",
        "test_v9_2_3_broad_local_rule_is_repaired_to_whitelist",
        "test_legacy_local_whitelist_block_is_graduated_to_v12_2_0",
        "test_v12_2_0_whitelist_is_idempotent_no_op_second_run",
        "test_narrow_pre_existing_rule_triggers_warning_alongside_whitelist",
    }
)


def test_v12_2_0_gitignore_whitelist_repair(project_root: Path) -> None:
    """W-18 v12.2.0 D-1: gitignore selective whitelist + repair surface.

    Discharges the W-18 precondition for the v12.2.0 MINOR CHANGELOG
    entry mentioning the gitignore fix. Pins:

    * src/devolaflow/local/workspace.py declares the 3 required positive
      whitelist rules in both `_LOCAL_WHITELIST_BLOCK_LINES` AND
      `_LOCAL_WHITELIST_REQUIRED_RULES`. Substring presence — robust
      against block-comment refactor; fails only on rule rename / removal.
    * src/devolaflow/local/workspace.py preserves `_V92_LOCAL_BROAD_RULE`
      so the repair path knows which v9.2.3 rule to graduate.
    * src/devolaflow/local/workspace.py exports `_has_correct_local_whitelist`
      (the detection helper used by `_audit_gitignore_coverage` and
      `ensure_local_gitignore`).
    * The repo-root `.gitignore` carries the 3 required positive rules
      (DevolaFlow source repo demonstrates the pattern it teaches).
    * The companion test file defines the 6 canonical PV-02 test functions.

    Coupled invariants verified GREEN at v12.2.0 PV-02 close:
    * Existing test suite (101 init + scaffold tests) PASS unchanged
      against the new whitelist semantics.
    * W-18 v9.2.3 ghost-audit stanza still GREEN (the v9.2.3 public
      symbols `_audit_gitignore_coverage` + `last_gitignore_audit`
      remain importable; `VALID_MODES` unchanged).
    * W-21 Soul-set freeze preserved at 10 entries (gitignore fix at
      runtime not at rule corpus).
    * W-20 reuse-first preserved at 7 env flags (no new
      `DEVOLAFLOW_*` flag — fix is operator-facing, not env-gated).

    Source: ``.local/research/v12.2.0_gap_analysis.md`` §2 D-1 +
    ``.local/feedbacks/feedback_for_v12.1.0.md``.
    """
    workspace_path = project_root / _V12_2_0_WORKSPACE_FILE
    assert workspace_path.is_file(), (
        f"W-18 v12.2.0 violation: {_V12_2_0_WORKSPACE_FILE} missing — release blocker."
    )
    workspace_text = workspace_path.read_text(encoding="utf-8")

    for required_rule in sorted(_V12_2_0_WHITELIST_REQUIRED_RULES):
        assert required_rule in workspace_text, (
            f"W-18 v12.2.0 violation: {_V12_2_0_WORKSPACE_FILE} missing required "
            f"whitelist rule literal {required_rule!r}. The whitelist block MUST "
            f"declare every positive rule so consumer repos get the team-collab "
            f"subdirs (.local/memory/specs/ + .local/research/ + the v14.0.0 "
            f".local/human/input/ zone) tracked by default. See gap analysis §2 D-1."
        )

    assert "_V92_LOCAL_BROAD_RULE" in workspace_text, (
        f"W-18 v12.2.0 violation: {_V12_2_0_WORKSPACE_FILE} missing "
        f"`_V92_LOCAL_BROAD_RULE` constant. The repair path MUST preserve "
        f"the v9.2.3 broad rule literal so it can detect and graduate "
        f"existing repos to the v12.2.0 whitelist."
    )

    assert "_has_correct_local_whitelist" in workspace_text, (
        f"W-18 v12.2.0 violation: {_V12_2_0_WORKSPACE_FILE} missing "
        f"`_has_correct_local_whitelist` helper. The detection helper is the "
        f"keystone for both `_audit_gitignore_coverage` suppression and "
        f"`ensure_local_gitignore` idempotency."
    )

    from devolaflow.local.workspace import (
        _LOCAL_WHITELIST_BLOCK_LINES,
        _LOCAL_WHITELIST_REQUIRED_RULES,
        _has_correct_local_whitelist,
    )

    assert callable(_has_correct_local_whitelist), (
        "W-18 v12.2.0 violation: _has_correct_local_whitelist must be importable + callable"
    )
    assert _LOCAL_WHITELIST_REQUIRED_RULES == _V12_2_0_WHITELIST_REQUIRED_RULES, (
        f"W-18 v12.2.0 violation: workspace._LOCAL_WHITELIST_REQUIRED_RULES = "
        f"{_LOCAL_WHITELIST_REQUIRED_RULES!r}; expected {_V12_2_0_WHITELIST_REQUIRED_RULES!r}. "
        f"The required-rules membership is the contract surface the test pins."
    )
    for required in _V12_2_0_WHITELIST_REQUIRED_RULES:
        assert required in _LOCAL_WHITELIST_BLOCK_LINES, (
            f"W-18 v12.2.0 violation: _LOCAL_WHITELIST_BLOCK_LINES missing "
            f"required rule {required!r}; the block + the required-rules set "
            f"MUST agree on the 3 positive rules."
        )

    repo_gitignore = project_root / _V12_2_0_REPO_GITIGNORE
    assert repo_gitignore.is_file(), (
        f"W-18 v12.2.0 violation: {_V12_2_0_REPO_GITIGNORE} missing — release blocker."
    )
    repo_gitignore_lines = repo_gitignore.read_text(encoding="utf-8").splitlines()
    for required_rule in sorted(_V12_2_0_WHITELIST_REQUIRED_RULES):
        assert required_rule in repo_gitignore_lines, (
            f"W-18 v12.2.0 violation: DevolaFlow source repo {_V12_2_0_REPO_GITIGNORE} "
            f"missing required v12.2.0 whitelist rule {required_rule!r}. The source "
            f"repo MUST demonstrate the same pattern it teaches consumer repos."
        )
    assert _V12_2_0_SUPERSEDED_RULE not in repo_gitignore_lines, (
        f"W-18 v12.2.0 violation: DevolaFlow source repo {_V12_2_0_REPO_GITIGNORE} "
        f"still carries the v9.2.3 broad `{_V12_2_0_SUPERSEDED_RULE}` rule that "
        f"v12.2.0 PV-02 supersedes. The source repo MUST be graduated to the "
        f"v12.2.0 whitelist alongside the helper-code change."
    )

    test_path = project_root / _V12_2_0_TEST_FILE
    assert test_path.is_file(), (
        f"W-18 v12.2.0 violation: {_V12_2_0_TEST_FILE} missing — release blocker."
    )
    test_module = ast.parse(test_path.read_text(encoding="utf-8"))
    defined = {
        node.name
        for node in test_module.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    missing = sorted(_V12_2_0_REQUIRED_GITIGNORE_FN_NAMES - defined)
    assert not missing, (
        f"W-18 v12.2.0 violation: {_V12_2_0_TEST_FILE} missing required NEW test "
        f"functions {missing!r}. Required canonical 6-name set per PV-02 dispatch: "
        f"{sorted(_V12_2_0_REQUIRED_GITIGNORE_FN_NAMES)!r}; defined: {sorted(defined)!r}."
    )


# ---------------------------------------------------------------------------
# v12.2.0 PV-03 W-18 ghost-audit refresh — Mnimiy 3-rule behavioral extension.
# ---------------------------------------------------------------------------
#
# Per W-18 sequencing the ghost-audit refresh MUST land BEFORE the v12.2.0
# CHANGELOG entry mentioning the BG-005..BG-007 behavioral primitive
# additions. This stanza pins the v12.2.0 PV-03 surface:
#
# * workflow-system/agent/references/behavioral-guidelines.md documents
#   all 3 NEW rule sections (BG-005, BG-006, BG-007) with their literal
#   IDs and dispatch field names (no_llm_for_deterministic,
#   surface_conflicts, convention_first).
# * src/devolaflow/task_adaptive_selector.py::_compose_behavioral_block
#   renders the 3 NEW rule bullets when active (substring presence pin).
# * schemas/lean-dispatch.yaml#lean_format_spec.behavioral_guidelines.fields
#   declares the 3 NEW sub-fields with severity classification.
# * workflow-system/agent/context_profiles.yaml#meta.behavioral_guidelines_defaults
#   carries per-tier defaults for the 3 NEW keys.
# * tests/test_behavioral_guidelines.py declares the canonical 7 PV-03
#   test functions (TestMnimiyBehavioralExtensions class).
#
# Source: ``.local/research/v12.2.0_gap_analysis.md`` §2 D-2.
# ---------------------------------------------------------------------------
_V12_2_0_PV03_REF_FILE: Path = Path("workflow-system/agent/references/behavioral-guidelines.md")


_V12_2_0_PV03_SELECTOR_FILE: Path = Path("src/devolaflow/task_adaptive_selector.py")


_V12_2_0_PV03_SCHEMA_FILE: Path = Path("schemas/lean-dispatch.yaml")


_V12_2_0_PV03_PROFILES_FILE: Path = Path("workflow-system/agent/context_profiles.yaml")


_V12_2_0_PV03_TEST_FILE: Path = Path("tests/test_behavioral_guidelines.py")


_V12_2_0_PV03_NEW_RULE_IDS: tuple[str, ...] = ("BG-005", "BG-006", "BG-007")


_V12_2_0_PV03_NEW_FIELD_KEYS: tuple[str, ...] = (
    "no_llm_for_deterministic",
    "surface_conflicts",
    "convention_first",
)


_V12_2_0_PV03_REQUIRED_TEST_FN_NAMES: frozenset[str] = frozenset(
    {
        "test_active_no_llm_for_deterministic_emits_bg005",
        "test_active_surface_conflicts_emits_bg006",
        "test_active_convention_first_emits_bg007",
        "test_inactive_v12_2_0_rules_omit_their_bullets",
        "test_select_behavioral_sections_resolves_v12_2_0_keys_from_tier",
        "test_per_key_override_works_for_v12_2_0_keys",
        "test_pre_v12_2_0_profile_without_new_keys_resolves_falsy",
        "test_canonical_yaml_carries_v12_2_0_defaults",
    }
)


def test_v12_2_0_mnimiy_behavioral_extensions(project_root: Path) -> None:
    """W-18 v12.2.0 PV-03 D-2: Mnimiy 3-rule behavioral extension.

    Discharges the W-18 precondition for the v12.2.0 CHANGELOG entry
    that mentions the BG-005..BG-007 additions. Pins:

    * References doc declares all 3 NEW rule sections + field names.
    * `_compose_behavioral_block` renders the 3 NEW rule bullets.
    * Schema declares the 3 NEW sub-fields under `behavioral_guidelines`.
    * Per-tier defaults in `context_profiles.yaml` carry the 3 NEW keys.
    * Companion test class `TestMnimiyBehavioralExtensions` defines all
      8 canonical PV-03 test functions.

    Coupled invariants verified GREEN at v12.2.0 PV-03 close:
    * A-2.3 NEST extension — canonical_order length stays at 17 and
      schema version stays at 6 (no top-level field added).
    * A-2.4 multi-baseline 33/33 PASS unchanged.
    * C-4 SKILL.md line ceiling preserved (PV-03 added 0 SKILL.md lines).
    * C-4 references-tier ceiling: behavioral-guidelines.md stays
      ≤ 1000 lines (Large tier per SF-1).
    * W-21 Soul-set freeze preserved at 10 entries (behavioral primitives
      are NOT Soul rules; they live in the behavioral_guidelines block).
    * W-20 reuse-first preserved at 7 env flags (no new flag — the 3
      new BGs are dispatch-payload fields, not env-gated behaviour).
    * S-10 hook-chain byte-id contract preserved (no lifecycle hook
      changes; this PV is documentation + dispatcher rendering only).

    Source: ``.local/research/v12.2.0_gap_analysis.md`` §2 D-2.
    """
    ref_path = project_root / _V12_2_0_PV03_REF_FILE
    assert ref_path.is_file(), (
        f"W-18 v12.2.0 PV-03 violation: {_V12_2_0_PV03_REF_FILE} missing — release blocker."
    )
    ref_text = ref_path.read_text(encoding="utf-8")
    for rule_id in _V12_2_0_PV03_NEW_RULE_IDS:
        assert rule_id in ref_text, (
            f"W-18 v12.2.0 PV-03 violation: {_V12_2_0_PV03_REF_FILE} missing rule "
            f"section for {rule_id}. The 3 NEW rule sections MUST land before "
            f"the CHANGELOG entry per W-18 sequencing. See gap analysis §2 D-2."
        )
    for field_key in _V12_2_0_PV03_NEW_FIELD_KEYS:
        assert field_key in ref_text, (
            f"W-18 v12.2.0 PV-03 violation: {_V12_2_0_PV03_REF_FILE} missing field "
            f"name {field_key!r}. The reference doc MUST document the dispatch "
            f"sub-key for each NEW rule."
        )

    selector_path = project_root / _V12_2_0_PV03_SELECTOR_FILE
    assert selector_path.is_file(), (
        f"W-18 v12.2.0 PV-03 violation: {_V12_2_0_PV03_SELECTOR_FILE} missing."
    )
    selector_text = selector_path.read_text(encoding="utf-8")
    for rule_id in _V12_2_0_PV03_NEW_RULE_IDS:
        rule_marker = f"{rule_id} "
        assert rule_marker in selector_text, (
            f"W-18 v12.2.0 PV-03 violation: {_V12_2_0_PV03_SELECTOR_FILE} missing "
            f"`{rule_marker}` rendering literal. `_compose_behavioral_block` MUST "
            f"emit the rule id when the corresponding flag is active."
        )

    schema_path = project_root / _V12_2_0_PV03_SCHEMA_FILE
    schema_text = schema_path.read_text(encoding="utf-8")
    for field_key in _V12_2_0_PV03_NEW_FIELD_KEYS:
        assert field_key in schema_text, (
            f"W-18 v12.2.0 PV-03 violation: {_V12_2_0_PV03_SCHEMA_FILE} missing "
            f"field shape declaration for {field_key!r}. The NEST sub-field MUST "
            f"land in `lean_format_spec.behavioral_guidelines.fields`."
        )

    profiles_path = project_root / _V12_2_0_PV03_PROFILES_FILE
    profiles_text = profiles_path.read_text(encoding="utf-8")
    for field_key in _V12_2_0_PV03_NEW_FIELD_KEYS:
        assert field_key in profiles_text, (
            f"W-18 v12.2.0 PV-03 violation: {_V12_2_0_PV03_PROFILES_FILE} missing "
            f"per-tier default for {field_key!r} in `meta.behavioral_guidelines_defaults`."
        )

    test_path = project_root / _V12_2_0_PV03_TEST_FILE
    test_module = ast.parse(test_path.read_text(encoding="utf-8"))

    def _collect_test_fn_names(node: ast.AST) -> set[str]:
        """Recursively collect test function names from module + class bodies."""
        names: set[str] = set()
        for child in ast.walk(node):
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef) and child.name.startswith(
                "test_"
            ):
                names.add(child.name)
        return names

    defined = _collect_test_fn_names(test_module)
    missing = sorted(_V12_2_0_PV03_REQUIRED_TEST_FN_NAMES - defined)
    assert not missing, (
        f"W-18 v12.2.0 PV-03 violation: {_V12_2_0_PV03_TEST_FILE} missing required "
        f"NEW test functions {missing!r}. Required canonical 8-name set per PV-03 "
        f"dispatch: {sorted(_V12_2_0_PV03_REQUIRED_TEST_FN_NAMES)!r}."
    )


# ---------------------------------------------------------------------------
# v12.2.0 PV-04 W-18 ghost-audit refresh — telegraphed runtime enforcement.
# ---------------------------------------------------------------------------
#
# Per W-18 sequencing the ghost-audit refresh MUST land BEFORE the v12.2.0
# CHANGELOG entry mentioning the v12.0.0+v12.1.0 telegraphed runtime
# enforcement. This stanza pins the v12.2.0 PV-04 surface:
#
# * src/devolaflow/lifecycle/reject_subagent_quality_score.py — NEW
#   pre_dispatch extra hook (D-1 runtime closure).
# * src/devolaflow/lifecycle/__init__.py wires the new hook via
#   `register_hook(_PRE_DISPATCH_EVENT, reject_subagent_quality_score)`.
# * src/devolaflow/agent_workspace/dispatch_executor.py adds the optional
#   `timeouts={task_id: seconds}` kwarg to both dispatch_sequential and
#   dispatch_parallel (D-2 runtime closure — `asyncio.wait_for`).
# * src/devolaflow/task_adaptive_selector.py declares
#   TASK_TYPE_TIMEOUT_DEFAULTS + default_timeout_for() per the SKILL.md
#   §"Subagent Hang Prevention" L0 contract.
# * tests/test_async_dispatch_executor_timeout.py defines >= 13 canonical
#   PV-04 timeout test functions.
# * tests/test_lifecycle_reject_subagent_quality_score.py defines >= 8
#   canonical PV-04 hook test functions.
#
# Source: ``.local/research/v12.2.0_gap_analysis.md`` §2 D-4 +
# CHANGELOG.md §[12.0.0] + §[12.1.0] telegraph.
# ---------------------------------------------------------------------------
_V12_2_0_PV04_HOOK_FILE: Path = Path("src/devolaflow/lifecycle/reject_subagent_quality_score.py")


_V12_2_0_PV04_EXECUTOR_FILE: Path = Path("src/devolaflow/agent_workspace/dispatch_executor.py")


_V12_2_0_PV04_SELECTOR_FILE: Path = Path("src/devolaflow/task_adaptive_selector.py")


_V12_2_0_PV04_LIFECYCLE_INIT_FILE: Path = Path("src/devolaflow/lifecycle/__init__.py")


_V12_2_0_PV04_TIMEOUT_TEST_FILE: Path = Path("tests/test_async_dispatch_executor_timeout.py")


_V12_2_0_PV04_HOOK_TEST_FILE: Path = Path("tests/test_lifecycle_reject_subagent_quality_score.py")


_V12_2_0_PV04_TASK_TYPES: tuple[str, ...] = (
    "research",
    "impl",
    "test",
    "review",
    "hotfix",
)


_V12_2_0_PV04_TIMEOUT_MIN_TESTS: int = 13


_V12_2_0_PV04_HOOK_MIN_TESTS: int = 8


def test_v12_2_0_telegraphed_runtime_enforcement(project_root: Path) -> None:
    """W-18 v12.2.0 PV-04 D-4: runtime enforcement of v12.0.0+v12.1.0 telegraph.

    Pins the v12.2.0 PV-04 surface so the CHANGELOG entry mentioning
    runtime enforcement is backed by working code + tests per W-18.

    Coupled invariants verified GREEN at v12.2.0 PV-04 close:
    * S-10 hook-chain byte-id contract preserved — the new hook is
      registered as an extra (NOT a default replacement) so callers
      registering their own extras on `pre_dispatch` see the same
      validate_dispatch + validate_owned_files defaults first.
    * Backward-compat: callers that do NOT pass the `timeouts=` kwarg
      to AsyncDispatchExecutor see v9.3.0 byte-identical behaviour.
    * A-2.4 multi-baseline 33/33 PASS unchanged (no schema NEST).
    * W-20 reuse-first preserved at 7 env flags (no new flag — the
      v12.2.0 PV-04 surfaces are pure library-level + lifecycle wiring;
      no env-gated activation needed).

    Source: ``.local/research/v12.2.0_gap_analysis.md`` §2 D-4.
    """
    # 1. The hook module exists and declares the canonical event name.
    hook_path = project_root / _V12_2_0_PV04_HOOK_FILE
    assert hook_path.is_file(), (
        f"W-18 v12.2.0 PV-04 violation: {_V12_2_0_PV04_HOOK_FILE} missing — release blocker."
    )
    hook_text = hook_path.read_text(encoding="utf-8")
    assert 'EVENT = "pre_dispatch"' in hook_text, (
        f"W-18 v12.2.0 PV-04 violation: {_V12_2_0_PV04_HOOK_FILE} missing the "
        f'canonical `EVENT = "pre_dispatch"` constant.'
    )
    assert "def reject_subagent_quality_score(" in hook_text, (
        f"W-18 v12.2.0 PV-04 violation: {_V12_2_0_PV04_HOOK_FILE} missing the "
        f"canonical `reject_subagent_quality_score` function definition."
    )

    # 2. The lifecycle init wires the hook via register_hook.
    init_path = project_root / _V12_2_0_PV04_LIFECYCLE_INIT_FILE
    init_text = init_path.read_text(encoding="utf-8")
    assert "reject_subagent_quality_score" in init_text, (
        f"W-18 v12.2.0 PV-04 violation: {_V12_2_0_PV04_LIFECYCLE_INIT_FILE} "
        f"missing `reject_subagent_quality_score` import / wiring."
    )
    assert "register_hook(_PRE_DISPATCH_EVENT, reject_subagent_quality_score)" in init_text, (
        f"W-18 v12.2.0 PV-04 violation: {_V12_2_0_PV04_LIFECYCLE_INIT_FILE} "
        f"missing the canonical `register_hook` call for the new hook."
    )

    # 3. The executor accepts the `timeouts` kwarg on both dispatch methods.
    executor_text = (project_root / _V12_2_0_PV04_EXECUTOR_FILE).read_text(encoding="utf-8")
    assert "timeouts: dict[str, float] | None = None" in executor_text, (
        f"W-18 v12.2.0 PV-04 violation: {_V12_2_0_PV04_EXECUTOR_FILE} missing the "
        f"canonical `timeouts: dict[str, float] | None = None` kwarg signature."
    )
    assert "asyncio.wait_for" in executor_text, (
        f"W-18 v12.2.0 PV-04 violation: {_V12_2_0_PV04_EXECUTOR_FILE} missing "
        f"the `asyncio.wait_for` timeout primitive."
    )

    # 4. The selector declares the per-task-type defaults.
    selector_text = (project_root / _V12_2_0_PV04_SELECTOR_FILE).read_text(encoding="utf-8")
    assert "TASK_TYPE_TIMEOUT_DEFAULTS" in selector_text
    assert "def default_timeout_for(" in selector_text
    for task_type in _V12_2_0_PV04_TASK_TYPES:
        assert f'"{task_type}"' in selector_text, (
            f"W-18 v12.2.0 PV-04 violation: {_V12_2_0_PV04_SELECTOR_FILE} missing "
            f"per-task-type default for {task_type!r}. The SKILL.md §'Subagent Hang "
            f"Prevention' L0 contract pins all 5 task types."
        )

    # 5. The two NEW test files exist with the minimum test-function count.
    timeout_test_path = project_root / _V12_2_0_PV04_TIMEOUT_TEST_FILE
    assert timeout_test_path.is_file(), (
        f"W-18 v12.2.0 PV-04 violation: {_V12_2_0_PV04_TIMEOUT_TEST_FILE} missing."
    )
    timeout_module = ast.parse(timeout_test_path.read_text(encoding="utf-8"))
    timeout_test_count = sum(
        1
        for node in timeout_module.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        and node.name.startswith("test_")
    )
    assert timeout_test_count >= _V12_2_0_PV04_TIMEOUT_MIN_TESTS, (
        f"W-18 v12.2.0 PV-04 violation: {_V12_2_0_PV04_TIMEOUT_TEST_FILE} declares "
        f"{timeout_test_count} test functions; PV-04 dispatch requires "
        f">= {_V12_2_0_PV04_TIMEOUT_MIN_TESTS}."
    )

    hook_test_path = project_root / _V12_2_0_PV04_HOOK_TEST_FILE
    assert hook_test_path.is_file(), (
        f"W-18 v12.2.0 PV-04 violation: {_V12_2_0_PV04_HOOK_TEST_FILE} missing."
    )
    hook_module = ast.parse(hook_test_path.read_text(encoding="utf-8"))
    hook_test_count = sum(
        1
        for node in hook_module.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        and node.name.startswith("test_")
    )
    assert hook_test_count >= _V12_2_0_PV04_HOOK_MIN_TESTS, (
        f"W-18 v12.2.0 PV-04 violation: {_V12_2_0_PV04_HOOK_TEST_FILE} declares "
        f"{hook_test_count} test functions; PV-04 dispatch requires "
        f">= {_V12_2_0_PV04_HOOK_MIN_TESTS}."
    )
