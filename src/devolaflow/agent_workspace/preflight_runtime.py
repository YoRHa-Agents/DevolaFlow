"""Closed-stop evaluation and atomic preflight snapshot refresh."""

from __future__ import annotations

import hashlib
import os
import re
from collections.abc import Sequence
from dataclasses import dataclass
from math import ceil
from pathlib import Path
from typing import Final, Literal

from devolaflow.agent_workspace.preflight import (
    PreflightAuthorizationError,
    _active_checklist_folder,
    _authorization_digest,
    _extract_preflight_sections,
    _frontmatter_shape,
    _parse_authorization_records,
    _parse_stop_cards,
    _stage_adjacent,
    _validate_permitted_stops,
    _validate_section0,
    _validate_timestamp,
)
from devolaflow.agent_workspace.round_parser import (
    RoundArtifactParseError,
    parse_checklist,
    parse_stage,
)

__all__ = [
    "Decision",
    "PreflightRuntimeError",
    "PreflightSnapshot",
    "StopSignal",
    "evaluate_permitted_stops",
    "refresh_preflight_snapshot",
]

_HASH_RE: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")
_CHECKED_RE: Final[re.Pattern[str]] = re.compile(
    r"^- Checked: (\d+)/(\d+) "
    r"\(P0: (\d+)/(\d+), P1: (\d+)/(\d+), P2: (\d+)/(\d+)\)$"
)
_CARDS_RE: Final[re.Pattern[str]] = re.compile(
    r"^- Remaining stop cards: \[(.*)\] \| Reached this round: \[(.*)\]$"
)
_ROUNDS_RE: Final[re.Pattern[str]] = re.compile(r"^- Estimated remaining rounds: (\d+)$")
_BLOCKERS_RE: Final[re.Pattern[str]] = re.compile(r"^- Current blockers: (.+)$")
_SNAPSHOT_HEADING: Final[str] = "## 4. Progress Snapshot"
_PRIORITIES: Final[tuple[str, ...]] = ("P0", "P1", "P2")


class PreflightRuntimeError(RuntimeError):
    """A deterministic failure raised before a runtime artifact mutation."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True)
class StopSignal:
    """Candidate runtime facts evaluated against the closed stop whitelist."""

    reached_card_id: str | None = None
    reached_card_disposition: str | None = None
    current_round: int | None = None
    max_rounds: int | None = None
    net_round_deltas: tuple[int, ...] = ()
    exception_level: str | None = None
    exception_reason: str | None = None
    reopened_reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "net_round_deltas", tuple(self.net_round_deltas))


@dataclass(frozen=True)
class Decision:
    """Immutable whitelist decision; an empty stop set means continue."""

    should_stop: bool
    stop_ids: tuple[str, ...]
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "stop_ids", tuple(self.stop_ids))
        object.__setattr__(self, "reasons", tuple(self.reasons))

    @property
    def action(self) -> Literal["STOP", "CONTINUE"]:
        """Return the direct execution action."""
        return "STOP" if self.should_stop else "CONTINUE"


@dataclass(frozen=True)
class PreflightSnapshot:
    """Immutable, body-derived Section 4 state."""

    snapshot_round: int
    checked: int
    total: int
    priority_counts: tuple[tuple[str, int, int], ...]
    capacity_per_round: int
    reserved_stop_cards: tuple[str, ...]
    remaining_stop_cards: tuple[str, ...]
    reached_cards: tuple[str, ...]
    estimated_remaining_rounds: int
    blockers: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "priority_counts",
            tuple(tuple(counts) for counts in self.priority_counts),
        )
        for field_name in (
            "reserved_stop_cards",
            "remaining_stop_cards",
            "reached_cards",
            "blockers",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))


def evaluate_permitted_stops(signal: StopSignal) -> Decision:
    """Evaluate only STOP-1 through STOP-4; every other signal continues."""
    if not isinstance(signal, StopSignal):
        raise PreflightRuntimeError("INVALID_SIGNAL", "signal must be a StopSignal")

    stop_ids: list[str] = []
    reasons: list[str] = []
    if signal.reached_card_id is not None and signal.reached_card_disposition == "reserved_stop":
        stop_ids.append("STOP-1")
        reasons.append(f"reserved stop card {signal.reached_card_id} was reached")

    max_rounds_reached = (
        type(signal.current_round) is int
        and type(signal.max_rounds) is int
        and signal.max_rounds > 0
        and signal.current_round >= signal.max_rounds
    )
    stagnated = len(signal.net_round_deltas) >= 2 and all(
        type(delta) is int and delta <= 0 for delta in signal.net_round_deltas[-2:]
    )
    if max_rounds_reached or stagnated:
        stop_ids.append("STOP-2")
        reasons.append(
            "max_rounds was reached"
            if max_rounds_reached
            else "net progress stagnated for two rounds"
        )

    rollback_reason = signal.exception_reason or ""
    rollback_data_risk = re.search(
        r"\b(?:state corruption|data loss)\b",
        rollback_reason,
        flags=re.IGNORECASE,
    )
    if signal.exception_level == "FULL_ROLLBACK" and rollback_data_risk is not None:
        stop_ids.append("STOP-3")
        reasons.append("FULL_ROLLBACK reported state corruption or data loss")

    if isinstance(signal.reopened_reason, str) and signal.reopened_reason.strip().startswith(
        "STOP:"
    ):
        stop_ids.append("STOP-4")
        reasons.append("reopened reason starts with the explicit STOP: instruction")

    return Decision(bool(stop_ids), tuple(stop_ids), tuple(reasons))


def _runtime_error(code: str, message: str, exc: Exception | None = None) -> None:
    error = PreflightRuntimeError(code, message)
    if exc is None:
        raise error
    raise error from exc


def _normalize_strings(
    values: Sequence[str],
    *,
    field_name: str,
    allow_empty: bool = True,
) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        _runtime_error("INVALID_INPUT", f"{field_name} must be a sequence of strings")
    normalized = tuple(values)
    if not allow_empty and not normalized:
        _runtime_error("INVALID_INPUT", f"{field_name} must not be empty")
    for value in normalized:
        if (
            not isinstance(value, str)
            or not value
            or value != value.strip()
            or "\n" in value
            or "\r" in value
        ):
            _runtime_error(
                "MULTILINE_INPUT",
                f"{field_name} entries must be non-empty, trimmed, single-line strings",
            )
    if len(normalized) != len(set(normalized)):
        _runtime_error("INVALID_INPUT", f"{field_name} must not contain duplicates")
    return normalized


def _parse_card_list(raw: str, *, field_name: str) -> tuple[str, ...]:
    if not raw:
        return ()
    return _normalize_strings(tuple(raw.split(", ")), field_name=field_name)


def _validate_existing_snapshot(
    content: str,
    *,
    known_cards: frozenset[str],
    reserved_cards: frozenset[str],
) -> None:
    lines = content.splitlines()
    if len(lines) != 4:
        _runtime_error("MALFORMED_PREFLIGHT", "Section 4 must contain exactly four lines")
    checked = _CHECKED_RE.fullmatch(lines[0])
    cards = _CARDS_RE.fullmatch(lines[1])
    rounds = _ROUNDS_RE.fullmatch(lines[2])
    blockers = _BLOCKERS_RE.fullmatch(lines[3])
    if checked is None or cards is None or rounds is None or blockers is None:
        _runtime_error("MALFORMED_PREFLIGHT", "Section 4 does not match canonical syntax")

    values = tuple(int(value) for value in checked.groups())
    total_checked, total, *priority_values = values
    if total_checked > total:
        _runtime_error("MALFORMED_PREFLIGHT", "Section 4 checked count exceeds total")
    priority_pairs = tuple(zip(priority_values[::2], priority_values[1::2], strict=True))
    if any(done > count for done, count in priority_pairs):
        _runtime_error("MALFORMED_PREFLIGHT", "Section 4 priority checked count exceeds total")
    if (
        sum(done for done, _count in priority_pairs) != total_checked
        or sum(count for _done, count in priority_pairs) != total
    ):
        _runtime_error("MALFORMED_PREFLIGHT", "Section 4 priority counts do not sum to totals")

    remaining = _parse_card_list(cards.group(1), field_name="remaining stop cards")
    reached = _parse_card_list(cards.group(2), field_name="reached cards")
    if not set(remaining).issubset(reserved_cards) or not set(reached).issubset(known_cards):
        _runtime_error("UNKNOWN_CARD", "Section 4 references an unknown or non-reserved card")
    blocker_text = blockers.group(1)
    if "\n" in blocker_text or "\r" in blocker_text:
        _runtime_error("MULTILINE_INPUT", "Section 4 blockers must be single-line")


def _load_checklist(path: Path, change_id: str):
    try:
        document = parse_checklist(path.read_text(encoding="utf-8"), filename="checklist.md")
    except (OSError, UnicodeError, RoundArtifactParseError) as exc:
        _runtime_error("MALFORMED_CHECKLIST", "checklist.md is missing or malformed", exc)
    frontmatter = document.artifact.frontmatter
    items = document.items
    item_ids = tuple(item.item_id for item in items)
    counts = {
        priority: sum(item.priority == priority for item in items) for priority in _PRIORITIES
    }
    checked = sum(item.checked for item in items)
    reverted = sum(not item.checked and item.reverted_reason is not None for item in items)
    if (
        frontmatter.get("parent") != change_id
        or frontmatter.get("schema_version") != 1
        or not items
        or len(item_ids) != len(set(item_ids))
        or frontmatter.get("total_items") != len(items)
        or frontmatter.get("checked") != checked
        or frontmatter.get("priority_dist") != counts
        or frontmatter.get("reverted_open") != reverted
    ):
        _runtime_error(
            "MALFORMED_CHECKLIST",
            "checklist.md frontmatter, ids, or body-derived counts are inconsistent",
        )
    return document


def _load_stage(path: Path, change_id: str, checklist_ids: frozenset[str]):
    try:
        document = parse_stage(path.read_text(encoding="utf-8"), filename="stage.md")
    except (OSError, UnicodeError, RoundArtifactParseError) as exc:
        _runtime_error("MALFORMED_STAGE", "stage.md is missing or malformed", exc)
    frontmatter = document.artifact.frontmatter
    referenced_ids = {pick.item_id for pick in document.initial_priorities}
    referenced_ids.update(change.item_id for change in document.priority_changes)
    # v17.0.0 R5 (D-R5-1): the upper bound follows
    # meta.capacity.round_capacity (import at call boundary to avoid the
    # agent_workspace ↔ harness init cycle). Dark config → 5, byte-identical
    # to the pre-R5 literal; the reader validates 1..5 so the bound can
    # never exceed the stage-schema hard cap.
    from devolaflow.harness.capacity import capacity_profile

    if (
        frontmatter.get("parent") != change_id
        or frontmatter.get("schema_version") != 1
        or document.current_round < 0
        or document.max_rounds < 1
        or document.current_round > document.max_rounds
        or not 1 <= document.capacity_per_round <= capacity_profile().round_capacity
        or not referenced_ids.issubset(checklist_ids)
    ):
        _runtime_error(
            "MALFORMED_STAGE",
            "stage.md frontmatter, bounds, or checklist references are inconsistent",
        )
    return document


def _load_signed_preflight(
    preflight_path: Path,
    mirror_path: Path,
    change_id: str,
    checklist_ids: frozenset[str],
) -> tuple[bytes, dict[str, object], object, tuple[object, ...]]:
    try:
        original = preflight_path.read_bytes()
        text = original.decode("utf-8")
        frontmatter, sections = _extract_preflight_sections(text)
        _frontmatter_shape(frontmatter, change_id=change_id)
        authorized_at = frontmatter.get("authorized_at")
        if authorized_at is None:
            raise PreflightAuthorizationError("preflight is unsigned")
        _validate_timestamp(authorized_at, field_name="authorized_at")
        project_hash = frontmatter.get("project_config_hash")
        authorization_hash = frontmatter.get("authorization_hash")
        if not isinstance(project_hash, str) or _HASH_RE.fullmatch(project_hash) is None:
            raise PreflightAuthorizationError("signed preflight has an invalid project hash")
        if (
            not isinstance(authorization_hash, str)
            or _HASH_RE.fullmatch(authorization_hash) is None
        ):
            raise PreflightAuthorizationError("signed preflight has an invalid authorization seal")
        _validate_section0(sections.contents[0], frontmatter)
        cards = _parse_stop_cards(sections.contents[1], checklist_ids=set(checklist_ids))
        _parse_authorization_records(
            sections.contents[2],
            cards=cards,
            authorized_at=authorized_at,
        )
        _validate_permitted_stops(sections.contents[3])
        if authorization_hash != _authorization_digest(frontmatter, sections):
            raise PreflightAuthorizationError("authorization seal does not match Sections 0-3")
        if hashlib.sha256(mirror_path.read_bytes()).hexdigest() != project_hash:
            raise PreflightAuthorizationError(
                "project config mirror does not match its signed hash"
            )
    except (OSError, UnicodeError, PreflightAuthorizationError) as exc:
        _runtime_error("INVALID_SIGNATURE", "preflight.md is not validly signed", exc)
    return original, frontmatter, sections, cards


def _render_snapshot(snapshot: PreflightSnapshot) -> str:
    priority = ", ".join(
        f"{name}: {checked}/{total}" for name, checked, total in snapshot.priority_counts
    )
    remaining = ", ".join(snapshot.remaining_stop_cards)
    reached = ", ".join(snapshot.reached_cards)
    blockers = "none" if not snapshot.blockers else "; ".join(snapshot.blockers)
    return (
        f"- Checked: {snapshot.checked}/{snapshot.total} ({priority})\n"
        f"- Remaining stop cards: [{remaining}] | Reached this round: [{reached}]\n"
        f"- Estimated remaining rounds: {snapshot.estimated_remaining_rounds}\n"
        f"- Current blockers: {blockers}"
    )


def _replace_snapshot_bytes(
    original: bytes,
    *,
    snapshot: PreflightSnapshot,
) -> bytes:
    text = original.decode("utf-8")
    closing = text.find("\n---", 4)
    if closing < 0:
        _runtime_error("MALFORMED_PREFLIGHT", "preflight frontmatter fence is missing")
    frontmatter = text[:closing]
    updated_frontmatter, replacements = re.subn(
        r"(?m)^snapshot_round: [^\n]+$",
        f"snapshot_round: {snapshot.snapshot_round}",
        frontmatter,
    )
    if replacements != 1:
        _runtime_error(
            "MALFORMED_PREFLIGHT",
            "preflight frontmatter must contain one canonical snapshot_round line",
        )
    heading_marker = f"\n{_SNAPSHOT_HEADING}\n"
    heading_index = text.find(heading_marker, closing)
    if heading_index < 0 or text.find(heading_marker, heading_index + 1) >= 0:
        _runtime_error("MALFORMED_PREFLIGHT", "Section 4 heading is missing or duplicated")
    prefix = updated_frontmatter + text[closing : heading_index + len(heading_marker)]
    return f"{prefix}{_render_snapshot(snapshot)}\n".encode()


def refresh_preflight_snapshot(
    repo_root: Path,
    change_id: str,
    *,
    round_num: int | None = None,
    reached_card_ids: Sequence[str] = (),
    blockers: Sequence[str] = (),
) -> PreflightSnapshot:
    """Validate three signed artifacts, then atomically replace only snapshot state."""
    try:
        folder = _active_checklist_folder(Path(repo_root), change_id)
    except PreflightAuthorizationError as exc:
        _runtime_error("INVALID_CHANGE", str(exc), exc)
    checklist = _load_checklist(folder / "checklist.md", change_id)
    checklist_ids = frozenset(item.item_id for item in checklist.items)
    stage = _load_stage(folder / "stage.md", change_id, checklist_ids)
    if round_num is not None and (type(round_num) is not int or round_num != stage.current_round):
        _runtime_error(
            "STALE_ROUND",
            f"requested round {round_num!r} does not equal stage current_round "
            f"{stage.current_round}",
        )

    preflight_path = folder / "preflight.md"
    original, frontmatter, sections, cards = _load_signed_preflight(
        preflight_path,
        Path(repo_root) / ".local" / "project_config.yaml",
        change_id,
        checklist_ids,
    )
    known_cards = frozenset(card.card_id for card in cards)
    reserved_cards = tuple(card.card_id for card in cards if card.disposition == "reserved_stop")
    _validate_existing_snapshot(
        sections.contents[4],
        known_cards=known_cards,
        reserved_cards=frozenset(reserved_cards),
    )
    current_snapshot_round = frontmatter["snapshot_round"]
    assert isinstance(current_snapshot_round, int)
    if current_snapshot_round > stage.current_round:
        _runtime_error(
            "STALE_ROUND",
            "preflight snapshot_round is ahead of stage current_round",
        )

    reached = _normalize_strings(reached_card_ids, field_name="reached_card_ids")
    unknown_cards = set(reached).difference(known_cards)
    if unknown_cards:
        _runtime_error(
            "UNKNOWN_CARD",
            f"reached_card_ids contains unknown cards {sorted(unknown_cards)!r}",
        )
    requested_blockers = _normalize_strings(blockers, field_name="blockers")
    reverted_blockers = tuple(
        f"{item.item_id}: {item.reverted_reason}"
        for item in checklist.items
        if not item.checked and item.reverted_reason is not None
    )
    all_blockers = requested_blockers + tuple(
        blocker for blocker in reverted_blockers if blocker not in requested_blockers
    )

    checked = sum(item.checked for item in checklist.items)
    total = len(checklist.items)
    priority_counts = tuple(
        (
            priority,
            sum(item.checked and item.priority == priority for item in checklist.items),
            sum(item.priority == priority for item in checklist.items),
        )
        for priority in _PRIORITIES
    )
    remaining = tuple(card_id for card_id in reserved_cards if card_id not in reached)
    snapshot = PreflightSnapshot(
        snapshot_round=stage.current_round,
        checked=checked,
        total=total,
        priority_counts=priority_counts,
        capacity_per_round=stage.capacity_per_round,
        reserved_stop_cards=reserved_cards,
        remaining_stop_cards=remaining,
        reached_cards=reached,
        estimated_remaining_rounds=ceil((total - checked) / stage.capacity_per_round),
        blockers=all_blockers,
    )
    updated = _replace_snapshot_bytes(original, snapshot=snapshot)
    if updated == original:
        return snapshot

    temporary: Path | None = None
    try:
        temporary = _stage_adjacent(preflight_path, updated)
        if preflight_path.read_bytes() != original:
            _runtime_error(
                "CONCURRENT_DRIFT",
                "preflight.md changed concurrently before snapshot commit",
            )
        os.replace(temporary, preflight_path)
        temporary = None
    except PreflightRuntimeError:
        raise
    except OSError as exc:
        _runtime_error("SNAPSHOT_WRITE", "snapshot transaction failed", exc)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return snapshot
