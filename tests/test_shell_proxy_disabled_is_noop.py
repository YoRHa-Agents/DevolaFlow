"""R5 strict baseline tests — shell-proxy is a no-op when DEVOLAFLOW_RTK_PROXY is unset.

Codifies the contract that PV-02 (v8.3.2) MUST preserve the v8.3.1
baseline byte-identical when the env-flag is unset / set to "0":

1. :func:`devolaflow.shell_proxy.proxy_command` returns input unchanged
2. :class:`devolaflow.shell_proxy.ShellProxy` does NOT call
   :func:`shutil.which` or :func:`subprocess.run`
3. The lifecycle hook :func:`devolaflow.lifecycle.pre_shell_call`
   returns ``metadata["wrapped_cmd"]`` == ``payload["cmd"]``

Mirror the v8.3.0 PV-08 R5 strict precedent (71/71 byte-identical
tests when memory-bridge feature flag is unset). The filename is
deliberately verbose to flag intent — this file must not be deleted
without explicit retrospective entry per the v8.4.0 cycle plan §4.

External canonical URL (per S-7): https://github.com/rtk-ai/rtk
"""

from __future__ import annotations

from unittest.mock import patch

from devolaflow.lifecycle import pre_shell_call
from devolaflow.shell_proxy import (
    ShellProxy,
    is_proxy_enabled,
    proxy_command,
)


class TestR5StrictProxyDisabledIsNoop:
    def test_proxy_command_is_identity_for_all_command_shapes_when_unset(self) -> None:
        env: dict[str, str] = {}
        cmds = [
            "pytest tests/ -q",
            "ruff check src/ tests/",
            "git diff HEAD",
            "git log -1 --oneline",
            "git status --short",
            "git add .",
            "git commit -m 'feat'",
            "make check-cursor-skill",
            "python -c 'print(1)'",
            "ls -la",
        ]
        for cmd in cmds:
            assert proxy_command(cmd, env=env) == cmd, (
                f"R5 strict: proxy_command should be identity when "
                f"DEVOLAFLOW_RTK_PROXY is unset; got "
                f"{proxy_command(cmd, env=env)!r} for cmd={cmd!r}"
            )
        # Also verify "0" is treated as off
        assert proxy_command("pytest tests/", env={"DEVOLAFLOW_RTK_PROXY": "0"}) == "pytest tests/"

    def test_no_subprocess_calls_when_unset(self) -> None:
        # The hot-path R5 strict invariant: zero subprocess overhead.
        env: dict[str, str] = {}
        with patch("subprocess.run") as mock_run, patch("shutil.which") as mock_which:
            for cmd in ("pytest tests/", "git diff", "ruff check src/"):
                proxy_command(cmd, env=env)
            # Also exercise the class entry point.
            proxy = ShellProxy(env)
            assert proxy.config.proxy_enabled is False
            proxy.wrap_command("pytest tests/")
            assert mock_run.call_count == 0, (
                "R5 strict: no subprocess.run call when DEVOLAFLOW_RTK_PROXY unset"
            )
            assert mock_which.call_count == 0, (
                "R5 strict: no shutil.which call when DEVOLAFLOW_RTK_PROXY unset"
            )

    def test_pre_shell_call_passthrough_metadata_when_unset(self) -> None:
        # The lifecycle-hook integration half of R5 strict: metadata says
        # not-rewritten, proxy not-enabled, no subprocess work happened.
        with (
            patch.dict("os.environ", {}, clear=True),
            patch("subprocess.run") as mock_run,
            patch("shutil.which") as mock_which,
        ):
            payload = {"cmd": "pytest tests/ -q", "cwd": None}
            result = pre_shell_call(payload)
            assert result.passed is True
            assert result.metadata["wrapped_cmd"] == "pytest tests/ -q"
            assert result.metadata["proxy_enabled"] is False
            assert result.metadata["was_rewritten"] is False
            # Original payload is unchanged (hook is non-mutating)
            assert payload["cmd"] == "pytest tests/ -q"
            assert mock_run.call_count == 0
            assert mock_which.call_count == 0

    def test_is_proxy_enabled_is_the_strict_gate(self) -> None:
        # Only literal "1" enables the proxy — defensive against typos
        # (e.g. "true", "yes", "TRUE", "1.0", "01", " 1 ") accidentally
        # flipping the default.
        truthy_lookalikes = ["true", "yes", "on", "TRUE", "1.0", "01", " 1 "]
        for val in truthy_lookalikes:
            assert is_proxy_enabled({"DEVOLAFLOW_RTK_PROXY": val}) is False, (
                f"R5 strict: only literal '1' should enable; got True for {val!r}"
            )
        # Unset env → False; literal "1" → True
        assert is_proxy_enabled({}) is False
        assert is_proxy_enabled({"DEVOLAFLOW_RTK_PROXY": "1"}) is True
