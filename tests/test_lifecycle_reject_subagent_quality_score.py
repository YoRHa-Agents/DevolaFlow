"""v12.2.0 PV-04 — `reject_subagent_quality_score` pre_dispatch hook tests.

Closes the v12.0.0/v12.1.0 telegraph "Runtime enforcement of forbidden
patterns (e.g., a `pre_dispatch` hook that rejects L3 reports carrying
`quality_score` fields)" per `.local/research/v12.2.0_gap_analysis.md`
§2 D-4. The hook is wired as a `pre_dispatch` extra (NOT a default
replacement) per the S-10 byte-id contract — operators registering
their own extras on `pre_dispatch` see no behavioural drift; the
validate_dispatch default still runs FIRST.

Test surface covers (per the v12.2.0 PV-04 dispatch AC, updated for
the v15.0.0 G-038 flip 2 strict graduation):

1. STRICT default (since v15.0.0): a direct invocation with
   `quality_score` and no explicit `strict` argument raises
   HookViolation.
2. Opt-out path: explicit `strict=False` restores the v12.2.0..v14.x
   permissive warn-and-return behaviour.
3. A clean dispatch (no `quality_score` field) returns a HookResult
   with NO violations.
4. The hook is wired into the lifecycle event chain so `run_hooks`
   invocations against `pre_dispatch` execute it (the chain invokes
   handlers permissively and centralises the strict policy — S-10
   emission is unaffected by the flip).
5. The hook ignores nested `quality_score` fields inside
   `predecessor_artifacts` historical evidence, but DOES scan the
   `metrics` / `self_check` evidence blocks (the v15.0.0 nested-block
   scan; `metrics.gate_input_score` stays legitimate).
"""

from __future__ import annotations

import pytest

from devolaflow.lifecycle import (
    PRE_DISPATCH_EVENT,
    HookResult,
    HookViolation,
    list_handlers,
    register_hook,
    reject_subagent_quality_score,
    run_hooks,
)


@pytest.fixture
def hook_registered():
    """Ensure the v12.2.0 PV-04 hook is wired before each wiring test.

    Other test modules (e.g. tests/test_lifecycle_hooks.py) call
    `clear_hooks()` which clears the extras registry. Since
    `reject_subagent_quality_score` is registered as an extra (per the
    S-10 byte-id contract that the defaults stay immutable), it gets
    cleared by those teardowns. This fixture re-registers the hook so
    the wiring tests are robust against extras being cleared between
    test modules.

    The W-18 v12.2.0 PV-04 ghost-audit stanza is the canonical
    source-of-truth pin for the lifecycle/__init__.py
    ``register_hook(_PRE_DISPATCH_EVENT, reject_subagent_quality_score)``
    call — that lint runs at module import time and does NOT depend on
    extras-registry state.
    """
    handlers = list_handlers(PRE_DISPATCH_EVENT)
    if reject_subagent_quality_score not in handlers:
        register_hook(PRE_DISPATCH_EVENT, reject_subagent_quality_score)
    yield


# ---------------------------------------------------------------------------
# 1. Opt-out path — explicit strict=False keeps the permissive behaviour
# ---------------------------------------------------------------------------


def test_hook_attaches_violation_with_explicit_strict_false_opt_out() -> None:
    """The documented v15.0.0 opt-out: an explicit `strict=False` call
    returns a HookResult with the violation attached (the
    v12.2.0..v14.x permissive behaviour); no raise per the S-5
    explicit-error-state discipline."""
    payload = {
        "task": {"id": "T-001"},
        "quality_score": 18,  # forbidden — L0-only per SKILL.md
    }
    result = reject_subagent_quality_score(payload, strict=False)
    assert isinstance(result, HookResult)
    assert len(result.violations) == 1
    violation = result.violations[0]
    assert violation.code == "QS-001"
    assert violation.severity == "error"
    assert "quality_score" in violation.message
    # S-5: the strict-failure message names the opt-out surface.
    assert "strict=False" in violation.message


def test_hook_returns_clean_result_when_field_absent() -> None:
    """A dispatch payload WITHOUT `quality_score` returns a clean
    HookResult with no violations (strict default is a no-op on clean
    payloads; `gate.quality` stays legitimate — the nested scan covers
    ONLY `metrics` / `self_check`)."""
    payload = {
        "task": {"id": "T-002"},
        "gate": {"coverage": 80, "quality": 85},
    }
    result = reject_subagent_quality_score(payload)
    assert isinstance(result, HookResult)
    assert result.violations == []
    assert result.metadata.get("checked_key") == "quality_score"


# ---------------------------------------------------------------------------
# 2. STRICT default (v15.0.0 G-038 flip 2) — raises HookViolation
# ---------------------------------------------------------------------------


def test_hook_raises_by_default_when_field_present() -> None:
    """v15.0.0 G-038 flip 2: the STRICT default — a direct invocation
    with NO explicit `strict` argument re-raises the top-severity
    HookViolation (the v12.2.0..v14.x default merely warned)."""
    payload = {
        "task": {"id": "T-003"},
        "quality_score": 15,
    }
    with pytest.raises(HookViolation) as excinfo:
        reject_subagent_quality_score(payload)
    assert excinfo.value.code == "QS-001"
    assert "strict=False" in excinfo.value.message, (
        "S-5: the strict raise must name the opt-out (strict=False)"
    )


def test_hook_raises_in_strict_mode_when_field_present() -> None:
    """Explicit `strict=True` re-raises the top-severity HookViolation
    per the lifecycle dispatcher's strict contract (unchanged by the
    default flip)."""
    payload = {
        "task": {"id": "T-003b"},
        "quality_score": 15,
    }
    with pytest.raises(HookViolation) as excinfo:
        reject_subagent_quality_score(payload, strict=True)
    assert excinfo.value.code == "QS-001"


def test_hook_does_not_raise_in_strict_mode_when_field_absent() -> None:
    """Strict mode is a no-op when there are no violations to surface."""
    payload = {
        "task": {"id": "T-004"},
        "accept": ["AC-1: returns 200"],
    }
    result = reject_subagent_quality_score(payload, strict=True)
    assert isinstance(result, HookResult)
    assert result.violations == []


def test_hook_scans_metrics_and_self_check_blocks() -> None:
    """v15.0.0 nested-block scan (ADR-007 phase split): `quality_score`
    / `quality` keys inside the `metrics` / `self_check` evidence
    blocks are rejected, while `metrics.gate_input_score` (the G-013
    one-doctrine rename) stays legitimate."""
    # metrics.gate_input_score alone is clean evidence — no violation.
    clean = {
        "task": {"id": "T-010"},
        "metrics": {"tests_passed": 5, "tests_failed": 0, "gate_input_score": 92},
        "self_check": {"goal_anchor": "feature X", "simplicity": "none"},
    }
    result = reject_subagent_quality_score(clean)
    assert result.violations == []

    # quality_score smuggled inside metrics → raises by default.
    smuggled_metrics = {
        "task": {"id": "T-011"},
        "metrics": {"tests_passed": 5, "quality_score": 17},
    }
    with pytest.raises(HookViolation) as excinfo:
        reject_subagent_quality_score(smuggled_metrics)
    assert excinfo.value.code == "QS-001"
    assert excinfo.value.context.get("location") == "'metrics' block"

    # bare `quality` inside self_check → flagged too (opt-out view).
    smuggled_self_check = {
        "task": {"id": "T-012"},
        "self_check": {"quality": 9.5},
    }
    result = reject_subagent_quality_score(smuggled_self_check, strict=False)
    assert [v.context.get("location") for v in result.violations] == ["'self_check' block"]
    assert [v.context.get("field") for v in result.violations] == ["quality"]


# ---------------------------------------------------------------------------
# 3. Wiring — hook is registered on pre_dispatch event
# ---------------------------------------------------------------------------


def test_hook_is_wired_into_pre_dispatch_event_chain(hook_registered) -> None:
    """The v12.2.0 PV-04 wiring registers `reject_subagent_quality_score`
    as a `pre_dispatch` extra so `run_hooks(pre_dispatch, ...)` invokes
    it alongside the canonical `validate_dispatch` default. The fixture
    ensures the hook is registered even if a prior test module called
    `clear_hooks()` (which strips extras per the public API contract)."""
    handlers = list_handlers(PRE_DISPATCH_EVENT)
    handler_names = [h.__name__ for h in handlers]
    assert "reject_subagent_quality_score" in handler_names, (
        f"v12.2.0 PV-04 wiring violation: `reject_subagent_quality_score` "
        f"must be registered on `pre_dispatch`; got handlers: {handler_names!r}"
    )


def test_hook_runs_via_dispatcher_run_hooks(hook_registered) -> None:
    """End-to-end through `run_hooks`: a dispatch with `quality_score`
    surfaces the violation in the aggregate result."""
    payload = {
        "task": {"id": "T-005"},
        "accept": ["AC-1: behaviour X"],
        "quality_score": 12,
    }
    result = run_hooks(PRE_DISPATCH_EVENT, payload, strict=False)
    qs_violations = [v for v in result.violations if v.code == "QS-001"]
    assert len(qs_violations) == 1, (
        f"v12.2.0 PV-04 wiring violation: `run_hooks(pre_dispatch, ...)` must "
        f"surface the QS-001 violation; got violations: {result.violations!r}"
    )


# ---------------------------------------------------------------------------
# 4. Top-level-only discipline — nested quality_score is NOT flagged
# ---------------------------------------------------------------------------


def test_hook_ignores_nested_quality_score_in_predecessor_artifacts() -> None:
    """Predecessor artifacts may legitimately carry historical L0 scoring
    as evidence; the top-level-only discipline avoids flagging that."""
    payload = {
        "task": {"id": "T-006"},
        "pred": [
            {
                "path": ".local/.agent/active/c1/STATUS.yaml",
                "summary": "round 1 baseline; L0 awarded quality_score=17",
                "quality_score": 17,  # nested — historical, NOT a fresh L3 report
            }
        ],
    }
    result = reject_subagent_quality_score(payload)
    assert result.violations == [], (
        f"v12.2.0 PV-04 contract: nested `quality_score` in predecessor "
        f"artifacts is legitimate read-only evidence; the top-level-only "
        f"discipline MUST NOT flag it. Got violations: {result.violations!r}"
    )


def test_hook_handles_non_dict_payload_defensively() -> None:
    """Defensive: non-dict payloads are NOT crashes — the hook returns
    clean (validate_dispatch handles schema-level malformation)."""
    result = reject_subagent_quality_score(None)  # type: ignore[arg-type]
    assert result.violations == []
    result = reject_subagent_quality_score("malformed")  # type: ignore[arg-type]
    assert result.violations == []
