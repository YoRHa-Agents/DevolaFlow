"""End-to-end `refresh_all` exercise against the live registry.

Closes D-P-1 from `.local/research/v10.2.0_gap_analysis.md` §3.1:

> `refresh_all` has NEVER been exercised end-to-end against the live
> registry. Every call path in `tests/test_plugin_upgrade.py` mocks
> `subprocess.run` or stubs `upgrade_plugin`.
> `RefreshOutcome(action="upgraded")` never observed against a real
> plugin install.

Contract here is deliberately narrow: **real subprocess fired**, NOT
"upgrade succeeded". A network-absent CI run emits
`RefreshOutcome(action="failed", error=...)` and the test still
passes because the subprocess path was exercised for real. We skip
entirely only when:

1. The `nines` binary is not on PATH (no upgrade target to verify), OR
2. The operator explicitly sets `DEVOLAFLOW_TEST_OFFLINE=1` (CI runs
   without network egress).

CRITICAL: this file does NOT mock `subprocess.run` — that is what
makes it e2e. The 608-line `tests/test_plugin_upgrade.py` is the
mocked-only counterpart and continues to cover the fast inner-loop
cases.

Source: `.local/research/v10.2.0_gap_analysis.md` §3.1 D-P-1 +
`.local/research/v10.2.0_cycle_plan.md` §3 PV-01.
External tool reference (S-7): https://github.com/YoRHa-Agents/DevolaFlow
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from devolaflow.plugins import RefreshOutcome, refresh_all


def _offline_reason() -> str | None:
    """Return a human-readable skip reason when the e2e run cannot proceed.

    Returns ``None`` when the environment appears network-reachable and
    the `nines` plugin is available to upgrade.
    """
    if os.environ.get("DEVOLAFLOW_TEST_OFFLINE", "").strip() == "1":
        return "offline — DEVOLAFLOW_TEST_OFFLINE=1 set"
    if shutil.which("nines") is None:
        return "offline — `nines` binary not on PATH"
    return None


def test_refresh_all_force_only_nines_fires_real_subprocess(
    tmp_path: Path,
) -> None:
    """`refresh_all(force=True, only=["nines"])` exercises the real
    subprocess pipeline end-to-end.

    The test writes `_append_log` output to a `tmp_path` file so the
    run's audit trail is self-contained (does NOT touch the repo's
    canonical `.local/memory/plugin_install.log`). Assertions:

    * exactly 1 outcome returned (matches the `only=["nines"]` filter);
    * the outcome's `plugin_id` equals `"nines"`;
    * the outcome's `action` is one of `{"upgraded", "failed"}` —
      BOTH are legitimate proofs that the subprocess ran. `"failed"`
      on pip timeout / returncode-nonzero is the CI-safe path per
      `tests/test_plugin_upgrade.py::§9` documentation; `"upgraded"`
      is the happy path when pip's registry responds.
    """
    reason = _offline_reason()
    if reason is not None:
        pytest.skip(reason)

    log_path = tmp_path / "plugin_install.log"
    outcomes = refresh_all(force=True, only=["nines"], log_path=log_path)

    assert len(outcomes) == 1, (
        f"`refresh_all(force=True, only=['nines'])` must emit exactly "
        f"one outcome; got {len(outcomes)} — {outcomes!r}"
    )
    outcome = outcomes[0]
    assert isinstance(outcome, RefreshOutcome)
    assert outcome.plugin_id == "nines", (
        f"filter was only=['nines']; got outcome for {outcome.plugin_id!r}"
    )
    assert outcome.action in {"upgraded", "failed"}, (
        f"D-P-1 contract: real subprocess must fire → action ∈ "
        f"{{'upgraded', 'failed'}}; got {outcome.action!r} "
        f"(outcome={outcome!r})"
    )


def test_refresh_all_force_captures_log_audit_trail(
    tmp_path: Path,
) -> None:
    """The e2e path appends a JSONL record to the install log whenever
    a refresh attempt fires (success OR failure). Covers the audit-
    trail side-effect that `tests/test_plugin_upgrade.py` mocks out.

    Asserts that after `refresh_all(force=True, only=["nines"])` runs,
    the log file EXISTS and contains at least one JSON-parseable line
    carrying the `plugin_id: "nines"` field.
    """
    reason = _offline_reason()
    if reason is not None:
        pytest.skip(reason)

    import json

    log_path = tmp_path / "plugin_install.log"
    _ = refresh_all(force=True, only=["nines"], log_path=log_path)

    assert log_path.is_file(), (
        "real subprocess fired → _append_log should have written at "
        "least one JSONL record to the log; file missing"
    )
    lines = [line for line in log_path.read_text().splitlines() if line.strip()]
    assert lines, "log file empty — subprocess either never fired or log write failed"
    nines_events = []
    for line in lines:
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict) and record.get("plugin_id") == "nines":
            nines_events.append(record)
    assert nines_events, (
        f"no `plugin_id: nines` events in log despite refresh_all ran; raw lines = {lines!r}"
    )
