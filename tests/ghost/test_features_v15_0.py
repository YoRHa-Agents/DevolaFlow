"""Ghost audit — per-cycle W-18 feature stanzas for the v15.0 cycle.

Per v15-ADR-001 (v14.3.0 split): new W-18 stanzas for a v15.0.x release
append HERE; the next MAJOR/MINOR cycle rotates to a fresh
``test_features_v<MAJ>_<MIN>.py``. Every symbol pinned below was
verified against the working tree at authoring time (v15.0.0 T7
release close) — NOT blind-trusted from sibling-task descriptions.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest
import yaml


def test_v15_0_0_pre_dispatch_strict_graduation_registered(project_root: Path) -> None:
    """W-18 v15.0.0: the T1 pre_dispatch strict graduation (G-038) has coverage.

    Discharges the W-18 precondition for the v15.0.0 CHANGELOG entry on
    the T1 hook-chain slice. The stanza pins:

    (a) The chain-strict knob: ``ProposalEmitter`` AND
        ``ProposalGenerator`` accept ``pre_dispatch_strict`` defaulting
        to ``True`` (escape hatch:
        ``ProposalGenerator(pre_dispatch_strict=False)``).
    (b) ``reject_subagent_quality_score`` nested scan covers EXACTLY the
        ``metrics`` / ``self_check`` evidence blocks (the v14.3.0
        placeholder discharge — see test_features_v14_3.py).
    (c) ``reject_subagent_banner_emission`` is default-wired into the
        pre_dispatch chain at import time, with the documented per-handler
        opt-out ``unregister_pre_dispatch_extra()``.
    (d) ``lifecycle.dispatcher.unregister_hook`` — the generic G-038
        flip-3 opt-out surface — is exported and callable.
    """
    import importlib

    from devolaflow.feedback import ProposalGenerator
    from devolaflow.feedback_emit import ProposalEmitter
    from devolaflow.lifecycle import dispatcher

    # importlib.import_module — the package __init__ re-binds these names
    # to the hook FUNCTIONS, so a plain ``from devolaflow.lifecycle
    # import ...`` would shadow the modules.
    banner_mod = importlib.import_module("devolaflow.lifecycle.reject_subagent_banner_emission")
    qs_mod = importlib.import_module("devolaflow.lifecycle.reject_subagent_quality_score")

    # --- (a) chain-strict knob, strict by default ---------------------------
    for cls in (ProposalEmitter, ProposalGenerator):
        param = inspect.signature(cls.__init__).parameters.get("pre_dispatch_strict")
        assert param is not None and param.default is True, (
            f"W-18 v15.0.0 violation: {cls.__name__} lost the "
            "pre_dispatch_strict=True default (G-038 strict graduation; "
            "escape: pre_dispatch_strict=False)."
        )

    # --- (b) QS nested scan over metrics/self_check -------------------------
    assert qs_mod._NESTED_SCAN_BLOCKS == ("metrics", "self_check"), (
        "W-18 v15.0.0 violation: reject_subagent_quality_score nested-scan "
        "block set drifted from ('metrics', 'self_check') (G-038; "
        "v14.3.0 placeholder discharge)."
    )

    # --- (c) banner hook default-wired + documented opt-out ------------------
    lifecycle_init = (project_root / "src/devolaflow/lifecycle/__init__.py").read_text(
        encoding="utf-8"
    )
    banner_wiring = "register_hook(_PRE_DISPATCH_EVENT, reject_subagent_banner_emission)"
    assert banner_wiring in lifecycle_init, (
        "W-18 v15.0.0 violation: lifecycle/__init__.py no longer default-"
        "wires reject_subagent_banner_emission into pre_dispatch (G-038 flip 3)."
    )
    assert callable(banner_mod.unregister_pre_dispatch_extra), (
        "W-18 v15.0.0 violation: unregister_pre_dispatch_extra opt-out missing "
        "from reject_subagent_banner_emission (G-038 flip 3)."
    )

    # --- (d) generic per-handler opt-out surface ------------------------------
    assert callable(dispatcher.unregister_hook), (
        "W-18 v15.0.0 violation: lifecycle.dispatcher.unregister_hook missing "
        "(the G-038 flip-3 per-handler opt-out surface)."
    )
    assert "unregister_hook" in dispatcher.__all__


def test_v15_0_0_default_events_17_registered() -> None:
    """W-18 v15.0.0: DEFAULT_EVENTS 16 → 17 (G-038 flip 4) has coverage.

    ``check_human_input_write`` (exported additively since v14.0.0)
    joins the tuple APPENDED at position 17 per A-2.2 append-only —
    positions 1-16 stay byte-stable; position 1 stays ``pre_dispatch``.
    """
    from devolaflow.lifecycle import (
        CHECK_HUMAN_INPUT_WRITE_EVENT,
        DEFAULT_EVENTS,
        PRE_DISPATCH_EVENT,
    )

    assert len(DEFAULT_EVENTS) == 17, (
        f"W-18 v15.0.0 violation: DEFAULT_EVENTS length drifted to "
        f"{len(DEFAULT_EVENTS)} (G-038 flip 4 pinned the 17-entry shape)."
    )
    assert DEFAULT_EVENTS[0] == PRE_DISPATCH_EVENT
    assert DEFAULT_EVENTS[16] == CHECK_HUMAN_INPUT_WRITE_EVENT, (
        "W-18 v15.0.0 violation: check_human_input_write must sit at "
        "position 17 (A-2.2 append-only tail)."
    )


def test_v15_0_0_workspace_strict_and_timeout_registered(project_root: Path) -> None:
    """W-18 v15.0.0: workspace strict wiring + wave timeouts (G-038 flips 1+5) have coverage.

    The stanza pins:

    (a) ``runtime_wiring.fire_file_write`` / ``fire_task_stop`` default
        ``strict=True`` (S-8 "mode: full" under
        DEVOLAFLOW_AGENT_WORKSPACE=1; opt-out ``strict=False``).
    (b) The call sites in agent_workspace/change.py + handoff.py
        RE-RAISE ``HookViolation`` (block + escalate) instead of the
        v14.3.0 warn-and-proceed.
    (c) ``dispatch._resolve_task_timeout`` resolution order: explicit
        ``timeout_seconds`` verbatim → ``None`` opt-out → G-037
        task-type class default → 7200 s fail-safe ceiling.
    """
    from devolaflow.dispatch import _resolve_task_timeout
    from devolaflow.lifecycle.runtime_wiring import fire_file_write, fire_task_stop

    # --- (a) strict defaults --------------------------------------------------
    for fn in (fire_file_write, fire_task_stop):
        param = inspect.signature(fn).parameters["strict"]
        assert param.default is True, (
            f"W-18 v15.0.0 violation: {fn.__name__} lost the strict=True "
            "default (G-038 flip 5 / S-8 mode: full)."
        )

    # --- (b) call-site re-raise -------------------------------------------------
    for rel_path in (
        "src/devolaflow/agent_workspace/change.py",
        "src/devolaflow/agent_workspace/handoff.py",
    ):
        text = (project_root / rel_path).read_text(encoding="utf-8")
        assert "except HookViolation:" in text, (
            f"W-18 v15.0.0 violation: {rel_path} lost the HookViolation "
            "re-raise call site (G-038 flip 5 block + escalate)."
        )

    # --- (c) timeout resolution order (G-038 flip 1, fed by G-037) -------------
    assert _resolve_task_timeout({"timeout_seconds": 42}) == 42.0
    assert _resolve_task_timeout({"timeout_seconds": None}) is None, (
        "W-18 v15.0.0 violation: timeout_seconds: null must stay the "
        "documented per-task opt-out (no timeout)."
    )
    assert _resolve_task_timeout({"type": "hotfix"}) == 600.0
    assert _resolve_task_timeout({}) == 7200.0, (
        "W-18 v15.0.0 violation: unknown/missing task type must resolve "
        "to the 7200 s fail-safe ceiling."
    )


def test_v15_0_0_legibility_weight_graduation_registered() -> None:
    """W-18 v15.0.0: STANDARD legibility_weight 0.0 → 0.05 (G-038 flip 6) has coverage.

    STANDARD matches STRICT/AUDIT at 0.05; RELAXED stays 0.0. Opt-out:
    ``dataclasses.replace(STANDARD, legibility_weight=0.0)``.
    """
    from devolaflow.gate.profiles import AUDIT, RELAXED, STANDARD, STRICT

    assert STANDARD.legibility_weight == pytest.approx(0.05), (
        "W-18 v15.0.0 violation: STANDARD.legibility_weight drifted from "
        "0.05 (G-038 flip 6 graduation)."
    )
    assert STRICT.legibility_weight == pytest.approx(0.05)
    assert AUDIT.legibility_weight == pytest.approx(0.05)
    assert RELAXED.legibility_weight == pytest.approx(0.0), (
        "W-18 v15.0.0 violation: RELAXED.legibility_weight must stay 0.0 "
        "(the byte-identical permissive profile)."
    )


def test_v15_0_0_strict_graduation_doc_pins_registered(project_root: Path) -> None:
    """W-18 v15.0.0: the T1 strict-graduation doc pins have coverage.

    (a) env-flags.md §2.15 carries the G-038 strict-graduation row for
        the engaged-workspace adapters (flag absent = byte-identical
        no-op, UNCHANGED).
    (b) execution-protocol.md §14 carries the default-on
        ``asyncio.wait_for`` timeout graduation contract.
    """
    env_text = (project_root / "workflow-system/agent/references/env-flags.md").read_text(
        encoding="utf-8"
    )
    section_2_15 = env_text.split("### 2.15 `DEVOLAFLOW_AGENT_WORKSPACE`", 1)
    assert len(section_2_15) == 2, (
        "W-18 v15.0.0 violation: env-flags.md lost the §2.15 DEVOLAFLOW_AGENT_WORKSPACE section."
    )
    body_2_15 = section_2_15[1].split("\n### ", 1)[0]
    assert "v15.0.0 strict graduation (G-038)" in body_2_15, (
        "W-18 v15.0.0 violation: env-flags.md §2.15 missing the G-038 "
        "strict-graduation row (S-8 mode: full under the engaged flag)."
    )

    ep_text = (project_root / "workflow-system/agent/references/execution-protocol.md").read_text(
        encoding="utf-8"
    )
    section_14 = ep_text.split("## 14. Per-Task-Type Timeout Defaults", 1)
    assert len(section_14) == 2
    body_14 = section_14[1].split("\n## ", 1)[0]
    for fragment in ("v15.0.0 strict graduation (G-038)", "asyncio.wait_for"):
        assert fragment in body_14, (
            f"W-18 v15.0.0 violation: execution-protocol.md §14 missing the "
            f"graduated {fragment!r} timeout contract (G-038 flip 1)."
        )


def test_v15_0_0_artifact_scoring_registered(project_root: Path) -> None:
    """W-18 v15.0.0: the T4 L0 artifact scoring module (v15-ADR-007 phase 2) has coverage.

    Pins the 4 public symbols of ``gate/artifact_score.py``
    (``score_artifact_evidence`` / ``ArtifactScore`` + ``to_gate_input``
    / ``DimensionScore`` / ``EvidenceDoctrineError``), the
    evidence-doctrine raise, the unscored-renormalization honesty
    contract, AND the wiring direction discipline (gate→scorer since
    the v15.0.0 R1 reinforcement slice — the scorer module never
    invokes ``evaluate_gate``; see
    ``test_v15_0_0_artifact_evidence_gate_wiring_registered``).
    """
    from devolaflow.gate.artifact_score import (
        ArtifactScore,
        DimensionScore,
        EvidenceDoctrineError,
        score_artifact_evidence,
    )

    # Evidence doctrine: a smuggled L3 score raises — top level AND nested.
    with pytest.raises(EvidenceDoctrineError):
        score_artifact_evidence({"quality_score": 9.5})
    with pytest.raises(EvidenceDoctrineError):
        score_artifact_evidence({"metrics": {"quality": 9.5}})

    # Unscored renormalization: no evidence → composite None, coverage 0.0.
    empty = score_artifact_evidence({})
    assert isinstance(empty, ArtifactScore)
    assert empty.composite is None and empty.evidence_coverage == 0.0, (
        "W-18 v15.0.0 violation: score_artifact_evidence must never "
        "fabricate a composite from zero evidence (ADR-007)."
    )
    assert all(isinstance(dim, DimensionScore) for dim in empty.dimensions.values())
    assert empty.to_gate_input() == {"dimensions": {}, "weights": {}}

    # Partial evidence: correctness scores; weights renormalize to 1.0.
    partial = score_artifact_evidence({"ac_results": [{"id": "AC-1", "verdict": "pass"}]})
    assert partial.composite is not None
    adapter = partial.to_gate_input()
    assert sum(adapter["weights"].values()) == pytest.approx(1.0)

    # Standalone discipline + dedicated suite.
    module_text = (project_root / "src/devolaflow/gate/artifact_score.py").read_text(
        encoding="utf-8"
    )
    assert "evaluate_gate(" not in module_text, (
        "W-18 v15.0.0 violation: artifact_score.py must stay gate-agnostic — "
        "the R1 wiring direction is gate→scorer (scorer.py consumes "
        "score_artifact_evidence); this module never invokes evaluate_gate."
    )
    assert (project_root / "tests/test_artifact_score.py").is_file()


def test_v15_0_0_artifact_evidence_gate_wiring_registered(project_root: Path) -> None:
    """W-18 v15.0.0: the R1 evaluate_gate artifact-evidence wiring has coverage.

    Discharges the SI-3 reinforcement rule R1 ("measured-not-gated"):
    the L0-side artifact score is now gate-consumable. The stanza pins:

    (a) ``evaluate_gate`` accepts ``artifact_evidence`` defaulting
        ``None`` (absence-safe per the legibility precedent).
    (b) ``GateProfile.artifact_evidence_weight`` defaults — model 0.0;
        STRICT/STANDARD/AUDIT 0.05, RELAXED 0.0 (legibility mirror).
    (c) ``score_artifact_evidence`` is OFF the dead-API
        ``DEFAULT_ALLOWLIST`` (it has a production caller now).
    (d) The doc pins: decomposition-gate.md gate-dimension row +
        artifact-quality.md §3 consumer line cite the wiring.
    """
    from devolaflow.gate.models import GateProfile
    from devolaflow.gate.profiles import AUDIT, RELAXED, STANDARD, STRICT
    from devolaflow.gate.scorer import _attach_artifact_evidence, evaluate_gate

    # --- (a) opt-in NEST-style parameter, absence-safe default ---------------
    param = inspect.signature(evaluate_gate).parameters.get("artifact_evidence")
    assert param is not None and param.default is None, (
        "W-18 v15.0.0 violation: evaluate_gate lost the artifact_evidence "
        "opt-in parameter (R1 gate wiring per v15-ADR-007)."
    )
    assert callable(_attach_artifact_evidence)

    # --- (b) weight defaults mirror the legibility precedent ------------------
    field_default = GateProfile.__dataclass_fields__["artifact_evidence_weight"].default
    assert field_default == 0.0
    for profile, expected in ((STRICT, 0.05), (STANDARD, 0.05), (AUDIT, 0.05), (RELAXED, 0.0)):
        assert profile.artifact_evidence_weight == pytest.approx(expected), (
            f"W-18 v15.0.0 violation: {profile.name}.artifact_evidence_weight "
            f"drifted from {expected} (R1 legibility-mirror defaults)."
        )

    # --- (c) allowlist cleanup -------------------------------------------------
    dead_apis_text = (project_root / "scripts/detect_dead_apis.py").read_text(encoding="utf-8")
    assert '"devolaflow.gate.artifact_score:score_artifact_evidence"' not in dead_apis_text, (
        "W-18 v15.0.0 violation: score_artifact_evidence must stay OFF "
        "DEFAULT_ALLOWLIST — the R1 wiring gave it a production caller."
    )

    # --- (d) doc pins -----------------------------------------------------------
    dg_text = (project_root / "workflow-system/agent/references/decomposition-gate.md").read_text(
        encoding="utf-8"
    )
    assert "artifact_evidence_weight" in dg_text, (
        "W-18 v15.0.0 violation: decomposition-gate.md lost the R1 "
        "artifact-evidence gate-dimension doc line."
    )
    aq_text = (project_root / "workflow-system/agent/references/artifact-quality.md").read_text(
        encoding="utf-8"
    )
    assert "evaluate_gate" in aq_text and "artifact_evidence" in aq_text, (
        "W-18 v15.0.0 violation: artifact-quality.md §3 consumer line no "
        "longer cites the evaluate_gate(artifact_evidence=...) wiring."
    )


def test_v15_0_0_dedup_digest_coherence_registered(project_root: Path) -> None:
    """W-18 v15.0.0: the T5 dedup-ledger self-containment (G-007) has coverage.

    Pins ``DEDUP_DIGEST_MAX_CHARS`` (320), the ``_digest_summary`` bound,
    the ``_DEDUP_REF_RE`` ref shape, the ``entries[*].digest`` schema
    literal in lean-dispatch.yaml, and the context-isolation.md
    self-containment anchor.
    """
    from devolaflow.compressor import DEDUP_DIGEST_MAX_CHARS, _digest_summary
    from devolaflow.compressor.transforms import _DEDUP_REF_RE

    assert DEDUP_DIGEST_MAX_CHARS == 320, (
        "W-18 v15.0.0 violation: DEDUP_DIGEST_MAX_CHARS drifted from 320 (G-007)."
    )
    short = "fact-A; fact-B"
    assert _digest_summary(short) == short, (
        "W-18 v15.0.0 violation: summaries at or under the bound must "
        "travel verbatim through _digest_summary (G-007)."
    )
    assert len(_digest_summary("x" * 1000)) <= DEDUP_DIGEST_MAX_CHARS
    assert _DEDUP_REF_RE.match("@round-1:pred-0"), (
        "W-18 v15.0.0 violation: _DEDUP_REF_RE no longer matches the "
        "'@round-N:pred-K' ref shape — ref-exclusion (no chained ref→ref) "
        "depends on it (G-007)."
    )
    assert not _DEDUP_REF_RE.match("plain summary text")

    schema_text = (project_root / "schemas/lean-dispatch.yaml").read_text(encoding="utf-8")
    assert "entries[*].digest" in schema_text, (
        "W-18 v15.0.0 violation: lean-dispatch.yaml lost the "
        "entries[*].digest self-containment literal (G-007 NEST; "
        "canonical_order stays 17 / version stays 6)."
    )
    assert "digest: str (v15.0.0 G-007" in schema_text

    ci_text = (project_root / "workflow-system/agent/references/context-isolation.md").read_text(
        encoding="utf-8"
    )
    assert "`predecessor_dedup_ledger` self-containment (v15.0.0, G-007" in ci_text, (
        "W-18 v15.0.0 violation: context-isolation.md §10 lost the G-007 self-containment anchor."
    )


def test_v15_0_0_plugin_registry_unification_registered(project_root: Path) -> None:
    """W-18 v15.0.0: the T6 plugin-registry unification (G-021) has coverage.

    Pins the owner header ("single A-5 SSOT owner" in
    runtime-plugins.yaml), the view header ("DERIVED SURFACE" +
    generated-from truth in plugins.yaml), and the id-mirror: the view's
    plugin keys equal the owner's ``plugins[*].id`` set AND order.
    """
    owner_path = project_root / "workflow-system/agent/knowledge/runtime-plugins.yaml"
    view_path = project_root / "workflow-system/agent/plugins.yaml"

    owner_text = owner_path.read_text(encoding="utf-8")
    assert "single A-5 SSOT owner" in owner_text, (
        "W-18 v15.0.0 violation: runtime-plugins.yaml lost its A-5 SSOT "
        "owner header (G-021 unification)."
    )

    view_text = view_path.read_text(encoding="utf-8")
    assert "DERIVED SURFACE (v15.0.0 G-021)" in view_text, (
        "W-18 v15.0.0 violation: plugins.yaml lost its DERIVED-SURFACE "
        "header (G-021 — the view is NOT a second registration owner)."
    )
    assert "GENERATED-FROM TRUTH" in view_text

    owner = yaml.safe_load(owner_text)
    view = yaml.safe_load(view_text)
    owner_ids = [p["id"] for p in owner["plugins"]]
    view_ids = list(view["plugins"].keys())
    assert view_ids == owner_ids, (
        f"W-18 v15.0.0 violation: plugins.yaml view keys {view_ids} no "
        f"longer mirror the owner's plugins[*].id order {owner_ids} (G-021)."
    )
    assert "ui-pro" in owner_ids and "rtk" in owner_ids, (
        "W-18 v15.0.0 violation: the G-021 ui-pro rename / rtk addition "
        "regressed in the owner registry."
    )


def test_v15_0_0_r2_retirement_criteria_registered(project_root: Path) -> None:
    """W-18 v15.0.0 R2: dated shim/alias retirement criteria exist (SI-3 §4 item 4).

    The R2 reinforcement round (W-8) appended a "Retirement criteria
    (v15.0.0 R2)" section to v15-ADR-006 (24 re-export shims) and
    v15-ADR-002 (16 composition aliases). The stanza pins, per ADR:

    (a) the section heading exists and is DATED (2026-06-12 authoring +
        the v16.0.0 retirement window + the EXTEND-to-v17.0.0 fallback);
    (b) each criterion is command-anchored (the exact check command
        appears in the section);
    (c) ADR-006 names BOTH S-10 permanent exemptions verbatim.
    """
    heading = "## Retirement criteria (v15.0.0 R2)"
    adr_dir = project_root / ".local/research/adr"
    adr6 = (adr_dir / "v15-ADR-006-scorer-selector-module-split.md").read_text(encoding="utf-8")
    adr2 = (adr_dir / "v15-ADR-002-template-phase-b-collapse.md").read_text(encoding="utf-8")

    for name, text in (("v15-ADR-006", adr6), ("v15-ADR-002", adr2)):
        assert heading in text, (
            f"W-18 v15.0.0 R2 violation: {name} lost its '{heading}' section "
            "(SI-3 finding R4 — open-ended compatibility surfaces)."
        )
        section = text.split(heading, 1)[1]
        for date_pin in ("2026-06-12", "v16.0.0", "EXTEND-to-v17.0.0"):
            assert date_pin in section, (
                f"W-18 v15.0.0 R2 violation: {name} retirement criteria lost "
                f"the dated anchor {date_pin!r} — criteria must stay dated."
            )

    # (b) command-anchored: each section carries its exact check commands.
    adr6_section = adr6.split(heading, 1)[1]
    for command in (
        "python -m pytest tests/test_module_split_shims.py"
        "::test_s10_named_paths_verbatim_functional -q",
        'rg -n "revisit ≥ v16.0.0 per the ADR-006 shim clause" CHANGELOG.md',
    ):
        assert command in adr6_section, (
            f"W-18 v15.0.0 R2 violation: ADR-006 retirement criteria lost "
            f"the check command {command!r}."
        )
    adr2_section = adr2.split(heading, 1)[1]
    for command in (
        '"tests/test_template_compositions.py::test_alias_resolution_emits_deprecation_warning"',
        'rg -n "hard removal lands no earlier than v16.0.0" CHANGELOG.md',
    ):
        assert command in adr2_section, (
            f"W-18 v15.0.0 R2 violation: ADR-002 retirement criteria lost "
            f"the check command {command!r}."
        )

    # (c) ADR-006 names the two S-10 permanent exemptions verbatim.
    for exempt_path in (
        "`feedback.py::populate_cascade_gate_fields`",
        "`feedback.py::ProposalGenerator.generate_round_dispatch`",
    ):
        assert exempt_path in adr6_section, (
            f"W-18 v15.0.0 R2 violation: ADR-006 retirement criteria no "
            f"longer name the S-10 permanent exemption {exempt_path} — the "
            "exemptions must stay named so no retirement PR touches them."
        )
