"""Tests for v9.4.0 PV-04 plugin schema v3 + upgrade_cmd + daily-refresh CLI.

Closes D-P-4 (MAJOR — daily-upgrade surface) + D-P-5 (MAJOR — schema v3
bump for upgrade_cmd) + D-P-8 (MINOR — registry refresh UX) from
`.local/research/v9.4.0_gap_analysis.md` §3.2.

Test surface:

§1 — Schema v3 parses cleanly + canonical registry has upgrade_cmd
§2 — Schema v1/v2 entries still load (backward compat — gap §6 AC-4)
§3 — `read_last_checked` reads JSONL audit trail correctly
§4 — `is_plugin_stale` honours threshold + treats unseen as stale
§5 — `upgrade_plugin` runs the right command + writes plugin_upgraded log entry
§6 — `refresh_all` iterates registry + skips fresh + upgrades stale
§7 — `refresh_all --force` upgrades all regardless of staleness
§8 — `refresh_all --plugin <id>` restricts to a single plugin
§9 — Network failure becomes RefreshOutcome(action="failed") (CI-safe)
§10 — `list_plugins` returns inspection rows with last_checked
"""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from devolaflow.plugins import (
    RefreshOutcome,
    is_plugin_stale,
    list_plugins,
    load_registry,
    read_last_checked,
    refresh_all,
    upgrade_plugin,
)
from devolaflow.plugins.exceptions import PluginInstallError
from devolaflow.plugins.installer import (
    _DEFAULT_UPGRADE_CHECK_FREQUENCY_HOURS,
    _SUPPORTED_SCHEMA_VERSIONS,
)

# ---------------------------------------------------------------------------
# §1 — Schema v3 + canonical registry shape
# ---------------------------------------------------------------------------


class TestSchemaV3:
    """Pin the schema v3 contract: upgrade_cmd field + 24h default."""

    def test_supported_schema_versions_includes_v3(self) -> None:
        assert frozenset({1, 2, 3}) == _SUPPORTED_SCHEMA_VERSIONS, (
            f"v9.4.0 PV-04 must include schema v3 in the supported set; "
            f"got {_SUPPORTED_SCHEMA_VERSIONS!r}"
        )

    def test_default_upgrade_frequency_is_24h(self) -> None:
        assert _DEFAULT_UPGRADE_CHECK_FREQUENCY_HOURS == 24, (
            "Daily upgrade cadence per gap analysis §3.2 D-P-5"
        )

    def test_canonical_registry_is_v3(self) -> None:
        registry = load_registry()
        assert registry["schema_version"] == 3, (
            f"runtime-plugins.yaml schema_version must be 3 in v9.4.0 PV-04; "
            f"got {registry['schema_version']!r}"
        )

    def test_canonical_registry_carries_upgrade_cmd_per_plugin(self) -> None:
        registry = load_registry()
        for entry in registry["plugins"]:
            assert "upgrade_cmd" in entry, (
                f"v9.4.0 PV-04 contract: every plugin in v3 registry should "
                f"carry an upgrade_cmd. Plugin {entry.get('id')!r} missing"
            )

    def test_canonical_defaults_carry_frequency(self) -> None:
        registry = load_registry()
        defaults = registry.get("defaults", {})
        assert defaults.get("upgrade_check_frequency_hours") == 24


# ---------------------------------------------------------------------------
# §2 — Backward compatibility: v1 + v2 entries still load
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_registry_v2(tmp_path: Path) -> Path:
    """Write a minimal schema_version=2 registry that DOES NOT carry upgrade_cmd."""
    registry_yaml = """\
schema_version: 2
last_updated: "2026-04-23"
plugins:
  - id: legacy-tool
    backend: pip
    package: legacy-tool
    install_cmd: "pip install --upgrade legacy-tool"
    version_check_cmd: "legacy-tool --version"
    min_version: "1.0.0"
    canonical_url: "https://example.com/legacy"
    invoked_by_workflows: []
defaults:
  auto_install: true
  prefer_local_fallback: true
  network_timeout_seconds: 90
  install_log_path: ".local/memory/plugin_install.log"
"""
    path = tmp_path / "runtime-plugins-v2.yaml"
    path.write_text(registry_yaml, encoding="utf-8")
    return path


@pytest.fixture
def tmp_registry_v1(tmp_path: Path) -> Path:
    """Write a minimal schema_version=1 registry."""
    registry_yaml = """\
schema_version: 1
last_updated: "2026-01-01"
plugins:
  - id: ancient-tool
    backend: pip
    package: ancient-tool
    install_cmd: "pip install ancient-tool"
    version_check_cmd: "ancient-tool --version"
    min_version: "0.1.0"
    canonical_url: "https://example.com/ancient"
defaults:
  auto_install: true
"""
    path = tmp_path / "runtime-plugins-v1.yaml"
    path.write_text(registry_yaml, encoding="utf-8")
    return path


class TestBackwardCompatibility:
    """v1 and v2 entries must still load; missing upgrade_cmd → falls back to install_cmd."""

    def test_backward_compat_v2_entries_load(self, tmp_registry_v2: Path) -> None:
        registry = load_registry(tmp_registry_v2)
        assert registry["schema_version"] == 2
        assert len(registry["plugins"]) == 1
        assert registry["plugins"][0]["id"] == "legacy-tool"

    def test_backward_compat_v1_entries_load(self, tmp_registry_v1: Path) -> None:
        registry = load_registry(tmp_registry_v1)
        assert registry["schema_version"] == 1
        assert len(registry["plugins"]) == 1

    def test_v2_entry_resolves_with_no_upgrade_cmd(self, tmp_registry_v2: Path) -> None:
        from devolaflow.plugins.installer import resolve_plugin

        registry = load_registry(tmp_registry_v2)
        spec = resolve_plugin("legacy-tool", registry)
        # v2 entry has no upgrade_cmd field — spec.upgrade_cmd defaults to None
        assert spec.upgrade_cmd is None


# ---------------------------------------------------------------------------
# §3 — read_last_checked reads JSONL audit trail
# ---------------------------------------------------------------------------


def _write_log_lines(log_path: Path, lines: list[dict]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as fh:
        for record in lines:
            fh.write(json.dumps(record) + "\n")


class TestReadLastChecked:
    """Parse plugin_install.log and return the most-recent timestamp per plugin."""

    def test_returns_none_when_log_missing(self, tmp_path: Path) -> None:
        assert read_last_checked("nines", log_path=tmp_path / "missing.log") is None

    def test_returns_most_recent_for_plugin(self, tmp_path: Path) -> None:
        log = tmp_path / "plugin_install.log"
        ts_old = "2026-04-01T10:00:00+00:00"
        ts_new = "2026-05-01T10:00:00+00:00"
        _write_log_lines(
            log,
            [
                {"ts": ts_old, "plugin_id": "nines", "event": "plugin_installed", "details": {}},
                {
                    "ts": ts_new,
                    "plugin_id": "nines",
                    "event": "plugin_already_installed",
                    "details": {},
                },
                {"ts": ts_new, "plugin_id": "ui-pro", "event": "plugin_installed", "details": {}},
            ],
        )
        result = read_last_checked("nines", log_path=log)
        assert result is not None
        assert result == datetime.fromisoformat(ts_new)

    def test_ignores_failure_events(self, tmp_path: Path) -> None:
        """Only successful events count as a "checked" timestamp."""
        log = tmp_path / "plugin_install.log"
        ts = "2026-05-01T10:00:00+00:00"
        _write_log_lines(
            log,
            [
                {"ts": ts, "plugin_id": "nines", "event": "plugin_install_failed", "details": {}},
                {
                    "ts": ts,
                    "plugin_id": "nines",
                    "event": "plugin_install_distinguish_failed_postinstall",
                    "details": {},
                },
            ],
        )
        assert read_last_checked("nines", log_path=log) is None

    def test_skips_malformed_lines(self, tmp_path: Path) -> None:
        log = tmp_path / "plugin_install.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("w", encoding="utf-8") as fh:
            fh.write("not-json-at-all\n")
            fh.write(
                json.dumps(
                    {"ts": "garbage-timestamp", "plugin_id": "nines", "event": "plugin_installed"}
                )
                + "\n"
            )
            fh.write(
                json.dumps(
                    {
                        "ts": "2026-05-01T10:00:00+00:00",
                        "plugin_id": "nines",
                        "event": "plugin_installed",
                    }
                )
                + "\n"
            )
        result = read_last_checked("nines", log_path=log)
        assert result is not None
        assert result.year == 2026 and result.month == 5

    def test_recognises_plugin_upgraded_event(self, tmp_path: Path) -> None:
        log = tmp_path / "plugin_install.log"
        ts = "2026-05-01T10:00:00+00:00"
        _write_log_lines(
            log,
            [{"ts": ts, "plugin_id": "nines", "event": "plugin_upgraded", "details": {}}],
        )
        assert read_last_checked("nines", log_path=log) == datetime.fromisoformat(ts)


# ---------------------------------------------------------------------------
# §4 — is_plugin_stale honours threshold
# ---------------------------------------------------------------------------


class TestIsPluginStale:
    """Stale = (now - last_checked) >= threshold_hours OR no record exists."""

    def test_no_record_is_stale(self, tmp_path: Path) -> None:
        assert (
            is_plugin_stale("nines", threshold_hours=24, log_path=tmp_path / "missing.log") is True
        )

    def test_recent_check_is_fresh(self, tmp_path: Path) -> None:
        log = tmp_path / "plugin_install.log"
        recent_ts = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
        _write_log_lines(
            log,
            [{"ts": recent_ts, "plugin_id": "nines", "event": "plugin_installed", "details": {}}],
        )
        assert is_plugin_stale("nines", threshold_hours=24, log_path=log) is False

    def test_old_check_is_stale(self, tmp_path: Path) -> None:
        log = tmp_path / "plugin_install.log"
        old_ts = (datetime.now(UTC) - timedelta(hours=48)).isoformat()
        _write_log_lines(
            log,
            [{"ts": old_ts, "plugin_id": "nines", "event": "plugin_installed", "details": {}}],
        )
        assert is_plugin_stale("nines", threshold_hours=24, log_path=log) is True

    def test_now_arg_overrides_clock(self, tmp_path: Path) -> None:
        """Test seam: pin the staleness reference time."""
        log = tmp_path / "plugin_install.log"
        ts_str = "2026-05-01T00:00:00+00:00"
        _write_log_lines(
            log,
            [{"ts": ts_str, "plugin_id": "nines", "event": "plugin_installed", "details": {}}],
        )
        # 23 hours later → fresh
        assert (
            is_plugin_stale(
                "nines",
                threshold_hours=24,
                log_path=log,
                now=datetime(2026, 5, 1, 23, 0, 0, tzinfo=UTC),
            )
            is False
        )
        # 25 hours later → stale
        assert (
            is_plugin_stale(
                "nines",
                threshold_hours=24,
                log_path=log,
                now=datetime(2026, 5, 2, 1, 0, 0, tzinfo=UTC),
            )
            is True
        )


# ---------------------------------------------------------------------------
# §5-9 — upgrade_plugin + refresh_all (with mocked subprocess)
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_subprocess(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Patch _run_cmd to return a configurable mock; track invocations."""
    state: dict = {"calls": [], "responses": {}, "default_returncode": 0}

    def fake_run(cmd: str, *, timeout: int) -> subprocess.CompletedProcess[str]:
        state["calls"].append(cmd)
        for prefix, response in state["responses"].items():
            if cmd.startswith(prefix):
                return response
        # Default mock version 99.99.99 — above every plugin's min_version
        # so the post-upgrade probe in upgrade_plugin doesn't accidentally
        # trip the version-mismatch guard.
        return subprocess.CompletedProcess(
            args=["bash", "-c", cmd],
            returncode=state["default_returncode"],
            stdout="version 99.99.99",
            stderr="",
        )

    monkeypatch.setattr("devolaflow.plugins.installer._run_cmd", fake_run)
    return state


class TestUpgradePlugin:
    """upgrade_plugin runs the right command + writes a plugin_upgraded log entry."""

    def test_upgrades_plugin_and_logs_event(self, tmp_path: Path, mock_subprocess: dict) -> None:
        log = tmp_path / "plugin_install.log"
        result = upgrade_plugin("nines", log_path=log)
        # Mock version probe returns 99.99.99 — above the 3.0.0 min_version
        assert result == "99.99.99"
        log_lines = log.read_text(encoding="utf-8").splitlines()
        assert len(log_lines) >= 1
        events = [json.loads(line)["event"] for line in log_lines]
        assert "plugin_upgraded" in events

    def test_upgrade_runs_explicit_upgrade_cmd_when_present(
        self, tmp_path: Path, mock_subprocess: dict
    ) -> None:
        """When upgrade_cmd is set, prefer it over install_cmd."""
        log = tmp_path / "plugin_install.log"
        upgrade_plugin("nines", log_path=log)
        # The canonical nines registry has upgrade_cmd == install_cmd, but
        # the call recorder shows both the upgrade and the verify probe.
        upgrade_calls = [c for c in mock_subprocess["calls"] if "pip install --upgrade nines" in c]
        assert upgrade_calls, (
            f"upgrade_plugin must run the upgrade command; calls={mock_subprocess['calls']!r}"
        )

    def test_upgrade_failure_raises_loudly(self, tmp_path: Path, mock_subprocess: dict) -> None:
        """Exit code != 0 from upgrade_cmd raises PluginInstallError per S-5."""
        mock_subprocess["responses"]["pip install --upgrade nines"] = subprocess.CompletedProcess(
            args=["bash", "-c", "pip install --upgrade nines"],
            returncode=1,
            stdout="",
            stderr="network unreachable",
        )
        log = tmp_path / "plugin_install.log"
        with pytest.raises(PluginInstallError, match="upgrade failed"):
            upgrade_plugin("nines", log_path=log)

    def test_upgrade_failure_logs_failed_event(self, tmp_path: Path, mock_subprocess: dict) -> None:
        mock_subprocess["responses"]["pip install --upgrade nines"] = subprocess.CompletedProcess(
            args=["bash", "-c", "pip install --upgrade nines"],
            returncode=1,
            stdout="",
            stderr="boom",
        )
        log = tmp_path / "plugin_install.log"
        with pytest.raises(PluginInstallError):
            upgrade_plugin("nines", log_path=log)
        events = [
            json.loads(line)["event"] for line in log.read_text(encoding="utf-8").splitlines()
        ]
        assert "plugin_upgrade_failed" in events


class TestRefreshAll:
    """refresh_all walks registry + skips fresh + upgrades stale."""

    def test_refresh_skips_fresh_plugins(self, tmp_path: Path, mock_subprocess: dict) -> None:
        """When all plugins are fresh, refresh_all upgrades nothing."""
        log = tmp_path / "plugin_install.log"
        recent_ts = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
        _write_log_lines(
            log,
            [
                {"ts": recent_ts, "plugin_id": "nines", "event": "plugin_installed", "details": {}},
                {
                    "ts": recent_ts,
                    "plugin_id": "ui-pro",
                    "event": "plugin_installed",
                    "details": {},
                },
                {"ts": recent_ts, "plugin_id": "rtk", "event": "plugin_installed", "details": {}},
            ],
        )
        outcomes = refresh_all(log_path=log)
        actions = {o.plugin_id: o.action for o in outcomes}
        assert all(action == "skipped_fresh" for action in actions.values())
        assert set(actions.keys()) == {"nines", "ui-pro", "rtk"}

    def test_refresh_force_upgrades_all_regardless_of_staleness(
        self, tmp_path: Path, mock_subprocess: dict
    ) -> None:
        """--force bypasses the staleness check."""
        log = tmp_path / "plugin_install.log"
        recent_ts = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
        _write_log_lines(
            log,
            [
                {"ts": recent_ts, "plugin_id": "nines", "event": "plugin_installed", "details": {}},
                {
                    "ts": recent_ts,
                    "plugin_id": "ui-pro",
                    "event": "plugin_installed",
                    "details": {},
                },
                {"ts": recent_ts, "plugin_id": "rtk", "event": "plugin_installed", "details": {}},
            ],
        )
        outcomes = refresh_all(log_path=log, force=True)
        upgraded = [o for o in outcomes if o.action == "upgraded"]
        assert len(upgraded) == 3, (
            f"--force must upgrade ALL plugins regardless of staleness; "
            f"got upgraded={[o.plugin_id for o in upgraded]!r}"
        )

    def test_refresh_only_filter_restricts_to_one_plugin(
        self, tmp_path: Path, mock_subprocess: dict
    ) -> None:
        """`only=['nines']` restricts processing to the nines plugin."""
        log = tmp_path / "plugin_install.log"
        outcomes = refresh_all(log_path=log, force=True, only=["nines"])
        assert {o.plugin_id for o in outcomes} == {"nines"}

    def test_refresh_unknown_plugin_in_only_returns_empty(
        self, tmp_path: Path, mock_subprocess: dict
    ) -> None:
        log = tmp_path / "plugin_install.log"
        outcomes = refresh_all(log_path=log, force=True, only=["nonexistent"])
        assert outcomes == []

    def test_refresh_upgrade_failure_captured_as_outcome_not_raised(
        self, tmp_path: Path, mock_subprocess: dict
    ) -> None:
        """CI-safe: network failure on one plugin → outcome action='failed', no raise."""
        log = tmp_path / "plugin_install.log"
        mock_subprocess["responses"]["pip install --upgrade nines"] = subprocess.CompletedProcess(
            args=["bash", "-c", "x"], returncode=1, stdout="", stderr="boom"
        )
        outcomes = refresh_all(log_path=log, force=True, only=["nines"])
        assert len(outcomes) == 1
        assert outcomes[0].action == "failed"
        assert outcomes[0].plugin_id == "nines"
        assert "PluginInstallError" in (outcomes[0].error or "")

    def test_refresh_outcome_dataclass_fields(self) -> None:
        outcome = RefreshOutcome(plugin_id="nines", action="upgraded", version="3.3.0")
        assert outcome.plugin_id == "nines"
        assert outcome.action == "upgraded"
        assert outcome.version == "3.3.0"
        assert outcome.reason is None
        assert outcome.error is None


# ---------------------------------------------------------------------------
# §10 — list_plugins inspection rows
# ---------------------------------------------------------------------------


class TestListPlugins:
    """list_plugins returns inspection rows with last_checked field."""

    def test_list_plugins_returns_one_row_per_plugin(
        self, tmp_path: Path, mock_subprocess: dict
    ) -> None:
        log = tmp_path / "plugin_install.log"
        rows = list_plugins(log_path=log)
        ids = {row["id"] for row in rows}
        assert ids == {"nines", "ui-pro", "rtk"}

    def test_list_plugins_carries_last_checked(self, tmp_path: Path, mock_subprocess: dict) -> None:
        log = tmp_path / "plugin_install.log"
        ts = "2026-05-01T10:00:00+00:00"
        _write_log_lines(
            log,
            [{"ts": ts, "plugin_id": "nines", "event": "plugin_installed", "details": {}}],
        )
        rows = list_plugins(log_path=log)
        nines_row = next(r for r in rows if r["id"] == "nines")
        assert nines_row["last_checked"] == ts
        ui_pro_row = next(r for r in rows if r["id"] == "ui-pro")
        assert ui_pro_row["last_checked"] is None

    def test_list_plugins_carries_invoked_workflows(
        self, tmp_path: Path, mock_subprocess: dict
    ) -> None:
        rows = list_plugins(log_path=tmp_path / "missing.log")
        nines_row = next(r for r in rows if r["id"] == "nines")
        assert "skill-optimization" in nines_row["invoked_by_workflows"]

    def test_list_plugins_marks_explicit_upgrade_cmd(
        self, tmp_path: Path, mock_subprocess: dict
    ) -> None:
        """has_explicit_upgrade_cmd should be True for canonical v3 entries."""
        rows = list_plugins(log_path=tmp_path / "missing.log")
        for row in rows:
            assert row["has_explicit_upgrade_cmd"] is True, (
                f"v3 canonical registry should declare upgrade_cmd per plugin; "
                f"plugin {row['id']!r} missing it"
            )


# ---------------------------------------------------------------------------
# §11 — CLI smoke test (`devolaflow plugins list --json`)
# ---------------------------------------------------------------------------


class TestPluginsCli:
    """Smoke-test the `devolaflow plugins` CLI subcommand."""

    def test_cli_list_json_prints_array(
        self, mock_subprocess: dict, capsys: pytest.CaptureFixture
    ) -> None:
        from devolaflow.cli import plugins_cmd

        with (
            patch("sys.argv", ["devolaflow-plugins", "list", "--json"]),
            pytest.raises(SystemExit) as exc_info,
        ):
            plugins_cmd()
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        rows = json.loads(captured.out)
        assert isinstance(rows, list)
        assert all("id" in r for r in rows)

    def test_cli_status_alias_works(
        self, mock_subprocess: dict, capsys: pytest.CaptureFixture
    ) -> None:
        from devolaflow.cli import plugins_cmd

        with (
            patch("sys.argv", ["devolaflow-plugins", "status", "--json"]),
            pytest.raises(SystemExit) as exc_info,
        ):
            plugins_cmd()
        assert exc_info.value.code == 0

    def test_cli_refresh_force_exits_zero_on_success(
        self, tmp_path: Path, mock_subprocess: dict, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """gap analysis §6 AC-5: refresh CLI exits 0 on staleness check."""
        from devolaflow.cli import plugins_cmd

        # Use the canonical registry but redirect log to tmp; with --force, all
        # plugins upgrade; mock_subprocess returns 0 for all commands.
        monkeypatch.chdir(tmp_path)
        # Provide a minimal local registry mirror so load_registry() finds it.
        registry_dir = tmp_path / "workflow-system" / "agent" / "knowledge"
        registry_dir.mkdir(parents=True)
        canonical = (
            Path(__file__).resolve().parent.parent
            / "workflow-system/agent/knowledge/runtime-plugins.yaml"
        )
        (registry_dir / "runtime-plugins.yaml").write_text(
            canonical.read_text(encoding="utf-8"), encoding="utf-8"
        )

        with (
            patch("sys.argv", ["devolaflow-plugins", "refresh", "--force"]),
            pytest.raises(SystemExit) as exc_info,
        ):
            plugins_cmd()
        assert exc_info.value.code == 0

    def test_cli_refresh_failure_exits_one(
        self, tmp_path: Path, mock_subprocess: dict, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """gap analysis §6 AC-7: per-row failures → exit 1; no crash."""
        from devolaflow.cli import plugins_cmd

        mock_subprocess["responses"]["pip install --upgrade nines"] = subprocess.CompletedProcess(
            args=["bash", "-c", "x"], returncode=1, stdout="", stderr="boom"
        )
        monkeypatch.chdir(tmp_path)
        registry_dir = tmp_path / "workflow-system" / "agent" / "knowledge"
        registry_dir.mkdir(parents=True)
        canonical = (
            Path(__file__).resolve().parent.parent
            / "workflow-system/agent/knowledge/runtime-plugins.yaml"
        )
        (registry_dir / "runtime-plugins.yaml").write_text(
            canonical.read_text(encoding="utf-8"), encoding="utf-8"
        )

        with (
            patch(
                "sys.argv",
                ["devolaflow-plugins", "refresh", "--force", "--plugin", "nines"],
            ),
            pytest.raises(SystemExit) as exc_info,
        ):
            plugins_cmd()
        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# §12 — Schema v3 fixture round-trip (no live registry mutation)
# ---------------------------------------------------------------------------


def test_schema_v3_round_trips_via_yaml(tmp_path: Path) -> None:
    """Pin that a valid v3 registry serialises round-trip cleanly."""
    sample = {
        "schema_version": 3,
        "last_updated": "2026-05-02",
        "plugins": [
            {
                "id": "test-plugin",
                "backend": "pip",
                "package": "test-pkg",
                "install_cmd": "pip install test-pkg",
                "upgrade_cmd": "pip install --upgrade test-pkg",
                "version_check_cmd": "test-pkg --version",
                "min_version": "1.0.0",
                "canonical_url": "https://example.com",
                "invoked_by_workflows": ["test-flow"],
            }
        ],
        "defaults": {
            "auto_install": True,
            "upgrade_check_frequency_hours": 12,
            "install_log_path": str(tmp_path / "log.jsonl"),
            "network_timeout_seconds": 30,
            "prefer_local_fallback": True,
        },
    }
    registry_path = tmp_path / "v3-sample.yaml"
    registry_path.write_text(yaml.dump(sample), encoding="utf-8")
    parsed = load_registry(registry_path)
    assert parsed["schema_version"] == 3
    assert parsed["plugins"][0]["upgrade_cmd"] == "pip install --upgrade test-pkg"
    assert parsed["defaults"]["upgrade_check_frequency_hours"] == 12
