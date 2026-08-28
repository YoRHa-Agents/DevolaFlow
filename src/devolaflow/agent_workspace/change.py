"""Change dataclass + ChangeStore for ``.local/.agent/active/`` artifacts.

Closes C-003 (Python half) per ``.local/research/v8.3.0_gap_analysis.md`` §2.1
and the M-005 Python binding for ``schemas/agent-workspace/change-status.yaml``.

A :class:`Change` is the in-memory representation of a single
``.local/.agent/active/<change-id>/`` folder. Since v17.0.0 the only
supported storage layout is the checklist-anchored ``checklist.md`` +
``stage.md`` + ``preflight.md`` + ``evidence/*.txt`` layout (plus the shared
artifacts and parsed STATUS values). The pre-v16 ``acceptance.md`` +
``tasks.md`` dual-track was removed at its declared ``removal_target``;
loading such a folder raises :exc:`LegacyChangeLayoutError`.

The :class:`ChangeStore` exposes list / get / move semantics on top of
``.local/.agent/active/`` and ``.local/.agent/archive/``. It is the sole
mutator for the FSM ``state`` field in ``STATUS.yaml`` (per
``schemas/agent-workspace/change-status.yaml#state_transitions``).

Round-trip contract (AC-2 of v8.2.5 patch_plan):

* ``Change.from_active_folder(p).to_active_folder(p2)`` produces
  byte-identical files when the source-folder layout is well-formed.
* Frontmatter ordering inside ``STATUS.yaml`` is preserved via
  ``insertion_order`` semantics on ``yaml.safe_dump`` with
  ``sort_keys=False``.
* ``learnings.jsonl`` is an opaque JSONL blob copied verbatim on round-trip
  (parsing belongs to ``learnings.py``).

Public API: :class:`Change` (dataclass mirroring the on-disk artifact set),
:class:`ChangeStore` (list / get / move / transition_state), and the
:exc:`ChangeStoreError` / :exc:`ChangeNotFoundError` /
:exc:`LegacyChangeLayoutError` error types.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Final

import yaml

from devolaflow._durability import (
    DurabilityError,
    durable_move_directory,
    ensure_same_device,
)
from devolaflow._durability import (
    fsync_directory as _fsync_directory,
)

logger = logging.getLogger(__name__)

__all__ = [
    "ACTIVE_DIR_DEFAULT",
    "ARCHIVE_DIR_DEFAULT",
    "ARTIFACT_FILES_V16",
    "ChecklistProgress",
    "Change",
    "ChangeLayout",
    "ChangeNotFoundError",
    "ChangeStore",
    "ChangeStoreError",
    "FSM_STATES",
    "LegacyChangeLayoutError",
    "STATE_TRANSITIONS",
    "derive_checklist_progress",
    "detect_change_layout",
    "reconcile_round_boundary",
]


ACTIVE_DIR_DEFAULT: Final[Path] = Path(".local") / ".agent" / "active"
ARCHIVE_DIR_DEFAULT: Final[Path] = Path(".local") / ".agent" / "archive"

# The checklist-anchored v16 artifact set. ``evidence/*.txt`` is represented
# separately by ``Change.evidence_files`` because its filenames are dynamic.
ARTIFACT_FILES_V16: Final[tuple[str, ...]] = (
    "goal.md",
    "checklist.md",
    "stage.md",
    "preflight.md",
    "spec.md",
    "STATUS.yaml",
    "owned_files.txt",
    "learnings.jsonl",
)

# FSM states + legal transitions — verbatim from
# ``schemas/agent-workspace/change-status.yaml#state_transitions``.
FSM_STATES: Final[tuple[str, ...]] = (
    "PROPOSED",
    "IN_PROGRESS",
    "VERIFYING",
    "ARCHIVED",
    "ESCALATED",
)
STATE_TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    "PROPOSED": frozenset({"IN_PROGRESS"}),
    "IN_PROGRESS": frozenset({"VERIFYING", "ESCALATED"}),
    "VERIFYING": frozenset({"IN_PROGRESS", "ARCHIVED"}),
    "ARCHIVED": frozenset(),
    "ESCALATED": frozenset(),
}

_CHANGE_ID_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9][a-z0-9.-]*[a-z0-9]$")
_DATE_PREFIX_RE: Final[re.Pattern[str]] = re.compile(r"^\d{4}-\d{2}-\d{2}-")
_ISO_UTC_RE: Final[re.Pattern[str]] = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class ChangeStoreError(RuntimeError):
    """Generic error raised by :class:`ChangeStore`.

    Subclassed by more specific errors (e.g. :exc:`ChangeNotFoundError`).
    Keeping a non-trivial superclass simplifies callers that want to
    catch any change-store failure.
    """


class ChangeNotFoundError(ChangeStoreError):
    """Raised when a change-id is not present in active or archive."""


class LegacyChangeLayoutError(ChangeStoreError):
    """Raised when a change folder still uses the removed pre-v16 layout.

    The ``acceptance.md`` + ``tasks.md`` dual-track was deprecated in
    v16.0.0 (``deprecated_since``) and removed at its declared
    ``removal_target`` of v17.0.0. Per S-5 the removed layout is a loud
    error, never a silent current-layout read.
    """


class ChangeLayout(StrEnum):
    """Canonical active/archive folder layouts supported since v17.0.0."""

    CHECKLIST = "CHECKLIST"
    INVALID_MIXED = "INVALID_MIXED"


@dataclass(frozen=True)
class ChecklistProgress:
    """Body-derived checklist counters used by lifecycle guards."""

    total_items: int
    checked: int
    reverted_open: int

    @property
    def percent_complete(self) -> int:
        """Return deterministic integer progress without trusting frontmatter."""

        if not self.total_items:
            return 0
        return self.checked * 100 // self.total_items

    @property
    def ready_for_verifying(self) -> bool:
        """Whether the parsed checklist body permits VERIFYING."""

        return self.total_items > 0 and self.checked == self.total_items and self.reverted_open == 0


def derive_checklist_progress(checklist_md: str) -> ChecklistProgress:
    """Derive lifecycle counters from parsed item bodies, never frontmatter."""

    from devolaflow.agent_workspace.round_parser import parse_checklist

    document = parse_checklist(checklist_md)
    return ChecklistProgress(
        total_items=len(document.items),
        checked=sum(item.checked for item in document.items),
        reverted_open=sum(
            not item.checked and item.reverted_reason is not None for item in document.items
        ),
    )


def detect_change_layout(folder: Path | str) -> ChangeLayout:
    """Detect a change folder's canonical storage layout without mutating it.

    Presence of ``checklist.md`` together with ``tasks.md`` or
    ``acceptance.md`` is an invalid mixed layout. Legacy markers without
    ``checklist.md`` raise :exc:`LegacyChangeLayoutError` (the pre-v16
    layout was removed in v17.0.0). Everything else — including folders
    that have not written ``checklist.md`` yet — is the checklist layout.
    """

    folder_path = Path(folder)
    if not folder_path.is_dir():
        raise ChangeNotFoundError(
            f"change folder {folder_path!s} does not exist or is not a directory"
        )

    has_checklist = (folder_path / "checklist.md").exists()
    has_legacy = any((folder_path / name).exists() for name in ("tasks.md", "acceptance.md"))
    if has_checklist and has_legacy:
        return ChangeLayout.INVALID_MIXED
    if has_legacy:
        raise LegacyChangeLayoutError(
            f"change folder {folder_path!s} uses the removed legacy layout: "
            "tasks.md/acceptance.md dual-track removed in v17.0.0; migrate to "
            "checklist.md (see schemas/agent-workspace/change-checklist.yaml)"
        )
    return ChangeLayout.CHECKLIST


@dataclass
class Change:
    """In-memory representation of one ``.local/.agent/active/<id>/`` folder.

    Artifact attributes hold verbatim on-disk text for the checklist
    layout. The ``status`` attribute carries the parsed ``STATUS.yaml``
    mapping.

    ``Change.from_active_folder(path)`` is the canonical constructor;
    direct dataclass instantiation is reserved for tests.
    """

    change_id: str
    goal_md: str = ""
    spec_md: str = ""
    status: dict = field(default_factory=dict)
    owned_files: list[str] = field(default_factory=list)
    learnings_jsonl: str | None = None
    # Source folder — populated by from_active_folder; useful for diagnostics.
    source_folder: Path | None = None
    layout: ChangeLayout = ChangeLayout.CHECKLIST
    checklist_md: str = ""
    stage_md: str = ""
    preflight_md: str = ""
    evidence_files: dict[str, str] = field(default_factory=dict)
    # Agent onboarding entry point (v17.2.0). Empty string means the source
    # folder lacked the file; ``to_active_folder`` backfills the scaffold.
    entrance_md: str = ""

    @property
    def state(self) -> str:
        """Convenience accessor for ``status['state']`` (raises KeyError if absent)."""
        return str(self.status["state"])

    @property
    def percent_complete(self) -> int:
        """Convenience accessor for ``status['percent_complete']``."""
        return int(self.status.get("percent_complete", 0))

    @property
    def last_handoff_seq(self) -> int:
        """Convenience accessor for ``status['last_handoff_seq']`` (default 0)."""
        return int(self.status.get("last_handoff_seq", 0))

    @property
    def last_handoff_summary(self) -> dict | None:
        """Optional accessor for ``status['last_handoff_summary']`` (v10.7.0 D-P-3).

        Returns the dict-shaped most-recent-handoff diagnostic snapshot
        (``{from_layer, to_layer, ts, seq}``) when populated by upstream
        write-back (e.g. ``HandoffStore.write_envelope`` future hook), or
        ``None`` for v8.3.0..v10.6.x STATUS.yaml files that pre-date the
        D-P-3 NEST demo. Treats explicit-null and absent identically per
        the schema's nullable contract.
        """
        raw = self.status.get("last_handoff_summary")
        if not isinstance(raw, dict):
            return None
        return raw

    @classmethod
    def from_active_folder(cls, folder: Path | str) -> Change:
        """Load a :class:`Change` from an active-change folder.

        ``folder`` MUST be either the actual active folder
        (``.../active/<id>/``) OR an archive folder
        (``.../archive/<YYYY-MM-DD>-<id>/``) — both layouts share the same
        artifact set. The change-id is derived from the folder basename
        (date prefix stripped for archive folders).

        Raises:
          ChangeNotFoundError: when ``folder`` does not exist.
          ChangeStoreError: when STATUS.yaml is malformed (loud per S-5).
        """
        folder_path = Path(folder)
        layout = detect_change_layout(folder_path)
        if layout is ChangeLayout.INVALID_MIXED:
            raise ChangeStoreError(
                f"change folder {folder_path!s} has INVALID_MIXED layout: "
                "checklist.md cannot coexist with tasks.md or acceptance.md"
            )

        change_id = _derive_change_id(folder_path.name)

        def _read(name: str) -> str:
            path = folder_path / name
            if not path.exists():
                return ""
            return path.read_text(encoding="utf-8")

        status_text = _read("STATUS.yaml")
        if not status_text.strip():
            raise ChangeStoreError(
                f"STATUS.yaml is missing or empty in {folder_path!s}; "
                "every active change folder MUST carry a populated STATUS.yaml "
                "(see schemas/agent-workspace/change-status.yaml)"
            )
        status_data = yaml.safe_load(status_text)
        if not isinstance(status_data, dict):
            raise ChangeStoreError(
                f"STATUS.yaml in {folder_path!s} did not parse as a YAML mapping "
                f"(got {type(status_data).__name__})"
            )

        owned_files_text = _read("owned_files.txt")
        owned_files = [line for line in owned_files_text.splitlines() if line.strip()]

        learnings_path = folder_path / "learnings.jsonl"
        learnings_jsonl = (
            learnings_path.read_text(encoding="utf-8") if learnings_path.exists() else None
        )

        evidence_files: dict[str, str] = {}
        evidence_dir = folder_path / "evidence"
        if evidence_dir.is_dir():
            evidence_files = {
                evidence_path.name: evidence_path.read_text(encoding="utf-8")
                for evidence_path in sorted(evidence_dir.glob("*.txt"))
                if evidence_path.is_file()
            }

        return cls(
            change_id=change_id,
            goal_md=_read("goal.md"),
            spec_md=_read("spec.md"),
            status=status_data,
            owned_files=owned_files,
            learnings_jsonl=learnings_jsonl,
            source_folder=folder_path,
            layout=layout,
            checklist_md=_read("checklist.md"),
            stage_md=_read("stage.md"),
            preflight_md=_read("preflight.md"),
            evidence_files=evidence_files,
            entrance_md=_read("entrance.md"),
        )

    def to_active_folder(self, folder: Path | str) -> None:
        """Write this :class:`Change` to ``folder`` (creating it if absent).

        Existing files in the checklist layout are overwritten. A non-empty
        target with mixed legacy markers is rejected rather than cleaned or
        migrated. Only the canonical artifact set
        (:data:`ARTIFACT_FILES_V16`) is written.

        Round-trip contract (AC-2): when the source was loaded via
        :meth:`from_active_folder`, the output is byte-identical to the
        source — modulo:

        * ``STATUS.yaml`` re-rendered via ``yaml.safe_dump(sort_keys=False)``
          (preserves insertion order — the canonical ordering matches the
          schema's ``instance_top_level_required`` list).
        * ``owned_files.txt`` re-rendered with the strict LF-only newline
          contract from ``schemas/agent-workspace/owned-files.yaml``.
        * Empty / absent ``learnings.jsonl`` is NOT written (the schema
          treats it as opt-in).
        * A source folder WITHOUT ``entrance.md`` gains one on write: the
          onboarding router is backfilled from the scaffold template
          (design D-4 backfill; v20.0.x fix).
        """
        folder_path = Path(folder)
        layout = ChangeLayout(self.layout)
        if layout is ChangeLayout.INVALID_MIXED:
            raise ChangeStoreError("cannot write a Change with INVALID_MIXED layout")
        if folder_path.exists() and not folder_path.is_dir():
            raise ChangeStoreError(f"change target {folder_path!s} exists and is not a directory")
        if folder_path.is_dir() and any(folder_path.iterdir()):
            # Raises LegacyChangeLayoutError for a legacy-marker target —
            # refusing to clean or migrate a removed layout implicitly.
            target_layout = detect_change_layout(folder_path)
            if target_layout is ChangeLayout.INVALID_MIXED:
                raise ChangeStoreError(
                    f"change target {folder_path!s} has INVALID_MIXED layout; "
                    "refusing to clean or migrate it implicitly"
                )

        evidence_items: list[tuple[str, str]] = []
        for basename, text in self.evidence_files.items():
            evidence_name = Path(basename)
            if evidence_name.name != basename or evidence_name.suffix != ".txt":
                raise ChangeStoreError(f"evidence filename {basename!r} must be a .txt basename")
            evidence_items.append((basename, text))

        folder_path.mkdir(parents=True, exist_ok=True)

        def _write(name: str, text: str, *, newline: str | None = None) -> None:
            """Write one artifact through the hooked write surface (ADR-003).

            Fires the ``file_write`` lifecycle hook BEFORE the write (see
            :func:`_fire_file_write_hook`), then performs the exact
            pre-v14.3.0 ``Path.write_text`` call.
            """
            target = folder_path / name
            _fire_file_write_hook(target, self.owned_files, folder_path)
            if newline is None:
                target.write_text(text, encoding="utf-8")
            else:
                target.write_text(text, encoding="utf-8", newline=newline)

        from devolaflow.agent_workspace.entrance import derive_goal_title, render_entrance_md

        _write("goal.md", self.goal_md)
        _write("checklist.md", self.checklist_md)
        _write("stage.md", self.stage_md)
        _write("preflight.md", self.preflight_md)
        _write("spec.md", self.spec_md)
        # A loaded entrance round-trips verbatim; an absent one is backfilled
        # from the scaffold template (design D-4).
        entrance_text = self.entrance_md or render_entrance_md(
            self.change_id,
            derive_goal_title(self.goal_md, self.change_id),
        )
        _write("entrance.md", entrance_text)

        status_yaml = yaml.safe_dump(
            self.status,
            sort_keys=False,
            default_flow_style=False,
            allow_unicode=True,
        )
        _write("STATUS.yaml", status_yaml)

        owned_text = "\n".join(self.owned_files)
        if owned_text and not owned_text.endswith("\n"):
            owned_text += "\n"
        _write("owned_files.txt", owned_text, newline="\n")

        evidence_dir = folder_path / "evidence"
        evidence_dir.mkdir(parents=True, exist_ok=True)
        for basename, text in evidence_items:
            _write(str(Path("evidence") / basename), text)

        if self.learnings_jsonl is not None:
            _write("learnings.jsonl", self.learnings_jsonl, newline="\n")

    def with_state(self, new_state: str) -> Change:
        """Return a copy with ``status['state']`` updated; refreshes ``last_updated``.

        The transition matrix is enforced (``ChangeStoreError`` raised when
        the requested transition is illegal per
        :data:`STATE_TRANSITIONS`).
        """
        if new_state not in FSM_STATES:
            raise ChangeStoreError(f"unknown state {new_state!r}; expected one of {FSM_STATES}")
        current_state = str(self.status.get("state", "PROPOSED"))
        allowed = STATE_TRANSITIONS.get(current_state, frozenset())
        if new_state not in allowed and new_state != current_state:
            raise ChangeStoreError(
                f"illegal state transition {current_state!r} → {new_state!r}; "
                f"allowed: {sorted(allowed) if allowed else '<terminal>'}"
            )
        new_status = dict(self.status)
        new_status["state"] = new_state
        new_status["last_updated"] = _now_iso()
        return Change(
            change_id=self.change_id,
            goal_md=self.goal_md,
            spec_md=self.spec_md,
            status=new_status,
            owned_files=list(self.owned_files),
            learnings_jsonl=self.learnings_jsonl,
            source_folder=self.source_folder,
            layout=self.layout,
            checklist_md=self.checklist_md,
            stage_md=self.stage_md,
            preflight_md=self.preflight_md,
            evidence_files=dict(self.evidence_files),
            entrance_md=self.entrance_md,
        )


def reconcile_round_boundary(
    change: Change,
    *,
    at: str | None = None,
) -> Change:
    """Return a checklist change with body-derived STATUS counters reconciled.

    The helper is side-effect free. An open user revert demotes VERIFYING to
    IN_PROGRESS. The pinned ``## Progress`` header inside ``checklist.md`` is
    re-aligned with the derived done/doing/todo state (the sole checklist
    mutation); stage artifacts and prior round history remain byte-identical.
    """

    if change.layout is not ChangeLayout.CHECKLIST:
        return change
    timestamp = at or _now_iso()
    if _ISO_UTC_RE.fullmatch(timestamp) is None:
        raise ChangeStoreError(
            f"round-boundary timestamp must use YYYY-MM-DDTHH:MM:SSZ; got {timestamp!r}"
        )

    from devolaflow.agent_workspace.progress import refresh_progress_header
    from devolaflow.agent_workspace.round_parser import parse_stage

    try:
        progress = derive_checklist_progress(change.checklist_md)
        stage = parse_stage(change.stage_md)
        checklist_md = refresh_progress_header(change.checklist_md, change.stage_md)
    except ValueError as exc:
        raise ChangeStoreError(
            f"cannot reconcile checklist round boundary for {change.change_id!r}: {exc}"
        ) from exc
    if progress.total_items == 0:
        raise ChangeStoreError(
            f"cannot reconcile checklist round boundary for {change.change_id!r}: "
            "parsed checklist body contains no items"
        )

    new_status = dict(change.status)
    new_status["checklist_checked"] = progress.checked
    new_status["checklist_total"] = progress.total_items
    new_status["percent_complete"] = progress.percent_complete
    new_status["current_round"] = stage.current_round
    if change.state == "VERIFYING" and progress.reverted_open:
        new_status["state"] = "IN_PROGRESS"
        new_status["gate_score"] = None
        new_status["verify_pass"] = None
    new_status["last_updated"] = timestamp
    return replace(change, status=new_status, checklist_md=checklist_md)


def _fire_file_write_hook(
    target: Path,
    owned_files: list[str],
    change_folder: Path,
) -> None:
    """Fire the ``file_write`` lifecycle hook for one artifact write.

    Production call site for
    :func:`devolaflow.lifecycle.runtime_wiring.fire_file_write` per ADR-003:
    ``Change.to_active_folder`` IS the framework's change-driven write
    surface, so every artifact write runs through the hook BEFORE touching
    disk. STRICT by default since v15.0.0 (G-038 graduation): an S-8
    ownership violation raises :class:`HookViolation` and blocks the write;
    ``strict=False`` is the adapter's explicit opt-out (S-8 "mode: lite").
    Byte-identical zero-IO no-op when ``DEVOLAFLOW_AGENT_WORKSPACE`` != "1"
    (W-20 flag reuse). Per the S-5 isolation pattern
    (``feedback_emit.ProposalEmitter._fire_hook_chain``), a buggy handler —
    any exception other than :class:`HookViolation` — is logged at WARNING
    and the write proceeds. The lazy import keeps the no-cycle property
    between ``agent_workspace`` and ``lifecycle``.
    """
    from devolaflow.lifecycle.dispatcher import HookViolation
    from devolaflow.lifecycle.runtime_wiring import fire_file_write

    try:
        fire_file_write(
            target,
            owned_files=owned_files,
            change_folder=change_folder,
        )
    except HookViolation:
        # v15.0.0 strict graduation: S-8 "mode: full" — block + escalate.
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "file_write hook raised %s for %s; write proceeds unchanged "
            "(S-5 isolation for non-violation hook bugs per ADR-003)",
            exc,
            target,
        )


def _now_iso() -> str:
    """ISO-8601 UTC timestamp with seconds precision (matches schema patterns)."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _derive_change_id(basename: str) -> str:
    """Strip a ``YYYY-MM-DD-`` prefix if present; verify against schema regex.

    Both active folders (``add-dark-mode``) and archive folders
    (``2026-04-22-add-dark-mode``) are supported. The pattern matches the
    ``schemas/agent-workspace/change-status.yaml#fields.change_id.pattern``.
    """
    candidate = basename
    if _DATE_PREFIX_RE.match(candidate):
        candidate = candidate[len("YYYY-MM-DD-") :]
    if not _CHANGE_ID_RE.match(candidate):
        raise ChangeStoreError(
            f"derived change-id {candidate!r} (from folder {basename!r}) does not "
            f"match the lowercase-kebab-case pattern from change-status.yaml "
            f"(^[a-z0-9][a-z0-9.-]*[a-z0-9]$)"
        )
    return candidate


@dataclass
class ChangeStore:
    """List / get / move semantics over ``.local/.agent/active|archive/``.

    The store keeps no in-memory cache — every operation re-reads the
    filesystem. This matches the v8.3.0 design's "no shared state" mandate
    (P5 — Artifacts as Contracts) and avoids stale-cache bugs when
    multiple agents touch the workspace concurrently.

    Attributes:
      repo_root: Repo root used to resolve the default ``active``/``archive``
        directories. Defaults to ``Path.cwd()``.
      active_dir: Override for the active folder root (relative to
        ``repo_root``). Defaults to ``.local/.agent/active``.
      archive_dir: Override for the archive folder root. Defaults to
        ``.local/.agent/archive``.
    """

    repo_root: Path = field(default_factory=Path.cwd)
    active_dir: Path = field(default_factory=lambda: Path(ACTIVE_DIR_DEFAULT))
    archive_dir: Path = field(default_factory=lambda: Path(ARCHIVE_DIR_DEFAULT))

    @property
    def active_root(self) -> Path:
        """Absolute (or repo-rooted) path to the active folder root."""
        return self._resolve(self.active_dir)

    @property
    def archive_root(self) -> Path:
        """Absolute (or repo-rooted) path to the archive folder root."""
        return self._resolve(self.archive_dir)

    def _resolve(self, p: Path) -> Path:
        return p if p.is_absolute() else self.repo_root / p

    def _get_active(self, change_id: str) -> tuple[Change, Path]:
        target = self.active_root / change_id
        if not target.is_dir():
            raise ChangeStoreError(
                f"operation requires an ACTIVE change; {change_id!r} is absent "
                f"from {self.active_root!s}"
            )
        return Change.from_active_folder(target), target

    @staticmethod
    def _write_artifact(change: Change, folder: Path, filename: str, text: str) -> None:
        target = folder / filename
        _fire_file_write_hook(target, change.owned_files, folder)
        target.write_text(text, encoding="utf-8")

    def _write_status(self, change: Change, folder: Path) -> None:
        status_yaml = yaml.safe_dump(
            change.status,
            sort_keys=False,
            default_flow_style=False,
            allow_unicode=True,
        )
        self._write_artifact(change, folder, "STATUS.yaml", status_yaml)

    def list_active(self) -> list[str]:
        """Return change-ids of every folder under ``active_root``.

        Sorted alphabetically. Folders that do not match the change-id
        pattern are SKIPPED (defensive — some FS may sprinkle ``.gitkeep``
        / ``.DS_Store`` etc.). Loud only on STATUS.yaml load (in
        :meth:`get`); listing is silent on malformed names.
        """
        root = self.active_root
        if not root.is_dir():
            return []
        ids: list[str] = []
        for child in sorted(root.iterdir()):
            if not child.is_dir():
                continue
            try:
                ids.append(_derive_change_id(child.name))
            except ChangeStoreError:
                continue
        return ids

    def list_archive(self) -> list[tuple[str, str]]:
        """Return ``(date_prefix, change_id)`` pairs for archived changes.

        Sorted by ``date_prefix`` ascending then ``change_id`` ascending.
        ``date_prefix`` is the literal ``YYYY-MM-DD`` (``""`` if the folder
        does not carry a date prefix, which should only happen in tests).
        """
        root = self.archive_root
        if not root.is_dir():
            return []
        rows: list[tuple[str, str]] = []
        for child in sorted(root.iterdir()):
            if not child.is_dir():
                continue
            name = child.name
            if _DATE_PREFIX_RE.match(name):
                date_prefix = name[: len("YYYY-MM-DD")]
                try:
                    cid = _derive_change_id(name)
                except ChangeStoreError:
                    continue
            else:
                date_prefix = ""
                try:
                    cid = _derive_change_id(name)
                except ChangeStoreError:
                    continue
            rows.append((date_prefix, cid))
        rows.sort()
        return rows

    def get(self, change_id: str) -> Change:
        """Load a change by id (active first, then archive).

        Raises:
          ChangeNotFoundError: when ``change_id`` is in neither tree.
        """
        active_path = self.active_root / change_id
        if active_path.is_dir():
            return Change.from_active_folder(active_path)
        # Archive: linear scan since the date prefix is unknown.
        for child in self.archive_root.iterdir() if self.archive_root.is_dir() else []:
            if not child.is_dir():
                continue
            try:
                cid = _derive_change_id(child.name)
            except ChangeStoreError:
                continue
            if cid == change_id:
                return Change.from_active_folder(child)
        raise ChangeNotFoundError(
            f"change {change_id!r} not found under {self.active_root!s} or {self.archive_root!s}"
        )

    def has_active(self, change_id: str) -> bool:
        """True if an active folder for ``change_id`` exists."""
        return (self.active_root / change_id).is_dir()

    def has_archived(self, change_id: str) -> bool:
        """True if an archived folder (any date prefix) for ``change_id`` exists."""
        if not self.archive_root.is_dir():
            return False
        for child in self.archive_root.iterdir():
            if not child.is_dir():
                continue
            try:
                cid = _derive_change_id(child.name)
            except ChangeStoreError:
                continue
            if cid == change_id:
                return True
        return False

    def find_archived_path(self, change_id: str) -> Path | None:
        """Return the archived folder path for ``change_id`` (or ``None``)."""
        if not self.archive_root.is_dir():
            return None
        for child in self.archive_root.iterdir():
            if not child.is_dir():
                continue
            try:
                cid = _derive_change_id(child.name)
            except ChangeStoreError:
                continue
            if cid == change_id:
                return child
        return None

    def transition_state(self, change_id: str, new_state: str) -> Change:
        """Mutate ``STATUS.yaml`` to ``new_state`` and write it back.

        Returns the updated :class:`Change`. Raises
        :exc:`ChangeStoreError` when the transition is illegal per
        :data:`STATE_TRANSITIONS`.
        """
        change, target_folder = self._get_active(change_id)
        if change.state == "IN_PROGRESS" and new_state == "VERIFYING":
            try:
                progress = derive_checklist_progress(change.checklist_md)
            except ValueError as exc:
                raise ChangeStoreError(
                    f"cannot transition checklist change {change_id!r} to VERIFYING: {exc}"
                ) from exc
            if not progress.ready_for_verifying:
                raise ChangeStoreError(
                    "CHECKLIST_NOT_READY: IN_PROGRESS -> VERIFYING requires the parsed "
                    "checklist body to have all items checked and zero open reverts "
                    f"(checked={progress.checked}, total={progress.total_items}, "
                    f"reverted_open={progress.reverted_open})"
                )
            synced_status = dict(change.status)
            synced_status["checklist_checked"] = progress.checked
            synced_status["checklist_total"] = progress.total_items
            synced_status["percent_complete"] = progress.percent_complete
            change = replace(change, status=synced_status)

        updated = change.with_state(new_state)
        self._write_status(updated, target_folder)
        return updated

    def revert_checklist_item(
        self,
        change_id: str,
        item_id: str,
        reason: str,
        *,
        actor: str,
        at: str | None = None,
    ) -> Change:
        """Explicitly persist a user-only checked-item revert.

        Only ``checklist.md`` is written. STATUS reconciliation and any
        VERIFYING demotion remain an explicit round-boundary operation.
        """

        change, folder = self._get_active(change_id)
        from devolaflow.agent_workspace.progress import refresh_progress_header
        from devolaflow.agent_workspace.round_engine import (
            revert_checklist_item as render_revert,
        )

        updated_text = render_revert(
            change.checklist_md,
            item_id,
            reason,
            actor=actor,
            at=at or _now_iso(),
        )
        # Keep the pinned progress header byte-aligned with the reopened item.
        updated_text = refresh_progress_header(updated_text, change.stage_md)
        updated = replace(change, checklist_md=updated_text)
        self._write_artifact(updated, folder, "checklist.md", updated_text)
        return updated

    def reconcile_round_boundary(
        self,
        change_id: str,
        *,
        at: str | None = None,
    ) -> Change:
        """Persist body-derived counters, header alignment, and any demotion."""

        change, folder = self._get_active(change_id)
        updated = reconcile_round_boundary(change, at=at)
        if updated is change:
            return change
        if updated.checklist_md != change.checklist_md:
            self._write_artifact(updated, folder, "checklist.md", updated.checklist_md)
        self._write_status(updated, folder)
        return updated

    def refresh_progress_header(self, change_id: str) -> Change:
        """Re-align the pinned ``## Progress`` header and persist it.

        The canonical L0 alignment call after checking items, adjusting
        ``effort:`` estimates, or writing the in-flight round's stage.md
        history row. Byte-identical checklists are not rewritten.
        """

        change, folder = self._get_active(change_id)
        from devolaflow.agent_workspace.progress import refresh_progress_header

        try:
            updated_text = refresh_progress_header(change.checklist_md, change.stage_md)
        except ValueError as exc:
            raise ChangeStoreError(
                f"cannot refresh progress header for {change_id!r}: {exc}"
            ) from exc
        if updated_text == change.checklist_md:
            return change
        updated = replace(change, checklist_md=updated_text)
        self._write_artifact(updated, folder, "checklist.md", updated_text)
        return updated

    def move_to_archive(self, change_id: str, *, archive_date: str | None = None) -> Path:
        """Atomically and durably move ``active/<id>/`` → archive.

        ``archive_date`` pins the ``YYYY-MM-DD`` prefix (defaults to today's
        UTC date; useful for tests + replay). Returns the archive folder path.

        Raises:
          ChangeNotFoundError: when ``change_id`` is not active.
          ChangeStoreError: when the archive target exists, the paths sit on
            different devices, or durability cannot be established
            (cross-device copy/delete would break the atomic move contract).
        """
        active_path = self.active_root / change_id
        if not active_path.is_dir():
            raise ChangeNotFoundError(
                f"cannot archive {change_id!r}: no active folder at {active_path!s}"
            )
        date_prefix = archive_date or _now_iso().split("T")[0]
        archive_target = self.archive_root / f"{date_prefix}-{change_id}"
        if archive_target.exists():
            raise ChangeStoreError(
                f"archive target {archive_target!s} already exists; "
                f"refusing to overwrite (delete or rename to retry)"
            )
        try:
            ensure_same_device(active_path, archive_target.parent)
            archive_target.parent.mkdir(parents=True, exist_ok=True)
            ensure_same_device(active_path, archive_target.parent)
            durable_move_directory(active_path, archive_target, fsync=_fsync_directory)
        except DurabilityError as exc:
            raise ChangeStoreError(str(exc)) from exc
        return archive_target
