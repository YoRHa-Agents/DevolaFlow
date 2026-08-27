"""Focused implementation slice for the legacy module."""

# ruff: noqa: F403, F405

from __future__ import annotations

from .common import *  # noqa: F403


def _tokenize_for_retrieval(text: str) -> frozenset[str]:
    """Lowercase + split on non-alnum + strip stopwords + drop tokens of length < 2.

    Returns a ``frozenset[str]`` of content tokens suitable for fast set
    intersection against query tokens. Empty / non-string input returns the
    empty frozenset so callers may pass through ``retrieval_query=None``
    without branching.
    """
    if not isinstance(text, str) or not text:
        return frozenset()
    tokens: list[str] = []
    for raw in _QUERY_TOKEN_SPLIT_RE.split(text.lower()):
        if len(raw) < 2:
            continue
        if raw in _QUERY_STOPWORDS:
            continue
        tokens.append(raw)
    return frozenset(tokens)


def _score_section_against_query(section_text: str, query_tokens: frozenset[str]) -> float:
    """Return jaccard-like overlap (intersection / union) of section vs query.

    Tokenises ``section_text`` via :func:`_tokenize_for_retrieval` (lowercase
    + split on non-alphanumeric + strip stopwords + drop tokens of length <2)
    and returns ``len(section ∩ query) / len(section ∪ query)``. Returns
    ``0.0`` when the union is empty (degenerate case where both sides have
    no scoring tokens after stopword strip), so the helper is safe on empty
    section text and empty query tokens.
    """
    section_tokens = _tokenize_for_retrieval(section_text)
    union = section_tokens | query_tokens
    if not union:
        return 0.0
    intersection = section_tokens & query_tokens
    return len(intersection) / len(union)


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
    directive: dict | None = None,
) -> list[tuple[str, str]]:
    """Reorder ``sections`` so schema-hint matches come first; nothing dropped.

    Heading matching is case-insensitive substring against the priority list
    (per ADR-003 §3 risk row 1: accepts "Decisions" plural / "Decision"
    singular alike). Sections without a priority match keep their document
    order after the prioritised ones.

    v8.0.0 (P-02) — when ``directive`` is provided with a non-empty
    ``focus_keywords`` list, sections whose heading or body contains any
    keyword (case-insensitive substring) are promoted to the front of the
    returned list, BEFORE the schema-hint priority pass is applied to the
    remaining sections. This is the "directed compaction" overlay layered
    on top of the existing schema-hint priority pass; with ``directive=None``
    the function is byte-identical to the v7.x behaviour (verified by
    :class:`tests.test_compressor.TestSummarisePredecessorRefactor`).
    """
    focus_partition = _partition_sections_by_directive(sections, directive)
    if focus_partition is not None:
        focused, normal = focus_partition
        return _rank_sections_by_schema_hint(focused, schema_hint) + _rank_sections_by_schema_hint(
            normal, schema_hint
        )
    return _rank_sections_by_schema_hint(sections, schema_hint)


def _normalise_focus_keywords(directive: dict | None) -> list[str]:
    """Return the lowercased non-empty string keywords from ``directive``.

    Used by both :func:`_partition_sections_by_directive` (compressor.py
    section ranker overlay) and :func:`directed_compact` (text-level
    paragraph filter) so directive parsing stays in one place. ``directive``
    may be ``None`` (returns ``[]``); ``focus_keywords`` may be missing,
    None, or a list — non-string entries are skipped without raising
    (S-5: explicit no-op return rather than silent attribute error).
    """
    if not directive:
        return []
    raw = directive.get("focus_keywords") or []
    return [str(kw).lower() for kw in raw if isinstance(kw, str) and kw]


def _partition_sections_by_directive(
    sections: list[tuple[str, str]],
    directive: dict | None,
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]] | None:
    """Split ``sections`` into ``(focused, normal)`` per ``directive.focus_keywords``.

    Returns ``None`` when ``directive`` is missing or carries no usable
    keywords; the caller MUST then fall back to the schema-hint priority
    path. A section is "focused" when at least one keyword matches its
    heading (case-insensitive substring) or its body. Document order is
    preserved within each partition.
    """
    keywords = _normalise_focus_keywords(directive)
    if not keywords:
        return None
    focused: list[tuple[str, str]] = []
    normal: list[tuple[str, str]] = []
    for section in sections:
        section_text = section[0].lower() + "\n" + section[1].lower()
        if any(kw in section_text for kw in keywords):
            focused.append(section)
        else:
            normal.append(section)
    return focused, normal


def _rank_sections_by_schema_hint(
    sections: list[tuple[str, str]],
    schema_hint: str | None,
) -> list[tuple[str, str]]:
    """Apply the v7.0.2 schema-hint priority ordering to ``sections``.

    Extracted from the legacy :func:`_select_sections_by_priority` body in
    v8.0.0 (P-02) so the directed-compaction overlay can compose by calling
    this helper twice (once on the focused partition, once on the normal
    partition). Behaviour for ``schema_hint=None`` or unknown hints is to
    return ``sections`` unchanged (legacy contract preserved).
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


def _select_sections_by_query(
    sections: list[tuple[str, str]],
    schema_hint: str | None,
    query_tokens: frozenset[str],
) -> list[tuple[str, str]]:
    """Rank ``sections`` by ``0.6 * query_overlap + 0.4 * schema_priority_norm``.

    Used by :func:`summarise_predecessor` when a non-empty
    ``retrieval_query`` is provided (P-05, v7.2.5). Each section is scored on
    two axes:

    * ``query_overlap`` — :func:`_score_section_against_query` jaccard
      overlap between the section text (heading + body) and the query token
      frozenset. In ``[0.0, 1.0]``.
    * ``schema_priority_norm`` — normalised schema-hint priority. Slot 0
      (highest priority keyword) maps to ``1.0``; the lowest slot maps to
      ``1 / N`` where ``N == len(priorities)``. Sections whose heading does
      not match any priority keyword score ``0.0``. When ``schema_hint`` is
      ``None`` or unrecognised, the schema axis collapses to ``0.0`` for
      every section so the ranking is driven purely by query overlap.

    The combined score is ``0.6 * query_overlap + 0.4 * schema_priority_norm``
    (matches the v7.3.0 patch plan §P-05). Sections are returned in
    descending order of combined score; ties resolve by document order so
    the result is deterministic across runs. Empty ``query_tokens`` falls
    back to :func:`_select_sections_by_priority` to preserve the v7.0.2
    behaviour.
    """
    if not query_tokens:
        return _select_sections_by_priority(sections, schema_hint)

    priorities = SCHEMA_HINT_PRIORITIES.get(schema_hint, ()) if schema_hint else ()
    n_pri = max(1, len(priorities))

    scored: list[tuple[float, int, tuple[str, str]]] = []
    for doc_idx, section in enumerate(sections):
        heading, body = section
        section_text = f"{heading} {body}" if heading else body
        query_overlap = _score_section_against_query(section_text, query_tokens)

        schema_priority_norm = 0.0
        if priorities:
            heading_lower = heading.lower()
            for idx, keyword in enumerate(priorities):
                if keyword in heading_lower:
                    schema_priority_norm = (n_pri - idx) / n_pri
                    break

        combined = (
            _QUERY_OVERLAP_WEIGHT * query_overlap + _SCHEMA_PRIORITY_WEIGHT * schema_priority_norm
        )
        scored.append((-combined, doc_idx, section))

    scored.sort(key=lambda triple: (triple[0], triple[1]))
    return [section for _, _, section in scored]


__all__ = [
    name
    for name in globals()
    if name not in {"__name__", "__package__", "__loader__", "__spec__", "__builtins__", "__all__"}
]
