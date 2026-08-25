"""Focused closed-stop and transactional preflight snapshot tests."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

import devolaflow.agent_workspace.preflight_runtime as runtime
from devolaflow.agent_workspace.preflight import (
    PreflightAuthorization,
    draft_preflight_section0,
    sign_preflight,
)
from devolaflow.agent_workspace.preflight_runtime import (
    PreflightRuntimeError,
    StopSignal,
    evaluate_permitted_stops,
    refresh_preflight_snapshot,
)
from devolaflow.skills.slash_commands import scaffold_change_folder

_CHANGE_ID = "preflight-runtime"
_AUTHORIZED_AT = "2026-08-24T12:00:00Z"


def _signed_workspace(root: Path) -> Path:
    draft = draft_preflight_section0(
        root,
        project_name=_CHANGE_ID,
        project_purpose=f"Complete {_CHANGE_ID}",
        seed_mode="feature-enhancement",
    )
    folder = scaffold_change_folder("Preflight Runtime", root, change_id=_CHANGE_ID)
    sign_preflight(
        root,
        _CHANGE_ID,
        draft=draft,
        authorizations=[
            PreflightAuthorization(
                card_id="PF-A1",
                disposition="reserved_stop",
                quote="Stop when the reserved user confirmation is reached.",
            )
        ],
        authorized_at=_AUTHORIZED_AT,
    )
    (folder / "checklist.md").write_text(
        f"""\
---
parent: {_CHANGE_ID}
schema_version: 1
total_items: 3
checked: 1
priority_dist: {{P0: 1, P1: 1, P2: 1}}
reverted_open: 1
---

# Checklist

## G1: Exercise runtime snapshots
- [x] C-G1.1 (P0) The completed assertion has evidence
      verify: manual
      evidence: evidence/C-G1.1.txt | checked_by: user | round: 1 | at: {_AUTHORIZED_AT}
- [ ] C-G1.2 (P1) The normal assertion remains open
      verify: manual
- [ ] C-G1.3 (P2) The reopened assertion remains blocked
      verify: manual
      reverted: Preserve this exact finding | at: {_AUTHORIZED_AT}
""",
        encoding="utf-8",
        newline="\n",
    )
    (folder / "stage.md").write_text(
        f"""\
---
parent: {_CHANGE_ID}
schema_version: 1
current_round: 2
max_rounds: 4
capacity_per_round: 2
---

# Stage — Round Control

## Priority Settings
- {_AUTHORIZED_AT} initial: P0=[C-G1.1] P1=[C-G1.2] P2=[C-G1.3]

## Round History
| Round | Picked | Waves | Result | Blockers | Checkpoint | Gate trend |
|---|---|---|---|---|---|---|

## Next Round Plan
- Candidates: [C-G1.2, C-G1.3]
- Estimated remaining rounds: 1
""",
        encoding="utf-8",
        newline="\n",
    )
    return folder


def test_stop_whitelist_is_exact_and_models_are_frozen() -> None:
    cases = (
        (
            StopSignal(reached_card_id="PF-A1", reached_card_disposition="reserved_stop"),
            ("STOP-1",),
        ),
        (StopSignal(reached_card_id="PF-A1", reached_card_disposition="preauthorized"), ()),
        (StopSignal(current_round=4, max_rounds=4), ("STOP-2",)),
        (StopSignal(net_round_deltas=(2, 0, -1)), ("STOP-2",)),
        (StopSignal(net_round_deltas=(0,)), ()),
        (
            StopSignal(
                exception_level="FULL_ROLLBACK",
                exception_reason="Detected state corruption in checkpoint data.",
            ),
            ("STOP-3",),
        ),
        (
            StopSignal(
                exception_level="HUMAN_INTERVENE",
                exception_reason="Detected data loss.",
            ),
            (),
        ),
        (StopSignal(reopened_reason=" \tSTOP: wait for operator \t"), ("STOP-4",)),
        (StopSignal(reopened_reason="stop: lowercase is ordinary text"), ()),
    )
    for signal, expected in cases:
        decision = evaluate_permitted_stops(signal)
        assert decision.stop_ids == expected
        assert decision.should_stop is bool(expected)
        assert decision.action == ("STOP" if expected else "CONTINUE")

    combined = evaluate_permitted_stops(
        StopSignal(
            reached_card_id="PF-A1",
            reached_card_disposition="reserved_stop",
            current_round=4,
            max_rounds=4,
            exception_level="FULL_ROLLBACK",
            exception_reason="data loss",
            reopened_reason="STOP: halt",
        )
    )
    assert combined.stop_ids == ("STOP-1", "STOP-2", "STOP-3", "STOP-4")
    mutable_deltas = [0, 0]
    copied_signal = StopSignal(net_round_deltas=mutable_deltas)  # type: ignore[arg-type]
    mutable_deltas.append(1)
    assert copied_signal.net_round_deltas == (0, 0)
    with pytest.raises(FrozenInstanceError):
        combined.should_stop = False  # type: ignore[misc]
    with pytest.raises(PreflightRuntimeError, match="INVALID_SIGNAL"):
        evaluate_permitted_stops(object())  # type: ignore[arg-type]


def test_refresh_updates_only_snapshot_and_is_idempotent(tmp_path: Path) -> None:
    folder = _signed_workspace(tmp_path)
    path = folder / "preflight.md"
    before = path.read_bytes()
    sealed_prefix = before.split(b"\n## 4. Progress Snapshot\n", 1)[0]

    snapshot = refresh_preflight_snapshot(
        tmp_path,
        _CHANGE_ID,
        round_num=2,
        reached_card_ids=("PF-A1",),
        blockers=("GATE-7: dependency unavailable",),
    )

    after = path.read_bytes()
    assert (
        after.split(b"\n## 4. Progress Snapshot\n", 1)[0].replace(
            b"snapshot_round: 2",
            b"snapshot_round: 0",
        )
        == sealed_prefix
    )
    assert snapshot.checked == 1 and snapshot.total == 3
    assert snapshot.priority_counts == (("P0", 1, 1), ("P1", 0, 1), ("P2", 0, 1))
    assert snapshot.capacity_per_round == 2
    assert snapshot.reserved_stop_cards == ("PF-A1",)
    assert snapshot.remaining_stop_cards == ()
    assert snapshot.reached_cards == ("PF-A1",)
    assert snapshot.estimated_remaining_rounds == 1
    assert snapshot.blockers == (
        "GATE-7: dependency unavailable",
        "C-G1.3: Preserve this exact finding",
    )
    assert b"authorization_hash:" in after
    assert b"- Checked: 1/3 (P0: 1/1, P1: 0/1, P2: 0/1)" in after

    inode = path.stat().st_ino
    assert (
        refresh_preflight_snapshot(
            tmp_path,
            _CHANGE_ID,
            round_num=2,
            reached_card_ids=("PF-A1",),
            blockers=("GATE-7: dependency unavailable",),
        )
        == snapshot
    )
    assert path.stat().st_ino == inode
    with pytest.raises(FrozenInstanceError):
        snapshot.checked = 2  # type: ignore[misc]


def test_refresh_rejects_invalid_inputs_and_artifacts_before_write(tmp_path: Path) -> None:
    cases = ("unknown", "multiline", "stale", "malformed-stage", "malformed-snapshot")
    for case in cases:
        root = tmp_path / case
        root.mkdir()
        folder = _signed_workspace(root)
        preflight_path = folder / "preflight.md"
        kwargs: dict[str, object] = {"round_num": 2}
        expected_code = {
            "unknown": "UNKNOWN_CARD",
            "multiline": "MULTILINE_INPUT",
            "stale": "STALE_ROUND",
            "malformed-stage": "MALFORMED_STAGE",
            "malformed-snapshot": "MALFORMED_PREFLIGHT",
        }[case]
        if case == "unknown":
            kwargs["reached_card_ids"] = ("PF-X9",)
        elif case == "multiline":
            kwargs["blockers"] = ("line one\nline two",)
        elif case == "stale":
            kwargs["round_num"] = 1
        elif case == "malformed-stage":
            stage_path = folder / "stage.md"
            stage_path.write_text(
                stage_path.read_text(encoding="utf-8").replace(
                    "capacity_per_round: 2",
                    "capacity_per_round: 0",
                ),
                encoding="utf-8",
                newline="\n",
            )
        else:
            preflight_path.write_text(
                preflight_path.read_text(encoding="utf-8").replace(
                    "- Checked: 0/1",
                    "- Checked: malformed",
                ),
                encoding="utf-8",
                newline="\n",
            )
        before = preflight_path.read_bytes()

        with pytest.raises(PreflightRuntimeError) as exc_info:
            refresh_preflight_snapshot(root, _CHANGE_ID, **kwargs)  # type: ignore[arg-type]

        assert exc_info.value.code == expected_code
        assert preflight_path.read_bytes() == before


def test_refresh_detects_concurrent_drift_without_overwrite(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    folder = _signed_workspace(tmp_path)
    path = folder / "preflight.md"
    stage_adjacent = runtime._stage_adjacent

    def inject_drift(target: Path, content: bytes) -> Path:
        temporary = stage_adjacent(target, content)
        target.write_text(
            target.read_text(encoding="utf-8").replace(
                "- Current blockers: PF-A1; preflight authorization pending",
                "- Current blockers: concurrent writer",
            ),
            encoding="utf-8",
            newline="\n",
        )
        return temporary

    monkeypatch.setattr(runtime, "_stage_adjacent", inject_drift)
    with pytest.raises(PreflightRuntimeError) as exc_info:
        refresh_preflight_snapshot(tmp_path, _CHANGE_ID, round_num=2)

    assert exc_info.value.code == "CONCURRENT_DRIFT"
    assert "- Current blockers: concurrent writer" in path.read_text(encoding="utf-8")
    assert not tuple(path.parent.glob(f".{path.name}.*.tmp"))
