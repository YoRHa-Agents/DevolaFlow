"""Generated navigation index for handoff envelopes (v24.0.0).

Design ref: `.local/research/v24.0.0_s9_amendment_draft.md` §6.

Gap analysis F-03: an N-round change accumulates envelopes with no index, so
an agent that needs one fact opens every file. Relocating them would require
amending S-9, which is human-gated and deliberately on a separate track.

This module is the interim answer, and it is index-only **by construction**:
it reads envelopes and writes exactly one generated file outside the handoff
directory. It contains no move, no rewrite, and no delete. S-9 is therefore
satisfied without needing the amendment at all — and when the amendment does
land, the relocation path is additive rather than a rewrite of this code.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from devolaflow.workspace_compact.models import HANDOFF_INDEX_MARKER
from devolaflow.workspace_ledger import Finding, render_rows_table, write_generated_view

logger = logging.getLogger(__name__)

HANDOFF_DIR = Path(".local") / ".agent" / "handoff"
INDEX_RELATIVE = HANDOFF_DIR / "INDEX.md"

_ENVELOPE_RE = re.compile(
    r"^(?P<from>L[0-3])__(?P<to>L[0-3])__(?P<change_id>[a-z0-9][a-z0-9.-]*[a-z0-9])"
    r"__(?P<seq>\d{4})\.yaml$"
)


@dataclass(frozen=True)
class EnvelopeSummary:
    """One envelope reduced to the fields an index needs."""

    filename: str
    from_layer: str
    to_layer: str
    change_id: str
    seq: int
    subject: str
    bytes: int


def _summarize(path: Path) -> EnvelopeSummary | None:
    match = _ENVELOPE_RE.match(path.name)
    if match is None:
        return None
    subject = ""
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            for key in ("subject", "summary", "title", "purpose", "intent"):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    subject = value.strip().splitlines()[0][:120]
                    break
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        logger.warning("handoff index could not read %s: %s", path.name, exc)
        subject = "(unreadable)"
    try:
        size = path.stat().st_size
    except OSError:
        size = 0
    return EnvelopeSummary(
        filename=path.name,
        from_layer=match.group("from"),
        to_layer=match.group("to"),
        change_id=match.group("change_id"),
        seq=int(match.group("seq")),
        subject=subject,
        bytes=size,
    )


def collect_envelopes(
    repo_root: str | Path, *, change_id: str | None = None
) -> tuple[EnvelopeSummary, ...]:
    """Read every envelope's header fields without modifying any of them."""

    directory = Path(repo_root) / HANDOFF_DIR
    if not directory.is_dir():
        return ()
    summaries = []
    for path in sorted(directory.glob("*.yaml")):
        summary = _summarize(path)
        if summary is None:
            continue
        if change_id is not None and summary.change_id != change_id:
            continue
        summaries.append(summary)
    return tuple(sorted(summaries, key=lambda item: (item.change_id, item.seq)))


def render_handoff_index(summaries: tuple[EnvelopeSummary, ...]) -> str:
    """Render the generated index; envelopes themselves are never touched."""

    total_bytes = sum(item.bytes for item in summaries)
    changes = sorted({item.change_id for item in summaries})
    lines = [
        HANDOFF_INDEX_MARKER,
        "# Handoff Envelope Index",
        "",
        "Generated navigation view. The envelopes are the authoritative record",
        "and are append-only under S-9: nothing here has been moved, rewritten,",
        "or removed. Read one row instead of opening every envelope.",
        "",
        f"Envelopes: {len(summaries)} · Changes: {len(changes)} · Bytes: {total_bytes}",
        "",
    ]
    if not summaries:
        lines.extend(["No envelopes.", ""])
        return "\n".join(lines).rstrip("\n") + "\n"
    for change in changes:
        rows = [item for item in summaries if item.change_id == change]
        lines.extend([f"## {change}", ""])
        lines.extend(
            render_rows_table(
                ("Seq", "Route", "Subject", "Bytes", "File"),
                [
                    (
                        f"{item.seq:04d}",
                        f"{item.from_layer}→{item.to_layer}",
                        (item.subject or "—").replace("|", "\\|"),
                        str(item.bytes),
                        f"`{item.filename}`",
                    )
                    for item in rows
                ],
            )
        )
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"


def write_handoff_index(
    repo_root: str | Path, *, change_id: str | None = None
) -> tuple[Path | None, tuple[str, ...]]:
    """Persist the generated index beside the envelopes it describes."""

    root = Path(repo_root)
    directory = root / HANDOFF_DIR
    if not directory.is_dir():
        return None, ("NO_HANDOFF_DIR: nothing to index",)
    summaries = collect_envelopes(root, change_id=change_id)
    target = root / INDEX_RELATIVE
    findings: tuple[Finding, ...] = write_generated_view(
        root,
        target,
        render_handoff_index(summaries),
        marker=HANDOFF_INDEX_MARKER,
    )
    if findings:
        return None, tuple(f"{item.code}: {item.message}" for item in findings)
    return target, ()


__all__ = [
    "HANDOFF_DIR",
    "INDEX_RELATIVE",
    "EnvelopeSummary",
    "collect_envelopes",
    "render_handoff_index",
    "write_handoff_index",
]
