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
from typing import NamedTuple

from ..profiles import ToneProfile
from ..regions import apply_to_prose

_BULLET_LINE_RE = re.compile(r"^(?P<indent>[ \t]*)(?P<marker>[-*+])[ \t]+(?P<rest>.*)$")
_BLOCK_SEP_RE = re.compile(r"\n\s*\n")
_MAX_BULLET_CHARS = 80


class _BlockParts(NamedTuple):
    """Output of :func:`_classify_block_lines`.

    Carries the four logical regions of a candidate bullet block so that
    the downstream constraint checker + emit helpers can operate on
    plain attribute access instead of unpacking 4-element tuples at
    every call site.
    """

    intro: list[str]
    bullets_indent: str
    bullet_items: list[str]
    tail: list[str]


def _classify_block_lines(lines: list[str]) -> _BlockParts | None:
    """Split *lines* into intro / bullets / tail regions.

    Returns ``None`` for two structural-rejection paths so the caller
    treats the block as uncollapsible byte-identically to the pre-v12.4.0
    behaviour:

    * A subsequent bullet line whose indent differs from the established
      ``bullets_indent`` (mis-aligned or nested list — never collapse).
    * The absence of any bullet line at all (nothing to collapse).

    State-machine notes (preserved verbatim from the pre-refactor body):
    once ``in_bullets`` is set True it never resets, so the pre-refactor
    code's ``if bullet_items or bullets_indent is not None`` check inside
    the first-bullet-seen branch was provably dead code (the branch is
    only ever entered when both are still in their initial empty state)
    and is omitted here. Verified equivalent by the existing
    ``test_bullets_*`` fixture suite + the v12.4.0 PV-04 cc-pin test.
    """
    intro: list[str] = []
    bullets_indent: str = ""
    bullet_items: list[str] = []
    tail: list[str] = []
    in_bullets = False
    for line in lines:
        m = _BULLET_LINE_RE.match(line)
        if not m:
            (tail if in_bullets else intro).append(line)
            continue
        if not in_bullets:
            bullets_indent = m.group("indent")
            in_bullets = True
        elif m.group("indent") != bullets_indent:
            return None
        bullet_items.append(m.group("rest"))
    if not bullet_items:
        return None
    return _BlockParts(intro, bullets_indent, bullet_items, tail)


def _validate_bullet_constraints(parts: _BlockParts) -> bool:
    """Return True iff *parts* meets the collapse-eligibility contract.

    Mirrors the four guard clauses that the pre-refactor body inlined:

    1. ≤ 2 bullet items (3+ items are a real list per the humanize
       research §3.5 — never collapse).
    2. Top-level indent only (any indented bullet block is nested and
       gets preserved verbatim).
    3. No bullet exceeds :data:`_MAX_BULLET_CHARS` of content (long
       bullets are intentional list structure, not AI-voice scaffolding).
    4. No empty bullet (an empty bullet usually means the author was
       still editing).
    """
    if len(parts.bullet_items) > 2:
        return False
    if parts.bullets_indent:
        return False
    for item in parts.bullet_items:
        if len(item) > _MAX_BULLET_CHARS:
            return False
        if not item.strip():
            return False
    return True


def _collapse_no_intro(bullet_items: list[str], tail: list[str]) -> list[str]:
    """Emit the collapsed block when no intro paragraph precedes the bullets.

    1-item case: replace the single bullet with its prose body.
    2-item case: merge as ``"X, and Y"`` continuation (no leading paragraph).
    """
    if len(bullet_items) == 1:
        return [bullet_items[0].rstrip()] + tail
    merged = f"{bullet_items[0].rstrip()}, and {bullet_items[1].rstrip()}"
    return [merged] + tail


def _collapse_with_intro(
    intro: list[str],
    last_intro: str,
    bullet_items: list[str],
    tail: list[str],
) -> list[str]:
    """Emit the collapsed block when an intro paragraph precedes the bullets.

    Pre-condition: ``last_intro`` ends with ``:`` / ``.`` / ``!`` / ``?``.
    The intro-eligibility check stays in the orchestrator so this helper
    focuses on selecting the emit shape:

    * ``:`` suffix → colon-prefix continuation (``intro: continuation``).
    * ``.`` suffix → em-dash continuation (``intro — continuation.``).
    * ``!`` or ``?`` suffix → space-joined continuation (preserves the
      original sentence-final punctuation in *last_intro* untouched).
    """
    intro_prefix = intro[:-1]
    if len(bullet_items) == 1:
        continuation = bullet_items[0].rstrip()
    else:
        continuation = f"{bullet_items[0].rstrip()}, and {bullet_items[1].rstrip()}"
    if last_intro.endswith(":"):
        replacement = f"{last_intro[:-1]}: {continuation}"
    elif last_intro.endswith("."):
        replacement = f"{last_intro[:-1]} — {continuation}."
    else:
        replacement = f"{last_intro} {continuation}"
    return intro_prefix + [replacement] + tail


def _collapse_block(lines: list[str]) -> list[str]:
    """Try to collapse ``lines`` (a block separated by blank-lines) as a
    ≤ 2-item bullet list. Returns the possibly-collapsed line list.

    A block is collapsed only when:
    * The first non-empty non-bullet line forms an intro paragraph
      ending with ``:`` or ``.`` OR there is no intro line.
    * Exactly 1 or 2 bullet lines follow at the same indentation.
    * No nested bullet children are present.
    * Each bullet is ≤ 80 chars of content.

    v12.4.0 PV-04 decomposition (per
    ``.local/research/v12.4.0_gap_analysis.md`` §2 D-3): the original
    cc=25 body split into four helpers
    (:func:`_classify_block_lines`, :func:`_validate_bullet_constraints`,
    :func:`_collapse_no_intro`, :func:`_collapse_with_intro`). Public
    behaviour byte-identical to v12.3.0 — verified by the existing
    ``test_bullets_*`` fixture suite + the cc-pin test in
    ``tests/test_v12_4_0_complexity_targets.py``.
    """
    parts = _classify_block_lines(lines)
    if parts is None:
        return lines
    if not _validate_bullet_constraints(parts):
        return lines
    non_blank_intro = [s for s in parts.intro if s.strip()]
    if not non_blank_intro:
        return _collapse_no_intro(parts.bullet_items, parts.tail)
    last_intro = non_blank_intro[-1].rstrip()
    if not last_intro.endswith((":", ".", "!", "?")):
        return lines
    return _collapse_with_intro(parts.intro, last_intro, parts.bullet_items, parts.tail)


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
