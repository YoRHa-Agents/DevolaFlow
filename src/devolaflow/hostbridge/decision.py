"""Bridge decision core — routes host tool events into the lifecycle chain.

v17.0.0 R2 (G17-B1 closure, design §D-R2-1/§D-R2-2). The single public
entry point is :func:`decide`:

1. **Fast path (R5 strict)** — when ``DEVOLAFLOW_HOST_ENFORCE`` is not
   EXACTLY the literal string ``"1"``, every event is allowed with ZERO
   filesystem IO and zero ``run_hooks`` dispatch. The flag is a NEW
   env var deliberately decoupled from ``DEVOLAFLOW_AGENT_WORKSPACE``
   per W-20 §3 orthogonality: that flag activates workspace scaffolding
   plus the framework-internal ``fire_*`` write adapters, while THIS
   flag activates interception of HOST tool events — a different
   runtime surface (operators may enforce without scaffolding, or
   scaffold without enforcing). Full argument:
   ``references/env-flags.md`` §2.18.
2. **file_write** — the owned set is the UNION of every active
   change's ``.local/.agent/active/<id>/owned_files.txt`` manifest
   (no active change → allow), with the S-8 §2/§3 directory
   exemptions materialised exactly the way
   ``lifecycle/runtime_wiring.py`` does (targets inside a change
   folder itself or ``.local/.agent/handoff/`` are appended to the
   allowed list before the hook fires). A ``CFO006`` blocker from
   ``run_hooks("file_write", ...)`` denies with a reason quoting the
   path and the active change id(s).
3. **shell** — ALWAYS allowed. ``run_hooks("pre_shell_call", ...)``
   fires for advisory rewrite metadata only (this bridge is the FIRST
   production caller of that hook); its errors are swallowed into the
   audit record (S-5 — logged, never crashing the bridge).
4. **Audit** — every enforced decision appends one JSONL line to
   ``.local/telemetry/hostbridge.jsonl`` (see :mod:`.audit`).
5. **Fail-open** — ANY internal exception yields ``verdict
   "error_allow"`` plus an audit line; :func:`decide` never raises.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from devolaflow.hostbridge.audit import append_audit, build_audit_record
from devolaflow.hostbridge.normalize import (
    KIND_FILE_WRITE,
    KIND_SHELL,
    BridgeEvent,
)

logger = logging.getLogger(__name__)

ENV_FLAG: str = "DEVOLAFLOW_HOST_ENFORCE"
ENV_FLAG_TRUTHY: str = "1"

VERDICT_ALLOW = "allow"
VERDICT_DENY = "deny"
VERDICT_ERROR_ALLOW = "error_allow"

_CFO_OWNERSHIP_BREACH = "CFO006"


def is_host_enforce_active() -> bool:
    """True iff the enforcement flag is EXACTLY the string ``"1"``.

    R5 strict parsing — absent, ``"0"``, ``"true"``, ``"01"`` etc. all
    read as OFF, matching the §6 conjunction contract in
    ``references/env-flags.md``.
    """
    return os.environ.get(ENV_FLAG, "") == ENV_FLAG_TRUTHY


@dataclass(frozen=True)
class BridgeDecision:
    """Outcome of one bridge decision.

    ``allow`` is the host-facing verdict; ``verdict`` distinguishes the
    fail-open flavours (``allow`` / ``deny`` / ``error_allow``);
    ``audit`` carries the ledger record that was appended (empty on the
    R5 fast path, which writes nothing).
    """

    allow: bool
    verdict: str
    reason: str
    audit: dict[str, Any] = field(default_factory=dict)


def _discover_active_changes(repo_root: Path) -> list[tuple[str, Path, list[str]]]:
    """Return ``(change_id, folder, owned_files)`` for every active change.

    Mirrors ``lifecycle/runtime_wiring._resolve_manifest`` but across
    ALL active changes (the bridge cannot know which change the host
    agent belongs to, so S-8 is evaluated against the union). Lazy
    import keeps the active-folder layout SSOT on
    :mod:`devolaflow.agent_workspace.change` (A-5).
    """
    from devolaflow.agent_workspace.change import ACTIVE_DIR_DEFAULT

    active_root = repo_root / ACTIVE_DIR_DEFAULT
    if not active_root.is_dir():
        return []
    changes: list[tuple[str, Path, list[str]]] = []
    for folder in sorted(active_root.iterdir()):
        manifest = folder / "owned_files.txt"
        if not (folder.is_dir() and manifest.is_file()):
            continue
        lines = manifest.read_text(encoding="utf-8").splitlines()
        owned = [line.strip() for line in lines if line.strip()]
        changes.append((folder.name, folder, owned))
    return changes


def _is_s8_exempt(target: str, change_folders: list[Path], repo_root: Path) -> bool:
    """S-8 §2/§3 directory exemptions, same shape as ``runtime_wiring``.

    §2: paths inside ANY active change folder itself. §3: paths inside
    ``.local/.agent/handoff/``. Reuses ``runtime_wiring._is_under`` so
    the containment semantics can never drift between the framework
    adapter and the host bridge.
    """
    from devolaflow.agent_workspace.handoff import HANDOFF_DIR_DEFAULT
    from devolaflow.lifecycle.runtime_wiring import _is_under

    for folder in change_folders:
        if _is_under(target, folder):
            return True
    return _is_under(target, repo_root / HANDOFF_DIR_DEFAULT)


def _repo_relative(path: str, repo_root: Path) -> str:
    """Best-effort repo-relative form of *path* for owned-set matching.

    Host payloads may carry absolute paths while ``owned_files.txt``
    entries are repo-relative (S-2). Paths outside the repo are
    returned unchanged — they will not match the owned set and are
    denied per S-8 ("outside the union").
    """
    candidate = Path(path)
    if not candidate.is_absolute():
        return path
    try:
        return candidate.resolve().relative_to(repo_root.resolve()).as_posix()
    except (ValueError, OSError):
        return path


def _decide_file_write(
    event: BridgeEvent,
    repo_root: Path,
    record_extra: dict[str, Any],
) -> tuple[str, str]:
    from devolaflow.lifecycle import run_hooks

    changes = _discover_active_changes(repo_root)
    if not changes:
        return VERDICT_ALLOW, "no active change folder — ownership enforcement not in scope"

    change_ids = [change_id for change_id, _, _ in changes]
    change_folders = [folder for _, folder, _ in changes]
    owned_union: list[str] = []
    for _, _, owned in changes:
        owned_union.extend(owned)
    record_extra["active_changes"] = change_ids

    for raw_path in event.all_paths:
        rel_path = _repo_relative(raw_path, repo_root)
        allowed = list(owned_union)
        if _is_s8_exempt(str(repo_root / rel_path), change_folders, repo_root):
            allowed.append(rel_path)
        result = run_hooks("file_write", {"path": rel_path, "owned_files": allowed}, strict=False)
        breach = any(
            v.code == _CFO_OWNERSHIP_BREACH and v.severity == "blocker" for v in result.violations
        )
        if breach:
            reason = (
                f"S-8 ownership breach: write to '{rel_path}' is outside the "
                f"owned_files union of active change(s) "
                f"{', '.join(repr(c) for c in change_ids)} (CFO006)"
            )
            return VERDICT_DENY, reason
        if result.violations:
            # Shape-level violations (CFO001..CFO005) cannot arise from
            # this adapter's payload; if they ever do, fail-open loudly.
            record_extra["hook_violations"] = [str(v) for v in result.violations]

    return VERDICT_ALLOW, "all write targets inside owned_files union / S-8 exemptions"


def _decide_shell(
    event: BridgeEvent,
    record_extra: dict[str, Any],
) -> tuple[str, str]:
    """Shell events are ALWAYS allowed; pre_shell_call is advisory only.

    S-1 shell denial would require dispatch-layer role evidence the
    host event does not carry — this round records rewrite metadata for
    the audit ledger and nothing more (design §D-R2-1 step 3).

    The handler is invoked DIRECTLY (the lifecycle package exports it
    with the uniform ``(payload, *, strict=False)`` signature for
    exactly this) because ``run_hooks`` aggregates violations but does
    not propagate per-handler ``metadata`` — and the rewrite metadata
    (``wrapped_cmd`` / ``proxy_enabled`` / ``was_rewritten``) is the
    entire point of this advisory call.
    """
    try:
        from devolaflow.lifecycle import pre_shell_call

        result = pre_shell_call({"cmd": event.command, "cwd": event.cwd}, strict=False)
        advisory = {
            key: result.metadata[key]
            for key in ("wrapped_cmd", "proxy_enabled", "was_rewritten")
            if key in result.metadata
        }
        if result.violations:
            advisory["violations"] = [str(v) for v in result.violations]
        record_extra["shell_advisory"] = advisory
    except Exception as exc:
        # S-5: swallow-and-log — the error lands in the audit ledger,
        # the shell call itself is never blocked by advisory failure.
        logger.warning("hostbridge pre_shell_call advisory failed", exc_info=True)
        record_extra["shell_advisory_error"] = repr(exc)
    return VERDICT_ALLOW, "shell events are advisory-only in v17 R2 — allowed"


def decide(event: BridgeEvent, repo_root: Path) -> BridgeDecision:
    """Decide one normalized host event. Never raises (fail-open)."""
    if not is_host_enforce_active():
        return BridgeDecision(
            allow=True,
            verdict=VERDICT_ALLOW,
            reason=f"{ENV_FLAG} is not '1' — host enforcement disabled",
        )

    started = time.perf_counter()
    record_extra: dict[str, Any] = {}
    try:
        if event.kind == KIND_FILE_WRITE:
            verdict, reason = _decide_file_write(event, repo_root, record_extra)
        elif event.kind == KIND_SHELL:
            verdict, reason = _decide_shell(event, record_extra)
        else:
            verdict = VERDICT_ALLOW
            reason = f"unrecognised event kind {event.kind!r} — fail-open"
    except Exception as exc:
        logger.warning("hostbridge decision failed — failing open", exc_info=True)
        verdict = VERDICT_ERROR_ALLOW
        reason = f"internal bridge error — fail-open: {exc!r}"
        record_extra["error"] = repr(exc)

    elapsed_ms = (time.perf_counter() - started) * 1000.0
    record = build_audit_record(
        host=event.host,
        kind=event.kind,
        path=event.path,
        command=event.command,
        verdict=verdict,
        reason=reason,
        elapsed_ms=elapsed_ms,
        extra=record_extra,
    )
    append_audit(repo_root, record)
    return BridgeDecision(
        allow=verdict != VERDICT_DENY,
        verdict=verdict,
        reason=reason,
        audit=record,
    )


__all__ = [
    "ENV_FLAG",
    "ENV_FLAG_TRUTHY",
    "VERDICT_ALLOW",
    "VERDICT_DENY",
    "VERDICT_ERROR_ALLOW",
    "BridgeDecision",
    "decide",
    "is_host_enforce_active",
]
