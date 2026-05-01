"""Cache primitives for the fast-path memory router (v8.3.3 PV-03).

Closes ``M-001`` from ``.local/research/v8.4.0_gap_analysis.md`` §2.1
(jointly with :mod:`devolaflow.memory_router.router`). This module owns
the immutable :class:`MemoryCase` value type and the per-route
invalidation predicates (TTL + version stamp) the router applies before
returning a hit.

Design discipline (per cycle plan §6 R3 — cache-poisoning mitigation):

* **Per-route TTL** — each :class:`MemoryCase` carries ``ttl_days`` plus
  an optional ``last_accessed`` ISO date. :func:`is_ttl_expired` returns
  True when ``today - last_accessed > ttl_days`` (or, when
  ``last_accessed`` is absent, when ``today - last_updated > ttl_days``).
* **Per-route version stamp** — :func:`is_version_stale` returns True
  when the case's ``version_stamp`` differs from
  :data:`devolaflow.__version__`. Breaking changes to dispatch semantics
  bump ``__version__`` and immediately invalidate every recipe authored
  before the bump (cache-miss is the safe path — the caller falls
  through to the live planner per R5 strict).

Both predicates are cheap dict reads — no file IO, no clock skew beyond
the local UTC midnight boundary.

Public surface (consumed by :mod:`devolaflow.memory_router.router` AND
by external operators inspecting cache state):

* :class:`MemoryCase` — frozen dataclass mirroring one ``index.yaml`` row
* :class:`MemoryCacheError` — raised when an index row is structurally
  malformed (S-5 loud — operators see the file path + the offending key)
* :func:`is_ttl_expired` — TTL predicate
* :func:`is_version_stale` — version-stamp predicate
* :func:`build_case_from_dict` — coerce a parsed YAML row → MemoryCase
* :func:`today_iso` — testable wall-clock helper (UTC date, ISO format)

R5 invariant (per cycle plan §5 I-7): when ``DEVOLAFLOW_MEMORY_ROUTER``
is unset (the default), this module is never imported by the dispatch
hot path — :class:`MemoryRouter` short-circuits via env-flag check
before touching :mod:`devolaflow.memory_router.cache`.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Final

__all__ = [
    "DEFAULT_TTL_DAYS",
    "MAX_TTL_DAYS",
    "MIN_TTL_DAYS",
    "MemoryCacheError",
    "MemoryCase",
    "build_case_from_dict",
    "consult_for_dispatch",
    "is_ttl_expired",
    "is_version_stale",
    "today_iso",
]

_logger = logging.getLogger(__name__)


DEFAULT_TTL_DAYS: Final[int] = 30
"""TTL fallback when an index row omits ``ttl_days`` (per ``schemas/memory-case.yaml``)."""

MIN_TTL_DAYS: Final[int] = 1
"""Lowest accepted ``ttl_days`` — anything below 1 day is rejected loudly."""

MAX_TTL_DAYS: Final[int] = 365
"""Highest accepted ``ttl_days`` — caps the route's lifetime at 1 year."""

_REQUIRED_FIELDS: Final[tuple[str, ...]] = (
    "case_id",
    "workflow_type",
    "task_type",
    "summary",
    "recipe_path",
    "version_stamp",
)
"""Index-row keys that MUST be present per ``schemas/memory-case.yaml``."""


class MemoryCacheError(ValueError):
    """Raised when an index row is structurally malformed.

    Loud per Rule S-5 — the operator sees the offending file path AND
    the missing or invalid field. The router catches this exception
    and falls back to a cache miss (the caller continues normally),
    but the warning is logged so the bad row can be repaired.
    """


@dataclass(frozen=True)
class MemoryCase:
    """Immutable in-memory representation of a single index row.

    Frozen so consumers can stash a returned :class:`MemoryCase` in a
    set / use it as a dict key without copy-on-mutate worries. The
    fields mirror the ``schemas/memory-case.yaml`` ``index_fields``
    contract verbatim — adding a new field here MUST be paired with an
    additive bump to that schema.

    Attributes:
        case_id: Stable identifier (``[a-z0-9-]``); equals the recipe
            file basename without ``.md``.
        workflow_type: Primary routing key (e.g. ``feature-implementation``).
        task_type: Secondary routing key (e.g. ``implement``).
        summary: Verbatim one-sentence summary lifted from the recipe
            frontmatter at seed time.
        recipe_path: Repo-relative path to the recipe markdown body.
        version_stamp: Semver string recorded at recipe-write time;
            compared against :data:`devolaflow.__version__` for the
            version-stamp invalidation check.
        ttl_days: How many days the route remains "fresh" after its
            last touch (default :data:`DEFAULT_TTL_DAYS`).
        last_accessed: ISO date of the most recent cache hit; ``""``
            on freshly seeded entries (in which case the TTL clock
            ticks from ``last_updated``).
        last_updated: ISO date the index row was authored or refreshed;
            used as the TTL fallback anchor when ``last_accessed`` is
            empty. Supplied by the parent index's ``last_updated`` key.
        repo_signal: Optional tertiary key disambiguating identical
            ``(workflow_type, task_type)`` pairs across repos.
        tags: Free-form labels (``[r5-strict, default-off, ...]``) for
            human-faceted browsing of the recipe library.
    """

    case_id: str
    workflow_type: str
    task_type: str
    summary: str
    recipe_path: str
    version_stamp: str
    ttl_days: int = DEFAULT_TTL_DAYS
    last_accessed: str = ""
    last_updated: str = ""
    repo_signal: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        """Validate scalar invariants at construction time.

        We deliberately keep validation tight here so callers can rely
        on a constructed :class:`MemoryCase` being well-formed. The
        :func:`build_case_from_dict` factory funnels every external
        creation through ``__post_init__`` so YAML-derived rows are
        validated identically to test-constructed instances.
        """
        if not self.case_id:
            raise MemoryCacheError("MemoryCase.case_id MUST be a non-empty string")
        if not self.workflow_type:
            raise MemoryCacheError("MemoryCase.workflow_type MUST be a non-empty string")
        if not self.task_type:
            raise MemoryCacheError("MemoryCase.task_type MUST be a non-empty string")
        if not self.recipe_path:
            raise MemoryCacheError("MemoryCase.recipe_path MUST be a non-empty string")
        if not self.recipe_path.startswith(".local/memory/cases/"):
            raise MemoryCacheError(
                f"MemoryCase.recipe_path must live under .local/memory/cases/ "
                f"(per schemas/memory-case.yaml + S-2); got {self.recipe_path!r}"
            )
        if not self.version_stamp:
            raise MemoryCacheError("MemoryCase.version_stamp MUST be a non-empty semver string")
        if not (MIN_TTL_DAYS <= self.ttl_days <= MAX_TTL_DAYS):
            raise MemoryCacheError(
                f"MemoryCase.ttl_days must be within [{MIN_TTL_DAYS}, {MAX_TTL_DAYS}]; "
                f"got {self.ttl_days!r} for case_id={self.case_id!r}"
            )


def today_iso() -> str:
    """Return today's UTC date as an ISO ``YYYY-MM-DD`` string.

    Wrapped in a function so tests can monkeypatch this single
    indirection without touching :mod:`datetime` globally.
    """
    return datetime.now(UTC).date().isoformat()


def _parse_iso_date(value: str, *, field_name: str, case_id: str) -> date | None:
    """Parse an ISO ``YYYY-MM-DD`` date or return None for empty strings.

    Empty strings (the seed default) return ``None`` — a missing
    timestamp is a legitimate state, not an error. Malformed strings
    raise :class:`MemoryCacheError` so the operator sees the bad row.
    """
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise MemoryCacheError(
            f"MemoryCase {case_id!r}: field {field_name!r} is not a valid ISO date "
            f"(YYYY-MM-DD); got {value!r}"
        ) from exc


def is_ttl_expired(case: MemoryCase, *, today: str | None = None) -> bool:
    """Return True iff *case* has aged past its ``ttl_days`` window.

    The TTL anchor is :attr:`MemoryCase.last_accessed` when present,
    otherwise :attr:`MemoryCase.last_updated`. When BOTH are empty
    (a programmer's mistake — every well-formed index row carries at
    least ``last_updated`` from the parent index header), the route
    is treated as fresh-but-undated and we return ``False`` rather
    than expire it spuriously. The router logs a WARNING in that case
    via :func:`devolaflow.memory_router.router.MemoryRouter._build_cases`.

    Args:
        case: The :class:`MemoryCase` to probe.
        today: Optional ISO ``YYYY-MM-DD`` override for the wall clock
            (test injection). Defaults to :func:`today_iso`.

    Returns:
        ``True`` when ``today - anchor > ttl_days``; ``False`` otherwise.
    """
    anchor_str = case.last_accessed or case.last_updated
    if not anchor_str:
        return False
    anchor = _parse_iso_date(
        anchor_str,
        field_name="last_accessed/last_updated",
        case_id=case.case_id,
    )
    if anchor is None:
        return False
    today_str = today if today is not None else today_iso()
    today_date = _parse_iso_date(today_str, field_name="today", case_id=case.case_id)
    if today_date is None:
        # Defensive — today_iso() never produces an empty string.
        return False
    age_days = (today_date - anchor).days
    return age_days > case.ttl_days


def is_version_stale(case: MemoryCase, current_version: str) -> bool:
    """Return True iff *case*'s ``version_stamp`` differs from *current_version*.

    String equality is intentional — we want byte-exact matches because
    the consumer (the live planner) is keyed by the running runtime
    version. Pre-release tags (``8.3.3-rc.1`` vs ``8.3.3``) DO trigger
    invalidation, which is the safe behavior: pre-release recipes may
    rely on schema drafts that the GA release never shipped.

    Args:
        case: The :class:`MemoryCase` to probe.
        current_version: The running runtime's
            :data:`devolaflow.__version__` value (passed in so this
            module avoids a hard import of :mod:`devolaflow` at probe
            time — keeps the cache layer dependency-free).

    Returns:
        ``True`` when the recipe was authored against a different
        runtime version (treat as miss); ``False`` when the route is
        version-current.
    """
    return case.version_stamp != current_version


def build_case_from_dict(
    row: Any,
    *,
    index_last_updated: str = "",
    source_path: str = "<index.yaml>",
) -> MemoryCase:
    """Coerce a parsed YAML index row into a validated :class:`MemoryCase`.

    Funnels every external construction through one validator so the
    router and the tests see identical error semantics. The
    *index_last_updated* parameter is the parent index's top-level
    ``last_updated`` field — it becomes the row's TTL fallback anchor
    when the row itself omits ``last_accessed``.

    Args:
        row: Parsed YAML row (expected to be a ``dict``).
        index_last_updated: ISO date from the index header; promoted
            into :attr:`MemoryCase.last_updated` when the row doesn't
            carry its own. Empty string when the index header is
            missing the field (a row-level warning is logged).
        source_path: Path to the index file the row came from; appears
            in error messages so operators can locate the offending row.

    Returns:
        A frozen, validated :class:`MemoryCase` instance.

    Raises:
        MemoryCacheError: When the row is not a mapping, or when any
            of :data:`_REQUIRED_FIELDS` is missing / has the wrong
            type, or when a derived constraint (``recipe_path`` prefix,
            ``ttl_days`` bounds) is violated.
    """
    if not isinstance(row, dict):
        raise MemoryCacheError(
            f"{source_path}: case row must be a YAML mapping; got {type(row).__name__}"
        )

    missing = [name for name in _REQUIRED_FIELDS if not row.get(name)]
    if missing:
        case_hint = row.get("case_id", "<unknown>")
        raise MemoryCacheError(
            f"{source_path}: case row {case_hint!r} missing required fields: {', '.join(missing)}"
        )

    raw_ttl = row.get("ttl_days", DEFAULT_TTL_DAYS)
    if isinstance(raw_ttl, bool) or not isinstance(raw_ttl, int):
        raise MemoryCacheError(
            f"{source_path}: case row {row.get('case_id')!r} has non-int ttl_days "
            f"({type(raw_ttl).__name__!s}={raw_ttl!r})"
        )

    raw_tags = row.get("tags", ())
    if not isinstance(raw_tags, list | tuple):
        raise MemoryCacheError(
            f"{source_path}: case row {row.get('case_id')!r} has non-list tags "
            f"({type(raw_tags).__name__!s})"
        )
    tags_tuple = tuple(str(t) for t in raw_tags)

    return MemoryCase(
        case_id=str(row["case_id"]),
        workflow_type=str(row["workflow_type"]),
        task_type=str(row["task_type"]),
        summary=str(row["summary"]),
        recipe_path=str(row["recipe_path"]),
        version_stamp=str(row["version_stamp"]),
        ttl_days=int(raw_ttl),
        last_accessed=str(row.get("last_accessed", "") or ""),
        last_updated=str(row.get("last_updated", index_last_updated) or index_last_updated),
        repo_signal=str(row.get("repo_signal", "") or ""),
        tags=tags_tuple,
    )


# ---------------------------------------------------------------------------
# v9.1.4 PV-04 — consult_for_dispatch (advisory hint surface)
# ---------------------------------------------------------------------------
#
# Surfaces matched MemoryCase entries as ADVISORY hints in the dispatch
# payload's `change_context.memory_case_hits` sub-field (NEST extension per
# A-2.3). Distinct from `MemoryRouter.lookup_case()` (the planner-replacement
# fast-path keyed on workflow_type+task_type). consult_for_dispatch is keyword-
# scored — caller passes a partially-formed dispatch payload and gets back
# the top-K MemoryCase hits whose summary/tags overlap the task description.
#
# W-20 reuse: gated by the SAME env-flag as MemoryRouter
# (DEVOLAFLOW_MEMORY_ROUTER) — both surfaces consume `.local/memory/cases/
# index.yaml` and are activated on the same operator opt-in. Per the v9.2.0
# cycle plan §"Self-iteration constraint compliance matrix" W-20 row,
# DEVOLAFLOW_MEMORY_CONSULT was discussed by name but ultimately REUSED
# DEVOLAFLOW_MEMORY_ROUTER ("0 new flags across the entire 7-PV cycle").

_CONSULT_ENV_FLAG: Final[str] = "DEVOLAFLOW_MEMORY_ROUTER"
"""Activation flag — REUSED from :mod:`devolaflow.memory_router.router`.

Set to the literal string ``"1"`` to enable. Per W-20 reuse-first this is
the SAME flag the fast-path :class:`MemoryRouter` consults — the two
surfaces share the same operator opt-in and the same
``.local/memory/cases/index.yaml`` source-of-truth, so introducing a
separate ``DEVOLAFLOW_MEMORY_CONSULT`` flag would have failed the
behavioural-orthogonality test in
``workflow-system/agent/references/env-flags.md`` §7.
"""

_CONSULT_ENV_TRUTHY: Final[str] = "1"
"""R5 strict — only the literal ``"1"`` activates; everything else is OFF."""

_DEFAULT_CONSULT_INDEX_PATH: Final[Path] = Path(".local/memory/cases/index.yaml")
"""Resolved against ``Path.cwd()`` at call time (NOT import time) so tests
using ``monkeypatch.chdir(tmp_path)`` get fresh resolution."""

_CONSULT_STOPWORDS: Final[frozenset[str]] = frozenset(
    {
        "the",
        "and",
        "for",
        "with",
        "from",
        "into",
        "this",
        "that",
        "have",
        "will",
    }
)
"""≤ 10 hardcoded English stopwords. Intentionally small — overlap scoring
is lightweight, and growing the list inflates the symbol's surface area
without measurable recall improvement on the canonical .local/memory/cases/
index shape."""

_CONSULT_KEYWORD_SPLIT_RE: Final[re.Pattern[str]] = re.compile(r"[^a-z0-9]+")
"""Lowercase-only tokenizer; matches word-boundaries on any non-alnum run."""

_CONSULT_DEFAULT_MAX_HITS: Final[int] = 3
"""Caps the returned hit list at 3 entries (matches the documented
``change_context.memory_case_hits`` schema cap of ≤ 3)."""


def _extract_dispatch_keywords(payload: Any) -> set[str]:
    """Return a lowercased keyword set from ``payload.task.{description,title}``.

    Defensive against missing keys / non-dict structures so a malformed
    payload returns an empty keyword set rather than raising. Matches the
    lean dispatch shape (``payload['task']['title']`` per
    ``schemas/lean-dispatch.yaml#lean_format_spec.task``) AND the verbose
    shape (``payload['task']['description']`` per the original_example).
    Stopwords + tokens shorter than 3 characters are dropped.
    """
    if not isinstance(payload, dict):
        return set()
    task = payload.get("task")
    if not isinstance(task, dict):
        return set()

    sources: list[str] = []
    for key in ("description", "title", "goal"):
        value = task.get(key)
        if isinstance(value, str) and value.strip():
            sources.append(value)
    top_goal = payload.get("goal")
    if isinstance(top_goal, str) and top_goal.strip():
        sources.append(top_goal)
    if not sources:
        return set()

    tokens: set[str] = set()
    for src in sources:
        for raw in _CONSULT_KEYWORD_SPLIT_RE.split(src.lower()):
            if len(raw) < 3:
                continue
            if raw in _CONSULT_STOPWORDS:
                continue
            tokens.add(raw)
    return tokens


def _case_keyword_corpus(case: MemoryCase) -> set[str]:
    """Lowercased keyword set extracted from a case's matchable fields.

    Mirrors :func:`_extract_dispatch_keywords` tokenisation so overlap
    scoring is symmetric. Pulls from ``summary`` + ``tags`` +
    ``workflow_type`` + ``task_type``; ``case_id`` and ``recipe_path`` are
    intentionally excluded — they leak filename noise that would inflate
    spurious matches.
    """
    sources: list[str] = [case.summary, case.workflow_type, case.task_type]
    sources.extend(str(tag) for tag in case.tags)
    tokens: set[str] = set()
    for src in sources:
        for raw in _CONSULT_KEYWORD_SPLIT_RE.split(src.lower()):
            if len(raw) < 3:
                continue
            if raw in _CONSULT_STOPWORDS:
                continue
            tokens.add(raw)
    return tokens


def _resolve_current_version_lazy() -> str:
    """Lazy-import :data:`devolaflow.__version__` (avoids import cycle).

    Mirrors :func:`devolaflow.memory_router.router._resolve_current_version`.
    Kept as a separate helper so :func:`consult_for_dispatch` stays pure
    function (no module-level side effects).
    """
    from devolaflow import __version__ as _devolaflow_version  # noqa: PLC0415

    return _devolaflow_version


def _is_consult_enabled(env: dict[str, str] | None) -> bool:
    """Pure env-flag read — NO file IO, NO subprocess.

    R5 strict: only the literal string ``"1"`` activates the consultation
    surface. Every other value (unset, ``"0"``, ``""``, ``"true"``,
    ``"yes"``, etc.) is treated as OFF.
    """
    source = env if env is not None else os.environ
    return source.get(_CONSULT_ENV_FLAG, "") == _CONSULT_ENV_TRUTHY


def consult_for_dispatch(
    payload: dict[str, Any],
    repo_root: Path | str,
    *,
    max_hits: int = _CONSULT_DEFAULT_MAX_HITS,
    env: dict[str, str] | None = None,
    current_version: str | None = None,
    today: str | None = None,
) -> list[MemoryCase]:
    """Return up to ``max_hits`` :class:`MemoryCase` hits matched against ``payload``.

    The advisory companion to :meth:`devolaflow.memory_router.router.MemoryRouter.lookup_case`
    (the planner-replacement fast-path). ``consult_for_dispatch`` does NOT
    short-circuit a planner decision — it returns case_id / summary
    candidates that the L0 dispatcher can surface in the dispatch payload's
    ``change_context.memory_case_hits`` sub-field (NEST extension per
    A-2.3, schema documented in ``schemas/lean-dispatch.yaml#lean_format_spec.change_context``).

    Decision tree (cache-miss is ALWAYS the safe path per R5 strict):

    1. Env-flag ``DEVOLAFLOW_MEMORY_ROUTER`` not set to literal ``"1"`` →
       return ``[]`` immediately. NO file IO. NO YAML parse. NO version
       resolve. (R5 strict zero-overhead — verified by
       ``tests/test_memory_consult_for_dispatch.py::test_env_flag_off_returns_empty_list``.)
    2. ``.local/memory/cases/index.yaml`` missing → log DEBUG (NOT
       WARNING — empty cases dir is a legitimate new-repo state) and
       return ``[]``.
    3. Index file present but malformed (YAML parse error / wrong shape)
       → log WARNING via :mod:`logging`, return ``[]`` (S-5 explicit error
       state — operator sees the path + the failing key). Caller continues
       normally with no advisory hints.
    4. Index well-formed → score every non-stale, non-expired
       :class:`MemoryCase` against the dispatch keywords; return top
       ``max_hits`` by overlap score (ties broken by ``last_accessed``
       desc, then ``case_id`` ascending for determinism).

    Match heuristic:

    * Extract keywords from ``payload['task']['description']`` +
      ``payload['task']['title']`` + ``payload['task']['goal']`` +
      ``payload['goal']`` (defensive — missing keys are skipped, never
      raise). Lowercase; drop stopwords (10 common English) and tokens
      shorter than 3 characters.
    * For each :class:`MemoryCase`, compute a corpus from
      ``summary + tags + workflow_type + task_type``. Score = size of
      keyword-set intersection.
    * Skip cases with score 0, with ``is_version_stale(current_version)``,
      or with ``is_ttl_expired(today=today)``.
    * Sort surviving cases by ``(-score, -last_accessed, +case_id)`` and
      return the first ``max_hits``.

    Args:
        payload: Lean or verbose dispatch payload (any dict shape — the
            extractor is defensive). Reads only; never mutates.
        repo_root: Path to the consumer repo root. Tests pass
            ``tmp_path``; production passes the L0 cwd.
        max_hits: Cap on returned hits. Defaults to 3 (matches the
            documented schema cap on ``memory_case_hits``).
        env: Optional env dict for tests; defaults to :data:`os.environ`.
        current_version: Optional override for the version-stale check;
            defaults to :data:`devolaflow.__version__` resolved lazily so
            this module stays import-cycle-free.
        today: Optional ISO date override for the TTL check; defaults to
            :func:`today_iso`.

    Returns:
        List of up to ``max_hits`` :class:`MemoryCase` instances ordered
        by descending overlap score. Empty list when env-flag is OFF, the
        index is missing, the index is malformed, or no case scored > 0.

    Production callers: surface the returned ``case_id`` strings in the
    dispatch payload's ``change_context.memory_case_hits`` block (PV-06
    end-to-end test ``tests/test_capability_e2e.py`` will exercise the
    full dispatch-side wire-up; in v9.1.4 PV-04 this function is added to
    ``scripts/detect_dead_apis.py::DEFAULT_ALLOWLIST`` with the comment
    pointing at the upcoming PV-06 caller).
    """
    if not _is_consult_enabled(env):
        return []

    cap = max(0, int(max_hits))
    if cap == 0:
        return []

    keywords = _extract_dispatch_keywords(payload)
    if not keywords:
        return []

    root = Path(repo_root)
    index_path = root / _DEFAULT_CONSULT_INDEX_PATH
    if not index_path.exists():
        _logger.debug(
            "[memory_router.consult] index file %s not present — returning [] "
            "(legitimate new-repo state)",
            index_path,
        )
        return []

    try:
        text = index_path.read_text(encoding="utf-8")
    except OSError as exc:
        _logger.warning(
            "[memory_router.consult] cannot read index at %s: %s — returning [] "
            "(S-5 explicit error state; caller continues without advisory hints)",
            index_path,
            exc,
        )
        return []

    try:
        import yaml  # noqa: PLC0415

        payload_yaml = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        _logger.warning(
            "[memory_router.consult] index at %s is not valid YAML: %s — "
            "returning [] (S-5 explicit error state)",
            index_path,
            exc,
        )
        return []
    except ImportError as exc:  # pragma: no cover — defensive
        _logger.warning(
            "[memory_router.consult] PyYAML not installed: %s — returning []",
            exc,
        )
        return []

    if payload_yaml is None:
        return []
    if not isinstance(payload_yaml, dict):
        _logger.warning(
            "[memory_router.consult] index at %s top-level must be a mapping; "
            "got %s — returning [] (S-5 explicit error state)",
            index_path,
            type(payload_yaml).__name__,
        )
        return []

    raw_cases = payload_yaml.get("cases", [])
    if not isinstance(raw_cases, list):
        _logger.warning(
            "[memory_router.consult] index at %s 'cases' key must be a list; "
            "got %s — returning [] (S-5 explicit error state)",
            index_path,
            type(raw_cases).__name__,
        )
        return []

    index_last_updated = str(payload_yaml.get("last_updated", "") or "")
    runtime_version = (
        current_version if current_version is not None else _resolve_current_version_lazy()
    )

    scored: list[tuple[int, str, str, MemoryCase]] = []
    for idx, row in enumerate(raw_cases):
        try:
            case = build_case_from_dict(
                row,
                index_last_updated=index_last_updated,
                source_path=str(index_path),
            )
        except MemoryCacheError as exc:
            row_hint = (
                row.get("case_id", f"<row#{idx}>") if isinstance(row, dict) else f"<row#{idx}>"
            )
            _logger.warning(
                "[memory_router.consult] dropping malformed case row %r in %s: %s",
                row_hint,
                index_path,
                exc,
            )
            continue

        if is_version_stale(case, runtime_version):
            continue
        try:
            expired = is_ttl_expired(case, today=today)
        except MemoryCacheError as exc:
            _logger.warning(
                "[memory_router.consult] case %r has malformed date field; skipping: %s",
                case.case_id,
                exc,
            )
            continue
        if expired:
            continue

        case_corpus = _case_keyword_corpus(case)
        score = len(keywords & case_corpus)
        if score <= 0:
            continue

        # Sort key tuple: (-score, -last_accessed_str, +case_id) so highest
        # score wins; ties broken by most-recent access (descending), then
        # lexicographic case_id ascending. The string-sort on dates works
        # because ISO YYYY-MM-DD is lexicographically chronological.
        scored.append((-score, _negate_iso_date(case.last_accessed), case.case_id, case))

    scored.sort(key=lambda triple: (triple[0], triple[1], triple[2]))
    return [case for _score, _neg_date, _cid, case in scored[:cap]]


def _negate_iso_date(value: str) -> str:
    """Return a string sort key that orders newer ISO dates first.

    Empty strings sort AFTER any real date (so undated cases lose ties
    against dated cases). For real dates, we negate by subtracting from
    a sentinel year far in the future and emitting the result as
    ``YYYY-MM-DD`` again so plain ``sorted()`` (ascending) places newer
    dates first — pure-string indirection avoids importing :mod:`datetime`
    here for what is otherwise a hot-path tie breaker.
    """
    if not value:
        return "9999-12-31"
    try:
        anchor = date.fromisoformat(value)
    except ValueError:
        return "9999-12-31"
    delta = date(9999, 12, 31).toordinal() - anchor.toordinal()
    return f"{delta:08d}"
