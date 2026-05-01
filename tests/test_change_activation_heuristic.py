"""Tests for the v9.1.2 PV-02 change-driven activation heuristic.

Pins the public contract of
:mod:`devolaflow.skills.change_activation` per Architecture rule
**A-6** "Workspace Engagement Auto-Activation" (see
``.rules/architecture.mdc``):

1. :func:`classify_complexity` returns the correct
   :data:`Complexity` literal across the documented thresholds
   (TRIVIAL / SIMPLE / STANDARD / COMPLEX).
2. :func:`activation_verdict` returns the correct
   :data:`ActivationVerdict` literal across the verdict matrix
   (MUST / SHOULD / NO).
3. :func:`from_env` is the single env-var read site and applies R5
   strict matching ("1" only) — A-6.2.
4. The opt-out (``--no-change``) overrides any positive verdict
   even when the env flag is ON — A-6.3.

Each test runs in O(1) — pure-function inputs, no filesystem I/O,
no env-var monkeypatching needed for the verdict / classifier
suites (they pass an explicit env mapping to :func:`from_env` when
exercising it).
"""

from __future__ import annotations

import pytest

from devolaflow.skills.change_activation import (
    ENV_FLAG_NAME,
    ENV_FLAG_TRUTHY,
    ActivationVerdict,
    Complexity,
    activation_verdict,
    classify_complexity,
    from_env,
)

# ── classify_complexity ────────────────────────────────────────────────


def test_classify_complexity_trivial() -> None:
    """Single file + < 20 LOC → TRIVIAL.

    Mirrors the SKILL.md §"Quick Action Decision" Trivial row verbatim:
    "Single file, < 20 lines, obvious fix".
    """
    assert classify_complexity(files_count=1, loc_estimate=5) == "TRIVIAL"
    assert classify_complexity(files_count=1, loc_estimate=19) == "TRIVIAL"
    assert classify_complexity(files_count=0, loc_estimate=0) == "TRIVIAL"


@pytest.mark.parametrize(
    ("files_count", "loc_estimate", "expected"),
    [
        # SIMPLE row — 1-3 files, clear scope
        (2, 50, "SIMPLE"),
        (3, 100, "SIMPLE"),
        (1, 25, "SIMPLE"),  # single file but > 20 LOC bumps to SIMPLE
        # STANDARD row — 3-10 files, needs design or review
        (4, 150, "STANDARD"),
        (10, 500, "STANDARD"),
        # COMPLEX row — 10+ files, cross-cutting, multi-day
        (11, 600, "COMPLEX"),
        (50, 5000, "COMPLEX"),
    ],
)
def test_classify_complexity_simple_standard_complex(
    files_count: int,
    loc_estimate: int,
    expected: Complexity,
) -> None:
    """Cross-cell parametrize over the 3 non-trivial complexity tiers.

    Each row mirrors the SKILL.md §"Quick Action Decision" row whose
    threshold the inputs straddle. A-6.1 pins the classifier as the
    sole authority for these thresholds.
    """
    assert classify_complexity(files_count, loc_estimate) == expected


def test_classify_complexity_cross_cutting_forces_standard_floor() -> None:
    """``is_cross_cutting=True`` upgrades to at least STANDARD regardless of size.

    A single-file change that touches the layout invariant or env-flag
    inventory MUST be at least STANDARD per the cycle plan §PV-02 (the
    heuristic is conservative — better to scaffold a change folder for
    a cross-cutting trivial edit than to skip the audit trail).
    """
    assert classify_complexity(1, 5, is_cross_cutting=True) == "STANDARD"
    assert classify_complexity(2, 50, is_cross_cutting=True) == "STANDARD"
    # Very large + cross-cutting still bumps past STANDARD into COMPLEX.
    assert classify_complexity(20, 1000, is_cross_cutting=True) == "COMPLEX"


def test_classify_complexity_negative_inputs_raise() -> None:
    """S-5: negative inputs raise ValueError instead of silently coercing."""
    with pytest.raises(ValueError, match="files_count must be >= 0"):
        classify_complexity(-1, 0)
    with pytest.raises(ValueError, match="loc_estimate must be >= 0"):
        classify_complexity(0, -5)


# ── activation_verdict ─────────────────────────────────────────────────


def test_activation_verdict_must_for_complex_with_env() -> None:
    """COMPLEX + env=True + opt_out=False → MUST_OPEN_CHANGE.

    Per A-6 verdict matrix: the env-flag-on path for the highest
    complexity tier is the MUST mandate (L0 must scaffold
    ``.local/.agent/active/<id>/`` before dispatching the first L1
    stage).
    """
    assert (
        activation_verdict("COMPLEX", env_agent_workspace=True, opt_out=False) == "MUST_OPEN_CHANGE"
    )


def test_activation_verdict_should_for_standard_with_env() -> None:
    """STANDARD + env=True + opt_out=False → SHOULD_OPEN_CHANGE.

    Pins the milder verdict — operators are advised to engage but the
    `--no-change` opt-out remains available (per A-6.3).
    """
    assert (
        activation_verdict("STANDARD", env_agent_workspace=True, opt_out=False)
        == "SHOULD_OPEN_CHANGE"
    )


@pytest.mark.parametrize(
    "complexity",
    ["TRIVIAL", "SIMPLE", "STANDARD", "COMPLEX"],
)
def test_activation_verdict_no_change_without_env(complexity: Complexity) -> None:
    """env=False → NO_CHANGE for any complexity (R5 strict default-OFF).

    The byte-stable proof that A-6's behaviour is fully gated by the
    env flag — when ``DEVOLAFLOW_AGENT_WORKSPACE`` is absent (or
    anything other than the literal "1"), the verdict is NO_CHANGE
    regardless of how complex the task is. Operators get the v9.1.1
    workspace-scan READ behaviour but no auto-scaffold WRITE.
    """
    assert activation_verdict(complexity, env_agent_workspace=False, opt_out=False) == "NO_CHANGE"


@pytest.mark.parametrize(
    "complexity",
    ["TRIVIAL", "SIMPLE", "STANDARD", "COMPLEX"],
)
def test_activation_verdict_opt_out_overrides(complexity: Complexity) -> None:
    """opt_out=True → NO_CHANGE for any complexity even with env=True.

    Pins A-6.3 — the ``--no-change`` opt-out is the authoritative
    escape hatch; the operator's explicit refusal to engage trumps
    the heuristic regardless of complexity tier.
    """
    assert activation_verdict(complexity, env_agent_workspace=True, opt_out=True) == "NO_CHANGE"


def test_activation_verdict_simple_or_trivial_always_no_change() -> None:
    """SIMPLE / TRIVIAL never trigger MUST or SHOULD (NO_CHANGE always).

    Pins the small-task path: matching ceremony to complexity is the
    SKILL.md §"Quick Action Decision" rule. The change-driven workflow
    is overkill for a 2-file fix.
    """
    for complexity in ("TRIVIAL", "SIMPLE"):
        for env in (True, False):
            for opt_out in (True, False):
                assert activation_verdict(complexity, env, opt_out=opt_out) == "NO_CHANGE", (
                    f"unexpected verdict for {complexity=}, {env=}, {opt_out=}"
                )


def test_activation_verdict_invalid_complexity_raises() -> None:
    """S-5: unknown complexity literal raises ValueError, never silently coerces."""
    with pytest.raises(ValueError, match="complexity 'NOT_A_TIER' is not one of"):
        activation_verdict("NOT_A_TIER", env_agent_workspace=True)  # type: ignore[arg-type]


# ── from_env (single env-var read site) ────────────────────────────────


def test_from_env_truthy_only_on_literal_one() -> None:
    """R5 strict: only the literal "1" is truthy; nothing else.

    The ENV_FLAG_TRUTHY constant pins the contract; every variant
    other than the exact literal returns False so caches/mocks/tests
    stay deterministic.
    """
    assert from_env({ENV_FLAG_NAME: "1"}) is True
    assert from_env({ENV_FLAG_NAME: "true"}) is False
    assert from_env({ENV_FLAG_NAME: "0"}) is False
    assert from_env({ENV_FLAG_NAME: ""}) is False
    assert from_env({}) is False
    assert from_env({"OTHER_FLAG": "1"}) is False


def test_from_env_constants_pin_public_contract() -> None:
    """ENV_FLAG_NAME + ENV_FLAG_TRUTHY are the public contract surface."""
    assert ENV_FLAG_NAME == "DEVOLAFLOW_AGENT_WORKSPACE"
    assert ENV_FLAG_TRUTHY == "1"


def test_verdict_string_values_are_stable() -> None:
    """Pin the three verdict string literals — operators rely on these.

    Per A-6.1 the three verdict strings are the sole public contract
    of the module. Changing any literal is a release blocker (it
    would break every operator script that grep'd for the strings).
    """
    must: ActivationVerdict = "MUST_OPEN_CHANGE"
    should: ActivationVerdict = "SHOULD_OPEN_CHANGE"
    no: ActivationVerdict = "NO_CHANGE"
    assert {must, should, no} == {"MUST_OPEN_CHANGE", "SHOULD_OPEN_CHANGE", "NO_CHANGE"}
