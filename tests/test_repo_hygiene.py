"""Tests for the release-side repository hygiene batch."""

from __future__ import annotations

import json
from pathlib import Path

from scripts import check_repo_hygiene as hygiene


def test_hygiene_batch_has_stable_release_checks_and_relative_inputs() -> None:
    specs = hygiene._specs("origin/main")
    assert [spec.name for spec in specs] == [
        "agent-language",
        "import-graph",
        "module-size",
        "functional-matrix",
        "ghost",
    ]
    assert all(
        not Path(item).is_absolute() and ".." not in Path(item).parts
        for spec in specs
        for item in spec.inputs
    )
    assert specs[0].cacheable is True
    assert specs[-1].cacheable is False
    ghost_command = hygiene._legacy_ghost_command(Path("."), list(specs[-1].command))
    assert "tests/ghost/test_features_v20_0.py" not in ghost_command
    assert "tests/ghost/test_features_v15_2.py" in ghost_command


def test_repeated_batch_uses_cache_for_stable_inventory_checks(tmp_path: Path, monkeypatch) -> None:
    calls: list[str] = []

    def fake_run(root: Path, spec: hygiene.CheckSpec) -> hygiene.CheckResult:
        calls.append(spec.name)
        return hygiene.CheckResult(spec.name, hygiene.STATUS_PASS, detail="fake")

    monkeypatch.setattr(hygiene, "_run_spec", fake_run)
    cache = tmp_path / "cache.json"
    first = hygiene.run_checks(tmp_path, cache_path=cache)
    second = hygiene.run_checks(tmp_path, cache_path=cache)

    assert calls == [
        "agent-language",
        "import-graph",
        "module-size",
        "functional-matrix",
        "ghost",
        "functional-matrix",
        "ghost",
    ]
    assert [result.status for result in first] == [hygiene.STATUS_PASS] * 5
    assert [result.cached for result in second] == [True, True, True, False, False]
    payload = json.loads(cache.read_text(encoding="utf-8"))
    assert payload["version"] == hygiene.CACHE_VERSION
    assert set(payload["checks"]) == {"agent-language", "import-graph", "module-size"}


def test_changed_only_never_treats_unchanged_checks_as_pass(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(hygiene, "_changed_paths", lambda root, ref: set())
    monkeypatch.setattr(
        hygiene,
        "_run_spec",
        lambda root, spec: (_ for _ in ()).throw(AssertionError("must not run")),
    )

    results = hygiene.run_checks(tmp_path, changed_only=True, cache_path=None)

    assert {result.status for result in results} == {hygiene.STATUS_INSUFFICIENT}
    assert hygiene._overall_status(results) == hygiene.STATUS_INSUFFICIENT


def test_dry_run_is_explicitly_insufficient() -> None:
    results = hygiene.run_checks(Path("."), dry_run=True, cache_path=None)

    assert all(result.detail == "dry-run" for result in results)
    assert hygiene._overall_status(results) == hygiene.STATUS_INSUFFICIENT


def test_failed_check_propagates_without_becoming_insufficient(tmp_path: Path, monkeypatch) -> None:
    def fake_run(root: Path, spec: hygiene.CheckSpec) -> hygiene.CheckResult:
        status = hygiene.STATUS_FAIL if spec.name == "import-graph" else hygiene.STATUS_PASS
        detail = "exit=1" if status == "FAIL" else "exit=0"
        return hygiene.CheckResult(spec.name, status, detail=detail)

    monkeypatch.setattr(hygiene, "_run_spec", fake_run)
    results = hygiene.run_checks(tmp_path, cache_path=None)

    assert next(result for result in results if result.name == "import-graph").status == "FAIL"
    assert hygiene._overall_status(results) == hygiene.STATUS_FAIL


def test_cache_invalidates_when_an_inventory_input_changes(tmp_path: Path, monkeypatch) -> None:
    calls: list[str] = []

    def fake_run(root: Path, spec: hygiene.CheckSpec) -> hygiene.CheckResult:
        calls.append(spec.name)
        return hygiene.CheckResult(spec.name, hygiene.STATUS_PASS)

    monkeypatch.setattr(hygiene, "_run_spec", fake_run)
    cache = tmp_path / "cache.json"
    (tmp_path / "AGENTS.md").write_text("before\n", encoding="utf-8")
    hygiene.run_checks(tmp_path, cache_path=cache)
    (tmp_path / "AGENTS.md").write_text("after\n", encoding="utf-8")
    hygiene.run_checks(tmp_path, cache_path=cache)

    assert calls.count("agent-language") == 2
    assert calls.count("import-graph") == 1
    assert calls.count("module-size") == 1


def test_json_main_reports_insufficient_and_returns_two_for_dry_run(
    capsys,
) -> None:
    exit_code = hygiene.main(["--dry-run", "--no-cache", "--format", "json"])

    assert exit_code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == hygiene.STATUS_INSUFFICIENT
    assert all(item["status"] == hygiene.STATUS_INSUFFICIENT for item in payload["checks"])
