"""Focused persistence and safety tests for agent-workspace checkpoints."""

from __future__ import annotations

import hashlib
import os
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml

from devolaflow.agent_workspace import (
    CheckpointError,
    checkpoint_round_pass,
    goal_content_hash,
    load_checkpoint,
    write_checkpoint,
)

_FIXTURE = Path(__file__).parent / "fixtures" / "example_checkpoint.yaml"


def _checkpoint() -> dict[str, object]:
    loaded = yaml.safe_load(_FIXTURE.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def _latest_checked_ids(payload: dict[str, object]) -> list[str]:
    convergence = payload["convergence_state"]
    assert isinstance(convergence, dict)
    history = convergence["round_history"]
    assert isinstance(history, list)
    latest = history[-1]
    assert isinstance(latest, dict)
    checked_ids = latest["checked_ids"]
    assert isinstance(checked_ids, list)
    return checked_ids


@pytest.mark.parametrize("checked_ids", [[], ["C-G1.1", "C-G1.2"]])
def test_checkpoint_roundtrip_is_canonical_atomic_and_no_clobber(
    tmp_path: Path,
    checked_ids: list[str],
) -> None:
    payload = _checkpoint()
    _latest_checked_ids(payload)[:] = checked_ids
    original = deepcopy(payload)

    written = write_checkpoint(tmp_path, payload)
    expected = yaml.safe_dump(
        payload,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    ).encode("utf-8")
    latest = written.parent / "checkpoint_latest.yaml"

    assert payload == original
    assert written.read_bytes() == expected
    assert latest.is_symlink()
    assert os.readlink(latest) == written.name
    assert load_checkpoint(tmp_path) == payload
    assert load_checkpoint(tmp_path, payload["metadata"]["checkpoint_id"]) == payload  # type: ignore[index]
    with pytest.raises(CheckpointError, match="refusing overwrite"):
        write_checkpoint(tmp_path, payload)


def _invalid_payload(case: str) -> object:
    payload = _checkpoint()
    metadata = payload["metadata"]
    convergence = payload["convergence_state"]
    assert isinstance(metadata, dict)
    assert isinstance(convergence, dict)
    history = convergence["round_history"]
    assert isinstance(history, list)
    latest = history[-1]
    assert isinstance(latest, dict)

    if case == "not-mapping":
        return []
    if case == "missing-block":
        payload.pop("wave_state")
    elif case == "wrong-block-type":
        payload["quality_snapshot"] = []
    elif case == "unsafe-id":
        metadata["checkpoint_id"] = "cp_../../escape"
    elif case == "missing-convergence":
        payload.pop("convergence_state")
    elif case == "empty-history":
        convergence["round_history"] = []
    elif case == "missing-checked-ids":
        latest.pop("checked_ids")
    elif case == "non-list-checked-ids":
        latest["checked_ids"] = "C-G1.1"
    elif case == "invalid-checked-id":
        latest["checked_ids"] = ["C-G0.1"]
    elif case == "duplicate-checked-id":
        latest["checked_ids"] = ["C-G1.1", "C-G1.1"]
    elif case == "unordered-checked-ids":
        latest["checked_ids"] = ["C-G2.1", "C-G1.2"]
    elif case == "unsafe-yaml":
        payload["extra"] = object()
    elif case == "lossy-yaml":
        payload["extra"] = (1, 2)
    else:  # pragma: no cover - test table owns the case set
        raise AssertionError(case)
    return payload


@pytest.mark.parametrize(
    "case",
    [
        "not-mapping",
        "missing-block",
        "wrong-block-type",
        "unsafe-id",
        "missing-convergence",
        "empty-history",
        "missing-checked-ids",
        "non-list-checked-ids",
        "invalid-checked-id",
        "duplicate-checked-id",
        "unordered-checked-ids",
        "unsafe-yaml",
        "lossy-yaml",
    ],
)
def test_write_rejects_malformed_or_unsafe_checkpoint(tmp_path: Path, case: str) -> None:
    with pytest.raises(CheckpointError):
        write_checkpoint(tmp_path, _invalid_payload(case))  # type: ignore[arg-type]
    assert not list((tmp_path / ".local" / "checkpoints").glob("cp_*.yaml"))


def _arrange_bad_load(root: Path, case: str) -> str | None:
    folder = root / ".local" / "checkpoints"
    folder.mkdir(parents=True)
    latest = folder / "checkpoint_latest.yaml"

    if case == "missing-latest":
        return None
    if case == "regular-latest":
        latest.write_text("not a symlink\n", encoding="utf-8")
        return None
    if case == "absolute-latest":
        latest.symlink_to("/tmp/cp_outside.yaml")
        return None
    if case == "traversing-latest":
        latest.symlink_to("../cp_outside.yaml")
        return None
    if case == "dangling-latest":
        latest.symlink_to("cp_missing.yaml")
        return None
    if case == "unsafe-explicit-id":
        return "../cp_escape"
    if case == "missing-explicit":
        return "cp_missing"
    if case == "malformed-yaml":
        (folder / "cp_malformed.yaml").write_text("metadata: [unterminated\n", encoding="utf-8")
        return "cp_malformed"
    if case == "metadata-mismatch":
        (folder / "cp_other.yaml").write_text(
            yaml.safe_dump(_checkpoint(), sort_keys=False),
            encoding="utf-8",
        )
        return "cp_other"
    if case == "escaping-file-symlink":
        outside = root / "outside.yaml"
        outside.write_text(yaml.safe_dump(_checkpoint(), sort_keys=False), encoding="utf-8")
        (folder / "cp_link.yaml").symlink_to(outside)
        return "cp_link"
    raise AssertionError(case)  # pragma: no cover - test table owns the case set


@pytest.mark.parametrize(
    "case",
    [
        "missing-latest",
        "regular-latest",
        "absolute-latest",
        "traversing-latest",
        "dangling-latest",
        "unsafe-explicit-id",
        "missing-explicit",
        "malformed-yaml",
        "metadata-mismatch",
        "escaping-file-symlink",
    ],
)
def test_load_fails_loudly_for_missing_malformed_or_unsafe_state(
    tmp_path: Path,
    case: str,
) -> None:
    explicit = _arrange_bad_load(tmp_path, case)
    with pytest.raises(CheckpointError):
        load_checkpoint(tmp_path, explicit)


# ── v17.0.0 R4 — round PASS → auto checkpoint (D-R4-2) + goal hash (D-R4-3) ──


@dataclass(frozen=True)
class _StageStub:
    current_round: int = 1
    max_rounds: int = 3


@dataclass(frozen=True)
class _PassStub:
    passed: bool = True


def _arrange_round_pass_workspace(root: Path, *, goal_text: str | None) -> None:
    (root / ".local").mkdir(parents=True)
    (root / ".local" / "project_config.yaml").write_bytes(b"quality:\n  max_rounds: 3\n")
    change_folder = root / ".local" / ".agent" / "active" / "r4-demo"
    change_folder.mkdir(parents=True)
    if goal_text is not None:
        (change_folder / "goal.md").write_text(goal_text, encoding="utf-8")


def test_goal_content_hash_normalizes_newlines_and_missing_file(tmp_path: Path) -> None:
    _arrange_round_pass_workspace(tmp_path, goal_text=None)
    assert goal_content_hash(tmp_path, "r4-demo") == ""

    goal_path = tmp_path / ".local" / ".agent" / "active" / "r4-demo" / "goal.md"
    goal_path.write_bytes(b"# Goal\r\nShip R4.\r")
    crlf_hash = goal_content_hash(tmp_path, "r4-demo")
    normalized_bytes = b"# Goal\nShip R4.\n"
    goal_path.write_bytes(normalized_bytes)
    assert goal_content_hash(tmp_path, "r4-demo") == crlf_hash
    assert crlf_hash == f"sha256:{hashlib.sha256(normalized_bytes).hexdigest()}"

    with pytest.raises(CheckpointError, match="invalid change_id"):
        goal_content_hash(tmp_path, "../escape")


def test_checkpoint_round_pass_composes_valid_resumable_checkpoint(tmp_path: Path) -> None:
    goal_text = "# Goal\nShip the composition API.\n"
    _arrange_round_pass_workspace(tmp_path, goal_text=goal_text)

    result = checkpoint_round_pass(
        tmp_path,
        "r4-demo",
        _PassStub(),
        # Deliberately unordered + duplicated: the API canonicalizes.
        ["C-G1.3", "C-G1.1", "C-G1.3", "C-G2.1"],
        stage_view=_StageStub(current_round=1, max_rounds=3),
        score=90.0,
    )

    assert result.checkpoint_id == "cp_r4-demo_round_1"
    assert result.stage_reference == ".local/checkpoints/cp_r4-demo_round_1.yaml"
    assert result.path == tmp_path / ".local" / "checkpoints" / "cp_r4-demo_round_1.yaml"
    assert result.goal_hash == goal_content_hash(tmp_path, "r4-demo") != ""

    loaded = load_checkpoint(tmp_path)  # latest symlink resolves to it
    metadata = loaded["metadata"]
    assert isinstance(metadata, dict)
    assert metadata["trigger"] == "convergence_round_complete"
    project_state = loaded["project_state"]
    assert isinstance(project_state, dict)
    assert project_state["goal_hash"] == result.goal_hash
    assert project_state["config_hash"].startswith("sha256:")
    assert _latest_checked_ids(loaded) == ["C-G1.1", "C-G1.3", "C-G2.1"]

    # Same round twice → no-clobber (loud, never overwrites).
    with pytest.raises(CheckpointError, match="refusing overwrite"):
        checkpoint_round_pass(
            tmp_path,
            "r4-demo",
            _PassStub(),
            ["C-G1.1"],
            stage_view=_StageStub(current_round=1, max_rounds=3),
        )


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("failed_round", "requires a PASS verdict"),
        ("missing_config", "project config is missing"),
        ("bad_change_id", "invalid change_id"),
        ("round_exceeds_max", "exceeds max_rounds"),
        ("bad_checked_id", "expected C-Gn.m"),
    ],
)
def test_checkpoint_round_pass_rejects_invalid_inputs(
    tmp_path: Path, case: str, message: str
) -> None:
    _arrange_round_pass_workspace(tmp_path, goal_text="# Goal\nR4.\n")
    if case == "missing_config":
        (tmp_path / ".local" / "project_config.yaml").unlink()

    kwargs: dict[str, object] = {
        "pass_result": _PassStub(passed=case != "failed_round"),
        "checked_ids": ["not-an-id"] if case == "bad_checked_id" else ["C-G1.1"],
        "stage_view": _StageStub(current_round=4 if case == "round_exceeds_max" else 1),
    }
    change_id = "Bad_ID" if case == "bad_change_id" else "r4-demo"

    with pytest.raises(CheckpointError, match=message):
        checkpoint_round_pass(
            tmp_path,
            change_id,
            kwargs["pass_result"],
            kwargs["checked_ids"],  # type: ignore[arg-type]
            stage_view=kwargs["stage_view"],
        )
    assert not (tmp_path / ".local" / "checkpoints").exists()
