"""``devolaflow.writing_style`` — naturalness scoring + humanizing transforms.

Public API:

* ``score_text(text, profile)`` — composite + per-feature sub-scores
* ``score_corpus(items, profile_fn)`` — aggregate + per-doc scores
* ``load_profile(name)`` — return one of the three tone profiles
* ``apply_transforms(text, profile, *, enabled=None)`` — region-aware
  humanizer (ships in PV-03)
* ``NaturalnessScore``, ``ToneProfile``, ``StyleError``

This package is the single source of truth for writing-style
infrastructure. It MUST NOT be imported by the dispatch hot path
(``task_adaptive_selector.py``, ``compressor/``, ``lifecycle/``,
``feedback.py``, ``agent_workspace/dispatch_executor.py``). Enforced
by ``tests/test_writing_style_isolated.py``.

Design ref: v10.1.0 PV-01 research §§4-5 + gap analysis §3.1.
"""

from __future__ import annotations

from .errors import StyleError
from .profiles import (
    DOCUMENTATION_NATURAL,
    MARKETING_WARM,
    TECHNICAL_CONCISE,
    FeatureCaps,
    ToneProfile,
    load_profile,
    profile_for_path,
)
from .scorer import (
    CorpusScore,
    NaturalnessScore,
    RawFeatures,
    compute_composite,
    extract_features,
    score_corpus,
    score_text,
)

try:
    from .transforms import TransformResult, apply_transforms
except ImportError:  # pragma: no cover — transforms package ships in PV-03
    TransformResult = None  # type: ignore[assignment]
    apply_transforms = None  # type: ignore[assignment]


__all__ = [
    "StyleError",
    "FeatureCaps",
    "ToneProfile",
    "TECHNICAL_CONCISE",
    "DOCUMENTATION_NATURAL",
    "MARKETING_WARM",
    "load_profile",
    "profile_for_path",
    "RawFeatures",
    "NaturalnessScore",
    "CorpusScore",
    "extract_features",
    "compute_composite",
    "score_text",
    "score_corpus",
    "apply_transforms",
    "TransformResult",
]
