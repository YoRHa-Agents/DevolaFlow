"""v17.0.0 R5 (G17-B6 / D-R5-1) — capacity/threshold dark-config contract.

Pins the :mod:`devolaflow.harness.capacity` SSOT reader (A-5 owner of
``context_profiles.yaml#meta.capacity``) plus the consumer wiring:

* config ABSENT → all hardcoded defaults, per-field ``source == "default"``,
  byte-identical to the pre-R5 literals (the shipped YAML stays dark);
* config PRESENT → values + per-field ``source == "config"``;
* config INVALID → loud :class:`CapacityConfigError` (S-5, never clamped);
* consumers (``round_engine`` default + stop-guard windows,
  ``dispatch_executor`` default, ``telemetry`` bound + ledger field) follow
  the configured values while their pinned literal fallbacks stay true.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml

import devolaflow.task_adaptive_selector as selector
from devolaflow.agent_workspace.dispatch_executor import (
    DEFAULT_MAX_CONCURRENCY,
    AsyncDispatchExecutor,
)
from devolaflow.agent_workspace.round_engine import (
    ITEM_UNSUCCESSFUL_THREE_ROUNDS,
    NET_STAGNATION_TWO_ROUNDS,
    RoundEngineError,
    RoundProgress,
    evaluate_stop_guard,
    select_round,
)
from devolaflow.harness.capacity import (
    CAPACITY_TARGET_RANGES,
    CapacityConfigError,
    CapacityProfile,
    capacity_profile,
)
from devolaflow.harness.telemetry import build_dispatch_record


@dataclass(frozen=True)
class Item:
    item_id: str
    priority: str = "P1"
    checked: bool = False
    depends: tuple[str, ...] = ()
    reverted: bool = False


@dataclass(frozen=True)
class Checklist:
    items: tuple[Item, ...]


@dataclass(frozen=True)
class Stage:
    priority_changes: tuple = ()


def _write_profiles(path: Path, meta: dict) -> Path:
    path.write_text(yaml.safe_dump({"meta": meta}), encoding="utf-8")
    return path


def _configured_profiles(tmp_path: Path, capacity: dict) -> Path:
    return _write_profiles(tmp_path / "profiles.yaml", {"capacity": capacity})


def test_capacity_profile_defaults_when_dark(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Absent key → hardcoded defaults; unreadable file → WARNING + defaults.

    Also pins that the SHIPPED context_profiles.yaml declares no
    ``meta.capacity`` block (the extension point ships dark), so default
    resolution is byte-identical to the pre-R5 literals 5/4/2/3.
    """
    expected = CapacityProfile()
    assert (
        expected.round_capacity,
        expected.max_concurrency,
        expected.stagnation_rounds,
        expected.unsuccessful_item_rounds,
    ) == (5, 4, 2, 3)
    assert expected.max_concurrency == DEFAULT_MAX_CONCURRENCY

    # Shipped config ships dark → defaults.
    shipped = capacity_profile()
    assert shipped == expected
    assert shipped.source == "default"
    assert set(shipped.sources.values()) == {"default"}

    # Explicit meta without a capacity block → defaults.
    absent = _write_profiles(tmp_path / "absent.yaml", {"budget_hard_cap_tokens": 8000})
    assert capacity_profile(absent) == expected

    # Unreadable profiles file → WARNING + defaults (tiers.py precedent).
    with caplog.at_level("WARNING", logger="devolaflow.harness.capacity"):
        fallback = capacity_profile(tmp_path / "missing.yaml")
    assert fallback == expected
    assert "capacity profile config load failed" in caplog.text


def test_capacity_profile_reads_config_with_per_field_sources(tmp_path: Path) -> None:
    """Declared fields resolve with source "config"; omitted stay "default"."""
    full = capacity_profile(
        _configured_profiles(
            tmp_path,
            {
                "round_capacity": 3,
                "max_concurrency": 8,
                "stop_guard": {"stagnation_rounds": 4, "unsuccessful_item_rounds": 6},
            },
        )
    )
    assert (
        full.round_capacity,
        full.max_concurrency,
        full.stagnation_rounds,
        full.unsuccessful_item_rounds,
    ) == (3, 8, 4, 6)
    assert set(full.sources.values()) == {"config"}
    assert full.source == "config"

    partial = capacity_profile(_configured_profiles(tmp_path, {"round_capacity": 2}))
    assert partial.round_capacity == 2
    assert (
        partial.max_concurrency,
        partial.stagnation_rounds,
        partial.unsuccessful_item_rounds,
    ) == (4, 2, 3)
    assert partial.sources["round_capacity"] == "config"
    assert partial.sources["max_concurrency"] == "default"
    assert partial.source == "config"


@pytest.mark.parametrize(
    "capacity_block",
    [
        {"round_capacity": 0},
        {"round_capacity": 6},
        {"round_capacity": True},
        {"round_capacity": "5"},
        {"max_concurrency": 9},
        {"max_concurrency": 0},
        {"stop_guard": {"stagnation_rounds": 6}},
        {"stop_guard": {"unsuccessful_item_rounds": 0}},
        {"stop_guard": {"stagnation_windows": 2}},
        {"stop_guard": "aggressive"},
        {"round_capcity": 5},
        "not-a-mapping",
    ],
)
def test_capacity_profile_rejects_invalid_config(
    tmp_path: Path,
    capacity_block: object,
) -> None:
    """Present-but-invalid config raises loudly (S-5) — never clamped."""
    configured = _configured_profiles(tmp_path, capacity_block)  # type: ignore[arg-type]
    with pytest.raises(CapacityConfigError):
        capacity_profile(configured)


def test_round_engine_defaults_follow_capacity_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Omitted capacity/window args resolve through meta.capacity.

    The 1..5 stage-schema hard cap is unchanged: an explicit capacity of 5
    stays valid even when the configured DEFAULT is smaller, and explicit
    window arguments override the configured widths.
    """
    configured = _configured_profiles(
        tmp_path,
        {
            "round_capacity": 2,
            "stop_guard": {"stagnation_rounds": 1, "unsuccessful_item_rounds": 2},
        },
    )
    monkeypatch.setattr(selector, "PROFILES_PATH", configured)

    checklist = Checklist(tuple(Item(f"C-{index}", priority="P0") for index in range(4)))
    assert len(select_round(checklist, Stage()).selected) == 2
    assert len(select_round(checklist, Stage(), capacity=5).selected) == 4

    stalled = (RoundProgress(round_num=1, picked_item_ids=("C-0",)),)
    configured_guard = evaluate_stop_guard(
        stalled,
        current_round=1,
        max_rounds=9,
        open_item_ids=("C-0",),
    )
    assert NET_STAGNATION_TWO_ROUNDS in configured_guard.reasons

    two_rounds = (
        RoundProgress(round_num=1, picked_item_ids=("C-0",), checked_item_ids=("x",)),
        RoundProgress(round_num=2, picked_item_ids=("C-0",), checked_item_ids=("x",)),
    )
    assert ITEM_UNSUCCESSFUL_THREE_ROUNDS in (
        evaluate_stop_guard(
            two_rounds,
            current_round=2,
            max_rounds=9,
            open_item_ids=("C-0",),
        ).reasons
    )

    # Explicit window arguments win over the configured defaults.
    explicit = evaluate_stop_guard(
        stalled,
        current_round=1,
        max_rounds=9,
        open_item_ids=("C-0",),
        stagnation_rounds=2,
        unsuccessful_item_rounds=3,
    )
    assert explicit.reasons == ()
    with pytest.raises(RoundEngineError) as exc_info:
        evaluate_stop_guard(
            stalled,
            current_round=1,
            max_rounds=9,
            open_item_ids=(),
            stagnation_rounds=0,
        )
    assert exc_info.value.code == "INVALID_STOP_GUARD_WINDOW"


def test_dispatch_executor_default_follows_capacity_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Constructor default follows meta.capacity.max_concurrency (1..8)."""
    configured = _configured_profiles(tmp_path, {"max_concurrency": 6})
    monkeypatch.setattr(selector, "PROFILES_PATH", configured)
    assert AsyncDispatchExecutor().max_concurrency == 6
    # Explicit argument wins over the configured default.
    assert AsyncDispatchExecutor(max_concurrency=2).max_concurrency == 2

    invalid = _configured_profiles(tmp_path, {"max_concurrency": 99})
    monkeypatch.setattr(selector, "PROFILES_PATH", invalid)
    with pytest.raises(CapacityConfigError):
        AsyncDispatchExecutor()


def test_telemetry_capacity_field_and_bound_follow_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The ledger field carries the resolved profile; the slice bound mirrors it.

    An invalid meta.capacity block never blocks record building: telemetry
    degrades to the hardcoded defaults with a WARNING (S-5 nonblocking).
    """

    def payload(checklist_count: int) -> dict:
        return {
            "hdr": {"id": "dispatch-capacity-001"},
            "layer": "L2",
            "change_context": {
                "checklist_items": [
                    {"id": f"C-{index}", "assert": "a", "verify": "v"}
                    for index in range(checklist_count)
                ],
            },
        }

    configured = _configured_profiles(tmp_path, {"round_capacity": 3})
    monkeypatch.setattr(selector, "PROFILES_PATH", configured)
    record = build_dispatch_record(payload(3), change_id="capacity-config")
    assert record["capacity_profile"] == {
        "round_capacity": 3,
        "max_concurrency": 4,
        "source": "config",
    }
    assert list(record)[-2:] == ["capacity_profile", "agents_md_tokens"]
    with pytest.raises(ValueError, match="1 through 3 items"):
        build_dispatch_record(payload(4), change_id="capacity-config")

    invalid = _configured_profiles(tmp_path, {"round_capacity": 99})
    monkeypatch.setattr(selector, "PROFILES_PATH", invalid)
    with caplog.at_level("WARNING", logger="devolaflow.harness.telemetry"):
        degraded = build_dispatch_record(payload(4), change_id="capacity-config")
    assert degraded["capacity_profile"] == {
        "round_capacity": 5,
        "max_concurrency": 4,
        "source": "default",
    }
    assert "capacity profile resolution failed" in caplog.text


def test_capacity_target_ranges_match_reader_bounds() -> None:
    """The proposal-facing range table is the reader's own bound set (A-5)."""
    assert dict(CAPACITY_TARGET_RANGES) == {
        "meta.capacity.round_capacity": (1, 5),
        "meta.capacity.max_concurrency": (1, 8),
        "meta.capacity.stop_guard.stagnation_rounds": (1, 5),
        "meta.capacity.stop_guard.unsuccessful_item_rounds": (1, 6),
    }
