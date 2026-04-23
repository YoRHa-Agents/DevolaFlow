"""ArchiveManager — move active changes to archive + propose delta merges.

Closes the C-003 archive half + part of M-004 per
``.local/research/v8.3.0_gap_analysis.md`` §2.1, §2.3.

:class:`ArchiveManager.archive` performs the lifecycle move:

1. Resolve the active change folder under ``.local/.agent/active/<id>/``.
2. Verify the change is in a terminal-eligible state (VERIFYING).
3. Mutate ``STATUS.yaml`` so ``state == ARCHIVED`` and ``last_updated``
   refreshes (round-trip via :class:`Change.with_state`).
4. Move ``active/<id>/`` → ``archive/<YYYY-MM-DD>-<id>/``.
5. If a per-change ``learnings.jsonl`` is present, call
   ``devolaflow.learnings.consolidate_session`` to promote durable
   learnings to the global JSONL substrate (per
   ``.local/research/v8.3.0_design.md`` §4.2). The full ``v8.2.8`` memory
   bridge wiring (extra ``change_id`` parameters on
   ``capture_session_reflection`` / ``load_relevant_learnings``) is
   intentionally deferred — this PV calls the existing
   ``consolidate_session`` signature (R5: zero edits to ``learnings.py``).
6. Return an :class:`ArchiveResult` summarising the move + consolidation.

:meth:`ArchiveManager.propose_merge` produces the proposed delta-merged
source-of-truth spec content WITHOUT writing it to disk. The write-side
(``ArchiveManager.apply_merge``) is intentionally deferred to v8.2.7
reporter — per design.md §3.4 (Rule A-4), source-of-truth files are
mutated ONLY at archive time AFTER the gate has PASSED, and the gate's
``mergeability_check`` lives in the v8.2.7 reporter module.

Public API:

* :class:`ArchiveManager` — archive + propose_merge.
* :class:`ArchiveResult` — return value of ``archive()``.
* :class:`ProposedMerge` — return value of ``propose_merge()``.
* :exc:`ArchiveError` — generic archive-side error.
* :exc:`MergeConflict` — raised by ``propose_merge`` on stable-heading collision.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from devolaflow.agent_workspace.change import (
    Change,
    ChangeNotFoundError,
    ChangeStore,
)
from devolaflow.agent_workspace.delta_parser import (
    DeltaRequirement,
    DeltaSpec,
    DeltaSpecParseError,
    parse_delta_spec,
)
from devolaflow.learnings import Learning, consolidate_session

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

__all__ = [
    "ArchiveError",
    "ArchiveManager",
    "ArchiveResult",
    "MergeConflict",
    "ProposedMerge",
]


SOURCE_OF_TRUTH_ROOT_DEFAULT: Path = Path(".local") / "memory" / "specs"
GLOBAL_LEARNINGS_DEFAULT: Path = Path(".local") / "memory" / "operational.jsonl"


class ArchiveError(RuntimeError):
    """Generic error raised by :class:`ArchiveManager`."""


class MergeConflict(ArchiveError):  # noqa: N818 — public API name pinned by v8.3.0 patch_plan §v8.2.5 + schemas/agent-workspace/source-of-truth-spec.yaml#mutation_contract.delta_application_rules
    """Raised by :meth:`ArchiveManager.propose_merge` on a stable-heading collision.

    Per ``schemas/agent-workspace/source-of-truth-spec.yaml#mutation_contract``:

    * ADDED Requirements MUST be unique by stable heading; duplicate heading
      → MergeConflict.
    * MODIFIED Requirements MUST match an existing heading in source-of-truth;
      missing match → MergeConflict.
    * REMOVED Requirements MUST match an existing heading in source-of-truth;
      missing match → MergeConflict.

    Suppressed ruff N818 — the spec ``schemas/agent-workspace/source-of-truth-
    spec.yaml#mutation_contract.delta_application_rules`` and the v8.3.0
    patch_plan §v8.2.5 acceptance criteria pin this exact public identifier.
    """


@dataclass
class ArchiveResult:
    """Result returned by :meth:`ArchiveManager.archive`.

    Attributes:
      change_id: The archived change-id.
      archive_path: Final destination folder (``archive/<date>-<id>/``).
      consolidated_counts: ``{promoted, captured, skipped}`` counters from
        ``consolidate_session`` — all zero when no per-change
        ``learnings.jsonl`` was present.
      proposed_merge: Optional :class:`ProposedMerge` when ``--propose-merge``
        was requested via ``ArchiveManager.archive(..., propose_merge=True)``.
    """

    change_id: str
    archive_path: Path
    consolidated_counts: dict
    proposed_merge: ProposedMerge | None = None


@dataclass
class ProposedMerge:
    """Proposed delta-merge result returned by :meth:`ArchiveManager.propose_merge`.

    The ``content`` string is the full text of the proposed updated
    source-of-truth spec; callers (typically the v8.2.7 reporter) decide
    whether to write it. The ``target_path`` is the path the content
    WOULD be written to (``.local/memory/specs/<delta_target>/spec.md``).

    ``conflicts`` is empty on success; populated when a non-fatal
    conflict was downgraded to a warning (currently always empty —
    fatal conflicts raise :exc:`MergeConflict` instead).
    """

    change_id: str
    delta_target: str
    target_path: Path
    content: str
    summary: dict = field(default_factory=dict)
    conflicts: list[str] = field(default_factory=list)


@dataclass
class ArchiveManager:
    """Orchestrates the active → archive lifecycle move + delta-merge proposal.

    ``ArchiveManager.archive`` is idempotent on a per-change-id basis — a
    second call after the change has already been archived returns the
    existing archive path with empty consolidation counters.

    Attributes:
      store: The :class:`ChangeStore` used to read/write change folders.
      source_of_truth_root: Override for ``.local/memory/specs/``. Used by
        :meth:`propose_merge` to locate the source-of-truth spec.
      global_learnings_path: Override for ``.local/memory/operational.jsonl``.
        Passed to ``consolidate_session`` during archive.
    """

    store: ChangeStore = field(default_factory=ChangeStore)
    source_of_truth_root: Path = field(default_factory=lambda: Path(SOURCE_OF_TRUTH_ROOT_DEFAULT))
    global_learnings_path: Path = field(default_factory=lambda: Path(GLOBAL_LEARNINGS_DEFAULT))

    @property
    def _resolved_source_root(self) -> Path:
        return (
            self.source_of_truth_root
            if self.source_of_truth_root.is_absolute()
            else self.store.repo_root / self.source_of_truth_root
        )

    @property
    def _resolved_global_learnings(self) -> Path:
        return (
            self.global_learnings_path
            if self.global_learnings_path.is_absolute()
            else self.store.repo_root / self.global_learnings_path
        )

    def archive(
        self,
        change_id: str,
        *,
        archive_date: str | None = None,
        propose_merge: bool = False,
        require_state: str | None = "VERIFYING",
    ) -> ArchiveResult:
        """Archive an active change.

        Args:
          change_id: id of the active change to archive.
          archive_date: explicit ``YYYY-MM-DD`` prefix for the archive folder
            (defaults to today's UTC date). Pinning is useful for tests +
            replay.
          propose_merge: when True, run :meth:`propose_merge` after the
            move and attach the result to the returned :class:`ArchiveResult`.
          require_state: required pre-archive state (default ``"VERIFYING"``
            per the design FSM §1.3). Pass ``None`` to skip the check —
            useful for tests that bypass the verify stage.

        Returns:
          :class:`ArchiveResult` with the destination path + consolidation
          counters (and optionally a :class:`ProposedMerge`).

        Raises:
          ChangeNotFoundError: when ``change_id`` is not active or already archived.
          ArchiveError: when state guard fails OR archive target collision OR
            consolidation raises (loud per S-5).
        """
        # Idempotency: if already archived, return the existing path.
        if not self.store.has_active(change_id):
            existing = self.store.find_archived_path(change_id)
            if existing is not None:
                return ArchiveResult(
                    change_id=change_id,
                    archive_path=existing,
                    consolidated_counts={"promoted": 0, "captured": 0, "skipped": 0},
                )
            raise ChangeNotFoundError(
                f"cannot archive {change_id!r}: not present in active or archive"
            )

        change = self.store.get(change_id)
        current_state = change.state
        if require_state is not None and current_state != require_state:
            raise ArchiveError(
                f"cannot archive {change_id!r}: state is {current_state!r} but "
                f"archive requires {require_state!r} "
                f"(per .local/research/v8.3.0_design.md §1.3 lifecycle FSM)"
            )

        # Step 1: rewrite STATUS.yaml so state == ARCHIVED before the move.
        # The Change.with_state call enforces the legal transition matrix.
        archived_change = change.with_state("ARCHIVED")
        active_path = self.store.active_root / change_id
        archived_change.to_active_folder(active_path)

        # Step 2: physically move the folder.
        archive_target = self.store.move_to_archive(change_id, archive_date=archive_date)

        # Step 3: consolidate per-change learnings into the global JSONL.
        counts = self._consolidate_change_learnings(change_id, archive_target)

        # Step 4 (optional): build the proposed delta merge.
        proposal: ProposedMerge | None = None
        if propose_merge:
            try:
                proposal = self._propose_merge_from_archive(change_id, archive_target)
            except (DeltaSpecParseError, ArchiveError) as exc:
                # Loud but recoverable — caller can inspect summary.
                logger.warning(
                    "archive: propose_merge for %s failed: %s",
                    change_id,
                    exc,
                )
                proposal = None

        return ArchiveResult(
            change_id=change_id,
            archive_path=archive_target,
            consolidated_counts=counts,
            proposed_merge=proposal,
        )

    def _consolidate_change_learnings(self, change_id: str, archive_path: Path) -> dict:
        """Promote per-change learnings to global memory via ``consolidate_session``.

        When ``learnings.jsonl`` is absent (the change recorded no per-task
        reflections), returns ``{promoted: 0, captured: 0, skipped: 0}``
        without invoking the consolidator.
        """
        per_change_path = archive_path / "learnings.jsonl"
        if not per_change_path.exists():
            return {"promoted": 0, "captured": 0, "skipped": 0}

        learnings: list[Learning] = []
        for line_no, raw in enumerate(
            per_change_path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            line = raw.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                # Loud per S-5 — a corrupt learnings.jsonl is a data integrity
                # incident worth surfacing rather than silently skipping.
                raise ArchiveError(
                    f"learnings.jsonl in {archive_path!s} has malformed JSON on "
                    f"line {line_no}: {exc.msg}"
                ) from exc
            learning = _learning_from_jsonl_obj(obj)
            if learning is None:
                # Schema field absent — skip but log; do not raise.
                logger.info(
                    "archive: skipping learnings.jsonl line %d (missing required fields)",
                    line_no,
                )
                continue
            learnings.append(learning)

        global_jsonl = self._resolved_global_learnings
        global_jsonl.parent.mkdir(parents=True, exist_ok=True)
        if not global_jsonl.exists():
            global_jsonl.touch()
        return consolidate_session(
            session_id=f"archive-{change_id}",
            session_learnings=learnings,
            jsonl_path=global_jsonl,
        )

    def propose_merge(self, change_id: str) -> ProposedMerge:
        """Produce the proposed delta-merged source-of-truth spec content.

        Does NOT write to disk — write-side ships in v8.2.7 reporter per
        design.md §3.4 (Rule A-4: source-of-truth mutated ONLY at archive
        time AFTER the gate has PASSED).

        Args:
          change_id: id of an archived (or VERIFYING) change with a
            populated ``spec.md`` delta.

        Returns:
          :class:`ProposedMerge` with the merged content + target path.

        Raises:
          ChangeNotFoundError: when ``change_id`` is unknown.
          DeltaSpecParseError: when the change's ``spec.md`` is malformed.
          MergeConflict: on stable-heading collisions (see :class:`MergeConflict`).
          ArchiveError: when the spec is missing ``delta_target`` frontmatter.
        """
        change = self.store.get(change_id)
        # Determine the on-disk path the change lives at (active or archive).
        change_path = change.source_folder
        if change_path is None:
            raise ChangeNotFoundError(
                f"propose_merge: change {change_id!r} has no resolvable source folder"
            )
        return self._propose_merge_from_archive(change_id, change_path, change=change)

    def _propose_merge_from_archive(
        self,
        change_id: str,
        change_folder: Path,
        *,
        change: Change | None = None,
    ) -> ProposedMerge:
        """Internal — propose_merge against an arbitrary change folder."""
        if change is None:
            change = Change.from_active_folder(change_folder)
        if not change.spec_md.strip():
            raise ArchiveError(
                f"propose_merge: change {change_id!r} has no spec.md content "
                f"to merge (folder: {change_folder!s})"
            )
        delta = parse_delta_spec(change.spec_md)
        delta_target = str(delta.frontmatter.get("delta_target", "")).strip()
        if not delta_target:
            raise ArchiveError(
                f"propose_merge: change {change_id!r} spec.md is missing the "
                f"frontmatter `delta_target` field "
                f"(see schemas/agent-workspace/change-spec.yaml#frontmatter.required)"
            )

        target_path = self._resolved_source_root / delta_target / "spec.md"
        existing_text = target_path.read_text(encoding="utf-8") if target_path.exists() else ""

        merged_text, summary = _merge_delta_into_source(
            existing_text=existing_text,
            delta=delta,
            change_id=change_id,
            delta_target=delta_target,
        )

        return ProposedMerge(
            change_id=change_id,
            delta_target=delta_target,
            target_path=target_path,
            content=merged_text,
            summary=summary,
        )


# ---------------------------------------------------------------------------
# Helpers — delta-merge engine + JSONL learnings adapter
# ---------------------------------------------------------------------------


def _learning_from_jsonl_obj(obj: dict) -> Learning | None:
    """Coerce a raw JSONL row into a :class:`Learning`; return ``None`` on incompleteness.

    Mirrors the conservative behaviour of ``learnings.py::_entry_to_learning``
    so consolidation does not blow up on legacy entries that pre-date the
    later schema fields. ``None`` is returned for entries missing required
    Learning fields (``key`` / ``stage`` / ``task_type``); ``insight`` defaults
    to an empty string when absent (it has no default in the dataclass but is
    not part of the consolidation key).
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


def _merge_delta_into_source(
    *,
    existing_text: str,
    delta: DeltaSpec,
    change_id: str,
    delta_target: str,
) -> tuple[str, dict]:
    """Merge ``delta`` into ``existing_text`` and return ``(merged_text, summary)``.

    Implementation follows
    ``schemas/agent-workspace/source-of-truth-spec.yaml#mutation_contract``:

    * ADDED Requirements are appended verbatim — duplicate stable heading
      raises :class:`MergeConflict`.
    * MODIFIED Requirements REPLACE matching ``## Requirement:`` sections
      verbatim — missing match raises :class:`MergeConflict`.
    * REMOVED Requirements DELETE matching sections verbatim — missing
      match raises :class:`MergeConflict`.

    The returned ``summary`` dict carries per-section counters (``added`` /
    ``modified`` / ``removed``) so the caller (typically the v8.2.7
    reporter) can render a concise audit-trail string.
    """
    headings = _parse_existing_headings(existing_text)
    summary = {
        "added": 0,
        "modified": 0,
        "removed": 0,
        "delta_target": delta_target,
        "change_id": change_id,
    }

    if not existing_text.strip():
        # New domain — synthesize the H1 + frontmatter scaffold.
        existing_text = (
            f"---\n"
            f"domain: {delta_target}\n"
            f"schema_version: 1\n"
            f"last_merged_change: null\n"
            f"last_merged_at: null\n"
            f"---\n\n"
            f"# Spec: {delta_target} \u2014 Source-of-Truth\n\n"
        )
        headings = {}

    body_lines = existing_text.splitlines()

    # 1. ADDED — verify uniqueness, then append at end-of-file.
    for req in delta.added:
        if req.heading in headings:
            raise MergeConflict(
                f"ADDED Requirement {req.heading!r} already exists in "
                f"source-of-truth {delta_target!r}; "
                f"author a MODIFIED Requirement instead"
            )

    # 2. MODIFIED — verify matches exist; replace inline.
    for req in delta.modified:
        if req.heading not in headings:
            raise MergeConflict(
                f"MODIFIED Requirement {req.heading!r} has no matching "
                f"`## Requirement:` heading in source-of-truth {delta_target!r}; "
                f"author an ADDED Requirement instead"
            )

    # 3. REMOVED — verify matches exist; delete inline.
    for req in delta.removed:
        if req.heading not in headings:
            raise MergeConflict(
                f"REMOVED Requirement {req.heading!r} has no matching "
                f"`## Requirement:` heading in source-of-truth {delta_target!r}; "
                f"nothing to remove"
            )

    body_lines = _apply_replacements(
        body_lines,
        modifications=delta.modified,
        removals=delta.removed,
    )
    summary["modified"] = len(delta.modified)
    summary["removed"] = len(delta.removed)

    # Append ADDED Requirements at end-of-file.
    if delta.added:
        if body_lines and body_lines[-1].strip():
            body_lines.append("")
        for req in delta.added:
            body_lines.append(f"## Requirement: {req.heading}")
            if req.body:
                body_lines.append(req.body)
            body_lines.append("")
        summary["added"] = len(delta.added)

    merged = "\n".join(body_lines).rstrip("\n") + "\n"
    return merged, summary


def _parse_existing_headings(text: str) -> dict[str, tuple[int, int]]:
    """Return ``{heading: (start_line, end_line_exclusive)}`` for each ``## Requirement:`` block."""
    if not text.strip():
        return {}
    lines = text.splitlines()
    headings: dict[str, tuple[int, int]] = {}
    n = len(lines)
    cursor = 0
    while cursor < n:
        line = lines[cursor]
        if line.startswith("## Requirement: "):
            heading = line[len("## Requirement: ") :].strip()
            start = cursor
            cursor += 1
            while cursor < n and not lines[cursor].startswith("## "):
                cursor += 1
            headings[heading] = (start, cursor)
        else:
            cursor += 1
    return headings


def _apply_replacements(
    body_lines: list[str],
    *,
    modifications: list[DeltaRequirement],
    removals: list[DeltaRequirement],
) -> list[str]:
    """Apply MODIFIED + REMOVED edits to ``body_lines`` in a single pass.

    Both lists key on stable heading text (verbatim match required). The
    edits are applied right-to-left so line numbers stay valid as we
    splice. Returns a new list (no in-place mutation).
    """
    headings = _parse_existing_headings("\n".join(body_lines))
    if not modifications and not removals:
        return body_lines

    # Build the edit plan as a list of (start, end, replacement_lines) tuples
    # then apply right-to-left so indices remain valid.
    plan: list[tuple[int, int, list[str]]] = []
    for req in modifications:
        start, end = headings[req.heading]
        block = [f"## Requirement: {req.heading}"]
        if req.body:
            block.append(req.body)
        # Preserve the trailing blank line if the original had one.
        if end < len(body_lines) and body_lines[end - 1].strip() == "":
            block.append("")
        plan.append((start, end, block))
    for req in removals:
        start, end = headings[req.heading]
        # Drop the trailing blank line if present, to avoid double-blank.
        drop_end = end
        if drop_end < len(body_lines) and body_lines[drop_end - 1].strip() == "":
            pass
        plan.append((start, drop_end, []))

    plan.sort(key=lambda t: t[0], reverse=True)
    out = list(body_lines)
    for start, end, replacement in plan:
        out[start:end] = replacement
    return out
