"""Scaffold and manage the .local/ workspace directory."""

from __future__ import annotations

from pathlib import Path

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

In-flight changes managed by the `change-driven` workflow (lands v8.2.6).
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

Schema lands in v8.2.4 under `schemas/agent-workspace/handoff-envelope.yaml`.
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
The mergeability check (lands v8.2.5) gates the merge.
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

    for d in dirs or []:
        if d in ON_DEMAND_DIRS:
            (local_dir / d).mkdir(exist_ok=True)

    generate_index(local_dir)
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
