"""Tests for the ``check_envelope_append_only`` lifecycle hook (v9.1.0 W1-02).

Closes the W1-02 deliverable in the v9.1.0 cycle by giving the new
``check_envelope_append_only`` hook direct unit-test coverage. The hook
elevates **Soul Rule S-9** (Handoff Envelopes Are Append-Only) from a
prompt-only constraint to a deterministic check by validating that the
target ``path`` for an envelope-write payload is NOT already present in
the supplied ``existing_paths`` set.

Test strategy mirrors the patterns established by
``tests/test_lifecycle_hooks.py::TestCheckFileOwnership`` for the
sister S-8 hook (``check_file_ownership``):

* Clean payload returns ``passed=True`` with no violations.
* Append-only breach (``path`` already in ``existing_paths``) raises
  the canonical CEA001 ``blocker`` violation; strict mode re-raises.
* Payload-shape errors (missing / wrong-type ``path`` and
  ``existing_paths``) emit the appropriate CEA002 / CEA003 codes
  with ``error`` severity.
* Non-dict payload short-circuits to a single error-severity violation.
* The hook is reachable through :func:`devolaflow.lifecycle.run_hooks`
  via the new ``ENVELOPE_WRITE_EVENT`` constant — confirms wiring
  integrity (W-18 ghost-audit refresh: the new hook has a direct
  test surface, not just an indirect one through the dispatcher).

Together with ``tests/test_handoff_envelope_immutable.py`` (filesystem
immutability via ``HandoffStore``) and the existing dispatcher tests in
``tests/test_lifecycle_hooks.py`` (default-event registration), this
module gives S-9 enforcement full layered test coverage.
"""

from __future__ import annotations

import pytest

from devolaflow.lifecycle import (
    ENVELOPE_WRITE_EVENT,
    HookViolation,
    check_envelope_append_only,
    run_hooks,
)


class TestCheckEnvelopeAppendOnly:
    def test_clean_payload_passes(self) -> None:
        """Path NOT in existing_paths → no violations, passed=True."""
        payload = {"path": "x.yaml", "existing_paths": ["a.yaml"]}
        r = check_envelope_append_only(payload)
        assert r.passed is True
        assert r.violations == []
        assert r.event == "envelope_write"

    def test_overwrite_attempt_emits_blocker_cea001(self, caplog) -> None:
        """Path already in existing_paths → single CEA001 blocker."""
        import logging

        payload = {
            "path": "alpha__beta__chg-1__1.yaml",
            "existing_paths": [
                "alpha__beta__chg-1__1.yaml",
                "alpha__beta__chg-1__2.yaml",
            ],
        }
        with caplog.at_level(logging.WARNING, logger="devolaflow.lifecycle.dispatcher"):
            r = check_envelope_append_only(payload)
        assert r.passed is False
        assert len(r.violations) == 1
        assert r.violations[0].code == "CEA001"
        assert r.violations[0].severity == "blocker"
        assert "alpha__beta__chg-1__1.yaml" in r.violations[0].message
        # AC-3: WARNING-level log emitted via standard logging
        assert any("CEA001" in rec.message for rec in caplog.records)

    def test_strict_mode_raises_on_overwrite(self) -> None:
        """Strict mode + append-only breach → raises CEA001 blocker."""
        payload = {
            "path": "alpha__beta__chg-1__1.yaml",
            "existing_paths": ["alpha__beta__chg-1__1.yaml"],
        }
        with pytest.raises(HookViolation) as exc_info:
            check_envelope_append_only(payload, strict=True)
        assert exc_info.value.code == "CEA001"
        assert exc_info.value.severity == "blocker"

    def test_missing_path_emits_cea002(self) -> None:
        """Payload without 'path' → CEA002 error severity."""
        r = check_envelope_append_only({"existing_paths": []})
        assert r.passed is False
        assert r.violations[0].code == "CEA002"
        assert r.violations[0].severity == "error"

    def test_non_string_path_emits_cea002(self) -> None:
        """Payload with non-string 'path' → CEA002 error severity."""
        r = check_envelope_append_only({"path": 123, "existing_paths": []})
        assert r.passed is False
        assert r.violations[0].code == "CEA002"
        assert r.violations[0].severity == "error"

    def test_missing_existing_paths_emits_cea003(self) -> None:
        """Payload without 'existing_paths' → CEA003 error severity."""
        r = check_envelope_append_only({"path": "x.yaml"})
        assert r.passed is False
        assert r.violations[0].code == "CEA003"
        assert r.violations[0].severity == "error"

    def test_non_list_existing_paths_emits_cea003(self) -> None:
        """Payload with non-list 'existing_paths' → CEA003 error severity."""
        r = check_envelope_append_only({"path": "x.yaml", "existing_paths": "not-a-list"})
        assert r.passed is False
        assert r.violations[0].code == "CEA003"
        assert r.violations[0].severity == "error"

    def test_non_dict_payload_emits_error(self) -> None:
        """Non-dict payloads (list, None) short-circuit to a single CEA002 error."""
        r_list = check_envelope_append_only([])
        assert r_list.passed is False
        assert len(r_list.violations) == 1
        assert r_list.violations[0].code == "CEA002"
        assert r_list.violations[0].severity == "error"

        r_none = check_envelope_append_only(None)
        assert r_none.passed is False
        assert len(r_none.violations) == 1
        assert r_none.violations[0].code == "CEA002"
        assert r_none.violations[0].severity == "error"

    def test_path_normalisation_detects_equivalent_paths(self) -> None:
        """./x.yaml should normalise to x.yaml and trigger the append-only breach."""
        payload = {"path": "./x.yaml", "existing_paths": ["x.yaml"]}
        r = check_envelope_append_only(payload)
        assert r.passed is False
        assert r.violations[0].code == "CEA001"

    def test_existing_paths_with_non_string_entries_filtered(self) -> None:
        """Non-string entries in existing_paths are silently filtered out.

        Mirrors ``check_file_ownership`` defensive handling: dirty input
        (e.g. ``None`` or ``int`` slots in the existing-paths list) does
        not crash the hook; only string entries participate in the
        normalised-set membership check.
        """
        payload = {"path": "x.yaml", "existing_paths": [None, 42, "y.yaml"]}
        r = check_envelope_append_only(payload)
        assert r.passed is True


# ---------------------------------------------------------------------------
# run_hooks integration — confirm the new event routes through the default.
# ---------------------------------------------------------------------------


def test_run_hooks_dispatches_envelope_write_event() -> None:
    """``run_hooks(ENVELOPE_WRITE_EVENT, ...)`` routes to the default handler."""
    result = run_hooks(
        ENVELOPE_WRITE_EVENT,
        {"path": "x.yaml", "existing_paths": []},
    )
    assert result.passed is True
    assert result.event == "envelope_write"


def test_run_hooks_strict_raises_on_envelope_overwrite() -> None:
    """Strict-mode dispatch through ``run_hooks`` re-raises the CEA001 blocker."""
    with pytest.raises(HookViolation) as exc_info:
        run_hooks(
            ENVELOPE_WRITE_EVENT,
            {"path": "x.yaml", "existing_paths": ["x.yaml"]},
            strict=True,
        )
    assert exc_info.value.code == "CEA001"
    assert exc_info.value.severity == "blocker"
