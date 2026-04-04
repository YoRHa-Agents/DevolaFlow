"""Gate report generation (YAML + Markdown).

Design ref: design_decomposition_gate.md §5.5, Appendix B
"""

from __future__ import annotations

from datetime import UTC, datetime

import yaml

from devolaflow.gate.convergence import compute_trend
from devolaflow.gate.models import (
    CheckResult,
    ConvergenceRound,
    GateProfile,
    GateVerdict,
)


def _check_dict(cr: CheckResult) -> dict[str, object]:
    return {"status": cr.status, **cr.details}


def generate_yaml_report(
    verdict: GateVerdict,
    check_results: dict[str, CheckResult],
    history: list[ConvergenceRound] | None = None,
    profile: GateProfile | None = None,
    *,
    stage_id: str = "",
    stage_name: str = "",
    gate_type: str = "standard",
) -> str:
    """Produce a YAML gate report matching the §5.5 schema."""
    if history is None:
        history = []
    now = datetime.now(UTC).isoformat()

    report: dict[str, object] = {
        "gate_report": {
            "header": {
                "gate_id": f"G_{stage_id}" if stage_id else "G_unknown",
                "stage_id": stage_id,
                "stage_name": stage_name,
                "gate_type": gate_type,
                "gate_profile": profile.name if profile else "standard",
                "timestamp": now,
                "round": len(history) if history else 1,
                "max_rounds": profile.max_rounds if profile else 1,
            },
            "verdict": {
                "decision": verdict.decision,
                "rationale": verdict.rationale,
                "composite_score": verdict.composite_score,
                "meets_threshold": verdict.meets_threshold,
            },
            "check_results": {name: _check_dict(cr) for name, cr in check_results.items()},
        }
    }

    if history:
        trend = compute_trend(history)
        report["gate_report"]["convergence_history"] = {  # type: ignore[index]
            "rounds": [
                {
                    "round": r.round_num,
                    "composite_score": r.composite_score,
                    "blocker_count": r.blocker_count,
                    "critical_count": r.critical_count,
                    "timestamp": r.timestamp,
                }
                for r in history
            ],
            "trend": trend,
        }

    return yaml.dump(report, default_flow_style=False, sort_keys=False)


def _trend_arrow(history: list[ConvergenceRound], idx: int) -> str:
    if idx == 0:
        return "—"
    delta = history[idx].composite_score - history[idx - 1].composite_score
    if delta > 0:
        return "^"
    if delta < 0:
        return "v"
    return "="


def generate_markdown_report(
    verdict: GateVerdict,
    check_results: dict[str, CheckResult],
    history: list[ConvergenceRound] | None = None,
    profile: GateProfile | None = None,
    *,
    stage_id: str = "",
    stage_name: str = "",
    gate_type: str = "standard",
) -> str:
    """Produce a human-readable Markdown gate report (Appendix B template)."""
    if history is None:
        history = []
    now = datetime.now(UTC).isoformat()
    max_rounds = profile.max_rounds if profile else 1
    current_round = len(history) if history else 1
    threshold = profile.composite_threshold if profile else "N/A"
    score_display = (
        f"{verdict.composite_score:.1f}" if verdict.composite_score is not None else "N/A"
    )

    lines: list[str] = [
        f"# Gate Report: {stage_name or stage_id}",
        "",
        "## Summary",
        "| Field | Value |",
        "|-------|-------|",
        f"| Stage | {stage_id}: {stage_name} |",
        f"| Gate Type | {gate_type} |",
        f"| Profile | {profile.name if profile else 'N/A'} |",
        f"| Round | {current_round}/{max_rounds} |",
        f"| Verdict | **{verdict.decision}** |",
        f"| Composite Score | {score_display}/{threshold} |",
        f"| Timestamp | {now} |",
        "",
        "## Check Results",
    ]

    for name, cr in check_results.items():
        lines.append("")
        lines.append(f"### {name.replace('_', ' ').title()}")
        lines.append(f"- Status: {cr.status.upper()}")
        for key, val in cr.details.items():
            lines.append(f"- {key.replace('_', ' ').title()}: {val}")

    if history:
        lines.append("")
        lines.append("## Convergence History")
        lines.append("| Round | Composite | Blockers | Criticals | Trend |")
        lines.append("|-------|-----------|----------|-----------|-------|")
        for idx, r in enumerate(history):
            arrow = _trend_arrow(history, idx)
            lines.append(
                f"| {r.round_num} | {r.composite_score:.1f} | "
                f"{r.blocker_count} | {r.critical_count} | {arrow} |"
            )

    lines.extend(
        [
            "",
            "## Decision",
            f"**Verdict**: {verdict.decision}",
            f"**Rationale**: {verdict.rationale}",
        ]
    )

    return "\n".join(lines) + "\n"
