"""Memory bridge between the agent workspace and operational learnings.

Closes H-006 from ``.local/research/v8.3.0_gap_analysis.md`` per
``.local/research/v8.3.0_design.md`` §4 (lines 459–520) — the v8.2.8 patch
in the v8.3.0 minor cycle.

This module wires two flows:

1. **Archive-time consolidation** — :func:`consolidate_change_on_archive`
   loads the per-change ``learnings.jsonl`` from
   ``.local/.agent/archive/<date>-<change-id>/learnings.jsonl`` and forwards
   the parsed entries to the existing
   :func:`devolaflow.learnings.consolidate_session` (the v7.0.3 ADR-005
   promotion engine). This is the missing half of the v8.2.6 archive flow:
   without it, per-change reflective reflexes never make it into the global
   ``.local/memory/operational.jsonl`` substrate.
2. **Context hydration** — :func:`hydrate_change_context` validates the
   canonical active-change layout and loads the checklist payload (including
   verbatim ``evidence/*.txt``) for L0/L1/L2 context injection. Text
   artifacts are capped at their hard ceilings so a runaway ``spec.md``
   cannot blow a Wave Agent's 4K budget. Truncation appends a sentinel
   rather than raising — the caller still gets *some* context.

Public surface (consumed by ``v8.2.6`` change-driven workflow + future
``/devola:archive`` command in ``v8.2.9``):

* :func:`consolidate_change_on_archive` — archive-time JSONL → global
  promotion via :func:`consolidate_session`.
* :func:`hydrate_change_context` — load + cap the canonical artifact set for
  a checklist-layout active change.
* :exc:`MemoryBridgeError` — raised by
  :func:`consolidate_change_on_archive` when the per-change JSONL is
  syntactically malformed (S-5: loud, never silent).
* :data:`TRUNCATION_SENTINEL` — string appended to truncated artifacts
  so consumers can detect the cap was hit.

R5 invariant (I-PV08-A): this module **does not edit**
``src/devolaflow/learnings.py`` beyond the additive ``change_id``
parameters extended in v8.2.8 — every existing call site of the 14
public ``learnings`` functions remains byte-identical.

Source: v8.3.0 design.md §4 — closes gap H-006 from v8.3.0_gap_analysis.md.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Final

import yaml

from devolaflow.agent_workspace.change import (
    ACTIVE_DIR_DEFAULT,
    ARCHIVE_DIR_DEFAULT,
    ChangeLayout,
    ChangeNotFoundError,
    ChangeStoreError,
    detect_change_layout,
)
from devolaflow.agent_workspace.lint import estimate_tokens
from devolaflow.learnings import Learning, consolidate_session

_DATE_PREFIX_RE: Final[re.Pattern[str]] = re.compile(r"^\d{4}-\d{2}-\d{2}-")
"""Local copy of ``change.py`` archive-date pattern (private-by-convention
in change.py; duplicating here keeps memory_bridge a clean leaf module
without reaching into another module's underscored internals)."""

logger = logging.getLogger(__name__)

__all__ = [
    "MemoryBridgeError",
    "TRUNCATION_SENTINEL",
    "consolidate_change_on_archive",
    "hydrate_change_context",
]


TRUNCATION_SENTINEL: Final[str] = "…(truncated)"
"""Marker appended to artifacts whose raw token count exceeded the C-9 hard
ceiling. Consumers can grep for this sentinel to detect that the original
artifact was longer — the truncated payload is still parseable / useful
for context injection but lacks the trailing material."""


# Per Rule C-9 — verbatim from
# ``.cursor/rules/repo-governance.mdc#C-9`` and ``schemas/agent-workspace/*``.
# Keys are the dict keys returned by :func:`hydrate_change_context`; values
# are the HARD ceilings (the soft / hard split lives in
# :data:`devolaflow.agent_workspace.lint.CHECKLIST_ARTIFACT_BUDGETS`).
_CHECKLIST_HYDRATE_BUDGETS: Final[dict[str, int]] = {
    "goal": 400,
    "checklist": 2400,
    "stage": 800,
    "preflight": 1200,
    "spec": 3000,
    "status": 300,
    "owned_files": 100,
}
"""Checklist-layout hard ceilings for context hydration."""


class MemoryBridgeError(RuntimeError):
    """Raised by :func:`consolidate_change_on_archive` on irrecoverable I/O.

    Specifically: malformed JSON in a per-change ``learnings.jsonl``. We
    raise loudly per Rule S-5 because a corrupt JSONL is a data-integrity
    incident worth surfacing rather than silently dropping entries — the
    operator can inspect / recover the file before re-running.
    """


# ---------------------------------------------------------------------------
# Archive-time consolidation
# ---------------------------------------------------------------------------


def consolidate_change_on_archive(
    change_id: str,
    archive_root: Path | None = None,
    global_jsonl: Path | None = None,
) -> dict:
    """Promote per-change learnings to global memory at archive time.

    Walks ``archive_root`` for the dated folder matching ``change_id``
    (e.g. ``2026-04-23-add-foo`` for ``change_id='add-foo'``), loads its
    ``learnings.jsonl``, and forwards the parsed entries to
    :func:`devolaflow.learnings.consolidate_session` for promotion into
    ``global_jsonl`` (typically ``.local/memory/operational.jsonl``).

    Args:
        change_id: The change-id whose archive folder should be consolidated.
        archive_root: Override for the archive folder root. Defaults to
            ``.local/.agent/archive`` resolved against ``Path.cwd()``.
        global_jsonl: Override for the global JSONL destination. Defaults
            to ``.local/memory/operational.jsonl`` resolved against
            ``Path.cwd()``.

    Returns:
        The ``{promoted: int, captured: int, skipped: int}`` summary
        dict produced by :func:`consolidate_session`. When the archive
        folder exists but has no ``learnings.jsonl`` (a change that
        recorded no per-task reflections), returns the all-zeros dict
        without invoking the consolidator.

    Raises:
        ChangeNotFoundError: When no archived folder under
            ``archive_root`` matches ``change_id``. Raising explicitly per
            Rule S-5 — silent skips would mask archival mistakes.
        MemoryBridgeError: When ``learnings.jsonl`` is present but
            contains malformed JSON. Loud per S-5; the operator should
            inspect / repair the file before retrying.

    Notes:
        ``consolidate_session`` is the existing v7.0.3 ADR-005 promotion
        engine — it bumps confidence on duplicates and appends new
        entries with ``promotion_count=1``, returning the integer
        counts. This bridge is purely a wrapper; the promotion logic is
        unchanged.
    """
    if archive_root is None:
        archive_root = _resolve_under_cwd(ARCHIVE_DIR_DEFAULT)
    if global_jsonl is None:
        global_jsonl = _default_global_jsonl()

    archive_path = _find_archive_folder(archive_root, change_id)
    if archive_path is None:
        raise ChangeNotFoundError(
            f"consolidate_change_on_archive: no archive folder found for "
            f"change_id={change_id!r} under {archive_root!s} "
            f"(expected a folder named '<YYYY-MM-DD>-{change_id}' or "
            f"'{change_id}')"
        )

    learnings_path = archive_path / "learnings.jsonl"
    if not learnings_path.exists():
        logger.info(
            "consolidate_change_on_archive: no learnings.jsonl in %s; "
            "returning zero-counts (change recorded no reflections)",
            archive_path,
        )
        return {"promoted": 0, "captured": 0, "skipped": 0}

    learnings = _parse_learnings_jsonl(learnings_path)

    global_jsonl.parent.mkdir(parents=True, exist_ok=True)
    if not global_jsonl.exists():
        global_jsonl.touch()

    summary = consolidate_session(
        session_id=f"archive-{change_id}",
        session_learnings=learnings,
        jsonl_path=global_jsonl,
    )
    logger.info(
        "consolidate_change_on_archive: change=%s promoted=%d captured=%d skipped=%d",
        change_id,
        summary["promoted"],
        summary["captured"],
        summary["skipped"],
    )
    return summary


# ---------------------------------------------------------------------------
# Context hydration
# ---------------------------------------------------------------------------


def hydrate_change_context(
    change_id: str,
    active_root: Path | None = None,
) -> dict[str, Any]:
    """Hydrate an active change using the canonical checklist layout.

    The payload exposes ``goal``, ``checklist``, ``stage``, ``preflight``,
    ``spec``, ``status``, ``owned_files``, ``learnings``, and ``evidence``.
    Evidence values are verbatim text keyed by ``.txt`` basename.

    Text artifacts are capped to the hard ceiling for the detected layout.
    Truncation is destructive but additive — the original file on disk is
    untouched, only the in-memory payload is shortened — and a
    :data:`TRUNCATION_SENTINEL` marker is appended so consumers can detect the
    cap was hit.

    Args:
        change_id: The active change-id whose artifacts to load.
        active_root: Override for the active folder root. Defaults to
            ``.local/.agent/active`` resolved against ``Path.cwd()``.

    Returns:
        The nine-key checklist payload described above. Missing text/status
        artifacts return ``None``; missing list/mapping collections return
        an empty container.

    Raises:
        ChangeNotFoundError: When ``active_root/<change_id>/`` does not
            exist (S-5: loud — hydrate is a contract, the caller must
            know the change is real before requesting context).
        ChangeStoreError: When checklist and legacy marker artifacts coexist
            and the canonical detector reports ``INVALID_MIXED``.
        LegacyChangeLayoutError: When the folder still uses the removed
            pre-v16 tasks.md/acceptance.md layout.
    """
    if active_root is None:
        active_root = _resolve_under_cwd(ACTIVE_DIR_DEFAULT)
    folder = active_root / change_id
    if not folder.is_dir():
        raise ChangeNotFoundError(
            f"hydrate_change_context: no active folder for change_id="
            f"{change_id!r} under {active_root!s}"
        )

    layout = detect_change_layout(folder)
    if layout is ChangeLayout.INVALID_MIXED:
        raise ChangeStoreError(
            f"hydrate_change_context: change folder {folder!s} has "
            "INVALID_MIXED layout: checklist.md cannot coexist with "
            "tasks.md or acceptance.md"
        )

    budgets = _CHECKLIST_HYDRATE_BUDGETS
    return {
        "goal": _hydrate_markdown(folder / "goal.md", budgets["goal"]),
        "checklist": _hydrate_markdown(folder / "checklist.md", budgets["checklist"]),
        "stage": _hydrate_markdown(folder / "stage.md", budgets["stage"]),
        "preflight": _hydrate_markdown(folder / "preflight.md", budgets["preflight"]),
        "spec": _hydrate_markdown(folder / "spec.md", budgets["spec"]),
        "status": _hydrate_status(folder / "STATUS.yaml", budgets["status"]),
        "owned_files": _hydrate_owned_files(folder / "owned_files.txt", budgets["owned_files"]),
        "learnings": _hydrate_learnings(folder / "learnings.jsonl"),
        "evidence": _hydrate_evidence(folder / "evidence"),
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resolve_under_cwd(rel: Path) -> Path:
    """Resolve a relative ``Path`` against ``Path.cwd()`` once at call time.

    The default arguments of the public functions intentionally hold
    ``None`` so callers (and tests via ``monkeypatch.chdir``) get fresh
    cwd resolution on every call rather than the import-time directory.
    """
    return rel if rel.is_absolute() else Path.cwd() / rel


def _default_global_jsonl() -> Path:
    """Default destination for the consolidated global learnings JSONL."""
    return Path.cwd() / ".local" / "memory" / "operational.jsonl"


def _find_archive_folder(archive_root: Path, change_id: str) -> Path | None:
    """Walk ``archive_root`` for a folder whose suffix matches ``change_id``.

    Recognises two layouts (matching :mod:`devolaflow.agent_workspace.change`):

    * Dated archive folders ``YYYY-MM-DD-<change_id>`` (the v8.2.6 default).
    * Bare ``<change_id>`` folders (test fixtures / pre-v8.2.6 archives).

    Returns the matched :class:`pathlib.Path` or ``None`` when no match
    is found. Linear scan — archives are not expected to grow large
    enough for indexing to matter (one per change, ~weeks-months of
    history).
    """
    if not archive_root.is_dir():
        return None
    for child in sorted(archive_root.iterdir()):
        if not child.is_dir():
            continue
        name = child.name
        if name == change_id:
            return child
        if _DATE_PREFIX_RE.match(name):
            stripped = name[len("YYYY-MM-DD-") :]
            if stripped == change_id:
                return child
    return None


def _parse_learnings_jsonl(path: Path) -> list[Learning]:
    """Parse a learnings.jsonl into a list of :class:`Learning` instances.

    Malformed JSON raises :exc:`MemoryBridgeError` (S-5 loud). Entries
    missing the required Learning fields (``stage`` / ``task_type`` /
    ``key``) are skipped with a single warning per drop — this matches
    the conservative behaviour of
    :func:`devolaflow.agent_workspace.archive._learning_from_jsonl_obj`.
    """
    learnings: list[Learning] = []
    text = path.read_text(encoding="utf-8")
    for line_no, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            raise MemoryBridgeError(
                f"learnings.jsonl at {path!s} has malformed JSON on line {line_no}: {exc.msg}"
            ) from exc
        learning = _learning_from_obj(obj)
        if learning is None:
            logger.warning(
                "memory_bridge: skipping %s line %d (missing required Learning fields)",
                path,
                line_no,
            )
            continue
        learnings.append(learning)
    return learnings


def _learning_from_obj(obj: object) -> Learning | None:
    """Coerce a raw JSONL row dict into a :class:`Learning` (or ``None``).

    Mirrors :func:`devolaflow.agent_workspace.archive._learning_from_jsonl_obj`
    so this bridge accepts the same legacy / partial entries the v8.2.5
    ArchiveManager already tolerated. ``None`` is returned for rows
    missing the required Learning fields (``stage`` / ``task_type`` /
    ``key``); ``insight`` defaults to ``""`` when absent.
    """
    if not isinstance(obj, dict):
        return None
    key = obj.get("key")
    stage = obj.get("stage")
    task_type = obj.get("task_type")
    if not (key and stage and task_type):
        return None
    return Learning(
        stage=str(stage),
        task_type=str(task_type),
        key=str(key),
        insight=str(obj.get("insight", "")),
        confidence=float(obj.get("confidence", 0.5)),
        rule_id=str(obj.get("rule_id", "")),
        timestamp=str(obj.get("timestamp", "")),
        ttl_days=int(obj.get("ttl_days", 90)),
        source_task_id=str(obj.get("source_task_id", "") or ""),
        confidence_half_life_days=int(obj.get("confidence_half_life_days", 30)),
        last_accessed=str(obj.get("last_accessed", "") or ""),
        pinned_for_session=str(obj.get("pinned_for_session", "") or ""),
        promotion_count=int(obj.get("promotion_count", 0)),
        files=list(obj.get("files", []) or []),
        source=str(obj.get("source", "")),
    )


def _hydrate_markdown(path: Path, max_tokens: int) -> str | None:
    """Read a markdown artifact, truncating if it exceeds ``max_tokens``.

    Returns ``None`` when the file is absent (the consumer can branch
    on ``None`` to detect optional artifacts). When over budget, keeps
    the first ``max_tokens * 4`` characters minus the sentinel length
    and appends :data:`TRUNCATION_SENTINEL` on a fresh line.
    """
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    if estimate_tokens(text) <= max_tokens:
        return text
    keep_chars = max(0, max_tokens * 4 - len(TRUNCATION_SENTINEL) - 1)
    return text[:keep_chars].rstrip() + "\n" + TRUNCATION_SENTINEL


def _hydrate_status(path: Path, max_tokens: int) -> dict | None:
    """Parse STATUS.yaml; flag truncation but preserve the parsed mapping.

    YAML cannot be safely text-truncated mid-file (it would fail to
    parse), so for over-budget STATUS.yaml we still return the fully
    parsed dict but inject a ``"_truncated"`` key carrying
    :data:`TRUNCATION_SENTINEL` so consumers can detect the breach.
    """
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    parsed = yaml.safe_load(text)
    if not isinstance(parsed, dict):
        logger.warning(
            "memory_bridge: STATUS.yaml at %s did not parse as a mapping "
            "(got %s); returning empty dict",
            path,
            type(parsed).__name__,
        )
        return {}
    result = dict(parsed)
    if estimate_tokens(text) > max_tokens:
        result["_truncated"] = TRUNCATION_SENTINEL
    return result


def _hydrate_owned_files(path: Path, max_tokens: int) -> list[str]:
    """Parse owned_files.txt into a list[str]; truncate over-budget tails.

    One path per non-blank line. When the file's raw token count exceeds
    ``max_tokens``, keeps the longest prefix of lines that fits in the
    char budget and appends :data:`TRUNCATION_SENTINEL` as the final
    list entry (so consumers can detect / report the truncation).
    """
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    lines = [line for line in text.splitlines() if line.strip()]
    if estimate_tokens(text) <= max_tokens:
        return lines
    cap_chars = max(0, max_tokens * 4 - len(TRUNCATION_SENTINEL) - 1)
    kept: list[str] = []
    running = 0
    for line in lines:
        # +1 accounts for the implicit newline that joins entries.
        if running + len(line) + 1 > cap_chars:
            break
        kept.append(line)
        running += len(line) + 1
    kept.append(TRUNCATION_SENTINEL)
    return kept


def _hydrate_learnings(path: Path) -> list[Learning]:
    """Parse learnings.jsonl into a list[Learning] (no token cap).

    The file size is already bounded by
    :data:`devolaflow.agent_workspace.lint.LEARNINGS_JSONL_MAX_BYTES`
    (50 KB), so no additional truncation is applied here. Malformed
    lines are logged and skipped (NOT raised) — for hydration we prefer
    a partial list over a crash, since the consumer is reading context,
    not running consolidation. Loud-on-malformed is reserved for
    :func:`consolidate_change_on_archive`.
    """
    if not path.exists():
        return []
    learnings: list[Learning] = []
    text = path.read_text(encoding="utf-8")
    for line_no, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            logger.warning(
                "memory_bridge.hydrate: skipping malformed JSON at %s:%d",
                path,
                line_no,
            )
            continue
        learning = _learning_from_obj(obj)
        if learning is not None:
            learnings.append(learning)
    return learnings


def _hydrate_evidence(path: Path) -> dict[str, str]:
    """Return checklist evidence as ``basename -> verbatim text``.

    Only regular ``*.txt`` files participate in the canonical evidence set.
    Sorted traversal gives callers deterministic insertion order without
    altering file contents. A missing evidence directory returns ``{}``.
    """
    if not path.is_dir():
        return {}
    return {
        evidence_path.name: evidence_path.read_text(encoding="utf-8")
        for evidence_path in sorted(path.glob("*.txt"))
        if evidence_path.is_file()
    }
