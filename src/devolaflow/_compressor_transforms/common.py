"""Shared imports and constants for the legacy compatibility split."""

# ruff: noqa: F401, E402

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from devolaflow.compressor.patterns import (
    _DATA_CLOSE_ESCAPED,
    _DATA_ENVELOPE_FULL_RE,
    _INNER_CLOSE_TAG_RE,
    _MULTI_STEP_MIN_MATCHES,
    BYPASS_CONDITIONS,
    BYPASS_PATTERNS,
    DROP_PATTERNS,
    INJECTION_PATTERNS,
    INTENSITY_TIERS,
    PRESERVE_LIST,
    PRESERVE_PATTERNS,
)
from devolaflow.task_adaptive_selector import estimate_tokens

if TYPE_CHECKING:
    from collections.abc import Mapping

    from devolaflow.compression_pipeline import CompressionStage
    from devolaflow.llm_client import LLMClient

_stage_b_logger = logging.getLogger("devolaflow.compressor.stage_b")

DEFAULT_TRUNCATION_PLACEHOLDER: str = "[truncated {removed} chars]"

DEFAULT_TRUNCATION_HEAD_CHARS: int = 500

DEFAULT_TRUNCATION_TAIL_CHARS: int = 500

DEFAULT_TRUNCATION_KEEP: int = 3

DEFAULT_TRUNCATION_EXCLUDE: tuple[str, ...] = ("Read",)

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

_QUERY_STOPWORDS: frozenset[str] = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "been",
        "being",
        "but",
        "by",
        "can",
        "could",
        "did",
        "do",
        "does",
        "for",
        "from",
        "had",
        "has",
        "have",
        "in",
        "is",
        "may",
        "might",
        "of",
        "on",
        "or",
        "should",
        "the",
        "to",
        "was",
        "were",
        "will",
        "with",
        "would",
    }
)

_QUERY_TOKEN_SPLIT_RE: re.Pattern[str] = re.compile(r"[^a-zA-Z0-9]+")

_QUERY_OVERLAP_WEIGHT: float = 0.6

_SCHEMA_PRIORITY_WEIGHT: float = 0.4

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

_HEADING_RE: re.Pattern[str] = re.compile(r"^(#{1,3})\s+(.+?)\s*$")

ABSTRACTIVE_LOW_DENSITY_THRESHOLD: float = 0.30

ABSTRACTIVE_LOW_DENSITY_MAX_LINES: int = 2

ABSTRACTIVE_HIGH_DENSITY_MAX_LINES: int = 5

_DENSITY_TOKEN_RE: re.Pattern[str] = re.compile(r"[A-Za-z0-9_./-]{2,}")

STAGE_B_FAILURE_MODES: tuple[str, ...] = (
    "timeout",
    "network",
    "parse",
    "schema",
    "content_filter",
    "rate_limit",
    "fallback_disabled",
)

STAGE_B_ABORT_MARKER: str = "STAGE_B_ABORT"

DEFAULT_DIRECTED_COMPACT_MAX_DROP_PCT: float = 0.20

DEDUP_HASH_PREFIX_LENGTH: int = 12

DEDUP_DIGEST_MAX_CHARS: int = 320

_DEDUP_REF_RE = re.compile(r"^@round-[^\s:]+:pred-\d+$")

__all__ = [
    name
    for name in globals()
    if name not in {"__name__", "__package__", "__loader__", "__spec__", "__builtins__", "__all__"}
]
