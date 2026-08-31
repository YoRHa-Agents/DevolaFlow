"""Gap/coverage inventory engine and module-CLI tests."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import pytest
import yaml

from devolaflow.harness.__main__ import main
from devolaflow.harness.evaluator import SIGNAL_KEYS, SignalResult, render_evaluation
from devolaflow.harness.gap import (
    BUILTIN_GAP_AXES,
    GapConfigError,
    build_gap_report,
    compare_gap_reports,
    load_gap_report,
    render_capability_review,
)

_TS = "2026-08-25T00:00:00+00:00"


def _record(dispatch_id: str, *, layer: str) -> dict:
    return {
        "ts": _TS,
        "change_id": "gap-change",
        "round": 1,
        "layer": layer,
        "dispatch_id": dispatch_id,
        "tokens_injected_measured": 800,
        "tokens_budget": 1_000,
        "constraint_count": 4,
        "quantifiable_ratio": 0.75,
        "tier_breakdown": {"invariant": 2, "guard": 1, "advisory": 1},
        "advisory_folded": False,
        "model_hint": "quality",
    }


def _event() -> dict:
    proposal_id = "a" * 64
    return {
        "schema_version": 1,
        "event": "proposal_applied",
        "event_id": f"proposal_applied:{proposal_id}",
        "ts": _TS,
        "proposal_id": proposal_id,
        "proposal_ref": ".local/telemetry/proposals/p.yaml",
        "approval_ref": ".local/telemetry/approvals/a.yaml",
        "proposal_sha256": "b" * 64,
        "target_digest": "c" * 64,
    }


def _write_ledger(
    path: Path,
    *,
    layers: tuple[str, ...] = ("L0", "L1", "L2"),
    include_event: bool = True,
) -> Path:
    records: list[dict] = [
        _record(f"gap-{index}", layer=layer) for index, layer in enumerate(layers)
    ]
    if include_event:
        records.append(_event())
    path.write_text(
        "".join(json.dumps(record, separators=(",", ":")) + "\n" for record in records),
        encoding="utf-8",
    )
    return path


def _signals(unavailable: tuple[str, ...] = ()) -> dict[str, SignalResult]:
    values: dict[str, bool | float | int] = {
        "ruff_lint": True,
        "ruff_format": True,
        "test_suite": True,
        "coverage_pct": 85.0,
        "layout_invariant": True,
        "compatibility_suite": True,
        "w17_new_tests": 0,
        "docstring_coverage_pct": 90.0,
        "estimated_agents_md_tokens": 1200,
        "suite_wall_seconds": 18.25,
        "cjk_violations": 0,
        "ghost_loc": 900,
    }
    return {
        key: (
            SignalResult(available=False, error=f"{key} probe timeout")
            if key in unavailable
            else SignalResult(available=True, value=values[key])
        )
        for key in SIGNAL_KEYS
    }


def _scaffold_repo(
    root: Path,
    *,
    fixtures: bool = True,
    probe_models: bool = True,
    baselines: bool = True,
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    if fixtures:
        fixtures_dir = root / "tests" / "fixtures" / "harness"
        fixtures_dir.mkdir(parents=True)
        (fixtures_dir / "sample.yaml").write_text("id: sample\n", encoding="utf-8")
    if probe_models:
        profiles = root / "workflow-system" / "agent" / "context_profiles.yaml"
        profiles.parent.mkdir(parents=True)
        profiles.write_text(
            "meta:\n  probe_models:\n  - provider: mock\n    model: probe-model-1\n",
            encoding="utf-8",
        )
    if baselines:
        baselines_dir = root / ".local" / "telemetry" / "baselines"
        baselines_dir.mkdir(parents=True)
        (baselines_dir / "harness_baseline_v1.json").write_text("{}\n", encoding="utf-8")
    return root


def _write_config(path: Path, axes: list[dict]) -> Path:
    path.write_text(
        yaml.safe_dump({"schema_version": 1, "axes": axes}, sort_keys=False),
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize(
    (
        "layers",
        "include_event",
        "unavailable",
        "repo_flags",
        "expected_statuses",
        "expected_auto_fill",
        "expected_insufficient",
    ),
    [
        pytest.param(
            ("L0", "L1", "L2"),
            True,
            (),
            {},
            ("COVERED",) * 6,
            1.0,
            [],
            id="all-covered",
        ),
        pytest.param(
            ("L0",),
            False,
            (),
            {},
            ("PARTIAL", "COVERED", "COVERED", "COVERED", "COVERED", "GAP"),
            1.0,
            [],
            id="partial-observation-open-loop",
        ),
        pytest.param(
            ("L0", "L1", "L2"),
            True,
            ("coverage_pct", "docstring_coverage_pct"),
            {},
            ("COVERED", "PARTIAL", "COVERED", "COVERED", "PARTIAL", "COVERED"),
            0.7857,
            ["code_quality.coverage", "test_adequacy.coverage", "maintainability.docstrings"],
            id="partial-evaluation-and-signal",
        ),
        pytest.param(
            ("L0", "L1", "L2"),
            True,
            (),
            {"probe_models": False},
            ("COVERED", "COVERED", "PARTIAL", "COVERED", "COVERED", "COVERED"),
            1.0,
            [],
            id="probe-partial-no-model-table",
        ),
        pytest.param(
            ("L0", "L1", "L2"),
            True,
            SIGNAL_KEYS,
            {"fixtures": False, "probe_models": False, "baselines": False},
            ("COVERED", "PARTIAL", "GAP", "GAP", "GAP", "COVERED"),
            0.2143,
            [
                "code_quality.ruff_lint",
                "code_quality.ruff_format",
                "code_quality.coverage",
                "architecture_rationality.layout_invariant",
                "test_adequacy.test_suite",
                "test_adequacy.coverage",
                "test_adequacy.w17",
                "maintainability.ruff_format",
                "maintainability.docstrings",
                "compatibility.layout_invariant",
                "compatibility.compatibility_suite",
            ],
            id="probe-baseline-signal-gaps",
        ),
    ],
)
def test_builtin_axes_statuses_over_synthetic_ledgers(
    tmp_path: Path,
    layers: tuple[str, ...],
    include_event: bool,
    unavailable: tuple[str, ...],
    repo_flags: dict,
    expected_statuses: tuple[str, ...],
    expected_auto_fill: float,
    expected_insufficient: list[str],
) -> None:
    root = _scaffold_repo(tmp_path / "repo", **repo_flags)
    ledger = _write_ledger(tmp_path / "harness.jsonl", layers=layers, include_event=include_event)

    report = build_gap_report(
        ledger,
        repo_root=root,
        signals=_signals(tuple(unavailable)),
        sampled_at=_TS,
    )

    axes = report["axes"]
    assert [axis["id"] for axis in axes] == list(BUILTIN_GAP_AXES)
    assert all(axis["builtin"] is True for axis in axes)
    assert [axis["status"] for axis in axes] == list(expected_statuses)
    assert report["auto_fill_rate"] == expected_auto_fill
    assert report["insufficient_slots"] == expected_insufficient
    assert report["summary"] == {
        "covered": expected_statuses.count("COVERED"),
        "partial": expected_statuses.count("PARTIAL"),
        "gap": expected_statuses.count("GAP"),
    }
    for axis in axes:
        if axis["status"] == "COVERED":
            assert axis["gaps"] == []
        else:
            assert axis["gaps"], f"{axis['id']} must list concrete gaps"
            assert all(set(gap) == {"item", "reason"} for gap in axis["gaps"])


def test_absent_ledger_is_evidence_not_error(tmp_path: Path) -> None:
    root = _scaffold_repo(tmp_path / "repo")
    config = _write_config(
        tmp_path / "axes.yaml",
        [
            {
                "id": "sim-stage-latency",
                "title": "simulated stage latency observation",
                "probe": {"kind": "ledger_query", "spec": {"event": "stage_latency"}},
                "rationale": "stage latency must be observable before tuning",
            }
        ],
    )

    report = build_gap_report(
        tmp_path / "missing.jsonl",
        repo_root=root,
        axes_config=config,
        signals=_signals(),
        sampled_at=_TS,
    )

    by_id = {axis["id"]: axis for axis in report["axes"]}
    for axis_id in ("observation", "evaluation", "loop-closure"):
        assert by_id[axis_id]["status"] == "GAP"
        assert by_id[axis_id]["evidence"]["ledger"] == "absent"
        assert [gap["reason"] for gap in by_id[axis_id]["gaps"]] == ["ledger absent"]
    assert report["auto_fill_rate"] == 0.0
    assert report["insufficient_slots"] == []
    assert by_id["signal"]["status"] == "COVERED"
    assert by_id["probe"]["status"] == "COVERED"
    assert by_id["baseline"]["status"] == "COVERED"
    custom = by_id["sim-stage-latency"]
    assert custom["builtin"] is False
    assert custom["status"] == "GAP"
    assert custom["evidence"]["ledger"] == "absent"
    assert report["summary"] == {"covered": 3, "partial": 0, "gap": 4}


@pytest.mark.parametrize(
    ("probe", "expected_status", "reason_fragment", "evidence_subset"),
    [
        pytest.param(
            {"kind": "file_exists", "spec": {"path": "goal.txt"}},
            "COVERED",
            None,
            {"kind": "file_exists", "path": "goal.txt", "exists": True},
            id="file-exists-covered",
        ),
        pytest.param(
            {"kind": "file_exists", "spec": {"path": "absent.txt"}},
            "GAP",
            "path does not exist",
            {"exists": False},
            id="file-exists-gap",
        ),
        pytest.param(
            {
                "kind": "command",
                "spec": {
                    "argv": [sys.executable, "-c", "raise SystemExit(0)"],
                    "timeout_seconds": 30,
                },
            },
            "COVERED",
            None,
            {"kind": "command", "returncode": 0},
            id="command-covered",
        ),
        pytest.param(
            {
                "kind": "command",
                "spec": {
                    "argv": [
                        sys.executable,
                        "-c",
                        "import sys; sys.stderr.write('boom'); sys.exit(3)",
                    ],
                    "timeout_seconds": 30,
                },
            },
            "GAP",
            "command exited 3",
            {"returncode": 3, "stderr_tail": "boom"},
            id="command-nonzero-stderr-tail",
        ),
        pytest.param(
            {
                "kind": "command",
                "spec": {
                    "argv": [sys.executable, "-c", "import time; time.sleep(5)"],
                    "timeout_seconds": 1,
                },
            },
            "GAP",
            "timeout after 1s",
            {"timeout_seconds": 1},
            id="command-timeout",
        ),
        pytest.param(
            {"kind": "ledger_query", "spec": {"event": "proposal_applied"}},
            "COVERED",
            None,
            {"kind": "ledger_query", "event": "proposal_applied", "min_count": 1, "count": 1},
            id="ledger-query-covered",
        ),
        pytest.param(
            {"kind": "ledger_query", "spec": {"event": "proposal_applied", "min_count": 2}},
            "GAP",
            "need >= 2",
            {"min_count": 2, "count": 1},
            id="ledger-query-below-min-count",
        ),
    ],
)
def test_custom_axis_probe_kinds(
    tmp_path: Path,
    probe: dict,
    expected_status: str,
    reason_fragment: str | None,
    evidence_subset: dict,
) -> None:
    root = _scaffold_repo(tmp_path / "repo")
    (root / "goal.txt").write_text("goal\n", encoding="utf-8")
    ledger = _write_ledger(tmp_path / "harness.jsonl")
    config = _write_config(
        tmp_path / "axes.yaml",
        [{"id": "custom-axis", "title": "custom probe", "probe": probe}],
    )

    report = build_gap_report(
        ledger,
        repo_root=root,
        axes_config=config,
        signals=_signals(),
        sampled_at=_TS,
    )

    assert [axis["id"] for axis in report["axes"][:6]] == list(BUILTIN_GAP_AXES)
    axis = report["axes"][6]
    assert axis["id"] == "custom-axis"
    assert axis["title"] == "custom probe"
    assert axis["builtin"] is False
    assert axis["status"] == expected_status
    assert evidence_subset.items() <= axis["evidence"].items()
    if reason_fragment is None:
        assert axis["gaps"] == []
    else:
        assert reason_fragment in axis["gaps"][0]["reason"]


_VALID_AXIS = {"id": "ok-axis", "probe": {"kind": "file_exists", "spec": {"path": "goal.txt"}}}


@pytest.mark.parametrize(
    ("config_document", "match"),
    [
        pytest.param("axes: [unclosed", "invalid axes config YAML", id="malformed-yaml"),
        pytest.param("- 1\n- 2\n", "root must be a mapping", id="root-not-mapping"),
        pytest.param(
            {"schema_version": 2, "axes": [_VALID_AXIS]},
            "schema_version must equal 1",
            id="wrong-schema-version",
        ),
        pytest.param(
            {"schema_version": 1, "axes": [_VALID_AXIS], "notes": "x"},
            "keys mismatch",
            id="extra-top-level-key",
        ),
        pytest.param({"schema_version": 1, "axes": []}, "non-empty list", id="empty-axes"),
        pytest.param(
            {"schema_version": 1, "axes": [{"id": "no-probe-axis"}]},
            r"missing=\['probe'\]",
            id="missing-probe",
        ),
        pytest.param(
            {"schema_version": 1, "axes": [{"id": "x", "probe": {"kind": "vibes", "spec": {}}}]},
            "probe.kind must be one of",
            id="unknown-kind",
        ),
        pytest.param(
            {"schema_version": 1, "axes": [{"id": "Bad_Slug", "probe": _VALID_AXIS["probe"]}]},
            "lowercase hyphenated slug",
            id="invalid-slug",
        ),
        pytest.param(
            {"schema_version": 1, "axes": [{"id": "probe", "probe": _VALID_AXIS["probe"]}]},
            "collides",
            id="builtin-id-collision",
        ),
        pytest.param(
            {"schema_version": 1, "axes": [_VALID_AXIS, _VALID_AXIS]},
            "collides",
            id="duplicate-custom-id",
        ),
        pytest.param(
            {
                "schema_version": 1,
                "axes": [{"id": "x", "probe": {"kind": "command", "spec": {"argv": ["true"]}}}],
            },
            "'argv' and 'timeout_seconds'",
            id="command-missing-timeout",
        ),
        pytest.param(
            {
                "schema_version": 1,
                "axes": [
                    {
                        "id": "x",
                        "probe": {
                            "kind": "command",
                            "spec": {"argv": ["true"], "timeout_seconds": 121},
                        },
                    }
                ],
            },
            "timeout_seconds must be an integer",
            id="command-timeout-over-cap",
        ),
        pytest.param(
            {
                "schema_version": 1,
                "axes": [
                    {"id": "x", "probe": {"kind": "file_exists", "spec": {"path": "/etc/hosts"}}}
                ],
            },
            "repository-relative",
            id="file-exists-absolute-path",
        ),
        pytest.param(
            {
                "schema_version": 1,
                "axes": [
                    {
                        "id": "x",
                        "probe": {
                            "kind": "ledger_query",
                            "spec": {"event": "e", "min_count": 0},
                        },
                    }
                ],
            },
            "min_count must be an integer >= 1",
            id="ledger-query-zero-min-count",
        ),
    ],
)
def test_axes_config_errors_raise_gap_config_error(
    tmp_path: Path,
    config_document: str | dict,
    match: str,
) -> None:
    config = tmp_path / "axes.yaml"
    text = (
        config_document
        if isinstance(config_document, str)
        else yaml.safe_dump(config_document, sort_keys=False)
    )
    config.write_text(text, encoding="utf-8")

    with pytest.raises(GapConfigError, match=match):
        build_gap_report(
            tmp_path / "missing.jsonl",
            repo_root=tmp_path,
            axes_config=config,
            signals=_signals(),
        )


def test_cli_exit_codes_and_json_envelope(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_collect(repo_root: object, *, base_ref: str, runner: object = None) -> dict:
        return _signals()

    monkeypatch.setattr("devolaflow.harness.gap.collect_signals", fake_collect)
    root = _scaffold_repo(tmp_path / "repo")
    ledger = _write_ledger(tmp_path / "harness.jsonl")
    output = tmp_path / "gap.json"

    covered_exit = main(
        ["gap", "--ledger", str(ledger), "--repo", str(root), "--output", str(output)]
    )
    report = json.loads(output.read_text(encoding="utf-8"))
    assert covered_exit == 0
    assert output.read_text(encoding="utf-8") == render_evaluation(report)
    assert list(report) == [
        "schema_version",
        "sampled_at",
        "axes",
        "auto_fill_rate",
        "insufficient_slots",
        "summary",
    ]
    assert report["schema_version"] == 1
    assert [axis["id"] for axis in report["axes"]] == list(BUILTIN_GAP_AXES)
    assert all(
        list(axis) == ["id", "builtin", "status", "evidence", "gaps"] for axis in report["axes"]
    )
    assert report["summary"] == {"covered": 6, "partial": 0, "gap": 0}

    gapped_root = _scaffold_repo(tmp_path / "repo-no-baseline", baselines=False)
    gapped_exit = main(["gap", "--ledger", str(ledger), "--repo", str(gapped_root)])
    gapped = json.loads(capsys.readouterr().out)
    assert gapped_exit == 1
    assert {axis["id"]: axis["status"] for axis in gapped["axes"]}["baseline"] == "GAP"

    bad_config = tmp_path / "bad-axes.yaml"
    bad_config.write_text("axes: [unclosed", encoding="utf-8")
    assert (
        main(
            [
                "gap",
                "--ledger",
                str(ledger),
                "--repo",
                str(root),
                "--axes-config",
                str(bad_config),
            ]
        )
        == 2
    )
    assert "harness gap:" in capsys.readouterr().err

    bad_ledger = tmp_path / "bad.jsonl"
    bad_ledger.write_text('{"ts": "2026-08-25T00:00:00+00:00"}\n', encoding="utf-8")
    assert main(["gap", "--ledger", str(bad_ledger), "--repo", str(root)]) == 2
    assert "missing required field(s)" in capsys.readouterr().err


def test_report_is_deterministic_and_loadable_for_comparison(tmp_path: Path) -> None:
    root = _scaffold_repo(tmp_path / "repo")
    (root / "goal.txt").write_text("goal\n", encoding="utf-8")
    ledger = _write_ledger(tmp_path / "harness.jsonl")
    config = _write_config(
        tmp_path / "axes.yaml",
        [
            {"id": "first-axis", "probe": {"kind": "file_exists", "spec": {"path": "goal.txt"}}},
            {
                "id": "second-axis",
                "probe": {"kind": "ledger_query", "spec": {"event": "proposal_applied"}},
            },
        ],
    )

    reports = [
        build_gap_report(ledger, repo_root=root, axes_config=config, signals=_signals())
        for _ in range(2)
    ]
    for report in reports:
        datetime.fromisoformat(report["sampled_at"])
        report.pop("sampled_at")
    assert render_evaluation(reports[0]).encode() == render_evaluation(reports[1]).encode()
    assert [axis["id"] for axis in reports[0]["axes"][6:]] == ["first-axis", "second-axis"]

    frozen = build_gap_report(
        ledger,
        repo_root=root,
        axes_config=config,
        signals=_signals(),
        sampled_at=_TS,
    )
    before = tmp_path / "before.json"
    after = tmp_path / "after.json"
    before.write_text(render_evaluation(frozen), encoding="utf-8")
    after.write_text(render_evaluation(frozen), encoding="utf-8")
    assert load_gap_report(before) == frozen
    assert load_gap_report(after) == load_gap_report(before)


@pytest.mark.parametrize(
    ("document", "match"),
    [
        pytest.param("not json", "invalid gap report JSON", id="not-json"),
        pytest.param("[]", "root must be a mapping", id="root-not-mapping"),
        pytest.param(
            json.dumps({"schema_version": 1}),
            r"missing key\(s\)",
            id="missing-envelope-keys",
        ),
        pytest.param(
            json.dumps(
                {
                    "schema_version": 2,
                    "sampled_at": _TS,
                    "axes": [],
                    "auto_fill_rate": 0.0,
                    "insufficient_slots": [],
                    "summary": {},
                }
            ),
            "schema_version must equal 1",
            id="wrong-schema-version",
        ),
        pytest.param(
            json.dumps(
                {
                    "schema_version": 1,
                    "sampled_at": _TS,
                    "axes": [{"id": "observation", "status": "BOGUS"}],
                    "auto_fill_rate": 0.0,
                    "insufficient_slots": [],
                    "summary": {},
                }
            ),
            "COVERED/PARTIAL/GAP",
            id="invalid-axis-status",
        ),
    ],
)
def test_load_gap_report_rejects_invalid_documents(
    tmp_path: Path,
    document: str,
    match: str,
) -> None:
    path = tmp_path / "report.json"
    path.write_text(document, encoding="utf-8")
    with pytest.raises(GapConfigError, match=match):
        load_gap_report(path)


_AFTER_TS = "2026-08-26T00:00:00+00:00"
_GAP_LEDGER = {"item": "ledger", "reason": "ledger absent"}
_GAP_L1 = {"item": "L1", "reason": "no dispatch telemetry recorded for layer L1"}
_DELTA_KEYS = [
    "schema_version",
    "sampled_at",
    "axis_transitions",
    "auto_fill_rate_delta",
    "resolved_gaps",
    "new_gaps",
    "regressions",
    "summary_delta",
]


def _gap_axis(axis_id: str, status: str, gaps: list[dict] | None = None) -> dict:
    return {"id": axis_id, "builtin": True, "status": status, "evidence": {}, "gaps": gaps or []}


def _envelope(axes: list[dict], *, auto_fill: float = 1.0, sampled_at: str = _TS) -> dict:
    statuses = [axis["status"] for axis in axes]
    return {
        "schema_version": 1,
        "sampled_at": sampled_at,
        "axes": axes,
        "auto_fill_rate": auto_fill,
        "insufficient_slots": [],
        "summary": {
            "covered": statuses.count("COVERED"),
            "partial": statuses.count("PARTIAL"),
            "gap": statuses.count("GAP"),
        },
    }


@pytest.mark.parametrize(
    ("before_axes", "after_axes", "rates", "expected"),
    [
        pytest.param(
            [_gap_axis("observation", "COVERED"), _gap_axis("probe", "COVERED")],
            [_gap_axis("observation", "COVERED"), _gap_axis("probe", "COVERED")],
            (1.0, 1.0),
            {
                "axis_transitions": [
                    {"axis": "observation", "from": "COVERED", "to": "COVERED"},
                    {"axis": "probe", "from": "COVERED", "to": "COVERED"},
                ],
                "auto_fill_rate_delta": 0.0,
                "resolved_gaps": [],
                "new_gaps": [],
                "regressions": [],
                "summary_delta": {"covered": 0, "partial": 0, "gap": 0},
            },
            id="identity-all-unchanged",
        ),
        pytest.param(
            [_gap_axis("observation", "GAP", [_GAP_LEDGER])],
            [_gap_axis("observation", "COVERED")],
            (0.2143, 0.7857),
            {
                "axis_transitions": [{"axis": "observation", "from": "GAP", "to": "COVERED"}],
                "auto_fill_rate_delta": 0.5714,
                "resolved_gaps": [{"axis": "observation", **_GAP_LEDGER}],
                "new_gaps": [],
                "regressions": [],
                "summary_delta": {"covered": 1, "partial": 0, "gap": -1},
            },
            id="upgrade-resolves-verbatim-gap-item",
        ),
        pytest.param(
            [
                _gap_axis("observation", "COVERED"),
                _gap_axis("signal", "PARTIAL", [_GAP_LEDGER]),
            ],
            [
                _gap_axis("observation", "PARTIAL", [_GAP_L1]),
                _gap_axis("signal", "GAP", [_GAP_LEDGER, _GAP_L1]),
            ],
            (1.0, 0.5),
            {
                "axis_transitions": [
                    {"axis": "observation", "from": "COVERED", "to": "PARTIAL"},
                    {"axis": "signal", "from": "PARTIAL", "to": "GAP"},
                ],
                "auto_fill_rate_delta": -0.5,
                "resolved_gaps": [],
                "new_gaps": [
                    {"axis": "observation", **_GAP_L1},
                    {"axis": "signal", **_GAP_L1},
                ],
                "regressions": [
                    {"axis": "observation", "from": "COVERED", "to": "PARTIAL"},
                    {"axis": "signal", "from": "PARTIAL", "to": "GAP"},
                ],
                "summary_delta": {"covered": -1, "partial": 0, "gap": 1},
            },
            id="downgrades-and-new-gap-items",
        ),
        pytest.param(
            [_gap_axis("observation", "COVERED"), _gap_axis("old-axis", "COVERED")],
            [
                _gap_axis("observation", "COVERED"),
                _gap_axis("new-axis", "GAP", [_GAP_LEDGER]),
            ],
            (1.0, 1.0),
            {
                "axis_transitions": [
                    {"axis": "observation", "from": "COVERED", "to": "COVERED"},
                    {"axis": "old-axis", "from": "COVERED", "to": None},
                    {"axis": "new-axis", "from": None, "to": "GAP"},
                ],
                "auto_fill_rate_delta": 0.0,
                "resolved_gaps": [],
                "new_gaps": [{"axis": "new-axis", **_GAP_LEDGER}],
                "regressions": [{"axis": "old-axis", "from": "COVERED", "to": None}],
                "summary_delta": {"covered": -1, "partial": 0, "gap": 1},
            },
            id="newly-tracked-and-no-longer-tracked",
        ),
    ],
)
def test_compare_gap_reports_transition_matrix(
    before_axes: list[dict],
    after_axes: list[dict],
    rates: tuple[float, float],
    expected: dict,
) -> None:
    before = _envelope(before_axes, auto_fill=rates[0])
    after = _envelope(after_axes, auto_fill=rates[1], sampled_at=_AFTER_TS)

    delta = compare_gap_reports(before, after)

    assert list(delta) == _DELTA_KEYS
    assert delta["schema_version"] == 1
    assert delta["sampled_at"] == {"before": _TS, "after": _AFTER_TS}
    for key, value in expected.items():
        assert delta[key] == value, key


def test_render_capability_review_is_deterministic_and_lean() -> None:
    before = _envelope(
        [
            _gap_axis("observation", "GAP", [_GAP_LEDGER]),
            _gap_axis("signal", "COVERED"),
            _gap_axis("old-axis", "PARTIAL", [_GAP_L1]),
        ],
        auto_fill=0.2143,
    )
    after = _envelope(
        [
            _gap_axis("observation", "COVERED"),
            _gap_axis("signal", "PARTIAL", [_GAP_L1]),
            _gap_axis("new-axis", "GAP", [_GAP_LEDGER]),
        ],
        auto_fill=0.7857,
        sampled_at=_AFTER_TS,
    )
    delta = compare_gap_reports(before, after)

    renders = [
        render_capability_review(
            delta,
            before_ref="evidence/harness_gap_before.json",
            after_ref="evidence/harness_gap_after.json",
        )
        for _ in range(2)
    ]

    assert renders[0].encode() == renders[1].encode()
    review = renders[0]
    assert review.startswith("# Harness Capability Review\n")
    assert len(review.encode()) <= 10 * 1024
    sections = [
        "## Sources",
        "## Axis Transitions",
        "## Auto-fill Delta",
        "## Resolved Gaps",
        "## Regressions",
        "## Summary",
    ]
    positions = [review.index(section) for section in sections]
    assert positions == sorted(positions)
    assert f"- before: `evidence/harness_gap_before.json` (sampled_at {_TS})" in review
    assert f"- after: `evidence/harness_gap_after.json` (sampled_at {_AFTER_TS})" in review
    assert "| observation | GAP | COVERED |" in review
    assert "| old-axis | PARTIAL | (untracked) |" in review
    assert "| new-axis | (untracked) | GAP |" in review
    assert "- auto_fill_rate delta: +0.5714" in review
    assert "- `observation` / `ledger`: ledger absent" in review
    assert "Trend-only record" in review and "never gated" in review
    assert "- status downgrade `signal`: COVERED -> PARTIAL" in review
    assert "- no longer tracked `old-axis` (was PARTIAL)" in review
    assert "- new gap `signal` / `L1`: no dispatch telemetry recorded for layer L1" in review
    assert "- covered: +0\n- partial: +0\n- gap: +0" in review


def test_cli_compare_writes_review_and_keeps_exit_semantics(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_collect(repo_root: object, *, base_ref: str, runner: object = None) -> dict:
        return _signals()

    monkeypatch.setattr("devolaflow.harness.gap.collect_signals", fake_collect)
    covered_root = _scaffold_repo(tmp_path / "repo")
    gapped_root = _scaffold_repo(tmp_path / "repo-no-baseline", baselines=False)
    ledger = _write_ledger(tmp_path / "harness.jsonl")
    before_json = tmp_path / "before.json"
    after_json = tmp_path / "after.json"
    review_md = tmp_path / "review.md"

    assert (
        main(
            [
                "gap",
                "--ledger",
                str(ledger),
                "--repo",
                str(gapped_root),
                "--output",
                str(before_json),
            ]
        )
        == 1
    )
    improved_exit = main(
        [
            "gap",
            "--ledger",
            str(ledger),
            "--repo",
            str(covered_root),
            "--output",
            str(after_json),
            "--compare",
            str(before_json),
            "--review-output",
            str(review_md),
        ]
    )
    assert improved_exit == 0
    review = review_md.read_text(encoding="utf-8")
    assert "| baseline | GAP | COVERED |" in review
    assert f"- before: `{before_json.as_posix()}`" in review
    assert f"- after: `{after_json.as_posix()}`" in review
    assert "- `baseline` / `harness_baseline_*.json`:" in review
    assert "- none" in review
    before_report = json.loads(before_json.read_text(encoding="utf-8"))
    after_report = json.loads(after_json.read_text(encoding="utf-8"))
    assert before_report["sampled_at"] in review
    assert after_report["sampled_at"] in review

    regressed_exit = main(
        [
            "gap",
            "--ledger",
            str(ledger),
            "--repo",
            str(gapped_root),
            "--output",
            str(tmp_path / "after2.json"),
            "--compare",
            str(after_json),
            "--review-output",
            str(tmp_path / "review2.md"),
        ]
    )
    assert regressed_exit == 1
    regressed = (tmp_path / "review2.md").read_text(encoding="utf-8")
    assert "- status downgrade `baseline`: COVERED -> GAP" in regressed

    capsys.readouterr()
    bad_before = tmp_path / "bad.json"
    bad_before.write_text("not json", encoding="utf-8")
    after3_json = tmp_path / "after3.json"
    review3_md = tmp_path / "review3.md"
    malformed_exit = main(
        [
            "gap",
            "--ledger",
            str(ledger),
            "--repo",
            str(covered_root),
            "--output",
            str(after3_json),
            "--compare",
            str(bad_before),
            "--review-output",
            str(review3_md),
        ]
    )
    assert malformed_exit == 2
    stderr = capsys.readouterr().err
    assert "harness gap:" in stderr and "invalid gap report JSON" in stderr
    assert after3_json.exists()
    assert not review3_md.exists()


@pytest.mark.parametrize(
    "extra_argv",
    [
        pytest.param(["--compare", "before.json"], id="compare-without-review-output"),
        pytest.param(["--review-output", "review.md"], id="review-output-without-compare"),
    ],
)
def test_cli_compare_flags_must_be_paired(
    capsys: pytest.CaptureFixture[str],
    extra_argv: list[str],
) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["gap", "--ledger", "harness.jsonl", *extra_argv])
    assert excinfo.value.code == 2
    assert "--compare and --review-output must be given together" in capsys.readouterr().err
