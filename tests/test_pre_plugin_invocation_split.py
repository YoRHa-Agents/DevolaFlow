"""Tests for the v10.8.0 D-C-3 `pre_plugin_invocation` responsibility split.

Pins the 5 contract invariants from D-C-3 §2 step 7:

1. **install-only** — `pre_plugin_invocation_install` handles install only
   (no upgrade fires).
2. **upgrade-only** — `pre_plugin_invocation_upgrade` handles staleness +
   upgrade only (no install fires).
3. **alias-byte-identical** — the v9.4.0 `pre_plugin_invocation` event at
   `DEFAULT_EVENTS` position 9 preserves byte-identical observable
   behaviour when `DEVOLAFLOW_AUTO_INSTALL_PLUGINS=1`.
4. **disjoint-violations** — PPI001 fires from the install handler ONLY;
   PPI003 fires from the upgrade handler ONLY.
5. **1-cycle deprecation telegraph** — `env-flags.md` §2.13 documents the
   alias deprecation path + references the split handler modules.

Source: `.local/research/v11.0.0_patches/D-C-3.md` §2 patch_design step 7.
Canonical DevolaFlow URL: https://github.com/YoRHa-Agents/DevolaFlow
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from devolaflow.lifecycle import (
    DEFAULT_EVENTS,
    PRE_PLUGIN_INVOCATION_EVENT,
    PRE_PLUGIN_INVOCATION_INSTALL_EVENT,
    PRE_PLUGIN_INVOCATION_UPGRADE_EVENT,
    HookResult,
    clear_hooks,
    pre_plugin_invocation,
    pre_plugin_invocation_install,
    pre_plugin_invocation_upgrade,
)
from devolaflow.plugins.exceptions import (
    PluginInstallError,
    PluginVersionMismatch,
)


@pytest.fixture(autouse=True)
def _clear_extra_hooks():
    yield
    clear_hooks()


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# §1 — install-only: install handler does NOT fire upgrade_plugin
# ---------------------------------------------------------------------------


class TestInstallHandlerIsInstallOnly:
    """v10.8.0 D-C-3 step 7 bullet 1: install handler is install-only."""

    def test_install_handler_handles_only_install_path(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """install handler calls ensure_plugin; never invokes upgrade_plugin."""
        monkeypatch.setenv("DEVOLAFLOW_AUTO_INSTALL_PLUGINS", "1")

        with (
            patch(
                "devolaflow.plugins.installer.ensure_plugin",
                return_value="1.2.3",
            ) as mock_install,
            patch(
                "devolaflow.plugins.installer.is_plugin_stale",
                return_value=True,
            ) as mock_is_stale,
            patch(
                "devolaflow.plugins.installer.upgrade_plugin",
                return_value="1.2.4",
            ) as mock_upgrade,
        ):
            result = pre_plugin_invocation_install(
                {"plugin_id": "ui-pro"},
                strict=False,
            )

        assert isinstance(result, HookResult)
        assert mock_install.call_count == 1
        assert mock_install.call_args.args == ("ui-pro",)
        # Upgrade + staleness probes MUST NOT fire from the install handler.
        assert mock_is_stale.call_count == 0, (
            "install handler must NOT invoke is_plugin_stale — that is the "
            "upgrade handler's responsibility (D-C-3 §2 step 3)"
        )
        assert mock_upgrade.call_count == 0, (
            "install handler must NOT invoke upgrade_plugin — PPI003 belongs "
            "to the upgrade handler only (D-C-3 §2 disjoint-violations)"
        )


# ---------------------------------------------------------------------------
# §2 — upgrade-only: upgrade handler does NOT fire ensure_plugin
# ---------------------------------------------------------------------------


class TestUpgradeHandlerIsUpgradeOnly:
    """v10.8.0 D-C-3 step 7 bullet 2: upgrade handler is upgrade-only."""

    def test_upgrade_handler_handles_only_staleness_path(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """upgrade handler calls is_plugin_stale + upgrade_plugin; never ensure_plugin."""
        monkeypatch.setenv("DEVOLAFLOW_AUTO_INSTALL_PLUGINS", "1")

        with (
            patch(
                "devolaflow.plugins.installer.ensure_plugin",
                return_value="1.2.3",
            ) as mock_install,
            patch(
                "devolaflow.plugins.installer.is_plugin_stale",
                return_value=True,
            ) as mock_is_stale,
            patch(
                "devolaflow.plugins.installer.upgrade_plugin",
                return_value="1.2.4",
            ) as mock_upgrade,
        ):
            result = pre_plugin_invocation_upgrade(
                {"plugin_id": "ui-pro"},
                strict=False,
            )

        assert isinstance(result, HookResult)
        # Install MUST NOT fire from the upgrade handler.
        assert mock_install.call_count == 0, (
            "upgrade handler must NOT invoke ensure_plugin — that is the "
            "install handler's responsibility (D-C-3 §2 step 3)"
        )
        assert mock_is_stale.call_count == 1
        assert mock_upgrade.call_count == 1


# ---------------------------------------------------------------------------
# §3 — alias byte-identical when DEVOLAFLOW_AUTO_INSTALL_PLUGINS=1
# ---------------------------------------------------------------------------


class TestAliasByteIdentical:
    """D-C-3 step 7 bullet 3: alias preserves byte-identical v10.3.0 behaviour."""

    def test_alias_event_emits_byte_identical_to_v10_3_0(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Alias hook fires install + upgrade in sequence; PPI001 + PPI003 shape preserved."""
        monkeypatch.setenv("DEVOLAFLOW_AUTO_INSTALL_PLUGINS", "1")

        # Simulate install failure + skip upgrade (per v10.2.3 PV-04 contract:
        # install failure returns early before upgrade fires).
        with (
            patch(
                "devolaflow.plugins.installer.ensure_plugin",
                side_effect=PluginInstallError("npm registry 503"),
            ),
            patch(
                "devolaflow.plugins.installer.is_plugin_stale",
                return_value=False,
            ),
            patch(
                "devolaflow.plugins.installer.upgrade_plugin",
                return_value="1.2.4",
            ),
        ):
            result = pre_plugin_invocation(
                {"plugin_id": "ui-pro"},
                strict=False,
            )

        # PPI001 surfaced (install-failure path); dispatch did NOT raise.
        ppi001 = [v for v in result.violations if v.code == "PPI001"]
        assert len(ppi001) == 1
        # v15.2.0 B-6 — ui-pro is suggest-tier: severity degrades to warning
        # (alias + split handler share _ppi001_violation, so the shape stays
        # byte-identical between the two paths).
        assert ppi001[0].severity == "warning"

    def test_alias_byte_identical_when_disabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Env flag OFF → alias + both split handlers are zero-IO no-ops.

        The R5 strict contract preserved across the split: when
        `DEVOLAFLOW_AUTO_INSTALL_PLUGINS` is unset, every hook returns
        a clean empty HookResult WITHOUT subprocess / filesystem work.
        """
        monkeypatch.delenv("DEVOLAFLOW_AUTO_INSTALL_PLUGINS", raising=False)

        with (
            patch("devolaflow.plugins.installer.ensure_plugin") as mock_install,
            patch("devolaflow.plugins.installer.is_plugin_stale") as mock_is_stale,
            patch("devolaflow.plugins.installer.upgrade_plugin") as mock_upgrade,
        ):
            alias_result = pre_plugin_invocation({"plugin_id": "ui-pro"})
            install_result = pre_plugin_invocation_install({"plugin_id": "ui-pro"})
            upgrade_result = pre_plugin_invocation_upgrade({"plugin_id": "ui-pro"})

        # All three hooks pass cleanly with zero violations.
        assert alias_result.passed is True
        assert install_result.passed is True
        assert upgrade_result.passed is True
        # Zero subprocess / installer work.
        assert mock_install.call_count == 0
        assert mock_is_stale.call_count == 0
        assert mock_upgrade.call_count == 0


# ---------------------------------------------------------------------------
# §4 — disjoint violations: PPI001 ≠ PPI003 surfaces
# ---------------------------------------------------------------------------


class TestSplitHandlersEmitDisjointViolations:
    """D-C-3 step 7 bullet 4: PPI001 stays in install ONLY; PPI003 in upgrade ONLY."""

    def test_split_handlers_emit_disjoint_violations(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """PPI001 ONLY from install handler; PPI003 ONLY from upgrade handler.

        Verifies that the two codes are EMITTED BY DIFFERENT HANDLERS and
        neither handler can accidentally emit the other's code.
        """
        monkeypatch.setenv("DEVOLAFLOW_AUTO_INSTALL_PLUGINS", "1")

        # Install-only failure:
        with patch(
            "devolaflow.plugins.installer.ensure_plugin",
            side_effect=PluginInstallError("install failed"),
        ):
            install_result = pre_plugin_invocation_install(
                {"plugin_id": "ui-pro"},
                strict=False,
            )
        install_codes = {v.code for v in install_result.violations}
        assert install_codes == {"PPI001"}, (
            f"install handler must emit ONLY PPI001; got {install_codes}"
        )

        # Upgrade-only failure:
        with (
            patch(
                "devolaflow.plugins.installer.is_plugin_stale",
                return_value=True,
            ),
            patch(
                "devolaflow.plugins.installer.upgrade_plugin",
                side_effect=PluginVersionMismatch("version clash"),
            ),
        ):
            upgrade_result = pre_plugin_invocation_upgrade(
                {"plugin_id": "ui-pro"},
                strict=False,
            )
        upgrade_codes = {v.code for v in upgrade_result.violations}
        assert upgrade_codes == {"PPI003"}, (
            f"upgrade handler must emit ONLY PPI003; got {upgrade_codes}"
        )


# ---------------------------------------------------------------------------
# §4b — v15.0.0 R3 coverage lift: upgrade-handler guard + fallback branches
# ---------------------------------------------------------------------------


class TestUpgradeHandlerGuardsAndFallbacks:
    """Pin the S-5 best-effort branches the split suite left unexercised."""

    def test_upgrade_threshold_fallbacks_and_payload_guards(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Registry read/parse failures fall back to the default threshold
        (WARN, never raise — S-5 best-effort), and malformed payloads
        short-circuit to an empty result without touching the installer."""
        from devolaflow.lifecycle.pre_plugin_invocation_upgrade import (
            _resolve_upgrade_threshold_hours,
        )

        # Registry unreadable → default, no raise.
        with patch(
            "devolaflow.plugins.installer.load_registry",
            side_effect=FileNotFoundError("no registry"),
        ):
            assert _resolve_upgrade_threshold_hours(24) == 24
        # Registry parse blew up (non-IO) → default, no raise.
        with patch(
            "devolaflow.plugins.installer.load_registry",
            side_effect=RuntimeError("parse boom"),
        ):
            assert _resolve_upgrade_threshold_hours(24) == 24
        # defaults section malformed / threshold invalid → default.
        with patch(
            "devolaflow.plugins.installer.load_registry",
            return_value={"defaults": "not-a-dict"},
        ):
            assert _resolve_upgrade_threshold_hours(24) == 24
        with patch(
            "devolaflow.plugins.installer.load_registry",
            return_value={"defaults": {"upgrade_check_frequency_hours": -5}},
        ):
            assert _resolve_upgrade_threshold_hours(24) == 24
        # A valid registry value wins over the default.
        with patch(
            "devolaflow.plugins.installer.load_registry",
            return_value={"defaults": {"upgrade_check_frequency_hours": 6}},
        ):
            assert _resolve_upgrade_threshold_hours(24) == 6

        # Payload guards: flag ON but the payload carries no usable ids —
        # the handler returns an empty result with ZERO installer work.
        monkeypatch.setenv("DEVOLAFLOW_AUTO_INSTALL_PLUGINS", "1")
        with patch("devolaflow.plugins.installer.is_plugin_stale") as mock_stale:
            for payload in ("not-a-dict", {}, {"plugin_ids": "ui-pro"}, {"plugin_ids": [1, ""]}):
                result = pre_plugin_invocation_upgrade(payload, strict=False)
                assert isinstance(result, HookResult)
                assert result.violations == []
            assert mock_stale.call_count == 0, (
                "guard-path payloads must never reach the staleness probe"
            )

    def test_upgrade_probe_error_fresh_plugin_and_unexpected_reraise(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Staleness-probe errors skip the plugin (WARN), fresh plugins skip
        the upgrade, and a NON-domain upgrade exception re-raises per S-5."""
        import logging

        monkeypatch.setenv("DEVOLAFLOW_AUTO_INSTALL_PLUGINS", "1")

        # is_plugin_stale raised → probe skipped with a WARNING, no upgrade.
        with (
            patch(
                "devolaflow.plugins.installer.is_plugin_stale",
                side_effect=RuntimeError("probe boom"),
            ),
            patch("devolaflow.plugins.installer.upgrade_plugin") as mock_upgrade,
            caplog.at_level(logging.WARNING),
        ):
            result = pre_plugin_invocation_upgrade({"plugin_id": "ui-pro"}, strict=False)
        assert result.violations == []
        assert mock_upgrade.call_count == 0
        assert any("is_plugin_stale" in rec.message for rec in caplog.records), (
            "the skipped probe must log a WARNING (S-5 — no silent failure)"
        )

        # Fresh plugin (not stale) → no upgrade attempted, no violations.
        with (
            patch("devolaflow.plugins.installer.is_plugin_stale", return_value=False),
            patch("devolaflow.plugins.installer.upgrade_plugin") as mock_upgrade,
        ):
            result = pre_plugin_invocation_upgrade({"plugin_id": "ui-pro"}, strict=False)
        assert result.violations == []
        assert mock_upgrade.call_count == 0

        # NON-domain exception from upgrade_plugin → RE-RAISED (S-5), unlike
        # the domain exceptions which downgrade to PPI003 warnings.
        with (
            patch("devolaflow.plugins.installer.is_plugin_stale", return_value=True),
            patch(
                "devolaflow.plugins.installer.upgrade_plugin",
                side_effect=RuntimeError("unexpected boom"),
            ),
            pytest.raises(RuntimeError, match="unexpected boom"),
        ):
            pre_plugin_invocation_upgrade({"plugin_id": "ui-pro"}, strict=False)


# ---------------------------------------------------------------------------
# §5 — 1-cycle deprecation telegraph documented in env-flags.md
# ---------------------------------------------------------------------------


class TestAliasTelegraphedFor1CycleDeprecation:
    """D-C-3 step 7 bullet 5: env-flags.md §2.13 documents alias deprecation."""

    def test_env_flags_doc_documents_alias_deprecation_telegraph(self) -> None:
        """env-flags.md §2.13 row must cite the split + alias deprecation telegraph."""
        env_flags = (_project_root() / "workflow-system/agent/references/env-flags.md").read_text(
            encoding="utf-8"
        )
        # The split MUST be cited.
        assert "pre_plugin_invocation_install" in env_flags, (
            "env-flags.md §2.13 must cite the NEW install handler module"
        )
        assert "pre_plugin_invocation_upgrade" in env_flags, (
            "env-flags.md §2.13 must cite the NEW upgrade handler module"
        )
        # The alias deprecation telegraph MUST be documented.
        assert "Alias deprecation telegraph" in env_flags or (
            "alias deprecation telegraph" in env_flags
        ), "env-flags.md §2.13 must document the v10.8.0 → v12.0.0+ alias deprecation"
        # Positions 11 + 12 cited.
        assert "event slot #11" in env_flags or "position 11" in env_flags.lower()
        assert "event slot #12" in env_flags or "position 12" in env_flags.lower()

    def test_default_events_length_after_split(self) -> None:
        """A-2.2 append-only: DEFAULT_EVENTS grows to AT LEAST 12 entries.

        Positions 11 + 12 carry the two new event constants per D-C-3;
        positions 1-10 remain byte-stable per A-2.4. The SUPERSET
        containment check (``>= 12``) accommodates future APPEND-ONLY
        additions per A-2.2 — e.g., v11.0.0 PV-02 D-Q-3 appends 4 NEW
        canonical event names (positions 13-16) without disturbing
        positions 1-12.
        """
        assert len(DEFAULT_EVENTS) >= 12, (
            f"D-C-3 ships DEFAULT_EVENTS at length 12 (positions 1-12 "
            f"byte-stable); got {len(DEFAULT_EVENTS)}: {list(DEFAULT_EVENTS)}"
        )
        assert DEFAULT_EVENTS[10] == PRE_PLUGIN_INVOCATION_INSTALL_EVENT
        assert DEFAULT_EVENTS[11] == PRE_PLUGIN_INVOCATION_UPGRADE_EVENT
        # Position 9 alias preserved.
        assert DEFAULT_EVENTS[8] == PRE_PLUGIN_INVOCATION_EVENT
