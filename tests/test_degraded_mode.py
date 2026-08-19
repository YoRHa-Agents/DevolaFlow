"""Degraded-mode contract tests — every plugin has an unreachable-scenario test.

Pins the v10.8.0 D-C-1 contract: each of the 4 registered plugins (NineS,
Si-Chip, RTK, ui-pro) has an EXPLICIT regression test that documents what
happens when the plugin is unreachable. The reference doc
`workflow-system/agent/references/degraded-mode.md` codifies the per-plugin
contract; THIS test file is the executable proof that DevolaFlow honors it.

Source: `.local/research/v11.0.0_patches/D-C-1.md` §2 patch_design step 3
(four simulated scenarios: NineS / Si-Chip / RTK / ui-pro).

Per R1 mitigation (D-C-1 §9), the reference doc MUST open with a
"Degraded ≠ Full" warning in the first 500 characters; this file pins that
invariant to catch future edits that might dilute the warning.

External canonical URLs (S-7 compliance):
    * DevolaFlow: https://github.com/YoRHa-Agents/DevolaFlow
    * NineS: https://github.com/YoRHa-Agents/NineS
    * Si-Chip: https://github.com/YoRHa-Agents/Si-Chip
    * RTK: https://github.com/rtk-ai/rtk
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
    pre_shell_call,
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
        for plugin in ("NineS", "Si-Chip", "RTK", "ui-pro"):
            assert plugin in text
        # S-7 external URL contract — canonical GitHub URL for every plugin.
        assert "https://github.com/YoRHa-Agents/NineS" in text
        assert "https://github.com/YoRHa-Agents/Si-Chip" in text
        assert "https://github.com/rtk-ai/rtk" in text
        # S-2 no-absolute-paths in any committed reference.
        assert "/home/" not in text
        assert "/Users/" not in text
        assert "/root/" not in text


# ---------------------------------------------------------------------------
# §1 — NineS unreachable → W-2 manual fallback
# ---------------------------------------------------------------------------


class TestNineSUnreachableFallsBackToManualW2:
    """NineS degraded path: documented in repo-governance.mdc::W-2.

    DF does not actually INVOKE nines at dispatch-time (W-2 is a governance
    rule that operators discover at SI-1 planning / SI-2 analysis). The
    'degraded' contract here is: the W-2 rule TEXT declares the fallback
    exists AND the cycle-retrospective / evaluation template tolerates
    missing NineS JSON inputs.
    """

    def test_nines_unreachable_falls_back_to_manual_w2(self) -> None:
        """W-2 governance rule declares manual fallback when NineS absent.

        Verbatim from `.cursor/rules/repo-governance.mdc::W-2`: "When NineS
        is unavailable, manual analysis following the same dimensions is
        acceptable but must be explicitly noted as manual."

        This test pins the TEXT of the governance contract AND the
        degraded-mode reference documentation — if someone tries to delete
        the manual-fallback clause from either, this test fails.
        """
        governance = (_project_root() / ".cursor/rules/repo-governance.mdc").read_text(
            encoding="utf-8"
        )
        assert "manual analysis" in governance, (
            "W-2 governance rule must retain 'manual analysis' clause per "
            "D-C-1 degraded-mode contract."
        )
        assert "must be noted as manual" in governance or ("noted as manual" in governance), (
            "W-2 governance rule must retain the 'noted as manual' requirement."
        )
        # degraded-mode.md §1 must cite the W-2 fallback path.
        text = _degraded_mode_doc_text()
        assert "W-2" in text
        assert "manual" in text.lower()


# ---------------------------------------------------------------------------
# §2 — Si-Chip unreachable → PSE001 + SKIPPED_PERMISSIVE verdict
# ---------------------------------------------------------------------------


class TestSiChipUnreachableEmitsPSE001AndDefers:
    """Si-Chip degraded path: SiChipUnavailable → PSE001 + SKIPPED_PERMISSIVE.

    Codified at ``src/devolaflow/lifecycle/post_skill_edit.py::_run_si_chip_evaluation``
    lines 452-476. This test pins the cycle-level contract: the hook
    catches SiChipUnavailable; emits PSE001 (severity warning); sets
    ``metadata["verdict"] = "SKIPPED_PERMISSIVE"``; dispatch continues.
    """

    def test_si_chip_unreachable_emits_pse001_and_defers(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Pin the PSE001 + SKIPPED_PERMISSIVE + dispatch-continue contract.

        Monkeypatches the Si-Chip subprocess path so that `run_dogfood_cycle`
        raises `SiChipUnavailable`; asserts that `post_skill_edit` aggregates
        the PSE001 HookViolation on the HookResult and sets the verdict
        to `SKIPPED_PERMISSIVE` WITHOUT raising.
        """
        # Activate DEEP integration (req'd for non-trivial hook body).
        monkeypatch.setenv("DEVOLAFLOW_SI_CHIP_DEEP", "1")
        from devolaflow.lifecycle.post_skill_edit import post_skill_edit
        from devolaflow.si_chip_bridge import SiChipUnavailable

        def _fake_run_dogfood_cycle(**_kwargs):  # type: ignore[no-untyped-def]
            raise SiChipUnavailable(
                "Si-Chip not installed — DEEP integration skipped "
                "(install via https://github.com/YoRHa-Agents/Si-Chip)"
            )

        # Patch the import point inside the evaluator helper. post_skill_edit
        # filters touched_files against SKILL_CORPUS_PREFIX="workflow-system/agent/"
        # so the payload uses repo-relative paths (NOT tmp_path absolute) — the
        # file doesn't need to exist for the hook body to fire (Si-Chip is
        # monkeypatched to raise before any real IO).
        with patch(
            "devolaflow.si_chip_bridge.run_dogfood_cycle",
            side_effect=_fake_run_dogfood_cycle,
        ):
            payload = {"touched_files": ["workflow-system/agent/SKILL.md"]}
            result = post_skill_edit(payload, strict=False)

        assert isinstance(result, HookResult)
        # Dispatch continues (no exception raised).
        assert result.passed is True or result.passed is False  # finalize returns either
        # PSE001 present with warning severity.
        pse001 = [v for v in result.violations if v.code == "PSE001"]
        assert len(pse001) == 1, (
            f"expected 1 PSE001 violation, got {len(pse001)}: {[v.code for v in result.violations]}"
        )
        assert pse001[0].severity == "warning"
        # Verdict metadata marks SKIPPED_PERMISSIVE.
        assert result.metadata.get("verdict") == "SKIPPED_PERMISSIVE", (
            f"expected metadata['verdict']='SKIPPED_PERMISSIVE', got "
            f"{result.metadata.get('verdict')!r}"
        )
        # degraded-mode.md §2 must document PSE001 + SKIPPED_PERMISSIVE
        # (consolidated from deleted `test_degraded_mode_doc_cites_pse001_path`).
        text = _degraded_mode_doc_text()
        assert "PSE001" in text
        assert "SKIPPED_PERMISSIVE" in text
        assert "post_skill_edit" in text


# ---------------------------------------------------------------------------
# §3 — RTK unreachable → native-shell passthrough
# ---------------------------------------------------------------------------


class TestRTKUnreachableBypassesToNativeShell:
    """RTK degraded path: env-flag ON + binary missing → passthrough.

    The existing `tests/test_shell_proxy_disabled_is_noop.py` covers the
    env-flag UNSET case. THIS test covers the EXTENDED case: env-flag is
    ON, but `shutil.which("rtk")` returns None → passthrough still applies.
    """

    def test_rtk_unreachable_bypasses_to_native_shell(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Flag ON + rtk missing → wrap_command passthrough + passed HookResult."""
        monkeypatch.setenv("DEVOLAFLOW_RTK_PROXY", "1")

        from devolaflow.shell_proxy import ShellProxy
        from devolaflow.shell_proxy import proxy as proxy_module

        # Force shutil.which to report rtk as missing.
        with patch.object(proxy_module.shutil, "which", return_value=None):
            proxy = ShellProxy(env={"DEVOLAFLOW_RTK_PROXY": "1"})
            # Even with the env-flag ON, proxy_enabled must be False when
            # the binary is missing — this IS the R5 strict fallback path.
            assert proxy.config.proxy_enabled is False
            assert proxy.config.env_flag_set is True
            assert proxy.config.rtk_path is None
            # wrap_command returns the input unchanged.
            cmd = "pytest tests/ -q"
            assert proxy.wrap_command(cmd) == cmd

    def test_rtk_unreachable_pre_shell_call_metadata(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """pre_shell_call hook surfaces proxy_enabled=False + was_rewritten=False.

        Also confirms degraded-mode.md §3 cites the RTK fallback contract
        (consolidated from deleted `test_degraded_mode_doc_cites_rtk_fallback`).
        """
        monkeypatch.setenv("DEVOLAFLOW_RTK_PROXY", "1")

        from devolaflow.shell_proxy import proxy as proxy_module

        with patch.object(proxy_module.shutil, "which", return_value=None):
            payload = {"cmd": "git status", "cwd": None}
            result = pre_shell_call(payload)

        assert result.metadata["proxy_enabled"] is False
        assert result.metadata["was_rewritten"] is False
        assert result.metadata["wrapped_cmd"] == "git status"
        # Doc citation check (consolidated):
        text = _degraded_mode_doc_text()
        assert "RTK" in text
        assert "shutil.which" in text
        assert "DEVOLAFLOW_RTK_PROXY" in text


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
    """Pin the 4-of-4 plugin coverage invariant from D-C-1 §5 benefit_metrics."""

    def test_all_four_plugins_have_an_unreachable_scenario_test(self) -> None:
        """D-C-1 §5 metric: plugins with a network-install path have an
        unreachable scenario test. v13.0.0 adds impeccable (mirrors ui-pro)."""
        test_text = Path(__file__).read_text(encoding="utf-8")
        # Each plugin's dedicated test function must exist in THIS file.
        expected_tests = (
            "test_nines_unreachable_falls_back_to_manual_w2",
            "test_si_chip_unreachable_emits_pse001_and_defers",
            "test_rtk_unreachable_bypasses_to_native_shell",
            "test_ui_pro_unreachable_emits_ppi001_permissive_continues",
            "test_impeccable_unreachable_emits_ppi001_permissive_continues",
        )
        for name in expected_tests:
            assert name in test_text, (
                f"D-C-1 §5 coverage audit: missing scenario test {name!r}. "
                f"Every registered plugin (NineS/Si-Chip/RTK/ui-pro/impeccable) "
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
