"""Runtime lean format validator and compressor for DevolaFlow.

Enforces the compression rules (preserve_list, drop_list, intensity tiers)
defined in lean-dispatch.yaml / lean-report.yaml at runtime, closing the gap
where compression previously depended on LLM compliance alone.

Based on: CO-1 (lean format), CO-2 (verbatim extraction),
          LLM Scaling Paradox (compaction > summarization).
"""

from __future__ import annotations

import re

from devolaflow.task_adaptive_selector import estimate_tokens

__all__ = [
    "PRESERVE_LIST",
    "DROP_LIST",
    "INTENSITY_TIERS",
    "PRESERVE_PATTERNS",
    "DROP_PATTERNS",
    "validate_preserve_list",
    "detect_drop_violations",
    "compress_message",
    "validate_lean_format",
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
