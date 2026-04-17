"""Runtime lean format validator and compressor for DevolaFlow.

Enforces the compression rules (preserve_list, drop_list, intensity tiers)
defined in lean-dispatch.yaml / lean-report.yaml at runtime, closing the gap
where compression previously depended on LLM compliance alone.

Based on: CO-1 (lean format), CO-2 (verbatim extraction),
          LLM Scaling Paradox (compaction > summarization).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from devolaflow.task_adaptive_selector import estimate_tokens

__all__ = [
    "PRESERVE_LIST",
    "DROP_LIST",
    "INTENSITY_TIERS",
    "PRESERVE_PATTERNS",
    "DROP_PATTERNS",
    "DEFAULT_DISPATCH_LAYOUT",
    "DispatchLayoutError",
    "ToolUseTruncation",
    "validate_preserve_list",
    "detect_drop_violations",
    "compress_message",
    "validate_lean_format",
    "assert_dispatch_layout",
    "compute_dispatch_lcp_pct",
    "truncate_tool_output",
    "clear_old_tool_uses",
]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PRESERVE_LIST = [
    "file_paths",
    "error_messages_verbatim",
    "metric_values",
    "commit_hashes",
    "acceptance_criteria",
    "task_ids",
    "artifact_references",
    "version_strings",
    "environment_identifiers",
    "dependency_versions",
    "line_numbers",
    "timing_values",
]

DROP_LIST = [
    "filler_phrases",
    "hedging_language",
    "pleasantries",
    "redundant_narration",
    "meta_commentary",
    "apologies",
    "progress_narration",
    "obvious_acknowledgments",
    "tool_call_echoing",
]

INTENSITY_TIERS: dict[str, dict[str, list[str]]] = {
    "minimal": {"active_drops": ["filler_phrases", "pleasantries", "apologies"]},
    "standard": {
        "active_drops": [
            "filler_phrases",
            "hedging_language",
            "pleasantries",
            "redundant_narration",
            "apologies",
            "progress_narration",
            "obvious_acknowledgments",
        ]
    },
    "aggressive": {"active_drops": list(DROP_LIST)},
}

# ---------------------------------------------------------------------------
# Preserve-pattern validators
# ---------------------------------------------------------------------------

PRESERVE_PATTERNS: dict[str, re.Pattern[str]] = {
    "file_paths": re.compile(r"[\w./\-]+\.\w+"),
    "error_messages_verbatim": re.compile(r"(?:Error|Exception|Traceback|FAIL)"),
    "metric_values": re.compile(r"\d+\.?\d*%?"),
    "commit_hashes": re.compile(r"\b[0-9a-f]{7,40}\b"),
    "task_ids": re.compile(r"[TSWE]\d{2,}"),
    "version_strings": re.compile(r"\d+\.\d+\.\d+"),
}

# ---------------------------------------------------------------------------
# Drop-pattern detectors
# ---------------------------------------------------------------------------

DROP_PATTERNS: dict[str, re.Pattern[str]] = {
    "filler_phrases": re.compile(
        r"\b(?:basically|essentially|actually|obviously|clearly|simply put)\b",
        re.IGNORECASE,
    ),
    "hedging_language": re.compile(
        r"\b(?:might|perhaps|possibly|it seems|I think|I believe|arguably)\b",
        re.IGNORECASE,
    ),
    "pleasantries": re.compile(
        r"\b(?:please|thank you|thanks|great question|happy to help)\b",
        re.IGNORECASE,
    ),
    "redundant_narration": re.compile(
        r"\b(?:as mentioned|as discussed|as noted|as stated|as we know)\b",
        re.IGNORECASE,
    ),
    "meta_commentary": re.compile(
        r"\b(?:let me|I will now|moving on to|in this section)\b",
        re.IGNORECASE,
    ),
    "apologies": re.compile(
        r"\b(?:sorry|apologies|I apologize|unfortunately)\b",
        re.IGNORECASE,
    ),
    "progress_narration": re.compile(
        r"\b(?:making good progress|working on|getting closer)\b",
        re.IGNORECASE,
    ),
    "obvious_acknowledgments": re.compile(
        r"\b(?:understood|got it|will do|sure thing|absolutely)\b",
        re.IGNORECASE,
    ),
    "tool_call_echoing": re.compile(
        r"\b(?:I (?:just )?(?:ran|executed|called|used) (?:the )?\w+ tool)\b",
        re.IGNORECASE,
    ),
}

# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------


def validate_preserve_list(message: str) -> dict:
    """Check which preserve_list items are present in the message.

    Returns a dict with:
      - present: list of (item_name, count) tuples
      - absent: list of item_names not found
      - integrity_score: fraction of pattern-checked items that are present
    """
    present: list[tuple[str, int]] = []
    absent: list[str] = []

    for item in PRESERVE_LIST:
        pattern = PRESERVE_PATTERNS.get(item)
        if pattern is None:
            continue
        matches = pattern.findall(message)
        if matches:
            present.append((item, len(matches)))
        else:
            absent.append(item)

    checked = len(present) + len(absent)
    integrity_score = len(present) / checked if checked > 0 else 0.0

    return {
        "present": present,
        "absent": absent,
        "integrity_score": integrity_score,
    }


def detect_drop_violations(message: str, intensity: str = "standard") -> dict:
    """Detect drop_list items that should have been removed.

    Returns a dict with:
      - violations: list of (item_name, matches) tuples
      - violation_count: total number of matches across all drop categories
      - compliance_score: 1.0 means no violations
    """
    if intensity not in INTENSITY_TIERS:
        intensity = "standard"

    active_drops = INTENSITY_TIERS[intensity]["active_drops"]
    violations: list[tuple[str, list[str]]] = []
    total = 0

    for drop_name in active_drops:
        pattern = DROP_PATTERNS.get(drop_name)
        if pattern is None:
            continue
        matches = pattern.findall(message)
        if matches:
            violations.append((drop_name, matches))
            total += len(matches)

    compliance_score = 0.0 if total > 0 else 1.0

    return {
        "violations": violations,
        "violation_count": total,
        "compliance_score": compliance_score,
    }


def compress_message(message: str, intensity: str = "standard") -> dict:
    """Apply deterministic compression to a message.

    For each active drop pattern (based on intensity tier), removes matches,
    then collapses whitespace and strips trailing spaces per line.

    Returns a dict with:
      - original_tokens: token count before compression
      - compressed_tokens: token count after compression
      - compressed_text: the compressed message
      - compression_ratio: fraction of tokens saved (0..1)
      - transformations_applied: names of drop patterns that matched
    """
    if intensity not in INTENSITY_TIERS:
        intensity = "standard"

    original_tokens = estimate_tokens(message)
    active_drops = INTENSITY_TIERS[intensity]["active_drops"]

    text = message
    transformations: list[str] = []

    for drop_name in active_drops:
        pattern = DROP_PATTERNS.get(drop_name)
        if pattern is None:
            continue
        new_text = pattern.sub("", text)
        if new_text != text:
            transformations.append(drop_name)
            text = new_text

    text = re.sub(r"[^\S\n]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = "\n".join(line.rstrip() for line in text.splitlines())
    text = text.strip()

    compressed_tokens = estimate_tokens(text)
    ratio = 1.0 - compressed_tokens / original_tokens if original_tokens > 0 else 0.0

    return {
        "original_tokens": original_tokens,
        "compressed_tokens": compressed_tokens,
        "compression_ratio": ratio,
        "compressed_text": text,
        "transformations_applied": transformations,
    }


def validate_lean_format(message: str, intensity: str = "standard") -> dict:
    """Validate that a message conforms to lean format rules.

    Combines preserve-list validation and drop-violation detection into a
    single 0-100 score.  Higher score = more lean-compliant.

    Returns a dict with:
      - valid: True when score >= 70
      - score: float 0-100
      - preserve_present: preserve items found
      - preserve_missing: preserve items expected but absent
      - drops_remaining: drop items still present
      - intensity: the tier used
      - details: list of diagnostic strings
    """
    if intensity not in INTENSITY_TIERS:
        intensity = "standard"

    preserve_result = validate_preserve_list(message)
    drop_result = detect_drop_violations(message, intensity)

    details: list[str] = []

    preserve_score = preserve_result["integrity_score"] * 100
    violation_count = drop_result["violation_count"]

    if violation_count > 0:
        penalty = min(violation_count * 10, 60)
        drop_score = max(0, 100 - penalty)
        details.append(f"{violation_count} drop violations (penalty {penalty})")
    else:
        drop_score = 100.0
        details.append("no drop violations")

    if preserve_result["present"]:
        details.append(f"preserve items found: {[p[0] for p in preserve_result['present']]}")
    if preserve_result["absent"]:
        details.append(f"preserve items missing: {preserve_result['absent']}")

    score = round((preserve_score * 0.4) + (drop_score * 0.6), 1)

    return {
        "valid": score >= 70,
        "score": score,
        "preserve_present": [p[0] for p in preserve_result["present"]],
        "preserve_missing": preserve_result["absent"],
        "drops_remaining": [v[0] for v in drop_result["violations"]],
        "intensity": intensity,
        "details": details,
    }


DEFAULT_DISPATCH_LAYOUT: list[str] = [
    "hdr",
    "task",
    "goal",
    "assumptions",
    "pred",
    "files",
    "rules",
    "shared",
    "accept",
    "reinforce",
    "verify_cfg",
    "gate",
]


class DispatchLayoutError(ValueError):
    """Raised when a dispatch payload's top-level key order violates the
    canonical layout invariant declared in lean-dispatch.yaml."""


def assert_dispatch_layout(
    payload: dict,
    layout_spec: list[str] | None = None,
) -> None:
    """Validate that ``payload``'s top-level key insertion order is a
    subsequence of the canonical layout (default ``DEFAULT_DISPATCH_LAYOUT``).

    Each spec key may be absent, but none may appear out of order. Unknown keys
    MUST appear after the last spec key (additive rule per ADR-001 §2). Raises
    :class:`DispatchLayoutError` identifying the first violating key.
    """
    if not isinstance(payload, dict):
        raise DispatchLayoutError(f"payload must be a dict, got {type(payload).__name__}")

    spec = list(layout_spec) if layout_spec is not None else list(DEFAULT_DISPATCH_LAYOUT)
    spec_index = {key: idx for idx, key in enumerate(spec)}
    last_position = -1
    seen_unknown = False

    for key in payload:
        if key not in spec_index:
            seen_unknown = True
            continue
        if seen_unknown:
            raise DispatchLayoutError(
                f"spec key {key!r} appears after non-spec key(s); new top-level "
                f"keys MUST be appended after {spec[-1]!r} (additive rule, ADR-001 §2)"
            )
        position = spec_index[key]
        if position < last_position:
            raise DispatchLayoutError(
                f"key {key!r} (canonical position {position}) appears after "
                f"{spec[last_position]!r} (canonical position {last_position}); "
                f"canonical order is {spec!r}"
            )
        last_position = position


def compute_dispatch_lcp_pct(payload_a: dict, payload_b: dict) -> float:
    """Longest common prefix of the rendered YAML for two dispatch payloads,
    as a fraction of ``payload_a``'s rendered byte length.

    Used by the H.2 stability test (ADR-001 §6). Renders both via
    ``yaml.safe_dump(..., sort_keys=False, default_flow_style=False)`` to
    preserve insertion order across implementations. Returns 0.0 if
    ``payload_a`` renders empty.
    """
    import yaml

    bytes_a = yaml.safe_dump(payload_a, sort_keys=False, default_flow_style=False).encode("utf-8")
    bytes_b = yaml.safe_dump(payload_b, sort_keys=False, default_flow_style=False).encode("utf-8")
    if not bytes_a:
        return 0.0
    common = 0
    for byte_a, byte_b in zip(bytes_a, bytes_b, strict=False):
        if byte_a != byte_b:
            break
        common += 1
    return common / len(bytes_a)


# ---------------------------------------------------------------------------
# v7.0.1 — Tool-output truncation primitive (ADR-002, ships J.2)
# ---------------------------------------------------------------------------

DEFAULT_TRUNCATION_PLACEHOLDER: str = "[truncated {removed} chars]"
DEFAULT_TRUNCATION_HEAD_CHARS: int = 500
DEFAULT_TRUNCATION_TAIL_CHARS: int = 500
DEFAULT_TRUNCATION_KEEP: int = 3
DEFAULT_TRUNCATION_EXCLUDE: tuple[str, ...] = ("Read",)


@dataclass(frozen=True)
class ToolUseTruncation:
    """Result of a tool-output truncation pass.

    Reports how many ``tool_use`` records were preserved verbatim
    (``kept_count``) versus had their middle elided (``cleared_count``),
    plus the head/tail/placeholder/exclude policy that was applied.
    Producing layer is the L3 task agent; consumer is the L2 wave agent.
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
