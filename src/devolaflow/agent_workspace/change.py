"""Change dataclass + ChangeStore for ``.local/.agent/active/`` artifacts.

Closes C-003 (Python half) per ``.local/research/v8.3.0_gap_analysis.md`` §2.1
and the M-005 Python binding for ``schemas/agent-workspace/change-status.yaml``.

A :class:`Change` is the in-memory representation of a single
``.local/.agent/active/<change-id>/`` folder, mapping the seven on-disk
artifacts (``goal.md`` / ``acceptance.md`` / ``spec.md`` / ``tasks.md`` /
``STATUS.yaml`` / ``owned_files.txt`` / ``learnings.jsonl``) to attributes
plus the parsed STATUS frontmatter values.

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
* ``learnings.jsonl`` is an opaque JSONL blob; it is copied verbatim
  on round-trip (parsing is the consumer's responsibility — the
  ``learnings.py`` module already handles JSONL semantics).

Public API:

* :class:`Change` — dataclass mirroring the on-disk artifact set.
* :class:`ChangeStore` — list / get / move / transition_state.
* :exc:`ChangeStoreError` — generic store-side error.
* :exc:`ChangeNotFoundError` — raised when a change-id is not found.
"""

from __future__ import annotations

import logging
import re
import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

import yaml

logger = logging.getLogger(__name__)

__all__ = [
    "ACTIVE_DIR_DEFAULT",
    "ARCHIVE_DIR_DEFAULT",
    "ARTIFACT_FILES",
    "Change",
    "ChangeNotFoundError",
    "ChangeStore",
    "ChangeStoreError",
    "FSM_STATES",
    "STATE_TRANSITIONS",
]


ACTIVE_DIR_DEFAULT: Final[Path] = Path(".local") / ".agent" / "active"
ARCHIVE_DIR_DEFAULT: Final[Path] = Path(".local") / ".agent" / "archive"

# The seven artifacts defined in ``schemas/agent-workspace/`` (PV-04).
# Order follows ``.local/research/v8.3.0_design.md`` §1.1 verbatim.
ARTIFACT_FILES: Final[tuple[str, ...]] = (
    "goal.md",
    "acceptance.md",
    "spec.md",
    "tasks.md",
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


class ChangeStoreError(RuntimeError):
    """Generic error raised by :class:`ChangeStore`.

    Subclassed by more specific errors (e.g. :exc:`ChangeNotFoundError`).
    Keeping a non-trivial superclass simplifies callers that want to
    catch any change-store failure.
    """


class ChangeNotFoundError(ChangeStoreError):
    """Raised when a change-id is not present in active or archive."""


@dataclass
class Change:
    """In-memory representation of one ``.local/.agent/active/<id>/`` folder.

    The seven artifact attributes hold the verbatim on-disk text (or
    ``None`` when the file is absent — only ``learnings.jsonl`` is
    legitimately optional). The ``status`` attribute carries the parsed
    ``STATUS.yaml`` mapping.

    ``Change.from_active_folder(path)`` is the canonical constructor;
    direct dataclass instantiation is reserved for tests.
    """

    change_id: str
    goal_md: str = ""
    acceptance_md: str = ""
    spec_md: str = ""
    tasks_md: str = ""
    status: dict = field(default_factory=dict)
    owned_files: list[str] = field(default_factory=list)
    learnings_jsonl: str | None = None
    # Source folder — populated by from_active_folder; useful for diagnostics.
    source_folder: Path | None = None

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
        if not folder_path.is_dir():
            raise ChangeNotFoundError(
                f"change folder {folder_path!s} does not exist or is not a directory"
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

        return cls(
            change_id=change_id,
            goal_md=_read("goal.md"),
            acceptance_md=_read("acceptance.md"),
            spec_md=_read("spec.md"),
            tasks_md=_read("tasks.md"),
            status=status_data,
            owned_files=owned_files,
            learnings_jsonl=learnings_jsonl,
            source_folder=folder_path,
        )

    def to_active_folder(self, folder: Path | str) -> None:
        """Write this :class:`Change` to ``folder`` (creating it if absent).

        Existing files in ``folder`` are OVERWRITTEN. The seven
        artifacts are written in the canonical order from
        :data:`ARTIFACT_FILES`.

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
        """
        folder_path = Path(folder)
        folder_path.mkdir(parents=True, exist_ok=True)

        def _write(name: str, text: str, *, newline: str | None = None) -> None:
            """Write one artifact through the hooked write surface (ADR-003).

            Fires the ``file_write`` lifecycle hook BEFORE the write per
            ADR-003 (STRICT default since v15.0.0 — an S-8 ownership
            violation raises ``HookViolation`` and BLOCKS the write;
            byte-identical no-op when ``DEVOLAFLOW_AGENT_WORKSPACE`` !=
            "1"), then performs the exact pre-v14.3.0
            ``Path.write_text`` call.
            """
            target = folder_path / name
            _fire_file_write_hook(target, self.owned_files, folder_path)
            if newline is None:
                target.write_text(text, encoding="utf-8")
            else:
                target.write_text(text, encoding="utf-8", newline=newline)

        _write("goal.md", self.goal_md)
        _write("acceptance.md", self.acceptance_md)
        _write("spec.md", self.spec_md)
        _write("tasks.md", self.tasks_md)

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
            acceptance_md=self.acceptance_md,
            spec_md=self.spec_md,
            tasks_md=self.tasks_md,
            status=new_status,
            owned_files=list(self.owned_files),
            learnings_jsonl=self.learnings_jsonl,
            source_folder=self.source_folder,
        )


def _fire_file_write_hook(
    target: Path,
    owned_files: list[str],
    change_folder: Path,
) -> None:
    """Fire the ``file_write`` lifecycle hook for one artifact write.

    Production call site for
    :func:`devolaflow.lifecycle.runtime_wiring.fire_file_write` per
    ADR-003 (``docs/cycle-archive/adr/v15-ADR-003-output-closure-
    enforcement-locus.md``): ``Change.to_active_folder`` IS the
    framework's change-driven write surface, so every artifact write
    runs through the hook BEFORE touching disk. STRICT by default
    since v15.0.0 (G-038 graduation per ADR-003 §Decision 3): the call
    defers to ``fire_file_write``'s own strict default, so an S-8
    ownership violation raises :class:`HookViolation` (block +
    escalate, S-8 "mode: full") and the write never happens. Opt-out
    is the adapter's explicit ``strict=False`` parameter (S-8 "mode:
    lite"). Still a byte-identical zero-IO no-op when
    ``DEVOLAFLOW_AGENT_WORKSPACE`` != "1" (W-20 flag reuse — the
    activation gate is UNCHANGED).

    Per the S-5 isolation pattern established by
    ``feedback_emit.ProposalEmitter._fire_hook_chain``, a buggy hook
    handler (any exception OTHER than the strict-mode
    :class:`HookViolation`) is logged at WARNING and the write
    proceeds — infrastructure bugs MUST NOT break the change-driven
    flow, but a real S-8 violation MUST. Lazy import keeps the
    no-cycle property between ``agent_workspace`` and ``lifecycle``
    (mirrors ``auto_write_handoff``'s lazy reverse import).
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
        change = self.get(change_id)
        updated = change.with_state(new_state)
        target_folder = self.active_root / change_id
        if not target_folder.is_dir():
            raise ChangeStoreError(
                f"transition_state requires an ACTIVE change; {change_id!r} is "
                f"either archived or absent (search: {self.active_root!s})"
            )
        # Round-trip the full Change to disk so STATUS.yaml is rewritten with
        # the new state + refreshed last_updated stamp.
        updated.to_active_folder(target_folder)
        return updated

    def move_to_archive(self, change_id: str, *, archive_date: str | None = None) -> Path:
        """Atomically move ``active/<id>/`` → ``archive/<date>-<id>/``.

        Args:
          change_id: id of the active change to archive.
          archive_date: explicit ``YYYY-MM-DD`` prefix (defaults to today's
            UTC date). Pinning the date is useful for tests + replay.

        Returns:
          The archive folder path.

        Raises:
          ChangeNotFoundError: when ``change_id`` is not active.
          ChangeStoreError: when the archive target already exists (idempotency
            is the caller's contract — see
            :meth:`ArchiveManager.archive`).
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
        archive_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(active_path), str(archive_target))
        return archive_target
