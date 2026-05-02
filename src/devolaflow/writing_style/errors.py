"""Exceptions raised by the writing_style package."""

from __future__ import annotations


class StyleError(Exception):
    """Base class for writing-style errors.

    Raised for unknown profiles, malformed catalogues, and any
    invariant violation inside the scorer or transform pipeline.
    Per S-5 (no silent failures): every ``StyleError`` either
    surfaces to the caller or is logged at WARNING by the caller.
    """


__all__ = ["StyleError"]
