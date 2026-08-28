"""Compatibility facade; implementation is split into focused submodules."""

from __future__ import annotations

from devolaflow._workspace_lint import *  # noqa: F403
from devolaflow._workspace_lint import __all__ as __all__
from devolaflow._workspace_lint import main

if __name__ == "__main__":  # pragma: no cover - CLI entry only
    raise SystemExit(main())
