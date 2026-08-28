"""Rollback support for a failed workspace archive attempt.

Split out of `devolaflow.agent_workspace.archive` at v20.0.0 to honour the
W-9 module-size ratchet. The guard captures every locally mutated surface
before :meth:`ArchiveManager.archive` starts (STATUS.yaml bytes, the global
learnings ledger, the not-yet-existing archive target) and restores them all
when the attempt fails partway, so a failed archive never strands a change
half-moved (Loop v3 B4 closure).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from devolaflow._durability import fsync_directory, write_durable

logger = logging.getLogger(__name__)


class ArchiveRollbackError(RuntimeError):
    """Raised when a failed archive attempt could not be rolled back."""


@dataclass
class ArchiveAttemptGuard:
    """Mutable snapshot of the state a failed archive attempt must restore."""

    change_id: str
    active_path: Path
    global_path: Path
    status_before: bytes
    global_before: bytes | None
    archive_target: Path | None = None
    mutation_started: bool = False

    @classmethod
    def capture(
        cls, *, change_id: str, active_path: Path, global_path: Path
    ) -> ArchiveAttemptGuard:
        """Snapshot the mutable archive surfaces before any mutation."""

        return cls(
            change_id=change_id,
            active_path=active_path,
            global_path=global_path,
            status_before=(active_path / "STATUS.yaml").read_bytes(),
            global_before=global_path.read_bytes() if global_path.exists() else None,
        )

    def rollback(self) -> None:
        """Restore all locally mutated archive state after a failed attempt."""

        try:
            if (
                self.archive_target is not None
                and self.archive_target.exists()
                and not self.active_path.exists()
            ):
                os.replace(self.archive_target, self.active_path)
                fsync_directory(self.active_path.parent)
                fsync_directory(self.archive_target.parent)
            if self.mutation_started and self.active_path.exists():
                write_durable(self.active_path / "STATUS.yaml", self.status_before)
            if self.mutation_started:
                if self.global_before is None:
                    if self.global_path.exists():
                        self.global_path.unlink()
                        fsync_directory(self.global_path.parent)
                else:
                    self.global_path.parent.mkdir(parents=True, exist_ok=True)
                    write_durable(self.global_path, self.global_before)
        except OSError as exc:
            logger.error(
                "archive rollback failed for %s; manual recovery is required: %s",
                self.change_id,
                exc,
            )
            raise ArchiveRollbackError(
                f"archive rollback failed for {self.change_id!r}; manual recovery required: {exc}"
            ) from exc
