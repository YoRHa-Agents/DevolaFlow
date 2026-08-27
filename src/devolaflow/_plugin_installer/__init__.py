"""Implementation package for the compatibility-preserving split."""

from __future__ import annotations

import sys as _sys
import types as _types

from . import backends as _backends
from . import common as _common
from . import freshness as _freshness
from . import lifecycle as _lifecycle
from . import refresh as _refresh
from . import specs as _specs

_parts = [_common, _specs, _backends, _lifecycle, _freshness, _refresh]
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
