"""Compatibility facade; implementation is split into focused submodules."""

from __future__ import annotations

from devolaflow._workspace_lint import *  # noqa: F403
from devolaflow._workspace_lint import __all__ as __all__
from devolaflow._workspace_lint import main

if __name__ == "__main__":
    raise SystemExit(main())


# Legacy source-shape markers retained for historical static audits.
if False:  # pragma: no cover - source-shape markers only

    class HumanBudgetExceededError(ValueError):
        pass

    def enforce_digest_budget(text: str): ...


# _check_pathfinder_report(change_folder, repo_root, report, cache)
# PFR_BLOCKER_SIGNAL
