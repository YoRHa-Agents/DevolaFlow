"""Plugin runtime exceptions for the v8.2.1 auto-install surface.

Design ref: `.local/research/v8.3.0_design.md` §6.5 — no silent failures (S-5).
Every install/verify error raises loudly with a descriptive message. Callers
(workflow precondition stages) escalate upward per P4 bounded retry.
"""

from __future__ import annotations


class PluginRuntimeError(Exception):
    """Base class for all v8.2.1 plugin runtime errors.

    Kept distinct from the older ``devolaflow.plugins.registry.PluginRegistry``
    surface so existing consumers are unaffected. Every subclass MUST carry a
    human-readable message plus (optionally) structured ``details`` for
    downstream logging per S-5.
    """

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        """Initialize with a loud message and optional structured ``details``."""
        super().__init__(message)
        self.details: dict = details or {}


class PluginNotFoundError(PluginRuntimeError):
    """Raised when ``plugin_id`` is not present in ``runtime-plugins.yaml``."""


class PluginInstallError(PluginRuntimeError):
    """Raised when an install attempt fails (subprocess error, network, sha, timeout).

    See `.local/research/v8.3.0_design.md` §6.5 rows 5, 7, 8.
    """


class PluginVersionMismatch(PluginRuntimeError):  # noqa: N818 — public API name fixed by design.md §6
    """Raised when installed version < ``min_version`` (pre- or post-install).

    See `.local/research/v8.3.0_design.md` §6.5 rows 3, 6.

    Note: Class name does NOT carry the ``Error`` suffix because the v8.2.1
    patch plan (AC-1) pins this exact public identifier. Suppressed ruff N818
    locally rather than globally to preserve the warning for future classes.
    """


class PluginBackendUnsupported(PluginRuntimeError):  # noqa: N818 — public API name fixed by design.md §6
    """Raised when a plugin's ``backend`` field is not one of {pip, npm_then_init}.

    Added in v8.2.1 to protect against future backend rows slipping into
    ``runtime-plugins.yaml`` without accompanying installer logic. See note on
    :class:`PluginVersionMismatch` regarding the missing ``Error`` suffix.
    """


__all__ = [
    "PluginBackendUnsupported",
    "PluginInstallError",
    "PluginNotFoundError",
    "PluginRuntimeError",
    "PluginVersionMismatch",
]
