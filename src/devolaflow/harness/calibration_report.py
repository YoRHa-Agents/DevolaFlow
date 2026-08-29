"""Markdown rendering for CLI calibration reports."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def _render_cell_line(cell: Mapping[str, Any]) -> str:
    counts = cell["counts"]
    pass_rate = cell["pass_rate"]
    rate = (
        f"{pass_rate['value']:.3f} CI95={pass_rate['ci95']}"
        if pass_rate["value"] is not None
        else "INSUFFICIENT"
    )
    latency = cell["wall_time_seconds"]
    latency_text = (
        f"p50={latency['p50']:.4f}, p95={latency['p95']:.4f}"
        if latency["status"] == "AVAILABLE"
        else "INSUFFICIENT"
    )
    tokens = cell["token_cost"]
    token_text = f"mean={tokens['mean']:.1f}" if tokens["mean"] is not None else "INSUFFICIENT"
    return (
        f"| {cell['task_class']} | {cell['channel']} | {cell['arm']} | "
        f"{counts['n']} | {counts['pass']} | {counts['fail']} | {counts['insufficient']} | "
        f"{rate} | {latency_text} | {token_text} |"
    )


def render_calibration_report(report: Mapping[str, Any]) -> str:
    """Render a report without absolute paths or raw CLI output."""

    metadata = report["metadata"]
    matrix = report["matrix"]
    counts = report["summary"]["counts"]
    lines = [
        "# v21.1.0 PV-02 CLI calibration ROI",
        "",
        f"- Run ID: `{report['run_id']}`",
        f"- Generated at: `{metadata['generated_at']}`",
        f"- Fixed salt: `{metadata['salt']}`",
        f"- Seed: `{metadata['seed']}`",
        "",
        "## Matrix design",
        "",
        f"- Task classes: `{', '.join(matrix['task_classes'])}`",
        f"- Channels: `{', '.join(matrix['channels'])}`",
        f"- Arms: `{', '.join(matrix['arms'])}`",
        f"- Replicates per cell: `{matrix['replicates']}`",
        f"- Planned specs: `{matrix['planned_specs']}`",
        f"- Per-probe timeout: `{matrix['timeout_seconds']}` seconds",
        f"- Outer timeout: `{matrix['total_timeout_seconds']}` seconds",
        "- Order: `task class → channel → arm → replicate`, delegated to `plan_probe_matrix`.",
        "",
        "## CLI preflight",
        "",
        "| Channel | Executable | Version check | Auth status | Evidence |",
        "|---|---:|---|---|---|",
    ]
    for item in report["preflight"]:
        version = item["version_check"]
        lines.append(
            f"| {item['channel']} | {item['executable_available']} | "
            f"{version['status']} (exit={version['exit_code']}) | "
            f"{item['auth_status']} | {item['auth_evidence']} |"
        )
    lines.extend(
        [
            "",
            "## Execution counts",
            "",
            f"- Planned: `{counts['planned']}`",
            f"- Observed artifacts: `{counts['observed']}`",
            f"- Completed CLI outcomes (PASS + FAIL): `{counts['completed']}`",
            f"- PASS: `{counts['pass']}`; FAIL: `{counts['fail']}`; "
            f"INSUFFICIENT: `{counts['insufficient']}`",
            f"- Unrecorded: `{counts['unrecorded']}`",
            "",
            "## Cell results",
            "",
            "| Task | Channel | Arm | n | PASS | FAIL | INSUFFICIENT | "
            "Pass rate / CI95 | Wall p50/p95 (s) | Token mean |",
            "|---|---|---|---:|---:|---:|---:|---|---|---|",
        ]
    )
    lines.extend(_render_cell_line(cell) for cell in report["summary"]["cells"])
    lines.extend(["", "## Skill-on/off differences", ""])
    for comparison in report["summary"]["comparisons"]:
        difference = comparison["pass_rate_difference"]
        lines.append(
            f"- `{comparison['task_class']}/{comparison['channel']}`: "
            f"pass-rate skill-on minus skill-off = "
            f"`{difference['skill_on_minus_skill_off']}`; CI95 = `{difference['ci95']}`; "
            f"status = `{difference['status']}`. "
            f"Wall uncertainty: `{comparison['wall_time_p50_difference_seconds']['uncertainty']}`; "
            f"token uncertainty: `{comparison['token_cost_difference']['uncertainty']}`."
        )
    lines.extend(
        [
            "",
            "## ROI conclusion",
            "",
            f"- Status: `{report['summary']['roi']['status']}`",
            f"- {report['summary']['roi']['conclusion']}",
            f"- Quality causality: `{report['summary']['roi']['quality_causality']}`",
            "",
            "## Limitations",
            "",
            "- CLI availability, authentication, timeout, and non-zero outcomes are not "
            "replaced by simulated results.",
            "- Missing token usage is `null`/`INSUFFICIENT`; it is never treated as zero.",
            "- Missing `skill_loaded` observation is `null`/`INSUFFICIENT`; arm names are "
            "not proof of skill loading.",
            "- A complete matrix with unavailable telemetry remains insufficient for token "
            "ROI and causal quality claims.",
            "- Raw diagnostics are retained only in repository-relative probe artifacts; "
            "this report does not include full stdout/stderr.",
            "",
        ]
    )
    return "\n".join(lines)


__all__ = ["render_calibration_report"]
