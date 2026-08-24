"""Pre-Shell-call lifecycle hook — RTK shell-proxy thin delegator (v8.3.2 PV-02).

Closes the lifecycle integration half of ``R-002`` from
``.local/research/v8.4.0_gap_analysis.md`` §2.1: when an L2 Task
Agent is about to dispatch a Shell-tool call, this hook gives the
:mod:`devolaflow.shell_proxy` package a chance to rewrite the command
through ``rtk <cmd>`` for token compression.

Mirrors the thin-delegator pattern of RTK's own Claude hook
(``hooks/claude/rtk-rewrite.sh``) per the historical analysis: this module
contains NO rewrite logic; it parses the payload, calls
:meth:`ShellProxy.wrap_command`, and stuffs the result into
``HookResult.metadata["wrapped_cmd"]`` so downstream consumers can
inspect both the original ``cmd`` and the wrapped form without
guessing which was used.

Permissive default — emits a WARNING via the lifecycle logger when
the payload schema is wrong AND, in strict mode, raises the
top-severity :class:`HookViolation`. The wrap itself is NEVER a
violation (passthrough is the safe default per R5 strict).

Contract (payload schema):

* ``cmd: str`` (required) — the Shell-tool command to dispatch
* ``cwd: str | None`` (optional) — the requested working directory;
  passed through opaque to the proxy (the proxy currently does not
  consult cwd; reserved for future per-cwd rewrites a la RTK's
  ``[filters.<name>]`` schema from the historical analysis)

Result:

* ``metadata["wrapped_cmd"]`` — the (possibly rewritten) command;
  equals the input ``cmd`` when the proxy is OFF or the command is
  not whitelisted, otherwise ``"rtk " + cmd`` for Tier 1 (or Tier 2
  when its opt-in flag is also set).
* ``metadata["proxy_enabled"]`` — whether the proxy was active at
  hook-fire time; useful for downstream diagnostics.
* ``metadata["was_rewritten"]`` — strict equality test (cheaper than
  comparing strings on every read).

R5 strict (per task spec): when ``DEVOLAFLOW_RTK_PROXY`` is unset
the hook is a near-no-op — it parses the payload, calls
:meth:`ShellProxy.wrap_command` (which fast-paths via
:func:`is_proxy_enabled` returning False), and returns the input
``cmd`` in ``metadata["wrapped_cmd"]``. NO subprocess work occurs.
"""

from __future__ import annotations

from typing import Any

from devolaflow.lifecycle.dispatcher import HookResult, HookViolation, finalize
from devolaflow.shell_proxy import ShellProxy

EVENT = "pre_shell_call"


def _collect_violations(payload: dict[str, Any]) -> list[HookViolation]:
    """Validate *payload* shape and return any schema violations.

    Returns an empty list on a well-formed payload. Mirrors the
    discipline of :mod:`devolaflow.lifecycle.check_file_ownership`
    so the strict-raise behavior is uniform across the lifecycle
    package.
    """
    if not isinstance(payload, dict):
        return [
            HookViolation(
                code="PSC001",
                message="pre_shell_call payload is not a mapping",
                severity="error",
                context={"payload_type": type(payload).__name__},
            )
        ]

    cmd = payload.get("cmd")
    if cmd is None:
        return [
            HookViolation(
                code="PSC002",
                message="pre_shell_call payload missing required field: 'cmd'",
                severity="error",
                context={"keys_present": sorted(payload.keys())},
            )
        ]

    if not isinstance(cmd, str):
        return [
            HookViolation(
                code="PSC003",
                message="'cmd' must be a string",
                severity="error",
                context={"cmd_type": type(cmd).__name__},
            )
        ]

    cwd = payload.get("cwd")
    if cwd is not None and not isinstance(cwd, str):
        return [
            HookViolation(
                code="PSC004",
                message="'cwd' must be a string when present",
                severity="error",
                context={"cwd_type": type(cwd).__name__},
            )
        ]

    return []


def pre_shell_call(
    payload: dict[str, Any],
    *,
    strict: bool = False,
) -> HookResult:
    """Rewrite *payload['cmd']* through the RTK shell-proxy.

    Permissive default — schema violations log a WARNING via the
    lifecycle logger and return a populated :class:`HookResult`.
    Strict mode re-raises the top-severity :class:`HookViolation`
    (always ``error`` for shape problems; the wrap itself never
    produces a violation).

    On a well-formed payload, the returned result has ``passed=True``
    and the wrapped command in ``metadata["wrapped_cmd"]``. The
    original ``cmd`` is unchanged in the input dict (the hook is
    pure / non-mutating).
    """
    violations = _collect_violations(payload)
    if violations:
        return finalize(EVENT, violations, strict=strict)

    proxy = ShellProxy()
    cmd: str = payload["cmd"]
    wrapped: str = proxy.wrap_command(cmd)

    result = HookResult(event=EVENT, passed=True, violations=[])
    result.metadata["wrapped_cmd"] = wrapped
    result.metadata["proxy_enabled"] = proxy.config.proxy_enabled
    result.metadata["was_rewritten"] = wrapped != cmd
    if proxy.config.warnings:
        result.metadata["proxy_warnings"] = list(proxy.config.warnings)

    return result


__all__ = ["EVENT", "pre_shell_call"]
