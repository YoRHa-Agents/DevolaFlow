"""T-S2 — collapse ≤ 2-item bullet lists into prose.

Detects consecutive lines matching ``^- `` / ``^* `` / ``^+ `` that
form a list of length ≤ 2 and fold them into the preceding paragraph
as a ``"X" (or a two-item pair "X, and Y")`` continuation. Skips
lists where any bullet exceeds 80 chars (likely a real list) or
where any bullet contains multi-line continuation.

Per the PV-01 research §3.5 finding: the aggregate bullet ratio
looks fine (0.262 vs human 0.259) but the worst docs hit 0.628
(CHANGELOG) and 0.377 (FAQ). Those worst docs include many 1-item
and 2-item lists that could read as prose.

Implementation notes:

* Only runs on prose regions (region-safe via ``apply_to_prose``).
* Leaves 3+ item lists untouched. The humanize research classifies
  those as real list structure, not AI-voice scaffolding.
* Preserves indentation; nested lists are detected by indentation
  depth and left alone.
* Idempotent: a folded list has no bullet markers, so a second pass
  is a no-op over that paragraph.

Region-safety: uses ``regions.apply_to_prose``; fenced-code ``-`` (as
YAML list syntax) is never touched because the whole code fence is
a protected region.
"""

from __future__ import annotations

import re

from ..profiles import ToneProfile
from ..regions import apply_to_prose

_BULLET_LINE_RE = re.compile(r"^(?P<indent>[ \t]*)(?P<marker>[-*+])[ \t]+(?P<rest>.*)$")
_BLOCK_SEP_RE = re.compile(r"\n\s*\n")
_MAX_BULLET_CHARS = 80


def _collapse_block(lines: list[str]) -> list[str]:
    """Try to collapse ``lines`` (a block separated by blank-lines) as a
    ≤ 2-item bullet list. Returns the possibly-collapsed line list.

    A block is collapsed only when:
    * The first non-empty non-bullet line forms an intro paragraph
      ending with ``:`` or ``.`` OR there is no intro line.
    * Exactly 1 or 2 bullet lines follow at the same indentation.
    * No nested bullet children are present.
    * Each bullet is ≤ 80 chars of content.
    """
    intro: list[str] = []
    bullets_indent: str | None = None
    bullet_items: list[str] = []
    tail: list[str] = []
    in_bullets = False
    for line in lines:
        m = _BULLET_LINE_RE.match(line)
        if m and not in_bullets:
            if bullet_items or bullets_indent is not None:
                return lines
            bullets_indent = m.group("indent")
            bullet_items.append(m.group("rest"))
            in_bullets = True
        elif m and in_bullets:
            if m.group("indent") != bullets_indent:
                return lines
            bullet_items.append(m.group("rest"))
        else:
            if in_bullets:
                tail.append(line)
            else:
                intro.append(line)

    if not bullet_items or len(bullet_items) > 2:
        return lines
    if len(bullets_indent or "") > 0:
        return lines
    for item in bullet_items:
        if len(item) > _MAX_BULLET_CHARS:
            return lines
        if not item.strip():
            return lines

    non_blank_intro = [s for s in intro if s.strip()]
    if not non_blank_intro:
        if len(bullet_items) == 1:
            return [bullet_items[0].rstrip()] + tail
        merged = f"{bullet_items[0].rstrip()}, and {bullet_items[1].rstrip()}"
        return [merged] + tail

    last_intro = non_blank_intro[-1].rstrip()
    if not last_intro.endswith((":", ".", "!", "?")):
        return lines

    intro_prefix = intro[:-1]
    intro_body = last_intro
    if len(bullet_items) == 1:
        if intro_body.endswith(":"):
            replacement = f"{intro_body[:-1]}: {bullet_items[0].rstrip()}"
        elif intro_body.endswith("."):
            replacement = f"{intro_body[:-1]} — {bullet_items[0].rstrip()}."
        else:
            replacement = f"{intro_body} {bullet_items[0].rstrip()}"
    else:
        merged = f"{bullet_items[0].rstrip()}, and {bullet_items[1].rstrip()}"
        if intro_body.endswith(":"):
            replacement = f"{intro_body[:-1]}: {merged}"
        elif intro_body.endswith("."):
            replacement = f"{intro_body[:-1]} — {merged}."
        else:
            replacement = f"{intro_body} {merged}"

    return intro_prefix + [replacement] + tail


def _transform_prose(text: str) -> str:
    parts = _BLOCK_SEP_RE.split(text)
    separators: list[str] = [m.group(0) for m in _BLOCK_SEP_RE.finditer(text)]
    out_parts: list[str] = []
    for idx, block in enumerate(parts):
        lines = block.split("\n")
        collapsed = _collapse_block(lines)
        out_parts.append("\n".join(collapsed))
        if idx < len(separators):
            out_parts.append(separators[idx])
    return "".join(out_parts)


def apply(text: str, profile: ToneProfile) -> str:
    """Run the T-S2 bullet-collapse transform over prose regions."""
    del profile
    return apply_to_prose(text, _transform_prose)


__all__ = ["apply"]
