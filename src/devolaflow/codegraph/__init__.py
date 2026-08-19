"""Codegraph integration — pre-indexed code knowledge graph wrapper.

DevolaFlow's wrapper around the upstream `colbymchenry/codegraph`
npm-distributed CLI (`@colbymchenry/codegraph@>=0.9.3`). Provides a
subprocess-mediated Python surface that L0/L1/L2 dispatchers + L3 task
agents can invoke for symbol search, context building, impact analysis,
caller traces, and test-affected detection.

Upstream: https://github.com/colbymchenry/codegraph

Per the v12.5.0 PV-03 D-1.1 design, the package mirrors the structure of
:mod:`devolaflow.nines`:

* :mod:`devolaflow.codegraph._cli` — thin subprocess wrapper around the
  ``codegraph`` CLI binary; raises :exc:`CodegraphUnavailableError` when
  the binary is missing / fails / produces unparseable output.
* :mod:`devolaflow.codegraph.researcher` — public researcher API that
  callers (L0/L1/L2 planning, L3 task review, gate scoring) invoke. Each
  helper catches :exc:`CodegraphUnavailableError` and returns an empty
  sentinel result so callers can transparently fall back to
  :mod:`devolaflow`'s built-in Read/Glob/Grep planning paths.
* :mod:`devolaflow.codegraph.markers` — tri-state marker files
  (``.codegraph/.indexing`` / ``.ready`` / ``.failed``) coordinating the
  backgrounded ``codegraph init`` with downstream analyze consumers
  (Track C-3 D-11; suggest-tier probe stays
  :func:`is_codegraph_available`).

Per S-5 (no silent failures): every CLI failure path logs a WARNING
through ``logging.getLogger("devolaflow.codegraph")`` so operators can
audit the degraded-mode invocations. Per S-7 (external resource URLs):
the npm package + GitHub URL are the only canonical references; no
local clone path is hardcoded.

Activation gating: codegraph reuses the existing
``DEVOLAFLOW_AUTO_INSTALL_PLUGINS=1`` env flag per W-20 reuse-first
discipline (the plugin installer + degraded-mode gating share the same
operator activation surface). NO new env flag is introduced.
"""

from devolaflow.codegraph._cli import (
    CodegraphError,
    CodegraphInvocationResult,
    CodegraphUnavailableError,
    is_codegraph_available,
    run_codegraph_cli,
)
from devolaflow.codegraph.markers import (
    MarkerState,
    mark_failed,
    mark_indexing,
    mark_ready,
    read_marker_state,
)
from devolaflow.codegraph.researcher import (
    build_context,
    get_affected_tests,
    get_callers,
    get_impact,
    search_symbols,
)

__all__ = [
    # CLI surface (thin subprocess wrapper)
    "CodegraphError",
    "CodegraphInvocationResult",
    "CodegraphUnavailableError",
    "is_codegraph_available",
    "run_codegraph_cli",
    # Researcher API (preferred)
    "build_context",
    "get_affected_tests",
    "get_callers",
    "get_impact",
    "search_symbols",
    # Backgrounded-init marker protocol (Track C-3)
    "MarkerState",
    "mark_failed",
    "mark_indexing",
    "mark_ready",
    "read_marker_state",
]
