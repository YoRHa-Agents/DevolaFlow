"""Bounded, replayable probes for supported local agent CLIs.

This module deliberately keeps subprocess execution separate from the legacy
provider/model probe in :mod:`devolaflow.harness.probe`.  A probe is an
observation: unavailable executables, missing usage telemetry, and unobserved
skill state remain explicit ``INSUFFICIENT`` evidence rather than estimates.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import signal
import subprocess
import tempfile
import time
from collections.abc import Callable, Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from devolaflow.host_contract import normalize_skill_observation

SUPPORTED_CHANNELS: Final[tuple[str, ...]] = (
    "claude",
    "codex",
    "kimi",
    "cursor-agent",
    "copilot",
)
PROBE_HOSTS: Final[dict[str, str]] = {
    "claude": "claude",
    "codex": "codex",
    "kimi": "kimicode",
    "cursor-agent": "cursor",
    "copilot": "copilot",
}
TASK_CLASSES: Final[tuple[str, ...]] = (
    "read-only",
    "tool-heavy",
    "multi-file",
    "recovery",
)
ARM_CHOICES: Final[frozenset[str]] = frozenset({"skill-on", "skill-off", "baseline", "candidate"})
DEFAULT_TIMEOUT_SECONDS: Final[float] = 120.0
MAX_TIMEOUT_SECONDS: Final[float] = 3_600.0
MAX_SUMMARY_CHARS: Final[int] = 2_000
PROBE_SCHEMA_VERSION: Final[int] = 1
PROBE_EXIT_CODES: Final[dict[str, int]] = {"PASS": 0, "FAIL": 1, "INSUFFICIENT": 2}
PROBE_STATUSES: Final[tuple[str, ...]] = ("PASS", "FAIL", "INSUFFICIENT")

# These are executable names and argument shapes, not filesystem paths or
# credentials. Operators can replace every value through ChannelConfig or a
# JSON command configuration file.
DEFAULT_COMMAND_TEMPLATES: Final[dict[str, tuple[str, ...]]] = {
    "claude": ("claude", "-p", "{prompt}", "--output-format", "json"),
    "codex": ("codex", "exec", "--json", "{prompt}"),
    "kimi": ("kimi", "--prompt", "{prompt}", "--output-format", "stream-json"),
    "cursor-agent": ("cursor-agent", "-p", "{prompt}", "--output-format", "json"),
    "copilot": ("copilot", "-p", "{prompt}", "--output-format", "json"),
}

_SECRET_RE = re.compile(
    r"(?i)(authorization|api[_-]?key|access[_-]?token|refresh[_-]?token|"
    r"password|secret|token)\s*[:=]\s*([\"']?)[^\s,\"']+\2"
)
_SECRET_FLAG_RE = re.compile(
    r"(?i)(--?(?:api[-_]?key|access[-_]?token|refresh[-_]?token|password|secret|token)\s+)"
    r"[^\s]+"
)
_BEARER_RE = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+")
_KEY_RE = re.compile(r"\b(?:sk|key|token)[-_][A-Za-z0-9_-]{12,}\b", re.IGNORECASE)

CommandRunner = Callable[..., subprocess.CompletedProcess[str]]


class ProbeError(ValueError):
    """A CLI probe specification or command configuration is invalid."""


def _bounded_subprocess_run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
    """Run a command while killing descendants without waiting on inherited pipes."""

    timeout = kwargs.pop("timeout")
    check = kwargs.pop("check", False)
    text_mode = kwargs.pop("text", kwargs.pop("universal_newlines", False))
    encoding = kwargs.pop("encoding", None) or "utf-8"
    errors = kwargs.pop("errors", "replace")

    def read_capture(stream: Any) -> str | bytes:
        stream.seek(0)
        value = stream.read()
        if text_mode and isinstance(value, bytes):
            return value.decode(encoding, errors=errors)
        return value

    with tempfile.TemporaryFile() as stdout_file, tempfile.TemporaryFile() as stderr_file:
        kwargs.pop("capture_output", False)
        process = subprocess.Popen(
            argv,
            start_new_session=True,
            stdout=stdout_file,
            stderr=stderr_file,
            **kwargs,
        )
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            try:
                if os.name == "posix":
                    os.killpg(process.pid, signal.SIGKILL)
                else:
                    process.kill()
            except OSError:
                process.kill()
            with suppress(subprocess.TimeoutExpired):
                process.wait(timeout=1)
            raise subprocess.TimeoutExpired(
                argv,
                timeout,
                output=read_capture(stdout_file),
                stderr=read_capture(stderr_file),
            ) from exc
        stdout = read_capture(stdout_file)
        stderr = read_capture(stderr_file)
    completed = subprocess.CompletedProcess(argv, process.returncode, stdout, stderr)
    if check and process.returncode:
        raise subprocess.CalledProcessError(
            process.returncode,
            argv,
            output=stdout,
            stderr=stderr,
        )
    return completed


def _invoke_runner(runner: CommandRunner, argv: list[str], **kwargs: Any) -> Any:
    if runner is subprocess.run:
        return _bounded_subprocess_run(argv, **kwargs)
    return runner(argv, **kwargs)


def _derive_run_id(
    *,
    channel: str,
    task_class: str,
    arm: str,
    seed: str,
    replicate: int,
    prompt: str,
    salt: int | float | str | None,
) -> str:
    identity = {
        "channel": channel,
        "task_class": task_class,
        "arm": arm,
        "seed": seed,
        "replicate": replicate,
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "salt": salt,
    }
    try:
        encoded = json.dumps(identity, ensure_ascii=False, allow_nan=False, sort_keys=True).encode(
            "utf-8"
        )
    except (TypeError, ValueError) as exc:
        raise ProbeError(f"salt must be JSON-serializable: {exc}") from exc
    return f"probe-{hashlib.sha256(encoded).hexdigest()}"


@dataclass(frozen=True)
class ChannelConfig:
    """One explicit executable and argv template for a supported channel."""

    channel: str
    executable: str
    args: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.channel not in SUPPORTED_CHANNELS:
            raise ProbeError(f"channel must be one of {SUPPORTED_CHANNELS!r}")
        if not isinstance(self.executable, str) or not self.executable.strip():
            raise ProbeError("executable must be a non-empty string")
        if any(not isinstance(arg, str) or not arg for arg in self.args):
            raise ProbeError("args must contain only non-empty strings")

    @classmethod
    def from_mapping(cls, channel: str, value: Mapping[str, Any]) -> ChannelConfig:
        """Build a config from ``{executable, args}`` or an ``argv`` list."""

        if not isinstance(value, Mapping):
            raise ProbeError(f"command config for {channel!r} must be a mapping")
        if "argv" in value:
            raw_argv = value["argv"]
            if (
                not isinstance(raw_argv, list)
                or not raw_argv
                or any(not isinstance(item, str) or not item for item in raw_argv)
            ):
                raise ProbeError(
                    f"command config for {channel!r}.argv must be a non-empty string list"
                )
            return cls(channel, raw_argv[0], tuple(raw_argv[1:]))
        executable = value.get("executable")
        raw_args = value.get("args", [])
        if not isinstance(raw_args, list):
            raise ProbeError(f"command config for {channel!r}.args must be a list")
        return cls(channel, executable, tuple(raw_args))

    def render(self, spec: ProbeSpec) -> list[str]:
        """Render argv without shell interpolation or command concatenation."""

        values = {
            "prompt": spec.prompt,
            "channel": spec.channel,
            "task_class": spec.task_class,
            "arm": spec.arm,
            "seed": spec.seed,
            "replicate": str(spec.replicate),
            "run_id": spec.run_id,
        }
        rendered: list[str] = []
        for template in (self.executable, *self.args):
            try:
                rendered.append(template.format(**values))
            except (KeyError, ValueError) as exc:
                raise ProbeError(f"invalid command template {template!r}") from exc
        return rendered


@dataclass(frozen=True)
class ProbeSpec:
    """One replayable task/channel/arm probe invocation."""

    channel: str
    task_class: str
    arm: str
    seed: str
    replicate: int
    prompt: str
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    output_path: str | Path | None = None
    salt: int | float | str | None = None
    generated_at: str | None = None
    run_id: str = ""

    def __post_init__(self) -> None:
        _validate_dimensions(self.channel, self.task_class, self.arm)
        if not isinstance(self.seed, str) or not self.seed.strip():
            raise ProbeError("seed must be a non-empty string")
        if type(self.replicate) is not int or self.replicate < 1:
            raise ProbeError("replicate must be a positive integer")
        if not isinstance(self.prompt, str):
            raise ProbeError("prompt must be a string")
        _validate_timeout(self.timeout_seconds)
        if self.output_path is not None and not isinstance(self.output_path, (str, Path)):
            raise ProbeError("output_path must be a path or null")
        if not self.run_id:
            object.__setattr__(
                self,
                "run_id",
                _derive_run_id(
                    channel=self.channel,
                    task_class=self.task_class,
                    arm=self.arm,
                    seed=self.seed,
                    replicate=self.replicate,
                    prompt=self.prompt,
                    salt=self.salt,
                ),
            )

    def with_run_id(self, run_id: str) -> ProbeSpec:
        """Return this immutable spec with its derived run ID."""

        return ProbeSpec(
            channel=self.channel,
            task_class=self.task_class,
            arm=self.arm,
            seed=self.seed,
            replicate=self.replicate,
            prompt=self.prompt,
            timeout_seconds=self.timeout_seconds,
            output_path=self.output_path,
            salt=self.salt,
            generated_at=self.generated_at,
            run_id=run_id,
        )

    def as_dict(self) -> dict[str, Any]:
        """Return the stable machine-readable spec shape."""

        return {
            "channel": self.channel,
            "task_class": self.task_class,
            "arm": self.arm,
            "seed": self.seed,
            "replicate": self.replicate,
            "prompt": self.prompt,
            "timeout_seconds": self.timeout_seconds,
            "output_path": str(self.output_path) if self.output_path is not None else None,
            "run_id": self.run_id,
        }


def _validate_dimensions(channel: str, task_class: str, arm: str) -> None:
    if channel not in SUPPORTED_CHANNELS:
        raise ProbeError(f"unknown channel {channel!r}; expected {SUPPORTED_CHANNELS!r}")
    if task_class not in TASK_CLASSES:
        raise ProbeError(f"unknown task_class {task_class!r}; expected {TASK_CLASSES!r}")
    if arm not in ARM_CHOICES:
        raise ProbeError(f"unknown arm {arm!r}; expected {sorted(ARM_CHOICES)!r}")


def _validate_timeout(timeout_seconds: object) -> float:
    if (
        isinstance(timeout_seconds, bool)
        or not isinstance(timeout_seconds, (int, float))
        or timeout_seconds <= 0
        or timeout_seconds > MAX_TIMEOUT_SECONDS
    ):
        raise ProbeError(f"timeout_seconds must be > 0 and <= {MAX_TIMEOUT_SECONDS:g}")
    return float(timeout_seconds)


def build_probe_spec(
    *,
    channel: str,
    task_class: str,
    arm: str,
    seed: str,
    replicate: int,
    prompt: str,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    output_path: str | Path | None = None,
    salt: int | float | str | None = None,
    generated_at: str | None = None,
) -> ProbeSpec:
    """Construct and validate one explicit probe specification."""

    return ProbeSpec(
        channel=channel,
        task_class=task_class,
        arm=arm,
        seed=seed,
        replicate=replicate,
        prompt=prompt,
        timeout_seconds=timeout_seconds,
        output_path=output_path,
        salt=salt,
        generated_at=generated_at,
    )


def plan_probe_matrix(
    replicates: int,
    *,
    seed: str,
    arms: Sequence[str] = ("skill-off", "skill-on"),
    channels: Sequence[str] = SUPPORTED_CHANNELS,
    task_classes: Sequence[str] = TASK_CLASSES,
    prompt: str = "",
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> tuple[ProbeSpec, ...]:
    """Plan a deterministic 4×3×2×N matrix without executing any CLI.

    Ordering is task class, channel, arm, then replicate.  The full canonical
    dimensions are required so accidental partial calibration plans cannot be
    mistaken for the 240-run PV-02 design.
    """

    if type(replicates) is not int or replicates <= 0:
        raise ProbeError("replicates must be a positive integer")
    resolved_channels = tuple(channels)
    resolved_task_classes = tuple(task_classes)
    if resolved_channels != SUPPORTED_CHANNELS:
        raise ProbeError(f"channels must equal {SUPPORTED_CHANNELS!r}")
    if resolved_task_classes != TASK_CLASSES:
        raise ProbeError(f"task_classes must equal {TASK_CLASSES!r}")
    resolved_arms = tuple(arms)
    if len(resolved_arms) != 2 or any(arm not in ARM_CHOICES for arm in resolved_arms):
        raise ProbeError("arms must contain exactly two known arm IDs")
    if len(set(resolved_arms)) != 2:
        raise ProbeError("arms must not contain duplicates")
    _validate_timeout(timeout_seconds)
    return tuple(
        build_probe_spec(
            channel=channel,
            task_class=task_class,
            arm=arm,
            seed=seed,
            replicate=replicate,
            prompt=prompt,
            timeout_seconds=timeout_seconds,
        )
        for task_class in resolved_task_classes
        for channel in resolved_channels
        for arm in resolved_arms
        for replicate in range(1, replicates + 1)
    )


def load_channel_configs(path: str | Path | None = None) -> dict[str, ChannelConfig]:
    """Load explicit channel command templates from a JSON object.

    Omitted channels use executable-name defaults.  Unknown channel keys and
    malformed values fail loudly before a subprocess can be started.
    """

    configs = {
        channel: ChannelConfig(channel, template[0], tuple(template[1:]))
        for channel, template in DEFAULT_COMMAND_TEMPLATES.items()
    }
    if path is None:
        return configs
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProbeError(f"cannot read command config {path}: {exc}") from exc
    if not isinstance(raw, Mapping):
        raise ProbeError("command config root must be a JSON object")
    for channel, value in raw.items():
        if channel not in SUPPORTED_CHANNELS:
            raise ProbeError(f"unknown command config channel {channel!r}")
        configs[channel] = ChannelConfig.from_mapping(channel, value)
    return configs


def _safe_text(value: object) -> str:
    text = value.decode("utf-8", errors="replace") if isinstance(value, bytes) else str(value or "")
    text = _SECRET_RE.sub(r"\1=<redacted>", text)
    text = _SECRET_FLAG_RE.sub(r"\1<redacted>", text)
    text = _BEARER_RE.sub("Bearer <redacted>", text)
    text = _KEY_RE.sub("<redacted>", text)
    if len(text) > MAX_SUMMARY_CHARS:
        return text[:MAX_SUMMARY_CHARS] + "…"
    return text


def _iso_timestamp(value: str | None) -> str:
    resolved = value or datetime.now(UTC).isoformat()
    if not isinstance(resolved, str) or not resolved.strip():
        raise ProbeError("generated_at must be a non-empty ISO-8601 timestamp")
    try:
        datetime.fromisoformat(resolved.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProbeError("generated_at must be an ISO-8601 timestamp") from exc
    return resolved


def _relative_path(value: str | Path, root: Path) -> str:
    candidate = Path(value)
    if not candidate.is_absolute() and (".." in candidate.parts or str(candidate).startswith("~")):
        raise ProbeError("output_path must be repository-relative")
    try:
        resolved = (
            (root / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
        )
        relative = resolved.relative_to(root.resolve())
    except (OSError, ValueError) as exc:
        raise ProbeError("output_path must be inside repo_root") from exc
    return relative.as_posix()


def build_probe_metadata(spec: ProbeSpec, *, repo_root: str | Path = ".") -> dict[str, Any]:
    """Build deterministic identity plus repository-relative output metadata."""

    root = Path(repo_root).resolve()
    if not root.is_dir():
        raise ProbeError(f"repo_root is not a directory: {repo_root}")
    run_id = _derive_run_id(
        channel=spec.channel,
        task_class=spec.task_class,
        arm=spec.arm,
        seed=spec.seed,
        replicate=spec.replicate,
        prompt=spec.prompt,
        salt=spec.salt,
    )
    output = spec.output_path or Path(".local/telemetry/cli-probes") / f"{run_id}.json"
    output_relative = _relative_path(output, root)
    return {
        "schema_version": PROBE_SCHEMA_VERSION,
        "run_id": run_id,
        "seed": spec.seed,
        "channel": spec.channel,
        "task_class": spec.task_class,
        "arm": spec.arm,
        "replicate": spec.replicate,
        "salt": spec.salt,
        "generated_at": _iso_timestamp(spec.generated_at),
        "output_path": output_relative,
        "artifact_path": output_relative,
    }


def _json_objects(stdout: object) -> list[Mapping[str, Any]]:
    """Return JSON response objects from JSON or JSONL CLI output.

    Agent CLIs differ in whether their machine-readable mode emits one JSON
    object or a stream of objects.  This helper only locates explicit JSON
    fields; it never derives usage or skill state from prose or text length.
    """

    raw = (
        stdout.decode("utf-8", errors="replace") if isinstance(stdout, bytes) else str(stdout or "")
    )
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        objects: list[Mapping[str, Any]] = []
        for line in raw.splitlines():
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, Mapping):
                objects.append(value)
        return objects
    if isinstance(parsed, Mapping):
        return [parsed]
    if isinstance(parsed, list):
        return [value for value in parsed if isinstance(value, Mapping)]
    return []


def _token_usage(stdout: object) -> dict[str, Any]:
    usage: Mapping[str, Any] | None = None
    for payload in _json_objects(stdout):
        candidate = payload.get("usage")
        if not isinstance(candidate, Mapping):
            candidate = payload.get("token_usage")
        if not isinstance(candidate, Mapping):
            direct_fields = {"input_tokens", "output_tokens", "prompt_tokens", "completion_tokens"}
            candidate = payload if direct_fields & set(payload) else None
        if isinstance(candidate, Mapping):
            usage = candidate
    if not isinstance(usage, Mapping):
        return {
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
            "status": "INSUFFICIENT",
        }
    input_tokens = usage.get("input_tokens", usage.get("prompt_tokens", usage.get("input")))
    output_tokens = usage.get("output_tokens", usage.get("completion_tokens", usage.get("output")))
    valid = all(type(value) is int and value >= 0 for value in (input_tokens, output_tokens))
    if not valid:
        input_tokens = input_tokens if type(input_tokens) is int and input_tokens >= 0 else None
        output_tokens = output_tokens if type(output_tokens) is int and output_tokens >= 0 else None
    available = input_tokens is not None and output_tokens is not None
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens if available else None,
        "status": "AVAILABLE" if available else "INSUFFICIENT",
    }


def _skill_loaded(
    stdout: object,
    channel: str,
    *,
    reason: str | None = None,
) -> dict[str, Any]:
    value = None
    for candidate in _json_objects(stdout):
        value = candidate.get("skill_loaded")
        if not isinstance(value, bool):
            metadata = candidate.get("metadata")
            value = metadata.get("skill_loaded") if isinstance(metadata, Mapping) else None
        if isinstance(value, bool):
            break
    if not isinstance(value, bool):
        value = None
        reason = reason or (
            "skill_loaded was absent from the CLI JSON output; runtime skill state "
            "is not observable for this invocation"
        )
    return normalize_skill_observation(PROBE_HOSTS[channel], value, reason=reason)


def _base_result(
    spec: ProbeSpec,
    metadata: Mapping[str, Any],
    argv: list[str],
    *,
    cwd: str,
) -> dict[str, Any]:
    return {
        "schema_version": PROBE_SCHEMA_VERSION,
        "event": "cli_probe",
        "status": "INSUFFICIENT",
        "metadata": dict(metadata),
        "channel": spec.channel,
        "measurement": {
            "host": PROBE_HOSTS[spec.channel],
            "channel": spec.channel,
        },
        "task_class": spec.task_class,
        "arm": spec.arm,
        "command": {
            "argv": [_safe_text(argument) for argument in argv],
            "cwd": cwd,
            "timeout_seconds": spec.timeout_seconds,
        },
        "execution": {
            "exit_code": None,
            "stdout_summary": "",
            "stderr_summary": "",
            "wall_time_seconds": 0.0,
            "reason": "unavailable",
        },
        "token_usage": {
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
            "status": "INSUFFICIENT",
        },
        "skill_loaded": _skill_loaded(
            "",
            spec.channel,
            reason="CLI channel was unavailable or did not complete; no skill state was observed",
        ),
        "stages": {"run": {"wall_time_seconds": 0.0}},
    }


class CLIProbeRunner:
    """Execute one configured local CLI with a hard subprocess timeout."""

    def __init__(
        self,
        *,
        repo_root: str | Path = ".",
        commands: Mapping[str, ChannelConfig] | None = None,
        runner: CommandRunner = subprocess.run,
    ) -> None:
        self.repo_root = Path(repo_root).resolve()
        if not self.repo_root.is_dir():
            raise ProbeError(f"repo_root is not a directory: {repo_root}")
        self.commands = load_channel_configs()
        if commands is not None:
            unknown = set(commands) - set(SUPPORTED_CHANNELS)
            if unknown:
                raise ProbeError(f"commands contain unsupported channels: {sorted(unknown)}")
            self.commands.update(commands)
        if any(not isinstance(config, ChannelConfig) for config in self.commands.values()):
            raise ProbeError("commands values must be ChannelConfig instances")
        self.runner = runner

    def run(self, spec: ProbeSpec) -> dict[str, Any]:
        """Execute and optionally serialize one probe result."""

        if not isinstance(spec, ProbeSpec):
            raise ProbeError("spec must be a ProbeSpec")
        metadata = build_probe_metadata(spec, repo_root=self.repo_root)
        resolved_spec = spec.with_run_id(metadata["run_id"])
        argv = self.commands[spec.channel].render(resolved_spec)
        result = _base_result(
            resolved_spec,
            metadata,
            argv,
            cwd=".",
        )
        started = time.perf_counter()
        try:
            completed = _invoke_runner(
                self.runner,
                argv,
                cwd=str(self.repo_root),
                check=False,
                capture_output=True,
                text=True,
                timeout=spec.timeout_seconds,
                shell=False,
            )
            wall_time = time.perf_counter() - started
            stdout = getattr(completed, "stdout", "")
            stderr = getattr(completed, "stderr", "")
            exit_code = getattr(completed, "returncode", None)
            result["execution"].update(
                {
                    "exit_code": exit_code,
                    "stdout_summary": _safe_text(stdout),
                    "stderr_summary": _safe_text(stderr),
                    "wall_time_seconds": wall_time,
                    "reason": "completed" if exit_code == 0 else "nonzero_exit",
                }
            )
            result["stages"]["run"]["wall_time_seconds"] = wall_time
            result["token_usage"] = _token_usage(stdout)
            result["skill_loaded"] = _skill_loaded(stdout, spec.channel)
            result["status"] = "PASS" if exit_code == 0 else "FAIL"
        except subprocess.TimeoutExpired as exc:
            wall_time = time.perf_counter() - started
            result["execution"].update(
                {
                    "stdout_summary": _safe_text(exc.output),
                    "stderr_summary": _safe_text(exc.stderr),
                    "wall_time_seconds": wall_time,
                    "reason": "timeout",
                }
            )
            result["stages"]["run"]["wall_time_seconds"] = wall_time
        except (FileNotFoundError, PermissionError) as exc:
            wall_time = time.perf_counter() - started
            result["execution"].update(
                {
                    "stderr_summary": _safe_text(f"{type(exc).__name__}: {exc}"),
                    "wall_time_seconds": wall_time,
                    "reason": "unavailable",
                }
            )
            result["stages"]["run"]["wall_time_seconds"] = wall_time
        except (OSError, subprocess.SubprocessError) as exc:
            wall_time = time.perf_counter() - started
            result["execution"].update(
                {
                    "stderr_summary": _safe_text(f"{type(exc).__name__}: {exc}"),
                    "wall_time_seconds": wall_time,
                    "reason": "runner_error",
                }
            )
            result["stages"]["run"]["wall_time_seconds"] = wall_time
        _write_result(result, self.repo_root)
        return result

    def record_insufficient(self, spec: ProbeSpec, *, reason: str) -> dict[str, Any]:
        """Persist an explicit non-execution result for a bounded run stop.

        Calibration uses this only after an outer timeout or a preflight
        decision that makes another subprocess invocation unsafe.  It keeps
        the same metadata, command shape, and artifact serialization as a
        normal probe without pretending that a CLI was called.
        """

        if not isinstance(spec, ProbeSpec):
            raise ProbeError("spec must be a ProbeSpec")
        if not isinstance(reason, str) or not reason.strip():
            raise ProbeError("reason must be a non-empty string")
        metadata = build_probe_metadata(spec, repo_root=self.repo_root)
        resolved_spec = spec.with_run_id(metadata["run_id"])
        argv = self.commands[spec.channel].render(resolved_spec)
        result = _base_result(
            resolved_spec,
            metadata,
            argv,
            cwd=".",
        )
        result["execution"]["reason"] = reason
        _write_result(result, self.repo_root)
        return result


def _write_result(result: Mapping[str, Any], repo_root: Path) -> Path:
    relative = result["metadata"]["output_path"]
    destination = repo_root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(
            json.loads(serialize_probe_result(result)),
            ensure_ascii=False,
            indent=2,
            separators=(",", ": "),
        )
        + "\n",
        encoding="utf-8",
    )
    return destination


def run_cli_probe(
    spec: ProbeSpec,
    *,
    repo_root: str | Path = ".",
    commands: Mapping[str, ChannelConfig] | None = None,
    runner: CommandRunner = subprocess.run,
) -> dict[str, Any]:
    """Convenience API for one bounded local CLI probe."""

    return CLIProbeRunner(repo_root=repo_root, commands=commands, runner=runner).run(spec)


def serialize_probe_result(result: Mapping[str, Any]) -> str:
    """Serialize a result as stable JSON suitable for JSONL or artifact use."""

    if not isinstance(result, Mapping):
        raise ProbeError("result must be a mapping")
    return json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


__all__ = [
    "ARM_CHOICES",
    "ChannelConfig",
    "CLIProbeRunner",
    "DEFAULT_COMMAND_TEMPLATES",
    "DEFAULT_TIMEOUT_SECONDS",
    "MAX_TIMEOUT_SECONDS",
    "ProbeError",
    "PROBE_EXIT_CODES",
    "PROBE_HOSTS",
    "PROBE_STATUSES",
    "ProbeSpec",
    "PROBE_SCHEMA_VERSION",
    "SUPPORTED_CHANNELS",
    "TASK_CLASSES",
    "build_probe_metadata",
    "build_probe_spec",
    "load_channel_configs",
    "plan_probe_matrix",
    "run_cli_probe",
    "serialize_probe_result",
]
