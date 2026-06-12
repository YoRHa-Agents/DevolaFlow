"""Self-Improving Feedback Loop Module for DevolaFlow.

Collects execution metrics from gate verdicts and status reports, analyzes
patterns (recurring violations, convergence stagnation, profile mismatches),
and generates structured improvement proposals with safeguards against
runaway self-modification.

Design ref: S02-T08-engine-infra.md §5 (Integration Point 5)
"""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from devolaflow.feedback_emit import ProposalEmitter
from devolaflow.gate.models import Finding, GateVerdict, Severity
from devolaflow.gate.reinforcement import (
    ReinforcementBlock,
    findings_to_reinforcement,
)
from devolaflow.learnings import _now_iso, _read_lines

logger = logging.getLogger(__name__)

# v10.6.0 PV-02 — the S-10 4-event lifecycle hook chain firing
# (``pre_dispatch`` → ``post_dispatch`` → ``pre_handoff`` →
# ``pre_plugin_invocation``) was extracted from this module into
# :class:`devolaflow.feedback_emit.ProposalEmitter`. The 4 hook event
# constants (``_HOOK_PRE_DISPATCH``, etc.) and the lazy lifecycle
# import live there now. Behaviour is byte-identical to v10.5.x
# baseline — pinned by ``tests/test_dispatch_emission_runs_hooks.py``
# (10 release-blocker tests) AND by the new
# ``tests/test_feedback_emit.py`` (8 unit tests on ``ProposalEmitter``
# in isolation). See PDS ``v11.0.0_patches/D-Q-2.md`` for the full
# rationale.

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

    def __init__(self, *, pre_dispatch_strict: bool = True) -> None:
        """Initialize the proposal generator with empty internal state.

        v10.6.0 PV-02 (D-Q-2 god-function refactor) — composes a
        :class:`devolaflow.feedback_emit.ProposalEmitter` for round-N+1
        dispatch emission. The emitter owns the S-10 4-event lifecycle
        hook chain firing AND the deep-copy + reinforcement merge
        pipeline; this class delegates to it via the
        :meth:`generate_round_dispatch` façade.

        v15.0.0 strict graduation (G-038): ``pre_dispatch_strict``
        defaults to ``True`` — a ``pre_dispatch`` hook violation
        (missing/placeholder acceptance criteria, malformed AC-v2
        block, subagent ``quality_score`` / banner leakage) raises
        :class:`devolaflow.lifecycle.HookViolation` from
        :meth:`generate_round_dispatch` and BLOCKS the dispatch. Pass
        ``pre_dispatch_strict=False`` for the documented permissive
        escape (pre-v15.0.0 warn-only behaviour).
        """
        self._state = _ProposalState()
        self._emitter = ProposalEmitter(pre_dispatch_strict=pre_dispatch_strict)

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

        Thin façade — delegates to
        :meth:`devolaflow.feedback_emit.ProposalEmitter.emit`.

        V6-01 wiring: stitches :meth:`generate_reinforcement` into the
        dispatch lifecycle so L3 Task Agents receive the reinforcement
        block under ``context.applicable_rules.reinforcement`` on rounds
        ≥ 2. Round 1 is a pure pass-through — the first attempt has no
        prior round to learn from.

        v8.4.4 PV-04 / v9.1.3 PV-03 / v9.4.0 PV-03 wiring: the FINAL
        dispatch payload of every return path is run through the
        lifecycle hook chain (``pre_dispatch`` → ``post_dispatch`` →
        ``pre_handoff`` → ``pre_plugin_invocation``) per Soul Rule S-10.
        Hooks run in permissive mode — see
        :func:`devolaflow.feedback_emit._fire_hook_chain` for the R5
        strict-byte-identical contract.

        v10.6.0 PV-02 (D-Q-2): the deep-copy + reinforcement merge +
        hook chain pipeline now lives on
        :class:`devolaflow.feedback_emit.ProposalEmitter`. This class
        retains :meth:`generate_reinforcement` (which extracts
        :class:`ReinforcementBlock` from a :class:`GateVerdict`) and
        passes it as the ``reinforcement_factory`` callable so the
        v6-01 wiring contract is preserved verbatim.

        The input ``base_dispatch`` is never mutated; a deep copy is
        returned in all cases.
        """
        return self._emitter.emit(
            base_dispatch=base_dispatch,
            verdict=verdict,
            round_num=round_num,
            target_score=target_score,
            severity_floor=severity_floor,
            reinforcement_factory=self.generate_reinforcement,
        )


# ---------------------------------------------------------------------------
# v14.5.0 (ADR-006 / gap G-025) — PERMANENT re-export shims for the module
# split. ``feedback.py`` keeps the feedback classes
# (``FeedbackCollector`` / ``FeedbackAnalyzer`` / ``ProposalGenerator`` —
# incl. the S-10-named ``ProposalGenerator.generate_round_dispatch``, which
# does NOT move); the extracted concerns live in:
#
#   * ``gate/cascade.py``  — populate_cascade_gate_fields +
#     populate_intra_task_convergence (+ their constants), beside the
#     validators they pair with
#   * ``dispatch.py``      — dispatch_wave_tasks + dispatch_dogfood_cycle
#     (the wave-execution / dogfood dispatch wrappers; see its module
#     docstring for the full shim tracking table)
#
# Deprecation note: prefer the new owner-module paths in NEW code. These
# shims are PERMANENT (lifetime >= v16.0.0, revisit then — per the ADR's
# shim clause): Soul rule S-10 names ``feedback.py`` verbatim and
# ``schemas/lean-dispatch.yaml`` line 683 names
# ``feedback.py::populate_cascade_gate_fields`` — neither text changes; the
# shim preserves the path contract. Every re-export below is
# identity-preserving (``old_path.symbol is new_path.symbol``), pinned by
# ``tests/test_module_split_shims.py``.
# ---------------------------------------------------------------------------
from devolaflow.dispatch import (  # noqa: E402, F401
    dispatch_dogfood_cycle,
    dispatch_wave_tasks,
)
from devolaflow.gate.cascade import (  # noqa: E402, F401
    INTRA_TASK_CONVERGENCE_TASK_TYPES,
    INTRA_TASK_MAX_ROUNDS_DEFAULT,
    populate_cascade_gate_fields,
    populate_intra_task_convergence,
)
