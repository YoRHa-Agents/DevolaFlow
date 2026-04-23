"""Fast-path memory router (v8.3.3 PV-03 — closes M-001).

Closes ``M-001`` from ``.local/research/v8.4.0_gap_analysis.md`` §2.1:
when ``DEVOLAFLOW_MEMORY_ROUTER=1`` is set AND
``.local/memory/cases/index.yaml`` carries a fresh route for the
``(workflow_type, task_type)`` (and optionally ``repo_signal``) probe,
returns a :class:`MemoryCase` so the L0/L1 dispatcher can skip
re-deriving workflow + stage decomposition from SKILL.md (~3K tokens
of planning context per dispatch — see gap analysis §1).

Cache-miss is the SAFE path (R5 strict) — when the env-flag is unset,
the index is missing, the YAML is malformed, the route's TTL has
expired, or the route's ``version_stamp`` differs from
:data:`devolaflow.__version__`, :func:`lookup_case` returns ``None``
and the caller falls through to the existing planner unchanged. Per
the cycle plan §6 R3 mitigation, the router NEVER raises in normal
operation — every error path logs a WARNING with actionable text per
S-5 then degrades to a miss.

Activation discipline (per cycle plan §5 I-7 R5 strict):

* :func:`is_router_enabled` is a pure env-flag read with NO file IO.
  Suitable for the dispatch hot path — always early-return BEFORE
  touching the rest of this module.
* :class:`MemoryRouter` lazily loads the index on first
  :meth:`MemoryRouter.lookup_case` call; subsequent calls reuse the
  in-process cache. The lifetime of one :class:`MemoryRouter`
  instance scopes the in-process cache (instantiate per dispatch
  cycle to pick up index edits).
* When the env-flag is unset, even constructing a :class:`MemoryRouter`
  is a no-op — :meth:`MemoryRouter.lookup_case` short-circuits to
  ``None`` before touching the filesystem.

Public surface (consumed by L0/L1 dispatchers + tests):

* :func:`is_router_enabled` — pure env-flag read; never spawns IO
* :func:`lookup_case` — flat-call convenience wrapping
  :meth:`MemoryRouter.lookup_case` for callers that don't need the
  router instance for cache reuse
* :class:`MemoryRouter` — full API with lazy loading + in-process cache
* :class:`MemoryRouterError` — raised ONLY by callers that explicitly
  opt into strict mode via :meth:`MemoryRouter.lookup_case_strict`
  (cf. lifecycle hook strict-mode pattern in v8.3.2 PV-02)

External canonical URL (per S-7): https://github.com/YoRHa-Agents/DevolaFlow
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

import yaml

from devolaflow.memory_router.cache import (
    MemoryCacheError,
    MemoryCase,
    build_case_from_dict,
    is_ttl_expired,
    is_version_stale,
)

logger = logging.getLogger(__name__)


__all__ = [
    "DEFAULT_INDEX_PATH",
    "ENV_FLAG",
    "MemoryRouter",
    "MemoryRouterError",
    "is_router_enabled",
    "lookup_case",
]


ENV_FLAG: Final[str] = "DEVOLAFLOW_MEMORY_ROUTER"
"""Primary activation env-flag. Set to ``"1"`` to enable lookups.

Any other value (including ``"0"``, empty string, and unset) leaves
the router DISABLED for R5 strict compatibility with the v8.3.2
baseline."""

DEFAULT_INDEX_PATH: Final[Path] = Path(".local/memory/cases/index.yaml")
"""Default lookup target relative to ``Path.cwd()``.

Resolved at lookup time (NOT import time) so tests using
``monkeypatch.chdir(tmp_path)`` get fresh resolution. Mirrors the
:func:`devolaflow.learnings.resolve_learnings_path` precedent.
"""


class MemoryRouterError(RuntimeError):
    """Raised by :meth:`MemoryRouter.lookup_case_strict`.

    The DEFAULT lookup path (:meth:`MemoryRouter.lookup_case`) NEVER
    raises — failures degrade to ``None`` (cache-miss). The strict
    variant exists for callers that intentionally want to surface
    schema breakage rather than fall through (e.g. CI verification
    scripts or operator-driven inspection tools).
    """


def is_router_enabled(env: dict[str, str] | None = None) -> bool:
    """Return True iff :data:`ENV_FLAG` is set to ``"1"`` in *env*.

    Pure env-flag read — no file IO, no subprocess. Suitable for the
    dispatch hot path; always early-return BEFORE any other
    memory_router code runs (R5 strict per cycle plan §5 I-7).

    When *env* is ``None``, reads :data:`os.environ`.
    """
    source = env if env is not None else os.environ
    return source.get(ENV_FLAG, "0") == "1"


@dataclass(frozen=True)
class _IndexLoadResult:
    """Internal — outcome of one :meth:`MemoryRouter._load_index` call.

    Frozen so the in-process cache stores an immutable snapshot.
    Empty list + non-None ``warning`` indicates "load failed gracefully";
    populated list indicates "load succeeded with N entries".
    """

    cases: tuple[MemoryCase, ...]
    index_path: Path
    warning: str | None = None
    failed_rows: tuple[str, ...] = field(default_factory=tuple)


class MemoryRouter:
    """Fast-path recipe lookup against ``.local/memory/cases/index.yaml``.

    Designed to be cheap to instantiate and reasonably cheap to call.
    Construction is a no-op (no file IO); the index is loaded lazily
    on the first :meth:`lookup_case` call and cached on the instance
    for the lifetime of the dispatch cycle.

    Reuse pattern:

    .. code-block:: python

        router = MemoryRouter()  # cheap; nothing loaded yet
        for task in dispatch_queue:
            case = router.lookup_case(task.workflow_type, task.task_type)
            if case is None:
                # Cache miss — fall through to live planner (R5 strict)
                ...

    Constructor parameters allow tests to inject a custom env dict, a
    pre-built case list (skipping IO entirely), or an alternate index
    path under tmp_path.
    """

    __slots__ = ("_cache", "_current_version", "_env", "_index_path")

    def __init__(
        self,
        *,
        env: dict[str, str] | None = None,
        index_path: Path | str | None = None,
        current_version: str | None = None,
        cases: list[MemoryCase] | None = None,
    ) -> None:
        self._env = env if env is not None else dict(os.environ)
        self._index_path: Path = Path(index_path) if index_path else _resolve_default_index_path()
        self._current_version = (
            current_version if current_version is not None else _resolve_current_version()
        )
        if cases is not None:
            self._cache: _IndexLoadResult | None = _IndexLoadResult(
                cases=tuple(cases),
                index_path=self._index_path,
                warning=None,
            )
        else:
            self._cache = None

    @property
    def index_path(self) -> Path:
        """Resolved index path — exposed for diagnostics + test assertions."""
        return self._index_path

    @property
    def current_version(self) -> str:
        """Runtime version stamp used for the version-stale check."""
        return self._current_version

    def is_enabled(self) -> bool:
        """Return True iff this router would actually perform lookups.

        Mirror of :func:`is_router_enabled` scoped to the constructor's
        captured env dict (so tests can build a router with a frozen
        env without monkeypatching :data:`os.environ`).
        """
        return self._env.get(ENV_FLAG, "0") == "1"

    def lookup_case(
        self,
        workflow_type: str,
        task_type: str,
        *,
        repo_signal: str | None = None,
    ) -> MemoryCase | None:
        """Return a fresh :class:`MemoryCase` for the probe, or ``None``.

        Decision tree (cache-miss is ALWAYS the safe path per R5 strict):

        1. Env-flag unset → return ``None`` immediately. NO file IO.
        2. Index missing OR malformed → log WARNING, return ``None``.
        3. No row matches ``(workflow_type, task_type, repo_signal?)`` →
           return ``None``.
        4. Matching row's ``version_stamp`` != current version OR row is
           past its TTL → return ``None`` (treat as miss, do NOT raise).
        5. Otherwise → return the :class:`MemoryCase` (frozen instance).

        Args:
            workflow_type: Primary routing key (e.g.
                ``"feature-implementation"``).
            task_type: Secondary routing key (e.g. ``"implement"``).
            repo_signal: Optional tertiary key. When supplied, narrows
                the match to rows whose ``repo_signal`` equals this
                value exactly (case-sensitive). When ``None`` (the
                default), the first matching row by index order wins
                regardless of its ``repo_signal``.

        Returns:
            A :class:`MemoryCase` on a fresh hit, ``None`` otherwise.
            Callers MUST treat ``None`` as a cache-miss and fall
            through to the existing planner.
        """
        if not self.is_enabled():
            return None

        if not workflow_type or not task_type:
            logger.warning(
                "[memory_router] lookup_case called with empty key "
                "(workflow_type=%r, task_type=%r); returning None "
                "(callers must supply both keys)",
                workflow_type,
                task_type,
            )
            return None

        load = self._cache if self._cache is not None else self._load_index()
        self._cache = load

        for case in load.cases:
            if case.workflow_type != workflow_type:
                continue
            if case.task_type != task_type:
                continue
            if repo_signal is not None and case.repo_signal != repo_signal:
                continue

            if is_version_stale(case, self._current_version):
                logger.info(
                    "[memory_router] case %r matched but version-stale "
                    "(version_stamp=%s, current=%s); treating as miss",
                    case.case_id,
                    case.version_stamp,
                    self._current_version,
                )
                continue
            try:
                expired = is_ttl_expired(case)
            except MemoryCacheError as exc:
                logger.warning(
                    "[memory_router] case %r has malformed date field; treating as miss: %s",
                    case.case_id,
                    exc,
                )
                continue
            if expired:
                logger.info(
                    "[memory_router] case %r matched but TTL-expired "
                    "(ttl_days=%d, last_accessed=%r, last_updated=%r); treating as miss",
                    case.case_id,
                    case.ttl_days,
                    case.last_accessed,
                    case.last_updated,
                )
                continue

            return case

        return None

    def lookup_case_strict(
        self,
        workflow_type: str,
        task_type: str,
        *,
        repo_signal: str | None = None,
    ) -> MemoryCase | None:
        """Strict variant — raises :class:`MemoryRouterError` on schema breaks.

        Behaves identically to :meth:`lookup_case` for the happy path
        and the genuine miss paths (no matching row, TTL expiry,
        version stale). The DIFFERENCE: when the index file exists but
        is structurally malformed (YAML parse error, non-list ``cases``,
        missing required field on a row, etc.), the strict variant
        raises :class:`MemoryRouterError` instead of degrading silently.

        Intended for CI verification scripts and operator inspection
        tools — NOT for the dispatch hot path. The dispatch path MUST
        use :meth:`lookup_case` so a corrupt index never blocks
        production work.
        """
        if not self.is_enabled():
            return None

        load = self._load_index()
        if load.warning is not None:
            raise MemoryRouterError(load.warning)
        if load.failed_rows:
            raise MemoryRouterError(
                f"memory_router: {len(load.failed_rows)} malformed rows in "
                f"{load.index_path}: {', '.join(load.failed_rows)}"
            )

        # Replace the cache so a subsequent lookup_case() reuses it.
        self._cache = load
        return self.lookup_case(workflow_type, task_type, repo_signal=repo_signal)

    def _load_index(self) -> _IndexLoadResult:
        """Read + parse + validate ``index.yaml`` into a tuple of cases.

        NEVER raises — every error path returns an :class:`_IndexLoadResult`
        with an empty ``cases`` tuple AND a non-None ``warning`` so the
        router degrades to a miss while still surfacing the failure to
        the operator via the ``logger.warning`` call.
        """
        path = self._index_path
        if not path.exists():
            logger.info(
                "[memory_router] index file %s not present; cache disabled, "
                "callers fall through to live planner (this is normal on a "
                "fresh checkout)",
                path,
            )
            return _IndexLoadResult(cases=(), index_path=path, warning=None)

        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            warning = (
                f"memory_router: cannot read index at {path}: {exc} — "
                "treating as cache-miss (caller falls through to live planner)"
            )
            logger.warning("[memory_router] %s", warning)
            return _IndexLoadResult(cases=(), index_path=path, warning=warning)

        try:
            payload = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            warning = (
                f"memory_router: index at {path} is not valid YAML: {exc} — "
                "treating as cache-miss (caller falls through to live planner)"
            )
            logger.warning("[memory_router] %s", warning)
            return _IndexLoadResult(cases=(), index_path=path, warning=warning)

        if payload is None:
            return _IndexLoadResult(cases=(), index_path=path, warning=None)

        if not isinstance(payload, dict):
            warning = (
                f"memory_router: index at {path} top-level must be a mapping; "
                f"got {type(payload).__name__} — treating as cache-miss"
            )
            logger.warning("[memory_router] %s", warning)
            return _IndexLoadResult(cases=(), index_path=path, warning=warning)

        raw_cases = payload.get("cases", [])
        if not isinstance(raw_cases, list):
            warning = (
                f"memory_router: index at {path} 'cases' key must be a list; "
                f"got {type(raw_cases).__name__} — treating as cache-miss"
            )
            logger.warning("[memory_router] %s", warning)
            return _IndexLoadResult(cases=(), index_path=path, warning=warning)

        index_last_updated = str(payload.get("last_updated", "") or "")
        cases: list[MemoryCase] = []
        failed: list[str] = []
        for idx, row in enumerate(raw_cases):
            try:
                case = build_case_from_dict(
                    row,
                    index_last_updated=index_last_updated,
                    source_path=str(path),
                )
            except MemoryCacheError as exc:
                row_hint = (
                    row.get("case_id", f"<row#{idx}>") if isinstance(row, dict) else f"<row#{idx}>"
                )
                logger.warning(
                    "[memory_router] dropping malformed case row %r in %s: %s",
                    row_hint,
                    path,
                    exc,
                )
                failed.append(str(row_hint))
                continue
            cases.append(case)

        return _IndexLoadResult(
            cases=tuple(cases),
            index_path=path,
            warning=None,
            failed_rows=tuple(failed),
        )


def lookup_case(
    workflow_type: str,
    task_type: str,
    *,
    repo_signal: str | None = None,
    env: dict[str, str] | None = None,
    index_path: Path | str | None = None,
    current_version: str | None = None,
) -> MemoryCase | None:
    """Module-level convenience equivalent to ``MemoryRouter().lookup_case(...)``.

    Flat-call style for callers that don't need to retain the
    :class:`MemoryRouter` instance for cache reuse. R5 strict
    zero-overhead is preserved — when the env-flag is unset,
    :func:`is_router_enabled` returns False BEFORE the more expensive
    :class:`MemoryRouter` construction runs, and we short-circuit to
    ``None`` without touching the filesystem.

    The keyword-only constructor pass-throughs (``env``, ``index_path``,
    ``current_version``) exist so tests can inject overrides without
    monkeypatching :data:`os.environ` or :func:`Path.cwd`.
    """
    if not is_router_enabled(env):
        return None
    router = MemoryRouter(
        env=env,
        index_path=index_path,
        current_version=current_version,
    )
    return router.lookup_case(workflow_type, task_type, repo_signal=repo_signal)


def _resolve_default_index_path() -> Path:
    """Resolve :data:`DEFAULT_INDEX_PATH` against the current working directory.

    Wrapped in a function so each :class:`MemoryRouter` construction
    picks up the latest cwd (necessary for tests using
    ``monkeypatch.chdir(tmp_path)``).
    """
    return Path.cwd() / DEFAULT_INDEX_PATH


def _resolve_current_version() -> str:
    """Read :data:`devolaflow.__version__` lazily.

    Imported inside the function (rather than at module top) to avoid
    a hard import cycle: :mod:`devolaflow.__init__` may grow imports
    that in turn import :mod:`devolaflow.memory_router`. The lazy
    import keeps the cache layer dependency-free.
    """
    from devolaflow import __version__  # noqa: PLC0415  (intentional lazy import)

    return __version__
