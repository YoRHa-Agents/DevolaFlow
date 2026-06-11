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
    Path("tests/test_plugin_refresh_e2e.py"),
    Path("tests/test_plugin_refresh_first_run.py"),
)


# v10.2.0 PV-01 NEW baseline fixtures (W-16 wholesale regen + 10th multi-baseline pin).
_V10_2_0_NEW_BASELINE_FILES: tuple[Path, ...] = (
    Path("benchmarks/devolaflow_context/baselines/v10.2.0_baseline.json"),
    Path("benchmarks/devolaflow_context/baselines/layout_invariant_v10.2.0.yaml"),
)


# v10.2.0 PV-01 D-P-3 new helper + its module path.
_V10_2_0_INSTALL_RESOLVER_PATH: Path = Path("src/devolaflow/si_chip_bridge/install_resolver.py")


_V10_2_0_INSTALL_RESOLVER_NEW_SYMBOL: str = "read_installed_si_chip_version"


# v10.2.0 PV-01 D-P-3 registry edit contract.
_V10_2_0_RUNTIME_PLUGINS_YAML: Path = Path("workflow-system/agent/knowledge/runtime-plugins.yaml")


_V10_2_0_DEAD_HARDCODED_HEURISTIC: str = "echo si-chip/0.4.0"


_V10_2_0_CHANGELOG_LITERAL: str = "## [10.2.0]"


def test_v10_2_0_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v10.2.0: every NEW v10.2.0 PV-01 surface has presence coverage.

    Discharges the W-18 precondition for the v10.2.0 cycle-start MINOR.
    The CHANGELOG entry mentions the 3 new test files, the 2 new
    baseline fixtures, the `read_installed_si_chip_version` helper,
    and the D-P-3 si-chip `version_check_cmd` swap. Each needs a
    presence assertion here BEFORE the CHANGELOG mention is valid —
    per W-18 refresh-before-document sequencing.

    v10.2.0 PV-01 pins:

    1. **3 NEW test files** — every file in `_V10_2_0_NEW_TEST_FILES`
       must exist on disk (D-P-1 / D-P-4 / D-P-6 closures).
    2. **2 NEW baseline fixtures** — `v10.2.0_baseline.json` (W-16
       wholesale regen) + `layout_invariant_v10.2.0.yaml` (10th multi-
       baseline pin).
    3. **`read_installed_si_chip_version` helper** — defined in
       `src/devolaflow/si_chip_bridge/install_resolver.py` (D-P-3).
    4. **si-chip `version_check_cmd` swap** — the pre-v10.2.0
       hardcoded `echo si-chip/0.4.0` heuristic MUST be absent from
       `runtime-plugins.yaml` (replaced with the real frontmatter
       probe per D-P-3 closure).
    5. **CHANGELOG entry** — `## [10.2.0]` header is present.
    """
    import ast

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
            f"missing. v10.2.0 PV-01 ships this baseline (W-16 wholesale "
            f"regen + 10th multi-baseline pin); regenerate via "
            f"`python -m benchmarks.devolaflow_context.generate_baseline "
            f"--output <path>` (for the JSON) OR copy "
            f"`layout_invariant_v9.7.0.yaml` (for the YAML witness)."
        )

    resolver_path = project_root / _V10_2_0_INSTALL_RESOLVER_PATH
    assert resolver_path.is_file(), (
        f"W-18 v10.2.0 violation: {_V10_2_0_INSTALL_RESOLVER_PATH} missing."
    )
    resolver_source = resolver_path.read_text(encoding="utf-8")
    resolver_module = ast.parse(resolver_source)
    defined_names = {
        node.name
        for node in ast.walk(resolver_module)
        if isinstance(node, ast.FunctionDef | ast.ClassDef)
    }
    assert _V10_2_0_INSTALL_RESOLVER_NEW_SYMBOL in defined_names, (
        f"W-18 v10.2.0 violation: install_resolver module missing "
        f"{_V10_2_0_INSTALL_RESOLVER_NEW_SYMBOL!r}; v10.2.0 PV-01 D-P-3 "
        f"ships this helper. Either restore it OR remove the CHANGELOG "
        f"mention of D-P-3."
    )

    runtime_yaml_path = project_root / _V10_2_0_RUNTIME_PLUGINS_YAML
    assert runtime_yaml_path.is_file(), (
        f"W-18 v10.2.0 violation: {_V10_2_0_RUNTIME_PLUGINS_YAML} missing."
    )
    runtime_yaml_text = runtime_yaml_path.read_text(encoding="utf-8")
    si_chip_block_start = runtime_yaml_text.find("- id: si-chip")
    assert si_chip_block_start != -1, (
        "W-18 v10.2.0 violation: si-chip block missing from runtime-plugins.yaml."
    )
    si_chip_block_end = runtime_yaml_text.find(
        "\n  - id:",
        si_chip_block_start + 1,
    )
    if si_chip_block_end == -1:
        si_chip_block_end = runtime_yaml_text.find("\ndefaults:", si_chip_block_start)
    si_chip_block = runtime_yaml_text[si_chip_block_start:si_chip_block_end]
    assert _V10_2_0_DEAD_HARDCODED_HEURISTIC not in si_chip_block, (
        f"W-18 v10.2.0 violation: si-chip block still contains the pre-"
        f"v10.2.0 hardcoded heuristic {_V10_2_0_DEAD_HARDCODED_HEURISTIC!r}. "
        f"D-P-3 replaces it with a real read_installed_si_chip_version "
        f"probe; restore the probe OR remove the CHANGELOG mention of "
        f"D-P-3."
    )
    assert _V10_2_0_INSTALL_RESOLVER_NEW_SYMBOL in si_chip_block, (
        f"W-18 v10.2.0 violation: si-chip version_check_cmd should call "
        f"{_V10_2_0_INSTALL_RESOLVER_NEW_SYMBOL!r}; current block does not "
        f"reference the helper. The v10.2.0 PV-01 D-P-3 closure requires "
        f"the probe to call into the bridge module."
    )

    changelog_path = project_root / "CHANGELOG.md"
    changelog_text = changelog_path.read_text(encoding="utf-8")
    assert _V10_2_0_CHANGELOG_LITERAL in changelog_text, (
        f"W-18 v10.2.0 violation: CHANGELOG entry "
        f"{_V10_2_0_CHANGELOG_LITERAL!r} missing; PV-01 ships this entry."
    )


# ---------------------------------------------------------------------------
# W-18 v10.2.1 ghost-audit refresh — PV-02 PATCH (formal Si-Chip integration).
# ---------------------------------------------------------------------------

# v10.2.1 PV-02 NEW test files (D-S-2 / D-S-3 / D-S-5 closures).
_V10_2_1_NEW_TEST_FILES: tuple[Path, ...] = (
    Path("tests/test_dispatch_dogfood_cycle.py"),
    Path("tests/test_sichip_iteration_delta_gate.py"),
    Path("tests/test_sichip_dedup_feedback_doc.py"),
)


# v10.2.1 PV-02 D-S-2 new public symbol on devolaflow.feedback.
# v14.5.0 (ADR-006 G-025) ghost-pin update: the symbol's DEFINITION moved
# to the new owner module src/devolaflow/dispatch.py; the historical
# devolaflow.feedback import path keeps working via a permanent
# identity-preserving re-export shim (pinned by
# tests/test_module_split_shims.py). The AST def pin below follows the
# re-export truth's owner module.
_V10_2_1_FEEDBACK_NEW_SYMBOL: str = "dispatch_dogfood_cycle"


_V10_2_1_FEEDBACK_NEW_SYMBOL_OWNER: Path = Path("src/devolaflow/dispatch.py")


# v10.2.1 PV-02 D-P-2 introspection constant on the lifecycle hook.
_V10_2_1_PRE_PLUGIN_INVOCATION_CONST: str = "EVENT_TRIGGERS_DAILY_UPGRADE"


# v10.2.1 PV-02 D-S-6 — the obsolete v9.5.0 literal MUST be gone from runner.py.
_V10_2_1_DEAD_WORK_DIR_LITERAL: str = '"v9.5.0"'


# v10.2.1 PV-02 D-S-3 — Makefile reference proving the iteration_delta gate
# is wired as the 7th SI-10 step.
_V10_2_1_MAKEFILE_GATE_REFERENCE: str = "test_sichip_iteration_delta_gate"


# v10.2.1 PV-02 dogfood pass #1 deliverable path (gitignored content; the
# path-presence assertion is the operator-visible contract).
_V10_2_1_DOGFOOD_PASS1_DOC: Path = Path(".local/research/v10.2.1_dogfood_pass1.md")


_V10_2_1_CHANGELOG_LITERAL: str = "## [10.2.1]"


def test_v10_2_1_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v10.2.1: every NEW v10.2.1 PV-02 surface has presence coverage.

    Discharges the W-18 precondition for the v10.2.1 PV-02 PATCH.
    The CHANGELOG entry mentions the 3 new test files, the
    `dispatch_dogfood_cycle` wrapper, the `EVENT_TRIGGERS_DAILY_UPGRADE`
    introspection constant, the Makefile `release-preflight` 7th-step
    wire, the absence of the obsolete v9.5.0 work_dir literal in
    runner.py, and the dogfood pass #1 research artifact. Each needs a
    presence assertion here BEFORE the CHANGELOG mention is valid — per
    W-18 refresh-before-document sequencing.

    v10.2.1 PV-02 pins:

    1. **3 NEW test files** — every file in `_V10_2_1_NEW_TEST_FILES`
       must exist on disk (D-S-2 / D-S-3 / D-S-5 closures).
    2. **`dispatch_dogfood_cycle` symbol** — defined in
       `src/devolaflow/feedback.py` (D-S-2 closure).
    3. **`EVENT_TRIGGERS_DAILY_UPGRADE` constant** — defined in
       `src/devolaflow/lifecycle/pre_plugin_invocation.py` (D-P-2
       closure introspection contract).
    4. **Makefile references the gate test** — the
       `release-preflight` chain calls
       `test_sichip_iteration_delta_gate` as the 7th SI-10 step
       (D-S-3 / D-V-1 closure).
    5. **No `"v9.5.0"` literal in `runner.py`** — D-S-6 swap is
       complete; the obsolete hardcoded work_dir literal is gone.
    6. **Dogfood pass #1 artifact** — file path presence at
       `.local/research/v10.2.1_dogfood_pass1.md` (gitignored content;
       path-presence is the operator-visible contract).
    7. **CHANGELOG entry** — `## [10.2.1]` header is present.
    """
    import ast

    for test_rel in _V10_2_1_NEW_TEST_FILES:
        test_path = project_root / test_rel
        assert test_path.is_file(), (
            f"W-18 v10.2.1 violation: NEW test file {test_rel} missing. "
            f"v10.2.1 PV-02 ships this file per the cycle plan §3 PV-02; "
            f"restore it or remove the CHANGELOG mention of the "
            f"corresponding gap closure."
        )

    # v14.5.0 (ADR-006 G-025): definition moved feedback.py → dispatch.py;
    # the old import path is shimmed (see _V10_2_1_FEEDBACK_NEW_SYMBOL note).
    feedback_path = project_root / _V10_2_1_FEEDBACK_NEW_SYMBOL_OWNER
    assert feedback_path.is_file(), (
        f"W-18 v10.2.1 violation: {_V10_2_1_FEEDBACK_NEW_SYMBOL_OWNER} missing."
    )
    feedback_source = feedback_path.read_text(encoding="utf-8")
    feedback_module = ast.parse(feedback_source)
    feedback_defined = {
        node.name
        for node in ast.walk(feedback_module)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
    }
    assert _V10_2_1_FEEDBACK_NEW_SYMBOL in feedback_defined, (
        f"W-18 v10.2.1 violation: {_V10_2_1_FEEDBACK_NEW_SYMBOL_OWNER} missing "
        f"{_V10_2_1_FEEDBACK_NEW_SYMBOL!r}; v10.2.1 PV-02 D-S-2 ships "
        f"this wrapper. Either restore it OR remove the CHANGELOG "
        f"mention of D-S-2."
    )
    from devolaflow import dispatch as _dispatch_module
    from devolaflow import feedback as _feedback_module

    assert _feedback_module.dispatch_dogfood_cycle is _dispatch_module.dispatch_dogfood_cycle, (
        "W-18 v10.2.1 violation: the devolaflow.feedback re-export shim for "
        "dispatch_dogfood_cycle must stay identity-preserving (ADR-006)."
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

    runner_path = project_root / "src/devolaflow/si_chip_bridge/runner.py"
    assert runner_path.is_file(), "W-18 v10.2.1 violation: si_chip_bridge/runner.py missing."
    runner_source = runner_path.read_text(encoding="utf-8")
    # The literal MUST NOT appear inside the work_dir default expression
    # of `run_dogfood_cycle`. We scan the function body for it.
    runner_module = ast.parse(runner_source)
    run_dogfood_cycle_node: ast.FunctionDef | None = None
    for node in ast.walk(runner_module):
        if isinstance(node, ast.FunctionDef) and node.name == "run_dogfood_cycle":
            run_dogfood_cycle_node = node
            break
    assert run_dogfood_cycle_node is not None, (
        "W-18 v10.2.1 violation: run_dogfood_cycle function missing from si_chip_bridge/runner.py."
    )
    func_source = ast.get_source_segment(runner_source, run_dogfood_cycle_node) or ""
    assert _V10_2_1_DEAD_WORK_DIR_LITERAL not in func_source, (
        f"W-18 v10.2.1 violation: run_dogfood_cycle still contains the "
        f"obsolete work_dir literal {_V10_2_1_DEAD_WORK_DIR_LITERAL!r}. "
        f"v10.2.1 PV-02 D-S-6 closure swaps it for `__version__`-tracking "
        f"behaviour; restore the swap OR remove the CHANGELOG mention of "
        f"D-S-6."
    )

    makefile_path = project_root / "Makefile"
    assert makefile_path.is_file(), "W-18 v10.2.1 violation: Makefile missing."
    makefile_text = makefile_path.read_text(encoding="utf-8")
    assert _V10_2_1_MAKEFILE_GATE_REFERENCE in makefile_text, (
        f"W-18 v10.2.1 violation: Makefile does NOT reference "
        f"{_V10_2_1_MAKEFILE_GATE_REFERENCE!r}; the v10.2.1 PV-02 "
        f"release-preflight target is the 7th SI-10 step wire and must "
        f"be present per D-V-1."
    )
    assert "release-preflight:" in makefile_text, (
        "W-18 v10.2.1 violation: Makefile missing release-preflight target."
    )

    _w18_research_artifact_path(project_root, _V10_2_1_DOGFOOD_PASS1_DOC)

    changelog_path = project_root / "CHANGELOG.md"
    changelog_text = changelog_path.read_text(encoding="utf-8")
    assert _V10_2_1_CHANGELOG_LITERAL in changelog_text, (
        f"W-18 v10.2.1 violation: CHANGELOG entry "
        f"{_V10_2_1_CHANGELOG_LITERAL!r} missing; PV-02 ships this entry."
    )


# ---------------------------------------------------------------------------
# W-18 v10.2.2 ghost-audit refresh — PV-03 PATCH (NineS deep-analysis +
# Si-Chip eval adapter prototype).
# ---------------------------------------------------------------------------

# v10.2.2 PV-03 NEW script (D-N-1 closure: NineS-to-Si-Chip eval adapter).
_V10_2_2_ADAPTER_SCRIPT: Path = Path("scripts/nines_to_sichip_eval_adapter.py")


# v10.2.2 PV-03 NEW unit-test file pinning the adapter contract.
_V10_2_2_ADAPTER_TEST: Path = Path("tests/test_nines_to_sichip_adapter.py")


# v10.2.2 PV-03 D-N-1 — public symbols that MUST be defined in the adapter
# (the 4 functions plus the CLI entry point form the operator-visible contract).
_V10_2_2_ADAPTER_REQUIRED_SYMBOLS: tuple[str, ...] = (
    "load_nines_json",
    "validate_nines_shape",
    "build_runs",
    "build_baselines",
    "write_runs_dir",
    "write_baseline_dir",
    "main",
)


# v10.2.2 PV-03 D-N-3 — three NineS deep-analysis JSON outputs (gitignored
# content; path-presence is the operator-visible contract).
_V10_2_2_NINES_JSON_PATHS: tuple[Path, ...] = (
    Path(".local/research/v10.2.2_nines.json"),
    Path(".local/research/v10.2.2_nines_plugins.json"),
    Path(".local/research/v10.2.2_nines_lifecycle.json"),
)


# v10.2.2 PV-03 D-N-3 NineS synthesis (gitignored content; path-presence
# contract).
_V10_2_2_NINES_SYNTHESIS_DOC: Path = Path(".local/research/v10.2.2_nines.md")


# v10.2.2 PV-03 dogfood pass #2 deliverable (gitignored content;
# path-presence contract).
_V10_2_2_DOGFOOD_PASS2_DOC: Path = Path(".local/research/v10.2.2_dogfood_pass2.md")


_V10_2_2_CHANGELOG_LITERAL: str = "## [10.2.2]"


def test_v10_2_2_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v10.2.2: every NEW v10.2.2 PV-03 surface has presence coverage.

    Discharges the W-18 precondition for the v10.2.2 PV-03 PATCH.
    The CHANGELOG entry mentions the NineS-to-Si-Chip eval adapter
    script + 7 public functions, the unit-test file, the 3 NineS
    deep-analysis JSONs, the synthesis document, and the dogfood pass
    #2 capture. Each needs a presence assertion here BEFORE the
    CHANGELOG mention is valid — per W-18 refresh-before-document
    sequencing.

    v10.2.2 PV-03 pins:

    1. **Adapter script** — `scripts/nines_to_sichip_eval_adapter.py`
       exists and defines all 7 public symbols (`load_nines_json`,
       `validate_nines_shape`, `build_runs`, `build_baselines`,
       `write_runs_dir`, `write_baseline_dir`, `main`).
    2. **Adapter unit-test file** —
       `tests/test_nines_to_sichip_adapter.py` exists.
    3. **3 NineS deep-analysis JSONs** — every path in
       `_V10_2_2_NINES_JSON_PATHS` exists (D-N-3 closure;
       `nines analyze --target-path src/devolaflow/{si_chip_bridge,plugins,lifecycle}`).
    4. **NineS synthesis** — `.local/research/v10.2.2_nines.md` exists
       (D-N-3 closure; per-package finding + agent-impact synthesis).
    5. **Dogfood pass #2** — `.local/research/v10.2.2_dogfood_pass2.md`
       exists (D-N-1 + D-S-1 closure; adapter outcome + per-file
       iteration_delta capture).
    6. **CHANGELOG entry** — `## [10.2.2]` header is present.
    """
    import ast

    adapter_path = project_root / _V10_2_2_ADAPTER_SCRIPT
    assert adapter_path.is_file(), (
        f"W-18 v10.2.2 violation: NEW adapter script {_V10_2_2_ADAPTER_SCRIPT} "
        f"missing. v10.2.2 PV-03 D-N-1 ships this script per the cycle plan "
        f"§3 PV-03; restore it or remove the CHANGELOG mention of D-N-1."
    )
    adapter_source = adapter_path.read_text(encoding="utf-8")
    adapter_module = ast.parse(adapter_source)
    adapter_defined = {
        node.name
        for node in ast.walk(adapter_module)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
    }
    for sym in _V10_2_2_ADAPTER_REQUIRED_SYMBOLS:
        assert sym in adapter_defined, (
            f"W-18 v10.2.2 violation: adapter script missing required public "
            f"symbol {sym!r}; v10.2.2 PV-03 D-N-1 contract requires this "
            f"symbol. Either restore it OR remove the CHANGELOG mention of "
            f"D-N-1."
        )

    test_path = project_root / _V10_2_2_ADAPTER_TEST
    assert test_path.is_file(), (
        f"W-18 v10.2.2 violation: NEW adapter test file "
        f"{_V10_2_2_ADAPTER_TEST} missing. v10.2.2 PV-03 D-N-1 ships ≥6 "
        f"unit tests per the cycle plan AC #2; restore it or remove the "
        f"CHANGELOG mention."
    )

    for json_path in _V10_2_2_NINES_JSON_PATHS:
        _w18_research_artifact_path(project_root, json_path)

    _w18_research_artifact_path(project_root, _V10_2_2_NINES_SYNTHESIS_DOC)

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


# v10.2.3 PV-04 Track A — bridge defect fix surface.
_V10_2_3_BRIDGE_MODELS_FILE: Path = Path("src/devolaflow/si_chip_bridge/models.py")


# Strings that MUST appear in models.py to prove the MVP-8 nested-key
# support shipped (NOT a paraphrase — the literal Si-Chip MVP-8 path
# fragments per .local/dogfood/10.2.1/skill-optimization_after_metrics.yaml).
_V10_2_3_BRIDGE_MVP8_LITERALS: tuple[str, ...] = (
    "T1_pass_rate",
    "T3_baseline_delta",
    "C1_metadata_tokens",
    "C2_body_tokens",
    "baseline_delta",
)


# v10.2.3 PV-04 Track B-1 — pre_plugin_invocation helpers.
_V10_2_3_PPI_FILE: Path = Path("src/devolaflow/lifecycle/pre_plugin_invocation.py")


_V10_2_3_PPI_HELPERS: tuple[str, ...] = (
    "_resolve_upgrade_threshold_hours",
    "_run_install_then_upgrade_for_plugin",
)


# v10.2.3 PV-04 Track B-2 — post_skill_edit helpers.
_V10_2_3_PSE_FILE: Path = Path("src/devolaflow/lifecycle/post_skill_edit.py")


_V10_2_3_PSE_HELPERS: tuple[str, ...] = (
    "_compute_fingerprint",
    "_load_existing_fingerprints",
    "_run_si_chip_evaluation",
)


_V10_2_3_CHANGELOG_LITERAL: str = "## [10.2.3]"


def test_v10_2_3_new_symbols_have_coverage(project_root: Path) -> None:
    """W-18 v10.2.3: every NEW v10.2.3 PV-04 surface has presence coverage.

    Discharges the W-18 precondition for the v10.2.3 PV-04 PATCH
    (self-iteration round 1). The CHANGELOG entry mentions the bridge
    defect fix in `MetricsReport.from_yaml_dict` (Track A), the two
    Track B CC reductions in `pre_plugin_invocation` and `post_skill_edit`
    via extracted helpers, and the two research deliverables (dogfood
    pass #3 + iteration round 1 report). Each needs a presence
    assertion here BEFORE the CHANGELOG mention is valid — per W-18
    refresh-before-document sequencing.

    v10.2.3 PV-04 pins:

    1. **Bridge defect fix (Track A)** —
       `src/devolaflow/si_chip_bridge/models.py` carries MVP-8 nested
       path literals (T1_pass_rate, T3_baseline_delta,
       C1_metadata_tokens, C2_body_tokens, baseline_delta). Without
       these the v10.2.2 PV-03 dogfood pass #2 bridge defect is not
       fixed.
    2. **CC reduction Track B-1** —
       `src/devolaflow/lifecycle/pre_plugin_invocation.py` defines
       `_resolve_upgrade_threshold_hours` and
       `_run_install_then_upgrade_for_plugin`.
    3. **CC reduction Track B-2** —
       `src/devolaflow/lifecycle/post_skill_edit.py` defines
       `_compute_fingerprint`, `_load_existing_fingerprints`, and
       `_run_si_chip_evaluation`.
    4. **Dogfood pass #3 deliverable** —
       `.local/research/v10.2.3_dogfood_pass3.md` exists.
    5. **Self-iteration round 1 report** —
       `.local/research/v10.2.3_iteration_round1.md` exists.
    6. **CHANGELOG entry** — `## [10.2.3]` header is present.
    """
    import ast

    bridge_path = project_root / _V10_2_3_BRIDGE_MODELS_FILE
    assert bridge_path.is_file(), (
        f"W-18 v10.2.3 violation: bridge file {_V10_2_3_BRIDGE_MODELS_FILE} "
        f"missing. v10.2.3 PV-04 Track A patches `MetricsReport.from_yaml_dict` "
        f"in this file; restore it or remove the CHANGELOG mention."
    )
    bridge_source = bridge_path.read_text(encoding="utf-8")
    for literal in _V10_2_3_BRIDGE_MVP8_LITERALS:
        assert literal in bridge_source, (
            f"W-18 v10.2.3 violation: bridge models.py missing MVP-8 literal "
            f"{literal!r}; v10.2.3 PV-04 Track A REQUIRES this nested-key "
            f"path to read Si-Chip aggregate_eval.py v0.1.6 emit shape. "
            f"Either restore the literal OR remove the CHANGELOG mention "
            f"of the bridge defect fix."
        )

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

    pse_path = project_root / _V10_2_3_PSE_FILE
    assert pse_path.is_file(), (
        f"W-18 v10.2.3 violation: post_skill_edit file {_V10_2_3_PSE_FILE} "
        f"missing. v10.2.3 PV-04 Track B-2 extracts helpers in this file; "
        f"restore it or remove the CHANGELOG mention."
    )
    pse_source = pse_path.read_text(encoding="utf-8")
    pse_module = ast.parse(pse_source)
    pse_defined = {
        node.name
        for node in ast.walk(pse_module)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    for helper in _V10_2_3_PSE_HELPERS:
        assert helper in pse_defined, (
            f"W-18 v10.2.3 violation: post_skill_edit.py missing helper "
            f"{helper!r}; v10.2.3 PV-04 Track B-2 ships this helper as "
            f"part of the CC=13 → ≤7 reduction. Either restore the helper "
            f"OR remove the CHANGELOG mention of Track B-2."
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
# `read_last_checked` per NineS PV-03 finding CC-a5d310-0003).
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
    import ast

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
            f"per NineS PV-03 finding CC-a5d310-0003. Either restore "
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
