"""Pure-function discovery API for DevolaFlow consumer-repo workspace surfaces.

This module is the canonical entry point that L0 (Project Agent) calls at
session start to learn whether the consumer repo has any DevolaFlow-managed
state — accumulated user feedback, source-of-truth specs, prior memory cases,
in-flight change folders, or the layered ``.rules/`` corpus. The result is a
frozen :class:`WorkspaceContext` snapshot that the dispatch context can
surface to downstream layers without re-walking the filesystem.

Design contract (R5 strict, S-5 explicit error states):

* Pure-function: :func:`scan_workspace` performs ONLY filesystem reads. It
  never writes, never mutates, never spawns processes. Safe to call
  repeatedly (idempotent; same inputs → same outputs modulo on-disk drift).
* Sane defaults: missing paths return ``False`` / empty tuple / 0 — NEVER
  raise. The caller can treat the snapshot as authoritative without
  defensive try/except blocks.
* Explicit failure surface (S-5): unreadable paths (PermissionError) emit
  a WARNING through the standard :mod:`logging` channel and are treated as
  absent. Silent absorption is forbidden — the warn entry is the explicit
  error state per Soul Rule S-5.

Public surface (NOT re-exported through ``devolaflow.__init__``):

* :class:`WorkspaceContext` — frozen dataclass; the discovery snapshot.
* :func:`scan_workspace` — pure factory that builds a snapshot.
* :data:`MAX_FEEDBACKS_RETURNED` — module-level public constant pinning the
  3-feedback ingestion cap shared with
  ``references/plan-mode-enforcement.md`` §"Feedback Ingestion".
* :meth:`WorkspaceContext.to_summary_dict` — JSON-serialisable rendering of
  the snapshot for dispatch-context injection.

SKILL.md (`workflow-system/agent/SKILL.md`) §"Workspace Engagement" instructs
L0 to call this at session start. ``references/agent-workspace.md`` §1
"When to Engage" enumerates the activation contract per workspace surface.

Source: v9.1.1 PV-01 (cycle v9.2.0). Closes the discovery gap catalogued in
``.local/research/v9.1.1_pv01_design.md`` (the SKILL.md teaches workspace
engagement but never instructed agents to scan the surfaces at session start
prior to v9.1.1).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = [
    "MAX_FEEDBACKS_RETURNED",
    "WorkspaceContext",
    "scan_workspace",
]

_logger = logging.getLogger(__name__)

# Names of files inside ``.local/.agent/active/`` that are NOT change-folder
# directories — README scaffolding (created by ``devola-init local``) and
# dot-files. Filtered out of the ``active_changes`` enumeration so callers
# see only real in-flight changes.
_ACTIVE_DIR_BLOCKLIST: frozenset[str] = frozenset({"README.md"})

# Names of files inside ``.local/memory/cases/`` that are scaffolding rather
# than real cases. Mirrors the ``.local/.agent/active/`` policy above.
_MEMORY_CASES_BLOCKLIST: frozenset[str] = frozenset({"README.md", "index.yaml"})

# Compiled-rule-corpus targets the discovery snapshot reports as present.
# Order matches the canonical compile-config: AGENTS.md (parent target) +
# Cursor-specific MDC. Both are FILE paths relative to ``repo_root``.
_COMPILED_CORPUS_CANDIDATES: tuple[str, ...] = (
    "AGENTS.md",
    ".cursor/rules/repo-governance.mdc",
)

# Maximum number of feedback files surfaced via ``recent_feedbacks``. Three
# is the L0 plan-mode default (per ``references/plan-mode-enforcement.md``
# §"Feedback Ingestion") — older feedbacks remain on disk but are not
# auto-loaded into dispatch context. Public alias exposed under the
# documented PV-01 spec name; ``_RECENT_FEEDBACKS_LIMIT`` retained as the
# internal symbol the helper functions read so prior call-sites stay
# byte-identical (R5 strict additive — no rename).
MAX_FEEDBACKS_RETURNED: int = 3
_RECENT_FEEDBACKS_LIMIT: int = MAX_FEEDBACKS_RETURNED


@dataclass(frozen=True)
class WorkspaceContext:
    """Snapshot of ``.local/``, ``.agent/``, ``.rules/`` presence in a repo.

    Returned by :func:`scan_workspace`. Pure data — no methods that mutate
    the filesystem; the dataclass is :func:`dataclasses.dataclass(frozen=True)`
    so consumers cannot accidentally edit a snapshot in flight.

    Attributes
    ----------
    repo_root:
        Absolute :class:`Path` of the consumer repo root (the argument the
        snapshot was built for, normalised via :func:`Path.resolve`).
    has_local:
        ``True`` when ``.local/`` exists as a directory under ``repo_root``.
    has_rules:
        ``True`` when ``.rules/`` exists as a directory under ``repo_root``.
    has_agent_dir:
        ``True`` when ``.local/.agent/`` exists as a directory.
    active_changes:
        Sorted tuple of subdirectory names under ``.local/.agent/active/``.
        Empty when the directory is absent or contains only README/dot-files.
    recent_feedbacks:
        Tuple of up to 3 :class:`Path` objects matching
        ``.local/feedbacks/feedback_for_v*.md`` ordered by modification time
        descending (newest first). The 3-entry cap mirrors the plan-mode
        feedback-ingestion default in ``references/plan-mode-enforcement.md``.
    source_of_truth_specs:
        Tuple of all files matching ``.local/memory/specs/*/spec.md``,
        sorted by path. Empty when ``.local/memory/specs/`` is absent.
    memory_cases_count:
        Count of files under ``.local/memory/cases/`` excluding ``README.md``
        and ``index.yaml``. Zero when the directory is absent.
    rules_layer_set:
        Sorted tuple of ``.rules/*.mdc`` file stems (e.g. ``("architecture",
        "conventions", "soul", "style", "workflow")``). Empty when
        ``.rules/`` is absent.
    compiled_corpora:
        Tuple of strings naming the compiled-corpus targets that exist
        under ``repo_root`` — ``"AGENTS.md"`` and/or
        ``".cursor/rules/repo-governance.mdc"``. Order matches
        :data:`_COMPILED_CORPUS_CANDIDATES`.
    has_human_dir:
        ``True`` when ``.local/human/`` exists as a directory — the
        v14.0.0 human-interaction surface (first-class sibling of
        ``.agent/`` / ``memory/`` / ``research/``). ``False`` when absent.
    human_constitution:
        :class:`Path` to ``.local/human/input/constitution.md`` when the
        file is present, else ``None``. The authoritative, amendable
        human principles/constraints anchor (the binding INPUT zone).
    human_requirements:
        :class:`Path` to ``.local/human/input/requirements.md`` when the
        file is present, else ``None``. The durable stable-ID requirement
        set (the plan-mode scope contract).
    human_digest:
        :class:`Path` to ``.local/human/output/DIGEST.md`` when the file
        is present, else ``None``. The read-first, anti-flooding
        convergence digest (the OUTPUT zone skim surface).
    """

    repo_root: Path
    has_local: bool
    has_rules: bool
    has_agent_dir: bool
    active_changes: tuple[str, ...] = ()
    recent_feedbacks: tuple[Path, ...] = ()
    source_of_truth_specs: tuple[Path, ...] = ()
    memory_cases_count: int = 0
    rules_layer_set: tuple[str, ...] = ()
    compiled_corpora: tuple[str, ...] = ()
    has_human_dir: bool = False
    human_constitution: Path | None = None
    human_requirements: Path | None = None
    human_digest: Path | None = None

    def to_summary_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable summary of this snapshot.

        Convert :class:`Path` fields to repo-root-relative POSIX strings so the
        result round-trips through :func:`json.dumps` / :func:`json.loads`
        without a custom encoder. Designed for **dispatch-context injection** —
        the L0 dispatcher serialises the snapshot into the ``change_context``
        block (or an out-of-band log) without walking the filesystem again on
        the consumer side.

        Path-handling contract:

        * ``repo_root`` is rendered via :func:`Path.as_posix` (absolute path,
          stable on every platform).
        * Each entry in ``recent_feedbacks`` and ``source_of_truth_specs`` is
          rendered RELATIVE to ``repo_root`` (POSIX form). When a Path is
          NOT under ``repo_root`` (the snapshot was constructed by hand with
          out-of-tree paths), the absolute POSIX form is emitted as a
          fallback rather than raising.

        Returns
        -------
        dict[str, Any]
            JSON-serialisable mapping. Keys mirror the dataclass field names
            (no renames) so the schema is self-documenting.

        Examples
        --------
        >>> import json
        >>> ctx = scan_workspace(".")  # doctest: +SKIP
        >>> json.dumps(ctx.to_summary_dict())  # doctest: +SKIP
        '{"repo_root": ".../DevolaFlow", "has_local": true, ...}'
        """

        def _rel(p: Path) -> str:
            try:
                return p.relative_to(self.repo_root).as_posix()
            except ValueError:
                return p.as_posix()

        return {
            "repo_root": self.repo_root.as_posix(),
            "has_local": self.has_local,
            "has_rules": self.has_rules,
            "has_agent_dir": self.has_agent_dir,
            "active_changes": list(self.active_changes),
            "recent_feedbacks": [_rel(p) for p in self.recent_feedbacks],
            "source_of_truth_specs": [_rel(p) for p in self.source_of_truth_specs],
            "memory_cases_count": self.memory_cases_count,
            "rules_layer_set": list(self.rules_layer_set),
            "compiled_corpora": list(self.compiled_corpora),
            "has_human_dir": self.has_human_dir,
            "human_constitution": (
                _rel(self.human_constitution) if self.human_constitution is not None else None
            ),
            "human_requirements": (
                _rel(self.human_requirements) if self.human_requirements is not None else None
            ),
            "human_digest": (_rel(self.human_digest) if self.human_digest is not None else None),
        }


def _is_dir_safe(path: Path) -> bool:
    """Return ``True`` iff ``path`` is a directory; absorb PermissionError.

    PermissionError emits a WARNING and returns ``False`` (S-5 explicit
    error state — the warning IS the explicit signal; downstream callers
    treat the path as absent).
    """
    try:
        return path.is_dir()
    except PermissionError as exc:
        _logger.warning(
            "scan_workspace: PermissionError reading %s — treating as absent: %s",
            path,
            exc,
        )
        return False
    except OSError as exc:
        _logger.warning(
            "scan_workspace: OSError reading %s — treating as absent: %s",
            path,
            exc,
        )
        return False


def _is_file_safe(path: Path) -> bool:
    """Return ``True`` iff ``path`` is a regular file; absorb PermissionError.

    Single-file analogue of :func:`_is_dir_safe` (PermissionError is a
    subclass of OSError, so the single ``except OSError`` arm catches both).
    An unreadable path emits a WARNING and is treated as absent — the warning
    IS the explicit error state per Soul Rule S-5; callers never raise.
    """
    try:
        return path.is_file()
    except OSError as exc:
        _logger.warning(
            "scan_workspace: OSError checking %s — treating as absent: %s",
            path,
            exc,
        )
        return False


def _list_dir_safe(path: Path) -> list[Path]:
    """Return ``list(path.iterdir())`` or ``[]`` if unreadable.

    Mirrors :func:`_is_dir_safe` semantics — PermissionError / OSError
    emit a WARNING and degrade to an empty listing per S-5.
    """
    try:
        return list(path.iterdir())
    except PermissionError as exc:
        _logger.warning(
            "scan_workspace: PermissionError listing %s — treating as empty: %s",
            path,
            exc,
        )
        return []
    except OSError as exc:
        _logger.warning(
            "scan_workspace: OSError listing %s — treating as empty: %s",
            path,
            exc,
        )
        return []


def _stat_mtime_safe(path: Path) -> float:
    """Return ``path.stat().st_mtime`` or ``0.0`` on failure.

    Used as an mtime-descending sort key for ``recent_feedbacks``;
    unreadable entries sort to the end of the list rather than crashing
    the scan.
    """
    try:
        return path.stat().st_mtime
    except OSError as exc:
        _logger.warning(
            "scan_workspace: OSError statting %s — using mtime 0.0: %s",
            path,
            exc,
        )
        return 0.0


def _scan_active_changes(agent_dir: Path) -> tuple[str, ...]:
    """Return sorted active-change-folder names under ``.local/.agent/active/``.

    Filters out README.md and dot-files (per :data:`_ACTIVE_DIR_BLOCKLIST`).
    Only directories are reported as changes — file entries (e.g., a stray
    YAML) are skipped.
    """
    active_root = agent_dir / "active"
    if not _is_dir_safe(active_root):
        return ()
    names: list[str] = []
    for entry in _list_dir_safe(active_root):
        if entry.name in _ACTIVE_DIR_BLOCKLIST or entry.name.startswith("."):
            continue
        if _is_dir_safe(entry):
            names.append(entry.name)
    return tuple(sorted(names))


def _scan_recent_feedbacks(local_dir: Path) -> tuple[Path, ...]:
    """Return up to 3 ``feedback_for_v*.md`` files, newest first by mtime."""
    feedbacks_dir = local_dir / "feedbacks"
    if not _is_dir_safe(feedbacks_dir):
        return ()
    candidates = [
        p
        for p in _list_dir_safe(feedbacks_dir)
        if p.is_file() and p.name.startswith("feedback_for_v") and p.suffix == ".md"
    ]
    candidates.sort(key=_stat_mtime_safe, reverse=True)
    return tuple(candidates[:_RECENT_FEEDBACKS_LIMIT])


def _scan_source_of_truth_specs(local_dir: Path) -> tuple[Path, ...]:
    """Return all ``.local/memory/specs/<domain>/spec.md`` files, sorted.

    Walks one level deep under ``.local/memory/specs/`` so every domain
    subdirectory contributes at most one ``spec.md``. Missing directories
    silently return an empty tuple (S-5 explicit defaults).
    """
    specs_root = local_dir / "memory" / "specs"
    if not _is_dir_safe(specs_root):
        return ()
    specs: list[Path] = []
    for domain in _list_dir_safe(specs_root):
        if not _is_dir_safe(domain):
            continue
        spec_file = domain / "spec.md"
        try:
            if spec_file.is_file():
                specs.append(spec_file)
        except OSError as exc:
            _logger.warning(
                "scan_workspace: OSError checking %s — skipping: %s",
                spec_file,
                exc,
            )
    specs.sort()
    return tuple(specs)


def _scan_memory_cases_count(local_dir: Path) -> int:
    """Count ``.local/memory/cases/*`` files excluding scaffolding."""
    cases_root = local_dir / "memory" / "cases"
    if not _is_dir_safe(cases_root):
        return 0
    count = 0
    for entry in _list_dir_safe(cases_root):
        if entry.name in _MEMORY_CASES_BLOCKLIST or entry.name.startswith("."):
            continue
        try:
            if entry.is_file():
                count += 1
        except OSError as exc:
            _logger.warning(
                "scan_workspace: OSError checking %s — skipping: %s",
                entry,
                exc,
            )
    return count


def _scan_rules_layer_set(rules_dir: Path) -> tuple[str, ...]:
    """Return sorted tuple of ``.rules/*.mdc`` file stems."""
    if not _is_dir_safe(rules_dir):
        return ()
    stems = sorted(p.stem for p in _list_dir_safe(rules_dir) if p.is_file() and p.suffix == ".mdc")
    return tuple(stems)


def _scan_compiled_corpora(repo_root: Path) -> tuple[str, ...]:
    """Return tuple of compiled-rule-corpus target names that exist on disk.

    Order matches :data:`_COMPILED_CORPUS_CANDIDATES`. Each candidate is
    checked via :func:`Path.is_file` with PermissionError absorbed.
    """
    present: list[str] = []
    for relpath in _COMPILED_CORPUS_CANDIDATES:
        full = repo_root / relpath
        try:
            if full.is_file():
                present.append(relpath)
        except OSError as exc:
            _logger.warning(
                "scan_workspace: OSError checking %s — treating as absent: %s",
                full,
                exc,
            )
    return tuple(present)


def _scan_human_input(local_dir: Path) -> tuple[Path | None, Path | None]:
    """Return ``(constitution, requirements)`` paths under ``.local/human/input/``.

    Mirrors :func:`_scan_recent_feedbacks` — performs ONLY filesystem reads.
    Each anchor (``input/constitution.md`` and ``input/requirements.md``)
    resolves to its :class:`Path` when present, else ``None`` (S-5 explicit
    default). :func:`_is_file_safe` degrades a PermissionError/OSError to
    ``None`` + a WARNING — never raises — so the v14.0.0 INPUT zone is safe
    to probe unconditionally at session start.
    """
    input_dir = local_dir / "human" / "input"
    constitution = input_dir / "constitution.md"
    requirements = input_dir / "requirements.md"
    return (
        constitution if _is_file_safe(constitution) else None,
        requirements if _is_file_safe(requirements) else None,
    )


def _scan_human_output(local_dir: Path) -> Path | None:
    """Return the ``.local/human/output/DIGEST.md`` path when present, else ``None``.

    Mirrors :func:`_scan_recent_feedbacks` S-5 semantics — the read-first
    digest is the only OUTPUT-zone anchor the discovery snapshot surfaces
    (the per-cycle convergence reports stay private and are not scanned).
    """
    digest = local_dir / "human" / "output" / "DIGEST.md"
    return digest if _is_file_safe(digest) else None


def scan_workspace(repo_root: Path | str) -> WorkspaceContext:
    """Scan a consumer repo for DevolaFlow workspace surfaces.

    Returns a :class:`WorkspaceContext` snapshot describing whether
    ``.local/``, ``.rules/``, and ``.local/.agent/`` are present, plus
    the contents of those surfaces (active changes, recent feedbacks,
    source-of-truth specs, memory case count, rules layer set, compiled
    corpora).

    Pure function — no side effects. Safe to call repeatedly. Returns
    sane defaults (``False`` / empty tuple / 0) when paths are absent
    so consumers do not need defensive try/except blocks. Per S-5,
    PermissionError / OSError emit a WARNING through the module logger
    and degrade to absent rather than silently swallowing the error.

    Parameters
    ----------
    repo_root:
        Path to the consumer repo root. Accepts :class:`str` (converted
        via :class:`Path`) or :class:`Path`. Resolved via
        :func:`Path.resolve` so the snapshot stores the canonical
        absolute path regardless of CWD.

    Returns
    -------
    WorkspaceContext
        Frozen snapshot of the detected surfaces.

    Examples
    --------
    >>> ctx = scan_workspace(".")  # doctest: +SKIP
    >>> ctx.has_local  # doctest: +SKIP
    True
    >>> ctx.rules_layer_set  # doctest: +SKIP
    ('architecture', 'conventions', 'soul', 'style', 'workflow')
    """
    root = Path(repo_root).resolve()
    local_dir = root / ".local"
    rules_dir = root / ".rules"
    agent_dir = local_dir / ".agent"

    has_local = _is_dir_safe(local_dir)
    has_rules = _is_dir_safe(rules_dir)
    has_agent_dir = _is_dir_safe(agent_dir)

    active_changes: tuple[str, ...] = ()
    recent_feedbacks: tuple[Path, ...] = ()
    source_of_truth_specs: tuple[Path, ...] = ()
    memory_cases_count = 0
    rules_layer_set: tuple[str, ...] = ()
    has_human_dir = False
    human_constitution: Path | None = None
    human_requirements: Path | None = None
    human_digest: Path | None = None

    if has_agent_dir:
        active_changes = _scan_active_changes(agent_dir)
    if has_local:
        recent_feedbacks = _scan_recent_feedbacks(local_dir)
        source_of_truth_specs = _scan_source_of_truth_specs(local_dir)
        memory_cases_count = _scan_memory_cases_count(local_dir)
        has_human_dir = _is_dir_safe(local_dir / "human")
        human_constitution, human_requirements = _scan_human_input(local_dir)
        human_digest = _scan_human_output(local_dir)
    if has_rules:
        rules_layer_set = _scan_rules_layer_set(rules_dir)

    compiled_corpora = _scan_compiled_corpora(root)

    return WorkspaceContext(
        repo_root=root,
        has_local=has_local,
        has_rules=has_rules,
        has_agent_dir=has_agent_dir,
        active_changes=active_changes,
        recent_feedbacks=recent_feedbacks,
        source_of_truth_specs=source_of_truth_specs,
        memory_cases_count=memory_cases_count,
        rules_layer_set=rules_layer_set,
        compiled_corpora=compiled_corpora,
        has_human_dir=has_human_dir,
        human_constitution=human_constitution,
        human_requirements=human_requirements,
        human_digest=human_digest,
    )
