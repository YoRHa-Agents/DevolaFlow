"""Ghost audit — per-cycle W-18 feature stanzas for the v12.5 cycle.

Split from ``tests/test_no_ghost_features.py`` per v15-ADR-001
(v14.3.0). New W-18 stanzas for a v12.5.x release append HERE; the
next MINOR cycle rotates to a fresh ``test_features_v<MAJ>_<MIN>.py``.
"""

from __future__ import annotations

from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# W-18 stanza for v12.5.0 PV-02 D-2 — cc-spike sweep carry-over
# ---------------------------------------------------------------------------
#
# Per W-18 sequencing the ghost-audit refresh MUST land BEFORE the v12.5.0
# CHANGELOG entry mentioning the PV-02 cc-spike sweep. This stanza pins the
# v12.5.0 PV-02 surface (closes the v12.4.0 retro §6 telegraph item 1):
#
# * 4 helpers extracted from ``load_command_mappings`` (was cc=18 per
#   ``.local/research/v12.4.0_nines_deep_commands.json`` warning-tier
#   finding) into ``_resolve_commands_root`` + ``_load_recipe_payload`` +
#   ``_filter_recipe_freshness`` + ``_should_keep_recipe``.
# * 2 helpers extracted from ``apply_local_recipe`` (was cc=17 per the
#   same NineS finding) into ``_resolve_apply_inputs`` (folding the 5
#   early-return decisions) + ``_apply_recipe_transform`` (folding the
#   strip-ansi → pre/post filter → truncate → on-empty pipeline).
# * Both public signatures byte-identical to the pre-refactor forms.
# * Companion cc-pin file ``tests/test_v12_5_0_complexity_targets.py``
#   exists with the 7 cc-pin tests (orchestrator ≤ cc=10 per target,
#   per-helper ≤ cc=8 parametrize, signature byte-identical literal
#   match for both targets, all-helpers-present sentinel).
#
# Source: ``.local/research/v12.5.0_gap_analysis.md`` §2 D-2 +
# ``.local/research/v12.4.0_retrospective.md`` §6 telegraph item 1 +
# ``tests/test_v12_5_0_complexity_targets.py`` (the companion cc-pin
# file). The W-18 sequencing rule is at
# ``.cursor/rules/repo-governance.mdc`` §W-18.
# ---------------------------------------------------------------------------
_V12_5_0_COMMANDS_FILE: Path = Path("src/devolaflow/shell_proxy/commands.py")


_V12_5_0_LOAD_MAPPINGS_HELPERS: tuple[str, ...] = (
    "_resolve_commands_root",
    "_load_recipe_payload",
    "_filter_recipe_freshness",
    "_should_keep_recipe",
)


_V12_5_0_APPLY_RECIPE_HELPERS: tuple[str, ...] = (
    "_resolve_apply_inputs",
    "_apply_recipe_transform",
)


_V12_5_0_LOAD_MAPPINGS_SIGNATURE_LITERAL: str = (
    "def load_command_mappings(\n"
    "    *,\n"
    "    commands_dir: Path | str | None = None,\n"
    "    repo_signal: str | None = None,\n"
    "    env: dict[str, str] | None = None,\n"
    "    current_version: str | None = None,\n"
    ") -> dict[str, CommandMapping]:"
)


_V12_5_0_APPLY_RECIPE_SIGNATURE_LITERAL: str = (
    "def apply_local_recipe(\n"
    "    cmd: str,\n"
    "    output: str,\n"
    "    *,\n"
    "    mappings: dict[str, CommandMapping] | None = None,\n"
    "    env: dict[str, str] | None = None,\n"
    "    commands_dir: Path | str | None = None,\n"
    "    repo_signal: str | None = None,\n"
    ") -> tuple[str, bool]:"
)


def test_v12_5_0_cc_spike_sweep_complete(project_root: Path) -> None:
    """W-18 v12.5.0 PV-02 D-2: ``load_command_mappings`` + ``apply_local_recipe`` cc-spike sweep.

    Discharges the W-18 precondition for the v12.5.0 CHANGELOG entry
    mentioning the PV-02 cc-spike sweep. The stanza asserts three
    load-bearing surfaces (mirroring the v12.4.0 PV-04 stanza pattern):

    (a) Every helper symbol is present at module scope in
    ``src/devolaflow/shell_proxy/commands.py`` — 4 ``_resolve_*`` /
    ``_load_*`` / ``_filter_*`` / ``_should_*`` helpers for
    ``load_command_mappings`` AND 2 helpers for ``apply_local_recipe``
    (``_resolve_apply_inputs`` + ``_apply_recipe_transform``). Without
    these 6 symbols the cc reduction did NOT happen and the CHANGELOG
    entry would be a ghost feature per S-4.

    (b) Both public signatures are byte-identical to the pre-refactor
    forms. The CO-2 / C-3 no-API-break invariant pins:
      * ``def load_command_mappings(*, commands_dir, repo_signal, env,
        current_version) -> dict[str, CommandMapping]:`` (consumed by
        ``apply_local_recipe`` + the proxy + the compression-pipeline
        stage + every ``tests/test_shell_proxy_*`` fixture)
      * ``def apply_local_recipe(cmd, output, *, mappings, env,
        commands_dir, repo_signal) -> tuple[str, bool]:`` (the public
        API consumed by the proxy + the compression-pipeline stage)
    Any reorder / rename / default-change is a release blocker.

    (c) The companion test file
    ``tests/test_v12_5_0_complexity_targets.py`` exists with the cc-pin
    tests (orchestrator ≤ cc=10 per target, per-helper ≤ cc=8
    parametrize, signature byte-identical literal match for both
    targets, all-helpers-present sentinel).

    Source: ``.local/research/v12.5.0_gap_analysis.md`` §2 D-2 +
    ``.local/research/v12.4.0_nines_deep_commands.json`` (NineS deep
    finding for ``load_command_mappings`` cc=16 + ``apply_local_recipe``
    cc=16 — both warning-tier deferred from v12.4.0 to v12.5.0); the
    W-18 sequencing rule is at
    ``.cursor/rules/repo-governance.mdc`` §W-18.
    """
    # --- (a.1) load_command_mappings helpers in commands.py ------------
    commands_path = project_root / _V12_5_0_COMMANDS_FILE
    assert commands_path.is_file(), (
        f"W-18 v12.5.0 PV-02 violation: {_V12_5_0_COMMANDS_FILE} missing — "
        "release blocker. The refactor MUST land in the canonical commands "
        "module per the PV-02 owned-files manifest item 1."
    )
    commands_text = commands_path.read_text(encoding="utf-8")
    for helper_name in _V12_5_0_LOAD_MAPPINGS_HELPERS:
        signature_literal = f"def {helper_name}("
        assert signature_literal in commands_text, (
            f"W-18 v12.5.0 PV-02 violation: {_V12_5_0_COMMANDS_FILE} missing "
            f"helper function ``{helper_name}``. The 4-helper decomposition "
            "is what brings ``load_command_mappings`` cc from 18 to 9; if "
            "this assertion fires, the refactor was either reverted or never "
            "applied. Expected helper signatures are documented at "
            "``.local/research/v12.5.0_gap_analysis.md`` §2 D-2."
        )

    # --- (a.2) apply_local_recipe helpers in commands.py --------------
    for helper_name in _V12_5_0_APPLY_RECIPE_HELPERS:
        signature_literal = f"def {helper_name}("
        assert signature_literal in commands_text, (
            f"W-18 v12.5.0 PV-02 violation: {_V12_5_0_COMMANDS_FILE} missing "
            f"helper function ``{helper_name}``. The 2-helper decomposition "
            "is what brings ``apply_local_recipe`` cc from 17 to 4; if this "
            "assertion fires, the refactor was either reverted or never "
            "applied."
        )

    # --- (b.1) load_command_mappings signature byte-identical ---------
    assert _V12_5_0_LOAD_MAPPINGS_SIGNATURE_LITERAL in commands_text, (
        f"W-18 v12.5.0 PV-02 violation: {_V12_5_0_COMMANDS_FILE} has drifted "
        "the public ``load_command_mappings`` signature. The CO-2 / C-3 "
        "no-API-break invariant requires byte-identical preservation. "
        f"Expected literal:\n\n{_V12_5_0_LOAD_MAPPINGS_SIGNATURE_LITERAL}\n\n"
        "If a future PV needs to ADD a parameter, append it after "
        "``current_version`` with a default value (additive change)."
    )

    # --- (b.2) apply_local_recipe signature byte-identical ------------
    assert _V12_5_0_APPLY_RECIPE_SIGNATURE_LITERAL in commands_text, (
        f"W-18 v12.5.0 PV-02 violation: {_V12_5_0_COMMANDS_FILE} has drifted "
        "the public ``apply_local_recipe`` signature. Per CO-2 / C-3 the "
        "API surface MUST stay byte-identical so the proxy + the "
        "compression-pipeline stage + every fixture test keeps working. "
        f"Expected literal:\n\n{_V12_5_0_APPLY_RECIPE_SIGNATURE_LITERAL}"
    )

    # --- (c) companion cc-pin test file -------------------------------
    pv02_complexity_test_path = project_root / Path("tests/test_v12_5_0_complexity_targets.py")
    assert pv02_complexity_test_path.is_file(), (
        "W-18 v12.5.0 PV-02 violation: tests/test_v12_5_0_complexity_targets.py "
        "missing — release blocker. The companion cc-pin test file guards "
        "against future re-bloat of ``load_command_mappings`` AND "
        "``apply_local_recipe`` per the PV-02 owned-files manifest item 4."
    )
    pv02_complexity_test_text = pv02_complexity_test_path.read_text(encoding="utf-8")
    for expected_test in (
        "test_load_command_mappings_cc_under_ceiling",
        "test_load_command_mappings_helpers_cc_under_ceiling",
        "test_load_command_mappings_signature_byte_identical",
        "test_apply_local_recipe_cc_under_ceiling",
        "test_apply_local_recipe_helpers_cc_under_ceiling",
        "test_apply_local_recipe_signature_byte_identical",
        "test_v12_5_0_pv02_helpers_all_present",
    ):
        assert f"def {expected_test}" in pv02_complexity_test_text, (
            f"W-18 v12.5.0 PV-02 violation: "
            f"tests/test_v12_5_0_complexity_targets.py missing test function "
            f"``{expected_test}``. The 7-function contract (3 for "
            "load_command_mappings + 3 for apply_local_recipe + 1 sentinel) "
            "is documented in the PV-02 owned-files manifest item 4."
        )


# ---------------------------------------------------------------------------
# W-18 stanza for v12.5.0 PV-03 D-1.1 — codegraph plugin landing
# ---------------------------------------------------------------------------
#
# Per W-18 sequencing the ghost-audit refresh MUST land BEFORE the v12.5.0
# CHANGELOG entry mentioning the codegraph plugin. This stanza pins the
# v12.5.0 PV-03 D-1.1 surface (closes the v12.4.0 retro §3 BLOCKER feedback
# item: "codegraph integration is the primary deliverable for v12.5.0"):
#
# * workflow-system/agent/plugins.yaml carries the `codegraph:` block
#   under `plugins:` with the 8 capabilities + `code_intelligence` role +
#   the 4 stage_mapping recipes (analyze/scaffold/research/impact).
# * workflow-system/agent/plugins.yaml `plugin_roles:` carries the NEW
#   `code_intelligence:` block (5th role) with provider=codegraph.
# * workflow-system/agent/knowledge/runtime-plugins.yaml `plugins:` list
#   carries the `id: codegraph` entry with backend=npm_then_init.
# * workflow-system/agent/knowledge/reference-dependencies.yaml
#   `active_tracking:` list (12th entry) carries the codegraph reference
#   pin for the W-2 / SI-2 reference review cycle.
# * src/devolaflow/codegraph/ package exists with __init__.py + _cli.py
#   (run_codegraph_cli + CodegraphUnavailableError) + researcher.py (5
#   public helpers: build_context, search_symbols, get_impact,
#   get_callers, get_affected_tests).
# * Companion test files tests/test_codegraph.py + the 6 new
#   TestV1250CodegraphRegistration tests in tests/test_plugins.py + the
#   codegraph entry in tests/test_runtime_plugins_smoke.py exist.
#
# Source: .local/research/v12.5.0_gap_analysis.md §2 D-1 +
# .local/research/v12.5.0_codegraph_benefit_analysis.md §3 (5-surface
# architecture) + §6.1 PV-03 acceptance criteria. The W-18 sequencing
# rule is at .cursor/rules/repo-governance.mdc §W-18.
# ---------------------------------------------------------------------------
_V12_5_0_PV03_PLUGINS_FILE: Path = Path("workflow-system/agent/plugins.yaml")


_V12_5_0_PV03_RUNTIME_FILE: Path = Path("workflow-system/agent/knowledge/runtime-plugins.yaml")


_V12_5_0_PV03_REFERENCES_FILE: Path = Path(
    "workflow-system/agent/knowledge/reference-dependencies.yaml"
)


_V12_5_0_PV03_PACKAGE_DIR: Path = Path("src/devolaflow/codegraph")


_V12_5_0_PV03_PACKAGE_FILES: tuple[str, ...] = (
    "__init__.py",
    "_cli.py",
    "researcher.py",
)


_V12_5_0_PV03_RESEARCHER_PUBLIC_HELPERS: tuple[str, ...] = (
    "build_context",
    "search_symbols",
    "get_impact",
    "get_callers",
    "get_affected_tests",
)


def test_v12_5_0_codegraph_plugin_registered(project_root: Path) -> None:
    """W-18 v12.5.0 PV-03 D-1.1: codegraph plugin landed across 3 registries + Python wrapper.

    Discharges the W-18 precondition for the v12.5.0 CHANGELOG entry
    mentioning the codegraph plugin. The stanza asserts five
    load-bearing surfaces:

    (a) plugins.yaml carries the codegraph block + code_intelligence role.
    (b) runtime-plugins.yaml carries the codegraph entry under `plugins:`.
    (c) reference-dependencies.yaml carries the 12th active_tracking entry.
    (d) src/devolaflow/codegraph/ package exists with the 3 expected files.
    (e) Companion test files tests/test_codegraph.py +
        tests/test_plugins.py::TestV1250CodegraphRegistration +
        tests/test_runtime_plugins_smoke.py::test_codegraph_runtime_entry_smoke
        exist.

    Source: .local/research/v12.5.0_gap_analysis.md §2 D-1.
    """

    # --- (a) plugins.yaml: codegraph block + code_intelligence role ---
    plugins_path = project_root / _V12_5_0_PV03_PLUGINS_FILE
    assert plugins_path.is_file(), (
        f"W-18 v12.5.0 PV-03 violation: {_V12_5_0_PV03_PLUGINS_FILE} missing — release blocker."
    )
    plugins_payload = yaml.safe_load(plugins_path.read_text(encoding="utf-8"))
    plugins = plugins_payload.get("plugins") or {}
    assert "codegraph" in plugins, (
        "W-18 v12.5.0 PV-03 violation: plugins.yaml missing top-level "
        "`codegraph` block under `plugins:`. The block is the canonical "
        "plugin catalog declaration per A-5 SSOT registry pattern."
    )
    codegraph = plugins["codegraph"]
    assert codegraph.get("role") == "code_intelligence"
    assert codegraph.get("min_version") == "0.9.3"
    assert codegraph.get("repo_url") == "https://github.com/colbymchenry/codegraph"
    plugin_roles = plugins_payload.get("plugin_roles") or {}
    assert "code_intelligence" in plugin_roles, (
        "W-18 v12.5.0 PV-03 violation: plugins.yaml missing "
        "`plugin_roles.code_intelligence` block. The 5th role MUST exist."
    )

    # --- (b) runtime-plugins.yaml: codegraph entry --------------------
    runtime_path = project_root / _V12_5_0_PV03_RUNTIME_FILE
    runtime_payload = yaml.safe_load(runtime_path.read_text(encoding="utf-8"))
    runtime_plugins = runtime_payload.get("plugins") or []
    runtime_ids = {p.get("id") for p in runtime_plugins if isinstance(p, dict)}
    assert "codegraph" in runtime_ids, (
        f"W-18 v12.5.0 PV-03 violation: {_V12_5_0_PV03_RUNTIME_FILE} missing "
        "the `id: codegraph` entry under `plugins:` list."
    )

    # --- (c) reference-dependencies.yaml: 12th active_tracking entry --
    refs_path = project_root / _V12_5_0_PV03_REFERENCES_FILE
    refs_payload = yaml.safe_load(refs_path.read_text(encoding="utf-8"))
    active = refs_payload.get("active_tracking") or []
    active_ids = {entry.get("id") for entry in active if isinstance(entry, dict)}
    assert "codegraph" in active_ids, (
        f"W-18 v12.5.0 PV-03 violation: {_V12_5_0_PV03_REFERENCES_FILE} "
        "missing the `id: codegraph` entry under `active_tracking:` list. "
        "The reference pin enables the W-2 / SI-2 reference review cycle "
        "to track upstream codegraph version drift."
    )

    # --- (d) Python wrapper package files -----------------------------
    package_dir = project_root / _V12_5_0_PV03_PACKAGE_DIR
    assert package_dir.is_dir(), (
        f"W-18 v12.5.0 PV-03 violation: {_V12_5_0_PV03_PACKAGE_DIR} missing — "
        "release blocker. The Python wrapper package is the canonical "
        "consumer-facing surface for codegraph CLI invocations."
    )
    for fname in _V12_5_0_PV03_PACKAGE_FILES:
        assert (package_dir / fname).is_file(), (
            f"W-18 v12.5.0 PV-03 violation: {_V12_5_0_PV03_PACKAGE_DIR}/{fname} "
            "missing — release blocker per the package skeleton contract."
        )
    init_text = (package_dir / "__init__.py").read_text(encoding="utf-8")
    for helper in _V12_5_0_PV03_RESEARCHER_PUBLIC_HELPERS:
        assert f'"{helper}"' in init_text, (
            f"W-18 v12.5.0 PV-03 violation: __init__.py __all__ missing "
            f"public helper {helper!r}. The 5 researcher helpers are the "
            "v12.5.0 PV-03 D-1.1 contract surface."
        )

    # --- (e) Companion test files -------------------------------------
    codegraph_tests = project_root / Path("tests/test_codegraph.py")
    assert codegraph_tests.is_file(), (
        "W-18 v12.5.0 PV-03 violation: tests/test_codegraph.py missing — "
        "release blocker. The companion test file pins the wrapper "
        "package contract (subprocess mocking + degraded-mode + "
        "structured-error)."
    )
    plugins_tests = project_root / Path("tests/test_plugins.py")
    plugins_text = plugins_tests.read_text(encoding="utf-8")
    assert "TestV1250CodegraphRegistration" in plugins_text, (
        "W-18 v12.5.0 PV-03 violation: tests/test_plugins.py missing the "
        "TestV1250CodegraphRegistration class with the 6 plugin-registry "
        "pin tests."
    )
    runtime_tests = project_root / Path("tests/test_runtime_plugins_smoke.py")
    runtime_text = runtime_tests.read_text(encoding="utf-8")
    assert "test_codegraph_runtime_entry_smoke" in runtime_text, (
        "W-18 v12.5.0 PV-03 violation: tests/test_runtime_plugins_smoke.py "
        "missing the test_codegraph_runtime_entry_smoke test pinning the "
        "runtime plugin entry."
    )


# ---------------------------------------------------------------------------
# W-18 stanza for v12.5.0 PV-04 D-1.2 — codegraph workflow wiring
# ---------------------------------------------------------------------------
#
# Per W-18 sequencing the ghost-audit refresh MUST land BEFORE the v12.5.0
# CHANGELOG entry mentioning the codegraph workflow wiring. This stanza
# pins the v12.5.0 PV-04 D-1.2 surface (closes the codegraph integration's
# template-side surface):
#
# * repo-init.yaml: analyze.config.codegraph_commands + scaffold.config.
#   codegraph_init (with on_failure: warn + add_to_gitignore: [.codegraph/])
#   + verify.config.codegraph_smoke (mode=full only).
# * onboarding.yaml: analyze.config.codegraph_commands.
# * security-audit.yaml: analyze.config.codegraph_commands (callers + impact).
# * product-verification.yaml: analyze.config.codegraph_commands (explore + impact).
# * context_profiles.yaml: meta.codegraph_integration block (parallel to
#   meta.nines_integration) with 5 commands recipes + 6 triggers.
# * Companion test file tests/test_codegraph_workflow_wiring.py with the
#   12 structural assertion tests.
#
# Source: .local/research/v12.5.0_gap_analysis.md §2 D-1.2 +
# .local/research/v12.5.0_codegraph_benefit_analysis.md §3 surface 5 +
# §6.2 PV-04 acceptance criteria.
# ---------------------------------------------------------------------------
_V12_5_0_PV04_REPO_INIT_FILE: Path = Path("workflow-system/agent/templates/builtin/repo-init.yaml")


# v15.0.0 (v15-ADR-002 Phase B): the 3 sister yamls (onboarding /
# security-audit / product-verification) were deleted; their analyze-stage
# codegraph_commands recipes are carried over verbatim as
# params.codegraph_commands on the corresponding composition entries in
# templates/registry.yaml#compositions. The (b)-(d) pins below are
# retargeted to the manifest (provenance: v15-ADR-002 decision 2).
_V12_5_0_PV04_REGISTRY_FILE: Path = Path("workflow-system/agent/templates/registry.yaml")


_V12_5_0_PV04_SISTER_COMPOSITIONS: tuple[str, ...] = (
    "onboarding",
    "security-audit",
    "product-verification",
)


_V12_5_0_PV04_CONTEXT_PROFILES_FILE: Path = Path("workflow-system/agent/context_profiles.yaml")


def test_v12_5_0_codegraph_workflow_wired(project_root: Path) -> None:
    """W-18 v12.5.0 PV-04 D-1.2: codegraph wired across 4 templates + context profile.

    Discharges the W-18 precondition for the v12.5.0 CHANGELOG entry
    mentioning the codegraph workflow wiring. The stanza asserts six
    load-bearing surfaces:

    (a) repo-init.yaml carries 3 codegraph surfaces (analyze hint +
        scaffold init sub-step + verify smoke check).
    (b) onboarding composition carries params.codegraph_commands.
    (c) security-audit composition carries params.codegraph_commands.
    (d) product-verification composition carries params.codegraph_commands.
        ((b)-(d) retargeted from the deleted sister yamls to the
        registry.yaml compositions manifest per v15-ADR-002 Phase B.)
    (e) context_profiles.yaml carries meta.codegraph_integration block.
    (f) Companion test file tests/test_codegraph_workflow_wiring.py exists
        with the 12 structural assertion tests.

    Source: .local/research/v12.5.0_gap_analysis.md §2 D-1.2.
    """

    # --- (a) repo-init.yaml — 3 codegraph surfaces -------------------
    repo_init_text = (project_root / _V12_5_0_PV04_REPO_INIT_FILE).read_text(encoding="utf-8")
    for literal in (
        "codegraph_commands:",
        "codegraph_init:",
        "codegraph init {project_root}",
        ".codegraph/",
        "codegraph_smoke:",
    ):
        assert literal in repo_init_text, (
            f"W-18 v12.5.0 PV-04 violation: {_V12_5_0_PV04_REPO_INIT_FILE} "
            f"missing required literal {literal!r}. The 3 codegraph "
            "surfaces (analyze hint + scaffold init + verify smoke) MUST "
            "be present per the cycle plan §PV-04 deliverable list."
        )

    # --- (b)-(d) sister compositions — params.codegraph_commands -----
    # Retargeted at v15.0.0 (v15-ADR-002 Phase B): the sister yamls were
    # deleted; the wiring lives on the composition manifest entries.
    registry_payload = yaml.safe_load(
        (project_root / _V12_5_0_PV04_REGISTRY_FILE).read_text(encoding="utf-8")
    )
    compositions = {c["name"]: c for c in registry_payload.get("compositions", [])}
    for name in _V12_5_0_PV04_SISTER_COMPOSITIONS:
        entry = compositions.get(name)
        assert entry is not None, (
            f"W-18 v12.5.0 PV-04 violation (v15-ADR-002 carry-over): "
            f"composition {name!r} missing from "
            f"templates/registry.yaml#compositions."
        )
        assert (entry.get("params") or {}).get("codegraph_commands"), (
            f"W-18 v12.5.0 PV-04 violation (v15-ADR-002 carry-over): "
            f"composition {name!r} missing `params.codegraph_commands` — "
            f"the sister-template codegraph wiring MUST survive the "
            f"Phase B collapse per the cycle plan §PV-04 deliverable list."
        )

    # --- (e) context_profiles.yaml — meta.codegraph_integration block
    cp_path = project_root / _V12_5_0_PV04_CONTEXT_PROFILES_FILE
    cp_payload = yaml.safe_load(cp_path.read_text(encoding="utf-8"))
    meta = cp_payload.get("meta") or {}
    cg_integration = meta.get("codegraph_integration")
    assert cg_integration is not None, (
        f"W-18 v12.5.0 PV-04 violation: {_V12_5_0_PV04_CONTEXT_PROFILES_FILE} "
        "missing `meta.codegraph_integration` block. The block parallels "
        "meta.nines_integration above and is a release blocker."
    )
    assert "commands" in cg_integration
    assert "triggers" in cg_integration

    # --- (f) companion test file -------------------------------------
    wiring_test_path = project_root / Path("tests/test_codegraph_workflow_wiring.py")
    assert wiring_test_path.is_file(), (
        "W-18 v12.5.0 PV-04 violation: "
        "tests/test_codegraph_workflow_wiring.py missing — release blocker. "
        "The companion test file pins the workflow + context-profile "
        "wiring contract (12 structural assertion tests)."
    )
    wiring_text = wiring_test_path.read_text(encoding="utf-8")
    for class_or_test in (
        "TestRepoInitCodegraphWiring",
        "test_sister_template_analyze_has_codegraph_commands",
        "TestContextProfilesCodegraphIntegration",
    ):
        assert class_or_test in wiring_text, (
            f"W-18 v12.5.0 PV-04 violation: "
            "tests/test_codegraph_workflow_wiring.py missing "
            f"{class_or_test!r}. The 12-test contract is documented in "
            "the cycle plan §PV-04 deliverable list."
        )


# ---------------------------------------------------------------------------
# W-18 stanza for v12.5.0 PV-05 D-1.3 — codegraph docs landed
# ---------------------------------------------------------------------------
#
# Per W-18 sequencing the ghost-audit refresh MUST land BEFORE the v12.5.0
# CHANGELOG entry mentioning the codegraph reference doc + degraded-mode +
# env-flags + SKILL.md updates. This stanza pins the v12.5.0 PV-05 D-1.3
# documentation surface:
#
# * workflow-system/agent/references/codegraph.md exists with the
#   6 canonical anchor sections (§1..§6) under the C-4 Large-tier
#   ceiling.
# * workflow-system/agent/references/degraded-mode.md carries the
#   codegraph row in §"Plugin Matrix" + the §"Section 5 — codegraph"
#   detailed treatment.
# * workflow-system/agent/references/env-flags.md §7 W-20 checklist
#   carries the v12.5.0 PV-05 reuse-first reference case note (codegraph
#   reuses DEVOLAFLOW_AUTO_INSTALL_PLUGINS).
# * workflow-system/agent/SKILL.md carries the §"Workspace Engagement"
#   .codegraph/ row + §"Reference Navigation Guide" Tier-2 codegraph
#   row + §"Quick Start" repo-init codegraph note (originally
#   "auto-installs codegraph index in ALL modes"; revised to the
#   suggest-tier background wording by Track C-3 D-11 — see
#   tests/ghost/test_features_v15_0.py::
#   test_v15_0_x_codegraph_backgrounding_registered).
# * SF-4 reference set updated: 21 → 22 entries
#   (_SF4_REFERENCE_SET in tests/test_no_ghost_features.py).
# * Companion test file tests/test_codegraph_reference_doc.py exists
#   with the 6 structural assertion tests.
#
# Source: .local/research/v12.5.0_gap_analysis.md §2 D-1.3 +
# .local/research/v12.5.0_codegraph_benefit_analysis.md §6.3
# PV-05 acceptance criteria.
# ---------------------------------------------------------------------------
_V12_5_0_PV05_REFERENCE_FILE: Path = Path("workflow-system/agent/references/codegraph.md")


_V12_5_0_PV05_DEGRADED_FILE: Path = Path("workflow-system/agent/references/degraded-mode.md")


_V12_5_0_PV05_ENVFLAGS_FILE: Path = Path("workflow-system/agent/references/env-flags.md")


_V12_5_0_PV05_SKILL_FILE: Path = Path("workflow-system/agent/SKILL.md")


def test_v12_5_0_codegraph_docs_landed(project_root: Path) -> None:
    """W-18 v12.5.0 PV-05 D-1.3: codegraph docs surface landed.

    Discharges the W-18 precondition for the v12.5.0 CHANGELOG entry
    mentioning the codegraph documentation. The stanza asserts five
    load-bearing surfaces:

    (a) references/codegraph.md exists with the 6 canonical anchors.
    (b) references/degraded-mode.md mentions codegraph in §Plugin Matrix
        + §Section 5.
    (c) references/env-flags.md §7 carries the W-20 reuse-first note.
    (d) SKILL.md carries the .codegraph/ row + Tier-2 row + repo-init note.
    (e) Companion test file tests/test_codegraph_reference_doc.py exists.

    Source: .local/research/v12.5.0_gap_analysis.md §2 D-1.3.
    """
    # --- (a) references/codegraph.md ---------------------------------
    ref_path = project_root / _V12_5_0_PV05_REFERENCE_FILE
    assert ref_path.is_file(), (
        f"W-18 v12.5.0 PV-05 violation: {_V12_5_0_PV05_REFERENCE_FILE} missing — release blocker."
    )
    ref_text = ref_path.read_text(encoding="utf-8")
    for anchor in (
        "## §1 — What codegraph is",
        "## §2 — The 9 MCP tools",
        "## §3 — CLI surface",
        "## §4 — DevolaFlow integration map",
        "## §5 — Degraded-mode contract",
        "## §6 — Cache management",
    ):
        assert anchor in ref_text, (
            f"W-18 v12.5.0 PV-05 violation: "
            f"{_V12_5_0_PV05_REFERENCE_FILE} missing anchor {anchor!r}. "
            "The 6 canonical sections are the PV-05 acceptance criterion."
        )

    # --- (b) references/degraded-mode.md — codegraph row + Section 5
    degraded_text = (project_root / _V12_5_0_PV05_DEGRADED_FILE).read_text(encoding="utf-8")
    assert "| codegraph |" in degraded_text, (
        f"W-18 v12.5.0 PV-05 violation: {_V12_5_0_PV05_DEGRADED_FILE} "
        "missing the `| codegraph |` row in §Plugin Matrix."
    )
    assert "### Section 5 — codegraph" in degraded_text, (
        f"W-18 v12.5.0 PV-05 violation: {_V12_5_0_PV05_DEGRADED_FILE} "
        "missing the `### Section 5 — codegraph` detailed treatment."
    )

    # --- (c) references/env-flags.md — W-20 reuse-first note ---------
    envflags_text = (project_root / _V12_5_0_PV05_ENVFLAGS_FILE).read_text(encoding="utf-8")
    assert "v12.5.0 PV-05 reuse-first" in envflags_text, (
        f"W-18 v12.5.0 PV-05 violation: {_V12_5_0_PV05_ENVFLAGS_FILE} "
        "§7 missing the v12.5.0 PV-05 reuse-first reference case note. "
        "The note documents that codegraph REUSED "
        "DEVOLAFLOW_AUTO_INSTALL_PLUGINS rather than authoring a new flag."
    )

    # --- (d) SKILL.md — 3 codegraph mentions -------------------------
    skill_text = (project_root / _V12_5_0_PV05_SKILL_FILE).read_text(encoding="utf-8")
    assert ".codegraph/codegraph.db" in skill_text or ".codegraph/" in skill_text, (
        f"W-18 v12.5.0 PV-05 violation: {_V12_5_0_PV05_SKILL_FILE} "
        "§Workspace Engagement missing the .codegraph/ row."
    )
    assert "references/codegraph.md" in skill_text, (
        f"W-18 v12.5.0 PV-05 violation: {_V12_5_0_PV05_SKILL_FILE} "
        "§Reference Navigation Guide Tier-2 missing the codegraph row."
    )
    # Track C-3 D-11 revised the original "auto-installs codegraph index
    # in ALL modes" wording: codegraph is now suggest-tier + backgrounded.
    # The stanza keeps pinning that the repo-init row MENTIONS codegraph
    # (the PV-05 deliverable); the current wording is pinned by the v15
    # stanza (test_v15_0_x_codegraph_backgrounding_registered).
    assert "codegraph suggest-tier" in skill_text, (
        f"W-18 v12.5.0 PV-05 violation: {_V12_5_0_PV05_SKILL_FILE} "
        "§Quick Start repo-init row lost its codegraph note "
        "(suggest-tier wording per Track C-3 D-11)."
    )

    # --- (e) companion test file -------------------------------------
    doc_test_path = project_root / Path("tests/test_codegraph_reference_doc.py")
    assert doc_test_path.is_file(), (
        "W-18 v12.5.0 PV-05 violation: "
        "tests/test_codegraph_reference_doc.py missing — release blocker."
    )


# ---------------------------------------------------------------------------
# W-18 stanza for v12.5.0 PV-05 D-3 — handoff envelope auto-strip helper
# ---------------------------------------------------------------------------
#
# Per W-18 sequencing the ghost-audit refresh MUST land BEFORE the v12.5.0
# CHANGELOG entry mentioning the strip_l0_only_metadata helper. This stanza
# pins the v12.5.0 PV-05 D-3 surface (closes the v12.4.0 retro §6 telegraph
# item 2 — handoff envelope auto-strip helper):
#
# * src/devolaflow/agent_workspace/handoff.py exports the
#   strip_l0_only_metadata public function symbol.
# * The helper signature matches the documented contract
#   (envelope: dict -> dict; pure / idempotent / permissive on absent /
#   permissive on empty / S-5 explicit warn on non-dict).
# * Companion test file tests/test_handoff_strip_metadata.py exists with
#   the 11 contract-pin tests covering happy-path + idempotency +
#   pure-function-invariant + degraded paths.
#
# Source: .local/research/v12.5.0_gap_analysis.md §2 D-3 +
# .local/research/v12.4.0_retrospective.md §6 telegraph item 2.
# ---------------------------------------------------------------------------
_V12_5_0_PV05_HANDOFF_FILE: Path = Path("src/devolaflow/agent_workspace/handoff.py")


def test_v12_5_0_handoff_strip_helper(project_root: Path) -> None:
    """W-18 v12.5.0 PV-05 D-3: strip_l0_only_metadata helper landed.

    Discharges the W-18 precondition for the v12.5.0 CHANGELOG entry
    mentioning the handoff envelope auto-strip helper. The stanza
    asserts three load-bearing surfaces:

    (a) src/devolaflow/agent_workspace/handoff.py declares the public
        strip_l0_only_metadata symbol with the documented signature.
    (b) The helper is exported in __all__ so callers can import it.
    (c) Companion test file tests/test_handoff_strip_metadata.py exists
        with the 11 contract-pin tests.

    Source: .local/research/v12.5.0_gap_analysis.md §2 D-3.
    """
    # --- (a) handoff.py declares the helper --------------------------
    handoff_text = (project_root / _V12_5_0_PV05_HANDOFF_FILE).read_text(encoding="utf-8")
    assert "def strip_l0_only_metadata(envelope: dict) -> dict:" in handoff_text, (
        f"W-18 v12.5.0 PV-05 violation: {_V12_5_0_PV05_HANDOFF_FILE} "
        "missing `def strip_l0_only_metadata(envelope: dict) -> dict:` "
        "definition. The signature is part of the v12.5.0 PV-05 D-3 "
        "contract surface."
    )

    # --- (b) __all__ export ------------------------------------------
    assert '__all__.append("strip_l0_only_metadata")' in handoff_text, (
        f"W-18 v12.5.0 PV-05 violation: {_V12_5_0_PV05_HANDOFF_FILE} "
        'missing `__all__.append("strip_l0_only_metadata")` — the '
        "public-API export is part of the contract."
    )

    # --- (c) companion test file -------------------------------------
    test_path = project_root / Path("tests/test_handoff_strip_metadata.py")
    assert test_path.is_file(), (
        "W-18 v12.5.0 PV-05 violation: "
        "tests/test_handoff_strip_metadata.py missing — release blocker."
    )
    test_text = test_path.read_text(encoding="utf-8")
    for expected_test in (
        "test_happy_path_strips_banner_literal_from_string_field",
        "test_happy_path_strips_quality_score_key",
        "test_idempotency",
        "test_input_dict_not_mutated",
        "test_non_dict_input_warns_and_returns_unchanged",
        "test_companion_to_banner_hook_zero_violations_post_strip",
    ):
        assert f"def {expected_test}" in test_text, (
            f"W-18 v12.5.0 PV-05 violation: "
            "tests/test_handoff_strip_metadata.py missing test "
            f"{expected_test!r}."
        )
