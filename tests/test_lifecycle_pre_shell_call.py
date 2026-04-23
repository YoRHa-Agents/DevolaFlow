"""Tests for the ``pre_shell_call`` lifecycle hook (v8.3.2 PV-02 — R-002).

Validates that the new hook integrates cleanly with the existing
:mod:`devolaflow.lifecycle.dispatcher` framework — same
``HookResult`` envelope, same permissive default + strict-opt-in
contract, same payload-shape validation discipline as
``check_file_ownership`` / ``validate_dispatch`` /
``test_on_complete`` / ``format_on_edit``.

Coverage:

* Hook is registered as a default for the new event on package import
* Dispatching the event via :func:`run_hooks` works with the new hook
* Schema enforcement (missing ``cmd``, wrong types) raises in strict
* Wrapped command lands in ``HookResult.metadata["wrapped_cmd"]``
* The hook is non-mutating (input payload unchanged)
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from devolaflow.lifecycle import (
    DEFAULT_EVENTS,
    PRE_SHELL_CALL_EVENT,
    HookViolation,
    list_handlers,
    pre_shell_call,
    registered_events,
    run_hooks,
)


class TestPreShellCallHookIntegration:
    def test_event_constant_and_default_handler_registration(self) -> None:
        # Event constant exposed; in DEFAULT_EVENTS; in registered_events;
        # default handler is the actual function.
        assert PRE_SHELL_CALL_EVENT == "pre_shell_call"
        assert PRE_SHELL_CALL_EVENT in DEFAULT_EVENTS
        assert PRE_SHELL_CALL_EVENT in registered_events()
        handlers = list_handlers(PRE_SHELL_CALL_EVENT)
        assert len(handlers) >= 1
        assert handlers[0] is pre_shell_call

    def test_run_hooks_dispatches_pre_shell_call(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            result = run_hooks(
                PRE_SHELL_CALL_EVENT,
                {"cmd": "pytest tests/", "cwd": None},
            )
            # run_hooks aggregates passed=True signal; per-hook metadata is
            # carried on the hook's own HookResult.
            assert result.passed is True

    def test_direct_invocation_carries_wrapped_cmd_metadata(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            result = pre_shell_call({"cmd": "pytest tests/ -q", "cwd": None})
        assert result.event == "pre_shell_call"
        assert result.passed is True
        assert result.metadata["wrapped_cmd"] == "pytest tests/ -q"
        assert result.metadata["was_rewritten"] is False
        assert result.metadata["proxy_enabled"] is False


class TestPreShellCallPayloadValidation:
    def test_strict_mode_raises_for_each_bad_payload_shape(self) -> None:
        # Four schema violations + their codes (mirrors check_file_ownership's
        # CFO001-CFO005 discipline at the PSC namespace).
        cases: list[tuple[object, str]] = [
            ("not-a-dict", "PSC001"),
            ({"cwd": "."}, "PSC002"),  # missing cmd
            ({"cmd": 123}, "PSC003"),  # non-string cmd
            ({"cmd": "pytest tests/", "cwd": 42}, "PSC004"),  # non-string cwd
        ]
        for payload, expected_code in cases:
            with pytest.raises(HookViolation) as exc_info:
                pre_shell_call(payload, strict=True)  # type: ignore[arg-type]
            assert exc_info.value.code == expected_code, (
                f"payload={payload!r} expected code {expected_code} got {exc_info.value.code}"
            )

    def test_permissive_returns_failed_result_for_bad_payload(self) -> None:
        result = pre_shell_call({"cwd": "."})
        assert result.passed is False
        assert len(result.violations) == 1
        assert result.violations[0].code == "PSC002"
        assert result.violations[0].severity == "error"

    def test_well_formed_payload_does_not_mutate_input(self) -> None:
        payload = {"cmd": "pytest tests/ -q", "cwd": "."}
        snapshot = dict(payload)
        with patch.dict("os.environ", {}, clear=True):
            pre_shell_call(payload)
        assert payload == snapshot
