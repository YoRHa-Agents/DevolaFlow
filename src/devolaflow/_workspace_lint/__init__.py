"""Internal implementation package for workspace linting."""

from __future__ import annotations

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
        {
            _name: _value
            for _name, _value in vars(_part).items()
            if not _name.startswith("__") and _name != "_load_dependencies"
        }
    )
for _part in _parts:
    vars(_part).update(_exports)
globals().update(_exports)
__all__ = sorted(_exports)

_common._load_dependencies()
_exports.update(
    {
        _name: _value
        for _name, _value in vars(_common).items()
        if not _name.startswith("__") and _name != "_load_dependencies"
    }
)
for _part in _parts:
    vars(_part).update(_exports)
globals().update(_exports)
__all__ = sorted(_exports)
