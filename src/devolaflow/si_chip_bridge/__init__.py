"""Si-Chip bridge — typed Python wrappers around Si-Chip CLI scripts.

Public API for the v9.5.0 PV-04 lifecycle hook + PV-05 self-application
dogfood pass. Wraps the Si-Chip v0.4.0 script trio
(``profile_static.py``, ``count_tokens.py``, ``aggregate_eval.py``)
into typed Python so DevolaFlow's lifecycle layer can invoke them
without embedding subprocess/YAML logic inline.

Quick start::

    from devolaflow.si_chip_bridge import (
        find_si_chip_install,
        profile,
        evaluate,
        aggregate_delta,
        apply_or_defer,
        run_dogfood_cycle,
        SiChipUnavailable,
    )

    install = find_si_chip_install()
    if install is None:
        raise SiChipUnavailable("install Si-Chip first")

    result = run_dogfood_cycle(
        ability_name="devola-flow",
        skill_md=Path("workflow-system/agent/SKILL.md"),
    )
    if result.verdict == ApplyVerdict.APPLY:
        ... # land the proposed changes
    else:
        ... # write a deferred-changes feedback doc

Source: v9.5.0 PV-02 — closes D-S-2 from
`.local/research/v9.5.0_gap_analysis.md` §3.1.
External tool reference: https://github.com/YoRHa-Agents/Si-Chip
"""

from __future__ import annotations

from devolaflow.si_chip_bridge.install_resolver import (
    ENV_FALLBACK,
    ENV_HOME,
    SKILL_MD_NAME,
    SiChipInstall,
    find_si_chip_install,
)
from devolaflow.si_chip_bridge.models import (
    ApplyVerdict,
    BasicAbilityProfile,
    IterationDeltaReport,
    MetricsReport,
    SiChipResult,
)
from devolaflow.si_chip_bridge.runner import (
    APPLY_DEFER_EPSILON,
    COUNT_TOKENS_SCRIPT,
    DEFAULT_THRESHOLD,
    DEFAULT_TIMEOUT_SECONDS,
    EVALUATE_SCRIPT,
    PROFILE_SCRIPT,
    SiChipError,
    SiChipUnavailable,
    aggregate_delta,
    apply_or_defer,
    count_tokens,
    evaluate,
    profile,
    run_dogfood_cycle,
)

__all__ = [
    "APPLY_DEFER_EPSILON",
    "COUNT_TOKENS_SCRIPT",
    "DEFAULT_THRESHOLD",
    "DEFAULT_TIMEOUT_SECONDS",
    "ENV_FALLBACK",
    "ENV_HOME",
    "EVALUATE_SCRIPT",
    "PROFILE_SCRIPT",
    "SKILL_MD_NAME",
    "ApplyVerdict",
    "BasicAbilityProfile",
    "IterationDeltaReport",
    "MetricsReport",
    "SiChipError",
    "SiChipInstall",
    "SiChipResult",
    "SiChipUnavailable",
    "aggregate_delta",
    "apply_or_defer",
    "count_tokens",
    "evaluate",
    "find_si_chip_install",
    "profile",
    "run_dogfood_cycle",
]
