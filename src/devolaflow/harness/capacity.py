"""Capacity/threshold profile — SSOT reader for the ``meta.capacity`` dark config.

v17.0.0 R5 (G17-B6 / D-R5-1) — the round-capacity, executor-concurrency,
and stop-guard window numerals were previously scattered as hardcoded
literals across four consumer modules (``agent_workspace/round_engine.py``,
``agent_workspace/dispatch_executor.py``, ``agent_workspace/preflight_runtime.py``,
``harness/telemetry.py``). This module is the single owner (A-5) of their
configurable defaults: consumers import :func:`capacity_profile` and never
re-define the registration data locally. The per-module literals they keep
(``_CAPACITY_MAX``, ``DEFAULT_MAX_CONCURRENCY``, …) remain as pinned
FALLBACK defaults — they are byte-equal to the dataclass defaults below and
stay the contract whenever the config key is absent.

Dark-config pattern (mirrors ``harness/tiers.py::_advisory_fold_tiers``,
the v17 R3 precedent): the shipped ``context_profiles.yaml`` declares NO
``meta.capacity`` block, so behaviour is byte-identical to the pre-R5
hardcoded values. Operators opt in by declaring:

.. code-block:: yaml

    meta:
      capacity:
        round_capacity: 5        # 1..5 (stage schema hard cap unchanged)
        max_concurrency: 4       # 1..8
        stop_guard:
          stagnation_rounds: 2   # 1..5
          unsuccessful_item_rounds: 3  # 1..6

Failure semantics (S-5):

* Key ABSENT → all defaults, ``source == "default"`` per field
  (byte-identical, zero behaviour change).
* Profiles file unreadable → WARNING + all defaults (mirrors the tiers
  precedent — a broken install must not crash round selection).
* Key PRESENT but malformed / out of range / carrying unknown sub-keys →
  :class:`CapacityConfigError` raised LOUDLY. Values are never silently
  clamped.

The proposal loop (``harness/proposal.py``) imports
:data:`CAPACITY_TARGET_RANGES` so the ``meta.capacity.*`` AUTO_CONFIG
allowlist validates against the same ranges this reader enforces (one
range table, one owner). Note the apply path patches EXISTING config keys
only — an operator must declare the ``meta.capacity`` block before an
approved capacity proposal can be applied.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Final

logger = logging.getLogger(__name__)

__all__ = [
    "CAPACITY_TARGET_RANGES",
    "CapacityConfigError",
    "CapacityProfile",
    "capacity_profile",
]


class CapacityConfigError(ValueError):
    """A declared ``meta.capacity`` block is malformed or out of range."""


# One row per configurable field:
# (dataclass field, meta.capacity-relative key path, default, lo, hi).
_FIELD_SPECS: Final[tuple[tuple[str, str, int, int, int], ...]] = (
    ("round_capacity", "round_capacity", 5, 1, 5),
    ("max_concurrency", "max_concurrency", 4, 1, 8),
    ("stagnation_rounds", "stop_guard.stagnation_rounds", 2, 1, 5),
    ("unsuccessful_item_rounds", "stop_guard.unsuccessful_item_rounds", 3, 1, 6),
)

# Proposal-facing range table keyed by full config path. Imported by
# ``harness/proposal.py`` for the AUTO_CONFIG allowlist validation so the
# reader and the proposal loop can never disagree on a bound (A-5).
CAPACITY_TARGET_RANGES: Final[Mapping[str, tuple[int, int]]] = MappingProxyType(
    {f"meta.capacity.{key}": (lo, hi) for _, key, _, lo, hi in _FIELD_SPECS}
)

_ALLOWED_TOP_KEYS: Final[frozenset[str]] = frozenset(
    {"round_capacity", "max_concurrency", "stop_guard"}
)
_ALLOWED_STOP_GUARD_KEYS: Final[frozenset[str]] = frozenset(
    {"stagnation_rounds", "unsuccessful_item_rounds"}
)

_DEFAULT_SOURCES: Final[Mapping[str, str]] = MappingProxyType(
    {name: "default" for name, _, _, _, _ in _FIELD_SPECS}
)


def _default_sources() -> Mapping[str, str]:
    """Return a fresh immutable provenance mapping for default profiles."""

    return MappingProxyType(dict(_DEFAULT_SOURCES))


@dataclass(frozen=True)
class CapacityProfile:
    """Resolved capacity/threshold defaults with per-field provenance.

    ``sources`` maps every field name to ``"config"`` (value came from a
    declared ``meta.capacity`` key) or ``"default"`` (key absent — the
    hardcoded pre-R5 literal). :attr:`source` is the aggregate view the
    telemetry ledger records: ``"config"`` when ANY field came from config.
    """

    round_capacity: int = 5
    max_concurrency: int = 4
    stagnation_rounds: int = 2
    unsuccessful_item_rounds: int = 3
    sources: Mapping[str, str] = field(default_factory=_default_sources)

    @property
    def source(self) -> str:
        """Aggregate provenance: ``"config"`` if any field came from config."""

        return "config" if "config" in self.sources.values() else "default"


def _lookup(block: Mapping[str, object], key_path: str) -> tuple[bool, object]:
    """Return ``(present, value)`` for a dotted key path inside the block."""

    cursor: object = block
    parts = key_path.split(".")
    for part in parts:
        if not isinstance(cursor, Mapping) or part not in cursor:
            return False, None
        cursor = cursor[part]
    return True, cursor


def _reject_unknown_keys(block: Mapping[str, object]) -> None:
    unknown = sorted(set(map(str, block)) - _ALLOWED_TOP_KEYS)
    if unknown:
        raise CapacityConfigError(
            f"meta.capacity contains unknown key(s) {unknown}; "
            f"allowed keys are {sorted(_ALLOWED_TOP_KEYS)}"
        )
    stop_guard = block.get("stop_guard")
    if stop_guard is None:
        return
    if not isinstance(stop_guard, Mapping):
        raise CapacityConfigError(f"meta.capacity.stop_guard must be a mapping; got {stop_guard!r}")
    unknown = sorted(set(map(str, stop_guard)) - _ALLOWED_STOP_GUARD_KEYS)
    if unknown:
        raise CapacityConfigError(
            f"meta.capacity.stop_guard contains unknown key(s) {unknown}; "
            f"allowed keys are {sorted(_ALLOWED_STOP_GUARD_KEYS)}"
        )


def capacity_profile(profiles_path: Path | None = None) -> CapacityProfile:
    """Resolve the capacity profile from ``context_profiles.yaml#meta.capacity``.

    Absent key → all dataclass defaults with per-field ``source ==
    "default"`` (canonical absence-as-default; the extension point ships
    dark). A present-but-invalid block raises :class:`CapacityConfigError`
    loudly per S-5 — values are never clamped. A profiles-load failure
    falls back to the defaults with a WARNING (tiers.py precedent). The
    YAML read is served by the selector's mtime-keyed LRU cache
    (``load_profiles``, imported at call boundary to avoid the harness ↔
    selector module-initialization cycle), so warm calls cost dictionary
    lookups plus one ``stat``.
    """

    from devolaflow.task_adaptive_selector import load_profiles

    try:
        config = load_profiles(profiles_path)
    except Exception as exc:  # noqa: BLE001 - unreadable profiles must not crash consumers
        logger.warning(
            "capacity profile config load failed (%s); falling back to defaults",
            exc,
        )
        return CapacityProfile()

    meta = config.get("meta") if isinstance(config, dict) else None
    block = meta.get("capacity") if isinstance(meta, Mapping) else None
    if block is None:
        return CapacityProfile()
    if not isinstance(block, Mapping):
        raise CapacityConfigError(f"meta.capacity must be a mapping; got {block!r}")
    _reject_unknown_keys(block)

    values: dict[str, int] = {}
    sources: dict[str, str] = {}
    for name, key_path, default, lo, hi in _FIELD_SPECS:
        present, value = _lookup(block, key_path)
        if not present:
            values[name] = default
            sources[name] = "default"
            continue
        if type(value) is not int or not lo <= value <= hi:
            raise CapacityConfigError(
                f"meta.capacity.{key_path} must be an integer in [{lo}, {hi}]; got {value!r}"
            )
        values[name] = value
        sources[name] = "config"
    return CapacityProfile(sources=MappingProxyType(sources), **values)
