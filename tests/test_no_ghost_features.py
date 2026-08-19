"""DEPRECATED aggregator — the ghost audit moved to ``tests/ghost/`` (v14.3.0).

Per ``docs/cycle-archive/adr/v15-ADR-001-ghost-audit-decomposition.md`` the
monolithic ghost audit was split by enforcement domain:

* ``tests/ghost/test_rules.py`` — rule-cap, compile-drift, rule-surface lints.
* ``tests/ghost/test_schema.py`` — schema-manifest companion lints.
* ``tests/ghost/test_registries.py`` — A-5 SSOT single-owner, SF-4 reference
  set, MIRRORED_FILES parity.
* ``tests/ghost/test_features_v<MAJ>_<MIN>.py`` — per-cycle W-18 feature
  stanzas (one file per MINOR cycle; new stanzas append to the CURRENT
  cycle file, e.g. ``test_features_v14_3.py`` for v14.3.x).
* ``tests/ghost/test_features_legacy.py`` — pre-v9.1 stanzas (the original
  v7.5.0 audit categories A-K).

This aggregator carries NO test bodies — run the package instead:

    python -m pytest tests/ghost/ -q

It re-exports the shared pins below for one deprecation cycle so external
citations (W-21, ADR-007, C-7, A-5.1) and importers stay valid. Removal
target: v15.0.0, with a coordinated rule recompile (ADR-001 decision 2).
"""

from tests.ghost.test_registries import (
    _SF4_REFERENCE_SET,
    _SSOT_PYTHON_REGISTRIES,
    _SSOT_YAML_REGISTRIES,
)
from tests.ghost.test_rules import _RULE_COUNT_CAP_HARD, _SOUL_FREEZE_COUNT

__all__ = [
    "_RULE_COUNT_CAP_HARD",
    "_SF4_REFERENCE_SET",
    "_SOUL_FREEZE_COUNT",
    "_SSOT_PYTHON_REGISTRIES",
    "_SSOT_YAML_REGISTRIES",
]
