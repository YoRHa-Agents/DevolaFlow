"""Shared filesystem durability primitives (v20.0.0 module-size split).

The Loop v3 behavioral closures gave the workspace and local-task archive
paths a common durability contract: atomic same-device renames, explicit
directory-entry flushes, and rollback on a failed move. The primitives live
here so `devolaflow.agent_workspace.archive`, `devolaflow.agent_workspace.change`,
and `devolaflow.local.archive` share one implementation instead of growing
three grandfathered modules past their W-9 module-size baselines.

Callers that need failure injection in tests keep referencing these functions
through their own module globals (`from devolaflow._durability import
fsync_directory as _fsync_directory`), so monkeypatching the consumer module
attribute still intercepts every call.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path


class DurabilityError(RuntimeError):
    """Raised when an atomic-move or flush contract cannot be honoured."""


def fsync_directory(path: Path) -> None:
    """Flush a directory entry, or fail rather than claiming durable storage."""

    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_durable(path: Path, content: bytes) -> None:
    """Persist bytes and flush both file data and its parent directory."""

    path.write_bytes(content)
    with path.open("rb") as stream:
        os.fsync(stream.fileno())
    fsync_directory(path.parent)


def existing_parent(path: Path) -> Path:
    """Return the nearest existing ancestor without creating a destination."""

    current = path
    while not current.exists() and current != current.parent:
        current = current.parent
    return current


def _same_device(source: Path, destination: Path) -> bool:
    """Return whether an atomic rename can use both paths' devices."""

    try:
        return source.stat().st_dev == existing_parent(destination).stat().st_dev
    except OSError:
        return False


def ensure_same_device(source: Path, destination: Path) -> None:
    """Raise :class:`DurabilityError` unless an atomic rename is available."""

    try:
        if source.stat().st_dev != existing_parent(destination).stat().st_dev:
            raise DurabilityError(
                "cannot archive across devices; atomic rename and durability "
                "contract are unavailable"
            )
    except OSError as exc:
        raise DurabilityError(f"cannot establish same-device archive contract: {exc}") from exc


def durable_move_directory(
    source: Path, target: Path, *, fsync: Callable[[Path], None] = fsync_directory
) -> None:
    """Atomically move ``source`` to ``target`` with directory flushes.

    On a flush failure after the rename, the move is rolled back before the
    error is reported; a rollback failure is reported as requiring manual
    recovery. ``fsync`` is injectable so consumer modules can keep their
    module-level failure-injection seams.
    """

    try:
        os.replace(source, target)
        fsync(source.parent)
        fsync(target.parent)
    except OSError as exc:
        if target.exists() and not source.exists():
            try:
                os.replace(target, source)
                fsync(source.parent)
                fsync(target.parent)
            except OSError as rollback_exc:
                raise DurabilityError(
                    "archive move durability failed and recovery also failed; "
                    f"manual recovery required: {rollback_exc}"
                ) from exc
        raise DurabilityError(
            f"archive move durability contract failed; move was rolled back: {exc}"
        ) from exc
