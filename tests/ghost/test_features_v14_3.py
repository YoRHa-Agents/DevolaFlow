"""Ghost audit — per-cycle W-18 feature stanzas for the v14.3 cycle.

Split from ``tests/test_no_ghost_features.py`` per v15-ADR-001
(v14.3.0). New W-18 stanzas for a v14.3.x release append HERE; the
next MINOR cycle rotates to a fresh ``test_features_v<MAJ>_<MIN>.py``.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from tests.ghost.test_registries import _SF4_REFERENCE_SET


def test_v14_3_0_artifact_quality_rubric_registered(project_root: Path) -> None:
    """W-18 v14.3.0: the artifact-quality evidence rubric (G-004) has coverage.

    Discharges the W-18 precondition for the v14.3.0 CHANGELOG entry on the
    T2 slice (evidence rubric + L3 self-verify protocol per v15-ADR-007).
    The stanza asserts the load-bearing surfaces:

    (a) references/artifact-quality.md exists with all 5 sections + the
        doctrine guard line (evidence-not-scores).
    (b) "artifact-quality.md" is pinned in _SF4_REFERENCE_SET (25th entry).
    (c) SKILL.md carries the Tier-2 nav row + the VERIFY-step self-verify
        pointer (C-7 places 1+3 of the four-place sync).
    (d) scripts/sync_cursor_skill.py MIRRORED_FILES carries the entry
        (C-7 place 4).
    (e) references/execution-protocol.md carries §15 "L3 Self-Verify"
        (G-005 protocol slice: AC-v2 consumption + max-2-iteration bound).
    (f) references/task-quality-score.md cross-references the rubric split.

    Source: .local/research/v14.2.0_gap_analysis.md §2.1 G-004 + G-005;
    docs/cycle-archive/adr/v15-ADR-007-artifact-evidence-vs-scoring-doctrine.md.
    """
    # --- (a) the 25th reference + doctrine guard ----------------------
    ref_path = project_root / "workflow-system/agent/references/artifact-quality.md"
    assert ref_path.is_file(), (
        "W-18 v14.3.0 violation: references/artifact-quality.md missing — release blocker."
    )
    ref_text = ref_path.read_text(encoding="utf-8")
    assert "L3 MUST NOT compute or report numeric quality scores" in ref_text, (
        "W-18 v14.3.0 violation: artifact-quality.md missing the §1 doctrine guard line."
    )
    assert "reject_subagent_quality_score" in ref_text, (
        "W-18 v14.3.0 violation: artifact-quality.md must cite the runtime doctrine hook."
    )
    for section in (
        "## §1 Doctrine",
        "## §2 The Four Excellence Dimensions",
        "## §3 Evidence Emission Map",
        "## §4 Self-Verify Checklist",
        "## §5 Failure Honesty",
    ):
        assert section in ref_text, (
            f"W-18 v14.3.0 violation: artifact-quality.md missing section {section!r}."
        )

    # --- (b) SF-4 set membership --------------------------------------
    assert "artifact-quality.md" in set(_SF4_REFERENCE_SET), (
        "W-18 v14.3.0 violation: _SF4_REFERENCE_SET must include artifact-quality.md (25th entry)."
    )

    # --- (c) SKILL.md Tier-2 row + VERIFY-step pointer ----------------
    skill_text = (project_root / "workflow-system/agent/SKILL.md").read_text(encoding="utf-8")
    assert "`references/artifact-quality.md`" in skill_text, (
        "W-18 v14.3.0 violation: SKILL.md Tier-2 nav table missing the artifact-quality.md row."
    )
    assert "L0 verifies evidence, not vibes" in skill_text, (
        "W-18 v14.3.0 violation: SKILL.md VERIFY step missing the L3 self-verify pointer."
    )

    # --- (d) mirror manifest entry ------------------------------------
    # Since the v15.0.x install-manifest SSOT (Track B-1), MIRRORED_FILES
    # derives from workflow-system/agent/manifest.yaml — the entry check
    # targets the owner surface (C-7 place 4).
    manifest_text = (project_root / "workflow-system/agent/manifest.yaml").read_text(
        encoding="utf-8"
    )
    assert "references/artifact-quality.md" in manifest_text, (
        "W-18 v14.3.0 violation: workflow-system/agent/manifest.yaml "
        "missing references/artifact-quality.md."
    )

    # --- (e) execution-protocol §15 L3 Self-Verify --------------------
    proto_text = (
        project_root / "workflow-system/agent/references/execution-protocol.md"
    ).read_text(encoding="utf-8")
    assert "## 15. L3 Self-Verify (v14.3.0+)" in proto_text, (
        "W-18 v14.3.0 violation: execution-protocol.md missing §15 L3 Self-Verify."
    )
    assert "acceptance_criteria_v2" in proto_text and "2 self-fix iterations" in proto_text, (
        "W-18 v14.3.0 violation: §15 must consume acceptance_criteria_v2."
        " with the max-2-self-fix-iteration P4 bound."
    )

    # --- (f) task-quality-score.md rubric-split cross-ref -------------
    tqs_text = (project_root / "workflow-system/agent/references/task-quality-score.md").read_text(
        encoding="utf-8"
    )
    assert "artifact-quality.md" in tqs_text, (
        "W-18 v14.3.0 violation: task-quality-score.md missing the cross-ref "
        "distinguishing the two rubrics."
    )

    # --- (g) sibling G-002/G-003 report transport (landed same wave) --
    # The rubric's §3 emission map cites these as its transport contract;
    # pin them here so the cross-file fact cannot silently regress.
    report_text = (project_root / "schemas/lean-report.yaml").read_text(encoding="utf-8")
    for block in ("self_check:", "ac_results:", "diff_stats:"):
        assert block in report_text, (
            f"W-18 v14.3.0 violation: schemas/lean-report.yaml missing the "
            f"additive {block!r} evidence block the artifact-quality §3 "
            "emission map transports through."
        )


# --- SIBLING-TASK PLACEHOLDER RESOLUTION (v14.3.0 T4 release-close) -------
# The T2 authoring-time placeholder asked release-close to pin (1) the
# lifecycle runtime-wiring symbols per v15-ADR-003 — discharged by
# ``test_v14_3_0_hook_runtime_wiring_registered`` below — and (2) the
# ``reject_subagent_quality_score`` doctrine extension over the NEW report
# blocks. Item (2) is now DISCHARGED: the in-block scanning extension
# landed at v15.0.0 (G-038 — the hook scans the ``metrics`` /
# ``self_check`` evidence blocks, strict by default) and is pinned by
# ``tests/ghost/test_features_v15_0.py::
# test_v15_0_0_pre_dispatch_strict_graduation_registered`` per the
# v15-ADR-007 phase split. The prompt-side doctrine that keeps the new
# blocks score-free remains pinned by
# ``test_v14_3_0_report_evidence_blocks_registered`` below.


def test_v14_3_0_report_evidence_blocks_registered(project_root: Path) -> None:
    """W-18 v14.3.0: the T1 report-evidence transport (G-002 + G-003) has coverage.

    Discharges the W-18 precondition for the v14.3.0 CHANGELOG entry on the
    T1 slice (lean-report evidence blocks + behavioral-guidelines Evidence
    wiring + message-schemas reference rows). The stanza pins:

    (a) schemas/lean-report.yaml ``lean_format_spec.self_check`` with all 5
        evidence fields (plan_artifact / goal_anchor / simplicity /
        conflicts / conventions).
    (b) ``lean_format_spec.ac_results`` per-entry shape {id, verdict,
        cmd_digest} with the ``pass|fail|skip`` verdict enum.
    (c) ``lean_format_spec.diff_stats`` fields {files, insertions,
        deletions}.
    (d) references/behavioral-guidelines.md carries the 5 ``**Evidence**``
        clauses citing ``self_check.*`` + the See-Also wiring line to
        ``lean_format_spec.self_check``.
    (e) references/message-schemas.md §"Field Documentation" carries the 3
        new rows + the evidence-only doctrine paragraph citing the
        ``reject_subagent_quality_score`` runtime guard (v15-ADR-007).

    Source: .local/research/v14.2.0_gap_analysis.md §2.1 G-002 + G-003;
    docs/cycle-archive/adr/v15-ADR-007-artifact-evidence-vs-scoring-doctrine.md.
    """
    # --- (a)-(c) lean_format_spec structural pins ----------------------
    report_spec = yaml.safe_load(
        (project_root / "schemas/lean-report.yaml").read_text(encoding="utf-8")
    )["lean_format_spec"]

    self_check_fields = set(report_spec["self_check"]["fields"])
    expected_self_check = {"plan_artifact", "goal_anchor", "simplicity", "conflicts", "conventions"}
    assert self_check_fields == expected_self_check, (
        f"W-18 v14.3.0 violation: lean_format_spec.self_check.fields drifted — "
        f"missing={sorted(expected_self_check - self_check_fields)}, "
        f"extra={sorted(self_check_fields - expected_self_check)}."
    )

    ac_entry = report_spec["ac_results"]["per_entry"]
    assert set(ac_entry) == {"id", "verdict", "cmd_digest"}, (
        f"W-18 v14.3.0 violation: lean_format_spec.ac_results.per_entry keys "
        f"drifted from {{id, verdict, cmd_digest}}: {sorted(ac_entry)}."
    )
    assert ac_entry["verdict"] == "pass|fail|skip", (
        "W-18 v14.3.0 violation: ac_results verdict enum must stay 'pass|fail|skip' verbatim."
    )

    diff_fields = set(report_spec["diff_stats"]["fields"])
    assert diff_fields == {"files", "insertions", "deletions"}, (
        f"W-18 v14.3.0 violation: lean_format_spec.diff_stats.fields drifted "
        f"from {{files, insertions, deletions}}: {sorted(diff_fields)}."
    )

    # --- (d) behavioral-guidelines Evidence-clause wiring --------------
    bg_text = (
        project_root / "workflow-system/agent/references/behavioral-guidelines.md"
    ).read_text(encoding="utf-8")
    for field in sorted(expected_self_check):
        assert f"**Evidence**: ``self_check.{field}``" in bg_text, (
            f"W-18 v14.3.0 violation: behavioral-guidelines.md missing the "
            f"Evidence clause for self_check.{field}."
        )
    assert "schemas/lean-report.yaml#lean_format_spec.self_check" in bg_text, (
        "W-18 v14.3.0 violation: behavioral-guidelines.md See-Also missing the "
        "lean_format_spec.self_check wiring line."
    )

    # --- (e) message-schemas reference rows + doctrine paragraph -------
    ms_text = (project_root / "workflow-system/agent/references/message-schemas.md").read_text(
        encoding="utf-8"
    )
    for row_fragment in (
        "| `self_check` | NO | v14.3.0 G-002",
        "| `ac_results` | NO | v14.3.0 G-003",
        "| `diff_stats` | NO | v14.3.0 G-003",
    ):
        assert row_fragment in ms_text, (
            f"W-18 v14.3.0 violation: message-schemas.md Field Documentation "
            f"missing the row starting {row_fragment!r}."
        )
    assert "Evidence-only doctrine (v15-ADR-007)" in ms_text, (
        "W-18 v14.3.0 violation: message-schemas.md missing the evidence-only doctrine paragraph."
    )
    assert "reject_subagent_quality_score" in ms_text, (
        "W-18 v14.3.0 violation: message-schemas.md doctrine paragraph must "
        "cite the reject_subagent_quality_score runtime guard."
    )


def test_v14_3_0_hook_runtime_wiring_registered(project_root: Path) -> None:
    """W-18 v14.3.0: the T3 permissive hook wiring (G-001) has coverage.

    Discharges the W-18 precondition for the v14.3.0 CHANGELOG entry on the
    T3 slice (file_write/task_stop runtime wiring per v15-ADR-003 + the
    validate_dispatch AC-v2 structural checks). The stanza pins:

    (a) src/devolaflow/lifecycle/runtime_wiring.py exports exactly the 5
        public symbols (ENV_FLAG, ENV_FLAG_TRUTHY, fire_file_write,
        fire_task_stop, is_workspace_engaged).
    (b) devolaflow.lifecycle re-exports the 3 wiring callables.
    (c) The two production call sites:
        agent_workspace/change.py::_fire_file_write_hook and
        agent_workspace/handoff.py::_fire_task_stop_hook.
    (d) validate_dispatch._collect_ac_v2_violations + the VD005-VD008
        violation-code literals.
    (e) tests/test_hook_runtime_wiring.py exists (the dedicated unit
        suite for the wiring layer).

    Source: .local/research/v14.2.0_gap_analysis.md §2.1 G-001;
    docs/cycle-archive/adr/v15-ADR-003 (permissive hook wiring).
    """
    # --- (a) runtime_wiring public surface ------------------------------
    from devolaflow.lifecycle import runtime_wiring

    expected_symbols = {
        "ENV_FLAG",
        "ENV_FLAG_TRUTHY",
        "fire_file_write",
        "fire_task_stop",
        "is_workspace_engaged",
    }
    assert set(runtime_wiring.__all__) == expected_symbols, (
        f"W-18 v14.3.0 violation: runtime_wiring.__all__ drifted — "
        f"expected {sorted(expected_symbols)}, got {sorted(runtime_wiring.__all__)}."
    )
    assert runtime_wiring.ENV_FLAG == "DEVOLAFLOW_AGENT_WORKSPACE", (
        "W-18 v14.3.0 violation: runtime_wiring must REUSE "
        "DEVOLAFLOW_AGENT_WORKSPACE per W-20 (zero new env flags)."
    )
    assert runtime_wiring.ENV_FLAG_TRUTHY == "1", (
        "W-18 v14.3.0 violation: runtime_wiring R5-strict truthy literal must stay exactly '1'."
    )

    # --- (b) lifecycle package re-exports -------------------------------
    import devolaflow.lifecycle as lifecycle

    for symbol in ("fire_file_write", "fire_task_stop", "is_workspace_engaged"):
        assert symbol in lifecycle.__all__, (
            f"W-18 v14.3.0 violation: devolaflow.lifecycle no longer re-exports {symbol!r}."
        )

    # --- (c) production call sites ---------------------------------------
    change_text = (project_root / "src/devolaflow/agent_workspace/change.py").read_text(
        encoding="utf-8"
    )
    assert "_fire_file_write_hook" in change_text, (
        "W-18 v14.3.0 violation: agent_workspace/change.py lost the "
        "_fire_file_write_hook call site — fire_file_write is unwired."
    )
    handoff_text = (project_root / "src/devolaflow/agent_workspace/handoff.py").read_text(
        encoding="utf-8"
    )
    assert "_fire_task_stop_hook" in handoff_text, (
        "W-18 v14.3.0 violation: agent_workspace/handoff.py lost the "
        "_fire_task_stop_hook call site — fire_task_stop is unwired."
    )

    # --- (d) validate_dispatch AC-v2 structural checks -------------------
    vd_text = (project_root / "src/devolaflow/lifecycle/validate_dispatch.py").read_text(
        encoding="utf-8"
    )
    assert "_collect_ac_v2_violations" in vd_text, (
        "W-18 v14.3.0 violation: validate_dispatch lost "
        "_collect_ac_v2_violations (G-001 AC-v2 structural checks)."
    )
    for code in ("VD005", "VD006", "VD007", "VD008"):
        assert code in vd_text, (
            f"W-18 v14.3.0 violation: validate_dispatch missing the {code} violation-code literal."
        )

    # --- (e) dedicated unit suite ----------------------------------------
    wiring_tests = project_root / "tests/test_hook_runtime_wiring.py"
    assert wiring_tests.is_file(), (
        "W-18 v14.3.0 violation: tests/test_hook_runtime_wiring.py missing — "
        "the wiring layer has no dedicated unit suite."
    )
