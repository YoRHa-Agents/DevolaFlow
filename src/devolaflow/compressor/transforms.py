"""Compatibility facade; implementation is split into focused submodules."""

from __future__ import annotations

from devolaflow._compressor_transforms import *  # noqa: F403
from devolaflow._compressor_transforms import __all__ as __all__
from devolaflow._compressor_transforms import validation as _validation


def compress_message(*args, **kwargs):
    """Compatibility wrapper for the moved lean-message compressor."""
    return _validation.compress_message(*args, **kwargs)


def validate_lean_format(*args, **kwargs):
    """Compatibility wrapper for the moved lean-format validator."""
    return _validation.validate_lean_format(*args, **kwargs)
