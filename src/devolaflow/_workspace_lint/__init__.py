"""Implementation package for the compatibility-preserving split."""

from __future__ import annotations

import sys as _sys
import types as _types

from . import advanced_semantics as _advanced_semantics
from . import api as _api
from . import artifact_semantics as _artifact_semantics
from . import budget as _budget
from . import cli as _cli
from . import common as _common

_parts = [_common, _budget, _artifact_semantics, _advanced_semantics, _api, _cli]
_exports = {}
for _part in _parts:
    _exports.update(
        {_name: _value for _name, _value in vars(_part).items() if not _name.startswith("__")}
    )
for _part in _parts:
    vars(_part).update(_exports)
globals().update(_exports)


class _CompatModule(_types.ModuleType):
    """Forward legacy monkeypatches into every implementation slice."""

    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        if name in _exports:
            for _part in _parts:
                setattr(_part, name, value)


_sys.modules[__name__].__class__ = _CompatModule
__all__ = sorted(_exports)
