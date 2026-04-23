"""Tests for the lifecycle hooks package (P-05 in the v7.5.0 cycle).

Covers the 3 default hooks (``validate_dispatch``, ``check_file_ownership``,
``test_on_complete``), the central :func:`run_hooks` orchestrator, and
the extra-handler registry layer (``register_hook`` / ``clear_hooks`` /
``list_handlers``). Closes BLOCKER ghost G-C1 documented in
``.local/research/v7.5.0_ghost_audit.md`` §3.C.

Test strategy:

* Each hook is exercised in BOTH permissive (default) and strict modes.
* Each hook's malformed-payload paths are covered (non-dict payload,
  missing required fields, wrong type for a field, placeholder
  acceptance criteria).
* ``run_hooks`` is exercised for: empty-event, missing handler, single
  handler, multi-handler aggregation, strict re-raise of cross-handler
  top severity.
* ``HookViolation`` and ``HookResult`` envelope behaviour (severity
  ordering, equality, raisability) is pinned so future refactors of the
  dispatcher don't silently break the contract.
* Logging discipline (caplog vs ``print``) is verified — AC-3 requires
  WARNING-level emissions via the standard :mod:`logging` module.
"""

from __future__ import annotations

import logging

import pytest

from devolaflow.lifecycle import (
    DEFAULT_EVENTS,
    FILE_WRITE_EVENT,
    PRE_DISPATCH_EVENT,
    TASK_STOP_EVENT,
    HookResult,
    HookViolation,
    check_file_ownership,
    clear_hooks,
    list_handlers,
    register_hook,
    registered_events,
    run_hooks,
    test_on_complete,
    validate_dispatch,
)
from devolaflow.lifecycle.dispatcher import emit_violations, finalize


@pytest.fixture(autouse=True)
def _reset_extras() -> None:
    """Clear extra-handler registry between tests so register_hook tests don't leak."""
    clear_hooks()
    yield
    clear_hooks()


# ---------------------------------------------------------------------------
# Envelope dataclasses — HookViolation / HookResult
# ---------------------------------------------------------------------------


class TestHookViolation:
    def test_is_exception_subclass(self) -> None:
        assert issubclass(HookViolation, Exception)

    def test_can_be_raised_and_caught(self) -> None:
        with pytest.raises(HookViolation) as exc_info:
            raise HookViolation("X001", "boom", severity="blocker")
        assert exc_info.value.code == "X001"
        assert exc_info.value.severity == "blocker"
        assert "boom" in str(exc_info.value)

    def test_str_includes_severity_and_code(self) -> None:
        v = HookViolation("V001", "msg", severity="error")
        rendered = str(v)
        assert "[error]" in rendered
        assert "V001" in rendered
        assert "msg" in rendered

    def test_repr_round_trips_fields(self) -> None:
        v = HookViolation("V002", "msg2", severity="warning", context={"k": 1})
        rep = repr(v)
        assert "V002" in rep and "warning" in rep and "msg2" in rep and "'k': 1" in rep

    def test_equality_and_hash(self) -> None:
        a = HookViolation("V001", "m", severity="blocker", context={"k": 1})
        b = HookViolation("V001", "m", severity="blocker", context={"k": 1})
        c = HookViolation("V001", "m", severity="error", context={"k": 1})
        assert a == b
        assert a != c
        assert a != "not-a-violation"
        # Hash consistency (equal objects → equal hashes)
        assert hash(a) == hash(b)

    def test_default_severity_is_error(self) -> None:
        v = HookViolation("V003", "m")
        assert v.severity == "error"

    def test_context_defaults_to_empty_dict(self) -> None:
        v = HookViolation("V004", "m")
        assert v.context == {}


class TestHookResult:
    def test_clean_result_severity_is_none(self) -> None:
        r = HookResult(event="x")
        assert r.passed is True
        assert r.violations == []
        assert r.severity is None
        assert r.top_violation() is None

    def test_severity_picks_max_across_violations(self) -> None:
        r = HookResult(
            event="x",
            passed=False,
            violations=[
                HookViolation("A", "a", severity="warning"),
                HookViolation("B", "b", severity="blocker"),
                HookViolation("C", "c", severity="error"),
            ],
        )
        assert r.severity == "blocker"
        assert r.top_violation().code == "B"

    def test_metadata_is_mutable_dict(self) -> None:
        r = HookResult(event="x")
        r.metadata["reason"] = "no handlers"
        assert r.metadata == {"reason": "no handlers"}


# ---------------------------------------------------------------------------
# Default event wiring — ensure 3 events are auto-registered after import
# ---------------------------------------------------------------------------


def test_default_events_match_skill_md_table() -> None:
    """Package must wire all canonical events (3 original + format_on_edit + pre_shell_call)."""
    assert PRE_DISPATCH_EVENT == "pre_dispatch"
    assert FILE_WRITE_EVENT == "file_write"
    assert TASK_STOP_EVENT == "task_stop"
    assert set(DEFAULT_EVENTS) == {
        "pre_dispatch",
        "file_write",
        "task_stop",
        "format_on_edit",
        "pre_shell_call",
    }


def test_registered_events_includes_all_defaults() -> None:
    events = registered_events()
    for ev in DEFAULT_EVENTS:
        assert ev in events, f"default event '{ev}' not registered"


def test_list_handlers_returns_default_for_each_event() -> None:
    assert list_handlers(PRE_DISPATCH_EVENT) == (validate_dispatch,)
    assert list_handlers(FILE_WRITE_EVENT) == (check_file_ownership,)
    assert list_handlers(TASK_STOP_EVENT) == (test_on_complete,)


# ---------------------------------------------------------------------------
# validate_dispatch — pre_dispatch hook
# ---------------------------------------------------------------------------


class TestValidateDispatch:
    def test_passes_with_testable_acceptance_criteria(self) -> None:
        payload = {
            "task": {"id": "T01"},
            "accept": [
                "JWT middleware exported from src/middleware/auth.ts",
                "valid token → req.user populated",
            ],
        }
        r = validate_dispatch(payload)
        assert r.passed is True
        assert r.violations == []
        assert r.event == "pre_dispatch"

    def test_accepts_verbose_acceptance_criteria_key(self) -> None:
        payload = {"acceptance_criteria": ["criterion that is long enough to be testable"]}
        r = validate_dispatch(payload)
        assert r.passed is True

    def test_warns_on_empty_accept_list_in_permissive_mode(self, caplog) -> None:
        with caplog.at_level(logging.WARNING, logger="devolaflow.lifecycle.dispatcher"):
            r = validate_dispatch({"accept": []})
        assert r.passed is False
        assert len(r.violations) == 1
        assert r.violations[0].code == "VD004"
        assert r.violations[0].severity == "blocker"
        # AC-3: must log via logging module, not print
        assert any("VD004" in rec.message for rec in caplog.records)

    def test_strict_raises_on_empty_accept_list(self) -> None:
        with pytest.raises(HookViolation) as exc_info:
            validate_dispatch({"accept": []}, strict=True)
        assert exc_info.value.code == "VD004"
        assert exc_info.value.severity == "blocker"

    def test_rejects_placeholder_criteria(self) -> None:
        payload = {"accept": ["TBD", "todo", "n/a", "various", ""]}
        r = validate_dispatch(payload)
        assert r.passed is False
        assert r.violations[0].code == "VD004"

    def test_filters_short_non_string_criteria(self) -> None:
        payload = {"accept": [None, 1, "ok", "yes", 3.14]}
        r = validate_dispatch(payload)
        assert r.passed is False
        assert r.violations[0].code == "VD004"

    def test_missing_accept_key_returns_blocker(self) -> None:
        payload = {"task": {"id": "T01"}}
        r = validate_dispatch(payload)
        assert r.passed is False
        assert r.violations[0].code == "VD002"
        assert r.violations[0].severity == "blocker"

    def test_non_dict_payload_returns_error(self) -> None:
        r = validate_dispatch("not a dict")
        assert r.passed is False
        assert r.violations[0].code == "VD001"
        assert r.violations[0].severity == "error"

    def test_strict_raises_on_non_dict_payload(self) -> None:
        with pytest.raises(HookViolation) as exc_info:
            validate_dispatch(["a", "list"], strict=True)
        assert exc_info.value.code == "VD001"

    def test_accept_field_must_be_list(self) -> None:
        r = validate_dispatch({"accept": "not a list"})
        assert r.passed is False
        assert r.violations[0].code == "VD003"
        assert r.violations[0].severity == "error"


# ---------------------------------------------------------------------------
# check_file_ownership — file_write hook
# ---------------------------------------------------------------------------


class TestCheckFileOwnership:
    def test_passes_when_path_in_owned_files(self) -> None:
        payload = {"path": "src/x.py", "owned_files": ["src/x.py", "src/y.py"]}
        r = check_file_ownership(payload)
        assert r.passed is True
        assert r.event == "file_write"

    def test_warns_when_path_outside_owned(self, caplog) -> None:
        with caplog.at_level(logging.WARNING, logger="devolaflow.lifecycle.dispatcher"):
            r = check_file_ownership({"path": "outside.py", "owned_files": ["a.py", "b.py"]})
        assert r.passed is False
        assert r.violations[0].code == "CFO006"
        assert r.violations[0].severity == "blocker"
        assert "outside.py" in r.violations[0].message
        # AC-3: WARNING-level log emitted via standard logging
        assert any("CFO006" in rec.message for rec in caplog.records)

    def test_strict_raises_when_outside_owned(self) -> None:
        with pytest.raises(HookViolation) as exc_info:
            check_file_ownership(
                {"path": "outside.py", "owned_files": ["a.py"]},
                strict=True,
            )
        assert exc_info.value.code == "CFO006"
        assert exc_info.value.severity == "blocker"

    def test_normalises_paths_for_comparison(self) -> None:
        # ./src/x.py should normalise to src/x.py and match.
        payload = {"path": "./src/x.py", "owned_files": ["src/x.py"]}
        r = check_file_ownership(payload)
        assert r.passed is True

    def test_accepts_alternate_files_key(self) -> None:
        payload = {"path": "a.py", "files": ["a.py"]}
        r = check_file_ownership(payload)
        assert r.passed is True

    def test_missing_path_returns_error(self) -> None:
        r = check_file_ownership({"owned_files": ["a.py"]})
        assert r.violations[0].code == "CFO002"
        assert r.violations[0].severity == "error"

    def test_path_must_be_string(self) -> None:
        r = check_file_ownership({"path": 123, "owned_files": ["a.py"]})
        assert r.violations[0].code == "CFO003"

    def test_missing_owned_files_returns_error(self) -> None:
        r = check_file_ownership({"path": "a.py"})
        assert r.violations[0].code == "CFO004"

    def test_owned_files_must_be_list(self) -> None:
        r = check_file_ownership({"path": "a.py", "owned_files": "not-a-list"})
        assert r.violations[0].code == "CFO005"

    def test_non_dict_payload_returns_error(self) -> None:
        r = check_file_ownership(None)
        assert r.violations[0].code == "CFO001"

    def test_owned_files_with_non_string_entries_filtered(self) -> None:
        # Non-string entries in owned_files should be silently filtered
        # (so the hook doesn't crash on dirty input) but the path-match
        # decision still rejects the unowned write.
        r = check_file_ownership({"path": "a.py", "owned_files": [None, 42, "b.py"]})
        assert r.passed is False
        assert r.violations[0].code == "CFO006"


# ---------------------------------------------------------------------------
# test_on_complete — task_stop hook
# ---------------------------------------------------------------------------


class TestTestOnComplete:
    def test_passes_with_clean_metrics(self) -> None:
        payload = {
            "metrics": {
                "tests_passed": 100,
                "tests_failed": 0,
                "lint_status": "clean",
            }
        }
        r = test_on_complete(payload)
        assert r.passed is True
        assert r.event == "task_stop"

    def test_passes_with_top_level_metrics(self) -> None:
        payload = {"tests_passed": 50, "tests_failed": 0, "lint_status": "pass"}
        r = test_on_complete(payload)
        assert r.passed is True

    def test_warns_on_test_failures_in_permissive_mode(self, caplog) -> None:
        payload = {"metrics": {"tests_passed": 90, "tests_failed": 3, "lint_status": "clean"}}
        with caplog.at_level(logging.WARNING, logger="devolaflow.lifecycle.dispatcher"):
            r = test_on_complete(payload)
        assert r.passed is False
        assert any(v.code == "TOC004" for v in r.violations)
        assert any("TOC004" in rec.message for rec in caplog.records)

    def test_strict_raises_on_test_failures(self) -> None:
        payload = {"metrics": {"tests_passed": 90, "tests_failed": 1, "lint_status": "clean"}}
        with pytest.raises(HookViolation) as exc_info:
            test_on_complete(payload, strict=True)
        assert exc_info.value.code == "TOC004"
        assert exc_info.value.severity == "blocker"

    def test_strict_raises_on_dirty_lint(self) -> None:
        payload = {
            "metrics": {
                "tests_passed": 100,
                "tests_failed": 0,
                "lint_status": "warnings",
            }
        }
        with pytest.raises(HookViolation) as exc_info:
            test_on_complete(payload, strict=True)
        assert exc_info.value.code == "TOC006"

    def test_accepts_multiple_clean_lint_synonyms(self) -> None:
        for token in ["clean", "PASS", "passed", "OK", "green", "0_warnings"]:
            payload = {
                "tests_passed": 1,
                "tests_failed": 0,
                "lint_status": token,
            }
            r = test_on_complete(payload)
            assert r.passed is True, f"token {token!r} should be clean"

    def test_missing_test_metrics_returns_error(self) -> None:
        r = test_on_complete({"lint_status": "clean"})
        assert any(v.code == "TOC003" for v in r.violations)

    def test_missing_lint_status_returns_error(self) -> None:
        r = test_on_complete({"tests_passed": 1, "tests_failed": 0})
        assert any(v.code == "TOC005" for v in r.violations)

    def test_metrics_must_be_dict_when_present(self) -> None:
        r = test_on_complete({"metrics": "not-a-dict"})
        assert r.violations[0].code == "TOC002"

    def test_non_dict_payload_returns_error(self) -> None:
        r = test_on_complete([])
        assert r.violations[0].code == "TOC001"

    def test_tests_failed_coerces_string_to_int(self) -> None:
        payload = {"tests_passed": 10, "tests_failed": "2", "lint_status": "clean"}
        r = test_on_complete(payload)
        assert r.passed is False
        assert any(v.code == "TOC004" for v in r.violations)

    def test_aggregates_multiple_violations(self) -> None:
        payload = {"tests_passed": 1, "tests_failed": 5, "lint_status": "warnings"}
        r = test_on_complete(payload)
        # Both TOC004 (test failures) and TOC006 (dirty lint) should fire
        codes = {v.code for v in r.violations}
        assert "TOC004" in codes
        assert "TOC006" in codes

    def test_coerce_int_handles_bool_float_and_unparseable(self) -> None:
        """Cover _coerce_int branches: bool, float, malformed string, unknown type."""
        from devolaflow.lifecycle.test_on_complete import _coerce_int

        assert _coerce_int(True) == 1  # bool branch
        assert _coerce_int(False, default=99) == 0  # bool False stays 0
        assert _coerce_int(3.7) == 3  # float branch
        assert _coerce_int("not-a-number", default=42) == 42  # string ValueError
        assert _coerce_int(None, default=7) == 7  # unknown type fallback
        assert _coerce_int(["list"], default=5) == 5  # unknown type fallback


# ---------------------------------------------------------------------------
# run_hooks orchestrator
# ---------------------------------------------------------------------------


class TestRunHooks:
    def test_unknown_event_returns_clean_result_with_metadata(self) -> None:
        r = run_hooks("nonexistent_event", {})
        assert r.passed is True
        assert r.violations == []
        assert r.metadata.get("reason") == "no handlers registered"

    def test_event_with_no_handlers_after_clear(self) -> None:
        # Register an extra handler and clear it; the default for that
        # event remains, so we verify clear_hooks DOES NOT remove defaults.
        r = run_hooks(FILE_WRITE_EVENT, {"path": "a.py", "owned_files": ["a.py"]})
        assert r.passed is True

    def test_dispatches_to_default_handler_for_each_event(self) -> None:
        # pre_dispatch
        r = run_hooks(
            PRE_DISPATCH_EVENT,
            {"accept": ["AC long enough to be testable"]},
        )
        assert r.passed is True

        # file_write
        r = run_hooks(FILE_WRITE_EVENT, {"path": "a.py", "owned_files": ["a.py"]})
        assert r.passed is True

        # task_stop
        r = run_hooks(
            TASK_STOP_EVENT,
            {"tests_passed": 1, "tests_failed": 0, "lint_status": "clean"},
        )
        assert r.passed is True

    def test_permissive_default_does_not_raise(self) -> None:
        # AC-3 wording: returns HookResult with violations but does NOT raise.
        r = run_hooks(
            FILE_WRITE_EVENT,
            {"path": "outside.py", "owned_files": ["a.py"]},
        )
        assert r.passed is False
        assert len(r.violations) == 1

    def test_strict_mode_raises_top_severity_violation(self) -> None:
        with pytest.raises(HookViolation) as exc_info:
            run_hooks(
                FILE_WRITE_EVENT,
                {"path": "outside.py", "owned_files": ["a.py"]},
                strict=True,
            )
        assert exc_info.value.severity == "blocker"

    def test_register_hook_appends_extra_handler(self) -> None:
        captured: list[dict] = []

        def extra(payload: dict, *, strict: bool = False) -> HookResult:
            captured.append(payload)
            return HookResult(event=FILE_WRITE_EVENT)

        register_hook(FILE_WRITE_EVENT, extra)
        handlers = list_handlers(FILE_WRITE_EVENT)
        assert len(handlers) == 2  # default + extra
        assert handlers[1] is extra

        run_hooks(FILE_WRITE_EVENT, {"path": "a.py", "owned_files": ["a.py"]})
        assert len(captured) == 1
        assert captured[0]["path"] == "a.py"

    def test_clear_hooks_only_removes_extras(self) -> None:
        def extra(payload: dict, *, strict: bool = False) -> HookResult:
            return HookResult(event=FILE_WRITE_EVENT)

        register_hook(FILE_WRITE_EVENT, extra)
        assert len(list_handlers(FILE_WRITE_EVENT)) == 2
        clear_hooks(FILE_WRITE_EVENT)
        assert list_handlers(FILE_WRITE_EVENT) == (check_file_ownership,)

    def test_clear_hooks_with_no_arg_clears_all_extras(self) -> None:
        def extra(payload: dict, *, strict: bool = False) -> HookResult:
            return HookResult(event="x")

        register_hook(FILE_WRITE_EVENT, extra)
        register_hook(PRE_DISPATCH_EVENT, extra)
        clear_hooks()
        assert list_handlers(FILE_WRITE_EVENT) == (check_file_ownership,)
        assert list_handlers(PRE_DISPATCH_EVENT) == (validate_dispatch,)

    def test_aggregates_violations_from_multiple_handlers(self) -> None:
        def extra(payload: dict, *, strict: bool = False) -> HookResult:
            v = HookViolation("EXTRA001", "extra failure", severity="error")
            return HookResult(event=FILE_WRITE_EVENT, passed=False, violations=[v])

        register_hook(FILE_WRITE_EVENT, extra)
        r = run_hooks(
            FILE_WRITE_EVENT,
            {"path": "outside.py", "owned_files": ["a.py"]},
        )
        codes = {v.code for v in r.violations}
        assert "CFO006" in codes  # default handler
        assert "EXTRA001" in codes  # extra handler
        assert r.passed is False

    def test_strict_raises_top_across_handlers(self) -> None:
        # Default handler reports severity=blocker (CFO006); extra reports
        # severity=warning. Strict mode must raise the blocker, not the warning.
        def extra(payload: dict, *, strict: bool = False) -> HookResult:
            v = HookViolation("EXTRA002", "low-priority warning", severity="warning")
            return HookResult(event=FILE_WRITE_EVENT, passed=False, violations=[v])

        register_hook(FILE_WRITE_EVENT, extra)
        with pytest.raises(HookViolation) as exc_info:
            run_hooks(
                FILE_WRITE_EVENT,
                {"path": "outside.py", "owned_files": ["a.py"]},
                strict=True,
            )
        assert exc_info.value.severity == "blocker"
        assert exc_info.value.code == "CFO006"

    def test_handler_invoked_in_permissive_mode_even_when_run_hooks_strict(
        self,
    ) -> None:
        """Confirm AC contract: the dispatcher centralises the strict raise.

        Each handler is invoked with ``strict=False`` regardless of the
        caller's request; only ``run_hooks`` itself decides to escalate.
        This makes the across-handler violation set fully populated on
        the result envelope before the raise propagates.
        """
        observed_strict_flags: list[bool] = []

        def extra(payload: dict, *, strict: bool = False) -> HookResult:
            observed_strict_flags.append(strict)
            return HookResult(event=FILE_WRITE_EVENT)

        register_hook(FILE_WRITE_EVENT, extra)
        # Use a payload that PASSES default so no raise happens; we just
        # care about the strict-flag propagation.
        run_hooks(
            FILE_WRITE_EVENT,
            {"path": "a.py", "owned_files": ["a.py"]},
            strict=True,
        )
        assert observed_strict_flags == [False]

    def test_multiple_extra_handlers_invoked_in_insertion_order(self) -> None:
        order: list[str] = []

        def first(payload: dict, *, strict: bool = False) -> HookResult:
            order.append("first")
            return HookResult(event=FILE_WRITE_EVENT)

        def second(payload: dict, *, strict: bool = False) -> HookResult:
            order.append("second")
            return HookResult(event=FILE_WRITE_EVENT)

        register_hook(FILE_WRITE_EVENT, first)
        register_hook(FILE_WRITE_EVENT, second)
        run_hooks(FILE_WRITE_EVENT, {"path": "a.py", "owned_files": ["a.py"]})
        # Default handler runs first, then first, then second.
        assert order == ["first", "second"]


# ---------------------------------------------------------------------------
# Logging discipline — AC-3 requirement
# ---------------------------------------------------------------------------


class TestLoggingDiscipline:
    def test_emit_violations_logs_at_warning_level(self, caplog) -> None:
        v = HookViolation("X001", "boom", severity="error")
        with caplog.at_level(logging.WARNING, logger="devolaflow.lifecycle.dispatcher"):
            emit_violations("custom_event", [v])
        records = [r for r in caplog.records if r.levelname == "WARNING"]
        assert len(records) == 1
        assert "custom_event" in records[0].message
        assert "X001" in records[0].message

    def test_strict_mode_logs_error_before_raise(self, caplog) -> None:
        with (
            caplog.at_level(logging.ERROR, logger="devolaflow.lifecycle.dispatcher"),
            pytest.raises(HookViolation),
        ):
            run_hooks(
                FILE_WRITE_EVENT,
                {"path": "outside.py", "owned_files": ["a.py"]},
                strict=True,
            )
        # At least one ERROR-level log was emitted before the raise
        assert any(r.levelname == "ERROR" for r in caplog.records)

    def test_finalize_returns_clean_result_when_no_violations(self) -> None:
        r = finalize("event_x", [], strict=True)
        assert r.passed is True
        assert r.event == "event_x"
        assert r.violations == []

    def test_no_print_calls_in_lifecycle_modules(self) -> None:
        """Static check — defence in depth against accidentally introducing print()."""
        from pathlib import Path

        pkg_dir = Path(__file__).resolve().parent.parent / "src" / "devolaflow" / "lifecycle"
        for py in pkg_dir.glob("*.py"):
            text = py.read_text(encoding="utf-8")
            # Strip docstring / comment occurrences by searching for
            # statement-style `print(` at the start of a line (modulo
            # whitespace). This is sufficient for our defensive check —
            # the package is small and contains no legitimate print().
            for line in text.splitlines():
                stripped = line.strip()
                assert not stripped.startswith("print("), (
                    f"Found stray print() call in {py.name}: {stripped!r}"
                )
