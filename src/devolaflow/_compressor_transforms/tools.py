"""Focused implementation slice for the legacy module."""

# ruff: noqa: F403, F405

from __future__ import annotations

from .common import *  # noqa: F403


@dataclass(frozen=True)
class ToolUseTruncation:
    """Result of a tool-output truncation pass.

    Reports how many ``tool_use`` records were preserved verbatim
    (``kept_count``) versus had their middle elided (``cleared_count``),
    plus the head/tail/placeholder/exclude policy that was applied.
    Producing layer is the L2 task agent; consumer is the L1 wave agent.
    """

    kept_count: int
    cleared_count: int
    head_chars: int
    tail_chars: int
    placeholder: str
    excluded_tool_names: tuple[str, ...]


def truncate_tool_output(
    text: str,
    *,
    head_chars: int = DEFAULT_TRUNCATION_HEAD_CHARS,
    tail_chars: int = DEFAULT_TRUNCATION_TAIL_CHARS,
    placeholder_template: str = DEFAULT_TRUNCATION_PLACEHOLDER,
) -> tuple[str, int]:
    """Truncate the middle of a single tool_use output.

    If ``len(text) <= head_chars + tail_chars`` the text is returned unchanged
    with ``removed == 0``. Otherwise the head + tail are kept verbatim and the
    elided middle is replaced by ``placeholder_template`` with ``{removed}``
    substituted for the count of dropped characters.

    Pure function; no side effects. Slicing is character-based via
    :func:`len`, which counts Unicode code points and so preserves
    surrogate-safe boundaries for typical text payloads (per ADR-002 §2.2).
    """
    if head_chars < 0 or tail_chars < 0:
        raise ValueError("head_chars and tail_chars must be non-negative")
    threshold = head_chars + tail_chars
    if len(text) <= threshold:
        return text, 0
    removed = len(text) - threshold
    placeholder = placeholder_template.format(removed=removed)
    head = text[:head_chars]
    tail = text[-tail_chars:] if tail_chars > 0 else ""
    return head + placeholder + tail, removed


def clear_old_tool_uses(
    tool_uses: list[dict],
    *,
    keep: int = DEFAULT_TRUNCATION_KEEP,
    exclude_tool_names: tuple[str, ...] = DEFAULT_TRUNCATION_EXCLUDE,
    head_chars: int = DEFAULT_TRUNCATION_HEAD_CHARS,
    tail_chars: int = DEFAULT_TRUNCATION_TAIL_CHARS,
    placeholder_template: str = DEFAULT_TRUNCATION_PLACEHOLDER,
) -> tuple[list[dict], ToolUseTruncation]:
    """Apply tool-output truncation policy across a sequence of ``tool_use``
    records (each is a dict with at least ``name`` and ``output`` keys).

    The MOST RECENT ``keep`` records are preserved verbatim. Older records
    whose ``name`` is in ``exclude_tool_names`` are also preserved verbatim
    (default: ``Read`` output, which is frequently cited verbatim in code
    reviews per ADR-002 §2.2). All other older records have their ``output``
    elided via :func:`truncate_tool_output`.

    Returns a ``(modified_list, summary)`` tuple. The list is a shallow copy
    in original order; modified records are themselves shallow copies with a
    rewritten ``output`` field, so the caller's input is not mutated.
    ``summary.kept_count`` and ``summary.cleared_count`` always sum to
    ``len(tool_uses)``. ``cleared_count`` only counts records where the
    output text was actually shortened (``removed > 0``); records whose
    output was already shorter than the threshold are counted as kept.
    """
    if keep < 0:
        raise ValueError("keep must be non-negative")
    excluded = tuple(exclude_tool_names)
    excluded_set = set(excluded)
    n = len(tool_uses)
    kept = 0
    cleared = 0
    modified: list[dict] = []
    threshold_index = max(n - keep, 0)
    for idx, record in enumerate(tool_uses):
        if idx >= threshold_index:
            modified.append(record)
            kept += 1
            continue
        name = record.get("name")
        if name in excluded_set:
            modified.append(record)
            kept += 1
            continue
        output = record.get("output", "")
        if not isinstance(output, str):
            modified.append(record)
            kept += 1
            continue
        new_output, removed = truncate_tool_output(
            output,
            head_chars=head_chars,
            tail_chars=tail_chars,
            placeholder_template=placeholder_template,
        )
        if removed == 0:
            modified.append(record)
            kept += 1
            continue
        new_record = dict(record)
        new_record["output"] = new_output
        modified.append(new_record)
        cleared += 1
    summary = ToolUseTruncation(
        kept_count=kept,
        cleared_count=cleared,
        head_chars=head_chars,
        tail_chars=tail_chars,
        placeholder=placeholder_template,
        excluded_tool_names=excluded,
    )
    return modified, summary


__all__ = [
    name
    for name in globals()
    if name not in {"__name__", "__package__", "__loader__", "__spec__", "__builtins__", "__all__"}
]
