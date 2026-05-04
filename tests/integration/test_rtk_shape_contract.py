"""RTK bridge shape contract tests.

Pins the v10.8.0 D-C-2 contract: DevolaFlow's ``ShellProxy.wrap_command``
consumes ``rtk rewrite <cmd>`` stdout verbatim. A schema drift in RTK's
rewrite output format would surface here before it lands in production
shell execution.

Canonical RTK URL: https://github.com/rtk-ai/rtk
"""

from __future__ import annotations

from tests.integration.conftest import load_text_fixture


class TestRTKRewriteStdoutShape:
    """Pin the shape of ``rtk rewrite <cmd>`` stdout.

    The contract (v8.3.2 PV-02 baseline): RTK rewrites a Tier-1 command by
    prepending the literal ``rtk `` string. For known Tier-1 commands
    (``pytest``, ``git diff``, etc.) the output MUST be ``rtk <cmd>``.
    """

    def test_rtk_rewrite_stdout_shape_for_both_fixtures(self) -> None:
        """`rtk rewrite <cmd>` stdout starts with 'rtk ' for pytest + git diff.

        Consolidates the per-fixture shape check into one parametrized-in-body
        regression — both fixtures share the same prepend-literal-'rtk '
        contract; a single assertion chain catches the whole class.
        """
        for fixture_name, expected_substr in (
            ("rewrite_pytest_stdout.txt", "pytest"),
            ("rewrite_git_diff_stdout.txt", "git"),
        ):
            raw = load_text_fixture("rtk", fixture_name)
            lines = [line for line in raw.splitlines() if not line.startswith("#") and line.strip()]
            assert len(lines) == 1, (
                f"RTK {fixture_name} should carry 1 rewrite line; got {len(lines)}: {lines}"
            )
            rewrite = lines[0]
            assert rewrite.startswith("rtk "), (
                f"RTK rewrite must start with 'rtk ' literal; got {rewrite!r}"
            )
            assert expected_substr in rewrite

    def test_rtk_proxy_wrap_command_matches_fixture_shape(self) -> None:
        """ShellProxy.wrap_command output shape matches the captured fixture.

        This is the end-to-end shape check: the fixture captures
        ``rtk rewrite "pytest tests/ -q"`` stdout; ``wrap_command`` should
        produce the same "rtk pytest tests/ -q" string for that input.
        """
        from unittest.mock import patch

        from devolaflow.shell_proxy import ShellProxy
        from devolaflow.shell_proxy.proxy import ShellProxyConfig

        raw = load_text_fixture("rtk", "rewrite_pytest_stdout.txt")
        expected_lines = [
            line for line in raw.splitlines() if not line.startswith("#") and line.strip()
        ]
        expected = expected_lines[-1]

        # Force proxy_enabled via a frozen config; no real rtk binary needed.
        with patch("shutil.which", return_value="/usr/local/bin/rtk"):
            config = ShellProxyConfig(
                env_flag_set=True,
                tier2_enabled=False,
                rtk_path="/usr/local/bin/rtk",
                distinguish_passed=True,
                proxy_enabled=True,
            )
            proxy = ShellProxy(config=config)
            wrapped = proxy.wrap_command("pytest tests/ -q")
        assert wrapped == expected, (
            f"wrap_command shape mismatch vs fixture; wrapped={wrapped!r}, fixture={expected!r}"
        )
