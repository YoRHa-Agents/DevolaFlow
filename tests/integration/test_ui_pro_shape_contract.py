"""ui-pro bridge shape contract tests.

Pins the v10.8.0 D-C-2 contract: the `uipro init` install step produces
a stable success-log shape that future ui-pro releases MUST preserve or
DevolaFlow's `pre_plugin_invocation` → `ensure_plugin('ui-pro')` path
silently regresses.

Canonical ui-pro URL: https://github.com/YoRHa-Agents/ui-pro
"""

from __future__ import annotations

from tests.integration.conftest import load_text_fixture


class TestUiProInitLogShape:
    """Pin that ``uipro init --ai cursor --global`` success log has expected markers."""

    def test_init_success_log_has_expected_markers_and_targets(self) -> None:
        """Success log contains the 4 markers DF surfaces in PPI diagnostics.

        Consolidates the per-marker + per-target checks into one regression —
        ui-pro's log is a single-shape contract; splitting the assertions
        doesn't add coverage but does inflate W-17 budget.
        """
        log = load_text_fixture("ui-pro", "init_success.log")
        # Prefix marker:
        assert "[uipro]" in log
        # Success markers:
        assert "init complete" in log
        assert "exit_code=0" in log
        # DF-expected targets (from runtime-plugins.yaml install_cmd):
        assert "scope=global" in log
        assert "ai=cursor" in log
