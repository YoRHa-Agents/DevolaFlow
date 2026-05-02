"""Tone profiles for the writing-style scorer + transformer.

Three profiles per Q-C (L0-approved PV-01 decision):

* ``technical_concise`` — CHANGELOG entries, research artefacts.
  Tight register, heavy info density is fine, but we still want
  em-dashes controlled and clichés suppressed.
* ``documentation_natural`` — README, EN/ZH user guides.
  Balanced register, bullet/header caps tighter than CHANGELOG.
* ``marketing_warm`` — demo landing-page "What's New" prose,
  release announcements. Slightly warmer register; bullet/header
  caps tightest.

Each profile carries:

* weights for the 10 composite sub-scores (must sum to 1.0)
* per-feature caps that saturate the sub-score at 0 (below cap =
  no penalty; above = linear penalty up to the hit ceiling)
* ``advisory_floor`` — naturalness below this triggers a CI warning
* ``hard_floor`` — naturalness below this is a release blocker
* ``transforms_enabled`` — the five SAFE transform flags; the
  Q-D CHANGELOG policy uses this to disable T-S2/T-S3/T-S4 for
  technical_concise
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True)
class FeatureCaps:
    """Per-feature thresholds at which the AI-flavor sub-score starts
    (below cap = no penalty) and the unit scale over which it saturates
    at 1.0 (``start + scale`` saturates).
    """

    burstiness_target: float = 0.65
    burstiness_scale: float = 0.65
    ttr_target: float = 0.45
    ttr_scale: float = 0.30
    bold_per_1k_start: float = 8.0
    bold_per_1k_scale: float = 25.0
    emdash_per_1k_start: float = 5.0
    emdash_per_1k_scale: float = 25.0
    tier1_per_1k_scale: float = 5.0
    tier2_per_1k_scale: float = 15.0
    signposts_per_1k_scale: float = 10.0
    neg_parallel_per_1k_scale: float = 3.0
    bullet_ratio_start: float = 0.25
    bullet_ratio_scale: float = 0.25
    header_ratio_start: float = 0.12
    header_ratio_scale: float = 0.15


@dataclass(frozen=True)
class ToneProfile:
    name: str
    weights: Mapping[str, float]
    caps: FeatureCaps
    advisory_floor: float
    hard_floor: float
    transforms_enabled: Mapping[str, bool] = field(
        default_factory=lambda: {
            "emdash": True,
            "bullets": True,
            "signposts": True,
            "headers": True,
            "cliches": True,
        }
    )

    def enabled(self, transform_name: str) -> bool:
        return bool(self.transforms_enabled.get(transform_name, True))


_DEFAULT_WEIGHTS: dict[str, float] = {
    "burstiness": 0.10,
    "ttr": 0.05,
    "bold": 0.15,
    "emdash": 0.15,
    "tier1": 0.05,
    "tier2": 0.05,
    "signposts": 0.10,
    "neg_parallel": 0.05,
    "bullet": 0.15,
    "header": 0.15,
}


# All three profiles share the same scoring caps (the PV-01 probe's
# calibrated thresholds — 8.0 bold/1k, 0.25 bullet-ratio, etc.). Per
# Q-E, profiles differ in advisory / hard floors and in which of the
# five SAFE transforms they allow. Uniform scoring lets the benchmark
# round-trip against the PV-01 baseline exactly.

TECHNICAL_CONCISE = ToneProfile(
    name="technical_concise",
    weights=_DEFAULT_WEIGHTS,
    caps=FeatureCaps(),
    advisory_floor=65.0,
    hard_floor=45.0,
    transforms_enabled={
        "emdash": True,
        "bullets": False,
        "signposts": False,
        "headers": False,
        "cliches": True,
    },
)


DOCUMENTATION_NATURAL = ToneProfile(
    name="documentation_natural",
    weights=_DEFAULT_WEIGHTS,
    caps=FeatureCaps(),
    advisory_floor=65.0,
    hard_floor=45.0,
    transforms_enabled={
        "emdash": True,
        "bullets": True,
        "signposts": True,
        "headers": True,
        "cliches": True,
    },
)


MARKETING_WARM = ToneProfile(
    name="marketing_warm",
    weights=_DEFAULT_WEIGHTS,
    caps=FeatureCaps(),
    advisory_floor=70.0,
    hard_floor=50.0,
    transforms_enabled={
        "emdash": True,
        "bullets": True,
        "signposts": True,
        "headers": True,
        "cliches": True,
    },
)


_PROFILES: dict[str, ToneProfile] = {
    "technical_concise": TECHNICAL_CONCISE,
    "documentation_natural": DOCUMENTATION_NATURAL,
    "marketing_warm": MARKETING_WARM,
}


def load_profile(name: str) -> ToneProfile:
    """Return the named profile. Raises ``StyleError`` on unknown name."""
    from .errors import StyleError

    try:
        return _PROFILES[name]
    except KeyError as exc:
        valid = ", ".join(sorted(_PROFILES))
        raise StyleError(f"unknown tone profile {name!r} (valid: {valid})") from exc


def profile_for_path(relative_path: str) -> ToneProfile:
    """Pick a profile based on the doc's path within the repo.

    Rules (evaluated top-down, first match wins):

    * ``CHANGELOG.md`` → technical_concise
    * anything under ``.local/research/`` → technical_concise
    * anything under ``workflow-system/human/demo/`` → marketing_warm
    * anything under ``workflow-system/human/en/`` or
      ``workflow-system/human/zh/`` → documentation_natural
    * ``README.md`` → documentation_natural
    * fallback → documentation_natural
    """
    path = relative_path.replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    if path == "CHANGELOG.md":
        return TECHNICAL_CONCISE
    if path.startswith(".local/research/"):
        return TECHNICAL_CONCISE
    if path.startswith("workflow-system/human/demo/"):
        return MARKETING_WARM
    if path.startswith("workflow-system/human/en/") or path.startswith("workflow-system/human/zh/"):
        return DOCUMENTATION_NATURAL
    if path == "README.md":
        return DOCUMENTATION_NATURAL
    return DOCUMENTATION_NATURAL


__all__ = [
    "FeatureCaps",
    "ToneProfile",
    "TECHNICAL_CONCISE",
    "DOCUMENTATION_NATURAL",
    "MARKETING_WARM",
    "load_profile",
    "profile_for_path",
]
