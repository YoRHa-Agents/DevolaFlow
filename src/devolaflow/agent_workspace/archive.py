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
:meth:`ArchiveManager.apply_merge` (v8.4.4 PV-04 closure) writes the
proposed content atomically AFTER verifying the gate score clears the
W-3 / SI-3 threshold (≥ 8.5 PATCH/MINOR; ≥ 9.0 MAJOR) per Rule A-4.

v9.1.5 PV-05 — when :meth:`ArchiveManager.archive` is invoked with
``propose_merge=True``, the resulting :class:`ArchiveResult` carries the
:class:`ProposedMerge` for caller inspection but does NOT auto-apply
(callers explicitly invoke :meth:`apply_merge` or use the dedicated
``seed_initial_spec`` first-time seed surface — see
:mod:`devolaflow.agent_workspace.spec_bootstrap`).

Public API:

* :class:`ArchiveManager` — archive + propose_merge + apply_merge.
* :class:`ArchiveResult` — return value of ``archive()``.
* :class:`ProposedMerge` — return value of ``propose_merge()``.
* :class:`AppliedMerge` — return value of ``apply_merge()``.
* :exc:`ArchiveError` — generic archive-side error.
* :exc:`GateThresholdNotMet` — raised by ``apply_merge`` when gate < threshold.
* :exc:`MergeConflict` — raised by ``propose_merge`` on stable-heading collision.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from devolaflow.agent_workspace.archive_recovery import (
    ArchiveAttemptGuard,
    ArchiveRollbackError,
)
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

logger = logging.getLogger(__name__)

__all__ = [
    "AppliedMerge",
    "ArchiveError",
    "ArchiveManager",
    "ArchiveResult",
    "GateThresholdNotMet",
    "MergeConflict",
    "ProposedMerge",
]


SOURCE_OF_TRUTH_ROOT_DEFAULT: Path = Path(".local") / "memory" / "specs"
GLOBAL_LEARNINGS_DEFAULT: Path = Path(".local") / "memory" / "operational.jsonl"

# v8.4.4 PV-04 — apply_merge gate thresholds aligned with W-3 / SI-3
# composite-score policy. PATCH/MINOR changes require ≥ 8.5; MAJOR
# changes require ≥ 9.0. See `.local/research/v9.0.0_pv04_design.md` §2.
GATE_THRESHOLD_DEFAULT: float = 8.5
GATE_THRESHOLD_MAJOR: float = 9.0

# Harness-construction archive gate (design §4, decision 5). A change is
# harness-flagged iff HARNESS_PREFLIGHT_FILENAME exists in its change folder
# (artifact-as-contract; W-20 reuse-first). Flagged changes REQUIRE a
# non-empty capability review at archive time; delta VALUES are trends only.
HARNESS_PREFLIGHT_FILENAME: str = "harness_preflight.md"
HARNESS_CAPABILITY_REVIEW_RELPATH: str = "evidence/harness_capability_review.md"


class ArchiveError(RuntimeError):
    """Generic error raised by :class:`ArchiveManager`."""


class GateThresholdNotMet(ArchiveError):  # noqa: N818 — public API name pinned by v8.4.4 PV-04 design.md §2.3 + symmetry with sibling MergeConflict per the v8.3.0 patch_plan §v8.2.5 naming convention; ArchiveError suffix is implicit through the parent class.
    """Raised by :meth:`ArchiveManager.apply_merge` when gate score is below threshold.

    Per Rule A-4 (`.cursor/rules/repo-governance.mdc` §"A-4 — Source-of-
    Truth Spec Location"), source-of-truth files (.local/memory/specs/
    <domain>/spec.md) are mutated ONLY at archive time AFTER the gate
    has PASSED. The default thresholds match W-3 / SI-3:

    - PATCH/MINOR change → composite ≥ 8.5
    - MAJOR change       → composite ≥ 9.0

    Raised verbatim with the gate score + threshold so callers can
    surface the exact gap to the operator (S-5 — no silent failures).
    """


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
class AppliedMerge:
    """Result returned by :meth:`ArchiveManager.apply_merge`.

    Carries the on-disk path that received the new source-of-truth
    content + the verbatim ``gate_score`` consulted to authorise the
    write. Per A-4 + W-3 / SI-3, the gate score MUST be ≥ 8.5 (PATCH/
    MINOR) or ≥ 9.0 (MAJOR) for the write to occur — see
    :exc:`GateThresholdNotMet` for the failure path.

    Attributes:
      change_id: id of the change whose spec.md was applied.
      delta_target: ``frontmatter.delta_target`` from the change spec.
      applied_path: on-disk path of the written source-of-truth spec
        (``.local/memory/specs/<delta_target>/spec.md`` by default).
      gate_score: verbatim gate composite score consulted at apply time.
      threshold: the threshold the gate score had to clear (8.5 or 9.0).
      summary: per-section counters (added / modified / removed) from
        :func:`_merge_delta_into_source` — useful for audit-trail logs.
      bytes_written: number of bytes written to ``applied_path``.
    """

    change_id: str
    delta_target: str
    applied_path: Path
    gate_score: float
    threshold: float
    summary: dict = field(default_factory=dict)
    bytes_written: int = 0


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
        auto_regenerate_reports: bool = True,
    ) -> ArchiveResult:
        """Archive an active change.

        Args:
          change_id: id of the active change to archive.
          archive_date: explicit ``YYYY-MM-DD`` prefix for the archive folder
            (defaults to today's UTC date). Pinning is useful for tests +
            replay.
          propose_merge: when True, run :meth:`propose_merge` after the
            move and attach the result to the returned :class:`ArchiveResult`.
            v9.1.5 PV-05 wiring clarification: ``archive(propose_merge=True)``
            ONLY computes the merged content — it does NOT auto-apply. The
            caller decides whether to invoke :meth:`apply_merge` (which
            enforces the W-3 / SI-3 gate-score threshold per Rule A-4) or
            to inspect ``ArchiveResult.proposed_merge.content`` for review.
            For first-time source-of-truth seeding (NEW domain, no existing
            spec on disk), use
            :func:`devolaflow.agent_workspace.spec_bootstrap.seed_initial_spec`
            instead — it gates on filesystem absence (the A-4 first-time-seed
            invariant) rather than gate-score, and is the canonical surface
            for repo-init / new-domain bootstrap.
          require_state: required pre-archive state (default ``"VERIFYING"``
            per the design FSM §1.3). Pass ``None`` to skip the check —
            useful for tests that bypass the verify stage.
          auto_regenerate_reports: when True (default — v8.4.4 PV-04
            I-PV07-A closure), automatically regenerates the per-change
            ``REPORT.md`` (in the archive folder) AND the workspace-wide
            ``.local/.agent/REPORT.md`` after the move + consolidation.
            Permissive — render failures are logged but do NOT raise so
            the archive itself stays atomic. Set to ``False`` for tests
            that need byte-pinned filesystem state.

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

        active_path = self.store.active_root / change_id
        guard = ArchiveAttemptGuard.capture(
            change_id=change_id,
            active_path=active_path,
            global_path=self._resolved_global_learnings,
        )

        try:
            # Harness-construction archive gate: runs BEFORE any STATUS
            # mutation so a failed gate leaves the active folder untouched.
            # Non-flagged changes pay exactly one flag-file existence test.
            self._guard_harness_capability_review(change_id, active_path)

            # Step 1: rewrite STATUS.yaml so state == ARCHIVED before the move.
            # The Change.with_state call enforces the legal transition matrix.
            archived_change = change.with_state("ARCHIVED")
            guard.mutation_started = True
            archived_change.to_active_folder(active_path)

            # Step 2: physically move the folder.
            archive_target = self.store.move_to_archive(change_id, archive_date=archive_date)
            guard.archive_target = archive_target

            # Step 3: consolidate per-change learnings into the global JSONL.
            counts = self._consolidate_change_learnings(change_id, archive_target)
        except Exception as exc:
            try:
                guard.rollback()
            except ArchiveRollbackError as rollback_exc:
                raise ArchiveError(str(rollback_exc)) from rollback_exc
            raise ArchiveError(
                f"archive for {change_id!r} failed before completion; "
                f"the active change was retained and recovery was verified: {exc}"
            ) from exc

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

        # Step 5 (v8.4.4 PV-04 I-PV07-A closure): auto-regenerate the
        # per-change + workspace REPORT.md so the human-readable audit
        # surface reflects the new ARCHIVED state without requiring an
        # explicit `python -m devolaflow.agent_workspace.reporter --all`
        # invocation. Permissive: render failures are logged but never
        # raise (REPORT.md is a presentation surface, not an integrity
        # contract).
        if auto_regenerate_reports:
            self._auto_regenerate_reports(change_id, archive_target)

        return ArchiveResult(
            change_id=change_id,
            archive_path=archive_target,
            consolidated_counts=counts,
            proposed_merge=proposal,
        )

    def _guard_harness_capability_review(self, change_id: str, active_path: Path) -> None:
        """Existence-only archive gate for harness-flagged changes.

        A change is harness-flagged iff :data:`HARNESS_PREFLIGHT_FILENAME`
        exists in its change folder (artifact-as-contract). Flagged changes
        REQUIRE a non-empty :data:`HARNESS_CAPABILITY_REVIEW_RELPATH` (from
        ``harness gap --compare``) before the move; delta values are trends
        only and are NOT inspected here. Non-flagged changes pay a single
        flag-file existence test. Raises :exc:`ArchiveError` (loud per S-5)
        when the flagged review artifact is missing or empty.
        """
        flag_path = active_path / HARNESS_PREFLIGHT_FILENAME
        if not flag_path.is_file():
            return
        review_path = active_path / HARNESS_CAPABILITY_REVIEW_RELPATH
        if not review_path.is_file() or review_path.stat().st_size == 0:
            raise ArchiveError(
                f"cannot archive harness-flagged change {change_id!r}: the "
                f"capability review artifact {review_path!s} is missing or "
                f"empty; the change is flagged by {HARNESS_PREFLIGHT_FILENAME} "
                f"so `python -m devolaflow.harness gap --compare` must produce "
                f"{HARNESS_CAPABILITY_REVIEW_RELPATH} before archive "
                f"(existence-only gate; delta values are recorded trends, "
                f"not PASS conditions)"
            )

    def _auto_regenerate_reports(self, change_id: str, archive_path: Path) -> None:
        """Auto-regenerate per-change + workspace REPORT.md after archive.

        v8.4.4 PV-04 — I-PV07-A closure. Permissive: any render failure is
        logged at WARNING (S-5 — never silent) but NEVER raises out of
        :meth:`archive`. Two writes are attempted: ``<archive_path>/REPORT.md``
        (``reporter.render_change_report``) and ``.local/.agent/REPORT.md``
        (``reporter.render_workspace_report``).
        """
        try:
            from devolaflow.agent_workspace.reporter import (
                WORKSPACE_REPORT_PATH_DEFAULT,
                render_change_report,
                render_workspace_report,
            )
        except ImportError as exc:  # pragma: no cover - defensive only
            logger.warning(
                "auto_regenerate_reports: reporter unavailable for %s: %s",
                change_id,
                exc,
            )
            return

        repo_root = self.store.repo_root

        try:
            change_text = render_change_report(change_id, repo_root=repo_root)
            change_report_path = archive_path / "REPORT.md"
            change_report_path.write_text(
                change_text if change_text.endswith("\n") else change_text + "\n",
                encoding="utf-8",
                newline="\n",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "auto_regenerate_reports: per-change REPORT.md for %s failed: %s",
                change_id,
                exc,
            )

        try:
            workspace_text = render_workspace_report(repo_root=repo_root)
            workspace_path = repo_root / WORKSPACE_REPORT_PATH_DEFAULT
            workspace_path.parent.mkdir(parents=True, exist_ok=True)
            workspace_path.write_text(
                workspace_text if workspace_text.endswith("\n") else workspace_text + "\n",
                encoding="utf-8",
                newline="\n",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "auto_regenerate_reports: workspace REPORT.md after %s failed: %s",
                change_id,
                exc,
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

        Does NOT write to disk — write-side is :meth:`apply_merge` (v8.4.4
        PV-04, M-004 / A-4 closure). Per design.md §3.4 (Rule A-4),
        source-of-truth is mutated ONLY at archive time AFTER the gate
        has PASSED; ``propose_merge`` is the read-side companion that
        builds the merged content for review BEFORE the gate runs.

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

    def apply_merge(
        self,
        change_id: str,
        *,
        is_major_change: bool = False,
        require_gate_score: float | None = None,
    ) -> AppliedMerge:
        """Write the proposed delta-merged source-of-truth spec to disk.

        v8.4.4 PV-04 — closes M-004 + A-4 ADR full closure. Per Rule A-4
        (`.cursor/rules/repo-governance.mdc` §"A-4 — Source-of-Truth
        Spec Location"), source-of-truth files at
        ``.local/memory/specs/<domain>/spec.md`` are mutated ONLY at
        archive time AFTER the gate has PASSED. This method enforces
        that contract:

        1. Calls :meth:`propose_merge` to build the merged content.
        2. Reads ``change.status['gate_score']`` (verbatim, no synthesis).
        3. Compares against the threshold:
           - PATCH/MINOR change → ``GATE_THRESHOLD_DEFAULT`` (8.5)
           - MAJOR change       → ``GATE_THRESHOLD_MAJOR`` (9.0)
           - Caller override    → ``require_gate_score`` parameter
        4. If gate < threshold → raises :exc:`GateThresholdNotMet` with
           verbatim score + threshold; nothing is written.
        5. Otherwise: atomic write (POSIX ``rename``) to ``target_path``
           via a ``.tmp`` sibling, so readers never see a half-written
           spec. Returns :class:`AppliedMerge` with bytes written +
           audit summary.

        Args:
          change_id: id of an archived (or VERIFYING) change.
          is_major_change: when ``True``, requires ``gate_score >= 9.0``
            (MAJOR-bump threshold). Defaults to ``False`` (PATCH/MINOR
            threshold of 8.5).
          require_gate_score: explicit threshold override (use when the
            calling workflow has its own gate policy). When ``None``,
            the default tier-based threshold applies.

        Returns:
          :class:`AppliedMerge` with the on-disk path + gate metadata.

        Raises:
          GateThresholdNotMet: when the change's gate score is below the
            threshold (PATCH/MINOR ≥ 8.5; MAJOR ≥ 9.0).
          ChangeNotFoundError: when the change is unknown.
          DeltaSpecParseError: when the change's ``spec.md`` is malformed.
          MergeConflict: on stable-heading collisions (delegated from
            :meth:`propose_merge`).
          ArchiveError: when the spec is missing ``delta_target``
            frontmatter or the change has no ``gate_score`` recorded
            (S-5 — no silent fallback to a default score).
        """
        proposal = self.propose_merge(change_id)

        change = self.store.get(change_id)
        gate_score_raw = change.status.get("gate_score")
        if gate_score_raw is None:
            raise ArchiveError(
                f"apply_merge: change {change_id!r} has no gate_score in STATUS.yaml; "
                f"cannot authorise source-of-truth mutation per Rule A-4 "
                f"(see .cursor/rules/repo-governance.mdc §A-4)"
            )
        try:
            gate_score = float(gate_score_raw)
        except (TypeError, ValueError) as exc:
            raise ArchiveError(
                f"apply_merge: change {change_id!r} has invalid gate_score "
                f"{gate_score_raw!r} (must be float)"
            ) from exc

        if require_gate_score is not None:
            threshold = float(require_gate_score)
        elif is_major_change:
            threshold = GATE_THRESHOLD_MAJOR
        else:
            threshold = GATE_THRESHOLD_DEFAULT

        if gate_score < threshold:
            tier_label = "MAJOR" if is_major_change else "PATCH/MINOR"
            raise GateThresholdNotMet(
                f"apply_merge: change {change_id!r} gate_score {gate_score:.2f} "
                f"is below the {tier_label} threshold {threshold:.2f}; "
                f"source-of-truth NOT mutated per Rule A-4"
            )

        applied_path = proposal.target_path
        applied_path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write: stage to .tmp sibling, then POSIX rename.
        tmp_path = applied_path.with_suffix(applied_path.suffix + ".tmp")
        content = proposal.content if proposal.content.endswith("\n") else proposal.content + "\n"
        tmp_path.write_text(content, encoding="utf-8", newline="\n")
        tmp_path.replace(applied_path)
        bytes_written = len(content.encode("utf-8"))

        logger.info(
            "apply_merge: change %s applied to %s (gate=%.2f >= %.2f, %d bytes)",
            change_id,
            applied_path,
            gate_score,
            threshold,
            bytes_written,
        )

        return AppliedMerge(
            change_id=change_id,
            delta_target=proposal.delta_target,
            applied_path=applied_path,
            gate_score=gate_score,
            threshold=threshold,
            summary=dict(proposal.summary),
            bytes_written=bytes_written,
        )

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
