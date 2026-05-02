"""T-S5 — delete sycophantic opener / chatbot-artefact phrases.

Catalog-driven strip of the AI-assistant openers ("Great question!",
"Certainly!", "Absolutely!", "I hope this helps", "Let me know if
you'd like", "Happy to help"). These never occur in DevolaFlow's
authored prose today, but future agents may inherit the pattern —
the transform is a guard-rail.

Per Q-D, T-S5 is enabled on every profile (CHANGELOG included).

Region-safety: uses ``regions.apply_to_prose``; sycophantic phrases
inside fenced code (e.g. a documented chatbot transcript example)
are preserved.

NOTE: module filename is ``cliches.py`` (ASCII) rather than
``clichés.py`` (non-ASCII) for cross-platform Python import safety;
the feature is still called "T-S5 clichés" per the research spec.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from ..errors import StyleError
from ..profiles import ToneProfile
from ..regions import apply_to_prose

_CATALOG_PATH = Path(__file__).parent.parent / "data" / "cliche_catalog.yaml"


@lru_cache(maxsize=1)
def _load_phrases() -> tuple[str, ...]:
    if not _CATALOG_PATH.exists():
        raise StyleError(f"cliche catalog missing at {_CATALOG_PATH}")
    try:
        import yaml
    except ImportError as exc:
        raise StyleError("PyYAML required for cliches transform") from exc
    data = yaml.safe_load(_CATALOG_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise StyleError("cliche_catalog.yaml must be a mapping at the top level")
    phrases = data.get("sycophantic_phrases") or []
    if not isinstance(phrases, list):
        raise StyleError("cliche_catalog.yaml:sycophantic_phrases must be a list")
    return tuple(sorted((p.lower() for p in phrases), key=len, reverse=True))


@lru_cache(maxsize=1)
def _compile_matcher() -> re.Pattern[str]:
    phrases = _load_phrases()
    if not phrases:
        return re.compile(r"(?!x)x")
    escaped = "|".join(re.escape(p) for p in phrases)
    return re.compile(escaped, re.IGNORECASE)


def _transform_prose(prose: str) -> str:
    pattern = _compile_matcher()
    return pattern.sub("", prose)


def apply(text: str, profile: ToneProfile) -> str:
    """Run the T-S5 cliché / sycophant-strip transform over prose regions."""
    del profile
    return apply_to_prose(text, _transform_prose)


__all__ = ["apply"]
