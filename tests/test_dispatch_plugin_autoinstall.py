"""Tests for v9.4.0 PV-03 dispatcher → plugin auto-install wiring.

Closes D-P-2 (the ``ensure_plugin()`` dead-wire ghost) + D-P-6
(``plugins_for_workflow`` helper) from
``.local/research/v9.4.0_gap_analysis.md`` §3.1.

PV-02 shipped the ``pre_plugin_invocation`` lifecycle hook in isolation;
this PV wires the hook into ``feedback.py::ProposalGenerator._emit_dispatch``
so every dispatch automatically pre-flights its plugin candidates. The
acceptance criterion (`v9.4.0_gap_analysis.md` §6 AC-3) requires the
hit-count of ``ensure_plugin`` references in ``src/devolaflow/`` to grow
from 2 (pre-v9.4.0: installer.py + __init__.py) to ≥ 4 (v9.4.0 PV-03:
add lifecycle/pre_plugin_invocation.py + (after this commit) the
test-mocked invocation surface in feedback._emit_dispatch's hook chain).

Test contract (covers the end-to-end wiring + the new helper):

§1 — `plugins_for_workflow` helper resolves registry correctly
§2 — Dispatch with workflow=`skill-optimization` triggers ensure_plugin("si-chip")
§3 — Dispatch with workflow=`product-verification` triggers ensure_plugin("ui-pro")
§4 — Dispatch with no workflow / no plugin candidates → no install
§5 — Env-flag OFF → no install regardless of workflow
§6 — S-10 hook chain still fires on every dispatch (regression guard)
§7 — Empty workflow string is silent no-op (NOT a violation)
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from devolaflow.feedback import ProposalGenerator
from devolaflow.gate.models import GateVerdict
from devolaflow.lifecycle import (
    POST_DISPATCH_EVENT,
    PRE_DISPATCH_EVENT,
    PRE_HANDOFF_EVENT,
    PRE_PLUGIN_INVOCATION_EVENT,
    clear_hooks,
)
from devolaflow.lifecycle.pre_plugin_invocation import (
    ENV_FLAG,
    ENV_FLAG_TRUTHY,
    pre_plugin_invocation,
)
from devolaflow.plugins import plugins_for_workflow

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_extras_and_unset_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each test starts with NO env-flag set + extras cleared."""
    monkeypatch.delenv(ENV_FLAG, raising=False)
    yield
    clear_hooks()


def _base_dispatch_with_workflow(workflow: str | None = None) -> dict:
    """Minimal dispatch payload, optionally citing a workflow."""
    base: dict = {
        "task_id": "T-PV03",
        "task_type": "implement",
        "accept": ["plugin auto-install fires before L3 dispatch"],
        "context": {
            "applicable_rules": {"loading_strategy": "standard"},
            "target_files": ["src/foo.py"],
        },
    }
    if workflow is not None:
        base["workflow"] = workflow
    return base


def _verdict_round1() -> GateVerdict | None:
    """Round-1 dispatch has no prior verdict (pure pass-through path)."""
    return None


# ---------------------------------------------------------------------------
# §1 — `plugins_for_workflow` helper resolves canonical registry
# ---------------------------------------------------------------------------


class TestPluginsForWorkflowHelper:
    """Pin the workflow → plugin resolution against the canonical registry."""

    def test_product_verification_resolves_to_ui_pro(self) -> None:
        ids = plugins_for_workflow("product-verification")
        assert "ui-pro" in ids

    def test_shell_proxy_resolves_to_rtk(self) -> None:
        ids = plugins_for_workflow("shell-proxy")
        assert "rtk" in ids

    def test_unknown_workflow_returns_empty_list(self) -> None:
        assert plugins_for_workflow("nonexistent-workflow") == []

    def test_empty_workflow_returns_empty_list(self) -> None:
        assert plugins_for_workflow("") == []

    def test_non_string_workflow_returns_empty_list(self) -> None:
        # type: ignore[arg-type] - intentionally testing wrong type
        assert plugins_for_workflow(None) == []  # type: ignore[arg-type]
        assert plugins_for_workflow(42) == []  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# §2-5 — End-to-end dispatch → ensure_plugin wiring
# ---------------------------------------------------------------------------


class TestDispatchAutoInstall:
    """The full PV-03 wiring: dispatch with workflow → ensure_plugin called."""

    def test_product_verification_dispatch_triggers_ui_pro(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """v9.4.0 PV-03 baseline: product-verification → [ui-pro].

        v12.5.0 PV-05 D-1.2 update: product-verification now ALSO invokes
        codegraph (workflow wiring per ``plugins.yaml#codegraph.workflows`` +
        ``runtime-plugins.yaml#codegraph.invoked_by_workflows``). Registry
        order: ui-pro first (legacy), codegraph second (v12.5.0 addition).
        """
        monkeypatch.setenv(ENV_FLAG, ENV_FLAG_TRUTHY)
        invocations: list[str] = []

        def fake_ensure(plugin_id: str, **_kw):  # type: ignore[no-untyped-def]
            invocations.append(plugin_id)
            return "2.0.0"

        with patch(
            "devolaflow.plugins.installer.ensure_plugin",
            side_effect=fake_ensure,
        ):
            ProposalGenerator().generate_round_dispatch(
                _base_dispatch_with_workflow("product-verification"),
                _verdict_round1(),
                round_num=1,
            )
        assert invocations == ["ui-pro", "codegraph"], (
            f"v12.5.0 PV-05 contract: product-verification dispatch MUST trigger "
            f"ensure_plugin('ui-pro') AND ensure_plugin('codegraph'); got {invocations!r}"
        )

    def test_dispatch_without_workflow_does_not_install(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Dispatch with no `workflow` field → no auto-install (silent no-op)."""
        monkeypatch.setenv(ENV_FLAG, ENV_FLAG_TRUTHY)
        invocations: list[str] = []

        def fake_ensure(plugin_id: str, **_kw):  # type: ignore[no-untyped-def]
            invocations.append(plugin_id)
            return "0.0.0"

        with patch(
            "devolaflow.plugins.installer.ensure_plugin",
            side_effect=fake_ensure,
        ):
            ProposalGenerator().generate_round_dispatch(
                _base_dispatch_with_workflow(None),
                _verdict_round1(),
                round_num=1,
            )
        assert invocations == [], (
            "dispatch without `workflow` field must not trigger any "
            f"auto-install; got invocations={invocations!r}"
        )

    def test_dispatch_with_unknown_workflow_does_not_install(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Workflow name not in registry → no install (registry returns [])."""
        monkeypatch.setenv(ENV_FLAG, ENV_FLAG_TRUTHY)
        invocations: list[str] = []

        def fake_ensure(plugin_id: str, **_kw):  # type: ignore[no-untyped-def]
            invocations.append(plugin_id)
            return "0.0.0"

        with patch(
            "devolaflow.plugins.installer.ensure_plugin",
            side_effect=fake_ensure,
        ):
            ProposalGenerator().generate_round_dispatch(
                _base_dispatch_with_workflow("nonexistent-workflow"),
                _verdict_round1(),
                round_num=1,
            )
        assert invocations == []

    def test_env_flag_off_does_not_install_even_with_workflow(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """R5 strict: env-flag OFF means no install regardless of workflow."""
        monkeypatch.delenv(ENV_FLAG, raising=False)
        invocations: list[str] = []

        def fake_ensure(plugin_id: str, **_kw):  # type: ignore[no-untyped-def]
            invocations.append(plugin_id)
            return "3.3.0"

        with patch(
            "devolaflow.plugins.installer.ensure_plugin",
            side_effect=fake_ensure,
        ):
            ProposalGenerator().generate_round_dispatch(
                _base_dispatch_with_workflow("skill-optimization"),
                _verdict_round1(),
                round_num=1,
            )
        assert invocations == [], (
            "DEVOLAFLOW_AUTO_INSTALL_PLUGINS unset MUST disable auto-install "
            f"even when workflow=skill-optimization; got invocations={invocations!r}"
        )


# ---------------------------------------------------------------------------
# §6 — S-10 hook chain regression guard (existing chain still fires)
# ---------------------------------------------------------------------------


class TestS10HookChainPreserved:
    """The full 4-event hook chain must still fire on every dispatch path.

    Closes the v9.4.0 PV-03 contract that adding `pre_plugin_invocation`
    does NOT regress the S-10 governance hook chain — every dispatch
    still runs `pre_dispatch` → `post_dispatch` → `pre_handoff` →
    `pre_plugin_invocation` exactly once each in permissive mode.
    """

    def test_full_4_event_chain_fires_on_round1(self) -> None:
        gen = ProposalGenerator()
        events_seen: list[str] = []

        def fake_run_hooks(event, _payload, *, strict=False):  # noqa: ANN001
            events_seen.append(event)

        with patch("devolaflow.lifecycle.run_hooks", side_effect=fake_run_hooks):
            gen.generate_round_dispatch(
                _base_dispatch_with_workflow("skill-optimization"),
                _verdict_round1(),
                round_num=1,
            )
        assert events_seen == [
            PRE_DISPATCH_EVENT,
            POST_DISPATCH_EVENT,
            PRE_HANDOFF_EVENT,
            PRE_PLUGIN_INVOCATION_EVENT,
        ], f"v9.4.0 PV-03 must preserve the S-10 4-event hook chain in order; got {events_seen!r}"


# ---------------------------------------------------------------------------
# §7 — Empty / malformed workflow handling
# ---------------------------------------------------------------------------


class TestWorkflowEdgeCases:
    """Edge cases for the `workflow` field in the dispatch payload."""

    def test_empty_workflow_string_is_silent_noop(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """`workflow: ""` MUST NOT raise / install / produce violations."""
        monkeypatch.setenv(ENV_FLAG, ENV_FLAG_TRUTHY)
        invocations: list[str] = []

        def fake_ensure(plugin_id: str, **_kw):  # type: ignore[no-untyped-def]
            invocations.append(plugin_id)
            return "0.0.0"

        with patch(
            "devolaflow.plugins.installer.ensure_plugin",
            side_effect=fake_ensure,
        ):
            result = pre_plugin_invocation({"workflow": ""})
        assert result.passed is True
        assert invocations == []

    def test_workflow_combined_with_explicit_plugin_id_dedupes(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Explicit si-chip plus skill-optimization deduplicates to one install."""
        monkeypatch.setenv(ENV_FLAG, ENV_FLAG_TRUTHY)
        invocations: list[str] = []

        def fake_ensure(plugin_id: str, **_kw):  # type: ignore[no-untyped-def]
            invocations.append(plugin_id)
            return "3.3.0"

        with patch(
            "devolaflow.plugins.installer.ensure_plugin",
            side_effect=fake_ensure,
        ):
            pre_plugin_invocation({"workflow": "skill-optimization", "plugin_id": "si-chip"})
        assert invocations == ["si-chip"]

    def test_explicit_plugin_id_runs_first_workflow_appended(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """plugin_ids merged with workflow-resolved IDs preserves explicit-first order.

        Explicit plugin_ids=["rtk"] comes first; workflow-resolved IDs follow.
        """
        monkeypatch.setenv(ENV_FLAG, ENV_FLAG_TRUTHY)
        invocations: list[str] = []

        def fake_ensure(plugin_id: str, **_kw):  # type: ignore[no-untyped-def]
            invocations.append(plugin_id)
            return "1.0.0"

        with patch(
            "devolaflow.plugins.installer.ensure_plugin",
            side_effect=fake_ensure,
        ):
            pre_plugin_invocation(
                {
                    "plugin_ids": ["rtk"],
                    "workflow": "skill-optimization",  # resolves to si-chip
                }
            )
        # plugin_ids comes first (explicit), workflow-resolved IDs second (in registry order)
        assert invocations == ["rtk", "si-chip"]
