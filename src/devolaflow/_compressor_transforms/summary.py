"""Focused implementation slice for the legacy module."""

# ruff: noqa: F403, F405

from __future__ import annotations

from .common import *  # noqa: F403


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


def _validate_summary_args(mode: str, max_tokens: int) -> None:
    """Validate ``mode`` and ``max_tokens`` for :func:`summarise_predecessor`.

    Extracted from the legacy ``summarise_predecessor`` body in v8.0.0
    (P-02) to bring the parent function's cyclomatic complexity from 16
    down to ≤10 after a historical complexity finding. Raises
    :class:`ValueError` for unknown modes or non-positive ``max_tokens``.

    v8.0.0 (P-12) — ``abstractive`` mode is now implemented via the
    Stage A heuristic path (``_assemble_abstractive_summary``); the
    earlier :class:`NotImplementedError` raise was removed. Stage B
    (LLM-assisted) remains out of scope for v8.0.0; the design lives
    in ``.local/research/v8.0.0_p12_abstractive_stage_b_design.md`` and
    is targeted for v8.2.0 PV-01.
    """
    if mode not in ("extractive", "abstractive"):
        raise ValueError(f"unknown mode {mode!r} (expected 'extractive' or 'abstractive')")
    if max_tokens <= 0:
        raise ValueError(f"max_tokens must be positive (got {max_tokens})")


def _select_sections_for_summary(
    sections: list[tuple[str, str]],
    schema_hint: str | None,
    retrieval_query: str | None,
    directive: dict | None,
) -> list[tuple[str, str]]:
    """Pick the section ranker (query > priority+directive) for a summary.

    Extracted from the legacy ``summarise_predecessor`` body in v8.0.0
    (P-02). When ``retrieval_query`` produces a non-empty token frozenset
    after stopword strip, sections are ranked via
    :func:`_select_sections_by_query` (P-05, v7.2.5 retrieval-prioritised
    mode). Otherwise sections fall back to :func:`_select_sections_by_priority`
    with the optional v8.0.0 ``directive`` overlay. Empty ``retrieval_query``
    AND ``directive=None`` preserves byte-stable v7.0.2 behaviour.
    """
    query_tokens = _tokenize_for_retrieval(retrieval_query or "")
    if query_tokens:
        return _select_sections_by_query(sections, schema_hint, query_tokens)
    return _select_sections_by_priority(sections, schema_hint, directive)


def _assemble_summary_body(
    selected: list[tuple[str, str]],
    facts_block: str,
    max_tokens: int,
) -> tuple[str, list[str], list[str], bool]:
    """Greedy section packer: fits sections into the remaining token budget.

    Returns ``(summary_text, covered_headings, dropped_headings, was_bounded)``.
    ``summary_text`` is ``facts_block`` followed by a blank line and the
    packed sections (joined with double newlines). Sections that exceed the
    remaining budget are dropped entirely; if the FIRST exceeding section
    could be partially included (remaining budget > marker tokens + 5) it
    is truncated via :func:`_truncate_to_tokens` and ``was_bounded`` is set.

    Extracted from the legacy ``summarise_predecessor`` body in v8.0.0
    (P-02) to drive the parent function's cc 16 → ≤10. The greedy/first-
    truncation policy and the marker-tokens + 5 inclusion threshold are
    preserved verbatim from v7.0.2.
    """
    facts_tokens = estimate_tokens(facts_block)
    body_budget = max(0, max_tokens - facts_tokens)
    marker_tokens = estimate_tokens(SUMMARY_TRUNCATION_MARKER)
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
        if remaining > marker_tokens + 5 and not was_bounded:
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
    return summary_text, covered, dropped, was_bounded


def _compute_information_density(text: str) -> float:
    """Return an information-density score in ``[0.0, 1.0]`` for ``text``.

    Stage A heuristic (P-12, v8.0.0). The score blends two signals so
    repetitive whitespace / filler text scores low and entity-rich code
    or specification text scores high:

    * **Unique-token ratio** (``α = 0.6``): ``len(unique_tokens) /
      len(tokens)`` over the regex ``[A-Za-z0-9_./-]{2,}`` (tokens of
      length ≥ 2; underscores, dots, slashes, hyphens kept so that
      ``src/auth.py`` and ``foo_bar`` stay intact). Repeated tokens
      collapse the ratio toward 0; all-distinct tokens push it to 1.
    * **Entity-density signal** (``β = 0.4``): a normalised
      ``min(1.0, entity_count / max(1, total_tokens / 20))`` so that a
      section with at least one structured entity per ~20 tokens hits
      the ceiling. Entities are pulled via :func:`extract_named_entities`
      and count file paths, task IDs, version strings, commit hashes,
      metric values, error messages, acceptance bullets, and interface
      signatures (the same 8 classes used by the extractive path).

    Edge cases (return ``0.0``):

    * ``text`` is None, not a str, empty, or whitespace-only.
    * ``text`` produces zero scoring tokens after the regex pass.

    The score is bounded by construction: each component is in
    ``[0.0, 1.0]`` and ``α + β = 1.0`` so the weighted sum stays in
    ``[0.0, 1.0]``. Determinism: pure function of ``text`` — no I/O,
    no time-dependence, no randomness; bytewise identical across
    Python runs (CO-2 verbatim safety).
    """
    if not isinstance(text, str) or not text or not text.strip():
        return 0.0

    tokens = _DENSITY_TOKEN_RE.findall(text)
    total = len(tokens)
    if total == 0:
        return 0.0

    unique_ratio = len(set(t.lower() for t in tokens)) / total

    entities = extract_named_entities(text)
    entity_density = min(1.0, len(entities) / max(1.0, total / 20.0))

    score = 0.6 * unique_ratio + 0.4 * entity_density
    if score < 0.0:
        return 0.0
    if score > 1.0:
        return 1.0
    return score


def _summarise_low_density_section(heading: str, body: str) -> str:
    """Compress a low-density section to ``≤2`` lines (Stage A heuristic).

    Used by :func:`_assemble_abstractive_summary` when
    :func:`_compute_information_density` reports ``< 0.30``. The output
    is at most :data:`ABSTRACTIVE_LOW_DENSITY_MAX_LINES` newline-joined
    lines (``2`` by default). Strategy:

    * Line 1 — the section heading (prefixed ``## ``) when present;
      otherwise the first non-blank body line trimmed to ~120 chars.
    * Line 2 — the first non-blank, non-heading body line trimmed to
      ~120 chars (key-phrase extraction by truncation, not by NLP).

    Empty body → returns the heading line alone (still ≤2 lines).
    Empty heading AND empty body → returns the empty string ``""`` so
    the orchestrator (:func:`_assemble_abstractive_summary`) skips it
    via its ``if not chunk: continue`` guard. This is what triggers
    the extractive fallback for fully-empty artifacts (P-12 AC: empty
    body → mode falls back to extractive).
    """
    body_lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
    head = f"## {heading}".strip() if heading else ""
    if not head and not body_lines:
        return ""
    if not body_lines:
        return head
    first = body_lines[0]
    if len(first) > 120:
        first = first[:117].rstrip() + "..."
    if not head:
        return first
    return f"{head}\n{first}"


def _summarise_high_density_section(
    heading: str,
    body: str,
    section_entities: list[dict],
) -> str:
    """Preserve a high-density section in ``≤5`` lines while keeping entities.

    Used by :func:`_assemble_abstractive_summary` when
    :func:`_compute_information_density` reports ``≥ 0.30``. The output
    is at most :data:`ABSTRACTIVE_HIGH_DENSITY_MAX_LINES` newline-joined
    lines (``5`` by default). Strategy:

    * Line 1 — ``## <heading>`` when present.
    * Lines 2..N — the first ``N-1`` non-blank body lines verbatim
      (CO-2 verbatim — no paraphrasing).
    * If the verbatim slice would drop any entity ``value`` reported by
      :func:`extract_named_entities` for THIS section, an additional
      ``entities: [<comma-joined values>]`` line is appended (still
      bounded by the 5-line cap so we may drop the LAST verbatim line
      to make room — entity preservation always wins over verbatim
      tail per AC #4 of P-12).

    The 5-line cap is a soft upper bound: empty body → returns just the
    heading (1 line); a 1-line body → returns 2 lines.
    """
    body_lines = [ln for ln in body.splitlines() if ln.strip()]
    head = f"## {heading}".strip() if heading else ""

    out: list[str] = []
    if head:
        out.append(head)
    remaining_slots = ABSTRACTIVE_HIGH_DENSITY_MAX_LINES - len(out)
    out.extend(body_lines[:remaining_slots])

    entity_values = [e.get("value", "") for e in section_entities if e.get("value")]
    if entity_values:
        joined_out = "\n".join(out)
        missing = [v for v in entity_values if v not in joined_out]
        if missing:
            entity_line = "entities: [" + ", ".join(missing) + "]"
            if len(out) >= ABSTRACTIVE_HIGH_DENSITY_MAX_LINES:
                out[-1] = entity_line
            else:
                out.append(entity_line)

    if not out:
        return ""
    return "\n".join(out)


def _assemble_abstractive_summary(
    sections: list[tuple[str, str]],
    full_text: str,
    max_tokens: int,
) -> tuple[str, list[str], list[str], bool]:
    """Stage A orchestrator: density-routed section summariser.

    Returns ``(summary_text, covered_headings, dropped_headings,
    was_bounded)`` matching :func:`_assemble_summary_body`'s contract so
    :func:`summarise_predecessor` can swap implementations cleanly.

    Algorithm (per P-12 §3 patch plan):

    1. Pre-extract all named entities from ``full_text`` once so each
       section can look up its own entities in O(1) by source line.
    2. For each section, compute :func:`_compute_information_density`
       on the body text.
    3. Low-density (``< 0.30``) → :func:`_summarise_low_density_section`
       (≤2 lines).
    4. High-density (``≥ 0.30``) → :func:`_summarise_high_density_section`
       (≤5 lines, entities preserved).
    5. Greedy-pack into ``max_tokens``; sections whose chunk wouldn't
       fit go to ``dropped_headings`` (matches extractive semantics).
    6. ``was_bounded=True`` iff the final output had to be hard-truncated
       to honour ``max_tokens`` OR a section was elided due to budget.

    Determinism: this orchestrator is a pure function of its inputs;
    no I/O, no clock, no randomness — safe to call from CO-2 verbatim
    callers.
    """
    all_entities = extract_named_entities(full_text)

    line_to_section: dict[int, int] = {}
    cursor = 1
    for sec_idx, (heading, body) in enumerate(sections):
        if heading:
            cursor += 1
        body_line_count = body.count("\n") + 1 if body else 0
        for offset in range(body_line_count):
            line_to_section[cursor + offset] = sec_idx
        cursor += body_line_count + 1

    covered: list[str] = []
    dropped: list[str] = []
    chunks: list[str] = []
    remaining = max_tokens
    marker_tokens = estimate_tokens(SUMMARY_TRUNCATION_MARKER)
    was_bounded = False

    for sec_idx, (heading, body) in enumerate(sections):
        density = _compute_information_density(body)
        section_entities = [
            e for e in all_entities if line_to_section.get(e.get("source_line", -1)) == sec_idx
        ]
        if density < ABSTRACTIVE_LOW_DENSITY_THRESHOLD:
            chunk = _summarise_low_density_section(heading, body)
        else:
            chunk = _summarise_high_density_section(heading, body, section_entities)
        if not chunk:
            continue
        chunk_tokens = estimate_tokens(chunk)
        if chunk_tokens <= remaining:
            chunks.append(chunk)
            covered.append(heading)
            remaining -= chunk_tokens
            continue
        if remaining > marker_tokens + 5 and not was_bounded:
            truncated, _ = _truncate_to_tokens(chunk, remaining)
            chunks.append(truncated)
            covered.append(heading)
            was_bounded = True
            remaining = 0
        else:
            dropped.append(heading)
            was_bounded = True

    summary_text = "\n\n".join(chunks)
    if estimate_tokens(summary_text) > max_tokens:
        summary_text, _ = _truncate_to_tokens(summary_text, max_tokens)
        was_bounded = True

    return summary_text, covered, dropped, was_bounded


def _build_stage_b_prompt(
    *,
    artifact_path: str,
    full_text: str,
    stage_a_summary: str,
    entities: list[dict],
    max_tokens: int,
) -> str:
    """Render the Stage B prompt per design doc §3 template.

    The prompt includes the verbatim entities block (so the LLM has an
    authoritative list of values it MUST keep), the Stage A snapshot
    (used as a hint, not ground truth), and the full artifact body. The
    prompt always ends with a 4-clause OUTPUT REQUIREMENTS block whose
    last clause names the ``STAGE_B_ABORT:`` sentinel for graceful
    refusal — the caller handles the abort case as ``fallback_disabled``.
    """
    entity_lines = []
    seen_values: set[str] = set()
    for entry in entities:
        value = entry.get("value", "") if isinstance(entry, dict) else ""
        if not value or value in seen_values:
            continue
        seen_values.add(value)
        first_line = value.splitlines()[0] if value else ""
        entity_lines.append(f"  - {first_line}")
    entities_block = "\n".join(entity_lines) if entity_lines else "  (no entities extracted)"
    return (
        "SYSTEM:\n"
        "You are a CO-2 verbatim summariser. Your job is to compress the "
        f"predecessor artifact below into <= {max_tokens} tokens while preserving\n"
        "EVERY entity from the verbatim list. Do NOT paraphrase entity values.\n"
        "Do NOT introduce facts not present in the artifact. Output a single\n"
        "markdown block with the same heading hierarchy as the input.\n"
        "\n"
        "VERBATIM ENTITIES (MUST appear character-for-character in your output):\n"
        f"{entities_block}\n"
        "\n"
        "USER:\n"
        f"Artifact: {artifact_path}\n"
        "Mode: stage_b_abstractive\n"
        "Stage A snapshot (use as a HINT, not as ground truth):\n"
        f"{stage_a_summary}\n"
        "\n"
        "Full artifact body:\n"
        f"{full_text}\n"
        "\n"
        "OUTPUT REQUIREMENTS:\n"
        f"1. Single markdown block, <= {max_tokens} tokens.\n"
        "2. Every entity from VERBATIM ENTITIES MUST appear unchanged.\n"
        "3. Preserve heading hierarchy (do not flatten H2->H1).\n"
        "4. If you cannot meet (1) AND (2), respond with the literal string\n"
        f'   "{STAGE_B_ABORT_MARKER}: <reason>" and nothing else. The caller will fall\n'
        "   back to Stage A.\n"
    )


def _log_stage_b_fallback(mode: str, *, reason: str) -> None:
    """Emit a single S-5 structured WARNING for a Stage B fallback.

    Validates ``mode`` against :data:`STAGE_B_FAILURE_MODES` to prevent
    silent typos that would defeat the SI-4 harness attribution chain.
    Raises ValueError on unknown mode (S-5: explicit failure rather than
    silent log of garbage).
    """
    if mode not in STAGE_B_FAILURE_MODES:
        valid = sorted(STAGE_B_FAILURE_MODES)
        raise ValueError(f"unknown Stage B failure mode {mode!r}; expected one of {valid}")
    _stage_b_logger.warning("stage_b.fallback mode=%s reason=%s", mode, reason)


def _stage_b_check_response_error(response_error: str | None) -> str | None:
    """Map an :class:`LLMResponse.error` value to a Stage B failure mode.

    Returns the canonical Stage B failure mode name when the response
    carries an error the caller should treat as a fallback signal,
    otherwise ``None`` (success path). Unknown / unexpected error
    strings collapse to ``"network"`` rather than silently passing
    through (S-5 conservative default).
    """
    if response_error is None:
        return None
    if response_error in STAGE_B_FAILURE_MODES:
        return response_error
    return "network"


def _stage_b_validate_entities(text: str, entities: list[dict]) -> list[str]:
    """Return the list of entity values dropped from ``text`` (CO-2 verbatim check).

    Iterates :func:`extract_named_entities`-shaped dicts and returns the
    subset whose ``value`` is NOT a substring of ``text``. Used by the
    Stage B caller to detect F4 entity_drop fallbacks. Empty entities
    list returns ``[]`` (no constraint to violate).
    """
    if not entities:
        return []
    missing: list[str] = []
    for entry in entities:
        value = entry.get("value", "") if isinstance(entry, dict) else ""
        if not value:
            continue
        if value not in text:
            missing.append(value)
    return missing


def _invoke_stage_b_llm(
    *,
    artifact_path: str,
    full_text: str,
    stage_a_summary: str,
    entities: list[dict],
    max_tokens: int,
    client: LLMClient | None,
) -> dict | None:
    """Attempt Stage B LLM refinement; return refined summary OR None on any failure.

    Wraps :meth:`devolaflow.llm_client.LLMClient.complete` with the seven
    failure-mode dispatch chain documented in :data:`STAGE_B_FAILURE_MODES`.
    On any failure, the caller MUST treat the ``None`` return as the
    signal to fall back to ``stage_a_summary`` (the Stage A heuristic
    output is ALWAYS the fallback baseline per design doc §7).

    Failure-mode dispatch order (matches design doc §4 detection sequence):

      1. ``parse``             — caller passed non-string artifact data
      2. (``LLMResponse.error`` carries one of FAILURE_MODES → mapped
         to that mode and logged)
      3. ``parse``             — empty body
      4. ``fallback_disabled`` — body starts with ``STAGE_B_ABORT:``
      5. ``schema``            — body exceeded ``max_tokens`` AND
         post-truncation entity check fails
      6. ``schema``            — body dropped any verbatim entity
      7. (success — return refined summary)

    The function NEVER raises on LLM-side failures: every fallback is
    routed through :func:`_log_stage_b_fallback` which validates the
    mode and emits the canonical S-5 log line. Raises only on caller
    misuse (TypeError on ``entities`` shape — defensive, not silenced).
    """
    if client is None:
        from devolaflow.llm_client import LLMClient as _LLMClient

        client = _LLMClient(provider="mock")
    prompt = _build_stage_b_prompt(
        artifact_path=artifact_path,
        full_text=full_text,
        stage_a_summary=stage_a_summary,
        entities=entities,
        max_tokens=max_tokens,
    )
    try:
        response = client.complete(prompt)
    except Exception as exc:  # noqa: BLE001 - S-5: never propagate raw exceptions
        _log_stage_b_fallback("network", reason=f"client raised {type(exc).__name__}: {exc}")
        return None
    error_mode = _stage_b_check_response_error(response.error)
    if error_mode is not None:
        _log_stage_b_fallback(
            error_mode,
            reason=(
                f"llm_client returned error={response.error} latency_ms={response.latency_ms:.1f}"
            ),
        )
        return None
    text = response.text or ""
    if not text.strip():
        _log_stage_b_fallback("parse", reason="empty LLM response body")
        return None
    if text.lstrip().startswith(STAGE_B_ABORT_MARKER):
        first_line = text.lstrip().splitlines()[0]
        _log_stage_b_fallback("fallback_disabled", reason=first_line)
        return None
    actual_tokens = estimate_tokens(text)
    was_bounded = False
    if actual_tokens > max_tokens:
        text, _ = _truncate_to_tokens(text, max_tokens)
        was_bounded = True
        missing_after_trunc = _stage_b_validate_entities(text, entities)
        if missing_after_trunc:
            _log_stage_b_fallback(
                "schema",
                reason=(
                    f"output exceeded max_tokens={max_tokens} and post-truncation "
                    f"dropped {len(missing_after_trunc)} entities"
                ),
            )
            return None
    missing = _stage_b_validate_entities(text, entities)
    if missing:
        sample = missing[:3]
        more = "..." if len(missing) > 3 else ""
        _log_stage_b_fallback(
            "schema",
            reason=f"LLM output dropped {len(missing)} entities: {sample}{more}",
        )
        return None
    return {
        "summary_text": text,
        "tokens_in": response.tokens_in,
        "tokens_out": response.tokens_out,
        "latency_ms": response.latency_ms,
        "was_bounded": was_bounded,
    }


def summarise_predecessor(
    artifact_path: str,
    max_tokens: int = DEFAULT_SUMMARY_MAX_TOKENS,
    mode: str = DEFAULT_SUMMARY_MODE,
    schema_hint: str | None = None,
    retrieval_query: str | None = None,
    directive: dict | None = None,
    llm_assist: bool = False,
    llm_client: LLMClient | None = None,
) -> dict:
    """Produce a bounded-token summary of a predecessor artifact.

    See ``docs/cycle-archive/adr/v7-ADR-003-hierarchical-summary.md`` §2 for the
    full algorithm. The default ``extractive`` mode is deterministic and
    verbatim per CO-2: it parses the artifact by extension, runs
    :func:`extract_named_entities` on the full body, and emits a
    ``key_facts:`` YAML prefix followed by the schema-hint-prioritised
    sections, hard-capped at ``max_tokens`` tokens.

    v8.0.0 (P-12) — ``abstractive`` mode is now wired via the Stage A
    heuristic path (:func:`_assemble_abstractive_summary`). It computes
    :func:`_compute_information_density` per section, collapses
    low-density sections (``< 0.30``) to ≤2-line key-phrase summaries,
    and preserves high-density sections (``≥ 0.30``) in ≤5 lines while
    keeping every named entity intact (AC #4). Returns the same 7-key
    dict contract as extractive. The Stage A path falls back to
    extractive when its output would be empty (defensive: matches the
    extractive byte-stable behaviour for empty-body artifacts).

    v8.2.0 (PV-01) — ``llm_assist=True`` opts INTO the LLM-assisted
    Stage B refinement path. Stage A is ALWAYS computed first (it's
    the fallback baseline AND the LLM's hint per
    ``.local/research/v8.0.0_p12_abstractive_stage_b_design.md`` §7).
    When Stage B succeeds the 7-key return adds an 8th
    ``abstractive_stage='b'`` field so downstream status reports can
    distinguish "Stage B succeeded" from "Stage B fell back" (per Stage
    B design §4 SI-4 attribution requirement); when ANY of the seven
    canonical :data:`STAGE_B_FAILURE_MODES` triggers, Stage A output is
    returned with ``abstractive_stage='a'`` and a structured WARNING
    line is emitted to the ``devolaflow.compressor.stage_b`` logger
    (S-5 No Silent Failures). Default ``llm_assist=False`` preserves
    byte-identical v8.0.0-p10 Stage A return shape (the 7-key dict has
    no ``abstractive_stage`` key) — pinned by
    :class:`tests.test_compressor.TestAbstractiveStageBLLM`
    ``test_*_byte_identical_to_stage_a``.

    When ``retrieval_query`` is provided AND non-empty (after stopword strip
    via :func:`_tokenize_for_retrieval`) the section ranker switches from
    pure schema-hint priority to a retrieval-prioritised mode (P-05, v7.2.5)
    that ranks sections by ``0.6 * query_overlap + 0.4 * schema_priority``.
    This surfaces the sections most relevant to a known question first,
    improving density on long-context Q&A artifacts (50k+ token repos)
    where the question is known upfront. Default ``retrieval_query=None``
    preserves byte-stable existing behaviour — verified by
    :class:`tests.test_compressor.TestRetrievalScoring`.

    v8.0.0 (P-02) — when ``directive`` is provided it is forwarded to
    :func:`_select_sections_by_priority` so the focus-keyword overlay
    promotes matching sections to the head of the body. The directive
    field shape is ``{focus_keywords: list[str], max_drop_pct: float}``;
    only ``focus_keywords`` is consumed at the section-ranking layer. The
    directive is mutually exclusive with ``retrieval_query`` — when both
    are provided, ``retrieval_query`` wins (it already encodes a richer
    relevance signal). Default ``directive=None`` preserves the v7.x
    section-ordering behaviour byte-identically (verified by
    :class:`tests.test_compressor.TestSummarisePredecessorRefactor`).

    v8.0.0 (P-02) refactor: this function delegates section selection to
    :func:`_select_sections_for_summary` and body packing to
    :func:`_assemble_summary_body`, bringing its cyclomatic complexity
    from 16 down to ≤10 and closing the historical complexity finding. The
    return contract (7 keys, types, and order of ``covered_sections`` /
    ``dropped_sections``) is preserved bytewise — the helper extraction
    is a pure refactor, NOT a behaviour change.

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
    _validate_summary_args(mode, max_tokens)

    path = Path(artifact_path)
    if not path.exists():
        raise FileNotFoundError(f"artifact not found: {artifact_path}")

    text = path.read_text(encoding="utf-8")
    parser = _PARSER_BY_EXT.get(path.suffix.lower(), _parse_markdown_sections)
    sections = parser(text)
    entities = extract_named_entities(text)

    if mode == "abstractive":
        summary_text, covered, dropped, was_bounded = _assemble_abstractive_summary(
            sections, text, max_tokens
        )
        if not summary_text.strip():
            mode = "extractive"
        else:
            stage_b_summary = summary_text
            stage_b_was_bounded = was_bounded
            stage_label: str | None = None
            if llm_assist:
                stage_label = "a"
                stage_b_result = _invoke_stage_b_llm(
                    artifact_path=artifact_path,
                    full_text=text,
                    stage_a_summary=summary_text,
                    entities=entities,
                    max_tokens=max_tokens,
                    client=llm_client,
                )
                if stage_b_result is not None:
                    stage_b_summary = stage_b_result["summary_text"]
                    stage_b_was_bounded = stage_b_result.get("was_bounded", was_bounded)
                    stage_label = "b"
            result = {
                "summary_text": stage_b_summary,
                "mode": mode,
                "token_count": estimate_tokens(stage_b_summary),
                "extracted_entities": entities,
                "covered_sections": covered,
                "dropped_sections": dropped,
                "was_bounded": stage_b_was_bounded,
            }
            if stage_label is not None:
                result["abstractive_stage"] = stage_label
            return result

    selected = _select_sections_for_summary(sections, schema_hint, retrieval_query, directive)

    fact_lines = ["key_facts:"]
    for entity in entities:
        first_line = entity["value"].splitlines()[0]
        fact_lines.append(f"  - {first_line}")
    facts_block = "\n".join(fact_lines)

    summary_text, covered, dropped, was_bounded = _assemble_summary_body(
        selected, facts_block, max_tokens
    )

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


__all__ = [
    name
    for name in globals()
    if name not in {"__name__", "__package__", "__loader__", "__spec__", "__builtins__", "__all__"}
]
