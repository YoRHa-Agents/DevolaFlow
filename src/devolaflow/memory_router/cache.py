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

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any, Final

__all__ = [
    "DEFAULT_TTL_DAYS",
    "MAX_TTL_DAYS",
    "MIN_TTL_DAYS",
    "MemoryCacheError",
    "MemoryCase",
    "build_case_from_dict",
    "is_ttl_expired",
    "is_version_stale",
    "today_iso",
]


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
