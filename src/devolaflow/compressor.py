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
from pathlib import Path

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
    "DEFAULT_SUMMARY_MODE",
    "DEFAULT_SUMMARY_MAX_TOKENS",
    "DEFAULT_SUMMARY_TRIGGER_PCT",
    "SUMMARY_TRUNCATION_MARKER",
    "SCHEMA_HINT_PRIORITIES",
    "validate_preserve_list",
    "detect_drop_violations",
    "compress_message",
    "validate_lean_format",
    "assert_dispatch_layout",
    "compute_dispatch_lcp_pct",
    "truncate_tool_output",
    "clear_old_tool_uses",
    "summarise_predecessor",
    "extract_named_entities",
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


# ---------------------------------------------------------------------------
# v7.0.2 — Hierarchical predecessor summariser (ADR-003, ships J.3)
# ---------------------------------------------------------------------------

DEFAULT_SUMMARY_MODE: str = "extractive"
DEFAULT_SUMMARY_MAX_TOKENS: int = 500
DEFAULT_SUMMARY_TRIGGER_PCT: int = 25
SUMMARY_TRUNCATION_MARKER: str = "[TRUNCATED]"

SCHEMA_HINT_PRIORITIES: dict[str, tuple[str, ...]] = {
    "design": ("decision", "consequences", "alternatives"),
    "research": ("recommendations", "open questions", "synthesis"),
    "adr": ("decision", "consequences", "test plan"),
    "gate_report": ("verdict", "findings", "metrics"),
}

_NER_ACCEPTANCE_PATTERN: re.Pattern[str] = re.compile(
    r"^\s*[-*]\s+(?:MUST(?:\s+NOT)?|SHOULD(?:\s+NOT)?|SHALL(?:\s+NOT)?|MAY)\b.+$",
    re.MULTILINE,
)
_NER_INTERFACE_PATTERN: re.Pattern[str] = re.compile(
    r"(?:^[ \t]*(?:async\s+)?def\s+\w+\s*\([^)]*\)"
    r"|^[ \t]*class\s+\w+\b"
    r"|^[ \t]*[a-zA-Z_][\w]*\s*:\s*"
    r"(?:str|int|bool|float|list|dict|tuple|Any|None|Optional)\b)",
    re.MULTILINE,
)

_ENTITY_PATTERNS: dict[str, re.Pattern[str]] = {
    "file_paths": PRESERVE_PATTERNS["file_paths"],
    "task_ids": PRESERVE_PATTERNS["task_ids"],
    "version_strings": PRESERVE_PATTERNS["version_strings"],
    "commit_hashes": PRESERVE_PATTERNS["commit_hashes"],
    "metric_values": PRESERVE_PATTERNS["metric_values"],
    "error_messages": PRESERVE_PATTERNS["error_messages_verbatim"],
    "acceptance_criterion_bullets": _NER_ACCEPTANCE_PATTERN,
    "interface_signatures": _NER_INTERFACE_PATTERN,
}


def extract_named_entities(text: str) -> list[dict]:
    """Deterministic NER over DevolaFlow's 8 structured entity classes.

    Detects file_paths, task_ids, version_strings, commit_hashes,
    metric_values, error_messages, acceptance_criterion_bullets, and
    interface_signatures (Python ``def``/``class`` or YAML ``key: type`` hints).
    Reuses :data:`PRESERVE_PATTERNS` for the first six entity types so the
    compactor and the summariser stay in lock-step on what counts as a
    preserve-list fact (ADR-003 §2.2 step 2).

    Returns an in-document-order list of ``{type, value, source_line}`` dicts.
    Duplicate ``(type, value)`` pairs are emitted once, anchored to their
    first occurrence. ``source_line`` is 1-indexed.
    """
    if not isinstance(text, str) or not text:
        return []

    line_starts: list[int] = [0]
    for idx, ch in enumerate(text):
        if ch == "\n":
            line_starts.append(idx + 1)

    def _line_for(offset: int) -> int:
        lo, hi = 0, len(line_starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if line_starts[mid] <= offset:
                lo = mid
            else:
                hi = mid - 1
        return lo + 1

    found: list[tuple[int, dict]] = []
    seen: set[tuple[str, str]] = set()
    for entity_type, pattern in _ENTITY_PATTERNS.items():
        for match in pattern.finditer(text):
            value = match.group(0).strip()
            if not value:
                continue
            key = (entity_type, value)
            if key in seen:
                continue
            seen.add(key)
            found.append(
                (
                    match.start(),
                    {"type": entity_type, "value": value, "source_line": _line_for(match.start())},
                )
            )
    found.sort(key=lambda pair: pair[0])
    return [entry for _, entry in found]


_HEADING_RE: re.Pattern[str] = re.compile(r"^(#{1,3})\s+(.+?)\s*$")


def _parse_markdown_sections(text: str) -> list[tuple[str, str]]:
    """Split markdown into ``(heading, body)`` tuples on H1/H2/H3 boundaries.

    The body of section *N* runs until the next heading. Content before the
    first heading is emitted under the empty heading ``""``.
    """
    sections: list[tuple[str, str]] = []
    current_heading = ""
    current_body: list[str] = []
    for line in text.splitlines():
        match = _HEADING_RE.match(line)
        if match is not None:
            if current_heading or current_body:
                sections.append((current_heading, "\n".join(current_body).strip("\n")))
            current_heading = match.group(2).strip()
            current_body = []
            continue
        current_body.append(line)
    if current_heading or current_body:
        sections.append((current_heading, "\n".join(current_body).strip("\n")))
    return sections or [("", text)]


def _parse_yaml_sections(text: str) -> list[tuple[str, str]]:
    """Split YAML into ``(top_level_key, body)`` tuples."""
    try:
        import yaml as _yaml

        data = _yaml.safe_load(text)
    except Exception:
        return _parse_markdown_sections(text)
    if not isinstance(data, dict) or not data:
        return [("", text)]
    sections: list[tuple[str, str]] = []
    for key, value in data.items():
        body = _yaml.safe_dump({key: value}, sort_keys=False, default_flow_style=False).rstrip()
        sections.append((str(key), body))
    return sections


def _parse_json_sections(text: str) -> list[tuple[str, str]]:
    """Split JSON object leaves into ``(key, body)`` tuples."""
    import json as _json

    try:
        data = _json.loads(text)
    except Exception:
        return _parse_markdown_sections(text)
    if not isinstance(data, dict) or not data:
        return [("", text)]
    return [(str(key), _json.dumps(value, indent=2)) for key, value in data.items()]


def _parse_toml_sections(text: str) -> list[tuple[str, str]]:
    """Split TOML into ``(table_name, body)`` tuples; falls back to markdown."""
    try:
        import tomllib as _tomllib

        data = _tomllib.loads(text)
    except Exception:
        return _parse_markdown_sections(text)
    if not isinstance(data, dict) or not data:
        return [("", text)]
    return [(str(key), repr(value)) for key, value in data.items()]


_PARSER_BY_EXT: dict[str, callable] = {
    ".md": _parse_markdown_sections,
    ".markdown": _parse_markdown_sections,
    ".yaml": _parse_yaml_sections,
    ".yml": _parse_yaml_sections,
    ".json": _parse_json_sections,
    ".toml": _parse_toml_sections,
}


def _select_sections_by_priority(
    sections: list[tuple[str, str]],
    schema_hint: str | None,
) -> list[tuple[str, str]]:
    """Reorder ``sections`` so schema-hint matches come first; nothing dropped.

    Heading matching is case-insensitive substring against the priority list
    (per ADR-003 §3 risk row 1: accepts "Decisions" plural / "Decision"
    singular alike). Sections without a priority match keep their document
    order after the prioritised ones.
    """
    if schema_hint is None or schema_hint not in SCHEMA_HINT_PRIORITIES:
        return list(sections)
    priorities = SCHEMA_HINT_PRIORITIES[schema_hint]
    ranked: list[tuple[int, int, tuple[str, str]]] = []
    rest: list[tuple[int, tuple[str, str]]] = []
    for doc_idx, section in enumerate(sections):
        heading_lower = section[0].lower()
        rank: int | None = None
        for idx, keyword in enumerate(priorities):
            if keyword in heading_lower:
                rank = idx
                break
        if rank is not None:
            ranked.append((rank, doc_idx, section))
        else:
            rest.append((doc_idx, section))
    ranked.sort(key=lambda triple: (triple[0], triple[1]))
    rest.sort(key=lambda pair: pair[0])
    return [section for _, _, section in ranked] + [section for _, section in rest]


def _truncate_to_tokens(text: str, max_tokens: int) -> tuple[str, bool]:
    """Hard-cap ``text`` at ``max_tokens`` tokens, appending the truncation
    marker. Returns ``(maybe_truncated_text, was_bounded)``.
    """
    if max_tokens <= 0:
        return SUMMARY_TRUNCATION_MARKER, True
    current = estimate_tokens(text)
    if current <= max_tokens:
        return text, False
    marker_tokens = estimate_tokens(SUMMARY_TRUNCATION_MARKER)
    keep_tokens = max(1, max_tokens - marker_tokens)
    if not text:
        return SUMMARY_TRUNCATION_MARKER, True
    ratio = keep_tokens / max(current, 1)
    cutoff = max(1, int(len(text) * ratio))
    truncated = text[:cutoff].rstrip()
    while estimate_tokens(truncated + " " + SUMMARY_TRUNCATION_MARKER) > max_tokens and truncated:
        truncated = truncated[: max(1, len(truncated) - 16)]
    return truncated.rstrip() + " " + SUMMARY_TRUNCATION_MARKER, True


def summarise_predecessor(
    artifact_path: str,
    max_tokens: int = DEFAULT_SUMMARY_MAX_TOKENS,
    mode: str = DEFAULT_SUMMARY_MODE,
    schema_hint: str | None = None,
) -> dict:
    """Produce a bounded-token summary of a predecessor artifact.

    See ``.local/research/adr/v7-ADR-003-hierarchical-summary.md`` §2 for the
    full algorithm. The default ``extractive`` mode is deterministic and
    verbatim per CO-2: it parses the artifact by extension, runs
    :func:`extract_named_entities` on the full body, and emits a
    ``key_facts:`` YAML prefix followed by the schema-hint-prioritised
    sections, hard-capped at ``max_tokens`` tokens.

    Mode ``abstractive`` is a stub at v7.0.2 — it raises
    :class:`NotImplementedError` until the LLM call is wired in v7.0.3+
    (per ADR-003 §2.3, abstractive opts in via
    ``context_profiles.yaml#summary_mode``).

    Returns a 7-key dict:
      * ``summary_text`` — bounded markdown body (≤ ``max_tokens`` tokens).
      * ``mode`` — echoed mode string.
      * ``token_count`` — actual token count of ``summary_text``.
      * ``extracted_entities`` — verbatim entity list (see
        :func:`extract_named_entities`).
      * ``covered_sections`` — headings that contributed to ``summary_text``.
      * ``dropped_sections`` — headings skipped entirely (token budget).
      * ``was_bounded`` — ``True`` iff truncation marker was inserted.
    """
    if mode not in ("extractive", "abstractive"):
        raise ValueError(f"unknown mode {mode!r} (expected 'extractive' or 'abstractive')")
    if mode == "abstractive":
        raise NotImplementedError(
            "abstractive summarisation is not yet wired (planned for v7.0.3+); "
            "use mode='extractive' for the deterministic verbatim path"
        )
    if max_tokens <= 0:
        raise ValueError(f"max_tokens must be positive (got {max_tokens})")

    path = Path(artifact_path)
    if not path.exists():
        raise FileNotFoundError(f"artifact not found: {artifact_path}")

    text = path.read_text(encoding="utf-8")
    parser = _PARSER_BY_EXT.get(path.suffix.lower(), _parse_markdown_sections)
    sections = parser(text)
    selected = _select_sections_by_priority(sections, schema_hint)
    entities = extract_named_entities(text)

    fact_lines = ["key_facts:"]
    for entity in entities:
        first_line = entity["value"].splitlines()[0]
        fact_lines.append(f"  - {first_line}")
    facts_block = "\n".join(fact_lines)

    facts_tokens = estimate_tokens(facts_block)
    body_budget = max(0, max_tokens - facts_tokens)
    covered: list[str] = []
    dropped: list[str] = []
    body_chunks: list[str] = []
    was_bounded = False
    remaining = body_budget

    for heading, body in selected:
        chunk = f"## {heading}\n\n{body}".strip() if heading else body.strip()
        if not chunk:
            continue
        chunk_tokens = estimate_tokens(chunk)
        if chunk_tokens <= remaining:
            body_chunks.append(chunk)
            covered.append(heading)
            remaining -= chunk_tokens
            continue
        if remaining > estimate_tokens(SUMMARY_TRUNCATION_MARKER) + 5 and not was_bounded:
            truncated, _ = _truncate_to_tokens(chunk, remaining)
            body_chunks.append(truncated)
            covered.append(heading)
            was_bounded = True
            remaining = 0
        else:
            dropped.append(heading)

    summary_text = facts_block
    if body_chunks:
        summary_text = facts_block + "\n\n" + "\n\n".join(body_chunks)

    if estimate_tokens(summary_text) > max_tokens:
        summary_text, _ = _truncate_to_tokens(summary_text, max_tokens)
        was_bounded = True

    return {
        "summary_text": summary_text,
        "mode": mode,
        "token_count": estimate_tokens(summary_text),
        "extracted_entities": entities,
        "covered_sections": covered,
        "dropped_sections": dropped,
        "was_bounded": was_bounded,
    }
