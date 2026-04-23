"""Tests for the RTK shell-proxy package (v8.3.2 PV-02 — closes R-002).

Mirrors the test discipline established by ``tests/test_plugins.py``
(v8.3.1 PV-01) and the lifecycle hook tests in
``tests/test_lifecycle_hooks.py``.

Coverage:

* :class:`ShellProxyConfig` / :class:`ShellProxy` instantiation under
  every env-flag + binary + distinguish combination
* :func:`is_proxy_enabled` pure env-flag read (R5 strict no-subprocess
  hot path)
* :func:`proxy_command` module-level convenience
* :data:`WHITELIST` regex precision per task spec (`pytest tests/...`
  matches but `pytest-style-runner` does NOT; `git diff HEAD` matches
  but `git diffshow` does NOT)
* Tier 2 opt-in gating
* ``rtk gain`` distinguish-failure path → log + passthrough (S-5)
* ``rtk`` missing → log + passthrough

Subprocess + ``shutil.which`` are mocked everywhere — no real RTK
binary required, no network, no compile.

To stay within the v8.4.0 cycle plan §4 +35-test PV-02 cap (mirrors
the v8.3.0 retro §4.6 lesson on test discipline), this file uses
loops-with-asserts inside single test functions where the cases
exercise the same code path with different inputs. Each test function
fails-fast on its first sub-case mismatch, so debugging stays cheap.
"""

from __future__ import annotations

import logging
import subprocess
from unittest.mock import patch

import pytest

from devolaflow.shell_proxy import (
    WHITELIST,
    ShellProxy,
    ShellProxyConfig,
    is_proxy_enabled,
    proxy_command,
)
from devolaflow.shell_proxy.proxy import _resolve_config
from devolaflow.shell_proxy.registry import match_command


def _ok(stdout: str = "", returncode: int = 0) -> subprocess.CompletedProcess[str]:
    """Build a successful :class:`subprocess.CompletedProcess` for mock returns."""
    return subprocess.CompletedProcess(
        args=["rtk", "gain"],
        returncode=returncode,
        stdout=stdout,
        stderr="",
    )


@pytest.fixture
def env_off() -> dict[str, str]:
    """Env dict with the proxy flag explicitly off (default-off baseline)."""
    return {}


@pytest.fixture
def env_on() -> dict[str, str]:
    """Env dict with the primary proxy flag set to ``"1"``."""
    return {"DEVOLAFLOW_RTK_PROXY": "1"}


@pytest.fixture
def env_on_tier2() -> dict[str, str]:
    """Env dict with both the primary AND Tier 2 flags set."""
    return {"DEVOLAFLOW_RTK_PROXY": "1", "DEVOLAFLOW_RTK_PROXY_TIER2": "1"}


# ---------------------------------------------------------------------------
# Section 1 — is_proxy_enabled (pure env-flag read; R5 strict no-subprocess)
# ---------------------------------------------------------------------------


class TestIsProxyEnabled:
    def test_env_flag_decides_for_all_value_shapes(self) -> None:
        # Only literal "1" enables; everything else (including unset, "0",
        # "true", "yes") leaves the proxy disabled.
        cases: list[tuple[dict[str, str], bool]] = [
            ({}, False),
            ({"DEVOLAFLOW_RTK_PROXY": "0"}, False),
            ({"DEVOLAFLOW_RTK_PROXY": "1"}, True),
            ({"DEVOLAFLOW_RTK_PROXY": "true"}, False),
            ({"DEVOLAFLOW_RTK_PROXY": "yes"}, False),
            ({"DEVOLAFLOW_RTK_PROXY": ""}, False),
        ]
        for env, expected in cases:
            assert is_proxy_enabled(env) is expected, f"env={env!r}"

    def test_does_not_spawn_subprocess(self, env_off: dict[str, str]) -> None:
        # R5 strict invariant — is_proxy_enabled must never shell out.
        with patch("subprocess.run") as mock_run, patch("shutil.which") as mock_which:
            assert is_proxy_enabled(env_off) is False
            assert is_proxy_enabled({"DEVOLAFLOW_RTK_PROXY": "1"}) is True
            assert mock_run.call_count == 0
            assert mock_which.call_count == 0


# ---------------------------------------------------------------------------
# Section 2 — Whitelist registry (regex precision per task spec)
# ---------------------------------------------------------------------------


class TestWhitelistRegistry:
    def test_tier1_commands_match_with_and_without_args(self) -> None:
        # All Tier 1 commands match bare and with arguments.
        cases = [
            "pytest",
            "pytest tests/",
            "pytest tests/test_smoke.py -v",
            "ruff check",
            "ruff check src/ tests/",
            "git diff",
            "git diff HEAD",
            "git diff --stat",
            "git log",
            "git log -1 --oneline",
            "git status",
            "git status --short",
        ]
        for cmd in cases:
            assert match_command(cmd) == 1, f"expected Tier 1 for {cmd!r}"

    def test_anchor_excludes_hyphen_and_subcommand_glue(self) -> None:
        # Per task spec: `pytest tests/...` matches, `pytest-style-runner`
        # does NOT; `git diff` matches, `git diffshow` does NOT.
        non_whitelist = [
            "pytest-style-runner",
            "ruff check-helper",
            "git diffshow",
            "git difftool",
            "python -c 'print(1)'",
            "ls -la",
            "docker ps",
        ]
        for cmd in non_whitelist:
            assert match_command(cmd, tier2_enabled=True) is None, f"expected None for {cmd!r}"

    def test_tier2_gated_by_flag(self) -> None:
        # All Tier 2 commands match only when tier2_enabled=True.
        tier2_cases = [
            "git add .",
            "git commit -m 'x'",
            "git show HEAD",
            "cargo test",
            "npm test",
            "make",
            "make check-cursor-skill",
        ]
        for cmd in tier2_cases:
            assert match_command(cmd, tier2_enabled=False) is None, (
                f"Tier 2 should be gated when flag off; got match for {cmd!r}"
            )
            assert match_command(cmd, tier2_enabled=True) == 2, (
                f"Tier 2 should match when flag on for {cmd!r}"
            )

    def test_empty_or_invalid_returns_none(self) -> None:
        assert match_command("") is None
        assert match_command(None) is None  # type: ignore[arg-type]
        assert match_command(123) is None  # type: ignore[arg-type]

    def test_whitelist_contains_all_required_entries(self) -> None:
        # Per task spec — Tier 1 = pytest, ruff check, git diff/log/status
        for prefix in ("pytest", "ruff check", "git diff", "git log", "git status"):
            assert WHITELIST[prefix] == 1, f"{prefix!r} should be Tier 1"
        # Tier 2 = git add/commit/show, cargo test, npm test, make
        for prefix in (
            "git add",
            "git commit",
            "git show",
            "cargo test",
            "npm test",
            "make",
        ):
            assert WHITELIST[prefix] == 2, f"{prefix!r} should be Tier 2"


# ---------------------------------------------------------------------------
# Section 3 — ShellProxyConfig + _resolve_config (env + which + gain combos)
# ---------------------------------------------------------------------------


class TestResolveConfig:
    def test_flag_unset_returns_disabled_config_no_subprocess(
        self,
        env_off: dict[str, str],
    ) -> None:
        # R5 strict: env-flag off → no PATH lookup, no subprocess, no warnings
        with patch("shutil.which") as mock_which, patch("subprocess.run") as mock_run:
            cfg = _resolve_config(env_off)
            assert cfg.proxy_enabled is False
            assert cfg.env_flag_set is False
            assert cfg.rtk_path is None
            assert cfg.distinguish_passed is False
            assert cfg.warnings == ()
            assert mock_which.call_count == 0
            assert mock_run.call_count == 0

    def test_flag_on_rtk_missing_returns_disabled_with_warning(
        self,
        env_on: dict[str, str],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with (
            patch("shutil.which", return_value=None) as mock_which,
            patch("subprocess.run") as mock_run,
            caplog.at_level(logging.WARNING, logger="devolaflow.shell_proxy.proxy"),
        ):
            cfg = _resolve_config(env_on)
            assert cfg.proxy_enabled is False
            assert cfg.env_flag_set is True
            assert cfg.rtk_path is None
            assert mock_which.call_count == 1
            assert mock_run.call_count == 0  # No gain probe when binary missing
            assert len(cfg.warnings) == 1
            assert "binary not found on PATH" in cfg.warnings[0]
            assert any("binary not found on PATH" in r.message for r in caplog.records)

    def test_flag_on_rtk_present_gain_succeeds_returns_enabled(
        self,
        env_on: dict[str, str],
    ) -> None:
        with (
            patch("shutil.which", return_value="/usr/local/bin/rtk"),
            patch("subprocess.run", return_value=_ok(stdout="100 tokens saved")),
        ):
            cfg = _resolve_config(env_on)
            assert cfg.proxy_enabled is True
            assert cfg.env_flag_set is True
            assert cfg.rtk_path == "/usr/local/bin/rtk"
            assert cfg.distinguish_passed is True
            assert cfg.warnings == ()

    def test_flag_on_gain_fails_returns_disabled_with_collision_warning(
        self,
        env_on: dict[str, str],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        # The wrong-package case: rtk-type-kit responds to --version but not gain
        with (
            patch("shutil.which", return_value="/usr/local/bin/rtk"),
            patch("subprocess.run", return_value=_ok(returncode=1)),
            caplog.at_level(logging.WARNING, logger="devolaflow.shell_proxy.proxy"),
        ):
            cfg = _resolve_config(env_on)
            assert cfg.proxy_enabled is False
            assert cfg.distinguish_passed is False
            assert cfg.distinguish_error is not None
            # S-5: actionable text pointing at the rtk-type-kit collision
            assert "rtk-type-kit" in cfg.distinguish_error
            assert "INSTALL.md" in cfg.distinguish_error
            assert any("rtk-type-kit" in r.message for r in caplog.records)

    def test_flag_on_gain_subprocess_errors_return_disabled(
        self,
        env_on: dict[str, str],
    ) -> None:
        # Three failure modes: timeout, OSError, FileNotFoundError — each
        # gets a distinct actionable error message but all gracefully degrade.
        cases: list[tuple[BaseException, str]] = [
            (subprocess.TimeoutExpired(cmd=["rtk", "gain"], timeout=5.0), "timed out"),
            (OSError("permission denied"), "OS error"),
            (FileNotFoundError("rtk gone"), "disappeared"),
        ]
        for side_effect, error_substring in cases:
            with (
                patch("shutil.which", return_value="/usr/local/bin/rtk"),
                patch("subprocess.run", side_effect=side_effect),
            ):
                cfg = _resolve_config(env_on)
                assert cfg.proxy_enabled is False
                assert cfg.distinguish_error is not None
                assert error_substring in cfg.distinguish_error, (
                    f"expected {error_substring!r} in {cfg.distinguish_error!r}"
                )

    def test_tier2_flag_captured(self, env_on_tier2: dict[str, str]) -> None:
        with (
            patch("shutil.which", return_value="/usr/local/bin/rtk"),
            patch("subprocess.run", return_value=_ok()),
        ):
            cfg = _resolve_config(env_on_tier2)
            assert cfg.proxy_enabled is True
            assert cfg.tier2_enabled is True


# ---------------------------------------------------------------------------
# Section 4 — ShellProxy.wrap_command (rewrite-or-passthrough decisions)
# ---------------------------------------------------------------------------


class TestShellProxyWrapCommand:
    def test_passthrough_when_proxy_disabled(self, env_off: dict[str, str]) -> None:
        proxy = ShellProxy(env_off)
        assert proxy.wrap_command("pytest tests/ -q") == "pytest tests/ -q"
        assert proxy.wrap_command("git diff") == "git diff"

    def test_rewrites_tier1_when_enabled(self, env_on: dict[str, str]) -> None:
        with (
            patch("shutil.which", return_value="/usr/local/bin/rtk"),
            patch("subprocess.run", return_value=_ok()),
        ):
            proxy = ShellProxy(env_on)
        cases = [
            ("pytest tests/ -q", "rtk pytest tests/ -q"),
            ("ruff check src/", "rtk ruff check src/"),
            ("git diff HEAD", "rtk git diff HEAD"),
            ("git log -1", "rtk git log -1"),
            ("git status --short", "rtk git status --short"),
        ]
        for cmd, expected in cases:
            assert proxy.wrap_command(cmd) == expected, f"cmd={cmd!r}"

    def test_passthrough_for_unknown_or_ungated_when_enabled(
        self,
        env_on: dict[str, str],
    ) -> None:
        with (
            patch("shutil.which", return_value="/usr/local/bin/rtk"),
            patch("subprocess.run", return_value=_ok()),
        ):
            proxy = ShellProxy(env_on)
        # Tier 2 commands without the secondary flag set + non-whitelist
        passthroughs = [
            "python -c 'print(1)'",
            "ls -la",
            "git add .",
            "git commit -m 'x'",
            "make check-cursor-skill",
        ]
        for cmd in passthroughs:
            assert proxy.wrap_command(cmd) == cmd, f"cmd={cmd!r}"

    def test_rewrites_tier2_when_both_flags_set(
        self,
        env_on_tier2: dict[str, str],
    ) -> None:
        with (
            patch("shutil.which", return_value="/usr/local/bin/rtk"),
            patch("subprocess.run", return_value=_ok()),
        ):
            proxy = ShellProxy(env_on_tier2)
        cases = [
            ("git add .", "rtk git add ."),
            ("git commit -m 'x'", "rtk git commit -m 'x'"),
            ("git show HEAD", "rtk git show HEAD"),
            ("cargo test", "rtk cargo test"),
            ("make", "rtk make"),
        ]
        for cmd, expected in cases:
            assert proxy.wrap_command(cmd) == expected, f"cmd={cmd!r}"

    def test_passthrough_when_rtk_missing_or_distinguish_fails(
        self,
        env_on: dict[str, str],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        # rtk missing → passthrough
        with (
            patch("shutil.which", return_value=None),
            caplog.at_level(logging.WARNING, logger="devolaflow.shell_proxy.proxy"),
        ):
            proxy_missing = ShellProxy(env_on)
        assert proxy_missing.wrap_command("pytest tests/") == "pytest tests/"
        assert proxy_missing.config.proxy_enabled is False

        # rtk present but distinguish (`rtk gain`) fails → passthrough + warn
        with (
            patch("shutil.which", return_value="/usr/local/bin/rtk"),
            patch("subprocess.run", return_value=_ok(returncode=1)),
            caplog.at_level(logging.WARNING, logger="devolaflow.shell_proxy.proxy"),
        ):
            proxy_collision = ShellProxy(env_on)
        assert proxy_collision.wrap_command("pytest tests/") == "pytest tests/"
        assert proxy_collision.config.proxy_enabled is False

    def test_handles_empty_or_none_safely(self, env_on: dict[str, str]) -> None:
        with (
            patch("shutil.which", return_value="/usr/local/bin/rtk"),
            patch("subprocess.run", return_value=_ok()),
        ):
            proxy = ShellProxy(env_on)
        assert proxy.wrap_command("") == ""
        # Defensive — proxy is robust to malformed input even though the
        # lifecycle hook validates schema first.
        assert proxy.wrap_command(None) is None  # type: ignore[arg-type]

    def test_accepts_pre_resolved_config(self) -> None:
        # Tests can bypass env/subprocess with a pre-resolved config
        cfg = ShellProxyConfig(
            env_flag_set=True,
            rtk_path="/usr/local/bin/rtk",
            distinguish_passed=True,
            proxy_enabled=True,
        )
        proxy = ShellProxy(config=cfg)
        assert proxy.wrap_command("pytest tests/") == "rtk pytest tests/"


# ---------------------------------------------------------------------------
# Section 5 — proxy_command module-level convenience
# ---------------------------------------------------------------------------


class TestProxyCommand:
    def test_passthrough_when_disabled_no_subprocess(
        self,
        env_off: dict[str, str],
    ) -> None:
        # R5 strict: identity passthrough; no subprocess work
        with patch("shutil.which") as mock_which, patch("subprocess.run") as mock_run:
            assert proxy_command("pytest tests/", env=env_off) == "pytest tests/"
            assert mock_which.call_count == 0
            assert mock_run.call_count == 0

    def test_rewrites_when_enabled(self, env_on: dict[str, str]) -> None:
        with (
            patch("shutil.which", return_value="/usr/local/bin/rtk"),
            patch("subprocess.run", return_value=_ok()),
        ):
            assert proxy_command("pytest tests/", env=env_on) == "rtk pytest tests/"
