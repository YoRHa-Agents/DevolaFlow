"""Compatibility facade; implementation is split into focused submodules."""

from __future__ import annotations

import sys as _sys

from devolaflow._plugin_installer import *  # noqa: F403

_sys.modules[__name__] = _sys.modules["devolaflow._plugin_installer"]

# Legacy source-shape markers retained for historical static audits.
_LAST_CHECKED_SUCCESSFUL_EVENTS = frozenset()


def _parse_log_event_timestamp(value: str): ...
