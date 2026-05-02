"""Regression tests for the v9.3.0 PV-06 simple-task auto-shortcut.

Pin contract for
:func:`devolaflow.skills.change_activation.shortcut_verdict` and
:func:`devolaflow.skills.change_activation.shortcut_from_env`:

* SIMPLE / TRIVIAL complexity + ``DEVOLAFLOW_SIMPLE_SHORTCUT=1`` →
  ``"SHORTCUT_SIMPLE"`` verdict (dispatcher may skip L1 + L2).
* STANDARD / COMPLEX complexity → always ``"NO_SHORTCUT"`` (full
  L0→L1→L2→L3 chain mandated).
* Env flag absent / wrong value → ``"NO_SHORTCUT"`` for ANY
  complexity (R5 strict default-OFF).
* Opt-out parameter wins regardless of env state.
* The 3-valued :data:`ActivationVerdict` (MUST_OPEN_CHANGE /
  SHOULD_OPEN_CHANGE / NO_CHANGE) contract is UNCHANGED — the
  shortcut surface is orthogonal.

W-17 NEW test functions: 9 (within +30/PV cap; cycle-cumulative
running tally +36 of +150).

Closes D-E-4 from `.local/research/v9.3.0_gap_analysis.md` §1.4.
"""

from __future__ import annotations

import pytest

from devolaflow.skills.change_activation import (
    SHORTCUT_FLAG_NAME,
    SHORTCUT_FLAG_TRUTHY,
    activation_verdict,
    classify_complexity,
    from_env,
    shortcut_from_env,
    shortcut_verdict,
)

# ---------------------------------------------------------------------------
# §1 — Constants + module surface.
# ---------------------------------------------------------------------------


def test_shortcut_flag_constants_match_w_20_naming() -> None:
    """The flag name + truthy literal match the v9.3.0 PV-06 spec.

    Pinned because operators set the flag verbatim — a future PV that
    accidentally renamed the constant would break every operator's
    shell config without surfacing.
    """
    assert SHORTCUT_FLAG_NAME == "DEVOLAFLOW_SIMPLE_SHORTCUT"
    assert SHORTCUT_FLAG_TRUTHY == "1"


# ---------------------------------------------------------------------------
# §2 — shortcut_from_env (R5 strict env-var read).
# ---------------------------------------------------------------------------


def test_shortcut_from_env_strict_one() -> None:
    """Only the literal string ``"1"`` activates — every other value is OFF.

    R5 strict pattern matches every other DevolaFlow opt-in flag
    per `references/env-flags.md` §6 conjunction contract.
    """
    assert shortcut_from_env({SHORTCUT_FLAG_NAME: "1"}) is True
    # Any other value, including conventionally-truthy strings, is OFF.
    assert shortcut_from_env({SHORTCUT_FLAG_NAME: "true"}) is False
    assert shortcut_from_env({SHORTCUT_FLAG_NAME: "yes"}) is False
    assert shortcut_from_env({SHORTCUT_FLAG_NAME: "on"}) is False
    assert shortcut_from_env({SHORTCUT_FLAG_NAME: "01"}) is False
    assert shortcut_from_env({SHORTCUT_FLAG_NAME: " 1"}) is False
    assert shortcut_from_env({SHORTCUT_FLAG_NAME: "1\n"}) is False
    assert shortcut_from_env({SHORTCUT_FLAG_NAME: ""}) is False
    # Absent → OFF.
    assert shortcut_from_env({}) is False


def test_shortcut_from_env_independent_of_workspace_flag() -> None:
    """The two flags are orthogonal — setting one does NOT activate the other.

    Per W-20 §3 the NEW flag is justified because activation is
    behaviourally orthogonal to ``DEVOLAFLOW_AGENT_WORKSPACE``.
    Pinned so a future PV that conflates the two surfaces breaks
    this test.
    """
    # Workspace ON, shortcut OFF.
    assert from_env({"DEVOLAFLOW_AGENT_WORKSPACE": "1"}) is True
    assert shortcut_from_env({"DEVOLAFLOW_AGENT_WORKSPACE": "1"}) is False

    # Shortcut ON, workspace OFF.
    assert from_env({SHORTCUT_FLAG_NAME: "1"}) is False
    assert shortcut_from_env({SHORTCUT_FLAG_NAME: "1"}) is True


# ---------------------------------------------------------------------------
# §3 — shortcut_verdict matrix.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("complexity", ["SIMPLE", "TRIVIAL"])
def test_shortcut_verdict_simple_with_flag_returns_shortcut(complexity: str) -> None:
    """SIMPLE or TRIVIAL complexity + flag ON → SHORTCUT_SIMPLE."""
    verdict = shortcut_verdict(complexity, simple_shortcut_enabled=True)  # type: ignore[arg-type]
    assert verdict == "SHORTCUT_SIMPLE"


@pytest.mark.parametrize("complexity", ["STANDARD", "COMPLEX"])
def test_shortcut_verdict_standard_or_complex_never_shortcuts(complexity: str) -> None:
    """STANDARD / COMPLEX complexity → NO_SHORTCUT even with flag ON.

    These tiers need design / decomposition / wave coordination — the
    full L0→L1→L2→L3 chain is mandatory regardless of the env flag.
    """
    verdict = shortcut_verdict(complexity, simple_shortcut_enabled=True)  # type: ignore[arg-type]
    assert verdict == "NO_SHORTCUT", (
        f"complexity={complexity} MUST never produce SHORTCUT_SIMPLE — "
        "the dispatch chain is mandatory for design / decomposition tiers"
    )


@pytest.mark.parametrize("complexity", ["TRIVIAL", "SIMPLE", "STANDARD", "COMPLEX"])
def test_shortcut_verdict_flag_off_returns_no_shortcut(complexity: str) -> None:
    """Without the env flag, EVERY complexity returns NO_SHORTCUT.

    The acceptance criterion #2 from the v9.3.0 PV-06 spec: "Without
    env flag, behaviour byte-identical to v9.2.4". This test pins
    that contract for all 4 complexity tiers.
    """
    verdict = shortcut_verdict(complexity, simple_shortcut_enabled=False)  # type: ignore[arg-type]
    assert verdict == "NO_SHORTCUT"


def test_shortcut_verdict_opt_out_wins() -> None:
    """The opt-out parameter wins regardless of env state + complexity.

    Mirrors :func:`activation_verdict`'s ``opt_out`` escape hatch —
    operator-explicit opt-out always defeats activation.
    """
    # Even with SIMPLE complexity AND flag ON, opt_out=True returns NO_SHORTCUT.
    verdict = shortcut_verdict("SIMPLE", simple_shortcut_enabled=True, opt_out=True)
    assert verdict == "NO_SHORTCUT"


def test_shortcut_verdict_rejects_invalid_complexity() -> None:
    """Bad complexity strings raise ``ValueError`` (S-5 — never silently coerce)."""
    with pytest.raises(ValueError):
        shortcut_verdict("medium", simple_shortcut_enabled=True)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        shortcut_verdict("", simple_shortcut_enabled=True)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# §4 — Integration with classify_complexity.
# ---------------------------------------------------------------------------


def test_shortcut_verdict_chains_with_classify_complexity() -> None:
    """The full happy path: classify + shortcut_verdict produces SHORTCUT_SIMPLE.

    Mirrors the dispatcher's expected call chain — first
    :func:`classify_complexity` derives the tier from task metadata,
    then :func:`shortcut_verdict` decides whether to bypass L1 + L2.
    """
    # A trivial task: 1 file, 5 LOC — TRIVIAL complexity.
    complexity = classify_complexity(files_count=1, loc_estimate=5)
    assert complexity == "TRIVIAL"

    verdict = shortcut_verdict(complexity, simple_shortcut_enabled=True)
    assert verdict == "SHORTCUT_SIMPLE"


def test_activation_verdict_three_valued_contract_unchanged() -> None:
    """The :data:`ActivationVerdict` 3-valued contract is intact.

    Per A-6.1 ("the three-valued verdict is the sole public contract")
    the PV-06 PV MUST NOT add a 4th value to ``ActivationVerdict``.
    The shortcut surface is orthogonal — verified by enumerating
    every (complexity × env × opt_out) cross-product and asserting
    the 3 strings remain the only possible outputs.
    """
    expected_values = {"MUST_OPEN_CHANGE", "SHOULD_OPEN_CHANGE", "NO_CHANGE"}
    actual_values: set[str] = set()
    for complexity in ("TRIVIAL", "SIMPLE", "STANDARD", "COMPLEX"):
        for env in (True, False):
            for opt_out in (True, False):
                verdict = activation_verdict(
                    complexity,  # type: ignore[arg-type]
                    env_agent_workspace=env,
                    opt_out=opt_out,
                )
                actual_values.add(verdict)
    assert actual_values <= expected_values, (
        f"activation_verdict produced unexpected values {actual_values - expected_values}; "
        "the 3-valued contract is broken"
    )
