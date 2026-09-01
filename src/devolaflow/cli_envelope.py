"""One JSON object on stdout, including when the invocation was wrong (v24.3.0).

`devola-compact` and `devola-parking` both document a single JSON object on
stdout as their whole output contract, and both broke it in the same place:
argparse writes usage prose to stderr and exits 2 on its own, so a caller that
parses stdout receives nothing at all and has to fall back to reading prose it
was promised it would never have to read.

Exit 2 was also shared with a domain refusal, which made a mistyped flag and a
legitimate "no, that is not allowed" indistinguishable by exit code. The fix
keeps every exit code exactly as it was — callers already branch on them — and
puts the distinction in the payload as ``error_kind``, so the two cases are
told apart by reading the object the tool always promised to print.

This module is the single owner of that behaviour for both CLIs per A-5.
"""

from __future__ import annotations

import argparse
from typing import Any, Final

#: A malformed invocation: argparse rejected the arguments.
KIND_USAGE: Final[str] = "usage"

#: A well-formed invocation the domain declined to carry out.
KIND_DOMAIN: Final[str] = "domain"


class UsageError(Exception):
    """Raised in place of argparse's own stderr-and-exit behaviour."""

    def __init__(self, message: str, usage: str) -> None:
        super().__init__(message)
        self.usage = usage


class JsonUsageParser(argparse.ArgumentParser):
    """An ``ArgumentParser`` that reports usage failures to its caller.

    ``--help`` is deliberately left alone: it is an explicit request for prose
    by a human, and rendering help text as a JSON string would make it worse to
    read while helping no machine caller.
    """

    def error(self, message: str) -> None:  # type: ignore[override]
        raise UsageError(message, self.format_usage())


def usage_envelope(artifact_type: str, exc: UsageError, *, schema_version: int) -> dict[str, Any]:
    """Build the stdout envelope for a rejected invocation."""

    return {
        "artifact_type": artifact_type,
        "schema_version": schema_version,
        "error_kind": KIND_USAGE,
        "findings": [{"code": "USAGE_REJECTED", "message": str(exc)}],
        "usage": exc.usage.strip(),
        "healthy": False,
    }


def domain_envelope(
    artifact_type: str, code: str, message: str, *, schema_version: int
) -> dict[str, Any]:
    """Build the stdout envelope for a refusal the domain decided on."""

    return {
        "artifact_type": artifact_type,
        "schema_version": schema_version,
        "error_kind": KIND_DOMAIN,
        "findings": [{"code": code, "message": message}],
        "healthy": False,
    }


__all__ = [
    "KIND_DOMAIN",
    "KIND_USAGE",
    "JsonUsageParser",
    "UsageError",
    "domain_envelope",
    "usage_envelope",
]
