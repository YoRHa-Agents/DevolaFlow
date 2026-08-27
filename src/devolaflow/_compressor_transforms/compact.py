"""Focused implementation slice for the legacy module."""

# ruff: noqa: F403, F405

from __future__ import annotations

from .common import *  # noqa: F403


def _split_paragraphs(text: str) -> list[str]:
    """Split ``text`` into paragraph chunks on blank-line boundaries.

    Returns the original paragraph strings WITHOUT the separating blank
    lines so the caller can reassemble via ``"\\n\\n".join(kept)``. Empty
    input returns ``[]``. Single-paragraph input returns a 1-element list.
    """
    if not text:
        return []
    # Split on one-or-more blank lines (handles \n\n, \n\n\n, etc.).
    return [chunk for chunk in re.split(r"\n\s*\n", text) if chunk.strip()]


def _classify_paragraphs_by_focus(
    paragraphs: list[str],
    focus_keywords: list[str],
) -> tuple[set[int], set[int]]:
    """Return ``(focus_indices, nonfocus_indices)`` for ``paragraphs``.

    A paragraph is considered "focus" when at least one of the lowercased
    ``focus_keywords`` appears as a case-insensitive substring of the
    paragraph body (heading lines that begin with ``#`` are also part of
    the body for this match). The two index sets partition
    ``range(len(paragraphs))`` exactly.
    """
    keywords = [kw.lower() for kw in focus_keywords if kw]
    focus_idx: set[int] = set()
    nonfocus_idx: set[int] = set()
    for idx, para in enumerate(paragraphs):
        para_lower = para.lower()
        if any(kw in para_lower for kw in keywords):
            focus_idx.add(idx)
        else:
            nonfocus_idx.add(idx)
    return focus_idx, nonfocus_idx


def _select_paragraphs_to_drop(
    paragraphs: list[str],
    nonfocus_idx: set[int],
    max_drop_chars: int,
) -> set[int]:
    """Greedy non-focus paragraph picker bounded by ``max_drop_chars``.

    Sorts non-focus paragraphs by length DESCENDING (so we drop the
    largest non-focus chunks first to maximise compaction per drop) and
    accumulates indices whose cumulative character cost stays at or below
    ``max_drop_chars``. The +2 separator cost (``\\n\\n``) is ONLY charged
    when ``idx > 0`` because the leading paragraph has no preceding
    separator. Returns the set of indices to drop (empty when budget is 0).
    """
    if max_drop_chars <= 0 or not nonfocus_idx:
        return set()
    candidates = sorted(nonfocus_idx, key=lambda i: -len(paragraphs[i]))
    dropped: set[int] = set()
    dropped_chars = 0
    for idx in candidates:
        para_chars = len(paragraphs[idx]) + (2 if idx > 0 else 0)
        if dropped_chars + para_chars > max_drop_chars:
            continue
        dropped.add(idx)
        dropped_chars += para_chars
    return dropped


def directed_compact(
    text: str,
    focus_keywords: list[str] | None,
    *,
    max_drop_pct: float = DEFAULT_DIRECTED_COMPACT_MAX_DROP_PCT,
) -> str:
    """Apply Layer-3 directed compaction to ``text``.

    Splits ``text`` into paragraphs (blank-line boundaries), classifies each
    paragraph as "focus" (matches at least one of ``focus_keywords``,
    case-insensitive substring) or "non-focus", and then greedily drops the
    largest non-focus paragraphs whose cumulative character cost stays
    within ``max_drop_pct`` of the input length. Focus paragraphs are
    NEVER dropped, guaranteeing ≥ 80 % focus retention (in fact 100 % —
    the implementation never marks focus paragraphs for removal). The
    cumulative drop is bounded by ``max_drop_pct`` of the input length so
    no more than ``max_drop_pct`` of the original text is removed.

    Pass-through cases (input returned unchanged):
      * ``text`` is empty / not a string.
      * ``focus_keywords`` is None or empty (no focus signal — the function
        cannot distinguish focus from non-focus, so refuses to drop).
      * ``max_drop_pct <= 0`` (no drop budget).

    Edge cases:
      * ``max_drop_pct >= 1.0`` → cap at 1.0 (drop budget = full text).
      * Single paragraph that matches a keyword → returned unchanged.
      * Single paragraph that does NOT match → MAY be dropped if its
        length fits the drop budget; otherwise returned unchanged.

    Document order is preserved among the kept paragraphs.

    See P-02 in ``.local/research/v8.0.0_patch_plan.md`` §3 for the full
    contract; AC #2 (≥ 80 % focus retention, ≤ ``max_drop_pct`` total drop)
    is verified by :class:`tests.test_compressor.TestDirectedCompact`.
    """
    if not isinstance(text, str) or not text:
        return text
    if not focus_keywords:
        return text
    if max_drop_pct <= 0:
        return text
    capped_drop_pct = min(max_drop_pct, 1.0)

    paragraphs = _split_paragraphs(text)
    if not paragraphs:
        return text

    total_chars = len(text)
    max_drop_chars = int(total_chars * capped_drop_pct)

    _, nonfocus_idx = _classify_paragraphs_by_focus(paragraphs, focus_keywords)
    drop_idx = _select_paragraphs_to_drop(paragraphs, nonfocus_idx, max_drop_chars)
    if not drop_idx:
        return text

    kept = [para for idx, para in enumerate(paragraphs) if idx not in drop_idx]
    return "\n\n".join(kept)


__all__ = [
    name
    for name in globals()
    if name not in {"__name__", "__package__", "__loader__", "__spec__", "__builtins__", "__all__"}
]
