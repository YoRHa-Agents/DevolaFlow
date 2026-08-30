"""Strict, offline functional-matrix loading and execution primitives.

The YAML matrix is the inventory.  This module owns the small adapter registry
used by the PV-0 runner; matrix values are never imported or evaluated as
Python code.
"""

from __future__ import annotations

import http.client
import json
import logging
import os
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import urllib.request
from collections.abc import Callable, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, NoReturn

import yaml

LOGGER = logging.getLogger(__name__)

MATRIX_RELATIVE_PATH = Path("tests/functional/matrix.yaml")
SCHEMA_VERSION = 1
KNOWN_DOMAINS = frozenset(
    {
        "functional_infrastructure",
        "identity_and_packaging",
        "console_tooling",
        "module_execution",
        "template_and_workflow_runtime",
        "harness_and_telemetry",
        "agent_workspace",
        "gates_and_quality",
        "selector_and_context_routing",
        "plugin_registry_and_lifecycle",
        "code_intelligence",
        "compression_pipeline",
        "local_task_archive",
        "hostbridge_protocol",
        "agent_skill_delivery",
        "npm_installer_delivery",
    }
)
KNOWN_SURFACES = frozenset(
    {
        "matrix_loader",
        "typed_outcome",
        "optional_prerequisite",
        "matrix_gate",
        "installed_wheel_api",
        "console_script",
        "python_module",
        "repository_yaml",
        "external_binary",
        "npm_package",
        "runtime_api",
        "network_policy",
        "telemetry_artifact",
    }
)
KNOWN_TIERS = frozenset({"fast", "slow"})
REQUIRED_ROW_FIELDS = frozenset(
    {
        "id",
        "domain",
        "surface",
        "call",
        "fixture",
        "tier",
        "required",
        "expected",
        "design_source",
    }
)
ALLOWED_ROW_FIELDS = REQUIRED_ROW_FIELDS | {
    "entrypoint",
    "expected_status",
    "prerequisite",
}
ALLOWED_DOCUMENT_FIELDS = frozenset({"schema_version", "mode", "defaults", "rows"})
ALLOWED_DEFAULT_FIELDS = frozenset(
    {"timeout_seconds", "network", "unclassified_outcome", "required_skip"}
)


class OutcomeStatus(Enum):
    """The only statuses a functional adapter may report."""

    PASS = "PASS"
    FAIL = "FAIL"
    SKIP_OPTIONAL = "SKIP_OPTIONAL"
    INSUFFICIENT = "INSUFFICIENT"


FunctionalStatus = OutcomeStatus


@dataclass(frozen=True)
class FunctionalOutcome:
    """Typed, serializable evidence returned by one matrix adapter."""

    row_id: str
    status: OutcomeStatus
    message: str
    details: Mapping[str, Any] | None = None
    prerequisite: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a stable JSON-compatible representation."""
        return {
            "row_id": self.row_id,
            "status": self.status.value,
            "message": self.message,
            "details": dict(self.details or {}),
            "prerequisite": self.prerequisite,
        }

    def to_json(self) -> str:
        """Serialize this outcome with deterministic key ordering."""
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True)


FunctionalResult = FunctionalOutcome


@dataclass(frozen=True)
class MatrixDiagnostic:
    """One deterministic, row-keyed matrix contract diagnostic."""

    row_id: str
    code: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"row_id": self.row_id, "code": self.code, "message": self.message}

    def __str__(self) -> str:
        return f"row={self.row_id} code={self.code}: {self.message}"


class MatrixValidationError(ValueError):
    """Raised when a matrix cannot be loaded as the strict PV-0 schema."""

    def __init__(self, diagnostics: tuple[MatrixDiagnostic, ...]):
        self.diagnostics = diagnostics
        super().__init__("\n".join(str(item) for item in diagnostics))


@dataclass(frozen=True)
class MatrixRow:
    """Normalized matrix row passed to an explicit adapter."""

    id: str
    domain: str
    surface: str
    call: str
    fixture: str
    tier: str
    required: bool
    expected: str
    design_source: tuple[str, ...]
    expected_status: OutcomeStatus = OutcomeStatus.PASS
    prerequisite: str | None = None
    entrypoint: str | None = None

    @property
    def row_id(self) -> str:
        return self.id


@dataclass(frozen=True)
class MatrixDocument:
    """Validated matrix document and its offline execution defaults."""

    schema_version: int
    mode: str
    defaults: Mapping[str, Any]
    rows: tuple[MatrixRow, ...]

    def __iter__(self):
        return iter(self.rows)

    def __len__(self) -> int:
        return len(self.rows)


Adapter = Callable[[MatrixRow, Path], FunctionalOutcome]


class NetworkAccessDenied(RuntimeError):  # noqa: N818
    """Raised when a functional adapter attempts network access."""


@contextmanager
def _deny_network():
    """Deny common in-process network entrypoints for one adapter call."""

    def deny(*_args: Any, **_kwargs: Any) -> NoReturn:
        raise NetworkAccessDenied("network access is forbidden in offline functional mode")

    original = {
        "socket": socket.socket,
        "create_connection": socket.create_connection,
        "urlopen": urllib.request.urlopen,
        "http_connection": http.client.HTTPConnection,
        "https_connection": http.client.HTTPSConnection,
    }

    class GuardedSocket(original["socket"]):  # type: ignore[misc, valid-type]
        def connect(self, address: Any) -> None:
            deny(address)

        def connect_ex(self, address: Any) -> int:
            deny(address)
            return 1

    socket.socket = GuardedSocket  # type: ignore[assignment]
    socket.create_connection = deny  # type: ignore[assignment]
    urllib.request.urlopen = deny  # type: ignore[assignment]
    http.client.HTTPConnection = deny  # type: ignore[assignment]
    http.client.HTTPSConnection = deny  # type: ignore[assignment]
    try:
        yield
    finally:
        socket.socket = original["socket"]  # type: ignore[assignment]
        socket.create_connection = original["create_connection"]  # type: ignore[assignment]
        urllib.request.urlopen = original["urlopen"]  # type: ignore[assignment]
        http.client.HTTPConnection = original["http_connection"]  # type: ignore[assignment]
        http.client.HTTPSConnection = original["https_connection"]  # type: ignore[assignment]


@dataclass(frozen=True)
class EntrypointCase:
    """Behavioral subprocess contract for one public entrypoint."""

    kind: str
    valid_args: tuple[str, ...]
    expected_exit_codes: frozenset[int]
    expected_stdout: tuple[str, ...] = ()
    expected_stderr: tuple[str, ...] = ()
    valid_stdin: str = ""
    malformed_args: tuple[str, ...] | None = None
    malformed_exit_codes: frozenset[int] = frozenset()
    malformed_stdout: tuple[str, ...] = ()
    malformed_stderr: tuple[str, ...] = ()
    malformed_stdin: str = ""
    timeout_seconds: float = 30.0


MAINTAINED_MODULE_ENTRYPOINTS = (
    "devolaflow.build_skill",
    "devolaflow.task_adaptive_selector",
    "devolaflow.local.workspace",
    "devolaflow.pre_decision",
    # This is retained as a required negative contract: its docstring claims
    # support, but the module currently has no executable guard.
    "devolaflow.pre_decision.detect",
    "devolaflow.skills.slash_commands",
    "devolaflow.agent_workspace.lint",
    "devolaflow.agent_workspace.reporter",
    "devolaflow.harness",
    "devolaflow.hostbridge",
)


def load_console_script_inventory(repo_root: Path) -> tuple[str, ...]:
    """Read the canonical console-script names from ``pyproject.toml``."""
    with (repo_root / "pyproject.toml").open("rb") as stream:
        scripts = tomllib.load(stream).get("project", {}).get("scripts", {})
    if not isinstance(scripts, Mapping):
        raise ValueError("pyproject.toml project.scripts must be a mapping")
    return tuple(scripts)


def _format_case_args(args: tuple[str, ...], repo_root: Path) -> tuple[str, ...]:
    return tuple(value.replace("{repo_root}", str(repo_root)) for value in args)


_CONSOLE_SCRIPT_CASES: dict[str, EntrypointCase] = {
    "devola-init": EntrypointCase(
        "console_script",
        ("--list",),
        frozenset({0}),
        expected_stdout=("Available",),
    ),
    "devola-version": EntrypointCase(
        "console_script",
        (),
        frozenset({0}),
        expected_stdout=("DevolaFlow v",),
    ),
    "validate-template": EntrypointCase(
        "console_script",
        ("--all",),
        frozenset({0}),
        expected_stdout=("PASS:",),
        malformed_args=("missing-template.yaml",),
        malformed_exit_codes=frozenset({1}),
        malformed_stdout=("FAIL:",),
    ),
    "validate-gate": EntrypointCase(
        "console_script",
        (),
        frozenset({0}),
        expected_stdout=("usage:",),
        malformed_args=("--input", "missing-gate.yaml"),
        malformed_exit_codes=frozenset({2}),
        malformed_stderr=("error: input file not found",),
    ),
    "build-skill": EntrypointCase(
        "console_script",
        ("--tools", "cursor"),
        frozenset({0}),
        expected_stdout=("[OK]",),
        malformed_args=("--tools", "missing-adapter"),
        malformed_exit_codes=frozenset({2}),
        malformed_stderr=("Unknown adapters:",),
    ),
    "check-drift": EntrypointCase(
        "console_script",
        (),
        frozenset({0, 1}),
        expected_stdout=(),
        expected_stderr=(),
    ),
    "detect-repo-mode": EntrypointCase(
        "console_script",
        (),
        frozenset({0}),
        expected_stdout=("local",),
    ),
    "sync-rules": EntrypointCase(
        "console_script",
        (),
        frozenset({1}),
        expected_stdout=("No .rules/compile-config.yaml",),
    ),
    "check-rules-drift": EntrypointCase(
        "console_script",
        (),
        frozenset({1}),
        expected_stdout=("No .rules/ directory",),
    ),
    "scaffold-local": EntrypointCase(
        "console_script",
        (),
        frozenset({0}),
        expected_stdout=(".local/ workspace initialized.",),
    ),
    "devola-init-doctor": EntrypointCase(
        "console_script",
        (),
        frozenset({1}),
        expected_stdout=("missing path(s)",),
    ),
    "devolaflow-plugins": EntrypointCase(
        "console_script",
        ("list", "--json"),
        frozenset({0}),
        expected_stdout=("[",),
        malformed_args=("not-a-command",),
        malformed_exit_codes=frozenset({2}),
        malformed_stderr=("invalid choice",),
    ),
    "devola-local-archive": EntrypointCase(
        "console_script",
        ("--repo-root", "{repo_root}"),
        frozenset({0}),
        expected_stdout=('"artifact_type"',),
        malformed_args=("--apply", "{repo_root}/missing-plan.json"),
        malformed_exit_codes=frozenset({2}),
        malformed_stdout=('"MALFORMED_PLAN"',),
    ),
}


_MODULE_CASES: dict[str, EntrypointCase] = {
    "devolaflow.build_skill": EntrypointCase(
        "python_module",
        ("--tools", "cursor"),
        frozenset({0}),
        expected_stdout=("[OK]",),
    ),
    "devolaflow.task_adaptive_selector": EntrypointCase(
        "python_module",
        ("feature",),
        frozenset({0}),
        expected_stdout=("Profile:",),
        malformed_args=(),
        malformed_exit_codes=frozenset({1}),
        malformed_stdout=("Usage:",),
    ),
    "devolaflow.local.workspace": EntrypointCase(
        "python_module",
        (),
        frozenset({0}),
        expected_stdout=(".local/ workspace scaffolded",),
    ),
    "devolaflow.pre_decision": EntrypointCase(
        "python_module",
        (),
        frozenset({0}),
        expected_stdout=("local",),
    ),
    "devolaflow.pre_decision.detect": EntrypointCase(
        "python_module",
        (),
        frozenset({0}),
        # The expected output makes the existing wrapper mismatch observable.
        expected_stdout=("local",),
    ),
    "devolaflow.skills.slash_commands": EntrypointCase(
        "python_module",
        ("--help",),
        frozenset({0}),
        expected_stdout=("usage:",),
        malformed_args=("not-a-command",),
        malformed_exit_codes=frozenset({2}),
        malformed_stderr=("invalid choice",),
    ),
    "devolaflow.agent_workspace.lint": EntrypointCase(
        "python_module",
        ("--human", "--repo-root", "{repo_root}", "--quiet"),
        frozenset({0}),
    ),
    "devolaflow.agent_workspace.reporter": EntrypointCase(
        "python_module",
        # The pinned clock keeps the captured stdout byte-identical across
        # repeated runs (AC-5 idempotency), so the functional result
        # artifact stays deterministic.
        (
            "--workspace",
            "--print",
            "--repo-root",
            "{repo_root}",
            "--now",
            "2026-08-28T00:00:00Z",
        ),
        frozenset({0}),
        expected_stdout=("# Agent Workspace Status",),
    ),
    "devolaflow.harness": EntrypointCase(
        "python_module",
        (
            "aggregate",
            "--ledger",
            "{repo_root}/tests/fixtures/harness/functional.jsonl",
        ),
        frozenset({0}),
        expected_stdout=('"schema_version"',),
        malformed_args=(),
        malformed_exit_codes=frozenset({2}),
        malformed_stderr=("the following arguments are required",),
    ),
    "devolaflow.hostbridge": EntrypointCase(
        "python_module",
        ("--host", "cursor"),
        frozenset({0}),
        expected_stdout=('"permission": "allow"',),
        valid_stdin="{}",
        malformed_args=("--host", "cursor", "--bad-flag"),
        malformed_exit_codes=frozenset({0}),
        malformed_stdout=('"permission": "allow"',),
    ),
}


def _entrypoint_cases() -> Mapping[str, EntrypointCase]:
    """Return the explicit case registry used by both adapters and tests."""
    return {**_CONSOLE_SCRIPT_CASES, **_MODULE_CASES}


def _subprocess_environment() -> dict[str, str]:
    environment = {
        key: value for key, value in os.environ.items() if not key.startswith("DEVOLAFLOW_")
    }
    environment.update({"LC_ALL": "C.UTF-8", "PYTHONHASHSEED": "0"})
    return environment


def _run_entrypoint_process(
    row: MatrixRow,
    repo_root: Path,
    *,
    malformed: bool = False,
) -> tuple[subprocess.CompletedProcess[str] | None, str | None]:
    if not row.entrypoint:
        return None, "matrix row does not declare an entrypoint"
    case = _entrypoint_cases().get(row.entrypoint)
    if case is None or case.kind != row.surface:
        return None, f"no explicit subprocess case for {row.surface}: {row.entrypoint}"

    args = case.malformed_args if malformed else case.valid_args
    if args is None:
        return None, "no malformed invocation is declared"
    args = _format_case_args(args, repo_root)
    if case.kind == "console_script":
        executable = repo_root / ".venv" / "bin" / row.entrypoint
        if not executable.is_file():
            resolved = shutil.which(row.entrypoint)
            if resolved is None:
                return None, f"installed console script is unavailable: {row.entrypoint}"
            executable = Path(resolved)
        command = [str(executable), *args]
    else:
        command = [sys.executable, "-m", row.entrypoint, *args]

    cwd = repo_root
    if row.entrypoint in {
        "build-skill",
        "devolaflow.build_skill",
        "devola-init",
        "detect-repo-mode",
        "sync-rules",
        "check-rules-drift",
        "scaffold-local",
        "devola-init-doctor",
        "devola-local-archive",
        "devolaflow.local.workspace",
        "devolaflow.pre_decision",
        "devolaflow.pre_decision.detect",
        "devolaflow.hostbridge",
    }:
        cwd = Path(tempfile.mkdtemp(prefix="devolaflow-functional-"))

    try:
        return (
            subprocess.run(
                command,
                cwd=cwd,
                env=_subprocess_environment(),
                input=case.malformed_stdin if malformed else case.valid_stdin,
                text=True,
                capture_output=True,
                timeout=case.timeout_seconds,
                check=False,
            ),
            None,
        )
    except subprocess.TimeoutExpired as exc:
        return None, f"subprocess timed out after {case.timeout_seconds:g}s: {exc}"
    finally:
        if cwd != repo_root:
            shutil.rmtree(cwd, ignore_errors=True)


def run_entrypoint(
    row: MatrixRow, repo_root: Path, *, malformed: bool = False
) -> FunctionalOutcome:
    """Execute a declared console/module entrypoint and inspect its protocol."""
    case = _entrypoint_cases().get(row.entrypoint or "")
    if case is None:
        return _outcome(row, OutcomeStatus.FAIL, f"no explicit subprocess case: {row.entrypoint}")
    process, error = _run_entrypoint_process(row, repo_root, malformed=malformed)
    if error:
        return _outcome(row, OutcomeStatus.FAIL, error)
    assert process is not None
    expected_codes = case.malformed_exit_codes if malformed else case.expected_exit_codes
    expected_stdout = case.malformed_stdout if malformed else case.expected_stdout
    expected_stderr = case.malformed_stderr if malformed else case.expected_stderr
    combined = process.stdout + process.stderr
    missing = [
        f"{stream} contains {marker!r}"
        for stream, markers in (
            ("stdout", expected_stdout),
            ("stderr", expected_stderr),
        )
        for marker in markers
        if marker not in getattr(process, stream)
    ]
    if process.returncode not in expected_codes or missing:
        details = {
            "argv": process.args,
            "returncode": process.returncode,
            "stdout": process.stdout,
            "stderr": process.stderr,
            "missing": missing,
        }
        message = "subprocess contract mismatch"
        if row.entrypoint == "devolaflow.pre_decision.detect" and not process.stdout:
            message = "pre_decision.detect wrapper mismatch: no mode was emitted"
        return _outcome(row, OutcomeStatus.FAIL, message, details=details)
    if not expected_stdout and not expected_stderr and not combined:
        return _outcome(row, OutcomeStatus.FAIL, "subprocess produced no captured output")
    return _outcome(
        row,
        OutcomeStatus.PASS,
        "subprocess executed with the declared output and exit contract",
        details={
            "argv": process.args,
            "returncode": process.returncode,
            "stdout": process.stdout,
            "stderr": process.stderr,
        },
    )


def _console_script_adapter(row: MatrixRow, repo_root: Path) -> FunctionalOutcome:
    return run_entrypoint(row, repo_root)


def _python_module_adapter(row: MatrixRow, repo_root: Path) -> FunctionalOutcome:
    return run_entrypoint(row, repo_root)


def _outcome(
    row: MatrixRow,
    status: OutcomeStatus,
    message: str,
    *,
    details: Mapping[str, Any] | None = None,
    prerequisite: str | None = None,
) -> FunctionalOutcome:
    return FunctionalOutcome(
        row_id=row.id,
        status=status,
        message=message,
        details=details,
        prerequisite=prerequisite,
    )


def _validate_matrix_adapter(row: MatrixRow, repo_root: Path) -> FunctionalOutcome:
    fixture_path = repo_root / row.fixture
    if not fixture_path.is_file():
        return _outcome(row, OutcomeStatus.FAIL, f"fixture does not exist: {row.fixture}")
    return _outcome(row, OutcomeStatus.PASS, "matrix fixture is available")


def _serialize_outcome_adapter(row: MatrixRow, _repo_root: Path) -> FunctionalOutcome:
    candidate = _outcome(row, OutcomeStatus.PASS, "typed outcome serialized")
    decoded = json.loads(candidate.to_json())
    if decoded["status"] != OutcomeStatus.PASS.value:
        return _outcome(row, OutcomeStatus.FAIL, "serialized status changed")
    return candidate


def _optional_prerequisite_adapter(row: MatrixRow, _repo_root: Path) -> FunctionalOutcome:
    reason = row.prerequisite
    if not reason:
        return _outcome(row, OutcomeStatus.FAIL, "optional row has no prerequisite reason")
    return _outcome(
        row,
        OutcomeStatus.SKIP_OPTIONAL,
        reason,
        prerequisite=reason,
    )


def _matrix_gate_adapter(row: MatrixRow, repo_root: Path) -> FunctionalOutcome:
    diagnostics = validate_matrix_file(repo_root / row.fixture, repo_root)
    if diagnostics:
        return _outcome(
            row,
            OutcomeStatus.FAIL,
            "matrix contract has diagnostics",
            details={"diagnostics": [item.to_dict() for item in diagnostics]},
        )
    return _outcome(row, OutcomeStatus.PASS, "matrix contract is valid")


def _check_gate_skips_adapter(row: MatrixRow, _repo_root: Path) -> FunctionalOutcome:
    from devolaflow.gate.models import CheckResult, GateInput
    from devolaflow.gate.profiles import STANDARD
    from devolaflow.gate.scorer import evaluate_gate

    gate_input = GateInput(
        build_status=CheckResult(status="pass"),
        test_results=CheckResult(status="pass"),
        lint_status=CheckResult(status="pass"),
        acceptance_criteria_results=CheckResult(status="pass"),
    )
    failed_checks: list[str] = []
    for check_name in (
        "build_status",
        "test_results",
        "lint_status",
        "acceptance_criteria_results",
    ):
        setattr(gate_input, check_name, CheckResult(status="skip"))
        verdict = evaluate_gate(gate_input, STANDARD)
        if verdict.decision != "FAIL":
            return _outcome(row, OutcomeStatus.FAIL, f"required {check_name} skip passed")
        failed_checks.append(check_name)
        setattr(gate_input, check_name, CheckResult(status="pass"))
    return _outcome(
        row,
        OutcomeStatus.PASS,
        "standard gate rejects every required skipped check",
        details={"checked": failed_checks},
    )


def _check_parallelism_adapter(row: MatrixRow, _repo_root: Path) -> FunctionalOutcome:
    from devolaflow.agent_workspace.dispatch_executor import ExecutorError
    from devolaflow.dispatch import dispatch_wave_tasks

    rejected: list[int] = []
    for value in (0, -1):
        wave = {
            "tasks": [{"task_id": "one"}, {"task_id": "two"}],
            "sync_barrier": {"mode": "parallel", "max_parallelism": value},
        }
        try:
            dispatch_wave_tasks(wave, lambda task: lambda: task["task_id"])
        except ExecutorError:
            rejected.append(value)
    if rejected != [0, -1]:
        return _outcome(row, OutcomeStatus.FAIL, "invalid parallelism was not rejected")
    return _outcome(row, OutcomeStatus.PASS, "explicit zero and negative parallelism are rejected")


def _check_async_dispatch_adapter(row: MatrixRow, _repo_root: Path) -> FunctionalOutcome:
    import asyncio

    from devolaflow.dispatch import async_dispatch_wave_tasks

    async def dispatch() -> list[Any]:
        wave = {
            "tasks": [{"task_id": "one"}, {"task_id": "two"}],
            "sync_barrier": {"mode": "parallel", "max_parallelism": 2},
        }
        return await async_dispatch_wave_tasks(wave, lambda task: lambda: task["task_id"])

    outcomes = asyncio.run(dispatch())
    observed = [outcome.result for outcome in outcomes]
    if observed != ["one", "two"] or not all(outcome.succeeded for outcome in outcomes):
        return _outcome(row, OutcomeStatus.FAIL, "async dispatch did not preserve task results")
    return _outcome(row, OutcomeStatus.PASS, "async dispatch works from an active event loop")


def _check_process_timeout_adapter(row: MatrixRow, _repo_root: Path) -> FunctionalOutcome:
    import time

    from devolaflow.dispatch import dispatch_wave_tasks

    with tempfile.TemporaryDirectory(prefix="devolaflow-timeout-") as directory:
        marker = Path(directory) / "late-side-effect"
        wave = {
            "tasks": [{"task_id": "slow", "timeout_seconds": 0.05}],
            "sync_barrier": {"mode": "all"},
        }

        def slow_callable() -> None:
            time.sleep(0.2)
            marker.write_text("must not be written", encoding="utf-8")

        outcomes = dispatch_wave_tasks(wave, lambda _task: slow_callable)
        time.sleep(0.25)
        timed_out = (
            len(outcomes) == 1
            and not outcomes[0].succeeded
            and isinstance(outcomes[0].exception, TimeoutError)
            and not marker.exists()
        )
    if not timed_out:
        return _outcome(row, OutcomeStatus.FAIL, "timed-out work left a side effect")
    return _outcome(row, OutcomeStatus.PASS, "timed-out synchronous work is process-isolated")


def _handoff_envelope(seq: int, task_id: str):
    from devolaflow.agent_workspace.handoff import make_envelope

    return make_envelope(
        seq=seq,
        from_layer="L0",
        to_layer="L2",
        change_id="functional-handoff",
        envelope_kind="TaskDispatch",
        payload={
            "task_id": task_id,
            "type": "implement",
            "acceptance_criteria_ref": ".local/.agent/active/functional/acceptance.md",
            "owned_files_ref": ".local/.agent/active/functional/owned_files.txt",
        },
        created="2026-08-28T10:00:00Z",
    )


def _check_handoff_adapter(row: MatrixRow, _repo_root: Path) -> FunctionalOutcome:
    from concurrent.futures import ThreadPoolExecutor

    from devolaflow.agent_workspace.handoff import EnvelopeImmutableError, HandoffStore

    with tempfile.TemporaryDirectory(prefix="devolaflow-handoff-") as directory:
        root = Path(directory)
        store = HandoffStore(repo_root=root)
        envelopes = (_handoff_envelope(1, "winner-a"), _handoff_envelope(1, "winner-b"))
        successes = 0
        collisions = 0
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(store.write_envelope, item) for item in envelopes]
            for future in futures:
                try:
                    future.result()
                except EnvelopeImmutableError:
                    collisions += 1
                else:
                    successes += 1
        stored = store.read_envelopes("functional-handoff")
    if (successes, collisions, [item.seq for item in stored]) != (1, 1, [1]):
        return _outcome(
            row, OutcomeStatus.FAIL, "handoff collision did not preserve one immutable file"
        )
    return _outcome(row, OutcomeStatus.PASS, "same-sequence handoff creation is exclusive")


def _check_proposal_containment_adapter(row: MatrixRow, repo_root: Path) -> FunctionalOutcome:
    from devolaflow.feedback import _filter_valid_proposals

    valid = [
        {"target_file": "src/devolaflow/dispatch.py"},
        {"target_file": "workflow-system/agent/SKILL.md"},
        {"target_file": "schemas/lean-dispatch.yaml"},
    ]
    invalid = [
        {"target_file": "../outside.py"},
        {"target_file": "src/devolaflow/../outside.py"},
        {"target_file": str(repo_root / "src/devolaflow/absolute.py")},
    ]
    accepted = _filter_valid_proposals(valid + invalid, repo_root=repo_root)
    if accepted != valid:
        return _outcome(
            row, OutcomeStatus.FAIL, "proposal filtering escaped repository containment"
        )
    return _outcome(
        row,
        OutcomeStatus.PASS,
        "proposal targets use canonical repository containment",
        details={"accepted": len(valid), "rejected": len(invalid)},
    )


def _write_archive_task(root: Path, name: str) -> Path:
    path = root / ".local" / "tasks" / name
    path.mkdir(parents=True)
    (path / "task.yaml").write_text("status: done\ncluster: quality\n", encoding="utf-8")
    (path / "context.txt").write_text(name, encoding="utf-8")
    return path


def _git_commit_fixture(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True, capture_output=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=functional-test",
            "-c",
            "user.email=functional-test@example.invalid",
            "commit",
            "-qm",
            "functional fixture",
        ],
        cwd=root,
        check=True,
        capture_output=True,
    )


def _check_archive_approval_adapter(row: MatrixRow, _repo_root: Path) -> FunctionalOutcome:
    from devolaflow.local.archive import ArchiveApproval, apply_archive_plan, build_archive_plan

    with tempfile.TemporaryDirectory(prefix="devolaflow-archive-") as directory:
        root = Path(directory)
        first = _write_archive_task(root, "first")
        second = _write_archive_task(root, "second")
        _git_commit_fixture(root)
        plan = build_archive_plan(root)
        selected = next(entry for entry in plan.entries if entry.source.endswith("/first"))
        approval = ArchiveApproval(plan_fingerprint=plan.fingerprint, entries=(selected.key,))
        result = apply_archive_plan(root, plan, approval)
        index = (root / ".local" / "tasks" / "INDEX.md").read_text(encoding="utf-8")
        first_moved = not first.exists()
        second_retained = second.exists()
    if (
        not result.success
        or not first_moved
        or not second_retained
        or selected.source not in index
        or any(entry.source in index for entry in plan.entries if entry is not selected)
    ):
        return _outcome(row, OutcomeStatus.FAIL, "archive approval did not select the exact entry")
    return _outcome(
        row, OutcomeStatus.PASS, "archive apply requires and honors an exact approval subset"
    )


def _check_archive_recovery_adapter(row: MatrixRow, _repo_root: Path) -> FunctionalOutcome:
    import devolaflow.local.archive as archive_module
    from devolaflow.local.archive import (
        ArchiveError,
        apply_archive_plan,
        build_archive_plan,
        inspect_safety,
    )

    with tempfile.TemporaryDirectory(prefix="devolaflow-archive-recovery-") as directory:
        root = Path(directory)
        first = _write_archive_task(root, "first")
        second = _write_archive_task(root, "second")
        _git_commit_fixture(root)
        plan = build_archive_plan(root)
        original_same_device = archive_module._same_device
        archive_module._same_device = lambda *_args: False
        try:
            inspection = inspect_safety(root, plan.entries[0].source, plan.entries[0].destination)
        finally:
            archive_module._same_device = original_same_device
        original_append = archive_module.append_mapping_record

        def fail_second(*args: Any, **kwargs: Any):
            if len(args) > 1 and str(args[1]).endswith("/second"):
                raise ArchiveError("functional mapping persistence failure")
            return original_append(*args, **kwargs)

        archive_module.append_mapping_record = fail_second
        try:
            result = apply_archive_plan(root, plan, tuple(plan.entries))
        finally:
            archive_module.append_mapping_record = original_append
    if (
        not result.refused
        or not result.recovery_required
        or len(result.mappings) != 1
        or first.exists()
        or second.exists()
        or not any(finding.code == "PARTIAL_APPLY" for finding in result.findings)
        or not any(finding.code == "CROSS_DEVICE" for finding in inspection.findings)
    ):
        return _outcome(
            row, OutcomeStatus.FAIL, "archive recovery or preflight evidence was incomplete"
        )
    return _outcome(
        row,
        OutcomeStatus.PASS,
        "archive preflight and partial-apply recovery are explicit",
        details={"recovery_required": result.recovery_required},
    )


def _check_archive_mapping_index_adapter(row: MatrixRow, _repo_root: Path) -> FunctionalOutcome:
    from devolaflow.local.archive import ArchiveApproval, apply_archive_plan, build_archive_plan

    with tempfile.TemporaryDirectory(prefix="devolaflow-archive-index-") as directory:
        root = Path(directory)
        _write_archive_task(root, "mapped")
        _write_archive_task(root, "retained")
        _git_commit_fixture(root)
        plan = build_archive_plan(root)
        selected = next(entry for entry in plan.entries if entry.source.endswith("/mapped"))
        result = apply_archive_plan(
            root,
            plan,
            ArchiveApproval(plan.fingerprint, (selected.key,)),
        )
        mapping = (root / ".local" / "tasks" / "archive-mappings.yaml").read_text(encoding="utf-8")
        index = (root / ".local" / "tasks" / "INDEX.md").read_text(encoding="utf-8")
    if (
        not result.success
        or "sequence: 1" not in mapping
        or "<!-- devolaflow: generated task archive index -->" not in index
        or selected.source not in index
        or "retained" in index
    ):
        return _outcome(
            row, OutcomeStatus.FAIL, "mapping ledger did not authoritatively drive the index"
        )
    return _outcome(
        row, OutcomeStatus.PASS, "mapping ledger and generated index remain append-only"
    )


def _check_compression_adapter(row: MatrixRow, _repo_root: Path) -> FunctionalOutcome:
    from devolaflow.compression_pipeline import CompressionPipeline

    class AddMarker:
        name = "add-marker"

        def should_bypass(self, _payload: str, _context: Mapping[str, Any]) -> bool:
            return False

        def transform(self, payload: str, _context: Mapping[str, Any]) -> str:
            return payload + "!"

    class ObserveMarker:
        name = "observe-marker"

        def should_bypass(self, _payload: str, _context: Mapping[str, Any]) -> bool:
            return False

        def transform(self, payload: str, _context: Mapping[str, Any]) -> str:
            return payload + "?"

    result = CompressionPipeline(stages=(AddMarker(), ObserveMarker())).run("payload")
    if result.payload != "payload!?" or result.applied_stages != ("add-marker", "observe-marker"):
        return _outcome(row, OutcomeStatus.FAIL, "compression stages did not reduce sequentially")
    return _outcome(row, OutcomeStatus.PASS, "compression protocol and sequential reducer are live")


def _check_lifecycle_adapter(row: MatrixRow, _repo_root: Path) -> FunctionalOutcome:
    from devolaflow.lifecycle.dispatcher import (
        HookResult,
        HookViolation,
        clear_hooks,
        register_hook,
        run_hooks,
    )

    event = "functional-loop3-hooks"
    payload = {"nested": {"value": "original"}}

    def broken_handler(received: dict[str, Any], *, strict: bool = False) -> HookResult:
        del strict
        received["nested"]["value"] = "mutated"
        raise RuntimeError("functional handler failure")

    register_hook(event, broken_handler)
    try:
        result = run_hooks(event, payload)
        try:
            run_hooks(event, payload, strict=True)
        except HookViolation:
            strict_raised = True
        else:
            strict_raised = False
    finally:
        clear_hooks(event)
    if (
        result.passed
        or not strict_raised
        or result.violations[0].code != "LIFECYCLE_HANDLER_EXCEPTION"
        or payload != {"nested": {"value": "original"}}
    ):
        return _outcome(row, OutcomeStatus.FAIL, "lifecycle handler isolation contract failed")
    return _outcome(
        row, OutcomeStatus.PASS, "permissive hooks isolate failures and strict hooks raise"
    )


def _isolated_child_environment(
    *, home: Path | None = None, path: Path | None = None
) -> dict[str, str]:
    environment = _subprocess_environment()
    environment["PYTHONNOUSERSITE"] = "1"
    if home is not None:
        environment["HOME"] = str(home)
    if path is not None:
        environment["PATH"] = f"{path}{os.pathsep}{environment['PATH']}"
    return environment


def _check_wheel_adapter(row: MatrixRow, repo_root: Path) -> FunctionalOutcome:
    project_python = repo_root / ".venv" / "bin" / "python"
    uv = shutil.which("uv")
    if not project_python.is_file() or uv is None:
        return _outcome(
            row,
            OutcomeStatus.SKIP_OPTIONAL,
            row.prerequisite or "wheel build prerequisites are unavailable",
            prerequisite=row.prerequisite,
            details={"python": project_python.is_file(), "uv": uv is not None},
        )
    with tempfile.TemporaryDirectory(prefix="devolaflow-wheel-functional-") as directory:
        root = Path(directory)
        wheel_dir = root / "wheelhouse"
        wheel_dir.mkdir()
        build = subprocess.run(
            [uv, "build", "--wheel", "--offline", "--out-dir", str(wheel_dir)],
            cwd=repo_root,
            env=_isolated_child_environment(),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        wheels = sorted(wheel_dir.glob("devolaflow-*.whl"))
        if build.returncode != 0 or len(wheels) != 1:
            return _outcome(row, OutcomeStatus.FAIL, "offline wheel build failed")
        consumer = root / "consumer"
        create = subprocess.run(
            [str(project_python), "-m", "venv", str(consumer)],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        consumer_python = consumer / "bin" / "python"
        if create.returncode != 0:
            return _outcome(row, OutcomeStatus.FAIL, "consumer environment creation failed")
        install = subprocess.run(
            [
                str(consumer_python),
                "-m",
                "pip",
                "install",
                "--no-index",
                "--no-deps",
                str(wheels[0]),
            ],
            env=_isolated_child_environment(home=root / "home", path=consumer / "bin"),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if install.returncode != 0:
            return _outcome(row, OutcomeStatus.FAIL, "wheel-only installation failed")
        from devolaflow import __version__ as checkout_version

        probe = subprocess.run(
            [
                str(consumer_python),
                "-c",
                (
                    "import devolaflow; "
                    "from devolaflow.compression_pipeline import CompressionPipeline; "
                    f"assert devolaflow.__version__ == {checkout_version!r}; "
                    "assert CompressionPipeline().run('wheel').payload == 'wheel'"
                ),
            ],
            cwd=root,
            env=_isolated_child_environment(home=root / "home", path=consumer / "bin"),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    if probe.returncode != 0:
        return _outcome(row, OutcomeStatus.FAIL, "wheel consumer API probe failed")
    return _outcome(row, OutcomeStatus.PASS, "offline wheel build and isolated API import passed")


def _check_wheel_local_adapter(row: MatrixRow, repo_root: Path) -> FunctionalOutcome:
    project_python = repo_root / ".venv" / "bin" / "python"
    uv = shutil.which("uv")
    if not project_python.is_file() or uv is None:
        return _outcome(
            row,
            OutcomeStatus.SKIP_OPTIONAL,
            row.prerequisite or "wheel build prerequisites are unavailable",
            prerequisite=row.prerequisite,
        )
    with tempfile.TemporaryDirectory(prefix="devolaflow-wheel-local-") as directory:
        root = Path(directory)
        wheel_dir = root / "wheelhouse"
        wheel_dir.mkdir()
        build = subprocess.run(
            [uv, "build", "--wheel", "--offline", "--out-dir", str(wheel_dir)],
            cwd=repo_root,
            env=_isolated_child_environment(),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        wheels = sorted(wheel_dir.glob("devolaflow-*.whl"))
        if build.returncode != 0 or len(wheels) != 1:
            return _outcome(row, OutcomeStatus.FAIL, "offline wheel build failed")
        consumer = root / "consumer"
        subprocess.run(
            [str(project_python), "-m", "venv", str(consumer)],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        consumer_python = consumer / "bin" / "python"
        install = subprocess.run(
            [
                str(consumer_python),
                "-m",
                "pip",
                "install",
                "--no-index",
                "--no-deps",
                str(wheels[0]),
            ],
            env=_isolated_child_environment(home=root / "home", path=consumer / "bin"),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if install.returncode != 0:
            return _outcome(row, OutcomeStatus.FAIL, "wheel-only installation failed")
        dependencies = subprocess.run(
            [
                uv,
                "pip",
                "install",
                "--offline",
                "--python",
                str(consumer_python),
                "pyyaml>=6.0",
                "jsonschema>=4.20",
                "Jinja2>=3.1",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if dependencies.returncode != 0:
            return _outcome(row, OutcomeStatus.FAIL, "offline wheel dependency installation failed")
        init = subprocess.run(
            [str(consumer / "bin" / "devola-init"), "local", "--no-compile"],
            cwd=consumer,
            env=_isolated_child_environment(home=root / "home", path=consumer / "bin"),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        valid = (
            init.returncode == 0
            and (consumer / ".local").is_dir()
            and (consumer / ".local" / "index.md").is_file()
            and (consumer / ".rules" / "compile-config.yaml").is_file()
            and not (consumer / "workflow-system").exists()
        )
    if not valid:
        return _outcome(row, OutcomeStatus.FAIL, "wheel-only local initialization failed")
    return _outcome(row, OutcomeStatus.PASS, "wheel-only local initialization passed")


def _check_npm_adapter(row: MatrixRow, repo_root: Path) -> FunctionalOutcome:
    npm = shutil.which("npm")
    node = shutil.which("node")
    if npm is None or node is None:
        return _outcome(
            row,
            OutcomeStatus.SKIP_OPTIONAL,
            row.prerequisite or "npm and node are unavailable for offline package testing",
            prerequisite=row.prerequisite,
            details={"node": node is not None, "npm": npm is not None},
        )
    package_dir = repo_root / "packages" / "npm"
    with tempfile.TemporaryDirectory(prefix="devolaflow-npm-functional-") as directory:
        root = Path(directory)
        environment = _isolated_child_environment(home=root / "home")
        dry_run = subprocess.run(
            [npm, "pack", "--dry-run", "--offline", "--ignore-scripts", "--json"],
            cwd=package_dir,
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if dry_run.returncode != 0:
            return _outcome(row, OutcomeStatus.FAIL, "offline npm dry-run failed")
        try:
            dry_metadata = json.loads(dry_run.stdout)
            dry_files = {entry["path"] for entry in dry_metadata[0]["files"]}
        except (IndexError, KeyError, TypeError, json.JSONDecodeError):
            return _outcome(row, OutcomeStatus.FAIL, "npm dry-run output was malformed")
        packed_dir = root / "packed"
        packed_dir.mkdir()
        packed = subprocess.run(
            [
                npm,
                "pack",
                "--offline",
                "--ignore-scripts",
                "--json",
                "--pack-destination",
                str(packed_dir),
            ],
            cwd=package_dir,
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if packed.returncode != 0:
            return _outcome(row, OutcomeStatus.FAIL, "offline npm pack failed")
        try:
            tarball = packed_dir / json.loads(packed.stdout)[0]["filename"]
            with tarfile.open(tarball) as archive:
                names = archive.getnames()
                archive.extractall(root / "extracted")
        except (IndexError, KeyError, TypeError, json.JSONDecodeError, OSError, tarfile.TarError):
            return _outcome(row, OutcomeStatus.FAIL, "npm tarball output was malformed")
        packed_bin = root / "extracted" / "package" / "bin" / "devola-flow.js"
        help_result = subprocess.run(
            [node, str(packed_bin), "--help"],
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        version_result = subprocess.run(
            [node, str(packed_bin), "--version"],
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        files_result = subprocess.run(
            [
                node,
                str(packed_bin),
                "files",
                "cursor",
                "--manifest-file",
                str(repo_root / "workflow-system" / "agent" / "manifest.yaml"),
            ],
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    from devolaflow import __version__ as checkout_version

    valid = (
        "bin/devola-flow.js" in dry_files
        and "package.json" in dry_files
        and all(not path.startswith("src/") for path in dry_files)
        and "package/bin/devola-flow.js" in names
        and help_result.returncode == 0
        and "install <cursor|claude|codex|kimicode|dsh|all>" in help_result.stdout
        and version_result.returncode == 0
        and version_result.stdout.strip() == checkout_version
        and files_result.returncode == 0
        and "SKILL.md" in files_result.stdout.splitlines()
    )
    if not valid:
        return _outcome(row, OutcomeStatus.FAIL, "packed npm executable contract failed")
    return _outcome(row, OutcomeStatus.PASS, "offline npm pack and packed executable passed")


def _check_plugin_adapter(row: MatrixRow, repo_root: Path) -> FunctionalOutcome:
    import yaml

    from devolaflow.plugins import load_registry
    from devolaflow.plugins.installer import available_plugin_profiles, select_plugin_profile
    from devolaflow.plugins.loader import create_default_registry

    runtime_path = repo_root / "workflow-system" / "agent" / "knowledge" / "runtime-plugins.yaml"
    view_path = repo_root / "workflow-system" / "agent" / "plugins.yaml"
    runtime = load_registry(runtime_path)
    view = yaml.safe_load(view_path.read_text(encoding="utf-8"))
    plugin_ids = [entry["id"] for entry in runtime["plugins"]]
    expected_ids = ["ui-pro", "codegraph", "impeccable"]
    expected_default_ids = ["codegraph", "impeccable"]
    profiles = available_plugin_profiles(registry_path=runtime_path)
    registry = create_default_registry(plugins_yaml=view_path)
    if (
        plugin_ids != expected_ids
        or runtime["defaults"]["auto_install"] is not False
        or any(entry.get("tier") != "suggest" for entry in runtime["plugins"])
        or profiles["all"] != expected_default_ids
        or profiles["global"] != expected_default_ids
        or any(
            entry.get("default_install", True) is not (entry["id"] in expected_default_ids)
            for entry in runtime["plugins"]
        )
        or any(
            select_plugin_profile(plugin_id, registry_path=runtime_path) != [plugin_id]
            for plugin_id in expected_ids
        )
        or sorted(spec.name for spec in registry.list_plugins()) != sorted(expected_ids)
        or set(view["plugins"]) != set(expected_ids)
    ):
        return _outcome(row, OutcomeStatus.FAIL, "plugin SSOT/profile parity contract failed")
    return _outcome(
        row, OutcomeStatus.PASS, "plugin SSOT parity and explicit optional profiles passed"
    )


def _hostbridge_process(repo: Path, host: str, payload: str) -> subprocess.CompletedProcess[str]:
    environment = _isolated_child_environment()
    environment["DEVOLAFLOW_HOST_ENFORCE"] = "1"
    environment["PYTHONPATH"] = str(Path(__file__).parents[2] / "src")
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "devolaflow.hostbridge",
            "--host",
            host,
            "--repo-root",
            str(repo),
        ],
        cwd=repo,
        env=environment,
        input=payload,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )


def _check_hostbridge_adapter(row: MatrixRow, _repo_root: Path) -> FunctionalOutcome:
    with tempfile.TemporaryDirectory(prefix="devolaflow-hostbridge-") as directory:
        repo = Path(directory)
        owned = repo / ".local" / ".agent" / "active" / "functional"
        owned.mkdir(parents=True)
        (owned / "owned_files.txt").write_text("src/owned.py\n", encoding="utf-8")
        cursor_deny = _hostbridge_process(
            repo,
            "cursor",
            json.dumps({"tool": "Write", "tool_input": {"path": "src/evil.py"}}),
        )
        cursor_allow = _hostbridge_process(
            repo,
            "cursor",
            json.dumps({"tool": "Write", "tool_input": {"path": "src/owned.py"}}),
        )
        copilot = _hostbridge_process(
            repo,
            "copilot",
            json.dumps({"toolName": "edit", "toolArgs": {"file_path": "src/evil.py"}}),
        )
    valid = (
        cursor_deny.returncode == 0
        and json.loads(cursor_deny.stdout)["permission"] == "deny"
        and cursor_allow.returncode == 0
        and json.loads(cursor_allow.stdout)["permission"] == "allow"
        and copilot.returncode == 0
        and json.loads(copilot.stdout)["permissionDecision"] == "deny"
    )
    if not valid:
        return _outcome(row, OutcomeStatus.FAIL, "hostbridge process protocol failed")
    return _outcome(row, OutcomeStatus.PASS, "hostbridge synthetic process protocol passed")


def _write_executable(path: Path, body: str) -> None:
    path.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
    path.chmod(0o755)


def _check_codegraph_adapter(row: MatrixRow, _repo_root: Path) -> FunctionalOutcome:
    with tempfile.TemporaryDirectory(prefix="devolaflow-codegraph-") as directory:
        root = Path(directory)
        binary_dir = root / "bin"
        binary_dir.mkdir()
        _write_executable(
            binary_dir / "codegraph",
            (
                'if [ "$1" = "search" ]; then printf \'[{"name":"dispatch_wave_tasks"}]\\n\'; '
                'elif [ "$1" = "impact" ]; then printf \'{"nodes":1}\\n\'; '
                "else printf '# context\\n'; fi"
            ),
        )
        previous_path = os.environ.get("PATH")
        os.environ["PATH"] = str(binary_dir)
        try:
            from devolaflow.codegraph.researcher import get_impact, search_symbols

            symbols = search_symbols("dispatch", cwd=root)
            impact = get_impact("dispatch_wave_tasks", cwd=root)
        finally:
            if previous_path is None:
                os.environ.pop("PATH", None)
            else:
                os.environ["PATH"] = previous_path
    if symbols != [{"name": "dispatch_wave_tasks"}] or impact != {"nodes": 1}:
        return _outcome(row, OutcomeStatus.FAIL, "codegraph fake process protocol failed")
    return _outcome(row, OutcomeStatus.PASS, "codegraph fake process protocol passed")


def _check_network_adapter(row: MatrixRow, _repo_root: Path) -> FunctionalOutcome:
    denied: list[str] = []
    for label, operation in (
        ("socket", lambda: socket.create_connection(("127.0.0.1", 9))),
        ("urllib", lambda: urllib.request.urlopen("http://example.invalid", timeout=1)),
        ("http", lambda: http.client.HTTPConnection("example.invalid")),
    ):
        try:
            operation()
        except NetworkAccessDenied:
            denied.append(label)
    if denied != ["socket", "urllib", "http"]:
        return _outcome(
            row, OutcomeStatus.FAIL, "runner network denial did not cover all request paths"
        )
    return _outcome(
        row, OutcomeStatus.PASS, "socket, urllib, and HTTP requests are denied in-process"
    )


def _check_telemetry_adapter(row: MatrixRow, _repo_root: Path) -> FunctionalOutcome:
    candidate = _outcome(row, OutcomeStatus.PASS, "deterministic telemetry probe")
    first = serialize_outcomes([candidate])
    second = serialize_outcomes([candidate])
    if first != second or json.loads(first)[0]["status"] != "PASS":
        return _outcome(
            row, OutcomeStatus.FAIL, "functional telemetry serialization was not deterministic"
        )
    return _outcome(row, OutcomeStatus.PASS, "functional telemetry serialization is deterministic")


# Explicit registry ownership is intentional.  Do not derive imports from
# ``call`` values in matrix.yaml.
ADAPTERS: dict[str, Adapter] = {
    "validate_matrix_contract": _validate_matrix_adapter,
    "serialize_outcome": _serialize_outcome_adapter,
    "optional_prerequisite_skip": _optional_prerequisite_adapter,
    "check_matrix_contract": _matrix_gate_adapter,
    "run_console_script": _console_script_adapter,
    "run_python_module": _python_module_adapter,
    "check_gate_skips": _check_gate_skips_adapter,
    "check_parallelism": _check_parallelism_adapter,
    "check_async_dispatch": _check_async_dispatch_adapter,
    "check_process_timeout": _check_process_timeout_adapter,
    "check_handoff_exclusive_create": _check_handoff_adapter,
    "check_proposal_containment": _check_proposal_containment_adapter,
    "check_archive_approval": _check_archive_approval_adapter,
    "check_archive_recovery": _check_archive_recovery_adapter,
    "check_archive_mapping_index": _check_archive_mapping_index_adapter,
    "check_compression_protocol": _check_compression_adapter,
    "check_lifecycle_hooks": _check_lifecycle_adapter,
    "check_wheel_api": _check_wheel_adapter,
    "check_wheel_local": _check_wheel_local_adapter,
    "check_npm_delivery": _check_npm_adapter,
    "check_plugin_ssot_profiles": _check_plugin_adapter,
    "check_hostbridge_process": _check_hostbridge_adapter,
    "check_codegraph_process": _check_codegraph_adapter,
    "check_network_denial": _check_network_adapter,
    "check_telemetry_serialization": _check_telemetry_adapter,
}


def _diagnostic(row_id: str, code: str, message: str) -> MatrixDiagnostic:
    return MatrixDiagnostic(row_id=row_id, code=code, message=message)


def _path_is_safe(value: str, root: Path) -> bool:
    path = Path(value)
    resolved_root = root.resolve()
    resolved_path = (resolved_root / path).resolve()
    return (
        bool(value)
        and not path.is_absolute()
        and ".." not in path.parts
        and resolved_path.is_relative_to(resolved_root)
        and resolved_path.is_file()
    )


def _anchor_path(anchor: str) -> str:
    return anchor.split("#", 1)[0]


def _validate_row(
    raw: Any,
    index: int,
    repo_root: Path,
    seen_ids: set[str],
    seen_surfaces: set[tuple[str, str, str | None]],
) -> tuple[MatrixRow | None, list[MatrixDiagnostic]]:
    row_id = f"row[{index}]"
    if isinstance(raw, Mapping) and isinstance(raw.get("id"), str) and raw["id"]:
        row_id = raw["id"]
    diagnostics: list[MatrixDiagnostic] = []
    if not isinstance(raw, Mapping):
        return None, [_diagnostic(row_id, "malformed_row", "row must be a mapping")]

    unknown = sorted(set(raw) - ALLOWED_ROW_FIELDS)
    for field_name in unknown:
        diagnostics.append(_diagnostic(row_id, "unknown_field", f"unknown row field: {field_name}"))
    missing = sorted(REQUIRED_ROW_FIELDS - set(raw))
    for field_name in missing:
        diagnostics.append(
            _diagnostic(row_id, "missing_field", f"missing required field: {field_name}")
        )

    def string_field(name: str) -> str | None:
        value = raw.get(name)
        if not isinstance(value, str) or not value.strip():
            diagnostics.append(
                _diagnostic(row_id, "invalid_field", f"{name} must be a non-empty string")
            )
            return None
        return value

    id_value = string_field("id")
    domain = string_field("domain")
    surface = string_field("surface")
    call = string_field("call")
    fixture = string_field("fixture")
    tier = string_field("tier")
    expected = string_field("expected")
    entrypoint = raw.get("entrypoint")
    if entrypoint is not None and (not isinstance(entrypoint, str) or not entrypoint.strip()):
        diagnostics.append(
            _diagnostic(row_id, "invalid_field", "entrypoint must be a non-empty string")
        )
        entrypoint = None

    required = raw.get("required")
    if not isinstance(required, bool):
        diagnostics.append(_diagnostic(row_id, "invalid_field", "required must be boolean"))
        required = True

    sources = raw.get("design_source")
    if (
        not isinstance(sources, list)
        or not sources
        or not all(isinstance(item, str) and item.strip() for item in sources)
    ):
        diagnostics.append(
            _diagnostic(row_id, "invalid_field", "design_source must be a non-empty string list")
        )
        sources = []

    expected_status_raw = raw.get("expected_status", OutcomeStatus.PASS.value)
    try:
        expected_status = OutcomeStatus(expected_status_raw)
    except (TypeError, ValueError):
        diagnostics.append(
            _diagnostic(
                row_id,
                "invalid_field",
                "expected_status must be PASS, FAIL, SKIP_OPTIONAL, or INSUFFICIENT",
            )
        )
        expected_status = OutcomeStatus.PASS

    prerequisite = raw.get("prerequisite")
    if prerequisite is not None and (not isinstance(prerequisite, str) or not prerequisite.strip()):
        diagnostics.append(
            _diagnostic(row_id, "invalid_field", "prerequisite must be a non-empty string")
        )
        prerequisite = None

    if id_value is not None:
        if id_value in seen_ids:
            diagnostics.append(_diagnostic(row_id, "duplicate_id", "row ID is not unique"))
        seen_ids.add(id_value)
    if surface in {"console_script", "python_module"} and entrypoint is None:
        diagnostics.append(
            _diagnostic(row_id, "missing_entrypoint", f"{surface} rows must declare entrypoint")
        )
    if surface == "console_script" and entrypoint is not None:
        if entrypoint not in _CONSOLE_SCRIPT_CASES:
            diagnostics.append(_diagnostic(row_id, "unknown_entrypoint", entrypoint))
        elif call != "run_console_script":
            diagnostics.append(
                _diagnostic(row_id, "wrong_adapter", "console_script needs run_console_script")
            )
    if surface == "python_module" and entrypoint is not None:
        if entrypoint not in _MODULE_CASES:
            diagnostics.append(_diagnostic(row_id, "unknown_entrypoint", entrypoint))
        elif call != "run_python_module":
            diagnostics.append(
                _diagnostic(row_id, "wrong_adapter", "python_module needs run_python_module")
            )

    callable_surface = None
    if (
        surface in {"console_script", "python_module"}
        and call is not None
        and entrypoint is not None
    ):
        callable_surface = (surface, call, entrypoint)
    elif surface is not None and call is not None:
        callable_surface = (surface, call, None)
    if callable_surface is not None:
        if callable_surface in seen_surfaces:
            diagnostics.append(
                _diagnostic(row_id, "duplicate_surface", "surface/call semantics are not unique")
            )
        seen_surfaces.add(callable_surface)

    if domain is not None and domain not in KNOWN_DOMAINS:
        diagnostics.append(_diagnostic(row_id, "unknown_domain", f"unknown domain: {domain}"))
    if surface is not None and surface not in KNOWN_SURFACES:
        diagnostics.append(_diagnostic(row_id, "unknown_surface", f"unknown surface: {surface}"))
    if tier is not None and tier not in KNOWN_TIERS:
        diagnostics.append(_diagnostic(row_id, "unknown_tier", f"unknown tier: {tier}"))
    if call is not None and call not in ADAPTERS:
        diagnostics.append(_diagnostic(row_id, "missing_adapter", f"no adapter registered: {call}"))

    if fixture is not None and not _path_is_safe(fixture, repo_root):
        diagnostics.append(
            _diagnostic(
                row_id,
                "invalid_path",
                f"fixture must be an existing repository-relative file: {fixture}",
            )
        )
    for source in sources:
        source_path = _anchor_path(source)
        if "#" not in source or not source.split("#", 1)[1].strip():
            diagnostics.append(
                _diagnostic(
                    row_id,
                    "invalid_anchor",
                    f"design source must include a non-empty anchor: {source}",
                )
            )
        if not _path_is_safe(source_path, repo_root):
            diagnostics.append(
                _diagnostic(
                    row_id,
                    "invalid_path",
                    f"design source must be an existing repository-relative file: {source}",
                )
            )

    if not required and not prerequisite:
        diagnostics.append(
            _diagnostic(
                row_id,
                "unclassified_skip",
                "optional rows must declare an explicit prerequisite reason",
            )
        )
    if required and expected_status is not OutcomeStatus.PASS:
        diagnostics.append(
            _diagnostic(
                row_id,
                "required_gap",
                "required rows must expect PASS; unavailable evidence is a gap",
            )
        )
    if expected is not None and "insufficient" in expected.casefold():
        diagnostics.append(
            _diagnostic(
                row_id,
                "required_gap",
                "expected behavior cannot claim INSUFFICIENT evidence",
            )
        )

    if diagnostics or None in (id_value, domain, surface, call, fixture, tier, expected):
        return None, diagnostics
    return (
        MatrixRow(
            id=id_value,
            domain=domain,
            surface=surface,
            call=call,
            fixture=fixture,
            tier=tier,
            required=required,
            expected=expected,
            design_source=tuple(sources),
            expected_status=expected_status,
            prerequisite=prerequisite,
            entrypoint=entrypoint,
        ),
        diagnostics,
    )


def validate_matrix_payload(
    payload: Any,
    repo_root: Path | None = None,
) -> tuple[MatrixDiagnostic, ...]:
    """Validate a parsed matrix payload without executing any adapter."""
    root = (repo_root or Path.cwd()).resolve()
    diagnostics: list[MatrixDiagnostic] = []
    if not isinstance(payload, Mapping):
        return (_diagnostic("matrix", "malformed_schema", "document must be a mapping"),)

    for field_name in sorted(set(payload) - ALLOWED_DOCUMENT_FIELDS):
        diagnostics.append(
            _diagnostic("matrix", "unknown_field", f"unknown document field: {field_name}")
        )
    for field_name in sorted(ALLOWED_DOCUMENT_FIELDS - set(payload)):
        diagnostics.append(
            _diagnostic("matrix", "missing_field", f"missing required document field: {field_name}")
        )

    if payload.get("schema_version") != SCHEMA_VERSION:
        diagnostics.append(
            _diagnostic(
                "matrix",
                "invalid_schema_version",
                f"schema_version must be {SCHEMA_VERSION}",
            )
        )
    if payload.get("mode") != "offline":
        diagnostics.append(_diagnostic("matrix", "invalid_mode", "mode must be offline"))

    defaults = payload.get("defaults")
    if not isinstance(defaults, Mapping):
        diagnostics.append(_diagnostic("matrix", "malformed_schema", "defaults must be a mapping"))
    else:
        for field_name in sorted(set(defaults) - ALLOWED_DEFAULT_FIELDS):
            diagnostics.append(
                _diagnostic("matrix", "unknown_field", f"unknown defaults field: {field_name}")
            )
        expected_defaults = ALLOWED_DEFAULT_FIELDS
        for field_name in sorted(expected_defaults - set(defaults)):
            diagnostics.append(
                _diagnostic("matrix", "missing_field", f"missing defaults field: {field_name}")
            )
        timeout = defaults.get("timeout_seconds")
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout <= 0:
            diagnostics.append(
                _diagnostic("matrix", "invalid_default", "timeout_seconds must be positive")
            )
        if defaults.get("network") != "forbidden":
            diagnostics.append(
                _diagnostic("matrix", "invalid_default", "network must be forbidden")
            )
        if defaults.get("unclassified_outcome") != "fail":
            diagnostics.append(
                _diagnostic("matrix", "invalid_default", "unclassified_outcome must be fail")
            )
        if defaults.get("required_skip") != "fail":
            diagnostics.append(
                _diagnostic("matrix", "invalid_default", "required_skip must be fail")
            )

    rows = payload.get("rows")
    if not isinstance(rows, list):
        diagnostics.append(_diagnostic("matrix", "malformed_schema", "rows must be a list"))
        return tuple(diagnostics)
    if not rows:
        diagnostics.append(
            _diagnostic("matrix", "zero_rows", "matrix must contain at least one row")
        )

    seen_ids: set[str] = set()
    seen_surfaces: set[tuple[str, str, str | None]] = set()
    for index, raw_row in enumerate(rows):
        _, row_diagnostics = _validate_row(raw_row, index, root, seen_ids, seen_surfaces)
        diagnostics.extend(row_diagnostics)

    entrypoint_rows = [
        row
        for row in rows
        if isinstance(row, Mapping) and row.get("surface") in {"console_script", "python_module"}
    ]
    if entrypoint_rows:
        try:
            expected_console = set(load_console_script_inventory(root))
        except (OSError, tomllib.TOMLDecodeError, ValueError) as exc:
            diagnostics.append(
                _diagnostic(
                    "matrix", "inventory_unavailable", f"cannot read console inventory: {exc}"
                )
            )
            expected_console = set()
        actual_console = {
            row.get("entrypoint")
            for row in entrypoint_rows
            if row.get("surface") == "console_script" and isinstance(row.get("entrypoint"), str)
        }
        for entrypoint in sorted(expected_console - actual_console):
            diagnostics.append(
                _diagnostic(
                    "matrix",
                    "inventory_missing",
                    f"console script has no matrix row: {entrypoint}",
                )
            )
        for entrypoint in sorted(actual_console - expected_console):
            diagnostics.append(
                _diagnostic(
                    "matrix",
                    "inventory_extra",
                    f"matrix names unknown console script: {entrypoint}",
                )
            )

        actual_modules = {
            row.get("entrypoint")
            for row in entrypoint_rows
            if row.get("surface") == "python_module" and isinstance(row.get("entrypoint"), str)
        }
        for entrypoint in sorted(set(MAINTAINED_MODULE_ENTRYPOINTS) - actual_modules):
            diagnostics.append(
                _diagnostic(
                    "matrix",
                    "inventory_missing",
                    f"maintained module has no matrix row: {entrypoint}",
                )
            )
        for entrypoint in sorted(actual_modules - set(MAINTAINED_MODULE_ENTRYPOINTS)):
            diagnostics.append(
                _diagnostic(
                    "matrix",
                    "inventory_extra",
                    f"matrix names unknown maintained module: {entrypoint}",
                )
            )
    return tuple(diagnostics)


def validate_matrix_file(
    matrix_path: Path,
    repo_root: Path | None = None,
) -> tuple[MatrixDiagnostic, ...]:
    """Read and validate a matrix file, returning deterministic diagnostics."""
    root = (repo_root or Path.cwd()).resolve()
    path = Path(matrix_path)
    if not path.is_absolute():
        path = root / path
    if not path.is_file():
        return (
            _diagnostic(
                "matrix",
                "missing_file",
                f"matrix file does not exist: {path.as_posix()}",
            ),
        )
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        return (_diagnostic("matrix", "malformed_schema", f"cannot read YAML: {exc}"),)
    return validate_matrix_payload(payload, root)


def load_matrix(
    matrix_path: Path | None = None,
    repo_root: Path | None = None,
) -> MatrixDocument:
    """Load a valid matrix and normalize rows for adapter execution."""
    root = (repo_root or Path.cwd()).resolve()
    path = Path(matrix_path or MATRIX_RELATIVE_PATH)
    if not path.is_absolute():
        path = root / path
    diagnostics = validate_matrix_file(path, root)
    if diagnostics:
        raise MatrixValidationError(diagnostics)
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    rows = tuple(
        _validate_row(raw, index, root, set(), set())[0]
        for index, raw in enumerate(payload["rows"])
    )
    return MatrixDocument(
        schema_version=payload["schema_version"],
        mode=payload["mode"],
        defaults=dict(payload["defaults"]),
        rows=tuple(row for row in rows if row is not None),
    )


def select_rows(document: MatrixDocument, tier: str = "fast") -> tuple[MatrixRow, ...]:
    """Select one declared tier without changing the matrix inventory."""
    if tier not in KNOWN_TIERS:
        raise ValueError(f"unknown functional tier: {tier}")
    return tuple(row for row in document.rows if row.tier == tier)


def run_row(row: MatrixRow, repo_root: Path | None = None) -> FunctionalOutcome:
    """Execute one explicit adapter and return a policy-aware typed outcome."""
    root = (repo_root or Path.cwd()).resolve()
    adapter = ADAPTERS.get(row.call)
    if adapter is None:
        return _outcome(row, OutcomeStatus.FAIL, f"no adapter registered: {row.call}")
    try:
        with _deny_network():
            result = adapter(row, root)
    except Exception as exc:  # noqa: BLE001 - convert unclassified adapter errors
        LOGGER.exception("functional adapter failed for row %s", row.id)
        return _outcome(
            row,
            OutcomeStatus.FAIL,
            f"adapter raised {type(exc).__name__}: {exc}",
            details={"network_policy": _network_policy_details()},
        )
    if not isinstance(result, FunctionalOutcome):
        return _outcome(
            row,
            OutcomeStatus.FAIL,
            f"adapter returned {type(result).__name__}, expected FunctionalOutcome",
            details={"network_policy": _network_policy_details()},
        )
    if result.row_id != row.id:
        return _outcome(
            row,
            OutcomeStatus.FAIL,
            "adapter returned the wrong row ID",
            details={"network_policy": _network_policy_details()},
        )
    if result.status is OutcomeStatus.SKIP_OPTIONAL:
        if row.required:
            return _outcome(
                row,
                OutcomeStatus.FAIL,
                "required row cannot SKIP_OPTIONAL",
                details={"network_policy": _network_policy_details()},
            )
        if not row.prerequisite or not result.prerequisite:
            return _outcome(
                row,
                OutcomeStatus.FAIL,
                "optional skip lacks an explicit prerequisite",
                details={"network_policy": _network_policy_details()},
            )
        if result.prerequisite != row.prerequisite:
            return _outcome(
                row,
                OutcomeStatus.FAIL,
                "optional skip reason does not match the matrix",
                details={"network_policy": _network_policy_details()},
            )
    details = dict(result.details or {})
    details.setdefault("network_policy", _network_policy_details())
    return FunctionalOutcome(
        row_id=result.row_id,
        status=result.status,
        message=result.message,
        details=details,
        prerequisite=result.prerequisite,
    )


def _network_policy_details() -> dict[str, str]:
    return {
        "in_process": "socket, urllib, and http.client requests denied",
        "child_process": (
            "child processes are not monkeypatched; adapters use offline flags, "
            "isolated environments, or fake local binaries"
        ),
    }


def outcome_satisfies_row(row: MatrixRow, outcome: FunctionalOutcome) -> bool:
    """Return whether an observed outcome satisfies required/optional policy."""
    if row.required:
        return outcome.status is row.expected_status is OutcomeStatus.PASS
    if outcome.status is OutcomeStatus.SKIP_OPTIONAL:
        return bool(row.prerequisite and outcome.prerequisite == row.prerequisite)
    return outcome.status is row.expected_status


def serialize_outcomes(outcomes: tuple[FunctionalOutcome, ...] | list[FunctionalOutcome]) -> str:
    """Serialize row outcomes deterministically for optional telemetry callers."""
    return json.dumps(
        [outcome.to_dict() for outcome in outcomes],
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    )


def run_matrix(
    document: MatrixDocument | None = None,
    repo_root: Path | None = None,
    *,
    tier: str | None = None,
    output_path: Path | None = None,
) -> tuple[FunctionalOutcome, ...]:
    """Execute matrix rows and write a deterministic functional result artifact."""

    root = (repo_root or Path.cwd()).resolve()
    matrix = document or load_matrix(repo_root=root)
    rows = matrix.rows if tier in (None, "all") else select_rows(matrix, tier)
    outcomes = tuple(run_row(row, root) for row in rows)
    policy_outcomes: list[FunctionalOutcome] = []
    for row, outcome in zip(rows, outcomes, strict=True):
        if outcome_satisfies_row(row, outcome):
            policy_outcomes.append(outcome)
            continue
        details = dict(outcome.details or {})
        details["observed_status"] = outcome.status.value
        policy_outcomes.append(
            FunctionalOutcome(
                row_id=row.id,
                status=OutcomeStatus.FAIL,
                message="observed outcome does not satisfy the matrix policy",
                details=details,
                prerequisite=outcome.prerequisite,
            )
        )
    final_outcomes = tuple(policy_outcomes)
    counts = {
        status.value: sum(outcome.status is status for outcome in final_outcomes)
        for status in OutcomeStatus
    }
    artifact = {
        "schema_version": SCHEMA_VERSION,
        "mode": matrix.mode,
        "tier": tier or "all",
        "row_count": len(final_outcomes),
        "required_row_count": sum(row.required for row in rows),
        "status_counts": counts,
        "status": "PASS"
        if all(
            outcome_satisfies_row(row, outcome)
            for row, outcome in zip(rows, final_outcomes, strict=True)
        )
        else "FAIL",
        "outcomes": [outcome.to_dict() for outcome in final_outcomes],
    }
    target = output_path or root / ".local" / "telemetry" / "functional-test-results.json"
    if not target.is_absolute():
        target = root / target
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(artifact, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return final_outcomes
