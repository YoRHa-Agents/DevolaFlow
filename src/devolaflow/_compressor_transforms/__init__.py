"""Internal implementation package for compressor transforms."""

from __future__ import annotations

from . import common as _common
from . import compact as _compact
from . import dedup as _dedup
from . import pipeline as _pipeline
from . import retrieval as _retrieval
from . import summary as _summary
from . import tools as _tools
from . import validation as _validation

_parts = [_common, _validation, _tools, _retrieval, _summary, _compact, _pipeline, _dedup]
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
