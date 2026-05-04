"""Tests for the v9.4.0 PV-02 ``pre_plugin_invocation`` lifecycle hook.

Pins the contract in :mod:`devolaflow.lifecycle.pre_plugin_invocation`:

1. **Event registered** — ``DEFAULT_EVENTS`` includes
   ``pre_plugin_invocation`` at position 9 (A-2.2 append-only).
2. **R5 strict env-flag** — ``DEVOLAFLOW_AUTO_INSTALL_PLUGINS=1`` exact
   match; rejects loose values; default-OFF.
3. **Disabled is no-op + byte-identical** — when env-flag OFF, the
   handler returns a clean :class:`HookResult` with zero filesystem IO
   and zero subprocess work (lazy-import of installer module proves
   the cold-path import is not triggered).
4. **Payload extraction** — supports both ``plugin_id: str`` and
   ``plugin_ids: list[str]`` shapes; deduplicates; preserves order.
5. **Schema malformed** — non-string / empty entries surface as PPI002
   warnings (not errors; permissive default).
6. **Install delegated** — when env-flag ON + payload populated, calls
   ``ensure_plugin`` for each ID; aggregates failures as PPI001 errors.
7. **Permissive default never crashes** — domain exceptions captured;
   strict mode re-raises top-severity violation.

Source: `.local/research/v9.4.0_gap_analysis.md` §3.1 D-P-1 + D-P-3 +
§6 AC-1 / AC-2 / AC-6.
"""

from __future__ import annotations

import sys
from unittest.mock import patch

import pytest

from devolaflow.lifecycle import (
    DEFAULT_EVENTS,
    PRE_PLUGIN_INVOCATION_EVENT,
    HookResult,
    HookViolation,
    clear_hooks,
)
from devolaflow.lifecycle.pre_plugin_invocation import (
    ENV_FLAG,
    ENV_FLAG_TRUTHY,
    EVENT,
    EVENT_TRIGGERS_DAILY_UPGRADE,
    is_auto_install_active,
    pre_plugin_invocation,
)
from devolaflow.plugins.exceptions import (
    PluginInstallError,
    PluginNotFoundError,
    PluginVersionMismatch,
)


@pytest.fixture(autouse=True)
def _clear_extra_hooks():
    """Each test starts/ends with no extra hook handlers (defaults intact)."""
    yield
    clear_hooks()


# ---------------------------------------------------------------------------
# §1 — Event registration (A-2.2 append-only at position 9)
# ---------------------------------------------------------------------------


class TestEventRegistration:
    """Pin the canonical event name + DEFAULT_EVENTS membership at pos 9."""

    def test_event_constant_matches(self) -> None:
        assert EVENT == "pre_plugin_invocation"
        assert PRE_PLUGIN_INVOCATION_EVENT == EVENT

    def test_event_in_default_events(self) -> None:
        """A-2.2: pre_plugin_invocation APPENDED at the END of DEFAULT_EVENTS at pos 9.

        v9.4.0 PV-02 bumped 8 → 9 with this event at the tail. The
        v9.5.0 PV-04 cycle bumped 9 → 10 with post_skill_edit appended
        AFTER pre_plugin_invocation (A-2.2 append-only). This test now
        relaxes the strict ``== 9`` to ``>= 9`` and asserts the
        position-9 slot remains pre_plugin_invocation (frozen per
        A-2.4 cache-prefix invariant).
        """
        assert PRE_PLUGIN_INVOCATION_EVENT in DEFAULT_EVENTS
        assert len(DEFAULT_EVENTS) >= 9, (
            f"DEFAULT_EVENTS bumped 8 → 9 in v9.4.0 PV-02 "
            f"(was {len(DEFAULT_EVENTS)}); A-2.2 append-only invariant "
            f"requires this slot to remain at position 9 (1-indexed)"
        )
        # Position 9 (1-indexed) — index 8 — MUST be pre_plugin_invocation
        # per the v9.4.0 PV-02 frozen tail. Future appends (post_skill_edit
        # at pos 10 in v9.5.0 PV-04) extend AFTER this slot.
        assert DEFAULT_EVENTS[8] == PRE_PLUGIN_INVOCATION_EVENT, (
            f"PRE_PLUGIN_INVOCATION_EVENT must remain at 1-indexed "
            f"position 9 (DEFAULT_EVENTS[8]) per A-2.4 cache-prefix "
            f"invariant. Actual position-9: {DEFAULT_EVENTS[8]!r}"
        )

    def test_canonical_8_event_prefix_unchanged(self) -> None:
        """A-2.4 cache-prefix invariant: positions 1-8 byte-stable since v9.1.3."""
        assert DEFAULT_EVENTS[:8] == (
            "pre_dispatch",
            "post_dispatch",
            "file_write",
            "task_stop",
            "format_on_edit",
            "pre_shell_call",
            "envelope_write",
            "pre_handoff",
        )


# ---------------------------------------------------------------------------
# §2 — R5 strict env-flag parsing
# ---------------------------------------------------------------------------


class TestEnvFlagR5Strict:
    """Pin the env-flag parsing: literal "1" only; everything else falls through."""

    def test_env_flag_literal_one_active(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(ENV_FLAG, ENV_FLAG_TRUTHY)
        assert is_auto_install_active() is True

    @pytest.mark.parametrize(
        "value",
        [
            "true",
            "yes",
            "on",
            "01",
            "1\n",
            " 1",
            "1 ",
            "0",
            "TRUE",
            "True",
            "",
        ],
    )
    def test_env_flag_loose_values_rejected(
        self, monkeypatch: pytest.MonkeyPatch, value: str
    ) -> None:
        monkeypatch.setenv(ENV_FLAG, value)
        assert is_auto_install_active() is False, (
            f"R5 strict requires literal '1' only; rejected value {value!r}"
        )

    def test_env_flag_unset_disabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(ENV_FLAG, raising=False)
        assert is_auto_install_active() is False


# ---------------------------------------------------------------------------
# §3 — Disabled is no-op + byte-identical (the R5 strict zero-IO invariant)
# ---------------------------------------------------------------------------


class TestDisabledIsNoopByteIdentical:
    """When env-flag OFF, the hook MUST return cleanly with zero side-effects.

    The lazy-import contract (no `devolaflow.plugins.installer` import in
    the disabled path) is the strongest evidence we can offer that the
    R5 strict zero-IO invariant holds: if the cold-path module weren't
    loaded, no `ensure_plugin` ever ran, no subprocess spawned, no log
    written.
    """

    def test_disabled_returns_clean_hook_result(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(ENV_FLAG, raising=False)
        result = pre_plugin_invocation({"plugin_id": "nines"})
        assert isinstance(result, HookResult)
        assert result.passed is True
        assert result.violations == []

    def test_disabled_is_noop_byte_identical(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """R5 strict: disabled invocation MUST NOT import the installer module.

        If the env-flag-off path is truly zero-IO, the handler returns
        BEFORE the lazy-import. We prove this by patching ensure_plugin
        with a watcher that records every invocation — when the flag is
        unset, the watcher must never fire even with a populated payload.
        """
        monkeypatch.delenv(ENV_FLAG, raising=False)
        invocations: list[str] = []

        def watcher(plugin_id: str, **_kw):  # type: ignore[no-untyped-def]
            invocations.append(plugin_id)
            return "0.0.0"

        with patch(
            "devolaflow.plugins.installer.ensure_plugin",
            side_effect=watcher,
        ):
            for payload in (
                {"plugin_id": "nines"},
                {"plugin_ids": ["nines", "ui-pro", "rtk"]},
                {"plugin_id": "nines", "plugin_ids": ["ui-pro"]},
            ):
                result = pre_plugin_invocation(payload)
                assert result.passed is True
                assert result.violations == []
        assert invocations == [], (
            "ensure_plugin must NEVER fire when DEVOLAFLOW_AUTO_INSTALL_PLUGINS "
            "is unset — the lazy-import + early-return path failed"
        )

    def test_non_dict_payload_disabled_still_no_op(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(ENV_FLAG, raising=False)
        for payload in (None, [], "garbage", 42):
            result = pre_plugin_invocation(payload)  # type: ignore[arg-type]
            assert result.passed is True

    def test_no_plugin_candidates_is_silent_noop_when_enabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Gate 2: env-flag ON + empty payload → silent no-op (not an error)."""
        monkeypatch.setenv(ENV_FLAG, ENV_FLAG_TRUTHY)
        invocations: list[str] = []

        def watcher(plugin_id: str, **_kw):  # type: ignore[no-untyped-def]
            invocations.append(plugin_id)
            return "0.0.0"

        with patch(
            "devolaflow.plugins.installer.ensure_plugin",
            side_effect=watcher,
        ):
            result = pre_plugin_invocation({})
            assert result.passed is True
            assert invocations == []


# ---------------------------------------------------------------------------
# §4 — Active path: install delegation
# ---------------------------------------------------------------------------


class TestActiveDelegation:
    """When env-flag ON + payload populated, `ensure_plugin` is called per ID."""

    def test_single_plugin_id_invokes_ensure_plugin(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(ENV_FLAG, ENV_FLAG_TRUTHY)
        invocations: list[str] = []

        def fake_ensure(plugin_id: str, **_kw):  # type: ignore[no-untyped-def]
            invocations.append(plugin_id)
            return "3.3.0"

        with (
            patch(
                "devolaflow.plugins.installer.ensure_plugin",
                side_effect=fake_ensure,
            ),
            patch(
                "devolaflow.plugins.installer.is_plugin_stale",
                return_value=False,
            ),
        ):
            result = pre_plugin_invocation({"plugin_id": "nines"})
        assert invocations == ["nines"]
        assert result.passed is True
        assert result.violations == []

    def test_plugin_ids_list_invokes_ensure_plugin_per_id_in_order(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ENV_FLAG, ENV_FLAG_TRUTHY)
        invocations: list[str] = []

        def fake_ensure(plugin_id: str, **_kw):  # type: ignore[no-untyped-def]
            invocations.append(plugin_id)
            return "1.0.0"

        with (
            patch(
                "devolaflow.plugins.installer.ensure_plugin",
                side_effect=fake_ensure,
            ),
            patch(
                "devolaflow.plugins.installer.is_plugin_stale",
                return_value=False,
            ),
        ):
            result = pre_plugin_invocation({"plugin_ids": ["nines", "ui-pro", "rtk"]})
        assert invocations == ["nines", "ui-pro", "rtk"], (
            "list iteration must preserve insertion order"
        )
        assert result.passed is True

    def test_dedup_preserves_order(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Mixed plugin_id + plugin_ids dedup but preserve first-seen order."""
        monkeypatch.setenv(ENV_FLAG, ENV_FLAG_TRUTHY)
        invocations: list[str] = []

        def fake_ensure(plugin_id: str, **_kw):  # type: ignore[no-untyped-def]
            invocations.append(plugin_id)
            return "1.0.0"

        with (
            patch(
                "devolaflow.plugins.installer.ensure_plugin",
                side_effect=fake_ensure,
            ),
            patch(
                "devolaflow.plugins.installer.is_plugin_stale",
                return_value=False,
            ),
        ):
            pre_plugin_invocation(
                {"plugin_ids": ["nines", "ui-pro", "nines"], "plugin_id": "ui-pro"}
            )
        assert invocations == ["nines", "ui-pro"], (
            f"duplicates must be removed while preserving first-seen order; got {invocations!r}"
        )


# ---------------------------------------------------------------------------
# §5 — Failure handling: PPI001 install errors + PPI002 schema warnings
# ---------------------------------------------------------------------------


class TestFailureHandling:
    """Domain exceptions become PPI001 errors; schema problems become PPI002."""

    def test_plugin_install_error_becomes_ppi001(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(ENV_FLAG, ENV_FLAG_TRUTHY)

        def boom(plugin_id: str, **_kw):  # type: ignore[no-untyped-def]
            raise PluginInstallError(
                f"network unreachable for {plugin_id!r}",
                details={"plugin_id": plugin_id, "url": "https://example.com"},
            )

        with patch(
            "devolaflow.plugins.installer.ensure_plugin",
            side_effect=boom,
        ):
            result = pre_plugin_invocation({"plugin_id": "nines"})
        assert result.passed is False
        assert len(result.violations) == 1
        violation = result.violations[0]
        assert violation.code == "PPI001"
        assert violation.severity == "error"
        assert "nines" in violation.message
        assert "PluginInstallError" in violation.message
        assert violation.context["plugin_id"] == "nines"

    def test_plugin_not_found_error_becomes_ppi001(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(ENV_FLAG, ENV_FLAG_TRUTHY)

        def boom(plugin_id: str, **_kw):  # type: ignore[no-untyped-def]
            raise PluginNotFoundError(
                f"no such plugin {plugin_id!r}", details={"plugin_id": plugin_id}
            )

        with patch(
            "devolaflow.plugins.installer.ensure_plugin",
            side_effect=boom,
        ):
            result = pre_plugin_invocation({"plugin_id": "missing"})
        assert result.passed is False
        assert result.violations[0].code == "PPI001"

    def test_schema_violation_becomes_ppi002_warning(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(ENV_FLAG, ENV_FLAG_TRUTHY)
        # plugin_ids must be a list, not a string
        result = pre_plugin_invocation({"plugin_ids": "nines"})
        assert result.passed is False
        ppi002 = [v for v in result.violations if v.code == "PPI002"]
        assert len(ppi002) == 1
        assert ppi002[0].severity == "warning"

    def test_aggregates_multi_install_failures(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Each failing plugin contributes one PPI001; processing continues."""
        monkeypatch.setenv(ENV_FLAG, ENV_FLAG_TRUTHY)
        seen: list[str] = []

        def maybe_boom(plugin_id: str, **_kw):  # type: ignore[no-untyped-def]
            seen.append(plugin_id)
            if plugin_id == "ui-pro":
                raise PluginVersionMismatch(
                    f"{plugin_id} below floor", details={"plugin_id": plugin_id}
                )
            return "1.0.0"

        with patch(
            "devolaflow.plugins.installer.ensure_plugin",
            side_effect=maybe_boom,
        ):
            result = pre_plugin_invocation({"plugin_ids": ["nines", "ui-pro", "rtk"]})
        # All three plugins were attempted, even after ui-pro failed.
        assert seen == ["nines", "ui-pro", "rtk"]
        assert result.passed is False
        ppi001 = [v for v in result.violations if v.code == "PPI001"]
        assert len(ppi001) == 1
        assert ppi001[0].context["plugin_id"] == "ui-pro"

    def test_strict_mode_raises_top_severity_violation(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ENV_FLAG, ENV_FLAG_TRUTHY)

        def boom(plugin_id: str, **_kw):  # type: ignore[no-untyped-def]
            raise PluginInstallError(f"strict-mode test for {plugin_id!r}")

        with (
            patch(
                "devolaflow.plugins.installer.ensure_plugin",
                side_effect=boom,
            ),
            pytest.raises(HookViolation) as exc_info,
        ):
            pre_plugin_invocation({"plugin_id": "nines"}, strict=True)
        assert exc_info.value.code == "PPI001"
        assert exc_info.value.severity == "error"

    def test_unexpected_exception_reraised_per_s5(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """S-5: non-domain exceptions are logged loudly AND re-raised."""
        monkeypatch.setenv(ENV_FLAG, ENV_FLAG_TRUTHY)

        def kaboom(plugin_id: str, **_kw):  # type: ignore[no-untyped-def]
            raise OSError("disk full")

        with (
            patch(
                "devolaflow.plugins.installer.ensure_plugin",
                side_effect=kaboom,
            ),
            pytest.raises(OSError, match="disk full"),
        ):
            pre_plugin_invocation({"plugin_id": "nines"})


# ---------------------------------------------------------------------------
# §6 — Lazy-import contract (cold-path proof of zero-IO when disabled)
# ---------------------------------------------------------------------------


def test_lazy_import_contract_module_load_is_cheap() -> None:
    """The hook module must NOT pull in installer/exceptions at import time.

    The lazy-import inside ``pre_plugin_invocation`` is a load-bearing
    optimisation — without it, every dispatch (even when env-flag OFF)
    would import the 1030-LOC installer module, defeating the R5 strict
    zero-IO invariant. We can't unimport modules already loaded by other
    tests, but we CAN inspect the module source to confirm it does NOT
    statically reference the installer.
    """
    # Resolve the module via sys.modules — the symbol-import at the top of
    # this test file (`from devolaflow.lifecycle.pre_plugin_invocation
    # import pre_plugin_invocation`) shadows the module name with the
    # function, so a re-`import` would also bind the function. The fully-
    # qualified module is canonically registered in sys.modules.
    module_path = "devolaflow.lifecycle.pre_plugin_invocation"
    assert module_path in sys.modules, (
        f"hook module {module_path!r} must be loaded before this test runs; "
        "it should have been imported transitively by `from devolaflow.lifecycle "
        "import ...` at the top of this file"
    )
    hook_mod = sys.modules[module_path]
    source_path = hook_mod.__file__
    assert source_path is not None, (
        "hook module must have a __file__ attribute (we AST-walk the source "
        "to verify the lazy-import contract)"
    )
    with open(source_path, encoding="utf-8") as fh:
        source = fh.read()
    # AST-walk the source to identify ALL module-level imports. Function-body
    # imports inside `_extract_plugin_ids` (workflow→plugin resolution) and
    # inside `pre_plugin_invocation` (installer.ensure_plugin) are intentionally
    # ALLOWED — they ARE the lazy-import surface that delivers the R5 strict
    # zero-IO invariant. Module-level imports of those modules would defeat it.
    import ast

    tree = ast.parse(source)
    forbidden_modules = {
        "devolaflow.plugins.installer",
        "devolaflow.plugins.exceptions",
    }
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module in forbidden_modules:
            pytest.fail(
                f"v9.4.0 R5 strict violation: {hook_mod.__name__} statically "
                f"imports {node.module!r} at module top-level (line {node.lineno}). "
                "The R5 strict zero-IO invariant requires this import to live "
                "INSIDE a function body so the env-flag-OFF cold path does not "
                "pull in the 1030-LOC installer module."
            )
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in forbidden_modules:
                    pytest.fail(
                        f"v9.4.0 R5 strict violation: {hook_mod.__name__} "
                        f"statically imports {alias.name!r} at module top-level "
                        f"(line {node.lineno}). Move the import inside a "
                        "function body."
                    )


# ---------------------------------------------------------------------------
# §7 — D-P-2 BLOCKER closure: daily-upgrade integration (v10.2.1 PV-02)
# ---------------------------------------------------------------------------


class TestDailyUpgradeIntegration:
    """v10.2.1 PV-02 — pre_plugin_invocation now also fires upgrade_plugin
    for stale plugins (closes D-P-2 BLOCKER from v10.2.0 gap analysis §3.1).

    REUSE-FIRST contract per W-20 §3: the integration uses the existing
    ``DEVOLAFLOW_AUTO_INSTALL_PLUGINS=1`` env flag (same activation
    surface as v9.4.0 ensure_plugin path). 0 NEW env flags in this PV.

    Tests pin:
    1. **Stale plugin → upgrade_plugin fires** — env flag ON, plugin
       resolves at min_version BUT is stale → upgrade_plugin called.
    2. **Fresh plugin → no upgrade** — env flag ON, plugin fresh →
       upgrade_plugin NOT called (idempotent).
    3. **upgrade_plugin failure → PPI003 warning, dispatch unblocked** —
       env flag ON, stale, upgrade fails → violation aggregated as
       warning; permissive default does NOT raise.
    4. **Disabled is no-op** — env flag absent → upgrade_plugin NEVER
       called even on a stale plugin (R5 strict zero-IO byte-identical).
    """

    def test_event_triggers_daily_upgrade_constant_present(self) -> None:
        """The introspection constant is exposed for downstream governance."""
        assert EVENT_TRIGGERS_DAILY_UPGRADE is True, (
            "v10.2.1 PV-02 D-P-2: EVENT_TRIGGERS_DAILY_UPGRADE must be True "
            "to confirm the daily-upgrade behaviour is wired"
        )

    def test_d_p_2_stale_plugin_triggers_upgrade(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """D-P-2 closure: env flag ON + plugin stale → upgrade_plugin fires."""
        monkeypatch.setenv(ENV_FLAG, ENV_FLAG_TRUTHY)
        ensure_calls: list[str] = []
        upgrade_calls: list[str] = []

        def fake_ensure(plugin_id: str, **_kw):  # type: ignore[no-untyped-def]
            ensure_calls.append(plugin_id)
            return "3.3.0"

        def fake_upgrade(plugin_id: str, **_kw):  # type: ignore[no-untyped-def]
            upgrade_calls.append(plugin_id)
            return "3.3.1"

        with (
            patch(
                "devolaflow.plugins.installer.ensure_plugin",
                side_effect=fake_ensure,
            ),
            patch(
                "devolaflow.plugins.installer.is_plugin_stale",
                return_value=True,
            ),
            patch(
                "devolaflow.plugins.installer.upgrade_plugin",
                side_effect=fake_upgrade,
            ),
        ):
            result = pre_plugin_invocation({"plugin_id": "nines"})

        assert ensure_calls == ["nines"]
        assert upgrade_calls == ["nines"], (
            "D-P-2 violation: stale plugin did NOT trigger upgrade_plugin"
        )
        assert result.passed is True
        assert result.violations == []

    def test_d_p_2_fresh_plugin_no_upgrade(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """D-P-2 contract: fresh plugin → upgrade_plugin NOT called."""
        monkeypatch.setenv(ENV_FLAG, ENV_FLAG_TRUTHY)
        upgrade_calls: list[str] = []

        def fake_ensure(plugin_id: str, **_kw):  # type: ignore[no-untyped-def]
            return "3.3.0"

        def fake_upgrade(plugin_id: str, **_kw):  # type: ignore[no-untyped-def]
            upgrade_calls.append(plugin_id)
            return "3.3.1"

        with (
            patch(
                "devolaflow.plugins.installer.ensure_plugin",
                side_effect=fake_ensure,
            ),
            patch(
                "devolaflow.plugins.installer.is_plugin_stale",
                return_value=False,
            ),
            patch(
                "devolaflow.plugins.installer.upgrade_plugin",
                side_effect=fake_upgrade,
            ),
        ):
            result = pre_plugin_invocation({"plugin_id": "nines"})

        assert upgrade_calls == [], (
            f"D-P-2 idempotency violation: fresh plugin triggered "
            f"upgrade_plugin (calls: {upgrade_calls!r})"
        )
        assert result.passed is True

    def test_d_p_2_upgrade_failure_does_not_block_dispatch(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """D-P-2 fault tolerance: upgrade_plugin failure → PPI003 warning,
        dispatch returns successfully (does not raise)."""
        monkeypatch.setenv(ENV_FLAG, ENV_FLAG_TRUTHY)

        def fake_ensure(plugin_id: str, **_kw):  # type: ignore[no-untyped-def]
            return "3.3.0"

        def boom_upgrade(plugin_id: str, **_kw):  # type: ignore[no-untyped-def]
            raise PluginInstallError(
                f"network unreachable while upgrading {plugin_id!r}",
                details={"plugin_id": plugin_id, "stage": "upgrade"},
            )

        with (
            patch(
                "devolaflow.plugins.installer.ensure_plugin",
                side_effect=fake_ensure,
            ),
            patch(
                "devolaflow.plugins.installer.is_plugin_stale",
                return_value=True,
            ),
            patch(
                "devolaflow.plugins.installer.upgrade_plugin",
                side_effect=boom_upgrade,
            ),
        ):
            # Permissive default — must NOT raise.
            result = pre_plugin_invocation({"plugin_id": "nines"})

        ppi003 = [v for v in result.violations if v.code == "PPI003"]
        assert len(ppi003) == 1, (
            f"D-P-2: upgrade_plugin failure must surface as exactly one "
            f"PPI003 warning; got {[v.code for v in result.violations]!r}"
        )
        assert ppi003[0].severity == "warning"
        assert "nines" in ppi003[0].message
        assert ppi003[0].context["stage"] == "daily_upgrade"
        # PPI003 is a warning, not error → permissive HookResult.passed
        # depends on the dispatcher's pass_if floor; we assert no PPI001
        # was injected (the install-time error code), which would mean a
        # cascade.
        assert not any(v.code == "PPI001" for v in result.violations), (
            "Daily-upgrade failure must NOT cascade as a PPI001 install error"
        )

    def test_d_p_2_disabled_when_env_flag_off(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """R5 strict: env flag OFF → upgrade_plugin NEVER called.

        Even when the plugin would have been stale, the daily-upgrade
        path MUST NOT fire when the activation flag is unset. This is
        the byte-identical no-op invariant for the v9.3.0+ env-flag
        contract.
        """
        monkeypatch.delenv(ENV_FLAG, raising=False)
        ensure_calls: list[str] = []
        upgrade_calls: list[str] = []

        def watcher_ensure(plugin_id: str, **_kw):  # type: ignore[no-untyped-def]
            ensure_calls.append(plugin_id)
            return "0.0.0"

        def watcher_upgrade(plugin_id: str, **_kw):  # type: ignore[no-untyped-def]
            upgrade_calls.append(plugin_id)
            return "0.0.1"

        with (
            patch(
                "devolaflow.plugins.installer.ensure_plugin",
                side_effect=watcher_ensure,
            ),
            patch(
                "devolaflow.plugins.installer.is_plugin_stale",
                return_value=True,
            ),
            patch(
                "devolaflow.plugins.installer.upgrade_plugin",
                side_effect=watcher_upgrade,
            ),
        ):
            result = pre_plugin_invocation({"plugin_id": "nines"})

        assert ensure_calls == [], "R5 strict: ensure_plugin must not fire when env flag is OFF"
        assert upgrade_calls == [], (
            "R5 strict: upgrade_plugin must not fire when env flag is OFF "
            "(daily-upgrade path is gated behind the same activation surface)"
        )
        assert result.passed is True
        assert result.violations == []

    def test_d_p_2_stale_probe_failure_skips_upgrade(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When is_plugin_stale itself raises, upgrade is skipped per S-5.

        Documents the defensive contract: a corrupt install log file
        should NOT crash the daily-upgrade hook; the staleness probe
        failure is logged and the per-plugin loop continues.
        """
        monkeypatch.setenv(ENV_FLAG, ENV_FLAG_TRUTHY)
        upgrade_calls: list[str] = []

        def fake_ensure(plugin_id: str, **_kw):  # type: ignore[no-untyped-def]
            return "3.3.0"

        def boom_stale(plugin_id: str, **_kw):  # type: ignore[no-untyped-def]
            raise OSError("install log is corrupt")

        def watcher_upgrade(plugin_id: str, **_kw):  # type: ignore[no-untyped-def]
            upgrade_calls.append(plugin_id)
            return "3.3.1"

        with (
            patch(
                "devolaflow.plugins.installer.ensure_plugin",
                side_effect=fake_ensure,
            ),
            patch(
                "devolaflow.plugins.installer.is_plugin_stale",
                side_effect=boom_stale,
            ),
            patch(
                "devolaflow.plugins.installer.upgrade_plugin",
                side_effect=watcher_upgrade,
            ),
        ):
            result = pre_plugin_invocation({"plugin_id": "nines"})

        assert upgrade_calls == [], (
            "Stale probe failure must skip the upgrade attempt for that plugin"
        )
        assert result.passed is True


# ---------------------------------------------------------------------------
# §10 — v10.2.3 PV-04 helper extraction (CC reduction: 18 → ≤10)
# ---------------------------------------------------------------------------


class TestRunInstallThenUpgradeHelper:
    """Pin :func:`_run_install_then_upgrade_for_plugin` signature + contract.

    Helper extracted in v10.2.3 PV-04 from :func:`pre_plugin_invocation`
    to address the NineS PV-03 deep-analysis CC=18 finding at
    `.local/research/v10.2.2_nines.md` §2 row #2. Behaviour is byte-
    identical to the v10.2.1 baseline; this class proves the extraction
    preserves the public contract by exercising the helper directly.
    """

    def test_helper_imports_with_documented_signature(self) -> None:
        """The PV-04 helper exists and exposes the documented signature.

        Pins the signature so future PV refactors don't silently rename
        the helper out from under callers (the helper IS now part of
        the module's introspection surface per W-18).
        """
        import inspect

        from devolaflow.lifecycle.pre_plugin_invocation import (
            _run_install_then_upgrade_for_plugin,
        )

        sig = inspect.signature(_run_install_then_upgrade_for_plugin)
        params = sig.parameters
        assert "plugin_id" in params, "v10.2.3 PV-04: helper must take ``plugin_id`` positional arg"
        assert "threshold_hours" in params, (
            "v10.2.3 PV-04: helper must take ``threshold_hours`` keyword-only arg"
        )
        # Keyword-only enforcement — threshold_hours is *not* positional.
        assert params["threshold_hours"].kind == inspect.Parameter.KEYWORD_ONLY

    def test_helper_returns_empty_violations_on_clean_install(self) -> None:
        """Happy path: ensure_plugin succeeds + plugin not stale → 0 violations."""
        from devolaflow.lifecycle.pre_plugin_invocation import (
            _run_install_then_upgrade_for_plugin,
        )

        with (
            patch(
                "devolaflow.plugins.installer.ensure_plugin",
                return_value="1.0.0",
            ),
            patch(
                "devolaflow.plugins.installer.is_plugin_stale",
                return_value=False,
            ),
            patch(
                "devolaflow.plugins.installer.upgrade_plugin",
                side_effect=AssertionError("MUST NOT be called"),
            ),
        ):
            violations = _run_install_then_upgrade_for_plugin(
                "nines",
                threshold_hours=24,
            )
        assert violations == [], (
            "v10.2.3 PV-04: clean install + fresh plugin yields zero PPI* violations"
        )

    def test_helper_returns_ppi001_on_install_failure(self) -> None:
        """ensure_plugin failure → exactly one PPI001 error violation."""
        from devolaflow.lifecycle.pre_plugin_invocation import (
            _run_install_then_upgrade_for_plugin,
        )

        with (
            patch(
                "devolaflow.plugins.installer.ensure_plugin",
                side_effect=PluginInstallError("nines: boom"),
            ),
            patch(
                "devolaflow.plugins.installer.is_plugin_stale",
                side_effect=AssertionError("MUST NOT be called when install fails"),
            ),
        ):
            violations = _run_install_then_upgrade_for_plugin(
                "nines",
                threshold_hours=24,
            )
        assert len(violations) == 1
        assert violations[0].code == "PPI001"
        assert violations[0].severity == "error"
