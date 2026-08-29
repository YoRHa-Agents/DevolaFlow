"""Real local-CLI calibration matrix execution and ROI reporting.

The calibration layer intentionally treats the existing CLI probe runner as
the only subprocess boundary.  It plans the canonical matrix first, records
one artifact per planned spec, and never turns missing telemetry into a
synthetic cost or quality observation.
"""

from __future__ import annotations

import json
import subprocess
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, Final

from devolaflow.harness.calibration_aggregation import aggregate_calibration_results
from devolaflow.harness.calibration_matrix import (
    CALIBRATION_SCHEMA_VERSION,
    CalibrationError,
    CommandRunner,
    _calibration_run_id,
    _preflight_channel,
    _relative_path,
    _task_prompt,
    _timestamp,
    _validate_dimensions,
)
from devolaflow.harness.calibration_report import render_calibration_report
from devolaflow.harness.cli_probe import (
    DEFAULT_TIMEOUT_SECONDS,
    SUPPORTED_CHANNELS,
    TASK_CLASSES,
    ChannelConfig,
    CLIProbeRunner,
    ProbeSpec,
    build_probe_spec,
    load_channel_configs,
    plan_probe_matrix,
)

DEFAULT_REPLICATES: Final[int] = 10
DEFAULT_TOTAL_TIMEOUT_SECONDS: Final[float] = 3_600.0
DEFAULT_OUTPUT_DIR: Final[str] = ".local/research"
DEFAULT_RAW_OUTPUT_DIR: Final[str] = ".local/telemetry/cli-probes/v21.1.0"
DEFAULT_CYCLE: Final[str] = "v21.1.0"
AUTH_FAILURE_MARKERS: Final[tuple[str, ...]] = (
    "auth",
    "unauthorized",
    "not logged",
    "login required",
    "api key",
    "permission denied",
)


def _auth_failure(result: Mapping[str, Any]) -> bool:
    execution = result.get("execution")
    if not isinstance(execution, Mapping) or execution.get("reason") != "nonzero_exit":
        return False
    diagnostic = str(execution.get("stderr_summary", "")).lower()
    return any(marker in diagnostic for marker in AUTH_FAILURE_MARKERS)


class CalibrationRunner:
    """Run a canonical, serial CLI calibration matrix."""

    def __init__(
        self,
        *,
        repo_root: str | Path = ".",
        commands: Mapping[str, ChannelConfig] | None = None,
        runner: CommandRunner = subprocess.run,
    ) -> None:
        self.repo_root = Path(repo_root).resolve()
        if not self.repo_root.is_dir():
            raise CalibrationError(f"repo_root is not a directory: {repo_root}")
        self.runner = runner
        self.commands = load_channel_configs()
        if commands is not None:
            self.commands.update(commands)

    def plan(
        self,
        *,
        seed: str,
        salt: int | float | str | None,
        replicates: int = DEFAULT_REPLICATES,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        channels: Sequence[str] = SUPPORTED_CHANNELS,
        arms: Sequence[str] = ("skill-off", "skill-on"),
        task_classes: Sequence[str] = TASK_CLASSES,
        prompt_prefix: str = "",
        generated_at: str | None = None,
        raw_output_dir: str | Path = DEFAULT_RAW_OUTPUT_DIR,
    ) -> tuple[ProbeSpec, ...]:
        resolved_channels, resolved_arms, resolved_classes = _validate_dimensions(
            channels=channels,
            arms=arms,
            task_classes=task_classes,
        )
        generated = _timestamp(generated_at)
        canonical = plan_probe_matrix(
            replicates,
            seed=seed,
            channels=SUPPORTED_CHANNELS,
            task_classes=TASK_CLASSES,
            arms=resolved_arms,
            timeout_seconds=timeout_seconds,
        )
        selected = [
            spec
            for spec in canonical
            if spec.channel in resolved_channels and spec.task_class in resolved_classes
        ]
        raw_dir = _relative_path(raw_output_dir, self.repo_root, label="raw_output_dir")
        specs: list[ProbeSpec] = []
        for base in selected:
            spec = build_probe_spec(
                channel=base.channel,
                task_class=base.task_class,
                arm=base.arm,
                seed=seed,
                replicate=base.replicate,
                prompt=_task_prompt(base.task_class, base.arm, prompt_prefix),
                timeout_seconds=timeout_seconds,
                salt=salt,
                generated_at=generated,
            )
            specs.append(
                ProbeSpec(
                    **{
                        **spec.__dict__,
                        "output_path": f"{raw_dir}/{spec.run_id}.json",
                    }
                )
            )
        return tuple(specs)

    def run(
        self,
        *,
        seed: str,
        salt: int | float | str | None,
        replicates: int = DEFAULT_REPLICATES,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        total_timeout_seconds: float = DEFAULT_TOTAL_TIMEOUT_SECONDS,
        channels: Sequence[str] = SUPPORTED_CHANNELS,
        arms: Sequence[str] = ("skill-off", "skill-on"),
        task_classes: Sequence[str] = TASK_CLASSES,
        prompt_prefix: str = "",
        generated_at: str | None = None,
        output_dir: str | Path = DEFAULT_OUTPUT_DIR,
        raw_output_dir: str | Path = DEFAULT_RAW_OUTPUT_DIR,
        progress: Callable[[int, int], None] | None = None,
    ) -> dict[str, Any]:
        if (
            isinstance(total_timeout_seconds, bool)
            or not isinstance(total_timeout_seconds, (int, float))
            or total_timeout_seconds <= 0
        ):
            raise CalibrationError("total_timeout_seconds must be > 0")
        generated = _timestamp(generated_at)
        specs = self.plan(
            seed=seed,
            salt=salt,
            replicates=replicates,
            timeout_seconds=timeout_seconds,
            channels=channels,
            arms=arms,
            task_classes=task_classes,
            prompt_prefix=prompt_prefix,
            generated_at=generated,
            raw_output_dir=raw_output_dir,
        )
        if not specs:
            raise CalibrationError("calibration matrix is empty")
        run_id = _calibration_run_id(seed, salt, specs)
        cli_runner = CLIProbeRunner(
            repo_root=self.repo_root,
            commands=self.commands,
            runner=self.runner,
        )
        preflight = [
            _preflight_channel(
                self.commands[channel],
                runner=self.runner,
                repo_root=self.repo_root,
            )
            for channel in SUPPORTED_CHANNELS
            if channel in {spec.channel for spec in specs}
        ]
        unavailable_channels = {
            item["channel"] for item in preflight if not item["executable_available"]
        }
        auth_failed_channels: set[str] = set()
        results: list[dict[str, Any]] = []
        started = time.monotonic()
        for index, spec in enumerate(specs, start=1):
            if time.monotonic() - started >= total_timeout_seconds:
                result = cli_runner.record_insufficient(spec, reason="outer_timeout")
            elif spec.channel in unavailable_channels:
                result = cli_runner.record_insufficient(spec, reason="preflight_unavailable")
            elif spec.channel in auth_failed_channels:
                result = cli_runner.record_insufficient(spec, reason="preflight_auth_failed")
            else:
                result = cli_runner.run(spec)
                if _auth_failure(result):
                    auth_failed_channels.add(spec.channel)
            results.append(result)
            if progress is not None:
                progress(index, len(specs))
        for item in preflight:
            if item["channel"] in auth_failed_channels:
                item["auth_status"] = "AUTH_FAILED"
                item["auth_evidence"] = "AVAILABLE"
            elif item["channel"] not in unavailable_channels and any(
                result["channel"] == item["channel"] and result["status"] == "PASS"
                for result in results
            ):
                item["auth_status"] = "AUTHENTICATED"
                item["auth_evidence"] = "AVAILABLE"
            elif item["channel"] not in unavailable_channels:
                item["auth_status"] = "INSUFFICIENT"
                item["auth_evidence"] = "INSUFFICIENT"
        summary = aggregate_calibration_results(results, planned_specs=specs, run_id=run_id)
        output_relative = _relative_path(output_dir, self.repo_root, label="output_dir")
        report = {
            "schema_version": CALIBRATION_SCHEMA_VERSION,
            "report_type": "cli_calibration_roi",
            "run_id": run_id,
            "metadata": {
                "seed": seed,
                "salt": salt,
                "generated_at": generated,
                "repo_root": ".",  # Deliberately non-identifying and repository-relative.
            },
            "matrix": {
                "task_classes": list(dict.fromkeys(spec.task_class for spec in specs)),
                "channels": list(dict.fromkeys(spec.channel for spec in specs)),
                "arms": list(dict.fromkeys(spec.arm for spec in specs)),
                "replicates": replicates,
                "planned_specs": len(specs),
                "timeout_seconds": float(timeout_seconds),
                "total_timeout_seconds": float(total_timeout_seconds),
                "order": ["task_class", "channel", "arm", "replicate"],
            },
            "preflight": preflight,
            "summary": summary,
            "artifacts": {
                "raw_probe_dir": _relative_path(
                    raw_output_dir,
                    self.repo_root,
                    label="raw_output_dir",
                ),
                "report_dir": output_relative,
            },
        }
        report["markdown"] = render_calibration_report(report)
        return report

    def write_report(
        self,
        report: Mapping[str, Any],
        *,
        output_dir: str | Path = DEFAULT_OUTPUT_DIR,
        cycle: str = DEFAULT_CYCLE,
    ) -> tuple[Path, Path]:
        output = self.repo_root / _relative_path(output_dir, self.repo_root, label="output_dir")
        output.mkdir(parents=True, exist_ok=True)
        markdown_path = output / f"{cycle}_calibration_roi.md"
        json_path = output / f"{cycle}_calibration_roi.json"
        markdown_path.write_text(report["markdown"], encoding="utf-8")
        payload = {key: value for key, value in report.items() if key != "markdown"}
        json_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return markdown_path, json_path


def run_calibration(**kwargs: Any) -> dict[str, Any]:
    """Convenience API for one serial calibration run."""

    return CalibrationRunner(
        repo_root=kwargs.pop("repo_root", "."),
        commands=kwargs.pop("commands", None),
        runner=kwargs.pop("runner", subprocess.run),
    ).run(**kwargs)


__all__ = [
    "CALIBRATION_SCHEMA_VERSION",
    "CalibrationError",
    "CalibrationRunner",
    "DEFAULT_OUTPUT_DIR",
    "DEFAULT_RAW_OUTPUT_DIR",
    "DEFAULT_REPLICATES",
    "DEFAULT_TOTAL_TIMEOUT_SECONDS",
    "aggregate_calibration_results",
    "render_calibration_report",
    "run_calibration",
]
