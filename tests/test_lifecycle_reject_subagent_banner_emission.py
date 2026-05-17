"""v12.4.0 PV-05 — ``reject_subagent_banner_emission`` pre_dispatch hook tests.

Closes the v12.4.0 D-4 L0-only surfaces leak cluster runtime layer
(the prompt-side guarantee was discharged in v12.3.0 PV-02 via SKILL.md
§"Session Banner Contract"; this PV adds the runtime-side enforcement
that subagent dispatches MUST NOT carry banner literals).

Test surface covers (per the v12.4.0 PV-05 dispatch AC):

1. Permissive default: a subagent dispatch carrying a ``🌸 DevolaFlow vX.Y.Z``
   banner literal in a free-text field returns a HookResult with the
   violation attached (no raise).
2. Strict mode (``strict=True``): the violation is re-raised as a
   HookViolation per the lifecycle dispatcher's strict contract.
3. Non-target-layer skip: dispatches with ``target_layer == "L0"`` are
   no-ops (banners are legitimate L0 output).
4. The opt-in :func:`register_pre_dispatch_extra` helper wires the hook
   into the ``pre_dispatch`` extras chain.
5. Banner literal detection (positive case in a free-text field).
6. Defensive handling of non-dict payloads.
7. Nested ``predecessor_artifacts[*].summary`` carrying a banner does
   NOT flag (top-level-only discipline mirrors the v12.2.0 PV-04
   ``reject_subagent_quality_score`` precedent — historical evidence
   carried forward from prior L0-authored rounds is legitimate).
8. The hook is NOT auto-wired in ``DEFAULT_EVENTS`` (S-10 byte-id
   contract preservation — opt-in only).
"""

from __future__ import annotations

import pytest

from devolaflow.lifecycle import (
    PRE_DISPATCH_EVENT,
    HookResult,
    HookViolation,
    clear_hooks,
    list_handlers,
    register_hook,
    run_hooks,
)
from devolaflow.lifecycle.reject_subagent_banner_emission import (
    EVENT,
    register_pre_dispatch_extra,
    reject_subagent_banner_emission,
)

_BANNER_LITERAL_ACTIVE: str = "🌸 DevolaFlow v12.4.0 active · workflow: feature · mode: agent"
_BANNER_LITERAL_COMPLETE: str = "🌸 DevolaFlow v12.4.0 complete · 3 stages · 5 waves · 12 tasks"


@pytest.fixture
def opt_in_registered():
    """Opt-in register the hook for wiring tests; clear extras at teardown.

    Since the v12.4.0 PV-05 hook is **opt-in only** (NOT a default
    extra in ``lifecycle/__init__.py`` — that distinction preserves the
    S-10 byte-id contract for v12.3.0 callers), tests that exercise the
    end-to-end ``run_hooks`` dispatch path MUST call
    :func:`register_pre_dispatch_extra` to wire the hook. The teardown
    clears extras to avoid leaking the registration into sibling test
    modules per the v12.2.0 PV-04 hook-test convention.
    """
    register_pre_dispatch_extra()
    yield
    clear_hooks(PRE_DISPATCH_EVENT)
    # Re-register the v12.2.0 PV-04 default extra that
    # ``clear_hooks`` strips alongside our opt-in hook, so sibling
    # tests inheriting the cleaned registry don't lose the v12.2.0
    # ``reject_subagent_quality_score`` wiring.
    from devolaflow.lifecycle import reject_subagent_quality_score
    from devolaflow.lifecycle.validate_owned_files import validate_owned_files

    register_hook(PRE_DISPATCH_EVENT, validate_owned_files)
    register_hook(PRE_DISPATCH_EVENT, reject_subagent_quality_score)


# ---------------------------------------------------------------------------
# 1. Permissive default — violation attached, no raise
# ---------------------------------------------------------------------------


def test_hook_attaches_violation_in_permissive_mode() -> None:
    """A subagent dispatch with a banner literal in a free-text field
    returns a HookResult with the violation attached; no raise per the
    S-5 explicit-error-state discipline."""
    payload = {
        "task": {"id": "T-001"},
        "target_layer": "L3",
        "summary": _BANNER_LITERAL_ACTIVE,
    }
    result = reject_subagent_banner_emission(payload)
    assert isinstance(result, HookResult)
    assert len(result.violations) == 1
    violation = result.violations[0]
    assert violation.code == "BAN-001"
    assert violation.severity == "error"
    assert "banner" in violation.message.lower()
    assert violation.context.get("target_layer") == "L3"
    assert violation.context.get("field") == "summary"


# ---------------------------------------------------------------------------
# 2. Strict mode — re-raises HookViolation
# ---------------------------------------------------------------------------


def test_hook_raises_in_strict_mode_when_banner_present() -> None:
    """Strict mode re-raises the top-severity HookViolation per the
    lifecycle dispatcher's strict contract."""
    payload = {
        "task": {"id": "T-002"},
        "target_layer": "L1",
        "description": (
            "Build out the auth module. "
            + _BANNER_LITERAL_COMPLETE
            + " — banner leaked from prior run."
        ),
    }
    with pytest.raises(HookViolation) as excinfo:
        reject_subagent_banner_emission(payload, strict=True)
    assert excinfo.value.code == "BAN-001"
    assert excinfo.value.context.get("target_layer") == "L1"


# ---------------------------------------------------------------------------
# 3. Non-target-layer skip — L0 target is a no-op
# ---------------------------------------------------------------------------


def test_hook_is_noop_when_target_layer_is_l0() -> None:
    """When ``target_layer == "L0"`` the hook MUST be a no-op (banners
    are legitimate L0 operator-chat output). A clean HookResult with
    metadata pin proves the hook ran but found nothing to flag."""
    payload = {
        "task": {"id": "T-003"},
        "target_layer": "L0",
        "summary": _BANNER_LITERAL_ACTIVE,
    }
    result = reject_subagent_banner_emission(payload)
    assert isinstance(result, HookResult)
    assert result.violations == []
    assert result.metadata.get("checked_pattern") is not None


def test_hook_is_noop_when_target_layer_absent() -> None:
    """When the ``target_layer`` field is absent the hook MUST be a
    no-op — schema-level malformation is covered by the
    ``validate_dispatch`` default."""
    payload = {
        "task": {"id": "T-004"},
        "summary": _BANNER_LITERAL_ACTIVE,
    }
    result = reject_subagent_banner_emission(payload)
    assert result.violations == []


# ---------------------------------------------------------------------------
# 4. Opt-in wiring — register_pre_dispatch_extra wires the hook
# ---------------------------------------------------------------------------


def test_register_pre_dispatch_extra_wires_hook(opt_in_registered) -> None:
    """The opt-in registration helper appends
    ``reject_subagent_banner_emission`` to the ``pre_dispatch`` extras
    chain so ``run_hooks(pre_dispatch, ...)`` invokes it alongside the
    canonical defaults."""
    handlers = list_handlers(PRE_DISPATCH_EVENT)
    handler_names = [h.__name__ for h in handlers]
    assert "reject_subagent_banner_emission" in handler_names, (
        f"v12.4.0 PV-05 opt-in registration broken: "
        f"`register_pre_dispatch_extra()` MUST register the hook on "
        f"`pre_dispatch`; got handlers: {handler_names!r}"
    )


def test_hook_runs_via_dispatcher_run_hooks(opt_in_registered) -> None:
    """End-to-end through ``run_hooks``: a subagent dispatch with a
    banner literal surfaces the violation in the aggregate result."""
    payload = {
        "task": {"id": "T-005"},
        "target_layer": "L2",
        "acceptance_criteria": [
            "AC-1: feature X behaves correctly",
            _BANNER_LITERAL_ACTIVE,
        ],
    }
    result = run_hooks(PRE_DISPATCH_EVENT, payload, strict=False)
    ban_violations = [v for v in result.violations if v.code == "BAN-001"]
    assert len(ban_violations) == 1, (
        f"v12.4.0 PV-05 wiring broken: `run_hooks(pre_dispatch, ...)` "
        f"MUST surface the BAN-001 violation when the hook is "
        f"opt-in registered; got violations: {result.violations!r}"
    )
    assert ban_violations[0].context.get("field") == "acceptance_criteria[1]"


# ---------------------------------------------------------------------------
# 5. Defensive — non-dict payload + nested-banner exclusion
# ---------------------------------------------------------------------------


def test_hook_handles_non_dict_payload_defensively() -> None:
    """Defensive: non-dict payloads are NOT crashes — the hook returns
    clean (validate_dispatch handles schema-level malformation)."""
    result = reject_subagent_banner_emission(None)  # type: ignore[arg-type]
    assert result.violations == []
    result = reject_subagent_banner_emission("malformed")  # type: ignore[arg-type]
    assert result.violations == []
    result = reject_subagent_banner_emission(42)  # type: ignore[arg-type]
    assert result.violations == []


def test_hook_ignores_banner_inside_predecessor_artifacts() -> None:
    """The top-level-only discipline mirrors v12.2.0 PV-04: a banner
    appearing inside ``predecessor_artifacts[*].summary`` is IMMUTABLE
    historical evidence (e.g. the prior round's L0-authored predecessor
    summary literally captured the operator-facing banner). It MUST NOT
    flag — only fresh top-level emissions are operator-visible
    leakage."""
    payload = {
        "task": {"id": "T-006"},
        "target_layer": "L3",
        "predecessor_artifacts": [
            {
                "path": ".local/.agent/active/c1/STATUS.yaml",
                "summary": (
                    "round 1 baseline; operator saw " + _BANNER_LITERAL_ACTIVE + " at session start"
                ),
            }
        ],
    }
    result = reject_subagent_banner_emission(payload)
    assert result.violations == [], (
        f"v12.4.0 PV-05 contract violation: nested banner in "
        f"predecessor_artifacts[*].summary is IMMUTABLE historical "
        f"evidence and MUST NOT be flagged. Got violations: "
        f"{result.violations!r}"
    )


# ---------------------------------------------------------------------------
# 6. S-10 default-events preservation — the hook is NOT auto-wired
# ---------------------------------------------------------------------------


def test_hook_is_not_in_default_handlers() -> None:
    """The hook is **opt-in only** — it MUST NOT appear in the default
    handler chain returned by ``list_handlers(pre_dispatch)`` when
    ``register_pre_dispatch_extra()`` has NOT been called.

    This preserves the S-10 byte-identical default for v12.3.0 callers:
    a fresh process that loads ``devolaflow.lifecycle`` sees ONLY the
    v12.2.0 / earlier defaults + extras (``validate_dispatch`` default,
    ``validate_owned_files`` extra, ``reject_subagent_quality_score``
    extra) on ``pre_dispatch``. The banner hook surfaces only when the
    operator opts in via :func:`register_pre_dispatch_extra`.
    """
    handlers = list_handlers(PRE_DISPATCH_EVENT)
    handler_names = [h.__name__ for h in handlers]
    assert "reject_subagent_banner_emission" not in handler_names, (
        f"v12.4.0 PV-05 S-10 violation: "
        f"`reject_subagent_banner_emission` MUST NOT auto-register at "
        f"module load. Operators opt in via `register_pre_dispatch_extra()`. "
        f"Got handlers: {handler_names!r}"
    )
    # The EVENT constant is the canonical event name (= PRE_DISPATCH_EVENT).
    assert EVENT == PRE_DISPATCH_EVENT
