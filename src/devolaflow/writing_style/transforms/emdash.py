"""T-S1 — em-dash normalisation + density cap.

Three-stage transform:

1. **Typographic normalisation.** Convert ASCII ``--`` (two hyphens)
   into a single U+2014 em-dash ``—`` so the downstream density
   counter is uniform.
2. **Per-paragraph cap.** Within any paragraph containing 2 or more
   em-dashes, keep the first em-dash and downgrade subsequent
   em-dashes to commas. This alone brings most docs under the
   per-1k cap.
3. **Document-level density cap.** After step 2, if the whole-
   document em-dash density still exceeds the target
   (``TARGET_EMDASH_PER_1K``, default 12 per 1000 words — midway
   between the human-clean mean of 7.8 and the PV-01 scoring start
   of 5), walk em-dashes in reading order and demote the excess to
   commas. The first N em-dashes under the budget are kept as
   "meaningful pauses"; the rest become commas. This matches the
   2026 writehuman.ai finding that humanized text retains
   em-dashes at ~7% of the sample rate, meaningful but not
   overwhelming.

Idempotent: a second pass yields byte-identical output. Region-safe:
uses ``regions.apply_to_prose`` so em-dashes inside fenced code,
inline code, markdown link targets, and version strings are
preserved byte-for-byte.
"""

from __future__ import annotations

import re

from ..profiles import ToneProfile
from ..regions import apply_to_prose, split

_ASCII_DASHDASH_RE = re.compile(r"(?<!-)--(?!-)")
_EMDASH = "\u2014"
_PARAGRAPH_SEP_RE = re.compile(r"\n\s*\n")
_WORD_RE = re.compile(r"[A-Za-z\u4e00-\u9fa5][A-Za-z'\u4e00-\u9fa5-]*")

TARGET_EMDASH_PER_1K = 8.0


def _normalise_dashes(text: str) -> str:
    return _ASCII_DASHDASH_RE.sub(_EMDASH, text)


def _cap_emdashes_in_paragraph(paragraph: str) -> str:
    parts = paragraph.split(_EMDASH)
    if len(parts) < 3:
        return paragraph
    result = parts[0] + _EMDASH + parts[1]
    for part in parts[2:]:
        trimmed_result = result.rstrip(" ")
        trimmed_part = part.lstrip(" ")
        result = trimmed_result + ", " + trimmed_part
    return result


def _per_paragraph_cap(prose: str) -> str:
    paragraphs = _PARAGRAPH_SEP_RE.split(prose)
    separators: list[str] = [m.group(0) for m in _PARAGRAPH_SEP_RE.finditer(prose)]
    out_parts: list[str] = []
    for i, para in enumerate(paragraphs):
        out_parts.append(_cap_emdashes_in_paragraph(para))
        if i < len(separators):
            out_parts.append(separators[i])
    return "".join(out_parts)


def _count_prose_words(text: str) -> int:
    regions = split(text)
    return sum(len(_WORD_RE.findall(r.text)) for r in regions if r.kind == "prose")


def _demote_excess_emdashes(text: str, budget: int) -> str:
    """Walk ``text`` and keep at most ``budget`` em-dashes; demote
    the rest to ``, ``."""
    if budget < 0:
        budget = 0
    out: list[str] = []
    kept = 0
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == _EMDASH:
            if kept < budget:
                out.append(ch)
                kept += 1
            else:
                # Collapse surrounding spaces into a single ", "
                # so "a — b" becomes "a, b", not "a,  b".
                while out and out[-1] == " ":
                    out.pop()
                out.append(",")
                j = i + 1
                while j < len(text) and text[j] == " ":
                    j += 1
                out.append(" ")
                i = j
                continue
        else:
            out.append(ch)
        i += 1
    return "".join(out)


def apply(text: str, profile: ToneProfile) -> str:
    """Run the T-S1 em-dash transform with region safety."""
    del profile
    normalised = apply_to_prose(text, _normalise_dashes)
    per_paragraph_capped = apply_to_prose(normalised, _per_paragraph_cap)

    regions = split(per_paragraph_capped)
    total_emdashes = sum(r.text.count(_EMDASH) for r in regions if r.kind == "prose")
    total_words = _count_prose_words(per_paragraph_capped)
    if total_words < 200:
        return per_paragraph_capped
    budget = max(1, int(TARGET_EMDASH_PER_1K * total_words / 1000))
    if total_emdashes <= budget:
        return per_paragraph_capped

    out_parts: list[str] = []
    remaining_budget = budget
    for r in regions:
        if r.kind != "prose":
            out_parts.append(r.text)
            continue
        region_emdashes = r.text.count(_EMDASH)
        if remaining_budget >= region_emdashes:
            out_parts.append(r.text)
            remaining_budget -= region_emdashes
        else:
            out_parts.append(_demote_excess_emdashes(r.text, remaining_budget))
            remaining_budget = 0
    return "".join(out_parts)


__all__ = ["apply", "TARGET_EMDASH_PER_1K"]
