"""Fast-path memory router package — closes M-001 from v8.4.0 SI-1 gap analysis (PV-03).

Public surface:

* :class:`MemoryRouter` — main router class with lazy index load + in-process cache
* :class:`MemoryCase` — frozen dataclass mirroring one ``index.yaml`` row
* :class:`MemoryCacheError` — raised by :func:`build_case_from_dict` on schema breaks
* :class:`MemoryRouterError` — raised by :meth:`MemoryRouter.lookup_case_strict`
* :func:`lookup_case` — module-level convenience wrapper
* :func:`is_router_enabled` — pure env-flag read (R5 strict hot path)
* :data:`ENV_FLAG` — activation env-var name (``"DEVOLAFLOW_MEMORY_ROUTER"``)
* :data:`DEFAULT_INDEX_PATH` — repo-relative default index path

Activation (default OFF — R5 strict):

* Set ``DEVOLAFLOW_MEMORY_ROUTER=1`` to enable lookups against
  ``.local/memory/cases/index.yaml``.
* When the env-flag is unset, :func:`lookup_case` returns ``None``
  immediately — no file IO, no parsing — so all v8.3.2 baseline
  tests pass byte-identical (per cycle plan §5 I-7).

Cache invalidation (per cycle plan §6 R3 — cache-poisoning mitigation):

* Per-route TTL via :func:`is_ttl_expired`
* Per-route version stamp via :func:`is_version_stale` (route invalidates
  when the recipe's stamp differs from :data:`devolaflow.__version__`)

Schema (canonical source-of-truth): ``schemas/memory-case.yaml``.
Operator doc (gitignored): ``.local/memory/cases/README.md``.

External canonical URL (per S-7): https://github.com/YoRHa-Agents/DevolaFlow
"""

from __future__ import annotations

from devolaflow.memory_router.cache import (
    DEFAULT_TTL_DAYS,
    MAX_TTL_DAYS,
    MIN_TTL_DAYS,
    MemoryCacheError,
    MemoryCase,
    build_case_from_dict,
    is_ttl_expired,
    is_version_stale,
    today_iso,
)
from devolaflow.memory_router.router import (
    DEFAULT_INDEX_PATH,
    ENV_FLAG,
    MemoryRouter,
    MemoryRouterError,
    is_router_enabled,
    lookup_case,
)

__all__ = [
    "DEFAULT_INDEX_PATH",
    "DEFAULT_TTL_DAYS",
    "ENV_FLAG",
    "MAX_TTL_DAYS",
    "MIN_TTL_DAYS",
    "MemoryCacheError",
    "MemoryCase",
    "MemoryRouter",
    "MemoryRouterError",
    "build_case_from_dict",
    "is_router_enabled",
    "is_ttl_expired",
    "is_version_stale",
    "lookup_case",
    "today_iso",
]
