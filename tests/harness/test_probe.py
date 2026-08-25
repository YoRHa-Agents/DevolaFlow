"""Bounded model-probe contract and CLI tests."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from devolaflow.harness.__main__ import main
from devolaflow.harness.fixtures import load_harness_fixture
from devolaflow.harness.probe import (
    ProbeModel,
    build_probe_prompt,
    load_probe_model_table,
    run_probe,
    score_probe_response,
)
from devolaflow.llm_client import LLMClient, LLMResponse

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "harness"
PROFILE_KEYS = {
    "schema_version",
    "status",
    "provider",
    "model",
    "cycle",
    "probed_at",
    "model_version_echo",
    "probe_set_hash",
    "fold_mode",
    "baseline_profile",
    "calls",
    "tokens_spent",
    "guard_compliance",
    "schema_validity",
    "fold_delta",
    "scenarios",
}


@pytest.mark.parametrize(
    ("case", "expected_schema", "expected_guard"),
    [
        ("valid", 1.0, 1.0),
        ("nested_forbidden", 0.0, 1.0),
        ("duplicate_guard", 0.0, 4 / 5),
        ("missing_literal", 1.0, 4 / 5),
        ("fenced", 0.0, 1 / 5),
    ],
)
def test_prompt_and_recursive_response_scoring(
    case: str,
    expected_schema: float,
    expected_guard: float,
) -> None:
    fixture = load_harness_fixture(FIXTURE_DIR / "hierarchy_trivial_collapse.yaml")
    prompt = build_probe_prompt(fixture)
    assert "```" not in prompt
    assert "exactly one unfenced YAML mapping" in prompt
    response = LLMClient(provider="mock", model="mock-probe").complete(prompt)
    report = yaml.safe_load(response.text)

    if case == "nested_forbidden":
        report["artifacts"][0]["quality_score"] = 100
    elif case == "duplicate_guard":
        report["ac_results"].append(dict(report["ac_results"][0]))
    elif case in {"missing_literal", "fenced"}:
        report["artifacts"][0]["delta"] = "INLINE"

    rendered = yaml.safe_dump(report, sort_keys=False)
    if case == "fenced":
        rendered = f"```yaml\n{rendered}```\n"
    score = score_probe_response(fixture, rendered)
    assert score["schema_validity"] == expected_schema
    assert score["guard_compliance"] == pytest.approx(expected_guard)


@pytest.mark.parametrize("fixture_name", ["model_tier_advisory_fold.yaml"])
def test_run_probe_profiles_statuses_baseline_and_no_key(
    fixture_name: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fixture = load_harness_fixture(FIXTURE_DIR / fixture_name)
    full_path = tmp_path / "full.yaml"
    full = run_probe(
        [fixture],
        provider="mock",
        model="mock-probe",
        cycle="v16.0.0",
        fold_mode="full",
        output=full_path,
        probed_at="2026-08-25T00:00:00+00:00",
    )
    assert set(full) == PROFILE_KEYS
    assert full["status"] == "PASS"
    assert full["calls"] == {"attempted": 1, "succeeded": 1, "failed": 0}
    assert full["guard_compliance"] == full["schema_validity"] == 1.0
    assert full["tokens_spent"] > 0
    assert yaml.safe_load(full_path.read_text(encoding="utf-8")) == full

    folded = run_probe(
        [fixture],
        provider="mock",
        model="mock-probe",
        cycle="v16.0.0",
        baseline_profile=full_path,
        output=tmp_path / "folded.yaml",
        probed_at="2026-08-25T00:00:01+00:00",
    )
    assert folded["status"] == "PASS"
    assert folded["fold_delta"] == 0.0
    assert folded["baseline_profile"] == str(full_path)

    fail_client = LLMClient(
        provider="mock",
        model="mock-probe",
        mock_handler=lambda _prompt, model: LLMResponse(
            text="{}\n",
            model=model,
            latency_ms=0.0,
            tokens_in=1,
            tokens_out=1,
            error=None,
        ),
    )
    failed = run_probe(
        [fixture],
        provider="mock",
        model="mock-probe",
        cycle="v16.0.0",
        client=fail_client,
        output=tmp_path / "failed.yaml",
    )
    assert failed["status"] == "FAIL"
    assert failed["calls"] == {"attempted": 1, "succeeded": 1, "failed": 0}

    partial_client = LLMClient(
        provider="mock",
        model="mock-probe",
        mock_handler=lambda _prompt, model: LLMResponse(
            text="",
            model=model,
            latency_ms=0.0,
            tokens_in=0,
            tokens_out=0,
            error="rate_limit",
        ),
    )
    partial = run_probe(
        [fixture],
        provider="mock",
        model="mock-probe",
        cycle="v16.0.0",
        client=partial_client,
        output=tmp_path / "partial.yaml",
    )
    assert partial["status"] == "PARTIAL"
    assert partial["calls"] == {"attempted": 1, "succeeded": 0, "failed": 1}
    assert partial["scenarios"][0]["failure_mode"] == "rate_limit"

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    real_client = LLMClient(provider="openai", model="gpt-test")
    monkeypatch.setattr(
        real_client,
        "complete",
        lambda _prompt: pytest.fail("missing-key probe must perform zero calls"),
    )
    skipped = run_probe(
        [fixture],
        provider="openai",
        model="gpt-test",
        cycle="v16.0.0",
        client=real_client,
        output=tmp_path / "skipped.yaml",
    )
    assert skipped["status"] == "SKIPPED_NO_KEY"
    assert skipped["calls"] == {"attempted": 0, "succeeded": 0, "failed": 0}
    assert skipped["tokens_spent"] == 0
    assert skipped["guard_compliance"] is skipped["schema_validity"] is None
    assert skipped["model_version_echo"] is None
    assert skipped["scenarios"][0]["failure_mode"] == "fallback_disabled"

    mismatched = dict(full)
    mismatched["cycle"] = "v15.9.0"
    mismatch_path = tmp_path / "mismatch.yaml"
    mismatch_path.write_text(yaml.safe_dump(mismatched), encoding="utf-8")
    with pytest.raises(ValueError, match="does not match current probe: cycle"):
        run_probe(
            [fixture],
            provider="mock",
            model="mock-probe",
            cycle="v16.0.0",
            baseline_profile=mismatch_path,
            output=tmp_path / "must-not-write.yaml",
        )

    mock_output = tmp_path / "mock.yaml"
    assert (
        main(
            [
                "probe",
                "--provider",
                "mock",
                "--model",
                "mock-probe",
                "--cycle",
                "v16.0.0",
                "--fixtures",
                str(FIXTURE_DIR),
                "--output",
                str(mock_output),
            ]
        )
        == 0
    )
    profile = yaml.safe_load(mock_output.read_text(encoding="utf-8"))
    assert profile["status"] == "PASS"
    assert profile["calls"] == {"attempted": 10, "succeeded": 10, "failed": 0}
    assert capsys.readouterr().out == "harness probe: PASS\n"

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    skipped_output = tmp_path / "skipped.yaml"
    assert (
        main(
            [
                "probe",
                "--provider",
                "anthropic",
                "--model",
                "claude-test",
                "--cycle",
                "v16.0.0",
                "--fixtures",
                str(FIXTURE_DIR),
                "--max-tokens",
                "2000",
                "--timeout",
                "30",
                "--output",
                str(skipped_output),
            ]
        )
        == 2
    )
    skipped = yaml.safe_load(skipped_output.read_text(encoding="utf-8"))
    assert skipped["status"] == "SKIPPED_NO_KEY"
    assert skipped["calls"]["attempted"] == 0
    assert capsys.readouterr().out == "harness probe: SKIPPED_NO_KEY\n"


# ---------------------------------------------------------------------------
# v17.0.0 R5 (D-R5-2) — meta.probe_models config-table sweep.
# ---------------------------------------------------------------------------


def _write_probe_profiles(path: Path, probe_models: object) -> Path:
    meta: dict = {"budget_hard_cap_tokens": 8000}
    if probe_models is not None:
        meta["probe_models"] = probe_models
    path.write_text(yaml.safe_dump({"meta": meta}), encoding="utf-8")
    return path


def test_load_probe_model_table_dark_configured_and_malformed(tmp_path: Path) -> None:
    """Absent key → empty tuple; declared entries load; malformed raise (S-5)."""
    assert load_probe_model_table(_write_probe_profiles(tmp_path / "dark.yaml", None)) == ()
    # The SHIPPED config declares no table — the extension point ships dark.
    assert load_probe_model_table() == ()

    configured = _write_probe_profiles(
        tmp_path / "configured.yaml",
        [
            {"provider": "mock", "model": "mock-probe"},
            {"provider": "openai", "model": "gpt-future"},
        ],
    )
    table = load_probe_model_table(configured)
    assert table == (
        ProbeModel(provider="mock", model="mock-probe"),
        ProbeModel(provider="openai", model="gpt-future"),
    )

    for malformed in (
        [],
        "mock",
        [{"provider": "mock"}],
        [{"provider": "mock", "model": "m", "extra": 1}],
        [{"provider": "unknown", "model": "m"}],
        [{"provider": "mock", "model": ""}],
        [{"provider": "mock", "model": 7}],
    ):
        with pytest.raises(ValueError, match="probe_models"):
            load_probe_model_table(_write_probe_profiles(tmp_path / "bad.yaml", malformed))


def test_probe_cli_sweeps_configured_model_table(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Omitting --provider/--model sweeps the table, one profile per model.

    Per-model artifact names derive from the single ``--output`` argument
    via the shared filename sanitizer; the exit code is the worst per-model
    verdict under the unchanged single-model mapping.
    """
    import devolaflow.task_adaptive_selector as selector

    configured = _write_probe_profiles(
        tmp_path / "profiles.yaml",
        [
            {"provider": "mock", "model": "mock-probe"},
            {"provider": "mock", "model": "mock/alt:v2"},
        ],
    )
    monkeypatch.setattr(selector, "PROFILES_PATH", configured)

    output = tmp_path / "sweep.yaml"
    assert (
        main(
            [
                "probe",
                "--cycle",
                "v17.0.0",
                "--fixtures",
                str(FIXTURE_DIR),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    assert capsys.readouterr().out == (
        "harness probe [mock:mock-probe]: PASS\nharness probe [mock:mock/alt:v2]: PASS\n"
    )
    first = yaml.safe_load((tmp_path / "sweep__mock__mock-probe.yaml").read_text("utf-8"))
    second = yaml.safe_load((tmp_path / "sweep__mock__mock_alt_v2.yaml").read_text("utf-8"))
    assert set(first) == set(second) == PROFILE_KEYS
    assert first["model"] == "mock-probe"
    assert second["model"] == "mock/alt:v2"
    assert not output.exists()

    # Worst-verdict exit aggregation: a keyless real provider joins → 2.
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    mixed = _write_probe_profiles(
        tmp_path / "mixed.yaml",
        [
            {"provider": "mock", "model": "mock-probe"},
            {"provider": "openai", "model": "gpt-future"},
        ],
    )
    monkeypatch.setattr(selector, "PROFILES_PATH", mixed)
    assert (
        main(
            [
                "probe",
                "--cycle",
                "v17.0.0",
                "--fixtures",
                str(FIXTURE_DIR),
                "--output",
                str(tmp_path / "mixed-sweep.yaml"),
            ]
        )
        == 2
    )
    assert capsys.readouterr().out == (
        "harness probe [mock:mock-probe]: PASS\nharness probe [openai:gpt-future]: SKIPPED_NO_KEY\n"
    )


def test_probe_cli_errors_without_model_or_table(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """S-5 explicit errors: empty table and mixed flag usage exit 2 loudly."""
    import devolaflow.task_adaptive_selector as selector

    dark = _write_probe_profiles(tmp_path / "dark.yaml", None)
    monkeypatch.setattr(selector, "PROFILES_PATH", dark)

    assert main(["probe", "--cycle", "v17.0.0", "--fixtures", str(FIXTURE_DIR)]) == 2
    assert "meta.probe_models is not configured" in capsys.readouterr().err

    assert (
        main(
            [
                "probe",
                "--provider",
                "mock",
                "--cycle",
                "v17.0.0",
                "--fixtures",
                str(FIXTURE_DIR),
            ]
        )
        == 2
    )
    assert "BOTH --provider and --model" in capsys.readouterr().err
