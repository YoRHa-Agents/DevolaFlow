"""NineS advisor — research guidance and legacy gate verdict enrichment.

Primary API:  :func:`get_research_advice` — interprets NineS analysis
output and recommends next research / skill-iteration steps.

Legacy API:  :func:`run_nines_advisor` — borderline gate verdict
enrichment (deprecated; prefer standard gate + research separation).
"""

from __future__ import annotations

import json
import logging
import subprocess
import warnings
from dataclasses import dataclass, field

from devolaflow.gate.models import GateVerdict

logger = logging.getLogger(__name__)

_DEFAULT_COMMANDS: dict[str, str] = {
    "self-eval": "nines -f json self-eval",
    "review": "nines -f json analyze --target-path {path}",
    "iterate": "nines -f json iterate --max-rounds 1",
}


@dataclass
class NinesAdvisorConfig:
    """Configuration for the NineS advisor integration."""

    enabled: bool = False
    commands: dict[str, str] = field(default_factory=lambda: dict(_DEFAULT_COMMANDS))
    triggers: list[str] = field(default_factory=lambda: ["self-eval"])
    max_retries: int = 2


def should_invoke_advisor(verdict: GateVerdict, config: NinesAdvisorConfig) -> bool:
    """Return True when the advisor should be consulted."""
    return verdict.advisor_recommended and config.enabled


def _run_nines_command(cmd: str, retries: int) -> dict[str, object] | None:
    """Execute a NineS CLI command and return parsed JSON, or None on failure."""
    for attempt in range(1, retries + 1):
        try:
            result = subprocess.run(
                cmd.split(),
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0:
                return json.loads(result.stdout)  # type: ignore[no-any-return]
            logger.warning(
                "NineS command failed (attempt %d/%d, rc=%d): %s",
                attempt,
                retries,
                result.returncode,
                result.stderr.strip(),
            )
        except subprocess.TimeoutExpired:
            logger.warning("NineS command timed out (attempt %d/%d): %s", attempt, retries, cmd)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("NineS command error (attempt %d/%d): %s", attempt, retries, exc)
    return None


_SCORE_KEYS = ("score", "overall_score", "quality_score")
_REASONING_KEYS = ("reasoning", "summary", "details")
_APPROVE_STATUSES = frozenset({"pass", "passed", "approve", "approved", "ok"})
_SCORE_THRESHOLD = 70


def _extract_score(data: dict[str, object]) -> int | float | None:
    for key in _SCORE_KEYS:
        val = data.get(key)
        if isinstance(val, (int, float)):
            return val
    return None


def _extract_reasoning(data: dict[str, object]) -> str:
    for key in _REASONING_KEYS:
        val = data.get(key)
        if val:
            return str(val)
    return ""


def _interpret_result(data: dict[str, object]) -> tuple[str, str]:
    """Derive an APPROVE/REJECT verdict and reasoning from NineS output."""
    score = _extract_score(data)
    reasoning = _extract_reasoning(data)

    if score is not None:
        verdict = "APPROVE" if score >= _SCORE_THRESHOLD else "REJECT"
        meets = "meets" if score >= _SCORE_THRESHOLD else "below"
        fallback = f"NineS score {score} {meets} threshold"
        return verdict, reasoning or fallback

    status = str(data.get("status", "")).lower()
    if status in _APPROVE_STATUSES:
        return "APPROVE", reasoning or "NineS status: approved"
    return "REJECT", reasoning or "NineS did not return a passing status"


def run_nines_advisor(
    verdict: GateVerdict,
    config: NinesAdvisorConfig,
    artifact_path: str,
) -> GateVerdict:
    """Enrich a borderline gate verdict with NineS automated analysis.

    .. deprecated::
        Gate verdict enrichment via NineS is deprecated.  Use
        :func:`get_research_advice` for NineS-powered guidance, and the
        standard gate mechanism for quality gates.

    If the advisor should not run (disabled or not recommended),
    returns the verdict unchanged.
    """
    warnings.warn(
        "run_nines_advisor is deprecated for gate enrichment. "
        "Use get_research_advice() for NineS research guidance and "
        "evaluate_gate() for quality gates.",
        DeprecationWarning,
        stacklevel=2,
    )
    if not should_invoke_advisor(verdict, config):
        return verdict

    for trigger in config.triggers:
        cmd_template = config.commands.get(trigger)
        if not cmd_template:
            logger.warning("No command configured for trigger %r, skipping", trigger)
            continue

        cmd = cmd_template.format(path=artifact_path)
        data = _run_nines_command(cmd, config.max_retries)
        if data is None:
            continue

        advisor_verdict, reasoning = _interpret_result(data)
        verdict.advisor_verdict = advisor_verdict
        verdict.advisor_context = (
            f"NineS ({trigger}): {reasoning}"
            if reasoning
            else f"NineS ({trigger}): {advisor_verdict}"
        )
        return verdict

    logger.warning("All NineS triggers exhausted without a result; verdict unchanged")
    return verdict


def get_research_advice(
    config: NinesAdvisorConfig,
    target_path: str,
) -> dict[str, object]:
    """Use NineS to produce research guidance for a target artifact.

    Unlike :func:`run_nines_advisor`, this function does **not** interact
    with gate verdicts.  It runs configured NineS commands against
    *target_path* and returns a structured recommendation dict::

        {
            "status": "ok" | "no_result",
            "recommendations": [...],
            "raw_outputs": {<trigger>: <nines_json>, ...},
        }

    Parameters
    ----------
    config:
        Advisor configuration (``commands`` and ``triggers`` are used).
    target_path:
        Filesystem path forwarded to NineS CLI commands.
    """
    recommendations: list[str] = []
    raw_outputs: dict[str, object] = {}

    for trigger in config.triggers:
        cmd_template = config.commands.get(trigger)
        if not cmd_template:
            logger.warning("No command configured for trigger %r, skipping", trigger)
            continue

        cmd = cmd_template.format(path=target_path)
        data = _run_nines_command(cmd, config.max_retries)
        if data is None:
            continue

        raw_outputs[trigger] = data

        summary = data.get("reasoning") or data.get("summary") or data.get("details")
        if summary:
            recommendations.append(f"{trigger}: {summary}")

        next_steps = data.get("next_steps") or data.get("suggestions")
        if isinstance(next_steps, list):
            recommendations.extend(str(s) for s in next_steps)

    if not raw_outputs:
        return {"status": "no_result", "recommendations": [], "raw_outputs": {}}

    return {
        "status": "ok",
        "recommendations": recommendations,
        "raw_outputs": raw_outputs,
    }
