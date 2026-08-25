"""Tests for the v9.0.0 PV-06 (v8.5.1) Theme T5 5-primitive default-on flip.

Pins the R5 strict opt-out contract for the 5 v8.0.0 gate primitives
that flip from opt-in (default OFF) to default-ON for STRICT/AUDIT
profiles in v8.5.1:

* :func:`devolaflow.gate.budget.is_token_budget_breaker_active` (T5 #1)
* :func:`devolaflow.gate.ladder.is_verification_ladder_active` (T5 #2)
* :func:`devolaflow.gate.ratchet.is_gate_ratchet_active` (T5 #3)
* :func:`devolaflow.gate.complexity_detector.is_complexity_detector_active` (T5 #4)
* :func:`devolaflow.ac_generator.is_ac_generator_active` (T5 #5)

For each primitive the contract is identical:

* env-flag EXACTLY ``"0"`` → force inactive regardless of profile flag
* env-flag EXACTLY ``"1"`` → force active regardless of profile flag
* env-flag unset → respect the profile flag (True for STRICT/AUDIT,
  False for STANDARD/RELAXED).

Per env-flags.md §2 R5 strict parsing — values like ``"true"``, ``"yes"``,
``"on"``, ``"01"``, ``""`` are NOT accepted as activation values.

Per W-17 (≤ +30 NEW test functions per PV) the 5 primitives' uniform
contract is exercised through 3 parametrized test functions rather than
5 × N per-primitive functions.
"""

from __future__ import annotations

import pytest

from devolaflow.ac_generator import ENV_FLAG as AC_GEN_ENV_FLAG
from devolaflow.ac_generator import is_ac_generator_active
from devolaflow.gate.budget import (
    ENV_FLAG as TOKEN_BUDGET_ENV_FLAG,
)
from devolaflow.gate.budget import (
    is_token_budget_breaker_active,
)
from devolaflow.gate.complexity_detector import (
    ENV_FLAG as COMPLEXITY_ENV_FLAG,
)
from devolaflow.gate.complexity_detector import (
    is_complexity_detector_active,
)
from devolaflow.gate.ladder import (
    VERIFICATION_LADDER_ENV_FLAG,
    is_verification_ladder_active,
)
from devolaflow.gate.profiles import AUDIT, RELAXED, STANDARD, STRICT
from devolaflow.gate.ratchet import ENV_FLAG as RATCHET_ENV_FLAG
from devolaflow.gate.ratchet import is_gate_ratchet_active

_PRIMITIVE_TABLE = [
    ("token_budget_breaker", TOKEN_BUDGET_ENV_FLAG, is_token_budget_breaker_active),
    ("verification_ladder", VERIFICATION_LADDER_ENV_FLAG, is_verification_ladder_active),
    ("gate_ratchet", RATCHET_ENV_FLAG, is_gate_ratchet_active),
    ("complexity_detector", COMPLEXITY_ENV_FLAG, is_complexity_detector_active),
    ("ac_generator", AC_GEN_ENV_FLAG, is_ac_generator_active),
]


def test_strict_audit_default_to_true_for_all_five_primitives() -> None:
    """v9.0.0 PV-06: STRICT and AUDIT profiles default the 5 flags to True."""
    for profile in (STRICT, AUDIT):
        assert profile.budget_breaker_enabled is True, (
            f"{profile.name}.budget_breaker_enabled MUST be True post-flip"
        )
        assert profile.ladder_enabled is True, (
            f"{profile.name}.ladder_enabled MUST be True post-flip"
        )
        assert profile.ratchet_enabled is True, (
            f"{profile.name}.ratchet_enabled MUST be True post-flip"
        )
        assert profile.complexity_detector_enabled is True, (
            f"{profile.name}.complexity_detector_enabled MUST be True post-flip"
        )
        assert profile.ac_generator_enabled is True, (
            f"{profile.name}.ac_generator_enabled MUST be True post-flip"
        )


def test_standard_relaxed_default_to_false_for_all_five_primitives() -> None:
    """v9.0.0 PV-06: STANDARD and RELAXED profiles preserve opt-in defaults."""
    for profile in (STANDARD, RELAXED):
        assert profile.budget_breaker_enabled is False
        assert profile.ladder_enabled is False
        assert profile.ratchet_enabled is False
        assert profile.complexity_detector_enabled is False
        assert profile.ac_generator_enabled is False


@pytest.mark.parametrize(
    ("primitive_id", "env_flag", "is_active"),
    _PRIMITIVE_TABLE,
)
def test_env_flag_zero_opts_out_on_flipped_profiles(
    primitive_id: str,
    env_flag: str,
    is_active,
) -> None:
    """R5 strict opt-out — env value EXACTLY "0" disables on STRICT and AUDIT."""
    assert is_active(STRICT, env={env_flag: "0"}) is False, (
        f"{primitive_id}: STRICT + {env_flag}=0 MUST opt out"
    )
    assert is_active(AUDIT, env={env_flag: "0"}) is False, (
        f"{primitive_id}: AUDIT + {env_flag}=0 MUST opt out"
    )


@pytest.mark.parametrize(
    ("primitive_id", "env_flag", "is_active"),
    _PRIMITIVE_TABLE,
)
def test_env_flag_one_forces_on_for_opt_in_profiles(
    primitive_id: str,
    env_flag: str,
    is_active,
) -> None:
    """R5 strict opt-IN — env value EXACTLY "1" overrides STANDARD/RELAXED defaults."""
    assert is_active(STANDARD, env={env_flag: "1"}) is True, (
        f"{primitive_id}: STANDARD + {env_flag}=1 MUST force on"
    )
    assert is_active(RELAXED, env={env_flag: "1"}) is True, (
        f"{primitive_id}: RELAXED + {env_flag}=1 MUST force on"
    )


@pytest.mark.parametrize(
    ("primitive_id", "env_flag", "is_active"),
    _PRIMITIVE_TABLE,
)
@pytest.mark.parametrize("loose_value", ["true", "TRUE", "yes", "on", "01", "1 ", " 1", ""])
def test_loose_env_values_fall_back_to_profile_flag(
    primitive_id: str,
    env_flag: str,
    is_active,
    loose_value: str,
) -> None:
    """R5 strict — loose-truthy env values fall back to the profile flag."""
    assert is_active(STRICT, env={env_flag: loose_value}) is True, (
        f"{primitive_id}: STRICT + {env_flag}={loose_value!r} MUST honour profile=True"
    )
    assert is_active(STANDARD, env={env_flag: loose_value}) is False, (
        f"{primitive_id}: STANDARD + {env_flag}={loose_value!r} MUST honour profile=False"
    )


@pytest.mark.parametrize(
    ("primitive_id", "env_flag", "is_active"),
    _PRIMITIVE_TABLE,
)
def test_env_unset_respects_profile_flag(
    primitive_id: str,
    env_flag: str,
    is_active,
) -> None:
    """env-var absent → profile flag wins for both STRICT and STANDARD."""
    assert is_active(STRICT, env={}) is True
    assert is_active(STANDARD, env={}) is False
