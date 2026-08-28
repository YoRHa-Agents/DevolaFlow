"""Internal implementation package for workspace reports."""

from __future__ import annotations

from . import common as _common
from . import data as _data
from . import paths as _paths
from . import renderers as _renderers
from . import rules_cli as _rules_cli

_parts = [_common, _renderers, _paths, _data, _rules_cli]
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
