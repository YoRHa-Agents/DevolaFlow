"""T-S1 — em-dash normalisation + density cap.

Two-stage transform:

1. **Typographic normalisation.** Convert ASCII ``--`` (two hyphens)
   into a single U+2014 em-dash ``—`` so the downstream density
   counter is uniform. The replacement is skipped when the ``--``
   appears inside a protected region (handled by
   ``regions.apply_to_prose``).
2. **Density cap.** Within a paragraph containing 3 or more em-dashes,
   downgrade the 2nd through N-th em-dashes to commas. The 1st
   em-dash in a paragraph is preserved as a "meaningful" pause
   (matching the 2026 writehuman.ai humanized baseline of 7.1%
   em-dash density and the chezmoi/ruff/caveman human-clean mean of
   ~7.8 per 1000 words).

The transform is idempotent: a second pass over already-transformed
text is a no-op because every ``—`` count per paragraph is ≤ 1.

Region-safety: uses ``regions.apply_to_prose`` so em-dashes inside
fenced code, inline code, markdown link targets, and version strings
are preserved byte-for-byte.
"""

from __future__ import annotations

import re

from ..profiles import ToneProfile
from ..regions import apply_to_prose

_ASCII_DASHDASH_RE = re.compile(r"(?<!-)--(?!-)")
_EMDASH = "\u2014"
_PARAGRAPH_SEP_RE = re.compile(r"\n\s*\n")


def _normalise_dashes(text: str) -> str:
    return _ASCII_DASHDASH_RE.sub(_EMDASH, text)


def _cap_emdashes_in_paragraph(paragraph: str) -> str:
    parts = paragraph.split(_EMDASH)
    if len(parts) < 4:
        return paragraph
    # Keep the first em-dash intact. Replace subsequent em-dashes
    # with a comma + space. If the character before the em-dash is
    # already a space, collapse into a single ", " pattern.
    result = parts[0] + _EMDASH + parts[1]
    for part in parts[2:]:
        trimmed_result = result.rstrip(" ")
        trimmed_part = part.lstrip(" ")
        result = trimmed_result + ", " + trimmed_part
    return result


def _transform_prose(prose: str) -> str:
    normalised = _normalise_dashes(prose)
    paragraphs = _PARAGRAPH_SEP_RE.split(normalised)
    separators: list[str] = []
    for m in _PARAGRAPH_SEP_RE.finditer(normalised):
        separators.append(m.group(0))
    out_parts: list[str] = []
    for i, para in enumerate(paragraphs):
        out_parts.append(_cap_emdashes_in_paragraph(para))
        if i < len(separators):
            out_parts.append(separators[i])
    return "".join(out_parts)


def apply(text: str, profile: ToneProfile) -> str:
    """Run the T-S1 em-dash transform over prose regions."""
    del profile  # thresholds are uniform across profiles for T-S1
    return apply_to_prose(text, _transform_prose)


__all__ = ["apply"]
