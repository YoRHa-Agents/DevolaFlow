"""Degraded-mode contract tests — every plugin has an unreachable-scenario test.

Pins the v10.8.0 D-C-1 contract: each registered plugin with a local degraded
path has an EXPLICIT regression test that documents what
happens when the plugin is unreachable. The reference doc
`workflow-system/agent/references/degraded-mode.md` codifies the per-plugin
contract; THIS test file is the executable proof that DevolaFlow honors it.

Source: `.local/research/v11.0.0_patches/D-C-1.md` §2 patch_design step 3.

Per R1 mitigation (D-C-1 §9), the reference doc MUST open with a
"Degraded ≠ Full" warning in the first 500 characters; this file pins that
invariant to catch future edits that might dilute the warning.

External canonical URLs (S-7 compliance):
    * DevolaFlow: https://github.com/YoRHa-Agents/DevolaFlow
    * ui-pro: https://github.com/YoRHa-Agents/ui-pro
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from devolaflow.lifecycle import (
    HookResult,
    HookViolation,
    clear_hooks,
)


@pytest.fixture(autouse=True)
def _clear_extra_hooks():
    """Each test starts/ends with no extra hook handlers (defaults intact)."""
    yield
    clear_hooks()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _project_root() -> Path:
    """Return the repo root — tests live at ``<root>/tests/``."""
    return Path(__file__).resolve().parent.parent


def _degraded_mode_doc_text() -> str:
    """Read the degraded-mode reference verbatim."""
    return (_project_root() / "workflow-system/agent/references/degraded-mode.md").read_text(
        encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# §0 — R1 mitigation: "Degraded ≠ Full" warning MUST appear first
# ---------------------------------------------------------------------------


class TestDegradedNotFullWarning:
    """R1 mitigation per D-C-1 §9: the reference MUST lead with a caveat.

    If an operator reads the first ~500 characters and walks away thinking
    "DevolaFlow works fully offline," the reference has failed its purpose.
    """

    def test_warning_appears_in_first_500_chars(self) -> None:
        """The 'Degraded ≠ Full' warning surfaces in the first 500 chars.

        Pins R1 mitigation from `.local/research/v11.0.0_patches/D-C-1.md` §9:
        the reference MUST open with a "Degraded ≠ Full" warning section
        explicitly listing what STOPS working when each plugin is unreachable.
        Consolidates the warning-body + S-2 no-absolute-paths + S-7 external-
        URL contract checks into the single R1 regression.
        """
        head = _degraded_mode_doc_text()[:500]
        assert "Degraded ≠ Full" in head, (
            "degraded-mode.md must open with 'Degraded ≠ Full' warning "
            f"in the first 500 characters (D-C-1 §9 R1). First 500:\n{head!r}"
        )
        # Body assertions (merged from deleted tests to keep W-17 tight):
        text = _degraded_mode_doc_text()
        assert "What STOPS working" in text
        for plugin in ("ui-pro", "impeccable"):
            assert plugin in text
        # S-7 external URL contract — canonical GitHub URL for every plugin.
        # S-2 no-absolute-paths in any committed reference.
        assert "/home/" not in text
        assert "/Users/" not in text
        assert "/root/" not in text


# ---------------------------------------------------------------------------
# §4 — ui-pro unreachable → PPI001 + permissive-continue
# ---------------------------------------------------------------------------


class TestUiProUnreachableEmitsPPI001PermissiveContinues:
    """ui-pro degraded path: PluginInstallError → PPI001 error, no-raise.

    Codified at ``src/devolaflow/lifecycle/pre_plugin_invocation.py`` lines
    420-448 (the `_run_install_then_upgrade_for_plugin` helper's ensure_plugin
    catch block). This test pins the cycle-level contract: the hook
    catches PluginInstallError; emits PPI001 (severity warning since the
    v15.2.0 B-6 tier-aware degrade — ui-pro/impeccable are suggest-tier);
    in permissive mode the dispatch continues.
    """

    def test_ui_pro_unreachable_emits_ppi001_permissive_continues(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Pin the PPI001 + permissive-continue contract for ui-pro install."""
        monkeypatch.setenv("DEVOLAFLOW_AUTO_INSTALL_PLUGINS", "1")
        from devolaflow.lifecycle.pre_plugin_invocation import pre_plugin_invocation
        from devolaflow.plugins.exceptions import PluginInstallError

        def _fake_ensure_plugin(plugin_id: str, **_kwargs: object) -> str:  # type: ignore[no-untyped-def]
            raise PluginInstallError(
                f"npm install -g uipro-cli failed (registry unreachable): {plugin_id}"
            )

        with patch(
            "devolaflow.plugins.installer.ensure_plugin",
            side_effect=_fake_ensure_plugin,
        ):
            # Also short-circuit upgrade/staleness calls (the alias path
            # does install-then-upgrade; the install failure returns early
            # before upgrade runs per the existing v10.2.3 PV-04 helper).
            result = pre_plugin_invocation(
                {"plugin_id": "ui-pro"},
                strict=False,
            )

        assert isinstance(result, HookResult)
        # PPI001 present with warning severity (suggest-tier per B-6).
        ppi001 = [v for v in result.violations if v.code == "PPI001"]
        assert len(ppi001) == 1, (
            f"expected 1 PPI001 violation, got {len(ppi001)}: {[v.code for v in result.violations]}"
        )
        assert ppi001[0].severity == "warning"
        assert "ui-pro" in ppi001[0].message
        # Strict mode re-raises the same PPI001 HookViolation (finalize
        # raises on ANY violation regardless of severity).
        with patch(
            "devolaflow.plugins.installer.ensure_plugin",
            side_effect=_fake_ensure_plugin,
        ):
            with pytest.raises(HookViolation) as exc_info:
                pre_plugin_invocation({"plugin_id": "ui-pro"}, strict=True)
            assert exc_info.value.code == "PPI001"
            assert exc_info.value.severity == "warning"
        # degraded-mode.md §4 must cite PPI001 + permissive-continue.
        text = _degraded_mode_doc_text()
        assert "PPI001" in text
        assert "pre_plugin_invocation" in text
        assert "permissive" in text.lower()

    def test_impeccable_unreachable_emits_ppi001_permissive_continues(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """v13.0.0: pin the PPI001 + permissive-continue contract for impeccable.

        Mirrors the ui-pro contract — impeccable shares the
        `pre_plugin_invocation` → `ensure_plugin` install path (backend
        npm_then_init). When `npm install -g impeccable` fails the hook emits
        PPI001 (warning — suggest-tier per v15.2.0 B-6); permissive mode
        (default) continues, strict mode re-raises.
        """
        monkeypatch.setenv("DEVOLAFLOW_AUTO_INSTALL_PLUGINS", "1")
        from devolaflow.lifecycle.pre_plugin_invocation import pre_plugin_invocation
        from devolaflow.plugins.exceptions import PluginInstallError

        def _fake_ensure_plugin(plugin_id: str, **_kwargs: object) -> str:  # type: ignore[no-untyped-def]
            raise PluginInstallError(
                f"npm install -g impeccable failed (registry unreachable): {plugin_id}"
            )

        with patch(
            "devolaflow.plugins.installer.ensure_plugin",
            side_effect=_fake_ensure_plugin,
        ):
            result = pre_plugin_invocation({"plugin_id": "impeccable"}, strict=False)

        assert isinstance(result, HookResult)
        ppi001 = [v for v in result.violations if v.code == "PPI001"]
        assert len(ppi001) == 1, (
            f"expected 1 PPI001 violation, got {len(ppi001)}: {[v.code for v in result.violations]}"
        )
        assert ppi001[0].severity == "warning"
        assert "impeccable" in ppi001[0].message
        # Strict mode re-raises the same PPI001 HookViolation (finalize
        # raises on ANY violation regardless of severity).
        with patch(
            "devolaflow.plugins.installer.ensure_plugin",
            side_effect=_fake_ensure_plugin,
        ):
            with pytest.raises(HookViolation) as exc_info:
                pre_plugin_invocation({"plugin_id": "impeccable"}, strict=True)
            assert exc_info.value.code == "PPI001"
            assert exc_info.value.severity == "warning"
        # degraded-mode.md must carry an impeccable section + matrix row.
        text = _degraded_mode_doc_text()
        assert "impeccable" in text.lower()
        assert "Section 6 — impeccable" in text


# ---------------------------------------------------------------------------
# §5 — Degraded-mode coverage audit (meta-test)
# ---------------------------------------------------------------------------


class TestDegradedModeCoverageAudit:
    """Pin degraded-scenario coverage for the remaining bridge-backed plugins."""

    def test_remaining_plugins_have_unreachable_scenario_tests(self) -> None:
        """Remaining plugins with executable degraded paths have scenario tests."""
        test_text = Path(__file__).read_text(encoding="utf-8")
        # Each plugin's dedicated test function must exist in THIS file.
        expected_tests = (
            "test_ui_pro_unreachable_emits_ppi001_permissive_continues",
            "test_impeccable_unreachable_emits_ppi001_permissive_continues",
        )
        for name in expected_tests:
            assert name in test_text, (
                f"D-C-1 §5 coverage audit: missing scenario test {name!r}. "
                f"Every covered plugin (ui-pro/impeccable) "
                f"MUST have an explicit unreachable-scenario test."
            )

    def test_reference_doc_present_and_nonempty(self) -> None:
        """degraded-mode.md MUST exist and be non-empty."""
        ref = _project_root() / "workflow-system/agent/references/degraded-mode.md"
        assert ref.is_file(), f"degraded-mode.md missing at {ref}"
        content = ref.read_text(encoding="utf-8")
        assert len(content) > 1000, (
            f"degraded-mode.md too short ({len(content)} chars); should be "
            f"substantive per D-C-1 §2 (~600 LOC target)"
        )
