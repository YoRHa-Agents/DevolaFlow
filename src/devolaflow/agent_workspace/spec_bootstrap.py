"""Source-of-truth spec bootstrap — first-time seeding from a verified archive.

Closes M-004 deferred from the v9.0.0 retrospective §3.3 per
``.cursor/plans/workspace-capability-activation_ec560bc8.plan.md`` §PV-05.

A new DevolaFlow repo's ``.local/memory/specs/`` is empty by default — the
source-of-truth contract per Rule A-4 says specs are mutated ONLY at archive
time AFTER the gate has PASSED. That contract assumes the source-of-truth
already exists; it is silent on how to populate the FIRST entry for a domain.

:func:`seed_initial_spec` closes that gap. Given a verified archive folder
under ``.local/.agent/archive/<archive_id>/`` and a target ``domain``, it:

1. Validates the archive folder exists and contains a ``spec.md``.
2. Validates the target ``.local/memory/specs/<domain>/spec.md`` is absent
   (A-4 invariant — first-time seed only). When ``force=True`` the existing
   target is overwritten with a WARNING log (S-5 — never silent).
3. Invokes :meth:`devolaflow.agent_workspace.archive.ArchiveManager.propose_merge`
   to compute the merged content. Because the target spec is absent (or being
   overwritten), the merge produces the H1 + frontmatter scaffold + the
   archive's ADDED Requirements as the body (the existing scaffold path in
   ``_merge_delta_into_source`` handles this transparently).
4. Writes the proposed content atomically (``.tmp`` sibling + POSIX rename),
   mirroring :meth:`ArchiveManager.apply_merge`'s atomic-write contract.

Crucially, ``seed_initial_spec`` does NOT call
:meth:`ArchiveManager.apply_merge`. Apply_merge enforces a gate-score
threshold (≥ 8.5 PATCH/MINOR; ≥ 9.0 MAJOR) and is the canonical UPDATE path
for an existing source-of-truth. The seed path is a one-shot bootstrap that
gates on filesystem absence (A-4 first-time-seed invariant) instead of
gate-score. Subsequent mutations of the same domain go through the
``propose_merge → apply_merge`` flow.

Public API:

* :func:`seed_initial_spec` — text → on-disk source-of-truth spec.
* :exc:`SpecBootstrapError` — generic bootstrap-side error (subclasses
  :class:`RuntimeError` so callers can catch it without importing
  :mod:`devolaflow.agent_workspace.archive`).
"""

from __future__ import annotations

import logging
from pathlib import Path

from devolaflow.agent_workspace.archive import (
    ArchiveError,
    ArchiveManager,
    MergeConflict,
    ProposedMerge,
)
from devolaflow.agent_workspace.change import (
    _DATE_PREFIX_RE,
    ChangeNotFoundError,
    ChangeStore,
)
from devolaflow.agent_workspace.delta_parser import DeltaSpecParseError

__all__ = [
    "SpecBootstrapError",
    "seed_initial_spec",
]


logger = logging.getLogger(__name__)


SOURCE_OF_TRUTH_ROOT: Path = Path(".local") / "memory" / "specs"
ARCHIVE_ROOT: Path = Path(".local") / ".agent" / "archive"


class SpecBootstrapError(RuntimeError):
    """Generic error raised by :func:`seed_initial_spec`.

    Subclasses :class:`RuntimeError` so callers can catch it without
    importing :mod:`devolaflow.agent_workspace.archive`. Wraps the
    underlying :exc:`ArchiveError` / :exc:`MergeConflict` /
    :exc:`DeltaSpecParseError` / :exc:`ChangeNotFoundError` causes via
    ``__cause__`` so the original failure is recoverable for diagnostics.
    """


def seed_initial_spec(
    domain: str,
    archive_id: str,
    repo_root: Path,
    *,
    force: bool = False,
) -> Path:
    """Seed ``.local/memory/specs/<domain>/spec.md`` from a verified archive.

    A-4 invariant: source-of-truth is mutated ONLY at archive time AFTER
    the gate has PASSED. ``seed_initial_spec`` is the FIRST-TIME population
    of a domain's spec from the corresponding archive folder's ``spec.md``
    (which contains the ADDED / MODIFIED / REMOVED Requirements the change
    applied). Subsequent updates go through
    :meth:`devolaflow.agent_workspace.archive.ArchiveManager.propose_merge`
    → :meth:`apply_merge` (the existing v8.4.4 PV-04 API).

    Args:
      domain: Source-of-truth domain name (e.g. ``"agent_workspace"``,
        ``"memory_router"``). Becomes ``.local/memory/specs/<domain>/``.
        MUST be a non-empty string with no path separators.
      archive_id: Archive folder identifier — accepts EITHER the full
        date-prefixed folder name (e.g. ``"2026-04-30-pv05"``) or the
        bare change-id (e.g. ``"pv05"``). The function looks the change
        up under ``.local/.agent/archive/`` via the standard
        :class:`ChangeStore` lookup, which scans both prefixed and
        bare-id folder names.
      repo_root: Repo root for path resolution. The archive folder is
        looked up under ``repo_root / ".local/.agent/archive"``; the
        target spec lands under ``repo_root / ".local/memory/specs"``.
      force: When ``False`` (default) refuses to overwrite an existing
        ``.local/memory/specs/<domain>/spec.md`` — the A-4 invariant
        for first-time seeds. When ``True``, the existing spec is
        overwritten and a WARNING is logged (S-5 — never silent).

    Returns:
      Absolute path to the written ``.local/memory/specs/<domain>/spec.md``.

    Raises:
      SpecBootstrapError: When ``domain`` is empty / contains a path
        separator, when the archive folder is absent, when the archive's
        ``spec.md`` is missing or malformed, when the merge produces a
        conflict (e.g. ADDED collision with a residual SoT scaffold),
        OR when the target spec already exists and ``force=False``.
        Underlying causes preserved via ``__cause__``.
    """
    if not domain or "/" in domain or "\\" in domain or domain == ".":
        raise SpecBootstrapError(
            f"seed_initial_spec: invalid domain {domain!r} — must be a "
            f"non-empty string with no path separators"
        )
    if not archive_id:
        raise SpecBootstrapError("seed_initial_spec: archive_id must be a non-empty string")

    repo_root = Path(repo_root)
    target_path = repo_root / SOURCE_OF_TRUTH_ROOT / domain / "spec.md"
    archive_root = repo_root / ARCHIVE_ROOT
    archive_folder = archive_root / archive_id

    if not archive_folder.is_dir():
        raise SpecBootstrapError(
            f"seed_initial_spec: archive folder not found at {archive_folder!s} — "
            f"verify archive_id={archive_id!r} exists under "
            f"{archive_root!s} (the archive must be created via "
            f"ArchiveManager.archive() before it can seed a source-of-truth)"
        )

    archive_spec_path = archive_folder / "spec.md"
    if not archive_spec_path.is_file():
        raise SpecBootstrapError(
            f"seed_initial_spec: archive folder {archive_folder!s} has no spec.md — "
            f"a verified archive MUST carry the change's delta spec "
            f"(per schemas/agent-workspace/change-spec.yaml)"
        )

    if target_path.exists():
        if not force:
            raise SpecBootstrapError(
                f"seed_initial_spec: target source-of-truth {target_path!s} already "
                f"exists — refusing to overwrite per A-4 invariant. Subsequent "
                f"updates of an existing spec MUST go through "
                f"ArchiveManager.propose_merge → apply_merge (with a gate score "
                f">= 8.5 PATCH/MINOR or >= 9.0 MAJOR). Pass force=True to "
                f"override (logs WARNING + overwrites)."
            )
        logger.warning(
            "seed_initial_spec: force=True overwriting existing source-of-truth "
            "at %s (A-4 update path is propose_merge -> apply_merge; "
            "force=True is for repo-init / disaster-recovery only)",
            target_path,
        )
        # force=True semantics: wholesale replacement (disaster-recovery /
        # repo-init reset). Remove the existing target BEFORE propose_merge
        # runs so the merge engine synthesises a fresh H1 + frontmatter
        # scaffold rather than appending the archive's ADDED Requirements
        # to the stale body. The atomic-write path below will recreate the
        # file from the merged content.
        target_path.unlink()

    bare_change_id = _strip_date_prefix(archive_id)
    store = ChangeStore(repo_root=repo_root)
    manager = ArchiveManager(store=store)

    try:
        proposal: ProposedMerge = manager.propose_merge(bare_change_id)
    except (
        ChangeNotFoundError,
        MergeConflict,
        DeltaSpecParseError,
        ArchiveError,
    ) as exc:
        raise SpecBootstrapError(
            f"seed_initial_spec: propose_merge failed for archive_id={archive_id!r} "
            f"(bare change_id={bare_change_id!r}): {exc}"
        ) from exc

    if proposal.delta_target != domain:
        raise SpecBootstrapError(
            f"seed_initial_spec: archive {archive_id!r} declares "
            f"delta_target={proposal.delta_target!r} but the caller asked to "
            f"seed domain {domain!r} — refusing to write a mismatched spec "
            f"(per A-4, the spec's delta_target frontmatter is the binding "
            f"contract for which source-of-truth domain it mutates)"
        )

    target_path.parent.mkdir(parents=True, exist_ok=True)
    content = proposal.content
    if not content.endswith("\n"):
        content = content + "\n"
    tmp_path = target_path.with_suffix(target_path.suffix + ".tmp")
    tmp_path.write_text(content, encoding="utf-8", newline="\n")
    tmp_path.replace(target_path)

    logger.info(
        "seed_initial_spec: wrote %d bytes to %s (domain=%s, archive_id=%s, force=%s)",
        len(content.encode("utf-8")),
        target_path,
        domain,
        archive_id,
        force,
    )
    return target_path


def _strip_date_prefix(archive_id: str) -> str:
    """Return ``archive_id`` with a leading ``YYYY-MM-DD-`` prefix removed.

    Both the date-prefixed archive folder name (``"2026-04-30-pv05"``) and
    the bare change-id (``"pv05"``) are accepted by
    :func:`seed_initial_spec`; this helper normalizes them to the bare
    change-id required by :class:`ChangeStore.get`.
    """
    if _DATE_PREFIX_RE.match(archive_id):
        return archive_id[len("YYYY-MM-DD-") :]
    return archive_id
