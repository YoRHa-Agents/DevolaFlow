"""v17.0.0 R2 (G17-B2 / D-R2-5) — ``assert_layer_token_budget`` pre_dispatch hook tests.

Closes the G17-B2 gap from ``.local/research/v17.0.0_gap_analysis.md``:
``meta.layer_token_budgets`` had no dispatch-time consumer —
``build_dispatch_record`` records overruns but never raises. The hook
under test estimates the dispatch payload with the EXACT telemetry
measurement pipeline (``estimate_tokens(stable_yaml(payload))``) and
surfaces ``ALB001`` (severity ``error``) when the estimate exceeds the
target layer's budget from ``harness.telemetry.LAYER_TOKEN_BUDGETS``.

Test surface (7 functions, W-17 cap ≤ 8 per the R2 task decomposition):

1. Within-budget + legacy/unresolvable attribution → PASS, non-mutating
   (parametrized over every telemetry attribution path, incl. the
   first-found-wins mirror of ``_dispatch_layer``).
2. Boundary (measured == budget) passes; overrun (budget + 1) attaches
   ALB001 in lite mode without mutating the payload.
3. Overrun raises ALB001 under ``strict=True`` for each layer.
4. Defensive inputs (non-dict, unserializable) never block.
5. Wiring — registered as the LAST ``pre_dispatch`` extra, surfaces
   ALB001 through ``run_hooks``.
6. Parity — ``context_profiles.yaml#meta.layer_token_budgets`` equals
   ``LAYER_TOKEN_BUDGETS`` (A-5 single owner cannot drift).
7. E2E — the strict emission default blocks an over-budget dispatch out
   of ``ProposalGenerator.generate_round_dispatch``; the documented
   ``pre_dispatch_strict=False`` escape warns and returns unchanged.

ALB002 (declared ``gate.token_budget`` soft check) is intentionally
ABSENT: ``gate.token_budget`` is the v8.0.0 P-03 circuit breaker for
CUMULATIVE gate-evaluation usage (``{max_tokens, warn_at, break_at}``
per ``schemas/lean-dispatch.yaml``), not a payload-size declaration.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

import devolaflow.lifecycle.assert_layer_budget as assert_layer_budget_module
from devolaflow.feedback import ProposalGenerator
from devolaflow.harness.telemetry import LAYER_TOKEN_BUDGETS, stable_yaml
from devolaflow.lifecycle import (
    PRE_DISPATCH_EVENT,
    HookResult,
    HookViolation,
    list_handlers,
    register_hook,
    run_hooks,
)
from devolaflow.lifecycle.assert_layer_budget import assert_layer_token_budget
from devolaflow.task_adaptive_selector import estimate_tokens

_CONTEXT_PROFILES = Path("workflow-system/agent/context_profiles.yaml")

# context_profiles.yaml meta key ↔ telemetry layer token (A-3 hierarchy).
_YAML_KEY_TO_LAYER = {"l0_project": "L0", "l1_wave": "L1", "l2_task": "L2"}


@pytest.fixture
def hook_registered():
    """Re-register the hook if a sibling module's ``clear_hooks()`` stripped it.

    The v12.2.0 PV-04 ``hook_registered`` fixture convention: the hook IS
    default-wired at import time in ``lifecycle/__init__.py``, but sibling
    test modules call ``clear_hooks()`` which strips ALL extras.
    """
    if assert_layer_token_budget not in list_handlers(PRE_DISPATCH_EVENT):
        register_hook(PRE_DISPATCH_EVENT, assert_layer_token_budget)
    yield


def _patch_measured(monkeypatch, tokens: int) -> None:
    """Pin the hook's token estimate for deterministic overrun tests."""
    monkeypatch.setattr(
        assert_layer_budget_module,
        "estimate_tokens",
        lambda text: tokens,
    )


# ---------------------------------------------------------------------------
# 1. Within-budget + legacy attribution — PASS, non-mutating
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("payload", "expected_layer"),
    [
        # Every telemetry attribution path, mirrored from _dispatch_layer.
        ({"task_id": "T-1", "layer": "L2"}, "L2"),
        ({"task_id": "T-2", "hdr": {"to_layer": "task"}}, "L2"),
        ({"task_id": "T-3", "change_context": {"to_layer": "wave"}}, "L1"),
        ({"task_id": "T-4", "header": {"layer": "project"}}, "L0"),
        ({"task_id": "T-5", "to_layer": "L0"}, "L0"),
        # Legacy / unresolvable attribution → PASS (never blocked).
        ({"task_id": "T-6", "accept": ["AC-1"]}, None),
        ({"task_id": "T-7", "layer": "L9"}, None),
        ({"task_id": "T-8", "layer": "   "}, None),
        # First-found-wins mirror: a malformed high-priority field fails
        # attribution WITHOUT falling through to the valid top-level layer
        # (telemetry would not record this dispatch either).
        ({"task_id": "T-9", "hdr": {"to_layer": None}, "layer": "L2"}, None),
    ],
)
def test_within_budget_and_legacy_attribution_pass(payload, expected_layer) -> None:
    control = copy.deepcopy(payload)

    result = assert_layer_token_budget(payload)
    assert isinstance(result, HookResult)
    assert result.passed is True
    assert result.violations == []
    if expected_layer is None:
        assert result.metadata["reason"] == "no telemetry-resolvable layer attribution"
    else:
        assert result.metadata["layer"] == expected_layer
        assert result.metadata["budget_tokens"] == LAYER_TOKEN_BUDGETS[expected_layer]
        assert result.metadata["measured_tokens"] == estimate_tokens(stable_yaml(payload))

    # Strict is a no-op on clean payloads, and the hook never mutates.
    strict_result = assert_layer_token_budget(payload, strict=True)
    assert strict_result.passed is True
    assert payload == control, "hook must never mutate the payload (S-10 byte-identity)"


# ---------------------------------------------------------------------------
# 2. Boundary + overrun in lite mode (strict=False default)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("delta", "expect_pass"), [(0, True), (1, False)])
def test_boundary_passes_and_overrun_attaches_alb001_in_lite_mode(
    monkeypatch, delta, expect_pass
) -> None:
    budget = LAYER_TOKEN_BUDGETS["L1"]
    measured = budget + delta
    _patch_measured(monkeypatch, measured)
    payload = {"task_id": "T-lite", "layer": "L1", "accept": ["AC-1"]}
    control = copy.deepcopy(payload)

    result = assert_layer_token_budget(payload)

    assert payload == control, "lite mode must not mutate the payload"
    if expect_pass:
        assert result.passed is True
        assert result.violations == []
        assert result.metadata["measured_tokens"] == budget
        return

    assert result.passed is False
    assert len(result.violations) == 1
    violation = result.violations[0]
    assert violation.code == "ALB001"
    assert violation.severity == "error"
    assert "'L1'" in violation.message
    assert str(measured) in violation.message
    assert str(budget) in violation.message
    assert violation.context["layer"] == "L1"
    assert violation.context["measured_tokens"] == measured
    assert violation.context["budget_tokens"] == budget


# ---------------------------------------------------------------------------
# 3. Overrun raises under strict — every layer budget
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("layer", sorted(LAYER_TOKEN_BUDGETS))
def test_overrun_raises_alb001_under_strict_for_each_layer(monkeypatch, layer) -> None:
    budget = LAYER_TOKEN_BUDGETS[layer]
    _patch_measured(monkeypatch, budget + 1)
    payload = {"task_id": f"T-{layer}", "layer": layer}

    with pytest.raises(HookViolation) as excinfo:
        assert_layer_token_budget(payload, strict=True)
    assert excinfo.value.code == "ALB001"
    assert excinfo.value.severity == "error"
    assert excinfo.value.context["budget_tokens"] == budget


# ---------------------------------------------------------------------------
# 4. Defensive — non-dict + unserializable payloads never block
# ---------------------------------------------------------------------------


def test_defensive_inputs_never_block(caplog) -> None:
    for bad in (None, "malformed", 42):
        result = assert_layer_token_budget(bad)  # type: ignore[arg-type]
        assert result.passed is True
        assert result.metadata["reason"] == "payload is not a dict"

    # A payload that resolves a layer but cannot be YAML-serialized is
    # PASSED with a WARNING (S-5 explicit log; measurement never blocks).
    unserializable = {"task_id": "T-blob", "layer": "L2", "blob": object()}
    with caplog.at_level("WARNING", logger="devolaflow.lifecycle.assert_layer_budget"):
        result = assert_layer_token_budget(unserializable, strict=True)
    assert result.passed is True
    assert result.metadata["reason"] == "token measurement failed"
    assert any("could not measure" in rec.message for rec in caplog.records)


# ---------------------------------------------------------------------------
# 5. Wiring — LAST pre_dispatch extra; surfaces ALB001 via run_hooks
# ---------------------------------------------------------------------------


def test_registered_as_last_pre_dispatch_extra_and_surfaces_via_run_hooks(
    monkeypatch, hook_registered
) -> None:
    import inspect

    import devolaflow.lifecycle as lifecycle_pkg

    pkg_source = inspect.getsource(lifecycle_pkg)
    anchor = "register_hook(_PRE_DISPATCH_EVENT, assert_layer_token_budget)"
    banner_anchor = "register_hook(_PRE_DISPATCH_EVENT, reject_subagent_banner_emission)"
    assert anchor in pkg_source, (
        "v17.0.0 R2 wiring violation: assert_layer_token_budget must be "
        "default-wired as a pre_dispatch extra in lifecycle/__init__.py"
    )
    assert pkg_source.index(anchor) > pkg_source.index(banner_anchor), (
        "the layer-budget assertion must register AFTER the existing extras"
    )
    assert assert_layer_token_budget in list_handlers(PRE_DISPATCH_EVENT)

    _patch_measured(monkeypatch, LAYER_TOKEN_BUDGETS["L2"] + 1)
    payload = {"task_id": "T-chain", "layer": "L2", "accept": ["AC-1"]}
    result = run_hooks(PRE_DISPATCH_EVENT, payload, strict=False)
    alb_violations = [v for v in result.violations if v.code == "ALB001"]
    assert len(alb_violations) == 1, (
        f"run_hooks(pre_dispatch, ...) must surface ALB001 for an "
        f"over-budget payload; got violations: {result.violations!r}"
    )


# ---------------------------------------------------------------------------
# 6. Parity — context_profiles.yaml meta cannot drift from the constant
# ---------------------------------------------------------------------------


def test_layer_token_budgets_parity_with_context_profiles(project_root: Path) -> None:
    """A-5 single owner: `harness.telemetry.LAYER_TOKEN_BUDGETS` owns the
    numbers; `context_profiles.yaml#meta.layer_token_budgets` (the A-3
    prompt-side surface) must carry the identical values."""
    data = yaml.safe_load((project_root / _CONTEXT_PROFILES).read_text(encoding="utf-8"))
    declared = data["meta"]["layer_token_budgets"]
    assert set(declared) == set(_YAML_KEY_TO_LAYER), (
        f"context_profiles.yaml meta.layer_token_budgets keys drifted: {sorted(declared)!r}"
    )
    mapped = {_YAML_KEY_TO_LAYER[key]: value for key, value in declared.items()}
    assert mapped == LAYER_TOKEN_BUDGETS, (
        f"layer token budgets drifted: context_profiles.yaml declares {mapped!r} "
        f"but harness.telemetry.LAYER_TOKEN_BUDGETS is {LAYER_TOKEN_BUDGETS!r}"
    )


# ---------------------------------------------------------------------------
# 7. E2E — strict emission default blocks an over-budget dispatch
# ---------------------------------------------------------------------------


def test_strict_emission_blocks_over_budget_dispatch(
    monkeypatch, tmp_path, caplog, hook_registered
) -> None:
    """G17-B2 closure end-to-end: `ProposalGenerator.generate_round_dispatch`
    (strict pre_dispatch by default since v15.0.0 G-038) raises ALB001 for
    an over-budget dispatch; the documented `pre_dispatch_strict=False`
    escape warns via the lifecycle logger and returns the payload unchanged."""
    monkeypatch.chdir(tmp_path)  # keep post_dispatch telemetry away from the repo
    _patch_measured(monkeypatch, LAYER_TOKEN_BUDGETS["L2"] + 1)
    base = {
        "task_id": "T-R2-B2",
        "task_type": "refactor",
        "layer": "L2",
        "accept": ["the layer budget assertion blocks over-budget dispatches"],
        "context": {
            "applicable_rules": {"loading_strategy": "standard"},
            "target_files": ["src/foo.py"],
        },
    }
    control = copy.deepcopy(base)

    with pytest.raises(HookViolation) as excinfo:
        ProposalGenerator().generate_round_dispatch(base, None, round_num=1)
    assert excinfo.value.code == "ALB001"

    with caplog.at_level("WARNING", logger="devolaflow.lifecycle.dispatcher"):
        released = ProposalGenerator(pre_dispatch_strict=False).generate_round_dispatch(
            base, None, round_num=1
        )
    assert released == control, "the permissive escape must return the dispatch unchanged"
    assert any("ALB001" in rec.message for rec in caplog.records), (
        "S-5: the lite path must still WARN via the lifecycle logger"
    )
