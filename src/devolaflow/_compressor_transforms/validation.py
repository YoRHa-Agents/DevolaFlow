"""Focused implementation slice for message validation."""

# ruff: noqa: F403, F405

from __future__ import annotations

from .common import *  # noqa: F403


def wrap_data_envelope(text: str, channel_id: str | None = None) -> str:
    """Wrap untrusted ``text`` in a ``<data channel="...">…</data>`` envelope.

    When ``channel_id`` is ``None`` the channel attribute is omitted so the
    output is ``<data>\\n{text}\\n</data>``. When provided, the attribute is
    rendered as ``channel="{channel_id}"`` (no quoting/escaping is applied to
    the channel id beyond the regex-imposed shape — callers MUST keep channel
    ids in ``[A-Za-z0-9._:-]`` form).

    Any literal ``</data>`` substring inside ``text`` is rewritten to
    ``</data\\u200B>`` (a zero-width space inside the closing tag) before the
    envelope is emitted. This prevents an envelope-escape attack where
    attacker-controlled content could close the envelope early and have the
    L2 agent treat trailing text as authoritative dispatcher instructions.
    The visible glyph stream is unchanged for human reviewers; only the
    strict regex used by :func:`unwrap_data_envelope` is denied a match on
    the injected payload.
    """
    if not isinstance(text, str):
        raise TypeError(f"text must be str, got {type(text).__name__}")
    safe = _INNER_CLOSE_TAG_RE.sub(_DATA_CLOSE_ESCAPED, text)
    if channel_id is None:
        return f"<data>\n{safe}\n</data>"
    return f'<data channel="{channel_id}">\n{safe}\n</data>'


def unwrap_data_envelope(envelope: str) -> tuple[str, str | None]:
    """Round-trip the inverse of :func:`wrap_data_envelope`.

    Returns ``(inner, channel_id)`` where ``channel_id`` is ``None`` when
    the envelope omitted the attribute. If ``envelope`` does not begin with
    ``<data`` the function returns ``(envelope, None)`` unchanged — this
    lets callers feed mixed wrapped/unwrapped strings without branching.

    Raises :class:`ValueError` if the input opens with ``<data`` but is
    missing the closing ``</data>`` tag, or otherwise fails the strict
    envelope regex (e.g., trailing content after ``</data>``). This strict
    match is intentional: a partially-malformed envelope is treated as an
    attack signal, not as recoverable data.
    """
    if not isinstance(envelope, str):
        raise TypeError(f"envelope must be str, got {type(envelope).__name__}")
    if not envelope.startswith("<data"):
        return envelope, None
    match = _DATA_ENVELOPE_FULL_RE.match(envelope)
    if match is None:
        raise ValueError(
            "malformed data envelope: input opens with '<data' but does not "
            'match the strict <data[ channel="..."]>\\n...\\n</data> shape '
            "(possible envelope-escape attack — refuse to parse)"
        )
    return match.group("inner"), match.group("channel")


def detect_data_channel_instructions(text: str) -> list[str]:
    """Return a sorted list of matched INJECTION_PATTERNS category names.

    The four categories — ``ignore_prior``, ``new_system_prompt``,
    ``output_redirect``, ``role_override`` — capture the canonical
    prompt-injection variants documented in arXiv:2604.02837v1. The
    return is sorted alphabetically so callers can compare results
    deterministically (e.g., status-report finding signatures).

    Returns an empty list when ``text`` is empty or when no pattern
    matches. The function never raises on input shape — non-string input
    is treated as "no match" rather than an error so it can be wired
    safely into the dispatcher's read-side loop.
    """
    if not isinstance(text, str) or not text:
        return []
    matched: list[str] = []
    for name, pattern in INJECTION_PATTERNS.items():
        if pattern.search(text):
            matched.append(name)
    matched.sort()
    return matched


class CompressionBypassWarning(UserWarning):
    """Raised (as a warning, not exception) when compress_message() bypasses
    compression because the input matched one or more bypass_conditions.

    Wave agents observe these via Python's warnings module OR via the
    ``bypass_warning`` field on the compress_message() return dict.
    """


def detect_bypass_conditions(
    message: str,
    conditions: list[str] | None = None,
) -> list[str]:
    """Return list of matched bypass-condition names in BYPASS_CONDITIONS order.

    ``conditions=None`` (default) checks ALL of BYPASS_CONDITIONS.
    ``conditions=[]`` (explicit empty list) returns [] without checking
    anything — backward-compat opt-out for callers that pass an empty list.
    """
    if conditions is None:
        conditions = BYPASS_CONDITIONS
    if not conditions or not message:
        return []
    matched: list[str] = []
    for name in conditions:
        pattern = BYPASS_PATTERNS.get(name)
        if pattern is None:
            continue
        if name == "multi_step_sequence_with_order_dependency":
            if len(pattern.findall(message)) >= _MULTI_STEP_MIN_MATCHES:
                matched.append(name)
        elif pattern.search(message):
            matched.append(name)
    return matched


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


def compress_message(
    message: str,
    intensity: str = "standard",
    bypass_conditions: list[str] | None = None,
) -> dict:
    """Apply deterministic compression to a message.

    For each active drop pattern (based on intensity tier), removes matches,
    then collapses whitespace and strips trailing spaces per line.

    Returns a dict with:
      - original_tokens: token count before compression
      - compressed_tokens: token count after compression
      - compressed_text: the compressed message
      - compression_ratio: fraction of tokens saved (0..1)
      - transformations_applied: names of drop patterns that matched
      - bypass_matched: list of matched bypass-condition names (empty when
        no bypass triggered); v7.2.0+
      - bypass_warning: one-line human-readable warning when bypass fired,
        otherwise None; v7.2.0+

    v7.2.0 (C-002): if any bypass_conditions match, the source is returned
    verbatim (compression_ratio == 0.0, transformations_applied == []) and
    a one-line warning is emitted via the warnings module + bypass_warning
    field. Pass ``bypass_conditions=[]`` to fully opt out (legacy behaviour).
    """
    import warnings

    if intensity not in INTENSITY_TIERS:
        intensity = "standard"

    matched_bypass = detect_bypass_conditions(message, bypass_conditions)
    if matched_bypass:
        original_tokens = estimate_tokens(message)
        warning_msg = (
            f"compression_bypass: returned source verbatim due to matched "
            f"conditions [{','.join(matched_bypass)}] under intensity={intensity!r}"
        )
        warnings.warn(warning_msg, CompressionBypassWarning, stacklevel=2)
        return {
            "original_tokens": original_tokens,
            "compressed_tokens": original_tokens,
            "compression_ratio": 0.0,
            "compressed_text": message,
            "transformations_applied": [],
            "bypass_matched": matched_bypass,
            "bypass_warning": warning_msg,
        }

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
        "bypass_matched": [],
        "bypass_warning": None,
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


__all__ = [
    name
    for name in globals()
    if name not in {"__name__", "__package__", "__loader__", "__spec__", "__builtins__", "__all__"}
]
