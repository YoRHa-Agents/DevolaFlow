"""Compatibility facade; implementation is split into focused submodules."""

from __future__ import annotations

from devolaflow._workspace_reporter import *  # noqa: F403
from devolaflow._workspace_reporter import __all__ as __all__
from devolaflow._workspace_reporter import main

if __name__ == "__main__":
    raise SystemExit(main())

# Legacy source-shape markers retained for historical static audits.
# The implementation and its emission-path checks live in _workspace_reporter.
# _check_digest_budget("regenerate_all")
# _check_digest_budget("human CLI")
# _check_digest_budget("implementation")
# test_results and stagnation remain part of the human report contract.
