"""`devola-compact` command surface (v24.0.0).

Design ref: `.local/research/v24.0.0_design_adr.md` §6.

`plan` is always free and always report-only. `apply` requires the plan's
fingerprint, which an operator supplies only after reading the plan. An
unattended agent therefore plans, queues, and stops — it cannot relocate
anything on its own initiative.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from devolaflow.workspace_compact.bloat import (
    DEFAULT_THRESHOLD_TOKENS,
    scan_bloat,
    suggestion_text,
)
from devolaflow.workspace_compact.digest import audit_digest, set_agent_section
from devolaflow.workspace_compact.engine import (
    apply_plan,
    build_plan,
    digest_path,
    load_mappings,
    locate,
    restore,
    verify_integrity,
)
from devolaflow.workspace_compact.handoff_index import write_handoff_index
from devolaflow.workspace_compact.handoff_relocate import (
    apply_relocation,
    plan_relocation,
    verify_relocations,
)
from devolaflow.workspace_compact.models import CompactError, CompactPlan
from devolaflow.workspace_compact.telemetry import (
    DEFAULT_LEDGER,
    OUTCOME_BYPASSED,
    OUTCOME_PLANNED,
    append_event,
    build_event,
    summarize,
)
from devolaflow.workspace_ledger import LedgerError

COMPACT_OK = 0
COMPACT_MALFORMED = 2
COMPACT_REFUSED = 3

_SCHEMA_VERSION = 1

INSTALL_HINT = (
    "uv tool install --force --python 3.13 "
    "'devolaflow @ git+https://github.com/YoRHa-Agents/DevolaFlow.git'"
)


def _json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n"


def _plan_note(plan: CompactPlan) -> str:
    """Say what to do next, including when the answer is "do nothing"."""

    if not plan.movable:
        if not plan.candidates:
            return "nothing is eligible and no candidate remains; this folder is already lean"
        heaviest = plan.candidates[0]
        return (
            "no entry is automatically eligible. The heaviest retained file is "
            f"`{heaviest.source}` ({heaviest.tokens_estimated} tokens); name it with "
            "`--include <path>` to plan its relocation. See `candidates` below."
        )
    if not plan.pays_for_itself:
        return (
            f"report-only. This plan relocates {plan.movable_tokens} tokens but the digest "
            f"it writes costs {plan.digest_tokens}, a net of {plan.net_tokens}. Compacting "
            "would make this folder more expensive to read, not less."
        )
    return "report-only; apply requires --approve <fingerprint>"


def _plan_payload(plan: CompactPlan) -> dict[str, Any]:
    return {
        "artifact_type": "compact-plan",
        "schema_version": _SCHEMA_VERSION,
        "folder": plan.folder,
        "fingerprint": plan.fingerprint,
        "retained_tokens": plan.retained_tokens,
        "movable_tokens": plan.movable_tokens,
        "digest_tokens": plan.digest_tokens,
        "net_tokens": plan.net_tokens,
        "pays_for_itself": plan.pays_for_itself,
        "projected_reduction": round(plan.projected_reduction, 4),
        "findings": list(plan.findings),
        "entries": [
            {
                "source": entry.source,
                "destination": entry.destination,
                "category": entry.category.value,
                "action": entry.action.value,
                "reason": entry.reason,
                "bytes": entry.bytes,
                "tokens_estimated": entry.tokens_estimated,
                "sha256": entry.sha256,
            }
            for entry in plan.entries
            if entry.action.value == "move"
        ],
        "candidates": [
            {
                "source": entry.source,
                "tokens_estimated": entry.tokens_estimated,
                "summary": entry.summary,
            }
            for entry in plan.candidates[:10]
        ],
        "retained_count": sum(1 for entry in plan.entries if entry.action.value == "retain"),
        "note": _plan_note(plan),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="devola-compact",
        description=(
            "Non-destructive compaction of one task or change folder: relocate "
            "settled content into an in-folder archive, record a hashed mapping, "
            "and leave a generated digest in its place."
        ),
    )
    # `--folder` is accepted on both sides of the subcommand. Registering it
    # only ahead of the subparsers made `devola-compact plan --folder X` fail
    # with "unrecognized arguments" — which is the order this tool's own
    # suggestion text printed (v24.1.0 friction finding).
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--folder", type=Path, default=None, dest="folder_after")
    common.add_argument("--telemetry", type=Path, default=None, dest="telemetry_after")

    parser.add_argument(
        "--folder", type=Path, default=None, help="task or change folder to compact"
    )
    parser.add_argument(
        "--telemetry",
        type=Path,
        default=None,
        help=f"compaction telemetry ledger to append to (conventionally {DEFAULT_LEDGER})",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser(
        "probe",
        parents=[common],
        help="report that the runtime and write path are available",
    )
    sub.add_parser("telemetry", parents=[common], help="summarise the compaction telemetry ledger")

    plan = sub.add_parser(
        "plan", parents=[common], help="classify the folder and report what would move"
    )
    plan.add_argument(
        "--include",
        action="append",
        default=[],
        help="relocate this path too (repeatable); the channel for hand-written artifacts",
    )

    apply_parser = sub.add_parser("apply", parents=[common], help="relocate an approved plan")
    apply_parser.add_argument("--approve", required=True, help="fingerprint of the read plan")
    apply_parser.add_argument("--include", action="append", default=[])
    apply_parser.add_argument(
        "--only",
        action="append",
        default=None,
        help="restrict the move to these approved sources (repeatable)",
    )

    locate_parser = sub.add_parser("locate", parents=[common], help="search the archived originals")
    locate_parser.add_argument("--query", required=True)
    locate_parser.add_argument("--limit", type=int, default=20)

    restore_parser = sub.add_parser(
        "restore", parents=[common], help="copy one archived original back in place"
    )
    restore_parser.add_argument("--source", required=True)

    sub.add_parser(
        "verify",
        parents=[common],
        help="re-hash every archived original; non-zero on mismatch",
    )
    sub.add_parser(
        "audit", parents=[common], help="report digest drift and broken narration anchors"
    )

    summary = sub.add_parser(
        "summarize", parents=[common], help="replace the digest's agent narration"
    )
    summary.add_argument(
        "--text", required=True, help="narration; every bullet needs a [[path#Lnn]] anchor"
    )

    scan = sub.add_parser(
        "scan",
        parents=[common],
        help="report folders an agent can no longer read in one pass",
    )
    scan.add_argument("--repo-root", type=Path, default=Path.cwd())
    scan.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD_TOKENS)

    handoff = sub.add_parser(
        "handoff-index",
        parents=[common],
        help="render a generated index of handoff envelopes",
    )
    handoff.add_argument("--repo-root", type=Path, default=Path.cwd())
    handoff.add_argument("--change-id", default=None)

    relocate = sub.add_parser(
        "handoff-relocate",
        parents=[common],
        help="relocate archived-change handoff envelopes under S-9.1",
    )
    relocate.add_argument("--repo-root", type=Path, default=Path.cwd())
    relocate.add_argument("--change-id", default=None)
    relocate.add_argument(
        "--approve",
        default=None,
        help="plan fingerprint authorising the move; omit for a report-only plan",
    )

    handoff_verify = sub.add_parser(
        "handoff-verify",
        parents=[common],
        help="re-hash every relocated envelope; non-zero on mismatch",
    )
    handoff_verify.add_argument("--repo-root", type=Path, default=Path.cwd())

    return parser


def _resolve_shared_options(args: argparse.Namespace) -> None:
    """Fold the post-subcommand aliases of `--folder`/`--telemetry` back in."""

    args.folder = getattr(args, "folder_after", None) or args.folder or Path.cwd()
    args.telemetry = getattr(args, "telemetry_after", None) or args.telemetry


def _dispatch(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    command = args.command
    folder = args.folder

    if command == "probe":
        return {
            "artifact_type": "compact-probe",
            "schema_version": _SCHEMA_VERSION,
            "runtime_available": True,
            "write_available": True,
            "install_hint": INSTALL_HINT,
        }, COMPACT_OK

    if command == "telemetry":
        return {
            "artifact_type": "compact-telemetry",
            "schema_version": _SCHEMA_VERSION,
            "ledger": str(args.telemetry or DEFAULT_LEDGER),
            **summarize(args.telemetry or DEFAULT_LEDGER),
        }, COMPACT_OK

    if command == "plan":
        plan = build_plan(folder, include=args.include)
        if args.telemetry:
            # Three outcomes, all recorded. `bypassed` was dead vocabulary in
            # v24 — declared but never written — which meant the ledger could
            # not distinguish "no plan was made" from "a plan was made and
            # declined itself", the two cases that decide whether compaction
            # is worth suggesting at all.
            if not plan.movable:
                outcome, reason = OUTCOME_BYPASSED, "nothing is automatically eligible"
            elif not plan.pays_for_itself:
                outcome, reason = (
                    OUTCOME_BYPASSED,
                    f"digest costs {plan.digest_tokens} against {plan.movable_tokens} relocated",
                )
            else:
                outcome, reason = OUTCOME_PLANNED, "awaiting operator consent"
            append_event(
                args.telemetry,
                build_event(
                    str(folder),
                    outcome,
                    tokens_before=plan.retained_tokens + plan.movable_tokens,
                    tokens_after=plan.retained_tokens,
                    entries=len(plan.movable),
                    reason=reason,
                ),
            )
        return _plan_payload(plan), COMPACT_OK

    if command == "apply":
        plan = build_plan(folder, include=args.include)
        result = apply_plan(
            folder,
            plan,
            approval_fingerprint=args.approve,
            sources=args.only,
            telemetry_ledger=args.telemetry,
        )
        payload = {
            "artifact_type": "compact-result",
            "schema_version": _SCHEMA_VERSION,
            "folder": str(folder),
            "applied": [
                {"source": entry.source, "destination": entry.destination}
                for entry in result.applied
            ],
            "findings": list(result.findings),
            "refused": result.refused,
            "tokens_before": result.tokens_before,
            "tokens_after": result.tokens_after,
            "reduction": round(result.reduction, 4),
            "digest": result.digest_path,
            "success": result.success,
            "digest_findings": list(result.digest_findings),
            "digest_current": result.digest_current,
        }
        return payload, COMPACT_OK if result.success else COMPACT_REFUSED

    if command == "locate":
        hits = locate(folder, args.query, limit=args.limit)
        return {
            "artifact_type": "compact-locate",
            "schema_version": _SCHEMA_VERSION,
            "query": args.query,
            "hits": [
                {
                    "archived_path": hit.archived_path,
                    "original_source": hit.original_source,
                    "line": hit.line,
                    "excerpt": hit.excerpt,
                }
                for hit in hits
            ],
            "count": len(hits),
        }, COMPACT_OK

    if command == "restore":
        target = restore(folder, args.source)
        return {
            "artifact_type": "compact-restore",
            "schema_version": _SCHEMA_VERSION,
            "restored": target.as_posix(),
            "note": "archived original is retained so its hash stays verifiable",
        }, COMPACT_OK

    if command == "verify":
        problems = verify_integrity(folder)
        return {
            "artifact_type": "compact-verify",
            "schema_version": _SCHEMA_VERSION,
            "mappings": len(load_mappings(Path(folder))),
            "problems": list(problems),
            "zero_loss": not problems,
        }, COMPACT_OK if not problems else COMPACT_REFUSED

    if command == "audit":
        findings = audit_digest(Path(folder))
        return {
            "artifact_type": "compact-audit",
            "schema_version": _SCHEMA_VERSION,
            "findings": [{"code": item.code, "message": item.message} for item in findings],
            "healthy": not findings,
        }, COMPACT_OK if not findings else COMPACT_REFUSED

    if command == "summarize":
        problems = set_agent_section(Path(folder), args.text)
        return {
            "artifact_type": "compact-summary",
            "schema_version": _SCHEMA_VERSION,
            "digest": digest_path(Path(folder)).as_posix(),
            "findings": list(problems),
            "accepted": not problems,
        }, COMPACT_OK if not problems else COMPACT_REFUSED

    if command == "scan":
        findings = scan_bloat(args.repo_root, threshold_tokens=args.threshold)
        return {
            "artifact_type": "compact-scan",
            "schema_version": _SCHEMA_VERSION,
            "threshold_tokens": args.threshold,
            "over_threshold": [
                {
                    "folder": item.folder,
                    "tokens": item.tokens,
                    "bytes": item.bytes,
                    "files": item.files,
                    "archived_tokens": item.archived_tokens,
                }
                for item in findings
            ],
            "suggestion": suggestion_text(findings, threshold=args.threshold),
        }, COMPACT_OK

    if command == "handoff-index":
        written, findings = write_handoff_index(args.repo_root, change_id=args.change_id)
        return {
            "artifact_type": "handoff-index",
            "schema_version": _SCHEMA_VERSION,
            "index": None if written is None else written.as_posix(),
            "findings": list(findings),
            "healthy": not findings,
        }, COMPACT_OK if not findings else COMPACT_REFUSED

    if command == "handoff-relocate":
        plan = plan_relocation(args.repo_root, change_id=args.change_id)
        payload = {
            "artifact_type": "handoff-relocation",
            "schema_version": _SCHEMA_VERSION,
            "fingerprint": plan.fingerprint,
            "archived_changes": list(plan.archived_changes),
            "candidates": [
                {
                    "source": item.source,
                    "destination": item.destination,
                    "change_id": item.change_id,
                    "seq": item.seq,
                    "bytes": item.bytes,
                    "sha256": item.sha256,
                }
                for item in plan.candidates
            ],
            "refused": list(plan.refused),
        }
        if args.approve is None:
            payload["applied"] = False
            payload["note"] = "report-only; re-run with --approve <fingerprint> to relocate"
            return payload, COMPACT_OK
        result = apply_relocation(args.repo_root, plan, approval_fingerprint=args.approve)
        payload["applied"] = True
        payload["moved"] = [item.source for item in result.moved]
        payload["findings"] = list(result.findings)
        payload["index"] = result.index_path
        payload["success"] = result.success
        return payload, COMPACT_OK if result.success else COMPACT_REFUSED

    if command == "handoff-verify":
        problems = verify_relocations(args.repo_root)
        return {
            "artifact_type": "handoff-verify",
            "schema_version": _SCHEMA_VERSION,
            "problems": list(problems),
            "zero_loss": not problems,
        }, COMPACT_OK if not problems else COMPACT_REFUSED

    raise CompactError(f"unknown command: {command}")


def main(argv: Sequence[str] | None = None) -> int:
    """Run one compaction command and print exactly one JSON object."""

    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else sys.argv[1:])
    _resolve_shared_options(args)
    try:
        payload, exit_code = _dispatch(args)
    except (CompactError, LedgerError) as exc:
        print(
            _json(
                {
                    "artifact_type": "compact-error",
                    "schema_version": _SCHEMA_VERSION,
                    "findings": [{"code": "COMPACT_REFUSED", "message": str(exc)}],
                    "healthy": False,
                }
            ),
            end="",
        )
        return COMPACT_MALFORMED
    print(_json(payload), end="")
    return exit_code


def compact_cmd() -> None:
    """Console-script entry point."""

    sys.exit(main())


__all__ = [
    "COMPACT_MALFORMED",
    "COMPACT_OK",
    "COMPACT_REFUSED",
    "INSTALL_HINT",
    "compact_cmd",
    "main",
]
