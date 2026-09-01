"""`devola-parking` command surface (v24.0.0).

Design ref: `.local/research/v24.0.0_design_adr.md` §5, §7.

This is the only supported way to write a parking surface. Agents call it;
operators speak their decisions in chat and the agent records them here. Every
subcommand prints one JSON object so a caller never has to parse prose.

The runtime is a hard prerequisite by design (gap analysis F-09): if this
command is unavailable the correct agent behaviour is to report that writes
are impossible and print the install command, never to hand-write the files
that this tool owns.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from devolaflow.parking.adopt import apply_adoption, plan_adoption
from devolaflow.parking.models import ParkingError, RiskState, Severity
from devolaflow.parking.store import ParkingStore
from devolaflow.workspace_ledger import Finding, LedgerError

PARKING_OK = 0
PARKING_MALFORMED = 2
PARKING_REFUSED = 3

_SCHEMA_VERSION = 1

INSTALL_HINT = (
    "uv tool install --force --python 3.13 "
    "'devolaflow @ git+https://github.com/YoRHa-Agents/DevolaFlow.git'"
)


def _json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n"


def _findings(items: Sequence[Finding]) -> list[dict[str, str]]:
    return [{"code": item.code, "message": item.message} for item in items]


def _risk_payload(store: ParkingStore, risk_id: str) -> dict[str, Any]:
    risk = store.load_risk(risk_id)
    return {
        "id": risk.id,
        "title": risk.title,
        "state": risk.state.value,
        "severity": risk.severity.value,
        "trigger": risk.trigger,
        "disposition": risk.disposition,
        "judgment_refs": list(risk.judgment_refs),
        "legacy_id": risk.legacy_id,
        "path": store.risk_path(risk.id).as_posix(),
    }


def _status_payload(store: ParkingStore) -> dict[str, Any]:
    snapshot = store.snapshot()
    drift = store.audit()
    return {
        "artifact_type": "parking-status",
        "schema_version": _SCHEMA_VERSION,
        "folder": store.folder.as_posix(),
        "exists": store.exists,
        "counts": {
            "risks": len(snapshot.risks),
            "live": sum(1 for risk in snapshot.risks if risk.live),
            "pending_decisions": len(snapshot.pending),
            "settled_decisions": len(snapshot.settled),
            "events": len(snapshot.events),
        },
        "live_risks": [
            {
                "id": risk.id,
                "severity": risk.severity.value,
                "state": risk.state.value,
                "title": risk.title,
            }
            for risk in snapshot.risks
            if risk.live
        ],
        "pending_decisions": [
            {"id": row.id, "subject": row.subject, "question": row.question}
            for row in snapshot.pending
        ],
        "findings": _findings(drift),
        "healthy": not drift,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="devola-parking",
        description=(
            "Single write entry point for risk parking, the judgment ledger, "
            "and the event ledger inside one task or change folder."
        ),
    )
    # `--folder` is accepted on both sides of the subcommand: registering it
    # only ahead of the subparsers made the natural `devola-parking status
    # --folder X` fail with "unrecognized arguments" (v24.1.0 friction finding).
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--folder", type=Path, default=None, dest="folder_after")

    parser.add_argument(
        "--folder",
        type=Path,
        default=None,
        help="task or change folder that owns the parking surface",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser(
        "probe",
        parents=[common],
        help="report that the runtime and write path are available",
    )
    sub.add_parser("scaffold", parents=[common], help="create the parking surface (idempotent)")
    sub.add_parser(
        "status", parents=[common], help="report risks, pending decisions, and view drift"
    )
    sub.add_parser(
        "audit",
        parents=[common],
        help="report generated-view drift only; non-zero on drift",
    )

    opened = sub.add_parser("open", parents=[common], help="register a new risk")
    opened.add_argument("--title", required=True)
    opened.add_argument(
        "--severity", choices=[item.value for item in Severity], default=Severity.MAJOR.value
    )
    opened.add_argument("--trigger", default="")
    opened.add_argument("--disposition", default="")
    opened.add_argument("--body", default="")
    opened.add_argument("--legacy-id", default=None)

    transition = sub.add_parser(
        "transition", parents=[common], help="move a risk to another lifecycle state"
    )
    transition.add_argument("--risk", required=True)
    transition.add_argument("--to", required=True, choices=[item.value for item in RiskState])
    transition.add_argument("--reason", required=True)

    update = sub.add_parser(
        "update", parents=[common], help="append a dated history note to a risk"
    )
    update.add_argument("--risk", required=True)
    update.add_argument("--note", required=True)
    update.add_argument("--disposition", default=None)
    update.add_argument("--trigger", default=None)

    ask = sub.add_parser("ask", parents=[common], help="queue a decision without blocking the risk")
    ask.add_argument("--subject", required=True)
    ask.add_argument("--question", required=True)

    decide = sub.add_parser(
        "decide", parents=[common], help="record an operator decision (append-only)"
    )
    decide.add_argument("--question-id", default=None, help="answer a queued question")
    decide.add_argument("--subject", default=None, help="subject for a standalone decision")
    decide.add_argument("--question", default=None, help="question text for a standalone decision")
    decide.add_argument("--decision", required=True)

    adopt = sub.add_parser(
        "adopt", parents=[common], help="preview or apply adoption of a legacy document"
    )
    adopt.add_argument("--source", type=Path, required=True)
    adopt.add_argument("--approve", default=None, help="plan fingerprint authorising the write")

    return parser


def _resolve_shared_options(args: argparse.Namespace) -> None:
    """Fold the post-subcommand alias of `--folder` back into `args.folder`."""

    args.folder = getattr(args, "folder_after", None) or args.folder or Path.cwd()


def _dispatch(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    store = ParkingStore(args.folder)
    command = args.command

    if command == "probe":
        return {
            "artifact_type": "parking-probe",
            "schema_version": _SCHEMA_VERSION,
            "runtime_available": True,
            "write_available": True,
            "install_hint": INSTALL_HINT,
        }, PARKING_OK

    if command == "scaffold":
        created = store.scaffold()
        return {
            "artifact_type": "parking-scaffold",
            "schema_version": _SCHEMA_VERSION,
            "created": [path.as_posix() for path in created],
        }, PARKING_OK

    if command == "status":
        payload = _status_payload(store)
        return payload, PARKING_OK if payload["healthy"] else PARKING_REFUSED

    if command == "audit":
        drift = store.audit()
        return {
            "artifact_type": "parking-audit",
            "schema_version": _SCHEMA_VERSION,
            "findings": _findings(drift),
            "healthy": not drift,
        }, PARKING_OK if not drift else PARKING_REFUSED

    if command == "open":
        risk = store.open_risk(
            args.title,
            severity=args.severity,
            trigger=args.trigger,
            disposition=args.disposition,
            body=args.body,
            legacy_id=args.legacy_id,
        )
        return {
            "artifact_type": "parking-risk",
            "schema_version": _SCHEMA_VERSION,
            "risk": _risk_payload(store, risk.id),
        }, PARKING_OK

    if command == "transition":
        risk = store.transition_risk(args.risk, args.to, reason=args.reason)
        return {
            "artifact_type": "parking-risk",
            "schema_version": _SCHEMA_VERSION,
            "risk": _risk_payload(store, risk.id),
        }, PARKING_OK

    if command == "update":
        risk = store.update_risk(
            args.risk,
            note=args.note,
            disposition=args.disposition,
            trigger=args.trigger,
        )
        return {
            "artifact_type": "parking-risk",
            "schema_version": _SCHEMA_VERSION,
            "risk": _risk_payload(store, risk.id),
        }, PARKING_OK

    if command == "ask":
        judgment = store.raise_question(args.question, subject=args.subject)
        return {
            "artifact_type": "parking-question",
            "schema_version": _SCHEMA_VERSION,
            "judgment": {
                "id": judgment.id,
                "subject": judgment.subject,
                "question": judgment.question,
                "pending": True,
            },
        }, PARKING_OK

    if command == "decide":
        judgment = store.record_decision(
            args.decision,
            question_id=args.question_id,
            subject=args.subject,
            question=args.question,
        )
        return {
            "artifact_type": "parking-decision",
            "schema_version": _SCHEMA_VERSION,
            "judgment": {
                "id": judgment.id,
                "subject": judgment.subject,
                "question": judgment.question,
                "decision": judgment.decision,
                "supersedes": judgment.supersedes,
            },
        }, PARKING_OK

    if command == "adopt":
        plan = plan_adoption(args.source)
        payload: dict[str, Any] = {
            "artifact_type": "parking-adoption",
            "schema_version": _SCHEMA_VERSION,
            "source": plan.source,
            "source_sha256": plan.source_sha256,
            "source_lines": plan.source_lines,
            "preamble_lines": plan.preamble_lines,
            "unmapped_lines": plan.unmapped_lines,
            "fingerprint": plan.fingerprint,
            "candidates": [
                {
                    "legacy_id": item.legacy_id,
                    "state": item.state.value,
                    "severity": item.severity.value,
                    "title": item.title,
                    "section": item.section,
                    "source_line": item.source_line,
                }
                for item in plan.candidates
            ],
        }
        if args.approve is None:
            payload["applied"] = False
            payload["note"] = "report-only; re-run with --approve <fingerprint> to write"
            return payload, PARKING_OK
        created = apply_adoption(args.folder, plan, approval_fingerprint=args.approve)
        payload["applied"] = True
        payload["created"] = list(created)
        return payload, PARKING_OK

    raise ParkingError(f"unknown command: {command}")


def main(argv: Sequence[str] | None = None) -> int:
    """Run one parking command and print exactly one JSON object."""

    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else sys.argv[1:])
    _resolve_shared_options(args)
    try:
        payload, exit_code = _dispatch(args)
    except (ParkingError, LedgerError) as exc:
        print(
            _json(
                {
                    "artifact_type": "parking-error",
                    "schema_version": _SCHEMA_VERSION,
                    "findings": [{"code": "PARKING_REFUSED", "message": str(exc)}],
                    "healthy": False,
                }
            ),
            end="",
        )
        return PARKING_MALFORMED
    print(_json(payload), end="")
    return exit_code


def parking_cmd() -> None:
    """Console-script entry point."""

    sys.exit(main())


__all__ = [
    "INSTALL_HINT",
    "PARKING_MALFORMED",
    "PARKING_OK",
    "PARKING_REFUSED",
    "main",
    "parking_cmd",
]
