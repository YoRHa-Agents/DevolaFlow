"""File and directory token metering (v24.0.0).

Gap analysis F-06: `devolaflow.harness.context_tokens.measure_context_tokens`
is zero-IO by explicit contract, so nothing in the repository could answer
"how many tokens does this folder cost an agent that reads it?". Compaction's
primary metric is exactly that number before and after, which means the
IO-performing wrapper has to exist somewhere — here, in the domain that needs
it, rather than by weakening the zero-IO contract of the harness helper.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from devolaflow.harness.context_tokens import estimate_text_tokens

logger = logging.getLogger(__name__)

#: Suffixes measured as text. Anything else is counted by bytes only, because
#: running a text tokenizer over binary content produces a number that looks
#: authoritative and means nothing.
TEXT_SUFFIXES = frozenset(
    {".md", ".yaml", ".yml", ".txt", ".json", ".jsonl", ".py", ".toml", ".cfg", ".ini", ".mdc"}
)


@dataclass(frozen=True)
class PathMeasurement:
    """Measured cost of one path, or of a directory's whole subtree."""

    path: str
    bytes: int
    tokens: int
    files: int
    measured_as_text: bool

    @property
    def estimated(self) -> bool:
        """Return whether the token count is a tokenizer estimate."""

        return self.measured_as_text


def measure_file(path: Path) -> PathMeasurement:
    """Measure one file, estimating tokens only for text-like suffixes."""

    try:
        size = path.stat().st_size
    except OSError as exc:
        logger.warning("token metering could not stat %s: %s", path, exc)
        return PathMeasurement(path.as_posix(), 0, 0, 0, False)
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return PathMeasurement(path.as_posix(), size, 0, 1, False)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        logger.warning("token metering could not read %s: %s", path, exc)
        return PathMeasurement(path.as_posix(), size, 0, 1, False)
    return PathMeasurement(path.as_posix(), size, estimate_text_tokens(text) or 0, 1, True)


def measure_path(path: Path) -> PathMeasurement:
    """Measure a file or a whole directory subtree."""

    if path.is_file():
        return measure_file(path)
    if not path.is_dir():
        return PathMeasurement(path.as_posix(), 0, 0, 0, False)
    total_bytes = 0
    total_tokens = 0
    files = 0
    text_seen = False
    for child in sorted(p for p in path.rglob("*") if p.is_file()):
        measurement = measure_file(child)
        total_bytes += measurement.bytes
        total_tokens += measurement.tokens
        files += measurement.files
        text_seen = text_seen or measurement.measured_as_text
    return PathMeasurement(path.as_posix(), total_bytes, total_tokens, files, text_seen)


def resident_tokens(folder: Path, *, exclude: Iterable[Path] = ()) -> int:
    """Return the token cost of everything an agent would read in a folder.

    Archived originals are excluded by the caller: they are still on disk and
    still reachable, but they are no longer in the agent's reading path, which
    is precisely what compaction buys.
    """

    excluded = {path.resolve() for path in exclude}
    total = 0
    for child in sorted(p for p in folder.rglob("*") if p.is_file()):
        resolved = child.resolve()
        if any(resolved == item or item in resolved.parents for item in excluded):
            continue
        total += measure_file(child).tokens
    return total


__all__ = [
    "TEXT_SUFFIXES",
    "PathMeasurement",
    "measure_file",
    "measure_path",
    "resident_tokens",
]
