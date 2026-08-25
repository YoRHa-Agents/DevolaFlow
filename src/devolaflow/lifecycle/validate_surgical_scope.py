"""Surgical-scope diff verifier — mechanical BG-003 tier checks.

v14.4.0 (task v14.4.0-T2-surgical-scope) closes the F-P1 product-review
gap: ``workflow-system/agent/references/behavioral-guidelines.md`` Rule 3
(BG-003 ``surgical_scope``) defines three tiers — line / function /
module — but until now NO Python module verified any tier; the rule was
prompt-only self-discipline. This module is the PURE analysis layer that
the v14.3.0 runtime-wiring surfaces (``fire_task_stop``) and the
``artifact-quality.md`` §2(b) "Minimal diff" dimension can consume.

Tier mapping (verbatim from BG-003's tier table):

* ``module`` — "Compare diff filename set against ``owned_files``" →
  :func:`check_module_scope`. Mirrors the S-8 §2/§3 directory
  exemptions used by ``runtime_wiring._is_s8_exempt`` (change folder +
  handoff outbox).
* ``function`` — "Walk diff hunks; reject hunks that cross declared
  function boundaries" → :func:`check_function_scope`, driven by
  ``git diff -U0`` hunk headers checked against declared line ranges.
  NOTE: dispatch payloads do NOT yet carry an
  ``owned_files[*].line_ranges`` shape (only LL-004 in
  behavioral-guidelines.md names it); this module defines the shape
  forward as ``{path: [(start, end), ...]}`` — 1-based inclusive
  new-side line ranges. Dispatch-side population is a future slice.
* ``line`` — currently aliased to ``function`` per the BG-003 tier
  table ("Future v8.2.0 work"); the prompt-side LL-001..LL-005
  criteria remain L2 self-audit territory.

Purity contract: every function is side-effect free EXCEPT the
documented, bounded ``git`` subprocess (read-only ``git diff``
invocations, ``timeout=GIT_TIMEOUT_SECONDS``). Errors raise
:class:`SurgicalScopeError` per Soul Rule S-5 — a failed git run NEVER
silently degrades to an empty diff.

Lifecycle wiring: :func:`validate_surgical_scope` is the hook-shaped
handler (``handler(payload, *, strict=False) -> HookResult``). It is
NOT in the default chain — default wiring is a v15.0.0 decision (rides
the ADR-003 strict-graduation cluster). Operators opt in per session
via :func:`register_surgical_scope_hook`, which appends the handler as
an extra on the ``task_stop`` event (clearable via ``clear_hooks``).
Payloads without a ``surgical_scope`` block are a clean no-op so the
existing ``test_on_complete`` StatusReport payloads pass byte-identical.
"""

from __future__ import annotations

import posixpath
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from devolaflow.lifecycle.dispatcher import (
    HookResult,
    HookViolation,
    finalize,
    register_hook,
)

EVENT = "task_stop"

GIT_TIMEOUT_SECONDS: int = 30
"""Hard ceiling for every git subprocess (bounded-shell constraint)."""

_HUNK_HEADER_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")

LineRanges = dict[str, list[tuple[int, int]]]
"""Forward-defined function-tier manifest shape: repo-relative path →
1-based inclusive ``(start, end)`` line ranges on the NEW side of the
diff. Mirrors the LL-004 ``owned_files[*].line_ranges`` prose; the
dispatch-side population is a future slice."""


class SurgicalScopeError(RuntimeError):
    """Raised when the git subprocess cannot produce a trustworthy diff.

    Covers: missing ``git`` binary, non-existent ``repo_root``, bad
    ``base_ref``, non-zero git exit, and subprocess timeout. Per S-5
    these conditions RAISE — they never return an empty
    :class:`DiffStats` that a caller could mistake for "no changes".
    """


@dataclass(frozen=True)
class FileDiffStat:
    """Per-file ``git diff --numstat`` row (binary rows carry 0/0)."""

    path: str
    insertions: int
    deletions: int
    binary: bool = False


@dataclass(frozen=True)
class DiffStats:
    """Aggregate diff measurement vs ``base_ref`` (artifact-quality §2(b))."""

    base_ref: str
    files: tuple[FileDiffStat, ...]
    insertions: int
    deletions: int

    @property
    def changed_paths(self) -> tuple[str, ...]:
        """Repo-relative paths of every changed file, in diff order."""
        return tuple(f.path for f in self.files)


@dataclass(frozen=True)
class ScopeViolation:
    """A single BG-003 tier breach (severity is always blocker per BG-003)."""

    code: str
    tier: str
    path: str
    message: str


def _run_git(repo_root: str | Path, *args: str) -> str:
    """Run a bounded, read-only git command; return stdout or raise (S-5)."""
    root = Path(repo_root)
    if not root.is_dir():
        raise SurgicalScopeError(f"repo_root is not a directory: {root}")
    argv = ["git", "-C", str(root), *args]
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except FileNotFoundError as exc:
        raise SurgicalScopeError("git binary not found on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise SurgicalScopeError(
            f"git timed out after {GIT_TIMEOUT_SECONDS}s: {' '.join(argv)}"
        ) from exc
    if proc.returncode != 0:
        raise SurgicalScopeError(
            f"git exited {proc.returncode}: {' '.join(argv)} — {proc.stderr.strip()}"
        )
    return proc.stdout


def collect_diff_stats(repo_root: str | Path, base_ref: str = "HEAD") -> DiffStats:
    """Measure the working-tree diff against *base_ref* via ``--numstat``.

    Counts tracked changes (staged + unstaged) relative to *base_ref*;
    untracked-and-unstaged files are invisible to ``git diff`` by design
    (the S-8 write-time hook covers those). ``--no-renames`` keeps the
    parse shape stable: a rename surfaces as delete + add, so BOTH paths
    participate in scope checks. Binary rows (``-\t-\tpath``) yield a
    :class:`FileDiffStat` with ``binary=True`` and 0/0 counts.

    Raises :class:`SurgicalScopeError` on any git failure (S-5).
    """
    out = _run_git(repo_root, "diff", "--no-ext-diff", "--no-renames", "--numstat", base_ref)
    files: list[FileDiffStat] = []
    total_ins = 0
    total_del = 0
    for line in out.splitlines():
        if not line.strip():
            continue
        ins_raw, del_raw, path = line.split("\t", 2)
        binary = ins_raw == "-" or del_raw == "-"
        ins = 0 if binary else int(ins_raw)
        dels = 0 if binary else int(del_raw)
        files.append(FileDiffStat(path=path, insertions=ins, deletions=dels, binary=binary))
        total_ins += ins
        total_del += dels
    return DiffStats(
        base_ref=base_ref,
        files=tuple(files),
        insertions=total_ins,
        deletions=total_del,
    )


def _normalise_rel(path: str) -> str:
    """Normalise a repo-relative POSIX path for set comparison."""
    return posixpath.normpath(path.strip()).strip("/")


def _is_under_rel(target: str, ancestor: str) -> bool:
    """True iff repo-relative *target* equals *ancestor* or lives inside it."""
    t = _normalise_rel(target)
    a = _normalise_rel(ancestor)
    return t == a or t.startswith(a + "/")


def _is_s8_exempt_rel(path: str, change_folder: str | None) -> bool:
    """S-8 §2/§3 exemptions on repo-relative diff paths.

    Mirrors ``runtime_wiring._is_s8_exempt`` (which operates on absolute
    write targets) for the diff-side repo-relative path shape: (§2) the
    active change folder itself, (§3) the handoff outbox. The handoff
    constant is lazily imported so the SSOT stays on
    :mod:`devolaflow.agent_workspace.handoff` (A-5).
    """
    if change_folder is not None and _is_under_rel(path, change_folder):
        return True

    from devolaflow.agent_workspace.handoff import HANDOFF_DIR_DEFAULT

    return _is_under_rel(path, HANDOFF_DIR_DEFAULT.as_posix())


def check_module_scope(
    diff_stats: DiffStats,
    owned_files: list[str],
    *,
    change_folder: str | None = None,
) -> list[ScopeViolation]:
    """Module tier: changed-filename set ⊆ ``owned_files`` manifest.

    *change_folder* is the repo-relative active change folder (S-8 §2
    exemption); the handoff outbox (S-8 §3) is always exempt. Returns
    one ``SSV001`` violation per out-of-manifest changed file.
    """
    owned = {_normalise_rel(p) for p in owned_files}
    violations: list[ScopeViolation] = []
    for path in diff_stats.changed_paths:
        normalised = _normalise_rel(path)
        if normalised in owned or _is_s8_exempt_rel(normalised, change_folder):
            continue
        violations.append(
            ScopeViolation(
                code="SSV001",
                tier="module",
                path=path,
                message=(
                    f"BG-003 module-tier breach: '{path}' changed but is not in "
                    f"the owned_files manifest"
                ),
            )
        )
    return violations


def _iter_diff_hunks(repo_root: str | Path, base_ref: str) -> list[tuple[str, int, int]]:
    """Yield ``(path, new_start, new_count)`` per hunk of ``git diff -U0``.

    *path* is the new-side repo-relative path (a-side for pure
    deletions). Pure-deletion hunks (``new_count == 0``) are anchored at
    ``max(new_start, 1)`` so range checks have a concrete line to test.
    """
    out = _run_git(repo_root, "diff", "--no-ext-diff", "--no-renames", "-U0", base_ref)
    hunks: list[tuple[str, int, int]] = []
    current_a: str | None = None
    current: str | None = None
    for line in out.splitlines():
        if line.startswith("--- "):
            target = line[4:]
            current_a = None if target == "/dev/null" else target.removeprefix("a/")
        elif line.startswith("+++ "):
            target = line[4:]
            current = current_a if target == "/dev/null" else target.removeprefix("b/")
        elif line.startswith("@@") and current is not None:
            match = _HUNK_HEADER_RE.match(line)
            if match is None:
                raise SurgicalScopeError(f"unparseable hunk header: {line!r}")
            new_start = int(match.group(3))
            new_count = int(match.group(4)) if match.group(4) is not None else 1
            hunks.append((current, new_start, new_count))
    return hunks


def _merged_ranges(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Merge overlapping/adjacent 1-based inclusive ranges; validate shape."""
    cleaned: list[tuple[int, int]] = []
    for entry in ranges:
        start, end = int(entry[0]), int(entry[1])
        if start < 1 or end < start:
            raise ValueError(f"invalid line range (1-based inclusive): {entry!r}")
        cleaned.append((start, end))
    cleaned.sort()
    merged: list[tuple[int, int]] = []
    for start, end in cleaned:
        if merged and start <= merged[-1][1] + 1:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def check_function_scope(
    repo_root: str | Path,
    owned_files_with_ranges: LineRanges,
    base_ref: str = "HEAD",
) -> list[ScopeViolation]:
    """Function tier: every hunk in a declared file stays inside its ranges.

    *owned_files_with_ranges* uses the forward-defined shape
    ``{path: [(start, end), ...]}`` (see :data:`LineRanges`). Hunks in
    files WITHOUT a declared-range entry are not judged here — filename
    containment is the module tier's job (:func:`check_module_scope`);
    :func:`evaluate_surgical_scope` composes both for function-tier runs.
    Returns one ``SSV002`` violation per out-of-range hunk.
    """
    declared = {
        _normalise_rel(path): _merged_ranges(list(ranges))
        for path, ranges in owned_files_with_ranges.items()
    }
    violations: list[ScopeViolation] = []
    for path, new_start, new_count in _iter_diff_hunks(repo_root, base_ref):
        ranges = declared.get(_normalise_rel(path))
        if ranges is None:
            continue
        span_start = max(new_start, 1)
        span_end = span_start + max(new_count, 1) - 1
        in_range = any(start <= span_start and span_end <= end for start, end in ranges)
        if not in_range:
            violations.append(
                ScopeViolation(
                    code="SSV002",
                    tier="function",
                    path=path,
                    message=(
                        f"BG-003 function-tier breach: hunk at lines "
                        f"{span_start}-{span_end} of '{path}' falls outside the "
                        f"declared line_ranges {ranges}"
                    ),
                )
            )
    return violations


def evaluate_surgical_scope(
    repo_root: str | Path,
    *,
    owned_files: list[str] | None = None,
    line_ranges: LineRanges | None = None,
    base_ref: str = "HEAD",
    change_folder: str | None = None,
) -> dict[str, Any]:
    """Orchestrating entry — tier auto-selected by available metadata.

    * ``line_ranges`` present → ``function`` tier: range adherence PLUS
      module containment against ``owned_files ∪ line_ranges.keys()``
      (a function-tier task is module-bounded by BG-003 composition).
    * ``owned_files`` only → ``module`` tier.
    * Neither → ``stats_only``: measure the diff, judge nothing.

    Returns ``{"tier_checked": str, "violations": list[ScopeViolation],
    "diff_stats": DiffStats}``. Raises :class:`SurgicalScopeError` /
    ``ValueError`` on git failure or malformed ranges (S-5).
    """
    diff_stats = collect_diff_stats(repo_root, base_ref)

    if line_ranges:
        manifest = list(owned_files or []) + list(line_ranges)
        violations = check_module_scope(diff_stats, manifest, change_folder=change_folder)
        violations += check_function_scope(repo_root, line_ranges, base_ref)
        tier = "function"
    elif owned_files:
        violations = check_module_scope(diff_stats, owned_files, change_folder=change_folder)
        tier = "module"
    else:
        violations = []
        tier = "stats_only"

    return {"tier_checked": tier, "violations": violations, "diff_stats": diff_stats}


def _violations_from_block(block: dict[str, Any]) -> list[HookViolation]:
    """Evaluate a ``surgical_scope`` payload block into hook violations."""
    line_ranges_raw = block.get("line_ranges") or {}
    line_ranges: LineRanges = {
        str(path): [(int(r[0]), int(r[1])) for r in ranges]
        for path, ranges in line_ranges_raw.items()
    }
    verdict = evaluate_surgical_scope(
        block.get("repo_root", "."),
        owned_files=block.get("owned_files"),
        line_ranges=line_ranges,
        base_ref=block.get("base_ref", "HEAD"),
        change_folder=block.get("change_folder"),
    )
    return [
        HookViolation(
            code=v.code,
            message=v.message,
            severity="blocker",
            context={"tier": v.tier, "path": v.path},
        )
        for v in verdict["violations"]
    ]


def validate_surgical_scope(
    payload: dict[str, Any],
    *,
    strict: bool = False,
) -> HookResult:
    """Hook-shaped BG-003 verifier for the ``task_stop`` event (opt-in).

    Activation gate (mirrors ``runtime_wiring`` Gate 2): the payload
    must carry a ``surgical_scope`` mapping —
    ``{"repo_root", "base_ref", "owned_files", "line_ranges",
    "change_folder"}`` (all optional inside the block). Payloads without
    the block (every existing StatusReport shape) return a clean result
    with a metadata reason — a documented no-op, not a swallowed error.

    Tier breaches surface as ``blocker`` violations (BG-003 severity);
    a malformed block is ``SSV003`` (error) and a git failure is
    ``SSV004`` (error) — explicit error states per S-5, so a permissive
    chain run records the failure instead of aborting mid-aggregate.
    """
    if not isinstance(payload, dict):
        return finalize(
            EVENT,
            [
                HookViolation(
                    code="SSV003",
                    message="surgical-scope payload is not a mapping",
                    severity="error",
                    context={"payload_type": type(payload).__name__},
                )
            ],
            strict=strict,
        )

    block = payload.get("surgical_scope")
    if block is None:
        return HookResult(
            event=EVENT,
            passed=True,
            metadata={"reason": "no surgical_scope block — opt-in verifier no-op"},
        )
    if not isinstance(block, dict):
        return finalize(
            EVENT,
            [
                HookViolation(
                    code="SSV003",
                    message="'surgical_scope' block must be a mapping",
                    severity="error",
                    context={"block_type": type(block).__name__},
                )
            ],
            strict=strict,
        )

    try:
        violations = _violations_from_block(block)
    except (SurgicalScopeError, ValueError, TypeError, KeyError, IndexError) as exc:
        violations = [
            HookViolation(
                code="SSV004",
                message=f"surgical-scope evaluation failed: {exc}",
                severity="error",
                context={"error_type": type(exc).__name__},
            )
        ]
    return finalize(EVENT, violations, strict=strict)


def register_surgical_scope_hook(event: str = EVENT) -> None:
    """Opt-in: append :func:`validate_surgical_scope` as an extra on *event*.

    NOT called at import time — the default ``task_stop`` chain stays
    byte-stable at ``(test_on_complete,)`` (default wiring is a v15.0.0
    decision per the ADR-003 strict-graduation telegraph). Operators
    undo the registration with ``clear_hooks(event)``.
    """
    register_hook(event, validate_surgical_scope)


__all__ = [
    "EVENT",
    "GIT_TIMEOUT_SECONDS",
    "DiffStats",
    "FileDiffStat",
    "LineRanges",
    "ScopeViolation",
    "SurgicalScopeError",
    "check_function_scope",
    "check_module_scope",
    "collect_diff_stats",
    "evaluate_surgical_scope",
    "register_surgical_scope_hook",
    "validate_surgical_scope",
]
