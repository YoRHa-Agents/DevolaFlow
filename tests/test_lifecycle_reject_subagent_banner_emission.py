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
4. The :func:`register_pre_dispatch_extra` helper (re-)wires the hook
   into the ``pre_dispatch`` extras chain.
5. Banner literal detection (positive case in a free-text field).
6. Defensive handling of non-dict payloads.
7. Nested ``predecessor_artifacts[*].summary`` carrying a banner does
   NOT flag (top-level-only discipline mirrors the v12.2.0 PV-04
   ``reject_subagent_quality_score`` precedent — historical evidence
   carried forward from prior L0-authored rounds is legitimate).
8. v15.0.0 G-038 flip 3: the hook IS default-wired at import time in
   ``lifecycle/__init__.py`` (graduating the v12.4.0 opt-in), and the
   documented opt-out :func:`unregister_pre_dispatch_extra` removes
   ONLY this hook from the extras chain.
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
    unregister_pre_dispatch_extra,
)

_BANNER_LITERAL_ACTIVE: str = "🌸 DevolaFlow v12.4.0 active · workflow: feature · mode: agent"
_BANNER_LITERAL_COMPLETE: str = "🌸 DevolaFlow v12.4.0 complete · 3 stages · 5 waves · 12 tasks"


@pytest.fixture
def opt_in_registered():
    """Ensure the hook is wired for wiring tests; restore extras at teardown.

    Since v15.0.0 (G-038 flip 3) the hook IS default-wired at import
    time in ``lifecycle/__init__.py`` — but sibling test modules call
    ``clear_hooks()`` which strips ALL extras (defaults stay), so the
    wiring tests re-register if absent (the v12.2.0 PV-04
    ``hook_registered`` fixture convention). The teardown clears
    extras and re-registers the import-time extras so sibling tests
    inheriting the cleaned registry keep the canonical chain.
    """
    if reject_subagent_banner_emission not in list_handlers(PRE_DISPATCH_EVENT):
        register_pre_dispatch_extra()
    yield
    clear_hooks(PRE_DISPATCH_EVENT)
    # Re-register the import-time extras that ``clear_hooks`` strips
    # alongside our hook, so sibling tests inheriting the cleaned
    # registry don't lose the v12.2.0 ``reject_subagent_quality_score``
    # + v15.0.0 banner wiring.
    from devolaflow.lifecycle import reject_subagent_quality_score
    from devolaflow.lifecycle.validate_owned_files import validate_owned_files

    register_hook(PRE_DISPATCH_EVENT, validate_owned_files)
    register_hook(PRE_DISPATCH_EVENT, reject_subagent_quality_score)
    register_pre_dispatch_extra()


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
# 6. v15.0.0 default wiring (G-038 flip 3) + documented opt-out
# ---------------------------------------------------------------------------


def test_hook_is_default_wired_at_import(opt_in_registered) -> None:
    """v15.0.0 G-038 flip 3: the hook IS default-wired into the
    ``pre_dispatch`` extras chain at import time.

    Two assertions, mirroring the inverted v12.4.0 pin:

    * source-level: ``lifecycle/__init__.py`` carries the canonical
      ``register_hook(_PRE_DISPATCH_EVENT, reject_subagent_banner_emission)``
      call (robust against sibling test modules having called
      ``clear_hooks()`` in this process);
    * registry-level: the handler chain includes the hook (the fixture
      re-registers if a sibling cleared extras, per the v12.2.0
      PV-04 convention).

    The hook never mutates the payload, so the S-10 byte-identical
    dispatch contract is preserved (pinned by
    ``tests/test_dispatch_emission_runs_hooks.py``).
    """
    import inspect

    import devolaflow.lifecycle as lifecycle_pkg

    pkg_source = inspect.getsource(lifecycle_pkg)
    assert "register_hook(_PRE_DISPATCH_EVENT, reject_subagent_banner_emission)" in pkg_source, (
        "v15.0.0 G-038 flip 3 violation: `reject_subagent_banner_emission` "
        "must be default-wired in lifecycle/__init__.py (graduating the "
        "v12.4.0 opt-in per the DEFAULTS-PERMISSIVE-IN-MINOR / "
        "STRICT-IN-NEXT-MAJOR pattern)"
    )
    handler_names = [h.__name__ for h in list_handlers(PRE_DISPATCH_EVENT)]
    assert "reject_subagent_banner_emission" in handler_names
    # The EVENT constant is the canonical event name (= PRE_DISPATCH_EVENT).
    assert EVENT == PRE_DISPATCH_EVENT


def test_unregister_pre_dispatch_extra_opts_out(opt_in_registered) -> None:
    """The documented flip-3 opt-out: ``unregister_pre_dispatch_extra()``
    removes ONLY the banner hook from the extras chain — sibling extras
    (``reject_subagent_quality_score``) and the ``validate_dispatch``
    default stay registered. Idempotent: a second call returns False.
    """
    assert unregister_pre_dispatch_extra() is True
    handler_names = [h.__name__ for h in list_handlers(PRE_DISPATCH_EVENT)]
    assert "reject_subagent_banner_emission" not in handler_names
    assert "validate_dispatch" in handler_names, "defaults must survive the opt-out"
    assert "reject_subagent_quality_score" in handler_names, (
        "the opt-out must be per-hook — sibling extras stay registered"
    )
    # Idempotent no-op on the second call.
    assert unregister_pre_dispatch_extra() is False
    # Opt back in — the helper re-wires the hook.
    register_pre_dispatch_extra()
    assert "reject_subagent_banner_emission" in [
        h.__name__ for h in list_handlers(PRE_DISPATCH_EVENT)
    ]
