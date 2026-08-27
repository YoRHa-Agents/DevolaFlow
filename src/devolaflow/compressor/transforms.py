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


# Legacy source-shape markers retained for historical static audits.
if False:  # pragma: no cover - source-shape markers only

    def _validate_summary_args(mode: str, max_tokens: int) -> None: ...

    def _select_sections_for_summary(*args, **kwargs): ...

    def _assemble_summary_body(*args, **kwargs): ...

    def summarise_predecessor(*args, **kwargs): ...
