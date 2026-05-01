"""Scaffold and manage the .local/ workspace directory."""

from __future__ import annotations

import fnmatch
import logging
from pathlib import Path

_LOGGER = logging.getLogger(__name__)

REQUIRED_DIRS = [
    "feedbacks",
    "tasks",
    "memory",
    ".agent/active",
    ".agent/handoff",
    ".agent/archive",
]
ON_DEMAND_DIRS = ["research", "design", "benchmarks", "logs", "scratch"]

# v8.2.3 — additive subdirs not in REQUIRED_DIRS proper. memory/specs is
# the source-of-truth contract location per Architecture Rule A-4
# (.local/research/v8.3.0_design.md §1.1, M-004 ADR).
MEMORY_SUBDIRS = ["memory/specs"]

_DIR_README_CONTENT: dict[str, str] = {
    "feedbacks": """\
# feedbacks/

Format: `feedback_for_vX.Y.Z.md` (one file per version).

Conventions:
- Line 1: `# Feedback for DevolaFlow vX.Y.Z`
- Line 3: `> Date: YYYY-MM-DD | Author: name | Version: vX.Y.Z`
- Sections: Issues (with Severity), Positives, user feedback
- Session logs: `feedback_for_vX.Y.Z_session.md`
- External sources: subdirectories (e.g. `from_evobench/`)
- Resolution tracking: see `TRACKER.md` (do not edit source files)
""",
    "tasks": """\
# tasks/

Format: Markdown overview + optional YAML specs.

Conventions:
- Line 1: `# Task: [title]`
- Line 3: `> ID: T-[ver]-[seq] | Priority: P1-P4 | Status: planned/active/done`
- Sections: Description, Acceptance Criteria (checklist), Files
- YAML specs for machine-readable dispatch live alongside .md overviews
""",
    "memory": """\
# memory/

Auto-memory workspace for DevolaFlow learnings.

Files:
- `MEMORY.md` — index (loaded at session start)
- `prefs.md` — personal preferences (role, communication style)
- `operational.jsonl` — machine-managed learnings (JSONL)
- `topic-*.md` — on-demand topic notes
""",
    ".agent/active": """\
# .agent/active/

In-flight changes managed by the `change-driven` workflow (shipped v8.2.6+; see
`workflow-system/agent/templates/builtin/change-driven.yaml` for the stage definition).
Each subfolder is `<change-id>/` with the per-change artifact set:

- `goal.md` — intent statement (<= 200 tokens, hard ceiling 400)
- `acceptance.md` — testable AC checklist (<= 400 tokens, hard ceiling 800)
- `spec.md` — OpenSpec-style ADDED/MODIFIED/REMOVED delta (<= 1500 tokens)
- `tasks.md` — implementation checklist (<= 800 tokens)
- `STATUS.yaml` — machine-readable state block (<= 100 tokens)
- `owned_files.txt` — ownership manifest (<= 50 tokens, max 6 paths)
- `learnings.jsonl` — per-change reflections (capped 50 KB)

S-8 invariant: L3 task agents inside this folder MUST NOT write outside
their `owned_files.txt` set (plus the change folder + handoff outbox).
See `.local/research/v8.3.0_design.md` Section 1.1 for the full layout.
""",
    ".agent/handoff": """\
# .agent/handoff/

Cross-agent handoff envelopes — append-only per Soul Rule S-9.

Naming: `<from>__<to>__<change-id>__<seq>.yaml`
- `seq` is a monotonic int starting at `0001` (zero-padded for sort-correct listing)
- Once an envelope file exists, it MUST NOT be modified or deleted
- New information goes in `seq + 1`

Schema shipped in v8.2.4 under `schemas/agent-workspace/handoff-envelope.yaml`.
Append-only enforcement: `tests/test_handoff_envelope_immutable.py` (CI lint)
plus the `lifecycle/check_envelope_append_only` hook (block in STRICT mode).
""",
    ".agent/archive": """\
# .agent/archive/

Completed changes preserved with date prefix `<YYYY-MM-DD>-<change-id>/`.
Frozen at archive time + auto-generated `REPORT.md` summarising the change.

Archive is the read-mostly half of the lifecycle FSM
(see `.local/research/v8.3.0_design.md` Section 1.3). Source-of-truth specs
in `.local/memory/specs/` are mutated only after the change-gate composite
score >= 8.5 PASSES (W-3 / SI-3 for minor, >= 9.0 for major) per Rule A-4.
The mergeability check (shipped v8.2.5+) gates the merge.
""",
    "memory/specs": """\
# memory/specs/

Source-of-truth spec contracts per Architecture Rule A-4 (M-004 ADR).
Per-domain layout: `<domain>/spec.md` (e.g. `agent_workspace/spec.md`).

Mutated **only at archive time** after the change-gate composite score
PASSES per W-3 / SI-3 (>= 8.5 for minor, >= 9.0 for major). Per-change
`.local/.agent/active/<id>/spec.md` files contain DELTAS (ADDED/MODIFIED/
REMOVED Requirements) relative to this source-of-truth.
""",
}


def scaffold_local(
    cwd: str | Path,
    dirs: list[str] | None = None,
) -> Path:
    """Create .local/ with required dirs + optional on-demand dirs.

    Idempotent — safe to re-run. On every call this also repairs the two
    pre-existing scaffolding gaps documented in
    ``.local/research/v8.3.0_gap_analysis.md`` Section 1.1:

    - **G-1 repair**: ``index.md`` is regenerated unconditionally so
      drifted listings (existing-repo case) catch up to the actual
      subdirectory layout.
    - **G-2 repair**: :func:`generate_tracker` and
      :func:`generate_memory_index` are invoked on every call so older
      `.local/` directories that pre-date the helpers acquire the missing
      ``TRACKER.md`` / ``MEMORY.md`` on the next run. Both helpers no-op
      when the target file already exists.

    Args:
        cwd: Working directory (repo root).
        dirs: Additional on-demand directories to create.  Only names
              listed in ON_DEMAND_DIRS are accepted; unknown names are
              silently ignored.

    Returns:
        Path to the .local/ directory.
    """
    local_dir = Path(cwd) / ".local"
    local_dir.mkdir(exist_ok=True)

    for d in REQUIRED_DIRS:
        (local_dir / d).mkdir(parents=True, exist_ok=True)
        generate_dir_readme(local_dir / d, d)

    for d in MEMORY_SUBDIRS:
        (local_dir / d).mkdir(parents=True, exist_ok=True)
        generate_dir_readme(local_dir / d, d)

    generate_tracker(local_dir / "feedbacks")
    generate_memory_index(local_dir / "memory")

    on_demand_created: list[Path] = []
    for d in dirs or []:
        if d in ON_DEMAND_DIRS:
            target = local_dir / d
            target.mkdir(exist_ok=True)
            on_demand_created.append(target)

    generate_index(local_dir)

    # v9.2.3 PV-02 — I-003 closure: advise the operator when a freshly
    # scaffolded path is shadowed by an existing .gitignore rule. Pure
    # WARNING log per match — never raises (S-5 graceful degradation).
    created_roots: list[Path] = (
        [local_dir / d for d in REQUIRED_DIRS]
        + [local_dir / d for d in MEMORY_SUBDIRS]
        + on_demand_created
    )
    _audit_gitignore_coverage(Path(cwd), created_roots)

    return local_dir


def generate_memory_index(memory_dir: Path) -> Path:
    """Create MEMORY.md index in the memory directory if it doesn't exist.

    Args:
        memory_dir: Path to the memory/ directory.

    Returns:
        Path to the generated MEMORY.md file.
    """
    path = memory_dir / "MEMORY.md"
    if not path.exists():
        path.write_text(
            "# Memory Index\n"
            "\n"
            "> Auto-maintained by DevolaFlow. Updated on scaffold.\n"
            "\n"
            "## Files\n"
            "\n"
            "(No entries yet. Memory files will appear here as the project evolves.)\n",
            encoding="utf-8",
        )
    return path


def generate_tracker(feedbacks_dir: Path) -> Path:
    """Create TRACKER.md in the feedbacks directory if it doesn't exist.

    Args:
        feedbacks_dir: Path to the feedbacks/ directory.

    Returns:
        Path to the generated TRACKER.md file.
    """
    path = feedbacks_dir / "TRACKER.md"
    if not path.exists():
        path.write_text(
            "# Feedback Tracker\n"
            "\n"
            "> Auto-maintained by DevolaFlow. Do not edit feedback source files.\n"
            "> Last updated: (auto)\n"
            "\n"
            "## Open\n"
            "\n"
            "(No open items.)\n"
            "\n"
            "## Resolved\n"
            "\n"
            "(No resolved items yet.)\n"
            "\n"
            "## Deferred\n"
            "\n"
            "(No deferred items.)\n",
            encoding="utf-8",
        )
    return path


def generate_dir_readme(dir_path: Path, dir_name: str) -> Path:
    """Create a README.md convention file in the given directory if it doesn't exist.

    Args:
        dir_path: Path to the target directory.
        dir_name: Logical name of the directory (used to select content template).

    Returns:
        Path to the generated README.md file.
    """
    path = dir_path / "README.md"
    if not path.exists():
        content = _DIR_README_CONTENT.get(dir_name)
        if content is not None:
            path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# v9.2.3 PV-02 — I-003 .gitignore coverage audit.
# ---------------------------------------------------------------------------
#
# When ``scaffold_local(cwd)`` materialises a path that an EXISTING
# ``.gitignore`` rule already covers, the README anchor we just wrote
# (e.g. ``.local/.agent/active/README.md``) is invisible to ``git status``
# and to every reviewer browsing the repo on GitHub. Pre-v9.2.3 this was
# a silent surprise — operators who carried a ``.local/`` ignore rule
# from a prior session got the new convention docs but never saw them
# in version control until they opened the working tree directly.
#
# v9.2.3 closes the gap with a tail-call audit: after every path is
# materialised, walk the cwd-relative ``.gitignore`` rules and emit a
# WARNING per match enumerating the path, the README that won't be
# tracked, and the recommended ``!<path>/README.md`` whitelist line.
#
# Design constraints (S-5 strict):
# - Zero ``raise`` paths. Failures (unreadable .gitignore, permission
#   error, malformed UTF-8) log a WARNING and short-circuit to the
#   "no rules" branch — the audit is advisory; it MUST NOT block the
#   scaffold.
# - Negation rules (``!pattern``) are intentionally skipped — the audit
#   only needs to detect the "written but hidden" case; a negation is
#   the operator's explicit whitelist that the audit would only muddy.
# - The most-recent audit result is cached at module level so callers
#   that need programmatic access (test fixtures, CI hooks, the
#   forthcoming v9.3.0 ``devola-init doctor`` surface) can read it
#   without re-walking the disk via :func:`last_gitignore_audit`.
#
# Source: v9.2.3 PV-02 dispatch — closes I-003 from
# ``.local/feedbacks/feedback_for_v9.2.1.md`` §3 and
# ``.local/research/v9.2.2_gap_analysis.md`` §2 PV-02 scope.

VALID_GITIGNORE_AUDIT_REASON: tuple[str, ...] = (
    "directory_ignore_rule",
    "wildcard_pattern_match",
)

_LAST_GITIGNORE_AUDIT: list[Path] = []


def _read_gitignore_rules(cwd: Path) -> list[str]:
    """Return non-comment non-empty lines from ``cwd/.gitignore``.

    Pure filter — no interpretation of directory / negation / anchor
    semantics is performed at this layer; callers (specifically
    :func:`_path_matches_gitignore`) own that logic.

    The audit is advisory (S-5 graceful degradation): if the file
    exists but cannot be read (permission denied, IO error, decode
    error) the helper logs a single WARNING and returns ``[]`` — the
    scaffold MUST NOT block on a malformed ``.gitignore``.

    Returns an empty list when no ``.gitignore`` is present at the
    repo root (the common case for fresh repos — DEBUG-only log).
    """
    gi = cwd / ".gitignore"
    if not gi.is_file():
        _LOGGER.debug("scaffold_local: no .gitignore at %s; audit skipped", gi)
        return []
    try:
        text = gi.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        _LOGGER.warning(
            "scaffold_local: could not read %s: %s; gitignore audit skipped",
            gi,
            exc,
        )
        return []
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def _path_matches_gitignore(rel_posix: str, rules: list[str]) -> bool:
    """Return True iff any non-negation gitignore rule matches ``rel_posix``.

    Conservative gitignore semantics (intentionally NOT a full
    re-implementation of `gitignore(5)`):

    * Trailing ``/`` rules are treated as directory-prefix rules — a
      rule ``.local/`` matches both the path ``.local`` and any path
      that starts with ``.local/``.
    * Leading ``/`` rules are root-anchored — the leading slash is
      stripped here because the audit only ever tests repo-relative
      paths (already anchored at the repo root).
    * Wildcards are dispatched through :func:`fnmatch.fnmatch` — note
      Python's ``fnmatch`` does NOT special-case ``/`` so ``*`` matches
      across path separators (close enough for the audit's purpose).
    * Negation rules (``!pattern``) are skipped — the audit only
      detects the "written but hidden" case; a negation is the
      operator's explicit whitelist that the audit would only muddy.
    """
    for rule in rules:
        if rule.startswith("!"):
            continue
        cleaned = rule.lstrip("/").rstrip("/")
        if not cleaned:
            continue
        if rel_posix == cleaned:
            return True
        if rel_posix.startswith(cleaned + "/"):
            return True
        if fnmatch.fnmatch(rel_posix, cleaned):
            return True
        if "/" not in cleaned and any(
            fnmatch.fnmatch(part, cleaned) for part in rel_posix.split("/") if part
        ):
            return True
    return False


def _audit_gitignore_coverage(cwd: Path, created: list[Path]) -> list[Path]:
    """Return the subset of ``created`` covered by an existing gitignore rule.

    Side effect — emits one WARNING log per match enumerating:

    1. the ignored path (repo-relative POSIX)
    2. the README the operator won't see in version control
    3. the recommended ``!<rel>/README.md`` whitelist line

    Caches the returned list at module level so :func:`last_gitignore_audit`
    can return it without re-walking the disk.
    """
    global _LAST_GITIGNORE_AUDIT
    rules = _read_gitignore_rules(cwd)
    if not rules:
        _LAST_GITIGNORE_AUDIT = []
        return []

    cwd_resolved = cwd.resolve()
    covered: list[Path] = []
    for path in created:
        try:
            rel = path.resolve().relative_to(cwd_resolved)
        except ValueError:
            # Path is outside cwd (defensive — should never happen for the
            # scaffold's own outputs, but log + skip per S-5).
            _LOGGER.warning(
                "scaffold_local: created path %s is outside cwd %s; "
                "gitignore audit skipped for this entry",
                path,
                cwd_resolved,
            )
            continue
        rel_posix = rel.as_posix()
        if _path_matches_gitignore(rel_posix, rules):
            covered.append(path)
            _LOGGER.warning(
                "scaffold_local: %s is covered by an existing .gitignore rule "
                "— the generated README at %s/README.md will not be visible "
                "in version control. Whitelist it with `!%s/README.md` in "
                ".gitignore to keep the convention docs tracked while still "
                "ignoring runtime contents.",
                rel_posix,
                rel_posix,
                rel_posix,
            )

    _LAST_GITIGNORE_AUDIT = covered
    return covered


def last_gitignore_audit() -> list[Path]:
    """Return the result of the most recent ``_audit_gitignore_coverage`` call.

    Empty list when ``scaffold_local`` has not yet been called OR when
    the most recent invocation found no matching paths. Provides a
    programmatic surface for callers that need the audit result without
    re-walking the disk (test fixtures, CI hooks, the forthcoming
    v9.3.0 ``devola-init doctor`` surface).
    """
    return list(_LAST_GITIGNORE_AUDIT)


def generate_index(local_dir: str | Path) -> Path:
    """Generate index.md listing existing subdirectories.

    Idempotent: only writes when the rendered listing differs from the
    file already on disk. This keeps the file mtime stable across no-op
    re-scaffolds while still healing the G-1 drift case (existing-repo
    re-run picks up newly-added subdirectories).

    Returns:
        Path to the generated index.md.
    """
    local_dir = Path(local_dir)
    subdirs = sorted(p.name for p in local_dir.iterdir() if p.is_dir())

    lines = [
        "# .local/ workspace index",
        "",
        "Auto-generated directory listing.",
        "",
    ]
    for name in subdirs:
        lines.append(f"- `{name}/`")
    new_content = "\n".join(lines) + "\n"

    index_path = local_dir / "index.md"
    if index_path.exists() and index_path.read_text(encoding="utf-8") == new_content:
        return index_path

    index_path.write_text(new_content, encoding="utf-8")
    return index_path
