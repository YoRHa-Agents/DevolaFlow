"""Si-Chip subprocess runner — typed Python wrappers around the 3 CLI scripts.

Wraps the Si-Chip v0.4.0 script trio (``profile_static.py``,
``count_tokens.py``, ``aggregate_eval.py``) into a Python API the
DevolaFlow lifecycle hook (PV-04) and dogfood pass (PV-05) can call
directly.

Public functions:

* :func:`profile` — runs ``profile_static.py --ability <name> --out <path>``;
  parses the resulting YAML into :class:`BasicAbilityProfile`.
* :func:`count_tokens` — runs ``count_tokens.py --file <skill_md> --both``;
  returns ``(metadata_tokens, body_tokens)``.
* :func:`evaluate` — runs ``aggregate_eval.py --runs-dir ... --baseline-dir
  ... --skill-md ... --out ...``; parses YAML into :class:`MetricsReport`.
* :func:`aggregate_delta` — pure Python; computes
  :class:`IterationDeltaReport` from two :class:`MetricsReport` instances.
* :func:`apply_or_defer` — pure Python; threshold gate (default +0.10
  per Si-Chip spec §23) returning :class:`ApplyVerdict`.

S-5 contract: every subprocess wrapper uses ``subprocess.run(check=False)``
with explicit stdout/stderr capture; non-zero exits raise
:class:`SiChipError` with the captured stderr verbatim. Missing Si-Chip
install raises :class:`SiChipUnavailable` (distinct exception so callers
can downgrade to "skip" semantics without swallowing other failures).

S-7 compliance: the install dir is resolved via
:func:`devolaflow.si_chip_bridge.install_resolver.find_si_chip_install`;
no path is hardcoded. Operators control discovery via the documented
``SI_CHIP_HOME`` / ``DEVOLAFLOW_SI_CHIP_FALLBACK_DIR`` env vars.

Source: v9.5.0 PV-02 — closes D-S-2 from
`.local/research/v9.5.0_gap_analysis.md` §3.1.
"""

from __future__ import annotations

import logging
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from devolaflow.si_chip_bridge.install_resolver import (
    SiChipInstall,
    find_si_chip_install,
)
from devolaflow.si_chip_bridge.models import (
    ApplyVerdict,
    BasicAbilityProfile,
    IterationDeltaReport,
    MetricsReport,
    SiChipResult,
)

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS: int = 90
DEFAULT_THRESHOLD: float = 0.10

# IEEE-754 absolute tolerance for the apply/defer threshold comparison.
# Without this, a delta of e.g. ``0.6 - 0.5 = 0.09999999999999998`` would
# incorrectly DEFER against a 0.10 threshold despite the operator's clear
# intent that the change clears the gate. The epsilon is 8 orders of
# magnitude smaller than the smallest real-world Si-Chip composite delta
# (the spec §23 threshold of +0.10 dwarfs 1e-9), so it cannot mask any
# actual sub-threshold improvement.
APPLY_DEFER_EPSILON: float = 1e-9

PROFILE_SCRIPT: str = "profile_static.py"
EVALUATE_SCRIPT: str = "aggregate_eval.py"
COUNT_TOKENS_SCRIPT: str = "count_tokens.py"

# The count_tokens.py script emits 3 KEY=VALUE lines on stdout
# (metadata_tokens=NN / body_tokens=NN / verdict=pass|fail).
_COUNT_TOKENS_LINE_RX = re.compile(r"^([a-z_]+)=(.+)$", re.MULTILINE)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class SiChipError(Exception):
    """Base error for any failure in the bridge runtime.

    Carries the optional ``details`` dict (mirrors the
    :mod:`devolaflow.plugins.exceptions` convention) for structured
    downstream logging.
    """

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        """Initialize with a loud message and optional structured ``details``."""
        super().__init__(message)
        self.details: dict = details or {}


class SiChipUnavailable(SiChipError):  # noqa: N818 — public API name; subclass of SiChipError
    """Raised when the resolver cannot locate any Si-Chip install.

    Distinct from :class:`SiChipError` so callers (the PV-04 lifecycle
    hook, the PV-05 dogfood pass) can downgrade to "skip the dogfood
    cycle" semantics without swallowing genuine subprocess failures.
    The CI environment / fresh clones legitimately do not have Si-Chip
    installed; the hook MUST handle this gracefully per the v9.5.0
    DEEP integration spec.
    """


# ---------------------------------------------------------------------------
# Subprocess helpers
# ---------------------------------------------------------------------------


def _require_install() -> SiChipInstall:
    """Locate the Si-Chip install or raise :class:`SiChipUnavailable`.

    Wraps :func:`find_si_chip_install` and converts the ``None``
    return into a loud, actionable exception. Tests can monkeypatch
    ``find_si_chip_install`` directly to inject a fake install path.
    """
    install = find_si_chip_install()
    if install is None:
        raise SiChipUnavailable(
            "Si-Chip not installed; tried $SI_CHIP_HOME, "
            "~/.cursor/skills/si-chip/[si-chip/], "
            "~/.claude/skills/si-chip/[si-chip/], "
            "$DEVOLAFLOW_SI_CHIP_FALLBACK_DIR. Install with: "
            "curl -fsSL https://yorha-agents.github.io/Si-Chip/install.sh "
            "| bash -s -- --target cursor --scope global --yes",
            details={
                "canonical_url": "https://github.com/YoRHa-Agents/Si-Chip",
            },
        )
    return install


def _require_script(install: SiChipInstall, script_name: str) -> Path:
    """Locate ``script_name`` in the install or raise :class:`SiChipError`.

    The Si-Chip v0.4.0 installer occasionally produces partial installs
    (SKILL.md present + scripts/ missing) when the underlying tar
    extraction fails halfway. This helper makes the failure mode
    explicit per S-5.
    """
    script = install.script_path(script_name)
    if script is None:
        raise SiChipError(
            f"Si-Chip install at {install.root} is missing "
            f"scripts/{script_name}. The install may be incomplete; "
            f"re-run the installer with --force.",
            details={
                "install_root": str(install.root),
                "missing_script": script_name,
                "install_source": install.source,
            },
        )
    return script


def _run(
    cmd: list[str],
    *,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run ``cmd`` via subprocess and return the completed process.

    S-5 compliant: ``check=False`` so callers can inspect stderr +
    return-code. Captures both streams as text. Logs INFO on entry,
    WARNING on non-zero exit.

    Raises
    ------
    SiChipError
        On :class:`subprocess.TimeoutExpired` (loud per S-5).
    """
    logger.info("si_chip_bridge.runner: invoking %s", " ".join(cmd))
    try:
        completed = subprocess.run(  # noqa: S603 — cmd is constructed in-module from validated paths
            cmd,
            cwd=str(cwd) if cwd is not None else None,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise SiChipError(
            f"Si-Chip subprocess timed out after {timeout}s: {' '.join(cmd)}",
            details={"cmd": cmd, "timeout": timeout, "stderr": exc.stderr or ""},
        ) from exc
    if completed.returncode != 0:
        logger.warning(
            "si_chip_bridge.runner: subprocess exited %d for cmd=%r stderr=%r",
            completed.returncode,
            cmd,
            completed.stderr.strip()[:300] if completed.stderr else "",
        )
    return completed


def _parse_yaml(path: Path) -> dict[str, Any]:
    """Parse a YAML file into a dict; loud on errors per S-5."""
    if not path.is_file():
        raise SiChipError(
            f"Si-Chip subprocess did not produce expected output file: {path}",
            details={"path": str(path)},
        )
    try:
        import yaml
    except ImportError as exc:
        raise SiChipError(
            "PyYAML required to parse Si-Chip output; install with: pip install pyyaml",
            details={"missing_module": "yaml"},
        ) from exc
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise SiChipError(
            f"Failed to parse Si-Chip YAML output at {path}: {exc}",
            details={"path": str(path), "yaml_error": str(exc)},
        ) from exc
    if not isinstance(data, dict):
        raise SiChipError(
            f"Si-Chip YAML at {path} did not parse into a mapping (got {type(data).__name__})",
            details={"path": str(path)},
        )
    return data


# ---------------------------------------------------------------------------
# Public API: profile + count_tokens + evaluate
# ---------------------------------------------------------------------------


def profile(
    ability_name: str,
    out_path: Path,
    *,
    install: SiChipInstall | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> BasicAbilityProfile:
    """Run Si-Chip's profile_static.py for ``ability_name``; parse output.

    Equivalent to the shell command::

        python <install>/scripts/profile_static.py \\
            --ability <ability_name> --out <out_path>

    Parameters
    ----------
    ability_name : str
        Pass-through ``--ability`` argument; for DevolaFlow's dogfood
        pass this is ``"devola-flow"``.
    out_path : Path
        Where Si-Chip writes the BasicAbilityProfile YAML. Caller
        owns the path; bridge does NOT auto-tempify.
    install : SiChipInstall, optional
        Pre-resolved install dir; tests inject a fake here. When
        omitted, the resolver runs.
    timeout : int
        Subprocess timeout in seconds; default 90.

    Raises
    ------
    SiChipUnavailable
        Si-Chip is not installed (resolver returned None).
    SiChipError
        Subprocess failed / output YAML missing / YAML malformed.
    """
    install = install or _require_install()
    script = _require_script(install, PROFILE_SCRIPT)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        str(script),
        "--ability",
        ability_name,
        "--out",
        str(out_path),
    ]
    completed = _run(cmd, timeout=timeout, cwd=install.root)
    if completed.returncode != 0:
        raise SiChipError(
            f"profile_static.py exited {completed.returncode} for ability "
            f"{ability_name!r}; stderr: {completed.stderr.strip()[:400]}",
            details={
                "cmd": cmd,
                "returncode": completed.returncode,
                "stderr": completed.stderr,
                "stdout": completed.stdout,
            },
        )
    data = _parse_yaml(out_path)
    return BasicAbilityProfile.from_yaml_dict(data)


def count_tokens(
    skill_md: Path,
    *,
    install: SiChipInstall | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> tuple[int, int]:
    """Run Si-Chip's count_tokens.py against ``skill_md``; return ``(meta, body)``.

    Equivalent to the shell command::

        python <install>/scripts/count_tokens.py --file <skill_md> --both

    Returns ``(metadata_tokens, body_tokens)`` parsed from the
    KEY=VALUE stdout. Useful as a cheap pre-check before the heavier
    :func:`evaluate` (which involves baseline + with-ability runs).
    """
    install = install or _require_install()
    script = _require_script(install, COUNT_TOKENS_SCRIPT)
    cmd = [
        sys.executable,
        str(script),
        "--file",
        str(skill_md),
        "--both",
    ]
    completed = _run(cmd, timeout=timeout, cwd=install.root)
    if completed.returncode != 0:
        raise SiChipError(
            f"count_tokens.py exited {completed.returncode} for "
            f"{skill_md}; stderr: {completed.stderr.strip()[:400]}",
            details={
                "cmd": cmd,
                "returncode": completed.returncode,
                "stderr": completed.stderr,
            },
        )
    parsed: dict[str, str] = dict(_COUNT_TOKENS_LINE_RX.findall(completed.stdout))
    try:
        meta = int(parsed.get("metadata_tokens", "0"))
        body = int(parsed.get("body_tokens", "0"))
    except ValueError as exc:
        raise SiChipError(
            f"count_tokens.py produced unparseable output for {skill_md}: {completed.stdout!r}",
            details={"stdout": completed.stdout, "parsed": parsed},
        ) from exc
    return meta, body


def evaluate(
    skill_md: Path,
    runs_dir: Path,
    baseline_dir: Path,
    out_path: Path,
    *,
    install: SiChipInstall | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> MetricsReport:
    """Run Si-Chip's aggregate_eval.py; parse the resulting metrics_report.yaml.

    Equivalent to the shell command::

        python <install>/scripts/aggregate_eval.py \\
            --runs-dir <runs_dir> --baseline-dir <baseline_dir> \\
            --skill-md <skill_md> --out <out_path>

    Parameters
    ----------
    skill_md : Path
        SKILL.md to score (consumed by the C1_metadata_tokens probe).
    runs_dir : Path
        Directory of with-ability run outputs (operator-prepared).
    baseline_dir : Path
        Directory of no-ability baseline run outputs (operator-prepared).
    out_path : Path
        Where Si-Chip writes the metrics_report YAML.
    install, timeout : same as :func:`profile`.

    Raises same as :func:`profile`.
    """
    install = install or _require_install()
    script = _require_script(install, EVALUATE_SCRIPT)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        str(script),
        "--runs-dir",
        str(runs_dir),
        "--baseline-dir",
        str(baseline_dir),
        "--skill-md",
        str(skill_md),
        "--out",
        str(out_path),
    ]
    completed = _run(cmd, timeout=timeout, cwd=install.root)
    if completed.returncode != 0:
        raise SiChipError(
            f"aggregate_eval.py exited {completed.returncode}; "
            f"stderr: {completed.stderr.strip()[:400]}",
            details={
                "cmd": cmd,
                "returncode": completed.returncode,
                "stderr": completed.stderr,
            },
        )
    data = _parse_yaml(out_path)
    return MetricsReport.from_yaml_dict(data)


# ---------------------------------------------------------------------------
# Public API: aggregate_delta + apply_or_defer (pure Python)
# ---------------------------------------------------------------------------


def aggregate_delta(
    before: MetricsReport,
    after: MetricsReport,
    *,
    threshold: float = DEFAULT_THRESHOLD,
) -> IterationDeltaReport:
    """Compute the iteration_delta = after.composite - before.composite.

    Pure Python; no IO. Si-Chip spec §23 defines iteration_delta as
    the per-round composite change; the apply/defer decision is
    based on whether this delta clears the threshold.

    Parameters
    ----------
    before : MetricsReport
        Baseline (no proposed change applied).
    after : MetricsReport
        Post-change.
    threshold : float
        Cutoff for the apply/defer decision; default 0.10 per Si-Chip
        spec §23.
    """
    delta = after.composite - before.composite
    return IterationDeltaReport(
        before=before,
        after=after,
        iteration_delta=delta,
        threshold=threshold,
    )


def apply_or_defer(
    delta: IterationDeltaReport,
    *,
    threshold: float | None = None,
) -> ApplyVerdict:
    """Return ``APPLY`` when ``iteration_delta >= threshold``; else ``DEFER``.

    Pure Python; no IO. The threshold defaults to
    ``delta.threshold`` (i.e. the value baked into the
    :class:`IterationDeltaReport` by :func:`aggregate_delta`); callers
    may override per-call (used by tests + operators tuning the gate
    per workflow profile).

    Per the v9.5.0 user requirement: changes that score below threshold
    are NOT applied automatically — they are deferred to a feedback
    document the operator reviews. This is the "ensure those things
    are genuinely effective ... BEFORE applying them" contract from
    the verbatim user requirement (see
    `.local/research/v9.5.0_gap_analysis.md` §1).
    """
    cutoff = threshold if threshold is not None else delta.threshold
    if delta.iteration_delta >= cutoff - APPLY_DEFER_EPSILON:
        return ApplyVerdict.APPLY
    return ApplyVerdict.DEFER


# ---------------------------------------------------------------------------
# Public API: top-level dogfood orchestration
# ---------------------------------------------------------------------------


def run_dogfood_cycle(
    ability_name: str,
    skill_md: Path,
    *,
    runs_dir: Path | None = None,
    baseline_dir: Path | None = None,
    work_dir: Path | None = None,
    threshold: float = DEFAULT_THRESHOLD,
    install: SiChipInstall | None = None,
) -> SiChipResult:
    """Top-level orchestrator: profile → evaluate (twice) → delta → verdict.

    This is the canonical entry point for the v9.5.0 PV-04
    :mod:`devolaflow.lifecycle.post_skill_edit` lifecycle hook AND the
    PV-05 self-application dogfood pass.

    Two-stage cycle:

    1. Run Si-Chip's profile + cheap count_tokens probe to confirm the
       skill file fits its budgets.
    2. When ``runs_dir`` + ``baseline_dir`` are provided, run the full
       :func:`evaluate` against both AND compute the iteration_delta.
       Otherwise the cycle returns a DEFER verdict with notes
       explaining no eval data was available.

    Parameters
    ----------
    ability_name : str
        Pass-through to :func:`profile`; e.g. ``"devola-flow"``.
    skill_md : Path
        SKILL.md being evaluated.
    runs_dir, baseline_dir : Path, optional
        Eval run + baseline directories. When both omitted the cycle
        runs the cheap profile-only path (PV-04 lifecycle hook common
        case — most commits don't have eval data on hand).
    work_dir : Path, optional
        Where intermediate YAML files land. Defaults to a temp dir.
    threshold : float
        Apply/defer threshold; default 0.10.
    install : SiChipInstall, optional
        Pre-resolved install (tests pass a fake here).

    Returns
    -------
    SiChipResult
        Carries verdict + delta (when computed) + notes for the
        feedback doc.

    Raises
    ------
    SiChipUnavailable
        Si-Chip not installed.
    SiChipError
        Subprocess failure on a stage that should have succeeded.
    """
    install = install or _require_install()
    notes: list[str] = []
    work_dir = work_dir or Path.cwd() / ".local" / "dogfood" / "v9.5.0"
    work_dir.mkdir(parents=True, exist_ok=True)

    profile_path = work_dir / f"{ability_name}_profile.yaml"
    profile_data = profile(ability_name, profile_path, install=install)
    notes.append(
        f"profile: ability={profile_data.ability_id!r} "
        f"meta_tokens={profile_data.metadata_tokens} "
        f"body_tokens={profile_data.body_tokens}"
    )

    if runs_dir is None or baseline_dir is None:
        notes.append(
            "evaluate: skipped — runs_dir/baseline_dir not supplied; "
            "DEFER verdict emitted (no iteration_delta computed)"
        )
        return SiChipResult(
            verdict=ApplyVerdict.DEFER,
            delta=None,
            install_source=install.source,
            skill_md=skill_md,
            notes=notes,
        )

    baseline_path = work_dir / f"{ability_name}_baseline_metrics.yaml"
    after_path = work_dir / f"{ability_name}_after_metrics.yaml"
    before = evaluate(skill_md, baseline_dir, baseline_dir, baseline_path, install=install)
    after = evaluate(skill_md, runs_dir, baseline_dir, after_path, install=install)
    delta = aggregate_delta(before, after, threshold=threshold)
    verdict = apply_or_defer(delta, threshold=threshold)
    notes.append(
        f"iteration_delta={delta.iteration_delta:+.4f} "
        f"vs threshold {threshold:+.2f} → {verdict.value}"
    )
    return SiChipResult(
        verdict=verdict,
        delta=delta,
        install_source=install.source,
        skill_md=skill_md,
        notes=notes,
    )


__all__ = [
    "COUNT_TOKENS_SCRIPT",
    "DEFAULT_THRESHOLD",
    "DEFAULT_TIMEOUT_SECONDS",
    "EVALUATE_SCRIPT",
    "PROFILE_SCRIPT",
    "SiChipError",
    "SiChipUnavailable",
    "aggregate_delta",
    "apply_or_defer",
    "count_tokens",
    "evaluate",
    "profile",
    "run_dogfood_cycle",
]
