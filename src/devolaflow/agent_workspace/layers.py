"""Single source of truth for v16 agent-layer tokens.

Layer tokens are provenance-sensitive during the v16 compatibility window:
``L1`` means Stage in legacy schema v1 but Wave in the current schema, while
``L2`` means Wave in v1 but Task in the current schema.  Callers therefore
MUST supply the schema version instead of guessing from the token alone.
"""

from __future__ import annotations

import warnings
from typing import Final

__all__ = [
    "CURRENT_HANDOFF_SCHEMA_VERSION",
    "CURRENT_HDR_LAYER_TOKENS",
    "CURRENT_LAYER_ROLES",
    "CURRENT_LAYER_TOKENS",
    "LEGACY_HANDOFF_SCHEMA_VERSION",
    "LEGACY_V1_HDR_LAYER_MAP",
    "LEGACY_V1_LAYER_MAP",
    "LegacyLayerWarning",
    "normalize_hdr_layer",
    "normalize_layer",
]


LEGACY_HANDOFF_SCHEMA_VERSION: Final[int] = 1
CURRENT_HANDOFF_SCHEMA_VERSION: Final[int] = 2

CURRENT_LAYER_TOKENS: Final[tuple[str, ...]] = ("L0", "L1", "L2")
CURRENT_LAYER_ROLES: Final[dict[str, str]] = {
    "L0": "Project",
    "L1": "Wave",
    "L2": "Task",
}

# Explicitly named v1: the same L1/L2 spellings have different v16 meanings.
LEGACY_V1_LAYER_MAP: Final[dict[str, str]] = {
    "L0": "L0",
    "L1": "L0",
    "L2": "L1",
    "L3": "L2",
}

# ``hdr.layer`` identifies a dispatcher, so Task is not an emission value.
CURRENT_HDR_LAYER_TOKENS: Final[tuple[str, ...]] = ("project", "wave")
LEGACY_V1_HDR_LAYER_MAP: Final[dict[str, str]] = {
    "project": "project",
    "stage": "project",
    "wave": "wave",
}


class LegacyLayerWarning(UserWarning):
    """Warning emitted when a schema-v1 layer token is normalized."""


_warned_legacy_tokens: set[tuple[str, str]] = set()


def _validate_context(context: str) -> None:
    if not isinstance(context, str) or not context.strip():
        raise ValueError("layer normalization context must be a non-empty string")


def _warn_legacy_once(*, context: str, token: str, normalized: str) -> None:
    """Warn once for each caller context/token pair (S-5)."""

    warning_key = (context, token)
    if warning_key in _warned_legacy_tokens:
        return
    _warned_legacy_tokens.add(warning_key)
    warnings.warn(
        (
            f"{context}: legacy schema-v1 layer token {token!r} normalized "
            f"to v16 token {normalized!r}; emit v16 tokens for new artifacts"
        ),
        LegacyLayerWarning,
        stacklevel=3,
    )


def normalize_layer(token: str, *, schema_version: int, context: str) -> str:
    """Return the current ``L0``/``L1``/``L2`` token for explicit provenance.

    ``schema_version=1`` applies :data:`LEGACY_V1_LAYER_MAP` and warns once
    per ``(context, token)``.  ``schema_version=2`` accepts only current
    tokens.  Unknown versions and tokens raise :class:`ValueError`.
    """

    _validate_context(context)
    if schema_version == LEGACY_HANDOFF_SCHEMA_VERSION:
        try:
            normalized = LEGACY_V1_LAYER_MAP[token]
        except (KeyError, TypeError) as exc:
            raise ValueError(f"unknown legacy schema-v1 layer token: {token!r}") from exc
        _warn_legacy_once(context=context, token=token, normalized=normalized)
        return normalized
    if schema_version == CURRENT_HANDOFF_SCHEMA_VERSION:
        if token not in CURRENT_LAYER_TOKENS:
            raise ValueError(
                f"unknown current layer token {token!r}; expected one of {CURRENT_LAYER_TOKENS}"
            )
        return token
    raise ValueError(
        f"unknown layer schema version {schema_version!r}; "
        f"expected {LEGACY_HANDOFF_SCHEMA_VERSION} or {CURRENT_HANDOFF_SCHEMA_VERSION}"
    )


def normalize_hdr_layer(token: str, *, schema_version: int, context: str) -> str:
    """Normalize a lean ``hdr.layer`` value with explicit schema provenance."""

    _validate_context(context)
    if schema_version == LEGACY_HANDOFF_SCHEMA_VERSION:
        try:
            normalized = LEGACY_V1_HDR_LAYER_MAP[token]
        except (KeyError, TypeError) as exc:
            raise ValueError(f"unknown legacy schema-v1 hdr.layer token: {token!r}") from exc
        _warn_legacy_once(context=context, token=token, normalized=normalized)
        return normalized
    if schema_version == CURRENT_HANDOFF_SCHEMA_VERSION:
        if token not in CURRENT_HDR_LAYER_TOKENS:
            raise ValueError(
                f"unknown current hdr.layer token {token!r}; "
                f"expected one of {CURRENT_HDR_LAYER_TOKENS}"
            )
        return token
    raise ValueError(
        f"unknown hdr.layer schema version {schema_version!r}; "
        f"expected {LEGACY_HANDOFF_SCHEMA_VERSION} or {CURRENT_HANDOFF_SCHEMA_VERSION}"
    )
