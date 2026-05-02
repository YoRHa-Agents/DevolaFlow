"""Region classifier for writing-style analysis and transformation.

Splits a markdown document into a sequence of non-overlapping ``Region``
spans with a type tag. The scorer uses this to know which spans count as
prose for lexical/stylometric features; the transforms use it to know
which spans they are allowed to rewrite.

Only ``prose`` regions are writable by transforms. Everything else is
protected:

* ``fenced_code``   — ``` ... ``` blocks (any language)
* ``inline_code``   — `` `...` `` spans
* ``markdown_link`` — ``[text](url)`` and ``[text][ref]`` constructs;
  the link syntax is frozen because rewriting link text can break
  cross-references
* ``version``       — ``vX.Y.Z`` (``v10.1.0``, ``v8.0.0-rc1``, etc.)
* ``html_tag``      — ``<...>`` inline HTML (keeps anchor fragments
  intact in the demo index.html corpus)
* ``url``           — bare ``https?://...`` URLs

The split is stable and deterministic: ``split(text)`` then
``"".join(r.text for r in regions)`` round-trips the input byte-for-byte.
This round-trip property is pinned by
``tests/test_writing_style_transforms.py::test_region_split_round_trip``.

Design ref: v10.1.0 PV-01 research §4.1 preprocessing rules +
§5 transform contract ("byte-stable on a fixture with embedded code").
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

RegionType = Literal[
    "prose",
    "fenced_code",
    "inline_code",
    "markdown_link",
    "version",
    "html_tag",
    "url",
]

PROTECTED_TYPES: frozenset[str] = frozenset(
    {"fenced_code", "inline_code", "markdown_link", "version", "html_tag", "url"}
)


@dataclass(frozen=True)
class Region:
    """A single span of a classified document."""

    start: int
    end: int
    kind: RegionType
    text: str

    @property
    def writable(self) -> bool:
        return self.kind == "prose"


_FENCED_CODE_RE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
_HTML_TAG_RE = re.compile(r"<[^<>\n]{1,200}>")
_URL_RE = re.compile(r"https?://[^\s)>\]]+")
_MARKDOWN_LINK_RE = re.compile(r"\[[^\]\n]{1,200}\]\((?:[^()\n]{1,400}|\([^()\n]{0,200}\))*\)")
_MARKDOWN_REFLINK_RE = re.compile(r"\[[^\]\n]{1,200}\]\[[^\]\n]{0,200}\]")
_VERSION_RE = re.compile(r"\bv\d+\.\d+\.\d+(?:[.-][\w]+)*\b")


_PROTECTED_PATTERNS: list[tuple[RegionType, re.Pattern[str]]] = [
    ("fenced_code", _FENCED_CODE_RE),
    ("inline_code", _INLINE_CODE_RE),
    ("html_tag", _HTML_TAG_RE),
    ("url", _URL_RE),
    ("markdown_link", _MARKDOWN_LINK_RE),
    ("markdown_link", _MARKDOWN_REFLINK_RE),
    ("version", _VERSION_RE),
]


def split(text: str) -> list[Region]:
    """Decompose ``text`` into an ordered sequence of ``Region`` spans.

    The returned list tiles ``[0, len(text))`` exactly: every byte of
    the input lands in exactly one region, and concatenating
    ``r.text`` in order reproduces the input verbatim.

    Precedence when two protected patterns overlap: first match by
    start offset wins; ties broken by the order in
    ``_PROTECTED_PATTERNS`` (fenced code before inline code, etc.).
    """
    if not text:
        return []

    # Collect all protected matches, then pick a non-overlapping
    # subset using earliest-start / longest-span as the tie-breaker.
    candidates: list[tuple[int, int, RegionType]] = []
    for kind, pattern in _PROTECTED_PATTERNS:
        for m in pattern.finditer(text):
            candidates.append((m.start(), m.end(), kind))

    candidates.sort(key=lambda x: (x[0], -(x[1] - x[0])))
    chosen: list[tuple[int, int, RegionType]] = []
    cursor = 0
    for start, end, kind in candidates:
        if start < cursor:
            continue
        chosen.append((start, end, kind))
        cursor = end

    regions: list[Region] = []
    pos = 0
    for start, end, kind in chosen:
        if pos < start:
            regions.append(Region(pos, start, "prose", text[pos:start]))
        regions.append(Region(start, end, kind, text[start:end]))
        pos = end
    if pos < len(text):
        regions.append(Region(pos, len(text), "prose", text[pos:]))

    return regions


def prose_only(text: str) -> str:
    """Return the concatenation of prose regions with protected spans
    replaced by a single space.

    This is what the scorer consumes for feature extraction. Keeping a
    placeholder space preserves sentence boundaries across a stripped
    code fence (so burstiness isn't inflated by accidentally joining
    sentences through removed code).
    """
    regions = split(text)
    parts: list[str] = []
    for r in regions:
        parts.append(r.text if r.kind == "prose" else " ")
    return "".join(parts)


def apply_to_prose(text: str, transform: callable[[str], str]) -> str:
    """Apply ``transform`` to each prose region; protected spans are
    preserved byte-for-byte.

    ``transform`` is called once per prose region. It MUST be a pure
    function over its input (no side effects, deterministic output).
    The returned string is the concatenation of transformed prose
    regions interleaved with untouched protected spans, so protected
    region byte offsets are updated but the spans themselves never
    change content.
    """
    regions = split(text)
    parts: list[str] = []
    for r in regions:
        if r.kind == "prose":
            parts.append(transform(r.text))
        else:
            parts.append(r.text)
    return "".join(parts)


__all__ = ["Region", "RegionType", "PROTECTED_TYPES", "split", "prose_only", "apply_to_prose"]
