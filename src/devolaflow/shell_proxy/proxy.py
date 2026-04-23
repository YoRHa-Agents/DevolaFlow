"""RTK shell-proxy wrapper (PV-02 R-002 + PV-04 M-002 layer integration).

PV-02 (v8.3.2): closes ``R-002`` from
``.local/research/v8.4.0_gap_analysis.md`` §2.1: when the env-flag
``DEVOLAFLOW_RTK_PROXY=1`` is set AND the ``rtk`` binary is on PATH AND
``rtk gain`` succeeds AND the command matches
:mod:`devolaflow.shell_proxy.registry`'s whitelist, transparently
rewrites the Shell-tool call as ``rtk <cmd>`` for the documented
~80% token-compression layer per ``.local/research/v8.4.0_rtk_nines_analysis.md``
§6.

PV-04 (v8.3.4): closes ``M-002`` from the same gap analysis. Adds an
optional :meth:`ShellProxy.apply_recipe_to_output` step that, when
``.local/memory/commands/`` recipes exist for the matched command,
applies the local recipe AFTER ``rtk rewrite`` runs. Precedence per
the M-002 ask (verbatim): local recipe wins → RTK rewrite → passthrough.
The new step is purely additive — :meth:`ShellProxy.wrap_command` is
byte-identical pre/post v8.3.4 (the recipe layer operates on captured
output, not on the dispatch command itself).

R5 strict (per task spec): default OFF means ``wrap_command`` is a
zero-overhead identity passthrough — when ``DEVOLAFLOW_RTK_PROXY``
is unset OR set to ``"0"``, the function returns the input string
unchanged WITHOUT spawning any subprocess (no ``shutil.which``, no
``rtk gain`` probe). All v8.3.1 baseline tests pass byte-identical
when the flag is unset. The PV-04 :meth:`apply_recipe_to_output` is
ALSO a no-op when the env-flag is unset OR when no recipes are
present under ``.local/memory/commands/`` — the v8.3.3 baseline
tests pass byte-identical in both cases.

Loud failures (S-5): if the env-flag IS set but ``rtk`` is missing OR
``rtk gain`` returns a non-zero exit code (the latter is the rtk-type-kit
collision case per RTK ``INSTALL.md``), the proxy logs a WARNING with
actionable text AND gracefully passthroughs — it does NOT raise. The
caller (the lifecycle hook) sees the original command unchanged and
continues normally.

Forward-declared workflow id: PV-01 (v8.3.1) registered ``shell-proxy``
under ``runtime-plugins.yaml::plugins[rtk].invoked_by_workflows``;
this module is the activation surface (env-flag), not a workflow template.
PV-02 + PV-04 do NOT need to register a workflow — the env-flag
activation model is sufficient per the task spec.

Public API:

* :func:`is_proxy_enabled` — pure env-flag read; no subprocess work
* :func:`proxy_command` — module-level convenience equivalent to
  ``ShellProxy().wrap_command(cmd)``
* :class:`ShellProxy` — the main wrapper; see also
  :meth:`ShellProxy.apply_recipe_to_output` (PV-04 hook)
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

        v8.3.4 R5 strict: behavior is byte-identical to v8.3.3 — the
        new PV-04 local-recipe layer (:meth:`apply_recipe_to_output`)
        operates on captured output AFTER the rewrite runs, NOT on
        the dispatch command itself. ``wrap_command`` does NOT touch
        ``.local/memory/commands/``.
        """
        if not self.config.proxy_enabled:
            return cmd

        if not isinstance(cmd, str) or not cmd:
            return cmd

        tier: Tier | None = match_command(cmd, tier2_enabled=self.config.tier2_enabled)
        if tier is None:
            return cmd

        return "rtk " + cmd

    def apply_recipe_to_output(
        self,
        cmd: str,
        output: str,
        *,
        repo_signal: str | None = None,
    ) -> tuple[str, bool]:
        """Apply the matching local recipe to a command's captured *output*.

        v8.3.4 PV-04 — closes M-002. After ``wrap_command`` decides
        whether to rewrite the command via ``rtk <cmd>`` (PV-02) and the
        Shell tool actually executes it, the captured stdout/stderr can
        be passed through this method to apply repo-specific compression
        recipes layered ON TOP of RTK's built-in 100+ command rewrites.

        Decision tree (precedence per gap analysis §2.1 M-002 verbatim):

        1. Proxy disabled (env-flag off, rtk missing, distinguish failed)
           → return ``(output, False)`` IMMEDIATELY. NO file IO.
        2. *cmd* not whitelisted by the registry → return
           ``(output, False)`` (the proxy didn't rewrite it; the local
           recipe layer should not either).
        3. No recipe matches *cmd*'s canonical id → return
           ``(output, False)`` (caller falls back to RTK's already-applied
           rewrite output, then to passthrough — the precedence chain).
        4. Recipe matches AND apply succeeds → return
           ``(rewritten_output, True)``.
        5. Recipe matches BUT regex.sub raises (defensive) → log WARNING
           and return ``(output, False)``. Loud per S-5.

        R5 strict: when no ``.local/memory/commands/`` directory exists
        OR no recipes match *cmd*, this method is byte-equivalent to
        identity passthrough — :meth:`wrap_command` behavior is
        unchanged from v8.3.3. The local-recipe layer is purely additive.

        Args:
            cmd: The shell command (the original *cmd* passed to
                :meth:`wrap_command`, not the ``"rtk " + cmd`` rewrite —
                the recipe matcher anchors on the canonical command
                head, e.g. ``pytest`` not ``rtk pytest``).
            output: The captured stdout/stderr text from running the
                (possibly RTK-rewritten) command.
            repo_signal: Optional namespace filter (forwarded to
                :func:`apply_local_recipe`). When supplied, narrows the
                recipe lookup to the matching ``repo_signal`` namespace
                only.

        Returns:
            A tuple ``(output_after_recipe, was_applied)``. ``was_applied``
            is True iff a local recipe matched AND the substitutions
            ran without raising. When False, the caller sees the
            original *output* unchanged and the precedence chain falls
            through to RTK's pre-applied compression (already in
            *output* when the proxy rewrote the command) → passthrough.
        """
        if not self.config.proxy_enabled:
            return output, False
        if not isinstance(cmd, str) or not cmd:
            return output, False

        tier: Tier | None = match_command(cmd, tier2_enabled=self.config.tier2_enabled)
        if tier is None:
            # Out-of-whitelist commands are not eligible for the local
            # recipe layer either — preserves the v8.3.3 invariant that
            # the proxy + recipe surfaces stay aligned.
            return output, False

        from devolaflow.shell_proxy.commands import apply_local_recipe  # noqa: PLC0415

        return apply_local_recipe(cmd, output, repo_signal=repo_signal)


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
