"""Runtime wiring adapters — ``fire_file_write`` + ``fire_task_stop``.

v14.3.0 G-001 closure per
``docs/cycle-archive/adr/v15-ADR-003-output-closure-enforcement-locus.md``
("WIRE the hooks — two-phase"): the ``file_write`` (``check_file_ownership``)
and ``task_stop`` (``test_on_complete``) lifecycle hooks shipped UNWIRED for
7 major versions while SKILL.md §"Lifecycle Hooks" advertised write/stop-time
enforcement. This module is the execution-side adapter that gives both
events their FIRST production call sites:

* :func:`fire_file_write` — invoked by the framework's own change-driven
  write surface (:meth:`devolaflow.agent_workspace.change.Change.
  to_active_folder`) BEFORE each artifact write. Builds the S-8 allowed
  set (owned_files manifest from the active change context, plus the
  S-8 §2/§3 directory exemptions materialised for the exact-match hook)
  and dispatches ``run_hooks("file_write", payload)``.
* :func:`fire_task_stop` — invoked at the L2 report emission surface
  (:meth:`devolaflow.agent_workspace.handoff.HandoffStore.write_envelope`
  for ``StatusReport`` envelopes) with the report block as payload. The
  default ``test_on_complete`` handler consumes the report's in-memory
  ``metrics`` block — it spawns NO subprocesses (ADR-003 §Decision 2).

Behaviour contract (R5 strict, mirrors ``auto_write_handoff``):

1. **Gate 1 (env-flag OFF)** — if ``DEVOLAFLOW_AGENT_WORKSPACE`` is unset
   or anything other than the literal string ``"1"``, both adapters
   return ``None`` with ZERO filesystem I/O and ZERO ``run_hooks``
   dispatch. Every non-opted-in code path is byte-identical to v14.2.x.
   Per Workflow Rule W-20 (env-flag reuse-first) the flag REUSES the
   activation surface S-8 already binds to (same flag as A-6 workspace
   engagement + the ``pre_handoff`` auto-write) — NO new env flag.

2. **Gate 2 (no change context)** — ``fire_file_write`` with neither an
   explicit ``owned_files`` manifest nor a resolvable ``change_id``
   manifest is a clean no-op (``None``): per Soul Rule S-8 the ownership
   check is scoped to change-driven flows with an active change folder.

3. **Strict default (v15.0.0)** — per ADR-003 §Decision 3 (the G-038
   strict-graduation cluster), the engaged-mode default flips
   permissive → STRICT: an ownership violation (``file_write``) or a
   failing report (``task_stop``) raises the top-severity
   :class:`HookViolation` — block + escalate per S-8 "mode: full".
   Opt-out: pass ``strict=False`` explicitly (S-8 "mode: lite" — the
   v14.3.0 warn + log behaviour; S-5 — the WARN actually logs). The
   ``strict`` parameter is the sole opt-out surface; NO env flag is
   added and the Gate-1 activation flag is UNCHANGED (W-20).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from devolaflow.lifecycle.check_file_ownership import EVENT as _FILE_WRITE_EVENT
from devolaflow.lifecycle.dispatcher import HookResult, run_hooks
from devolaflow.lifecycle.test_on_complete import EVENT as _TASK_STOP_EVENT

ENV_FLAG: str = "DEVOLAFLOW_AGENT_WORKSPACE"
ENV_FLAG_TRUTHY: str = "1"

logger = logging.getLogger(__name__)


def is_workspace_engaged() -> bool:
    """True iff the W-20-reused activation flag is EXACTLY the string ``"1"``.

    R5 strict parsing — absent, ``"0"``, ``"true"``, ``"yes"`` etc. all
    read as OFF, matching ``auto_write_handoff`` / Architecture rule
    A-6.2 byte-for-byte so the two surfaces can never disagree.
    """
    return os.environ.get(ENV_FLAG, "") == ENV_FLAG_TRUTHY


def _normalise_abs(path: str | Path) -> str:
    """Absolute + normalised form of *path* for directory-containment checks."""
    return os.path.normpath(os.path.abspath(str(path)))


def _is_under(target: str | Path, ancestor: str | Path) -> bool:
    """True iff *target* equals *ancestor* or lives inside it."""
    t = _normalise_abs(target)
    a = _normalise_abs(ancestor)
    return t == a or t.startswith(a + os.sep)


def _resolve_manifest(
    change_id: str,
    repo_root: str | Path | None,
) -> tuple[list[str] | None, Path | None]:
    """Read the ``owned_files.txt`` manifest for *change_id*.

    Returns ``(manifest, change_folder)``; ``manifest`` is ``None`` when
    the active change folder carries no manifest (the caller treats that
    as "no active change context" per Gate 2). Lazy-imports the
    agent-workspace path constant so the SSOT for the active-folder
    layout stays on :mod:`devolaflow.agent_workspace.change` (A-5) and
    the lifecycle package remains import-light on the hot no-op path.
    """
    from devolaflow.agent_workspace.change import ACTIVE_DIR_DEFAULT

    root = Path(repo_root) if repo_root is not None else Path.cwd()
    folder = root / ACTIVE_DIR_DEFAULT / change_id
    manifest_path = folder / "owned_files.txt"
    if not manifest_path.is_file():
        return None, folder if folder.is_dir() else None
    lines = manifest_path.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip()], folder


def _is_s8_exempt(
    target: str | Path,
    change_folder: str | Path | None,
    repo_root: str | Path | None,
) -> bool:
    """True iff *target* falls under the S-8 §2/§3 directory exemptions.

    Soul Rule S-8 allows writes to (2) the change folder itself and
    (3) the agent's handoff outbox, in ADDITION to (1) the
    ``owned_files.txt`` manifest. ``check_file_ownership`` performs
    exact-path membership, so the adapter evaluates the two
    directory-scoped union items here and materialises a hit by
    appending the exact target to the allowed list it hands the hook.
    """
    if change_folder is not None and _is_under(target, change_folder):
        return True

    from devolaflow.agent_workspace.handoff import HANDOFF_DIR_DEFAULT

    root = Path(repo_root) if repo_root is not None else Path.cwd()
    return _is_under(target, root / HANDOFF_DIR_DEFAULT)


def fire_file_write(
    path: str | Path,
    *,
    owned_files: list[str] | None = None,
    change_id: str | None = None,
    change_folder: str | Path | None = None,
    repo_root: str | Path | None = None,
    strict: bool = True,
) -> HookResult | None:
    """Fire the ``file_write`` hook for a framework-surface write to *path*.

    Call BEFORE performing the write (ADR-003: "fires ``file_write``
    before owned-file writes") so the strict default (v15.0.0
    graduation) blocks the write instead of post-hoc reporting it.

    Args:
      path: Write target (relative paths are interpreted against the
        process cwd, matching the manifest convention of repo-root-
        relative entries when the process runs at the repo root).
      owned_files: Explicit manifest (S-8 union item 1). When supplied,
        no filesystem resolution happens.
      change_id: Active change id; used to resolve the manifest from
        ``.local/.agent/active/<change_id>/owned_files.txt`` when
        ``owned_files`` is not supplied.
      change_folder: The active change folder for the S-8 §2 exemption.
        Defaults to the folder resolved from ``change_id`` (if any).
      repo_root: Root for resolving the active/handoff trees (defaults
        to ``Path.cwd()``).
      strict: ``True`` (STRICT default since v15.0.0, S-8 "mode: full"
        per ADR-003 §Decision 3) → an ownership violation raises the
        top-severity :class:`HookViolation` out of ``run_hooks`` —
        block + escalate. Opt-out: pass ``strict=False`` explicitly
        (S-8 "mode: lite") → violations WARN and are returned on the
        result, the v14.3.0 permissive behaviour.

    Returns:
      ``None`` when Gate 1 (env flag) or Gate 2 (no change context)
      short-circuits; otherwise the aggregate :class:`HookResult` from
      ``run_hooks("file_write", ...)``.
    """
    if not is_workspace_engaged():
        return None

    folder = Path(change_folder) if change_folder is not None else None
    manifest = list(owned_files) if owned_files is not None else None

    if manifest is None and change_id:
        manifest, resolved_folder = _resolve_manifest(change_id, repo_root)
        if folder is None:
            folder = resolved_folder

    if manifest is None:
        return None

    allowed = list(manifest)
    if _is_s8_exempt(path, folder, repo_root):
        allowed.append(str(path))

    payload: dict[str, Any] = {"path": str(path), "owned_files": allowed}
    if change_id:
        payload["change_id"] = change_id
    return run_hooks(_FILE_WRITE_EVENT, payload, strict=strict)


def fire_task_stop(
    report: dict[str, Any],
    *,
    strict: bool = True,
) -> HookResult | None:
    """Fire the ``task_stop`` hook for a finalised L2 status report.

    *report* is the StatusReport payload (lean top-level
    ``tests_passed`` / ``tests_failed`` / ``lint_status`` fields or the
    nested ``metrics`` block — both shapes are accepted by the default
    ``test_on_complete`` handler). The handler consumes the in-memory
    report evidence only; it spawns NO subprocesses (ADR-003
    §Decision 2 — the report-side ``self_check`` / ``ac_results``
    evidence transport is the v15-ADR-007 companion).

    ``strict`` is ``True`` by default since v15.0.0 (S-8 "mode: full"
    per ADR-003 §Decision 3): a failing report (e.g. ``tests_failed >
    0`` / lint not clean) raises the top-severity
    :class:`HookViolation` so the P4 retry classifier can catch +
    escalate. Opt-out: pass ``strict=False`` explicitly (S-8 "mode:
    lite" — the v14.3.0 warn-and-return behaviour).

    Returns ``None`` when the env flag is OFF (Gate 1 — zero IO, zero
    ``run_hooks`` dispatch; the activation gate is UNCHANGED by the
    strict flip); otherwise the aggregate :class:`HookResult` from
    ``run_hooks("task_stop", ...)``.
    """
    if not is_workspace_engaged():
        return None
    return run_hooks(_TASK_STOP_EVENT, report, strict=strict)


__all__ = [
    "ENV_FLAG",
    "ENV_FLAG_TRUTHY",
    "fire_file_write",
    "fire_task_stop",
    "is_workspace_engaged",
]
