"""Validation and execution helpers for CLI calibration matrix planning."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from devolaflow.harness.cli_probe import (
    SUPPORTED_CHANNELS,
    TASK_CLASSES,
    ChannelConfig,
    ProbeSpec,
    _invoke_runner,
)

CALIBRATION_SCHEMA_VERSION: Final[int] = 1
CommandRunner = Callable[..., subprocess.CompletedProcess[str]]


class CalibrationError(ValueError):
    """A calibration configuration or report input is invalid."""


def _timestamp(value: str | None) -> str:
    resolved = value or datetime.now(UTC).isoformat()
    try:
        datetime.fromisoformat(resolved.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise CalibrationError("generated_at must be an ISO-8601 timestamp") from exc
    return resolved


def _relative_path(path: str | Path, repo_root: Path, *, label: str) -> str:
    candidate = Path(path)
    try:
        resolved = (
            (repo_root / candidate).resolve()
            if not candidate.is_absolute()
            else candidate.resolve()
        )
        return resolved.relative_to(repo_root.resolve()).as_posix()
    except (OSError, ValueError) as exc:
        raise CalibrationError(f"{label} must be inside repo_root") from exc


def _validate_dimensions(
    *,
    channels: Sequence[str],
    arms: Sequence[str],
    task_classes: Sequence[str],
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    resolved_channels = tuple(channels)
    resolved_arms = tuple(arms)
    resolved_classes = tuple(task_classes)
    if not resolved_channels or any(
        channel not in SUPPORTED_CHANNELS for channel in resolved_channels
    ):
        raise CalibrationError(f"channels must be a non-empty subset of {SUPPORTED_CHANNELS!r}")
    if len(set(resolved_channels)) != len(resolved_channels):
        raise CalibrationError("channels must not contain duplicates")
    if len(resolved_arms) != 2 or set(resolved_arms) != {"skill-on", "skill-off"}:
        raise CalibrationError("arms must contain exactly skill-on and skill-off")
    if not resolved_classes or any(
        task_class not in TASK_CLASSES for task_class in resolved_classes
    ):
        raise CalibrationError(f"task_classes must be a non-empty subset of {TASK_CLASSES!r}")
    if len(set(resolved_classes)) != len(resolved_classes):
        raise CalibrationError("task_classes must not contain duplicates")
    return resolved_channels, resolved_arms, resolved_classes


def _task_prompt(task_class: str, arm: str, prompt_prefix: str) -> str:
    prompts = {
        "read-only": (
            "Perform a bounded read-only repository inspection. Do not edit, create, "
            "delete, or execute mutating commands. Return a concise result."
        ),
        "tool-heavy": (
            "Perform a bounded tool-heavy diagnostic using read-only commands only. "
            "Do not edit, create, delete, install, or network-write anything. "
            "Return a concise result."
        ),
        "multi-file": (
            "Review a hypothetical multi-file change and report affected files and risks. "
            "Do not edit files or apply the hypothetical change. Return a concise result."
        ),
        "recovery": (
            "Inspect a hypothetical failed verification and describe a safe recovery sequence. "
            "Do not edit files, retry indefinitely, or run destructive commands. "
            "Return a concise result."
        ),
    }
    arm_instruction = (
        "Calibration arm: follow the installed DevolaFlow skill if it is available."
        if arm == "skill-on"
        else "Calibration arm: do not rely on the DevolaFlow skill; use only the task request."
    )
    prefix = f"{prompt_prefix.strip()} " if prompt_prefix.strip() else ""
    return f"{prefix}{prompts[task_class]} {arm_instruction}"


def _calibration_run_id(seed: str, salt: object, specs: Sequence[ProbeSpec]) -> str:
    identity = {
        "seed": seed,
        "salt": salt,
        "spec_count": len(specs),
        "channels": sorted({spec.channel for spec in specs}),
        "task_classes": sorted({spec.task_class for spec in specs}),
        "arms": sorted({spec.arm for spec in specs}),
        "replicates": max((spec.replicate for spec in specs), default=0),
    }
    encoded = json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"calibration-{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"


def _preflight_channel(
    config: ChannelConfig,
    *,
    runner: CommandRunner,
    repo_root: Path,
    timeout_seconds: float = 5.0,
) -> dict[str, Any]:
    """Check executable presence without retaining command output or paths."""

    started = time.perf_counter()
    executable_available = shutil.which(config.executable) is not None
    record: dict[str, Any] = {
        "channel": config.channel,
        "executable_available": executable_available,
        "version_check": {
            "status": "INSUFFICIENT",
            "exit_code": None,
            "wall_time_seconds": 0.0,
        },
        "auth_status": "INSUFFICIENT",
        "auth_evidence": "INSUFFICIENT",
    }
    if not executable_available:
        record["auth_status"] = "UNAVAILABLE"
        record["auth_evidence"] = "INSUFFICIENT"
        return record
    try:
        completed = _invoke_runner(
            runner,
            [config.executable, "--version"],
            cwd=str(repo_root),
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=False,
        )
    except (FileNotFoundError, PermissionError):
        record["executable_available"] = False
        record["auth_status"] = "UNAVAILABLE"
        record["version_check"]["wall_time_seconds"] = time.perf_counter() - started
        return record
    except subprocess.TimeoutExpired:
        record["version_check"]["wall_time_seconds"] = time.perf_counter() - started
        return record
    except (OSError, subprocess.SubprocessError):
        record["version_check"]["wall_time_seconds"] = time.perf_counter() - started
        return record
    record["version_check"].update(
        {
            "status": "AVAILABLE" if completed.returncode == 0 else "INSUFFICIENT",
            "exit_code": completed.returncode,
            "wall_time_seconds": time.perf_counter() - started,
        }
    )
    # Version output is not an authentication proof. Actual probe outcomes
    # update this field after the first real invocation for the channel.
    return record


__all__ = [
    "CALIBRATION_SCHEMA_VERSION",
    "CalibrationError",
    "CommandRunner",
]
