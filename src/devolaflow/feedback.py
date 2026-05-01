"""Self-Improving Feedback Loop Module for DevolaFlow.

Collects execution metrics from gate verdicts and status reports, analyzes
patterns (recurring violations, convergence stagnation, profile mismatches),
and generates structured improvement proposals with safeguards against
runaway self-modification.

Design ref: S02-T08-engine-infra.md §5 (Integration Point 5)
"""

from __future__ import annotations

import copy
import logging
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from devolaflow.gate.models import Finding, GateVerdict, Severity
from devolaflow.gate.reinforcement import (
    ReinforcementBlock,
    findings_to_reinforcement,
    merge_reinforcement_into_dispatch,
)
from devolaflow.learnings import _now_iso, _read_lines

logger = logging.getLogger(__name__)

# v8.4.4 PV-04 — Soul Rule S-10 enforcement: every dispatch payload returned
# by ``generate_round_dispatch`` is run through the lifecycle hook chain
# (`pre_dispatch` → `post_dispatch`) so prompt-side governance contracts can
# observe / validate / annotate the payload without coupling
# ``feedback.py`` to specific handlers. The hook is invoked in PERMISSIVE
# mode (``strict=False``) per the v8.4.0 retro §4.1 #4 R5 strict pattern —
# byte-output is identical when no extras are registered, and a buggy
# custom handler MUST NOT bring down the round-N+1 dispatch emission.
#
# Closes the dead-wire identified in v6.0.3 retro precedent + C-03 from
# `.local/research/v9.0.0_gap_analysis.md` §3.1.
#
# v9.1.3 PV-03 — extends the chain to include `pre_handoff` AFTER the
# governance tail. At this point the dispatch payload is fully-formed +
# lint-validated, making it the correct moment to consider materialising
# a handoff envelope under `.local/.agent/handoff/`. The default
# handler (`auto_write_handoff`) is a no-op when
# `DEVOLAFLOW_AGENT_WORKSPACE` is unset (R5 strict byte-identical), so
# adding the third event preserves the byte-output guarantee for
# operators who haven't opted into the agent-workspace activation
# surface. Closes G-005 deferred from v9.1.0 by giving
# `HandoffStore.write_envelope` its FIRST production caller.
_HOOK_PRE_DISPATCH = "pre_dispatch"
_HOOK_POST_DISPATCH = "post_dispatch"
_HOOK_PRE_HANDOFF = "pre_handoff"

LOCKED_FILES = frozenset(
    {
        "__init__.py",
        "pyproject.toml",
        "feedback.py",
    }
)

MAX_PROPOSALS_PER_WORKFLOW = 3
CONFIDENCE_FLOOR = 0.7


@dataclass
class Proposal:
    """A structured improvement proposal."""

    id: str
    type: str
    description: str
    confidence: float
    target_file: str
    suggested_change: str


def _is_locked(target_file: str) -> bool:
    """Return True if *target_file* is in the scope-lock set."""
    basename = Path(target_file).name
    if basename in LOCKED_FILES:
        return True
    return basename.startswith("test_")


def _inside_devolaflow(target_file: str) -> bool:
    """Return True if *target_file* lives within the DevolaFlow tree.

    Accepts relative paths (rooted at repo), or paths containing
    'devolaflow', 'workflow-system', 'schemas', or '.cursor/rules'.
    """
    allowed_prefixes = (
        "src/devolaflow/",
        "workflow-system/",
        "schemas/",
        ".cursor/rules/",
    )
    return any(target_file.startswith(p) or f"/{p}" in target_file for p in allowed_prefixes)


class FeedbackCollector:
    """Extracts structured metrics from gate verdicts and status reports."""

    def collect_from_gate(self, verdict: GateVerdict) -> dict:
        """Extract composite_score, decision, and findings_count from a GateVerdict."""
        findings_count = 0
        if "findings" in verdict.details:
            raw = verdict.details["findings"]
            findings_count = len(raw) if isinstance(raw, list) else int(raw)

        return {
            "composite_score": verdict.composite_score,
            "decision": verdict.decision,
            "findings_count": findings_count,
        }

    def collect_from_report(self, report_data: dict) -> dict:
        """Extract metrics, issues, and elapsed time from a status report dict."""
        return {
            "metrics": report_data.get("metrics", {}),
            "issues": report_data.get("issues", []),
            "elapsed_seconds": report_data.get("elapsed_seconds", 0),
        }

    def collect_workflow_metrics(self, stages: list[dict]) -> dict:
        """Aggregate workflow-level metrics across all stages.

        Each stage dict is expected to have keys: rounds, composite_score, name.
        """
        if not stages:
            return {
                "total_rounds": 0,
                "avg_composite": 0.0,
                "bottleneck_stage": "",
            }

        total_rounds = sum(s.get("rounds", 0) for s in stages)
        scores = [s.get("composite_score", 0.0) for s in stages]
        avg_composite = sum(scores) / len(scores) if scores else 0.0

        bottleneck = max(stages, key=lambda s: s.get("rounds", 0))

        return {
            "total_rounds": total_rounds,
            "avg_composite": round(avg_composite, 2),
            "bottleneck_stage": bottleneck.get("name", ""),
        }


class FeedbackAnalyzer:
    """Detects patterns in execution history that suggest improvements."""

    def detect_recurring_violations(
        self,
        learnings_path: Path,
        min_occurrences: int = 3,
    ) -> list[dict]:
        """Find rule_ids that appear >= *min_occurrences* times in learnings."""
        entries = _read_lines(learnings_path)
        rule_counts: Counter[str] = Counter()
        rule_examples: dict[str, list[str]] = {}

        for entry in entries:
            rid = entry.get("rule_id", "")
            if not rid:
                continue
            rule_counts[rid] += 1
            rule_examples.setdefault(rid, []).append(entry.get("insight", ""))

        return [
            {
                "rule_id": rid,
                "count": count,
                "examples": rule_examples.get(rid, [])[:3],
            }
            for rid, count in rule_counts.items()
            if count >= min_occurrences
        ]

    def detect_convergence_stagnation(
        self,
        rounds: list[dict],
        threshold: float = 2.0,
    ) -> bool:
        """Return True if score improvement < *threshold* for 2+ consecutive rounds.

        Each round dict must have a ``composite_score`` key.
        """
        if len(rounds) < 3:
            return False

        consecutive_stagnant = 0
        for i in range(1, len(rounds)):
            prev = rounds[i - 1].get("composite_score", 0.0)
            curr = rounds[i].get("composite_score", 0.0)
            improvement = curr - prev
            if improvement < threshold:
                consecutive_stagnant += 1
                if consecutive_stagnant >= 2:
                    return True
            else:
                consecutive_stagnant = 0

        return False

    def detect_profile_mismatch(
        self,
        task_type: str,
        actual_metrics: dict,
        expected_thresholds: dict,
    ) -> list[str]:
        """Compare actual metrics against expected thresholds.

        Returns a list of human-readable mismatch descriptions.
        """
        mismatches: list[str] = []
        for metric_name, expected_value in expected_thresholds.items():
            actual_value = actual_metrics.get(metric_name)
            if actual_value is None:
                mismatches.append(
                    f"{task_type}: metric '{metric_name}' missing from actual metrics"
                )
                continue
            if (
                isinstance(expected_value, (int, float))
                and isinstance(actual_value, (int, float))
                and actual_value < expected_value
            ):
                mismatches.append(
                    f"{task_type}: '{metric_name}' is {actual_value}, expected >= {expected_value}"
                )
        return mismatches


@dataclass
class _ProposalState:
    """Internal bookkeeping for proposal generation safeguards."""

    recent_rule_ids: dict[str, str] = field(default_factory=dict)


def _make_proposal(
    index: int,
    ptype: str,
    description: str,
    confidence: float,
    target_file: str,
    suggested_change: str,
) -> dict:
    return {
        "id": f"prop-{_now_iso()[:10]}-{index + 1:03d}",
        "type": ptype,
        "description": description,
        "confidence": confidence,
        "target_file": target_file,
        "suggested_change": suggested_change,
    }


def _filter_valid_proposals(proposals: list[dict]) -> list[dict]:
    valid: list[dict] = []
    for p in proposals:
        tf = p.get("target_file", "")
        if _is_locked(tf):
            logger.info("Rejecting proposal for locked file: %s", tf)
            continue
        if not _inside_devolaflow(tf):
            logger.info("Rejecting proposal for out-of-scope file: %s", tf)
            continue
        valid.append(p)
    return valid[:MAX_PROPOSALS_PER_WORKFLOW]


class ProposalGenerator:
    """Creates structured improvement proposals from analysis results.

    Safeguards enforced:
    - Max ``MAX_PROPOSALS_PER_WORKFLOW`` (3) proposals per invocation
    - Confidence floor ``CONFIDENCE_FLOOR`` (0.7) on source evidence
    - Scope-lock: proposals targeting locked files are rejected
    - DevolaFlow scope: proposals for files outside the repo are rejected
    """

    def __init__(self) -> None:
        """Initialize the proposal generator with empty internal state."""
        self._state = _ProposalState()

    def generate_proposals(self, analysis: dict) -> list[dict]:
        """Generate improvement proposals from an analysis dict.

        *analysis* should contain optional keys:
        - ``recurring_violations``: list[dict] from FeedbackAnalyzer
        - ``stagnation_detected``: bool
        - ``profile_mismatches``: list[str]
        - ``confidence``: float — overall analysis confidence

        Returns a list of proposal dicts, each with keys:
        id, type, description, confidence, target_file, suggested_change.
        """
        confidence = float(analysis.get("confidence", 0.0))
        if confidence < CONFIDENCE_FLOOR:
            logger.info(
                "Analysis confidence %.2f below floor %.2f — no proposals",
                confidence,
                CONFIDENCE_FLOOR,
            )
            return []

        proposals: list[dict] = []
        self._add_violation_proposals(analysis, confidence, proposals)
        self._add_stagnation_proposal(analysis, confidence, proposals)
        self._add_mismatch_proposals(analysis, confidence, proposals)
        return _filter_valid_proposals(proposals)

    def _add_violation_proposals(
        self,
        analysis: dict,
        confidence: float,
        proposals: list[dict],
    ) -> None:
        for violation in analysis.get("recurring_violations", []):
            if len(proposals) >= MAX_PROPOSALS_PER_WORKFLOW:
                return
            rule_id = violation.get("rule_id", "")
            if not rule_id:
                continue
            target = f".cursor/rules/{rule_id.lower().replace('-', '_')}.mdc"
            if _is_locked(target):
                logger.info("Skipping locked target: %s", target)
                continue
            proposals.append(
                _make_proposal(
                    index=len(proposals),
                    ptype="rule_update",
                    description=(
                        f"Rule {rule_id} violated {violation.get('count', 0)} times — "
                        "consider clarification or threshold adjustment"
                    ),
                    confidence=confidence,
                    target_file=target,
                    suggested_change=f"Review rule {rule_id} for clarity",
                )
            )

    def _add_stagnation_proposal(
        self,
        analysis: dict,
        confidence: float,
        proposals: list[dict],
    ) -> None:
        if not analysis.get("stagnation_detected"):
            return
        if len(proposals) >= MAX_PROPOSALS_PER_WORKFLOW:
            return
        target = "workflow-system/agent/context_profiles.yaml"
        if _is_locked(target):
            return
        proposals.append(
            _make_proposal(
                index=len(proposals),
                ptype="profile_tune",
                description=(
                    "Convergence stagnation detected — "
                    "consider adjusting gate thresholds or max_rounds"
                ),
                confidence=confidence,
                target_file=target,
                suggested_change="Lower composite_threshold or increase max_rounds",
            )
        )

    def _add_mismatch_proposals(
        self,
        analysis: dict,
        confidence: float,
        proposals: list[dict],
    ) -> None:
        target = "workflow-system/agent/context_profiles.yaml"
        for mismatch in analysis.get("profile_mismatches", []):
            if len(proposals) >= MAX_PROPOSALS_PER_WORKFLOW:
                return
            if _is_locked(target):
                continue
            proposals.append(
                _make_proposal(
                    index=len(proposals),
                    ptype="profile_tune",
                    description=f"Profile mismatch: {mismatch}",
                    confidence=confidence,
                    target_file=target,
                    suggested_change="Adjust section_priorities or token budget",
                )
            )

    def generate_reinforcement(
        self,
        verdict: GateVerdict,
        round_num: int,
        target_score: float = 85.0,
        severity_floor: Severity = "major",
    ) -> ReinforcementBlock | None:
        """Generate a :class:`ReinforcementBlock` from a gate verdict.

        Bridges feedback analysis (Approach E) with the dispatch-level
        reinforcement mechanism (Approach B).  Returns ``None`` when the
        verdict has no actionable findings.
        """
        findings_raw = verdict.details.get("findings", [])
        if not findings_raw:
            return None

        findings: list[Finding] = []
        for i, raw in enumerate(findings_raw):
            if isinstance(raw, Finding):
                findings.append(raw)
            elif isinstance(raw, dict):
                findings.append(
                    Finding(
                        finding_id=raw.get("finding_id", f"F-{i:03d}"),
                        severity=raw.get("severity", "major"),
                        category=raw.get("category", "general"),
                        location=raw.get("location", ""),
                        description=raw.get("description", ""),
                        suggestion=raw.get("suggestion", ""),
                        rule_id=raw.get("rule_id", ""),
                    )
                )

        if not findings:
            return None

        prior_score = verdict.composite_score or 0.0
        return findings_to_reinforcement(
            findings=findings,
            round_num=round_num,
            prior_score=prior_score,
            target_score=target_score,
            severity_floor=severity_floor,
        )

    def generate_round_dispatch(
        self,
        base_dispatch: dict[str, Any],
        verdict: GateVerdict | None,
        round_num: int,
        target_score: float = 85.0,
        severity_floor: Severity = "major",
    ) -> dict[str, Any]:
        """Produce a dispatch for convergence round ``round_num``.

        V6-01 wiring: stitches :meth:`generate_reinforcement` into the
        dispatch lifecycle so L3 Task Agents receive the reinforcement
        block under ``context.applicable_rules.reinforcement`` on rounds
        ≥ 2.  Round 1 is a pure pass-through — the first attempt has no
        prior round to learn from.

        v8.4.4 PV-04 wiring: the FINAL dispatch payload of every return
        path is run through the lifecycle hook chain
        (``pre_dispatch`` → ``post_dispatch``) per Soul Rule S-10
        ("Prompt-Side Governance Contract Embedding"). Hooks run in
        permissive mode — see ``_emit_dispatch`` docstring for R5
        strict-byte-identical contract.

        The input ``base_dispatch`` is never mutated; a deep copy is
        returned in all cases.
        """
        dispatch = copy.deepcopy(base_dispatch)

        if round_num <= 1 or verdict is None:
            return self._emit_dispatch(dispatch)

        block = self.generate_reinforcement(
            verdict,
            round_num=round_num,
            target_score=target_score,
            severity_floor=severity_floor,
        )
        if block is None:
            return self._emit_dispatch(dispatch)

        return self._emit_dispatch(merge_reinforcement_into_dispatch(dispatch, block))

    def _emit_dispatch(self, dispatch: dict[str, Any]) -> dict[str, Any]:
        """Run the lifecycle hook chain on ``dispatch`` and return it unchanged.

        v8.4.4 PV-04 — Soul Rule S-10 enforcement point. Fires
        ``pre_dispatch`` → ``post_dispatch`` → ``pre_handoff`` against
        the dispatch payload via :func:`devolaflow.lifecycle.run_hooks`;
        all three calls run in permissive mode (``strict=False``) so a
        violation only emits a WARNING via the lifecycle logger and
        never raises out of the dispatch path.

        v9.1.3 PV-03 — added ``pre_handoff`` AFTER the governance tail
        (Soul Rule S-10) so the payload is fully-formed + lint-validated
        before the handoff-write decision runs. The default
        ``auto_write_handoff`` handler is a no-op when
        ``DEVOLAFLOW_AGENT_WORKSPACE`` is unset (R5 strict
        byte-identical), so adding the third event preserves the
        byte-output guarantee for operators who haven't opted into the
        agent-workspace activation surface. Closes G-005 from v9.1.0
        by giving ``HandoffStore.write_envelope`` its FIRST production
        caller.

        R5 strict-byte-identical invariant (v8.4.0 retro §4.1 #4): when
        no extra handlers are registered for either event, the returned
        ``dispatch`` is byte-identical to the pre-PV-04 behaviour. The
        permissive default handlers either return cleanly
        (``post_dispatch`` is a no-op; ``pre_handoff`` is a no-op when
        the env-flag is OFF) or emit a WARNING log without mutating
        the payload (``pre_dispatch`` / ``validate_dispatch``).

        S-5 (no silent failures): a buggy custom handler that raises
        from inside the dispatch path is caught here, logged at
        WARNING level via ``logger.warning``, and the dispatch is
        returned unchanged — the round-N+1 emission MUST NOT crash on a
        third-party hook bug. Each event is wrapped in its own
        try/except so a failure on one does NOT short-circuit the
        others (the hook chain is collectively a contract; per-event
        independence is intentional).
        """
        try:
            from devolaflow import lifecycle
        except ImportError as exc:  # pragma: no cover - defensive
            logger.warning(
                "feedback._emit_dispatch: lifecycle module unavailable (%s); "
                "skipping pre_dispatch / post_dispatch / pre_handoff hooks",
                exc,
            )
            return dispatch

        for event in (_HOOK_PRE_DISPATCH, _HOOK_POST_DISPATCH, _HOOK_PRE_HANDOFF):
            try:
                lifecycle.run_hooks(event, dispatch, strict=False)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "feedback._emit_dispatch: %s hook raised %s; dispatch returned unchanged",
                    event,
                    exc,
                )
        return dispatch
