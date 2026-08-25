"""Focused HBP-01 loop-start authorization tests."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

from devolaflow.agent_workspace import (
    ChangeNotFoundError,
    PreflightAuthorization,
    draft_preflight_section0,
    sign_preflight,
)
from devolaflow.feedback import ProposalGenerator
from devolaflow.lifecycle import HookViolation, validate_dispatch
from devolaflow.skills.slash_commands import run_apply, scaffold_change_folder

_CHANGE_ID = "hbp-loop"
_AUTHORIZED_AT = "2026-08-24T12:00:00Z"


def _bound_round_payload() -> dict[str, object]:
    return {
        "accept": ["signed preflight permits the selected checklist round"],
        "change_context": {
            "change_id": _CHANGE_ID,
            "active_folder": f".local/.agent/active/{_CHANGE_ID}",
            "checklist_items": [
                {
                    "id": "C-G1.1",
                    "assert": "HBP-01 remains enforced",
                    "verify": "pytest tests/test_preflight_loop_guard.py",
                    "priority": "P1",
                }
            ],
            "round_context": {"round_n": 1, "reverted_ids": []},
        },
    }


def _scaffold(tmp_path: Path, *, signed: bool) -> Path:
    draft = draft_preflight_section0(
        tmp_path,
        project_name=_CHANGE_ID,
        project_purpose=f"Complete {_CHANGE_ID}",
        seed_mode="feature-enhancement",
    )
    folder = scaffold_change_folder("HBP Loop", tmp_path, change_id=_CHANGE_ID)
    if signed:
        sign_preflight(
            tmp_path,
            _CHANGE_ID,
            draft=draft,
            authorizations=[
                PreflightAuthorization(
                    card_id="PF-A1",
                    disposition="reserved_stop",
                    quote="Approved checklist execution",
                )
            ],
            authorized_at=_AUTHORIZED_AT,
        )
    return folder


def _set_frontmatter(path: Path, key: str, value: object) -> None:
    text = path.read_text(encoding="utf-8")
    _prefix, raw_frontmatter, body = text.split("---", 2)
    frontmatter = yaml.safe_load(raw_frontmatter)
    frontmatter[key] = value
    path.write_text(
        "---\n"
        + yaml.safe_dump(frontmatter, sort_keys=False, default_flow_style=False)
        + "---"
        + body,
        encoding="utf-8",
        newline="\n",
    )


@pytest.mark.parametrize(
    "payload",
    [
        {
            "accept": ["legacy active dispatch remains unchanged"],
            "change_context": {
                "change_id": "legacy-change",
                "active_folder": ".local/.agent/active/legacy-change",
                "state": "IN_PROGRESS",
            },
        },
        {"accept": ["free-floating dispatch remains unchanged"]},
        {
            "accept": ["unbound round dispatch remains unchanged"],
            "change_context": {
                "change_id": "unbound-round",
                "checklist_items": [{"id": "C-G1.1"}],
                "round_context": {"round_n": 1},
            },
        },
    ],
    ids=["legacy", "free-floating", "unbound-round"],
)
def test_noncanonical_dispatches_are_zero_io_and_unchanged(
    monkeypatch: pytest.MonkeyPatch,
    payload: dict[str, object],
) -> None:
    before = copy.deepcopy(payload)

    def unexpected_read(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("noncanonical dispatch attempted a filesystem read")

    for method_name in ("read_text", "read_bytes", "exists", "is_dir", "is_file", "open"):
        monkeypatch.setattr(Path, method_name, unexpected_read)

    result = validate_dispatch(payload, strict=True)

    assert result.passed
    assert payload == before


@pytest.mark.parametrize(
    "case",
    [
        "unsigned",
        "invalid-authorized-at",
        "invalid-project-config-hash",
        "invalid-authorization-hash",
        "mirror-drift",
    ],
)
def test_unsigned_or_invalid_preflight_blocks_hooks_and_apply_before_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
) -> None:
    folder = _scaffold(tmp_path, signed=case != "unsigned")
    preflight_path = folder / "preflight.md"
    if case == "invalid-authorized-at":
        _set_frontmatter(preflight_path, "authorized_at", "2026-02-30T12:00:00Z")
    elif case == "invalid-project-config-hash":
        _set_frontmatter(preflight_path, "project_config_hash", "g" * 64)
    elif case == "invalid-authorization-hash":
        _set_frontmatter(preflight_path, "authorization_hash", "0" * 64)
    elif case == "mirror-drift":
        mirror_path = tmp_path / ".local" / "project_config.yaml"
        mirror_path.write_bytes(mirror_path.read_bytes() + b"# drift\n")

    monkeypatch.chdir(tmp_path)
    payload = _bound_round_payload()
    before_payload = copy.deepcopy(payload)
    status_path = folder / "STATUS.yaml"
    before_status = status_path.read_bytes()

    with pytest.raises(HookViolation) as direct:
        validate_dispatch(payload, strict=True)
    assert direct.value.code == "HBP001"
    assert direct.value.severity == "blocker"

    with pytest.raises(HookViolation) as emitted:
        ProposalGenerator().generate_round_dispatch(payload, None, round_num=1)
    assert emitted.value.code == "HBP001"

    with pytest.raises(HookViolation) as applied:
        run_apply(_CHANGE_ID, tmp_path)
    assert applied.value.code == "HBP001"
    assert status_path.read_bytes() == before_status
    assert payload == before_payload

    with pytest.raises(ChangeNotFoundError):
        run_apply("missing-change", tmp_path)


def test_sign_preflight_artifact_passes_strict_hook_and_apply(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _scaffold(tmp_path, signed=True)
    monkeypatch.chdir(tmp_path)
    payload = _bound_round_payload()
    before = copy.deepcopy(payload)

    assert validate_dispatch(payload, strict=True).passed
    assert ProposalGenerator().generate_round_dispatch(payload, None, round_num=1) == before

    change = run_apply(_CHANGE_ID, tmp_path)
    assert change.state == "IN_PROGRESS"
    assert payload == before
