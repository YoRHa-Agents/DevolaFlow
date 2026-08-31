"""Contract tests for the bounded local CLI probe runner."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

from devolaflow.harness.__main__ import main
from devolaflow.harness.cli_probe import (
    PROBE_HOSTS,
    SUPPORTED_CHANNELS,
    ChannelConfig,
    CLIProbeRunner,
    ProbeError,
    build_probe_metadata,
    build_probe_spec,
    plan_probe_matrix,
)


def _spec(tmp_path: Path, **overrides: object):
    values = {
        "channel": "claude",
        "task_class": "read-only",
        "arm": "skill-on",
        "seed": "70000001",
        "replicate": 1,
        "prompt": "inspect the repository",
        "generated_at": "2026-08-29T00:00:00+00:00",
        "output_path": "artifacts/probe.json",
        "salt": "70000001",
    }
    values.update(overrides)
    return build_probe_spec(**values)


def _commands() -> dict[str, ChannelConfig]:
    return {
        channel: ChannelConfig(channel, f"fake-{channel}", ("--prompt", "{prompt}"))
        for channel in SUPPORTED_CHANNELS
    }


def test_success_captures_usage_skill_timing_and_redacts_diagnostics(tmp_path: Path) -> None:
    calls: list[dict] = []
    spec = _spec(tmp_path)

    def fake_runner(argv, **kwargs):
        calls.append({"argv": argv, **kwargs})
        canary = re.search(r"DF-SKILL-CANARY-[A-Za-z0-9]+", argv[-1]).group(0)
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout=json.dumps(
                {
                    "usage": {"input_tokens": 12, "output_tokens": 7},
                    "skill_canary_echo": canary,
                    "message": "ok",
                }
            ),
            stderr="api_key=secret-value",
        )

    result = CLIProbeRunner(repo_root=tmp_path, commands=_commands(), runner=fake_runner).run(spec)

    assert result["status"] == "PASS"
    assert result["execution"]["exit_code"] == 0
    assert result["token_usage"]["input_tokens"] == 12
    assert result["token_usage"]["output_tokens"] == 7
    assert result["token_usage"]["total_tokens"] == 19
    assert result["token_usage"]["status"] == "AVAILABLE"
    assert result["token_usage"]["usage_observation"] == {
        "status": "AVAILABLE",
        "reason": "usage_observed",
        "source_path": "usage",
    }
    assert result["token_usage"]["cache_usage"] == {
        "cache_read": {"tokens": None, "status": "INSUFFICIENT", "source_path": None},
        "cache_creation": {"tokens": None, "status": "INSUFFICIENT", "source_path": None},
        "cache_write": {"tokens": None, "status": "INSUFFICIENT", "source_path": None},
        "uncached_input": {
            "tokens": 12,
            "status": "AVAILABLE",
            "source_path": "usage.input_tokens",
        },
    }
    assert result["skill_loaded"]["value"] is True
    assert result["skill_loaded"]["observed"] is True
    assert result["skill_loaded"]["status"] == "AVAILABLE"
    assert result["skill_loaded"]["provenance"] == "probe-runtime"
    assert result["skill_loaded"]["host"] == "claude"
    assert result["skill_loaded"]["contract_status"] == "designed"
    assert result["skill_loaded"]["hsc_validation"]["status"] == "INSUFFICIENT"
    assert result["skill_canary"]["status"] == "AVAILABLE"
    assert result["skill_canary"]["source_path"] == "skill_canary_echo"
    assert result["execution"]["stderr_summary"] == "api_key=<redacted>"
    assert result["stages"]["run"]["wall_time_seconds"] >= 0
    assert calls[0]["shell"] is False
    assert calls[0]["timeout"] == 120.0
    assert json.loads((tmp_path / "artifacts/probe.json").read_text())["status"] == "PASS"


def test_unavailable_cli_is_structured_insufficient(tmp_path: Path) -> None:
    def unavailable(*_args, **_kwargs):
        raise FileNotFoundError("fake-cli not found")

    result = CLIProbeRunner(repo_root=tmp_path, commands=_commands(), runner=unavailable).run(
        _spec(tmp_path)
    )

    assert result["status"] == "INSUFFICIENT"
    assert result["execution"]["reason"] == "unavailable"
    assert result["execution"]["exit_code"] is None
    assert "fake-cli not found" in result["execution"]["stderr_summary"]
    assert result["skill_loaded"]["value"] is None
    assert result["skill_loaded"]["status"] == "INSUFFICIENT"
    assert result["skill_loaded"]["hsc_validation"]["status"] == "INSUFFICIENT"


def test_timeout_preserves_partial_diagnostics(tmp_path: Path) -> None:
    def timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(
            cmd=["fake-claude"], timeout=0.1, output="partial", stderr="still running"
        )

    result = CLIProbeRunner(repo_root=tmp_path, commands=_commands(), runner=timeout).run(
        _spec(tmp_path, timeout_seconds=0.1)
    )

    assert result["status"] == "INSUFFICIENT"
    assert result["execution"]["reason"] == "timeout"
    assert result["execution"]["stdout_summary"] == "partial"
    assert result["execution"]["stderr_summary"] == "still running"
    assert result["execution"]["wall_time_seconds"] >= 0
    assert result["execution"]["timeout_phase"] == "probe"
    assert result["execution"]["termination_reason"] == "timeout_expired"
    assert result["execution"]["started_at"] is not None
    assert result["execution"]["finished_at"] is not None
    assert result["execution"]["partial_output_summary"] == {
        "stdout": "partial",
        "stderr": "still running",
    }


def test_nonzero_exit_is_fail_and_tokens_remain_insufficient(tmp_path: Path) -> None:
    def failed(argv, **_kwargs):
        return subprocess.CompletedProcess(argv, 17, stdout="not json", stderr="bad input")

    result = CLIProbeRunner(repo_root=tmp_path, commands=_commands(), runner=failed).run(
        _spec(tmp_path)
    )

    assert result["status"] == "FAIL"
    assert result["execution"]["reason"] == "nonzero_exit"
    assert result["execution"]["exit_code"] == 17
    assert result["token_usage"]["status"] == "INSUFFICIENT"
    assert result["skill_loaded"]["status"] == "INSUFFICIENT"


def test_metadata_is_stable_and_paths_are_relative(tmp_path: Path) -> None:
    first = build_probe_metadata(_spec(tmp_path), repo_root=tmp_path)
    second = build_probe_metadata(_spec(tmp_path), repo_root=tmp_path)

    assert first == second
    assert first["run_id"].startswith("probe-")
    assert first["salt"] == "70000001"
    assert first["output_path"] == "artifacts/probe.json"
    assert not first["output_path"].startswith("/")


def test_matrix_has_400_ordered_specs_without_execution() -> None:
    specs = plan_probe_matrix(10, seed="matrix-seed")

    assert len(specs) == 400
    assert specs[0].as_dict()["task_class"] == "read-only"
    assert specs[0].as_dict()["channel"] == "claude"
    assert specs[0].as_dict()["arm"] == "skill-off"
    assert specs[0].replicate == 1
    assert specs[-1].as_dict()["task_class"] == "recovery"
    assert specs[-1].as_dict()["channel"] == "copilot"
    assert specs[-1].as_dict()["arm"] == "skill-on"
    assert specs[-1].replicate == 10


@pytest.mark.parametrize(
    "kwargs",
    [
        {"replicates": 0},
        {"replicates": -1},
        {"replicates": 1, "channels": ("claude",)},
        {"replicates": 1, "task_classes": ("read-only",)},
        {"replicates": 1, "arms": ("skill-on", "unknown")},
    ],
)
def test_matrix_rejects_invalid_dimensions(kwargs: dict) -> None:
    kwargs = {"seed": "s", **kwargs}
    with pytest.raises(ProbeError):
        plan_probe_matrix(**kwargs)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("channel", "shell; injection"),
        ("task_class", "unknown"),
        ("arm", "unknown"),
        ("timeout_seconds", 0),
        ("timeout_seconds", 3_601),
    ],
)
def test_spec_rejects_invalid_values(field: str, value: object) -> None:
    with pytest.raises(ProbeError):
        build_probe_spec(
            channel=value if field == "channel" else "claude",
            task_class=value if field == "task_class" else "read-only",
            arm=value if field == "arm" else "skill-on",
            seed="s",
            replicate=1,
            prompt="p",
            timeout_seconds=value if field == "timeout_seconds" else 1,
        )


def test_cli_plan_is_dry_run_and_writes_machine_readable_json(tmp_path: Path) -> None:
    output = tmp_path / "plan.json"

    assert (
        main(
            [
                "probe-plan",
                "--replicates",
                "10",
                "--seed",
                "70000001",
                "--output",
                str(output),
            ]
        )
        == 0
    )
    plan = json.loads(output.read_text())
    assert plan["status"] == "PLAN"
    assert plan["count"] == 400


def test_command_template_uses_argv_without_shell(tmp_path: Path) -> None:
    observed: list[list[str]] = []

    def fake_runner(argv, **kwargs):
        observed.append(argv)
        assert kwargs["shell"] is False
        return subprocess.CompletedProcess(argv, 0, stdout="{}", stderr="")

    config = ChannelConfig("claude", "fake-cli", ("--prompt", "{prompt}"))
    CLIProbeRunner(repo_root=tmp_path, commands={"claude": config}, runner=fake_runner).run(
        _spec(tmp_path, prompt="value; touch SHOULD_NOT_EXIST")
    )

    assert observed[0][:2] == ["fake-cli", "--prompt"]
    assert observed[0][2].startswith("value; touch SHOULD_NOT_EXIST")
    assert "DF-SKILL-CANARY-" in observed[0][2]
    assert not (tmp_path / "SHOULD_NOT_EXIST").exists()


def test_new_channels_map_to_existing_hosts_and_parse_jsonl_evidence(tmp_path: Path) -> None:
    assert PROBE_HOSTS["cursor-agent"] == "cursor"
    assert PROBE_HOSTS["copilot"] == "copilot"
    calls: list[dict] = []

    def fake_runner(argv, **kwargs):
        calls.append({"argv": argv, **kwargs})
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout=(
                '{"message":"stream"}\n'
                '{"usage":{"prompt_tokens":8,"completion_tokens":3},'
                '"metadata":{"skill_loaded":false}}\n'
            ),
            stderr="token=secret-value",
        )

    for channel in ("cursor-agent", "copilot"):
        result = CLIProbeRunner(
            repo_root=tmp_path,
            commands={channel: ChannelConfig(channel, f"fake-{channel}", ("{prompt}",))},
            runner=fake_runner,
        ).run(_spec(tmp_path, channel=channel, output_path=f"{channel}.json"))
        assert result["status"] == "PASS"
        assert result["measurement"] == {"host": PROBE_HOSTS[channel], "channel": channel}
        assert result["token_usage"]["total_tokens"] == 11
        assert result["skill_loaded"]["value"] is None
        assert result["skill_loaded"]["status"] == "INSUFFICIENT"
        assert result["execution"]["stderr_summary"] == "token=<redacted>"

    assert all(call["shell"] is False for call in calls)


def test_success_without_explicit_usage_or_skill_stays_insufficient(tmp_path: Path) -> None:
    def fake_runner(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 0, stdout="completed in 2 seconds", stderr="")

    result = CLIProbeRunner(
        repo_root=tmp_path,
        commands={"copilot": ChannelConfig("copilot", "fake-copilot", ("{prompt}",))},
        runner=fake_runner,
    ).run(_spec(tmp_path, channel="copilot"))

    assert result["status"] == "PASS"
    assert result["token_usage"]["input_tokens"] is None
    assert result["token_usage"]["output_tokens"] is None
    assert result["token_usage"]["total_tokens"] is None
    assert result["token_usage"]["status"] == "INSUFFICIENT"
    assert all(
        observation["tokens"] is None
        and observation["status"] == "INSUFFICIENT"
        and observation["source_path"] is None
        for observation in result["token_usage"]["cache_usage"].values()
    )
    assert result["skill_loaded"]["value"] is None
    assert result["skill_loaded"]["status"] == "INSUFFICIENT"
    assert result["token_usage"]["usage_observation"]["reason"] == "parser_mismatch"


@pytest.mark.parametrize(
    ("channel", "stdout", "expected"),
    [
        pytest.param(
            "claude",
            json.dumps(
                {
                    "response": {
                        "usage": {
                            "input_tokens": 21,
                            "output_tokens": 5,
                            "cache_read_input_tokens": 8,
                            "cache_creation_input_tokens": 3,
                        }
                    }
                }
            ),
            {
                "cache_read": (8, "response.usage.cache_read_input_tokens"),
                "cache_creation": (3, "response.usage.cache_creation_input_tokens"),
                "cache_write": (None, None),
                "uncached_input": (21, "response.usage.input_tokens"),
            },
            id="claude-nested-json",
        ),
        pytest.param(
            "codex",
            (
                '{"type":"message","message":"running"}\n'
                '{"type":"turn.completed","response":{"usage":{"input_tokens":34,'
                '"output_tokens":6,"cached_input_tokens":13,'
                '"input_tokens_details":{"cached_tokens":12},'
                '"uncached_input_tokens":21}}}\n'
            ),
            {
                "cache_read": (13, "response.usage.cached_input_tokens"),
                "cache_creation": (None, None),
                "cache_write": (None, None),
                "uncached_input": (21, "response.usage.uncached_input_tokens"),
            },
            id="codex-nested-jsonl",
        ),
        pytest.param(
            "kimi",
            json.dumps(
                {
                    "result": {
                        "usage": {
                            "input_tokens": 55,
                            "output_tokens": 2,
                            "cache_read_input_tokens": 44,
                            "cache_creation_input_tokens": 11,
                        }
                    }
                }
            ),
            {
                "cache_read": (None, None),
                "cache_creation": (None, None),
                "cache_write": (None, None),
                "uncached_input": (None, None),
            },
            id="kimi-unsupported-cache-paths",
        ),
    ],
)
def test_provider_cache_usage_preserves_aliases_paths_and_unsupported_kimi(
    tmp_path: Path,
    channel: str,
    stdout: str,
    expected: dict[str, tuple[int | None, str | None]],
) -> None:
    def fake_runner(argv, **_kwargs):
        return subprocess.CompletedProcess(argv, 0, stdout=stdout, stderr="")

    result = CLIProbeRunner(
        repo_root=tmp_path,
        commands={channel: ChannelConfig(channel, f"fake-{channel}", ("{prompt}",))},
        runner=fake_runner,
    ).run(_spec(tmp_path, channel=channel, output_path=f"{channel}.json"))

    usage = result["token_usage"]
    expected_input = {"claude": 21, "codex": 34, "kimi": 55}[channel]
    assert usage["input_tokens"] == expected_input
    assert usage["total_tokens"] is not None
    for component, (tokens, source_path) in expected.items():
        assert usage["cache_usage"][component] == {
            "tokens": tokens,
            "status": "AVAILABLE" if tokens is not None else "INSUFFICIENT",
            "source_path": source_path,
        }


def test_provider_cache_usage_distinguishes_explicit_zero_missing_and_malformed(
    tmp_path: Path,
) -> None:
    stdout = json.dumps(
        {
            "event": {
                "usage": {
                    "input_tokens": 10,
                    "output_tokens": 2,
                    "cache_read_input_tokens": 0,
                    "cache_creation_input_tokens": "bad",
                }
            }
        }
    )

    def fake_runner(argv, **_kwargs):
        return subprocess.CompletedProcess(argv, 0, stdout=stdout, stderr="")

    result = CLIProbeRunner(
        repo_root=tmp_path,
        commands={"claude": ChannelConfig("claude", "fake-claude", ("{prompt}",))},
        runner=fake_runner,
    ).run(_spec(tmp_path, output_path="cache.json"))

    cache = result["token_usage"]["cache_usage"]
    assert cache["cache_read"] == {
        "tokens": 0,
        "status": "AVAILABLE",
        "source_path": "event.usage.cache_read_input_tokens",
    }
    assert cache["cache_creation"] == {
        "tokens": None,
        "status": "INSUFFICIENT",
        "source_path": "event.usage.cache_creation_input_tokens",
    }
    assert cache["cache_write"] == {
        "tokens": None,
        "status": "INSUFFICIENT",
        "source_path": None,
    }


def test_malformed_nested_usage_remains_insufficient(tmp_path: Path) -> None:
    def fake_runner(argv, **_kwargs):
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout=json.dumps({"response": {"usage": ["not", "a", "mapping"]}}),
            stderr="",
        )

    result = CLIProbeRunner(
        repo_root=tmp_path,
        commands={"codex": ChannelConfig("codex", "fake-codex", ("{prompt}",))},
        runner=fake_runner,
    ).run(_spec(tmp_path, channel="codex", output_path="malformed.json"))

    assert result["token_usage"]["input_tokens"] is None
    assert result["token_usage"]["output_tokens"] is None
    assert result["token_usage"]["total_tokens"] is None
    assert result["token_usage"]["status"] == "INSUFFICIENT"
    assert all(
        value == {"tokens": None, "status": "INSUFFICIENT", "source_path": None}
        for value in result["token_usage"]["cache_usage"].values()
    )


def test_kimi_stream_json_distinguishes_missing_usage_from_parser_mismatch(
    tmp_path: Path,
) -> None:
    stdout = "\n".join(
        [
            '{"role":"meta","type":"system.version","version":"0.39.1"}',
            '{"role":"assistant","tool_calls":[]}',
            '{"role":"tool","content":"ok"}',
            '{"role":"assistant","content":"done"}',
            '{"role":"meta","type":"session.resume_hint","session_id":"redacted"}',
        ]
    )

    def fake_runner(argv, **_kwargs):
        return subprocess.CompletedProcess(argv, 0, stdout=stdout, stderr="")

    result = CLIProbeRunner(
        repo_root=tmp_path,
        commands={"kimi": ChannelConfig("kimi", "fake-kimi", ("{prompt}",))},
        runner=fake_runner,
        telemetry_ledger=None,
    ).run(_spec(tmp_path, channel="kimi", output_path="kimi.json"))

    assert result["status"] == "PASS"
    assert result["token_usage"]["status"] == "INSUFFICIENT"
    assert result["token_usage"]["usage_observation"] == {
        "status": "INSUFFICIENT",
        "reason": "missing_usage",
        "source_path": "$",
    }
    assert result["skill_loaded"]["value"] is None
    assert result["skill_loaded"]["status"] == "INSUFFICIENT"


def test_skill_canary_mismatch_and_missing_echo_are_not_negative_proof(tmp_path: Path) -> None:
    def mismatched(argv, **_kwargs):
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout=json.dumps({"skill_canary_echo": "DF-SKILL-CANARY-wrong"}),
            stderr="",
        )

    mismatch = CLIProbeRunner(
        repo_root=tmp_path,
        commands={"claude": ChannelConfig("claude", "fake-claude", ("{prompt}",))},
        runner=mismatched,
        telemetry_ledger=None,
    ).run(_spec(tmp_path, output_path="mismatch.json"))
    assert mismatch["skill_canary"]["status"] == "INSUFFICIENT"
    assert mismatch["skill_canary"]["reason"] == "canary_mismatch"
    assert mismatch["skill_loaded"]["value"] is None

    def missing(argv, **_kwargs):
        return subprocess.CompletedProcess(argv, 0, stdout="{}", stderr="")

    absent = CLIProbeRunner(
        repo_root=tmp_path,
        commands={"claude": ChannelConfig("claude", "fake-claude", ("{prompt}",))},
        runner=missing,
        telemetry_ledger=None,
    ).run(_spec(tmp_path, output_path="missing.json"))
    assert absent["skill_canary"]["status"] == "INSUFFICIENT"
    assert absent["skill_canary"]["reason"] == "missing_canary_echo"
    assert absent["skill_loaded"]["value"] is None
