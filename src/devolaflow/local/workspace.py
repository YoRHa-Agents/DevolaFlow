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
    # v14.0.0 — human-interaction surface (`.local/human/`). INPUT is the
    # durable, git-tracked, immutable-post-approval zone (D-4/ADR-2); OUTPUT
    # + archive are private, bounded (C-9) agent-draft → human-approve zones.
    "human",
    "human/input",
    "human/input/amendments",
    "human/output",
    "human/output/convergence",
    "human/archive",
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
    "human": """\
# human/

Human-interaction surface (v14.0.0). A first-class sibling of `.agent/`,
`memory/`, and `research/` — but with an explicit write-owner split:

- `input/` — **WRITE-OWNER: human.** Durable, authoritative requirements +
  constraints. Immutable post-approval (append amendments, never edit in
  place). Git-TRACKED (the authoritative, PR-reviewable zone, per ADR-2).
- `output/` — **WRITE-OWNER: agent drafts -> human approves.** Concise,
  budget-capped convergence reports + digest. Private (gitignored) — bounded
  reports stay local, not PR-visible.
- `archive/` — frozen, dated snapshots of superseded INPUT + closed OUTPUT
  (the A-4 "what changed and why" trail). Private (gitignored).

human INPUT (intent) NEVER overlaps `memory/specs/` (agent behaviour, W-23.4).
""",
    "human/input": """\
# human/input/

**WRITE-OWNER: human.** The authoritative, durable INPUT zone.

- `constitution.md` — amendable principles/constraints (per-file `Version` /
  `Ratified` / `Last Amended` stamp + a Governance amendment protocol).
- `requirements.md` — `REQ-<DOMAIN>-NN` entries + a Traceability matrix
  (`Unmapped: 0`) + Out-of-Scope. Shards to `requirements/<domain>.md` on
  overflow.
- `amendments/` — append-only amendment ledger (S-9 discipline): one dated
  `<YYYY-MM-DD>-<slug>.md` per change; the 引导回测 / regression lineage.

**Immutability:** a `Lifecycle: RATIFIED` requirement (or a constitution with
its `Ratified:` stamp set) is IMMUTABLE — record changes by APPENDING a dated
amendment + bumping that file's version stamp; never edit the ratified text in
place. `Lifecycle: DRAFT` blocks are freely editable until ratified.
""",
    "human/output": """\
# human/output/

**WRITE-OWNER: agent drafts -> human approves.** Private (gitignored),
concise, budget-capped (C-9) — conclusion-first to avoid output flooding.

- `DIGEST.md` — read-first STATE digest (this-cycle REQ deltas + one rollup
  line; refreshed each cycle, superseded copies rotate to `../archive/`).
- `convergence/<version>-convergence.md` — per-cycle report: line-1 status
  enum (`passed` | `gaps_found` | `human_needed`), per-REQ evidence rows
  (verbatim per C-3), and a blocking-vs-advisory finding split.

These reports CITE `CHANGELOG.md` / `.local/research/<version>_retrospective.md`
by path — they never restate them.
""",
    "human/input/amendments": """\
# human/input/amendments/

**WRITE-OWNER: human.** Append-only amendment ledger (S-9 discipline) for the
INPUT zone. One dated `<YYYY-MM-DD>-<slug>.md` per change — the 引导回测 /
regression lineage for ratified requirements + constitution edits.

A `Lifecycle: RATIFIED` requirement (or a constitution with its `Ratified:`
stamp set) is IMMUTABLE: record a change by ADDING a new dated amendment file
here + bumping the amended file's `**Version**` stamp; NEVER edit the ratified
text in place. Existing amendment files are never modified or deleted (mirrors
the `.agent/handoff/` append-only S-9 contract).
""",
    "human/output/convergence": """\
# human/output/convergence/

**WRITE-OWNER: agent drafts -> human approves.** Private (gitignored),
budget-capped (C-9). One per-cycle report `<version>-convergence.md` —
line-1 status enum (`passed` | `gaps_found` | `human_needed`), a 4-column
per-REQ evidence table (`REQ-ID | Acceptance criterion | Result | Evidence`,
verbatim per C-3), and a blocking-vs-advisory finding split (design §4a).

Generated by `python -m devolaflow.agent_workspace.reporter --human <version>`
(or `regenerate_all(human_version=...)`). Reports CITE
`CHANGELOG.md` / `.local/research/<version>_retrospective.md` — never restate.
""",
    "human/archive": """\
# human/archive/

Frozen, dated snapshots of superseded INPUT + closed OUTPUT — the A-4 "what
changed and why" trail. Private (gitignored). A superseded `DIGEST.md` rotates
here on each cycle; closed convergence reports + retired requirement shards are
preserved with their date prefix. Read-mostly: snapshots are never edited in
place once written.
""",
}


class ScaffoldVerificationError(RuntimeError):
    """Raised when the post-scaffold gitignore self-check finds missing rules.

    full_review_and_improve Track C-1 (R5 F1-H3): the scaffold previously
    relied on advisory WARN logs for gitignore write failures, so a broken
    ``.gitignore`` (read-only FS, path-is-a-directory, partial user edits)
    produced a "successful" scaffold with missing entries that nobody
    noticed. Per S-5 the scaffold now verifies its own output and raises
    this error with the exact missing rules so the operator (or calling
    agent) can repair and re-run — the scaffold itself stays idempotent.
    """

    def __init__(self, missing_rules: list[str], gitignore_path: Path) -> None:
        self.missing_rules = list(missing_rules)
        self.gitignore_path = gitignore_path
        super().__init__(
            f"scaffold self-check failed: {gitignore_path} is missing "
            f"{len(self.missing_rules)} required rule(s): {self.missing_rules}. "
            "Fix the file (or its permissions) and re-run the scaffold."
        )


# full_review_and_improve Track C-1 (R5 F1-H1): entries the scaffold writes
# DETERMINISTICALLY, decoupled from any plugin/CLI outcome. `.codegraph/`
# historically depended on the repo-init template's prompt-side
# `codegraph_init.add_to_gitignore` semantic — when `codegraph init` failed
# (on_failure: warn) the entry was silently skipped. The scaffold now owns
# the entry: it is written BEFORE any codegraph invocation and regardless
# of whether the CLI exists.
SCAFFOLD_GITIGNORE_ENTRIES: tuple[str, ...] = (".codegraph/",)

_SCAFFOLD_ENTRIES_HEADER: str = "# DevolaFlow scaffold entries (tool-local caches; safe to keep)"


def ensure_gitignore_entries(cwd: str | Path, entries: tuple[str, ...] | list[str]) -> list[str]:
    """Idempotently append missing ignore ``entries`` to ``cwd/.gitignore``.

    Deterministic replacement for the prompt-side ``add_to_gitignore``
    template semantic (R5 F1-H1/H3): existing user content and comments are
    preserved verbatim; entries already present as exact rules are skipped;
    missing entries are appended under a single header comment. Safe to
    re-run any number of times — a no-op run leaves the file byte-identical.

    Read/write failures log an explicit WARNING (S-5) and return ``[]``;
    the caller's verification step (:func:`verify_scaffold_gitignore` via
    ``scaffold_local``) is responsible for escalating persistent failures.

    Returns:
        The list of entries actually appended (empty when all were present).
    """
    cwd = Path(cwd)
    gi = cwd / ".gitignore"

    text = ""
    if gi.exists():
        try:
            text = gi.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            _LOGGER.warning(
                "ensure_gitignore_entries: could not read %s: %s; entries not written",
                gi,
                exc,
            )
            return []

    existing_rules = set(_parse_gitignore_rules(text))
    missing = [e for e in entries if e not in existing_rules]
    if not missing:
        return []

    lines = text.splitlines()
    if lines and lines[-1].strip():
        lines.append("")
    if _SCAFFOLD_ENTRIES_HEADER not in text:
        lines.append(_SCAFFOLD_ENTRIES_HEADER)
    lines.extend(missing)

    try:
        gi.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    except OSError as exc:
        _LOGGER.warning(
            "ensure_gitignore_entries: could not write %s: %s; entries not written",
            gi,
            exc,
        )
        return []
    return missing


def verify_scaffold_gitignore(cwd: str | Path) -> list[str]:
    """Return the scaffold-required gitignore rules missing from ``cwd``.

    The required set is the v12.2.0 ``.local/`` whitelist detection key
    (:data:`_LOCAL_WHITELIST_REQUIRED_RULES`) plus the deterministic
    scaffold entries (:data:`SCAFFOLD_GITIGNORE_ENTRIES`). Empty list means
    the ``.gitignore`` is in the expected post-scaffold state. Pure check —
    never writes; unreadable files report every required rule as missing.
    """
    cwd = Path(cwd)
    gi = cwd / ".gitignore"
    required = sorted(_LOCAL_WHITELIST_REQUIRED_RULES) + list(SCAFFOLD_GITIGNORE_ENTRIES)
    if not gi.is_file():
        return required
    try:
        rules = set(_parse_gitignore_rules(gi.read_text(encoding="utf-8")))
    except (OSError, UnicodeDecodeError):
        return required
    return [r for r in required if r not in rules]


def scaffold_local(
    cwd: str | Path,
    dirs: list[str] | None = None,
    *,
    verify: bool = True,
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

    full_review_and_improve Track C-1 adds two gitignore guarantees:

    - Deterministic entries (:data:`SCAFFOLD_GITIGNORE_ENTRIES`, e.g.
      ``.codegraph/``) are written via :func:`ensure_gitignore_entries`
      BEFORE any plugin/CLI runs — decoupled from `codegraph init` outcome.
    - A post-scaffold self-check (:func:`verify_scaffold_gitignore`) raises
      :class:`ScaffoldVerificationError` when required rules are missing
      (S-5: no silent success). Pass ``verify=False`` to restore the old
      advisory-only behaviour.

    Args:
        cwd: Working directory (repo root).
        dirs: Additional on-demand directories to create.  Only names
              listed in ON_DEMAND_DIRS are accepted; unknown names are
              silently ignored.
        verify: Run the post-scaffold gitignore self-check (default True).

    Returns:
        Path to the .local/ directory.

    Raises:
        ScaffoldVerificationError: when ``verify=True`` and required
            gitignore rules are still missing after the scaffold ran.
    """
    cwd = Path(cwd)
    ensure_local_gitignore(cwd)
    ensure_gitignore_entries(cwd, SCAFFOLD_GITIGNORE_ENTRIES)

    local_dir = cwd / ".local"
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
    _audit_gitignore_coverage(cwd, created_roots)

    if verify:
        missing_rules = verify_scaffold_gitignore(cwd)
        if missing_rules:
            raise ScaffoldVerificationError(missing_rules, cwd / ".gitignore")

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
            "> Human-maintained. Do not edit feedback source files.\n"
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
# v12.2.0 PV-02 — selective `.local/` whitelist + repair surface.
# ---------------------------------------------------------------------------
#
# Closes the v12.1.0 feedback `.local/feedbacks/feedback_for_v12.1.0.md`:
# "everything under .local/ except necessary git-repo / team-collaboration
# content should be properly ignored". The whitelist allows two team-collab
# subdirectories to be tracked under git while keeping everything else private:
#
#   * `.local/memory/specs/`  — A-4 source-of-truth contracts (per the
#                               M-004 ADR; mutated only at archive time
#                               after the change-gate composite score
#                               passes).
#   * `.local/research/`      — W-1/SI-1 gap analyses + W-7/SI-8 retros +
#                               ADRs + design docs cited by per-cycle
#                               retrospectives + W-19 archive sources.
#
# Supersedes the v9.2.3 PV-02 broad `.local/` ignore (which over-corrected
# the legacy whitelist by hiding every team-collab subdir). The repair
# surface idempotently graduates both pre-v9.2.3 whitelists AND the v9.2.3
# broad rule to the v12.2.0 whitelist block.
#
# Design constraints (S-5 strict):
# - Zero `raise` paths. Failures (unreadable .gitignore, permission
#   error, malformed UTF-8) log a WARNING and short-circuit to the
#   "no rules" branch — the helper is advisory; it MUST NOT block the
#   scaffold.
# - The most-recent audit result is cached at module level so callers
#   that need programmatic access (test fixtures, CI hooks, the
#   `devola-init doctor` surface) can read it without re-walking the
#   disk via :func:`last_gitignore_audit`.
#
# Source: v12.2.0 PV-02 dispatch + `.local/feedbacks/feedback_for_v12.1.0.md`.

VALID_GITIGNORE_AUDIT_REASON: tuple[str, ...] = (
    "directory_ignore_rule",
    "wildcard_pattern_match",
)

_LAST_GITIGNORE_AUDIT: list[Path] = []

# v12.2.0 whitelist block — single canonical multi-line block written by
# `ensure_local_gitignore`. The four rules in
# `_LOCAL_WHITELIST_REQUIRED_RULES` are the detection key (presence of all
# four indicates the block is active and no repair is needed); the v14.0.0
# `!.local/human/` negation joined the original three.
_LOCAL_WHITELIST_BLOCK_LINES: tuple[str, ...] = (
    "# DevolaFlow local workspace (whitelist team-collab subdirs; everything else private)",
    "# Per feedback_for_v12.1.0.md — narrow whitelist replaces v9.2.3 broad ignore.",
    "# Team-tracked: .local/memory/specs/ (A-4) + .local/research/ (W-7/W-19 artifacts).",
    ".local/*",
    "!.local/.gitignore",
    "!.local/memory/",
    ".local/memory/*",
    "!.local/memory/specs/",
    "!.local/memory/specs/**",
    "!.local/research/",
    "!.local/research/**",
    # v14.0.0 — track the human INPUT zone ONLY (D-4 / ADR-2). The
    # `.local/human/*` re-exclusion keeps output/ + archive/ PRIVATE (D2
    # locked) while `!.local/human/input/**` re-includes the authoritative
    # INPUT zone — mirrors the `!.local/memory/` -> `.local/memory/*` ->
    # `!.local/memory/specs/` precedent above.
    "!.local/human/",
    ".local/human/*",
    "!.local/human/input/",
    "!.local/human/input/**",
)

_LOCAL_WHITELIST_REQUIRED_RULES: frozenset[str] = frozenset(
    {
        ".local/*",
        "!.local/memory/specs/",
        "!.local/research/",
        "!.local/human/",
    }
)

# Banner comments that introduced the v9.2.3 / pre-v12.2.0 ignore blocks.
# Stripped during repair so the v12.2.0 block lands cleanly without
# orphaned headers.
_OLD_LOCAL_BANNER_COMMENTS: frozenset[str] = frozenset(
    {
        "# DevolaFlow local workspace (private)",
        "# DevolaFlow private workspace state",
    }
)

# v9.2.3 PV-02 broad rule — superseded by the v12.2.0 whitelist.
_V92_LOCAL_BROAD_RULE: str = ".local/"

# Legacy whitelist set (pre-v9.2.3). The v12.2.0 repair path strips each
# of these so the new block is the single source-of-truth in the file.
_OLD_LOCAL_WHITELIST_RULES: frozenset[str] = frozenset(
    {
        ".local/*",
        "!.local/.agent/",
        "!.local/.agent/**",
        "!.local/memory/",
        ".local/memory/*",
        "!.local/memory/specs/",
        "!.local/memory/specs/**",
        ".local/.agent/active/*/learnings.jsonl",
        ".local/.agent/archive/*/learnings.jsonl",
        ".local/memory/operational.jsonl",
        ".local/memory/session_state.json",
        ".local/memory/prefs.md",
        ".local/memory/plugin_install.log",
    }
)

# Union of every rule the v12.2.0 repair path KNOWS how to graduate
# (legacy whitelist + v9.2.3 broad). Detection helpers iterate over this
# set; rules outside it are left alone (hand-authored ignores survive).
_SUPERSEDED_LOCAL_RULES: frozenset[str] = _OLD_LOCAL_WHITELIST_RULES | frozenset(
    {_V92_LOCAL_BROAD_RULE}
)


def _parse_gitignore_rules(text: str) -> list[str]:
    """Return non-comment non-empty rules from a ``.gitignore`` text blob."""
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def _has_correct_local_whitelist(rules: list[str]) -> bool:
    """Return True iff parsed ``rules`` already contain the v12.2.0 whitelist.

    Detection key: the 4 rules in
    :data:`_LOCAL_WHITELIST_REQUIRED_RULES` must all be present (the original
    three plus the v14.0.0 ``!.local/human/`` negation). Presence of any
    subset (but not all 4) is treated as a partial/legacy state and triggers
    the repair path.
    """
    rule_set = set(rules)
    return _LOCAL_WHITELIST_REQUIRED_RULES.issubset(rule_set)


def _is_broad_local_ignore_rule(rule: str) -> bool:
    """Return True when ``rule`` is the v9.2.3 broad ``.local/`` rule.

    Preserved as a public helper for the audit-suppression branch in
    :func:`_audit_gitignore_coverage` and for the v9.2.3 W-18 ghost-audit
    pin in ``tests/test_no_ghost_features.py``. The v12.2.0 PV-02 repair
    path no longer relies on this helper directly — :func:`ensure_local_gitignore`
    walks :data:`_SUPERSEDED_LOCAL_RULES` instead.
    """
    if rule.startswith("!"):
        return False
    return rule.lstrip("/").rstrip("/") == ".local"


def _narrow_local_ignore_rules(rules: list[str]) -> list[str]:
    """Return ``.local``-scoped ignores narrower than the v12.2.0 whitelist.

    Used by :func:`ensure_local_gitignore` to surface hand-authored narrow
    rules (e.g. ``.local/.agent/active/``) so the operator sees a WARN
    pointing at the surviving rule when the v12.2.0 whitelist is appended
    alongside (rather than replacing) the narrow rule.
    """
    narrow: list[str] = []
    for rule in rules:
        if rule.startswith("!"):
            continue
        if rule in _SUPERSEDED_LOCAL_RULES:
            continue
        cleaned = rule.lstrip("/")
        if cleaned.startswith(".local/"):
            narrow.append(rule)
    return narrow


def ensure_local_gitignore(cwd: str | Path) -> bool:
    """Ensure consumer repos keep ``.local/`` private with v12.2.0 whitelist.

    Idempotent: returns ``False`` (no write) when the v12.2.0 whitelist
    block is already present. Otherwise strips superseded rules (the
    v9.2.3 broad ``.local/`` + legacy pre-v9.2.3 whitelist entries) AND
    their orphaned banner comments, then appends the v12.2.0 whitelist
    block.

    The helper is intentionally advisory for read/write failures: normal
    scaffold flows still create the workspace, but failures log an explicit
    WARNING per S-5 (no silent failures).

    Returns:
        True when ``.gitignore`` was created or changed, False otherwise.
    """
    cwd = Path(cwd)
    gi = cwd / ".gitignore"

    if gi.exists():
        try:
            text = gi.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            _LOGGER.warning(
                "scaffold_local: could not read %s: %s; unable to ensure .local/ whitelist",
                gi,
                exc,
            )
            return False
    else:
        text = ""

    lines = text.splitlines()
    rules = _parse_gitignore_rules(text)

    if _has_correct_local_whitelist(rules):
        return False

    has_old_whitelist = any(rule in _OLD_LOCAL_WHITELIST_RULES for rule in rules)
    has_v92_broad = any(_is_broad_local_ignore_rule(rule) for rule in rules)

    new_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped in _SUPERSEDED_LOCAL_RULES:
            continue
        if stripped in _OLD_LOCAL_BANNER_COMMENTS:
            continue
        new_lines.append(line)

    if has_old_whitelist:
        _LOGGER.info(
            "scaffold_local: repaired legacy .local gitignore whitelist rules in %s "
            "(graduated to v12.2.0 selective whitelist)",
            gi,
        )
    if has_v92_broad:
        _LOGGER.info(
            "scaffold_local: repaired v9.2.3 broad .local/ rule in %s "
            "(graduated to v12.2.0 selective whitelist; "
            ".local/memory/specs/ + .local/research/ now tracked by default)",
            gi,
        )

    surviving_rules = _parse_gitignore_rules("\n".join(new_lines))
    narrow_rules = _narrow_local_ignore_rules(surviving_rules)
    if narrow_rules:
        _LOGGER.warning(
            "scaffold_local: %s has narrow .local ignore rule(s) %s surviving alongside the "
            "v12.2.0 whitelist; adding `.local/*` block — review the narrow rule if it "
            "intentionally hides files the whitelist would otherwise track.",
            gi,
            ", ".join(narrow_rules),
        )

    if new_lines and new_lines[-1].strip():
        new_lines.append("")
    new_lines.extend(_LOCAL_WHITELIST_BLOCK_LINES)

    new_text = "\n".join(new_lines).rstrip() + "\n"
    try:
        gi.write_text(new_text, encoding="utf-8")
    except OSError as exc:
        _LOGGER.warning(
            "scaffold_local: could not write %s: %s; unable to ensure .local/ whitelist",
            gi,
            exc,
        )
        return False

    return True


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
    return _parse_gitignore_rules(text)


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
    * Negation rules (``!pattern``) are skipped — broad ``.local/``
      coverage is the desired scaffold state, so the audit only needs
      positive ignore matches.
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

    Side effect — emits one WARNING log per match enumerating the ignored
    path (repo-relative POSIX). The audit is intentionally suppressed when
    the repo root already carries either:

    1. the v12.2.0 selective whitelist block (the canonical state after
       :func:`ensure_local_gitignore` runs), OR
    2. the legacy v9.2.3 broad ``.local/`` rule (still a valid private
       state for repos that have not yet adopted the v12.2.0 whitelist).

    Caches the returned list at module level so :func:`last_gitignore_audit`
    can return it without re-walking the disk.
    """
    global _LAST_GITIGNORE_AUDIT
    rules = _read_gitignore_rules(cwd)
    if not rules:
        _LAST_GITIGNORE_AUDIT = []
        return []
    if _has_correct_local_whitelist(rules):
        _LAST_GITIGNORE_AUDIT = []
        return []
    if any(_is_broad_local_ignore_rule(rule) for rule in rules):
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
                "and will remain private. Adopt the v12.2.0 whitelist block "
                "(written automatically by `ensure_local_gitignore`) if you "
                "want DevolaFlow's team-collab subdirs tracked while keeping "
                "the rest private.",
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


if __name__ == "__main__":
    # full_review_and_improve Track C-1 (R5 F1-H2): `scripts/install.sh local`
    # has invoked `python3 -m devolaflow.local.workspace` since v9.x, but the
    # module had no __main__ path — the call imported the module and exited 0
    # without scaffolding anything (silent no-op). This block makes the
    # historic invocation real. Failures propagate as a traceback + non-zero
    # exit per S-5; the ScaffoldVerificationError message carries the exact
    # missing rules.
    scaffold_local(Path.cwd())
    print(".local/ workspace scaffolded (directories + gitignore verified).")
