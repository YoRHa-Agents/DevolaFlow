"""T-S4 — demote orphan headers whose section is shorter than 40 words.

An "orphan header" is a ``##``-level (or deeper) header whose section
body — everything from the header line up to the next header at the
same-or-shallower depth — contains fewer than 40 prose words. The
research §3.5 finding: many DevolaFlow docs have ``header_ratio``
above 0.12 (the human-clean mean), driven by 3-line sections that
would read as bold prose paragraphs.

Demotion rule: the ``## Foo`` becomes ``**Foo**`` inline-bold on its
own line, followed by the body. This preserves the visual landmark
while dropping the section out of the TOC / anchor namespace.

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
from ..regions import apply_to_prose

_HEADER_RE = re.compile(r"^(?P<hash>#{2,6})\s+(?P<title>.+?)(?P<anchor>\s*\{#[^}]+\})?\s*$")
_MIN_PROSE_WORDS = 40
_WORD_RE = re.compile(r"[A-Za-z\u4e00-\u9fa5][A-Za-z'\u4e00-\u9fa5-]*")


def _count_prose_words(lines: list[str]) -> int:
    return sum(len(_WORD_RE.findall(line)) for line in lines)


def _transform_prose(text: str) -> str:
    lines = text.split("\n")
    out_lines: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
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
        j = i + 1
        body_lines: list[str] = []
        while j < len(lines):
            nxt = _HEADER_RE.match(lines[j])
            if nxt and len(nxt.group("hash")) <= depth:
                break
            body_lines.append(lines[j])
            j += 1
        word_count = _count_prose_words(body_lines)
        if 0 < word_count < _MIN_PROSE_WORDS:
            title = m.group("title").strip()
            out_lines.append(f"**{title}**")
            i += 1
        else:
            out_lines.append(line)
            i += 1
    return "\n".join(out_lines)


def apply(text: str, profile: ToneProfile) -> str:
    """Run the T-S4 header-demotion transform over prose regions."""
    del profile
    return apply_to_prose(text, _transform_prose)


__all__ = ["apply"]
