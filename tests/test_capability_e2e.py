"""End-to-end capability test for the v9.2.0 DevolaFlow engagement cycle.

Validates the cycle promise: a consumer repo running DevolaFlow v9.2.0
properly engages ``.local/`` + ``.local/.agent/`` + ``.rules/`` surfaces
at L0 session start AND through the dispatch → handoff → archive
lifecycle.

This file is the **headline lint of the v9.2.0 cycle** (per the cycle
plan §"PV-06 — repo-init seed examples + E2E capability test + cycle
rollup"). It crosses every PV's deliverable through a tmp-path repo
fixture and proves the promised composition works:

* PV-01 ``scan_workspace`` discovery API surfaces the 3 first-class
  workspace surfaces correctly.
* PV-02 ``classify_complexity`` + ``activation_verdict`` heuristic
  drives change-folder scaffolding when ``DEVOLAFLOW_AGENT_WORKSPACE=1``
  AND complexity ≥ Standard.
* PV-03 ``auto_write_handoff`` lifecycle hook materialises a handoff
  envelope under ``.local/.agent/handoff/`` when the env-flag is ON AND
  the dispatch carries a populated ``change_context``.
* PV-04 ``memory_router.consult_for_dispatch`` returns ``MemoryCase``
  hits for matching cases (env-flag-gated; same flag as the upstream
  ``MemoryRouter``).
* PV-05 ``ArchiveManager.archive(propose_merge=True)`` computes a merge
  proposal but does NOT auto-apply (A-4 invariant); ``agents_md_slice``
  default-ON visible to dispatch unless ``DEVOLAFLOW_AGENTS_MD_SLICE=0``.
* PV-06 ``install_local(with_examples=True)`` seeds 3 worked-trace
  fixtures so new repos can read the pattern out-of-the-box.

The 10 tests below cover the cycle plan §PV-06 acceptance criteria:

1. ``test_l0_detects_feedbacks_specs_active_changes_via_scan_workspace``
2. ``test_standard_task_auto_opens_change_folder_when_env_flag_on``
3. ``test_standard_task_does_not_open_folder_without_env_flag``
4. ``test_l1_l2_dispatch_writes_handoff_envelope_when_flag_on``
5. ``test_memory_consult_emits_hit_when_prior_case_present``
6. ``test_archive_triggers_source_of_truth_merge_proposal``
7. ``test_artifacts_respect_c9_token_budgets``
8. ``test_install_local_with_examples_seeds_three_artifacts``
9. ``test_install_local_core_mode_skips_examples``
10. ``test_agents_md_slice_default_on_visible_to_dispatch``

All tests are self-contained, use ``tmp_path`` fixtures, never write
outside ``tmp_path``, and either set or delete the relevant env flags
via ``monkeypatch`` so the suite is byte-stable across parallel runs.

Source: v9.2.0 cycle plan §PV-06 — codified per the cycle's headline
e2e contract (closes G-005 / G-006 / G-015 + M-004 / M-007 /
agents_md_slice runtime wiring). NEW test count = 10 (within W-17 ≤ +30
PV-06 cap; cycle cumulative ~93 of 150).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

import devolaflow as _devolaflow_pkg
from devolaflow.agent_workspace.archive import ArchiveManager, ArchiveResult
from devolaflow.agent_workspace.change import Change, ChangeStore
from devolaflow.agent_workspace.lint import (
    ARTIFACT_BUDGETS,
    estimate_tokens,
)
from devolaflow.init_project import (
    _EXAMPLE_CHANGE_ID,
    _EXAMPLE_DOMAIN,
    install_local,
)
from devolaflow.local.workspace import scaffold_local
from devolaflow.memory_router.cache import consult_for_dispatch
from devolaflow.skills.change_activation import (
    activation_verdict,
    classify_complexity,
    from_env,
)
from devolaflow.task_adaptive_selector import select_agents_md_slice
from devolaflow.workspace_context import scan_workspace

# ---------------------------------------------------------------------------
# Fixtures + helpers
# ---------------------------------------------------------------------------


def _today_iso() -> str:
    """ISO date for memory-case fixtures."""
    return datetime.now(UTC).date().isoformat()


def _make_payload(change_id: str, *, from_layer: str = "L1", to_layer: str = "L2") -> dict:
    """Build a minimal valid dispatch payload mirroring v9.1.3 test patterns."""
    return {
        "task": {
            "id": "T-PV06",
            "type": "implement",
            "title": "wire memory consultation into dispatch",
            "description": "implement memory router fast-path consultation for dispatch context",
        },
        "goal": "wire memory consultation into change_context",
        "accept": ["envelope written under .local/.agent/handoff/"],
        "context": {"applicable_rules": {"loading_strategy": "standard"}},
        "change_context": {
            "change_id": change_id,
            "active_folder": f".local/.agent/active/{change_id}",
            "state": "IN_PROGRESS",
            "spec_delta_target": "agent_workspace",
            "owned_files_ref": f".local/.agent/active/{change_id}/owned_files.txt",
            "acceptance_ref": f".local/.agent/active/{change_id}/acceptance.md",
            "from_layer": from_layer,
            "to_layer": to_layer,
        },
    }


def _agent_dir() -> Path:
    """Repository's workflow-system/agent/ directory used for install_local."""
    return Path(__file__).resolve().parent.parent / "workflow-system" / "agent"


# ---------------------------------------------------------------------------
# 1. scan_workspace surfaces feedbacks / specs / active changes
# ---------------------------------------------------------------------------


def test_l0_detects_feedbacks_specs_active_changes_via_scan_workspace(tmp_path: Path) -> None:
    """PV-01 contract — ``scan_workspace`` returns correct presence/counts.

    Given a tmp repo with a ``.local/feedbacks/`` entry, a
    ``.local/memory/specs/<domain>/spec.md``, and an active change folder,
    ``scan_workspace`` returns the populated ``WorkspaceContext`` with all
    three counters > 0. Validates the cycle headline promise that L0 can
    discover the workspace surfaces in a single API call.
    """
    scaffold_local(tmp_path)
    feedback = tmp_path / ".local" / "feedbacks" / "feedback_for_v9.1.5.md"
    feedback.write_text("# feedback fixture", encoding="utf-8")

    spec_dir = tmp_path / ".local" / "memory" / "specs" / "example-domain"
    spec_dir.mkdir(parents=True, exist_ok=True)
    (spec_dir / "spec.md").write_text(
        "---\ndomain: example-domain\nschema_version: 1\n"
        "last_merged_change: null\nlast_merged_at: null\n---\n\n"
        "# Spec: Example-Domain — Source-of-Truth\n",
        encoding="utf-8",
    )

    active = tmp_path / ".local" / ".agent" / "active" / "ex-change"
    active.mkdir(parents=True, exist_ok=True)
    (active / "STATUS.yaml").write_text("state: PROPOSED\n", encoding="utf-8")

    ctx = scan_workspace(tmp_path)

    assert ctx.has_local is True
    assert ctx.has_agent_dir is True
    assert "ex-change" in ctx.active_changes, (
        f"scan_workspace must enumerate active changes; got {ctx.active_changes!r}"
    )
    assert len(ctx.recent_feedbacks) == 1, (
        f"feedback_for_v9.1.5.md MUST be surfaced; got {ctx.recent_feedbacks!r}"
    )
    assert len(ctx.source_of_truth_specs) == 1, (
        f"example-domain/spec.md MUST be surfaced; got {ctx.source_of_truth_specs!r}"
    )


# ---------------------------------------------------------------------------
# 2. + 3. Activation heuristic gates change-folder scaffolding (env-flag based)
# ---------------------------------------------------------------------------


def test_standard_task_auto_opens_change_folder_when_env_flag_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """PV-02 contract — Standard+ complexity + env-flag ON → SHOULD_OPEN_CHANGE.

    Couples the PV-02 ``classify_complexity`` heuristic with the
    ``activation_verdict`` mapper to prove a Standard-tier task routes
    to ``SHOULD_OPEN_CHANGE`` when ``DEVOLAFLOW_AGENT_WORKSPACE=1`` —
    the canonical L0 instruction to scaffold ``.local/.agent/active/<id>/``
    before dispatching the first L1 stage (per Architecture rule A-6).

    The test then materialises the change folder via ``install_local
    (with_examples=True)`` to demonstrate the L0 follow-through is
    feasible (the heuristic fires the verdict; the seed helper gives L0
    a worked-trace fixture to clone).
    """
    monkeypatch.setenv("DEVOLAFLOW_AGENT_WORKSPACE", "1")
    monkeypatch.delenv("DEVOLAFLOW_AGENTS_MD_SLICE", raising=False)

    complexity = classify_complexity(files_count=5, loc_estimate=120)
    assert complexity == "STANDARD", (
        f"5 files / 120 LOC must classify as STANDARD; got {complexity!r}"
    )

    verdict = activation_verdict(complexity, env_agent_workspace=from_env())
    assert verdict == "SHOULD_OPEN_CHANGE", (
        f"STANDARD + env=ON must route to SHOULD_OPEN_CHANGE; got {verdict!r}"
    )

    install_local(_agent_dir(), tmp_path, compile_rules=False, with_examples=True)
    active = tmp_path / ".local" / ".agent" / "active" / _EXAMPLE_CHANGE_ID
    assert active.is_dir(), f"L0 follow-through: with_examples=True MUST scaffold {active}"
    assert (active / "goal.md").is_file()
    assert (active / "STATUS.yaml").is_file()


def test_standard_task_does_not_open_folder_without_env_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R5 strict — env-flag absent → NO_CHANGE regardless of complexity.

    Pins the byte-identical-when-OFF invariant: even a COMPLEX task
    routes to NO_CHANGE when ``DEVOLAFLOW_AGENT_WORKSPACE`` is unset.
    Operators who have not opted into the workspace engagement
    capability see v9.1.4 byte-identical behaviour.
    """
    monkeypatch.delenv("DEVOLAFLOW_AGENT_WORKSPACE", raising=False)

    for complexity_input, expected_tier in (
        ((1, 5, False), "TRIVIAL"),
        ((2, 50, False), "SIMPLE"),
        ((5, 200, False), "STANDARD"),
        ((20, 800, False), "COMPLEX"),
    ):
        complexity = classify_complexity(*complexity_input)
        assert complexity == expected_tier
        verdict = activation_verdict(complexity, env_agent_workspace=from_env())
        assert verdict == "NO_CHANGE", (
            f"R5 strict violation: env=OFF + {complexity!r} must yield NO_CHANGE; got {verdict!r}"
        )

    # And no change folder gets scaffolded under the tmp repo.
    install_local(_agent_dir(), tmp_path, compile_rules=False, with_examples=False)
    active_root = tmp_path / ".local" / ".agent" / "active"
    # The README scaffolding is allowed — but no example change folder.
    assert not (active_root / _EXAMPLE_CHANGE_ID).exists(), (
        "with_examples=False MUST NOT scaffold the example change folder"
    )


# ---------------------------------------------------------------------------
# 4. L1 → L2 dispatch writes a handoff envelope when env-flag is ON
# ---------------------------------------------------------------------------


def test_l1_l2_dispatch_writes_handoff_envelope_when_flag_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """PV-03 G-005 closure — handoff envelope materialises on L1→L2 dispatch.

    Drives ``auto_write_handoff`` directly with a populated
    ``change_context`` payload while ``DEVOLAFLOW_AGENT_WORKSPACE=1`` is
    set; asserts the envelope lands at the canonical
    ``<from>__<to>__<change-id>__<seq>.yaml`` filename with
    ``envelope_kind: TaskDispatch`` and seq=1 (the first L1→L2 hop in
    the change's lifecycle).
    """
    from devolaflow.lifecycle.auto_write_handoff import (
        ENV_FLAG,
        ENV_FLAG_TRUTHY,
        auto_write_handoff,
    )

    monkeypatch.setenv(ENV_FLAG, ENV_FLAG_TRUTHY)
    monkeypatch.chdir(tmp_path)

    change_id = "pv06-e2e-dispatch"
    payload = _make_payload(change_id, from_layer="L1", to_layer="L2")

    result = auto_write_handoff(payload)
    assert result.passed is True, f"hook must pass; violations={result.violations!r}"

    expected = tmp_path / ".local" / ".agent" / "handoff" / f"L1__L2__{change_id}__0001.yaml"
    assert expected.is_file(), f"PV-03 contract violation: L1→L2 dispatch MUST write {expected}"
    body = expected.read_text(encoding="utf-8")
    assert "envelope_kind: TaskDispatch" in body
    assert f"change_id: {change_id}" in body
    assert "from_layer: L1" in body
    assert "to_layer: L2" in body
    assert "seq: 1" in body


# ---------------------------------------------------------------------------
# 5. Memory consult emits ≥ 1 hit when prior case present
# ---------------------------------------------------------------------------


def test_memory_consult_emits_hit_when_prior_case_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """PV-04 contract — ``consult_for_dispatch`` returns hits when index populated.

    Stages a ``.local/memory/cases/index.yaml`` with one matching case,
    sets ``DEVOLAFLOW_MEMORY_ROUTER=1`` (W-20 reuse — the same flag the
    fast-path ``MemoryRouter`` consults), and asserts at least one
    ``MemoryCase`` hit comes back. Validates the v9.1.4 PV-04 advisory
    surface end-to-end.
    """
    monkeypatch.setenv("DEVOLAFLOW_MEMORY_ROUTER", "1")
    monkeypatch.delenv("DEVOLAFLOW_AGENT_WORKSPACE", raising=False)

    cases_dir = tmp_path / ".local" / "memory" / "cases"
    cases_dir.mkdir(parents=True, exist_ok=True)
    case_row = {
        "case_id": "memory-router-fast-path",
        "workflow_type": "feature-implementation",
        "task_type": "implement",
        "summary": "memory router fast-path consultation for dispatch",
        "recipe_path": ".local/memory/cases/memory-router-fast-path.md",
        # Use the live __version__ so the case's version_stamp matches
        # the current `is_version_stale` predicate; this keeps the e2e
        # test resilient across version bumps without a regenerate.
        "version_stamp": _devolaflow_pkg.__version__,
        "ttl_days": 30,
        "last_accessed": _today_iso(),
        "tags": ["memory", "router", "consultation"],
    }
    (cases_dir / "index.yaml").write_text(
        yaml.safe_dump({"last_updated": _today_iso(), "cases": [case_row]}, sort_keys=False),
        encoding="utf-8",
    )

    payload = _make_payload("pv06-memory-consult-hit")
    hits = consult_for_dispatch(payload, tmp_path)

    assert len(hits) >= 1, (
        f"PV-04 contract violation: with a matching case in index.yaml, "
        f"consult_for_dispatch MUST return ≥ 1 hit; got {hits!r}"
    )
    assert hits[0].case_id == "memory-router-fast-path"


# ---------------------------------------------------------------------------
# 6. Archive triggers source-of-truth merge proposal (NOT auto-applied)
# ---------------------------------------------------------------------------


def test_archive_triggers_source_of_truth_merge_proposal(tmp_path: Path) -> None:
    """PV-05 wiring + A-4 invariant — archive computes proposal but does not auto-apply.

    Stages an active change with a verifiable spec.md ADDED Requirement,
    transitions it through PROPOSED → IN_PROGRESS → VERIFYING, then
    archives it with ``propose_merge=True``. Asserts:

    * ``ArchiveResult.proposed_merge`` is populated (i.e. the merge
      machinery ran).
    * The source-of-truth file under ``.local/memory/specs/<domain>/``
      is NOT auto-created (A-4 invariant — the caller must explicitly
      invoke ``apply_merge`` or ``seed_initial_spec``).
    """
    scaffold_local(tmp_path)
    change_id = "pv06-archive-merge"
    active = tmp_path / ".local" / ".agent" / "active" / change_id
    active.mkdir(parents=True, exist_ok=True)

    spec = """\
---
parent: pv06-archive-merge
delta_target: example-merge-target
delta_kind: lite
---

# Operation Spec for pv06-archive-merge

## Purpose
Validate that ArchiveManager.archive(propose_merge=True) computes a
merge proposal but does NOT auto-apply per Architecture rule A-4.

## ADDED Requirements

### Requirement: Archive merge is proposed-only
The system MUST compute a merge proposal at archive time without
mutating the source-of-truth at `.local/memory/specs/<domain>/spec.md`.

#### Scenario: Archive completes with propose_merge=True
- GIVEN a change in VERIFYING state with a populated spec.md
- WHEN ArchiveManager.archive(propose_merge=True) runs
- THEN ArchiveResult.proposed_merge is populated
  AND .local/memory/specs/<delta_target>/spec.md remains absent
"""
    (active / "spec.md").write_text(spec, encoding="utf-8")
    (active / "goal.md").write_text("# Goal\nValidate archive merge proposal.\n", encoding="utf-8")
    (active / "acceptance.md").write_text(
        "# AC\n1. Proposal returned.\n2. Source-of-truth absent post-archive.\n", encoding="utf-8"
    )
    (active / "tasks.md").write_text("# Tasks\n## T1\nDrive archive.\n", encoding="utf-8")
    (active / "owned_files.txt").write_text("src/foo.py\n", encoding="utf-8")
    (active / "STATUS.yaml").write_text(
        "schema_version: 1\n"
        f"change_id: {change_id}\n"
        "state: VERIFYING\n"
        'created: "2026-05-01T00:00:00Z"\n'
        'last_updated: "2026-05-01T00:00:00Z"\n'
        "percent_complete: 100\n"
        "last_handoff_seq: 1\n",
        encoding="utf-8",
    )

    store = ChangeStore(repo_root=tmp_path)
    manager = ArchiveManager(store=store)
    result = manager.archive(
        change_id,
        archive_date="2026-05-01",
        propose_merge=True,
        require_state="VERIFYING",
        auto_regenerate_reports=False,
    )

    assert isinstance(result, ArchiveResult)
    assert result.proposed_merge is not None, (
        "PV-05 wiring violation: archive(propose_merge=True) MUST populate "
        "ArchiveResult.proposed_merge"
    )

    sot_path = tmp_path / ".local" / "memory" / "specs" / "example-merge-target" / "spec.md"
    assert not sot_path.exists(), (
        f"A-4 invariant violation: archive(propose_merge=True) auto-applied to "
        f"{sot_path}; the merge MUST be proposed-only — apply_merge / "
        f"seed_initial_spec are the only legal writers"
    )


# ---------------------------------------------------------------------------
# 7. Artifacts respect C-9 token budgets
# ---------------------------------------------------------------------------


def test_artifacts_respect_c9_token_budgets(tmp_path: Path) -> None:
    """C-9 contract — every example artifact stays within its budget ceiling.

    Drives ``install_local(with_examples=True)`` then checks every
    artifact's estimated token count against ``ARTIFACT_BUDGETS`` from
    ``devolaflow.agent_workspace.lint``. The handoff envelope is checked
    against the design.md §1.1 budget (600 / 1200 — not in
    ARTIFACT_BUDGETS but pinned in the cycle plan §PV-06).
    """
    install_local(_agent_dir(), tmp_path, compile_rules=False, with_examples=True)

    active = tmp_path / ".local" / ".agent" / "active" / _EXAMPLE_CHANGE_ID
    handoff = tmp_path / ".local" / ".agent" / "handoff"
    envelope = handoff / f"L0__L2__{_EXAMPLE_CHANGE_ID}__0001.yaml"

    for filename, (soft, hard) in ARTIFACT_BUDGETS.items():
        target = active / filename
        if not target.exists():
            # README.md is part of the seed but not in ARTIFACT_BUDGETS.
            continue
        observed = estimate_tokens(target.read_text(encoding="utf-8"))
        assert observed <= hard, (
            f"C-9 hard ceiling breach: {filename!r} is {observed} tokens, "
            f"hard ceiling {hard} (soft {soft})"
        )

    assert envelope.is_file(), "envelope MUST be present for budget check"
    envelope_observed = estimate_tokens(envelope.read_text(encoding="utf-8"))
    assert envelope_observed <= 1200, (
        f"design.md §1.1 envelope hard ceiling 1200 breached: observed {envelope_observed} tokens"
    )


# ---------------------------------------------------------------------------
# 8. + 9. install_local --with-examples seeds 3 fixtures; core mode skips
# ---------------------------------------------------------------------------


def test_install_local_with_examples_seeds_three_artifacts(tmp_path: Path) -> None:
    """PV-06 acceptance — ``with_examples=True`` produces 3 fixtures.

    The cycle plan §PV-06 acceptance criterion #1 reads: "``devola-init
    local --with-examples`` produces a populated workspace with 3 example
    artifacts (active folder + handoff envelope + specs file)". This test
    pins each fixture path explicitly.
    """
    install_local(_agent_dir(), tmp_path, compile_rules=False, with_examples=True)

    active = tmp_path / ".local" / ".agent" / "active" / _EXAMPLE_CHANGE_ID
    envelope = (
        tmp_path / ".local" / ".agent" / "handoff" / f"L0__L2__{_EXAMPLE_CHANGE_ID}__0001.yaml"
    )
    spec = tmp_path / ".local" / "memory" / "specs" / _EXAMPLE_DOMAIN / "spec.md"

    assert active.is_dir(), f"PV-06 fixture #1 missing: {active}"
    for required in (
        "goal.md",
        "acceptance.md",
        "spec.md",
        "tasks.md",
        "STATUS.yaml",
        "owned_files.txt",
        "README.md",
    ):
        assert (active / required).is_file(), f"active folder missing {required}"

    assert envelope.is_file(), f"PV-06 fixture #2 missing: {envelope}"
    assert spec.is_file(), f"PV-06 fixture #3 missing: {spec}"

    # The active change folder MUST round-trip cleanly through
    # Change.from_active_folder — i.e. the YAML in STATUS.yaml is valid
    # AND owned_files.txt parses into the seven-line manifest.
    change = Change.from_active_folder(active)
    assert change.change_id == _EXAMPLE_CHANGE_ID
    assert change.state == "PROPOSED"
    assert len(change.owned_files) >= 1, "owned_files.txt should not be empty"


def test_install_local_core_mode_skips_examples(tmp_path: Path) -> None:
    """PV-06 contract — ``with_examples=False`` (core mode) SKIPs seeding.

    Validates the matrix from the cycle plan: "default ON for ``mode:
    full``, OFF for ``mode: core``". Operators who run ``devola-init
    local`` without ``--with-examples`` see the lean scaffolding only —
    no example change folder, no envelope, no example spec.
    """
    install_local(_agent_dir(), tmp_path, compile_rules=False, with_examples=False)

    active = tmp_path / ".local" / ".agent" / "active" / _EXAMPLE_CHANGE_ID
    envelope = (
        tmp_path / ".local" / ".agent" / "handoff" / f"L0__L2__{_EXAMPLE_CHANGE_ID}__0001.yaml"
    )
    spec = tmp_path / ".local" / "memory" / "specs" / _EXAMPLE_DOMAIN / "spec.md"

    assert not active.exists(), (
        f"core-mode violation: {active} MUST NOT be created when with_examples=False"
    )
    assert not envelope.exists(), f"core-mode violation: {envelope} MUST NOT be created"
    assert not spec.exists(), f"core-mode violation: {spec} MUST NOT be created"

    # But the lean scaffolding MUST still be present.
    assert (tmp_path / ".local" / "feedbacks").is_dir()
    assert (tmp_path / ".local" / "memory").is_dir()
    assert (tmp_path / ".local" / ".agent" / "active").is_dir()


# ---------------------------------------------------------------------------
# 10. agents_md_slice default-ON visible to dispatch
# ---------------------------------------------------------------------------


def test_agents_md_slice_default_on_visible_to_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PV-05 contract — default-ON visible to dispatch unless DEVOLAFLOW_AGENTS_MD_SLICE=0.

    The v9.1.5 PV-05 default-ON flip is the cycle's only
    operator-visible behaviour change. This test asserts that

    * Default (env-flag absent) → ``slice_enabled`` is True for a known
      task type ("implement"), so dispatchers see sliced AGENTS.md.
    * ``DEVOLAFLOW_AGENTS_MD_SLICE=0`` set → ``slice_enabled`` is False
      (R5 strict opt-out, byte-stable to v9.1.4).

    Mirrors the v9.1.5 ``test_pv07_agents_md_slice.py`` proofs but
    bundled into the e2e cycle headline so the v9.2.0 promise is
    pinned end-to-end. ``feature`` is one of the canonical task-type
    profile keys in ``context_profiles.yaml#meta.agents_md_slice
    .profiles`` so the slice activates rather than falling through to
    the unmatched-task-type ``fallback: full`` branch.
    """
    # Default path — env-flag UNSET reads YAML default which is enabled=true.
    monkeypatch.delenv("DEVOLAFLOW_AGENTS_MD_SLICE", raising=False)
    default_result = select_agents_md_slice("feature")
    assert default_result["slice_enabled"] is True, (
        f"v9.1.5 PV-05 default-ON regression: env-flag UNSET + 'feature' "
        f"task type MUST yield slice_enabled=True; got "
        f"{default_result['slice_enabled']!r}"
    )

    # Opt-out path — env-flag '0' returns byte-identical full text.
    optout_result = select_agents_md_slice(
        "feature",
        env={"DEVOLAFLOW_AGENTS_MD_SLICE": "0"},
    )
    assert optout_result["slice_enabled"] is False, (
        f"R5 strict opt-out regression: DEVOLAFLOW_AGENTS_MD_SLICE=0 MUST "
        f"yield slice_enabled=False; got {optout_result['slice_enabled']!r}"
    )


__all__ = [
    "test_agents_md_slice_default_on_visible_to_dispatch",
    "test_archive_triggers_source_of_truth_merge_proposal",
    "test_artifacts_respect_c9_token_budgets",
    "test_install_local_core_mode_skips_examples",
    "test_install_local_with_examples_seeds_three_artifacts",
    "test_l0_detects_feedbacks_specs_active_changes_via_scan_workspace",
    "test_l1_l2_dispatch_writes_handoff_envelope_when_flag_on",
    "test_memory_consult_emits_hit_when_prior_case_present",
    "test_standard_task_auto_opens_change_folder_when_env_flag_on",
    "test_standard_task_does_not_open_folder_without_env_flag",
]
