"""CLI entry — ``python -m devolaflow.hostbridge --host <host>``.

Reads ONE JSON object from stdin (the host's pre-tool-use payload),
normalizes it, decides, and responds using the host's block protocol:

* ``cursor`` — stdout JSON: allow → ``{"permission": "allow"}``;
  deny → ``{"permission": "deny", "agent_message": "<reason>"}``.
  Always exit 0 (Cursor consumes the JSON, not the exit code).
* ``claude`` / ``codex`` / ``kimi`` / ``dsh`` — allow → silent exit 0;
  deny → reason on stderr + exit 2.
* ``copilot`` — stdout JSON with ``permissionDecision`` and
  ``permissionDecisionReason``; always exit 0.

``python -m devolaflow.hostbridge install <host>`` delegates to
:mod:`devolaflow.hostbridge.install`. ``python -m devolaflow.hostbridge
resume [--host cursor|claude]`` delegates to
:mod:`devolaflow.hostbridge.session` (v17 R4 session-start resume
summary; gated on ``DEVOLAFLOW_AGENT_WORKSPACE=1``, always exit 0).

Fail-open guarantee (design §D-R2-1): NO exception escapes this module.
Unparseable argv/stdin, or any internal error, degrades to the host's
allow response with exit 0.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from devolaflow.hostbridge.decision import BridgeDecision, decide
from devolaflow.hostbridge.normalize import (
    KIND_FILE_WRITE,
    KIND_SHELL,
    KNOWN_HOSTS,
    normalize_event,
)

_CURSOR_ALLOW_JSON = '{"permission": "allow"}'
_COPILOT_ALLOW_JSON = '{"permissionDecision": "allow"}'
logger = logging.getLogger(__name__)


def _respond(host: str, decision: BridgeDecision) -> int:
    if host == "cursor":
        if decision.allow:
            print(_CURSOR_ALLOW_JSON)
        else:
            print(json.dumps({"permission": "deny", "agent_message": decision.reason}))
        return 0
    if host == "copilot":
        if decision.allow:
            print(_COPILOT_ALLOW_JSON)
        else:
            print(
                json.dumps(
                    {
                        "permissionDecision": "deny",
                        "permissionDecisionReason": decision.reason,
                    }
                )
            )
        return 0
    if decision.allow:
        return 0
    print(decision.reason, file=sys.stderr)
    return 2


def _allow_fallback(host: str | None) -> int:
    """Universal allow for degraded paths (bad argv, internal error)."""
    if host == "cursor":
        print(_CURSOR_ALLOW_JSON)
    elif host == "copilot":
        print(_COPILOT_ALLOW_JSON)
    return 0


def _host_hint(argv: list[str]) -> str:
    """Recover a response protocol when argument parsing itself fails."""
    candidate = "cursor"
    for index, value in enumerate(argv):
        if value == "--host" and index + 1 < len(argv):
            candidate = argv[index + 1]
            break
        if value.startswith("--host="):
            candidate = value.partition("=")[2]
            break
    return "copilot" if candidate == "copilot" else "cursor"


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:]) if argv is None else list(argv)

    if argv and argv[0] == "install":
        from devolaflow.hostbridge.install import main as install_main

        return install_main(argv[1:])

    if argv and argv[0] == "resume":
        from devolaflow.hostbridge.session import main as session_main

        return session_main(argv[1:])

    parser = argparse.ArgumentParser(
        prog="python -m devolaflow.hostbridge",
        description="DevolaFlow host-bridge: stdin tool event -> boundary verdict.",
    )
    parser.add_argument("--host", required=True, choices=KNOWN_HOSTS)
    parser.add_argument("--event", choices=(KIND_FILE_WRITE, KIND_SHELL), default=None)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="repo root for enforcement lookups (default: current directory)",
    )

    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        # Bad argv MUST NOT block the host tool call: emit the most
        # conservative allow shape (harmless stdout for exit-code hosts).
        logger.warning(
            "hostbridge argument parsing failed (exit=%r); allowing host tool call via fallback",
            exc.code,
            exc_info=True,
        )
        return _allow_fallback(_host_hint(argv))

    try:
        try:
            data = json.loads(sys.stdin.read())
        except json.JSONDecodeError:
            logger.warning(
                "hostbridge received malformed stdin; normalizing to unknown event",
                exc_info=True,
            )
            data = None  # normalize_event degrades this to kind="unknown"
        except Exception:
            logger.warning(
                "hostbridge stdin parsing failed unexpectedly; normalizing to unknown event",
                exc_info=True,
            )
            data = None  # normalize_event degrades this to kind="unknown"

        event = normalize_event(args.host, data, event_override=args.event)
        repo_root = args.repo_root if args.repo_root is not None else Path.cwd()
        decision = decide(event, repo_root)
        return _respond(args.host, decision)
    except Exception as exc:
        logger.warning(
            "hostbridge internal error for host %r; allowing via fail-open fallback: %s",
            args.host,
            exc,
            exc_info=True,
        )
        return _allow_fallback(args.host)


if __name__ == "__main__":
    sys.exit(main())
