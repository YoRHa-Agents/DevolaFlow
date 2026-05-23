"""Never-installed (first-run) staleness branch pins.

Closes D-P-6 from `.local/research/v10.2.0_gap_analysis.md` §3.1:

> `is_plugin_stale` returns `True` when `read_last_checked` returns
> `None` (never-installed → "stale immediately"). Combined with
> `refresh_all(force=False)` on a fresh clone, this triggers a forced
> upgrade attempt for every plugin even when the operator only wanted
> to refresh ONE.

The behaviour is CORRECT per the docstring contract — a never-installed
plugin MUST be treated as stale so the first dispatch actually
installs it — but v10.1.0 had no regression pin. A future refactor
that inverted the semantics would silently break dispatch-time auto-
install with no CI signal.

This file pins the 3 entry points of the first-run path:

§1 — `is_plugin_stale(log_path=<missing>) → True`
§2 — `is_plugin_stale(log_path=<empty file>) → True`
§3 — `refresh_all(force=False)` on a fresh log directory triggers an
     upgrade attempt for every plugin (each attempt recorded as the
     subprocess either succeeds or fails — monkeypatched to avoid
     network egress; this test is about staleness logic, not network).

Source: `.local/research/v10.2.0_gap_analysis.md` §3.1 D-P-6 +
`.local/research/v10.2.0_cycle_plan.md` §3 PV-01.
External tool reference (S-7): https://github.com/YoRHa-Agents/DevolaFlow
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from devolaflow.plugins import installer as _installer
from devolaflow.plugins import is_plugin_stale, refresh_all


def test_is_plugin_stale_returns_true_when_log_path_is_missing(
    tmp_path: Path,
) -> None:
    """Missing log file → `read_last_checked` returns None → stale."""
    missing_log = tmp_path / "never_created.log"
    assert not missing_log.exists()
    assert (
        is_plugin_stale(
            "nines",
            threshold_hours=24,
            log_path=missing_log,
        )
        is True
    ), (
        "D-P-6 violation: never-installed plugin MUST be treated as "
        "stale so dispatch-time auto-install can fire on the first "
        "invocation. `is_plugin_stale` contract requires True for "
        "missing log."
    )


def test_is_plugin_stale_returns_true_when_log_is_empty(
    tmp_path: Path,
) -> None:
    """Empty log file (no prior events) → stale (never-installed branch)."""
    empty_log = tmp_path / "plugin_install.log"
    empty_log.write_text("")
    assert (
        is_plugin_stale(
            "si-chip",
            threshold_hours=24,
            log_path=empty_log,
        )
        is True
    ), (
        "D-P-6 violation: a plugin with ZERO recorded events is still "
        "never-installed; `is_plugin_stale` must return True."
    )


def test_is_plugin_stale_returns_true_when_log_has_other_plugins_only(
    tmp_path: Path,
) -> None:
    """Log has events for OTHER plugins but none for this plugin → stale.

    Guards against a naive "log exists therefore fresh" reading of the
    stale predicate. Per-plugin staleness means per-plugin log scans.
    """
    import json

    mixed_log = tmp_path / "plugin_install.log"
    ts = datetime.now(UTC).isoformat()
    # nines event exists, but this test asks about si-chip.
    mixed_log.write_text(
        json.dumps(
            {
                "ts": ts,
                "plugin_id": "nines",
                "event": "plugin_installed",
                "details": {"version": "3.3.0"},
            }
        )
        + "\n"
    )
    assert (
        is_plugin_stale(
            "si-chip",
            threshold_hours=24,
            log_path=mixed_log,
        )
        is True
    ), (
        "D-P-6 violation: log scan must filter by plugin_id; a log "
        "populated with OTHER plugins must still report THIS plugin "
        "as stale when it has no own events."
    )


def test_refresh_all_triggers_upgrade_attempt_for_every_plugin_on_fresh_log(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`refresh_all(force=False, log_path=<fresh>)` triggers an upgrade
    attempt for every plugin because every plugin is "never-installed".

    Uses `monkeypatch` to stub `upgrade_plugin` — this test pins the
    staleness-triggered dispatch shape, NOT the network I/O. Each
    registered plugin should hit `upgrade_plugin` exactly once.
    """
    fresh_log = tmp_path / "memory" / "plugin_install.log"
    assert not fresh_log.exists()

    attempt_record: list[str] = []

    def fake_upgrade_plugin(plugin_id: str, **_kwargs: object) -> str:
        attempt_record.append(plugin_id)
        return "99.0.0"

    monkeypatch.setattr(_installer, "upgrade_plugin", fake_upgrade_plugin)

    outcomes = refresh_all(force=False, log_path=fresh_log)

    registered_ids = {"nines", "ui-pro", "rtk", "si-chip", "codegraph"}
    attempted_ids = set(attempt_record)
    missed = registered_ids - attempted_ids
    assert not missed, (
        f"D-P-6 contract: first-run refresh_all must attempt every "
        f"plugin (never-installed → stale); missed = {sorted(missed)!r}"
    )
    actions = {o.action for o in outcomes}
    assert actions == {"upgraded"}, (
        f"all first-run attempts should land as 'upgraded' under the "
        f"monkeypatched upgrade_plugin; got {actions!r}"
    )
    assert {o.plugin_id for o in outcomes} == registered_ids
