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
DEFAULT_TELEMETRY_LEDGER: Final[str] = ".local/telemetry/harness.jsonl"
SKILL_CANARY_PREFIX: Final[str] = "DF-SKILL-CANARY-"
PROBE_SCHEMA_VERSION: Final[int] = 1
PROBE_EXIT_CODES: Final[dict[str, int]] = {"PASS": 0, "FAIL": 1, "INSUFFICIENT": 2}
PROBE_STATUSES: Final[tuple[str, ...]] = ("PASS", "FAIL", "INSUFFICIENT")
CACHE_USAGE_COMPONENTS: Final[tuple[str, ...]] = (
    "cache_read",
    "cache_creation",
    "cache_write",
    "uncached_input",
)

# These are provider response fields, not estimates.  Kimi intentionally has
# no entries until a captured Kimi response establishes a cache field path.
_CACHE_USAGE_ALIASES: Final[dict[str, dict[str, tuple[tuple[str, ...], ...]]]] = {
    "claude": {
        "cache_read": (("cache_read_input_tokens",),),
        "cache_creation": (("cache_creation_input_tokens",),),
        "cache_write": (("cache_write_input_tokens",),),
        "uncached_input": (("input_tokens",),),
    },
    "codex": {
        "cache_read": (
            ("cached_input_tokens",),
            ("input_tokens_details", "cached_tokens"),
            ("prompt_tokens_details", "cached_tokens"),
        ),
        "cache_creation": (("cache_creation_input_tokens",),),
        "cache_write": (("cache_write_input_tokens",),),
        "uncached_input": (("uncached_input_tokens",),),
    },
    "kimi": {
        "cache_read": (),
        "cache_creation": (),
        "cache_write": (),
        "uncached_input": (),
    },
}

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
_ABSOLUTE_PATH_RE = re.compile(
    r"(?<![\w])/(?:Users|private|var|tmp|home|opt|etc|Applications|Library)(?:/[^\s\"']*)?"
)

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


def _derive_skill_canary(spec: ProbeSpec) -> str | None:
    """Return a non-secret marker for skill-on response verification."""

    if spec.arm != "skill-on":
        return None
    identity = {
        "channel": spec.channel,
        "task_class": spec.task_class,
        "arm": spec.arm,
        "seed": spec.seed,
        "replicate": spec.replicate,
        "salt": spec.salt,
    }
    encoded = json.dumps(identity, ensure_ascii=False, allow_nan=False, sort_keys=True).encode(
        "utf-8"
    )
    return f"{SKILL_CANARY_PREFIX}{hashlib.sha256(encoded).hexdigest()[:20]}"


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
            "prompt": _probe_prompt(spec),
            "channel": spec.channel,
            "task_class": spec.task_class,
            "arm": spec.arm,
            "seed": spec.seed,
            "replicate": str(spec.replicate),
            "run_id": spec.run_id,
            "skill_canary": spec.skill_canary or "",
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
            "skill_canary": self.skill_canary,
        }

    @property
    def skill_canary(self) -> str | None:
        return _derive_skill_canary(self)


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


def _probe_prompt(spec: ProbeSpec) -> str:
    """Add a non-semantic response marker only to skill-on probes."""

    canary = spec.skill_canary
    if canary is None:
        return spec.prompt
    return (
        f"{spec.prompt}\n\n"
        "Harness verification only: if the DevolaFlow skill is loaded, echo the exact "
        f"marker `{canary}` in the structured response field `skill_canary_echo`. "
        "Do not change the requested task or perform any additional action."
    )


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
    text = _ABSOLUTE_PATH_RE.sub("<absolute-path>", text)
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


def _json_mappings_with_paths(stdout: object) -> list[tuple[Mapping[str, Any], str]]:
    """Return every JSON mapping and its repository-independent JSON path."""

    raw = (
        stdout.decode("utf-8", errors="replace") if isinstance(stdout, bytes) else str(stdout or "")
    )
    roots: list[Any] = []
    try:
        roots.append(json.loads(raw))
    except (TypeError, json.JSONDecodeError):
        for line in raw.splitlines():
            if not line.strip():
                continue
            try:
                roots.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    mappings: list[tuple[Mapping[str, Any], str]] = []

    def visit(value: object, path: str) -> None:
        if isinstance(value, Mapping):
            mappings.append((value, path))
            for key, child in value.items():
                child_path = f"{path}.{key}" if path else str(key)
                visit(child, child_path)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, f"{path}[{index}]")

    for root in roots:
        visit(root, "")
    return mappings


def _json_parse_mismatch_path(stdout: object) -> str | None:
    """Return the first malformed JSONL line, if the stream is not JSON."""

    raw = (
        stdout.decode("utf-8", errors="replace") if isinstance(stdout, bytes) else str(stdout or "")
    )
    try:
        json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        for line_number, line in enumerate(raw.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                json.loads(line)
            except json.JSONDecodeError:
                return f"jsonl.line[{line_number}]"
    return None


def _path_for_usage(base_path: str, field_path: Sequence[str]) -> str:
    suffix = ".".join(field_path)
    return f"{base_path}.{suffix}" if base_path else suffix


def _cache_observation(
    usage: Mapping[str, Any],
    usage_path: str,
    aliases: Sequence[tuple[str, ...]],
) -> dict[str, Any]:
    """Read one explicitly named provider field without treating absence as zero."""

    for field_path in aliases:
        value: object = usage
        found = True
        for key in field_path:
            if not isinstance(value, Mapping) or key not in value:
                found = False
                break
            value = value[key]
        if not found:
            continue
        source_path = _path_for_usage(usage_path, field_path)
        if type(value) is int and value >= 0:
            return {"tokens": value, "status": "AVAILABLE", "source_path": source_path}
        return {"tokens": None, "status": "INSUFFICIENT", "source_path": source_path}
    return {"tokens": None, "status": "INSUFFICIENT", "source_path": None}


def _empty_cache_usage() -> dict[str, dict[str, Any]]:
    return {
        component: {"tokens": None, "status": "INSUFFICIENT", "source_path": None}
        for component in CACHE_USAGE_COMPONENTS
    }


def _token_usage(stdout: object, *, channel: str | None = None) -> dict[str, Any]:
    usage: Mapping[str, Any] | None = None
    usage_path = ""
    parser_mismatch_path = _json_parse_mismatch_path(stdout)
    mappings = _json_mappings_with_paths(stdout)
    for payload, payload_path in mappings:
        candidate = payload.get("usage")
        candidate_path = f"{payload_path}.usage" if payload_path else "usage"
        if not isinstance(candidate, Mapping):
            if "usage" in payload:
                parser_mismatch_path = candidate_path
            candidate = payload.get("token_usage")
            candidate_path = f"{payload_path}.token_usage" if payload_path else "token_usage"
        if not isinstance(candidate, Mapping):
            if "token_usage" in payload:
                parser_mismatch_path = candidate_path
            direct_fields = {"input_tokens", "output_tokens", "prompt_tokens", "completion_tokens"}
            candidate = payload if direct_fields & set(payload) else None
            candidate_path = payload_path
            if candidate is not None:
                parser_mismatch_path = candidate_path or "$"
        if isinstance(candidate, Mapping):
            usage = candidate
            usage_path = candidate_path
    if not isinstance(usage, Mapping):
        return {
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
            "cache_usage": _empty_cache_usage(),
            "usage_observation": {
                "status": "INSUFFICIENT",
                "reason": (
                    "parser_mismatch" if parser_mismatch_path or not mappings else "missing_usage"
                ),
                "source_path": parser_mismatch_path or "$",
            },
            "status": "INSUFFICIENT",
        }
    input_tokens = usage.get("input_tokens", usage.get("prompt_tokens", usage.get("input")))
    output_tokens = usage.get("output_tokens", usage.get("completion_tokens", usage.get("output")))
    valid = all(type(value) is int and value >= 0 for value in (input_tokens, output_tokens))
    if not valid:
        input_tokens = input_tokens if type(input_tokens) is int and input_tokens >= 0 else None
        output_tokens = output_tokens if type(output_tokens) is int and output_tokens >= 0 else None
    available = input_tokens is not None and output_tokens is not None
    cache_usage = _empty_cache_usage()
    aliases = _CACHE_USAGE_ALIASES.get(channel or "", {})
    for component in CACHE_USAGE_COMPONENTS:
        cache_usage[component] = _cache_observation(
            usage,
            usage_path,
            aliases.get(component, ()),
        )
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens if available else None,
        "cache_usage": cache_usage,
        "usage_observation": {
            "status": "AVAILABLE" if available else "INSUFFICIENT",
            "reason": "usage_observed" if available else "parser_mismatch",
            "source_path": usage_path or "$",
        },
        "status": "AVAILABLE" if available else "INSUFFICIENT",
    }


def _skill_loaded(
    stdout: object,
    channel: str,
    *,
    arm: str,
    expected_canary: str | None,
    reason: str | None = None,
) -> dict[str, Any]:
    value: bool | None = None
    canary = _skill_canary_observation(
        stdout,
        arm=arm,
        expected_canary=expected_canary,
    )
    for candidate, _ in _json_mappings_with_paths(stdout):
        direct = candidate.get("skill_loaded")
        nested = candidate.get("metadata")
        value = direct if isinstance(direct, bool) else None
        if value is None and isinstance(nested, Mapping):
            nested_value = nested.get("skill_loaded")
            value = nested_value if isinstance(nested_value, bool) else None
        if isinstance(value, bool):
            break
    if arm == "skill-on":
        value = True if canary["status"] == "AVAILABLE" else None
        reason = reason or canary["reason"]
    if not isinstance(value, bool):
        value = None
        reason = reason or (
            "skill_loaded was absent from the CLI JSON output; runtime skill state "
            "is not observable for this invocation"
        )
    return normalize_skill_observation(PROBE_HOSTS[channel], value, reason=reason)


def _skill_canary_observation(
    stdout: object,
    *,
    arm: str,
    expected_canary: str | None,
) -> dict[str, Any]:
    """Find an exact structured canary echo without inspecting prose."""

    if arm != "skill-on" or expected_canary is None:
        return {
            "expected": None,
            "echo": None,
            "source_path": None,
            "status": "NOT_APPLICABLE",
            "reason": "skill canary is only requested for skill-on probes",
        }
    first_path = "$"
    for candidate, payload_path in _json_mappings_with_paths(stdout):
        source_path = f"{payload_path}.skill_canary_echo" if payload_path else "skill_canary_echo"
        if "skill_canary_echo" not in candidate:
            continue
        echo = candidate["skill_canary_echo"]
        if not isinstance(echo, str):
            return {
                "expected": expected_canary,
                "echo": None,
                "source_path": source_path,
                "status": "INSUFFICIENT",
                "reason": "canary_mismatch",
            }
        if echo == expected_canary:
            return {
                "expected": expected_canary,
                "echo": echo,
                "source_path": source_path,
                "status": "AVAILABLE",
                "reason": "canary_echo_verified",
            }
        return {
            "expected": expected_canary,
            "echo": echo,
            "source_path": source_path,
            "status": "INSUFFICIENT",
            "reason": "canary_mismatch",
        }
    return {
        "expected": expected_canary,
        "echo": None,
        "source_path": first_path,
        "status": "INSUFFICIENT",
        "reason": "missing_canary_echo",
    }


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
            "started_at": None,
            "finished_at": None,
            "stdout_summary": "",
            "stderr_summary": "",
            "partial_output_summary": {"stdout": "", "stderr": ""},
            "wall_time_seconds": 0.0,
            "reason": "unavailable",
            "timeout_phase": None,
            "termination_reason": None,
        },
        "token_usage": {
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
            "cache_usage": _empty_cache_usage(),
            "usage_observation": {
                "status": "INSUFFICIENT",
                "reason": "missing_usage",
                "source_path": "$",
            },
            "status": "INSUFFICIENT",
        },
        "skill_loaded": _skill_loaded(
            "",
            spec.channel,
            arm=spec.arm,
            expected_canary=spec.skill_canary,
            reason="CLI channel was unavailable or did not complete; no skill state was observed",
        ),
        "skill_canary": _skill_canary_observation(
            "",
            arm=spec.arm,
            expected_canary=spec.skill_canary,
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
        telemetry_ledger: str | Path | None = DEFAULT_TELEMETRY_LEDGER,
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
        self.telemetry_ledger = telemetry_ledger

    def _ingest_telemetry(self, result: dict[str, Any]) -> None:
        """Append the new probe artifact without hiding ingestion failures."""

        if self.telemetry_ledger is None:
            return
        try:
            from devolaflow.harness.token_injection import ingest_cli_probe_artifact

            ledger = Path(self.telemetry_ledger)
            if not ledger.is_absolute():
                ledger = self.repo_root / ledger
            record = ingest_cli_probe_artifact(
                self.repo_root / result["metadata"]["artifact_path"],
                ledger,
                repo_root=self.repo_root,
                layer="L2",
                profile="cli-probe",
            )
            result["telemetry"] = {
                "status": "AVAILABLE",
                "ledger_path": _relative_path(ledger, self.repo_root),
                "event_id": record["event_id"],
            }
        except Exception as exc:  # noqa: BLE001 - result carries the failure
            result["telemetry"] = {
                "status": "INSUFFICIENT",
                "ledger_path": _relative_path(
                    Path(self.telemetry_ledger)
                    if self.telemetry_ledger is not None
                    else self.repo_root / DEFAULT_TELEMETRY_LEDGER,
                    self.repo_root,
                ),
                "reason": f"{type(exc).__name__}: {exc}",
            }

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
        started_at = _iso_timestamp(None)
        result["execution"]["started_at"] = started_at
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
                    "finished_at": _iso_timestamp(None),
                    "stdout_summary": _safe_text(stdout),
                    "stderr_summary": _safe_text(stderr),
                    "partial_output_summary": {
                        "stdout": _safe_text(stdout),
                        "stderr": _safe_text(stderr),
                    },
                    "wall_time_seconds": wall_time,
                    "reason": "completed" if exit_code == 0 else "nonzero_exit",
                    "termination_reason": "process_exit",
                }
            )
            result["stages"]["run"]["wall_time_seconds"] = wall_time
            result["token_usage"] = _token_usage(stdout, channel=spec.channel)
            result["skill_loaded"] = _skill_loaded(
                stdout,
                spec.channel,
                arm=spec.arm,
                expected_canary=spec.skill_canary,
            )
            result["skill_canary"] = _skill_canary_observation(
                stdout,
                arm=spec.arm,
                expected_canary=spec.skill_canary,
            )
            result["status"] = "PASS" if exit_code == 0 else "FAIL"
        except subprocess.TimeoutExpired as exc:
            wall_time = time.perf_counter() - started
            stdout_summary = _safe_text(exc.output)
            stderr_summary = _safe_text(exc.stderr)
            result["execution"].update(
                {
                    "finished_at": _iso_timestamp(None),
                    "stdout_summary": stdout_summary,
                    "stderr_summary": stderr_summary,
                    "partial_output_summary": {
                        "stdout": stdout_summary,
                        "stderr": stderr_summary,
                    },
                    "wall_time_seconds": wall_time,
                    "reason": "timeout",
                    "timeout_phase": "probe",
                    "termination_reason": "timeout_expired",
                }
            )
            result["stages"]["run"]["wall_time_seconds"] = wall_time
        except (FileNotFoundError, PermissionError) as exc:
            wall_time = time.perf_counter() - started
            result["execution"].update(
                {
                    "finished_at": _iso_timestamp(None),
                    "stderr_summary": _safe_text(f"{type(exc).__name__}: {exc}"),
                    "partial_output_summary": {
                        "stdout": "",
                        "stderr": _safe_text(f"{type(exc).__name__}: {exc}"),
                    },
                    "wall_time_seconds": wall_time,
                    "reason": "unavailable",
                    "termination_reason": "runner_not_available",
                }
            )
            result["stages"]["run"]["wall_time_seconds"] = wall_time
        except (OSError, subprocess.SubprocessError) as exc:
            wall_time = time.perf_counter() - started
            result["execution"].update(
                {
                    "finished_at": _iso_timestamp(None),
                    "stderr_summary": _safe_text(f"{type(exc).__name__}: {exc}"),
                    "partial_output_summary": {
                        "stdout": "",
                        "stderr": _safe_text(f"{type(exc).__name__}: {exc}"),
                    },
                    "wall_time_seconds": wall_time,
                    "reason": "runner_error",
                    "termination_reason": "runner_error",
                }
            )
            result["stages"]["run"]["wall_time_seconds"] = wall_time
        _write_result(result, self.repo_root)
        self._ingest_telemetry(result)
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
        result["execution"]["started_at"] = _iso_timestamp(None)
        result["execution"]["finished_at"] = result["execution"]["started_at"]
        result["execution"]["termination_reason"] = reason
        if reason == "outer_timeout":
            result["execution"]["timeout_phase"] = "calibration"
        _write_result(result, self.repo_root)
        self._ingest_telemetry(result)
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
    telemetry_ledger: str | Path | None = DEFAULT_TELEMETRY_LEDGER,
) -> dict[str, Any]:
    """Convenience API for one bounded local CLI probe."""

    return CLIProbeRunner(
        repo_root=repo_root,
        commands=commands,
        runner=runner,
        telemetry_ledger=telemetry_ledger,
    ).run(spec)


def serialize_probe_result(result: Mapping[str, Any]) -> str:
    """Serialize a result as stable JSON suitable for JSONL or artifact use."""

    if not isinstance(result, Mapping):
        raise ProbeError("result must be a mapping")
    return json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


__all__ = [
    "ARM_CHOICES",
    "CACHE_USAGE_COMPONENTS",
    "ChannelConfig",
    "CLIProbeRunner",
    "DEFAULT_COMMAND_TEMPLATES",
    "DEFAULT_TELEMETRY_LEDGER",
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
