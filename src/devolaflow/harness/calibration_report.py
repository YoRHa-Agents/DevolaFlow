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
    latency_text = "INSUFFICIENT"
    if latency["status"] == "AVAILABLE":
        latency_text = f"p50={latency['p50']:.4f}, p95={latency['p95']:.4f}"
    tokens = cell["token_cost"]
    token_text = (
        f"mean={tokens['mean']:.1f}"
        if tokens["status"] == "AVAILABLE" and tokens["mean"] is not None
        else "INSUFFICIENT"
    )
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
    execution = report.get("execution", {})
    telemetry = report.get("telemetry", {})
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
        "## Calibration lifecycle",
        "",
        f"- Started at: `{execution.get('started_at')}`",
        f"- Finished at: `{execution.get('finished_at')}`",
        f"- Timeout phase: `{execution.get('timeout_phase')}`",
        f"- Termination reason: `{execution.get('termination_reason')}`",
        f"- Telemetry ledger: `{telemetry.get('ledger_path')}`",
        f"- New telemetry records: `{telemetry.get('appended_records', 0)}`",
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
        paired = comparison.get("paired_differences")
        lines.append(
            f"- `{comparison['task_class']}/{comparison['channel']}`: "
            f"legacy pass-rate skill-on minus skill-off = "
            f"`{difference['skill_on_minus_skill_off']}`; legacy CI95 = `{difference['ci95']}`; "
            f"status = `{difference['status']}`."
        )
        if paired is None:
            lines.append(
                f"  Legacy report has no matched-replicate bootstrap data. "
                f"Wall uncertainty: "
                f"`{comparison['wall_time_p50_difference_seconds']['uncertainty']}`; "
                f"token uncertainty: `{comparison['token_cost_difference']['uncertainty']}`."
            )
            continue
        paired_pass = paired["pass_rate"]
        paired_latency = paired["wall_time_seconds"]
        paired_tokens = paired["token_cost"]
        lines.append(
            f"  Paired pass-rate on-minus-off = `{paired_pass['skill_on_minus_skill_off']}`; "
            f"bootstrap CI95 = `{paired_pass['ci95']}`; pairs = "
            f"`{paired['pairing']['observed_pairs']}/{paired['pairing']['expected_pairs']}`; "
            f"status = `{paired_pass['status']}`. "
            f"Paired wall mean delta = `{paired_latency['skill_on_minus_skill_off']}` "
            f"({paired_latency['status']}); paired token mean delta = "
            f"`{paired_tokens['skill_on_minus_skill_off']}` ({paired_tokens['status']})."
        )
        lines.append(
            f"  Bootstrap: `{paired['bootstrap']['method']}`, seed "
            f"`{paired['bootstrap']['seed']}`, replicates "
            f"`{paired['bootstrap']['replicates']}`, unit "
            f"`{paired['bootstrap']['resample_unit']}`; "
            f"{paired['causal_interpretation']}"
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
            "- Skill-on requires an exact structured `skill_canary_echo`; missing or mismatched "
            "echoes remain `null`/`INSUFFICIENT`.",
            "- Kimi usage reports distinguish missing usage from parser mismatch and retain "
            "the inspected JSON source path.",
            "- Wilson intervals are descriptive success-rate intervals only; with n=5 they "
            "do not establish significance or causality.",
            "- p95 from n=5 is the maximum observed value, not a stable tail estimate.",
            "- MDE and statistical power are limited by the small, matched sample; no "
            "pre-specified MDE or powered causal inference is claimed.",
            "- Paired bootstrap resamples matched replicate pairs within each cell; it "
            "quantifies observed association and does not establish a causal skill effect.",
            "- Incomplete cells retain any observed partial summaries in machine-readable "
            "`observed_partial` fields only; the default table shows them as `INSUFFICIENT`.",
            "- A complete matrix with unavailable telemetry remains insufficient for token "
            "ROI and causal quality claims.",
            "- Raw diagnostics are retained only in repository-relative probe artifacts; "
            "this report does not include full stdout/stderr.",
            "",
        ]
    )
    return "\n".join(lines)


__all__ = ["render_calibration_report"]
