"""RTK shell-proxy wrapper (v8.3.2 PV-02 — closes R-002).

Closes ``R-002`` from ``.local/research/v8.4.0_gap_analysis.md`` §2.1:
when the env-flag ``DEVOLAFLOW_RTK_PROXY=1`` is set AND the ``rtk``
binary is on PATH AND ``rtk gain`` succeeds AND the command matches
:mod:`devolaflow.shell_proxy.registry`'s whitelist, transparently
rewrites the Shell-tool call as ``rtk <cmd>`` for the documented
~80% token-compression layer per ``.local/research/v8.4.0_rtk_nines_analysis.md``
§6 (whitelist table cites RTK README's stated savings per command).

R5 strict (per task spec): default OFF means ``wrap_command`` is a
zero-overhead identity passthrough — when ``DEVOLAFLOW_RTK_PROXY``
is unset OR set to ``"0"``, the function returns the input string
unchanged WITHOUT spawning any subprocess (no ``shutil.which``, no
``rtk gain`` probe). All v8.3.1 baseline tests pass byte-identical
when the flag is unset.

Loud failures (S-5): if the env-flag IS set but ``rtk`` is missing OR
``rtk gain`` returns a non-zero exit code (the latter is the rtk-type-kit
collision case per RTK ``INSTALL.md``), the proxy logs a WARNING with
actionable text AND gracefully passthroughs — it does NOT raise. The
caller (the lifecycle hook) sees the original command unchanged and
continues normally.

Forward-declared workflow id: PV-01 (v8.3.1) registered ``shell-proxy``
under ``runtime-plugins.yaml::plugins[rtk].invoked_by_workflows``;
this PV is the activation surface (env-flag), not a workflow template.
PV-02 does NOT need to register a workflow — the env-flag activation
model is sufficient per the task spec.

Public API:

* :func:`is_proxy_enabled` — pure env-flag read; no subprocess work
* :func:`proxy_command` — module-level convenience equivalent to
  ``ShellProxy().wrap_command(cmd)``
* :class:`ShellProxy` — the main wrapper
* :class:`ShellProxyConfig` — frozen dataclass capturing env-flag state
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from dataclasses import dataclass, field

from devolaflow.shell_proxy.registry import Tier, match_command

logger = logging.getLogger(__name__)


_ENV_FLAG: str = "DEVOLAFLOW_RTK_PROXY"
"""Primary activation env-flag. Set to ``"1"`` to enable the proxy.

Any value other than ``"1"`` (including ``"0"``, empty string, and
unset) leaves the proxy DISABLED for R5 strict compatibility with
the v8.3.1 baseline."""

_TIER2_ENV_FLAG: str = "DEVOLAFLOW_RTK_PROXY_TIER2"
"""Secondary opt-in env-flag for Tier 2 commands.

Tier 2 entries (`git add`, `git commit`, `git show`, `cargo test`,
`npm test`, `make`) are eligible for rewriting ONLY when this flag is
also set to ``"1"``. The primary :data:`_ENV_FLAG` MUST also be set —
Tier 2 alone is not enough."""

_DISTINGUISH_TIMEOUT_SECONDS: float = 5.0
"""Wall-clock budget for the ``rtk gain`` distinguish probe.

Modeled on the existing ``runtime-plugins.yaml::defaults.network_timeout_seconds``
pattern but tighter — distinguish runs locally with no network and the
binary should respond in <100ms when correctly installed."""


@dataclass(frozen=True)
class ShellProxyConfig:
    """Frozen snapshot of the proxy's activation context.

    Captured once per :class:`ShellProxy` instantiation so repeated
    calls to :meth:`ShellProxy.wrap_command` don't re-read the
    environment. The env-flag values, the resolved binary path, and
    the distinguish-probe outcome are all captured up-front, allowing
    the per-call hot path to be a single dict lookup + regex match.

    The ``proxy_enabled`` field is the canonical "should I rewrite?"
    boolean — it is True iff:

    1. The primary env-flag is set to ``"1"``, AND
    2. ``shutil.which("rtk")`` returned a non-None path, AND
    3. ``rtk gain`` exited 0 within :data:`_DISTINGUISH_TIMEOUT_SECONDS`.

    When :data:`_ENV_FLAG` is unset, fields 2 + 3 are NEVER probed and
    ``proxy_enabled`` is False — this is the R5 strict zero-overhead
    code path.
    """

    env_flag_set: bool = False
    tier2_enabled: bool = False
    rtk_path: str | None = None
    distinguish_passed: bool = False
    distinguish_error: str | None = None
    proxy_enabled: bool = False
    warnings: tuple[str, ...] = field(default_factory=tuple)


def is_proxy_enabled(env: dict[str, str] | None = None) -> bool:
    """Return True iff :data:`_ENV_FLAG` is set to ``"1"`` in *env*.

    Pure env-flag read — does NOT probe for the rtk binary, does NOT
    spawn any subprocess. Suitable for the hot path. Use this to
    early-return BEFORE any other shell_proxy code runs (R5 strict).

    When *env* is ``None``, reads :data:`os.environ`.
    """
    source = env if env is not None else os.environ
    return source.get(_ENV_FLAG, "0") == "1"


def _is_tier2_enabled(env: dict[str, str] | None = None) -> bool:
    """Return True iff :data:`_TIER2_ENV_FLAG` is set to ``"1"``."""
    source = env if env is not None else os.environ
    return source.get(_TIER2_ENV_FLAG, "0") == "1"


def _probe_distinguish(rtk_path: str) -> tuple[bool, str | None]:
    """Run ``rtk gain`` to verify this is RTK (not rtk-type-kit).

    Returns ``(True, None)`` on success, ``(False, error_message)`` on
    any failure (non-zero exit, FileNotFoundError, TimeoutExpired,
    OSError). The error message is the rtk-type-kit collision text
    from RTK ``INSTALL.md`` per S-5 — actionable, not silent.

    Failures are NEVER raised — the caller (:class:`ShellProxy`) logs
    a WARNING and falls back to passthrough. This matches RTK's own
    Claude hook behavior in ``hooks/claude/rtk-rewrite.sh`` lines
    21-24: missing-rtk → warn → exit 0 (no rewrite).
    """
    try:
        result = subprocess.run(
            [rtk_path, "gain"],
            capture_output=True,
            text=True,
            timeout=_DISTINGUISH_TIMEOUT_SECONDS,
            check=False,
        )
    except FileNotFoundError as exc:
        return False, f"rtk binary disappeared between which() and run(): {exc}"
    except subprocess.TimeoutExpired:
        return False, (
            f"rtk gain timed out after {_DISTINGUISH_TIMEOUT_SECONDS}s — "
            "binary may be hung or wrong package on PATH"
        )
    except OSError as exc:
        return False, f"OS error invoking rtk gain: {exc}"

    if result.returncode != 0:
        return False, (
            f"rtk gain exited {result.returncode} — likely the rtk-type-kit "
            "collision per RTK INSTALL.md "
            "(https://github.com/rtk-ai/rtk/blob/master/INSTALL.md). "
            "Two unrelated projects are named 'rtk': Rust Token Killer "
            "(this project — has 'rtk gain' command) and Rust Type Kit "
            "(reachingforthejack/rtk — DIFFERENT project). If 'rtk gain' "
            "fails, you have the wrong package — reinstall via the canonical "
            "install script (see https://github.com/rtk-ai/rtk#installation)."
        )

    return True, None


def _resolve_config(env: dict[str, str] | None = None) -> ShellProxyConfig:
    """Resolve the full activation context from *env* and PATH.

    Encapsulates the decision tree:

    1. Env-flag unset/0 → ``ShellProxyConfig()`` defaults (proxy_enabled=False);
       NO subprocess work done (R5 strict).
    2. Env-flag set + rtk missing → log WARNING, return config with
       ``rtk_path=None`` and ``proxy_enabled=False``.
    3. Env-flag set + rtk present + gain fails → log WARNING with
       collision text per S-5, return config with
       ``distinguish_passed=False`` and ``proxy_enabled=False``.
    4. All checks pass → ``proxy_enabled=True``, ``rtk_path`` set,
       ``distinguish_passed=True``.

    Tier 2 enablement (``DEVOLAFLOW_RTK_PROXY_TIER2``) is captured
    independently and is meaningful only when ``proxy_enabled`` is True.
    """
    flag_set = is_proxy_enabled(env)
    if not flag_set:
        # R5 strict zero-overhead path — no PATH lookup, no subprocess.
        return ShellProxyConfig(env_flag_set=False, proxy_enabled=False)

    tier2 = _is_tier2_enabled(env)
    rtk_path = shutil.which("rtk")
    if rtk_path is None:
        msg = (
            f"{_ENV_FLAG}=1 but `rtk` binary not found on PATH; "
            "passthrough enabled. Install rtk per "
            "https://github.com/rtk-ai/rtk#installation"
        )
        logger.warning("[shell_proxy] %s", msg)
        return ShellProxyConfig(
            env_flag_set=True,
            tier2_enabled=tier2,
            rtk_path=None,
            proxy_enabled=False,
            warnings=(msg,),
        )

    distinguish_ok, distinguish_err = _probe_distinguish(rtk_path)
    if not distinguish_ok:
        msg = (
            f"{_ENV_FLAG}=1 and rtk found at {rtk_path}, but distinguish "
            f"probe failed; passthrough enabled. {distinguish_err}"
        )
        logger.warning("[shell_proxy] %s", msg)
        return ShellProxyConfig(
            env_flag_set=True,
            tier2_enabled=tier2,
            rtk_path=rtk_path,
            distinguish_passed=False,
            distinguish_error=distinguish_err,
            proxy_enabled=False,
            warnings=(msg,),
        )

    return ShellProxyConfig(
        env_flag_set=True,
        tier2_enabled=tier2,
        rtk_path=rtk_path,
        distinguish_passed=True,
        proxy_enabled=True,
    )


class ShellProxy:
    """RTK shell-command rewriter.

    Hold the resolved :class:`ShellProxyConfig` and expose
    :meth:`wrap_command` as the canonical "rewrite or passthrough"
    entry point.

    Designed to be cheap to instantiate — :class:`ShellProxyConfig`
    captures the activation snapshot once. Multiple calls to
    :meth:`wrap_command` with the same config are pure dict-lookup +
    regex-match.

    Tests can pass a custom *env* dict OR a pre-resolved *config*
    to avoid touching the real environment / spawning subprocess.
    """

    __slots__ = ("config",)

    def __init__(
        self,
        env: dict[str, str] | None = None,
        *,
        config: ShellProxyConfig | None = None,
    ) -> None:
        if config is not None:
            self.config: ShellProxyConfig = config
        else:
            self.config = _resolve_config(env)

    def wrap_command(self, cmd: str) -> str:
        """Return the (possibly rewritten) command.

        Decision rules:

        * If the proxy is disabled (env-flag off, rtk missing, or
          distinguish failed) → return *cmd* unchanged.
        * If *cmd* is None / empty / not a string → return *cmd*
          unchanged (defensive — the lifecycle hook validates schema
          but the proxy is robust to malformed input).
        * If *cmd* matches a Tier 1 entry → return ``"rtk " + cmd``.
        * If *cmd* matches a Tier 2 entry AND ``DEVOLAFLOW_RTK_PROXY_TIER2=1``
          → return ``"rtk " + cmd``.
        * Otherwise → return *cmd* unchanged.

        The rewritten form is ``"rtk " + cmd`` (NOT ``f"rtk {cmd}"``)
        to make the prefix obvious in logs and tests; the trailing
        whitespace handling is delegated to ``rtk rewrite``'s own
        parser per RTK's documented hook protocol.
        """
        if not self.config.proxy_enabled:
            return cmd

        if not isinstance(cmd, str) or not cmd:
            return cmd

        tier: Tier | None = match_command(cmd, tier2_enabled=self.config.tier2_enabled)
        if tier is None:
            return cmd

        return "rtk " + cmd


def proxy_command(cmd: str, env: dict[str, str] | None = None) -> str:
    """Module-level convenience wrapping :meth:`ShellProxy.wrap_command`.

    Equivalent to ``ShellProxy(env).wrap_command(cmd)`` but flat-call
    style for callers that don't need to retain the config snapshot.

    R5 strict zero-overhead is preserved — when the env-flag is unset,
    :func:`is_proxy_enabled` returns False BEFORE the more expensive
    :func:`_resolve_config` work runs, and we short-circuit identity.
    """
    if not is_proxy_enabled(env):
        return cmd
    return ShellProxy(env).wrap_command(cmd)


__all__ = [
    "ShellProxy",
    "ShellProxyConfig",
    "is_proxy_enabled",
    "proxy_command",
]
