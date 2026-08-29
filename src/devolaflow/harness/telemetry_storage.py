"""Append-only storage primitives for harness telemetry segments."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Final

HARNESS_SEGMENT_MAX_BYTES: Final[int] = 64 * 1024
MAX_HARNESS_SEGMENT_BYTES: Final[int] = HARNESS_SEGMENT_MAX_BYTES

_BASE_LEDGER_NAME = "harness.jsonl"
_SEGMENT_RE = re.compile(r"^harness\.(?P<index>[1-9]\d*)\.jsonl$")

logger = logging.getLogger(__name__)


def _segment_index(path: Path) -> int | None:
    if path.name == _BASE_LEDGER_NAME:
        return 0
    match = _SEGMENT_RE.fullmatch(path.name)
    return int(match.group("index")) if match else None


def _segment_path(change_folder: Path, index: int) -> Path:
    if index == 0:
        return change_folder / _BASE_LEDGER_NAME
    return change_folder / f"harness.{index}.jsonl"


def append_harness_record(
    change_folder: str | Path,
    record: dict[str, Any],
    *,
    max_bytes: int = HARNESS_SEGMENT_MAX_BYTES,
) -> Path | None:
    """Append one compact JSONL record, rotating before the byte ceiling.

    Rotation is append-only: existing segments are never rewritten. The
    implementation uses directory metadata and ``stat`` only; it never reads
    an existing ledger into memory and deliberately performs no ``fsync``.
    """
    folder = Path(change_folder)
    try:
        if type(max_bytes) is not int or max_bytes <= 0:
            raise ValueError("max_bytes must be a positive integer")
        if not folder.is_dir():
            raise OSError(f"active change folder does not exist: {folder!s}")
        encoded = (json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n").encode(
            "utf-8"
        )
        if len(encoded) > max_bytes:
            logger.warning(
                "harness telemetry record is %d bytes, exceeding the %d-byte "
                "segment cap; record not written",
                len(encoded),
                max_bytes,
            )
            return None

        indexed_segments = [
            (index, child)
            for child in folder.iterdir()
            if child.is_file() and (index := _segment_index(child)) is not None
        ]
        if indexed_segments:
            index, target = max(indexed_segments, key=lambda item: item[0])
        else:
            index, target = 0, _segment_path(folder, 0)

        current_size = target.stat().st_size if target.exists() else 0
        if current_size + len(encoded) > max_bytes:
            target = _segment_path(folder, index + 1)

        with target.open("ab") as stream:
            stream.write(encoded)
        return target
    except (OSError, TypeError, ValueError) as exc:
        logger.warning(
            "harness telemetry append failed for %s: %s; dispatch continues",
            folder,
            exc,
        )
        return None


__all__ = [
    "HARNESS_SEGMENT_MAX_BYTES",
    "MAX_HARNESS_SEGMENT_BYTES",
    "append_harness_record",
]
