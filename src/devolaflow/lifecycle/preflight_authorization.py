"""HBP-01 authorization guard for checklist-round execution."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from devolaflow.agent_workspace.preflight import (
    PreflightAuthorizationError,
    _authorization_digest,
    _extract_preflight_sections,
    _frontmatter_shape,
    _parse_authorization_records,
    _parse_stop_cards,
    _validate_permitted_stops,
    _validate_section0,
    _validate_timestamp,
)
from devolaflow.lifecycle.dispatcher import HookViolation

HBP_CODE = "HBP001"

_CHANGE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9.-]*[a-z0-9]$")
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_ACTIVE_ROOT = Path(".local") / ".agent" / "active"


def _canonical_round_change_id(payload: object) -> str | None:
    """Return the active change id only for a canonical bound round payload."""
    if not isinstance(payload, dict):
        return None
    change_context = payload.get("change_context")
    if not isinstance(change_context, dict):
        return None

    checklist_items = change_context.get("checklist_items")
    round_context = change_context.get("round_context")
    if (
        not isinstance(checklist_items, list)
        or not checklist_items
        or not isinstance(round_context, dict)
        or type(round_context.get("round_n")) is not int
        or round_context["round_n"] < 1
    ):
        return None

    change_id = change_context.get("change_id")
    active_folder = change_context.get("active_folder")
    if (
        not isinstance(change_id, str)
        or _CHANGE_ID_RE.fullmatch(change_id) is None
        or active_folder != (_ACTIVE_ROOT / change_id).as_posix()
    ):
        return None
    return change_id


def _blocker(change_id: str, reason: str) -> HookViolation:
    return HookViolation(
        code=HBP_CODE,
        message=(f"HBP-01 blocks checklist execution for change {change_id!r}: {reason}"),
        severity="blocker",
        context={
            "change_id": change_id,
            "preflight": (_ACTIVE_ROOT / change_id / "preflight.md").as_posix(),
        },
    )


def guard_preflight_authorization(repo_root: str | Path, change_id: str) -> None:
    """Raise HBP001 unless the active checklist preflight has a valid signature."""
    if not isinstance(change_id, str) or _CHANGE_ID_RE.fullmatch(change_id) is None:
        raise _blocker(str(change_id), "active change binding is invalid")

    root = Path(repo_root)
    preflight_path = root / _ACTIVE_ROOT / change_id / "preflight.md"
    mirror_path = root / ".local" / "project_config.yaml"
    try:
        preflight_text = preflight_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise _blocker(change_id, "preflight.md is missing or unreadable") from exc

    try:
        frontmatter, sections = _extract_preflight_sections(preflight_text)
        _frontmatter_shape(frontmatter, change_id=change_id)

        authorized_at = frontmatter.get("authorized_at")
        if authorized_at is None:
            raise PreflightAuthorizationError("preflight is unsigned")
        _validate_timestamp(authorized_at, field_name="authorized_at")

        project_config_hash = frontmatter.get("project_config_hash")
        if (
            not isinstance(project_config_hash, str)
            or _HASH_RE.fullmatch(project_config_hash) is None
        ):
            raise PreflightAuthorizationError(
                "signed preflight requires a valid project_config_hash"
            )
        authorization_hash = frontmatter.get("authorization_hash")
        if (
            not isinstance(authorization_hash, str)
            or _HASH_RE.fullmatch(authorization_hash) is None
        ):
            raise PreflightAuthorizationError(
                "signed preflight requires a valid authorization_hash"
            )

        _validate_section0(sections.contents[0], frontmatter)
        cards = _parse_stop_cards(sections.contents[1], checklist_ids=None)
        _parse_authorization_records(
            sections.contents[2],
            cards=cards,
            authorized_at=authorized_at,
        )
        _validate_permitted_stops(sections.contents[3])
    except PreflightAuthorizationError as exc:
        raise _blocker(change_id, str(exc)) from exc

    try:
        mirror_digest = hashlib.sha256(mirror_path.read_bytes()).hexdigest()
    except OSError as exc:
        raise _blocker(
            change_id,
            ".local/project_config.yaml is missing or unreadable",
        ) from exc
    if mirror_digest != project_config_hash:
        raise _blocker(
            change_id,
            "project_config_hash does not match .local/project_config.yaml",
        )
    if authorization_hash != _authorization_digest(frontmatter, sections):
        raise _blocker(
            change_id,
            "authorization_hash does not match signed Sections 0 through 3",
        )


def collect_preflight_authorization_violations(
    payload: dict[str, Any],
    *,
    repo_root: str | Path | None = None,
) -> list[HookViolation]:
    """Collect HBP-01 only for canonical rounds bound to an active change."""
    change_id = _canonical_round_change_id(payload)
    if change_id is None:
        return []
    try:
        guard_preflight_authorization(
            Path.cwd() if repo_root is None else repo_root,
            change_id,
        )
    except HookViolation as violation:
        return [violation]
    return []


__all__ = [
    "HBP_CODE",
    "collect_preflight_authorization_violations",
    "guard_preflight_authorization",
]
