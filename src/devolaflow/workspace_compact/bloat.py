"""Workspace bloat awareness for proactive compaction suggestions (v24.0.0).

Gap analysis F-07: `devolaflow.workspace_context.scan_workspace` probes
existence and counts but carries no size dimension, so L0 cannot notice that
a folder has grown past what an agent can read until a prompt actually
overflows — the failure this cycle exists to prevent.

This scanner adds that dimension without touching `scan_workspace`, whose
frozen return type is pinned by a large test surface. It is read-only and
suggests; it never compacts. Acting on a suggestion still requires a plan the
operator reads and approves.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from devolaflow.workspace_compact.metering import measure_path
from devolaflow.workspace_compact.models import COMPACT_DIRNAME

logger = logging.getLogger(__name__)

#: A folder costing more than one L2 task's entire context budget cannot be
#: read in one pass by the agent that owns it. That is the principled
#: threshold, not a round number: it is the point where the folder stops
#: fitting the layer that works in it (see A-3 layer budgets).
DEFAULT_THRESHOLD_TOKENS = 8_000

_SCAN_ROOTS = (
    Path(".local") / ".agent" / "active",
    Path(".local") / "tasks",
)


@dataclass(frozen=True)
class BloatFinding:
    """One folder whose resident cost exceeds the suggestion threshold."""

    folder: str
    tokens: int
    bytes: int
    files: int
    archived_tokens: int
    threshold: int = DEFAULT_THRESHOLD_TOKENS

    @property
    def over_by(self) -> int:
        """Return how far past the scan's own threshold this folder sits."""

        return self.tokens - self.threshold


def measure_folder(folder: Path) -> tuple[int, int, int, int]:
    """Return resident tokens, bytes, files, and already-archived tokens."""

    whole = measure_path(folder)
    archive = folder / COMPACT_DIRNAME
    archived = measure_path(archive) if archive.is_dir() else None
    archived_tokens = archived.tokens if archived else 0
    archived_bytes = archived.bytes if archived else 0
    archived_files = archived.files if archived else 0
    return (
        whole.tokens - archived_tokens,
        whole.bytes - archived_bytes,
        whole.files - archived_files,
        archived_tokens,
    )


def scan_bloat(
    repo_root: str | Path,
    *,
    threshold_tokens: int = DEFAULT_THRESHOLD_TOKENS,
) -> tuple[BloatFinding, ...]:
    """Report every workspace folder whose resident cost is over threshold.

    Read-only. Already-relocated content is excluded, so a folder that has
    been compacted does not keep re-triggering on the archive it produced.
    """

    root = Path(repo_root)
    findings: list[BloatFinding] = []
    for relative in _SCAN_ROOTS:
        container = root / relative
        if not container.is_dir():
            continue
        try:
            children = sorted(child for child in container.iterdir() if child.is_dir())
        except OSError as exc:
            logger.warning("bloat scan could not read %s: %s", container, exc)
            continue
        for folder in children:
            tokens, size, files, archived_tokens = measure_folder(folder)
            if tokens < threshold_tokens:
                continue
            findings.append(
                BloatFinding(
                    folder=folder.relative_to(root).as_posix(),
                    tokens=tokens,
                    bytes=size,
                    files=files,
                    archived_tokens=archived_tokens,
                    threshold=threshold_tokens,
                )
            )
    return tuple(sorted(findings, key=lambda item: -item.tokens))


def suggestion_text(
    findings: tuple[BloatFinding, ...],
    *,
    threshold: int = DEFAULT_THRESHOLD_TOKENS,
) -> str:
    """Render the one-paragraph suggestion an L0 dispatcher would surface.

    ``threshold`` must be the value the scan actually filtered on. Reporting
    the default while having filtered on something else makes the reader
    mistrust every number in the message.
    """

    if not findings:
        return f"No workspace folder exceeds {threshold} resident tokens."
    lines = [
        f"{len(findings)} folder(s) exceed {threshold} resident tokens — "
        "an agent cannot read them in one pass. Run `devola-compact plan --folder <path>` "
        "to see what would move and what it would cost; a plan that does not pay for its "
        "own digest says so. Most workspace weight sits in hand-written documents that "
        "automatic classification retains, so read the plan's `candidates` list and name "
        "one with `--include <path>`. Nothing relocates without your approval.",
        "",
    ]
    lines.extend(
        f"- `{item.folder}` — {item.tokens} tokens across {item.files} files"
        + (f" ({item.archived_tokens} already archived)" if item.archived_tokens else "")
        for item in findings
    )
    return "\n".join(lines)


__all__ = [
    "DEFAULT_THRESHOLD_TOKENS",
    "BloatFinding",
    "measure_folder",
    "scan_bloat",
    "suggestion_text",
]
