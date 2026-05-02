"""T-S3 — strip sentence-starting signpost prefixes.

Deletes the catalog-driven prefixes (``It's worth noting that ``,
``At its core, ``, ``In conclusion, ``, etc.) when they open a
sentence. Preserves the rest of the sentence and up-cases the
following word's first letter.

Catalog source: ``data/cliche_catalog.yaml::signpost_prefixes``.
Matching is case-insensitive on the prefix; the replacement keeps
the original capitalisation of the first word that follows.

Sentence-start detection: immediately after a start-of-line (with
optional whitespace) or after ``.``/``!``/``?`` followed by
whitespace. This avoids stripping mid-sentence "in conclusion" in
cases like "the report ended in conclusion of a point" (where
"in conclusion" is not AI signposting).

Region-safety: uses ``regions.apply_to_prose``.
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
def _load_prefixes() -> tuple[str, ...]:
    if not _CATALOG_PATH.exists():
        raise StyleError(f"cliche catalog missing at {_CATALOG_PATH}")
    try:
        import yaml
    except ImportError as exc:
        raise StyleError("PyYAML required for signposts transform") from exc
    data = yaml.safe_load(_CATALOG_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise StyleError("cliche_catalog.yaml must be a mapping at the top level")
    prefixes = data.get("signpost_prefixes") or []
    if not isinstance(prefixes, list):
        raise StyleError("cliche_catalog.yaml:signpost_prefixes must be a list")
    return tuple(sorted((p.lower() for p in prefixes), key=len, reverse=True))


@lru_cache(maxsize=1)
def _compile_matcher() -> re.Pattern[str]:
    prefixes = _load_prefixes()
    if not prefixes:
        return re.compile(r"(?!x)x")
    escaped = "|".join(re.escape(p) for p in prefixes)
    return re.compile(
        r"(?P<start>(?:^|(?<=[.!?])\s+))(?P<prefix>" + escaped + r")",
        re.IGNORECASE | re.MULTILINE,
    )


def _replace_match(m: re.Match[str]) -> str:
    start = m.group("start")
    # Preserve the whitespace that preceded the prefix so paragraph
    # reflow isn't disturbed. Capitalisation of the following word is
    # handled by the post-processor below.
    return start


def _recapitalise_after_stripped_prefix(text: str, positions: list[int]) -> str:
    """Uppercase the first alphabetic char after each stripped position.

    ``positions`` is sorted list of byte offsets where a prefix was
    deleted. We walk them in reverse so earlier indices remain valid
    after slicing.
    """
    out = list(text)
    for pos in reversed(positions):
        for i in range(pos, min(pos + 4, len(out))):
            ch = out[i]
            if ch == " " or ch == "\t":
                continue
            if ch.isalpha():
                out[i] = ch.upper()
            break
    return "".join(out)


def _transform_prose(prose: str) -> str:
    pattern = _compile_matcher()
    stripped_positions: list[int] = []
    cursor = 0
    parts: list[str] = []
    for m in pattern.finditer(prose):
        parts.append(prose[cursor : m.start()])
        parts.append(m.group("start"))
        stripped_positions.append(sum(len(p) for p in parts))
        cursor = m.end()
    parts.append(prose[cursor:])
    joined = "".join(parts)
    return _recapitalise_after_stripped_prefix(joined, stripped_positions)


def apply(text: str, profile: ToneProfile) -> str:
    """Run the T-S3 signpost-strip transform over prose regions."""
    del profile
    return apply_to_prose(text, _transform_prose)


__all__ = ["apply"]
