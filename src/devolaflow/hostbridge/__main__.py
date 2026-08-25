"""CLI entry — ``python -m devolaflow.hostbridge --host <host>``.

Reads ONE JSON object from stdin (the host's pre-tool-use payload),
normalizes it, decides, and responds using the host's block protocol:

* ``cursor`` — stdout JSON: allow → ``{"permission": "allow"}``;
  deny → ``{"permission": "deny", "agent_message": "<reason>"}``.
  Always exit 0 (Cursor consumes the JSON, not the exit code).
* ``claude`` / ``codex`` / ``kimi`` / ``dsh`` — allow → silent exit 0;
  deny → reason on stderr + exit 2.

``python -m devolaflow.hostbridge install <host>`` delegates to
:mod:`devolaflow.hostbridge.install`.

Fail-open guarantee (design §D-R2-1): NO exception escapes this module.
Unparseable argv/stdin, or any internal error, degrades to the host's
allow response with exit 0.
"""

from __future__ import annotations

import argparse
import json
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


def _respond(host: str, decision: BridgeDecision) -> int:
    if host == "cursor":
        if decision.allow:
            print(_CURSOR_ALLOW_JSON)
        else:
            print(json.dumps({"permission": "deny", "agent_message": decision.reason}))
        return 0
    if decision.allow:
        return 0
    print(decision.reason, file=sys.stderr)
    return 2


def _allow_fallback(host: str | None) -> int:
    """Universal allow for degraded paths (bad argv, internal error)."""
    if host == "cursor":
        print(_CURSOR_ALLOW_JSON)
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:]) if argv is None else list(argv)

    if argv and argv[0] == "install":
        from devolaflow.hostbridge.install import main as install_main

        return install_main(argv[1:])

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
    except SystemExit:
        # Bad argv MUST NOT block the host tool call: emit the most
        # conservative allow shape (harmless stdout for exit-code hosts).
        return _allow_fallback("cursor")

    try:
        try:
            data = json.loads(sys.stdin.read())
        except Exception:
            data = None  # normalize_event degrades this to kind="unknown"

        event = normalize_event(args.host, data, event_override=args.event)
        repo_root = args.repo_root if args.repo_root is not None else Path.cwd()
        decision = decide(event, repo_root)
        return _respond(args.host, decision)
    except Exception:
        return _allow_fallback(args.host)


if __name__ == "__main__":
    sys.exit(main())
