"""Explicit-approval and idempotent harness proposal tests."""

from __future__ import annotations

import hashlib
import json
import os
from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from devolaflow.harness.__main__ import main as harness_main
from devolaflow.harness.proposal import (
    ProposalError,
    apply_approved_proposal,
    build_proposal,
    validate_approval,
    write_proposal,
)


def test_build_and_write_proposal_are_exact_immutable_and_bounded(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    evaluation = {
        "schema_version": 1,
        "sampled_at": "2026-08-25T00:00:00+00:00",
        "verdict": "NOT_READY",
        "suggestions": [{"dimension": "performance_impact", "reason": "low headroom"}],
    }
    targets = [
        {
            "path": "meta.summary_trigger_pct",
            "current": 25,
            "value": 30,
            "reason": "reduce predecessor pressure",
        },
        {
            "path": "meta.layer_token_budgets.l0_project",
            "current": 5000,
            "value": 5500,
            "reason": "measured p95 exceeded target",
        },
    ]
    proposal = build_proposal(evaluation, cycle="v16.0.0", targets=targets)

    assert list(proposal) == [
        "schema_version",
        "proposal_id",
        "cycle",
        "generated_at",
        "source_evaluation",
        "targets",
        "apply_mode",
        "status",
    ]
    assert proposal["generated_at"] == evaluation["sampled_at"]
    assert proposal["apply_mode"] == "AUTO_CONFIG"
    assert proposal["status"] == "PROPOSED"
    assert len(proposal["proposal_id"]) == len(proposal["source_evaluation"]) == 64
    assert proposal == build_proposal(evaluation, cycle="v16.0.0", targets=targets)

    destination = tmp_path / "proposal.yaml"
    assert write_proposal(proposal, destination) == destination
    first_bytes = destination.read_bytes()
    os.utime(destination, ns=(1_000_000_000, 1_000_000_000))
    assert write_proposal(proposal, destination) == destination
    assert destination.read_bytes() == first_bytes
    assert destination.stat().st_mtime_ns == 1_000_000_000
    loaded = yaml.safe_load(first_bytes)
    assert set(loaded) == set(proposal)
    assert "APPROVE" not in first_bytes.decode()

    evaluation_path = tmp_path / "evaluation.json"
    targets_path = tmp_path / "targets.yaml"
    cli_output = tmp_path / "cli-proposal.yaml"
    evaluation_path.write_text(json.dumps(evaluation), encoding="utf-8")
    targets_path.write_text(yaml.safe_dump({"targets": targets}), encoding="utf-8")
    assert (
        harness_main(
            [
                "propose",
                "--evaluation",
                str(evaluation_path),
                "--targets",
                str(targets_path),
                "--cycle",
                "v16.0.0",
                "--output",
                str(cli_output),
            ]
        )
        == 0
    )
    assert yaml.safe_load(cli_output.read_text(encoding="utf-8")) == proposal
    assert capsys.readouterr().out == f"harness propose: PROPOSED {cli_output}\n"
    assert not list(tmp_path.glob("*approval*"))

    for change_path in (
        "applicable_rules.constraint_tier",
        "behavioral_guidelines.advisory_fold_models",
        "stage.capacity_per_round",
        "stage.max_rounds",
        "meta.not_allowlisted",
    ):
        change = build_proposal(
            evaluation,
            cycle="v16.0.0",
            targets=[{"path": change_path, "value": 4, "reason": "manual design change"}],
        )
        assert change["apply_mode"] == "CHANGE_REQUIRED"

    invalid_targets = (
        {"path": "meta.layer_token_budgets.l0_project", "value": 0},
        {"path": "meta.layer_token_budgets.l0_project", "value": 8001},
        {"path": "meta.summary_trigger_pct", "value": 101},
        {"path": "meta.recency_decay_factor", "value": 0},
        {"path": "meta.complexity_routing.simple", "value": "turbo"},
        {"path": "meta.summary_trigger_pct", "value": 30, "to": 31},
    )
    for target in invalid_targets:
        with pytest.raises(ProposalError):
            build_proposal(evaluation, cycle="v16.0.0", targets=[target])
    for bad_call in (
        {"evaluation": {}, "cycle": "v16.0.0", "targets": targets},
        {"evaluation": evaluation, "cycle": "", "targets": targets},
        {"evaluation": evaluation, "cycle": "v16.0.0", "targets": []},
        {"evaluation": evaluation, "cycle": "v16.0.0", "targets": [42]},
        {
            "evaluation": evaluation,
            "cycle": "v16.0.0",
            "targets": [{"path": "", "value": 1}],
        },
        {
            "evaluation": evaluation,
            "cycle": "v16.0.0",
            "targets": [
                {"path": "stage.max_rounds", "value": 2},
                {"path": "stage.max_rounds", "value": 3},
            ],
        },
        {
            "evaluation": evaluation,
            "cycle": "v16.0.0",
            "targets": [{"path": "stage.max_rounds", "value": {1, 2}}],
        },
        {
            "evaluation": {"sampled_at": "2026-08-25T00:00:00+00:00", "bad": {1}},
            "cycle": "v16.0.0",
            "targets": [{"path": "stage.max_rounds", "value": 2}],
        },
    ):
        with pytest.raises(ProposalError):
            build_proposal(**bad_call)  # type: ignore[arg-type]
    with pytest.raises(ProposalError, match="ISO-8601"):
        build_proposal(
            evaluation,
            cycle="v16.0.0",
            targets=targets,
            generated_at="not-a-timestamp",
        )

    changed = deepcopy(proposal)
    changed["cycle"] = "v16.1.0"
    with pytest.raises(ProposalError, match="immutable proposal"):
        write_proposal(changed, destination)
    for field, value in (
        ("schema_version", 2),
        ("proposal_id", "bad"),
        ("generated_at", "bad"),
        ("targets", []),
        ("apply_mode", "CHANGE_REQUIRED"),
        ("status", "APPROVE"),
    ):
        malformed = deepcopy(proposal)
        malformed[field] = value
        with pytest.raises(ProposalError):
            write_proposal(malformed, tmp_path / f"bad-{field}.yaml")
    unsorted = deepcopy(proposal)
    unsorted["targets"].reverse()
    with pytest.raises(ProposalError, match="sorted"):
        write_proposal(unsorted, tmp_path / "unsorted.yaml")
    wrong_id = deepcopy(proposal)
    wrong_id["proposal_id"] = "0" * 64
    with pytest.raises(ProposalError, match="does not bind"):
        write_proposal(wrong_id, tmp_path / "wrong-id.yaml")


def test_approved_apply_is_atomic_audited_idempotent_and_drift_safe(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config_path = tmp_path / "workflow-system" / "agent" / "context_profiles.yaml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        yaml.safe_dump(
            {
                "meta": {
                    "budget_hard_cap_tokens": 8000,
                    "layer_token_budgets": {
                        "l0_project": 5000,
                        "l1_wave": 5000,
                        "l2_task": 8000,
                    },
                    "summary_trigger_pct": 25,
                    "recency_decay_factor": 0.9,
                    "complexity_routing": {
                        "simple": "budget",
                        "medium": "balanced",
                        "complex": "quality",
                        "very_complex": "quality",
                    },
                }
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    evaluation = {
        "sampled_at": "2026-08-25T00:00:00+00:00",
        "verdict": "NOT_READY",
    }
    targets = [
        {
            "path": "meta.layer_token_budgets.l0_project",
            "current": 5000,
            "value": 6000,
        },
        {"path": "meta.summary_trigger_pct", "current": 25, "value": 40},
        {"path": "meta.recency_decay_factor", "current": 0.9, "value": 0.75},
        {
            "path": "meta.complexity_routing.simple",
            "current": "budget",
            "value": "inherit",
        },
    ]
    proposal = build_proposal(evaluation, cycle="v16.0.0", targets=targets)
    proposal_path = write_proposal(proposal, tmp_path / ".local/research/proposal.yaml")
    approval = {
        "schema_version": 1,
        "proposal_id": proposal["proposal_id"],
        "proposal_sha256": hashlib.sha256(proposal_path.read_bytes()).hexdigest(),
        "decision": "APPROVE",
        "approved_by": "operator",
        "approved_at": "2026-08-25T00:01:00+00:00",
        "approved_targets": proposal["targets"],
    }
    approval_path = tmp_path / ".local/research/proposal.approval.yaml"
    approval_path.write_text(yaml.safe_dump(approval, sort_keys=False), encoding="utf-8")
    ledger_path = tmp_path / ".local/telemetry/harness.jsonl"
    approval_bytes = approval_path.read_bytes()
    assert validate_approval(proposal_path, approval_path) == approval
    assert approval_path.read_bytes() == approval_bytes

    rejected = deepcopy(approval)
    rejected["decision"] = "REJECT"
    rejected_path = tmp_path / ".local/research/proposal.rejected.yaml"
    rejected_path.write_text(yaml.safe_dump(rejected, sort_keys=False), encoding="utf-8")
    before = config_path.read_bytes()
    with pytest.raises(ProposalError, match="APPROVE"):
        apply_approved_proposal(
            proposal_path,
            rejected_path,
            repo_root=tmp_path,
            config_path=config_path,
            ledger_path=ledger_path,
        )
    assert config_path.read_bytes() == before
    assert not ledger_path.exists()

    invalid_approvals = []
    wrong_hash = deepcopy(approval)
    wrong_hash["proposal_sha256"] = "0" * 64
    invalid_approvals.append(wrong_hash)
    missing_target = deepcopy(approval)
    missing_target["approved_targets"] = []
    invalid_approvals.append(missing_target)
    extra_key = deepcopy(approval)
    extra_key["auto_approve"] = True
    invalid_approvals.append(extra_key)
    wrong_schema = deepcopy(approval)
    wrong_schema["schema_version"] = 2
    invalid_approvals.append(wrong_schema)
    wrong_id = deepcopy(approval)
    wrong_id["proposal_id"] = "0" * 64
    invalid_approvals.append(wrong_id)
    no_operator = deepcopy(approval)
    no_operator["approved_by"] = ""
    invalid_approvals.append(no_operator)
    bad_timestamp = deepcopy(approval)
    bad_timestamp["approved_at"] = "not-a-timestamp"
    invalid_approvals.append(bad_timestamp)
    for invalid in invalid_approvals:
        with pytest.raises(ProposalError):
            validate_approval(proposal, invalid)

    fold_proposal = build_proposal(
        evaluation,
        cycle="v16.0.0",
        targets=[
            {
                "path": "behavioral_guidelines.advisory_fold_models",
                "value": ["quality", "frontier"],
            }
        ],
    )
    fold_path = write_proposal(fold_proposal, tmp_path / "fold.yaml")
    fold_approval = {
        **approval,
        "proposal_id": fold_proposal["proposal_id"],
        "proposal_sha256": hashlib.sha256(fold_path.read_bytes()).hexdigest(),
        "approved_targets": fold_proposal["targets"],
    }
    with pytest.raises(ProposalError, match="model profile"):
        validate_approval(fold_path, fold_approval)
    for profile in (
        {
            "cycle": "v15.0.0",
            "status": "PASS",
            "guard_compliance": 1.0,
            "schema_validity": 1.0,
            "fold_delta": 0.0,
        },
        {
            "cycle": "v16.0.0",
            "status": "FAIL",
            "guard_compliance": 1.0,
            "schema_validity": 1.0,
            "fold_delta": 0.0,
        },
        {
            "cycle": "v16.0.0",
            "status": "PASS",
            "guard_compliance": 0.9,
            "schema_validity": 1.0,
            "fold_delta": 0.0,
        },
        {
            "cycle": "v16.0.0",
            "status": "PASS",
            "guard_compliance": 1.0,
            "schema_validity": 1.0,
            "fold_delta": -0.11,
        },
    ):
        with pytest.raises(ProposalError):
            validate_approval(fold_path, fold_approval, model_profile=profile)
    assert (
        validate_approval(
            fold_path,
            fold_approval,
            model_profile={
                "cycle": "v16.0.0",
                "status": "PASS",
                "guard_compliance": 1.0,
                "schema_validity": 1.0,
                "fold_delta": -0.10,
            },
        )
        == fold_approval
    )
    profile_path = tmp_path / "profile.yaml"
    profile_path.write_text(
        yaml.safe_dump(
            {
                "cycle": "v16.0.0",
                "status": "PASS",
                "guard_compliance": 1.0,
                "schema_validity": 1.0,
                "fold_delta": 0.0,
            }
        ),
        encoding="utf-8",
    )
    assert validate_approval(fold_path, fold_approval, model_profile=profile_path) == fold_approval
    fold_approval_path = tmp_path / "fold.approval.yaml"
    fold_approval_path.write_text(
        yaml.safe_dump(fold_approval, sort_keys=False),
        encoding="utf-8",
    )
    assert (
        harness_main(
            [
                "apply",
                "--proposal",
                str(fold_path),
                "--approval",
                str(fold_approval_path),
                "--repo",
                str(tmp_path),
                "--model",
                str(profile_path),
            ]
        )
        == 1
    )
    capsys.readouterr()

    apply_args = [
        "apply",
        "--proposal",
        str(proposal_path),
        "--approval",
        str(approval_path),
        "--repo",
        str(tmp_path),
        "--config",
        str(config_path),
        "--ledger",
        str(ledger_path),
    ]
    assert harness_main(apply_args) == 0
    assert capsys.readouterr().out == "harness apply: APPLIED\n"
    patched = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert patched["meta"]["layer_token_budgets"]["l0_project"] == 6000
    assert patched["meta"]["summary_trigger_pct"] == 40
    assert patched["meta"]["recency_decay_factor"] == 0.75
    assert patched["meta"]["complexity_routing"]["simple"] == "inherit"
    event = json.loads(ledger_path.read_text(encoding="utf-8"))
    assert set(event) == {
        "schema_version",
        "event",
        "event_id",
        "ts",
        "proposal_id",
        "proposal_ref",
        "approval_ref",
        "proposal_sha256",
        "target_digest",
    }
    assert event["event"] == "proposal_applied"
    assert event["event_id"] == f"proposal_applied:{proposal['proposal_id']}"
    assert event["proposal_ref"] == ".local/research/proposal.yaml"
    assert event["approval_ref"] == ".local/research/proposal.approval.yaml"
    other_config = tmp_path / "other.yaml"
    other_config.write_bytes(config_path.read_bytes())
    with pytest.raises(ProposalError, match="context_profiles"):
        apply_approved_proposal(
            proposal_path,
            approval_path,
            repo_root=tmp_path,
            config_path=other_config,
            ledger_path=ledger_path,
        )
    assert other_config.read_bytes() == config_path.read_bytes()
    config_after = config_path.read_bytes()
    ledger_after = ledger_path.read_bytes()
    relative_apply_args = [
        "apply",
        "--proposal",
        str(proposal_path.relative_to(tmp_path)),
        "--approval",
        str(approval_path.relative_to(tmp_path)),
        "--repo",
        str(tmp_path),
        "--config",
        str(config_path.relative_to(tmp_path)),
        "--ledger",
        str(ledger_path.relative_to(tmp_path)),
    ]
    assert harness_main(relative_apply_args) == 0
    assert capsys.readouterr().out == "harness apply: ALREADY_APPLIED\n"
    assert config_path.read_bytes() == config_after
    assert ledger_path.read_bytes() == ledger_after

    drift_ledger = tmp_path / ".local/telemetry/drift.jsonl"
    collision = deepcopy(event)
    collision["proposal_sha256"] = "0" * 64
    drift_ledger.write_text(json.dumps(collision) + "\n", encoding="utf-8")
    with pytest.raises(ProposalError, match="collision"):
        apply_approved_proposal(
            proposal_path,
            approval_path,
            repo_root=tmp_path,
            config_path=config_path,
            ledger_path=drift_ledger,
        )
    drift_ledger.unlink()
    with pytest.raises(ProposalError, match="drift"):
        apply_approved_proposal(
            proposal_path,
            approval_path,
            repo_root=tmp_path,
            config_path=config_path,
            ledger_path=drift_ledger,
        )
    assert not drift_ledger.exists()

    lock_path = config_path.with_name(f".{config_path.name}.proposal.lock")
    lock_path.write_text("occupied", encoding="utf-8")
    with pytest.raises(ProposalError, match="concurrent"):
        apply_approved_proposal(
            proposal_path,
            approval_path,
            repo_root=tmp_path,
            config_path=config_path,
            ledger_path=drift_ledger,
        )
    lock_path.unlink()

    change = build_proposal(
        evaluation,
        cycle="v16.0.0",
        targets=[{"path": "stage.max_rounds", "value": 8}],
    )
    change_path = write_proposal(change, tmp_path / ".local/research/change.yaml")
    change_approval = {
        **approval,
        "proposal_id": change["proposal_id"],
        "proposal_sha256": hashlib.sha256(change_path.read_bytes()).hexdigest(),
        "approved_targets": change["targets"],
    }
    change_approval_path = tmp_path / ".local/research/change.approval.yaml"
    change_approval_path.write_text(
        yaml.safe_dump(change_approval, sort_keys=False),
        encoding="utf-8",
    )
    before_change_required = config_path.read_bytes()
    assert (
        harness_main(
            [
                "apply",
                "--proposal",
                str(change_path),
                "--approval",
                str(change_approval_path),
                "--repo",
                str(tmp_path),
                "--config",
                str(config_path),
                "--ledger",
                str(drift_ledger),
            ]
        )
        == 1
    )
    assert capsys.readouterr().out == "harness apply: CHANGE_REQUIRED\n"
    assert config_path.read_bytes() == before_change_required
    assert not drift_ledger.exists()
    assert (
        harness_main(
            [
                "apply",
                "--proposal",
                str(tmp_path / "missing.yaml"),
                "--approval",
                str(change_approval_path),
                "--repo",
                str(tmp_path),
            ]
        )
        == 2
    )


# ---------------------------------------------------------------------------
# v17.0.0 R5 (G17-B6 / D-R5-1) — meta.capacity.* AUTO_CONFIG targets.
# ---------------------------------------------------------------------------


def test_capacity_targets_are_auto_config_with_range_validation() -> None:
    """The four meta.capacity paths are allowlisted with owner-module ranges.

    Range validation mirrors the layer_token_budgets precedent but sources
    its bounds from ``harness.capacity.CAPACITY_TARGET_RANGES`` (A-5 — the
    reader and the proposal loop share one table). ``stage.capacity_per_round``
    stays CHANGE_REQUIRED: per-change capacity edits remain human-reviewed.
    """
    from devolaflow.harness.capacity import CAPACITY_TARGET_RANGES

    evaluation = {"sampled_at": "2026-08-25T00:00:00+00:00", "verdict": "NOT_READY"}
    targets = [
        {
            "path": "meta.capacity.round_capacity",
            "value": 4,
            "model_hint": "frontier",
        },
        {"path": "meta.capacity.max_concurrency", "value": 8, "model_hint": "frontier"},
        {"path": "meta.capacity.stop_guard.stagnation_rounds", "value": 3},
        {"path": "meta.capacity.stop_guard.unsuccessful_item_rounds", "value": 4},
    ]
    proposal = build_proposal(evaluation, cycle="v17.0.0", targets=targets)
    assert proposal["apply_mode"] == "AUTO_CONFIG"

    stage_capacity = build_proposal(
        evaluation,
        cycle="v17.0.0",
        targets=[{"path": "stage.capacity_per_round", "value": 4}],
    )
    assert stage_capacity["apply_mode"] == "CHANGE_REQUIRED"

    for path, (lo, hi) in CAPACITY_TARGET_RANGES.items():
        for bad_value in (lo - 1, hi + 1, True, str(hi)):
            with pytest.raises(ProposalError, match=f"integer in \\[{lo}, {hi}\\]"):
                build_proposal(
                    evaluation,
                    cycle="v17.0.0",
                    targets=[{"path": path, "value": bad_value}],
                )


def test_capacity_proposal_apply_roundtrip_patches_declared_block(
    tmp_path: Path,
) -> None:
    """An approved capacity proposal patches a DECLARED meta.capacity block.

    The apply transaction never creates config structure: on a dark config
    (no ``meta.capacity`` block) the same apply fails loudly with the
    existing path-does-not-exist error, preserving the R5 dark-shipping
    contract.
    """
    config_path = tmp_path / "workflow-system" / "agent" / "context_profiles.yaml"
    config_path.parent.mkdir(parents=True)
    dark_config = {"meta": {"budget_hard_cap_tokens": 8000}}
    declared_config = {
        "meta": {
            "budget_hard_cap_tokens": 8000,
            "capacity": {
                "round_capacity": 5,
                "max_concurrency": 4,
                "stop_guard": {"stagnation_rounds": 2, "unsuccessful_item_rounds": 3},
            },
        }
    }
    config_path.write_text(yaml.safe_dump(declared_config, sort_keys=False), encoding="utf-8")

    evaluation = {"sampled_at": "2026-08-25T00:00:00+00:00", "verdict": "NOT_READY"}
    proposal = build_proposal(
        evaluation,
        cycle="v17.0.0",
        targets=[
            {"path": "meta.capacity.max_concurrency", "current": 4, "value": 6},
            {"path": "meta.capacity.round_capacity", "current": 5, "value": 4},
        ],
    )
    proposal_path = write_proposal(proposal, tmp_path / ".local/research/capacity.yaml")
    approval = {
        "schema_version": 1,
        "proposal_id": proposal["proposal_id"],
        "proposal_sha256": hashlib.sha256(proposal_path.read_bytes()).hexdigest(),
        "decision": "APPROVE",
        "approved_by": "operator",
        "approved_at": "2026-08-25T00:01:00+00:00",
        "approved_targets": proposal["targets"],
    }
    approval_path = tmp_path / ".local/research/capacity.approval.yaml"
    approval_path.write_text(yaml.safe_dump(approval, sort_keys=False), encoding="utf-8")
    ledger_path = tmp_path / ".local/telemetry/harness.jsonl"

    status = apply_approved_proposal(
        proposal_path,
        approval_path,
        repo_root=tmp_path,
        config_path=config_path,
        ledger_path=ledger_path,
    )
    assert status == "APPLIED"
    patched = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert patched["meta"]["capacity"]["max_concurrency"] == 6
    assert patched["meta"]["capacity"]["round_capacity"] == 4
    assert patched["meta"]["capacity"]["stop_guard"] == {
        "stagnation_rounds": 2,
        "unsuccessful_item_rounds": 3,
    }
    event = json.loads(ledger_path.read_text(encoding="utf-8"))
    assert event["event"] == "proposal_applied"

    # Dark config → the apply path refuses to create the missing block.
    config_path.write_text(yaml.safe_dump(dark_config, sort_keys=False), encoding="utf-8")
    ledger_path.unlink()
    with pytest.raises(ProposalError, match="does not exist in config"):
        apply_approved_proposal(
            proposal_path,
            approval_path,
            repo_root=tmp_path,
            config_path=config_path,
            ledger_path=ledger_path,
        )
