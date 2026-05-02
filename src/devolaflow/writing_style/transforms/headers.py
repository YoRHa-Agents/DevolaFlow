"""T-S4 — demote orphan headers whose section is shorter than 40 words.

An "orphan header" is a ``##``-level (or deeper) header whose section
body — everything from the header line up to the next header at the
same-or-shallower depth — contains fewer than 40 prose words. The
research §3.5 finding: many DevolaFlow docs have ``header_ratio``
above 0.12 (the human-clean mean), driven by 3-line sections that
would read as bold prose paragraphs.

Demotion rule: the ``## Foo`` becomes ``**Foo**`` inline-bold on its
own line WHEN the doc isn't already bold-saturated. For docs whose
bold density already sits above the scorer's bold cap (~8 bold
markers per 1000 words), demotion falls back to plain-text
"Foo." — this stops the transform from nudging bold-heavy docs
deeper into the saturation zone.

Skip conditions:

* Top-level ``#`` (document title) — never demoted.
* ``##`` with ≥ 40 prose words in its body.
* Headers with an explicit anchor ``{#foo}`` — skipped because they
  may be linked from elsewhere.
* The section body is empty / one-liner that is itself a header at
  the same depth (a TOC-style header stack).

Region-safety: uses ``regions.apply_to_prose``; code fences and
inline code are preserved. The header regex only matches at start-
of-line and the content replacement is inside a prose region.
"""

from __future__ import annotations

import re

from ..profiles import ToneProfile

_HEADER_RE = re.compile(r"^(?P<hash>#{2,6})\s+(?P<title>.+?)(?P<anchor>\s*\{#[^}]+\})?\s*$")
_FENCE_RE = re.compile(r"^```")
_MIN_PROSE_WORDS = 40
_MIN_DEPTH_TO_DEMOTE = 3
_WORD_RE = re.compile(r"[A-Za-z\u4e00-\u9fa5][A-Za-z'\u4e00-\u9fa5-]*")
_BOLD_RE = re.compile(r"\*\*[^*\n]{1,80}\*\*")

BOLD_SATURATION_PER_1K = 8.0


def _count_prose_words(lines: list[str]) -> int:
    return sum(len(_WORD_RE.findall(line)) for line in lines)


def _doc_is_bold_saturated(text: str) -> bool:
    words = len(_WORD_RE.findall(text))
    if words < 200:
        return False
    bold_count = len(_BOLD_RE.findall(text))
    per_1k = bold_count * 1000.0 / max(200, words)
    return per_1k > BOLD_SATURATION_PER_1K


def apply(text: str, profile: ToneProfile) -> str:
    """Run the T-S4 header-demotion transform at document scope.

    Unlike the other four transforms, T-S4 operates on the whole
    document rather than per-prose-region. Region-walking caused
    short headers to be counted as orphans because protected spans
    (inline code, markdown links) break the doc into small prose
    slices that lose the context of the following body. Since
    header lines themselves are pure markdown syntax (no protected
    spans can appear inside a ``## Foo`` line), operating at doc
    scope is safe.

    Headers inside fenced code blocks are skipped via a simple
    line-level fence tracker.
    """
    del profile
    bold_saturated = _doc_is_bold_saturated(text)
    lines = text.split("\n")
    in_code_fence = False
    out_lines: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if _FENCE_RE.match(line):
            in_code_fence = not in_code_fence
            out_lines.append(line)
            i += 1
            continue
        if in_code_fence:
            out_lines.append(line)
            i += 1
            continue
        m = _HEADER_RE.match(line)
        if not m:
            out_lines.append(line)
            i += 1
            continue
        if m.group("anchor"):
            out_lines.append(line)
            i += 1
            continue
        depth = len(m.group("hash"))
        if depth < _MIN_DEPTH_TO_DEMOTE:
            out_lines.append(line)
            i += 1
            continue
        j = i + 1
        body_lines: list[str] = []
        while j < len(lines):
            if _FENCE_RE.match(lines[j]):
                body_lines.append(lines[j])
                j += 1
                while j < len(lines) and not _FENCE_RE.match(lines[j]):
                    body_lines.append(lines[j])
                    j += 1
                if j < len(lines):
                    body_lines.append(lines[j])
                    j += 1
                continue
            nxt = _HEADER_RE.match(lines[j])
            if nxt and len(nxt.group("hash")) <= depth:
                break
            body_lines.append(lines[j])
            j += 1
        word_count = _count_prose_words(body_lines)
        if 0 < word_count < _MIN_PROSE_WORDS:
            title = m.group("title").strip()
            if bold_saturated:
                out_lines.append(title)
            else:
                out_lines.append(f"**{title}**")
            i += 1
        else:
            out_lines.append(line)
            i += 1
    return "\n".join(out_lines)


__all__ = ["apply", "BOLD_SATURATION_PER_1K"]
